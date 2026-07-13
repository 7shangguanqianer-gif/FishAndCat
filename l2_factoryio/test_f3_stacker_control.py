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
        stacker.fork_hold = None
        stacker.target = Mock()
        stacker.coil = Mock()
        inputs = [False] * len(f3.INPUT_NAMES)
        inputs[f3.IN_AT_MIDDLE] = True
        coils = [False] * len(f3.COIL_NAMES)
        coils[f3.C_LIFT] = True
        stacker.snapshot = Mock(return_value={
            "inputs": inputs,
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
        for address in f3.CONVEYOR_COILS:
            self.assertIn(call.coil(address, False), timeline.mock_calls)
        self.assertNotIn(call.coil(f3.C_FORKS_L, False), timeline.mock_calls)
        self.assertNotIn(call.coil(f3.C_FORKS_R, False), timeline.mock_calls)

    def test_safe_stop_preserves_lift_for_recovery_unsafe_load(self):
        stacker = self.make_stop_stacker(f3.LoadState.RECOVERY_UNSAFE)

        stacker.safe_stop()

        self.assertNotIn(call(f3.C_LIFT, False), stacker.coil.call_args_list)

    def test_safe_stop_clears_lift_when_load_is_known_empty(self):
        stacker = self.make_stop_stacker(f3.LoadState.EMPTY)
        stacker.snapshot.return_value["coils"][f3.C_LIFT] = False

        stacker.safe_stop()

        stacker.coil.assert_any_call(f3.C_LIFT, False)

    def test_safe_stop_rejects_false_success_when_readback_is_not_zero(self):
        stacker = self.make_stop_stacker(f3.LoadState.EMPTY)
        stacker.snapshot.return_value["target"] = 30

        with patch.object(f3, "SAFE_STOP_TIMEOUT", 0.0):
            with self.assertRaisesRegex(RuntimeError, "stabilization"):
                stacker.safe_stop()

    def test_safe_stop_preserves_confirmed_right_hold_because_false_retracts(self):
        stacker = self.make_stop_stacker(f3.LoadState.PLACED_PENDING)
        stacker.fork_hold = f3.C_FORKS_R
        stacker.snapshot.return_value["coils"][f3.C_FORKS_R] = True
        stacker.snapshot.return_value["coils"][f3.C_LIFT] = False
        stacker.snapshot.return_value["inputs"][f3.IN_AT_MIDDLE] = False
        stacker.snapshot.return_value["inputs"][f3.IN_AT_RIGHT] = True

        stacker.safe_stop()

        self.assertNotIn(call(f3.C_FORKS_R, False), stacker.coil.call_args_list)
        self.assertNotIn(call(f3.C_FORKS_L, False), stacker.coil.call_args_list)

    def test_place_failure_cleanup_preserves_right_hold_and_does_not_lower(self):
        stacker = self.make_stop_stacker(f3.LoadState.CARRYING)
        stacker.fork_hold = f3.C_FORKS_R
        stacker.snapshot.return_value["coils"][f3.C_FORKS_R] = True
        stacker.snapshot.return_value["coils"][f3.C_LIFT] = False
        stacker.snapshot.return_value["inputs"][f3.IN_AT_MIDDLE] = False
        stacker.snapshot.return_value["inputs"][f3.IN_AT_RIGHT] = True

        stacker.safe_stop()

        self.assertNotIn(call(f3.C_FORKS_R, False), stacker.coil.call_args_list)
        self.assertNotIn(call(f3.C_LIFT, False), stacker.coil.call_args_list)

    def test_snapshot_failure_still_attempts_target_zero_without_fork_writes(self):
        stacker = self.make_stop_stacker(f3.LoadState.UNKNOWN)
        stacker.snapshot.side_effect = RuntimeError("link down")

        with self.assertRaisesRegex(RuntimeError, "fork state ambiguous"):
            stacker.safe_stop(preserve_lift=True)

        stacker.target.assert_called_once_with(0)
        for address in (f3.C_FORKS_L, f3.C_FORKS_R, f3.C_LIFT):
            self.assertNotIn(call(address, False), stacker.coil.call_args_list)
        for address in f3.CONVEYOR_COILS:
            self.assertIn(call(address, False), stacker.coil.call_args_list)

    def test_dual_fork_coils_fail_closed_without_retract_write(self):
        stacker = self.make_stop_stacker(f3.LoadState.UNKNOWN)
        stacker.snapshot.return_value["coils"][f3.C_FORKS_L] = True
        stacker.snapshot.return_value["coils"][f3.C_FORKS_R] = True
        stacker.snapshot.return_value["inputs"][f3.IN_AT_MIDDLE] = False
        stacker.snapshot.return_value["inputs"][f3.IN_AT_RIGHT] = True

        with self.assertRaisesRegex(RuntimeError, "both fork hold coils"):
            stacker.safe_stop(preserve_lift=True)

        self.assertNotIn(call(f3.C_FORKS_L, False), stacker.coil.call_args_list)
        self.assertNotIn(call(f3.C_FORKS_R, False), stacker.coil.call_args_list)

    def test_stale_memory_hold_fails_closed_without_clearing_actual_fork(self):
        stacker = self.make_stop_stacker(f3.LoadState.UNKNOWN)
        stacker.fork_hold = f3.C_FORKS_R
        stacker.snapshot.return_value["coils"][f3.C_FORKS_L] = True
        stacker.snapshot.return_value["inputs"][f3.IN_AT_MIDDLE] = False
        stacker.snapshot.return_value["inputs"][f3.IN_AT_LEFT] = True

        with self.assertRaisesRegex(RuntimeError, "stale fork_hold"):
            stacker.safe_stop(preserve_lift=True)

        self.assertNotIn(call(f3.C_FORKS_L, False), stacker.coil.call_args_list)
        self.assertNotIn(call(f3.C_FORKS_R, False), stacker.coil.call_args_list)


class SequenceContractTests(unittest.TestCase):
    def make_stacker(self):
        stacker = f3.Stacker.__new__(f3.Stacker)
        stacker.load_state = f3.LoadState.EMPTY
        stacker.position_hint = f3.POS_REST
        stacker.fork_hold = None
        stacker.goto = Mock()
        stacker.forks_left_hold = Mock()
        stacker.forks_right_hold = Mock()
        stacker.release_forks_to_middle = Mock()
        stacker.coil = Mock()
        stacker.wait_motion_cycle = Mock()
        stacker.wait_stable = Mock()
        stacker.wait_for_box_edge = Mock()
        stacker.box_at_load = Mock(return_value=False)
        stacker.assert_loaded_transport_ready = Mock()
        stacker.assert_fork_position = Mock()
        stacker.assert_placement_hold_ready = Mock()
        stacker.resume_extended_recovery = Mock()
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
        timeline.attach_mock(stacker.forks_left_hold, "left_hold")
        timeline.attach_mock(stacker.coil, "coil")
        timeline.attach_mock(stacker.wait_motion_cycle, "motion")
        timeline.attach_mock(stacker.wait_stable, "stable")
        timeline.attach_mock(stacker.release_forks_to_middle, "release_middle")

        stacker.pick_from_load()

        names = [item[0] for item in timeline.mock_calls]
        self.assertLess(names.index("left_hold"), names.index("coil"))
        self.assertLess(names.index("coil"), names.index("motion"))
        self.assertLess(names.index("motion"), names.index("release_middle"))
        self.assertEqual(stacker.load_state, f3.LoadState.CARRYING)

    def test_pick_marks_carrying_before_lift_write_can_fail(self):
        stacker = self.make_stacker()
        stacker.box_at_load.return_value = True
        stacker.coil.side_effect = RuntimeError("lift write failed")

        with self.assertRaisesRegex(RuntimeError, "lift write failed"):
            stacker.pick_from_load()

        self.assertEqual(stacker.load_state, f3.LoadState.CARRYING)

    def test_fused_place_hold_is_disabled_with_split_gate_guidance(self):
        stacker = self.make_stacker()
        stacker.load_state = f3.LoadState.CARRYING
        stacker.position_hint = 30

        with self.assertRaisesRegex(RuntimeError, "place-extend"):
            stacker.place_hold(30)

        stacker.forks_right_hold.assert_not_called()
        stacker.coil.assert_not_called()

    def test_place_extend_holds_right_and_never_writes_lift(self):
        stacker = self.make_stacker()
        stacker.load_state = f3.LoadState.CARRYING
        stacker.position_hint = 30

        stacker.place_extend(30)

        stacker.forks_right_hold.assert_called_once_with()
        stacker.coil.assert_not_called()
        stacker.wait_motion_cycle.assert_not_called()
        stacker.release_forks_to_middle.assert_not_called()
        self.assertEqual(stacker.load_state, f3.LoadState.EXTENDED_HOLD)

    def test_place_lower_requires_extended_hold_state(self):
        stacker = self.make_stacker()
        stacker.load_state = f3.LoadState.CARRYING
        stacker.position_hint = 30

        with self.assertRaisesRegex(RuntimeError, "EXTENDED_HOLD"):
            stacker.place_lower(30)

        stacker.coil.assert_not_called()

    def test_place_lower_lowers_with_real_z_and_keeps_right_hold(self):
        stacker = self.make_stacker()
        stacker.load_state = f3.LoadState.EXTENDED_HOLD
        stacker.position_hint = 30
        with patch("f3_stacker_control.time.sleep"):
            stacker.place_lower(30)

        stacker.assert_fork_position.assert_called_once_with(f3.IN_AT_RIGHT, "Right")
        stacker.coil.assert_called_once_with(f3.C_LIFT, False)
        self.assertEqual(stacker.wait_motion_cycle.call_args.args[0], "lower load")
        stacker.release_forks_to_middle.assert_not_called()
        stacker.assert_placement_hold_ready.assert_called_once_with()
        self.assertEqual(stacker.load_state, f3.LoadState.PLACED_PENDING)

    def test_place_lower_no_z_with_failed_selfcheck_records_persistent_fault(self):
        stacker = self.make_stacker()
        stacker.load_state = f3.LoadState.EXTENDED_HOLD
        stacker.position_hint = 30
        stacker.wait_motion_cycle.side_effect = RuntimeError(
            "NO START(3.0s): lower load"
        )
        stacker._zero_drop_hold_confirmed = Mock(return_value=False)

        with patch("f3_stacker_control.fault_lock.record_fault") as record:
            with self.assertRaisesRegex(RuntimeError, "NO START"):
                stacker.place_lower(30)

        record.assert_called_once()
        self.assertEqual(
            record.call_args.args[0], f3.fault_lock.FAULT_LIFT_POSITION_UNKNOWN
        )
        self.assertEqual(record.call_args.kwargs["cell"], 30)

    def test_place_lower_no_z_with_stable_site_enters_lower_stalled(self):
        """0713 根因语义：零行程停驻=疑似放置成功，保持现场不落锁。"""
        stacker = self.make_stacker()
        stacker.load_state = f3.LoadState.EXTENDED_HOLD
        stacker.position_hint = 30
        stacker.wait_motion_cycle.side_effect = RuntimeError(
            "NO START(3.0s): lower load"
        )
        stacker._zero_drop_hold_confirmed = Mock(return_value=True)

        with patch("f3_stacker_control.fault_lock.record_fault") as record:
            stacker.place_lower(30)  # 不应 raise

        record.assert_not_called()
        self.assertEqual(stacker.load_state, f3.LoadState.LOWER_STALLED)
        stacker.coil.assert_called_once_with(f3.C_LIFT, False)
        stacker.release_forks_to_middle.assert_not_called()

    def test_zero_drop_selfcheck_truth_table(self):
        stacker = f3.Stacker.__new__(f3.Stacker)

        def snap(fork_bits=(False, False, True), moving=(False, False),
                 c2=False, c3=True, lift=False, target=0):
            inputs = [False] * len(f3.INPUT_NAMES)
            inputs[f3.IN_AT_LEFT], inputs[f3.IN_AT_MIDDLE], inputs[f3.IN_AT_RIGHT] = fork_bits
            inputs[f3.IN_MOVING_X], inputs[f3.IN_MOVING_Z] = moving
            coils = [False] * len(f3.COIL_NAMES)
            coils[f3.C_FORKS_L], coils[f3.C_FORKS_R], coils[f3.C_LIFT] = c2, c3, lift
            return {"inputs": inputs, "coils": coils, "target": target}

        stacker.snapshot = Mock(return_value=snap())
        self.assertTrue(stacker._zero_drop_hold_confirmed())
        for bad in (
            snap(fork_bits=(False, True, False)),      # 叉不在 Right
            snap(moving=(False, True)),                 # 仍在动
            snap(c3=False),                             # 保持丢失
            snap(c2=True),                              # 双叉
            snap(lift=True),                            # Lift 命令未落
            snap(target=30),                            # Target 未清
        ):
            stacker.snapshot = Mock(return_value=bad)
            self.assertFalse(stacker._zero_drop_hold_confirmed())
        stacker.snapshot = Mock(side_effect=RuntimeError("link down"))
        self.assertFalse(stacker._zero_drop_hold_confirmed())

    def test_retract_requires_explicit_operator_confirmation(self):
        stacker = self.make_stacker()
        stacker.load_state = f3.LoadState.PLACED_PENDING
        with self.assertRaisesRegex(RuntimeError, "operator confirmation"):
            stacker.retract_after_placement(operator_confirmed=False)

        stacker.release_forks_to_middle.assert_not_called()

    def test_retract_centers_only_after_confirmation(self):
        stacker = self.make_stacker()
        stacker.load_state = f3.LoadState.PLACED_PENDING
        stacker.retract_after_placement(operator_confirmed=True)

        stacker.assert_fork_position.assert_called_once_with(f3.IN_AT_RIGHT, "Right")
        stacker.release_forks_to_middle.assert_called_once_with()
        self.assertEqual(stacker.load_state, f3.LoadState.PLACED)

    def test_recover_place_lift_preserves_right_hold_and_never_retracts(self):
        stacker = self.make_stacker()
        stacker.load_state = f3.LoadState.CARRYING
        stacker.position_hint = 1
        stacker.din = Mock(return_value=False)

        with patch.object(f3, "START_TIMEOUT", 0.0):
            stacker.recover_place_hold_lift(1)

        stacker.coil.assert_called_once_with(f3.C_LIFT, True)
        stacker.release_forks_to_middle.assert_not_called()
        stacker.resume_extended_recovery.assert_called_once_with(
            operator_confirmed=True,
            position=1,
            expected_lift=True,
        )

    @patch("f3_stacker_control.fault_lock.record_fault")
    def test_recover_place_retract_requires_raised_gate_before_centering(self, record):
        stacker = self.make_stacker()
        stacker.load_state = f3.LoadState.CARRYING
        stacker.position_hint = 30
        timeline = Mock()
        timeline.attach_mock(stacker.resume_extended_recovery, "gate")
        timeline.attach_mock(stacker.release_forks_to_middle, "center")

        stacker.recover_place_hold_retract(30)

        self.assertLess(
            timeline.mock_calls.index(call.gate(
                operator_confirmed=True,
                position=30,
                expected_lift=True,
            )),
            timeline.mock_calls.index(call.center()),
        )
        stacker.assert_loaded_transport_ready.assert_called_once_with()
        record.assert_called_once()
        self.assertEqual(stacker.load_state, f3.LoadState.RECOVERY_UNSAFE)

    def test_relift_only_raises_lift_and_keeps_position(self):
        stacker = self.make_stacker()
        stacker.load_state = f3.LoadState.CARRYING
        stacker.position_hint = 1

        stacker.relift_carried_load(1)

        stacker.assert_fork_position.assert_called_once_with(f3.IN_AT_MIDDLE, "Middle")
        stacker.coil.assert_called_once_with(f3.C_LIFT, True)
        stacker.wait_motion_cycle.assert_called_once()
        self.assertEqual(
            stacker.wait_motion_cycle.call_args.args[0], "relift carried load"
        )
        stacker.goto.assert_not_called()
        stacker.forks_left_hold.assert_not_called()
        stacker.forks_right_hold.assert_not_called()

    def test_observation_allows_expected_gui_pause(self):
        stacker = self.make_stacker()
        stacker.print_snapshot = Mock()

        with patch("f3_stacker_control.time.sleep"):
            stacker.observe_phase("G2_PICK", 0.2)

        stacker.check_safety_inputs.assert_called_with(require_running=False)

    def test_pick_diagnostic_reuses_only_confirmed_staged_box(self):
        stacker = self.make_stacker()
        stacker.box_at_load.return_value = True
        stacker.feed_one_box = Mock()
        stacker.pick_from_load = Mock()
        stacker.observe_phase = Mock()

        stacker.run_diagnostic(
            "pick", 1, observe_seconds=2.0, cargo_confirmed=True
        )

        stacker.feed_one_box.assert_not_called()
        stacker.pick_from_load.assert_called_once_with()
        stacker.observe_phase.assert_called_once_with("G2_PICK", 2.0)

    def test_pick_diagnostic_rejects_unconfirmed_staged_box(self):
        stacker = self.make_stacker()
        stacker.box_at_load.return_value = True
        stacker.feed_one_box = Mock()
        stacker.pick_from_load = Mock()

        with self.assertRaisesRegex(RuntimeError, "--confirm-cargo required"):
            stacker.run_diagnostic("pick", 1)

        stacker.feed_one_box.assert_not_called()
        stacker.pick_from_load.assert_not_called()

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

    def test_fused_place_diagnostic_raises_split_guidance(self):
        stacker = self.make_stacker()
        stacker.load_state = f3.LoadState.CARRYING
        stacker.retract_after_placement = Mock()
        stacker.observe_phase = Mock()

        with self.assertRaisesRegex(ValueError, "invalid diagnostic phase"):
            stacker.run_diagnostic("place", 54, observe_seconds=2.0)

        stacker.retract_after_placement.assert_not_called()
        stacker.observe_phase.assert_not_called()

    def test_place_extend_and_lower_are_distinct_diagnostic_gates(self):
        stacker = self.make_stacker()
        stacker.load_state = f3.LoadState.CARRYING
        stacker.place_extend = Mock()
        stacker.place_lower = Mock()
        stacker.retract_after_placement = Mock()
        stacker.observe_phase = Mock()

        stacker.run_diagnostic("place-extend", 54, observe_seconds=2.0)
        stacker.place_extend.assert_called_once_with(54)
        stacker.place_lower.assert_not_called()
        stacker.observe_phase.assert_called_once_with("G4_PLACE_EXTEND_HOLD", 2.0)

        stacker.observe_phase.reset_mock()
        stacker.run_diagnostic("place-lower", 54, observe_seconds=1.0)
        stacker.place_lower.assert_called_once_with(54)
        stacker.retract_after_placement.assert_not_called()
        stacker.observe_phase.assert_called_once_with("G4_PLACE_LOWER_HOLD", 1.0)


class ForkAndGateTests(unittest.TestCase):
    def make_stacker(self):
        stacker = f3.Stacker.__new__(f3.Stacker)
        stacker.load_state = f3.LoadState.UNKNOWN
        stacker.position_hint = None
        stacker.fork_hold = None
        stacker.din = Mock()
        stacker.coil = Mock()
        stacker.wait_stable = Mock()
        return stacker

    def test_fork_position_rejects_multiple_active_limits(self):
        stacker = self.make_stacker()
        stacker.din.side_effect = lambda addr: addr in (f3.IN_AT_MIDDLE, f3.IN_AT_RIGHT)

        with self.assertRaisesRegex(RuntimeError, "one-hot"):
            stacker.assert_fork_position(f3.IN_AT_MIDDLE, "Middle")

    def test_box_at_load_uses_active_low_sensor_polarity(self):
        stacker = self.make_stacker()
        stacker.din.return_value = False
        self.assertTrue(stacker.box_at_load())

    def test_reset_empty_scene_preflight_rejects_any_active_low_cargo_sensor(self):
        stacker = self.make_stacker()
        inputs = [False] * len(f3.INPUT_NAMES)
        inputs[f3.IN_AT_MIDDLE] = True
        for address in (f3.IN_AT_ENTRY, f3.IN_AT_LOAD, f3.IN_AT_UNLOAD, f3.IN_AT_EXIT):
            inputs[address] = True
        inputs[f3.IN_AT_LOAD] = False  # active-low: 载入位有货
        coils = [False] * len(f3.COIL_NAMES)
        stacker.snapshot = Mock(return_value={
            "inputs": inputs,
            "coils": coils,
            "target": 0,
        })

        with self.assertRaisesRegex(RuntimeError, "cargo sensors occupied=At Load"):
            stacker.assert_action_ready(require_empty_scene=True)

    def test_non_reset_preflight_does_not_mislabel_staged_pick_as_empty_scene(self):
        stacker = self.make_stacker()
        inputs = [False] * len(f3.INPUT_NAMES)
        inputs[f3.IN_AT_MIDDLE] = True
        inputs[f3.IN_AT_LOAD] = False
        coils = [False] * len(f3.COIL_NAMES)
        stacker.snapshot = Mock(return_value={
            "inputs": inputs,
            "coils": coils,
            "target": 0,
        })

        stacker.assert_action_ready(require_empty_scene=False)

    def test_extended_recovery_gate_records_right_hold_and_carrying(self):
        stacker = self.make_stacker()
        inputs = [False] * len(f3.INPUT_NAMES)
        inputs[f3.IN_AT_RIGHT] = True
        coils = [False] * len(f3.COIL_NAMES)
        coils[f3.C_FORKS_R] = True
        coils[f3.C_LIFT] = True
        stacker.snapshot = Mock(return_value={
            "inputs": inputs,
            "coils": coils,
            "target": 0,
        })

        stacker.resume_extended_recovery(
            operator_confirmed=True,
            position=30,
            expected_lift=True,
        )

        self.assertEqual(stacker.load_state, f3.LoadState.CARRYING)
        self.assertEqual(stacker.position_hint, 30)
        self.assertEqual(stacker.fork_hold, f3.C_FORKS_R)

    def test_extended_recovery_gate_rejects_wrong_lift_state(self):
        stacker = self.make_stacker()
        inputs = [False] * len(f3.INPUT_NAMES)
        inputs[f3.IN_AT_RIGHT] = True
        coils = [False] * len(f3.COIL_NAMES)
        coils[f3.C_FORKS_R] = True
        stacker.snapshot = Mock(return_value={
            "inputs": inputs,
            "coils": coils,
            "target": 0,
        })

        with self.assertRaisesRegex(RuntimeError, "Lift=False"):
            stacker.resume_extended_recovery(
                operator_confirmed=True,
                position=1,
                expected_lift=True,
            )
        stacker.din.return_value = True
        self.assertFalse(stacker.box_at_load())

    def test_extend_keeps_selected_output_asserted_after_limit_is_reached(self):
        stacker = self.make_stacker()
        stacker.assert_fork_position = Mock()

        stacker._fork_to_hold("Left", f3.C_FORKS_L, f3.IN_AT_LEFT)

        self.assertEqual(
            stacker.coil.call_args_list,
            [call(f3.C_FORKS_R, False), call(f3.C_FORKS_L, True)],
        )
        self.assertEqual(stacker.fork_hold, f3.C_FORKS_L)

    def test_right_extend_keeps_right_output_asserted(self):
        stacker = self.make_stacker()
        stacker.assert_fork_position = Mock()

        stacker._fork_to_hold("Right", f3.C_FORKS_R, f3.IN_AT_RIGHT)

        self.assertEqual(
            stacker.coil.call_args_list,
            [call(f3.C_FORKS_L, False), call(f3.C_FORKS_R, True)],
        )
        self.assertEqual(stacker.fork_hold, f3.C_FORKS_R)

    def test_extend_failure_releases_both_outputs(self):
        stacker = self.make_stacker()
        stacker.assert_fork_position = Mock()
        stacker.wait_stable.side_effect = RuntimeError("limit timeout")

        with self.assertRaisesRegex(RuntimeError, "limit timeout"):
            stacker._fork_to_hold("Right", f3.C_FORKS_R, f3.IN_AT_RIGHT)

        self.assertEqual(
            stacker.coil.call_args_list[-2:],
            [call(f3.C_FORKS_L, False), call(f3.C_FORKS_R, False)],
        )
        self.assertIsNone(stacker.fork_hold)

    def test_release_to_middle_never_writes_true(self):
        stacker = self.make_stacker()
        stacker._read_fork_bits = Mock(return_value=(False, False, True))
        stacker.fork_hold = f3.C_FORKS_R

        stacker.release_forks_to_middle()

        self.assertTrue(stacker.coil.call_args_list)
        self.assertTrue(all(item.args[1] is False for item in stacker.coil.call_args_list))
        self.assertIsNone(stacker.fork_hold)

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

    def test_resume_lowered_carrying_requires_exact_recovery_snapshot(self):
        stacker = self.make_stacker()
        inputs = [False] * len(f3.INPUT_NAMES)
        inputs[f3.IN_AT_MIDDLE] = True
        inputs[f3.IN_AT_LOAD] = True
        coils = [False] * len(f3.COIL_NAMES)
        stacker.snapshot = Mock(return_value={"inputs": inputs, "coils": coils, "target": 0})

        stacker.resume_lowered_carrying(operator_confirmed=True, position=1)

        self.assertEqual(stacker.load_state, f3.LoadState.CARRYING)
        self.assertEqual(stacker.position_hint, 1)

    def test_resume_lowered_carrying_rejects_lift_already_true(self):
        stacker = self.make_stacker()
        inputs = [False] * len(f3.INPUT_NAMES)
        inputs[f3.IN_AT_MIDDLE] = True
        inputs[f3.IN_AT_LOAD] = True
        coils = [False] * len(f3.COIL_NAMES)
        coils[f3.C_LIFT] = True
        stacker.snapshot = Mock(return_value={"inputs": inputs, "coils": coils, "target": 0})

        with self.assertRaisesRegex(RuntimeError, "Lift must be False"):
            stacker.resume_lowered_carrying(operator_confirmed=True, position=1)


class MainCleanupTests(unittest.TestCase):
    def test_successful_place_extend_preserves_right_hold(self):
        stacker = Mock()

        f3._finish_diagnostic(stacker, "place-extend")

        stacker.safe_stop.assert_not_called()

    def test_successful_place_lower_preserves_right_hold(self):
        stacker = Mock()

        f3._finish_diagnostic(stacker, "place-lower")

        stacker.safe_stop.assert_not_called()

    def test_successful_relift_performs_no_cleanup_writes(self):
        stacker = Mock()

        f3._finish_diagnostic(stacker, "relift")

        stacker.safe_stop.assert_not_called()

    def test_successful_recover_lift_preserves_right_hold(self):
        stacker = Mock()

        f3._finish_diagnostic(stacker, "recover-lift")

        stacker.safe_stop.assert_not_called()

    def test_other_successful_phase_runs_safe_stop(self):
        stacker = Mock()

        f3._finish_diagnostic(stacker, "travel")

        stacker.safe_stop.assert_called_once_with()


class ParserTests(unittest.TestCase):
    def test_diagnostic_phases_are_split_at_manual_gates(self):
        self.assertEqual(
            f3.DIAGNOSTIC_PHASES,
            ("feed", "pick", "travel", "place-extend", "place-lower", "retract"),
        )

    def test_acceptance_cells_cover_near_middle_far_extremes(self):
        self.assertEqual(f3.ACCEPTANCE_CELLS, (1, 30, 54))

    def test_travel_current_position_is_recorded_for_fresh_known_origin(self):
        args = f3.build_parser().parse_args([
            "diagnose", "travel", "30",
            "--current-position", "1",
            "--confirm-cargo",
            "--confirm-position",
        ])
        stacker = Mock()

        f3._prepare_diagnostic(stacker, args)

        stacker.resume_carrying.assert_called_once_with(
            operator_confirmed=True,
            position=1,
        )

    @patch("f3_stacker_control.fault_lock.require_last_phase")
    def test_place_extend_requires_persisted_travel_chain(self, require_phase):
        args = f3.build_parser().parse_args([
            "diagnose", "place-extend", "30", "--confirm-cargo", "--confirm-position",
        ])
        stacker = Mock()
        f3._prepare_diagnostic(stacker, args)
        require_phase.assert_called_once_with(
            "travel",
            cell=30,
            load_state_value=f3.LoadState.CARRYING.value,
            lift_command=True,
        )

    @patch("f3_stacker_control.fault_lock.require_last_phase")
    def test_place_lower_requires_persisted_extend_chain(self, require_phase):
        args = f3.build_parser().parse_args([
            "diagnose", "place-lower", "30", "--confirm-position", "--confirm-clearance",
        ])
        stacker = Mock()
        f3._prepare_diagnostic(stacker, args)
        require_phase.assert_called_once_with(
            "place-extend",
            cell=30,
            load_state_value=f3.LoadState.EXTENDED_HOLD.value,
            fork_hold=f3.C_FORKS_R,
            lift_command=True,
        )

    @patch("f3_stacker_control.fault_lock.require_last_phase")
    @patch("f3_stacker_control.fault_lock.load_state")
    def test_retract_requires_persisted_lower_chain(self, load_state, require_phase):
        load_state.return_value = {
            "last_phase": {
                "phase": "place-lower",
                "load_state": f3.LoadState.PLACED_PENDING.value,
            },
        }
        args = f3.build_parser().parse_args([
            "diagnose", "retract", "30", "--confirm-position", "--confirm-placement",
        ])
        stacker = Mock()
        f3._prepare_diagnostic(stacker, args)
        require_phase.assert_called_once_with(
            "place-lower",
            cell=30,
            load_state_value=f3.LoadState.PLACED_PENDING.value,
            fork_hold=f3.C_FORKS_R,
            lift_command=False,
        )

    @patch("f3_stacker_control.fault_lock.require_last_phase")
    @patch("f3_stacker_control.fault_lock.load_state")
    def test_retract_accepts_zero_drop_lower_stalled_chain(self, load_state, require_phase):
        """0713 根因：place-lower 零行程停驻后 retract 必须可达（人工视觉门裁决）。"""
        load_state.return_value = {
            "last_phase": {
                "phase": "place-lower",
                "load_state": f3.LoadState.LOWER_STALLED.value,
            },
        }
        args = f3.build_parser().parse_args([
            "diagnose", "retract", "30", "--confirm-position", "--confirm-placement",
        ])
        stacker = Mock()
        f3._prepare_diagnostic(stacker, args)
        require_phase.assert_called_once_with(
            "place-lower",
            cell=30,
            load_state_value=f3.LoadState.LOWER_STALLED.value,
            fork_hold=f3.C_FORKS_R,
            lift_command=False,
        )

    @patch("f3_stacker_control.fault_lock.require_last_phase")
    @patch("f3_stacker_control.fault_lock.load_state")
    def test_retract_rejects_other_persisted_load_states(self, load_state, require_phase):
        load_state.return_value = {
            "last_phase": {
                "phase": "place-lower",
                "load_state": f3.LoadState.EXTENDED_HOLD.value,
            },
        }
        args = f3.build_parser().parse_args([
            "diagnose", "retract", "30", "--confirm-position", "--confirm-placement",
        ])
        with self.assertRaisesRegex(RuntimeError, "placed_pending/lower_stalled"):
            f3._prepare_diagnostic(Mock(), args)
        require_phase.assert_not_called()

    def test_reset_epoch_requires_visual_emitter_and_traceable_note(self):
        stacker = Mock()
        args = f3.build_parser().parse_args([
            "reset-epoch", "--operator-confirmed-restart",
        ])
        with self.assertRaisesRegex(RuntimeError, "visual-empty"):
            f3._run_reset_epoch(stacker, args)

    @patch("f3_stacker_control.fault_lock.clear_for_new_epoch")
    def test_reset_epoch_runs_cargo_aware_preflight_and_records_manual_boundary(self, clear):
        clear.return_value = {
            "epoch_started_at": "2026-07-13T00:00:00",
            "cleared_fault": None,
        }
        stacker = Mock(unsafe=True)
        args = f3.build_parser().parse_args([
            "reset-epoch",
            "--operator-confirmed-restart",
            "--confirm-visual-empty",
            "--confirm-emitter-off",
            "--note", "img/empty.png",
        ])
        f3._run_reset_epoch(stacker, args)
        stacker.assert_action_ready.assert_called_once_with(require_empty_scene=True)
        clear.assert_called_once_with(
            operator_confirmed_restart=True,
            preflight_passed=True,
            visual_empty_confirmed=True,
            emitter_off_confirmed=True,
            note="img/empty.png",
        )


if __name__ == "__main__":
    unittest.main()
