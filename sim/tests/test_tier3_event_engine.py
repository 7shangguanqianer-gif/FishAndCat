# -*- coding: utf-8 -*-
"""Single Tier 3 event engine: backward compatibility and auditable events."""

import os
import sys
import unittest


SIM = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if SIM not in sys.path:
    sys.path.insert(0, SIM)

import cargo_scenarios as cs
import realism
import warehouse_sim as ws
from mixed_ops import build_scenario_workload, build_workload


LEGACY_EXPECTED = {
    "seq": {"avg_retr": 19.422934023925457, "busy_total": 9073.918956154059,
            "downtime": 600.0, "fails": 0, "n_down": 1,
            "resp_p50": 134.89645392716375, "resp_p95": 917.9616137053558,
            "tot_dual": 5473.918956154061, "util": 0.49015726602977344, "viol": 0},
    "near": {"avg_retr": 11.757961524729913, "busy_total": 6894.237992117822,
             "downtime": 600.0, "fails": 0, "n_down": 1,
             "resp_p50": 77.33333333333394, "resp_p95": 651.1093516320318,
             "tot_dual": 3294.2379921178235, "util": 0.36494828694852305, "viol": 0},
    "score": {"avg_retr": 11.287552847860265, "busy_total": 6801.812217153048,
              "downtime": 600.0, "fails": 0, "n_down": 1,
              "resp_p50": 76.02413425728264, "resp_p95": 660.959370191817,
              "tot_dual": 3201.8122171530545, "util": 0.3595094124404995, "viol": 0},
    "awra": {"avg_retr": 10.740850585273417, "busy_total": 6713.085410252489,
             "downtime": 600.0, "fails": 0, "n_down": 1,
             "resp_p50": 71.0, "resp_p95": 666.9999999999999,
             "tot_dual": 3113.0854102524877, "util": 0.35481660575999885, "viol": 0},
}


class TestTier3EventEngine(unittest.TestCase):
    def setUp(self):
        self.old_accel = ws.ACCEL
        ws.ACCEL = True

    def tearDown(self):
        ws.ACCEL = self.old_accel

    def legacy_inputs(self, cycles=100):
        seed = 2026
        goods = ws.gen_goods(120, seed, "skew")
        new_goods, requests = build_workload(goods, cycles, seed)
        w_max = max(g.weight for g in goods)
        f_max = max(g.freq for g in goods)
        d_on, bg_on = ws.lookup_weights(120, "skew", "online")
        d_ba, bg_ba = ws.lookup_weights(120, "skew", "batch")
        fn = ws.make_score_fn(1.0, bg_on / 2, bg_on / 2, d_on, w_max, f_max)
        fnb = ws.make_score_fn(1.0, bg_ba / 2, bg_ba / 2, d_ba, w_max, f_max)
        arrivals, _ = realism.common_arrivals(
            goods, new_goods, requests, fn, w_max, f_max, fnb,
            cycles=cycles, seed=seed,
        )
        return seed, goods, new_goods, requests, w_max, f_max, fn, fnb, arrivals

    def test_legacy_four_strategy_metrics_are_bit_exact(self):
        args = self.legacy_inputs()
        seed, goods, new_goods, requests, w_max, f_max, fn, fnb, arrivals = args
        for strategy, expected in LEGACY_EXPECTED.items():
            actual = realism.run_tier3(
                strategy, goods, new_goods, requests, fn, w_max, f_max, fnb,
                arrivals=arrivals, cycles=100, seed=seed,
            )
            self.assertEqual(actual, expected, strategy)

    def test_fault_intervals_are_deterministic_and_hashable(self):
        a = realism.build_fault_intervals(100, 2026, 3000.0)
        b = realism.build_fault_intervals(100, 2026, 3000.0)
        self.assertEqual(a, b)
        self.assertEqual(len(a), 101)
        self.assertEqual(realism.stream_hash(a), realism.stream_hash(b))
        self.assertNotEqual(
            realism.stream_hash(a),
            realism.stream_hash(realism.build_fault_intervals(100, 2027, 3000.0)),
        )

    def test_fault_recovery_splits_and_resumes_the_actual_operation_phase(self):
        args = self.legacy_inputs(cycles=1)
        seed, goods, new_goods, requests, w_max, f_max, fn, fnb, arrivals = args
        baseline_events = []
        realism.run_tier3(
            "awra", goods, new_goods, requests, fn, w_max, f_max, fnb,
            arrivals=arrivals, cycles=1, seed=seed,
            fault_intervals=[1.0e9, 1.0e9], event_sink=baseline_events,
        )
        operations = [
            phase for phase in baseline_events[0]["phases"]
            if phase["name"] not in {"QUEUE", "FAULT_RECOVERY"}
            and phase["t1"] > phase["t0"]
        ]
        self.assertGreaterEqual(len(operations), 2)

        productive_before = 0.0
        targets = []
        for phase in operations:
            duration = phase["t1"] - phase["t0"]
            targets.append((phase["name"], productive_before + duration / 2.0))
            productive_before += duration
            if len(targets) == 2:
                break
        self.assertNotEqual(targets[0][0], targets[1][0])

        for target_name, offset in targets:
            events = []
            realism.run_tier3(
                "awra", goods, new_goods, requests, fn, w_max, f_max, fnb,
                arrivals=arrivals, cycles=1, seed=seed,
                fault_intervals=[offset, 1.0e9], event_sink=events,
            )
            event = events[0]
            recovery = next(p for p in event["phases"] if p["name"] == "FAULT_RECOVERY")
            self.assertEqual(recovery["operation_phase"], target_name)
            before = next(
                p for p in event["phases"]
                if p["name"] == target_name and p.get("segment") == "before_fault"
            )
            after = next(
                p for p in event["phases"]
                if p["name"] == target_name and p.get("segment") == "after_fault"
            )
            self.assertEqual(before["u1"], recovery["frozen_u"])
            self.assertEqual(after["u0"], recovery["frozen_u"])
            self.assertEqual(before["t1"], recovery["t0"])
            self.assertEqual(recovery["t1"], after["t0"])
            self.assertFalse(any(
                recovery["t0"] < owner["t"] < recovery["t1"]
                for owner in event["ownership_events"]
            ))

    def test_productive_busy_clock_consumes_remainder_and_allows_two_faults(self):
        """A repair must not reset the productive-time gap inside one cycle."""
        args = self.legacy_inputs(cycles=1)
        seed, goods, new_goods, requests, w_max, f_max, fn, fnb, arrivals = args
        baseline_events = []
        baseline = realism.run_tier3(
            "awra", goods, new_goods, requests, fn, w_max, f_max, fnb,
            arrivals=arrivals, cycles=1, seed=seed,
            fault_intervals=[1.0e9, 1.0e9], event_sink=baseline_events,
        )
        operations = [
            phase for phase in baseline_events[0]["phases"]
            if phase["name"] not in {"QUEUE", "FAULT_RECOVERY"}
            and phase["t1"] > phase["t0"]
        ]
        first_duration = operations[0]["t1"] - operations[0]["t0"]
        second_duration = operations[1]["t1"] - operations[1]["t0"]
        first_offset = first_duration / 2.0
        second_offset = first_duration + second_duration / 2.0

        events = []
        metrics = realism.run_tier3(
            "awra", goods, new_goods, requests, fn, w_max, f_max, fnb,
            arrivals=arrivals, cycles=1, seed=seed,
            fault_intervals=[
                first_offset,
                second_offset - first_offset,
                1.0e9,
            ],
            event_sink=events,
        )
        recoveries = [p for p in events[0]["phases"] if p["name"] == "FAULT_RECOVERY"]
        self.assertEqual(metrics["n_down"], 2)
        self.assertEqual(metrics["downtime"], 2 * realism.MTTR_S)
        self.assertEqual(metrics["productive_busy_s"], baseline["productive_busy_s"])
        self.assertEqual(events[0]["fault_busy_offsets"], [first_offset, second_offset])
        self.assertEqual(
            [p["operation_phase"] for p in recoveries],
            [operations[0]["name"], operations[1]["name"]],
        )
        self.assertEqual(len(recoveries), 2)
        self.assertEqual(
            events[0]["service"],
            baseline_events[0]["service"] + 2 * realism.MTTR_S,
        )

    def test_event_sink_has_continuous_phases_snapshots_and_ownership(self):
        args = self.legacy_inputs(cycles=8)
        seed, goods, new_goods, requests, w_max, f_max, fn, fnb, arrivals = args
        events = []
        metrics = realism.run_tier3(
            "awra", goods, new_goods, requests, fn, w_max, f_max, fnb,
            arrivals=arrivals, cycles=8, seed=seed, event_sink=events,
        )
        self.assertEqual(len(events), 8)
        for event in events:
            self.assertEqual(len(event["inventory_before"]), 120)
            self.assertEqual(len(event["inventory_after"]), 120)
            self.assertEqual(event["phases"][0]["t0"], event["arrival"])
            self.assertEqual(event["phases"][-1]["t1"], event["finish"])
            for left, right in zip(event["phases"], event["phases"][1:]):
                self.assertEqual(left["t1"], right["t0"])
            self.assertTrue(all(phase["t0"] <= phase["t1"] for phase in event["phases"]))
            self.assertEqual(len(event["ownership_events"]), 4)
            self.assertEqual(event["ownership_events"][-1]["t"], event["finish"])
        responses = sorted(event["response"] for event in events)
        self.assertEqual(metrics["resp_p50"], responses[len(responses) // 2])
        self.assertEqual(metrics["resp_p95"], responses[min(len(responses) - 1, int(len(responses) * 0.95))])

    def test_e14_rejects_are_not_response_or_service_samples(self):
        scenario = cs.load_registry()["scenarios"]["E14"]
        goods = cs.build_initial_goods("E14", 2026)
        inbound = cs.build_inbound_goods("E14", 2026, 100)
        workload = build_scenario_workload(goods, inbound, scenario, 2026)
        w_max = max(g.weight for g in goods)
        f_max = max(g.freq for g in goods)
        fn = ws.make_score_fn(1.0, 0.6, 0.4, 0.15, w_max, f_max)
        arrivals, _ = realism.common_arrivals_for_workload(
            goods, workload, fn, w_max, f_max, fn, seed=2026,
            tier3_params=scenario["tier3"],
        )
        events = []
        metrics = realism.run_tier3(
            "awra", goods, workload["valid_inbound_goods"], workload["requests"],
            fn, w_max, f_max, fn, arrivals=arrivals, cycles=100, seed=2026,
            workload=workload, event_sink=events, tier3_params=scenario["tier3"],
        )
        self.assertEqual(metrics["scheduled_cycles"], 100)
        self.assertEqual(metrics["valid_cycles"], 94)
        self.assertEqual(metrics["rejected_cycles"], 6)
        self.assertEqual(metrics["response_sample_n"], 94)
        self.assertEqual(metrics["dual_time_sample_n"], 94)
        rejected = [event for event in events if event["status"] == "REJECT_NO_DISPATCH"]
        self.assertEqual(len(rejected), 6)
        self.assertTrue(all(event["response"] is None for event in rejected))
        self.assertTrue(all(event["service"] == 0.0 for event in rejected))
        self.assertTrue(all(event["inventory_before"] == event["inventory_after"] for event in rejected))
        self.assertTrue(all(event["inventory_before"] is not event["inventory_after"] for event in rejected))

    def test_online_placement_failure_terminates_without_inventory_corruption(self):
        scenario = cs.load_registry()["scenarios"]["E08"]
        seed = 2032
        goods = cs.build_initial_goods("E08", seed)
        inbound = cs.build_inbound_goods("E08", seed, scenario["scheduled_cycles"])
        workload = build_scenario_workload(goods, inbound, scenario, seed)
        w_max = max(g.weight for g in goods)
        f_max = max(g.freq for g in goods)
        fn = ws.make_score_fn(1.0, 0.6, 0.4, 0.15, w_max, f_max)
        arrivals, _ = realism.common_arrivals_for_workload(
            goods, workload, fn, w_max, f_max, fn, seed=seed,
            tier3_params=scenario["tier3"],
        )
        events = []
        metrics = realism.run_tier3(
            "awra", goods, workload["valid_inbound_goods"], workload["requests"],
            fn, w_max, f_max, fn, arrivals=arrivals,
            cycles=workload["scheduled_cycles"], seed=seed, workload=workload,
            event_sink=events, tier3_params=scenario["tier3"],
        )
        terminal = events[-1]
        self.assertEqual(metrics["status"], "INFEASIBLE")
        self.assertEqual(metrics["fails"], 1)
        self.assertEqual(terminal["status"], "PLACEMENT_FAIL_TERMINAL")
        self.assertEqual(terminal["cycle"], metrics["terminal_failure_cycle"])
        self.assertEqual(terminal["inventory_before"], terminal["inventory_after"])
        self.assertIsNot(terminal["inventory_before"], terminal["inventory_after"])
        self.assertEqual(terminal["ownership_events"], [])
        self.assertEqual(len(terminal["inventory_after"]), len(goods))
        self.assertEqual(len(events), metrics["processed_scheduled_cycles"])
        self.assertEqual(metrics["completed_cycles"], metrics["response_sample_n"])
        self.assertGreater(metrics["unprocessed_cycles"], 0)

    def test_stream_hashes_are_shared_across_strategies(self):
        scenario = cs.load_registry()["scenarios"]["E02"]
        goods = cs.build_initial_goods("E02", 2026)
        inbound = cs.build_inbound_goods("E02", 2026, 100)
        workload = build_scenario_workload(goods, inbound, scenario, 2026)
        w_max = max(g.weight for g in goods)
        f_max = max(g.freq for g in goods)
        fn = ws.make_score_fn(1.0, 0.6, 0.4, 0.15, w_max, f_max)
        arrivals, _ = realism.common_arrivals_for_workload(
            goods, workload, fn, w_max, f_max, fn, seed=2026,
            tier3_params=scenario["tier3"],
        )
        hashes = []
        for strategy in ("seq", "near", "score", "awra"):
            metrics = realism.run_tier3(
                strategy, goods, workload["valid_inbound_goods"], workload["requests"],
                fn, w_max, f_max, fn, arrivals=arrivals, cycles=100, seed=2026,
                workload=workload, tier3_params=scenario["tier3"],
            )
            hashes.append(metrics["stream_hashes"])
        self.assertEqual(hashes, [hashes[0]] * 4)
        self.assertEqual(hashes[0]["workload_hash"], workload["workload_hash"])
        self.assertEqual(set(hashes[0]), {"workload_hash", "arrivals_hash", "noise_hash", "fault_stream_hash"})

    def test_workload_and_events_cannot_label_each_other(self):
        scenario = cs.load_registry()["scenarios"]["E02"]
        goods = cs.build_initial_goods("E02", 2026)
        inbound = cs.build_inbound_goods("E02", 2026, 100)
        workload = build_scenario_workload(goods, inbound, scenario, 2026)
        w_max = max(g.weight for g in goods)
        f_max = max(g.freq for g in goods)
        fn = ws.make_score_fn(1.0, 0.6, 0.4, 0.15, w_max, f_max)
        arrivals, _ = realism.common_arrivals_for_workload(
            goods, workload, fn, w_max, f_max, fn, seed=2026,
            tier3_params=scenario["tier3"],
        )
        tampered = list(workload["cycles"])
        tampered[0] = dict(tampered[0], dispatch=False, status="REJECT_NO_DISPATCH")
        with self.assertRaisesRegex(ValueError, "mutually exclusive"):
            realism.run_tier3(
                "awra", goods, workload["valid_inbound_goods"], workload["requests"],
                fn, w_max, f_max, fn, arrivals=arrivals, cycles=100, seed=2026,
                workload=workload, events=tampered,
                tier3_params=scenario["tier3"],
            )

    def test_events_only_hash_covers_every_good_field_and_record_metadata(self):
        args = self.legacy_inputs(cycles=1)
        seed, goods, new_goods, requests, w_max, f_max, fn, fnb, arrivals = args
        records = realism._legacy_event_records(new_goods, requests, 1)
        baseline = realism._legacy_workload_hash(goods, records, seed)

        def clone(good, **overrides):
            values = dict(gid=good.gid, name=good.name, weight=good.weight,
                          freq=good.freq, vol=good.vol)
            values.update(overrides)
            return ws.Good(values["gid"], values["name"], values["weight"],
                           values["freq"], values["vol"])

        field_changes = {
            "gid": new_goods[0].gid + 50000,
            "name": new_goods[0].name + "_tampered",
            "weight": new_goods[0].weight + 0.125,
            "freq": new_goods[0].freq + 0.125,
            "vol": new_goods[0].vol + 0.001,
        }
        for field, value in field_changes.items():
            changed = [dict(records[0])]
            changed[0]["inbound_good"] = clone(new_goods[0], **{field: value})
            self.assertNotEqual(
                realism._legacy_workload_hash(goods, changed, seed), baseline, field
            )

        for field, value in {
            "cycle": 99,
            "status": "TAMPERED",
            "dispatch": False,
            "inbound_profile": "heavy",
            "advisory": {"applied": True},
        }.items():
            changed = [dict(records[0])]
            changed[0][field] = value
            self.assertNotEqual(
                realism._legacy_workload_hash(goods, changed, seed), baseline, field
            )

        base_metrics = realism.run_tier3(
            "awra", goods, new_goods, requests, fn, w_max, f_max, fnb,
            arrivals=arrivals, cycles=1, seed=seed, events=records,
            fault_intervals=[1.0e9, 1.0e9],
        )
        changed = [dict(records[0])]
        changed[0]["inbound_good"] = clone(
            new_goods[0], name=new_goods[0].name + "_tampered"
        )
        changed_metrics = realism.run_tier3(
            "awra", goods, [changed[0]["inbound_good"]], requests,
            fn, w_max, f_max, fnb, arrivals=arrivals, cycles=1, seed=seed,
            events=changed, fault_intervals=[1.0e9, 1.0e9],
        )
        self.assertNotEqual(
            base_metrics["stream_hashes"]["workload_hash"],
            changed_metrics["stream_hashes"]["workload_hash"],
        )


if __name__ == "__main__":
    unittest.main()
