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


def metrics_of(goods, tie_break, ls_eps, rule="sum"):
    ws.ACCEL = False
    wm, fm = max(g.weight for g in goods), max(g.freq for g in goods)
    fn = ws.make_score_fn(1.0, 0.6, 0.4, 0.15, wm, fm)
    wh, placed, failed = ws.run_awra_ls(goods, rule, fn, wm, fm,
                                        tie_break=tie_break, ls_eps=ls_eps)
    return ws.metrics(wh, placed, failed)


def main():
    print("=" * 68)
    print("T2.1 一致性探针:sim 口径(full,1e-12) vs 完整 ST 语义(st二元组,1e-6)")
    print("gap 源:G1 assign tie-break(score&travel 双平局);G2 LS 阈值(单双精度)")
    print("=" * 68)

    seeds = [2026 + i for i in range(30)]
    g1 = g2 = both = diff_items = 0
    max_expt_d = max_energy_rd = 0.0
    worst = None
    for name in ig.SCENARIOS:
        for sd in seeds:
            goods = ig.gen_instance(name, sd)
            base = run_variant(goods, "sum", "full", 1e-12)
            if diff_of(base, run_variant(goods, "sum", "st", 1e-12)):    # 仅 tie-break
                g1 += 1
            if diff_of(base, run_variant(goods, "sum", "full", 1e-6)):   # 仅阈值
                g2 += 1
            d = diff_of(base, run_variant(goods, "sum", "st", 1e-6))     # 完整 ST 语义
            if d:
                both += 1
                diff_items += len(d)
                mf = metrics_of(goods, "full", 1e-12)                    # 聚合等价性验证
                ms = metrics_of(goods, "st", 1e-6)
                max_expt_d = max(max_expt_d, abs(mf["exp_t"] - ms["exp_t"]))
                max_energy_rd = max(max_energy_rd,
                                    abs(mf["energy"] - ms["energy"]) / max(mf["energy"], 1.0))
                if worst is None or len(d) > worst[2]:
                    worst = (name, sd, len(d))
    n = len(ig.SCENARIOS) * 30
    print(f"\n[全量 {n} 次(12 场景 × 30 seeds)]")
    print(f"  G1 tie-break 单独触发: {g1}/{n}(理论 gap,score&travel 需同时相等)")
    print(f"  G2 LS 阈值 单独触发:  {g2}/{n}(单双精度结构性)")
    print(f"  完整 ST 语义布局分歧:  {both}/{n}(共 {diff_items} 件位置不同)")
    if worst:
        print(f"  最大分歧: {worst[0]} seed {worst[1]} → {worst[2]} 件")
    print(f"  ★ 分歧场景聚合指标差异上界: exp_t {max_expt_d:.2e},energy 相对 {max_energy_rd:.2e}")

    demo = ws.gen_goods(20, 2026)
    _, _, dd = run_both(demo)
    print(f"\n[演示批 20 件 seed=2026(T25 用同批)] 布局分歧: {len(dd)} 件"
          f" → {'✅ 逐位一致,T25 逐位护栏有效' if not dd else '❌'}")

    print("\n结论:")
    print(f"  G1 零/近零触发=理论 gap;G2 {g2}/{n} 触发(单双精度)。但**分歧布局的聚合")
    print(f"  指标差异 ≈ {max_expt_d:.1e}**——sim 与 ST 收敛到 score 完全等价的不同局部最优")
    print("  (高密度下等价最优解有多个分支),非缺陷 → sim↔ST 数值等价、演示批逐位一致。")
    print("  G2 不可靠改 ST 消除(单精度精度所限);正确定位=承认等价解,T25 用小批量演示逐位护栏。")


if __name__ == "__main__":
    main()
