"""C6 同源回放状态层单测。"""

from __future__ import annotations

import json
from pathlib import Path

from c6_replay_state import (
    build_replay,
    build_replay_from_jsonl,
    load_events_jsonl,
)
from event_log import TaskEvent
from task_contract import FaultCode, Operation, TaskStatus


def _ev(
    seq: int,
    status: TaskStatus,
    *,
    operation: Operation = Operation.INBOUND,
    phase: str = "store",
    physical_source: int | None = None,
    physical_target: int | None = None,
    fault_code: FaultCode = FaultCode.NONE,
    ts: str = "2026-07-13T20:00:00",
    attempt: int = 1,
    message: str = "",
) -> TaskEvent:
    return TaskEvent(
        timestamp=ts,
        task_id=seq,
        request_seq=seq,
        operation=operation,
        status=status,
        phase=phase,
        attempt=attempt,
        physical_source=physical_source,
        physical_target=physical_target,
        fault_code=fault_code,
        message=message,
    )


def test_empty_events_yield_empty_timeline():
    tl = build_replay([])
    assert tl.frames == ()
    assert tl.summary.total_frames == 0
    assert tl.summary.tasks_seen == 0
    assert tl.summary.final_occupancy == 0
    assert tl.summary.span_seconds is None


def test_inbound_done_occupies_target():
    tl = build_replay([
        _ev(1, TaskStatus.RUNNING, operation=Operation.INBOUND, physical_target=30),
        _ev(1, TaskStatus.DONE, operation=Operation.INBOUND, physical_target=30),
    ])
    # RUNNING 帧尚未占用；DONE 帧后占用 30
    assert tl.frames[0].occupied_cells == frozenset()
    assert tl.frames[1].occupied_cells == frozenset({30})
    assert tl.summary.final_occupancy == 1
    assert tl.summary.tasks_done == 1


def test_outbound_done_frees_source_from_initial():
    tl = build_replay(
        [_ev(1, TaskStatus.DONE, operation=Operation.OUTBOUND, phase="retrieve", physical_source=12)],
        initial_occupancy=[12, 34],
    )
    assert tl.frames[-1].occupied_cells == frozenset({34})
    assert tl.summary.final_occupancy == 1


def test_dual_done_frees_source_and_adds_target():
    tl = build_replay(
        [_ev(1, TaskStatus.DONE, operation=Operation.DUAL, phase="store",
             physical_source=5, physical_target=50)],
        initial_occupancy=[5],
    )
    assert tl.frames[-1].occupied_cells == frozenset({50})


def test_done_is_idempotent():
    # 同一 (task_id, request_seq) 的 DONE 重复出现，只结算一次
    tl = build_replay([
        _ev(1, TaskStatus.DONE, operation=Operation.INBOUND, physical_target=7),
        _ev(1, TaskStatus.DONE, operation=Operation.INBOUND, physical_target=7),
    ])
    assert tl.frames[-1].occupied_cells == frozenset({7})
    assert tl.summary.tasks_done == 1
    assert tl.summary.tasks_seen == 1


def test_fault_recorded_and_no_occupancy_change():
    tl = build_replay([
        _ev(1, TaskStatus.RUNNING, operation=Operation.INBOUND, physical_target=9),
        _ev(1, TaskStatus.FAULT, operation=Operation.INBOUND, physical_target=9,
            fault_code=FaultCode.DROPPED_LOAD, phase="place"),
    ])
    assert tl.summary.tasks_faulted == 1
    assert tl.summary.final_occupancy == 0        # 故障不入库
    assert len(tl.summary.faults) == 1
    fm = tl.summary.faults[0]
    assert fm.task_id == 1
    assert fm.fault_code is FaultCode.DROPPED_LOAD
    assert fm.seq == 1


def test_intermediate_statuses_do_not_change_occupancy():
    tl = build_replay([
        _ev(1, TaskStatus.QUEUED, physical_target=3),
        _ev(1, TaskStatus.DISPATCHED, physical_target=3),
        _ev(1, TaskStatus.RUNNING, physical_target=3),
    ])
    assert all(f.occupied_cells == frozenset() for f in tl.frames)
    assert tl.summary.tasks_done == 0


def test_crane_cell_exact_phase_mapping():
    # 真实相位契约（task_orchestrator）：仅 STORE_TARGET/RETRIEVE_SOURCE 标格
    at_target = build_replay([_ev(1, TaskStatus.RUNNING, operation=Operation.INBOUND,
                                  phase="STORE_TARGET", physical_target=42)])
    assert at_target.frames[0].crane_cell == 42

    at_source = build_replay([_ev(1, TaskStatus.RUNNING, operation=Operation.OUTBOUND,
                                  phase="RETRIEVE_SOURCE", physical_source=11)])
    assert at_source.frames[0].crane_cell == 11

    # DUAL 的 FEED/PICK_LOAD 是 store 腿前置（在出入口），不得标 source（旧启发式的误判）
    for ph in ("DISPATCH", "ACK", "START", "FEED", "PICK_LOAD", "RETURN_IO",
               "UNLOAD", "RETURN_REST", "COMPLETE", "SAFE_STOP", "unknown-phase"):
        tl = build_replay([_ev(1, TaskStatus.RUNNING, operation=Operation.DUAL,
                               phase=ph, physical_source=5, physical_target=50)])
        assert tl.frames[0].crane_cell is None, f"phase={ph} 应为 None"


def test_occupancy_series_and_span():
    tl = build_replay([
        _ev(1, TaskStatus.RUNNING, operation=Operation.INBOUND, physical_target=1,
            ts="2026-07-13T20:00:00"),
        _ev(1, TaskStatus.DONE, operation=Operation.INBOUND, physical_target=1,
            ts="2026-07-13T20:00:05"),
        _ev(2, TaskStatus.DONE, operation=Operation.INBOUND, physical_target=2,
            ts="2026-07-13T20:00:20"),
    ])
    assert tl.occupancy_series() == [0, 1, 2]
    assert tl.summary.span_seconds == 20.0


def test_span_handles_utc_z_suffix():
    # 同源 orchestrator 产出 '...Z'(UTC) 时间戳，span 应正常计算
    tl = build_replay([
        _ev(1, TaskStatus.RUNNING, ts="2026-07-14T02:00:00.000000Z"),
        _ev(1, TaskStatus.DONE, ts="2026-07-14T02:00:12.500000Z"),
    ])
    assert tl.summary.span_seconds == 12.5


def test_span_none_on_unparseable_ts():
    tl = build_replay([
        _ev(1, TaskStatus.RUNNING, ts="not-a-time"),
        _ev(1, TaskStatus.DONE, ts="also-bad"),
    ])
    assert tl.summary.span_seconds is None


def test_throughput_series_is_cumulative_done():
    tl = build_replay([
        _ev(1, TaskStatus.RUNNING, operation=Operation.INBOUND, physical_target=1),
        _ev(1, TaskStatus.DONE, operation=Operation.INBOUND, physical_target=1),
        _ev(2, TaskStatus.RUNNING, operation=Operation.INBOUND, physical_target=2),
        _ev(2, TaskStatus.DONE, operation=Operation.INBOUND, physical_target=2),
    ])
    assert tl.throughput_series() == [0, 1, 1, 2]
    assert tl.frames[-1].completed_so_far == 2


def test_avg_cycle_and_per_task_cycles():
    tl = build_replay([
        _ev(1, TaskStatus.QUEUED, operation=Operation.INBOUND, physical_target=1,
            ts="2026-07-14T02:00:00Z"),
        _ev(1, TaskStatus.DONE, operation=Operation.INBOUND, physical_target=1,
            ts="2026-07-14T02:00:10Z"),
        _ev(2, TaskStatus.QUEUED, operation=Operation.INBOUND, physical_target=2,
            ts="2026-07-14T02:00:00Z"),
        _ev(2, TaskStatus.DONE, operation=Operation.INBOUND, physical_target=2,
            ts="2026-07-14T02:00:20Z"),
    ])
    cycles = tl.task_cycle_seconds()
    assert cycles == {1: 10.0, 2: 20.0}
    assert tl.summary.avg_cycle_seconds == 15.0


def test_avg_cycle_none_without_done():
    tl = build_replay([_ev(1, TaskStatus.RUNNING, ts="2026-07-14T02:00:00Z")])
    assert tl.summary.avg_cycle_seconds is None
    assert tl.task_cycle_seconds() == {}


def test_jsonl_roundtrip(tmp_path: Path):
    events = [
        _ev(1, TaskStatus.RUNNING, operation=Operation.INBOUND, physical_target=8),
        _ev(1, TaskStatus.DONE, operation=Operation.INBOUND, physical_target=8),
    ]
    p = tmp_path / "events.jsonl"
    p.write_text(
        "\n".join(json.dumps(e.to_dict()) for e in events) + "\n",
        encoding="utf-8",
    )
    loaded = load_events_jsonl(p)
    assert len(loaded) == 2
    tl = build_replay_from_jsonl(p)
    assert tl.summary.final_occupancy == 1
    assert tl.summary.tasks_done == 1


def test_jsonl_tolerates_blank_lines(tmp_path: Path):
    p = tmp_path / "events.jsonl"
    ev = _ev(1, TaskStatus.DONE, operation=Operation.INBOUND, physical_target=4)
    p.write_text(json.dumps(ev.to_dict()) + "\n\n", encoding="utf-8")
    assert len(load_events_jsonl(p)) == 1


# ---------- 集成：真实 orchestrator 的相位契约锁 ----------

class _NullAdapter:
    """DeviceAdapter 无副作用实现（仅供契约锁测试）。"""

    def feed(self): pass
    def pick_load(self): pass
    def store(self, cell): pass
    def retrieve(self, cell): pass
    def go_rest(self): pass
    def unload(self): pass
    def safe_stop(self): pass


def test_real_orchestrator_phase_contract(tmp_path: Path):
    """用真实 TaskOrchestrator 事件流锁死 crane_cell 契约——orchestrator
    相位名若漂移（如改名 STORE_TARGET），本测试立即红。"""
    from event_log import JsonlEventLog
    from task_contract import WarehouseTask
    from task_orchestrator import TaskOrchestrator

    log = JsonlEventLog(tmp_path / "events.jsonl")
    orch = TaskOrchestrator(_NullAdapter(), log)
    orch.execute(WarehouseTask(1, 1, Operation.INBOUND, goods_id=9, logical_target=399))
    orch.execute(WarehouseTask(2, 2, Operation.DUAL, goods_id=8,
                               logical_source=399, logical_target=0))

    tl = build_replay(log.read_all())
    by_phase = {}
    for f in tl.frames:
        by_phase.setdefault((f.task_id, f.phase), f)

    # INBOUND：STORE_TARGET 标 target(=54)，收尾/出入口相位不标格
    assert by_phase[(1, "STORE_TARGET")].crane_cell == 54
    for ph in ("DISPATCH", "START", "FEED", "PICK_LOAD", "RETURN_REST", "COMPLETE"):
        assert by_phase[(1, ph)].crane_cell is None
    # DUAL：store 腿标 target(=1)，retrieve 腿标 source(=54)，其余 None
    assert by_phase[(2, "STORE_TARGET")].crane_cell == 1
    assert by_phase[(2, "RETRIEVE_SOURCE")].crane_cell == 54
    for ph in ("FEED", "PICK_LOAD", "RETURN_IO", "UNLOAD", "RETURN_REST"):
        assert by_phase[(2, ph)].crane_cell is None
    # 占用结算跟着走：入 54 → DUAL 释 54 入 1
    assert tl.frames[-1].occupied_cells == frozenset({1})
