# 0716 S3 冻结与 Claude Code 接管完整回执

## 结论

S3 当前实现已按用户指令冻结。三份 `v7` 版式候选各通过 20/20 技术 QA，但**全部未获用户信息架构/视觉批准，不得作为定稿或继续微调**。正式页 `l4_showcase/src/样张_S3定稿.html` 未覆盖，SHA256 仍为：

`b59954cb21ca2959886add1d28cb1a9ce32684bd76c5ff051744762b9a92bedb`

完整、可续接的唯一主记录：

`.claude/handoffs/2026-07-16-080158-s3-0716-freeze-and-claude-code-takeover.md`

## 用户最新裁决

1. “七步在做什么”不应常驻占据面板，应在鼠标移到具体阶段节点时按需显示。
2. “容量书签”不是合适的学术名称，且在页面多处重复；需要重做术语和唯一信息层级。
3. Codex 的流程错误是未经用户确认宏观方案就直接编码。
4. 后续 Claude Code 必须先给用户看大体方案，用户确认后再写冻结规格；第二次确认前仍不得编码。

## 本轮查明的回退 bug

不是浏览器缓存，也不是 Three.js 状态凭空丢失：

- 成熟母版同时含顶部当前作业摘要和底部当前作业 dock；
- 增量候选只叠加 fill 阶段导航，却仍运行旧 mixed IN/OUT trace；
- 旧 QA 只验布局、控件和滚动，没有断言“当前作业事实只能有一份”，也没有断言 2D/3D/目标/随载货/阶段节点必须同 event id；
- 因此自动测试绿，但红框信息重复、绿框状态不对等仍被带回。

当前技术修复已让顶部旧作业源隐藏，底部 dock 唯一；同一 `activeFrame` 同时驱动 2D、3D、目标、随载货、占用和文字。

## 已完成技术事实

- Active release：`d75a06b085f9b1aef9ed`。
- 20×20：133 个不可管理预占格 + 267 件管理货 = 400 总占用。
- 三个在线 lane：SEQ / NEAR / SCORE，各 267 件；AUTO 在当前偏斜情景启动时映射 SCORE。
- 前端 bundle 10/10 PASS；payload SHA=`07e039c5...b55d8`，file SHA=`9b8c9ae7...addee`。
- release 回归 8/8 PASS，最近一次 538.164 s。
- SCORE 显示最多 Top3 和真实四分项；SEQ/NEAR 不伪造 score。
- 稳定与能耗代理共用“载重×层高”原始因子，仅权重不同，现已强制解释。
- 原始 trace 是 4 阶段；7 步仅为按几何/货叉阈值拆分的展示步骤。801 事件、5607 展示步，不冒充 5607 个原生时间戳。
- 同侧并行双链与货架成 T 形；顶视 QA 覆盖 1280/1600/1920。
- QA 快照包含 UI 资产、pointer、registry、manifest、三份 audit；只称本地哈希锁定可复现快照，不称签名或抗篡改。

## QA 失败演进（必须保留）

- `v4`：自动 20/20，但人工截图发现地图越出 1280×720。根因是 `overflow:hidden` 让滚动指标假绿。
- `v5`：加入每个 HUD 子元素真实矩形断言后，方案 2 正确 FAIL 19/20。
- `v6`：修复裁切。
- `v7`：三版各 20/20；1280 地图边长分别为 115.6 / 115.6 / 86.7 px。
- 用户随后否决整个信息架构，因此 v7 仍是 NO-GO。自动 PASS 不能覆盖用户验收。

## 当前冻结文件

- `l4_showcase/src/样张_S3_fill恢复候选.html`
- `l4_showcase/src/s3_fill_candidate_runtime.js`
- `l4_showcase/src/s3_fill_store.js`
- `l4_showcase/src/样张_S3_版式候选_1_均衡双栏.html`
- `l4_showcase/src/样张_S3_版式候选_2_地图主证.html`
- `l4_showcase/src/样张_S3_版式候选_3_流程主证.html`
- `l4_showcase/tools/capture_s3_fill_candidate_qa.mjs`
- `l4_showcase/tools/build_s3_layout_review_candidates.py`

最新技术证据：`l4_showcase/out/s3_layout_reviews_0716_v7/`。旧 v1—v6 仅作失败演进证据。

## Claude Code 的第一阶段任务

只读恢复后，先给用户 2—3 套宏观信息架构方案，不改 HTML。每套必须回答：

1. 原“容量书签”改叫什么，页面只出现在哪一处；
2. 七步说明如何由具体阶段节点 hover/focus/点击渐进显示；
3. 当前作业事实在哪一处唯一显示；
4. 2D、3D、算法 Top3、统计数据的主次顺序；
5. 哪些现有信息删除，哪些折叠；
6. 1280×720 与 1600×900 的一屏线框如何不同。

用户选定方案后，Claude Code 先写一页冻结规格并再次请求确认；二次确认后才允许编码。

## 边界

- 不开 AB，不跑 `tools/ab_scripting`，不启动 Factory I/O，不做 Git 写。
- 不覆盖正式页。
- 不把 fill-only SIM 写成出库闭环、PLC 证据或 Factory I/O 连续运行。
- 不把 267 写成仓库总容量；不把 7 展示步写成 7 个原生时段；不把本地 hash 写成签名。

Claude Code 可粘贴提示词：`_通信/codex_out/0716_ClaudeCode接管提示词_S3冻结态.md`。

