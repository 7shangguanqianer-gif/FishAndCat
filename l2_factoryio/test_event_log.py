import tempfile
import unittest
from pathlib import Path

from event_log import JsonlEventLog, TaskEvent
from task_contract import FaultCode, Operation, TaskStatus


class EventLogTests(unittest.TestCase):
    def test_append_and_read_preserve_order_and_fields(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "events.jsonl"
            log = JsonlEventLog(path)
            first = TaskEvent(
                timestamp="2026-07-13T00:00:00Z",
                task_id=7,
                request_seq=11,
                operation=Operation.INBOUND,
                status=TaskStatus.RUNNING,
                phase="STORE_TARGET",
                attempt=1,
                logical_target=399,
                physical_target=54,
            )
            second = TaskEvent(
                timestamp="2026-07-13T00:00:01Z",
                task_id=7,
                request_seq=11,
                operation=Operation.INBOUND,
                status=TaskStatus.FAULT,
                phase="SAFE_STOP",
                attempt=1,
                fault_code=FaultCode.TIMEOUT,
                message="motion timeout",
            )
            log.append(first)
            log.append(second)
            self.assertEqual(log.read_all(), [first, second])
            self.assertEqual(
                len(path.read_text(encoding="utf-8").splitlines()),
                2,
            )


if __name__ == "__main__":
    unittest.main()
