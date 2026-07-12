# -*- coding: utf-8 -*-
"""
adaptive_weights.py — A1 场景权重可行性/稳定性表(T11，sim设计；不等于PLC闭环)
思想(资料包 contextual bandit 的轻量确定性版):最优权重依赖场景(F5 已证:
在线/批量要不同 δ)。离线在场景网格上标定最优权重 → 生成"场景→权重"策略表 →
输出场景可行性/候选稳定性策略表；仅当全部单元 FEASIBLE 时才允许显式
``--emit-st`` 生成 PLC 表(查表=确定性可解释,不上任何在线学习)。
场景维度:库存密度(120/200/240件≈63/83/93%,sum口径267可用位) × 货物分布(uniform/skew/heavy) × 模式(在线/批量)
权重网格:δ∈{0,0.05,0.10,0.15,0.20} × (β+γ)∈{0.6,1.0,1.4}(F5:β/γ 只有和起作用,β=γ=和/2)
选优:fail-first——仅在 fail=0 且 viol=0 的候选中按 exp_t/能耗选优；
     无零失败候选时显式 INFEASIBLE，禁止从失败幸存者里按 exp_t 伪选优。
产出:out/adaptive_weights.csv(全网格)+ out/weight_policy_table.csv(策略表)
     + out/adaptive_weights_by_seed.csv(逐 seed 选择稳定性)
     + 可选 --emit-st 生成 plc/08_GVL_WeightPolicy_generated.st；存在 INFEASIBLE 时拒绝生成
     + figs/fig12_自适应权重.png(固定默认 vs 场景自适应的增益)
运行:python adaptive_weights.py [--quick]   (全量约 10-20 分钟,建议后台)
"""
import argparse
from collections import Counter
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


def select_policy(rows):
    """fail-first 策略选优；无零失败候选时返回显式 INFEASIBLE。"""
    if not rows:
        raise ValueError("select_policy requires at least one candidate")
    clean = [r for r in rows if r["viol_sum"] == 0 and r["fail_sum"] == 0]
    nonviol = [r for r in rows if r["viol_sum"] == 0]
    min_fail = min(r["fail_sum"] for r in (nonviol or rows))
    if not clean:
        return dict(status="INFEASIBLE", best_delta=None, best_bg=None,
                    best_exp=None, best_ene=None, fail=None, min_fail=min_fail)
    best = min(clean, key=lambda r: (r["exp_mean"], r["ene_mean"]))
    return dict(status="FEASIBLE", best_delta=best["delta"], best_bg=best["bg"],
                best_exp=best["exp_mean"], best_ene=best["ene_mean"],
                fail=0, min_fail=0)


def winner_stability(seed_rows):
    """逐 seed winner 票数；不可行 seed 记 INFEASIBLE，不伪造 n=2 CI。"""
    by_seed = {}
    for sd in sorted({r["seed"] for r in seed_rows}):
        rows = [r for r in seed_rows if r["seed"] == sd]
        clean = [r for r in rows if r["viol"] == 0 and r["fail"] == 0]
        if not clean:
            by_seed[sd] = "INFEASIBLE"
            continue
        best = min(clean, key=lambda r: (r["exp"], r["ene"]))
        by_seed[sd] = f"d{best['delta']}:bg{best['bg']}"
    votes = Counter(by_seed.values())
    top = max(votes.values()) if votes else 0
    return dict(seed_count=len(by_seed),
                winner_votes=";".join(f"{k}={v}" for k, v in sorted(votes.items())),
                winner_rate=round(top / len(by_seed), 3) if by_seed else None,
                selection_stable=len(votes) == 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="小网格逻辑自检")
    ap.add_argument("--emit-st", action="store_true",
                    help="显式生成 plc/08；任一场景 INFEASIBLE 时 fail closed")
    a = ap.parse_args()
    densities, cases, deltas, bgs, seeds = DENSITIES, CASES, DELTAS, BGS, SEEDS
    if a.quick:
        densities, cases, deltas, bgs, seeds = [120], ["skew"], [0.10, 0.15], [1.0], [2026]

    t0 = time.time()
    rows, seed_rows = [], []
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
                seed_rows.append(dict(density=dens, case=case, mode=mode, seed=sd,
                                      delta=delta, bg=bg, exp=m["exp_t"],
                                      ene=m["energy"], fail=m["fail"], viol=m["viol"]))
            rows.append(dict(density=dens, case=case, mode=mode, delta=delta, bg=bg,
                             exp_mean=round(st.mean(accs["exp"]), 3),
                             ene_mean=round(st.mean(accs["ene"]), 1),
                             fail_sum=sum(accs["fail"]), viol_sum=sum(accs["viol"]),
                             seed_count=len(seeds)))
        print(f"  [{di}/{n_scn}] density={dens} case={case} mode={mode}"
              f"({time.time()-t0:.0f}s)")

    os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
    with open(os.path.join(HERE, "out", "adaptive_weights.csv"), "w", newline="",
              encoding="utf-8-sig") as fp:
        w = csv.DictWriter(fp, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    with open(os.path.join(HERE, "out", "adaptive_weights_by_seed.csv"), "w", newline="",
              encoding="utf-8-sig") as fp:
        w = csv.DictWriter(fp, fieldnames=list(seed_rows[0].keys()))
        w.writeheader()
        w.writerows(seed_rows)

    # ---- 策略表:fail=0+viol=0 前提下 exp 最小,tie=能耗 ----
    policy, gains = [], []
    for dens, case, mode in itertools.product(densities, cases, MODES):
        sel = [r for r in rows if (r["density"], r["case"], r["mode"]) == (dens, case, mode)]
        chosen = select_policy(sel)
        cur = next((r for r in sel if (r["delta"], r["bg"]) == DEFAULT), None)
        gain = ((1 - chosen["best_exp"] / cur["exp_mean"]) * 100
                if chosen["status"] == "FEASIBLE" and cur and cur["fail_sum"] == 0 else None)
        stable = winner_stability([
            r for r in seed_rows
            if (r["density"], r["case"], r["mode"]) == (dens, case, mode)
        ])
        policy.append(dict(density=dens, case=case, mode=mode,
                           status=chosen["status"],
                           best_delta=chosen["best_delta"], best_bg=chosen["best_bg"],
                           best_exp=chosen["best_exp"],
                           default_exp=cur["exp_mean"] if cur else None,
                           gain_pct=None if gain is None else round(gain, 2),
                           fail=chosen["fail"], min_fail=chosen["min_fail"],
                           candidate_count=len(sel), **stable))
        if gain is not None:
            gains.append(gain)
    with open(os.path.join(HERE, "out", "weight_policy_table.csv"), "w", newline="",
              encoding="utf-8-sig") as fp:
        w = csv.DictWriter(fp, fieldnames=list(policy[0].keys()))
        w.writeheader()
        w.writerows(policy)

    print(f"\n策略表(fail=0+viol=0 才选优;否则 INFEASIBLE):")
    print(f"{'密度':>5}{'分布':>9}{'模式':>8}{'状态':>12}{'最优δ':>7}{'最优β+γ':>8}{'exp_t':>8}{'增益':>8}")
    for p in policy:
        if p["status"] == "FEASIBLE":
            print(f"{p['density']:>5}{p['case']:>9}{p['mode']:>8}{p['status']:>12}"
                  f"{p['best_delta']:>7}{p['best_bg']:>8}{p['best_exp']:>8.3f}"
                  f"{p['gain_pct']:>7.1f}%")
        else:
            print(f"{p['density']:>5}{p['case']:>9}{p['mode']:>8}{p['status']:>12}"
                  f"{'-':>7}{'-':>8}{'-':>8}{'-':>8} min_fail={p['min_fail']}")
    print(f"\n可行场景自适应 vs 固定默认:平均增益 {st.mean(gains):.2f}%,"
          f"最大增益 {max(gains):.2f}%")

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
    if a.emit_st:
        bad = [p for p in policy if p["status"] != "FEASIBLE"]
        if bad:
            labels = ", ".join(f"{p['density']}/{p['case']}/{p['mode']}" for p in bad)
            raise RuntimeError(f"refuse ST generation: INFEASIBLE policy cells: {labels}")
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
            vals = [0.0 if p["gain_pct"] is None else p["gain_pct"] for p in sel]
            bars = ax.bar(range(len(sel)), vals,
                          color=["#c62828" if p["status"] == "INFEASIBLE" else
                                 "#2e7d32" if v > 0.5 else "#90a4ae"
                                 for p, v in zip(sel, vals)])
            for b, v, p in zip(bars, vals, sel):
                label = (f"INFEASIBLE\nminfail={p['min_fail']}" if p["status"] == "INFEASIBLE"
                         else f"{v:.1f}%\n稳={p['winner_rate']:.0%}")
                ax.text(b.get_x() + b.get_width() / 2, v, label, ha="center",
                        va="bottom", fontsize=7)
            ax.set_xticks(range(len(sel)))
            ax.set_xticklabels(labels, fontsize=8)
            ax.set_title(f"{title}:自适应 vs 固定默认", fontsize=11)
            ax.axhline(0, color="#666", lw=0.8)
            ax.spines[["top", "right"]].set_visible(False)
        axes[0].set_ylabel("期望取货时间增益 (%)")
        fig.suptitle("A1 场景自适应权重:fail-first 可行性与选择稳定性(2 seeds)", fontsize=12)
        fig.tight_layout()
        os.makedirs(os.path.join(HERE, "figs"), exist_ok=True)
        fig.savefig(os.path.join(HERE, "figs", "fig12_自适应权重.png"), dpi=300)
        print("已生成 figs/fig12_自适应权重.png")
    print(f"总耗时 {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
