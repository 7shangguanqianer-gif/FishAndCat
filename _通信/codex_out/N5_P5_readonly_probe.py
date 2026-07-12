# -*- coding: utf-8 -*-
"""N5-P5 read-only statistical probe. Prints JSON only."""
from __future__ import annotations

import itertools
import json
import math
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SIM = ROOT / "sim"
sys.path.insert(0, str(SIM))

import adaptive_weights as aw  # noqa: E402
import headline as hl  # noqa: E402
import warehouse_sim as ws  # noqa: E402

T95_DF4 = 2.776


def summary(values):
    mean = st.mean(values)
    sd = st.stdev(values)
    half = T95_DF4 * sd / math.sqrt(len(values))
    return {"values": values, "mean": mean, "sample_sd": sd,
            "ci95_halfwidth": half, "ci95": [mean - half, mean + half]}


def main_scene_tuning_instability():
    records = {mode: {} for mode in aw.MODES}
    seed_best = {mode: {} for mode in aw.MODES}
    aggregate_best = {}
    for mode in aw.MODES:
        for seed in aw.SEEDS:
            goods = ws.gen_goods(120, seed, "skew")
            wm, fm = max(g.weight for g in goods), max(g.freq for g in goods)
            vals = []
            for delta, bg in itertools.product(aw.DELTAS, aw.BGS):
                m = aw.run_one(goods, mode, delta, bg, wm, fm)
                row = {"delta": delta, "bg": bg, "exp": m["exp_t"],
                       "energy": m["energy"], "fail": m["fail"], "viol": m["viol"]}
                vals.append(row)
                records[mode].setdefault((delta, bg), []).append(row)
            best = min((r for r in vals if r["viol"] == 0),
                       key=lambda r: (r["exp"], r["energy"]))
            seed_best[mode][str(seed)] = best
        aggregate = []
        for (delta, bg), vals in records[mode].items():
            aggregate.append({
                "delta": delta,
                "bg": bg,
                "exp_mean": st.mean(r["exp"] for r in vals),
                "energy_mean": st.mean(r["energy"] for r in vals),
                "fail_sum": sum(r["fail"] for r in vals),
                "viol_sum": sum(r["viol"] for r in vals),
            })
        aggregate_best[mode] = min(
            (r for r in aggregate if r["viol_sum"] == 0),
            key=lambda r: (r["exp_mean"], r["energy_mean"]),
        )
    return {"scene": [120, "skew"], "candidates_per_mode": len(aw.DELTAS) * len(aw.BGS),
            "seed_best": seed_best, "two_seed_best": aggregate_best}


def main():
    H = hl.caliber(accel=True, adaptive=True)
    awra = H["awra"]["exp"]
    seq = H["seq"]["exp"]
    paired_abs = [s - a for s, a in zip(seq, awra)]
    paired_pct = [(1 - a / s) * 100 for s, a in zip(seq, awra)]
    loo = []
    for i, seed in enumerate(hl.SEEDS):
        aa = [v for j, v in enumerate(awra) if j != i]
        ss = [v for j, v in enumerate(seq) if j != i]
        loo.append({"omitted_seed": seed, "awra_mean": st.mean(aa),
                    "drop_pct_ratio_of_means": (1 - st.mean(aa) / st.mean(ss)) * 100})

    result = {
        "seed_provenance": {
            "calibration": aw.SEEDS,
            "declared_holdout": [42, 123, 999],
            "headline": hl.SEEDS,
            "headline_is_union_of_calibration_and_holdout":
                set(hl.SEEDS) == set(aw.SEEDS) | {42, 123, 999},
            "untouched_final_test_seeds": sorted(set(hl.SEEDS) -
                                                 (set(aw.SEEDS) | {42, 123, 999})),
        },
        "headline_H": {
            "awra_exp": summary(awra),
            "seq_exp": summary(seq),
            "paired_seq_minus_awra": summary(paired_abs),
            "paired_drop_pct": summary(paired_pct),
            "leave_one_out": loo,
            "loo_awra_mean_range": [min(r["awra_mean"] for r in loo),
                                     max(r["awra_mean"] for r in loo)],
            "loo_drop_pct_range": [min(r["drop_pct_ratio_of_means"] for r in loo),
                                    max(r["drop_pct_ratio_of_means"] for r in loo)],
        },
        "main_scene_tuning": main_scene_tuning_instability(),
    }
    ws.ACCEL = False
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
