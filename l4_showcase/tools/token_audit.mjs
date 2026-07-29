/* 设计 token 实况盘点:把五个页面里真正用到的字号/色值/间距/圆角/字重全数出来。
   只读,不改任何文件。目的是把「凌乱」从感觉变成可数的事实。 */
import { readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
const HERE = dirname(fileURLToPath(import.meta.url));
const SHOWCASE = resolve(HERE, '..');
const SRC = join(SHOWCASE, 'src');
const PAGES = {
  '00 导览':     join(SRC, '00_导览.html'),
  '01 连续填仓': join(SRC, '01_连续填仓.html'),
  '02 入出闭环': join(SRC, '02_入出闭环.html'),
  '03 FIO证据':  join(SRC, '03_FIO物理证据.html'),
  '04 AB工程':   join(SRC, '04_AB工程.html'),
  '壳 shell':    join(SHOWCASE, 'app_shell', 'shell.html'),
};

/* 只看 <style> 段与内联 style,避免把 JS 里的字符串误当样式 */
const styleText = (html) => {
  const blocks = [...html.matchAll(/<style[^>]*>([\s\S]*?)<\/style>/gi)].map(m => m[1]);
  const inline = [...html.matchAll(/\sstyle="([^"]*)"/gi)].map(m => m[1]);
  return blocks.join('\n') + '\n' + inline.join(';\n');
};

const collect = (css, re, norm = x => x) => {
  const bag = new Map();
  for (const m of css.matchAll(re)) {
    const v = norm(m[1]);
    if (v == null) continue;
    bag.set(v, (bag.get(v) || 0) + 1);
  }
  return bag;
};

/* 色值统一成小写 hex;三位补成六位,便于发现"同色不同写法" */
const normHex = (h) => {
  h = h.toLowerCase();
  if (h.length === 4) h = '#' + h[1] + h[1] + h[2] + h[2] + h[3] + h[3];
  return h.length === 9 ? h.slice(0, 7) + '(+alpha)' : h;
};

const report = {};
for (const [name, path] of Object.entries(PAGES)) {
  let html;
  try { html = readFileSync(path, 'utf8'); } catch { console.log(`跳过(读不到):${name}`); continue; }
  const css = styleText(html);
  report[name] = {
    字号: collect(css, /font-size:\s*([\d.]+)px/gi),
    字号简写: collect(css, /font:\s*(?:\d+\s+)?([\d.]+)px/gi),
    字重: collect(css, /font-weight:\s*(\d{3}|bold|normal)/gi),
    色值: collect(css, /(#[0-9a-fA-F]{3,8})\b/g, normHex),
    圆角: collect(css, /border-radius:\s*([\d.]+)px/gi),
    内边距: collect(css, /padding:\s*([\d.]+)px/gi),
    间隙: collect(css, /gap:\s*([\d.]+)px/gi),
  };
}

const merge = (key) => {
  const all = new Map();
  for (const r of Object.values(report))
    for (const [v, n] of r[key]) all.set(v, (all.get(v) || 0) + n);
  return all;
};

const line = (s) => console.log(s);
line('页面                字号种类  字重  色值  圆角  padding  gap');
for (const [name, r] of Object.entries(report)) {
  const fs = new Set([...r.字号.keys(), ...r.字号简写.keys()]);
  line(`${name.padEnd(16)}  ${String(fs.size).padStart(6)}  ${String(r.字重.size).padStart(4)}  ` +
    `${String(r.色值.size).padStart(4)}  ${String(r.圆角.size).padStart(4)}  ` +
    `${String(r.内边距.size).padStart(7)}  ${String(r.间隙.size).padStart(3)}`);
}

const sortNum = (m) => [...m.keys()].map(Number).filter(n => !isNaN(n)).sort((a, b) => a - b);
const fsAll = new Map();
for (const r of Object.values(report)) {
  for (const [v, n] of r.字号) fsAll.set(v, (fsAll.get(v) || 0) + n);
  for (const [v, n] of r.字号简写) fsAll.set(v, (fsAll.get(v) || 0) + n);
}
line('\n===== 全库字号(升序,括号=出现次数) =====');
line(sortNum(fsAll).map(v => `${v}px(${fsAll.get(String(v)) ?? fsAll.get(v)})`).join('  '));
line(`字号种类合计:${fsAll.size}`);

const rad = merge('圆角'), pad = merge('内边距'), gap = merge('间隙'), col = merge('色值'), wt = merge('字重');
line('\n===== 圆角 ====='); line(sortNum(rad).map(v => `${v}px`).join('  ') + `   共 ${rad.size} 种`);
line('\n===== padding 单值 ====='); line(sortNum(pad).map(v => `${v}px`).join('  ') + `   共 ${pad.size} 种`);
line('\n===== gap ====='); line(sortNum(gap).map(v => `${v}px`).join('  ') + `   共 ${gap.size} 种`);
line('\n===== 字重 ====='); line([...wt.keys()].sort().join('  ') + `   共 ${wt.size} 种`);
line(`\n===== 色值种类合计:${col.size} =====`);
line('出现 ≥3 次的:');
line([...col.entries()].filter(([, n]) => n >= 3).sort((a, b) => b[1] - a[1])
  .map(([v, n]) => `${v}×${n}`).join('  '));
line('\n只出现 1 次的色值(最可能是随手写的):');
const once = [...col.entries()].filter(([, n]) => n === 1).map(([v]) => v);
line(once.join('  '));
line(`一次性色值 ${once.length} 个 / 共 ${col.size} 个 = ${(once.length / col.size * 100).toFixed(0)}%`);

/* 4px 基准符合度 */
const off4 = [...new Set([...sortNum(pad), ...sortNum(gap)])].filter(v => v % 4 !== 0);
line(`\n===== 间距不在 4px 基准上的值 =====\n${off4.join('  ')}   (共 ${off4.length} 个)`);

writeFileSync(join(SHOWCASE, 'out', 'token_audit.json'),
  JSON.stringify(Object.fromEntries(Object.entries(report).map(([k, r]) =>
    [k, Object.fromEntries(Object.entries(r).map(([kk, m]) => [kk, Object.fromEntries(m)]))])), null, 1), 'utf8');
line('\nJSON -> scratchpad/token_audit.json');
