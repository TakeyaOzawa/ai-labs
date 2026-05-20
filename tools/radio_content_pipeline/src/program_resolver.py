#!/usr/bin/env python3.12
"""
program_resolver: 番組表API照合モジュール

目的:
    config/programs.ymlの番組リストをradiko番組表APIと照合し、
    タイムフリー対象の放送回を特定してyt-dlp用URLを生成する。

使い方:
    python3.12 src/program_resolver.py
    python3.12 src/program_resolver.py --config /app/config/programs.yml

出力: JSON（検出された番組リスト）
依存: pyyaml
"""
import argparse
import json
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ─── 定数定義 ────────────────────────────────────────────────────

JST = timezone(timedelta(hours=9))

# radiko番組表API（v4: yt-dlp-rajikoが使用しているバージョン）
RADIKO_PROGRAM_API = "https://radiko.jp/v3/program/station/weekly/{station_id}.xml"

# タイムフリー対象期間（放送後1週間）
TIMEFREE_DAYS = 7

# yt-dlp-rajiko用URLテンプレート
RADIKO_TIMEFREE_URL = "https://radiko.jp/#!/ts/{station_id}/{start_time}"

DEFAULT_CONFIG_PATH = Path("/app/config/programs.yml")

REQUEST_TIMEOUT = 30


# ─── 設定ファイル読み込み ────────────────────────────────────────

def load_programs_config(config_path: Path) -> list[dict]:
    """programs.ymlを読み込んで番組リストを返す。

    Args:
        config_path: programs.ymlのパス

    Returns:
        番組設定のリスト

    Raises:
        FileNotFoundError: 設定ファイルが存在しない場合
        ValueError: 設定ファイルの形式が不正な場合
    """
    import yaml

    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")

    content = config_path.read_text(encoding="utf-8")
    data = yaml.safe_load(content)

    if not data or "programs" not in data:
        raise ValueError(f"Invalid config format: {config_path}")

    programs = data["programs"]
    if not isinstance(programs, list):
        raise ValueError("'programs' must be a list")

    # バリデーション
    for prog in programs:
        has_name = "name" in prog and prog["name"]
        has_performer = "performer_contains" in prog and prog["performer_contains"]
        if not has_name and not has_performer:
            raise ValueError(
                f"Program entry requires 'name' or 'performer_contains': {prog}"
            )
        prog.setdefault("source", "radiko")
        prog.setdefault("name", "")  # name未指定時は空文字（全番組マッチ）
        prog.setdefault("station_id", "")  # station_id未指定時は全局検索

    return programs


# ─── radiko番組表API ─────────────────────────────────────────────

def fetch_weekly_programs(station_id: str) -> list[dict]:
    """radiko番組表APIから1週間分の番組情報を取得する。

    Args:
        station_id: 放送局ID（例: TBS, LFR, QRR）

    Returns:
        番組情報のリスト。各要素は:
        {
            "title": str,
            "station_id": str,
            "start_time": str (YYYYMMDDHHmmss),
            "end_time": str (YYYYMMDDHHmmss),
            "date": str (YYYYMMDD),
            "description": str,
            "performers": str,
        }

    Raises:
        urllib.error.HTTPError: API呼び出し失敗時
    """
    import gzip

    url = RADIKO_PROGRAM_API.format(station_id=station_id)
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "radio-pipeline/1.0")
    req.add_header("Accept-Encoding", "gzip, deflate")

    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
        raw_data = resp.read()
        # gzip圧縮されている場合はデコード
        if resp.headers.get("Content-Encoding") == "gzip" or raw_data[:2] == b'\x1f\x8b':
            raw_data = gzip.decompress(raw_data)
        xml_content = raw_data.decode("utf-8")

    root = ET.fromstring(xml_content)
    programs = []

    for prog in root.iter("prog"):
        ft = prog.get("ft", "")
        to = prog.get("to", "")
        title_elem = prog.find("title")
        desc_elem = prog.find("desc")
        pfm_elem = prog.find("pfm")

        title = title_elem.text if title_elem is not None and title_elem.text else ""
        description = desc_elem.text if desc_elem is not None and desc_elem.text else ""
        performers = pfm_elem.text if pfm_elem is not None and pfm_elem.text else ""

        if ft and title:
            programs.append({
                "title": title,
                "station_id": station_id,
                "start_time": ft,
                "end_time": to,
                "date": ft[:8],
                "description": description,
                "performers": performers,
            })

    return programs


# ─── 番組検索 ────────────────────────────────────────────────────

def search_program(
    programs: list[dict],
    target_name: str,
    day_of_week: int | None = None,
    performer_contains: str = "",
) -> list[dict]:
    """番組リストから対象番組を検索する（部分一致）。

    Args:
        programs: fetch_weekly_programsの戻り値
        target_name: 検索する番組名（空文字の場合は番組名フィルタなし）
        day_of_week: 曜日フィルタ（0=月曜, 6=日曜）。Noneで全曜日
        performer_contains: 出演者フィルタ（部分一致）。空文字の場合はフィルタなし

    Returns:
        マッチした番組のリスト
    """
    matches = []
    for prog in programs:
        # 番組名フィルタ（target_nameが空なら全番組マッチ）
        if target_name and target_name not in prog["title"]:
            continue

        # 出演者フィルタ
        if performer_contains:
            performers = prog.get("performers", "") or ""
            if performer_contains not in performers:
                continue

        # 曜日フィルタ
        if day_of_week is not None:
            try:
                dt = datetime.strptime(prog["start_time"], "%Y%m%d%H%M%S")
                if dt.weekday() != day_of_week:
                    continue
            except ValueError:
                continue

        matches.append(prog)
    return matches


def filter_timefree_eligible(programs: list[dict]) -> list[dict]:
    """タイムフリー対象期間内の番組のみフィルタする。

    タイムフリー対象: 放送終了後1週間以内

    Args:
        programs: 番組リスト

    Returns:
        タイムフリー対象の番組リスト
    """
    now = datetime.now(JST)
    eligible = []

    for prog in programs:
        try:
            end_time = datetime.strptime(
                prog["end_time"], "%Y%m%d%H%M%S"
            ).replace(tzinfo=JST)
            # 放送終了済み かつ 1週間以内
            if end_time < now and (now - end_time).days < TIMEFREE_DAYS:
                eligible.append(prog)
        except (ValueError, KeyError):
            continue

    return eligible


# ─── URL生成 ─────────────────────────────────────────────────────

def generate_download_url(program: dict) -> str:
    """yt-dlp-rajiko用のダウンロードURLを生成する。

    Args:
        program: 番組情報dict

    Returns:
        radiko タイムフリーURL
    """
    return RADIKO_TIMEFREE_URL.format(
        station_id=program["station_id"],
        start_time=program["start_time"],
    )


def generate_output_filename(program: dict) -> str:
    """出力ファイル名を生成する。

    フォーマット: {station_id}_{title}_{date}.m4a

    Args:
        program: 番組情報dict

    Returns:
        ファイル名（拡張子付き）
    """
    # ファイル名に使えない文字を除去
    title = program["title"]
    for char in ['/', '\\', ':', '*', '?', '"', '<', '>', '|']:
        title = title.replace(char, '')

    return f"{program['station_id']}_{title}_{program['date']}.m4a"


# ─── メイン処理 ──────────────────────────────────────────────────

def resolve_programs(config_path: Path) -> list[dict]:
    """番組設定を読み込み、タイムフリー対象の放送回を検索する。

    Args:
        config_path: programs.ymlのパス

    Returns:
        ダウンロード対象の番組リスト。各要素は:
        {
            "program_name": str,
            "station_id": str,
            "title": str,
            "start_time": str,
            "end_time": str,
            "date": str,
            "download_url": str,
            "output_filename": str,
            "performers": str,
        }
    """
    config = load_programs_config(config_path)
    results = []

    for prog_config in config:
        if prog_config.get("source") != "radiko":
            continue

        station_id = prog_config.get("station_id", "")
        target_name = prog_config.get("name", "")
        day_of_week = prog_config.get("day_of_week")
        performer_contains = prog_config.get("performer_contains", "")

        # station_id 未指定時は全局を検索
        target_stations = [station_id] if station_id else list(KNOWN_STATIONS.keys())

        for sid in target_stations:
            try:
                weekly = fetch_weekly_programs(sid)
            except Exception as e:
                print(
                    f"[resolver] Failed to fetch programs for "
                    f"{sid}: {e}",
                    file=sys.stderr,
                )
                continue

            matches = search_program(
                weekly, target_name, day_of_week, performer_contains,
            )
            eligible = filter_timefree_eligible(matches)

            # program_name: name があればそれを使用、なければタイトルから取得
            for prog in eligible:
                program_name = target_name or prog["title"]
                results.append({
                    "program_name": program_name,
                    "station_id": sid,
                    "title": prog["title"],
                    "start_time": prog["start_time"],
                    "end_time": prog["end_time"],
                    "date": prog["date"],
                    "download_url": generate_download_url(prog),
                    "output_filename": generate_output_filename(prog),
                    "performers": prog.get("performers", ""),
                })

    return results


# ─── 番組検索（CLI用） ───────────────────────────────────────────

# radiko主要局一覧（関東エリア）
KNOWN_STATIONS: dict[str, str] = {
    "TBS": "TBSラジオ",
    "QRR": "文化放送",
    "LFR": "ニッポン放送",
    "RN1": "ラジオNIKKEI第1",
    "RN2": "ラジオNIKKEI第2",
    "INT": "InterFM897",
    "FMT": "TOKYO FM",
    "FMJ": "J-WAVE",
    "JORF": "ラジオ日本",
    "BAYFM78": "bayfm78",
    "NACK5": "NACK5",
    "YFM": "FMヨコハマ",
    "HOUSOU-DAIGAKU": "放送大学",
    "JOAK": "NHKラジオ第1（東京）",
    "JOAK-FM": "NHK-FM（東京）",
}


def list_stations() -> list[dict]:
    """利用可能な放送局一覧を返す。"""
    return [
        {"station_id": sid, "name": name}
        for sid, name in KNOWN_STATIONS.items()
    ]


def search_station_programs(
    station_id: str,
    keyword: str | None = None,
) -> list[dict]:
    """指定局の番組一覧を取得し、キーワードでフィルタする。

    Args:
        station_id: 放送局ID
        keyword: 番組名の部分一致キーワード（Noneで全件）

    Returns:
        番組情報のリスト（重複排除済み、タイトル順）
    """
    weekly = fetch_weekly_programs(station_id)

    # 重複排除（同一番組名は1件にまとめる）
    seen_titles: set[str] = set()
    unique_programs = []
    for prog in weekly:
        title = prog["title"]
        if title in seen_titles:
            continue
        seen_titles.add(title)

        if keyword and keyword.lower() not in title.lower():
            continue

        unique_programs.append(prog)

    # タイトル順でソート
    unique_programs.sort(key=lambda p: p["title"])
    return unique_programs


# ─── CLI ─────────────────────────────────────────────────────────

def main():
    """CLIエントリポイント。"""
    parser = argparse.ArgumentParser(
        description="radiko番組表照合 — 番組検索・タイムフリー対象番組検索"
    )
    subparsers = parser.add_subparsers(dest="command")

    # サブコマンド: resolve（デフォルト動作）
    resolve_parser = subparsers.add_parser(
        "resolve", help="programs.ymlの番組をradiko番組表と照合"
    )
    resolve_parser.add_argument(
        "--config", type=Path, default=DEFAULT_CONFIG_PATH,
        help="programs.ymlのパス",
    )

    # サブコマンド: search
    search_parser = subparsers.add_parser(
        "search", help="radiko番組表をキーワード検索"
    )
    search_parser.add_argument(
        "keyword", nargs="?", default=None,
        help="番組名の部分一致キーワード（省略で全件）",
    )
    search_parser.add_argument(
        "--station", "-s", default=None,
        help="放送局ID（例: TBS, LFR, QRR）。省略で主要局全て検索",
    )

    # サブコマンド: stations
    subparsers.add_parser(
        "stations", help="利用可能な放送局一覧を表示"
    )

    args = parser.parse_args()

    if args.command == "stations":
        stations = list_stations()
        for s in stations:
            print(f"  {s['station_id']:<15} {s['name']}")

    elif args.command == "search":
        target_stations = (
            [args.station] if args.station
            else list(KNOWN_STATIONS.keys())
        )

        all_results = []
        for station_id in target_stations:
            try:
                programs = search_station_programs(
                    station_id, args.keyword
                )
                for prog in programs:
                    all_results.append(prog)
            except Exception as e:
                print(
                    f"[search] {station_id}: {e}",
                    file=sys.stderr,
                )

        if not all_results:
            print("該当する番組が見つかりませんでした。")
            sys.exit(0)

        # 表形式で出力
        print(f"{'局ID':<10} {'番組名':<35} {'曜日時間':<20} {'出演者'}")
        print("─" * 90)
        for prog in all_results:
            # 放送時間をフォーマット
            try:
                dt = datetime.strptime(prog["start_time"], "%Y%m%d%H%M%S")
                weekdays = "月火水木金土日"
                day_str = weekdays[dt.weekday()]
                time_str = f"{day_str} {dt.strftime('%H:%M')}"
            except (ValueError, IndexError):
                time_str = prog.get("start_time", "")[:8]

            title = prog["title"][:33]
            performers = (prog.get("performers") or "")[:25]
            print(
                f"  {prog['station_id']:<8} {title:<35} "
                f"{time_str:<20} {performers}"
            )

        print(f"\n合計: {len(all_results)}件")

    elif args.command == "resolve" or args.command is None:
        config_path = (
            args.config if hasattr(args, "config") and args.config
            else DEFAULT_CONFIG_PATH
        )
        try:
            results = resolve_programs(config_path)
            output = {
                "success": True,
                "count": len(results),
                "programs": results,
            }
            print(json.dumps(output, ensure_ascii=False, indent=2))
        except Exception as e:
            output = {"success": False, "error": str(e)}
            print(json.dumps(output, ensure_ascii=False), file=sys.stderr)
            sys.exit(1)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
