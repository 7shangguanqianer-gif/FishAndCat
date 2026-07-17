# 02_入出闭环.html 建页实现计划(M4b · 去风险交付 · 页体建议用户在场窗口做)

> 状态:**实现计划(非页体)**。经深侦察 s3_ac_runtime.js(1976 行)+ 其冻结原宿主页 archive_候选历史/样张_S3_三方向候选.html(1108 行)+ s3_trace_store.js,结论:**建页可行但高脆性,应在用户在场窗口做(可即时目视迭代)**,而非夜间盲编码——理由见 §1。本计划把契约、配方、风险、待澄清点全部前置,让实际建页降到「照单执行 + 目视校对」。

## 1. 工作量与延后理由(与冻结规格 §6-3「~2000 行级,单独工作窗」一致)

- **运行时非自包含**:`createBrowserRenderer(root)`(runtime:815)引用 `scene/camera/renderer/controls/mast/carrier/RACK/INFEED/OUTFEED/IO/mount/viewportEl/setCamera/resizeScene/…` 约 30 个标识符,**runtime 内零声明**——全部来自原宿主页内联 `<script>`(host:689-1102,684 行场景搭建)。新页要么原样搬这 684 行,要么重写等价全局集。
- **严格加载序 + 数据前置**:`three→OrbitControls→[684行场景脚本]→body(挂载点)→out/s3_trace_manifest.js→out/s1_comparison_evidence.js→s3_trace_store.js→s3_ac_runtime.js(自动 bootstrap)`。`bootstrap()` 首行 `invariant(S3TraceStore && S3_TRACE_MANIFEST)`(runtime:1612),缺任一或顺序错=白屏。
- **崩溃面大**:漏 `#insightStack`/`#viewport`、`#taskline` 无预置 `.kicker` 子、`#railHead` 无 `.matrix` 子、`#cycleReset` 缺失,任一即 TypeError 白屏或 RAF 循环卡死。夜间无用户目视,QA 只能事后发现,返工成本高。
- **结论**:页体在用户在场窗口做(边建边看),本计划已把"看什么、按什么顺序、哪些禁手写"全部固化,建页时间应显著压缩。

## 2. 建页配方(照单执行)

### 2a. 脚本加载顺序(照抄 host:687-688,1103-1106)
```
three.min.js → OrbitControls.js → [内联场景搭建 <script>,原样搬 host:689-1102]
→ …body 静态 HTML(仅 §2c 挂载点)… →
out/s3_trace_manifest.js → out/s1_comparison_evidence.js → src/s3_trace_store.js → src/s3_ac_runtime.js
```
`s3_ac_runtime.js` 必须最后(加载即 bootstrap)。trace 数据经 `<script>` 注入(store:410-472),协议限 `file:` 或同源 loopback(store:200-230)——本地双击开或 QA 的 loopback server 均满足。

### 2b. 运行时**自建、新页禁手写**的 id(createRuntimeDom,runtime:1591-1609)
`#decisionWrap` `#queueCard`(含 #queueStrip/#queueMeta) `#comparisonMini`(含 #comparisonMiniBars/#openComparisonLabMini) `#judgePath`(含 #judgeRoute/#judgeRouteMeta/#judgeAction/#judgeActionMeta/#judgeEvidence/#judgeEvidenceMeta) `#openComparisonLab` `#comparisonLab`(含 #closeComparisonLab/#comparisonScenarioTab/#comparisonModeTab/#comparisonToolbar/#comparisonAutoSummary/#comparisonTable/#comparisonFoot/#comparisonTitle)。
**手写=重复 id,静态那份变死节点误导排查。** 只留空的 `#workHud`/`#insightStack`/`#runtimeActions`(内含真实子 `#traceLoadState`)。

### 2c. 新页**必须预置**的挂载点/控件 id(runtime 只读/绑,不创建)
- 挂载:`#workHud` `#insightStack` `#viewport` `#gl`(3D mount) `#runtimeActions`(含子 `#traceLoadState`) `#runtimeControls` `#traceErrorHost`
- 顶栏控件:`#strategySelect`(seq/near/score/AUTO/awra;awra 单独 optgroup「离线批量参照·非同信息集」)`#tierSelect` `#profileSelect` `#pauseMotion` `#replayTrace` `#resetCamera`(原 id `resetCamera`)`#exp`(导出3D帧)`#playbackSpeed` `#playbackValue`
- 任务卡:`#taskline`(**须预置子 `.kicker`**)`#taskPrimary` `#actionBadge` `#stepIndex` `#stepPurposeText` `#ownerState`
- 顶部标识:`#railHead`(**须预置子 `.matrix`**;本体由场景脚本造)
- cycle 轴:`#phaseSegments` `#phaseTimeScale`(含 #phaseTimeCursor)`#phaseNow` `#phaseClock`
- 实时轴位:`#xValue/#zValue/#forkValue` + `#xFill/#zFill/#forkFill`
- 统计:`#factCycle/#factQueue/#factAlarm` `#traceStats`(取货实测块候选,见 §5-Q1)
- canvas:`#speed` `#slotMap`
- 浮层:`#targetBeacon` `#faultStateBanner` `#sceneDock` `#sceneCaption/#sceneActionText/#sceneCargoMeta/#sceneActionMeta` `#cycleReset`(空遮罩容器,含 `.resetCard`)

### 2d. A 壳 CSS/chrome 复用(仿 01_连续填仓.html)
- `<html data-s3-layout="A">`(由新 interactions.js 设置);复用 01 页 `--rail-w`/`#topbarA`/`#workHud` 栅格/`--topbar-h`/`--axis-h` 变量与 layout-A 作用域样式。
- 新建 `s3_mixed_layout_a_interactions.js`(仿 s3_layout_a_interactions.js 312 行):设 data-s3-layout、cycle 轴节点(0/25/50/75/100)点击暂停到快照、放大 overlay(若复用 2D)、浮层 pop。
- **不动**:样张_S3_三方向候选.html(冻结)、s3_ac_runtime.js/s3_trace_store.js(数据渲染层;仅 §5-Q2 文案若需最小补丁再逐处列账)、trace 五 lane 数据。

## 3. 治理叙事接入(规格 §3 + 侦察修正 §6-1)
- **AUTO 不改名**(侦察证实是 run-start-once 规则路由,决策在上游 trace 生成脚本,runtime:1048-1055 纯展示):下拉话术精确化「规则路由 AUTO(启动时一次选定)」,保留 runtime 既有「启动时一次选定 · SIM」披露。
- comparisonLab(S1 受控对照,144 单元格 10seed×18情景×8模式)入口保留并纳入 QA——兑现「砸掉 #15 并入现有页」。footer 硬编码「S1 与当前 3D 不池化」隔离声明(runtime:1739)保留。
- 口径徽章:sim 标注、「演示补段不计 KPI」、77/0 不在本页宣称(本页 Web sim,不引 PLC)。

## 4. 新 QA `capture_s3_mixed_layout_a_qa.mjs`(仿 layout_a QA 骨架,规格 §4)
视口三档无溢出;五 lane 绑定;AUTO 话术精确化断言(非改名);awra 分组「离线参照·非同信息集」不冒充在线;cycle 轴节点 0/25/50/75/100 快照语义;取货实测块存在且数值来自 trace(可复算);comparisonLab 打开/关闭/inert/两轴切换;禁词(容量书签/智能路由)零命中;cycleReset 遮罩语义;无重复 id(防 §2b 陷阱)。

## 5. 待用户拍板/澄清(建页前须定)

- **Q1 「取货实测块」指哪个**:runtime 无同名 id。最近候选:`#traceStats`(批量真实统计:response_p50/p95、utilization、queue_peak)或 `#axisHud` 实时轴位(单帧瞬时)。规格 §2 说「高频货取货时间实测(从 trace 事件提取)+入出闭环 KPI」——倾向 `#traceStats` 为主 + 补一个「热门件取货均时」派生。**需用户确认口径与取哪些字段**。
- **Q2 AUTO 话术真实性**:「AUTO 是确定性规则阈值」硬编码在 runtime:1739/1058;其真实性依赖上游 trace 生成脚本(本侦察范围外)。若报告/页面要如实背书,需追溯生成脚本确认,不能只凭 runtime。
- **Q3 视觉聚焦边界**:runtime 硬编码 20×20 货架 + 100 周期存取,`drawSlotMap`/`validateVisualTopology`/`validateInventoryRows`(120 行)/`groups.length===cycles*7` 全是强 invariant。02 页想突出「入出口」只能靠 CSS/相机预设视觉裁切,**不能**从数据/渲染层摘货架。确认可接受。
- **Q4 684 行场景脚本搬运方式**:原样内联搬运(最稳,但新页体积大)vs 抽成共享 `s3_ac_scene.js`(减重复,但需验证 runtime 自由变量作用域仍可见——非模块脚本顶层 const 共享全局词法环境,抽文件需保持非 module 且顺序在 runtime 前)。建议原样内联(低风险),体积代价可接受。

## 6. 证据/参考行号锚
侦察全表见本次 overnight 会话记录;关键锚:runtime 自建 DOM 1591-1609、bootstrap 1611-1963、invariant 1612、AUTO 展示 1048-1055、comparisonLab 1675-1740、drawSlotMap 1150-1183、cycleReset 1478-1479 / host:682、加载序 host:687-1106。
