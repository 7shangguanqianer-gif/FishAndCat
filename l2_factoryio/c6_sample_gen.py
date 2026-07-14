"""C6 同源样本生成器（demo，非测试）。

用**真实的 `TaskOrchestrator`（C2 离线编排门）**跑一段混合调度，产出 TaskEvent
JSONL——这就是 C6「同源」数据源（与驱动真实系统的是同一套编排/事件契约）；
再喂给 `c6_replay_state` 归约成回放时间线并打印摘要，证明同源管线端到端跑通。

用法:
    python c6_sample_gen.py [输出.jsonl]     # 默认写 scratchpad 外的临时文件并打印摘要
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from c6_replay_state import build_replay_from_jsonl, _format_summary
from event_log import JsonlEventLog
from task_contract import Operation, WarehouseTask
from task_orchestrator import TaskOrchestrator


class _DemoAdapter:
    """DeviceAdapter 协议的无副作用实现——只记录动作序列，不驱动任何硬件。"""

    def __init__(self) -> None:
        self.actions: list[str] = []

    def feed(self) -> None: self.actions.append("feed")
    def pick_load(self) -> None: self.actions.append("pick_load")
    def store(self, cell: int) -> None: self.actions.append(f"store:{cell}")
    def retrieve(self, cell: int) -> None: self.actions.append(f"retrieve:{cell}")
    def go_rest(self) -> None: self.actions.append("go_rest")
    def unload(self) -> None: self.actions.append("unload")
    def safe_stop(self) -> None: self.actions.append("safe_stop")


# 一段有代表性的混合调度：先入库铺底，再出库，再一个存取合一（DUAL）
_SCHEDULE = [
    WarehouseTask(1, 1, Operation.INBOUND, goods_id=11, logical_target=0),
    WarehouseTask(2, 2, Operation.INBOUND, goods_id=12, logical_target=210),
    WarehouseTask(3, 3, Operation.INBOUND, goods_id=13, logical_target=399),
    WarehouseTask(4, 4, Operation.OUTBOUND, goods_id=11, logical_source=0),
    WarehouseTask(5, 5, Operation.DUAL, goods_id=14, logical_source=210, logical_target=190),
]


def generate(path: str | Path) -> Path:
    path = Path(path)
    log = JsonlEventLog(path)
    orchestrator = TaskOrchestrator(_DemoAdapter(), log)
    for task in _SCHEDULE:
        orchestrator.execute(task)
    return path


def main() -> None:
    try:  # Windows 控制台 cp1252 无法输出中文，强制 UTF-8
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

    if len(sys.argv) >= 2:
        out = Path(sys.argv[1])
    else:
        out = Path(tempfile.gettempdir()) / "c6_sample_events.jsonl"
    generate(out)
    print(f"[同源事件流已写] {out}")
    timeline = build_replay_from_jsonl(out)
    print(_format_summary(timeline))
    print("\n首/末帧占用:")
    print(f"  首帧 seq0 占用 {timeline.frames[0].occupancy} 格")
    print(f"  末帧 占用 {timeline.frames[-1].occupancy} 格  -> {sorted(timeline.frames[-1].occupied_cells)}")


if __name__ == "__main__":
    main()
