# -*- coding: utf-8 -*-
"""mixed_dispatch_sweep.py — 双命令调度 30 seed 离线原型(M4a,0718 overnight)。

目的:为「双命令调度设计稿」供可复现的 30 seed 统计——双命令(存完顺路取,省一次空驶
回程)相对单命令(两趟独立往返)的节省%,以及布局在出库侧兑现的高频近格红利(出库均时)。

复用 mixed_ops.py 生产函数(build_workload / run_mixed / initial_layout 链),**零改生产**:
每 seed 独立 gen_goods(120)→build_workload(cycles)→对每 lane run_mixed。固定 seed 2026..2055。
四 lane:seq 顺序基线 / near 就近贪心 / score 多目标在线 / awra 批量(初始布局用批量评分)。

用法(项目根):
    PYTHONIOENCODING=utf-8 python sim/mixed_dispatch_sweep.py --seeds 30 --cycles 100
    python sim/mixed_dispatch_sweep.py --seeds 3 --smoke   # 冒烟,不落证据
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import warehouse_sim as ws  # noqa: E402
import mixed_ops as mo  # noqa: E402

LANES = ("seq", "near", "score", "awra")
SCHEMA = "s3-mixed-dispatch-sweep-v1"


def run_seed(seed: int, cycles: int) -> dict:
    goods = ws.gen_goods(mo.N_INIT, seed)
    w_max = max(g.weight for g in goods)
    f_max = max(g.freq for g in goods)
    fn = ws.make_score_fn(1.0, 0.6, 0.4, 0.15, w_max, f_max)
    new_goods, requests = mo.build_workload(goods, cycles, seed)
    row = {"seed": seed, "lanes": {}}
    for lane in LANES:
        m = mo.run_mixed(lane, goods, new_goods, requests, fn, w_max, f_max,
                         fn_batch=fn, seed=seed)
        row["lanes"][lane] = {
            "tot_single_s": round(m["tot_single"], 3),
            "tot_dual_s": round(m["tot_dual"], 3),
            "saving_pct": round(m["saving"], 4),
            "avg_retr_s": round(m["avg_retr"], 4),
            "thr_dual_ops_h": round(m["thr_dual"], 3),
            "fails": m["fails"], "viol": m["viol"],
        }
    return row


def summarize(rows: list) -> dict:
    def series(lane, key):
        return [r["lanes"][lane][key] for r in rows]

    def stat(vals):
        return {"mean": round(statistics.fmean(vals), 4),
                "stdev": round(statistics.stdev(vals), 4) if len(vals) > 1 else 0.0}

    per_lane = {}
    for lane in LANES:
        per_lane[lane] = {
            "saving_pct": stat(series(lane, "saving_pct")),
            "avg_retr_s": stat(series(lane, "avg_retr_s")),
            "tot_dual_s": stat(series(lane, "tot_dual_s")),
            "thr_dual_ops_h": stat(series(lane, "thr_dual_ops_h")),
        }
    # awra 布局 vs seq 基线:出库均时降幅逐 seed 配对
    retr_pairwise = sum(1 for r in rows
                        if r["lanes"]["awra"]["avg_retr_s"] < r["lanes"]["seq"]["avg_retr_s"])
    dual_total = sum(series("awra", "tot_dual_s"))
    single_total = sum(series("awra", "tot_single_s"))
    return {
        "per_lane": per_lane,
        "awra_vs_seq_retr_improved": f"{retr_pairwise}/{len(rows)}",
        "awra_dual_vs_single_saving_pooled_pct": round((1 - dual_total / single_total) * 100, 4),
        "fails_all_zero": all(r["lanes"][l]["fails"] == 0 for r in rows for l in LANES),
        "viol_all_zero": all(r["lanes"][l]["viol"] == 0 for r in rows for l in LANES),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=30)
    ap.add_argument("--start", type=int, default=2026)
    ap.add_argument("--cycles", type=int, default=100)
    ap.add_argument("--smoke", action="store_true")
    args = ap.parse_args()
    seeds = list(range(args.start, args.start + args.seeds))
    began = time.time()
    rows = []
    for seed in seeds:
        rows.append(run_seed(seed, args.cycles))
        print(f"  seed {seed} done", flush=True)
    payload = {
        "schema": SCHEMA, "cycles": args.cycles,
        "seeds": {"start": args.start, "count": args.seeds},
        "lanes": {"seq": "顺序基线", "near": "就近贪心", "score": "多目标在线",
                  "awra": "AWRA-LS 批量布局"},
        "dispatch": {"single_command": "两趟独立往返 T=2·t(存)+2·t(取)",
                     "dual_command": "一趟联合行程 T=t(存)+t(存→取)+t(取),省一次空驶回程"},
        "patch_scope": "复用 mixed_ops 生产函数,生产文件零改动",
        "rows": rows, "summary": summarize(rows),
    }
    if args.smoke:
        print(json.dumps(payload["summary"], ensure_ascii=False, indent=1))
    else:
        out_dir = Path(__file__).resolve().parents[1] / "l4_showcase" / "evidence"
        target = out_dir / f"s3_mixed_dispatch_{args.start}_{args.start + args.seeds - 1}.json"
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"  -> {target}", flush=True)
    print(f"total {time.time() - began:.1f}s", flush=True)


if __name__ == "__main__":
    main()
