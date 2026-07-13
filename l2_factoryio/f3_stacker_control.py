# -*- coding: utf-8 -*-
"""F3 快线：Python 直控 Factory I/O Automated Warehouse（Modbus TCP）。

角色：Python 是“伪 PLC”，经 Modbus TCP 读取传感器、写执行器。
口径：本产物只称“Python 直控技术预演”，不称 AC500/PLC 闭环。

0713 分层校准结论：
- Target Position 1..54=货位，0=原地停止，55=rest/载入位。
- 当前工作假设：载入台在 Left 侧、货架在 Right 侧；必须由 G2/G4 画面亲验。
- At Entry/Load/Unload/Exit 为低有效货物传感器：False=有箱，True=空。
- Lift=True 微抬取箱；带载移动必须保持 Lift=True，禁止把货物降成自由载荷。
- Factory I/O 没有 cargo-present 和当前位置反馈，因此信号门不能代替人工画面门。

安全协议：
- 主流程拆成 feed -> pick -> travel -> place -> retract 五个物理门；
  relift 只用于已确认货物仍在承载台的异常恢复。
- pick/travel 收尾只停止运动，保留 Lift=True；不得用通用清零主动掉箱。
- place 在下放后保持货叉伸出，人工确认货架承载后才单独执行 retract。
- place 若下放无 Z 边沿，禁止直接 retract；必须先 recover-lift 恢复微抬，
  画面确认货物仍由托盘承载后再 recover-retract 回中。恢复回中后的货物
  视为姿态未知，禁止继续带载行走；保存证据后必须 F6 清场重来。
- Forks Left/Right 是保持型命令：伸出期间必须保持；Lift 切换并落稳后，
  才能双输出 False 释放并自动回 Middle。
- stop/snapshot 在 Pause、Stop 或 E-stop 状态下仍必须可用。

推荐校准命令（每轮先 F6、再 F5 RUN）：
  python f3_stacker_control.py diagnose feed 1 --confirm-rest --observe-seconds 30
  python f3_stacker_control.py diagnose pick 1 --confirm-rest --observe-seconds 30
  # 画面确认货物水平且在承载台后，不复位：
  python f3_stacker_control.py diagnose travel 1 --confirm-cargo --confirm-position --observe-seconds 30
  # 仅对“完整应用重启后、从未进入 recovery 的可信新载荷”记录起点；
  # recovery 后 cargo pose 不可信，严禁用此命令继续运输：
  python f3_stacker_control.py diagnose travel 30 --current-position 1 --confirm-cargo --confirm-position --observe-seconds 30
  # 仅用于“货物仍在承载台但 Lift=False”的现场恢复：
  python f3_stacker_control.py diagnose relift 1 --confirm-cargo --confirm-position --observe-seconds 20
  python f3_stacker_control.py diagnose place 1 --confirm-cargo --confirm-position --observe-seconds 30
  # place 报 NO START 且货物仍在伸出托盘上时，分两门恢复：
  python f3_stacker_control.py diagnose recover-lift 1 --confirm-cargo --confirm-position --observe-seconds 20
  python f3_stacker_control.py diagnose recover-retract 1 --confirm-cargo --confirm-position --observe-seconds 10
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

import fault_lock


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
DIAGNOSTIC_PHASES = (
    "feed", "pick", "travel", "relift", "place",
    "place-extend", "place-lower",
    "recover-lift", "recover-retract", "retract",
)
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
    EXTENDED_HOLD = "extended_hold"      # place-extend 完成：Right 保持、Lift 仍 True、待视觉门
    RECOVERY_UNSAFE = "recovery_unsafe"
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
        # Left/Right 是保持型输出；记录已确认到限位且必须继续保持的方向。
        self.fork_hold: int | None = None

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

    def resume_lowered_carrying(
        self, *, operator_confirmed: bool, position: int
    ) -> None:
        """恢复 G4 失败后仍在承载台、但 Lift=False 的已知现场状态。"""
        if not operator_confirmed:
            raise RuntimeError(
                "cargo visual confirmation required before relift recovery"
            )
        if not 1 <= position <= 54:
            raise ValueError(f"invalid recovery cell: {position}")
        snap = self.snapshot()
        problems = []
        fork_bits = self._fork_bits_from_snapshot(snap)
        if fork_bits != (False, True, False):
            problems.append(f"fork limits not one-hot Middle: {fork_bits}")
        if snap["inputs"][IN_MOVING_X] or snap["inputs"][IN_MOVING_Z]:
            problems.append("crane still moving")
        if not snap["inputs"][IN_AT_LOAD]:
            problems.append("At Load still blocked")
        if snap["coils"][C_LIFT]:
            problems.append("Lift must be False before relift recovery")
        if snap["coils"][C_FORKS_L] or snap["coils"][C_FORKS_R]:
            problems.append("fork outputs must be False at Middle")
        if snap["target"] != 0:
            problems.append(f"Target={snap['target']} (expected 0)")
        if problems:
            raise RuntimeError("relift recovery gate failed: " + "; ".join(problems))
        # 从这里起按“货物仍在承载台”保守处理；异常清理不得主动降 Lift。
        self.load_state = LoadState.CARRYING
        self.position_hint = position
        self.fork_hold = None
        print(
            f"OPERATOR GATE: cargo visually confirmed on lowered carriage; "
            f"current position={position}"
        )

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
        if snap["coils"][C_FORKS_L] or not snap["coils"][C_FORKS_R]:
            problems.append("Forks Right hold output must remain True")
        if snap["target"] != 0:
            problems.append(f"Target={snap['target']} (expected 0)")
        if problems:
            raise RuntimeError("placement hold gate failed: " + "; ".join(problems))
        self.load_state = LoadState.PLACED_PENDING
        self.position_hint = position
        self.fork_hold = C_FORKS_R
        print(f"OPERATOR GATE: rack support confirmed at cell {position}")

    def resume_extended_recovery(
        self,
        *,
        operator_confirmed: bool,
        position: int,
        expected_lift: bool,
    ) -> None:
        """恢复 place 失败后 Right 保持伸出的已知现场状态。"""
        if not operator_confirmed:
            raise RuntimeError(
                "cargo visual confirmation required for extended-fork recovery"
            )
        if not 1 <= position <= 54:
            raise ValueError(f"invalid extended recovery cell: {position}")
        snap = self.snapshot()
        problems = []
        fork_bits = self._fork_bits_from_snapshot(snap)
        if fork_bits != (False, False, True):
            problems.append(f"fork limits not one-hot Right: {fork_bits}")
        if snap["inputs"][IN_MOVING_X] or snap["inputs"][IN_MOVING_Z]:
            problems.append("crane still moving")
        if bool(snap["coils"][C_LIFT]) != expected_lift:
            problems.append(
                f"Lift={snap['coils'][C_LIFT]} (expected {expected_lift})"
            )
        if snap["coils"][C_FORKS_L] or not snap["coils"][C_FORKS_R]:
            problems.append("Forks Right hold output must remain True")
        if snap["target"] != 0:
            problems.append(f"Target={snap['target']} (expected 0)")
        if problems:
            raise RuntimeError(
                "extended recovery gate failed: " + "; ".join(problems)
            )
        self.load_state = LoadState.CARRYING
        self.position_hint = position
        self.fork_hold = C_FORKS_R
        state = "raised" if expected_lift else "lower-commanded/no-Z"
        print(
            f"OPERATOR GATE: cargo visually confirmed on extended pallet; "
            f"state={state}; current position={position}"
        )

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
        """停止行走/输送；已确认伸出的保持型叉臂不得因清零而自动回中。"""
        if preserve_lift is None:
            preserve_lift = self.load_state in (
                LoadState.UNKNOWN,
                LoadState.CARRYING,
                LoadState.EXTENDED_HOLD,
                LoadState.RECOVERY_UNSAFE,
            )
        held_fork = getattr(self, "fork_hold", None)
        if held_fork not in (C_FORKS_L, C_FORKS_R):
            held_fork = None
        if held_fork is None:
            # H1 门3（跨进程负载感知）：新进程 fork_hold=None，但上一进程可能
            # 留下伸叉保持——线圈读回 True 即视为保持中；此时写 False 不是
            # “停止”而是主动回中拉货。支撑关系未知，默认不撤叉。
            try:
                snap = self.snapshot()
                for address in (C_FORKS_L, C_FORKS_R):
                    if snap["coils"][address]:
                        held_fork = address
                        self.fork_hold = address
                        print(
                            f"* stop: rebuilt fork hold from coil readback "
                            f"C{address}=True; refusing to auto-retract"
                        )
                        break
            except Exception as exc:
                raise RuntimeError(
                    f"safe stop aborted: cannot read back fork coils ({exc}); "
                    "refusing blind retract of possibly extended forks"
                )
        errors = []
        try:
            # 先停 X/Z 目标，避免清执行器过程中继续行走。
            self.target(0)
        except Exception as exc:
            errors.append(f"HR0: {exc}")
        for address in MOTION_COILS:
            if address == held_fork:
                # 对该部件，False 不是“停止”而是主动自动回中。
                continue
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
            bad = [
                address for address in MOTION_COILS
                if address != held_fork and snap["coils"][address]
            ]
            if held_fork is not None and not snap["coils"][held_fork]:
                errors.append(f"held fork output C{held_fork} unexpectedly False")
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
        fork_text = f"C{held_fork}=True held" if held_fork is not None else "False"
        print(
            f"SAFE STOP VERIFIED: other motion coils=False, Target=0, "
            f"Lift={lift_text}, ForkHold={fork_text}"
        )

    # 旧入口保留为兼容别名，但语义已是载荷感知停机。
    def all_stop(self) -> None:
        self.safe_stop()

    # ---- 组合动作 ----
    def crane_moving(self) -> bool:
        return self.din(IN_MOVING_X) or self.din(IN_MOVING_Z)

    def box_at_load(self) -> bool:
        # 0713 实物 A/B：入口有托盘+箱体时 At Entry=False，而空载的
        # At Load/Unload/Exit=True；四个货物检测传感器均为低有效。
        return not self.din(IN_AT_LOAD)

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

    def _fork_to_hold(self, name: str, coil_address: int, limit_input: int) -> None:
        """伸到指定侧并保持命令；调用方完成 Lift 动作后才允许释放。"""
        self.assert_fork_position(IN_AT_MIDDLE, "Middle")
        primary_error = None
        try:
            opposite = C_FORKS_R if coil_address == C_FORKS_L else C_FORKS_L
            self.coil(opposite, False)
            self.coil(coil_address, True)
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
            self.fork_hold = coil_address
            print(f"* forks one-hot {name}; C{coil_address}=True hold preserved")
        except Exception as exc:
            primary_error = exc
            try:
                # 尚未确认到限位时回到默认 Middle，避免半伸状态悬停。
                self._clear_fork_outputs()
                self.fork_hold = None
            except Exception as clear_exc:
                primary_error = RuntimeError(f"{primary_error}; {clear_exc}")
        if primary_error is not None:
            raise primary_error

    def forks_left_hold(self) -> None:
        self._fork_to_hold("Left", C_FORKS_L, IN_AT_LEFT)

    def forks_right_hold(self) -> None:
        self._fork_to_hold("Right", C_FORKS_R, IN_AT_RIGHT)

    def release_forks_to_middle(self) -> None:
        """双输出 False 释放保持，机构自动回 Middle；绝不同时写 True。"""
        bits = self._read_fork_bits()
        if bits == (False, True, False):
            self._clear_fork_outputs()
            self.fork_hold = None
            print("* forks already one-hot Middle")
            return
        if sum(bits) != 1 or bits[1]:
            raise RuntimeError(f"cannot center from invalid fork limits: {bits}")
        departed_input = IN_AT_LEFT if bits[0] else IN_AT_RIGHT
        self._clear_fork_outputs()
        self.fork_hold = None
        self.wait_stable(
            "forks departed extended limit after hold release",
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
        self.release_forks_to_middle()
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
        self.forks_left_hold()
        # 从此刻起叉已在货物下方；即使 Lift 写入/反馈随后失败，清理路径也
        # 必须按“可能带载”保守处理，不能主动写 Lift=False。
        self.load_state = LoadState.CARRYING
        self.coil(C_LIFT, True)
        try:
            self.wait_motion_cycle("lift load", lambda: self.din(IN_MOVING_Z))
        except RuntimeError as exc:
            # 0713 postF6 G2 实例：Left 到位、Lift=True 却无 Z。跨进程落锁。
            if "NO START" in str(exc):
                fault_lock.record_fault(
                    fault_lock.FAULT_LIFT_POSITION_UNKNOWN,
                    cell=None,
                    detail=f"pick wrote Lift=True but Moving Z never started: {exc}",
                    context={"phase": "pick"},
                )
                print(
                    "PERSISTENT FAULT LOCK: LIFT_POSITION_UNKNOWN recorded; "
                    "save evidence, exit and FULLY restart Factory I/O"
                )
            raise
        self.wait_stable("At Load cleared", lambda: not self.box_at_load())
        self.release_forks_to_middle()
        self.assert_loaded_transport_ready()

    def travel_loaded_to(self, cell: int) -> None:
        if not 1 <= cell <= 54:
            raise ValueError(f"cell must be 1..54, got {cell}")
        if self.load_state != LoadState.CARRYING:
            raise RuntimeError(f"travel requires CARRYING state, got {self.load_state.value}")
        self.assert_loaded_transport_ready()
        self.goto(cell, f"(loaded travel to cell {cell})")

    def relift_carried_load(self, cell: int) -> None:
        """只恢复承载台微抬状态；禁止 X 行走和叉臂动作。"""
        if self.load_state != LoadState.CARRYING:
            raise RuntimeError(
                f"relift requires operator-confirmed CARRYING state, "
                f"got {self.load_state.value}"
            )
        if self.position_hint != cell:
            raise RuntimeError(
                f"relift position evidence mismatch: confirmed={self.position_hint}, "
                f"cell={cell}"
            )
        self.assert_fork_position(IN_AT_MIDDLE, "Middle")
        print(f"* 恢复微抬：仅 Lift=True，不移动 X/叉臂（货位 {cell}）")
        # load_state 已在人工门处先标为 CARRYING；写入失败也不会主动降载。
        self.coil(C_LIFT, True)
        try:
            self.wait_motion_cycle(
                "relift carried load", lambda: self.din(IN_MOVING_Z)
            )
        except RuntimeError as exc:
            if "NO START" in str(exc):
                fault_lock.record_fault(
                    fault_lock.FAULT_LIFT_POSITION_UNKNOWN,
                    cell=cell,
                    detail=f"relift wrote Lift=True but Moving Z never started: {exc}",
                    context={"phase": "relift"},
                )
                print(
                    "PERSISTENT FAULT LOCK: LIFT_POSITION_UNKNOWN recorded; "
                    "save evidence, exit and FULLY restart Factory I/O"
                )
            raise
        self.assert_loaded_transport_ready()

    def assert_placement_hold_ready(self) -> None:
        """验证放箱观察门：Right 到位且保持，Lift 已下放，系统静止。"""
        snap = self.snapshot()
        problems = []
        fork_bits = self._fork_bits_from_snapshot(snap)
        if fork_bits != (False, False, True):
            problems.append(f"fork limits not one-hot Right: {fork_bits}")
        if snap["inputs"][IN_MOVING_X] or snap["inputs"][IN_MOVING_Z]:
            problems.append("crane still moving")
        if snap["coils"][C_LIFT]:
            problems.append("Lift must be False after placement")
        if snap["coils"][C_FORKS_L] or not snap["coils"][C_FORKS_R]:
            problems.append("Forks Right hold output must remain True")
        if snap["target"] != 0:
            problems.append(f"Target={snap['target']} (expected 0)")
        if problems:
            raise RuntimeError("placement hold actuator gate failed: " + "; ".join(problems))
        print("PLACEMENT ACTUATOR GATE OK: Right held, Lift=False, motion settled")

    def place_hold(self, cell: int) -> None:
        """0713 H1 拆门后禁用：Right 到位后立即下放正是 G4 事故形态。"""
        raise RuntimeError(
            "place is split into fail-closed gates: run place-extend, pass the "
            "visual gate, then place-lower; the fused place phase is disabled"
        )

    def place_extend(self, cell: int) -> None:
        """G4 第一段：仅伸 Right 保持，绝不写 Lift；停在下放前视觉门。"""
        if not 1 <= cell <= 54:
            raise ValueError(f"cell must be 1..54, got {cell}")
        if self.load_state != LoadState.CARRYING:
            raise RuntimeError(
                f"place-extend requires CARRYING state, got {self.load_state.value}"
            )
        if self.position_hint != cell:
            raise RuntimeError(
                f"place-extend position evidence mismatch: "
                f"confirmed={self.position_hint}, cell={cell}"
            )
        self.assert_loaded_transport_ready()
        print(
            f"* 放箱-伸叉段：Right 侧伸叉并保持；本相位禁止任何 Lift 写入"
            f"（货位 {cell}）"
        )
        self.forks_right_hold()
        self.load_state = LoadState.EXTENDED_HOLD
        print(
            "PLACE-EXTEND HOLD: inspect clearance/tilt/hook on camera; "
            "only a passing visual gate authorizes place-lower"
        )

    def resume_extended_hold(
        self, *, operator_confirmed: bool, position: int
    ) -> None:
        """place-lower 的跨进程前置：Right 保持伸出且 Lift 命令仍为 True。"""
        if not operator_confirmed:
            raise RuntimeError(
                "clearance visual confirmation required before place-lower"
            )
        if not 1 <= position <= 54:
            raise ValueError(f"invalid extended-hold cell: {position}")
        snap = self.snapshot()
        problems = []
        fork_bits = self._fork_bits_from_snapshot(snap)
        if fork_bits != (False, False, True):
            problems.append(f"fork limits not one-hot Right: {fork_bits}")
        if snap["inputs"][IN_MOVING_X] or snap["inputs"][IN_MOVING_Z]:
            problems.append("crane still moving")
        if not snap["coils"][C_LIFT]:
            problems.append("Lift command must still be True before lowering")
        if snap["coils"][C_FORKS_L] or not snap["coils"][C_FORKS_R]:
            problems.append("Forks Right hold output must remain True")
        if snap["target"] != 0:
            problems.append(f"Target={snap['target']} (expected 0)")
        if problems:
            raise RuntimeError("extended-hold gate failed: " + "; ".join(problems))
        self.load_state = LoadState.EXTENDED_HOLD
        self.position_hint = position
        self.fork_hold = C_FORKS_R
        print(
            f"OPERATOR GATE: clearance visually confirmed at cell {position}; "
            "lowering authorized"
        )

    def place_lower(self, cell: int) -> None:
        """G4 第二段：视觉门通过后才下放；无 Z 即持久故障锁。"""
        if not 1 <= cell <= 54:
            raise ValueError(f"cell must be 1..54, got {cell}")
        if self.load_state != LoadState.EXTENDED_HOLD:
            raise RuntimeError(
                f"place-lower requires EXTENDED_HOLD state, got {self.load_state.value}"
            )
        if self.position_hint != cell:
            raise RuntimeError(
                f"place-lower position evidence mismatch: "
                f"confirmed={self.position_hint}, cell={cell}"
            )
        self.assert_fork_position(IN_AT_RIGHT, "Right")
        print(f"* 放箱-下放段：Lift=False，要求真实 Z 边沿（货位 {cell}）")
        self.coil(C_LIFT, False)
        # 空载 A 探针已实测 Right=True 时下降会出现真实 Z 边沿；任何 NO START
        # 都是物理状态失配 -> 持久故障锁（fail-closed，跨进程不可绕过）。
        try:
            self.wait_motion_cycle("lower load", lambda: self.din(IN_MOVING_Z))
        except RuntimeError as exc:
            if "NO START" in str(exc):
                fault_lock.record_fault(
                    fault_lock.FAULT_LIFT_POSITION_UNKNOWN,
                    cell=cell,
                    detail=(
                        "place-lower wrote Lift=False but Moving Z never "
                        f"started: {exc}"
                    ),
                    context={"phase": "place-lower"},
                )
                print(
                    "PERSISTENT FAULT LOCK: LIFT_POSITION_UNKNOWN recorded; "
                    "save evidence, exit and FULLY restart Factory I/O"
                )
            raise
        print(f"* placement settle dwell: {PLACEMENT_SETTLE_DWELL:.1f}s")
        time.sleep(PLACEMENT_SETTLE_DWELL)
        self.assert_placement_hold_ready()
        self.load_state = LoadState.PLACED_PENDING
        print("PLACEMENT HOLD: inspect rack support before running retract")

    def recover_place_hold_lift(self, cell: int) -> None:
        """place 无 Z 边沿后的第一道恢复门：保持伸叉，只恢复 Lift=True。"""
        if self.load_state != LoadState.CARRYING:
            raise RuntimeError(
                f"recover-lift requires CARRYING state, got {self.load_state.value}"
            )
        if self.position_hint != cell:
            raise RuntimeError(
                f"recover-lift position evidence mismatch: "
                f"confirmed={self.position_hint}, cell={cell}"
            )
        self.assert_fork_position(IN_AT_RIGHT, "Right")
        print(
            f"* 放箱失败恢复-抬起：Right 保持，先 Lift=True；"
            f"禁止在此相位回中（货位 {cell}）"
        )
        self.coil(C_LIFT, True)

        # 若平台确实已下放，会出现 Z 边沿；若 place 的下降从未启动，平台本就
        # 在抬起位置，允许无边沿，但仅限本恢复相位且必须随后校验输出/静止状态。
        t0 = time.monotonic()
        saw_motion = False
        while time.monotonic() - t0 < START_TIMEOUT:
            self.check_safety_inputs(require_running=True)
            if self.din(IN_MOVING_Z):
                saw_motion = True
                print(
                    f"  [start {time.monotonic() - t0:4.2f}s] "
                    "recover extended load lift"
                )
                break
            time.sleep(POLL)
        if saw_motion:
            self.wait_stable(
                "recover extended load lift settled",
                lambda: not self.din(IN_MOVING_Z),
                timeout=STEP_TIMEOUT,
            )
        else:
            print(
                "  [recovery-only] no Z edge: platform may already be raised; "
                "visual gate remains mandatory before recover-retract"
            )

        self.resume_extended_recovery(
            operator_confirmed=True,
            position=cell,
            expected_lift=True,
        )
        print("RECOVERY HOLD: inspect pallet/cargo before recover-retract")

    def recover_place_hold_retract(self, cell: int) -> None:
        """第二道恢复门：Lift=True 且画面确认后，才把伸出货物带回承载台。"""
        if self.load_state != LoadState.CARRYING:
            raise RuntimeError(
                f"recover-retract requires CARRYING state, got {self.load_state.value}"
            )
        if self.position_hint != cell:
            raise RuntimeError(
                f"recover-retract position evidence mismatch: "
                f"confirmed={self.position_hint}, cell={cell}"
            )
        self.resume_extended_recovery(
            operator_confirmed=True,
            position=cell,
            expected_lift=True,
        )
        self.release_forks_to_middle()
        self.assert_loaded_transport_ready()
        self.load_state = LoadState.RECOVERY_UNSAFE
        # 0713 现场教训：一次恢复后继续运输 -> cell 30 掉落。锁必须跨进程。
        fault_lock.record_fault(
            fault_lock.FAULT_RECOVERY_UNSAFE,
            cell=cell,
            detail=(
                "recover-retract completed; cargo pose untrusted after recovery "
                "-- transport forbidden until full application restart"
            ),
            context={"phase": "recover-retract"},
        )
        print(
            "RECOVERY COMPLETE: pallet/cargo returned to raised carriage; "
            "pose is untrusted -> PERSISTENT FAULT LOCK recorded; "
            "save evidence, exit and FULLY restart Factory I/O -- DO NOT TRAVEL"
        )

    def retract_after_placement(self, *, operator_confirmed: bool) -> None:
        if not operator_confirmed:
            raise RuntimeError("operator confirmation required before fork retract")
        if self.load_state != LoadState.PLACED_PENDING:
            raise RuntimeError(
                f"retract requires PLACED_PENDING state, got {self.load_state.value}"
            )
        self.assert_fork_position(IN_AT_RIGHT, "Right")
        self.release_forks_to_middle()
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
        cargo_confirmed: bool = False,
        placement_confirmed: bool = False,
    ) -> None:
        if phase not in DIAGNOSTIC_PHASES:
            raise ValueError(f"invalid diagnostic phase: {phase}")
        if phase == "feed":
            self.feed_one_box()
            self.observe_phase("G1_FEED", observe_seconds)
        elif phase == "pick":
            if self.box_at_load():
                if not cargo_confirmed:
                    raise RuntimeError(
                        "--confirm-cargo required: visually confirm the staged load "
                        "before reusing G1 evidence"
                    )
                self.load_state = LoadState.STAGED
                print("OPERATOR GATE: reuse visually confirmed G1 staged cargo")
            else:
                self.feed_one_box()
            self.pick_from_load()
            self.observe_phase("G2_PICK", observe_seconds)
        elif phase == "travel":
            self.travel_loaded_to(cell)
            self.observe_phase("G3_TRAVEL", observe_seconds)
        elif phase == "relift":
            self.relift_carried_load(cell)
            self.observe_phase("RECOVERY_RELIFT", observe_seconds)
        elif phase == "place":
            self.place_hold(cell)  # fail-closed：指引改用 place-extend/place-lower
        elif phase == "place-extend":
            self.place_extend(cell)
            self.observe_phase("G4_PLACE_EXTEND_HOLD", observe_seconds)
        elif phase == "place-lower":
            self.place_lower(cell)
            self.observe_phase("G4_PLACE_LOWER_HOLD", observe_seconds)
        elif phase == "recover-lift":
            self.recover_place_hold_lift(cell)
            self.observe_phase("RECOVERY_PLACE_LIFT_HOLD", observe_seconds)
        elif phase == "recover-retract":
            self.recover_place_hold_retract(cell)
            self.observe_phase("RECOVERY_PLACE_RETRACT", observe_seconds)
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
    diagnose.add_argument(
        "--confirm-clearance",
        action="store_true",
        help="visual gate passed on extended pallet (place-lower prerequisite)",
    )
    diagnose.add_argument(
        "--current-position",
        type=int,
        default=None,
        help="operator-confirmed current position for travel; default=55/rest",
    )

    mark_fault = sub.add_parser(
        "mark-fault",
        help="record an operator-observed persistent fault (e.g. camera-confirmed drop)",
    )
    mark_fault.add_argument("code", choices=fault_lock.KNOWN_FAULTS)
    mark_fault.add_argument("--cell", type=int, default=None)
    mark_fault.add_argument("--detail", required=True)

    reset_epoch = sub.add_parser(
        "reset-epoch",
        help="clear the persistent fault lock after a FULL application restart",
    )
    reset_epoch.add_argument(
        "--operator-confirmed-restart",
        action="store_true",
        help="assert Factory I/O was fully exited and restarted (F6 does NOT count)",
    )
    reset_epoch.add_argument("--note", default="")
    return parser


def _prepare_diagnostic(stacker: Stacker, args: argparse.Namespace) -> None:
    phase = args.phase
    stacker.check_safety_inputs(require_running=True)
    if phase in ("feed", "pick"):
        stacker.assert_action_ready()
        stacker.confirm_rest_baseline(args.confirm_rest)
    elif phase == "travel":
        if not args.confirm_position:
            raise RuntimeError(
                "--confirm-position required: visually confirm current crane position"
            )
        current_position = (
            POS_REST if args.current_position is None else args.current_position
        )
        stacker.resume_carrying(
            operator_confirmed=args.confirm_cargo,
            position=current_position,
        )
    elif phase == "relift":
        if not args.confirm_position:
            raise RuntimeError(
                f"--confirm-position required: visually confirm crane at cell {args.cell}"
            )
        stacker.resume_lowered_carrying(
            operator_confirmed=args.confirm_cargo,
            position=args.cell,
        )
    elif phase == "place":
        # fail-closed：不做任何现场写入，run_diagnostic 会直接抛拆门指引。
        pass
    elif phase == "place-extend":
        if not args.confirm_position:
            raise RuntimeError(
                f"--confirm-position required: visually confirm crane at cell {args.cell}"
            )
        stacker.resume_carrying(
            operator_confirmed=args.confirm_cargo,
            position=args.cell,
        )
    elif phase == "place-lower":
        if not args.confirm_position:
            raise RuntimeError(
                f"--confirm-position required: visually confirm crane at cell {args.cell}"
            )
        if not args.confirm_clearance:
            raise RuntimeError(
                "--confirm-clearance required: pass the visual gate (clearance/"
                "tilt/hook) on the extended pallet before lowering"
            )
        stacker.resume_extended_hold(
            operator_confirmed=args.confirm_clearance,
            position=args.cell,
        )
    elif phase == "recover-lift":
        if not args.confirm_position:
            raise RuntimeError(
                f"--confirm-position required: visually confirm crane at cell {args.cell}"
            )
        stacker.resume_extended_recovery(
            operator_confirmed=args.confirm_cargo,
            position=args.cell,
            expected_lift=False,
        )
    elif phase == "recover-retract":
        if not args.confirm_position:
            raise RuntimeError(
                f"--confirm-position required: visually confirm crane at cell {args.cell}"
            )
        stacker.resume_extended_recovery(
            operator_confirmed=args.confirm_cargo,
            position=args.cell,
            expected_lift=True,
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


def _finish_diagnostic(stacker: Stacker, phase: str) -> None:
    """保留需要跨进程维持的物理状态；其余相位执行载荷感知停机。"""
    if phase in ("place-extend", "place-lower", "recover-lift"):
        print(
            "EXTENDED HOLD PRESERVED: Forks Right remains True; "
            "use only the next visually authorized phase"
        )
        return
    if phase == "relift":
        print(
            "RELIFT STATE PRESERVED: successful recovery wrote Lift=True only; "
            "no X/fork cleanup writes required"
        )
        return
    stacker.safe_stop()


def _assert_unlocked_for_action(mode: str) -> None:
    """H1 门2：持久故障锁下只允许取证类命令；--confirm-* 不能绕过。"""
    state = fault_lock.load_state()
    if not fault_lock.is_locked(state):
        return
    if mode in {"snapshot", "stop", "mark-fault", "reset-epoch"}:
        return
    raise RuntimeError(
        "PERSISTENT FAULT LOCK ACTIVE -> " + fault_lock.lock_reason(state)
        + "; only snapshot/stop/mark-fault are allowed. Unlock path: save "
        "evidence, FULLY exit and restart Factory I/O, verify an empty-scene "
        "preflight, then run reset-epoch --operator-confirmed-restart"
    )


def _run_reset_epoch(stacker: Stacker, args: argparse.Namespace) -> None:
    """清锁前强制在线空场 preflight：RUN 中、全零输出、one-hot Middle。"""
    stacker.check_safety_inputs(require_running=True)
    preflight_ok = False
    try:
        stacker.assert_action_ready()
        preflight_ok = True
    except RuntimeError as exc:
        print(f"EMPTY-SCENE PREFLIGHT FAILED: {exc}")
    state = fault_lock.clear_for_new_epoch(
        operator_confirmed_restart=args.operator_confirmed_restart,
        preflight_passed=preflight_ok,
        note=args.note,
    )
    print(
        "FAULT LOCK CLEARED: new epoch started at "
        f"{state['epoch_started_at']}; cleared={state['cleared_fault']}"
    )


def main() -> None:
    args = build_parser().parse_args()
    mode = args.mode
    action_mode = mode in {
        "probe", "demo", "diagnose", "accept", "reset-epoch", "mark-fault",
    }
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
        _assert_unlocked_for_action(mode)
        if mode == "mark-fault":
            state = fault_lock.record_fault(
                args.code, cell=args.cell, detail=args.detail,
                context={"phase": "operator-mark"},
            )
            print(f"PERSISTENT FAULT LOCK RECORDED: {fault_lock.lock_reason(state)}")
            return
        stacker = Stacker()
        if mode == "snapshot":
            stacker.print_snapshot("F3 SNAPSHOT")
        elif mode == "stop":
            # 未知现场不撤 Lift，避免恢复 RUN 后主动掉箱。
            stacker.safe_stop(preserve_lift=True)
        elif mode == "reset-epoch":
            _run_reset_epoch(stacker, args)
        elif mode == "diagnose":
            _prepare_diagnostic(stacker, args)
            stacker.run_diagnostic(
                args.phase,
                args.cell,
                args.observe_seconds,
                cargo_confirmed=args.confirm_cargo,
                placement_confirmed=args.confirm_placement,
            )
            _finish_diagnostic(stacker, args.phase)
            fault_lock.record_phase_state(
                phase=args.phase,
                cell=args.cell,
                load_state_value=stacker.load_state.value,
                fork_hold=stacker.fork_hold,
                lift_command=None,
            )
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
