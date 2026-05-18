#!/usr/bin/env python3.12
"""
Version check utility for Python scripts
"""

import sys

def check_python_version():
    """Check if Python version is 3.12 or higher"""
    if sys.version_info < (3, 12):
        print(f"❌ Python 3.12以上が必要です。現在のバージョン: {sys.version}")
        sys.exit(1)

if __name__ == "__main__":
    check_python_version()
    print("✅ Python version check passed")
