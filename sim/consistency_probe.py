# -*- coding: utf-8 -*-
"""
consistency_probe.py — T2.1 sim↔ST 一致性审计探针(0707,brainstorm 步 a/9 实现)

背景:AWRA-LS 的 assign 阶段,Python 用四元组 tie-break (score,travel,tier,col),
ST FB_SelectSlot 用 (score,travel)+扫描序(col 外 tier 内)兜底。二者仅在 score 与
travel **同时相等**时可能选不同位置(reloc/swap 两口径同为 score+扫描序,已一致)。
本探针用数据回答:这个理论 gap 在真实数据下是否触发?

方法:同一批货物,分别用 tie_break="full"(现 sim 口径)与 "st"(模拟 ST 语义)跑
run_awra_ls,逐位比对终局布局。全一致 → gap 零触发,T25 端到端向量会绿;
有分歧 → 定位到具体货物/位置,决定统一哪边 tie-break。

覆盖:演示批 20 件(seed 2026,T25 用同批)+ 12 场景 × 30 seeds 全量压力。
运行:python consistency_probe.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import warehouse_sim as ws
import instance_gen as ig


def layout_map(placed):
    """货物 gid → (col, tier) 映射(逐位比对用)。"""
    return {g.gid: pos for g, pos in placed}


def run_variant(goods, rule, tie_break, ls_eps):
    ws.ACCEL = False                                  # 与 T19/T25 同口径(匀速)
    wm, fm = max(g.weight for g in goods), max(g.freq for g in goods)
    fn = ws.make_score_fn(1.0, 0.6, 0.4, 0.15, wm, fm)
    _, placed, _ = ws.run_awra_ls(goods, rule, fn, wm, fm,
                                  tie_break=tie_break, ls_eps=ls_eps)
    return layout_map(placed)


def diff_of(ma, mb):
    return [(gid, ma[gid], mb.get(gid)) for gid in ma if ma[gid] != mb.get(gid)]


def run_both(goods, rule="sum"):
    """sim 口径(full,1e-12)vs 完整 ST 语义(st,1e-6),返回分歧列表。"""
    m_sim = run_variant(goods, rule, "full", 1e-12)
    m_st = run_variant(goods, rule, "st", 1e-6)       # ST:二元组 tie-break + 单精度阈值
    return m_sim, m_st, diff_of(m_sim, m_st)


def main():
    print("=" * 68)
    print("T2.1 一致性探针:sim 口径(full,1e-12) vs 完整 ST 语义(st二元组,1e-6)")
    print("两个 gap 源:G1 assign tie-break(score&travel 双平局);G2 LS 改进阈值(单双精度)")
    print("=" * 68)

    # ---- 分离测两个 gap(定位来源)----
    print("\n[gap 分离,12 场景 × 30 seeds]")
    seeds = [2026 + i for i in range(30)]
    g1_hits = g2_hits = both_hits = 0
    for name in ig.SCENARIOS:
        for sd in seeds:
            goods = ig.gen_instance(name, sd)
            base = run_variant(goods, "sum", "full", 1e-12)
            if diff_of(base, run_variant(goods, "sum", "st", 1e-12)):     # 仅 tie-break 变
                g1_hits += 1
            if diff_of(base, run_variant(goods, "sum", "full", 1e-6)):    # 仅阈值变
                g2_hits += 1
            if diff_of(base, run_variant(goods, "sum", "st", 1e-6)):      # 都变(完整 ST)
                both_hits += 1
    print(f"  G1 tie-break 单独触发: {g1_hits}/390 次")
    print(f"  G2 LS 阈值 单独触发:  {g2_hits}/390 次")
    print(f"  完整 ST 语义 vs sim:  {both_hits}/390 次")

    # ---- 演示批 20 件(T25 端到端向量的同一批)----
    demo = ws.gen_goods(20, 2026)
    _, _, diff = run_both(demo)
    print(f"\n[演示批 20 件 seed=2026 sum口径] 完整语义分歧: {len(diff)} 件"
          f" → {'✅ 逐位一致,T25 向量可用 full 口径导出' if not diff else '❌ 见下'}")
    for gid, pf, ps in diff:
        print(f"    货物 {gid}: sim={pf}  ST={ps}")

    # ---- 12 场景 × 30 seeds 全量压力(找极端触发)----
    print(f"\n[全量压力 12 场景 × 30 seeds]")
    total_diff_seeds = 0
    total_diff_items = 0
    worst = None
    for name in ig.SCENARIOS:
        for sd in [2026 + i for i in range(30)]:
            goods = ig.gen_instance(name, sd)
            _, _, diff = run_both(goods)
            if diff:
                total_diff_seeds += 1
                total_diff_items += len(diff)
                if worst is None or len(diff) > worst[2]:
                    worst = (name, sd, len(diff))
    n_runs = len(ig.SCENARIOS) * 30
    print(f"  {n_runs} 次运行中,布局有分歧的: {total_diff_seeds} 次"
          f"(共 {total_diff_items} 件货位置不同)")
    if worst:
        print(f"  最大分歧: 场景 {worst[0]} seed {worst[1]} → {worst[2]} 件")
    print(f"\n结论: {'两种 tie-break 全场景逐位一致 → gap 理论存在但零触发,' if total_diff_seeds == 0 else 'gap 实际触发,需统一 tie-break;'}"
          f"{'ST 移植若忠实,终局布局必与 sim 相同,T25 用 full 口径导出即可。' if total_diff_seeds == 0 else ''}")
    if total_diff_seeds > 0:
        print("  → 决策:统一为 full 口径——ST FB_SelectSlot 补 tier/col 显式次级 tie-break,")
        print("    或 sim assign 降为二元组(需重跑 H 锁)。挂机保守:改 ST(不动已锁 sim 数字)。")


if __name__ == "__main__":
    main()
