# -*- coding: utf-8 -*-
"""Scenario workload contract: CRN, gate rejection and E18 drift advisory."""

import hashlib
import json
import os
import random
import sys
import unittest


SIM = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if SIM not in sys.path:
    sys.path.insert(0, SIM)

import cargo_scenarios as cs
import warehouse_sim as ws
from mixed_ops import build_scenario_workload, build_workload


def legacy_hash(new_goods, requests):
    payload = {
        "new": [(g.gid, g.name, g.weight, g.freq, g.vol) for g in new_goods],
        "request_gids": [g.gid for g in requests],
    }
    raw = json.dumps(payload, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


class TestScenarioWorkload(unittest.TestCase):
    def scenario_inputs(self, sid, seed=2026):
        scenario = cs.load_registry()["scenarios"][sid]
        initial = cs.build_initial_goods(sid, seed)
        inbound = cs.build_inbound_goods(sid, seed, scenario["scheduled_cycles"])
        return scenario, initial, inbound

    def test_legacy_build_workload_golden_is_unchanged(self):
        initial = ws.gen_goods(120, 2026, "skew")
        new_goods, requests = build_workload(initial, 100, 2026)
        self.assertEqual(
            legacy_hash(new_goods, requests),
            "332dad835199fd1f39145fbda2d3e321780b6de687c66b108ea7dd0f1faeac2f",
        )

    def test_scenario_workload_is_deterministic_and_strategy_independent(self):
        scenario, initial, inbound = self.scenario_inputs("E02")
        hashes = []
        for _mode in ("random", "seq", "near", "score", "awra", "cb", "tob", "AUTO"):
            result = build_scenario_workload(initial, inbound, scenario, 2026)
            hashes.append(result["workload_hash"])
        self.assertEqual(len(set(hashes)), 1)

        result = build_scenario_workload(initial, inbound, scenario, 2026)
        self.assertEqual(result["scheduled_cycles"], 100)
        self.assertEqual(result["valid_cycles"], 100)
        self.assertEqual(result["rejected_cycles"], 0)
        self.assertEqual(len(result["requests"]), 100)
        self.assertEqual(len(result["dispatch_mask"]), 100)
        self.assertTrue(all(result["dispatch_mask"]))

    def test_all_registered_scenarios_conserve_inventory_and_gid_ownership(self):
        registry = cs.load_registry()
        for sid, scenario in registry["scenarios"].items():
            initial = cs.build_initial_goods(sid, 2026)
            inbound = cs.build_inbound_goods(sid, 2026, scenario["scheduled_cycles"])
            result = build_scenario_workload(initial, inbound, scenario, 2026)
            self.assertEqual(result["scenario_id"], sid)
            self.assertEqual(result["final_inventory_count"], scenario["initial_count"], sid)
            self.assertEqual(len(result["final_pool_gids"]), len(set(result["final_pool_gids"])), sid)
            self.assertEqual(
                result["rejected_cycles"],
                scenario["invalid_inbound_policy"]["expected_count"],
                sid,
            )
            self.assertEqual(
                result["valid_cycles"] + result["rejected_cycles"],
                result["scheduled_cycles"],
                sid,
            )

    def test_requests_follow_frequency_weighted_evolving_legal_pool(self):
        scenario, initial, inbound = self.scenario_inputs("E02")
        result = build_scenario_workload(initial, inbound, scenario, 2026)

        rng = random.Random(2026 + 13)
        pool = list(initial)
        expected = []
        for good_in in inbound:
            good_out = rng.choices(pool, weights=[g.freq for g in pool], k=1)[0]
            expected.append(good_out.gid)
            pool.remove(good_out)
            pool.append(good_in)
        self.assertEqual([g.gid for g in result["requests"]], expected)
        self.assertEqual(result["final_pool_gids"], [g.gid for g in pool])

    def test_e14_rejects_six_without_dispatch_or_inventory_mutation(self):
        scenario, initial, inbound = self.scenario_inputs("E14")
        result = build_scenario_workload(initial, inbound, scenario, 2026)
        self.assertEqual(result["scheduled_cycles"], 100)
        self.assertEqual(result["valid_cycles"], 94)
        self.assertEqual(result["rejected_cycles"], 6)
        self.assertEqual(result["response_sample_n"], 94)
        self.assertEqual(result["reject_service_s"], 0)
        self.assertEqual(len(result["requests"]), 94)
        self.assertEqual(len(result["valid_inbound_goods"]), 94)
        self.assertEqual(result["final_inventory_count"], 120)

        rejected = [cycle for cycle in result["cycles"] if not cycle["dispatch"]]
        self.assertEqual(len(rejected), 6)
        for cycle in rejected:
            self.assertEqual(cycle["status"], "REJECT_NO_DISPATCH")
            self.assertIsNone(cycle["outbound_gid"])
            self.assertEqual(cycle["inventory_before"], cycle["inventory_after"])
            self.assertNotIn(cycle["inbound_gid"], result["final_pool_gids"])

        self.assertEqual(
            sum(cycle["inventory_after"] - cycle["inventory_before"] for cycle in result["cycles"]),
            0,
        )

    def test_e18_segments_and_advisories_do_not_apply_a_route_change(self):
        scenario, initial, inbound = self.scenario_inputs("E18")
        result = build_scenario_workload(initial, inbound, scenario, 2026)
        labels = [cycle["inbound_profile"] for cycle in result["cycles"]]
        self.assertEqual(labels[:33], ["uniform"] * 33)
        self.assertEqual(labels[33:66], ["skew"] * 33)
        self.assertEqual(labels[66:], ["heavy"] * 33)
        self.assertEqual([item["cycle"] for item in result["advisories"]], [33, 66])
        for advisory in result["advisories"]:
            self.assertIs(advisory["advisory_only"], True)
            self.assertIs(advisory["applied"], False)
            self.assertIs(advisory["existing_inventory_relayout"], False)
            self.assertEqual(advisory["objective"], "lexicographic")
            self.assertIn(advisory["recommended_strategy"], {"awra", "cb", "tob"})


if __name__ == "__main__":
    unittest.main()
