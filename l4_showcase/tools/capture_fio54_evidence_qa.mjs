/* 54 格 FIO 证据页验收 QA。
   基线(0717,任务信验收条 1-7,8/8):三视口无裁切/无水平滚动、控制台零错误、全部图片资源加载成功(无 404)、
   口径带常驻、"20×20"仅出现在边界说明语境、越界表述零命中、三张验收图落盘、五秒盲测。
   0721 回灌升级新增(施工规格 §2.5,适配既有脚本而非新写):负结果七条逐字符与基线一致、素材引用文件
   存在性抽查(≥5 个真实路径 200)、矩阵数字 66/54/11 与内嵌 json 一致、video 元素存在、40 帧缩略数=40、
   口径句含「54 份=H5 验收链」、游离标签(候选/变体X 等 mock 命名)已删。合计 15 项断言。 */
import { createRequire } from 'node:module';
import { createServer } from 'node:http';
import { extname, join, resolve, sep } from 'node:path';
import { existsSync, mkdirSync, readFileSync, readdirSync, statSync, writeFileSync } from 'node:fs';

const ROOT = 'F:/abb_wh_work';
const PAGE = 'l4_showcase/src/03_FIO物理证据.html';
const OUT = join(ROOT, 'l4_showcase', 'out', 'fio54_evidence_qa_0721');
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
const report = {schema: 'fio54-evidence-qa-v2-0721', consoleErrors: [], failedRequests: [], viewports: [], pass: false, errors: []};
const url = `http://127.0.0.1:${port}/${PAGE.split('/').map(encodeURIComponent).join('/')}`;

// 负结果七条基线(逐字符,取自回灌施工前的原页 <section id="neg"> 7 个 .item 块;h3/p 内部 HTML 原样保留)
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

try {
  let textAudit = null;
  for (const [w, h] of [[1280, 720], [1440, 900], [1920, 1080]]) {
    const page = await browser.newPage({viewport: {width: w, height: h}});
    page.on('pageerror', e => report.consoleErrors.push(`${w}x${h}: ${e.message}`));
    page.on('console', m => { if (m.type() === 'error') report.consoleErrors.push(`${w}x${h} console: ${m.text()}`); });
    page.on('requestfailed', r => report.failedRequests.push(`${w}x${h}: ${r.url()}`));
    page.on('response', r => { if (r.status() >= 400) report.failedRequests.push(`${w}x${h} ${r.status()}: ${r.url()}`); });
    await page.goto(url, {waitUntil: 'networkidle'});
    const audit = await page.evaluate(async ({negBaseline, assetPaths}) => {
      // 页面用 loading="lazy" 做 40 帧缩略带与卡片缩略图的性能优化(有意为之,非缺陷)。
      // 自动化审计不会真的滚动到每张图,需先强制 lazy -> eager 触发加载,再等待全部图片就绪,
      // 否则会把"尚未进入视口故未加载"误判为"图片损坏"。#lightboxImg 初始 src="" 是有意的空占位
      // (弹层未触发前不应有内容),不计入"图片加载"断言。
      document.querySelectorAll('img[loading="lazy"]').forEach(img => { img.loading = 'eager'; });
      await Promise.all([...document.images].map(img => {
        if (img.complete || !img.getAttribute('src')) return Promise.resolve();
        return new Promise(res => {
          img.addEventListener('load', res, {once: true});
          img.addEventListener('error', res, {once: true});
          setTimeout(res, 4000);
        });
      }));
      const imgs = [...document.images]
        .filter(i => !!i.getAttribute('src')) // 排除 #lightboxImg 等有意的空 src 占位元素
        .map(i => ({src: i.getAttribute('src'), ok: i.complete && i.naturalWidth > 0}));
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

      // ---- 0721 新增断言 ----
      // 负结果七条逐字符与基线一致
      const negSection = document.getElementById('neg');
      const negItems = negSection ? [...negSection.querySelectorAll('.item')] : [];
      const negMismatches = [];
      if (negItems.length !== negBaseline.length) {
        negMismatches.push(`count mismatch: dom=${negItems.length} baseline=${negBaseline.length}`);
      }
      negBaseline.forEach((b, idx) => {
        const el = negItems[idx];
        if (!el) { negMismatches.push(`item ${idx + 1} missing`); return; }
        const h3 = (el.querySelector('h3')?.innerHTML || '').trim();
        const p = (el.querySelector('p')?.innerHTML || '').trim();
        if (h3 !== b.h3) negMismatches.push(`item ${idx + 1} h3 mismatch`);
        if (p !== b.p) negMismatches.push(`item ${idx + 1} p mismatch`);
      });

      // 矩阵数字 66/54/11 与内嵌 json 一致 + 口径句
      let matrixJson = null, matrixJsonError = null;
      try { matrixJson = JSON.parse(document.getElementById('f3MatrixData').textContent); }
      catch (e) { matrixJsonError = e.message; }
      const matrixNumbersOk = !!matrixJson &&
        matrixJson.total_files === 66 &&
        matrixJson.summary.total_groups === 11 &&
        matrixJson.summary.h5_chain_files === 54 &&
        matrixJson.summary.h5_chain_groups === 9 &&
        body.includes('66 份') && body.includes('11 组') && body.includes('54 份=H5 验收链');
      const caliberOk = body.includes('66 份含验收前预演与验收后复核,其中 54 份=H5 验收链(9链×6相位)');

      // video 元素存在
      const videoEl = document.querySelector('#assetLib video[controls][preload="metadata"]');
      const videoSourceEl = videoEl ? videoEl.querySelector('source[type="video/mp4"]') : null;
      const videoOk = !!videoEl && !!videoSourceEl && /F3_cell30_全链素材\.mp4$/.test(videoSourceEl.getAttribute('src') || '');

      // 40 帧缩略数
      const frameCount = document.querySelectorAll('.frameStrip img').length;

      // 游离标签(mock 变体命名/旧候选标签)已删
      const strayTerms = ['Claude 候选', '独立证据页', '不属于 S3 算法页面族', '变体D', '变体F', '变体E'];
      const strayFound = strayTerms.filter(t => document.documentElement.innerHTML.includes(t));

      // 素材引用文件存在性抽查(fetch 相对路径,与页面自身引用写法一致)
      const assetChecks = await Promise.all(assetPaths.map(async (p) => {
        try { const r = await fetch(p); return {p, status: r.status, ok: r.ok}; }
        catch (e) { return {p, status: 0, ok: false, error: String(e)}; }
      }));
      const assetExistCount = assetChecks.filter(x => x.ok).length;

      return {
        imgs, bandVisible,
        hScroll: document.documentElement.scrollWidth > innerWidth + 1,
        ctx2020: ctxs, ctx2020AllBounded: ctxs.length > 0 && ctxs.every(c => boundaryWords.test(c)),
        riskyViolations, forbiddenHit: riskyViolations.length > 0,
        blindCheck: /54 格/.test(body) && /物理 I\/O/.test(body) && band.textContent.includes('技术预演'),
        negMismatches, negOk: negMismatches.length === 0,
        matrixJsonError, matrixNumbersOk, caliberOk,
        videoOk, frameCount, frameCountOk: frameCount === 40,
        strayFound, strayOk: strayFound.length === 0,
        assetChecks, assetExistCount, assetExistOk: assetExistCount >= 5
      };
    }, {negBaseline: NEG_BASELINE, assetPaths: ASSET_PATHS});
    report.viewports.push({w, h, ...audit});
    await page.screenshot({path: join(OUT, `viewport_${w}x${h}_首屏.png`)});
    if (w === 1440) {
      await page.locator('#chain button').first().click();
      await page.evaluate(() => document.querySelector('#stationDetail details').open = true);
      await page.screenshot({path: join(OUT, '验收图2_IO链展开.png')});
      await page.evaluate(() => document.getElementById('matrixTable').scrollIntoView());
      await page.screenshot({path: join(OUT, '验收图3_矩阵仪表.png')});
      await page.evaluate(() => document.getElementById('neg').scrollIntoView());
      await page.screenshot({path: join(OUT, '验收图4_边界与负结果.png')});
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
    blindFiveSecond: report.viewports.every(v => v.blindCheck),
    negResultsVerbatim: report.viewports.every(v => v.negOk),
    assetPathsExist5: report.viewports.every(v => v.assetExistOk),
    matrixNumbers66_54_11: report.viewports.every(v => v.matrixNumbersOk && !v.matrixJsonError),
    videoElementExists: report.viewports.every(v => v.videoOk),
    frameThumbCount40: report.viewports.every(v => v.frameCountOk),
    caliberSentencePresent: report.viewports.every(v => v.caliberOk),
    strayLabelsRemoved: report.viewports.every(v => v.strayOk)
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
