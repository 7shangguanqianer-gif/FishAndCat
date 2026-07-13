# -*- coding: utf-8 -*-
"""H1.1 Web API Emitter 写入口与异常关断契约。"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, call, patch

import fault_lock
import webapi_probe


class WebApiEmitterGuardTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "fault_state.json"
        self._original_default = fault_lock.default_state_path
        fault_lock.default_state_path = lambda: self.path
        with fault_lock.command_guard("reset-epoch", path=self.path):
            fault_lock.clear_for_new_epoch(
                operator_confirmed_restart=True,
                preflight_passed=True,
                visual_empty_confirmed=True,
                emitter_off_confirmed=True,
                note="test evidence",
                path=self.path,
            )

    def tearDown(self):
        fault_lock.default_state_path = self._original_default
        self._tmp.cleanup()

    @patch("webapi_probe._request")
    def test_force_emitter_rejects_direct_write_without_command_lease(self, request):
        with self.assertRaisesRegex(RuntimeError, "no command_guard"):
            webapi_probe._force_emitter("http://127.0.0.1", True)
        request.assert_not_called()

    @patch("webapi_probe._request", return_value=(204, ""))
    def test_force_emitter_is_allowed_inside_unlocked_pulse_lease(self, request):
        with fault_lock.command_guard("emitter-pulse"):
            with self.assertRaisesRegex(RuntimeError, "write-ahead"):
                webapi_probe._force_emitter("http://127.0.0.1", True)
            token = fault_lock.begin_transition(
                "emitter-pulse", cell=None, context={"test": True},
            )
            webapi_probe._force_emitter("http://127.0.0.1", True)
            fault_lock.complete_transition(token)
        request.assert_called_once()

    @patch("webapi_probe._emitter_state")
    @patch("webapi_probe._force_emitter")
    @patch("webapi_probe.time.sleep", side_effect=KeyboardInterrupt())
    def test_pulse_attempts_force_off_even_when_interrupted(self, sleep, force, state):
        with fault_lock.command_guard("emitter-pulse"):
            fault_lock.begin_transition("emitter-pulse", cell=None)
            with self.assertRaises(KeyboardInterrupt):
                webapi_probe.cmd_emitter_pulse("http://127.0.0.1", 1.5)
        self.assertEqual(force.call_args_list, [call("http://127.0.0.1", True), call("http://127.0.0.1", False)])
        state.assert_not_called()

    @patch("webapi_probe._request")
    def test_emitter_readback_uses_tags_endpoint_which_carries_isforced(self, request):
        """0713 实测：/api/tag/values 条目不含 isForced，只有 /api/tags 才有。

        若读回校验走 values 端点会恒判 mismatch，把成功的 force-off 误报成
        EMITTER_STATE_UNKNOWN 假锁（13:54 真实锁文件中有一条实例）。
        """
        def fake_request(base, path, method="GET", payload=None):
            if path == "/api/tag/values-force":
                return 204, ""
            if path == "/api/tags":
                return 200, [{
                    "id": webapi_probe.EMITTER_TAG_ID, "name": "Emitter",
                    "value": False, "isForced": True, "forcedValue": False,
                }]
            if path == "/api/tag/values":
                # 真实端点形状：无 isForced/forcedValue 字段。
                return 200, [{"id": webapi_probe.EMITTER_TAG_ID, "value": False}]
            raise AssertionError(f"unexpected path {path}")

        request.side_effect = fake_request
        with fault_lock.command_guard("emitter-off"):
            webapi_probe.cmd_emitter_off("http://127.0.0.1")  # 不应误报 mismatch
        called_paths = [c.args[1] for c in request.call_args_list]
        self.assertIn("/api/tags", called_paths)

    @patch("webapi_probe._request", return_value=(204, ""))
    def test_locked_state_blocks_pulse_but_allows_force_off(self, request):
        fault_lock.record_fault(
            fault_lock.FAULT_CARGO_LOST,
            cell=1,
            detail="drop",
            path=self.path,
        )
        with self.assertRaisesRegex(RuntimeError, "PERSISTENT FAULT LOCK"):
            with fault_lock.command_guard("emitter-pulse"):
                pass
        with fault_lock.command_guard("emitter-off"):
            webapi_probe._force_emitter("http://127.0.0.1", False)
        request.assert_called_once()


if __name__ == "__main__":
    unittest.main()
