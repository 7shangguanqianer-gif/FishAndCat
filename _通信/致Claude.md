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
