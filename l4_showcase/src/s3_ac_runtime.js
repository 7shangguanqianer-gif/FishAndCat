/* S3 single-source runtime: one verified sim trace drives 3D and every live datum. */
(function (root, factory) {
  "use strict";
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else {
    root.S3ACRuntime = api;
    api.bootstrap(root);
  }
})(typeof window !== "undefined" ? window : globalThis, function () {
  "use strict";

  const TRACE_SCHEMA = "s3-dynamic-trace-v2";
  const PROCESS_STEPS = [
    "LOAD_IN", "INBOUND_TRAVEL", "STORE_HANDLE", "LINK_TRAVEL",
    "RETRIEVE_HANDLE", "OUTBOUND_TRAVEL", "SCAN_EXIT"
  ];
  const STEP_INDEX = Object.freeze(Object.fromEntries(PROCESS_STEPS.map((name, index) => [name, index])));
  const STEP_LABEL = Object.freeze({
    LOAD_IN: "入口交接", INBOUND_TRAVEL: "载货入库", STORE_HANDLE: "伸叉放货",
    LINK_TRAVEL: "空载联程", RETRIEVE_HANDLE: "伸叉取货",
    OUTBOUND_TRAVEL: "载货回口", SCAN_EXIT: "扫码离场"
  });
  /* 七列窄时间轴只放两字识别词；完整动作名仍用于当前步骤、title 与无障碍标签。 */
  const STEP_SHORT_LABEL = Object.freeze({
    LOAD_IN: "交接", INBOUND_TRAVEL: "入库", STORE_HANDLE: "放货",
    LINK_TRAVEL: "联程", RETRIEVE_HANDLE: "取货",
    OUTBOUND_TRAVEL: "回口", SCAN_EXIT: "扫码"
  });
  const QUEUE_LABEL = "入场前排队";
  const QUEUE_PURPOSE = "入口货物尚未到达交接时刻；此段是 SIM 排队等待，不是输送或货叉动作";
  const STEP_PURPOSE = Object.freeze({
    LOAD_IN: "入口队首货物完成身份交接，进入本周期作业",
    INBOUND_TRAVEL: "X / Z 双轴同步，将入库货送往算法选定货位",
    STORE_HANDLE: "货叉完成放货，下一阶段由库存快照接管该 gid",
    LINK_TRAVEL: "不返回 I/O，直接从存货位联程到取货位",
    RETRIEVE_HANDLE: "从指定货位取出同一 gid，并释放该库存格",
    OUTBOUND_TRAVEL: "携带出库货返回 I/O 交接区",
    SCAN_EXIT: "OUTFEED → SCANNED → EXIT_MASK → CONSUMED 可见闭环"
  });
  const STRATEGY_LABEL = Object.freeze({seq: "SEQ", near: "NEAR", score: "SCORE", awra: "AWRA-LS", cb: "CB", tob: "TOB", AUTO: "AUTO"});
  const EVIDENCE_MODE_LABEL = Object.freeze({random: "RANDOM", seq: "SEQ", near: "NEAR", score: "SCORE",
    awra: "AWRA-LS", cb: "CB→SCORE", tob: "TOB→SCORE", AUTO: "AUTO"});
  const EVIDENCE_MODES = Object.freeze(["random", "seq", "near", "score", "awra", "cb", "tob", "AUTO"]);
  const PROFILE_SCENARIO = Object.freeze({uniform: "E01", skew: "E02", heavy: "E03"});
  const OWNER_LABEL = Object.freeze({
    QUEUE: "入口队列", CARRIER_IN: "载货台·入库", RACK: "货架库存",
    CARRIER_OUT: "载货台·出库", OUTFEED: "出口输送", SCANNED: "扫码确认",
    EXIT_MASK: "离场遮罩", CONSUMED: "闭环完成"
  });
  const PROFILE_LABEL = Object.freeze({uniform: "均匀", skew: "偏斜", heavy: "重货"});
  const GRADE_LABEL = Object.freeze({heavy: "重货", mid: "中货", light: "轻货"});
  const DEFAULT_SIM_RATE = 80;
  /* 真实 VX/VZ/AX/AZ 不变；此比例只把长 trace 压缩为可辨识的画面时间。2×≈旧版 0.55 的节奏。 */
  const DEFAULT_PLAYBACK_SCALE = 0.22;
  const PLAYBACK_MULTIPLIER_MIN = 0.25, PLAYBACK_MULTIPLIER_MAX = 2.0;
  /*
     演示时间与仿真时间严格分层：t0/t1、motionPoint 与 KPI 永远使用原始 sim；
     下列常量只决定观众看到多久。主行程采用同类单调映射，避免旧版 /80 后
     “真实行程一闪而过、非建模扫码补段反而最慢”的轻重倒置。
  */
  const PRESENTATION_TIMING = Object.freeze({
    queueFactor: .004, queueMin: .28, queueMax: .70, loadHandoff: .42,
    travelFactor: .09, travelMin: .60, travelMax: 1.60,
    handle: .66, faultRecovery: .50,
    outfeed: .42, scanned: .18, exitMask: .16, consumed: .08
  });
  const ZERO_STEP_DISPLAY_S = PRESENTATION_TIMING.loadHandoff;
  const MIN_TRAVEL_DISPLAY_S = PRESENTATION_TIMING.travelMin, MIN_HANDLE_DISPLAY_S = PRESENTATION_TIMING.handle;
  const CONSUMED_HOLD_S = PRESENTATION_TIMING.consumed, LOOP_RESET_MASK_S = 0.28;
  const EPS = 1e-9;
  /* DOM 布局落到设备像素时会产生 <0.5 px² 的浮点交叠假象；实际矩形验收仍要求零像素覆盖。 */
  const SCREEN_AREA_EPS = .5;
  const VX = 2.0, VZ = 0.5, AX = 0.5, AZ = 0.3;

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
    return clamp(Math.round(parsed * 4) / 4, PLAYBACK_MULTIPLIER_MIN, PLAYBACK_MULTIPLIER_MAX);
  }

  function effectivePlaybackScale(multiplier) {
    return DEFAULT_PLAYBACK_SCALE * normalizePlaybackMultiplier(multiplier);
  }

  function handleCargoDrop(operationKey, progress, cargoDrop) {
    invariant(Number.isFinite(progress) && Number.isFinite(cargoDrop) && cargoDrop >= 0, "货叉承托参数非法");
    if (operationKey === "STORE_HANDLE") return cargoDrop * clamp((progress - .42) / .18, 0, 1);
    if (operationKey === "RETRIEVE_HANDLE") return cargoDrop * (1 - clamp((progress - .52) / .18, 0, 1));
    return 0;
  }

  /* 单一货物运动学真相源：3D 渲染与 Node 契约测试共用，避免阶段交接各写一套坐标。 */
  function cargoWorldPosition(frame, machineWorld, geometry) {
    invariant(frame && Number.isFinite(frame.operationProgress), "货物帧参数非法");
    invariant(machineWorld && Number.isFinite(machineWorld.worldX) && Number.isFinite(machineWorld.worldZ), "货物机位参数非法");
    invariant(geometry && geometry.io && geometry.transfer && geometry.infeed && geometry.outfeed, "货物几何参数缺失");
    const io = geometry.io, transfer = geometry.transfer, infeed = geometry.infeed, outfeed = geometry.outfeed;
    const cargoZOffset = Number(geometry.cargoZOffset), cargoDrop = Number(geometry.cargoDrop), cargoReach = Number(geometry.cargoReach);
    invariant(Number.isFinite(io.x) && Number.isFinite(io.y) && Number.isFinite(infeed.y) &&
      Number.isFinite(infeed.entryX) && Number.isFinite(infeed.loadX) && Number.isFinite(infeed.z) &&
      Number.isFinite(outfeed.y) && Number.isFinite(outfeed.startX) && Number.isFinite(outfeed.scanX) &&
      Number.isFinite(outfeed.maskX) && Number.isFinite(outfeed.endX) && Number.isFinite(outfeed.z) &&
      Number.isFinite(transfer.x) && Number.isFinite(transfer.y) && Number.isFinite(transfer.z) &&
      Number.isFinite(cargoZOffset) && Number.isFinite(cargoDrop) && cargoDrop >= 0 && Number.isFinite(cargoReach) && cargoReach > 0,
      "货物几何参数非法");
    invariant(Math.abs(transfer.x - io.x) <= EPS && Math.abs(transfer.y - io.y) <= EPS,
      "货物转接锚必须与逻辑 I/O 共位");
    let x = machineWorld.worldX, y = transfer.y, z = machineWorld.worldZ + cargoZOffset;
    if (frame.operationKey === "LOAD_IN") {
      const p = ease(frame.phaseProgress);
      if (frame.cargoOwner === "QUEUE") {
        /* QUEUE 是入场前等待，不得借真实排队时长偷跑输送动作。 */
        x = infeed.entryX; y = infeed.y; z = infeed.z;
      } else {
        /* 不计 SIM/KPI 的入口交接补段承载完整 Entry→Load→Transfer 视觉路径。 */
        const firstLength = Math.abs(infeed.loadX - infeed.entryX);
        const secondLength = Math.hypot(transfer.x - infeed.loadX, transfer.y - infeed.y, transfer.z - infeed.z);
        const split = firstLength / Math.max(EPS, firstLength + secondLength);
        if (p <= split) {
          const u = split > EPS ? p / split : 1;
          x = infeed.entryX + (infeed.loadX - infeed.entryX) * u; y = infeed.y; z = infeed.z;
        } else {
          const u = (p - split) / Math.max(EPS, 1 - split);
          x = infeed.loadX + (transfer.x - infeed.loadX) * u;
          y = infeed.y + (transfer.y - infeed.y) * u; z = infeed.z + (transfer.z - infeed.z) * u;
        }
      }
    } else if (frame.operationKey === "STORE_HANDLE") {
      const approach = ease(frame.operationProgress / .50);
      y = transfer.y + cargoReach * approach;
      z -= handleCargoDrop(frame.operationKey, frame.operationProgress, cargoDrop);
    } else if (frame.operationKey === "RETRIEVE_HANDLE") {
      const retreat = ease((frame.operationProgress - .50) / .50);
      y = transfer.y + cargoReach * (1 - retreat);
      z -= handleCargoDrop(frame.operationKey, frame.operationProgress, cargoDrop);
    } else if (frame.operationKey === "SCAN_EXIT") {
      const p = ease(frame.phaseProgress); z = outfeed.z;
      if (frame.cargoOwner === "OUTFEED") {
        const split = .38;
        if (p <= split) {
          const u = ease(p / split); x = transfer.x + (outfeed.startX - transfer.x) * u;
          y = transfer.y + (outfeed.y - transfer.y) * u;
        } else {
          const u = ease((p - split) / (1 - split)); x = outfeed.startX + (outfeed.scanX - outfeed.startX) * u; y = outfeed.y;
        }
      } else if (frame.cargoOwner === "SCANNED") {
        x = outfeed.scanX + (outfeed.maskX - outfeed.scanX) * p; y = outfeed.y;
      } else {
        x = outfeed.maskX + (outfeed.endX - outfeed.maskX) * p; y = outfeed.y;
      }
    }
    return {x, y, z};
  }

  function ownershipSnapshot(frame) {
    invariant(frame && Array.isArray(frame.inventoryRows) && Array.isArray(frame.queueGids), "所有权帧非法");
    const records = [];
    frame.inventoryRows.forEach(row => records.push({gid: row.gid, owner: "RACK", renderVisible: true}));
    frame.queueGids.forEach((gid, index) => records.push({gid, owner: "QUEUE_WAITING", renderVisible: index < 4}));
    if (frame.cargoGid !== null && frame.cargoGid !== undefined && frame.cargoOwner !== "CONSUMED") {
      records.push({gid: frame.cargoGid, owner: frame.cargoOwner || "UNKNOWN", renderVisible: true});
    }
    const grouped = new Map();
    records.forEach(record => { const list = grouped.get(record.gid) || []; list.push(record); grouped.set(record.gid, list); });
    const duplicates = Array.from(grouped, ([gid, list]) => ({gid, owners: list.map(item => item.owner)})).filter(item => item.owners.length !== 1);
    return {records, duplicates, unique: duplicates.length === 0};
  }

  function validateVisualTopology(topology) {
    invariant(topology && topology.io && topology.transfer && topology.infeed && topology.outfeed &&
      topology.infeedEnvelope && topology.outfeedEnvelope, "双工位拓扑缺失");
    const {io, transfer, infeed, outfeed, infeedEnvelope, outfeedEnvelope} = topology;
    [infeed.y, infeed.entryX, infeed.loadX, infeed.width, outfeed.y, outfeed.startX, outfeed.endX, outfeed.width].forEach(value => invariant(Number.isFinite(value), "双工位拓扑坐标非法"));
    invariant(topology.visualOnly === true, "双工位必须声明为展示层");
    invariant(Array.isArray(topology.logicalOrigin) && topology.logicalOrigin[0] === 0 && topology.logicalOrigin[1] === 0, "双工位不得改变 canonical I/O (0,0)");
    invariant(topology.collinear === true && topology.sharedBelt === false && topology.oppositeSides === true,
      "入/出库链必须是同轴分段、不得共用可争用带段");
    invariant(topology.collinearAxis === "x", "输送链共轴方向必须为横向 x");
    [transfer.x, transfer.y, transfer.z].forEach(value => invariant(Number.isFinite(value), "I/O 转接锚非法"));
    invariant(Math.abs(transfer.x - io.x) <= EPS && Math.abs(transfer.y - io.y) <= EPS,
      "物理转接锚与逻辑 I/O 映射不一致");
    const axisOffset = Math.abs(outfeed.y - infeed.y);
    invariant(axisOffset <= 1e-9, "入/出库链未处于同一中心轴");
    invariant(infeed.entryX < infeed.loadX && infeed.loadX < io.x, "入库段必须从左侧单向接近 I/O");
    invariant(io.x < outfeed.startX && outfeed.startX < outfeed.scanX && outfeed.scanX < outfeed.maskX && outfeed.maskX < outfeed.endX,
      "出库段必须从 I/O 单向远离并依次通过卸载/扫码/离场");
    const junctionGap = outfeed.startX - infeed.loadX;
    invariant(junctionGap > Math.max(infeed.width, outfeed.width), "I/O 两侧分段净距不足一个活动货物宽度");
    const rackFrontY = Number(topology.rackFrontY);
    invariant(Number.isFinite(rackFrontY), "货架前界缺失");
    const rackFrontClearance = rackFrontY - Math.max(infeed.y + infeed.width / 2, outfeed.y + outfeed.width / 2);
    invariant(rackFrontClearance >= .30, "共轴输送链与货架前界净距不足 0.30 m");
    const validEnvelope = envelope => [envelope.xMin, envelope.xMax, envelope.yMin, envelope.yMax].every(Number.isFinite) &&
      envelope.xMin < envelope.xMax && envelope.yMin < envelope.yMax;
    invariant(validEnvelope(infeedEnvelope) && validEnvelope(outfeedEnvelope), "输送链物理包络非法");
    const overlapX = Math.max(0, Math.min(infeedEnvelope.xMax, outfeedEnvelope.xMax) - Math.max(infeedEnvelope.xMin, outfeedEnvelope.xMin));
    const overlapY = Math.max(0, Math.min(infeedEnvelope.yMax, outfeedEnvelope.yMax) - Math.max(infeedEnvelope.yMin, outfeedEnvelope.yMin));
    const envelopeOverlapArea = overlapX * overlapY;
    invariant(envelopeOverlapArea <= EPS, "入/出库物理带段包络发生重叠");
    invariant(infeedEnvelope.xMax <= transfer.x + EPS && outfeedEnvelope.xMin >= transfer.x - EPS,
      "入/出库带段必须只通过受控转接区连接 I/O");
    return {axisOffset, junctionGap, rackFrontClearance, collinearAxis: "x", collinear: true, sharedBelt: false, oppositeSides: true,
      logicalOrigin: topology.logicalOrigin.slice(), visualOnly: true,
      singleRackFace: topology.singleRackFace === true, singleAisle: topology.singleAisle === true,
      transferAnchor: {x: transfer.x, y: transfer.y, z: transfer.z}, envelopeOverlapArea,
      infeedEnvelope: Object.assign({}, infeedEnvelope), outfeedEnvelope: Object.assign({}, outfeedEnvelope)};
  }

  function rectIntersectionArea(left, right) {
    const width = Math.max(0, Math.min(left.right, right.right) - Math.max(left.left, right.left));
    const height = Math.max(0, Math.min(left.bottom, right.bottom) - Math.max(left.top, right.top));
    return width * height;
  }

  function pointInRect(point, rect, padding = 0) {
    return point.x >= rect.left - padding && point.x <= rect.right + padding &&
      point.y >= rect.top - padding && point.y <= rect.bottom + padding;
  }

  function orientation(a, b, c) {
    const value = (b.y - a.y) * (c.x - b.x) - (b.x - a.x) * (c.y - b.y);
    return Math.abs(value) <= EPS ? 0 : value > 0 ? 1 : 2;
  }

  function onSegment(a, b, c) {
    return b.x <= Math.max(a.x, c.x) + EPS && b.x >= Math.min(a.x, c.x) - EPS &&
      b.y <= Math.max(a.y, c.y) + EPS && b.y >= Math.min(a.y, c.y) - EPS;
  }

  function segmentsIntersect(a, b, c, d) {
    const o1 = orientation(a, b, c), o2 = orientation(a, b, d), o3 = orientation(c, d, a), o4 = orientation(c, d, b);
    if (o1 !== o2 && o3 !== o4) return true;
    return (o1 === 0 && onSegment(a, c, b)) || (o2 === 0 && onSegment(a, d, b)) ||
      (o3 === 0 && onSegment(c, a, d)) || (o4 === 0 && onSegment(c, b, d));
  }

  function segmentIntersectsRect(a, b, rect, padding = 1) {
    const expanded = {left: rect.left - padding, right: rect.right + padding, top: rect.top - padding, bottom: rect.bottom + padding};
    if (pointInRect(a, expanded) || pointInRect(b, expanded)) return true;
    const tl = {x: expanded.left, y: expanded.top}, tr = {x: expanded.right, y: expanded.top};
    const br = {x: expanded.right, y: expanded.bottom}, bl = {x: expanded.left, y: expanded.bottom};
    return segmentsIntersect(a, b, tl, tr) || segmentsIntersect(a, b, tr, br) ||
      segmentsIntersect(a, b, br, bl) || segmentsIntersect(a, b, bl, tl);
  }

  function compactPoints(points) {
    return points.filter((point, index) => index === 0 || Math.hypot(point.x - points[index - 1].x, point.y - points[index - 1].y) > EPS);
  }

  function routeSegments(points) {
    const result = [];
    for (let index = 1; index < points.length; index += 1) result.push([points[index - 1], points[index]]);
    return result;
  }

  function routeLength(points) {
    return routeSegments(points).reduce((sum, [a, b]) => sum + Math.hypot(b.x - a.x, b.y - a.y), 0);
  }

  function leaderRouteCandidates(anchor, rect, obstacles = []) {
    const endpoints = [
      {x: rect.left, y: clamp(anchor.y, rect.top, rect.bottom)},
      {x: rect.right, y: clamp(anchor.y, rect.top, rect.bottom)},
      {x: clamp(anchor.x, rect.left, rect.right), y: rect.top},
      {x: clamp(anchor.x, rect.left, rect.right), y: rect.bottom}
    ];
    const candidates = [];
    endpoints.forEach(endpoint => {
      const horizontalFirst = {x: endpoint.x, y: anchor.y}, verticalFirst = {x: anchor.x, y: endpoint.y};
      candidates.push([anchor, endpoint], [anchor, horizontalFirst, endpoint], [anchor, verticalFirst, endpoint]);
      /* 直接线与单折线都被同伴标签挡住时，沿障碍外缘生成确定性的两折绕行。
         这不是放宽碰撞门；最终仍由 obstacleHits=0 的评分门选择。 */
      obstacles.forEach(obstacle => {
        const clearance = 6;
        [obstacle.left - clearance, obstacle.right + clearance].forEach(x => {
          candidates.push([anchor, {x, y: anchor.y}, {x, y: endpoint.y}, endpoint]);
        });
        [obstacle.top - clearance, obstacle.bottom + clearance].forEach(y => {
          candidates.push([anchor, {x: anchor.x, y}, {x: endpoint.x, y}, endpoint]);
        });
      });
    });
    return candidates.map((rawPoints, rank) => {
      const points = compactPoints(rawPoints), segments = routeSegments(points);
      const obstacleHits = obstacles.reduce((count, obstacle) =>
        count + (segments.some(([a, b]) => segmentIntersectsRect(a, b, obstacle, 2)) ? 1 : 0), 0);
      const length = routeLength(points), bends = Math.max(0, points.length - 2);
      const score = obstacleHits * 1e7 + length + bends * 9 + rank * .01;
      return {points, length, obstacleHits, crossings: 0, score};
    }).sort((left, right) => left.score - right.score);
  }

  function routeCrossings(left, right) {
    return routeSegments(left.points).reduce((count, [a, b]) => count +
      routeSegments(right.points).filter(([c, d]) => segmentsIntersect(a, b, c, d)).length, 0);
  }

  function chooseLeaderRoute(anchor, rect, obstacles = [], priorRoutes = []) {
    let best = null;
    leaderRouteCandidates(anchor, rect, obstacles).forEach(candidate => {
      const crossings = priorRoutes.reduce((count, route) => count + routeCrossings(candidate, route), 0);
      const score = candidate.score + crossings * 5e6;
      if (!best || score < best.score) best = Object.assign({}, candidate, {crossings, score});
    });
    return best;
  }

  function chooseLabelPairLayout(items, bounds, obstacles) {
    invariant(Array.isArray(items) && items.length > 0 && items.length <= 2, "标签布局只支持一至两个信标");
    const safeObstacles = Array.isArray(obstacles) ? obstacles : [];
    const options = items.map(item => {
      const w = item.width, h = item.height, x = item.anchor.x, y = item.anchor.y;
      const offsets = item.role === "target" ?
        [[22,-h/2],[-w-22,-h/2],[-w/2,-h-30],[-w/2,30],[22,-h-12],[-w-22,-h-12],
          [38,-h-48],[-w-38,-h-48],[38,32],[-w-38,32],[-w/2,-h-72],[-w/2,54],
          [38,-h-76],[-w-38,-h-76]] :
        [[-w/2,-h-42],[20,-h/2],[-w-20,-h/2],[-w/2,28],[20,-h-12],[-w-20,-h-12],
          [-w/2,-h-72],[36,-h-42],[-w-36,-h-42],[36,38],[-w-36,38],[-w/2,56],
          [36,-h-80],[-w-36,-h-80]];
      return offsets.map(([dx,dy], rank) => {
        let left = x + dx, top = y + dy;
        const rawLeft = left, rawTop = top;
        left = clamp(left, bounds.left, bounds.right - w); top = clamp(top, bounds.top, bounds.bottom - h);
        const rect = {left, top, right: left + w, bottom: top + h, width: w, height: h};
        const clampCost = Math.abs(left - rawLeft) + Math.abs(top - rawTop);
        const obstacleArea = safeObstacles.reduce((sum, obstacle) => sum + rectIntersectionArea(rect, obstacle), 0);
        const anchorCover = safeObstacles.filter(obstacle => obstacle.anchorZone).reduce((sum, obstacle) => sum + rectIntersectionArea(rect, obstacle), 0);
        return {id: item.id, role: item.role, rect, anchor: item.anchor, score: rank * 3 + clampCost * 18 + obstacleArea * 40 + anchorCover * 240};
      });
    });
    let best = null;
    options[0].forEach(first => {
      const seconds = options[1] || [null];
      seconds.forEach(second => {
        const overlap = second ? rectIntersectionArea(first.rect, second.rect) : 0;
        const score = first.score + (second ? second.score : 0) + overlap * 2400;
        if (!best || score < best.score) best = {score, overlapArea: overlap, placements: second ? [first, second] : [first]};
      });
    });
    return best;
  }

  function validateComparisonEvidence(evidence) {
    invariant(evidence && evidence.schema_version === "s1-comparison-evidence-v1", "S1 对照证据 schema 不匹配");
    invariant(evidence.sim_only === true && evidence.stage === "s1", "S1 对照证据缺少 sim-only / stage 守门");
    invariant(evidence.purpose === "controlled-comparison-only; never merge with representative S3 playback", "S1/S3 证据隔离声明缺失");
    invariant(Array.isArray(evidence.seeds) && evidence.seeds.length === 10 && evidence.seeds.every((seed, index) => seed === 2026 + index), "S1 seeds 必须为 2026..2035");
    invariant(Array.isArray(evidence.modes) && evidence.modes.length === EVIDENCE_MODES.length &&
      evidence.modes.every((mode, index) => mode === EVIDENCE_MODES[index]), "S1 对照模式轴不匹配");
    invariant(Array.isArray(evidence.scenarios) && evidence.scenarios.length === 18, "S1 对照必须覆盖 18 个情景");
    invariant(Array.isArray(evidence.rows) && evidence.rows.length === 144, "S1 对照必须包含 18×8 单元");
    const scenarioIds = evidence.scenarios.map(item => item.id);
    invariant(new Set(scenarioIds).size === 18 && scenarioIds.every((id, index) => id === `E${String(index + 1).padStart(2, "0")}`), "S1 情景编号不完整");
    const cells = new Set();
    evidence.rows.forEach(row => {
      invariant(scenarioIds.includes(row.scenario) && EVIDENCE_MODES.includes(row.mode), "S1 对照单元轴非法");
      invariant(Number.isInteger(row.n_runs) && row.n_runs === 10 && Number.isInteger(row.n_feasible) && row.n_feasible >= 0 && row.n_feasible <= 10, "S1 对照样本数非法");
      invariant(row.p95_mean_s === null || Number.isFinite(row.p95_mean_s), "S1 P95 均值非法");
      invariant(row.p95_ci95_half_s === null || Number.isFinite(row.p95_ci95_half_s), "S1 P95 CI 非法");
      invariant(Number.isInteger(row.fail_sum) && Number.isInteger(row.viol_sum) && Number.isInteger(row.reject_sum), "S1 护栏计数非法");
      invariant(row.picked_counts && typeof row.picked_counts === "object" && Number.isFinite(row.selection_stability), "S1 路由统计非法");
      const key = `${row.scenario}/${row.mode}`; invariant(!cells.has(key), `S1 对照重复单元 ${key}`); cells.add(key);
    });
    const extended = evidence.scenarios.find(item => item.id === "E15");
    invariant(extended && extended.extended_pressure === true && extended.canonical_g2 === false && extended.headline_eligible === false,
      "E15 降级口径三字段不完整");
    return true;
  }

  function selectComparisonEvidence(evidence, axis, key) {
    validateComparisonEvidence(evidence);
    if (axis === "scenario") {
      invariant(evidence.scenarios.some(item => item.id === key), `未知 S1 情景 ${key}`);
      return EVIDENCE_MODES.map(mode => evidence.rows.find(row => row.scenario === key && row.mode === mode));
    }
    invariant(axis === "mode" && EVIDENCE_MODES.includes(key), `未知 S1 对照轴 ${axis}/${key}`);
    return evidence.scenarios.map(scenario => evidence.rows.find(row => row.scenario === scenario.id && row.mode === key));
  }

  function asSlot(value, label) {
    invariant(value && Number.isInteger(value.col) && Number.isInteger(value.tier), `${label} 非法`);
    invariant(value.col >= 0 && value.col < 20 && value.tier >= 0 && value.tier < 20, `${label} 越界`);
    invariant((value.col + value.tier) % 3 !== 0, `${label} 落入预占禁用格`);
    return [value.col, value.tier];
  }

  function validateInventoryRows(rows, label, expectedSize) {
    invariant(Array.isArray(rows), `${label} 不是数组`);
    if (expectedSize !== undefined) invariant(rows.length === expectedSize, `${label} 数量应为 ${expectedSize}`);
    const gids = new Set(), slots = new Set();
    rows.forEach(row => {
      invariant(row && Number.isInteger(row.gid), `${label} gid 非法`);
      const slot = asSlot(row, `${label} gid=${row.gid}`);
      const key = slot.join("/");
      invariant(!gids.has(row.gid), `${label} 重复 gid=${row.gid}`);
      invariant(!slots.has(key), `${label} 重复货位 ${key}`);
      gids.add(row.gid); slots.add(key);
    });
    return rows;
  }

  function effectivePhaseName(phase) {
    return phase.name === "FAULT_RECOVERY" ? phase.operation_phase : phase.name;
  }

  function presentationRateScale(simRate) {
    return DEFAULT_SIM_RATE / simRate;
  }

  function queuePresentationDuration(actual, simRate) {
    return clamp(actual * PRESENTATION_TIMING.queueFactor * presentationRateScale(simRate),
      PRESENTATION_TIMING.queueMin, PRESENTATION_TIMING.queueMax);
  }

  function phaseDuration(phase, operationKey, simRate) {
    const actual = Number(phase.t1) - Number(phase.t0);
    invariant(Number.isFinite(actual) && actual >= -EPS, `phase ${phase.name} 时长非法`);
    const rateScale = presentationRateScale(simRate);
    if (phase.name === "FAULT_RECOVERY") return PRESENTATION_TIMING.faultRecovery * rateScale;
    if (["STORE_HANDLE", "RETRIEVE_HANDLE"].includes(operationKey)) return PRESENTATION_TIMING.handle * rateScale;
    if (["INBOUND_TRAVEL", "LINK_TRAVEL", "OUTBOUND_TRAVEL"].includes(operationKey)) {
      return clamp(actual * PRESENTATION_TIMING.travelFactor * rateScale,
        PRESENTATION_TIMING.travelMin * rateScale, PRESENTATION_TIMING.travelMax * rateScale);
    }
    return actual > EPS ? actual / simRate : ZERO_STEP_DISPLAY_S;
  }

  function applyOperationDisplayFloor(segments, operationKey) {
    const minimum = ["INBOUND_TRAVEL", "LINK_TRAVEL", "OUTBOUND_TRAVEL"].includes(operationKey) ? MIN_TRAVEL_DISPLAY_S :
      ["STORE_HANDLE", "RETRIEVE_HANDLE"].includes(operationKey) ? MIN_HANDLE_DISPLAY_S : 0;
    const total = segments.reduce((sum, segment) => sum + segment.duration, 0);
    if (minimum <= 0 || total >= minimum - EPS) return segments;
    const scale = minimum / Math.max(EPS, total);
    return segments.map(segment => Object.assign({}, segment, {duration: segment.duration * scale, presentationStretched: true}));
  }

  function normalizePhaseSlot(value, fallback) {
    return Array.isArray(value) && value.length === 2 ? [Number(value[0]), Number(value[1])] : fallback.slice();
  }

  function buildTimeline(trace, simRate = DEFAULT_SIM_RATE) {
    invariant(trace && trace.schema_version === TRACE_SCHEMA && trace.sim_only === true, "trace schema / sim 边界不匹配");
    invariant(Number.isFinite(simRate) && simRate > 0, "simRate 必须为正数");
    invariant(trace.meta && Number.isInteger(trace.meta.seed), "trace seed 缺失");
    invariant(Array.isArray(trace.events) && trace.events.length === trace.meta.cycles, "trace event 数量不匹配");
    invariant(Array.isArray(trace.inventory_snapshots) && trace.inventory_snapshots.length === trace.events.length + 1, "库存快照数量不匹配");
    trace.inventory_snapshots.forEach((rows, index) => validateInventoryRows(rows, `snapshot[${index}]`, 120));
    invariant(trace.comparability && trace.comparability.s1_matrix_same_parameterization === false &&
      trace.comparability.ui_rule === "do_not_compare_or_merge", "S1 参数隔离守门缺失");

    const segments = [], groups = [], groupsByKey = new Map();
    let clock = 0;

    function addGroup(event, cycleIndex, operationKey, rawSegments) {
      invariant(rawSegments.length > 0, `cycle ${cycleIndex} ${operationKey} 无显示段`);
      const d0 = clock;
      rawSegments.forEach(raw => {
        invariant(Number.isFinite(raw.duration) && raw.duration > 0, `${operationKey} 显示时长非法`);
        const segment = Object.assign({}, raw, {
          index: segments.length, cycleIndex, cycle: event.cycle,
          cycleNumber: event.cycle_number, operationKey, event,
          d0: clock, d1: clock + raw.duration
        });
        clock = segment.d1;
        segments.push(segment);
      });
      const presentationDurationS = clock - d0;
      const simDurationS = rawSegments.reduce((sum, segment) => sum +
        (segment.simModelled === false ? 0 : Math.max(0, Number(segment.simT1) - Number(segment.simT0))), 0);
      const presentationOnlyDurationS = rawSegments.reduce((sum, segment) => sum +
        (segment.simModelled === false ? segment.duration : 0), 0);
      const group = {cycleIndex, cycle: event.cycle, cycleNumber: event.cycle_number, operationKey, d0, d1: clock,
        simDurationS, presentationDurationS, presentationOnlyDurationS,
        wallSecondsAt1x: presentationDurationS / DEFAULT_PLAYBACK_SCALE};
      const key = `${cycleIndex}|${operationKey}`;
      invariant(!groupsByKey.has(key), `重复 checkpoint group ${key}`);
      groupsByKey.set(key, group); groups.push(group);
      rawSegments.forEach((_raw, offset) => {
        const segment = segments[segments.length - rawSegments.length + offset];
        segment.groupD0 = group.d0; segment.groupD1 = group.d1;
        segment.groupSimDurationS = group.simDurationS;
        segment.groupPresentationDurationS = group.presentationDurationS;
        segment.groupPresentationOnlyDurationS = group.presentationOnlyDurationS;
        segment.groupWallSecondsAt1x = group.wallSecondsAt1x;
      });
    }

    trace.events.forEach((event, cycleIndex) => {
      invariant(event.cycle === cycleIndex && event.cycle_number === cycleIndex + 1, `cycle ${cycleIndex} 编号不连续`);
      invariant(event.inventory_before_ref === cycleIndex && event.inventory_after_ref === cycleIndex + 1, `cycle ${cycleIndex} 快照引用不连续`);
      const storeSlot = asSlot(event.store_slot, `cycle ${cycleIndex} store_slot`);
      const retrieveSlot = asSlot(event.retrieve_slot, `cycle ${cycleIndex} retrieve_slot`);
      invariant(Array.isArray(event.process_steps) && event.process_steps.length === PROCESS_STEPS.length, `cycle ${cycleIndex} process_steps 不完整`);
      const stepByName = new Map(event.process_steps.map(step => [step.name, step]));
      invariant(PROCESS_STEPS.every(name => stepByName.has(name)), `cycle ${cycleIndex} 七步契约不完整`);

      const queuePhase = event.phases.find(phase => phase.name === "QUEUE");
      const loadSegments = [];
      if (queuePhase && Number(queuePhase.t1) - Number(queuePhase.t0) > EPS) {
        loadSegments.push({
          phaseName: "QUEUE", effectiveName: "LOAD_IN", owner: "QUEUE",
          cargoGid: event.inbound_gid, from: [0, 0], to: [0, 0], u0: 0, u1: 1,
          simT0: queuePhase.t0, simT1: queuePhase.t1,
          duration: queuePresentationDuration(queuePhase.t1 - queuePhase.t0, simRate), simModelled: true,
          presentationMapped: true
        });
      }
      const loadStep = stepByName.get("LOAD_IN");
      loadSegments.push({
        phaseName: "LOAD_IN", effectiveName: "LOAD_IN", owner: "CARRIER_IN",
        cargoGid: event.inbound_gid, from: [0, 0], to: [0, 0], u0: 0, u1: 1,
        simT0: loadStep.t0, simT1: loadStep.t1,
        duration: PRESENTATION_TIMING.loadHandoff, simModelled: false, presentationMapped: true
      });
      addGroup(event, cycleIndex, "LOAD_IN", loadSegments);

      PROCESS_STEPS.slice(1, 6).forEach(operationKey => {
        const matches = event.phases.filter(phase => effectivePhaseName(phase) === operationKey);
        const fallback = operationKey === "INBOUND_TRAVEL" ? [[0, 0], storeSlot] :
          operationKey === "STORE_HANDLE" ? [storeSlot, storeSlot] :
          operationKey === "LINK_TRAVEL" ? [storeSlot, retrieveSlot] :
          operationKey === "RETRIEVE_HANDLE" ? [retrieveSlot, retrieveSlot] : [retrieveSlot, [0, 0]];
        let raw = matches.length ? matches.map(phase => ({
          phaseName: phase.name, effectiveName: operationKey,
          owner: phase.cargo_owner || null, cargoGid: phase.cargo_gid ?? null,
          from: normalizePhaseSlot(phase.from, fallback[0]), to: normalizePhaseSlot(phase.to, fallback[1]),
          u0: Number.isFinite(phase.u0) ? phase.u0 : 0,
          u1: Number.isFinite(phase.u1) ? phase.u1 : 1,
          simT0: phase.t0, simT1: phase.t1,
          duration: phaseDuration(phase, operationKey, simRate), simModelled: phase.sim_modelled !== false,
          presentationMapped: true,
          faultIndex: phase.fault_index ?? null
        })) : (() => {
          const step = stepByName.get(operationKey);
          return [{
            phaseName: operationKey, effectiveName: operationKey,
            owner: step.cargo_owner || null, cargoGid: step.cargo_gid ?? null,
            from: fallback[0], to: fallback[1], u0: 0, u1: 1,
            simT0: step.t0, simT1: step.t1,
            duration: ZERO_STEP_DISPLAY_S, simModelled: step.sim_modelled !== false,
            presentationZeroDuration: true
          }];
        })();
        raw = applyOperationDisplayFloor(raw, operationKey);
        addGroup(event, cycleIndex, operationKey, raw);
      });

      const lifecycle = event.ownership_events.filter(item =>
        item.gid === event.outbound_gid && ["SCANNED", "EXIT_MASK", "CONSUMED"].includes(item.to));
      invariant(lifecycle.length === 3, `cycle ${cycleIndex} 出口所有权链不完整`);
      const offsets = [0].concat(lifecycle.map(item => Number(item.display_offset_s)));
      invariant(offsets.slice(1).every((value, index) => Number.isFinite(value) && value > offsets[index]), `cycle ${cycleIndex} 出口显示偏移非法`);
      const tailOwners = ["OUTFEED", "SCANNED", "EXIT_MASK"];
      const tailDurations = [PRESENTATION_TIMING.outfeed, PRESENTATION_TIMING.scanned, PRESENTATION_TIMING.exitMask];
      const tail = tailOwners.map((owner, index) => ({
        phaseName: owner, effectiveName: "SCAN_EXIT", owner,
        cargoGid: event.outbound_gid, from: [0, 0], to: [0, 0], u0: 0, u1: 1,
        simT0: event.finish, simT1: event.finish,
        duration: tailDurations[index], simModelled: false, presentationMapped: true,
        lifecycleOffset0: offsets[index], lifecycleOffset1: offsets[index + 1]
      }));
      tail.push({
        phaseName: "CONSUMED", effectiveName: "SCAN_EXIT", owner: "CONSUMED",
        cargoGid: event.outbound_gid, from: [0, 0], to: [0, 0], u0: 0, u1: 1,
        simT0: event.finish, simT1: event.finish, duration: CONSUMED_HOLD_S, simModelled: false,
        lifecycleOffset0: offsets[offsets.length - 1], lifecycleOffset1: offsets[offsets.length - 1] + CONSUMED_HOLD_S
      });
      addGroup(event, cycleIndex, "SCAN_EXIT", tail);
    });

    invariant(groups.length === trace.events.length * PROCESS_STEPS.length, "checkpoint group 数量不是 cycles × 7");
    invariant(clock > 0, "timeline 总时长为零");
    return {traceId: trace.meta.trace_id, seed: trace.meta.seed, simRate, segments, groups, groupsByKey, total: clock};
  }

  function normalizedElapsed(elapsed, total) {
    invariant(Number.isFinite(elapsed) && Number.isFinite(total) && total > 0, "elapsed / total 非法");
    const loop = Math.floor(elapsed / total);
    const local = ((elapsed % total) + total) % total;
    return {loop, local};
  }

  function locateSegment(timeline, elapsed) {
    const normalized = normalizedElapsed(elapsed, timeline.total);
    let low = 0, high = timeline.segments.length - 1;
    while (low < high) {
      const mid = Math.floor((low + high) / 2);
      if (normalized.local < timeline.segments[mid].d1) high = mid;
      else low = mid + 1;
    }
    const segment = timeline.segments[low];
    const progress = clamp((normalized.local - segment.d0) / Math.max(EPS, segment.d1 - segment.d0), 0, 1);
    return {segment, progress, loop: normalized.loop, local: normalized.local};
  }

  function checkpointAt(timeline, elapsed) {
    const found = locateSegment(timeline, elapsed), segment = found.segment;
    const progress = clamp((found.local - segment.groupD0) / Math.max(EPS, segment.groupD1 - segment.groupD0), 0, 1);
    return {
      seed: timeline.seed, cycleIndex: segment.cycleIndex, cycleNumber: segment.cycleNumber,
      phase: segment.operationKey, progress, loop: found.loop
    };
  }

  function elapsedForCheckpoint(timeline, checkpoint) {
    invariant(checkpoint && checkpoint.seed === timeline.seed, "目标 trace seed 与 checkpoint 不一致");
    invariant(Number.isInteger(checkpoint.cycleIndex) && PROCESS_STEPS.includes(checkpoint.phase), "checkpoint 周期 / 阶段非法");
    const group = timeline.groupsByKey.get(`${checkpoint.cycleIndex}|${checkpoint.phase}`);
    invariant(group, `目标 trace 缺少 checkpoint ${checkpoint.cycleIndex}/${checkpoint.phase}`);
    const local = group.d0 + clamp(Number(checkpoint.progress), 0, 1) * (group.d1 - group.d0);
    return Math.max(0, Number(checkpoint.loop) || 0) * timeline.total + local;
  }

  function axisTime(distance, vmax, accel, motion) {
    if (distance <= 0) return 0;
    if (motion === "constant_speed") return distance / vmax;
    return distance >= vmax * vmax / accel ? distance / vmax + vmax / accel : 2 * Math.sqrt(distance / accel);
  }

  function axisPosition(time, distance, vmax, accel, motion) {
    if (distance <= 0) return 0;
    const total = axisTime(distance, vmax, accel, motion), t = clamp(time, 0, total);
    if (motion === "constant_speed") return Math.min(distance, vmax * t);
    if (distance >= vmax * vmax / accel) {
      const ramp = vmax / accel;
      if (t < ramp) return 0.5 * accel * t * t;
      if (t <= total - ramp) return 0.5 * accel * ramp * ramp + vmax * (t - ramp);
      return distance - 0.5 * accel * (total - t) * (total - t);
    }
    const ramp = Math.sqrt(distance / accel);
    return t < ramp ? 0.5 * accel * t * t : distance - 0.5 * accel * (total - t) * (total - t);
  }

  function axisVelocity(time, distance, vmax, accel, motion) {
    if (distance <= 0) return 0;
    const total = axisTime(distance, vmax, accel, motion), t = clamp(time, 0, total);
    if (motion === "constant_speed") return t >= total ? 0 : vmax;
    const peak = distance >= vmax * vmax / accel ? vmax : accel * Math.sqrt(distance / accel);
    const ramp = peak / accel;
    if (t < ramp) return accel * t;
    if (t <= total - ramp) return peak;
    return Math.max(0, accel * (total - t));
  }

  function motionPoint(trace, from, to, u) {
    const dx = Math.abs(to[0] - from[0]), dz = Math.abs(to[1] - from[1]);
    const motion = trace.meta.motion;
    const tx = axisTime(dx, VX, AX, motion), tz = axisTime(dz, VZ, AZ, motion), total = Math.max(tx, tz);
    const t = clamp(u, 0, 1) * total;
    const sx = Math.sign(to[0] - from[0]), sz = Math.sign(to[1] - from[1]);
    return {
      x: from[0] + sx * axisPosition(t, dx, VX, AX, motion),
      z: from[1] + sz * axisPosition(t, dz, VZ, AZ, motion),
      vx: sx * axisVelocity(t, dx, VX, AX, motion),
      vz: sz * axisVelocity(t, dz, VZ, AZ, motion), total
    };
  }

  /* 七步路径计划与 cargoWorldPosition 共用坐标真相源。
     LINK_TRAVEL 是空载设备联程，其余六步均为货物可追踪路径。 */
  function operationPathPlan(trace, event, geometry, count = 72) {
    invariant(trace && trace.meta && event && event.store_slot && event.retrieve_slot, "路径计划事件缺失");
    invariant(geometry && geometry.io && geometry.transfer && geometry.infeed && geometry.outfeed, "路径计划几何缺失");
    invariant(Number.isInteger(count) && count >= 8, "路径采样数必须为 >=8 的整数");
    const io = geometry.io, transfer = geometry.transfer, infeed = geometry.infeed, outfeed = geometry.outfeed;
    const cargoZOffset = Number(geometry.cargoZOffset), cargoDrop = Number(geometry.cargoDrop), cargoReach = Number(geometry.cargoReach);
    invariant(Number.isFinite(cargoZOffset) && Number.isFinite(cargoDrop) && Number.isFinite(cargoReach) && cargoReach > 0,
      "路径计划货物几何非法");
    const store = [event.store_slot.col, event.store_slot.tier];
    const retrieve = [event.retrieve_slot.col, event.retrieve_slot.tier];
    const machinePath = (from, to, loaded) => Array.from({length: count + 1}, (_, index) => {
      const point = motionPoint(trace, from, to, index / count);
      return {x: point.x + .5, y: transfer.y, z: point.z + .5 + (loaded ? cargoZOffset : 0)};
    });
    const handlePath = (operationKey, slot, owner) => Array.from({length: count + 1}, (_, index) => {
      const progress = index / count, machine = motionPoint(trace, slot, slot, 0);
      return cargoWorldPosition(
        {operationKey, operationProgress: progress, phaseProgress: progress, cargoOwner: owner},
        {worldX: machine.x + .5, worldZ: machine.z + .5}, geometry
      );
    });
    const plans = [
      {operationKey: "LOAD_IN", kind: "cargo-in", arrowCount: 2, points: [
        {x: infeed.entryX, y: infeed.y, z: infeed.z},
        {x: infeed.loadX, y: infeed.y, z: infeed.z},
        {x: transfer.x, y: transfer.y, z: transfer.z}
      ]},
      {operationKey: "INBOUND_TRAVEL", kind: "cargo-in", arrowCount: 3, points: machinePath([0, 0], store, true)},
      {operationKey: "STORE_HANDLE", kind: "handle", arrowCount: 1, points: handlePath("STORE_HANDLE", store, "CARRIER_IN")},
      {operationKey: "LINK_TRAVEL", kind: "empty", arrowCount: 3, points: machinePath(store, retrieve, false)},
      {operationKey: "RETRIEVE_HANDLE", kind: "handle", arrowCount: 1, points: handlePath("RETRIEVE_HANDLE", retrieve, "CARRIER_OUT")},
      {operationKey: "OUTBOUND_TRAVEL", kind: "cargo-out", arrowCount: 3, points: machinePath(retrieve, [0, 0], true)},
      {operationKey: "SCAN_EXIT", kind: "cargo-out", arrowCount: 3, points: [
        {x: transfer.x, y: transfer.y, z: transfer.z},
        {x: outfeed.startX, y: outfeed.y, z: outfeed.z},
        {x: outfeed.scanX, y: outfeed.y, z: outfeed.z},
        {x: outfeed.maskX, y: outfeed.y, z: outfeed.z},
        {x: outfeed.endX, y: outfeed.y, z: outfeed.z}
      ]}
    ];
    invariant(plans.length === PROCESS_STEPS.length && plans.every((plan, index) => plan.operationKey === PROCESS_STEPS[index]), "路径计划未覆盖七步顺序");
    return plans;
  }

  function rowsForOperation(trace, event, operationKey) {
    const before = trace.inventory_snapshots[event.inventory_before_ref];
    const after = trace.inventory_snapshots[event.inventory_after_ref];
    if (operationKey === "SCAN_EXIT" || operationKey === "OUTBOUND_TRAVEL") return after.map(row => Object.assign({}, row));
    const rows = new Map(before.map(row => [row.gid, Object.assign({}, row)]));
    if (["LINK_TRAVEL", "RETRIEVE_HANDLE"].includes(operationKey)) {
      rows.set(event.inbound_gid, {gid: event.inbound_gid, col: event.store_slot.col, tier: event.store_slot.tier});
    }
    if (operationKey === "RETRIEVE_HANDLE") rows.delete(event.outbound_gid);
    return Array.from(rows.values());
  }

  function deriveFrame(trace, timeline, elapsed) {
    const found = locateSegment(timeline, elapsed), segment = found.segment, event = segment.event;
    const operationProgress = clamp((found.local - segment.groupD0) / Math.max(EPS, segment.groupD1 - segment.groupD0), 0, 1);
    const phaseU = segment.phaseName === "FAULT_RECOVERY" ? segment.u0 :
      segment.u0 + (segment.u1 - segment.u0) * found.progress;
    const machine = motionPoint(trace, segment.from, segment.to, phaseU);
    const op = segment.operationKey;
    const targetSlot = ["LOAD_IN", "INBOUND_TRAVEL", "STORE_HANDLE"].includes(op) ? asSlot(event.store_slot, "store target") :
      ["LINK_TRAVEL", "RETRIEVE_HANDLE"].includes(op) ? asSlot(event.retrieve_slot, "retrieve source") : null;
    const cargoGid = op === "LINK_TRAVEL" ? null : segment.cargoGid;
    const inventoryRows = rowsForOperation(trace, event, op);
    validateInventoryRows(inventoryRows, `frame cycle ${segment.cycleIndex} ${op}`);
    const simTime = Number(segment.simT0) + (Number(segment.simT1) - Number(segment.simT0)) * found.progress;
    const cycleTiming = PROCESS_STEPS.map(operationKey => {
      const group = timeline.groupsByKey.get(`${segment.cycleIndex}|${operationKey}`);
      invariant(group, `frame 缺少周期时序 ${segment.cycleIndex}/${operationKey}`);
      return {operationKey, simDurationS: group.simDurationS, presentationDurationS: group.presentationDurationS,
        presentationOnlyDurationS: group.presentationOnlyDurationS, wallSecondsAt1x: group.wallSecondsAt1x};
    });
    return {
      traceId: trace.meta.trace_id, cycleIndex: segment.cycleIndex, cycleNumber: segment.cycleNumber,
      operationKey: op, phaseName: segment.phaseName, phaseProgress: found.progress,
      operationProgress, loop: found.loop, elapsedLocal: found.local, simTime,
      machine, targetSlot, cargoGid, cargoOwner: segment.owner,
      queueGids: event.queue_waiting_gids.slice(), inventoryRows,
      event, faulted: segment.phaseName === "FAULT_RECOVERY", faultIndex: segment.faultIndex,
      presentationOnly: segment.simModelled === false || segment.presentationZeroDuration === true,
      presentationScaled: segment.presentationStretched === true || segment.presentationMapped === true,
      timing: {simDurationS: segment.groupSimDurationS, presentationDurationS: segment.groupPresentationDurationS,
        presentationOnlyDurationS: segment.groupPresentationOnlyDurationS,
        wallSecondsAt1x: segment.groupWallSecondsAt1x}, cycleTiming
    };
  }

  function reconcileInventoryMap(current, rows, hooks) {
    invariant(current instanceof Map, "current inventory 必须为 Map");
    validateInventoryRows(rows, "reconcile inventory");
    const nextGids = new Set(rows.map(row => row.gid));
    Array.from(current.keys()).forEach(gid => {
      if (!nextGids.has(gid)) {
        if (hooks && hooks.remove) hooks.remove(current.get(gid), gid);
        current.delete(gid);
      }
    });
    rows.forEach(row => {
      if (current.has(row.gid)) {
        if (hooks && hooks.update) hooks.update(current.get(row.gid), row);
      } else {
        const value = hooks && hooks.create ? hooks.create(row) : Object.assign({}, row);
        current.set(row.gid, value);
      }
    });
    return current;
  }

  function createLatestOnlyLoader(options) {
    invariant(options && typeof options.load === "function" && typeof options.prepare === "function" && typeof options.commit === "function", "latest loader 配置不完整");
    let epoch = 0, destroyed = false, staleCount = 0;
    async function select(query, context, loadOptions) {
      invariant(!destroyed, "selection loader 已销毁");
      const token = ++epoch;
      if (options.onLoading) options.onLoading(true, query, token);
      try {
        const trace = await options.load(query, loadOptions);
        if (destroyed || token !== epoch) { staleCount += 1; return {status: "stale", token}; }
        const prepared = await options.prepare(trace, context, query);
        if (destroyed || token !== epoch) { staleCount += 1; return {status: "stale", token}; }
        options.commit(prepared, query, token);
        if (options.onLoading) options.onLoading(false, query, token);
        return {status: "committed", token, prepared};
      } catch (error) {
        if (destroyed || token !== epoch) { staleCount += 1; return {status: "stale", token, error}; }
        if (options.onLoading) options.onLoading(false, query, token);
        if (options.onError) options.onError(error, query, token);
        return {status: "error", token, error};
      }
    }
    return {
      select,
      destroy() { destroyed = true; epoch += 1; },
      snapshot() { return {epoch, destroyed, staleCount}; }
    };
  }

  function createBrowserRenderer(root) {
    const doc = root.document;
    const byId = id => doc.getElementById(id);
    /* 0717 #28:目标格发光壳+格口箭头实体由 02 页母版创建并挂 __S3_TARGET_FX;判空跳过。
       存取双向分两态:入库=金色收敛(同 01),出库源位=淡出转灰(下面 targetFxGrey)。 */
    const targetFx = root.__S3_TARGET_FX || null;
    const targetFxGrey = targetFx ? new THREE.Color(0x707a85) : null;
    const topologyAudit = validateVisualTopology(Object.assign({io: IO, transfer: TRANSFER_ANCHOR, infeed: INFEED, outfeed: OUTFEED,
      infeedEnvelope: CONVEYOR_ENVELOPES.infeed, outfeedEnvelope: CONVEYOR_ENVELOPES.outfeed}, TRANSFER_TOPOLOGY));
    const stockGroup = new THREE.Group(), queueGroup = new THREE.Group();
    scene.add(stockGroup); scene.add(queueGroup);
    if (cargo.parent) cargo.parent.remove(cargo);
    scene.add(cargo); cargo.visible = false;

    const gradeMaterial = {heavy: M.heavy, mid: M.mid, light: M.light};
    const gradeCssColor = grade => grade === "heavy" ? "#102a43" : grade === "light" ? "#42c7e6" : "#006bb6";
    /* 在库货物严格来自事件库存快照。按等级实例化箱体，再用一组深色箱盖补足体积边界；
       不再叠加会遮住等级色的绿色实心外壳，仍保持 4 次绘制。 */
    const stockCapacity = N * N, stockDummy = new THREE.Object3D();
    const stockBodyGeometry = new THREE.BoxGeometry(.70, .72, .58);
    const stockLidGeometry = new THREE.BoxGeometry(.74, .76, .10);
    /* 0718 再修(用户指正,正确):热度色**不涂在货箱上**——货箱本体保留等级(重/中/轻)色,
       可读性不被牺牲(等级是稳定性/能耗评分维度)。热度改由「货位背板」承载(见下 cellHeatMesh)。
       行业惯例(Slot3D/WarehouseBlueprint)亦是「按库位的拣选活跃度给库位着色」——热度属于**位置**,不是画在货物身上。 */
    const stockGradeMeshes = Object.fromEntries(Object.entries(gradeMaterial).map(([grade, material]) => {
      const mesh = new THREE.InstancedMesh(stockBodyGeometry, material, stockCapacity);
      mesh.count = 0; mesh.castShadow = false; mesh.receiveShadow = false; stockGroup.add(mesh); return [grade, mesh];
    }));
    /* 货位热度背板:薄板贴在货箱正后方(比箱体宽),正面看=围绕货箱的一圈色环 → 热度可读且不遮挡等级色。
       只给**在库货位**上色:空位无存储活动、自然无热度(诚实呈现,不编造)。 */
    const cellHeatGeometry = new THREE.BoxGeometry(.96, .02, .96);
    const cellHeatMesh = new THREE.InstancedMesh(cellHeatGeometry, new THREE.MeshBasicMaterial({color: 0xffffff}), stockCapacity);
    cellHeatMesh.count = 0; cellHeatMesh.castShadow = false; cellHeatMesh.receiveShadow = false;
    cellHeatMesh.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(stockCapacity * 3).fill(1), 3);
    stockGroup.add(cellHeatMesh);
    /* 0718 #26-2 改版:弃逐箱金顶,顶盖改「货位色阶热力图」——每箱盖按 freq_true 归一化连续上色(冷蓝→琥珀→热红),
       用 InstancedMesh.instanceColor(setColorAt)零额外几何。材质基色设白,让 instanceColor 就是真实热度色;仍保持 4 次绘制。 */
    /* 顶盖用 MeshBasicMaterial(平涂不受光)让 instanceColor 满饱和呈现,热度色如实可读;基色白=最终色即热度色。 */
    const stockLidMaterial = M.lid;
    const stockLidMesh = new THREE.InstancedMesh(stockLidGeometry, stockLidMaterial, stockCapacity);
    stockLidMesh.count = 0; stockLidMesh.castShadow = false; stockLidMesh.receiveShadow = false; stockGroup.add(stockLidMesh);
    /* 注:instanceColor 必须按容量预分配。three.js 的 setColorAt 首调时按当时 count 分配,若 count 还是 0
       会分配成 Float32Array(0),后续 setColorAt 全部写入虚空(本轮实测踩过:colorArrayLen=0、色阶恒不显现)。
       见上 cellHeatMesh 的预分配。 */
    /* 色阶:三段插值 冷=中性浅灰(#aeb8c0)→琥珀(#e7b800)→热红(#c0392b);t 由 freq_true 的秩归一化。
       冷端**不用蓝**:货箱等级色本身是蓝系(重/中/轻),冷蓝框会与蓝箱语义撞色糊成一片;
       改中性灰后低频不抢注意力、暖/热才真正跳出来(注意力预算给热门)。 */
    const HEAT_COLD = new THREE.Color(0xaeb8c0), HEAT_MID = new THREE.Color(0xe7b800), HEAT_HOT = new THREE.Color(0xc0392b);
    const heatScratch = new THREE.Color(), gradeScratch = new THREE.Color();
    function heatColor(t) {
      t = t < 0 ? 0 : t > 1 ? 1 : t;
      return t < .5 ? heatScratch.copy(HEAT_COLD).lerp(HEAT_MID, t * 2)
                    : heatScratch.copy(HEAT_MID).lerp(HEAT_HOT, (t - .5) * 2);
    }
    let freqRank = new Map();
    /* 0718 #26-2 B层·近 I/O 热区包络:热门货(freq_true 前 20%)实际所在格子的包围盒,半透明琥珀块 + 亮描边;随 setTrace 重算。 */
    const hotZoneMat = new THREE.MeshBasicMaterial({color: 0xe7b800, transparent: true, opacity: .10, depthWrite: false, side: THREE.DoubleSide});
    const hotZoneMesh = new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1), hotZoneMat);
    hotZoneMesh.visible = false; hotZoneMesh.renderOrder = 2; scene.add(hotZoneMesh);
    const hotZoneEdges = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(1, 1, 1)),
      new THREE.LineBasicMaterial({color: 0xffb100, transparent: true, opacity: .95}));
    hotZoneEdges.visible = false; hotZoneEdges.renderOrder = 6; scene.add(hotZoneEdges);
    function updateHotZone(trace) {
      const rows = Array.isArray(trace.initial_inventory) ? trace.initial_inventory.filter(r => hotGids.has(r.gid)) : [];
      if (!rows.length) { hotZoneReady = false; applyHeat3D(); return; }
      let minCol = Infinity, maxCol = -Infinity, minTier = Infinity, maxTier = -Infinity;
      rows.forEach(r => { minCol = Math.min(minCol, r.col); maxCol = Math.max(maxCol, r.col);
        minTier = Math.min(minTier, r.tier); maxTier = Math.max(maxTier, r.tier); });
      const cx = (minCol + maxCol + 1) / 2, cz = (minTier + maxTier + 1) / 2;
      const sx = (maxCol - minCol + 1) + .14, sz = (maxTier - minTier + 1) + .14, sy = RACK.depth + .12;
      hotZoneMesh.position.set(cx, RACK.loadY, cz); hotZoneMesh.scale.set(sx, sy, sz);
      hotZoneEdges.position.copy(hotZoneMesh.position); hotZoneEdges.scale.copy(hotZoneMesh.scale);
      hotZoneReady = true; applyHeat3D();
    }
    /* 0718 热度开关:3D(货位色框 + 热区包络)与 2D(左栏货位图热力)各一个。
       开关 DOM 挂在已有的「货位热度」图例面板内——**不动左栏栅格**(该处每加内容都会触发一轮 @media 断点
       适配战,是本页最脆的地方),既保排版协调又保各视口适配性。 */
    let heat3DOn = true, heat2DOn = true, hotZoneReady = false;
    function applyHeat3D() {
      cellHeatMesh.visible = heat3DOn;
      hotZoneMesh.visible = hotZoneEdges.visible = heat3DOn && hotZoneReady;
    }
    const heat3DBox = document.getElementById("heat3dToggle"), heat2DBox = document.getElementById("heat2dToggle");
    if (heat3DBox) { heat3DBox.checked = heat3DOn; heat3DBox.addEventListener("change", () => { heat3DOn = !!heat3DBox.checked; applyHeat3D(); }); }
    if (heat2DBox) { heat2DBox.checked = heat2DOn; heat2DBox.addEventListener("change", () => { heat2DOn = !!heat2DBox.checked; }); }
    const queueBaseGeometry = new THREE.BoxGeometry(.76, .72, .10);
    const queueBoxGeometry = new THREE.BoxGeometry(.69, .66, .58);
    const queueEdgeGeometry = new THREE.EdgesGeometry(queueBoxGeometry);
    const queueEdgeMaterial = new THREE.LineBasicMaterial({color: 0x17202b});
    const activeMaterial = {};
    Object.keys(gradeMaterial).forEach(key => {
      activeMaterial[key] = gradeMaterial[key].clone();
      activeMaterial[key].transparent = true; activeMaterial[key].opacity = 1;
    });
    const inventory = new Map(), stockPool = [], queuePool = [], livePaths = [];
    let catalog = new Map(), currentTrace = null, stockSignature = "", pathSignature = "", tooltipSerial = 0, lastFrame = null, lastQueueGids = [], lastOverlayLayout = null, lastStationLayout = null;
    let lastStockGradeCounts = {heavy: 0, mid: 0, light: 0};
    /* 0717 #26-2 热门集合:cargo_catalog[].freq_true 降序前 1/5,随每条 trace 在 setTrace 内重算。 */
    let hotGids = new Set();

    function good(gid) {
      const value = catalog.get(gid);
      invariant(value, `cargo_catalog 缺少 gid=${gid}`);
      return value;
    }

    function stockCreate(row) {
      const wrapper = {row: null}; stockUpdate(wrapper, row); return wrapper;
    }

    function stockUpdate(wrapper, row) {
      wrapper.row = Object.assign({}, row);
    }

    function stockRemove(wrapper) {
      wrapper.row = null;
    }

    function rebuildStockInstances() {
      const gradeCounts = {heavy: 0, mid: 0, light: 0};
      let lidCount = 0;
      inventory.forEach(wrapper => {
        const row = wrapper.row, item = good(row.gid), grade = stockGradeMeshes[item.grade] ? item.grade : "mid";
        /* 货位热度背板(位置着色):贴在货箱正后方,正面看是一圈色环,不遮挡箱体等级色 */
        stockDummy.position.set(row.col + .5, RACK.loadY + .38, row.tier + .5); stockDummy.updateMatrix();
        cellHeatMesh.setMatrixAt(lidCount, stockDummy.matrix);
        cellHeatMesh.setColorAt(lidCount, heatColor(freqRank.has(row.gid) ? freqRank.get(row.gid) : .5));
        /* 货箱本体=等级色(重/中/轻),保持原样不被热度覆盖 */
        stockDummy.position.set(row.col + .5, RACK.loadY, row.tier + .43); stockDummy.updateMatrix();
        stockGradeMeshes[grade].setMatrixAt(gradeCounts[grade]++, stockDummy.matrix);
        stockDummy.position.set(row.col + .5, RACK.loadY, row.tier + .77); stockDummy.updateMatrix();
        stockLidMesh.setMatrixAt(lidCount, stockDummy.matrix);
        lidCount += 1;
      });
      stockLidMesh.count = lidCount; stockLidMesh.instanceMatrix.needsUpdate = true;
      cellHeatMesh.count = lidCount; cellHeatMesh.instanceMatrix.needsUpdate = true;
      if (cellHeatMesh.instanceColor) cellHeatMesh.instanceColor.needsUpdate = true;
      Object.entries(stockGradeMeshes).forEach(([grade, mesh]) => {
        mesh.count = gradeCounts[grade]; mesh.instanceMatrix.needsUpdate = true;
        if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
      });
      lastStockGradeCounts = gradeCounts;
    }

    function setInventory(rows) {
      const nextSignature = rows.map(row => {
        const item = good(row.gid); return `${row.gid}:${row.col}/${row.tier}:${item.grade}`;
      }).join("|");
      if (nextSignature === stockSignature) return;
      stockSignature = nextSignature;
      reconcileInventoryMap(inventory, rows, {create: stockCreate, update: stockUpdate, remove: stockRemove});
      rebuildStockInstances();
    }

    function ensureQueueUnit(index) {
      while (queuePool.length <= index) {
        const unit = new THREE.Group();
        const base = new THREE.Mesh(queueBaseGeometry, M.wood);
        const box = new THREE.Mesh(queueBoxGeometry, M.mid);
        base.position.z = .12; box.position.z = .48; base.castShadow = box.castShadow = true;
        box.add(new THREE.LineSegments(queueEdgeGeometry, queueEdgeMaterial));
        unit.add(base, box); queueGroup.add(unit); queuePool.push({unit, box});
      }
      return queuePool[index];
    }

    /* 队列最多可见 4 件；一次性预热，长跑期间只切 visible，不再懒增长场景图。 */
    ensureQueueUnit(3); queuePool.forEach(item => { item.unit.visible = false; });

    function setQueue(gids) {
      const shown3d = gids.slice(0, 4), shownRail = gids.slice(0, 2); lastQueueGids = shown3d.slice();
      queuePool.forEach(item => { item.unit.visible = false; });
      shown3d.forEach((gid, index) => {
        const item = ensureQueueUnit(index), cargoGood = good(gid);
        item.unit.visible = true; item.unit.position.set(INFEED.entryX - .78 - index * .76, INFEED.y, 0); item.unit.userData = {gid, owner: "QUEUE_WAITING", lane: "INFEED"};
        item.box.material = gradeMaterial[cargoGood.grade] || M.mid;
      });
      const strip = byId("queueStrip");
      strip.replaceChildren();
      if (!gids.length) {
        const empty = doc.createElement("em"); empty.textContent = "当前无等待货物"; strip.append(empty);
      } else {
        shownRail.forEach(gid => {
          const cargoGood = good(gid), chip = doc.createElement("span");
          chip.textContent = cargoGood.name; chip.style.borderLeftColor = cargoGood.grade === "heavy" ? "#0b2e4f" : cargoGood.grade === "light" ? "#006a7a" : "#0057b8";
          strip.append(chip);
        });
        if (gids.length > shownRail.length) { const more = doc.createElement("em"); more.textContent = `+${gids.length - shownRail.length}`; strip.append(more); }
      }
      byId("queueMeta").textContent = `${gids.length} 等待`;
    }

    function disposePath(path) {
      scene.remove(path.group);
      path.group.traverse(object => { if (object.geometry) object.geometry.dispose(); });
      path.material.dispose();
      if (path.haloMaterial) path.haloMaterial.dispose();
    }

    function clearPaths() { while (livePaths.length) disposePath(livePaths.pop()); }

    function setPaths(trace, event) {
      const signature = `${trace.meta.trace_id}|${event.cycle}|${event.store_slot.col}/${event.store_slot.tier}|${event.retrieve_slot.col}/${event.retrieve_slot.tier}`;
      if (signature === pathSignature) return;
      pathSignature = signature; clearPaths();
      const colors = {"cargo-in": 0x183f68, handle: 0x7a4aa8, empty: 0x6e7881, "cargo-out": 0x0084a8};
      const geometry = {io: IO, transfer: TRANSFER_ANCHOR, infeed: INFEED, outfeed: OUTFEED,
        cargoZOffset: CARGO_Z_OFFSET, cargoDrop: CARGO_DROP, cargoReach: CARGO_REACH};
      operationPathPlan(trace, event, geometry).forEach(plan => {
        const points = plan.points.map(point => new THREE.Vector3(point.x, point.y, point.z));
        const path = addPath(points, {color: colors[plan.kind], opacity: .28, radius: .065, haloRadius: .12, arrowCount: plan.arrowCount, operationKey: plan.operationKey, kind: plan.kind});
        path.operationKey = plan.operationKey; path.kind = plan.kind; path.baseColor = colors[plan.kind];
        path.auditPoints = plan.points.map(point => ({x: point.x, y: point.y, z: point.z}));
        livePaths.push(path);
      });
    }

    function updatePathEmphasis(operationKey) {
      const current = STEP_INDEX[operationKey];
      livePaths.forEach(path => {
        const index = STEP_INDEX[path.operationKey];
        path.material.color.setHex(index === current ? 0xff6a00 : path.baseColor);
        path.material.opacity = index === current ? .96 : index < current ? .42 : .24;
        path.material.depthTest = index !== current;
        if (path.haloMaterial) path.haloMaterial.opacity = index === current ? .84 : index < current ? .10 : 0;
        path.group.traverse(object => { if (object.isMesh) object.renderOrder = index === current ? (object.material === path.material ? 6 : 5) : 1; });
      });
    }

    function setMachine(frame) {
      const worldX = frame.machine.x + .5, worldZ = frame.machine.z + .5;
      mast.position.x = worldX; machineParts.forEach(part => { part.position.x = worldX; });
      carrier.position.set(worldX, IO.y, worldZ);
      const beltLength = Math.max(.45, N - worldZ + .05), beltCenter = (N + worldZ) / 2;
      liftBelts.forEach(belt => { belt.scale.z = beltLength; belt.position.z = beltCenter; });
      forkGroup.position.set(0, 0, 0);
      if (["STORE_HANDLE", "RETRIEVE_HANDLE"].includes(frame.operationKey)) {
        const p = frame.operationProgress;
        const extension = p < .48 ? ease(p / .48) : p < .60 ? 1 : 1 - ease((p - .60) / .40);
        forkExtension = FORK_MAX * extension; forkGroup.position.y = forkExtension;
        /* 与 setCargo 共用同一 drop，保证放货低位抽叉、取货低位插叉。 */
        forkDrop = handleCargoDrop(frame.operationKey, p, CARGO_DROP);
        forkGroup.position.z = -forkDrop;
      } else { forkExtension = 0; forkDrop = 0; }
      return {worldX, worldZ};
    }

    function setCargo(frame, machineWorld) {
      if (frame.cargoGid === null || frame.cargoGid === undefined || frame.cargoOwner === "CONSUMED") {
        cargo.visible = false;
        cargo.userData = {gid: null, owner: frame.cargoOwner || null, operationKey: frame.operationKey};
        return;
      }
      const cargoGood = good(frame.cargoGid), material = activeMaterial[cargoGood.grade] || activeMaterial.mid;
      Object.values(activeMaterial).forEach(item => { item.opacity = 1; });
      cargo.material = material; cargo.visible = true;
      cargo.userData = {gid: frame.cargoGid, owner: frame.cargoOwner || null, operationKey: frame.operationKey};
      const position = cargoWorldPosition(frame, machineWorld, {
        io: IO, transfer: TRANSFER_ANCHOR, infeed: INFEED, outfeed: OUTFEED,
        cargoZOffset: CARGO_Z_OFFSET, cargoDrop: CARGO_DROP, cargoReach: CARGO_REACH
      });
      if (frame.operationKey === "SCAN_EXIT") material.opacity = frame.cargoOwner === "EXIT_MASK" ? 1 - frame.phaseProgress * .88 : 1;
      cargo.position.set(position.x, position.y, position.z);
    }

    function setTarget(frame) {
      const visible = Array.isArray(frame.targetSlot);
      targetBox.visible = targetPad.visible = visible;
      if (targetFx && !visible) { targetFx.glow.visible = targetFx.face.visible = targetFx.arrow.visible = false; }
      if (!visible) return;
      const [col, tier] = frame.targetSlot;
      targetBox.position.set(col + .5, RACK.loadY, tier + .5);
      targetPad.position.set(col + .5, RACK.loadY, tier + .075);
      const beacon = byId("targetBeacon");
      const inbound = ["LOAD_IN", "INBOUND_TRAVEL", "STORE_HANDLE"].includes(frame.operationKey);
      beacon.querySelector("b").textContent = `${inbound ? "入库目标" : "出库源位"} ${String(col).padStart(2, "0")} / ${String(tier).padStart(2, "0")}`;
      beacon.querySelector("span").textContent = `第 ${String(col).padStart(2, "0")} 列 · 第 ${String(tier).padStart(2, "0")} 层`;
      beacon.setAttribute("aria-label", `${inbound ? "入库目标货位" : "出库源货位"}，列 ${col}，层 ${tier}`);
      /* 0717 #28 用户拍板:目标格强高亮。存取双向分两态——
         入库(LOAD_IN/INBOUND_TRAVEL/STORE_HANDLE):金色发光壳+竖直箭头,STORE_HANDLE 收尾判定完成→金色收敛(稳定亮金、箭头收起);
         出库源位(LINK_TRAVEL/RETRIEVE_HANDLE):淡出转灰,RETRIEVE_HANDLE 随取货推进整体淡出、箭头收起。
         呼吸/淡出的每帧透明度在 renderFrame 里按 glow.userData.mode 驱动(相位取 frame.simTime,seek 可复现)。 */
      if (targetFx) {
        /* 0718 #28 修穿模:目标 FX(glow/face/arrow)只在「行进接近目标」段显示;进入 handle 段
           (STORE_HANDLE/RETRIEVE_HANDLE)整体隐藏——此时货叉/mast/货物占据目标格,FX 会与之穿插。
           配色分支(入库金 / 出库淡灰)仅在 travel 段生效。 */
        const handling = ["STORE_HANDLE", "RETRIEVE_HANDLE"].includes(frame.operationKey);
        /* 0718 追加门:只按 operationKey 分段仍漏「行进段末尾已到位」——实测 INBOUND_TRAVEL p=.95 与
           LINK_TRAVEL p=.95 的 |machine.x - col| = 0.00 / 0.02,此时竖直箭头正落在堆垛机机身里被吞掉
           (工装 scratchpad/fxsweep.mjs 可复现)。故再按几何距离关一道:近于机身半宽(载货台 1.05 宽)即收起箭头。
           发光壳与格口面留着——它们贴在货位上,不与机身争位,仍需指示目标。 */
        const arrived = frame.machine ? Math.abs(frame.machine.x - col) < .60 : false;
        if (handling) {
          targetFx.glow.visible = targetFx.face.visible = targetFx.arrow.visible = false;
        } else {
          targetFx.glow.visible = true; targetFx.glow.position.set(col + .5, RACK.loadY, tier + .5);
          targetFx.face.visible = true; targetFx.face.position.set(col + .5, RACK.frontY - .012, tier + .5);
          targetFx.arrow.visible = !arrived;
          targetFx.arrow.position.set(col + .5, targetFx.arrowY, tier + targetFx.arrowZGap);
          targetFx.arrow.userData.baseZ = tier + targetFx.arrowZGap;
          const ud = targetFx.glow.userData;
          if (inbound) {
            targetFx.glowMat.color.copy(targetFx.amber); targetFx.faceMat.color.copy(targetFx.amber);
            ud.mode = "inbound"; ud.fade = 1;
          } else {
            targetFx.glowMat.color.copy(targetFxGrey); targetFx.faceMat.color.copy(targetFxGrey);
            ud.mode = "outbound"; ud.fade = 1;
          }
        }
      }
    }

    function metricChip(label, value, description, sub) {
      const button = doc.createElement("button"), number = doc.createElement("b");
      const caption = doc.createElement("small"), tip = doc.createElement("span");
      const tipId = `s3-tip-${++tooltipSerial}`;
      button.type = "button"; button.className = "metricHelp";
      button.setAttribute("aria-label", `${label} ${value}；按 Enter 或空格查看定义`);
      button.setAttribute("aria-describedby", tipId); button.setAttribute("aria-expanded", "false");
      number.textContent = value; caption.textContent = label;
      if (sub) { const caliber = doc.createElement("i"); caliber.className = "statCaliber"; caliber.textContent = sub; caption.append(caliber); }
      tip.id = tipId; tip.className = "tipBubble"; tip.setAttribute("role", "tooltip"); tip.textContent = description;
      button.append(number, caption, tip);
      const setOpen = open => {
        button.classList.toggle("is-open", open);
        button.setAttribute("aria-expanded", String(open));
      };
      button.addEventListener("mouseenter", () => setOpen(true));
      button.addEventListener("mouseleave", () => { if (doc.activeElement !== button) setOpen(false); });
      button.addEventListener("focus", () => setOpen(true));
      button.addEventListener("blur", () => setOpen(false));
      button.addEventListener("click", () => setOpen(true));
      button.addEventListener("keydown", event => {
        if (event.key !== "Escape") return;
        event.preventDefault(); setOpen(false); button.blur();
      });
      return button;
    }

    function renderDecision(trace) {
      const host = byId("decisionWrap"), router = trace.router, requested = trace.meta.strategy_mode;
      const picked = STRATEGY_LABEL[router.picked] || String(router.picked).toUpperCase();
      const chain = `${STRATEGY_LABEL[router.initial_strategy] || router.initial_strategy} → ${STRATEGY_LABEL[router.online_strategy] || router.online_strategy}`;
      const routedExtra = requested === "AUTO" && ["cb", "tob"].includes(router.picked);
      const title = requested === "AUTO" ? `${routedExtra ? "AUTO 路由额外策略" : "AUTO 已选择"} · ${picked}` : `人工固定 ${STRATEGY_LABEL[requested] || requested}`;
      const judgeRoute = byId("judgeRoute"), judgeRouteMeta = byId("judgeRouteMeta");
      if (judgeRoute) judgeRoute.textContent = requested === "AUTO" ? `AUTO · ${chain}` : `固定 · ${picked}`;
      if (judgeRouteMeta) judgeRouteMeta.textContent = requested === "AUTO" ? "启动时一次选定 · SIM" : "人工固定策略 · SIM";
      host.replaceChildren();
      const head = doc.createElement("div"); head.className = "dHead";
      const strong = doc.createElement("b"), scope = doc.createElement("span"); strong.textContent = title; scope.textContent = "启动时一次选定 · SIM"; head.append(strong, scope);
      const selection = doc.createElement("div"); selection.className = "selectionSummary";
      const summaryStrong = doc.createElement("strong"), summaryText = doc.createElement("span"); summaryStrong.textContent = chain; summaryText.textContent = requested === "AUTO" ? "启动时一次选定" : "AUTO 未接管"; selection.append(summaryStrong, summaryText);
      const reason = doc.createElement("div"); reason.className = "proofLead"; reason.textContent = router.reason;
      const signals = doc.createElement("div"); signals.className = "routeSignals";
      const facts = [
        [`ρ ${router.profile.density.toFixed(3)}`, "初始密度"],
        [`skew ${router.profile.skew.toFixed(3)}`, "频率偏斜"],
        [`n ${router.profile.n}`, "初始货量"]
      ];
      facts.forEach(([value, label]) => { const item = doc.createElement("span"); item.textContent = `${value} · ${label}`; signals.append(item); });
      const advanced = doc.createElement("details"), advancedSummary = doc.createElement("summary"), advancedBody = doc.createElement("div");
      advanced.className = "decisionAdvanced"; advancedSummary.textContent = router.online_strategy === "score" ? "路由参数 / 候选位权重" : "路由参数 / 本链无候选评分";
      advancedBody.className = "advancedBody"; advancedBody.append(signals); advanced.append(advancedSummary, advancedBody);
      advanced.addEventListener("keydown", event => {
        if (event.key !== "Escape" || !advanced.open) return;
        event.preventDefault(); advanced.removeAttribute("open"); advancedSummary.focus();
      });
      /* 0719 功能批次 D4:AUTO 参数展开器移入证据叠层(ISA-101 L3 细节层);常驻卡只留策略行 */
      host.append(head, selection, reason);
      const evPanel = doc.querySelector("#evidenceDock .evidencePanel");
      if (evPanel) {
        const oldAdvanced = evPanel.querySelector(".decisionAdvanced"); if (oldAdvanced) oldAdvanced.remove();
        evPanel.append(advanced);
      } else host.append(advanced);

      if (router.online_strategy === "score") {
        const weights = trace.meta.score_weights && trace.meta.score_weights.online;
        invariant(Array.isArray(weights) && weights.length === 4 && weights.every(Number.isFinite), "score trace 缺少四项在线权重");
        const block = doc.createElement("div"); block.className = "weightBlock";
        const weightHead = doc.createElement("div"); weightHead.className = "weightHead";
        const weightTitle = doc.createElement("b"), weightScope = doc.createElement("span");
        weightTitle.textContent = "候选位目标权重"; weightScope.textContent = "Σw·h 越低越优"; weightHead.append(weightTitle, weightScope);
        const grid = doc.createElement("div"); grid.className = "weightGrid";
        const definitions = [
          ["效率", `α ${weights[0].toFixed(2)}`, "效率项 h_eff=(频次/最大频次)×(行程时间/最大时间)，惩罚高频货放远位。此处只显示权重，不是本周期分值。"],
          ["稳定", `β ${weights[1].toFixed(2)}`, "稳定项 h_stab=(重量/最大重量)×(层高/最高层)，惩罚重货放高层。此处只显示权重，不是本周期分值。"],
          ["能耗", `γ ${weights[2].toFixed(2)}`, "能耗项 h_energy=(重量×层高×单元高度)/(最大重量×最大高度)，是归一化提升做功代理，不是 kWh。此处只显示权重。"],
          ["预留", `δ ${weights[3].toFixed(2)}`, "预留项 h_resv=(1−频次归一)×(1−时间归一)，惩罚冷门货占用近位，为热门货保留稀缺近位。此处只显示权重。"]
        ];
        definitions.forEach(([label, value, description]) => grid.append(metricChip(label, value, description)));
        const note = doc.createElement("div"); note.className = "weightNote"; note.textContent = "权重，不是本周期分值；当前界面不伪造候选位排名。";
        block.append(weightHead, grid, note); advancedBody.append(block);
      } else {
        const note = doc.createElement("div"); note.className = "weightNote";
        note.textContent = "本链不调用四项候选位评分函数；因此不显示伪评分。";
        advancedBody.append(note);
      }
    }

    function renderTraceStats(trace) {
      const host = byId("traceStats"), stats = trace.stats;
      host.replaceChildren();
      const head = doc.createElement("div"); head.className = "statsHead";
      const title = doc.createElement("b"), scope = doc.createElement("span");
      title.textContent = "本批统计"; scope.textContent = "单 seed · SIM";
      scope.title = "当前 trace；不与 S1 多 seed 聚合合并"; head.append(title, scope);
      const grid = doc.createElement("div"); grid.className = "statsGrid";
      const tierBoundary = trace.meta.tier === 3 ? "Tier 3 响应包含等待、装卸与故障恢复。" : `Tier ${trace.meta.tier} 不包含 Tier 3 的等待、装卸与故障恢复。`;
      /* N1 行程格:闭环曼哈顿长度(I/O(0,0)→存→取→I/O),格间距 1 m,口径 C2 与 AB 侧 FC_CalcPathLen 同源 */
      const manhTotal = trace.events.reduce((sum, ev) => sum
        + ev.store_slot.col + ev.store_slot.tier
        + Math.abs(ev.retrieve_slot.col - ev.store_slot.col) + Math.abs(ev.retrieve_slot.tier - ev.store_slot.tier)
        + ev.retrieve_slot.col + ev.retrieve_slot.tier, 0);
      const metrics = [
        ["响应 P50", `${Number(stats.response_p50_s).toFixed(1)} s`, `当前 100 周期单 seed 响应时间的中位数。${tierBoundary}`],
        ["响应 P95", `${Number(stats.response_p95_s).toFixed(1)} s`, `当前 100 周期单 seed 响应时间的 95 分位数。${tierBoundary}`,
          trace.meta.tier === 3 ? "口径:含队列等待·装卸·故障恢复" : null],
        ["设备利用率", `${(Number(stats.utilization) * 100).toFixed(1)}%`, "当前 trace 的 productive busy time / performance finish time；busy 为双轴作业忙时，不含故障停机。"],
        ["峰值等待", String(stats.queue_peak_waiting), "当前 trace 全程的最大等待队列长度，只计 waiting，不含正在作业的货物。"],
        ["模型故障", String(stats.faults), `当前 trace 中由 sim 故障流建模出的故障次数，不代表现场 PLC 故障实测。${Number(stats.faults) > 0 ? "点击跳到故障回放。" : ""}`],
        ["约束违规", String(stats.violations), "当前 trace 的硬约束违规计数；验收要求为 0。"],
        ["周期均行程", `${(manhTotal / Math.max(1, trace.events.length)).toFixed(1)} m`,
          `闭环行程(入库+交织+出库)的曼哈顿长度周期均值，格间距 1 m。口径 C2：与 AB 画面 FB_Stats.PathLength 同源，与时间指标并列呈现不混用。百周期总行程 ${manhTotal} m。`]
      ];
      metrics.forEach(([label, value, description, sub]) => {
        const chip = metricChip(label, value, description, sub);
        if (label === "模型故障" && Number(stats.faults) > 0) {
          chip.classList.add("statJump");
          chip.addEventListener("click", () => { try { root.__S3_QA.seekFault(0); } catch (error) {} });
        }
        grid.append(chip);
      });
      /* N3 复现指纹:seed + trace_id + 口径批。sim_only 由 trace 断言保证 */
      const finger = doc.createElement("div"); finger.className = "statFinger";
      finger.textContent = `复现:seed ${trace.meta.seed} · ${trace.meta.trace_id || "trace"} · sim_only · 统计口径同批 ${trace.meta.cycles} 周期`;
      host.append(head, grid, finger);
      const judgeEvidence = byId("judgeEvidence"), judgeEvidenceMeta = byId("judgeEvidenceMeta");
      if (judgeEvidence) judgeEvidence.textContent = `P95 ${Number(stats.response_p95_s).toFixed(1)}s · 违规 ${stats.violations}`;
      if (judgeEvidenceMeta) judgeEvidenceMeta.textContent = `S3 单 seed · 故障 ${stats.faults}；S1 10 seeds 对照另列`;
      renderOpsEvidence(trace);
      renderRespSpark(trace);
      renderFaultMarks(trace);
      renderEvidenceExtras(trace);
    }

    /* M2 响应趋势 sparkline:数据=trace.events[].response(与批统计同源),P95 参考线=stats.response_p95_s(同口径,不另算分位)。 */
    function renderRespSpark(trace) {
      let host = byId("respSpark");
      if (!host) {
        const statsHost = byId("traceStats");
        if (!statsHost || !statsHost.parentElement) return;
        host = doc.createElement("section"); host.id = "respSpark"; statsHost.after(host);
      }
      const p95 = Number(trace.stats.response_p95_s);
      host.innerHTML = `<div class="sparkHead"><b>响应时间趋势 · ${trace.events.length} 周期</b><span>虚线 = P95 ${p95.toFixed(1)}s(同批口径)· 红点 = 故障周期</span></div>`;
      const canvas = doc.createElement("canvas"); host.append(canvas);
      const width = Math.max(60, host.clientWidth - 18), height = 26, dpr = 2;
      canvas.style.width = "100%"; canvas.style.height = `${height}px`;
      canvas.width = Math.round(width * dpr); canvas.height = height * dpr;
      const ctx = canvas.getContext("2d"); ctx.scale(dpr, dpr);
      const values = trace.events.map(ev => Number(ev.response));
      const max = Math.max(p95, ...values), pad = 2, n = values.length;
      const X = i => pad + (n > 1 ? i / (n - 1) : 0) * (width - pad * 2);
      const Y = v => height - pad - (max > 0 ? v / max : 0) * (height - pad * 2);
      ctx.strokeStyle = "#c9a227"; ctx.setLineDash([3, 3]);
      ctx.beginPath(); ctx.moveTo(pad, Y(p95)); ctx.lineTo(width - pad, Y(p95)); ctx.stroke(); ctx.setLineDash([]);
      ctx.strokeStyle = "#17365d"; ctx.lineWidth = 1.1; ctx.beginPath();
      values.forEach((v, i) => { if (i) ctx.lineTo(X(i), Y(v)); else ctx.moveTo(X(0), Y(v)); }); ctx.stroke();
      ctx.fillStyle = "#c62828";
      trace.events.forEach((ev, i) => { if (ev.faulted) { ctx.beginPath(); ctx.arc(X(i), Y(values[i]), 2.4, 0, 7); ctx.fill(); } });
    }

    /* M1 故障周期标记:轴行红点(按周期号百分比定位),点击经公开 API seekFault 跳到该故障回放。幂等:每次重渲清旧点。 */
    function renderFaultMarks(trace) {
      const track = byId("cycleAxisTrack"); if (!track) return;
      track.querySelectorAll(".axisFaultDot").forEach(el => el.remove());
      let faultOrder = -1;
      trace.events.forEach(ev => {
        if (!ev.faulted) return;
        faultOrder += 1; const orderNow = faultOrder;
        const dot = doc.createElement("button"); dot.type = "button"; dot.className = "axisFaultDot";
        dot.style.left = `${(ev.cycle_number / trace.meta.cycles * 100).toFixed(2)}%`;
        dot.title = `故障周期 #${ev.cycle_number} · 点击跳到故障回放`;
        dot.setAttribute("aria-label", dot.title);
        const tag = doc.createElement("i"); tag.textContent = `⚠ ${ev.cycle_number}`; dot.append(tag);
        dot.addEventListener("click", event => {
          event.stopPropagation();
          try { root.__S3_QA.seekFault(orderNow); } catch (error) {}
        });
        track.append(dot);
      });
    }

    /* N4 故障卡 + N2 差值 CI(叠层,甲版收纳)。CI 数据源=out/s3_mixed_dispatch_sweep.js(30 seed 调度 sweep,
       独立于 S1 矩阵与当前 trace——manifest 红线 do_not_compare_or_merge,故只在叠层独立面板呈现并标注口径)。 */
    function renderEvidenceExtras(trace) {
      const panel = doc.querySelector("#evidenceDock .evidencePanel"); if (!panel) return;
      let fault = byId("evFaultCard");
      if (!fault) { fault = doc.createElement("section"); fault.id = "evFaultCard"; panel.append(fault); }
      const faultEv = trace.events.find(item => item.faulted);
      if (faultEv) {
        const mttr = trace.meta.tier3_params ? Number(trace.meta.tier3_params.fault_mttr_s) : null;
        fault.hidden = false;
        fault.innerHTML = `<b>故障演示 · 第 ${faultEv.cycle_number} 周期</b><span>${mttr ? `停机 ${mttr}s(MTTR 模型)· ` : ""}该周期响应 ${Number(faultEv.response).toFixed(0)}s;可跳到故障回放复验「停机 → 队列积压 → 恢复消化」全过程。</span><button type="button" id="evFaultJump">跳到故障回放</button>`;
        fault.querySelector("#evFaultJump").addEventListener("click", () => {
          try { root.__S3_QA.seekFault(0); const close = byId("closeEvidenceDock"); if (close) close.click(); } catch (error) {}
        });
      } else { fault.hidden = true; fault.innerHTML = ""; }
      let ci = byId("evCiPanel");
      if (!ci) { ci = doc.createElement("section"); ci.id = "evCiPanel"; panel.append(ci); }
      const sweep = root.S3_MIXED_DISPATCH_SWEEP;
      if (!sweep || !Array.isArray(sweep.rows) || !sweep.rows.length) {
        ci.innerHTML = '<b>多 seed 稳健性</b><div class="ciNote">sweep 证据未加载(out/s3_mixed_dispatch_sweep.js)。</div>'; return;
      }
      const rows = sweep.rows;
      if (rows.length !== 30) { ci.innerHTML = `<b>多 seed 稳健性</b><div class="ciNote">seed 数 ${rows.length} ≠ 30,t 临界值须更新后才能出 CI(拒绝近似)。</div>`; return; }
      const T_CRIT = 2.045; /* t(0.975, df=29) */
      const st = arr => { const n = arr.length, m = arr.reduce((a, b) => a + b, 0) / n;
        const sd = Math.sqrt(arr.reduce((a, b) => a + (b - m) ** 2, 0) / (n - 1)); return { n, m, sd, half: T_CRIT * sd / Math.sqrt(n) }; };
      const diff = st(rows.map(r => r.lanes.seq.avg_retr_s - r.lanes.score.avg_retr_s));
      const seq = st(rows.map(r => r.lanes.seq.avg_retr_s)), sco = st(rows.map(r => r.lanes.score.avg_retr_s));
      let fails = 0, viol = 0; rows.forEach(r => Object.values(r.lanes).forEach(lane => { fails += lane.fails; viol += lane.viol; }));
      const span = 24;
      const pct = v => Math.max(0, Math.min(100, v / span * 100)).toFixed(1);
      const bar = (label, s, color) =>
        `<div class="ciRow"><span>${label}</span><span class="ciTrack"><i style="left:${pct(s.m - s.sd)}%;width:${(pct(s.m + s.sd) - pct(s.m - s.sd)).toFixed(1)}%;background:${color}55"></i><i class="ciMean" style="left:${pct(s.m)}%;background:${color}"></i></span><code>${s.m.toFixed(1)}±${s.sd.toFixed(1)}s</code></div>`;
      ci.innerHTML = `<b>多 seed 稳健性 · ${rows.length} seed × ${sweep.cycles} 周期</b>`
        + bar("SEQ", seq, "#8a96a1") + bar("SCORE", sco, "#0057b8")
        + `<div class="ciDelta">Δ=${diff.m.toFixed(2)}s,95%CI [${(diff.m - diff.half).toFixed(2)}, ${(diff.m + diff.half).toFixed(2)}](配对 t,df=29)</div>`
        + `<div class="ciNote">口径:调度 sweep 单趟平均取货响应(${sweep.schema});独立数据源,不与 S1 对照或本页批统计直接比较。全体 fails=${fails}、violations=${viol}。横条 = 均值±1sd,量程 0-${span}s。</div>`;
    }

    /* 0719 任务b · 存取对置 + 取货实测(零改数据,全部由已加载 trace 现算,可复现):
       - 腿时长 = 七步 process_steps 的 SIM 时刻差(t1-t0),与 trace.stats 同源;
         入库腿 = INBOUND_TRAVEL+STORE_HANDLE;取货腿 = LINK_TRAVEL+RETRIEVE_HANDLE+OUTBOUND_TRAVEL。
       - 热门集合 = cargo_catalog.freq_true 降序前 20%(与 3D 热区 hotGids 同定义,独立重算避免闭包耦合);
         热门/非热门取货均时按 event.outbound_gid 分组 —— 「热门放得近 → 取得快」的直接证据。
       - 省一趟 = 逐周期「store→I/O→retrieve 两段」−「store→retrieve 直达(交织)」,
         用运行时自己的 axisTime(VX/AX/VZ/AZ,双轴同动取 max)按 trace.meta.motion 口径折算 —— 复用官方运动学,非自建模型。 */
    function buildOpsEvidence(trace) {
      const catalog = Array.isArray(trace.cargo_catalog) ? trace.cargo_catalog : [];
      const sorted = catalog.slice().sort((a, b) => Number(b.freq_true) - Number(a.freq_true));
      const hot = new Set(sorted.slice(0, Math.max(1, Math.floor(sorted.length / 5))).map(row => row.gid));
      const motion = trace.meta.motion;
      const leg = (a, b) => Math.max(axisTime(Math.abs(b[0] - a[0]), VX, AX, motion), axisTime(Math.abs(b[1] - a[1]), VZ, AZ, motion));
      let storeSum = 0, retrSum = 0, linkSum = 0, savedSum = 0, hotSum = 0, hotN = 0, coldSum = 0, coldN = 0;
      trace.events.forEach(event => {
        const bySteps = new Map(event.process_steps.map(step => [step.name, step]));
        const span = key => { const step = bySteps.get(key); return step ? Number(step.t1) - Number(step.t0) : 0; };
        const storeLeg = span("INBOUND_TRAVEL") + span("STORE_HANDLE");
        const retrLeg = span("LINK_TRAVEL") + span("RETRIEVE_HANDLE") + span("OUTBOUND_TRAVEL");
        storeSum += storeLeg; retrSum += retrLeg; linkSum += span("LINK_TRAVEL");
        const s = [event.store_slot.col, event.store_slot.tier], r = [event.retrieve_slot.col, event.retrieve_slot.tier];
        savedSum += Math.max(0, leg(s, [0, 0]) + leg([0, 0], r) - leg(s, r));
        if (hot.has(event.outbound_gid)) { hotSum += retrLeg; hotN += 1; } else { coldSum += retrLeg; coldN += 1; }
      });
      const n = trace.events.length || 1;
      return {n, hotN, coldN, motion,
        storeAvg: storeSum / n, retrAvg: retrSum / n, linkAvg: linkSum / n,
        hotAvg: hotN ? hotSum / hotN : 0, coldAvg: coldN ? coldSum / coldN : 0, savedTotal: savedSum};
    }

    function renderOpsEvidence(trace) {
      /* 版面 variant 由 URL ?s3b=dock|rail|axis 声明(三版供用户选择;选定后收敛为单版) */
      if (!doc.documentElement.dataset.s3B) {
        let pick = "dock";
        try { pick = new root.URLSearchParams(root.location.search).get("s3b") || "dock"; } catch (error) {}
        doc.documentElement.dataset.s3B = ["dock", "rail", "axis"].includes(pick) ? pick : "dock";
      }
      const data = buildOpsEvidence(trace);
      const fmt = value => value.toFixed(1);
      const storeShare = Math.round(100 * data.storeAvg / Math.max(1e-9, data.storeAvg + data.retrAvg));
      let host = byId("opsEvidence");
      if (!host) { host = doc.createElement("section"); host.id = "opsEvidence"; host.setAttribute("aria-label", "存取对置与取货实测,SIM 同源"); }
      host.innerHTML = `<div class="oeHead"><b>存取对置 · 取货实测</b><span>单 seed · SIM</span></div>` +
        `<div class="oePair" style="--store:${storeShare}%">` +
        `<div class="oeLeg oeStore"><label>入库腿均时</label><b>${fmt(data.storeAvg)} s</b><i></i></div>` +
        `<div class="oeLeg oeRetr"><label>取货腿均时</label><b>${fmt(data.retrAvg)} s</b><i></i></div></div>` +
        `<div class="oeGrid">` +
        `<div class="oeHot"><b>${fmt(data.hotAvg)} s</b><span>热门件取货均时 · n=${data.hotN}</span></div>` +
        `<div><b>${fmt(data.coldAvg)} s</b><span>非热门取货均时 · n=${data.coldN}</span></div>` +
        `<div><b>${fmt(data.linkAvg)} s</b><span>交织腿均时 · 存→取直达</span></div>` +
        `<div><b>${(data.savedTotal / 60).toFixed(1)} min</b><span>省一趟合计 / ${data.n} 周期</span></div></div>` +
        `<div class="oeNote">腿时长 = 七步 SIM 时刻差；省一趟 = 同一运动学（${data.motion === "constant_speed" ? "匀速" : "加减速"}）折算「回 I/O 再出发 − 直达」</div>`;
      const variant = doc.documentElement.dataset.s3B;
      const target = variant === "rail" ? byId("workHud") : variant === "axis" ? byId("viewport") : byId("sceneDock");
      if (target && host.parentElement !== target) target.append(host);
    }

    function canvasContext(id) {
      const canvas = byId(id), rect = canvas.getBoundingClientRect(), ratio = Math.min(root.devicePixelRatio || 1, 2);
      if (rect.width < 2 || rect.height < 2) return null;
      const width = Math.round(rect.width * ratio), height = Math.round(rect.height * ratio);
      if (canvas.width !== width || canvas.height !== height) { canvas.width = width; canvas.height = height; }
      const context = canvas.getContext("2d"); context.setTransform(ratio, 0, 0, ratio, 0, 0); context.clearRect(0, 0, rect.width, rect.height);
      return {context, width: rect.width, height: rect.height};
    }

    function drawSpeed(frame) {
      const surface = canvasContext("speed"); if (!surface) return;
      const {context: g, width, height} = surface, left = 28, right = width - 8, top = 8, bottom = height - 14;
      g.strokeStyle = "#d8dee3"; g.lineWidth = 1;
      [0, .5, 1].forEach(part => { const y = bottom - part * (bottom - top); g.beginPath(); g.moveTo(left, y); g.lineTo(right, y); g.stroke(); });
      const bars = [{label: "X", value: Math.abs(frame.machine.vx), max: VX, color: "#17365d"}, {label: "Z", value: Math.abs(frame.machine.vz), max: VZ, color: "#4a6fa5"}];
      bars.forEach((bar, index) => {
        const y = top + 8 + index * Math.max(16, (bottom - top) / 2);
        g.fillStyle = "#66717a"; g.font = "9px Consolas"; g.fillText(bar.label, 4, y + 3);
        g.fillStyle = "#e5e9ec"; g.fillRect(left, y - 5, right - left, 8);
        g.fillStyle = bar.color; g.fillRect(left, y - 5, (right - left) * clamp(bar.value / bar.max, 0, 1), 8);
        g.fillStyle = "#26343e"; g.textAlign = "right"; g.fillText(`${bar.value.toFixed(2)} m/s`, right, y + 3); g.textAlign = "left";
      });
    }

    function drawSlotMap(frame) {
      const surface = canvasContext("slotMap"); if (!surface) return;
      const {context: g, width, height} = surface, size = Math.min(width - 24, height - 12), cell = size / 20, x0 = (width - size) / 2, y0 = (height - size) / 2;
      g.fillStyle = "#e9edef"; g.fillRect(x0, y0, size, size);
      for (let col = 0; col < 20; col += 1) for (let tier = 0; tier < 20; tier += 1) {
        const x = x0 + col * cell, y = y0 + (19 - tier) * cell;
        if ((col + tier) % 3 === 0) {
          g.save(); g.beginPath(); g.rect(x + .5, y + .5, cell - 1, cell - 1); g.clip();
          g.fillStyle = "#87939c"; g.fillRect(x + .5, y + .5, cell - 1, cell - 1);
          g.strokeStyle = "#d6dde2"; g.lineWidth = Math.max(.65, cell * .12);
          const hatchStep = Math.max(2.8, cell * .48);
          for (let d = -cell; d < cell * 2; d += hatchStep) { g.beginPath(); g.moveTo(x + d, y + cell); g.lineTo(x + d + cell, y); g.stroke(); }
          g.restore();
        }
        g.strokeStyle = "#c8d0d6"; g.strokeRect(x, y, cell, cell);
      }
      frame.inventoryRows.forEach(row => {
        const item = good(row.gid), x = x0 + row.col * cell, y = y0 + (19 - row.tier) * cell;
        /* 2D 热力层:平面图无透视遮挡,可整格铺热度底 → 总览尺度也能一眼读出热度分布,
           正好补上 3D 在总览尺度失效(400 格时每格约 25px、单格标识必然消失)的短板。
           开热度时货物框缩小居中,让热度底露出足够宽的边;等级色不被牺牲。 */
        if (heat2DOn) {
          g.fillStyle = "#" + heatColor(freqRank.has(row.gid) ? freqRank.get(row.gid) : .5).getHexString();
          g.fillRect(x + .5, y + .5, cell - 1, cell - 1);
        }
        const bx = heat2DOn ? cell * .26 : cell * .12, bw = heat2DOn ? cell * .48 : cell * .76;
        const by = heat2DOn ? cell * .28 : cell * .15, bh = heat2DOn ? cell * .44 : cell * .70;
        g.fillStyle = gradeCssColor(item.grade);
        g.fillRect(x + bx, y + by, bw, bh);
        g.strokeStyle = "#ffffff"; g.lineWidth = Math.max(.65, cell * .07);
        g.strokeRect(x + bx, y + by, bw, bh);
        if (!heat2DOn) { g.fillStyle = "rgba(255,255,255,.38)"; g.fillRect(x + cell * .17, y + cell * .20, cell * .66, Math.max(1, cell * .10)); }
      });
      if (frame.targetSlot) {
        const x = x0 + frame.targetSlot[0] * cell, y = y0 + (19 - frame.targetSlot[1]) * cell;
        g.strokeStyle = "#e7b800"; g.lineWidth = Math.max(2, cell * .22); g.strokeRect(x + 1, y + 1, cell - 2, cell - 2);
      }
      if (frame.cargoGid !== null && frame.operationKey !== "SCAN_EXIT") {
        const col = clamp(frame.machine.x, 0, 19), tier = clamp(frame.machine.z, 0, 19);
        g.beginPath(); g.arc(x0 + (col + .5) * cell, y0 + (19 - tier + .5) * cell, Math.max(2.2, cell * .32), 0, Math.PI * 2);
        g.fillStyle = gradeCssColor(good(frame.cargoGid).grade); g.fill(); g.strokeStyle = "#e7b800"; g.lineWidth = Math.max(1.2, cell * .16); g.stroke();
      }
    }

    function projectAnchor(world) {
      const vector = world.clone().project(camera), mountRect = mount.getBoundingClientRect(), viewportRect = viewportEl.getBoundingClientRect();
      const visible = vector.z >= -1 && vector.z <= 1 && vector.x >= -1.03 && vector.x <= 1.03 && vector.y >= -1.03 && vector.y <= 1.03;
      if (!visible) return null;
      return {
        x: mountRect.left - viewportRect.left + (vector.x + 1) * mountRect.width / 2,
        y: mountRect.top - viewportRect.top + (1 - vector.y) * mountRect.height / 2,
        depth: vector.z, world: world.toArray()
      };
    }

    function projectWorldBox(box) {
      camera.updateMatrixWorld();
      const mountRect = mount.getBoundingClientRect();
      const corners = [];
      [box.min.x, box.max.x].forEach(x => [box.min.y, box.max.y].forEach(y => [box.min.z, box.max.z].forEach(z => {
        const ndc = new THREE.Vector3(x, y, z).project(camera);
        corners.push({
          x: (ndc.x + 1) * mountRect.width / 2,
          y: (1 - ndc.y) * mountRect.height / 2,
          z: ndc.z
        });
      })));
      const xs = corners.map(point => point.x), ys = corners.map(point => point.y);
      const left = Math.min(...xs), right = Math.max(...xs), top = Math.min(...ys), bottom = Math.max(...ys);
      const width = right - left, height = bottom - top;
      const depthVisible = corners.every(point => point.z >= -1 && point.z <= 1);
      const inside = depthVisible && left >= 0 && top >= 0 && right <= mountRect.width && bottom <= mountRect.height;
      return {
        left, top, right, bottom, width, height, inside, depthVisible,
        widthRatio: width / mountRect.width, heightRatio: height / mountRect.height,
        clearance: {
          left: left / mountRect.width, right: (mountRect.width - right) / mountRect.width,
          top: top / mountRect.height, bottom: (mountRect.height - bottom) / mountRect.height
        }
      };
    }

    function unionScreenProjections(projections) {
      invariant(Array.isArray(projections) && projections.length > 0, "屏幕投影并集不能为空");
      const mountRect = mount.getBoundingClientRect();
      const left = Math.min(...projections.map(item => item.left));
      const right = Math.max(...projections.map(item => item.right));
      const top = Math.min(...projections.map(item => item.top));
      const bottom = Math.max(...projections.map(item => item.bottom));
      return {
        left, top, right, bottom, width: right - left, height: bottom - top,
        inside: projections.every(item => item.inside),
        depthVisible: projections.every(item => item.depthVisible),
        widthRatio: (right - left) / mountRect.width,
        heightRatio: (bottom - top) / mountRect.height,
        clearance: {
          left: left / mountRect.width,
          right: (mountRect.width - right) / mountRect.width,
          top: top / mountRect.height,
          bottom: (mountRect.height - bottom) / mountRect.height
        }
      };
    }

    function compositionSnapshot() {
      const rack = new THREE.Box3(
        new THREE.Vector3(-.35, -.30, Z0),
        new THREE.Vector3(N + .35, 1.10, N + .20)
      );
      const stationMinX = Math.min(INFEED.entryX, INFEED.loadX, OUTFEED.startX, OUTFEED.endX, IO.x) - .16;
      const stationMaxX = Math.max(INFEED.entryX, INFEED.loadX, OUTFEED.startX, OUTFEED.endX, IO.x) + .16;
      const stationMinY = Math.min(INFEED.y - .76, OUTFEED.y - .76, IO.y - .76);
      const stationMaxY = Math.max(INFEED.y + .76, OUTFEED.y + .76, IO.y + .76);
      const stations = new THREE.Box3(
        new THREE.Vector3(stationMinX, stationMinY, Z0),
        new THREE.Vector3(stationMaxX, stationMaxY, 1.68)
      );
      const maximumQueueEnvelope = new THREE.Box3(
        new THREE.Vector3(INFEED.entryX - 3.38, INFEED.y - .48, Z0),
        new THREE.Vector3(INFEED.entryX - .38, INFEED.y + .48, 1.06)
      );
      const rackProjection = projectWorldBox(rack);
      const stationProjection = projectWorldBox(stations);
      const fixedSubject = unionScreenProjections([rackProjection, stationProjection]);
      const visibleQueueProjections = queuePool.filter(item => item.unit.visible).map(item => {
        item.unit.updateWorldMatrix(true, true);
        return projectWorldBox(new THREE.Box3().setFromObject(item.unit));
      });
      /* 验收只统计当前真实可见对象。潜在 4 箱队列不能在空队列截图中虚增主体宽度；
         它作为满载压力边界单列，供极端状态检查。 */
      const visibleSubject = unionScreenProjections([rackProjection, stationProjection, ...visibleQueueProjections]);
      const maxQueuePressureProjection = projectWorldBox(maximumQueueEnvelope);
      const maxPressureSubject = unionScreenProjections([rackProjection, stationProjection, maxQueuePressureProjection]);
      return {
        mount: {width: mount.getBoundingClientRect().width, height: mount.getBoundingClientRect().height},
        rack: rackProjection, stations: stationProjection,
        fixedSubject, visibleSubject, subject: visibleSubject,
        visibleQueue: visibleQueueProjections, queueVisibleCount: visibleQueueProjections.length,
        maxQueuePressure: {queue: maxQueuePressureProjection, subject: maxPressureSubject},
        entities: {fixed: 2, visibleQueue: visibleQueueProjections.length},
        /* 底部证据坞拥有独立高度后，三维主体在剩余 WebGL 区内以 65%~85% 宽度最清晰。 */
        gate: {targetWidthRatio: [.65, .85], targetTopClearance: [.04, .12]}
      };
    }

    function localRect(element, viewportRect) {
      const rect = element.getBoundingClientRect();
      return {left: rect.left - viewportRect.left, top: rect.top - viewportRect.top, right: rect.right - viewportRect.left, bottom: rect.bottom - viewportRect.top, width: rect.width, height: rect.height};
    }

    function inflateScreenRect(rect, padding = 8) {
      return {left: rect.left - padding, top: rect.top - padding, right: rect.right + padding,
        bottom: rect.bottom + padding, width: rect.width + padding * 2, height: rect.height + padding * 2};
    }

    function hideLeader(id) {
      const line = byId(id);
      if (line) { line.hidden = true; line.style.display = "none"; }
    }

    function routePlacedLeaders(definitions, placements, fixedObstacles) {
      const options = placements.map(placement => {
        const item = definitions.find(candidate => candidate.id === placement.id);
        const peerRects = placements.filter(candidate => candidate.id !== placement.id).map(candidate => inflateScreenRect(candidate.rect, 3));
        return {item, placement, routes: leaderRouteCandidates(item.anchor, placement.rect, fixedObstacles.concat(peerRects))};
      });
      let routes = [];
      if (options.length === 1) routes = [Object.assign({id: options[0].item.id, lineId: options[0].item.lineId}, options[0].routes[0])];
      else {
        let best = null;
        options[0].routes.forEach(first => options[1].routes.forEach(second => {
          const crossings = routeCrossings(first, second);
          const score = first.score + second.score + crossings * 5e6;
          if (!best || score < best.score) best = {score, crossings, first, second};
        }));
        routes = [
          Object.assign({id: options[0].item.id, lineId: options[0].item.lineId}, best.first, {crossings: best.crossings}),
          Object.assign({id: options[1].item.id, lineId: options[1].item.lineId}, best.second, {crossings: 0})
        ];
      }
      routes.forEach(route => {
        const item = definitions.find(candidate => candidate.id === route.id);
        const line = byId(item.lineId);
        line.setAttribute("points", route.points.map(point => `${point.x.toFixed(2)},${point.y.toFixed(2)}`).join(" "));
        line.hidden = false; line.style.display = "";
      });
      return {
        leaders: routes.map(route => ({id: route.id, lineId: route.lineId, points: route.points.map(point => ({x: point.x, y: point.y})),
          length: route.length, obstacleHits: route.obstacleHits, crossings: route.crossings})),
        leaderObstacleHits: routes.reduce((sum, route) => sum + route.obstacleHits, 0),
        leaderCrossings: routes.reduce((sum, route) => sum + route.crossings, 0),
        maxLeaderLength: routes.reduce((maximum, route) => Math.max(maximum, route.length), 0)
      };
    }

    /* 固定入/出库说明已经并入底坞，场景不再漂浮四个说明框。保留空审计对象，
       让全帧 QA 能明确证明“静态工位标签为 0”，而不是跳过该项。 */
    function layoutStationTags() {
      lastStationLayout = {visible: 0, overlapArea: 0, pairOverlapArea: 0, fixedOverlapArea: 0, outOfBounds: false,
        leaderObstacleHits: 0, leaderCrossings: 0, maxLeaderLength: 0, leaders: [], labels: []};
    }

    function layoutProjectedLabels(frame) {
      /* 0718 #28 黄牌(targetBeacon)废止:01 已退役,02 跟进。beacon 不再投影/防重叠,也不再显示;
         目标信息交给下方 dock 与 3D 目标格高亮承担。以下原投影实现整体短路,保留供回滚与契约留痕。 */
      const retiredBeacon = byId("targetBeacon");
      if (retiredBeacon) { retiredBeacon.hidden = true; retiredBeacon.style.display = "none"; }
      hideLeader("targetLeader");
      lastOverlayLayout = {visible: 0, overlapArea: 0, outOfBounds: false,
        leaderObstacleHits: 0, leaderCrossings: 0, maxLeaderLength: 0, leaders: [], labels: []};
      return;
      /* eslint-disable */
      const viewportRect = viewportEl.getBoundingClientRect(), mountRect = mount.getBoundingClientRect();
      const targetElement = byId("targetBeacon");
      const definitions = [];
      if (frame.targetSlot) {
        const anchor = projectAnchor(new THREE.Vector3(frame.targetSlot[0] + .5, RACK.frontY - .035, frame.targetSlot[1] + .65));
        if (anchor) definitions.push({id: "targetBeacon", role: "target", element: targetElement, lineId: "targetLeader", anchor});
      }
      const targetActive = definitions.some(item => item.element === targetElement);
      targetElement.hidden = !targetActive;
      if (!targetActive) hideLeader("targetLeader");
      if (!definitions.length) { lastOverlayLayout = {visible: 0, overlapArea: 0, outOfBounds: false,
        leaderObstacleHits: 0, leaderCrossings: 0, maxLeaderLength: 0, leaders: [], labels: []}; return; }

      definitions.forEach(item => { item.element.hidden = false; item.element.style.visibility = "hidden"; item.element.style.left = "0px"; item.element.style.top = "0px"; });
      definitions.forEach(item => { const rect = item.element.getBoundingClientRect(); item.width = rect.width; item.height = rect.height; });
      const margin = 10, bounds = {
        left: mountRect.left - viewportRect.left + margin, top: mountRect.top - viewportRect.top + margin,
        right: mountRect.right - viewportRect.left - margin, bottom: mountRect.bottom - viewportRect.top - margin
      };
      const fixedObstacles = ["sceneDock", "faultStateBanner"]
        .map(byId).filter(element => element && !element.hidden).map(element => inflateScreenRect(localRect(element, viewportRect)));
      const anchorObstacles = definitions.map(item => ({left: item.anchor.x - 18, top: item.anchor.y - 18,
        right: item.anchor.x + 18, bottom: item.anchor.y + 18, anchorZone: true}));
      const obstacles = fixedObstacles.concat(anchorObstacles);
      const result = chooseLabelPairLayout(definitions, bounds, obstacles);
      result.placements.forEach(placement => {
        const item = definitions.find(candidate => candidate.id === placement.id), rect = placement.rect;
        item.element.style.left = `${rect.left}px`; item.element.style.top = `${rect.top}px`; item.element.style.visibility = "";
      });
      const leaderSummary = routePlacedLeaders(definitions, result.placements, fixedObstacles);
      const outOfBounds = result.placements.some(({rect}) => rect.left < bounds.left - EPS || rect.top < bounds.top - EPS || rect.right > bounds.right + EPS || rect.bottom > bounds.bottom + EPS);
      /* anchorObstacles 只用于偏好评分，代表三维锚点周围的视觉呼吸区，不是 DOM 遮挡；
         验收 overlapArea 只统计真正互相覆盖的标签与固定 HUD。 */
      const obstacleOverlapArea = result.placements.reduce((sum, placement) =>
        sum + fixedObstacles.reduce((subtotal, obstacle) => subtotal + rectIntersectionArea(placement.rect, obstacle), 0), 0);
      const rawOverlayOverlapArea = result.overlapArea + obstacleOverlapArea;
      lastOverlayLayout = {visible: result.placements.length,
        overlapArea: rawOverlayOverlapArea <= SCREEN_AREA_EPS ? 0 : rawOverlayOverlapArea,
        pairOverlapArea: result.overlapArea, obstacleOverlapArea, outOfBounds, ...leaderSummary,
        labels: result.placements.map(item => ({id: item.id, left: item.rect.left, top: item.rect.top, right: item.rect.right, bottom: item.rect.bottom, anchor: Object.assign({}, item.anchor)}))};
    }

    function updateText(trace, frame) {
      const cargoGood = frame.cargoGid === null ? null : good(frame.cargoGid), event = frame.event;
      const queueActive = frame.phaseName === "QUEUE", visibleStepLabel = queueActive ? QUEUE_LABEL : STEP_LABEL[frame.operationKey];
      byId("taskPrimary").textContent = `C${String(frame.cycleNumber).padStart(3, "0")} · ${good(event.inbound_gid).name} 入 ${String(event.store_slot.col).padStart(2, "0")}/${String(event.store_slot.tier).padStart(2, "0")} · ${good(event.outbound_gid).name} 出 ${String(event.retrieve_slot.col).padStart(2, "0")}/${String(event.retrieve_slot.tier).padStart(2, "0")}`;
      const action = byId("actionBadge"); action.textContent = frame.faulted ? "故障恢复" : visibleStepLabel;
      action.style.backgroundColor = frame.faulted ? "#b71c1c" : ["INBOUND_TRAVEL", "LINK_TRAVEL", "OUTBOUND_TRAVEL"].includes(frame.operationKey) ? "#17365d" : "#e7b800";
      action.style.color = frame.faulted || ["INBOUND_TRAVEL", "LINK_TRAVEL", "OUTBOUND_TRAVEL"].includes(frame.operationKey) ? "#fff" : "#17202b";
      byId("stepIndex").textContent = `${frame.faulted ? "故障 · " : ""}步骤 ${STEP_INDEX[frame.operationKey] + 1} / 7`;
      byId("stepPurposeText").textContent = queueActive ? QUEUE_PURPOSE : STEP_PURPOSE[frame.operationKey];
      byId("ownerState").textContent = cargoGood ? `货物：${cargoGood.name} · ${OWNER_LABEL[frame.cargoOwner] || frame.cargoOwner}` : "货物：空载台";
      byId("phaseNow").textContent = `${frame.faulted ? "故障 · " : ""}步骤 ${STEP_INDEX[frame.operationKey] + 1} · ${visibleStepLabel}`;
      const totalCycleSim = frame.cycleTiming.reduce((sum, item) => sum + item.simDurationS, 0);
      byId("phaseClock").textContent = `SIM ${totalCycleSim.toFixed(1)} s · 1=排队/交接`;
      /* 0719 功能批次:railFacts 三格删——周期计数直写轴行;等待/故障与统计块重复。queueCard 事件浮现:等待>0 才显示。 */
      byId("cycleAxisCount").textContent = `${frame.cycleNumber} / ${trace.meta.cycles}`;
      byId("queueCard").hidden = frame.queueGids.length === 0;
      const faultBanner = byId("faultStateBanner"); faultBanner.hidden = !frame.faulted;
      if (frame.faulted) faultBanner.querySelector("span").textContent = `故障 ${String((frame.faultIndex ?? 0) + 1).padStart(2, "0")} · ${visibleStepLabel} 保持位`;
      byId("xValue").textContent = `${frame.machine.x.toFixed(2)} m`; byId("zValue").textContent = `${frame.machine.z.toFixed(2)} m`; byId("forkValue").textContent = `${forkExtension.toFixed(2)} m`;
      byId("xFill").style.setProperty("--fill", `${frame.machine.x / 19 * 100}%`); byId("zFill").style.setProperty("--fill", `${frame.machine.z / 19 * 100}%`); byId("forkFill").style.setProperty("--fill", `${forkExtension / FORK_MAX * 100}%`);
      byId("queueMeta").textContent = `${frame.queueGids.length} 等待`;
      const judgeAction = byId("judgeAction"), judgeActionMeta = byId("judgeActionMeta");
      if (judgeAction) judgeAction.textContent = `STEP ${STEP_INDEX[frame.operationKey] + 1} · ${visibleStepLabel}`;
      if (judgeActionMeta) {
        const owner = cargoGood ? (OWNER_LABEL[frame.cargoOwner] || frame.cargoOwner) : "空载台";
        judgeActionMeta.textContent = cargoGood ? `${cargoGood.name} · ${owner}` : `${owner} · ${STEP_PURPOSE[frame.operationKey]}`;
      }
      const phases = Array.from(byId("phaseSegments").querySelectorAll(".phaseSeg"));
      phases.forEach((element, index) => {
        const item = frame.cycleTiming[index], active = index === STEP_INDEX[frame.operationKey];
        element.classList.toggle("active", active);
        const firstHasQueue = item.operationKey === "LOAD_IN" && item.simDurationS > EPS;
        element.querySelector(".phaseName").textContent = firstHasQueue ? "排队" : STEP_SHORT_LABEL[item.operationKey];
        element.querySelector(".phaseDuration").textContent = item.simDurationS > EPS ? `${item.simDurationS.toFixed(1)}s` : "展示";
        element.title = item.operationKey === "LOAD_IN" ? (firstHasQueue ?
          `1. 入场前排队 · SIM ${item.simDurationS.toFixed(1)} s；随后入口交接为展示补段，不计 SIM/KPI` :
          "1. 入口交接 · 展示补段，不计 SIM/KPI") :
          `${index + 1}. ${STEP_LABEL[item.operationKey]} · ${item.simDurationS > EPS ? `SIM ${item.simDurationS.toFixed(1)} s` : "展示补段，不计 SIM/KPI"}`;
      });
      const scaleParts = Array.from(byId("phaseTimeScale").querySelectorAll(".phaseTimePart"));
      let completedSim = 0;
      scaleParts.forEach((element, index) => {
        const item = frame.cycleTiming[index], ratio = totalCycleSim > EPS ? item.simDurationS / totalCycleSim : 0;
        element.style.width = `${ratio * 100}%`; element.classList.toggle("active", index === STEP_INDEX[frame.operationKey]);
        element.classList.toggle("presentationOnly", item.simDurationS <= EPS);
        if (index < STEP_INDEX[frame.operationKey]) completedSim += item.simDurationS;
      });
      const currentSim = frame.cycleTiming[STEP_INDEX[frame.operationKey]].simDurationS;
      byId("phaseTimeCursor").style.left = `${totalCycleSim > EPS ? (completedSim + currentSim * frame.operationProgress) / totalCycleSim * 100 : 0}%`;
      const ownerText = cargoGood ? (OWNER_LABEL[frame.cargoOwner] || frame.cargoOwner) : "空载台";
      const cargoSummary = cargoGood ? `${cargoGood.name} · ${cargoGood.weight_kg.toFixed(1)} kg · ${GRADE_LABEL[cargoGood.grade] || cargoGood.grade}` : "空载联程";
      const timing = frame.timing || {simDurationS: 0, presentationDurationS: 0};
      const wallSeconds = timing.presentationDurationS / DEFAULT_PLAYBACK_SCALE;
      const timingText = frame.operationKey === "LOAD_IN" ? (timing.simDurationS > EPS ?
        `排队 SIM ${timing.simDurationS.toFixed(1)} s · 交接为展示补段 · 1×共 ${wallSeconds.toFixed(1)} s` :
        `无排队 · 交接展示 ${wallSeconds.toFixed(1)} s · 不计 KPI`) : timing.simDurationS > EPS ?
        `SIM ${timing.simDurationS.toFixed(1)} s → 1×演示 ${wallSeconds.toFixed(1)} s` :
        `1×展示补段 ${wallSeconds.toFixed(1)} s · 不计 KPI`;
      byId("sceneActionText").textContent = `${visibleStepLabel} · ${cargoGood ? `${cargoGood.name} · ${ownerText}` : ownerText}`;
      byId("sceneCargoMeta").textContent = `${cargoSummary} · ${timingText}`;
      byId("sceneActionMeta").textContent = `${frame.faulted ? "故障保持" : `步骤 ${STEP_INDEX[frame.operationKey] + 1}/7`} · 缩时演示 · SIM`;
      byId("sceneCaption").setAttribute("aria-label", `当前动作：${byId("sceneActionText").textContent}`);
    }

    function setTrace(trace) {
      currentTrace = trace; catalog = new Map(trace.cargo_catalog.map(item => [item.gid, item])); stockSignature = "";
      invariant(catalog.size === trace.cargo_catalog.length, "cargo_catalog 重复 gid");
      /* #26-2:热门集合随 trace 重算(45 条 trace 各 catalog 不同);freq_true 用真值不用带噪 freq_est。
         同行 stockSignature="" 会触发下帧 rebuildStockInstances() 重画,金顶随之生效,无需额外失效。 */
      const order = trace.cargo_catalog.map((item, index) => ({gid: item.gid, freq: item.freq_true, index}));
      order.sort((a, b) => b.freq - a.freq || a.index - b.index);
      hotGids = new Set(order.slice(0, Math.max(1, Math.floor(order.length / 5))).map(e => e.gid));
      /* #26-2 A层色阶归一化:用 freq_true 的秩(rank)映射,冷→热连续铺满,规避 skew 分布下线性 min-max 全挤冷端;
         order 已按 freq 降序,index 0=最热→t=1,末位=最冷→t=0。B层近 I/O 热区随之重算。 */
      const denom = order.length > 1 ? order.length - 1 : 1;
      freqRank = new Map(order.map((e, index) => [e.gid, order.length > 1 ? 1 - index / denom : .5]));
      updateHotZone(trace);
      trace.events.forEach(event => { good(event.inbound_gid); good(event.outbound_gid); });
      pathSignature = ""; clearPaths(); renderDecision(trace); renderTraceStats(trace);
      byId("taskline").querySelector(".kicker").textContent = "已校验 · 同源 SIM 轨迹";
      byId("railHead").querySelector(".matrix").innerHTML = `20 × 20<br>SIM / T${trace.meta.tier}`;
      const phaseSegments = byId("phaseSegments"), phaseTimeScale = byId("phaseTimeScale");
      phaseSegments.replaceChildren(); phaseTimeScale.replaceChildren();
      PROCESS_STEPS.forEach((name, index) => {
        const segment = doc.createElement("span"), phaseName = doc.createElement("span"), duration = doc.createElement("small");
        segment.className = "phaseSeg"; segment.append(doc.createTextNode(String(index + 1)));
        phaseName.className = "phaseName"; phaseName.textContent = STEP_SHORT_LABEL[name]; duration.className = "phaseDuration"; duration.textContent = "--";
        segment.append(phaseName, duration); segment.title = `${index + 1}. ${STEP_LABEL[name]}`;
        segment.setAttribute("aria-label", `${index + 1}. ${STEP_LABEL[name]}`); phaseSegments.append(segment);
        const timePart = doc.createElement("span"); timePart.className = `phaseTimePart phaseTone${index + 1}`;
        timePart.setAttribute("aria-hidden", "true"); phaseTimeScale.append(timePart);
      });
      const cursor = doc.createElement("i"); cursor.id = "phaseTimeCursor"; cursor.setAttribute("aria-hidden", "true"); phaseTimeScale.append(cursor);
    }

    function renderFrame(trace, frame) {
      if (currentTrace !== trace) setTrace(trace);
      lastFrame = frame;
      setInventory(frame.inventoryRows);
      setQueue(frame.queueGids); setPaths(trace, frame.event); updatePathEmphasis(frame.operationKey);
      const machineWorld = setMachine(frame); setCargo(frame, machineWorld); setTarget(frame);
      updateText(trace, frame); drawSpeed(frame); drawSlotMap(frame);
      const loopMask = byId("cycleReset"), maskVisible = frame.loop > 0 && frame.elapsedLocal < LOOP_RESET_MASK_S;
      loopMask.classList.toggle("is-visible", maskVisible); loopMask.setAttribute("aria-hidden", String(!maskVisible));
      /* #28 目标格发光壳呼吸 + 箭头竖直浮动:相位取演示时钟 frame.simTime(seek 后固定,截图可复现)。
         入库=金色呼吸/完成收敛;出库=淡出转灰(整体乘 fade,随取货推进衰减)。 */
      if (targetFx && targetFx.glow.visible) {
        const pulse = (Math.sin(frame.simTime * 2.4) + 1) / 2, live = targetFx.arrow.visible;
        const ud = targetFx.glow.userData, fade = ud.fade == null ? 1 : ud.fade;
        if (ud.mode === "outbound") {
          targetFx.glowMat.opacity = (live ? .28 + .18 * pulse : .30) * fade;
          targetFx.faceMat.opacity = (live ? .66 + .22 * pulse : .55) * fade;
        } else {
          targetFx.glowMat.opacity = live ? .30 + .22 * pulse : .48;
          targetFx.faceMat.opacity = live ? .72 + .26 * pulse : .95;
        }
        if (live) targetFx.arrow.position.z = targetFx.arrow.userData.baseZ - targetFx.floatAmp * pulse;
      }
      renderer.render(scene, camera);
      layoutStationTags(frame);
      layoutProjectedLabels(frame);
    }

    function refreshProjection() {
      /* 镜头拖动不改变业务帧，但会改变所有世界坐标的屏幕投影。
         事件驱动重绘避免在暂停或后台 RAF 降频时留下失配的标签与引线。 */
      if (!lastFrame) return;
      renderer.render(scene, camera);
      layoutStationTags(lastFrame);
      layoutProjectedLabels(lastFrame);
    }

    function collisionSnapshot(includeBoxes = false) {
      const actors = [];
      if (cargo.visible) actors.push({label: `ACTIVE_${cargo.userData.gid || "UNKNOWN"}`, object: cargo});
      queuePool.forEach((item, index) => {
        if (item.unit.visible) actors.push({label: `QUEUE_${item.unit.userData.gid || index}`, object: item.unit});
      });
      const boxedActors = actors.map(actor => {
        actor.object.updateWorldMatrix(true, true);
        return {label: actor.label, box: new THREE.Box3().setFromObject(actor.object)};
      });
      const boxedSolids = stationCollisionSolids.map(object => {
        object.updateWorldMatrix(true, false);
        return {label: object.userData.collisionLabel || object.name || "STATION_SOLID", box: new THREE.Box3().setFromObject(object)};
      });
      const collisions = [], floorBreaches = [];
      const overlap = (a, b) => ({
        x: Math.min(a.max.x, b.max.x) - Math.max(a.min.x, b.min.x),
        y: Math.min(a.max.y, b.max.y) - Math.max(a.min.y, b.min.y),
        z: Math.min(a.max.z, b.max.z) - Math.max(a.min.z, b.min.z)
      });
      const gap = (a, b) => Math.hypot(
        Math.max(b.min.x - a.max.x, a.min.x - b.max.x, 0),
        Math.max(b.min.y - a.max.y, a.min.y - b.max.y, 0),
        Math.max(b.min.z - a.max.z, a.min.z - b.max.z, 0)
      );
      let minClearance = Number.POSITIVE_INFINITY;
      boxedActors.forEach(actor => {
        boxedSolids.forEach(solid => {
          const penetration = overlap(actor.box, solid.box), clearance = gap(actor.box, solid.box);
          minClearance = Math.min(minClearance, clearance);
          if (penetration.x > EPS && penetration.y > EPS && penetration.z > EPS) {
            collisions.push({a: actor.label, b: solid.label, penetration});
          }
        });
        if (actor.box.min.x < FLOOR.x0 - EPS || actor.box.max.x > FLOOR.x1 + EPS ||
            actor.box.min.y < FLOOR.y0 - EPS || actor.box.max.y > FLOOR.y1 + EPS || actor.box.min.z < Z0 - EPS) {
          floorBreaches.push({actor: actor.label, min: actor.box.min.toArray(), max: actor.box.max.toArray()});
        }
      });
      for (let i = 0; i < boxedActors.length; i += 1) for (let j = i + 1; j < boxedActors.length; j += 1) {
        const penetration = overlap(boxedActors[i].box, boxedActors[j].box);
        if (penetration.x > EPS && penetration.y > EPS && penetration.z > EPS) {
          collisions.push({a: boxedActors[i].label, b: boxedActors[j].label, penetration});
        }
      }
      const result = {scope: "active_queue_cargo_vs_station_solids_each_other_and_floor", actorCount: boxedActors.length, stationSolidCount: boxedSolids.length,
        minClearance: Number.isFinite(minClearance) ? minClearance : null, collisions, floorBreaches};
      if (includeBoxes) result.geometry = {
        actors: boxedActors.map(item => ({label: item.label, min: item.box.min.toArray(), max: item.box.max.toArray()})),
        solids: boxedSolids.map(item => ({label: item.label, min: item.box.min.toArray(), max: item.box.max.toArray()}))
      };
      return result;
    }

    function metrics() {
      let sceneMeshes = 0; scene.traverse(object => { if (object.isMesh || object.isInstancedMesh) sceneMeshes += 1; });
      return {
        inventorySize: inventory.size, inventoryGids: Array.from(inventory.keys()).sort((a, b) => a - b),
        stockPool: stockPool.length, queuePool: queuePool.length, queueVisibleGids: lastQueueGids.slice(), pathCount: livePaths.length, sceneMeshes,
        stockVisual: {source: "event_inventory_snapshot", gradeCounts: Object.assign({}, lastStockGradeCounts), lidCount: stockLidMesh.count, solidGreenShell: false},
        pathPlan: livePaths.map(path => ({operationKey: path.operationKey, kind: path.kind, opacity: path.material.opacity,
          start: Object.assign({}, path.auditPoints[0]), end: Object.assign({}, path.auditPoints[path.auditPoints.length - 1])})),
        operationKey: lastFrame && lastFrame.operationKey, phaseName: lastFrame && lastFrame.phaseName,
        faulted: Boolean(lastFrame && lastFrame.faulted), faultIndex: lastFrame && lastFrame.faultIndex,
        cargoOwner: lastFrame && lastFrame.cargoOwner,
        timing: lastFrame && lastFrame.timing ? Object.assign({}, lastFrame.timing) : null,
        loop: lastFrame && lastFrame.loop, loopResetMask: byId("cycleReset").classList.contains("is-visible"),
        mastX: mast.position.x, carrierX: carrier.position.x, carrierZ: carrier.position.z,
        forkExtension, forkY: forkGroup.position.y, forkDrop,
        cargo: {
          visible: cargo.visible, gid: cargo.visible ? cargo.userData.gid : null,
          owner: cargo.userData.owner || null, operationKey: cargo.userData.operationKey || null,
          parent: cargo.parent === scene ? "scene" : cargo.parent === carrier ? "carrier" : "other",
          x: cargo.position.x, y: cargo.position.y, z: cargo.position.z, opacity: cargo.material.opacity
        },
        transfer: {x: TRANSFER_ANCHOR.x, y: TRANSFER_ANCHOR.y, z: TRANSFER_ANCHOR.z},
        infeed: {y: INFEED.y, entryX: INFEED.entryX, loadX: INFEED.loadX, z: INFEED.z},
        outfeed: {y: OUTFEED.y, startX: OUTFEED.startX, scanX: OUTFEED.scanX, maskX: OUTFEED.maskX, endX: OUTFEED.endX, z: OUTFEED.z},
        topology: topologyAudit, labels: lastOverlayLayout, stationLabels: lastStationLayout, collisions: collisionSnapshot(), composition: compositionSnapshot(),
        ownership: lastFrame ? ownershipSnapshot(lastFrame) : null,
        camera: cameraSnapshot()
      };
    }

    function dispose() {
      clearPaths();
      Array.from(inventory.values()).forEach(stockRemove); inventory.clear();
      scene.remove(stockGroup); scene.remove(queueGroup); cargo.visible = false;
      stockBodyGeometry.dispose(); stockLidGeometry.dispose();
      queueBaseGeometry.dispose(); queueBoxGeometry.dispose(); queueEdgeGeometry.dispose(); queueEdgeMaterial.dispose();
      Object.values(activeMaterial).forEach(material => material.dispose());
      queuePool.forEach(item => queueGroup.remove(item.unit));
    }

    return {renderFrame, refreshProjection, collisionSnapshot, compositionSnapshot, metrics, dispose};
  }

  function createRuntimeDom(root) {
    const doc = root.document, rail = doc.getElementById("workHud");
    const decision = doc.createElement("section"); decision.id = "decisionWrap"; decision.innerHTML = '<div class="dHead"><b>等待算法轨迹</b><span>仅 SIM</span></div>';
    const queue = doc.createElement("section"); queue.id = "queueCard";
    queue.innerHTML = '<div class="qHead"><b>入口等待队列 · 同一 gid</b><span id="queueMeta">-- 等待</span></div><div id="queueStrip"><em>正在加载</em></div>';
    const insight = doc.getElementById("insightStack");
    invariant(insight, "Task10 insightStack 缺失");
    const comparisonMini = doc.createElement("section"); comparisonMini.id = "comparisonMini";
    comparisonMini.innerHTML = '<div class="comparisonMiniHead"><div><b>S1 受控对照 · 当前 4 / 完整 8</b><span>10 seeds · SIM<br>其余路由见完整对照</span></div><button id="openComparisonLabMini" type="button" aria-label="查看 S1 完整八种算法链受控对照">查看完整对照</button></div><div id="comparisonMiniBars"><em>正在校验证据</em></div>';
    const judgePath = doc.createElement("section"); judgePath.id = "judgePath"; judgePath.setAttribute("aria-label", "当前画面同源证据链");
    judgePath.innerHTML = '<div class="judgePathHead"><b>本屏证据链</b><span>同一轨迹</span></div><div class="judgePathSteps"><div class="judgeStep" data-step="01" data-tone="route"><b id="judgeRoute">等待策略</b><span id="judgeRouteMeta">轨迹加载中</span></div><div class="judgeStep" data-step="02" data-tone="motion"><b id="judgeAction">等待动作</b><span id="judgeActionMeta">轨迹加载中</span></div><div class="judgeStep" data-step="03" data-tone="proof"><b id="judgeEvidence">等待验收</b><span id="judgeEvidenceMeta">轨迹加载中</span></div></div>';
    const actionHost = doc.getElementById("runtimeActions"), traceState = doc.getElementById("traceLoadState");
    const compareButton = doc.createElement("button"); compareButton.id = "openComparisonLab"; compareButton.type = "button"; compareButton.textContent = "对照证据";
    actionHost.insertBefore(compareButton, traceState);
    const comparisonLab = doc.createElement("section"); comparisonLab.id = "comparisonLab"; comparisonLab.hidden = true;
    comparisonLab.setAttribute("role", "dialog"); comparisonLab.setAttribute("aria-modal", "true"); comparisonLab.setAttribute("aria-labelledby", "comparisonTitle"); comparisonLab.setAttribute("aria-describedby", "comparisonFoot");
    comparisonLab.innerHTML = '<div class="comparisonPanel"><header><div><span>S1 受控对照 · SIM</span><h2 id="comparisonTitle">算法与货物情景对照</h2></div><button id="closeComparisonLab" type="button" aria-label="关闭对照证据">×</button></header><div class="comparisonTabs" role="tablist" aria-label="对照方向"><button id="comparisonScenarioTab" type="button" role="tab" aria-selected="true" aria-controls="comparisonTable" tabindex="0">同情景 · 八模式</button><button id="comparisonModeTab" type="button" role="tab" aria-selected="false" aria-controls="comparisonTable" tabindex="-1">同算法 · 十八情景</button></div><div id="comparisonToolbar"></div><div id="comparisonAutoSummary"></div><div id="comparisonTable" role="region" aria-live="polite" aria-label="S1 对照数据" tabindex="0"></div><footer id="comparisonFoot"></footer></div>';
    /* 0719 左栏信息架构重排(依据 ISA-101.01-2015 四级信息分层,见 docs/左栏信息架构研究与合流方案_0718.md):
       L1 常驻左栏 = 等待队列 / 本批统计 / 当前相位 / 2D 货位图;
       「S1 受控对照」与「本屏证据链」属 L2-L3,降级为顶栏 chip → 叠层按需展开。
       实测左栏内容 914px > 可用 850px(insightStack 独占 537px),此举腾出约 300px 给 2D 货位图放大
       (每格 6.6px → 约 14px,逐格色阶方可读)。**内容一条不删,只改可达路径。** */
    const evidenceDock = doc.createElement("section"); evidenceDock.id = "evidenceDock"; evidenceDock.hidden = true;
    evidenceDock.setAttribute("role", "dialog"); evidenceDock.setAttribute("aria-modal", "true");
    evidenceDock.setAttribute("aria-labelledby", "evidenceDockTitle");
    const evidencePanel = doc.createElement("div"); evidencePanel.className = "evidencePanel";
    const evidenceHead = doc.createElement("header");
    evidenceHead.innerHTML = '<div><span>同一轨迹 · SIM</span><h2 id="evidenceDockTitle">本屏证据链 · S1 受控对照</h2></div><button id="closeEvidenceDock" type="button" aria-label="关闭本屏证据">×</button>';
    evidencePanel.append(evidenceHead, judgePath, comparisonMini);
    evidenceDock.append(evidencePanel);
    const evidenceButton = doc.createElement("button"); evidenceButton.id = "openEvidenceDock"; evidenceButton.type = "button";
    evidenceButton.textContent = "本屏证据"; evidenceButton.setAttribute("aria-haspopup", "dialog");
    actionHost.insertBefore(evidenceButton, compareButton);
    rail.append(decision, comparisonLab, evidenceDock); insight.prepend(queue);
  }

  function bootstrap(root) {
    invariant(root && root.document && root.S3TraceStore && root.S3_TRACE_MANIFEST, "S3 trace store / manifest 未加载");
    createRuntimeDom(root);
    const doc = root.document, byId = id => doc.getElementById(id), rendererBridge = createBrowserRenderer(root);
    const state = {
      trace: null, timeline: null, elapsed: 0, lastNow: null,
      paused: false, loading: false, playbackMultiplier: 1, playbackScale: effectivePlaybackScale(1),
      query: null, rafId: null, destroyed: false, runtimeErrors: 0,
      comparison: {valid: false, error: null, open: false, axis: "scenario", scenario: "E02", mode: "AUTO", trigger: null}
    };
    const listeners = [];
    const listen = (target, type, handler) => { target.addEventListener(type, handler); listeners.push([target, type, handler]); };
    const store = new root.S3TraceStore({
      root, document: doc, manifest: root.S3_TRACE_MANIFEST, cacheLimit: 3,
      errorHost: null, onError: function () {}, resourceDisposer: function () {}
    });
    const comparisonEvidence = root.S3_COMPARISON_EVIDENCE;
    try { validateComparisonEvidence(comparisonEvidence); state.comparison.valid = true; }
    catch (error) { state.comparison.error = error; }

    function queryFromControls() {
      return {tier: Number(byId("tierSelect").value), profile: byId("profileSelect").value, strategy_mode: byId("strategySelect").value};
    }

    function comparisonScenario(id) {
      return comparisonEvidence.scenarios.find(item => item.id === id);
    }

    function comparisonPickText(row) {
      return Object.entries(row.picked_counts).map(([mode, count]) => `${EVIDENCE_MODE_LABEL[mode] || mode.toUpperCase()}×${count}`).join(" / ");
    }

    function formatEvidenceNumber(value, digits = 1) {
      return value === null || value === undefined || !Number.isFinite(Number(value)) ? "NA" : Number(value).toFixed(digits);
    }

    function renderComparisonMini() {
      const host = byId("comparisonMiniBars"), title = byId("comparisonMini").querySelector(".comparisonMiniHead b");
      host.replaceChildren();
      if (!state.comparison.valid) {
        const message = doc.createElement("em"); message.textContent = `证据不可用：${state.comparison.error ? state.comparison.error.message : "bundle 缺失"}`; host.append(message);
        [byId("openComparisonLab"), byId("openComparisonLabMini")].forEach(button => { button.disabled = true; button.setAttribute("aria-disabled", "true"); });
        return;
      }
      const profile = state.query ? state.query.profile : byId("profileSelect").value;
      const scenarioId = PROFILE_SCENARIO[profile] || "E02", scenario = comparisonScenario(scenarioId);
      title.textContent = `S1 ${scenarioId} · 固定 4 / 8`;
      const rows = selectComparisonEvidence(comparisonEvidence, "scenario", scenarioId).filter(row => ["seq", "near", "score", "awra"].includes(row.mode));
      const maximum = Math.max(...rows.map(row => row.p95_mean_s || 0), 1);
      rows.forEach(row => {
        const item = doc.createElement("div"); item.className = "miniCompareRow";
        item.dataset.current = String(Boolean(state.query && state.query.strategy_mode === row.mode));
        item.setAttribute("aria-label", `${scenario.title} ${EVIDENCE_MODE_LABEL[row.mode]}，seed级响应P95均值 ${formatEvidenceNumber(row.p95_mean_s)} 秒，95%CI半宽 ${formatEvidenceNumber(row.p95_ci95_half_s)} 秒`);
        const label = doc.createElement("span"), track = doc.createElement("span"), fill = doc.createElement("i"), value = doc.createElement("span");
        label.textContent = EVIDENCE_MODE_LABEL[row.mode]; track.className = "miniCompareTrack"; fill.style.width = `${Math.max(2, row.p95_mean_s / maximum * 100)}%`; track.append(fill);
        value.textContent = `${formatEvidenceNumber(row.p95_mean_s)}s`; item.append(label, track, value); host.append(item);
      });
    }

    function comparisonHeaderCell(label, description) {
      const cell = doc.createElement("div"), button = doc.createElement("button"); button.type = "button";
      button.textContent = label; button.title = description; button.setAttribute("aria-label", `${label}：${description}`); cell.append(button); return cell;
    }

    function renderComparisonLab() {
      if (!state.comparison.valid) return;
      byId("comparisonScenarioTab").setAttribute("aria-selected", String(state.comparison.axis === "scenario"));
      byId("comparisonModeTab").setAttribute("aria-selected", String(state.comparison.axis === "mode"));
      byId("comparisonScenarioTab").tabIndex = state.comparison.axis === "scenario" ? 0 : -1;
      byId("comparisonModeTab").tabIndex = state.comparison.axis === "mode" ? 0 : -1;
      const toolbar = byId("comparisonToolbar"); toolbar.replaceChildren();
      const label = doc.createElement("label"), labelText = doc.createElement("span"), select = doc.createElement("select"), scope = doc.createElement("div");
      scope.className = "matrixScope"; scope.textContent = "S1 · 10 seeds × 100 周期\n固定权重 · SIM";
      if (state.comparison.axis === "scenario") {
        labelText.textContent = "受控情景";
        comparisonEvidence.scenarios.forEach(item => {
          const option = doc.createElement("option"); option.value = item.id; option.textContent = `${item.id} · ${item.title}${item.extended_pressure ? " · 扩展压力" : ""}`; select.append(option);
        });
        select.value = state.comparison.scenario;
        select.addEventListener("change", () => { state.comparison.scenario = select.value; renderComparisonLab(); });
      } else {
        labelText.textContent = "固定算法链";
        EVIDENCE_MODES.forEach(mode => { const option = doc.createElement("option"); option.value = mode; option.textContent = EVIDENCE_MODE_LABEL[mode]; select.append(option); });
        select.value = state.comparison.mode;
        select.addEventListener("change", () => { state.comparison.mode = select.value; renderComparisonLab(); });
      }
      label.append(labelText, select); toolbar.append(label, scope);

      const rows = selectComparisonEvidence(comparisonEvidence, state.comparison.axis,
        state.comparison.axis === "scenario" ? state.comparison.scenario : state.comparison.mode);
      const table = byId("comparisonTable"); table.replaceChildren();
      const header = doc.createElement("div"); header.className = "comparisonRow comparisonHeader";
      header.append(
        comparisonHeaderCell(state.comparison.axis === "scenario" ? "算法链" : "货物情景", "本列只标识 S1 受控单元；不等于当前 S3 三维 trace。"),
        comparisonHeaderCell("响应 P95", "每个 seed 内按 sorted[min(n-1,int(n×0.95))] 取系统响应 P95；此处为 seed 级 P95 均值与 t-95%CI 半宽。"),
        comparisonHeaderCell("可行", "n_feasible / 10；AUTO 或固定策略不可行时不把 NA regret 填成 0。"),
        comparisonHeaderCell("护栏", "10 seeds 合计 fail / viol；E14 的预期拒收另列 reject，不混作失败。"),
        comparisonHeaderCell("选择 / 稳定", "picked_counts 为 10 seeds 的启动时一次选择；稳定率=max(picked_count)/10，不代表运行中逐货切换。")
      ); table.append(header);
      rows.forEach(row => {
        const scenario = comparisonScenario(row.scenario), line = doc.createElement("div");
        line.className = "comparisonRow comparisonBodyRow"; line.dataset.auto = String(row.mode === "AUTO"); line.dataset.extended = String(scenario.extended_pressure);
        const identity = doc.createElement("div"), p95 = doc.createElement("div"), feasible = doc.createElement("div"), guard = doc.createElement("div"), route = doc.createElement("div");
        const identityStrong = doc.createElement("strong"), identitySmall = doc.createElement("small");
        if (state.comparison.axis === "scenario") { identityStrong.textContent = EVIDENCE_MODE_LABEL[row.mode]; identitySmall.textContent = row.mode === "AUTO" ? "规则阈值 · run-start-once" : row.mode; }
        else { identityStrong.textContent = `${scenario.id} · ${scenario.title}`; identitySmall.textContent = scenario.extended_pressure ? "扩展 Tier 3 压力 · 非 canonical G2 / 非 H" : "canonical G2 情景"; }
        identity.append(identityStrong, identitySmall);
        const p95Strong = doc.createElement("strong"), p95Small = doc.createElement("small"); p95Strong.textContent = row.p95_mean_s === null ? "NA" : `${formatEvidenceNumber(row.p95_mean_s)} s`;
        p95Small.textContent = row.p95_mean_s === null ? "不可比" : `±${formatEvidenceNumber(row.p95_ci95_half_s)} · n=${row.p95_seed_n}`; p95.append(p95Strong, p95Small);
        const feasibleStrong = doc.createElement("strong"), feasibleSmall = doc.createElement("small"); feasibleStrong.textContent = `${row.n_feasible}/10`; feasibleStrong.className = row.n_feasible === 10 ? "guardOk" : "guardBad";
        feasibleSmall.textContent = `不可行 ${(row.infeasible_rate * 100).toFixed(0)}%`; feasible.append(feasibleStrong, feasibleSmall);
        const guardStrong = doc.createElement("strong"), guardSmall = doc.createElement("small"); guardStrong.textContent = `${row.fail_sum} / ${row.viol_sum}`; guardStrong.className = row.fail_sum === 0 && row.viol_sum === 0 ? "guardOk" : "guardBad";
        guardSmall.textContent = `reject ${row.reject_sum}`; guard.append(guardStrong, guardSmall);
        const routeStrong = doc.createElement("strong"), routeSmall = doc.createElement("small"); routeStrong.textContent = comparisonPickText(row); routeSmall.textContent = `稳定 ${(row.selection_stability * 100).toFixed(0)}%`; route.append(routeStrong, routeSmall);
        line.append(identity, p95, feasible, guard, route); table.append(line);
      });

      const autoSummary = byId("comparisonAutoSummary"); autoSummary.replaceChildren();
      if (state.comparison.axis === "scenario") {
        const auto = rows.find(row => row.mode === "AUTO"), scenario = comparisonScenario(state.comparison.scenario);
        const strong = doc.createElement("b"), span = doc.createElement("span"); strong.textContent = `AUTO → ${comparisonPickText(auto)} · 选择稳定 ${(auto.selection_stability * 100).toFixed(0)}%`;
        span.textContent = auto.auto_regret_mean_s === null ? "regret=NA（无可比固定 oracle 或 AUTO 不可行）" :
          `动态 regret ${formatEvidenceNumber(auto.auto_regret_mean_s)} ±${formatEvidenceNumber(auto.auto_regret_ci95_half_s)} s；同 (scenario, seed) 的可行固定策略最小 P95 作事后 oracle。${scenario.extended_pressure ? " 本情景为扩展压力，非 canonical G2 / 非 H。" : ""}`;
        autoSummary.append(strong, span);
      } else {
        const strong = doc.createElement("b"), span = doc.createElement("span"); strong.textContent = `${EVIDENCE_MODE_LABEL[state.comparison.mode]} · 18 情景敏感性视图`;
        span.textContent = "工作负载不同，只用于暴露边界与退化，不跨情景求平均、不据此做算法总排名。"; autoSummary.append(strong, span);
      }
      byId("comparisonFoot").innerHTML = '<b>证据隔离：</b>S1 为 2026..2035 的受控筛查；当前 3D 是独立 S3 单 seed 代表性回放。两者不池化、不把 S1 数值冒充当前动画 KPI。固定评分权重仅隔离路由差异；AUTO 是确定性规则阈值，启动时一次选定，不是在线学习。';
    }

    function comparisonInertTargets() {
      const rail = byId("workHud"), viewport = byId("viewport"), dialog = byId("comparisonLab");
      return Array.from(new Set([
        ...Array.from(rail.children).filter(element => element !== dialog),
        ...Array.from(viewport.children).filter(element => element !== rail)
      ]));
    }

    function setComparisonInert(open) {
      comparisonInertTargets().forEach(element => {
        if (open) {
          element.dataset.s3PreviousAriaHidden = element.hasAttribute("aria-hidden") ? element.getAttribute("aria-hidden") : "__ABSENT__";
          element.inert = true; element.setAttribute("aria-hidden", "true");
        } else if (element.dataset.s3PreviousAriaHidden !== undefined) {
          element.inert = false;
          const previous = element.dataset.s3PreviousAriaHidden;
          if (previous === "__ABSENT__") element.removeAttribute("aria-hidden"); else element.setAttribute("aria-hidden", previous);
          delete element.dataset.s3PreviousAriaHidden;
        }
      });
    }

    function comparisonFocusables() {
      return Array.from(byId("comparisonLab").querySelectorAll('button:not([disabled]),select:not([disabled]),[href],[tabindex]:not([tabindex="-1"])'))
        .filter(element => !element.hidden && element.getClientRects().length > 0);
    }

    function openComparisonLab(trigger) {
      if (!state.comparison.valid) return;
      state.comparison.trigger = trigger || null;
      state.comparison.scenario = PROFILE_SCENARIO[state.query ? state.query.profile : byId("profileSelect").value] || state.comparison.scenario;
      state.comparison.open = true; byId("comparisonLab").hidden = false; setComparisonInert(true); renderComparisonLab(); byId("closeComparisonLab").focus();
    }

    function closeComparisonLab() {
      if (!state.comparison.open) return;
      state.comparison.open = false; byId("comparisonLab").hidden = true; setComparisonInert(false);
      if (state.comparison.trigger && typeof state.comparison.trigger.focus === "function") state.comparison.trigger.focus();
      state.comparison.trigger = null;
    }

    /* 0719 本屏证据叠层:结构与 comparisonLab 一致(hidden 属性开合 + 触发器焦点回归),
       但不设 inert——它只是把左栏降级下来的两块按需展开,不阻断背景观察。 */
    let evidenceTrigger = null;
    function openEvidenceDock(trigger) {
      evidenceTrigger = trigger || null;
      byId("evidenceDock").hidden = false; byId("closeEvidenceDock").focus();
    }
    function closeEvidenceDock() {
      const dock = byId("evidenceDock");
      if (dock.hidden) return;
      dock.hidden = true;
      if (evidenceTrigger && typeof evidenceTrigger.focus === "function") evidenceTrigger.focus();
      evidenceTrigger = null;
    }

    function comparisonSnapshot() {
      return {valid: state.comparison.valid, error: state.comparison.error && state.comparison.error.message,
        open: state.comparison.open, axis: state.comparison.axis, scenario: state.comparison.scenario, mode: state.comparison.mode,
        miniRows: byId("comparisonMiniBars").querySelectorAll(".miniCompareRow").length,
        tableRows: Math.max(0, byId("comparisonTable").querySelectorAll(".comparisonBodyRow").length),
        inertTargets: comparisonInertTargets().filter(element => element.inert).length,
        activeElement: doc.activeElement && doc.activeElement.id};
    }

    function sameQuery(left, right) {
      return left && right && left.tier === right.tier && left.profile === right.profile && left.strategy_mode === right.strategy_mode;
    }

    function syncControls(query) {
      byId("tierSelect").value = String(query.tier); byId("profileSelect").value = query.profile; byId("strategySelect").value = query.strategy_mode;
    }

    function setLoading(loading, query) {
      state.loading = loading;
      byId("traceLoadState").textContent = loading ? `校验 T${query.tier}/${query.profile}/${query.strategy_mode}…` : "已校验 · sim trace";
      byId("runtimeControls").setAttribute("aria-busy", String(loading));
      ["tierSelect", "profileSelect", "strategySelect"].forEach(id => { byId(id).setAttribute("aria-busy", String(loading)); });
    }

    function clearError() { const host = byId("traceErrorHost"); host.hidden = true; host.replaceChildren(); }

    let lastFailedQuery = null;
    function showError(error, query) {
      lastFailedQuery = Object.assign({}, query);
      const host = byId("traceErrorHost"); host.replaceChildren();
      const text = doc.createElement("span"), retry = doc.createElement("button");
      text.textContent = `加载失败 · T${query.tier}/${query.profile}/${query.strategy_mode} · ${error.message}`;
      retry.type = "button"; retry.textContent = "重试该组合";
      retry.addEventListener("click", () => { selectQuery(lastFailedQuery, {force: true}); });
      host.append(text, retry); host.hidden = false;
      if (state.query) syncControls(state.query);
    }

    const latest = createLatestOnlyLoader({
      load: (query, options) => store.load(query, options),
      prepare: (trace, context) => {
        const timeline = buildTimeline(trace);
        const elapsed = context ? elapsedForCheckpoint(timeline, context) : 0;
        return {trace, timeline, elapsed, frame: deriveFrame(trace, timeline, elapsed)};
      },
      commit: prepared => {
        state.trace = prepared.trace; state.timeline = prepared.timeline; state.elapsed = prepared.elapsed;
        state.query = {tier: prepared.trace.meta.tier, profile: prepared.trace.meta.profile, strategy_mode: prepared.trace.meta.strategy_mode};
        syncControls(state.query); clearError(); rendererBridge.renderFrame(state.trace, prepared.frame); renderComparisonMini();
        if (state.comparison.open) renderComparisonLab();
      },
      onLoading: setLoading,
      onError: showError
    });

    function selectQuery(query, options) {
      if (state.destroyed || (state.query && sameQuery(query, state.query) && !options)) return Promise.resolve({status: "unchanged"});
      const checkpoint = state.timeline ? checkpointAt(state.timeline, state.elapsed) : null;
      return latest.select(Object.assign({}, query), checkpoint, options);
    }

    function togglePause() {
      state.paused = !state.paused;
      const button = byId("pauseMotion"); button.textContent = state.paused ? "继续" : "暂停"; button.setAttribute("aria-pressed", String(state.paused));
    }

    function replay() { if (state.timeline) { state.elapsed = 0; state.lastNow = null; } }

    function setPlaybackMultiplier(value) {
      const multiplier = normalizePlaybackMultiplier(value);
      state.playbackMultiplier = multiplier; state.playbackScale = effectivePlaybackScale(multiplier); state.lastNow = null;
      byId("playbackSpeed").value = String(multiplier); byId("playbackValue").textContent = `${multiplier.toFixed(2)}×`;
      return multiplier;
    }

    function exportFrame() {
      renderer.render(scene, camera);
      const link = doc.createElement("a"); link.download = `S3_${state.trace ? state.trace.meta.trace_id : "frame"}.png`; link.href = renderer.domElement.toDataURL("image/png"); link.click();
    }

    ["strategySelect", "tierSelect", "profileSelect"].forEach(id => listen(byId(id), "change", () => { selectQuery(queryFromControls()); }));
    listen(byId("pauseMotion"), "click", togglePause); listen(byId("replayTrace"), "click", replay);
    listen(byId("resetCamera"), "click", () => { setCamera(); }); listen(byId("exp"), "click", exportFrame);
    listen(byId("playbackSpeed"), "input", event => { setPlaybackMultiplier(event.target.value); });
    ["openComparisonLab", "openComparisonLabMini"].forEach(id => listen(byId(id), "click", event => openComparisonLab(event.currentTarget)));
    listen(byId("closeComparisonLab"), "click", closeComparisonLab);
    /* 0719 本屏证据叠层开合(顶栏 chip / 关闭钮 / 点遮罩 / Esc) */
    listen(byId("openEvidenceDock"), "click", event => openEvidenceDock(event.currentTarget));
    listen(byId("closeEvidenceDock"), "click", closeEvidenceDock);
    listen(byId("evidenceDock"), "click", event => { if (event.target === byId("evidenceDock")) closeEvidenceDock(); });
    listen(byId("evidenceDock"), "keydown", event => { if (event.key === "Escape") { event.preventDefault(); closeEvidenceDock(); } });
    listen(byId("comparisonScenarioTab"), "click", () => { state.comparison.axis = "scenario"; renderComparisonLab(); });
    listen(byId("comparisonModeTab"), "click", () => { state.comparison.axis = "mode"; renderComparisonLab(); });
    listen(byId("comparisonLab"), "click", event => { if (event.target === byId("comparisonLab")) closeComparisonLab(); });
    listen(byId("comparisonLab"), "keydown", event => {
      if (event.key === "Escape") { event.preventDefault(); closeComparisonLab(); return; }
      if (["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key) && event.target.matches('[role="tab"]')) {
        event.preventDefault();
        state.comparison.axis = ["ArrowRight", "End"].includes(event.key) ? "mode" : "scenario"; renderComparisonLab();
        byId(state.comparison.axis === "mode" ? "comparisonModeTab" : "comparisonScenarioTab").focus(); return;
      }
      if (event.key !== "Tab") return;
      const focusables = comparisonFocusables(); if (!focusables.length) return;
      const first = focusables[0], last = focusables[focusables.length - 1];
      if (event.shiftKey && (doc.activeElement === first || !byId("comparisonLab").contains(doc.activeElement))) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && doc.activeElement === last) { event.preventDefault(); first.focus(); }
    });
    listen(controls, "change", () => { rendererBridge.refreshProjection(); });
    listen(root, "resize", () => { resizeScene(); if (state.trace) renderRespSpark(state.trace); });

    const schedule = callback => root.requestAnimationFrame(callback);
    function frame(now) {
      if (state.destroyed) return;
      try {
        if (state.lastNow === null) state.lastNow = now;
        const delta = clamp((now - state.lastNow) / 1000, 0, .20); state.lastNow = now;
        controls.update();
        if (state.timeline && !state.paused && !state.loading) state.elapsed += delta * state.playbackScale;
        if (state.trace && state.timeline) rendererBridge.renderFrame(state.trace, deriveFrame(state.trace, state.timeline, state.elapsed));
        else renderer.render(scene, camera);
      } catch (error) {
        state.runtimeErrors += 1; state.paused = true; showError(error, state.query || queryFromControls());
      }
      state.rafId = schedule(frame);
    }

    function destroy() {
      if (state.destroyed) return;
      state.destroyed = true; latest.destroy(); store.destroy();
      if (state.comparison.open) setComparisonInert(false);
      if (state.rafId !== null) root.cancelAnimationFrame(state.rafId);
      listeners.forEach(([target, type, handler]) => target.removeEventListener(type, handler));
      rendererBridge.dispose();
    }

    renderComparisonMini();
    root.__S3_QA = Object.freeze({
      version: "s3-single-runtime-v1",
      snapshot() {
        return {
          traceId: state.trace && state.trace.meta.trace_id, query: state.query && Object.assign({}, state.query),
          paused: state.paused, loading: state.loading, runtimeErrors: state.runtimeErrors,
          playback: {baseScale: DEFAULT_PLAYBACK_SCALE, multiplier: state.playbackMultiplier, effectiveScale: state.playbackScale},
          checkpoint: state.timeline ? checkpointAt(state.timeline, state.elapsed) : null,
          loader: latest.snapshot(), comparison: comparisonSnapshot(), renderer: rendererBridge.metrics()
        };
      },
      select(query) { return selectQuery(query); },
      setPlaybackMultiplier(value) { return setPlaybackMultiplier(value); },
      resetCamera() { return setCamera(); },
      composition() { return rendererBridge.compositionSnapshot(); },
      collisionGeometry() { return rendererBridge.collisionSnapshot(true); },
      runLoopAudit(count = 20) {
        invariant(state.timeline && Number.isInteger(count) && count > 0, "runLoopAudit 参数非法");
        const before = rendererBridge.metrics(); state.elapsed += state.timeline.total * count;
        rendererBridge.renderFrame(state.trace, deriveFrame(state.trace, state.timeline, state.elapsed));
        return {before, after: rendererBridge.metrics(), checkpoint: checkpointAt(state.timeline, state.elapsed)};
      },
      seek(cycleIndex, operationKey, progress = .5) {
        invariant(state.trace && state.timeline, "seek 前 trace 尚未就绪");
        invariant(Number.isInteger(cycleIndex) && cycleIndex >= 0 && cycleIndex < state.trace.events.length, "seek cycleIndex 越界");
        invariant(PROCESS_STEPS.includes(operationKey), "seek operationKey 非法");
        invariant(Number.isFinite(progress) && progress >= 0 && progress <= 1, "seek progress 必须在 0..1");
        const group = state.timeline.groupsByKey.get(`${cycleIndex}|${operationKey}`);
        invariant(group, `seek group 不存在 ${cycleIndex}/${operationKey}`);
        state.elapsed = group.d0 + (group.d1 - group.d0) * progress; state.lastNow = null; state.paused = true;
        byId("pauseMotion").textContent = "继续"; byId("pauseMotion").setAttribute("aria-pressed", "true");
        rendererBridge.renderFrame(state.trace, deriveFrame(state.trace, state.timeline, state.elapsed));
        return root.__S3_QA.snapshot();
      },
      seekFault(faultIndex = 0) {
        invariant(state.trace && state.timeline, "seekFault 前 trace 尚未就绪");
        const faults = state.timeline.segments.filter(segment => segment.phaseName === "FAULT_RECOVERY");
        invariant(Number.isInteger(faultIndex) && faultIndex >= 0 && faultIndex < faults.length, "seekFault faultIndex 越界");
        const segment = faults[faultIndex]; state.elapsed = (segment.d0 + segment.d1) / 2; state.lastNow = null; state.paused = true;
        byId("pauseMotion").textContent = "继续"; byId("pauseMotion").setAttribute("aria-pressed", "true");
        rendererBridge.renderFrame(state.trace, deriveFrame(state.trace, state.timeline, state.elapsed));
        return root.__S3_QA.snapshot();
      },
      destroy
    });

    selectQuery(queryFromControls());
    state.rafId = schedule(frame);
    return {state, selectQuery, destroy};
  }

  return {
    TRACE_SCHEMA, PROCESS_STEPS, DEFAULT_SIM_RATE, DEFAULT_PLAYBACK_SCALE, PLAYBACK_MULTIPLIER_MIN, PLAYBACK_MULTIPLIER_MAX,
    PRESENTATION_TIMING,
    MIN_TRAVEL_DISPLAY_S, MIN_HANDLE_DISPLAY_S, CONSUMED_HOLD_S, LOOP_RESET_MASK_S,
    normalizePlaybackMultiplier, effectivePlaybackScale, ownershipSnapshot, validateVisualTopology, rectIntersectionArea, chooseLabelPairLayout,
    pointInRect, segmentsIntersect, segmentIntersectsRect, chooseLeaderRoute,
    validateComparisonEvidence, selectComparisonEvidence,
    buildTimeline, locateSegment,
    checkpointAt, elapsedForCheckpoint, deriveFrame, reconcileInventoryMap,
    createLatestOnlyLoader, motionPoint, handleCargoDrop, cargoWorldPosition, operationPathPlan, bootstrap
  };
});
