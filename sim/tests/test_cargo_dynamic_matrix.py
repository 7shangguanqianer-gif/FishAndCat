# -*- coding: utf-8 -*-
"""Risk matrix runner: fairness, infeasible regret and downgrade labels."""

import csv
import hashlib
import json
import os
import sys
import tempfile
import unittest


SIM = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if SIM not in sys.path:
    sys.path.insert(0, SIM)

import cargo_dynamic_matrix as cdm


class TestCargoDynamicMatrix(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.smoke_scenarios = ["E02", "E10", "E14", "E15", "E18"]
        cls.result = cdm.run_matrix(cls.smoke_scenarios, [2026])

    def test_smoke_has_five_cells_and_eight_modes_each(self):
        self.assertEqual(len(self.result["cells"]), 5)
        self.assertEqual(len(self.result["detail"]), 40)
        for sid in self.smoke_scenarios:
            rows = [row for row in self.result["detail"] if row["scenario"] == sid]
            self.assertEqual([row["mode"] for row in rows], cdm.MODES)

    def test_each_cell_has_one_shared_four_hash_bundle(self):
        for cell in self.result["cells"]:
            self.assertIs(cell["fairness_pass"], True)
            rows = [
                row for row in self.result["detail"]
                if row["scenario"] == cell["scenario"] and row["seed"] == cell["seed"]
            ]
            bundles = {
                (row["workload_hash"], row["arrivals_hash"],
                 row["noise_hash"], row["fault_stream_hash"])
                for row in rows
            }
            self.assertEqual(len(bundles), 1, cell["scenario"])

    def test_e14_and_e15_contract_fields_survive_csv_shape(self):
        e14 = [row for row in self.result["detail"] if row["scenario"] == "E14"]
        self.assertTrue(all(row["scheduled_cycles"] == 100 for row in e14))
        self.assertTrue(all(row["valid_cycles"] == 94 for row in e14))
        self.assertTrue(all(row["rejected_cycles"] == 6 for row in e14))
        self.assertTrue(all(row["response_sample_n"] in (0, 94) for row in e14))

        e15 = [row for row in self.result["detail"] if row["scenario"] == "E15"]
        self.assertTrue(all(row["extended_pressure"] is True for row in e15))
        self.assertTrue(all(row["canonical_g2"] is False for row in e15))
        self.assertTrue(all(row["headline_eligible"] is False for row in e15))
        self.assertTrue(all("非 canonical G2、非 H" in row["scenario_title"] for row in e15))

    def test_auto_regret_is_numeric_only_on_comparable_cells(self):
        auto_rows = [row for row in self.result["detail"] if row["mode"] == "AUTO"]
        for row in auto_rows:
            if row["auto_regret_status"] == "COMPARABLE":
                self.assertIsInstance(row["auto_regret_s"], float)
                self.assertGreaterEqual(row["auto_regret_s"], 0.0)
                self.assertTrue(row["oracle_mode"])
            else:
                self.assertIsNone(row["auto_regret_s"])

    def test_e13_infeasible_auto_regret_is_na(self):
        result = cdm.run_matrix(["E13"], [2026])
        auto = next(row for row in result["detail"] if row["mode"] == "AUTO")
        self.assertEqual(auto["status"], "INFEASIBLE")
        self.assertIsNone(auto["resp_p95_s"])
        self.assertIsNone(auto["auto_regret_s"])
        self.assertIn(auto["auto_regret_status"], {"NA_AUTO_INFEASIBLE", "NA_NO_FIXED_ORACLE"})
        self.assertEqual(result["cells"][0]["arrival_reference_status"], "GEOMETRY_BOUND_FALLBACK")

    def test_online_placement_failure_is_terminal_not_keyerror_or_fallback(self):
        # This full-S1 counterexample used to crash later when the workload
        # requested an inbound gid that AWRA had failed to place at cycle 4.
        result = cdm.run_matrix(["E08"], [2032])
        self.assertEqual(len(result["detail"]), 8)
        awra = next(row for row in result["detail"] if row["mode"] == "awra")
        self.assertEqual(awra["status"], "INFEASIBLE")
        self.assertEqual(awra["fails"], 1)
        self.assertIsNotNone(awra["terminal_failure_cycle"])
        self.assertGreater(awra["unprocessed_cycles"], 0)
        self.assertLess(awra["completed_cycles"], awra["valid_cycles"])
        self.assertIsNone(awra["resp_p95_s"])
        self.assertEqual(awra["failure_policy"], "TERMINATE_NO_FALLBACK")

    def test_stage_seed_partitions_are_disjoint_and_exact(self):
        self.assertEqual(cdm.stage_seeds("s1"), list(range(2026, 2036)))
        self.assertEqual(cdm.stage_seeds("s2"), list(range(31001, 31031)))
        self.assertEqual(cdm.stage_seeds("s3"), list(range(41001, 41011)))
        self.assertTrue(set(cdm.stage_seeds("s1")).isdisjoint(cdm.stage_seeds("s2")))
        self.assertTrue(set(cdm.stage_seeds("s2")).isdisjoint(cdm.stage_seeds("s3")))

    def test_write_outputs_preserves_detail_and_downgrade_fields(self):
        with tempfile.TemporaryDirectory() as temp:
            paths = cdm.write_outputs(self.result, temp, stage="smoke")
            self.assertEqual(set(paths), {"detail", "agg", "params", "manifest"})
            for path in paths.values():
                self.assertTrue(os.path.exists(path), path)
            with open(paths["detail"], encoding="utf-8-sig", newline="") as fp:
                rows = list(csv.DictReader(fp))
            e15 = next(row for row in rows if row["scenario"] == "E15")
            self.assertEqual(e15["extended_pressure"], "True")
            self.assertEqual(e15["canonical_g2"], "False")
            self.assertEqual(e15["headline_eligible"], "False")
            self.assertIn("非 canonical G2、非 H", e15["scenario_title"])

    def test_stage_outputs_are_isolated_and_conflicting_overwrite_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            s1 = cdm.write_outputs(self.result, temp, stage="s1")
            s2 = cdm.write_outputs(self.result, temp, stage="s2")
            self.assertNotEqual(os.path.dirname(s1["detail"]), os.path.dirname(s2["detail"]))
            self.assertEqual(os.path.basename(os.path.dirname(s1["detail"])), "s1")
            self.assertEqual(os.path.basename(os.path.dirname(s2["detail"])), "s2")

            # An identical rerun is deterministic and may safely refresh the
            # same evidence stage.
            repeat = cdm.write_outputs(self.result, temp, stage="s1")
            self.assertEqual(s1, repeat)

            conflicting = dict(self.result)
            conflicting["seeds"] = [99999]
            with self.assertRaisesRegex(FileExistsError, "refusing to overwrite"):
                cdm.write_outputs(conflicting, temp, stage="s1")

    def test_stage_path_escape_and_concurrent_writer_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            for stage in ("", ".", "..", "C:\\temp", "CON", "smoke/../s1"):
                with self.subTest(stage=stage):
                    with self.assertRaisesRegex(ValueError, "unsupported evidence stage"):
                        cdm.write_outputs(self.result, temp, stage=stage)

            stage_dir = os.path.join(temp, "cargo_dynamic_matrix", "s1")
            os.makedirs(stage_dir)
            lock = os.path.join(stage_dir, ".write.lock")
            with open(lock, "w", encoding="utf-8") as fp:
                fp.write("independent-writer")
            with self.assertRaisesRegex(FileExistsError, "write lock"):
                cdm.write_outputs(self.result, temp, stage="s1")

    def test_manifest_anchors_runner_functions_modes_and_actual_counts(self):
        with tempfile.TemporaryDirectory() as temp:
            paths = cdm.write_outputs(self.result, temp, stage="smoke")
            with open(paths["manifest"], encoding="utf-8") as fp:
                manifest = json.load(fp)
            runner = manifest["runner_provenance"]
            with open(cdm.__file__, "rb") as fp:
                expected_file_hash = hashlib.sha256(fp.read()).hexdigest()
            self.assertEqual(runner["source_sha256"]["sim/cargo_dynamic_matrix.py"],
                             expected_file_hash)
            self.assertEqual(
                set(runner["function_sha256"]),
                {
                    "stage_seeds", "_arrival_stream", "_row_from_metrics",
                    "run_cell", "aggregate_rows", "run_matrix", "write_outputs",
                },
            )
            self.assertEqual(manifest["modes"], cdm.MODES)
            self.assertEqual(manifest["cell_count"], 5)
            self.assertEqual(manifest["run_count"], 40)
            self.assertEqual(manifest["stage"], "smoke")


if __name__ == "__main__":
    unittest.main()
