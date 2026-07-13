# Factory I/O C Contract and Orchestrator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不连接 AB GUI 的前提下，先固化 Factory I/O 安全动作基线，并实现可离线验证的 20×20→54 任务契约、JSONL 事件日志和 INBOUND/OUTBOUND/DUAL 编排器。

**Architecture:** AB 后续负责业务队列与逻辑库位，Python 只验证任务快照、映射代表格并调用设备适配器。编排器依赖小型 `DeviceAdapter` 接口，离线测试使用 FakeAdapter；真实 Modbus 适配在碰撞门关闭后接入，避免现场物理问题污染任务状态机。

**Tech Stack:** Python 3.10+ 标准库（dataclasses、enum、json、typing、unittest）+ 现有 pymodbus；不新增依赖。

---

## 文件结构与职责

- Modify: `l2_factoryio/f3_stacker_control.py` — 当前已完成但未提交的低层安全动作基线。
- Create: `l2_factoryio/test_f3_stacker_control.py` — 现有低层动作离线回归，先精确提交。
- Create: `l2_factoryio/task_contract.py` — 三类任务、状态、故障、400→54 映射和序列化。
- Create: `l2_factoryio/test_task_contract.py` — 契约边界、角点、单调性和 round-trip。
- Create: `l2_factoryio/event_log.py` — 追加式 JSONL 事件证据。
- Create: `l2_factoryio/test_event_log.py` — 日志字段、追加顺序和重建测试。
- Create: `l2_factoryio/task_orchestrator.py` — 与具体通信无关的单活动任务状态机。
- Create: `l2_factoryio/test_task_orchestrator.py` — FakeAdapter 三任务、幂等和 safe-stop 测试。
- Modify: `docs/overnight2-report_0712night.md` — 记录节奏变更和 C0–C2 实际结论。

## Task 1: 固化当前 F3 安全动作基线

**Files:**
- Modify: `l2_factoryio/f3_stacker_control.py`
- Create: `l2_factoryio/test_f3_stacker_control.py`

- [ ] **Step 1: 编译并运行现有 6 个离线测试**

Run:

```powershell
Set-Location F:\abb_wh_work\l2_factoryio
python -m py_compile f3_stacker_control.py test_f3_stacker_control.py
python -m unittest -v test_f3_stacker_control.py
```

Expected: `Ran 6 tests` 和 `OK`。

- [ ] **Step 2: 审计精确暂存范围**

Run:

```powershell
Set-Location F:\abb_wh_work
git add -- l2_factoryio/f3_stacker_control.py l2_factoryio/test_f3_stacker_control.py
git diff --cached --name-only
```

Expected: 只有上述两个文件。

- [ ] **Step 3: 提交并推送安全基线**

Run:

```powershell
git commit -m "F3安全基线:固化落稳动作与离线回归"
git push
```

Expected: commit/push 成功；其他用户/Claude 脏文件仍未暂存。

## Task 2: 以 TDD 建立统一任务契约和 400→54 映射

**Files:**
- Create: `l2_factoryio/test_task_contract.py`
- Create: `l2_factoryio/task_contract.py`

- [ ] **Step 1: 写失败测试**

Create `l2_factoryio/test_task_contract.py`:

```python
import unittest

from task_contract import (
    MAPPING_VERSION,
    Operation,
    WarehouseTask,
    map_logical_to_physical,
)


class MappingTests(unittest.TestCase):
    def test_four_corners_map_to_nine_by_six_corners(self):
        self.assertEqual(map_logical_to_physical(0), 1)
        self.assertEqual(map_logical_to_physical(19), 9)
        self.assertEqual(map_logical_to_physical(380), 46)
        self.assertEqual(map_logical_to_physical(399), 54)

    def test_mapping_is_monotonic_on_each_axis(self):
        bottom = [map_logical_to_physical(col) for col in range(20)]
        left = [map_logical_to_physical(tier * 20) for tier in range(20)]
        self.assertEqual(bottom, sorted(bottom))
        self.assertEqual(left, sorted(left))

    def test_mapping_rejects_out_of_range_logical_cell(self):
        for invalid in (-1, 400):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    map_logical_to_physical(invalid)


class WarehouseTaskTests(unittest.TestCase):
    def test_operation_requires_the_correct_cells(self):
        WarehouseTask(1, 1, Operation.INBOUND, 7, logical_target=399)
        WarehouseTask(2, 2, Operation.OUTBOUND, 7, logical_source=0)
        WarehouseTask(
            3, 3, Operation.DUAL, 7,
            logical_source=0, logical_target=399,
        )
        with self.assertRaises(ValueError):
            WarehouseTask(4, 4, Operation.INBOUND, 7)
        with self.assertRaises(ValueError):
            WarehouseTask(5, 5, Operation.OUTBOUND, 7)

    def test_physical_cells_are_derived_not_supplied(self):
        task = WarehouseTask(
            9, 12, Operation.DUAL, 88,
            logical_source=0, logical_target=399,
            strategy_id=3, reason_code=17,
        )
        self.assertEqual(task.physical_source, 1)
        self.assertEqual(task.physical_target, 54)
        self.assertEqual(task.mapping_version, MAPPING_VERSION)

    def test_round_trip_preserves_contract(self):
        task = WarehouseTask(
            9, 12, Operation.DUAL, 88,
            logical_source=21, logical_target=378,
            strategy_id=3, reason_code=17,
        )
        self.assertEqual(WarehouseTask.from_dict(task.to_dict()), task)

    def test_ids_must_be_positive(self):
        with self.assertRaises(ValueError):
            WarehouseTask(0, 1, Operation.INBOUND, 1, logical_target=1)
        with self.assertRaises(ValueError):
            WarehouseTask(1, 0, Operation.INBOUND, 1, logical_target=1)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试确认因模块不存在而失败**

Run:

```powershell
Set-Location F:\abb_wh_work\l2_factoryio
python -m unittest -v test_task_contract.py
```

Expected: `ModuleNotFoundError: No module named 'task_contract'`。

- [ ] **Step 3: 实现最小契约**

Create `l2_factoryio/task_contract.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, IntEnum
from typing import Any


MAPPING_VERSION = "grid20x20_to_grid9x6_v1"


class Operation(IntEnum):
    INBOUND = 1
    OUTBOUND = 2
    DUAL = 3


class TaskStatus(IntEnum):
    QUEUED = 0
    DISPATCHED = 1
    ACKED = 2
    RUNNING = 3
    DONE = 4
    FAULT = 5


class FaultCode(str, Enum):
    NONE = "NONE"
    ESTOP = "ESTOP"
    STOP = "STOP"
    DROPPED_LOAD = "DROPPED_LOAD"
    CARGO_LOST = "CARGO_LOST"
    COLLISION_OR_STALL = "COLLISION_OR_STALL"
    TIMEOUT = "TIMEOUT"
    IO_ERROR = "IO_ERROR"
    CONTRACT_ERROR = "CONTRACT_ERROR"
    SAFE_STOP_FAILED = "SAFE_STOP_FAILED"


def _validate_logical_cell(logical_cell: int) -> None:
    if not 0 <= logical_cell < 400:
        raise ValueError(f"logical cell must be 0..399, got {logical_cell}")


def map_logical_to_physical(logical_cell: int) -> int:
    _validate_logical_cell(logical_cell)
    logical_tier, logical_col = divmod(logical_cell, 20)
    physical_col = (logical_col * 8 + 9) // 19
    physical_tier = (logical_tier * 5 + 9) // 19
    return physical_tier * 9 + physical_col + 1


@dataclass(frozen=True)
class WarehouseTask:
    task_id: int
    request_seq: int
    operation: Operation
    goods_id: int
    logical_source: int | None = None
    logical_target: int | None = None
    strategy_id: int = 0
    reason_code: int = 0
    mapping_version: str = MAPPING_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "operation", Operation(self.operation))
        if self.task_id <= 0:
            raise ValueError(f"task_id must be positive, got {self.task_id}")
        if self.request_seq <= 0:
            raise ValueError(
                f"request_seq must be positive, got {self.request_seq}"
            )
        if self.goods_id <= 0:
            raise ValueError(f"goods_id must be positive, got {self.goods_id}")
        if self.mapping_version != MAPPING_VERSION:
            raise ValueError(f"unsupported mapping_version: {self.mapping_version}")
        if self.logical_source is not None:
            _validate_logical_cell(self.logical_source)
        if self.logical_target is not None:
            _validate_logical_cell(self.logical_target)
        if self.operation is Operation.INBOUND and self.logical_target is None:
            raise ValueError("INBOUND requires logical_target")
        if self.operation is Operation.OUTBOUND and self.logical_source is None:
            raise ValueError("OUTBOUND requires logical_source")
        if self.operation is Operation.DUAL:
            if self.logical_source is None or self.logical_target is None:
                raise ValueError("DUAL requires logical_source and logical_target")

    @property
    def physical_source(self) -> int | None:
        if self.logical_source is None:
            return None
        return map_logical_to_physical(self.logical_source)

    @property
    def physical_target(self) -> int | None:
        if self.logical_target is None:
            return None
        return map_logical_to_physical(self.logical_target)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "request_seq": self.request_seq,
            "operation": int(self.operation),
            "goods_id": self.goods_id,
            "logical_source": self.logical_source,
            "logical_target": self.logical_target,
            "physical_source": self.physical_source,
            "physical_target": self.physical_target,
            "strategy_id": self.strategy_id,
            "reason_code": self.reason_code,
            "mapping_version": self.mapping_version,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "WarehouseTask":
        return cls(
            task_id=int(payload["task_id"]),
            request_seq=int(payload["request_seq"]),
            operation=Operation(int(payload["operation"])),
            goods_id=int(payload["goods_id"]),
            logical_source=payload.get("logical_source"),
            logical_target=payload.get("logical_target"),
            strategy_id=int(payload.get("strategy_id", 0)),
            reason_code=int(payload.get("reason_code", 0)),
            mapping_version=str(payload.get("mapping_version", MAPPING_VERSION)),
        )
```

- [ ] **Step 4: 运行契约测试**

Run:

```powershell
python -m unittest -v test_task_contract.py
```

Expected: `Ran 7 tests` 和 `OK`。

- [ ] **Step 5: 提交并推送契约门**

Run:

```powershell
Set-Location F:\abb_wh_work
git add -- l2_factoryio/task_contract.py l2_factoryio/test_task_contract.py
git diff --cached --name-only
git commit -m "C1契约:冻结三类任务与400到54映射"
git push
```

Expected: 暂存只有两个契约文件；commit/push 成功。

## Task 3: 以 TDD 建立追加式事件日志

**Files:**
- Create: `l2_factoryio/test_event_log.py`
- Create: `l2_factoryio/event_log.py`

- [ ] **Step 1: 写失败测试**

Create `l2_factoryio/test_event_log.py`:

```python
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
            self.assertEqual(len(path.read_text(encoding="utf-8").splitlines()), 2)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m unittest -v test_event_log.py`  
Expected: `ModuleNotFoundError: No module named 'event_log'`。

- [ ] **Step 3: 实现事件记录和 JSONL 仓库**

Create `l2_factoryio/event_log.py`:

```python
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
            fault_code=FaultCode(payload.get("fault_code", FaultCode.NONE.value)),
            message=str(payload.get("message", "")),
        )


class JsonlEventLog:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def append(self, event: TaskEvent) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(event.to_dict(), ensure_ascii=False, sort_keys=True)
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
                except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                    raise ValueError(
                        f"invalid event at {self.path}:{line_number}: {exc}"
                    ) from exc
        return events
```

- [ ] **Step 4: 运行事件日志测试**

Run: `python -m unittest -v test_event_log.py`  
Expected: `Ran 1 test` 和 `OK`。

- [ ] **Step 5: 提交并推送事件证据门**

Run:

```powershell
Set-Location F:\abb_wh_work
git add -- l2_factoryio/event_log.py l2_factoryio/test_event_log.py
git commit -m "C1事件:增加同源JSONL任务证据"
git push
```

Expected: 只提交事件日志和测试。

## Task 4: 以 TDD 实现三任务离线编排器

**Files:**
- Create: `l2_factoryio/test_task_orchestrator.py`
- Create: `l2_factoryio/task_orchestrator.py`

- [ ] **Step 1: 写 FakeAdapter 行为测试**

Create `l2_factoryio/test_task_orchestrator.py`:

```python
import tempfile
import unittest
from pathlib import Path

from event_log import JsonlEventLog
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

    def feed(self): self._do("feed")
    def pick_load(self): self._do("pick_load")
    def store(self, cell): self._do(f"store:{cell}")
    def retrieve(self, cell): self._do(f"retrieve:{cell}")
    def go_rest(self): self._do("go_rest")
    def unload(self): self._do("unload")

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
            3, 3, Operation.DUAL, 9,
            logical_source=0, logical_target=399,
        )
        adapter, _, result, _ = self.run_task(task)
        self.assertEqual(
            adapter.actions,
            [
                "feed", "pick_load", "store:54", "retrieve:1",
                "go_rest", "unload", "go_rest",
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
        self.assertEqual(adapter.actions, ["feed", "pick_load", "store:1", "go_rest"])

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
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m unittest -v test_task_orchestrator.py`  
Expected: `ModuleNotFoundError: No module named 'task_orchestrator'`。

- [ ] **Step 3: 实现设备协议、阶段计划和故障收口**

Create `l2_factoryio/task_orchestrator.py`:

```python
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

    def _plan(self, task: WarehouseTask) -> list[tuple[str, Callable[[], None]]]:
        if task.operation is Operation.INBOUND:
            return [
                ("FEED", self.adapter.feed),
                ("PICK_LOAD", self.adapter.pick_load),
                ("STORE_TARGET", lambda: self.adapter.store(task.physical_target)),
                ("RETURN_REST", self.adapter.go_rest),
            ]
        if task.operation is Operation.OUTBOUND:
            return [
                ("RETRIEVE_SOURCE", lambda: self.adapter.retrieve(task.physical_source)),
                ("RETURN_IO", self.adapter.go_rest),
                ("UNLOAD", self.adapter.unload),
                ("RETURN_REST", self.adapter.go_rest),
            ]
        return [
            ("FEED", self.adapter.feed),
            ("PICK_LOAD", self.adapter.pick_load),
            ("STORE_TARGET", lambda: self.adapter.store(task.physical_target)),
            ("RETRIEVE_SOURCE", lambda: self.adapter.retrieve(task.physical_source)),
            ("RETURN_IO", self.adapter.go_rest),
            ("UNLOAD", self.adapter.unload),
            ("RETURN_REST", self.adapter.go_rest),
        ]

    def execute(self, task: WarehouseTask) -> ExecutionResult:
        previous = self._results_by_request.get(task.request_seq)
        if previous is not None:
            return ExecutionResult(
                task_id=previous.task_id,
                request_seq=previous.request_seq,
                status=previous.status,
                fault_code=previous.fault_code,
                duplicate=True,
                safe_stop_failed=previous.safe_stop_failed,
            )

        self._emit(task, TaskStatus.DISPATCHED, "DISPATCH")
        self._emit(task, TaskStatus.ACKED, "ACK")
        self._emit(task, TaskStatus.RUNNING, "START")
        try:
            for phase, action in self._plan(task):
                self._emit(task, TaskStatus.RUNNING, phase)
                action()
        except AdapterFault as exc:
            stop_failed = False
            stop_message = ""
            try:
                self.adapter.safe_stop()
            except Exception as stop_exc:
                stop_failed = True
                stop_message = str(stop_exc)
            result = ExecutionResult(
                task.task_id,
                task.request_seq,
                TaskStatus.FAULT,
                exc.code,
                safe_stop_failed=stop_failed,
            )
            self._emit(
                task, TaskStatus.FAULT, "SAFE_STOP",
                fault_code=exc.code, message=str(exc),
            )
            if stop_failed:
                self._emit(
                    task, TaskStatus.FAULT, "SAFE_STOP_FAILED",
                    fault_code=FaultCode.SAFE_STOP_FAILED,
                    message=stop_message,
                )
            self._results_by_request[task.request_seq] = result
            return result
        except Exception as exc:
            try:
                self.adapter.safe_stop()
                stop_failed = False
            except Exception:
                stop_failed = True
            result = ExecutionResult(
                task.task_id,
                task.request_seq,
                TaskStatus.FAULT,
                FaultCode.IO_ERROR,
                safe_stop_failed=stop_failed,
            )
            self._emit(
                task, TaskStatus.FAULT, "SAFE_STOP",
                fault_code=FaultCode.IO_ERROR, message=str(exc),
            )
            self._results_by_request[task.request_seq] = result
            return result

        result = ExecutionResult(task.task_id, task.request_seq, TaskStatus.DONE)
        self._emit(task, TaskStatus.DONE, "COMPLETE")
        self._results_by_request[task.request_seq] = result
        return result
```

- [ ] **Step 4: 运行全套 C0–C2 离线测试**

Run:

```powershell
Set-Location F:\abb_wh_work\l2_factoryio
python -m py_compile task_contract.py event_log.py task_orchestrator.py
python -m unittest -v test_f3_stacker_control.py test_task_contract.py test_event_log.py test_task_orchestrator.py
```

Expected: `Ran 20 tests` 和 `OK`。

- [ ] **Step 5: 提交并推送离线编排门**

Run:

```powershell
Set-Location F:\abb_wh_work
git add -- l2_factoryio/task_orchestrator.py l2_factoryio/test_task_orchestrator.py
git commit -m "C2编排:离线打通入库出库双命令"
git push
```

Expected: 只提交编排器和测试。

## Task 5: 更新唯一账本并签发下一门

**Files:**
- Modify: `docs/overnight2-report_0712night.md`

- [ ] **Step 1: 在任务队列下追加路径 C 变更说明**

Add:

```markdown
### 0713 用户改拍：Factory I/O 路径 C + 保留自研 3D

- 原 F3“三箱快线→F4 OPC→F5 联调”改为 C0 安全门→C1 契约门→C2 离线编排门→C3 AB 握手门→C4 单任务在线门→C5 三任务在线门→C6 同源 3D 门。
- AB 保持 20×20 业务真相源；Python 仅做 400→54 显式代表映射、设备适配和 safe-stop；Factory I/O 不称 400 格物理孪生。
- 下一步先完成 F3 现场碰撞门，再进入 AB OPC UA，禁止越门录正式素材。
```

- [ ] **Step 2: 追加实际 commit 和测试结果**

Run:

```powershell
git log -4 --oneline
Set-Location F:\abb_wh_work\l2_factoryio
python -m unittest -v test_f3_stacker_control.py test_task_contract.py test_event_log.py test_task_orchestrator.py
```

Expected: 根据上述输出追加一条“C0–C2 实际结果”记录，逐项写入真实 commit 短哈希、真实测试数和 `OK`；不预写绿灯。

- [ ] **Step 3: 精确提交账本**

Run:

```powershell
Set-Location F:\abb_wh_work
git add -- docs/overnight2-report_0712night.md
git commit -m "overnight2:路径C门禁节奏与C0-C2结果落账"
git push
```

Expected: 只提交唯一账本。

## 计划自审结论

- 规格覆盖：本计划覆盖 C0 安全代码基线、C1 契约/映射/事件和 C2 三任务离线编排；C3 AB ST/OPC、C4–C5 在线动作和 C6 3D EventSource 各自在前置门通过后另起计划。
- 无占位：每个代码步骤给出完整内容、命令和预期；账本绿灯必须由实际测试回填。
- 类型一致：`Operation`、`TaskStatus`、`FaultCode`、`WarehouseTask`、`TaskEvent` 和 `ExecutionResult` 在四个模块中名称一致；logical 统一 0..399，physical 统一 1..54。
- 风险边界：当前编排器只记录故障并 safe-stop，不实施自动物理重试；一次自动重试要等真实 Adapter 能证明 rest/middle/无载荷后再加，符合“未知载荷不盲目重放”的安全原则。
