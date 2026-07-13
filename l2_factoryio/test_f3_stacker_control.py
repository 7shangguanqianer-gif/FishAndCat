# -*- coding: utf-8 -*-
"""F3 状态机的离线回归测试；不连接 Factory I/O。"""

import unittest
from unittest.mock import Mock, call, patch

import f3_stacker_control as f3


class SequenceContractTests(unittest.TestCase):
    def make_stacker(self):
        stacker = f3.Stacker.__new__(f3.Stacker)
        stacker.goto = Mock()
        stacker.forks_left = Mock()
        stacker.forks_right = Mock()
        stacker.forks_center = Mock()
        stacker.coil = Mock()
        stacker.wait_motion_cycle = Mock()
        stacker.wait_stable = Mock()
        stacker.box_at_load = Mock(return_value=True)
        return stacker

    def test_pick_uses_left_forks_then_lifts_and_centers(self):
        stacker = self.make_stacker()

        stacker.pick_from_load()

        stacker.goto.assert_called_once_with(f3.POS_REST, "(rest=载入台)")
        stacker.forks_left.assert_called_once_with()
        stacker.forks_right.assert_not_called()
        self.assertEqual(
            stacker.coil.call_args_list,
            [call(f3.C_LIFT, True), call(f3.C_LIFT, False)],
        )
        self.assertEqual(stacker.wait_motion_cycle.call_count, 2)
        stacker.forks_center.assert_called_once_with()

    def test_store_uses_right_forks_then_lowers_and_centers(self):
        stacker = self.make_stacker()

        stacker.store_to(1)

        stacker.goto.assert_called_once_with(1, "(货位 1)")
        stacker.forks_right.assert_called_once_with()
        stacker.forks_left.assert_not_called()
        self.assertEqual(
            stacker.coil.call_args_list,
            [call(f3.C_LIFT, True), call(f3.C_LIFT, False)],
        )
        self.assertEqual(stacker.wait_motion_cycle.call_count, 2)
        stacker.forks_center.assert_called_once_with()

    def test_feed_does_not_run_conveyors_when_load_is_occupied(self):
        stacker = self.make_stacker()
        stacker.box_at_load.return_value = True

        stacker.feed_one_box()

        stacker.coil.assert_not_called()

    def test_store_rejects_non_cell_positions(self):
        stacker = self.make_stacker()

        for invalid in (0, 55, -1, 99):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    stacker.store_to(invalid)

    def test_first_rest_command_allows_idempotent_no_motion(self):
        stacker = self.make_stacker()
        stacker.position_hint = None
        stacker.target = Mock()
        stacker.crane_moving = Mock(return_value=False)

        f3.Stacker.goto(stacker, f3.POS_REST, "rest")

        stacker.wait_motion_cycle.assert_called_once_with(
            f"crane -> {f3.POS_REST}",
            stacker.crane_moving,
            allow_no_start=True,
        )

    def test_action_preflight_rejects_residual_motion(self):
        stacker = self.make_stacker()
        inputs = [False] * len(f3.INPUT_NAMES)
        inputs[f3.IN_AT_MIDDLE] = True
        inputs[f3.IN_MOVING_Z] = True
        stacker.snapshot = Mock(return_value={
            "inputs": inputs,
            "coils": [False] * len(f3.COIL_NAMES),
            "target": 0,
        })

        with self.assertRaisesRegex(RuntimeError, "Moving X/Z"):
            stacker.assert_action_ready()


if __name__ == "__main__":
    unittest.main()
