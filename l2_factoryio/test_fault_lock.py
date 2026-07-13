# -*- coding: utf-8 -*-
"""H1 门2/门3 回归：持久故障锁跨进程语义 + 负载感知 stop 重建。"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, call

import fault_lock
import f3_stacker_control as f3


class FaultLockFileTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "fault_state.json"

    def tearDown(self):
        self._tmp.cleanup()

    def test_record_fault_locks_and_survives_reload(self):
        fault_lock.record_fault(
            fault_lock.FAULT_LIFT_POSITION_UNKNOWN,
            cell=30, detail="no Z", path=self.path,
        )

        state = fault_lock.load_state(self.path)
        self.assertTrue(fault_lock.is_locked(state))
        self.assertEqual(state["fault"]["code"], "LIFT_POSITION_UNKNOWN")
        self.assertFalse(state["cargo_trust"])

    def test_unknown_fault_code_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown fault code"):
            fault_lock.record_fault("TYPO_CODE", cell=1, detail="x", path=self.path)

    def test_missing_file_is_unlocked(self):
        self.assertFalse(fault_lock.is_locked(fault_lock.load_state(self.path)))

    def test_corrupt_file_is_treated_as_locked(self):
        self.path.write_text("{not json", encoding="utf-8")

        state = fault_lock.load_state(self.path)
        self.assertTrue(fault_lock.is_locked(state))
        self.assertIn("corrupt", fault_lock.lock_reason(state))

    def test_phase_state_write_does_not_clear_fault(self):
        fault_lock.record_fault(
            fault_lock.FAULT_RECOVERY_UNSAFE,
            cell=1, detail="drop", path=self.path,
        )
        fault_lock.record_phase_state(
            phase="stop", cell=None, load_state_value="unknown",
            fork_hold=None, lift_command=None, path=self.path,
        )

        state = fault_lock.load_state(self.path)
        self.assertTrue(fault_lock.is_locked(state))
        self.assertEqual(state["last_phase"]["phase"], "stop")

    def test_clear_requires_operator_confirmed_restart(self):
        fault_lock.record_fault(
            fault_lock.FAULT_CARGO_LOST, cell=30, detail="drop", path=self.path,
        )
        with self.assertRaisesRegex(RuntimeError, "FULL"):
            fault_lock.clear_for_new_epoch(
                operator_confirmed_restart=False,
                preflight_passed=True,
                path=self.path,
            )
        self.assertTrue(fault_lock.is_locked(fault_lock.load_state(self.path)))

    def test_clear_requires_passing_preflight(self):
        fault_lock.record_fault(
            fault_lock.FAULT_CARGO_LOST, cell=30, detail="drop", path=self.path,
        )
        with self.assertRaisesRegex(RuntimeError, "preflight"):
            fault_lock.clear_for_new_epoch(
                operator_confirmed_restart=True,
                preflight_passed=False,
                path=self.path,
            )
        self.assertTrue(fault_lock.is_locked(fault_lock.load_state(self.path)))

    def test_clear_with_both_conditions_unlocks_and_keeps_audit(self):
        fault_lock.record_fault(
            fault_lock.FAULT_CARGO_LOST, cell=30, detail="drop", path=self.path,
        )
        state = fault_lock.clear_for_new_epoch(
            operator_confirmed_restart=True,
            preflight_passed=True,
            note="full restart 0713",
            path=self.path,
        )

        self.assertFalse(fault_lock.is_locked(state))
        self.assertEqual(state["cleared_fault"]["code"], "CARGO_LOST")
        reloaded = fault_lock.load_state(self.path)
        self.assertFalse(fault_lock.is_locked(reloaded))


class CliBypassGuardTests(unittest.TestCase):
    """CLI 新进程带任何 --confirm-* 旗标都不得绕过持久锁。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "fault_state.json"
        self._orig_default = fault_lock.default_state_path
        fault_lock.default_state_path = lambda: self.path

    def tearDown(self):
        fault_lock.default_state_path = self._orig_default
        self._tmp.cleanup()

    def test_locked_state_blocks_diagnose_even_with_confirm_flags(self):
        fault_lock.record_fault(
            fault_lock.FAULT_RECOVERY_UNSAFE, cell=1, detail="x", path=self.path,
        )

        with self.assertRaisesRegex(RuntimeError, "PERSISTENT FAULT LOCK"):
            f3._assert_unlocked_for_action("diagnose")

    def test_locked_state_blocks_probe_demo_accept(self):
        fault_lock.record_fault(
            fault_lock.FAULT_LIFT_POSITION_UNKNOWN, cell=1, detail="x",
            path=self.path,
        )
        for mode in ("probe", "demo", "accept"):
            with self.assertRaises(RuntimeError):
                f3._assert_unlocked_for_action(mode)

    def test_locked_state_allows_evidence_and_unlock_modes(self):
        fault_lock.record_fault(
            fault_lock.FAULT_LOWER_NO_START, cell=1, detail="x", path=self.path,
        )
        for mode in ("snapshot", "stop", "mark-fault", "reset-epoch"):
            f3._assert_unlocked_for_action(mode)  # 不应抛

    def test_unlocked_state_allows_diagnose(self):
        f3._assert_unlocked_for_action("diagnose")  # 不应抛


class StopForkHoldRebuildTests(unittest.TestCase):
    """H1 门3：新进程 stop 必须从线圈读回重建叉保持，拒绝盲目回中。"""

    def make_fresh_process_stacker(self, coils):
        stacker = f3.Stacker.__new__(f3.Stacker)
        stacker.load_state = f3.LoadState.UNKNOWN
        stacker.position_hint = None
        stacker.fork_hold = None  # 新进程内存状态
        stacker.target = Mock()
        stacker.coil = Mock()
        stacker.snapshot = Mock(return_value={
            "inputs": [False] * len(f3.INPUT_NAMES),
            "coils": list(coils),
            "target": 0,
        })
        return stacker

    def test_stop_rebuilds_right_hold_from_coil_readback(self):
        coils = [False] * len(f3.COIL_NAMES)
        coils[f3.C_FORKS_R] = True
        coils[f3.C_LIFT] = True
        stacker = self.make_fresh_process_stacker(coils)

        stacker.safe_stop(preserve_lift=True)

        self.assertEqual(stacker.fork_hold, f3.C_FORKS_R)
        self.assertNotIn(
            call(f3.C_FORKS_R, False), stacker.coil.call_args_list
        )
        self.assertIn(call(f3.C_FORKS_L, False), stacker.coil.call_args_list)
        self.assertNotIn(call(f3.C_LIFT, False), stacker.coil.call_args_list)

    def test_stop_rebuilds_left_hold_from_coil_readback(self):
        coils = [False] * len(f3.COIL_NAMES)
        coils[f3.C_FORKS_L] = True
        stacker = self.make_fresh_process_stacker(coils)

        stacker.safe_stop(preserve_lift=True)

        self.assertEqual(stacker.fork_hold, f3.C_FORKS_L)
        self.assertNotIn(
            call(f3.C_FORKS_L, False), stacker.coil.call_args_list
        )

    def test_stop_aborts_if_fork_readback_unavailable(self):
        stacker = f3.Stacker.__new__(f3.Stacker)
        stacker.load_state = f3.LoadState.UNKNOWN
        stacker.position_hint = None
        stacker.fork_hold = None
        stacker.target = Mock()
        stacker.coil = Mock()
        stacker.snapshot = Mock(side_effect=RuntimeError("link down"))

        with self.assertRaisesRegex(RuntimeError, "blind retract"):
            stacker.safe_stop(preserve_lift=True)

        stacker.coil.assert_not_called()


if __name__ == "__main__":
    unittest.main()
