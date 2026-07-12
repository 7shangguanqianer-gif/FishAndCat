# 给 Claude 的完整接力提示词：读懂 Codex N2/N3/N4 全部发现

把下面整段原样交给 Claude Code。目标是先理解和复核，不默认授权改项目文件。

---

你接管 F:\abb_wh_work 的“智储优控”项目。请先暂停任何改码/改文档/开 AB/git 操作，按下面顺序读完证据，再给我一份“接受/不同意/需补证”的裁决表。不要只读汇总，不要把旧审查当当前真相。

## 一、必读顺序

1. _通信/致Claude.md 顶部 N4 回执。
2. _通信/codex_out/N2_汇总回执_0712.md。
3. _通信/codex_out/N3_汇总回执_0712.md。
4. _通信/codex_out/给Claude_读懂Codex全部发现_N2N3版_0712.md。
5. N4 全套：
   - N4_P0_审计边界与盲区地图_0712.md
   - N4_P1_测试与假绿_0712.md
   - N4_P2_PLC状态机与权限边界_0712.md
   - N4_P3_生成链与二进制溯源_0712.md
   - N4_P3_二进制抽取证据_0712.md
   - N4_P4_跨机复现与提交包_0712.md
   - N4_P5_后续复核候选_0712.md
   - N4_汇总回执_0712.md
6. N3 的逐项证据与 48 文件/326 位置 grep 登记：
   - N3_P1_发现_0712.md
   - N3_P2_发现_0712.md
   - N3_P3_发现_0712.md
   - N3_P3_PPTX文本抽取_0712.md
   - N3_P4_发现_0712.md
   - N3_P4_指定grep分类登记_0712.md
   - N3_P4_DOCX文本抽取_0712.md
   - N3_P5_发现_0712.md

读完后亲自回源核查我下面列的关键行。不要因 Codex/Claude 先前都同意就跳过。

## 二、用户已拍板、不得倒退的 N2 基线

1. D1：98.5% 是 sim 的 det_lexicographic oracle attainment，不是 PLC holistic 档成绩，更不是理论上限。speed 可到 99.9%，oracle 定义上 100%。
2. PLC 当前只实现 holistic 主打档；13 场景中 11 个 lex/speed 推荐依赖 PLC 未实现的 TOB/CB。holistic 在当前 390 实例约 81.6%、closed gap 0。
3. D2：08 权重表在，但生产运行没有场景→权重消费者；FB_SceneDetect 只选策略，不改权重。管理员可手改静态值，仍不是自适应。
4. PLC 默认 xUseAccel=FALSE：plc/02_GVL.st:36。T25 明确锁匀速：plc/06_PRG_Test.st:166；T22 测完即恢复 FALSE：:143。
5. canonical 新 sum H 单 seed 锁是 8.6232：sim/tests/test_sim.py:189；7.6202 只保留 legacy and 锁：:204。canonical 头部旧值落点是 docs/canonical_assumptions.md:39-41。
6. 报告/PPT/演示不得宣称任何“PLC H 闭环”。当前 PLC 能说的是核心 ST 逻辑和静态匀速黄金向量/在线测试；头条 KPI 必须标 sim。
7. 方案甲不是改 8 处 Markdown，而是四组闭环：真相源；报告/演示文本；生成器+DOCX/PPTX 再生；渲染/grep/长跑审计。
8. 不在未授权时新增 sum+xUseAccel=TRUE 端到端测试；T25 保留历史匀速锚。若后续用户授权，N4 已证明这条测试现在优先级上升。

## 三、数字字典：N4 后必须用这个新版

- 8.40：120 件/skew/sum、5 seeds、ACCEL=True+adaptive=True 的 sim H 均值。
- 8.6232：同 H 设计口径、seed2026 的 sum 回归锁。
- 7.6202：旧 and 底图、seed2026 的 legacy H 锁，只作历史。
- 8.757：Python warehouse_sim 引擎中 ACCEL=True+static 的 5-seed sim 结果。
- 8.794：N4 按当前 ST 固定 FC_TMax=38、tie_break=st、ls_eps=1e-6 做的更近 Python 代理。
- 6.443：ACCEL=False+static、PLC 默认开关方向的 5-seed sim 代理。

关键修正：8.757 不再叫“PLC 可逐值实现代理”。Python make_score_fn 的 tmax 随 ACCEL 变为 39.6667：sim/warehouse_sim.py:110-115、249-251；ST FC_TMax 始终匀速 38：plc/03_Functions.st:174-177。T19/T22 没测加减速评分：plc/06_PRG_Test.st:101-143。8.794 也只是更近的 Python 数学代理，不是 AB/AC500 实测。

## 四、N3 必须保留的新增结论

1. A3“检修存量冻结”不成立：局搜 relocation 可把维护源位货物搬出，且注释在“冻结/允许出”之间冲突。
2. A4 画面锁未全接；更关键的是 N4 证明 guard 在消费者后，值虽回滚，布局副作用可永久留下。
3. C6 aSlotOps 是布局写入近似，不是完整物理存取履历；漏计重定位源位，INT 还会长期溢出。
4. adaptive_weights/verify_policy 忽略 failed，在线高压 KPI 有幸存者偏差。
5. realism 各策略按自己的服务时长生成 arrival，P50/P95 不是 common workload 公平横比。
6. 演示步骤 6 的 AWRA→Score 快照不会自动跳变；v4 权限/维护镜头需要重登录、跨页与修正首选格；三页 HMI 在线长跑仍待验。
7. 报告/PPT/桌面面板把 sim H、230、年化能耗、自适应与 AC500 绑定；二进制还混 23/24/45 等旧测试数。
8. N3 指定 grep 已按 ①需改、②历史证据、③sim 事实 分类 48 文件/326 个去重位置，方案甲验收必须复用该登记，不要重新凭印象搜。
9. 独立“无需改”裁决：plc/04_FB_Warehouse.st:910-915 与 sim/lifecycle_sim.py:3 可保留；plc/README_PLC.md:40-44 不能整段判无需改，43-44 的冻结/画面锁声明要改。

## 五、N4 六个新阻塞，必须逐条回源

### 1. 加减速评分桥断裂

见上面的 8.757→8.794 修正。数值差只有约 0.038 s，但每 seed 平均 38.4/120 件位置变化，不能以“卖点差很小”掩盖实现差异。

### 2. ParamGuard 顺序错误

主状态机消费者在 plc/05_PRG_Main.st:57-187；fbGuard 在 :198-206。守卫 threat model 明说防绕过 HMI：plc/04_FB_Warehouse.st:1060-1064。请构造“一拍越权写→先分配→后回滚”的状态反例，不要只看 T55。

### 3. LoadDemo 数组越界

数组 1..400：plc/02_GVL.st:71-74；PRG 直接载入：plc/05_PRG_Main.st:100-107；FC 每次无条件追加20：plc/07_GVL_Data_generated.st:84-131。空表第21次写 aGoods[401]。

### 4. run_all 不是全量再生

sim/run_all.py:19-30 只跑七步、排除专项；:41-47 把所有旧 out/figs 打印成产物。build_report 读取的多份专项 CSV 不在链中，且不生成 DOCX/PPTX。当前 doc_check 还是 11 断链+1 过时、exit1。

### 5. H 页面嵌静态匀速图

plots.compute 固定权重且 ACCEL 默认 FALSE：sim/plots.py:37-51；fig1/fig5 仍写 and：:70、186。PPT H 页嵌 fig1：sim/build_ppt.py:115-120；报告 H 章节嵌 fig4：sim/build_report.py:499-516。必须先修图源，再重生二进制。

### 6. 干净机器/提交包不可复现

无 requirements/lock/license/manifest；sim/out、sim/figs 默认被忽略；当前整仓约143MB，含缓存、备份、锁、内部通信、研究PDF。README“可删全部再生”和“任意机器 Python3.8+”不可继续照写。

## 六、N4 其他高优先项

1. test_oracle_gap 的性能来自冻结 instgen_detail.csv，不会因评分/可行性变化变红；真实 golden test 还会重写正式 oracle 输出。
2. run_all 只跑 test_sim 的21个，漏 oracle 2个。
3. H/legacy/全场景测试未断言 failed=0。
4. T25/T58 在单个触发扫描内 WHILE 10万/100万次，有看门狗风险；没有显式 timeout/done 断言。
5. N_CASES 可在线改，能隐藏后部失败或越界。
6. T58 只断言 aSlotOps>=1，旧履历可垫绿。
7. ID=0/负/重复可入表，但0又是空位哨兵，Query 对<=0拒绝且重复只返第一件。
8. 策略开始时锁部分值，完成时又读实时 SelStrategy，中途切换可错走/漏走 LS。
9. nBatch/nPairs<=0 会永久不前进；管理员无范围保护。
10. 运行中可改权重/运动/λ，批次没有参数快照，最终布局无法归属单一口径。
11. VisuViolationCount 只查重量/体积，报告却外推到占用冲突/全部约束。
12. SceneDetect 400件最坏单拍约2万步只靠注释估算；测试最大21件。
13. build_report 缺 CSV 仍保存、只警告、exit0。
14. 项目全景说明书.docx 是孤儿历史快照；有7.42/66.2/74.3、356/152、23/18 tests 等。
15. AB可视化搭建操作卡_块3增补.docx 当前旧于 md。
16. 没有 submission allowlist、依赖锁、第三方许可/SBOM、secret/PII 清洁证明。

## 七、正面结论也要保留

1. 报告16图、PPT8图、用户导览10图与当前 sim/figs SHA-256 全同；无旧图片残骸、无外部图片关系。问题在当前图源，不在 ZIP。
2. 常规坐标检查、路径数组最大长度、动画路径清零护栏设计较稳。
3. 核心 sim 脚本多数按 __file__ 用相对路径，修成跨机包的基础存在。
4. N3 已确认若干 sim 算法事实本身准确；不要为了去错配而删除历史测试锁、审查证据或正确的 sim 结果。

## 八、你现在要输出的裁决格式

先不要改文件。请输出：

1. “接受/不同意/需补证”表，至少覆盖 N4-01、02、03、04、05、07、09、14、15、16、17、18、19、20、26、27、28、30、35、36、37、40。
2. 每个不同意项必须给原始 file:line 反证，不接受只说“看起来没问题”。
3. 明确新版数字字典，尤其 8.757 与 8.794 的边界。
4. 给出修复批次建议，但不执行；按以下依赖顺序：
   - P0 口径/图源/生成器；
   - P1 PLC 会产生错误状态的代码；
   - P2 测试与完整再生链；
   - P3 AB/实机/提交包。
5. 若用户随后授权方案甲或代码修复，先生成受影响文件清单和回滚/验收门；不得只改 Markdown，也不得用新二进制覆盖旧文件而不保留审计证据。

## 九、验收底线

- 任何头条都带 sim/PLC/AB/实机层级。
- 8.40/8.6232/8.757/8.794/6.443/7.6202 不混。
- 所有成功均同时报告 failed。
- 图表自身带 rule/motion/weights/seeds。
- test 全量 discover，测试不写正式 out。
- 报告/PPT required input 缺失时非0退出。
- 干净副本可从空 out/figs 全量再生，并有 manifest 哈希。
- AB 反例测试至少覆盖 guard、LoadDemo、策略切换、非法分片、400件最坏扫描、sum+ACCEL评分。
- 最终提交包使用 allowlist，通过 PII/secret/license/render/复跑检查。

完成裁决后停下，等用户决定是否授权修改。

---

