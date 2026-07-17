import { createRequire } from 'node:module';
import { createHash } from 'node:crypto';
import { createServer } from 'node:http';
import { fileURLToPath } from 'node:url';
import { dirname, extname, join, resolve, sep } from 'node:path';
import { copyFileSync, existsSync, mkdirSync, readFileSync, readdirSync, statSync, writeFileSync } from 'node:fs';

const HERE = dirname(fileURLToPath(import.meta.url));
const SHOWCASE = resolve(HERE, '..');
const SOURCE = resolve(process.argv[3] || join(SHOWCASE, 'src', 'archive_候选历史', '样张_S3_fill恢复候选.html'));
const RUNTIME = join(SHOWCASE, 'src', 's3_fill_candidate_runtime.js');
const STORE = join(SHOWCASE, 'src', 's3_fill_store.js');
const DATA_GATE = join(SHOWCASE, 'out', 's3_fill_data_gate');
const POINTER = join(DATA_GATE, 'latest.json');
const POINTER_RECORD = JSON.parse(readFileSync(POINTER, 'utf8'));
const EXPECTED_RELEASE = POINTER_RECORD.release_id;
const MANIFEST = resolve(DATA_GATE, POINTER_RECORD.manifest_resource);
if (!MANIFEST.startsWith(DATA_GATE + sep)) throw new Error('release manifest escapes data gate root');
const MANIFEST_RECORD = JSON.parse(readFileSync(MANIFEST, 'utf8'));
const REGISTRY = join(SHOWCASE, 'evidence', 's3_fill_release_registry.json');
const RELEASE_DIR = dirname(MANIFEST);
const AUDIT_NEAR = join(RELEASE_DIR, 'candidate_audit_online_near.jsonl.gz');
const AUDIT_SCORE = join(RELEASE_DIR, 'candidate_audit_online_score.jsonl.gz');
const AUDIT_SEQ = join(RELEASE_DIR, 'candidate_audit_online_seq.jsonl.gz');
const OUT = resolve(process.argv[2] || join(SHOWCASE, 'out', 's3_fill_candidate_qa_0716'));
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
  const packageRoot = join(pnpmRoot, packageDir, 'node_modules', 'playwright');
  playwright = createRequire(join(packageRoot, 'package.json'))('playwright');
}
const { chromium } = playwright;

const mime = {'.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.json': 'application/json; charset=utf-8'};
const hash = path => createHash('sha256').update(readFileSync(path)).digest('hex');
mkdirSync(OUT, {recursive: true});
const liveFiles = {
  source: SOURCE,
  runtime: RUNTIME,
  store: STORE,
  three: join(SHOWCASE, 'src', 'lib', 'three.min.js'),
  orbit: join(SHOWCASE, 'src', 'lib', 'OrbitControls.js'),
  pointer: POINTER,
  registry: REGISTRY,
  manifest: MANIFEST,
  auditNear: AUDIT_NEAR,
  auditScore: AUDIT_SCORE,
  auditSeq: AUDIT_SEQ
};
const initialHashes = Object.fromEntries(Object.entries(liveFiles).map(([key, path]) => [key, hash(path)]));
const snapshotId = createHash('sha256').update(JSON.stringify(initialHashes)).digest('hex').slice(0, 16);
const SNAPSHOT = join(OUT, `_local_hash_snapshot_${snapshotId}`);
const snapshotTargets = {
  source: join(SNAPSHOT, 'src', '样张_S3_fill恢复候选.html'),
  runtime: join(SNAPSHOT, 'src', 's3_fill_candidate_runtime.js'),
  store: join(SNAPSHOT, 'src', 's3_fill_store.js'),
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
    const target = resolve(SNAPSHOT, pathname || 'src/样张_S3_fill恢复候选.html');
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
const report = {schema: 's3-fill-candidate-qa-v3', source: SOURCE, expectedRelease: EXPECTED_RELEASE,
  snapshot: {id: snapshotId, root: SNAPSHOT, initialHashes, snapshotHashes,
    trustBoundary: releaseEvidenceAudit.trustBoundary}, releaseEvidenceAudit,
  runtimeErrors: [], consoleErrors: [], viewports: [], topologyViewports: [], states: [], pass: false, errors: []};

try {
  for (const [width, height] of [[1280, 720], [1600, 900], [1920, 1080]]) {
    const page = await browser.newPage({viewport: {width, height}, deviceScaleFactor: 1});
    page.on('pageerror', error => report.runtimeErrors.push(`${width}x${height}: ${error.message}`));
    page.on('console', message => { if (message.type() === 'error') report.consoleErrors.push(`${width}x${height}: ${message.text()}`); });
    await page.goto(`http://127.0.0.1:${port}/src/${encodeURIComponent('样张_S3_fill恢复候选.html')}`, {waitUntil: 'load'});
    await page.waitForFunction(expected => window.__S3_FILL_QA?.snapshot?.().releaseId === expected, EXPECTED_RELEASE, {timeout: 30000});
    const viewportAudit = await page.evaluate(() => {
      const rail = document.getElementById('workHud').getBoundingClientRect();
      const dock = document.getElementById('sceneDock').getBoundingClientRect();
      const gl = document.getElementById('gl').getBoundingClientRect();
      const controls = document.getElementById('runtimeControls').getBoundingClientRect();
      const bookmarks = document.getElementById('fillBookmarks').getBoundingClientRect();
      const mapWrap = document.getElementById('slotMapWrap').getBoundingClientRect();
      const map = document.getElementById('slotMap').getBoundingClientRect();
      const mapKey = document.querySelector('#slotMapWrap .mapKey').getBoundingClientRect();
      const phaseSegmentCount = document.querySelectorAll('#phaseSegments .phaseSeg').length;
      const hudOverflow = [...document.querySelectorAll('#workHud > *,#insightStack > *')].filter(element => {
        const style = getComputedStyle(element), rect = element.getBoundingClientRect();
        if (style.display === 'none' || style.visibility === 'hidden' || rect.width <= 0 || rect.height <= 0) return false;
        return rect.left < rail.left - .5 || rect.right > rail.right + .5 || rect.top < rail.top - .5 || rect.bottom > rail.bottom + .5 ||
          rect.left < -.5 || rect.right > innerWidth + .5 || rect.top < -.5 || rect.bottom > innerHeight + .5;
      }).map(element => ({id: element.id || element.className, rect: {...element.getBoundingClientRect().toJSON()}}));
      const narrowCritical = [...document.querySelectorAll('#insightStack b,#insightStack small,#insightStack span')].filter(element => {
        const style = getComputedStyle(element), rect = element.getBoundingClientRect(), text = element.textContent.trim();
        return style.display !== 'none' && style.visibility !== 'hidden' && text.length >= 2 && rect.height > 0 &&
          rect.width < 32 && rect.height > rect.width * 1.35;
      }).map(element => element.textContent.trim());
      return {rail: {...rail.toJSON()}, dock: {...dock.toJSON()}, gl: {...gl.toJSON()}, controls: {...controls.toJSON()}, bookmarks: {...bookmarks.toJSON()},
        map: {...map.toJSON()}, mapWrap: {...mapWrap.toJSON()}, mapKey: {...mapKey.toJSON()},
        bodyScroll: {width: document.documentElement.scrollWidth, height: document.documentElement.scrollHeight},
        clipped: rail.bottom > innerHeight + .5 || dock.bottom > innerHeight + .5 || gl.width < 300 || gl.height < 300,
        mapClipped: map.left < mapWrap.left - .5 || map.right > mapWrap.right + .5 || map.top < mapWrap.top - .5 || map.bottom > mapKey.top + .5,
        phaseSegmentCount, narrowCritical, hudOverflow, overlap: !(controls.bottom <= bookmarks.top + .5 || bookmarks.bottom <= controls.top + .5)};
    });
    report.viewports.push({width, height, ...viewportAudit});
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
  await page.goto(`http://127.0.0.1:${port}/src/${encodeURIComponent('样张_S3_fill恢复候选.html')}`, {waitUntil: 'load'});
  await page.waitForFunction(expected => window.__S3_FILL_QA?.snapshot?.().releaseId === expected, EXPECTED_RELEASE, {timeout: 30000});

  for (const count of [0, 67, 134, 201, 241, 267]) {
    const value = await page.evaluate(countValue => window.__S3_FILL_QA.seekBookmark(countValue), count);
    const overlay = await page.evaluate(() => {
      const beacon = document.getElementById('targetBeacon'), dock = document.getElementById('sceneDock');
      const b = beacon.getBoundingClientRect(), d = dock.getBoundingClientRect();
      const overlap = Math.max(0, Math.min(b.right, d.right) - Math.max(b.left, d.left)) * Math.max(0, Math.min(b.bottom, d.bottom) - Math.max(b.top, d.top));
      return {targetHidden: beacon.hidden, target: {...b.toJSON()}, dock: {...d.toJSON()}, overlap};
    });
    report.states.push({name: `bookmark_${count}`, snapshot: value, overlay});
    await page.screenshot({path: join(OUT, `bookmark_${String(count).padStart(3, '0')}.png`), fullPage: false});
  }

  for (const [operation, progress] of [['INFEED_HANDOFF', .55], ['LADEN_TRAVEL', .55], ['STORE_HANDLE', .50], ['STORE_HANDLE', .72], ['EMPTY_RETURN', .55]]) {
    const value = await page.evaluate(({operation, progress}) => window.__S3_FILL_QA.seekEvent(133, operation, progress), {operation, progress});
    report.states.push({name: `event134_${operation}_${progress}`, snapshot: value});
    await page.screenshot({path: join(OUT, `event134_${operation}_${String(progress).replace('.', '_')}.png`), fullPage: false});
  }

  const laneStates = {};
  for (const algorithm of ['seq', 'near', 'score', 'AUTO']) {
    laneStates[algorithm] = await page.evaluate(value => { window.__S3_FILL_QA.setAlgorithm(value); return window.__S3_FILL_QA.seekBookmark(134); }, algorithm);
  }
  report.laneStates = laneStates;
  await page.close();

  report.finalHashes = Object.fromEntries(Object.entries(liveFiles).map(([key, path]) => [key, hash(path)]));
  const endpoint = Object.fromEntries(report.states.filter(item => item.name.startsWith('bookmark_')).map(item => [item.snapshot.managedCount, item.snapshot]));
  const sameHashes = (left, right) => Object.keys(left).every(key => left[key] === right[key]);
  const assertions = {
    localHashLockedSnapshot: sameHashes(initialHashes, snapshotHashes) && sameHashes(initialHashes, report.finalHashes),
    releaseEvidenceSnapshot: releaseEvidenceAudit.pass,
    noRuntimeErrors: report.runtimeErrors.length === 0 && report.consoleErrors.length === 0,
    viewportsInside: report.viewports.every(item => !item.clipped && !item.mapClipped && !item.overlap && item.narrowCritical.length === 0 &&
      item.hudOverflow.length === 0 && item.mapWrap.bottom <= item.height + .5 && item.map.bottom <= item.height + .5 &&
      item.mapKey.bottom <= item.height + .5 && item.bodyScroll.height <= item.height + 1 && item.bodyScroll.width <= item.width + 1),
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
      item.snapshot.timingAudit.maxPresentationFormulaError <= 1e-9 && item.snapshot.timingAudit.minSimStep > 0 &&
      item.snapshot.timingAudit.minPresentationStep > 0 && item.snapshot.timingAudit.sourcePhaseCount === 4 &&
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
    noDuplicateCurrentJob: report.states.every(item => item.snapshot.duplicateAudit.jobFactLeafCount <= 1)
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
