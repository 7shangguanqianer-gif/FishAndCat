/* 02_入出闭环.html · mixed 页启动+治理 QA(0718 M4b 起步版)
   范围=本增量已交付的部分:运行时可启动(trace 驱动、0 错误、120 库存)+ 核心治理文案
   (AUTO 精确话术「规则路由」、禁词「智能路由」零命中、五 lane 齐)。
   未覆盖(A 壳 rail 布局/cycle 轴 0-25-50-75-100/取货实测块=用户在场迭代后再补断言)。 */
import { createRequire } from 'node:module';
import { createServer } from 'node:http';
import { fileURLToPath } from 'node:url';
import { dirname, extname, join, resolve, sep } from 'node:path';
import { existsSync, readFileSync, readdirSync, mkdirSync, writeFileSync } from 'node:fs';

const HERE = dirname(fileURLToPath(import.meta.url));
const SHOWCASE = resolve(HERE, '..');
const PAGE = '02_入出闭环.html';
const OUT = resolve(process.argv[2] || join(SHOWCASE, 'out', 's3_mixed_layout_a_qa_0718'));
mkdirSync(OUT, { recursive: true });
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

const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8', '.json': 'application/json; charset=utf-8',
  '.png': 'image/png', '.mjs': 'text/javascript; charset=utf-8' };

const server = createServer((req, res) => {
  try {
    const urlPath = decodeURIComponent(req.url.split('?')[0]);
    const filePath = resolve(join(SHOWCASE, urlPath));
    if (!filePath.startsWith(SHOWCASE + sep) && filePath !== SHOWCASE) { res.writeHead(403); res.end(); return; }
    if (!existsSync(filePath)) { res.writeHead(404); res.end(); return; }
    res.writeHead(200, { 'Content-Type': MIME[extname(filePath)] || 'application/octet-stream' });
    res.end(readFileSync(filePath));
  } catch { res.writeHead(500); res.end(); }
});

const report = { page: PAGE, runtimeErrors: [], consoleErrors: [], boot: null, gov: null, pass: false, errors: [] };
await new Promise(r => server.listen(0, '127.0.0.1', r));
const port = server.address().port;
const pageUrl = `http://127.0.0.1:${port}/src/${encodeURIComponent(PAGE)}`;
const browser = await chromium.launch({ executablePath: CHROME, args: ['--use-angle=d3d11', '--enable-unsafe-swiftshader'] });
try {
  const page = await browser.newPage({ viewport: { width: 1600, height: 900 }, deviceScaleFactor: 1 });
  page.on('pageerror', e => report.runtimeErrors.push(e.message));
  page.on('console', m => { if (m.type() === 'error') report.consoleErrors.push(m.text()); });
  await page.goto(pageUrl, { waitUntil: 'load' });
  await page.waitForFunction(() => { try { return !!window.__S3_QA && !window.__S3_QA.snapshot().loading; } catch { return false; } }, { timeout: 30000 });
  await page.waitForTimeout(400);
  report.boot = await page.evaluate(() => {
    const s = window.__S3_QA.snapshot();
    return { booted: true, traceId: s.traceId, loading: s.loading, runtimeErrors: s.runtimeErrors,
      invCount: s.renderer?.inventorySize, phase: s.renderer?.phaseName, query: s.query };
  });
  report.gov = await page.evaluate(() => {
    const auto = document.querySelector('#strategySelect option[value="AUTO"]');
    return {
      autoText: auto ? auto.textContent : null,
      hasBadName: /智能路由/.test(document.body.innerHTML),
      lanes: [...document.querySelectorAll('#strategySelect option')].map(o => o.value),
      awraOfflineGroup: !!document.querySelector('#strategySelect optgroup[label*="离线"]'),
    };
  });
  await page.screenshot({ path: join(OUT, 'mixed_02_boot.png'), fullPage: false });
  const a = {
    booted: report.boot.booted === true && report.boot.loading === false,
    runtimeErrors0: report.boot.runtimeErrors === 0 && report.runtimeErrors.length === 0,
    inventory120: report.boot.invCount === 120,
    traceDriven: typeof report.boot.traceId === 'string' && report.boot.traceId.length > 0,
    autoRuleRouting: /规则路由|启动时一次选定/.test(report.gov.autoText || ''),
    no智能路由: report.gov.hasBadName === false,
    fiveLanes: JSON.stringify(report.gov.lanes) === JSON.stringify(['seq', 'near', 'score', 'AUTO', 'awra']),
    awraOfflineDisclosed: report.gov.awraOfflineGroup === true,
  };
  report.assertions = a; report.pass = Object.values(a).every(Boolean);
  report.errors = Object.entries(a).filter(([, v]) => !v).map(([k]) => k);
} catch (e) {
  report.pass = false; report.errors.push(`qa_exception:${e.name}:${e.message}`);
} finally {
  await browser.close(); await new Promise(r => server.close(r));
}
writeFileSync(join(OUT, 'qa_report.json'), JSON.stringify(report, null, 1), 'utf8');
console.log(`${report.pass ? 'PASS' : 'FAIL'} ${Object.values(report.assertions || {}).filter(Boolean).length}/${Object.keys(report.assertions || {}).length}; ${join(OUT, 'qa_report.json')}`);
if (!report.pass) { console.log('errors:', report.errors.join(', ')); process.exitCode = 1; }
