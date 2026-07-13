# -*- coding: utf-8 -*-
"""Factory I/O F3 的跨进程 fail-closed 状态门（H1.1）。

本模块只提供软件级互斥与可恢复证据，不冒充功能安全 PLC：

- 状态文件缺失、损坏、旧 schema、cargo_trust!=True、未完成事务均锁定；
- Windows/POSIX 进程锁覆盖“判锁 -> 动作 -> 状态提交”，避免 lost update/TOCTOU；
- 所有设备写入口必须处于 command_guard 租约内；
- 写设备前记录 transition_pending，正常完成后才清除；进程强杀会留下锁；
- reset-epoch 仍是人工重启声明，不声称能从 API 机器证明应用重启。
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

STATE_FILENAME = "fault_state.json"
LOCK_FILENAME = "fault_state.lock"
AUDIT_FILENAME = "fault_events.jsonl"
STATE_SCHEMA_VERSION = 2
DEFAULT_LOCK_TIMEOUT = 5.0

# stop 模式只可执行保守撤险写：Target=0、输送带/Lift=False；C2/C3=False
# 在 Factory I/O 中是主动回中，故永不列入此白名单。
SAFE_STOP_FALSE_COILS = frozenset((0, 1, 4, 5, 6))

FAULT_LOWER_NO_START = "LOWER_NO_START"
FAULT_LIFT_POSITION_UNKNOWN = "LIFT_POSITION_UNKNOWN"
FAULT_CARGO_LOST = "CARGO_LOST"
FAULT_RECOVERY_UNSAFE = "RECOVERY_UNSAFE"
FAULT_COMMAND_ABORTED = "COMMAND_ABORTED"
FAULT_SAFE_STOP_UNCONFIRMED = "SAFE_STOP_UNCONFIRMED"
FAULT_FORK_STATE_AMBIGUOUS = "FORK_STATE_AMBIGUOUS"
FAULT_EMITTER_STATE_UNKNOWN = "EMITTER_STATE_UNKNOWN"
KNOWN_FAULTS = (
    FAULT_LOWER_NO_START,
    FAULT_LIFT_POSITION_UNKNOWN,
    FAULT_CARGO_LOST,
    FAULT_RECOVERY_UNSAFE,
    FAULT_COMMAND_ABORTED,
    FAULT_SAFE_STOP_UNCONFIRMED,
    FAULT_FORK_STATE_AMBIGUOUS,
    FAULT_EMITTER_STATE_UNKNOWN,
)

# 这些命令在锁定态仍可用于取证、保守停机或创建新 epoch。
LOCKED_ALLOWED_MODES = {
    "snapshot",
    "stop",
    "mark-fault",
    "reset-epoch",
    "emitter-off",
    "emitter-status",
}

_LOCAL_LOCKS: dict[str, threading.RLock] = {}
_LOCAL_LOCKS_GUARD = threading.Lock()
_TLS = threading.local()


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def default_state_path() -> Path:
    return Path(__file__).resolve().parent / STATE_FILENAME


def _lock_path(path: Path) -> Path:
    return path.with_name(LOCK_FILENAME)


def audit_path(path: Path | None = None) -> Path:
    return (path or default_state_path()).with_name(AUDIT_FILENAME)


def _path_key(path: Path) -> str:
    return str(path.resolve()).casefold()


def _local_lock_for(key: str) -> threading.RLock:
    with _LOCAL_LOCKS_GUARD:
        return _LOCAL_LOCKS.setdefault(key, threading.RLock())


def _open_and_lock(lock_path: Path, timeout: float):
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    # a+b 原子地“存在则打开、缺失则创建”，避免两个首启进程在
    # r+b -> w+b 窗口互相截断锁文件。
    stream = lock_path.open("a+b")
    stream.seek(0, os.SEEK_END)
    if stream.tell() == 0:
        stream.write(b"\0")
        stream.flush()
        os.fsync(stream.fileno())
    deadline = time.monotonic() + timeout
    while True:
        try:
            stream.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return stream
        except OSError as exc:
            if time.monotonic() >= deadline:
                stream.close()
                raise TimeoutError(
                    f"command lease timeout after {timeout:.1f}s: {lock_path}"
                ) from exc
            time.sleep(0.05)


def _unlock_and_close(stream) -> None:
    try:
        stream.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
    finally:
        stream.close()


@contextmanager
def interprocess_lock(path: Path | None = None, *, timeout: float = DEFAULT_LOCK_TIMEOUT):
    """同线程可重入、跨线程/进程互斥的状态文件租约。"""
    state_path = path or default_state_path()
    key = _path_key(state_path)
    local_lock = _local_lock_for(key)
    if timeout < 0:
        raise ValueError("lock timeout must be non-negative")
    deadline = time.monotonic() + timeout
    if not local_lock.acquire(timeout=timeout):
        raise TimeoutError(
            f"command lease timeout after {timeout:.1f}s: {_lock_path(state_path)}"
        )
    depths = getattr(_TLS, "lock_depths", None)
    if depths is None:
        depths = _TLS.lock_depths = {}
    handles = getattr(_TLS, "lock_handles", None)
    if handles is None:
        handles = _TLS.lock_handles = {}
    try:
        if depths.get(key, 0):
            depths[key] += 1
            try:
                yield state_path
            finally:
                depths[key] -= 1
            return
        remaining = max(0.0, deadline - time.monotonic())
        stream = _open_and_lock(_lock_path(state_path), remaining)
        depths[key] = 1
        handles[key] = stream
        try:
            yield state_path
        finally:
            depths.pop(key, None)
            handles.pop(key, None)
            _unlock_and_close(stream)
    finally:
        local_lock.release()


def _load_error(kind: str, **details) -> dict:
    return {"_load_error": kind, **details}


def load_state(path: Path | None = None) -> dict:
    """读取并校验 schema；任何不可证明状态都返回 fail-closed 标记。"""
    p = path or default_state_path()
    if not p.exists():
        return _load_error("missing", path=str(p))
    try:
        with p.open("r", encoding="utf-8") as stream:
            data = json.load(stream)
    except (json.JSONDecodeError, OSError) as exc:
        return _load_error("corrupt", error=str(exc), path=str(p))
    if not isinstance(data, dict):
        return _load_error("invalid_type", raw_type=type(data).__name__)
    if data.get("schema_version") != STATE_SCHEMA_VERSION:
        return _load_error(
            "schema",
            expected=STATE_SCHEMA_VERSION,
            found=data.get("schema_version"),
            raw_state=data,
        )
    revision = data.get("revision")
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 0:
        return _load_error("revision", found=revision, raw_state=data)
    if not isinstance(data.get("cargo_trust"), bool):
        return _load_error("cargo_trust", found=data.get("cargo_trust"), raw_state=data)
    return data


def _atomic_write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=path.stem + "_", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _append_audit(
    state_path: Path,
    *,
    event_type: str,
    revision: int,
    payload: dict,
    actor: str = "process",
) -> None:
    """只追加、fsync 的 H1 事件证据；调用方必须已持有状态租约。"""
    stack = getattr(_TLS, "command_stack", None) or []
    mode = stack[-1][0] if stack and stack[-1][1] == _path_key(state_path) else None
    event = {
        "event_id": uuid.uuid4().hex,
        "recorded_at": _now(),
        "event_type": event_type,
        "revision": revision,
        "actor": actor,
        "pid": os.getpid(),
        "command_mode": mode,
        "payload": payload,
    }
    p = audit_path(state_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(event, ensure_ascii=False, sort_keys=True)
    with p.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(line + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def _base_revision(state: dict) -> int:
    revision = state.get("revision")
    return revision if isinstance(revision, int) and not isinstance(revision, bool) else 0


def _commit(path: Path, state: dict, *, previous_revision: int) -> dict:
    state["schema_version"] = STATE_SCHEMA_VERSION
    state["revision"] = previous_revision + 1
    _atomic_write(path, state)
    return state


def is_locked(state: dict) -> bool:
    return (
        bool(state.get("_load_error"))
        or state.get("cargo_trust") is not True
        or bool(state.get("fault"))
        or bool(state.get("transition_pending"))
    )


def lock_reason(state: dict) -> str:
    if state.get("_load_error"):
        return (
            f"state unavailable/invalid ({state['_load_error']}): "
            f"{state.get('error', state.get('path', state.get('found', 'unknown')))}"
        )
    fault = state.get("fault") or {}
    if fault:
        return (
            f"persistent fault {fault.get('code', '?')} at cell "
            f"{fault.get('cell', '?')} ({fault.get('recorded_at', '?')}): "
            f"{fault.get('detail', '')}"
        )
    pending = state.get("transition_pending") or {}
    if pending:
        return (
            f"unfinished transition {pending.get('action', '?')} "
            f"({pending.get('started_at', '?')}, token={pending.get('token', '?')})"
        )
    if state.get("cargo_trust") is not True:
        return "cargo_trust is not explicitly true"
    return "unlocked"


def assert_mode_allowed(mode: str, *, path: Path | None = None) -> dict:
    state = load_state(path)
    if is_locked(state) and mode not in LOCKED_ALLOWED_MODES:
        raise RuntimeError(
            "PERSISTENT FAULT LOCK ACTIVE -> " + lock_reason(state)
            + "; only snapshot/stop/mark-fault/reset-epoch/emitter-off are allowed"
        )
    return state


@contextmanager
def command_guard(
    mode: str,
    *,
    path: Path | None = None,
    timeout: float = DEFAULT_LOCK_TIMEOUT,
):
    """持有整个设备命令的跨进程租约，并建立低层写许可。"""
    p = path or default_state_path()
    with interprocess_lock(p, timeout=timeout):
        state = assert_mode_allowed(mode, path=p)
        stack = getattr(_TLS, "command_stack", None)
        if stack is None:
            stack = _TLS.command_stack = []
        stack.append((mode, _path_key(p)))
        try:
            yield state
        finally:
            stack.pop()


def require_command_session(*, path: Path | None = None) -> str:
    stack = getattr(_TLS, "command_stack", None) or []
    if not stack:
        raise RuntimeError(
            "device write rejected: no command_guard lease (global fault lock bypass)"
        )
    mode, key = stack[-1]
    expected_key = _path_key(path or default_state_path())
    if key != expected_key:
        raise RuntimeError("device write rejected: command lease belongs to another state file")
    return mode


def assert_device_write_allowed(
    kind: str,
    *,
    address: int | None = None,
    value: object = None,
    path: Path | None = None,
) -> str:
    """按命令能力与 write-ahead pending 双重授权低层设备写。"""
    p = path or default_state_path()
    mode = require_command_session(path=p)

    if mode == "stop":
        target_zero = (
            kind == "modbus-target"
            and isinstance(value, int)
            and not isinstance(value, bool)
            and value == 0
        )
        safe_false_coil = (
            kind == "modbus-coil"
            and address in SAFE_STOP_FALSE_COILS
            and value is False
        )
        if target_zero or safe_false_coil:
            return mode
        raise RuntimeError(
            f"device write rejected: stop capability forbids {kind} "
            f"address={address} value={value!r}"
        )

    if mode == "emitter-off":
        if kind == "emitter" and value is False:
            return mode
        raise RuntimeError(
            f"device write rejected: emitter-off capability forbids {kind} "
            f"value={value!r}"
        )

    state = load_state(p)
    pending = state.get("transition_pending") or {}
    if pending.get("command_mode") != mode:
        raise RuntimeError(
            "device write rejected: no matching write-ahead transition_pending "
            f"for command mode {mode}"
        )

    if mode in {"diagnose", "mechanics-probe"} and kind in {
        "modbus-coil", "modbus-target",
    }:
        return mode
    if mode == "emitter-pulse" and kind == "emitter":
        return mode
    raise RuntimeError(
        f"device write rejected: command mode {mode} has no {kind} capability"
    )


def record_fault(
    code: str,
    *,
    cell: int | None,
    detail: str,
    context: dict | None = None,
    path: Path | None = None,
) -> dict:
    """记录主故障；后续故障进入 history，不覆盖最早未清故障。"""
    if code not in KNOWN_FAULTS:
        raise ValueError(f"unknown fault code: {code}")
    p = path or default_state_path()
    with interprocess_lock(p):
        old = load_state(p)
        previous_revision = _base_revision(old)
        if old.get("_load_error"):
            state = {
                "schema_version": STATE_SCHEMA_VERSION,
                "revision": previous_revision,
                "cargo_trust": False,
                "previous_state_issue": lock_reason(old),
                "previous_raw_state": old.get("raw_state"),
            }
        else:
            state = dict(old)
        entry = {
            "code": code,
            "cell": cell,
            "detail": detail,
            "recorded_at": _now(),
            "context": context or {},
        }
        history = list(state.get("fault_history") or [])
        history.append(entry)
        state["fault_history"] = history
        if not state.get("fault"):
            state["fault"] = entry
        else:
            state["latest_fault"] = entry
        state["cargo_trust"] = False
        committed = _commit(p, state, previous_revision=previous_revision)
        # fault 当前态先落盘，审计失败也不能让安全锁失效。
        _append_audit(
            p,
            event_type="fault-recorded",
            revision=committed["revision"],
            payload=entry,
        )
        return committed


def record_phase_state(
    *,
    phase: str,
    cell: int | None,
    load_state_value: str,
    fork_hold: int | None,
    lift_command: bool | None,
    transition_token: str | None = None,
    path: Path | None = None,
) -> dict:
    """记录正常相位交接；不清故障或 pending。"""
    mode = require_command_session(path=path)
    if mode != "diagnose":
        raise RuntimeError(f"phase write requires diagnose lease, found {mode}")
    p = path or default_state_path()
    with interprocess_lock(p):
        state = load_state(p)
        if state.get("_load_error") or state.get("fault") or state.get("cargo_trust") is not True:
            raise RuntimeError("refusing phase write on locked state: " + lock_reason(state))
        pending = state.get("transition_pending") or {}
        if not transition_token or pending.get("token") != transition_token:
            raise RuntimeError("phase write transition token mismatch")
        if pending.get("command_mode") != mode:
            raise RuntimeError("phase write command mode mismatch")
        previous_revision = _base_revision(state)
        state = dict(state)
        state["last_phase"] = {
            "phase": phase,
            "cell": cell,
            "load_state": load_state_value,
            "fork_hold": fork_hold,
            "lift_command": lift_command,
            "recorded_at": _now(),
        }
        _append_audit(
            p,
            event_type="phase-observed",
            revision=previous_revision + 1,
            payload=dict(state["last_phase"]),
        )
        return _commit(p, state, previous_revision=previous_revision)


def require_last_phase(
    expected_phase: str,
    *,
    cell: int | None,
    load_state_value: str | None = None,
    fork_hold: int | None = None,
    lift_command: bool | None = None,
    path: Path | None = None,
) -> dict:
    """消费跨进程门的最小证据；现场 snapshot 仍须由控制器再次验证。"""
    state = load_state(path)
    if is_locked(state):
        raise RuntimeError("cannot consume phase on locked state: " + lock_reason(state))
    phase = state.get("last_phase") or {}
    problems = []
    if phase.get("phase") != expected_phase:
        problems.append(f"phase={phase.get('phase')} expected={expected_phase}")
    if phase.get("cell") != cell:
        problems.append(f"cell={phase.get('cell')} expected={cell}")
    if load_state_value is not None and phase.get("load_state") != load_state_value:
        problems.append(
            f"load_state={phase.get('load_state')} expected={load_state_value}"
        )
    if fork_hold is not None and phase.get("fork_hold") != fork_hold:
        problems.append(f"fork_hold={phase.get('fork_hold')} expected={fork_hold}")
    if lift_command is not None and phase.get("lift_command") is not lift_command:
        problems.append(
            f"lift_command={phase.get('lift_command')} expected={lift_command}"
        )
    if problems:
        raise RuntimeError("persisted phase gate failed: " + "; ".join(problems))
    return phase


def begin_transition(
    action: str,
    *,
    cell: int | None,
    context: dict | None = None,
    path: Path | None = None,
) -> str:
    """设备写前 durable intent；强杀会留下 transition_pending 锁。"""
    mode = require_command_session(path=path)
    valid_action = (
        (mode == "diagnose" and action.startswith("diagnose:"))
        or (mode == "mechanics-probe" and action.startswith("mechanics-probe:"))
        or (mode == "emitter-pulse" and action == "emitter-pulse")
        or (mode == "stop" and action == "safe-stop")
    )
    if not valid_action:
        raise RuntimeError(
            f"transition action {action!r} is not authorized by command mode {mode!r}"
        )
    p = path or default_state_path()
    with interprocess_lock(p):
        state = load_state(p)
        if is_locked(state):
            raise RuntimeError("cannot begin transition on locked state: " + lock_reason(state))
        token = uuid.uuid4().hex
        previous_revision = _base_revision(state)
        state = dict(state)
        state["transition_pending"] = {
            "token": token,
            "action": action,
            "cell": cell,
            "started_at": _now(),
            "command_mode": mode,
            "epoch_id": state.get("epoch_id"),
            "base_revision": previous_revision,
            "context": context or {},
        }
        _append_audit(
            p,
            event_type="transition-intent",
            revision=previous_revision + 1,
            payload=dict(state["transition_pending"]),
        )
        _commit(p, state, previous_revision=previous_revision)
        return token


def complete_transition(token: str, *, path: Path | None = None) -> dict:
    mode = require_command_session(path=path)
    p = path or default_state_path()
    with interprocess_lock(p):
        state = load_state(p)
        if state.get("_load_error"):
            raise RuntimeError("transition completion lost state: " + lock_reason(state))
        pending = state.get("transition_pending") or {}
        if pending.get("token") != token:
            raise RuntimeError("transition completion token mismatch")
        if pending.get("command_mode") != mode:
            raise RuntimeError(
                f"transition completion lease mismatch: pending="
                f"{pending.get('command_mode')} current={mode}"
            )
        if state.get("fault") or state.get("cargo_trust") is not True:
            raise RuntimeError("refusing to clear transition after fault")
        previous_revision = _base_revision(state)
        state = dict(state)
        finished = dict(pending)
        finished["completed_at"] = _now()
        state["last_transition"] = finished
        state.pop("transition_pending", None)
        # 先追加“完成请求”再清 pending；审计写失败时仍保持 fail-closed。
        _append_audit(
            p,
            event_type="transition-complete-request",
            revision=previous_revision + 1,
            payload=finished,
        )
        return _commit(p, state, previous_revision=previous_revision)


def clear_for_new_epoch(
    *,
    operator_confirmed_restart: bool,
    preflight_passed: bool,
    visual_empty_confirmed: bool,
    emitter_off_confirmed: bool,
    note: str,
    path: Path | None = None,
) -> dict:
    """人工确认完整重启后的唯一解锁路径；不声称机器验证了重启。"""
    if not operator_confirmed_restart:
        raise RuntimeError(
            "reset-epoch requires --operator-confirmed-restart; this is an "
            "operator attestation, not machine-verifiable restart evidence"
        )
    if not preflight_passed:
        raise RuntimeError("reset-epoch requires a passing online empty-scene preflight")
    if not visual_empty_confirmed:
        raise RuntimeError("reset-epoch requires --confirm-visual-empty")
    if not emitter_off_confirmed:
        raise RuntimeError("reset-epoch requires --confirm-emitter-off")
    if not note.strip():
        raise RuntimeError("reset-epoch requires --note with screenshot/video evidence path")
    mode = require_command_session(path=path)
    if mode != "reset-epoch":
        raise RuntimeError(f"epoch reset requires reset-epoch lease, found {mode}")
    p = path or default_state_path()
    with interprocess_lock(p):
        old = load_state(p)
        previous_revision = _base_revision(old)
        old_history = [] if old.get("_load_error") else list(old.get("fault_history") or [])
        reset_history = [] if old.get("_load_error") else list(old.get("reset_history") or [])
        reset_entry = {
            "epoch_started_at": _now(),
            "epoch_id": uuid.uuid4().hex,
            "restart_evidence": "operator-attested-only",
            "visual_empty_confirmed": True,
            "emitter_off_confirmed": True,
            "note": note.strip(),
            "cleared_fault": None if old.get("_load_error") else old.get("fault"),
            "cleared_transition": None
            if old.get("_load_error")
            else old.get("transition_pending"),
            "cleared_state_issue": lock_reason(old) if old.get("_load_error") else None,
            "cleared_raw_state": old.get("raw_state") if old.get("_load_error") else None,
        }
        reset_history.append(reset_entry)
        state = {
            "schema_version": STATE_SCHEMA_VERSION,
            "revision": previous_revision,
            "epoch_id": reset_entry["epoch_id"],
            "epoch_started_at": reset_entry["epoch_started_at"],
            "restart_evidence": reset_entry["restart_evidence"],
            "cargo_trust": True,
            "fault_history": old_history,
            "reset_history": reset_history,
            "last_phase": None,
            "cleared_fault": reset_entry["cleared_fault"],
            "cleared_transition": reset_entry["cleared_transition"],
        }
        # reset 是唯一解锁写；审计必须先成功，失败时旧锁状态保持不变。
        _append_audit(
            p,
            event_type="epoch-reset-request",
            revision=previous_revision + 1,
            payload=reset_entry,
            actor="operator-attested",
        )
        return _commit(p, state, previous_revision=previous_revision)
