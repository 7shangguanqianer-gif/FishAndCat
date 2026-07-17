# -*- coding: utf-8 -*-
"""S3 fill-only 数据门回归。"""
import copy
import hashlib
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import fill_only as fill


class TestFillOnlyContract(unittest.TestCase):
    @staticmethod
    def _reseal_self_consistent(lane, audits):
        audit_prefix = hashlib.sha256(b"s3-fill-audit-genesis-v1").hexdigest()
        audit_prefixes = {0: audit_prefix}
        for index, audit in enumerate(audits, start=1):
            audit.pop("audit_sha256", None)
            audit["audit_sha256"] = fill.payload_sha256(audit)
            audit_prefix = hashlib.sha256(
                (audit_prefix + audit["audit_sha256"]).encode("ascii")
            ).hexdigest()
            audit_prefixes[index] = audit_prefix
            event = lane["events"][index - 1]
            event["decision"]["candidate_audit_ref"]["audit_sha256"] = audit[
                "audit_sha256"
            ]
            event.pop("event_sha256", None)
            event["event_sha256"] = fill.payload_sha256(event)
        event_prefix = hashlib.sha256(b"s3-fill-genesis-v1").hexdigest()
        event_prefixes = {0: event_prefix}
        for index, event in enumerate(lane["events"], start=1):
            event_prefix = hashlib.sha256(
                (event_prefix + event["event_sha256"]).encode("ascii")
            ).hexdigest()
            event_prefixes[index] = event_prefix
        for checkpoint in lane["checkpoints"]:
            count = checkpoint["event_count"]
            checkpoint["audit_prefix_sha256"] = audit_prefixes[count]
            checkpoint["event_prefix_sha256"] = event_prefixes[count]
        lane["candidate_audit"]["audit_prefix_sha256"] = audit_prefix
        lane.pop("lane_result_sha256", None)
        lane["lane_result_sha256"] = fill.payload_sha256(lane)

    def test_canonical_capacity_and_safe_profile(self):
        shared = fill.build_shared_input()
        capacity = shared["capacity"]
        self.assertEqual(capacity["total_slots"], 400)
        self.assertEqual(capacity["preoccupied_slots"], 133)
        self.assertEqual(capacity["managed_capacity"], 267)
        self.assertEqual(capacity["start"], {"managed_goods": 0, "total_unavailable": 133})
        self.assertEqual(capacity["full_endpoint"],
                         {"managed_goods": 267, "total_unavailable": 400})
        self.assertEqual(len(shared["cargo_catalog"]), 267)
        self.assertLessEqual(max(item["weight_kg"] for item in shared["cargo_catalog"]), 60.0)
        self.assertLessEqual(max(item["volume_m3"] for item in shared["cargo_catalog"]), 0.9)
        self.assertEqual(
            shared["runtime_provenance"]["locked_versions"],
            {"python": shared["runtime_provenance"]["python"],
             "numpy": shared["runtime_provenance"]["numpy"],
             "scipy": shared["runtime_provenance"]["scipy"]},
        )

    def test_dependency_lock_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            lock = os.path.join(tmp, "requirements.lock")
            with open(lock, "w", encoding="utf-8") as handle:
                handle.write("python==0.0.0\nnumpy==0.0.0\nscipy==0.0.0\n")
            with mock.patch.object(fill, "DEPENDENCY_LOCK", fill.Path(lock)):
                with self.assertRaisesRegex(RuntimeError, "dependency lock mismatch"):
                    fill.build_shared_input(count=1)

    def test_shared_input_is_deterministic_and_hash_guarded(self):
        first = fill.build_shared_input(count=12, seed=77, case="heavy")
        second = fill.build_shared_input(count=12, seed=77, case="heavy")
        self.assertEqual(first, second)
        tampered = copy.deepcopy(first)
        tampered["cargo_catalog"][0]["weight_kg"] += 1.0
        with self.assertRaisesRegex(ValueError, "shared input hash mismatch"):
            fill.run_online_lane(tampered, "score")

    def test_score_normalization_is_fixed_before_arrivals(self):
        short = fill.build_shared_input(count=1, seed=2026)
        full = fill.build_shared_input(count=fill.MANAGED_CAPACITY, seed=2026)
        expected = {
            "source": "predeclared_profile_bounds_not_cargo_catalog_statistics",
            "causal_scope": "known_before_first_arrival",
            "w_max": 60.0,
            "f_max": 100.0,
            "t_max_s": full["motion"]["t_max_score_normalizer_s"],
        }
        self.assertEqual(short["score_policy"]["normalization"], expected)
        self.assertEqual(full["score_policy"]["normalization"], expected)
        self.assertEqual(short["cargo_catalog"][0], full["cargo_catalog"][0])
        short_lane = fill.run_online_lane(short, "score")
        full_lane = fill.run_online_lane(full, "score")
        self.assertEqual(
            short_lane["events"][0]["decision"]["selected_slot"],
            full_lane["events"][0]["decision"]["selected_slot"],
        )

    def test_all_online_lanes_share_inputs_but_own_clocks(self):
        shared = fill.build_shared_input(count=16, seed=88)
        lanes = [fill.run_online_lane(shared, algorithm)
                 for algorithm in fill.ONLINE_ALGORITHMS]
        self.assertEqual({lane["shared_input_sha256"] for lane in lanes},
                         {shared["shared_input_sha256"]})
        self.assertTrue(all(lane["status"] == "FEASIBLE" for lane in lanes))
        self.assertTrue(all(lane["algorithm"]["fallback_policy"] == "none_fail_closed"
                            for lane in lanes))
        self.assertGreater(len({lane["metrics"]["makespan_s"] for lane in lanes}), 1)

    def test_candidate_audit_covers_all_slots_and_links_to_event(self):
        shared = fill.build_shared_input(count=3, seed=99)
        audits = []
        lane = fill.run_online_lane(shared, "score", audits.append, "audit.jsonl.gz")
        self.assertEqual(fill.validate_candidate_audits(lane, audits), [])
        self.assertEqual(len(audits), 3)
        first = audits[0]
        self.assertEqual(first["candidate_count"], 400)
        self.assertEqual(first["legal_count"], 267)
        self.assertEqual(first["rejection_reason_counts"]["PREOCCUPIED"], 133)
        self.assertEqual(sum(row["selected"] for row in first["candidates"]), 1)
        chosen = next(row for row in first["candidates"] if row["selected"])
        self.assertEqual(chosen["rank"], 1)
        self.assertEqual(chosen["slot"], lane["events"][0]["decision"]["selected_slot"])
        self.assertEqual(chosen["score_terms"]["stability_raw"],
                         chosen["score_terms"]["energy_proxy_raw"])
        self.assertTrue(first["known_collinearity"][
            "stability_raw_equals_energy_proxy_raw"])

    def test_non_score_audit_does_not_fabricate_score_terms(self):
        shared = fill.build_shared_input(count=1)
        for algorithm in ("seq", "near"):
            audits = []
            lane = fill.run_online_lane(shared, algorithm, audits.append)
            selected = next(row for row in audits[0]["candidates"] if row["selected"])
            self.assertNotIn("score_terms", selected)
            self.assertIsNone(lane["events"][0]["decision"]["selected_score"])

    def test_candidate_audit_tampering_is_detected(self):
        shared = fill.build_shared_input(count=2)
        audits = []
        lane = fill.run_online_lane(shared, "near", audits.append)
        audits[0]["selected_slot"] = [19, 19]
        errors = fill.validate_candidate_audits(lane, audits)
        self.assertTrue(any(item.startswith("audit_hash:1") for item in errors))
        self.assertIn("selected_slot:1", errors)

    def test_semantic_replay_rejects_self_consistent_rehash(self):
        shared = fill.build_shared_input(count=3, seed=177)
        audits = []
        lane = fill.run_online_lane(shared, "score", audits.append)
        forged_lane = copy.deepcopy(lane)
        forged_audits = copy.deepcopy(audits)
        selected = next(
            row for row in forged_audits[0]["candidates"] if row["selected"]
        )
        selected["score_terms"]["score_total"] += 0.001
        forged_lane["events"][0]["decision"]["selected_score"] = selected[
            "score_terms"
        ]["score_total"]
        self._reseal_self_consistent(forged_lane, forged_audits)
        self.assertEqual(fill.validate_online_lane(shared, forged_lane), [])
        self.assertEqual(
            fill.validate_candidate_audits(forged_lane, forged_audits), []
        )
        replay_errors = fill.replay_validate_online_lane(
            shared, forged_lane, forged_audits
        )
        self.assertIn("semantic_audit_mismatch:1", replay_errors)
        self.assertIn("lane_semantic_replay", replay_errors)

    def test_semantic_replay_rejects_rehashed_fake_metrics(self):
        shared = fill.build_shared_input(count=3, seed=178)
        audits = []
        lane = fill.run_online_lane(shared, "near", audits.append)
        forged = copy.deepcopy(lane)
        forged["metrics"]["makespan_s"] = 0.0
        forged.pop("lane_result_sha256")
        forged["lane_result_sha256"] = fill.payload_sha256(forged)
        self.assertEqual(fill.validate_online_lane(shared, forged), [])
        self.assertIn(
            "lane_semantic_replay",
            fill.replay_validate_online_lane(shared, forged, audits),
        )

    def test_full_267_score_lane_reaches_exact_bookmarks(self):
        shared = fill.build_shared_input()
        lane = fill.run_online_lane(shared, "score")
        self.assertEqual(fill.validate_online_lane(shared, lane), [])
        self.assertEqual([item["event_count"] for item in lane["checkpoints"]],
                         [0, 67, 134, 201, 241, 267])
        self.assertEqual(lane["metrics"]["placed"], 267)
        self.assertEqual(lane["metrics"]["managed_fill_ratio"], 1.0)
        self.assertEqual(lane["metrics"]["total_occupancy_ratio"], 1.0)
        self.assertEqual(lane["metrics"]["violations"], 0)
        self.assertNotIn("OUTFEED", str(lane))
        self.assertNotIn("CONSUMED", str(lane))

    def test_all_three_full_267_lanes_reach_safe_terminal(self):
        shared = fill.build_shared_input()
        for algorithm in fill.ONLINE_ALGORITHMS:
            lane = fill.run_online_lane(shared, algorithm)
            self.assertEqual(fill.validate_online_lane(shared, lane), [])
            self.assertEqual(lane["terminal_state"], "FULL_SAFE")
            self.assertEqual(lane["metrics"]["placed"], 267)
            self.assertEqual(lane["metrics"]["failed"], 0)
            self.assertEqual(lane["metrics"]["violations"], 0)

    def test_offline_and_exact_references_are_not_online_lanes(self):
        shared = fill.build_shared_input(count=24)
        awra = fill.run_awra_offline_reference(shared)
        lap = fill.run_lap_exact_references(shared)
        self.assertEqual(awra["status"], "FEASIBLE")
        self.assertEqual(awra["placed"], 24)
        self.assertEqual(awra["decision_scope"], "offline_batch")
        self.assertIn("not_same_information_set", awra["comparison_role"])
        self.assertEqual(lap["decision_scope"], "offline_exact_static_assignment")
        self.assertEqual(
            lap["objectives"]["score"]["normalization"], {
                "w_max": shared["score_policy"]["normalization"]["w_max"],
                "f_max": shared["score_policy"]["normalization"]["f_max"],
                "t_max_s": shared["score_policy"]["normalization"]["t_max_s"],
                "score_policy_id": shared["score_policy"]["id"],
            },
        )
        self.assertEqual(
            lap["objectives"]["score"]["objective_contract"],
            "same_frozen_score_normalization_as_online_and_awra_reference",
        )
        for item in lap["objectives"].values():
            self.assertEqual(item["status"], "FEASIBLE")
            self.assertEqual(item["assignment_count"], 24)


if __name__ == "__main__":
    unittest.main()
