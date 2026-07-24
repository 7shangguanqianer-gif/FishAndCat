/* S3 fill-only candidate runtime. One verified release drives bookmarks, 2D, 3D and text. */
(function (root) {
  "use strict";

  const EPS = 1e-9;
  const BOOKMARKS = Object.freeze([0, 67, 134, 201, 241, 267]);
  const STEP_ORDER = Object.freeze(["INFEED_HANDOFF", "LADEN_TRAVEL", "STORE_HANDLE", "EMPTY_RETURN"]);
  const STEP_META = Object.freeze({
    INFEED_HANDOFF: {short: "交接", label: "入口交接", purpose: "同侧入库链把到场货物送至 T 形互锁转接台"},
    LADEN_TRAVEL: {short: "入库", label: "双轴入库", purpose: "X / Z 双轴按加减速模型同步运行至算法选定货位"},
    STORE_HANDLE: {short: "放货", label: "伸叉放货", purpose: "货叉先承托伸入，完成交接后再空叉回收"},
    EMPTY_RETURN: {short: "回程", label: "空载回程", purpose: "货物已由货架接管；堆垛机空载返回唯一逻辑 I/O"}
  });
  const DISPLAY_STEPS = Object.freeze([
    {phase: "INFEED_HANDOFF", p0: 0, p1: null, short: "入场", label: "输送入场", purpose: "货物沿入库链从入口运行至装载工位"},
    {phase: "INFEED_HANDOFF", p0: null, p1: 1, short: "交接", label: "入口交接", purpose: "货物通过 T 形互锁台交接至堆垛机"},
    {phase: "LADEN_TRAVEL", p0: 0, p1: 1, short: "入库", label: "双轴入库", purpose: "X / Z 双轴按加减速模型同步运行至目标货位"},
    {phase: "STORE_HANDLE", p0: 0, p1: .44, short: "伸叉", label: "货叉伸入", purpose: "货叉保持承托并伸入目标货位"},
    {phase: "STORE_HANDLE", p0: .44, p1: .62, short: "放货", label: "货物交接", purpose: "货物由货叉转交货架，所有权切换为 RACK"},
    {phase: "STORE_HANDLE", p0: .62, p1: 1, short: "回叉", label: "货叉回收", purpose: "货物留在货架，空叉回收至载货台"},
    {phase: "EMPTY_RETURN", p0: 0, p1: 1, short: "回程", label: "空载回程", purpose: "堆垛机空载返回唯一逻辑 I/O"}
  ]);
  const LANE_LABEL = Object.freeze({seq: "顺序放置 SEQ", near: "就近放置 NEAR", score: "多目标评分 SCORE"});
  const GRADE_LABEL = Object.freeze({heavy: "重货", mid: "中货", light: "轻货"});
  const OWNER_LABEL = Object.freeze({INFEED: "入库链", CARRIER: "载货台", FORK: "货叉", RACK: "货架"});
  /* 0716 用户授权修改:2D 采用 3D 渲染视觉采样色(光照+ACESFilmic 后实际观感),消除 2D/3D 色差(R11)。
     采样来源:bookmark_134 渲染帧三级货物聚类中心;原值 heavy#102a43/mid#006bb6/light#42c7e6。 */
  const GRADE_CSS = Object.freeze({heavy: "#366786", mid: "#4ea9c2", light: "#abd1d8"});
  const PATH_COLOR = Object.freeze({
    INFEED_HANDOFF: 0xe85d04, LADEN_TRAVEL: 0xff000f, STORE_HANDLE: 0xe7b800, EMPTY_RETURN: 0x7b2cbf
  });
  /* W6(0720 照 02 语言重做):演示倍率吸附刻度,数值与 s3_ac_runtime.js 的 PLAYBACK_MULTIPLIER_MIN/MAX/
     PLAYBACK_SNAP_TICKS/RADIUS 同源(同一批用户拍板值);01 无独立 DEFAULT_PLAYBACK_SCALE 概念,
     倍率直接驱动 state.multiplier,不引入 effectivePlaybackScale 这层抽象。 */
  const PLAYBACK_MULTIPLIER_MIN = 0.25, PLAYBACK_MULTIPLIER_MAX = 5;
  const PLAYBACK_SNAP_TICKS = Object.freeze([0.25, 0.5, 1, 2, 3, 5]);
  const PLAYBACK_SNAP_RADIUS = 0.1;

  function invariant(condition, message) {
    if (!condition) throw new Error(message);
  }

  function clamp(value, low, high) {
    return Math.min(high, Math.max(low, value));
  }

  function ease(value) {
    const p = clamp(value, 0, 1);
    return p * p * (3 - 2 * p);
  }

  function normalizePlaybackMultiplier(value) {
    const parsed = Number(value);
    invariant(Number.isFinite(parsed), "演示倍率非法");
    const clamped = clamp(parsed, PLAYBACK_MULTIPLIER_MIN, PLAYBACK_MULTIPLIER_MAX);
    let nearestTick = clamped, nearestDist = Infinity;
    PLAYBACK_SNAP_TICKS.forEach(tick => {
      const dist = Math.abs(clamped - tick);
      if (dist < nearestDist) { nearestDist = dist; nearestTick = tick; }
    });
    const snapped = nearestDist <= PLAYBACK_SNAP_RADIUS ? nearestTick : clamped;
    return Math.round(snapped * 100) / 100;
  }

  function payloadFromVerifiedQueue() {
    const queue = root.__S3_FILL_VERIFIED_QUEUE__;
    invariant(Array.isArray(queue) && queue.length === 1, "fill bundle 队列必须且只能有一个已验证 payload");
    const record = queue.shift();
    invariant(record && record.schema_version === "s3-fill-verified-queue-envelope-v1" && record.payload, "fill bundle 队列记录非法");
    invariant(record.bundle_payload_sha256 === record.payload.bundle_payload_sha256, "fill bundle 队列哈希不一致");
    return record.payload;
  }

  function validatePayload(payload) {
    invariant(payload && payload.schema_version === "s3-fill-frontend-bundle-v1", "fill bundle schema 不匹配");
    invariant(payload.validator && payload.validator.pass === true &&
      payload.validator.data_integrity_pass === true, "fill bundle 未通过独立数据验证");
    invariant(payload.validator.front_end_bindable === true &&
      payload.validator.frontend_binding_status === "ok", "fill bundle 尚未获得前端绑定批准");
    invariant(payload.manifest && payload.manifest.sim_only === true, "fill bundle 必须明确 SIM");
    invariant(payload.manifest.data_gate.front_end_evidence_binding === "DISABLED_PENDING_VERIFIED_LOADER",
      "原始 manifest 前端边界不匹配");
    invariant(payload.release.release_id === payload.pointer.release_id &&
      payload.release.release_id === payload.registry.active_release_id, "release / pointer / registry 未锁定同一版本");
    invariant(payload.registry.active_entry &&
      payload.registry.active_entry.status === "approved_for_frontend_binding",
      "registry 当前版本未批准前端绑定");
    const algorithms = payload.online_lanes.map(lane => lane.algorithm && lane.algorithm.id).sort();
    invariant(JSON.stringify(algorithms) === JSON.stringify(["near", "score", "seq"]), "在线 lane 必须精确为 SEQ/NEAR/SCORE");
    invariant(payload.capacity.cols === 20 && payload.capacity.tiers === 20 &&
      payload.capacity.preoccupied_slots === 133 && payload.capacity.managed_capacity === 267,
      "20×20 / 133+267 容量契约不匹配");
    invariant(payload.cargo_catalog.length === 267, "cargo_catalog 必须为 267 件");
    invariant(payload.decision_evidence && payload.decision_evidence.schema_version === "s3-fill-decision-top3-v1" &&
      Array.isArray(payload.decision_evidence.lanes) && payload.decision_evidence.lanes.length === 3,
      "逐事件候选证据未装载");
    invariant(payload.score_policy && payload.score_policy.known_collinearity &&
      payload.score_policy.known_collinearity.stability_raw_equals_energy_proxy_raw === true &&
      payload.score_policy.known_collinearity.ui_rule === "preserve computation but explain jointly as one load-height factor",
      "SCORE 载重×层高共线性契约缺失");
    return payload;
  }

  function validateTopology() {
    invariant(TRANSFER_TOPOLOGY.sameSide === true && TRANSFER_TOPOLOGY.parallel === true &&
      TRANSFER_TOPOLOGY.parallelAxis === "y" && TRANSFER_TOPOLOGY.tJunction === true &&
      TRANSFER_TOPOLOGY.sharedBelt === false, "候选必须是同侧并行 T 形双链");
    invariant(INFEED.loadY < IO.y && OUTFEED.startY < IO.y && INFEED.entryY < INFEED.loadY &&
      OUTFEED.endY < OUTFEED.maskY && OUTFEED.maskY < OUTFEED.scanY && OUTFEED.scanY < OUTFEED.startY,
      "双链方向或工位顺序非法");
    const overlapX = Math.max(0, Math.min(CONVEYOR_ENVELOPES.infeed.xMax, CONVEYOR_ENVELOPES.outfeed.xMax) -
      Math.max(CONVEYOR_ENVELOPES.infeed.xMin, CONVEYOR_ENVELOPES.outfeed.xMin));
    const overlapY = Math.max(0, Math.min(CONVEYOR_ENVELOPES.infeed.yMax, CONVEYOR_ENVELOPES.outfeed.yMax) -
      Math.max(CONVEYOR_ENVELOPES.infeed.yMin, CONVEYOR_ENVELOPES.outfeed.yMin));
    invariant(overlapX * overlapY <= EPS, "入/出库链物理包络重叠");
    return Object.freeze({sameSide: true, parallel: true, parallelAxis: "y", tJunction: true,
      sharedBelt: false, singleAisle: true, singleRackFace: true, envelopeOverlapArea: overlapX * overlapY});
  }

  function phasePresentationSeconds(phase) {
    const actual = Number(phase.t1) - Number(phase.t0);
    invariant(Number.isFinite(actual) && actual >= 0, `阶段 ${phase.name} SIM 时长非法`);
    /* 单一严格单调映射；没有按阶段另设快慢，避免“主运动快、交接慢”的倒置。 */
    return 0.38 + actual * 0.05;
  }

  function rowsFromGrid(grid) {
    const rows = [];
    for (let col = 0; col < 20; col += 1) for (let tier = 0; tier < 20; tier += 1) {
      const gid = grid[col * 20 + tier];
      if (gid > 0) rows.push({gid, col, tier});
    }
    return rows;
  }

  function buildLaneModel(lane, capacity, decisionEvidence) {
    const algorithmId = lane.algorithm && lane.algorithm.id;
    invariant(LANE_LABEL[algorithmId], "lane algorithm id 非法");
    invariant(lane.status === "FEASIBLE" && lane.failure === null && lane.events.length === 267, `${algorithmId} lane 不完整`);
    invariant(decisionEvidence && decisionEvidence.algorithm === algorithmId &&
      decisionEvidence.lane_id === lane.lane_id && decisionEvidence.events.length === 267,
      `${algorithmId} Top 3 证据链不完整`);
    invariant(lane.checkpoints.map(item => item.event_count).join(",") === BOOKMARKS.join(","), `${algorithmId} 书签不完整`);
    const initial = lane.checkpoints[0].grid_col_major.slice();
    invariant(initial.length === 400 && initial.filter(value => value === -1).length === capacity.preoccupied_slots &&
      initial.filter(value => value > 0).length === 0, `${algorithmId} 零起点非法`);
    const grids = [initial], inventories = [rowsFromGrid(initial)], eventStarts = [];
    const segments = [];
    let displayClock = 0;
    lane.events.forEach((event, eventIndex) => {
      invariant(event.event_index === eventIndex + 1 && event.gid === eventIndex + 1, `${algorithmId} 事件序号断链`);
      const decisionAudit = decisionEvidence.events[eventIndex];
      invariant(decisionAudit.event_index === event.event_index &&
        decisionAudit.audit_sha256 === event.decision.candidate_audit_ref.audit_sha256 &&
        decisionAudit.top3.length >= 1 && decisionAudit.top3.length <= 3 &&
        decisionAudit.top3[0].rank === 1 && decisionAudit.top3[0].selected === true &&
        JSON.stringify(decisionAudit.top3[0].slot) === JSON.stringify(event.decision.selected_slot),
        `${algorithmId} 事件 ${event.event_index} Top 3 与实际决策不一致`);
      if (algorithmId === "score") invariant(Math.abs(decisionAudit.top3[0].score_terms.score_total -
        event.decision.selected_score) <= EPS, `score 事件 ${event.event_index} 总分与实际决策不一致`);
      invariant(event.occupancy.managed_before === eventIndex && event.occupancy.managed_after === eventIndex + 1,
        `${algorithmId} 事件容量断链`);
      const grid = grids[eventIndex].slice(), [col, tier] = event.slot_state_change.slot;
      invariant(grid[col * 20 + tier] === 0 && event.slot_state_change.after === `GID:${event.gid}`,
        `${algorithmId} 事件 ${event.event_index} 目标格非法`);
      grid[col * 20 + tier] = event.gid;
      grids.push(grid); inventories.push(rowsFromGrid(grid)); eventStarts.push(displayClock);
      invariant(event.phases.length === STEP_ORDER.length && event.phases.every((phase, index) => phase.name === STEP_ORDER[index]),
        `${algorithmId} 事件 ${event.event_index} 四阶段不完整`);
      let phaseCursor = Number(event.clock.start_s), phaseSimTotal = 0;
      event.phases.forEach((phase, phaseIndex) => {
        const phaseActual = Number(phase.t1) - Number(phase.t0);
        invariant(Math.abs(Number(phase.t0) - phaseCursor) <= EPS && phaseActual >= 0,
          `${algorithmId} 事件 ${event.event_index} 阶段 ${phaseIndex + 1} 时间断链`);
        phaseCursor = Number(phase.t1); phaseSimTotal += phaseActual;
        const duration = phasePresentationSeconds(phase);
        segments.push({eventIndex, phaseIndex, phase, event, d0: displayClock, d1: displayClock + duration, duration});
        displayClock += duration;
      });
      invariant(Math.abs(phaseCursor - Number(event.clock.finish_s)) <= EPS &&
        Math.abs(phaseSimTotal - Number(event.clock.duration_s)) <= EPS,
        `${algorithmId} 事件 ${event.event_index} 阶段总时长与事件不一致`);
    });
    eventStarts.push(displayClock);
    invariant(inventories[267].length === 267 && grids[267].filter(value => value !== 0).length === 400,
      `${algorithmId} 满终点非法`);
    lane.checkpoints.forEach(checkpoint => {
      invariant(JSON.stringify(grids[checkpoint.event_count]) === JSON.stringify(checkpoint.grid_col_major),
        `${algorithmId} 书签 ${checkpoint.event_count} 与 reducer 不一致`);
    });
    return Object.freeze({lane, decisionEvidence, grids, inventories, eventStarts, segments, total: displayClock});
  }

  function locateSegment(model, elapsed) {
    const value = clamp(elapsed, 0, Math.max(0, model.total - EPS));
    let low = 0, high = model.segments.length - 1;
    while (low < high) {
      const mid = (low + high) >> 1;
      if (value < model.segments[mid].d1) high = mid; else low = mid + 1;
    }
    const segment = model.segments[low];
    return {segment, progress: clamp((value - segment.d0) / segment.duration, 0, 1)};
  }

  function motionAxis(time, distance, vmax, accel) {
    if (distance <= 0) return {position: 0, velocity: 0, total: 0};
    const total = axisT(distance, vmax, accel), t = clamp(time, 0, total);
    const position = axisPos(t, distance, vmax, accel), velocity = axisV(t, distance, vmax, accel);
    return {position, velocity, total};
  }

  function motionPoint(from, to, progress, loaded) {
    const dx = Math.abs(to[0] - from[0]), dz = Math.abs(to[1] - from[1]);
    const tx = axisT(dx, VX, AX), vz = loaded ? VZ * 0.8 : VZ, tz = axisT(dz, vz, AZ), total = Math.max(tx, tz);
    const t = clamp(progress, 0, 1) * total;
    const mx = motionAxis(t, dx, VX, AX), mz = motionAxis(t, dz, vz, AZ);
    return {x: from[0] + Math.sign(to[0] - from[0]) * mx.position,
      z: from[1] + Math.sign(to[1] - from[1]) * mz.position,
      vx: Math.sign(to[0] - from[0]) * mx.velocity, vz: Math.sign(to[1] - from[1]) * mz.velocity, total};
  }

  function pointOnPolyline(points, progress) {
    const lengths = points.slice(1).map((point, index) => point.distanceTo(points[index]));
    const total = lengths.reduce((sum, value) => sum + value, 0), target = clamp(progress, 0, 1) * total;
    let walked = 0;
    for (let index = 0; index < lengths.length; index += 1) {
      if (target <= walked + lengths[index] + EPS) return points[index].clone().lerp(points[index + 1],
        lengths[index] <= EPS ? 1 : (target - walked) / lengths[index]);
      walked += lengths[index];
    }
    return points[points.length - 1].clone();
  }

  const payload = validatePayload(payloadFromVerifiedQueue());
  /* 治理 C2:情景以 payload 自证字段为准(不信 URL),skew=生产偏斜货流,uniform=对照情景。 */
  const SCENARIO = payload.shared_input_provenance && payload.shared_input_provenance.profile &&
    payload.shared_input_provenance.profile.case === "uniform" ? "uniform" : "skew";
  const topologyAudit = validateTopology();
  const catalog = new Map(payload.cargo_catalog.map(item => [item.gid, item]));
  const evidenceByAlgorithm = new Map(payload.decision_evidence.lanes.map(item => [item.algorithm, item]));
  const models = new Map(payload.online_lanes.map(lane => [lane.algorithm.id,
    buildLaneModel(lane, payload.capacity, evidenceByAlgorithm.get(lane.algorithm.id))]));
  const byId = id => document.getElementById(id);
  const good = gid => { const item = catalog.get(gid); invariant(item, `cargo_catalog 缺少 gid=${gid}`); return item; };
  /* 0717 #28 二轮:热门集合口径同 sim/warehouse_sim.py:400——已放置货按 freq 降序前 1/5
     (稳定排序保放置序),267 件→前 53;三 lane 同一到达队列,集合一致,任取一 lane 计算。 */
  /* W6:货位访问排名(第 N/267 名)与热门集合同源同序——复用同一份按 freq 降序、稳定排序的 order,
     不另起一套排序口径。呼应 02 的 freqRankByGid;01 数据门无 freq_true 字段,同义用 freq(已核实,
     见 s3_fill_store.js 字段名)。 */
  const {hotGids, freqRankByGid} = (() => {
    const order = models.get("score").lane.events.map((event, index) =>
      ({gid: event.gid, freq: good(event.gid).freq, index}));
    order.sort((a, b) => b.freq - a.freq || a.index - b.index);
    const hotSet = new Set(order.slice(0, Math.max(1, Math.floor(order.length / 5))).map(entry => entry.gid));
    const rankByGid = new Map(order.map((entry, rankIndex) => [entry.gid, rankIndex + 1]));
    return {hotGids: hotSet, freqRankByGid: rankByGid};
  })();
  const targetCardMode = document.documentElement.dataset.s3TargetCard === "1";
  const infeedEntryDistance = Math.abs(INFEED.loadY - INFEED.entryY);
  const infeedTransferDistance = Math.hypot(IO.x - INFEED.x, CROSSBAR.y - INFEED.loadY) +
    Math.hypot(TRANSFER_ANCHOR.x - IO.x, TRANSFER_ANCHOR.y - CROSSBAR.y);
  const INFEED_ENTRY_RATIO = infeedEntryDistance / (infeedEntryDistance + infeedTransferDistance);
  DISPLAY_STEPS[0].p1 = DISPLAY_STEPS[1].p0 = INFEED_ENTRY_RATIO;

  function displayStepIndex(frame) {
    if (frame.idle) return -1;
    return DISPLAY_STEPS.findIndex(step => step.phase === frame.operation &&
      frame.phaseProgress >= step.p0 - EPS && frame.phaseProgress <= step.p1 + EPS);
  }

  function displayDurations(event, presentation = false) {
    const byPhase = Object.fromEntries(event.phases.map(phase => [phase.name,
      presentation ? phasePresentationSeconds(phase) : Number(phase.t1) - Number(phase.t0)]));
    return DISPLAY_STEPS.map(step => byPhase[step.phase] * (step.p1 - step.p0));
  }

  function validateTimingModels() {
    let eventCount = 0, stepCount = 0, maxSimSumError = 0, maxPresentationFormulaError = 0;
    let minSimStep = Infinity, maxSimStep = 0, minPresentationStep = Infinity, maxPresentationStep = 0;
    models.forEach(model => model.lane.events.forEach(event => {
      const sim = displayDurations(event), presentation = displayDurations(event, true);
      const eventSim = Number(event.clock.duration_s), simSum = sim.reduce((sum, value) => sum + value, 0);
      maxSimSumError = Math.max(maxSimSumError, Math.abs(simSum - eventSim));
      sim.forEach((value, index) => {
        invariant(value > 0 && presentation[index] > 0, `事件 ${event.event_index} 七个展示步时长必须为正`);
        minSimStep = Math.min(minSimStep, value); maxSimStep = Math.max(maxSimStep, value);
        minPresentationStep = Math.min(minPresentationStep, presentation[index]);
        maxPresentationStep = Math.max(maxPresentationStep, presentation[index]); stepCount += 1;
      });
      event.phases.forEach(phase => {
        const actual = Number(phase.t1) - Number(phase.t0), expected = .38 + actual * .05;
        maxPresentationFormulaError = Math.max(maxPresentationFormulaError,
          Math.abs(phasePresentationSeconds(phase) - expected));
      });
      eventCount += 1;
    }));
    invariant(eventCount === 3 * 267 && stepCount === 3 * 267 * 7 && maxSimSumError <= EPS &&
      maxPresentationFormulaError <= EPS, "四阶段 trace / 七展示步时长审计失败");
    return Object.freeze({eventCount, stepCount, maxSimSumError, maxPresentationFormulaError,
      minSimStep, maxSimStep, minPresentationStep, maxPresentationStep,
      sourcePhaseCount: 4, displayStepCount: 7, method: "derived_from_four_trace_phases",
      mapping: "四个原始 trace 阶段统一使用 0.38 + 0.05 × SIM秒；七个展示步按几何与货叉阈值细分，不是七个原生时间戳"});
  }

  const timingAudit = validateTimingModels();

  /* The mature base created the machine and rack. Candidate runtime owns only dynamic objects. */
  const stockGroup = new THREE.Group(); scene.add(stockGroup);
  const stockDummy = new THREE.Object3D(), stockCapacity = 267;
  const stockBodyGeometry = new THREE.BoxGeometry(.84, .86, .72);
  const stockLidGeometry = new THREE.BoxGeometry(.86, .88, .08);
  const gradeMaterial = {heavy: M.heavy, mid: M.mid, light: M.light};
  const stockMeshes = Object.fromEntries(Object.entries(gradeMaterial).map(([grade, material]) => {
    const mesh = new THREE.InstancedMesh(stockBodyGeometry, material, stockCapacity);
    mesh.count = 0; mesh.castShadow = false; mesh.receiveShadow = false; stockGroup.add(mesh); return [grade, mesh];
  }));
  const lidMesh = new THREE.InstancedMesh(stockLidGeometry, M.lid, stockCapacity);
  lidMesh.count = 0; stockGroup.add(lidMesh);
  /* 0717 #26-2 热门货 3D 视觉通道:hot20(freq 前 1/5)货箱换金顶盖——SCORE「热门放近」的胜利从隐形变可见。 */
  const hotLidMaterial = M.lid.clone(); hotLidMaterial.color.set(0xd9ad00);
  if (hotLidMaterial.emissive) hotLidMaterial.emissive.set(0x3a2e00);
  const hotLidMesh = new THREE.InstancedMesh(stockLidGeometry, hotLidMaterial, stockCapacity);
  hotLidMesh.count = 0; stockGroup.add(hotLidMesh);
  if (cargo.parent) cargo.parent.remove(cargo); scene.add(cargo); cargo.visible = false;

  const activeMaterials = Object.fromEntries(Object.entries(gradeMaterial).map(([grade, material]) => {
    const clone = material.clone(); clone.transparent = true; clone.opacity = 1; return [grade, clone];
  }));
  let stockSignature = "", pathSignature = "", livePaths = [], lastFrame = null, runtimeErrors = 0, lastBeaconAudit = null;
  /* 0717 #28:目标格发光壳+格口箭头实体由 01 页母版创建并挂 __S3_TARGET_FX;候选页无此全局,判空跳过。 */
  const targetFx = root.__S3_TARGET_FX || null;

  function setInventory(rows, laneId, managedCount) {
    const signature = `${laneId}:${managedCount}`;
    if (signature === stockSignature) return;
    stockSignature = signature;
    const counts = {heavy: 0, mid: 0, light: 0}; let lidCount = 0, hotLidCount = 0;
    rows.forEach(row => {
      const grade = good(row.gid).grade;
      stockDummy.position.set(row.col + .5, RACK.loadY, row.tier + .46); stockDummy.updateMatrix();
      stockMeshes[grade].setMatrixAt(counts[grade]++, stockDummy.matrix);
      stockDummy.position.set(row.col + .5, RACK.loadY, row.tier + .84); stockDummy.updateMatrix();
      /* #26-2:热门货金顶盖,普通货灰顶盖 */
      if (hotGids.has(row.gid)) hotLidMesh.setMatrixAt(hotLidCount++, stockDummy.matrix);
      else lidMesh.setMatrixAt(lidCount++, stockDummy.matrix);
    });
    Object.entries(stockMeshes).forEach(([grade, mesh]) => { mesh.count = counts[grade]; mesh.instanceMatrix.needsUpdate = true; });
    lidMesh.count = lidCount; lidMesh.instanceMatrix.needsUpdate = true;
    hotLidMesh.count = hotLidCount; hotLidMesh.instanceMatrix.needsUpdate = true;
  }

  function disposePaths() {
    livePaths.forEach(path => { scene.remove(path.group); path.group.traverse(object => { if (object.geometry) object.geometry.dispose(); });
      path.material.dispose(); if (path.haloMaterial) path.haloMaterial.dispose(); });
    livePaths = [];
  }

  function sampledMachinePath(from, to, loaded) {
    return Array.from({length: 33}, (_, index) => {
      const point = motionPoint(from, to, index / 32, loaded);
      return new THREE.Vector3(point.x + .5, IO.y, point.z + .5 + (loaded ? CARGO_Z_OFFSET : 0));
    });
  }

  function pathPlans(event) {
    const [col, tier] = event.decision.selected_slot;
    const infeed = [
      new THREE.Vector3(INFEED.x, INFEED.entryY, INFEED.z),
      new THREE.Vector3(INFEED.x, INFEED.loadY, INFEED.z),
      new THREE.Vector3(IO.x, CROSSBAR.y, TRANSFER_ANCHOR.z),
      new THREE.Vector3(TRANSFER_ANCHOR.x, TRANSFER_ANCHOR.y, TRANSFER_ANCHOR.z)
    ];
    const store = Array.from({length: 17}, (_, index) => new THREE.Vector3(col + .5,
      TRANSFER_ANCHOR.y + (RACK.loadY - TRANSFER_ANCHOR.y) * index / 16, tier + .5 + CARGO_Z_OFFSET));
    return [
      {key: "INFEED_HANDOFF", points: infeed, arrows: 3},
      {key: "LADEN_TRAVEL", points: sampledMachinePath([0, 0], [col, tier], true), arrows: 3},
      {key: "STORE_HANDLE", points: store, arrows: 1},
      {key: "EMPTY_RETURN", points: sampledMachinePath([col, tier], [0, 0], false), arrows: 3}
    ];
  }

  function setPaths(event, laneId, activeKey) {
    const signature = `${laneId}:${event.event_index}`;
    if (signature !== pathSignature) {
      pathSignature = signature; disposePaths();
      pathPlans(event).forEach(plan => {
        const path = addPath(plan.points, {color: PATH_COLOR[plan.key], opacity: .28, arrowCount: plan.arrows,
          operationKey: plan.key, kind: "fill", radius: .065, haloRadius: .12});
        path.key = plan.key; path.points = plan.points.map(point => point.toArray()); livePaths.push(path);
      });
    }
    const activeIndex = STEP_ORDER.indexOf(activeKey);
    livePaths.forEach(path => {
      const index = STEP_ORDER.indexOf(path.key), active = index === activeIndex;
      path.material.opacity = active ? .98 : activeIndex < 0 ? .36 : index < activeIndex ? .42 : .24;
      path.material.depthTest = !active;
      if (path.haloMaterial) path.haloMaterial.opacity = active ? .72 : 0;
      path.group.renderOrder = active ? 7 : 2;
    });
  }

  function machineFrame(operation, phaseProgress, slot) {
    if (operation === "LADEN_TRAVEL") return motionPoint([0, 0], slot, phaseProgress, true);
    if (operation === "EMPTY_RETURN") return motionPoint(slot, [0, 0], phaseProgress, false);
    if (operation === "STORE_HANDLE") return {x: slot[0], z: slot[1], vx: 0, vz: 0, total: 0};
    return {x: 0, z: 0, vx: 0, vz: 0, total: 0};
  }

  function activeFrame(model, elapsed) {
    const found = locateSegment(model, elapsed), {event, phase, eventIndex} = found.segment;
    const operation = phase.name, p = found.progress, slot = event.decision.selected_slot;
    const afterTransfer = operation === "EMPTY_RETURN" || (operation === "STORE_HANDLE" && p >= .62);
    const rows = model.inventories[eventIndex + (afterTransfer ? 1 : 0)];
    const machine = machineFrame(operation, p, slot);
    const cargoVisible = operation !== "EMPTY_RETURN" && !(operation === "STORE_HANDLE" && p >= .62);
    return {idle: false, event, eventIndex, phase, operation, phaseProgress: p, machine, slot,
      rows, managedCount: eventIndex + (afterTransfer ? 1 : 0), cargoVisible, cargoOwner:
        operation === "INFEED_HANDOFF" ? "INFEED" : operation === "LADEN_TRAVEL" ? "CARRIER" :
          operation === "STORE_HANDLE" && p < .62 ? "FORK" : "RACK",
      simTime: Number(phase.t0) + (Number(phase.t1) - Number(phase.t0)) * p};
  }

  function idleFrame(model, count) {
    const event = count < 267 ? model.lane.events[count] : model.lane.events[266];
    return {idle: true, event, eventIndex: Math.min(count, 266), phase: null, operation: null, phaseProgress: 0,
      machine: {x: 0, z: 0, vx: 0, vz: 0, total: 0}, slot: count < 267 ? event.decision.selected_slot : null,
      rows: model.inventories[count], managedCount: count, cargoVisible: false, cargoOwner: count === 267 ? "FULL" : "NOT_ARRIVED",
      simTime: count === 267 ? model.lane.events[266].clock.finish_s : count === 0 ? 0 : model.lane.events[count - 1].clock.finish_s};
  }

  function setMachine(frame) {
    const worldX = frame.machine.x + .5, worldZ = frame.machine.z + .5;
    mast.position.x = worldX; machineParts.forEach(part => { part.position.x = worldX; });
    carrier.position.set(worldX, IO.y, worldZ);
    const beltLength = Math.max(.45, N - worldZ + .05), beltCenter = (N + worldZ) / 2;
    liftBelts.forEach(belt => { belt.scale.z = beltLength; belt.position.z = beltCenter; });
    forkGroup.position.set(0, 0, 0); forkExtension = 0; forkDrop = 0;
    if (frame.operation === "STORE_HANDLE") {
      const p = frame.phaseProgress;
      const extension = p < .44 ? ease(p / .44) : p < .62 ? 1 : 1 - ease((p - .62) / .38);
      forkExtension = FORK_MAX * extension; forkGroup.position.y = forkExtension;
      forkDrop = CARGO_DROP * clamp((p - .40) / .16, 0, 1); forkGroup.position.z = -forkDrop;
    }
    return {worldX, worldZ};
  }

  function setCargo(frame, machineWorld) {
    if (!frame.cargoVisible) { cargo.visible = false; cargo.userData = {gid: null, owner: frame.cargoOwner}; return; }
    const item = good(frame.event.gid), material = activeMaterials[item.grade];
    Object.values(activeMaterials).forEach(value => { value.opacity = 1; }); cargo.material = material; cargo.visible = true;
    cargo.userData = {gid: item.gid, owner: frame.cargoOwner, grade: item.grade};
    let position;
    if (frame.operation === "INFEED_HANDOFF") position = pointOnPolyline([
      new THREE.Vector3(INFEED.x, INFEED.entryY, INFEED.z), new THREE.Vector3(INFEED.x, INFEED.loadY, INFEED.z),
      new THREE.Vector3(IO.x, CROSSBAR.y, TRANSFER_ANCHOR.z), new THREE.Vector3(TRANSFER_ANCHOR.x, TRANSFER_ANCHOR.y, TRANSFER_ANCHOR.z)
    ], ease(frame.phaseProgress));
    else if (frame.operation === "STORE_HANDLE") position = new THREE.Vector3(machineWorld.worldX,
      TRANSFER_ANCHOR.y + (RACK.loadY - TRANSFER_ANCHOR.y) * ease(frame.phaseProgress / .62),
      machineWorld.worldZ + CARGO_Z_OFFSET - forkDrop);
    else position = new THREE.Vector3(machineWorld.worldX, TRANSFER_ANCHOR.y, machineWorld.worldZ + CARGO_Z_OFFSET);
    cargo.position.copy(position);
  }

  function setTarget(frame) {
    const visible = Array.isArray(frame.slot);
    targetBox.visible = targetPad.visible = visible; byId("targetBeacon").hidden = !visible;
    if (targetFx && !visible) { targetFx.glow.visible = targetFx.arrow.visible = targetFx.face.visible = false; }
    const card = byId("targetCard");
    if (card && !visible) {
      card.classList.add("done"); byId("targetCardState").textContent = "已填满";
      byId("targetCardSlot").textContent = "267 / 267"; byId("targetCardDetail").textContent = "全部货位入库确认 · 违规 0";
    }
    if (!visible) { byId("targetLeader").hidden = true; return; }
    const [col, tier] = frame.slot;
    targetBox.position.set(col + .5, RACK.loadY, tier + .5); targetPad.position.set(col + .5, RACK.loadY, tier + .075);
    const beacon = byId("targetBeacon"), completed = !frame.idle && frame.cargoOwner === "RACK";
    /* 0717 #28 用户拍板:目标格自身强高亮——发光壳(入库完成转绿常亮)+ 大头针箭头(完成后收起)。 */
    if (targetFx) {
      targetFx.glow.visible = true; targetFx.glow.position.set(col + .5, RACK.loadY, tier + .5);
      targetFx.face.visible = true; targetFx.face.position.set(col + .5, RACK.frontY - .012, tier + .5);
      targetFx.glowMat.color.copy(completed ? targetFx.done : targetFx.amber);
      targetFx.faceMat.color.copy(completed ? targetFx.done : targetFx.amber);
      targetFx.arrow.visible = !completed;
      targetFx.arrow.position.set(col + .5, targetFx.arrowY, tier + targetFx.arrowZGap);
      targetFx.arrow.userData.baseZ = tier + targetFx.arrowZGap;
    }
    beacon.querySelector("b").textContent = `${completed ? "已入库货位" : "入库目标"} ${String(col).padStart(2, "0")} / ${String(tier).padStart(2, "0")}`;
    beacon.querySelector("span").textContent = `第 ${String(col).padStart(2, "0")} 列 · 第 ${String(tier).padStart(2, "0")} 层`;
    /* 0717 #28 二轮:dock 目标货位卡接管标牌文字(3D 只留图形高亮);候选页无此卡,判空跳过。 */
    if (card) {
      card.classList.toggle("done", completed);
      byId("targetCardState").textContent = completed ? "已入库" : frame.idle ? "下一目标" : "入库作业中";
      byId("targetCardSlot").textContent = `${String(col).padStart(2, "0")} / ${String(tier).padStart(2, "0")}`;
      byId("targetCardDetail").textContent = `第 ${String(col).padStart(2, "0")} 列 · 第 ${String(tier).padStart(2, "0")} 层`;
    }
  }

  function layoutTarget(frame) {
    if (!frame.slot) { lastBeaconAudit = null; return; }
    /* 0717 #28 二轮:target-card 模式下 3D 标牌退役(CSS display:none),文字由 dock 目标货位卡承担;
       审计改记卡片一致性,QA beaconAnchored 门按 mode 分支。 */
    if (targetCardMode) {
      const slotEl = byId("targetCardSlot");
      lastBeaconAudit = {mode: "dock-card", slot: frame.slot.slice(),
        cardVisible: Boolean(slotEl) && slotEl.getBoundingClientRect().height > 4,
        cardText: slotEl ? slotEl.textContent : "",
        beaconRetired: getComputedStyle(byId("targetBeacon")).display === "none"};
      return;
    }
    const viewportRect = viewportEl.getBoundingClientRect(), mountRect = mount.getBoundingClientRect();
    const ndc = new THREE.Vector3(frame.slot[0] + .5, RACK.frontY - .04, frame.slot[1] + .65).project(camera);
    const anchor = {x: mountRect.left - viewportRect.left + (ndc.x + 1) * mountRect.width / 2,
      y: mountRect.top - viewportRect.top + (1 - ndc.y) * mountRect.height / 2};
    const beacon = byId("targetBeacon"); beacon.style.visibility = "hidden"; beacon.hidden = false;
    const rect = beacon.getBoundingClientRect(), bounds = {left: mountRect.left - viewportRect.left + 10,
      right: mountRect.right - viewportRect.left - 10, top: mountRect.top - viewportRect.top + 10,
      bottom: mountRect.bottom - viewportRect.top - 10};
    let left = anchor.x + 22;
    if (left + rect.width > bounds.right) left = anchor.x - rect.width - 22;
    left = clamp(left, bounds.left, bounds.right - rect.width);
    const top = clamp(anchor.y - rect.height / 2, bounds.top, bounds.bottom - rect.height);
    beacon.style.left = `${left}px`; beacon.style.top = `${top}px`; beacon.style.visibility = "";
    const line = byId("targetLeader"), endX = left > anchor.x ? left : left + rect.width, endY = top + rect.height / 2;
    line.setAttribute("points", `${anchor.x.toFixed(1)},${anchor.y.toFixed(1)} ${endX.toFixed(1)},${endY.toFixed(1)}`);
    line.hidden = false; line.style.display = "";
    /* 0717 用户验收修:标牌被边界钳位(目标格投影贴视口边/被左栏遮)时,连线距离可观测——
       QA 据此断言"标牌要么贴格、要么有可见引线指回格位",错位不再只能靠肉眼撞见。 */
    lastBeaconAudit = {slot: frame.slot.slice(), anchor: {x: anchor.x, y: anchor.y},
      beacon: {left, top, width: rect.width, height: rect.height},
      dist: Math.hypot(endX - anchor.x, endY - anchor.y),
      clamped: Math.abs(top - (anchor.y - rect.height / 2)) > .5 || (left !== anchor.x + 22 && left !== anchor.x - rect.width - 22),
      leaderVisible: !line.hidden && line.style.display !== "none"};
  }

  function canvasSurface(id) {
    const canvas = byId(id), rect = canvas.getBoundingClientRect(), ratio = Math.min(root.devicePixelRatio || 1, 2);
    if (rect.width < 2 || rect.height < 2) return null;
    const width = Math.round(rect.width * ratio), height = Math.round(rect.height * ratio);
    if (canvas.width !== width || canvas.height !== height) { canvas.width = width; canvas.height = height; }
    const context = canvas.getContext("2d"); context.setTransform(ratio, 0, 0, ratio, 0, 0); context.clearRect(0, 0, rect.width, rect.height);
    return {context, width: rect.width, height: rect.height};
  }

  /* 0717 #26-1/2:2D 三联同帧对比——SEQ|NEAR|SCORE 同一进度并排推进,同帧直视分化
     (SEQ 竖条纹 vs SCORE 低层横铺);热门货画角标。lastMapAudit 供 QA。 */
  let lastMapAudit = null;
  function drawGridPanel(g, frame, laneId, px, py, panel) {
    const model = models.get(laneId), grid = model.grids[frame.managedCount], cell = panel / 20;
    const active = laneId === state.laneId;
    g.fillStyle = "#eef2f4"; g.fillRect(px, py, panel, panel);
    for (let col = 0; col < 20; col += 1) for (let tier = 0; tier < 20; tier += 1) {
      const x = px + col * cell, y = py + (19 - tier) * cell, value = grid[col * 20 + tier];
      if (value === -1) {
        g.fillStyle = "#76848e"; g.fillRect(x + .4, y + .4, cell - .8, cell - .8);
        /* 0716 用户授权修改:斜纹裁剪到本格矩形内,修复放大视图下纹线溢出到相邻货物格的绘制缺陷。 */
        g.save(); g.beginPath(); g.rect(x + .4, y + .4, cell - .8, cell - .8); g.clip();
        g.strokeStyle = "#dce3e7"; g.lineWidth = Math.max(.6, cell * .11);
        for (let d = -cell; d < cell * 2; d += Math.max(2.8, cell * .48)) { g.beginPath(); g.moveTo(x + d, y + cell); g.lineTo(x + d + cell, y); g.stroke(); }
        g.restore();
      } else if (value > 0) {
        g.fillStyle = GRADE_CSS[good(value).grade]; g.fillRect(x + .5, y + .5, cell - 1, cell - 1);
        if (hotGids.has(value)) {
          const notch = Math.max(2.2, cell * .42);
          g.fillStyle = "#ffd400"; g.beginPath(); g.moveTo(x + cell - .5, y + .5);
          g.lineTo(x + cell - .5, y + notch); g.lineTo(x + cell - notch, y + .5); g.closePath(); g.fill();
        }
      }
      if (cell >= 8) { g.strokeStyle = "#c7d0d6"; g.lineWidth = .55; g.strokeRect(x, y, cell, cell); }
    }
    const targetSlot = frame.managedCount < 267 ?
      model.lane.events[Math.min(frame.eventIndex, 266)].decision.selected_slot : null;
    if (targetSlot) {
      const x = px + targetSlot[0] * cell, y = py + (19 - targetSlot[1]) * cell;
      g.strokeStyle = "#ffd400"; g.lineWidth = Math.max(1.6, cell * .22); g.strokeRect(x + .5, y + .5, cell - 1, cell - 1);
    }
    if (active && frame.cargoVisible && ["LADEN_TRAVEL", "STORE_HANDLE"].includes(frame.operation)) {
      const col = clamp(frame.machine.x, 0, 19), tier = clamp(frame.machine.z, 0, 19);
      g.beginPath(); g.arc(px + (col + .5) * cell, py + (19 - tier + .5) * cell, Math.max(2.2, cell * .31), 0, Math.PI * 2);
      g.fillStyle = GRADE_CSS[good(frame.event.gid).grade]; g.fill(); g.strokeStyle = "#ffd400"; g.lineWidth = 1.2; g.stroke();
    }
    g.strokeStyle = active ? "#e7b800" : "#c7d0d6"; g.lineWidth = active ? 2 : 1;
    g.strokeRect(px - .5, py - .5, panel + 1, panel + 1);
    return targetSlot;
  }
  function drawSlotMap(frame) {
    const surface = canvasSurface("slotMap"); if (!surface) return;
    const {context: g, width, height} = surface;
    const gap = 9, labelH = 13;
    /* 0722b:容器窄高(精华条撑满全高)时改纵向排——三张网格各占 ~rail 宽,可读性远高于
       横排三小图;宽扁容器(放大层/低窗)仍横排。mode 字面保持 "tri"(QA 兼容),新增 orientation。 */
    const vertical = height > width * 1.15;
    const targets = {};
    if (vertical) {
      const panel = Math.min(width - 4, (height - (labelH + gap) * 3 - 3) / 3);
      const x0 = (width - panel) / 2;
      ["seq", "near", "score"].forEach((laneId, index) => {
        const py = labelH + 1 + index * (panel + labelH + gap), active = laneId === state.laneId;
        g.font = `${active ? "800" : "700"} 9px "Microsoft YaHei"`; g.textAlign = "left";
        g.fillStyle = active ? "#8a6a00" : "#5d6972";
        g.fillText(`${laneId.toUpperCase()}${active ? " · 当前" : ""}`, x0 + 1, py - 4);
        targets[laneId] = drawGridPanel(g, frame, laneId, x0, py, panel);
      });
    } else {
      const panel = Math.min((width - gap * 2 - 4) / 3, height - labelH - 3);
      const x0 = (width - panel * 3 - gap * 2) / 2, y0 = labelH + 1;
      ["seq", "near", "score"].forEach((laneId, index) => {
        const px = x0 + index * (panel + gap), active = laneId === state.laneId;
        g.font = `${active ? "800" : "700"} 9px "Microsoft YaHei"`; g.textAlign = "left";
        g.fillStyle = active ? "#8a6a00" : "#5d6972";
        g.fillText(`${laneId.toUpperCase()}${active ? " · 当前" : ""}`, px + 1, y0 - 4);
        targets[laneId] = drawGridPanel(g, frame, laneId, px, y0, panel);
      });
    }
    lastMapAudit = {mode: "tri", orientation: vertical ? "v" : "h", managedCount: frame.managedCount,
      activeLane: state.laneId, targets, hotSetSize: hotGids.size};
  }

  /* 0717 #26-4:终态货-格配对差异热力图(SCORE−SEQ 每格热门度差)。满仓守恒下三算法终态占同一
     267 格集合,总量指标数学必然全同——货-格配对是唯一有信息量的终态对比。终态静态,按尺寸画一次;
     canvas 平时藏于放大 overlay,rect 为 0 时跳过。lastDiffAudit 供 QA。 */
  let lastDiffAudit = null;
  function drawDiffMap() {
    const canvas = byId("diffMap"); if (!canvas) return;
    const rect = canvas.getBoundingClientRect(); if (rect.width < 2 || rect.height < 2) return;
    const signature = `${Math.round(rect.width)}x${Math.round(rect.height)}`;
    if (canvas.dataset.drawn === signature) return;
    const surface = canvasSurface("diffMap"); if (!surface) return;
    canvas.dataset.drawn = signature;
    const {context: g, width, height} = surface, size = Math.min(width - 4, height - 4), cell = size / 20;
    const x0 = (width - size) / 2, y0 = (height - size) / 2;
    const seqGrid = models.get("seq").grids[267], scoreGrid = models.get("score").grids[267];
    const diffs = seqGrid.map((seqValue, index) => {
      const scoreValue = scoreGrid[index];
      if (seqValue === -1) return null;
      return (scoreValue > 0 ? good(scoreValue).freq : 0) - (seqValue > 0 ? good(seqValue).freq : 0);
    });
    const maxAbs = Math.max(...diffs.filter(value => value !== null).map(Math.abs), 1e-9);
    let nonZeroCells = 0;
    g.fillStyle = "#f4f6f8"; g.fillRect(x0, y0, size, size);
    for (let col = 0; col < 20; col += 1) for (let tier = 0; tier < 20; tier += 1) {
      const x = x0 + col * cell, y = y0 + (19 - tier) * cell, diff = diffs[col * 20 + tier];
      if (diff === null) { g.fillStyle = "#d7dde1"; g.fillRect(x + .4, y + .4, cell - .8, cell - .8); continue; }
      if (Math.abs(diff) > 1e-9) {
        nonZeroCells += 1;
        const strength = Math.pow(Math.abs(diff) / maxAbs, .55);
        g.fillStyle = diff > 0 ? `rgba(216,148,0,${(.14 + .82 * strength).toFixed(3)})` :
          `rgba(11,111,191,${(.14 + .82 * strength).toFixed(3)})`;
        g.fillRect(x + .4, y + .4, cell - .8, cell - .8);
      }
      if (cell >= 8) { g.strokeStyle = "#cdd5da"; g.lineWidth = .5; g.strokeRect(x, y, cell, cell); }
    }
    g.strokeStyle = "#9ea9b1"; g.lineWidth = 1; g.strokeRect(x0 - .5, y0 - .5, size + 1, size + 1);
    lastDiffAudit = {nonZeroCells, maxAbs: Number(maxAbs.toFixed(3)), cells: 400,
      reservedCells: diffs.filter(value => value === null).length};
  }

  function drawSpeed(frame) {
    const surface = canvasSurface("speed"); if (!surface) return;
    const {context: g, width, height} = surface, left = 28, right = width - 8, top = 8, bottom = height - 12;
    [{label: "X", value: Math.abs(frame.machine.vx), max: VX, color: "#ff000f"},
      {label: "Z", value: Math.abs(frame.machine.vz), max: VZ, color: "#7b2cbf"}].forEach((bar, index) => {
      const y = top + 8 + index * Math.max(15, (bottom - top) / 2); g.fillStyle = "#66717a"; g.font = "9px Consolas"; g.fillText(bar.label, 4, y + 3);
      g.fillStyle = "#e1e6e9"; g.fillRect(left, y - 5, right - left, 8); g.fillStyle = bar.color;
      g.fillRect(left, y - 5, (right - left) * clamp(bar.value / bar.max, 0, 1), 8); g.fillStyle = "#26343e"; g.textAlign = "right";
      g.fillText(`${bar.value.toFixed(2)} m/s`, right, y + 3); g.textAlign = "left";
    });
  }

  function configureDom() {
    /* 0716 深审治理 A+B(用户全面批准,docs/S3算法深审与治理方案_0716.md):
       ①「智能路由」实为硬编码常量,改名「默认策略」;②统计块重排+守恒量披露;③平局兜底与等时区解说。
       样式随 runtime 注入,五个引用页(fill恢复候选/三份版式候选/进度轴候选)同步生效,不改各页 HTML。 */
    const governanceStyle = document.createElement("style");
    governanceStyle.textContent =
      ".statsDelta{position:absolute;top:2px;right:2px;padding:1px 2px;font:800 6.5px/1 Consolas,monospace}" +
      ".statsDelta.better{color:#1d6b2e;background:#e2f2e5}.statsDelta.worse{color:#8a4a00;background:#fdeeda}" +
      "#traceStats .conservedCell{background:#fffbe8;outline:1px dashed #c9a800;outline-offset:-1px}" +
      "#traceStats .conservedCell b{font-size:8.5px}#traceStats .conservedCell small{color:#7a6a00}" +
      "#decisionWrap .tieNote{margin-top:4px;padding:4px 6px;border-left:3px solid #17365d;background:#eef3f8;color:#3c4c5c;font:7.5px/1.35 \"Microsoft YaHei\",sans-serif}" +
      /* 0717 #28:①拟真档说明标签(非控件观感) ②dock 货物大字行的等级色块(色值=A 布局 2D 图例采样色) */
      "#tierFixedTag{display:flex;flex-direction:column;justify-content:center;gap:1px;min-height:25px;padding:2px 8px;box-sizing:border-box;" +
        "border-left:3px solid #e7b800;background:#eef2f5;color:#1c2932;cursor:help}" +
      "#tierFixedTag b{font:700 9.5px/1.15 \"Microsoft YaHei\",sans-serif;white-space:nowrap}" +
      "#tierFixedTag small{font:400 7px/1.1 \"Microsoft YaHei\",sans-serif;color:#68747d;white-space:nowrap}" +
      "#sceneActionText .gradeDot{display:inline-block;width:9px;height:9px;margin-right:5px;vertical-align:-1px}" +
      ".gradeDot.heavy{background:#366786}.gradeDot.mid{background:#4ea9c2}.gradeDot.light{background:#abd1d8}" +
      "#sceneActionText em{font-style:normal}" +
      "#sceneActionText .hotChip{margin-left:7px;padding:1px 5px 2px;background:#fdf3cf;border:1px solid #e0b600;" +
        "color:#5b4a00;font-size:.78em;font-weight:800;white-space:nowrap;vertical-align:1px}" +
      /* 0717 #26-3 冷门送远解说卡 */
      "#decisionWrap .reserveNote{margin-top:4px;padding:4px 6px;border-left:3px solid #b8860b;background:#fdf7e3;" +
        "color:#4c3d10;font:7.5px/1.35 \"Microsoft YaHei\",sans-serif}";
    document.head.append(governanceStyle);
    byId("strategySelect").innerHTML = '<option value="AUTO" selected>默认策略 SCORE</option><option value="score">多目标评分 SCORE</option><option value="near">就近放置 NEAR</option><option value="seq">顺序放置 SEQ</option>';
    /* 0717 #28 用户拍板:锁定下拉在观感上像坏控件——整个换成静态说明标签(非下拉),口径如实:
       本页只有一个已验证数据门;三档拟真是 02_入出闭环 页的功能。 */
    const tierTag = document.createElement("span"); tierTag.id = "tierFixedTag";
    tierTag.innerHTML = "<b>连续填满 · SIM 数据门</b><small>本页固定口径 · 三档拟真见 02 页</small>";
    tierTag.title = "本页为连续填满单一验证口径(加减速 SIM 数据门),不提供档位切换;三档拟真(档1 数据模型 / 档2 加减速 / 档3 综合情景)在 02_入出闭环 页提供";
    byId("tierSelect").replaceWith(tierTag);
    /* 治理 C2:支持情景切换的页面(html[data-s3-scenario-switch],由页面 store 选择器声明)启用
       skew/uniform 双情景下拉,切换=改 URL 参数整页重载(每情景仍是单 payload 队列,验证契约不变);
       冻结页(fill恢复候选/三份版式候选)无标记,保持单 option disabled,行为零变化。 */
    if (document.documentElement.dataset.s3ScenarioSwitch === "1") {
      byId("profileSelect").innerHTML = '<option value="skew">偏斜货流 · 帕累托样本</option><option value="uniform">均匀货流 · 对照情景</option>';
      byId("profileSelect").value = SCENARIO; byId("profileSelect").disabled = false;
      byId("profileSelect").addEventListener("change", event => {
        const search = new URLSearchParams(location.search);
        if (event.target.value === "uniform") search.set("profile", "uniform"); else search.delete("profile");
        location.search = search.toString() ? `?${search.toString()}` : "";
      });
    } else {
      byId("profileSelect").innerHTML = SCENARIO === "uniform" ?
        '<option value="uniform" selected>均匀货流 · 对照情景</option>' :
        '<option value="skew" selected>偏斜货流 · 可复现样本</option>';
      byId("profileSelect").disabled = true;
    }
    byId("traceLoadState").textContent = "数据链已验证";
    byId("railHead").querySelector(".matrix").innerHTML = "20 × 20<br>SIM / 填满";
    /* 0717 #26-1:单图升三联同帧对比 */
    const mapHead = byId("slotMapWrap").querySelector(".mapHead"); mapHead.querySelector("b").textContent = "三算法同帧对比 · 20 × 20";
    mapHead.querySelector("span").textContent = "同批货同进度 · SEQ | NEAR | SCORE · 133 预占同布"; mapHead.querySelector("strong").id = "capacityTotal";
    /* 热门图例只在决赛 01 页(target-card 模式)追加:候选页(冻结观感)加此项会把 1600×900
       下的 slotMapWrap 撑出视口 1.3px(candidate QA viewportsInside 实测),角点绘制不受影响。 */
    const mapKey = byId("slotMapWrap").querySelector(".mapKey");
    if (targetCardMode && mapKey && !mapKey.querySelector(".hotKey")) {
      const hotKey = document.createElement("span"); hotKey.className = "hotKey";
      hotKey.innerHTML = '<i style="background:#ffd400"></i>★ 热门前 20%'; mapKey.append(hotKey);
    }
    byId("slotMapWrap").querySelector(".mapRule span").textContent = "sum 规则：预占 133 格，不属于管理容量";
    const facts = Array.from(byId("railFacts").children); facts[0].querySelector("span").textContent = "已入库 / 267";
    facts[1].querySelector("span").textContent = "入口等待"; facts[2].querySelector("span").textContent = "约束违规";
    const decision = document.createElement("section"); decision.id = "decisionWrap"; decision.setAttribute("aria-label", "当前算法决策依据");
    byId("runtimeControls").after(decision);
    const bookmarks = document.createElement("section"); bookmarks.id = "fillBookmarks"; bookmarks.setAttribute("aria-label", "入库进度");
    bookmarks.innerHTML = '<div class="fillHead"><b>入库进度 · 从空到满</b><span>点击即暂停到已验证快照</span></div><div id="fillBookmarkButtons"></div><div id="fillEvidence"><span><b id="fillManaged">0 / 267</b>管理货</span><span><b id="fillTotal">133 / 400</b>总占用</span><span><b id="fillViol">0</b>违规</span><span><b id="fillSource">SIM</b>证据边界</span></div>';
    decision.after(bookmarks);
    const host = byId("fillBookmarkButtons");
    BOOKMARKS.forEach((count, index) => { const button = document.createElement("button"); button.type = "button"; button.dataset.count = String(count);
      button.innerHTML = `${count} / 267<small>${["0%", "25%", "50%", "75%", "90%", "100%"][index]}</small>`; host.append(button); });
    const release = document.createElement("div"); release.id = "releaseBadge";
    release.innerHTML = "<b>连续填满已验证 · SIM</b>3 种在线算法 · 各 267 件"; viewportEl.append(release);
    const guide = document.createElement("section"); guide.id = "processGuide"; guide.setAttribute("aria-label", "四阶段 trace 的七步演示拆分");
    guide.innerHTML = '<div class="processGuideHead"><b>七步在做什么</b><span>4 阶段 trace · 几何细分</span></div><div id="processGuideRows"></div>';
    DISPLAY_STEPS.forEach((step, index) => { const row = document.createElement("div"); row.className = "processGuideRow"; row.dataset.step = String(index);
      row.innerHTML = `<i>${index + 1}</i><b>${step.label}</b><span>${step.purpose}</span>`; guide.querySelector("#processGuideRows").append(row); });
    byId("insightStack").append(guide);
    byId("reserveRuleBadge").innerHTML = '<span class="in"><i></i>入库路径</span><span class="empty"><i></i>空载回程</span><span class="blocked"><i></i>预占</span><span class="hotlid"><i style="background:#d9ad00"></i>金顶 = 热门前 20%</span>';
    byId("phaseNow").textContent = "入库进度 0 / 267"; byId("phaseClock").textContent = "等待连续回放";

    /* W7(0721 回灌,规格 docs/施工规格_回灌0721.md §1.2):赛马场主版面四区块——同源口径声明条 /
       主区四图标题条 / 赛段比分条 / 终态总分牌 / 30-seed 分布带。全部直接读闭包内 payload/models
       真实数据(数据渲染进 runtime);DOM 顺序不重要,可见次序完全由 html 内 order 样式决定(见
       html[data-s3-layout="A"] 的 #raceBanner 等 order 规则)。 */
    const LANES3 = ["seq", "near", "score"];
    const sameInputSet = new Set(payload.online_lanes.map(lane => lane.shared_input_sha256));
    const raceBanner = document.createElement("div");
    raceBanner.id = "raceBanner"; raceBanner.className = "vPanel"; raceBanner.tabIndex = 0;
    raceBanner.setAttribute("role", "note"); raceBanner.setAttribute("aria-label", "口径声明,聚焦或悬停展开全文");
    /* 0722 §B.1:口径声明压缩为精华条头部一行小字,hover/focus 展开全文——拆成
       raceBannerLine(常显单行)+ raceBannerFull(展开态全文,含原数据抽查子行);
       两者都在 DOM 内,raceBanner.textContent 覆盖全部原文,QA 逐字断言不受影响。 */
    const raceBannerLineText = `三算法同一到达队列 · 同一数据门 · 单 seed ${payload.shared_input_provenance.profile.seed}` +
      `(30-seed 佐证见证据 s3_fill_seed_sweep_${SCENARIO}_2026_2055.json)· SIM`;
    const raceBannerSubText = `数据抽查:三条在线 lane 的 shared_input_sha256 唯一值个数 = ${sameInputSet.size}(应为 1)← payload.online_lanes[].shared_input_sha256(数据源:./s3_fill_store.js)`;
    raceBanner.innerHTML = `<span class="raceBannerLine">${raceBannerLineText}</span>` +
      `<div class="raceBannerFull">${raceBannerLineText}<span style="display:block;margin-top:4px;font:400 8.5px/1.3 Consolas,monospace;color:#8a6a55">${raceBannerSubText}</span></div>`;

    /* 0722 §B.1 新增:当前容量节点三算法关键指标微条(renderRaceMicro 每帧写入,见下方)。 */
    const raceMicroBar = document.createElement("section");
    raceMicroBar.id = "raceMicroBar"; raceMicroBar.setAttribute("aria-label", "当前容量节点三算法关键指标");

    /* 0722 §B.1 新增:SCORE 相对 SEQ 领先徽章——终态数据,一次性计算,不随播放变化。
       复用 expected_retrieval_s(全页反复强调的"回应赛题存取效率"headline 指标)。 */
    const raceLeadBadge = document.createElement("section");
    raceLeadBadge.id = "raceLeadBadge"; raceLeadBadge.setAttribute("aria-label", "SCORE 相对 SEQ 终态领先幅度");
    {
      const seqFinal = models.get("seq").lane.metrics, scoreFinal = models.get("score").lane.metrics;
      const pct = seqFinal.expected_retrieval_s > 0 ?
        (scoreFinal.expected_retrieval_s - seqFinal.expected_retrieval_s) / seqFinal.expected_retrieval_s * 100 : 0;
      const better = pct < 0;
      raceLeadBadge.innerHTML = `<span class="leadLabel">SCORE vs SEQ · 期望取货(终态)</span>` +
        `<b class="leadValue ${better ? "better" : "worse"}">${better ? "▼" : "▲"}${Math.abs(pct).toFixed(1)}%</b>`;
    }

    const raceGridsIntro = document.createElement("div");
    raceGridsIntro.id = "raceGridsIntro"; raceGridsIntro.className = "vPanel";
    raceGridsIntro.innerHTML = '<div class="vHead"><b>主区 · 算法赛马场四图</b><span>SEQ | NEAR | SCORE 同帧三联 + SCORE−SEQ 终态差异热力图</span></div>' +
      '<div class="note">三算法共享同一到达队列与同一 20×20 / 133 预占容量契约(见上方声明);差异只来自放置策略本身,可直接横向对比。差异热力图见下方内嵌卡片。</div>';

    const raceScoreboard = document.createElement("section");
    raceScoreboard.id = "raceScoreboard"; raceScoreboard.className = "vPanel";
    const raceMetrics = [
      {key: "expected_retrieval_s", label: "期望取货 s", digits: 2},
      {key: "round_trip_path_m", label: "累计行程 m", digits: 0}
    ];
    const raceMaxByMetric = {};
    raceMetrics.forEach(m => {
      const vals = [];
      LANES3.forEach(id => models.get(id).lane.checkpoints.forEach(cp => vals.push(cp.metrics_to_date[m.key])));
      raceMaxByMetric[m.key] = Math.max(...vals) || 1;
    });
    const raceRowsHtml = BOOKMARKS.map((count, index) => {
      const cellsHtml = raceMetrics.map(m => {
        const barsHtml = LANES3.map(algo => {
          const cp = models.get(algo).lane.checkpoints.find(item => item.event_count === count);
          const v = cp.metrics_to_date[m.key];
          const pct = (v / raceMaxByMetric[m.key] * 100).toFixed(1);
          return `<div class="raceBarRow" data-algo="${algo}"><span>${algo.toUpperCase()}</span>` +
            `<span class="raceBarTrack"><i style="width:${pct}%"></i></span><span>${v.toFixed(m.digits)}</span></div>`;
        }).join("");
        return `<div><span class="raceMetricLabel">${m.label}</span>${barsHtml}</div>`;
      }).join("");
      return `<div class="raceNode"><span class="nodeLabel">${count} / 267<small>${["0%", "25%", "50%", "75%", "90%", "100%"][index]}</small></span>${cellsHtml}</div>`;
    }).join("");
    const raceViolLine = LANES3.map(id => `${id.toUpperCase()} ${models.get(id).lane.metrics.violations}`).join(" · ");
    raceScoreboard.innerHTML = '<div class="vHead"><b>赛段比分条 · 6 节点 × 三算法</b><span>online_lanes[].checkpoints[].metrics_to_date</span></div>' +
      raceRowsHtml +
      `<div class="spotCheck">说明:violations(约束违规)在数据门中只有终态计数,checkpoint 未逐节点记录该字段,故未在此强行编造逐节点值——终态如实为 0(${raceViolLine}),而 violations 定义上只增不减,终态 0 即蕴含全程各节点亦为 0;完整违规值见下方终态总分牌。</div>`;

    const raceFinalBoard = document.createElement("section");
    raceFinalBoard.id = "raceFinalBoard"; raceFinalBoard.className = "vPanel";
    const finalMetrics = [
      {key: "hot20_retrieval_s", label: "热门取货 s", digits: 2, lowerBetter: true},
      {key: "heavy20_mean_tier", label: "重货均层", digits: 2, lowerBetter: true},
      {key: "lift_work_proxy_kgm", label: "能耗代理 kg·m", digits: 0, lowerBetter: true},
      {key: "expected_retrieval_s", label: "期望取货 s", digits: 2, lowerBetter: true},
      {key: "violations", label: "约束违规", digits: 0, lowerBetter: null},
      {key: "makespan_s", label: "完工 s(三算法恒等)", digits: 0, lowerBetter: null},
      {key: "round_trip_path_m", label: "行程 m(三算法恒等)", digits: 0, lowerBetter: null}
    ];
    const seqMetricsFinal = models.get("seq").lane.metrics;
    const finalBodyRows = finalMetrics.map(m => {
      const cells = LANES3.map(algo => {
        const v = models.get(algo).lane.metrics[m.key];
        const cls = algo === "seq" ? "baseCol" : "";
        let badge = "";
        if (algo !== "seq" && m.lowerBetter !== null && seqMetricsFinal[m.key] > 0) {
          const pct = (v - seqMetricsFinal[m.key]) / seqMetricsFinal[m.key] * 100;
          if (Math.abs(pct) >= .05) {
            const better = m.lowerBetter ? pct < 0 : pct > 0;
            /* 涨跌徽章沿用既有 .statsDelta/.better/.worse(governanceStyle 已定义,见上文);
               表格单元格内需覆盖其绝对定位为随文,覆盖规则见 html 内 .finalMatrix .statsDelta。 */
            badge = ` <em class="statsDelta ${better ? "better" : "worse"}">${pct < 0 ? "▼" : "▲"}${Math.abs(pct).toFixed(1)}%</em>`;
          }
        }
        return `<td class="${cls}">${v.toFixed(m.digits)}${badge}</td>`;
      }).join("");
      return `<tr><td>${m.label}</td>${cells}</tr>`;
    }).join("");
    raceFinalBoard.innerHTML = '<div class="vHead"><b>终态总分牌 · 三算法并排</b><span>online_lanes[].metrics(终态)</span></div>' +
      `<table class="finalMatrix"><thead><tr><th>指标</th><th class="baseCol">SEQ · 基线</th><th>NEAR</th><th>SCORE</th></tr></thead><tbody>${finalBodyRows}</tbody></table>` +
      `<div class="spotCheck">数据抽查:屏上 SCORE 期望取货 = ${models.get("score").lane.metrics.expected_retrieval_s.toFixed(3)} s ← online_lanes[algorithm.id=score].metrics.expected_retrieval_s(数据源:./s3_fill_store.js)</div>`;

    const seedBand = document.createElement("section");
    seedBand.id = "raceSeedBand"; seedBand.className = "vPanel";
    seedBand.innerHTML = '<div class="vHead"><b>30-seed 分布带 · 三算法稳健性</b><span>加载中…</span></div>';

    bookmarks.after(raceBanner); raceBanner.after(raceMicroBar); raceMicroBar.after(raceLeadBadge);
    raceLeadBadge.after(raceGridsIntro); raceGridsIntro.after(raceScoreboard);
    raceScoreboard.after(raceFinalBoard); raceFinalBoard.after(seedBand);

    /* 治理 C2 两情景兼容:30-seed 证据文件按 SCENARIO 切换(skew/uniform),真 fetch 不编造。 */
    fetch(`../evidence/s3_fill_seed_sweep_${SCENARIO}_2026_2055.json`).then(response => {
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return response.json();
    }).then(sweep => {
      const seedMetrics = [
        {key: "expected_retrieval_s", label: "期望取货 s", digits: 2},
        {key: "hot20_retrieval_s", label: "热门取货 s", digits: 2},
        {key: "heavy20_mean_tier", label: "重货均层", digits: 2},
        {key: "lift_work_proxy_kgm", label: "能耗代理 kg·m", digits: 0}
      ];
      const seedRowsHtml = seedMetrics.map(m => {
        const perMetric = sweep.summary.per_metric[m.key].stats;
        const globalMax = Math.max(perMetric.seq.max, perMetric.near.max, perMetric.score.max);
        const globalMin = Math.min(perMetric.seq.min, perMetric.near.min, perMetric.score.min);
        const span = Math.max(1e-9, globalMax - globalMin);
        const barsHtml = ["seq", "near", "score"].map(algo => {
          const s = perMetric[algo];
          const left = (s.min - globalMin) / span * 100, width = Math.max(1, (s.max - s.min) / span * 100);
          const meanLeft = (s.mean - globalMin) / span * 100;
          return `<div class="seedBarLine"><span>${algo.toUpperCase()}</span><span class="seedTrack">` +
            `<i class="seedRange" style="left:${left.toFixed(1)}%;width:${width.toFixed(1)}%"></i>` +
            `<i class="seedMean" style="left:${meanLeft.toFixed(1)}%"></i></span><span>均值 ${s.mean.toFixed(m.digits)}</span></div>`;
        }).join("");
        return `<div class="seedRow"><div class="sHead">${m.label}</div>${barsHtml}</div>`;
      }).join("");
      seedBand.innerHTML = `<div class="vHead"><b>30-seed 分布带 · 三算法稳健性</b><span>seed ${sweep.seeds[0]}–${sweep.seeds[sweep.seeds.length - 1]} · case=${sweep.case}</span></div>` +
        seedRowsHtml +
        `<div class="note">条形范围 = min–max(数据文件字段,非 P50 分位数;文件未提供分位数,如实以 min/mean/max 呈现,竖线=均值);对应本页当前展示单 seed(${payload.shared_input_provenance.profile.seed})作为 30-seed 中的一个样本点。</div>` +
        `<div class="spotCheck">数据抽查:SCORE 期望取货 30-seed 均值 = ${sweep.summary.per_metric.expected_retrieval_s.stats.score.mean.toFixed(3)} s(min ${sweep.summary.per_metric.expected_retrieval_s.stats.score.min.toFixed(2)} / max ${sweep.summary.per_metric.expected_retrieval_s.stats.score.max.toFixed(2)}) ← 真 fetch ../evidence/s3_fill_seed_sweep_${SCENARIO}_2026_2055.json summary.per_metric.expected_retrieval_s.stats.score</div>`;
      root.__S3_FILL_SEED_BAND_READY__ = true;
    }).catch(error => {
      seedBand.innerHTML = `<div class="vHead"><b>30-seed 分布带</b><span style="color:#b71c1c">加载失败</span></div><div class="note">${String(error)}</div>`;
      root.__S3_FILL_SEED_BAND_READY__ = "error";
      console.error("[01] 30-seed fetch 失败", error);
    });
  }

  configureDom();

  const state = {requested: "AUTO", laneId: "score", model: models.get("score"), elapsed: 0, idleCount: 0,
    paused: true, multiplier: 1, lastNow: null, raf: null};

  function laneForRequest(requested) { return requested === "AUTO" ? "score" : requested; }

  function renderDecision(frame) {
    const lane = state.model.lane, event = frame.event, host = byId("decisionWrap"), selected = event.decision.selected_slot;
    const reason = state.laneId === "seq" ? "按列优先选择首个可用格" : state.laneId === "near" ? "选择双轴行程时间最短的可用格" :
      "固定四项权重的总分最小；页面启动默认展示本策略";
    if (frame.idle && frame.managedCount === 267) {
      host.innerHTML = '<div class="dHead"><b>连续填满完成</b><span>267 / 267 · SIM</span></div>' +
        '<div class="candidateTop">400 / 400 总占用；已无下一件货物或候选货位。</div>';
      return;
    }
    const audit = state.model.decisionEvidence.events[event.event_index - 1], top3 = audit.top3;
    const score = event.decision.selected_score;
    const candidateRows = top3.map(item => {
      const slot = `${String(item.slot[0]).padStart(2, "0")} / ${String(item.slot[1]).padStart(2, "0")}`;
      const objective = state.laneId === "score" ? `总分 ${Number(item.score_terms.score_total).toFixed(4)}` :
        state.laneId === "near" ? `行程 ${Number(item.objective_value).toFixed(2)} s` : `顺序键 ${item.objective_value}`;
      return `<div class="cand${item.selected ? " selected" : ""}" title="单程 ${Number(item.path_one_way_m).toFixed(1)} m；双轴时间 ${Number(item.travel_time_s).toFixed(2)} s">` +
        `<b>第 ${item.rank} 名</b><span>${slot}</span><span>${objective}</span><em>${item.selected ? "选中" : "候选"}</em></div>`;
    }).join("");
    /* 平局兜底披露(治理 B):NEAR 85.8% / SCORE 73.8% 的事件选中格与其他货位目标值并列,
       屏上如实给出并列组人数与兜底排序键,并解释等时区的结构性根因(VZ=0.5 为 VX=2.0 的 1/4)。 */
    const top1 = top3[0];
    const tieNote = state.laneId !== "seq" && Number(top1.tie_size) > 1 ?
      `<div class="tieNote" role="note">${state.laneId === "near" ?
        `行程 ${Number(top1.travel_time_s).toFixed(2)} s 由 ${top1.tie_size} 个货位并列，按更低层、更小列落位。` :
        `总分 ${Number(top1.score_terms.score_total).toFixed(4)} 由 ${top1.tie_size} 个货位并列，按更短行程、更低层、更小列落位。`}` +
      "等时区现象：垂直限速 0.5 m/s 仅为水平 2.0 m/s 的 1/4，多数货位行程由层高主导、与列号无关，并列是结构性结果。</div>" : "";
    const terms = state.laneId === "score" ? top3[0].score_terms : null;
    /* 0717 #26-3 冷门送远解说卡:保留项主导+当前货非热门时,当场讲清"为什么这件货被送远"
       ——对冲开局镜头的直觉冲击(首件 G001 送最远角是设计行为,不是 bug);附同件货 SEQ/NEAR 对照落位。 */
    const reserveNote = (() => {
      if (!terms || frame.idle) return "";
      const weighted = {efficiency: Number(terms.efficiency_weighted), stability: Number(terms.stability_weighted),
        energy: Number(terms.energy_proxy_weighted), reserve: Number(terms.position_reservation_weighted)};
      const reserveDominant = weighted.reserve >= Math.max(weighted.efficiency, weighted.stability, weighted.energy);
      const cargo = good(event.gid);
      if (!reserveDominant || hotGids.has(event.gid)) return "";
      const slotText = value => `(${String(value[0]).padStart(2, "0")},${String(value[1]).padStart(2, "0")})`;
      const seqSlot = models.get("seq").lane.events[event.event_index - 1].decision.selected_slot;
      const nearSlot = models.get("near").lane.events[event.event_index - 1].decision.selected_slot;
      return `<div class="reserveNote" role="note">冷门货让位机理：${cargo.name} 频次 ${cargo.freq.toFixed(2)}(非热门），` +
        `四项贡献中位置保留项最大（${weighted.reserve.toFixed(4)}）——低频货被主动推向远端，近端货位为后续热门货保留。` +
        `同件货对照：SEQ 落 ${slotText(seqSlot)} · NEAR 落 ${slotText(nearSlot)} · SCORE 落 ${slotText(selected)}。` +
        `${event.event_index === 1 ? "开局首件即此机理的最直观案例：用远端一格换取全局热门近置（终点统计的热门取货角标即其收益）。" : ""}</div>`;
    })();
    const breakdown = terms ? `<div class="scoreBreakdown" aria-label="选中货位评分分项">` +
      `<span title="效率项：频次与双轴行程时间的加权贡献">效率<b>${Number(terms.efficiency_weighted).toFixed(4)}</b></span>` +
      `<span title="稳定项：重量与层位耦合的加权贡献；越小越优">稳定<b>${Number(terms.stability_weighted).toFixed(4)}</b></span>` +
      `<span title="能耗代理项：重量与提升高度的加权贡献；SIM 代理，不是现场电表值">能耗代理<b>${Number(terms.energy_proxy_weighted).toFixed(4)}</b></span>` +
      `<span title="位置保留项：为后续货物保留高价值近端货位的加权贡献">位置保留<b>${Number(terms.position_reservation_weighted).toFixed(4)}</b></span></div>` +
      `<div class="scoreFactorNote" role="note">稳定与能耗代理共用“载重×层高”原始因子，仅权重不同；不可视为两项独立证据。</div>` : "";
    host.innerHTML = `<div class="dHead"><b>${state.requested === "AUTO" ? "默认策略 SCORE" : LANE_LABEL[state.laneId]}</b><span>逐件在线 · SIM</span></div>` +
      `<div class="decisionLine"><span>选择依据</span><b>${reason}</b></div>` +
      `<div class="decisionLine"><span>${frame.idle && frame.managedCount === 267 ? "终点" : "下一目标"}</span><b>${frame.slot ? `${String(selected[0]).padStart(2, "0")} / ${String(selected[1]).padStart(2, "0")}` : "400 / 400 已满"}</b></div>` +
      `<div class="decisionLine"><span>候选审计</span><b>${audit.legal_count} 个合法 · 排除 ${audit.rejected_count}</b></div>` +
      `<div class="candidates" aria-label="最多三个已审计合法候选">${candidateRows}</div>${tieNote}${reserveNote}${breakdown}` +
      `<div class="candidateTop">第 1 名与实际货位、${score === null ? "排序依据" : `总分 ${Number(score).toFixed(4)}`}、审计引用逐项一致；临近满仓时如实显示不足 3 个候选。</div>`;
  }

  function renderStats() {
    /* 治理 A(0716 深审)+ C1 修正(0717 跑批):指标顺序按「能区分算法的在前」重排;
       期望取货在本展示种子(2026)恰为 SEQ 占优,但 30 种子跑批中 SCORE 四项均值全部最优
       (evidence/s3_fill_seed_sweep_skew_2026_2055.json)——title 如实给双口径,不粉饰单种子角标;
       完工时长/总行程对落位顺序数学守恒,单列为守恒量格预讲。角标 = 相对 SEQ 基线,本组指标越低越好。 */
    const metrics = state.model.lane.metrics, host = byId("traceStats");
    const seqMetrics = models.get("seq").lane.metrics;
    const deltaBadge = (value, base) => {
      if (state.laneId === "seq" || !(base > 0)) return "";
      const pct = (value - base) / base * 100;
      if (Math.abs(pct) < .005) return "";
      return `<em class="statsDelta ${pct < 0 ? "better" : "worse"}">${pct < 0 ? "▼" : "▲"}${Math.abs(pct).toFixed(1)}%</em>`;
    };
    host.innerHTML = `<div class="statsHead"><b>批次 KPI(终态)</b><span>单种子 · 连续入库 · SIM</span></div><div class="statsGrid">` +
      `<button class="metricHelp" title="访问频次前 20% 热门货物的期望取货时间；把高频货放近端货位的直接收益(30 种子跑批方向一致)。角标为相对 SEQ 基线的变化，▼ 更优"><b>${metrics.hot20_retrieval_s.toFixed(2)} s</b><small>热门取货 ⓘ</small>${deltaBadge(metrics.hot20_retrieval_s, seqMetrics.hot20_retrieval_s)}</button>` +
      `<button class="metricHelp" title="最重 20% 货物的平均层位，越低越稳(降低重心；30 种子跑批方向一致)"><b>${metrics.heavy20_mean_tier.toFixed(2)}</b><small>重货均层 ⓘ</small>${deltaBadge(metrics.heavy20_mean_tier, seqMetrics.heavy20_mean_tier)}</button>` +
      `<button class="metricHelp" title="Σ 重量×提升高度，单位 kg·m；SIM 能耗代理，不是现场电表值(30 种子跑批方向一致)"><b>${Math.round(metrics.lift_work_proxy_kgm)}</b><small>能耗代理 kg·m ⓘ</small>${deltaBadge(metrics.lift_work_proxy_kgm, seqMetrics.lift_work_proxy_kgm)}</button>` +
      `<button class="metricHelp" title="${SCENARIO === "uniform" ?
        "全部 267 件的频次加权期望取货时间。本页为均匀货流对照情景(单种子 2026)：热门不突出，分层红利天然小，三算法趋同本身就是适用条件的诚实披露；30 种子稳健性跑批中 SCORE 均值仍最优(21.34 vs SEQ 21.69 s)但幅度小于偏斜情景——证据 evidence/s3_fill_seed_sweep_uniform_2026_2055.json" :
        "全部 267 件的频次加权期望取货时间。本页为单种子(2026)可复现样本，该种子恰 SEQ 占优；30 种子稳健性跑批(2026–2055)中 SCORE 均值最优(20.57 vs SEQ 21.70 s)，四项指标全部领先——证据 evidence/s3_fill_seed_sweep_skew_2026_2055.json"}"><b>${metrics.expected_retrieval_s.toFixed(2)} s</b><small>期望取货 ⓘ</small>${deltaBadge(metrics.expected_retrieval_s, seqMetrics.expected_retrieval_s)}</button>` +
      `<button class="metricHelp" title="本连续入库数据门的硬约束违规"><b>${metrics.violations}</b><small>约束违规 ⓘ</small></button>` +
      `<button class="metricHelp conservedCell" title="守恒量：填满口径下三种算法终态占据同一批 267 个货位，完工时长与总行程只取决于货位集合与同批货物，数学上必然三算法相等——能区分算法的是取货侧与分布侧指标"><b>${Math.round(metrics.makespan_s)} s · ${Math.round(metrics.round_trip_path_m)} m</b><small>完工/行程 · 三算法恒等 ⓘ</small></button></div>`;
  }

  /* W7(0721 回灌 §1.3):决策解剖——评分瀑布 + Top-3 候选对比,固定读 SCORE lane(与右上角
     算法下拉当前驱动 3D/2D 的算法各自独立;非 SCORE 算法没有 score_terms,解剖室口径固定拆 SCORE)。
     并入放大层(#s3MapOverlay 内的 #scoreAnatomy,由 interactions.js 创建);该容器在本函数首次
     调用时可能尚不存在(interactions.js 晚于本文件加载),故判空跳过,后续每帧重试。 */
  function renderScoreAnatomy(frame) {
    const host = byId("scoreAnatomy"); if (!host) return;
    const scoreModel = models.get("score"), idx = frame.eventIndex;
    const audit = scoreModel.decisionEvidence.events[idx], top1 = audit.top3[0], terms = top1.score_terms;
    const scoreEvent = scoreModel.lane.events[idx], cargo = good(scoreEvent.gid);
    const weights = payload.score_policy.weights;
    const FACTORS = [
      {key: "efficiency", label: "效率(频次×行程)"},
      {key: "stability", label: "稳定(重量×层高)"},
      {key: "energy_proxy", label: "能耗代理(重量×提升高度)"},
      {key: "position_reservation", label: "位置保留(为后续热门货让位)"}
    ];
    const waterfallRows = FACTORS.map((f, index) => {
      const raw = terms[`${f.key}_raw`], weighted = terms[`${f.key}_weighted`];
      const pct = terms.score_total > 0 ? weighted / terms.score_total * 100 : 0;
      return `<div class="waterfallRow" data-zero="${weighted <= 0}"><div class="wHead"><b>${f.label}</b>` +
        `<span>raw ${raw.toFixed(4)} × w ${weights[index]} = ${weighted.toFixed(4)}</span></div>` +
        `<div class="waterfallTrack"><i style="width:${Math.max(1.5, pct)}%"></i></div></div>`;
    }).join("");
    const top3Rows = audit.top3.map(item => {
      const slot = `${String(item.slot[0]).padStart(2, "0")} / ${String(item.slot[1]).padStart(2, "0")}`;
      return `<tr${item.selected ? ' class="selectedRow"' : ""}><td>第 ${item.rank} 名${item.selected ? " · 选中" : ""}</td><td>${slot}</td>` +
        `<td>${Number(item.objective_value).toFixed(4)}</td><td>${Number(item.travel_time_s).toFixed(2)} s</td><td>${item.tie_size}</td></tr>`;
    }).join("");
    host.innerHTML = `<div class="vPanel"><div class="vHead"><b>当前件评分瀑布 · SCORE 算法</b><span>事件 ${idx + 1} / 267 · ${cargo.name}(${GRADE_LABEL[cargo.grade] || cargo.grade})</span></div>` +
      waterfallRows +
      `<div class="normGauges"><div><b>${Number(terms.f_norm).toFixed(3)}</b><span>f_norm 频次归一</span></div>` +
      `<div><b>${Number(terms.t_norm).toFixed(3)}</b><span>t_norm 行程归一</span></div>` +
      `<div><b>${Number(terms.w_norm).toFixed(3)}</b><span>w_norm 重量归一</span></div></div>` +
      `<div class="scoreTotalLine"><span>score_total(四项加权和)</span><b>${Number(terms.score_total).toFixed(4)}</b></div>` +
      `<div class="spotCheck">数据抽查:score_total = ${Number(terms.score_total).toFixed(6)} ← decision_evidence.lanes[score].events[${idx}].top3[0].score_terms.score_total(数据源:./s3_fill_store.js)</div></div>` +
      `<div class="vPanel"><div class="vHead"><b>Top-3 候选对比 · SCORE 算法</b><span>legal ${audit.legal_count} · rejected ${audit.rejected_count}</span></div>` +
      `<table class="top3Table"><thead><tr><th>名次</th><th>货位</th><th>总分</th><th>双轴时间</th><th>并列数</th></tr></thead><tbody>${top3Rows}</tbody></table>` +
      `<div class="note">总分 = score_terms.score_total(经 objective_value 通用字段读出);并列数(tie_size)>1 表示该名次由多个货位并列,按结构化兜底键落位(等时区现象:垂直限速仅为水平 1/4)。</div></div>`;
  }

  /* 0722 §B.1:精华条「当前容量节点三算法关键指标微条」——找最近已过的容量节点(书签),
     复用赛段比分条(raceScoreboard)同款 checkpoints.metrics_to_date 数据源与横条渲染手法,
     只是把六节点压缩为当前一节点、只展示 expected_retrieval_s 一项(全页反复强调的
     headline 指标),避免与放大层的完整赛段比分条重复。宿主 #raceMicroBar 不存在时安全跳过
     (与 renderScoreAnatomy 的判空模式一致)。 */
  function renderRaceMicro(frame) {
    const host = byId("raceMicroBar"); if (!host) return;
    const LANES3 = ["seq", "near", "score"];
    const count = BOOKMARKS.filter(mark => mark <= frame.managedCount).pop() ?? 0;
    const index = BOOKMARKS.indexOf(count);
    /* 0722b:恢复双指标(期望取货 + 累计行程)——rail 撑满后空间富余,单指标显空;
       两组各自独立归一化,口径与赛段比分全表(弹层)一致。 */
    const METRICS2 = [
      {key: "expected_retrieval_s", label: "期望取货 s", digits: 2},
      {key: "round_trip_path_m", label: "累计行程 m", digits: 0}
    ];
    const groupsHtml = METRICS2.map(metric => {
      const rows = LANES3.map(id => {
        const checkpoint = models.get(id).lane.checkpoints.find(item => item.event_count === count);
        return {id, v: checkpoint.metrics_to_date[metric.key]};
      });
      const max = Math.max(...rows.map(row => row.v)) || 1;
      const barsHtml = rows.map(row => `<div class="raceBarRow" data-algo="${row.id}"><span>${row.id.toUpperCase()}</span>` +
        `<span class="raceBarTrack"><i style="width:${(row.v / max * 100).toFixed(1)}%"></i></span><span>${row.v.toFixed(metric.digits)}</span></div>`).join("");
      return `<div class="microGroup"><div class="microHead"><b>当前节点三算法 · ${metric.label}</b>` +
        `<span>${count} / 267 · ${["0%", "25%", "50%", "75%", "90%", "100%"][index]}</span></div>${barsHtml}</div>`;
    }).join("");
    host.innerHTML = groupsHtml;
  }

  /* W7(0721 回灌 §1.4):证据抽屉数据源——validator.checks 18 项 + 当前 lane 的 checkpoints 哈希链 6 节点
     + 终态账本(不含 fixed_score_diagnostic_total) + 口径与边界卡。按需调用(抽屉展开时才算),
     不是每帧轮询;interactions.js 的 toggleEvidence() 负责把这份结构化数据渲成抽屉 HTML。 */
  function auditDetail() {
    const laneId = state.laneId, lane = state.model.lane;
    const checks = Object.keys(payload.validator.checks).map(name => ({name, pass: payload.validator.checks[name] === true}));
    const checkpoints = lane.checkpoints.map(cp => ({
      eventCount: cp.event_count, label: cp.label, phase: cp.phase,
      auditPrefix12: cp.audit_prefix_sha256.slice(0, 12), totalUnavailable: cp.total_unavailable
    }));
    const m = lane.metrics, entry = payload.registry.active_entry, approval = entry.frontend_binding_approval;
    return {
      laneId, laneLabel: LANE_LABEL[laneId],
      validatorModule: payload.validator.module, validatorScope: payload.validator.scope,
      checks, checksPassCount: checks.filter(item => item.pass).length,
      checkpoints,
      ledger: {managedFillRatio: m.managed_fill_ratio, totalOccupancyRatio: m.total_occupancy_ratio,
        placed: m.placed, violations: m.violations, makespanS: m.makespan_s},
      boundary: {evidenceBoundary: entry.evidence_boundary, approvedAtUtc: approval.approved_at_utc,
        registryStatus: entry.status, testPassed: approval.test_result.passed,
        testTotal: approval.test_result.passed + approval.test_result.failed,
        arrivalModel: payload.shared_input_provenance.arrival_model}
    };
  }

  function updatePhaseRail(frame) {
    const event = frame.event, host = byId("phaseSegments"), scale = byId("phaseTimeScale");
    if (!host.dataset.fillBuilt) {
      host.replaceChildren(); scale.replaceChildren();
      DISPLAY_STEPS.forEach((step, index) => { const span = document.createElement("span"); span.className = "phaseSeg";
        span.innerHTML = `${index + 1}<span class="phaseName">${step.short}</span><small class="phaseDuration">--</small>`; span.title = step.purpose; host.append(span);
        const part = document.createElement("span"); part.className = `phaseTimePart phaseTone${index + 1}`; scale.append(part); });
      const cursor = document.createElement("i"); cursor.id = "phaseTimeCursor"; scale.append(cursor); host.dataset.fillBuilt = "true";
    }
    const simDurations = displayDurations(event), presentationDurations = displayDurations(event, true),
      total = simDurations.reduce((sum, value) => sum + value, 0), activeIndex = displayStepIndex(frame);
    Array.from(host.children).forEach((element, index) => { element.classList.toggle("active", !frame.idle && index === activeIndex);
      element.querySelector(".phaseDuration").textContent = `${simDurations[index].toFixed(1)}s`;
      element.title = `${DISPLAY_STEPS[index].purpose}；SIM ${simDurations[index].toFixed(1)} s；演示 ${presentationDurations[index].toFixed(2)} s`; });
    let completed = 0;
    Array.from(scale.querySelectorAll(".phaseTimePart")).forEach((element, index) => {
      element.style.width = `${simDurations[index] / total * 100}%`; element.classList.toggle("active", !frame.idle && index === activeIndex);
      if (!frame.idle && index < activeIndex) completed += simDurations[index];
    });
    const activeStep = activeIndex < 0 ? null : DISPLAY_STEPS[activeIndex];
    const localProgress = activeStep ? clamp((frame.phaseProgress - activeStep.p0) / (activeStep.p1 - activeStep.p0), 0, 1) : 0;
    const current = frame.idle ? 0 : simDurations[activeIndex] * localProgress;
    byId("phaseTimeCursor").style.left = `${frame.idle ? frame.managedCount === 267 ? 100 : 0 : (completed + current) / total * 100}%`;
    byId("phaseNow").textContent = frame.idle ? `入库进度 ${frame.managedCount} / 267` : `步骤 ${activeIndex + 1}/7 · ${activeStep.label}`;
    /* 0717 用户验收:口径句不常驻,收进 title(hover 可见);常显只留本件 SIM 时长。 */
    byId("phaseClock").textContent = `本件 SIM ${total.toFixed(1)} s`;
    byId("phaseClock").title = "七步为 4 阶段 trace 按几何与货叉阈值细分的展示口径,不是七个原生时间戳";
    Array.from(byId("processGuideRows").children).forEach((row, index) => {
      row.classList.toggle("active", !frame.idle && index === activeIndex);
      row.title = `${DISPLAY_STEPS[index].purpose}；SIM ${simDurations[index].toFixed(1)} s；演示 ${presentationDurations[index].toFixed(2)} s`;
    });
  }

  function updateText(frame) {
    const item = good(frame.event.gid);
    byId("factCycle").textContent = `${frame.managedCount} / 267`; byId("factQueue").textContent = "0"; byId("factAlarm").textContent = "0";
    byId("capacityTotal").textContent = `${payload.capacity.preoccupied_slots + frame.managedCount} / 400`;
    byId("fillManaged").textContent = `${frame.managedCount} / 267`; byId("fillTotal").textContent = `${133 + frame.managedCount} / 400`;
    byId("fillViol").textContent = String(state.model.lane.metrics.violations); byId("fillSource").textContent = "SIM";
    byId("xValue").textContent = `${frame.machine.x.toFixed(2)} m`; byId("zValue").textContent = `${frame.machine.z.toFixed(2)} m`; byId("forkValue").textContent = `${forkExtension.toFixed(2)} m`;
    /* W6:双轴速度并入轴状态行(轨道+数字),口径与 02 s3_ac_runtime.js 同源;F 轴无速度概念,不接。 */
    [["xVel", frame.machine.vx, VX], ["zVel", frame.machine.vz, VZ]].forEach(([id, value, vMax]) => {
      const numEl = byId(id), trackEl = byId(`${id}Track`);
      if (!numEl) return;
      const speed = Math.abs(value);
      numEl.textContent = `${speed.toFixed(2)} m/s`;
      if (trackEl) trackEl.style.setProperty("--vfill", `${Math.min(100, speed / vMax * 100).toFixed(1)}%`);
    });
    byId("xFill").style.setProperty("--fill", `${frame.machine.x / 19 * 100}%`); byId("zFill").style.setProperty("--fill", `${frame.machine.z / 19 * 100}%`);
    byId("forkFill").style.setProperty("--fill", `${forkExtension / FORK_MAX * 100}%`);
    /* W6(0720 照 02 语言重做):大字行只留步骤+货名(与 02 sceneActionText 同构;七步条已迁回右栏,
       不再需要在此兼职承担步骤名)。货物全量属性(重量/体积/等级/热冷/热度/排名)下沉到
       sceneCargoMeta 芯片行——字段口径未变(weight_kg/volume_m3/grade/freq 均为数据门真实字段,
       01 无 freq_true,同义用 freq;不虚构任何字段)。目标格信息仍归 dock 目标货位卡,不重复。 */
    const stepIndex = displayStepIndex(frame), stepLabel = stepIndex >= 0 ? DISPLAY_STEPS[stepIndex].label : "";
    byId("sceneActionText").textContent = frame.idle
      ? (frame.managedCount === 267 ? "连续填满完成 · 267 / 267" : `入库进度 · 已入库 ${frame.managedCount} / 267`)
      : `${stepLabel} · ${item.name}`;
    byId("sceneActionMeta").textContent = frame.idle ? "已验证快照 · SIM" : `SIM ${frame.simTime.toFixed(1)} s`;
    const metaHost = byId("sceneCargoMeta");
    if (frame.idle) {
      metaHost.textContent = `${133 + frame.managedCount} / 400 总占用 · 违规 0`;
    } else {
      const isHot = hotGids.has(item.gid);
      const rank = freqRankByGid.get(item.gid);
      const rankText = rank ? `第 ${rank}/267 名` : "名次未知";
      metaHost.innerHTML = `<span class="cgChip cgWeight">${item.weight_kg.toFixed(1)} kg</span>` +
        `<span class="cgChip cgVolume">${Number(item.volume_m3).toFixed(2)} m³</span>` +
        `<span class="cgChip cgGrade-${item.grade}">${GRADE_LABEL[item.grade] || item.grade}</span>` +
        `<span class="cgChip ${isHot ? "cgHot" : "cgCold"}">${isHot ? "热门件 · 前20%" : "非热门"}</span>` +
        `<span class="cgRank">访问频次 ${item.freq.toFixed(2)} · ${rankText}</span>` +
        `<span class="cgTime">第 ${frame.eventIndex + 1} / 267 件 · 归属 ${OWNER_LABEL[frame.cargoOwner] || frame.cargoOwner}</span>`;
    }
    Array.from(byId("fillBookmarkButtons").querySelectorAll("button")).forEach(button =>
      button.setAttribute("aria-current", String(Number(button.dataset.count) === frame.managedCount && frame.idle)));
  }

  function renderFrame(frame) {
    lastFrame = frame; setInventory(frame.rows, state.laneId, frame.managedCount);
    if (frame.idle && frame.managedCount === 267) { disposePaths(); pathSignature = ""; }
    else setPaths(frame.event, state.laneId, frame.idle ? null : frame.operation);
    const machineWorld = setMachine(frame); setCargo(frame, machineWorld); setTarget(frame); drawSlotMap(frame); drawSpeed(frame); drawDiffMap();
    /* #28 发光壳呼吸+箭头竖直浮动:相位取演示时钟 state.elapsed(seek 后固定,截图可复现),不用挂钟。 */
    if (targetFx && targetFx.glow.visible) {
      const pulse = (Math.sin(state.elapsed * 2.4) + 1) / 2, live = targetFx.arrow.visible;
      targetFx.glowMat.opacity = live ? .30 + .22 * pulse : .48;
      targetFx.faceMat.opacity = live ? .72 + .26 * pulse : .95;
      if (live) targetFx.arrow.position.z = targetFx.arrow.userData.baseZ - targetFx.floatAmp * pulse;
    }
    renderDecision(frame); renderScoreAnatomy(frame); renderRaceMicro(frame); updatePhaseRail(frame); updateText(frame); renderer.render(scene, camera); layoutTarget(frame);
  }

  function currentFrame() { return state.idleCount === null ? activeFrame(state.model, state.elapsed) : idleFrame(state.model, state.idleCount); }

  function seekBookmark(count) {
    invariant(BOOKMARKS.includes(count), "非法入库进度书签"); state.idleCount = count; state.elapsed = state.model.eventStarts[count];
    state.paused = true; state.lastNow = null;
    renderFrame(currentFrame()); return snapshot();
  }

  function setAlgorithm(requested) {
    const laneId = laneForRequest(requested); invariant(models.has(laneId), "不支持的在线算法");
    const count = state.idleCount === null ? locateSegment(state.model, state.elapsed).segment.eventIndex : state.idleCount;
    state.requested = requested; state.laneId = laneId; state.model = models.get(laneId); state.idleCount = count;
    /* 下拉与实际 lane 保持一致:QA 钩子/书签路径切换算法时同步回写(程序赋值不会再触发 change)。 */
    byId("strategySelect").value = requested;
    state.elapsed = state.model.eventStarts[count]; pathSignature = ""; stockSignature = ""; renderStats(); renderFrame(currentFrame());
  }

  function togglePause() {
    /* 0722 §B.3:「继续」播放钮系上轮(W7 0721 F1)误删——0720 否决单仅「从头回放/导出3D帧/
       总览」三项,不含「继续」。本轮拍板改为进页自动播放 + 顶栏暂停/继续单钮双态(按钮 DOM
       同 02 s3_ac_runtime.js 的 #pauseMotion 写法:textContent + aria-pressed 同步)。
       idle→continuous 转换逻辑不变(0721 遗留,复用勿重写)。 */
    if (state.paused && state.idleCount !== null) {
      if (state.idleCount >= 267) { seekBookmark(0); }
      state.elapsed = state.model.eventStarts[state.idleCount]; state.idleCount = null;
    }
    state.paused = !state.paused; state.lastNow = null;
    const button = byId("playPauseBtn");
    if (button) { button.textContent = state.paused ? "继续" : "暂停"; button.setAttribute("aria-pressed", String(state.paused)); }
  }

  function exportFrame() {
    renderer.render(scene, camera); const link = document.createElement("a");
    link.download = `S3_fill_${state.laneId}_${lastFrame ? lastFrame.managedCount : 0}.png`; link.href = renderer.domElement.toDataURL("image/png"); link.click();
  }

  const defaultPolarLimits = Object.freeze([controls.minPolarAngle, controls.maxPolarAngle]);
  function restoreDefaultCamera() {
    controls.enabled = true; controls.minPolarAngle = defaultPolarLimits[0]; controls.maxPolarAngle = defaultPolarLimits[1];
    camera.up.set(0, 0, 1); return setCamera();
  }

  function setTopologyCamera() {
    const damping = controls.enableDamping; controls.enableDamping = false; controls.enabled = false;
    controls.minPolarAngle = 0; controls.maxPolarAngle = Math.PI;
    camera.up.set(0, 1, 0); controls.target.set(.5, -2.85, 0); camera.position.set(.5, -2.85, 17.5);
    camera.fov = 35; camera.zoom = 1; camera.updateProjectionMatrix(); camera.lookAt(controls.target); controls.update();
    controls.enableDamping = damping; renderer.render(scene, camera); if (lastFrame) layoutTarget(lastFrame);
    return cameraSnapshot();
  }

  function visibleTextDuplicateAudit() {
    const visible = Array.from(document.querySelectorAll("body *")).filter(element => {
      const style = getComputedStyle(element), rect = element.getBoundingClientRect();
      return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0 && element.children.length === 0;
    }).map(element => element.textContent.trim()).filter(Boolean);
    const jobFacts = visible.filter(text => /^G\d{3}.*\d{2}\/\d{2}/.test(text));
    return {jobFactLeafCount: jobFacts.length, jobFacts};
  }

  function topologyProjectionAudit() {
    const rect = renderer.domElement.getBoundingClientRect();
    const project = (x, y, z = .18) => {
      const point = new THREE.Vector3(x, y, z).project(camera);
      const screen = {x: rect.left + (point.x + 1) * rect.width / 2,
        y: rect.top + (1 - point.y) * rect.height / 2};
      screen.inside = point.z >= -1 && point.z <= 1 && screen.x >= rect.left && screen.x <= rect.right &&
        screen.y >= rect.top && screen.y <= rect.bottom; return screen;
    };
    const points = {
      inEntry: project(INFEED.x, INFEED.entryY), inLoad: project(INFEED.x, INFEED.loadY),
      outStart: project(OUTFEED.x, OUTFEED.startY), outExit: project(OUTFEED.x, OUTFEED.endY),
      crossLeft: project(CROSSBAR.xMin, CROSSBAR.y), crossRight: project(CROSSBAR.xMax, CROSSBAR.y),
      io: project(IO.x, IO.y)
    };
    const distance = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);
    return {points, allInside: Object.values(points).every(point => point.inside),
      laneSeparationPx: distance(project(INFEED.x, -3.5), project(OUTFEED.x, -3.5)),
      infeedLengthPx: distance(points.inEntry, points.inLoad), outfeedLengthPx: distance(points.outStart, points.outExit),
      crossbarLengthPx: distance(points.crossLeft, points.crossRight)};
  }

  function snapshot() {
    const frame = lastFrame || currentFrame();
    return {releaseId: payload.release.release_id, bundlePayloadSha256: payload.bundle_payload_sha256,
      requested: state.requested, laneId: state.laneId, paused: state.paused, multiplier: state.multiplier,
      /* 0722 §B.3:自动播放 QA 断言需要一个随时间单调增长的读数;simTime 直接读现有 state.elapsed,
         不新引入并行状态源。 */
      simTime: state.elapsed,
      idle: frame.idle, managedCount: frame.managedCount, totalUnavailable: 133 + frame.managedCount,
      eventIndex: frame.event.event_index, operation: frame.operation, target: frame.slot && frame.slot.slice(),
      inventorySize: frame.rows.length, inventoryGids: frame.rows.map(row => row.gid),
      cargo: {visible: cargo.visible, gid: cargo.visible ? cargo.userData.gid : null, owner: cargo.userData.owner || null,
        position: cargo.position.toArray()}, machine: Object.assign({}, frame.machine), paths: livePaths.map(path => ({key: path.key,
        opacity: path.material.opacity, start: path.points[0], end: path.points[path.points.length - 1]})),
      topology: topologyAudit, topologyProjection: topologyProjectionAudit(), camera: cameraSnapshot(), timingAudit,
      scorePolicyAudit: {sharedLoadHeightFactor: payload.score_policy.known_collinearity.stability_raw_equals_energy_proxy_raw,
        uiRule: payload.score_policy.known_collinearity.ui_rule,
        disclosureVisible: state.laneId !== "score" || Boolean(document.querySelector(".scoreFactorNote")?.textContent.includes("共用“载重×层高”原始因子"))},
      runtimeErrors, duplicateAudit: visibleTextDuplicateAudit(),
      beaconAudit: lastBeaconAudit,
      targetFx: targetFx ? {glowVisible: targetFx.glow.visible, arrowVisible: targetFx.arrow.visible,
        faceVisible: targetFx.face.visible, glowColor: `#${targetFx.glowMat.color.getHexString()}`,
        glowOpacity: Number(targetFx.glowMat.opacity.toFixed(3)),
        glowPosition: targetFx.glow.position.toArray()} : null,
      cargoCard: {headline: byId("sceneActionText").textContent, meta: byId("sceneCargoMeta").textContent,
        /* W6:热门标已随货物属性行下沉到 sceneCargoMeta(.cgHot),不再挂 #sceneActionText */
        hotChipShown: Boolean(document.querySelector("#sceneCargoMeta .cgHot")),
        hotMatches: lastFrame && !lastFrame.idle ?
          Boolean(document.querySelector("#sceneCargoMeta .cgHot")) === hotGids.has(lastFrame.event.gid) : true,
        hotSetSize: hotGids.size},
      targetCard: byId("targetCard") ? {state: byId("targetCardState").textContent,
        slotText: byId("targetCardSlot").textContent, detail: byId("targetCardDetail").textContent,
        done: byId("targetCard").classList.contains("done")} : null,
      mapAudit: lastMapAudit, diffAudit: lastDiffAudit,
      hotVisual: {hotLidCount: hotLidMesh.count,
        hotInventoryCount: lastFrame ? lastFrame.rows.filter(row => hotGids.has(row.gid)).length : 0,
        legendPresent: /热门前 20%/.test(byId("reserveRuleBadge").textContent)},
      reserveNotePresent: Boolean(document.querySelector("#decisionWrap .reserveNote")),
      narrativeAudit: {
        scenario: SCENARIO,
        scenarioSwitchEnabled: !byId("profileSelect").disabled,
        profileSelectValue: byId("profileSelect").value,
        strategyOptionAutoText: byId("strategySelect").querySelector('option[value="AUTO"]').textContent,
        smartRoutingTermHits: (document.body.textContent.match(/智能路由/g) || []).length,
        statsSmallOrder: Array.from(document.querySelectorAll("#traceStats .metricHelp small")).map(el => el.textContent.trim()),
        conservedCellPresent: Boolean(document.querySelector("#traceStats .conservedCell")),
        conservedValuesEqualAcrossLanes: ["seq", "near", "score"].every(id =>
          models.get(id).lane.metrics.makespan_s === models.get("seq").lane.metrics.makespan_s &&
          models.get(id).lane.metrics.round_trip_path_m === models.get("seq").lane.metrics.round_trip_path_m),
        deltaBadgeCount: document.querySelectorAll("#traceStats .statsDelta").length,
        expectedRetrievalMechanismNoted: /30 种子稳健性跑批/.test(Array.from(
          document.querySelectorAll("#traceStats .metricHelp")).map(el => el.title).join("")),
        tieNote: {
          present: Boolean(document.querySelector("#decisionWrap .tieNote")),
          top1TieSize: Number(state.model.decisionEvidence.events[frame.event.event_index - 1].top3[0].tie_size) || null,
          isochroneNoted: /等时区/.test(document.querySelector("#decisionWrap .tieNote")?.textContent || "")
        }
      },
      decisionEvidence: {auditSha256: state.model.decisionEvidence.events[frame.event.event_index - 1].audit_sha256,
        top3: state.model.decisionEvidence.events[frame.event.event_index - 1].top3,
        selectedSlotMatches: JSON.stringify(state.model.decisionEvidence.events[frame.event.event_index - 1].top3[0].slot) ===
          JSON.stringify(frame.event.decision.selected_slot)},
      displayStepIndex: displayStepIndex(frame), displayStepCount: DISPLAY_STEPS.length,
      semantic: {inventoryMatchesManaged: frame.rows.length === frame.managedCount,
        totalMatches: 133 + frame.rows.length === 133 + frame.managedCount,
        fullEndpoint: frame.managedCount !== 267 || frame.rows.length === 267,
        zeroEndpoint: frame.managedCount !== 0 || frame.rows.length === 0}};
  }

  byId("strategySelect").addEventListener("change", event => setAlgorithm(event.target.value));
  byId("playPauseBtn").addEventListener("click", togglePause);
  /* W6(0720,拍板同 02 W1-8):「总览」相机复位按钮与其 DOM 一并删除;resetCamera() 仍留作
     QA 程序化钩子(见下方公开 API,__S3_FILL_QA.resetCamera() 供脚本调用)。
     W7(0721 F1 底座清理):暂停/继续、从头回放、导出3D帧三按钮同法删除——DOM 与专属事件绑定一并去除,
     togglePause()/exportFrame() 保留为 __S3_FILL_QA 程序化钩子;「从头回放」等价于 seekBookmark(0),
     已由既有 fillBookmarkButtons 的 0/267 节点覆盖,不需要单独暴露。默认态维持 paused=true
     (bookmark 0 冻结画面),与既有 QA 确定性快照假设一致;赛段/终态对比改为主交互路径。 */
  byId("playbackSpeed").addEventListener("input", event => { state.multiplier = normalizePlaybackMultiplier(event.target.value); byId("playbackValue").textContent = `${state.multiplier.toFixed(2)}×`; });
  byId("fillBookmarkButtons").addEventListener("click", event => { const button = event.target.closest("button[data-count]"); if (button) seekBookmark(Number(button.dataset.count)); });
  controls.addEventListener("change", () => { if (lastFrame) { renderer.render(scene, camera); layoutTarget(lastFrame); } });
  root.addEventListener("resize", () => { resizeScene(); if (lastFrame) layoutTarget(lastFrame); });

  function animationFrame(now) {
    try {
      if (state.lastNow === null) state.lastNow = now;
      const delta = clamp((now - state.lastNow) / 1000, 0, .2); state.lastNow = now; controls.update();
      if (!state.paused && state.idleCount === null) {
        state.elapsed += delta * state.multiplier;
        if (state.elapsed >= state.model.total) { state.elapsed = state.model.total; state.idleCount = 267; state.paused = true; }
      }
      renderFrame(currentFrame());
    } catch (error) {
      runtimeErrors += 1; state.paused = true; byId("traceErrorHost").hidden = false; byId("traceErrorHost").textContent = error.message;
    }
    state.raf = root.requestAnimationFrame(animationFrame);
  }

  renderStats(); seekBookmark(0);
  /* 0722 §B.3:进页自动播放(就绪后自动 play,与 02 行为对齐)——复用 togglePause() 既有的
     idle→continuous 转换,不新写播放状态机。此刻 state.paused=true/idleCount=0
     (seekBookmark(0) 刚设),togglePause() 调一次即完成"冻结书签→连续播放"且同步顶栏
     按钮文案/aria-pressed。 */
  togglePause();
  root.__S3_FILL_QA = Object.freeze({
    version: "s3-fill-candidate-runtime-v1", snapshot,
    seekBookmark, setAlgorithm, auditDetail,
    /* W7:UI 按钮已删,togglePause/exportFrame 保留为程序化钩子(同 resetCamera 先例)。 */
    togglePause, exportFrame,
    seekEvent(eventIndex, operation, progress) {
      invariant(Number.isInteger(eventIndex) && eventIndex >= 0 && eventIndex < 267 && STEP_ORDER.includes(operation), "seekEvent 参数非法");
      const segment = state.model.segments.find(item => item.eventIndex === eventIndex && item.phase.name === operation);
      invariant(segment, "seekEvent 段不存在"); state.elapsed = segment.d0 + clamp(Number(progress), 0, 1) * segment.duration;
      state.idleCount = null; state.paused = true; state.lastNow = null; renderFrame(currentFrame()); return snapshot();
    },
    setPlaybackMultiplier(value) { state.multiplier = normalizePlaybackMultiplier(value); byId("playbackSpeed").value = String(state.multiplier); byId("playbackValue").textContent = `${state.multiplier.toFixed(2)}×`; return state.multiplier; },
    resetCamera() { restoreDefaultCamera(); renderFrame(currentFrame()); return snapshot(); },
    setTopologyCamera() { setTopologyCamera(); return snapshot(); }
  });
  state.raf = root.requestAnimationFrame(animationFrame);
})(window);
