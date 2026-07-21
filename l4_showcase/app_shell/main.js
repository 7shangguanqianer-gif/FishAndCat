/* 智储优控 L4 展示站 · Electron 桌面壳(W3b 批次:融合导航壳)
   在 W2 PoC(main.js 双模式验证)基础上转正:壳统一加载 app_shell/shell.html
   (左 48px 深色图标侧栏 + 右内容 iframe),不再直接把顶层窗口指向某张场景页。
   加载模式沿用 PoC 的 SHELL_MODE 开关,但默认值改为 http(0720 桌面化调研结论:
   docs/桌面化调研与壳定案_0720.md——http 内置静态服务消除 file:// 协议差异,是选定路径):
     - SHELL_MODE=http(默认):主进程内起 node http 静态服务(root=l4_showcase),
       win.loadURL 指向 http://127.0.0.1:PORT/app_shell/shell.html。
     - SHELL_MODE=file:        win.loadFile 直开 app_shell/shell.html(file:// 协议,
       仅作调试/对照保留,W3b 验收不覆盖此路径)。
   端口默认由 OS 随机分配(listen(0,...));SHELL_HTTP_PORT 环境变量可强制固定端口,
   仅供 verify 脚本做「同源跨进程重启」的 localStorage 清理验证用,不影响正常使用。 */

const { app, BrowserWindow, session, ipcMain, shell } = require('electron');
const path = require('node:path');
const http = require('node:http');
const fs = require('node:fs');

const MODE = process.env.SHELL_MODE === 'file' ? 'file' : 'http';
const APP_DIR = __dirname;                                   // F:\abb_wh_work\l4_showcase\app_shell
const SHOWCASE_ROOT = path.resolve(APP_DIR, '..');            // F:\abb_wh_work\l4_showcase(静态服务根)
const PROJECT_ROOT = path.resolve(SHOWCASE_ROOT, '..');       // F:\abb_wh_work(materials.config.json 路径解析根)
const ENTRY_RELATIVE = path.join('app_shell', 'shell.html');  // 相对 SHOWCASE_ROOT

/* MIME 表在 W2 PoC 四种类型基础上加 .png(启动页缩略图,app_shell/assets/*.png)。
   与 tools/capture_s3_layout_a_qa.mjs:42 的表同源扩展,不引入未用到的类型。
   0721 素材路由批次补 .jpg/.jpeg/.mp4(03 页 l2_factoryio 实拍素材与全链视频)。 */
const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.mp4': 'video/mp4'
};

let staticServer = null;

function startStaticServer() {
  const requestedPort = process.env.SHELL_HTTP_PORT ? Number(process.env.SHELL_HTTP_PORT) : 0;
  return new Promise((resolvePort, reject) => {
    staticServer = http.createServer((request, response) => {
      try {
        const pathname = decodeURIComponent(new URL(request.url, 'http://127.0.0.1').pathname).replace(/^\/+/, '');
        if (pathname === 'favicon.ico') { response.writeHead(204); response.end(); return; }
        /* 0721 素材白名单路由(用户批准):03 页素材 ../../l2_factoryio/* 经浏览器归一化到
           域根后越出 SHOWCASE_ROOT,旧闸一律 404。仅放行 l2_factoryio/ 前缀改按 PROJECT_ROOT
           解析,其余路径仍锁 SHOWCASE_ROOT;两路各自保留前缀闸防目录穿越。
           mp4 不做 Range 分片(438KB 全量返回,Chromium 可播;若后续大视频需 seek 再补)。 */
        const isMaterialPath = pathname.startsWith('l2_factoryio/');
        const rootDir = isMaterialPath ? PROJECT_ROOT : SHOWCASE_ROOT;
        const guardPrefix = isMaterialPath
          ? path.join(PROJECT_ROOT, 'l2_factoryio') + path.sep
          : SHOWCASE_ROOT + path.sep;
        const target = path.resolve(rootDir, pathname || ENTRY_RELATIVE);
        if (!target.startsWith(guardPrefix) || !fs.existsSync(target) || !fs.statSync(target).isFile()) {
          response.writeHead(404); response.end('not found'); return;
        }
        response.writeHead(200, {
          'content-type': MIME[path.extname(target)] || 'application/octet-stream',
          'cache-control': 'no-store'
        });
        response.end(fs.readFileSync(target));
      } catch (error) {
        response.writeHead(500); response.end(String((error && error.message) || error));
      }
    });
    staticServer.on('error', reject);
    staticServer.listen(requestedPort, '127.0.0.1', () => resolvePort(staticServer.address().port));
  });
}

/* ---------- 提交材料 ipc:主进程读 materials.config.json,校验后 shell.openPath ----------
   渲染侧(preload.js 暴露的 shellAPI.openMaterial)只传 key,真实文件系统路径与存在性校验
   全部留在主进程,contextIsolation 下渲染进程不直接碰 fs。 */
function loadMaterialsConfig() {
  const configPath = path.join(APP_DIR, 'materials.config.json');
  const raw = fs.readFileSync(configPath, 'utf8');
  return JSON.parse(raw);
}

ipcMain.handle('open-material', async (_event, key) => {
  try {
    const config = loadMaterialsConfig();
    const entry = config && config[key];
    if (!entry || typeof entry.path !== 'string') {
      return { ok: false, reason: 'unknown-key' };
    }
    if (entry.todo) {
      return { ok: false, reason: 'todo' };
    }
    const target = path.resolve(PROJECT_ROOT, entry.path);
    if (target !== PROJECT_ROOT && !target.startsWith(PROJECT_ROOT + path.sep)) {
      return { ok: false, reason: 'out-of-root' };
    }
    if (!fs.existsSync(target)) {
      return { ok: false, reason: 'not-found', path: target };
    }
    const openError = await shell.openPath(target);
    if (openError) {
      return { ok: false, reason: 'open-failed', detail: openError };
    }
    return { ok: true, path: target };
  } catch (error) {
    return { ok: false, reason: 'exception', detail: String((error && error.message) || error) };
  }
});

let win = null;

async function createWindow() {
  win = new BrowserWindow({
    useContentSize: true,
    width: 1600,
    height: 900,
    minWidth: 1280,
    minHeight: 800,
    autoHideMenuBar: true,
    show: false,
    webPreferences: {
      contextIsolation: true,
      sandbox: true,
      preload: path.join(APP_DIR, 'preload.js')
    }
  });

  win.once('ready-to-show', () => win.show());

  /* F11 = 壳级全屏切换(before-input-event 捕获,而非 globalShortcut——只在本窗口有焦点时生效,
     不劫持系统级 F11)。全屏只改变原生窗口边界,侧栏是页面内 flex 布局的一部分,天然随内容保留。 */
  win.webContents.on('before-input-event', (event, input) => {
    if (input.type === 'keyDown' && (input.key === 'F11' || input.code === 'F11')) {
      win.setFullScreen(!win.isFullScreen());
      event.preventDefault();
      console.log('[shell-fullscreen] F11 -> isFullScreen=' + win.isFullScreen());
    }
  });

  let httpPort = null;
  if (MODE === 'http') {
    httpPort = await startStaticServer();
    const encodedPath = ENTRY_RELATIVE.split(path.sep).map(encodeURIComponent).join('/');
    const url = `http://127.0.0.1:${httpPort}/${encodedPath}`;
    await win.loadURL(url);
  } else {
    await win.loadFile(path.join(APP_DIR, 'shell.html'));
  }

  /* 供外部 verify 脚本抓取的一行 JSON 信息(poc_verify.js / verify_w3b.js 解析 stdout)。 */
  console.log('[shell-info] ' + JSON.stringify({
    mode: MODE,
    httpPort,
    showcaseRoot: SHOWCASE_ROOT,
    projectRoot: PROJECT_ROOT,
    userData: app.getPath('userData'),
    electronVersion: process.versions.electron,
    chromeVersion: process.versions.chrome
  }));
}

app.whenReady().then(async () => {
  /* 每次启动回默认:清一次 localStorage,运行中切页(sidebar/iframe 导航)不再重复触发——
     本回调只在 app 生命周期内跑一次。 */
  await session.defaultSession.clearStorageData({ storages: ['localstorage'] });
  await createWindow();
}).catch(error => {
  console.error('[shell-error] createWindow failed: ' + ((error && error.stack) || error));
  app.exit(1);
});

app.on('window-all-closed', () => {
  if (staticServer) { try { staticServer.close(); } catch { /* noop */ } }
  if (process.platform !== 'darwin') app.quit();
});
