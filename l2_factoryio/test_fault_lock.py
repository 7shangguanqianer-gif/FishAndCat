# -*- coding: utf-8 -*-
"""H1.1：fail-closed 状态、命令租约、事务 pending 与保守 stop 回归。"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, call, patch

import fault_lock
import f3_stacker_control as f3


def initialize_epoch(path: Path) -> dict:
    with fault_lock.command_guard("reset-epoch", path=path):
        return fault_lock.clear_for_new_epoch(
            operator_confirmed_restart=True,
            preflight_passed=True,
            visual_empty_confirmed=True,
            emitter_off_confirmed=True,
            note="test evidence",
            path=path,
        )


class FaultLockFileTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "fault_state.json"

    def tearDown(self):
        self._tmp.cleanup()

    def test_missing_file_is_fail_closed(self):
        state = fault_lock.load_state(self.path)
        self.assertTrue(fault_lock.is_locked(state))
        self.assertIn("missing", fault_lock.lock_reason(state))

    def test_old_or_partial_schema_is_fail_closed(self):
        for payload in (
            {"cargo_trust": False},
            {"fault": {}},
            {"schema_version": 1, "revision": 0, "cargo_trust": True},
        ):
            self.path.write_text(json.dumps(payload), encoding="utf-8")
            self.assertTrue(fault_lock.is_locked(fault_lock.load_state(self.path)))

    def test_valid_schema_with_untrusted_cargo_is_locked(self):
        self.path.write_text(
            json.dumps({
                "schema_version": fault_lock.STATE_SCHEMA_VERSION,
                "revision": 0,
                "cargo_trust": False,
            }),
            encoding="utf-8",
        )
        state = fault_lock.load_state(self.path)
        self.assertTrue(fault_lock.is_locked(state))
        self.assertIn("cargo_trust", fault_lock.lock_reason(state))

    def test_corrupt_file_is_treated_as_locked(self):
        self.path.write_text("{not json", encoding="utf-8")
        state = fault_lock.load_state(self.path)
        self.assertTrue(fault_lock.is_locked(state))
        self.assertIn("corrupt", fault_lock.lock_reason(state))

    def test_record_fault_from_missing_state_creates_valid_locked_schema(self):
        state = fault_lock.record_fault(
            fault_lock.FAULT_LIFT_POSITION_UNKNOWN,
            cell=30,
            detail="no Z",
            path=self.path,
        )
        reloaded = fault_lock.load_state(self.path)
        self.assertEqual(state["schema_version"], fault_lock.STATE_SCHEMA_VERSION)
        self.assertTrue(fault_lock.is_locked(reloaded))
        self.assertEqual(reloaded["fault"]["code"], "LIFT_POSITION_UNKNOWN")
        self.assertFalse(reloaded["cargo_trust"])

    def test_unknown_fault_code_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown fault code"):
            fault_lock.record_fault("TYPO_CODE", cell=1, detail="x", path=self.path)

    def test_later_fault_does_not_overwrite_primary_and_history_keeps_both(self):
        fault_lock.record_fault(
            fault_lock.FAULT_CARGO_LOST, cell=1, detail="first", path=self.path,
        )
        state = fault_lock.record_fault(
            fault_lock.FAULT_COMMAND_ABORTED, cell=1, detail="second", path=self.path,
        )
        self.assertEqual(state["fault"]["code"], fault_lock.FAULT_CARGO_LOST)
        self.assertEqual(state["latest_fault"]["code"], fault_lock.FAULT_COMMAND_ABORTED)
        self.assertEqual([x["detail"] for x in state["fault_history"]], ["first", "second"])

    def test_phase_state_write_is_rejected_on_fault_instead_of_clearing_it(self):
        fault_lock.record_fault(
            fault_lock.FAULT_RECOVERY_UNSAFE, cell=1, detail="drop", path=self.path,
        )
        with fault_lock.command_guard("stop", path=self.path):
            with self.assertRaisesRegex(RuntimeError, "requires diagnose|locked state"):
                fault_lock.record_phase_state(
                    phase="stop",
                    cell=None,
                    load_state_value="unknown",
                    fork_hold=None,
                    lift_command=None,
                    path=self.path,
                )
        self.assertTrue(fault_lock.is_locked(fault_lock.load_state(self.path)))

    def test_clear_requires_every_human_and_online_gate(self):
        required = {
            "operator_confirmed_restart": True,
            "preflight_passed": True,
            "visual_empty_confirmed": True,
            "emitter_off_confirmed": True,
            "note": "evidence.png",
            "path": self.path,
        }
        cases = (
            ("operator_confirmed_restart", False, "operator"),
            ("preflight_passed", False, "preflight"),
            ("visual_empty_confirmed", False, "visual"),
            ("emitter_off_confirmed", False, "emitter"),
            ("note", "", "note"),
        )
        for key, value, message in cases:
            kwargs = dict(required)
            kwargs[key] = value
            with self.subTest(key=key):
                with self.assertRaisesRegex(RuntimeError, message):
                    fault_lock.clear_for_new_epoch(**kwargs)

    def test_clear_initializes_new_epoch_and_preserves_fault_history(self):
        fault_lock.record_fault(
            fault_lock.FAULT_CARGO_LOST, cell=30, detail="drop", path=self.path,
        )
        state = initialize_epoch(self.path)
        self.assertFalse(fault_lock.is_locked(state))
        self.assertEqual(state["restart_evidence"], "operator-attested-only")
        self.assertEqual(state["fault_history"][0]["code"], "CARGO_LOST")
        self.assertEqual(len(state["reset_history"]), 1)
        self.assertIsNone(state["last_phase"])

    def test_clear_with_complete_evidence_still_requires_reset_lease(self):
        with self.assertRaisesRegex(RuntimeError, "no command_guard"):
            fault_lock.clear_for_new_epoch(
                operator_confirmed_restart=True,
                preflight_passed=True,
                visual_empty_confirmed=True,
                emitter_off_confirmed=True,
                note="evidence.png",
                path=self.path,
            )

    def test_audit_is_separate_jsonl_and_preserves_event_order(self):
        initialize_epoch(self.path)
        fault_lock.record_fault(
            fault_lock.FAULT_CARGO_LOST, cell=30, detail="drop", path=self.path,
        )
        lines = fault_lock.audit_path(self.path).read_text(encoding="utf-8").splitlines()
        events = [json.loads(line) for line in lines]
        self.assertEqual(
            [event["event_type"] for event in events],
            ["epoch-reset-request", "fault-recorded"],
        )
        self.assertEqual(events[0]["actor"], "operator-attested")
        self.assertEqual(events[1]["payload"]["detail"], "drop")
        self.assertLess(events[0]["revision"], events[1]["revision"])

    def test_revision_is_monotonic(self):
        state0 = initialize_epoch(self.path)
        with fault_lock.command_guard("diagnose", path=self.path):
            token = fault_lock.begin_transition(
                "diagnose:feed", cell=1, path=self.path,
            )
            state1 = fault_lock.record_phase_state(
                phase="feed",
                cell=1,
                load_state_value="staged",
                fork_hold=None,
                lift_command=False,
                transition_token=token,
                path=self.path,
            )
            fault_lock.complete_transition(token, path=self.path)
        state2 = fault_lock.record_fault(
            fault_lock.FAULT_COMMAND_ABORTED,
            cell=1,
            detail="x",
            path=self.path,
        )
        self.assertEqual(
            [state0["revision"], state1["revision"], state2["revision"]],
            sorted({state0["revision"], state1["revision"], state2["revision"]}),
        )


class TransitionAndLeaseTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "fault_state.json"
        initialize_epoch(self.path)

    def tearDown(self):
        self._tmp.cleanup()

    def test_transition_pending_locks_until_matching_completion(self):
        with fault_lock.command_guard("diagnose", path=self.path):
            token = fault_lock.begin_transition(
                "diagnose:place-extend", cell=30, path=self.path,
            )
            pending = fault_lock.load_state(self.path)
            self.assertTrue(fault_lock.is_locked(pending))
            self.assertEqual(pending["transition_pending"]["token"], token)
            fault_lock.record_phase_state(
                phase="place-extend",
                cell=30,
                load_state_value="extended_hold",
                fork_hold=f3.C_FORKS_R,
                lift_command=True,
                transition_token=token,
                path=self.path,
            )
            completed = fault_lock.complete_transition(token, path=self.path)
        self.assertFalse(fault_lock.is_locked(completed))
        self.assertNotIn("transition_pending", completed)

    def test_transition_wrong_token_cannot_clear_pending(self):
        with fault_lock.command_guard("diagnose", path=self.path):
            fault_lock.begin_transition("diagnose:pick", cell=1, path=self.path)
            with self.assertRaisesRegex(RuntimeError, "token mismatch"):
                fault_lock.complete_transition("wrong", path=self.path)
        self.assertTrue(fault_lock.is_locked(fault_lock.load_state(self.path)))

    def test_allowed_stop_lease_cannot_clear_an_interrupted_diagnose(self):
        with fault_lock.command_guard("diagnose", path=self.path):
            token = fault_lock.begin_transition(
                "diagnose:pick", cell=1, path=self.path,
            )
        with fault_lock.command_guard("stop", path=self.path):
            with self.assertRaisesRegex(RuntimeError, "lease mismatch"):
                fault_lock.complete_transition(token, path=self.path)
        self.assertTrue(fault_lock.is_locked(fault_lock.load_state(self.path)))

    def test_begin_transition_requires_command_lease(self):
        with self.assertRaisesRegex(RuntimeError, "no command_guard"):
            fault_lock.begin_transition("raw", cell=None, path=self.path)

    def test_locked_state_blocks_action_guard_but_allows_stop(self):
        fault_lock.record_fault(
            fault_lock.FAULT_CARGO_LOST, cell=1, detail="x", path=self.path,
        )
        with self.assertRaisesRegex(RuntimeError, "PERSISTENT FAULT LOCK"):
            with fault_lock.command_guard("diagnose", path=self.path):
                pass
        with fault_lock.command_guard("stop", path=self.path):
            self.assertEqual(fault_lock.require_command_session(path=self.path), "stop")

    def test_command_guard_blocks_competing_state_writer_until_release(self):
        entered = threading.Event()
        release = threading.Event()
        writer_done = threading.Event()

        def holder():
            with fault_lock.command_guard("diagnose", path=self.path):
                entered.set()
                release.wait(2.0)

        def writer():
            entered.wait(2.0)
            fault_lock.record_fault(
                fault_lock.FAULT_COMMAND_ABORTED,
                cell=1,
                detail="concurrent",
                path=self.path,
            )
            writer_done.set()

        a = threading.Thread(target=holder)
        b = threading.Thread(target=writer)
        a.start()
        b.start()
        self.assertTrue(entered.wait(1.0))
        self.assertFalse(writer_done.wait(0.15))
        release.set()
        a.join(2.0)
        b.join(2.0)
        self.assertTrue(writer_done.is_set())
        self.assertTrue(fault_lock.is_locked(fault_lock.load_state(self.path)))

    def test_same_process_competing_thread_honors_timeout(self):
        entered = threading.Event()
        release = threading.Event()

        def holder():
            with fault_lock.interprocess_lock(self.path, timeout=1.0):
                entered.set()
                release.wait(2.0)

        worker = threading.Thread(target=holder)
        worker.start()
        self.assertTrue(entered.wait(1.0))
        try:
            with self.assertRaisesRegex(TimeoutError, "command lease timeout"):
                with fault_lock.interprocess_lock(self.path, timeout=0.1):
                    pass
        finally:
            release.set()
            worker.join(2.0)

    def test_persisted_phase_gate_accepts_exact_chain_and_rejects_mismatch(self):
        with fault_lock.command_guard("diagnose", path=self.path):
            token = fault_lock.begin_transition(
                "diagnose:place-extend", cell=30, path=self.path,
            )
            fault_lock.record_phase_state(
                phase="place-extend",
                cell=30,
                load_state_value="extended_hold",
                fork_hold=f3.C_FORKS_R,
                lift_command=True,
                transition_token=token,
                path=self.path,
            )
            fault_lock.complete_transition(token, path=self.path)
        phase = fault_lock.require_last_phase(
            "place-extend",
            cell=30,
            load_state_value="extended_hold",
            fork_hold=f3.C_FORKS_R,
            lift_command=True,
            path=self.path,
        )
        self.assertEqual(phase["cell"], 30)
        with self.assertRaisesRegex(RuntimeError, "persisted phase gate"):
            fault_lock.require_last_phase("place-lower", cell=30, path=self.path)


class ProcessFailureInjectionTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.env = os.environ.copy()
        self.env["PYTHONPATH"] = str(Path(__file__).resolve().parent)

    def tearDown(self):
        self._tmp.cleanup()

    def run_child(self, source: str, state: Path):
        return subprocess.run(
            [sys.executable, "-B", "-c", source, str(state)],
            text=True,
            capture_output=True,
            env=self.env,
            timeout=10,
        )

    def start_fault_child(self, state: Path, detail: str):
        source = """
import sys
from pathlib import Path
import fault_lock
p = Path(sys.argv[1])
detail = sys.argv[2]
print('ATTEMPT', flush=True)
fault_lock.record_fault(fault_lock.FAULT_COMMAND_ABORTED, cell=1, detail=detail, path=p)
print('DONE', flush=True)
"""
        return subprocess.Popen(
            [sys.executable, "-B", "-c", source, str(state), detail],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=self.env,
        )

    def test_hard_kill_after_intent_leaves_pending_and_releases_lock(self):
        state = self.root / "kill_pending" / "fault_state.json"
        child = """
import os, sys
from pathlib import Path
import fault_lock
p = Path(sys.argv[1])
with fault_lock.command_guard('reset-epoch', path=p):
    fault_lock.clear_for_new_epoch(operator_confirmed_restart=True, preflight_passed=True, visual_empty_confirmed=True, emitter_off_confirmed=True, note='kill-test', path=p)
with fault_lock.command_guard('diagnose', path=p):
    token = fault_lock.begin_transition('diagnose:pick', cell=1, path=p)
    print(token, flush=True)
    os._exit(97)
"""
        result = self.run_child(child, state)
        token = result.stdout.strip()
        self.assertEqual(result.returncode, 97, result.stderr)
        self.assertEqual(len(token), 32)
        self.assertEqual(
            fault_lock.load_state(state)["transition_pending"]["token"], token,
        )
        with self.assertRaisesRegex(RuntimeError, "PERSISTENT FAULT LOCK"):
            with fault_lock.command_guard("diagnose", path=state):
                pass
        with fault_lock.command_guard("stop", path=state):
            with self.assertRaisesRegex(RuntimeError, "lease mismatch"):
                fault_lock.complete_transition(token, path=state)
        with fault_lock.interprocess_lock(state, timeout=0.5):
            pass

    def test_hard_kill_while_holding_byte_lock_releases_os_lock(self):
        state = self.root / "kill_lock" / "fault_state.json"
        child = """
import os, sys
from pathlib import Path
import fault_lock
p = Path(sys.argv[1])
with fault_lock.interprocess_lock(p, timeout=1.0):
    print('LOCKED', flush=True)
    os._exit(98)
"""
        result = self.run_child(child, state)
        self.assertEqual((result.returncode, result.stdout.strip()), (98, "LOCKED"))
        with fault_lock.interprocess_lock(state, timeout=0.5):
            pass

    def test_deleted_state_mid_command_rejects_device_write(self):
        state = self.root / "delete_state" / "fault_state.json"
        initialize_epoch(state)
        with fault_lock.command_guard("diagnose", path=state):
            fault_lock.begin_transition("diagnose:pick", cell=1, path=state)
            state.unlink()
            with self.assertRaisesRegex(RuntimeError, "write-ahead"):
                fault_lock.assert_device_write_allowed(
                    "modbus-coil", address=f3.C_LIFT, value=True, path=state,
                )
        self.assertTrue(fault_lock.is_locked(fault_lock.load_state(state)))

    def test_audit_failures_preserve_fail_closed_state(self):
        audit_error = OSError("audit medium unavailable")

        reset_state = self.root / "audit_reset" / "fault_state.json"
        with fault_lock.command_guard("reset-epoch", path=reset_state):
            with patch.object(fault_lock, "_append_audit", side_effect=audit_error):
                with self.assertRaisesRegex(OSError, "audit medium"):
                    fault_lock.clear_for_new_epoch(
                        operator_confirmed_restart=True,
                        preflight_passed=True,
                        visual_empty_confirmed=True,
                        emitter_off_confirmed=True,
                        note="must-not-clear",
                        path=reset_state,
                    )
        self.assertTrue(fault_lock.is_locked(fault_lock.load_state(reset_state)))

        transition_state = self.root / "audit_transition" / "fault_state.json"
        initialize_epoch(transition_state)
        with fault_lock.command_guard("diagnose", path=transition_state):
            token = fault_lock.begin_transition(
                "diagnose:pick", cell=1, path=transition_state,
            )
            with patch.object(fault_lock, "_append_audit", side_effect=audit_error):
                with self.assertRaisesRegex(OSError, "audit medium"):
                    fault_lock.complete_transition(token, path=transition_state)
        self.assertEqual(
            fault_lock.load_state(transition_state)["transition_pending"]["token"],
            token,
        )

        fault_state = self.root / "audit_fault" / "fault_state.json"
        initialize_epoch(fault_state)
        with patch.object(fault_lock, "_append_audit", side_effect=audit_error):
            with self.assertRaisesRegex(OSError, "audit medium"):
                fault_lock.record_fault(
                    fault_lock.FAULT_COMMAND_ABORTED,
                    cell=1,
                    detail="fault must win",
                    path=fault_state,
                )
        loaded = fault_lock.load_state(fault_state)
        self.assertTrue(fault_lock.is_locked(loaded))
        self.assertEqual(loaded["fault"]["code"], fault_lock.FAULT_COMMAND_ABORTED)

    def test_cross_process_fault_waits_for_action_lease_then_wins(self):
        state = self.root / "race_action_fault" / "fault_state.json"
        initialize_epoch(state)
        with fault_lock.command_guard("diagnose", path=state):
            token = fault_lock.begin_transition(
                "diagnose:pick", cell=1, path=state,
            )
            child = self.start_fault_child(state, "during action")
            self.assertEqual(child.stdout.readline().strip(), "ATTEMPT")
            self.assertIsNone(child.poll(), "fault writer bypassed active action lease")
            fault_lock.complete_transition(token, path=state)
        stdout, stderr = child.communicate(timeout=10)
        self.assertEqual(child.returncode, 0, stderr)
        self.assertEqual(stdout.strip(), "DONE")
        loaded = fault_lock.load_state(state)
        self.assertTrue(fault_lock.is_locked(loaded))
        self.assertEqual(loaded["fault"]["detail"], "during action")

    def test_cross_process_fault_waits_for_reset_lease_then_wins(self):
        state = self.root / "race_reset_fault" / "fault_state.json"
        initialize_epoch(state)
        with fault_lock.command_guard("reset-epoch", path=state):
            child = self.start_fault_child(state, "during reset")
            self.assertEqual(child.stdout.readline().strip(), "ATTEMPT")
            self.assertIsNone(child.poll(), "fault writer bypassed active reset lease")
            fault_lock.clear_for_new_epoch(
                operator_confirmed_restart=True,
                preflight_passed=True,
                visual_empty_confirmed=True,
                emitter_off_confirmed=True,
                note="race reset",
                path=state,
            )
        stdout, stderr = child.communicate(timeout=10)
        self.assertEqual(child.returncode, 0, stderr)
        self.assertEqual(stdout.strip(), "DONE")
        loaded = fault_lock.load_state(state)
        self.assertTrue(fault_lock.is_locked(loaded))
        self.assertEqual(loaded["fault"]["detail"], "during reset")


class CliBypassGuardTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "fault_state.json"
        self._orig_default = fault_lock.default_state_path
        fault_lock.default_state_path = lambda: self.path

    def tearDown(self):
        fault_lock.default_state_path = self._orig_default
        self._tmp.cleanup()

    def test_locked_state_blocks_diagnose_and_legacy_modes(self):
        fault_lock.record_fault(
            fault_lock.FAULT_RECOVERY_UNSAFE, cell=1, detail="x", path=self.path,
        )
        for mode in ("diagnose", "probe", "demo", "accept", "mechanics-probe", "emitter-pulse"):
            with self.subTest(mode=mode):
                with self.assertRaisesRegex(RuntimeError, "PERSISTENT FAULT LOCK"):
                    f3._assert_unlocked_for_action(mode)

    def test_locked_state_allows_evidence_stop_reset_and_emitter_off(self):
        fault_lock.record_fault(
            fault_lock.FAULT_LOWER_NO_START, cell=1, detail="x", path=self.path,
        )
        for mode in ("snapshot", "stop", "mark-fault", "reset-epoch", "emitter-off"):
            f3._assert_unlocked_for_action(mode)

    def test_unlocked_state_allows_diagnose(self):
        initialize_epoch(self.path)
        f3._assert_unlocked_for_action("diagnose")

    def test_low_level_coil_and_target_reject_calls_without_lease(self):
        initialize_epoch(self.path)
        response = Mock()
        response.isError.return_value = False
        client = Mock()
        client.connect.return_value = True
        client.write_coil.return_value = response
        client.write_register.return_value = response
        stacker = f3.Stacker(client)

        with self.assertRaisesRegex(RuntimeError, "no command_guard"):
            stacker.coil(f3.C_LIFT, True)
        with self.assertRaisesRegex(RuntimeError, "no command_guard"):
            stacker.target(1)
        client.write_coil.assert_not_called()
        client.write_register.assert_not_called()

        with fault_lock.command_guard("diagnose"):
            with self.assertRaisesRegex(RuntimeError, "write-ahead"):
                stacker.coil(f3.C_LIFT, True)
            with self.assertRaisesRegex(RuntimeError, "write-ahead"):
                stacker.target(1)
            token = fault_lock.begin_transition("diagnose:pick", cell=1)
            stacker.coil(f3.C_LIFT, True)
            stacker.target(1)
            fault_lock.complete_transition(token)
        client.write_coil.assert_called_once()
        client.write_register.assert_called_once()

    def test_read_only_and_emitter_off_leases_cannot_write_modbus(self):
        initialize_epoch(self.path)
        response = Mock()
        response.isError.return_value = False
        client = Mock()
        client.connect.return_value = True
        client.write_coil.return_value = response
        client.write_register.return_value = response
        stacker = f3.Stacker(client)
        for mode in ("snapshot", "mark-fault", "reset-epoch", "emitter-off"):
            with self.subTest(mode=mode):
                with fault_lock.command_guard(mode):
                    with self.assertRaisesRegex(RuntimeError, "forbids|write-ahead"):
                        stacker.coil(f3.C_LIFT, True)
        client.write_coil.assert_not_called()

    def test_stop_capability_allows_only_zero_and_safe_false_outputs(self):
        initialize_epoch(self.path)
        with fault_lock.command_guard("stop"):
            fault_lock.assert_device_write_allowed(
                "modbus-target", address=0, value=0,
            )
            fault_lock.assert_device_write_allowed(
                "modbus-coil", address=f3.C_LIFT, value=False,
            )
            for address, value in (
                (f3.C_FORKS_L, False),
                (f3.C_FORKS_R, False),
                (f3.C_LIFT, True),
            ):
                with self.subTest(address=address, value=value):
                    with self.assertRaisesRegex(RuntimeError, "stop capability"):
                        fault_lock.assert_device_write_allowed(
                            "modbus-coil", address=address, value=value,
                        )

    def test_any_started_command_exception_persists_abort_and_pending(self):
        initialize_epoch(self.path)
        stacker = Mock()
        args = argparse.Namespace(cell=30, phase="place-lower")
        with fault_lock.command_guard("diagnose"):
            token = fault_lock.begin_transition("diagnose:place-lower", cell=30)
            f3._handle_command_failure(
                mode="diagnose",
                args=args,
                stacker=stacker,
                transition_token=token,
                error=RuntimeError("TIMEOUT after Z start"),
            )
        state = fault_lock.load_state(self.path)
        self.assertTrue(fault_lock.is_locked(state))
        self.assertEqual(state["fault"]["code"], fault_lock.FAULT_COMMAND_ABORTED)
        self.assertEqual(state["transition_pending"]["token"], token)


class StopForkHoldRebuildTests(unittest.TestCase):
    def make_fresh_process_stacker(self, coils):
        stacker = f3.Stacker.__new__(f3.Stacker)
        stacker.load_state = f3.LoadState.UNKNOWN
        stacker.position_hint = None
        stacker.fork_hold = None
        stacker.target = Mock()
        stacker.coil = Mock()
        inputs = [False] * len(f3.INPUT_NAMES)
        if coils[f3.C_FORKS_L] and not coils[f3.C_FORKS_R]:
            inputs[f3.IN_AT_LEFT] = True
        elif coils[f3.C_FORKS_R] and not coils[f3.C_FORKS_L]:
            inputs[f3.IN_AT_RIGHT] = True
        else:
            inputs[f3.IN_AT_MIDDLE] = True
        stacker.snapshot = Mock(return_value={
            "inputs": inputs,
            "coils": list(coils),
            "target": 0,
        })
        return stacker

    def test_stop_rebuilds_right_hold_from_stable_coil_and_limit(self):
        coils = [False] * len(f3.COIL_NAMES)
        coils[f3.C_FORKS_R] = True
        coils[f3.C_LIFT] = True
        stacker = self.make_fresh_process_stacker(coils)
        stacker.safe_stop(preserve_lift=True)
        self.assertEqual(stacker.fork_hold, f3.C_FORKS_R)
        self.assertNotIn(call(f3.C_FORKS_R, False), stacker.coil.call_args_list)
        self.assertNotIn(call(f3.C_FORKS_L, False), stacker.coil.call_args_list)
        self.assertNotIn(call(f3.C_LIFT, False), stacker.coil.call_args_list)

    def test_stop_rebuilds_left_hold_from_stable_coil_and_limit(self):
        coils = [False] * len(f3.COIL_NAMES)
        coils[f3.C_FORKS_L] = True
        stacker = self.make_fresh_process_stacker(coils)
        stacker.safe_stop(preserve_lift=True)
        self.assertEqual(stacker.fork_hold, f3.C_FORKS_L)
        self.assertNotIn(call(f3.C_FORKS_L, False), stacker.coil.call_args_list)

    def test_stop_read_failure_still_targets_zero_and_never_touches_fork_or_lift(self):
        stacker = f3.Stacker.__new__(f3.Stacker)
        stacker.load_state = f3.LoadState.UNKNOWN
        stacker.position_hint = None
        stacker.fork_hold = None
        stacker.target = Mock()
        stacker.coil = Mock()
        stacker.snapshot = Mock(side_effect=RuntimeError("link down"))

        with self.assertRaisesRegex(RuntimeError, "fork state ambiguous"):
            stacker.safe_stop(preserve_lift=True)
        stacker.target.assert_called_once_with(0)
        for address in (f3.C_FORKS_L, f3.C_FORKS_R, f3.C_LIFT):
            self.assertNotIn(call(address, False), stacker.coil.call_args_list)


if __name__ == "__main__":
    unittest.main()
