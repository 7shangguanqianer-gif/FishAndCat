# PLC 侧使用说明(Automation Builder / AC500 V3)

> 本目录是 ST 源码骨架(文本形式)。Automation Builder(下称 AB)装好后按下述步骤导入,
> 无实体PLC时可在AB PC仿真模式检查有限逻辑；这不等于实体AC500完整运行或性能验证。
> 交付形式官方要求待确认(canonical D 清单),先按「AB 工程 + ST 源码」双备份准备。
> **0717 基线**：当前 `06_PRG_Test.st` 声明 **77 项全部为真实断言**(T01-T59 核心 ST/静态匀速黄金向量、T60-T75 轨B 平局统一/容量护栏/CB-TOB/隐患清扫、T76 取出演示四分支、T77 FC_TMax 加减速口径),在线读回铁证 **iPassed=77 / iFailed=0 / xAllPass=TRUE**(`tools/ab_scripting/logs/runtest_result_20260717_010514.txt`)。历史基线:76/0=0716(E7 取出演示)、59/0=0712(最早读回锚),引用需带日期。
> **⚠ 自己复现前先读 §2b**:两条规矩——①判据 `iPassed + iFailed ≡ N_CASES`,两数之和 ≠ 77 说明**跑的不是当前应用**,不是有用例失败;②**只认 `tools\ab_scripting\logs\` 里带时间戳的归档**,脚本目录下那两个 `*_result.txt` 是暂存文件,会被 git 操作改写。

## 1. 文件清单与导入对象对应

| 文件 | 导入为 | 说明 |
|---|---|---|
| 01_DUTs.st | 4 个 DUT(每个 TYPE 一个) | ST_Good / ST_Slot / ST_Stats / E_MainState |
| 02_GVL.st | 3 个 GVL | GVL_Param(常量段+变量段合一个,含 L1 加减速参数)/ GVL_WH / GVL_Visu |
| 03_Functions.st | 17 个 POU-函数 | FC_CapCoef 等纯函数 + FC_AxisTime(L1 梯形)+ FC_CalcDualCycleTime(L2 双命令)+ FC_StateToColor(L6 配色查表)+ **FC_MaintToggle**(A3 检修翻转)+ **FC_HeatColor / FC_BlendLight**(C2/C6 热力色阶、C1 层高亮混色,0711) |
| 04_FB_Warehouse.st | 16 个 POU-功能块 | Init / SelectSlot / AssignAllGoods / **AssignClassTurnover(CB/TOB，源码待AB复测)** / LocalSwapImprove / Stats / BuildVisuPath + **FB_AnimatePath**(L6 动画回放)+ **FB_ScanLoadProbe**(L4 AB PC仿真负载探针)+ **FB_VisuRefresh**(L6 颜色镜像)+ **FB_SceneDetect / FB_UserAuth / FB_ParamGuard** |
| 05_PRG_Main.st | 1 个 POU-程序 | 主状态机,挂循环任务 |
| 06_PRG_Test.st | 1 个 POU-程序 | 77 项自检全为真实断言(0717 在线 77/0 读回);含 T22 加减速向量、T74/T77 FC_TMax 边界与口径、T76 取出演示四分支 |
| 07_GVL_Data_generated.st | 2 DUT + 1 GVL + 1 函数 | **生成文件勿手改**,由 sim/export_st_vectors.py 重生(含 ExpTimeAccel + **T25 的 ST_AwraCell/aAwraExpect 终局向量 + LAM/MAX_LS 单源常量**,0707) |

## 2. 建工程步骤(AB 2.8+/AC500 V3)

1. 新建工程 → PLC AC500 V3 系列任选一款 CPU(如 PM5650;仿真模式与型号无关)。
2. Application 下按上表逐个"添加对象"(DUT / 全局变量列表 / POU),名称与代码里的一致,粘贴对应段落。
   - 粘贴时去掉 TYPE/FUNCTION 外层已由 AB 自动生成的重复声明(AB 建 POU 时会预置声明头,以文件里的为准覆盖)。
3. 任务配置:Task(循环,10ms)→ 挂 PRG_Main;PRG_Test 可挂同任务(默认不触发,置 xRunTests 才跑)。
4. 菜单 在线 → 仿真(Simulation)勾选 → 登录(Login)→ 运行(Run)。
5. 首次验证顺序:
   a. 自检基线：PRG_Test.xRunTests:=TRUE → **iPassed=77、iFailed=0**(0717 在线读回;76/0=0716、59/0=0712 为历史锚)。任何 ST 改动后必须重跑 `tools\ab_scripting\ab_sync.ps1` 取得新读回,源码计数本身不升级证据;**若读回不是 77/0,先按 §2b 判断是不是"跑的不是当前应用",不要先怀疑用例**;
   b. GVL_Visu.CmdLoadDemo := TRUE(载入 20 件演示货,与仿真同 seed 同源);
   c. GVL_Visu.SelStrategy := 3(AWRA-LS);CmdRunAssign := TRUE;
   d. 观察 fbAssign/fbImprove 分片推进(xBusy→xDone),看 GVL_WH.stStats:ViolCnt 必须=0。

## 2b. 复现 77/0 的两条规矩(0729 补)

**一句话**:①读回数少了先怀疑"跑的不是当前应用",别先怀疑用例;②证据只认 `logs\` 里的归档。

### 2b-0 理论陷阱:改过 `VAR CONSTANT` 后走在线更改登录,读回的是旧应用的旧常量

**自查判据(不用开 AB 就能判)**:汇总循环(`06_PRG_Test.st:966-972`)是
```
FOR i := 1 TO N_CASES DO
    IF aResult[i] THEN iPassed := iPassed + 1; ELSE iFailed := iFailed + 1; ... END_IF
END_FOR
```
每轮必给两个计数器之一加一,所以 **`iPassed + iFailed ≡ N_CASES` 恒成立**。
→ **读回两数之和 ≠ 当前 `N_CASES`(现为 77),说明跑的不是当前应用,而不是"有用例失败"。**
真有用例失败的样子是 `iPassed + iFailed = 77` 且 `iFailed > 0`,并且 `sLastFail` 会带上 `T<编号>`。

**机制根因**:
- `tools\ab_scripting\run_test.py:38` 是 `onapp.login(OnlineChangeOption.Try, True)` —— **在线更改**优先,不保证全量下载;
- `N_CASES : INT := 77` 声明在 `06_PRG_Test.st:12` 的 `VAR CONSTANT` 段,该行注释自己写着「常量化=N4-08,**在线不可改**」;
- 两者叠加 → 源码同步和编译都成功,新常量却没进到仿真 PLC 里跑的那份应用。

**上述陷阱是"能发生",不是"已发生"** —— 截至 0729,仓库里**没有任何一次读回被它咬到过**的证据。
之所以单独写这一节,是因为 0729 审计时差点把另一件事误判成它,见下。

### 2b-1 别把 `runtest_result.txt` 当证据:它是暂存输出,又被 git 跟踪,内容与 mtime 会被 git 操作改写

**误判经过(0729,已澄清)**:`tools\ab_scripting\runtest_result.txt` 的 mtime 是 **2026-07-27 21:44:26**,
内容 `iPassed=INT#76 / iFailed=INT#0`。看上去像"7/27 跑了一次,只拿到 76",于是先被归因为上面那个在线更改陷阱。

**实际不是。那天根本没跑 AB。** 四条独立证据:
1. 它与 `logs\runtest_result_20260716_135644.txt` **逐字节完全相同**(连 ScriptEngine 的 `dir()` 列表和
   `guid=74993588-...` 都一样);同批 `sync_result.txt` 与 `logs\sync_result_20260716_135644.txt` 也逐字节相同;
2. 两个文件的 mtime **相同到纳秒**(`21:44:26.018723200`)。而脚本是分两阶段写的,中间隔着编译——
   0716 那对归档就是 13:54 与 13:56,差两分钟。同纳秒只可能来自一次**复制/还原**;
3. `git reflog` 里有 `c9a3363 HEAD@{2026-07-27 21:44:26 -0500}: reset: moving to HEAD` —— **时间戳完全吻合**;
   同一刻被改写的还有 `l4_showcase\app_shell\package.json` 与 `package-lock.json`(对应 21:49 那次 QA 环境抢修);
4. `logs\` 里没有任何 0727 的归档,而 `ab_sync.ps1` 的归档是**无条件**的。

→ 那个 76 是 `git reset --hard` 把 **0716 提交的文件**还原回磁盘的结果,不是一次测试读回。
**最后一次真实 AB 场次仍是 0717(`logs\*_20260717_010514`,77/0)**,此后至今未再跑过。

**规矩(本节的实际价值)**:
- **只认 `logs\` 里带时间戳的归档副本**,那是 `ab_sync.ps1` 每轮无条件复制、不被覆盖的证据;
- **`tools\ab_scripting\` 根目录下的 `runtest_result.txt` / `sync_result.txt` 一律视为暂存**——
  每次运行会先 `Remove-Item` 再重建,而它们又在 git 里,任何 `reset` / `checkout` / `stash` 都会改写它们的内容与 mtime;
- 引用任何一次读回,**必须带上归档文件名里的时间戳**。

### 2b-2 下次重验怎么做(尚未实证,做完请回填本节)
1. 关掉 AB GUI(`ab_sync.ps1` 开头会拒绝在 GUI 开着时运行,防双实例毁工程);
2. 走完整 `powershell -File tools\ab_scripting\ab_sync.ps1`,**不要单独调 `run_test.py`** ——
   完整脚本才会归档日志并过 77/0 硬闸(该闸已于 0729 重写,见下);
3. 若真读回 `iPassed+iFailed < N_CASES`,再把 `run_test.py:38` 的 `OnlineChangeOption.Try` 改成 `Never`
   (禁在线更改、强制全量下载)后重跑 —— **此改法尚未实测,属待验证方案**;
4. 日志归档进 `logs\` 并 `git add`,再回写 `sim\out\plc_evidence.csv`
   (那是**手工登记源**,不是脚本产物,见 `sim\build_report.py:332`)。

**0729 已把判据做进 `ab_sync.ps1` 的硬闸**:它现在从 `06_PRG_Test.st` 读 `N_CASES`(不再硬编码 77),
并把两种失败分开报——`iPassed+iFailed ≠ N_CASES` 报 `!! STALE APPLICATION - this is NOT a test failure.`
并指回本节;和值相等而 `iFailed>0` 才报 `!! REAL TEST FAILURE` 并打印 `sLastFail`。
该闸门逻辑已用 0712/0716/0717 三份真实归档 + 一份合成的真失败日志实测过四条分支判定正确(未开 AB)。

## 3. 设计要点(答辩讲这几条)

- **扫描周期感知分片**:批量分配每周期只处理 nBatchPerCycle 件、局部搜索每周期 nPairsPerCycle 对,
  优化算法以非阻塞状态机跑在实时控制器上,不触发看门狗——这是"AI 算法落地 PLC"的关键工程手段。
- **有限一致性边界**:T19/T20 与 20件 T25 锁静态匀速黄金向量;near 平局顺序按 Python 统一(T60,已入 77/0 在线读回)。**加减速评分分母分叉已修**(0717 治理D:FC_TMax 随 xUseAccel,T77 断言匀速 38.0/加减速 39.667/tNorm≡1.0;披露见 docs/S3算法深审与治理方案_0716.md D-①)。REAL 单精度 vs Python 双精度差异仍在(容差 1e-3)。**"演示落位可在 PLC 复现"仍不可说**——行程模型(T22)与评分归一(T77)已同构验证,但同货物序列端到端逐格重放未做对拍。
- **边界判断成体系**:越界/负输入/超重/超容/预占/满仓/无可行位报警,全部有用例(T01-T18)。
- **口径开关**:xSimultaneousXY 切换切比雪夫(主口径)/顺序模型(对照),现场可演示两者差异。
- **操作侧当前边界(0717 口径)**:FB_SceneDetect holistic/lexicographic 切档与 CB/TOB 路由(`FB_AssignClassTurnover`)已入 77/0 在线读回(T61-T69/T75)。lexicographic 98.5% 仍只是 sim 在 `excess_fail=0` 可比域的评估,不是控制器读回。场景权重表(08_GVL_WeightPolicy)仍未接入运行时闭环(D-2 已知项)。检修语义:T73 已断言"冻结源位存量不被重定位搬走";权限是单客户端演示码+ST 回滚守卫,尚无多客户端隔离证据。

## 4. 已知注意项

- PLC REAL 为单精度,Python 为双精度:一致性比对容差 1e-3;如出现平局翻转导致选位偶发不一致,
  将 FC_CalcScore 及比较链改用 LREAL(AC500 V3 支持)即可,已预留说明。
- 07 是生成文件:改了 Python 评分函数/权重/场景参数,必须重跑 `python sim/export_st_vectors.py`
  并在 AB 里替换粘贴,否则 T19/T20 会红——红了先想是不是忘了同步,这是设计出来的护栏。
- **STRING 字面量已全部 ASCII 化(2026-07-05,W-005 实测后落地)**:中文字符串触发 AB 的
  C0555 编码警告,已把 05/04 里所有状态文本改为英文状态码(RESET_INIT / READY_PRECOUNT= /
  ERR_GOODS_FULL_400 / ERR_NEG_INPUT / SUGGEST_X=…_Y= / ALARM_NO_FEASIBLE_SLOT /
  DEMO_LOADED_N= / ERR_NO_GOODS / ASSIGN_RUN_PLACED= / IMPROVE_R=…_SWAPS= /
  DONE_FAILED_N= / DONE_OK / NO_SLOT_GOODS_ID=)。**AB 工程侧必须与本清单逐条一致**
  (Codex 首建时自改过部分,须按本清单对齐,消掉全部 C0555 警告);
  决赛可视化画面用静态中文标签解释状态码,变量字符串保持 ASCII。注释中文无碍。
- Task 挂载:标准做法是 Task 直接挂 PRG_Main/PRG_Test 两个调用;Codex 首建时用了
  "PLC_PRG 包一层再调用两者"的等效绕法(行为相同),保持现状即可——但"直接挂会
  not defined"的说法不成立,勿写进报告。
- 局部交换阶段 O(n²) 对数在 n=400 时约 8 万对/轮,按 nPairsPerCycle=200 需 ~400 周期/轮(10ms 任务 ≈ 4s/轮),
  演示可接受;若嫌慢调大 nPairsPerCycle(单周期 200 对评分 ≈ 微秒级,余量巨大)。
- **IEC ST 的 AND/OR 不短路**(两侧都求值,与 C/Python 直觉相反):`WHILE i >= 1 AND aF[i] < v`
  在 i=0 时仍会访问 aF[0] → 下标越界。守卫条件与数组访问必须分离(嵌套 IF + EXIT),
  见 FB_SceneDetect 插入排序(0711 首写即在自查中抓获)。AND_THEN 是 3.5 扩展,为可移植性不用。

## 4b. L4 负载实测怎么跑(W3,AB 仿真在线状态)

在 PRG_Main 的 STATE_ASSIGN / STATE_IMPROVE 分支里包夹分片调用:
```
fbProbe(xStart := TRUE);
fbAssign(...);                  (* 或 fbImprove(...) *)
fbProbe(xStop := TRUE);
```
在线观察 fbProbe.rAvgUs / rMaxUs / nSamples,记录成表:
「nBatchPerCycle=10 时单周期平均 X µs / 最大 Y µs,占 10ms 周期 Z%,看门狗裕量 N 倍」。
注:仿真模式跑在 PC 上,数值偏乐观——报告口径写"仿真实测+真机预估",若能借到实体 AC500 再补真机行。
**0706 终局(三时钟源全灭,口径转任务级)**:①LTIME 差分恒 0(0705-A 实测);
②任务监视页 Avg/Min 恒 0、Max=1024µs 时钟粒度噪声(0705-B 实测);③SysTimeGetNs 差分
恒 0(0706 自动化管线实测;SysTime 3.5.17 placeholder 引用+位置传参适配已入 09 文件)——
根因:PC 仿真时间服务按周期缓存/粒度粗于周期,**周期内 µs 在仿真环境不可测(如实记录)**。
**现行 L4 口径=任务级完成周期数**(探针 nSamples=周期计数器;确定性指标,真机同值;
  真机预估=周期数×10ms 标称):四组历史 AB 仿真数据 `sim/out/l4_task_cycles_data.csv`，参数说明见 `_params.csv`；
  源测量脚本已归档为 `tools/ab_scripting/archive/measure_l4b.py`（本轮未运行 AB）。

## 5. 决赛可视化(T17,ST 侧已就绪)

**完整搭建步骤见 `2_你要操作/AB可视化搭建操作卡.md`(零基础逐键说明)。** 架构要点:

- 20×20 网格 = 一个模板矩形绑 `GVL_Visu.VisuSlotColor[$FIRSTDIM$,$SECONDDIM$]`,
  用 AB/CODESYS 官方命令 **Multiply visu element(元件倍增)** 一次生成 400 格——
  不要手工复制 400 个矩形;
- 颜色由 PLC 侧 FB_VisuRefresh 每周期算好(FC_StateToColor 查表 + 上下翻转:显示行0=层19),
  画面元件不写死颜色,改配色只改 FC_StateToColor;
- 堆垛机图元设计位置放 (0,0),Absolute movement 绑 VisuCraneXpx/Ypx(FB_VisuRefresh 换算,
  几何常量 GRID_X0/Y0、CELL_PX_W/H 在 GVL_Param);
- 输入区绑 InGood* 与 Cmd* 按钮(Tap 方式,程序内做沿检测),动画按钮=CmdAnimate,
  报警灯=VisuAlarm;状态码为 ASCII(见 §4),画面用静态中文标签作对照解释。
- 演示脚本(六步:初始状态→轻高频→重货→批量→算法对比→超重报警)已细化到按钮级,
  见操作卡 §6;录屏建议同卡 §7。
