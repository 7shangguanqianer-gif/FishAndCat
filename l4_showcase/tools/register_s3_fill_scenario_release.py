"""为情景对照数据门(治理 C2)登记独立 detached registry。

skew 生产 registry(evidence/s3_fill_release_registry.json)零接触;本脚本只为
独立情景目录(如 out/s3_fill_data_gate_uniform)生成/更新其专属 registry 文件,
entry 字段全部从盘上 release 与当前源码实算,与 validate_s3_fill_trace.py 的
校验点逐项对齐(source_sha256 / pointer_sha256 / loader hash / 10 项 loader 测试凭据)。

用法(项目根):
    PYTHONIOENCODING=utf-8 python l4_showcase/tools/register_s3_fill_scenario_release.py \
        --dir l4_showcase/out/s3_fill_data_gate_uniform \
        --registry l4_showcase/evidence/s3_fill_release_registry_uniform.json \
        --scenario uniform
登记后必须复跑:
    python l4_showcase/tools/validate_s3_fill_trace.py --dir <dir> --registry <registry>
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "sim"))

import fill_only as fill  # noqa: E402

REGISTRY_SCHEMA = "s3-fill-release-registry-v1"
APPROVAL_SCHEMA = "s3-fill-frontend-binding-approval-v1"
SOURCE_FILES = (
    "sim/fill_only.py",
    "sim/warehouse_sim.py",
    "sim/lap_optimal.py",
    "l4_showcase/tools/generate_s3_fill_trace.py",
    "l4_showcase/tools/validate_s3_fill_trace.py",
    "l4_showcase/evidence/s3_fill_requirements.lock",
)
LOADER_FILES = (
    "l4_showcase/tools/build_s3_fill_frontend_bundle.py",
    "l4_showcase/tools/test_s3_fill_frontend_bundle.py",
)


def run_loader_tests() -> dict:
    command = [sys.executable, "-B", str(ROOT / "l4_showcase" / "tools" / "test_s3_fill_frontend_bundle.py")]
    completed = subprocess.run(command, capture_output=True, text=True, cwd=ROOT)
    tail = (completed.stdout + completed.stderr).strip().splitlines()
    summary = next((line for line in reversed(tail) if "PASS" in line or "FAIL" in line), "")
    if completed.returncode != 0 or "PASS 10/10" not in summary:
        raise RuntimeError(f"loader tests did not pass 10/10: rc={completed.returncode} {summary!r}")
    return {"passed": 10, "failed": 0,
            "command": "python -B l4_showcase/tools/test_s3_fill_frontend_bundle.py"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dir", required=True, type=Path)
    parser.add_argument("--registry", required=True, type=Path)
    parser.add_argument("--scenario", required=True, choices=("uniform", "heavy"))
    args = parser.parse_args()

    gate_dir = args.dir.resolve()
    registry_path = args.registry.resolve()
    if registry_path == (ROOT / "l4_showcase" / "evidence" / "s3_fill_release_registry.json").resolve():
        raise SystemExit("refusing to touch the production skew registry")

    pointer = json.loads((gate_dir / "latest.json").read_text(encoding="utf-8"))
    manifest_path = gate_dir / pointer["manifest_resource"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("manifest_sha256") != pointer.get("manifest_payload_sha256"):
        raise SystemExit("pointer/manifest payload hash mismatch")
    if not manifest.get("data_gate", {}).get("pass"):
        raise SystemExit("data gate did not pass; refusing to register")

    test_result = run_loader_tests()
    now_utc = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    entry = {
        "release_id": pointer["release_id"],
        "manifest_payload_sha256": manifest["manifest_sha256"],
        "manifest_file_sha256": fill.file_sha256(manifest_path),
        "pointer_sha256": pointer["pointer_sha256"],
        "trust_level": "local_detached_registry_not_signature",
        "status": "approved_for_frontend_binding",
        "evidence_boundary": (
            f"single-seed SIM {args.scenario} traffic contrast scenario (governance C2, "
            "approved under 0716 user blanket approval of packages A/B/C1/C2/D); "
            "not headline KPI, PLC evidence, field throughput, or continuous operation proof"
        ),
        "frontend_binding_approval": {
            "schema_version": APPROVAL_SCHEMA,
            "bundle_schema_version": "s3-fill-frontend-bundle-v1",
            "release_id": pointer["release_id"],
            "approved_at_utc": now_utc,
            "loader_source_sha256": {name: fill.file_sha256(ROOT / name) for name in LOADER_FILES},
            "test_result": test_result,
            "scope": (
                f"file:// S3 fill-only candidate loader for the {args.scenario} contrast release; "
                "same loader sources as the production skew binding"
            ),
            "evidence_boundary": (
                f"SIM single-seed {args.scenario} fill trace and frontend replay only; "
                "contrast scenario beside the production skew release"
            ),
        },
        "source_sha256": {name: fill.file_sha256(ROOT / name) for name in SOURCE_FILES},
    }
    registry = {
        "schema_version": REGISTRY_SCHEMA,
        "active_release_id": pointer["release_id"],
        "trust_boundary": (
            "Local detached registry for the contrast-scenario release, checked independently "
            "from generated artifacts. It is not a cryptographic signature and does not defend "
            "against an attacker who can rewrite both source and registry."
        ),
        "entries": [entry],
    }
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"registered {args.scenario} release {pointer['release_id']} -> {registry_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
