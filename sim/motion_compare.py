# -*- coding: utf-8 -*-
"""
motion_compare.py — L1 运动模型对比实验:匀速 vs 梯形速度曲线(加减速)
产出:out/motion_compare.csv + figs/fig7_运动模型对比.png(左:t(d)曲线;右:策略指标对比)
要点:匀速模型系统性低估短程行程时间(加减速主导),即"近位不免费"——
     这改变时间地形,是模型准确性章的实质升级(题面:贴近实际工程应用)。
运行:python motion_compare.py(~10s,seed=2026,120件,and)
"""
import csv
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import warehouse_sim as ws

HERE = os.path.dirname(os.path.abspath(__file__))
SEED, N, RULE = 2026, 120, "and"
STRATS = ["random", "seq", "near", "score", "awra"]
LBL = {"random": "随机", "seq": "顺序基线", "near": "就近贪心",
       "score": "多目标评分(在线)", "awra": "AWRA-LS(批量)"}


def run_all(goods):
    w_max = max(g.weight for g in goods)
    f_max = max(g.freq for g in goods)
    fn = ws.make_score_fn(1.0, 0.6, 0.4, 0.15, w_max, f_max)
    out = {}
    for name, strat in [("random", ws.strat_random(random.Random(SEED + 1))),
                        ("seq", ws.strat_seq), ("near", ws.strat_near),
                        ("score", ws.strat_score)]:
        wh, placed, failed = ws.run_online(strat, goods, RULE, fn)
        out[name] = ws.metrics(wh, placed, failed)
    wh, placed, failed = ws.run_awra_ls(goods, RULE, fn, w_max, f_max)
    out["awra"] = ws.metrics(wh, placed, failed)
    return out


def main():
    goods = ws.gen_goods(N, SEED)
    res = {}
    for accel in (False, True):
        ws.ACCEL = accel
        res[accel] = run_all(goods)         # 同一批货物,两种口径各自重新决策+评估
    ws.ACCEL = False                        # 恢复默认口径

    # ---- CSV ----
    os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
    path = os.path.join(HERE, "out", "motion_compare.csv")
    with open(path, "w", newline="", encoding="utf-8-sig") as fp:
        w = csv.writer(fp)
        w.writerow(["strategy", "motion", "exp_t", "hot_t", "tot_time2", "energy", "viol"])
        for accel in (False, True):
            for s in STRATS:
                m = res[accel][s]
                w.writerow([s, "trapezoid" if accel else "uniform",
                            round(m["exp_t"], 3), round(m["hot_t"], 3),
                            round(m["tot_time2"], 1), round(m["energy"], 0), m["viol"]])

    # ---- 控制台结论 ----
    print(f"{'策略':<10}{'匀速exp_t':>10}{'加减速exp_t':>12}{'低估幅度':>9}")
    for s in STRATS:
        u = res[False][s]["exp_t"]
        t = res[True][s]["exp_t"]
        print(f"{s:<10}{u:>10.2f}{t:>12.2f}{(t/u-1)*100:>8.1f}%")
    ua = res[False]["awra"]
    ta = res[True]["awra"]
    us = res[False]["seq"]
    ts = res[True]["seq"]
    print(f"\n加减速口径下 awra 对 seq 降幅:{(1-ta['exp_t']/ts['exp_t'])*100:.1f}%"
          f"(匀速口径 {(1-ua['exp_t']/us['exp_t'])*100:.1f}%)——相对优势在两口径下均成立")
    print(f"违规:全部 {sum(res[a][s]['viol'] for a in res for s in STRATS)}")

    # ---- fig7 ----
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, (axL, axR) = plt.subplots(1, 2, figsize=(12.5, 4.3),
                                   gridspec_kw={"width_ratios": [1, 1.3]})
    # 左:单轴 t(d) 曲线(水平轴与垂直轴)
    ds = [i * 0.25 for i in range(0, 81)]
    axL.plot(ds, [d / ws.VX for d in ds], "--", color="#1976d2", lw=1.2,
             label=f"水平·匀速 d/{ws.VX}")
    axL.plot(ds, [ws.axis_time(d, ws.VX, ws.AX) for d in ds], "-", color="#1976d2",
             lw=1.8, label=f"水平·梯形(a={ws.AX})")
    axL.plot(ds, [d / ws.VY for d in ds], "--", color="#e65100", lw=1.2,
             label=f"垂直·匀速 d/{ws.VY}")
    axL.plot(ds, [ws.axis_time(d, ws.VY, ws.AY) for d in ds], "-", color="#e65100",
             lw=1.8, label=f"垂直·梯形(a={ws.AY})")
    axL.set_xlabel("单轴行程距离 d (m)")
    axL.set_ylabel("行程时间 (s)")
    axL.set_title("单轴时间模型:匀速系统性低估短程")
    axL.legend(fontsize=8)
    axL.spines[["top", "right"]].set_visible(False)
    # 右:五策略 exp_t 双口径对比
    x = range(len(STRATS))
    w_ = 0.36
    axR.bar([i - w_ / 2 for i in x], [res[False][s]["exp_t"] for s in STRATS], w_,
            color="#90a4ae", label="匀速口径")
    axR.bar([i + w_ / 2 for i in x], [res[True][s]["exp_t"] for s in STRATS], w_,
            color="#2e7d32", label="梯形加减速口径")
    for i, s in enumerate(STRATS):
        axR.text(i - w_ / 2, res[False][s]["exp_t"], f"{res[False][s]['exp_t']:.1f}",
                 ha="center", va="bottom", fontsize=8)
        axR.text(i + w_ / 2, res[True][s]["exp_t"], f"{res[True][s]['exp_t']:.1f}",
                 ha="center", va="bottom", fontsize=8)
    axR.set_xticks(list(x))
    axR.set_xticklabels([LBL[s] for s in STRATS], fontsize=8)
    axR.set_ylabel("期望取货时间 (s)")
    axR.set_title("五策略在两种运动口径下(各自重新决策)")
    axR.legend(fontsize=9)
    axR.spines[["top", "right"]].set_visible(False)
    fig.suptitle("L1 运动模型升级:匀速 vs 梯形速度曲线(seed=2026,120件,and)", fontsize=12)
    fig.tight_layout()
    os.makedirs(os.path.join(HERE, "figs"), exist_ok=True)
    fig.savefig(os.path.join(HERE, "figs", "fig7_运动模型对比.png"), dpi=300)
    print(f"输出:{path} + figs/fig7_运动模型对比.png")


if __name__ == "__main__":
    main()
