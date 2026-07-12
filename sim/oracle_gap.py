# -*- coding: utf-8 -*-
"""
oracle_gap.py — A1 oracle gap 量化实验(0711 总库 A1;9 天技术窗第一格)

问题:场景检测器(strategy_lib.select_strategy,三档 objective)离"后验最优"有多远?
方法(Algorithm Selection 标准框架,Rice 1976;VBS/SBS 术语沿 SAT 社区/ASlib 惯例):
  VBS(oracle)  per-instance 后验最优:每 (场景,seed) 实例上 7 策略里词典序最优
                (fail 最小 → exp_t 最小;illegal_mix 场景 fail 恒=非法件数,词典序天然兼容)。
                另算 unrestricted oracle(纯 exp_t 最小,忽略 fail)做参考下界。
  SBS           单一固定策略中**词典序**最优者:excess_fail 总数最小组内平均 gap 最小。
                (v1 教训:纯 gap 均值会把 tob 选成 SBS——它在 dense fail 9.7 件/实例,
                 exp_t 只含已放件,产生 −3% 的"漏件假优势";fail 是题面一票否决项。)
  选择器        检测器三档(holistic/lexicographic/speed,batch_known=True)+ 7 固定策略。
  gap%          仅在 excess_fail=0 的可比域计算
                (exp_t_sel − exp_t_VBS) / exp_t_VBS × 100；失败更多时写 N/A。
  attainment%   仅在 excess_fail=0 的可比域计算 exp_t_VBS / exp_t_sel × 100。
  closed gap%   (gap_SBS − gap_sel) / gap_SBS × 100(选择器吃掉了 VBS-SBS 差距的多少)。
  excess_fail   fail − fail_VBS(超出 oracle 的失败件;illegal_mix 全策略同 6 件→excess 0)。
多目标护栏:oracle gap 只量 exp_t 单目标;holistic 档的 gap 是**有意支付的安全溢价**
(买 heavy_tier 低层/能耗低),故聚合同时报 heavy_tier/energy,判读给"溢价↔安全"完整账。

数据源:out/instgen_detail.csv(instance_gen.py 产物,13 场景 × 30 seeds × 7 策略,0706)
       ——本脚本纯后处理,不重跑仿真;检测器画像由 gen_instance 重新生成货物计算(确定性)。
输出:out/oracle_gap_detail.csv 逐实例 / out/oracle_gap.csv 场景聚合
     out/oracle_gap_profiles.csv 逐实例批次画像(A2 ST 化位级比对用)
     out/oracle_gap_summary.txt 中文判读(双预案自动落笔)/ figs/fig13_oracle_gap.png
运行:python oracle_gap.py(秒级)
文献(0711 sonnet 查证枪核实,B5 报告周引用):VBS/SBS 定义=Bischl et al. 2016, ASlib,
  Artificial Intelligence 237:41-58;closed gap=(SBS−sel)/(SBS−VBS)=Lindauer, van Rijn &
  Kotthoff 2019, AIJ 272:86-100(OASC 官方指标);框架奠基=Rice 1976, Advances in
  Computers 15:65-118。gap 空间中 VBS 的 gap=0,故本脚本 (gap_SBS−gap_sel)/gap_SBS 等价。
"""
import csv
import os
import statistics as st
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import instance_gen as ig
import strategy_lib as sl

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
DETAIL = os.path.join(OUT, "instgen_detail.csv")

OBJECTIVES = ["holistic", "lexicographic", "speed"]   # 检测器三档(F18-3:目标口径是输入)
FIXED = ["random", "seq", "near", "score", "awra", "cb", "tob"]


def load_detail():
    """detail.csv → {(scenario, seed): {strat: row}};行内数值字段转 float/int。"""
    inst = defaultdict(dict)
    with open(DETAIL, encoding="utf-8-sig") as fp:
        for r in csv.DictReader(fp):
            key = (r["scenario"], int(r["seed"]))
            inst[key][r["strat"]] = dict(exp_t=float(r["exp_t"]), fail=int(r["fail"]),
                                         viol=int(r["viol"]), heavy=float(r["heavy_tier"]),
                                         ene=float(r["energy"]))
    return inst


def comparable_gap(exp_t, oracle_exp, excess_fail):
    """只在失败数不劣于词典序 oracle 时比较时间。

    excess_fail>0 的候选虽然可能更快，但漏件使 exp_t 分母失真；此时返回 N/A，
    防止产生 >100% attainment 的伪超越。
    """
    if excess_fail > 0:
        return None, None
    gap = (exp_t - oracle_exp) / oracle_exp * 100.0
    attain = oracle_exp / exp_t * 100.0 if exp_t > 0 else None
    return gap, attain


def _ci_or_none(values):
    if not values:
        return None, None
    return ig.ci95(values)


def _mean_or_none(values):
    return st.mean(values) if values else None


def _fmt(value, spec):
    return "N/A" if value is None else format(value, spec)


def main():
    inst = load_detail()
    scenarios = sorted({k[0] for k in inst}, key=lambda s: list(ig.SCENARIOS).index(s))
    seeds = sorted({k[1] for k in inst})
    n_inst = len(inst)
    print(f"实例 {n_inst} 个({len(scenarios)} 场景 × {len(seeds)} seeds),"
          f"策略 {len(FIXED)},检测器档位 {OBJECTIVES}")

    # ---- 检测器推荐(逐实例:重生成货物 → 画像 → 三档推荐;确定性,与仿真同 seed 同源) ----
    det_pick = {}                                     # (scn, sd, obj) -> strat
    profiles = {}                                     # (scn, sd) -> profile(落盘核查用)
    for scn in scenarios:
        for sd in seeds:
            goods = ig.gen_instance(scn, sd)
            p = sl.batch_profile(goods)
            profiles[(scn, sd)] = p
            for obj in OBJECTIVES:
                det_pick[(scn, sd, obj)] = sl.select_strategy(p, True, obj)

    # ---- 逐实例:VBS(词典序)/unrestricted oracle/各选择器 gap ----
    selectors = [f"det_{o}" for o in OBJECTIVES] + FIXED
    rows_detail, agg_acc = [], defaultdict(lambda: defaultdict(list))
    raw_lt_lex = 0                                    # unrestricted < 词典序 oracle 的实例数
    for (scn, sd), by_strat in sorted(inst.items(),
                                      key=lambda kv: (scenarios.index(kv[0][0]), kv[0][1])):
        vbs_strat = min(FIXED, key=lambda s: (by_strat[s]["fail"], by_strat[s]["exp_t"]))
        vbs = by_strat[vbs_strat]["exp_t"]
        vbs_fail = by_strat[vbs_strat]["fail"]
        raw = min(by_strat[s]["exp_t"] for s in FIXED)
        raw_lt_lex += (raw < vbs - 1e-12)
        for sel in selectors:
            strat = det_pick[(scn, sd, sel[4:])] if sel.startswith("det_") else sel
            r = by_strat[strat]
            exf = r["fail"] - vbs_fail                 # 超出 oracle 的失败件(一票否决项)
            gap, attain = comparable_gap(r["exp_t"], vbs, exf)
            rows_detail.append(dict(scenario=scn, seed=sd, selector=sel, strat=strat,
                                    exp_t=round(r["exp_t"], 4), fail=r["fail"],
                                    excess_fail=exf,
                                    oracle_strat=vbs_strat, oracle_exp=round(vbs, 4),
                                    gap_pct="" if gap is None else round(gap, 3),
                                    attain_pct="" if attain is None else round(attain, 2)))
            a = agg_acc[(scn, sel)]
            if gap is not None:
                a["gap"].append(gap)
            if attain is not None:
                a["attain"].append(attain)
            a["exf"].append(exf); a["strat"].append(strat)
            a["heavy"].append(r["heavy"]); a["ene"].append(r["ene"])
            a["total"].append(1)

    # ---- 场景聚合 + 全局行 ----
    rows_agg = []
    glob = defaultdict(lambda: defaultdict(list))
    for (scn, sel), a in agg_acc.items():
        gm, gh = _ci_or_none(a["gap"])
        am, _ = _ci_or_none(a["attain"])
        picks = sorted(set(a["strat"]))
        rows_agg.append(dict(scenario=scn, selector=sel,
                             gap_mean="" if gm is None else round(gm, 3),
                             gap_ci95="" if gh is None else round(gh, 3),
                             attain_mean="" if am is None else round(am, 2),
                             exf_mean=round(st.mean(a["exf"]), 2),
                             heavy_mean=round(st.mean(a["heavy"]), 3),
                             ene_mean=round(st.mean(a["ene"]), 1),
                             comparable_n=len(a["gap"]), total_n=len(a["total"]),
                             picked=" ".join(picks)))
        g = glob[sel]
        for k in ("gap", "attain", "exf", "heavy", "ene", "total"):
            g[k] += a[k]
    for sel in selectors:
        g = glob[sel]
        gm, gh = _ci_or_none(g["gap"])
        am, _ = _ci_or_none(g["attain"])
        rows_agg.append(dict(scenario="ALL", selector=sel,
                             gap_mean="" if gm is None else round(gm, 3),
                             gap_ci95="" if gh is None else round(gh, 3),
                             attain_mean="" if am is None else round(am, 2),
                             exf_mean=round(st.mean(g["exf"]), 2),
                             heavy_mean=round(st.mean(g["heavy"]), 3),
                             ene_mean=round(st.mean(g["ene"]), 1),
                             comparable_n=len(g["gap"]), total_n=len(g["total"]),
                             picked=""))

    # ---- SBS(词典序:excess_fail 总数最小 → gap 均值最小)与 closed gap ----
    fixed_glob = {s: _mean_or_none(glob[s]["gap"]) for s in FIXED}
    fixed_exf = {s: sum(glob[s]["exf"]) for s in FIXED}
    sbs = min(FIXED, key=lambda s: (fixed_exf[s],
                                    float("inf") if fixed_glob[s] is None else fixed_glob[s]))
    gap_sbs = fixed_glob[sbs]
    closed = {}
    for o in OBJECTIVES:
        det_gap = _mean_or_none(glob[f"det_{o}"]["gap"])
        closed[o] = ((gap_sbs - det_gap) / gap_sbs * 100.0
                     if gap_sbs and det_gap is not None else None)

    os.makedirs(OUT, exist_ok=True)
    prof_rows = [dict(scenario=s, seed=sd, **profiles[(s, sd)]) for s in scenarios
                 for sd in seeds]
    for fname, rows in (("oracle_gap_detail.csv", rows_detail), ("oracle_gap.csv", rows_agg),
                        ("oracle_gap_profiles.csv", prof_rows)):
        with open(os.path.join(OUT, fname), "w", newline="", encoding="utf-8-sig") as fp:
            w = csv.DictWriter(fp, fieldnames=list(rows[0].keys()))
            w.writeheader(); w.writerows(rows)

    # ---- 双预案判读(总库 A1 授权口径,按数据自动落笔) ----
    sbs_worst = sorted([r for r in rows_agg if r["selector"] == sbs
                        and r["scenario"] != "ALL" and r["gap_mean"] != ""],
                       key=lambda r: -r["gap_mean"])[:3]
    L = ["# A1 oracle gap 实验判读(oracle_gap.py 自动生成;数据=instgen_detail 13场景×30seed)",
         "",
         f"- VBS(词典序 oracle:fail 最小→exp_t 最小);unrestricted oracle 更低的实例 "
         f"{raw_lt_lex}/{n_inst}(纯速度下界,含 fail>0 漏件失真,只做参考不进叙事)。",
         f"- SBS(词典序最优固定策略:excess_fail 总数→gap 均值)= **{sbs}**,"
         f"全局平均 gap {_fmt(gap_sbs, '.2f')}%;其最差三场景:"
         + "、".join(f"{r['scenario']} {r['gap_mean']:.1f}%" for r in sbs_worst) + "。",
         f"- 固定策略 excess_fail 总账(30 实例累计,>0=有漏件假优势不可作 SBS):"
         + " ".join(f"{s}={fixed_exf[s]}" for s in FIXED) + "。", ""]
    for o in OBJECTIVES:
        g = glob[f"det_{o}"]
        g_gap = _mean_or_none(g["gap"])
        g_attain = _mean_or_none(g["attain"])
        L.append(f"- 检测器[{o}]:全局 gap {_fmt(g_gap, '.2f')}%,"
                 f"达 oracle {_fmt(g_attain, '.1f')}%,closed gap {_fmt(closed[o], '.1f')}%,"
                 f"excess_fail 均值 {st.mean(g['exf']):.2f}"
                 f",可比 {len(g['gap'])}/{len(g['total'])}(excess_fail=0),"
                 f"heavy_tier {st.mean(g['heavy']):.2f},energy {st.mean(g['ene']):.0f}")
    hol_attain = _mean_or_none(glob["det_holistic"]["attain"])
    lex_attain = _mean_or_none(glob["det_lexicographic"]["attain"])
    valid_attains = [v for v in (hol_attain, lex_attain) if v is not None]
    best_attain = max(valid_attains) if valid_attains else None
    best_o = max(OBJECTIVES, key=lambda o: _mean_or_none(glob[f"det_{o}"]["attain"])
                 if glob[f"det_{o}"]["attain"] else float("-inf"))
    worst_fix = max((s for s in FIXED if fixed_glob[s] is not None), key=lambda s: fixed_glob[s])
    L += ["", "## 双预案落笔(0711 授权)", ""]
    if lex_attain is not None and lex_attain >= 95.0:
        L.append(f"**预案①得到sim证据**:词典序检测器通过一次画像/查表，在excess_fail=0可比域"
                 f"达到oracle {lex_attain:.1f}%。它是不在线试跑多策略的低负载候选形态；历史AB PC仿真"
                 f"只观察到单件推荐含400格全扫在1个任务周期内完成，实体AC500最坏时延与watchdog未测。"
                 f"因此不得把该结果称为PLC实测、理论上限或已证明的工程最优形态。")
    if gap_sbs >= 5.0 or (sbs_worst and sbs_worst[0]["gap_mean"] >= 10.0):
        L.append(f"**预案②成立**:场景间最优策略差异显著——词典序可用的最优固定策略 {sbs} "
                 f"在最差场景落后 oracle {sbs_worst[0]['gap_mean']:.1f}%"
                 f"({sbs_worst[0]['scenario']}),最差固定策略 {worst_fix} 全局 gap "
                 f"{fixed_glob[worst_fix]:.1f}%;纯速度候选 tob 虽 gap 低但在 dense 场景"
                 f"漏件 {fixed_exf['tob']} 件(题面'存放准确性'一票否决)——单一策略存在"
                 f"结构性风险,场景检测是硬需而非锦上添花。")
    if best_attain is not None and best_attain < 95.0 and gap_sbs < 5.0:
        L.append(f"两预案均未达阈值(检测器最高 attain {best_attain:.1f}%、"
                 f"SBS gap {gap_sbs:.2f}%):按'检测器与最优固定策略同水平,价值在可解释切换"
                 f"与安全档位'的保守口径写,不夸大。")
    hh, sh = st.mean(glob["det_holistic"]["heavy"]), st.mean(glob["det_speed"]["heavy"])
    he, se = st.mean(glob["det_holistic"]["ene"]), st.mean(glob["det_speed"]["ene"])
    L += ["", "## holistic 档的 gap = 有意支付的安全溢价(多目标护栏,防单目标误读)", "",
          f"- oracle gap 只量 exp_t 单目标;holistic 档(主打 AWRA)全局 gap "
          f"{st.mean(glob['det_holistic']['gap']):.1f}% 的对价:重货平均层高 {hh:.2f} vs "
          f"speed 档 {sh:.2f}(低 {sh / hh:.1f} 倍),能耗代理 {he:.0f} vs {se:.0f}"
          f"(低 {(1 - he / se) * 100:.0f}%)。",
          "- 报告口径:sim可比较holistic/lexicographic/speed三档；当前ST源码已有holistic/lexicographic"
          "切换、CB/TOB分配与对应新增断言，但尚未完成新一轮AB复测。故98.5%/99.9%仍只属于"
          "excess_fail=0可比域的sim结果，不得写成已验证的客户档或控制器效果。"]
    L += ["", "## 检测器逐场景推荐核查(lexicographic 档 vs 0706 标定表 detector_rules.md)", ""]
    for scn in scenarios:
        picks = sorted(set(agg_acc[(scn, "det_lexicographic")]["strat"]))
        L.append(f"- {scn}: {' '.join(picks)}")
    with open(os.path.join(OUT, "oracle_gap_summary.txt"), "w", encoding="utf-8") as fp:
        fp.write("\n".join(L) + "\n")

    # ---- fig13:左=检测器三档+SBS 逐场景 gap;右=7 固定策略全局 gap 排名 ----
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 4.6),
                                   gridspec_kw={"width_ratios": [2.2, 1]})
    series = [("det_holistic", "检测器·holistic(全要素默认)", "#1565c0"),
              ("det_lexicographic", "检测器·词典序", "#2e7d32"),
              ("det_speed", "检测器·纯效率", "#ef6c00"),
              (sbs, f"SBS 最优固定策略({sbs})", "#9e9e9e")]
    W = 0.2
    for i, (sel, label, color) in enumerate(series):
        vals, errs = [], []
        for scn in scenarios:
            r = next(r for r in rows_agg if r["scenario"] == scn and r["selector"] == sel)
            vals.append(0.0 if r["gap_mean"] == "" else r["gap_mean"])
            errs.append(0.0 if r["gap_ci95"] == "" else r["gap_ci95"])
        xs = [x + (i - 1.5) * W for x in range(len(scenarios))]
        ax1.bar(xs, vals, W, yerr=errs, capsize=2, label=label, color=color,
                error_kw=dict(lw=0.7))
    ax1.set_xticks(range(len(scenarios)))
    ax1.set_xticklabels(scenarios, rotation=35, ha="right", fontsize=8)
    ax1.set_ylabel("oracle gap(%,低=好)")
    ax1.set_title("检测器三档 vs 最优固定策略:逐场景 oracle gap(30 seeds,±CI95)", fontsize=11)
    ax1.legend(fontsize=8)
    ax1.axhline(0, color="#444", lw=0.8)
    ax1.spines[["top", "right"]].set_visible(False)
    order = sorted(FIXED, key=lambda s: (fixed_exf[s] > 0,
                                         float("inf") if fixed_glob[s] is None else fixed_glob[s]))
    bar_vals = [0.0 if fixed_glob[s] is None else fixed_glob[s] for s in order]
    ax2.barh(range(len(order)), bar_vals,
             color=["#2e7d32" if s == sbs else
                    "#c62828" if fixed_exf[s] > 0 else "#90a4ae" for s in order])
    for i, s in enumerate(order):
        note = (" N/A" if fixed_glob[s] is None else f" {fixed_glob[s]:.1f}%")
        if fixed_exf[s] > 0:
            note += f"(漏件{fixed_exf[s]}件;百分比仅含可比实例)"
        ax2.text(max(0.0 if fixed_glob[s] is None else fixed_glob[s], 0),
                 i, note, va="center", fontsize=7.5)
    ax2.set_yticks(range(len(order)))
    ax2.set_yticklabels(order, fontsize=9)
    ax2.set_xlabel("全局平均 gap(%;红=有失败漏件,exp_t 失真)")
    ax2.set_title("固定策略 vs oracle(全 390 实例)", fontsize=11)
    ax2.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    os.makedirs(os.path.join(HERE, "figs"), exist_ok=True)
    fig.savefig(os.path.join(HERE, "figs", "fig13_oracle_gap.png"), dpi=300)

    print("\n".join(L[:20]))
    print(f"\nCSV/判读/图已写:out/oracle_gap*.csv, out/oracle_gap_summary.txt,"
          f" figs/fig13_oracle_gap.png")


if __name__ == "__main__":
    main()
