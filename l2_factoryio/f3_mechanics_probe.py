# -*- coding: utf-8 -*-
"""F3 空载机械探针：验证 Right 保持是否阻断 Lift 下放。

只允许在 F6 后、场景无托盘/箱体且 Emitter=False 时运行。探针不证明
放箱成功，只为 A/B 隔离 Stacker Crane 的 Forks/Lift 互锁语义。
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

import fault_lock

from f3_stacker_control import (
    C_FORKS_R,
    C_LIFT,
    IN_AT_MIDDLE,
    IN_AT_RIGHT,
    IN_MOVING_Z,
    LoadState,
    POLL,
    Stacker,
    TeeStream,
)


EDGE_TIMEOUT = 0.35
STRICT_START_TIMEOUT = 3.0
MIN_VALID_Z_DURATION = 1.0


def wait_for_z_edge(stacker: Stacker, timeout: float) -> float | None:
    """返回 Moving Z 首次出现的秒数；未出现时返回 None。"""
    started = time.monotonic()
    while time.monotonic() - started < timeout:
        stacker.check_safety_inputs(require_running=True)
        if stacker.din(IN_MOVING_Z):
            return time.monotonic() - started
        time.sleep(min(0.02, POLL))
    return None


def monitor_z_finish_and_right(
    stacker: Stacker, timeout: float = 10.0
) -> tuple[float, bool]:
    """从已见 Z 边沿起监视到稳定结束，并记录 Right 限位是否曾丢失。"""
    started = time.monotonic()
    stable_since = None
    right_lost = False
    while time.monotonic() - started < timeout:
        stacker.check_safety_inputs(require_running=True)
        moving = stacker.din(IN_MOVING_Z)
        if not stacker.din(IN_AT_RIGHT):
            right_lost = True
        if moving:
            stable_since = None
        else:
            stable_since = stable_since or time.monotonic()
            if time.monotonic() - stable_since >= 0.20:
                return time.monotonic() - started, right_lost
        time.sleep(min(0.02, POLL))
    raise RuntimeError(f"TIMEOUT({timeout}s): B lower did not settle")


def prepare_empty_probe(stacker: Stacker) -> None:
    stacker.assert_action_ready(require_empty_scene=True)
    stacker.load_state = LoadState.EMPTY
    stacker.goto(1, "(empty mechanics probe)")
    stacker.assert_fork_position(IN_AT_MIDDLE, "Middle")
    print("* baseline: Lift=True at Middle; a real Moving Z edge is mandatory")
    stacker.coil(C_LIFT, True)
    stacker.wait_motion_cycle(
        "baseline lift raise",
        lambda: stacker.din(IN_MOVING_Z),
        start_timeout=STRICT_START_TIMEOUT,
    )


def probe_a(stacker: Stacker) -> bool:
    """A：Right 持续为 True 时写 Lift=False。"""
    print("* A: Right=True held -> Lift=False")
    stacker.forks_right_hold()
    stacker.coil(C_LIFT, False)
    edge = wait_for_z_edge(stacker, STRICT_START_TIMEOUT)
    if edge is None:
        print("A_RESULT=NO_Z_START while Right=True [interlock supported]")
        return False
    print(f"A_RESULT=Z_STARTED at {edge:.3f}s while Right=True [interlock refuted]")
    stacker.wait_stable(
        "A lower settled", lambda: not stacker.din(IN_MOVING_Z), timeout=10.0
    )
    return True


def probe_b(stacker: Stacker) -> bool:
    """B：短暂释放 Right 以触发下放，见 Z 边沿后立即重新保持。"""
    print("* B: Right=True to limit -> Right=False + Lift=False -> Z edge -> Right=True")
    stacker.forks_right_hold()
    timeline = time.monotonic()
    stacker.coil(C_FORKS_R, False)
    stacker.fork_hold = None
    stacker.coil(C_LIFT, False)
    edge = wait_for_z_edge(stacker, EDGE_TIMEOUT)
    if edge is None:
        print(f"B_RESULT=NO_Z_START within {EDGE_TIMEOUT:.2f}s after Right release")
        return False

    right_before_reassert = stacker.din(IN_AT_RIGHT)
    stacker.coil(C_FORKS_R, True)
    stacker.fork_hold = C_FORKS_R
    print(
        f"  B edge={edge:.3f}s, RightLimitBeforeReassert={right_before_reassert}, "
        f"release_to_reassert={time.monotonic() - timeline:.3f}s"
    )
    z_duration, right_lost_during_z = monitor_z_finish_and_right(stacker)
    right_after_settle = stacker.din(IN_AT_RIGHT)
    if z_duration < MIN_VALID_Z_DURATION:
        print(
            "B_RESULT=Z_ABORTED_AFTER_RIGHT_REASSERT "
            f"duration={z_duration:.3f}s (<{MIN_VALID_Z_DURATION:.1f}s)"
        )
        return False
    if not right_before_reassert or right_lost_during_z or not right_after_settle:
        print(
            "B_RESULT=Z_STARTED_BUT_RIGHT_LIMIT_LOST "
            f"before={right_before_reassert}, during={right_lost_during_z}, "
            f"after={right_after_settle}"
        )
        return False
    print(
        f"B_RESULT=PASS Z completed in {z_duration:.3f}s while Right remained held"
    )
    return True


def cleanup_empty_probe(stacker: Stacker) -> None:
    """空载专用清理；无论探针结论如何都回 Middle、Lift=False、Target=0。"""
    try:
        bits = stacker._read_fork_bits()
        stacker._clear_fork_outputs()
        stacker.fork_hold = None
        if bits != (False, True, False):
            # B 可能在两个限位之间失败；空载时清两路后直接等待自动回中。
            stacker.wait_stable(
                "empty probe cleanup one-hot Middle",
                lambda: stacker._read_fork_bits() == (False, True, False),
                timeout=8.0,
                stable_for=0.15,
            )
    finally:
        stacker.load_state = LoadState.EMPTY
        stacker.safe_stop(preserve_lift=False)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", choices=("A", "B"))
    parser.add_argument("--confirm-empty", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if not args.confirm_empty:
        raise SystemExit(
            "--confirm-empty required after F6: verify no pallet/box and Emitter=False"
        )

    log_dir = Path(__file__).resolve().parent / "logs"
    log_dir.mkdir(exist_ok=True)
    log_path = log_dir / f"F3_mechanics_{args.case}_{datetime.now():%Y%m%d_%H%M%S}.log"
    original_stdout = sys.stdout
    log_file = log_path.open("w", encoding="utf-8", newline="\n")
    sys.stdout = TeeStream(original_stdout, log_file)
    stacker = None
    transition_token = None
    try:
        with fault_lock.command_guard("mechanics-probe"):
            print(f"LOG FILE: {log_path}")
            stacker = Stacker()
            transition_token = fault_lock.begin_transition(
                f"mechanics-probe:{args.case}",
                cell=None,
                context={
                    "confirm_empty": True,
                    "expected_before": "empty scene; Middle; all outputs off",
                    "expected_after": "empty scene; Target=0; conservative stop",
                },
            )
            failure = None
            cleanup_failure = None
            try:
                prepare_empty_probe(stacker)
                passed = probe_a(stacker) if args.case == "A" else probe_b(stacker)
                stacker.print_snapshot(f"MECHANICS {args.case} RESULT")
                print(f"PROBE_{args.case}_PASS={passed}")
            except BaseException as exc:
                failure = exc
            try:
                cleanup_empty_probe(stacker)
            except BaseException as exc:
                cleanup_failure = exc
            if failure is not None or cleanup_failure is not None:
                detail = f"mechanics probe failed: {failure}"
                if cleanup_failure is not None:
                    detail += f"; cleanup/safe-stop failed: {cleanup_failure}"
                fault_lock.record_fault(
                    fault_lock.FAULT_SAFE_STOP_UNCONFIRMED
                    if cleanup_failure is not None
                    else fault_lock.FAULT_COMMAND_ABORTED,
                    cell=None,
                    detail=detail,
                    context={
                        "probe_case": args.case,
                        "transition_token": transition_token,
                    },
                )
                if failure is not None:
                    raise failure
                raise cleanup_failure
            fault_lock.complete_transition(transition_token)
            transition_token = None
    finally:
        if stacker is not None:
            stacker.c.close()
        sys.stdout = original_stdout
        log_file.close()


if __name__ == "__main__":
    main()
