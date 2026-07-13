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
    """Map a 20x20 logical cell to a 9x6 representative FIO cell."""
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
