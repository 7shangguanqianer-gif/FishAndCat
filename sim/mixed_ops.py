# -*- coding: utf-8 -*-
"""
mixed_ops.py — L2 存取混合作业流仿真:补齐题面"存取效率(单位时间存取量)"的"取"半边
模型(canonical B6/C9/C10):
  初始:某策略完成 120 件入库(布局=该策略的产出);
  混合流:M 个周期,每周期 = 1 件新货入库 + 1 件在库货出库(出库请求按访问频次
  加权无放回抽样,池随入库演化;请求序列只依赖货物身份,对所有策略完全相同);
  单命令口径:两趟独立往返  T = 2·t(存位) + 2·t(取位)
  双命令口径:一趟联合行程  T = t(存位) + t(存位→取位) + t(取位)
             (存完顺路去取,省一次空驶回程——AS/RS 标准 dual command cycle)
  节省 = t(存)+t(取)−t(存→取) ≥ 0(切比雪夫满足三角不等式)。
指标:混合流总时间(两口径)、双命令节省%、吞吐(存取次数/小时,C9)、违规。
布局的价值在出库侧兑现:高频货放得近 → 抽中的取货行程短——这是"访问频次"闭环。
运行:python mixed_ops.py [--cycles 100] [--accel]
输出:out/mixed_ops.csv + figs/fig8_混合作业.png
"""
import argparse
import csv
import hashlib
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import warehouse_sim as ws
import cargo_scenarios as cs
import strategy_lib as sl

HERE = os.path.dirname(os.path.abspath(__file__))
SEED, N_INIT, RULE = 2026, 120, "sum"
STRATS = ["seq", "near", "score", "awra"]
DYNAMIC_STRATS = ["random", "seq", "near", "score", "awra", "cb", "tob"]
LBL = {"seq": "顺序基线", "near": "就近贪心", "score": "多目标评分(在线)",
       "awra": "AWRA-LS(批量)"}


def build_workload(init_goods, n_cycles, seed):
    """生成与策略无关的混合作业负载:
    新货序列(gen_goods 派生 seed)+ 出库请求序列(按频次加权无放回,池随入库演化)。
    只用货物身份,不看仓位 → 所有策略面对完全相同的负载(公平口径)。"""
    new_goods = ws.gen_goods(n_cycles, seed + 7)
    for i, g in enumerate(new_goods):               # 避免 gid 冲突:偏移编号
        g.gid = 1000 + i + 1
        g.name = f"N{i+1:03d}"
    rng = random.Random(seed + 13)
    pool = list(init_goods)
    requests = []                                    # 每周期出库的货物对象
    for k in range(n_cycles):
        weights = [g.freq for g in pool]
        g_out = rng.choices(pool, weights=weights, k=1)[0]
        pool.remove(g_out)
        requests.append(g_out)
        pool.append(new_goods[k])                    # 该周期新货入池,后续可能被取
    return new_goods, requests


def _canonical_hash(value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True,
                     separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _good_payload(good):
    return dict(gid=good.gid, name=good.name, weight=good.weight,
                freq=good.freq, volume=good.vol)


def _pool_order_hash(pool):
    """Hash the ordered identity/weight vector actually consumed by random.choices."""
    return _canonical_hash([(g.gid, g.freq) for g in pool])


def _registered_scenario_id(scenario):
    """Recover the registry key without adding a duplicated mutable id field."""
    for sid, registered in cs.load_registry()["scenarios"].items():
        if scenario == registered:
            return sid
    return scenario.get("scenario_id", "CUSTOM")


def _inbound_profile_label(scenario, cycle):
    generator = scenario["inbound_goods_generator"]
    if generator["type"] != "segmented_cases":
        return scenario["profile"]
    for segment in generator["segments"]:
        if segment["start_cycle"] <= cycle <= segment["end_cycle"]:
            return segment["case"]
    raise ValueError(f"cycle {cycle} is outside the registered inbound segments")


def build_scenario_workload(initial_goods, inbound_goods, scenario, seed):
    """Build a registered, strategy-independent dynamic workload.

    The function consumes cargo identity/frequency only.  It never receives a
    warehouse layout, so request sampling cannot accidentally depend on slot
    positions.  Legal cycles keep the legacy order (pick outbound from current
    pool, remove it, then add inbound).  Illegal inbound is rejected at the
    gate and consumes neither a request RNG draw nor a dispatch cycle.
    """
    scheduled = int(scenario["scheduled_cycles"])
    if len(inbound_goods) != scheduled:
        raise ValueError(
            f"registered workload requires {scheduled} inbound cycles, got {len(inbound_goods)}"
        )
    if not initial_goods or any(not cs.is_legal_cargo(g) for g in initial_goods):
        raise ValueError("initial inventory must be non-empty and entrance-legal")
    all_gids = [g.gid for g in initial_goods] + [g.gid for g in inbound_goods]
    if len(all_gids) != len(set(all_gids)):
        raise ValueError("initial and inbound gid sets must be globally unique")

    policy = scenario["request_pool_policy"]
    if (policy.get("type") != "weighted_current_legal_inventory"
            or policy.get("weight") != "freq"
            or policy.get("position_blind") is not True):
        raise ValueError(f"unsupported request pool policy: {policy!r}")
    rng = random.Random(int(seed) + int(policy["seed_offset"]))
    pool = list(initial_goods)
    cycles = []
    valid_inbound = []
    requests = []
    dispatch_mask = []
    advisories = []
    advisory_cycles = set(scenario.get("router_contract", {}).get("advisory_cycles", []))

    for cycle, good_in in enumerate(inbound_goods):
        before_count = len(pool)
        before_hash = _pool_order_hash(pool)
        advisory = None
        if cycle in advisory_cycles:
            profile = cs.scenario_profile(pool)
            advisory = {
                "cycle": cycle,
                "profile": profile,
                "objective": "lexicographic",
                "recommended_strategy": sl.select_strategy(
                    profile, batch_known=True, objective="lexicographic"
                ),
                "advisory_only": True,
                "applied": False,
                "existing_inventory_relayout": False,
            }
            advisories.append(advisory)

        legal = cs.is_legal_cargo(good_in)
        good_out = None
        if legal:
            weights = [g.freq for g in pool]
            if not weights or sum(weights) <= 0.0:
                raise ValueError("request pool must have positive total frequency")
            good_out = rng.choices(pool, weights=weights, k=1)[0]
            pool.remove(good_out)
            pool.append(good_in)
            valid_inbound.append(good_in)
            requests.append(good_out)
            status = "PAIRED_IN_OUT"
            dispatch = True
        else:
            status = "REJECT_NO_DISPATCH"
            dispatch = False

        dispatch_mask.append(dispatch)
        cycles.append({
            "cycle": cycle,
            "status": status,
            "dispatch": dispatch,
            "inbound_profile": _inbound_profile_label(scenario, cycle),
            "inbound_good": good_in,
            "outbound_good": good_out,
            "inbound_gid": good_in.gid,
            "outbound_gid": good_out.gid if good_out is not None else None,
            "inventory_before": before_count,
            "inventory_after": len(pool),
            "pool_order_hash_before": before_hash,
            "pool_order_hash_after": _pool_order_hash(pool),
            "advisory": advisory,
        })

    rejected = len(cycles) - len(valid_inbound)
    invalid_policy = scenario["invalid_inbound_policy"]
    expected_rejected = int(invalid_policy["expected_count"])
    if rejected != expected_rejected:
        raise ValueError(
            f"invalid-inbound contract mismatch: expected {expected_rejected}, got {rejected}"
        )
    if len(pool) != len(initial_goods):
        raise AssertionError("paired workload did not conserve legal inventory count")

    scenario_id = _registered_scenario_id(scenario)
    cycle_payload = []
    for item in cycles:
        cycle_payload.append({
            "cycle": item["cycle"],
            "status": item["status"],
            "dispatch": item["dispatch"],
            "inbound_profile": item["inbound_profile"],
            "inbound": _good_payload(item["inbound_good"]),
            "outbound_gid": item["outbound_gid"],
            "inventory_before": item["inventory_before"],
            "inventory_after": item["inventory_after"],
            "pool_order_hash_before": item["pool_order_hash_before"],
            "pool_order_hash_after": item["pool_order_hash_after"],
            "advisory": item["advisory"],
        })
    inbound_payload = [_good_payload(g) for g in inbound_goods]
    request_payload = [item["outbound_gid"] for item in cycles]
    workload_payload = {
        "schema_version": "scenario_workload_v1",
        "scenario_id": scenario_id,
        "seed": int(seed),
        "request_pool_policy": policy,
        "invalid_inbound_policy": invalid_policy,
        "initial_goods": [_good_payload(g) for g in initial_goods],
        "cycles": cycle_payload,
    }
    return {
        "schema_version": "scenario_workload_v1",
        "scenario_id": scenario_id,
        "seed": int(seed),
        "scheduled_cycles": scheduled,
        "valid_cycles": len(valid_inbound),
        "rejected_cycles": rejected,
        "response_sample_n": len(valid_inbound),
        "reject_service_s": invalid_policy.get("reject_service_s", 0),
        "cycles": cycles,
        "valid_inbound_goods": valid_inbound,
        "requests": requests,
        "dispatch_mask": dispatch_mask,
        "advisories": advisories,
        "final_pool_gids": [g.gid for g in pool],
        "final_inventory_count": len(pool),
        "inbound_stream_hash": _canonical_hash(inbound_payload),
        "request_stream_hash": _canonical_hash(request_payload),
        "workload_hash": _canonical_hash(workload_payload),
    }


def resolve_strategy_mode(mode, goods, batch_known=True, objective="lexicographic"):
    """Resolve a manual mode or AUTO exactly once from the true initial batch."""
    normalized = str(mode).lower()
    profile = sl.batch_profile(goods)
    if normalized == "auto":
        return sl.explain_selection(profile, batch_known, objective)
    if normalized not in sl.STRATEGY_CHAINS:
        raise ValueError(f"unknown strategy mode: {mode}")
    chain = sl.STRATEGY_CHAINS[normalized]
    return {
        "router_version": "manual_override_v1",
        "profile": profile,
        "batch_known": bool(batch_known),
        "objective": objective,
        "picked": normalized,
        "alt": None,
        "reason_code": "MANUAL_OVERRIDE",
        "reason": "人工固定策略；AUTO 路由未接管",
        "reason_basis": "manual_override",
        "thresholds": dict(sl.ROUTER_THRESHOLDS),
        "initial_strategy": chain["initial"],
        "online_strategy": chain["online"],
        "selection_scope": "fixed_manual",
        "weight_aware": False,
        "display_only_features": ["w_mean", "w_heavy"],
    }


def online_strategy_callable(strat_name, seed=SEED):
    online_name = sl.STRATEGY_CHAINS[strat_name]["online"]
    if online_name == "random":
        return ws.strat_random(random.Random(seed + 301))
    return {"seq": ws.strat_seq, "near": ws.strat_near,
            "score": ws.strat_score}[online_name]


def initial_layout(strat_name, goods, fn, w_max, f_max, seed=SEED,
                   return_failed=False):
    """Execute the registered initial-stage algorithm without hidden relayout."""
    if strat_name == "awra":
        wh, placed, failed = ws.run_awra_ls(goods, RULE, fn, w_max, f_max)
    elif strat_name == "cb":
        wh, placed, failed = sl.run_class_based(goods, RULE)
    elif strat_name == "tob":
        wh, placed, failed = sl.run_full_turnover(goods, RULE)
    elif strat_name == "random":
        wh, placed, failed = ws.run_online(
            ws.strat_random(random.Random(seed + 1)), goods, RULE, fn
        )
    else:
        strat = {"seq": ws.strat_seq, "near": ws.strat_near,
                 "score": ws.strat_score}[strat_name]
        wh, placed, failed = ws.run_online(strat, goods, RULE, fn)
    positions = {g.gid: pos for g, pos in placed}
    if return_failed:
        return wh, positions, failed
    assert not failed, strat_name
    return wh, positions


def run_mixed(strat_name, goods, new_goods, requests, fn, w_max, f_max,
              fn_batch=None, seed=SEED, batch_known=True,
              objective="lexicographic"):
    """跑混合流:入库决策用该策略的在线形式(awra 布局的后续入库用 score 在线,
    因为混合流是逐件到达场景——批量重排不适用于单件即时决策,如实声明)。
    fn_batch:awra 初始布局用的评分(H 口径下批量/在线权重不同,A1);缺省=fn。"""
    decision = resolve_strategy_mode(strat_name, goods, batch_known, objective)
    picked = decision["picked"]
    wh, pos_of = initial_layout(
        picked, goods, fn_batch or fn, w_max, f_max, seed=seed
    )
    online = online_strategy_callable(picked, seed)
    tot_single = tot_dual = 0.0
    retr_t = []
    fails = viol = 0
    for g_in, g_out in zip(new_goods, requests):
        s_out = pos_of.pop(g_out.gid)
        s_in = online(wh, g_in, fn)
        if s_in is None:                             # 边界:无可行位(混合流不应发生)
            fails += 1
            t_out = ws.travel_time(*s_out)
            tot_single += 2 * t_out
            tot_dual += 2 * t_out
            wh.remove(s_out[0], s_out[1])
            continue
        if g_in.weight > ws.tier_cap(s_in[1]) or g_in.vol > ws.CELL_VOL:
            viol += 1
        t_in = ws.travel_time(*s_in)
        t_out = ws.travel_time(*s_out)
        t_link = ws.travel_time_between(s_in[0], s_in[1], s_out[0], s_out[1])
        tot_single += 2 * t_in + 2 * t_out
        tot_dual += t_in + t_link + t_out
        retr_t.append(t_out)
        wh.put(s_in[0], s_in[1], g_in)
        pos_of[g_in.gid] = s_in
        wh.remove(s_out[0], s_out[1])
    n_ops = 2 * len(new_goods)                       # 每周期=1存+1取
    return dict(tot_single=tot_single, tot_dual=tot_dual,
                saving=(1 - tot_dual / tot_single) * 100 if tot_single else 0.0,
                thr_single=n_ops / (tot_single / 3600) if tot_single else 0.0,
                thr_dual=n_ops / (tot_dual / 3600) if tot_dual else 0.0,
                avg_retr=sum(retr_t) / len(retr_t) if retr_t else 0.0,
                fails=fails, viol=viol)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cycles", type=int, default=100, help="混合周期数(默认100)")
    ap.add_argument("--accel", action="store_true", help="用 L1 加减速口径")
    ap.add_argument("--adaptive", action="store_true",
                    help="A1 sim场景权重设计表(H设计口径；非PLC闭环)")
    a = ap.parse_args()
    if a.accel:
        ws.ACCEL = True

    goods = ws.gen_goods(N_INIT, SEED)
    w_max = max(g.weight for g in goods)
    f_max = max(g.freq for g in goods)
    if a.adaptive:
        d_on, bg_on = ws.lookup_weights(N_INIT, "skew", "online")
        d_ba, bg_ba = ws.lookup_weights(N_INIT, "skew", "batch")
        fn = ws.make_score_fn(1.0, bg_on / 2, bg_on / 2, d_on, w_max, f_max)
        fn_batch = ws.make_score_fn(1.0, bg_ba / 2, bg_ba / 2, d_ba, w_max, f_max)
    else:
        fn = ws.make_score_fn(1.0, 0.6, 0.4, 0.15, w_max, f_max)
        fn_batch = fn
    new_goods, requests = build_workload(goods, a.cycles, SEED)

    motion = ("梯形加减速" if ws.ACCEL else "匀速") + ("+自适应权重" if a.adaptive else "+固定权重")
    print(f"混合作业流:{a.cycles} 周期(每周期1存+1取,共{2*a.cycles}次作业),"
          f"口径={motion},seed={SEED}")
    print(f"{'策略':<16}{'单命令总时(s)':>13}{'双命令总时(s)':>13}{'节省':>7}"
          f"{'双命令模式单操作/h':>19}{'出库均时(s)':>11}{'失败':>5}{'违规':>5}")
    rows = []
    for s in STRATS:
        m = run_mixed(s, goods, new_goods, requests, fn, w_max, f_max, fn_batch)
        rows.append((s, m))
        print(f"{LBL[s]:<16}{m['tot_single']:>13.0f}{m['tot_dual']:>13.0f}"
              f"{m['saving']:>6.1f}%{m['thr_dual']:>15.0f}{m['avg_retr']:>11.2f}"
              f"{m['fails']:>5}{m['viol']:>5}")

    base = dict(rows)["seq"]
    best = dict(rows)["awra"]
    print(f"\nawra 布局 vs seq 布局(双命令口径):混合流总时 "
          f"{base['tot_dual']:.0f}→{best['tot_dual']:.0f}s"
          f"(降 {(1-best['tot_dual']/base['tot_dual'])*100:.1f}%),"
          f"单操作吞吐 {base['thr_dual']:.0f}→{best['thr_dual']:.0f} 次/h"
          f"(awra约{best['thr_dual']/2:.1f}双周期/h)"
          f"(提 {(best['thr_dual']/base['thr_dual']-1)*100:.1f}%)")
    print(f"双命令 vs 单命令(awra 布局):节省 {best['saving']:.1f}% —— 存取联程省空驶")

    # ---- CSV ----
    os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
    path = os.path.join(HERE, "out", "mixed_ops.csv")
    with open(path, "w", newline="", encoding="utf-8-sig") as fp:
        w = csv.writer(fp)
        w.writerow(["strategy", "motion", "weights", "cycles", "tot_single_s", "tot_dual_s",
                    "saving_pct", "throughput_single_command_ops_h",
                    "throughput_dual_command_ops_h",
                    "avg_retrieve_s", "fails", "viol"])
        for s, m in rows:
            w.writerow([s, "trapezoid" if ws.ACCEL else "uniform",
                        "adaptive" if a.adaptive else "fixed", a.cycles,
                        round(m["tot_single"], 1), round(m["tot_dual"], 1),
                        round(m["saving"], 2), round(m["thr_single"], 1),
                        round(m["thr_dual"], 1), round(m["avg_retr"], 3),
                        m["fails"], m["viol"]])

    # ---- fig8 ----
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, (axL, axR) = plt.subplots(1, 2, figsize=(12, 4.2))
    x = range(len(STRATS))
    w_ = 0.36
    axL.bar([i - w_ / 2 for i in x], [dict(rows)[s]["tot_single"] for s in STRATS],
            w_, color="#90a4ae", label="单命令(两趟独立往返)")
    axL.bar([i + w_ / 2 for i in x], [dict(rows)[s]["tot_dual"] for s in STRATS],
            w_, color="#2e7d32", label="双命令(存取联程)")
    for i, s in enumerate(STRATS):
        m = dict(rows)[s]
        axL.text(i + w_ / 2, m["tot_dual"], f"-{m['saving']:.0f}%",
                 ha="center", va="bottom", fontsize=9, color="#2e7d32")
    axL.set_xticks(list(x))
    axL.set_xticklabels([LBL[s] for s in STRATS], fontsize=8)
    axL.set_ylabel(f"{a.cycles}周期混合流总时间 (s)")
    axL.set_title("单命令 vs 双命令周期")
    axL.legend(fontsize=9)
    axL.spines[["top", "right"]].set_visible(False)
    thr = [dict(rows)[s]["thr_dual"] for s in STRATS]
    bars = axR.bar(x, thr, color=["#8d6e63", "#1976d2", "#f9a825", "#2e7d32"])
    for b, v in zip(bars, thr):
        axR.text(b.get_x() + b.get_width() / 2, v, f"{v:.0f}", ha="center",
                 va="bottom", fontsize=9)
    axR.set_xticks(list(x))
    axR.set_xticklabels([LBL[s] for s in STRATS], fontsize=8)
    axR.set_ylabel("双命令模式吞吐(单操作/小时)")
    axR.set_title("单位时间存取量(题面指标)——布局质量在出库侧兑现")
    axR.spines[["top", "right"]].set_visible(False)
    fig.suptitle(f"L2 存取混合作业流({a.cycles}周期,{motion}口径,seed={SEED})", fontsize=12)
    fig.tight_layout()
    os.makedirs(os.path.join(HERE, "figs"), exist_ok=True)
    fig.savefig(os.path.join(HERE, "figs", "fig8_混合作业.png"), dpi=300)
    print(f"输出:{path} + figs/fig8_混合作业.png")


if __name__ == "__main__":
    main()
