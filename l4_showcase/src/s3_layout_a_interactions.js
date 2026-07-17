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

  /* ---------- 2. 顶栏:railHead + runtimeControls 搬入 ---------- */
  const topbar = doc.createElement("div");
  topbar.id = "topbarA";
  viewport.prepend(topbar);
  topbar.append(byId("railHead"), byId("runtimeControls"));

  /* ---------- 3. 进度轴宿主:fillBookmarks 重塑 ---------- */
  const axisHost = doc.createElement("div");
  axisHost.id = "progressAxisHost";
  viewport.insertBefore(axisHost, byId("gl"));
  const bookmarks = byId("fillBookmarks");
  axisHost.append(bookmarks);
  /* 术语(一次性,全页唯一出现处):原「容量书签 · 从空到满」 */
  const fillHead = bookmarks.querySelector(".fillHead");
  fillHead.querySelector("b").textContent = "入库进度 · 容量节点";
  fillHead.querySelector("span").textContent = "点击节点跳转并暂停到已验证快照";
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
  /* 0717 #28 二轮(用户拍板):镜头与演示倍率整体上移到进度轴行(节点轴与计数簇之间) */
  bookmarks.insertBefore(byId("sceneTools"), axisRight);

  /* ---------- 4. dock:0717 #28 四格并三格——七段微条并入「当前作业」格(仍在 sceneDock 内,
     步骤名由微条题行唯一承担,货物信息升大字);入口等待入 caption;路径图例移场景左下 ---------- */
  byId("sceneCaption").append(byId("phaseRail"));
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
  viewport.append(byId("reserveRuleBadge"));
  /* 七段可聚焦 */
  const segments = Array.from(byId("phaseSegments").children);
  segments.forEach(segment => segment.setAttribute("tabindex", "0"));
  /* 2D 小卡放大提示 */
  const mapWrap = byId("slotMapWrap");
  const zoomHint = doc.createElement("span");
  zoomHint.className = "zoomHint";
  zoomHint.textContent = "点击放大 ⤢";
  mapWrap.append(zoomHint);
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
     规则(spec §3/§5):禁止词「容量书签」;idle 态计数不得在 dock 重复。 */
  const phaseNow = byId("phaseNow");
  const actionText = byId("sceneActionText");
  const cargoMeta = byId("sceneCargoMeta");
  let rewriting = false;
  const rewriteObserver = new MutationObserver(() => {
    if (rewriting) return;
    rewriting = true;
    try {
      const now = phaseNow.textContent;
      if (now.includes("容量书签")) phaseNow.textContent = "已暂停 · 节点快照";
      const action = actionText.textContent;
      if (action.includes("容量书签")) {
        const match = action.match(/等待第 (\d+) 件/);
        actionText.textContent = match ? `等待第 ${match[1]} 件入库` : "已暂停 · 节点快照";
      } else if (/连续填满完成 · \d+ \/ 267/.test(action)) {
        actionText.textContent = "连续填满完成";
      }
      const cargoIdle = /总占用/.test(cargoMeta.textContent);
      cargoMeta.style.visibility = cargoIdle ? "hidden" : "";
    } finally {
      rewriting = false;
    }
  });
  [phaseNow, actionText, cargoMeta].forEach(element =>
    rewriteObserver.observe(element, { childList: true, characterData: true, subtree: true }));
  rewriteObserver.takeRecords();
  phaseNow.textContent = phaseNow.textContent.includes("容量书签") ? "已暂停 · 节点快照" : phaseNow.textContent;
  if (actionText.textContent.includes("容量书签")) {
    const match = actionText.textContent.match(/等待第 (\d+) 件/);
    actionText.textContent = match ? `等待第 ${match[1]} 件入库` : "已暂停 · 节点快照";
  }
  if (/总占用/.test(cargoMeta.textContent)) cargoMeta.style.visibility = "hidden";

  /* ---------- 8b. 布局搬运改变了 #gl 尺寸:触发 resize 让 renderer/浮签重算 ---------- */
  root.dispatchEvent(new Event("resize"));

  /* ---------- 9. QA 自检钩子 ---------- */
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
        }
      };
    },
    openMap, closeMap,
    showNodePop(index) { renderNodePop(nodeButtons[index]); return nodePop.getBoundingClientRect(); },
    showSegPop(index) { renderSegPop(segments[index], index); return segPop.getBoundingClientRect(); },
    showEvidence() { if (!evidencePop.classList.contains("show")) toggleEvidence(); return evidencePop.getBoundingClientRect(); },
    hidePops
  });
})(window);
