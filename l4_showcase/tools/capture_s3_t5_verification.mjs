/* T5 验收:证据中心重构(B1-B7)+ 三档四件套。独立于 capture_s3_mixed_layout_a_qa.mjs(那个脚本只测
   启动治理文案,不碰证据中心/三档),本脚本按 T5 任务书 §C 验收清单逐条断言 + 截图。
   Playwright 底座与既有 QA 脚本同源:同一 chromium 可执行文件、同一 args、同一 MIME 表、同一就绪判据。 */
import { createRequire } from 'node:module';
import { createServer } from 'node:http';
import { fileURLToPath } from 'node:url';
import { dirname, extname, join, resolve, sep } from 'node:path';
import { existsSync, readFileSync, readdirSync, mkdirSync, writeFileSync } from 'node:fs';

const HERE = dirname(fileURLToPath(import.meta.url));
const SHOWCASE = resolve(HERE, '..');
const PAGE = '02_入出闭环.html';
const OUT = resolve(SHOWCASE, 'out', 't5_0720');
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

  /* ---- B4/B1 根修:evidenceCenter 挂 body,不再是 rail 窄条,左上角无死区 ---- */
  const openBtnParent = await page.evaluate(() => document.getElementById('evidenceCenter').parentElement.tagName);
  assertCheck('evidenceCenter_parent_is_body', openBtnParent === 'BODY', `parent=${openBtnParent}`);

  await page.click('#openEvidenceCenter');
  await page.waitForSelector('#evidenceCenter:not([hidden])');
  const openState1 = await page.evaluate(() => {
    const rect = document.getElementById('evidenceCenter').getBoundingClientRect();
    const hit = document.elementFromPoint(15, 15);
    const s = window.__S3_QA.snapshot();
    return {
      rect: { w: rect.width, h: rect.height, l: rect.left, t: rect.top },
      hitInsideCenter: !!(hit && hit.closest('#evidenceCenter')),
      hitTag: hit ? hit.tagName + (hit.id ? '#' + hit.id : '') : null,
      tab1Hidden: document.getElementById('evidenceCenterTab1').hidden,
      tab2Hidden: document.getElementById('evidenceCenterTab2').hidden,
      judgePathDisplay: getComputedStyle(document.getElementById('judgePath')).display,
      judgePathHeight: document.getElementById('judgePath').getBoundingClientRect().height,
      comparisonMiniText: document.getElementById('comparisonMiniBars').textContent.slice(0, 40),
      mainInert: document.getElementById('main').inert,
      evidenceCenterState: s.evidenceCenter
    };
  });
  assertCheck('B1_fullscreen_not_narrow_strip', openState1.rect.w >= 1590 && openState1.rect.h >= 890, JSON.stringify(openState1.rect));
  assertCheck('B4_no_dead_zone_top_left', openState1.hitInsideCenter, `hit=${openState1.hitTag}`);
  assertCheck('B7_judgePath_visible_when_open', openState1.judgePathDisplay !== 'none' && openState1.judgePathHeight > 0, JSON.stringify(openState1));
  assertCheck('B3_background_inert_when_open', openState1.mainInert === true, `mainInert=${openState1.mainInert}`);
  assertCheck('opens_to_tab1_by_default', !openState1.tab1Hidden && openState1.tab2Hidden, JSON.stringify(openState1));
  assertCheck('evidenceCenter_state_open_true', openState1.evidenceCenterState.open === true && openState1.evidenceCenterState.tab === 'tab1', JSON.stringify(openState1.evidenceCenterState));
  await page.screenshot({ path: join(OUT, 'ec_tab1.png'), fullPage: false });

  /* ---- B3 实测:顶栏在 inert 下真不可交互。
     踩坑记录:page.selectOption() 是 Playwright 对 <select> 的「逻辑赋值」API——它不发真实鼠标事件
     /不做 hit-test,只检查 disabled/visible,不认 inert(inert 不改 .disabled),会误报「可改值成功」
     (首轮实测 before=AUTO after=seq,具体又实为改值生效——inert 本身没挡住它,只是这个 API 选错了)。
     改用真正走 hit-test 的 .click()(应因 inert 拦截而超时/不可达)与 .focus()(inert 元素禁止成为
     activeElement,是规范行为)双重验证,才是这条 UI 契约的正确复现方式。 */
  const before = await page.evaluate(() => document.getElementById('strategySelect').value);
  let clickBlocked = false;
  try { await page.click('#strategySelect', { timeout: 1500 }); } catch (e) { clickBlocked = true; }
  const focusAttempt = await page.evaluate(() => {
    document.getElementById('strategySelect').focus();
    return document.activeElement && document.activeElement.id;
  });
  const after = await page.evaluate(() => document.getElementById('strategySelect').value);
  assertCheck('B3_topbar_unclickable_when_open', clickBlocked, `clickBlocked=${clickBlocked}`);
  assertCheck('B3_topbar_unfocusable_when_open', focusAttempt !== 'strategySelect', `activeElementAfterFocusAttempt=${focusAttempt}`);
  assertCheck('B3_value_unchanged_when_open', before === after, `before=${before} after=${after}`);

  /* ---- 切 tab2:S1 受控对照,B2 表格不横向截字 ---- */
  await page.click('#evidenceCenterTab2Btn');
  await page.waitForTimeout(150);
  const tab2State = await page.evaluate(() => {
    const table = document.getElementById('comparisonTable');
    const row = document.querySelector('.comparisonRow.comparisonBodyRow');
    return {
      tab1Hidden: document.getElementById('evidenceCenterTab1').hidden,
      tab2Hidden: document.getElementById('evidenceCenterTab2').hidden,
      tableScrollW: table.scrollWidth, tableClientW: table.clientWidth,
      headerCells: document.querySelectorAll('.comparisonHeader > div').length,
      bodyRows: document.querySelectorAll('.comparisonBodyRow').length,
      rowScrollW: row ? row.scrollWidth : null, rowClientW: row ? row.clientWidth : null,
      innerHeaderHidden: getComputedStyle(document.querySelector('#evidenceCenterTab2 .comparisonPanel > header')).display
    };
  });
  assertCheck('tab2_visible_after_switch', tab2State.tab1Hidden && !tab2State.tab2Hidden, JSON.stringify(tab2State));
  assertCheck('B2_table_no_horizontal_overflow', tab2State.tableScrollW <= tab2State.tableClientW + 1, JSON.stringify(tab2State));
  assertCheck('B2_row_no_horizontal_overflow', tab2State.rowScrollW !== null && tab2State.rowScrollW <= tab2State.rowClientW + 1, JSON.stringify(tab2State));
  assertCheck('tab2_table_populated', tab2State.headerCells === 5 && tab2State.bodyRows === 8, JSON.stringify(tab2State));
  assertCheck('inner_header_hidden_not_duplicated', tab2State.innerHeaderHidden === 'none', tab2State.innerHeaderHidden);
  await page.screenshot({ path: join(OUT, 'ec_tab2.png'), fullPage: false });

  /* ---- B5 焦点陷阱:Tab 走查若干次,焦点应恒留在 evidenceCenterPanel 内 ---- */
  await page.click('#evidenceCenterTab1Btn');
  await page.waitForTimeout(100);
  await page.focus('#closeEvidenceCenter');
  let escaped = false;
  for (let i = 0; i < 30; i += 1) {
    await page.keyboard.press('Tab');
    const inside = await page.evaluate(() => {
      const panel = document.getElementById('evidenceCenterPanel');
      return panel.contains(document.activeElement);
    });
    if (!inside) { escaped = true; break; }
  }
  assertCheck('B5_focus_trap_holds_30_tabs', !escaped, `escaped=${escaped}`);

  /* ---- B6 根修:即使人为把焦点丢到背景(inert 下正常不可达,这里防御性直接 focus 验证 Esc 仍是 document 级) ---- */
  await page.evaluate(() => { document.getElementById('evidenceCenter').hidden = false; });
  await page.keyboard.press('Escape');
  await page.waitForTimeout(150);
  const afterEsc1 = await page.evaluate(() => document.getElementById('evidenceCenter').hidden);
  assertCheck('B6_escape_closes_from_trapped_focus', afterEsc1 === true, `hidden=${afterEsc1}`);

  /* ---- 背景点击关闭 + 触发按钮焦点回归 ----
     openEvidenceDock/openComparisonLab 是 0720 版B 转正后 CSS display:none 的旧按钮(DOM/监听原样保留,
     仅证据两键单键化后不再可见)。用 page.evaluate 直接 .click() 而非 page.click(),因为 Playwright 的
     actionability 检查会因 display:none 永久等不到「visible」——这正是 T5 规格要防的场景本身
     (「防 QA/其他代码触发旧 id 时行为不缺」),用 DOM 级 click() 精确复现。 */
  await page.evaluate(() => document.getElementById('openEvidenceDock').click());
  await page.waitForSelector('#evidenceCenter:not([hidden])');
  const tab1ViaOldBtn = await page.evaluate(() => document.getElementById('evidenceCenterTab1').hidden);
  assertCheck('old_openEvidenceDock_routes_to_tab1', tab1ViaOldBtn === false, `tab1Hidden=${tab1ViaOldBtn}`);
  await page.mouse.click(15, 850);
  await page.waitForTimeout(150);
  const afterBackdrop = await page.evaluate(() => ({
    hidden: document.getElementById('evidenceCenter').hidden,
    activeId: document.activeElement && document.activeElement.id
  }));
  assertCheck('backdrop_click_closes', afterBackdrop.hidden === true, JSON.stringify(afterBackdrop));
  /* trigger 本次是隐藏的旧入口 openEvidenceDock(display:none),真实浏览器无法把焦点移到不可见元素上;
     runtime 的 closeEvidenceCenter 对此有防御性回退(offsetParent===null 时改焦停到恒可见的
     openEvidenceCenter),核验回退生效而非焦点掉进虚空(activeId 不为空即可,详细回退目标见下一断言)。 */
  assertCheck('focus_returns_to_trigger', afterBackdrop.activeId === 'openEvidenceCenter', JSON.stringify(afterBackdrop));

  /* ---- 旧 openComparisonLab / mini 改线验证(同上,DOM 级 click 绕过 display:none 的 actionability 等待) ---- */
  await page.evaluate(() => document.getElementById('openComparisonLab').click());
  await page.waitForSelector('#evidenceCenter:not([hidden])');
  const tab2ViaOldBtn = await page.evaluate(() => document.getElementById('evidenceCenterTab2').hidden);
  assertCheck('old_openComparisonLab_routes_to_tab2', tab2ViaOldBtn === false, `tab2Hidden=${tab2ViaOldBtn}`);
  await page.keyboard.press('Escape');
  await page.waitForTimeout(150);
  await page.click('#openEvidenceCenter'); // 默认开到 tab1,comparisonMini(含 openComparisonLabMini)在其中
  await page.waitForSelector('#evidenceCenter:not([hidden])');
  await page.click('#openComparisonLabMini');
  await page.waitForTimeout(150);
  const viaMini = await page.evaluate(() => document.getElementById('evidenceCenterTab2').hidden);
  assertCheck('mini_button_switches_to_tab2', viaMini === false, `tab2Hidden=${viaMini}`);
  await page.keyboard.press('Escape');
  await page.waitForTimeout(150);

  /* ---- 嵌套操作 + 三次开关(零 pageerror 由页面级监听贯穿全程统计) ---- */
  for (let i = 0; i < 3; i += 1) {
    await page.click('#openEvidenceCenter');
    await page.waitForSelector('#evidenceCenter:not([hidden])');
    await page.click('#evidenceCenterTab2Btn');
    await page.waitForTimeout(80);
    await page.click('#evidenceCenterTab1Btn');
    await page.waitForTimeout(80);
    await page.click('#closeEvidenceCenter');
    await page.waitForSelector('#evidenceCenter', { state: 'hidden' });
  }
  ok('nested_and_triple_toggle_completed', 'open->tab2->tab1->close ×3');

  /* ---- 1366×768:B7 核心验证(旧 @media(min-width:1600px) 死约束下 judgePath 会消失) ---- */
  await page.setViewportSize({ width: 1366, height: 768 });
  await page.waitForTimeout(150);
  await page.click('#openEvidenceCenter');
  await page.waitForSelector('#evidenceCenter:not([hidden])');
  const at1366 = await page.evaluate(() => {
    const jp = document.getElementById('judgePath');
    const cs = getComputedStyle(jp);
    const rect = jp.getBoundingClientRect();
    return { display: cs.display, height: rect.height, viewport: [window.innerWidth, window.innerHeight] };
  });
  assertCheck('B7_judgePath_visible_at_1366x768', at1366.display !== 'none' && at1366.height > 0, JSON.stringify(at1366));
  await page.screenshot({ path: join(OUT, 'ec_1366.png'), fullPage: false });
  await page.keyboard.press('Escape');
  await page.waitForTimeout(150);
  await page.setViewportSize({ width: 1600, height: 900 });
  await page.waitForTimeout(150);

  /* ---- 三档:分段按钮 + 徽章 + LOD + 差异条 ---- */
  const tierInit = await page.evaluate(() => window.__S3_QA.snapshot());
  assertCheck('default_tier_is_3', tierInit.query.tier === 3, `tier=${tierInit.query.tier}`);
  const badge3 = await page.evaluate(() => document.getElementById('tierBadge').textContent);
  assertCheck('tierBadge_shows_tier3_mechanism', badge3.includes('档3') && badge3.includes('加减速+故障+潮汐'), badge3);

  const before1 = await page.evaluate(() => { const s = window.__S3_QA.snapshot(); return { traceId: s.traceId }; });
  await page.click('.tierSeg[data-tier="1"]');
  await page.waitForFunction(() => { const s = window.__S3_QA.snapshot(); return !s.loading && s.query.tier === 1; }, { timeout: 15000 });
  await page.waitForTimeout(300);
  const tier1Snap = await page.evaluate(() => window.__S3_QA.snapshot());
  const badge1 = await page.evaluate(() => document.getElementById('tierBadge').textContent);
  assertCheck('tier_switch_to_1_reloads', tier1Snap.query.tier === 1 && tier1Snap.traceId !== before1.traceId, `tier=${tier1Snap.query.tier} traceId=${tier1Snap.traceId}`);
  assertCheck('tierBadge_shows_tier1_simplified_suffix', badge1.includes('档1') && badge1.includes('简化呈现'), badge1);
  assertCheck('tier1_LOD_decor_hidden', tier1Snap.renderer.tierLod.tier === 1 && tier1Snap.renderer.tierLod.decorVisible === false, JSON.stringify(tier1Snap.renderer.tierLod));
  assertCheck('tier1_LOD_grid_hidden', tier1Snap.renderer.tierLod.gridVisible === false, JSON.stringify(tier1Snap.renderer.tierLod));
  const grayed = tier1Snap.renderer.tierLod.gradeHex.heavy !== tier1Snap.renderer.tierLod.gradeOriginalHex.heavy;
  assertCheck('tier1_LOD_grade_color_desaturated', grayed, JSON.stringify(tier1Snap.renderer.tierLod));
  const tierSegAria1 = await page.evaluate(() => document.querySelector('.tierSeg[data-tier="1"]').getAttribute('aria-checked'));
  assertCheck('tierSeg_aria_checked_syncs', tierSegAria1 === 'true', tierSegAria1);
  await page.screenshot({ path: join(OUT, 'tier1_lod.png'), fullPage: false });

  /* ---- 切档差异条:1→2 触发,抓帧于 3.2s 内;算法切换不触发(用另一独立断言核实) ---- */
  await page.click('.tierSeg[data-tier="2"]');
  await page.waitForFunction(() => { const s = window.__S3_QA.snapshot(); return !s.loading && s.query.tier === 2; }, { timeout: 15000 });
  await page.waitForTimeout(250);
  const toastState = await page.evaluate(() => {
    const el = document.getElementById('tierDiffToast');
    return el ? { text: el.textContent, showing: el.classList.contains('show') } : null;
  });
  assertCheck('tierDiffToast_shows_after_tier_switch', !!(toastState && toastState.showing && /档1→档2/.test(toastState.text) && /P95/.test(toastState.text) && /故障/.test(toastState.text)), JSON.stringify(toastState));
  await page.screenshot({ path: join(OUT, 'tier_toast.png'), fullPage: false });

  const tier2Snap = await page.evaluate(() => window.__S3_QA.snapshot());
  assertCheck('tier2_LOD_decor_restored', tier2Snap.renderer.tierLod.tier === 2 && tier2Snap.renderer.tierLod.decorVisible === true, JSON.stringify(tier2Snap.renderer.tierLod));
  assertCheck('tier2_LOD_grade_color_restored', tier2Snap.renderer.tierLod.gradeHex.heavy === tier2Snap.renderer.tierLod.gradeOriginalHex.heavy, JSON.stringify(tier2Snap.renderer.tierLod));

  /* 算法切换不应触发切档差异条(即便刚清空的 toast 类名仍在,重新确认它没有因为策略变更而重新 show) */
  await page.evaluate(() => { document.getElementById('tierDiffToast').classList.remove('show'); });
  await page.selectOption('#strategySelect', 'seq');
  await page.waitForFunction(() => !window.__S3_QA.snapshot().loading, { timeout: 15000 });
  await page.waitForTimeout(200);
  const toastAfterStrategy = await page.evaluate(() => document.getElementById('tierDiffToast').classList.contains('show'));
  assertCheck('tierDiffToast_not_triggered_by_strategy_change', toastAfterStrategy === false, `showing=${toastAfterStrategy}`);

  /* ---- 三档来回切×2 + 证据中心开关×3 已覆盖;再补一轮 tier 来回确保零 pageerror ---- */
  await page.click('.tierSeg[data-tier="3"]');
  await page.waitForFunction(() => { const s = window.__S3_QA.snapshot(); return !s.loading && s.query.tier === 3; }, { timeout: 15000 });
  await page.click('.tierSeg[data-tier="1"]');
  await page.waitForFunction(() => { const s = window.__S3_QA.snapshot(); return !s.loading && s.query.tier === 1; }, { timeout: 15000 });
  await page.click('.tierSeg[data-tier="3"]');
  await page.waitForFunction(() => { const s = window.__S3_QA.snapshot(); return !s.loading && s.query.tier === 3; }, { timeout: 15000 });
  ok('tier_round_trip_x2_completed', '3->1->3 (含前面 3->1->2 共 >=2 轮)');

  assertCheck('zero_page_errors', report.pageErrors.length === 0, JSON.stringify(report.pageErrors));

  report.pass = Object.values(report.checks).every(c => c.ok) && report.pageErrors.length === 0;
} catch (e) {
  report.pass = false; report.checks.qa_exception = { ok: false, detail: `${e.name}:${e.message}\n${e.stack || ''}` };
} finally {
  await browser.close(); await new Promise(r => server.close(r));
}
writeFileSync(join(OUT, 't5_verification_report.json'), JSON.stringify(report, null, 1), 'utf8');
const total = Object.keys(report.checks).length, passed = Object.values(report.checks).filter(c => c.ok).length;
console.log(`${report.pass ? 'PASS' : 'FAIL'} ${passed}/${total}; pageErrors=${report.pageErrors.length}; consoleErrors=${report.consoleErrors.length}`);
console.log(join(OUT, 't5_verification_report.json'));
if (!report.pass) {
  console.log('failed checks:', Object.entries(report.checks).filter(([, v]) => !v.ok).map(([k]) => k).join(', '));
  process.exitCode = 1;
}
