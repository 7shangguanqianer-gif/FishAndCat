# Factory I/O F3 Layered Calibration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不移动官方 Factory I/O 场景几何的前提下，建立可观察、可证伪、可回滚的入料—取货—带载移动—入架门禁，并完成 `[1, 30, 54] × 3` 物理验收。

**Architecture:** 保留 `f3_stacker_control.py` 现有 Modbus、安全互锁和组合动作结构，只增加三项最小能力：载入前 rest/停带后落稳、带载移动前状态门、诊断观察窗口。离线测试只验证控制契约；现场 G0–G4 使用固定机位、I/O 快照和日志三重证据，任何一门失败都停止扩展。

**Tech Stack:** Python 3.9、`unittest`、`pymodbus`、Factory I/O 2.5.10 Ultimate、Modbus TCP/IP Server、PowerShell、Git。

---

## File Map

- Modify: `l2_factoryio/f3_stacker_control.py` — 载入准备、落稳窗口、带载状态门、诊断观察窗口和 CLI 参数。
- Modify: `l2_factoryio/test_f3_stacker_control.py` — 上述控制契约的离线回归测试。
- Create: `l2_factoryio/records/F3_layered_calibration_0713.md` — G0–G4 与 9 次终验的命令、I/O、画面判定和失败记录。
- Create conditionally after physical PASS: `l2_factoryio/scenes/F3_calibration_pass_0713.factoryio` — 仅保存官方几何 + 已验证 Modbus 映射；transform 不得变化。
- Update after final verdict: `docs/overnight2-report_0712night.md` — F3 状态、证据路径、剩余阻塞；不提前签绿。

## Task 1: Freeze the Current Controller Baseline

**Files:**
- Inspect: `l2_factoryio/f3_stacker_control.py`
- Inspect: `l2_factoryio/test_f3_stacker_control.py`
- Inspect: `l2_factoryio/logs/`

- [ ] **Step 1: Verify Factory I/O outputs are safe before file work**

Run:

```powershell
python .\f3_stacker_control.py stop
python .\f3_stacker_control.py snapshot
```

Expected: `C0..C6=False`, `Target=0`; if Modbus is unavailable because the clean official scene has Driver=None, record that fact and do not start GUI motion.

- [ ] **Step 2: Run the current offline regression**

Run:

```powershell
python -m unittest -v test_f3_stacker_control.py
```

Expected: `Ran 13 tests` and `OK`.

- [ ] **Step 3: Record the dirty-file boundary**

Run:

```powershell
git diff -- l2_factoryio/f3_stacker_control.py l2_factoryio/test_f3_stacker_control.py
git status --short
```

Expected: only the already-known uncommitted F3 edits overlap this plan; unrelated DOCX/MD changes remain untouched and unstaged.

## Task 2: Prepare the Load Station Before Feeding

**Files:**
- Modify: `l2_factoryio/test_f3_stacker_control.py`
- Modify: `l2_factoryio/f3_stacker_control.py`

- [ ] **Step 1: Add failing tests for rest-before-feed and post-belt settling**

Add to `SequenceContractTests`:

```python
def test_feed_moves_to_rest_before_starting_conveyors(self):
    stacker = self.make_stacker()
    stacker.box_at_load.side_effect = [False, True, True]

    with patch("f3_stacker_control.time.sleep"):
        stacker.feed_one_box()

    stacker.goto.assert_called_once_with(f3.POS_REST, "(prepare load station)")
    first_belt_call = stacker.coil.call_args_list.index(call(f3.C_ENTRY_CONV, True))
    self.assertGreater(first_belt_call, -1)

def test_feed_stops_belts_before_settle_dwell(self):
    stacker = self.make_stacker()
    stacker.box_at_load.side_effect = [False, True, True]

    with patch("f3_stacker_control.time.sleep") as sleep:
        stacker.feed_one_box()

    self.assertEqual(stacker.coil.call_args_list[-2:], [
        call(f3.C_ENTRY_CONV, False),
        call(f3.C_LOAD_CONV, False),
    ])
    sleep.assert_called_once_with(f3.LOAD_SETTLE_DWELL)
    self.assertEqual(f3.LOAD_SETTLE_DWELL, 2.0)

def test_feed_rechecks_load_after_settle(self):
    stacker = self.make_stacker()
    stacker.box_at_load.side_effect = [False, True, True]

    with patch("f3_stacker_control.time.sleep"):
        stacker.feed_one_box()

    self.assertEqual(stacker.wait_stable.call_count, 2)
    self.assertEqual(stacker.wait_stable.call_args_list[-1].args[0], "box remains at load after settle")
```

- [ ] **Step 2: Run the three tests and verify failure**

Run:

```powershell
python -m unittest -v \
  test_f3_stacker_control.SequenceContractTests.test_feed_moves_to_rest_before_starting_conveyors \
  test_f3_stacker_control.SequenceContractTests.test_feed_stops_belts_before_settle_dwell \
  test_f3_stacker_control.SequenceContractTests.test_feed_rechecks_load_after_settle
```

Expected: FAIL because `LOAD_SETTLE_DWELL` and the preparation/second stability check do not exist.

- [ ] **Step 3: Implement the minimal load-station preparation**

Add beside `PLACEMENT_SETTLE_DWELL`:

```python
LOAD_SETTLE_DWELL = 2.0
```

Change `feed_one_box()` to:

```python
def feed_one_box(self) -> None:
    self.goto(POS_REST, "(prepare load station)")
    self.forks_center()
    if self.box_at_load():
        print("* 载入位已有箱，跳过输送")
        return
    print("* 入料：Entry + Load Conveyor")
    self.coil(C_ENTRY_CONV, True)
    self.coil(C_LOAD_CONV, True)
    try:
        self.wait_stable(
            "box At Load",
            self.box_at_load,
            timeout=60.0,
            stable_for=0.30,
        )
    finally:
        self.coil(C_ENTRY_CONV, False)
        self.coil(C_LOAD_CONV, False)
    print(f"* load settle dwell: {LOAD_SETTLE_DWELL:.1f}s")
    time.sleep(LOAD_SETTLE_DWELL)
    self.wait_stable(
        "box remains at load after settle",
        self.box_at_load,
        timeout=1.5,
        stable_for=0.40,
    )
```

Update existing feed tests so `forks_center` and `goto` are expected preparation calls even when a box already occupies At Load.

- [ ] **Step 4: Run the full controller test file**

Run:

```powershell
python -m unittest -v test_f3_stacker_control.py
```

Expected: `Ran 16 tests` and `OK`.

- [ ] **Step 5: Commit only the two controller files**

```powershell
git add -- l2_factoryio/f3_stacker_control.py l2_factoryio/test_f3_stacker_control.py
git diff --cached --check
git commit -m "F3校准:载入前归位并增加停带落稳门"
git push origin master
```

## Task 3: Add a Loaded-Transport State Gate

**Files:**
- Modify: `l2_factoryio/test_f3_stacker_control.py`
- Modify: `l2_factoryio/f3_stacker_control.py`

- [ ] **Step 1: Add failing tests for unsafe loaded travel**

Extend `make_stacker()` with `stacker.assert_loaded_transport_ready = Mock()` only in tests that verify higher-level orchestration; for the method tests create a raw `Stacker.__new__` instance.

Add:

```python
def test_loaded_transport_gate_rejects_unsafe_state(self):
    stacker = f3.Stacker.__new__(f3.Stacker)
    inputs = [False] * len(f3.INPUT_NAMES)
    inputs[f3.IN_AT_MIDDLE] = True
    inputs[f3.IN_AT_LOAD] = True
    coils = [False] * len(f3.COIL_NAMES)
    coils[f3.C_LIFT] = False
    stacker.snapshot = Mock(return_value={"inputs": inputs, "coils": coils, "target": 0})

    with self.assertRaisesRegex(RuntimeError, "Lift=True"):
        stacker.assert_loaded_transport_ready()

def test_loaded_transport_gate_accepts_middle_lifted_and_load_clear(self):
    stacker = f3.Stacker.__new__(f3.Stacker)
    inputs = [False] * len(f3.INPUT_NAMES)
    inputs[f3.IN_AT_MIDDLE] = True
    inputs[f3.IN_AT_LOAD] = True
    coils = [False] * len(f3.COIL_NAMES)
    coils[f3.C_LIFT] = True
    stacker.snapshot = Mock(return_value={"inputs": inputs, "coils": coils, "target": 0})

    stacker.assert_loaded_transport_ready()

def test_travel_checks_loaded_gate_before_motion(self):
    stacker = self.make_stacker()
    stacker.assert_loaded_transport_ready = Mock()

    stacker.travel_loaded_to(30)

    stacker.assert_loaded_transport_ready.assert_called_once_with()
    stacker.goto.assert_called_once_with(30, "(loaded travel to cell 30)")
```

- [ ] **Step 2: Run the tests and verify failure**

Run:

```powershell
python -m unittest -v \
  test_f3_stacker_control.SequenceContractTests.test_loaded_transport_gate_rejects_unsafe_state \
  test_f3_stacker_control.SequenceContractTests.test_loaded_transport_gate_accepts_middle_lifted_and_load_clear \
  test_f3_stacker_control.SequenceContractTests.test_travel_checks_loaded_gate_before_motion
```

Expected: FAIL because `assert_loaded_transport_ready()` does not exist.

- [ ] **Step 3: Implement the gate and call it before movement**

Add to `Stacker`:

```python
def assert_loaded_transport_ready(self) -> None:
    snap = self.snapshot()
    problems = []
    if not snap["inputs"][IN_AT_MIDDLE]:
        problems.append("forks are not Middle")
    if snap["inputs"][IN_MOVING_X] or snap["inputs"][IN_MOVING_Z]:
        problems.append("crane still moving")
    if not snap["inputs"][IN_AT_LOAD]:
        problems.append("At Load still blocked")
    if not snap["coils"][C_LIFT]:
        problems.append("Lift=True required for loaded travel")
    if snap["coils"][C_FORKS_L] or snap["coils"][C_FORKS_R]:
        problems.append("fork outputs must be False at Middle")
    if problems:
        raise RuntimeError("loaded transport gate failed: " + "; ".join(problems))
    print("LOADED GATE OK: Middle, Lift=True, At Load clear")
```

Change `travel_loaded_to()` to call `self.assert_loaded_transport_ready()` before `self.goto(...)`.

- [ ] **Step 4: Run the full controller test file**

Run:

```powershell
python -m unittest -v test_f3_stacker_control.py
```

Expected: `Ran 19 tests` and `OK`.

- [ ] **Step 5: Commit and push the gate**

```powershell
git add -- l2_factoryio/f3_stacker_control.py l2_factoryio/test_f3_stacker_control.py
git diff --cached --check
git commit -m "F3校准:带载移动前增加状态门"
git push origin master
```

## Task 4: Add an Explicit Diagnostic Observation Window

**Files:**
- Modify: `l2_factoryio/test_f3_stacker_control.py`
- Modify: `l2_factoryio/f3_stacker_control.py`

- [ ] **Step 1: Add failing tests for observation-before-cleanup**

Add:

```python
def test_observation_hold_emits_snapshot_and_waits(self):
    stacker = self.make_stacker()
    stacker.print_snapshot = Mock()
    stacker.check_interlocks = Mock()

    with patch("f3_stacker_control.time.sleep") as sleep:
        stacker.observe_phase("G2_PICK", 0.2)

    stacker.print_snapshot.assert_called_once_with("OBSERVE G2_PICK")
    self.assertGreaterEqual(sleep.call_count, 1)

def test_diagnostic_pick_observes_before_return(self):
    stacker = self.make_stacker()
    stacker.feed_one_box = Mock()
    stacker.pick_from_load = Mock()
    stacker.observe_phase = Mock()

    stacker.run_diagnostic("pick", 1, observe_seconds=20.0)

    stacker.pick_from_load.assert_called_once_with()
    stacker.observe_phase.assert_called_once_with("G2_PICK", 20.0)
```

- [ ] **Step 2: Run the tests and verify failure**

Run:

```powershell
python -m unittest -v \
  test_f3_stacker_control.SequenceContractTests.test_observation_hold_emits_snapshot_and_waits \
  test_f3_stacker_control.SequenceContractTests.test_diagnostic_pick_observes_before_return
```

Expected: FAIL because `observe_phase()` and the `observe_seconds` argument do not exist.

- [ ] **Step 3: Implement observation without changing the mechanical state**

Add:

```python
def observe_phase(self, label: str, seconds: float) -> None:
    if seconds <= 0:
        return
    self.print_snapshot(f"OBSERVE {label}")
    print(f"OBSERVE WINDOW {label}: {seconds:.1f}s; pause Factory I/O now")
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        self.check_interlocks()
        time.sleep(min(0.10, max(0.0, deadline - time.monotonic())))
```

Change the diagnostic signature and phase labels:

```python
def run_diagnostic(self, phase: str, cell: int, observe_seconds: float = 0.0) -> None:
    if phase not in DIAGNOSTIC_PHASES:
        raise ValueError(f"invalid diagnostic phase: {phase}")
    if phase == "store":
        self.store_one(cell)
        self.observe_phase("G4_STORE", observe_seconds)
        return
    self.feed_one_box()
    if phase == "feed":
        self.observe_phase("G1_FEED", observe_seconds)
        return
    self.pick_from_load()
    if phase == "pick":
        self.observe_phase("G2_PICK", observe_seconds)
        return
    self.travel_loaded_to(cell)
    self.observe_phase("G3_TRAVEL", observe_seconds)
```

Extend the parser and main dispatch:

```python
diagnose.add_argument("--observe-seconds", type=float, default=0.0)
```

```python
stacker.run_diagnostic(args.phase, args.cell, args.observe_seconds)
```

The observation window must run before `main()` reaches the existing final `all_stop()`.

- [ ] **Step 4: Run all controller tests and compile**

Run:

```powershell
python -m unittest -v test_f3_stacker_control.py
python -m py_compile f3_stacker_control.py test_f3_stacker_control.py
```

Expected: `Ran 21 tests`, `OK`, and compile exits 0.

- [ ] **Step 5: Commit and push the diagnostic window**

```powershell
git add -- l2_factoryio/f3_stacker_control.py l2_factoryio/test_f3_stacker_control.py
git diff --cached --check
git commit -m "F3诊断:增加不破坏现场的观察窗口"
git push origin master
```

## Task 5: Establish G0 and G1 Live Evidence

**Files:**
- Create: `l2_factoryio/records/F3_layered_calibration_0713.md`
- Optionally create: `l2_factoryio/img/F3_G0_geometry_0713.png`
- Optionally create: `l2_factoryio/img/F3_G1_feed_settled_0713.png`

- [ ] **Step 1: Restore the mapped debug scene without moving parts**

In Factory I/O, open the saved debug copy containing the Modbus mapping. Confirm status bar shows `Modbus TCP/IP Server (Started)`. Do not use Edit-mode dragging; press F6 before each live probe.

- [ ] **Step 2: Capture the fixed G0 camera**

Use a saved top/oblique camera that shows the load conveyor endpoint, carrier/forks and first rack column. Record the clean-scene XML facts in the record:

```markdown
- Object count: baseline=45, debug=45
- StackerCrane: Position 276,33,146
- LoadingConveyor: Position 266,2,184 and 285,2,184
- Rack: Position 266,25,109 / 136 / 163
- Transform verdict: no conveyor/stacker/rack displacement
```

- [ ] **Step 3: Run G1 only**

Run:

```powershell
python .\f3_stacker_control.py diagnose feed 1 --observe-seconds 20
```

During `OBSERVE WINDOW G1_FEED`, pause Factory I/O and capture the fixed camera. Do not proceed if the pallet or box is already tilted, sliding, oscillating, or touching the guard.

- [ ] **Step 4: Record the G1 verdict**

Append a table row with exact timestamp, command, At Load state, belt coil states, screenshot path and `PASS/FAIL`. If FAIL, change only `LOAD_SETTLE_DWELL` or conveyor sequencing in a new TDD task; do not run G2.

- [ ] **Step 5: Commit only G0/G1 evidence when the verdict is explicit**

```powershell
git add -- l2_factoryio/records/F3_layered_calibration_0713.md l2_factoryio/img/F3_G0_geometry_0713.png l2_factoryio/img/F3_G1_feed_settled_0713.png
git diff --cached --check
git commit -m "F3现场:G0几何与G1入料落稳验收"
git push origin master
```

If an optional image was not created, omit that exact path from `git add`.

## Task 6: Establish G2 Direction and Pickup Evidence

**Files:**
- Update: `l2_factoryio/records/F3_layered_calibration_0713.md`
- Create: `l2_factoryio/img/F3_G2_pick_left_0713.png`

- [ ] **Step 1: Reset and run the Left-side working hypothesis**

Press F6, then run:

```powershell
python .\f3_stacker_control.py diagnose pick 1 --observe-seconds 20
```

During `OBSERVE WINDOW G2_PICK`, pause Factory I/O. Required I/O: At Load=True, At Middle=True, Lift coil=True, fork coils=False.

- [ ] **Step 2: Apply the visual gate**

Required picture: pallet/box is horizontal on the carrier, clear of load conveyor, control cabinet and safeguards. A cleared At Load with a tilted/falling pallet is FAIL.

- [ ] **Step 3: Run the opposite direction only if Left fails to clear At Load**

Do not edit production code first. Use a one-off empty/single-load diagnostic branch only after F6, capture Right-side evidence, and then change direction constants/tests together. Never run both sides against the same disturbed load.

- [ ] **Step 4: Record and commit the direction verdict**

Append the observed direction, I/O, screenshot, and whether any cargo contact occurred. Commit only the record/image; if code direction changes, use a separate TDD commit before repeating G2.

## Task 7: Establish G3 and G4 Physical Evidence

**Files:**
- Update: `l2_factoryio/records/F3_layered_calibration_0713.md`
- Create: `l2_factoryio/img/F3_G3_travel_cell1_0713.png`
- Create: `l2_factoryio/img/F3_G4_store_cell1_0713.png`

- [ ] **Step 1: Run one loaded move to cell 1**

Press F6, then run:

```powershell
python .\f3_stacker_control.py diagnose travel 1 --observe-seconds 20
```

During the observation window, pause and verify horizontal cargo, Middle forks, Lift=True, no guard/cabinet contact and no continued Moving X/Z.

- [ ] **Step 2: Run one complete store only after G3 PASS**

Press F6, then run:

```powershell
python .\f3_stacker_control.py diagnose store 1 --observe-seconds 10
```

Required picture: pallet rests flat on rack beams; forks return Middle without dragging the pallet; crane returns rest; no upright pallet remains near the load station.

- [ ] **Step 3: Record exact failures instead of tuning globally**

Map failures to one gate: pre-feed tilt→G1, pickup tilt→G2, travel fall→G3, rack drag/drop→G4. Physics timestep/solver changes are prohibited unless all four action gates are correct and default 1× still shows residual jitter.

- [ ] **Step 4: Commit G2–G4 evidence**

```powershell
git add -- l2_factoryio/records/F3_layered_calibration_0713.md l2_factoryio/img/F3_G2_pick_left_0713.png l2_factoryio/img/F3_G3_travel_cell1_0713.png l2_factoryio/img/F3_G4_store_cell1_0713.png
git diff --cached --check
git commit -m "F3现场:关闭取货带载与入架分层门"
git push origin master
```

## Task 8: Run the 3/3 Calibration and 9/9 Final Gate

**Files:**
- Update: `l2_factoryio/records/F3_layered_calibration_0713.md`
- Update only after final verdict: `docs/overnight2-report_0712night.md`
- Create after PASS: `l2_factoryio/scenes/F3_calibration_pass_0713.factoryio`

- [ ] **Step 1: Run one calibration pass across representative cells**

For each cell, press F6 and run separately:

```powershell
python .\f3_stacker_control.py probe 1
python .\f3_stacker_control.py probe 30
python .\f3_stacker_control.py probe 54
```

Expected: 3/3 visual + I/O + log PASS. Do not use `accept` yet because separate F6 resets isolate failures.

- [ ] **Step 2: Repeat two more isolated rounds**

Repeat the same three commands twice, pressing F6 before every command. Expected cumulative result: 9/9; each run records its own log and screenshot/verdict.

- [ ] **Step 3: Run all offline regressions**

Run:

```powershell
python -m unittest -v test_f3_stacker_control.py test_task_contract.py test_event_log.py test_task_orchestrator.py
python -m py_compile f3_stacker_control.py task_contract.py event_log.py task_orchestrator.py
```

Expected: all tests `OK`, compile exits 0.

- [ ] **Step 4: Save the passing scene only if transforms remain official**

Save As `F3_calibration_pass_0713.factoryio`, then compare object count and StackerCrane/LoadingConveyor/Rack transforms against G0. Copy it into `l2_factoryio/scenes/` only when transform verdict is unchanged.

- [ ] **Step 5: Update the overnight ledger without overstating scope**

If 9/9 PASS, mark F3 as “Python 直控技术预演物理门通过”; explicitly retain “非 AC500/PLC 闭环、非 400 格物理孪生”. If any run fails, F3 remains red and the ledger names the failed gate and evidence.

- [ ] **Step 6: Commit and push the final verdict**

```powershell
git add -- l2_factoryio/f3_stacker_control.py l2_factoryio/test_f3_stacker_control.py l2_factoryio/records/F3_layered_calibration_0713.md docs/overnight2-report_0712night.md
git add -- l2_factoryio/scenes/F3_calibration_pass_0713.factoryio
git diff --cached --check
git commit -m "F3验收:完成分层校准与9次物理证据"
git push origin master
```

If final status is FAIL, omit the scene file and use commit message `F3验收:落档分层校准失败证据`.

## Task 9: Resume the Deferred C Path Only After F3 PASS

**Files:**
- Update later under a separate plan: `l2_factoryio/task_orchestrator.py`
- Create later under a separate plan: `l2_factoryio/3b_ab_opcua_实验记录.md`
- Update later under a separate plan: self-developed 3D event replay consumer

- [ ] **Step 1: Verify F3 is actually green**

Required evidence: G0–G4 explicit PASS, 9/9 representative-cell runs, offline regressions green, outputs stopped.

- [ ] **Step 2: Close Factory I/O before AB OPC UA experiments**

Do not run Factory I/O and Automation Builder GUI automation concurrently. Start F4/F5 from the existing C-path design in a new implementation plan.

- [ ] **Step 3: Preserve scope labels**

Factory I/O remains “Python 直控技术预演”; AB remains the 20×20 business truth source; self-developed 3D replays the same task events and does not claim physical Factory I/O 400-cell equivalence.
