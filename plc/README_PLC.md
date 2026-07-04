# PLC 侧使用说明(Automation Builder / AC500 V3)

> 本目录是 ST 源码骨架(文本形式)。Automation Builder(下称 AB)装好后按下述步骤导入,
> 无实体 PLC 也能在仿真模式下完整运行(初赛口径足够)。
> 交付形式官方要求待确认(canonical D 清单),先按「AB 工程 + ST 源码」双备份准备。

## 1. 文件清单与导入对象对应

| 文件 | 导入为 | 说明 |
|---|---|---|
| 01_DUTs.st | 4 个 DUT(每个 TYPE 一个) | ST_Good / ST_Slot / ST_Stats / E_MainState |
| 02_GVL.st | 3 个 GVL | GVL_Param(常量段+变量段合一个,含 L1 加减速参数)/ GVL_WH / GVL_Visu |
| 03_Functions.st | 11 个 POU-函数 | FC_CapCoef 等纯函数 + FC_AxisTime(L1 梯形)+ FC_CalcDualCycleTime(L2 双命令) |
| 04_FB_Warehouse.st | 8 个 POU-功能块 | Init / SelectSlot / AssignAllGoods / LocalSwapImprove / Stats / BuildVisuPath + **FB_AnimatePath**(L6 动画回放)+ **FB_ScanLoadProbe**(L4 负载实测) |
| 05_PRG_Main.st | 1 个 POU-程序 | 主状态机,挂循环任务 |
| 06_PRG_Test.st | 1 个 POU-程序 | 23 个边界+一致性用例(T22 加减速向量/T23 双命令) |
| 07_GVL_Data_generated.st | 1 DUT + 1 GVL + 1 函数 | **生成文件勿手改**,由 sim/export_st_vectors.py 重生(含 ExpTimeAccel) |

## 2. 建工程步骤(AB 2.8+/AC500 V3)

1. 新建工程 → PLC AC500 V3 系列任选一款 CPU(如 PM5650;仿真模式与型号无关)。
2. Application 下按上表逐个"添加对象"(DUT / 全局变量列表 / POU),名称与代码里的一致,粘贴对应段落。
   - 粘贴时去掉 TYPE/FUNCTION 外层已由 AB 自动生成的重复声明(AB 建 POU 时会预置声明头,以文件里的为准覆盖)。
3. 任务配置:Task(循环,10ms)→ 挂 PRG_Main;PRG_Test 可挂同任务(默认不触发,置 xRunTests 才跑)。
4. 菜单 在线 → 仿真(Simulation)勾选 → 登录(Login)→ 运行(Run)。
5. 首次验证顺序:
   a. PRG_Test.xRunTests := TRUE → 期望 **iPassed=23**, iFailed=0(T19/T20/T22 是与 Python 的一致性向量,T23 双命令已知值);
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

## 4. 已知注意项

- PLC REAL 为单精度,Python 为双精度:一致性比对容差 1e-3;如出现平局翻转导致选位偶发不一致,
  将 FC_CalcScore 及比较链改用 LREAL(AC500 V3 支持)即可,已预留说明。
- 07 是生成文件:改了 Python 评分函数/权重/场景参数,必须重跑 `python sim/export_st_vectors.py`
  并在 AB 里替换粘贴,否则 T19/T20 会红——红了先想是不是忘了同步,这是设计出来的护栏。
- STRING 字面量中避免中文(部分 AB 版本编码敏感);注释中文无碍。
- 局部交换阶段 O(n²) 对数在 n=400 时约 8 万对/轮,按 nPairsPerCycle=200 需 ~400 周期/轮(10ms 任务 ≈ 4s/轮),
  演示可接受;若嫌慢调大 nPairsPerCycle(单周期 200 对评分 ≈ 微秒级,余量巨大)。

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
LTIME() 在个别 AB 版本若不可用,改用 SysTime 库 SysTimeGetNs(报错时按此替换)。

## 5. 决赛可视化(W4 起做,变量已就绪)

CODESYS Visualization 画面绑定 GVL_Visu:20×20 网格用"矩形阵列+VisuSlotState 颜色映射"
(0空闲/1预占/2占用/3推荐/4路径/5报警),输入区绑 InGood* 与 Cmd* 按钮,统计区绑 Visu 统计变量。
演示脚本见 _ref/资料包 §10.3(六步:初始状态→轻高频→重货→批量→算法对比→超重报警)。
