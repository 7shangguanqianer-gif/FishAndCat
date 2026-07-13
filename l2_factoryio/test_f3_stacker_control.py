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
        stacker.assert_loaded_transport_ready = Mock()
        return stacker

    def test_pick_uses_left_forks_then_lifts_and_centers(self):
        stacker = self.make_stacker()

        stacker.pick_from_load()

        stacker.goto.assert_called_once_with(f3.POS_REST, "(rest=载入台)")
        stacker.forks_left.assert_called_once_with()
        stacker.forks_right.assert_not_called()
        self.assertEqual(
            stacker.coil.call_args_list,
            [call(f3.C_LIFT, True)],
        )
        self.assertEqual(stacker.wait_motion_cycle.call_count, 1)
        stacker.forks_center.assert_called_once_with()

    def test_store_uses_right_forks_then_lowers_and_centers(self):
        stacker = self.make_stacker()

        stacker.store_to(1)

        stacker.goto.assert_called_once_with(1, "(loaded travel to cell 1)")
        stacker.forks_right.assert_called_once_with()
        stacker.forks_left.assert_not_called()
        self.assertEqual(
            stacker.coil.call_args_list,
            [call(f3.C_LIFT, False)],
        )
        self.assertEqual(stacker.wait_motion_cycle.call_count, 1)
        stacker.forks_center.assert_called_once_with()

    def test_feed_does_not_run_conveyors_when_load_is_occupied(self):
        stacker = self.make_stacker()
        stacker.box_at_load.return_value = True

        stacker.feed_one_box()

        stacker.coil.assert_not_called()

    def test_feed_moves_to_rest_before_starting_conveyors(self):
        stacker = self.make_stacker()
        stacker.box_at_load.return_value = False
        actions = Mock()
        actions.attach_mock(stacker.goto, "goto")
        actions.attach_mock(stacker.coil, "coil")

        with patch("f3_stacker_control.time.sleep"):
            stacker.feed_one_box()

        rest_call = call.goto(f3.POS_REST, "(prepare load station)")
        belt_call = call.coil(f3.C_ENTRY_CONV, True)
        self.assertIn(rest_call, actions.mock_calls)
        self.assertLess(
            actions.mock_calls.index(rest_call),
            actions.mock_calls.index(belt_call),
        )

    def test_feed_stops_belts_before_settle_dwell(self):
        stacker = self.make_stacker()
        stacker.box_at_load.return_value = False

        with patch("f3_stacker_control.time.sleep") as sleep:
            stacker.feed_one_box()

        self.assertEqual(
            stacker.coil.call_args_list[-2:],
            [
                call(f3.C_ENTRY_CONV, False),
                call(f3.C_LOAD_CONV, False),
            ],
        )
        sleep.assert_called_once_with(f3.LOAD_SETTLE_DWELL)
        self.assertEqual(f3.LOAD_SETTLE_DWELL, 2.0)

    def test_feed_rechecks_load_after_settle(self):
        stacker = self.make_stacker()
        stacker.box_at_load.return_value = False

        with patch("f3_stacker_control.time.sleep"):
            stacker.feed_one_box()

        self.assertEqual(stacker.wait_stable.call_count, 2)
        self.assertEqual(
            stacker.wait_stable.call_args_list[-1].args[0],
            "box remains at load after settle",
        )

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

    def test_loaded_transport_gate_rejects_unsafe_state(self):
        stacker = f3.Stacker.__new__(f3.Stacker)
        inputs = [False] * len(f3.INPUT_NAMES)
        inputs[f3.IN_AT_MIDDLE] = True
        inputs[f3.IN_AT_LOAD] = True
        coils = [False] * len(f3.COIL_NAMES)
        coils[f3.C_LIFT] = False
        stacker.snapshot = Mock(return_value={
            "inputs": inputs,
            "coils": coils,
            "target": 0,
        })

        with self.assertRaisesRegex(RuntimeError, "Lift=True"):
            stacker.assert_loaded_transport_ready()

    def test_loaded_transport_gate_accepts_middle_lifted_and_load_clear(self):
        stacker = f3.Stacker.__new__(f3.Stacker)
        inputs = [False] * len(f3.INPUT_NAMES)
        inputs[f3.IN_AT_MIDDLE] = True
        inputs[f3.IN_AT_LOAD] = True
        coils = [False] * len(f3.COIL_NAMES)
        coils[f3.C_LIFT] = True
        stacker.snapshot = Mock(return_value={
            "inputs": inputs,
            "coils": coils,
            "target": 0,
        })

        stacker.assert_loaded_transport_ready()

    def test_travel_checks_loaded_gate_before_motion(self):
        stacker = self.make_stacker()
        stacker.assert_loaded_transport_ready = Mock()

        stacker.travel_loaded_to(30)

        stacker.assert_loaded_transport_ready.assert_called_once_with()
        stacker.goto.assert_called_once_with(30, "(loaded travel to cell 30)")

    def test_pick_does_not_lower_or_sleep_before_loaded_travel(self):
        stacker = self.make_stacker()

        with patch("f3_stacker_control.time.sleep") as sleep:
            stacker.pick_from_load()

        sleep.assert_not_called()
        stacker.coil.assert_called_once_with(f3.C_LIFT, True)

    def test_store_waits_for_load_to_settle_before_forks_center(self):
        stacker = self.make_stacker()

        with patch("f3_stacker_control.time.sleep") as sleep:
            stacker.store_to(1)

        sleep.assert_called_once_with(f3.PLACEMENT_SETTLE_DWELL)
        self.assertEqual(f3.PLACEMENT_SETTLE_DWELL, 1.5)

    def test_diagnostic_feed_stops_after_feed(self):
        stacker = self.make_stacker()
        stacker.feed_one_box = Mock()
        stacker.pick_from_load = Mock()
        stacker.travel_loaded_to = Mock()
        stacker.store_one = Mock()

        stacker.run_diagnostic("feed", 1)

        stacker.feed_one_box.assert_called_once_with()
        stacker.pick_from_load.assert_not_called()
        stacker.travel_loaded_to.assert_not_called()
        stacker.store_one.assert_not_called()

    def test_diagnostic_pick_runs_prerequisites_only(self):
        stacker = self.make_stacker()
        stacker.feed_one_box = Mock()
        stacker.pick_from_load = Mock()
        stacker.travel_loaded_to = Mock()
        stacker.store_one = Mock()

        stacker.run_diagnostic("pick", 1)

        stacker.feed_one_box.assert_called_once_with()
        stacker.pick_from_load.assert_called_once_with()
        stacker.travel_loaded_to.assert_not_called()
        stacker.store_one.assert_not_called()

    def test_diagnostic_travel_runs_pick_then_loaded_travel(self):
        stacker = self.make_stacker()
        stacker.feed_one_box = Mock()
        stacker.pick_from_load = Mock()
        stacker.travel_loaded_to = Mock()
        stacker.store_one = Mock()

        stacker.run_diagnostic("travel", 30)

        stacker.feed_one_box.assert_called_once_with()
        stacker.pick_from_load.assert_called_once_with()
        stacker.travel_loaded_to.assert_called_once_with(30)
        stacker.store_one.assert_not_called()

    def test_diagnostic_store_reuses_full_cycle(self):
        stacker = self.make_stacker()
        stacker.feed_one_box = Mock()
        stacker.pick_from_load = Mock()
        stacker.travel_loaded_to = Mock()
        stacker.store_one = Mock()

        stacker.run_diagnostic("store", 54)

        stacker.store_one.assert_called_once_with(54)
        stacker.feed_one_box.assert_not_called()

    def test_observation_hold_emits_snapshot_and_waits(self):
        stacker = self.make_stacker()
        stacker.print_snapshot = Mock()
        stacker.check_interlocks = Mock()

        with patch("f3_stacker_control.time.sleep") as sleep:
            stacker.observe_phase("G2_PICK", 0.2)

        stacker.print_snapshot.assert_called_once_with("OBSERVE G2_PICK")
        self.assertGreaterEqual(sleep.call_count, 1)

    def test_diagnostic_pick_observes_before_return(self):
        stacker = self.make_stacker()
        stacker.feed_one_box = Mock()
        stacker.pick_from_load = Mock()
        stacker.observe_phase = Mock()

        stacker.run_diagnostic("pick", 1, observe_seconds=20.0)

        stacker.pick_from_load.assert_called_once_with()
        stacker.observe_phase.assert_called_once_with("G2_PICK", 20.0)

    def test_acceptance_cells_cover_near_middle_far_extremes(self):
        self.assertEqual(f3.ACCEPTANCE_CELLS, (1, 30, 54))


if __name__ == "__main__":
    unittest.main()
