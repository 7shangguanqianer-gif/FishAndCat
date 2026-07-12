# -*- coding: utf-8 -*-
"""N5-P4 read-only counterfactuals. Prints JSON; writes no project artifacts."""
from __future__ import annotations

import csv
import json
import random
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SIM = ROOT / "sim"
sys.path.insert(0, str(SIM))

import lifecycle_sim as lc  # noqa: E402
import mixed_ops as mo  # noqa: E402
import realism as rl  # noqa: E402
import warehouse_sim as ws  # noqa: E402


def adaptive_failure_audit():
    path = SIM / "out" / "adaptive_weights.csv"
    rows = list(csv.DictReader(path.open(encoding="utf-8-sig")))
    groups = {}
    for row in rows:
        key = (int(row["density"]), row["case"], row["mode"])
        groups.setdefault(key, []).append(row)
    details = []
    for key, vals in sorted(groups.items()):
        valid = [r for r in vals if int(r["viol_sum"]) == 0]
        best = min(valid, key=lambda r: (float(r["exp_mean"]), float(r["ene_mean"])))
        safe = [r for r in valid if int(r["fail_sum"]) == 0]
        if int(best["fail_sum"]) > 0:
            details.append({
                "scenario": list(key),
                "selected_delta": float(best["delta"]),
                "selected_bg": float(best["bg"]),
                "selected_exp": float(best["exp_mean"]),
                "selected_fail_sum": int(best["fail_sum"]),
                "zero_fail_candidate_exists": bool(safe),
                "min_fail_sum_any_weight": min(int(r["fail_sum"]) for r in valid),
            })
    return {
        "rows": len(rows),
        "groups": len(groups),
        "selected_with_fail_groups": len(details),
        "details": details,
    }


def shared_arrivals(e_pair, cycles, seed):
    rng = random.Random(seed + 23)
    arrivals = []
    now = 0.0
    for k in range(cycles):
        rho = rl.RHO_PEAK if k < cycles // 2 else rl.RHO_OFF
        now += rng.expovariate(rho / e_pair)
        arrivals.append(now)
    return arrivals


def run_tier3_with_arrivals(strat_name, goods, new_goods, requests, fn, wm, fm,
                            fnb, arrivals, seed):
    goods_est = rl.noisy_clone(goods, rl.FREQ_SIGMA, seed + 21)
    new_est = rl.noisy_clone(new_goods, rl.FREQ_SIGMA, seed + 22)
    wh, pos_of = mo.initial_layout(strat_name, goods_est, fnb or fn, wm, fm)
    online = {"seq": ws.strat_seq, "near": ws.strat_near,
              "score": ws.strat_score, "awra": ws.strat_score}[strat_name]
    rng_fail = random.Random(seed + 29)
    next_fail_busy = rng_fail.expovariate(1.0 / rl.MTBF_S)
    crane_free = busy_acc = downtime = 0.0
    responses = []
    n_down = fails = completed = 0
    for k, (g_in, g_out) in enumerate(zip(new_est, requests)):
        s_out = pos_of.pop(g_out.gid)
        s_in = online(wh, g_in, fn)
        if s_in is None:
            fails += 1
            wh.remove(s_out[0], s_out[1])
            continue
        service = (ws.travel_time(*s_in)
                   + ws.travel_time_between(s_in[0], s_in[1], s_out[0], s_out[1])
                   + ws.travel_time(*s_out) + 2 * rl.HANDLE_S)
        start = max(arrivals[k], crane_free)
        if busy_acc + service > next_fail_busy:
            service += rl.MTTR_S
            downtime += rl.MTTR_S
            n_down += 1
            next_fail_busy = busy_acc + service + rng_fail.expovariate(1.0 / rl.MTBF_S)
        finish = start + service
        crane_free = finish
        busy_acc += service
        responses.append(finish - arrivals[k])
        wh.put(s_in[0], s_in[1], g_in)
        pos_of[g_in.gid] = s_in
        wh.remove(s_out[0], s_out[1])
        completed += 1
    responses.sort()
    n = len(responses)
    return {
        "p50": responses[n // 2] if n else 0.0,
        "p95": responses[min(n - 1, int(n * 0.95))] if n else 0.0,
        "util": (busy_acc - downtime) / crane_free if crane_free else 0.0,
        "n_down": n_down,
        "fails": fails,
        "makespan": crane_free,
        "completed_ops_per_hour": (2 * completed / crane_free * 3600.0) if crane_free else 0.0,
    }


def realism_common_arrival_audit():
    cycles = 100
    seed = rl.SEED
    goods = ws.gen_goods(rl.N_INIT, seed)
    new_goods, requests = mo.build_workload(goods, cycles, seed)
    wm, fm = max(g.weight for g in goods), max(g.freq for g in goods)
    ws.ACCEL = True
    d_on, bg_on = ws.lookup_weights(rl.N_INIT, "skew", "online")
    d_ba, bg_ba = ws.lookup_weights(rl.N_INIT, "skew", "batch")
    fn = ws.make_score_fn(1.0, bg_on / 2, bg_on / 2, d_on, wm, fm)
    fnb = ws.make_score_fn(1.0, bg_ba / 2, bg_ba / 2, d_ba, wm, fm)

    # Existing implementation: each strategy derives its own e_pair and arrival scale.
    existing = rl.tier3(goods, new_goods, requests, cycles)

    # Counterfactual: define external demand once from the seq baseline, then reuse exact arrivals.
    goods_est = rl.noisy_clone(goods, rl.FREQ_SIGMA, seed + 21)
    new_est = rl.noisy_clone(new_goods, rl.FREQ_SIGMA, seed + 22)
    probe = mo.run_mixed("seq", goods_est, new_est, requests, fn, wm, fm, fnb)
    e_pair_ref = probe["tot_dual"] / cycles + 2 * rl.HANDLE_S
    arrivals = shared_arrivals(e_pair_ref, cycles, seed)
    common = {
        s: run_tier3_with_arrivals(s, goods, new_goods, requests, fn, wm, fm,
                                   fnb, arrivals, seed)
        for s in mo.STRATS
    }
    return {
        "cycles": cycles,
        "arrival_reference": "seq",
        "reference_pair_s": e_pair_ref,
        "last_arrival_s": arrivals[-1],
        "existing_strategy_specific_arrivals": {
            s: {"p50": existing[s]["resp_p50"], "p95": existing[s]["resp_p95"],
                "util": existing[s]["util"]}
            for s in mo.STRATS
        },
        "common_arrivals": common,
    }


def lifecycle_with_flush(seed, delta, cycles=200, day_len=40, turnover=10):
    ws.ACCEL = False
    goods = ws.gen_goods(lc.N_INIT, seed)
    wm, fm = max(g.weight for g in goods), max(g.freq for g in goods)
    fn = ws.make_score_fn(1.0, 0.6, 0.4, delta, wm, fm)
    wh, placed, failed = ws.run_awra_ls(goods, lc.RULE, fn, wm, fm)
    assert not failed
    pos_of = {g.gid: p for g, p in placed}
    by_gid = {g.gid: g for g in goods}
    new_goods = ws.gen_goods(cycles // turnover + 2, seed + 7)
    for i, good in enumerate(new_goods):
        good.gid, good.name = 1000 + i + 1, f"N{i+1:03d}"
    rng = random.Random(seed + 13)
    pending = []
    ni = n_return = 0
    total = 0.0
    for k in range(cycles):
        due = [p for p in pending if p[0] <= k]
        pending = [p for p in pending if p[0] > k]
        for _, good in due:
            pos = ws.strat_score(wh, good, fn)
            assert pos is not None
            wh.put(pos[0], pos[1], good)
            pos_of[good.gid] = pos
            by_gid[good.gid] = good
            total += lc._t_store(pos, good)
        gids = list(pos_of)
        gid = rng.choices(gids, weights=[by_gid[x].freq for x in gids], k=1)[0]
        good = by_gid[gid]
        pos = pos_of.pop(gid)
        total += lc._t_retrieve(pos, good)
        wh.remove(pos[0], pos[1])
        n_return += 1
        if n_return % turnover == 0 and ni < len(new_goods):
            back = new_goods[ni]
            ni += 1
        else:
            back = good
        pending.append((k + lc.LAG, back))
        if (k + 1) % day_len == 0:
            lc.reslot_pass(wh, pos_of, by_gid, day_len=day_len)

    pre_count = len(pos_of)
    pre_q = lc.layout_quality(wh, pos_of, by_gid)
    pending_count = len(pending)
    flush_time = 0.0
    for _, good in sorted(pending):
        pos = ws.strat_score(wh, good, fn)
        assert pos is not None
        wh.put(pos[0], pos[1], good)
        pos_of[good.gid] = pos
        by_gid[good.gid] = good
        flush_time += lc._t_store(pos, good)
    return {
        "pending": pending_count,
        "inventory_before_flush": pre_count,
        "inventory_after_flush": len(pos_of),
        "total_before_flush": total,
        "flush_store_time": flush_time,
        "flush_pct_of_reported_total": 100 * flush_time / total,
        "quality_before_flush": pre_q,
        "quality_after_flush": lc.layout_quality(wh, pos_of, by_gid),
    }


def lifecycle_tail_audit():
    rows = []
    for seed in range(2026, 2036):
        for delta in (0.15, 0.0):
            row = lifecycle_with_flush(seed, delta)
            row.update(seed=seed, delta=delta)
            rows.append(row)
    return {
        "scope_runs": len(rows),
        "seeds": list(range(2026, 2036)),
        "pending_values": sorted(set(r["pending"] for r in rows)),
        "inventory_before_values": sorted(set(r["inventory_before_flush"] for r in rows)),
        "inventory_after_values": sorted(set(r["inventory_after_flush"] for r in rows)),
        "mean_flush_time_s": st.mean(r["flush_store_time"] for r in rows),
        "range_flush_time_s": [min(r["flush_store_time"] for r in rows),
                               max(r["flush_store_time"] for r in rows)],
        "mean_flush_pct": st.mean(r["flush_pct_of_reported_total"] for r in rows),
        "mean_quality_shift": st.mean(r["quality_after_flush"] - r["quality_before_flush"]
                                      for r in rows),
    }


def main():
    result = {
        "adaptive_failure": adaptive_failure_audit(),
        "realism_common_arrival": realism_common_arrival_audit(),
        "lifecycle_tail": lifecycle_tail_audit(),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
