# 给 Claude Code：同步 Codex 的 S3 终验、重构前研究与下一阶段计划

> 0716 研究更新：本提示词已加入 Task17 封账后的三路独立复核和官方调研。以下“研究已完成”的新事实 supersede 文中早期“尚待调研”状态，但不覆盖 Task17 的技术 QA 证据。

请进入 `F:\abb_wh_work`，只读完成一次状态同步，不要立即修改页面、正式版、canonical、AB、Factory I/O 或 Git。

按顺序完整阅读：

1. `.claude/handoffs/2026-07-16-014130-s3-task17-and-next-design-research.md`
2. `_通信/codex_out/0715_S3_Task17真实时序_货位图_双链与连续性终验回执.md`
3. `research/0716/S3重构前算法与HMI调研_0716.md`
4. `research/0716/sources.jsonl`
5. `research/0716/evidence.jsonl`
6. `research/0716/claims.jsonl`
7. `research/0716/run_manifest.json`
8. `_通信/codex_out/0716_S3重构前算法与HMI调研回执.md`
9. `l4_showcase/out/s3_6h_qa_0715/task17_queue_static_v5/capture_manifest.json`
10. `l4_showcase/src/样张_S3_三方向候选.html`
11. `l4_showcase/src/s3_ac_runtime.js`
12. `l4_showcase/tools/test_s3_runtime_contract.mjs`
13. `l4_showcase/tools/capture_s3_task12_qa.mjs`

同步时请特别接受并保留以下事实：

- 正式版 `l4_showcase/src/样张_S3定稿.html` 未改；当前工作对象只是候选版。
- 最终证据为 schema v9 manifest：30/30 Node、84/84 截图、6300/6300 帧、19/19 顶层 checks 全真。
- 首段 200s+ 是静态“入场前排队”，不是输送耗时；最终浏览器证据 `queueSamples=624`、`queueDisplacement=0`。
- 完整 `Entry→Load→Transfer` 由不计 SIM/KPI 的 `CARRIER_IN` 展示补段承担。
- 133 个预占体逐 instance matrix 审计齐平；不是只看聚合 bbox。
- 碰撞结论只覆盖 `active/queue cargo vs station solids / cargo each other / floor`，不得写成全场景装配无碰撞。
- 同一名 gpt-5.6-sol 独立审查者两次 REJECT 后第三次 ACCEPT，无 P0/P1/P2；两次拒绝和全部失败目录必须保留，不能只摘最终绿灯。
- 当前四个候选源文件 SHA256 以 handoff 的 `Current SHA256` 表为准。
- 技术 QA 的 PASS 与新增展示 NO-GO 必须并列保留：前者证明自有契约下的几何/性能，后者证明契约越过了项目证据边界。
- 20×20 是逻辑仓位 SIM；Factory I/O 当前只证明 54 格物理 I/O/时序，400 格物理方案 No-Go。
- 页面中的 `SCANNED / EXIT_MASK / CONSUMED` 不是本地 FIO 已验证物理工位；不得继续实体化为真实设备链。
- AWRA-LS 与 SCORE 共用评分函数；AWRA-LS 的增量是批次排序与局部搜索。当前稳定项与能耗项代数相同。
- 现有 trace 没有逐候选分数；任何候选 score、分项贡献或排名 UI 都必须先扩展 sim 导出。
- AUTO 是 run-start-once 规则选路，不是在线学习或逐货切换；当前九条 AUTO 回放全是 `TOB→SCORE`。
- S1 的 18×8×10-seed 统计证据与 S3 的 45 条单-seed代表回放不可合并、相减或共同排名。
- 三入口推荐结构为：预设情景主入口、规则推荐+八算法对照次入口、单件自定义独立沙盒；单件沙盒不得继承聚合 KPI。
- Tier 是拟真假设层，不是算法推荐档位。

研究阶段已经完成；下一阶段已经锁定流程，但尚未拍板具体设计：

1. Codex 与用户进行 3 轮 × 4 问，共 12 问；每轮等待用户回答。
2. 三轮全部锁定后，Codex 只产出 5 套差异显著的设计规格，覆盖信息架构、逻辑SIM/FIO分层、货架、堆垛机、入/出库链、轨迹、真实score解释和三种测试入口。
3. 用户选择并微调后才实施；在此之前不要抢先重构或覆盖正式版。

用户最新未实施需求也必须保留：灰色堆垛机重构；指出当前入库链建模错误；解释并可视化各算法评分；去重顶部任务卡/底部当前作业；统一地图与 3D 货物色；给“全量 8”明确点击引导；删除冗余英文；客观融合“单件自定义 / 预设批次 / 推荐档位与算法对照”三类入口。

请只回一份同步回执，格式如下：

- 已读文件与 SHA256 核对结果；
- 接受/不同意的事实逐条列出；
- 若不同意，必须给 `file:line` 与可复现证据；
- 确认不会重做已完成 Task17，不会在 12 问前抢先实现；
- 列出你认为 handoff 或研究账本仍缺失的最多 5 项信息。

不要运行 AB、Factory I/O、`tools/ab_scripting`，不要做 Git 写，不要改任何现有文件。
