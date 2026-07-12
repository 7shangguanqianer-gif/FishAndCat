# -*- coding: utf-8 -*-
"""
final_test_30seed.py — U3 合规的 30-seed untouched final test（0712 overnight T2）
目的:修 N5-17——headline 8.40±0.48s 是 5-seed 回归锚(标定集∪历史 holdout,被"碰过"),
     违项目自定 U3 统计纪律;本脚本用 30 个从未参与任何开发/调参/标定的新 seed
     做一次性 final test,给报告提供泛化证据。
seed 选择规则(显式声明,防"挑好看"质疑):SEEDS_FINAL = range(10001,10031) 连续区间,
     与开发用 seed(2026/7/42/123/999 及 gen_goods 内部任何历史使用)无交集;
     选定后不重跑不筛选,负结果如实报告(U3 精神)。
口径:完全复用 headline.run_five(H=加减速+自适应 / 对照=匀速+固定默认),
     场景同 headline(120件/skew/sum)——只换 seed 集,零新口径。
运行:python final_test_30seed.py (~12 分钟) → out/final_test_30seed.csv + 报告句
"""
import csv
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
import headline as hl

HERE = os.path.dirname(os.path.abspath(__file__))
SEEDS_FINAL = list(range(10001, 10031))   # 30 个 untouched seed,连续区间规则
STRATS = hl.STRATS


def caliber(accel, adaptive, seeds):
    ws.ACCEL = accel
    agg = {s: {"exp": [], "hot": [], "ene": [], "ht": [], "viol": 0,
               "fail": 0} for s in STRATS}
    per_seed_drop = []                     # AWRA vs seq 每 seed 降幅(仅 H 口径关心)
    for sd in seeds:
        goods = ws.gen_goods(120, sd)
        res = hl.run_five(goods, sd, adaptive)
        for s in STRATS:
            agg[s]["exp"].append(res[s]["exp_t"])
            agg[s]["hot"].append(res[s]["hot_t"])
            agg[s]["ene"].append(res[s]["energy"])
            agg[s]["ht"].append(res[s]["heavy_tier"])
            agg[s]["viol"] += res[s]["viol"]
            agg[s]["fail"] += res[s]["fail"]
        per_seed_drop.append(
            (1 - res["awra"]["exp_t"] / res["seq"]["exp_t"]) * 100)
    ws.ACCEL = False
    return agg, per_seed_drop


def main():
    t0 = time.time()
    n = len(SEEDS_FINAL)
    print(f"30-seed untouched final test(U3):seeds={SEEDS_FINAL[0]}..{SEEDS_FINAL[-1]}"
          f"(连续区间,与开发 seed 零交集),120件/skew/sum")
    H, drops = caliber(accel=True, adaptive=True, seeds=SEEDS_FINAL)
    L, _ = caliber(accel=False, adaptive=False, seeds=SEEDS_FINAL)

    tcrit = 2.045                          # t(0.975, df=29)
    rows = []
    print(f"\n{'策略':<8}{'H:exp_t均±sample SD':>22}{'95%CI半宽':>10}"
          f"{'H:能耗':>9}{'H:重货层':>8}{'对照:exp_t':>11}{'违规Σ':>6}")
    for s in STRATS:
        he = st.mean(H[s]["exp"])
        hs = st.stdev(H[s]["exp"])
        ci = tcrit * hs / (n ** 0.5)
        le = st.mean(L[s]["exp"])
        print(f"{s:<8}{he:>11.2f}±{hs:<4.2f}{ci:>10.3f}"
              f"{st.mean(H[s]['ene']):>9.0f}{st.mean(H[s]['ht']):>8.2f}"
              f"{le:>11.2f}{H[s]['viol'] + L[s]['viol']:>6}")
        rows.append(dict(strategy=s,
                         H_exp_mean=round(he, 3), H_exp_std=round(hs, 3),
                         H_exp_ci95_half=round(ci, 3),
                         H_hot_mean=round(st.mean(H[s]["hot"]), 3),
                         H_energy_mean=round(st.mean(H[s]["ene"]), 1),
                         H_heavy_tier=round(st.mean(H[s]["ht"]), 3),
                         legacy_exp_mean=round(le, 3),
                         seed_count=n, seed_rule="10001..10030_contiguous_untouched",
                         H_dispersion="sample_sd",
                         evidence_scope="30seed_untouched_final_test_U3",
                         fail_sum=H[s]["fail"] + L[s]["fail"],
                         viol_sum=H[s]["viol"] + L[s]["viol"]))

    e = lambda s, k="exp": st.mean(H[s][k])
    drop = (1 - e("awra") / e("seq")) * 100
    ene_drop = (1 - e("awra", "ene") / e("seq", "ene")) * 100
    print(f"\n★30-seed final test 报告句(数字来源=本脚本,seed 规则见文件头):")
    print(f"  AWRA-LS 期望取货 {e('awra'):.2f}±{st.stdev(H['awra']['exp']):.2f}s"
          f"(sample SD,n=30),较顺序基线({e('seq'):.2f}s)降 {drop:.1f}%;"
          f"能耗降 {ene_drop:.1f}%;重货均层 {st.mean(H['awra']['ht']):.2f}")
    print(f"  per-seed 降幅分布:min {min(drops):.1f}% / 中位 {st.median(drops):.1f}%"
          f" / max {max(drops):.1f}%(30/30 seed 全为正收益: {all(d > 0 for d in drops)})")
    print(f"  违规全口径合计 {sum(r['viol_sum'] for r in rows)}(必须0);"
          f"失败合计 {sum(r['fail_sum'] for r in rows)}(必须0)")
    print(f"  对照口径 awra {st.mean(L['awra']['exp']):.2f}s,"
          f"降 {(1 - st.mean(L['awra']['exp']) / st.mean(L['seq']['exp'])) * 100:.1f}%")

    os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
    path = os.path.join(HERE, "out", "final_test_30seed.csv")
    with open(path, "w", newline="", encoding="utf-8-sig") as fp:
        w = csv.DictWriter(fp, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    # per-seed 明细一并落盘(可复现审计)
    path2 = os.path.join(HERE, "out", "final_test_30seed_per_seed.csv")
    with open(path2, "w", newline="", encoding="utf-8-sig") as fp:
        w = csv.writer(fp)
        w.writerow(["seed", "awra_exp_H", "seq_exp_H", "drop_pct"])
        for i, sd in enumerate(SEEDS_FINAL):
            w.writerow([sd, round(H["awra"]["exp"][i], 3),
                        round(H["seq"]["exp"][i], 3), round(drops[i], 2)])
    print(f"\nCSV:{path}\nCSV(per-seed):{path2}")
    print(f"耗时 {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
