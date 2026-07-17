# -*- coding: utf-8 -*-
"""S3 multi-strategy showcase: versioned cargo-scenario contract tests."""

import copy
import os
import sys
import unittest


SIM = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if SIM not in sys.path:
    sys.path.insert(0, SIM)

import cargo_scenarios as cs
import instance_gen as ig
import warehouse_sim as ws


def values(goods, attr):
    return sorted(getattr(g, attr) for g in goods)


class TestCargoScenarioRegistry(unittest.TestCase):
    def test_registry_has_all_scenarios_and_seed_partitions(self):
        registry = cs.load_registry()
        self.assertEqual(registry["schema_version"], "cargo_dynamic_v1")
        self.assertEqual(
            list(registry["scenarios"]),
            [f"E{i:02d}" for i in range(1, 19)],
        )
        self.assertEqual(registry["seed_ranges"]["S1_exploration"], [2026, 2035])
        self.assertEqual(registry["seed_ranges"]["S2_confirmation"], [31001, 31030])
        self.assertEqual(registry["seed_ranges"]["S3_long_run"], [41001, 41010])
        self.assertEqual(registry["seed_ranges"]["weight_v2_untouched"], [51001, 51030])

        required = {
            "initial_goods_generator",
            "inbound_goods_generator",
            "request_pool_policy",
            "invalid_inbound_policy",
        }
        for sid, scenario in registry["scenarios"].items():
            self.assertTrue(required.issubset(scenario), sid)

    def test_all_scenarios_are_deterministic_and_gid_unique(self):
        registry = cs.load_registry()
        for sid, scenario in registry["scenarios"].items():
            cycles = scenario["scheduled_cycles"]
            first_initial = cs.build_initial_goods(sid, 2026)
            again_initial = cs.build_initial_goods(sid, 2026)
            first_inbound = cs.build_inbound_goods(sid, 2026, cycles)
            again_inbound = cs.build_inbound_goods(sid, 2026, cycles)

            self.assertEqual(len(first_initial), scenario["initial_count"], sid)
            self.assertEqual(len(first_inbound), cycles, sid)
            self.assertEqual(cs.goods_signature(first_initial), cs.goods_signature(again_initial), sid)
            self.assertEqual(cs.goods_signature(first_inbound), cs.goods_signature(again_inbound), sid)

            gids = [g.gid for g in first_initial + first_inbound]
            self.assertEqual(len(gids), len(set(gids)), sid)

    def test_correlated_scenarios_preserve_marginals_and_hit_threshold(self):
        seed = 2026
        for sid in ("E10", "E11", "E12"):
            initial = cs.build_initial_goods(sid, seed)
            inbound = cs.build_inbound_goods(sid, seed, 100)
            baseline_initial = ws.gen_goods(120, seed, "skew")
            baseline_inbound = ws.gen_goods(100, seed + 7, "skew")

            for attr in ("weight", "freq", "vol"):
                self.assertEqual(values(initial, attr), values(baseline_initial, attr), (sid, attr, "initial"))
                self.assertEqual(values(inbound, attr), values(baseline_inbound, attr), (sid, attr, "inbound"))

            p0 = cs.scenario_profile(initial)
            p1 = cs.scenario_profile(inbound)
            if sid == "E10":
                self.assertGreaterEqual(p0["rho_weight_freq"], 0.75)
                self.assertGreaterEqual(p1["rho_weight_freq"], 0.75)
            elif sid == "E11":
                self.assertLessEqual(p0["rho_weight_freq"], -0.75)
                self.assertLessEqual(p1["rho_weight_freq"], -0.75)
            else:
                self.assertGreaterEqual(p0["rho_weight_volume"], 0.75)
                self.assertGreaterEqual(p1["rho_weight_volume"], 0.75)

    def test_correlations_hold_across_registered_s1_and_s2_seeds(self):
        seeds = list(range(2026, 2036)) + list(range(31001, 31031))
        for seed in seeds:
            for sid, field, threshold in (
                ("E10", "rho_weight_freq", 0.75),
                ("E11", "rho_weight_freq", -0.75),
                ("E12", "rho_weight_volume", 0.75),
            ):
                for goods in (
                    cs.build_initial_goods(sid, seed),
                    cs.build_inbound_goods(sid, seed, 100),
                ):
                    actual = cs.scenario_profile(goods)[field]
                    if threshold > 0:
                        self.assertGreaterEqual(actual, threshold, (sid, seed, actual))
                    else:
                        self.assertLessEqual(actual, threshold, (sid, seed, actual))

    def test_e04_to_e09_initial_generators_match_existing_source_scenarios(self):
        mapping = {
            "E04": "tiny_light",
            "E05": "light_sparse",
            "E06": "flat_info",
            "E07": "heavy_sparse",
            "E08": "dense_200",
            "E09": "dense_240",
        }
        for sid, source_name in mapping.items():
            actual = cs.build_initial_goods(sid, 2026)
            expected = ig.gen_instance(source_name, 2026)
            for attr in ("weight", "freq", "vol"):
                self.assertEqual(
                    [getattr(g, attr) for g in actual],
                    [getattr(g, attr) for g in expected],
                    (sid, attr),
                )

    def test_e04_to_e09_inbound_generators_match_existing_source_parameters(self):
        dsl_mapping = {
            "E04": "tiny_light",
            "E05": "light_sparse",
            "E06": "flat_info",
            "E07": "heavy_sparse",
        }
        for sid, source_name in dsl_mapping.items():
            temp_name = f"__test_inbound_{source_name}"
            source = copy.deepcopy(ig.SCENARIOS[source_name])
            source["n"] = 100
            ig.SCENARIOS[temp_name] = source
            try:
                expected = ig.gen_instance(temp_name, 2026 + 7)
            finally:
                del ig.SCENARIOS[temp_name]
            actual = cs.build_inbound_goods(sid, 2026, 100)
            for attr in ("weight", "freq", "vol"):
                self.assertEqual(
                    [getattr(g, attr) for g in actual],
                    [getattr(g, attr) for g in expected],
                    (sid, attr),
                )

        for sid in ("E08", "E09"):
            actual = cs.build_inbound_goods(sid, 2026, 100)
            expected = ws.gen_goods(100, 2026 + 7, "skew")
            for attr in ("weight", "freq", "vol"):
                self.assertEqual(
                    [getattr(g, attr) for g in actual],
                    [getattr(g, attr) for g in expected],
                    (sid, attr),
                )

    def test_registry_semantic_validation_rejects_contract_drift(self):
        base = cs.load_registry()

        broken = copy.deepcopy(base)
        broken["scenarios"]["E02"]["request_pool_policy"]["weight"] = "position"
        with self.assertRaisesRegex(ValueError, "request_pool_policy"):
            cs._validate_registry(broken, "cargo_dynamic_v1")

        broken = copy.deepcopy(base)
        broken["scenarios"]["E14"]["valid_cycles"] = 95
        with self.assertRaisesRegex(ValueError, "valid_cycles"):
            cs._validate_registry(broken, "cargo_dynamic_v1")

        broken = copy.deepcopy(base)
        broken["scenarios"]["E18"]["inbound_goods_generator"]["segments"][1]["start_cycle"] = 34
        with self.assertRaisesRegex(ValueError, "segments"):
            cs._validate_registry(broken, "cargo_dynamic_v1")

    def test_near_limit_and_illegal_mix_contracts(self):
        for goods in (
            cs.build_initial_goods("E13", 2026),
            cs.build_inbound_goods("E13", 2026, 100),
        ):
            self.assertTrue(all(90.0 <= g.weight <= 99.5 for g in goods))
            self.assertTrue(all(0.90 <= g.vol <= 0.99 for g in goods))
            self.assertTrue(all(cs.is_legal_cargo(g) for g in goods))

        initial = cs.build_initial_goods("E14", 2026)
        inbound = cs.build_inbound_goods("E14", 2026, 100)
        self.assertTrue(all(cs.is_legal_cargo(g) for g in initial))
        illegal = [g for g in inbound if not cs.is_legal_cargo(g)]
        self.assertEqual(len(illegal), 6)
        self.assertEqual(sum(g.weight > ws.BASE_CAP for g in illegal), 3)
        self.assertEqual(sum(g.vol > ws.CELL_VOL for g in illegal), 3)

    def test_e15_downgrade_flags_and_manifest_hashes_are_explicit(self):
        scenario = cs.load_registry()["scenarios"]["E15"]
        self.assertIs(scenario["extended_pressure"], True)
        self.assertIs(scenario["canonical_g2"], False)
        self.assertIs(scenario["headline_eligible"], False)

        first = cs.scenario_manifest("E15")
        second = cs.scenario_manifest("E15")
        self.assertEqual(first, second)
        self.assertEqual(first["scenario_id"], "E15")
        self.assertEqual(len(first["registry_sha256"]), 64)
        self.assertGreaterEqual(len(first["source_sha256"]), 4)
        self.assertTrue(all(len(value) == 64 for value in first["source_sha256"].values()))
        self.assertIn("sim/mixed_ops.py", first["source_sha256"])
        self.assertEqual(
            set(first["function_sha256"]),
            {
                "mixed_ops.build_scenario_workload",
                "mixed_ops.build_workload",
                "mixed_ops.initial_layout",
                "mixed_ops.online_strategy_callable",
                "mixed_ops.resolve_strategy_mode",
                "realism.build_fault_intervals",
                "realism.build_noise_stream",
                "realism.common_arrivals_for_workload",
                "realism.run_tier3",
                "strategy_lib.explain_selection",
                "strategy_lib.select_strategy",
            },
        )
        self.assertTrue(all(len(value) == 64 for value in first["function_sha256"].values()))


if __name__ == "__main__":
    unittest.main()
