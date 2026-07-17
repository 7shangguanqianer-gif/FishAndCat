# -*- coding: utf-8 -*-
"""Contract tests for the 45-file S3 trace bundle."""

import csv
import hashlib
import io
import inspect
import json
import os
import sys
import tempfile
import unittest
import shutil
from copy import deepcopy
from unittest import mock


HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import generate_s3_tier3_trace as gen


EXPECTED_TRANSITIONS = [
    ("QUEUE", "CARRIER_IN"),
    ("CARRIER_IN", "RACK"),
    ("RACK", "CARRIER_OUT"),
    ("CARRIER_OUT", "OUTFEED"),
    ("OUTFEED", "SCANNED"),
    ("SCANNED", "EXIT_MASK"),
    ("EXIT_MASK", "CONSUMED"),
]
EXPECTED_STEPS = [
    "LOAD_IN", "INBOUND_TRAVEL", "STORE_HANDLE", "LINK_TRAVEL",
    "RETRIEVE_HANDLE", "OUTBOUND_TRAVEL", "SCAN_EXIT",
]


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as fp:
        for chunk in iter(lambda: fp.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_trace_js(path):
    with open(path, encoding="utf-8") as fp:
        text = fp.read()
    prefix = "window.__S3_TRACE_REGISTER__("
    if not text.startswith(prefix) or not text.endswith(");\n"):
        raise AssertionError(f"bad trace wrapper: {path}")
    args = text[len(prefix):-3]
    decoder = json.JSONDecoder()
    trace_id, cursor = decoder.raw_decode(args)
    if args[cursor] != ",":
        raise AssertionError(f"bad trace id separator: {path}")
    payload, end = decoder.raw_decode(args, cursor + 1)
    if args[end:].strip():
        raise AssertionError(f"trailing trace bytes: {path}")
    return trace_id, payload


class TestS3TraceBundle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.manifest = gen.generate_trace_bundle(
            cls.temp.name, seed=2026, cycles=100
        )
        cls.trace_dir = os.path.join(cls.temp.name, "s3_traces")

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def traces(self):
        for entry in self.manifest["entries"]:
            path = os.path.join(self.temp.name, entry["file"])
            trace_id, payload = read_trace_js(path)
            yield entry, path, trace_id, payload

    def test_exact_45_combinations_and_manifest_limits(self):
        expected = {
            (tier, profile, mode)
            for tier in gen.TRACE_TIERS
            for profile in gen.TRACE_PROFILES
            for mode in gen.UI_MODES
        }
        actual = {
            (entry["tier"], entry["profile"], entry["strategy_mode"])
            for entry in self.manifest["entries"]
        }
        self.assertEqual(actual, expected)
        self.assertEqual(len(self.manifest["entries"]), 45)
        self.assertEqual(self.manifest["schema_version"], gen.MANIFEST_SCHEMA_VERSION)
        self.assertEqual(self.manifest["entry_count"], 45)
        self.assertEqual(
            self.manifest["matrix_reference"], gen.load_s1_matrix_reference()
        )
        self.assertFalse(
            self.manifest["comparability_policy"]["s1_matrix_same_parameterization"]
        )
        self.assertEqual(
            self.manifest["comparability_policy"]["ui_rule"],
            "do_not_compare_or_merge",
        )
        manifest_js = os.path.join(self.temp.name, "s3_trace_manifest.js")
        manifest_json = os.path.join(self.temp.name, "s3_trace_manifest.json")
        self.assertLessEqual(os.path.getsize(manifest_js), 100 * 1024)
        with open(manifest_json, encoding="utf-8") as fp:
            self.assertEqual(json.load(fp), self.manifest)

    def test_every_trace_hash_schema_size_and_provenance(self):
        for entry, path, trace_id, trace in self.traces():
            with self.subTest(trace_id=entry["trace_id"]):
                self.assertEqual(trace_id, entry["trace_id"])
                self.assertEqual(trace["schema_version"], gen.TRACE_SCHEMA_VERSION)
                self.assertTrue(trace["sim_only"])
                self.assertEqual(trace["source"], "sim.realism.run_tier3:event_sink")
                self.assertEqual(trace["payload_sha256"], gen.canonical_payload_hash(trace))
                self.assertEqual(
                    trace["semantic_runtime_sha256_v1"],
                    gen.semantic_runtime_payload_hash(trace),
                )
                self.assertEqual(entry["payload_sha256"], trace["payload_sha256"])
                self.assertEqual(
                    entry["semantic_runtime_sha256_v1"],
                    trace["semantic_runtime_sha256_v1"],
                )
                self.assertEqual(entry["file_sha256"], sha256(path))
                self.assertEqual(entry["bytes"], os.path.getsize(path))
                self.assertLessEqual(entry["bytes"], 800 * 1024)
                self.assertEqual(set(trace["stream_hashes"]), {
                    "workload_hash", "arrivals_hash", "noise_hash", "fault_stream_hash"
                })
                self.assertIn("sim/realism.py", trace["provenance"]["source_sha256"])
                self.assertIn("sim/strategy_lib.py", trace["provenance"]["source_sha256"])
                self.assertEqual(trace["stats"]["scope"], "single_seed_representative_replay")
                reference = trace["stats"]["multi_seed_source"]
                self.assertTrue(reference["path"].endswith("cargo_dynamic_matrix_agg.csv"))
                self.assertEqual(reference["stage"], "s1")
                self.assertEqual(reference["seeds"], list(range(2026, 2036)))
                self.assertEqual(len(reference["modes"]), 8)
                self.assertEqual(
                    reference["manifest_sha256"],
                    sha256(os.path.join(
                        ROOT, "sim", "out", "cargo_dynamic_matrix", "s1",
                        "cargo_dynamic_matrix_manifest.json",
                    )),
                )
                self.assertEqual(trace["comparability"]["s1_matrix_same_parameterization"],
                                 False)
                self.assertTrue(trace["comparability"]["mismatch_fields"])
                self.assertEqual(trace["comparability"]["ui_rule"],
                                 "do_not_compare_or_merge")
                if entry["tier"] == 3:
                    self.assertEqual(
                        set(trace["comparability"]["mismatch_fields"]),
                        {"score_policy", "freq_noise_sigma"},
                    )

    def test_inventory_phase_and_full_gid_ownership_contract(self):
        for entry, _, _, trace in self.traces():
            with self.subTest(trace_id=entry["trace_id"]):
                self.assertEqual(len(trace["initial_inventory"]), 120)
                self.assertEqual(len(trace["final_inventory"]), 120)
                self.assertEqual(len(trace["inventory_snapshots"]), 101)
                self.assertEqual(trace["initial_inventory"], trace["inventory_snapshots"][0])
                self.assertEqual(trace["final_inventory"], trace["inventory_snapshots"][-1])
                self.assertEqual(len(trace["events"]), 100)
                previous_after = trace["initial_inventory"]
                for event in trace["events"]:
                    inventory_before = trace["inventory_snapshots"][event["inventory_before_ref"]]
                    inventory_after = trace["inventory_snapshots"][event["inventory_after_ref"]]
                    self.assertEqual(event["status"], "COMPLETED")
                    self.assertEqual(inventory_before, previous_after)
                    self.assertEqual(len(inventory_before), 120)
                    self.assertEqual(len(inventory_after), 120)
                    self.assertEqual(
                        len({item["gid"] for item in inventory_after}), 120
                    )
                    transitions = [(item["from"], item["to"])
                                   for item in event["ownership_events"]]
                    self.assertEqual(transitions, EXPECTED_TRANSITIONS)
                    self.assertEqual([step["name"] for step in event["process_steps"]],
                                     EXPECTED_STEPS)
                    phases = event["phases"]
                    for phase in phases:
                        self.assertTrue({
                            "name", "t0", "t1", "from", "to", "u0", "u1",
                            "cargo_owner", "cargo_gid",
                        }.issubset(phase))
                        self.assertLessEqual(phase["t0"], phase["t1"])
                    for left, right in zip(phases, phases[1:]):
                        self.assertEqual(left["t1"], right["t0"])
                    previous_after = inventory_after
                self.assertEqual(previous_after, trace["final_inventory"])

    def test_tiers_share_workload_but_keep_physical_scope_explicit(self):
        by_key = {}
        for entry, _, _, trace in self.traces():
            by_key[(entry["tier"], entry["profile"], entry["strategy_mode"])] = trace
        for profile in gen.TRACE_PROFILES:
            for mode in gen.UI_MODES:
                t1 = by_key[(1, profile, mode)]
                t2 = by_key[(2, profile, mode)]
                t3 = by_key[(3, profile, mode)]
                self.assertEqual(
                    {t1["stream_hashes"]["workload_hash"],
                     t2["stream_hashes"]["workload_hash"],
                     t3["stream_hashes"]["workload_hash"]},
                    {t1["stream_hashes"]["workload_hash"]},
                )
                self.assertEqual(t1["meta"]["motion"], "constant_speed")
                self.assertEqual(t2["meta"]["motion"], "trapezoid_accel")
                self.assertEqual(t3["meta"]["motion"], "trapezoid_accel")
                self.assertEqual(t1["stats"]["faults"], 0)
                self.assertEqual(t2["stats"]["faults"], 0)
                self.assertEqual(t3["meta"]["tier3_params"]["freq_noise_sigma"], 0.30)
                self.assertEqual(t3["meta"]["tier3_params"]["fault_mtbf_s"], 3000.0)

    def test_s1_matrix_reference_fails_closed_on_identity_tampering(self):
        reference = gen.load_s1_matrix_reference()
        self.assertEqual(reference["stage"], "s1")
        self.assertEqual(reference["run_count"], 1440)
        manifest_path = os.path.join(
            ROOT, "sim", "out", "cargo_dynamic_matrix", "s1",
            "cargo_dynamic_matrix_manifest.json",
        )
        with open(manifest_path, encoding="utf-8") as fp:
            manifest = json.load(fp)
        output_hashes = manifest["outputs_sha256"]
        mutations = []
        changed = deepcopy(manifest); changed["stage"] = "s2"; mutations.append(changed)
        changed = deepcopy(manifest); changed["seeds"] = [2026]; mutations.append(changed)
        changed = deepcopy(manifest); changed["modes"] = ["AUTO"]; mutations.append(changed)
        changed = deepcopy(manifest); changed["run_count"] = 1; mutations.append(changed)
        changed = deepcopy(manifest)
        changed["runner_provenance"]["source_sha256"]["sim/cargo_dynamic_matrix.py"] = "0" * 64
        mutations.append(changed)
        changed = deepcopy(manifest)
        first_function = next(iter(changed["runner_provenance"]["function_sha256"]))
        changed["runner_provenance"]["function_sha256"][first_function] = "f" * 64
        mutations.append(changed)
        for changed in mutations:
            with self.subTest(field=next(
                key for key in changed if changed.get(key) != manifest.get(key)
            )):
                with self.assertRaises(ValueError):
                    gen.validate_s1_matrix_manifest(changed, output_hashes)
        with self.assertRaises(ValueError):
            bad_hashes = dict(output_hashes, agg="f" * 64)
            gen.validate_s1_matrix_manifest(manifest, bad_hashes)

    def test_all_eleven_params_are_semantically_locked(self):
        base = os.path.join(ROOT, "sim", "out", "cargo_dynamic_matrix", "s1")
        paths = {
            "manifest": os.path.join(base, "cargo_dynamic_matrix_manifest.json"),
            "agg": os.path.join(base, "cargo_dynamic_matrix_agg.csv"),
            "detail": os.path.join(base, "cargo_dynamic_matrix_detail.csv"),
            "params": os.path.join(base, "cargo_dynamic_matrix_params.csv"),
        }
        contents = {}
        for name, path in paths.items():
            with open(path, "rb") as fp:
                contents[name] = fp.read()
        manifest = json.loads(contents["manifest"].decode("utf-8"))
        params_text = contents["params"].decode("utf-8-sig")
        rows = list(csv.DictReader(io.StringIO(params_text)))
        self.assertEqual(len(rows), 11)
        for target in [row["param"] for row in rows]:
            changed_rows = deepcopy(rows)
            for row in changed_rows:
                if row["param"] == target:
                    row["value"] = "__tampered__"
            output = io.StringIO()
            writer = csv.DictWriter(
                output, fieldnames=["param", "value", "note"], lineterminator="\n"
            )
            writer.writeheader()
            writer.writerows(changed_rows)
            changed_contents = dict(contents, params=output.getvalue().encode("utf-8"))
            changed_hashes = {
                name: hashlib.sha256(changed_contents[name]).hexdigest()
                for name in ("agg", "detail", "params")
            }
            changed_manifest = deepcopy(manifest)
            changed_manifest["outputs_sha256"] = changed_hashes
            gen.validate_s1_matrix_manifest(changed_manifest, changed_hashes)
            with self.subTest(param=target), self.assertRaises(ValueError):
                gen.validate_s1_output_content(changed_contents, changed_manifest)

    def test_stable_snapshot_reader_retries_and_fails_closed(self):
        paths = {"manifest": object(), "agg": object()}
        values = iter([b"A", b"A", b"B", b"B", b"B", b"B", b"B", b"B"])
        self.assertEqual(
            gen._read_stable_file_set(paths, attempts=2,
                                      reader=lambda _path: next(values)),
            {"manifest": b"B", "agg": b"B"},
        )
        counter = {"value": 0}
        def unstable(_path):
            counter["value"] += 1
            return str(counter["value"]).encode("ascii")
        with self.assertRaises(RuntimeError):
            gen._read_stable_file_set(paths, attempts=2, reader=unstable)

    @staticmethod
    def _tiny_trace(tier, profile, strategy_mode, seed, matrix_reference, **_kwargs):
        trace = {
            "schema_version": gen.TRACE_SCHEMA_VERSION,
            "sim_only": True,
            "meta": {
                "trace_id": f"t{tier}_{profile}_{strategy_mode.lower()}",
                "picked_strategy": strategy_mode,
            },
            "stats": {"faults": 0},
            "matrix_reference": matrix_reference,
        }
        trace["semantic_runtime_sha256_v1"] = gen.semantic_runtime_payload_hash(trace)
        trace["payload_sha256"] = gen.canonical_payload_hash(trace)
        return trace

    def test_bundle_rejects_mid_generation_matrix_replacement(self):
        reference_a = gen.load_s1_matrix_reference()
        reference_b = deepcopy(reference_a)
        reference_b["manifest_sha256"] = "0" * 64
        with tempfile.TemporaryDirectory() as temp:
            with mock.patch.object(
                gen, "load_s1_matrix_reference", side_effect=[reference_a, reference_b]
            ), mock.patch.object(gen, "build_trace", side_effect=self._tiny_trace):
                with self.assertRaises(RuntimeError):
                    gen.generate_trace_bundle(temp, seed=2026, cycles=100)
            self.assertFalse(os.path.exists(os.path.join(temp, "s3_trace_manifest.js")))

    def test_same_process_second_bundle_refreshes_matrix_reference(self):
        reference_a = gen.load_s1_matrix_reference()
        reference_b = deepcopy(reference_a)
        reference_b["manifest_sha256"] = "1" * 64
        with tempfile.TemporaryDirectory() as temp_a, tempfile.TemporaryDirectory() as temp_b:
            with mock.patch.object(
                gen, "load_s1_matrix_reference",
                side_effect=[
                    reference_a, reference_a, reference_a,
                    reference_b, reference_b, reference_b,
                ],
            ), mock.patch.object(gen, "build_trace", side_effect=self._tiny_trace):
                manifest_a = gen.generate_trace_bundle(temp_a, seed=2026, cycles=100)
                manifest_b = gen.generate_trace_bundle(temp_b, seed=2026, cycles=100)
        self.assertEqual(manifest_a["matrix_reference"], reference_a)
        self.assertEqual(manifest_b["matrix_reference"], reference_b)

    def test_real_temp_file_replacement_is_rejected(self):
        base = os.path.join(ROOT, "sim", "out", "cargo_dynamic_matrix", "s1")
        names = {
            "manifest": "cargo_dynamic_matrix_manifest.json",
            "agg": "cargo_dynamic_matrix_agg.csv",
            "detail": "cargo_dynamic_matrix_detail.csv",
            "params": "cargo_dynamic_matrix_params.csv",
        }
        for target_name in names:
            with self.subTest(file=target_name), tempfile.TemporaryDirectory() as temp:
                paths = {}
                for key, filename in names.items():
                    source = os.path.join(base, filename)
                    target = os.path.join(temp, filename)
                    shutil.copy2(source, target)
                    paths[key] = target
                locked = gen.load_s1_matrix_reference(paths)
                replacement = paths[target_name] + ".replacement"
                with open(replacement, "wb") as fp:
                    fp.write(b"replaced evidence bytes\n")
                os.replace(replacement, paths[target_name])
                with self.assertRaises((ValueError, RuntimeError)):
                    gen.assert_s1_matrix_reference_unchanged(locked, paths)

    def test_bundle_reference_guard_rejects_changed_snapshot(self):
        reference = gen.load_s1_matrix_reference()
        changed = deepcopy(reference)
        changed["manifest_sha256"] = "0" * 64
        with self.assertRaises(RuntimeError):
            gen.assert_s1_matrix_reference_unchanged(changed)
        self.assertEqual(
            gen.assert_s1_matrix_reference_unchanged(reference), reference
        )

    def test_exporter_contains_no_second_business_event_loop(self):
        source = inspect.getsource(gen)
        self.assertIn("realism.run_tier3(", source)
        self.assertNotIn("lru_cache", source)
        for forbidden in (
            "pos_of.pop", "wh.put(", "wh.remove(",
            "def phase_specs", "def add_absolute_phases",
        ):
            self.assertNotIn(forbidden, source)

    def test_semantic_runtime_hash_detects_deep_change_and_numeric_contract(self):
        trace = gen.build_trace(
            tier=1, profile="uniform", strategy_mode="seq", cycles=100, seed=2026
        )
        changed = deepcopy(trace)
        changed["events"][0]["phases"][0]["t1"] += 0.125
        self.assertNotEqual(
            gen.semantic_runtime_payload_hash(changed),
            trace["semantic_runtime_sha256_v1"],
        )
        self.assertEqual(gen._semantic_runtime_bytes(1),
                         gen._semantic_runtime_bytes(1.0))
        self.assertNotEqual(gen._semantic_runtime_bytes(0.0),
                            gen._semantic_runtime_bytes(-0.0))
        for invalid in (float("nan"), float("inf"), 1 << 53):
            with self.subTest(value=invalid), self.assertRaises(ValueError):
                gen._semantic_runtime_bytes(invalid)


if __name__ == "__main__":
    unittest.main()
