from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Protocol

from event_log import JsonlEventLog, TaskEvent
from task_contract import FaultCode, Operation, TaskStatus, WarehouseTask


class DeviceAdapter(Protocol):
    def feed(self) -> None: ...

    def pick_load(self) -> None: ...

    def store(self, cell: int) -> None: ...

    def retrieve(self, cell: int) -> None: ...

    def go_rest(self) -> None: ...

    def unload(self) -> None: ...

    def safe_stop(self) -> None: ...


class AdapterFault(RuntimeError):
    def __init__(self, code: FaultCode, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ExecutionResult:
    task_id: int
    request_seq: int
    status: TaskStatus
    fault_code: FaultCode = FaultCode.NONE
    duplicate: bool = False
    safe_stop_failed: bool = False


class TaskOrchestrator:
    def __init__(self, adapter: DeviceAdapter, event_log: JsonlEventLog):
        self.adapter = adapter
        self.event_log = event_log
        self._results_by_request: dict[int, ExecutionResult] = {}
        self._task_id_by_request: dict[int, int] = {}
        self._recover_results()

    def _recover_results(self) -> None:
        """Rebuild idempotency from append-only evidence after a restart."""
        seen_requests = set()
        for event in self.event_log.read_all():
            seen_requests.add(event.request_seq)
            existing_task_id = self._task_id_by_request.get(event.request_seq)
            if existing_task_id is not None and existing_task_id != event.task_id:
                raise ValueError(
                    "event log request_seq conflict: "
                    f"{event.request_seq} has task_id {existing_task_id} "
                    f"and {event.task_id}"
                )
            self._task_id_by_request[event.request_seq] = event.task_id
            if event.status is TaskStatus.DONE:
                self._results_by_request[event.request_seq] = ExecutionResult(
                    event.task_id,
                    event.request_seq,
                    TaskStatus.DONE,
                )
            elif event.status is TaskStatus.FAULT:
                previous = self._results_by_request.get(event.request_seq)
                safe_stop_failed = (
                    event.fault_code is FaultCode.SAFE_STOP_FAILED
                    or bool(previous and previous.safe_stop_failed)
                )
                fault_code = event.fault_code
                if (
                    fault_code is FaultCode.SAFE_STOP_FAILED
                    and previous is not None
                ):
                    fault_code = previous.fault_code
                self._results_by_request[event.request_seq] = ExecutionResult(
                    event.task_id,
                    event.request_seq,
                    TaskStatus.FAULT,
                    fault_code,
                    safe_stop_failed=safe_stop_failed,
                )
        for request_seq in seen_requests:
            if request_seq not in self._results_by_request:
                self._results_by_request[request_seq] = ExecutionResult(
                    self._task_id_by_request[request_seq],
                    request_seq,
                    TaskStatus.FAULT,
                    FaultCode.RECOVERY_REQUIRED,
                )

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def _emit(
        self,
        task: WarehouseTask,
        status: TaskStatus,
        phase: str,
        *,
        attempt: int = 1,
        fault_code: FaultCode = FaultCode.NONE,
        message: str = "",
    ) -> None:
        self.event_log.append(TaskEvent(
            timestamp=self._timestamp(),
            task_id=task.task_id,
            request_seq=task.request_seq,
            operation=task.operation,
            status=status,
            phase=phase,
            attempt=attempt,
            logical_source=task.logical_source,
            logical_target=task.logical_target,
            physical_source=task.physical_source,
            physical_target=task.physical_target,
            fault_code=fault_code,
            message=message,
        ))

    def _plan(
        self,
        task: WarehouseTask,
    ) -> list[tuple[str, Callable[[], None]]]:
        if task.operation is Operation.INBOUND:
            assert task.physical_target is not None
            return [
                ("FEED", self.adapter.feed),
                ("PICK_LOAD", self.adapter.pick_load),
                (
                    "STORE_TARGET",
                    lambda: self.adapter.store(task.physical_target),
                ),
                ("RETURN_REST", self.adapter.go_rest),
            ]
        if task.operation is Operation.OUTBOUND:
            assert task.physical_source is not None
            return [
                (
                    "RETRIEVE_SOURCE",
                    lambda: self.adapter.retrieve(task.physical_source),
                ),
                ("RETURN_IO", self.adapter.go_rest),
                ("UNLOAD", self.adapter.unload),
                ("RETURN_REST", self.adapter.go_rest),
            ]
        assert task.physical_source is not None
        assert task.physical_target is not None
        return [
            ("FEED", self.adapter.feed),
            ("PICK_LOAD", self.adapter.pick_load),
            (
                "STORE_TARGET",
                lambda: self.adapter.store(task.physical_target),
            ),
            (
                "RETRIEVE_SOURCE",
                lambda: self.adapter.retrieve(task.physical_source),
            ),
            ("RETURN_IO", self.adapter.go_rest),
            ("UNLOAD", self.adapter.unload),
            ("RETURN_REST", self.adapter.go_rest),
        ]

    def _safe_stop(
        self,
        task: WarehouseTask,
        original_code: FaultCode,
        original_message: str,
    ) -> bool:
        stop_failed = False
        stop_message = ""
        try:
            self.adapter.safe_stop()
        except Exception as stop_exc:
            stop_failed = True
            stop_message = str(stop_exc)
        self._emit(
            task,
            TaskStatus.FAULT,
            "SAFE_STOP",
            fault_code=original_code,
            message=original_message,
        )
        if stop_failed:
            self._emit(
                task,
                TaskStatus.FAULT,
                "SAFE_STOP_FAILED",
                fault_code=FaultCode.SAFE_STOP_FAILED,
                message=stop_message,
            )
        return stop_failed

    def execute(self, task: WarehouseTask) -> ExecutionResult:
        previous = self._results_by_request.get(task.request_seq)
        if previous is not None:
            if self._task_id_by_request[task.request_seq] != task.task_id:
                raise ValueError(
                    f"request_seq {task.request_seq} already belongs to "
                    f"task_id {self._task_id_by_request[task.request_seq]}, "
                    f"not {task.task_id}"
                )
            return ExecutionResult(
                task_id=previous.task_id,
                request_seq=previous.request_seq,
                status=previous.status,
                fault_code=previous.fault_code,
                duplicate=True,
                safe_stop_failed=previous.safe_stop_failed,
            )

        self._task_id_by_request[task.request_seq] = task.task_id
        self._emit(task, TaskStatus.DISPATCHED, "DISPATCH")
        self._emit(task, TaskStatus.ACKED, "ACK")
        self._emit(task, TaskStatus.RUNNING, "START")
        try:
            for phase, action in self._plan(task):
                self._emit(task, TaskStatus.RUNNING, phase)
                action()
        except AdapterFault as exc:
            stop_failed = self._safe_stop(task, exc.code, str(exc))
            result = ExecutionResult(
                task.task_id,
                task.request_seq,
                TaskStatus.FAULT,
                exc.code,
                safe_stop_failed=stop_failed,
            )
            self._results_by_request[task.request_seq] = result
            return result
        except Exception as exc:
            stop_failed = self._safe_stop(
                task,
                FaultCode.IO_ERROR,
                str(exc),
            )
            result = ExecutionResult(
                task.task_id,
                task.request_seq,
                TaskStatus.FAULT,
                FaultCode.IO_ERROR,
                safe_stop_failed=stop_failed,
            )
            self._results_by_request[task.request_seq] = result
            return result

        result = ExecutionResult(
            task.task_id,
            task.request_seq,
            TaskStatus.DONE,
        )
        self._emit(task, TaskStatus.DONE, "COMPLETE")
        self._results_by_request[task.request_seq] = result
        return result
