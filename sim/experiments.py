# -*- coding: utf-8 -*-
"""
experiments.py — 多 seed × 多分布 × 多场景实验矩阵(验证报告的数据引擎)
运行:python experiments.py            → 输出 sim/out/experiments_detail.csv + _agg.csv
矩阵:5 seeds × 3 货物分布 × H 设计口径主场景(sum+梯形加减速+自适应,120件)
     + 历史紧库存压力场景(or+匀速+固定,150件,3 seeds)——F3 证据保留。
口径:全部指标沿 canonical C1-C8;随机全部按 seed 播种(B5)。
"""
import csv
import os
import statistics as st
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import warehouse_sim as ws

SEEDS = [2026, 7, 42, 123, 999]
CASES = ["uniform", "skew", "heavy"]
STRATS = ["random", "seq", "near", "score", "awra"]
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")


def run_matrix(goods, rule, seed, case="skew", accel=False, adaptive=False):
    """跑五策略,返回 {strat: metrics}(与 warehouse_sim.main 同逻辑)。"""
    import random as _r
    w_max = max(g.weight for g in goods)
    f_max = max(g.freq for g in goods)
    ws.ACCEL = accel
    if adaptive:
        d_on, bg_on = ws.lookup_weights(len(goods), case, "online")
        d_ba, bg_ba = ws.lookup_weights(len(goods), case, "batch")
        fn = ws.make_score_fn(1.0, bg_on / 2, bg_on / 2, d_on, w_max, f_max)
        fn_batch = ws.make_score_fn(1.0, bg_ba / 2, bg_ba / 2, d_ba, w_max, f_max)
    else:
        fn = ws.make_score_fn(1.0, 0.6, 0.4, 0.15, w_max, f_max)
        fn_batch = fn
    res = {}
    for name, strat in [("random", ws.strat_random(_r.Random(seed + 1))),
                        ("seq", ws.strat_seq), ("near", ws.strat_near),
                        ("score", ws.strat_score)]:
        wh, placed, failed = ws.run_online(strat, goods, rule, fn)
        res[name] = ws.metrics(wh, placed, failed)
    wh, placed, failed = ws.run_awra_ls(goods, rule, fn_batch, w_max, f_max)
    res["awra"] = ws.metrics(wh, placed, failed)
    ws.ACCEL = False
    return res


def main():
    os.makedirs(OUT, exist_ok=True)
    rows = []
    # ---- H 设计主场景:sum / 梯形加减速 / 自适应 / 120件 / 3分布 / 5seeds ----
    for case in CASES:
        for seed in SEEDS:
            goods = ws.gen_goods(120, seed, case)
            for s, m in run_matrix(goods, "sum", seed, case,
                                   accel=True, adaptive=True).items():
                rows.append(dict(scene="main", case=case, rule="sum", goods=120,
                                 motion="trapezoid", weights="adaptive",
                                 seed=seed, strat=s, **m))
    # ---- 紧库存场景:or / 150件(F3 统计版) ----
    for seed in SEEDS[:3]:
        goods = ws.gen_goods(150, seed, "skew")
        for s, m in run_matrix(goods, "or", seed, "skew",
                               accel=False, adaptive=False).items():
            rows.append(dict(scene="tight", case="skew", rule="or", goods=150,
                             motion="constant_speed", weights="fixed",
                             seed=seed, strat=s, **m))

    keys = ["scene", "case", "rule", "goods", "motion", "weights",
            "seed", "strat", "n", "fail",
            "tot_time2", "exp_t", "hot_t", "heavy_tier", "energy", "cog",
            "path", "util", "viol"]
    with open(os.path.join(OUT, "experiments_detail.csv"), "w", newline="",
              encoding="utf-8-sig") as fp:
        w = csv.DictWriter(fp, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow({k: (round(r[k], 4) if isinstance(r[k], float) else r[k])
                        for k in keys})

    # ---- 聚合:场景×分布×策略 → mean±std ----
    agg_rows = []
    print(f"{'场景':<6}{'分布':<9}{'策略':<8}{'期望取货s(均±σ)':<20}{'能耗kg·m(均)':<14}"
          f"{'失败(均)':<9}{'违规Σ':<6}")
    print("-" * 66)
    for scene in ("main", "tight"):
        for case in (CASES if scene == "main" else ["skew"]):
            for s in STRATS:
                sel = [r for r in rows if r["scene"] == scene
                       and r["case"] == case and r["strat"] == s]
                if not sel:
                    continue
                et = [r["exp_t"] for r in sel]
                en = [r["energy"] for r in sel]
                fl = [r["fail"] for r in sel]
                vi = sum(r["viol"] for r in sel)
                mean_et = st.mean(et)
                sd_et = st.stdev(et) if len(et) > 1 else 0.0
                agg_rows.append(dict(scene=scene, case=case, strat=s,
                                     rule=sel[0]["rule"], motion=sel[0]["motion"],
                                     weights=sel[0]["weights"],
                                     exp_t_mean=round(mean_et, 3),
                                     exp_t_std=round(sd_et, 3),
                                     hot_t_mean=round(st.mean([r["hot_t"] for r in sel]), 3),
                                     heavy_tier_mean=round(st.mean([r["heavy_tier"] for r in sel]), 3),
                                     energy_mean=round(st.mean(en), 1),
                                     cog_mean=round(st.mean([r["cog"] for r in sel]), 3),
                                     fail_mean=round(st.mean(fl), 2),
                                     viol_sum=vi, n_runs=len(sel)))
                print(f"{scene:<6}{case:<9}{s:<8}{mean_et:>8.2f} ± {sd_et:<7.2f}"
                      f"{st.mean(en):>12.0f}  {st.mean(fl):>6.2f}  {vi:>4}")

    with open(os.path.join(OUT, "experiments_agg.csv"), "w", newline="",
              encoding="utf-8-sig") as fp:
        w = csv.DictWriter(fp, fieldnames=list(agg_rows[0].keys()))
        w.writeheader()
        w.writerows(agg_rows)

    # ---- 结论行(报告引用格式) ----
    def g(scene, case, s, k):
        return next(r for r in agg_rows if r["scene"] == scene
                    and r["case"] == case and r["strat"] == s)[k]
    imp = (1 - g("main", "skew", "awra", "exp_t_mean") / g("main", "skew", "seq", "exp_t_mean")) * 100
    ene = (1 - g("main", "skew", "awra", "energy_mean") / g("main", "skew", "seq", "energy_mean")) * 100
    print(f"\n[H设计口径主场景/偏态分布,5-seed回归锚] AWRA-LS vs 题面顺序基线:"
          f"期望取货降 {imp:.1f}%,能耗降 {ene:.1f}%")
    print(f"[紧库存,3 seeds] near 平均失败 {g('tight','skew','near','fail_mean'):.1f} 件,"
          f"awra 平均失败 {g('tight','skew','awra','fail_mean'):.1f} 件")
    print(f"全矩阵违规总数 = {sum(r['viol_sum'] for r in agg_rows)}(必须为 0)")
    print(f"\nCSV:{OUT}\\experiments_detail.csv / experiments_agg.csv")


if __name__ == "__main__":
    main()
