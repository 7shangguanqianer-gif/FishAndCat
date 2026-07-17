"""S3 fill 多 seed 稳健性跑批(治理 C1,0716 深审获批;docs/S3算法深审与治理方案_0716.md)。

回应 P1-5「单 seed=2026 未证明期望取货排序稳健」:对 N 个确定性 seed 重跑
SEQ/NEAR/SCORE 三条在线 lane(完整复用 fill_only.build_shared_input /
run_online_lane,评分定义零改动),汇总六项终点指标的均值±标准差、逐 seed
排序频次与方向一致性,落 JSON 证据文件。结果如实报告——若排序翻转,
以本文件为准修正页面叙事。

用法(项目根):
    PYTHONIOENCODING=utf-8 python sim/fill_seed_sweep.py --seeds 30
    python sim/fill_seed_sweep.py --seeds 2 --smoke   # 冒烟计时,不落证据

seed 集=range(--start, --start+--seeds),默认 start=2026(与生产 release 同首元),
全部参数写入证据文件,零随机性。
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fill_only  # noqa: E402  (评分/数据定义唯一来源,零改动复用)

METRIC_KEYS = (
    "expected_retrieval_s", "hot20_retrieval_s", "heavy20_mean_tier",
    "lift_work_proxy_kgm", "makespan_s", "round_trip_path_m",
)
SWEEP_SCHEMA = "s3-fill-seed-sweep-v1"


def run_one_seed(seed: int, case: str) -> Dict[str, Any]:
    shared = fill_only.build_shared_input(seed=seed, case=case)
    lanes: Dict[str, Dict[str, float]] = {}
    for algorithm in fill_only.ONLINE_ALGORITHMS:
        lane = fill_only.run_online_lane(shared, algorithm)
        if lane["status"] != "FEASIBLE":
            raise RuntimeError(f"seed={seed} {algorithm} INFEASIBLE: {lane['failure']}")
        lanes[algorithm] = {key: lane["metrics"][key] for key in METRIC_KEYS}
        lanes[algorithm]["violations"] = lane["metrics"]["violations"]
    return {"seed": seed, "shared_input_sha256": shared["shared_input_sha256"], "lanes": lanes}


def ranking(values: Dict[str, float]) -> str:
    """按值升序排出算法次序,如 'seq<score<near'(越低越好口径)。"""
    return "<".join(sorted(values, key=lambda alg: values[alg]))


def summarize(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    summary: Dict[str, Any] = {"per_metric": {}, "conserved": {}}
    for key in METRIC_KEYS:
        stats = {}
        for algorithm in fill_only.ONLINE_ALGORITHMS:
            samples = [row["lanes"][algorithm][key] for row in rows]
            stats[algorithm] = {
                "mean": round(statistics.fmean(samples), 6),
                "stdev": round(statistics.stdev(samples), 6) if len(samples) > 1 else 0.0,
                "min": min(samples), "max": max(samples),
            }
        orders = Counter(
            ranking({alg: row["lanes"][alg][key] for alg in fill_only.ONLINE_ALGORITHMS})
            for row in rows
        )
        pairwise = {
            "score_lt_seq": sum(1 for row in rows
                                if row["lanes"]["score"][key] < row["lanes"]["seq"][key]),
            "score_lt_near": sum(1 for row in rows
                                 if row["lanes"]["score"][key] < row["lanes"]["near"][key]),
            "seq_lt_near": sum(1 for row in rows
                               if row["lanes"]["seq"][key] < row["lanes"]["near"][key]),
        }
        summary["per_metric"][key] = {
            "stats": stats,
            "ranking_counts": dict(orders.most_common()),
            "pairwise_win_counts": pairwise,
        }
    # 守恒量核查:每个 seed 内 makespan/路程三 lane 必须逐位相等(同格集机理)
    for key in ("makespan_s", "round_trip_path_m"):
        summary["conserved"][key] = all(
            row["lanes"]["seq"][key] == row["lanes"]["near"][key] == row["lanes"]["score"][key]
            for row in rows
        )
    summary["violations_all_zero"] = all(
        row["lanes"][alg]["violations"] == 0
        for row in rows for alg in fill_only.ONLINE_ALGORITHMS
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seeds", type=int, default=30, help="seed 个数(≥30 为 C1 验收档)")
    parser.add_argument("--start", type=int, default=2026, help="首个 seed,集合=range(start,start+seeds)")
    parser.add_argument("--case", default="skew", choices=("skew", "uniform"), help="货流情景")
    parser.add_argument("--out", default=None, help="证据 JSON 输出路径(默认 l4_showcase/evidence/)")
    parser.add_argument("--smoke", action="store_true", help="冒烟:只计时,不写证据文件")
    args = parser.parse_args()

    seeds = list(range(args.start, args.start + args.seeds))
    rows: List[Dict[str, Any]] = []
    t0 = time.perf_counter()
    for index, seed in enumerate(seeds, start=1):
        seed_t0 = time.perf_counter()
        rows.append(run_one_seed(seed, args.case))
        print(f"[{index}/{len(seeds)}] seed={seed} done in {time.perf_counter() - seed_t0:.1f}s",
              flush=True)
    elapsed = time.perf_counter() - t0

    summary = summarize(rows)
    exp = summary["per_metric"]["expected_retrieval_s"]
    print(f"\n== expected_retrieval_s over {len(seeds)} seeds (case={args.case}) ==")
    for algorithm in fill_only.ONLINE_ALGORITHMS:
        stats = exp["stats"][algorithm]
        print(f"  {algorithm:5s} mean={stats['mean']:.3f} ± {stats['stdev']:.3f} "
              f"[{stats['min']:.3f}, {stats['max']:.3f}]")
    print(f"  ranking counts: {exp['ranking_counts']}")
    print(f"  pairwise wins:  {exp['pairwise_win_counts']}")
    print(f"  conserved(makespan/path)={summary['conserved']}  "
          f"violations_all_zero={summary['violations_all_zero']}")
    print(f"total {elapsed:.1f}s")

    if args.smoke:
        return 0
    out_path = Path(args.out) if args.out else (
        Path(__file__).resolve().parents[1] / "l4_showcase" / "evidence"
        / f"s3_fill_seed_sweep_{args.case}_{seeds[0]}_{seeds[-1]}.json"
    )
    payload = {
        "schema_version": SWEEP_SCHEMA,
        "sim_only": True,
        "purpose": "governance C1: multi-seed robustness of terminal metrics (P1-5)",
        "scoring_definition_unchanged": True,
        "generator": "sim/fill_seed_sweep.py reusing fill_only.build_shared_input/run_online_lane",
        "case": args.case, "seeds": seeds, "elapsed_s": round(elapsed, 1),
        "metric_keys": list(METRIC_KEYS),
        "summary": summary, "rows": rows,
    }
    payload["payload_sha256"] = fill_only.payload_sha256(payload)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"evidence -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
