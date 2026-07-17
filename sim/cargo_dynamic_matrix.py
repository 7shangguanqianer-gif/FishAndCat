# -*- coding: utf-8 -*-
"""Pre-registered dynamic cargo risk matrix for the S3 simulation showcase.

The runner compares seven fixed strategy chains plus one-shot AUTO on exactly
the same workload, arrivals, noise and busy-time fault stream.  All outputs are
simulation evidence; fixed score weights are used here to isolate the routing
and strategy-chain question from the separate 2-seed adaptive-weight design.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import csv
import hashlib
import inspect
import json
import os
import platform
import statistics as stats
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

import cargo_scenarios as cs
import instance_gen as ig
import mixed_ops as mo
import realism
import strategy_lib as sl
import warehouse_sim as ws


HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
MODES = mo.DYNAMIC_STRATS + ["AUTO"]
SMOKE_SCENARIOS = ["E02", "E10", "E14", "E15", "E18"]
SCORE_POLICY_ID = "fixed_default_v1_router_isolation"
SCORE_WEIGHTS = (1.0, 0.6, 0.4, 0.15)
SCHEMA_VERSION = "cargo_dynamic_matrix_v1"
EVIDENCE_STAGES = frozenset({"smoke", "s1", "s2", "s3"})


def stage_seeds(stage: str) -> List[int]:
    registry = cs.load_registry()
    mapping = {
        "s1": "S1_exploration",
        "s2": "S2_confirmation",
        "s3": "S3_long_run",
    }
    try:
        lo, hi = registry["seed_ranges"][mapping[stage.lower()]]
    except KeyError as exc:
        raise ValueError(f"stage has no dynamic seed partition: {stage}") from exc
    return list(range(int(lo), int(hi) + 1))


def s0_boundary_rows() -> List[Dict[str, Any]]:
    rows = []
    for density in (0.249, 0.250, 0.251, 0.699, 0.700, 0.701):
        profile = dict(n=120, density=density, skew=0.5, w_mean=40.0, w_heavy=0.2)
        rows.append({
            "axis": "density_direct", "input": density,
            "picked": sl.select_strategy(profile, True, "lexicographic"),
        })
    for n in (65, 66, 67, 186, 187, 188):
        profile = sl.batch_profile(ws.gen_goods(n, 2026, "skew"))
        rows.append({
            "axis": "n_reachable", "input": n, "rounded_density": profile["density"],
            "picked": sl.select_strategy(profile, True, "lexicographic"),
        })
    for skew in (0.349, 0.350, 0.351):
        profile = dict(n=120, density=0.45, skew=skew, w_mean=40.0, w_heavy=0.2)
        rows.append({
            "axis": "skew_online", "input": skew,
            "picked": sl.select_strategy(profile, False, "lexicographic"),
        })
    return rows


def _score_functions(goods):
    w_max = max(g.weight for g in goods)
    f_max = max(g.freq for g in goods)
    fn = ws.make_score_fn(*SCORE_WEIGHTS, w_max, f_max)
    return fn, fn, w_max, f_max


def _arrival_stream(goods, workload, fn, w_max, f_max, fn_batch,
                    scenario, seed):
    try:
        arrivals, reference_pair_s = realism.common_arrivals_for_workload(
            goods, workload, fn, w_max, f_max, fn_batch, seed=seed,
            tier3_params=scenario["tier3"],
        )
        return arrivals, reference_pair_s, "SEQ_REFERENCE"
    except AssertionError:
        # Some deliberately near-limit cells cannot build the seq reference at
        # all.  Use a deterministic geometry upper-bound only to create a CRN
        # arrival stream; keep every result non-headline and label the fallback.
        handle_s = float(scenario["tier3"].get("handle_s", realism.HANDLE_S))
        reference_pair_s = 3.0 * ws.t_max_now() + 2.0 * handle_s
        arrivals = realism.build_arrivals(
            workload["scheduled_cycles"], seed, reference_pair_s,
            rho_peak=scenario["tier3"]["arrival_rho"],
            rho_off=scenario["tier3"].get("arrival_rho_off", realism.RHO_OFF),
        )
        return arrivals, reference_pair_s, "GEOMETRY_BOUND_FALLBACK"


def _row_from_metrics(scenario_id, scenario, seed, mode, metrics,
                      reference_pair_s, reference_status, profile):
    router = metrics["router"]
    feasible = metrics["status"] == "FEASIBLE"
    raw_p50 = metrics.get("resp_p50")
    raw_p95 = metrics.get("resp_p95")
    hashes = metrics["stream_hashes"]
    return {
        "schema_version": SCHEMA_VERSION,
        "sim_only": True,
        "scenario": scenario_id,
        "scenario_title": scenario.get("ui_label", scenario["label"]),
        "seed": int(seed),
        "mode": mode,
        "picked_strategy": metrics["picked_strategy"],
        "initial_strategy": router["initial_strategy"],
        "online_strategy": router["online_strategy"],
        "objective": router["objective"],
        "batch_known": router["batch_known"],
        "reason_code": router["reason_code"],
        "reason_basis": router["reason_basis"],
        "selection_scope": router["selection_scope"],
        "weight_aware": router["weight_aware"],
        "profile_n": profile["n"],
        "profile_density": profile["density"],
        "profile_skew": profile["skew"],
        "profile_w_mean": profile["w_mean"],
        "profile_w_heavy": profile["w_heavy"],
        "rho_weight_freq": profile["rho_weight_freq"],
        "rho_weight_volume": profile["rho_weight_volume"],
        "score_policy": SCORE_POLICY_ID,
        "score_alpha": SCORE_WEIGHTS[0],
        "score_beta": SCORE_WEIGHTS[1],
        "score_gamma": SCORE_WEIGHTS[2],
        "score_delta": SCORE_WEIGHTS[3],
        "status": metrics["status"],
        "initial_fails": metrics["initial_fails"],
        "fails": metrics["fails"],
        "excess_fail": metrics["fails"],
        "viol": metrics["viol"],
        "scheduled_cycles": metrics["scheduled_cycles"],
        "valid_cycles": metrics["valid_cycles"],
        "rejected_cycles": metrics["rejected_cycles"],
        "processed_scheduled_cycles": metrics["processed_scheduled_cycles"],
        "processed_valid_cycles": metrics["processed_valid_cycles"],
        "processed_rejected_cycles": metrics["processed_rejected_cycles"],
        "completed_cycles": metrics["completed_cycles"],
        "unprocessed_cycles": metrics["unprocessed_cycles"],
        "terminal_failure_cycle": metrics["terminal_failure_cycle"],
        "terminal_failure_stage": metrics["terminal_failure_stage"],
        "failure_policy": metrics["failure_policy"],
        "expected_reject": scenario["invalid_inbound_policy"]["expected_count"],
        "response_sample_n": metrics["response_sample_n"],
        "dual_time_sample_n": metrics["dual_time_sample_n"],
        "raw_resp_p50_s": raw_p50,
        "raw_resp_p95_s": raw_p95,
        "resp_p50_s": raw_p50 if feasible else None,
        "resp_p95_s": raw_p95 if feasible else None,
        "avg_retrieve_s": metrics.get("avg_retr"),
        "travel_dual_s": metrics.get("tot_dual"),
        "busy_total_s": metrics.get("busy_total"),
        "util": metrics.get("util") if feasible else None,
        "n_down": metrics.get("n_down", 0),
        "downtime_s": metrics.get("downtime", 0.0),
        "drain_time_s": metrics.get("drain_time_s") if feasible else None,
        "final_layout_exp_t": metrics.get("final_layout_exp_t") if feasible else None,
        "final_energy_kgm": metrics.get("final_energy_kgm") if feasible else None,
        "final_heavy_tier": metrics.get("final_heavy_tier") if feasible else None,
        "final_cog_m": metrics.get("final_cog_m") if feasible else None,
        "strategy_switches": metrics["strategy_switches"],
        "advisory_count": metrics["advisory_count"],
        "arrival_reference_pair_s": reference_pair_s,
        "arrival_reference_status": reference_status,
        "arrival_rho": scenario["tier3"]["arrival_rho"],
        "freq_noise_sigma": scenario["tier3"]["freq_noise_sigma"],
        "fault_mtbf_s": scenario["tier3"]["fault_mtbf_s"],
        "fault_mttr_s": scenario["tier3"]["fault_mttr_s"],
        "extended_pressure": bool(scenario.get("extended_pressure", False)),
        "canonical_g2": bool(scenario.get("canonical_g2", True)),
        "headline_eligible": bool(scenario.get("headline_eligible", True)),
        "workload_hash": hashes["workload_hash"],
        "arrivals_hash": hashes["arrivals_hash"],
        "noise_hash": hashes["noise_hash"],
        "fault_stream_hash": hashes["fault_stream_hash"],
        "fairness_pass": None,
        "oracle_mode": None,
        "oracle_p95_s": None,
        "p95_gap_to_oracle_s": None,
        "auto_regret_s": None,
        "auto_regret_status": "NOT_AUTO" if mode != "AUTO" else None,
    }


def run_cell(scenario_id: str, seed: int,
             modes: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    registry = cs.load_registry()
    if scenario_id not in registry["scenarios"]:
        raise KeyError(f"unknown scenario: {scenario_id}")
    scenario = registry["scenarios"][scenario_id]
    modes = list(modes or MODES)
    if modes != MODES and any(mode not in MODES for mode in modes):
        raise ValueError(f"unknown matrix mode in {modes}")

    old_accel = ws.ACCEL
    ws.ACCEL = True
    try:
        goods = cs.build_initial_goods(scenario_id, seed)
        inbound = cs.build_inbound_goods(
            scenario_id, seed, scenario["scheduled_cycles"]
        )
        workload = mo.build_scenario_workload(goods, inbound, scenario, seed)
        fn, fn_batch, w_max, f_max = _score_functions(goods)
        arrivals, reference_pair_s, reference_status = _arrival_stream(
            goods, workload, fn, w_max, f_max, fn_batch, scenario, seed
        )
        all_inbound = [item["inbound_good"] for item in workload["cycles"]]
        noise_stream = realism.build_noise_stream(
            goods, all_inbound, scenario["tier3"]["freq_noise_sigma"], seed
        )
        fault_intervals = realism.build_fault_intervals(
            workload["scheduled_cycles"], seed, scenario["tier3"]["fault_mtbf_s"]
        )
        profile = cs.scenario_profile(goods)
        rows = []
        for mode in modes:
            metrics = realism.run_tier3(
                mode, goods, workload["valid_inbound_goods"], workload["requests"],
                fn, w_max, f_max, fn_batch,
                arrivals=arrivals, cycles=workload["scheduled_cycles"], seed=seed,
                workload=workload, fault_intervals=fault_intervals,
                noise_stream=noise_stream, tier3_params=scenario["tier3"],
                router_objective="lexicographic", batch_known=True,
            )
            rows.append(_row_from_metrics(
                scenario_id, scenario, seed, mode, metrics,
                reference_pair_s, reference_status, profile,
            ))
    finally:
        ws.ACCEL = old_accel

    bundles = {
        (row["workload_hash"], row["arrivals_hash"],
         row["noise_hash"], row["fault_stream_hash"])
        for row in rows
    }
    if len(bundles) != 1:
        raise RuntimeError(f"CRN hash mismatch in {scenario_id}/seed={seed}")
    for row in rows:
        row["fairness_pass"] = True

    fixed_feasible = [
        row for row in rows
        if row["mode"] != "AUTO" and row["status"] == "FEASIBLE"
        and row["resp_p95_s"] is not None and row["excess_fail"] == 0
        and row["viol"] == 0
    ]
    if fixed_feasible:
        oracle = min(fixed_feasible, key=lambda row: (row["resp_p95_s"], MODES.index(row["mode"])))
        for row in rows:
            row["oracle_mode"] = oracle["mode"]
            row["oracle_p95_s"] = oracle["resp_p95_s"]
            if row["status"] == "FEASIBLE" and row["resp_p95_s"] is not None:
                row["p95_gap_to_oracle_s"] = row["resp_p95_s"] - oracle["resp_p95_s"]
        auto = next((row for row in rows if row["mode"] == "AUTO"), None)
        if auto is not None:
            if auto["status"] == "FEASIBLE" and auto["resp_p95_s"] is not None:
                auto["auto_regret_s"] = auto["resp_p95_s"] - oracle["resp_p95_s"]
                auto["auto_regret_status"] = "COMPARABLE"
            else:
                auto["auto_regret_status"] = "NA_AUTO_INFEASIBLE"
    else:
        auto = next((row for row in rows if row["mode"] == "AUTO"), None)
        if auto is not None:
            auto["auto_regret_status"] = "NA_NO_FIXED_ORACLE"

    return {
        "scenario": scenario_id,
        "seed": int(seed),
        "rows": rows,
        "fairness_pass": True,
        "arrival_reference_pair_s": reference_pair_s,
        "arrival_reference_status": reference_status,
        "oracle_mode": fixed_feasible and min(
            fixed_feasible, key=lambda row: (row["resp_p95_s"], MODES.index(row["mode"]))
        )["mode"] or None,
    }


def _ci(values: Sequence[float]):
    if not values:
        return None, None, None
    mean, half = ig.ci95(list(values))
    sd = stats.stdev(values) if len(values) > 1 else 0.0
    return float(mean), float(sd), float(half)


def aggregate_rows(detail: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    groups = defaultdict(list)
    for row in detail:
        groups[(row["scenario"], row["mode"])].append(row)
    aggregated = []
    scenario_order = {f"E{i:02d}": i for i in range(1, 19)}
    for (scenario, mode), rows in sorted(
        groups.items(), key=lambda item: (scenario_order[item[0][0]], MODES.index(item[0][1]))
    ):
        p95 = [float(row["resp_p95_s"]) for row in rows if row["resp_p95_s"] is not None]
        regrets = [
            float(row["auto_regret_s"]) for row in rows
            if row["mode"] == "AUTO" and row["auto_regret_s"] is not None
        ]
        p95_mean, p95_sd, p95_ci = _ci(p95)
        regret_mean, regret_sd, regret_ci = _ci(regrets)
        picks = Counter(row["picked_strategy"] for row in rows)
        aggregated.append({
            "schema_version": SCHEMA_VERSION,
            "sim_only": True,
            "scenario": scenario,
            "scenario_title": rows[0]["scenario_title"],
            "mode": mode,
            "n_runs": len(rows),
            "n_feasible": sum(row["status"] == "FEASIBLE" for row in rows),
            "infeasible_rate": sum(row["status"] != "FEASIBLE" for row in rows) / len(rows),
            "p95_seed_n": len(p95),
            "p95_mean_s": p95_mean,
            "p95_sd_s": p95_sd,
            "p95_ci95_half_s": p95_ci,
            "auto_regret_seed_n": len(regrets),
            "auto_regret_mean_s": regret_mean,
            "auto_regret_sd_s": regret_sd,
            "auto_regret_ci95_half_s": regret_ci,
            "fail_sum": sum(row["fails"] for row in rows),
            "viol_sum": sum(row["viol"] for row in rows),
            "reject_sum": sum(row["rejected_cycles"] for row in rows),
            "picked_counts": json.dumps(dict(sorted(picks.items())), ensure_ascii=False,
                                        separators=(",", ":")),
            "selection_stability": max(picks.values()) / len(rows),
            "score_policy": SCORE_POLICY_ID,
            "extended_pressure": rows[0]["extended_pressure"],
            "canonical_g2": rows[0]["canonical_g2"],
            "headline_eligible": rows[0]["headline_eligible"],
        })
    return aggregated


def run_matrix(scenario_ids: Sequence[str], seeds: Sequence[int],
               modes: Optional[Sequence[str]] = None,
               stage: str = "custom") -> Dict[str, Any]:
    modes = list(modes or MODES)
    detail = []
    cells = []
    for scenario_id in scenario_ids:
        for seed in seeds:
            cell = run_cell(scenario_id, int(seed), modes=modes)
            for row in cell["rows"]:
                row["stage"] = stage
            detail.extend(cell["rows"])
            cells.append({key: value for key, value in cell.items() if key != "rows"})
    return {
        "schema_version": SCHEMA_VERSION,
        "sim_only": True,
        "stage": stage,
        "score_policy": SCORE_POLICY_ID,
        "scenarios": list(scenario_ids),
        "seeds": [int(seed) for seed in seeds],
        "modes": modes,
        "detail": detail,
        "agg": aggregate_rows(detail),
        "cells": cells,
        "scenario_manifests": {
            scenario_id: cs.scenario_manifest(scenario_id) for scenario_id in scenario_ids
        },
    }


def _write_csv(path: Path, rows: Sequence[Dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"refusing to write empty CSV: {path}")
    with path.open("w", newline="", encoding="utf-8-sig") as fp:
        writer = csv.DictWriter(fp, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fp:
        for chunk in iter(lambda: fp.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _function_sha256(function) -> str:
    source = inspect.getsource(function).replace("\r\n", "\n")
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def _runner_provenance() -> Dict[str, Any]:
    functions = {
        "stage_seeds": stage_seeds,
        "_arrival_stream": _arrival_stream,
        "_row_from_metrics": _row_from_metrics,
        "run_cell": run_cell,
        "aggregate_rows": aggregate_rows,
        "run_matrix": run_matrix,
        "write_outputs": write_outputs,
    }
    return {
        "source_sha256": {"sim/cargo_dynamic_matrix.py": _sha256(Path(__file__))},
        "function_sha256": {
            name: _function_sha256(function) for name, function in functions.items()
        },
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "platform": sys.platform,
    }


def _manifest_identity(manifest: Dict[str, Any]) -> Dict[str, Any]:
    """Fields that must match before an evidence stage may be refreshed."""
    return {
        key: manifest.get(key)
        for key in (
            "schema_version", "stage", "scenarios", "seeds", "modes",
            "score_policy", "cell_count", "run_count", "runner_provenance",
            "scenario_manifests",
        )
    }


@contextmanager
def _exclusive_stage_lock(output_dir: Path):
    """Serialize first-write and refresh operations for one evidence stage."""
    lock_path = output_dir / ".write.lock"
    try:
        descriptor = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise FileExistsError(f"evidence stage write lock is held: {lock_path}") from exc
    try:
        payload = json.dumps({"pid": os.getpid()}, separators=(",", ":")).encode("ascii")
        os.write(descriptor, payload)
        os.close(descriptor)
        descriptor = None
        yield
    finally:
        if descriptor is not None:
            os.close(descriptor)
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


def _write_outputs_locked(result: Dict[str, Any], output_dir: Path,
                          stage: str) -> Dict[str, str]:
    paths = {
        "detail": output_dir / "cargo_dynamic_matrix_detail.csv",
        "agg": output_dir / "cargo_dynamic_matrix_agg.csv",
        "params": output_dir / "cargo_dynamic_matrix_params.csv",
        "manifest": output_dir / "cargo_dynamic_matrix_manifest.json",
    }
    params = [
        {"param": "schema_version", "value": SCHEMA_VERSION,
         "note": "versioned dynamic matrix"},
        {"param": "stage", "value": stage, "note": "S1/S2/S3 never pooled"},
        {"param": "sim_only", "value": True, "note": "not PLC or field evidence"},
        {"param": "objective", "value": "lexicographic",
         "note": "offline-calibrated fixed thresholds; no runtime CI"},
        {"param": "score_policy", "value": SCORE_POLICY_ID,
         "note": "fixed weights isolate routing; not adaptive-weight evidence"},
        {"param": "online_failure_policy", "value": "TERMINATE_NO_FALLBACK",
         "note": "first placement failure ends that strategy run; partial P95 is non-comparable"},
        {"param": "score_weights", "value": json.dumps(SCORE_WEIGHTS),
         "note": "alpha,beta,gamma,delta"},
        {"param": "motion", "value": "trapezoid_accel",
         "note": "sim Tier 3 physical switch"},
        {"param": "p95_convention", "value": "sorted[min(n-1,int(n*0.95))]",
         "note": "seed-level P95; aggregate uses t-95% CI"},
        {"param": "scenarios", "value": ",".join(result["scenarios"]), "note": ""},
        {"param": "seeds", "value": ",".join(map(str, result["seeds"])), "note": ""},
    ]
    manifest_core = {
        "schema_version": SCHEMA_VERSION,
        "sim_only": True,
        "stage": stage,
        "scenarios": result["scenarios"],
        "seeds": result["seeds"],
        "modes": result.get("modes", list(dict.fromkeys(
            row["mode"] for row in result["detail"]
        ))),
        "score_policy": SCORE_POLICY_ID,
        "cell_count": len(result["cells"]),
        "run_count": len(result["detail"]),
        "runner_provenance": _runner_provenance(),
        "scenario_manifests": result["scenario_manifests"],
    }

    existing_manifest = None
    if paths["manifest"].exists():
        with paths["manifest"].open(encoding="utf-8") as fp:
            existing_manifest = json.load(fp)
        if _manifest_identity(existing_manifest) != _manifest_identity(manifest_core):
            raise FileExistsError(
                f"refusing to overwrite conflicting evidence stage: {output_dir}"
            )
    elif any(path.exists() for name, path in paths.items() if name != "manifest"):
        raise FileExistsError(
            f"refusing to overwrite incomplete evidence stage without manifest: {output_dir}"
        )

    # Build beside the targets, verify deterministic reruns, then replace the
    # manifest last so a partial write can never masquerade as complete evidence.
    with tempfile.TemporaryDirectory(prefix=".matrix-build-", dir=output_dir) as temp:
        temp_dir = Path(temp)
        temp_paths = {name: temp_dir / path.name for name, path in paths.items()}
        _write_csv(temp_paths["detail"], result["detail"])
        _write_csv(temp_paths["agg"], result["agg"])
        _write_csv(temp_paths["params"], params)
        output_hashes = {
            name: _sha256(path) for name, path in temp_paths.items() if name != "manifest"
        }
        if (existing_manifest is not None
                and existing_manifest.get("outputs_sha256") != output_hashes):
            raise FileExistsError(
                f"refusing to overwrite non-deterministic evidence stage: {output_dir}"
            )
        manifest = dict(manifest_core, outputs_sha256=output_hashes)
        with temp_paths["manifest"].open("w", encoding="utf-8") as fp:
            json.dump(manifest, fp, ensure_ascii=False, indent=2, sort_keys=True)
            fp.write("\n")
        for name in ("detail", "agg", "params", "manifest"):
            os.replace(temp_paths[name], paths[name])
    return {name: str(path) for name, path in paths.items()}


def write_outputs(result: Dict[str, Any], output_dir: os.PathLike,
                  stage: str) -> Dict[str, str]:
    if stage not in EVIDENCE_STAGES:
        raise ValueError(f"unsupported evidence stage: {stage!r}")
    stage_dir = Path(output_dir).resolve() / "cargo_dynamic_matrix" / stage
    stage_dir.mkdir(parents=True, exist_ok=True)
    with _exclusive_stage_lock(stage_dir):
        # Identity is deliberately read only after acquiring the lock.
        return _write_outputs_locked(result, stage_dir, stage)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=("s0", "s1", "s2", "s3"), default="s1")
    parser.add_argument("--scenarios", default="all",
                        help="comma-separated E ids; default all")
    parser.add_argument("--seeds", type=int, default=None,
                        help="use the first N seeds from the stage partition")
    parser.add_argument("--smoke", action="store_true",
                        help="E02/E10/E14/E15/E18 x first S1 seed")
    parser.add_argument("--out", default=str(OUT))
    args = parser.parse_args()

    if args.stage == "s0":
        path = Path(args.out) / "cargo_dynamic_matrix_s0.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fp:
            json.dump({"schema_version": SCHEMA_VERSION, "rows": s0_boundary_rows()},
                      fp, ensure_ascii=False, indent=2)
            fp.write("\n")
        print(f"S0 boundary evidence: {path}")
        return

    registry = cs.load_registry()
    if args.smoke:
        scenarios = SMOKE_SCENARIOS
        seeds = [stage_seeds("s1")[0]]
        stage = "smoke"
    else:
        scenarios = (list(registry["scenarios"]) if args.scenarios == "all"
                     else [item.strip() for item in args.scenarios.split(",") if item.strip()])
        seeds = stage_seeds(args.stage)
        if args.seeds is not None:
            if args.seeds <= 0:
                raise ValueError("--seeds must be positive")
            seeds = seeds[:args.seeds]
        stage = args.stage
    result = run_matrix(scenarios, seeds, stage=stage)
    paths = write_outputs(result, args.out, stage=stage)
    print(f"{len(result['cells'])} cells / {len(result['detail'])} runs; outputs={paths}")


if __name__ == "__main__":
    main()
