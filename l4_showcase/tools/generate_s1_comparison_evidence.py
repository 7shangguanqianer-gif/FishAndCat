"""Build the offline S1 comparison bundle used by the S3 evidence drawer.

The bundle is deliberately separate from the 45 representative S3 playback
traces.  S1 is the controlled 10-seed matrix; S3 remains a visual trace and
must not be pooled into rankings or regret calculations.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AGG = ROOT / "sim" / "out" / "cargo_dynamic_matrix" / "s1" / "cargo_dynamic_matrix_agg.csv"
PARAMS = ROOT / "sim" / "out" / "cargo_dynamic_matrix" / "s1" / "cargo_dynamic_matrix_params.csv"
MANIFEST = ROOT / "sim" / "out" / "cargo_dynamic_matrix" / "s1" / "cargo_dynamic_matrix_manifest.json"
OUTPUT = ROOT / "l4_showcase" / "out" / "s1_comparison_evidence.js"
CANONICAL_OUTPUT = ROOT / "l4_showcase" / "out" / "s1_comparison_evidence.canonical.json"

MODES = ["random", "seq", "near", "score", "awra", "cb", "tob", "AUTO"]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def as_bool(value: str) -> bool:
    if value not in {"True", "False"}:
        raise ValueError(f"invalid bool {value!r}")
    return value == "True"


def optional_float(value: str):
    return None if value == "" else float(value)


def main() -> None:
    with AGG.open("r", encoding="utf-8-sig", newline="") as handle:
        source_rows = list(csv.DictReader(handle))
    if len(source_rows) != 18 * 8:
        raise ValueError(f"expected 144 aggregate rows, got {len(source_rows)}")

    rows = []
    scenarios = []
    seen_scenarios = set()
    for row in source_rows:
        if row["mode"] not in MODES:
            raise ValueError(f"unexpected mode {row['mode']}")
        if row["scenario"] not in seen_scenarios:
            seen_scenarios.add(row["scenario"])
            scenarios.append({
                "id": row["scenario"],
                "title": row["scenario_title"],
                "extended_pressure": as_bool(row["extended_pressure"]),
                "canonical_g2": as_bool(row["canonical_g2"]),
                "headline_eligible": as_bool(row["headline_eligible"]),
            })
        rows.append({
            "scenario": row["scenario"],
            "mode": row["mode"],
            "n_runs": int(row["n_runs"]),
            "n_feasible": int(row["n_feasible"]),
            "infeasible_rate": float(row["infeasible_rate"]),
            "p95_seed_n": int(row["p95_seed_n"]),
            "p95_mean_s": optional_float(row["p95_mean_s"]),
            "p95_sd_s": optional_float(row["p95_sd_s"]),
            "p95_ci95_half_s": optional_float(row["p95_ci95_half_s"]),
            "auto_regret_seed_n": int(row["auto_regret_seed_n"]),
            "auto_regret_mean_s": optional_float(row["auto_regret_mean_s"]),
            "auto_regret_ci95_half_s": optional_float(row["auto_regret_ci95_half_s"]),
            "fail_sum": int(row["fail_sum"]),
            "viol_sum": int(row["viol_sum"]),
            "reject_sum": int(row["reject_sum"]),
            "picked_counts": json.loads(row["picked_counts"]),
            "selection_stability": float(row["selection_stability"]),
            "score_policy": row["score_policy"],
        })

    with PARAMS.open("r", encoding="utf-8-sig", newline="") as handle:
        params = {row["param"]: row["value"] for row in csv.DictReader(handle)}
    expected_seeds = [str(value) for value in range(2026, 2036)]
    if params.get("stage") != "s1" or params.get("sim_only") != "True":
        raise ValueError("S1/sim-only guard missing")
    if [item.strip() for item in params.get("seeds", "").split(",")] != expected_seeds:
        raise ValueError("unexpected S1 seed set")

    payload = {
        "schema_version": "s1-comparison-evidence-v1",
        "sim_only": True,
        "stage": "s1",
        "purpose": "controlled-comparison-only; never merge with representative S3 playback",
        "modes": MODES,
        "seeds": list(range(2026, 2036)),
        "score_policy": params["score_policy"],
        "online_failure_policy": params["online_failure_policy"],
        "p95_convention": params["p95_convention"],
        "scenarios": scenarios,
        "rows": rows,
        "source_hashes": {
            "aggregate_csv": sha256(AGG),
            "params_csv": sha256(PARAMS),
            "matrix_manifest_json": sha256(MANIFEST),
            "generator": sha256(Path(__file__).resolve()),
        },
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    payload["payload_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    pretty = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with CANONICAL_OUTPUT.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(canonical)
    with OUTPUT.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(
            "(function(root){\n  \"use strict\";\n  root.S3_COMPARISON_EVIDENCE = "
            + pretty
            + ";\n})(typeof window !== \"undefined\" ? window : globalThis);\n"
        )
    print(json.dumps({"output": str(OUTPUT), "canonical_output": str(CANONICAL_OUTPUT),
                      "rows": len(rows), "scenarios": len(scenarios),
                      "payload_sha256": payload["payload_sha256"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
