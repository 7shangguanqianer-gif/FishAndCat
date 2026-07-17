# -*- coding: utf-8 -*-
"""Seven fixed strategy chains plus one-shot AUTO routing."""

import os
import sys
import unittest


SIM = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if SIM not in sys.path:
    sys.path.insert(0, SIM)

import cargo_scenarios as cs
import mixed_ops as mo
import realism
import strategy_lib as sl
import warehouse_sim as ws


class TestAutoStrategyDynamic(unittest.TestCase):
    def setUp(self):
        self.old_accel = ws.ACCEL
        ws.ACCEL = True

    def tearDown(self):
        ws.ACCEL = self.old_accel

    @staticmethod
    def profile(n=120, density=0.45, skew=0.50, w_mean=40.0, w_heavy=0.2):
        return dict(n=n, density=density, skew=skew, w_mean=w_mean, w_heavy=w_heavy)

    @staticmethod
    def score_fn(goods):
        w_max = max(g.weight for g in goods)
        f_max = max(g.freq for g in goods)
        return ws.make_score_fn(1.0, 0.6, 0.4, 0.15, w_max, f_max), w_max, f_max

    def test_s0_direct_threshold_boundaries(self):
        for density, expected in (
            (0.249, "awra"), (0.250, "awra"), (0.251, "tob"),
            (0.699, "tob"), (0.700, "cb"), (0.701, "cb"),
        ):
            actual = sl.select_strategy(
                self.profile(density=density), batch_known=True,
                objective="lexicographic",
            )
            self.assertEqual(actual, expected, density)

        for skew, expected in ((0.349, "near"), (0.350, "score"), (0.351, "score")):
            actual = sl.select_strategy(
                self.profile(skew=skew), batch_known=False,
                objective="lexicographic",
            )
            self.assertEqual(actual, expected, skew)

    def test_s0_production_reachable_batch_boundaries(self):
        expected = {65: "awra", 66: "awra", 67: "tob", 186: "tob", 187: "cb", 188: "cb"}
        for n, pick in expected.items():
            goods = ws.gen_goods(n, 2026, "skew")
            profile = sl.batch_profile(goods)
            self.assertEqual(
                sl.select_strategy(profile, batch_known=True, objective="lexicographic"),
                pick,
                (n, profile["density"]),
            )

    def test_v1_router_is_weight_invariant_and_default_stays_holistic(self):
        for objective in ("holistic", "lexicographic", "speed"):
            for batch_known in (True, False):
                low = self.profile(w_mean=10.0, w_heavy=0.0)
                high = self.profile(w_mean=95.0, w_heavy=1.0)
                self.assertEqual(
                    sl.select_strategy(low, batch_known, objective),
                    sl.select_strategy(high, batch_known, objective),
                    (objective, batch_known),
                )
        profile = self.profile()
        self.assertEqual(
            sl.select_strategy(profile),
            sl.select_strategy(profile, objective="holistic"),
        )

    def test_chain_registry_is_exact_and_batch_algorithms_fall_back_to_score(self):
        self.assertEqual(
            sl.STRATEGY_CHAINS,
            {
                "random": {"initial": "random", "online": "random"},
                "seq": {"initial": "seq", "online": "seq"},
                "near": {"initial": "near", "online": "near"},
                "score": {"initial": "score", "online": "score"},
                "awra": {"initial": "awra", "online": "score"},
                "cb": {"initial": "cb", "online": "score"},
                "tob": {"initial": "tob", "online": "score"},
            },
        )

    def test_cb_tob_initial_layouts_are_source_identical(self):
        goods = ws.gen_goods(120, 2026, "skew")
        fn, w_max, f_max = self.score_fn(goods)
        for name, direct in (("cb", sl.run_class_based), ("tob", sl.run_full_turnover)):
            _, actual_pos, actual_failed = mo.initial_layout(
                name, goods, fn, w_max, f_max, seed=2026, return_failed=True,
            )
            _, placed, expected_failed = direct(goods, "sum")
            self.assertEqual(actual_pos, {g.gid: pos for g, pos in placed}, name)
            self.assertEqual([g.gid for g in actual_failed], [g.gid for g in expected_failed], name)

    def test_auto_matches_explicit_lexicographic_router_for_all_scenarios(self):
        registry = cs.load_registry()
        for sid in registry["scenarios"]:
            goods = cs.build_initial_goods(sid, 2026)
            decision = mo.resolve_strategy_mode(
                "AUTO", goods, batch_known=True, objective="lexicographic"
            )
            profile = sl.batch_profile(goods)
            self.assertEqual(
                decision["picked"],
                sl.select_strategy(profile, batch_known=True, objective="lexicographic"),
                sid,
            )
            self.assertEqual(decision["objective"], "lexicographic")
            self.assertIs(decision["weight_aware"], False)
            self.assertEqual(decision["selection_scope"], "run_start_once")

    def test_e18_auto_pick_is_not_changed_by_advisories(self):
        scenario = cs.load_registry()["scenarios"]["E18"]
        goods = cs.build_initial_goods("E18", 2026)
        inbound = cs.build_inbound_goods("E18", 2026, 99)
        workload = mo.build_scenario_workload(goods, inbound, scenario, 2026)
        fn, w_max, f_max = self.score_fn(goods)
        arrivals, _ = realism.common_arrivals_for_workload(
            goods, workload, fn, w_max, f_max, fn, seed=2026,
            tier3_params=scenario["tier3"],
        )
        result = realism.run_tier3(
            "AUTO", goods, workload["valid_inbound_goods"], workload["requests"],
            fn, w_max, f_max, fn, arrivals=arrivals, cycles=99, seed=2026,
            workload=workload, tier3_params=scenario["tier3"],
            router_objective="lexicographic", batch_known=True,
        )
        self.assertEqual(result["router"]["picked"], "tob")
        self.assertEqual(result["strategy_switches"], 0)
        self.assertEqual(result["advisory_count"], 2)
        self.assertEqual(result["router"]["selection_scope"], "run_start_once")

    def test_all_seven_fixed_chains_and_auto_share_exogenous_stream_hashes(self):
        scenario = cs.load_registry()["scenarios"]["E02"]
        goods = cs.build_initial_goods("E02", 2026)
        inbound = cs.build_inbound_goods("E02", 2026, 100)
        workload = mo.build_scenario_workload(goods, inbound, scenario, 2026)
        fn, w_max, f_max = self.score_fn(goods)
        arrivals, _ = realism.common_arrivals_for_workload(
            goods, workload, fn, w_max, f_max, fn, seed=2026,
            tier3_params=scenario["tier3"],
        )
        outputs = {}
        for mode in mo.DYNAMIC_STRATS + ["AUTO"]:
            outputs[mode] = realism.run_tier3(
                mode, goods, workload["valid_inbound_goods"], workload["requests"],
                fn, w_max, f_max, fn, arrivals=arrivals, cycles=100, seed=2026,
                workload=workload, tier3_params=scenario["tier3"],
                router_objective="lexicographic", batch_known=True,
            )
        hashes = [result["stream_hashes"] for result in outputs.values()]
        self.assertEqual(hashes, [hashes[0]] * 8)
        self.assertTrue(all(result["status"] == "FEASIBLE" for result in outputs.values()))
        self.assertEqual(outputs["AUTO"]["picked_strategy"], "tob")
        for batch_mode in ("awra", "cb", "tob"):
            self.assertEqual(outputs[batch_mode]["router"]["online_strategy"], "score")

        repeat_random = realism.run_tier3(
            "random", goods, workload["valid_inbound_goods"], workload["requests"],
            fn, w_max, f_max, fn, arrivals=arrivals, cycles=100, seed=2026,
            workload=workload, tier3_params=scenario["tier3"],
        )
        self.assertEqual(outputs["random"], repeat_random)

    def test_initial_batch_failure_is_explicit_infeasible_not_a_crash(self):
        scenario = cs.load_registry()["scenarios"]["E09"]
        goods = cs.build_initial_goods("E09", 2026)
        inbound = cs.build_inbound_goods("E09", 2026, 100)
        workload = mo.build_scenario_workload(goods, inbound, scenario, 2026)
        fn, w_max, f_max = self.score_fn(goods)
        arrivals, _ = realism.common_arrivals_for_workload(
            goods, workload, fn, w_max, f_max, fn, seed=2026,
            tier3_params=scenario["tier3"],
        )
        result = realism.run_tier3(
            "tob", goods, workload["valid_inbound_goods"], workload["requests"],
            fn, w_max, f_max, fn, arrivals=arrivals, cycles=100, seed=2026,
            workload=workload, tier3_params=scenario["tier3"],
        )
        self.assertEqual(result["status"], "INFEASIBLE")
        self.assertGreater(result["initial_fails"], 0)
        self.assertIsNone(result["resp_p95"])
        self.assertEqual(result["response_sample_n"], 0)
        self.assertEqual(set(result["stream_hashes"]),
                         {"workload_hash", "arrivals_hash", "noise_hash", "fault_stream_hash"})


if __name__ == "__main__":
    unittest.main()
