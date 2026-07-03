# -*- coding: utf-8 -*-
"""
run_all.py — 一键复现全部仿真产物(报告数据链的复现入口,评委/队友可跑)
顺序:回归测试 → 主对比+CSV → ST 一致性数据生成 → 多seed实验矩阵 → 全部图表
任何一步失败立即停止并报错。总耗时约 1-2 分钟。
运行:python run_all.py
"""
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

STEPS = [
    ("回归测试(15用例)", [sys.executable, os.path.join(HERE, "tests", "test_sim.py")]),
    ("主对比+CSV导出", [sys.executable, os.path.join(HERE, "warehouse_sim.py"),
                        "--csv", os.path.join(HERE, "out")]),
    ("ST一致性数据生成", [sys.executable, os.path.join(HERE, "export_st_vectors.py")]),
    ("多seed实验矩阵", [sys.executable, os.path.join(HERE, "experiments.py")]),
    ("报告图表(5张)", [sys.executable, os.path.join(HERE, "plots.py")]),
]


def main():
    t0 = time.time()
    for name, cmd in STEPS:
        print(f"\n{'=' * 20} {name} {'=' * 20}")
        r = subprocess.run(cmd)
        if r.returncode != 0:
            print(f"\n!! 步骤失败:{name}(exit={r.returncode}),后续已停止")
            sys.exit(r.returncode)
    print(f"\n全部完成,耗时 {time.time() - t0:.0f}s。产物:")
    for sub in ("out", "figs"):
        d = os.path.join(HERE, sub)
        if os.path.isdir(d):
            for f in sorted(os.listdir(d)):
                print(f"  sim/{sub}/{f}")
    print("  plc/07_GVL_Data_generated.st")


if __name__ == "__main__":
    main()
