# 会话断点 · 2026-07-19d(顶栏+dock 结构级重排 · compact 前落盘)

> 本文 = compact 后的**唯一恢复入口**。读完 §0/§1/§2 即可开工,其余按需查。

## 0. 用户原话逐字引用(防转述偏移第一防线)

> 「**绿框和蓝框的问题一点都没有解决!全部思考并且重新解决,你一个截图对你的改进验收.**」
> 「我希望你 compact 后**修复完所有问题,然后继续推进任务列表**」
> 「之前的 compact 造成了多次误读,这次你要好好反思做好措施」

绿框 = 顶栏(topbarA);蓝框 = dock 底带左中段(当前作业 + 双轴速度 + 实时轴位)。
验收方式 = **改完自己截图(1600×900)自查,贴图交用户验收**——不是口头汇报。

## 1. 反思:为什么两轮修复被判「一点都没有解决」(模式性错误)

两轮都做的是**参数级微调**(色值/padding/列宽/边框/高度统一),但用户批评「散漫/老旧/看不出来」
指向的是**结构级问题**(信息编排、视觉分组、组件形态)。这与 0719 早间「重构隔靴搔痒」是**同一个错误
第二次发生**。**措施(铁律)**:凡用户批评含「散/乱/老旧/看不出/排版」字样 → 一律做**结构重排**
(改 DOM 结构/信息编排/组件形态),**禁止只调 CSS 参数交差**;改完必须 1600×900 截图自查
「假如我是评委第一眼看」再交付。

## 2. 唯一下一步:顶栏 + dock 结构级重排(方案已想透,直接实施)

### 2a. dock 遥测块重做(蓝框核心)

现状病:双轴速度(canvas 两根条,0.00 时全空)+ 实时轴位(三行,轨道极淡点标太小,X/Z/F
字母看不清)= 两套系统、四列碎片、大量空白。

**方案:合并为单块「运动遥测」三行网格,每轴一行 = 轴名 | 位置点标轨道 | 位置值 | 速度值**
1. html(≈837 行)`#axisHud` 内三行改四列:
   `<div class="axis"><span>X</span><i id="xFill"></i><span id="xValue">0.00 m</span><span id="xVel">0.00 m/s</span></div>`
   (Z 同;F 行速度格留空 `<span></span>`)。标题 `<b>` 改「运动遥测 · X/Z 位置+速度」。
2. CSS(A 壳白化段):`#axisHud .axis{grid-template-columns:14px 1fr 54px 58px}`;
   轴名 span 加粗深色 9px;轨道加高 6px + 刻度(::before 在 50% 处 1px 竖线);点标加大
   `width:7px;height:14px;top:-4px`;数字列 Consolas 右对齐;xVel 列灰色(次要)。
3. runtime `renderFrame`(≈1706 行 xValue 写入处)加:
   `byId("xVel").textContent = `${Math.abs(frame.machine.vx).toFixed(2)} m/s`;`(zVel 同;faulted 时已是 0 ✓)。
4. **drawSpeed canvas 退役**:`#liveChartWrap{display:none}`(canvas 没了 drawSpeed 里
   canvasContext 返回 null 自动跳过,无 crash——已核实该函数首行判空);`#sceneTelemetry`
   改单列 `grid-template-columns:1fr`。dock 三列宽随之再平衡(遥测块可收窄)。
5. 「当前作业」块:meta 行文本截断(「…」)修——去掉尾部「交接展示 1.9 s·…」段或允许两行
   (`white-space:normal;line-height:1.35;max-height:2.7em;overflow:hidden`);图例条(入库/空载/
   出库/预占)缩小移到块底部独立行,与 meta 分离。

### 2b. 顶栏重做(绿框核心)

现状病:三个「label+select」裸珠子散排 + 中间大空白 + 五个按钮同权重混排 + 组感为零。

**方案:分组容器化(两组一徽章)**
1. interactions(搬运段 ≈30-45 行)建 `<div class="scenarioGroup">` 容器:把三个 label(算法/
   拟真档/货物画像)从 runtimeControls **移入** scenarioGroup,scenarioGroup 插在 runtimeControls
   前(或作为其第一子);再建 `<div class="actionGroup">` 概念上用 CSS 即可(runtimeActions 已是容器)。
2. CSS:
   - `.scenarioGroup{display:flex;align-items:center;gap:0;background:#f2f4f6;padding:3px 4px;border:1px solid #dde3e8}`
     内部 label 之间加 1px 分隔(`label+label{border-left:1px solid #dde3e8;padding-left:8px;margin-left:8px}`),
     select 去独立边框(`border:0;background:transparent`)——三选择器融为一个「情景配置」单元。
   - 按钮分两组:播放组(继续/从头回放)与证据组(导出3D帧/本屏证据/对照证据)之间加
     `#exp{margin-left:10px;border-left:...}` 或给「继续」主按钮强调态(深蓝实底白字:
     `#pauseMotion{background:#17365d;color:#fff;border-color:#17365d}`),其余次级白底。
   - 「已校验」绿徽章保持;PLC 徽章保持品牌旁。
3. 中间空白:scenarioGroup 组化后空白变「呼吸区」;若仍空可把 PLC 徽章移到空白区中部
   (`margin-left:auto` 给 scenarioGroup 后元素)——实施时看截图定。

### 2c. 验收(强制流程)

改完 → QA 8/8 → **1600×900 截图(常态帧 + seekFault 帧)自查**:①顶栏是否有明确视觉分组
②遥测三行是否一眼读出位置+速度③无截断文本④无page error → 贴图路径交用户验收。
判据不过就继续改,**不许口头交差**。

## 3. 已完成资产(本轮 0719 晚,全部有效勿重做)

| 项 | commit |
|---|---|
| CSS 根治 P1→P3(!important 31→11)+ A 壳转正 | `38955f8`…`0ea684c` |
| 功能批次甲版(删减四项+M1-M4+N1-N4)+2D 配色①收敛+b 收敛 | `bc3f8eb`/`7e63828`/`c7a364a` |
| 视觉六修(速度清零/七步 9.7+600s/sparkline 页错/2D 足迹/标题去重/暂停贴条) | `421aa96` |
| 3D 热度前罩(.78/depthWrite:false/-.40)+dock 白化 | `2bc0d8e`/`ac6ca7c` |
| tooltip fixed 脱裁+faultBanner 移 3D 区+载货台故障红球+轴位点标机制+顶栏徽章语义 | `d10e7e1` |
| 调研落盘(5 题证据分级+占位符三连事故) | `docs/视觉技术调研_0719.md` |

d10e7e1 的点标/徽章**机制正确但视觉强度不够**——2a/2b 在其上做结构级,不是推翻。

## 4. 修复完成后的任务队列(用户令「继续推进任务列表」)

1. M5 三标记(任务 b 收尾:取货 lane/交织腿标记/省一趟角标,3D 内容层)——#34 R2 最后一块
2. 01 页 G1-G4(指纹/差值CI/sparkline 口径核/PLC 徽章)+ P5 CSS 治疗(905 行/29 important,QA46 兜底)
3. 提交包副本换新(R5 时一并;out/s3_mixed_dispatch_sweep.js 等新静态依赖登记)
4. 任务 c(能力对比总览)/ d(#42 stale 根治,已授权)/ e(R3 录屏/R4 报告/R5 导览)
5. 待用户拍板项勿动:#25(1_/2_ 收编)、#38-41

## 5. 红线与工装(不变)

- 不碰 sim/*.py·trace·manifest·invariant 链(validateVisualTopology)·加载序;不碰 1_/2_ 用户文档;
  黄牌 #targetBeacon 永不再引入(DOM+display:none 保护令不可删);#taskline/#factCycle 等
  **runtime 每帧写入元素只能隐藏不能删 DOM**;git add 只点名+中文 commit+Co-Authored-By: Claude Fable 5;
  不编数字;扇出 agent 一律 sonnet/medium;workflow 返回值必核。
- deep-research synthesize 占位符=机制坑:**不重跑,直接读 journal.jsonl claims 主会话综合**;
  resume 时 args 必须逐字节一致(否则全量重烧,0719 实测 4.4M)。
- 工装(scratchpad):QA=`node tools/capture_s3_mixed_layout_a_qa.mjs`(8/8);视觉扫描
  visualscan.mjs/顶栏排查 topbaraudit.mjs;probe.mjs;01 QA=capture_s3_layout_a_qa.mjs(46/46,
  快照制新静态依赖须登记白名单+MIME)。02 QA 就绪判据 `__S3_QA` 且 `!snapshot().loading`。
- 机器部件(mast/carrier/machineParts)= html 母版脚本全局变量,runtime 作用域链可达。
