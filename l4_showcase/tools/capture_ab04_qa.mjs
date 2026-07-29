/* 04 AB 工程页 QA(0729 新建)。

   这页和 00 导览页是同一种失效模式:不会崩、不会渲染错,只会**悄悄说假话**——
   引一个已改名的文件、写一个已过时的数字。所以这套门全部指向
   「页面上印的数 / 路径,与仓库当前实际是否一致」,而不是"能不能渲染出来"。

   页面本身由 scratchpad/ab_final_gen.js 生成,但本 QA **不读生成器**——
   只读成品 HTML 与仓库源文件两侧,免得生成器和页面一起错还互相背书。
*/
import { chromium } from 'playwright';
import { createServer } from 'node:http';
import { readFileSync, existsSync, statSync, mkdirSync, writeFileSync, readdirSync } from 'node:fs';
import { join, resolve, extname, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const SHOWCASE = resolve(HERE, '..');
const PROJECT_ROOT = resolve(SHOWCASE, '..');
const PAGE = '04_AB工程.html';
const OUT = join(SHOWCASE, 'out', 'ab04_qa_0729');
const CHROME = 'C:/Users/86177/AppData/Local/ms-playwright/chromium-1223/chrome-win64/chrome.exe';

mkdirSync(OUT, { recursive: true });

const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8', '.css': 'text/css; charset=utf-8',
  '.png': 'image/png', '.jpg': 'image/jpeg' };

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
const BASE = `http://127.0.0.1:${server.address().port}`;

/* ---------- 仓库侧真值:每条都写清怎么算出来的 ---------- */
const readRepo = (p) => readFileSync(join(PROJECT_ROOT, p), 'utf8');

const stTest = readRepo('plc/06_PRG_Test.st');
const N_CASES = Number((stTest.match(/N_CASES\s*:\s*INT\s*:=\s*(\d+)/) || [])[1]);
/* aResult[n] := 的去重编号数,应与 N_CASES 相等 */
const assignIdx = [...new Set([...stTest.matchAll(/aResult\[(\d+)\]\s*:=/g)].map(m => Number(m[1])))].sort((a, b) => a - b);

const syncPy = readRepo('tools/ab_scripting/sync_st.py');
const mapBody = (syncPy.match(/MAP = \[([\s\S]*?)^\]/m) || [])[1] || '';
const mapRows = [...mapBody.matchAll(/\(\s*["']([^"']+)["']\s*,\s*["']([^"']+)["']\s*,\s*["']([^"']+)["']\s*\)/g)]
  .map(m => ({ name: m[1], file: m[2], kind: m[3] }));

/* wc -l 同义:数换行符 */
const ST_FILES = ['01_DUTs.st', '02_GVL.st', '03_Functions.st', '04_FB_Warehouse.st', '05_PRG_Main.st',
  '06_PRG_Test.st', '07_GVL_Data_generated.st', '08_GVL_WeightPolicy_generated.st', '09_FB_ScanLoadProbeNs_备用.st'];
const totalLines = ST_FILES.reduce((s, f) => s + (readRepo('plc/' + f).match(/\n/g) || []).length, 0);

const syncLog = readRepo('tools/ab_scripting/logs/sync_result_20260717_010514.txt');
const testLog = readRepo('tools/ab_scripting/logs/runtest_result_20260717_010514.txt');
const syncedCount = (syncLog.match(/^SYNCED:/gm) || []).length;
const iPassed = Number((testLog.match(/iPassed = INT#(\d+)/) || [])[1]);
const iFailed = Number((testLog.match(/iFailed = INT#(\d+)/) || [])[1]);

const genSt = readRepo('plc/07_GVL_Data_generated.st');
const cbExpt = (genSt.match(/CB_EXPT\s*:\s*REAL\s*:=\s*([\d.]+)/) || [])[1];
const tobExpt = (genSt.match(/TOB_EXPT\s*:\s*REAL\s*:=\s*([\d.]+)/) || [])[1];

/* ---------- 打开页面 ---------- */
const browser = await chromium.launch({ executablePath: CHROME });
const page = await browser.newPage({ viewport: { width: 1552, height: 900 }, deviceScaleFactor: 1 });
const pageErrors = [];
page.on('pageerror', e => pageErrors.push(String(e)));
await page.goto(`${BASE}/l4_showcase/src/${encodeURIComponent(PAGE)}`);
await page.waitForTimeout(300);

const dom = await page.evaluate(() => {
  const txt = document.body.innerText;
  const num = (re) => { const m = txt.match(re); return m ? Number(m[1].replace(/,/g, '')) : null; };
  window.scrollTo(9999, 0); const realScrollX = window.scrollX; window.scrollTo(0, 0);
  const bar = getComputedStyle(document.getElementById('brand'));
  return {
    text: txt,
    cells: document.querySelectorAll('.cell').length,
    cellNums: [...document.querySelectorAll('.gcells .cell')].map(e => Number(e.textContent)).sort((a, b) => a - b),
    objChips: document.querySelectorAll('.objChip').length,
    objNames: [...document.querySelectorAll('.objChip')].map(e => e.textContent.trim()),
    shotSlots: document.querySelectorAll('.shotSlot').length,
    sections: [...document.querySelectorAll('.sectionLead .idx')].map(e => e.textContent),
    serif: [...document.querySelectorAll('*')].filter(e => {
      const f = getComputedStyle(e).fontFamily || '';
      return /Georgia|Songti|SimSun/i.test(f);
    }).length,
    realScrollX,
    barH: bar.height, barBorder: bar.borderBottomWidth + ' ' + bar.borderBottomColor,
    /* 页面上所有 monospace 路径,用于文件存在硬门 */
    paths: [...new Set([...document.querySelectorAll('.src, .path, .lright .src')]
      .flatMap(e => (e.textContent.match(/(?:plc|tools|sim)[\/\\][^\s,;:()、,;。]*/g) || [])))],
  };
});

/* ---------- 门 ---------- */
const gates = [];
const gate = (name, pass, detail) => gates.push({ name, pass: !!pass, detail: String(detail) });

gate('assertCount', dom.cells === N_CASES && dom.cellNums.length === N_CASES,
  `页面断言格 ${dom.cells} / 有编号格 ${dom.cellNums.length} vs 源码 N_CASES=${N_CASES}`);

gate('assertNumbersContiguous', dom.cellNums.every((v, i) => v === i + 1) &&
  assignIdx.every((v, i) => v === i + 1) && assignIdx.length === N_CASES,
  `页面编号 1..${dom.cellNums[dom.cellNums.length - 1]} 无空洞;源码 aResult 赋值 ${assignIdx.length} 条同样无空洞`);

/* 四类计数之和必须等于 77 —— 分类错漏会在这里被抓。
   注:首版用 /(?:纯|界|拍|集)\s+(\d+)/g 取前 4 个,会误命中图例里的「与 Python 对拍 5 项」,
   算出 112 而误报页面错。改为锚定那一行完整句式,不靠"取前几个"。 */
const sumLine = dom.text.match(/合计\s*(\d+)\s*项\s*=\s*纯\s*(\d+)\s*\/\s*界\s*(\d+)\s*\/\s*拍\s*(\d+)\s*\/\s*集\s*(\d+)/);
const typeSum = sumLine ? Number(sumLine[2]) + Number(sumLine[3]) + Number(sumLine[4]) + Number(sumLine[5]) : null;
gate('typeSumEqualsTotal', sumLine && typeSum === N_CASES && Number(sumLine[1]) === N_CASES,
  sumLine ? `四类 ${sumLine[2]}+${sumLine[3]}+${sumLine[4]}+${sumLine[5]}=${typeSum},自称合计 ${sumLine[1]},N_CASES ${N_CASES}`
    : '页面上找不到「合计 N 项 = 纯 x / 界 x / 拍 x / 集 x」这一行');

gate('objCount', dom.objChips === mapRows.length && mapRows.length === 48,
  `页面对象芯片 ${dom.objChips} vs sync_st.py MAP ${mapRows.length} 条(应为 48)`);

const mapNames = new Set(mapRows.map(r => r.name));
const strayObj = dom.objNames.filter(n => !mapNames.has(n));
gate('objNamesAllInMap', strayObj.length === 0,
  strayObj.length ? `页面上有 MAP 里没有的对象:${strayObj.join(', ')}` : '48 个对象名全部在 MAP 中');

gate('syncedMatchesMap', syncedCount === mapRows.length,
  `0717 日志 SYNCED ${syncedCount} 条 vs MAP ${mapRows.length} 条`);

gate('onlineReadback', iPassed === N_CASES && iFailed === 0 && dom.text.includes(`INT#${N_CASES}`),
  `0717 读回 iPassed=${iPassed}/iFailed=${iFailed};页面含 INT#${N_CASES}`);

gate('totalLines', dom.text.includes(String(totalLines)),
  `wc -l plc/*.st = ${totalLines};页面${dom.text.includes(String(totalLines)) ? '含' : '不含'}该数`);

gate('goldenVectors', cbExpt && tobExpt && dom.text.includes(cbExpt) && dom.text.includes(tobExpt),
  `CB_EXPT=${cbExpt} / TOB_EXPT=${tobExpt},两者均需在页面上`);

/* 含 * 的是 glob(如 wc -l plc/*.st),不是实体路径:改判"该 glob 至少能展开出一个文件",
   否则一条写错的 glob 也能蒙混过关。 */
const globOf = (p) => {
  const dir = p.replace(/\\/g, '/').replace(/\/[^/]*$/, '');
  const pat = new RegExp('^' + p.replace(/\\/g, '/').split('/').pop().replace(/[.+^${}()|[\]]/g, '\\$&').replace(/\*/g, '.*') + '$');
  try { return readdirSync(join(PROJECT_ROOT, dir)).filter(f => pat.test(f)); } catch { return []; }
};
const badPaths = dom.paths.filter(p => p.includes('*')
  ? globOf(p).length === 0
  : !existsSync(join(PROJECT_ROOT, p.replace(/\\/g, '/'))));
const globs = dom.paths.filter(p => p.includes('*'));
gate('citedFilesExist', badPaths.length === 0,
  badPaths.length ? `页面引用但磁盘查无:${badPaths.join(' | ')}`
    : `${dom.paths.length} 条引用全部落地(其中 ${globs.length} 条是 glob,已验能展开:${globs.map(g => g + '→' + globOf(g).length + ' 个').join(', ') || '无'})`);

gate('shotSlotsMarked', dom.shotSlots >= 3, `截图占位 ${dom.shotSlots} 个(重拍后应逐个替换)`);

gate('sectionsSequential', dom.sections.join(',') === dom.sections.map((_, i) => String(i + 1).padStart(2, '0')).join(','),
  `节序号 ${dom.sections.join('/')}`);

gate('topbarMatchesSiblings', dom.barH === '48px' && dom.barBorder === '3px rgb(255, 0, 15)',
  `顶栏 ${dom.barH} + ${dom.barBorder}(应 48px + 3px rgb(255, 0, 15),与 01/02/03 一致)`);

gate('noSerif', dom.serif === 0, `衬线元素 ${dom.serif} 个`);
gate('noHorizontalScroll', dom.realScrollX === 0, `实际横滚 ${dom.realScrollX}px`);
gate('noPageError', pageErrors.length === 0, pageErrors.join(' | ') || '无');

/* ---------- 出报告 ---------- */
await page.screenshot({ path: join(OUT, 'ab04_full.png'), fullPage: true });
await browser.close();
server.close();

const passed = gates.filter(g => g.pass).length;
gates.forEach(g => console.log(`${g.pass ? 'PASS' : 'FAIL'} ${g.name}: ${g.detail}`));
writeFileSync(join(OUT, 'qa_report.json'), JSON.stringify({ page: PAGE, passed, total: gates.length, gates }, null, 1), 'utf8');
console.log(`\n${passed === gates.length ? 'PASS' : 'FAIL'} ${passed}/${gates.length}; ${join(OUT, 'qa_report.json')}`);
process.exit(passed === gates.length ? 0 : 1);
