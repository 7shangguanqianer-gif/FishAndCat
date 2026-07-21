/* 0721 素材白名单路由验证:起壳(固定端口)→ 四项断言 → 退出。
   ①素材 png 200+image/png ②素材 mp4 200+video/mp4 ③目录穿越 404(闸有效)④原有 shell.html 200 不回归。
   运行:node verify_material_route.mjs(cwd=app_shell) */
import { spawn } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const APP_DIR = path.dirname(fileURLToPath(import.meta.url));
const PORT = 18321;
const BASE = `http://127.0.0.1:${PORT}`;

const CASES = [
  { name: 'material-png', url: '/l2_factoryio/media/g4_evidence_0713/H5_9of9_终验_三格齐放第三轮.png', wantStatus: 200, wantType: 'image/png' },
  { name: 'material-mp4', url: '/l2_factoryio/media/F3_素材_cell30全链_0713/F3_cell30_全链素材.mp4', wantStatus: 200, wantType: 'video/mp4' },
  { name: 'traversal-blocked', url: '/l2_factoryio/../docs/命名总表_0720.md', wantStatus: 404, wantType: null },
  { name: 'shell-no-regress', url: '/app_shell/shell.html', wantStatus: 200, wantType: 'text/html; charset=utf-8' }
];

const electronBin = path.join(APP_DIR, 'node_modules', '.bin', process.platform === 'win32' ? 'electron.cmd' : 'electron');
const child = spawn(electronBin, ['.'], {
  cwd: APP_DIR, shell: process.platform === 'win32',
  env: { ...process.env, SHELL_HTTP_PORT: String(PORT) },
  stdio: 'ignore'
});

async function waitPort(deadlineMs) {
  const t0 = Date.now();
  while (Date.now() - t0 < deadlineMs) {
    try { await fetch(`${BASE}/app_shell/shell.html`, { method: 'HEAD' }); return; }
    catch { await new Promise(resolve => setTimeout(resolve, 300)); }
  }
  throw new Error(`port ${PORT} not ready in ${deadlineMs}ms`);
}

let failed = 0;
try {
  await waitPort(20000);
  for (const c of CASES) {
    const res = await fetch(BASE + encodeURI(c.url));
    const type = res.headers.get('content-type');
    const okStatus = res.status === c.wantStatus;
    const okType = c.wantType === null || type === c.wantType;
    const ok = okStatus && okType;
    if (!ok) failed += 1;
    console.log(`${ok ? 'PASS' : 'FAIL'} ${c.name}: status=${res.status}(want ${c.wantStatus}) type=${type}(want ${c.wantType ?? 'any'})`);
  }
} catch (error) {
  failed += 1;
  console.error('FAIL harness:', error.message);
} finally {
  child.kill('SIGTERM');
  if (process.platform === 'win32') spawn('taskkill', ['/pid', String(child.pid), '/T', '/F'], { shell: true });
}
console.log(failed === 0 ? `ALL PASS ${CASES.length}/${CASES.length}` : `FAILED ${failed}/${CASES.length}`);
process.exit(failed === 0 ? 0 : 1);
