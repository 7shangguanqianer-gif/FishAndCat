# -*- coding: utf-8 -*-
"""S3 独立 fill-only 数据门。

本模块只描述从 0/267 管理货物填到 267/267 的入库过程；133 个官方
``(col+tier)%3==0`` 预占格始终不可管理。它不复用 mixed IN/OUT trace，也不
产生出库、扫描或消失事件，避免把旧 100 周期混合作业剪接成伪填满证据。
"""
from __future__ import annotations

import hashlib
import json
import os
import copy
import platform
import threading
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Sequence, Tuple

import numpy as np
import scipy
import warehouse_sim as ws


SCHEMA_VERSION = "s3-fill-comparison-v1"
AUDIT_SCHEMA_VERSION = "s3-fill-candidate-audit-v1"
PROFILE_ID = "FILL_CANONICAL_SAFE"
RULE = "sum"
TOTAL_SLOTS = ws.COLS * ws.TIERS
PREOCCUPIED_SLOTS = sum(
    ws.preoccupied(col, tier, RULE)
    for col in range(ws.COLS) for tier in range(ws.TIERS)
)
MANAGED_CAPACITY = TOTAL_SLOTS - PREOCCUPIED_SLOTS
SCORE_POLICY_ID = "fixed_prior_bounds_v2_router_isolation"
SCORE_WEIGHTS = (1.0, 0.6, 0.4, 0.15)
SCORE_WEIGHT_MAX_KG = 60.0
SCORE_FREQ_MAX = 100.0
ONLINE_ALGORITHMS = ("seq", "near", "score")
CHECKPOINT_COUNTS = (0, 67, 134, 201, 241, 267)
CHECKPOINT_LABELS = ("0%", "25%", "50%", "75%", "90%", "100%")
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEPENDENCY_LOCK = PROJECT_ROOT / "l4_showcase" / "evidence" / "s3_fill_requirements.lock"
_ACCEL_LOCK = threading.RLock()
_LOCKED_RUNTIME_KEYS = ("python", "numpy", "scipy")


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def payload_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def file_sha256(path: os.PathLike[str] | str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_dependency_lock(path: os.PathLike[str] | str | None = None) -> Dict[str, str]:
    """解析并严格校验 fill evidence 运行时版本锁。"""
    lock_path = Path(path) if path is not None else DEPENDENCY_LOCK
    if not lock_path.is_file():
        raise RuntimeError(f"missing dependency lock: {lock_path}")
    locked: Dict[str, str] = {}
    for line_number, raw in enumerate(lock_path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.count("==") != 1:
            raise RuntimeError(f"malformed dependency lock line {line_number}")
        name, version = (item.strip() for item in line.split("==", 1))
        if name not in _LOCKED_RUNTIME_KEYS or not version or name in locked:
            raise RuntimeError(f"invalid dependency lock entry on line {line_number}")
        locked[name] = version
    if tuple(sorted(locked)) != tuple(sorted(_LOCKED_RUNTIME_KEYS)):
        raise RuntimeError("dependency lock must contain exactly python, numpy, scipy")
    return locked


def enforce_dependency_lock(path: os.PathLike[str] | str | None = None) -> Dict[str, str]:
    """运行时与版本锁逐项相等，否则拒绝生成或验证 release。"""
    locked = read_dependency_lock(path)
    actual = {
        "python": platform.python_version(),
        "numpy": np.__version__,
        "scipy": scipy.__version__,
    }
    mismatch = {
        key: {"locked": locked[key], "actual": actual[key]}
        for key in _LOCKED_RUNTIME_KEYS if locked[key] != actual[key]
    }
    if mismatch:
        raise RuntimeError(
            "dependency lock mismatch: "
            + ", ".join(
                f"{key} locked={item['locked']} actual={item['actual']}"
                for key, item in mismatch.items()
            )
        )
    return locked


def _round(value: float) -> float:
    return round(float(value), 9)


@contextmanager
def _accel_true_context():
    """串行保护 warehouse_sim 的进程级 ACCEL 开关。"""
    with _ACCEL_LOCK:
        old_accel = ws.ACCEL
        ws.ACCEL = True
        try:
            yield
        finally:
            ws.ACCEL = old_accel


def _with_accel_true(fn: Callable[[], Any]) -> Any:
    with _accel_true_context():
        return fn()


def build_fill_goods(count: int = MANAGED_CAPACITY, seed: int = 2026,
                     case: str = "skew") -> List[ws.Good]:
    """构造可填满口径货物。

    复用现有 ``gen_goods`` 的频次、体积和 case 分布，只把 5..80 kg 线性映射到
    5..60 kg。最高层限重为 62 kg，因此该 profile 刻意隔离“物理不可装”因素；
    它只能证明容量与事件链，不是随机重货压力测试。
    """
    if case not in {"uniform", "skew", "heavy"}:
        raise ValueError(f"unsupported fill case: {case}")
    if not 0 <= int(count) <= MANAGED_CAPACITY:
        raise ValueError(f"fill count must be within 0..{MANAGED_CAPACITY}")
    base = ws.gen_goods(int(count), int(seed), case)
    goods = []
    for good in base:
        safe_weight = round(5.0 + (good.weight - 5.0) * (55.0 / 75.0), 1)
        goods.append(ws.Good(
            good.gid, good.name, min(60.0, max(5.0, safe_weight)),
            good.freq, good.vol,
        ))
    return goods


def _good_payload(good: ws.Good) -> Dict[str, Any]:
    grade = "light" if good.weight <= 25.0 else (
        "mid" if good.weight <= 45.0 else "heavy"
    )
    return {
        "gid": int(good.gid), "name": good.name,
        "weight_kg": float(good.weight), "freq": float(good.freq),
        "volume_m3": float(good.vol), "grade": grade,
    }


def _good_from_payload(item: Dict[str, Any]) -> ws.Good:
    return ws.Good(
        int(item["gid"]), str(item["name"]), float(item["weight_kg"]),
        float(item["freq"]), float(item["volume_m3"]),
    )


def build_shared_input(count: int = MANAGED_CAPACITY, seed: int = 2026,
                       case: str = "skew") -> Dict[str, Any]:
    locked_runtime = enforce_dependency_lock()
    goods = build_fill_goods(count=count, seed=seed, case=case)

    def motion_values() -> Dict[str, Any]:
        return {
            "model": "trapezoid_accel_plus_laden_vertical_factor",
            "accel": True,
            "vx_mps": ws.VX, "vy_mps": ws.VY,
            "ax_mps2": ws.AX, "ay_mps2": ws.AY,
            "laden_vy_factor": ws.LADEN_FACTOR_VY,
            "handle_tiers": [list(item) for item in ws.HANDLE_TIERS[:-1]]
                + [["inf", ws.HANDLE_TIERS[-1][1]]],
            "t_max_score_normalizer_s": _round(ws.t_max_now()),
        }

    motion = _with_accel_true(motion_values)
    if any(good.weight > SCORE_WEIGHT_MAX_KG for good in goods):
        raise ValueError("fill profile exceeds predeclared score weight bound")
    if any(good.freq < 0.0 or good.freq > SCORE_FREQ_MAX for good in goods):
        raise ValueError("fill profile exceeds predeclared score frequency bound")
    root = Path(__file__).resolve().parent
    shared = {
        "schema_version": SCHEMA_VERSION,
        "trace_kind": "FILL_ONLY",
        "evidence_scope": "single-seed-SIM-capacity-gate-not-headline",
        "sim_only": True,
        "profile": {
            "id": PROFILE_ID,
            "case": case,
            "seed": int(seed),
            "target_managed_goods": int(count),
            "weight_transform": "5+(source_weight-5)*(55/75), clamped 5..60kg",
            "physical_scope": "all goods fit every tier by weight and volume",
        },
        "capacity": {
            "cols": ws.COLS, "tiers": ws.TIERS,
            "total_slots": TOTAL_SLOTS,
            "preoccupied_slots": PREOCCUPIED_SLOTS,
            "managed_capacity": MANAGED_CAPACITY,
            "rule": RULE,
            "rule_expression": "(col+tier)%3==0",
            "start": {"managed_goods": 0, "total_unavailable": PREOCCUPIED_SLOTS},
            "full_endpoint": {
                "managed_goods": MANAGED_CAPACITY,
                "total_unavailable": TOTAL_SLOTS,
            },
        },
        "arrival_model": "just_in_time_single_machine_no_queue",
        "motion": motion,
        "score_policy": {
            "id": SCORE_POLICY_ID,
            "weights": list(SCORE_WEIGHTS),
            "density_contract": "frozen fixed weights for this exact fill gate; no adaptive lookup or fallback",
            "known_collinearity": {
                "stability_raw_equals_energy_proxy_raw": True,
                "reason": "both equal (weight/w_max)*(tier/19) under 1m cell height",
                "ui_rule": "preserve computation but explain jointly as one load-height factor",
            },
            "normalization": {
                "source": "predeclared_profile_bounds_not_cargo_catalog_statistics",
                "causal_scope": "known_before_first_arrival",
                "w_max": SCORE_WEIGHT_MAX_KG, "f_max": SCORE_FREQ_MAX,
                "t_max_s": motion["t_max_score_normalizer_s"],
            },
        },
        "cargo_catalog": [_good_payload(good) for good in goods],
        "inbound_order": [int(good.gid) for good in goods],
        "source_sha256": {
            "sim/fill_only.py": file_sha256(__file__),
            "sim/warehouse_sim.py": file_sha256(root / "warehouse_sim.py"),
            "sim/lap_optimal.py": file_sha256(root / "lap_optimal.py"),
            "l4_showcase/evidence/s3_fill_requirements.lock": file_sha256(DEPENDENCY_LOCK),
        },
        "runtime_provenance": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "locked_versions": locked_runtime,
            "dependency_lock": "l4_showcase/evidence/s3_fill_requirements.lock",
            "dependency_lock_sha256": file_sha256(DEPENDENCY_LOCK),
        },
    }
    shared["shared_input_sha256"] = payload_sha256(shared)
    return shared


def _score_terms(good: ws.Good, col: int, tier: int,
                 shared: Dict[str, Any]) -> Dict[str, float]:
    alpha, beta, gamma, delta = shared["score_policy"]["weights"]
    normal = shared["score_policy"]["normalization"]
    t_norm = ws.travel_time(col, tier) / normal["t_max_s"]
    f_norm = good.freq / normal["f_max"]
    w_norm = good.weight / normal["w_max"]
    eff_raw = f_norm * t_norm
    stability_raw = w_norm * (tier / (ws.TIERS - 1))
    energy_raw = (good.weight * tier * ws.CELL_H) / (
        normal["w_max"] * ws.H_MAX
    )
    reservation_raw = (1.0 - f_norm) * (1.0 - t_norm)
    components = {
        "efficiency": alpha * eff_raw,
        "stability": beta * stability_raw,
        "energy_proxy": gamma * energy_raw,
        "position_reservation": delta * reservation_raw,
    }
    return {
        "t_norm": _round(t_norm), "f_norm": _round(f_norm),
        "w_norm": _round(w_norm),
        "efficiency_raw": _round(eff_raw),
        "stability_raw": _round(stability_raw),
        "energy_proxy_raw": _round(energy_raw),
        "position_reservation_raw": _round(reservation_raw),
        "efficiency_weighted": _round(components["efficiency"]),
        "stability_weighted": _round(components["stability"]),
        "energy_proxy_weighted": _round(components["energy_proxy"]),
        "position_reservation_weighted": _round(components["position_reservation"]),
        "score_total": _round(sum(components.values())),
    }


def _slot_state(wh: ws.Warehouse, col: int, tier: int) -> str:
    value = wh.grid[col][tier]
    if value == "PRE":
        return "PREOCCUPIED"
    if isinstance(value, ws.Good):
        return "OCCUPIED"
    return "EMPTY"


def _decision_key(algorithm: str, row: Dict[str, Any]) -> Tuple[Any, ...]:
    col, tier = row["slot"]
    if algorithm == "seq":
        return (col * ws.TIERS + tier,)
    if algorithm == "near":
        return (row["travel_time_s"], tier, col)
    if algorithm == "score":
        return (row["score_terms"]["score_total"], row["travel_time_s"], tier, col)
    raise ValueError(f"unsupported online fill algorithm: {algorithm}")


def _objective_tie_key(algorithm: str, row: Dict[str, Any]) -> Tuple[Any, ...]:
    if algorithm == "seq":
        col, tier = row["slot"]
        return (col * ws.TIERS + tier,)
    if algorithm == "near":
        return (row["travel_time_s"],)
    if algorithm == "score":
        return (row["score_terms"]["score_total"],)
    raise ValueError(f"unsupported online fill algorithm: {algorithm}")


def build_candidate_audit(wh: ws.Warehouse, good: ws.Good, algorithm: str,
                          event_index: int, shared: Dict[str, Any]) -> Dict[str, Any]:
    if algorithm not in ONLINE_ALGORITHMS:
        raise ValueError(f"unsupported online fill algorithm: {algorithm}")
    candidates = []
    rejection_counts: Counter[str] = Counter()
    for col in range(ws.COLS):
        for tier in range(ws.TIERS):
            state = _slot_state(wh, col, tier)
            reasons = []
            if state == "PREOCCUPIED":
                reasons.append("PREOCCUPIED")
            elif state == "OCCUPIED":
                reasons.append("OCCUPIED")
            if good.weight > ws.tier_cap(tier):
                reasons.append("OVERWEIGHT")
            if good.vol > ws.CELL_VOL:
                reasons.append("OVERSIZE")
            row: Dict[str, Any] = {
                "slot": [col, tier], "state_before": state,
                "tier_capacity_kg": _round(ws.tier_cap(tier)),
                "weight_margin_kg": _round(ws.tier_cap(tier) - good.weight),
                "volume_margin_m3": _round(ws.CELL_VOL - good.vol),
                "legal": not reasons, "rejection_reasons": reasons,
                "rank": None, "selected": False,
            }
            if reasons:
                rejection_counts.update(reasons)
            else:
                row["travel_time_s"] = _round(ws.travel_time(col, tier))
                row["path_one_way_m"] = _round(ws.path_len(col, tier))
                if algorithm == "score":
                    row["score_terms"] = _score_terms(good, col, tier, shared)
            candidates.append(row)
    legal = [row for row in candidates if row["legal"]]
    legal.sort(key=lambda row: _decision_key(algorithm, row))
    key_counts = Counter(_objective_tie_key(algorithm, row) for row in legal)
    tie_group = 0
    prior_key = None
    for rank, row in enumerate(legal, start=1):
        selection_key = _decision_key(algorithm, row)
        tie_key = _objective_tie_key(algorithm, row)
        if tie_key != prior_key:
            tie_group += 1
            prior_key = tie_key
        row["rank"] = rank
        row["selection_key"] = list(selection_key)
        row["objective_tie_key"] = list(tie_key)
        row["tie_group"] = tie_group
        row["tie_size"] = key_counts[tie_key]
    selected = legal[0] if legal else None
    if selected is not None:
        selected["selected"] = True
    audit = {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "shared_input_sha256": shared["shared_input_sha256"],
        "event_index": int(event_index), "algorithm": algorithm,
        "decision_basis": {
            "seq": "col-major first legal slot",
            "near": "min(travel_time,tier,col)",
            "score": "min(score,travel_time,tier,col)",
        }[algorithm],
        "score_terms_role": "decision_basis" if algorithm == "score" else "not_emitted",
        "known_collinearity": shared["score_policy"]["known_collinearity"],
        "inventory_state_sha256": payload_sha256(_compact_grid(wh)),
        "good": _good_payload(good),
        "candidate_count": len(candidates), "legal_count": len(legal),
        "rejected_count": len(candidates) - len(legal),
        "rejection_reason_counts": dict(sorted(rejection_counts.items())),
        "selected_slot": selected["slot"] if selected else None,
        "candidates": candidates,
    }
    audit["audit_sha256"] = payload_sha256(audit)
    return audit


def _compact_grid(wh: ws.Warehouse) -> List[int]:
    values = []
    for col in range(ws.COLS):
        for tier in range(ws.TIERS):
            value = wh.grid[col][tier]
            values.append(-1 if value == "PRE" else (
                int(value.gid) if isinstance(value, ws.Good) else 0
            ))
    return values


def _checkpoint_targets(target: int) -> List[Tuple[str, int]]:
    if target == MANAGED_CAPACITY:
        return list(zip(CHECKPOINT_LABELS, CHECKPOINT_COUNTS))
    counts = [0, round(target * .25), round(target * .50),
              round(target * .75), round(target * .90), target]
    unique = []
    for label, count in zip(CHECKPOINT_LABELS, counts):
        if not unique or unique[-1][1] != count:
            unique.append((label, count))
    return unique


def _event_record(good: ws.Good, selected: Sequence[int], algorithm: str,
                  event_index: int, start_s: float, audit: Dict[str, Any],
                  managed_before: int) -> Dict[str, Any]:
    col, tier = int(selected[0]), int(selected[1])
    load_s = ws.handle_time(good)
    laden_s = ws.travel_time_laden(0, 0, col, tier)
    store_s = ws.handle_time(good)
    empty_s = ws.travel_time_between(col, tier, 0, 0)
    t_load = start_s + load_s
    t_laden = t_load + laden_s
    t_store = t_laden + store_s
    finish = t_store + empty_s
    selected_row = next(row for row in audit["candidates"] if row["selected"])
    event = {
        "event_index": int(event_index), "operation": "INBOUND_STORE",
        "operation_status": "COMPLETE", "gid": int(good.gid),
        "algorithm": algorithm,
        "decision": {
            "selected_slot": [col, tier],
            "selected_rank": 1,
            "selected_travel_time_s": selected_row["travel_time_s"],
            "selected_score": (
                selected_row["score_terms"]["score_total"]
                if algorithm == "score" else None
            ),
            "candidate_audit_ref": {
                "event_index": int(event_index),
                "audit_sha256": audit["audit_sha256"],
            },
        },
        "clock": {
            "arrival_s": _round(start_s), "start_s": _round(start_s),
            "finish_s": _round(finish), "duration_s": _round(finish - start_s),
        },
        "phases": [
            {"name": "INFEED_HANDOFF", "t0": _round(start_s), "t1": _round(t_load),
             "machine_state": "LOAD_HANDLE", "cargo_state": "INFEED_QUEUE"},
            {"name": "LADEN_TRAVEL", "t0": _round(t_load), "t1": _round(t_laden),
             "machine_state": "LADEN_TRAVEL", "cargo_state": "CARRIER_IN",
             "from": [0, 0], "to": [col, tier]},
            {"name": "STORE_HANDLE", "t0": _round(t_laden), "t1": _round(t_store),
             "machine_state": "STORE_HANDLE", "cargo_state": "SLOT_CLAIMED"},
            {"name": "EMPTY_RETURN", "t0": _round(t_store), "t1": _round(finish),
             "machine_state": "EMPTY_RETURN", "cargo_state": "RACK_STORED",
             "from": [col, tier], "to": [0, 0]},
        ],
        "ownership_events": [
            {"t": _round(start_s), "from": "NOT_ARRIVED", "to": "INFEED_QUEUE"},
            {"t": _round(t_load), "from": "INFEED_QUEUE", "to": "CARRIER_IN"},
            {"t": _round(t_laden), "from": "CARRIER_IN", "to": "SLOT_CLAIMED"},
            {"t": _round(t_store), "from": "SLOT_CLAIMED", "to": "RACK_STORED"},
        ],
        "slot_state_change": {
            "slot": [col, tier], "before": "EMPTY", "after": f"GID:{good.gid}"
        },
        "occupancy": {
            "managed_before": managed_before, "managed_after": managed_before + 1,
            "total_unavailable_before": PREOCCUPIED_SLOTS + managed_before,
            "total_unavailable_after": PREOCCUPIED_SLOTS + managed_before + 1,
        },
        "metric_delta": {
            "laden_path_m": _round(ws.path_len(col, tier)),
            "empty_return_path_m": _round(ws.path_len(col, tier)),
            "lift_work_proxy_kgm": _round(good.weight * tier * ws.CELL_H),
        },
    }
    return event


def run_online_lane(shared: Dict[str, Any], algorithm: str,
                    audit_sink: Callable[[Dict[str, Any]], None] | None = None,
                    audit_resource: str | None = None) -> Dict[str, Any]:
    if algorithm not in ONLINE_ALGORITHMS:
        raise ValueError(f"unsupported online fill algorithm: {algorithm}")
    expected_hash = payload_sha256({
        key: value for key, value in shared.items() if key != "shared_input_sha256"
    })
    if shared.get("shared_input_sha256") != expected_hash:
        raise ValueError("shared input hash mismatch")
    goods_by_gid = {
        int(item["gid"]): _good_from_payload(item)
        for item in shared["cargo_catalog"]
    }
    goods = [goods_by_gid[int(gid)] for gid in shared["inbound_order"]]
    wh = ws.Warehouse(shared["capacity"]["rule"])
    events: List[Dict[str, Any]] = []
    checkpoints: List[Dict[str, Any]] = []
    target_map = {count: label for label, count in _checkpoint_targets(len(goods))}
    prefix_hash = hashlib.sha256(b"s3-fill-genesis-v1").hexdigest()
    audit_prefix_hash = hashlib.sha256(b"s3-fill-audit-genesis-v1").hexdigest()

    def capture_checkpoint(count: int) -> None:
        placed_events = events[:count]
        frequency_sum = sum(goods_by_gid[event["gid"]].freq for event in placed_events)
        expected_retrieval = (
            sum(goods_by_gid[event["gid"]].freq
                * event["decision"]["selected_travel_time_s"]
                for event in placed_events) / frequency_sum
            if frequency_sum else 0.0
        )
        checkpoints.append({
            "label": target_map[count], "event_count": count,
            "phase": "IDLE_AFTER_RETURN",
            "managed_goods": count,
            "total_unavailable": PREOCCUPIED_SLOTS + count,
            "event_prefix_sha256": prefix_hash,
            "audit_prefix_sha256": audit_prefix_hash,
            "snapshot_sha256": payload_sha256(_compact_grid(wh)),
            "metrics_to_date": {
                "makespan_s": (
                    placed_events[-1]["clock"]["finish_s"] if placed_events else 0.0
                ),
                "expected_retrieval_s": _round(expected_retrieval),
                "round_trip_path_m": _round(sum(
                    event["metric_delta"]["laden_path_m"]
                    + event["metric_delta"]["empty_return_path_m"]
                    for event in placed_events
                )),
                "lift_work_proxy_kgm": _round(sum(
                    event["metric_delta"]["lift_work_proxy_kgm"]
                    for event in placed_events
                )),
            },
            "grid_col_major": _compact_grid(wh),
        })

    if 0 in target_map:
        capture_checkpoint(0)
    status = "FEASIBLE"
    failure = None
    clock_s = 0.0

    with _accel_true_context():
        for event_index, good in enumerate(goods, start=1):
            audit = build_candidate_audit(wh, good, algorithm, event_index, shared)
            selected = audit["selected_slot"]
            if selected is None:
                status = "INFEASIBLE"
                failure = {
                    "event_index": event_index, "gid": good.gid,
                    "reason": "NO_LEGAL_SLOT", "fallback_used": False,
                }
                break
            if audit_sink is not None:
                audit_sink(audit)
            audit_prefix_hash = hashlib.sha256(
                (audit_prefix_hash + audit["audit_sha256"]).encode("ascii")
            ).hexdigest()
            event = _event_record(
                good, selected, algorithm, event_index, clock_s, audit, len(events)
            )
            col, tier = selected
            event["inventory_before_sha256"] = payload_sha256(_compact_grid(wh))
            wh.put(col, tier, good)
            event["inventory_after_sha256"] = payload_sha256(_compact_grid(wh))
            event["event_sha256"] = payload_sha256(event)
            events.append(event)
            clock_s = event["clock"]["finish_s"]
            prefix_hash = hashlib.sha256(
                (prefix_hash + event["event_sha256"]).encode("ascii")
            ).hexdigest()
            if len(events) in target_map:
                capture_checkpoint(len(events))
    placed = [(goods_by_gid[event["gid"]], tuple(event["decision"]["selected_slot"]))
              for event in events]

    def metric_values() -> Dict[str, Any]:
        base = ws.metrics(wh, placed, [] if status == "FEASIBLE" else [goods[len(events)]])
        score_fn = ws.make_score_fn(
            *shared["score_policy"]["weights"],
            shared["score_policy"]["normalization"]["w_max"],
            shared["score_policy"]["normalization"]["f_max"],
        )
        return {
            "placed": len(events), "failed": 0 if status == "FEASIBLE" else 1,
            "violations": base["viol"],
            "managed_fill_ratio": _round(len(events) / MANAGED_CAPACITY),
            "total_occupancy_ratio": _round((PREOCCUPIED_SLOTS + len(events)) / TOTAL_SLOTS),
            "makespan_s": _round(clock_s),
            "expected_retrieval_s": _round(base["exp_t"]),
            "hot20_retrieval_s": _round(base["hot_t"]),
            "heavy20_mean_tier": _round(base["heavy_tier"]),
            "round_trip_path_m": _round(base["path"]),
            "lift_work_proxy_kgm": _round(base["energy"]),
            "fixed_score_diagnostic_total": _round(
                sum(score_fn(good, *slot) for good, slot in placed)
            ),
        }

    metrics = _with_accel_true(metric_values)
    lane = {
        "lane_id": f"online_{algorithm}",
        "shared_input_sha256": shared["shared_input_sha256"],
        "algorithm": {
            "id": algorithm, "decision_scope": "online",
            "information_class": "current_good_plus_committed_inventory_only",
            "fallback_policy": "none_fail_closed",
            "config_sha256": payload_sha256({
                "algorithm": algorithm,
                "score_policy": shared["score_policy"],
            }),
        },
        "status": status,
        "terminal_state": (
            "FULL_SAFE" if status == "FEASIBLE" and len(events) == MANAGED_CAPACITY
            else ("PARTIAL_SAFE" if status == "FEASIBLE" else "INFEASIBLE")
        ),
        "failure": failure,
        "candidate_audit": {
            "schema_version": AUDIT_SCHEMA_VERSION,
            "resource": audit_resource,
            "event_count": len(events),
            "audit_prefix_sha256": audit_prefix_hash,
        },
        "events": events, "checkpoints": checkpoints,
        "metrics": metrics, "final_grid_col_major": _compact_grid(wh),
    }
    lane["lane_result_sha256"] = payload_sha256(lane)
    return lane


def run_awra_offline_reference(shared: Dict[str, Any]) -> Dict[str, Any]:
    goods = [_good_from_payload(item) for item in shared["cargo_catalog"]]

    def run() -> Dict[str, Any]:
        w_max = shared["score_policy"]["normalization"]["w_max"]
        f_max = shared["score_policy"]["normalization"]["f_max"]
        score_fn = ws.make_score_fn(*shared["score_policy"]["weights"], w_max, f_max)
        wh, placed, failed = ws.run_awra_ls(
            goods, shared["capacity"]["rule"], score_fn, w_max, f_max
        )
        metrics = ws.metrics(wh, placed, failed)
        result = {
            "reference_id": "awra_ls_offline_batch",
            "shared_input_sha256": shared["shared_input_sha256"],
            "decision_scope": "offline_batch",
            "comparison_role": "separate_reference_not_same_information_set_online_race",
            "status": "FEASIBLE" if not failed else "INFEASIBLE",
            "placed": len(placed), "failed": len(failed),
            "violations": metrics["viol"],
            "assignment": [
                {"gid": good.gid, "slot": [slot[0], slot[1]],
                 "score": _round(score_fn(good, *slot))}
                for good, slot in placed
            ],
            "metrics": {
                "expected_retrieval_s": _round(metrics["exp_t"]),
                "hot20_retrieval_s": _round(metrics["hot_t"]),
                "heavy20_mean_tier": _round(metrics["heavy_tier"]),
                "round_trip_path_m": _round(metrics["path"]),
                "lift_work_proxy_kgm": _round(metrics["energy"]),
                "score_total": _round(sum(score_fn(good, *slot) for good, slot in placed)),
            },
        }
        result["reference_sha256"] = payload_sha256(result)
        return result

    return _with_accel_true(run)


def run_lap_exact_references(shared: Dict[str, Any]) -> Dict[str, Any]:
    """同一静态实例的 LAP 精确参照；不冒充在线可执行策略。"""
    import lap_optimal as lap

    goods = [_good_from_payload(item) for item in shared["cargo_catalog"]]

    def run() -> Dict[str, Any]:
        references = {}
        shared_normalization = shared["score_policy"]["normalization"]
        normalization = {
            key: shared_normalization[key] for key in ("w_max", "f_max", "t_max_s")
        }
        for objective in ("score", "exp_t"):
            optimum, assignment = lap.solve_lap(
                goods, shared["capacity"]["rule"], objective,
                score_normalization=normalization if objective == "score" else None,
            )
            references[objective] = {
                "objective": objective,
                "status": "FEASIBLE" if optimum is not None else "INFEASIBLE",
                "objective_value": _round(optimum) if optimum is not None else None,
                "assignment_count": len(assignment) if isinstance(assignment, list) else None,
                "assignment": [
                    {"gid": good.gid, "slot": [slot[0], slot[1]]}
                    for good, slot in assignment
                ] if isinstance(assignment, list) else [],
            }
            if objective == "score":
                references[objective]["normalization"] = {
                    **normalization,
                    "score_policy_id": shared["score_policy"]["id"],
                }
                references[objective]["objective_contract"] = (
                    "same_frozen_score_normalization_as_online_and_awra_reference"
                )
            if objective == "exp_t":
                frequency_sum = sum(good.freq for good in goods)
                references[objective]["normalized_expected_retrieval_s"] = (
                    _round(optimum / frequency_sum) if optimum is not None and frequency_sum else None
                )
        result = {
            "reference_id": "scipy_lap_exact_static_instance",
            "shared_input_sha256": shared["shared_input_sha256"],
            "decision_scope": "offline_exact_static_assignment",
            "comparison_role": "exact_reference_not_online_controller",
            "runtime_provenance": shared["runtime_provenance"],
            "lap_source_sha256": shared["source_sha256"]["sim/lap_optimal.py"],
            "objectives": references,
        }
        result["reference_sha256"] = payload_sha256(result)
        return result

    return _with_accel_true(run)


def validate_online_lane(shared: Dict[str, Any], lane: Dict[str, Any]) -> List[str]:
    errors = []
    target = len(shared["inbound_order"])
    expected_lane_hash = payload_sha256({
        key: value for key, value in lane.items() if key != "lane_result_sha256"
    })
    if lane.get("lane_result_sha256") != expected_lane_hash:
        errors.append("lane_result_hash")
    if lane.get("shared_input_sha256") != shared.get("shared_input_sha256"):
        errors.append("shared_input_hash")
    if lane.get("status") != "FEASIBLE":
        errors.append("status")
    events = lane.get("events", [])
    if len(events) != target:
        errors.append("event_count")
    slots = [tuple(event["decision"]["selected_slot"]) for event in events]
    if len(set(slots)) != len(slots):
        errors.append("duplicate_slot")
    if any(ws.preoccupied(col, tier, RULE) for col, tier in slots):
        errors.append("preoccupied_touched")
    if lane.get("metrics", {}).get("violations") != 0:
        errors.append("violations")
    if lane.get("algorithm", {}).get("fallback_policy") != "none_fail_closed":
        errors.append("fallback_policy")
    expected_terminal = "FULL_SAFE" if target == MANAGED_CAPACITY else "PARTIAL_SAFE"
    if lane.get("terminal_state") != expected_terminal:
        errors.append("terminal_state")
    expected_counts = [count for _, count in _checkpoint_targets(target)]
    actual_counts = [item.get("event_count") for item in lane.get("checkpoints", [])]
    if actual_counts != expected_counts:
        errors.append("checkpoints")
    if any(item.get("phase") != "IDLE_AFTER_RETURN"
           for item in lane.get("checkpoints", [])):
        errors.append("checkpoint_phase")
    checkpoints_by_count = {
        item.get("event_count"): item for item in lane.get("checkpoints", [])
    }
    goods_by_gid = {
        int(item["gid"]): _good_from_payload(item)
        for item in shared["cargo_catalog"]
    }
    replay = ws.Warehouse(RULE)
    prefix_hash = hashlib.sha256(b"s3-fill-genesis-v1").hexdigest()

    def check_snapshot(count: int) -> None:
        item = checkpoints_by_count.get(count)
        if item is None:
            return
        grid = _compact_grid(replay)
        if item.get("snapshot_sha256") != payload_sha256(grid):
            errors.append(f"checkpoint_snapshot_hash:{count}")
        if item.get("grid_col_major") != grid:
            errors.append(f"checkpoint_snapshot:{count}")
        if item.get("event_prefix_sha256") != prefix_hash:
            errors.append(f"checkpoint_event_prefix:{count}")

    check_snapshot(0)
    for index, event in enumerate(events, start=1):
        expected_event_hash = payload_sha256({
            key: value for key, value in event.items() if key != "event_sha256"
        })
        if event.get("event_sha256") != expected_event_hash:
            errors.append(f"event_hash:{index}")
        before = payload_sha256(_compact_grid(replay))
        if event.get("inventory_before_sha256") != before:
            errors.append(f"inventory_before_hash:{index}")
        col, tier = event["decision"]["selected_slot"]
        good = goods_by_gid.get(int(event["gid"]))
        if good is None or not replay.feasible(col, tier, good):
            errors.append(f"replay_feasibility:{index}")
            break
        replay.put(col, tier, good)
        after = payload_sha256(_compact_grid(replay))
        if event.get("inventory_after_sha256") != after:
            errors.append(f"inventory_after_hash:{index}")
        prefix_hash = hashlib.sha256(
            (prefix_hash + str(event.get("event_sha256", ""))).encode("ascii")
        ).hexdigest()
        check_snapshot(index)
    final_grid = lane.get("final_grid_col_major", [])
    if len(final_grid) != TOTAL_SLOTS:
        errors.append("final_grid_width")
    else:
        for col in range(ws.COLS):
            for tier in range(ws.TIERS):
                value = final_grid[col * ws.TIERS + tier]
                if ws.preoccupied(col, tier, RULE):
                    if value != -1:
                        errors.append("preoccupied_final_state")
                        break
                elif target == MANAGED_CAPACITY and value <= 0:
                    errors.append("managed_slot_not_full")
                    break
    return sorted(set(errors))


def validate_candidate_audits(lane: Dict[str, Any],
                              audits: Iterable[Dict[str, Any]]) -> List[str]:
    errors = []
    events = lane.get("events", [])
    count = 0
    prefix_hash = hashlib.sha256(b"s3-fill-audit-genesis-v1").hexdigest()
    for count, audit in enumerate(audits, start=1):
        expected = payload_sha256({
            key: value for key, value in audit.items() if key != "audit_sha256"
        })
        if audit.get("audit_sha256") != expected:
            errors.append(f"audit_hash:{count}")
        if audit.get("candidate_count") != TOTAL_SLOTS:
            errors.append(f"candidate_count:{count}")
        selected = [row for row in audit.get("candidates", []) if row.get("selected")]
        if len(selected) != 1:
            errors.append(f"selected_count:{count}")
        elif selected[0].get("rank") != 1:
            errors.append(f"selected_rank:{count}")
        legal = [row for row in audit.get("candidates", []) if row.get("legal")]
        legal_ranks = sorted(row.get("rank") for row in legal)
        if legal_ranks != list(range(1, len(legal) + 1)):
            errors.append(f"legal_rank_sequence:{count}")
        slots = [tuple(row.get("slot", ())) for row in audit.get("candidates", [])]
        if len(slots) != TOTAL_SLOTS or len(set(slots)) != TOTAL_SLOTS:
            errors.append(f"candidate_slot_coverage:{count}")
        if audit.get("event_index") != count:
            errors.append(f"event_index:{count}")
        if audit.get("algorithm") != lane.get("algorithm", {}).get("id"):
            errors.append(f"algorithm:{count}")
        if count <= len(events):
            event = events[count - 1]
            if audit.get("selected_slot") != event["decision"]["selected_slot"]:
                errors.append(f"selected_slot:{count}")
            if audit.get("audit_sha256") != event["decision"]["candidate_audit_ref"]["audit_sha256"]:
                errors.append(f"event_audit_ref:{count}")
            if audit.get("inventory_state_sha256") != event.get("inventory_before_sha256"):
                errors.append(f"inventory_state_ref:{count}")
        prefix_hash = hashlib.sha256(
            (prefix_hash + str(audit.get("audit_sha256", ""))).encode("ascii")
        ).hexdigest()
    if count != len(events):
        errors.append("audit_event_count")
    if prefix_hash != lane.get("candidate_audit", {}).get("audit_prefix_sha256"):
        errors.append("audit_prefix_hash")
    return errors


def _lane_semantic_payload(lane: Dict[str, Any]) -> Dict[str, Any]:
    """移除发布载体字段，保留全部决策、时钟、指标与 checkpoint 语义。"""
    value = copy.deepcopy(lane)
    value.pop("lane_result_sha256", None)
    artifact = value.get("candidate_audit", {})
    artifact.pop("file_sha256", None)
    artifact.pop("compression", None)
    return value


def replay_validate_online_lane(shared: Dict[str, Any], lane: Dict[str, Any],
                                audits: Iterable[Dict[str, Any]]) -> List[str]:
    """从冻结输入逐事件重算算法，拒绝可自洽重哈希的伪候选与伪指标。

    审计以流式方式逐条比较，避免把 267×400 个候选同时保存在内存。
    这提供源码级语义重放；代码与产物共同被替换的威胁仍需外部 release
    registry/签名作为信任锚。
    """
    errors: List[str] = []
    actual_iter = iter(audits)
    actual_exhausted = False
    compared = 0

    def compare_expected(expected_audit: Dict[str, Any]) -> None:
        nonlocal actual_exhausted, compared
        if actual_exhausted:
            return
        try:
            actual_audit = next(actual_iter)
        except StopIteration:
            actual_exhausted = True
            errors.append("semantic_audit_missing")
            return
        compared += 1
        if canonical_json_bytes(actual_audit) != canonical_json_bytes(expected_audit):
            if sum(item.startswith("semantic_audit_mismatch:") for item in errors) < 20:
                errors.append(f"semantic_audit_mismatch:{compared}")

    try:
        algorithm = lane.get("algorithm", {}).get("id")
        expected_lane = run_online_lane(
            shared, algorithm, audit_sink=compare_expected,
            audit_resource=lane.get("candidate_audit", {}).get("resource"),
        )
    except Exception as exc:  # fail closed; report stable exception class only
        return [f"semantic_replay_exception:{type(exc).__name__}"]

    try:
        next(actual_iter)
        errors.append("semantic_audit_extra")
    except StopIteration:
        pass
    if payload_sha256(_lane_semantic_payload(lane)) != payload_sha256(
            _lane_semantic_payload(expected_lane)):
        errors.append("lane_semantic_replay")
    return sorted(set(errors))
