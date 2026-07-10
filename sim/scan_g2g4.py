# -*- coding: utf-8 -*-
"""
scan_g2g4.py — G2/G3/G4 情景参数敏感性扫描(0710 夜;深思清单第 1 条落地)
目的:把 canonical G2(到达强度)/G3(频次噪声)/G4(故障画像)从"情景假设-显式声明"
升到与 G1(装卸)同级的"扫描稳健"证据等级——红队问"ρ=0.75 换 0.6 呢"时有实测答案。

设计(与 G1 三点扫描同构,OFAT:一次只动一个参数,其余保持 canonical 基准):
  G2 到达强度:  (ρ峰,ρ谷) ∈ {(0.60,0.28), (0.75,0.35)*, (0.90,0.42)}(峰谷比 7/15 保持)
  G3 频次噪声:  σ ∈ {0.15, 0.30*, 0.45}(±16%/±35%/±57% 一倍标准差)
  G4 故障画像:  MTBF ∈ {1500, 3000*, 6000} s(MTTR 固定 600:扫使用强度,不扫维修组织)
  (* = canonical 基准点,七个配置点共用同一基准跑一次)
复用纪律:零改动 realism.py——run_tier3 引擎原样 import,扫描参数经模块属性注入
(HANDLE_S/RHO_PEAK/RHO_OFF/FREQ_SIGMA/MTBF_S/MTTR_S 均为 run_tier3 引用的模块全局)。
统计纪律:30 seed(2026..2055),CRN——同 seed 下各参数点共享同一负载(货物/请求由
seed 决定,参数只改拟真层);排序保持率按 seed 逐一判定后聚合。
口径:档3 专属(泊松+装卸+噪声+故障);不动主口径 H,不进回归门(与 realism.py 同例)。
运行:python scan_g2g4.py            → out/scan_g2g4.csv + out/scan_g2g4_agg.csv
     python scan_g2g4.py --smoke    → 单 seed 七点冒烟(约 1 分钟)
     python scan_g2g4.py --seeds N  → 自定 seed 数
"""
import argparse
import csv
import os
import sys
from concurrent.futures import ProcessPoolExecutor

# 统计协议同 dwell_point/instance_gen(Law 2015):配对 t + 95%CI
from instance_gen import paired_t

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

N_INIT, CYCLES = 120, 100
SEED0, N_SEEDS = 2026, 30
STRATS = ["seq", "near", "score", "awra"]

# 七个配置点:(组名, 点标签, 覆盖字典);base 同时是三组的中点
BASE = dict(RHO_PEAK=0.75, RHO_OFF=0.35, FREQ_SIGMA=0.30, MTBF_S=3000.0,
            MTTR_S=600.0, HANDLE_S=15.0)
POINTS = [
    ("base", "canonical", {}),
    ("G2_rho", "low_0.60", dict(RHO_PEAK=0.60, RHO_OFF=0.28)),
    ("G2_rho", "high_0.90", dict(RHO_PEAK=0.90, RHO_OFF=0.42)),
    ("G3_sigma", "low_0.15", dict(FREQ_SIGMA=0.15)),
    ("G3_sigma", "high_0.45", dict(FREQ_SIGMA=0.45)),
    ("G4_mtbf", "harsh_1500", dict(MTBF_S=1500.0)),
    ("G4_mtbf", "mild_6000", dict(MTBF_S=6000.0)),
]


def run_point(args):
    """子进程 worker:一个 (配置点, seed) 跑四策略。
    Windows spawn 下每个进程干净 import,参数注入进程内自洽。"""
    label, overrides, seed = args
    import warehouse_sim as ws
    import realism as rl
    from mixed_ops import build_workload

    for k, v in BASE.items():
        setattr(rl, k, v)
    for k, v in overrides.items():
        setattr(rl, k, v)

    goods = ws.gen_goods(N_INIT, seed)
    new_goods, requests = build_workload(goods, CYCLES, seed)
    w_max = max(g.weight for g in goods)
    f_max = max(g.freq for g in goods)
    ws.ACCEL = True                       # 档3 = 档2 物理口径之上叠拟真(同 realism.tier3)
    d_on, bg_on = ws.lookup_weights(N_INIT, "skew", "online")
    d_ba, bg_ba = ws.lookup_weights(N_INIT, "skew", "batch")
    fn = ws.make_score_fn(1.0, bg_on / 2, bg_on / 2, d_on, w_max, f_max)
    fnb = ws.make_score_fn(1.0, bg_ba / 2, bg_ba / 2, d_ba, w_max, f_max)

    rows = []
    for s in STRATS:
        m = rl.run_tier3(s, goods, new_goods, requests, fn, w_max, f_max, fnb,
                         cycles=CYCLES, seed=seed)
        rows.append(dict(label=label, seed=seed, strategy=s,
                         avg_retr=m["avg_retr"], resp_p50=m["resp_p50"],
                         resp_p95=m["resp_p95"], util=m["util"],
                         n_down=m["n_down"], fails=m["fails"], viol=m["viol"]))
    return rows


def mean(v):
    return sum(v) / len(v) if v else 0.0


def std(v):
    if len(v) < 2:
        return 0.0
    m = mean(v)
    return (sum((x - m) ** 2 for x in v) / (len(v) - 1)) ** 0.5


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=N_SEEDS)
    ap.add_argument("--smoke", action="store_true", help="单 seed 七点冒烟")
    a = ap.parse_args()
    seeds = [SEED0] if a.smoke else list(range(SEED0, SEED0 + a.seeds))

    jobs = [(f"{g}:{p}", ov, sd) for (g, p, ov) in POINTS for sd in seeds]
    print(f"G2-G4 扫描:{len(POINTS)} 配置点 × {len(seeds)} seeds × 4 策略 "
          f"= {len(jobs) * 4} 次档3混合流({CYCLES} 周期)")

    results = []
    workers = 1 if a.smoke else max(2, (os.cpu_count() or 4) - 2)
    if workers == 1:
        for j in jobs:
            results.extend(run_point(j))
    else:
        with ProcessPoolExecutor(max_workers=workers) as ex:
            done = 0
            for rows in ex.map(run_point, jobs, chunksize=1):
                results.extend(rows)
                done += 1
                if done % 20 == 0:
                    print(f"  进度 {done}/{len(jobs)}")

    os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
    raw_path = os.path.join(HERE, "out", "scan_g2g4.csv")
    with open(raw_path, "w", newline="", encoding="utf-8-sig") as fp:
        w = csv.DictWriter(fp, fieldnames=list(results[0].keys()))
        w.writeheader()
        w.writerows(results)

    # ---- 聚合 + 排序保持率(按 seed 逐判) ----
    by = {}
    for r in results:
        by.setdefault((r["label"], r["strategy"]), []).append(r)
    labels = [f"{g}:{p}" for (g, p, _) in POINTS]

    def col(lb, s, k):
        d = {x["seed"]: x[k] for x in by[(lb, s)]}
        return [d[sd] for sd in seeds]                # seed 对齐(配对前提)

    keep_rows = []
    print(f"\n{'配置点':<18}{'awra出库s':>10}{'seq出库s':>10}{'降幅%':>7}"
          f"{'awraP95s':>10}{'联合保序':>9}{'awra<seq出库':>12}{'awra<seq P50':>12}{'违规Σ':>7}")
    for lb in labels:
        per_seed_ok_r = []
        for sd in seeds:
            vals_r = {s: next(x["avg_retr"] for x in by[(lb, s)]
                              if x["seed"] == sd) for s in STRATS}
            per_seed_ok_r.append(vals_r["awra"] == min(vals_r.values())
                                 and vals_r["seq"] == max(vals_r.values()))
        aw, sq = col(lb, "awra", "avg_retr"), col(lb, "seq", "avg_retr")
        awp, sqp = col(lb, "awra", "resp_p50"), col(lb, "seq", "resp_p50")
        aw95, sq95 = col(lb, "awra", "resp_p95"), col(lb, "seq", "resp_p95")
        viol = sum(x["viol"] for s in STRATS for x in by[(lb, s)])
        drop = (1 - mean(aw) / mean(sq)) * 100
        kr = sum(per_seed_ok_r) / len(seeds) * 100
        # 成对口径(红队问法):awra 优于 seq 的 seed 占比 + 配对差 CI/t
        pw_r = sum(a < b for a, b in zip(aw, sq)) / len(seeds) * 100
        pw_p = sum(a < b for a, b in zip(awp, sqp)) / len(seeds) * 100
        pw_95 = sum(a < b for a, b in zip(aw95, sq95)) / len(seeds) * 100
        _dm, (lo, hi), t_stat, sig, _p = paired_t(aw, sq)
        print(f"{lb:<18}{mean(aw):>10.2f}{mean(sq):>10.2f}{drop:>7.1f}"
              f"{mean(aw95):>10.0f}{kr:>8.0f}%{pw_r:>11.0f}%{pw_p:>11.0f}%{viol:>7}")
        keep_rows.append(dict(label=lb, awra_avg_retr=round(mean(aw), 3),
                              awra_std=round(std(aw), 3),
                              seq_avg_retr=round(mean(sq), 3),
                              drop_pct=round(drop, 2),
                              diff_ci95=f"{lo:.2f}..{hi:.2f}",
                              paired_t=round(t_stat, 2), sig05=sig,
                              awra_p95=round(mean(aw95), 1),
                              seq_p95=round(mean(sq95), 1),
                              keep_rate_joint_pct=round(kr, 1),
                              pair_rate_retr_pct=round(pw_r, 1),
                              pair_rate_p50_pct=round(pw_p, 1),
                              pair_rate_p95_pct=round(pw_95, 1), viol_sum=viol,
                              seeds=len(seeds)))

    agg_path = os.path.join(HERE, "out", "scan_g2g4_agg.csv")
    with open(agg_path, "w", newline="", encoding="utf-8-sig") as fp:
        w = csv.DictWriter(fp, fieldnames=list(keep_rows[0].keys()))
        w.writeheader()
        w.writerows(keep_rows)
        w.writerow({})
    with open(agg_path, "a", newline="", encoding="utf-8-sig") as fp:
        w = csv.writer(fp)
        w.writerow(["param", "value"])
        for k, v in BASE.items():
            w.writerow([k, v])
        w.writerow(["cycles", CYCLES])
        w.writerow(["seeds", f"{seeds[0]}..{seeds[-1]}"])

    print(f"\n输出:{raw_path} + {agg_path}")


if __name__ == "__main__":
    main()
