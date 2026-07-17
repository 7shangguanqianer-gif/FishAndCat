# -*- coding: utf-8 -*-
"""
lap_optimal.py — T1.3 精确最优锚(U4;0706 枪F 裁决版)

原理:我们的批量分配目标 Σ score(g,slot) 各项均为 (货,位) 独立成本、无货物间
交互项 → 纯线性分配问题 LAP(多项式可解;含货物亲和项才是 QAP/NP-hard,
Reyes 2019 / Burkard QAP 综述背书)。scipy.optimize.linear_sum_assignment
(修正 Jonker-Volgenant,Crouse 2016)直接给**精确最优**,400×400 约 10ms——
比 CP-SAT 下界更快更硬,弃 OR-Tools(决策梯:已装依赖 scipy 能干)。

承重/容积硬约束编码:禁止边 big-M("forbidden assignment via prohibitive
cost",LAP 标准技巧)——不可行 (g,slot) 对赋 BIG,解出后检查未选中任何禁止边。

两个口径的最优锚:
  score 口径:min Σ score(g,slot)(与 AWRA-LS 同目标)→ gap = (AWRA−OPT)/OPT
             (报告列名 Gap(%),口径同 SLAPRP BCP 2024 惯例)
  exp_t 口径:min Σ freq·t(slot)/Σfreq(纯效率理论最优,重排不等式的含约束精确版)

三级证据链(报告 L3 章升级):松弛下界(analytic_bounds,忽略约束)
  ≤ LAP 精确最优(含约束) ≤ AWRA-LS 实测。

运行:python lap_optimal.py                     # 全场景×30 seeds(秒级)
     python lap_optimal.py --seeds 3           # 冒烟
输出:out/lap_gap.csv + 控制台 gap 汇总表
"""
import argparse
import csv
import math
import os
import statistics as st
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import numpy as np
from scipy.optimize import linear_sum_assignment

import warehouse_sim as ws
import instance_gen as ig

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
BIG = 1e9                                     # 禁止边 big-M(合法成本 ≤ 数量级 1e2)


def free_slots(rule):
    return [(c, t) for c in range(ws.COLS) for t in range(ws.TIERS)
            if not ws.preoccupied(c, t, rule)]


def _score_normalizers(goods, score_normalization):
    """返回 score 归一化参数；显式参数用于跨策略同目标证据链。"""
    if score_normalization is None:
        w_max = max(g.weight for g in goods)
        f_max = max(g.freq for g in goods)
        t_max = ws.t_max_now()
    else:
        required = {"w_max", "f_max", "t_max_s"}
        if set(score_normalization) != required:
            raise ValueError(
                "score_normalization must contain exactly w_max, f_max, t_max_s"
            )
        w_max = float(score_normalization["w_max"])
        f_max = float(score_normalization["f_max"])
        t_max = float(score_normalization["t_max_s"])
        runtime_t_max = float(ws.t_max_now())
        if not math.isclose(t_max, runtime_t_max, rel_tol=0.0, abs_tol=1e-9):
            raise ValueError(
                "score_normalization t_max_s does not match active motion model"
            )
    if not (math.isfinite(w_max) and math.isfinite(f_max)
            and math.isfinite(t_max) and w_max > 0 and f_max > 0 and t_max > 0):
        raise ValueError("score normalization bounds must be finite and positive")
    return w_max, f_max, t_max


def solve_lap(goods, rule, objective, *, score_normalization=None):
    """LAP 精确最优。objective ∈ {"score", "exp_t"}。

    ``score_normalization`` 为可选冻结口径 ``w_max/f_max/t_max_s``。不传时
    保留历史脚本的样本最大值口径；发布证据必须显式传入，避免与在线策略目标漂移。
    返回 (最优目标值, assignment[(good,pos)]);任一货物无可行位→(None, 违规货物数)。"""
    if objective not in {"score", "exp_t"}:
        raise ValueError(f"unsupported LAP objective: {objective}")
    slots = free_slots(rule)
    n, m = len(goods), len(slots)
    if n == 0:
        return 0.0, []
    # scipy 对 n>m 的矩形矩阵只返回 min(n,m) 个配对；若不先拦截，
    # 会把“只分配了部分货物”误报成完整可行解。
    if n > m:
        return None, n - m
    fn = None
    if objective == "score":
        w_max, f_max, _ = _score_normalizers(goods, score_normalization)
        fn = ws.make_score_fn(1.0, 0.6, 0.4, 0.15, w_max, f_max)
    C = np.full((n, m), BIG, dtype=float)
    for i, g in enumerate(goods):
        for j, (c, t) in enumerate(slots):
            if g.weight <= ws.tier_cap(t) and g.vol <= ws.CELL_VOL:   # 可行性=承重+容积
                if objective == "score":
                    C[i, j] = fn(g, c, t)
                else:                          # exp_t 口径:freq·travel_time(常数 Σf 略)
                    C[i, j] = g.freq * ws.travel_time(c, t)
    rows, cols = linear_sum_assignment(C)
    rows = np.asarray(rows, dtype=int)
    cols = np.asarray(cols, dtype=int)
    if len(rows) != len(cols) or len(rows) > n:
        raise RuntimeError("LAP solver returned an invalid complete assignment")
    if len(rows) != n:
        return None, n - len(rows)
    if (sorted(rows.tolist()) != list(range(n))
            or len(set(cols.tolist())) != n
            or np.any(cols < 0) or np.any(cols >= m)):
        raise RuntimeError("LAP solver returned an invalid complete assignment")
    if C[rows, cols].max() >= BIG:             # 有货物被迫走禁止边=该实例不可行
        bad = int((C[rows, cols] >= BIG).sum())
        return None, bad
    assign = [(goods[i], slots[j]) for i, j in zip(rows, cols)]
    return float(C[rows, cols].sum()), assign


def awra_objective(goods, rule, objective):
    """AWRA-LS 实测的同口径目标值(score 总分 或 频次加权行程总和)。"""
    w_max = max(g.weight for g in goods)
    f_max = max(g.freq for g in goods)
    fn = ws.make_score_fn(1.0, 0.6, 0.4, 0.15, w_max, f_max)
    wh, placed, failed = ws.run_awra_ls(goods, rule, fn, w_max, f_max)
    if failed:
        return None
    if objective == "score":
        return sum(fn(g, c, t) for g, (c, t) in placed)
    return sum(g.freq * ws.travel_time(c, t) for g, (c, t) in placed)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=30)
    ap.add_argument("--scenarios", default="all")
    ap.add_argument("--rule", default="sum", choices=["sum", "and", "or", "linear"])
    a = ap.parse_args()
    if a.seeds <= 0:
        ap.error("--seeds must be positive")
    seeds = [2026 + i for i in range(a.seeds)]
    names = list(ig.SCENARIOS) if a.scenarios == "all" else a.scenarios.split(",")

    rows = []
    print(f"{'场景':<15}{'口径':<7}{'AWRA-LS':>10}{'LAP最优':>10}{'Gap%(均值±CI95)':>18}")
    print("-" * 62)
    for name in names:
        for obj in ("score", "exp_t"):
            gaps = []
            for sd in seeds:
                goods = ig.gen_instance(name, sd)
                opt, _ = solve_lap(goods, a.rule, obj)
                heur = awra_objective(goods, a.rule, obj)
                if opt is None or heur is None or opt <= 0:
                    continue                   # 不可行实例如实跳过(记 rows 空缺)
                gap = (heur - opt) / opt * 100.0
                gaps.append(gap)
                rows.append(dict(scenario=name, objective=obj, seed=sd,
                                 awra=round(heur, 4), lap_opt=round(opt, 4),
                                 gap_pct=round(gap, 3)))
            if gaps:
                m, h = ig.ci95(gaps)
                hm = st.mean([r["awra"] for r in rows
                              if r["scenario"] == name and r["objective"] == obj])
                om = st.mean([r["lap_opt"] for r in rows
                              if r["scenario"] == name and r["objective"] == obj])
                print(f"{name:<15}{obj:<7}{hm:>10.2f}{om:>10.2f}"
                      f"{m:>10.2f} ± {h:<5.2f} (n={len(gaps)})")

    if not rows:
        raise RuntimeError("no comparable LAP rows; refusing to overwrite lap_gap.csv")
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "lap_gap.csv"), "w", newline="",
              encoding="utf-8-sig") as fp:
        w = csv.DictWriter(fp, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"\nCSV:{OUT}\\lap_gap.csv({len(rows)} 行)")


if __name__ == "__main__":
    main()
