# -*- coding: utf-8 -*-
"""Versioned cargo profiles for the S3 multi-strategy simulation showcase.

This module is intentionally a facts layer: it creates deterministic cargo
attributes and exposes their measured profile.  It does not select a strategy
and it does not change any global simulation default.
"""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import math
import random
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import strategy_lib as sl
import warehouse_sim as ws


HERE = Path(__file__).resolve().parent
SCENARIO_DIR = HERE / "scenarios"
DEFAULT_VERSION = "cargo_dynamic_v1"
_ATTR = {"weight": "weight", "freq": "freq", "volume": "vol", "vol": "vol"}
_REQUIRED_SCENARIO_FIELDS = {
    "initial_goods_generator",
    "inbound_goods_generator",
    "request_pool_policy",
    "invalid_inbound_policy",
}


def _registry_path(version: str) -> Path:
    if not version or any(ch not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_" for ch in version):
        raise ValueError(f"invalid registry version: {version!r}")
    return SCENARIO_DIR / f"{version}.json"


def _validate_registry(registry: Dict[str, Any], version: str) -> None:
    if registry.get("schema_version") != version:
        raise ValueError(
            f"registry schema mismatch: expected {version}, got {registry.get('schema_version')!r}"
        )
    expected_ids = [f"E{i:02d}" for i in range(1, 19)]
    scenarios = registry.get("scenarios")
    if not isinstance(scenarios, dict) or list(scenarios) != expected_ids:
        raise ValueError("registry must contain ordered scenarios E01..E18")
    for sid, scenario in scenarios.items():
        missing = _REQUIRED_SCENARIO_FIELDS.difference(scenario)
        if missing:
            raise ValueError(f"{sid} missing fields: {sorted(missing)}")
        if int(scenario.get("initial_count", -1)) < 1:
            raise ValueError(f"{sid} invalid initial_count")
        if int(scenario.get("scheduled_cycles", -1)) < 1:
            raise ValueError(f"{sid} invalid scheduled_cycles")
        request_policy = scenario["request_pool_policy"]
        if (request_policy.get("type") != "weighted_current_legal_inventory"
                or request_policy.get("weight") != "freq"
                or request_policy.get("seed_offset") != 13
                or request_policy.get("position_blind") is not True):
            raise ValueError(f"{sid} invalid request_pool_policy")
        invalid_policy = scenario["invalid_inbound_policy"]
        expected_rejected = invalid_policy.get("expected_count")
        if not isinstance(expected_rejected, int) or not 0 <= expected_rejected <= scenario["scheduled_cycles"]:
            raise ValueError(f"{sid} invalid expected rejection count")
        initial_generator = scenario["initial_goods_generator"]
        if int(initial_generator.get("count", -1)) != int(scenario["initial_count"]):
            raise ValueError(f"{sid} initial generator count mismatch")
        if scenario["inbound_goods_generator"].get("count_source") != "cycles":
            raise ValueError(f"{sid} inbound generator must be cycle-sized")
    e15 = scenarios["E15"]
    expected_flags = {
        "extended_pressure": True,
        "canonical_g2": False,
        "headline_eligible": False,
    }
    for key, expected in expected_flags.items():
        if e15.get(key) is not expected:
            raise ValueError(f"E15 must declare {key}={expected}")

    e14 = scenarios["E14"]
    if (int(e14.get("valid_cycles", -1)) + int(e14.get("rejected_cycles", -1))
            != int(e14["scheduled_cycles"])):
        raise ValueError("E14 valid_cycles + rejected_cycles must equal scheduled_cycles")
    if int(e14["invalid_inbound_policy"]["expected_count"]) != int(e14["rejected_cycles"]):
        raise ValueError("E14 rejection fields disagree")

    e18 = scenarios["E18"]
    segments = e18["inbound_goods_generator"].get("segments", [])
    next_cycle = 0
    for segment in segments:
        start = int(segment["start_cycle"])
        end = int(segment["end_cycle"])
        if start != next_cycle or end < start or segment.get("case") not in {"uniform", "skew", "heavy"}:
            raise ValueError("E18 segments must be contiguous, ordered and use registered cases")
        next_cycle = end + 1
    if next_cycle != int(e18["scheduled_cycles"]):
        raise ValueError("E18 segments must cover every scheduled cycle exactly once")
    router_contract = e18.get("router_contract", {})
    if (router_contract.get("advisory_cycles") != [33, 66]
            or router_contract.get("select_once_at_run_start") is not True
            or router_contract.get("advisory_only") is not True
            or router_contract.get("existing_inventory_relayout") is not False):
        raise ValueError("E18 router advisory contract drifted")

    ranges = registry.get("seed_ranges", {})
    required_ranges = (
        "S1_exploration",
        "S2_confirmation",
        "S3_long_run",
        "weight_v2_untouched",
    )
    intervals = []
    for name in required_ranges:
        value = ranges.get(name)
        if not isinstance(value, list) or len(value) != 2 or value[0] > value[1]:
            raise ValueError(f"invalid seed range {name}: {value!r}")
        intervals.append((value[0], value[1], name))
    intervals.sort()
    for left, right in zip(intervals, intervals[1:]):
        if left[1] >= right[0]:
            raise ValueError(f"seed ranges overlap: {left[2]} and {right[2]}")


def load_registry(version: str = DEFAULT_VERSION) -> Dict[str, Any]:
    """Load and validate a registry, returning a defensive deep copy."""
    path = _registry_path(version)
    with path.open("r", encoding="utf-8") as fp:
        registry = json.load(fp)
    _validate_registry(registry, version)
    return copy.deepcopy(registry)


def _clone_goods(goods: Iterable[ws.Good], gid_start: int) -> List[ws.Good]:
    cloned = []
    for offset, good in enumerate(goods):
        gid = gid_start + offset
        cloned.append(ws.Good(gid, f"G{gid:05d}", good.weight, good.freq, good.vol))
    return cloned


def _draw(rng: random.Random, spec: Dict[str, Any]) -> float:
    kind = spec["dist"]
    if kind == "uniform":
        return rng.uniform(float(spec["lo"]), float(spec["hi"]))
    if kind == "triangular":
        return rng.triangular(float(spec["lo"]), float(spec["hi"]), float(spec["mode"]))
    if kind == "pareto":
        return min(float(spec["cap"]), rng.paretovariate(float(spec["alpha"])))
    raise ValueError(f"unsupported distribution: {kind}")


def _generate_dsl(spec: Dict[str, Any], count: int, seed: int) -> List[ws.Good]:
    rng = random.Random(seed)
    gid_start = int(spec["gid_start"])
    goods = []
    for index in range(count):
        weight = round(_draw(rng, spec["weight"]), 1)
        freq = round(_draw(rng, spec["freq"]), 2)
        volume = round(_draw(rng, spec["volume"]), 2)
        gid = gid_start + index
        goods.append(ws.Good(gid, f"G{gid:05d}", weight, freq, volume))
    return goods


def _draw_legacy_case(rng: random.Random, case: str) -> Tuple[float, float, float]:
    """One-item equivalent of warehouse_sim.gen_goods, with one shared RNG."""
    if case == "heavy":
        weight = round(max(5.0, min(80.0, rng.triangular(5.0, 80.0, 72.0))), 1)
    elif case in ("uniform", "skew"):
        weight = round(rng.uniform(5.0, 80.0), 1)
    else:
        raise ValueError(f"unsupported legacy case: {case}")
    if case == "uniform":
        freq = round(rng.uniform(1.0, 100.0), 2)
    else:
        freq = min(100.0, round(rng.paretovariate(1.16), 2))
    volume = round(rng.uniform(0.1, 0.9), 2)
    return weight, freq, volume


def _segment_case(segments: Sequence[Dict[str, Any]], cycle: int) -> str:
    for segment in segments:
        if int(segment["start_cycle"]) <= cycle <= int(segment["end_cycle"]):
            return str(segment["case"])
    raise ValueError(f"cycle {cycle} is outside the registered E18 segments")


def _generate_segmented(spec: Dict[str, Any], count: int, seed: int) -> List[ws.Good]:
    rng = random.Random(seed)
    gid_start = int(spec["gid_start"])
    segments = spec["segments"]
    goods = []
    for cycle in range(count):
        weight, freq, volume = _draw_legacy_case(rng, _segment_case(segments, cycle))
        gid = gid_start + cycle
        goods.append(ws.Good(gid, f"G{gid:05d}", weight, freq, volume))
    return goods


def _apply_rank_coupling(
    goods: List[ws.Good], coupling: Dict[str, Any], coupling_seed: int
) -> List[ws.Good]:
    """Reassign one target multiset by deterministic near-monotone ranks.

    Stable `(attribute value, gid)` sorting defines ranks.  A small, seeded set
    of adjacent swaps uses the registered `seed+101` stream while keeping the
    requested correlation comfortably beyond the pre-registered threshold.
    No attribute value is created or discarded.
    """
    driver_attr = _ATTR[coupling["driver"]]
    target_attr = _ATTR[coupling["target"]]
    ranked_goods = sorted(goods, key=lambda good: (getattr(good, driver_attr), good.gid))
    target_values = [
        getattr(good, target_attr)
        for good in sorted(goods, key=lambda good: (getattr(good, target_attr), good.gid))
    ]
    if coupling["direction"] == "negative":
        target_values.reverse()
    elif coupling["direction"] != "positive":
        raise ValueError(f"invalid coupling direction: {coupling['direction']}")

    if len(target_values) > 1:
        rng = random.Random(coupling_seed)
        swap_count = max(1, int(round(len(target_values) * float(coupling["adjacent_swap_fraction"]))))
        for _ in range(swap_count):
            index = rng.randrange(len(target_values) - 1)
            target_values[index], target_values[index + 1] = (
                target_values[index + 1],
                target_values[index],
            )
    for good, value in zip(ranked_goods, target_values):
        setattr(good, target_attr, value)
    return goods


def _resolve_count(spec: Dict[str, Any], cycles: Optional[int]) -> int:
    if "count" in spec:
        return int(spec["count"])
    if spec.get("count_source") == "cycles" and cycles is not None:
        if int(cycles) < 0:
            raise ValueError("cycles must be non-negative")
        return int(cycles)
    raise ValueError("generator has no resolvable count")


def _build_goods(spec: Dict[str, Any], root_seed: int, cycles: Optional[int]) -> List[ws.Good]:
    count = _resolve_count(spec, cycles)
    effective_seed = int(root_seed) + int(spec.get("seed_offset", 0))
    gid_start = int(spec["gid_start"])
    kind = spec["type"]

    if kind == "legacy_case":
        return _clone_goods(ws.gen_goods(count, effective_seed, spec["case"]), gid_start)
    if kind == "dsl":
        return _generate_dsl(spec, count, effective_seed)
    if kind == "segmented_cases":
        return _generate_segmented(spec, count, effective_seed)
    if kind == "rank_coupled":
        goods = _clone_goods(ws.gen_goods(count, effective_seed, spec["base_case"]), gid_start)
        coupling_seed = int(root_seed) + int(spec["coupling"]["seed_offset"])
        return _apply_rank_coupling(goods, spec["coupling"], coupling_seed)
    if kind == "illegal_mix":
        goods = _clone_goods(ws.gen_goods(count, effective_seed, spec["base_case"]), gid_start)
        invalid_count = int(spec["invalid_count"])
        if count < invalid_count:
            raise ValueError(f"illegal_mix requires at least {invalid_count} cycles")
        rng = random.Random(int(root_seed) + int(spec["invalid_seed_offset"]))
        indexes = rng.sample(range(count), invalid_count)
        for order, index in enumerate(indexes):
            good = goods[index]
            if order % 2 == 0:
                lo, hi = spec["overweight_range_kg"]
                good.weight = round(rng.uniform(float(lo), float(hi)), 1)
            else:
                lo, hi = spec["oversize_range_m3"]
                good.vol = round(rng.uniform(float(lo), float(hi)), 2)
        return goods
    raise ValueError(f"unsupported generator type: {kind}")


def _scenario(scenario_id: str, version: str) -> Dict[str, Any]:
    registry = load_registry(version)
    try:
        return registry["scenarios"][scenario_id]
    except KeyError as exc:
        raise KeyError(f"unknown cargo scenario: {scenario_id}") from exc


def build_initial_goods(
    scenario_id: str, seed: int, version: str = DEFAULT_VERSION
) -> List[ws.Good]:
    """Build the registered initial inventory for one scenario and root seed."""
    scenario = _scenario(scenario_id, version)
    goods = _build_goods(scenario["initial_goods_generator"], seed, cycles=None)
    if len(goods) != int(scenario["initial_count"]):
        raise AssertionError(f"{scenario_id} initial-count contract failed")
    return goods


def build_inbound_goods(
    scenario_id: str, seed: int, cycles: int, version: str = DEFAULT_VERSION
) -> List[ws.Good]:
    """Build the complete, strategy-independent inbound stream."""
    scenario = _scenario(scenario_id, version)
    return _build_goods(scenario["inbound_goods_generator"], seed, cycles=int(cycles))


def is_legal_cargo(good: ws.Good) -> bool:
    """Entrance-gate physical envelope; rack-tier feasibility is checked later."""
    return 0.0 < good.weight <= ws.BASE_CAP and 0.0 < good.vol <= ws.CELL_VOL


def goods_signature(goods: Iterable[ws.Good]) -> Tuple[Tuple[Any, ...], ...]:
    """Immutable identity/attribute signature used by CRN and determinism tests."""
    return tuple((g.gid, g.name, g.weight, g.freq, g.vol) for g in goods)


def _average_ranks(values: Sequence[float]) -> List[float]:
    order = sorted(range(len(values)), key=lambda index: (values[index], index))
    ranks = [0.0] * len(values)
    start = 0
    while start < len(order):
        end = start + 1
        while end < len(order) and values[order[end]] == values[order[start]]:
            end += 1
        average_rank = ((start + 1) + end) / 2.0
        for cursor in range(start, end):
            ranks[order[cursor]] = average_rank
        start = end
    return ranks


def spearman_rho(left: Sequence[float], right: Sequence[float]) -> Optional[float]:
    """Spearman rank correlation with average ranks for ties, zero dependency."""
    if len(left) != len(right):
        raise ValueError("Spearman inputs must have equal length")
    if len(left) < 2:
        return None
    x = _average_ranks(left)
    y = _average_ranks(right)
    x_mean = sum(x) / len(x)
    y_mean = sum(y) / len(y)
    numerator = sum((a - x_mean) * (b - y_mean) for a, b in zip(x, y))
    x_ss = sum((a - x_mean) ** 2 for a in x)
    y_ss = sum((b - y_mean) ** 2 for b in y)
    denominator = math.sqrt(x_ss * y_ss)
    if denominator == 0.0:
        return None
    return numerator / denominator


def scenario_profile(goods: Sequence[ws.Good]) -> Dict[str, Any]:
    """Return router features plus measured legality and correlation evidence."""
    profile = sl.batch_profile(goods)
    weights = [g.weight for g in goods]
    freqs = [g.freq for g in goods]
    volumes = [g.vol for g in goods]
    rho_weight_freq = spearman_rho(weights, freqs)
    rho_weight_volume = spearman_rho(weights, volumes)
    profile.update(
        legal_count=sum(is_legal_cargo(g) for g in goods),
        invalid_count=sum(not is_legal_cargo(g) for g in goods),
        rho_weight_freq=(round(rho_weight_freq, 6) if rho_weight_freq is not None else None),
        rho_weight_volume=(round(rho_weight_volume, 6) if rho_weight_volume is not None else None),
    )
    return profile


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fp:
        for chunk in iter(lambda: fp.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _python_function_sha256(path: Path, function_name: str) -> str:
    """Hash one top-level function body without importing a potentially cyclic module."""
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name:
            segment = ast.get_source_segment(source, node)
            if segment is None:
                lines = source.splitlines(keepends=True)
                segment = "".join(lines[node.lineno - 1:node.end_lineno])
            return hashlib.sha256(segment.encode("utf-8")).hexdigest()
    raise ValueError(f"function {function_name!r} not found in {path}")


def scenario_manifest(
    scenario_id: str, version: str = DEFAULT_VERSION
) -> Dict[str, Any]:
    """Build a deterministic provenance record without any self-referential hash."""
    registry = load_registry(version)
    scenario = registry["scenarios"].get(scenario_id)
    if scenario is None:
        raise KeyError(f"unknown cargo scenario: {scenario_id}")
    registry_path = _registry_path(version)
    sources = {
        "sim/cargo_scenarios.py": Path(__file__).resolve(),
        f"sim/scenarios/{version}.json": registry_path,
        "sim/warehouse_sim.py": HERE / "warehouse_sim.py",
        "sim/instance_gen.py": HERE / "instance_gen.py",
        "sim/mixed_ops.py": HERE / "mixed_ops.py",
        "sim/realism.py": HERE / "realism.py",
        "sim/strategy_lib.py": HERE / "strategy_lib.py",
    }
    mixed_ops_path = HERE / "mixed_ops.py"
    realism_path = HERE / "realism.py"
    strategy_lib_path = HERE / "strategy_lib.py"
    return {
        "schema_version": version,
        "scenario_id": scenario_id,
        "sim_only": True,
        "seed_ranges": copy.deepcopy(registry["seed_ranges"]),
        "scenario_sha256": _canonical_sha256(scenario),
        "registry_sha256": _sha256(registry_path),
        "source_sha256": {name: _sha256(path) for name, path in sorted(sources.items())},
        "function_sha256": {
            "mixed_ops.build_scenario_workload": _python_function_sha256(
                mixed_ops_path, "build_scenario_workload"
            ),
            "mixed_ops.build_workload": _python_function_sha256(mixed_ops_path, "build_workload"),
            "mixed_ops.initial_layout": _python_function_sha256(mixed_ops_path, "initial_layout"),
            "mixed_ops.online_strategy_callable": _python_function_sha256(
                mixed_ops_path, "online_strategy_callable"
            ),
            "mixed_ops.resolve_strategy_mode": _python_function_sha256(
                mixed_ops_path, "resolve_strategy_mode"
            ),
            "realism.build_fault_intervals": _python_function_sha256(
                realism_path, "build_fault_intervals"
            ),
            "realism.build_noise_stream": _python_function_sha256(
                realism_path, "build_noise_stream"
            ),
            "realism.common_arrivals_for_workload": _python_function_sha256(
                realism_path, "common_arrivals_for_workload"
            ),
            "realism.run_tier3": _python_function_sha256(realism_path, "run_tier3"),
            "strategy_lib.explain_selection": _python_function_sha256(
                strategy_lib_path, "explain_selection"
            ),
            "strategy_lib.select_strategy": _python_function_sha256(
                strategy_lib_path, "select_strategy"
            ),
        },
        "scenario": copy.deepcopy(scenario),
    }


__all__ = [
    "DEFAULT_VERSION",
    "build_initial_goods",
    "build_inbound_goods",
    "goods_signature",
    "is_legal_cargo",
    "load_registry",
    "scenario_manifest",
    "scenario_profile",
    "spearman_rho",
]
