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
    "seq":    dict(en="Fixed-scan first-fit (engineering baseline)", zh="固定扫描序首个可行位",
                   anchor="题面字面策略;工业对应 SAP EWM Next Empty Bin(正名待拍板)"),
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


# 规则表(v0 先验版;--calibrate 用 30-seed 数据重标定后覆盖此注释块并写入
# out/detector_rules.md。规则形状=可直接蒸馏 ST if-else 的阈值级联):
#   证据基础:T1.1 全量数据(在线组 score≈near 于低偏斜/极小批;dense fail 差异)
#   + HSG 1976(偏斜是 turnover 类策略收益的来源)。
def select_strategy(profile, batch_known=True):
    """按批次画像推荐策略。batch_known=False 时只在在线组内选。"""
    p = profile
    if not batch_known:                       # 在线逐件:只有 seq/near/score 可选
        if p["skew"] < 0.35 or p["n"] <= 20:  # 画像无信息量/极小批→COL 即可
            return "near"
        return "score"
    if p["density"] >= 0.70:                  # 高压:批量重排防 fail(T1.1 硬证据)
        return "awra"
    if p["skew"] < 0.35:                      # 低偏斜:turnover 类失去收益来源
        return "near" if p["n"] <= 60 else "awra"
    return "awra"                             # 默认:批量已知时 AWRA-LS 全场景未败


def st_ifelse(rules_doc=False):
    """输出检测器的 ST if-else 蒸馏文本(块2 移植用;与 select_strategy 同逻辑)。"""
    return (
        "(* FC_SelectStrategy — 场景检测器蒸馏版(strategy_lib.select_strategy 同逻辑) *)\n"
        "IF NOT bBatchKnown THEN\n"
        "    IF rSkew < 0.35 OR nBatch <= 20 THEN sStrategy := 'COL';\n"
        "    ELSE sStrategy := 'SCORE'; END_IF;\n"
        "ELSIF rDensity >= 0.70 THEN sStrategy := 'AWRA';\n"
        "ELSIF rSkew < 0.35 AND nBatch <= 60 THEN sStrategy := 'COL';\n"
        "ELSE sStrategy := 'AWRA'; END_IF;\n"
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
    """从 out/instgen_agg.csv(7 策略全量后)提取每场景最优策略与并列关系,
    生成 out/detector_rules.md(规则表+每条规则的数据依据)。"""
    import csv
    path = os.path.join(HERE, "out", "instgen_agg.csv")
    if not os.path.exists(path):
        print("缺 out/instgen_agg.csv,先跑 python instance_gen.py")
        return
    rows = list(csv.DictReader(open(path, encoding="utf-8-sig")))
    scen = {}
    for r in rows:
        scen.setdefault(r["scenario"], []).append(r)
    lines = ["# 检测器标定表(自动生成;每场景最优策略+CI 并列判定)", ""]
    lines.append("| 场景 | 最优 | exp_t±CI | CI 并列的次优 |")
    lines.append("|---|---|---|---|")
    for name, rs in scen.items():
        rs = sorted(rs, key=lambda r: float(r["exp_t_mean"]))
        best = rs[0]
        b_hi = float(best["exp_t_mean"]) + float(best["exp_t_ci95"])
        ties = [r["strat"] for r in rs[1:]
                if float(r["exp_t_mean"]) - float(r["exp_t_ci95"]) <= b_hi]
        lines.append(f"| {name} | {best['strat']} | "
                     f"{best['exp_t_mean']}±{best['exp_t_ci95']} | {','.join(ties) or '-'} |")
    out = os.path.join(HERE, "out", "detector_rules.md")
    with open(out, "w", encoding="utf-8") as fp:
        fp.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"\n写入:{out}")


if __name__ == "__main__":
    main()
