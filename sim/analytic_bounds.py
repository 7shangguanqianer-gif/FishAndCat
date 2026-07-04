# -*- coding: utf-8 -*-
"""
analytic_bounds.py — L3 理论对比:解析期望 + 松弛下界,构成"理论-仿真-实现"证据链
三个理论量(均匀速口径;加减速口径可 --accel 重算离散量,连续式仅匀速有闭式):
  ① 随机存储期望(离散精确):E[t] = Σ_{可行空位} t(c,r) / N —— 与 random 策略多 seed
     仿真均值对照,验证仿真器正确性(理论=仿真);
  ② Bozer-White 连续货架近似(AS/RS 经典文献 1984):形状因子 b=t_x/t_y,
     单命令单程 E=T·(1/2+b²/6),两点间 E[TB]=T·(1/3+b²/6−b³/30) —— 展示离散/连续一致;
  ③ 频次感知松弛下界(重排不等式):热货配近位的完美指派
     LB = Σ f↓(i)·t↑(i) / Σf(忽略承重约束,故为任何可行方案的下界)——
     度量 AWRA-LS 距"理论最好"还有多远(实现≈理论)。
运行:python analytic_bounds.py
输出:out/analytic_bounds.csv + figs/fig9_理论对比.png(阶梯图)
"""
import csv
import os
import random
import statistics as st
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import warehouse_sim as ws

HERE = os.path.dirname(os.path.abspath(__file__))
SEED, N, RULE = 2026, 120, "and"
SEEDS = [2026, 7, 42, 123, 999]


def free_slots(rule):
    return [(c, t) for c in range(ws.COLS) for t in range(ws.TIERS)
            if not ws.preoccupied(c, t, rule)]


def main():
    slots = free_slots(RULE)
    times = sorted(ws.travel_time(*s) for s in slots)

    # ① 离散精确:随机存储期望单程(频次与位置独立 → 频次加权期望=位置均值)
    e_random_exact = sum(times) / len(times)

    # ② Bozer-White 连续近似(匀速口径闭式)
    t_x = (ws.COLS - 1) * ws.CELL_W / ws.VX
    t_y = (ws.TIERS - 1) * ws.CELL_H / ws.VY
    T = max(t_x, t_y)
    b = min(t_x, t_y) / T
    e_bw_sc = T * (0.5 + b * b / 6.0)
    e_bw_tb = T * (1.0 / 3.0 + b * b / 6.0 - b ** 3 / 30.0)
    # 离散两点间期望(全对精确求和,双命令理论参照)
    n = len(slots)
    tot = 0.0
    for i in range(n):
        ci, ti_ = slots[i]
        for j in range(n):
            if i != j:
                tot += ws.travel_time_between(ci, ti_, slots[j][0], slots[j][1])
    e_tb_exact = tot / (n * (n - 1))

    # random 策略多 seed 仿真均值(与①对照)
    sims = []
    for sd in SEEDS:
        goods = ws.gen_goods(N, sd)
        w_max = max(g.weight for g in goods)
        f_max = max(g.freq for g in goods)
        fn = ws.make_score_fn(1.0, 0.6, 0.4, 0.15, w_max, f_max)
        wh, placed, failed = ws.run_online(ws.strat_random(random.Random(sd + 1)),
                                           goods, RULE, fn)
        sims.append(ws.metrics(wh, placed, failed)["exp_t"])
    e_random_sim = st.mean(sims)
    sd_random_sim = st.stdev(sims)

    # ③ 频次感知松弛下界(seed=2026 那批货;忽略承重约束 → 任何可行方案 ≥ LB)
    goods = ws.gen_goods(N, SEED)
    f_desc = sorted((g.freq for g in goods), reverse=True)
    lb = sum(f * t for f, t in zip(f_desc, times[:N])) / sum(f_desc)

    # 各策略实测(seed=2026,与 F4 同口径)
    w_max = max(g.weight for g in goods)
    f_max = max(g.freq for g in goods)
    fn = ws.make_score_fn(1.0, 0.6, 0.4, 0.15, w_max, f_max)
    pts = {}
    for name, strat in [("random", ws.strat_random(random.Random(SEED + 1))),
                        ("seq", ws.strat_seq), ("near", ws.strat_near),
                        ("score", ws.strat_score)]:
        wh, placed, failed = ws.run_online(strat, goods, RULE, fn)
        pts[name] = ws.metrics(wh, placed, failed)["exp_t"]
    wh, placed, failed = ws.run_awra_ls(goods, RULE, fn, w_max, f_max)
    pts["awra"] = ws.metrics(wh, placed, failed)["exp_t"]

    print("① 随机存储期望单程(验证仿真器):")
    print(f"   离散精确 {e_random_exact:.3f}s | random 策略 5-seed 仿真 "
          f"{e_random_sim:.3f}±{sd_random_sim:.3f}s | 偏差 "
          f"{abs(e_random_sim-e_random_exact)/e_random_exact*100:.1f}%")
    print("② Bozer-White 连续近似 vs 离散精确:")
    print(f"   单命令单程:BW {e_bw_sc:.3f}s vs 离散 {e_random_exact:.3f}s"
          f"(差 {abs(e_bw_sc-e_random_exact)/e_random_exact*100:.1f}%,b={b:.2f})")
    print(f"   两点间 TB :BW {e_bw_tb:.3f}s vs 离散 {e_tb_exact:.3f}s"
          f"(差 {abs(e_bw_tb-e_tb_exact)/e_tb_exact*100:.1f}%)")
    print("③ 频次感知松弛下界与各策略(seed=2026):")
    print(f"   LB={lb:.3f}s ≤ ", end="")
    print(" ≤ ".join(f"{k} {pts[k]:.2f}" for k in
                     ["awra", "score", "near", "seq", "random"]))
    print(f"   ★AWRA-LS 距松弛下界 {(pts['awra']/lb-1)*100:.1f}%"
          f"(下界忽略承重约束,真实可达最优在两者之间)")

    # ---- CSV ----
    os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
    path = os.path.join(HERE, "out", "analytic_bounds.csv")
    with open(path, "w", newline="", encoding="utf-8-sig") as fp:
        w = csv.writer(fp)
        w.writerow(["quantity", "value_s", "kind"])
        w.writerow(["random_exact_discrete", round(e_random_exact, 4), "theory"])
        w.writerow(["random_sim_5seeds_mean", round(e_random_sim, 4), "simulation"])
        w.writerow(["bozer_white_sc_oneway", round(e_bw_sc, 4), "theory_continuous"])
        w.writerow(["travel_between_exact", round(e_tb_exact, 4), "theory"])
        w.writerow(["bozer_white_tb", round(e_bw_tb, 4), "theory_continuous"])
        w.writerow(["freq_aware_lower_bound", round(lb, 4), "theory_bound"])
        for k, v in pts.items():
            w.writerow([f"strategy_{k}", round(v, 4), "simulation_seed2026"])

    # ---- fig9 阶梯图 ----
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
    plt.rcParams["axes.unicode_minus"] = False
    items = [("松弛下界(重排不等式)", lb, "#7b1fa2"),
             ("AWRA-LS(实现)", pts["awra"], "#2e7d32"),
             ("score 在线(实现)", pts["score"], "#f9a825"),
             ("near(实现)", pts["near"], "#1976d2"),
             ("随机·仿真均值", e_random_sim, "#9e9e9e"),
             ("随机·离散精确(理论)", e_random_exact, "#616161"),
             ("随机·Bozer-White 连续(理论)", e_bw_sc, "#455a64")]
    fig, ax = plt.subplots(figsize=(8.2, 4.4))
    ys = range(len(items))
    ax.barh(list(ys), [v for _, v, _ in items], color=[c for _, _, c in items], height=0.62)
    for y, (name, v, _) in zip(ys, items):
        ax.text(v + 0.15, y, f"{v:.2f}s", va="center", fontsize=9)
    ax.set_yticks(list(ys))
    ax.set_yticklabels([n for n, _, _ in items], fontsize=9)
    ax.invert_yaxis()
    ax.set_xlabel("期望取货时间 (s)")
    ax.set_title("理论-仿真-实现 三级证据链(匀速口径,seed=2026/120件/and)")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    os.makedirs(os.path.join(HERE, "figs"), exist_ok=True)
    fig.savefig(os.path.join(HERE, "figs", "fig9_理论对比.png"), dpi=300)
    print(f"输出:{path} + figs/fig9_理论对比.png")


if __name__ == "__main__":
    main()
