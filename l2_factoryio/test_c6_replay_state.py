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


def test_crane_cell_heuristic():
    inbound = build_replay([_ev(1, TaskStatus.RUNNING, operation=Operation.INBOUND,
                                phase="store", physical_target=42)])
    assert inbound.frames[0].crane_cell == 42

    outbound = build_replay([_ev(1, TaskStatus.RUNNING, operation=Operation.OUTBOUND,
                                 phase="retrieve", physical_source=11)])
    assert outbound.frames[0].crane_cell == 11

    rest = build_replay([_ev(1, TaskStatus.DONE, operation=Operation.INBOUND,
                             phase="go_rest", physical_target=42)])
    assert rest.frames[0].crane_cell is None


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
