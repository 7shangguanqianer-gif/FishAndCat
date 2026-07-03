# Automation Builder 建工程操作卡(照着点,预计 60-90 分钟)

> 目标:把 plc\ 下 8 个 ST 文件导入 AB,仿真模式跑通 21 个测试用例(iPassed=21)。
> 你不需要懂 ST 也能完成;每一步都写了"预期看到什么"。卡壳了把报错原文发给我或 Codex。
> 注:AB 版本/语言不同,菜单名可能略有出入(中英对照都给了);界面差异不影响流程。

## 第一步:建工程(10 分钟)

1. 打开 Automation Builder → 新建工程(File → New Project / 文件 → 新建工程)。
2. 模板选 **AC500 项目**,工程名 `ABB_WH`,保存位置 `F:\abb_wh_work\plc\AB_Project\`(新建这个文件夹)。
3. 添加 PLC:选 **AC500 V3** 系列任意 CPU(推荐列表里选 **PM5650**;仿真模式下型号无所谓)。
   - 预期:左侧工程树出现 PLC_AC500_V3 → Application 节点。
4. 若首次启动提示许可证:选 **Basic license(免费)** 完成注册激活。

## 第二步:导入数据类型 DUT(15 分钟)

打开 `F:\abb_wh_work\plc\01_DUTs.st`(记事本/VSCode 均可),然后在 AB 里:

1. 右键 **Application → 添加对象(Add Object)→ DUT**。
2. 建 4 个 DUT,名字必须一字不差:`ST_Good`、`ST_Slot`、`ST_Stats`、`E_MainState`。
   - 建 ST_Good/ST_Slot/ST_Stats 时类型选 **结构(Structure)**;建 E_MainState 选 **枚举(Enumeration)**。
3. 每个 DUT 打开后,**全选编辑器里 AB 自动生成的模板文字,整体替换**为 01 文件里对应的
   `TYPE ... END_TYPE` 整段(含 TYPE 和 END_TYPE 行)。
4. 再打开 `07_GVL_Data_generated.st`,把里面的 `TYPE ST_TestVec ... END_TYPE` 段同样建成 DUT `ST_TestVec`。
   - 预期:5 个 DUT,编译无红。

## 第三步:导入全局变量 GVL(10 分钟)

1. 右键 Application → 添加对象 → **全局变量列表(Global Variable List)**,建 4 个:
   `GVL_Param`、`GVL_WH`、`GVL_Visu`、`GVL_Data`。
2. 从 `02_GVL.st` 把三段(注释里标了 GVL_Param / GVL_WH / GVL_Visu)分别整体粘贴进前三个;
   GVL_Param 里有两段 VAR_GLOBAL(CONSTANT 和普通),**两段都粘进同一个 GVL_Param**。
3. 从 `07_GVL_Data_generated.st` 把 `GVL_Data` 段(两个 VAR_GLOBAL 块)粘进 GVL_Data。
   - 预期:4 个 GVL,编译无红。

## 第四步:导入函数 FC(15 分钟)

1. 右键 Application → 添加对象 → **POU**,类型选 **功能(Function)**,返回类型按下表填:

| POU 名 | 返回类型 | 来源 |
|---|---|---|
| FC_CapCoef | REAL | 03 文件 |
| FC_IsPresetOccupied | BOOL | 03 |
| FC_CheckFeasible | BOOL | 03 |
| FC_FitsPhysical | BOOL | 03 |
| FC_CalcTravelTime | REAL | 03 |
| FC_CalcPathLen | REAL | 03 |
| FC_TMax | REAL | 03 |
| FC_CalcScore | REAL | 03 |
| FC_CalcPriority | REAL | 03 |
| FC_LoadDemoGoods | BOOL | **07 文件** |

2. 每个 POU:上半窗(声明区)粘 `FUNCTION ... END_VAR` 之间的声明部分,下半窗(实现区)粘剩余逻辑。
   - **AB 的 POU 编辑器分上下两窗**:上窗放 FUNCTION 头和 VAR_INPUT/VAR 声明,下窗放可执行语句;
     文件里 `END_VAR` 之后、`END_FUNCTION` 之前的内容全部属于下窗。
   - 若某版本 AB 是单窗模式,整段直接粘,再按报错微调。

## 第五步:导入功能块 FB 与程序 PRG(15 分钟)

1. 同法建 6 个 POU,类型选 **功能块(Function Block)**(来源 04 文件):
   `FB_InitWarehouse`、`FB_SelectSlot`、`FB_AssignAllGoods`、`FB_LocalSwapImprove`、`FB_Stats`、`FB_BuildVisuPath`。
2. 建 2 个 POU,类型选 **程序(Program)**:`PRG_Main`(05 文件)、`PRG_Test`(06 文件)。
3. 全部粘贴后:菜单 **编译(Build)→ 生成(Build)**。
   - 预期:0 错误。有错误看第七步排错表。

## 第六步:任务配置+仿真运行(15 分钟)

1. 工程树找到 **任务配置(Task Configuration)**→ 已有循环任务(如 Task)→ 周期设 **10ms**
   → 右键该任务 → 添加 POU 调用 → 挂 **PRG_Main**;再同法挂 **PRG_Test**。
2. 菜单 **在线(Online)→ 仿真(Simulation)** 打勾。
3. 在线 → 登录(Login)→ 确认下载 → 运行(Run/Start)。
   - 预期:状态栏绿色 RUN;PRG_Main 的 eState 自动走到 STATE_WAIT_INPUT。
4. **跑测试**:双击打开 PRG_Test(在线状态),找到变量 `xRunTests`,双击其"准备值"填 TRUE → 
   按 **Ctrl+F7(写入值)**。
   - 预期:`iPassed = 21`,`iFailed = 0`,`xAllPass = TRUE`。
   - 截图存到 `F:\abb_wh_work\plc\验收截图\`(建个文件夹),文件名 `W1_PRGTest_21pass.png`。
5. **跑演示**:GVL_Visu 里把 `CmdReset` 写 TRUE(复位测试污染的仓库)→ `CmdLoadDemo` 写 TRUE
   (载入 20 件演示货)→ `SelStrategy` 写 3 → `CmdRunAssign` 写 TRUE。
   - 预期:VisuStatusText 依次显示"分配中...→优化中...→完成:全部入库,违规=0";
     GVL_WH.stStats.PlacedCnt=20,ViolCnt=0。同样截图。

## 第七步:常见报错速查

| 报错关键词 | 原因 | 处理 |
|---|---|---|
| Unknown type: ST_Good | DUT 没建或名字打错 | 核对第二步 4+1 个 DUT 名 |
| Identifier 'GVL_Param' not found | GVL 没建全 | 核对第三步 4 个 GVL |
| 'MAX' unexpected | 个别版本需引标准库 | 工程树 Library Manager 确认 Standard 库在;在则改写为 IF 比较(告诉我,我给补丁) |
| CONCAT 嵌套报错 | 老版本 CONCAT 限两参 | 把三层 CONCAT 拆两句(告诉我位置,我给补丁) |
| E_MainState.STATE_IDLE 不识别 | 枚举前缀语法差异 | 把 `E_MainState.STATE_IDLE` 改成 `STATE_IDLE`(全文件同改) |
| 中文注释乱码 | 编码问题 | 无害,不影响编译;想清爽就用 VSCode 把文件另存为 UTF-8 with BOM 再粘 |

> 全部通过后告诉我"iPassed=21",我把 W1 验收清单第一条勾掉,并开工 L1 加减速模型。
> 这套操作你走完一遍,就已经学会了:AB 工程结构、DUT/GVL/POU 三类对象、仿真模式、在线写值——
> 决赛可视化(W4)要用的全部基本功。
