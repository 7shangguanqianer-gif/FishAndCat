# -*- coding: utf-8 -*-
"""F3 分层校准控制器的离线回归测试；不连接 Factory I/O。"""

import unittest
from unittest.mock import Mock, call, patch

import f3_stacker_control as f3


class FakeResponse:
    def __init__(self, *, bits=None, registers=None, error=False):
        self.bits = bits or []
        self.registers = registers or []
        self._error = error

    def isError(self):
        return self._error


class ConstructorAndStopTests(unittest.TestCase):
    def test_constructor_connects_without_requiring_run_interlock(self):
        client = Mock()
        client.connect.return_value = True

        stacker = f3.Stacker(client)

        self.assertIs(stacker.c, client)
        client.read_discrete_inputs.assert_not_called()

    def make_stop_stacker(self, load_state):
        stacker = f3.Stacker.__new__(f3.Stacker)
        stacker.load_state = load_state
        stacker.position_hint = 30
        stacker.target = Mock()
        stacker.coil = Mock()
        coils = [False] * len(f3.COIL_NAMES)
        coils[f3.C_LIFT] = True
        stacker.snapshot = Mock(return_value={
            "inputs": [False] * len(f3.INPUT_NAMES),
            "coils": coils,
            "target": 0,
        })
        return stacker

    def test_safe_stop_stops_target_first_and_preserves_lift_while_carrying(self):
        stacker = self.make_stop_stacker(f3.LoadState.CARRYING)
        timeline = Mock()
        timeline.attach_mock(stacker.target, "target")
        timeline.attach_mock(stacker.coil, "coil")

        stacker.safe_stop()

        self.assertEqual(timeline.mock_calls[0], call.target(0))
        self.assertNotIn(call.coil(f3.C_LIFT, False), timeline.mock_calls)
        for address in f3.MOTION_COILS:
            self.assertIn(call.coil(address, False), timeline.mock_calls)

    def test_safe_stop_clears_lift_when_load_is_known_empty(self):
        stacker = self.make_stop_stacker(f3.LoadState.EMPTY)
        stacker.snapshot.return_value["coils"][f3.C_LIFT] = False

        stacker.safe_stop()

        stacker.coil.assert_any_call(f3.C_LIFT, False)

    def test_safe_stop_rejects_false_success_when_readback_is_not_zero(self):
        stacker = self.make_stop_stacker(f3.LoadState.EMPTY)
        stacker.snapshot.return_value["target"] = 30

        with self.assertRaisesRegex(RuntimeError, "readback"):
            stacker.safe_stop()


class SequenceContractTests(unittest.TestCase):
    def make_stacker(self):
        stacker = f3.Stacker.__new__(f3.Stacker)
        stacker.load_state = f3.LoadState.EMPTY
        stacker.position_hint = f3.POS_REST
        stacker.goto = Mock()
        stacker.forks_left = Mock()
        stacker.forks_right = Mock()
        stacker.forks_center = Mock()
        stacker.coil = Mock()
        stacker.wait_motion_cycle = Mock()
        stacker.wait_stable = Mock()
        stacker.wait_for_box_edge = Mock()
        stacker.box_at_load = Mock(return_value=False)
        stacker.assert_loaded_transport_ready = Mock()
        stacker.check_safety_inputs = Mock()
        return stacker

    def test_feed_rejects_preexisting_load_instead_of_bypassing_g1(self):
        stacker = self.make_stacker()
        stacker.box_at_load.return_value = True

        with self.assertRaisesRegex(RuntimeError, "already occupied"):
            stacker.feed_one_box()

        stacker.coil.assert_not_called()

    def test_feed_stops_belts_at_first_sensor_edge_before_settle_check(self):
        stacker = self.make_stacker()
        actions = Mock()
        actions.attach_mock(stacker.wait_for_box_edge, "edge")
        actions.attach_mock(stacker.coil, "coil")
        actions.attach_mock(stacker.wait_stable, "stable")

        with patch("f3_stacker_control.time.sleep"):
            stacker.feed_one_box()

        calls = actions.mock_calls
        edge = calls.index(call.edge())
        stop_entry = calls.index(call.coil(f3.C_ENTRY_CONV, False))
        stop_load = calls.index(call.coil(f3.C_LOAD_CONV, False))
        stable = next(i for i, item in enumerate(calls) if item == call.stable(
            "box stable at load after belts stopped",
            stacker.box_at_load,
            timeout=1.5,
            stable_for=0.30,
        ))
        self.assertLess(edge, stop_entry)
        self.assertLess(stop_entry, stable)
        self.assertLess(stop_load, stable)

    def test_feed_cleans_first_belt_if_second_enable_fails(self):
        stacker = self.make_stacker()
        stacker.coil.side_effect = [None, RuntimeError("second write"), None, None]

        with self.assertRaisesRegex(RuntimeError, "second write"):
            stacker.feed_one_box()

        self.assertEqual(
            stacker.coil.call_args_list,
            [
                call(f3.C_ENTRY_CONV, True),
                call(f3.C_LOAD_CONV, True),
                call(f3.C_ENTRY_CONV, False),
                call(f3.C_LOAD_CONV, False),
            ],
        )

    def test_pick_strict_order_and_sets_carrying_state(self):
        stacker = self.make_stacker()
        stacker.box_at_load.return_value = True
        timeline = Mock()
        timeline.attach_mock(stacker.goto, "goto")
        timeline.attach_mock(stacker.forks_left, "left")
        timeline.attach_mock(stacker.coil, "coil")
        timeline.attach_mock(stacker.wait_motion_cycle, "motion")
        timeline.attach_mock(stacker.wait_stable, "stable")
        timeline.attach_mock(stacker.forks_center, "center")

        stacker.pick_from_load()

        names = [item[0] for item in timeline.mock_calls]
        self.assertLess(names.index("left"), names.index("coil"))
        self.assertLess(names.index("coil"), names.index("motion"))
        self.assertLess(names.index("motion"), names.index("center"))
        self.assertEqual(stacker.load_state, f3.LoadState.CARRYING)

    def test_pick_marks_carrying_before_lift_write_can_fail(self):
        stacker = self.make_stacker()
        stacker.box_at_load.return_value = True
        stacker.coil.side_effect = RuntimeError("lift write failed")

        with self.assertRaisesRegex(RuntimeError, "lift write failed"):
            stacker.pick_from_load()

        self.assertEqual(stacker.load_state, f3.LoadState.CARRYING)

    def test_place_hold_does_not_retract_before_manual_confirmation(self):
        stacker = self.make_stacker()
        stacker.load_state = f3.LoadState.CARRYING
        stacker.position_hint = 30
        stacker.assert_fork_position = Mock()

        with patch("f3_stacker_control.time.sleep"):
            stacker.place_hold(30)

        stacker.forks_right.assert_called_once_with()
        stacker.coil.assert_called_once_with(f3.C_LIFT, False)
        stacker.forks_center.assert_not_called()
        self.assertEqual(stacker.load_state, f3.LoadState.PLACED_PENDING)

    def test_retract_requires_explicit_operator_confirmation(self):
        stacker = self.make_stacker()
        stacker.load_state = f3.LoadState.PLACED_PENDING
        stacker.assert_fork_position = Mock()

        with self.assertRaisesRegex(RuntimeError, "operator confirmation"):
            stacker.retract_after_placement(operator_confirmed=False)

        stacker.forks_center.assert_not_called()

    def test_retract_centers_only_after_confirmation(self):
        stacker = self.make_stacker()
        stacker.load_state = f3.LoadState.PLACED_PENDING
        stacker.assert_fork_position = Mock()

        stacker.retract_after_placement(operator_confirmed=True)

        stacker.assert_fork_position.assert_called_once_with(f3.IN_AT_RIGHT, "Right")
        stacker.forks_center.assert_called_once_with()
        self.assertEqual(stacker.load_state, f3.LoadState.PLACED)

    def test_observation_allows_expected_gui_pause(self):
        stacker = self.make_stacker()
        stacker.print_snapshot = Mock()

        with patch("f3_stacker_control.time.sleep"):
            stacker.observe_phase("G2_PICK", 0.2)

        stacker.check_safety_inputs.assert_called_with(require_running=False)

    def test_travel_diagnostic_does_not_repeat_feed_or_pick(self):
        stacker = self.make_stacker()
        stacker.load_state = f3.LoadState.CARRYING
        stacker.feed_one_box = Mock()
        stacker.pick_from_load = Mock()
        stacker.travel_loaded_to = Mock()
        stacker.observe_phase = Mock()

        stacker.run_diagnostic("travel", 30, observe_seconds=2.0)

        stacker.feed_one_box.assert_not_called()
        stacker.pick_from_load.assert_not_called()
        stacker.travel_loaded_to.assert_called_once_with(30)
        stacker.observe_phase.assert_called_once_with("G3_TRAVEL", 2.0)

    def test_place_and_retract_are_distinct_diagnostic_gates(self):
        stacker = self.make_stacker()
        stacker.load_state = f3.LoadState.CARRYING
        stacker.place_hold = Mock()
        stacker.retract_after_placement = Mock()
        stacker.observe_phase = Mock()

        stacker.run_diagnostic("place", 54, observe_seconds=2.0)

        stacker.place_hold.assert_called_once_with(54)
        stacker.retract_after_placement.assert_not_called()
        stacker.observe_phase.assert_called_once_with("G4_PLACE_HOLD", 2.0)


class ForkAndGateTests(unittest.TestCase):
    def make_stacker(self):
        stacker = f3.Stacker.__new__(f3.Stacker)
        stacker.load_state = f3.LoadState.UNKNOWN
        stacker.position_hint = None
        stacker.din = Mock()
        stacker.coil = Mock()
        stacker.wait_stable = Mock()
        return stacker

    def test_fork_position_rejects_multiple_active_limits(self):
        stacker = self.make_stacker()
        stacker.din.side_effect = lambda addr: addr in (f3.IN_AT_MIDDLE, f3.IN_AT_RIGHT)

        with self.assertRaisesRegex(RuntimeError, "one-hot"):
            stacker.assert_fork_position(f3.IN_AT_MIDDLE, "Middle")

    def test_extend_clears_drive_outputs_after_limit_is_reached(self):
        stacker = self.make_stacker()
        stacker.assert_fork_position = Mock()

        stacker._fork_to("Left", f3.C_FORKS_L, f3.IN_AT_LEFT)

        self.assertEqual(
            stacker.coil.call_args_list[-2:],
            [call(f3.C_FORKS_L, False), call(f3.C_FORKS_R, False)],
        )

    def test_loaded_gate_rejects_conflicting_fork_limits(self):
        stacker = self.make_stacker()
        inputs = [False] * len(f3.INPUT_NAMES)
        inputs[f3.IN_AT_MIDDLE] = True
        inputs[f3.IN_AT_RIGHT] = True
        inputs[f3.IN_AT_LOAD] = True
        coils = [False] * len(f3.COIL_NAMES)
        coils[f3.C_LIFT] = True
        stacker.snapshot = Mock(return_value={"inputs": inputs, "coils": coils, "target": 0})

        with self.assertRaisesRegex(RuntimeError, "one-hot"):
            stacker.assert_loaded_transport_ready()

    def test_resume_carrying_requires_human_visual_confirmation(self):
        stacker = self.make_stacker()
        stacker.assert_loaded_transport_ready = Mock()

        with self.assertRaisesRegex(RuntimeError, "visual confirmation"):
            stacker.resume_carrying(operator_confirmed=False, position=30)

        stacker.assert_loaded_transport_ready.assert_not_called()

    def test_resume_carrying_records_operator_confirmed_position(self):
        stacker = self.make_stacker()
        stacker.assert_loaded_transport_ready = Mock()

        stacker.resume_carrying(operator_confirmed=True, position=30)

        self.assertEqual(stacker.load_state, f3.LoadState.CARRYING)
        self.assertEqual(stacker.position_hint, 30)


class ParserTests(unittest.TestCase):
    def test_diagnostic_phases_are_split_at_manual_gates(self):
        self.assertEqual(
            f3.DIAGNOSTIC_PHASES,
            ("feed", "pick", "travel", "place", "retract"),
        )

    def test_acceptance_cells_cover_near_middle_far_extremes(self):
        self.assertEqual(f3.ACCEPTANCE_CELLS, (1, 30, 54))


if __name__ == "__main__":
    unittest.main()
