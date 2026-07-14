"""F3 补:CB 策略 Python↔ST 钳位逻辑等价性复现脚本(补此前"420 实例零分歧"无 committed 脚本)。

背景:Codex 0712 只读差分探针(_通信/codex_out/轨B_ST对抗审查_0712.md §2.1)报告
"420/420 一致、mismatch=0",但未落盘可复现脚本。本脚本把 ST 侧 CB 放置的分支结构
(plc/04_FB_Warehouse.st:435-470:pass1 跳过 iSkip 个空闲格→首个可行位;iFree≤iSkip 时
钳位试最后一个空闲格;pass2 从头回退)**独立用 Python 复刻**(不复用 strategy_lib._place_from),
再与 Python 参考实现 strategy_lib.run_class_based 逐实例对照终局位置+失败 ID。

域(与 Codex 探针一致):rule∈{sum,and} × n∈{1,3,20,60,120,200,260} × 30 seeds = 420 实例。
判据:每件货终局(col,tier)与失败集合完全一致 → mismatch=0。

诚实边界:这是**ST 分支逻辑的 Python 独立复刻**(回归用),不是 AB 实跑 ST;权威交叉核对
仍是 AB PC 仿真的黄金向量(export_st_vectors.py + 75/0)。二者一致只证"两份 Python 实现
(参考版 _place_from 口径 vs ST 分支结构口径)在该域等价",与 Codex 探针同口径同结论。

运行:python cb_st_equiv.py          # 全 420 实例
     python cb_st_equiv.py --v     # 打印每组明细
"""
from __future__ import annotations

import sys

import strategy_lib as sl
import warehouse_sim as ws

RULES = ["sum", "and"]
SIZES = [1, 3, 20, 60, 120, 200, 260]
SEEDS = [2026 + i for i in range(30)]
BOUNDARIES = (0.70, 0.90)


def cb_st_mimic(goods, rule, boundaries=BOUNDARIES):
    """独立复刻 ST(04_FB_Warehouse.st)的 CB 放置分支——不调用 _place_from。"""
    wh = ws.Warehouse(rule)
    ranked = sorted(goods, key=lambda g: (-g.freq, g.gid))       # 同 Python CB 排序
    f_tot = sum(g.freq for g in ranked) or 1.0
    cls_of, acc = {}, 0.0
    for g in ranked:                                             # 同 Python 分类
        acc += g.freq
        cls_of[g.gid] = 0 if acc <= boundaries[0] * f_tot else \
                        (1 if acc <= boundaries[1] * f_tot else 2)
    n_cls = [sum(1 for g in ranked if cls_of[g.gid] == k) for k in range(3)]
    starts = [0, n_cls[0], n_cls[0] + n_cls[1]]                  # 同 Python 段起点
    placed, failed = [], []
    for g in ranked:
        order = sl._slots_by_time(wh)          # 空闲格按 ST aSlotOrder 同序(travel,tier,col)
        pos = None
        for i_pass, i_skip in ((1, starts[cls_of[g.gid]]), (2, 0)):
            i_free, last = 0, None
            for (c, t) in order:               # ST:逐空闲格,过 iSkip 后首个可行位即放
                if i_free >= i_skip:
                    if wh.feasible(c, t, g):
                        pos = (c, t)
                        break
                last = (c, t)
                i_free += 1
            if pos is not None:
                break
            # ST 钳位分支:pass1 且空闲格总数 iFree(=len(order)) ≤ iSkip → 试最后一个空闲格
            if i_pass == 1 and 0 < len(order) <= i_skip and last is not None \
                    and wh.feasible(last[0], last[1], g):
                pos = last
                break
        if pos is None:
            failed.append(g)
            continue
        wh.put(pos[0], pos[1], g)
        placed.append((g, pos))
    return wh, placed, failed


def _fingerprint(placed, failed):
    return ({g.gid: pos for g, pos in placed}, frozenset(g.gid for g in failed))


def main():
    verbose = "--v" in sys.argv
    total = mism = 0
    detail = []
    for rule in RULES:
        for n in SIZES:
            for sd in SEEDS:
                goods = ws.gen_goods(n, sd)                      # 默认 skew,正常唯一 ID 域
                _, p_ref, f_ref = sl.run_class_based(goods, rule, BOUNDARIES)
                _, p_st, f_st = cb_st_mimic(goods, rule, BOUNDARIES)
                total += 1
                if _fingerprint(p_ref, f_ref) != _fingerprint(p_st, f_st):
                    mism += 1
                    detail.append(f"MISMATCH rule={rule} n={n} seed={sd}")
            if verbose:
                print(f"  rule={rule:<3} n={n:>3}: 30 seeds 累计通过")
    print(f"\nCB Python(参考 _place_from) ↔ ST 分支复刻:{total - mism}/{total} 一致,"
          f"mismatch={mism}  (rule{RULES}×n{SIZES}×{len(SEEDS)}seeds)")
    for d in detail[:20]:
        print("  " + d)
    sys.exit(1 if mism else 0)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    main()
