import fs from "node:fs";
import path from "node:path";
import {createRequire} from "node:module";
import {fileURLToPath, pathToFileURL} from "node:url";

const require = createRequire(import.meta.url);
const {chromium} = require("playwright");
const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, "..", "..");
const candidates = [
  ["1_left", "样张_S3_母版增量方案_1_顶部横排.html", "left"],
  ["2_map", "样张_S3_母版增量方案_2_地图侧列.html", "map"],
  ["3_insight", "样张_S3_母版增量方案_3_证据卡组.html", "insight"],
];
const out = path.join(ROOT, "l4_showcase", "design_reviews", "screenshots_0716_incremental");
fs.mkdirSync(out, {recursive: true});

const executablePath = process.env.CHROME_PATH
  || "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const browser = await chromium.launch({
  headless: true,
  executablePath,
  args: ["--allow-file-access-from-files"],
});
const results = [];
for (const [id, filename, layout] of candidates) {
  const page = await browser.newPage({viewport: {width: 1600, height: 900}, deviceScaleFactor: 1});
  const consoleErrors = [];
  const pageErrors = [];
  page.on("console", message => { if (message.type() === "error") consoleErrors.push(message.text()); });
  page.on("pageerror", error => pageErrors.push(String(error)));
  const html = path.join(ROOT, "l4_showcase", "src", filename);
  await page.goto(pathToFileURL(html).href, {waitUntil: "load"});
  await page.waitForSelector("#gl canvas", {state: "visible", timeout: 15000});
  await page.waitForTimeout(2500);
  const audit = await page.evaluate(expectedLayout => {
    const root = document.documentElement;
    const byId = id => document.getElementById(id);
    const box = id => {
      const node = byId(id);
      if (!node) return null;
      const rect = node.getBoundingClientRect();
      return {left: rect.left, top: rect.top, right: rect.right, bottom: rect.bottom, width: rect.width, height: rect.height};
    };
    const required = [
      "strategySelect", "tierSelect", "profileSelect", "slotMap", "phaseRail",
      "sceneDock", "resetCamera", "playbackSpeed", "targetBeacon", "gl",
    ];
    const controls = required.reduce((acc, id) => ({...acc, [id]: Boolean(byId(id))}), {});
    const canvas = document.querySelector("#gl canvas");
    const bookmarkButtons = [...document.querySelectorAll("#fillBookmarks button")];
    const gl = box("gl"), rail = box("workHud"), dock = box("sceneDock"), bookmarks = box("fillBookmarks");
    const offscreen = [gl, rail, dock, bookmarks].filter(Boolean).some(rect => (
      rect.left < -1 || rect.top < -1 || rect.right > innerWidth + 1 || rect.bottom > innerHeight + 1
    ));
    return {
      layout: root.dataset.incrementalLayout,
      viewport: [innerWidth, innerHeight],
      scroll: [root.scrollWidth, root.scrollHeight],
      horizontalOverflow: root.scrollWidth > innerWidth + 1,
      verticalOverflow: root.scrollHeight > innerHeight + 1,
      offscreen,
      controls,
      canvas: canvas ? {width: canvas.clientWidth, height: canvas.clientHeight} : null,
      phaseCount: document.querySelectorAll("#phaseSegments .phaseSeg").length,
      bookmarkCount: bookmarkButtons.length,
      bookmarkLabels: bookmarkButtons.map(item => item.innerText.trim()),
      linkedChip: byId("linkedEvidenceChip")?.textContent || null,
      boxes: {gl, rail, dock, bookmarks},
      expectedLayout,
    };
  }, layout);
  const screenshot = path.join(out, `${id}_1600x900.png`);
  await page.screenshot({path: screenshot, fullPage: false});
  audit.screenshot = screenshot;
  audit.consoleErrors = consoleErrors;
  audit.pageErrors = pageErrors;
  audit.pass = audit.layout === layout
    && !audit.horizontalOverflow && !audit.verticalOverflow && !audit.offscreen
    && Object.values(audit.controls).every(Boolean)
    && audit.canvas?.width > 700 && audit.canvas?.height > 500
    && audit.phaseCount === 7 && audit.bookmarkCount === 6
    && audit.linkedChip === "D · 2D↔3D 同目标"
    && !consoleErrors.length && !pageErrors.length;
  results.push(audit);
  await page.close();
}
await browser.close();

const report = {
  schema: "s3-incremental-design-review-capture-v1",
  sourceRule: "full mature mother HTML plus review-only CSS/JS injection",
  viewport: [1600, 900],
  results,
  pass: results.every(item => item.pass),
};
const reportPath = path.join(out, "capture_qa.json");
fs.writeFileSync(reportPath, JSON.stringify(report, null, 2) + "\n", "utf8");
console.log(JSON.stringify({pass: report.pass, report: reportPath, results}, null, 2));
if (!report.pass) process.exitCode = 1;
