# -*- coding: utf-8 -*-
"""Regression checks for the deterministic S3 file:// frontend bundle."""
from __future__ import annotations

import hashlib
import json
import math
import sys
import unittest
from pathlib import Path
from typing import Any, Dict


sys.dont_write_bytecode = True

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parents[1]
SIM = ROOT / "sim"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
if str(SIM) not in sys.path:
    sys.path.insert(0, str(SIM))

import build_s3_fill_frontend_bundle as bundle
import fill_only as fill


PAYLOAD_START = "/*__S3_FILL_PAYLOAD_BEGIN__*/"
PAYLOAD_END = "/*__S3_FILL_PAYLOAD_END__*/"
EXPECTED_ALGORITHMS = tuple(fill.ONLINE_ALGORITHMS)
EXPECTED_CHECKPOINT_COUNTS = tuple(fill.CHECKPOINT_COUNTS)


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tree_fingerprint(directory: Path) -> Dict[str, str]:
    return {
        path.relative_to(directory).as_posix(): _file_sha256(path)
        for path in sorted(item for item in directory.rglob("*") if item.is_file())
    }


def _input_fingerprint() -> Dict[str, Any]:
    directory = bundle.DEFAULT_DIR.resolve()
    pointer_path = directory / "latest.json"
    pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
    release_dir = (directory / pointer["manifest_resource"]).resolve().parent
    return {
        "latest_json": _file_sha256(pointer_path),
        "release_tree": _tree_fingerprint(release_dir),
        "registry": _file_sha256(bundle.DEFAULT_REGISTRY),
    }


def _parse_payload_from_js(path: Path) -> Dict[str, Any]:
    return _parse_payload_from_source(path.read_text(encoding="utf-8"))


def _parse_payload_from_source(source: str) -> Dict[str, Any]:
    start = source.find(PAYLOAD_START)
    end = source.find(PAYLOAD_END)
    if start < 0 or end < 0 or end <= start:
        raise AssertionError("generated JS payload sentinels are missing or malformed")
    text = source[start + len(PAYLOAD_START):end]
    value = json.loads(text)
    if not isinstance(value, dict):
        raise AssertionError("generated JS payload must be a JSON object")
    return value


def _assert_finite(testcase: unittest.TestCase, value: Any, path: str = "payload") -> None:
    if isinstance(value, float):
        testcase.assertTrue(math.isfinite(value), f"non-finite number at {path}")
    elif isinstance(value, dict):
        for key, item in value.items():
            _assert_finite(testcase, item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _assert_finite(testcase, item, f"{path}[{index}]")


def _manifest_from_pointer() -> tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    pointer = json.loads((bundle.DEFAULT_DIR / "latest.json").read_text(encoding="utf-8"))
    manifest_path = bundle.DEFAULT_DIR / pointer["manifest_resource"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    registry = json.loads(bundle.DEFAULT_REGISTRY.read_text(encoding="utf-8"))
    return pointer, manifest, registry


def _recovered_shared(payload: Dict[str, Any]) -> Dict[str, Any]:
    shared = dict(payload["shared_input_provenance"])
    shared["capacity"] = payload["capacity"]
    shared["cargo_catalog"] = payload["cargo_catalog"]
    shared["score_policy"] = payload["score_policy"]
    return shared


class S3FillFrontendBundleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.inputs_before = _input_fingerprint()
        cls.build_payload, cls.validation_report = bundle.build_payload()
        cls.first_bytes = bundle.render_bundle(cls.build_payload)
        cls.first_file_sha256 = hashlib.sha256(cls.first_bytes).hexdigest()
        cls.payload = _parse_payload_from_source(cls.first_bytes.decode("utf-8"))
        cls.pointer, cls.manifest, cls.registry = _manifest_from_pointer()

    def test_01_independent_validator_gate_passed(self) -> None:
        self.assertTrue(self.validation_report["pass"])
        self.assertTrue(self.validation_report["data_integrity_pass"])
        self.assertTrue(all(self.validation_report["checks"].values()))
        lifecycle = self.validation_report["registry_lifecycle_status"]
        if lifecycle == "approved_for_frontend_binding":
            self.assertTrue(self.validation_report["front_end_bindable"])
            self.assertEqual(self.validation_report["frontend_binding_status"], "ok")
        else:
            self.assertEqual(lifecycle, "candidate_data_release")
            self.assertFalse(self.validation_report["front_end_bindable"])
            self.assertEqual(
                self.validation_report["frontend_binding_status"],
                "registry_not_approved_for_frontend",
            )

    def test_02_js_reverse_parse_and_canonical_payload_sha(self) -> None:
        self.assertEqual(self.payload, self.build_payload)
        without_sha = {
            key: value for key, value in self.payload.items()
            if key != "bundle_payload_sha256"
        }
        self.assertEqual(self.payload["bundle_payload_sha256"], fill.payload_sha256(without_sha))
        source = self.first_bytes.decode("utf-8")
        self.assertIn("root.__S3_FILL_REGISTER__", source)
        self.assertIn("__S3_FILL_VERIFIED_QUEUE__", source)
        self.assertNotIn("__S3_FILL_PAYLOAD__", source)
        self.assertNotIn("fetch(", source)

    def test_03_release_manifest_pointer_validator_and_registry_provenance(self) -> None:
        active_entries = [
            entry for entry in self.registry["entries"]
            if entry["release_id"] == self.registry["active_release_id"]
        ]
        self.assertEqual(len(active_entries), 1)
        self.assertEqual(self.payload["release"]["release_id"], self.pointer["release_id"])
        self.assertEqual(self.payload["pointer"], self.pointer)
        self.assertEqual(self.payload["registry"]["schema_version"], self.registry["schema_version"])
        self.assertEqual(self.payload["registry"]["active_release_id"], self.registry["active_release_id"])
        self.assertEqual(self.payload["registry"]["active_entry"], active_entries[0])
        self.assertEqual(
            self.payload["manifest"]["manifest_payload_sha256"],
            self.manifest["manifest_sha256"],
        )
        self.assertEqual(
            self.payload["manifest"]["manifest_file_sha256"],
            self.pointer["manifest_file_sha256"],
        )
        self.assertTrue(self.payload["validator"]["pass"])
        self.assertEqual(
            self.payload["validator"]["data_integrity_pass"],
            self.validation_report["data_integrity_pass"],
        )
        self.assertEqual(
            self.payload["validator"]["front_end_bindable"],
            self.validation_report["front_end_bindable"],
        )
        self.assertEqual(
            self.payload["validator"]["frontend_binding_status"],
            self.validation_report["frontend_binding_status"],
        )
        self.assertEqual(
            self.payload["validator"]["registry_lifecycle_status"],
            self.validation_report["registry_lifecycle_status"],
        )
        self.assertEqual(
            self.payload["validator"]["report_payload_sha256"],
            self.validation_report["report_payload_sha256"],
        )
        self.assertEqual(self.payload["validator"]["checks"], self.validation_report["checks"])

    def test_04_shared_capacity_catalog_and_score_policy_are_exact(self) -> None:
        shared = self.manifest["shared_input"]
        self.assertEqual(self.payload["capacity"], shared["capacity"])
        self.assertEqual(self.payload["cargo_catalog"], shared["cargo_catalog"])
        self.assertEqual(self.payload["score_policy"], shared["score_policy"])
        self.assertEqual(_recovered_shared(self.payload), shared)
        self.assertEqual(len(self.payload["cargo_catalog"]), 267)

    def test_05_online_lane_identity_is_exact_and_excludes_offline_references(self) -> None:
        lanes = self.payload["online_lanes"]
        self.assertEqual(len(lanes), 3)
        self.assertEqual(
            tuple(lane["algorithm"]["id"] for lane in lanes), EXPECTED_ALGORITHMS
        )
        self.assertEqual(
            tuple(lane["lane_id"] for lane in lanes),
            tuple(f"online_{algorithm}" for algorithm in EXPECTED_ALGORITHMS),
        )
        self.assertEqual(lanes, self.manifest["online_lanes"])
        self.assertNotIn("offline_references", self.payload)
        self.assertNotIn("lap_exact_reference", self.payload)

    def test_06_all_three_times_267_events_match_authoritative_manifest_field_by_field(self) -> None:
        expected_by_id = {
            lane["lane_id"]: lane for lane in self.manifest["online_lanes"]
        }
        self.assertEqual(set(expected_by_id), {lane["lane_id"] for lane in self.payload["online_lanes"]})
        for actual_lane in self.payload["online_lanes"]:
            expected_lane = expected_by_id[actual_lane["lane_id"]]
            self.assertEqual(len(actual_lane["events"]), 267)
            self.assertEqual(len(expected_lane["events"]), 267)
            for event_index, (actual_event, expected_event) in enumerate(
                zip(actual_lane["events"], expected_lane["events"]), start=1
            ):
                self.assertEqual(actual_event, expected_event, f"{actual_lane['lane_id']} event {event_index}")
                self.assertEqual(actual_event["event_index"], event_index)
                for required in (
                    "gid", "decision", "clock", "phases", "ownership_events", "occupancy",
                    "metric_delta", "event_sha256", "inventory_before_sha256",
                    "inventory_after_sha256",
                ):
                    self.assertIn(required, actual_event)
        evidence_lanes = {
            lane["lane_id"]: lane for lane in self.payload["decision_evidence"]["lanes"]
        }
        self.assertEqual(
            self.payload["decision_evidence"]["schema_version"],
            bundle.DECISION_EVIDENCE_SCHEMA,
        )
        self.assertEqual(set(evidence_lanes), set(expected_by_id))
        for lane in self.payload["online_lanes"]:
            algorithm = lane["algorithm"]["id"]
            evidence = evidence_lanes[lane["lane_id"]]
            self.assertEqual(evidence["algorithm"], algorithm)
            self.assertEqual(len(evidence["events"]), 267)
            self.assertEqual(
                evidence["audit_file_sha256"], lane["candidate_audit"]["file_sha256"]
            )
            for event, decision_audit in zip(lane["events"], evidence["events"]):
                self.assertEqual(decision_audit["event_index"], event["event_index"])
                self.assertEqual(
                    decision_audit["audit_sha256"],
                    event["decision"]["candidate_audit_ref"]["audit_sha256"],
                )
                top3 = decision_audit["top3"]
                expected_top_count = min(3, decision_audit["legal_count"])
                self.assertEqual(
                    [item["rank"] for item in top3],
                    list(range(1, expected_top_count + 1)),
                )
                self.assertTrue(top3[0]["selected"])
                self.assertTrue(all(not item["selected"] for item in top3[1:]))
                self.assertEqual(top3[0]["slot"], event["decision"]["selected_slot"])
                if algorithm == "score":
                    self.assertAlmostEqual(
                        top3[0]["score_terms"]["score_total"],
                        event["decision"]["selected_score"], places=9,
                    )
                    self.assertTrue(all("score_terms" in item for item in top3))
                else:
                    self.assertTrue(all("score_terms" not in item for item in top3))

    def test_07_reducer_replays_from_133_plus_zero_to_400_and_all_six_bookmarks(self) -> None:
        for lane in self.payload["online_lanes"]:
            checkpoints = lane["checkpoints"]
            self.assertEqual(tuple(point["event_count"] for point in checkpoints), EXPECTED_CHECKPOINT_COUNTS)
            grid = list(checkpoints[0]["grid_col_major"])
            self.assertEqual(len(grid), 400)
            self.assertEqual(grid.count(-1), 133)
            self.assertEqual(grid.count(0), 267)
            managed_goods = 0
            total_unavailable = 133
            expected_checkpoint = {point["event_count"]: point for point in checkpoints}
            for event in lane["events"]:
                self.assertEqual(event["occupancy"]["managed_before"], managed_goods)
                self.assertEqual(event["occupancy"]["total_unavailable_before"], total_unavailable)
                col, tier = event["decision"]["selected_slot"]
                slot_index = col * self.payload["capacity"]["tiers"] + tier
                self.assertEqual(grid[slot_index], 0, f"{lane['lane_id']} slot already occupied")
                self.assertEqual(event["slot_state_change"]["before"], "EMPTY")
                self.assertEqual(event["slot_state_change"]["after"], f"GID:{event['gid']}")
                grid[slot_index] = event["gid"]
                managed_goods += 1
                total_unavailable += 1
                self.assertEqual(event["occupancy"]["managed_after"], managed_goods)
                self.assertEqual(event["occupancy"]["total_unavailable_after"], total_unavailable)
                checkpoint = expected_checkpoint.get(event["event_index"])
                if checkpoint is not None:
                    self.assertEqual(grid, checkpoint["grid_col_major"], f"{lane['lane_id']} checkpoint {managed_goods}")
                    self.assertEqual(checkpoint["managed_goods"], managed_goods)
                    self.assertEqual(checkpoint["total_unavailable"], total_unavailable)
            self.assertEqual((managed_goods, total_unavailable), (267, 400))
            self.assertEqual(grid, lane["final_grid_col_major"])
            self.assertEqual(grid.count(-1), 133)
            self.assertEqual(grid.count(0), 0)
            self.assertEqual(len([value for value in grid if value > 0]), 267)

    def test_08_nan_and_infinity_are_forbidden(self) -> None:
        _assert_finite(self, self.payload)
        json.dumps(self.payload, allow_nan=False)

    def test_09_second_generation_is_byte_identical(self) -> None:
        second_payload, second_report = bundle.build_payload()
        second_bytes = bundle.render_bundle(second_payload)
        second_file_sha256 = hashlib.sha256(second_bytes).hexdigest()
        self.assertEqual(second_payload, self.build_payload)
        self.assertEqual(second_report["report_payload_sha256"], self.validation_report["report_payload_sha256"])
        self.assertEqual(second_file_sha256, self.first_file_sha256)
        self.assertEqual(second_bytes, self.first_bytes)

    def test_10_release_registry_and_pointer_inputs_remain_unchanged(self) -> None:
        self.assertEqual(_input_fingerprint(), self.inputs_before)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(S3FillFrontendBundleTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if result.wasSuccessful():
        payload, _ = bundle.build_payload()
        rendered = bundle.render_bundle(payload)
        print(
            "S3 frontend bundle tests PASS 10/10; "
            f"bundle_payload_sha256={payload['bundle_payload_sha256']}; "
            f"file_sha256={hashlib.sha256(rendered).hexdigest()}"
        )
    raise SystemExit(0 if result.wasSuccessful() else 1)
