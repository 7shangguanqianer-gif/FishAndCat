========================================================================
ABB杯「智储优控」overnight 续跑启动提示词(0711 16:45 立)
用途:上个 overnight 对话(0711 13:20-16:45)触发 court 输出层复读故障，无法会话内修复。
      在新对话框【粘贴本文件全文】即可完美接管，续跑接下来 2h。
========================================================================

接管 2026 ABB杯「智储优控」(F:\abb_wh_work)。上个 overnight 对话已高质量完成一大轮审查
(挖出 2 个报告级致命发现)，因 court 故障转此新对话续跑。方向全部拍板，直接执行，不重新论证。

【第一步:只读一份，确立全部真相】
docs\overnight-report_0711.md —— 上个 overnight 的【完整交接】。读它=掌握全部:
  · 顶部 TL;DR(60秒全局) · §2 全部发现 · §3 待批准修复清单(D组致命/A组文档/B组ST/C组sim)
  · §5 最终状态。此文件已 commit 到 github，是唯一续跑入口。
(如需项目全局再读:docs\技术方向总库_0711.md / 现状与任务.md §5 / docs\画面三页制施工蓝图_0711.md)

【当前精确状态(git HEAD=远程=最新，已真实核实)】
- git master:用 `git -C F:\abb_wh_work rev-parse origin/master` 看真实值(上个对话末尾为 33054d5，
  若本文件后又有 commit 以 rev-parse 为准)。github 已同步。**永远以真实 git 为准，见铁律 2。**
- ST 侧 ab_sync 59/0;画面三页制施工+17处GUI洗完(commit 806b709);编译 0 error/1 warning(历史项)。
- 上个 overnight 产出 13 份(docs\*_0711pm.md + overnight-report_0711.md)，全 commit+push。
- **两个报告级致命发现(已亲验代码属实，报告周精修前必须先拍板)**:
  · D-1:报告/演示头条"检测器 oracle 98.5%"是 sim lexicographic 档，但 AC500 只实现 holistic 档
    (真实 81.6%/closed gap 0.0%)——lex/speed 档需 TOB/CB 策略而 PLC 策略库只有 seq/near/score/AWRA-LS;
    演示 v4-1 画面显示 AWRA_HOLISTIC 却配 98.5% 台词。证据:04_FB_Warehouse.st:914-915/921、
    sim\out\oracle_gap_summary.txt L7-9、演示脚本v3_0711.md:61。
  · D-2:报告主口径"场景自适应权重策略表"PLC 死代码——FC_ClassifyScene 函数不存在(仅注释)、
    权重查表 aPolicyDelta 在注释块内不执行、rAlpha 等无自适应赋值，AC500 跑静态默认权重
    α1.0/β0.6/γ0.4/δ0.15。证据:08_GVL_WeightPolicy_generated.st:5/9-19、04_FB_Warehouse.st:1104-1105。
  · 处理方案:docs\D1D2处理方案_0711pm.md(方案甲诚实降级改8处/方案乙PLC补实现5-9天，推荐甲)。
- 17+D组 条修复建议在 overnight-report §3，全部待用户拍板，一律未擅改。

【本轮任务:overnight 续跑 2h，多 agent 审核，2h 内一直处理(用户令)】
性质=第二轮审查加深 + 报告周安全准备。队列(按序，每项派 sonnet/medium 子代理，后台并行;
做完取下一个;清了回 R1 加深循环，保证 2h 不空转):
  R1. **D-1/D-2 反验证(红队自审)**:派 critic sonnet 专门试图【推翻】D-1/D-2——PLC 是否其实
      以别的方式实现了检测器分档/权重自适应? 98.5% 是否在别处有正当引用? 找反例，防我方误报
      (对自己的结论做对抗验证)。产出 docs\D1D2反验证_0712.md。
  R2. **sim↔PLC 一致性第二层**:第一轮(docs\sim_plc一致性_0711pm.md)已挖策略/检测器/权重三处;
      第二层挖【指标口径层】——报告每个头条数字(awra 8.40s/降62%/能耗67.3%/吞吐230/夹逼9.9%)
      的 sim/PLC 来源是否一致;演示脚本 v4 之外全量镜头对照有无类似 D-1 的画面台词错配。
      产出 docs\sim_plc第二层_0712.md。
  R3. **D-2 量化**:PLC 静态权重(α1.0/β0.6/γ0.4/δ0.15) vs sim 自适应查表权重，头条 8.40s/62%
      实际差多少(跑 sim 对比，纯 python 不碰 AB)。产出 docs\D2量化_0712.md。
  R4. **报告周安全手术包**(不碰 D-1/D-2 待拍板叙事):B3 问题域标注图文字稿 / B4 黑盒功能测试表
      结构 / B8 de-AI 七规则清洗草案。产出 docs\报告草稿_B3B4B8_0712.md。
  R5. 循环:队列清回 R1，加深复核已有 13+ 份产出有无遗漏。
每完成一项:更新 overnight-report、写盘;每小时 checkpoint。

【铁律纪律(违反=事故)】
1. **子代理一律 sonnet、effort medium，严禁 fable**(两次烧额度事故防线)。Agent 工具派前逐个
   显式传 model="sonnet";不传=继承主模型=事故根因。仅规划/综合的单次主调用可 fable/high。
2. **court 应对**:若本对话也复发 court(输出层"court"复读)，立即压短面向用户文本、改
   「写文件+一句话指路」交付;**一切以真实 git/文件为准，绝不信任 court 期任何工具结果**——
   每次 push 后用 `git rev-parse origin/master` 核实真实远程 HEAD(上个对话 court 伪造过一次假 push，
   显示"成功"实际没推上;靠真实 git 核实才发现并补推)。若 court 严重到影响工作，写完当前成果
   +commit+核实后，提示用户再开新对话。
3. **不擅改真相源 md**(现状与任务/canonical_assumptions/技术方向总库/画面蓝图):改真相源口径、
   改 ST 代码一律【待用户批准】(overnight 挂机例外:新决策点选保守项记入 overnight-report 待拍板
   清单，不停在提问)。只自主做【新增产出文件】(docs\*_0712.md、新测试)，不改现有代码/文档。
4. **文档安全红线**:禁改 1_给你看\、2_你要操作\ 下用户 docx/xlsx/pptx(只读或另存新副本)。
   git commit 只 `git add` 指定新文件路径，绝不 `-A`(避免带上 11 个 docx 的 WPS 伪改 M——
   已诊断为内容零变化的伪改，遵用户拍板"不动不提交")。
5. **AB 互斥**:Automation Builder 现开着占工程独占锁。禁开 AB 双实例、禁子代理开 AB / 跑
   tools\ab_scripting\ 任何脚本(ScriptEngine 即使 headless 也起 AutomationBuilder.exe=双实例事故)、
   禁子代理做任何 git 操作(同仓双写竞态有实案)。
6. 负结果如实报;引用数字带来源(文件:行 或 CSV);不编造。每个子代理 prompt 必写"禁 spawn 子代理"
   (一次失控成 4×5 孙代理树的历史教训)+"禁 git/禁开 AB/禁改现有文件，只新建自己的产出"。
7. computer use 上个对话三次 user_denied(用户休息期无人点)。任务A画面长跑 + Codex 启动待用户
   授权，本轮不做 GUI(无人值守+court 风险)。AB 许可≈8/2 到期，续期指引=docs\AB许可续期指引_0711pm.md
   (用户回来第一步开 CodeMeter Control Center 查许可类型)。

【2h 收尾】汇总 overnight-report(做了什么/新发现/待拍板/未完项)，commit+push，
`git rev-parse origin/master` 核实真实远程 HEAD，停手待用户。

阅读完直接开工 R1(不必问，方向已拍板);新决策点选保守项记待拍板，不停在提问上。
========================================================================
