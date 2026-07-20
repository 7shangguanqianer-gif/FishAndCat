import assert from "node:assert/strict";
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import vm from "node:vm";
import {createRequire} from "node:module";
import {fileURLToPath} from "node:url";

const require = createRequire(import.meta.url);
const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const runtimePath = path.join(projectRoot, "l4_showcase", "src", "s3_ac_runtime.js");
const htmlPath = path.join(projectRoot, "l4_showcase", "src", "archive_候选历史", "样张_S3_三方向候选.html");
const traceRoot = path.join(projectRoot, "l4_showcase", "out", "s3_traces");
const comparisonEvidencePath = path.join(projectRoot, "l4_showcase", "out", "s1_comparison_evidence.js");
const comparisonCanonicalPath = path.join(projectRoot, "l4_showcase", "out", "s1_comparison_evidence.canonical.json");
const runtime = require(runtimePath);

function sha256File(filename) {
  return crypto.createHash("sha256").update(fs.readFileSync(filename)).digest("hex");
}

function loadComparisonEvidence() {
  const sandbox = {window: {}};
  vm.runInNewContext(fs.readFileSync(comparisonEvidencePath, "utf8"), sandbox, {filename: comparisonEvidencePath});
  assert(sandbox.window.S3_COMPARISON_EVIDENCE, "S1 comparison bundle did not register evidence");
  return sandbox.window.S3_COMPARISON_EVIDENCE;
}

const comparisonEvidence = loadComparisonEvidence();

function loadTrace(filename) {
  let registeredId = null, payload = null;
  const sandbox = {window: {__S3_TRACE_REGISTER__(traceId, trace) { registeredId = traceId; payload = trace; }}};
  vm.runInNewContext(fs.readFileSync(path.join(traceRoot, filename), "utf8"), sandbox, {filename});
  assert(payload, `${filename} did not register a payload`);
  assert.equal(registeredId, payload.meta.trace_id);
  return payload;
}

const traceFiles = fs.readdirSync(traceRoot).filter(name => name.endsWith(".js")).sort();
const traces = new Map(traceFiles.map(filename => [path.basename(filename, ".js"), loadTrace(filename)]));
const visualGeometry = Object.freeze({
  io: {x: .5, y: -.75},
  transfer: {x: .5, y: -.75, z: .55},
  infeed: {x: -.45, entryY: -5.15, loadY: -1.65, z: .55, width: 1.02},
  outfeed: {x: 1.45, startY: -1.65, scanY: -2.80, maskY: -3.95, endY: -5.15, z: .55, width: 1.02},
  infeedEnvelope: {xMin: -1.04, xMax: .14, yMin: -5.20, yMax: -1.60},
  outfeedEnvelope: {xMin: .86, xMax: 2.04, yMin: -5.20, yMax: -1.60},
  cargoZOffset: .05, cargoDrop: .055, cargoReach: 1.25, rackLoadY: .50
});

function groupElapsed(timeline, cycleIndex, phase, progress) {
  const group = timeline.groupsByKey.get(`${cycleIndex}|${phase}`);
  assert(group, `missing group ${cycleIndex}/${phase}`);
  return group.d0 + (group.d1 - group.d0) * progress;
}

function keyRows(rows) {
  return Array.from(rows, row => `${row.gid}:${row.col}/${row.tier}`).sort();
}

function deferred() {
  let resolve, reject;
  const promise = new Promise((ok, fail) => { resolve = ok; reject = fail; });
  return {promise, resolve, reject};
}

test("Task7 S1 comparison evidence is source-bound, complete and isolated from S3 playback", () => {
  assert.equal(runtime.validateComparisonEvidence(comparisonEvidence), true);
  assert.equal(comparisonEvidence.rows.length, 18 * 8);
  assert.equal(new Set(comparisonEvidence.rows.map(row => `${row.scenario}/${row.mode}`)).size, 18 * 8);

  const expectedHashes = {
    aggregate_csv: sha256File(path.join(projectRoot, "sim", "out", "cargo_dynamic_matrix", "s1", "cargo_dynamic_matrix_agg.csv")),
    params_csv: sha256File(path.join(projectRoot, "sim", "out", "cargo_dynamic_matrix", "s1", "cargo_dynamic_matrix_params.csv")),
    matrix_manifest_json: sha256File(path.join(projectRoot, "sim", "out", "cargo_dynamic_matrix", "s1", "cargo_dynamic_matrix_manifest.json")),
    generator: sha256File(path.join(projectRoot, "l4_showcase", "tools", "generate_s1_comparison_evidence.py"))
  };
  assert.deepEqual(JSON.parse(JSON.stringify(comparisonEvidence.source_hashes)), expectedHashes);

  const bundlePayload = JSON.parse(JSON.stringify(comparisonEvidence));
  const recordedPayloadHash = bundlePayload.payload_sha256;
  delete bundlePayload.payload_sha256;
  const canonicalBytes = fs.readFileSync(comparisonCanonicalPath);
  assert.equal(crypto.createHash("sha256").update(canonicalBytes).digest("hex"), recordedPayloadHash);
  assert.deepEqual(JSON.parse(canonicalBytes.toString("utf8")), bundlePayload);

  const e15 = comparisonEvidence.scenarios.find(item => item.id === "E15");
  assert.deepEqual(
    {extended_pressure: e15.extended_pressure, canonical_g2: e15.canonical_g2, headline_eligible: e15.headline_eligible},
    {extended_pressure: true, canonical_g2: false, headline_eligible: false}
  );
  assert.equal(e15.title, "扩展 Tier 3 压力情景（非 canonical G2、非 H）");
  assert.equal(comparisonEvidence.purpose, "controlled-comparison-only; never merge with representative S3 playback");
  for (const trace of traces.values()) {
    assert.equal(trace.comparability.s1_matrix_same_parameterization, false);
    assert.equal(trace.comparability.ui_rule, "do_not_compare_or_merge");
  }
});

test("Task7 comparison selectors preserve the controlled matrix axes and row order", () => {
  const scenarioRows = runtime.selectComparisonEvidence(comparisonEvidence, "scenario", "E02");
  assert.deepEqual(Array.from(scenarioRows, row => row.mode), ["random", "seq", "near", "score", "awra", "cb", "tob", "AUTO"]);
  assert(scenarioRows.every(row => row.scenario === "E02"));

  const modeRows = runtime.selectComparisonEvidence(comparisonEvidence, "mode", "AUTO");
  assert.deepEqual(Array.from(modeRows, row => row.scenario), Array.from(comparisonEvidence.scenarios, item => item.id));
  assert(modeRows.every(row => row.mode === "AUTO"));
  assert.throws(() => runtime.selectComparisonEvidence(comparisonEvidence, "scenario", "E99"), /未知 S1 情景/);
  assert.throws(() => runtime.selectComparisonEvidence(comparisonEvidence, "mode", "oracle"), /未知 S1 对照轴/);
});

test("Task12 mini comparison discloses its 4-of-8 scope and critical drawer copy stays at 9px", () => {
  const html = fs.readFileSync(htmlPath, "utf8"), source = fs.readFileSync(runtimePath, "utf8");
  for (const token of ["当前 4 / 完整 8", "10 seeds · SIM", "其余路由见完整对照", "查看完整对照"]) {
    assert.ok(source.includes(token), `迷你对比范围披露缺少 ${token}`);
  }
  assert.match(html, /\.comparisonBodyRow small\{[^}]*font-size:9px/);
  assert.match(html, /#comparisonFoot\{[^}]*font-size:9px/);
  assert.doesNotMatch(html, /\.comparisonRow>div\{[^}]*font-size:8\.5px/);
});

test("45 traces build one complete 100-cycle × 7-step timeline", () => {
  assert.equal(traceFiles.length, 45);
  for (const [traceId, trace] of traces) {
    const timeline = runtime.buildTimeline(trace);
    assert.equal(timeline.traceId, traceId);
    assert.equal(timeline.groups.length, 700);
    assert.equal(timeline.groupsByKey.size, 700);
    assert(timeline.total > 0);
    assert.equal(runtime.deriveFrame(trace, timeline, 0).cycleIndex, 0);
    assert.deepEqual(new Set(timeline.groups.map(group => group.operationKey)), new Set(runtime.PROCESS_STEPS));
  }
});

test("Task6 presentation floors keep short real-motion legs visible and end every cycle with CONSUMED hold", () => {
  for (const [traceId, trace] of traces) {
    const timeline = runtime.buildTimeline(trace);
    for (const group of timeline.groups) {
      const duration = group.d1 - group.d0;
      if (["INBOUND_TRAVEL", "LINK_TRAVEL", "OUTBOUND_TRAVEL"].includes(group.operationKey)) {
        assert(duration >= runtime.MIN_TRAVEL_DISPLAY_S - 1e-9, `${traceId}/${group.cycleIndex}/${group.operationKey} too fast`);
      }
      if (["STORE_HANDLE", "RETRIEVE_HANDLE"].includes(group.operationKey)) {
        assert(duration >= runtime.MIN_HANDLE_DISPLAY_S - 1e-9, `${traceId}/${group.cycleIndex}/${group.operationKey} too fast`);
      }
    }
    for (let cycleIndex = 0; cycleIndex < 100; cycleIndex += 1) {
      const tail = timeline.segments.filter(segment => segment.cycleIndex === cycleIndex && segment.operationKey === "SCAN_EXIT");
      assert.deepEqual(tail.map(segment => segment.phaseName), ["OUTFEED", "SCANNED", "EXIT_MASK", "CONSUMED"]);
      assert(Math.abs((tail.at(-1).d1 - tail.at(-1).d0) - runtime.CONSUMED_HOLD_S) < 1e-9);
      const consumedFrame = runtime.deriveFrame(trace, timeline, (tail.at(-1).d0 + tail.at(-1).d1) / 2);
      assert.equal(consumedFrame.cargoOwner, "CONSUMED");
      assert.equal(runtime.ownershipSnapshot(consumedFrame).unique, true);
      assert.deepEqual(keyRows(consumedFrame.inventoryRows), keyRows(trace.inventory_snapshots[cycleIndex + 1]));
    }
  }
});

test("Task16 phase-aware presentation timing is monotone, bounded and excluded from SIM evidence", () => {
  const travel = new Set(["INBOUND_TRAVEL", "LINK_TRAVEL", "OUTBOUND_TRAVEL"]);
  for (const [traceId, trace] of traces) {
    const timeline = runtime.buildTimeline(trace);
    for (const operationKey of travel) {
      const groups = timeline.groups.filter(group => group.operationKey === operationKey)
        .sort((a, b) => a.simDurationS - b.simDurationS || a.presentationDurationS - b.presentationDurationS);
      for (let index = 1; index < groups.length; index += 1) {
        if (groups[index].simDurationS > groups[index - 1].simDurationS + 1e-9) {
          assert(groups[index].presentationDurationS + 1e-9 >= groups[index - 1].presentationDurationS,
            `${traceId}/${operationKey} presentation mapping is not monotone`);
        }
      }
    }
    for (const group of timeline.groups) {
      const segments = timeline.segments.filter(segment => segment.cycleIndex === group.cycleIndex && segment.operationKey === group.operationKey);
      const modelled = segments.reduce((sum, segment) => sum + (segment.simModelled === false ? 0 : Math.max(0, segment.simT1 - segment.simT0)), 0);
      assert(Math.abs(modelled - group.simDurationS) < 1e-9, `${traceId}/${group.cycleIndex}/${group.operationKey} SIM duration polluted by presentation-only segment`);
      assert(Math.abs(group.wallSecondsAt1x - group.presentationDurationS / runtime.DEFAULT_PLAYBACK_SCALE) < 1e-9);
    }
  }
  const reference = runtime.buildTimeline(traces.get("t3_skew_auto"));
  const longestLoaded = reference.groups.filter(group => ["INBOUND_TRAVEL", "OUTBOUND_TRAVEL"].includes(group.operationKey))
    .sort((a, b) => b.simDurationS - a.simDurationS)[0];
  assert(longestLoaded.presentationDurationS >= runtime.PRESENTATION_TIMING.loadHandoff - 1e-9);
  assert(longestLoaded.presentationDurationS >= Math.max(runtime.PRESENTATION_TIMING.outfeed,
    runtime.PRESENTATION_TIMING.scanned, runtime.PRESENTATION_TIMING.exitMask) - 1e-9);
  const frame = runtime.deriveFrame(traces.get("t3_skew_auto"), reference, groupElapsed(reference, 20, "LOAD_IN", .5));
  assert.deepEqual(Array.from(frame.cycleTiming, item => item.operationKey), Array.from(runtime.PROCESS_STEPS));
  assert.equal(frame.cycleTiming.length, 7);
  assert.equal(frame.timing.presentationOnlyDurationS,
    reference.groupsByKey.get("20|LOAD_IN").presentationOnlyDurationS);
  const source = fs.readFileSync(runtimePath, "utf8"), html = fs.readFileSync(htmlPath, "utf8");
  /* 0719 去重复批次:meta 不再复述本步 SIM 数值(「排队 SIM x.x s」→「排队+交接 · SIM 见七步条」) */
  for (const token of ["phaseTimeScale", "phaseTimeCursor", "1=排队/交接", "QUEUE_LABEL", "排队+交接", "交接展示"]) {
    assert(source.includes(token) || html.includes(token), `real-time phase disclosure missing ${token}`);
  }
});

test("checkpoint projection preserves seed, cycle, phase and progress across all 45 traces", () => {
  const source = traces.get("t3_skew_auto"), sourceTimeline = runtime.buildTimeline(source);
  const sourceElapsed = groupElapsed(sourceTimeline, 47, "RETRIEVE_HANDLE", .63);
  const checkpoint = runtime.checkpointAt(sourceTimeline, sourceElapsed);
  assert.deepEqual({seed: checkpoint.seed, cycleIndex: checkpoint.cycleIndex, phase: checkpoint.phase}, {seed: 2026, cycleIndex: 47, phase: "RETRIEVE_HANDLE"});
  assert(Math.abs(checkpoint.progress - .63) < 1e-10);
  for (const trace of traces.values()) {
    const timeline = runtime.buildTimeline(trace);
    const projected = runtime.elapsedForCheckpoint(timeline, checkpoint);
    const roundTrip = runtime.checkpointAt(timeline, projected);
    assert.equal(roundTrip.seed, checkpoint.seed);
    assert.equal(roundTrip.cycleIndex, 47);
    assert.equal(roundTrip.phase, "RETRIEVE_HANDLE");
    assert(Math.abs(roundTrip.progress - .63) < 1e-9);
  }
});

test("fault checkpoint projects to the underlying operation when target trace has no fault", () => {
  const source = traces.get("t3_skew_auto"), sourceTimeline = runtime.buildTimeline(source);
  const fault = sourceTimeline.segments.find(segment => segment.phaseName === "FAULT_RECOVERY");
  assert(fault);
  const checkpoint = runtime.checkpointAt(sourceTimeline, (fault.d0 + fault.d1) / 2);
  assert.equal(checkpoint.phase, fault.effectiveName);
  const target = traces.get("t1_skew_seq"), targetTimeline = runtime.buildTimeline(target);
  assert(!targetTimeline.segments.some(segment => segment.phaseName === "FAULT_RECOVERY"));
  const projected = runtime.checkpointAt(targetTimeline, runtime.elapsedForCheckpoint(targetTimeline, checkpoint));
  assert.equal(projected.cycleIndex, checkpoint.cycleIndex);
  assert.equal(projected.phase, checkpoint.phase);
  assert(Math.abs(projected.progress - checkpoint.progress) < 1e-9);
});

test("inventory frames use the selected trace snapshots and never duplicate gid or slot", () => {
  for (const traceId of ["t1_uniform_seq", "t2_heavy_awra", "t3_skew_auto"]) {
    const trace = traces.get(traceId), timeline = runtime.buildTimeline(trace);
    for (const phase of runtime.PROCESS_STEPS) {
      const frame = runtime.deriveFrame(trace, timeline, groupElapsed(timeline, 38, phase, .5));
      const gids = new Set(frame.inventoryRows.map(row => row.gid));
      const slots = new Set(frame.inventoryRows.map(row => `${row.col}/${row.tier}`));
      assert.equal(gids.size, frame.inventoryRows.length, `${traceId}/${phase} duplicate gid`);
      assert.equal(slots.size, frame.inventoryRows.length, `${traceId}/${phase} duplicate slot`);
      if (["LINK_TRAVEL"].includes(phase)) assert.equal(frame.inventoryRows.length, 121);
      else assert.equal(frame.inventoryRows.length, 120);
    }
  }
  const left = traces.get("t3_skew_auto"), right = traces.get("t3_heavy_seq");
  const checkpoint = runtime.checkpointAt(runtime.buildTimeline(left), groupElapsed(runtime.buildTimeline(left), 62, "OUTBOUND_TRAVEL", .4));
  const rightTimeline = runtime.buildTimeline(right);
  const rightFrame = runtime.deriveFrame(right, rightTimeline, runtime.elapsedForCheckpoint(rightTimeline, checkpoint));
  assert.deepEqual(keyRows(rightFrame.inventoryRows), keyRows(right.inventory_snapshots[63]));
  assert.notDeepEqual(keyRows(rightFrame.inventoryRows), keyRows(left.inventory_snapshots[63]));
});

test("reconcile removes prior-trace state and converges exactly to target rows", () => {
  const source = traces.get("t3_skew_auto").inventory_snapshots[50];
  const target = traces.get("t3_heavy_seq").inventory_snapshots[50];
  const current = new Map();
  runtime.reconcileInventoryMap(current, source);
  runtime.reconcileInventoryMap(current, target, {
    create: row => ({...row}),
    update: (value, row) => Object.assign(value, row)
  });
  assert.equal(current.size, 120);
  assert.deepEqual(keyRows(Array.from(current.values())), keyRows(target));
  for (let loop = 0; loop < 20; loop += 1) {
    runtime.reconcileInventoryMap(current, target, {update: (value, row) => Object.assign(value, row)});
    assert.equal(current.size, 120);
  }
});

test("latest-only selection ignores A/B after C and emits no stale commit or stale error", async () => {
  const pending = new Map([["A", deferred()], ["B", deferred()], ["C", deferred()]]);
  const commits = [], errors = [], loading = [];
  const loader = runtime.createLatestOnlyLoader({
    load: query => pending.get(query).promise,
    prepare: async payload => ({payload}),
    commit: prepared => commits.push(prepared.payload),
    onError: error => errors.push(error.message),
    onLoading: (value, query) => loading.push(`${query}:${value}`)
  });
  const a = loader.select("A"), b = loader.select("B"), c = loader.select("C");
  pending.get("B").resolve("payload-B"); await Promise.resolve();
  pending.get("A").reject(new Error("stale A failure")); await Promise.resolve();
  pending.get("C").resolve("payload-C");
  const results = await Promise.all([a, b, c]);
  assert.deepEqual(results.map(result => result.status), ["stale", "stale", "committed"]);
  assert.deepEqual(commits, ["payload-C"]);
  assert.deepEqual(errors, []);
  assert.equal(loading.at(-1), "C:false");
  assert.equal(loader.snapshot().staleCount, 2);
});

test("destroy invalidates an inflight selection before prepare or commit", async () => {
  const pending = deferred(), commits = [], prepares = [];
  const loader = runtime.createLatestOnlyLoader({
    load: () => pending.promise,
    prepare: value => { prepares.push(value); return value; },
    commit: value => commits.push(value)
  });
  const request = loader.select("D"); loader.destroy(); pending.resolve("payload-D");
  const result = await request;
  assert.equal(result.status, "stale");
  assert.deepEqual(prepares, []); assert.deepEqual(commits, []);
  assert.equal(loader.snapshot().destroyed, true);
});

test("20-loop logical advance does not reset to cycle zero", () => {
  const trace = traces.get("t3_skew_auto"), timeline = runtime.buildTimeline(trace);
  const elapsed = groupElapsed(timeline, 73, "LINK_TRAVEL", .41) + timeline.total * 20;
  const checkpoint = runtime.checkpointAt(timeline, elapsed);
  assert.equal(checkpoint.loop, 20);
  assert.equal(checkpoint.cycleIndex, 73);
  assert.equal(checkpoint.phase, "LINK_TRAVEL");
  assert(Math.abs(checkpoint.progress - .41) < 1e-9);
});

test("HTML and runtime expose one view, one RAF source and no retired business state", () => {
  const html = fs.readFileSync(htmlPath, "utf8"), body = html.slice(html.indexOf("<body>"));
  const runtimeSource = fs.readFileSync(runtimePath, "utf8");
  for (const retired of ['id="modebar"', 'id="dataView"', "S3_AC_ACTIVE", "S3_TIER3_TRACE", "G016", "15 / 04", "const TARGET", "const goods", "staticStockMeshes", "staticQueueMeshes"]) {
    assert(!body.includes(retired), `retired state remains: ${retired}`);
  }
  assert(body.includes("targetBox.visible=false"), "cold start targetBox must be hidden");
  assert(body.includes("targetPad.visible=false"), "cold start targetPad must be hidden");
  assert(!html.includes("requestAnimationFrame"), "HTML must not own a RAF loop");
  assert.equal((runtimeSource.match(/requestAnimationFrame/g) || []).length, 1);
  assert.equal((runtimeSource.match(/root\.__S3_QA\s*=/g) || []).length, 1);
  for (const id of ["strategySelect", "tierSelect", "profileSelect", "pauseMotion", "replayTrace", "traceErrorHost"]) assert(body.includes(`id="${id}"`));
  for (const retired of ["algorithm_proof", ".jobs", ".candidates"]) assert(!runtimeSource.includes(retired));
});

test("Task10 rail uses current-trace facts and accessible definitions without a second state source", () => {
  const html = fs.readFileSync(htmlPath, "utf8"), runtimeSource = fs.readFileSync(runtimePath, "utf8");
  for (const token of ["insightStack.id='insightStack'", "traceStats.id='traceStats'", 'id="phaseNow"', "grid-template-areas:\"head head\""]) {
    assert(html.includes(token), `Task10 HTML token missing: ${token}`);
  }
  for (const token of ['judgePath.id = "judgePath"', 'byId("judgeRoute")', 'byId("judgeAction")', 'byId("judgeEvidence")', 'S3 单 seed · 故障']) {
    assert.ok(runtimeSource.includes(token), `Task10 同源证据链缺少 ${token}`);
  }
  for (const token of [
    "function metricChip", 'button.type = "button"', 'tip.setAttribute("role", "tooltip")',
    'button.setAttribute("aria-describedby"', 'event.key !== "Escape"', "function renderTraceStats",
    "stats.response_p50_s", "stats.response_p95_s", "stats.utilization", "stats.queue_peak_waiting",
    "stats.faults", "stats.violations", "trace.meta.score_weights && trace.meta.score_weights.online",
    "当前 trace；不与 S1 多 seed 聚合合并", "本链不调用四项候选位评分函数",
    "权重，不是本周期分值", "AUTO 路由额外策略", "insight.prepend(queue)",
    'advanced.className = "decisionAdvanced"', 'advancedBody.className = "advancedBody"',
    'const shown3d = gids.slice(0, 4), shownRail = gids.slice(0, 2)'
  ]) assert(runtimeSource.includes(token), `Task10 runtime token missing: ${token}`);
  assert(!runtimeSource.includes("stats.multi_seed_source"), "single-trace UI must not read S1 evidence");
  assert(!runtimeSource.includes("setInterval"), "Task10 must not add a second timer");
});

test("Task8 keyboard, live-region and reduced-motion contracts are explicit", () => {
  const html = fs.readFileSync(htmlPath, "utf8"), runtimeSource = fs.readFileSync(runtimePath, "utf8");
  for (const token of [
    'id="runtimeControls" aria-label="仿真回放选择" aria-busy="false"',
    'id="traceLoadState" role="status" aria-live="polite" aria-atomic="true"',
    'id="traceErrorHost" role="alert" aria-live="assertive" aria-atomic="true"',
    '@media(prefers-reduced-motion:reduce)', '#sceneTools input[type="range"]{width:100%;min-height:24px'
  ]) assert(html.includes(token), `Task8 HTML token missing: ${token}`);
  for (const token of [
    'comparisonLab.setAttribute("aria-describedby", "comparisonFoot")',
    'aria-controls="comparisonTable" tabindex="0"', 'aria-controls="comparisonTable" tabindex="-1"',
    'function setComparisonInert', 'function comparisonFocusables', 'event.key !== "Tab"',
    '["ArrowLeft", "ArrowRight", "Home", "End"]', 'element.inert = true',
    'byId("runtimeControls").setAttribute("aria-busy"'
  ]) assert(runtimeSource.includes(token), `Task8 runtime token missing: ${token}`);
});

test("Task9 delivery resources are local-only and the supported viewport floor is explicit", () => {
  const html = fs.readFileSync(htmlPath, "utf8"), runtimeSource = fs.readFileSync(runtimePath, "utf8");
  const storeSource = fs.readFileSync(path.join(projectRoot, "l4_showcase", "src", "s3_trace_store.js"), "utf8");
  const resourceRefs = Array.from(html.matchAll(/<(?:script|link)\b[^>]+(?:src|href)="([^"]+)"/g), match => match[1]);
  assert.deepEqual(resourceRefs, [
    "./lib/three.min.js", "./lib/OrbitControls.js", "../out/s3_trace_manifest.js",
    "../out/s1_comparison_evidence.js", "./s3_trace_store.js", "./s3_ac_runtime.js"
  ]);
  assert(resourceRefs.every(reference => !/^(?:https?:)?\/\//i.test(reference)), "delivery resource must not use network origin");
  assert(html.includes("html,body{min-width:1280px;min-height:720px"), "tested 1280x720 viewport floor must remain explicit");
  assert(!runtimeSource.includes("fetch("));
  assert(!storeSource.includes("fetch("));
  assert(storeSource.includes("new URL(entry.file, this.baseUrl).href"), "trace URLs must derive from the local manifest base");
});

test("Task12 single-rack dual-station scene, adjustable camera and compact ABB console are explicit", () => {
  const html = fs.readFileSync(htmlPath, "utf8"), runtimeSource = fs.readFileSync(runtimePath, "utf8");
  for (const token of [
    "pos:[30.0,-40.0,22.5]", "look:[9.35,-1.25,9.20]", "fov:32.4",
    "const INFEED=Object.freeze", "const OUTFEED=Object.freeze", "logicalOrigin:[0,0]", "visualOnly:true", "singleRackFace:true",
    "entryGate.name='entryGate'", "loadSign.name='loadStation'", "unloadSign.name='unloadStation'",
    "scannerGate.name='scannerGate'", "exitCurtain.name='exitCurtain'", "INFEED/OUTFEED 仅把 Factory I/O 的 Entry→Load、Unload→Exit 物理工位可视化；不进入 sim/KPI",
    "addFloorFlowLabel('入库  →'", "addFloorFlowLabel('→  出库'",
    "sceneTelemetry.id='sceneTelemetry'", "sceneTools.id='sceneTools'", "id=\"playbackSpeed\"", "labelLeaders.id='labelLeaders'",
    "controls.enabled=true", "controls.enablePan=true", "controls.minDistance=15", "controls.maxDistance=56",
    "controls.minAzimuthAngle=THREE.MathUtils.degToRad(-65)", "controls.maxAzimuthAngle=THREE.MathUtils.degToRad(65)",
    "const RACK=Object.freeze({frontY:0,backY:.95,backPanelY:1.005,depth:.95,loadY:.50,baseY:.40})",
    "addBox(N,.11,N,N/2,RACK.backPanelY,N/2,M.rackBack,true,true)", "addInstances(N,RACK.depth,.06",
    "addSegmentInstances(braceSegments,.026,M.rackBrace)",
    "grid-template-areas:\"head head\" \"task task\" \"controls controls\" \"decision decision\" \"map insight\" \"phase insight\"",
    "const FLOOR={x0:-7.5,x1:N+3,y0:-8.65,y1:7.15}", "const stationCollisionSolids=[]", "'ENTRY_BEAM'"
  ]) assert(html.includes(token), `Task12 HTML token missing: ${token}`);
  assert(!html.includes("controls.enabled=false"), "manual camera must not be disabled");
  assert.equal((html.match(/id="resetCamera"/g) || []).length, 1, "one camera preset button required");
  assert.match(runtimeSource, /function refreshProjection\(\)[\s\S]*layoutProjectedLabels\(lastFrame\)/,
    "camera-only movement must refresh projected labels from the current business frame");
  assert.match(runtimeSource, /listen\(controls,\s*"change",[\s\S]*rendererBridge\.refreshProjection\(\)/,
    "OrbitControls change must drive label reprojection even while paused");
  assert.match(runtimeSource, /function hideLeader\(id\)[\s\S]*line\.style\.display\s*=\s*"none"/,
    "hidden SVG leaders must use explicit display:none to avoid orphan line fragments");
  assert.match(runtimeSource, /function collisionSnapshot\([^)]*\)[\s\S]*stationCollisionSolids[\s\S]*floorBreaches/,
    "browser QA must expose active/queued cargo AABB collisions against registered hard station solids");
  assert.match(runtimeSource, /collisionGeometry\(\)\s*\{\s*return rendererBridge\.collisionSnapshot\(true\)/,
    "browser QA hook must expose actor/solid boxes for swept-volume verification");
  for (const token of [
    "validateVisualTopology", "ownershipSnapshot", "chooseLabelPairLayout", "layoutProjectedLabels", "layoutStationTags",
    'parent: cargo.parent === scene ? "scene"', "infeed: {x: INFEED.x", "outfeed: {x: OUTFEED.x",
    'g.strokeStyle = "#e7b800"', 'line.setAttribute("points"', "chooseLeaderRoute", "routePlacedLeaders",
    "leaderObstacleHits", "leaderCrossings", "maxLeaderLength",
    "seek(cycleIndex, operationKey, progress = .5)", 'state.paused = true',
    "function handleCargoDrop", "forkDrop = handleCargoDrop(frame.operationKey, p, CARGO_DROP)",
    "function cargoWorldPosition", "cargoWorldPosition(frame, machineWorld", "setPlaybackMultiplier", "effectivePlaybackScale", 'byId("sceneActionText").textContent',
    'scope: "active_queue_cargo_vs_station_solids_each_other_and_floor"'
  ]) assert(runtimeSource.includes(token), `Task12 runtime token missing: ${token}`);
  for (const token of ["applyOperationDisplayFloor", "CONSUMED_HOLD_S", 'phaseName: "CONSUMED"', "LOOP_RESET_MASK_S", 'loopMask.classList.toggle("is-visible"', 'CONSUMED: "闭环完成"']) {
    assert(runtimeSource.includes(token), `Task6 lifecycle token missing: ${token}`);
  }
  for (const token of ["function projectWorldBox", "function unionScreenProjections", "function compositionSnapshot", "visibleSubject", "maxQueuePressure", "queueVisibleCount", "targetWidthRatio: [.65, .85]", "composition: compositionSnapshot()", "composition() { return rendererBridge.compositionSnapshot(); }"]) {
    assert(runtimeSource.includes(token), `Task4 composition QA token missing: ${token}`);
  }
  assert.equal((html.match(/partFaceLabel\(entryGate,'入'/g) || []).length, 1);
  assert.equal((html.match(/partFaceLabel\(loadSign,'装'/g) || []).length, 1);
  assert.equal((html.match(/partFaceLabel\(unloadSign,'卸'/g) || []).length, 1);
  assert.equal((html.match(/partFaceLabel\(scannerGate,'扫'/g) || []).length, 1);
  assert.equal((html.match(/partFaceLabel\(exitCurtain,'出'/g) || []).length, 1);
  for (const retired of ["activeLoadBeacon", "infeedTag", "outfeedTag", "cargoLeader", "infeedLeader", "outfeedLeader"]) {
    assert(!html.includes(`${retired}.id='${retired}'`), `retired floating label remains: ${retired}`);
  }
});

test("Task13 restores the formal single-deep rack and prevents information-dead side views", () => {
  const html = fs.readFileSync(htmlPath, "utf8"), runtimeSource = fs.readFileSync(runtimePath, "utf8");
  assert.match(html, /const RACK=Object\.freeze\(\{frontY:0,backY:\.95,backPanelY:1\.005,depth:\.95,loadY:\.50,baseY:\.40\}\)/);
  assert.match(html, /addBox\(N\+\.6,1\.40,\.50,N\/2,RACK\.baseY,Z0\+\.25,M\.plinth,true,true\)/);
  assert.match(html, /addInstances\(N,RACK\.depth,\.06,[\s\S]*M\.body,true,true\)/);
  assert.match(html, /addInstances\(\.06,RACK\.depth,N,[\s\S]*M\.body,true,true\)/);
  assert.match(html, /addSegmentInstances\(braceSegments,\.026,M\.rackBrace\)/);
  assert.match(html, /controls\.minAzimuthAngle=THREE\.MathUtils\.degToRad\(-65\);controls\.maxAzimuthAngle=THREE\.MathUtils\.degToRad\(65\)/);
  assert.match(html, /frontality:-dy\/planar/);
  assert.match(runtimeSource, /new THREE\.BoxGeometry\(\.70, \.72, \.58\)/);
  assert.match(runtimeSource, /new THREE\.BoxGeometry\(\.74, \.76, \.10\)/);
  assert.match(runtimeSource, /stockDummy\.position\.set\(row\.col \+ \.5, RACK\.loadY, row\.tier \+ \.43\)/);
  assert.match(runtimeSource, /new THREE\.Vector3\(N \+ \.35, 1\.10, N \+ \.20\)/);
  assert.equal((html.match(/singleRackFace:true/g) || []).length, 1, "rack depth must not create a second logical rack face");
});

test("Task16 the sole target leader routes around boxes without retired cargo/station beacons", () => {
  const rect = {left: 100, top: 100, right: 200, bottom: 150, width: 100, height: 50};
  const obstacle = {left: 40, top: 110, right: 80, bottom: 130};
  const route = runtime.chooseLeaderRoute({x: 20, y: 120}, rect, [obstacle], []);
  assert.equal(route.obstacleHits, 0, `leader should route around obstacle: ${JSON.stringify(route)}`);
  assert(route.points.length >= 2 && route.length > 0);
  assert.equal(runtime.segmentIntersectsRect({x: 0, y: 0}, {x: 20, y: 20}, {left: 8, top: 8, right: 12, bottom: 12}), true);
  assert.equal(runtime.segmentIntersectsRect({x: 0, y: 0}, {x: 20, y: 0}, {left: 8, top: 8, right: 12, bottom: 12}), false);
  const runtimeSource = fs.readFileSync(runtimePath, "utf8"), html = fs.readFileSync(htmlPath, "utf8");
  assert.match(runtimeSource, /line\.setAttribute\("points", route\.points/);
  assert.match(runtimeSource, /leaderObstacleHits:[\s\S]*leaderCrossings:[\s\S]*maxLeaderLength:/);
  assert.match(html, /createElementNS\('http:\/\/www\.w3\.org\/2000\/svg','polyline'\)/);
  assert.match(runtimeSource, /definitions\.push\(\{id: "targetBeacon"/);
  assert(!runtimeSource.includes('byId("activeLoadBeacon")'));
});

test("Task14 unifies fixed scene information into one Chinese-first bottom evidence dock", () => {
  const html = fs.readFileSync(htmlPath, "utf8"), body = html.slice(html.indexOf("<body>"));
  const runtimeSource = fs.readFileSync(runtimePath, "utf8");
  for (const token of [
    "sceneDock.id='sceneDock'", "sceneDock.append(sceneCaption)", "sceneDock.append(sceneTelemetry)",
    "sceneCaption.append(reserveRuleBadge)", "sceneDock.append(sceneTools)",
    "当前作业", "setAttribute('aria-label','设备运动')", "入库", "空载", "出库", "预占", "镜头与演示倍率", "不改 SIM / KPI",
    "grid-template-columns:minmax(260px,1.38fr) minmax(220px,1fr) minmax(180px,.82fr)"
  ]) assert(body.includes(token) || html.includes(token), `Task14 dock token missing: ${token}`);
  for (const retired of ["MOTION TELEMETRY", "SCENE CONTROL", "LIVE AXIS", "OPERATOR CONSOLE", "VERIFIED SIM TRACE"]) {
    assert(!body.includes(retired), `Task14 decorative English remains: ${retired}`);
  }
  assert.equal((body.match(/\(列 \+ 层\) mod 3 = 0/g) || []).length, 1, "reserve formula must appear once in the left rule map");
  assert.equal((body.match(/133 \/ 400/g) || []).length, 1, "reserve count must appear once in the left rule map");
  assert.match(html, /#taskline\{display:none!important\}/, "top task summary must not duplicate the bottom current-job dock");
  assert.match(runtimeSource, /const fixedObstacles = \["sceneDock", "faultStateBanner"\]/);
  assert.match(runtimeSource, /byId\("sceneActionText"\)\.textContent = cargoGood \?/); /* 0719:货物名并入动作行 */
  assert.match(runtimeSource, /byId\("sceneActionMeta"\)\.textContent =/);
});

test("Task16 stock colors expose snapshot grades and reserved cells fill the rack cavity", () => {
  const html = fs.readFileSync(htmlPath, "utf8"), runtimeSource = fs.readFileSync(runtimePath, "utf8");
  for (const token of ["heavy:0x102a43", "mid:0x006bb6", "light:0x42c7e6", "CELL_FACE=.94", "CELL_BACK_FRONT=.925",
    "availableCellBacks", "reservedCellVolumes", "deriveInstanceBounds", "deriveInstanceBounds(reservedVolumeMesh,RACK.frontY,RACK.backY)",
    "mesh.getMatrixAt(index,matrix)", "failedIndices.push(index)", "reservedInstanceAudit:reservedBounds.perInstance",
    "frontFlushError:Math.abs(reservedMinY-RACK.frontY)", "backFlushError:Math.abs(reservedMaxY-RACK.backY)",
    "actualBoundsDerived:reservedBounds.derivedFromInstanceMatrices"]) {
    assert(html.includes(token), `Task15 stock/rack token missing: ${token}`);
  }
  for (const token of ["stockBodyGeometry", "stockLidGeometry", 'source: "event_inventory_snapshot"', "solidGreenShell: false"]) {
    assert(runtimeSource.includes(token), `Task15 snapshot visual token missing: ${token}`);
  }
  assert(!runtimeSource.includes("stockFrameMesh"), "opaque stock shell must not hide grade colors");
  assert(!runtimeSource.includes("0x2e7d32"), "green stock shell color must be retired");
  assert(!runtimeSource.includes('g.strokeStyle = "#43a047"'), "legacy green per-cell inventory frame must be retired");
  assert.match(runtimeSource, /gradeCssColor\(good\(frame\.cargoGid\)\.grade\)/, "2D moving cargo must reuse the 3D cargo grade color");
  let reserved = 0;
  for (let col = 0; col < 20; col += 1) for (let tier = 0; tier < 20; tier += 1) if ((col + tier) % 3 === 0) reserved += 1;
  assert.equal(reserved, 133);
  assert(html.includes("起始快照 + 周期存取"), "initial stock must be disclosed as a snapshot, not implied to have been replayed from empty");
});

test("Task15 seven-step path plan is complete, finite and aligned with cargo handoffs", () => {
  let checked = 0;
  for (const trace of traces.values()) for (const event of trace.events) {
    const plans = runtime.operationPathPlan(trace, event, visualGeometry);
    assert.deepEqual(Array.from(plans, plan => plan.operationKey), Array.from(runtime.PROCESS_STEPS));
    assert.deepEqual(Array.from(plans, plan => plan.kind), ["cargo-in", "cargo-in", "handle", "empty", "handle", "cargo-out", "cargo-out"]);
    assert(plans.every(plan => plan.points.length >= 3 && plan.points.every(point => [point.x, point.y, point.z].every(Number.isFinite))));
    const [load, inbound, store, link, retrieve, outbound, exit] = plans;
    assert.deepEqual(load.points[0], {x: visualGeometry.infeed.x, y: visualGeometry.infeed.entryY, z: visualGeometry.infeed.z});
    assert.deepEqual(load.points.at(-1), inbound.points[0]);
    assert.deepEqual(retrieve.points.at(-1), outbound.points[0]);
    assert.deepEqual(outbound.points.at(-1), exit.points[0]);
    assert.equal(link.kind, "empty");
    const storeExpected = runtime.cargoWorldPosition(
      {operationKey: "STORE_HANDLE", operationProgress: 1, phaseProgress: 1, cargoOwner: "CARRIER_IN"},
      {worldX: event.store_slot.col + .5, worldZ: event.store_slot.tier + .5}, visualGeometry
    );
    const retrieveExpected = runtime.cargoWorldPosition(
      {operationKey: "RETRIEVE_HANDLE", operationProgress: 1, phaseProgress: 1, cargoOwner: "CARRIER_OUT"},
      {worldX: event.retrieve_slot.col + .5, worldZ: event.retrieve_slot.tier + .5}, visualGeometry
    );
    assert.deepEqual(store.points.at(-1), storeExpected);
    assert.deepEqual(retrieve.points.at(-1), retrieveExpected);
    assert(Math.abs(store.points.at(-1).y - visualGeometry.rackLoadY) <= 1e-12, "stored cargo must end at stock center depth");
    assert(Math.abs(retrieve.points[0].y - visualGeometry.rackLoadY) <= 1e-12, "retrieved cargo must start at stock center depth");
    assert.deepEqual(exit.points.slice(1), [
      {x: visualGeometry.outfeed.x, y: visualGeometry.outfeed.startY, z: visualGeometry.outfeed.z},
      {x: visualGeometry.outfeed.x, y: visualGeometry.outfeed.scanY, z: visualGeometry.outfeed.z},
      {x: visualGeometry.outfeed.x, y: visualGeometry.outfeed.maskY, z: visualGeometry.outfeed.z},
      {x: visualGeometry.outfeed.x, y: visualGeometry.outfeed.endY, z: visualGeometry.outfeed.z}
    ]);
    checked += 1;
  }
  assert.equal(checked, 4500);
});

test("Task11 store/retrieve fork drop tracks cargo support height without penetration", () => {
  const drop = .055, sample = operation => Array.from({length: 101}, (_, index) => runtime.handleCargoDrop(operation, index / 100, drop));
  const store = sample("STORE_HANDLE"), retrieve = sample("RETRIEVE_HANDLE");
  assert.equal(store[0], 0); assert.equal(store[100], drop);
  assert.equal(retrieve[0], drop); assert.equal(retrieve[100], 0);
  for (let index = 1; index < store.length; index += 1) {
    assert(store[index] >= store[index - 1] - 1e-12, `store drop reversed at ${index}`);
    assert(retrieve[index] <= retrieve[index - 1] + 1e-12, `retrieve drop reversed at ${index}`);
  }
  for (const value of store.concat(retrieve)) {
    const cargoBottom = .05 - value - .29;
    const forkTop = -value - .28 + .075 / 2;
    const clearance = cargoBottom - forkTop;
    assert(clearance > .002 && clearance < .003, `fork/cargo support clearance invalid at drop=${value}: ${clearance}`);
  }
  assert(Math.abs((.5 + .05 - drop) - .495) <= 1e-12, "placed cargo must align with rack inventory center");
});

test("Task11 target semantics end at retrieval and fault recovery has an explicit QA state", () => {
  const runtimeSource = fs.readFileSync(runtimePath, "utf8"), htmlSource = fs.readFileSync(htmlPath, "utf8");
  assert.match(runtimeSource, /\["LINK_TRAVEL", "RETRIEVE_HANDLE"\]\.includes\(op\)/);
  assert.doesNotMatch(runtimeSource, /\["LINK_TRAVEL", "RETRIEVE_HANDLE", "OUTBOUND_TRAVEL"\]\.includes\(op\)/);
  for (const token of ["入库目标", "出库源位", "seekFault(faultIndex = 0)", 'faultStateBanner']) {
    assert.ok(runtimeSource.includes(token) || htmlSource.includes(token), `Task11 边界状态缺少 ${token}`);
  }
});

test("Task12 all 4,500 carrier-to-unload boundaries are position-continuous", () => {
  let checked = 0;
  for (const trace of traces.values()) {
    for (const event of trace.events) {
      const outboundMachine = runtime.motionPoint(trace, [event.retrieve_slot.col, event.retrieve_slot.tier], [0, 0], 1);
      const scanMachine = runtime.motionPoint(trace, [0, 0], [0, 0], 0);
      const outbound = runtime.cargoWorldPosition(
        {operationKey: "OUTBOUND_TRAVEL", operationProgress: 1, phaseProgress: 1, cargoOwner: "CARRIER_OUT"},
        {worldX: outboundMachine.x + .5, worldZ: outboundMachine.z + .5}, visualGeometry
      );
      const scan = runtime.cargoWorldPosition(
        {operationKey: "SCAN_EXIT", operationProgress: 0, phaseProgress: 0, cargoOwner: "OUTFEED"},
        {worldX: scanMachine.x + .5, worldZ: scanMachine.z + .5}, visualGeometry
      );
      const distance = Math.hypot(outbound.x - scan.x, outbound.y - scan.y, outbound.z - scan.z);
      assert(distance <= 1e-6, `${trace.meta.trace_id}/cycle=${event.cycle} handoff jump=${distance}`);
      checked += 1;
    }
  }
  assert.equal(checked, 4500);
});

test("Task16 Entry→Load and Unload→Exit are continuous on coaxial but non-shared segments", () => {
  const machine = {worldX: .5, worldZ: .5};
  const point = (operationKey, cargoOwner, phaseProgress) => runtime.cargoWorldPosition({operationKey, cargoOwner, phaseProgress, operationProgress: phaseProgress}, machine, visualGeometry);
  const samePoint = (left, right) => Math.hypot(left.x-right.x,left.y-right.y,left.z-right.z) <= 1e-9;
  const queueStart = point("LOAD_IN", "QUEUE", 0), queueMid = point("LOAD_IN", "QUEUE", .5), queueEnd = point("LOAD_IN", "QUEUE", 1);
  const loadStart = point("LOAD_IN", "CARRIER_IN", 0), loadEnd = point("LOAD_IN", "CARRIER_IN", 1);
  assert.deepEqual(queueStart, {x: visualGeometry.infeed.x, y: visualGeometry.infeed.entryY, z: visualGeometry.infeed.z});
  assert(samePoint(queueStart, queueMid)); assert(samePoint(queueMid, queueEnd));
  assert(samePoint(queueEnd, loadStart)); assert(samePoint(loadEnd, visualGeometry.transfer));
  const outfeedEnd = point("SCAN_EXIT", "OUTFEED", 1), scannedStart = point("SCAN_EXIT", "SCANNED", 0);
  const scannedEnd = point("SCAN_EXIT", "SCANNED", 1), maskStart = point("SCAN_EXIT", "EXIT_MASK", 0);
  assert(samePoint(outfeedEnd, scannedStart)); assert(samePoint(scannedEnd, maskStart));
  const audit = runtime.validateVisualTopology({io: visualGeometry.io, transfer: visualGeometry.transfer,
    infeed: visualGeometry.infeed, outfeed: visualGeometry.outfeed,
    infeedEnvelope: visualGeometry.infeedEnvelope, outfeedEnvelope: visualGeometry.outfeedEnvelope,
    logicalOrigin: [0, 0], visualOnly: true, singleAisle: true, singleRackFace: true,
    parallel: true, parallelAxis: "y", sharedBelt: false, dualLane: true, rackFrontY: 0});
  assert.equal(audit.axisOffset, 0); assert(audit.junctionGap > visualGeometry.infeed.width);
  assert(audit.rackFrontClearance >= .30); assert.equal(audit.parallelAxis, "y"); assert.deepEqual(audit.logicalOrigin, [0, 0]);
  assert.equal(audit.sharedBelt, false); assert.equal(audit.dualLane, true);
  assert.equal(audit.envelopeOverlapArea, 0); assert.deepEqual(audit.transferAnchor, visualGeometry.transfer);
  assert(visualGeometry.infeed.loadY < visualGeometry.io.y && visualGeometry.outfeed.startY < visualGeometry.io.y,
    "parallel dual lanes must both approach I/O from the rack-facing end");
});

test("Task12 every sampled frame has exactly one logical owner per gid", () => {
  let checked = 0;
  for (const [traceId, trace] of traces) {
    const timeline = runtime.buildTimeline(trace);
    for (let cycle = 0; cycle < trace.events.length; cycle += 1) {
      for (const operation of runtime.PROCESS_STEPS) {
        for (const progress of [.001, .5, .999]) {
          const frame = runtime.deriveFrame(trace, timeline, groupElapsed(timeline, cycle, operation, progress));
          const snapshot = runtime.ownershipSnapshot(frame);
          assert(snapshot.unique, `${traceId}/${cycle}/${operation}/${progress} duplicates=${JSON.stringify(snapshot.duplicates)}`);
          if (frame.cargoGid !== null) {
            assert(!frame.inventoryRows.some(row => row.gid === frame.cargoGid), `${traceId}/${cycle}/${operation} active cargo remains in rack`);
            assert(!frame.queueGids.includes(frame.cargoGid), `${traceId}/${cycle}/${operation} active cargo remains waiting`);
          }
          checked += 1;
        }
      }
    }
  }
  assert.equal(checked, 94500);
});

test("Task12 playback multiplier changes presentation time only", () => {
  assert.equal(runtime.DEFAULT_PLAYBACK_SCALE, .22);
  assert.equal(runtime.normalizePlaybackMultiplier(.1), .25);
  assert.equal(runtime.normalizePlaybackMultiplier(9), 2);
  assert.equal(runtime.normalizePlaybackMultiplier(1.13), 1.25);
  assert.equal(runtime.effectivePlaybackScale(.25), .055);
  assert.equal(runtime.effectivePlaybackScale(1), .22);
  assert.equal(runtime.effectivePlaybackScale(2), .44);
  const source = fs.readFileSync(runtimePath, "utf8");
  assert(source.includes("state.elapsed += delta * state.playbackScale"));
  assert(!source.includes("VX * state.playback")); assert(!source.includes("VZ * state.playback"));
  assert(!source.includes("trace.stats ="));
});

test("Task12 paired label solver avoids overlap, bounds and protected HUD zones", () => {
  const viewports = [{right: 800, bottom: 600}, {right: 1260, bottom: 720}, {right: 1500, bottom: 900}];
  const anchors = [[40, 40], [400, 300], [760, 560], [220, 500], [620, 90]];
  for (const viewport of viewports) for (const [x, y] of anchors) {
    const bounds = {left: 10, top: 10, right: viewport.right - 10, bottom: viewport.bottom - 10};
    const obstacles = [{left: bounds.right - 280, top: bounds.bottom - 120, right: bounds.right, bottom: bounds.bottom},
      {left: x - 18, top: y - 18, right: x + 18, bottom: y + 18, anchorZone: true}];
    const layout = runtime.chooseLabelPairLayout([
      {id: "target", role: "target", anchor: {x, y}, width: 170, height: 54},
      {id: "cargo", role: "cargo", anchor: {x: x + 5, y: y + 4}, width: 155, height: 48}
    ], bounds, obstacles);
    assert.equal(layout.overlapArea, 0, `labels overlap at ${x}/${y}`);
    for (const {rect} of layout.placements) {
      assert(rect.left >= bounds.left && rect.top >= bounds.top && rect.right <= bounds.right && rect.bottom <= bounds.bottom, `label out of bounds at ${x}/${y}`);
    }
  }
});
