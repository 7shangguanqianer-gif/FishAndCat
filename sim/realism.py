# -*- coding: utf-8 -*-
"""
realism.py — L7 拟真度阶梯:三档同管线sim对比(档1 数据模型 / 档2 H设计 / 档3 综合情景)
设计(docs/L7_拟真度阶梯设计.md,0705 用户拍板"分3档展示"):
  三档共用同一管线 = 初始入库 120 件 + 混合流 100 周期(每周期1存+1取,双命令),
  只差拟真开关,保证跨档可比:
    档1 = 匀速 + 固定权重 + 固定节拍 + 无装卸 + 频次全知 + 无故障(对照口径,文献可比)
    档2 = 梯形加减速 + 场景权重(= sim H设计口径,复用 mixed_ops.run_mixed 保证数字同源)
    档3 = 档2 物理口径 + 泊松到达(峰谷) + 装卸时间 + 频次估计噪声 + 故障注入
  档3 定位=在显式情景假设下检查均值/分位/违规；不称“最真实”，也不预设全部策略排序不变。
  头条 H 锁不动,本脚本不进回归门(与 sensitivity.py 同例)。
跨档可比指标:出库均时(纯行程,C3 流版)/ 双命令服务总时 / 违规;
档3 专属指标:响应时间 P50/P95(含排队)、利用率、故障停机——工业客户视角(可用性)。
口径纪律:装卸时间只进"服务时间/忙时",不进"出库行程均时"——后者跨档同定义。
  运行:python realism.py            → out/realism_matrix_data.csv + out/realism_matrix_params.csv
                                      + figs/fig16_拟真度阶梯.png
     python realism.py --quick    → 30 周期自检
"""
import argparse
import csv
import hashlib
import json
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import warehouse_sim as ws
from mixed_ops import (LBL, STRATS, build_workload, initial_layout,
                       online_strategy_callable, resolve_strategy_mode, run_mixed)

HERE = os.path.dirname(os.path.abspath(__file__))
SEED, N_INIT, RULE = 2026, 120, "sum"

# ---- 档3参数：G1为推导+扫描；G2-G4为显式情景假设，均非现场标定 ----
HANDLE_S = 15.0        # 〔G1〕单次存/取的装卸附加时间 s(I/O 侧+货位侧两次货叉循环合计)
RHO_PEAK = 0.75        # 〔G2〕高峰时段堆垛机目标利用率(决定泊松到达强度)
RHO_OFF = 0.35         # 〔G2〕低谷时段目标利用率
FREQ_SIGMA = 0.30      # 〔G3〕访问频次估计噪声:f_est = f_true·exp(N(0,σ²)) 对数正态乘性
MTBF_S = 3000.0        # 〔G4〕忙时平均无故障时间情景值 s
MTTR_S = 600.0         # 〔G4〕平均修复时间 s


def stream_hash(value):
    """Canonical SHA256 for deterministic exogenous-stream evidence."""
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True,
                     separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def build_noise_factors(goods, sigma, seed):
    """Pre-generate one multiplicative frequency factor per gid."""
    if sigma <= 0:
        return {g.gid: 1.0 for g in goods}
    rng = random.Random(seed)
    return {g.gid: math.exp(rng.gauss(0.0, sigma)) for g in goods}


def build_noise_stream(goods, inbound_goods, sigma, seed):
    """Two independent, strategy-exogenous noise vectors (legacy offsets preserved)."""
    initial = build_noise_factors(goods, sigma, seed + 21)
    inbound = build_noise_factors(inbound_goods, sigma, seed + 22)
    payload = {
        "sigma": sigma,
        "initial": [(g.gid, initial[g.gid]) for g in goods],
        "inbound": [(g.gid, inbound[g.gid]) for g in inbound_goods],
    }
    return {"initial": initial, "inbound": inbound, "hash": stream_hash(payload)}


def build_fault_intervals(cycles, seed, mtbf_s=MTBF_S):
    """Pre-generate busy-time Exp(MTBF) gaps shared by every compared strategy."""
    if cycles < 0:
        raise ValueError("cycles must be non-negative")
    if mtbf_s <= 0:
        raise ValueError("mtbf_s must be positive")
    rng = random.Random(seed + 29)
    return [rng.expovariate(1.0 / mtbf_s) for _ in range(cycles + 1)]


def _tier3_params(overrides=None):
    overrides = overrides or {}
    return {
        "handle_s": float(overrides.get("handle_s", HANDLE_S)),
        "arrival_rho": float(overrides.get("arrival_rho", RHO_PEAK)),
        "arrival_rho_off": float(overrides.get("arrival_rho_off", RHO_OFF)),
        "freq_noise_sigma": float(overrides.get("freq_noise_sigma", FREQ_SIGMA)),
        "fault_mtbf_s": float(overrides.get("fault_mtbf_s", MTBF_S)),
        "fault_mttr_s": float(overrides.get("fault_mttr_s", MTTR_S)),
    }


def noisy_clone(goods, sigma, seed, factors=None):
    """频次估计噪声:决策侧用 f_est 克隆(布局/评分都基于估计值),
    真实需求抽样(build_workload 的 requests)仍用 f_true——现实=画像不准但需求是真的。
    返回 gid 对齐的克隆列表;sigma=0 时返回原对象(档1/2 路径零扰动)。"""
    if sigma <= 0:
        return list(goods)
    factors = factors or build_noise_factors(goods, sigma, seed)
    out = []
    for g in goods:
        c = ws.Good(g.gid, g.name, g.weight, g.freq * factors[g.gid], g.vol)
        out.append(c)
    return out


def build_arrivals(cycles, seed, reference_pair_s, rho_peak=None, rho_off=None):
    """生成策略外生的共同到达流。

    ``reference_pair_s`` 只由统一的 seq reference 负载估计一次；不得按待比较
    策略各自反推，否则响应分位数会混入不同到达强度，失去 CRN 公平性。
    """
    if cycles < 0:
        raise ValueError("cycles must be non-negative")
    if reference_pair_s <= 0:
        raise ValueError("reference_pair_s must be positive")
    rho_peak = RHO_PEAK if rho_peak is None else float(rho_peak)
    rho_off = RHO_OFF if rho_off is None else float(rho_off)
    if rho_peak <= 0 or rho_off <= 0:
        raise ValueError("arrival rho values must be positive")
    rng = random.Random(seed + 23)
    arrivals, t = [], 0.0
    for k in range(cycles):
        rho = rho_peak if k < cycles // 2 else rho_off
        t += rng.expovariate(rho / reference_pair_s)
        arrivals.append(t)
    return arrivals


def common_arrivals(goods, new_goods, requests, fn, w_max, f_max,
                    fn_batch=None, cycles=100, seed=SEED):
    """以统一 seq reference 估计服务均值并生成四策略共享的到达时刻。"""
    goods_est = noisy_clone(goods, FREQ_SIGMA, seed + 21)
    new_est = noisy_clone(new_goods, FREQ_SIGMA, seed + 22)
    probe = run_mixed("seq", goods_est, new_est, requests, fn, w_max, f_max,
                      fn_batch)
    reference_pair_s = probe["tot_dual"] / cycles + 2 * HANDLE_S
    return build_arrivals(cycles, seed, reference_pair_s), reference_pair_s


def common_arrivals_for_workload(goods, workload, fn, w_max, f_max,
                                 fn_batch=None, seed=SEED, tier3_params=None):
    """Scenario-aware seq reference; rejected gate cycles are not service samples."""
    params = _tier3_params(tier3_params)
    valid_cycles = int(workload["valid_cycles"])
    scheduled_cycles = int(workload["scheduled_cycles"])
    if valid_cycles <= 0:
        raise ValueError("workload must contain at least one valid dispatch cycle")
    all_inbound = [item["inbound_good"] for item in workload["cycles"]]
    noise = build_noise_stream(
        goods, all_inbound, params["freq_noise_sigma"], seed
    )
    goods_est = noisy_clone(
        goods, params["freq_noise_sigma"], seed + 21, noise["initial"]
    )
    valid_est = []
    for good in workload["valid_inbound_goods"]:
        factor = noise["inbound"][good.gid]
        valid_est.append(ws.Good(
            good.gid, good.name, good.weight, good.freq * factor, good.vol
        ))
    probe = run_mixed(
        "seq", goods_est, valid_est, workload["requests"], fn, w_max, f_max,
        fn_batch,
    )
    reference_pair_s = probe["tot_dual"] / valid_cycles + 2 * params["handle_s"]
    arrivals = build_arrivals(
        scheduled_cycles, seed, reference_pair_s,
        rho_peak=params["arrival_rho"], rho_off=params["arrival_rho_off"],
    )
    return arrivals, reference_pair_s


def _inventory_snapshot(pos_of):
    return [
        {"gid": gid, "col": pos[0], "tier": pos[1]}
        for gid, pos in sorted(pos_of.items())
    ]


def _emit_event(event_sink, event):
    if event_sink is None:
        return
    if callable(event_sink):
        event_sink(event)
        return
    if hasattr(event_sink, "append"):
        event_sink.append(event)
        return
    raise TypeError("event_sink must be callable or append-capable")


def _legacy_event_records(new_goods, requests, cycles):
    if len(new_goods) != cycles or len(requests) != cycles:
        raise ValueError("legacy Tier 3 workload length must equal cycles")
    return [
        {"cycle": k, "status": "PAIRED_IN_OUT", "dispatch": True,
         "inbound_good": good_in, "outbound_good": good_out}
        for k, (good_in, good_out) in enumerate(zip(new_goods, requests))
    ]


def _provenance_payload(value):
    """Turn an event payload into JSON data without dropping Good fields.

    Events-only callers do not have the richer scenario-workload manifest, so
    their provenance hash must cover every supplied record field and every
    cargo attribute instead of maintaining a second, lossy field list.
    """
    if isinstance(value, ws.Good):
        return {
            "gid": value.gid,
            "name": value.name,
            "weight": value.weight,
            "freq": value.freq,
            "volume": value.vol,
        }
    if isinstance(value, dict):
        return {key: _provenance_payload(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_provenance_payload(item) for item in value]
    return value


def _legacy_workload_hash(goods, records, seed):
    """Canonical provenance for legacy-generated or events-only inputs."""
    return stream_hash({
        "schema_version": "events_only_workload_v2",
        "seed": seed,
        "initial": _provenance_payload(goods),
        "cycles": _provenance_payload(records),
    })


def _completed_phases(arrival, start, finish, t_in, t_link, t_out,
                      handle_s, fault_offsets, fault_mttr_s):
    """Build visual phases and splice every productive-time fault crossing.

    Each offset is measured from the cycle's productive-service start.  Queue
    and prior repairs consume wall-clock time but never advance that cursor.
    Motion/handling freezes at the exact local `u` and resumes from it.
    """
    if fault_offsets is None:
        fault_offsets = []
    elif isinstance(fault_offsets, (int, float)):
        fault_offsets = [float(fault_offsets)]
    else:
        fault_offsets = [float(value) for value in fault_offsets]
    if fault_offsets != sorted(fault_offsets):
        raise ValueError("fault busy-time offsets must be sorted")

    phases = [{"name": "QUEUE", "t0": arrival, "t1": start}]
    operations = (
        ("INBOUND_TRAVEL", t_in),
        ("STORE_HANDLE", handle_s),
        ("LINK_TRAVEL", t_link),
        ("RETRIEVE_HANDLE", handle_s),
        ("OUTBOUND_TRAVEL", t_out),
    )
    cursor = start
    productive_cursor = 0.0
    fault_index = 0
    milestones = {}
    eps = 1.0e-12

    for name, duration in operations:
        phase_start = productive_cursor
        phase_end = phase_start + duration
        phase_faults = []
        while fault_index < len(fault_offsets):
            offset = fault_offsets[fault_index]
            if offset > phase_end + eps:
                break
            if offset < phase_start - eps:
                raise ValueError("fault busy-time offsets overlap prior operation")
            phase_faults.append((fault_index, max(phase_start, min(phase_end, offset))))
            fault_index += 1

        local_cursor = 0.0
        for local_fault_number, (global_fault_number, offset) in enumerate(phase_faults):
            cut = offset - phase_start
            fraction = cut / duration if duration > 0.0 else 0.0
            if cut > local_cursor + eps:
                if len(phase_faults) == 1 and local_cursor == 0.0:
                    segment = "before_fault"
                elif local_cursor == 0.0:
                    segment = "before_fault"
                else:
                    segment = "between_faults"
                phases.append({
                    "name": name, "segment": segment,
                    "t0": cursor, "t1": cursor + (cut - local_cursor),
                    "u0": (local_cursor / duration if duration > 0.0 else 0.0),
                    "u1": fraction,
                })
                cursor += cut - local_cursor
            phases.append({
                "name": "FAULT_RECOVERY", "operation_phase": name,
                "fault_index": global_fault_number,
                "t0": cursor, "t1": cursor + fault_mttr_s,
                "frozen_u": fraction, "sim_modelled": True,
            })
            cursor += fault_mttr_s
            local_cursor = cut

        if duration > local_cursor + eps:
            phases.append({
                "name": name,
                "segment": ("after_fault" if phase_faults else "full"),
                "t0": cursor, "t1": cursor + (duration - local_cursor),
                "u0": (local_cursor / duration if duration > 0.0 else 0.0),
                "u1": 1.0,
            })
            cursor += duration - local_cursor
        productive_cursor = phase_end
        if name == "STORE_HANDLE":
            milestones["stored"] = cursor
        elif name == "RETRIEVE_HANDLE":
            milestones["retrieved"] = cursor
        elif name == "OUTBOUND_TRAVEL":
            milestones["outfeed"] = cursor

    if fault_index != len(fault_offsets):
        raise ValueError("fault busy-time offset lies outside productive service")
    # Preserve exact metric arithmetic while forcing visual phases to close.
    phases[-1]["t1"] = finish
    milestones["outfeed"] = finish
    return phases, milestones


def run_tier3(strat_name, goods, new_goods, requests, fn, w_max, f_max,
              fn_batch=None, arrivals=None, cycles=100, seed=SEED,
              workload=None, events=None, fault_intervals=None,
              event_sink=None, noise_stream=None, tier3_params=None,
              router_objective="lexicographic", batch_known=True):
    """Single Tier 3 event engine with an exact legacy-default compatibility path.

    `workload` or `events` may contain gate-reject cycles.  Exogenous arrivals,
    noise and busy-time fault intervals are generated outside strategy branches
    and exposed by hash.  Event details are built only when a sink is supplied.
    """
    params = _tier3_params(tier3_params)
    decision = resolve_strategy_mode(
        strat_name, goods, batch_known=batch_known, objective=router_objective
    )
    picked = decision["picked"]
    extended = any(value is not None for value in (
        workload, events, fault_intervals, event_sink, noise_stream, tier3_params,
    )) or str(strat_name).lower() not in {"seq", "near", "score", "awra"}
    # The no-extension path is an exact historical-number compatibility lane.
    # Dynamic experiments use the corrected productive busy-time clock below;
    # the legacy lane intentionally keeps its old arithmetic byte-for-byte.
    legacy_compat = not extended
    if workload is not None and events is not None:
        raise ValueError("workload and events are mutually exclusive provenance inputs")
    if events is not None:
        records = list(events)
    elif workload is not None:
        records = list(workload["cycles"])
    else:
        records = _legacy_event_records(new_goods, requests, cycles)
    if len(records) != cycles:
        raise ValueError(f"run_tier3 expected {cycles} scheduled events, got {len(records)}")
    if arrivals is None or len(arrivals) != len(records):
        raise ValueError("run_tier3 requires one common arrivals vector per scheduled event")

    all_inbound = [item["inbound_good"] for item in records]
    noise_stream = noise_stream or build_noise_stream(
        goods, all_inbound, params["freq_noise_sigma"], seed
    )
    goods_est = noisy_clone(
        goods, params["freq_noise_sigma"], seed + 21, noise_stream["initial"]
    )
    inbound_est = {}
    for good in all_inbound:
        factor = noise_stream["inbound"][good.gid]
        inbound_est[good.gid] = ws.Good(
            good.gid, good.name, good.weight, good.freq * factor, good.vol
        )
    intervals = list(fault_intervals) if fault_intervals is not None else build_fault_intervals(
        len(records), seed, params["fault_mtbf_s"]
    )
    if not intervals or any(value <= 0 for value in intervals):
        raise ValueError("fault_intervals must contain positive busy-time gaps")
    shared_hashes = {
        "workload_hash": (workload["workload_hash"] if workload is not None
                          else _legacy_workload_hash(goods, records, seed)),
        "arrivals_hash": stream_hash(arrivals),
        "noise_hash": noise_stream["hash"],
        "fault_stream_hash": stream_hash({
            "mtbf_s": params["fault_mtbf_s"],
            "mttr_s": params["fault_mttr_s"],
            "intervals": intervals,
        }),
    }
    planned_dispatch_count = sum(bool(item.get("dispatch", True)) for item in records)
    planned_rejected_count = len(records) - planned_dispatch_count
    wh, pos_of, initial_failed = initial_layout(
        picked, goods_est, fn_batch or fn, w_max, f_max,
        seed=seed, return_failed=True,
    )
    if initial_failed and not extended:
        raise AssertionError(picked)
    if initial_failed:
        return {
            "tot_dual": 0.0,
            "busy_total": 0.0,
            "avg_retr": 0.0,
            "resp_p50": None,
            "resp_p95": None,
            "util": None,
            "n_down": 0,
            "downtime": 0.0,
            "fails": len(initial_failed),
            "viol": 0,
            "status": "INFEASIBLE",
            "initial_fails": len(initial_failed),
            "initial_placed": len(pos_of),
            "scheduled_cycles": len(records),
            "valid_cycles": planned_dispatch_count,
            "rejected_cycles": planned_rejected_count,
            "processed_scheduled_cycles": 0,
            "processed_valid_cycles": 0,
            "processed_rejected_cycles": 0,
            "completed_cycles": 0,
            "unprocessed_cycles": len(records),
            "terminal_failure_cycle": None,
            "terminal_failure_stage": "INITIAL_LAYOUT",
            "failure_policy": "TERMINATE_NO_FALLBACK",
            "response_sample_n": 0,
            "dual_time_sample_n": 0,
            "util_sample_n": 0,
            "productive_busy_s": 0.0,
            "fault_clock_mode": "productive_busy_time_v1",
            "reject_service_s": (workload.get("reject_service_s", 0)
                                  if workload is not None else 0),
            "router": decision,
            "picked_strategy": picked,
            "strategy_switches": 0,
            "advisory_count": sum(item.get("advisory") is not None for item in records),
            "stream_hashes": shared_hashes,
        }
    online = online_strategy_callable(picked, seed)
    next_fail_busy = intervals[0]
    fault_cursor = 1

    crane_free = 0.0
    busy_acc = 0.0
    productive_busy_acc = 0.0
    tot_dual = 0.0
    retr_t, responses = [], []
    fails = viol = n_down = 0
    downtime = 0.0
    dispatch_count = 0
    rejected_count = 0
    processed_scheduled_cycles = 0
    terminal_failure_cycle = None
    terminal_failure_stage = None

    for k, record in enumerate(records):
        processed_scheduled_cycles = k + 1
        arrival = arrivals[k]
        snapshot_before = _inventory_snapshot(pos_of) if event_sink is not None else None
        if not record.get("dispatch", True):
            rejected_count += 1
            event = {
                "cycle": k, "status": "REJECT_NO_DISPATCH",
                "arrival": arrival, "start": arrival, "finish": arrival,
                "service": 0.0, "response": None,
                "inbound_gid": record["inbound_good"].gid,
                "outbound_gid": None,
                "inbound_profile": record.get("inbound_profile"),
                "advisory": record.get("advisory"),
                "phases": [{"name": "GATE_REJECT", "t0": arrival, "t1": arrival,
                            "sim_modelled": True}],
                "ownership_events": [],
                "inventory_before": snapshot_before,
                "inventory_after": (list(snapshot_before)
                                    if snapshot_before is not None else None),
            }
            _emit_event(event_sink, event)
            continue

        dispatch_count += 1
        true_in = record["inbound_good"]
        good_in = inbound_est[true_in.gid]
        good_out = record["outbound_good"]
        if good_out is None or good_out.gid not in pos_of:
            raise ValueError(
                f"workload outbound gid missing before cycle {k}: "
                f"{None if good_out is None else good_out.gid}"
            )
        s_out = pos_of.pop(good_out.gid)
        s_in = online(wh, good_in, fn)
        if s_in is None:
            fails += 1
            # Placement is planned before either leg executes.  Restore the
            # outbound lookup and terminate this strategy run without silently
            # switching algorithms or corrupting the pre-registered workload.
            pos_of[good_out.gid] = s_out
            failure_time = max(arrival, crane_free)
            terminal_failure_cycle = k
            terminal_failure_stage = "ONLINE_PLACEMENT"
            event = {
                "cycle": k, "status": "PLACEMENT_FAIL_TERMINAL",
                "terminal": True,
                "failure_policy": "TERMINATE_NO_FALLBACK",
                "arrival": arrival, "start": failure_time, "finish": failure_time,
                "service": 0.0, "response": None,
                "inbound_gid": good_in.gid, "outbound_gid": good_out.gid,
                "inbound_profile": record.get("inbound_profile"),
                "advisory": record.get("advisory"),
                "phases": [{"name": "PLACEMENT_FAIL_TERMINAL",
                            "t0": failure_time, "t1": failure_time}],
                "ownership_events": [],
                "inventory_before": snapshot_before,
                "inventory_after": (list(snapshot_before)
                                    if snapshot_before is not None else None),
            }
            _emit_event(event_sink, event)
            break
        if good_in.weight > ws.tier_cap(s_in[1]) or good_in.vol > ws.CELL_VOL:
            viol += 1
        t_in = ws.travel_time(*s_in)
        t_link = ws.travel_time_between(s_in[0], s_in[1], s_out[0], s_out[1])
        t_out = ws.travel_time(*s_out)
        productive_service = t_in + t_link + t_out + 2 * params["handle_s"]
        service = productive_service
        start = max(arrival, crane_free)
        fault_offsets = []
        if legacy_compat:
            # Historical implementation: at most one failure per completed
            # cycle and the next gap begins at that cycle's end.  Kept solely
            # to protect the four published regression anchors.
            if busy_acc + service > next_fail_busy:
                fault_offsets.append(next_fail_busy - busy_acc)
                service += params["fault_mttr_s"]
                downtime += params["fault_mttr_s"]
                n_down += 1
                if fault_cursor >= len(intervals):
                    raise ValueError("fault_intervals exhausted")
                next_fail_busy = busy_acc + service + intervals[fault_cursor]
                fault_cursor += 1
        else:
            # Correct v1 clock: every Exp gap is consumed only by productive
            # motion/handling.  Queue and MTTR advance wall time, never MTBF.
            cycle_productive_end = productive_busy_acc + productive_service
            while cycle_productive_end > next_fail_busy:
                fault_offsets.append(next_fail_busy - productive_busy_acc)
                downtime += params["fault_mttr_s"]
                n_down += 1
                if fault_cursor >= len(intervals):
                    raise ValueError("fault_intervals exhausted")
                next_fail_busy += intervals[fault_cursor]
                fault_cursor += 1
            service += len(fault_offsets) * params["fault_mttr_s"]
        finish = start + service
        crane_free = finish
        busy_acc += service
        productive_busy_acc += productive_service
        tot_dual += t_in + t_link + t_out
        retr_t.append(t_out)
        response = finish - arrival
        responses.append(response)
        wh.put(s_in[0], s_in[1], good_in)
        pos_of[good_in.gid] = s_in
        wh.remove(s_out[0], s_out[1])

        if event_sink is not None:
            phases, milestones = _completed_phases(
                arrival, start, finish, t_in, t_link, t_out,
                params["handle_s"], fault_offsets, params["fault_mttr_s"],
            )
            ownership_events = [
                {"t": start, "gid": good_in.gid, "from": "QUEUE", "to": "CARRIER_IN"},
                {"t": milestones["stored"], "gid": good_in.gid,
                 "from": "CARRIER_IN", "to": "RACK"},
                {"t": milestones["retrieved"], "gid": good_out.gid,
                 "from": "RACK", "to": "CARRIER_OUT"},
                {"t": finish, "gid": good_out.gid,
                 "from": "CARRIER_OUT", "to": "OUTFEED"},
            ]
            _emit_event(event_sink, {
                "cycle": k, "status": "COMPLETED",
                "arrival": arrival, "start": start, "finish": finish,
                "service": service, "response": response,
                "inbound_gid": good_in.gid, "outbound_gid": good_out.gid,
                "inbound_profile": record.get("inbound_profile"),
                "advisory": record.get("advisory"),
                "store_slot": {"col": s_in[0], "tier": s_in[1]},
                "retrieve_slot": {"col": s_out[0], "tier": s_out[1]},
                "faulted": bool(fault_offsets),
                "fault_busy_offset": (fault_offsets[0] if fault_offsets else None),
                "fault_busy_offsets": list(fault_offsets),
                "phases": phases,
                "ownership_events": ownership_events,
                "inventory_before": snapshot_before,
                "inventory_after": _inventory_snapshot(pos_of),
            })

    responses.sort()
    n = len(responses)
    makespan = crane_free
    result = dict(tot_dual=tot_dual,
                  busy_total=busy_acc,
                  avg_retr=sum(retr_t) / len(retr_t) if retr_t else 0.0,
                  resp_p50=responses[n // 2] if n else 0.0,
                  resp_p95=responses[min(n - 1, int(n * 0.95))] if n else 0.0,
                  util=(busy_acc - downtime) / makespan if makespan else 0.0,
                  n_down=n_down, downtime=downtime,
                  fails=fails, viol=viol)
    if extended:
        true_by_gid = {g.gid: g for g in goods}
        true_by_gid.update({g.gid: g for g in all_inbound})
        final_placed = [
            (true_by_gid[gid], pos) for gid, pos in pos_of.items()
            if gid in true_by_gid
        ]
        final_layout = ws.metrics(wh, final_placed, [])
        result.update(
            status=("FEASIBLE" if fails == 0 and viol == 0 else "INFEASIBLE"),
            initial_fails=0,
            initial_placed=len(goods),
            scheduled_cycles=len(records),
            valid_cycles=planned_dispatch_count,
            rejected_cycles=planned_rejected_count,
            processed_scheduled_cycles=processed_scheduled_cycles,
            processed_valid_cycles=dispatch_count,
            processed_rejected_cycles=rejected_count,
            completed_cycles=len(retr_t),
            unprocessed_cycles=len(records) - processed_scheduled_cycles,
            terminal_failure_cycle=terminal_failure_cycle,
            terminal_failure_stage=terminal_failure_stage,
            failure_policy="TERMINATE_NO_FALLBACK",
            response_sample_n=n,
            dual_time_sample_n=len(retr_t),
            util_sample_n=len(retr_t),
            productive_busy_s=productive_busy_acc,
            fault_clock_mode="productive_busy_time_v1",
            reject_service_s=(workload.get("reject_service_s", 0)
                              if workload is not None else 0),
            router=decision,
            picked_strategy=picked,
            strategy_switches=0,
            advisory_count=sum(item.get("advisory") is not None for item in records),
            makespan_s=makespan,
            drain_time_s=(max(0.0, makespan - arrivals[-1]) if arrivals else 0.0),
            final_layout_exp_t=final_layout["exp_t"],
            final_energy_kgm=final_layout["energy"],
            final_heavy_tier=final_layout["heavy_tier"],
            final_cog_m=final_layout["cog"],
            stream_hashes=shared_hashes,
        )
    return result


def tier12(tier, goods, new_goods, requests, cycles):
    """档1/档2:直接复用 mixed_ops.run_mixed(与 F8 数字同源)。"""
    w_max = max(g.weight for g in goods)
    f_max = max(g.freq for g in goods)
    ws.ACCEL = (tier == 2)
    if tier == 2:
        d_on, bg_on = ws.lookup_weights(N_INIT, "skew", "online")
        d_ba, bg_ba = ws.lookup_weights(N_INIT, "skew", "batch")
        fn = ws.make_score_fn(1.0, bg_on / 2, bg_on / 2, d_on, w_max, f_max)
        fnb = ws.make_score_fn(1.0, bg_ba / 2, bg_ba / 2, d_ba, w_max, f_max)
    else:
        fn = ws.make_score_fn(1.0, 0.6, 0.4, 0.15, w_max, f_max)
        fnb = fn
    out = {}
    for s in STRATS:
        m = run_mixed(s, goods, new_goods, requests, fn, w_max, f_max, fnb)
        out[s] = dict(tot_dual=m["tot_dual"], avg_retr=m["avg_retr"],
                      busy_total=m["tot_dual"], resp_p50=None, resp_p95=None,
                      util=None, n_down=0, downtime=0.0,
                      fails=m["fails"], viol=m["viol"])
    return out


def tier3(goods, new_goods, requests, cycles):
    w_max = max(g.weight for g in goods)
    f_max = max(g.freq for g in goods)
    ws.ACCEL = True                                       # 档3 = 档2 物理口径之上叠拟真
    d_on, bg_on = ws.lookup_weights(N_INIT, "skew", "online")
    d_ba, bg_ba = ws.lookup_weights(N_INIT, "skew", "batch")
    fn = ws.make_score_fn(1.0, bg_on / 2, bg_on / 2, d_on, w_max, f_max)
    fnb = ws.make_score_fn(1.0, bg_ba / 2, bg_ba / 2, d_ba, w_max, f_max)
    arrivals, reference_pair_s = common_arrivals(
        goods, new_goods, requests, fn, w_max, f_max, fnb, cycles=cycles, seed=SEED)
    out = {s: run_tier3(s, goods, new_goods, requests, fn, w_max, f_max, fnb,
                        arrivals=arrivals, cycles=cycles)
           for s in STRATS}
    return out, dict(arrival_reference_strategy="seq",
                     arrival_reference_pair_s=reference_pair_s,
                     common_arrivals=1)


def main():
    global HANDLE_S
    ap = argparse.ArgumentParser()
    ap.add_argument("--cycles", type=int, default=100)
    ap.add_argument("--quick", action="store_true", help="30 周期快速自检")
    ap.add_argument("--handle", type=float, default=None,
                    help="覆盖装卸时间 s/次(canonical G1;敏感性扫描用,如 10/15/20)")
    a = ap.parse_args()
    if a.handle is not None:
        HANDLE_S = a.handle
    cycles = 30 if a.quick else a.cycles

    goods = ws.gen_goods(N_INIT, SEED)
    new_goods, requests = build_workload(goods, cycles, SEED)

    print(f"L7 拟真度阶梯:{cycles} 周期混合流,seed={SEED}")
    print(f"档3 sim参数(G1推导+扫描；G2-G4显式情景假设,非现场标定):装卸 {HANDLE_S}s/次,ρ峰谷 "
          f"{RHO_PEAK}/{RHO_OFF},频次噪声 σ={FREQ_SIGMA},MTBF/MTTR "
          f"{MTBF_S:.0f}/{MTTR_S:.0f}s")
    tier3_out, arrival_meta = tier3(goods, new_goods, requests, cycles)
    tiers = {1: tier12(1, goods, new_goods, requests, cycles),
             2: tier12(2, goods, new_goods, requests, cycles),
             3: tier3_out}
    TNAME = {1: "档1 数据模型", 2: "档2 sim H设计", 3: "档3 综合sim情景"}

    for t in (1, 2, 3):
        print(f"\n—— {TNAME[t]} ——")
        hdr = f"{'策略':<14}{'出库均时s':>9}{'行程总时s':>10}{'违规':>5}"
        if t == 3:
            hdr += f"{'响应P50s':>9}{'响应P95s':>9}{'利用率':>7}{'故障':>5}"
        print(hdr)
        for s in STRATS:
            m = tiers[t][s]
            line = f"{LBL[s]:<14}{m['avg_retr']:>9.2f}{m['tot_dual']:>10.0f}{m['viol']:>5}"
            if t == 3:
                line += (f"{m['resp_p50']:>9.0f}{m['resp_p95']:>9.0f}"
                         f"{m['util']:>7.2f}{m['n_down']:>5}")
            print(line)
        d = (1 - tiers[t]["awra"]["avg_retr"] / tiers[t]["seq"]["avg_retr"]) * 100
        print(f"  awra vs seq 出库均时降幅:{d:.1f}%")

    # 阶梯核心句
    drops = {t: (1 - tiers[t]["awra"]["avg_retr"] / tiers[t]["seq"]["avg_retr"]) * 100
             for t in (1, 2, 3)}
    order_keep = all(
        tiers[t]["awra"]["avg_retr"] < tiers[t]["score"]["avg_retr"]
        < tiers[t]["seq"]["avg_retr"] for t in (1, 2, 3))
    print(f"\n★阶梯结论:awra 较 seq 出库均时降幅 档1 {drops[1]:.1f}% → 档2 "
          f"{drops[2]:.1f}% → 档3 {drops[3]:.1f}%;"
          f"AWRA/score/seq行程均值偏序三档{'保持' if order_keep else '变化'}；响应P50/P95另判;"
          f"违规合计 {sum(tiers[t][s]['viol'] for t in tiers for s in STRATS)}")

    # ---- CSV ----
    os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
    path = os.path.join(HERE, "out", "realism_matrix_data.csv")
    with open(path, "w", newline="", encoding="utf-8-sig") as fp:
        w = csv.writer(fp)
        w.writerow(["tier", "strategy", "avg_retrieve_s", "travel_dual_s",
                    "busy_total_s", "resp_p50_s", "resp_p95_s", "util",
                    "n_down", "downtime_s", "fails", "viol"])
        for t in (1, 2, 3):
            for s in STRATS:
                m = tiers[t][s]
                w.writerow([t, s, round(m["avg_retr"], 3), round(m["tot_dual"], 1),
                            round(m["busy_total"], 1),
                            "" if m["resp_p50"] is None else round(m["resp_p50"], 1),
                            "" if m["resp_p95"] is None else round(m["resp_p95"], 1),
                            "" if m["util"] is None else round(m["util"], 3),
                            m["n_down"], round(m["downtime"], 1),
                            m["fails"], m["viol"]])
    param_path = os.path.join(HERE, "out", "realism_matrix_params.csv")
    with open(param_path, "w", newline="", encoding="utf-8-sig") as fp:
        w = csv.writer(fp)
        w.writerow(["param", "value", "note"])
        for k, v, note in [
            ("handle_s", HANDLE_S, "G1推导中值；10/15/20s扫描；非现场实测"),
            ("rho_peak", RHO_PEAK, "G2显式情景假设；非现场标定"),
            ("rho_off", RHO_OFF, "G2显式情景假设；非现场标定"),
            ("freq_sigma", FREQ_SIGMA, "G3显式情景假设；非现场标定"),
            ("mtbf_s", MTBF_S, "G4显式情景假设；非现场标定"),
            ("mttr_s", MTTR_S, "G4显式情景假设；非现场标定"),
            ("arrival_reference_strategy", arrival_meta["arrival_reference_strategy"],
             "所有策略共享同一外生到达流"),
            ("arrival_reference_pair_s", round(arrival_meta["arrival_reference_pair_s"], 6),
             "seq reference 的纯行程均值+两次装卸"),
            ("common_arrivals", arrival_meta["common_arrivals"], "1=CRN 共同到达流"),
            ("cycles", cycles, ""), ("seed", SEED, "")]:
            w.writerow([k, v, note])

    # ---- fig16 ----
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, (axL, axR) = plt.subplots(1, 2, figsize=(12.5, 4.4))
    colors = {"seq": "#8d6e63", "near": "#1976d2", "score": "#f9a825",
              "awra": "#2e7d32"}
    xs = [1, 2, 3]
    for s in STRATS:
        ys = [tiers[t][s]["avg_retr"] for t in xs]
        axL.plot(xs, ys, "o-", color=colors[s], label=LBL[s], linewidth=2)
    for t in xs:
        axL.text(t, tiers[t]["awra"]["avg_retr"] - 0.35,
                 f"-{drops[t]:.0f}%", ha="center", fontsize=9, color="#2e7d32")
    axL.set_xticks(xs)
    axL.set_xticklabels([TNAME[t] for t in xs], fontsize=9)
    axL.set_ylabel("出库均时 s(纯行程口径,跨档可比)")
    axL.set_title("三档sim下的布局质量:AWRA相对seq行程方向保持")
    axL.legend(fontsize=8)
    axL.spines[["top", "right"]].set_visible(False)

    w_ = 0.36
    x3 = range(len(STRATS))
    p50 = [tiers[3][s]["resp_p50"] for s in STRATS]
    p95 = [tiers[3][s]["resp_p95"] for s in STRATS]
    axR.bar([i - w_ / 2 for i in x3], p50, w_, color="#90a4ae", label="响应 P50")
    axR.bar([i + w_ / 2 for i in x3], p95, w_, color="#c62828", label="响应 P95")
    axR.set_xticks(list(x3))
    axR.set_xticklabels([LBL[s] for s in STRATS], fontsize=8)
    axR.set_ylabel("任务响应时间 s(到达→完成,含排队/装卸/故障)")
    axR.set_title(f"档3 工业视角:响应分位与可用性(故障注入 "
                  f"{tiers[3]['awra']['n_down']} 次示例)")
    axR.legend(fontsize=9)
    axR.spines[["top", "right"]].set_visible(False)
    fig.suptitle(f"L7 拟真度阶梯({cycles}周期混合流,seed={SEED};"
                 f"档3参数为显式情景假设,共同到达流)", fontsize=12)
    fig.tight_layout()
    os.makedirs(os.path.join(HERE, "figs"), exist_ok=True)
    fig.savefig(os.path.join(HERE, "figs", "fig16_拟真度阶梯.png"), dpi=300)
    print(f"输出:{path} + {param_path} + figs/fig16_拟真度阶梯.png")


if __name__ == "__main__":
    main()
