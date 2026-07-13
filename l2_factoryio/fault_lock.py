# -*- coding: utf-8 -*-
"""跨进程持久故障锁与现场状态文件（H1 门 2/4）。

背景（F3_现场故障与Claude接管_20260713.md §7.3）：
`RECOVERY_UNSAFE` 等故障状态此前只存在于进程内存；CLI 新进程可用
`--confirm-*` 人工旗标重新构造 CARRYING 绕过。本模块把故障与相位交接
状态持久化到 `fault_state.json`：

- 任一 NO_START / LIFT_POSITION_UNKNOWN / CARGO_LOST / RECOVERY_UNSAFE
  记录后 -> 锁定：后续任何 action 相位（含全部 --confirm-* 旗标）拒绝，
  只允许 snapshot / stop 取证。
- 解锁唯一路径：完整重启 Factory I/O 后运行 `reset-epoch`，且现场空场
  preflight 必须真实通过；清锁记录审计字段，不静默删除。

写入使用同目录临时文件 + os.replace 原子替换，避免半写状态。
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

STATE_FILENAME = "fault_state.json"

# 需要持久锁定的故障码
FAULT_LOWER_NO_START = "LOWER_NO_START"
FAULT_LIFT_POSITION_UNKNOWN = "LIFT_POSITION_UNKNOWN"
FAULT_CARGO_LOST = "CARGO_LOST"
FAULT_RECOVERY_UNSAFE = "RECOVERY_UNSAFE"
KNOWN_FAULTS = (
    FAULT_LOWER_NO_START,
    FAULT_LIFT_POSITION_UNKNOWN,
    FAULT_CARGO_LOST,
    FAULT_RECOVERY_UNSAFE,
)


def default_state_path() -> Path:
    return Path(__file__).resolve().parent / STATE_FILENAME


def load_state(path: Path | None = None) -> dict:
    """读状态文件；不存在或损坏都按“无记录”返回空 dict（损坏时附标记）。

    损坏文件不静默覆盖：返回 {"corrupt": True}，调用方必须按锁定处理，
    因为无法证明其中没有未消费的故障。
    """
    p = path or default_state_path()
    if not p.exists():
        return {}
    try:
        with p.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            return {"corrupt": True, "raw_type": type(data).__name__}
        return data
    except (json.JSONDecodeError, OSError) as exc:
        return {"corrupt": True, "error": str(exc)}


def _atomic_write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=path.stem + "_", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def is_locked(state: dict) -> bool:
    return bool(state.get("fault")) or bool(state.get("corrupt"))


def lock_reason(state: dict) -> str:
    if state.get("corrupt"):
        return f"state file corrupt: {state.get('error', 'unparseable')}"
    fault = state.get("fault") or {}
    return (
        f"persistent fault {fault.get('code', '?')} at cell "
        f"{fault.get('cell', '?')} ({fault.get('recorded_at', '?')}): "
        f"{fault.get('detail', '')}"
    )


def record_fault(
    code: str,
    *,
    cell: int | None,
    detail: str,
    context: dict | None = None,
    path: Path | None = None,
) -> dict:
    """写入持久故障并锁定。未知故障码直接拒绝，防拼写错误造成静默弱锁。"""
    if code not in KNOWN_FAULTS:
        raise ValueError(f"unknown fault code: {code}")
    p = path or default_state_path()
    state = load_state(p)
    if state.get("corrupt"):
        # 损坏文件本身已是锁定态；用全新结构覆盖并保留损坏事实。
        state = {"previous_corrupt": True}
    state["fault"] = {
        "code": code,
        "cell": cell,
        "detail": detail,
        "recorded_at": datetime.now().isoformat(timespec="seconds"),
        "context": context or {},
    }
    state["cargo_trust"] = False
    _atomic_write(p, state)
    return state


def record_phase_state(
    *,
    phase: str,
    cell: int | None,
    load_state_value: str,
    fork_hold: int | None,
    lift_command: bool | None,
    path: Path | None = None,
) -> dict:
    """记录正常相位交接状态（extended hold 等），供下一进程重建现场。

    不改动已存在的 fault 字段——故障只能由 reset-epoch 清除。
    """
    p = path or default_state_path()
    state = load_state(p)
    if state.get("corrupt"):
        raise RuntimeError(
            "refusing to write phase state over corrupt fault file; "
            "resolve manually: " + lock_reason(state)
        )
    state["last_phase"] = {
        "phase": phase,
        "cell": cell,
        "load_state": load_state_value,
        "fork_hold": fork_hold,
        "lift_command": lift_command,
        "recorded_at": datetime.now().isoformat(timespec="seconds"),
    }
    _atomic_write(p, state)
    return state


def clear_for_new_epoch(
    *,
    operator_confirmed_restart: bool,
    preflight_passed: bool,
    note: str = "",
    path: Path | None = None,
) -> dict:
    """reset-epoch：唯一的解锁路径。双条件缺一不可，清锁留审计记录。"""
    if not operator_confirmed_restart:
        raise RuntimeError(
            "reset-epoch requires --operator-confirmed-restart: only a FULL "
            "Factory I/O application restart (not F6) authorizes a new epoch"
        )
    if not preflight_passed:
        raise RuntimeError(
            "reset-epoch requires a passing empty-scene preflight; "
            "refusing to clear the fault lock"
        )
    p = path or default_state_path()
    old = load_state(p)
    state = {
        "epoch_started_at": datetime.now().isoformat(timespec="seconds"),
        "cargo_trust": True,
        "cleared_fault": old.get("fault"),
        "cleared_note": note,
    }
    _atomic_write(p, state)
    return state
