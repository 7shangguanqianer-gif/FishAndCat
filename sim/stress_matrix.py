# -*- coding: utf-8 -*-
"""
stress_matrix.py — A3 鲁棒性压力矩阵(T12):三类扰动下各策略的退化对比
呼应题面"设备损耗"要素:别人把损耗当指标,我们把它当扰动源来验证鲁棒性。
扰动(3 seeds 均值,基线=120件 skew/and 布局):
  S1 需求漂移:布局完成后频次洗牌(热货变冷/冷货变热),布局不动重算 exp_t
     → 退化幅度;再给一列"夜间重排恢复后"(复用 reslot_cycle 成本感知重排)。
  S2 重货潮:货物重量分布极端化 w∈U[50,80](承重约束高压),重新布局
     → 失败件数 + 重货平均层高(谁把重货稳进底层)。
  S3 设备退化:布局完成后随机 3 层承重系数再乘 0.8(老化/降级),
     → 既有布局的"超载须搬修"货物数 + 修复搬运行车成本(三段计时)。
结论预期(让数据说话,如实报告):AWRA 系退化最平缓/失败最少。
运行:python stress_matrix.py    输出:out/stress_matrix.csv + figs/fig13_鲁棒压力.png
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
from reslot_cycle import reslot_pass

HERE = os.path.dirname(os.path.abspath(__file__))
SEEDS = [2026, 7, 42]
STRATS = ["seq", "near", "score", "awra"]
LBL = {"seq": "顺序基线", "near": "就近贪心", "score": "多目标评分", "awra": "AWRA-LS"}


def build(strat, goods, fn, w_max, f_max):
    if strat == "awra":
        wh, placed, failed = ws.run_awra_ls(goods, "sum", fn, w_max, f_max)
    else:
        s = {"seq": ws.strat_seq, "near": ws.strat_near, "score": ws.strat_score}[strat]
        wh, placed, failed = ws.run_online(s, goods, "sum", fn)
    return wh, placed, failed


def exp_t_of(placed):
    fs = sum(g.freq for g, _ in placed) or 1.0
    return sum(g.freq * ws.travel_time(c, t) for g, (c, t) in placed) / fs


def main():
    rows = {s: dict(base=[], drift=[], drift_rec=[], heavy_fail=[], heavy_tier=[],
                    degrade_viol=[], degrade_cost=[]) for s in STRATS}

    for sd in SEEDS:
        goods = ws.gen_goods(120, sd)
        w_max = max(g.weight for g in goods)
        f_max = max(g.freq for g in goods)
        fn = ws.make_score_fn(1.0, 0.6, 0.4, 0.15, w_max, f_max)

        # ---- S1 需求漂移(布局不动,频次洗牌;各策略同一洗牌事件) ----
        new_freqs = [g.freq for g in goods]
        random.Random(sd + 99).shuffle(new_freqs)
        for s in STRATS:
            g2 = ws.gen_goods(120, sd)                    # 干净副本
            wm = max(x.weight for x in g2)
            fm = max(x.freq for x in g2)
            fn2 = ws.make_score_fn(1.0, 0.6, 0.4, 0.15, wm, fm)
            wh, placed, failed = build(s, g2, fn2, wm, fm)
            assert not failed
            rows[s]["base"].append(exp_t_of(placed))
            for idx, g in enumerate(g2):                   # 漂移
                g.freq = new_freqs[idx]
            rows[s]["drift"].append(exp_t_of(placed))
            # 夜间重排恢复(成本感知,day_len=100 口径同 F11)
            pos_of = {g.gid: p for g, p in placed}
            by_gid = {g.gid: g for g in g2}
            reslot_pass(wh, pos_of, by_gid, day_len=100)
            placed2 = [(by_gid[gid], p) for gid, p in pos_of.items()]
            rows[s]["drift_rec"].append(exp_t_of(placed2))

        # ---- S2 重货潮(重量极端化,重新布局) ----
        heavy = ws.gen_goods(120, sd)
        rngh = random.Random(sd + 5)
        for g in heavy:
            g.weight = round(rngh.uniform(50.0, 80.0), 1)
        wmh = max(x.weight for x in heavy)
        fmh = max(x.freq for x in heavy)
        fnh = ws.make_score_fn(1.0, 0.6, 0.4, 0.15, wmh, fmh)
        for s in STRATS:
            wh, placed, failed = build(s, [ws.Good(g.gid, g.name, g.weight, g.freq, g.vol)
                                           for g in heavy], fnh, wmh, fmh)
            rows[s]["heavy_fail"].append(len(failed))
            hv = sorted(placed, key=lambda pg: -pg[0].weight)[:max(1, len(placed) // 5)]
            rows[s]["heavy_tier"].append(sum(t for _, (_, t) in hv) / len(hv))

        # ---- S3 设备退化(布局后 3 层承重×0.8,检修复负担;各策略同一退化事件) ----
        bad_tiers = random.Random(sd + 77).sample(range(0, 11), 3)   # 低层退化才有杀伤力
        for s in STRATS:
            g3 = ws.gen_goods(120, sd)
            wm = max(x.weight for x in g3)
            fm = max(x.freq for x in g3)
            fn3 = ws.make_score_fn(1.0, 0.6, 0.4, 0.15, wm, fm)
            wh, placed, failed = build(s, g3, fn3, wm, fm)
            viol, cost = 0, 0.0
            for g, (c, t) in placed:
                if t in bad_tiers and g.weight > ws.tier_cap(t) * 0.8:
                    viol += 1
                    # 修复=搬到最近可行安全位(三段行车;简化:搬到同列最近的未退化可行层)
                    best = None
                    for tt in range(ws.TIERS):
                        if tt not in bad_tiers and wh.grid[c][tt] is None \
                           and g.weight <= ws.tier_cap(tt):
                            best = (c, tt)
                            break
                    if best is None:
                        best = (c, t)                       # 无位可搬,成本按原地两段计
                    cost += (ws.travel_time(c, t)
                             + ws.travel_time_between(c, t, best[0], best[1])
                             + ws.travel_time(*best))
            rows[s]["degrade_viol"].append(viol)
            rows[s]["degrade_cost"].append(cost)

    # ---- 汇总 ----
    print(f"{'策略':<10}{'基线exp_t':>9}{'漂移后':>8}{'退化%':>7}{'重排恢复':>9}"
          f"{'重货潮失败':>10}{'重货均层':>9}{'退化层超载':>10}{'修复成本s':>10}")
    summary = []
    for s in STRATS:
        r = rows[s]
        base = st.mean(r["base"])
        drift = st.mean(r["drift"])
        rec = st.mean(r["drift_rec"])
        deg = (drift / base - 1) * 100
        hf = st.mean(r["heavy_fail"])
        ht = st.mean(r["heavy_tier"])
        dv = st.mean(r["degrade_viol"])
        dc = st.mean(r["degrade_cost"])
        summary.append(dict(strategy=s, base_exp=round(base, 3),
                            drift_exp=round(drift, 3), drift_pct=round(deg, 1),
                            drift_recovered=round(rec, 3),
                            heavy_fail=round(hf, 2), heavy_tier=round(ht, 2),
                            degrade_viol=round(dv, 2), degrade_cost=round(dc, 1)))
        print(f"{LBL[s]:<10}{base:>9.2f}{drift:>8.2f}{deg:>6.1f}%{rec:>9.2f}"
              f"{hf:>10.2f}{ht:>9.2f}{dv:>10.2f}{dc:>10.1f}")

    os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
    with open(os.path.join(HERE, "out", "stress_matrix.csv"), "w", newline="",
              encoding="utf-8-sig") as fp:
        w = csv.DictWriter(fp, fieldnames=list(summary[0].keys()))
        w.writeheader()
        w.writerows(summary)

    # ---- fig13 三面板 ----
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
    plt.rcParams["axes.unicode_minus"] = False
    C = ["#8d6e63", "#1976d2", "#f9a825", "#2e7d32"]
    names = [LBL[s] for s in STRATS]
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.0))
    specs = [("drift_pct", "S1 需求漂移退化%(重排可恢复,见表)", "%"),
             ("heavy_tier", "S2 重货潮:重货平均层高(低=稳)", "层"),
             ("degrade_viol", "S3 低层承重退化:超载需搬修件数", "件")]
    for ax, (k, title, unit) in zip(axes, specs):
        vals = [next(r for r in summary if r["strategy"] == s)[k] for s in STRATS]
        bars = ax.bar(range(4), vals, color=C)
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, v, f"{v:.1f}", ha="center",
                    va="bottom", fontsize=9)
        ax.set_xticks(range(4))
        ax.set_xticklabels(names, fontsize=8)
        ax.set_title(title, fontsize=10)
        ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle("A3 鲁棒性压力矩阵:三类扰动下的退化对比(越低越稳;3 seeds)", fontsize=12)
    fig.tight_layout()
    os.makedirs(os.path.join(HERE, "figs"), exist_ok=True)
    fig.savefig(os.path.join(HERE, "figs", "fig13_鲁棒压力.png"), dpi=300)
    print(f"\n输出:out/stress_matrix.csv + figs/fig13_鲁棒压力.png")


if __name__ == "__main__":
    main()
