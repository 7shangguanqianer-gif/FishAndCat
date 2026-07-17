# -*- coding: utf-8 -*-
"""只读复核 S3 fill-only release：原始字节、源码重放与 detached registry。"""
from __future__ import annotations

import argparse
import gzip
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, Tuple


sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[2]
SIM = ROOT / "sim"
if str(SIM) not in sys.path:
    sys.path.insert(0, str(SIM))

import fill_only as fill


DEFAULT_DIR = ROOT / "l4_showcase" / "out" / "s3_fill_data_gate"
DEFAULT_REGISTRY = (
    ROOT / "l4_showcase" / "evidence" / "s3_fill_release_registry.json"
)
POINTER_SCHEMA = "s3-fill-latest-pointer-v1"
REGISTRY_SCHEMA = "s3-fill-release-registry-v1"
ACTIVE_REGISTRY_STATUSES = frozenset({
    "candidate_data_release", "approved_for_frontend_binding",
})
FRONTEND_APPROVED_STATUS = "approved_for_frontend_binding"
FRONTEND_APPROVAL_SCHEMA = "s3-fill-frontend-binding-approval-v1"


def _reject_non_finite_json(value: str) -> None:
    raise ValueError(f"non-finite JSON constant is forbidden: {value}")


def _loads_strict(text: str) -> Any:
    return json.loads(text, parse_constant=_reject_non_finite_json)


def _read_json_strict(path: Path) -> Any:
    return _loads_strict(path.read_text(encoding="utf-8"))


def _audits(path: Path) -> Iterable[Dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            try:
                yield _loads_strict(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"invalid audit JSON at line {line_number}"
                ) from exc


def _hash_without(value: Dict[str, Any], field: str) -> str:
    return fill.payload_sha256(
        {key: item for key, item in value.items() if key != field}
    )


def _safe_child(root: Path, resource: str) -> Path:
    if not isinstance(resource, str) or not resource:
        raise ValueError("empty resource")
    candidate = (root / resource).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"resource escapes root: {resource}") from exc
    return candidate


def _resolve_release(directory: Path) -> Tuple[Path, Path, Dict[str, Any]]:
    directory = directory.resolve()
    pointer_path = directory / "latest.json"
    if not pointer_path.is_file():
        raise FileNotFoundError(
            f"authoritative latest pointer is missing: {pointer_path}"
        )
    root_doc = _read_json_strict(pointer_path)
    if root_doc.get("schema_version") != POINTER_SCHEMA:
        raise ValueError("latest pointer schema mismatch")
    if root_doc.get("pointer_sha256") != _hash_without(root_doc, "pointer_sha256"):
        raise ValueError("latest pointer hash mismatch")
    if root_doc.get("authoritative_entrypoint") != "latest.json":
        raise ValueError("latest pointer authoritative entrypoint mismatch")
    manifest_path = _safe_child(directory, root_doc.get("manifest_resource"))
    if not manifest_path.is_file():
        raise FileNotFoundError(manifest_path)
    return manifest_path, manifest_path.parent, root_doc


def _release_source_hashes() -> Dict[str, str]:
    return {
        "sim/fill_only.py": fill.file_sha256(SIM / "fill_only.py"),
        "sim/warehouse_sim.py": fill.file_sha256(SIM / "warehouse_sim.py"),
        "sim/lap_optimal.py": fill.file_sha256(SIM / "lap_optimal.py"),
        "l4_showcase/tools/generate_s3_fill_trace.py": fill.file_sha256(
            ROOT / "l4_showcase" / "tools" / "generate_s3_fill_trace.py"
        ),
        "l4_showcase/tools/validate_s3_fill_trace.py": fill.file_sha256(__file__),
        "l4_showcase/evidence/s3_fill_requirements.lock": fill.file_sha256(
            ROOT / "l4_showcase" / "evidence" / "s3_fill_requirements.lock"
        ),
    }


def _registry_entry(registry_path: Path, manifest: Dict[str, Any],
                    manifest_path: Path, pointer: Dict[str, Any]) -> Tuple[Dict[str, Any] | None, str]:
    if not registry_path.is_file():
        return None, "registry_missing"
    registry = _read_json_strict(registry_path)
    if registry.get("schema_version") != REGISTRY_SCHEMA:
        return None, "registry_schema"
    matches = [
        item for item in registry.get("entries", [])
        if item.get("manifest_payload_sha256") == manifest.get("manifest_sha256")
    ]
    if len(matches) != 1:
        return None, "registry_entry_count"
    entry = matches[0]
    if entry.get("release_id") != pointer.get("release_id"):
        return None, "registry_release_id"
    if entry.get("pointer_sha256") != pointer.get("pointer_sha256"):
        return None, "registry_pointer_sha256"
    if registry.get("active_release_id") != pointer.get("release_id"):
        return None, "registry_active_release_id"
    if entry.get("manifest_file_sha256") != fill.file_sha256(manifest_path):
        return None, "registry_manifest_file"
    if entry.get("source_sha256") != _release_source_hashes():
        return None, "registry_sources"
    if entry.get("trust_level") != "local_detached_registry_not_signature":
        return None, "registry_trust_label"
    if entry.get("status") not in ACTIVE_REGISTRY_STATUSES:
        return entry, "registry_lifecycle_status"
    return entry, "ok"


def _frontend_binding_status(entry: Dict[str, Any] | None) -> Tuple[bool, str]:
    """Validate detached loader approval without mutating the immutable release."""
    if not entry or entry.get("status") != FRONTEND_APPROVED_STATUS:
        return False, "registry_not_approved_for_frontend"
    approval = entry.get("frontend_binding_approval")
    if not isinstance(approval, dict) or approval.get("schema_version") != FRONTEND_APPROVAL_SCHEMA:
        return False, "frontend_approval_schema"
    if approval.get("bundle_schema_version") != "s3-fill-frontend-bundle-v1":
        return False, "frontend_bundle_schema"
    sources = approval.get("loader_source_sha256")
    required_sources = {
        "l4_showcase/tools/build_s3_fill_frontend_bundle.py": (
            ROOT / "l4_showcase" / "tools" / "build_s3_fill_frontend_bundle.py"
        ),
        "l4_showcase/tools/test_s3_fill_frontend_bundle.py": (
            ROOT / "l4_showcase" / "tools" / "test_s3_fill_frontend_bundle.py"
        ),
    }
    if not isinstance(sources, dict) or set(sources) != set(required_sources):
        return False, "frontend_loader_sources"
    if any(sources[name] != fill.file_sha256(path) for name, path in required_sources.items()):
        return False, "frontend_loader_source_hash"
    result = approval.get("test_result")
    if not isinstance(result, dict) or result.get("passed") != 10 or result.get("failed") != 0:
        return False, "frontend_loader_test_result"
    if approval.get("release_id") != entry.get("release_id"):
        return False, "frontend_approval_release_id"
    return True, "ok"


def _expected_derived(manifest: Dict[str, Any]) -> Dict[str, Any]:
    lanes = manifest["online_lanes"]
    offline = manifest["offline_references"][0]
    lap = manifest["lap_exact_reference"]
    lap_score = lap["objectives"]["score"]["objective_value"]
    lap_expected = lap["objectives"]["exp_t"][
        "normalized_expected_retrieval_s"
    ]
    return {
        "scope": "same static instance only",
        "awra_score_gap_to_exact_lap_pct": round(
            (offline["metrics"]["score_total"] - lap_score)
            / lap_score * 100.0, 9
        ),
        "awra_expected_retrieval_gap_to_exp_t_lap_pct": round(
            (offline["metrics"]["expected_retrieval_s"] - lap_expected)
            / lap_expected * 100.0, 9
        ),
        "online_fixed_score_diagnostic_gap_to_exact_lap_pct": {
            lane["algorithm"]["id"]: round(
                (lane["metrics"]["fixed_score_diagnostic_total"] - lap_score)
                / lap_score * 100.0, 9
            ) for lane in lanes
        },
        "method_guard": (
            "LAP gap is valid only for this identical static instance and matching objective; "
            "it is not an online oracle or theoretical universal upper bound"
        ),
    }


def validate(directory: Path = DEFAULT_DIR,
             registry_path: Path = DEFAULT_REGISTRY) -> Dict[str, Any]:
    manifest_path, release_dir, pointer = _resolve_release(directory)
    manifest = _read_json_strict(manifest_path)
    errors = []
    checks: Dict[str, Any] = {}

    checks["manifest_sha256"] = (
        manifest.get("manifest_sha256")
        == _hash_without(manifest, "manifest_sha256")
    )
    checks["atomic_pointer"] = (
        pointer.get("manifest_file_sha256") == fill.file_sha256(manifest_path)
        and pointer.get("manifest_payload_sha256")
        == manifest.get("manifest_sha256")
        and pointer.get("release_id") == manifest.get("manifest_sha256", "")[:20]
        and pointer.get("authoritative_entrypoint") == "latest.json"
    )

    shared = manifest.get("shared_input", {})
    checks["shared_input_sha256"] = (
        shared.get("shared_input_sha256")
        == _hash_without(shared, "shared_input_sha256")
    )
    checks["schema"] = (
        manifest.get("schema_version") == fill.SCHEMA_VERSION
        and manifest.get("sim_only") is True
        and shared.get("trace_kind") == "FILL_ONLY"
    )
    checks["capacity"] = shared.get("capacity") == {
        "cols": 20, "tiers": 20, "total_slots": 400,
        "preoccupied_slots": 133, "managed_capacity": 267,
        "rule": "sum", "rule_expression": "(col+tier)%3==0",
        "start": {"managed_goods": 0, "total_unavailable": 133},
        "full_endpoint": {"managed_goods": 267, "total_unavailable": 400},
    }
    normal = shared.get("score_policy", {}).get("normalization", {})
    checks["causal_fixed_normalization"] = (
        normal.get("source")
        == "predeclared_profile_bounds_not_cargo_catalog_statistics"
        and normal.get("causal_scope") == "known_before_first_arrival"
        and normal.get("w_max") == 60.0
        and normal.get("f_max") == 100.0
    )

    profile = shared.get("profile", {})
    try:
        expected_shared = fill.build_shared_input(
            count=int(profile["target_managed_goods"]),
            seed=int(profile["seed"]), case=str(profile["case"]),
        )
        checks["shared_source_rebuild"] = (
            fill.canonical_json_bytes(shared)
            == fill.canonical_json_bytes(expected_shared)
        )
    except Exception as exc:
        expected_shared = shared
        checks["shared_source_rebuild"] = False
        errors.append(f"shared_source_rebuild:{type(exc).__name__}")

    checks["shared_sources_current"] = (
        shared.get("source_sha256")
        == expected_shared.get("source_sha256")
    )
    checks["manifest_sources_current"] = (
        manifest.get("source_sha256") == {
            "l4_showcase/tools/generate_s3_fill_trace.py": _release_source_hashes()[
                "l4_showcase/tools/generate_s3_fill_trace.py"
            ],
            "l4_showcase/tools/validate_s3_fill_trace.py": _release_source_hashes()[
                "l4_showcase/tools/validate_s3_fill_trace.py"
            ],
        }
    )

    lanes = manifest.get("online_lanes", [])
    lane_results = {}
    for lane in lanes:
        lane_id = lane.get("lane_id", "unknown")
        resource = lane.get("candidate_audit", {}).get("resource")
        try:
            audit_path = _safe_child(release_dir, resource)
        except (TypeError, ValueError) as exc:
            lane_results[lane_id] = {
                "errors": [f"unsafe_audit_resource:{type(exc).__name__}"]
            }
            continue
        if audit_path.parent != release_dir or not audit_path.is_file():
            lane_results[lane_id] = {"errors": ["missing_audit_resource"]}
            continue
        lane_errors = fill.validate_online_lane(expected_shared, lane)
        audit_errors = fill.validate_candidate_audits(lane, _audits(audit_path))
        semantic_errors = fill.replay_validate_online_lane(
            expected_shared, lane, _audits(audit_path)
        )
        raw_hash = fill.file_sha256(audit_path)
        if not (
            raw_hash == lane.get("candidate_audit", {}).get("file_sha256")
            == manifest.get("audit_files", {}).get(resource, {}).get("sha256")
        ):
            audit_errors.append("raw_file_sha256")
        lane_results[lane_id] = {
            "errors": lane_errors + audit_errors + semantic_errors,
            "raw_file_sha256": raw_hash,
            "event_count": len(lane.get("events", [])),
        }
    expected_algorithms = set(fill.ONLINE_ALGORITHMS)
    checks["online_lane_set"] = (
        len(lanes) == len(expected_algorithms)
        and {lane.get("algorithm", {}).get("id") for lane in lanes}
        == expected_algorithms
        and set(lane_results) == {
            f"online_{algorithm}" for algorithm in expected_algorithms
        }
    )
    checks["online_lanes"] = bool(lane_results) and all(
        not result["errors"] for result in lane_results.values()
    )

    offline = manifest.get("offline_references", [{}])[0]
    lap = manifest.get("lap_exact_reference", {})
    try:
        expected_offline = fill.run_awra_offline_reference(expected_shared)
        expected_lap = fill.run_lap_exact_references(expected_shared)
        checks["offline_source_replay"] = (
            fill.canonical_json_bytes(offline)
            == fill.canonical_json_bytes(expected_offline)
        )
        checks["lap_source_replay"] = (
            fill.canonical_json_bytes(lap)
            == fill.canonical_json_bytes(expected_lap)
        )
    except Exception as exc:
        checks["offline_source_replay"] = False
        checks["lap_source_replay"] = False
        errors.append(f"reference_source_replay:{type(exc).__name__}")
    checks["derived_comparisons"] = (
        manifest.get("derived_comparisons") == _expected_derived(manifest)
    )
    checks["fairness"] = (
        manifest.get("online_fairness", {}).get(
            "all_lane_input_hashes_identical"
        ) is True
        and manifest.get("online_fairness", {}).get("fallback_forbidden") is True
        and manifest.get("online_fairness", {}).get("comparison_scope")
        == "same_information_set_online_only"
    )
    checks["interpretation_guard"] = (
        manifest.get("interpretation_guard", {})
        .get("full_fill_flat_metrics_observed", {})
        == {"makespan_s": True, "round_trip_path_m": True}
        and manifest.get("interpretation_guard", {})
        .get("collinearity_rule", {})
        .get("stability_raw_equals_energy_proxy_raw") is True
    )
    checks["gate_claim"] = (
        manifest.get("data_gate", {}).get("pass") is True
        and manifest.get("data_gate", {}).get("errors") == []
        and manifest.get("data_gate", {}).get("checkpoint_counts")
        == [0, 67, 134, 201, 241, 267]
        and manifest.get("data_gate", {}).get("front_end_evidence_binding")
        == "DISABLED_PENDING_VERIFIED_LOADER"
    )

    registry_entry, registry_status = _registry_entry(
        registry_path.resolve(), manifest, manifest_path, pointer
    )
    checks["detached_registry"] = registry_status == "ok"
    if registry_status != "ok":
        errors.append(registry_status)

    frontend_bindable, frontend_binding_status = _frontend_binding_status(
        registry_entry if registry_status == "ok" else None
    )

    errors.extend(name for name, passed in checks.items() if not passed)
    for lane_id, result in lane_results.items():
        errors.extend(f"{lane_id}:{item}" for item in result["errors"])
    data_integrity_pass = not errors
    report = {
        "schema_version": "s3-fill-independent-validation-v3",
        "scope": (
            "read-only raw bytes + source-rebuilt shared input + per-event semantic replay + "
            "offline/LAP replay + local detached registry; registry is not a cryptographic signature"
        ),
        "release_id": pointer.get("release_id"),
        "manifest_path": str(manifest_path),
        "manifest_file_sha256": fill.file_sha256(manifest_path),
        "manifest_payload_sha256": manifest.get("manifest_sha256"),
        "registry_entry": registry_entry,
        "registry_lifecycle_status": (
            registry_entry.get("status") if registry_entry else None
        ),
        "frontend_binding_status": frontend_binding_status,
        "front_end_bindable": data_integrity_pass and frontend_bindable,
        "checks": checks,
        "lanes": lane_results,
        "data_integrity_pass": data_integrity_pass,
        "pass": data_integrity_pass,
        "errors": sorted(set(errors)),
    }
    report["report_payload_sha256"] = fill.payload_sha256(report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", type=Path, default=DEFAULT_DIR)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument(
        "--report", type=Path,
        help="optional explicit report destination; omitted means read-only stdout",
    )
    args = parser.parse_args()
    report = validate(args.dir, args.registry)
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(
                report, ensure_ascii=False, sort_keys=True, indent=2,
                allow_nan=False,
            ) + "\n",
            encoding="utf-8",
        )
    print(
        f"S3 fill-only independent validation "
        f"{'PASS' if report['pass'] else 'FAIL'}; "
        f"report={args.report if args.report else 'stdout-only'}; "
        f"sha256={report['report_payload_sha256']}"
    )
    if not report["pass"]:
        print(json.dumps(report["errors"], ensure_ascii=False))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
