# -*- coding: utf-8 -*-
"""
calibrate.py — 评分权重多 seed 精标(W-003)
网格:δ∈{0.05..0.30} × β∈{0.4,0.6,0.8} × γ∈{0.2,0.4,0.6},α=1.0 固定 → 54 组合
每组合 5 seeds × 120件 × and 规则,跑 score(在线)与 awra(批量);near 每 seed 缓存作基线。
选优准则(执行单 W-003):
  ①硬门槛:score 的 exp_t 均值 ≤ near 的 exp_t 均值;
  ②主排序:hot_t(score) 均值最小;
  ③约束:energy(score) 均值不劣于 near 5% 以上。
输出:sim/out/calibration.csv(全网格)+ 控制台推荐组合。
纪律:只推荐,不改 warehouse_sim.py 默认值——权重是口径,变更须用户批准后走 canonical 流程。
用法:python calibrate.py [--quick](quick=2组合×2seeds 逻辑自检)
"""
import argparse
import csv
import itertools
import os
import statistics as st
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import warehouse_sim as ws

SEEDS = [2026, 7, 42, 123, 999]
DELTAS = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30]
BETAS = [0.4, 0.6, 0.8]
GAMMAS = [0.2, 0.4, 0.6]
N_GOODS, RULE = 120, "sum"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")


def run_pair(goods, fn, w_max, f_max):
    """跑 score(在线)与 awra(批量),返回两组 metrics。"""
    wh, placed, failed = ws.run_online(ws.strat_score, goods, RULE, fn)
    m_score = ws.metrics(wh, placed, failed)
    wh, placed, failed = ws.run_awra_ls(goods, RULE, fn, w_max, f_max)
    m_awra = ws.metrics(wh, placed, failed)
    return m_score, m_awra


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="小样本逻辑自检(2组合x2seeds)")
    a = ap.parse_args()

    deltas, betas, gammas, seeds = DELTAS, BETAS, GAMMAS, SEEDS
    if a.quick:
        deltas, betas, gammas, seeds = [0.15], [0.6], [0.4, 0.6], SEEDS[:2]

    # near 基线与权重无关:每 seed 缓存一次
    goods_cache, near_cache = {}, {}
    for sd in seeds:
        goods = ws.gen_goods(N_GOODS, sd)
        goods_cache[sd] = (goods, max(g.weight for g in goods), max(g.freq for g in goods))
        fn0 = ws.make_score_fn(1.0, 0.6, 0.4, 0.15, goods_cache[sd][1], goods_cache[sd][2])
        wh, placed, failed = ws.run_online(ws.strat_near, goods, RULE, fn0)
        near_cache[sd] = ws.metrics(wh, placed, failed)
    near_exp = st.mean(near_cache[sd]["exp_t"] for sd in seeds)
    near_hot = st.mean(near_cache[sd]["hot_t"] for sd in seeds)
    near_ene = st.mean(near_cache[sd]["energy"] for sd in seeds)
    print(f"near 基线(均值,{len(seeds)} seeds):exp_t={near_exp:.3f} hot_t={near_hot:.3f} "
          f"energy={near_ene:.0f}\n")

    combos = list(itertools.product(deltas, betas, gammas))
    print(f"网格 {len(combos)} 组合 × {len(seeds)} seeds,开始…")
    t0 = time.time()
    rows = []
    for i, (d, b, g) in enumerate(combos, 1):
        acc = {k: [] for k in ("s_exp", "s_hot", "s_ene", "s_cog",
                               "a_exp", "a_hot", "a_ene", "a_cog", "viol")}
        for sd in seeds:
            goods, w_max, f_max = goods_cache[sd]
            fn = ws.make_score_fn(1.0, b, g, d, w_max, f_max)
            ms, ma = run_pair(goods, fn, w_max, f_max)
            acc["s_exp"].append(ms["exp_t"]);  acc["s_hot"].append(ms["hot_t"])
            acc["s_ene"].append(ms["energy"]); acc["s_cog"].append(ms["cog"])
            acc["a_exp"].append(ma["exp_t"]);  acc["a_hot"].append(ma["hot_t"])
            acc["a_ene"].append(ma["energy"]); acc["a_cog"].append(ma["cog"])
            acc["viol"].append(ms["viol"] + ma["viol"])
        row = dict(delta=d, beta=b, gamma=g,
                   score_exp_mean=round(st.mean(acc["s_exp"]), 3),
                   score_exp_std=round(st.stdev(acc["s_exp"]), 3) if len(seeds) > 1 else 0,
                   score_hot_mean=round(st.mean(acc["s_hot"]), 3),
                   score_ene_mean=round(st.mean(acc["s_ene"]), 1),
                   score_cog_mean=round(st.mean(acc["s_cog"]), 3),
                   awra_exp_mean=round(st.mean(acc["a_exp"]), 3),
                   awra_hot_mean=round(st.mean(acc["a_hot"]), 3),
                   awra_ene_mean=round(st.mean(acc["a_ene"]), 1),
                   viol_sum=sum(acc["viol"]))
        rows.append(row)
        if i % 9 == 0 or i == len(combos):
            print(f"  [{i}/{len(combos)}] δ={d} β={b} γ={g} "
                  f"score_exp={row['score_exp_mean']} hot={row['score_hot_mean']} "
                  f"({time.time()-t0:.0f}s)")

    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "calibration.csv")
    with open(path, "w", newline="", encoding="utf-8-sig") as fp:
        w = csv.DictWriter(fp, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # ---- 选优 ----
    ok = [r for r in rows if r["viol_sum"] == 0
          and r["score_exp_mean"] <= near_exp + 1e-9
          and r["score_ene_mean"] <= near_ene * 1.05]
    print(f"\n通过硬门槛(exp≤near 且 energy≤near*1.05 且违规0):{len(ok)}/{len(rows)} 组合")
    if ok:
        best = min(ok, key=lambda r: (r["score_hot_mean"], r["score_exp_mean"]))
        cur = next((r for r in rows if (r["delta"], r["beta"], r["gamma"]) == (0.15, 0.6, 0.4)), None)
        print(f"\n★推荐组合:δ={best['delta']} β={best['beta']} γ={best['gamma']}")
        print(f"  score:exp={best['score_exp_mean']}(near {near_exp:.3f}) "
              f"hot={best['score_hot_mean']}(near {near_hot:.3f}) "
              f"ene={best['score_ene_mean']:.0f}(near {near_ene:.0f})")
        print(f"  awra :exp={best['awra_exp_mean']} hot={best['awra_hot_mean']} "
              f"ene={best['awra_ene_mean']:.0f}")
        if cur:
            print(f"  当前默认(δ0.15/β0.6/γ0.4):score exp={cur['score_exp_mean']} "
                  f"hot={cur['score_hot_mean']} ene={cur['score_ene_mean']:.0f}")
            better = (best["score_hot_mean"] < cur["score_hot_mean"] - 0.05)
            print(f"  结论:{'推荐值明显更优,建议走 canonical 流程换默认' if better else '当前默认已在最优邻域,无须变更'}")
    print(f"\nCSV:{path}(耗时 {time.time()-t0:.0f}s)")


if __name__ == "__main__":
    main()
