from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from task_contract import FaultCode, Operation, TaskStatus


@dataclass(frozen=True)
class TaskEvent:
    timestamp: str
    task_id: int
    request_seq: int
    operation: Operation
    status: TaskStatus
    phase: str
    attempt: int
    logical_source: int | None = None
    logical_target: int | None = None
    physical_source: int | None = None
    physical_target: int | None = None
    fault_code: FaultCode = FaultCode.NONE
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["operation"] = int(self.operation)
        payload["status"] = int(self.status)
        payload["fault_code"] = self.fault_code.value
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TaskEvent":
        return cls(
            timestamp=str(payload["timestamp"]),
            task_id=int(payload["task_id"]),
            request_seq=int(payload["request_seq"]),
            operation=Operation(int(payload["operation"])),
            status=TaskStatus(int(payload["status"])),
            phase=str(payload["phase"]),
            attempt=int(payload["attempt"]),
            logical_source=payload.get("logical_source"),
            logical_target=payload.get("logical_target"),
            physical_source=payload.get("physical_source"),
            physical_target=payload.get("physical_target"),
            fault_code=FaultCode(
                payload.get("fault_code", FaultCode.NONE.value)
            ),
            message=str(payload.get("message", "")),
        )


class JsonlEventLog:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def append(self, event: TaskEvent) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(
            event.to_dict(),
            ensure_ascii=False,
            sort_keys=True,
        )
        with self.path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(line + "\n")
            stream.flush()

    def read_all(self) -> list[TaskEvent]:
        if not self.path.exists():
            return []
        events = []
        with self.path.open("r", encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, start=1):
                if not line.strip():
                    continue
                try:
                    events.append(TaskEvent.from_dict(json.loads(line)))
                except (
                    KeyError,
                    TypeError,
                    ValueError,
                    json.JSONDecodeError,
                ) as exc:
                    raise ValueError(
                        f"invalid event at {self.path}:{line_number}: {exc}"
                    ) from exc
        return events
