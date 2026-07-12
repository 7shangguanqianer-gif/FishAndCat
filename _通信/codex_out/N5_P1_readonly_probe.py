# -*- coding: utf-8 -*-
"""N5-P1 read-only probe. Prints JSON only; never writes project artifacts."""
from __future__ import annotations

import json
import math
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SIM = ROOT / "sim"
sys.path.insert(0, str(SIM))

import instance_gen as ig  # noqa: E402
import warehouse_sim as ws  # noqa: E402


def f32(value):
    return struct.unpack("<f", struct.pack("<f", float(value)))[0]


def layout(placed):
    return {g.gid: pos for g, pos in placed}


def layout_diff(a, b):
    keys = set(a) | set(b)
    return sum(a.get(k) != b.get(k) for k in keys)


def strat_near_st_scan(wh, good, score_fn):
    """Mirror FB_SelectSlot near branch: strict time, col-major scan keeps first tie."""
    found = None
    best_t = math.inf
    for col in range(ws.COLS):
        for tier in range(ws.TIERS):
            if not wh.feasible(col, tier, good):
                continue
            travel = ws.travel_time(col, tier)
            if travel < best_t:
                found = (col, tier)
                best_t = travel
    return found


def score_f32_factory(alpha, beta, gamma, delta, w_max, f_max):
    """Conservative REAL proxy: round each named ST temporary/result to IEEE-754 binary32."""
    a, b, c, d = map(f32, (alpha, beta, gamma, delta))
    wm, fm = f32(w_max), f32(f_max)
    hmax = f32(f32(ws.TIERS - 1) * f32(ws.CELL_H))
    # ST FC_TMax currently stays on the uniform formula even if xUseAccel is true.
    tmax = f32(max(f32(f32(ws.COLS - 1) * f32(ws.CELL_W) / f32(ws.VX)),
                   f32(f32(ws.TIERS - 1) * f32(ws.CELL_H) / f32(ws.VY))))

    def score(good, col, tier):
        travel = f32(max(f32(f32(col) * f32(ws.CELL_W) / f32(ws.VX)),
                         f32(f32(tier) * f32(ws.CELL_H) / f32(ws.VY))))
        tnorm = f32(travel / tmax)
        fnorm = f32(f32(good.freq) / fm)
        eff = f32(fnorm * tnorm)
        stab = f32(f32(f32(good.weight) / wm) * f32(f32(tier) / f32(ws.TIERS - 1)))
        energy = f32(f32(f32(f32(good.weight) * f32(tier)) * f32(ws.CELL_H)) /
                     f32(wm * hmax))
        resv = f32(f32(f32(1.0) - fnorm) * f32(f32(1.0) - tnorm))
        left = f32(f32(a * eff) + f32(b * stab))
        right = f32(f32(c * energy) + f32(d * resv))
        return f32(left + right)

    return score


def run_near(goods, strategy):
    ws.ACCEL = False
    wm = max(g.weight for g in goods)
    fm = max(g.freq for g in goods)
    fn = ws.make_score_fn(1.0, 0.6, 0.4, 0.15, wm, fm)
    wh, placed, failed = ws.run_online(strategy, goods, "sum", fn)
    return layout(placed), ws.metrics(wh, placed, failed)


def run_awra(goods, score_fn):
    ws.ACCEL = False
    wm = max(g.weight for g in goods)
    fm = max(g.freq for g in goods)
    wh, placed, failed = ws.run_awra_ls(
        goods, "sum", score_fn, wm, fm, tie_break="st", ls_eps=1e-6
    )
    return layout(placed), ws.metrics(wh, placed, failed)


def priority_order(goods, use_f32):
    wm = max(g.weight for g in goods)
    fm = max(g.freq for g in goods)
    vm = max(g.vol for g in goods)

    def p(g):
        if not use_f32:
            return 0.50 * g.freq / fm + 0.35 * g.weight / wm + 0.15 * g.vol / vm
        p1 = f32(f32(0.50) * f32(f32(g.freq) / f32(fm)))
        p2 = f32(f32(0.35) * f32(f32(g.weight) / f32(wm)))
        p3 = f32(f32(0.15) * f32(f32(g.vol) / f32(vm)))
        return f32(f32(p1 + p2) + p3)

    return [g.gid for g in sorted(goods, key=lambda g: (-p(g), g.gid))]


def main():
    ws.ACCEL = False
    seeds = list(range(2026, 2056))
    # REAL32 end-to-end AWRA is much more expensive than the near probe; use one
    # predeclared seed per each of the 13 scenario strata and report that limit.
    f32_seeds = {2026}
    near_runs = 0
    near_changed_runs = 0
    near_changed_items = 0
    near_max_items = 0
    near_worst = None
    near_max_exp = 0.0
    near_max_energy_rel = 0.0

    f32_runs = 0
    f32_changed_runs = 0
    f32_changed_items = 0
    f32_max_items = 0
    f32_worst = None
    f32_max_exp = 0.0
    f32_max_energy_rel = 0.0
    rank_changed_runs = 0

    for scenario in ig.SCENARIOS:
        for seed in seeds:
            goods = ig.gen_instance(scenario, seed)

            py_map, py_m = run_near(goods, ws.strat_near)
            st_map, st_m = run_near(goods, strat_near_st_scan)
            n_diff = layout_diff(py_map, st_map)
            near_runs += 1
            if n_diff:
                near_changed_runs += 1
                near_changed_items += n_diff
                near_max_exp = max(near_max_exp, abs(py_m["exp_t"] - st_m["exp_t"]))
                near_max_energy_rel = max(
                    near_max_energy_rel,
                    abs(py_m["energy"] - st_m["energy"]) / max(abs(py_m["energy"]), 1.0),
                )
                if n_diff > near_max_items:
                    near_max_items = n_diff
                    near_worst = [scenario, seed]

            if seed in f32_seeds:
                wm = max(g.weight for g in goods)
                fm = max(g.freq for g in goods)
                d_fn = ws.make_score_fn(1.0, 0.6, 0.4, 0.15, wm, fm)
                q_fn = score_f32_factory(1.0, 0.6, 0.4, 0.15, wm, fm)
                d_map, d_m = run_awra(goods, d_fn)
                q_map, q_m = run_awra(goods, q_fn)
                q_diff = layout_diff(d_map, q_map)
                f32_runs += 1
                if q_diff:
                    f32_changed_runs += 1
                    f32_changed_items += q_diff
                    f32_max_exp = max(f32_max_exp, abs(d_m["exp_t"] - q_m["exp_t"]))
                    f32_max_energy_rel = max(
                        f32_max_energy_rel,
                        abs(d_m["energy"] - q_m["energy"]) / max(abs(d_m["energy"]), 1.0),
                    )
                    if q_diff > f32_max_items:
                        f32_max_items = q_diff
                        f32_worst = [scenario, seed]
                if priority_order(goods, False) != priority_order(goods, True):
                    rank_changed_runs += 1

    demo = ws.gen_goods(20, 2026)
    demo_py, demo_py_m = run_near(demo, ws.strat_near)
    demo_st, demo_st_m = run_near(demo, strat_near_st_scan)
    wm = max(g.weight for g in demo)
    fm = max(g.freq for g in demo)
    demo_d, demo_dm = run_awra(demo, ws.make_score_fn(1.0, 0.6, 0.4, 0.15, wm, fm))
    demo_q, demo_qm = run_awra(demo, score_f32_factory(1.0, 0.6, 0.4, 0.15, wm, fm))

    # Valid but non-sequential IDs expose Python gid tie-break vs ST array-index tie-break.
    synthetic = [
        ws.Good(100, "A", 10.0, 10.0, 0.5),
        ws.Good(1, "B", 10.0, 10.0, 0.5),
    ]
    python_rank = priority_order(synthetic, False)
    st_rank_by_index = [g.gid for g in synthetic]

    # Concrete equal-time pair: Python near tie picks lower tier, ST col-major keeps lower col.
    pair = [(0, 1), (4, 0)]
    pair_python = min(pair, key=lambda s: (ws.travel_time(*s), s[1], s[0]))
    pair_st = min(pair, key=lambda s: (ws.travel_time(*s), s[0], s[1]))

    result = {
        "scope": {"scenarios": len(ig.SCENARIOS), "seeds": len(seeds), "runs": near_runs},
        "near_tie_rule": {
            "changed_runs": near_changed_runs,
            "changed_items_total": near_changed_items,
            "max_items_one_run": near_max_items,
            "worst": near_worst,
            "max_abs_exp_t_delta_s": near_max_exp,
            "max_energy_relative_delta": near_max_energy_rel,
            "demo20_layout_diff": layout_diff(demo_py, demo_st),
            "demo20_exp_t_delta_s": abs(demo_py_m["exp_t"] - demo_st_m["exp_t"]),
            "equal_time_pair": {
                "slots": pair,
                "travel_s": [ws.travel_time(*s) for s in pair],
                "python_choice": pair_python,
                "st_scan_choice": pair_st,
            },
        },
        "real32_proxy": {
            "scope_runs": f32_runs,
            "scope_seeds": sorted(f32_seeds),
            "changed_runs": f32_changed_runs,
            "changed_items_total": f32_changed_items,
            "max_items_one_run": f32_max_items,
            "worst": f32_worst,
            "max_abs_exp_t_delta_s": f32_max_exp,
            "max_energy_relative_delta": f32_max_energy_rel,
            "priority_order_changed_runs": rank_changed_runs,
            "demo20_layout_diff": layout_diff(demo_d, demo_q),
            "demo20_exp_t_delta_s": abs(demo_dm["exp_t"] - demo_qm["exp_t"]),
        },
        "rank_tie_nonsequential_ids": {
            "python_gid_order": python_rank,
            "st_array_index_order": st_rank_by_index,
            "different": python_rank != st_rank_by_index,
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
