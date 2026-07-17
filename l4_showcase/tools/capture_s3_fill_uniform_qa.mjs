/* 治理 C2 专项 QA(0717):uniform 对照情景装载与切换。
   覆盖:①?profile=uniform 绑定 uniform release ②payload 自证情景与下拉一致 ③治理 A+B 断言组在
   uniform lane 同样成立 ④默认(无参数)页仍绑 skew 生产 release。
   (原第⑤条"冻结页行为零变化"随 0717 目录清理退役:fill恢复候选页已挪 archive_候选历史/,
    直接 live-serve 会因页内相对资源断链;该行为锚由 v7 QA 的 hash-snapshot 机制继续承担。)
   轻量 live-serve(不做 hash snapshot):完整基线由 capture_s3_layout_a_qa.mjs / v7 QA 负责。 */
import { createRequire } from 'node:module';
import { createServer } from 'node:http';
import { fileURLToPath } from 'node:url';
import { dirname, extname, join, resolve, sep } from 'node:path';
import { existsSync, mkdirSync, readFileSync, readdirSync, statSync, writeFileSync } from 'node:fs';

const HERE = dirname(fileURLToPath(import.meta.url));
const SHOWCASE = resolve(HERE, '..');
const OUT = resolve(process.argv[2] || join(SHOWCASE, 'out', 's3_fill_uniform_qa_0717'));
const PAGE = '01_连续填仓.html';
const UNIFORM_POINTER = JSON.parse(readFileSync(join(SHOWCASE, 'out', 's3_fill_data_gate_uniform', 'latest.json'), 'utf8'));
const SKEW_POINTER = JSON.parse(readFileSync(join(SHOWCASE, 'out', 's3_fill_data_gate', 'latest.json'), 'utf8'));
const CHROME = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE ||
  'C:/Users/86177/AppData/Local/ms-playwright/chromium-1223/chrome-win64/chrome.exe';
const localRequire = createRequire(import.meta.url);
let playwright;
try { playwright = localRequire('playwright'); }
catch (error) {
  const pnpmRoot = 'C:/Users/86177/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/.pnpm';
  const packageDir = existsSync(pnpmRoot) ? readdirSync(pnpmRoot).find(name => /^playwright@/.test(name)) : null;
  if (!packageDir) throw error;
  playwright = createRequire(join(pnpmRoot, packageDir, 'node_modules', 'playwright', 'package.json'))('playwright');
}

const mime = {'.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.json': 'application/json; charset=utf-8'};
mkdirSync(OUT, {recursive: true});
const server = createServer((request, response) => {
  try {
    const pathname = decodeURIComponent(new URL(request.url, 'http://127.0.0.1').pathname).replace(/^\/+/, '');
    if (pathname === 'favicon.ico') { response.writeHead(204); response.end(); return; }
    const target = resolve(SHOWCASE, pathname);
    if (!target.startsWith(resolve(SHOWCASE) + sep) || !existsSync(target) || !statSync(target).isFile()) {
      response.writeHead(404); response.end('not found'); return;
    }
    response.writeHead(200, {'content-type': mime[extname(target)] || 'application/octet-stream', 'cache-control': 'no-store'});
    response.end(readFileSync(target));
  } catch (error) { response.writeHead(500); response.end(error.message); }
});
await new Promise(ready => server.listen(0, '127.0.0.1', ready));
const port = server.address().port;
const browser = await playwright.chromium.launch({headless: true, executablePath: CHROME});
const report = {schema: 's3-fill-uniform-qa-v1', uniformRelease: UNIFORM_POINTER.release_id,
  skewRelease: SKEW_POINTER.release_id, runtimeErrors: [], states: {}, pass: false, errors: []};

async function open(pageName, query) {
  const page = await browser.newPage({viewport: {width: 1600, height: 900}, deviceScaleFactor: 1});
  page.on('pageerror', error => report.runtimeErrors.push(`${pageName}${query}: ${error.message}`));
  page.on('console', message => { if (message.type() === 'error') report.runtimeErrors.push(`${pageName}${query} console: ${message.text()}`); });
  await page.goto(`http://127.0.0.1:${port}/src/${encodeURIComponent(pageName)}${query}`, {waitUntil: 'load'});
  await page.waitForFunction(() => window.__S3_FILL_QA?.snapshot, null, {timeout: 30000});
  return page;
}

try {
  {
    const page = await open(PAGE, '?profile=uniform');
    const laneStates = {};
    for (const algorithm of ['seq', 'near', 'score', 'AUTO']) {
      laneStates[algorithm] = await page.evaluate(value => {
        window.__S3_FILL_QA.setAlgorithm(value); return window.__S3_FILL_QA.seekBookmark(134);
      }, algorithm);
    }
    report.states.uniform = laneStates;
    await page.evaluate(() => window.__S3_FILL_QA.setAlgorithm('AUTO'));
    await page.waitForTimeout(120);
    await page.screenshot({path: join(OUT, 'uniform_layoutA_auto134.png'), fullPage: false});
    await page.evaluate(() => window.__S3_FILL_QA.setAlgorithm('near'));
    await page.waitForTimeout(120);
    await page.screenshot({path: join(OUT, 'uniform_layoutA_near134.png'), fullPage: false});
    await page.close();
  }
  {
    const page = await open(PAGE, '');
    report.states.skewDefault = await page.evaluate(() => window.__S3_FILL_QA.seekBookmark(134));
    await page.close();
  }

  const u = report.states.uniform, na = state => state.narrativeAudit;
  const assertions = {
    noRuntimeErrors: report.runtimeErrors.length === 0,
    uniformReleaseBound: Object.values(u).every(state => state.releaseId === UNIFORM_POINTER.release_id),
    uniformScenarioSelfProof: Object.values(u).every(state => na(state).scenario === 'uniform' &&
      na(state).profileSelectValue === 'uniform' && na(state).scenarioSwitchEnabled === true),
    uniformLaneBinding: u.seq.laneId === 'seq' && u.near.laneId === 'near' &&
      u.score.laneId === 'score' && u.AUTO.laneId === 'score',
    uniformGovStats: Object.values(u).every(state => {
      const order = na(state).statsSmallOrder;
      return order.length === 6 && order[0].includes('热门取货') && order[5].includes('三算法恒等') &&
        na(state).conservedCellPresent && na(state).conservedValuesEqualAcrossLanes &&
        na(state).smartRoutingTermHits === 0 && na(state).expectedRetrievalMechanismNoted;
    }),
    uniformDeltaBadges: u.score.narrativeAudit.deltaBadgeCount === 4 && u.seq.narrativeAudit.deltaBadgeCount === 0,
    uniformTieDisclosure: ['near', 'score', 'AUTO'].every(id => {
      const tie = na(u[id]).tieNote;
      return tie.top1TieSize > 1 ? tie.present && tie.isochroneNoted : !tie.present;
    }) && na(u.seq).tieNote.present === false,
    skewDefaultUntouched: report.states.skewDefault.releaseId === SKEW_POINTER.release_id &&
      na(report.states.skewDefault).scenario === 'skew' &&
      na(report.states.skewDefault).profileSelectValue === 'skew' &&
      na(report.states.skewDefault).scenarioSwitchEnabled === true
  };
  report.assertions = assertions; report.pass = Object.values(assertions).every(Boolean);
  report.errors = Object.entries(assertions).filter(([, value]) => !value).map(([key]) => key);
} catch (error) {
  report.pass = false;
  report.errors.push(`qa_exception:${error.name}:${error.message}`);
} finally {
  await browser.close(); await new Promise(done => server.close(done));
}

writeFileSync(join(OUT, 'qa_report.json'), JSON.stringify(report, null, 2), 'utf8');
process.stdout.write(`${report.pass ? 'PASS' : 'FAIL'} ${Object.values(report.assertions || {}).filter(Boolean).length}/${Object.keys(report.assertions || {}).length}; ${join(OUT, 'qa_report.json')}\n`);
if (!report.pass) process.exitCode = 1;
