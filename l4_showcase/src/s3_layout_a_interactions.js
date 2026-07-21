/* S3 方案A「进度轴驱动」交互层(0716,规格=design_reviews/0716_s3_ia_review/spec_a_freeze.md)
   原则:s3_fill_candidate_runtime.js / s3_fill_store.js 零改动——本层只做:
   ① DOM 搬运(元素引用与事件委托不失效) ② CSS 作用域开关 ③ 浮层(节点快照/七步说明/证据链)
   ④ runtime 每帧写死文案的治理(MutationObserver 防重入) ⑤ QA 自检钩子。 */
(function (root) {
  "use strict";
  const doc = root.document;
  if (doc.documentElement.dataset.s3Mode !== "fill-only-candidate" || !root.__S3_FILL_QA) return;

  const byId = id => doc.getElementById(id);
  const BOOKMARKS = [0, 67, 134, 201, 241, 267];
  const PCT = ["0%", "25%", "50%", "75%", "90%", "100%"];
  const viewport = byId("viewport");
  const workHud = byId("workHud");
  const sceneDock = byId("sceneDock");

  /* ---------- 1. 布局作用域 ---------- */
  doc.documentElement.dataset.s3Layout = "A";

  /* ---------- 2. 顶栏:railHead + runtimeControls 搬入静态 #topbarA(W6:改用 HTML 静态占位,
     同 02 终态,免一次 JS createElement 的首屏时序缝隙;元素不存在则整段安全跳过) ---------- */
  const topbar = byId("topbarA");
  if (topbar) topbar.append(byId("railHead"), byId("runtimeControls"));

  /* ---------- 3. 进度轴宿主:fillBookmarks 重塑,迁入右栏顶部(W6 同 02 0720 版B:竖排空间换横排,
     3D 视野增大)。#progressAxisHost 的 order:-1(见样式区)保证恒居 #workHud 首位。 ---------- */
  const axisHost = doc.createElement("div");
  axisHost.id = "progressAxisHost";
  workHud.prepend(axisHost);
  const bookmarks = byId("fillBookmarks");
  axisHost.append(bookmarks);
  /* 0720 命名总表 B4:标题简化为「入库进度」,「容量节点」语义降入副题小字(全页唯一出现处) */
  const fillHead = bookmarks.querySelector(".fillHead");
  fillHead.querySelector("b").textContent = "入库进度";
  fillHead.querySelector("span").textContent = "容量节点 · 点击跳转并暂停到已验证快照";
  /* 轴线填充与节点定位 */
  const buttonHost = byId("fillBookmarkButtons");
  const axisFill = doc.createElement("i");
  axisFill.className = "axisFill";
  buttonHost.prepend(axisFill);
  const nodeButtons = Array.from(buttonHost.querySelectorAll("button[data-count]"));
  nodeButtons.forEach(button => {
    const count = Number(button.dataset.count);
    const index = BOOKMARKS.indexOf(count);
    button.style.left = `${(count / 267 * 100).toFixed(2)}%`;
    button.dataset.axisLabel = `${count} · ${PCT[index]}`;
    button.setAttribute("aria-label", `跳转到 ${count} / 267(${PCT[index]})并暂停到已验证快照`);
  });
  /* 计数组(全页唯一)+ 验证角标 移到轴右端 */
  const axisRight = doc.createElement("div");
  axisRight.id = "axisRight";
  bookmarks.append(axisRight);
  axisRight.append(byId("fillEvidence"), byId("releaseBadge"));

  /* ---------- 4. dock:W6(照 02 语言重做)白化四分列(当前作业 | 轴状态 | 目标货位卡 | 2D 图例)。
     七段微条(phaseRail)不再并入「当前作业」格——迁回右栏,成为独立可折叠块,恢复 02 终态的
     信息架构(七步条与决策卡/KPI塔同级,不再挤占 dock 空间);它在 inline 场景脚本里本就是
     rail.append(...) 的直接子级,这里不搬运,只需不再把它 append 进 sceneCaption。
     镜头/演示倍率迁到 3D 区右下角悬浮小卡(同 02 0720 版B);01 rail 在左、3D 在右,不需要像
     02 那样在样式里扣减 --rail-w。 ---------- */
  if (byId("sceneTools").parentElement !== viewport) viewport.append(byId("sceneTools"));
  /* 0717 #28 二轮(用户拍板):dock 第三格=目标货位卡——接管 3D 黄标牌的全部文字信息
     (3D 场景只留发光壳+面框+箭头图形高亮);声明 target-card 模式供 runtime 分支。 */
  doc.documentElement.dataset.s3TargetCard = "1";
  const targetCard = doc.createElement("section");
  targetCard.id = "targetCard";
  targetCard.setAttribute("aria-label", "当前目标货位");
  targetCard.setAttribute("aria-live", "off");
  targetCard.innerHTML = '<div class="targetHead"><b>目标货位</b><span id="targetCardState">等待轨迹</span></div>' +
    '<b id="targetCardSlot">-- / --</b><span id="targetCardDetail">同源 SIM 轨迹载入中</span>';
  sceneDock.append(targetCard);
  const factsSlot = doc.createElement("span");
  factsSlot.id = "railFactsDockSlot";
  byId("sceneCaption").append(factsSlot);
  const queueCell = byId("factQueue").parentElement; /* <div><b id=factQueue>..</b><span>入口等待</span></div> */
  queueCell.style.cssText = "display:flex;gap:4px;align-items:baseline;background:transparent;padding:0";
  factsSlot.append(queueCell);
  /* W6:reserveRuleBadge 由 3D 悬浮小标牌收编为 dock 第四格「2D 图例」列(同 02 heatLegend 收编手法);
     补一个块头(runtime.js 的 innerHTML 只写图例条目本身,不含标题),对齐其余三格都有标题的观感。
     不改 runtime.js 里 reserveRuleBadge.innerHTML 的原文——QA hotVisual.legendPresent 断言依赖
     其中「热门前 20%」原文子串,搬运/加壳不碰这段文本。 */
  const reserveBadgeEl = byId("reserveRuleBadge");
  const legendHead = doc.createElement("div");
  legendHead.className = "legendHead";
  legendHead.innerHTML = "<b>2D 图例</b>";
  reserveBadgeEl.prepend(legendHead);
  sceneDock.append(reserveBadgeEl);
  /* 七段可聚焦 */
  const segments = Array.from(byId("phaseSegments").children);
  segments.forEach(segment => segment.setAttribute("tabindex", "0"));
  /* 2D 小卡放大提示 */
  const mapWrap = byId("slotMapWrap");
  const zoomHint = doc.createElement("span");
  zoomHint.className = "zoomHint";
  zoomHint.textContent = "点击放大 ⤢";
  mapWrap.append(zoomHint);
  /* 0717 #26-4:终态货-格配对差异热力图(仅放大 overlay 内显示;canvas 由 runtime 绘制,
     满仓守恒下货-格配对是唯一有信息量的终态对比) */
  const diffWrap = doc.createElement("div");
  diffWrap.id = "diffMapWrap";
  diffWrap.innerHTML = '<div class="diffHead"><b>终态货-格配对差异 · SCORE − SEQ</b>' +
    '<span>满仓终态三算法占同一 267 格集合(完工/行程守恒),差异全部在「哪件货配哪格」——每格显示两算法所放货物的访问频次差</span></div>' +
    '<canvas id="diffMap"></canvas>' +
    '<div class="diffKey"><span><i class="dPos"></i>SCORE 放了更热门的货</span>' +
    '<span><i class="dNeg"></i>SCORE 放了更冷门的货</span><span><i class="dZero"></i>预占 / 无差</span></div>';
  mapWrap.append(diffWrap);
  /* 取货指标注解(E2,0716):点明终点统计中的取货项回应赛题「存取效率」;traceStats 由 runtime 重写 innerHTML,注解放其后独立节点 */
  const retrievalNote = doc.createElement("div");
  retrievalNote.id = "retrievalNote";
  retrievalNote.textContent = "期望/热门取货 = 访问频次加权的取货时间(SIM)——放置质量决定取出效率,直接回应赛题「存取效率(单位时间存取量)」指标。";
  byId("traceStats").after(retrievalNote);

  /* ---------- 5. 共享浮层 ---------- */
  function makePop(id) {
    const pop = doc.createElement("div");
    pop.id = id;
    pop.className = "s3aPop";
    pop.setAttribute("role", "tooltip");
    viewport.append(pop);
    return pop;
  }
  const nodePop = makePop("axisNodePop");
  const segPop = makePop("segPop");
  const evidencePop = makePop("evidencePop");

  function placePop(pop, anchor, prefer = "below") {
    const viewportRect = viewport.getBoundingClientRect();
    const rect = anchor.getBoundingClientRect();
    pop.style.visibility = "hidden";
    pop.classList.add("show");
    const popRect = pop.getBoundingClientRect();
    let left = rect.left - viewportRect.left + rect.width / 2 - popRect.width / 2;
    left = Math.max(8, Math.min(left, viewportRect.width - popRect.width - 8));
    let top = prefer === "below"
      ? rect.bottom - viewportRect.top + 8
      : rect.top - viewportRect.top - popRect.height - 8;
    if (top < 8) top = rect.bottom - viewportRect.top + 8;
    if (top + popRect.height > viewportRect.height - 8) top = rect.top - viewportRect.top - popRect.height - 8;
    pop.style.left = `${Math.round(left)}px`;
    pop.style.top = `${Math.round(top)}px`;
    pop.style.visibility = "";
  }
  function hidePops() {
    [nodePop, segPop, evidencePop].forEach(pop => pop.classList.remove("show"));
    if (segPopTimer) { clearInterval(segPopTimer); segPopTimer = null; }
  }

  /* 节点快照浮层(按需披露;默认态不重复计数组) */
  function renderNodePop(button) {
    const count = Number(button.dataset.count);
    const index = BOOKMARKS.indexOf(count);
    const current = button.getAttribute("aria-current") === "true";
    const violations = (byId("fillViol") || {}).textContent || "0";
    nodePop.innerHTML = `<h4>节点 ${count} / 267(${PCT[index]})${current ? " · 当前" : ""}</h4>` +
      `<table><tr><td>管理货</td><td>${count} / 267</td></tr>` +
      `<tr><td>总占用</td><td>${133 + count} / 400</td></tr>` +
      `<tr><td>约束违规</td><td>${violations}</td></tr></table>` +
      `<div class="note">${count === 267 ? "267=可管理容量;133 预占 + 267 = 400 总占用。" : "133 预占为不可管理体积,不计入管理容量。"}` +
      `点击圆点跳转并暂停到已验证快照 · SIM。</div>`;
    placePop(nodePop, button, "below");
  }
  nodeButtons.forEach(button => {
    button.addEventListener("mouseenter", () => renderNodePop(button));
    button.addEventListener("focus", () => renderNodePop(button));
    button.addEventListener("mouseleave", () => nodePop.classList.remove("show"));
    button.addEventListener("blur", () => nodePop.classList.remove("show"));
  });

  /* 七步说明浮层:runtime 每帧把「目的;SIM;演示」写进 span.title,浮层实时读取 */
  let segPopTimer = null;
  function renderSegPop(segment, index) {
    const parse = () => {
      const parts = String(segment.title || "").split("；");
      const name = (segment.querySelector(".phaseName") || {}).textContent || `第 ${index + 1} 步`;
      segPop.innerHTML = `<h4>第 ${index + 1} 步 · ${name}</h4>` +
        `<div class="rows"><div><span>${parts[0] || "--"}</span></div>` +
        `<div><span>SIM 时长</span><span>${(parts[1] || "--").replace("SIM ", "")}</span></div>` +
        `<div><span>演示时长</span><span>${(parts[2] || "--").replace("演示 ", "")}</span></div></div>` +
        `<div class="note">7 展示步由 4 阶段 trace 按几何/货叉阈值拆分;演示时长=0.38s + 0.05×SIM 单调压缩,不反转各步长短。</div>`;
    };
    parse();
    placePop(segPop, segment, "above");
    if (segPopTimer) clearInterval(segPopTimer);
    segPopTimer = setInterval(parse, 250);
  }
  segments.forEach((segment, index) => {
    segment.addEventListener("mouseenter", () => renderSegPop(segment, index));
    segment.addEventListener("focus", () => renderSegPop(segment, index));
    segment.addEventListener("mouseleave", () => { segPop.classList.remove("show"); if (segPopTimer) { clearInterval(segPopTimer); segPopTimer = null; } });
    segment.addEventListener("blur", () => { segPop.classList.remove("show"); if (segPopTimer) { clearInterval(segPopTimer); segPopTimer = null; } });
  });

  /* 证据链浮层:数据链已验证 → 点击展开 */
  const loadState = byId("traceLoadState");
  loadState.setAttribute("role", "button");
  loadState.setAttribute("tabindex", "0");
  loadState.setAttribute("aria-haspopup", "dialog");
  function toggleEvidence() {
    if (evidencePop.classList.contains("show")) { evidencePop.classList.remove("show"); return; }
    const snapshot = root.__S3_FILL_QA.snapshot();
    evidencePop.innerHTML = `<h4>数据链已验证 · 证据链</h4>` +
      `<table><tr><td>release</td><td>${snapshot.releaseId}</td></tr>` +
      `<tr><td>违规</td><td>0</td></tr></table>` +
      `<div class="rows"><div><span>bundle payload SHA-256</span></div></div><code>${snapshot.bundlePayloadSha256}</code>` +
      `<div class="note">${snapshot.timingAudit.mapping}。本地哈希锁定的可复现证据快照,不是加密签名。三条在线算法 × 各 267 件,SIM 证据边界。</div>`;
    placePop(evidencePop, loadState, "below");
  }
  loadState.addEventListener("click", toggleEvidence);
  loadState.addEventListener("keydown", event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); toggleEvidence(); } });

  /* ---------- 6. 2D 放大覆盖层(DOM 搬运,canvas 自适应重画) ---------- */
  const overlay = doc.createElement("div");
  overlay.id = "s3MapOverlay";
  overlay.innerHTML = '<div class="mapDock"><button type="button" class="mapDockClose" aria-label="关闭放大视图">×</button></div>';
  viewport.append(overlay);
  const mapDock = overlay.querySelector(".mapDock");
  const mapHome = { parent: mapWrap.parentElement, next: mapWrap.nextSibling };
  function openMap() {
    if (overlay.classList.contains("open")) return;
    mapDock.append(mapWrap);
    overlay.classList.add("open");
  }
  function closeMap() {
    if (!overlay.classList.contains("open")) return;
    overlay.classList.remove("open");
    mapHome.parent.insertBefore(mapWrap, mapHome.next);
  }
  mapWrap.addEventListener("click", () => { if (!overlay.classList.contains("open")) openMap(); });
  overlay.addEventListener("click", event => { if (event.target === overlay || event.target.classList.contains("mapDockClose")) closeMap(); });
  root.addEventListener("keydown", event => {
    if (event.key === "Escape") { closeMap(); hidePops(); }
  });

  /* ---------- 7. 进度轴实时推进(监听 runtime 每帧写入的 #fillManaged) ---------- */
  let lastManaged = -1;
  function syncAxis() {
    const managed = parseInt((byId("fillManaged") || {}).textContent, 10);
    if (!Number.isFinite(managed) || managed === lastManaged) return;
    lastManaged = managed;
    axisFill.style.width = `${(managed / 267 * 100).toFixed(2)}%`;
    nodeButtons.forEach(button => button.classList.toggle("axisDone", Number(button.dataset.count) <= managed));
  }
  new MutationObserver(syncAxis).observe(byId("fillManaged"), { childList: true, characterData: true, subtree: true });
  syncAxis();

  /* ---------- 8. runtime 写死文案治理(防重入改写;不改 runtime) ----------
     0720 命名总表 B4:源「容量书签」已改「入库进度」词根并清零,原「容量书签」专属拦截分支
     (phaseNow/actionText 命中该词的重写)随之整体删除;此处只保留与该词无关的治理——
     连续填满完成简写、idle 态总占用隐藏(避免 dock 内计数重复)。 */
  const actionText = byId("sceneActionText");
  const cargoMeta = byId("sceneCargoMeta");
  let rewriting = false;
  const rewriteObserver = new MutationObserver(() => {
    if (rewriting) return;
    rewriting = true;
    try {
      const action = actionText.textContent;
      if (/连续填满完成 · \d+ \/ 267/.test(action)) {
        actionText.textContent = "连续填满完成";
      }
      const cargoIdle = /总占用/.test(cargoMeta.textContent);
      cargoMeta.style.visibility = cargoIdle ? "hidden" : "";
    } finally {
      rewriting = false;
    }
  });
  [actionText, cargoMeta].forEach(element =>
    rewriteObserver.observe(element, { childList: true, characterData: true, subtree: true }));
  rewriteObserver.takeRecords();
  if (/总占用/.test(cargoMeta.textContent)) cargoMeta.style.visibility = "hidden";

  /* ---------- 8b. 布局搬运改变了 #gl 尺寸:触发 resize 让 renderer/浮签重算 ---------- */
  root.dispatchEvent(new Event("resize"));

  /* ---------- 9. 折叠收纳(W6,拍板「整栏收边+逐块折叠+持久化」,同 02 W1-7) ----------
     右栏(#workHud)与底 dock(#sceneDock)两大版块整体收成 26px 边缘细条;
     栏内五块(算法决策/2D 三算法对比/批次KPI/七步在做什么/七步条)块头可单独折叠。
     机制:收展只改 --rail-w / --scene-dock-h 两个既有 CSS 变量的值,#gl/#sceneDock 等一切引用它们的
     规则自动跟随(样式见 01 html 的 W6 收口节)。持久化 localStorage s3_collapse_01_v1 =
     {rail,dock,blocks:{id:bool}}(键名与 02 的 s3_collapse_v1 区分,互不干扰);
     缺省/解析失败=全展开,保证 QA 脚本首次加载零感知。
     01 的五个可折叠块全在右栏(不像 02 还有一个 opsEvidence 住在 dock),事件代理挂在
     #workHud 本身即可覆盖,不需要像 02 那样上提到共同祖先 #viewport。同理,01 的
     decisionWrap/slotMapWrap/traceStats/processGuide/phaseRail 全部在 configureDom()
     同步创建(不像 02 的 opsEvidence 要等异步 trace 就绪才 append),故不需要 MutationObserver
     兜底,直接查一次即可。用捕获阶段是因为 #slotMapWrap 自身已有「点击放大 2D 图」的冒泡监听
     (见下第 6 节),块头点击若走冒泡会先触发放大再触发折叠;捕获阶段能抢在放大监听之前
     stopPropagation 拦下块头点击。 */
  /* processGuide 不入列:它自 0716 起即 display:none!important 退役(七步常驻面板已被 dock 微条+
     phaseRail 悬浮说明取代,QA processGuideHidden 断言强制其隐藏),W6 不重开此决定——只重排
     "仍可见" 的块。 */
  const COLLAPSE_KEY = "s3_collapse_01_v1";
  const RAIL_BLOCK_IDS = ["decisionWrap", "slotMapWrap", "traceStats", "phaseRail"];
  const RAIL_BLOCK_HEADER_SELECTOR = "#decisionWrap .dHead,#slotMapWrap .mapHead,#traceStats .statsHead,#phaseRail .phaseTitle";

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
  if (sceneDock) {
    dockCollapseBtn = doc.createElement("button");
    dockCollapseBtn.id = "dockCollapseBtn"; dockCollapseBtn.type = "button";
    dockCollapseBtn.innerHTML = '<i class="edgeArrow" aria-hidden="true">▾</i><span class="edgeLabel">面板</span>';
    const applyDockCollapsed = collapsed => {
      viewport.style.setProperty("--scene-dock-h", collapsed ? "26px" : "");
      if (!collapsed) viewport.style.removeProperty("--scene-dock-h");
      sceneDock.classList.toggle("is-collapsed", collapsed);
      dockCollapseBtn.setAttribute("aria-expanded", String(!collapsed));
      dockCollapseBtn.setAttribute("aria-label", collapsed ? "展开底部信息带" : "收起底部信息带");
    };
    dockCollapseBtn.addEventListener("click", () => {
      const collapsed = !sceneDock.classList.contains("is-collapsed");
      applyDockCollapsed(collapsed);
      collapseState.dock = collapsed; saveCollapseState();
      root.dispatchEvent(new Event("resize"));
    });
    sceneDock.append(dockCollapseBtn);
    applyDockCollapsed(collapseState.dock);
  }

  RAIL_BLOCK_IDS.forEach(id => {
    const block = byId(id);
    if (block && collapseState.blocks[id]) block.classList.add("railBlockCollapsed");
  });
  workHud.addEventListener("click", event => {
    const header = event.target.closest(RAIL_BLOCK_HEADER_SELECTOR);
    if (!header) return;
    const block = header.closest(RAIL_BLOCK_IDS.map(id => `#${id}`).join(","));
    if (!block) return;
    event.stopPropagation();
    const collapsed = block.classList.toggle("railBlockCollapsed");
    collapseState.blocks[block.id] = collapsed; saveCollapseState();
    root.dispatchEvent(new Event("resize"));
  }, true);

  /* ---------- 10. QA 自检钩子 ---------- */
  function visibleLeafTexts() {
    return Array.from(doc.querySelectorAll("body *")).filter(element => {
      const style = getComputedStyle(element);
      const rect = element.getBoundingClientRect();
      return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0 && element.children.length === 0;
    }).map(element => (element.textContent || "").trim()).filter(Boolean);
  }
  root.__S3_LAYOUT_A = Object.freeze({
    version: "s3-layout-a-interactions-v1",
    audit() {
      const texts = visibleLeafTexts();
      return {
        layout: doc.documentElement.dataset.s3Layout,
        forbiddenBookmarkTermHits: texts.filter(text => text.includes("容量书签")).length,
        capacityNodeTermHits: texts.filter(text => text.includes("容量节点")).length,
        managedCountVisibleHits: texts.filter(text => /管理货/.test(text)).length,
        totalCountVisibleHits: texts.filter(text => /总占用/.test(text)).length,
        stepPurposeVisibleHits: texts.filter(text => /T 形互锁台交接至堆垛机|X \/ Z 双轴按加减速模型/.test(text)).length,
        processGuideHidden: getComputedStyle(byId("processGuide")).display === "none",
        taskLineHidden: getComputedStyle(byId("taskline")).display === "none",
        topbarPresent: Boolean(byId("topbarA")),
        axisNodeCount: nodeButtons.length,
        axisFillWidth: axisFill.style.width,
        segmentsFocusable: segments.every(segment => segment.getAttribute("tabindex") === "0"),
        mapOverlayOpen: overlay.classList.contains("open"),
        pops: {
          node: nodePop.classList.contains("show"),
          seg: segPop.classList.contains("show"),
          evidence: evidencePop.classList.contains("show")
        },
        /* W6:折叠态自检(同 02 __S3_MIXED_LAYOUT_A.audit() 的 collapse 字段) */
        collapse: {
          rail: workHud.classList.contains("is-collapsed"),
          dock: Boolean(sceneDock && sceneDock.classList.contains("is-collapsed")),
          blocks: Object.fromEntries(RAIL_BLOCK_IDS.map(id => { const el = byId(id); return [id, Boolean(el && el.classList.contains("railBlockCollapsed"))]; }))
        }
      };
    },
    openMap, closeMap,
    showNodePop(index) { renderNodePop(nodeButtons[index]); return nodePop.getBoundingClientRect(); },
    showSegPop(index) { renderSegPop(segments[index], index); return segPop.getBoundingClientRect(); },
    showEvidence() { if (!evidencePop.classList.contains("show")) toggleEvidence(); return evidencePop.getBoundingClientRect(); },
    hidePops,
    toggleRailCollapse() { railCollapseBtn.click(); return workHud.classList.contains("is-collapsed"); },
    toggleDockCollapse() { if (dockCollapseBtn) dockCollapseBtn.click(); return Boolean(sceneDock && sceneDock.classList.contains("is-collapsed")); },
    toggleBlockCollapse(id) {
      const block = byId(id); if (!block) return null;
      const header = block.querySelector(".dHead,.mapHead,.statsHead,.phaseTitle");
      if (header) header.click();
      return block.classList.contains("railBlockCollapsed");
    }
  });
})(window);
