/* S3 方案A「进度轴候选」QA(0716,规格=design_reviews/0716_s3_ia_review/spec_a_freeze.md §7)
   基线:capture_s3_fill_candidate_qa.mjs(v7,冻结不改)的全部语义断言 + 方案 A 新增门:
   唯一性(计数/术语/七步不常驻)、浮层视口、9 项安置齐全、reserveRuleBadge 面积(防 0716 白罩事故回归)。 */
import { createRequire } from 'node:module';
import { createHash } from 'node:crypto';
import { createServer } from 'node:http';
import { fileURLToPath } from 'node:url';
import { dirname, extname, join, resolve, sep } from 'node:path';
import { copyFileSync, existsSync, mkdirSync, readFileSync, readdirSync, statSync, writeFileSync } from 'node:fs';

const HERE = dirname(fileURLToPath(import.meta.url));
const SHOWCASE = resolve(HERE, '..');
const PAGE_NAME = '01_连续填仓.html';
const SOURCE = join(SHOWCASE, 'src', PAGE_NAME);
const RUNTIME = join(SHOWCASE, 'src', 's3_fill_candidate_runtime.js');
const STORE = join(SHOWCASE, 'src', 's3_fill_store.js');
const INTERACTIONS = join(SHOWCASE, 'src', 's3_layout_a_interactions.js');
const DATA_GATE = join(SHOWCASE, 'out', 's3_fill_data_gate');
const POINTER = join(DATA_GATE, 'latest.json');
const POINTER_RECORD = JSON.parse(readFileSync(POINTER, 'utf8'));
const EXPECTED_RELEASE = POINTER_RECORD.release_id;
const MANIFEST = resolve(DATA_GATE, POINTER_RECORD.manifest_resource);
if (!MANIFEST.startsWith(DATA_GATE + sep)) throw new Error('release manifest escapes data gate root');
const REGISTRY = join(SHOWCASE, 'evidence', 's3_fill_release_registry.json');
const RELEASE_DIR = dirname(MANIFEST);
const OUT = resolve(process.argv[2] || join(SHOWCASE, 'out', 's3_layout_a_qa_0716'));
const CHROME = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE ||
  'C:/Users/86177/AppData/Local/ms-playwright/chromium-1223/chrome-win64/chrome.exe';
const localRequire = createRequire(import.meta.url);
const bundledNodeModules = process.env.CODEX_NODE_MODULES ||
  'C:/Users/86177/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules';
let playwright;
try { playwright = localRequire('playwright'); }
catch (error) {
  const pnpmRoot = join(bundledNodeModules, '.pnpm');
  const packageDir = existsSync(pnpmRoot) ? readdirSync(pnpmRoot).find(name => /^playwright@/.test(name)) : null;
  if (!packageDir) throw error;
  playwright = createRequire(join(pnpmRoot, packageDir, 'node_modules', 'playwright', 'package.json'))('playwright');
}
const { chromium } = playwright;

const mime = {'.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.json': 'application/json; charset=utf-8'};
const hash = path => createHash('sha256').update(readFileSync(path)).digest('hex');
mkdirSync(OUT, {recursive: true});
const liveFiles = {
  source: SOURCE, runtime: RUNTIME, store: STORE, interactions: INTERACTIONS,
  three: join(SHOWCASE, 'src', 'lib', 'three.min.js'),
  orbit: join(SHOWCASE, 'src', 'lib', 'OrbitControls.js'),
  pointer: POINTER, registry: REGISTRY, manifest: MANIFEST,
  auditNear: join(RELEASE_DIR, 'candidate_audit_online_near.jsonl.gz'),
  auditScore: join(RELEASE_DIR, 'candidate_audit_online_score.jsonl.gz'),
  auditSeq: join(RELEASE_DIR, 'candidate_audit_online_seq.jsonl.gz')
};
const initialHashes = Object.fromEntries(Object.entries(liveFiles).map(([key, path]) => [key, hash(path)]));
const snapshotId = createHash('sha256').update(JSON.stringify(initialHashes)).digest('hex').slice(0, 16);
const SNAPSHOT = join(OUT, `_local_hash_snapshot_${snapshotId}`);
const snapshotTargets = {
  source: join(SNAPSHOT, 'src', PAGE_NAME),
  runtime: join(SNAPSHOT, 'src', 's3_fill_candidate_runtime.js'),
  store: join(SNAPSHOT, 'src', 's3_fill_store.js'),
  interactions: join(SNAPSHOT, 'src', 's3_layout_a_interactions.js'),
  three: join(SNAPSHOT, 'src', 'lib', 'three.min.js'),
  orbit: join(SNAPSHOT, 'src', 'lib', 'OrbitControls.js'),
  pointer: join(SNAPSHOT, 'release_evidence', 'latest.json'),
  registry: join(SNAPSHOT, 'release_evidence', 's3_fill_release_registry.json'),
  manifest: join(SNAPSHOT, 'release_evidence', 's3_fill_data_gate.json'),
  auditNear: join(SNAPSHOT, 'release_evidence', 'candidate_audit_online_near.jsonl.gz'),
  auditScore: join(SNAPSHOT, 'release_evidence', 'candidate_audit_online_score.jsonl.gz'),
  auditSeq: join(SNAPSHOT, 'release_evidence', 'candidate_audit_online_seq.jsonl.gz')
};
for (const [key, target] of Object.entries(snapshotTargets)) {
  mkdirSync(dirname(target), {recursive: true});
  if (!existsSync(target)) copyFileSync(liveFiles[key], target);
  if (hash(target) !== initialHashes[key]) throw new Error(`local hash snapshot collision: ${key}`);
}
const snapshotHashes = Object.fromEntries(Object.entries(snapshotTargets).map(([key, path]) => [key, hash(path)]));
const registryRecord = JSON.parse(readFileSync(REGISTRY, 'utf8'));
const registryEntry = registryRecord.entries.find(entry => entry.release_id === EXPECTED_RELEASE);
const MANIFEST_RECORD = JSON.parse(readFileSync(MANIFEST, 'utf8'));
const auditHashChecks = {
  near: MANIFEST_RECORD.audit_files?.['candidate_audit_online_near.jsonl.gz']?.sha256 === initialHashes.auditNear,
  score: MANIFEST_RECORD.audit_files?.['candidate_audit_online_score.jsonl.gz']?.sha256 === initialHashes.auditScore,
  seq: MANIFEST_RECORD.audit_files?.['candidate_audit_online_seq.jsonl.gz']?.sha256 === initialHashes.auditSeq
};
const releaseEvidenceAudit = {
  trustBoundary: 'local hash-locked reproducibility snapshot; not a cryptographic signature or anti-tamper guarantee',
  releaseId: EXPECTED_RELEASE,
  pointerMatchesManifest: POINTER_RECORD.manifest_file_sha256 === initialHashes.manifest,
  registryMatchesRelease: registryRecord.active_release_id === EXPECTED_RELEASE && registryEntry?.status === 'approved_for_frontend_binding' &&
    registryEntry?.manifest_file_sha256 === initialHashes.manifest && registryEntry?.manifest_payload_sha256 === POINTER_RECORD.manifest_payload_sha256,
  auditHashChecks
};
releaseEvidenceAudit.pass = releaseEvidenceAudit.pointerMatchesManifest && releaseEvidenceAudit.registryMatchesRelease &&
  Object.values(auditHashChecks).every(Boolean);

const server = createServer((request, response) => {
  try {
    const pathname = decodeURIComponent(new URL(request.url, 'http://127.0.0.1').pathname).replace(/^\/+/, '');
    if (pathname === 'favicon.ico') { response.writeHead(204); response.end(); return; }
    const target = resolve(SNAPSHOT, pathname || `src/${PAGE_NAME}`);
    if (!target.startsWith(SNAPSHOT + sep) || !existsSync(target) || !statSync(target).isFile()) {
      response.writeHead(404); response.end('not found'); return;
    }
    response.writeHead(200, {'content-type': mime[extname(target)] || 'application/octet-stream', 'cache-control': 'no-store'});
    response.end(readFileSync(target));
  } catch (error) { response.writeHead(500); response.end(error.message); }
});
await new Promise(resolveReady => server.listen(0, '127.0.0.1', resolveReady));
const port = server.address().port;
const browser = await chromium.launch({headless: true, executablePath: CHROME});
const report = {schema: 's3-layout-a-qa-v1', source: SOURCE, expectedRelease: EXPECTED_RELEASE,
  snapshot: {id: snapshotId, root: SNAPSHOT, initialHashes, snapshotHashes, trustBoundary: releaseEvidenceAudit.trustBoundary},
  releaseEvidenceAudit, runtimeErrors: [], consoleErrors: [], viewports: [], topologyViewports: [], layoutAudits: [], popAudits: [], states: [], pass: false, errors: []};

const pageUrl = `http://127.0.0.1:${port}/src/${encodeURIComponent(PAGE_NAME)}`;
try {
  for (const [width, height] of [[1280, 720], [1600, 900], [1920, 1080]]) {
    const page = await browser.newPage({viewport: {width, height}, deviceScaleFactor: 1});
    page.on('pageerror', error => report.runtimeErrors.push(`${width}x${height}: ${error.message}`));
    page.on('console', message => { if (message.type() === 'error') report.consoleErrors.push(`${width}x${height}: ${message.text()}`); });
    await page.goto(pageUrl, {waitUntil: 'load'});
    await page.waitForFunction(expected => window.__S3_FILL_QA?.snapshot?.().releaseId === expected && window.__S3_LAYOUT_A, EXPECTED_RELEASE, {timeout: 30000});
    const viewportAudit = await page.evaluate(() => {
      const rail = document.getElementById('workHud').getBoundingClientRect();
      const dock = document.getElementById('sceneDock').getBoundingClientRect();
      const gl = document.getElementById('gl').getBoundingClientRect();
      const topbar = document.getElementById('topbarA').getBoundingClientRect();
      const axis = document.getElementById('progressAxisHost').getBoundingClientRect();
      const bookmarks = document.getElementById('fillBookmarks').getBoundingClientRect();
      const mapWrap = document.getElementById('slotMapWrap').getBoundingClientRect();
      const map = document.getElementById('slotMap').getBoundingClientRect();
      const mapKeyEl = document.querySelector('#slotMapWrap .mapKey');
      const mapKeyVisible = mapKeyEl && getComputedStyle(mapKeyEl).display !== 'none';
      const badge = document.getElementById('reserveRuleBadge').getBoundingClientRect();
      const phaseSegmentCount = document.querySelectorAll('#phaseSegments .phaseSeg').length;
      const hudOverflow = [...document.querySelectorAll('#workHud > *,#insightStack > *')].filter(element => {
        const style = getComputedStyle(element), rect = element.getBoundingClientRect();
        if (style.display === 'none' || style.visibility === 'hidden' || rect.width <= 0 || rect.height <= 0) return false;
        return rect.left < rail.left - .5 || rect.right > rail.right + .5 || rect.top < rail.top - .5 || rect.bottom > rail.bottom + .5 ||
          rect.left < -.5 || rect.right > innerWidth + .5 || rect.top < -.5 || rect.bottom > innerHeight + .5;
      }).map(element => ({id: element.id || element.className, rect: {...element.getBoundingClientRect().toJSON()}}));
      const badgeAreaShare = (badge.width * badge.height) / Math.max(1, gl.width * gl.height);
      return {rail: {...rail.toJSON()}, dock: {...dock.toJSON()}, gl: {...gl.toJSON()}, topbar: {...topbar.toJSON()},
        axis: {...axis.toJSON()}, bookmarks: {...bookmarks.toJSON()}, map: {...map.toJSON()}, mapWrap: {...mapWrap.toJSON()},
        mapKeyVisible, badge: {...badge.toJSON()}, badgeAreaShare, phaseSegmentCount,
        bodyScroll: {width: document.documentElement.scrollWidth, height: document.documentElement.scrollHeight},
        clipped: rail.bottom > innerHeight + .5 || dock.bottom > innerHeight + .5 || gl.width < 300 || gl.height < 300,
        mapClipped: map.left < mapWrap.left - .5 || map.right > mapWrap.right + .5 || map.top < mapWrap.top - .5 || map.bottom > mapWrap.bottom + .5,
        hudOverflow,
        axisAboveGl: axis.bottom <= gl.top + .5 && topbar.bottom <= axis.top + .5};
    });
    report.viewports.push({width, height, ...viewportAudit});
    const layoutAudit = await page.evaluate(() => window.__S3_LAYOUT_A.audit());
    const placement = await page.evaluate(() => ({
      traceStatsVisible: getComputedStyle(document.getElementById('traceStats')).display !== 'none' &&
        document.getElementById('traceStats').getBoundingClientRect().height > 20,
      queueVisible: document.getElementById('factQueue').getBoundingClientRect().height > 4,
      zoomHintPresent: Boolean(document.querySelector('#slotMapWrap .zoomHint')),
      releaseBadgeInAxis: document.getElementById('releaseBadge').closest('#axisRight') !== null,
      evidenceInAxis: document.getElementById('fillEvidence').closest('#axisRight') !== null,
      selectionReasonPresent: /固定四项权重|首个可用格|行程时间最短/.test(document.getElementById('decisionWrap').textContent),
      speedCanvasPresent: Boolean(document.getElementById('speed')),
      phaseRailInDock: document.getElementById('phaseRail').closest('#sceneDock') !== null,
      controlsInTopbar: document.getElementById('runtimeControls').closest('#topbarA') !== null,
      retrievalNotePresent: /存取效率/.test(document.getElementById('retrievalNote')?.textContent || '')
    }));
    report.layoutAudits.push({width, height, ...layoutAudit, placement});
    await page.screenshot({path: join(OUT, `viewport_${width}x${height}_start.png`), fullPage: false});
    const topology = await page.evaluate(() => {
      window.__S3_FILL_QA.setAlgorithm('score');
      window.__S3_FILL_QA.seekBookmark(267);
      return window.__S3_FILL_QA.setTopologyCamera();
    });
    await page.waitForTimeout(120);
    report.topologyViewports.push({width, height, ...topology});
    await page.screenshot({path: join(OUT, `topology_top_${width}x${height}.png`), fullPage: false});
    await page.evaluate(() => window.__S3_FILL_QA.resetCamera());
    await page.close();
  }

  const page = await browser.newPage({viewport: {width: 1600, height: 900}, deviceScaleFactor: 1});
  page.on('pageerror', error => report.runtimeErrors.push(`state: ${error.message}`));
  page.on('console', message => { if (message.type() === 'error') report.consoleErrors.push(`state: ${message.text()}`); });
  await page.goto(pageUrl, {waitUntil: 'load'});
  await page.waitForFunction(expected => window.__S3_FILL_QA?.snapshot?.().releaseId === expected && window.__S3_LAYOUT_A, EXPECTED_RELEASE, {timeout: 30000});

  for (const count of [0, 67, 134, 201, 241, 267]) {
    const value = await page.evaluate(countValue => window.__S3_FILL_QA.seekBookmark(countValue), count);
    const overlay = await page.evaluate(() => {
      const beacon = document.getElementById('targetBeacon'), dock = document.getElementById('sceneDock');
      const b = beacon.getBoundingClientRect(), d = dock.getBoundingClientRect();
      const overlap = Math.max(0, Math.min(b.right, d.right) - Math.max(b.left, d.left)) * Math.max(0, Math.min(b.bottom, d.bottom) - Math.max(b.top, d.top));
      return {targetHidden: beacon.hidden, target: {...b.toJSON()}, dock: {...d.toJSON()}, overlap,
        axisFill: document.querySelector('#fillBookmarkButtons .axisFill').style.width,
        layout: window.__S3_LAYOUT_A.audit()};
    });
    report.states.push({name: `bookmark_${count}`, snapshot: value, overlay});
    await page.screenshot({path: join(OUT, `bookmark_${String(count).padStart(3, '0')}.png`), fullPage: false});
  }

  for (const [operation, progress] of [['INFEED_HANDOFF', .55], ['LADEN_TRAVEL', .55], ['STORE_HANDLE', .50], ['STORE_HANDLE', .72], ['EMPTY_RETURN', .55]]) {
    const value = await page.evaluate(({operation, progress}) => window.__S3_FILL_QA.seekEvent(133, operation, progress), {operation, progress});
    report.states.push({name: `event134_${operation}_${progress}`, snapshot: value});
    await page.screenshot({path: join(OUT, `event134_${operation}_${String(progress).replace('.', '_')}.png`), fullPage: false});
  }

  /* 浮层视口断言 + hover 截图 */
  const viewportBox = await page.evaluate(() => document.getElementById('viewport').getBoundingClientRect().toJSON());
  const inViewport = rect => rect.width > 40 && rect.height > 24 &&
    rect.left >= viewportBox.left - .5 && rect.right <= viewportBox.right + .5 &&
    rect.top >= viewportBox.top - .5 && rect.bottom <= viewportBox.bottom + .5;
  const pops = [];
  for (const index of [0, 2, 5]) {
    const rect = await page.evaluate(value => window.__S3_LAYOUT_A.showNodePop(value).toJSON(), index);
    pops.push({kind: `node_${index}`, rect, inside: inViewport(rect)});
    if (index === 2) await page.screenshot({path: join(OUT, 'pop_node_134.png'), fullPage: false});
    await page.evaluate(() => window.__S3_LAYOUT_A.hidePops());
  }
  await page.evaluate(() => window.__S3_FILL_QA.seekEvent(133, 'LADEN_TRAVEL', .5));
  for (const index of [0, 3, 6]) {
    const rect = await page.evaluate(value => window.__S3_LAYOUT_A.showSegPop(value).toJSON(), index);
    pops.push({kind: `seg_${index}`, rect, inside: inViewport(rect)});
    if (index === 3) await page.screenshot({path: join(OUT, 'pop_seg_playing.png'), fullPage: false});
    await page.evaluate(() => window.__S3_LAYOUT_A.hidePops());
  }
  {
    const rect = await page.evaluate(() => window.__S3_LAYOUT_A.showEvidence().toJSON());
    pops.push({kind: 'evidence', rect, inside: inViewport(rect)});
    await page.screenshot({path: join(OUT, 'pop_evidence.png'), fullPage: false});
    await page.evaluate(() => window.__S3_LAYOUT_A.hidePops());
  }
  {
    await page.evaluate(() => window.__S3_LAYOUT_A.openMap());
    await page.waitForTimeout(350);
    const zoom = await page.evaluate(() => ({
      open: document.getElementById('s3MapOverlay').classList.contains('open'),
      mapRect: document.getElementById('slotMap').getBoundingClientRect().toJSON(),
      mapKeyVisible: getComputedStyle(document.querySelector('#slotMapWrap .mapKey')).display !== 'none'
    }));
    pops.push({kind: 'mapZoom', rect: zoom.mapRect, inside: zoom.open && zoom.mapRect.width >= 380 && zoom.mapKeyVisible});
    await page.screenshot({path: join(OUT, 'pop_mapzoom.png'), fullPage: false});
    await page.evaluate(() => window.__S3_LAYOUT_A.closeMap());
  }
  report.popAudits = pops;

  const laneStates = {};
  for (const algorithm of ['seq', 'near', 'score', 'AUTO']) {
    laneStates[algorithm] = await page.evaluate(value => { window.__S3_FILL_QA.setAlgorithm(value); return window.__S3_FILL_QA.seekBookmark(134); }, algorithm);
  }
  report.laneStates = laneStates;
  await page.close();

  report.finalHashes = Object.fromEntries(Object.entries(liveFiles).map(([key, path]) => [key, hash(path)]));
  const endpoint = Object.fromEntries(report.states.filter(item => item.name.startsWith('bookmark_')).map(item => [item.snapshot.managedCount, item.snapshot]));
  const bookmarkOverlays = Object.fromEntries(report.states.filter(item => item.name.startsWith('bookmark_')).map(item => [item.snapshot.managedCount, item.overlay]));
  const sameHashes = (left, right) => Object.keys(left).every(key => left[key] === right[key]);
  const assertions = {
    /* --- v7 基线断言(全保留) --- */
    localHashLockedSnapshot: sameHashes(initialHashes, snapshotHashes) && sameHashes(initialHashes, report.finalHashes),
    releaseEvidenceSnapshot: releaseEvidenceAudit.pass,
    noRuntimeErrors: report.runtimeErrors.length === 0 && report.consoleErrors.length === 0,
    viewportsInside: report.viewports.every(item => !item.clipped && !item.mapClipped && item.hudOverflow.length === 0 &&
      item.mapWrap.bottom <= item.height + .5 && item.map.bottom <= item.height + .5 &&
      item.bodyScroll.height <= item.height + 1 && item.bodyScroll.width <= item.width + 1),
    zeroEndpoint: endpoint[0]?.inventorySize === 0 && endpoint[0]?.totalUnavailable === 133 && endpoint[0]?.cargo.visible === false,
    fullEndpoint: endpoint[267]?.inventorySize === 267 && endpoint[267]?.totalUnavailable === 400 && endpoint[267]?.target === null && endpoint[267]?.cargo.visible === false,
    fullEndpointNoStalePath: endpoint[267]?.paths.length === 0,
    allBookmarksSameSource: [0, 67, 134, 201, 241, 267].every(count => endpoint[count]?.inventorySize === count && endpoint[count]?.semantic.inventoryMatchesManaged),
    sameSideTTopology: Object.values(endpoint).every(item => item.topology.sameSide && item.topology.parallel && item.topology.tJunction && item.topology.envelopeOverlapArea === 0),
    oneTargetNoDockOverlap: report.states.filter(item => item.overlay).every(item => item.snapshot.managedCount === 267 ? item.overlay.targetHidden : !item.overlay.targetHidden && item.overlay.overlap === 0),
    fourPathsVisible: report.states.filter(item => item.name.startsWith('event134_')).every(item => item.snapshot.paths.length === 4 && item.snapshot.paths.every(path => path.opacity >= .24)),
    sevenStepDisclosure: report.viewports.every(item => item.phaseSegmentCount === 7) && report.states.filter(item => item.name.startsWith('event134_')).every(item => item.snapshot.displayStepCount === 7 && item.snapshot.displayStepIndex >= 0 && item.snapshot.displayStepIndex < 7),
    displayStepTimingDerived: report.states.every(item => item.snapshot.timingAudit.eventCount === 801 &&
      item.snapshot.timingAudit.stepCount === 5607 && item.snapshot.timingAudit.maxSimSumError <= 1e-9 &&
      item.snapshot.timingAudit.maxPresentationFormulaError <= 1e-9 && item.snapshot.timingAudit.sourcePhaseCount === 4 &&
      item.snapshot.timingAudit.displayStepCount === 7 && item.snapshot.timingAudit.method === 'derived_from_four_trace_phases'),
    onlineLaneBinding: laneStates.seq.laneId === 'seq' && laneStates.near.laneId === 'near' && laneStates.score.laneId === 'score' && laneStates.AUTO.laneId === 'score',
    decisionEvidenceLinked: report.states.every(item => item.snapshot.decisionEvidence.selectedSlotMatches &&
      item.snapshot.decisionEvidence.top3.length >= 1 && item.snapshot.decisionEvidence.top3.length <= 3 &&
      item.snapshot.decisionEvidence.top3[0].rank === 1 && item.snapshot.decisionEvidence.top3[0].selected === true),
    scoreTop3Breakdown: laneStates.score.decisionEvidence.top3.length === 3 &&
      laneStates.score.decisionEvidence.top3.every(item => item.score_terms && Number.isFinite(item.score_terms.score_total)) &&
      laneStates.AUTO.decisionEvidence.top3.every(item => item.score_terms && Number.isFinite(item.score_terms.score_total)),
    scoreCollinearityDisclosed: laneStates.score.scorePolicyAudit.sharedLoadHeightFactor === true &&
      laneStates.score.scorePolicyAudit.disclosureVisible === true,
    nonScoreDoesNotFakeScore: laneStates.seq.decisionEvidence.top3.every(item => !('score_terms' in item)) &&
      laneStates.near.decisionEvidence.top3.every(item => !('score_terms' in item)),
    topologyTopReadable: report.topologyViewports.length === 3 && report.topologyViewports.every(item =>
      item.topologyProjection.allInside && item.topologyProjection.laneSeparationPx >= 30 &&
      item.topologyProjection.infeedLengthPx >= 80 && item.topologyProjection.outfeedLengthPx >= 80 &&
      item.topologyProjection.crossbarLengthPx >= 30),
    noDuplicateCurrentJob: report.states.every(item => item.snapshot.duplicateAudit.jobFactLeafCount <= 1),
    /* --- 方案 A 新增门(spec §5/§7) --- */
    forbiddenTermZero: report.layoutAudits.every(item => item.forbiddenBookmarkTermHits === 0) &&
      report.states.every(item => item.overlay ? item.overlay.layout.forbiddenBookmarkTermHits === 0 : true),
    capacityNodeTermUnique: report.layoutAudits.every(item => item.capacityNodeTermHits === 1),
    countGroupUnique: report.layoutAudits.every(item => item.managedCountVisibleHits <= 1),
    stepPurposeNotResident: report.layoutAudits.every(item => item.stepPurposeVisibleHits === 0),
    processGuideHidden: report.layoutAudits.every(item => item.processGuideHidden && item.taskLineHidden),
    layoutSkeleton: report.layoutAudits.every(item => item.topbarPresent && item.axisNodeCount === 6 && item.segmentsFocusable) &&
      report.viewports.every(item => item.axisAboveGl),
    placementComplete: report.layoutAudits.every(item => Object.values(item.placement).every(Boolean)),
    reserveBadgeCompact: report.viewports.every(item => item.badgeAreaShare < .15 && item.badge.width < item.gl.width * .6),
    axisFillProgress: bookmarkOverlays[134]?.axisFill === '50.19%' && bookmarkOverlays[267]?.axisFill === '100%' && bookmarkOverlays[0]?.axisFill === '0%',
    popsInsideViewport: report.popAudits.every(item => item.inside),
    /* --- 治理 A+B 门(0716 深审获批,docs/S3算法深审与治理方案_0716.md) --- */
    govStatsReordered: report.states.every(item => {
      const order = item.snapshot.narrativeAudit.statsSmallOrder;
      return order.length === 6 && order[0].includes('热门取货') && order[1].includes('重货均层') &&
        order[2].includes('能耗代理') && order[3].includes('期望取货') && order[4].includes('约束违规') && order[5].includes('三算法恒等');
    }),
    govConservedBadge: report.states.every(item => item.snapshot.narrativeAudit.conservedCellPresent &&
      item.snapshot.narrativeAudit.conservedValuesEqualAcrossLanes),
    govNoSmartRoutingTerm: report.states.every(item => item.snapshot.narrativeAudit.smartRoutingTermHits === 0) &&
      Object.values(laneStates).every(item => item.narrativeAudit.smartRoutingTermHits === 0 &&
        /默认策略 SCORE/.test(item.narrativeAudit.strategyOptionAutoText)),
    govExpectedRetrievalMechanism: report.states.every(item => item.snapshot.narrativeAudit.expectedRetrievalMechanismNoted),
    govDeltaBadges: laneStates.score.narrativeAudit.deltaBadgeCount === 4 && laneStates.AUTO.narrativeAudit.deltaBadgeCount === 4 &&
      laneStates.near.narrativeAudit.deltaBadgeCount === 4 && laneStates.seq.narrativeAudit.deltaBadgeCount === 0,
    govTieDisclosure: ['near', 'score', 'AUTO'].every(id => {
      const tie = laneStates[id].narrativeAudit.tieNote;
      return tie.top1TieSize > 1 ? tie.present && tie.isochroneNoted : !tie.present;
    }) && laneStates.near.narrativeAudit.tieNote.present === true &&
      laneStates.seq.narrativeAudit.tieNote.present === false,
    /* --- 0717 用户验收门:目标标牌锚定(标牌贴格或有可见引线指回,连线距离有界) --- */
    beaconAnchored: report.states.every(item => {
      const audit = item.snapshot.beaconAudit;
      return item.snapshot.target === null ? audit === null :
        Boolean(audit) && audit.leaderVisible === true && audit.dist < 480;
    })
  };
  report.assertions = assertions; report.pass = Object.values(assertions).every(Boolean);
  report.errors = Object.entries(assertions).filter(([, value]) => !value).map(([key]) => key);
} catch (error) {
  report.pass = false;
  report.errors.push(`qa_exception:${error.name}:${error.message}`);
} finally {
  await browser.close(); await new Promise(resolveClose => server.close(resolveClose));
}

writeFileSync(join(OUT, 'qa_report.json'), JSON.stringify(report, null, 2), 'utf8');
process.stdout.write(`${report.pass ? 'PASS' : 'FAIL'} ${Object.values(report.assertions || {}).filter(Boolean).length}/${Object.keys(report.assertions || {}).length}; ${join(OUT, 'qa_report.json')}\n`);
if (!report.pass) process.exitCode = 1;
