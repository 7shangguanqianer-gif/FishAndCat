/* PoC 验证脚本(node 直跑:node poc_verify.js)。
   用 electron 可执行程序以 --remote-debugging-port 启动 app_shell/main.js 两次(file 模式 / http 模式各一次),
   再用项目已装的 playwright(createRequire 回退到 codex 运行时 pnpm 目录,不作为 app_shell 依赖新增)
   connectOverCDP 连上抓取,核对:
     1. 00 导览页加载零 pageerror
     2. 导航到 02_入出闭环.html:__S3_QA 就绪且 !loading、three.js WebGL 画面渲染非全白、snapshot() 数据正常
     3. localStorage 写读回(setItem 后 reload 仍在)
   产物:app_shell/out/poc_file_mode.png、poc_http_mode.png、poc_report.json。
   纪律:只读 ../src 与 ../out,不写任何 app_shell 之外的文件。 */
'use strict';

const { spawn } = require('node:child_process');
const { createRequire } = require('node:module');
const path = require('node:path');
const fs = require('node:fs');
const { pathToFileURL } = require('node:url');

const APP_DIR = __dirname;
const SHOWCASE_ROOT = path.resolve(APP_DIR, '..');
const OUT_DIR = path.join(APP_DIR, 'out');
fs.mkdirSync(OUT_DIR, { recursive: true });

/* ---------- 解析 playwright:项目已装,不作为 app_shell 依赖新增;回退 codex 运行时 pnpm 目录 ---------- */
function resolvePlaywright() {
  const localRequire = createRequire(__filename);
  try {
    return localRequire('playwright');
  } catch (error) {
    const bundledNodeModules = process.env.CODEX_NODE_MODULES ||
      'C:/Users/86177/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules';
    const pnpmRoot = path.join(bundledNodeModules, '.pnpm');
    const packageDir = fs.existsSync(pnpmRoot)
      ? fs.readdirSync(pnpmRoot).find(name => /^playwright@/.test(name))
      : null;
    if (!packageDir) throw error;
    const pkgJsonPath = path.join(pnpmRoot, packageDir, 'node_modules', 'playwright', 'package.json');
    return createRequire(pkgJsonPath)('playwright');
  }
}

const { chromium } = resolvePlaywright();

/* ---------- 解析 electron 可执行文件(app_shell 自己的 devDependency) ---------- */
const electronPath = createRequire(path.join(APP_DIR, 'package.json'))('electron');
if (typeof electronPath !== 'string' || !fs.existsSync(electronPath)) {
  throw new Error(`electron 可执行文件解析失败: ${JSON.stringify(electronPath)}(先跑 npm install)`);
}

/* ---------- 小工具 ---------- */
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

async function waitForCdp(port, timeoutMs = 20000) {
  const deadline = Date.now() + timeoutMs;
  let lastError = null;
  while (Date.now() < deadline) {
    try {
      const res = await fetch(`http://127.0.0.1:${port}/json/version`);
      if (res.ok) return await res.json();
    } catch (error) { lastError = error; }
    await sleep(100);
  }
  throw new Error(`CDP 端口 ${port} 在 ${timeoutMs}ms 内未就绪: ${lastError && lastError.message}`);
}

async function waitForPage(browser, timeoutMs = 20000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    for (const context of browser.contexts()) {
      for (const page of context.pages()) {
        if (!page.url().startsWith('devtools://')) return page;
      }
    }
    await sleep(100);
  }
  throw new Error(`${timeoutMs}ms 内未发现可用 page target`);
}

function toFileUrl(relPathFromShowcase) {
  return pathToFileURL(path.join(SHOWCASE_ROOT, ...relPathFromShowcase.split('/'))).href;
}

function toHttpUrl(port, relPathFromShowcase) {
  const encoded = relPathFromShowcase.split('/').map(encodeURIComponent).join('/');
  return `http://127.0.0.1:${port}/${encoded}`;
}

function parseShellInfo(stdoutText) {
  const match = stdoutText.match(/\[shell-info\]\s+(\{.*\})/);
  return match ? JSON.parse(match[1]) : null;
}

async function gotoAndCollectErrors(page, url, errorsBucket) {
  errorsBucket.pageErrors.length = 0;
  errorsBucket.consoleErrors.length = 0;
  await page.goto(url, { waitUntil: 'load', timeout: 30000 });
  return {
    url,
    pageErrorCount: errorsBucket.pageErrors.length,
    consoleErrorCount: errorsBucket.consoleErrors.length,
    pageErrorSamples: errorsBucket.pageErrors.slice(0, 3),
    consoleErrorSamples: errorsBucket.consoleErrors.slice(0, 3)
  };
}

async function waitS3QaReady(page, timeoutMs = 30000) {
  const startedAt = Date.now();
  await page.waitForFunction(() => {
    try { return !!window.__S3_QA && !window.__S3_QA.snapshot().loading; } catch { return false; }
  }, { timeout: timeoutMs });
  await page.waitForTimeout(300);
  return Date.now() - startedAt;
}

/* 与 tools/capture_s3_task12_qa.mjs:461-467 同一手法(renderer.render 后 drawImage+getImageData 读像素),
   复用本项目已验证的做法,而非另造一套截图判空逻辑。 */
async function checkWebglNonBlank(page) {
  return page.evaluate(() => {
    try {
      if (typeof renderer === 'undefined' || typeof scene === 'undefined' || typeof camera === 'undefined') {
        return { ok: false, reason: 'renderer/scene/camera 全局未找到' };
      }
      renderer.render(scene, camera);
      const source = renderer.domElement;
      const probe = document.createElement('canvas');
      probe.width = source.width; probe.height = source.height;
      const ctx = probe.getContext('2d', { willReadFrequently: true });
      ctx.drawImage(source, 0, 0);
      const pixels = ctx.getImageData(0, 0, probe.width, probe.height).data;
      let minV = 255, maxV = 0, sum = 0;
      const count = pixels.length / 4;
      for (let i = 0; i < pixels.length; i += 4) {
        const v = (pixels[i] + pixels[i + 1] + pixels[i + 2]) / 3;
        if (v < minV) minV = v;
        if (v > maxV) maxV = v;
        sum += v;
      }
      return { ok: true, width: probe.width, height: probe.height, minV, maxV, range: maxV - minV, meanV: sum / count };
    } catch (error) {
      return { ok: false, reason: String((error && error.message) || error) };
    }
  });
}

async function checkSnapshotData(page) {
  return page.evaluate(() => {
    try {
      const s = window.__S3_QA.snapshot();
      return { ok: true, traceId: s.traceId || null, loading: s.loading, runtimeErrorCount: (s.runtimeErrors || []).length, query: s.query || null };
    } catch (error) {
      return { ok: false, reason: String((error && error.message) || error) };
    }
  });
}

async function checkLocalStorageRoundTrip(page) {
  const marker = `__shell_poc_${Date.now()}__`;
  const before = await page.evaluate(key => {
    localStorage.setItem(key, 'ok');
    return localStorage.getItem(key);
  }, marker);
  await page.reload({ waitUntil: 'load', timeout: 30000 });
  await page.waitForTimeout(200);
  const after = await page.evaluate(key => localStorage.getItem(key), marker);
  return { marker, before, after, persisted: before === 'ok' && after === 'ok' };
}

/* ---------- 单模式完整流程 ---------- */
async function runMode(mode, cdpPort) {
  const env = Object.assign({}, process.env, { SHELL_MODE: mode });
  delete env.ELECTRON_RUN_AS_NODE; /* 防止继承自宿主进程,导致 electron.exe 被当纯 node 跑,不建窗口/不开 CDP */
  const args = [APP_DIR, `--remote-debugging-port=${cdpPort}`];
  const child = spawn(electronPath, args, { cwd: APP_DIR, env, stdio: ['ignore', 'pipe', 'pipe'] });

  let stdoutBuf = '', stderrBuf = '';
  child.stdout.on('data', chunk => { stdoutBuf += chunk.toString('utf8'); });
  child.stderr.on('data', chunk => { stderrBuf += chunk.toString('utf8'); });
  let exitInfo = null;
  child.on('exit', (code, signal) => { exitInfo = { code, signal }; });

  const result = { mode, cdpPort, ok: false, errors: [] };
  let browser = null;
  try {
    await waitForCdp(cdpPort, 20000);
    browser = await chromium.connectOverCDP(`http://127.0.0.1:${cdpPort}`);
    const page = await waitForPage(browser, 20000);

    const errorsBucket = { pageErrors: [], consoleErrors: [] };
    page.on('pageerror', error => errorsBucket.pageErrors.push(String((error && error.message) || error)));
    page.on('console', message => { if (message.type() === 'error') errorsBucket.consoleErrors.push(message.text()); });

    let shellInfo = parseShellInfo(stdoutBuf);
    for (let i = 0; i < 30 && !shellInfo; i += 1) { await sleep(100); shellInfo = parseShellInfo(stdoutBuf); }
    result.shellInfo = shellInfo;
    if (mode === 'http' && (!shellInfo || !shellInfo.httpPort)) throw new Error('http 模式未拿到 shellInfo.httpPort(主进程未打印或静态服务未起)');

    const url00 = mode === 'file' ? toFileUrl('src/00_导览.html') : toHttpUrl(shellInfo.httpPort, 'src/00_导览.html');
    const url02 = mode === 'file' ? toFileUrl('src/02_入出闭环.html') : toHttpUrl(shellInfo.httpPort, 'src/02_入出闭环.html');

    result.page00 = await gotoAndCollectErrors(page, url00, errorsBucket);

    result.page02 = await gotoAndCollectErrors(page, url02, errorsBucket);
    result.page02.s3qaReadyMs = await waitS3QaReady(page, 30000);
    /* waitS3QaReady 期间可能又有异步 pageerror/console.error,补读一次计数 */
    result.page02.pageErrorCount = errorsBucket.pageErrors.length;
    result.page02.consoleErrorCount = errorsBucket.consoleErrors.length;
    result.page02.pageErrorSamples = errorsBucket.pageErrors.slice(0, 3);
    result.page02.consoleErrorSamples = errorsBucket.consoleErrors.slice(0, 3);

    result.webgl = await checkWebglNonBlank(page);
    result.snapshotData = await checkSnapshotData(page);
    result.viewport = await page.evaluate(() => ({ innerWidth: window.innerWidth, innerHeight: window.innerHeight, devicePixelRatio: window.devicePixelRatio }));

    const screenshotPath = path.join(OUT_DIR, `poc_${mode}_mode.png`);
    await page.screenshot({ path: screenshotPath });
    result.screenshot = { path: screenshotPath };

    result.localStorage = await checkLocalStorageRoundTrip(page);

    result.ok = true;
  } catch (error) {
    result.errors.push(String((error && error.stack) || error));
  } finally {
    try { if (browser) await browser.close(); } catch { /* noop:CDP 断开失败不影响后续强杀进程 */ }
    if (child.exitCode === null && !child.killed) child.kill();
    const killDeadline = Date.now() + 5000;
    while (exitInfo === null && Date.now() < killDeadline) { await sleep(50); }
    if (exitInfo === null) { try { child.kill('SIGKILL'); } catch { /* noop */ } }
  }
  result.exitInfo = exitInfo;
  result.stderrTail = stderrBuf.split(/\r?\n/).filter(Boolean).slice(-20);
  return result;
}

async function main() {
  const results = {};
  results.file = await runMode('file', 9522);
  await sleep(500); /* 给上一个 electron 进程端口/锁完全释放留余量 */
  results.http = await runMode('http', 9523);

  const reportPath = path.join(OUT_DIR, 'poc_report.json');
  fs.writeFileSync(reportPath, JSON.stringify(results, null, 2), 'utf8');

  console.log('\n==== PoC 验证结果(JSON 已写入 ' + reportPath + ') ====');
  console.log(JSON.stringify(results, null, 2));
}

main().catch(error => {
  console.error('poc_verify 顶层失败: ' + ((error && error.stack) || error));
  process.exit(1);
});
