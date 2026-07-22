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

const mime = {'.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.json': 'application/json; charset=utf-8', '.css': 'text/css; charset=utf-8'};
const hash = path => createHash('sha256').update(readFileSync(path)).digest('hex');
mkdirSync(OUT, {recursive: true});
const liveFiles = {
  source: SOURCE, runtime: RUNTIME, store: STORE, interactions: INTERACTIONS,
  shellCss: join(SHOWCASE, 'src', 's3_shell_v2.css'), /* 0719 V2 壳体共享语法 */
  three: join(SHOWCASE, 'src', 'lib', 'three.min.js'),
  orbit: join(SHOWCASE, 'src', 'lib', 'OrbitControls.js'),
  pointer: POINTER, registry: REGISTRY, manifest: MANIFEST,
  auditNear: join(RELEASE_DIR, 'candidate_audit_online_near.jsonl.gz'),
  auditScore: join(RELEASE_DIR, 'candidate_audit_online_score.jsonl.gz'),
  auditSeq: join(RELEASE_DIR, 'candidate_audit_online_seq.jsonl.gz'),
  /* 0721 回灌:30-seed 分布带真 fetch ../evidence/s3_fill_seed_sweep_skew_2026_2055.json,
     快照服务器需能就近提供该文件,否则页面控制台报 404(noRuntimeErrors 门连带失败)。 */
  evidenceSeedSkew: join(SHOWCASE, 'evidence', 's3_fill_seed_sweep_skew_2026_2055.json')
};
const initialHashes = Object.fromEntries(Object.entries(liveFiles).map(([key, path]) => [key, hash(path)]));
const snapshotId = createHash('sha256').update(JSON.stringify(initialHashes)).digest('hex').slice(0, 16);
const SNAPSHOT = join(OUT, `_local_hash_snapshot_${snapshotId}`);
const snapshotTargets = {
  source: join(SNAPSHOT, 'src', PAGE_NAME),
  runtime: join(SNAPSHOT, 'src', 's3_fill_candidate_runtime.js'),
  store: join(SNAPSHOT, 'src', 's3_fill_store.js'),
  interactions: join(SNAPSHOT, 'src', 's3_layout_a_interactions.js'),
  shellCss: join(SNAPSHOT, 'src', 's3_shell_v2.css'),
  three: join(SNAPSHOT, 'src', 'lib', 'three.min.js'),
  orbit: join(SNAPSHOT, 'src', 'lib', 'OrbitControls.js'),
  pointer: join(SNAPSHOT, 'release_evidence', 'latest.json'),
  registry: join(SNAPSHOT, 'release_evidence', 's3_fill_release_registry.json'),
  manifest: join(SNAPSHOT, 'release_evidence', 's3_fill_data_gate.json'),
  auditNear: join(SNAPSHOT, 'release_evidence', 'candidate_audit_online_near.jsonl.gz'),
  auditScore: join(SNAPSHOT, 'release_evidence', 'candidate_audit_online_score.jsonl.gz'),
  auditSeq: join(SNAPSHOT, 'release_evidence', 'candidate_audit_online_seq.jsonl.gz'),
  /* 相对 src/01_连续填仓.html 的 ../evidence/ 必须解析到快照根下的 evidence/,与生产目录结构一致。 */
  evidenceSeedSkew: join(SNAPSHOT, 'evidence', 's3_fill_seed_sweep_skew_2026_2055.json')
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
      /* 0721 回灌:赛马场四图+赛段比分条+终态总分牌+30-seed 分布带把 #workHud 内容撑高,
         html[data-s3-layout="A"] #workHud 已改 overflow-y:auto——纵向"折叠以下"是设计内的可滚动
         结果,不再是缺陷;仍要卡住的是横向溢出(真实裁切/意外横向滚动条)。故只查左右边界,
         不再查 top/bottom(vertical 下限交给 out-of-fold 但仍可滚动到达)。 */
      const hudOverflow = [...document.querySelectorAll('#workHud > *,#insightStack > *')].filter(element => {
        const style = getComputedStyle(element), rect = element.getBoundingClientRect();
        if (style.display === 'none' || style.visibility === 'hidden' || rect.width <= 0 || rect.height <= 0) return false;
        return rect.left < rail.left - .5 || rect.right > rail.right + .5 || rect.left < -.5 || rect.right > innerWidth + .5;
      }).map(element => ({id: element.id || element.className, rect: {...element.getBoundingClientRect().toJSON()}}));
      const badgeAreaShare = (badge.width * badge.height) / Math.max(1, gl.width * gl.height);
      return {rail: {...rail.toJSON()}, dock: {...dock.toJSON()}, gl: {...gl.toJSON()}, topbar: {...topbar.toJSON()},
        axis: {...axis.toJSON()}, bookmarks: {...bookmarks.toJSON()}, map: {...map.toJSON()}, mapWrap: {...mapWrap.toJSON()},
        mapKeyVisible, badge: {...badge.toJSON()}, badgeAreaShare, phaseSegmentCount,
        bodyScroll: {width: document.documentElement.scrollWidth, height: document.documentElement.scrollHeight},
        clipped: rail.bottom > innerHeight + .5 || dock.bottom > innerHeight + .5 || gl.width < 300 || gl.height < 300,
        mapClipped: map.left < mapWrap.left - .5 || map.right > mapWrap.right + .5 || map.top < mapWrap.top - .5 || map.bottom > mapWrap.bottom + .5,
        hudOverflow,
        /* W6(0720 照 02 语言重做):入库进度轴从"顶栏下独立横条"迁入右栏顶部(同 02 0720 版B),
           axis 不再与 gl 上下堆叠,而是并列于 rail 内——axisAboveGl 的堆叠假设不再成立,
           改核「轴在 rail 边界内」+「gl 紧贴 topbar 下缘(不留独立轴条空隙)」两项等价断言。 */
        axisInsideRail: axis.left >= rail.left - .5 && axis.right <= rail.right + .5 && axis.top >= rail.top - .5,
        glStartsAtTopbar: Math.abs(gl.top - topbar.bottom) <= .5};
    });
    report.viewports.push({width, height, ...viewportAudit});
    const layoutAudit = await page.evaluate(() => window.__S3_LAYOUT_A.audit());
    const placement = await page.evaluate(() => ({
      traceStatsVisible: getComputedStyle(document.getElementById('traceStats')).display !== 'none' &&
        document.getElementById('traceStats').getBoundingClientRect().height > 20,
      /* W6:railFacts(含 factQueue)整栏 display:none 退役——三格中两格(factQueue/factAlarm)恒硬编码
         "0"从未反映真实状态,第三格(factCycle/已入库)与 fillEvidence 的管理货计数完全重复
         (同 02 0719 删 railFacts 的理由:「等待/故障与统计块重复」)。改核同一信息的现役位置。 */
      fillEvidenceVisible: document.getElementById('fillEvidence').getBoundingClientRect().height > 4,
      zoomHintPresent: Boolean(document.querySelector('#slotMapWrap .zoomHint')),
      releaseBadgeInAxis: document.getElementById('releaseBadge').closest('#axisRight') !== null,
      evidenceInAxis: document.getElementById('fillEvidence').closest('#axisRight') !== null,
      selectionReasonPresent: /固定四项权重|首个可用格|行程时间最短/.test(document.getElementById('decisionWrap').textContent),
      speedCanvasPresent: Boolean(document.getElementById('speed')),
      /* W6(照 02 语言重做):phaseRail(七步条)迁回右栏,恢复 02 终态信息架构——不再并入 dock 的
         「当前作业」格(旧 0717 #28 的收纳手法在 02 后续迭代中已被舍弃,01 跟进同一决定) */
      phaseRailInRail: document.getElementById('phaseRail').closest('#workHud') !== null,
      controlsInTopbar: document.getElementById('runtimeControls').closest('#topbarA') !== null,
      retrievalNotePresent: /存取效率/.test(document.getElementById('retrievalNote')?.textContent || ''),
      /* 0717 #28 用户拍板:②拟真档换说明标签(非 select 且原下拉不复存在) */
      tierTagPresent: (() => { const tag = document.getElementById('tierFixedTag');
        return Boolean(tag) && tag.tagName !== 'SELECT' && /SIM 数据门/.test(tag.textContent) &&
          !document.getElementById('tierSelect'); })(),
      /* W6:dock 四分列(当前作业 | 轴状态 | 目标货位卡 | 2D 图例),不再靠"phaseRail 在 caption 内"判定 */
      dockColumnsComplete: Array.from(document.getElementById('sceneDock').children).filter(c => c.id !== 'dockCollapseBtn').length === 4,
      /* W6:「当前作业」格不再需要容纳七段微条,不再要求约占半幅——仍要求它是 dock 内最宽的信息列
         且货物行为大字(fontSize>=13,同旧门槛,未随 02 blueprint 的 12px 松动——见改动清单说明) */
      cargoHeadlineDominant: (() => {
        const caption = document.getElementById('sceneCaption').getBoundingClientRect();
        const dock = document.getElementById('sceneDock').getBoundingClientRect();
        const fontSize = parseFloat(getComputedStyle(document.getElementById('sceneActionText')).fontSize);
        const share = caption.width / dock.width;
        return share > .28 && share < .55 && fontSize >= 13; })(),
      /* W6:镜头/演示倍率迁到 3D 区右下角悬浮小卡(同 02 0720 版B),不再挂进度轴行尾 */
      toolsFloating: document.getElementById('sceneTools').closest('#viewport') !== null &&
        document.getElementById('sceneTools').closest('#fillBookmarks') === null,
      targetCardInDock: (() => { const card = document.getElementById('targetCard');
        return Boolean(card) && card.closest('#sceneDock') !== null &&
          Array.from(document.getElementById('sceneDock').children).filter(c => c.id !== 'dockCollapseBtn').length === 4; })(),
      beaconRetired: getComputedStyle(document.getElementById('targetBeacon')).display === 'none' &&
        getComputedStyle(document.getElementById('labelLeaders')).display === 'none'
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
    /* 0721 回灌:phaseRail 随赛马场新内容下移(order:10),默认滚动位置在折叠线以下——
       先把目标段滚入视口再触发悬停浮层,断言语义不变(浮层仍须落在 viewport 内),
       只是补上"可达"前提(#workHud 已声明 overflow-y:auto,可滚动到达是设计内行为)。 */
    await page.evaluate(value => {
      const segment = document.querySelectorAll('#phaseSegments .phaseSeg')[value];
      if (segment) segment.scrollIntoView({block: 'center'});
    }, index);
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
  /* 0718 M1b:rail 态(未放大)差异热力图常驻左栏且已绘、非全零 */
  await page.waitForTimeout(150);
  report.railDiff = await page.evaluate(() => {
    const rectOf = sel => { const el = document.querySelector(sel); if (!el) return null;
      const cs = getComputedStyle(el); if (cs.display === 'none') return {hidden: true};
      return el.getBoundingClientRect().toJSON(); };
    return {
      overlayOpen: document.getElementById('s3MapOverlay').classList.contains('open'),
      display: getComputedStyle(document.getElementById('diffMapWrap')).display,
      diffRect: document.getElementById('diffMap')?.getBoundingClientRect().toJSON() || null,
      diffAudit: window.__S3_FILL_QA.snapshot().diffAudit,
      /* 0718 M1b:堆叠顺序诊断(mapHead→mapRule→三联→mapKey→diffHead→diffMap,bottom 须单调递增不重叠) */
      stack: {
        mapHead: rectOf('#slotMapWrap .mapHead'), mapRule: rectOf('#slotMapWrap .mapRule'),
        slotMap: rectOf('#slotMap'), mapKey: rectOf('#slotMapWrap .mapKey'),
        diffHead: rectOf('#diffMapWrap .diffHead'), diffKey: rectOf('#diffMapWrap .diffKey')
      }
    };
  });
  let diffZoom = null;
  {
    await page.evaluate(() => window.__S3_LAYOUT_A.openMap());
    await page.waitForTimeout(350);
    const zoom = await page.evaluate(() => ({
      open: document.getElementById('s3MapOverlay').classList.contains('open'),
      mapRect: document.getElementById('slotMap').getBoundingClientRect().toJSON(),
      mapKeyVisible: getComputedStyle(document.querySelector('#slotMapWrap .mapKey')).display !== 'none',
      /* 0717 #26-4:overlay 内差异热力图已绘且非全零 */
      diffRect: document.getElementById('diffMap')?.getBoundingClientRect().toJSON() || null,
      diffAudit: window.__S3_FILL_QA.snapshot().diffAudit,
      diffKeyText: document.querySelector('#diffMapWrap .diffKey')?.textContent || ''
    }));
    diffZoom = zoom;
    pops.push({kind: 'mapZoom', rect: zoom.mapRect, inside: zoom.open && zoom.mapRect.width >= 380 && zoom.mapKeyVisible});
    await page.screenshot({path: join(OUT, 'pop_mapzoom.png'), fullPage: false});
    await page.evaluate(() => window.__S3_LAYOUT_A.closeMap());
  }
  report.popAudits = pops;
  report.diffZoom = diffZoom;

  /* W6(0720 照 02 语言重做,拍板新增):折叠收纳自检——右栏整体收边、底 dock 整体收边、
     决策卡单块收边,三者同时验证尺寸真的收缩且 __S3_LAYOUT_A.audit().collapse 如实反映态。
     结束前原样切回展开,不残留态污染后续断言。 */
  const collapseBefore = await page.evaluate(() => ({
    railW: document.getElementById('workHud').getBoundingClientRect().width,
    dockH: document.getElementById('sceneDock').getBoundingClientRect().height,
    decisionH: document.getElementById('decisionWrap').getBoundingClientRect().height
  }));
  await page.evaluate(() => {
    window.__S3_LAYOUT_A.toggleRailCollapse();
    window.__S3_LAYOUT_A.toggleDockCollapse();
    window.__S3_LAYOUT_A.toggleBlockCollapse('decisionWrap');
  });
  await page.waitForTimeout(150);
  const collapseAfter = await page.evaluate(() => ({
    railW: document.getElementById('workHud').getBoundingClientRect().width,
    dockH: document.getElementById('sceneDock').getBoundingClientRect().height,
    decisionH: document.getElementById('decisionWrap').getBoundingClientRect().height,
    audit: window.__S3_LAYOUT_A.audit().collapse
  }));
  await page.screenshot({ path: join(OUT, 'collapsed_state.png'), fullPage: false });
  await page.evaluate(() => {
    window.__S3_LAYOUT_A.toggleRailCollapse();
    window.__S3_LAYOUT_A.toggleDockCollapse();
    window.__S3_LAYOUT_A.toggleBlockCollapse('decisionWrap');
  });
  await page.waitForTimeout(150);
  report.collapseAudit = { before: collapseBefore, after: collapseAfter };

  const laneStates = {};
  for (const algorithm of ['seq', 'near', 'score', 'AUTO']) {
    laneStates[algorithm] = await page.evaluate(value => { window.__S3_FILL_QA.setAlgorithm(value); return window.__S3_FILL_QA.seekBookmark(134); }, algorithm);
  }
  /* 0717 #26-3:score 首件(G001 冷门送最远角)必须出冷门送远解说卡 */
  const firstEventState = await page.evaluate(() => {
    window.__S3_FILL_QA.setAlgorithm('score');
    return window.__S3_FILL_QA.seekEvent(0, 'LADEN_TRAVEL', .5);
  });
  await page.screenshot({path: join(OUT, 'event001_score_reserve_note.png'), fullPage: false});
  report.laneStates = laneStates;

  /* 0721 回灌 §1.6 新增断言的数据采集:同源口径声明条 / 赛段比分条节点数 / 终态总分牌三列 /
     评分瀑布 score_total 与 payload 一致(此刻 state.laneId 已被上面的 firstEventState 设为 score)/
     validator 清单 18 项 / 30-seed fetch 成功且三算法均值上屏。 */
  await page.waitForFunction(() => window.__S3_FILL_SEED_BAND_READY__ !== undefined, {timeout: 15000}).catch(() => {});
  report.raceExtras = await page.evaluate(() => {
    const banner = document.getElementById('raceBanner');
    const scoreboardNodes = document.querySelectorAll('#raceScoreboard .raceNode');
    const finalHeaders = Array.from(document.querySelectorAll('#raceFinalBoard .finalMatrix thead th')).map(el => el.textContent.trim());
    const anatomy = document.getElementById('scoreAnatomy');
    const scoreTotalText = anatomy ? (anatomy.querySelector('.scoreTotalLine b')?.textContent || '') : '';
    const seedBand = document.getElementById('raceSeedBand');
    const seedBarCount = seedBand ? seedBand.querySelectorAll('.seedBarLine').length : 0;
    const seedText = seedBand ? seedBand.textContent : '';
    const snap = window.__S3_FILL_QA.snapshot();
    return {
      bannerText: banner ? banner.textContent : '',
      scoreboardNodeCount: scoreboardNodes.length,
      finalBoardHeaders: finalHeaders,
      scoreAnatomyTotalText: scoreTotalText,
      seedBandReady: window.__S3_FILL_SEED_BAND_READY__,
      seedBandBarCount: seedBarCount,
      seedBandHasAllAlgos: /SEQ/.test(seedText) && /NEAR/.test(seedText) && /SCORE/.test(seedText) && /均值/.test(seedText),
      auditChecksLength: window.__S3_FILL_QA.auditDetail().checks.length,
      snapshotLaneId: snap.laneId,
      snapshotScoreTotal: snap.decisionEvidence.top3[0].score_terms ? snap.decisionEvidence.top3[0].score_terms.score_total : null
    };
  });
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
    /* 0721 回灌:赛马场四区块把 #workHud 内容撑高于单屏,html[data-s3-layout="A"] #workHud 已改
       overflow-y:auto——mapWrap/map 的"必须落在单屏高度内"是旧假设(内容原本一屏装完),现由
       可滚动到达替代;仍保留的是 !clipped(3D 主视口本身不缩水)、!mapClipped(三联画布真落在
       自己 wrapper 内,不是被压扁/溢出的缺陷)、hudOverflow(仅横向,见上方改动)、
       bodyScroll(页面级不产生意外整体滚动,#workHud 内部滚动已被其自身 overflow 吸收)。 */
    viewportsInside: report.viewports.every(item => !item.clipped && !item.mapClipped && item.hudOverflow.length === 0 &&
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
      report.viewports.every(item => item.axisInsideRail && item.glStartsAtTopbar),
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
    /* --- 0717 用户验收门:目标定位信息可达——dock-card 模式(0717 二轮拍板)断言目标货位卡
       可见且与 target 一致、3D 黄标牌退役;旧模式保留引线锚定判据 --- */
    beaconAnchored: report.states.every(item => {
      const audit = item.snapshot.beaconAudit;
      if (item.snapshot.target === null) return audit === null;
      if (!audit) return false;
      if (audit.mode === 'dock-card') {
        const expect = `${String(item.snapshot.target[0]).padStart(2, '0')} / ${String(item.snapshot.target[1]).padStart(2, '0')}`;
        return audit.cardVisible && audit.beaconRetired && audit.cardText === expect;
      }
      return audit.leaderVisible === true && audit.dist < 480;
    }),
    /* --- 0717 #28 用户拍板门:①目标格发光壳(amber 呼吸,入库完成转绿常亮)+格口箭头(完成收起) --- */
    fx28TargetGlowArrow: report.states.every(item => {
      const fx = item.snapshot.targetFx;
      if (!fx) return false;
      if (item.snapshot.target === null) return !fx.glowVisible && !fx.arrowVisible;
      const done = !item.name.startsWith('bookmark_') && item.snapshot.cargo.owner === 'RACK';
      return fx.glowVisible && fx.arrowVisible === !done &&
        fx.glowColor === (done ? '#2f9e4f' : '#e7b800') && fx.glowOpacity > .05 &&
        Math.abs(fx.glowPosition[0] - (item.snapshot.target[0] + .5)) < 1e-6 &&
        Math.abs(fx.glowPosition[2] - (item.snapshot.target[1] + .5)) < 1e-6;
    }),
    /* --- 0717 #28:②拟真档说明标签替换锁死下拉 --- */
    fx28TierTagLabel: report.layoutAudits.every(item => item.placement.tierTagPresent),
    /* --- W6:dock 四分列完整、当前作业格是 dock 内最宽列且货物为大字(照 02 语言重做后,
       七段微条已迁回右栏,门槛调整见 placement.cargoHeadlineDominant 处注释) --- */
    fx28DockColumnsComplete: report.layoutAudits.every(item => item.placement.dockColumnsComplete && item.placement.cargoHeadlineDominant),
    /* --- 0717 #28 二轮:货物属性行(重量+体积+频次为数据门真实字段;热门标与 sim 前 1/5 口径一致) --- */
    /* W6:重量/体积从大字行下沉到货物属性芯片行(同 02 sceneActionText/sceneCargoMeta 分工),
       kg/m³ 断言改核 meta(货物属性行),headline 现只留「步骤 · 货名」 */
    fx28CargoAttrs: report.states.filter(item => item.name.startsWith('event134_')).every(item =>
      /kg/.test(item.snapshot.cargoCard.meta) && /m³/.test(item.snapshot.cargoCard.meta) &&
      /访问频次/.test(item.snapshot.cargoCard.meta)) &&
      report.states.every(item => item.snapshot.cargoCard.hotSetSize === 53 && item.snapshot.cargoCard.hotMatches),
    /* --- 目标货位卡入 dock、镜头/倍率簇迁 3D 区悬浮小卡(W6 同 02 0720 版B)、3D 黄标牌退役 --- */
    fx28TargetCardAndTools: report.layoutAudits.every(item => item.placement.toolsFloating &&
      item.placement.targetCardInDock && item.placement.beaconRetired) &&
      report.states.every(item => item.snapshot.target === null ?
        item.snapshot.targetCard.done && item.snapshot.targetCard.slotText === '267 / 267' :
        item.snapshot.targetCard.slotText === `${String(item.snapshot.target[0]).padStart(2, '0')} / ${String(item.snapshot.target[1]).padStart(2, '0')}`),
    /* --- 0717 #26-1:2D 三联同帧对比(三 lane 同 managedCount;当前 lane 目标与 snapshot 一致) --- */
    fx26TriPanel: report.states.every(item => {
      const audit = item.snapshot.mapAudit;
      return Boolean(audit) && audit.mode === 'tri' && audit.managedCount === item.snapshot.managedCount &&
        ['seq', 'near', 'score'].every(key => key in audit.targets) &&
        (item.snapshot.target === null ? audit.targets[audit.activeLane] === null :
          JSON.stringify(audit.targets[audit.activeLane]) === JSON.stringify(item.snapshot.target));
    }) && laneStates.seq.mapAudit.activeLane === 'seq' && laneStates.score.mapAudit.activeLane === 'score',
    /* --- 0717 #26-2:热门货视觉通道(3D 金顶数=在库热门数;2D/3D 图例在位;集合口径 53) --- */
    fx26HotVisual: report.states.every(item => item.snapshot.hotVisual.hotLidCount === item.snapshot.hotVisual.hotInventoryCount &&
      item.snapshot.hotVisual.legendPresent),
    /* --- 0717 #26-3:冷门送远解说卡(score 首件 G001 出卡;热门件 G134 不出) --- */
    fx26ColdFarNote: firstEventState.reserveNotePresent === true &&
      report.states.filter(item => item.name.startsWith('event134_')).every(item => item.snapshot.reserveNotePresent === false),
    /* --- 0717 #26-4 / 0718 M1b:终态差异热力图 overlay 内已绘+rail 内常驻(均非全零、图例齐) --- */
    fx26DiffMap: Boolean(report.diffZoom) && report.diffZoom.open !== false &&
      Boolean(report.diffZoom.diffAudit) && report.diffZoom.diffAudit.nonZeroCells > 0 &&
      report.diffZoom.diffAudit.reservedCells === 133 &&
      report.diffZoom.diffRect && report.diffZoom.diffRect.width >= 200 &&
      /SCORE 放了更热门|更冷门/.test(report.diffZoom.diffKeyText) &&
      Boolean(report.railDiff) && report.railDiff.overlayOpen === false &&
      report.railDiff.display !== 'none' &&
      report.railDiff.diffRect && report.railDiff.diffRect.height > 2 && report.railDiff.diffRect.width > 2 &&
      Boolean(report.railDiff.diffAudit) && report.railDiff.diffAudit.nonZeroCells > 0,
    /* --- W6(0720 照 02 语言重做,拍板新增):折叠收纳三级(整栏/整 dock/单块)真实收缩 + 自检钩子如实 --- */
    collapseMechanismWorks: report.collapseAudit.after.railW < report.collapseAudit.before.railW - 100 &&
      report.collapseAudit.after.dockH < report.collapseAudit.before.dockH - 40 &&
      report.collapseAudit.after.decisionH < report.collapseAudit.before.decisionH - 10 &&
      report.collapseAudit.after.audit.rail === true && report.collapseAudit.after.audit.dock === true &&
      report.collapseAudit.after.audit.blocks.decisionWrap === true,
    /* --- 0721 回灌(docs/施工规格_回灌0721.md §1.6):赛马场主版面 + 决策解剖 + 证据抽屉新增门 --- */
    raceBannerDisclosure: report.raceExtras.bannerText.includes('同一到达队列'),
    raceScoreboardSixNodes: report.raceExtras.scoreboardNodeCount === 6,
    raceFinalBoardThreeColumns: ['SEQ', 'NEAR', 'SCORE'].every(label =>
      report.raceExtras.finalBoardHeaders.some(header => header.includes(label))),
    scoreAnatomyTotalMatchesPayload: report.raceExtras.snapshotLaneId === 'score' &&
      report.raceExtras.snapshotScoreTotal !== null &&
      report.raceExtras.scoreAnatomyTotalText === report.raceExtras.snapshotScoreTotal.toFixed(4),
    validatorChecksEighteen: report.raceExtras.auditChecksLength === 18,
    seedBandFetchedAndMeansShown: report.raceExtras.seedBandReady === true && report.raceExtras.seedBandBarCount === 12 &&
      report.raceExtras.seedBandHasAllAlgos
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
