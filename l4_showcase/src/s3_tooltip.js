/* S3 悬浮解释层公共模块(0728 阶段二:双页悬浮全覆盖)
 *
 * 用户拍板:「主界面整洁,但评委鼠标悬浮到对应的位置,都可以有小悬浮窗解释我们为什么这么做
 * 以及有多优秀」+「全覆盖 + 首次进页引导」+ 文案「三段式,注意用词要学术」。
 *
 * 为什么不用原生 title:①约 1 秒延迟,评委多半等不到就移开了 ②无法排版(三段式挤成一行)
 * ③长文本被系统截断 ④样式不受控,与三页的白红工程风割裂。
 *
 * 为什么用**事件委托 + 选择器注册表**而不是逐元素 addEventListener:两页的指标区、图例、
 * 步骤条都是每帧用 innerHTML 重渲染的,逐元素绑定会在第一次重渲染时全部失效(挂上去看着有,
 * 演示到第二帧就没了)。委托到 document 后,注册表按选择器匹配,重渲染免疫。
 *
 * 三段式结构(学术工程风;不吹嘘、不把自主设计包装成行业规范):
 *   what —— 这个量/控件**是什么**(定义与口径,含单位与分母)
 *   why  —— **为何这样设计**(依据分级标注:硬约束 / 跨域类比 / 厂商实践 / 本项目自主设计)
 *   edge —— **优在哪 / 边界在哪**(可复现数字及其来源,或明确的不适用场景)
 * 三段均可缺省;缺省段不渲染空壳。edge 里出现的数字必须能指到来源文件或命令。
 *
 * 定位:气泡 position:fixed 脱离任何 overflow 裁剪链(0719 tipBubble 被 workHud 裁掉的教训),
 * 按可用空间自动上下翻转并夹进视口,不做「总在右侧」这种窄容器里必然出画的假设。
 *
 * 载入契约:classic script,挂 window.S3Tooltip,须在各页 runtime 之前载入。
 */
"use strict";
(function (root, doc) {
  const registry = [];          /* [{selector, spec}] —— 后注册的排在后面,匹配时从内向外走 DOM */
  let layer = null, active = null, serial = 0;

  function injectStyle() {
    if (doc.getElementById("s3TooltipStyle")) return;
    const style = doc.createElement("style");
    style.id = "s3TooltipStyle";
    /* 白底 + ABB 红左条,与三页顶栏同一套工程风;全站红线禁深色大底,此处仅气泡本体用白。 */
    style.textContent = `
#s3TooltipLayer{position:fixed;inset:0;pointer-events:none;z-index:9000}
#s3TooltipLayer .s3tip{position:absolute;max-width:352px;background:#fff;color:#17202b;
  border:1px solid #c9d0d6;border-left:3px solid #ff000f;border-radius:3px;
  box-shadow:0 6px 22px rgba(23,32,43,.16);padding:9px 11px 10px;font-size:12px;line-height:1.55;
  opacity:0;transform:translateY(3px);transition:opacity .12s ease,transform .12s ease}
#s3TooltipLayer .s3tip.is-on{opacity:1;transform:translateY(0)}
#s3TooltipLayer .s3tip b.tt{display:block;font-size:12.5px;font-weight:700;margin-bottom:4px;letter-spacing:.01em}
#s3TooltipLayer .s3tip p{margin:0 0 5px}
#s3TooltipLayer .s3tip p:last-child{margin-bottom:0}
#s3TooltipLayer .s3tip .k{display:inline-block;color:#8a939b;font-weight:700;
  font-size:10.5px;letter-spacing:.06em;margin-right:6px}
#s3TooltipLayer .s3tip .edge{color:#4a5560;border-top:1px dashed #dfe4e7;padding-top:5px;margin-top:6px}
[data-s3tip="1"]{cursor:help}
/* bottom 抬到 150px:两页底部都有约 110–130 px 高的仪表 dock,贴 18px 会正好盖住它。
   引导是临时物,不该遮住常驻信息。 */
#s3FirstHint{position:fixed;z-index:9001;right:18px;bottom:150px;background:#17202b;color:#fff;
  border-radius:4px;padding:9px 13px;font-size:12.5px;line-height:1.5;
  box-shadow:0 8px 26px rgba(23,32,43,.28);display:flex;align-items:center;gap:12px;max-width:380px}
#s3FirstHint b{color:#ffd400;font-weight:700}
#s3FirstHint button{border:0;background:rgba(255,255,255,.16);color:#fff;border-radius:3px;
  padding:4px 10px;font-size:12px;cursor:pointer;white-space:nowrap}
#s3FirstHint button:hover{background:rgba(255,255,255,.28)}
@media (prefers-reduced-motion:reduce){#s3TooltipLayer .s3tip{transition:none}}`;
    doc.head.appendChild(style);
  }

  function ensureLayer() {
    if (layer && layer.isConnected) return layer;
    injectStyle();
    layer = doc.createElement("div");
    layer.id = "s3TooltipLayer";
    doc.body.appendChild(layer);
    return layer;
  }

  const esc = text => String(text == null ? "" : text)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

  function render(spec) {
    const parts = [];
    if (spec.title) parts.push(`<b class="tt">${esc(spec.title)}</b>`);
    if (spec.what) parts.push(`<p><span class="k">是什么</span>${esc(spec.what)}</p>`);
    if (spec.why) parts.push(`<p><span class="k">为何这样</span>${esc(spec.why)}</p>`);
    if (spec.edge) parts.push(`<p class="edge"><span class="k">优 / 边界</span>${esc(spec.edge)}</p>`);
    return parts.join("");
  }

  function place(bubble, host) {
    const r = host.getBoundingClientRect(), b = bubble.getBoundingClientRect();
    const vw = root.innerWidth, vh = root.innerHeight, gap = 8, pad = 6;
    /* 优先放触发元素下方;下方装不下就翻到上方;两边都不够则贴住空间较大的一侧再夹进视口。 */
    const below = vh - r.bottom - gap, above = r.top - gap;
    let top = (below >= b.height || below >= above) ? r.bottom + gap : r.top - gap - b.height;
    top = Math.max(pad, Math.min(top, vh - b.height - pad));
    let left = r.left + r.width / 2 - b.width / 2;
    left = Math.max(pad, Math.min(left, vw - b.width - pad));
    bubble.style.top = `${Math.round(top)}px`;
    bubble.style.left = `${Math.round(left)}px`;
  }

  function show(host, spec) {
    if (active && active.host === host) return;
    hide();
    /* 原生 title 会与自定义气泡同时冒出来、两个框叠在一起;搬进 data 备份后摘掉。 */
    if (host.hasAttribute("title")) {
      host.dataset.s3tipNativeTitle = host.getAttribute("title");
      host.removeAttribute("title");
    }
    host.dataset.s3tip = "1";
    const bubble = doc.createElement("div");
    bubble.className = "s3tip";
    bubble.id = `s3tip-${++serial}`;
    bubble.setAttribute("role", "tooltip");
    bubble.innerHTML = render(spec);
    ensureLayer().appendChild(bubble);
    place(bubble, host);          /* 插入后先量一次真实尺寸 */
    place(bubble, host);          /* 再按真实尺寸定一次,避免首帧跳位 */
    root.requestAnimationFrame(() => bubble.classList.add("is-on"));
    host.setAttribute("aria-describedby", bubble.id);
    active = {host, bubble, spec};
  }

  function hide() {
    if (!active) return;
    active.host.removeAttribute("aria-describedby");
    if (active.bubble.parentNode) active.bubble.parentNode.removeChild(active.bubble);
    active = null;
  }

  const normalize = spec => (typeof spec === "string" ? {what: spec} : (spec || {}));

  /* 注册表:selector → spec。两页各注册自己那张;同一选择器重复注册以最后一次为准。 */
  function register(table) {
    Object.keys(table).forEach(selector => {
      const existing = registry.find(entry => entry.selector === selector);
      if (existing) existing.spec = normalize(table[selector]);
      else registry.push({selector, spec: normalize(table[selector])});
    });
    sweep();
    return registry.length;
  }

  /* 从事件目标向上走,命中的最内层元素胜出(内层语义比外层容器更精确)。 */
  function findHit(target) {
    for (let node = target; node && node.nodeType === 1 && node !== doc.body; node = node.parentElement) {
      for (const entry of registry) {
        try { if (node.matches(entry.selector)) return {host: node, spec: entry.spec}; }
        catch (error) { /* 非法选择器不该拖垮整页,跳过 */ }
      }
    }
    return null;
  }

  /* 给当前匹配到的元素打标记 + 摘原生 title + 补 tabindex(键盘走查可达)。
     重渲染后可再调一次;幂等。 */
  function sweep() {
    let n = 0;
    registry.forEach(entry => {
      let nodes;
      try { nodes = doc.querySelectorAll(entry.selector); } catch (error) { return; }
      nodes.forEach(el => {
        el.dataset.s3tip = "1"; n += 1;
        if (el.hasAttribute("title")) {
          el.dataset.s3tipNativeTitle = el.getAttribute("title");
          el.removeAttribute("title");
        }
        if (!/^(A|BUTTON|INPUT|SELECT|TEXTAREA)$/.test(el.tagName) && !el.hasAttribute("tabindex")) {
          el.setAttribute("tabindex", "0");
        }
      });
    });
    return n;
  }

  /* 首次进页一次性引导:localStorage 记忆,二次访问不打扰。键名风格同既有 s3_collapse_01_v1。 */
  function firstVisitHint(options) {
    const o = options || {}, key = o.key;
    if (!key) return false;
    let seen = false;
    try { seen = root.localStorage.getItem(key) === "1"; } catch (error) { seen = false; }
    if (seen) return false;
    injectStyle();
    const box = doc.createElement("div");
    box.id = "s3FirstHint";
    box.setAttribute("role", "status");
    const text = doc.createElement("span");
    text.innerHTML = o.html ||
      `把鼠标停在任意<b>指标 / 图例 / 控件</b>上,可展开该项的口径、设计依据与适用边界。`;
    const button = doc.createElement("button");
    button.type = "button"; button.textContent = o.dismissText || "知道了";
    /* 「首次进页」的语义是**出现过一次就算数**,不是「点过按钮才算数」:评委不点直接走开,
       下次进来再弹一遍就成了骚扰。故在展示的那一刻即写盘;按钮只负责立刻收起。 */
    try { root.localStorage.setItem(key, "1"); } catch (error) { /* 隐私模式写不进,不影响本次浏览 */ }
    const close = () => { if (box.parentNode) box.parentNode.removeChild(box); };
    button.addEventListener("click", close);
    box.append(text, button);
    doc.body.appendChild(box);
    if (o.autoDismissMs) root.setTimeout(close, o.autoDismissMs);
    return true;
  }

  doc.addEventListener("pointerover", event => {
    const hit = findHit(event.target);
    if (hit) show(hit.host, hit.spec); else hide();
  }, true);
  doc.addEventListener("focusin", event => {
    const hit = findHit(event.target);
    if (hit) show(hit.host, hit.spec); else hide();
  }, true);
  doc.addEventListener("focusout", hide, true);
  doc.addEventListener("keydown", event => { if (event.key === "Escape") hide(); });
  root.addEventListener("scroll", hide, true);
  root.addEventListener("resize", hide);

  root.S3Tooltip = Object.freeze({
    register, sweep, hide, firstVisitHint,
    /* QA 用:逐条报告注册项当前命中几个元素、三段各段是否有文案。 */
    coverage() {
      return registry.map(entry => {
        let count = 0;
        try { count = doc.querySelectorAll(entry.selector).length; } catch (error) { count = -1; }
        return {selector: entry.selector, matched: count,
          has: ["title", "what", "why", "edge"].filter(key => entry.spec[key])};
      });
    },
    activeSpec() { return active ? active.spec : null; },
    registeredCount() { return registry.length; }
  });
})(typeof window !== "undefined" ? window : globalThis,
   typeof document !== "undefined" ? document : null);
