# -*- coding: utf-8 -*-
"""
strategy_lib.py — T1.2 策略库 + 场景检测器(U1;0706 deep-research 定版)

一、术语正名表 TERMS(用户令 0706:一律学术标准名;证据=deep-research 12 条
    confirmed claims,奠基文献三方多票核对):
    经典三族 = randomized / class-based / full-turnover-based storage
    (Hausman, Schwarz & Graves 1976, Management Science 22(6):629-638)。
二、新增两个经典批量策略(补全四联对比的"vs ABC"腿,并为检测器提供更全候选):
    CB  Class-based storage  三级分区(A/B/C 按累计频次 70%/90% 分界,经典惯例;
        区=可行位按行程时间升序三段,段长按类件数配额)
    TOB Full-turnover-based storage  周转率降序逐件放最近可行位
        (COI 变体:Heskett 1963/64 提出、Kallina & Lynn 1976 证 LP 最优,
         按 vol/freq 升序;开关 use_coi 切换)
三、场景检测器 detect_scenario:批次画像特征 → 推荐策略(规则由 instance_gen
    30-seed 数据标定,calibrate 模式生成;可蒸馏 ST if-else,块2 移植)。
    工业对应物=Dynamic Slotting with Scenario Management(Lucas 等);
    学术框架=Algorithm Selection Problem(Rice 1976)。

不适用而不实现(报告边界点名):duration-of-stay(Goetschalckx & Ratliff 1990,
    需驻留时间信息,纯入库场景无此数据,决赛展望);correlation-based(CoB,
    目标含货物间交互项=QAP,NP-hard,超出线性口径)。

运行:python strategy_lib.py            # 冒烟:新策略 3 seeds 快检
     python strategy_lib.py --calibrate # 读 out/instgen_agg.csv 标定检测器规则
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import warehouse_sim as ws

HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------- 一、术语正名表(报告/画面/注释统一引用此表) ----------------
TERMS = {
    "random": dict(en="Random-based storage (RB)", zh="随机存储",
                   anchor="Hausman, Schwarz & Graves 1976, Mgmt Sci 22(6)"),
    "seq":    dict(en="Fixed-Scan First-Fit (engineering baseline)", zh="固定扫描优先(工程基线)",
                   anchor="题面'连续存放'字面策略,无文献专名——如实标注(0706 拍板①);工业近亲 SAP EWM Next Empty Bin(仅提及不冒认)"),
    "near":   dict(en="Closest Open Location (COL)", zh="最近可用库位",
                   anchor="HSG 1976(与 RB 等价性论断);Reyes et al. 2019 目录 COL"),
    "score":  dict(en="Multi-criteria weighted scoring (frequency-based family)",
                   zh="多准则加权评分", anchor="Reyes et al. 2019 目录 FB 族的多目标推广"),
    "awra":   dict(en="Rank-and-Assign with Local Search (AWRA-LS)", zh="加权排序分配+局部搜索",
                   anchor="Pan et al. 2025 IEEE TKDE 同名分层架构;批量启发式族"),
    "cb":     dict(en="Class-based storage (CB)", zh="ABC 分级存储",
                   anchor="HSG 1976 三分类之一;Petersen et al. 2004 实践 2-4 类"),
    "tob":    dict(en="Full-turnover-based storage (TOB)", zh="全周转率存储",
                   anchor="HSG 1976;COI 变体:Heskett 1963/64,Kallina & Lynn 1976 LP 最优性"),
}


# ---------------- 二、新增经典批量策略 ----------------
def _slots_by_time(wh):
    """全部非预占位按行程时间升序(平局取低层、小列——与 COL 平局规则一致)。"""
    slots = [(c, t) for c in range(ws.COLS) for t in range(ws.TIERS)
             if wh.grid[c][t] is None]
    return sorted(slots, key=lambda s: (ws.travel_time(*s), s[1], s[0]))


def _place_from(wh, good, order, start=0):
    """从 order[start:] 起找第一个可行位;找不到返回 None(边界口径同 ST 侧)。"""
    for i in range(start, len(order)):
        c, t = order[i]
        if wh.feasible(c, t, good):
            return c, t
    return None


def run_full_turnover(goods, rule, use_coi=False):
    """TOB:周转率(freq)降序逐件放全局最近可行位;use_coi=True 改按 COI=vol/freq
    升序(低 COI 先挑近位)。返回 (wh, placed, failed) 同 run_awra_ls 签名。"""
    wh = ws.Warehouse(rule)
    if use_coi:
        ranked = sorted(goods, key=lambda g: (g.vol / max(g.freq, 1e-9), g.gid))
    else:
        ranked = sorted(goods, key=lambda g: (-g.freq, g.gid))
    placed, failed = [], []
    for g in ranked:
        pos = _place_from(wh, g, _slots_by_time(wh))
        if pos is None:
            failed.append(g)
            continue
        wh.put(pos[0], pos[1], g)
        placed.append((g, pos))
    return wh, placed, failed


def run_class_based(goods, rule, boundaries=(0.70, 0.90)):
    """CB:货物按频次降序累计占比分 A/B/C(默认 70%/90% 分界,经典惯例);
    可行位按行程时间升序,按各类件数切三段配额;各类件在本段内找最近可行位,
    段内无可行位则溢出到后续位序(承重边界处理,口径与 ST 移植一致)。"""
    wh = ws.Warehouse(rule)
    ranked = sorted(goods, key=lambda g: (-g.freq, g.gid))
    f_tot = sum(g.freq for g in ranked) or 1.0
    cls_of, acc = {}, 0.0
    for g in ranked:
        acc += g.freq
        cls_of[g.gid] = 0 if acc <= boundaries[0] * f_tot else \
                        (1 if acc <= boundaries[1] * f_tot else 2)
    n_cls = [sum(1 for g in ranked if cls_of[g.gid] == k) for k in range(3)]
    placed, failed = [], []
    # 段起点按类件数累计(A 段从 0 起,B 段从 nA 起,C 段从 nA+nB 起)
    starts = [0, n_cls[0], n_cls[0] + n_cls[1]]
    for g in ranked:                          # 类内按频次序逐件放
        order = _slots_by_time(wh)
        pos = _place_from(wh, g, order, start=min(starts[cls_of[g.gid]], max(len(order) - 1, 0)))
        if pos is None:                       # 段起点之后全不可行→从头兜底(溢出回近区)
            pos = _place_from(wh, g, order, start=0)
        if pos is None:
            failed.append(g)
            continue
        wh.put(pos[0], pos[1], g)
        placed.append((g, pos))
    return wh, placed, failed


# ---------------- 三、场景检测器(特征 → 推荐策略) ----------------
def batch_profile(goods, capacity=267):
    """批次画像特征(全部可由 PLC 侧一次遍历算出,便于 ST 蒸馏):
    n         批量大小
    density   n / 可用位数(sum 口径 267)
    skew      频次偏斜度 = top20% 件的频次占比(0.2=无偏斜,→1=极端偏斜)
    w_mean    重量均值;w_heavy 超过 60kg 件占比(承重压力代理)
    """
    n = len(goods)
    fs = sorted((g.freq for g in goods), reverse=True)
    f_tot = sum(fs) or 1.0
    top = max(1, n // 5)
    return dict(
        n=n,
        density=round(n / capacity, 3),
        skew=round(sum(fs[:top]) / f_tot, 3),
        w_mean=round(sum(g.weight for g in goods) / max(n, 1), 1),
        w_heavy=round(sum(1 for g in goods if g.weight > 60.0) / max(n, 1), 3),
    )


# 规则表 v1(0706 由 7 策略×30 seeds 标定表蒸馏,out/detector_rules.md;
# 规则形状=可直接蒸馏 ST if-else 的阈值级联)。
# **检测器的目标口径本身是输入**(F18-3):三档 objective——
#   speed         纯效率(exp_t 词典首键):TOB 主导,dense 因 fail 否决转 CB;
#   lexicographic 词典序(fail=0→exp_t+CI 并列→heavy_tier 低)=标定表原样;
#   holistic      题面全要素(承重稳定 C6/能耗 C4 权重高):AWRA 主导,
#                 极小批/无画像信息时降级简单规则(在线组 F18-2)。
# 默认档=holistic(挂机保守解,与主打算法叙事一致;默认档最终待拍板)。
def select_strategy(profile, batch_known=True, objective="holistic"):
    """按批次画像推荐策略。batch_known=False 时只在在线组内选(seq/near/score)。"""
    p = profile
    if not batch_known:                       # 在线逐件场景
        if p["skew"] < 0.35 or p["n"] <= 20:  # 画像无信息量/极小批→COL 即可(F18-2)
            return "near"
        return "score"
    if objective == "speed":
        return "cb" if p["density"] >= 0.70 else "tob"   # dense:TOB fail 9.7 被否决(F19)
    if objective == "lexicographic":          # 标定表 v1 蒸馏(out/detector_rules.md;12/12)
        if p["density"] >= 0.70:
            return "cb"                       # cb 快于 awra 且 fail=0(重货偏高,待拍板)
        if p["density"] <= 0.25 and p["n"] > 20:
            return "awra"                     # 低密度:与 tob CI 并列,安全键胜出
        return "tob"                          # 极小批(n≤20)tob 显著更快,不并列
    # holistic(默认):重货层高/能耗/高压 fail 全要素——AWRA 未在任何场景被否决
    if p["skew"] < 0.35 and p["n"] <= 20:
        return "near"                         # 极小批+无画像:简单规则即可(F18-2)
    return "awra"


def recommend(profile, batch_known=True, objective="holistic",
              prefer_throughput=False):
    """检测器完整输出(0706 拍板②④⑤落地):
    strategy      主推策略(④:AWRA 为主;prefer_throughput=True 且高密度时切 CB
                  ——'企业更重吞吐'的可选配项,报告写成可配置开关)
    alt           备选策略+切换条件(④附带条件的显式表达)
    delta_suggest δ 建议值(②条件化:density≥0.70 才开 0.15,否则 0——
                  F21:低填充 δ 净亏/高压回库失败 -26%)
    objective     评判档位(⑤三档并存:holistic 全要素默认/speed 纯效率/
                  lexicographic 词典序,按演示与客户口径切换)"""
    p = profile
    strat = select_strategy(p, batch_known, objective)
    alt = ""
    if batch_known and p["density"] >= 0.70:
        if prefer_throughput and objective != "holistic":
            strat, alt = "cb", "awra(重货层高低4倍/能耗低——安全合规口径)"
        else:
            alt = "cb(exp_t 快约8%——吞吐优先口径可选配)"
    delta = 0.15 if p["density"] >= 0.70 else 0.0
    return dict(strategy=strat, alt=alt, delta_suggest=delta,
                objective=objective,
                note="δ 条件化依据 F21;主推 AWRA、CB 可选配依据 0706 拍板④")


def st_ifelse(objective="holistic"):
    """输出检测器的 ST if-else 蒸馏文本(块2 移植用;与 select_strategy v1 同逻辑)。"""
    if objective == "lexicographic":
        body = ("ELSIF rDensity >= 0.70 THEN sStrategy := 'CB';\n"
                "ELSIF rDensity <= 0.25 AND nBatch > 20 THEN sStrategy := 'AWRA';\n"  # 0712 修:补 n>20,与 select_strategy 对齐(曾漏致 tiny_light 误路由)
                "ELSE sStrategy := 'TOB'; END_IF;\n")
    else:                                     # holistic 默认档
        body = ("ELSIF rSkew < 0.35 AND nBatch <= 20 THEN sStrategy := 'COL';\n"
                "ELSE sStrategy := 'AWRA'; END_IF;\n")
    return (
        "(* FC_SelectStrategy — 场景检测器蒸馏版 v1(objective=" + objective + ") *)\n"
        "IF NOT bBatchKnown THEN\n"
        "    IF rSkew < 0.35 OR nBatch <= 20 THEN sStrategy := 'COL';\n"
        "    ELSE sStrategy := 'SCORE'; END_IF;\n" + body
    )


# ---------------- 冒烟 ----------------
def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--calibrate", action="store_true",
                    help="读 out/instgen_agg.csv 重标定检测器规则(需先跑 instance_gen)")
    a = ap.parse_args()
    if a.calibrate:
        print("标定模式:由 instance_gen 全量数据驱动,见 calibrate_detector()")
        calibrate_detector()
        return
    for sd in (2026, 7, 42):
        goods = ws.gen_goods(120, sd)
        for name, fn in (("cb", run_class_based), ("tob", run_full_turnover)):
            wh, placed, failed = fn(goods, "sum")
            m = ws.metrics(wh, placed, failed)
            print(f"seed={sd} {name}: exp_t={m['exp_t']:.2f} fail={m['fail']} viol={m['viol']}")
        prof = batch_profile(goods)
        print(f"seed={sd} profile={prof} -> {select_strategy(prof)}")


def calibrate_detector():
    """从 out/instgen_agg.csv(7 策略全量后)按**词典序目标**标定每场景最优:
    ①可行性:fail_mean>0 一票否决(题面'存放准确性'=必须放得进);
    ②效率:exp_t 最优 + CI 重叠者入并列集;
    ③安全平票键:并列集内取 heavy_tier 最低(题面'存放合理性'=重货靠底层)。
    纯 exp_t 单键会全选 TOB(它在 dense fail=9.7 件)——单指标标定不可辩护。
    生成 out/detector_rules.md。综合目标的加权形式待拍板,词典序为挂机保守解。"""
    import csv
    path = os.path.join(HERE, "out", "instgen_agg.csv")
    if not os.path.exists(path):
        print("缺 out/instgen_agg.csv,先跑 python instance_gen.py")
        return
    rows = list(csv.DictReader(open(path, encoding="utf-8-sig")))
    scen = {}
    for r in rows:
        scen.setdefault(r["scenario"], []).append(r)
    lines = ["# 检测器标定表(词典序:fail=0 → exp_t 最优+CI并列 → heavy_tier 低)",
             "", "| 场景 | 推荐 | exp_t±CI | heavy_tier | CI 并列集 | 淘汰(fail>0) |",
             "|---|---|---|---|---|---|"]
    for name, rs in scen.items():
        ok = [r for r in rs if float(r["fail_mean"]) == 0.0]
        cut = [r["strat"] for r in rs if float(r["fail_mean"]) > 0.0]
        ok = sorted(ok, key=lambda r: float(r["exp_t_mean"]))
        best_t = float(ok[0]["exp_t_mean"]) + float(ok[0]["exp_t_ci95"])
        ties = [r for r in ok
                if float(r["exp_t_mean"]) - float(r["exp_t_ci95"]) <= best_t]
        pick = min(ties, key=lambda r: float(r["heavy_tier_mean"]))
        lines.append(
            f"| {name} | **{pick['strat']}** | {pick['exp_t_mean']}±{pick['exp_t_ci95']} | "
            f"{pick['heavy_tier_mean']} | {','.join(r['strat'] for r in ties)} | "
            f"{','.join(cut) or '-'} |")
    out = os.path.join(HERE, "out", "detector_rules.md")
    with open(out, "w", encoding="utf-8") as fp:
        fp.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"\n写入:{out}")


if __name__ == "__main__":
    main()
