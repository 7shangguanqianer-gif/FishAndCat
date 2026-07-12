# -*- coding: utf-8 -*-
"""
adaptive_weights.py — A1 场景自适应权重策略表(T11):把 AWRA 的 Adaptive 做实
思想(资料包 contextual bandit 的轻量确定性版):最优权重依赖场景(F5 已证:
在线/批量要不同 δ)。离线在场景网格上标定最优权重 → 生成"场景→权重"策略表 →
PLC 按当前场景查表切换(查表=确定性可解释,不上任何在线学习)。
场景维度:库存密度(120/200/240件≈63/83/93%,sum口径267可用位) × 货物分布(uniform/skew/heavy) × 模式(在线/批量)
权重网格:δ∈{0,0.05,0.10,0.15,0.20} × (β+γ)∈{0.6,1.0,1.4}(F5:β/γ 只有和起作用,β=γ=和/2)
选优:期望取货 exp_t 均值最小(2 seeds),tie-break 能耗;违规必须 0。
产出:out/adaptive_weights.csv(全网格)+ out/weight_policy_table.csv(策略表)
     + plc/08_GVL_WeightPolicy_generated.st(ST 查表,生成文件勿手改)
     + figs/fig12_自适应权重.png(固定默认 vs 场景自适应的增益)
运行:python adaptive_weights.py [--quick]   (全量约 10-20 分钟,建议后台)
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

HERE = os.path.dirname(os.path.abspath(__file__))
SEEDS = [2026, 7]
DENSITIES = [120, 200, 240]          # 占用率(含133预占,官方sum口径)≈ 63% / 83% / 93%
CASES = ["uniform", "skew", "heavy"]
MODES = ["online", "batch"]
DELTAS = [0.0, 0.05, 0.10, 0.15, 0.20]
BGS = [0.6, 1.0, 1.4]
DEFAULT = (0.15, 1.0)                # 当前默认(δ, β+γ)


def run_one(goods, mode, delta, bg, w_max, f_max):
    fn = ws.make_score_fn(1.0, bg / 2, bg / 2, delta, w_max, f_max)
    if mode == "online":
        wh, placed, failed = ws.run_online(ws.strat_score, goods, "sum", fn)
    else:
        wh, placed, failed = ws.run_awra_ls(goods, "sum", fn, w_max, f_max)
    m = ws.metrics(wh, placed, failed)
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="小网格逻辑自检")
    a = ap.parse_args()
    densities, cases, deltas, bgs, seeds = DENSITIES, CASES, DELTAS, BGS, SEEDS
    if a.quick:
        densities, cases, deltas, bgs, seeds = [120], ["skew"], [0.10, 0.15], [1.0], [2026]

    t0 = time.time()
    rows = []
    n_scn = len(densities) * len(cases) * len(MODES)
    print(f"场景 {n_scn} 个 × 权重组合 {len(deltas)*len(bgs)} × {len(seeds)} seeds,开始…")
    for di, (dens, case, mode) in enumerate(
            itertools.product(densities, cases, MODES), 1):
        goods_by_seed = {}
        for sd in seeds:
            g = ws.gen_goods(dens, sd, case)
            goods_by_seed[sd] = (g, max(x.weight for x in g), max(x.freq for x in g))
        for delta, bg in itertools.product(deltas, bgs):
            accs = {"exp": [], "ene": [], "fail": [], "viol": []}
            for sd in seeds:
                g, w_max, f_max = goods_by_seed[sd]
                m = run_one(g, mode, delta, bg, w_max, f_max)
                accs["exp"].append(m["exp_t"])
                accs["ene"].append(m["energy"])
                accs["fail"].append(m["fail"])
                accs["viol"].append(m["viol"])
            rows.append(dict(density=dens, case=case, mode=mode, delta=delta, bg=bg,
                             exp_mean=round(st.mean(accs["exp"]), 3),
                             ene_mean=round(st.mean(accs["ene"]), 1),
                             fail_sum=sum(accs["fail"]), viol_sum=sum(accs["viol"])))
        print(f"  [{di}/{n_scn}] density={dens} case={case} mode={mode}"
              f"({time.time()-t0:.0f}s)")

    os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
    with open(os.path.join(HERE, "out", "adaptive_weights.csv"), "w", newline="",
              encoding="utf-8-sig") as fp:
        w = csv.DictWriter(fp, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # ---- 策略表:每场景最优(违规0前提,exp 最小,tie=能耗) ----
    policy, gains = [], []
    for dens, case, mode in itertools.product(densities, cases, MODES):
        sel = [r for r in rows if (r["density"], r["case"], r["mode"]) == (dens, case, mode)
               and r["viol_sum"] == 0]
        best = min(sel, key=lambda r: (r["exp_mean"], r["ene_mean"]))
        cur = next((r for r in sel if (r["delta"], r["bg"]) == DEFAULT), None)
        gain = (1 - best["exp_mean"] / cur["exp_mean"]) * 100 if cur else 0.0
        policy.append(dict(density=dens, case=case, mode=mode,
                           best_delta=best["delta"], best_bg=best["bg"],
                           best_exp=best["exp_mean"],
                           default_exp=cur["exp_mean"] if cur else None,
                           gain_pct=round(gain, 2),
                           fail=best["fail_sum"]))
        gains.append(gain)
    with open(os.path.join(HERE, "out", "weight_policy_table.csv"), "w", newline="",
              encoding="utf-8-sig") as fp:
        w = csv.DictWriter(fp, fieldnames=list(policy[0].keys()))
        w.writeheader()
        w.writerows(policy)

    print(f"\n策略表(场景→最优权重;增益=对固定默认 δ0.15/β+γ1.0):")
    print(f"{'密度':>5}{'分布':>9}{'模式':>8}{'最优δ':>7}{'最优β+γ':>8}{'exp_t':>8}{'增益':>8}")
    for p in policy:
        print(f"{p['density']:>5}{p['case']:>9}{p['mode']:>8}{p['best_delta']:>7}"
              f"{p['best_bg']:>8}{p['best_exp']:>8.3f}{p['gain_pct']:>7.1f}%")
    print(f"\n自适应查表 vs 固定默认:平均增益 {st.mean(gains):.2f}%,"
          f"最大增益 {max(gains):.2f}%(场景:"
          f"{max(policy, key=lambda p: p['gain_pct'])['density']}/"
          f"{max(policy, key=lambda p: p['gain_pct'])['case']}/"
          f"{max(policy, key=lambda p: p['gain_pct'])['mode']})")

    # ---- ST 查表生成(密度3档×分布3档×模式2档 → δ, β+γ) ----
    if a.quick:
        print(f"quick 自检通过,总耗时 {time.time()-t0:.0f}s(ST/图生成仅全量模式)")
        return
    dens_idx = {d: i for i, d in enumerate(densities)}
    case_idx = {c: i for i, c in enumerate(cases)}
    L = ["(* ============================================================",
         "   08_GVL_WeightPolicy_generated.st — 生成文件,勿手改!",
         "   由 sim/adaptive_weights.py 生成:场景→权重 策略表(A1 自适应机制)",
         "   场景判档(PLC 在线可算):iDensity 0/1/2=占用率<55%/<85%/其余;",
         "   iDist 0/1/2=均匀/高频偏态/重货(按库存重量均值与频次变异系数判,见 FC_ClassifyScene);",
         "   xBatch FALSE=在线逐件 TRUE=批量重排。",
         "   ============================================================ *)",
         "VAR_GLOBAL CONSTANT",
         "    // aPolicyDelta/aPolicyBG[iDensity, iDist, xBatch(0/1)]",
         "    aPolicyDelta : ARRAY[0..2, 0..2, 0..1] OF REAL := ["]
    dvals, bvals = {}, {}
    for p in policy:
        key = (dens_idx[p["density"]], case_idx[p["case"]], 0 if p["mode"] == "online" else 1)
        dvals[key] = p["best_delta"]
        bvals[key] = p["best_bg"]
    flat_d = [str(dvals[(i, j, k)]) for i in range(3) for j in range(3) for k in range(2)]
    flat_b = [str(bvals[(i, j, k)]) for i in range(3) for j in range(3) for k in range(2)]
    L.append("        " + ", ".join(flat_d) + "];")
    L.append("    aPolicyBG : ARRAY[0..2, 0..2, 0..1] OF REAL := [")
    L.append("        " + ", ".join(flat_b) + "];")
    L.append("END_VAR")
    L.append("")
    L.append("(* 用法(PRG_Main 分配启动前调用):")
    L.append("   GVL_Param.rDelta := aPolicyDelta[iDensity, iDist, SEL(xBatch, 0, 1)];")
    L.append("   bg := aPolicyBG[iDensity, iDist, SEL(xBatch, 0, 1)];")
    L.append("   GVL_Param.rBeta := bg / 2.0;  GVL_Param.rGamma := bg / 2.0;  *)")
    if not a.quick:
        with open(os.path.join(HERE, "..", "plc",
                               "08_GVL_WeightPolicy_generated.st"), "w",
                  encoding="utf-8") as fp:
            fp.write("\n".join(L) + "\n")
        print("已生成 plc/08_GVL_WeightPolicy_generated.st")

    # ---- fig12 ----
    if not a.quick:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
        plt.rcParams["axes.unicode_minus"] = False
        fig, axes = plt.subplots(1, 2, figsize=(12, 4.2), sharey=True)
        for ax, mode, title in zip(axes, MODES, ["在线(逐件决策)", "批量(AWRA-LS)"]):
            sel = [p for p in policy if p["mode"] == mode]
            labels = [f"{p['density']}件\n{p['case']}" for p in sel]
            vals = [p["gain_pct"] for p in sel]
            bars = ax.bar(range(len(sel)), vals,
                          color=["#2e7d32" if v > 0.5 else "#90a4ae" for v in vals])
            for b, v in zip(bars, vals):
                ax.text(b.get_x() + b.get_width() / 2, v, f"{v:.1f}%", ha="center",
                        va="bottom", fontsize=8)
            ax.set_xticks(range(len(sel)))
            ax.set_xticklabels(labels, fontsize=8)
            ax.set_title(f"{title}:自适应 vs 固定默认", fontsize=11)
            ax.axhline(0, color="#666", lw=0.8)
            ax.spines[["top", "right"]].set_visible(False)
        axes[0].set_ylabel("期望取货时间增益 (%)")
        fig.suptitle("A1 场景自适应权重:9 场景×2 模式的查表增益(2 seeds)", fontsize=12)
        fig.tight_layout()
        os.makedirs(os.path.join(HERE, "figs"), exist_ok=True)
        fig.savefig(os.path.join(HERE, "figs", "fig12_自适应权重.png"), dpi=300)
        print("已生成 figs/fig12_自适应权重.png")
    print(f"总耗时 {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
