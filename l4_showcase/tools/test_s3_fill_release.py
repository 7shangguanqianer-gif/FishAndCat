# -*- coding: utf-8 -*-
"""S3 fill-only atomic publication and read-only validation regression tests."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


sys.dont_write_bytecode = True

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parents[1]
SIM = ROOT / "sim"
for path in (str(TOOLS), str(SIM)):
    if path not in sys.path:
        sys.path.insert(0, path)

import fill_only as fill
import generate_s3_fill_trace as generator
import validate_s3_fill_trace as validator


class TestS3FillRelease(unittest.TestCase):
    @staticmethod
    def _fingerprint(root: Path):
        if not root.exists():
            return {}
        return {
            str(path.relative_to(root)).replace("\\", "/"): fill.file_sha256(path)
            for path in sorted(item for item in root.rglob("*") if item.is_file())
        }

    @classmethod
    def _fingerprints(cls, outdir: Path):
        return {
            "outdir": cls._fingerprint(outdir),
            "sim": cls._fingerprint(SIM),
            "tools": cls._fingerprint(TOOLS),
        }

    @staticmethod
    def _pointer(outdir: Path):
        return json.loads((outdir / "latest.json").read_text(encoding="utf-8"))

    @staticmethod
    def _registry_entry(outdir: Path, pointer):
        manifest_path = outdir / pointer["manifest_resource"]
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        return {
            "release_id": pointer["release_id"],
            "manifest_payload_sha256": manifest["manifest_sha256"],
            "manifest_file_sha256": fill.file_sha256(manifest_path),
            "pointer_sha256": pointer["pointer_sha256"],
            "trust_level": "local_detached_registry_not_signature",
            "status": "candidate_data_release",
            "source_sha256": validator._release_source_hashes(),
        }

    @staticmethod
    def _write_registry(path: Path, entries, active_release_id: str):
        path.write_text(
            json.dumps(
                {
                    "schema_version": validator.REGISTRY_SCHEMA,
                    "active_release_id": active_release_id,
                    "entries": entries,
                },
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
            ) + "\n",
            encoding="utf-8",
        )

    def test_fresh_generate_is_versioned_deterministic_and_validation_is_read_only(self):
        with tempfile.TemporaryDirectory(prefix="s3-fill-release-") as temp:
            outdir = Path(temp) / "gate"
            registry = Path(temp) / "registry.json"
            first = generator.generate(outdir=outdir)
            pointer = self._pointer(outdir)
            self.assertEqual(pointer["schema_version"], generator.POINTER_SCHEMA)
            self.assertEqual(pointer["authoritative_entrypoint"], "latest.json")
            self.assertEqual(pointer["release_id"], first["manifest_sha256"][:20])
            self.assertTrue((outdir / pointer["manifest_resource"]).is_file())
            self.assertEqual(len(list((outdir / "releases").iterdir())), 1)
            self._write_registry(
                registry, [self._registry_entry(outdir, pointer)], pointer["release_id"]
            )

            before = self._fingerprints(outdir)
            report = validator.validate(outdir, registry)
            after = self._fingerprints(outdir)
            self.assertTrue(report["pass"], report["errors"])
            self.assertEqual(before, after)
            self.assertFalse((outdir / "s3_fill_validation_report.json").exists())

            second = generator.generate(outdir=outdir)
            self.assertEqual(first["manifest_sha256"], second["manifest_sha256"])
            self.assertEqual(len(list((outdir / "releases").iterdir())), 1)

    def test_release_algorithms_must_be_exact_and_subset_cannot_promote_latest(self):
        with tempfile.TemporaryDirectory(prefix="s3-fill-release-") as temp:
            outdir = Path(temp) / "gate"
            with self.assertRaisesRegex(ValueError, "must exactly equal"):
                generator.generate(outdir=outdir, algorithms=("seq", "near"))
            self.assertFalse((outdir / "latest.json").exists())

            generator.generate(outdir=outdir)
            before = self._fingerprint(outdir)
            latest_before = (outdir / "latest.json").read_bytes()
            with self.assertRaisesRegex(ValueError, "must exactly equal"):
                generator.generate(outdir=outdir, algorithms=("seq", "near"))
            with self.assertRaisesRegex(ValueError, "must exactly equal"):
                generator.generate(
                    outdir=outdir, algorithms=("seq", "near", "score", "score")
                )
            self.assertEqual(latest_before, (outdir / "latest.json").read_bytes())
            self.assertEqual(before, self._fingerprint(outdir))

    def test_latest_is_unique_authority_and_is_promoted_last(self):
        with tempfile.TemporaryDirectory(prefix="s3-fill-release-") as temp:
            outdir = Path(temp) / "gate"
            calls = []
            original_json = generator._atomic_write_json
            original_text = generator._atomic_write_text

            def record_json(path, value):
                calls.append(path.name)
                original_json(path, value)

            def record_text(path, value):
                calls.append(path.name)
                original_text(path, value)

            with mock.patch.object(generator, "_atomic_write_json", side_effect=record_json), \
                 mock.patch.object(generator, "_atomic_write_text", side_effect=record_text):
                generator.generate(outdir=outdir)

            self.assertEqual(calls[-1], "latest.json")
            self.assertIn("s3_fill_data_gate.json", calls[:-1])
            self.assertIn("s3_fill_data_gate_summary.md", calls[:-1])
            alias = json.loads((outdir / "s3_fill_data_gate.json").read_text(encoding="utf-8"))
            self.assertEqual(alias["schema_version"], generator.ALIAS_SCHEMA)
            self.assertTrue(alias["non_authoritative"])
            self.assertEqual(alias["authoritative_entrypoint"], "latest.json")

            (outdir / "latest.json").unlink()
            with self.assertRaisesRegex(FileNotFoundError, "authoritative latest"):
                validator.validate(outdir, Path(temp) / "unused-registry.json")

    def test_validator_import_and_validation_do_not_change_outdir_sim_or_tools(self):
        with tempfile.TemporaryDirectory(prefix="s3-fill-import-") as temp:
            sandbox = Path(temp) / "fixture"
            tools_copy = sandbox / "l4_showcase" / "tools"
            sim_copy = sandbox / "sim"
            outdir = sandbox / "l4_showcase" / "out" / "s3_fill_data_gate"
            tools_copy.mkdir(parents=True)
            sim_copy.mkdir(parents=True)
            outdir.mkdir(parents=True)
            shutil.copy2(TOOLS / "validate_s3_fill_trace.py", tools_copy)
            for name in ("fill_only.py", "warehouse_sim.py"):
                shutil.copy2(SIM / name, sim_copy)

            before = {
                "outdir": self._fingerprint(outdir),
                "sim": self._fingerprint(sim_copy),
                "tools": self._fingerprint(tools_copy),
            }
            validator_script = tools_copy / "validate_s3_fill_trace.py"
            completed = subprocess.run(
                [sys.executable, str(validator_script), "--dir", str(outdir)], cwd=sandbox,
                capture_output=True, text=True, check=False,
            )
            after = {
                "outdir": self._fingerprint(outdir),
                "sim": self._fingerprint(sim_copy),
                "tools": self._fingerprint(tools_copy),
            }
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("authoritative latest pointer is missing", completed.stderr)
            self.assertEqual(before, after)

    def test_detached_registry_binds_pointer_release_and_active_release(self):
        with tempfile.TemporaryDirectory(prefix="s3-fill-release-") as temp:
            outdir = Path(temp) / "gate"
            registry = Path(temp) / "registry.json"
            generator.generate(outdir=outdir, case="skew")
            pointer_a = self._pointer(outdir)
            entry_a = self._registry_entry(outdir, pointer_a)
            generator.generate(outdir=outdir, case="uniform")
            pointer_b = self._pointer(outdir)
            entry_b = self._registry_entry(outdir, pointer_b)

            self._write_registry(registry, [entry_a, entry_b], pointer_b["release_id"])
            self.assertTrue(validator.validate(outdir, registry)["pass"])

            bad_pointer = json.loads(json.dumps(entry_b))
            bad_pointer["pointer_sha256"] = "0" * 64
            self._write_registry(registry, [bad_pointer], pointer_b["release_id"])
            report = validator.validate(outdir, registry)
            self.assertFalse(report["pass"])
            self.assertIn("registry_pointer_sha256", report["errors"])

            bad_release = json.loads(json.dumps(entry_b))
            bad_release["release_id"] = "not-the-pointer-release"
            self._write_registry(registry, [bad_release], pointer_b["release_id"])
            report = validator.validate(outdir, registry)
            self.assertFalse(report["pass"])
            self.assertIn("registry_release_id", report["errors"])

            self._write_registry(registry, [entry_a, entry_b], pointer_b["release_id"])
            generator._atomic_write_json(outdir / "latest.json", pointer_a)
            report = validator.validate(outdir, registry)
            self.assertFalse(report["pass"])
            self.assertIn("registry_active_release_id", report["errors"])

    def test_registry_lifecycle_separates_data_integrity_from_frontend_authority(self):
        with tempfile.TemporaryDirectory(prefix="s3-fill-lifecycle-") as temp:
            outdir = Path(temp) / "gate"
            registry = Path(temp) / "registry.json"
            generator.generate(outdir=outdir, case="skew")
            pointer = self._pointer(outdir)
            candidate = self._registry_entry(outdir, pointer)

            self._write_registry(registry, [candidate], pointer["release_id"])
            report = validator.validate(outdir, registry)
            self.assertTrue(report["data_integrity_pass"], report["errors"])
            self.assertFalse(report["front_end_bindable"])
            self.assertEqual(
                report["frontend_binding_status"],
                "registry_not_approved_for_frontend",
            )

            approved_without_evidence = json.loads(json.dumps(candidate))
            approved_without_evidence["status"] = "approved_for_frontend_binding"
            self._write_registry(
                registry, [approved_without_evidence], pointer["release_id"]
            )
            report = validator.validate(outdir, registry)
            self.assertTrue(report["data_integrity_pass"], report["errors"])
            self.assertFalse(report["front_end_bindable"])
            self.assertEqual(report["frontend_binding_status"], "frontend_approval_schema")

            approved = json.loads(json.dumps(approved_without_evidence))
            approved["frontend_binding_approval"] = {
                "schema_version": validator.FRONTEND_APPROVAL_SCHEMA,
                "bundle_schema_version": "s3-fill-frontend-bundle-v1",
                "release_id": pointer["release_id"],
                "loader_source_sha256": {
                    "l4_showcase/tools/build_s3_fill_frontend_bundle.py": fill.file_sha256(
                        TOOLS / "build_s3_fill_frontend_bundle.py"
                    ),
                    "l4_showcase/tools/test_s3_fill_frontend_bundle.py": fill.file_sha256(
                        TOOLS / "test_s3_fill_frontend_bundle.py"
                    ),
                },
                "test_result": {"passed": 10, "failed": 0},
            }
            self._write_registry(registry, [approved], pointer["release_id"])
            report = validator.validate(outdir, registry)
            self.assertTrue(report["data_integrity_pass"], report["errors"])
            self.assertTrue(report["front_end_bindable"])
            self.assertEqual(report["frontend_binding_status"], "ok")

            superseded = json.loads(json.dumps(candidate))
            superseded["status"] = "superseded_after_independent_no_go_review"
            self._write_registry(registry, [superseded], pointer["release_id"])
            report = validator.validate(outdir, registry)
            self.assertFalse(report["data_integrity_pass"])
            self.assertFalse(report["front_end_bindable"])
            self.assertIn("registry_lifecycle_status", report["errors"])

    def test_validator_rejects_missing_duplicate_extra_lanes_and_non_finite_json(self):
        with tempfile.TemporaryDirectory(prefix="s3-fill-negative-") as temp:
            outdir = Path(temp) / "gate"
            registry = Path(temp) / "registry.json"
            generator.generate(outdir=outdir, case="skew")
            pointer_path = outdir / "latest.json"
            original_pointer = self._pointer(outdir)
            manifest_path = outdir / original_pointer["manifest_resource"]
            original_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

            def publish_mutated(manifest):
                manifest = json.loads(json.dumps(manifest))
                manifest["manifest_sha256"] = fill.payload_sha256({
                    key: value for key, value in manifest.items()
                    if key != "manifest_sha256"
                })
                manifest_path.write_text(
                    json.dumps(
                        manifest, ensure_ascii=False, sort_keys=True,
                        indent=2, allow_nan=False,
                    ) + "\n",
                    encoding="utf-8",
                )
                pointer = json.loads(json.dumps(original_pointer))
                pointer["release_id"] = manifest["manifest_sha256"][:20]
                pointer["manifest_payload_sha256"] = manifest["manifest_sha256"]
                pointer["manifest_file_sha256"] = fill.file_sha256(manifest_path)
                pointer["pointer_sha256"] = fill.payload_sha256({
                    key: value for key, value in pointer.items()
                    if key != "pointer_sha256"
                })
                pointer_path.write_text(
                    json.dumps(
                        pointer, ensure_ascii=False, sort_keys=True,
                        indent=2, allow_nan=False,
                    ) + "\n",
                    encoding="utf-8",
                )
                self._write_registry(
                    registry, [self._registry_entry(outdir, pointer)],
                    pointer["release_id"],
                )
                return validator.validate(outdir, registry)

            lanes = original_manifest["online_lanes"]
            variants = {
                "missing": lanes[:2],
                "duplicate": [lanes[0], lanes[0], lanes[2]],
                "extra": lanes + [lanes[0]],
            }
            for label, changed_lanes in variants.items():
                with self.subTest(label=label):
                    changed = json.loads(json.dumps(original_manifest))
                    changed["online_lanes"] = changed_lanes
                    report = publish_mutated(changed)
                    self.assertFalse(report["pass"])
                    self.assertFalse(report["checks"]["online_lane_set"])

            non_finite = json.loads(json.dumps(original_manifest))
            non_finite["shared_input"]["profile"]["seed"] = float("nan")
            manifest_path.write_text(
                json.dumps(
                    non_finite, ensure_ascii=False, sort_keys=True,
                    indent=2, allow_nan=True,
                ) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "non-finite JSON constant"):
                validator.validate(outdir, registry)

    def test_stale_lock_requires_manual_confirmation_and_is_not_removed(self):
        with tempfile.TemporaryDirectory(prefix="s3-fill-lock-") as temp:
            outdir = Path(temp) / "gate"
            outdir.parent.mkdir(parents=True, exist_ok=True)
            lock = outdir.parent / f".{outdir.name}.publish.lock"
            lock.write_text("99999999", encoding="ascii")
            try:
                with self.assertRaisesRegex(RuntimeError, "refusing automatic stale-lock removal"):
                    generator.generate(outdir=outdir)
                self.assertTrue(lock.is_file())
                self.assertEqual(lock.read_text(encoding="ascii"), "99999999")
            finally:
                lock.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
