"""S3 评分修订 what-if 离线跑批(方案6,0717 用户批准"证据先行";docs/存取算法与呈现改进方案_0717.md)。

两个修订假设(只在本进程内 monkeypatch,不落盘改 fill_only/warehouse_sim 生产定义):
  V1 tau      —— 位置保留项距离饱和:resv=(1-f_norm)*(1-min(t_norm,tau)/tau),tau=0.5。
                 冷门货"推到中远即止",不再区分中远与最远角(修首件送最远角的观感过激)。
  V2 dynfmax  —— f_max 动态化:f_norm=freq/max(批次实际 freq),替代常数 100。
                 修 skew 情景 f_norm 塌缩(max freq≈28 → f_norm≤0.28)导致的效率项失活。
  V3 both     —— 两者叠加。
V0 baseline = 现行生产定义(同时跑 SEQ/NEAR 作对照与守恒核查)。

每 (case, seed) 完整复用 fill_only.build_shared_input / run_online_lane;SEQ/NEAR 与评分
无关只跑一次。输出四取货/分布指标 + 守恒量核查 + 首件落位(直接回应"首件为何送最远角")。

用法(项目根):
    PYTHONIOENCODING=utf-8 python sim/score_whatif_sweep.py --seeds 30
    python sim/score_whatif_sweep.py --seeds 2 --smoke   # 冒烟,不落证据
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fill_only  # noqa: E402
import warehouse_sim as ws  # noqa: E402

METRIC_KEYS = (
    "expected_retrieval_s", "hot20_retrieval_s", "heavy20_mean_tier",
    "lift_work_proxy_kgm", "makespan_s", "round_trip_path_m",
)
VARIANTS = ("baseline", "tau", "dynfmax", "both")
SCHEMA = "s3-score-whatif-sweep-v1"
_ORIG_SCORE_TERMS = fill_only._score_terms
_ORIG_MAKE_SCORE_FN = ws.make_score_fn


def _variant_score_terms(kind: str, tau: float, f_dyn: float):
    """生成 _score_terms 变体:与生产实现逐项同构,仅改 f_max 分母与保留项距离饱和两点。"""
    def score_terms(good, col, tier, shared):
        alpha, beta, gamma, delta = shared["score_policy"]["weights"]
        normal = shared["score_policy"]["normalization"]
        f_max = f_dyn if kind in ("dynfmax", "both") else normal["f_max"]
        t_norm = ws.travel_time(col, tier) / normal["t_max_s"]
        f_norm = good.freq / f_max
        w_norm = good.weight / normal["w_max"]
        eff_raw = f_norm * t_norm
        stability_raw = w_norm * (tier / (ws.TIERS - 1))
        energy_raw = (good.weight * tier * ws.CELL_H) / (normal["w_max"] * ws.H_MAX)
        g_t = min(t_norm, tau) / tau if kind in ("tau", "both") else t_norm
        reservation_raw = (1.0 - f_norm) * (1.0 - g_t)
        components = {
            "efficiency": alpha * eff_raw,
            "stability": beta * stability_raw,
            "energy_proxy": gamma * energy_raw,
            "position_reservation": delta * reservation_raw,
        }
        rnd = fill_only._round
        return {
            "t_norm": rnd(t_norm), "f_norm": rnd(f_norm), "w_norm": rnd(w_norm),
            "efficiency_raw": rnd(eff_raw), "stability_raw": rnd(stability_raw),
            "energy_proxy_raw": rnd(energy_raw),
            "position_reservation_raw": rnd(reservation_raw),
            "efficiency_weighted": rnd(components["efficiency"]),
            "stability_weighted": rnd(components["stability"]),
            "energy_proxy_weighted": rnd(components["energy_proxy"]),
            "position_reservation_weighted": rnd(components["position_reservation"]),
            "score_total": rnd(sum(components.values())),
        }
    return score_terms


def _variant_make_score_fn(kind: str, tau: float, f_dyn: float):
    def factory(alpha, beta, gamma, delta, w_max, f_max):
        f_eff = f_dyn if kind in ("dynfmax", "both") else f_max
        tmax = ws.t_max_now()
        def score(good, col, tier):
            t_norm = ws.travel_time(col, tier) / tmax
            f_norm = good.freq / f_eff
            eff = f_norm * t_norm
            stab = (good.weight / w_max) * (tier / (ws.TIERS - 1))
            energy = (good.weight * tier * ws.CELL_H) / (w_max * ws.H_MAX)
            g_t = min(t_norm, tau) / tau if kind in ("tau", "both") else t_norm
            resv = (1.0 - f_norm) * (1.0 - g_t)
            return alpha * eff + beta * stab + gamma * energy + delta * resv
        return score
    return factory


@contextmanager
def patched(kind: str, tau: float, f_dyn: float):
    if kind == "baseline":
        yield
        return
    fill_only._score_terms = _variant_score_terms(kind, tau, f_dyn)
    ws.make_score_fn = _variant_make_score_fn(kind, tau, f_dyn)
    try:
        yield
    finally:
        fill_only._score_terms = _ORIG_SCORE_TERMS
        ws.make_score_fn = _ORIG_MAKE_SCORE_FN


def lane_digest(lane: Dict[str, Any]) -> Dict[str, Any]:
    digest = {key: lane["metrics"][key] for key in METRIC_KEYS}
    digest["violations"] = lane["metrics"]["violations"]
    digest["first_slot"] = lane["events"][0]["decision"]["selected_slot"]
    return digest


def run_case(case: str, seeds: List[int], tau: float) -> Dict[str, Any]:
    rows = []
    for seed in seeds:
        shared = fill_only.build_shared_input(seed=seed, case=case)
        f_dyn = max(float(item["freq"]) for item in shared["cargo_catalog"])
        row: Dict[str, Any] = {"seed": seed, "f_dyn": round(f_dyn, 6), "lanes": {}}
        for algorithm in ("seq", "near"):
            lane = fill_only.run_online_lane(shared, algorithm)
            if lane["status"] != "FEASIBLE":
                raise RuntimeError(f"seed={seed} {algorithm} INFEASIBLE")
            row["lanes"][algorithm] = lane_digest(lane)
        for kind in VARIANTS:
            with patched(kind, tau, f_dyn):
                lane = fill_only.run_online_lane(shared, "score")
            if lane["status"] != "FEASIBLE":
                raise RuntimeError(f"seed={seed} score[{kind}] INFEASIBLE")
            row["lanes"][f"score_{kind}"] = lane_digest(lane)
        rows.append(row)
        print(f"  seed {seed} done", flush=True)
    return {"case": case, "rows": rows, "summary": summarize(rows)}


def summarize(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    lanes = ["seq", "near"] + [f"score_{kind}" for kind in VARIANTS]
    summary: Dict[str, Any] = {"per_metric": {}, "first_slot": {}, "conserved": {}, "pairwise_vs_baseline": {}}
    for key in METRIC_KEYS:
        summary["per_metric"][key] = {
            lane: {
                "mean": round(statistics.fmean([row["lanes"][lane][key] for row in rows]), 6),
                "stdev": round(statistics.stdev([row["lanes"][lane][key] for row in rows]), 6)
                if len(rows) > 1 else 0.0,
            } for lane in lanes
        }
    for key in ("expected_retrieval_s", "hot20_retrieval_s", "heavy20_mean_tier", "lift_work_proxy_kgm"):
        summary["pairwise_vs_baseline"][key] = {
            f"score_{kind}": sum(
                1 for row in rows
                if row["lanes"][f"score_{kind}"][key] < row["lanes"]["score_baseline"][key]
            ) for kind in VARIANTS if kind != "baseline"
        }
    for lane in lanes:
        slots = [tuple(row["lanes"][lane]["first_slot"]) for row in rows]
        counts: Dict[str, int] = {}
        for slot in slots:
            label = f"({slot[0]:02d},{slot[1]:02d})"
            counts[label] = counts.get(label, 0) + 1
        summary["first_slot"][lane] = dict(sorted(counts.items(), key=lambda kv: -kv[1]))
    for key in ("makespan_s", "round_trip_path_m"):
        summary["conserved"][key] = all(
            len({row["lanes"][lane][key] for lane in lanes}) == 1 for row in rows
        )
    summary["violations_all_zero"] = all(
        row["lanes"][lane]["violations"] == 0 for row in rows for lane in lanes
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=30)
    parser.add_argument("--start", type=int, default=2026)
    parser.add_argument("--tau", type=float, default=0.5)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    seeds = list(range(args.start, args.start + args.seeds))
    began = time.time()
    out_dir = Path(__file__).resolve().parents[1] / "l4_showcase" / "evidence"
    for case in ("skew", "uniform"):
        print(f"[case {case}] seeds={seeds[0]}..{seeds[-1]} tau={args.tau}", flush=True)
        result = run_case(case, seeds, args.tau)
        payload = {
            "schema": SCHEMA, "case": case, "tau": args.tau,
            "seeds": {"start": args.start, "count": args.seeds},
            "variants": {
                "baseline": "生产现行评分定义(零改动)",
                "tau": f"保留项距离饱和 g=min(t_norm,{args.tau})/{args.tau}",
                "dynfmax": "f_norm 分母=批次实际 max freq(替代常数 100)",
                "both": "tau+dynfmax 叠加",
            },
            "patch_scope": "仅本进程 monkeypatch fill_only._score_terms + ws.make_score_fn;生产文件零改动",
            **result,
        }
        if args.smoke:
            print(json.dumps(payload["summary"], ensure_ascii=False, indent=1))
        else:
            target = out_dir / f"s3_score_whatif_{case}_{args.start}_{args.start + args.seeds - 1}.json"
            target.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"  -> {target}", flush=True)
    print(f"total {time.time() - began:.1f}s", flush=True)


if __name__ == "__main__":
    main()
