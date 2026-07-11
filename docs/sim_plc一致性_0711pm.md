# sim↔PLC 一致性系统排查(0711pm,D-1 延伸;overnight 无人值守)

> 审查人:Claude Code(独立完成,未 spawn 子代理,未 git,未开 Automation Builder,未改动任何现有文件)。
> 任务:D-1(检测器档位错配,已知)之外,系统排查"sim 宣称有、AC500 PLC(ST代码)实际未实现"的其余错配。
> 方法:逐条对照 sim(`sim/*.py`)与 PLC(`plc/*.st`)源码 + 全仓 grep 交叉验证 + 报告/演示文案回查,
> 不采信任何既有文档的"已完成"措辞,一律回到源码验证。已读全部 9 个 `.st` 文件、`strategy_lib.py`/
> `warehouse_sim.py`/`adaptive_weights.py`/`headline.py`/`export_st_vectors.py` 等 sim 核心文件,
> 以及既有四份审查(一致性审计/ST审查/sim审查/对抗复审,均 0711pm)避免重复劳动。
> 引用一律"文件:行"。负结果如实(一致就明说一致),不编数字。

---

## 0. 一句话摘要

除 D-1 外,系统排查新发现 **2 处结构性错配**(D-2/D-3)+ 1 处已知问题的量化补强 + 2 处轻量级观察点。
**最严重的新发现是 D-2:项目反复宣称"报告主口径 H = 梯形加减速 + 场景自适应权重策略表"
(`docs/canonical_assumptions.md:38`、`现状与任务.md:70-71`),但后半句在 PLC 上是彻底的死代码——
`plc/08_GVL_WeightPolicy_generated.st` 的查表数组从未被任何 ST 代码读取,负责场景分类的
`FC_ClassifyScene` 函数在全仓库里根本不存在。** 严重度与 D-1 相当:两者共同的后果是——**报告头条数字
(8.40s/62.0%/67.3% 等)背后的两套"创新机制"(检测器分档 + 权重自适应),AC500 上都只是半成品**,
一个演委只需要现场提问"你们的自适应权重在哪段 ST 代码里生效"就能当场发现第二个坑。

---

## 1. 排查范围与依据

| 编号 | sim 侧 | PLC 侧 | 结论 |
|---|---|---|---|
| 策略集 | `sim/strategy_lib.py`(7 策略) | `plc/02_GVL.st:117` `SelStrategy` | 见 §2 D-1(已知)|
| 检测器档位 | `sim/strategy_lib.py:153-171` (3 档) | `plc/04_FB_Warehouse.st:910-1017` `FB_SceneDetect` | 见 §2 D-1(已知,本次补量化证据)|
| 权重策略表 | `sim/warehouse_sim.py:216-237`+`sim/adaptive_weights.py` | `plc/08_GVL_WeightPolicy_generated.st` | **见 §3 D-2(新发现,致命)** |
| 双命令周期 | `sim/mixed_ops.py`/`correlated_storage.py`/`realism.py` | `plc/03_Functions.st:146-161` `FC_CalcDualCycleTime` | **见 §4 D-3(新发现,建议→中等)** |
| 驻留点/装卸档/AWRA-LS 内核 | 见 §5 | 见 §5 | 一致(已披露的设计决定或既有审查已覆盖)|

---

## 2. D-1(已知问题)的补强证据——不重复认定,只加固边界

D-1 本身(检测器档位错配:报告头条 98.5% 属 lexicographic 档,AC500 只实现 holistic 档,真实
81.6%/closed 0.0%)已由 `docs/对抗复审_0711pm.md` §3 与 `docs/overnight-report_0711.md` D-1 节
完整认定,本次不重新论证,只补一条此前未被引用的量化证据,回答任务书"确认边界,看有无衍生问题":

**`sim/out/detector_rules.md`(lexicographic 档标定表,报告 §3.6 明确引用为"标定表原样")12 个场景
的推荐里,10/12 推荐 `tob` 或 `cb`——PLC 完全无法执行的两个策略;只有 2/12(light_sparse/heavy_sparse)
落在 PLC 能执行的 `awra`。** 也就是说 lexicographic 档不是"边界情况下才推荐不了的策略",而是
"标定表 83% 的场景都推荐 PLC 做不到的策略"——这条标定表本身,如果字面上被搬到 PLC,十次里有八次会
尝试调用不存在的 CB/TOB 执行器。报告草稿 `docs/报告草稿_B1B2B10_0711pm.md:326-328` 把这张三行规则表
(density≥0.70→CB / density≤0.25∧n>20→AWRA-LS / 其余→TOB)当作"检测器决策依据表"直接呈现,
**这三行里有两行(CB、TOB)对应的执行器 PLC 策略库里不存在**,是 D-1 在报告正文里最具体的落点,
建议与 D-1 的方向 A/C 一并处理(不单独编号)。

---

## 3. D-2(新发现·致命):"场景自适应权重策略表"是 PLC 上的死代码,且未被任何既有审查发现

### 3.1 sim 侧:这是"H 口径"(头条数字唯一来源)的官方定义组成部分之一,不是边缘实验

- `docs/canonical_assumptions.md:38`:"报告主口径 H(2026-07-04 用户拍板①②)= 梯形加减速(A4b)+
  **场景自适应权重策略表(E v2)**"。`:86,120` 重复此定义,`:120` 明确"2026-07-04 v2.0(用户拍板落地)"。
- `现状与任务.md:70-71`:"**主口径 H**(0704 三拍板落地)= 梯形加减速 + **场景自适应权重策略表**;
  头条数字唯一来源 `python sim/headline.py`"。
- `sim/headline.py:4-5`(docstring):"H 口径 = 梯形加减速(A4b,拍板②)+ 场景自适应权重(A1/T11,拍板①)";
  `:28-38` 的 `run_five()` 在 `adaptive=True`(H 口径分支,`:68` `H = caliber(accel=True, adaptive=True)`)
  下显式调用 `ws.lookup_weights(len(goods), "skew", "online"/"batch")` 取场景相关的 (δ, β+γ),
  **不是固定默认值**。
- `sim/warehouse_sim.py:220-230` `WEIGHT_POLICY` 字典(18 项,密度 3 档×分布 3 档×模式 2 档)+
  `:233-237` `lookup_weights()`;`:234` 注释原文:"场景→权重查表(**PLC 侧对应 plc/08 的
  aPolicyDelta/aPolicyBG**)"——这条注释本身就是一个需要被证伪或证实的断言。
  `sim/adaptive_weights.py`(全文件)是标定+生成脚本,`:156-161` 直接把生成的 ST 代码写入
  `plc/08_GVL_WeightPolicy_generated.st`。
- 该机制被至少 7 个 sim 脚本复用(`headline.py`/`correlated_storage.py:220-221`/
  `energy_report.py:106-107`/`mixed_ops.py:124-125`/`realism.py:143-144,164-165`/
  `scan_g2g4.py:73-74`/`warehouse_sim.py:487-488` CLI 分支),不是孤立小实验。
- `1_给你看/实验发现.md:209`(F13"A1 场景自适应权重")+`:226-228`(F14"报告主口径 H 头条数字"明确写
  "H 口径 = 梯形加减速 + 场景自适应权重策略表")——F13 被单独列为一条可写入报告"创新点"的发现
  (查表增益均值 3.51%/峰值 7.27%,exp_t 指标)。

### 3.2 PLC 侧:数据表在,消费逻辑一行都没有

- `plc/08_GVL_WeightPolicy_generated.st`(全文件,19 行):`aPolicyDelta`/`aPolicyBG` 两个
  `ARRAY[0..2,0..2,0..1]` 常量数组确实存在,且**数值与当前 `sim/warehouse_sim.py:220-230` 的
  `WEIGHT_POLICY` 逐一手工核对完全一致**(18 项 δ 与 β+γ 按 `(iDensity,iDist,xBatch)` 展开顺序
  逐位相同)——**数据本身没有过期或漂移**,问题不在数据。
- 但 `:5` 注释"…按库存重量均值与频次变异系数判,**见 FC_ClassifyScene**"——`FC_ClassifyScene`
  **在全仓库 `plc/*.st` 里不存在**(全目录 grep 零命中,只有这一处注释提到它的名字)。
- `:16-19` 唯一展示"如何使用这张表"的代码(`GVL_Param.rDelta := aPolicyDelta[iDensity, iDist,
  SEL(xBatch,0,1)];...`)**整段在 `(* … *)` 注释块内**,不是可执行代码。
- `iDensity`/`iDist`/`xBatch` 三个索引变量**在全仓库 `plc/*.st` 里没有任何一处被声明为真实变量**
  (全目录 grep 零命中,除上述注释外)。`aPolicyDelta`/`aPolicyBG` 同样**在其自身声明文件之外,
  全仓库零处被索引/读取**。
- 实际生效的运行时权重是纯静态常量:`plc/02_GVL.st:54-56`——`rBeta:=0.6`、`rGamma:=0.4`、
  `rDelta:=0.15`,固定默认值,与场景无关。
- 这三个变量仅有的"动态"出现在 `plc/04_FB_Warehouse.st:1060-1111` `FB_ParamGuard`(A4 权限守卫,
  `:1087-1088,1104-1105` 逐字出现 `rAlpha/rBeta/rGamma/rDelta`)——但这是"管理员手动在 HMI 调参区
  改值 → 操作员级每周期回滚到快照"的**人工调参 + 越权保护**机制,与"按批次画像自动切换"是完全不同
  的两件事,和 `iDensity/iDist` 分类无关。
- `plc/05_PRG_Main.st:131,137-138`(`STATE_ASSIGN` 分派 `fbAssign(xStart:=xKickAssign,
  xUseRank:=xUseRank, iStrategy:=iStrat)`)——调用参数里没有任何权重相关输入,证实 `FB_AssignAllGoods`
  内部只会读 `GVL_Param.rDelta/rBeta/rGamma` 这几个静态全局量,PRG_Main 从未在进入 ASSIGN 前做过
  场景分类或权重切换。
- **T25 端到端护栏("PLC 忠实实现 AWRA-LS"的旗舰证据)本身就是用静态默认权重生成的,天然测不出这个洞**:
  `sim/export_st_vectors.py:28`——`score_fn = ws.make_score_fn(1.0, 0.6, 0.4, 0.15, w_max, f_max)`,
  注释"与 canonical E **默认**一致"。也就是说 T25 只验证了"PLC 在固定默认权重下的 AWRA-LS 与 sim
  一致"(这条本身是真的、已验证),从未也不可能验证自适应权重机制——因为 PLC 根本没有这个机制可测。

### 3.3 "看起来已完成"的假象从何而来(反向核实,避免误判)

- `现状与任务.md:110`:"附带收益:①三个**从未进过工程**的对象入列(FB_VisuRefresh/FC_StateToColor/
  **GVL_WeightPolicy**——批次 C 的'重贴 4 对象'环节被提前消化…)"——`GVL_WeightPolicy` 在 0706 被
  `ab_sync` 自动化管线**编译进了 AB 工程**(对象存在、编译通过),这是"进了工程"与"被使用"被混为一谈
  的根源。
- `tools/ab_scripting/sync_result.txt:48`:"SYNCED: GVL_WeightPolicy (gvl, decl 622 ch, **impl - ch**,
  via replace())"——同步日志自己写着"impl(实现)0 字符",数据声明有 622 字符、实现代码 0 字符,
  与本次发现完全吻合(GVL 类对象本身没有实现段是正常的,但这恰恰说明"同步成功=编译通过"不能
  等价于"逻辑已接入"——本条日志是我在排查中用来交叉验证的旁证,不是新发现的来源)。
- **反向验证方法论没有问题**:同为"生成文件"的 `plc/07_GVL_Data_generated.st`(演示批数据+T19/T20/T25
  测试向量)经 grep 确认 `aTestVec`/`aAwraExpect`/`FC_LoadDemoGoods` 在 `03_Functions.st`/
  `05_PRG_Main.st`/`06_PRG_Test.st` 三处均被真实引用——证明"sim 生成 ST 文件"这个模式本身没问题,
  07 号文件是接好的,08 号文件是唯一的例外。

### 3.4 报告/演示是否引用了 PLC 没有的东西

- **是,且是以"官方口径定义"的强度引用的**:`canonical_assumptions.md`(项目自称"唯一真相源",
  `现状与任务.md:6` 规定"建模假设/指标口径只认 docs/canonical_assumptions.md")把这个机制写进了
  H 口径的**定义**里,不是可有可无的一句话。任何后续报告写作(B1/B2/B10 之外的章节尚未成稿)如果
  照抄 `实验发现.md` F13/F14 或 canonical 的原文,几乎必然会把"场景自适应权重策略表"写成已交付的
  PLC 能力。
- 当前 `docs/报告草稿_B1B2B10_0711pm.md` 全文 grep "自适应权重"**零命中**——即已成稿的 B1/B2/B10
  三节尚未触及这个坑,这是本次审查唯一的好消息:**坑还没被写进报告正文,现在处理成本最低**。

### 3.5 影响幅度(避免夸大——如实报告缓解证据)

`1_给你看/实验发现.md:209-223`(F13)团队自己的实验显示,自适应权重相对固定默认的增益"均值 3.51%/
峰值 7.27%"(exp_t 指标,`verify_policy.py` 留出 seed 交叉验证通过)——**即"PLC 缺这个机制"对
期望取货时间这一项的实际数字影响,按项目自己的量化,大概率是个位数百分比级别,不是数量级错误**。
但这不改变结构性结论:这个机制在 PLC 上 100% 不存在,而它是 H 口径定义的一半,评委若要求"用 ST
代码逐行讲解自适应权重怎么切换",现场答不出来。

### 3.6 建议

1. **最低成本**:在 canonical/现状与任务/未来报告章节里,把"场景自适应权重策略表"明确标注为
   **"sim 侧已验证的算法增强,当前 PLC 版本未接入(ST 侧待办)"**,与 `docs/驻留点设计_0708.md` 处理
   "last/demand 驻留点策略"的方式一致(该文档就是本项目"诚实标注 sim-only"的正面范例,见 §5)。
2. **中等成本(若时间允许,报告周或决赛前)**:补写 `FC_ClassifyScene`(按 `08_GVL` 注释的 iDensity
   <55%/<85%/其余、iDist 按重量均值+频次变异系数)+ 在 `PRG_Main` 进入 `STATE_ASSIGN` 前调用它并索引
   `aPolicyDelta/aPolicyBG` 写回 `GVL_Param.rDelta/rBeta/rGamma`——工作量对照 A2(FB_SceneDetect)
   量级,**且需要重新生成 T25 黄金向量(export_st_vectors.py 要改用 adaptive 权重)并重跑 ab_sync**。
3. 若采用方案 2,注意 `sim/headline.py` 硬编码 `case="skew"`(`:32-33`)与实际 `gen_goods` 生成的
   场景分布是否一致,这是权重表调用点的一个独立小细节,顺手核对。

---

## 4. D-3(新发现·建议,中等严重度):"双命令周期"只有公式级验证,没有真实运行模式

- **sim 侧**:`sim/mixed_ops.py`(全文件)/`sim/correlated_storage.py:180-203`/`sim/realism.py:77-127`/
  `sim/energy_report.py:46-71` 均围绕"双命令周期"(存取联程,dual-command cycle,AS/RS 经典概念)
  构建了完整的**多周期混合作业**实验:交替存取、联程节省%、吞吐次/h、能耗——是报告"混合作业吞吐"
  相关论述的数据来源(`sim/build_report.py:391,424,489-495`)。
- **PLC 侧**:`plc/03_Functions.st:146-161` `FC_CalcDualCycleTime` 正确实现了三段式行程时间公式
  (I/O→存位→取位→I/O),`plc/06_PRG_Test.st:146-148` T23 用例验证"已知值+不劣于单命令"——**公式本身
  是对的,且有测试覆盖**,这一点上比 D-2 情况好。
- **但**:全仓库 grep `FC_CalcDualCycleTime`,除了自身定义、T23 测试调用、README 提及外,
  **在 `04_FB_Warehouse.st`/`05_PRG_Main.st` 里零处被调用**——即 PLC 状态机(`01_DUTs.st:60-72`
  `E_MainState` 仅 IDLE/INIT/WAIT_INPUT/ASSIGN/IMPROVE/STATS/DONE/FAULT 八态)**没有任何"存取交替
  运行"的实际工作模式**,现有 12+4 步演示脚本(`docs/演示脚本v3_0711.md`)也没有一步尝试演示双命令
  运行。sim 那套"吞吐 X 次/h(双命令口径)"的多周期统计,在 PLC 上从未、也无法以当前状态机结构被
  复现为一次真实运行。
- **报告是否引用了 PLC 没有的东西**:程度较轻。`sim/build_report.py:424`(C10 口径定义行)与
  `:489-495`(第 3 章"物理与作业真实度"小节)把双命令周期作为**假设/方法论定义**呈现
  ("联程 T=t(0→存)+t(存→取)+t(取→0);较两个单命令省一次空驶,节省量≥0 由三角不等式保证"),
  没有直接宣称"AC500 现场跑出了这个吞吐提升"——比 D-1/D-2 更接近"如实的方法论声明",评委当场拆穿
  的路径需要多问一句"这个吞吐数字是仿真算的还是 PLC 跑出来的",不像 D-1 那样一眼screen+台词对不上。
- **建议**:报告写到"双命令周期"相关小节时加一句限定语,如"该吞吐/节省%数据来自 Python 多周期
  仿真;PLC 侧当前验证的是单次双命令行程时间公式的正确性(T23),尚未实现存取交替的持续运行模式"——
  与 D-2 的建议 1 属同一类"补限定语"低成本动作,可合并处理。

---

## 5. 一致项清单(逐条核实,确认覆盖,避免虚报problem)

以下各项经本次排查确认 sim 与 PLC**一致**,或"sim 有 PLC 无"但**已被诚实披露、非隐藏缺口**,
列出以证明排查覆盖面,不是只挑问题:

| 项 | sim 侧 | PLC 侧 | 结论 |
|---|---|---|---|
| 策略核心算法(rank/score/feasibility) | `warehouse_sim.py` 对应函数 | `plc/04_FB_Warehouse.st` 对应 FB | ✅ 一致,`docs/T2.1_一致性审计_gap表_0707.md` 已逐段核对,仅 G1(0/390 触发)/G2(35/390 触发,exp_t≤1.09e-2s/energy≤7.18e-4,已披露)两处工程可忽略差异,非新问题 |
| 权重策略表**数值**(不含消费逻辑) | `warehouse_sim.py:220-230` `WEIGHT_POLICY` | `plc/08_GVL_WeightPolicy_generated.st:10-13` | ✅ 18 项数值逐一核对完全一致(本次手工核对),数据未过期;消费逻辑缺失见 D-2,是两件事 |
| 驻留点(dwell-point) | `sim/dwell_point.py`+`docs/驻留点设计_0708.md` 4 策略实验 | 无 DWELL 态,固定停 I/O(0,0) | ✅ 一致(诚实披露):`驻留点设计_0708.md:5`"ST 侧判 YAGNI 零改动",exhaustive 枚举证明官方 io 口径已是最优,PLC 不需要变。报告若引用此发现,不构成"sim 有 PLC 无"的问题,因为**没有任何文档声称 PLC 实现了 last/center/demand** |
| 装卸时间三档(U2) | `warehouse_sim.py:95-107` `handle_time`/`cycle_time_laden` | `plc/03_Functions.st:388-392` `FC_HandleTime`+`02_GVL.st:43-47` | ✅ 一致,双方均明确"不进评分链路"(`02_GVL.st:41`注释;报告 F23 三探针证零影响),自我披露口径一致 |
| 双命令周期**公式** | `warehouse_sim.py:64` `travel_time` 语义 | `plc/03_Functions.st:149-161` `FC_CalcDualCycleTime`,T23 验证 | ✅ 公式一致;**运行模式**缺失见 D-3 |
| 演示画面数值真实性 | 头条数字(62.0%/67.3%/230次h 等)仅存在于 sim 报告/PPT 层 | `演示脚本v3_0711.md` 全 12+4 步逐条核对,画面显示均为 PLC 原生统计量(Total inbound≈186.0、UtilPct=0.4、Handling=7.00s 等) | ✅ 一致,HMI 画面没有伪造/硬编码头条百分比数字冒充"实时算出"(全 `plc/*.st` grep 头条数值字面量,除 D-1 已知的口头台词错配外,无第二处) |
| SelStrategy 未覆盖的 sim 策略(random/cb/tob) | `strategy_lib.py` 7 策略 | `02_GVL.st:117` 仅 4 档 | ⚠️ 即 D-1 范围内的已知差集,报告/技术方向总库对 cb/tob 的引用均限定在"sim 侧 7 策略对比实验"语境,未见把 cb/tob 包装成 PLC 能力的独立新增问题 |

---

## 6. 轻量观察点(不构成独立编号问题,顺手记录)

1. **A5"真机标称"措辞需在报告最终稿保持限定语**:`docs/A5执行时间实测_0711.md:3-6,33-34` 已明确
   自认这组数字(192/560/2056/1880 周期→1.92/5.60/20.6/18.8s)是"AB PC 仿真周期数 × 10ms 任务标称"
   的**换算估算值**,并非物理 AC500 实测("真机行值待借到实体 AC500 补测")。本次抽查
   `技术方向总库_0711.md:20`、`现状与任务.md` 相关引用均未丢掉这层限定,**当前无违规**,只是提醒
   报告周精修/口语化压缩文字时,不要把"标称预估"简化成"AC500 实测"。
2. **"A1"编号在项目内有两个不同所指**:`技术方向总库_0711.md` 的 A1 = oracle gap 量化实验;
   `sim/adaptive_weights.py` 文档字符串与 `实验发现.md` F13 的"A1" = 场景自适应权重策略表
   (T11)。两者是完全不同的两件事,同名不同指,纯文档卫生问题,建议未来引用时用更具体的名字
   (如"检测器实验"vs"权重表实验")避免后续写作时张冠李戴。

---

## 7. 评委对照 sim+PLC 代码可当场拆穿的点(汇总排序)

1. **D-1(已知)**:演示画面显示 `REC=AWRA_HOLISTIC`,解说词却说"达事后最优 98.5%"——98.5% 是
   lexicographic 档数字,与屏幕上跑的 holistic 档无关;该场景(tiny_light)下 holistic 真实值 68.5%,
   是全库最差。**拆穿方式:看一眼演示画面 + 听一句解说词,不需要读代码。**
2. **D-2(新发现)**:问一句"自适应权重策略表在哪段 ST 代码里生效"——`grep aPolicyDelta plc/*.st`
   只会找到它自己的声明文件,`FC_ClassifyScene` 整个仓库不存在。**拆穿方式:需要读代码或现场追问,
   比 D-1 隐蔽,但只要评委拿到源码(AC500 实现 30% 评分项通常意味着会看代码)几分钟内可定位。**
3. **D-1 衍生**:报告 `报告草稿_B1B2B10_0711pm.md:326-328` 的"检测器决策依据表"三行有两行
   (CB/TOB)对应 PLC 不存在的执行器——**拆穿方式:对照 `02_GVL.st:117` 的 SelStrategy 枚举,
   一分钟可查。**
4. **D-3(新发现,较轻)**:追问"双命令周期的吞吐提升是仿真算的还是机器跑出来的"——诚实回答是
   "仿真算的,PLC 只验证了单次行程时间公式"。**拆穿方式:需要评委主动追问,当前报告文字本身
   没有过度声明,风险低于前三条。**

---

## 8. 处理优先级建议

按"评委发现概率 × 一旦发现的杀伤力 / 修复成本"排序:

1. D-1(已有三个方向待用户拍板,见 `overnight-report_0711.md`)—— 不重复,仅提醒:方向 A/C 的文案
   修改应**一并覆盖 §2 提到的报告 326-328 行三行决策表**,不要只改 B10 正文和演示台词。
2. D-2 §3.6 建议 1(把权重表标注为"sim 已验证、PLC 未接入")——**5 分钟文本改动,强烈建议今晚/
   报告动笔前就做**,防止 F13 被写手抄进正在撰写的后续报告章节(当前 B1/B2/B10 尚未涉及,是这个坑
   成本最低的窗口期)。
3. D-3 建议(补限定语)——与 D-2 建议 1 同批处理,成本同样很低。
4. D-2 §3.6 建议 2(真正实现 FC_ClassifyScene 接入)——中等工作量,需要用户拍板是否在剩余窗口期
   投入,不建议 overnight 自行决定。
5. §6 两条轻量观察点——顺手处理,不单独排期。
