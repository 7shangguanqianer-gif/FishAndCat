# 给 Claude Code：接管 AB「取出」按钮剩余任务

进入 F:/abb_wh_work，只接管 0716 AB 可视化「取出」按钮批次。

先完整读取：

1. F:/abb_wh_work/.claude/handoffs/2026-07-16-205841-ab-retrieve-button-claude-takeover.md
2. F:/abb_wh_work/_通信/codex_out/0716_AB取出按钮_中止与ClaudeCode接管完整回执.md
3. F:/abb_wh_work/_通信/致Codex.md 顶部 0716 批次
4. F:/abb_wh_work/docs/续窗交接_0716B.md
5. F:/abb_wh_work/docs/canonical_assumptions.md

关键现场：Automation Builder 当前可能仍以 ABB_WH.project* 打开，里面只有 Codex 未保存的半成品。第一动作必须关闭工程并在保存询问选择“否/No”，从磁盘 F:/abb_wh_work/plc/AB_Project/ABB_WH.project 干净重开。磁盘基线 SHA256=04A6607BB60CEE6FD50B7AB935D40F2059790E9D2F92E5A382472B645E75FD50。不要保存星号状态。

先裁决一个签发冲突：任务书写 P1，但“现有查询按钮同组旁”实际只能是 P2 VisuStats；P1 没有 Query。原始施工卡 2_你要操作/AB可视化搭建操作卡_块3增补.md:57,86-90、docs/画面三页制施工蓝图_0711.md:87-88、docs/报告草稿_§6可视化_0712.md:12 均证明查询区在 P2。建议以 P2 为最终落点，并在回执中解释偏离字面 P1 的依据；不要在两页各建一套。

实现要求：

- 新增一个「取出」瞬时按钮，复用 GVL_Visu.InQueryId。
- 绑定 GVL_Visu.CmdRetrieve，不新增输入框。
- 最安全做法：复制现有 Query，逐项核对 Input configuration，只替换变量。
- 推荐布局：Retrieve x1080 y60 w100 h30；命中灯移 x1080 y104；Found 移 x1118 y104。实际边界不同时以无重叠和 Properties 实测为准。
- 可选“已取出 %d 件”→ GVL_Visu.iRetrievedCount；空间不自然则按任务书跳过。
- 每个元素核对 X/Y、Text、Tap/Toggle、按下/释放动作；弹窗标题确认后再 OK。

验收：

1. GUI Build/F11 为 0 errors，warnings 如实。
2. Login → Load demo → Run assign → 输入已分配 demo ID（优先 901）→ Query → 取出。
3. 等 RETRIEVED_OK；确认原格位变空，同 ID 再查询为未分配/位置 -1，iRetrievedCount +1。
4. 保存在线证据截图到 F:/abb_wh_work/_通信/codex_out。
5. Logout 并关闭 AB。
6. 写最终回执到 codex_out，并在 F:/abb_wh_work/_通信/致Claude.md 顶部追加。

红线：

- AB GUI 开着绝不运行 tools/ab_scripting。
- 不改 ST、sim、canonical 或用户文档。
- 不做任何 Git 写。
- 工作区已有大量其他任务的 M/??，不得清理、覆盖或纳入本批。
- 负结果如实，不用旧 76/0 代替本次 GUI 在线闭环。
