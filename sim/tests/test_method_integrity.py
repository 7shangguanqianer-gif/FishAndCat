# -*- coding: utf-8 -*-
"""0712 N5/sim 方法修复的最小完整性门。"""

import csv
import os
import sys
import tempfile
import unittest


SIM = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if SIM not in sys.path:
    sys.path.insert(0, SIM)

import adaptive_weights as aw
import lifecycle_sim as life
import oracle_gap as og
import realism
import verify_policy as vp
import warehouse_sim as ws


class TestAdaptiveFailFirst(unittest.TestCase):
    def test_select_policy_uses_only_zero_fail_candidates(self):
        rows = [
            dict(delta=0.10, bg=0.6, exp_mean=4.0, ene_mean=100.0,
                 fail_sum=2, viol_sum=0),
            dict(delta=0.15, bg=1.0, exp_mean=5.0, ene_mean=90.0,
                 fail_sum=0, viol_sum=0),
        ]
        result = aw.select_policy(rows)
        self.assertEqual(result["status"], "FEASIBLE")
        self.assertEqual(result["best_delta"], 0.15)
        self.assertEqual(result["fail"], 0)

    def test_select_policy_returns_infeasible_without_zero_fail_candidate(self):
        rows = [
            dict(delta=0.10, bg=0.6, exp_mean=4.0, ene_mean=100.0,
                 fail_sum=6, viol_sum=0),
            dict(delta=0.15, bg=1.0, exp_mean=5.0, ene_mean=90.0,
                 fail_sum=2, viol_sum=0),
        ]
        result = aw.select_policy(rows)
        self.assertEqual(result["status"], "INFEASIBLE")
        self.assertIsNone(result["best_delta"])
        self.assertIsNone(result["best_exp"])
        self.assertEqual(result["min_fail"], 2)

    def test_verify_run_returns_failed_count(self):
        goods = ws.gen_goods(20, 2026, "skew")
        w_max = max(g.weight for g in goods)
        f_max = max(g.freq for g in goods)
        result = vp.run(goods, "batch", (0.05, 0.6), w_max, f_max)
        self.assertEqual(set(result), {"exp_t", "viol", "fail"})
        self.assertEqual(result["viol"], 0)
        self.assertEqual(result["fail"], 0)

    def test_runtime_lookup_fails_closed_for_infeasible_online_cell(self):
        with self.assertRaisesRegex(ValueError, "INFEASIBLE"):
            ws.lookup_weights(200, "skew", "online")
        self.assertEqual(ws.lookup_weights(200, "skew", "batch"), (0.05, 0.6))


class TestCommonArrivals(unittest.TestCase):
    def test_arrivals_are_deterministic_and_strictly_increasing(self):
        a = realism.build_arrivals(20, 2026, 84.75)
        b = realism.build_arrivals(20, 2026, 84.75)
        self.assertEqual(a, b)
        self.assertEqual(len(a), 20)
        self.assertTrue(all(x < y for x, y in zip(a, a[1:])))


class TestLifecycleDrain(unittest.TestCase):
    def test_end_of_horizon_drains_pending_inventory(self):
        result = life.run_lifecycle(2026, 0.15, cycles=8, day_len=100,
                                    turnover=10, n_init=20)
        self.assertEqual(result["pending_end"], 0)
        self.assertEqual(result["inventory_end"], 20)
        self.assertGreater(result["flush_count"], 0)
        self.assertGreater(result["flush_time"], 0.0)


class TestOracleComparableDomain(unittest.TestCase):
    def test_excess_fail_has_no_time_attainment(self):
        gap, attain = og.comparable_gap(1.0, 10.0, excess_fail=5)
        self.assertIsNone(gap)
        self.assertIsNone(attain)

    def test_zero_excess_fail_keeps_normal_percentage(self):
        gap, attain = og.comparable_gap(10.0, 9.0, excess_fail=0)
        self.assertAlmostEqual(gap, 11.1111111111)
        self.assertAlmostEqual(attain, 90.0)


class TestSplitCsvSchemas(unittest.TestCase):
    EXPECTED = [
        "energy_report_data.csv", "energy_report_params.csv",
        "realism_matrix_data.csv", "realism_matrix_params.csv",
        "l4_task_cycles_data.csv", "l4_task_cycles_params.csv",
        "reslot_cycle_data.csv", "reslot_cycle_summary.csv",
        "scan_g2g4_agg_data.csv", "scan_g2g4_agg_params.csv",
        "rl_probe_data.csv", "rl_probe_summary.csv",
        "plc_evidence.csv",
    ]

    def test_each_generated_csv_has_one_width_and_one_header(self):
        out = os.path.join(SIM, "out")
        for name in self.EXPECTED:
            path = os.path.join(out, name)
            self.assertTrue(os.path.exists(path), name)
            with open(path, encoding="utf-8-sig", newline="") as fp:
                rows = list(csv.reader(fp))
            self.assertGreaterEqual(len(rows), 2, name)
            self.assertEqual(len({len(r) for r in rows}), 1, name)
            self.assertEqual(sum(r == rows[0] for r in rows), 1, name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
