/* 视觉回归基线门(0729 新建)。

   为什么需要:现有九套质量门共 160 项**全是数值/结构门**——它们能发现"数字对不上""元素不存在",
   但没有任何一项能发现"颜色改丑了""间距塌了""层级乱了"。设计语言收敛要大改 CSS,
   没有这道门就等于闭着眼睛动刀:160 项照样全绿,页面却可能已经难看。

   为什么由验收方建、且基线在改动之前采集:
   基线是尺子。尺子不能由被验收方来造,否则等于自己给自己打分。

   零新依赖:仓库里只有 playwright,没有 pngjs/pixelmatch。
   故用浏览器自己当图像处理器——把两张 PNG 画进 canvas 逐像素比,
   顺带用 canvas 生成差异热图。不 npm i 任何东西。

   三维页的确定性:
   1. 用页面自己暴露的 seek 钩子定到固定帧(01 __S3_FILL_QA.seekEvent / 02 __S3_QA.seek);
   2. 再把所有 <canvas> 遮成纯色——**本次收敛只动 CSS/版面,不动三维场景内部配色**(负责人第 5 条拍板),
      所以三维画面本就不该进比对;遮掉它同时消除 GPU 渲染的逐帧抖动。

   用法:
     node tools/visual_baseline.mjs capture     采集基线 → visual_baseline/
     node tools/visual_baseline.mjs check       与基线比对 → out/visual_diff_<时间>/
*/
import { chromium } from 'playwright';
import { createServer } from 'node:http';
import { readFileSync, existsSync, statSync, mkdirSync, writeFileSync, readdirSync, rmSync } from 'node:fs';
import { join, resolve, extname, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const SHOWCASE = resolve(HERE, '..');
const PROJECT_ROOT = resolve(SHOWCASE, '..');
const BASE_DIR = join(SHOWCASE, 'visual_baseline');
const CHROME = 'C:/Users/86177/AppData/Local/ms-playwright/chromium-1223/chrome-win64/chrome.exe';

const MODE = (process.argv[2] || '').toLowerCase();
if (!['capture', 'check'].includes(MODE)) {
  console.error('用法: node tools/visual_baseline.mjs capture|check');
  process.exit(2);
}

/* 差异容忍:单像素任一通道差 > 阈值才算"变了"。
   8 是为了吃掉字体抗锯齿与 GPU 合成的亚像素噪声,不是为了放水——
   真实的颜色/间距改动远大于 8。 */
const CHANNEL_TOL = 8;
/* 整图变化像素占比超过这个数就报 FAIL。0.1% 足以在 1552×900 上抓到一个小徽章变色。 */
const FAIL_RATIO = 0.001;

const VIEWPORTS = [
  { key: 'shell', width: 1552, height: 900 },   // 壳内容区实测尺寸
  { key: 'min', width: 1232, height: 800 },     // 壳最小尺寸
];

const PAGES = [
  { key: '00_导览', file: '00_导览.html',
    ready: () => !!window.__D00_READY__ },
  { key: '01_连续填仓', file: '01_连续填仓.html',
    ready: () => { try { return !!window.__S3_FILL_QA && !!window.__S3_FILL_QA.snapshot(); } catch { return false; } },
    /* 定到一个中段行程帧:比"页面刚加载"更能暴露运行态的版面问题 */
    prepare: () => { try { window.__S3_FILL_QA.seekEvent(133, 'LADEN_TRAVEL', .5); } catch { } } },
  { key: '02_入出闭环', file: '02_入出闭环.html',
    ready: () => { try { return !!window.__S3_QA && !window.__S3_QA.snapshot().loading; } catch { return false; } },
    prepare: () => { try { window.__S3_QA.seek(2, 'OUTBOUND', .5); } catch { } } },
  { key: '03_FIO物理证据', file: '03_FIO物理证据.html' },
  { key: '04_AB工程', file: '04_AB工程.html' },
];

/* ---------- 静态服务 ---------- */
const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8', '.css': 'text/css; charset=utf-8',
  '.png': 'image/png', '.jpg': 'image/jpeg', '.mp4': 'video/mp4' };
const server = createServer((req, res) => {
  const rel = decodeURIComponent(new URL(req.url, 'http://x').pathname).replace(/^\/+/, '');
  const target = resolve(PROJECT_ROOT, rel);
  if (!target.startsWith(PROJECT_ROOT) || !existsSync(target) || !statSync(target).isFile()) {
    res.writeHead(404); res.end(); return;
  }
  res.writeHead(200, { 'Content-Type': MIME[extname(target).toLowerCase()] || 'application/octet-stream' });
  res.end(readFileSync(target));
});
await new Promise(r => server.listen(0, '127.0.0.1', r));
const BASE_URL = `http://127.0.0.1:${server.address().port}`;

const browser = await chromium.launch({ executablePath: CHROME });

/* ---------- 采集一张 ---------- */
async function shoot(p, vp) {
  const page = await browser.newPage({ viewport: { width: vp.width, height: vp.height }, deviceScaleFactor: 1 });
  const errs = [];
  page.on('pageerror', e => errs.push(String(e)));
  await page.goto(`${BASE_URL}/l4_showcase/src/${encodeURIComponent(p.file)}`);
  if (p.ready) await page.waitForFunction(p.ready, { timeout: 30000 });
  else await page.waitForTimeout(400);
  if (p.prepare) { await page.evaluate(p.prepare); await page.waitForTimeout(500); }
  /* 关掉动画/过渡,消除采集时机造成的抖动 */
  await page.addStyleTag({ content: `*,*::before,*::after{animation:none!important;transition:none!important}` });
  await page.waitForTimeout(200);
  const buf = await page.screenshot({
    fullPage: true,
    /* 遮掉三维画布:本次收敛不动场景内部配色,且 GPU 渲染逐帧不可复现 */
    mask: [page.locator('canvas')],
    maskColor: '#ff00ff',
  });
  await page.close();
  return { buf, errs };
}

/* ---------- 用浏览器当图像处理器做 diff ---------- */
const differ = await browser.newPage();
await differ.setContent('<html><body></body></html>');
async function diffPng(aBuf, bBuf) {
  return await differ.evaluate(async ({ a, b, tol }) => {
    const load = (b64) => new Promise((res, rej) => {
      const img = new Image();
      img.onload = () => res(img); img.onerror = rej;
      img.src = 'data:image/png;base64,' + b64;
    });
    const [ia, ib] = await Promise.all([load(a), load(b)]);
    const W = Math.max(ia.width, ib.width), H = Math.max(ia.height, ib.height);
    const mk = (img) => {
      const c = document.createElement('canvas'); c.width = W; c.height = H;
      const x = c.getContext('2d', { willReadFrequently: true });
      x.fillStyle = '#000'; x.fillRect(0, 0, W, H);
      x.drawImage(img, 0, 0);
      return x.getImageData(0, 0, W, H).data;
    };
    const da = mk(ia), db = mk(ib);
    const out = document.createElement('canvas'); out.width = W; out.height = H;
    const octx = out.getContext('2d');
    const od = octx.createImageData(W, H);
    let changed = 0;
    for (let i = 0; i < da.length; i += 4) {
      const d = Math.max(Math.abs(da[i] - db[i]), Math.abs(da[i + 1] - db[i + 1]), Math.abs(da[i + 2] - db[i + 2]));
      if (d > tol) {
        changed++;
        od.data[i] = 255; od.data[i + 1] = 0; od.data[i + 2] = 90; od.data[i + 3] = 255;
      } else {
        /* 未变区域压成淡灰底,让差异点跳出来 */
        const g = 235 + (da[i] * .06) | 0;
        od.data[i] = g; od.data[i + 1] = g; od.data[i + 2] = g; od.data[i + 3] = 255;
      }
    }
    octx.putImageData(od, 0, 0);
    return {
      w: W, h: H,
      sizeChanged: ia.width !== ib.width || ia.height !== ib.height,
      baseSize: `${ia.width}x${ia.height}`, curSize: `${ib.width}x${ib.height}`,
      changed, total: W * H, ratio: changed / (W * H),
      diffPng: out.toDataURL('image/png').split(',')[1],
    };
  }, { a: aBuf.toString('base64'), b: bBuf.toString('base64'), tol: CHANNEL_TOL });
}

/* ---------- 主流程 ---------- */
const shots = [];
for (const p of PAGES) {
  for (const vp of VIEWPORTS) {
    const name = `${p.key}__${vp.key}.png`;
    const { buf, errs } = await shoot(p, vp);
    shots.push({ page: p.key, vp: vp.key, name, buf, errs });
    if (errs.length) console.log(`  ! ${name} pageerror ${errs.length}: ${errs[0].slice(0, 90)}`);
  }
}

if (MODE === 'capture') {
  mkdirSync(BASE_DIR, { recursive: true });
  for (const s of shots) writeFileSync(join(BASE_DIR, s.name), s.buf);
  const manifest = {
    capturedAtCommit: 'see git log',
    channelTol: CHANNEL_TOL, failRatio: FAIL_RATIO,
    viewports: VIEWPORTS, shots: shots.map(s => ({ name: s.name, bytes: s.buf.length })),
    note: '基线在设计收敛开工前采集。三维 <canvas> 已用 #ff00ff 遮罩——本次收敛不动场景内部配色。',
  };
  writeFileSync(join(BASE_DIR, 'manifest.json'), JSON.stringify(manifest, null, 1), 'utf8');
  const mb = shots.reduce((s, x) => s + x.buf.length, 0) / 1048576;
  console.log(`\n已采集 ${shots.length} 张基线 → ${BASE_DIR}  (合计 ${mb.toFixed(1)} MB)`);
  shots.forEach(s => console.log(`  ${s.name.padEnd(30)} ${(s.buf.length / 1024).toFixed(0)} KB`));
} else {
  const stamp = new Date().toISOString().replace(/[:.]/g, '').slice(0, 15);
  const OUT = join(SHOWCASE, 'out', `visual_diff_${stamp}`);
  mkdirSync(OUT, { recursive: true });
  const rows = [];
  for (const s of shots) {
    const basePath = join(BASE_DIR, s.name);
    if (!existsSync(basePath)) { rows.push({ name: s.name, status: 'NO_BASELINE' }); continue; }
    const r = await diffPng(readFileSync(basePath), s.buf);
    if (r.changed > 0) writeFileSync(join(OUT, s.name.replace('.png', '_diff.png')), Buffer.from(r.diffPng, 'base64'));
    writeFileSync(join(OUT, s.name.replace('.png', '_current.png')), s.buf);
    rows.push({ name: s.name, status: r.ratio > FAIL_RATIO ? 'CHANGED' : 'ok',
      ratio: r.ratio, changed: r.changed, total: r.total,
      sizeChanged: r.sizeChanged, baseSize: r.baseSize, curSize: r.curSize });
  }
  writeFileSync(join(OUT, 'report.json'), JSON.stringify({ channelTol: CHANNEL_TOL, failRatio: FAIL_RATIO, rows }, null, 1), 'utf8');
  console.log('');
  rows.forEach(r => {
    if (r.status === 'NO_BASELINE') { console.log(`NO_BASELINE ${r.name}`); return; }
    const pct = (r.ratio * 100).toFixed(3) + '%';
    console.log(`${r.status === 'ok' ? 'ok      ' : 'CHANGED '} ${r.name.padEnd(30)} ${pct.padStart(8)} ` +
      `(${r.changed}/${r.total})${r.sizeChanged ? `  尺寸 ${r.baseSize}→${r.curSize}` : ''}`);
  });
  const bad = rows.filter(r => r.status !== 'ok');
  console.log(`\n${bad.length ? 'CHANGED' : 'PASS'} ${rows.length - bad.length}/${rows.length} 未变;差异图与当前图 → ${OUT}`);
  console.log('注:CHANGED 不等于错——设计收敛本来就要改观感。看差异图确认"改的正是想改的地方"。');
}

await browser.close();
server.close();
