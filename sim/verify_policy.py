# -*- coding: utf-8 -*-
"""
verify_policy.py — sim场景权重表的有限留出复核（非独立final、非U3泛化）
方法:用已参与历史验收、但未参与两 seed 标定的 seeds(42/123/999)在代表性场景上复验
     "策略表权重 vs 固定默认(δ0.15/β+γ1.0)"的增益方向与幅度。
判定:仅对标定为 FEASIBLE 的行验证 failed=0/viol=0；INFEASIBLE 行明确拒绝泛化判定。
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

SEEDS_HOLDOUT = [42, 123, 999]  # 有限留出；不是未触碰final test，也不满足U3 30-seed
# 策略表(来源:adaptive_weights.py 2026-07-04,out/weight_policy_table.csv)
POLICY = {  # (density, case, mode) -> (delta, beta+gamma)  0706 sum口径重标
    (120, "uniform", "online"): (0.20, 0.6), (120, "uniform", "batch"): (0.15, 0.6),
    (120, "skew", "online"): (0.10, 1.0),    (120, "skew", "batch"): (0.05, 0.6),
    (120, "heavy", "online"): (0.10, 0.6),   (120, "heavy", "batch"): (0.10, 0.6),
    (200, "uniform", "online"): (0.20, 0.6), (200, "uniform", "batch"): (0.20, 0.6),
    (200, "skew", "online"): (0.15, 0.6),    (200, "skew", "batch"): (0.05, 0.6),
    (200, "heavy", "online"): (0.20, 0.6),   (200, "heavy", "batch"): (0.10, 0.6),
    (240, "uniform", "online"): (0.20, 0.6), (240, "uniform", "batch"): (0.20, 0.6),
    (240, "skew", "online"): (0.20, 0.6),    (240, "skew", "batch"): (0.05, 0.6),
    (240, "heavy", "online"): (0.20, 0.6),   (240, "heavy", "batch"): (0.15, 0.6),
}
INFEASIBLE = {
    (dens, case, "online")
    for dens in (200, 240) for case in ("uniform", "skew", "heavy")
}
DEFAULT = (0.15, 1.0)
SCENES = [(120, "skew"), (120, "heavy"), (200, "skew"), (240, "skew")]  # 代表性抽样(0706 新档)


def run(goods, mode, dw, w_max, f_max):
    delta, bg = dw
    fn = ws.make_score_fn(1.0, bg / 2, bg / 2, delta, w_max, f_max)
    if mode == "online":
        wh, placed, failed = ws.run_online(ws.strat_score, goods, "sum", fn)
    else:
        wh, placed, failed = ws.run_awra_ls(goods, "sum", fn, w_max, f_max)
    m = ws.metrics(wh, placed, failed)
    return {"exp_t": m["exp_t"], "viol": m["viol"], "fail": m["fail"]}


def main():
    print(f"泛化验证:留出 seeds {SEEDS_HOLDOUT} × 场景 {SCENES} × 2 模式")
    print(f"{'场景':<14}{'模式':<8}{'默认exp_t':>10}{'查表exp_t':>10}{'增益':>8}")
    gains = {"online": [], "batch": []}
    all_viol = all_fail = 0
    infeasible_seen = []
    for dens, case in SCENES:
        for mode in ("online", "batch"):
            key = (dens, case, mode)
            if key in INFEASIBLE:
                infeasible_seen.append(key)
                print(f"{dens}/{case:<9}{mode:<8}{'INFEASIBLE':>28}"
                      "(标定网格无零失败候选,不做 exp_t 泛化判定)")
                continue
            e_def, e_pol = [], []
            for sd in SEEDS_HOLDOUT:
                goods = ws.gen_goods(dens, sd, case)
                w_max = max(g.weight for g in goods)
                f_max = max(g.freq for g in goods)
                a = run(goods, mode, DEFAULT, w_max, f_max)
                b = run(goods, mode, POLICY[key], w_max, f_max)
                e_def.append(a["exp_t"])
                e_pol.append(b["exp_t"])
                all_viol += a["viol"] + b["viol"]
                all_fail += a["fail"] + b["fail"]
            g = (1 - st.mean(e_pol) / st.mean(e_def)) * 100
            gains[mode].append(g)
            print(f"{dens}/{case:<9}{mode:<8}{st.mean(e_def):>10.3f}"
                  f"{st.mean(e_pol):>10.3f}{g:>7.1f}%")
    b_ok = all(g > 0 for g in gains["batch"])
    print(f"\n批量模式留出增益:均值 {st.mean(gains['batch']):.2f}%"
          f"(标定值口径 3-8.5%),全部>0:{b_ok}")
    print(f"在线模式留出增益:均值 {st.mean(gains['online']):.2f}%")
    print(f"违规总数:{all_viol}(必须0);失败总数:{all_fail}(有效行必须0)")
    print("不可行行:" + (", ".join(f"{d}/{c}/{m}" for d, c, m in infeasible_seen)
                          if infeasible_seen else "无"))
    verdict = b_ok and all_viol == 0 and all_fail == 0 and st.mean(gains["batch"]) > 1.5
    print(f"\n判定:{'✅ 批量可行行验证通过；在线高密度保持 INFEASIBLE' if verdict else '❌ 未通过——回报用户,不切'}")


if __name__ == "__main__":
    main()
