"""U5 生命周期 δ 敏感性:配对显著性检验(补 F1——此前 canonical/报告写 p<0.001 无计算依据)。

读 out/lifecycle_delta.csv(与 _240 变体),对每个汰换率(turnover)把 δ=0.15 与 δ=0.0
按 seed 配对,做配对 t 检验(scipy.stats.ttest_rel)于 tot_time(总作业时)与 retr_mean
(出库均响应),输出真实 t / 双尾 p / 单尾 p / 95%CI(均值差)/ Cohen's dz,写 out/lifecycle_stats.csv。

可复现:python lifecycle_stats.py            # 主数据集
        python lifecycle_stats.py --240     # n_init=240 变体
数字口径与 lifecycle_sim.py 一致(匀速 legacy 物理 + 固定权重,δ 生命周期专项,非头条 H)。
"""
from __future__ import annotations

import csv
import math
import os
import sys

from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
METRICS = [("tot_time", "总作业时 s"), ("retr_mean", "出库均响应 s")]
# turnover 参数(每几次回库汰换1新货)→ 汰换率%(lifecycle_sim.py:71:10=10%/3≈33%/2=50%)
TURNOVER_PCT = {"10": "10", "3": "33", "2": "50"}


def _load(path):
    with open(path, encoding="utf-8-sig", newline="") as fp:
        return list(csv.DictReader(fp))


def _paired(rows, turnover, metric):
    """返回按 seed 对齐的 (δ0.15 值列表, δ0.0 值列表)。"""
    by = {}
    for r in rows:
        if r["turnover"] != turnover:
            continue
        by.setdefault(r["seed"], {})[r["delta"]] = float(r[metric])
    a, b = [], []
    for sd, d in sorted(by.items()):
        if "0.15" in d and "0.0" in d:
            a.append(d["0.15"])
            b.append(d["0.0"])
    return a, b


def analyse(path):
    rows = _load(path)
    turnovers = sorted({r["turnover"] for r in rows}, key=lambda x: float(x))
    out = []
    for tv in turnovers:
        for metric, mlbl in METRICS:
            a, b = _paired(rows, tv, metric)
            n = len(a)
            diffs = [x - y for x, y in zip(a, b)]
            mean_d = sum(diffs) / n
            sd_d = math.sqrt(sum((x - mean_d) ** 2 for x in diffs) / (n - 1)) if n > 1 else 0.0
            se = sd_d / math.sqrt(n) if n > 1 else 0.0
            t_stat, p_two = stats.ttest_rel(a, b)
            # 单尾(H1: δ0.15 > δ0.0)
            p_one = p_two / 2 if t_stat > 0 else 1 - p_two / 2
            tcrit = stats.t.ppf(0.975, n - 1) if n > 1 else 0.0
            ci_lo, ci_hi = mean_d - tcrit * se, mean_d + tcrit * se
            dz = mean_d / sd_d if sd_d else 0.0
            out.append(dict(
                turnover=tv, churn_pct=TURNOVER_PCT.get(tv, tv), metric=metric, label=mlbl, n=n,
                mean_d015=round(sum(a) / n, 3), mean_d0=round(sum(b) / n, 3),
                mean_diff=round(mean_d, 3),
                ci95_lo=round(ci_lo, 3), ci95_hi=round(ci_hi, 3),
                t=round(float(t_stat), 3), p_two=float(p_two), p_one=float(p_one),
                cohen_dz=round(dz, 3),
                sig="***" if p_two < 0.001 else "**" if p_two < 0.01 else "*" if p_two < 0.05 else "ns",
            ))
    return out


def _fmt_p(p):
    return "<1e-6" if p < 1e-6 else f"{p:.2e}" if p < 1e-3 else f"{p:.4f}"


def main():
    variant = "--240" in sys.argv
    src = os.path.join(HERE, "out", "lifecycle_delta_240.csv" if variant else "lifecycle_delta.csv")
    dst = os.path.join(HERE, "out", "lifecycle_stats_240.csv" if variant else "lifecycle_stats.csv")
    res = analyse(src)
    cols = ["turnover", "churn_pct", "metric", "label", "n", "mean_d015", "mean_d0", "mean_diff",
            "ci95_lo", "ci95_hi", "t", "p_two", "p_one", "cohen_dz", "sig"]
    with open(dst, "w", encoding="utf-8-sig", newline="") as fp:
        w = csv.DictWriter(fp, fieldnames=cols)
        w.writeheader()
        w.writerows(res)
    print(f"源 {os.path.basename(src)} -> {os.path.basename(dst)}")
    for r in res:
        print(f"  汰换{r['churn_pct']:>3}% · {r['label']:<9} n={r['n']:>2}  "
              f"δ0.15={r['mean_d015']:>10}  δ0={r['mean_d0']:>10}  "
              f"Δ={r['mean_diff']:>+9}  95%CI[{r['ci95_lo']:>+8},{r['ci95_hi']:>+8}]  "
              f"t={r['t']:>8}  p_two={_fmt_p(r['p_two']):>9}  {r['sig']:>3}  dz={r['cohen_dz']}")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    main()
