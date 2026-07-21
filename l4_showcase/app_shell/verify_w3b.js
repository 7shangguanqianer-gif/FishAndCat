/* W3b 融合导航壳验收脚本(node 直跑:node verify_w3b.js)。
   两次启动 electron(SHELL_MODE=http,固定 SHELL_HTTP_PORT 以便跨进程重启保持同源,
   这样才能有意义地验证「重启清 localStorage」——随机端口的话不清也会因换源而看不到旧 key,
   测试会假阳性),playwright connectOverCDP 连上做验收:
     第一次启动:a 启动页截图 / b 进入02(iframe __S3_QA 就绪+WebGL 非全白+零 pageerror)/
                c 侧栏切01、03(各自就绪信号+零 pageerror)/ d 关于窗口(版本号非空)/
                e 写 localStorage 探针 key / f F11 全屏(侧栏仍渲染)
     第二次启动(全新进程,同端口):e 核验探针 key 已不在(证明 clearStorageData 每次启动生效一次)
   产物:app_shell/out/w3b/{launch,page02,page01,page03,about,fullscreen}.png + verify_report.json
   纪律:不改 main.js/preload.js/shell.html/launch.html 之外的行为,不碰 src/、tools/、docs/。 */
'use strict';

const { spawn } = require('node:child_process');
const { createRequire } = require('node:module');
const path = require('node:path');
const fs = require('node:fs');

const APP_DIR = __dirname;
const OUT_DIR = path.join(APP_DIR, 'out', 'w3b');
fs.mkdirSync(OUT_DIR, { recursive: true });

/* ---------- 解析 playwright(与 poc_verify.js 完全同一手法,项目已装不新增依赖) ---------- */
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
const electronPath = createRequire(path.join(APP_DIR, 'package.json'))('electron');
if (typeof electronPath !== 'string' || !fs.existsSync(electronPath)) {
  throw new Error(`electron 可执行文件解析失败: ${JSON.stringify(electronPath)}(先跑 npm install)`);
}

const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
const FIXED_PORT = 47129;

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

async function waitForShellPage(browser, timeoutMs = 20000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    for (const context of browser.contexts()) {
      for (const page of context.pages()) {
        if (page.url().includes('shell.html')) return page;
      }
    }
    await sleep(100);
  }
  throw new Error(`${timeoutMs}ms 内未发现 shell.html page target`);
}

function parseShellInfo(stdoutText) {
  const match = stdoutText.match(/\[shell-info\]\s+(\{.*\})/);
  return match ? JSON.parse(match[1]) : null;
}

function launchElectron(cdpPort) {
  const env = Object.assign({}, process.env, { SHELL_MODE: 'http', SHELL_HTTP_PORT: String(FIXED_PORT) });
  delete env.ELECTRON_RUN_AS_NODE;
  const args = [APP_DIR, `--remote-debugging-port=${cdpPort}`];
  const child = spawn(electronPath, args, { cwd: APP_DIR, env, stdio: ['ignore', 'pipe', 'pipe'] });
  let stdoutBuf = '', stderrBuf = '';
  child.stdout.on('data', chunk => { stdoutBuf += chunk.toString('utf8'); });
  child.stderr.on('data', chunk => { stderrBuf += chunk.toString('utf8'); });
  return {
    child,
    get stdoutBuf() { return stdoutBuf; },
    get stderrBuf() { return stderrBuf; }
  };
}

async function killChild(child) {
  if (child.exitCode === null && !child.killed) child.kill();
  const deadline = Date.now() + 5000;
  while (child.exitCode === null && Date.now() < deadline) await sleep(50);
  if (child.exitCode === null) { try { child.kill('SIGKILL'); } catch { /* noop */ } }
}

/* 与 poc_verify.js 同一手法(renderer.render 后 drawImage+getImageData 读像素判非全白)。 */
function webglCheckFn() {
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
}

async function findChildFrame(page, urlIncludes, timeoutMs = 20000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const frame = page.frames().find(f => f.url().includes(urlIncludes));
    if (frame) return frame;
    await sleep(100);
  }
  throw new Error(`${timeoutMs}ms 内未发现 URL 含「${urlIncludes}」的 iframe`);
}

async function waitS3QaReady(frame, timeoutMs = 30000) {
  const startedAt = Date.now();
  await frame.waitForFunction(() => {
    try { return !!window.__S3_QA && !window.__S3_QA.snapshot().loading; } catch { return false; }
  }, { timeout: timeoutMs });
  await sleep(300);
  return Date.now() - startedAt;
}

async function waitThreeReady(frame, timeoutMs = 30000) {
  const startedAt = Date.now();
  await frame.waitForFunction(() => {
    try { return typeof renderer !== 'undefined' && typeof scene !== 'undefined' && typeof camera !== 'undefined'; } catch { return false; }
  }, { timeout: timeoutMs });
  await sleep(500);
  return Date.now() - startedAt;
}

async function waitViewImgReady(frame, timeoutMs = 20000) {
  const startedAt = Date.now();
  await frame.waitForFunction(() => {
    const img = document.getElementById('viewImg');
    return !!(img && img.getAttribute('src'));
  }, { timeout: timeoutMs });
  await sleep(300);
  return Date.now() - startedAt;
}

/* page.keyboard.press('F11') 经排查在本 CDP 连接下不带 windowsVirtualKeyCode,
   Electron before-input-event 收不到可识别的 F11(诊断见 scratchpad/diag_f11.js 与 diag_f11b.js:
   高层 keyboard.press 全程 0 次 [shell-fullscreen] 日志;换原始 Input.dispatchKeyEvent 显式带
   windowsVirtualKeyCode:122 后主进程立即打印 isFullScreen=true)。改走原始 CDP 派发,与应用代码无关。 */
async function pressF11(cdpSession) {
  const base = { key: 'F11', code: 'F11', windowsVirtualKeyCode: 122, nativeVirtualKeyCode: 122, unmodifiedText: '', text: '' };
  await cdpSession.send('Input.dispatchKeyEvent', Object.assign({ type: 'rawKeyDown' }, base));
  await cdpSession.send('Input.dispatchKeyEvent', Object.assign({ type: 'keyUp' }, base));
}

async function overrideDeviceMetrics1600x900(page) {
  const cdp = await page.context().newCDPSession(page);
  await cdp.send('Emulation.setDeviceMetricsOverride', { width: 1600, height: 900, deviceScaleFactor: 1, mobile: false });
  return cdp;
}

async function clearDeviceMetrics(cdp) {
  try { await cdp.send('Emulation.clearDeviceMetricsOverride'); } catch { /* noop */ }
}

const REQUIRED_STEPS = ['a_launch', 'b_page02', 'c_page01', 'c_page03', 'd_about', 'e_write_marker', 'f_fullscreen', 'e_verify_cleared'];

async function main() {
  const report = { startedAt: new Date().toISOString(), steps: [] };

  /* ========== 第一次启动:a/b/c/d/e(写)/f ========== */
  const CDP_PORT_1 = 9531;
  const launch1 = launchElectron(CDP_PORT_1);
  let browser1 = null;
  try {
    await waitForCdp(CDP_PORT_1, 20000);
    browser1 = await chromium.connectOverCDP(`http://127.0.0.1:${CDP_PORT_1}`);
    const page = await waitForShellPage(browser1, 20000);

    const pageErrors = [];
    const consoleErrors = [];
    page.on('pageerror', error => pageErrors.push(String((error && error.message) || error)));
    page.on('console', message => { if (message.type() === 'error') consoleErrors.push(message.text()); });

    let shellInfo = parseShellInfo(launch1.stdoutBuf);
    for (let i = 0; i < 50 && !shellInfo; i += 1) { await sleep(100); shellInfo = parseShellInfo(launch1.stdoutBuf); }
    report.shellInfo = shellInfo;
    if (!shellInfo || !shellInfo.httpPort) throw new Error('未拿到 shellInfo.httpPort(主进程未打印或静态服务未起)');

    await page.waitForFunction(() => !!window.__SHELL_READY__, { timeout: 20000 });
    const cdpMetrics = await overrideDeviceMetrics1600x900(page);

    /* ---- a) 启动页渲染截图 ---- */
    const launchFrame = await findChildFrame(page, 'launch.html');
    await launchFrame.waitForFunction(() => !!window.__LAUNCH_READY__, { timeout: 20000 });
    await sleep(300);
    await page.screenshot({ path: path.join(OUT_DIR, 'launch.png') });
    report.steps.push({ step: 'a_launch', ok: pageErrors.length === 0, pageErrorCount: pageErrors.length });

    /* ---- b) 「进入 02」→ iframe 内 __S3_QA 就绪 + WebGL 非全白 + 零 pageerror ---- */
    pageErrors.length = 0; consoleErrors.length = 0;
    await launchFrame.click('button[data-nav-target="02"]');
    const frame02 = await findChildFrame(page, '02_');
    const s3qaReadyMs = await waitS3QaReady(frame02, 30000);
    const webgl02 = await frame02.evaluate(webglCheckFn);
    await sleep(200);
    await page.screenshot({ path: path.join(OUT_DIR, 'page02.png') });
    report.steps.push({
      step: 'b_page02',
      ok: !!webgl02.ok && webgl02.range > 5 && pageErrors.length === 0,
      s3qaReadyMs, webgl: webgl02, pageErrorCount: pageErrors.length,
      pageErrorSamples: pageErrors.slice(0, 3), consoleErrorCount: consoleErrors.length
    });

    /* ---- c) 侧栏切 01 ---- */
    pageErrors.length = 0; consoleErrors.length = 0;
    await page.click('.rail-item[data-key="01"] .rail-icon');
    const frame01 = await findChildFrame(page, '01_');
    const threeReadyMs = await waitThreeReady(frame01, 30000);
    const webgl01 = await frame01.evaluate(webglCheckFn);
    await sleep(200);
    await page.screenshot({ path: path.join(OUT_DIR, 'page01.png') });
    report.steps.push({
      step: 'c_page01',
      ok: !!webgl01.ok && webgl01.range > 5 && pageErrors.length === 0,
      threeReadyMs, webgl: webgl01, pageErrorCount: pageErrors.length, pageErrorSamples: pageErrors.slice(0, 3)
    });

    /* ---- c) 侧栏切 03 ---- */
    pageErrors.length = 0; consoleErrors.length = 0;
    await page.click('.rail-item[data-key="03"] .rail-icon');
    const frame03 = await findChildFrame(page, '03_');
    const viewImgReadyMs = await waitViewImgReady(frame03, 20000);
    await sleep(200);
    await page.screenshot({ path: path.join(OUT_DIR, 'page03.png') });
    report.steps.push({
      step: 'c_page03', ok: pageErrors.length === 0,
      viewImgReadyMs, pageErrorCount: pageErrors.length, pageErrorSamples: pageErrors.slice(0, 3)
    });

    /* ---- d) 关于窗口 ---- */
    await page.click('.rail-item[data-key="about"] .rail-icon');
    await page.waitForSelector('#aboutDialog[open]', { timeout: 5000 });
    const versions = await page.evaluate(() => ({
      electron: document.getElementById('verElectron').textContent,
      chrome: document.getElementById('verChrome').textContent,
      node: document.getElementById('verNode').textContent
    }));
    await sleep(150);
    await page.screenshot({ path: path.join(OUT_DIR, 'about.png') });
    report.steps.push({ step: 'd_about', ok: !!(versions.electron && versions.electron !== '-'), versions });
    await page.click('#aboutClose');
    /* <dialog> 没 open 属性时 UA 样式表判 display:none,天然不可能是「visible」——
       用 waitForSelector(':not([open])',{state:'visible'}) 会永久超时,改用 .open 属性直接判。 */
    await page.waitForFunction(() => document.getElementById('aboutDialog').open === false, { timeout: 5000 });

    /* ---- e) 写 localStorage 探针(第二次启动核验清空) ---- */
    const marker = '__w3b_persist_probe__';
    await page.evaluate((key) => localStorage.setItem(key, 'launch1'), marker);
    const wroteValue = await page.evaluate((key) => localStorage.getItem(key), marker);
    report.steps.push({ step: 'e_write_marker', ok: wroteValue === 'launch1', marker, wroteValue });

    /* ---- f) F11 全屏截图(侧栏在)—— 截图前清设备度量覆盖,还原真实全屏分辨率 ---- */
    await clearDeviceMetrics(cdpMetrics);
    await page.bringToFront();
    const viewportBeforeF11 = await page.evaluate(() => ({ innerW: window.innerWidth, innerH: window.innerHeight }));
    await pressF11(cdpMetrics);
    await sleep(700);
    const viewportAfterF11 = await page.evaluate(() => ({ innerW: window.innerWidth, innerH: window.innerHeight }));
    await page.screenshot({ path: path.join(OUT_DIR, 'fullscreen.png') });
    const railVisibleInFullscreen = await page.evaluate(() => {
      const rail = document.getElementById('rail');
      if (!rail) return false;
      const r = rail.getBoundingClientRect();
      return r.width > 0 && r.height > 0 && getComputedStyle(rail).display !== 'none';
    });
    const dimsGrew = (viewportAfterF11.innerW * viewportAfterF11.innerH) > (viewportBeforeF11.innerW * viewportBeforeF11.innerH);
    report.steps.push({
      step: 'f_fullscreen', ok: railVisibleInFullscreen && dimsGrew,
      viewportBeforeF11, viewportAfterF11, dimsGrew, railVisibleInFullscreen
    });
    await pressF11(cdpMetrics);
    await sleep(300);
  } catch (error) {
    report.fatalError1 = String((error && error.stack) || error);
  } finally {
    try { if (browser1) await browser1.close(); } catch { /* noop */ }
    await killChild(launch1.child);
  }
  report.launch1StderrTail = launch1.stderrBuf.split(/\r?\n/).filter(Boolean).slice(-20);

  await sleep(600);

  /* ========== 第二次启动(全新进程,同 SHELL_HTTP_PORT 保同源):核验 key 已清空 ========== */
  const CDP_PORT_2 = 9532;
  const launch2 = launchElectron(CDP_PORT_2);
  let browser2 = null;
  try {
    await waitForCdp(CDP_PORT_2, 20000);
    browser2 = await chromium.connectOverCDP(`http://127.0.0.1:${CDP_PORT_2}`);
    const page2 = await waitForShellPage(browser2, 20000);
    await page2.waitForFunction(() => !!window.__SHELL_READY__, { timeout: 20000 });
    const marker = '__w3b_persist_probe__';
    const afterRestart = await page2.evaluate((key) => localStorage.getItem(key), marker);
    report.steps.push({
      step: 'e_verify_cleared', ok: afterRestart === null, afterRestart,
      note: '第二次启动应看不到第一次写入的 key(clearStorageData 每次 app ready 生效一次)'
    });
  } catch (error) {
    report.fatalError2 = String((error && error.stack) || error);
  } finally {
    try { if (browser2) await browser2.close(); } catch { /* noop */ }
    await killChild(launch2.child);
  }
  report.launch2StderrTail = launch2.stderrBuf.split(/\r?\n/).filter(Boolean).slice(-20);

  report.finishedAt = new Date().toISOString();
  const presentSteps = new Set(report.steps.map(s => s.step));
  report.allStepsPresent = REQUIRED_STEPS.every(s => presentSteps.has(s));
  report.allOk = report.allStepsPresent && report.steps.every(s => s.ok);

  const reportPath = path.join(OUT_DIR, 'verify_report.json');
  fs.writeFileSync(reportPath, JSON.stringify(report, null, 2), 'utf8');
  console.log('\n==== W3b 验收结果(JSON 已写入 ' + reportPath + ') ====');
  console.log(JSON.stringify(report, null, 2));
  if (!report.allOk) process.exitCode = 1;
}

main().catch(error => {
  console.error('verify_w3b 顶层失败: ' + ((error && error.stack) || error));
  process.exit(1);
});
