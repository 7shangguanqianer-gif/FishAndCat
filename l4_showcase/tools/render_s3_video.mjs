import { createRequire } from 'node:module';
import { createHash } from 'node:crypto';
import { createServer } from 'node:http';
import { fileURLToPath } from 'node:url';
import { dirname, extname, join, resolve, sep } from 'node:path';
import { existsSync, mkdirSync, readFileSync, statSync, unlinkSync, writeFileSync } from 'node:fs';

const HERE = dirname(fileURLToPath(import.meta.url));
const SHOWCASE = resolve(HERE, '..');
const SOURCE = join(SHOWCASE, 'src', '样张_S3定稿.html');
const MODE = process.argv[2] || 'full';
if (!['test', 'full'].includes(MODE)) throw new Error(`Mode must be test or full, got: ${MODE}`);
const require = createRequire(import.meta.url);
const { chromium } = require('playwright');
const OUT = resolve(process.argv[3] || join(SHOWCASE, 'out', MODE === 'test' ? '_test_s3_0714' : '_frames_s3_0714_final_v2'));
const EXTERNAL_URL = process.env.S3_URL || '';
const CHROME = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE ||
  'C:/Users/86177/AppData/Local/ms-playwright/chromium-1223/chrome-win64/chrome.exe';
const ANGLE = process.env.S3_ANGLE || 'd3d11';

const FPS = 30;
const DURATION = 32;
const SCENE_END = 26;
const MOTION_START = 1.2;
const DPR = 1.5;
const VIEWPORT = { width: 1280, height: 720 };
const TEST_TIMES = [0, 0.6, 1.2, 5.0, 13.6, 15.1, 25.75, 26.0, 26.35, 28.0, 31.7];

const clamp01 = x => Math.max(0, Math.min(1, x));
const smooth = x => { x = clamp01(x); return x * x * (3 - 2 * x); };

function timeline(t) {
  const view = t < SCENE_END ? 'scene' : 'data';
  const phase = view === 'scene'
    ? (t < MOTION_START ? 0.5 : Math.min(30.999, 0.5 + (t - MOTION_START) * 1.25))
    // 数据页保留约 5 s 读图时间，同时让速度图的黄色时间游标从 0→31 s 缓慢扫过。
    : 30.999 * clamp01((t - 26.45) / (31.4 - 26.45));
  const cameraFrac = clamp01(t / SCENE_END); // anim3d_formal.py 的线性 -72°→-56° 扫掠

  let fade = 0;
  // 首帧直接给出稳定三维总览，避免 PPT/资源管理器默认海报帧成为纯白缩略图。
  if (t >= 25.6 && t < 26.0) fade = smooth((t - 25.6) / 0.4);
  else if (t >= 26.0 && t < 26.45) fade = 1 - smooth((t - 26.0) / 0.45);
  else if (t >= 31.4) fade = smooth((t - 31.4) / 0.6);

  // 不对 WebGL canvas 做 CSS 缩放；SwiftShader 长序列截图中会产生合成黑块。
  return { view, phase, cameraFrac, fade };
}

function startStaticServer() {
  const root = SHOWCASE;
  const mime = new Map([
    ['.html', 'text/html; charset=utf-8'],
    ['.js', 'text/javascript; charset=utf-8'],
    ['.css', 'text/css; charset=utf-8']
  ]);
  return new Promise((resolveServer, rejectServer) => {
    const server = createServer((req, res) => {
      try {
        const pathname = decodeURIComponent(new URL(req.url, 'http://127.0.0.1').pathname);
        const file = resolve(root, pathname.replace(/^\/+/, ''));
        if (!(file === root || file.startsWith(root + sep)) || !existsSync(file) || statSync(file).isDirectory()) {
          res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
          res.end('Not found');
          return;
        }
        res.writeHead(200, {
          'Content-Type': mime.get(extname(file).toLowerCase()) || 'application/octet-stream',
          'Cache-Control': 'no-store'
        });
        res.end(readFileSync(file));
      } catch (error) {
        res.writeHead(500, { 'Content-Type': 'text/plain; charset=utf-8' });
        res.end(String(error));
      }
    });
    server.once('error', rejectServer);
    server.listen(0, '127.0.0.1', () => {
      const { port } = server.address();
      resolveServer({
        server,
        url: `http://127.0.0.1:${port}/src/%E6%A0%B7%E5%BC%A0_S3%E5%AE%9A%E7%A8%BF.html`
      });
    });
  });
}

async function main() {
  if (!existsSync(CHROME)) throw new Error(`Chromium not found: ${CHROME}`);
  mkdirSync(OUT, { recursive: true });
  const manifestPath = join(OUT, 'capture_manifest.json');
  const captureMarker = join(OUT, '.capture_in_progress');
  writeFileSync(captureMarker, `${new Date().toISOString()}\n`, 'utf8');
  if (existsSync(manifestPath)) unlinkSync(manifestPath);
  const sourceHash = createHash('sha256').update(readFileSync(SOURCE)).digest('hex').toUpperCase();
  const browser = await chromium.launch({
    headless: true,
    executablePath: CHROME,
    args: [`--use-angle=${ANGLE}`, '--enable-webgl', '--ignore-gpu-blocklist']
  });
  const context = await browser.newContext({ viewport: VIEWPORT, deviceScaleFactor: DPR });
  const page = await context.newPage();
  let staticServer = null;
  let targetUrl = EXTERNAL_URL;
  const errors = [];
  const badResponses = [];
  page.on('pageerror', error => errors.push(String(error)));
  page.on('console', msg => { if (msg.type() === 'error') errors.push(msg.text()); });
  page.on('response', response => {
    if (response.status() >= 400) badResponses.push({ status: response.status(), url: response.url() });
  });
  // Chromium 会自动请求站点图标；页面是离线展示件且未声明 favicon，捕获端返回空响应以免制造伪 404。
  await page.route('**/favicon.ico', route => route.fulfill({ status: 204, body: '' }));

  try {
    if (!targetUrl) {
      staticServer = await startStaticServer();
      targetUrl = staticServer.url;
    }
    await page.goto(targetUrl, { waitUntil: 'load' });
    await page.waitForFunction(() => window.__S3_QA && window.__S3_QA.total === 31);
    await page.addStyleTag({ content: '*{transition:none!important;animation:none!important}html{cursor:none!important}' });
    await page.evaluate(() => {
      const fade = document.createElement('div');
      fade.id = 'videoFade0714';
      Object.assign(fade.style, {
        position: 'fixed', inset: '0', zIndex: '99999', pointerEvents: 'none',
        background: '#f2f2f2', opacity: '1'
      });
      document.body.appendChild(fade);
    });

    const times = MODE === 'test'
      ? TEST_TIMES
      : Array.from({ length: Math.round(DURATION * FPS) }, (_, i) => i / FPS);

    for (let i = 0; i < times.length; i++) {
      const t = times[i];
      const state = timeline(t);
      await page.evaluate(async s => {
        paused = true;
        pauseNow = start + s.phase / SIM_SPEED * 1000;
        userCameraUntil = Number.POSITIVE_INFINITY;
        recoveryStart = 0;
        const desiredView = s.view === 'scene' ? 'sceneView' : 'dataView';
        if (document.querySelector('.view.active').id !== desiredView) setView(desiredView);
        await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));

        if (s.view === 'scene') {
          setCamera(s.cameraFrac);
          renderer.domElement.style.transform = 'none';
          renderer.render(scene, camera);
        } else {
          renderer.domElement.style.transform = 'none';
          drawSpeed(s.phase); drawQueue(); drawService();
        }
        document.getElementById('videoFade0714').style.opacity = String(s.fade);
      }, state);

      // 状态写入后再跨过两个合成帧，避免截图早于 WebGL/CSS paint 而出现随机黑块。
      await page.evaluate(() => new Promise(resolve =>
        requestAnimationFrame(() => requestAnimationFrame(resolve))));

      const filename = MODE === 'test'
        ? `test_${String(i).padStart(2, '0')}_${String(t).replace('.', 'p')}s.jpg`
        : `frame_${String(i).padStart(6, '0')}.jpg`;
      await page.screenshot({ path: join(OUT, filename), type: 'jpeg', quality: 94, animations: 'disabled' });
      if (MODE === 'full' && (i % 90 === 0 || i === times.length - 1)) {
        process.stdout.write(`frame ${i + 1}/${times.length}\n`);
      }
    }

    const finalQa = await page.evaluate(() => {
      const gl = renderer.getContext();
      const debug = gl.getExtension('WEBGL_debug_renderer_info');
      return {
        qa: window.__S3_QA,
        viewport: [innerWidth, innerHeight],
        page: [document.documentElement.scrollWidth, document.documentElement.scrollHeight],
        canvas: [renderer.domElement.width, renderer.domElement.height],
        dpr: devicePixelRatio,
        webglRenderer: debug ? gl.getParameter(debug.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER),
        webglVendor: debug ? gl.getParameter(debug.UNMASKED_VENDOR_WEBGL) : gl.getParameter(gl.VENDOR)
      };
    });
    const manifest = {
      mode: MODE,
      source: SOURCE,
      sourceSha256: sourceHash,
      url: targetUrl,
      selfHosted: !EXTERNAL_URL,
      fps: FPS,
      durationSeconds: DURATION,
      frameCount: times.length,
      viewport: VIEWPORT,
      deviceScaleFactor: DPR,
      outputPixels: [1920, 1080],
      angleBackendRequested: ANGLE,
      sceneEndSeconds: SCENE_END,
      motionStartSeconds: MOTION_START,
      digitalZoomMax: 1.0,
      errors,
      badResponses,
      finalQa
    };
    writeFileSync(manifestPath, JSON.stringify(manifest, null, 2), 'utf8');
    process.stdout.write(`manifest ${manifestPath}\n`);
    if (errors.length || badResponses.length) process.exitCode = 2;
    else unlinkSync(captureMarker);
  } finally {
    try {
      await browser.close();
    } finally {
      if (staticServer) await new Promise(resolveClose => staticServer.server.close(resolveClose));
    }
  }
}

await main();
