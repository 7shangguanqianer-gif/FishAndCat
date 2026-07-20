/* S3 mixed(02_入出闭环)方案A「进度轴驱动」交互层 · 步骤1 骨架版(0718 R2)
   仿 src/s3_layout_a_interactions.js;s3_ac_runtime.js / s3_trace_store.js / trace 数据零改动。
   本层只做:
     ① 作用域开关 document.documentElement.dataset.s3Layout = "A"
     ② 顶栏 DOM 搬运:railHead + runtimeControls 搬入静态 #topbarA
     ③ 入出周期轴节点(0/25/50/75/100)点击暂停到已验证快照(经 __S3_QA.seek;未就绪则占位忽略)
     ④ 节点快照浮层(按需披露)
     ⑤ 2D 货位图放大浮层(最小实现)
     ⑥ QA 自检钩子 __S3_MIXED_LAYOUT_A.audit()
   边界:步骤1 只求「A 壳能起来、不白屏」;四差异标记 / 取货实测块留步骤2/3。
   时序:runtime 于脚本加载时同步 bootstrap(),故本脚本运行时 railHead/runtimeControls/
        slotMapWrap/cycleAxisCount/__S3_QA 均已就绪;仍逐一存在性守护,保证 fail-open 不白屏。 */
(function (root) {
  "use strict";
  const doc = root.document;
  const byId = id => doc.getElementById(id);
  const viewport = byId("viewport");
  const workHud = byId("workHud");
  if (!viewport || !workHud) return;

  const CYCLES_TOTAL = 100;

  /* ---------- 1. 布局作用域 ---------- */
  doc.documentElement.dataset.s3Layout = "A";

  /* ---------- 2. 顶栏:railHead + runtimeControls 搬入静态 #topbarA ---------- */
  const topbar = byId("topbarA");
  const railHead = byId("railHead");
  const runtimeControls = byId("runtimeControls");
  if (topbar) {
    if (railHead) topbar.append(railHead);            /* railHead 由场景脚本创建并 prepend 到 workHud */
    /* 0719 功能批次 M3:PLC 分片可行性占位徽章——紧跟品牌(页面级口径徽章),在控件组之前 */
    const plcBadge = doc.createElement("span");
    plcBadge.id = "plcFeasBadge";
    plcBadge.textContent = "PLC 分片可行性 · 另页详述";
    plcBadge.title = "AC500 分片下装可行性另页详述;本页为 SIM 演示口径,不虚构 PLC 实测结论。";
    topbar.append(plcBadge);
    if (runtimeControls) {
      /* 0719d 结构重排(绿框):三个「label+select」融为一个情景配置单元;动作按钮分「播放/证据」两组。
         只包壳搬运,不动 id——runtime 已按 id 绑好监听,元素搬家监听随行。 */
      const scenarioGroup = doc.createElement("div");
      scenarioGroup.className = "scenarioGroup";
      scenarioGroup.setAttribute("aria-label", "情景配置：算法 · 拟真档 · 货物画像");
      runtimeControls.querySelectorAll(":scope > label").forEach(label => scenarioGroup.append(label));
      runtimeControls.prepend(scenarioGroup);
      const actions = byId("runtimeActions");
      if (actions) {
        const playSet = doc.createElement("span"); playSet.className = "btnSet";
        const proofSet = doc.createElement("span"); proofSet.className = "btnSet";
        ["pauseMotion", "replayTrace"].forEach(id => { const el = byId(id); if (el) playSet.append(el); });
        ["exp", "openEvidenceDock", "openComparisonLab"].forEach(id => { const el = byId(id); if (el) proofSet.append(el); });
        actions.prepend(playSet, proofSet);
      }
      topbar.append(runtimeControls);
    }
  }

  /* 0719 C2 组件公约:镜头与演示倍率 → 进度轴行尾(01 已如此,02 从 sceneDock 第三列搬来;
     样式在 s3_shell_v2.css 的 #cycleAxis #sceneTools 段,dock 腾出的列位留给取货实测块)。 */
  const cycleAxisHost = byId("cycleAxis");
  const sceneTools = byId("sceneTools");
  if (cycleAxisHost && sceneTools) cycleAxisHost.append(sceneTools);

  /* 0719 四分割(用户红框):货位热度图例从 3D 悬浮层集成进底 dock。本层运行时 opsEvidence
     尚未由 runtime 创建(trace 加载后才 append),故最终列序 = 当前作业|运动遥测|货位热度|存取对置 */
  const heatLegendEl = byId("heatLegend");
  const sceneDockEl = byId("sceneDock");
  if (heatLegendEl && sceneDockEl) sceneDockEl.append(heatLegendEl);

  /* ---------- 3. 共享浮层容器 ---------- */
  const nodePop = doc.createElement("div");
  nodePop.id = "cycleNodePop";
  nodePop.className = "s3aPop";
  nodePop.setAttribute("role", "tooltip");
  viewport.append(nodePop);

  function placePop(pop, anchor, prefer) {
    const vpRect = viewport.getBoundingClientRect();
    const rect = anchor.getBoundingClientRect();
    pop.classList.add("show");
    const popRect = pop.getBoundingClientRect();
    let left = rect.left - vpRect.left + rect.width / 2 - popRect.width / 2;
    left = Math.max(8, Math.min(left, vpRect.width - popRect.width - 8));
    let top = prefer === "below"
      ? rect.bottom - vpRect.top + 8
      : rect.top - vpRect.top - popRect.height - 8;
    if (top + popRect.height > vpRect.height - 8) top = rect.top - vpRect.top - popRect.height - 8;
    if (top < 8) top = rect.bottom - vpRect.top + 8;
    pop.style.left = `${Math.round(left)}px`;
    pop.style.top = `${Math.round(top)}px`;
  }

  /* ---------- 4. 入出周期轴:节点点击暂停到已验证快照 ---------- */
  const track = byId("cycleAxisTrack");
  const cycleFill = track ? track.querySelector(".cycleFill") : null;
  const nodeButtons = track ? Array.from(track.querySelectorAll("button[data-cycle]")) : [];

  function renderNodePop(button) {
    const cycle = Number(button.dataset.cycle);
    const label = button.dataset.axisLabel || String(cycle);
    const current = button.getAttribute("aria-current") === "true";
    nodePop.innerHTML =
      `<h4>周期节点 ${cycle} / ${CYCLES_TOTAL}${current ? " · 当前" : ""}</h4>` +
      `<table><tr><td>入出里程碑</td><td>${label}</td></tr></table>` +
      `<div class="note">点击圆点跳转并暂停到该周期的已验证快照 · SIM。存取双向的「入库完成 / 出库完成」语义细化留步骤 2/3。</div>`;
    placePop(nodePop, button, "below");
  }

  function seekToCycle(cycle) {
    /* 步骤1 占位:__S3_QA.seek 未就绪或参数越界时静默忽略,只保留视觉 aria-current 暂停态。 */
    if (!root.__S3_QA || typeof root.__S3_QA.seek !== "function") return;
    const cycleIndex = Math.max(0, Math.min(cycle, CYCLES_TOTAL - 1));
    try { root.__S3_QA.seek(cycleIndex, "LOAD_IN", 0.5); } catch (error) { /* seek 尚未就绪 */ }
  }

  let nodePopTimer = null;
  nodeButtons.forEach(button => {
    button.addEventListener("click", () => {
      nodeButtons.forEach(other => other.setAttribute("aria-current", other === button ? "true" : "false"));
      seekToCycle(Number(button.dataset.cycle));
      renderNodePop(button);
      /* 0719 修:点击后浮层 2.2s 自动收——原来无关闭触发(鼠标不动就一直挡视野,内容还会过时) */
      if (nodePopTimer) clearTimeout(nodePopTimer);
      nodePopTimer = setTimeout(() => nodePop.classList.remove("show"), 2200);
    });
    button.addEventListener("mouseenter", () => renderNodePop(button));
    button.addEventListener("focus", () => renderNodePop(button));
    button.addEventListener("mouseleave", () => nodePop.classList.remove("show"));
    button.addEventListener("blur", () => nodePop.classList.remove("show"));
  });

  /* 轴推进:监听 runtime 每帧直写的 #cycleAxisCount "N / 100"(0719:railFacts 已删,信号线从 factCycle 迁此;
     本层只读它更新 fill/axisDone,不回写,避免观察自触发)。 */
  const cycleCount = byId("cycleAxisCount");
  let lastCycle = -1;
  function syncAxis() {
    if (!cycleCount) return;
    const match = String(cycleCount.textContent || "").match(/(\d+)\s*\/\s*(\d+)/);
    if (!match) return;
    const done = Number(match[1]);
    if (done === lastCycle) return;
    lastCycle = done;
    if (cycleFill) cycleFill.style.width = `${(done / CYCLES_TOTAL * 100).toFixed(2)}%`;
    nodeButtons.forEach(button => button.classList.toggle("axisDone", Number(button.dataset.cycle) <= done));
  }
  if (cycleCount) {
    new MutationObserver(syncAxis).observe(cycleCount, { childList: true, characterData: true, subtree: true });
  }
  syncAxis();

  /* ---------- 5. 2D 货位图放大浮层(最小实现;DOM 搬运,canvas 由 runtime 自适应重画) ---------- */
  const mapWrap = byId("slotMapWrap");
  let overlay = null;
  if (mapWrap) {
    overlay = doc.createElement("div");
    overlay.id = "s3MapOverlay";
    overlay.innerHTML = '<div class="mapDock"><button type="button" class="mapDockClose" aria-label="关闭放大视图">×</button></div>';
    viewport.append(overlay);
    const mapDock = overlay.querySelector(".mapDock");
    const mapHome = { parent: mapWrap.parentElement, next: mapWrap.nextSibling };
    mapWrap.style.cursor = "zoom-in";
    const openMap = () => {
      if (overlay.classList.contains("open")) return;
      mapDock.append(mapWrap);
      overlay.classList.add("open");
      root.dispatchEvent(new Event("resize"));
    };
    const closeMap = () => {
      if (!overlay.classList.contains("open")) return;
      overlay.classList.remove("open");
      mapHome.parent.insertBefore(mapWrap, mapHome.next);
      root.dispatchEvent(new Event("resize"));
    };
    mapWrap.addEventListener("click", () => { if (!overlay.classList.contains("open")) openMap(); });
    overlay.addEventListener("click", event => {
      if (event.target === overlay || event.target.classList.contains("mapDockClose")) closeMap();
    });
    root.addEventListener("keydown", event => {
      if (event.key === "Escape") { closeMap(); nodePop.classList.remove("show"); }
    });
    root.__S3_MIXED_MAP = { openMap, closeMap };
  }

  /* ---------- 6. 布局搬运改变了 #gl 尺寸:触发 resize 让 renderer / 浮签重算 ---------- */
  root.dispatchEvent(new Event("resize"));

  /* ---------- 7. QA 自检钩子(步骤1 骨架断言) ---------- */
  root.__S3_MIXED_LAYOUT_A = Object.freeze({
    version: "s3-mixed-layout-a-interactions-v1-skeleton",
    audit() {
      return {
        layout: doc.documentElement.dataset.s3Layout,
        topbarPresent: Boolean(byId("topbarA")),
        railHeadInTopbar: Boolean(topbar && railHead && topbar.contains(railHead)),
        controlsInTopbar: Boolean(topbar && runtimeControls && topbar.contains(runtimeControls)),
        progressAxisPresent: Boolean(byId("progressAxisHost")),
        cycleNodeCount: nodeButtons.length,
        cycleNodes: nodeButtons.map(button => Number(button.dataset.cycle)),
        cycleFillWidth: cycleFill ? cycleFill.style.width : null,
        mapOverlayReady: Boolean(overlay)
      };
    },
    showNodePop(index) { if (nodeButtons[index]) { renderNodePop(nodeButtons[index]); return nodePop.getBoundingClientRect(); } return null; },
    hidePops() { nodePop.classList.remove("show"); }
  });
})(window);
