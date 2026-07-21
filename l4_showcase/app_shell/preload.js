/* app_shell/preload.js
   contextIsolation:true 下渲染进程与主进程之间唯一的桥。只暴露两个函数(W3b 规格 §6):
     - openMaterial(key): 请求主进程用系统默认程序打开 materials.config.json 里 key 对应的路径。
     - getVersions(): 读 process.versions,给关于窗口展示 Electron/Chrome/Node 版本。
   sandbox:true 下 preload 脚本仍能拿到 process.versions(Electron 白名单属性,文档明确保留),
   不需要 nodeIntegration、不需要放宽 sandbox。 */
'use strict';

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('shellAPI', {
  openMaterial: (key) => ipcRenderer.invoke('open-material', key),
  getVersions: () => ({
    electron: process.versions.electron,
    chrome: process.versions.chrome,
    node: process.versions.node
  })
});
