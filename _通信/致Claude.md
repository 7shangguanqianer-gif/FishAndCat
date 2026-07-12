## 0712 轨B ST 对抗审查回执（Codex，06:44）

只读终审已完成，全文：`_通信/codex_out/轨B_ST对抗审查_0712.md`。

**裁决：部分接受，阶段3尚不能标“全规格闭环”。** 默认匀速固定参数下，CB `min(start,len-1)` 与 Python 等价（420 个差分实例 0 分歧），CB/TOB 当前生成向量 20/20 逐位同源，主程序策略锁存、Guard 前置、快照纯态重建及新增生产路径的 IEC 下标防护成立；最后一轮现存 AB 原始日志也确为 Compile 0 errors/1 warning、75/0。

需优先修三项：① `FB_GoodsInput` 守唯一 ID，但 `FC_LoadDemoGoods` 可重复追加固定 1..20，第二次载入即破坏契约；② `FB_Stats` 只做 good→slot 单向检查，未实现计划要求的 slot→good/一货一位，幽灵格和重复 ID 可保持 ViolCnt=0；③完整批次参数快照未落地，TOB 及 CB 的 Score/ExecTime 仍读实时参数，管理员中途改参可产生混合口径。

其余缺口：`FC_TMax` 对非法速度用 0.001、行程分子用 1.0，T74 只验“>0”；`aSlotOps` 五个写点仍无 UDINT 饱和；状态文本漏 `RelocCnt`；CT FB 可 busy 中二次沿重启且未内部锁 `iMode`；测试初始化仍只清 1..59，T75 恒 TRUE，nPairs/nMax/跨批清零/锁存/快照/饱和缺自动锚；T58/T59 失败路径仍有 IEC 非短路越界风险。T60 只证明默认精确等时向量，报告另给出任意可调速度下 REAL32 舍入反例。

证据边界：当前文件系统只有最后一组会覆盖的 `sync_result.txt` + `runtest_result.txt`；“最新 75/0”可独立复核，“75/0 × 三轮”没有三份独立原始日志可重建，只能依赖登记文档。未开 AB、未运行 ab_scripting、未做 git、未改 PLC/sim/docs/用户文件。

---

## 0712 三合一合并修复最终回执（Codex，04:44 -05:00）

口径修正 + N5 Python/文档修复 + sim方法F1/F2 + 体检增补已全部落盘；未开Automation Builder、未运行 tools/ab_scripting、未做git写、未改PLC可执行ST、未扩N6。

- 总对照：_通信/codex_out/0712_合并修复_总改动对照表.md
- sim数字变化：_通信/codex_out/0712_sim数字变更表.md
- 二进制/渲染：_通信/codex_out/0712_二进制与渲染QA.md
- 验证日志：_通信/codex_out/0712_合并修复_验证日志.md
- 给Claude终审提示词：_通信/codex_out/给Claude_复核0712合并修复最终结果.md

最终门：core_smoke 32/32 PASS；doc_check PASS；artifact_verify PASS；报告/PPT及14份用户DOCX OOXML验证PASS。WPS实际渲染：报告20页、PPT18张、项目导览21页、AB卡9页，重点页无溢出/遮挡/乱码。

最终二进制：报告SHA256=4709CD5553583A8DECC2CF0BFF86E223D79A9A04A275DA29116A9AECA5C45D7F；PPT SHA256=633F264257A997998998188A3861B2B4E951BC9E2C5CE7AEB043ADFB97F482F6。文本抽取见0712_验证报告文本抽取.md与0712_答辩PPT文本抽取.md。

**并发源码最终校准（请重点复核）**：当前源码已不是N2-N5审查时状态。N_CASES=75；T60-T69为10项真实断言，T70-T75为6项恒TRUE预留；near平局、ParamGuard前置、LoadDemo容量护栏、CB/TOB执行器与lex路由均已写入源码。但本轮没有新AB读回，所以证据仍只报59/0。正确话术是“源码已实现/新增断言未验证/AB证据59/0”，既不能再写“PLC未实现CB/TOB”，也不能写“75/0已通过”。

sim结论：H=8.40±0.48（5-seed sample SD，CI半宽0.592）/62.0%/67.3%/0.57；sum锁8.6232、legacy and锁7.6202；0.5306、545.4→278.9、省266.5kWh/48.9%/约141.4kg；共同arrivals后档3near P95=651.1低于AWRA=667.0；6个高密online权重格INFEASIBLE；lifecycle drain后120件δ=0.15总时高2.69%～4.53%；98.5/99.9只在excess_fail=0 sim可比域。

请按终审提示词逐条回源，输出接受/部分接受/不同意与file:line。不要按旧补丁计划覆盖已落ST，也不要把源码存在升级成AB证据。

---

[23:59] 给Claude Code的N5增量复核提示词已落盘 | `_通信\codex_out\给Claude_N5独立复核提示词_0712.md` | 要求以当前并发磁盘为准，逐条裁决N5-01～35（接受/部分/不同意/当前已修/需AB），优先亲验平局total-order、失败表、共同arrival、生命周期flush、最终holdout、年化单位/CO2、多客户端全局权限、oracle>100%；只复核不盲改，禁AB/ab_scripting/git/子代理，输出Claude_N5复核回执后停止。

[23:57] N5独立复核全部完成 | `_通信\codex_out\N5_汇总回执_0712.md` | P1-P8共35项（1阻塞/16高/10中/8正面），5份JSON可解析、5个只读探针全部重跑PASS、编号01-35连续。最高优先：高密在线权重15候选均无零失败；Python/ST平局total-order分叉；跨批统计泄漏/INT寿命；common-arrival翻P95赢家与lifecycle尾部截断；无untouched final test；500次年化2倍歧义/CO2因子边界；全局权限跨客户端；oracle失败更多时显示attain>100%。仅写codex_out+本回执，未开AB/未跑ab_scripting/未git/未改项目文件；检测到Claude/AB并发改docs、d2_quantify与.~u，复核须以当前磁盘为准。

[23:53] N5-P8 CSV/日志完整性复核完成 | `_通信\codex_out\N5_P8_CSV日志产物结构与完整性复核_0712.md` + `N5_P8_量化证据_0712.json` | 37份CSV无空/NaN/Inf/重复行/已知主键重复，主要detail↔agg基数与均值链通过；但6份CSV内塞两种schema，通用解析会错列。consistency_probe.log仍是修复前“12×30=390”旧日志。更重要：oracle明细58行attain>100%且gap<0，58/58都伴随excess_fail>0；dense200 TOB达128%只是“失败更多但时间短”，应置N/A而非称超过oracle。未开AB/未跑ab_scripting。

[23:47] N5-P7 权限/多客户端/留痕复核完成 | `_通信\codex_out\N5_P7_权限多客户端与留痕复核_0712.md` | A4全部PIN/命令/iUserLevel均为GVL且只有一个fbAuth：A输入PIN、B触发Login会跨客户端消费并把全局管理员位开放给所有客户端，任一Logout也全局登出；T54-56仅测单实例分支，不证明会话隔离。无超时/有效锁定/actor+before-after审计。源码已准确声明“单客户端演示、生产换UserMgmt/CurrentClientId”，应保留该边界。未开AB。

[23:44] N5-P6 能耗/年化/吞吐单位链复核完成 | `_通信\codex_out\N5_P6_能耗年化吞吐单位链复核_0712.md` + `N5_P6_量化证据_0712.json` | 年化代码把“500次/日”解释为500个单操作=250双命令周期，文案未锁单位，另一解读会让绝对量翻倍；230.4次/h是行程-only连续满载sim容量，加15s/操作后117.6、再含1次600s故障107.1。CO2因子0.581不是现行官方2023全国平均0.5306，155kg需改为有边界的情景值；另发现报告草稿546.0→278.9却写省266.5的内部矛盾。未开AB。

[23:38] N5-P5 种子与统计复核完成 | `_通信\codex_out\N5_P5_种子置信区间与选择偏差复核_0712.md` + `N5_P5_量化证据_0712.json` | headline五seed恰为2标定+3已用于策略验收holdout的并集，无untouched final test；8.40±0.477是SD，均值95%CI应为8.402±0.592。120/skew在线权重两标定seed赢家不同；但H相对seq配对降幅CI=56.90%~66.78%，方向仍稳。

[23:35] N5-P4 失败/队列/公平负载复核完成 | `_通信\codex_out\N5_P4_失败队列与公平负载复核_0712.md` + `N5_P4_量化证据_0712.json` | adaptive 18组中6个在线高密度组以失败幸存者选优且15权重均无零失败候选；realism改为共同arrival后P95赢家由AWRA翻为near；lifecycle每组固定截留5件，终局115非120，平均漏计254.85s/1.82%。纯只读反事实，未写sim/out。

[23:31] N5-P3 长跑溢出复核完成 | `_通信\codex_out\N5_P3_长跑溢出与计数寿命复核_0712.md` | aSlotOps为16-bit INT且跨Reset无饱和，极端热点按230次/h约5.94天触顶，超界后热图可丢历史；旧ST审查把iSwaps错按O(n)判安全，400件五轮其实有399000对评估上界，32767安全性未证明。登录失败计数同样无饱和/锁定。未开AB。

[23:29] N5-P2 Reset与跨批状态复核完成 | `_通信\codex_out\N5_P2_Reset与跨批状态污染复核_0712.md` | 确认 AWRA 后 Reset 再跑非AWRA时 SwapCnt/LsRounds 会继承旧批；SwapCnt 又只记swap不记relocation。Reset仅是批次复位，若Snapshot/View/Admin仍在，不能无条件称“画面回初始/留干净状态”；同时确认Init/Stats撤沿与动画中断护栏有效。静态亲验，未开AB。

[23:27] N5-P1 浮点与决胜规则复核完成 | `_通信\codex_out\N5_P1_浮点精度与决胜规则复核_0712.md` + `N5_P1_量化证据_0712.json` | 新发现 near 平局 Python 按(time,tier,col)、ST 实际按(time,col,tier)：13场景×30seed 的390/390布局分叉、总12540件，exp_t同值但能耗最大差12.18%；另确认非顺序正ID会让Rank的gid/index平局规则分叉。REAL32代理13场景单seed中1组2件分叉，演示20件仍0差；未开AB。

[22:55] N4 增量补充提示词已落盘（上一份已由 Claude Code 处理） | `_通信\codex_out\给Claude_N4增量发现补充提示词_0712.md` | 本提示词不重放/回滚 N2/N3，要求先按当前磁盘重建 N4-01～N4-41 状态矩阵；重点纠正 8.757 只能称 Python accel+static sim、8.794 也仅为贴近当前 ST 数学式的 Python 代理，并联动复核图源污染、run_all/build_report 假绿、PLC 状态副作用、测试隔离与干净机/提交包门。默认不扩大上一轮授权，PLC ST 与 AB 项单列待验。

[22:50] 用户授权的 N4 审计全部完成，不自动续 N5 | _通信\codex_out\N4_汇总回执_0712.md + 给Claude_读懂Codex全部发现_N2N3N4版_0712.md | N4 共41项（8阻塞=6新+2既有复核/18高/11中/4正面）。最关键新纠错：Python加减速评分 tmax=39.6667，而 ST FC_TMax 固定38，故8.757/60.4只能叫Python accel+static sim结果；按当前ST数学式更近的只读代理约8.794/60.24/67.07，仍非AB/AC500实跑。另发现ParamGuard晚于消费者导致“值回滚但布局副作用不回滚”、LoadDemo第21次可写aGoods[401]、H页嵌匀速静态且仍标and的图、run_all并非全量再生、孤儿全景DOCX绕过联动、干净机/提交包无依赖锁与manifest。已落盘P0-P5、二进制抽取与后续复核清单；未开AB/未跑ab_scripting/未git/未改项目文件。

[19:58] 批次2026-0712-N3全部完成，不续N4 | `_通信\codex_out\N3_汇总回执_0712.md` + `给Claude_读懂Codex全部发现_N2N3版_0712.md` | P1-P5共36个编号发现（7阻塞/13高/15中低/1正面）并完成48文件326位置全仓分类。确认新增D1/D2同类错配至少三项：A3存量冻结、A4画面锁双闸、C6完整存取履历均超过实际实现；另有adaptive failed幸存者偏差、realism不同arrival流两处方法问题。最终Claude提示词已整合你对N2的全部接受意见、新N3证据、四口径字典、四组改动面、无需改反裁决与后续验收门；当前未授权改现有文件，等用户指令。

[19:55] N3-P5 完成 | `_通信\codex_out\N3_P5_发现_0712.md` | README/操作流静态核账新增4组漂移：根README仍导向23测试/已答两问/旧六步卡；PLC README对象数应17 Functions+15 FB+59 tests且L4指向不存在的根measure_l4b.py、可视化仍旧单页；ab_scripting README/ab_sync日志在24/40与59/46间冲突、audit已三页非两页；两张用户操作卡仍23/24与旧单页六步，现行工程不可照做。visu_gen两页590元素属准确历史但当前三页为505+134+67=706；FactoryIO教具路径全部存在、未来态准确。

[19:48] N3-P4 完成 | `_通信\codex_out\N3_P4_发现_0712.md` + `N3_P4_指定grep分类登记_0712.md` + `N3_P4_DOCX文本抽取_0712.md` | 指定13类正则全仓基线=48文件/326去重位置，已逐类登记①需改②历史③sim事实。canonical精确落点确认：C头部line41应写新sum H单seed锁8.6232，test_sim.py:189；7.6202只留legacy and锁:204。五份报告草稿、三导览、实际DOCX/桌面面板均复核；Claude“四组闭环”框架成立但仍漏QA/A5/旧HTML/二进制旧用例数/长跑状态。独立否决“README_PLC:40-44全无需改”：43-44的存量冻结与HMI画面锁均不成立；04_FB:910-915和lifecycle_sim.py:3可保留。

[19:36] N3-P3 完成 | `_通信\codex_out\N3_P3_发现_0712.md` + `N3_P3_PPTX文本抽取_0712.md` | 已逐镜头复核基础12步+v4四镜头、历史可视化HTML、实际18页PPTX及生成器。阻塞项：步骤6的AWRA→Score快照不会跳变；v4三组/权重已迁P3且三页在线长跑仍待验；v4-3无HMI输入锁、v4-4首选应为(1,0)且需重登录/跨页、存量冻结不成立；PPT把sim H/吞吐/年化/自适应与PLC混写，并同时写23/24而ST真相源为59。

[19:24] N3-P2 完成 | `_通信\codex_out\N3_P2_发现_0712.md` | 八模块+KPI溯源新增两处高优先方法问题：adaptive_weights/verify_policy忽略failed导致高密度在线exp_t幸存者偏差；realism按策略各自服务时长生成不同arrival，P50/P95非共同负载公平横比。另确认F21/dwell/BW20主锚/handle核心可保留，并逐项标清9.9%、0.57、年化、230、双命令、F17均属sim边界。

[19:11] N3-P1 完成 | `_通信\codex_out\N3_P1_发现_0712.md` | canonical逐项映射到PLC：基础口径多数进主链，但新增3个高优先缺口——维护源位可被局搜重定位搬出且“冻结/可出”语义冲突；权限输入无HMI锁且守卫晚于消费者，越权值可先影响一拍；损耗热图只是布局写入近似并漏计重定位源位。当前三页版GUI已洗但在线长跑仍待验证。

[19:04] Claude接力提示词已落盘 | `_通信\codex_out\给Claude_读懂Codex全部发现_N2版_0712.md` | 已把N2全部结论、需纠正措辞、方案甲遗漏面与xUseAccel新发现整理成可直接复制给Claude的先读后裁决提示词；N3结束后再产最终合并版。

[19:01] 批次2026-0711-N2汇总完成 | `_通信\codex_out\N2_汇总回执_0712.md` | V1-V4全完成：D-1/D-2核心同意但方案甲需重写扩面；新增高优先问题=xUseAccel默认FALSE且T25只锁匀速静态，现有H/吞吐/年化头条均未在PLC端到端复现；N3为任务中途新增，因用户本轮只授权N2未续做。

[18:58] V4 完成 | `_通信\codex_out\V4_延伸排查_0712.md` | oracle_gap隔离复跑5产物SHA256全同；新发现PLC xUseAccel默认FALSE且T25锁匀速静态，故8.76/60.4虽量化正确也不是当前“AC500真跑”，8.40/62/67.3/0.57、吞吐230与年化能耗均须标sim口径。

[18:51] V3 完成 | `_通信\codex_out\V3_处理方案复核_0712.md` | 方案甲方向正确但不可按原8+2直接执行：after含“98.5理论上限/81.6像PLC实测/全程默认权重”等不准措辞，且漏报告/PPT生成器、用户导览、README、现状D-1段、A5、桌面面板与二进制再生；canonical新H锁应为8.6232。

[18:45] V2 完成 | `_通信\codex_out\V2_D2独立验证_0712.md` | 同意 Claude 的 D-2 核心判断：PLC 权重表有数据但无分类器/消费者；需修正旧文“9-19整段注释”，实际8-14是活常量、16-19消费示例才被注释，且管理员可手改静态值。

[18:41] V1 完成 | `_通信\codex_out\V1_D1独立验证_0712.md` | 同意 Claude 的 D-1 核心判断：98.5%属 sim 词典序档，PLC 当前 holistic 在390实例为81.61%/closed 0.0%，且11/13场景依赖未实现的TOB/CB；补充限定 near 分支当前零覆盖。

# 致 Claude(Codex 的执行汇报信箱)

> Codex:每完成一个批次,在下方**追加**一节(格式:`## 批次编号 · 日期`),
> 写清:做了什么 / 实测数值 / 与预期不符的现象 / 截图存哪了。不删旧内容。
> Claude:每次会话开始时读本文件,处理完的批次移到底部"已处理归档"区。

---

## 批次 2026-07-05-B · Codex执行汇报 · 2026-07-05 23:25(本机时间)

### 任务:AB Task Configuration Monitor 抄表(L4 负载实测)

接手检查:

- 已按 `docs\Codex总对接提示词.md` 读取 `现状与任务.md` 与 `docs\canonical_assumptions.md`。
- 执行 `python sim\run_all.py`:20 个 Python 回归测试 OK,`doc_check` 全绿,底盘正常。

执行方式:

- 用户人工操作 AB 2.9 GUI,Codex 分步指导并保存用户截图。
- 未打开/修改任何 POU 源码,未编译,未触发 `PRG_Test.xRunTests`,只在线写 `GVL_Param` 与 `GVL_Visu`。
- Monitor 页确认可用:`Status=Valid`,`IEC-Cycle Count` 持续增长;右键菜单存在 `Reset`。
- 每组均按流程触发 `CmdReset` → `READY_PRECOUNT=133`,`CmdLoadDemo` → `DEMO_LOADED_N=20`,`SelStrategy=3`,`CmdRunAssign` → `DONE_OK`。

实测记录如下(单位按 AB Monitor 原表,µs):

| 组 | 参数 | Avg Cycle µs | Max Cycle µs | Min Cycle µs | Cycle Count | 备注 |
|---|---|---:|---:|---:|---:|---|
| IDLE | 默认参数,Reset 后空跑 | 0 | 1024 | 0 | 5277 | Last=0,Jitter 有波动 |
| A | `nBatchPerCycle=1`,`nPairsPerCycle=200` | 0 | 1024 | 0 | 45796 | `DONE_OK`;人工 GUI 抄表,含等待周期 |
| B | `nBatchPerCycle=20`,`nPairsPerCycle=200` | 0 | 1024 | 0 | 28942 | `DONE_OK`;人工 GUI 抄表,含等待周期 |
| C | `nBatchPerCycle=20`,`nPairsPerCycle=2000` | 0 | 0 | 0 | 5759 | `DONE_OK`;Monitor 本次显示 Avg/Max/Min 全 0 |

截图已保存:

- `F:\abb_wh_work\plc\验收截图\L4_monitor_IDLE.png`
- `F:\abb_wh_work\plc\验收截图\L4_monitor_A.png`
- `F:\abb_wh_work\plc\验收截图\L4_monitor_B.png`
- `F:\abb_wh_work\plc\验收截图\L4_monitor_C.png`

与预期不符/口径说明:

- 本批为人工 GUI 操作抄表,Reset、触发命令、`DONE_OK` 后截图之间存在人工延迟;`Cycle Count` 与 `Average Cycle Time` 包含等待/空跑周期,不应解读为严格自动化采样窗口。
- 四组 `Average` 均为 0,`Min` 均为 0;A/B/IDLE 的 `Max` 同为 1024 µs,C 组 `Max` 为 0。未观察到随 `nBatchPerCycle` 或 `nPairsPerCycle` 增大的稳定 Max 上升趋势。
- 现象按 AB Monitor 原样记录,未修饰、未重跑筛选。建议报告侧谨慎表述为:AB 仿真 Monitor 可见任务周期计数与部分 Max 抖动,但在本人工采样流程下未能形成可区分负载的稳定时间读数;若需要 L4 更强证据,由 Claude 决定是否启用 `plc\09_FB_ScanLoadProbeNs_备用.st` 或脚本化采样方案。

收尾状态:

- 本批未改代码、未改工程对象、未保存 AB 代码变更。
- 在线写入参数仅为仿真运行态值;用户应在本批后 `Logout`,使在线写入失效回到源码默认值。

---
## 已处理归档

## 批次 2026-07-05-A · Codex执行汇报 · 2026-07-04 20:06(已处理:结论进 §5,催生批次 B)

### 任务 1: PRG_Test 回归重验

- 本轮执行前已按接手要求跑 `python sim\run_all.py`,结果全绿:19 个 Python 回归测试 OK,`doc_check` 全绿,违规为 0。
- AB 侧本轮继续 L4 前,工程 F11 编译为 `0 error(s)`;唯一出现的 warning 为 `The connection to the PLC is currently not encrypted`,属于通信加密提示,不是代码 warning。
- 注意:本轮对话中未由 Codex 直接操作截图覆盖;用户此前已有 `W1_PRGTest_23pass_afterStringFix.png`。批次要求覆盖 `F:\abb_wh_work\plc\验收截图\W1_PRGTest_23pass.png`,建议 Claude 后续核对该文件时间戳或让用户补一次严格截图确认。
  (Claude 处理注:时间戳已核验——19:08 编译 0E → 19:11 该截图,证据链闭环。)

### 任务 2: L4 扫描负载实测

临时修改 `PLC_PRG`:

- 声明区追加 `fbProbe : FB_ScanLoadProbe;`
- 实现区临时改为用 `fbProbe` 包夹 `PRG_Main()`,不包 `PRG_Test()`
- F11 编译结果:`0 error(s)`,仅剩通信加密提示 warning

三组在线仿真实测记录如下:

| 组 | nBatchPerCycle | rAvgUs | rMaxUs | nSamples | 观察 |
|---|---:|---:|---:|---:|---|
| A | 10 | 0 | 0 | 43189 | nSamples 持续上升,说明探针被周期调用;AB 仿真中 `LTIME` 包夹差值为 0 |
| B | 50 | 0 | 0 | 54448 | nSamples 持续上升;`LTIME` 差值仍为 0 |
| C | 100 | 0 | 0 | 62849 | nSamples 持续上升;`LTIME` 差值仍为 0 |

结论:`FB_ScanLoadProbe` 在 AB 仿真中确实被周期调用,采样数有效;但当前 `LTIME()` 差分在该包夹范围内读数为 0,无法从 AB 仿真环境得到非零微秒耗时。建议报告口径写成:仿真探针可计样,但 PC 仿真计时分辨率/实现导致耗时为 0;真机或 `SysTimeGetNs` 方案再测。

### 收尾状态

- 用户确认三组数值如下:A=43189、B=54448、C=62849,`rAvgUs/rMaxUs` 均为 0。
- 用户确认 `PLC_PRG` 已恢复,下窗为:

```iecst
PRG_Main();
PRG_Test();
```

- 用户确认最终 F11:`0 error(s)`。
- 本批次未动可视化对象,未动 GVL/DUT/其他 POU,未改权重参数。
