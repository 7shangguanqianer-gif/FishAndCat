# -*- coding: utf-8 -*-
"""
sensitivity.py — T15 参数敏感性分析(回应 canonical D5"参数怎么定的/换一组还成立吗")
问题:评委最常见的质疑是"你的权重/物理参数是拍脑袋的吧?换一组结论还在吗?"
回答方式:围绕对照口径默认权重(1.0/0.6/0.4/0.15)与 H 口径运动参数做单因素扰动,
展示三件事:①δ 有"悬崖"(=0 退化成就近贪心,F2 的参数化重现),0.10-0.30 是平台;
②β+γ 只有"和"起作用(F5 冗余性的敏感性视角),扫和值结论不动;
③运动参数 ax/ay 整体缩放只平移绝对数,不改变"awra 优于 near"的相对结论与降幅量级。
口径:H 运动模型(ACCEL=True);权重扰动围绕对照口径固定权重做(自适应查表是派生物,
     扰动其源头权重才是真敏感性);3 seeds 均值;违规必须全程为 0。
运行:python sensitivity.py(~2-3 分钟,独立脚本,不进 run_all 回归门)
输出:out/sensitivity.csv + figs/fig14_参数敏感性.png + 控制台结论
"""
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import warehouse_sim as ws

HERE = os.path.dirname(os.path.abspath(__file__))
SEEDS = [2026, 2027, 2028]
N_GOODS = 120
RULE = "sum"                            # B1 官方口径 sum(133 预占格,同 headline)
BASE_W = (1.0, 0.6, 0.4, 0.15)          # 对照口径固定权重(canonical E)

DELTA_SCAN = [0.0, 0.05, 0.10, 0.15, 0.20, 0.30]
BG_SUM_SCAN = [0.4, 0.6, 1.0, 1.4, 2.0]  # β+γ 和值扫描(F5:仅和有效,对半拆)
ACC_SCALE = [0.5, 0.75, 1.0, 1.5, 2.0]   # ax/ay 同乘缩放


def eval_point(alpha, beta, gamma, delta, seeds=SEEDS):
    """一组权重下 near/score/awra 的 exp_t 三 seed 均值与违规和。"""
    acc = {"near": [], "score": [], "awra": []}
    viol = 0
    for seed in seeds:
        goods = ws.gen_goods(N_GOODS, seed)
        w_max = max(g.weight for g in goods)
        f_max = max(g.freq for g in goods)
        fn = ws.make_score_fn(alpha, beta, gamma, delta, w_max, f_max)
        for name in ("near", "score"):
            strat = {"near": ws.strat_near, "score": ws.strat_score}[name]
            wh, placed, failed = ws.run_online(strat, goods, RULE, fn)
            m = ws.metrics(wh, placed, failed)
            acc[name].append(m["exp_t"])
            viol += m["viol"]
        wh, placed, failed = ws.run_awra_ls(goods, RULE, fn, w_max, f_max)
        m = ws.metrics(wh, placed, failed)
        acc["awra"].append(m["exp_t"])
        viol += m["viol"]
    mean = {k: sum(v) / len(v) for k, v in acc.items()}
    return mean, viol


def main():
    ws.ACCEL = True                                   # H 口径运动模型
    a0, b0, g0, d0 = BASE_W
    rows, viol_total = [], 0
    ax0, ay0 = ws.AX, ws.AY

    print("=" * 64)
    print(f"T15 参数敏感性(H 运动模型,{len(SEEDS)} seeds 均值,基准权重 {BASE_W})")
    print("=" * 64)

    # ---- ① δ 扫描(α/β/γ 固定) ----
    print("\n[1/3] δ 位置价值预留项扫描(δ=0 应重现 F2 的就近贪心退化)")
    d_curve = []
    for d in DELTA_SCAN:
        mean, v = eval_point(a0, b0, g0, d)
        viol_total += v
        d_curve.append(mean)
        rows.append(dict(factor="delta", value=d, **{f"expt_{k}": round(x, 4)
                                                     for k, x in mean.items()}, viol=v))
        gap = (mean["near"] - mean["score"]) / mean["near"] * 100
        print(f"  δ={d:<5} near {mean['near']:.3f}  score {mean['score']:.3f}"
              f"(较near {gap:+.1f}%)  awra {mean['awra']:.3f}")

    # ---- ② β+γ 和值扫描(对半拆,δ 固定) ----
    print("\n[2/3] β+γ 和值扫描(F5 冗余性:只有和起作用,曲线应平缓)")
    bg_curve = []
    for s in BG_SUM_SCAN:
        mean, v = eval_point(a0, s / 2, s / 2, d0)
        viol_total += v
        bg_curve.append(mean)
        rows.append(dict(factor="beta_gamma_sum", value=s,
                         **{f"expt_{k}": round(x, 4) for k, x in mean.items()}, viol=v))
        print(f"  β+γ={s:<4} near {mean['near']:.3f}  score {mean['score']:.3f}"
              f"  awra {mean['awra']:.3f}")

    # ---- ③ 运动参数缩放(权重固定=基准) ----
    print("\n[3/3] 加减速 ax/ay 同乘缩放(绝对数平移,相对结论应稳定)")
    acc_curve = []
    for sc in ACC_SCALE:
        ws.AX, ws.AY = ax0 * sc, ay0 * sc
        mean, v = eval_point(a0, b0, g0, d0)
        viol_total += v
        acc_curve.append(mean)
        drop = (mean["near"] - mean["awra"]) / mean["near"] * 100
        rows.append(dict(factor="acc_scale", value=sc,
                         **{f"expt_{k}": round(x, 4) for k, x in mean.items()}, viol=v))
        print(f"  ×{sc:<5} near {mean['near']:.3f}  awra {mean['awra']:.3f}"
              f"(降 {drop:.1f}%)")
    ws.AX, ws.AY = ax0, ay0                            # 还原,防污染后续 import 者

    # ---- 结论句(报告 D5 小节直接引用) ----
    d0_row = d_curve[DELTA_SCAN.index(0.0)]
    plateau = [m["score"] for m, d in zip(d_curve, DELTA_SCAN) if 0.10 <= d <= 0.30]
    bg_spread = (max(m["awra"] for m in bg_curve) - min(m["awra"] for m in bg_curve))
    drops = [(m["near"] - m["awra"]) / m["near"] * 100 for m in acc_curve]
    print("\n" + "=" * 64)
    print("结论(违规全程合计 %d,必须为 0):" % viol_total)
    print(f"  ① δ=0 时 score 与 near 差 {abs(d0_row['score']-d0_row['near']):.3f}s"
          f"(退化重现 F2);δ∈[0.10,0.30] 平台内 score 极差 "
          f"{max(plateau)-min(plateau):.3f}s → 取 0.15 不是脆弱甜点;")
    print(f"  ② β+γ 和值 0.4→2.0(5倍),awra exp_t 极差仅 {bg_spread:.3f}s → F5 冗余性稳健;")
    print(f"  ③ 加减速 0.5×→2×,awra 较 near 降幅稳定在 {min(drops):.1f}%~{max(drops):.1f}%"
          f" → 结论不依赖具体物理参数取值。")

    # ---- CSV ----
    os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
    path = os.path.join(HERE, "out", "sensitivity.csv")
    with open(path, "w", newline="", encoding="utf-8-sig") as fp:
        w = csv.DictWriter(fp, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # ---- fig14(三联图) ----
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, axes = plt.subplots(1, 3, figsize=(12.5, 3.8))
    style = {"near": ("#8d6e63", "s", "近位贪心"), "score": ("#1565c0", "o", "在线评分"),
             "awra": ("#2e7d32", "^", "AWRA-LS")}
    panels = [(DELTA_SCAN, d_curve, "δ 位置价值预留项", "δ"),
              (BG_SUM_SCAN, bg_curve, "β+γ 和值(对半拆)", "β+γ"),
              (ACC_SCALE, acc_curve, "加减速缩放(×基准)", "缩放倍数")]
    for ax, (xs, curve, title, xlabel) in zip(axes, panels):
        for k, (color, mk, lbl) in style.items():
            ax.plot(xs, [m[k] for m in curve], marker=mk, ms=4, lw=1.4,
                    color=color, label=lbl)
        ax.set_title(title, fontsize=11)
        ax.set_xlabel(xlabel, fontsize=9)
        ax.set_ylabel("期望取货时间 s(C3)", fontsize=9)
        ax.grid(alpha=0.25, lw=0.5)
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].axvspan(0.10, 0.30, color="#2e7d32", alpha=0.08)
    axes[0].legend(fontsize=8, frameon=False)
    fig.suptitle("T15 参数敏感性:δ 有悬崖有平台 / β+γ 只认和 / 物理参数缩放不改结论"
                 "(H 口径,3 seeds)", fontsize=11)
    fig.tight_layout()
    os.makedirs(os.path.join(HERE, "figs"), exist_ok=True)
    fig.savefig(os.path.join(HERE, "figs", "fig14_参数敏感性.png"), dpi=300)
    print(f"\n输出:{path} + figs/fig14_参数敏感性.png")


if __name__ == "__main__":
    main()
