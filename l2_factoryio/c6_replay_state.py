"""C6 同源回放状态层（数据层，无渲染）。

把 `task_orchestrator` 产出的 `TaskEvent` JSONL（同源事件流）归约成
**逐帧仓库状态 + KPI**。C6「同源 JSONL 双视图」里，2D 仪表视图与 3D 视图
消费的是本层的同一份输出——保证两视图口径一致（同源）。

设计原则：
- **纯数据、确定性**：同一事件序列 → 同一时间线，可单测、可 diff。
- **设计无关**：不假设任何渲染栈；帧里只放"是什么状态"，不放"怎么画"。
- **不碰绿码**：只读 event_log / task_contract 的公开契约，不改 F3/orchestrator。

占用模型（保守、可解释）：
- 仓库初始占用由 `initial_occupancy` 显式给定（默认空仓）。
- 仅在任务 `status==DONE` 的那一刻改变占用（半途/FAULT 不改）：
  - INBOUND 完成 → 占用 `physical_target`；
  - OUTBOUND 完成 → 释放 `physical_source`；
  - DUAL   完成 → 先释放 `physical_source` 再占用 `physical_target`。
- 每个 (task_id, request_seq) 的 DONE 只结算一次（幂等，容忍事件流重复）。

堆垛机当前服务格（crane_cell）按 orchestrator 的**真实相位契约**精确映射
（来源=task_orchestrator._plan/execute 的相位常量），仅供视图定位，不参与占用结算：
- STORE_TARGET → physical_target；RETRIEVE_SOURCE → physical_source；
- 其余相位（DISPATCH/ACK/START/FEED/PICK_LOAD/RETURN_IO/UNLOAD/RETURN_REST/
  COMPLETE/SAFE_STOP*/未知）→ None——堆垛机不在货架格或位置不明，诚实不标。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Sequence

from event_log import TaskEvent
from task_contract import FaultCode, Operation, TaskStatus


# orchestrator 真实相位契约（task_orchestrator._plan/execute 的相位常量）中
# 唯二"堆垛机正在服务某个货架格"的相位；其余相位（含未知）诚实置 None。
_PHASE_AT_TARGET = "STORE_TARGET"
_PHASE_AT_SOURCE = "RETRIEVE_SOURCE"


def _crane_cell_for(event: TaskEvent) -> int | None:
    """该事件时堆垛机正在服务的物理格（None=出入口/在途/位置不明）。"""
    if event.phase == _PHASE_AT_TARGET:
        return event.physical_target
    if event.phase == _PHASE_AT_SOURCE:
        return event.physical_source
    return None


@dataclass(frozen=True)
class WarehouseFrame:
    """某一事件边界上的仓库快照（回放的一帧，表示"该事件发生后"的状态）。"""

    seq: int                          # 帧序号（0 起）
    timestamp: str                    # 事件时间戳（ISO8601 文本，原样透传）
    task_id: int
    request_seq: int
    operation: Operation
    status: TaskStatus
    phase: str
    attempt: int
    crane_cell: int | None            # 堆垛机当前服务的物理格（1..54），None=rest/出入口
    occupied_cells: frozenset[int]    # 该帧后已入库占用的物理格集合（1..54）
    completed_so_far: int             # 截至该帧的累计完成任务数（吞吐曲线纵轴）
    fault_code: FaultCode
    message: str

    @property
    def occupancy(self) -> int:
        return len(self.occupied_cells)


@dataclass(frozen=True)
class FaultMark:
    seq: int
    timestamp: str
    task_id: int
    fault_code: FaultCode
    phase: str
    message: str


@dataclass(frozen=True)
class ReplaySummary:
    total_events: int
    total_frames: int
    tasks_seen: int
    tasks_done: int
    tasks_faulted: int
    final_occupancy: int
    faults: tuple[FaultMark, ...]
    span_seconds: float | None        # 末帧-首帧秒数；时间戳不可解析时为 None
    avg_cycle_seconds: float | None   # 完成任务的平均周期(首见→DONE)；无可解析时间戳时 None


@dataclass(frozen=True)
class ReplayTimeline:
    frames: tuple[WarehouseFrame, ...]
    summary: ReplaySummary

    def frame_at(self, seq: int) -> WarehouseFrame:
        return self.frames[seq]

    def occupancy_series(self) -> list[int]:
        """每帧占用数序列——2D 仪表的占用曲线直接用。"""
        return [f.occupancy for f in self.frames]

    def throughput_series(self) -> list[int]:
        """每帧累计完成任务数序列——2D 仪表的吞吐曲线直接用。"""
        return [f.completed_so_far for f in self.frames]

    def task_cycle_seconds(self) -> dict[int, float]:
        """{task_id: 周期秒数}——首见事件→DONE 事件，仅含时间戳可解析的完成任务。"""
        first: dict[int, datetime] = {}
        done: dict[int, datetime] = {}
        for f in self.frames:
            ts = _parse_ts(f.timestamp)
            if ts is None:
                continue
            first.setdefault(f.task_id, ts)
            if f.status is TaskStatus.DONE:
                done[f.task_id] = ts
        return {
            tid: (done[tid] - first[tid]).total_seconds()
            for tid in done
            if tid in first
        }


def _parse_ts(ts: str) -> datetime | None:
    # 同源 orchestrator 产出 '...Z'(UTC)后缀；Python<3.11 的 fromisoformat 不认 Z，先归一化
    try:
        s = ts[:-1] + "+00:00" if ts.endswith("Z") else ts
        return datetime.fromisoformat(s)
    except (ValueError, TypeError, AttributeError):
        return None


def _span_seconds(frames: Sequence[WarehouseFrame]) -> float | None:
    if len(frames) < 2:
        return 0.0 if frames else None
    first = _parse_ts(frames[0].timestamp)
    last = _parse_ts(frames[-1].timestamp)
    if first is None or last is None:
        return None
    return (last - first).total_seconds()


def _avg_cycle_seconds(
    first_seen_ts: dict[int, str], done_ts: dict[int, str]
) -> float | None:
    cycles: list[float] = []
    for tid, done in done_ts.items():
        t0 = _parse_ts(first_seen_ts.get(tid, ""))
        t1 = _parse_ts(done)
        if t0 is not None and t1 is not None:
            cycles.append((t1 - t0).total_seconds())
    if not cycles:
        return None
    return sum(cycles) / len(cycles)


def build_replay(
    events: Iterable[TaskEvent],
    initial_occupancy: Iterable[int] | None = None,
) -> ReplayTimeline:
    """把同源事件流归约成回放时间线。

    events 按给定顺序处理（调用方负责排好序——通常即 JSONL 追加顺序）。
    """
    occupied: set[int] = set(initial_occupancy or ())
    settled: set[tuple[int, int]] = set()   # 已结算占用的 (task_id, request_seq)
    frames: list[WarehouseFrame] = []
    faults: list[FaultMark] = []
    tasks_seen: set[int] = set()
    first_seen_ts: dict[int, str] = {}      # task_id → 首见时间戳（算周期用）
    done_ts: dict[int, str] = {}            # task_id → DONE 时间戳
    tasks_done = 0
    tasks_faulted = 0

    for seq, ev in enumerate(events):
        tasks_seen.add(ev.task_id)
        first_seen_ts.setdefault(ev.task_id, ev.timestamp)

        if ev.status is TaskStatus.DONE:
            key = (ev.task_id, ev.request_seq)
            if key not in settled:
                settled.add(key)
                tasks_done += 1
                done_ts[ev.task_id] = ev.timestamp
                if ev.operation in (Operation.OUTBOUND, Operation.DUAL):
                    if ev.physical_source is not None:
                        occupied.discard(ev.physical_source)
                if ev.operation in (Operation.INBOUND, Operation.DUAL):
                    if ev.physical_target is not None:
                        occupied.add(ev.physical_target)

        if ev.status is TaskStatus.FAULT:
            tasks_faulted += 1
            faults.append(FaultMark(
                seq=seq,
                timestamp=ev.timestamp,
                task_id=ev.task_id,
                fault_code=ev.fault_code,
                phase=ev.phase,
                message=ev.message,
            ))

        frames.append(WarehouseFrame(
            seq=seq,
            timestamp=ev.timestamp,
            task_id=ev.task_id,
            request_seq=ev.request_seq,
            operation=ev.operation,
            status=ev.status,
            phase=ev.phase,
            attempt=ev.attempt,
            crane_cell=_crane_cell_for(ev),
            occupied_cells=frozenset(occupied),
            completed_so_far=tasks_done,
            fault_code=ev.fault_code,
            message=ev.message,
        ))

    summary = ReplaySummary(
        total_events=len(frames),
        total_frames=len(frames),
        tasks_seen=len(tasks_seen),
        tasks_done=tasks_done,
        tasks_faulted=tasks_faulted,
        final_occupancy=len(occupied),
        faults=tuple(faults),
        span_seconds=_span_seconds(frames),
        avg_cycle_seconds=_avg_cycle_seconds(first_seen_ts, done_ts),
    )
    return ReplayTimeline(frames=tuple(frames), summary=summary)


def load_events_jsonl(path: str | Path) -> list[TaskEvent]:
    """读取 TaskEvent JSONL（每行一条，兼容空行）。"""
    events: list[TaskEvent] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        events.append(TaskEvent.from_dict(json.loads(line)))
    return events


def build_replay_from_jsonl(
    path: str | Path,
    initial_occupancy: Iterable[int] | None = None,
) -> ReplayTimeline:
    return build_replay(load_events_jsonl(path), initial_occupancy=initial_occupancy)


def _format_summary(timeline: ReplayTimeline) -> str:
    s = timeline.summary
    span = "n/a" if s.span_seconds is None else f"{s.span_seconds:.1f}s"
    avg_cyc = "n/a" if s.avg_cycle_seconds is None else f"{s.avg_cycle_seconds:.1f}s"
    lines = [
        "=== C6 同源回放摘要 ===",
        f"事件/帧数    : {s.total_events}",
        f"任务(去重)   : {s.tasks_seen}",
        f"完成 / 故障  : {s.tasks_done} / {s.tasks_faulted}",
        f"末态占用格数 : {s.final_occupancy}",
        f"时间跨度     : {span}",
        f"平均任务周期 : {avg_cyc}",
    ]
    if s.faults:
        lines.append(f"故障点({len(s.faults)}):")
        for fm in s.faults:
            lines.append(f"  帧{fm.seq} task{fm.task_id} {fm.fault_code.value} @{fm.phase}")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys

    try:  # Windows 控制台 cp1252 无法输出中文，强制 UTF-8
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

    if len(sys.argv) < 2:
        print("用法: python c6_replay_state.py <TaskEvent.jsonl 路径>")
        raise SystemExit(2)
    tl = build_replay_from_jsonl(sys.argv[1])
    print(_format_summary(tl))
