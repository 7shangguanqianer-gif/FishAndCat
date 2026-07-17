# -*- coding: utf-8 -*-
"""生成独立 S3 fill-only 数据门；不触碰既有 S3 v2 trace/store。"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import shutil
import sys
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterable


ROOT = Path(__file__).resolve().parents[2]
SIM = ROOT / "sim"
if str(SIM) not in sys.path:
    sys.path.insert(0, str(SIM))

import fill_only as fill


DEFAULT_OUT = ROOT / "l4_showcase" / "out" / "s3_fill_data_gate"
POINTER_SCHEMA = "s3-fill-latest-pointer-v1"
ALIAS_SCHEMA = "s3-fill-release-alias-v1"


class DeterministicGzipJsonl:
    def __init__(self, path: Path):
        self.path = path
        self._raw = None
        self._gzip = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._raw = self.path.open("wb")
        self._gzip = gzip.GzipFile(
            filename="", mode="wb", fileobj=self._raw, mtime=0
        )
        return self

    def write(self, value: Dict[str, Any]) -> None:
        self._gzip.write(fill.canonical_json_bytes(value) + b"\n")

    def __exit__(self, exc_type, exc, traceback):
        try:
            if self._gzip is not None:
                self._gzip.close()
        finally:
            if self._raw is not None:
                self._raw.close()


def iter_gzip_jsonl(path: Path) -> Iterable[Dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid candidate audit JSONL line {line_number}") from exc


def _seal_lane(lane: Dict[str, Any]) -> None:
    lane.pop("lane_result_sha256", None)
    lane["lane_result_sha256"] = fill.payload_sha256(lane)


def _write_json(path: Path, value: Dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )


def _atomic_write_json(path: Path, value: Dict[str, Any]) -> None:
    temp = path.with_name(f".{path.name}.tmp-{os.getpid()}-{uuid.uuid4().hex}")
    _write_json(temp, value)
    os.replace(temp, path)


def _atomic_write_text(path: Path, value: str) -> None:
    temp = path.with_name(f".{path.name}.tmp-{os.getpid()}-{uuid.uuid4().hex}")
    temp.write_text(value, encoding="utf-8")
    os.replace(temp, path)


@contextmanager
def _exclusive_publish_lock(outdir: Path):
    outdir.parent.mkdir(parents=True, exist_ok=True)
    lock = outdir.parent / f".{outdir.name}.publish.lock"
    try:
        descriptor = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        try:
            owner_pid = lock.read_text(encoding="ascii").strip()
        except OSError:
            owner_pid = "unknown"
        raise RuntimeError(
            f"publish lock already exists: {lock}; refusing automatic stale-lock removal. "
            f"Confirm PID {owner_pid} is not running, then manually delete {lock}."
        ) from exc
    try:
        with os.fdopen(descriptor, "w", encoding="ascii") as handle:
            handle.write(str(os.getpid()))
        yield
    finally:
        lock.unlink(missing_ok=True)


def _tree_fingerprint(directory: Path) -> Dict[str, str]:
    return {
        str(path.relative_to(directory)).replace("\\", "/"): fill.file_sha256(path)
        for path in sorted(item for item in directory.rglob("*") if item.is_file())
    }


def _canonical_release_algorithms(algorithms: Iterable[str]) -> tuple[str, ...]:
    requested = tuple(algorithms)
    expected = tuple(fill.ONLINE_ALGORITHMS)
    if len(requested) != len(expected) or set(requested) != set(expected):
        raise ValueError(
            f"release algorithms must exactly equal {fill.ONLINE_ALGORITHMS}; "
            f"received {requested}"
        )
    return expected


def _quarantine_legacy_flat_files(outdir: Path) -> None:
    """首次升级时保留旧平铺证据，但让 active pointer 不再引用它。"""
    marker = outdir / "s3_fill_data_gate.json"
    is_pointer = False
    if marker.is_file():
        try:
            is_pointer = json.loads(marker.read_text(encoding="utf-8")).get(
                "schema_version"
            ) in {POINTER_SCHEMA, ALIAS_SCHEMA}
        except (OSError, ValueError, AttributeError):
            pass
    if is_pointer:
        return
    names = [
        "s3_fill_data_gate.json", "s3_fill_data_gate_summary.md",
        "s3_fill_validation_report.json",
        *[f"candidate_audit_online_{name}.jsonl.gz" for name in fill.ONLINE_ALGORITHMS],
    ]
    existing = [outdir / name for name in names if (outdir / name).is_file()]
    if not existing:
        return
    legacy = outdir / "legacy_flat_pre_atomic"
    legacy.mkdir(parents=True, exist_ok=True)
    for path in existing:
        target = legacy / path.name
        if target.exists():
            raise RuntimeError(f"legacy quarantine target already exists: {target}")
        os.replace(path, target)


def _summary(manifest: Dict[str, Any]) -> str:
    lines = [
        "# S3 fill-only 数据门摘要",
        "",
        "- 证据边界：single-seed SIM 容量/回放门，不是头条 KPI、PLC 实测或现场吞吐。",
        "- 容量口径：133 个官方预占格 + 267 个管理货位 = 400。",
        "- 起点：管理货物 0/267；总不可用 133/400。",
        "- 终点：管理货物 267/267；总占用 400/400（静态终点，不证明满库连续运行）。",
        f"- 数据生成门：{'PASS' if manifest['data_gate']['pass'] else 'FAIL'}；发布仍须独立语义重放与 detached registry。",
        "",
        "## 同信息集在线赛道",
        "",
        "| 算法 | 状态 | 入库件数 | makespan(s) | 期望取货(s) | 路程(m) | 提升功代理(kg·m) |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for lane in manifest["online_lanes"]:
        metrics = lane["metrics"]
        lines.append(
            f"| {lane['algorithm']['id']} | {lane['status']} | {metrics['placed']} | "
            f"{metrics['makespan_s']:.1f} | {metrics['expected_retrieval_s']:.3f} | "
            f"{metrics['round_trip_path_m']:.1f} | {metrics['lift_work_proxy_kgm']:.1f} |"
        )
    offline = manifest["offline_references"][0]
    lines += [
        "",
        "## 独立参照",
        "",
        f"- AWRA-LS：{offline['status']}，{offline['placed']}/267；它是离线整批参照，"
        "不与在线赛道宣称同信息集公平竞速。",
        "- LAP：同一静态实例精确参照，仅在该实例与相同目标函数下成立。",
        "- 候选槽全审计按在线赛道分别写入确定性 gzip JSONL。正式前端绑定尚未实现；在 loader 验证完成前，A/D 的 Top3 证据功能必须保持禁用。",
        "",
    ]
    return "\n".join(lines)


def _build_release(outdir: Path, seed: int = 2026,
                    case: str = "skew", algorithms=("seq", "near", "score")) -> Dict[str, Any]:
    algorithms = _canonical_release_algorithms(algorithms)
    outdir.mkdir(parents=True, exist_ok=True)
    shared = fill.build_shared_input(seed=seed, case=case)
    lanes = []
    validation: Dict[str, Any] = {}
    audit_files = {}
    for algorithm in algorithms:
        filename = f"candidate_audit_online_{algorithm}.jsonl.gz"
        path = outdir / filename
        with DeterministicGzipJsonl(path) as writer:
            lane = fill.run_online_lane(
                shared, algorithm, audit_sink=writer.write, audit_resource=filename
            )
        file_hash = fill.file_sha256(path)
        lane["candidate_audit"]["file_sha256"] = file_hash
        lane["candidate_audit"]["compression"] = "gzip-mtime-0-jsonl"
        _seal_lane(lane)
        lane_errors = fill.validate_online_lane(shared, lane)
        audit_errors = fill.validate_candidate_audits(lane, iter_gzip_jsonl(path))
        semantic_errors = fill.replay_validate_online_lane(
            shared, lane, iter_gzip_jsonl(path)
        )
        validation[lane["lane_id"]] = {
            "lane_errors": lane_errors,
            "candidate_audit_errors": audit_errors,
            "semantic_replay_errors": semantic_errors,
        }
        audit_files[filename] = {
            "sha256": file_hash, "events": len(lane["events"]),
        }
        lanes.append(lane)

    offline = fill.run_awra_offline_reference(shared)
    lap = fill.run_lap_exact_references(shared)
    lap_score = lap["objectives"]["score"]["objective_value"]
    lap_expected = lap["objectives"]["exp_t"]["normalized_expected_retrieval_s"]
    derived_comparisons = {
        "scope": "same static instance only",
        "awra_score_gap_to_exact_lap_pct": round(
            (offline["metrics"]["score_total"] - lap_score) / lap_score * 100.0, 9
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
    shared_hashes = {lane["shared_input_sha256"] for lane in lanes}
    online_fairness = {
        "comparison_scope": "same_information_set_online_only",
        "lane_ids": [lane["lane_id"] for lane in lanes],
        "shared_input_sha256": shared["shared_input_sha256"],
        "all_lane_input_hashes_identical": shared_hashes == {shared["shared_input_sha256"]},
        "same_cargo_catalog_and_order": True,
        "same_geometry_motion_and_score_normalization": True,
        "independent_lane_sim_clocks": True,
        "fallback_forbidden": True,
        "offline_references_excluded": [offline["reference_id"], lap["reference_id"]],
    }
    final_makespans = {lane["metrics"]["makespan_s"] for lane in lanes}
    final_paths = {lane["metrics"]["round_trip_path_m"] for lane in lanes}
    interpretation_guard = {
        "full_fill_flat_metrics_observed": {
            "makespan_s": len(final_makespans) == 1,
            "round_trip_path_m": len(final_paths) == 1,
        },
        "reason": (
            "at 267/267 every managed slot is visited once and every cargo is handled once; "
            "with fixed laden factor, final cumulative storage path and makespan are assignment-invariant"
        ),
        "ui_rule": (
            "do not rank algorithms by final fill makespan/path; compare bookmark trajectories and "
            "assignment-sensitive retrieval, load-height, energy-proxy, and fixed-score diagnostics"
        ),
        "collinearity_rule": shared["score_policy"]["known_collinearity"],
    }
    gate_errors = []
    if shared["capacity"] != {
            "cols": 20, "tiers": 20, "total_slots": 400,
            "preoccupied_slots": 133, "managed_capacity": 267,
            "rule": "sum", "rule_expression": "(col+tier)%3==0",
            "start": {"managed_goods": 0, "total_unavailable": 133},
            "full_endpoint": {"managed_goods": 267, "total_unavailable": 400}}:
        gate_errors.append("capacity_contract")
    for lane_id, result in validation.items():
        if (result["lane_errors"] or result["candidate_audit_errors"]
                or result["semantic_replay_errors"]):
            gate_errors.append(lane_id)
    if not online_fairness["all_lane_input_hashes_identical"]:
        gate_errors.append("shared_input_fairness")
    if offline["status"] != "FEASIBLE" or offline["placed"] != 267:
        gate_errors.append("awra_offline_reference")
    for objective, item in lap["objectives"].items():
        if item["status"] != "FEASIBLE" or item["assignment_count"] != 267:
            gate_errors.append(f"lap_{objective}")

    manifest = {
        "schema_version": fill.SCHEMA_VERSION,
        "source": "sim.fill_only + l4_showcase/tools/generate_s3_fill_trace.py",
        "sim_only": True,
        "evidence_boundary": (
            "single-seed capacity/replay gate; not headline KPI, PLC evidence, field throughput, "
            "or proof of continuous operation from a completely full warehouse"
        ),
        "shared_input": shared,
        "online_fairness": online_fairness,
        "interpretation_guard": interpretation_guard,
        "online_lanes": lanes,
        "offline_references": [offline],
        "lap_exact_reference": lap,
        "derived_comparisons": derived_comparisons,
        "audit_files": audit_files,
        "validation": validation,
        "data_gate": {
            "id": "S3_FILL_CANONICAL_SAFE_267",
            "pass": not gate_errors, "errors": gate_errors,
            "stage": "DATA_GENERATION_AND_SOURCE_REPLAY",
            "front_end_evidence_binding": "DISABLED_PENDING_VERIFIED_LOADER",
            "managed_endpoint": "0/267 -> 267/267",
            "total_endpoint": "133/400 -> 400/400",
            "checkpoint_counts": list(fill.CHECKPOINT_COUNTS),
        },
        "source_sha256": {
            "l4_showcase/tools/generate_s3_fill_trace.py": fill.file_sha256(__file__),
            "l4_showcase/tools/validate_s3_fill_trace.py": fill.file_sha256(
                ROOT / "l4_showcase" / "tools" / "validate_s3_fill_trace.py"
            ),
        },
    }
    manifest["manifest_sha256"] = fill.payload_sha256(manifest)
    _write_json(outdir / "s3_fill_data_gate.json", manifest)
    (outdir / "s3_fill_data_gate_summary.md").write_text(
        _summary(manifest), encoding="utf-8"
    )
    return manifest


def generate(outdir: Path = DEFAULT_OUT, seed: int = 2026,
             case: str = "skew", algorithms=("seq", "near", "score")) -> Dict[str, Any]:
    """在版本化暂存目录完成构建后，原子切换 latest pointer。"""
    algorithms = _canonical_release_algorithms(algorithms)
    outdir = outdir.resolve()
    with _exclusive_publish_lock(outdir):
        outdir.mkdir(parents=True, exist_ok=True)
        releases = outdir / "releases"
        releases.mkdir(parents=True, exist_ok=True)
        staging = outdir / f".staging-{os.getpid()}-{uuid.uuid4().hex}"
        staging.mkdir()
        try:
            manifest = _build_release(
                staging, seed=seed, case=case, algorithms=algorithms
            )
            release_id = manifest["manifest_sha256"][:20]
            final = releases / release_id
            if final.exists():
                if _tree_fingerprint(final) != _tree_fingerprint(staging):
                    raise RuntimeError(
                        f"release id collision or non-deterministic output: {release_id}"
                    )
                shutil.rmtree(staging)
            else:
                os.replace(staging, final)
            manifest_path = final / "s3_fill_data_gate.json"
            pointer = {
                "schema_version": POINTER_SCHEMA,
                "release_id": release_id,
                "manifest_resource": (
                    f"releases/{release_id}/s3_fill_data_gate.json"
                ),
                "manifest_file_sha256": fill.file_sha256(manifest_path),
                "manifest_payload_sha256": manifest["manifest_sha256"],
                "publication_model": "versioned_release_plus_atomic_latest_pointer",
                "authoritative_entrypoint": "latest.json",
            }
            pointer["pointer_sha256"] = fill.payload_sha256(pointer)
            alias = {
                "schema_version": ALIAS_SCHEMA,
                "authoritative_entrypoint": "latest.json",
                "non_authoritative": True,
                "release_id": release_id,
                "manifest_resource": pointer["manifest_resource"],
                "latest_pointer_sha256": pointer["pointer_sha256"],
            }
            alias["alias_sha256"] = fill.payload_sha256(alias)
            _quarantine_legacy_flat_files(outdir)
            _atomic_write_json(outdir / "s3_fill_data_gate.json", alias)
            _atomic_write_text(
                outdir / "s3_fill_data_gate_summary.md",
                (final / "s3_fill_data_gate_summary.md").read_text(encoding="utf-8"),
            )
            _atomic_write_json(outdir / "latest.json", pointer)
            return manifest
        finally:
            if staging.exists():
                shutil.rmtree(staging)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--outdir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--case", choices=("uniform", "skew", "heavy"), default="skew")
    parser.add_argument("--algorithms", default="seq,near,score")
    args = parser.parse_args()
    manifest = generate(
        outdir=args.outdir, seed=args.seed, case=args.case,
        algorithms=tuple(item.strip() for item in args.algorithms.split(",") if item.strip()),
    )
    print(
        f"S3 fill-only data gate {'PASS' if manifest['data_gate']['pass'] else 'FAIL'}; "
        f"pointer={args.outdir / 'latest.json'}; "
        f"sha256={manifest['manifest_sha256']}"
    )
    if not manifest["data_gate"]["pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
