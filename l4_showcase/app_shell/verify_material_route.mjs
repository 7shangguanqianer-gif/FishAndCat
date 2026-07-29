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
  /* 0729 修退出期竞态。原实现是
       spawn('taskkill', [...], { shell: true });
     spawn 出去**不等它结束**,下一行就 process.exit() —— taskkill 的 libuv async handle
     还在初始化就被连根拆掉,于是炸在
       Assertion failed: !(handle->flags & UV_HANDLE_CLOSING), file src\win\async.c, line 94
     退出码变成 127。四项断言其实全过,是纯粹的收尾竞态,但对任何看退出码的调用方
     (CI、批量跑门的脚本)都表现为"这套门失败了"。
     管道方式下 6/6 必现,裸终端偶发为 0——所以用 `| tail -1` 看结果时会完全漏掉它。
     改法:等 taskkill 真正结束再退;并去掉 shell:true(taskkill 是真实 exe,不需要 shell 包一层,
     顺带消掉 DEP0190 那条警告)。 */
  if (process.platform === 'win32') {
    await new Promise(resolve => {
      const killer = spawn('taskkill', ['/pid', String(child.pid), '/T', '/F'], { stdio: 'ignore' });
      killer.on('close', resolve);
      killer.on('error', resolve);   // taskkill 不在 PATH 也不该把整套门判失败
    });
  }
}
console.log(failed === 0 ? `ALL PASS ${CASES.length}/${CASES.length}` : `FAILED ${failed}/${CASES.length}`);
/* 用 exitCode 而非 process.exit():让事件循环自然收尾,不再抢在 handle 关闭前拆进程 */
process.exitCode = failed === 0 ? 0 : 1;
