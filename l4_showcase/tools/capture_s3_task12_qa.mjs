import { createRequire } from 'node:module';
import { createHash } from 'node:crypto';
import { createServer } from 'node:http';
import { fileURLToPath } from 'node:url';
import { dirname, extname, join, resolve, sep } from 'node:path';
import { existsSync, mkdirSync, readFileSync, readdirSync, statSync, writeFileSync } from 'node:fs';

const QA_SCRIPT = fileURLToPath(import.meta.url);
const HERE = dirname(QA_SCRIPT);
const SHOWCASE = resolve(HERE, '..');
const SOURCE = join(SHOWCASE, 'src', 'archive_候选历史', '样张_S3_三方向候选.html');
const RUNTIME = join(SHOWCASE, 'src', 's3_ac_runtime.js');
const TRACE_STORE = join(SHOWCASE, 'src', 's3_trace_store.js');
const THREE_LIB = join(SHOWCASE, 'src', 'lib', 'three.min.js');
const ORBIT_LIB = join(SHOWCASE, 'src', 'lib', 'OrbitControls.js');
const RUNTIME_TEST = join(SHOWCASE, 'tools', 'test_s3_runtime_contract.mjs');
const TRACE_MANIFEST = join(SHOWCASE, 'out', 's3_trace_manifest.json');
const COMPARISON_EVIDENCE = join(SHOWCASE, 'out', 's1_comparison_evidence.js');
const COMPARISON_CANONICAL = join(SHOWCASE, 'out', 's1_comparison_evidence.canonical.json');
const COMPARISON_GENERATOR = join(SHOWCASE, 'tools', 'generate_s1_comparison_evidence.py');
const OUT = resolve(process.argv[2] || join(SHOWCASE, 'out', 's3_task12_qa_0715'));
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

const VIEWPORTS = [[1280, 720], [1366, 768], [1600, 900], [1920, 1080]];
const STATES = [
  {name: '01_infeed_entry', query: ['AUTO', 'skew'], seek: [20, 'LOAD_IN', .12]},
  {name: '02_infeed_handoff', query: ['AUTO', 'skew'], seek: [20, 'LOAD_IN', .86]},
  {name: '03_store', query: ['AUTO', 'skew'], seek: [55, 'STORE_HANDLE', .64]},
  {name: '04_retrieve', query: ['AUTO', 'skew'], seek: [20, 'RETRIEVE_HANDLE', .64]},
  {name: '05_outbound_return', query: ['AUTO', 'skew'], seek: [20, 'OUTBOUND_TRAVEL', .80]},
  {name: '06_scan', query: ['AUTO', 'skew'], seek: [20, 'SCAN_EXIT', .50]},
  {name: '07_exit_mask', query: ['AUTO', 'skew'], seek: [20, 'SCAN_EXIT', .72]},
  {name: '08_algorithm_seq', query: ['seq', 'skew'], seek: [20, 'LOAD_IN', .50]},
  {name: '09_profile_heavy', query: ['AUTO', 'heavy'], seek: [20, 'LOAD_IN', .50]},
  {name: '10_camera_moved_paused', query: ['AUTO', 'skew'], seek: [55, 'STORE_HANDLE', .64], camera: 'move'},
  {name: '11_camera_reset', query: ['AUTO', 'skew'], seek: [55, 'STORE_HANDLE', .64], camera: 'reset'},
  {name: '12_io_closeup_qa', query: ['AUTO', 'skew'], seek: [20, 'SCAN_EXIT', .72], camera: 'ioCloseup', qaOnly: true},
  {name: '13_consumed_receipt', query: ['AUTO', 'skew'], seek: [20, 'SCAN_EXIT', .99]},
  {name: '14_s1_same_scenario_e02', query: ['AUTO', 'skew'], seek: [20, 'LOAD_IN', .50], comparison: {axis: 'scenario', key: 'E02'}},
  {name: '15_s1_same_mode_auto', query: ['AUTO', 'skew'], seek: [20, 'LOAD_IN', .50], comparison: {axis: 'mode', key: 'AUTO'}},
  {name: '16_s1_e15_downgraded', query: ['AUTO', 'heavy'], seek: [20, 'LOAD_IN', .50], comparison: {axis: 'scenario', key: 'E15'}},
  {name: '17_keyboard_focus_dialog', query: ['AUTO', 'skew'], seek: [20, 'LOAD_IN', .50], comparison: {axis: 'mode', key: 'AUTO'}, keyboardFocus: true},
  {name: '18_metric_tooltip_focus', query: ['AUTO', 'skew'], seek: [20, 'STORE_HANDLE', .64], tooltipIndex: 2},
  {name: '19_fault_recovery', query: ['AUTO', 'skew'], faultIndex: 0},
  {name: '20_long_inbound_midpoint', query: ['AUTO', 'skew'], seek: [12, 'INBOUND_TRAVEL', .50]},
  {name: '21_long_outbound_midpoint', query: ['AUTO', 'skew'], seek: [78, 'OUTBOUND_TRAVEL', .50]}
];

const sha256 = bytes => createHash('sha256').update(bytes).digest('hex').toUpperCase();
const fileHash = path => sha256(readFileSync(path));
/* InstancedMesh 矩阵落入 WebGL Float32；1e-7 m 仍小于 0.1 微米，只吸收表示误差而不掩盖可见缝隙。 */
const GEOMETRY_FLOAT_EPS = 1e-7;
const pngSize = bytes => {
  if (bytes.length < 24 || bytes.toString('ascii', 1, 4) !== 'PNG') throw new Error('not a PNG');
  return [bytes.readUInt32BE(16), bytes.readUInt32BE(20)];
};
const maxCameraError = (a, b) => Math.max(
  ...a.position.map((value, index) => Math.abs(value - b.position[index])),
  ...a.target.map((value, index) => Math.abs(value - b.target[index])),
  Math.abs(a.fov - b.fov), Math.abs(a.zoom - b.zoom)
);

function startStaticServer() {
  const mime = new Map([
    ['.html', 'text/html; charset=utf-8'], ['.js', 'text/javascript; charset=utf-8'],
    ['.json', 'application/json; charset=utf-8'], ['.css', 'text/css; charset=utf-8']
  ]);
  return new Promise((resolveServer, rejectServer) => {
    const server = createServer((req, res) => {
      try {
        const pathname = decodeURIComponent(new URL(req.url, 'http://127.0.0.1').pathname);
        const file = resolve(SHOWCASE, pathname.replace(/^\/+/, ''));
        if (!(file === SHOWCASE || file.startsWith(SHOWCASE + sep)) || !existsSync(file) || statSync(file).isDirectory()) {
          res.writeHead(404, {'Content-Type': 'text/plain; charset=utf-8'}); res.end('Not found'); return;
        }
        res.writeHead(200, {'Content-Type': mime.get(extname(file).toLowerCase()) || 'application/octet-stream', 'Cache-Control': 'no-store'});
        res.end(readFileSync(file));
      } catch (error) {
        res.writeHead(500, {'Content-Type': 'text/plain; charset=utf-8'}); res.end(String(error));
      }
    });
    server.once('error', rejectServer);
    server.listen(0, '127.0.0.1', () => resolveServer({
      server,
      url: `http://127.0.0.1:${server.address().port}/src/${encodeURIComponent('样张_S3_三方向候选.html')}`
    }));
  });
}

async function twoFrames(page) {
  await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
}

async function setQuery(page, strategy, profile) {
  const current = await page.evaluate(() => ({strategy: strategySelect.value, profile: profileSelect.value}));
  if (current.profile !== profile) await page.selectOption('#profileSelect', profile);
  if (current.strategy !== strategy) await page.selectOption('#strategySelect', strategy);
  await page.waitForFunction(([wantedStrategy, wantedProfile]) => {
    const snapshot = window.__S3_QA?.snapshot?.();
    return snapshot && !snapshot.loading && snapshot.query?.strategy_mode === wantedStrategy && snapshot.query?.profile === wantedProfile;
  }, [strategy, profile]);
}

async function dragCamera(page) {
  const box = await page.locator('#gl canvas').boundingBox();
  if (!box) throw new Error('WebGL canvas bounding box missing');
  const x = box.x + box.width * .63, y = box.y + box.height * .45;
  await page.mouse.move(x, y); await page.mouse.down();
  await page.mouse.move(x + 105, y - 42, {steps: 8}); await page.mouse.up();
  await twoFrames(page);
}

async function configureComparison(page, specification) {
  if (await page.locator('#comparisonLab').isVisible()) await page.locator('#closeComparisonLab').click();
  if (!specification) return;
  await page.locator('#openComparisonLab').click();
  if (specification.axis === 'mode') await page.locator('#comparisonModeTab').click();
  else await page.locator('#comparisonScenarioTab').click();
  await page.locator('#comparisonToolbar select').selectOption(specification.key);
  await twoFrames(page);
}

async function captureAudit(page) {
  return page.evaluate(() => {
    const snapshot = window.__S3_QA.snapshot();
    const rect = element => {
      if (!element || element.hidden) return null;
      const r = element.getBoundingClientRect();
      return {left: r.left, top: r.top, right: r.right, bottom: r.bottom, width: r.width, height: r.height,
        inside: r.left >= -.5 && r.top >= -.5 && r.right <= innerWidth + .5 && r.bottom <= innerHeight + .5};
    };
    const fixed = ['sceneDock', 'faultStateBanner', 'targetBeacon']
      .map(id => ({id, rect: rect(document.getElementById(id))})).filter(item => item.rect);
    const area = (a, b) => Math.max(0, Math.min(a.right, b.right) - Math.max(a.left, b.left)) *
      Math.max(0, Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top));
    const overlaps = [];
    for (let i = 0; i < fixed.length; i += 1) for (let j = i + 1; j < fixed.length; j += 1) {
      const value = area(fixed[i].rect, fixed[j].rect);
      if (value > 1) overlaps.push({a: fixed[i].id, b: fixed[j].id, area: value});
    }
    const leaderPairs = [['targetBeacon', 'targetLeader']];
    const orphanLeaders = leaderPairs.filter(([labelId, lineId]) => {
      const label = document.getElementById(labelId), line = document.getElementById(lineId);
      return (!label.hidden) !== (getComputedStyle(line).display !== 'none');
    });
    const rail = document.getElementById('workHud');
    const dockElement = document.getElementById('sceneDock'), dockRect = rect(dockElement);
    const dockChildren = ['sceneCaption', 'sceneTelemetry', 'sceneTools']
      .map(id => ({id, rect: rect(document.getElementById(id))}));
    const dockChildOverlaps = [];
    for (let i = 0; i < dockChildren.length; i += 1) for (let j = i + 1; j < dockChildren.length; j += 1) {
      const value = area(dockChildren[i].rect, dockChildren[j].rect);
      if (value > 1) dockChildOverlaps.push({a: dockChildren[i].id, b: dockChildren[j].id, area: value});
    }
    const dockText = dockElement.innerText.replace(/\s+/g, ' ').trim();
    const pageText = document.body.innerText.replace(/\s+/g, ' ');
    const literalCount = value => pageText.split(value).length - 1;
    const bannedDecorativeEnglish = ['MOTION TELEMETRY', 'SCENE CONTROL', 'LIVE AXIS', 'OPERATOR CONSOLE', 'VERIFIED SIM TRACE']
      .filter(value => dockText.includes(value));
    const sceneActionText = document.getElementById('sceneActionText').textContent.trim();
    const sceneActionMeta = document.getElementById('sceneActionMeta').textContent.trim();
    const cargoMeta = document.getElementById('sceneCargoMeta')?.textContent.trim() || '';
    const cargoName = `${sceneActionText} ${cargoMeta}`.match(/G\d+/)?.[0] || null;
    const dock = {
      rect: dockRect, children: dockChildren, childOverlaps: dockChildOverlaps, text: dockText,
      childrenInside: dockChildren.every(item => item.rect && item.rect.left >= dockRect.left - .5 && item.rect.top >= dockRect.top - .5 &&
        item.rect.right <= dockRect.right + .5 && item.rect.bottom <= dockRect.bottom + .5),
      bannedDecorativeEnglish, formulaOccurrences: literalCount('(列 + 层) mod 3 = 0'),
      reserveCountOccurrences: literalCount('133 / 400'), action: {text: sceneActionText, meta: sceneActionMeta, cargoName,
        clear: sceneActionText.length >= 4 && sceneActionMeta.includes('缩时演示') && sceneActionMeta.includes('SIM') &&
          (cargoMeta.includes('SIM') || cargoMeta.includes('展示补段')),
        cargoAligned: !snapshot.renderer.cargo.visible || Boolean(cargoName && sceneActionText.includes(cargoName))}
    };
    const comparisonLab = document.getElementById('comparisonLab'), comparisonPanel = comparisonLab.querySelector('.comparisonPanel');
    const comparisonTable = document.getElementById('comparisonTable'), comparisonFoot = document.getElementById('comparisonFoot');
    const comparison = {
      ...snapshot.comparison,
      lab: rect(comparisonLab), panel: rect(comparisonPanel), table: rect(comparisonTable), foot: rect(comparisonFoot),
      panelOverflow: [comparisonPanel.scrollWidth, comparisonPanel.clientWidth, comparisonPanel.scrollHeight, comparisonPanel.clientHeight],
      tableOverflow: [comparisonTable.scrollWidth, comparisonTable.clientWidth, comparisonTable.scrollHeight, comparisonTable.clientHeight],
      e15Rows: comparisonTable.querySelectorAll('.comparisonBodyRow[data-extended="true"]').length,
      selectedTab: comparisonLab.querySelector('.comparisonTabs button[aria-selected="true"]')?.id || null,
      summaryText: document.getElementById('comparisonAutoSummary').textContent.replace(/\s+/g, ' ').trim(),
      footText: comparisonFoot.textContent.replace(/\s+/g, ' ').trim()
    };
    const mini = document.getElementById('comparisonMini'), miniTitle = mini.querySelector('.comparisonMiniHead b'), miniScope = mini.querySelector('.comparisonMiniHead span');
    const criticalText = Array.from(document.querySelectorAll('.comparisonBodyRow small,#comparisonFoot,.comparisonHeader>div,#comparisonToolbar .matrixScope'))
      .filter(element => element.getClientRects().length).map(element => Number.parseFloat(getComputedStyle(element).fontSize));
    comparison.miniDisclosure = {title: miniTitle.textContent.trim(), scope: miniScope.textContent.replace(/\s+/g, ' ').trim(),
      button: document.getElementById('openComparisonLabMini').textContent.trim()};
    comparison.criticalFontMinPx = criticalText.length ? Math.min(...criticalText) : null;
    const openTooltip = document.querySelector('.metricHelp.is-open .tipBubble');
    const tooltip = openTooltip ? {rect: rect(openTooltip), role: openTooltip.getAttribute('role'), text: openTooltip.textContent.trim(),
      ownerExpanded: openTooltip.closest('.metricHelp')?.getAttribute('aria-expanded')} : null;
    const pathPlan = snapshot.renderer.pathPlan || [];
    const pointDistance = (a, b) => a && b ? Math.hypot(a.x - b.x, a.y - b.y, a.z - b.z) : Infinity;
    const continuityPairs = [[0,1],[1,2],[4,5],[5,6]].map(([left,right]) => ({left, right,
      distance: pointDistance(pathPlan[left]?.end, pathPlan[right]?.start)}));
    const mapWrapElement = document.getElementById('slotMapWrap'), mapCanvasElement = document.getElementById('slotMap'),
      mapKeyElement = mapWrapElement.querySelector('.mapKey');
    const mapWrapRect = rect(mapWrapElement), mapCanvasRect = rect(mapCanvasElement), mapKeyRect = rect(mapKeyElement);
    const mapLayout = {wrap: mapWrapRect, canvas: mapCanvasRect, key: mapKeyRect,
      aspectError: Math.abs(mapCanvasRect.width - mapCanvasRect.height), unusedBottom: mapWrapRect.bottom - mapKeyRect.bottom};
    const phaseSegments = Array.from(document.querySelectorAll('#phaseSegments .phaseSeg')),
      phaseTimeParts = Array.from(document.querySelectorAll('#phaseTimeScale .phaseTimePart'));
    const phaseLayout = {segments: phaseSegments.map(element => ({text: element.textContent.replace(/\s+/g, ' ').trim(),
        duration: element.querySelector('.phaseDuration')?.textContent.trim(), fontPx: Number.parseFloat(getComputedStyle(element).fontSize)})),
      timePartPercentages: phaseTimeParts.map(element => Number.parseFloat(element.style.width) || 0),
      current: document.getElementById('phaseNow').textContent.trim(), clock: document.getElementById('phaseClock').textContent.trim()};
    return {
      viewport: [innerWidth, innerHeight], scroll: [document.documentElement.scrollWidth, document.documentElement.scrollHeight],
      rail: {clientHeight: rail.clientHeight, scrollHeight: rail.scrollHeight}, fixed, overlaps, orphanLeaders, dock,
      traceId: snapshot.traceId, query: snapshot.query, checkpoint: snapshot.checkpoint, runtimeErrors: snapshot.runtimeErrors,
      playback: snapshot.playback, camera: snapshot.renderer.camera, cargo: snapshot.renderer.cargo,
      stockVisual: snapshot.renderer.stockVisual, pathPlan, pathContinuity: continuityPairs, timing: snapshot.renderer.timing,
      geometry: window.__S3_GEOMETRY_AUDIT, mapLayout, phaseLayout,
      labels: snapshot.renderer.labels, stationLabels: snapshot.renderer.stationLabels,
      composition: snapshot.renderer.composition,
      ownership: {unique: snapshot.renderer.ownership?.unique, duplicates: snapshot.renderer.ownership?.duplicates || [],
        records: snapshot.renderer.ownership?.records || []},
      collisions: snapshot.renderer.collisions, topology: snapshot.renderer.topology, comparison, tooltip,
      fault: {visible: !document.getElementById('faultStateBanner').hidden, text: document.getElementById('faultStateBanner').textContent.replace(/\s+/g, ' ').trim(),
        phaseName: snapshot.renderer.phaseName, faulted: snapshot.renderer.faulted, faultIndex: snapshot.renderer.faultIndex, checkpoint: snapshot.checkpoint}
    };
  });
}

async function runCameraExtremesAudit(page, outDir) {
  const poses = [
    {name: 'side-limit-left', position: [-33.3, -20.1, 24.65], target: [9.8, 0, 9.2], fov: 36},
    {name: 'side-limit-right', position: [52.3, -19.7, 26.9], target: [10, 0, 9.5], fov: 36},
    {name: 'wide-high', position: [42, -42, 31], target: [10, -.5, 8.8], fov: 38},
    {name: 'io-biased', position: [34, -38, 25], target: [6.5, -1.8, 7.3], fov: 38}
  ];
  const results = [];
  await setQuery(page, 'AUTO', 'skew');
  await page.evaluate(() => window.__S3_QA.seek(20, 'SCAN_EXIT', .72));
  for (const pose of poses) {
    await page.evaluate(({position, target, fov}) => {
      camera.position.set(...position); controls.target.set(...target); camera.fov = fov;
      camera.updateProjectionMatrix(); controls.update(); controls.dispatchEvent({type: 'change'});
    }, pose);
    await twoFrames(page);
    const audit = await captureAudit(page);
    const filename = `1280x720_qa_extreme_${pose.name}.png`, path = join(outDir, filename);
    await page.screenshot({path, type: 'png', animations: 'disabled'});
    const bytes = readFileSync(path), dimensions = pngSize(bytes);
    results.push({name: pose.name, pose, camera: audit.camera, labels: audit.labels, stationLabels: audit.stationLabels,
      composition: audit.composition, dock: audit.dock,
      fixedOverlaps: audit.overlaps, fixedInside: audit.fixed.every(item => item.rect.inside), orphanLeaders: audit.orphanLeaders,
      capture: {file: filename, file_sha256: sha256(bytes), dimensions}});
  }
  await page.evaluate(() => window.__S3_QA.resetCamera()); await twoFrames(page);
  return results;
}

async function runPlaybackAudit(page) {
  await setQuery(page, 'AUTO', 'skew');
  await page.evaluate(() => window.__S3_QA.seek(20, 'STORE_HANDLE', .64));
  const read = () => page.evaluate(() => {
    const s = window.__S3_QA.snapshot();
    return {traceId: s.traceId, checkpoint: s.checkpoint, inventory: s.renderer.inventoryGids,
      ownership: s.renderer.ownership.records, task: taskPrimary.textContent, stats: traceStats.textContent.replace(/\s+/g, ' ').trim(),
      playback: s.playback};
  });
  const baseline = await read();
  await page.locator('#playbackSpeed').fill('0.25'); const slow = await read();
  await page.locator('#playbackSpeed').fill('2'); const fast = await read();
  await page.locator('#playbackSpeed').fill('1');
  const invariant = value => JSON.stringify({...value, playback: undefined}) === JSON.stringify({...baseline, playback: undefined});
  return {baseline, slow, fast, slowInvariant: invariant(slow), fastInvariant: invariant(fast)};
}

async function runTimingAudit(page) {
  return page.evaluate(() => {
    const qa = window.__S3_QA;
    const operations = ['LOAD_IN','INBOUND_TRAVEL','STORE_HANDLE','LINK_TRAVEL','RETRIEVE_HANDLE','OUTBOUND_TRAVEL','SCAN_EXIT'];
    const byOperation = Object.fromEntries(operations.map(operation => [operation, []]));
    for (let cycle = 0; cycle < 100; cycle += 1) for (const operation of operations) {
      qa.seek(cycle, operation, .5);
      const timing = qa.snapshot().renderer.timing;
      byOperation[operation].push({cycle, simDurationS: timing.simDurationS,
        presentationDurationS: timing.presentationDurationS, wallSecondsAt1x: timing.wallSecondsAt1x});
    }
    const quantile = (values, q) => {
      const sorted = values.slice().sort((a,b) => a-b), index = (sorted.length - 1) * q;
      const lo = Math.floor(index), hi = Math.ceil(index), u = index - lo;
      return sorted[lo] * (1-u) + sorted[hi] * u;
    };
    const summary = Object.fromEntries(operations.map(operation => {
      const rows = byOperation[operation], sim = rows.map(row => row.simDurationS), wall = rows.map(row => row.wallSecondsAt1x);
      return [operation, {samples: rows.length,
        sim: {min: Math.min(...sim), p50: quantile(sim,.5), p95: quantile(sim,.95), max: Math.max(...sim)},
        wall: {min: Math.min(...wall), p50: quantile(wall,.5), p95: quantile(wall,.95), max: Math.max(...wall)}}];
    }));
    const monotoneFailures = [];
    for (const operation of ['INBOUND_TRAVEL','LINK_TRAVEL','OUTBOUND_TRAVEL']) {
      const rows = byOperation[operation].slice().sort((a,b) => a.simDurationS-b.simDurationS || a.presentationDurationS-b.presentationDurationS);
      for (let index=1;index<rows.length;index+=1) if (rows[index].simDurationS > rows[index-1].simDurationS + 1e-9 &&
          rows[index].presentationDurationS + 1e-9 < rows[index-1].presentationDurationS) {
        monotoneFailures.push({operation, previous: rows[index-1], current: rows[index]});
      }
    }
    const longestLoadedWall = Math.max(summary.INBOUND_TRAVEL.wall.max, summary.OUTBOUND_TRAVEL.wall.max);
    return {summary, monotoneFailures, longestLoadedWall,
      maximumEntryWall: summary.LOAD_IN.wall.max, maximumScanWall: summary.SCAN_EXIT.wall.max,
      invertedPriority: longestLoadedWall + 1e-9 < Math.max(summary.LOAD_IN.wall.max, summary.SCAN_EXIT.wall.max)};
  });
}

async function runHoverAudit(page) {
  const button = page.locator('#traceStats .metricHelp').nth(2);
  await button.hover(); await page.waitForTimeout(170);
  const result = await page.evaluate(() => {
    const item = document.querySelectorAll('#traceStats .metricHelp')[2], tip = item.querySelector('.tipBubble');
    return {expanded: item.getAttribute('aria-expanded'), visibility: getComputedStyle(tip).visibility,
      opacity: getComputedStyle(tip).opacity, text: tip.textContent};
  });
  const canvas = await page.locator('#gl canvas').boundingBox();
  if (canvas) await page.mouse.move(canvas.x + canvas.width * .75, canvas.y + canvas.height * .2);
  await page.waitForTimeout(170);
  return result;
}

async function runAccessibilityAudit(page) {
  await configureComparison(page, null); await setQuery(page, 'AUTO', 'skew');
  const readTargets = () => page.evaluate(() => {
    const controls = Array.from(document.querySelectorAll('button,select,input,summary,[href],[tabindex]:not([tabindex="-1"])'))
      .filter(element => !element.disabled && !element.hidden && element.getClientRects().length > 0 && !element.closest('[hidden]'));
    const measured = controls.map(element => { const rect = element.getBoundingClientRect(); return {
      id: element.id || element.tagName, width: rect.width, height: rect.height,
      label: element.getAttribute('aria-label') || element.textContent.replace(/\s+/g, ' ').trim().slice(0, 60)
    }; });
    const ids = Array.from(document.querySelectorAll('[id]')).map(element => element.id);
    return {count: measured.length, undersized: measured.filter(item => item.width < 23.5 || item.height < 23.5),
      duplicateIds: ids.filter((id, index) => ids.indexOf(id) !== index)};
  });
  const normalTargets = await readTargets();

  await page.locator('#openComparisonLab').focus(); await page.locator('#openComparisonLab').click(); await twoFrames(page);
  const opened = await page.evaluate(() => { const dialog = document.getElementById('comparisonLab'); return {
    active: document.activeElement.id, snapshot: window.__S3_QA.snapshot().comparison,
    backgroundInert: document.querySelectorAll('[inert]').length,
    dialogModal: dialog.getAttribute('aria-modal'), describedBy: dialog.getAttribute('aria-describedby')}; });
  const dialogTargets = await readTargets();
  await page.keyboard.press('Shift+Tab');
  const wrappedLast = await page.evaluate(() => ({id: document.activeElement.id, inside: document.getElementById('comparisonLab').contains(document.activeElement)}));
  await page.keyboard.press('Tab'); const wrappedFirst = await page.evaluate(() => document.activeElement.id);
  await page.locator('#comparisonScenarioTab').focus(); await page.keyboard.press('ArrowRight');
  const arrowNavigation = await page.evaluate(() => ({active: document.activeElement.id,
    selectedScenario: document.getElementById('comparisonScenarioTab').getAttribute('aria-selected'),
    selectedMode: document.getElementById('comparisonModeTab').getAttribute('aria-selected'),
    scenarioTabIndex: document.getElementById('comparisonScenarioTab').tabIndex,
    modeTabIndex: document.getElementById('comparisonModeTab').tabIndex,
    snapshot: window.__S3_QA.snapshot().comparison}));
  await page.keyboard.press('Escape');
  const closed = await page.evaluate(() => ({hidden: document.getElementById('comparisonLab').hidden, active: document.activeElement.id,
    inertRemaining: document.querySelectorAll('[inert]').length, snapshot: window.__S3_QA.snapshot().comparison}));

  const metric = page.locator('#traceStats .metricHelp').nth(2); await metric.focus();
  const tooltipFocused = await page.evaluate(() => { const button = document.querySelectorAll('#traceStats .metricHelp')[2], tip = button.querySelector('.tipBubble');
    return {active: document.activeElement === button, expanded: button.getAttribute('aria-expanded'), role: tip.getAttribute('role'),
      visible: getComputedStyle(tip).visibility, describedBy: button.getAttribute('aria-describedby') === tip.id}; });
  await page.keyboard.press('Escape');
  const tooltipClosed = await page.evaluate(() => { const button = document.querySelectorAll('#traceStats .metricHelp')[2];
    return {expanded: button.getAttribute('aria-expanded'), active: document.activeElement === button}; });

  await page.evaluate(() => window.__S3_QA.select({tier: 3, profile: 'skew', strategy_mode: 'missing'}));
  await page.locator('#traceErrorHost').waitFor({state: 'visible'});
  const failed = await page.evaluate(() => { const host = document.getElementById('traceErrorHost'); return {
    role: host.getAttribute('role'), live: host.getAttribute('aria-live'), atomic: host.getAttribute('aria-atomic'),
    retryButtons: host.querySelectorAll('button').length, text: host.textContent.replace(/\s+/g, ' ').trim(),
    controlsBusy: document.getElementById('runtimeControls').getAttribute('aria-busy')}; });
  await page.evaluate(() => window.__S3_QA.select({tier: 3, profile: 'skew', strategy_mode: 'near'}));
  await page.waitForFunction(() => window.__S3_QA.snapshot().traceId === 't3_skew_near' &&
    document.getElementById('traceErrorHost').hidden && document.getElementById('runtimeControls').getAttribute('aria-busy') === 'false');
  const recovered = await page.evaluate(() => ({errorHidden: document.getElementById('traceErrorHost').hidden,
    controlsBusy: document.getElementById('runtimeControls').getAttribute('aria-busy'),
    statusRole: document.getElementById('traceLoadState').getAttribute('role'),
    statusLive: document.getElementById('traceLoadState').getAttribute('aria-live')}));
  await setQuery(page, 'AUTO', 'skew');

  await page.emulateMedia({reducedMotion: 'reduce'});
  const reducedMotion = await page.evaluate(() => ({
    cycleReset: getComputedStyle(document.getElementById('cycleReset')).transitionDuration,
    actionBadge: getComputedStyle(document.getElementById('actionBadge')).transitionDuration}));
  await page.emulateMedia({reducedMotion: 'no-preference'});
  return {normalTargets, dialogTargets, opened, wrappedLast, wrappedFirst, arrowNavigation, closed,
    tooltipFocused, tooltipClosed, failed, recovered, reducedMotion};
}

async function runPerformanceAudit(page, readyMs) {
  await configureComparison(page, null); await setQuery(page, 'AUTO', 'skew');
  await page.evaluate(() => window.__S3_QA.seek(20, 'STORE_HANDLE', .64)); await twoFrames(page);
  const cdp = await page.context().newCDPSession(page);
  const forceMajorGc = async () => {
    await cdp.send('HeapProfiler.collectGarbage');
    await page.waitForTimeout(25);
  };
  const collect = () => page.evaluate(() => {
    renderer.render(scene, camera);
    const snapshot = window.__S3_QA.snapshot(), info = renderer.info;
    return {domNodes: document.querySelectorAll('*').length, heapBytes: performance.memory?.usedJSHeapSize ?? null,
      renderer: {calls: info.render.calls, triangles: info.render.triangles, lines: info.render.lines, points: info.render.points,
        geometries: info.memory.geometries, textures: info.memory.textures, programs: info.programs?.length ?? null},
      runtime: {sceneMeshes: snapshot.renderer.sceneMeshes, inventorySize: snapshot.renderer.inventorySize,
        pathCount: snapshot.renderer.pathCount, stockPool: snapshot.renderer.stockPool, queuePool: snapshot.renderer.queuePool,
        runtimeErrors: snapshot.runtimeErrors, checkpoint: snapshot.checkpoint}};
  });
  await forceMajorGc();
  const before = await collect();
  const runStress = () => page.evaluate(() => {
    const qa = window.__S3_QA, operations = ['LOAD_IN', 'INBOUND_TRAVEL', 'STORE_HANDLE', 'LINK_TRAVEL', 'RETRIEVE_HANDLE', 'OUTBOUND_TRAVEL', 'SCAN_EXIT'];
    const frames = 1400, start = performance.now();
    for (let index = 0; index < frames; index += 1) qa.seek(index % 100, operations[index % operations.length], (index % 97) / 96);
    qa.seek(20, 'STORE_HANDLE', .64);
    return {frames, durationMs: performance.now() - start};
  });
  const stress = await runStress();
  await twoFrames(page); await forceMajorGc();
  const afterFirst = await collect();
  const steadyStress = await runStress();
  await twoFrames(page); await forceMajorGc();
  const after = await collect();
  const raf = await page.evaluate(() => new Promise(resolve => {
    let frames = 0, first = null;
    const tick = now => { if (first === null) first = now; frames += 1;
      if (frames >= 120) resolve({frames, durationMs: now - first, fps: (frames - 1) * 1000 / Math.max(1, now - first)});
      else requestAnimationFrame(tick); };
    requestAnimationFrame(tick);
  }));
  await cdp.detach();
  return {readyMs, gcMethod: 'CDP HeapProfiler.collectGarbage', before, stress: {...stress, framesPerSecond: stress.frames * 1000 / stress.durationMs}, afterFirst,
    steadyStress: {...steadyStress, framesPerSecond: steadyStress.frames * 1000 / steadyStress.durationMs}, after, raf,
    heapWarmupDelta: before.heapBytes === null || afterFirst.heapBytes === null ? null : afterFirst.heapBytes - before.heapBytes,
    heapSteadyDelta: afterFirst.heapBytes === null || after.heapBytes === null ? null : after.heapBytes - afterFirst.heapBytes};
}

async function runDeterminismAudit(page) {
  await setQuery(page, 'AUTO', 'skew');
  const priorDamping = await page.evaluate(() => controls.enableDamping);
  await page.evaluate(() => { window.__S3_QA.resetCamera(); controls.enableDamping = false; controls.update(); window.__S3_QA.seek(55, 'STORE_HANDLE', .64); });
  await twoFrames(page);
  const state = () => page.evaluate(() => ({camera: cameraSnapshot(), snapshot: window.__S3_QA.snapshot()}));
  const read = storeReference => page.evaluate(store => {
    renderer.render(scene, camera);
    const source = renderer.domElement, probe = document.createElement('canvas');
    probe.width = source.width; probe.height = source.height;
    const context = probe.getContext('2d', {willReadFrequently: true});
    context.drawImage(source, 0, 0);
    const pixels = context.getImageData(0, 0, probe.width, probe.height).data;
    let pixelDiff = null;
    if (store) window.__S3_DETERMINISM_PIXELS = pixels;
    else {
      const before = window.__S3_DETERMINISM_PIXELS;
      let changedPixels = 0, maxChannelDelta = 0, totalChannelDelta = 0;
      for (let index = 0; index < pixels.length; index += 4) {
        let changed = false;
        for (let channel = 0; channel < 4; channel += 1) {
          const delta = Math.abs(pixels[index + channel] - before[index + channel]);
          if (delta > 0) changed = true;
          maxChannelDelta = Math.max(maxChannelDelta, delta); totalChannelDelta += delta;
        }
        if (changed) changedPixels += 1;
      }
      pixelDiff = {changedPixels, pixelCount: pixels.length / 4,
        changedRatio: changedPixels / (pixels.length / 4), maxChannelDelta, totalChannelDelta};
      delete window.__S3_DETERMINISM_PIXELS;
    }
    return {png: source.toDataURL('image/png'), pixelDiff};
  }, storeReference);
  const firstState = await state(), first = await read(true); await twoFrames(page); const second = await read(false), secondState = await state();
  await page.evaluate(value => { controls.enableDamping = value; controls.update(); }, priorDamping);
  const decode = value => Buffer.from(value.slice(value.indexOf(',') + 1), 'base64');
  const firstBytes = decode(first.png), secondBytes = decode(second.png);
  writeFileSync(join(OUT, 'determinism_01.png'), firstBytes); writeFileSync(join(OUT, 'determinism_02.png'), secondBytes);
  const coreState = value => {
    const snapshot = value.snapshot, rendererState = snapshot.renderer;
    return {traceId: snapshot.traceId, query: snapshot.query, paused: snapshot.paused, loading: snapshot.loading,
      runtimeErrors: snapshot.runtimeErrors, playback: snapshot.playback, checkpoint: snapshot.checkpoint,
      renderer: Object.fromEntries(['inventorySize','inventoryGids','stockPool','queuePool','queueVisibleGids','pathCount','sceneMeshes',
        'stockVisual','pathPlan','operationKey','phaseName','faulted','faultIndex','cargoOwner','timing','loop','loopResetMask',
        'mastX','carrierX','carrierZ','forkExtension','forkY','forkDrop','cargo','transfer','infeed','outfeed','topology','collisions','ownership']
        .map(key => [key, rendererState[key]]))};
  };
  const cameraError = maxCameraError(firstState.camera, secondState.camera);
  const stateStable = cameraError <= 1e-9 && JSON.stringify(coreState(firstState)) === JSON.stringify(coreState(secondState));
  const exactEqual = firstBytes.equals(secondBytes);
  const pixelStable = exactEqual || (second.pixelDiff.changedPixels <= 64 && second.pixelDiff.changedRatio <= .0002 &&
    second.pixelDiff.maxChannelDelta <= 2);
  return {equal: pixelStable, exactEqual, pixelStable, pixelTolerance:{maxChangedPixels:64,maxChangedRatio:.0002,maxChannelDelta:2},
    pixelDiff:second.pixelDiff, stateStable, cameraError, firstState, secondState,
    firstSha256: sha256(firstBytes), secondSha256: sha256(secondBytes), bytes: firstBytes.length};
}

async function runFullFrameAudit(page) {
  return page.evaluate(() => {
    const qa = window.__S3_QA;
    const collisionScope = 'active_queue_cargo_vs_station_solids_each_other_and_floor';
    const startedAt = performance.now();
    const operations = ['LOAD_IN', 'INBOUND_TRAVEL', 'STORE_HANDLE', 'LINK_TRAVEL', 'RETRIEVE_HANDLE', 'OUTBOUND_TRAVEL', 'SCAN_EXIT'];
    const progress = [0, .05, .15, .3, .5, .7, .85, .95, 1];
    let frames = 0, worstOverlap = 0, worstCase = null, outOfBounds = 0, stationOverlap = 0, stationOutOfBounds = 0,
      compositionGateFailures = 0, duplicateOwners = 0, runtimeErrors = 0;
    let collisions = 0, floorBreaches = 0, collisionScopeFailures = 0, orphanLeaders = 0, leaderObstacleHits = 0, leaderCrossings = 0,
      stationLeaderObstacleHits = 0, stationLeaderCrossings = 0, maxLeaderLength = 0, pathPlanFailures = 0, stockVisualFailures = 0;
    const leaderHitSamples = [];
    for (let cycle = 0; cycle < 100; cycle += 1) for (const operation of operations) for (const p of progress) {
      qa.seek(cycle, operation, p); const s = qa.snapshot(), c = s.renderer.collisions;
      frames += 1;
      const labelOverlap = s.renderer.labels.overlapArea || 0;
      if (labelOverlap > worstOverlap) {
        worstOverlap = labelOverlap;
        const ids = ['sceneDock', 'targetBeacon'];
        worstCase = {cycle, operation, progress: p, checkpoint: s.checkpoint, labels: s.renderer.labels,
          rects: Object.fromEntries(ids.map(id => {const element = document.getElementById(id); if (!element || element.hidden) return [id, null];
            const rect = element.getBoundingClientRect(); return [id, {left: rect.left, top: rect.top, right: rect.right, bottom: rect.bottom}];}))};
      }
      if (s.renderer.labels.outOfBounds) outOfBounds += 1;
      leaderObstacleHits += s.renderer.labels.leaderObstacleHits || 0;
      if (s.renderer.labels.leaderObstacleHits && leaderHitSamples.length < 12) leaderHitSamples.push({cycle, operation, progress: p,
        checkpoint: s.checkpoint, labels: s.renderer.labels, stationLabels: s.renderer.stationLabels});
      leaderCrossings += s.renderer.labels.leaderCrossings || 0;
      maxLeaderLength = Math.max(maxLeaderLength, s.renderer.labels.maxLeaderLength || 0);
      stationOverlap = Math.max(stationOverlap, s.renderer.stationLabels?.overlapArea || 0);
      if (s.renderer.stationLabels?.outOfBounds) stationOutOfBounds += 1;
      stationLeaderObstacleHits += s.renderer.stationLabels?.leaderObstacleHits || 0;
      stationLeaderCrossings += s.renderer.stationLabels?.leaderCrossings || 0;
      maxLeaderLength = Math.max(maxLeaderLength, s.renderer.stationLabels?.maxLeaderLength || 0);
      const subject = s.renderer.composition.visibleSubject, gate = s.renderer.composition.gate;
      if (!subject.inside || subject.widthRatio < gate.targetWidthRatio[0] - 1e-9 || subject.widthRatio > gate.targetWidthRatio[1] + 1e-9 ||
        subject.clearance.top < gate.targetTopClearance[0] - 1e-9 || subject.clearance.top > gate.targetTopClearance[1] + 1e-9) compositionGateFailures += 1;
      if (!s.renderer.ownership.unique || s.renderer.ownership.duplicates.length) duplicateOwners += 1;
      const pathPlan = s.renderer.pathPlan || [], activePaths = pathPlan.filter(path => Math.abs(path.opacity - .96) < 1e-9);
      const pathDistance = (left, right) => Math.hypot(left.x-right.x, left.y-right.y, left.z-right.z);
      const continuous = [[0,1],[1,2],[4,5],[5,6]].every(([left,right]) =>
        pathPlan[left]?.end && pathPlan[right]?.start && pathDistance(pathPlan[left].end,pathPlan[right].start) <= 1e-6);
      if (pathPlan.length !== 7 || pathPlan.map(path => path.operationKey).join('|') !== operations.join('|') ||
          activePaths.length !== 1 || activePaths[0].operationKey !== s.renderer.operationKey || !continuous) pathPlanFailures += 1;
      const stock = s.renderer.stockVisual, gradeTotal = stock ? Object.values(stock.gradeCounts).reduce((sum, value) => sum + value, 0) : -1;
      if (!stock || stock.source !== 'event_inventory_snapshot' || stock.solidGreenShell ||
          stock.lidCount !== s.renderer.inventorySize || gradeTotal !== s.renderer.inventorySize) stockVisualFailures += 1;
      if (s.runtimeErrors) runtimeErrors += 1;
      if (c.scope !== collisionScope) collisionScopeFailures += 1;
      collisions += c.collisions.length; floorBreaches += c.floorBreaches.length;
      for (const [labelId, lineId] of [['targetBeacon', 'targetLeader']]) {
        if ((!document.getElementById(labelId).hidden) !== (getComputedStyle(document.getElementById(lineId)).display !== 'none')) orphanLeaders += 1;
      }
    }
    return {frames, durationMs: performance.now() - startedAt, worstOverlap, worstCase, outOfBounds, stationOverlap, stationOutOfBounds,
      collisionScope, compositionGateFailures, duplicateOwners, runtimeErrors, collisions, floorBreaches, collisionScopeFailures, orphanLeaders,
      leaderObstacleHits, leaderCrossings, stationLeaderObstacleHits, stationLeaderCrossings, maxLeaderLength, leaderHitSamples,
      pathPlanFailures, stockVisualFailures};
  });
}

async function runSweptCollisionAudit(page) {
  return page.evaluate(() => {
    const qa = window.__S3_QA, steps = 1000,
      operations = ['LOAD_IN','INBOUND_TRAVEL','STORE_HANDLE','LINK_TRAVEL','RETRIEVE_HANDLE','OUTBOUND_TRAVEL','SCAN_EXIT'];
    const collisionScope = 'active_queue_cargo_vs_station_solids_each_other_and_floor';
    const centerHalf = box => ({
      center: box.min.map((value, index) => (value + box.max[index]) / 2),
      half: box.min.map((value, index) => (box.max[index] - value) / 2)
    });
    const segmentHitsExpandedBox = (from, to, half, solid) => {
      let t0 = 0, t1 = 1;
      for (let axis = 0; axis < 3; axis += 1) {
        const min = solid.min[axis] - half[axis], max = solid.max[axis] + half[axis], delta = to[axis] - from[axis];
        if (Math.abs(delta) < 1e-12) { if (from[axis] < min || from[axis] > max) return false; continue; }
        let a = (min - from[axis]) / delta, b = (max - from[axis]) / delta;
        if (a > b) [a, b] = [b, a]; t0 = Math.max(t0, a); t1 = Math.min(t1, b); if (t0 > t1) return false;
      }
      return true;
    };
    const result = {scope: collisionScope, scopeFailures: 0, stepsPerOperation: steps, endpointCollisions: [], sweptHits: [], floorBreaches: [],
      minClearance: Infinity, queueSamples: 0, queueDisplacement: 0};
    for (const operation of operations) {
      let previous = null, queueAnchor = null;
      for (let index = 0; index <= steps; index += 1) {
        qa.seek(20, operation, index / steps); const snapshot = qa.snapshot(), metrics = qa.collisionGeometry();
        if (metrics.scope !== collisionScope) result.scopeFailures += 1;
        result.minClearance = Math.min(result.minClearance, metrics.minClearance ?? Infinity);
        if (metrics.collisions.length) result.endpointCollisions.push({operation, index, collisions: metrics.collisions});
        if (metrics.floorBreaches.length) result.floorBreaches.push({operation, index, breaches: metrics.floorBreaches});
        const active = metrics.geometry.actors.find(item => item.label.startsWith('ACTIVE_'));
        if (operation === 'LOAD_IN' && snapshot.renderer.phaseName === 'QUEUE' && active) {
          const center = centerHalf(active).center;
          if (!queueAnchor) queueAnchor = center;
          result.queueSamples += 1;
          result.queueDisplacement = Math.max(result.queueDisplacement,
            Math.hypot(center[0]-queueAnchor[0], center[1]-queueAnchor[1], center[2]-queueAnchor[2]));
        }
        if (active && previous) {
          const a = centerHalf(previous.actor), b = centerHalf(active), half = a.half.map((value, axis) => Math.max(value, b.half[axis]));
          for (const solid of metrics.geometry.solids) if (segmentHitsExpandedBox(a.center, b.center, half, solid)) {
            result.sweptHits.push({operation, fromIndex: index - 1, toIndex: index, solid: solid.label});
          }
        }
        previous = active ? {actor: active} : null;
      }
    }
    let queueMaxActors = 0, queueCollisions = 0, queueFloorBreaches = 0;
    for (let cycle = 0; cycle < 100; cycle += 1) {
      qa.seek(cycle, 'LOAD_IN', 0); const metrics = qa.collisionGeometry();
      if (metrics.scope !== collisionScope) result.scopeFailures += 1;
      queueMaxActors = Math.max(queueMaxActors, metrics.actorCount); queueCollisions += metrics.collisions.length;
      queueFloorBreaches += metrics.floorBreaches.length;
    }
    return {...result, queueSweep: {cycles: 100, queueMaxActors, queueCollisions, queueFloorBreaches}};
  });
}

async function main() {
  if (!existsSync(CHROME)) throw new Error(`Chromium not found: ${CHROME}`);
  mkdirSync(OUT, {recursive: true});
  const serverHandle = await startStaticServer();
  const browser = await chromium.launch({headless: true, executablePath: CHROME,
    args: ['--use-angle=d3d11', '--enable-webgl', '--ignore-gpu-blocklist', '--js-flags=--expose-gc']});
  const context = await browser.newContext({viewport: {width: 1280, height: 720}, deviceScaleFactor: 1});
  const page = await context.newPage(); page.setDefaultTimeout(120000);
  const pageErrors = [], badResponses = [], requestedUrls = [];
  page.on('request', request => requestedUrls.push(request.url()));
  page.on('pageerror', error => pageErrors.push(String(error)));
  page.on('console', msg => { if (msg.type() === 'error') pageErrors.push(msg.text()); });
  page.on('response', response => { if (response.status() >= 400 && !response.url().endsWith('/favicon.ico')) badResponses.push({status: response.status(), url: response.url()}); });
  await page.route('**/favicon.ico', route => route.fulfill({status: 204, body: ''}));
  const captures = [], cameraBehaviors = [];
  try {
    const navigationStarted = Date.now();
    await page.goto(serverHandle.url, {waitUntil: 'load'});
    await page.waitForFunction(() => window.__S3_QA?.snapshot?.().traceId === 't3_skew_auto');
    const readyMs = Date.now() - navigationStarted;
    await page.addStyleTag({content: '*{animation:none!important}'});

    const playbackAudit = await runPlaybackAudit(page);
    const timingAudit = await runTimingAudit(page);
    const hoverAudit = await runHoverAudit(page);
    const accessibilityAudit = await runAccessibilityAudit(page);
    const performanceAudit = await runPerformanceAudit(page, readyMs);
    const determinismAudit = await runDeterminismAudit(page);
    const offlineAudit = await page.evaluate(() => ({
      resources: Array.from(document.querySelectorAll('script[src],link[href]')).map(element => element.src || element.href),
      origin: location.origin,
      navigation: (() => { const entry = performance.getEntriesByType('navigation')[0]; return entry ? {
        transferSize: entry.transferSize, encodedBodySize: entry.encodedBodySize, decodedBodySize: entry.decodedBodySize,
        domContentLoadedMs: entry.domContentLoadedEventEnd, loadMs: entry.loadEventEnd} : null; })()
    }));
    const allowedOrigin = new URL(serverHandle.url).origin;
    offlineAudit.requests = Array.from(new Set(requestedUrls));
    offlineAudit.externalRequests = offlineAudit.requests.filter(value => { try { const url = new URL(value); return !['data:', 'blob:'].includes(url.protocol) && url.origin !== allowedOrigin; } catch { return true; } });
    offlineAudit.externalResources = offlineAudit.resources.filter(value => { try { return new URL(value).origin !== allowedOrigin; } catch { return true; } });
    const fullFrameAudit = await runFullFrameAudit(page);
    const sweptCollisionAudit = await runSweptCollisionAudit(page);
    const cameraExtremesAudit = await runCameraExtremesAudit(page, OUT);

    for (const [width, height] of VIEWPORTS) {
      await page.setViewportSize({width, height}); await twoFrames(page);
      let cameraMoved = null;
      for (const state of STATES) {
        await configureComparison(page, null);
        await page.evaluate(() => { if (document.activeElement && typeof document.activeElement.blur === 'function') document.activeElement.blur(); });
        await setQuery(page, state.query[0], state.query[1]);
        if (state.faultIndex !== undefined) await page.evaluate(index => window.__S3_QA.seekFault(index), state.faultIndex);
        else await page.evaluate(([cycle, operation, progress]) => window.__S3_QA.seek(cycle, operation, progress), state.seek);
        if (state.camera !== 'reset') await page.evaluate(() => window.__S3_QA.resetCamera());
        await twoFrames(page);
        if (state.camera === 'move') {
          const before = await page.evaluate(() => window.__S3_QA.snapshot().renderer.camera);
          const beforeLabels = await page.evaluate(() => window.__S3_QA.snapshot().renderer.labels);
          await dragCamera(page);
          const after = await page.evaluate(() => window.__S3_QA.snapshot().renderer.camera);
          const afterLabels = await page.evaluate(() => window.__S3_QA.snapshot().renderer.labels);
          cameraMoved = {before, beforeLabels, after, afterLabels};
        } else if (state.camera === 'reset') {
          if (!cameraMoved) throw new Error('camera reset state lacks moved predecessor');
          await page.locator('#resetCamera').click(); await twoFrames(page);
          const reset = await page.evaluate(() => window.__S3_QA.snapshot().renderer.camera);
          cameraBehaviors.push({viewport: [width, height], ...cameraMoved, reset, maxResetError: maxCameraError(cameraMoved.before, reset)});
        } else if (state.camera === 'ioCloseup') {
          await page.evaluate(() => {
            camera.position.set(8.8, -17.5, 13.8); controls.target.set(.5, -3.05, 1.2);
            camera.fov = 38; camera.updateProjectionMatrix(); controls.update();
          });
          await twoFrames(page);
        }
        if (state.comparison) await configureComparison(page, state.comparison);
        if (state.keyboardFocus) await page.keyboard.press('Tab');
        if (state.tooltipIndex !== undefined) await page.locator('#traceStats .metricHelp').nth(state.tooltipIndex).focus();
        await twoFrames(page);
        const audit = await captureAudit(page), filename = `${width}x${height}_${state.name}.png`, path = join(OUT, filename);
        await page.screenshot({path, type: 'png', animations: 'disabled'});
        const bytes = readFileSync(path), dimensions = pngSize(bytes);
        captures.push({file: filename, file_sha256: sha256(bytes), dimensions, state: state.name, audit,
          checks: {dimensionsMatch: dimensions[0] === width && dimensions[1] === height,
            noDocumentOverflow: audit.scroll[0] === width && audit.scroll[1] === height,
            noRailOverflow: audit.rail.clientHeight === audit.rail.scrollHeight,
            fixedInside: audit.fixed.every(item => item.rect.inside), noOverlayOverlap: audit.overlaps.length === 0,
            dockUnifiedAndInside: audit.dock.rect?.inside && audit.dock.children.length === 3 && audit.dock.childrenInside && audit.dock.childOverlaps.length === 0,
            dockChineseFirstAndDeduplicated: audit.dock.bannedDecorativeEnglish.length === 0 && audit.dock.formulaOccurrences === 1 &&
              audit.dock.reserveCountOccurrences === 1 && audit.dock.action.clear && audit.dock.action.cargoAligned,
            noLabelConflict: audit.labels.overlapArea === 0 && !audit.labels.outOfBounds &&
              audit.labels.leaderObstacleHits === 0 && audit.labels.leaderCrossings === 0,
            noStationLabelConflict: audit.stationLabels.visible === 0 && audit.stationLabels.overlapArea === 0 && !audit.stationLabels.outOfBounds &&
              audit.stationLabels.leaderObstacleHits === 0 && audit.stationLabels.leaderCrossings === 0,
            visibleCompositionGate: state.qaOnly || state.camera === 'move' || (audit.composition.visibleSubject.inside &&
              audit.composition.visibleSubject.widthRatio >= audit.composition.gate.targetWidthRatio[0] &&
              audit.composition.visibleSubject.widthRatio <= audit.composition.gate.targetWidthRatio[1] &&
              audit.composition.visibleSubject.clearance.top >= audit.composition.gate.targetTopClearance[0] &&
              audit.composition.visibleSubject.clearance.top <= audit.composition.gate.targetTopClearance[1]),
            maxQueuePressureInside: state.qaOnly || state.camera === 'move' || audit.composition.maxQueuePressure.subject.inside,
            dualStationComposition: state.qaOnly || state.camera === 'move' || (audit.composition.stations.inside && audit.composition.stations.widthRatio >= .15),
            uniqueOwnership: audit.ownership.unique && audit.ownership.duplicates.length === 0,
            cargoStationFloorClear: audit.collisions.scope === 'active_queue_cargo_vs_station_solids_each_other_and_floor' &&
              audit.collisions.collisions.length === 0 && audit.collisions.floorBreaches.length === 0,
            coaxialNonSharedStations: audit.topology.collinear && !audit.topology.sharedBelt && audit.topology.oppositeSides &&
              audit.topology.axisOffset <= 1e-9 && audit.topology.rackFrontClearance >= .30 && audit.topology.collinearAxis === 'x' &&
              audit.topology.envelopeOverlapArea === 0 && audit.topology.transferAnchor.x === .5 && audit.topology.transferAnchor.y === -.75,
            noOrphanLeader: audit.orphanLeaders.length === 0,
            snapshotStockVisual: audit.stockVisual.source === 'event_inventory_snapshot' && !audit.stockVisual.solidGreenShell &&
              audit.stockVisual.lidCount === audit.ownership.records.filter(record => record.owner === 'RACK').length &&
              Object.values(audit.stockVisual.gradeCounts).reduce((sum, value) => sum + value, 0) === audit.stockVisual.lidCount,
            sevenStepPathVisual: audit.pathPlan.length === 7 && audit.pathPlan.map(path => path.operationKey).join('|') ===
              ['LOAD_IN','INBOUND_TRAVEL','STORE_HANDLE','LINK_TRAVEL','RETRIEVE_HANDLE','OUTBOUND_TRAVEL','SCAN_EXIT'].join('|') &&
              audit.pathPlan.filter(path => Math.abs(path.opacity - .96) < 1e-9).length === 1 &&
              audit.pathPlan.find(path => Math.abs(path.opacity - .96) < 1e-9).operationKey === audit.cargo.operationKey &&
              audit.pathContinuity.every(pair => pair.distance <= 1e-6) &&
              Math.abs(audit.pathPlan[2].end.y - audit.geometry.rackLoadY) <= 1e-9 &&
              Math.abs(audit.pathPlan[4].start.y - audit.geometry.rackLoadY) <= 1e-9,
            reservedVolumesPerInstanceFlush: audit.geometry.reservedCount === 133 && audit.geometry.availableCount === 267 &&
              Math.abs(audit.geometry.reservedMinY) <= GEOMETRY_FLOAT_EPS && Math.abs(audit.geometry.reservedMaxY - audit.geometry.rackDepth) <= GEOMETRY_FLOAT_EPS &&
              Math.abs(audit.geometry.reservedDepth - audit.geometry.rackDepth) <= GEOMETRY_FLOAT_EPS &&
              Math.abs(audit.geometry.cellFace + audit.geometry.beamWidth - 1) <= GEOMETRY_FLOAT_EPS && audit.geometry.rackDepth === .95 &&
              audit.geometry.actualBoundsDerived && audit.geometry.reservedBounds.derivedFromInstanceMatrices &&
              audit.geometry.frontFlushError <= GEOMETRY_FLOAT_EPS && audit.geometry.backFlushError <= GEOMETRY_FLOAT_EPS && audit.geometry.beamInnerFitError <= GEOMETRY_FLOAT_EPS &&
              audit.geometry.reservedInstanceAudit?.scannedFromInstanceMatrices && audit.geometry.reservedInstanceAudit.count === 133 &&
              Math.abs(audit.geometry.reservedInstanceAudit.minDepth - audit.geometry.rackDepth) <= GEOMETRY_FLOAT_EPS &&
              Math.abs(audit.geometry.reservedInstanceAudit.maxDepth - audit.geometry.rackDepth) <= GEOMETRY_FLOAT_EPS &&
              audit.geometry.reservedInstanceAudit.maxFrontError <= GEOMETRY_FLOAT_EPS && audit.geometry.reservedInstanceAudit.maxBackError <= GEOMETRY_FLOAT_EPS &&
              audit.geometry.reservedInstanceAudit.failedIndices.length === 0,
            squareMapNoDeadCard: audit.mapLayout.aspectError <= 1 && audit.mapLayout.unusedBottom >= -1 && audit.mapLayout.unusedBottom <= 10,
            realTimePhaseLegible: audit.phaseLayout.segments.length === 7 && audit.phaseLayout.timePartPercentages.length === 7 &&
              Math.abs(audit.phaseLayout.timePartPercentages.reduce((sum, value) => sum + value, 0) - 100) <= .02 &&
              audit.phaseLayout.segments.every(item => item.duration && item.fontPx >= 9 && (item.duration === '展示' || /^\d+\.\d+s$/.test(item.duration))) &&
              ((audit.phaseLayout.segments[0].duration === '展示' && audit.phaseLayout.segments[0].text.includes('交接')) ||
               (audit.phaseLayout.segments[0].duration !== '展示' && audit.phaseLayout.segments[0].text.includes('排队'))) &&
              audit.phaseLayout.clock.includes('SIM') && audit.phaseLayout.clock.includes('1=排队/交接'),
            comparisonValid: audit.comparison.valid && audit.comparison.miniRows === 4,
            miniScopeDisclosed: audit.comparison.miniDisclosure.title.includes('当前 4 / 完整 8') &&
              audit.comparison.miniDisclosure.scope.includes('非全量') && audit.comparison.miniDisclosure.scope.includes('AUTO / CB / TOB') &&
              audit.comparison.miniDisclosure.button.includes('查看完整对照'),
            comparisonStateCorrect: state.comparison ? (audit.comparison.open && audit.comparison.axis === state.comparison.axis &&
              (state.comparison.axis === 'scenario' ? audit.comparison.scenario : audit.comparison.mode) === state.comparison.key &&
              audit.comparison.tableRows === (state.comparison.axis === 'scenario' ? 8 : 18) &&
              audit.comparison.panel?.inside && audit.comparison.panelOverflow[0] === audit.comparison.panelOverflow[1] &&
              audit.comparison.footText.includes('S1') && audit.comparison.footText.includes('S3') && audit.comparison.footText.includes('不池化') &&
              audit.comparison.criticalFontMinPx >= 9 &&
              (state.comparison.key !== 'E15' || (audit.comparison.e15Rows === 8 && audit.comparison.summaryText.includes('非 canonical G2 / 非 H')))) :
              !audit.comparison.open,
            tooltipStateCorrect: state.tooltipIndex !== undefined ? Boolean(audit.tooltip?.rect?.inside && audit.tooltip.role === 'tooltip' &&
              audit.tooltip.ownerExpanded === 'true' && audit.tooltip.text.length > 20) : !audit.tooltip,
            faultStateCorrect: state.faultIndex !== undefined ? (audit.fault.visible && audit.fault.faulted && audit.fault.phaseName === 'FAULT_RECOVERY' &&
              audit.fault.faultIndex === state.faultIndex && audit.fault.text.includes('SIM 故障恢复')) : (!audit.fault.visible && !audit.fault.faulted),
            runtimeErrors0: audit.runtimeErrors === 0}}
        );
      }
    }

    const browserInfo = await page.evaluate(() => ({userAgent: navigator.userAgent, dpr: devicePixelRatio,
      webgl: (() => {const canvas = document.createElement('canvas'), gl = canvas.getContext('webgl'); if (!gl) return null;
        const ext = gl.getExtension('WEBGL_debug_renderer_info'); return ext ? {vendor: gl.getParameter(ext.UNMASKED_VENDOR_WEBGL), renderer: gl.getParameter(ext.UNMASKED_RENDERER_WEBGL)} : null;})()}));
    const aliases = [
      ['1280x720_03_store.png', '01_default_store_1280x720.png'],
      ['1280x720_01_infeed_entry.png', '02_default_infeed_1280x720.png'],
      ['1280x720_07_exit_mask.png', '03_default_outfeed_1280x720.png'],
      ['1280x720_12_io_closeup_qa.png', '04_qa_only_dual_lane_oblique.png']
    ].map(([source, alias]) => {
      const bytes = readFileSync(join(OUT, source)); writeFileSync(join(OUT, alias), bytes);
      return {source, alias, file_sha256: sha256(bytes)};
    });
    const checks = {
      captureCountExpected: captures.length === VIEWPORTS.length * STATES.length,
      allCaptureChecks: captures.every(capture => Object.values(capture.checks).every(Boolean)),
      cameraResetAll: cameraBehaviors.length === 4 && cameraBehaviors.every(item => item.maxResetError <= 1e-9),
      cameraMovedAll: cameraBehaviors.every(item => JSON.stringify(item.before.position) !== JSON.stringify(item.after.position)),
      labelReprojectedAll: cameraBehaviors.every(item => JSON.stringify(item.beforeLabels.labels) !== JSON.stringify(item.afterLabels.labels)),
      playbackInvariant: playbackAudit.slowInvariant && playbackAudit.fastInvariant && playbackAudit.slow.playback.effectiveScale === .055 && playbackAudit.fast.playback.effectiveScale === .44,
      timingPriorityCorrect: timingAudit.monotoneFailures.length === 0 && !timingAudit.invertedPriority &&
        Object.keys(timingAudit.summary).length === 7 && Object.values(timingAudit.summary).every(item => item.samples === 100),
      hoverVisible: hoverAudit.expanded === 'true' && hoverAudit.visibility === 'visible' && hoverAudit.opacity === '1',
      accessibilityComplete: accessibilityAudit.normalTargets.undersized.length === 0 && accessibilityAudit.dialogTargets.undersized.length === 0 &&
        accessibilityAudit.normalTargets.duplicateIds.length === 0 && accessibilityAudit.dialogTargets.duplicateIds.length === 0 &&
        accessibilityAudit.opened.active === 'closeComparisonLab' && accessibilityAudit.opened.backgroundInert > 0 &&
        accessibilityAudit.opened.dialogModal === 'true' && accessibilityAudit.opened.describedBy === 'comparisonFoot' &&
        accessibilityAudit.wrappedLast.inside && accessibilityAudit.wrappedLast.id !== 'closeComparisonLab' && accessibilityAudit.wrappedFirst === 'closeComparisonLab' &&
        accessibilityAudit.arrowNavigation.active === 'comparisonModeTab' && accessibilityAudit.arrowNavigation.selectedScenario === 'false' &&
        accessibilityAudit.arrowNavigation.selectedMode === 'true' && accessibilityAudit.arrowNavigation.scenarioTabIndex === -1 &&
        accessibilityAudit.arrowNavigation.modeTabIndex === 0 && accessibilityAudit.arrowNavigation.snapshot.axis === 'mode' &&
        accessibilityAudit.arrowNavigation.snapshot.tableRows === 18 && accessibilityAudit.closed.hidden &&
        accessibilityAudit.closed.active === 'openComparisonLab' && accessibilityAudit.closed.inertRemaining === 0 &&
        accessibilityAudit.tooltipFocused.active && accessibilityAudit.tooltipFocused.expanded === 'true' && accessibilityAudit.tooltipFocused.role === 'tooltip' &&
        accessibilityAudit.tooltipFocused.visible === 'visible' && accessibilityAudit.tooltipFocused.describedBy &&
        accessibilityAudit.tooltipClosed.expanded === 'false' && !accessibilityAudit.tooltipClosed.active &&
        accessibilityAudit.failed.role === 'alert' && accessibilityAudit.failed.live === 'assertive' && accessibilityAudit.failed.atomic === 'true' &&
        accessibilityAudit.failed.retryButtons === 1 && accessibilityAudit.failed.text.includes('加载失败') &&
        accessibilityAudit.recovered.errorHidden && accessibilityAudit.recovered.controlsBusy === 'false' &&
        accessibilityAudit.recovered.statusRole === 'status' && accessibilityAudit.recovered.statusLive === 'polite' &&
        accessibilityAudit.reducedMotion.cycleReset === '0s' && accessibilityAudit.reducedMotion.actionBadge === '0s',
      offlineSelfContained: offlineAudit.resources.length === 6 && offlineAudit.externalRequests.length === 0 && offlineAudit.externalResources.length === 0,
      performanceBudget: performanceAudit.readyMs <= 5000 && performanceAudit.raf.fps >= 45 &&
        performanceAudit.stress.frames === 1400 && performanceAudit.stress.framesPerSecond >= 60 &&
        performanceAudit.steadyStress.frames === 1400 && performanceAudit.steadyStress.framesPerSecond >= 60 &&
        performanceAudit.after.renderer.calls <= 350 && performanceAudit.after.runtime.runtimeErrors === 0 &&
        performanceAudit.before.domNodes === performanceAudit.after.domNodes &&
        performanceAudit.before.renderer.geometries === performanceAudit.after.renderer.geometries &&
        performanceAudit.before.renderer.textures === performanceAudit.after.renderer.textures &&
        performanceAudit.before.runtime.sceneMeshes === performanceAudit.after.runtime.sceneMeshes &&
        performanceAudit.before.runtime.inventorySize === performanceAudit.after.runtime.inventorySize &&
        performanceAudit.before.runtime.pathCount === performanceAudit.after.runtime.pathCount &&
        performanceAudit.before.runtime.stockPool === performanceAudit.after.runtime.stockPool &&
        performanceAudit.before.runtime.queuePool === performanceAudit.after.runtime.queuePool &&
        (performanceAudit.heapWarmupDelta === null || performanceAudit.heapWarmupDelta <= 24 * 1024 * 1024) &&
        (performanceAudit.heapSteadyDelta === null || performanceAudit.heapSteadyDelta <= 4 * 1024 * 1024),
      deterministicCanvas: determinismAudit.equal && determinismAudit.stateStable && determinismAudit.bytes > 10000,
      cameraExtremesClear: cameraExtremesAudit.length === 4 && cameraExtremesAudit.every(item =>
        item.labels.overlapArea === 0 && !item.labels.outOfBounds && item.labels.leaderObstacleHits === 0 && item.labels.leaderCrossings === 0 &&
        item.stationLabels.overlapArea === 0 && !item.stationLabels.outOfBounds && item.stationLabels.leaderObstacleHits === 0 &&
        item.stationLabels.leaderCrossings === 0 && item.fixedOverlaps.length === 0 && item.fixedInside && item.orphanLeaders.length === 0 &&
        item.dock.childrenInside && item.dock.childOverlaps.length === 0 && item.dock.bannedDecorativeEnglish.length === 0 &&
        item.camera.frontality >= Math.cos(65 * Math.PI / 180) - .01 && Math.abs(item.camera.azimuth) <= 65 * Math.PI / 180 + 1e-6 &&
        item.composition.rack.inside && item.composition.rack.widthRatio >= .25),
      cameraAzimuthBounded: cameraExtremesAudit.length === 4 && cameraExtremesAudit.every(item =>
        Math.abs(item.camera.azimuth) <= 65 * Math.PI / 180 + 1e-6 && item.camera.frontality >= Math.cos(65 * Math.PI / 180) - .01),
      extremeCameraPngsBound: cameraExtremesAudit.length === 4 && cameraExtremesAudit.every(item =>
        item.capture.dimensions[0] === 1280 && item.capture.dimensions[1] === 720 && existsSync(join(OUT, item.capture.file)) &&
        fileHash(join(OUT, item.capture.file)) === item.capture.file_sha256),
      fullFrame6300: fullFrameAudit.frames === 6300 && ['worstOverlap', 'outOfBounds', 'stationOverlap', 'stationOutOfBounds',
        'compositionGateFailures', 'duplicateOwners', 'runtimeErrors', 'collisions', 'floorBreaches', 'collisionScopeFailures', 'orphanLeaders',
        'leaderObstacleHits', 'leaderCrossings', 'stationLeaderObstacleHits', 'stationLeaderCrossings',
        'pathPlanFailures', 'stockVisualFailures'].every(key => fullFrameAudit[key] === 0),
      sweptCargoStationFloorClear: sweptCollisionAudit.scope === 'active_queue_cargo_vs_station_solids_each_other_and_floor' && sweptCollisionAudit.scopeFailures === 0 &&
        sweptCollisionAudit.queueSamples > 1 && sweptCollisionAudit.queueDisplacement <= 1e-7 &&
        sweptCollisionAudit.endpointCollisions.length === 0 && sweptCollisionAudit.sweptHits.length === 0 &&
        sweptCollisionAudit.floorBreaches.length === 0 && sweptCollisionAudit.queueSweep.queueCollisions === 0 && sweptCollisionAudit.queueSweep.queueFloorBreaches === 0,
      pageErrors0: pageErrors.length === 0, badResponses0: badResponses.length === 0
    };
    const manifest = {
      schema: 's3-task17-qa-v9', created_at: new Date().toISOString(), scope: 'candidate-only; supported viewport floor 1280x720; queue-SIM is stationary and separated from presentation-only Entry→Load→Transfer handoff + true-SIM proportional seven-step scale + slower presentation-only playback + snapshot-derived high-contrast stock + per-instance matrix-derived flush audit for all 133 full-depth reserved volumes + rack-depth cargo continuity + continuous seven-step paths + envelope-verified coaxial non-shared in/out segments + scoped active/queue cargo versus station-solid/floor collision audit + sole target beacon + Chinese-first bottom evidence dock; do not overwrite 样张_S3定稿.html before user approval',
      source_hashes: {
        html: fileHash(SOURCE),
        runtime: fileHash(RUNTIME),
        trace_store: fileHash(TRACE_STORE),
        three_lib: fileHash(THREE_LIB),
        orbit_lib: fileHash(ORBIT_LIB),
        runtime_test: fileHash(RUNTIME_TEST),
        qa_generator: fileHash(QA_SCRIPT),
        trace_manifest_json: fileHash(TRACE_MANIFEST),
        s1_comparison_evidence: fileHash(COMPARISON_EVIDENCE),
        s1_comparison_canonical: fileHash(COMPARISON_CANONICAL),
        s1_comparison_generator: fileHash(COMPARISON_GENERATOR)
      },
      browser: browserInfo, viewports: VIEWPORTS, states: STATES, capture_count: captures.length, aliases,
      behavior: {playbackAudit, timingAudit, hoverAudit, accessibilityAudit, offlineAudit, performanceAudit, determinismAudit,
        fullFrameAudit, sweptCollisionAudit, cameraExtremesAudit, cameraBehaviors},
      errors: {pageErrors, badResponses}, checks, captures
    };
    writeFileSync(join(OUT, 'capture_manifest.json'), JSON.stringify(manifest, null, 2), 'utf8');
    if (!Object.values(checks).every(Boolean)) throw new Error(`Task12 QA failed: ${JSON.stringify(checks)}`);
    process.stdout.write(`${JSON.stringify({out: OUT, checks, captureCount: captures.length}, null, 2)}\n`);
  } finally {
    await context.close(); await browser.close(); await new Promise(resolve => serverHandle.server.close(resolve));
  }
}

main().catch(error => { console.error(error.stack || error); process.exitCode = 1; });
