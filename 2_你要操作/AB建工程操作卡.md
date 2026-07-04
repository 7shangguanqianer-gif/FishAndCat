# Automation Builder 建工程操作卡(零基础版 v2)

> **你在干一件什么事**:把我们写好的 PLC 程序(plc\ 文件夹里那些 .st 文本文件)装进
> Automation Builder(以下简称 AB)这个软件里,让它在"仿真模式"(电脑里模拟一台 PLC,
> 不需要真机器)下跑起来,并跑通 23 个自动测试。
> **需要多久**:第一次做 90-120 分钟(含熟悉界面)。**难度**:不需要懂编程,会复制粘贴就行。
> **总原则**:每一步都写了"预期看到什么";只要和预期不符,**截图发给 Claude**,不要自己猜着点。
> 版本说明:AB 各版本菜单措辞略有差异(中文版/英文版也不同),本卡写通用位置,
> 括号里给英文名;找不到某个菜单=正常现象,截图问即可,不是你做错了。

---

## 第 0 步:先认识一下这个软件(5 分钟,只看不点)

启动 AB 后你会看到一个类似 Word 的窗口。记住三个区域,后面全程只跟它们打交道:

1. **左侧竖条区 = 工程树(Devices/设备)**:像文件资源管理器的目录树,
   我们所有东西都"挂"在这棵树上。最重要的节点叫 **Application(应用)**——程序都放它下面。
2. **中间大区域 = 编辑器**:双击树上的任何东西,就在这里打开编辑,粘贴代码也在这里。
3. **下方横条区 = 消息窗(Messages)**:编译后的结果在这里,**0 个错误**就是我们每一步的目标。

**五个术语,遇到就回来查**(不用背):

| 术语 | 大白话 |
|---|---|
| 工程(Project) | 一个"文档",保存我们全部工作,像 Word 的 .docx |
| DUT | "数据类型定义":告诉 PLC"货物"由哪些字段组成(编号/重量/频次…) |
| GVL | "全局变量表":整个程序共用的数据,比如 400 个仓位的数组 |
| POU | "程序单元":装代码的盒子,分三种——函数(算个数就返回)、功能块(有记忆的模块)、程序(主入口) |
| 编译(Build) | 让软件检查代码有没有写错,类似 Word 的拼写检查 |

---

## 第 1 步:新建工程(10 分钟)

1. 菜单栏点 **文件(File)→ 新建工程(New Project)**。
   - 预期:弹出一个对话框,里面有若干模板图标。
2. 选 **AC500 项目**(可能叫 "AC500 project" 或带 PLC 图标的模板)。
   - 下方两个输入框:**名称(Name)**填 `ABB_WH`;**位置(Location)**点"浏览"选
     `F:\abb_wh_work\plc\`,再手动在路径后补一层新文件夹名 `AB_Project`。点确定。
3. 接下来软件通常会让你**选 PLC 型号**(一个很长的产品列表):
   - 展开找 **AC500 V3** 系列,任选一款 CPU,推荐 **PM5650**(找不到就选任何 PM56xx)。
   - 为什么随便选也行:我们跑仿真,不连真机器,型号只是个名头。
   - 预期:确定后,左侧工程树出现一串节点,里面能找到 **Application**(可能藏在
     PLC_AC500 → PLC Logic → Application 这样的层级下,逐层点小箭头展开)。
4. 若弹出许可证提示:选 **Basic license(基础版,免费)**,按引导注册激活即可。
5. 随手保存:**Ctrl+S**(以后每完成一步都按一次,习惯)。

✅ 本步验收:左侧树里能看到 Application 节点。卡住→截图整个窗口发 Claude。

---

## 第 2 步:小试牛刀——先导 1+1 个,把流程跑通(15 分钟)

> 先用最小样本学会"建对象→粘代码→编译"这个循环,成功一次后面就是重复劳动。

**2a. 建第一个 DUT(数据类型)**

1. 左侧树上**右键点 Application → 添加对象(Add Object)→ DUT…**。
   - 预期:弹出对话框,让你填名称、选类型。
2. 名称填 `ST_Good`(一个字母都不能错,建议从本卡复制);类型选 **结构(Structure)**;点添加。
   - 预期:中间编辑器打开一个新页面,里面已有几行软件自动生成的模板文字
     (类似 `TYPE ST_Good : STRUCT ... END_TYPE`)。
3. 用记事本打开 `F:\abb_wh_work\plc\01_DUTs.st`,找到从 `TYPE ST_Good :` 开始、
   到第一个 `END_TYPE` 结束的整段,复制。
4. 回到 AB 编辑器:**Ctrl+A 全选(把模板全选中)→ Ctrl+V 粘贴覆盖**。Ctrl+S 保存。

**2b. 建第一个函数**

1. 右键 Application → 添加对象 → **POU…**。
2. 对话框里:名称填 `FC_CapCoef`;类型选 **功能(Function)**;
   下面会多出一个"返回类型(Return type)"框,填 `REAL`;实现语言选 **结构化文本(ST)**。点添加。
   - 预期:编辑器打开的页面**分上下两窗**——上窗放"声明"(变量定义),下窗放"逻辑"(执行语句)。
3. 打开 `plc\03_Functions.st`,找到 FC_CapCoef 那段:
   - `FUNCTION FC_CapCoef : REAL` 到最后一个 `END_VAR` 之间的内容 → 粘到**上窗**(先 Ctrl+A 清掉模板);
   - `END_VAR` 之后、`END_FUNCTION` 之前的剩余逻辑 → 粘到**下窗**。
   - 若你的 AB 只有一个窗口(个别版本如此):整段(含 FUNCTION 和 END_FUNCTION 行)全粘进去即可。
4. **编译一次**:菜单 编译(Build)→ 生成(Build),或按 **F11**。
   - 预期:下方消息窗显示 **"0 个错误(0 errors)"**(警告 warning 黄色的不用管)。

✅ 本步验收:编译 0 错误。这证明流程通了——后面全是重复。
❌ 若有红色错误:双击错误行看它跳到哪,截图(含错误文字)发 Claude,秒回补丁。

---

## 第 3 步:补齐其余数据类型和全局变量(20 分钟)

**3a. 再建 4 个 DUT**(方法同 2a,来源文件见括号):

| DUT 名称 | 类型选什么 | 代码来源 |
|---|---|---|
| ST_Slot | 结构(Structure) | 01_DUTs.st |
| ST_Stats | 结构(Structure) | 01_DUTs.st |
| E_MainState | **枚举(Enumeration)** | 01_DUTs.st |
| ST_TestVec | 结构(Structure) | **07**_GVL_Data_generated.st(文件开头) |

**3b. 建 4 个全局变量表 GVL**:右键 Application → 添加对象 → **全局变量列表(Global Variable List)**:

| GVL 名称 | 代码来源 | 特别说明 |
|---|---|---|
| GVL_Param | 02_GVL.st | 该段有**两个** VAR_GLOBAL 块(CONSTANT 和普通),**都**粘进这一个 GVL |
| GVL_WH | 02_GVL.st | — |
| GVL_Visu | 02_GVL.st | — |
| GVL_Data | 07_GVL_Data_generated.st | 也是两个块都粘 |

粘贴规则同前:打开 GVL 后 Ctrl+A 清掉模板,粘入源文件对应段落。每建完一个按 F11 编译一次,
保持"随时 0 错误"——一旦报错马上知道是刚才那步的问题,好定位。

✅ 本步验收:5 个 DUT + 4 个 GVL 全在树上,编译 0 错误。

---

## 第 4 步:导入全部函数(20 分钟)

方法同 2b(POU→功能→填返回类型→上下窗粘贴),共 12 个,一个个来:

| POU 名称 | 返回类型 | 来源 |
|---|---|---|
| FC_CapCoef | REAL | 已在第 2 步做完 ✓ |
| FC_IsPresetOccupied | BOOL | 03_Functions.st |
| FC_CheckFeasible | BOOL | 03 |
| FC_FitsPhysical | BOOL | 03 |
| FC_CalcTravelTime | REAL | 03 |
| FC_CalcPathLen | REAL | 03 |
| FC_TMax | REAL | 03 |
| FC_CalcScore | REAL | 03 |
| FC_CalcPriority | REAL | 03 |
| FC_AxisTime | REAL | 03 |
| FC_CalcDualCycleTime | REAL | 03 |
| FC_LoadDemoGoods | BOOL | **07** 文件末尾 |

小技巧:在源文件里搜函数名(记事本 Ctrl+F)直接定位;每段的边界是
`FUNCTION 名字 : 返回类型` 到 `END_FUNCTION`。每建 2-3 个按一次 F11。

---

## 第 5 步:导入功能块和主程序(20 分钟)

**5a. 8 个功能块**:添加对象 → POU → 类型选 **功能块(Function Block)**(没有返回类型框),
来源全部是 04_FB_Warehouse.st,段落边界 `FUNCTION_BLOCK 名字` 到 `END_FUNCTION_BLOCK`:
`FB_InitWarehouse`、`FB_SelectSlot`、`FB_AssignAllGoods`、`FB_LocalSwapImprove`、
`FB_Stats`、`FB_AnimatePath`、`FB_ScanLoadProbe`、`FB_BuildVisuPath`。

**5b. 2 个程序**:添加对象 → POU → 类型选 **程序(Program)**:
`PRG_Main`(来源 05_PRG_Main.st)、`PRG_Test`(来源 06_PRG_Test.st)。

粘完全部后 F11:**0 错误**才进下一步(报错→截图发 Claude)。
(plc 里还有个 08_GVL_WeightPolicy_generated.st 先**不用**导,那是后续接线用的。)

---

## 第 6 步:把程序挂上"任务"(10 分钟)

> 概念:PLC 是"每 10 毫秒把程序从头跑一遍"的循环机器;"任务(Task)"就是这个闹钟。
> 我们要告诉它:每响一次,跑 PRG_Main 和 PRG_Test。

1. 工程树里找 **任务配置(Task Configuration)**节点(通常在 Application 下面),
   展开后一般已有一个现成任务(可能叫 Task / MainTask)。双击它。
2. 编辑器里把 **周期/间隔(Interval)**设为 **10ms**(若显示 t#20ms 就改成 t#10ms)。
3. 在该任务页面找 **添加调用(Add Call / 添加 POU)**按钮 → 选 `PRG_Main` 确定;
   再点一次 → 选 `PRG_Test` 确定。
   - 预期:任务下方列表里出现这两个程序名。
4. F11 编译,0 错误;Ctrl+S。

---

## 第 7 步:开仿真,让程序跑起来(10 分钟)

> 概念三连:**仿真(Simulation)**=电脑里虚拟一台 PLC;**登录(Login)**=把程序装进这台
> 虚拟 PLC;**运行(Run)**=按下它的启动键。

1. 菜单 **在线(Online)→ 仿真(Simulation)**,点一下打勾。
   - 预期:窗口某处(通常底部)出现红色 SIMULATION 字样——红色是提醒"这是仿真",不是错误。
2. 菜单 在线 → **登录(Login)**,或按 **Alt+F8**。弹出"是否下载"之类的确认框 → 是/Yes。
   - 预期:工程树的 Application 节点变绿色或显示 [run]/[stop] 状态。
3. 菜单 调试(Debug)→ **启动(Start)**,或按 **F5**。
   - 预期:状态显示 **RUN(运行)**,通常是绿色。
4. 双击树上的 PRG_Main:编辑器现在是"在线模式"——每个变量后面都实时显示当前值。
   - 预期:变量 `eState` 的值显示 **STATE_WAIT_INPUT**(=程序已自动初始化完仓库,在等指令)。

✅ 到这里,一台虚拟 PLC 正在你电脑里以每秒 100 次的节奏跑我们的程序。

---

## 第 8 步:跑 23 个自动测试(15 分钟)——今天的最终验收

> 在线模式下改变量值的标准手法(记住这个,后面演示也用):
> **双击该变量所在行的"准备值(Prepared value)"列 → 出现 TRUE → 按 Ctrl+F7(写入值)**。
> (有的版本双击后直接弹小窗让你填,填 TRUE 确定即可。)

1. 双击打开 **PRG_Test**(在线状态下)。
2. 找到变量 `xRunTests`,按上面的手法把它写成 **TRUE**。
   - 程序瞬间跑完全部测试并把它自动复位回 FALSE,所以你可能看不到它变 TRUE——正常。
3. 看结果变量:
   - **`iPassed` = 23,`iFailed` = 0,`xAllPass` = TRUE** → 🎉 通过!
   - 其中 T19/T20/T22 三项=PLC 算出的数和 Python 仿真**逐条一致**,T23=双命令周期口径正确——
     这一步过了,报告里"仿真与实现互相背书"的证据链就闭环了。
4. **截图**:让 iPassed/iFailed 出现在画面里,存到 `F:\abb_wh_work\plc\验收截图\`
   (没有这个文件夹就新建),文件名 `W1_PRGTest_23pass.png`。
5. 若 iFailed ≠ 0:看 `sLastFail` 变量显示的编号(如 T13),截图发 Claude。

---

## 第 9 步:顺手看一眼演示效果(10 分钟,可选但推荐)

1. 双击打开 **GVL_Visu**(在线状态,能看到所有交互变量)。
2. 依次写值(手法同第 8 步):
   - `CmdReset` 写 TRUE(清掉测试留下的数据,重新初始化仓库);
   - `CmdLoadDemo` 写 TRUE(载入 20 件演示货物——和 Python 仿真同一批);
   - `SelStrategy` 写 **3**(选 AWRA-LS 算法);
   - `CmdRunAssign` 写 TRUE(开始分配!)。
3. 盯着 `VisuStatusText` 变量:会依次显示"分配中…→优化中…→**完成:全部入库,违规=0**"。
4. 再看 GVL_WH 里 `stStats`:PlacedCnt=20、ViolCnt=0。截图留档。

这就是决赛可视化的数据底座——W4 我们给它配上 20×20 的图形界面和动画。

---

## 常见报错速查

| 报错关键词(消息窗红字) | 原因 | 处理 |
|---|---|---|
| Unknown type: ST_Good | 数据类型没建或名字打错 | 核对第 2/3 步的 5 个 DUT 名称 |
| Identifier 'GVL_Param' not found | 全局变量表没建全 | 核对第 3b 步 4 个 GVL |
| Identifier 'FC_xxx' not found | 某个函数漏建了 | 对照第 4 步表格逐个数 |
| 'MAX' unexpected | 标准库没挂 | 截图发 Claude,给一行替换补丁 |
| CONCAT 嵌套报错 | 老版本字符串函数限两参 | 截图发 Claude,给拆分补丁 |
| E_MainState.STATE_IDLE 不识别 | 枚举写法的版本差异 | 把全文 `E_MainState.` 前缀删掉再编译(告诉 Claude 已这样做) |
| 中文注释乱码 | 编码差异 | 无害,不影响运行;看着难受就忽略注释 |
| 登录时报"没有设备/无法连接" | 忘了先勾仿真 | 回第 7 步第 1 条 |

> 万能兜底:**任何一步和预期不符 → 整窗截图 + 你做到第几步 → 发 Claude**。
> 你不需要判断问题出在哪,判断是我的活。
> 全部通过后告诉我"iPassed=23",我勾掉验收清单第一条。这一遍走完,你已经掌握了
> AB 的工程结构、四类对象、编译、仿真、在线写值——决赛可视化要用的全部基本功。
