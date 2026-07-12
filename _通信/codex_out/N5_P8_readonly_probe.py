# -*- coding: utf-8 -*-
"""N5 P8 只读扫描：sim/out CSV/日志结构、键唯一性与 detail↔agg 基数。"""

from __future__ import annotations

import csv
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "sim" / "out"
SECTIONED = {
    "energy_report.csv",
    "realism_matrix.csv",
    "l4_task_cycles.csv",
    "reslot_cycle.csv",
    "scan_g2g4_agg.csv",
    "rl_probe.csv",
}

KEY_SPECS = {
    "adaptive_weights.csv": ["density", "case", "mode", "delta", "bg"],
    "weight_policy_table.csv": ["density", "case", "mode"],
    "experiments_detail.csv": ["scene", "case", "seed", "strat"],
    "experiments_agg.csv": ["scene", "case", "strat"],
    "instgen_detail.csv": ["scenario", "seed", "strat"],
    "instgen_agg.csv": ["scenario", "strat"],
    "instgen_pairs.csv": ["scenario", "metric", "a", "b"],
    "lap_gap.csv": ["scenario", "objective", "seed"],
    "oracle_gap.csv": ["scenario", "selector"],
    "oracle_gap_detail.csv": ["scenario", "seed", "selector"],
    "oracle_gap_profiles.csv": ["scenario", "seed"],
    "scan_g2g4.csv": ["label", "seed", "strategy"],
    "scan_g2g4_agg.csv": ["label"],
    "lifecycle_delta.csv": ["turnover", "seed", "delta"],
    "lifecycle_delta_240.csv": ["turnover", "seed", "delta"],
    "mixed_ops.csv": ["strategy"],
    "motion_compare.csv": ["strategy", "motion"],
    "summary_metrics.csv": ["strategy"],
    "correlated_storage.csv": ["theta", "variant", "seed"],
    "dwell_point.csv": ["n_init", "p_store", "seed", "policy"],
    "l4_task_cycles.csv": ["group"],
    "rl_probe.csv": ["episode"],
}


def rows_of(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.reader(f))


def dict_rows(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def nonfinite_cells(rows):
    bad = []
    for line_no, row in enumerate(rows, 1):
        for col_no, value in enumerate(row, 1):
            v = value.strip()
            if not v:
                continue
            try:
                number = float(v)
            except ValueError:
                continue
            if not math.isfinite(number):
                bad.append([line_no, col_no, value])
    return bad


inventory = {}
for path in sorted(OUT.glob("*.csv")):
    rows = rows_of(path)
    widths = Counter(len(r) for r in rows)
    nonblank = [tuple(r) for r in rows[1:] if r]
    duplicates = sum(n - 1 for n in Counter(nonblank).values() if n > 1)
    header = rows[0] if rows else []
    header_repeats = [i for i, r in enumerate(rows[1:], 2) if r == header]
    ragged = [i for i, r in enumerate(rows[1:], 2) if r and len(r) != len(header)]
    key_dups = None
    key = KEY_SPECS.get(path.name)
    if key and path.name not in SECTIONED:
        recs = dict_rows(path)
        counts = Counter(tuple(r[k] for k in key) for r in recs)
        key_dups = sum(n - 1 for n in counts.values() if n > 1)
    inventory[path.name] = {
        "bytes": path.stat().st_size,
        "physical_rows": len(rows),
        "data_rows_excluding_first_header_and_blank": len(nonblank),
        "width_counts": dict(sorted(widths.items())),
        "blank_rows": [i for i, r in enumerate(rows, 1) if not r],
        "ragged_nonblank_rows_vs_first_header": ragged[:20],
        "header_repeat_rows": header_repeats,
        "duplicate_full_rows": duplicates,
        "nonfinite_cells": nonfinite_cells(rows),
        "known_key": key,
        "duplicate_known_keys": key_dups,
        "declared_multisection": path.name in SECTIONED,
    }


def group_counts(rows, fields):
    c = Counter(tuple(r[f] for f in fields) for r in rows)
    return c


inst_d = dict_rows(OUT / "instgen_detail.csv")
inst_a = dict_rows(OUT / "instgen_agg.csv")
inst_counts = group_counts(inst_d, ["scenario", "strat"])
inst_declared = {(r["scenario"], r["strat"]): int(r["n_runs"]) for r in inst_a}

exp_d = dict_rows(OUT / "experiments_detail.csv")
exp_a = dict_rows(OUT / "experiments_agg.csv")
exp_counts = group_counts(exp_d, ["scene", "case", "strat"])
exp_declared = {(r["scene"], r["case"], r["strat"]): int(r["n_runs"]) for r in exp_a}

oracle_d = dict_rows(OUT / "oracle_gap_detail.csv")
oracle_a = dict_rows(OUT / "oracle_gap.csv")
oracle_profiles = dict_rows(OUT / "oracle_gap_profiles.csv")


def max_aggregate_delta(detail, aggregate, key_fields, field_pairs, all_label=None):
    groups = defaultdict(list)
    for row in detail:
        groups[tuple(row[k] for k in key_fields)].append(row)
    deltas = {}
    for source_field, aggregate_field, mode in field_pairs:
        worst = 0.0
        for row in aggregate:
            key = tuple(row[k] for k in key_fields)
            if all_label and key[0] == all_label:
                selected = [r for r in detail if r[key_fields[-1]] == key[-1]]
            else:
                selected = groups.get(key, [])
            if not selected:
                continue
            values = [float(r[source_field]) for r in selected]
            expected = sum(values) if mode == "sum" else sum(values) / len(values)
            worst = max(worst, abs(float(row[aggregate_field]) - expected))
        deltas[f"{source_field}->{aggregate_field}_{mode}"] = worst
    return deltas


inst_mean_deltas = max_aggregate_delta(
    inst_d,
    inst_a,
    ["scenario", "strat"],
    [
        ("exp_t", "exp_t_mean", "mean"),
        ("energy", "energy_mean", "mean"),
        ("heavy_tier", "heavy_tier_mean", "mean"),
        ("hot_t", "hot_t_mean", "mean"),
        ("fail", "fail_mean", "mean"),
        ("viol", "viol_sum", "sum"),
    ],
)
exp_mean_deltas = max_aggregate_delta(
    exp_d,
    exp_a,
    ["scene", "case", "strat"],
    [
        ("exp_t", "exp_t_mean", "mean"),
        ("energy", "energy_mean", "mean"),
        ("heavy_tier", "heavy_tier_mean", "mean"),
        ("hot_t", "hot_t_mean", "mean"),
        ("fail", "fail_mean", "mean"),
        ("viol", "viol_sum", "sum"),
    ],
)
oracle_mean_deltas = max_aggregate_delta(
    oracle_d,
    oracle_a,
    ["scenario", "selector"],
    [
        ("gap_pct", "gap_mean", "mean"),
        ("attain_pct", "attain_mean", "mean"),
        ("excess_fail", "exf_mean", "mean"),
    ],
    all_label="ALL",
)

assignment = {}
for path in sorted(OUT.glob("assignment_*.csv")):
    recs = dict_rows(path)
    ids = [r["good_id"] for r in recs]
    positions = [(r["col"], r["tier"]) for r in recs]
    assignment[path.name] = {
        "rows": len(recs),
        "duplicate_good_ids": len(ids) - len(set(ids)),
        "duplicate_positions": len(positions) - len(set(positions)),
    }

consistency = (OUT / "consistency_probe.log").read_text(encoding="utf-8-sig")
label_match = re.search(r"全量\s+(\d+)\s+次\((\d+)\s+场景\s*[×x]\s*(\d+)\s*seeds", consistency)

# 展示普通 DictReader 对多表 CSV 的实际解释，证明不是一个可靠矩形表。
sectioned_reader = {}
for name in SECTIONED:
    recs = dict_rows(OUT / name)
    sectioned_reader[name] = {
        "dictreader_rows": len(recs),
        "rows_with_extra_columns_key_None": sum(1 for r in recs if None in r),
        "rows_with_missing_values": sum(1 for r in recs if any(v is None for k, v in r.items() if k is not None)),
    }

result = {
    "scope": "read-only scan of sim/out; no Automation Builder",
    "inventory_summary": {
        "csv_files": len(inventory),
        "zero_byte_files": [k for k, v in inventory.items() if v["bytes"] == 0],
        "nonfinite_files": [k for k, v in inventory.items() if v["nonfinite_cells"]],
        "duplicate_full_row_files": {k: v["duplicate_full_rows"] for k, v in inventory.items() if v["duplicate_full_rows"]},
        "duplicate_known_key_files": {k: v["duplicate_known_keys"] for k, v in inventory.items() if v["duplicate_known_keys"]},
        "ragged_files": {k: v["ragged_nonblank_rows_vs_first_header"] for k, v in inventory.items() if v["ragged_nonblank_rows_vs_first_header"]},
    },
    "inventory": inventory,
    "cross_checks": {
        "instgen": {
            "detail_rows": len(inst_d),
            "scenarios": len({r["scenario"] for r in inst_d}),
            "seeds": len({r["seed"] for r in inst_d}),
            "strategies": len({r["strat"] for r in inst_d}),
            "agg_rows": len(inst_a),
            "detail_group_count_matches_agg_n_runs": inst_counts == inst_declared,
            "max_abs_aggregate_deltas": inst_mean_deltas,
        },
        "experiments": {
            "detail_rows": len(exp_d),
            "agg_rows": len(exp_a),
            "detail_group_count_matches_agg_n_runs": exp_counts == exp_declared,
            "max_abs_aggregate_deltas": exp_mean_deltas,
        },
        "oracle": {
            "detail_rows": len(oracle_d),
            "summary_rows": len(oracle_a),
            "profile_rows": len(oracle_profiles),
            "scenarios": len({r["scenario"] for r in oracle_d}),
            "seeds": len({r["seed"] for r in oracle_d}),
            "selectors": len({r["selector"] for r in oracle_d}),
            "detail_expected_product": len({r["scenario"] for r in oracle_d}) * len({r["seed"] for r in oracle_d}) * len({r["selector"] for r in oracle_d}),
            "summary_includes_ALL_rows": sum(r["scenario"] == "ALL" for r in oracle_a),
            "max_abs_aggregate_deltas": oracle_mean_deltas,
            "negative_gap_detail_rows": sum(float(r["gap_pct"]) < 0 for r in oracle_d),
            "attain_over_100_detail_rows": sum(float(r["attain_pct"]) > 100 for r in oracle_d),
            "negative_gap_with_excess_fail_rows": sum(float(r["gap_pct"]) < 0 and int(r["excess_fail"]) > 0 for r in oracle_d),
            "negative_gap_without_excess_fail_rows": sum(float(r["gap_pct"]) < 0 and int(r["excess_fail"]) == 0 for r in oracle_d),
            "negative_gap_summary_rows": [
                [r["scenario"], r["selector"], float(r["gap_mean"]), float(r["attain_mean"]), float(r["exf_mean"])]
                for r in oracle_a if float(r["gap_mean"]) < 0
            ],
        },
        "adaptive": {
            "candidate_rows": len(dict_rows(OUT / "adaptive_weights.csv")),
            "policy_rows": len(dict_rows(OUT / "weight_policy_table.csv")),
        },
        "assignment": assignment,
    },
    "consistency_log_label": {
        "parsed": label_match.groups() if label_match else None,
        "actual_instgen_scenarios": len({r["scenario"] for r in inst_d}),
        "actual_instgen_runs": len(inst_d),
        "actual_probe_runs_implied_by_390": 390,
    },
    "multisection_dictreader_behavior": sectioned_reader,
}

print(json.dumps(result, ensure_ascii=False, indent=2))
