/* S3 行程速度剖面图公共模块(0728 #23:01 运动表现力提升 + 速度口径显眼披露)
 *
 * 用户拍板:「剖面图 + 场景分段路径」+「同步,抽进公共模块」。
 *
 * 要解决的问题(实测,非推测):梯形加减速双轴插补是两页共同的运动学内核,但在界面上
 * 几乎不可见——唯一活着的表达是底部约 8.5px 的 xVel/zVel 数字与 28px 宽的填充条;
 * 两页曾各有一个「双轴速度」面板(#liveChartWrap),在一屏返工时被 display:none 隐藏,
 * 其绘制函数从此每帧画进一张 0×0 的画布,是彻底的空转。本模块取代它。
 *
 * 与旧 drawSpeed 的本质差别:旧版画的是**当前时刻的两根速度条**(标量),看不出模型;
 * 本模块画的是**整段行程的速度-时间曲线**(函数),梯形的三段一眼可辨,游标标出"现在走到
 * 哪儿"。同样一份数据,后者才回答得了「加速多久、何时匀速、何时开始减速、两轴谁先到位」。
 *
 * 三个设计决策与理由:
 *  ① 横轴统一取**慢轴总时长**,不给两轴各画各的时间轴。双轴同步的物理事实就是"慢轴决定
 *     节拍"(S3Motion.point 里 total = max(tx, tz)),快轴先到位后速度归零、曲线贴地——
 *     这段贴地平台正是「独立到位」的可视证据,拆成两张图反而看不见。
 *  ② 背景三段分区按**主导轴(慢轴)**划分。两轴的加速/匀速/减速边界本就不同,若两套分区
 *     同时铺底会互相打架;标注慢轴、另一轴以曲线形态自证,信息密度最高且不产生歧义。
 *  ③ **不重复显示实时速度数字**。轴状态行(#axisHud 的 xVel/zVel)已是该数字的主位,
 *     这里只画形态与常量参数(vmax/accel/折减系数),遵守「同一数字只许一个主位」。
 *
 * 口径红线:曲线一律由 S3Motion 采样得出,本文件**不含任何独立的运动学实现**——避免出现
 * 第二套口径。任一页传入的 vmax/accel/motion/ladenFactor 都按该页 sim 数据原样传递,
 * 两页真实存在的口径差异(01 含满载升降折减 ×0.8、02 另有 constant_speed 匀速档)照实画出,
 * 不在这里"统一"。tools/test_s3_motion_parity.mjs 的反向断言守着这条线。
 *
 * 载入契约:classic script,挂 window.S3SpeedProfile,须在 s3_motion.js 之后、各页 runtime 之前。
 */
"use strict";
(function (root) {
  const MOTION = () => root.S3Motion;

  /* 配色沿用两页既有的速度语言(旧 drawSpeed 同值),不新造颜色:X=ABB 红,Z=紫。 */
  const PALETTE = Object.freeze({
    x: "#ff000f", z: "#7b2cbf",
    axis: "#9aa4ac", grid: "#e4e9ec", ink: "#17202b", muted: "#6a747d",
    accelBand: "rgba(255,0,15,.055)", cruiseBand: "rgba(23,54,93,.05)", decelBand: "rgba(123,44,191,.055)",
    cursor: "#17365d", plateau: "#cfd6db"
  });

  const clamp = (value, low, high) => value < low ? low : value > high ? high : value;

  /* 梯形的三段边界。匀速档(constant_speed)没有加减速段,退化为整段匀速——如实反映,
     不硬凑三段。distance 为 0 时整段为零长,调用方按"无行程"处理。 */
  function segmentsOf(distance, vmax, accel, motion) {
    const S3 = MOTION();
    const total = S3.axisTime(distance, vmax, accel, motion);
    if (!(total > 0)) return {total: 0, ramp: 0, cruiseStart: 0, cruiseEnd: 0, peak: 0, triangular: false, constant: false};
    if (motion === S3.CONSTANT) {
      return {total, ramp: 0, cruiseStart: 0, cruiseEnd: total, peak: vmax, triangular: false, constant: true};
    }
    /* 行程不足以加到 vmax 时,梯形退化为三角形(无匀速平台)——峰值只到 accel·√(d/accel)。 */
    const triangular = distance < vmax * vmax / accel;
    const peak = triangular ? accel * Math.sqrt(distance / accel) : vmax;
    const ramp = peak / accel;
    return {total, ramp, cruiseStart: ramp, cruiseEnd: Math.max(ramp, total - ramp), peak, triangular, constant: false};
  }

  function create(canvas, options) {
    const o = options || {};
    let last = null;

    /* 与两页既有 canvasSurface 同法处理 DPR;尺寸不足时直接放弃本帧(不报错、不空转出脏图)。 */
    function surface() {
      const rect = canvas.getBoundingClientRect();
      if (rect.width < 2 || rect.height < 2) return null;
      const ratio = Math.min(root.devicePixelRatio || 1, 2);
      const width = Math.round(rect.width * ratio), height = Math.round(rect.height * ratio);
      if (canvas.width !== width || canvas.height !== height) { canvas.width = width; canvas.height = height; }
      const context = canvas.getContext("2d");
      context.setTransform(ratio, 0, 0, ratio, 0, 0);
      context.clearRect(0, 0, rect.width, rect.height);
      return {g: context, w: rect.width, h: rect.height};
    }

    /* spec = {axes:[{key,label,color,distance,vmax,accel,motion}], time, caption, note}
       time 为本段已走时间(秒),超出总时长按到位处理。 */
    function update(spec) {
      const s = surface();
      if (!s) { last = null; return null; }
      const {g, w, h} = s;
      const S3 = MOTION();
      const axes = (spec.axes || []).map(axis => Object.assign({}, axis, {
        seg: segmentsOf(axis.distance, axis.vmax, axis.accel, axis.motion)
      }));
      const total = axes.reduce((max, axis) => Math.max(max, axis.seg.total), 0);
      /* 主导轴 = 决定节拍的慢轴;并列时取先声明者(01/02 都把 X 放前,行为稳定可复现)。 */
      const lead = axes.reduce((best, axis) => (best && best.seg.total >= axis.seg.total ? best : axis), null);

      /* ---- 布局:示波器式双泳道,共享横轴(时间),各轴独立纵轴 ----
         为什么不共用一根绝对速度纵轴:本项目 VX=2.0 而 VZ=0.5(满载还 ×0.8),量级差 4~5 倍,
         同轴线性缩放会把升降轴压成一条贴底的线——而实测多数货位行程恰恰**由升降轴主导**
         (「等时区现象」,本页既有结论),主导轴的梯形反倒看不见,图就白画了。分泳道后两轴
         形态都可读,时间轴仍对齐,"谁先到位"照样一眼可见。绝对量级由每泳道右端的额定速度
         标注与卡片内参数注交代,信息没有丢。 */
      const padL = 15, padR = 8, padT = 11, padB = 10, laneGap = 5;
      const plotW = Math.max(1, w - padL - padR);
      const laneH = Math.max(8, (h - padT - padB - laneGap * (axes.length - 1)) / Math.max(1, axes.length));
      const tx = t => padL + (total > 0 ? clamp(t / total, 0, 1) : 0) * plotW;
      const laneTop = index => padT + index * (laneH + laneGap);
      /* 纵轴留 18% 余量:跑满额定速度时曲线会顶到 vmax 线,若那条线就是泳道顶边,平台会
         直接压住左上角的额定速度标注(实测 Z 轴满速时 "0.40" 被曲线穿过)。留白后
         "曲线触到虚线顶线 = 跑满额定" 的读法不变,标注也不再被压。 */
      const HEADROOM = 1.42;
      const vy = (v, axis, index) => laneTop(index) + laneH - clamp(v / Math.max(axis.vmax * HEADROOM, 1e-6), 0, 1) * laneH;

      const SAMPLES = 96;
      const marks = [];
      axes.forEach((axis, index) => {
        const top = laneTop(index), bottom = top + laneH;
        const seg = axis.seg;

        /* 背景三段带:分泳道后每轴都能标**自己的**加速/匀速/减速,不再互相打架。 */
        if (seg.total > 0) {
          const bands = seg.constant
            ? [[0, seg.total, PALETTE.cruiseBand]]
            : [[0, seg.cruiseStart, PALETTE.accelBand],
               [seg.cruiseStart, seg.cruiseEnd, PALETTE.cruiseBand],
               [seg.cruiseEnd, seg.total, PALETTE.decelBand]];
          bands.forEach(([t0, t1, fill]) => {
            if (t1 - t0 <= 1e-9) return;
            g.fillStyle = fill; g.fillRect(tx(t0), top, Math.max(1, tx(t1) - tx(t0)), laneH);
          });
        }
        /* 额定速度顶线画在 vmax 处(不是泳道顶边):曲线触到它就是"跑满额定"。 */
        g.strokeStyle = PALETTE.grid; g.lineWidth = 1;
        g.save(); g.setLineDash([2, 3]);
        const capY = Math.round(vy(axis.vmax, axis, index)) + .5;
        g.beginPath(); g.moveTo(padL, capY); g.lineTo(padL + plotW, capY); g.stroke();
        g.restore();
        g.strokeStyle = PALETTE.axis;
        g.beginPath(); g.moveTo(padL + .5, top); g.lineTo(padL + .5, bottom + .5); g.lineTo(padL + plotW, bottom + .5); g.stroke();

        /* 曲线:一律 S3Motion 采样,不自算。**只画到本轴自己的 total 为止**——若一路采样到
           全局 total,本轴到位后会沿 0 线拖一条实线到右端,再叠上灰虚线就成了"红色虚线",
           把"已到位"误读成"仍在以某种方式运动"(首版实测缺陷)。到位之后交给下面的虚线平台。 */
        if (seg.total > 0) {
          const end = Math.min(seg.total, total);
          g.strokeStyle = axis.color; g.lineWidth = 1.5; g.beginPath();
          for (let i = 0; i <= SAMPLES; i += 1) {
            const t = end * i / SAMPLES;
            const v = Math.abs(S3.axisVelocity(t, axis.distance, axis.vmax, axis.accel, axis.motion));
            const px = tx(t), py = vy(v, axis, index);
            if (i === 0) g.moveTo(px, py); else g.lineTo(px, py);
          }
          g.stroke();
        }
        /* 该轴先到位后的贴地段画虚线,明示"已到位、仍在等慢轴"——双轴独立到位的可视证据。 */
        if (seg.total < total - 1e-9) {
          g.save(); g.setLineDash([3, 3]); g.strokeStyle = PALETTE.plateau; g.lineWidth = 1.2;
          g.beginPath(); g.moveTo(tx(Math.max(seg.total, 0)), vy(0, axis, index)); g.lineTo(tx(total), vy(0, axis, index)); g.stroke(); g.restore();
          g.font = "6.5px Consolas,monospace"; g.fillStyle = PALETTE.muted; g.textAlign = "right";
          g.fillText("已到位", padL + plotW - 1, bottom - 4); g.textAlign = "left";
        }

        /* 轴名(泳道左外侧)与额定速度(泳道内右上角)。 */
        g.font = "700 7px Consolas,monospace"; g.fillStyle = axis.color; g.textAlign = "right";
        g.fillText(axis.key.toUpperCase(), padL - 2, top + 7); g.textAlign = "left";
        g.font = "6.5px Consolas,monospace"; g.fillStyle = PALETTE.muted;
        g.fillText(`${axis.vmax.toFixed(2)}`, padL + 3, top + 7);

        /* 当前速度点。 */
        const now = clamp(Number(spec.time) || 0, 0, total);
        const v = seg.total > 0 && now <= seg.total
          ? Math.abs(S3.axisVelocity(now, axis.distance, axis.vmax, axis.accel, axis.motion)) : 0;
        g.fillStyle = axis.color;
        g.beginPath(); g.arc(tx(now), vy(v, axis, index), 2.2, 0, Math.PI * 2); g.fill();
        marks.push({key: axis.key, velocity: v});
      });

      /* ---- 游标:贯穿全部泳道,时间对齐 ---- */
      const now = clamp(Number(spec.time) || 0, 0, total);
      const cursorX = Math.round(tx(now)) + .5;
      g.strokeStyle = PALETTE.cursor; g.lineWidth = 1;
      g.beginPath(); g.moveTo(cursorX, padT); g.lineTo(cursorX, laneTop(axes.length - 1) + laneH); g.stroke();

      /* ---- 段标签:标主导轴(它决定节拍),画在最后一条泳道下方,窄段不画 ---- */
      if (lead && lead.seg.total > 0) {
        const seg = lead.seg, baseY = laneTop(axes.length - 1) + laneH + 8;
        g.font = "7px Consolas,monospace"; g.fillStyle = PALETTE.muted; g.textAlign = "center";
        const labels = seg.constant
          ? [["匀速", 0, seg.total]]
          : [["加速", 0, seg.cruiseStart], [seg.triangular ? "" : "匀速", seg.cruiseStart, seg.cruiseEnd], ["减速", seg.cruiseEnd, seg.total]];
        labels.forEach(([text, t0, t1]) => {
          if (!text || tx(t1) - tx(t0) < 24) return;
          g.fillText(text, (tx(t0) + tx(t1)) / 2, baseY);
        });
        g.textAlign = "left";
        /* 「谁定节拍」放左上角空位,不放底部——底部要留给三段标签,挤在一起会互相压字。 */
        g.font = "6.5px Consolas,monospace"; g.fillStyle = PALETTE.muted;
        g.fillText(`${lead.key.toUpperCase()} 轴定节拍 ${total.toFixed(1)} s`, padL, 7);
      }

      /* ---- 参数注(常量口径,非实时值,不与轴状态行重复) ---- */
      if (spec.note) {
        g.font = "6.5px Consolas,monospace"; g.fillStyle = PALETTE.muted; g.textAlign = "right";
        g.fillText(spec.note, padL + plotW, 7); g.textAlign = "left";
      }

      last = {
        total: Number(total.toFixed(6)), time: Number(now.toFixed(6)),
        leadKey: lead ? lead.key : null,
        axes: axes.map(axis => ({key: axis.key, distance: axis.distance, vmax: axis.vmax, accel: axis.accel,
          motion: axis.motion || "trapezoid_accel", total: Number(axis.seg.total.toFixed(6)),
          peak: Number(axis.seg.peak.toFixed(6)), triangular: axis.seg.triangular, constant: axis.seg.constant,
          cruiseStart: Number(axis.seg.cruiseStart.toFixed(6)), cruiseEnd: Number(axis.seg.cruiseEnd.toFixed(6)),
          arrivedEarly: axis.seg.total < total - 1e-9})),
        marks: marks.map(mark => ({key: mark.key, velocity: Number(mark.velocity.toFixed(6))})),
        caption: spec.caption || null, note: spec.note || null
      };
      return last;
    }

    function clear() { const s = surface(); last = null; return !!s; }

    return {update, clear, audit() { return last; }, palette: PALETTE};
  }

  /* 卡片自带样式:与悬浮气泡同一套白底 + ABB 红左条工程风,不新造视觉语言。
     落点是**三维视口内的浮层**而不是底部 dock——实测 dock 高 110px、轴状态已占 74px,
     剩余 36px 放不下一张读得出梯形的图;而剖面图与场景内分段路径本就要互相印证,
     同框看才有意义。position:absolute 相对视口定位,不参与 dock 的 grid 争位。 */
  function injectStyle(doc) {
    if (doc.getElementById("s3SpeedProfileStyle")) return;
    const style = doc.createElement("style");
    style.id = "s3SpeedProfileStyle";
    style.textContent = `
.s3SpeedProfile{position:absolute;z-index:6;width:238px;background:rgba(255,255,255,.94);
  border:1px solid #c9d0d6;border-left:3px solid #ff000f;border-radius:3px;
  box-shadow:0 4px 16px rgba(23,32,43,.13);padding:5px 7px 4px;box-sizing:border-box;pointer-events:auto}
.s3SpeedProfile .spHead{display:flex;justify-content:space-between;align-items:baseline;gap:8px}
.s3SpeedProfile .spHead b{font:700 9.5px/1.25 "Microsoft YaHei",sans-serif;color:#15202b;white-space:nowrap}
.s3SpeedProfile .spHead span{font:400 7px/1.25 Consolas,monospace;color:#7c868e;white-space:nowrap;
  overflow:hidden;text-overflow:ellipsis}
.s3SpeedProfile canvas{display:block;width:100%;height:94px;margin-top:5px}
.s3SpeedProfile .spFoot{margin-top:3px;padding-top:3px;border-top:1px dashed #dfe4e7;
  font:400 7px/1.4 "Microsoft YaHei",sans-serif;color:#6a747d}
.s3SpeedProfile .spKey{display:flex;gap:9px;margin-top:1px;font:400 7px/1.3 Consolas,monospace;color:#6a747d}
.s3SpeedProfile .spKey i{display:inline-block;width:9px;height:2px;vertical-align:middle;margin-right:3px}
@media(max-width:1200px){.s3SpeedProfile{width:198px}.s3SpeedProfile canvas{height:78px}}`;
    doc.head.appendChild(style);
  }

  /* options = {host, doc, id, title, hint, keys:[{label,color}], place:{top,right,bottom,left}} */
  function mount(options) {
    const o = options || {}, doc = o.doc || root.document, host = o.host;
    if (!host) return null;
    injectStyle(doc);
    const card = doc.createElement("div");
    card.className = "s3SpeedProfile";
    card.id = o.id || "s3SpeedProfile";
    card.setAttribute("aria-label", o.title || "行程速度剖面");
    const head = doc.createElement("div"); head.className = "spHead";
    head.innerHTML = `<b></b><span></span>`;
    head.querySelector("b").textContent = o.title || "行程速度剖面";
    head.querySelector("span").textContent = o.hint || "";
    const canvas = doc.createElement("canvas");
    card.append(head, canvas);
    /* 0728 用户拍板「两页剖面图加对页速度差异一句」:两页升降轴的额定速度标注(01=0.40、
       02=0.50)本身就是「同倍速下两页速度显示不同」的直接对照,但只有对照过两页才看得出来。
       在卡片底部写死一句指向对页的说明,让评委不悬停、不切页也能当场读懂那个差异从哪来。 */
    let foot = null;
    if (o.foot) {
      foot = doc.createElement("div"); foot.className = "spFoot";
      foot.textContent = o.foot; card.appendChild(foot);
    }
    if (o.keys && o.keys.length) {
      const key = doc.createElement("div"); key.className = "spKey";
      o.keys.forEach(item => {
        const span = doc.createElement("span");
        span.innerHTML = `<i style="background:${item.color}"></i>`;
        span.append(doc.createTextNode(item.label));
        key.appendChild(span);
      });
      card.appendChild(key);
    }
    const place = o.place || {top: "10px", right: "10px"};
    Object.keys(place).forEach(side => { card.style[side] = place[side]; });
    host.appendChild(card);
    const controller = create(canvas, o);
    return Object.assign({}, controller, {
      card, canvas,
      setHint(text) { head.querySelector("span").textContent = text; },
      setVisible(on) { card.style.display = on ? "" : "none"; }
    });
  }

  root.S3SpeedProfile = Object.freeze({create, mount, segmentsOf, PALETTE});
})(typeof window !== "undefined" ? window : globalThis);
