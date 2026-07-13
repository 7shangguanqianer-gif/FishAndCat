# -*- coding: utf-8 -*-
"""F3 快线：Python 直控 Factory I/O Automated Warehouse（Modbus TCP）。

角色：Python 是“伪 PLC”，经 Modbus TCP 读取传感器、写执行器。
口径：本产物只称“Python 直控技术预演”，不称 AC500/PLC 闭环。

0712 现场校准：
- Target Position 1..54=货位，0=原地停止，55=rest/载入位。
- 本场景载入输送带位于 Stacker Crane 的 Left 侧；货架位于 Right 侧。
- At Entry/Load/Unload/Exit 是对射传感器：False=被箱遮挡，True=空。
- Lift=True 微抬取箱，Lift=False 放下；Lift 行程会反映在 Moving Z。
- 运输前必须在 Lift=True 取货高度让叉臂回中，并保持 Lift=True 带载移动；
  到货位后伸叉、Lift=False 放入货架。禁止在移动前把货物放成自由载荷。
- 两个叉向输出同时为 True 时回中位；到位后两个输出都置 False。

安全原则：
- 所有运动都采用“先见起动/离位，再等停稳/到位”的两阶段判据。
- 任一步超时或异常都会清零输出并写 Target=0。
- probe/demo 正常结束时回到 rest，再清零输出。

用法：
  # probe/demo 前先在 Factory I/O 按 F6，确认场景是无散落物的新状态
  python f3_stacker_control.py snapshot  # 只读 I/O 快照
  python f3_stacker_control.py stop      # 输出安全清零
  python f3_stacker_control.py probe 1   # 单箱入库到货位 1
  python f3_stacker_control.py demo 3    # 连续入库到 [11, 24, 37]
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Callable

from pymodbus.client import ModbusTcpClient


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST, PORT, SLAVE = "127.0.0.1", 502, 1

# Discrete inputs
IN_AT_ENTRY, IN_AT_LOAD, IN_AT_LEFT, IN_AT_MIDDLE, IN_AT_RIGHT = 0, 1, 2, 3, 4
IN_AT_UNLOAD, IN_AT_EXIT, IN_MOVING_X, IN_MOVING_Z = 5, 6, 7, 8
IN_START, IN_RESET, IN_STOP, IN_ESTOP, IN_AUTO, IN_RUNNING = 9, 10, 11, 12, 13, 14

# Coils / holding register
C_ENTRY_CONV, C_LOAD_CONV, C_FORKS_L, C_FORKS_R, C_LIFT = 0, 1, 2, 3, 4
C_UNLOAD_CONV, C_EXIT_CONV = 5, 6
HR_TARGET = 0
POS_REST = 55

STEP_TIMEOUT = 30.0
START_TIMEOUT = 3.0
POLL = 0.05
SETTLE = 0.40
LOAD_SETTLE_DWELL = 2.0
PLACEMENT_SETTLE_DWELL = 1.5
DIAGNOSTIC_PHASES = ("feed", "pick", "travel", "store")
ACCEPTANCE_CELLS = (1, 30, 54)

INPUT_NAMES = (
    "At Entry", "At Load", "At Left", "At Middle", "At Right",
    "At Unload", "At Exit", "Moving X", "Moving Z", "Start", "Reset",
    "Stop", "Emergency stop", "Auto", "FACTORY I/O (Running)",
)
COIL_NAMES = (
    "Entry Conveyor", "Load Conveyor", "Forks Left", "Forks Right", "Lift",
    "Unload Conveyor", "Exit Conveyor", "Start light", "Reset light", "Stop light",
)


class TeeStream:
    """把现场动作日志同时写到控制台和证据文件。"""

    def __init__(self, *streams):
        self.streams = streams

    def write(self, text):
        for stream in self.streams:
            stream.write(text)
            stream.flush()
        return len(text)

    def flush(self):
        for stream in self.streams:
            stream.flush()


class Stacker:
    def __init__(self, client=None):
        self.c = client or ModbusTcpClient(HOST, port=PORT)
        if not self.c.connect():
            raise SystemExit("connect failed")
        self.position_hint: int | None = None
        self.check_interlocks()

    # ---- 基础 I/O ----
    def din(self, addr: int) -> bool:
        r = self.c.read_discrete_inputs(addr, count=1, slave=SLAVE)
        if r.isError():
            raise RuntimeError(f"read input {addr}: {r}")
        return bool(r.bits[0])

    def coil(self, addr: int, value: bool) -> None:
        r = self.c.write_coil(addr, value, slave=SLAVE)
        if r.isError():
            raise RuntimeError(f"write coil {addr}: {r}")

    def target(self, position: int) -> None:
        r = self.c.write_register(HR_TARGET, position, slave=SLAVE)
        if r.isError():
            raise RuntimeError(f"write target {position}: {r}")

    def check_interlocks(self) -> None:
        if not self.din(IN_RUNNING):
            raise RuntimeError("Factory I/O 未在 RUN 状态（Input14=False）")
        if not self.din(IN_STOP):
            raise RuntimeError("Stop 常闭输入断开（Input11=False）")
        if not self.din(IN_ESTOP):
            raise RuntimeError("Emergency stop 常闭输入断开（Input12=False）")

    def snapshot(self) -> dict:
        di = self.c.read_discrete_inputs(0, count=len(INPUT_NAMES), slave=SLAVE)
        co = self.c.read_coils(0, count=len(COIL_NAMES), slave=SLAVE)
        hr = self.c.read_holding_registers(HR_TARGET, count=1, slave=SLAVE)
        if di.isError() or co.isError() or hr.isError():
            raise RuntimeError(f"snapshot failed: di={di}, co={co}, hr={hr}")
        return {
            "inputs": [bool(x) for x in di.bits[: len(INPUT_NAMES)]],
            "coils": [bool(x) for x in co.bits[: len(COIL_NAMES)]],
            "target": int(hr.registers[0]),
        }

    def print_snapshot(self, label: str) -> None:
        snap = self.snapshot()
        print(f"--- {label} ---")
        print("inputs: " + ", ".join(
            f"{i}:{name}={snap['inputs'][i]}" for i, name in enumerate(INPUT_NAMES)
        ))
        print("coils: " + ", ".join(
            f"{i}:{name}={snap['coils'][i]}" for i, name in enumerate(COIL_NAMES)
        ))
        print(f"target: {snap['target']}")

    def assert_action_ready(self) -> None:
        """拒绝在上轮碰撞/中断残留状态上继续自动动作。"""
        snap = self.snapshot()
        problems = []
        if snap["inputs"][IN_MOVING_X] or snap["inputs"][IN_MOVING_Z]:
            problems.append("Moving X/Z still active")
        if not snap["inputs"][IN_AT_MIDDLE]:
            problems.append("forks are not at Middle")
        active = [i for i, value in enumerate(snap["coils"][:7]) if value]
        if active:
            problems.append(f"active coils={active}")
        if problems:
            raise RuntimeError(
                "action preflight failed (press Factory I/O F6 and recheck): "
                + "; ".join(problems)
            )
        print("PREFLIGHT OK: settled, forks Middle, C0..C6=False")

    # ---- 等待与安全 ----
    def wait_stable(
        self,
        description: str,
        predicate: Callable[[], bool],
        *,
        timeout: float = STEP_TIMEOUT,
        stable_for: float = SETTLE,
    ) -> None:
        started = time.monotonic()
        stable_since = None
        while time.monotonic() - started < timeout:
            self.check_interlocks()
            if predicate():
                stable_since = stable_since or time.monotonic()
                if time.monotonic() - stable_since >= stable_for:
                    print(f"  [ok {time.monotonic() - started:5.2f}s] {description}")
                    return
            else:
                stable_since = None
            time.sleep(POLL)
        raise RuntimeError(f"TIMEOUT({timeout}s): {description}")

    def wait_motion_cycle(
        self,
        description: str,
        moving: Callable[[], bool],
        *,
        start_timeout: float = START_TIMEOUT,
        finish_timeout: float = STEP_TIMEOUT,
        allow_no_start: bool = False,
    ) -> bool:
        t0 = time.monotonic()
        while time.monotonic() - t0 < start_timeout:
            self.check_interlocks()
            if moving():
                print(f"  [start {time.monotonic() - t0:4.2f}s] {description}")
                break
            time.sleep(POLL)
        else:
            if allow_no_start:
                self.wait_stable(
                    f"{description} already settled (no motion)",
                    lambda: not moving(),
                    timeout=1.0,
                )
                return False
            raise RuntimeError(f"NO START({start_timeout}s): {description}")

        self.wait_stable(
            f"{description} settled",
            lambda: not moving(),
            timeout=finish_timeout,
        )
        return True

    def all_stop(self) -> None:
        errors = []
        for address in (
            C_ENTRY_CONV, C_LOAD_CONV, C_FORKS_L, C_FORKS_R, C_LIFT,
            C_UNLOAD_CONV, C_EXIT_CONV,
        ):
            try:
                self.coil(address, False)
            except Exception as exc:  # 尽力停机后汇总，不吞掉事实
                errors.append(f"C{address}: {exc}")
        try:
            self.target(0)
        except Exception as exc:
            errors.append(f"HR0: {exc}")
        if errors:
            raise RuntimeError("safe stop incomplete: " + "; ".join(errors))
        print("SAFE STOP: C0..C6=False, Target=0")

    # ---- 组合动作 ----
    def crane_moving(self) -> bool:
        return self.din(IN_MOVING_X) or self.din(IN_MOVING_Z)

    def box_at_load(self) -> bool:
        return not self.din(IN_AT_LOAD)

    def goto(self, position: int, description: str = "") -> None:
        if position != POS_REST and not 1 <= position <= 54:
            raise ValueError(f"invalid target position: {position}")
        if self.position_hint == position:
            print(f"* Target Position = {position} {description} [already confirmed]")
            return
        print(f"* Target Position = {position} {description}")
        self.target(position)
        # 场景复位后堆垛机可能已物理位于 rest；Numerical 配置没有当前
        # Position 输入，因此首个幂等 rest 命令只可能以“持续停稳”确认。
        self.wait_motion_cycle(
            f"crane -> {position}",
            self.crane_moving,
            allow_no_start=(position == POS_REST and self.position_hint is None),
        )
        self.position_hint = position

    def _fork_to(self, name: str, coil_address: int, limit_input: int) -> None:
        if self.din(limit_input):
            print(f"* forks already at {name}")
            return
        self.coil(C_FORKS_L, coil_address == C_FORKS_L)
        self.coil(C_FORKS_R, coil_address == C_FORKS_R)
        self.wait_stable(
            f"forks At {name}",
            lambda: self.din(limit_input),
            timeout=8.0,
            stable_for=0.15,
        )

    def forks_left(self) -> None:
        self._fork_to("Left", C_FORKS_L, IN_AT_LEFT)

    def forks_right(self) -> None:
        self._fork_to("Right", C_FORKS_R, IN_AT_RIGHT)

    def forks_center(self) -> None:
        if self.din(IN_AT_MIDDLE):
            self.coil(C_FORKS_L, False)
            self.coil(C_FORKS_R, False)
            print("* forks already at Middle")
            return
        self.coil(C_FORKS_L, True)
        self.coil(C_FORKS_R, True)
        self.wait_stable(
            "forks At Middle",
            lambda: self.din(IN_AT_MIDDLE),
            timeout=8.0,
            stable_for=0.15,
        )
        self.coil(C_FORKS_L, False)
        self.coil(C_FORKS_R, False)

    def feed_one_box(self) -> None:
        self.goto(POS_REST, "(prepare load station)")
        self.forks_center()
        if self.box_at_load():
            print("* 载入位已有箱，跳过输送")
            return
        print("* 入料：Entry + Load Conveyor")
        self.coil(C_ENTRY_CONV, True)
        self.coil(C_LOAD_CONV, True)
        try:
            self.wait_stable(
                "box At Load",
                self.box_at_load,
                timeout=60.0,
                stable_for=0.30,
            )
        finally:
            self.coil(C_ENTRY_CONV, False)
            self.coil(C_LOAD_CONV, False)
        print(f"* load settle dwell: {LOAD_SETTLE_DWELL:.1f}s")
        time.sleep(LOAD_SETTLE_DWELL)
        self.wait_stable(
            "box remains at load after settle",
            self.box_at_load,
            timeout=1.5,
            stable_for=0.40,
        )

    def pick_from_load(self) -> None:
        if not self.box_at_load():
            raise RuntimeError("pick precondition failed: At Load is empty")
        self.goto(POS_REST, "(rest=载入台)")
        print("* 取箱：Left 侧伸叉 -> 抬起 -> 回中（保持 Lift=True 带载）")
        self.forks_left()
        self.coil(C_LIFT, True)
        self.wait_motion_cycle("lift load", lambda: self.din(IN_MOVING_Z))
        self.wait_stable("At Load cleared", lambda: not self.box_at_load())
        self.forks_center()

    def travel_loaded_to(self, cell: int) -> None:
        if not 1 <= cell <= 54:
            raise ValueError(f"cell must be 1..54, got {cell}")
        self.goto(cell, f"(loaded travel to cell {cell})")

    def store_to(self, cell: int) -> None:
        if not 1 <= cell <= 54:
            raise ValueError(f"cell must be 1..54, got {cell}")
        self.travel_loaded_to(cell)
        print(f"* 放箱：Right 侧伸叉 -> Lift=False 下放 -> 回中（货位 {cell}）")
        self.forks_right()
        self.coil(C_LIFT, False)
        self.wait_motion_cycle("lower load", lambda: self.din(IN_MOVING_Z))
        print(f"* placement settle dwell: {PLACEMENT_SETTLE_DWELL:.1f}s")
        time.sleep(PLACEMENT_SETTLE_DWELL)
        self.forks_center()

    def store_one(self, cell: int) -> None:
        self.feed_one_box()
        self.pick_from_load()
        self.store_to(cell)
        self.goto(POS_REST, "(cycle complete)")
        print(f"=== 货位 {cell} 单箱流程完成 ===\n")

    def run_diagnostic(self, phase: str, cell: int) -> None:
        if phase not in DIAGNOSTIC_PHASES:
            raise ValueError(f"invalid diagnostic phase: {phase}")
        if phase == "store":
            self.store_one(cell)
            return
        self.feed_one_box()
        if phase == "feed":
            return
        self.pick_from_load()
        if phase == "pick":
            return
        self.travel_loaded_to(cell)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    sub.add_parser("snapshot")
    sub.add_parser("stop")

    probe = sub.add_parser("probe")
    probe.add_argument("cell", type=int, nargs="?", default=1)

    demo = sub.add_parser("demo")
    demo.add_argument("count", type=int, nargs="?", default=3)

    diagnose = sub.add_parser("diagnose")
    diagnose.add_argument("phase", choices=DIAGNOSTIC_PHASES)
    diagnose.add_argument("cell", type=int, nargs="?", default=1)

    sub.add_parser("accept")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    mode = args.mode
    action_mode = mode in {"probe", "demo", "diagnose", "accept"}
    original_stdout = sys.stdout
    log_file = None
    if action_mode:
        log_dir = Path(__file__).resolve().parent / "logs"
        log_dir.mkdir(exist_ok=True)
        log_path = log_dir / f"F3_{mode}_{datetime.now():%Y%m%d_%H%M%S}.log"
        log_file = log_path.open("w", encoding="utf-8", newline="\n")
        sys.stdout = TeeStream(original_stdout, log_file)
        print(f"LOG FILE: {log_path}")

    stacker = Stacker()
    started = time.monotonic()
    try:
        if mode == "snapshot":
            stacker.print_snapshot("F3 SNAPSHOT")
        elif mode == "stop":
            stacker.all_stop()
        elif mode == "probe":
            stacker.assert_action_ready()
            stacker.store_one(args.cell)
        elif mode == "demo":
            stacker.assert_action_ready()
            if not 1 <= args.count <= 3:
                raise ValueError(f"demo count must be 1..3, got {args.count}")
            for cell in [11, 24, 37][: args.count]:
                stacker.store_one(cell)
        elif mode == "diagnose":
            stacker.assert_action_ready()
            stacker.run_diagnostic(args.phase, args.cell)
        elif mode == "accept":
            stacker.assert_action_ready()
            for cell in ACCEPTANCE_CELLS:
                stacker.store_one(cell)
        else:
            raise ValueError(f"unknown mode: {mode}")
        if action_mode:
            stacker.all_stop()
        print(f"ALL DONE in {time.monotonic() - started:.1f}s")
    except KeyboardInterrupt:
        print("interrupted -> safe stop")
        stacker.all_stop()
        raise
    except Exception as exc:
        print(f"FAILED: {exc}")
        try:
            stacker.all_stop()
        except Exception as stop_exc:
            print(f"SAFE STOP FAILED: {stop_exc}")
        raise
    finally:
        stacker.c.close()
        if log_file is not None:
            sys.stdout = original_stdout
            log_file.close()


if __name__ == "__main__":
    main()
