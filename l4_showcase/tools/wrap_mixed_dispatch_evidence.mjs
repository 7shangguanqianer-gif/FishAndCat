/* 把 evidence/s3_mixed_dispatch_2026_2055.json 包装成 window 全局 js(file:// 兼容,项目 script 注册惯例)。
   用法:node tools/wrap_mixed_dispatch_evidence.mjs  → 产出 out/s3_mixed_dispatch_sweep.js */
import { readFileSync, writeFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
const base = join(dirname(fileURLToPath(import.meta.url)), '..');
const src = join(base, 'evidence', 's3_mixed_dispatch_2026_2055.json');
const dst = join(base, 'out', 's3_mixed_dispatch_sweep.js');
const data = JSON.parse(readFileSync(src, 'utf8'));
if (data.schema !== 's3-mixed-dispatch-sweep-v1') throw new Error('schema 不符:' + data.schema);
writeFileSync(dst, 'window.S3_MIXED_DISPATCH_SWEEP=' + JSON.stringify(data) + ';\n');
console.log('OK ->', dst, '(seeds:', data.rows.length + ')');
