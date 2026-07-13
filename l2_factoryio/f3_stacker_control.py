# -*- coding: utf-8 -*-
"""F3 快线：Python 直控 Factory I/O Automated Warehouse（Modbus TCP）。

角色：Python 是“伪 PLC”，经 Modbus TCP 读取传感器、写执行器。
口径：本产物只称“Python 直控技术预演”，不称 AC500/PLC 闭环。

0713 分层校准结论：
- Target Position 1..54=货位，0=原地停止，55=rest/载入位。
- 当前工作假设：载入台在 Left 侧、货架在 Right 侧；必须由 G2/G4 画面亲验。
- At Entry/Load/Unload/Exit 为正逻辑到位传感器：True=有箱，False=空。
- Lift=True 微抬取箱；带载移动必须保持 Lift=True，禁止把货物降成自由载荷。
- Factory I/O 没有 cargo-present 和当前位置反馈，因此信号门不能代替人工画面门。

安全协议：
- 诊断拆成 feed -> pick -> travel -> place -> retract 五个物理门。
- pick/travel 收尾只停止运动，保留 Lift=True；不得用通用清零主动掉箱。
- place 在下放后保持货叉伸出，人工确认货架承载后才单独执行 retract。
- 叉限位必须 one-hot；到位后立即撤销叉驱动输出。
- stop/snapshot 在 Pause、Stop 或 E-stop 状态下仍必须可用。

推荐校准命令（每轮先 F6、再 F5 RUN）：
  python f3_stacker_control.py diagnose feed 1 --confirm-rest --observe-seconds 30
  python f3_stacker_control.py diagnose pick 1 --confirm-rest --observe-seconds 30
  # 画面确认货物水平且在承载台后，不复位：
  python f3_stacker_control.py diagnose travel 1 --confirm-cargo --confirm-position --observe-seconds 30
  python f3_stacker_control.py diagnose place 1 --confirm-cargo --confirm-position --observe-seconds 30
  # 画面确认货架梁已承载后：
  python f3_stacker_control.py diagnose retract 1 --confirm-placement --confirm-position --observe-seconds 10
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from enum import Enum
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
MOTION_COILS = (
    C_ENTRY_CONV, C_LOAD_CONV, C_FORKS_L, C_FORKS_R,
    C_UNLOAD_CONV, C_EXIT_CONV,
)
HR_TARGET = 0
POS_REST = 55

STEP_TIMEOUT = 30.0
START_TIMEOUT = 3.0
POLL = 0.05
SETTLE = 0.40
LOAD_SETTLE_DWELL = 2.0
PLACEMENT_SETTLE_DWELL = 1.5
DIAGNOSTIC_PHASES = ("feed", "pick", "travel", "place", "retract")
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


class LoadState(Enum):
    UNKNOWN = "unknown"
    EMPTY = "empty"
    STAGED = "staged"
    CARRYING = "carrying"
    PLACED_PENDING = "placed_pending"
    PLACED = "placed"


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
        # 构造只负责连接。stop/snapshot 不能被 RUN/Stop/E-stop 互锁挡住。
        self.position_hint: int | None = None
        self.load_state = LoadState.UNKNOWN

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

    def check_safety_inputs(self, *, require_running: bool = True) -> None:
        if require_running and not self.din(IN_RUNNING):
            raise RuntimeError("Factory I/O 未在 RUN 状态（Input14=False）")
        if not self.din(IN_STOP):
            raise RuntimeError("Stop 常闭输入断开（Input11=False）")
        if not self.din(IN_ESTOP):
            raise RuntimeError("Emergency stop 常闭输入断开（Input12=False）")

    # 兼容旧调用名；新代码显式传 require_running。
    def check_interlocks(self) -> None:
        self.check_safety_inputs(require_running=True)

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

    @staticmethod
    def _fork_bits_from_snapshot(snap: dict) -> tuple[bool, bool, bool]:
        inputs = snap["inputs"]
        return (
            inputs[IN_AT_LEFT],
            inputs[IN_AT_MIDDLE],
            inputs[IN_AT_RIGHT],
        )

    def _read_fork_bits(self) -> tuple[bool, bool, bool]:
        return (self.din(IN_AT_LEFT), self.din(IN_AT_MIDDLE), self.din(IN_AT_RIGHT))

    def assert_fork_position(self, expected_input: int, expected_name: str) -> None:
        bits = self._read_fork_bits()
        if sum(bits) != 1:
            raise RuntimeError(f"fork limits are not one-hot: Left/Middle/Right={bits}")
        expected_index = {
            IN_AT_LEFT: 0,
            IN_AT_MIDDLE: 1,
            IN_AT_RIGHT: 2,
        }[expected_input]
        if not bits[expected_index]:
            raise RuntimeError(
                f"fork position mismatch: expected {expected_name}, "
                f"Left/Middle/Right={bits}"
            )

    def assert_action_ready(self) -> None:
        """拒绝在上轮碰撞/中断残留状态上开始新箱。"""
        snap = self.snapshot()
        problems = []
        if snap["inputs"][IN_MOVING_X] or snap["inputs"][IN_MOVING_Z]:
            problems.append("Moving X/Z still active")
        fork_bits = self._fork_bits_from_snapshot(snap)
        if fork_bits != (False, True, False):
            problems.append(f"fork limits not one-hot Middle: {fork_bits}")
        active = [i for i, value in enumerate(snap["coils"][:7]) if value]
        if active:
            problems.append(f"active coils={active}")
        if snap["target"] != 0:
            problems.append(f"Target={snap['target']} (expected 0)")
        if problems:
            raise RuntimeError(
                "action preflight failed (save evidence, then F6 and recheck): "
                + "; ".join(problems)
            )
        self.load_state = LoadState.EMPTY
        print("PREFLIGHT OK: settled, forks one-hot Middle, C0..C6=False, Target=0")

    def confirm_rest_baseline(self, operator_confirmed: bool) -> None:
        if not operator_confirmed:
            raise RuntimeError(
                "rest position has no sensor feedback; rerun with --confirm-rest "
                "only after fixed-camera visual confirmation following F6"
            )
        self.position_hint = POS_REST
        print("OPERATOR GATE: fixed-camera rest position confirmed after F6")

    def assert_loaded_transport_ready(self) -> None:
        """只验证执行器/传感器一致性；不宣称货物真的仍在承载台。"""
        snap = self.snapshot()
        problems = []
        fork_bits = self._fork_bits_from_snapshot(snap)
        if fork_bits != (False, True, False):
            problems.append(f"fork limits not one-hot Middle: {fork_bits}")
        if snap["inputs"][IN_MOVING_X] or snap["inputs"][IN_MOVING_Z]:
            problems.append("crane still moving")
        if not snap["inputs"][IN_AT_LOAD]:
            problems.append("At Load still blocked")
        if not snap["coils"][C_LIFT]:
            problems.append("Lift=True required for loaded travel")
        if snap["coils"][C_FORKS_L] or snap["coils"][C_FORKS_R]:
            problems.append("fork outputs must be False at Middle")
        if problems:
            raise RuntimeError("actuator consistency gate failed: " + "; ".join(problems))
        print(
            "ACTUATOR GATE OK: Middle, Lift=True, At Load clear; "
            "cargo presence still requires visual confirmation"
        )

    def resume_carrying(self, *, operator_confirmed: bool, position: int) -> None:
        if not operator_confirmed:
            raise RuntimeError(
                "cargo visual confirmation required before resuming loaded motion"
            )
        if position != POS_REST and not 1 <= position <= 54:
            raise ValueError(f"invalid operator-confirmed position: {position}")
        self.assert_loaded_transport_ready()
        self.load_state = LoadState.CARRYING
        self.position_hint = position
        print(f"OPERATOR GATE: cargo horizontal/present; current position={position}")

    def resume_placement_pending(
        self, *, operator_confirmed: bool, position: int
    ) -> None:
        if not operator_confirmed:
            raise RuntimeError(
                "placement support confirmation required before retract"
            )
        if not 1 <= position <= 54:
            raise ValueError(f"invalid placement cell: {position}")
        snap = self.snapshot()
        fork_bits = self._fork_bits_from_snapshot(snap)
        problems = []
        if fork_bits != (False, False, True):
            problems.append(f"fork limits not one-hot Right: {fork_bits}")
        if snap["inputs"][IN_MOVING_X] or snap["inputs"][IN_MOVING_Z]:
            problems.append("crane still moving")
        if snap["coils"][C_LIFT]:
            problems.append("Lift must be False after placement")
        if problems:
            raise RuntimeError("placement hold gate failed: " + "; ".join(problems))
        self.load_state = LoadState.PLACED_PENDING
        self.position_hint = position
        print(f"OPERATOR GATE: rack support confirmed at cell {position}")

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
            self.check_safety_inputs(require_running=True)
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
    ) -> None:
        t0 = time.monotonic()
        while time.monotonic() - t0 < start_timeout:
            self.check_safety_inputs(require_running=True)
            if moving():
                print(f"  [start {time.monotonic() - t0:4.2f}s] {description}")
                break
            time.sleep(POLL)
        else:
            raise RuntimeError(f"NO START({start_timeout}s): {description}")

        self.wait_stable(
            f"{description} settled",
            lambda: not moving(),
            timeout=finish_timeout,
        )

    def safe_stop(self, *, preserve_lift: bool | None = None) -> None:
        """停止所有运动并读回；载荷不明或在途时绝不主动撤 Lift。"""
        if preserve_lift is None:
            preserve_lift = self.load_state in (LoadState.UNKNOWN, LoadState.CARRYING)
        errors = []
        try:
            # 先停 X/Z 目标，避免清执行器过程中继续行走。
            self.target(0)
        except Exception as exc:
            errors.append(f"HR0: {exc}")
        for address in MOTION_COILS:
            try:
                self.coil(address, False)
            except Exception as exc:
                errors.append(f"C{address}: {exc}")
        if not preserve_lift:
            try:
                self.coil(C_LIFT, False)
            except Exception as exc:
                errors.append(f"C{C_LIFT}: {exc}")

        try:
            snap = self.snapshot()
            bad = [address for address in MOTION_COILS if snap["coils"][address]]
            if not preserve_lift and snap["coils"][C_LIFT]:
                bad.append(C_LIFT)
            if snap["target"] != 0 or bad:
                errors.append(
                    f"readback mismatch: Target={snap['target']}, active coils={bad}"
                )
        except Exception as exc:
            errors.append(f"readback: {exc}")
        if errors:
            raise RuntimeError("safe stop incomplete: " + "; ".join(errors))
        lift_text = "preserved" if preserve_lift else "False"
        print(f"SAFE STOP VERIFIED: motion coils=False, Target=0, Lift={lift_text}")

    # 旧入口保留为兼容别名，但语义已是载荷感知停机。
    def all_stop(self) -> None:
        self.safe_stop()

    # ---- 组合动作 ----
    def crane_moving(self) -> bool:
        return self.din(IN_MOVING_X) or self.din(IN_MOVING_Z)

    def box_at_load(self) -> bool:
        # 0713 近景 + F6 空载亲验：At Load=False 时载入输送带为空。
        return self.din(IN_AT_LOAD)

    def goto(self, position: int, description: str = "") -> None:
        if position != POS_REST and not 1 <= position <= 54:
            raise ValueError(f"invalid target position: {position}")
        if self.position_hint == position:
            print(
                f"* Target Position = {position} {description} "
                "[operator/in-process position evidence]"
            )
            return
        print(f"* Target Position = {position} {description}")
        self.target(position)
        self.wait_motion_cycle(f"crane -> {position}", self.crane_moving)
        self.position_hint = position

    def _clear_fork_outputs(self) -> None:
        errors = []
        for address in (C_FORKS_L, C_FORKS_R):
            try:
                self.coil(address, False)
            except Exception as exc:
                errors.append(f"C{address}: {exc}")
        if errors:
            raise RuntimeError("fork output clear failed: " + "; ".join(errors))

    def _fork_to(self, name: str, coil_address: int, limit_input: int) -> None:
        self.assert_fork_position(IN_AT_MIDDLE, "Middle")
        primary_error = None
        try:
            self.coil(C_FORKS_L, coil_address == C_FORKS_L)
            self.coil(C_FORKS_R, coil_address == C_FORKS_R)
            self.wait_stable(
                "forks departed Middle",
                lambda: not self.din(IN_AT_MIDDLE),
                timeout=3.0,
                stable_for=POLL,
            )
            self.wait_stable(
                f"forks one-hot At {name}",
                lambda: self._read_fork_bits() == (
                    limit_input == IN_AT_LEFT,
                    limit_input == IN_AT_MIDDLE,
                    limit_input == IN_AT_RIGHT,
                ),
                timeout=8.0,
                stable_for=0.15,
            )
        except Exception as exc:
            primary_error = exc
        try:
            # 到限位后撤销驱动，避免持续顶推货物/货架。
            self._clear_fork_outputs()
        except Exception as clear_exc:
            if primary_error is None:
                primary_error = clear_exc
            else:
                primary_error = RuntimeError(f"{primary_error}; {clear_exc}")
        if primary_error is not None:
            raise primary_error

    def forks_left(self) -> None:
        self._fork_to("Left", C_FORKS_L, IN_AT_LEFT)

    def forks_right(self) -> None:
        self._fork_to("Right", C_FORKS_R, IN_AT_RIGHT)

    def forks_center(self) -> None:
        bits = self._read_fork_bits()
        if bits == (False, True, False):
            self._clear_fork_outputs()
            print("* forks already one-hot Middle")
            return
        if sum(bits) != 1 or bits[1]:
            raise RuntimeError(f"cannot center from invalid fork limits: {bits}")
        departed_input = IN_AT_LEFT if bits[0] else IN_AT_RIGHT
        primary_error = None
        try:
            self.coil(C_FORKS_L, True)
            self.coil(C_FORKS_R, True)
            self.wait_stable(
                "forks departed extended limit",
                lambda: not self.din(departed_input),
                timeout=3.0,
                stable_for=POLL,
            )
            self.wait_stable(
                "forks one-hot At Middle",
                lambda: self._read_fork_bits() == (False, True, False),
                timeout=8.0,
                stable_for=0.15,
            )
        except Exception as exc:
            primary_error = exc
        try:
            self._clear_fork_outputs()
        except Exception as clear_exc:
            if primary_error is None:
                primary_error = clear_exc
            else:
                primary_error = RuntimeError(f"{primary_error}; {clear_exc}")
        if primary_error is not None:
            raise primary_error

    def wait_for_box_edge(self) -> None:
        """第一次检测到 At Load 遮挡立即返回；防抖在停带后执行。"""
        started = time.monotonic()
        while time.monotonic() - started < 60.0:
            self.check_safety_inputs(require_running=True)
            if self.box_at_load():
                print(f"  [edge {time.monotonic() - started:5.2f}s] box At Load")
                return
            time.sleep(POLL)
        raise RuntimeError("TIMEOUT(60.0s): box At Load edge")

    def _verify_load_stable(self) -> None:
        self.wait_stable(
            "box stable at load after belts stopped",
            self.box_at_load,
            timeout=1.5,
            stable_for=0.30,
        )
        print(f"* load settle dwell: {LOAD_SETTLE_DWELL:.1f}s")
        time.sleep(LOAD_SETTLE_DWELL)
        self.wait_stable(
            "box remains at load after settle",
            self.box_at_load,
            timeout=1.5,
            stable_for=0.40,
        )
        self.load_state = LoadState.STAGED

    def feed_one_box(self) -> None:
        self.goto(POS_REST, "(prepare load station)")
        self.forks_center()
        if self.box_at_load():
            raise RuntimeError(
                "load station already occupied; G1 cannot be bypassed "
                "(save evidence, then F6 for a clean trial)"
            )
        print("* 入料：Entry + Load Conveyor")
        primary_error = None
        try:
            self.coil(C_ENTRY_CONV, True)
            self.coil(C_LOAD_CONV, True)
            self.wait_for_box_edge()
        except Exception as exc:
            primary_error = exc
        cleanup_errors = []
        for address in (C_ENTRY_CONV, C_LOAD_CONV):
            try:
                self.coil(address, False)
            except Exception as exc:
                cleanup_errors.append(f"C{address}: {exc}")
        if primary_error is not None:
            if cleanup_errors:
                raise RuntimeError(
                    f"{primary_error}; conveyor cleanup failed: {cleanup_errors}"
                ) from primary_error
            raise primary_error
        if cleanup_errors:
            raise RuntimeError("conveyor cleanup failed: " + "; ".join(cleanup_errors))

        # 防抖和落稳都在输送带已停止之后，避免传感器遮挡后继续顶推。
        self._verify_load_stable()

    def pick_from_load(self) -> None:
        if not self.box_at_load():
            raise RuntimeError("pick precondition failed: At Load is empty")
        self.goto(POS_REST, "(rest=载入台)")
        print("* 取箱：Left 侧伸叉 -> 抬起 -> 回中（保持 Lift=True 带载）")
        self.forks_left()
        # 从此刻起叉已在货物下方；即使 Lift 写入/反馈随后失败，清理路径也
        # 必须按“可能带载”保守处理，不能主动写 Lift=False。
        self.load_state = LoadState.CARRYING
        self.coil(C_LIFT, True)
        self.wait_motion_cycle("lift load", lambda: self.din(IN_MOVING_Z))
        self.wait_stable("At Load cleared", lambda: not self.box_at_load())
        self.forks_center()
        self.assert_loaded_transport_ready()

    def travel_loaded_to(self, cell: int) -> None:
        if not 1 <= cell <= 54:
            raise ValueError(f"cell must be 1..54, got {cell}")
        if self.load_state != LoadState.CARRYING:
            raise RuntimeError(f"travel requires CARRYING state, got {self.load_state.value}")
        self.assert_loaded_transport_ready()
        self.goto(cell, f"(loaded travel to cell {cell})")

    def place_hold(self, cell: int) -> None:
        if not 1 <= cell <= 54:
            raise ValueError(f"cell must be 1..54, got {cell}")
        if self.load_state != LoadState.CARRYING:
            raise RuntimeError(f"place requires CARRYING state, got {self.load_state.value}")
        if self.position_hint != cell:
            raise RuntimeError(
                f"place position evidence mismatch: confirmed={self.position_hint}, cell={cell}"
            )
        self.assert_loaded_transport_ready()
        print(
            f"* 放箱保持：Right 侧伸叉 -> Lift=False 下放 -> 保持伸叉（货位 {cell}）"
        )
        self.forks_right()
        self.coil(C_LIFT, False)
        self.wait_motion_cycle("lower load", lambda: self.din(IN_MOVING_Z))
        print(f"* placement settle dwell: {PLACEMENT_SETTLE_DWELL:.1f}s")
        time.sleep(PLACEMENT_SETTLE_DWELL)
        self.assert_fork_position(IN_AT_RIGHT, "Right")
        self.load_state = LoadState.PLACED_PENDING
        print("PLACEMENT HOLD: inspect rack support before running retract")

    def retract_after_placement(self, *, operator_confirmed: bool) -> None:
        if not operator_confirmed:
            raise RuntimeError("operator confirmation required before fork retract")
        if self.load_state != LoadState.PLACED_PENDING:
            raise RuntimeError(
                f"retract requires PLACED_PENDING state, got {self.load_state.value}"
            )
        self.assert_fork_position(IN_AT_RIGHT, "Right")
        self.forks_center()
        self.load_state = LoadState.PLACED
        print("PLACEMENT VERIFIED: forks retracted after operator confirmation")

    def observe_phase(self, label: str, seconds: float) -> None:
        """保留现场供取证；GUI Pause 是预期状态，不触发卸载式清理。"""
        if seconds <= 0:
            return
        self.print_snapshot(f"OBSERVE {label}")
        print(f"OBSERVE WINDOW {label}: {seconds:.1f}s; fixed-camera evidence now")
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            # Pause 会使 Input14=False；这里只继续监视 Stop/E-stop。
            self.check_safety_inputs(require_running=False)
            time.sleep(min(0.10, max(0.0, deadline - time.monotonic())))

    def run_diagnostic(
        self,
        phase: str,
        cell: int,
        observe_seconds: float = 0.0,
        *,
        placement_confirmed: bool = False,
    ) -> None:
        if phase not in DIAGNOSTIC_PHASES:
            raise ValueError(f"invalid diagnostic phase: {phase}")
        if phase == "feed":
            self.feed_one_box()
            self.observe_phase("G1_FEED", observe_seconds)
        elif phase == "pick":
            self.feed_one_box()
            self.pick_from_load()
            self.observe_phase("G2_PICK", observe_seconds)
        elif phase == "travel":
            self.travel_loaded_to(cell)
            self.observe_phase("G3_TRAVEL", observe_seconds)
        elif phase == "place":
            self.place_hold(cell)
            self.observe_phase("G4_PLACE_HOLD", observe_seconds)
        elif phase == "retract":
            self.retract_after_placement(operator_confirmed=placement_confirmed)
            self.observe_phase("G4_RETRACT", observe_seconds)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    sub.add_parser("snapshot")
    sub.add_parser("stop")

    # 旧全自动入口暂时保留参数兼容，但在 main 中 fail-closed 禁用。
    probe = sub.add_parser("probe")
    probe.add_argument("cell", type=int, nargs="?", default=1)
    demo = sub.add_parser("demo")
    demo.add_argument("count", type=int, nargs="?", default=3)
    sub.add_parser("accept")

    diagnose = sub.add_parser("diagnose")
    diagnose.add_argument("phase", choices=DIAGNOSTIC_PHASES)
    diagnose.add_argument("cell", type=int, nargs="?", default=1)
    diagnose.add_argument("--observe-seconds", type=float, default=0.0)
    diagnose.add_argument("--confirm-rest", action="store_true")
    diagnose.add_argument("--confirm-cargo", action="store_true")
    diagnose.add_argument("--confirm-position", action="store_true")
    diagnose.add_argument("--confirm-placement", action="store_true")
    return parser


def _prepare_diagnostic(stacker: Stacker, args: argparse.Namespace) -> None:
    phase = args.phase
    stacker.check_safety_inputs(require_running=True)
    if phase in ("feed", "pick"):
        stacker.assert_action_ready()
        stacker.confirm_rest_baseline(args.confirm_rest)
    elif phase == "travel":
        if not args.confirm_position:
            raise RuntimeError("--confirm-position required: visually confirm crane at rest")
        stacker.resume_carrying(
            operator_confirmed=args.confirm_cargo,
            position=POS_REST,
        )
    elif phase == "place":
        if not args.confirm_position:
            raise RuntimeError(
                f"--confirm-position required: visually confirm crane at cell {args.cell}"
            )
        stacker.resume_carrying(
            operator_confirmed=args.confirm_cargo,
            position=args.cell,
        )
    elif phase == "retract":
        if not args.confirm_position:
            raise RuntimeError(
                f"--confirm-position required: visually confirm crane at cell {args.cell}"
            )
        stacker.resume_placement_pending(
            operator_confirmed=args.confirm_placement,
            position=args.cell,
        )


def main() -> None:
    args = build_parser().parse_args()
    mode = args.mode
    action_mode = mode in {"probe", "demo", "diagnose", "accept"}
    original_stdout = sys.stdout
    log_file = None
    stacker = None
    started = time.monotonic()
    if action_mode:
        log_dir = Path(__file__).resolve().parent / "logs"
        log_dir.mkdir(exist_ok=True)
        log_path = log_dir / f"F3_{mode}_{datetime.now():%Y%m%d_%H%M%S}.log"
        log_file = log_path.open("w", encoding="utf-8", newline="\n")
        sys.stdout = TeeStream(original_stdout, log_file)
        print(f"LOG FILE: {log_path}")

    try:
        stacker = Stacker()
        if mode == "snapshot":
            stacker.print_snapshot("F3 SNAPSHOT")
        elif mode == "stop":
            # 未知现场不撤 Lift，避免恢复 RUN 后主动掉箱。
            stacker.safe_stop(preserve_lift=True)
        elif mode == "diagnose":
            _prepare_diagnostic(stacker, args)
            stacker.run_diagnostic(
                args.phase,
                args.cell,
                args.observe_seconds,
                placement_confirmed=args.confirm_placement,
            )
            stacker.safe_stop()
        elif mode in {"probe", "demo", "accept"}:
            raise RuntimeError(
                f"{mode} disabled until G1-G4 layered calibration is signed; "
                "use diagnose gates instead"
            )
        else:
            raise ValueError(f"unknown mode: {mode}")
        print(f"ALL DONE in {time.monotonic() - started:.1f}s")
    except KeyboardInterrupt:
        print("interrupted -> load-aware safe stop")
        if stacker is not None:
            stacker.safe_stop()
        raise
    except Exception as exc:
        print(f"FAILED: {exc}")
        if stacker is not None:
            try:
                stacker.safe_stop()
            except Exception as stop_exc:
                print(f"SAFE STOP FAILED: {stop_exc}")
        raise
    finally:
        if stacker is not None:
            stacker.c.close()
        if log_file is not None:
            sys.stdout = original_stdout
            log_file.close()


if __name__ == "__main__":
    main()
