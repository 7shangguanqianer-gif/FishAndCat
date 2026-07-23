/* 54 格 FIO 证据页验收 QA(0722 一屏返工版)。
   基线(0717,任务信验收条 1-7,8/8):三视口无裁切/无水平滚动、控制台零错误、全部图片资源加载成功(无 404)、
   口径带常驻、"20×20"仅出现在边界说明语境、越界表述零命中、三张验收图落盘、五秒盲测。
   0721 回灌升级(施工规格_回灌0721.md §2.5):负结果七条逐字符与基线一致、素材引用文件存在性抽查(≥5 个真实
   路径 200)、矩阵数字 66/54/11 与内嵌 json 一致、video 元素存在、40 帧缩略数=40、口径句含「54 份=H5 验收链」、
   游离标签(候选/变体X 等 mock 命名)已删。合计 15 项断言。
   0722 一屏返工升级(施工规格_一屏返工0722.md §A+§C):页面从整页纵向滚动改顶部 4 Tab(证据画面/证据链/
   I/O 矩阵/边界与负结果)分区,每 Tab 一屏零竖滚。15 项断言语义全部保留(机制随结构调整:内容分散到 4 个
   Tab 面板后,原先"扫全页 innerText"的检查改为"逐 Tab 切换采集 innerText 后拼接再扫",DOM 级查询类断言
   不受影响)。新增 4 项:①Tab 四区切换各拍(4 Tab × 2 分辨率 = 8 张状态截图);②每 Tab 双分辨率零滚动
   (document 与所有 overflow-y 容器 scrollHeight ≤ clientHeight+2,弹层内部与显式横向带白名单);③弹大层
   开合(证据链卡片详情层 + 六站点详情层 + 图片 lightbox,均验证开/关两态);④Tab 键盘可达(左右键在 4 个
   Tab 间移动并激活,Home/End 跳首尾)。截图底座按 §A.4:animations disabled + caret hide,document.fonts.ready
   后再拍,语义就绪断言替代 networkidle/固定 sleep,双分辨率改为 1920×1080 与 1280×800(不再用 1440×900/
   1280×720,与 §A.1 设计基准对齐)。合计 19 项断言。 */
import { createRequire } from 'node:module';
import { createServer } from 'node:http';
import { extname, join, resolve, sep } from 'node:path';
import { existsSync, mkdirSync, readFileSync, readdirSync, statSync, writeFileSync } from 'node:fs';

const ROOT = 'F:/abb_wh_work';
const PAGE = 'l4_showcase/src/03_FIO物理证据.html';
const OUT = join(ROOT, 'l4_showcase', 'out', 'fio54_evidence_qa_0722');
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
const mime = {'.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.png': 'image/png', '.jpg': 'image/jpeg', '.mp4': 'video/mp4'};
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
const report = {schema: 'fio54-evidence-qa-v3-0722', consoleErrors: [], failedRequests: [], viewports: [], scrollTable: [], pass: false, errors: []};
const url = `http://127.0.0.1:${port}/${PAGE.split('/').map(encodeURIComponent).join('/')}`;

// 负结果七条基线(逐字符,取自回灌施工前的原页 <section id="neg"> 7 个 .item 块;h3/p 内部 HTML 原样保留;
// 0722 返工仅将呈现位置从常驻侧栏改为独立 Tab 双列网格,措辞红线不变,基线不改)
const NEG_BASELINE = [
  {
    "h3": "① 托盘侧翻,\"命令完成\"≠物理成功(0712)",
    "p": "动作序列日志完整结束(<span class=\"path\">logs/F3_probe_20260712_233238.log</span>),但现场截图托盘已在装载口护栏附近侧翻——上一轮宽视角\"成功\"判断被撤销。此后立规:<b>物理验收只认画面证据,不认命令返回</b>。"
  },
  {
    "h3": "② G4 下放 NOSTART:货物不在承载台(0713)",
    "p": "下放序列启动时格位承载台为空(<span class=\"path\">media/g4_evidence_0713/G4_lower_NOSTART_cell30_全景_152304.png、G4_货物在格位承载台空_裁剪.png</span>)。根因链见诊断日志;该轮不计成功。"
  },
  {
    "h3": "③ 传感器极性误判(已作废结论)",
    "p": "At Entry/Load/Unload/Exit 实为 active-low(False=有货遮挡)。曾凭远景+At Load=False 误判\"空载\",0713 实物极性复核后作废(<span class=\"path\">io_map.md 头注</span>)。"
  },
  {
    "h3": "④ 叉臂保持型命令契约(曾把货拉回)",
    "p": "Forks Left/Right 是保持型命令,撤销即自动回 Middle——\"到限位即撤销\"的旧逻辑在取放中把货物拉回,已禁用;正确序列=全程保持对应叉臂输出直至交接完成(<span class=\"path\">io_map.md「叉臂取放动作契约」</span>)。"
  },
  {
    "h3": "⑤ F6 复位陷阱与\"无 Z 必须重启\"纪律",
    "p": "F6 只清理场景货物,不能复位控制输出或微升降机构:F6 后实测 Forks Left 到位、Lift=True 却无 Moving Z。任一无 Z、recovery 或掉落后必须保存证据并<b>完整退出重启 Factory I/O</b>,不得按 F6 续跑同一验收链。"
  },
  {
    "h3": "⑥ Emitter 强制值污染",
    "p": "Emitter tag 曾处于 isForced=true:普通写 false 不生效,必须 <span class=\"path\">PUT /api/tag/values-force</span> 显式 force false;单箱生成只能短暂 force true,At Entry 检出后立即 force false,否则连续生成多托货污染验收(<span class=\"path\">io_map.md「Emitter 强制值陷阱」</span>)。"
  },
  {
    "h3": "⑦ 能力边界:为什么不做 400 格物理(No-Go 裁决摘要)",
    "p": "Factory I/O 原生堆垛机目标位固定 1..54;Analog X/Z 只能在固定行程(10.5 m/6.625 m)内连续定位,No-Go 反证计算:若强行铺满 20×20 中心点,格距被压到约 0.553 m×0.349 m 且未扣端部余量;SDK/Web API 只开放 I/O tag,不开放自定义三维部件与碰撞体(厂商 2025 明确答复)。<b>结论:v2.5.10 内严格 400 格物理方案 No-Go——瓶颈是几何与运动学,不是地址容量。</b>一手来源五条见 <span class=\"path\">l2_factoryio/0713_F3碰撞闭环与20x20边界设计.md §1.3</span>。"
  }
];

// 素材引用文件存在性抽查:>=5 个真实项目内路径,页面自身相对路径写法(从 src/ 出发)
const ASSET_PATHS = [
  "../../l2_factoryio/img/F2_modbus_server_default_mapping_0712.png",
  "../../l2_factoryio/media/g4_evidence_0713/H5_9of9_终验_三格齐放第三轮.png",
  "../../l2_factoryio/media/g4_evidence_0713/G2_pick_带载确认_145804.png",
  "../../l2_factoryio/media/g4_evidence_0713/P3_官方原版放箱成功_货留格内_155815.png",
  "../../l2_factoryio/media/g4_evidence_0713/G4_lower_NOSTART_cell30_全景_152304.png",
  "../../l2_factoryio/media/F3_素材_cell30全链_0713/F3_cell30_全链素材.mp4",
  "../../l2_factoryio/media/F3_素材_cell30全链_0713/f_001.png",
  "../../l2_factoryio/media/F3_素材_cell30全链_0713/f_040.png"
];

const TABS = ["views", "chain", "matrix", "neg"];
const VIEWPORTS = [[1920, 1080], [1280, 800]]; // §A.1/§A.4:设计基准+收纳基准,不再用 1440×900/1280×720

function tabStateAssert() {
  // 页面内 evaluate:断言点击后 4 个 tab 的 aria-selected/hidden 是否与预期一致(§A.4 状态断言)
  return `(function(activeKey){
    const tabs=["views","chain","matrix","neg"];
    return tabs.every(function(k){
      const btn=document.getElementById("tab-"+k), panel=document.getElementById("panel-"+k);
      const shouldBeActive = (k===activeKey);
      return btn.getAttribute("aria-selected")===String(shouldBeActive) && panel.hidden===!shouldBeActive;
    });
  })`;
}

try {
  for (const [w, h] of VIEWPORTS) {
    const page = await browser.newPage({viewport: {width: w, height: h}});
    page.on('pageerror', e => report.consoleErrors.push(`${w}x${h}: ${e.message}`));
    page.on('console', m => { if (m.type() === 'error') report.consoleErrors.push(`${w}x${h} console: ${m.text()}`); });
    page.on('requestfailed', r => report.failedRequests.push(`${w}x${h}: ${r.url()}`));
    page.on('response', r => { if (r.status() >= 400) report.failedRequests.push(`${w}x${h} ${r.status()}: ${r.url()}`); });

    await page.goto(url, {waitUntil: 'load'});
    // 语义就绪断言替代 networkidle/固定 sleep(§A.4):等矩阵表 11 行、40 帧缩略、4 个 Tab 均已渲染
    await page.waitForFunction(() =>
      document.querySelectorAll('#matrixBody tr').length === 11 &&
      document.querySelectorAll('.frameStrip img').length === 40 &&
      document.querySelectorAll('#pageTabs [role="tab"]').length === 4
    );
    await page.evaluate(() => document.fonts.ready);

    const tabTexts = [];
    const imgSeen = new Map();
    let modalChainOk = false, modalStationOk = false, modalLightboxOk = false;

    for (const tabKey of TABS) {
      await page.click(`#tab-${tabKey}`);
      const stateOk = await page.evaluate(tabStateAssert() + `("${tabKey}")`);

      // 该 tab 可见后强制 lazy->eager 触发加载并等待就绪(逐 tab 访问确保每张图都曾"可见"过)
      await page.evaluate(async () => {
        document.querySelectorAll('img[loading="lazy"]').forEach(img => { img.loading = 'eager'; });
        await Promise.all([...document.images].map(img => {
          if (img.complete || !img.getAttribute('src')) return Promise.resolve();
          return new Promise(res => {
            img.addEventListener('load', res, {once: true});
            img.addEventListener('error', res, {once: true});
            setTimeout(res, 4000);
          });
        }));
      });
      await page.evaluate(() => document.fonts.ready);

      // 截图底座(§A.4):animations disabled + caret hide;Tab 四区切换各拍
      await page.screenshot({path: join(OUT, `tab_${tabKey}_${w}x${h}.png`), animations: 'disabled', caret: 'hide'});

      const audit = await page.evaluate(() => {
        const docEl = document.documentElement;
        const overflowViolations = [...document.querySelectorAll('*')].filter(el => {
          const cs = getComputedStyle(el);
          return (cs.overflowY === 'auto' || cs.overflowY === 'scroll') && !el.closest('#bigModal,#lightbox');
        }).filter(el => el.scrollHeight > el.clientHeight + 2)
          .map(el => ({tag: el.tagName, id: el.id, cls: el.className, scrollH: el.scrollHeight, clientH: el.clientHeight}));
        const imgs = [...document.images].filter(i => !!i.getAttribute('src')).map(i => ({src: i.getAttribute('src'), ok: i.complete && i.naturalWidth > 0}));
        return {
          docScrollH: docEl.scrollHeight, clientH: docEl.clientHeight, innerH: window.innerHeight,
          zeroScrollOk: docEl.scrollHeight <= docEl.clientHeight + 2,
          hScroll: docEl.scrollWidth > window.innerWidth + 1,
          overflowViolations,
          bodyText: document.body.innerText,
          imgs
        };
      });
      tabTexts.push(audit.bodyText);
      audit.imgs.forEach(i => imgSeen.set(i.src, i.ok || imgSeen.get(i.src) === true));
      report.scrollTable.push({
        w, h, tab: tabKey, stateOk,
        docScrollH: audit.docScrollH, clientH: audit.clientH, innerH: audit.innerH,
        zeroScrollOk: audit.zeroScrollOk, hScroll: audit.hScroll,
        overflowViolations: audit.overflowViolations
      });

      // 弹大层开合(§A.3/§C.3):证据链卡片详情层(chain tab)、六站点详情层(matrix tab)、图片 lightbox(views tab)
      if (tabKey === 'chain') {
        await page.click('#chainGrid .chainCard:nth-child(1)');
        const openedOk = await page.evaluate(() => {
          const m = document.getElementById('bigModal');
          return m.hidden === false && document.getElementById('bigModalBody').innerText.length > 20;
        });
        await page.screenshot({path: join(OUT, `modal_chain_open_${w}x${h}.png`), animations: 'disabled', caret: 'hide'});
        await page.keyboard.press('Escape');
        const closedOk = await page.evaluate(() => document.getElementById('bigModal').hidden === true);
        modalChainOk = openedOk && closedOk;
      }
      if (tabKey === 'matrix') {
        // 按文本定位「叉臂 / Lift」站点按钮(不用位置类选择器,禁 nth-of-type 纪律同样适用于测试脚本)
        await page.getByRole('tab', {name: /叉臂/}).click();
        const openedOk = await page.evaluate(() => {
          const m = document.getElementById('bigModal');
          return m.hidden === false && !!document.querySelector('#bigModalBody .modalStation table');
        });
        await page.screenshot({path: join(OUT, `modal_station_open_${w}x${h}.png`), animations: 'disabled', caret: 'hide'});
        await page.evaluate(() => document.getElementById('bigModal').click());
        const closedOk = await page.evaluate(() => document.getElementById('bigModal').hidden === true);
        modalStationOk = openedOk && closedOk;
      }
      if (tabKey === 'views') {
        await page.click('#viewImg');
        const openedOk = await page.evaluate(() => document.getElementById('lightbox').hidden === false);
        await page.screenshot({path: join(OUT, `modal_lightbox_open_${w}x${h}.png`), animations: 'disabled', caret: 'hide'});
        await page.keyboard.press('Escape');
        const closedOk = await page.evaluate(() => document.getElementById('lightbox').hidden === true);
        modalLightboxOk = openedOk && closedOk;
      }
    }

    // Tab 键盘可达:左右键在 4 个 tab 间移动并激活;Home/End 跳首尾(§C 要点⑥)
    await page.click('#tab-views');
    await page.focus('#tab-views');
    await page.keyboard.press('ArrowRight');
    const kbRightOk = await page.evaluate(() => document.activeElement.id === 'tab-chain' && document.getElementById('tab-chain').getAttribute('aria-selected') === 'true' && document.getElementById('panel-chain').hidden === false);
    await page.keyboard.press('ArrowLeft');
    const kbLeftOk = await page.evaluate(() => document.activeElement.id === 'tab-views' && document.getElementById('tab-views').getAttribute('aria-selected') === 'true');
    await page.keyboard.press('End');
    const kbEndOk = await page.evaluate(() => document.activeElement.id === 'tab-neg' && document.getElementById('panel-neg').hidden === false);
    await page.keyboard.press('Home');
    const kbHomeOk = await page.evaluate(() => document.activeElement.id === 'tab-views' && document.getElementById('panel-views').hidden === false);
    const tabKeyboardNavOk = kbRightOk && kbLeftOk && kbEndOk && kbHomeOk;

    // 全页拼接文本(4 tab 依次采集后拼接,语义等价于回灌前"扫整页 innerText")
    const fullText = tabTexts.join('\n');

    const negAndDom = await page.evaluate(({negBaseline, assetPaths}) => {
      const negSection = document.getElementById('neg');
      const negItems = negSection ? [...negSection.querySelectorAll('.item')] : [];
      const negMismatches = [];
      if (negItems.length !== negBaseline.length) negMismatches.push(`count mismatch: dom=${negItems.length} baseline=${negBaseline.length}`);
      negBaseline.forEach((b, idx) => {
        const el = negItems[idx];
        if (!el) { negMismatches.push(`item ${idx + 1} missing`); return; }
        const h3 = (el.querySelector('h3')?.innerHTML || '').trim();
        const p = (el.querySelector('p')?.innerHTML || '').trim();
        if (h3 !== b.h3) negMismatches.push(`item ${idx + 1} h3 mismatch`);
        if (p !== b.p) negMismatches.push(`item ${idx + 1} p mismatch`);
      });

      let matrixJson = null, matrixJsonError = null;
      try { matrixJson = JSON.parse(document.getElementById('f3MatrixData').textContent); }
      catch (e) { matrixJsonError = e.message; }

      const videoEl = document.querySelector('#assetLib video[controls][preload="metadata"]');
      const videoSourceEl = videoEl ? videoEl.querySelector('source[type="video/mp4"]') : null;
      const videoOk = !!videoEl && !!videoSourceEl && /F3_cell30_全链素材\.mp4$/.test(videoSourceEl.getAttribute('src') || '');

      const frameCount = document.querySelectorAll('.frameStrip img').length;

      const strayTerms = ['Claude 候选', '独立证据页', '不属于 S3 算法页面族', '变体D', '变体F', '变体E'];
      const strayFound = strayTerms.filter(t => document.documentElement.innerHTML.includes(t));

      return {negMismatches, negOk: negMismatches.length === 0, matrixJson, matrixJsonError, videoOk, frameCount, strayFound};
    }, {negBaseline: NEG_BASELINE, assetPaths: ASSET_PATHS});

    // 素材引用文件存在性抽查(fetch 相对路径,与页面自身引用写法一致)
    const assetChecks = await page.evaluate(async (assetPaths) => {
      const results = await Promise.all(assetPaths.map(async (p) => {
        try { const r = await fetch(p); return {p, status: r.status, ok: r.ok}; }
        catch (e) { return {p, status: 0, ok: false, error: String(e)}; }
      }));
      return results;
    }, ASSET_PATHS);
    const assetExistCount = assetChecks.filter(x => x.ok).length;

    // 20×20 语境审计 + 越界词审计 + 五秒盲测 + 54/66 口径句(在拼接后的全页文本上跑,语义等价回灌前)
    const ctxs = [];
    let i = -1;
    while ((i = fullText.indexOf('20×20', i + 1)) !== -1) ctxs.push(fullText.slice(Math.max(0, i - 60), i + 66));
    const boundaryWords = /非|不等同|不宣称|No-Go|不做|不证明|映射|孪生|边界/;
    const risky = ['完全闭环', '数字孪生', '400 格物理实现', '在线实测'];
    const riskyViolations = [];
    for (const term of risky) {
      let j = -1;
      while ((j = fullText.indexOf(term, j + 1)) !== -1) {
        const ctx = fullText.slice(Math.max(0, j - 30), j + term.length + 20);
        if (!/不|非|未|禁|≠|No-Go|边界/.test(ctx)) riskyViolations.push(ctx);
      }
    }
    const band = await page.evaluate(() => {
      const el = document.getElementById('scopeBand');
      const r = el.getBoundingClientRect();
      return {top: r.top, height: r.height, visible: r.top >= 0 && r.height > 0, text: el.textContent};
    });

    const matrixNumbersOk = !!negAndDom.matrixJson &&
      negAndDom.matrixJson.total_files === 66 &&
      negAndDom.matrixJson.summary.total_groups === 11 &&
      negAndDom.matrixJson.summary.h5_chain_files === 54 &&
      negAndDom.matrixJson.summary.h5_chain_groups === 9 &&
      fullText.includes('66 份') && fullText.includes('11 组') && fullText.includes('54 份=H5 验收链');
    const caliberOk = fullText.includes('66 份含验收前预演与验收后复核,其中 54 份=H5 验收链(9链×6相位)');

    const imgs = [...imgSeen.entries()].map(([src, ok]) => ({src, ok}));

    report.viewports.push({
      w, h,
      imgs, bandVisible: band.visible, bandSingleLine: band.height > 0 && band.height < 40,
      hScroll: report.scrollTable.filter(r => r.w === w && r.h === h).some(r => r.hScroll),
      zeroScrollAllTabsOk: report.scrollTable.filter(r => r.w === w && r.h === h).every(r => r.zeroScrollOk && r.overflowViolations.length === 0),
      tabStateAllOk: report.scrollTable.filter(r => r.w === w && r.h === h).every(r => r.stateOk),
      ctx2020: ctxs, ctx2020AllBounded: ctxs.length > 0 && ctxs.every(c => boundaryWords.test(c)),
      riskyViolations, forbiddenHit: riskyViolations.length > 0,
      blindCheck: /54 格/.test(fullText) && /物理 I\/O/.test(fullText) && band.text.includes('技术预演'),
      negMismatches: negAndDom.negMismatches, negOk: negAndDom.negOk,
      matrixJsonError: negAndDom.matrixJsonError, matrixNumbersOk, caliberOk,
      videoOk: negAndDom.videoOk, frameCount: negAndDom.frameCount, frameCountOk: negAndDom.frameCount === 40,
      strayFound: negAndDom.strayFound, strayOk: negAndDom.strayFound.length === 0,
      assetChecks, assetExistCount, assetExistOk: assetExistCount >= 5,
      modalChainOk, modalStationOk, modalLightboxOk, tabKeyboardNavOk
    });
    await page.close();
  }

  const a = report.assertions = {
    noConsoleErrors: report.consoleErrors.length === 0,
    noFailedRequests: report.failedRequests.length === 0,
    allImagesLoaded: report.viewports.every(v => v.imgs.length >= 1 && v.imgs.every(i => i.ok)),
    scopeBandSingleLine: report.viewports.every(v => v.bandVisible && v.bandSingleLine),
    noHorizontalScroll: report.viewports.every(v => !v.hScroll),
    grid2020OnlyInBoundary: report.viewports.every(v => v.ctx2020.length > 0 && v.ctx2020AllBounded),
    noForbiddenTerms: report.viewports.every(v => !v.forbiddenHit),
    blindFiveSecond: report.viewports.every(v => v.blindCheck),
    negResultsVerbatim: report.viewports.every(v => v.negOk),
    assetPathsExist5: report.viewports.every(v => v.assetExistOk),
    matrixNumbers66_54_11: report.viewports.every(v => v.matrixNumbersOk && !v.matrixJsonError),
    videoElementExists: report.viewports.every(v => v.videoOk),
    frameThumbCount40: report.viewports.every(v => v.frameCountOk),
    caliberSentencePresent: report.viewports.every(v => v.caliberOk),
    strayLabelsRemoved: report.viewports.every(v => v.strayOk),
    // 0722 一屏返工新增 4 项(§A+§C.3)
    tabSwitchAllCaptured: report.viewports.every(v => v.tabStateAllOk),
    zeroScrollAllTabsBothViewports: report.viewports.every(v => v.zeroScrollAllTabsOk),
    modalOpenCloseWorks: report.viewports.every(v => v.modalChainOk && v.modalStationOk && v.modalLightboxOk),
    tabKeyboardNav: report.viewports.every(v => v.tabKeyboardNavOk)
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
if (!report.pass) { console.log('errors:', report.errors); process.exitCode = 1; }
