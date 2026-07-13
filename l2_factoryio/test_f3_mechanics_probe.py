# -*- coding: utf-8 -*-
"""F3 空载叉臂/Lift A-B 探针离线契约测试。"""

import unittest
from unittest.mock import Mock, call, patch

import f3_mechanics_probe as probe
import f3_stacker_control as f3


class MechanicsProbeTests(unittest.TestCase):
    def make_stacker(self):
        stacker = Mock(unsafe=True)
        stacker.fork_hold = f3.C_FORKS_R
        return stacker

    @patch("f3_mechanics_probe.wait_for_z_edge", return_value=None)
    def test_a_keeps_right_held_while_lower_is_requested(self, edge):
        stacker = self.make_stacker()

        passed = probe.probe_a(stacker)

        self.assertFalse(passed)
        stacker.forks_right_hold.assert_called_once_with()
        stacker.coil.assert_called_once_with(f3.C_LIFT, False)
        self.assertNotIn(call(f3.C_FORKS_R, False), stacker.coil.call_args_list)
        edge.assert_called_once_with(stacker, probe.STRICT_START_TIMEOUT)

    @patch("f3_mechanics_probe.wait_for_z_edge", return_value=0.08)
    @patch("f3_mechanics_probe.monitor_z_finish_and_right", return_value=(2.2, False))
    @patch("f3_mechanics_probe.time.monotonic", side_effect=(10.0, 10.1))
    def test_b_release_lower_reassert_order(self, monotonic, monitor, edge):
        stacker = self.make_stacker()
        stacker.din.return_value = True

        passed = probe.probe_b(stacker)

        self.assertTrue(passed)
        self.assertEqual(
            stacker.coil.call_args_list,
            [
                call(f3.C_FORKS_R, False),
                call(f3.C_LIFT, False),
                call(f3.C_FORKS_R, True),
            ],
        )
        edge.assert_called_once_with(stacker, probe.EDGE_TIMEOUT)
        monitor.assert_called_once_with(stacker)
        self.assertEqual(stacker.fork_hold, f3.C_FORKS_R)

    @patch("f3_mechanics_probe.wait_for_z_edge", return_value=0.08)
    @patch("f3_mechanics_probe.monitor_z_finish_and_right", return_value=(0.25, False))
    @patch("f3_mechanics_probe.time.monotonic", side_effect=(10.0, 10.1))
    def test_b_rejects_z_pulse_aborted_by_right_reassert(
        self, monotonic, monitor, edge
    ):
        stacker = self.make_stacker()
        stacker.din.return_value = True

        self.assertFalse(probe.probe_b(stacker))

    def test_prepare_requires_real_baseline_z_cycle(self):
        stacker = self.make_stacker()

        probe.prepare_empty_probe(stacker)

        stacker.coil.assert_called_once_with(f3.C_LIFT, True)
        stacker.wait_motion_cycle.assert_called_once()
        self.assertEqual(
            stacker.wait_motion_cycle.call_args.kwargs["start_timeout"],
            probe.STRICT_START_TIMEOUT,
        )


if __name__ == "__main__":
    unittest.main()
