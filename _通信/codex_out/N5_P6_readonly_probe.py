# -*- coding: utf-8 -*-
"""N5 P6 只读复算：能耗年化、碳因子与吞吐单位链。"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SIM = ROOT / "sim"
sys.path.insert(0, str(SIM))

import energy_report as er  # noqa: E402
import mixed_ops as mo  # noqa: E402
import warehouse_sim as ws  # noqa: E402


def rerun_h_energy():
    ws.ACCEL = True
    goods = ws.gen_goods(mo.N_INIT, mo.SEED)
    w_max = max(g.weight for g in goods)
    f_max = max(g.freq for g in goods)
    d_on, bg_on = ws.lookup_weights(mo.N_INIT, "skew", "online")
    d_ba, bg_ba = ws.lookup_weights(mo.N_INIT, "skew", "batch")
    fn = ws.make_score_fn(1.0, bg_on / 2, bg_on / 2, d_on, w_max, f_max)
    fn_batch = ws.make_score_fn(1.0, bg_ba / 2, bg_ba / 2, d_ba, w_max, f_max)
    new_goods, requests = mo.build_workload(goods, 100, mo.SEED)

    cycles_individual_ops = er.DAILY_OPS / 2 * er.WORK_DAYS
    cycles_dual_commands = er.DAILY_OPS * er.WORK_DAYS
    out = {}
    for strategy in ("seq", "awra"):
        e_j, _, n_cycles = er.run_energy(
            strategy, goods, new_goods, requests, fn, w_max, f_max, fn_batch
        )
        kwh_cycle = e_j / er.ETA / n_cycles / er.J_PER_KWH
        out[strategy] = {
            "kwh_per_dual_cycle": kwh_cycle,
            "kwh_year_if_500_individual_ops_day": kwh_cycle * cycles_individual_ops,
            "kwh_year_if_500_dual_cycles_day": kwh_cycle * cycles_dual_commands,
        }
    return out


def read_mixed_h():
    with (SIM / "out" / "mixed_ops.csv").open(encoding="utf-8-sig", newline="") as f:
        return {row["strategy"]: row for row in csv.DictReader(f)}


energy = rerun_h_energy()
mixed = read_mixed_h()
seq_year = energy["seq"]["kwh_year_if_500_individual_ops_day"]
awra_year = energy["awra"]["kwh_year_if_500_individual_ops_day"]
saving_kwh = seq_year - awra_year
awra_travel = float(mixed["awra"]["tot_dual_s"])
n_ops = 2 * int(mixed["awra"]["cycles"])
handling_s = n_ops * 15.0
failure_s = 600.0

result = {
    "scope": "read-only Python rerun; no Automation Builder",
    "energy_h_rerun": energy,
    "annualization": {
        "daily_ops_source_value": er.DAILY_OPS,
        "work_days": er.WORK_DAYS,
        "code_interpretation": "500 individual operations/day = 250 dual cycles/day",
        "dual_cycles_per_year_used_by_code": er.DAILY_OPS / 2 * er.WORK_DAYS,
        "dual_cycles_per_year_if_500_means_cycles": er.DAILY_OPS * er.WORK_DAYS,
        "saving_kwh_current_interpretation": saving_kwh,
        "saving_kwh_if_500_dual_cycles_day": saving_kwh * 2,
        "relative_saving_pct": (1 - awra_year / seq_year) * 100,
        "cost_saving_yuan_at_0_8": saving_kwh * er.ELEC_PRICE,
    },
    "co2_factor_sensitivity": {
        "project_factor_0_581_saving_kg": saving_kwh * 0.581,
        "mee_2023_national_average_0_5306_saving_kg": saving_kwh * 0.5306,
        "mee_2023_excluding_market_nonfossil_0_6096_saving_kg": saving_kwh * 0.6096,
        "relative_saving_pct_unchanged": True,
    },
    "throughput_awra_h": {
        "operations": n_ops,
        "travel_only_s": awra_travel,
        "travel_only_ops_h": n_ops / awra_travel * 3600,
        "plus_15s_each_store_and_retrieve_s": awra_travel + handling_s,
        "plus_handling_ops_h": n_ops / (awra_travel + handling_s) * 3600,
        "plus_one_600s_failure_s": awra_travel + handling_s + failure_s,
        "plus_handling_and_failure_ops_h": n_ops / (awra_travel + handling_s + failure_s) * 3600,
        "realism_common_arrival_observed_ops_h_from_p4": 41.79,
    },
}

print(json.dumps(result, ensure_ascii=False, indent=2))
