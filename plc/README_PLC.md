# PLC 侧使用说明(Automation Builder / AC500 V3)

> 本目录是 ST 源码骨架(文本形式)。Automation Builder(下称 AB)装好后按下述步骤导入,
> 无实体 PLC 也能在仿真模式下完整运行(初赛口径足够)。
> 交付形式官方要求待确认(canonical D 清单),先按「AB 工程 + ST 源码」双备份准备。

## 1. 文件清单与导入对象对应

| 文件 | 导入为 | 说明 |
|---|---|---|
| 01_DUTs.st | 4 个 DUT(每个 TYPE 一个) | ST_Good / ST_Slot / ST_Stats / E_MainState |
| 02_GVL.st | 3 个 GVL | GVL_Param(常量段+变量段合一个,含 L1 加减速参数)/ GVL_WH / GVL_Visu |
| 03_Functions.st | 15 个 POU-函数 | FC_CapCoef 等纯函数 + FC_AxisTime(L1 梯形)+ FC_CalcDualCycleTime(L2 双命令)+ FC_StateToColor(L6 配色查表)+ **FC_MaintToggle**(A3 检修翻转)+ **FC_HeatColor / FC_BlendLight**(C2/C6 热力色阶、C1 层高亮混色,0711) |
| 04_FB_Warehouse.st | 12 个 POU-功能块 | Init / SelectSlot / AssignAllGoods / LocalSwapImprove / Stats / BuildVisuPath + **FB_AnimatePath**(L6 动画回放)+ **FB_ScanLoadProbe**(L4 负载实测)+ **FB_VisuRefresh**(L6 颜色镜像)+ **FB_SceneDetect / FB_UserAuth / FB_ParamGuard**(A2 检测器/A4 两级权限,0711) |
| 05_PRG_Main.st | 1 个 POU-程序 | 主状态机,挂循环任务 |
| 06_PRG_Test.st | 1 个 POU-程序 | 23 个边界+一致性用例(T22 加减速向量/T23 双命令) |
| 07_GVL_Data_generated.st | 2 DUT + 1 GVL + 1 函数 | **生成文件勿手改**,由 sim/export_st_vectors.py 重生(含 ExpTimeAccel + **T25 的 ST_AwraCell/aAwraExpect 终局向量 + LAM/MAX_LS 单源常量**,0707) |

## 2. 建工程步骤(AB 2.8+/AC500 V3)

1. 新建工程 → PLC AC500 V3 系列任选一款 CPU(如 PM5650;仿真模式与型号无关)。
2. Application 下按上表逐个"添加对象"(DUT / 全局变量列表 / POU),名称与代码里的一致,粘贴对应段落。
   - 粘贴时去掉 TYPE/FUNCTION 外层已由 AB 自动生成的重复声明(AB 建 POU 时会预置声明头,以文件里的为准覆盖)。
3. 任务配置:Task(循环,10ms)→ 挂 PRG_Main;PRG_Test 可挂同任务(默认不触发,置 xRunTests 才跑)。
4. 菜单 在线 → 仿真(Simulation)勾选 → 登录(Login)→ 运行(Run)。
5. 首次验证顺序:
   a. PRG_Test.xRunTests := TRUE → 期望 **iPassed=59**, iFailed=0(T19/T20/T22 一致性向量,T23 双命令,T24 预占格数 133,T25 AWRA 端到端,T26-T40 边界扩充,T41 FB_GoodsInput 封装,T42-T45 块3 查询/翻页/装卸/载货,T46-T56 检修挂起/场景检测器/两级权限,**T57-T59 热力色阶/仓位履历/层高亮——0711 A2-A4+C1/C2/C6**;iAwraPosDiff 逐位分歧预期 0);由 ScriptEngine 管线 `ab_sync.ps1` 实跑验证(判定串同步 59/0);
   b. GVL_Visu.CmdLoadDemo := TRUE(载入 20 件演示货,与仿真同 seed 同源);
   c. GVL_Visu.SelStrategy := 3(AWRA-LS);CmdRunAssign := TRUE;
   d. 观察 fbAssign/fbImprove 分片推进(xBusy→xDone),看 GVL_WH.stStats:ViolCnt 必须=0。

## 3. 设计要点(答辩讲这几条)

- **扫描周期感知分片**:批量分配每周期只处理 nBatchPerCycle 件、局部搜索每周期 nPairsPerCycle 对,
  优化算法以非阻塞状态机跑在实时控制器上,不触发看门狗——这是"AI 算法落地 PLC"的关键工程手段。
- **与 Python 仿真同源**:评分函数逐项对齐 + 测试向量自动生成比对(T19/T20)+ 演示批次同 seed,
  验证报告里的数字与 PLC 演示互相背书。
- **边界判断成体系**:越界/负输入/超重/超容/预占/满仓/无可行位报警,全部有用例(T01-T18)。
- **口径开关**:xSimultaneousXY 切换切比雪夫(主口径)/顺序模型(对照),现场可演示两者差异。
- **操作侧完备性(0711 A2-A4,对标同类赛项原文要求项)**:场景检测器(FB_SceneDetect,
  批次画像→推荐策略,sim 侧 A1 实验证 lex 档达 oracle 98.5%,ST 版=holistic 全要素档)+
  人工覆盖开关(xAutoStrategy)/ 检修挂起(FC_MaintToggle,SAP EWM putaway block 语义:
  禁新入库、存量冻结可查询,Reset 不清)/ 两级权限(FB_UserAuth+FB_ParamGuard 变量层双闸:
  画面元素锁定+越权改动一周期内回滚;内置 visu Access Rights 无脚本接口故不采用)。

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
真机预估=周期数×10ms 标称):四组实测数据 `sim/out/l4_task_cycles.csv`,报告 §5 已注入;
测量脚本 `tools/ab_scripting/measure_l4b.py`(全自动:包夹→四组→恢复)。

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
