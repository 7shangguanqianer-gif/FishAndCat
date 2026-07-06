# -*- coding: utf-8 -*-
"""
headline.py — 报告主口径(H 口径)头条数字生成器:数字的唯一可再生来源
H 口径 = 梯形加减速(A4b,拍板②)+ 场景自适应权重(A1/T11,拍板①),
对照口径 = 匀速+固定默认(历史/文献可比口径)。两套并列,报告正文用 H,对照入附表。
场景:120件/skew/and,5 seeds(与 F4/experiments 同基)。
运行:python headline.py(~1 分钟)→ out/headline_numbers.csv + 控制台报告句
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
SEEDS = [2026, 7, 42, 123, 999]
STRATS = ["random", "seq", "near", "score", "awra"]


def run_five(goods, seed, adaptive):
    w_max = max(g.weight for g in goods)
    f_max = max(g.freq for g in goods)
    if adaptive:
        d_on, bg_on = ws.lookup_weights(len(goods), "skew", "online")
        d_ba, bg_ba = ws.lookup_weights(len(goods), "skew", "batch")
        fn_on = ws.make_score_fn(1.0, bg_on / 2, bg_on / 2, d_on, w_max, f_max)
        fn_ba = ws.make_score_fn(1.0, bg_ba / 2, bg_ba / 2, d_ba, w_max, f_max)
    else:
        fn_on = ws.make_score_fn(1.0, 0.6, 0.4, 0.15, w_max, f_max)
        fn_ba = fn_on
    out = {}
    for name, strat in [("random", ws.strat_random(random.Random(seed + 1))),
                        ("seq", ws.strat_seq), ("near", ws.strat_near),
                        ("score", ws.strat_score)]:
        wh, placed, failed = ws.run_online(strat, goods, "sum", fn_on)
        out[name] = ws.metrics(wh, placed, failed)
    wh, placed, failed = ws.run_awra_ls(goods, "sum", fn_ba, w_max, f_max)
    out["awra"] = ws.metrics(wh, placed, failed)
    return out


def caliber(accel, adaptive):
    ws.ACCEL = accel
    agg = {s: {"exp": [], "hot": [], "ene": [], "ht": [], "viol": 0} for s in STRATS}
    for sd in SEEDS:
        goods = ws.gen_goods(120, sd)
        res = run_five(goods, sd, adaptive)
        for s in STRATS:
            agg[s]["exp"].append(res[s]["exp_t"])
            agg[s]["hot"].append(res[s]["hot_t"])
            agg[s]["ene"].append(res[s]["energy"])
            agg[s]["ht"].append(res[s]["heavy_tier"])
            agg[s]["viol"] += res[s]["viol"]
    ws.ACCEL = False
    return agg


def main():
    print("H 口径(加减速+自适应)与对照口径(匀速+固定默认),120件/skew/and,5 seeds\n")
    H = caliber(accel=True, adaptive=True)
    L = caliber(accel=False, adaptive=False)

    rows = []
    print(f"{'策略':<8}{'H:exp_t均±σ':>16}{'H:能耗':>9}{'H:重货层':>8}"
          f"{'对照:exp_t':>11}{'违规Σ':>6}")
    for s in STRATS:
        he = st.mean(H[s]["exp"])
        hs = st.stdev(H[s]["exp"])
        le = st.mean(L[s]["exp"])
        print(f"{s:<8}{he:>11.2f}±{hs:<4.2f}{st.mean(H[s]['ene']):>9.0f}"
              f"{st.mean(H[s]['ht']):>8.2f}{le:>11.2f}"
              f"{H[s]['viol'] + L[s]['viol']:>6}")
        rows.append(dict(strategy=s,
                         H_exp_mean=round(he, 3), H_exp_std=round(hs, 3),
                         H_hot_mean=round(st.mean(H[s]["hot"]), 3),
                         H_energy_mean=round(st.mean(H[s]["ene"]), 1),
                         H_heavy_tier=round(st.mean(H[s]["ht"]), 3),
                         legacy_exp_mean=round(le, 3),
                         viol_sum=H[s]["viol"] + L[s]["viol"]))

    e = lambda s, k="exp": st.mean(H[s][k])
    drop = (1 - e("awra") / e("seq")) * 100
    ene_drop = (1 - e("awra", "ene") / e("seq", "ene")) * 100
    gap_sc = (1 - e("awra") / e("score")) * 100
    print(f"\n★H 口径报告句(数字来源=本脚本,勿手抄旧值):")
    print(f"  AWRA-LS 期望取货 {e('awra'):.2f}s,较题面顺序基线({e('seq'):.2f}s)"
          f"降 {drop:.1f}%;能耗降 {ene_drop:.1f}%;重货平均层高 {st.mean(H['awra']['ht']):.2f}")
    print(f"  批量 vs 在线 gap:{gap_sc:.1f}%;违规全口径合计 "
          f"{sum(r['viol_sum'] for r in rows)}(必须0)")
    print(f"  对照口径(匀速+固定,文献可比):awra {st.mean(L['awra']['exp']):.2f}s,"
          f"降 {(1 - st.mean(L['awra']['exp']) / st.mean(L['seq']['exp'])) * 100:.1f}%")

    os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
    path = os.path.join(HERE, "out", "headline_numbers.csv")
    with open(path, "w", newline="", encoding="utf-8-sig") as fp:
        w = csv.DictWriter(fp, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"\nCSV:{path}")


if __name__ == "__main__":
    main()
