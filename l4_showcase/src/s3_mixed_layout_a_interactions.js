/* S3 mixed(02_入出闭环)方案A「进度轴驱动」交互层 · 步骤1 骨架版(0718 R2)
   仿 src/s3_layout_a_interactions.js;s3_ac_runtime.js / s3_trace_store.js / trace 数据零改动。
   本层只做:
     ① 作用域开关 document.documentElement.dataset.s3Layout = "A"
     ② 顶栏 DOM 搬运:railHead + runtimeControls 搬入静态 #topbarA
     ③ 入出周期轴节点(0/25/50/75/100)点击暂停到已验证快照(经 __S3_QA.seek;未就绪则占位忽略)
     ④ 节点快照浮层(按需披露)
     ⑤ 2D 货位图放大浮层(最小实现)
     ⑥ 折叠收纳:右栏/底 dock 整体收边 + 栏内五块单独折叠 + localStorage 持久化(W1-7)
     ⑦ QA 自检钩子 __S3_MIXED_LAYOUT_A.audit()
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

  /* 0720 版B 转正:作业周期进度轴从顶栏下的独立横条搬入右栏顶部(竖排空间换横排,3D 视野增大)。
     prepend 对已存在节点是移动不是复制,幂等安全;#progressAxisHost 的 order:-1(见 02 html 样式区)
     保证不论搬运时机都恒居 #workHud 首位。 */
  const progressAxisHost = byId("progressAxisHost");
  if (progressAxisHost && progressAxisHost.parentElement !== workHud) workHud.prepend(progressAxisHost);

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
      /* T5:三档分段按钮(#tierSegs,s3_ac_runtime.js 建在「拟真档」label 之后)是原生 <label> 的兄弟节点,
         不是 label 本身,不会被上面 :scope > label 的搬运捎带——显式接着挪到同一 label 后面,
         保证顶栏视觉顺序仍是「拟真档 [段1][段2][段3]」而不是被冲到货物画像后面。 */
      const tierSegsEl = byId("tierSegs");
      const tierLabelEl = byId("tierSelect") && byId("tierSelect").closest("label");
      if (tierSegsEl && tierLabelEl) tierLabelEl.after(tierSegsEl);
      const actions = byId("runtimeActions");
      if (actions) {
        const playSet = doc.createElement("span"); playSet.className = "btnSet";
        const proofSet = doc.createElement("span"); proofSet.className = "btnSet";
        ["pauseMotion", "replayTrace"].forEach(id => { const el = byId(id); if (el) playSet.append(el); });
        /* 0720 版B 转正:openEvidenceCenter 是唯一可见证据入口;exp/openEvidenceDock/openComparisonLab
           三个旧按钮 CSS 已隐藏(02 html 样式区),DOM 与监听原样保留、仍随组搬运,不单独摘出 */
        ["exp", "openEvidenceCenter", "openEvidenceDock", "openComparisonLab"].forEach(id => { const el = byId(id); if (el) proofSet.append(el); });
        actions.prepend(playSet, proofSet);
      }
      topbar.append(runtimeControls);
    }
  }

  /* 0720 版B 转正:进度轴迁入右栏后不再有「行尾」可挂;镜头与演示倍率改安置到 3D 区右下角
     悬浮小卡(直接挂 #viewport,position:absolute 由 02 html 样式区的 #sceneTools 规则给出;
     s3_shell_v2.css 的 #cycleAxis #sceneTools 段随之退役并已清)。 */
  const sceneTools = byId("sceneTools");
  if (sceneTools && sceneTools.parentElement !== viewport) viewport.append(sceneTools);

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

  /* ---------- 6. 折叠收纳(W1-7,拍板「整栏收边+逐块折叠+持久化」) ----------
     右栏(#workHud)与底 dock(#sceneDock)两大版块整体收成 26px 边缘细条;
     栏内五块(算法决策/2D 货位图/批次KPI/入库排队/出入库耗时分解)块头可单独折叠。
     机制:收展只改 --rail-w / --scene-dock-h 两个既有 CSS 变量的值,#gl/#sceneDock/#heatLegend/
     #sceneTools 等一切引用它们的规则自动跟随(样式见 02 html style 区 W1-7 节)。
     持久化 localStorage s3_collapse_v1 = {rail,dock,blocks:{id:bool}};缺省/解析失败=全展开,
     保证 QA 脚本首次加载零感知(默认态永远是展开态跑起来的)。
     块头点击用事件代理(捕获阶段)挂在 #viewport 上(#workHud 与 #sceneDock 的共同祖先——
     栏内四块 + dock 内 opsEvidence 一并覆盖),而不是直接挂在 .dHead/.mapHead 等元素——
     decisionWrap/traceStats 等的内部子节点会被 renderDecision/renderTraceStats 的
     replaceChildren() 整体换新,直接挂的监听会被一起冲掉;代理监听挂在稳定的祖先上,
     每次点击时才现查 event.target,天然不受重渲染影响。用捕获阶段是因为 #slotMapWrap 自身
     已有「点击放大 2D 图」的冒泡监听(第 5 节),块头点击若走冒泡会先触发放大再触发折叠,
     两个手势打架;捕获阶段能抢在放大监听之前 stopPropagation 拦下块头点击。 */
  const COLLAPSE_KEY = "s3_collapse_v1";
  /* opsEvidence(出入库耗时分解)物理上挂在 #sceneDock(底 dock),不是 #workHud(右栏)的子级——
     规格三例(批次KPI/货位状态图/出入库耗时分解)里唯一一个住在 dock 的,其余四块都在右栏。
     代理监听因此挂在两者共同的祖先 #viewport 上(见下),而不是只挂 #workHud。 */
  const RAIL_BLOCK_IDS = ["decisionWrap", "slotMapWrap", "traceStats", "queueCard", "phaseRail", "opsEvidence"];
  const RAIL_BLOCK_HEADER_SELECTOR = "#decisionWrap .dHead,#slotMapWrap .mapHead,#traceStats .statsHead,#queueCard .qHead,#phaseRail .phaseTitle,#opsEvidence .oeHead";

  function loadCollapseState() {
    try {
      const raw = root.localStorage.getItem(COLLAPSE_KEY);
      if (!raw) return { rail: false, dock: false, blocks: {} };
      const parsed = JSON.parse(raw);
      return {
        rail: Boolean(parsed.rail), dock: Boolean(parsed.dock),
        blocks: (parsed.blocks && typeof parsed.blocks === "object") ? parsed.blocks : {}
      };
    } catch (error) { return { rail: false, dock: false, blocks: {} }; }
  }
  function saveCollapseState() {
    try { root.localStorage.setItem(COLLAPSE_KEY, JSON.stringify(collapseState)); } catch (error) { /* 隐私模式/配额满,静默降级,不影响功能 */ }
  }
  const collapseState = loadCollapseState();

  const sceneDockEl2 = byId("sceneDock"); /* 第 4 节的 sceneDockEl 是块级 const,这里另起名避免重名冲突 */
  const railCollapseBtn = doc.createElement("button");
  railCollapseBtn.id = "railCollapseBtn"; railCollapseBtn.type = "button";
  railCollapseBtn.innerHTML = '<i class="edgeArrow" aria-hidden="true">◂</i><span class="edgeLabel">面板</span>';
  function applyRailCollapsed(collapsed) {
    doc.documentElement.style.setProperty("--rail-w", collapsed ? "26px" : "");
    if (!collapsed) doc.documentElement.style.removeProperty("--rail-w");
    workHud.classList.toggle("is-collapsed", collapsed);
    railCollapseBtn.setAttribute("aria-expanded", String(!collapsed));
    railCollapseBtn.setAttribute("aria-label", collapsed ? "展开右栏" : "收起右栏");
  }
  railCollapseBtn.addEventListener("click", () => {
    const collapsed = !workHud.classList.contains("is-collapsed");
    applyRailCollapsed(collapsed);
    collapseState.rail = collapsed; saveCollapseState();
    root.dispatchEvent(new Event("resize"));
  });
  workHud.append(railCollapseBtn);
  applyRailCollapsed(collapseState.rail);

  let dockCollapseBtn = null;
  if (sceneDockEl2) {
    dockCollapseBtn = doc.createElement("button");
    dockCollapseBtn.id = "dockCollapseBtn"; dockCollapseBtn.type = "button";
    dockCollapseBtn.innerHTML = '<i class="edgeArrow" aria-hidden="true">▾</i><span class="edgeLabel">面板</span>';
    const applyDockCollapsed = collapsed => {
      viewport.style.setProperty("--scene-dock-h", collapsed ? "26px" : "");
      if (!collapsed) viewport.style.removeProperty("--scene-dock-h");
      sceneDockEl2.classList.toggle("is-collapsed", collapsed);
      dockCollapseBtn.setAttribute("aria-expanded", String(!collapsed));
      dockCollapseBtn.setAttribute("aria-label", collapsed ? "展开底部信息带" : "收起底部信息带");
    };
    dockCollapseBtn.addEventListener("click", () => {
      const collapsed = !sceneDockEl2.classList.contains("is-collapsed");
      applyDockCollapsed(collapsed);
      collapseState.dock = collapsed; saveCollapseState();
      root.dispatchEvent(new Event("resize"));
    });
    sceneDockEl2.append(dockCollapseBtn);
    applyDockCollapsed(collapseState.dock);
  }

  function applyStoredBlockState(id) {
    const block = byId(id);
    if (block && collapseState.blocks[id]) block.classList.add("railBlockCollapsed");
    return Boolean(block);
  }
  const pendingBlockIds = RAIL_BLOCK_IDS.filter(id => !applyStoredBlockState(id));
  if (pendingBlockIds.length && sceneDockEl2) {
    /* opsEvidence 由 renderOpsEvidence 在首条 trace 异步就绪后才 createElement+append(trace 经
       动态 <script> 载入,不是同步可用),此刻查不到属正常;用一次性 MutationObserver 补上持久化态,
       追到后立即断开,不长期占用。 */
    const watcher = new MutationObserver(() => {
      const remaining = pendingBlockIds.filter(id => !applyStoredBlockState(id));
      if (remaining.length === 0) watcher.disconnect();
    });
    watcher.observe(sceneDockEl2, { childList: true });
  }
  /* 代理监听挂 #viewport(#workHud 与 #sceneDock 的共同祖先),一次覆盖右栏四块 + dock 内 opsEvidence。
     捕获阶段能抢在 #slotMapWrap 自身冒泡的「点击放大」监听之前拦截块头点击(见上方大注释)。 */
  viewport.addEventListener("click", event => {
    const header = event.target.closest(RAIL_BLOCK_HEADER_SELECTOR);
    if (!header) return;
    const block = header.closest(RAIL_BLOCK_IDS.map(id => `#${id}`).join(","));
    if (!block) return;
    event.stopPropagation();
    const collapsed = block.classList.toggle("railBlockCollapsed");
    collapseState.blocks[block.id] = collapsed; saveCollapseState();
    root.dispatchEvent(new Event("resize"));
  }, true);

  /* ---------- 7. QA 自检钩子(步骤1 骨架断言 + W1-7 折叠态,供人工/脚本核验) ---------- */
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
        mapOverlayReady: Boolean(overlay),
        collapse: {
          rail: workHud.classList.contains("is-collapsed"),
          dock: Boolean(sceneDockEl2 && sceneDockEl2.classList.contains("is-collapsed")),
          blocks: Object.fromEntries(RAIL_BLOCK_IDS.map(id => { const el = byId(id); return [id, Boolean(el && el.classList.contains("railBlockCollapsed"))]; }))
        }
      };
    },
    showNodePop(index) { if (nodeButtons[index]) { renderNodePop(nodeButtons[index]); return nodePop.getBoundingClientRect(); } return null; },
    hidePops() { nodePop.classList.remove("show"); }
  });
})(window);
