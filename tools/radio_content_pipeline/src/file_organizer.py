#!/usr/bin/env python3.12
"""
file_organizer: ファイル配置・ローテーション管理

目的:
    パイプラインの各ステップ完了後に呼び出され、
    ファイルを最終配置先にコピーし、ローテーションを管理する。

使い方:
    python3.12 src/file_organizer.py --file <path>
    python3.12 src/file_organizer.py --all

例:
    python3.12 src/file_organizer.py --file data/recordings/TBS_空気階段の踊り場_20260519.m4a
    python3.12 src/file_organizer.py --file data/summaries/TBS_空気階段の踊り場_20260519_summary.md
    python3.12 src/file_organizer.py --all

出力: ファイル配置結果（JSON）
依存: なし（標準ライブラリのみ）
"""
import argparse
import json
import re
import shutil
import sys
from pathlib import Path

# ─── 定数 ────────────────────────────────────────────────────────

HOME = Path.home()
OUTPUT_BASE = HOME / "Documents" / "works" / "scout_reports" / "radio_contents"
MAX_TMP_FILES = 5  # tmp/ 配下の最大保持件数（番組ごと）

# パイプラインのデータディレクトリ（ソース）
PIPELINE_DIR = HOME / "tools" / "radio_content_pipeline"
RECORDINGS_DIR = PIPELINE_DIR / "data" / "recordings"
TRANSCRIPTS_DIR = PIPELINE_DIR / "data" / "transcripts"
SUMMARIES_DIR = PIPELINE_DIR / "data" / "summaries"


# ─── ファイル名パース ────────────────────────────────────────────

def parse_filename(file_path: Path) -> dict | None:
    """ファイル名から局名・番組名・日付・種別をパースする。

    入力パターン:
        TBS_空気階段の踊り場_20260519.m4a
        TBS_空気階段の踊り場_20260519.json
        TBS_空気階段の踊り場_20260519_summary.md

    Returns:
        パース結果のdict、またはパース失敗時にNone
    """
    name = file_path.name
    suffix = file_path.suffix

    # _summary.md の判定
    is_summary = name.endswith("_summary.md")

    if is_summary:
        # _summary.md を除去してからパース
        base = name.removesuffix("_summary.md")
        file_type = "summary"
    else:
        base = file_path.stem
        if suffix == ".m4a":
            file_type = "audio"
        elif suffix == ".json":
            file_type = "transcript"
        else:
            return None

    # _ で分割
    parts = base.split("_")
    if len(parts) < 3:
        return None

    # 最初の要素 = 局名
    station_id = parts[0]

    # 最後の要素 = 日付（8桁数字）
    date_str = parts[-1]
    if not re.match(r"^\d{8}$", date_str):
        return None

    # 中間の要素 = 番組名
    program_name = "_".join(parts[1:-1])
    if not program_name:
        return None

    # 番組ディレクトリ名
    program_dir_name = f"{station_id}_{program_name}"

    return {
        "station_id": station_id,
        "program_name": program_name,
        "date": date_str,
        "file_type": file_type,
        "program_dir_name": program_dir_name,
    }


# ─── 配置ロジック ────────────────────────────────────────────────

def get_destination(parsed: dict, file_path: Path) -> Path:
    """配置先パスを決定する。

    Args:
        parsed: parse_filename() の結果
        file_path: 元ファイルパス（拡張子取得用）

    Returns:
        配置先の絶対パス
    """
    program_dir = OUTPUT_BASE / parsed["program_dir_name"]
    date = parsed["date"]
    station = parsed["station_id"]
    program = parsed["program_name"]

    if parsed["file_type"] == "summary":
        # 要約MDは番組ディレクトリ直下
        return program_dir / f"{date}_{station}_{program}_summary.md"
    else:
        # 音声・文字起こしはtmp/配下
        suffix = file_path.suffix
        return program_dir / "tmp" / f"{date}_{station}_{program}{suffix}"


def place_file(file_path: Path) -> dict:
    """ファイルを最終配置先にコピーする。

    Args:
        file_path: コピー元ファイルパス

    Returns:
        配置結果のdict
    """
    if not file_path.exists():
        return {
            "success": False,
            "error": f"ファイルが存在しません: {file_path}",
            "source": str(file_path),
        }

    parsed = parse_filename(file_path)
    if parsed is None:
        return {
            "success": False,
            "error": f"ファイル名をパースできません: {file_path.name}",
            "source": str(file_path),
        }

    destination = get_destination(parsed, file_path)

    # 配置先に同名ファイルが既に存在する場合はスキップ
    if destination.exists():
        return {
            "success": True,
            "source": str(file_path),
            "destination": str(destination),
            "skipped": True,
            "rotated": 0,
        }

    # ディレクトリ作成
    destination.parent.mkdir(parents=True, exist_ok=True)

    # コピー実行
    shutil.copy2(file_path, destination)

    # ローテーション実行（tmp/配下のファイルの場合）
    rotated = 0
    if parsed["file_type"] in ("audio", "transcript"):
        rotated = rotate_tmp_files(parsed["program_dir_name"])

    return {
        "success": True,
        "source": str(file_path),
        "destination": str(destination),
        "rotated": rotated,
    }


# ─── ローテーション ──────────────────────────────────────────────

def rotate_tmp_files(program_dir_name: str) -> int:
    """tmp/配下のファイルをローテーションする。

    .m4aファイルを日付順にソートし、MAX_TMP_FILES件を超えたら
    古い順に削除する。削除時は対応する.jsonも一緒に削除。

    Args:
        program_dir_name: 番組ディレクトリ名（例: TBS_空気階段の踊り場）

    Returns:
        削除したペア数
    """
    tmp_dir = OUTPUT_BASE / program_dir_name / "tmp"
    if not tmp_dir.exists():
        return 0

    # .m4a ファイルを日付順にソート（ファイル名先頭がYYYYMMDD）
    m4a_files = sorted(tmp_dir.glob("*.m4a"))

    if len(m4a_files) <= MAX_TMP_FILES:
        return 0

    # 古い順に削除（先頭が最も古い）
    files_to_remove = m4a_files[:len(m4a_files) - MAX_TMP_FILES]
    rotated = 0

    for m4a_file in files_to_remove:
        # 対応する.jsonファイル
        json_file = m4a_file.with_suffix(".json")

        # .m4a 削除
        m4a_file.unlink()

        # 対応する .json があれば削除
        if json_file.exists():
            json_file.unlink()

        rotated += 1

    return rotated


# ─── --all モード ────────────────────────────────────────────────

def place_all_files() -> list[dict]:
    """data/配下の全ファイルをスキャンして未配置ファイルを配置する。

    Returns:
        各ファイルの配置結果リスト
    """
    results = []

    # スキャン対象ディレクトリとパターン
    scan_targets = [
        (RECORDINGS_DIR, "*.m4a"),
        (TRANSCRIPTS_DIR, "*.json"),
        (SUMMARIES_DIR, "*_summary.md"),
    ]

    for directory, pattern in scan_targets:
        if not directory.exists():
            continue
        for file_path in sorted(directory.glob(pattern)):
            if file_path.is_file():
                result = place_file(file_path)
                results.append(result)

    return results


# ─── CLI ─────────────────────────────────────────────────────────

def main():
    """CLIエントリポイント。"""
    parser = argparse.ArgumentParser(
        description="ファイル配置・ローテーション管理"
    )
    parser.add_argument(
        "--file",
        type=str,
        help="配置するファイルのパス",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="data/配下の全ファイルをスキャンして配置",
    )
    args = parser.parse_args()

    if not args.file and not args.all:
        parser.print_help()
        sys.exit(2)

    if args.file:
        file_path = Path(args.file).resolve()
        result = place_file(file_path)
        print(json.dumps(result, ensure_ascii=False))
        if not result["success"]:
            sys.exit(1)

    elif args.all:
        results = place_all_files()
        summary = {
            "success": True,
            "total": len(results),
            "placed": sum(
                1 for r in results
                if r["success"] and not r.get("skipped")
            ),
            "skipped": sum(1 for r in results if r.get("skipped")),
            "failed": sum(1 for r in results if not r["success"]),
            "rotated": sum(r.get("rotated", 0) for r in results),
            "files": results,
        }
        print(json.dumps(summary, ensure_ascii=False))
        if summary["failed"] > 0:
            sys.exit(1)


if __name__ == "__main__":
    main()
