/* W1 细化八项批次 · 验收截图 + 功能核验(0720)。
   独立于 capture_s3_mixed_layout_a_qa.mjs(启动治理)与 capture_s3_t5_verification.mjs(T5 证据中心)——
   本脚本专测本轮八项改动(排队带延伸/货物信息行/2D撑满/故障点两修/顶栏基线/悬浮解释/折叠收纳/速度滑条),
   逐项断言 + 截图存 out/w1_0720/。Playwright 底座与既有 QA 脚本同源:同一 chromium、同一 args、同一
   MIME 表、同一就绪判据。 */
import { createRequire } from 'node:module';
import { createServer } from 'node:http';
import { fileURLToPath } from 'node:url';
import { dirname, extname, join, resolve, sep } from 'node:path';
import { existsSync, readFileSync, readdirSync, mkdirSync, writeFileSync } from 'node:fs';

const HERE = dirname(fileURLToPath(import.meta.url));
const SHOWCASE = resolve(HERE, '..');
const PAGE = '02_入出闭环.html';
const OUT = resolve(SHOWCASE, 'out', 'w1_0720');
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

const report = { page: PAGE, pageErrors: [], consoleErrors: [], checks: {}, pass: false };
const fail = (key, detail) => { report.checks[key] = { ok: false, detail }; };
const ok = (key, detail) => { report.checks[key] = { ok: true, detail }; };
const assertCheck = (key, cond, detail) => { if (cond) ok(key, detail); else fail(key, detail); };

await new Promise(r => server.listen(0, '127.0.0.1', r));
const port = server.address().port;
const pageUrl = `http://127.0.0.1:${port}/src/${encodeURIComponent(PAGE)}`;
const browser = await chromium.launch({ executablePath: CHROME, args: ['--use-angle=d3d11', '--enable-unsafe-swiftshader'] });

async function waitReady(page, timeout = 30000) {
  await page.waitForFunction(() => { try { return !!window.__S3_QA && !window.__S3_QA.snapshot().loading; } catch { return false; } }, { timeout });
  await page.waitForTimeout(250);
}

try {
  const page = await browser.newPage({ viewport: { width: 1600, height: 900 }, deviceScaleFactor: 1 });
  page.on('pageerror', e => report.pageErrors.push({ at: new Date().toISOString(), text: e.message }));
  page.on('console', m => { if (m.type() === 'error') report.consoleErrors.push({ at: new Date().toISOString(), text: m.text() }); });
  await page.goto(pageUrl, { waitUntil: 'load' });
  await waitReady(page);

  /* ================= 1. 排队带延伸(红框) ================= */
  await page.evaluate(() => window.__S3_QA.seek(12, 'LOAD_IN', 0.1));
  await page.waitForTimeout(150);
  const queueState = await page.evaluate(() => {
    const s = window.__S3_QA.snapshot();
    return { queueVisibleGids: s.renderer.queueVisibleGids, phaseName: s.renderer.phaseName };
  });
  assertCheck('queue_4boxes_visible', Array.isArray(queueState.queueVisibleGids) && queueState.queueVisibleGids.length === 4,
    JSON.stringify(queueState));
  /* 默认总览镜头(pos 30,-40,22.5)离入库排队区太远,箱体在截图里只有几像素——
     临时推近到入库带/排队段附近,只为截图取景,不改任何常量/业务状态。 */
  await page.evaluate(() => {
    const damping = controls.enableDamping; controls.enableDamping = false;
    controls.target.set(-0.45, -6.4, 0.35);
    camera.position.set(3.6, -10.2, 3.4);
    camera.updateProjectionMatrix(); camera.lookAt(controls.target); controls.update();
    controls.enableDamping = damping;
  });
  await page.waitForTimeout(150);
  await page.screenshot({ path: join(OUT, 'queue_belt.png') });
  await page.evaluate(() => window.__S3_QA.resetCamera());
  await page.waitForTimeout(100);

  /* ================= 2. 货物全量信息行(蓝框) ================= */
  await page.evaluate(() => window.__S3_QA.seek(5, 'INBOUND_TRAVEL', 0.5));
  await page.waitForTimeout(150);
  const cargoMetaState = await page.evaluate(() => {
    const el = document.getElementById('sceneCargoMeta');
    return {
      html: el ? el.innerHTML : null,
      hasWeight: !!el && /cgWeight/.test(el.innerHTML),
      hasVolume: !!el && /cgVolume/.test(el.innerHTML) && /m³/.test(el.innerHTML),
      hasRank: !!el && /cgRank/.test(el.innerHTML) && /第\s*\d+\/\d+\s*名/.test(el.innerHTML),
      hasGrade: !!el && /cgGrade-/.test(el.innerHTML)
    };
  });
  assertCheck('cargo_meta_has_volume', cargoMetaState.hasVolume, cargoMetaState.html);
  assertCheck('cargo_meta_has_rank', cargoMetaState.hasRank, cargoMetaState.html);
  assertCheck('cargo_meta_has_weight_and_grade', cargoMetaState.hasWeight && cargoMetaState.hasGrade, cargoMetaState.html);
  const sceneCaptionEl = page.locator('#sceneCaption');
  await sceneCaptionEl.screenshot({ path: join(OUT, 'cargo_info.png') });

  /* ================= 3. 2D 网格撑满(绿框) ================= */
  const mapMetrics = await page.evaluate(() => {
    const wrap = document.getElementById('slotMapWrap').getBoundingClientRect();
    const canvas = document.getElementById('slotMap').getBoundingClientRect();
    return { wrap: { w: wrap.width, h: wrap.height }, canvas: { w: canvas.width, h: canvas.height } };
  });
  const canvasAspectDelta = Math.abs(mapMetrics.canvas.w - mapMetrics.canvas.h);
  assertCheck('slotmap_canvas_is_square', canvasAspectDelta < 6, JSON.stringify(mapMetrics));
  await page.locator('#slotMapWrap').screenshot({ path: join(OUT, 'map_square.png') });
  /* 放大浮层同验不回归 */
  await page.evaluate(() => window.__S3_MIXED_MAP.openMap());
  await page.waitForTimeout(200);
  const overlayMetrics = await page.evaluate(() => {
    const canvas = document.getElementById('slotMap').getBoundingClientRect();
    return { w: canvas.width, h: canvas.height, overlayOpen: document.getElementById('s3MapOverlay').classList.contains('open') };
  });
  assertCheck('slotmap_overlay_still_opens', overlayMetrics.overlayOpen === true, JSON.stringify(overlayMetrics));
  assertCheck('slotmap_overlay_canvas_reasonable', overlayMetrics.w > 100 && overlayMetrics.h > 100, JSON.stringify(overlayMetrics));
  await page.evaluate(() => window.__S3_MIXED_MAP.closeMap());
  await page.waitForTimeout(150);

  /* ================= 4. 故障点两修(黑框) ================= */
  const faultDotAlign = await page.evaluate(() => {
    const dot = document.querySelector('#cycleAxisTrack .axisFaultDot');
    const track = document.getElementById('cycleAxisTrack');
    if (!dot || !track) return { found: false };
    const dotRect = dot.getBoundingClientRect(), lineTop = track.getBoundingClientRect().top + 10 + 1.5; /* ::before top:10px height:3px 中心 */
    return { found: true, dotCenterY: dotRect.top + dotRect.height / 2, axisLineCenterY: lineTop, delta: Math.abs((dotRect.top + dotRect.height / 2) - lineTop) };
  });
  assertCheck('fault_dot_vertically_aligned', faultDotAlign.found && faultDotAlign.delta < 2, JSON.stringify(faultDotAlign));
  if (faultDotAlign.found) {
    await page.evaluate(() => window.__S3_QA.seek(0, 'LOAD_IN', 0)); /* 先归位,便于观察点击后的跳转效果 */
    await page.waitForTimeout(100);
    await page.click('#cycleAxisTrack .axisFaultDot');
    await page.waitForTimeout(300);
    const afterClick = await page.evaluate(() => {
      const s = window.__S3_QA.snapshot();
      return { paused: s.paused, checkpoint: s.checkpoint };
    });
    assertCheck('fault_click_resumes_playing_at_cycle_start',
      afterClick.paused === false && afterClick.checkpoint && afterClick.checkpoint.phase === 'LOAD_IN',
      JSON.stringify(afterClick));
    await page.waitForTimeout(400); /* 播放几帧,截图能看出不是静止画面 */
    await page.screenshot({ path: join(OUT, 'fault_jump.png') });
  } else {
    fail('fault_click_resumes_playing_at_cycle_start', 'no axisFaultDot found on default trace');
    await page.screenshot({ path: join(OUT, 'fault_jump.png') });
  }

  /* ================= 5. 顶栏基线重排(橙框) ================= */
  const topbarAlign = await page.evaluate(() => {
    const centers = [];
    document.querySelectorAll('#topbarA #runtimeControls select, #topbarA .tierSeg, #topbarA #runtimeActions button, #topbarA #traceLoadState, #topbarA #plcFeasBadge').forEach(el => {
      const r = el.getBoundingClientRect();
      if (r.width > 0 && r.height > 0) centers.push({ id: el.id || el.className, cy: r.top + r.height / 2 });
    });
    const ys = centers.map(c => c.cy);
    return { count: centers.length, min: Math.min(...ys), max: Math.max(...ys), spread: Math.max(...ys) - Math.min(...ys), centers };
  });
  assertCheck('topbar_controls_share_baseline', topbarAlign.count > 5 && topbarAlign.spread <= 2, JSON.stringify(topbarAlign));
  await page.screenshot({ path: join(OUT, 'topbar_baseline.png') });

  /* ================= 6. 悬浮解释(橙框上) ================= */
  await page.hover('.tierSeg[data-tier="2"]');
  await page.waitForTimeout(250);
  const tooltipState = await page.evaluate(() => {
    const seg = document.querySelector('.tierSeg[data-tier="2"]');
    const tip = seg ? seg.querySelector('.tipBubble') : null;
    if (!tip) return { found: false };
    const style = getComputedStyle(tip);
    return { found: true, isOpen: seg.classList.contains('is-open'), opacity: style.opacity, text: tip.textContent };
  });
  assertCheck('tier_tooltip_opens_on_hover', tooltipState.found && tooltipState.isOpen && Number(tooltipState.opacity) > 0.5, JSON.stringify(tooltipState));
  await page.screenshot({ path: join(OUT, 'tooltip_tier.png') });
  await page.mouse.move(10, 10);
  await page.waitForTimeout(150);

  const profileIconState = await page.evaluate(() => {
    const icon = document.getElementById('profileInfoIcon');
    return { found: !!icon, hasTip: !!(icon && icon.querySelector('.tipBubble')) };
  });
  assertCheck('profile_info_icon_has_tooltip', profileIconState.found && profileIconState.hasTip, JSON.stringify(profileIconState));

  /* ================= 7. 折叠收纳(拍板) ================= */
  const beforeCollapse = await page.evaluate(() => window.__S3_MIXED_LAYOUT_A.audit().collapse);
  assertCheck('collapse_default_all_expanded',
    beforeCollapse.rail === false && beforeCollapse.dock === false && Object.values(beforeCollapse.blocks).every(v => v === false),
    JSON.stringify(beforeCollapse));
  await page.click('#railCollapseBtn');
  await page.click('#dockCollapseBtn');
  await page.waitForTimeout(300);
  const afterCollapse = await page.evaluate(() => {
    const a = window.__S3_MIXED_LAYOUT_A.audit().collapse;
    const glRect = document.getElementById('gl').getBoundingClientRect();
    return { collapse: a, railWidth: getComputedStyle(document.documentElement).getPropertyValue('--rail-w').trim(), glWidth: glRect.width };
  });
  assertCheck('collapse_rail_and_dock_toggle', afterCollapse.collapse.rail === true && afterCollapse.collapse.dock === true, JSON.stringify(afterCollapse));
  assertCheck('collapse_frees_3d_viewport_width', afterCollapse.glWidth > 1400, JSON.stringify(afterCollapse));
  await page.screenshot({ path: join(OUT, 'collapsed.png') });
  /* 复原,免得影响后续检查 */
  await page.click('#railCollapseBtn');
  await page.click('#dockCollapseBtn');
  await page.waitForTimeout(300);

  /* 逐块折叠抽查:货位状态图块头折叠一次再展开,确认内容 display:none + 箭头旋转 + 不影响放大点击 */
  await page.click('#slotMapWrap .mapHead');
  await page.waitForTimeout(150);
  const blockCollapseState = await page.evaluate(() => {
    const wrap = document.getElementById('slotMapWrap');
    const canvas = document.getElementById('slotMap');
    return { collapsed: wrap.classList.contains('railBlockCollapsed'), canvasVisible: canvas.offsetParent !== null };
  });
  assertCheck('block_collapse_hides_content', blockCollapseState.collapsed === true && blockCollapseState.canvasVisible === false, JSON.stringify(blockCollapseState));
  await page.click('#slotMapWrap .mapHead');
  await page.waitForTimeout(150);

  /* ================= 8. 速度滑条(橙框下) ================= */
  const resetCameraGone = await page.evaluate(() => !document.getElementById('resetCamera'));
  assertCheck('reset_camera_button_removed', resetCameraGone === true, `present=${!resetCameraGone}`);
  const sliderAttrs = await page.evaluate(() => {
    const input = document.getElementById('playbackSpeed');
    return { min: input.min, max: input.max, step: input.step, hasDatalist: !!document.getElementById('playbackTicks') };
  });
  assertCheck('slider_range_0.25_to_5', sliderAttrs.min === '0.25' && sliderAttrs.max === '5' && sliderAttrs.hasDatalist, JSON.stringify(sliderAttrs));
  /* 就近吸附:4.97 应吸到刻度 5;1.13 离最近刻度 1 距离 .13>.1,不吸附,保留原值 */
  const snapNear5 = await page.evaluate(() => window.__S3_QA.setPlaybackMultiplier(4.97));
  const snapAwayFromTick = await page.evaluate(() => window.__S3_QA.setPlaybackMultiplier(1.13));
  assertCheck('snap_to_nearest_tick_within_radius', snapNear5 === 5, `snapNear5=${snapNear5}`);
  assertCheck('no_snap_outside_radius', snapAwayFromTick === 1.13, `snapAwayFromTick=${snapAwayFromTick}`);
  await page.evaluate(() => window.__S3_QA.setPlaybackMultiplier(5));
  await page.waitForTimeout(150);
  const playbackValueText = await page.evaluate(() => document.getElementById('playbackValue').textContent);
  assertCheck('playback_value_shows_5x', playbackValueText.trim() === '5.00×', playbackValueText);
  await page.locator('#sceneTools').screenshot({ path: join(OUT, 'speed5x.png') });

  /* ================= 5x 下补跑一遍时序核验(核实演示循环/补段在 5x 下无逻辑破绽) ================= */
  /* seek() 总是把 state.paused 设 true(暂停查看快照的既有语义);__S3_QA 没有公开的"播放"方法,
     真实用户走的是点 #pauseMotion 按钮(标「继续」时点一下翻回播放),这里照做,不能只设倍率不恢复播放。 */
  await page.evaluate(() => window.__S3_QA.seek(0, 'LOAD_IN', 0));
  const pausedAfterSeek = await page.evaluate(() => window.__S3_QA.snapshot().paused);
  if (pausedAfterSeek) await page.click('#pauseMotion');
  await page.evaluate(() => window.__S3_QA.setPlaybackMultiplier(5));
  const before5x = await page.evaluate(() => window.__S3_QA.snapshot());
  assertCheck('5x_setup_is_playing_not_paused', before5x.paused === false, JSON.stringify(before5x.paused));
  /* 连续采样 8 次(每次间隔 1s,共 8s 真实时间),而不是只首尾各测一次——
     防止"首尾都推进了但中途卡死又恢复"这类首尾对比测不出来的假阴性;
     同时统计跨越了多少个不同 operationKey 相位,确认真的在走七步而不是卡在同一相位反复重算。 */
  const samples = [before5x.checkpoint];
  for (let i = 0; i < 8; i += 1) {
    await page.waitForTimeout(1000);
    const snap = await page.evaluate(() => window.__S3_QA.snapshot());
    samples.push(snap.checkpoint);
    if (snap.runtimeErrors > 0) { assertCheck('5x_no_runtime_errors_mid_stream', false, `runtimeErrors=${snap.runtimeErrors} at sample ${i}`); break; }
  }
  const after5x = await page.evaluate(() => window.__S3_QA.snapshot());
  const noStall = samples.every((s, i) => {
    if (i === 0) return true;
    const prev = samples[i - 1];
    return s.cycleIndex > prev.cycleIndex || s.phase !== prev.phase || s.progress !== prev.progress || s.loop > prev.loop;
  });
  const distinctPhases = new Set(samples.map(s => s.phase)).size;
  assertCheck('5x_playback_advances_without_errors',
    after5x.runtimeErrors === 0 && noStall,
    JSON.stringify({ samples, runtimeErrors: after5x.runtimeErrors, noStall }));
  assertCheck('5x_passes_through_multiple_phases', distinctPhases >= 2, `distinctPhases=${distinctPhases} samples=${JSON.stringify(samples.map(s => s.phase))}`);
  assertCheck('5x_no_new_page_or_console_errors', report.pageErrors.length === 0, JSON.stringify(report.pageErrors));

} catch (e) {
  report.pass = false; report.checks._exception = { ok: false, detail: `${e.name}:${e.message}\n${e.stack}` };
} finally {
  await browser.close(); await new Promise(r => server.close(r));
}

report.pass = Object.values(report.checks).every(c => c.ok) && report.pageErrors.length === 0;
writeFileSync(join(OUT, 'w1_report.json'), JSON.stringify(report, null, 1), 'utf8');
const passCount = Object.values(report.checks).filter(c => c.ok).length, totalCount = Object.keys(report.checks).length;
console.log(`${report.pass ? 'PASS' : 'FAIL'} ${passCount}/${totalCount}; pageErrors=${report.pageErrors.length}; consoleErrors=${report.consoleErrors.length}`);
for (const [k, v] of Object.entries(report.checks)) if (!v.ok) console.log(`  FAIL ${k}: ${v.detail}`);
if (!report.pass) process.exitCode = 1;
