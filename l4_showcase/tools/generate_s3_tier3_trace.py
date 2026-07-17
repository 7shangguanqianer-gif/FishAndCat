# -*- coding: utf-8 -*-
"""Generate the 45 deterministic traces consumed by the S3 showcase.

Business state changes come exclusively from ``sim.realism.run_tier3`` via its
event sink.  This module adds presentation geometry, queue observability and a
display-only scan/exit tail; it never places, removes or reroutes cargo.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
import platform
import struct
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
SIM = ROOT / "sim"
if str(SIM) not in sys.path:
    sys.path.insert(0, str(SIM))

import cargo_scenarios as cs  # noqa: E402
import cargo_dynamic_matrix as cdm  # noqa: E402
import mixed_ops as mo  # noqa: E402
import realism  # noqa: E402
import strategy_lib as sl  # noqa: E402
import warehouse_sim as ws  # noqa: E402


TRACE_SCHEMA_VERSION = "s3-dynamic-trace-v2"
MANIFEST_SCHEMA_VERSION = "s3-trace-manifest-v2"
TRACE_TIERS = (1, 2, 3)
TRACE_PROFILES = ("uniform", "skew", "heavy")
UI_MODES = ("seq", "near", "score", "awra", "AUTO")
PROFILE_SCENARIOS = {"uniform": "E01", "skew": "E02", "heavy": "E03"}
TIER3_CANONICAL_PARAMS = {
    "handle_s": float(realism.HANDLE_S),
    "arrival_rho": float(realism.RHO_PEAK),
    "arrival_rho_off": float(realism.RHO_OFF),
    "freq_noise_sigma": float(realism.FREQ_SIGMA),
    "fault_mtbf_s": float(realism.MTBF_S),
    "fault_mttr_s": float(realism.MTTR_S),
}
MULTI_SEED_SOURCE = (
    "sim/out/cargo_dynamic_matrix/s1/cargo_dynamic_matrix_agg.csv"
)
MULTI_SEED_MANIFEST = (
    "sim/out/cargo_dynamic_matrix/s1/cargo_dynamic_matrix_manifest.json"
)
MULTI_SEED_DETAIL = (
    "sim/out/cargo_dynamic_matrix/s1/cargo_dynamic_matrix_detail.csv"
)
MULTI_SEED_PARAMS = (
    "sim/out/cargo_dynamic_matrix/s1/cargo_dynamic_matrix_params.csv"
)
TRACE_JS_PREFIX = "window.__S3_TRACE_REGISTER__("
JS_SAFE_INTEGER_MAX = (1 << 53) - 1


def _sha256(path: os.PathLike) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as fp:
        for chunk in iter(lambda: fp.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def canonical_payload_hash(trace: Dict[str, Any]) -> str:
    payload = {key: value for key, value in trace.items() if key != "payload_sha256"}
    return hashlib.sha256(_canonical_json(payload)).hexdigest()


def _semantic_runtime_bytes(value: Any) -> bytes:
    """Cross-language v1 encoding for the object actually parsed by JavaScript."""
    output = bytearray()

    def length(value_length: int) -> None:
        if not 0 <= value_length <= 0xFFFFFFFF:
            raise ValueError("semantic runtime value exceeds uint32 length contract")
        output.extend(struct.pack(">I", value_length))

    def encode(item: Any) -> None:
        if item is None:
            output.append(0x00)
        elif item is False:
            output.append(0x01)
        elif item is True:
            output.append(0x02)
        elif isinstance(item, (int, float)) and not isinstance(item, bool):
            if isinstance(item, int) and abs(item) > JS_SAFE_INTEGER_MAX:
                raise ValueError("integer exceeds JavaScript safe integer contract")
            number = float(item)
            if not math.isfinite(number):
                raise ValueError("semantic runtime numbers must be finite")
            output.append(0x03)
            output.extend(struct.pack(">d", number))
        elif isinstance(item, str):
            encoded = item.encode("utf-8")
            output.append(0x04)
            length(len(encoded))
            output.extend(encoded)
        elif isinstance(item, (list, tuple)):
            output.append(0x05)
            length(len(item))
            for child in item:
                encode(child)
        elif isinstance(item, dict):
            if not all(isinstance(key, str) for key in item):
                raise ValueError("semantic runtime object keys must be strings")
            keys = sorted(item)
            output.append(0x06)
            length(len(keys))
            for key in keys:
                encode(key)
                encode(item[key])
        else:
            raise ValueError(f"unsupported semantic runtime type: {type(item).__name__}")

    encode(value)
    return bytes(output)


def semantic_runtime_payload_hash(trace: Dict[str, Any]) -> str:
    payload = {
        key: value for key, value in trace.items()
        if key not in {"payload_sha256", "semantic_runtime_sha256_v1"}
    }
    return hashlib.sha256(_semantic_runtime_bytes(payload)).hexdigest()


def validate_s1_matrix_manifest(manifest: Dict[str, Any],
                                actual_output_sha256: Dict[str, str]) -> None:
    """Fail closed unless the aggregate belongs to the locked S1 experiment."""
    expected_modes = list(mo.DYNAMIC_STRATS) + ["AUTO"]
    expected_scenarios = list(cs.load_registry()["scenarios"])
    checks = {
        "schema_version": manifest.get("schema_version") == "cargo_dynamic_matrix_v1",
        "stage": manifest.get("stage") == "s1",
        "seeds": manifest.get("seeds") == list(range(2026, 2036)),
        "modes": manifest.get("modes") == expected_modes,
        "scenarios": manifest.get("scenarios") == expected_scenarios,
        "cell_count": manifest.get("cell_count") == 180,
        "run_count": manifest.get("run_count") == 1440,
        "score_policy": manifest.get("score_policy") == "fixed_default_v1_router_isolation",
        "sim_only": manifest.get("sim_only") is True,
        "outputs_sha256": manifest.get("outputs_sha256") == actual_output_sha256,
    }
    runner = manifest.get("runner_provenance", {})
    current_runner = cdm._runner_provenance()
    checks["runner_source"] = (
        runner.get("source_sha256") == current_runner["source_sha256"]
    )
    checks["runner_functions"] = (
        runner.get("function_sha256") == current_runner["function_sha256"]
    )
    scenario_manifests = manifest.get("scenario_manifests", {})
    checks["scenario_manifests"] = (
        set(scenario_manifests) == set(expected_scenarios)
        and all(item.get("sim_only") is True
                for item in scenario_manifests.values())
    )
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise ValueError(f"S1 matrix evidence identity mismatch: {','.join(failed)}")


def _read_stable_file_set(paths: Dict[str, Path], attempts: int = 3,
                          reader=None) -> Dict[str, bytes]:
    """Return two consecutive identical reads or fail closed."""
    read = reader or (lambda path: path.read_bytes())
    for _ in range(attempts):
        first = {name: read(path) for name, path in paths.items()}
        second = {name: read(path) for name, path in paths.items()}
        if first == second:
            return first
    raise RuntimeError("S1 matrix evidence was unstable during snapshot read")


def _csv_rows(content: bytes, label: str) -> Tuple[List[str], List[Dict[str, str]]]:
    try:
        reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
        rows = list(reader)
    except (UnicodeDecodeError, csv.Error) as exc:
        raise ValueError(f"invalid S1 {label} CSV: {exc}") from exc
    if not reader.fieldnames or any(None in row for row in rows):
        raise ValueError(f"invalid S1 {label} CSV structure")
    return list(reader.fieldnames), rows


def validate_s1_output_content(contents: Dict[str, bytes],
                               manifest: Dict[str, Any]) -> None:
    """Validate the locked S1 aggregate/detail/params semantic coverage."""
    scenarios = list(manifest["scenarios"])
    modes = list(manifest["modes"])
    seeds = list(manifest["seeds"])
    score_policy = manifest["score_policy"]

    agg_fields, agg_rows = _csv_rows(contents["agg"], "aggregate")
    required_agg = {
        "schema_version", "sim_only", "scenario", "mode", "n_runs",
        "score_policy", "extended_pressure", "canonical_g2",
        "headline_eligible",
    }
    agg_keys = [(row["scenario"], row["mode"]) for row in agg_rows]
    expected_agg = {(scenario, mode) for scenario in scenarios for mode in modes}
    agg_ok = (
        required_agg.issubset(agg_fields)
        and len(agg_rows) == len(expected_agg) == 144
        and len(set(agg_keys)) == len(agg_keys)
        and set(agg_keys) == expected_agg
        and all(row["schema_version"] == "cargo_dynamic_matrix_v1"
                and row["sim_only"].lower() == "true"
                and row["score_policy"] == score_policy
                and int(row["n_runs"]) == len(seeds)
                for row in agg_rows)
    )
    if not agg_ok:
        raise ValueError("S1 aggregate CSV is not the complete 18x8 sim-only matrix")

    detail_fields, detail_rows = _csv_rows(contents["detail"], "detail")
    required_detail = {
        "schema_version", "sim_only", "scenario", "seed", "mode", "stage",
        "score_policy", "fairness_pass",
    }
    detail_keys = [
        (row["scenario"], int(row["seed"]), row["mode"]) for row in detail_rows
    ]
    expected_detail = {
        (scenario, seed, mode)
        for scenario in scenarios for seed in seeds for mode in modes
    }
    detail_ok = (
        required_detail.issubset(detail_fields)
        and len(detail_rows) == len(expected_detail) == 1440
        and len(set(detail_keys)) == len(detail_keys)
        and set(detail_keys) == expected_detail
        and all(row["schema_version"] == "cargo_dynamic_matrix_v1"
                and row["sim_only"].lower() == "true"
                and row["stage"] == "s1"
                and row["score_policy"] == score_policy
                and row["fairness_pass"].lower() == "true"
                for row in detail_rows)
    )
    if not detail_ok:
        raise ValueError("S1 detail CSV is not the complete fair 18x10x8 matrix")

    param_fields, param_rows = _csv_rows(contents["params"], "params")
    param_map = {row["param"]: row["value"] for row in param_rows}
    required_params = {
        "schema_version", "stage", "sim_only", "objective", "score_policy",
        "online_failure_policy", "score_weights", "motion", "p95_convention",
        "scenarios", "seeds",
    }
    expected_params = {
        "schema_version": "cargo_dynamic_matrix_v1",
        "stage": "s1",
        "sim_only": "True",
        "objective": "lexicographic",
        "score_policy": score_policy,
        "online_failure_policy": "TERMINATE_NO_FALLBACK",
        "score_weights": "[1.0, 0.6, 0.4, 0.15]",
        "motion": "trapezoid_accel",
        "p95_convention": "sorted[min(n-1,int(n*0.95))]",
        "scenarios": ",".join(scenarios),
        "seeds": ",".join(str(seed) for seed in seeds),
    }
    params_ok = (
        {"param", "value", "note"}.issubset(param_fields)
        and len(param_map) == len(param_rows)
        and set(param_map) == required_params == set(expected_params)
        and param_map == expected_params
    )
    if not params_ok:
        raise ValueError("S1 params CSV contract is incomplete or inconsistent")


def _default_s1_paths() -> Dict[str, Path]:
    return {
        "manifest": ROOT / MULTI_SEED_MANIFEST,
        "agg": ROOT / MULTI_SEED_SOURCE,
        "detail": ROOT / MULTI_SEED_DETAIL,
        "params": ROOT / MULTI_SEED_PARAMS,
    }


def load_s1_matrix_reference(
        paths: Dict[str, os.PathLike] | None = None) -> Dict[str, Any]:
    using_default_paths = paths is None
    paths = _default_s1_paths() if paths is None else {
        name: Path(path) for name, path in paths.items()
    }
    if set(paths) != {"manifest", "agg", "detail", "params"}:
        raise ValueError("S1 evidence paths must name manifest/agg/detail/params")
    if not all(path.is_file() for path in paths.values()):
        raise FileNotFoundError("locked S1 matrix evidence set is unavailable")
    contents = _read_stable_file_set(paths)
    try:
        manifest = json.loads(contents["manifest"].decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid S1 matrix manifest: {exc}") from exc
    output_sha256 = {
        name: hashlib.sha256(contents[name]).hexdigest()
        for name in ("agg", "detail", "params")
    }
    validate_s1_matrix_manifest(manifest, output_sha256)
    validate_s1_output_content(contents, manifest)
    manifest_sha256 = hashlib.sha256(contents["manifest"]).hexdigest()
    display_paths = (
        {
            "manifest": MULTI_SEED_MANIFEST,
            "agg": MULTI_SEED_SOURCE,
            "detail": MULTI_SEED_DETAIL,
            "params": MULTI_SEED_PARAMS,
        }
        if using_default_paths
        else {name: str(path.resolve()) for name, path in paths.items()}
    )
    return {
        "path": display_paths["agg"],
        "sha256": output_sha256["agg"],
        "manifest_path": display_paths["manifest"],
        "manifest_sha256": manifest_sha256,
        "detail_path": display_paths["detail"],
        "detail_sha256": output_sha256["detail"],
        "params_path": display_paths["params"],
        "params_sha256": output_sha256["params"],
        "output_sha256": output_sha256,
        "content_contract": {
            "aggregate_rows": 144,
            "detail_rows": 1440,
            "scenario_mode_cells": 144,
            "sim_only": True,
        },
        "stage": manifest["stage"],
        "seeds": manifest["seeds"],
        "modes": manifest["modes"],
        "scenarios": manifest["scenarios"],
        "cell_count": manifest["cell_count"],
        "run_count": manifest["run_count"],
        "score_policy": manifest["score_policy"],
        "runner_provenance": manifest["runner_provenance"],
    }


def assert_s1_matrix_reference_unchanged(
        locked_reference: Dict[str, Any],
        paths: Dict[str, os.PathLike] | None = None) -> Dict[str, Any]:
    """Re-read S1 evidence and reject a mixed-identity bundle before publish."""
    current_reference = load_s1_matrix_reference(paths)
    if _canonical_json(current_reference) != _canonical_json(locked_reference):
        raise RuntimeError("S1 matrix evidence changed during trace bundle generation")
    return current_reference


def _grade(weight: float) -> str:
    return "light" if weight <= 30.0 else ("mid" if weight <= 60.0 else "heavy")


def _good_payload(good, freq_est: float, source: str) -> Dict[str, Any]:
    return {
        "gid": int(good.gid),
        "name": good.name,
        "weight_kg": float(good.weight),
        "freq_true": float(good.freq),
        "freq_est": float(freq_est),
        "volume_m3": float(good.vol),
        "grade": _grade(good.weight),
        "source": source,
    }


def _tier_config(tier: int) -> Dict[str, Any]:
    if tier == 1:
        return {
            "tier": 1,
            "label": "Tier 1 数据模型",
            "motion": "constant_speed",
            "accel": False,
            "arrival_model": "fixed_no_queue_geometry_bound",
            "score_policy": "fixed_default",
            "params": {
                "handle_s": 0.0,
                "arrival_rho": 0.0,
                "arrival_rho_off": 0.0,
                "freq_noise_sigma": 0.0,
                "fault_mtbf_s": 1.0e12,
                "fault_mttr_s": 0.0,
            },
        }
    if tier == 2:
        return {
            "tier": 2,
            "label": "Tier 2 加减速设计 sim",
            "motion": "trapezoid_accel",
            "accel": True,
            "arrival_model": "fixed_no_queue_geometry_bound",
            "score_policy": "lookup_weights_sim_design",
            "params": {
                "handle_s": 0.0,
                "arrival_rho": 0.0,
                "arrival_rho_off": 0.0,
                "freq_noise_sigma": 0.0,
                "fault_mtbf_s": 1.0e12,
                "fault_mttr_s": 0.0,
            },
        }
    if tier == 3:
        return {
            "tier": 3,
            "label": "Tier 3 综合情景 sim",
            "motion": "trapezoid_accel",
            "accel": True,
            "arrival_model": "poisson_peak_offpeak",
            "score_policy": "lookup_weights_sim_design",
            "params": dict(TIER3_CANONICAL_PARAMS),
        }
    raise ValueError(f"unsupported trace tier: {tier}")


def _score_functions(goods, profile: str, tier: int):
    w_max = max(g.weight for g in goods)
    f_max = max(g.freq for g in goods)
    if tier == 1:
        online_weights = batch_weights = (1.0, 0.6, 0.4, 0.15)
    else:
        delta_online, bg_online = ws.lookup_weights(len(goods), profile, "online")
        delta_batch, bg_batch = ws.lookup_weights(len(goods), profile, "batch")
        online_weights = (1.0, bg_online / 2.0, bg_online / 2.0, delta_online)
        batch_weights = (1.0, bg_batch / 2.0, bg_batch / 2.0, delta_batch)
    fn = ws.make_score_fn(*online_weights, w_max, f_max)
    fn_batch = ws.make_score_fn(*batch_weights, w_max, f_max)
    return fn, fn_batch, w_max, f_max, online_weights, batch_weights


def _streams(goods, workload, fn, fn_batch, w_max, f_max,
             config: Dict[str, Any], seed: int):
    params = config["params"]
    if config["tier"] == 3:
        arrivals, reference_pair_s = realism.common_arrivals_for_workload(
            goods, workload, fn, w_max, f_max, fn_batch, seed=seed,
            tier3_params=params,
        )
        fault_intervals = realism.build_fault_intervals(
            workload["scheduled_cycles"], seed, params["fault_mtbf_s"]
        )
    else:
        reference_pair_s = (
            3.0 * ws.t_max_now() + 2.0 * params["handle_s"] + 1.0
        )
        arrivals = [index * reference_pair_s
                    for index in range(workload["scheduled_cycles"])]
        fault_intervals = [1.0e12] * (workload["scheduled_cycles"] + 1)
    all_inbound = [item["inbound_good"] for item in workload["cycles"]]
    noise_stream = realism.build_noise_stream(
        goods, all_inbound, params["freq_noise_sigma"], seed
    )
    return arrivals, reference_pair_s, fault_intervals, noise_stream


def _phase_base(phase: Dict[str, Any]) -> str:
    return (phase.get("operation_phase")
            if phase["name"] == "FAULT_RECOVERY" else phase["name"])


def _phase_geometry(event: Dict[str, Any], phase: Dict[str, Any]) -> Dict[str, Any]:
    base = _phase_base(phase)
    store = [event["store_slot"]["col"], event["store_slot"]["tier"]]
    retrieve = [event["retrieve_slot"]["col"], event["retrieve_slot"]["tier"]]
    io = [0, 0]
    mapping = {
        "QUEUE": (io, io, "QUEUE", event["inbound_gid"]),
        "INBOUND_TRAVEL": (io, store, "CARRIER_IN", event["inbound_gid"]),
        "STORE_HANDLE": (store, store, "CARRIER_IN", event["inbound_gid"]),
        "LINK_TRAVEL": (store, retrieve, None, None),
        "RETRIEVE_HANDLE": (retrieve, retrieve, "CARRIER_OUT", event["outbound_gid"]),
        "OUTBOUND_TRAVEL": (retrieve, io, "CARRIER_OUT", event["outbound_gid"]),
    }
    if base not in mapping:
        raise ValueError(f"unmapped engine phase: {phase!r}")
    origin, target, owner, gid = mapping[base]
    enriched = dict(phase)
    frozen = phase.get("frozen_u")
    enriched.update({
        "from": origin,
        "to": target,
        "u0": float(phase.get("u0", frozen if frozen is not None else 0.0)),
        "u1": float(phase.get("u1", frozen if frozen is not None else 1.0)),
        "cargo_owner": owner,
        "cargo_gid": gid,
    })
    return enriched


def _span(phases: Sequence[Dict[str, Any]], name: str,
          fallback: float) -> Tuple[float, float]:
    matching = [phase for phase in phases if _phase_base(phase) == name]
    if not matching:
        return fallback, fallback
    return matching[0]["t0"], matching[-1]["t1"]


def _process_steps(event: Dict[str, Any], phases: Sequence[Dict[str, Any]]):
    owners = event["ownership_events"]
    stored_t = owners[1]["t"]
    retrieved_t = owners[2]["t"]
    finish = event["finish"]
    specs = [
        ("LOAD_IN", event["start"], event["start"], event["inbound_gid"],
         "CARRIER_IN", False, 0.8),
        ("INBOUND_TRAVEL", *_span(phases, "INBOUND_TRAVEL", event["start"]),
         event["inbound_gid"], "CARRIER_IN", True, 0.0),
        ("STORE_HANDLE", *_span(phases, "STORE_HANDLE", stored_t),
         event["inbound_gid"], "CARRIER_IN", True, 0.0),
        ("LINK_TRAVEL", *_span(phases, "LINK_TRAVEL", stored_t),
         None, None, True, 0.0),
        ("RETRIEVE_HANDLE", *_span(phases, "RETRIEVE_HANDLE", retrieved_t),
         event["outbound_gid"], "CARRIER_OUT", True, 0.0),
        ("OUTBOUND_TRAVEL", *_span(phases, "OUTBOUND_TRAVEL", finish),
         event["outbound_gid"], "CARRIER_OUT", True, 0.0),
        ("SCAN_EXIT", finish, finish, event["outbound_gid"],
         "OUTFEED", False, 2.4),
    ]
    return [
        {
            "name": name, "t0": t0, "t1": t1, "cargo_gid": gid,
            "cargo_owner": owner, "sim_modelled": sim_modelled,
            "display_duration_s": display_duration,
        }
        for name, t0, t1, gid, owner, sim_modelled, display_duration in specs
    ]


def _enrich_event(event: Dict[str, Any], records, arrivals) -> Dict[str, Any]:
    enriched = dict(event)
    phases = [_phase_geometry(event, phase) for phase in event["phases"]]
    cycle = event["cycle"]
    pending = [
        records[index]["inbound_good"].gid
        for index in range(cycle, len(records))
        if records[index].get("dispatch", True) and arrivals[index] <= event["start"]
    ]
    if not pending or pending[0] != event["inbound_gid"]:
        raise RuntimeError(f"queue head diverged at cycle {cycle}")
    finish = event["finish"]
    lifecycle_tail = [
        {"t": finish, "display_offset_s": 0.8, "gid": event["outbound_gid"],
         "from": "OUTFEED", "to": "SCANNED", "sim_modelled": False},
        {"t": finish, "display_offset_s": 1.6, "gid": event["outbound_gid"],
         "from": "SCANNED", "to": "EXIT_MASK", "sim_modelled": False},
        {"t": finish, "display_offset_s": 2.4, "gid": event["outbound_gid"],
         "from": "EXIT_MASK", "to": "CONSUMED", "sim_modelled": False},
    ]
    enriched.update({
        "cycle_number": cycle + 1,
        "phases": phases,
        "process_steps": _process_steps(event, phases),
        "queue_gids_including_active": pending,
        "queue_waiting_gids": pending[1:],
        "queue_depth_waiting": max(0, len(pending) - 1),
        "ownership_events": [dict(item, sim_modelled=True)
                             for item in event["ownership_events"]] + lifecycle_tail,
        "display_lifecycle_s": 2.4,
        "performance_finish_s": finish,
    })
    return enriched


def _source_provenance(scenario_id: str,
                       matrix_reference: Dict[str, Any]) -> Dict[str, Any]:
    scenario_manifest = cs.scenario_manifest(scenario_id)
    sources = dict(scenario_manifest["source_sha256"])
    sources["l4_showcase/tools/generate_s3_tier3_trace.py"] = _sha256(__file__)
    return {
        "source_sha256": sources,
        "function_sha256": scenario_manifest["function_sha256"],
        "s1_matrix_manifest_sha256": matrix_reference["manifest_sha256"],
        "s1_matrix_agg_sha256": matrix_reference["sha256"],
        "s1_matrix_runner_provenance": matrix_reference["runner_provenance"],
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
    }


def _comparability(config: Dict[str, Any], matrix_reference: Dict[str, Any]):
    if config["tier"] == 3:
        mismatch = ["score_policy", "freq_noise_sigma"]
    elif config["tier"] == 2:
        mismatch = [
            "tier", "arrival_model", "score_policy", "freq_noise_sigma",
            "handle_s", "fault_model",
        ]
    else:
        mismatch = [
            "tier", "motion", "arrival_model", "score_policy",
            "freq_noise_sigma", "handle_s", "fault_model",
        ]
    return {
        "s1_matrix_same_parameterization": False,
        "mismatch_fields": mismatch,
        "ui_rule": "do_not_compare_or_merge",
        "matrix_evidence_role": "separate_fixed_score_router_isolation_context",
        "trace_parameterization": {
            "tier": config["tier"],
            "motion": config["motion"],
            "arrival_model": config["arrival_model"],
            "score_policy": config["score_policy"],
            "freq_noise_sigma": config["params"]["freq_noise_sigma"],
        },
        "matrix_parameterization": {
            "tier": 3,
            "score_policy": matrix_reference["score_policy"],
            "freq_noise_sigma_for_E01_E03": 0.0,
            "stage": matrix_reference["stage"],
        },
    }


def build_trace(tier: int = 3, profile: str = "skew",
                strategy_mode: str = "awra", cycles: int = 100,
                seed: int = realism.SEED,
                matrix_reference: Dict[str, Any] | None = None) -> Dict[str, Any]:
    if profile not in PROFILE_SCENARIOS:
        raise ValueError(f"unsupported trace profile: {profile}")
    if strategy_mode not in UI_MODES:
        raise ValueError(f"unsupported UI strategy mode: {strategy_mode}")
    config = _tier_config(int(tier))
    if matrix_reference is None:
        matrix_reference = load_s1_matrix_reference()
    scenario_id = PROFILE_SCENARIOS[profile]
    scenario = cs.load_registry()["scenarios"][scenario_id]
    if int(cycles) != int(scenario["scheduled_cycles"]):
        raise ValueError(
            f"trace cycles must match registered workload: {scenario['scheduled_cycles']}"
        )

    old_accel = ws.ACCEL
    ws.ACCEL = config["accel"]
    try:
        goods = cs.build_initial_goods(scenario_id, seed)
        inbound = cs.build_inbound_goods(scenario_id, seed, cycles)
        workload = mo.build_scenario_workload(goods, inbound, scenario, seed)
        fn, fn_batch, w_max, f_max, online_weights, batch_weights = _score_functions(
            goods, profile, tier
        )
        arrivals, reference_pair_s, fault_intervals, noise_stream = _streams(
            goods, workload, fn, fn_batch, w_max, f_max, config, seed
        )
        events = []
        metrics = realism.run_tier3(
            strategy_mode, goods, workload["valid_inbound_goods"], workload["requests"],
            fn, w_max, f_max, fn_batch, arrivals=arrivals, cycles=cycles, seed=seed,
            workload=workload, fault_intervals=fault_intervals,
            event_sink=events, noise_stream=noise_stream,
            tier3_params=config["params"], router_objective="lexicographic",
            batch_known=True,
        )
    finally:
        ws.ACCEL = old_accel

    if metrics["status"] != "FEASIBLE" or len(events) != cycles:
        raise RuntimeError(
            f"UI trace must be complete: tier={tier}/{profile}/{strategy_mode}, "
            f"status={metrics['status']}, events={len(events)}/{cycles}"
        )
    enriched_events_full = [
        _enrich_event(event, workload["cycles"], arrivals) for event in events
    ]
    initial_inventory = enriched_events_full[0]["inventory_before"]
    snapshot_pool = [initial_inventory]
    enriched_events = []
    for index, event in enumerate(enriched_events_full):
        if event["inventory_before"] != snapshot_pool[-1]:
            raise RuntimeError(f"inventory snapshot chain diverged at cycle {index}")
        compact = dict(event)
        compact.pop("inventory_before")
        compact.pop("inventory_after")
        compact["inventory_before_ref"] = index
        compact["inventory_after_ref"] = index + 1
        snapshot_pool.append(event["inventory_after"])
        enriched_events.append(compact)
    final_inventory = snapshot_pool[-1]
    initial_factors = noise_stream["initial"]
    inbound_factors = noise_stream["inbound"]
    catalog = [
        _good_payload(good, good.freq * initial_factors[good.gid], "initial")
        for good in goods
    ] + [
        _good_payload(good, good.freq * inbound_factors[good.gid], "inbound")
        for good in inbound
    ]
    catalog.sort(key=lambda item: item["gid"])
    queue_peak = max(event["queue_depth_waiting"] for event in enriched_events)
    trace_id = f"t{tier}_{profile}_{strategy_mode.lower()}"
    trace = {
        "schema_version": TRACE_SCHEMA_VERSION,
        "source": "sim.realism.run_tier3:event_sink",
        "sim_only": True,
        "meta": {
            "trace_id": trace_id,
            "tier": int(tier),
            "tier_label": config["label"],
            "profile": profile,
            "scenario_id": scenario_id,
            "strategy_mode": strategy_mode,
            "picked_strategy": metrics["picked_strategy"],
            "seed": int(seed),
            "cycles": int(cycles),
            "motion": config["motion"],
            "arrival_model": config["arrival_model"],
            "score_policy": config["score_policy"],
            "score_weights": {
                "online": list(online_weights), "batch": list(batch_weights)
            },
            "tier3_params": dict(config["params"]),
            "rule": realism.RULE,
            "preoccupied": sum(
                ws.preoccupied(col, tier_index, realism.RULE)
                for col in range(ws.COLS) for tier_index in range(ws.TIERS)
            ),
            "reference_pair_s": reference_pair_s,
            "display_tail_modelled": False,
        },
        "router": metrics["router"],
        "comparability": _comparability(config, matrix_reference),
        "stream_hashes": metrics["stream_hashes"],
        "cargo_catalog": catalog,
        "arrivals": [
            {"cycle": index, "time": time,
             "inbound_gid": workload["cycles"][index]["inbound_good"].gid}
            for index, time in enumerate(arrivals)
        ],
        "initial_inventory": initial_inventory,
        "inventory_snapshots": snapshot_pool,
        "events": enriched_events,
        "final_inventory": final_inventory,
        "stats": {
            "scope": "single_seed_representative_replay",
            "definition": "Tier 3 system response includes queue/handling/fault only when tier=3",
            "response_sample_n": metrics["response_sample_n"],
            "response_p50_s": metrics["resp_p50"],
            "response_p95_s": metrics["resp_p95"],
            "avg_retrieve_s": metrics["avg_retr"],
            "travel_dual_s": metrics["tot_dual"],
            "busy_total_s": metrics["busy_total"],
            "utilization": metrics["util"],
            "faults": metrics["n_down"],
            "downtime_s": metrics["downtime"],
            "queue_peak_waiting": queue_peak,
            "fails": metrics["fails"],
            "violations": metrics["viol"],
            "performance_finish_s": metrics["makespan_s"],
            "multi_seed_source": matrix_reference,
            "multi_seed_scope": (
                "separate S1 Tier 3 fixed-score routing-isolation evidence; "
                "parameterization differs and UI must not compare or merge"
            ),
        },
        "provenance": {
            **_source_provenance(scenario_id, matrix_reference),
            "generation_command": (
                "python l4_showcase/tools/generate_s3_tier3_trace.py "
                f"--seed {seed} --cycles {cycles}"
            ),
        },
    }
    trace["semantic_runtime_sha256_v1"] = semantic_runtime_payload_hash(trace)
    trace["payload_sha256"] = canonical_payload_hash(trace)
    return trace


def _trace_js(trace: Dict[str, Any]) -> bytes:
    return (
        TRACE_JS_PREFIX.encode("ascii")
        + _canonical_json(trace["meta"]["trace_id"])
        + b","
        + _canonical_json(trace)
        + b");\n"
    )


def generate_trace_bundle(output_dir: os.PathLike, seed: int = realism.SEED,
                          cycles: int = 100) -> Dict[str, Any]:
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    locked_matrix_reference = load_s1_matrix_reference()
    entries = []
    with tempfile.TemporaryDirectory(prefix=".trace-build-", dir=output_dir) as temp:
        temp_root = Path(temp)
        temp_trace_dir = temp_root / "s3_traces"
        temp_trace_dir.mkdir()
        for tier in TRACE_TIERS:
            for profile in TRACE_PROFILES:
                for strategy_mode in UI_MODES:
                    trace = build_trace(
                        tier=tier, profile=profile, strategy_mode=strategy_mode,
                        cycles=cycles, seed=seed,
                        matrix_reference=locked_matrix_reference,
                    )
                    filename = f"{trace['meta']['trace_id']}.js"
                    path = temp_trace_dir / filename
                    content = _trace_js(trace)
                    path.write_bytes(content)
                    entries.append({
                        "trace_id": trace["meta"]["trace_id"],
                        "tier": tier,
                        "profile": profile,
                        "strategy_mode": strategy_mode,
                        "picked_strategy": trace["meta"]["picked_strategy"],
                        "seed": int(seed),
                        "cycles": int(cycles),
                        "schema_version": TRACE_SCHEMA_VERSION,
                        "sim_only": True,
                        "file": f"s3_traces/{filename}",
                        "bytes": len(content),
                        "file_sha256": hashlib.sha256(content).hexdigest(),
                        "payload_sha256": trace["payload_sha256"],
                        "semantic_runtime_sha256_v1": trace[
                            "semantic_runtime_sha256_v1"
                        ],
                        "faults": trace["stats"]["faults"],
                    })
        assert_s1_matrix_reference_unchanged(locked_matrix_reference)
        manifest = {
            "schema_version": MANIFEST_SCHEMA_VERSION,
            "trace_schema_version": TRACE_SCHEMA_VERSION,
            "sim_only": True,
            "seed": int(seed),
            "cycles": int(cycles),
            "tiers": list(TRACE_TIERS),
            "profiles": list(TRACE_PROFILES),
            "ui_modes": list(UI_MODES),
            "entry_count": len(entries),
            "matrix_reference": locked_matrix_reference,
            "comparability_policy": {
                "s1_matrix_same_parameterization": False,
                "ui_rule": "do_not_compare_or_merge",
                "matrix_evidence_role": (
                    "separate_fixed_score_router_isolation_context"
                ),
            },
            "generation_provenance": {
                "generator_path": "l4_showcase/tools/generate_s3_tier3_trace.py",
                "generator_sha256": _sha256(__file__),
                "python": platform.python_version(),
                "implementation": platform.python_implementation(),
            },
            "limits": {"trace_bytes": 800 * 1024, "manifest_js_bytes": 100 * 1024},
            "entries": entries,
        }
        manifest_json = json.dumps(
            manifest, ensure_ascii=False, indent=2, sort_keys=True
        ).encode("utf-8") + b"\n"
        manifest_js = (
            b"window.S3_TRACE_MANIFEST=" + _canonical_json(manifest) + b";\n"
        )
        if any(entry["bytes"] > manifest["limits"]["trace_bytes"] for entry in entries):
            raise RuntimeError("one or more trace files exceed 800 KB")
        if len(manifest_js) > manifest["limits"]["manifest_js_bytes"]:
            raise RuntimeError("trace manifest exceeds 100 KB")
        (temp_root / "s3_trace_manifest.json").write_bytes(manifest_json)
        (temp_root / "s3_trace_manifest.js").write_bytes(manifest_js)

        # Keep the last evidence check immediately adjacent to publication.
        assert_s1_matrix_reference_unchanged(locked_matrix_reference)
        target_trace_dir = output_dir / "s3_traces"
        target_trace_dir.mkdir(exist_ok=True)
        for entry in entries:
            source = temp_root / entry["file"]
            target = output_dir / entry["file"]
            os.replace(source, target)
        os.replace(temp_root / "s3_trace_manifest.json",
                   output_dir / "s3_trace_manifest.json")
        os.replace(temp_root / "s3_trace_manifest.js",
                   output_dir / "s3_trace_manifest.js")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=realism.SEED)
    parser.add_argument("--cycles", type=int, default=100)
    parser.add_argument("--out", default=str(ROOT / "l4_showcase" / "out"))
    args = parser.parse_args()
    manifest = generate_trace_bundle(args.out, seed=args.seed, cycles=args.cycles)
    print(json.dumps({
        "manifest": str(Path(args.out).resolve() / "s3_trace_manifest.js"),
        "entries": manifest["entry_count"],
        "max_trace_bytes": max(entry["bytes"] for entry in manifest["entries"]),
        "fault_traces": sum(entry["faults"] > 0 for entry in manifest["entries"]),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
