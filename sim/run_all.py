# -*- coding: utf-8 -*-
"""兼容入口：旧“一键复现全部”已废止，必须显式选择一个有边界的阶段。"""
import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
STAGES = {
    "core_smoke": "core_smoke.py",
    "report_rebuild": "report_rebuild.py",
    "artifact_verify": "artifact_verify.py",
}


def main():
    ap = argparse.ArgumentParser(
        description="分阶段入口；不再承诺一条命令重建全部专项实验或 AB 证据")
    ap.add_argument("stage", choices=sorted(STAGES))
    a = ap.parse_args()
    raise SystemExit(subprocess.call([sys.executable, "-B",
                                      os.path.join(HERE, STAGES[a.stage])]))


if __name__ == "__main__":
    main()
