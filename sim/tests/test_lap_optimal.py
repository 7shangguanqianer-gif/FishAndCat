# -*- coding: utf-8 -*-
"""LAP 完整指派与 fail-closed 边界。"""
import os
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import lap_optimal as lap
import warehouse_sim as ws


def _good(gid, weight=10.0, freq=1.0, vol=0.5):
    return ws.Good(gid, f"G{gid:03d}", weight, freq, vol)


class TestLapCompleteAssignment(unittest.TestCase):
    def test_empty_instance_is_complete_zero_cost(self):
        self.assertEqual(lap.solve_lap([], "sum", "score"), (0.0, []))
        self.assertEqual(lap.solve_lap([], "sum", "exp_t"), (0.0, []))

    def test_invalid_objective_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "unsupported LAP objective"):
            lap.solve_lap([_good(1)], "sum", "unknown")

    def test_explicit_score_normalization_is_used_and_motion_bound_is_checked(self):
        goods = [_good(1, weight=10.0, freq=2.0),
                 _good(2, weight=20.0, freq=4.0)]
        normalization = {
            "w_max": 60.0, "f_max": 100.0,
            "t_max_s": ws.t_max_now(),
        }
        objective, assignment = lap.solve_lap(
            goods, "sum", "score", score_normalization=normalization
        )
        score_fn = ws.make_score_fn(1.0, 0.6, 0.4, 0.15, 60.0, 100.0)
        self.assertAlmostEqual(
            objective, sum(score_fn(good, *slot) for good, slot in assignment), places=12
        )
        bad = dict(normalization, t_max_s=normalization["t_max_s"] + 1.0)
        with self.assertRaisesRegex(ValueError, "active motion model"):
            lap.solve_lap(goods, "sum", "score", score_normalization=bad)

    def test_explicit_score_normalization_fails_closed_when_incomplete(self):
        with self.assertRaisesRegex(ValueError, "contain exactly"):
            lap.solve_lap(
                [_good(1)], "sum", "score",
                score_normalization={"w_max": 60.0, "f_max": 100.0},
            )

    def test_more_goods_than_managed_slots_is_not_partial_success(self):
        capacity = len(lap.free_slots("sum"))
        goods = [_good(index + 1, weight=1.0, vol=0.1)
                 for index in range(capacity + 1)]
        objective, unassigned = lap.solve_lap(goods, "sum", "score")
        self.assertIsNone(objective)
        self.assertEqual(unassigned, 1)

    def test_rectangular_matrix_assigns_every_good_once(self):
        goods = [_good(1), _good(2)]
        objective, assignment = lap.solve_lap(goods, "sum", "exp_t")
        self.assertIsNotNone(objective)
        self.assertEqual([good.gid for good, _ in assignment], [1, 2])
        self.assertEqual(len({slot for _, slot in assignment}), 2)

    def test_exact_managed_capacity_is_complete(self):
        capacity = len(lap.free_slots("sum"))
        goods = [_good(index + 1, weight=1.0, vol=0.1)
                 for index in range(capacity)]
        objective, assignment = lap.solve_lap(goods, "sum", "exp_t")
        self.assertIsNotNone(objective)
        self.assertEqual(len(assignment), capacity)
        self.assertEqual(len({slot for _, slot in assignment}), capacity)

    def test_partial_backend_result_cannot_be_reported_feasible(self):
        goods = [_good(1), _good(2)]
        with mock.patch.object(
                lap, "linear_sum_assignment",
                return_value=(np.array([0]), np.array([0]))):
            objective, unassigned = lap.solve_lap(goods, "sum", "score")
        self.assertIsNone(objective)
        self.assertEqual(unassigned, 1)

    def test_duplicate_slot_backend_result_is_rejected(self):
        goods = [_good(1), _good(2)]
        with mock.patch.object(
                lap, "linear_sum_assignment",
                return_value=(np.array([0, 1]), np.array([0, 0]))):
            with self.assertRaisesRegex(RuntimeError, "invalid complete assignment"):
                lap.solve_lap(goods, "sum", "score")

    def test_mismatched_or_overlong_backend_result_is_rejected(self):
        goods = [_good(1), _good(2)]
        bad_results = [
            (np.array([0, 1]), np.array([0])),
            (np.array([0, 1, 2]), np.array([0, 1, 2])),
        ]
        for result in bad_results:
            with self.subTest(result=result):
                with mock.patch.object(lap, "linear_sum_assignment", return_value=result):
                    with self.assertRaisesRegex(RuntimeError, "invalid complete assignment"):
                        lap.solve_lap(goods, "sum", "score")

    def test_main_refuses_to_overwrite_when_no_comparable_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = os.path.join(tmp, "lap_gap.csv")
            with open(output, "w", encoding="utf-8") as handle:
                handle.write("sentinel\n")
            argv = ["lap_optimal.py", "--seeds", "1", "--scenarios", "tiny_light"]
            with (mock.patch.object(lap, "OUT", tmp),
                  mock.patch.object(sys, "argv", argv),
                  mock.patch.object(lap, "solve_lap", return_value=(None, 1)),
                  mock.patch.object(lap, "awra_objective", return_value=None)):
                with self.assertRaisesRegex(RuntimeError, "refusing to overwrite"):
                    lap.main()
            with open(output, encoding="utf-8") as handle:
                self.assertEqual(handle.read(), "sentinel\n")


if __name__ == "__main__":
    unittest.main()
