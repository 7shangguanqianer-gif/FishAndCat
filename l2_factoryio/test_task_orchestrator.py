import tempfile
import unittest
from pathlib import Path

from event_log import JsonlEventLog, TaskEvent
from task_contract import FaultCode, Operation, TaskStatus, WarehouseTask
from task_orchestrator import AdapterFault, TaskOrchestrator


class FakeAdapter:
    def __init__(self, fail_on=None, stop_fails=False):
        self.actions = []
        self.fail_on = fail_on
        self.stop_fails = stop_fails

    def _do(self, action):
        self.actions.append(action)
        if action == self.fail_on:
            raise AdapterFault(FaultCode.TIMEOUT, f"failed at {action}")

    def feed(self):
        self._do("feed")

    def pick_load(self):
        self._do("pick_load")

    def store(self, cell):
        self._do(f"store:{cell}")

    def retrieve(self, cell):
        self._do(f"retrieve:{cell}")

    def go_rest(self):
        self._do("go_rest")

    def unload(self):
        self._do("unload")

    def safe_stop(self):
        self.actions.append("safe_stop")
        if self.stop_fails:
            raise RuntimeError("stop link failed")


class OrchestratorTests(unittest.TestCase):
    def run_task(self, task, adapter=None):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        log = JsonlEventLog(Path(temp.name) / "events.jsonl")
        adapter = adapter or FakeAdapter()
        orchestrator = TaskOrchestrator(adapter, log)
        result = orchestrator.execute(task)
        return adapter, log.read_all(), result, orchestrator

    def test_inbound_sequence(self):
        task = WarehouseTask(1, 1, Operation.INBOUND, 9, logical_target=399)
        adapter, events, result, _ = self.run_task(task)
        self.assertEqual(
            adapter.actions,
            ["feed", "pick_load", "store:54", "go_rest"],
        )
        self.assertEqual(result.status, TaskStatus.DONE)
        self.assertEqual(events[-1].status, TaskStatus.DONE)

    def test_outbound_sequence(self):
        task = WarehouseTask(2, 2, Operation.OUTBOUND, 9, logical_source=0)
        adapter, _, result, _ = self.run_task(task)
        self.assertEqual(
            adapter.actions,
            ["retrieve:1", "go_rest", "unload", "go_rest"],
        )
        self.assertEqual(result.status, TaskStatus.DONE)

    def test_dual_sequence(self):
        task = WarehouseTask(
            3,
            3,
            Operation.DUAL,
            9,
            logical_source=0,
            logical_target=399,
        )
        adapter, _, result, _ = self.run_task(task)
        self.assertEqual(
            adapter.actions,
            [
                "feed",
                "pick_load",
                "store:54",
                "retrieve:1",
                "go_rest",
                "unload",
                "go_rest",
            ],
        )
        self.assertEqual(result.status, TaskStatus.DONE)

    def test_duplicate_request_is_not_executed_twice(self):
        task = WarehouseTask(4, 4, Operation.INBOUND, 9, logical_target=1)
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        adapter = FakeAdapter()
        log = JsonlEventLog(Path(temp.name) / "events.jsonl")
        orchestrator = TaskOrchestrator(adapter, log)
        first = orchestrator.execute(task)
        second = orchestrator.execute(task)
        self.assertEqual(first.status, TaskStatus.DONE)
        self.assertTrue(second.duplicate)
        self.assertEqual(
            adapter.actions,
            ["feed", "pick_load", "store:1", "go_rest"],
        )

    def test_restart_recovers_idempotency_from_event_log(self):
        task = WarehouseTask(7, 7, Operation.INBOUND, 9, logical_target=1)
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        path = Path(temp.name) / "events.jsonl"
        first_adapter = FakeAdapter()
        first = TaskOrchestrator(first_adapter, JsonlEventLog(path))
        self.assertEqual(first.execute(task).status, TaskStatus.DONE)

        restarted_adapter = FakeAdapter()
        restarted = TaskOrchestrator(restarted_adapter, JsonlEventLog(path))
        result = restarted.execute(task)
        self.assertTrue(result.duplicate)
        self.assertEqual(restarted_adapter.actions, [])

    def test_reused_request_sequence_for_different_task_is_rejected(self):
        first_task = WarehouseTask(
            8, 8, Operation.INBOUND, 9, logical_target=1,
        )
        conflicting_task = WarehouseTask(
            9, 8, Operation.INBOUND, 10, logical_target=2,
        )
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        adapter = FakeAdapter()
        log = JsonlEventLog(Path(temp.name) / "events.jsonl")
        orchestrator = TaskOrchestrator(adapter, log)
        orchestrator.execute(first_task)
        with self.assertRaises(ValueError):
            orchestrator.execute(conflicting_task)

    def test_restart_blocks_incomplete_request_for_manual_recovery(self):
        task = WarehouseTask(10, 10, Operation.INBOUND, 9, logical_target=1)
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        path = Path(temp.name) / "events.jsonl"
        log = JsonlEventLog(path)
        log.append(TaskEvent(
            timestamp="2026-07-13T00:00:00Z",
            task_id=task.task_id,
            request_seq=task.request_seq,
            operation=task.operation,
            status=TaskStatus.RUNNING,
            phase="PICK_LOAD",
            attempt=1,
            logical_target=task.logical_target,
            physical_target=task.physical_target,
        ))

        adapter = FakeAdapter()
        restarted = TaskOrchestrator(adapter, JsonlEventLog(path))
        result = restarted.execute(task)
        self.assertTrue(result.duplicate)
        self.assertEqual(result.status, TaskStatus.FAULT)
        self.assertEqual(result.fault_code, FaultCode.RECOVERY_REQUIRED)
        self.assertEqual(adapter.actions, [])

    def test_fault_calls_safe_stop_and_records_fault(self):
        task = WarehouseTask(5, 5, Operation.INBOUND, 9, logical_target=1)
        adapter = FakeAdapter(fail_on="store:1")
        adapter, events, result, _ = self.run_task(task, adapter)
        self.assertEqual(adapter.actions[-1], "safe_stop")
        self.assertEqual(result.status, TaskStatus.FAULT)
        self.assertEqual(result.fault_code, FaultCode.TIMEOUT)
        self.assertEqual(events[-1].status, TaskStatus.FAULT)

    def test_safe_stop_failure_is_preserved_as_second_event(self):
        task = WarehouseTask(6, 6, Operation.INBOUND, 9, logical_target=1)
        adapter = FakeAdapter(fail_on="feed", stop_fails=True)
        _, events, result, _ = self.run_task(task, adapter)
        self.assertTrue(result.safe_stop_failed)
        self.assertEqual(events[-2].fault_code, FaultCode.TIMEOUT)
        self.assertEqual(events[-1].fault_code, FaultCode.SAFE_STOP_FAILED)


if __name__ == "__main__":
    unittest.main()
