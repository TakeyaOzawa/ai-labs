"""Python 3.12 バージョンガード。"""

import sys


def check_python_version() -> None:
    """Python 3.12 以外で実行された場合に終了する。"""
    if sys.version_info[:2] != (3, 12):
        sys.exit(f"Error: requires python3.12 (current: {sys.version_info.major}.{sys.version_info.minor})")
