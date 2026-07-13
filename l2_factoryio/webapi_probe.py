# -*- coding: utf-8 -*-
"""H1.5：Factory I/O Web API 全量 tag 枚举与 Emitter 治理（0713 拍板#4）。

目的：
1. 枚举场景全部 tags（含未映射进 Modbus 的），寻找堆垛机 X/Z 实体坐标、
   Lift 实体状态等反馈量——若存在，可把 LIFT_POSITION_UNKNOWN 盲区升级为
   实测（"无 Z=卡住 or 无行程 no-op"一测便知）。
2. 工具化 Codex 发现的 Emitter 强制值治理：普通写 values 覆盖不了 force，
   必须走 /api/tag/values-force。

依赖：仅标准库 urllib（决策梯③）。Web API 需在 Factory I/O console 开启：
  app.web_server = True   （每次完整重启后需重新确认，不持久化）
默认 base http://localhost:7410 —— H2 现场以实际端口核实后用 --base 覆盖。

用法：
  python webapi_probe.py dump                 # 全量 tags -> stdout + JSON 落盘
  python webapi_probe.py find                 # 只打印疑似位置/升降反馈 tag
  python webapi_probe.py emitter-status       # 查看 Emitter 当前值/强制态
  python webapi_probe.py emitter-off          # force false（治理多托污染）
  python webapi_probe.py emitter-pulse        # 短暂 force true 出单箱，检出即 force false
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

import fault_lock

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DEFAULT_BASE = "http://localhost:7410"
EMITTER_TAG_ID = "8e4549f8-74ed-4dd8-ab3d-b8ddb795e8c7"  # 0713 现场读取
POSITION_KEYWORDS = (
    "position", "pos x", "pos z", "x)", "z)", "lift", "height",
    "moving", "stacker", "crane", "target",
)


def _request(base: str, path: str, method: str = "GET", payload=None):
    url = base.rstrip("/") + path
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return resp.status, (json.loads(body) if body.strip() else None)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as exc:
        raise SystemExit(
            f"Web API unreachable at {url}: {exc.reason}. "
            "在 Factory I/O console 执行 app.web_server = True 后重试；"
            "或用 --base 指定实际端口"
        )


def fetch_tags(base: str) -> list[dict]:
    status, tags = _request(base, "/api/tags")
    if status != 200 or not isinstance(tags, list):
        raise SystemExit(f"/api/tags failed: HTTP {status}: {tags}")
    return tags


def fetch_values(base: str) -> list[dict]:
    status, values = _request(base, "/api/tag/values")
    if status != 200 or not isinstance(values, list):
        raise SystemExit(f"/api/tag/values failed: HTTP {status}: {values}")
    return values


def merged_tag_table(base: str) -> list[dict]:
    tags = {t.get("id"): dict(t) for t in fetch_tags(base)}
    for v in fetch_values(base):
        entry = tags.setdefault(v.get("id"), {})
        entry.update(v)
    return list(tags.values())


def cmd_dump(base: str) -> None:
    table = merged_tag_table(base)
    out_dir = Path(__file__).resolve().parent / "logs"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"webapi_tags_{datetime.now():%Y%m%d_%H%M%S}.json"
    out_path.write_text(
        json.dumps(table, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"TAG DUMP -> {out_path} ({len(table)} tags)")
    for t in sorted(table, key=lambda x: str(x.get("name", ""))):
        print(
            f"  {t.get('name', '?'):48s} type={t.get('type', '?'):8s} "
            f"value={t.get('value', '?')} forced={t.get('isForced', False)} "
            f"id={t.get('id', '?')}"
        )


def cmd_find(base: str) -> None:
    table = merged_tag_table(base)
    hits = [
        t for t in table
        if any(k in str(t.get("name", "")).lower() for k in POSITION_KEYWORDS)
    ]
    print(f"POSITION/LIFT CANDIDATES: {len(hits)}/{len(table)} tags")
    for t in sorted(hits, key=lambda x: str(x.get("name", ""))):
        print(
            f"  {t.get('name', '?'):48s} type={t.get('type', '?'):8s} "
            f"value={t.get('value', '?')} id={t.get('id', '?')}"
        )
    if not any(
        "position" in str(t.get("name", "")).lower()
        and str(t.get("type", "")).lower() in ("float", "real", "int")
        for t in hits
    ):
        print(
            "NOTE: 未见数值型实体坐标 tag —— LIFT_POSITION_UNKNOWN 维持人工门路径"
        )


def _emitter_state(base: str) -> dict:
    # 0713 实测：/api/tag/values 条目不含 isForced/forcedValue，只有 /api/tags
    # 才携带 force 态。读回校验若走 values 端点会恒判 mismatch -> 假
    # EMITTER_STATE_UNKNOWN 锁。
    for t in fetch_tags(base):
        if t.get("id") == EMITTER_TAG_ID:
            return t
    raise SystemExit(
        f"Emitter tag {EMITTER_TAG_ID} not found; 场景不同或 id 已变化——"
        "先 dump 全量核对"
    )


def cmd_emitter_status(base: str) -> None:
    print(json.dumps(_emitter_state(base), ensure_ascii=False, indent=2))


def _force_emitter(base: str, value: bool) -> None:
    fault_lock.assert_device_write_allowed("emitter", value=value)
    payload = [{"id": EMITTER_TAG_ID, "value": value}]
    status, body = _request(base, "/api/tag/values-force", "PUT", payload)
    if status not in (200, 204):
        raise SystemExit(f"values-force HTTP {status}: {body}")


def cmd_emitter_off(base: str) -> None:
    _force_emitter(base, False)
    state = _emitter_state(base)
    print(f"EMITTER FORCED OFF: {state}")
    if state.get("value") or not state.get("isForced", False):
        raise SystemExit("emitter force-off readback mismatch — 人工核对")


def cmd_emitter_pulse(base: str, timeout: float) -> None:
    """短暂 force true 出单箱；本脚本不读 Modbus，检出交给控制器/操作者。"""
    _force_emitter(base, True)
    print(f"EMITTER FORCED TRUE for up to {timeout:.1f}s (single box window)")
    try:
        time.sleep(timeout)
    finally:
        # Ctrl-C/异常也必须先尝试关 Emitter；失败由外层持久锁定。
        _force_emitter(base, False)
    state = _emitter_state(base)
    print("EMITTER FORCED FALSE (window closed)")
    print(json.dumps(state, ensure_ascii=False, indent=2))
    if state.get("value") or not state.get("isForced", False):
        raise RuntimeError("emitter force-off readback mismatch after pulse")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default=DEFAULT_BASE)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("dump")
    sub.add_parser("find")
    sub.add_parser("emitter-status")
    sub.add_parser("emitter-off")
    pulse = sub.add_parser("emitter-pulse")
    pulse.add_argument("--seconds", type=float, default=1.5)
    args = parser.parse_args()

    if args.cmd == "dump":
        cmd_dump(args.base)
    elif args.cmd == "find":
        cmd_find(args.base)
    elif args.cmd == "emitter-status":
        cmd_emitter_status(args.base)
    elif args.cmd == "emitter-off":
        with fault_lock.command_guard("emitter-off"):
            try:
                cmd_emitter_off(args.base)
            except BaseException as exc:
                fault_lock.record_fault(
                    fault_lock.FAULT_EMITTER_STATE_UNKNOWN,
                    cell=None,
                    detail=f"emitter-off failed: {type(exc).__name__}: {exc}",
                    context={"command": "emitter-off"},
                )
                raise
    elif args.cmd == "emitter-pulse":
        with fault_lock.command_guard("emitter-pulse"):
            token = fault_lock.begin_transition(
                "emitter-pulse",
                cell=None,
                context={
                    "seconds": args.seconds,
                    "expected_before": "Emitter forced False",
                    "expected_after": "Emitter forced False after one-box window",
                },
            )
            try:
                cmd_emitter_pulse(args.base, args.seconds)
            except BaseException as exc:
                fault_lock.record_fault(
                    fault_lock.FAULT_EMITTER_STATE_UNKNOWN,
                    cell=None,
                    detail=f"emitter-pulse failed: {type(exc).__name__}: {exc}",
                    context={"transition_token": token},
                )
                raise
            fault_lock.complete_transition(token)


if __name__ == "__main__":
    main()
