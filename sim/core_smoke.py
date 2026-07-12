# -*- coding: utf-8 -*-
"""核心 Python 回归门；不重建长耗时专项、报告/PPT 或 AB 产物。"""
import os
import subprocess
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
STEPS = [
    [sys.executable, "-B", "-m", "unittest", "discover", "-s",
     os.path.join(HERE, "tests"), "-v"],
    [sys.executable, "-B", os.path.join(HERE, "headline.py")],
]


def main():
    for cmd in STEPS:
        rc = subprocess.call(cmd)
        if rc:
            raise SystemExit(rc)
    print("core_smoke PASS：完整 unittest discover + 5-seed headline 回归锚")


if __name__ == "__main__":
    main()
