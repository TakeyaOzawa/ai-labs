"""ルートconftest: sys.pathにlib/を追加し、全テストからlib配下をimport可能にする。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
