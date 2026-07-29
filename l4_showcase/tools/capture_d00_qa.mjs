/* 00 导览页 QA(0728c 新建;此前该页**零覆盖**——这正是它的 04 章长期写着
   `00_导览_A.html` / `三维作业回放.html` / `运行数据看板.html` 三个不存在的文件而无人发现的原因)。

   用户拍板的核心门是「文件存在」硬门:页面点名的每一条路径都去磁盘真实校验。
   导览页的失效方式与三维页不同——它不会崩、不会渲染错,只会**悄悄地说假话**:
   指向一个已改名的文件、引用一个已过时的数字。所以这套门全部指向"页面说的与仓库实际是否一致"。
*/
import { chromium } from 'playwright';
import { createServer } from 'node:http';
import { readFileSync, existsSync, statSync, mkdirSync, writeFileSync } from 'node:fs';
import { join, resolve, extname, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const SHOWCASE = resolve(HERE, '..');
const PROJECT_ROOT = resolve(SHOWCASE, '..');
const PAGE = '00_导览.html';
const OUT = join(SHOWCASE, 'out', 'd00_qa_0728');
const CHROME = 'C:/Users/86177/AppData/Local/ms-playwright/chromium-1223/chrome-win64/chrome.exe';

mkdirSync(OUT, { recursive: true });

const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8', '.css': 'text/css; charset=utf-8',
  '.png': 'image/png', '.jpg': 'image/jpeg', '.mp4': 'video/mp4' };

const server = createServer((req, res) => {
  const rel = decodeURIComponent(new URL(req.url, 'http://x').pathname).replace(/^\/+/, '');
  const target = resolve(PROJECT_ROOT, rel);
  if (!target.startsWith(PROJECT_ROOT) || !existsSync(target) || !statSync(target).isFile()) {
    res.writeHead(404); res.end(); return;
  }
  res.writeHead(200, { 'content-type': MIME[extname(target).toLowerCase()] || 'application/octet-stream' });
  res.end(readFileSync(target));
});
await new Promise(r => server.listen(0, '127.0.0.1', r));
const port = server.address().port;

const report = { page: PAGE, runtimeErrors: [], consoleErrors: [], missed: [], audit: null,
  pathCheck: [], metricCheck: [], assertions: {}, errors: [], pass: false };

const browser = await chromium.launch({ executablePath: CHROME, args: ['--use-angle=d3d11', '--enable-unsafe-swiftshader'] });
try {
  /* 壳内可用区实测 1552×900(app_shell/main.js 默认内容区 1600×900 − 48px 侧栏)。 */
  const page = await browser.newPage({ viewport: { width: 1552, height: 900 } });
  page.on('pageerror', e => report.runtimeErrors.push(e.message));
  page.on('console', m => { if (m.type() === 'error') report.consoleErrors.push(m.text()); });
  page.on('response', r => { if (r.status() >= 400) report.missed.push(`${r.status()} ${r.url().split('/').pop()}`); });

  await page.goto(`http://127.0.0.1:${port}/l4_showcase/src/${encodeURIComponent(PAGE)}`, { waitUntil: 'load' });
  await page.waitForFunction(() => window.__D00_READY__ === true, null, { timeout: 20000 });
  await page.waitForTimeout(400);

  report.audit = await page.evaluate(() => window.__D00_AUDIT);
  await page.screenshot({ path: join(OUT, 'd00_top.png') });

  /* ── 文件存在硬门:页面点名的每条路径都去磁盘查 ──
     路径写的是仓库中的真实位置(0728c 用户拍板②),含通配符的按其所在目录校验。 */
  for (const raw of report.audit.paths) {
    const clean = raw.replace(/\\/g, '/').replace(/\/+$/, '');
    const hasGlob = clean.includes('*');
    const probe = hasGlob ? clean.slice(0, clean.lastIndexOf('/')) : clean;
    /* 00 章列的是提交包内的目标目录(01_验证报告\ 等),尚未建包,按"待打包"豁免并单独标注。 */
    const isPackTarget = /^0[1-5]_/.test(clean);
    const abs = resolve(PROJECT_ROOT, probe);
    report.pathCheck.push({ raw, probe, exists: existsSync(abs), isPackTarget, hasGlob });
  }

  /* ── 数字一致门:页面上的成果数字必须与来源文件当前取值一致 ── */
  const readCsvCell = (file, rowStartsWith, colIndex) => {
    const text = readFileSync(join(PROJECT_ROOT, file), 'utf8');
    const line = text.split(/\r?\n/).find(l => l.startsWith(rowStartsWith));
    return line ? line.split(',')[colIndex] : null;
  };
  const finalTest = readFileSync(join(PROJECT_ROOT, 'sim/out/final_test_30seed.csv'), 'utf8').split(/\r?\n/);
  const awra = (finalTest.find(l => l.startsWith('awra')) || '').split(',');
  const seq = (finalTest.find(l => l.startsWith('seq')) || '').split(',');
  const plcPassed = readCsvCell('sim/out/plc_evidence.csv', 'verified_passed', 1);
  const plcFailed = readCsvCell('sim/out/plc_evidence.csv', 'verified_failed', 1);
  /* oracle_gap.csv 的 ALL 行有 10 条(每个 selector 各一条),必须指定 selector。
     页面的「算法选择达成率」测的是**场景检测器 lexicographic 档**,不是任何固定策略;
     首版 QA 只写 startsWith('ALL') 取到了第一行 det_holistic(81.61),是取行错、不是数字错。
     同表里固定策略 awra 那行是 81.61/88.61,与本指标不是一回事(已写进该指标的 edge 段)。 */
  const pickAll = (file, selector) => (readFileSync(join(PROJECT_ROOT, file), 'utf8')
    .split(/\r?\n/).find(l => l.startsWith(`ALL,${selector}`)) || '').split(',');
  const oracleAll = pickAll('sim/out/oracle_gap.csv', 'det_lexicographic');
  const oracleAccelAll = pickAll('sim/out/oracle_gap_accel.csv', 'det_lexicographic');

  const shown = report.audit.metrics.join(' | ');
  report.metricCheck = [
    { name: 'H_exp 均值', shown, srcValue: awra[1], ok: shown.includes(Number(awra[1]).toFixed(2)) },
    { name: 'H_exp 标准差', shown, srcValue: awra[2], ok: shown.includes(Number(awra[2]).toFixed(2)) },
    { name: '降幅', shown, srcValue: (((Number(seq[1]) - Number(awra[1])) / Number(seq[1])) * 100).toFixed(1),
      /* 页面按 canonical C12 官方口径写 61.6%,由 csv 三位小数复算为 61.5%,差 0.1pp 属四舍五入。
         故此门只断言两者相差不超过 0.2pp,不强求逐位相同(0728c 断点 §4.4 已记此偏差)。 */
      ok: Math.abs(61.6 - ((Number(seq[1]) - Number(awra[1])) / Number(seq[1])) * 100) <= 0.2 && shown.includes('61.6') },
    { name: 'PLC 自测', shown, srcValue: `${plcPassed}/${plcFailed}`, ok: shown.includes(`${plcPassed} / ${plcFailed}`) },
    { name: '达成率 匀速', shown, srcValue: oracleAll[4], ok: shown.includes(Number(oracleAll[4]).toFixed(1)) },
    { name: '达成率 加减速', shown, srcValue: oracleAccelAll[4], ok: shown.includes(String(oracleAccelAll[4])) }
  ];

  /* ── 三页入口:href 指向的页面必须真实存在 ── */
  const sceneHrefsOk = report.audit.scenes.every(s =>
    existsSync(resolve(PROJECT_ROOT, 'l4_showcase/src', s.href.replace('./', ''))));

  /* ── 材料 key 必须都在 materials.config.json 里(含本轮补的 04) ── */
  const matCfg = JSON.parse(readFileSync(join(SHOWCASE, 'app_shell', 'materials.config.json'), 'utf8'));
  const matKeysOk = report.audit.materialKeys.every(k => Object.prototype.hasOwnProperty.call(matCfg, k));

  /* ── 章节浮标:点击可达 + 滚动时高亮跟随 ── */
  const railProbe = await page.evaluate(async () => {
    const btns = Array.from(document.querySelectorAll('.chapRail button'));
    const sc = document.getElementById('scroller');
    const wait = ms => new Promise(r => setTimeout(r, ms));
    const seen = [];
    for (const b of btns) {
      b.click();
      await wait(260);
      const cur = document.querySelector('.chapRail button[aria-current="true"]');
      seen.push({ want: b.querySelector('.t').textContent, got: cur ? cur.querySelector('.t').textContent : null,
        scrollTop: Math.round(sc.scrollTop) });
    }
    return { count: btns.length, seen, maxScroll: Math.round(sc.scrollHeight - sc.clientHeight) };
  });
  report.rail = railProbe;

  /* ── 顶栏视觉语言:与 01/02/03 同一套(无衬线、3px 红底边、ABB 字标 900 Arial) ── */
  const brand = await page.evaluate(() => {
    const bar = document.querySelector('.topbar'), word = document.querySelector('.abbWord');
    const cs = getComputedStyle(bar), ws = getComputedStyle(word);
    const serifs = Array.from(document.querySelectorAll('*')).filter(el => {
      const f = getComputedStyle(el).fontFamily.toLowerCase();
      return f.includes('georgia') || f.includes('songti') || f.includes('simsun') || f.includes('serif') && !f.includes('sans-serif');
    }).length;
    return { borderBottom: cs.borderBottomWidth + ' ' + cs.borderBottomColor, height: cs.height,
      abbWeight: ws.fontWeight, abbSize: ws.fontSize, abbColor: ws.color, serifCount: serifs };
  });
  report.brand = brand;

  await page.evaluate(() => document.getElementById('scroller').scrollTo(0, 99999));
  await page.waitForTimeout(400);
  await page.screenshot({ path: join(OUT, 'd00_bottom.png') });

  const a = {
    /* 页面能起、零运行时错误、零 404 */
    booted: report.audit && report.audit.chapters === 7,
    noRuntimeErrors: report.runtimeErrors.length === 0 && report.consoleErrors.length === 0,
    noMissedResources: report.missed.length === 0,
    /* 【核心硬门】页面点名的每条仓库路径都必须真实存在(提交包目标路径豁免并单列) */
    everyRepoPathExists: report.pathCheck.filter(p => !p.isPackTarget).every(p => p.exists),
    packTargetsDeclared: report.pathCheck.some(p => p.isPackTarget),
    /* 三页入口 href 真实存在;材料 key 都在配置里 */
    sceneHrefsExist: sceneHrefsOk && report.audit.scenes.length === 3,
    materialKeysConfigured: matKeysOk && report.audit.materialKeys.length === 5,
    /* 五个成果数字与来源文件当前取值一致 */
    metricsMatchSources: report.metricCheck.every(m => m.ok),
    /* 章节浮标七项都能点到且高亮跟随 */
    railNavigable: railProbe.count === 7 && railProbe.seen.every(s => s.got === s.want),
    /* 视觉语言:3px 红底边、ABB 字标 900 权重、全页零衬线 */
    brandAligned: /^3px/.test(brand.borderBottom) && brand.borderBottom.includes('255, 0, 15') &&
      brand.abbWeight === '900' && brand.abbSize === '24px' && brand.serifCount === 0
  };
  report.assertions = a;
  report.pass = Object.values(a).every(Boolean);
  report.errors = Object.entries(a).filter(([, v]) => !v).map(([k]) => k);
} catch (e) {
  report.pass = false; report.errors.push(`qa_exception:${e.name}:${e.message}`);
} finally {
  await browser.close(); server.close();
}

writeFileSync(join(OUT, 'qa_report.json'), JSON.stringify(report, null, 2), 'utf8');
const total = Object.keys(report.assertions).length;
const passed = Object.values(report.assertions).filter(Boolean).length;
console.log(`${report.pass ? 'PASS' : 'FAIL'} ${passed}/${total}; ${join(OUT, 'qa_report.json')}`);
if (!report.pass) console.log('failed:', report.errors.join(', '));
