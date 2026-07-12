# -*- coding: utf-8 -*-
"""仅从当前已存在 CSV/PNG 重建报告与 PPT；不声称重跑上游全部实验。"""
import os
import subprocess
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    for name in ("build_report.py", "build_ppt.py"):
        rc = subprocess.call([sys.executable, "-B", os.path.join(HERE, name)])
        if rc:
            raise SystemExit(rc)
    print("report_rebuild PASS：仅完成 DOCX/PPTX 生成；仍需独立渲染与视觉 QA")


if __name__ == "__main__":
    main()
