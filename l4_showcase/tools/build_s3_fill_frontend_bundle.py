# -*- coding: utf-8 -*-
"""Build the checked S3 fill-only payload used by file:// showcase pages."""
from __future__ import annotations

import argparse
import gzip
import json
import math
import os
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, Tuple


sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[2]
SIM = ROOT / "sim"
if str(SIM) not in sys.path:
    sys.path.insert(0, str(SIM))

import fill_only as fill
import validate_s3_fill_trace as validator


DEFAULT_DIR = ROOT / "l4_showcase" / "out" / "s3_fill_data_gate"
DEFAULT_REGISTRY = ROOT / "l4_showcase" / "evidence" / "s3_fill_release_registry.json"
DEFAULT_OUTPUT = ROOT / "l4_showcase" / "src" / "s3_fill_store.js"
BUNDLE_SCHEMA = "s3-fill-frontend-bundle-v1"
QUEUE_SCHEMA = "s3-fill-verified-queue-envelope-v1"
DECISION_EVIDENCE_SCHEMA = "s3-fill-decision-top3-v1"
EXPECTED_ALGORITHMS = tuple(fill.ONLINE_ALGORITHMS)


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON: {path}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def _safe_child(root: Path, resource: str) -> Path:
    if not isinstance(resource, str) or not resource:
        raise ValueError("empty manifest resource")
    candidate = (root / resource).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"manifest resource escapes release root: {resource}") from exc
    return candidate


def _assert_finite(value: Any, path: str = "payload") -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"non-finite number at {path}")
    if isinstance(value, dict):
        for key, item in value.items():
            _assert_finite(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _assert_finite(item, f"{path}[{index}]")


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant in candidate audit: {value}")


def _audit_records(path: Path) -> Iterable[Dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            try:
                value = json.loads(line, parse_constant=_reject_json_constant)
            except (json.JSONDecodeError, ValueError) as exc:
                raise ValueError(
                    f"invalid candidate audit JSON at {path.name}:{line_number}"
                ) from exc
            if not isinstance(value, dict):
                raise ValueError(
                    f"candidate audit object required at {path.name}:{line_number}"
                )
            yield value


def _compact_top_candidate(candidate: Dict[str, Any], algorithm: str) -> Dict[str, Any]:
    projected = {
        "rank": candidate["rank"],
        "slot": candidate["slot"],
        "selected": candidate["selected"],
        "travel_time_s": candidate["travel_time_s"],
        "path_one_way_m": candidate["path_one_way_m"],
        "tie_group": candidate["tie_group"],
        "tie_size": candidate["tie_size"],
        "objective_value": candidate["objective_tie_key"][0],
    }
    if algorithm == "score":
        terms = candidate.get("score_terms")
        if not isinstance(terms, dict):
            raise ValueError("SCORE Top 3 candidate lacks score_terms")
        projected["score_terms"] = terms
    elif "score_terms" in candidate:
        raise ValueError(f"{algorithm} candidate unexpectedly exposes SCORE terms")
    return projected


def _decision_evidence(
    directory: Path,
    pointer: Dict[str, Any],
    lanes: list[Dict[str, Any]],
) -> Dict[str, Any]:
    release_dir = _safe_child(directory, pointer["manifest_resource"]).parent
    projected_lanes = []
    for lane in lanes:
        algorithm = lane["algorithm"]["id"]
        descriptor = lane.get("candidate_audit")
        if not isinstance(descriptor, dict):
            raise ValueError(f"{algorithm} candidate audit descriptor missing")
        audit_path = _safe_child(release_dir, descriptor.get("resource"))
        if fill.file_sha256(audit_path) != descriptor.get("file_sha256"):
            raise ValueError(f"{algorithm} candidate audit file hash mismatch")
        events = lane["events"]
        records = []
        audits = iter(_audit_records(audit_path))
        for expected_index, event in enumerate(events, start=1):
            try:
                audit = next(audits)
            except StopIteration as exc:
                raise ValueError(
                    f"{algorithm} candidate audit ended before event {expected_index}"
                ) from exc
            if (
                audit.get("event_index") != expected_index
                or audit.get("algorithm") != algorithm
                or audit.get("selected_slot") != event["decision"]["selected_slot"]
                or audit.get("audit_sha256")
                != event["decision"]["candidate_audit_ref"]["audit_sha256"]
            ):
                raise ValueError(
                    f"{algorithm} event {expected_index} candidate audit linkage mismatch"
                )
            legal = [item for item in audit.get("candidates", []) if item.get("legal")]
            top3 = sorted(legal, key=lambda item: item.get("rank", 10**9))[:3]
            expected_top_count = min(3, int(audit.get("legal_count", 0)))
            if (
                len(top3) != expected_top_count
                or expected_top_count < 1
                or [item.get("rank") for item in top3]
                != list(range(1, expected_top_count + 1))
                or top3[0].get("selected") is not True
                or any(item.get("selected") for item in top3[1:])
                or top3[0].get("slot") != event["decision"]["selected_slot"]
                or event["decision"].get("selected_rank") != 1
            ):
                raise ValueError(
                    f"{algorithm} event {expected_index} Top 3 selection mismatch"
                )
            compact = [_compact_top_candidate(item, algorithm) for item in top3]
            if algorithm == "score":
                selected_score = event["decision"].get("selected_score")
                score_total = compact[0]["score_terms"]["score_total"]
                if not math.isclose(selected_score, score_total, abs_tol=1e-9):
                    raise ValueError(
                        f"score event {expected_index} selected score mismatch"
                    )
            elif event["decision"].get("selected_score") is not None:
                raise ValueError(
                    f"{algorithm} event {expected_index} must not expose SCORE total"
                )
            records.append({
                "event_index": expected_index,
                "audit_sha256": audit["audit_sha256"],
                "decision_basis": audit["decision_basis"],
                "legal_count": audit["legal_count"],
                "rejected_count": audit["rejected_count"],
                "top3": compact,
            })
        if len(records) != len(events):
            raise ValueError(f"{algorithm} candidate audit record count mismatch")
        try:
            next(audits)
        except StopIteration:
            pass
        else:
            raise ValueError(f"{algorithm} candidate audit has extra records")
        projected_lanes.append({
            "lane_id": lane["lane_id"],
            "algorithm": algorithm,
            "audit_resource": descriptor["resource"],
            "audit_file_sha256": descriptor["file_sha256"],
            "events": records,
        })
    return {
        "schema_version": DECISION_EVIDENCE_SCHEMA,
        "scope": "Up to Top 3 legal candidates per online event from immutable candidate audit",
        "lanes": projected_lanes,
    }


def _online_lanes(manifest: Dict[str, Any]) -> list[Dict[str, Any]]:
    lanes = manifest.get("online_lanes")
    if not isinstance(lanes, list):
        raise ValueError("manifest online_lanes must be a list")
    by_algorithm: Dict[str, Dict[str, Any]] = {}
    for lane in lanes:
        if not isinstance(lane, dict):
            raise ValueError("manifest online lane is not an object")
        algorithm = lane.get("algorithm", {}).get("id")
        lane_id = lane.get("lane_id")
        if not isinstance(algorithm, str) or lane_id != f"online_{algorithm}":
            raise ValueError("malformed online lane identity")
        if algorithm in by_algorithm:
            raise ValueError(f"duplicate online algorithm: {algorithm}")
        by_algorithm[algorithm] = lane
    if tuple(by_algorithm) != EXPECTED_ALGORITHMS or set(by_algorithm) != set(EXPECTED_ALGORITHMS):
        raise ValueError(
            f"online algorithms must exactly equal {EXPECTED_ALGORITHMS}; "
            f"received {tuple(by_algorithm)}"
        )
    return [by_algorithm[algorithm] for algorithm in EXPECTED_ALGORITHMS]


def _active_registry_entry(registry: Dict[str, Any], release_id: str) -> Dict[str, Any]:
    if registry.get("active_release_id") != release_id:
        raise ValueError("registry active release id does not match pointer")
    entries = [
        item for item in registry.get("entries", [])
        if isinstance(item, dict) and item.get("release_id") == release_id
    ]
    if len(entries) != 1:
        raise ValueError("registry must contain exactly one active release entry")
    return entries[0]


def _read_checked_release(
    directory: Path = DEFAULT_DIR,
    registry_path: Path = DEFAULT_REGISTRY,
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    """Read a coherent active release only after independent source replay passes."""
    directory = directory.resolve()
    registry_path = registry_path.resolve()
    report = validator.validate(directory, registry_path)
    if report.get("pass") is not True:
        raise ValueError(f"S3 independent validator did not pass: {report.get('errors')}")

    pointer = _read_json(directory / "latest.json")
    manifest_path = _safe_child(directory, pointer.get("manifest_resource"))
    manifest = _read_json(manifest_path)
    registry = _read_json(registry_path)
    release_id = pointer.get("release_id")
    if not isinstance(release_id, str):
        raise ValueError("active pointer release id is missing")

    if (
        report.get("release_id") != release_id
        or report.get("manifest_file_sha256") != fill.file_sha256(manifest_path)
        or report.get("manifest_payload_sha256") != manifest.get("manifest_sha256")
        or pointer.get("manifest_file_sha256") != fill.file_sha256(manifest_path)
        or pointer.get("manifest_payload_sha256") != manifest.get("manifest_sha256")
    ):
        raise ValueError("active release changed while the validator was running")

    entry = _active_registry_entry(registry, release_id)
    if (
        entry.get("manifest_payload_sha256") != manifest.get("manifest_sha256")
        or entry.get("manifest_file_sha256") != fill.file_sha256(manifest_path)
        or entry.get("pointer_sha256") != pointer.get("pointer_sha256")
    ):
        raise ValueError("registry active entry does not match active manifest/pointer")
    return pointer, manifest, registry, entry, report


def build_payload(
    directory: Path = DEFAULT_DIR,
    registry_path: Path = DEFAULT_REGISTRY,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Project the active validated release into an online-only frontend payload."""
    pointer, manifest, registry, registry_entry, report = _read_checked_release(
        directory, registry_path
    )
    shared = manifest.get("shared_input")
    if not isinstance(shared, dict):
        raise ValueError("manifest shared_input is missing")
    required_shared = {"capacity", "cargo_catalog", "score_policy"}
    if not required_shared.issubset(shared):
        raise ValueError("manifest shared_input lacks frontend reconstruction fields")
    lanes = _online_lanes(manifest)

    shared_provenance = {
        key: value for key, value in shared.items() if key not in required_shared
    }
    payload: Dict[str, Any] = {
        "schema_version": BUNDLE_SCHEMA,
        "release": {
            "release_id": pointer["release_id"],
            "publication_model": pointer["publication_model"],
        },
        "manifest": {
            "schema_version": manifest["schema_version"],
            "manifest_resource": pointer["manifest_resource"],
            "manifest_file_sha256": pointer["manifest_file_sha256"],
            "manifest_payload_sha256": manifest["manifest_sha256"],
            "source": manifest["source"],
            "source_sha256": manifest["source_sha256"],
            "sim_only": manifest["sim_only"],
            "evidence_boundary": manifest["evidence_boundary"],
            "data_gate": manifest["data_gate"],
        },
        "pointer": pointer,
        "registry": {
            "schema_version": registry["schema_version"],
            "active_release_id": registry["active_release_id"],
            "active_entry": registry_entry,
        },
        "validator": {
            "module": "l4_showcase/tools/validate_s3_fill_trace.py",
            "schema_version": report["schema_version"],
            "scope": report["scope"],
            "pass": report["pass"],
            "data_integrity_pass": report["data_integrity_pass"],
            "front_end_bindable": report["front_end_bindable"],
            "frontend_binding_status": report["frontend_binding_status"],
            "registry_lifecycle_status": report["registry_lifecycle_status"],
            "report_payload_sha256": report["report_payload_sha256"],
            "manifest_file_sha256": report["manifest_file_sha256"],
            "manifest_payload_sha256": report["manifest_payload_sha256"],
            "checks": report["checks"],
        },
        "shared_input_provenance": shared_provenance,
        "capacity": shared["capacity"],
        "cargo_catalog": shared["cargo_catalog"],
        "score_policy": shared["score_policy"],
        "online_lanes": lanes,
        "decision_evidence": _decision_evidence(directory, pointer, lanes),
    }
    _assert_finite(payload)
    payload["bundle_payload_sha256"] = fill.payload_sha256(payload)
    return payload, report


def render_bundle(payload: Dict[str, Any]) -> bytes:
    """Render a compact script that never exposes a bare, unverified payload global."""
    if payload.get("bundle_payload_sha256") != fill.payload_sha256(
        {key: value for key, value in payload.items() if key != "bundle_payload_sha256"}
    ):
        raise ValueError("bundle payload SHA-256 mismatch before rendering")
    _assert_finite(payload)
    encoded = fill.canonical_json_bytes(payload).decode("utf-8")
    source = "\n".join((
        "/* S3 fill-only verified frontend bundle; generated deterministically. */",
        "(function (root) {",
        "  \"use strict\";",
        "  var payload = /*__S3_FILL_PAYLOAD_BEGIN__*/" + encoded + "/*__S3_FILL_PAYLOAD_END__*/;",
        "  var register = root && root.__S3_FILL_REGISTER__;",
        "  if (typeof register === \"function\") {",
        "    register(payload);",
        "    return;",
        "  }",
        "  var queueKey = \"__S3_FILL_VERIFIED_QUEUE__\";",
        "  if (!Object.prototype.hasOwnProperty.call(root, queueKey)) {",
        "    Object.defineProperty(root, queueKey, {",
        "      value: [], writable: false, enumerable: false, configurable: false",
        "    });",
        "  }",
        "  var queue = root[queueKey];",
        "  if (!Array.isArray(queue)) {",
        "    throw new Error(\"S3 fill verified queue collision\");",
        "  }",
        "  queue.push(Object.freeze({",
        "    schema_version: \"" + QUEUE_SCHEMA + "\",",
        "    bundle_payload_sha256: payload.bundle_payload_sha256,",
        "    payload: payload",
        "  }));",
        "})(typeof window !== \"undefined\" ? window : globalThis);",
        "",
    ))
    return source.encode("utf-8")


def write_bundle(
    output: Path = DEFAULT_OUTPUT,
    directory: Path = DEFAULT_DIR,
    registry_path: Path = DEFAULT_REGISTRY,
) -> Tuple[Dict[str, Any], Dict[str, Any], str]:
    """Write the sole file:// bundle target after validator-gated construction."""
    output = output.resolve()
    if output != DEFAULT_OUTPUT.resolve():
        raise ValueError(f"output path is fixed to {DEFAULT_OUTPUT}")
    payload, report = build_payload(directory, registry_path)
    rendered = render_bundle(payload)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(rendered)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, output)
    finally:
        if temporary.exists():
            temporary.unlink()
    return payload, report, fill.file_sha256(output)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    payload, report, file_sha256 = write_bundle()
    print(
        "S3 fill frontend bundle PASS; "
        f"release={payload['release']['release_id']}; "
        f"payload_sha256={payload['bundle_payload_sha256']}; "
        f"file_sha256={file_sha256}; "
        f"validator_sha256={report['report_payload_sha256']}"
    )


if __name__ == "__main__":
    main()
