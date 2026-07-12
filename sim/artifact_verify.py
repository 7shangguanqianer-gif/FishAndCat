# -*- coding: utf-8 -*-
"""文本/CSV 联动门；不等价于 Word/PPT 逐页视觉验收或 AB 动态验证。"""
import os
import subprocess
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def main():
    steps = [
        [sys.executable, "-B", "-m", "unittest",
         "sim.tests.test_method_integrity.TestSplitCsvSchemas", "-v"],
        [sys.executable, "-B", os.path.join(ROOT, "tools", "doc_check.py")],
    ]
    for cmd in steps:
        rc = subprocess.call(cmd, cwd=ROOT)
        if rc:
            raise SystemExit(rc)
    print("artifact_verify PASS：CSV schema + 文档文本联动检查")


if __name__ == "__main__":
    main()
