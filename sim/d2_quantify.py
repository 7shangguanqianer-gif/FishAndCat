# -*- coding: utf-8 -*-
"""
D-2 量化(overnight R3, 0712): 只切"权重"一个变量, 隔离 D-2 对头条数字的真实影响.
- H = caliber(accel=True,  adaptive=True )  报告头条口径(加减速+自适应权重)  应复现 headline.py 的 8.40s
- P = caliber(accel=True,  adaptive=False)  Python 加减速+静态默认权重 sim 消融（非 PLC 代理/真跑）
- L = caliber(accel=False, adaptive=False)  对照口径(匀速+静态)  仅作参考(headline.py 的对照列)
纯 python, 不碰 AB. seed 固定(headline.SEEDS), 可复现.
"""
import sys, os
sys.path.insert(0, r"F:\abb_wh_work\sim")
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
import statistics as st
import warehouse_sim as ws
import headline as h


def summarize(agg):
    awra_exp = st.mean(agg["awra"]["exp"])
    seq_exp = st.mean(agg["seq"]["exp"])
    score_exp = st.mean(agg["score"]["exp"])
    awra_ene = st.mean(agg["awra"]["ene"])
    seq_ene = st.mean(agg["seq"]["ene"])
    return dict(
        awra_exp=awra_exp,
        awra_std=st.stdev(agg["awra"]["exp"]),
        seq_exp=seq_exp,
        score_exp=score_exp,
        drop_vs_seq=(1 - awra_exp / seq_exp) * 100,
        ene_drop_vs_seq=(1 - awra_ene / seq_ene) * 100,
        gap_vs_score=(1 - awra_exp / score_exp) * 100,
        heavy_tier=st.mean(agg["awra"]["ht"]),
        viol=agg["awra"]["viol"],
    )


print("seeds =", h.SEEDS, "| 120件/skew/and | 每档5 seeds\n")
configs = [
    ("H 报告头条口径 (加减速+自适应权重)", True, True),
    ("P PLC 实际口径 (加减速+静态默认权重)", True, False),
    ("L 对照口径 (匀速+静态) 参考", False, False),
]
res = {}
for name, accel, adaptive in configs:
    agg = h.caliber(accel=accel, adaptive=adaptive)
    s = summarize(agg)
    res[name] = s
    print(f"### {name}")
    print(f"  awra 期望取货    = {s['awra_exp']:.3f} ± {s['awra_std']:.3f} s")
    print(f"  seq  基线取货    = {s['seq_exp']:.3f} s")
    print(f"  score 在线基线   = {s['score_exp']:.3f} s")
    print(f"  较 seq 降幅      = {s['drop_vs_seq']:.2f} %")
    print(f"  能耗较 seq 降幅  = {s['ene_drop_vs_seq']:.2f} %")
    print(f"  批量 vs 在线 gap = {s['gap_vs_score']:.2f} %")
    print(f"  重货平均层高     = {s['heavy_tier']:.3f}")
    print(f"  违规Σ(awra)      = {s['viol']}")
    print()

H = res["H 报告头条口径 (加减速+自适应权重)"]
P = res["P PLC 实际口径 (加减速+静态默认权重)"]
print("=" * 60)
print("★ D-2 影响 = H(报告口径) vs P(PLC实际口径), 只切权重一个变量:")
print(f"  awra 取货时间 : 报告 {H['awra_exp']:.3f}s → PLC {P['awra_exp']:.3f}s "
      f"(Δ {P['awra_exp']-H['awra_exp']:+.3f}s, {(P['awra_exp']/H['awra_exp']-1)*100:+.2f}%)")
print(f"  较 seq 降幅   : 报告 {H['drop_vs_seq']:.2f}% → PLC {P['drop_vs_seq']:.2f}% "
      f"(Δ {P['drop_vs_seq']-H['drop_vs_seq']:+.2f} pp)")
print(f"  能耗降幅      : 报告 {H['ene_drop_vs_seq']:.2f}% → PLC {P['ene_drop_vs_seq']:.2f}% "
      f"(Δ {P['ene_drop_vs_seq']-H['ene_drop_vs_seq']:+.2f} pp)")
print(f"  重货平均层高  : 报告 {H['heavy_tier']:.3f} → PLC {P['heavy_tier']:.3f} "
      f"(Δ {P['heavy_tier']-H['heavy_tier']:+.3f})")
print(f"  批量vs在线gap : 报告 {H['gap_vs_score']:.2f}% → PLC {P['gap_vs_score']:.2f}%")
