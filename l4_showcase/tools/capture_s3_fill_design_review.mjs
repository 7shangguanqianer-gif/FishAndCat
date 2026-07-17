import fs from "node:fs";
import path from "node:path";
import {createRequire} from "node:module";
import {fileURLToPath, pathToFileURL} from "node:url";

const require = createRequire(import.meta.url);
const {chromium} = require("playwright");
const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, "..", "..");
const html = path.join(ROOT, "l4_showcase", "design_reviews", "0716_S3_fill_方案评审.html");
const out = path.join(ROOT, "l4_showcase", "design_reviews", "screenshots_0716");
fs.mkdirSync(out, {recursive: true});

const executablePath = process.env.CHROME_PATH
  || "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const browser = await chromium.launch({headless: true, executablePath});
const page = await browser.newPage({viewport: {width: 1600, height: 900}, deviceScaleFactor: 1});
const consoleErrors = [];
const pageErrors = [];
page.on("console", message => { if (message.type() === "error") consoleErrors.push(message.text()); });
page.on("pageerror", error => pageErrors.push(String(error)));

const results = [];
for (const id of ["v1", "v2", "v3", "vc"]) {
  await page.goto(`${pathToFileURL(html).href}?v=${id}`, {waitUntil: "load"});
  await page.waitForTimeout(120);
  const audit = await page.evaluate(expected => {
    const active = [...document.querySelectorAll(".view.active")];
    const root = document.documentElement;
    const visiblePanels = [...document.querySelectorAll(".view.active .panel,.view.active .stage")];
    return {
      expected,
      activeIds: active.map(item => item.id),
      viewport: [innerWidth, innerHeight],
      scrollWidth: root.scrollWidth,
      scrollHeight: root.scrollHeight,
      horizontalOverflow: root.scrollWidth > innerWidth + 1,
      verticalOverflow: root.scrollHeight > innerHeight + 1,
      panelsOutsideViewport: visiblePanels.filter(item => {
        const box = item.getBoundingClientRect();
        return box.left < -1 || box.top < -1 || box.right > innerWidth + 1 || box.bottom > innerHeight + 1;
      }).length,
      mapCells: document.querySelectorAll(".view.active [data-grid] .cell").length,
      rackCells: document.querySelectorAll(".view.active .rack .cell").length,
      targetCells: document.querySelectorAll(".view.active .cell.target").length,
      visibleText: active[0]?.innerText.length || 0,
    };
  }, id);
  const screenshot = path.join(out, `${id}_1600x900.png`);
  await page.screenshot({path: screenshot, fullPage: false});
  audit.screenshot = screenshot;
  audit.pass = audit.activeIds.length === 1 && audit.activeIds[0] === id
    && !audit.horizontalOverflow && !audit.verticalOverflow
    && audit.panelsOutsideViewport === 0 && audit.targetCells > 0
    && audit.visibleText > 100;
  results.push(audit);
}
await browser.close();

const report = {
  schema: "s3-fill-design-review-capture-v1",
  html,
  viewport: [1600, 900],
  consoleErrors,
  pageErrors,
  results,
  pass: !consoleErrors.length && !pageErrors.length && results.every(item => item.pass),
};
const reportPath = path.join(out, "capture_qa.json");
fs.writeFileSync(reportPath, JSON.stringify(report, null, 2) + "\n", "utf8");
console.log(JSON.stringify({pass: report.pass, report: reportPath, results}, null, 2));
if (!report.pass) process.exitCode = 1;
