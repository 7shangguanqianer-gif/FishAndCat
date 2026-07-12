# N5-P2 Reset、重复运行与跨批状态污染复核（0712）

## 结论

新增 3 项、正面确认 1 项。当前 Reset 能重建仓位并清五个主显示指标，但它不是完整会话/统计复位：AWRA 的 `SwapCnt/LsRounds` 会污染下一批非 AWRA 结果；`SwapCnt` 本身又漏记重定位；若快照模式仍开，Reset 后网格还可能继续显示上一批快照，故“画面回初始/留干净状态”只在附加前提下成立。

本项为控制流静态亲验；因 AB 工程正被占用且红线禁止打开，本轮未做在线点击实验。

## N5-05【高】AWRA → Reset → 非 AWRA 后，SwapCnt/LsRounds 保留上一批值

### 控制流证据

1. `ST_Stats` 定义 `SwapCnt/LsRounds` 为本次局搜统计：`plc/01_DUTs.st:55-56`。
2. 只有 AWRA 进入 `STATE_IMPROVE` 完成时，主程序才赋这两个字段：`plc/05_PRG_Main.st:151-163`。
3. Reset 只清 `PlacedCnt/FailedCnt` 和五个可视字段，没有清 `SwapCnt/LsRounds`：`plc/05_PRG_Main.st:34-53`。
4. `FB_Stats` 每批重算 `PlacedCnt`、时间、路径、能耗、违规、均值、利用率，但没有给 `SwapCnt/LsRounds` 赋值：`plc/04_FB_Warehouse.st:411-459`。
5. 非 AWRA 在 assign 完成后直接进 stats，不经过 improve：`plc/05_PRG_Main.st:141-148`。

因此序列必然是：

```text
AWRA 完成 -> SwapCnt=S, LsRounds=R
Reset     -> S/R 未清
Score/near/seq 完成 -> FB_Stats 不写 S/R
结果      -> 新批仍显示/暴露旧 S/R
```

这与刻意跨 Reset 保存的 `aSlotOps/aMaintBlock/snapshot` 不同；代码和注释没有把局搜批次统计定义为历史累计值。

### 测试缺口

- T25 只跑一次 AWRA 并核聚合/布局：`plc/06_PRG_Test.st:161-206`。
- 当前没有 “AWRA→Reset→score” 的跨批断言，也没有断言非 AWRA 后 `SwapCnt=0/LsRounds=0`。

### 影响

若报告、监视或后续画面读取 `stStats` 全字段，会把上一批局搜工作量归给当前非 AWRA 策略。修复应在批次开始或 Reset 时清零，而不是仅在 HMI 文案隐藏。

## N5-06【中】SwapCnt 注释称“接受的改进次数”，实际只计 swap、不计 relocation

- `FB_LocalSwapImprove` 分开输出 `iSwaps` 与 `iRelocs`：`plc/04_FB_Warehouse.st:244-253`。
- 接受重定位时 `iRelocs += 1`：`:310-326`；接受换位时 `iSwaps += 1`：`:347-370`。
- `ST_Stats.SwapCnt` 的注释却是“局部搜索接受的改进次数”：`plc/01_DUTs.st:55`。
- 主程序只复制 `fbImprove.iSwaps`，完全丢掉 `iRelocs`：`plc/05_PRG_Main.st:158-160`。
- 运行状态文本同样只显示 `SWAPS`：`:153-157`。

所以“局搜接受改进数”会系统性低报；只发生 relocation 的一批可以显示 `SWAPS=0`，但布局已经改变。建议要么新增 `RelocCnt`，要么把字段/台词严格改为“成对交换数”，不要把两类邻域混称。

## N5-07【中】Reset 是“仓库批次复位”，不是“画面/会话回初始”

Reset 明确清理的只有 `iGoodsCount`、两项 stats、报警、路径、堆垛机位置和五个显示统计：`plc/05_PRG_Main.st:34-53`。以下状态保留：

| 保留项 | 证据 | 性质 |
|---|---|---|
| 检修位 `aMaintBlock` | `plc/02_GVL.st:76-83` | 明确设计为跨 Reset |
| 操作热图 `aSlotOps` | 同上 | 明确设计为跨 Reset，但见 P3 溢出风险 |
| 快照 `aSnapState/xSnapValid` | `plc/05_PRG_Main.st:233-239` | 策略前后对比需要跨 Reset |
| `CmdCompareMode`、`iViewMode` | `plc/05_PRG_Main.st:223-232,251-264` | 档位/开关不复位 |
| 登录级别 | `plc/04_FB_Warehouse.st:1027-1057` | Reset 不调用 logout |
| 输入框及当前策略 | `plc/02_GVL.st:107-117` | Reset 未清 |

保留本身不全是 bug；错在文档把 Reset 说成无条件“画面回初始”“收场留干净状态”：`docs/演示脚本v3_0711.md:37`。特别是 `CmdCompareMode=TRUE` 且快照有效时，`FB_VisuRefresh` 优先渲染快照：`plc/04_FB_Warehouse.st:633-641`。此时 Reset 已把实时仓库清空，画面却仍显示上一批布局。

建议把演示收场写成显式序列：切回 Live/State view → Logout → Reset；或者新增用户认可的 `CmdHardReset`，与保留快照/检修/履历的批次 Reset 分开。

## N5-08【正面】已修的两处沿冻结与动画中断护栏确实有效

- `FB_InitWarehouse` 和 `FB_Stats` 用 `xOld := xExecute AND NOT xDone`，允许下一批重新触发：`plc/04_FB_Warehouse.st:48-51,461-463`。
- Reset 将 `VisuPathCount` 清 0：`plc/05_PRG_Main.st:39-40`；动画检测路径少于 2 点后安全停止，避免 `PathCount-1=-1`：`plc/04_FB_Warehouse.st:501-505`。
- 这支持保留“仓位重建、五个主指标归零、动画安全中止”的限定结论。

## 最小验收建议

1. 新增跨批测试：AWRA 产生非零局搜计数 → Reset → score → `SwapCnt=0/LsRounds=0`。
2. 构造只有 relocation、没有 swap 的布局，断言两类计数分别准确。
3. 在线验 `Snapshot mode→Reset`，决定是保留旧图并改台词，还是 Reset 自动回 Live。
4. 把“Reset”在 UI/文档中命名为“Reset batch”，并单独定义 hard reset 的清理矩阵。

