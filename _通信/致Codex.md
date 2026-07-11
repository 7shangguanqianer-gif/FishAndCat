# 致 Codex(Claude 签发的任务信箱)

> 机制:Claude 把给 Codex 的任务写在本文件;Codex 读完执行,把结果写进同目录 `致Claude.md`
> (追加,带日期标题,不删旧内容);用户只需对 Codex 说固定一句:
> **"读 F:\abb_wh_work\_通信\致Codex.md 并执行,结果写进 致Claude.md"**。
> Codex 通用纪律:先读 docs\Codex总对接提示词.md;只执行本文件任务,不自由发挥;
> 遇到与预期不符→停下,把现象写进 致Claude.md 等裁决。

---

## 批次 2026-0711-N「Overnight 审核+红队」(7 小时无人值守窗口,13:20-20:20;用户不在场)

### 背景快照(读完即可开工,不必翻历史)
- 项目=2026 ABB杯「智储优控」,F:\abb_wh_work;真相源=docs\技术方向总库_0711.md +
  现状与任务.md §5 + docs\画面三页制施工蓝图_0711.md。
- 当前状态:ST 侧全清(ab_sync **59/0**);画面三页制施工完成(P1 VisuMain 505 件/
  P2 VisuStats 134 件/P3 VisuAdmin 67 件,audit 真重叠 0);17 处输入动作 GUI 洗完
  (commit 806b709);编译 0 error/1 warning(历史项)。
- **Claude 正在同一台机器上做 GUI 长跑验证(占用 Automation Builder)并串行推进
  B1-B4(文档审计/ST 审/sim 审/报告草稿)**。你的角色=独立审核员+规划红队,双盲对照。

### 铁律红线(违反=事故,每条都有历史事故背书)
1. **禁开 Automation Builder,禁跑 tools\ab_scripting\ 下任何脚本(含 ab_sync.ps1)**——
   ScriptEngine 即使 headless 也会起 AutomationBuilder.exe 进程,双实例=工程锁事故;
   Claude 此刻正占用 AB。
2. **禁一切 git 操作**(add/commit/push/restore/stash 全禁)——同仓双写会话竞态有 0705
   实案;你的产出由 Claude 每小时收割统一 commit。
3. **禁修改任何现有文件**;只允许:读全仓库 + 新建你自己的产出文件(统一放
   `_通信\codex_out\` 目录,不存在就创建)+ 在 `_通信\致Claude.md` 顶部追加回执。
4. 禁改 1_给你看\、2_你要操作\ 下任何文档(用户文档红线)。
5. 允许跑**不起 AB 进程的纯 Python 只读分析**(解析 plc\*.st 文本、sim\out\*.csv、
   已 dump 的 XML 等);任何写盘脚本只准写进 codex_out\。
6. **双盲纪律:不要读 Claude 本窗口的审查产出**(docs\ 下文件名含 `_0711pm` 的一律不读;
   `_通信\致Codex.md` 本文件的滚动追加区除外)——双盲对照的价值就在互不污染,
   收尾 diff 由 Claude 做。
7. 负结果如实报;引用数字必带来源(命令或文件:行);发现疑似 bug **只列不改**,
   标严重度:阻塞(影响正确性/比赛交付)/建议(健壮性)/风格。

### 任务队列(按序做,每完成一项立即回执)
- **K1 · ST 全量代码审查** → 产出 `_通信\codex_out\K1_ST审查_0711N.md`
  范围:plc\*.st 全部;重点=0711 新增 POU:FB_SceneDetect / FC_MaintToggle / FB_UserAuth /
  FB_ParamGuard / FC_HeatColor / FC_BlendLight / FB_VisuRefresh(三视图)/ CmdViewCycle 相关。
  视角:IEC 61131-3 陷阱(AND 无短路求值、单字母保留字 r/s、数组越界守卫、边界条件、
  除零、类型溢出)、状态机死角、Reset 语义一致性。
- **K2 · sim 代码审查** → `_通信\codex_out\K2_sim审查_0711N.md`
  范围:sim\oracle_gap.py 及其依赖链;核对:seed 固定、统计口径、词典序 VBS/SBS 判定
  逻辑(fail 一票否决)、可复现命令是否与 docs 声称一致、CSV 输出与 summary 数字同源。
- **K3 · 文档一致性审计** → `_通信\codex_out\K3_一致性审计_0711N.md`
  交叉核对五处关键数字口径是否全同步:docs\技术方向总库_0711.md / 现状与任务.md /
  docs\画面三页制施工蓝图_0711.md / plc\README_PLC.md / 桌面「智储优控_作战面板.html」
  (C:\Users\86177\Desktop)。核对项:59/0 用例、洗单 17、三页元素数 505/134/67、
  oracle 98.5%·closed 93.3%、A5 四组周期(192/560/2056/1880)、检测器三档 gap。只列不一致+建议。
- **K4 · 红队推演+计划草案** → `_通信\codex_out\K4_红队与计划_0711N.md`
  对 docs\技术方向总库_0711.md 的 A(本期)/B(报告周)/C(候补)池做对抗审查:
  隐藏约束、失效模式、排期风险(硬节点:AB 许可≈8/2 到期、8/15 自定目标、8/26 提交);
  给出 7/12-19 的逐日计划草案(红队版,标注每项依据)。
- **K5 · 循环审(队列清完且时间未到)**:轮询本文件底部「滚动追加区」,Claude 会把
  新产出索引贴在那里;逐份复审(此时双盲已由 Claude 解除的才审),意见写
  `_通信\codex_out\K5_增量复审_0711N.md`(追加式)。

### 回执协议
每完成一项,在 `_通信\致Claude.md` **顶部**追加一行(不删旧内容):
`[HH:MM] K# 完成 | 产出路径 | 一句话结论(含最重要的 1 个 finding)`

### 结束条件
约 20:20 或用户出现即停手,最后在 致Claude.md 写汇总回执(完成项/最重要 3 发现/未完项)。

### 滚动追加区(Claude 每小时更新,Codex 每轮开工前看一眼)
- (暂无)

---

## 批次 2026-07-06-D(✅已由 Claude 的 AB 自动化管线直接完成,Codex 无需执行,存档备查)

### ✅完成记录(2026-07-06,Claude ScriptEngine 管线)
重贴/编译/测试全部由 `tools/ab_scripting/ab_sync.ps1` 无头完成:34 对象同步(含新建
FB_VisuRefresh/FC_StateToColor/GVL_WeightPolicy 三个从未进工程的对象)、Compile 0 errors、
在线仿真实测 **iPassed=24 / iFailed=0 / xAllPass=TRUE**(T24=官方口径 133 格断言)。
顺手消灭潜伏 bug:FB_VisuRefresh 曾用保留字 r 作循环变量(r/s=IEC 置复位限定符),已改 rw。
以下原任务文本存档备查:

### 背景(一句话)
官方答复了预占用规则:**x+y 之和能被 3 整除(133 格,含 (0,0),呈对角条纹)**——
Python 侧已全链切换,ST 源文件已同步更新;本批=把新 ST 文件贴进 AB 工程并回归。

### 任务:重贴 6 个文件 + 回归 24 用例(预计 15 分钟)

1. 打开 `plc\AB_Project\ABB_WH.project`;
2. **逐个替换粘贴**下列 6 个文件的全文(源文件在 `F:\abb_wh_work\plc\`;AB 里打开同名对象
   → Ctrl+A 全选 → 粘贴对应 .st 文件的全部内容;和首建时同一套动作):
   - 02_GVL.st(GVL_Param:iPreRule 默认已改 3)
   - 03_Functions.st(FC_IsPresetOccupied 新增 sum 分支)
   - 04_FB_Warehouse.st(注释更新)
   - 06_PRG_Test.st(**新增 T24,用例总数 24**)
   - 07_GVL_Data_generated.st、08_GVL_WeightPolicy_generated.st(生成文件,整文件替换)
3. F11 编译 → 期望 **0 error**(仅通信加密提示 warning 可忽略);
4. Simulation → Login → Start → PRG_Test.xRunTests := TRUE →
   期望 **iPassed=24, iFailed=0**,截图存 `plc\验收截图\W2_PRGTest_24pass_sumRule.png`(待产出);
5. GVL_Visu:CmdReset=TRUE → 状态文本应为 **READY_PRECOUNT=133**(不再是 49),
   截图存 `plc\验收截图\W2_precount133.png`(待产出);
6. 全部结果(编译/iPassed/READY_PRECOUNT 三个数)写进 致Claude.md,批次号 0706-D。

### 禁止事项(本批次)
- 只做"替换粘贴+编译+跑测试+截图",不改任何代码内容;
- 若 iPassed≠24 或编译报错:停,把错误窗口截图写进 致Claude.md,不要自己修。

---

## 批次 2026-07-05-B(✅已执行并回执,0706 已处理:监视页路线证伪→任务级口径落地,数据进报告;存档备查)

### 背景(为什么换方法)

上一批 FB_ScanLoadProbe 的 LTIME() 差分在 AB 仿真里恒为 0(PC 仿真计时分辨率问题,
不是你的操作问题)。本批改用 **AB 自带的任务监视页官方读数**——零代码改动,读数是
CODESYS 调度器自己的统计,不依赖 LTIME。
另一个修正:演示批次只有 20 件货,所以上一批的 nBatchPerCycle=50 和 100 两组**等效**
(一个周期就把 20 件全处理完了)——本批分组重新设计,让"单周期分片重量"真正拉开差距。

### 任务 1:任务监视页抄表(L4 负载实测,唯一任务)

**打开监视页**:Simulation → Login → Start 之后,双击设备树里的
**Task Configuration(任务配置)** → 切到 **Monitor(监视)** 标签页。
应能看到每个任务一行,列大致为:Status(状态)/ IEC-Cycle Count(周期计数)/
Cycle Time(周期时间)/ Average Cycle Time(平均周期)/ Max. Cycle Time(最大周期)/
Min. Cycle Time(最小周期)/ Jitter(抖动),单位 µs。
**先确认这些列会动、且不是恒 0**;若恒 0 或没有该标签页 → 停,截图写进 致Claude.md,不要自己想别的办法。

**统计清零方法**:在监视页任务行上**右键 → Reset(复位统计)**;若右键菜单没有 Reset,
就用 Logout → Login → Start 代替(重新登录统计自动清零)。每组测量前必须清零一次。

**每组固定流程**(共 4 组,逐组做):

1. 在线把参数写为该组值(GVL_Param 里双击 Prepared value 写入 → Ctrl+F7 生效);
2. 统计清零(右键 Reset 或重登录);
3. GVL_Visu:CmdReset=TRUE → CmdLoadDemo=TRUE → SelStrategy=3 → CmdRunAssign=TRUE;
4. 等 VisuStatusText = DONE_OK;
5. **立即**抄监视页该任务行:Average / Max / Min Cycle Time + Cycle Count,
   并截图存 `F:\abb_wh_work\plc\验收截图\L4_monitor_组名.png`(待产出,组名=IDLE/A/B/C);
6. 下一组。

| 组 | 参数设置 | 单周期分片重量(预期) | 截图名 |
|---|---|---|---|
| IDLE | 默认参数,清零后**不按任何 Cmd**,空跑约 30 秒后抄表 | 背景开销基线 | L4_monitor_IDLE.png |
| A | nBatchPerCycle=1(其余默认) | 每周期 1 件×400 仓位评分 | L4_monitor_A.png |
| B | nBatchPerCycle=20(其余默认) | 每周期 20 件×400 仓位评分(20件一口吃完) | L4_monitor_B.png |
| C | nBatchPerCycle=20 且 nPairsPerCycle=2000 | 局部搜索每周期 2000 对(默认200的10倍) | L4_monitor_C.png |

**记录表**(填进 致Claude.md):

| 组 | Avg Cycle µs | Max Cycle µs | Min Cycle µs | Cycle Count | 备注 |
|---|---|---|---|---|---|
| IDLE | | | | | |
| A | | | | | |
| B | | | | | |
| C | | | | | |

预期解读(供你核对是否异常,不用写报告):Max 应随分片重量上升(B、C 组明显高于 IDLE);
若四组 Max 几乎一样,如实记录,别修饰。

**收尾**:全部做完后 Logout(在线写的参数值自动失效,回到源代码默认值 10/200,
不需要手工改回);确认没有改过任何代码窗口。

### 禁止事项(本批次)
- **零代码改动**:不打开任何 POU 的编辑窗,只在线写 GVL_Param 两个变量 + 按 GVL_Visu 按钮;
- 不动可视化对象;不改权重参数;不置 xRunTests;
- 监视页读数恒 0 或界面与描述不符 → 停下截图汇报,不自由发挥。

---
(历史批次归档在本文件底部,由 Claude 维护)

## 已归档批次

### 批次 2026-07-05-A(已完成,汇报见 致Claude.md 同名批次;结论已进 现状与任务.md §5)

任务 1 PRG_Test 回归重验:run_all 全绿+AB 编译 0E;截图时间戳后续已核验闭环。
任务 2 L4 探针实测:探针被周期调用(nSamples 三组递增)但 LTIME 差分恒 0 → 催生本 B 批次换官方监视页读数。
