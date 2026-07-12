# -*- coding: utf-8 -*-
"""
plots.py — 验证报告图表生成(matplotlib)
运行:python plots.py     → 输出 sim/figs/fig1..fig5.png(300dpi,报告直插)
依赖:matplotlib(pip install matplotlib -i https://mirrors.aliyun.com/pypi/simple/)
数据:fig1-4 现算(seed=2026 主场景,与 F4/回归测试同口径);
     fig5 读 out/experiments_agg.csv(先跑 experiments.py)。
"""
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import random as _r

import warehouse_sim as ws

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False
FIGS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "figs")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
C = {"random": "#9e9e9e", "seq": "#8d6e63", "near": "#1976d2",
     "score": "#f9a825", "awra": "#2e7d32"}
LBL = {"random": "随机", "seq": "顺序基线", "near": "就近贪心",
       "score": "多目标评分(在线)", "awra": "AWRA-LS(批量)"}
STRATS = ["random", "seq", "near", "score", "awra"]


def compute(seed=2026, n=120, rule="sum", delta=0.15):
    goods = ws.gen_goods(n, seed)
    w_max = max(g.weight for g in goods)
    f_max = max(g.freq for g in goods)
    fn = ws.make_score_fn(1.0, 0.6, 0.4, delta, w_max, f_max)
    res, whs = {}, {}
    for name, strat in [("random", ws.strat_random(_r.Random(seed + 1))),
                        ("seq", ws.strat_seq), ("near", ws.strat_near),
                        ("score", ws.strat_score)]:
        wh, placed, failed = ws.run_online(strat, goods, rule, fn)
        res[name] = ws.metrics(wh, placed, failed)
        whs[name] = wh
    wh, placed, failed = ws.run_awra_ls(goods, rule, fn, w_max, f_max)
    res["awra"] = ws.metrics(wh, placed, failed)
    whs["awra"] = wh
    return goods, res, whs


def fig1(res):
    """四指标分组条形:一图看懂递进故事。"""
    specs = [("exp_t", "期望取货时间 (s)"), ("hot_t", "热货均时 (s)"),
             ("energy", "能耗代理 (kg·m)"), ("cog", "载荷重心高度 (m)")]
    fig, axes = plt.subplots(1, 4, figsize=(14, 3.6))
    for ax, (k, title) in zip(axes, specs):
        vals = [res[s][k] for s in STRATS]
        bars = ax.bar(range(5), vals, color=[C[s] for s in STRATS])
        ax.set_title(title, fontsize=11)
        ax.set_xticks(range(5))
        ax.set_xticklabels(["随机", "顺序", "就近", "评分", "AWRA"], fontsize=9)
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, v, f"{v:,.1f}" if v < 100 else f"{v:,.0f}",
                    ha="center", va="bottom", fontsize=8)
        ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle("五策略对比(seed=2026,120件,and 规则;违规均为 0)", fontsize=12)
    fig.tight_layout()
    fig.savefig(os.path.join(FIGS, "fig1_策略对比.png"), dpi=300)
    plt.close(fig)


def fig2(goods, whs):
    """占用热力图三联:直观看到"热货聚左下、重货沉底"。
    配色:空=白,预占=中灰(独立通道,不占用色带),货物=YlOrRd 按频次热度。"""
    import numpy as np
    from matplotlib.patches import Patch
    by_freq = sorted(goods, key=lambda g: -g.freq)
    rank = {g.gid: i for i, g in enumerate(by_freq)}
    n = len(goods)
    fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.6))
    for ax, name in zip(axes, ["near", "score", "awra"]):
        wh = whs[name]
        heat = np.full((20, 20), np.nan)            # [tier][col] 货物热度
        pre = np.zeros((20, 20), dtype=bool)
        for c in range(20):
            for t in range(20):
                cell = wh.grid[c][t]
                if cell == "PRE":
                    pre[t][c] = True
                elif cell is not None:
                    heat[t][c] = 1.0 - rank[cell.gid] / max(1, n - 1)
        # 底层:预占用灰块(独立绘制,不进色带)
        grey = np.where(pre, 0.55, np.nan)
        ax.imshow(grey, origin="lower", cmap="Greys", vmin=0, vmax=1,
                  aspect="equal", interpolation="nearest")
        im = ax.imshow(heat, origin="lower", cmap="YlOrRd", vmin=0, vmax=1,
                       aspect="equal", interpolation="nearest")
        ax.set_title(LBL[name], fontsize=11)
        ax.set_xlabel("列(I/O 口在左下)", fontsize=10)
        if name == "near":
            ax.set_ylabel("层(0=底层)", fontsize=10)
        ax.plot(0, 0, marker="*", color="#1976d2", markersize=11, markeredgecolor="white")
        ax.tick_params(labelsize=9)
    fig.suptitle("仓位占用热力图(seed=2026,120件;颜色深=访问频次高)", fontsize=12)
    cbar = fig.colorbar(im, ax=axes, shrink=0.8)
    cbar.set_label("货物频次热度(1=最热)", fontsize=10)
    axes[0].legend(handles=[Patch(fc="#8c8c8c", label="预占用格"),
                            Patch(fc="white", ec="#999999", label="空仓位"),
                            Patch(fc="#e6550d", label="货物(色深=热)")],
                   loc="upper left", fontsize=9, framealpha=0.9)
    fig.savefig(os.path.join(FIGS, "fig2_占用热力图.png"), dpi=300, bbox_inches="tight")
    plt.close(fig)


def fig3():
    """δ 扫描:位置价值预留项的标定依据(F2)。"""
    deltas = [0.0, 0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5]
    exp_ts, hot_ts, near_exp, near_hot = [], [], None, None
    for d in deltas:
        _, res, _ = compute(delta=d)
        exp_ts.append(res["score"]["exp_t"])
        hot_ts.append(res["score"]["hot_t"])
        near_exp = res["near"]["exp_t"]
        near_hot = res["near"]["hot_t"]
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(deltas, exp_ts, "o-", color=C["score"], label="score 期望取货 (s)")
    ax.plot(deltas, hot_ts, "s-", color="#e65100", label="score 热货均时 (s)")
    ax.axhline(near_exp, ls="--", color=C["near"], lw=1, label=f"near 期望取货 {near_exp:.2f}s")
    ax.axhline(near_hot, ls=":", color=C["near"], lw=1, label=f"near 热货均时 {near_hot:.2f}s")
    ax.axvspan(0.1, 0.15, color="#c8e6c9", alpha=0.5, label="甜点区 0.10~0.15")
    ax.set_xlabel("δ(位置价值预留权重)")
    ax.set_ylabel("时间 (s)")
    ax.set_title("δ 标定:δ=0 退化为就近贪心,过大则过度预留(seed=2026)")
    ax.legend(fontsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(os.path.join(FIGS, "fig3_delta标定.png"), dpi=300)
    plt.close(fig)


def fig4(res):
    """时间-能耗散点:多目标权衡定位图。"""
    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    for s in STRATS:
        ax.scatter(res[s]["exp_t"], res[s]["energy"], s=140, color=C[s],
                   edgecolor="white", zorder=3, label=LBL[s])
        ax.annotate(LBL[s], (res[s]["exp_t"], res[s]["energy"]),
                    textcoords="offset points", xytext=(8, 4), fontsize=9)
    ax.set_xlabel("期望取货时间 (s) →越小越好")
    ax.set_ylabel("能耗代理 (kg·m) →越小越好")
    ax.set_title("效率-能耗双目标定位(左下角为优)")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(os.path.join(FIGS, "fig4_时间能耗定位.png"), dpi=300)
    plt.close(fig)


def fig5():
    """多 seed 鲁棒性(读 experiments_agg.csv):三分布 × 策略,均值±σ。"""
    path = os.path.join(OUT, "experiments_agg.csv")
    if not os.path.exists(path):
        print("fig5 跳过:先跑 python experiments.py")
        return
    rows = list(csv.DictReader(open(path, encoding="utf-8-sig")))
    cases = ["uniform", "skew", "heavy"]
    case_lbl = {"uniform": "A 均匀", "skew": "B 高频偏态", "heavy": "C 重货偏多"}
    fig, ax = plt.subplots(figsize=(9, 4.2))
    width = 0.15
    for si, s in enumerate(STRATS):
        xs, ys, es = [], [], []
        for ci, case in enumerate(cases):
            r = next((r for r in rows if r["scene"] == "main"
                      and r["case"] == case and r["strat"] == s), None)
            if r:
                xs.append(ci + (si - 2) * width)
                ys.append(float(r["exp_t_mean"]))
                es.append(float(r["exp_t_std"]))
        ax.bar(xs, ys, width=width, yerr=es, capsize=3, color=C[s], label=LBL[s])
    ax.set_xticks(range(3))
    ax.set_xticklabels([case_lbl[c] for c in cases])
    ax.set_ylabel("期望取货时间 (s),均值±σ(5 seeds)")
    ax.set_title("三类货物分布下的鲁棒性(120件,and 规则)")
    ax.legend(fontsize=8, ncol=5, loc="upper center", bbox_to_anchor=(0.5, -0.12))
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(os.path.join(FIGS, "fig5_分布鲁棒性.png"), dpi=300, bbox_inches="tight")
    plt.close(fig)


def main():
    os.makedirs(FIGS, exist_ok=True)
    goods, res, whs = compute()
    fig1(res)
    fig2(goods, whs)
    fig3()
    fig4(res)
    fig5()
    print(f"图已输出:{FIGS}")
    for f in sorted(os.listdir(FIGS)):
        print("  ", f)


if __name__ == "__main__":
    main()
