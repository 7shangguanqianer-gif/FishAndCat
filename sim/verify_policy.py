# -*- coding: utf-8 -*-
"""
verify_policy.py — 自适应权重策略表的泛化验证(采纳前置,拍板①的证据)
方法:用**未参与标定**的 seeds(42/123/999)在代表性场景上复验
     "策略表权重 vs 固定默认(δ0.15/β+γ1.0)"的增益方向与幅度。
判定:批量模式全部场景增益>0 且均值不低于标定值的一半 → 通过,可切主口径。
运行:python verify_policy.py(~2 分钟)
"""
import os
import statistics as st
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import warehouse_sim as ws

SEEDS_HOLDOUT = [42, 123, 999]                 # 标定用的是 2026/7,这三个是留出
# 策略表(来源:adaptive_weights.py 2026-07-04,out/weight_policy_table.csv)
POLICY = {  # (density, case, mode) -> (delta, beta+gamma)
    (120, "uniform", "online"): (0.20, 0.6), (120, "uniform", "batch"): (0.15, 0.6),
    (120, "skew", "online"): (0.10, 1.0),    (120, "skew", "batch"): (0.05, 0.6),
    (120, "heavy", "online"): (0.10, 0.6),   (120, "heavy", "batch"): (0.10, 0.6),
    (240, "uniform", "online"): (0.20, 0.6), (240, "uniform", "batch"): (0.15, 0.6),
    (240, "skew", "online"): (0.20, 0.6),    (240, "skew", "batch"): (0.05, 0.6),
    (240, "heavy", "online"): (0.20, 0.6),   (240, "heavy", "batch"): (0.15, 0.6),
    (330, "uniform", "online"): (0.20, 0.6), (330, "uniform", "batch"): (0.20, 0.6),
    (330, "skew", "online"): (0.20, 0.6),    (330, "skew", "batch"): (0.05, 0.6),
    (330, "heavy", "online"): (0.20, 0.6),   (330, "heavy", "batch"): (0.20, 0.6),
}
DEFAULT = (0.15, 1.0)
SCENES = [(120, "skew"), (120, "heavy"), (240, "skew"), (330, "skew")]  # 代表性抽样


def run(goods, mode, dw, w_max, f_max):
    delta, bg = dw
    fn = ws.make_score_fn(1.0, bg / 2, bg / 2, delta, w_max, f_max)
    if mode == "online":
        wh, placed, failed = ws.run_online(ws.strat_score, goods, "and", fn)
    else:
        wh, placed, failed = ws.run_awra_ls(goods, "and", fn, w_max, f_max)
    m = ws.metrics(wh, placed, failed)
    return m["exp_t"], m["viol"]


def main():
    print(f"泛化验证:留出 seeds {SEEDS_HOLDOUT} × 场景 {SCENES} × 2 模式")
    print(f"{'场景':<14}{'模式':<8}{'默认exp_t':>10}{'查表exp_t':>10}{'增益':>8}")
    gains = {"online": [], "batch": []}
    all_viol = 0
    for dens, case in SCENES:
        for mode in ("online", "batch"):
            e_def, e_pol = [], []
            for sd in SEEDS_HOLDOUT:
                goods = ws.gen_goods(dens, sd, case)
                w_max = max(g.weight for g in goods)
                f_max = max(g.freq for g in goods)
                a, v1 = run(goods, mode, DEFAULT, w_max, f_max)
                b, v2 = run(goods, mode, POLICY[(dens, case, mode)], w_max, f_max)
                e_def.append(a)
                e_pol.append(b)
                all_viol += v1 + v2
            g = (1 - st.mean(e_pol) / st.mean(e_def)) * 100
            gains[mode].append(g)
            print(f"{dens}/{case:<9}{mode:<8}{st.mean(e_def):>10.3f}"
                  f"{st.mean(e_pol):>10.3f}{g:>7.1f}%")
    b_ok = all(g > 0 for g in gains["batch"])
    print(f"\n批量模式留出增益:均值 {st.mean(gains['batch']):.2f}%"
          f"(标定值口径 3-8.5%),全部>0:{b_ok}")
    print(f"在线模式留出增益:均值 {st.mean(gains['online']):.2f}%")
    print(f"违规总数:{all_viol}(必须0)")
    verdict = b_ok and all_viol == 0 and st.mean(gains["batch"]) > 1.5
    print(f"\n判定:{'✅ 通过——策略表泛化成立,可切主口径' if verdict else '❌ 未通过——回报用户,不切'}")


if __name__ == "__main__":
    main()
