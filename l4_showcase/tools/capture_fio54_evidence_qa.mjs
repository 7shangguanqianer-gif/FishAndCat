/* 54 格 FIO 证据页验收 QA(0717,任务信验收条 1-7):
   三视口无裁切/无水平滚动、控制台零错误、全部图片资源加载成功(无 404)、
   口径带常驻、"20×20"仅出现在边界说明语境、越界表述零命中、三张验收图落盘。 */
import { createRequire } from 'node:module';
import { createServer } from 'node:http';
import { extname, join, resolve, sep } from 'node:path';
import { existsSync, mkdirSync, readFileSync, readdirSync, statSync, writeFileSync } from 'node:fs';

const ROOT = 'F:/abb_wh_work';
const PAGE = 'l4_showcase/src/03_FIO物理证据.html';
const OUT = join(ROOT, 'l4_showcase', 'out', 'fio54_evidence_qa_0717');
const CHROME = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE ||
  'C:/Users/86177/AppData/Local/ms-playwright/chromium-1223/chrome-win64/chrome.exe';
const localRequire = createRequire(import.meta.url);
let playwright;
try { playwright = localRequire('playwright'); }
catch {
  const pnpmRoot = 'C:/Users/86177/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/.pnpm';
  const dir = readdirSync(pnpmRoot).find(n => /^playwright@/.test(n));
  playwright = createRequire(join(pnpmRoot, dir, 'node_modules', 'playwright', 'package.json'))('playwright');
}
const mime = {'.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.png': 'image/png', '.jpg': 'image/jpeg'};
mkdirSync(OUT, {recursive: true});
const server = createServer((req, res) => {
  try {
    const pathname = decodeURIComponent(new URL(req.url, 'http://127.0.0.1').pathname).replace(/^\/+/, '');
    if (pathname === 'favicon.ico') { res.writeHead(204); res.end(); return; }
    const target = resolve(ROOT, pathname);
    if (!target.startsWith(resolve(ROOT) + sep) || !existsSync(target) || !statSync(target).isFile()) {
      res.writeHead(404); res.end('nf'); return;
    }
    res.writeHead(200, {'content-type': mime[extname(target)] || 'application/octet-stream'});
    res.end(readFileSync(target));
  } catch (e) { res.writeHead(500); res.end(e.message); }
});
await new Promise(r => server.listen(0, '127.0.0.1', r));
const port = server.address().port;
const browser = await playwright.chromium.launch({headless: true, executablePath: CHROME});
const report = {schema: 'fio54-evidence-qa-v1', consoleErrors: [], failedRequests: [], viewports: [], pass: false, errors: []};
const url = `http://127.0.0.1:${port}/${PAGE.split('/').map(encodeURIComponent).join('/')}`;

try {
  let textAudit = null;
  for (const [w, h] of [[1280, 720], [1440, 900], [1920, 1080]]) {
    const page = await browser.newPage({viewport: {width: w, height: h}});
    page.on('pageerror', e => report.consoleErrors.push(`${w}x${h}: ${e.message}`));
    page.on('console', m => { if (m.type() === 'error') report.consoleErrors.push(`${w}x${h} console: ${m.text()}`); });
    page.on('requestfailed', r => report.failedRequests.push(`${w}x${h}: ${r.url()}`));
    page.on('response', r => { if (r.status() >= 400) report.failedRequests.push(`${w}x${h} ${r.status()}: ${r.url()}`); });
    await page.goto(url, {waitUntil: 'networkidle'});
    const audit = await page.evaluate(() => {
      const imgs = [...document.images].map(i => ({src: i.getAttribute('src'), ok: i.complete && i.naturalWidth > 0}));
      const band = document.getElementById('scopeBand');
      const bandVisible = band && band.getBoundingClientRect().top >= 0 && getComputedStyle(band).position === 'sticky';
      const body = document.body.innerText; // 渲染文本,不含 script 源码
      // "20×20" 语境审计:每处出现点前后 60 字符必须含边界词(非/不等同/No-Go 等)
      const ctxs = [];
      let i = -1;
      while ((i = body.indexOf('20×20', i + 1)) !== -1) ctxs.push(body.slice(Math.max(0, i - 60), i + 66));
      const boundaryWords = /非|不等同|不宣称|No-Go|不做|不证明|映射|孪生|边界/;
      // 越界词审计:出现本身合法当且仅当处于否定/边界语境(不|非|未|禁|≠|不等同)
      const risky = ['完全闭环', '数字孪生', '400 格物理实现', '在线实测'];
      const riskyViolations = [];
      for (const term of risky) {
        let j = -1;
        while ((j = body.indexOf(term, j + 1)) !== -1) {
          const ctx = body.slice(Math.max(0, j - 30), j + term.length + 20);
          if (!/不|非|未|禁|≠|No-Go|边界/.test(ctx)) riskyViolations.push(ctx);
        }
      }
      return {
        imgs, bandVisible,
        hScroll: document.documentElement.scrollWidth > innerWidth + 1,
        ctx2020: ctxs, ctx2020AllBounded: ctxs.length > 0 && ctxs.every(c => boundaryWords.test(c)),
        riskyViolations, forbiddenHit: riskyViolations.length > 0,
        blindCheck: /54 格/.test(body) && /物理 I\/O/.test(body) && band.textContent.includes('技术预演')
      };
    });
    report.viewports.push({w, h, ...audit});
    await page.screenshot({path: join(OUT, `viewport_${w}x${h}_首屏.png`)});
    if (w === 1440) {
      await page.click('#chain button:nth-of-type(1)');
      await page.evaluate(() => document.querySelector('#stationDetail details').open = true);
      await page.screenshot({path: join(OUT, '验收图2_IO链展开.png')});
      await page.evaluate(() => document.getElementById('neg').scrollIntoView());
      await page.screenshot({path: join(OUT, '验收图3_边界与负结果.png')});
    }
    await page.close();
    if (!textAudit) textAudit = audit;
  }
  const a = report.assertions = {
    noConsoleErrors: report.consoleErrors.length === 0,
    noFailedRequests: report.failedRequests.length === 0,
    allImagesLoaded: report.viewports.every(v => v.imgs.length >= 1 && v.imgs.every(i => i.ok)),
    scopeBandSticky: report.viewports.every(v => v.bandVisible),
    noHorizontalScroll: report.viewports.every(v => !v.hScroll),
    grid2020OnlyInBoundary: report.viewports.every(v => v.ctx2020.length > 0 && v.ctx2020AllBounded),
    noForbiddenTerms: report.viewports.every(v => !v.forbiddenHit),
    blindFiveSecond: report.viewports.every(v => v.blindCheck)
  };
  report.pass = Object.values(a).every(Boolean);
  report.errors = Object.entries(a).filter(([, v]) => !v).map(([k]) => k);
} catch (e) {
  report.pass = false; report.errors.push(`qa_exception:${e.message}`);
} finally {
  await browser.close(); await new Promise(r => server.close(r));
}
writeFileSync(join(OUT, 'qa_report.json'), JSON.stringify(report, null, 2), 'utf8');
process.stdout.write(`${report.pass ? 'PASS' : 'FAIL'} ${Object.values(report.assertions || {}).filter(Boolean).length}/${Object.keys(report.assertions || {}).length}; ${join(OUT, 'qa_report.json')}\n`);
if (!report.pass) process.exitCode = 1;
