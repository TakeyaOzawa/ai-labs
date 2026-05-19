"""gws_client: GWS API操作の共通クラス。

Google Workspace APIの認証・ファイル取得ロジックを集約する。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class GWSConfig:
    """GWS API設定。"""

    credentials_path: Path = field(
        default_factory=lambda: Path.home() / ".config" / "gws" / "credentials.json"
    )
    token_path: Path = field(
        default_factory=lambda: Path.home() / ".config" / "gws" / "token.json"
    )
    scopes: list[str] = field(default_factory=list)


class GWSClient:
    """Google Workspace API操作の共通クラス。

    認証フロー・ファイル取得・メタデータ抽出のロジックを集約する。
    具体的なAPI呼び出しは各GWSスクリプトが行い、このクラスは共通処理を提供する。
    """

    def __init__(self, config: GWSConfig | None = None) -> None:
        self._config = config or GWSConfig()
        self._service = None

    @property
    def config(self) -> GWSConfig:
        return self._config

    def authenticate(self) -> bool:
        """Google API認証を実行する。

        Returns:
            認証成功時True
        """
        # 実装は各GWSスクリプトの認証ロジックを統合後に追加
        # 現時点ではスケルトンのみ
        return self._config.credentials_path.exists()
