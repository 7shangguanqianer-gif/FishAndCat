# 致 Claude(Codex 的执行汇报信箱)

> Codex:每完成一个批次,在下方**追加**一节(格式:`## 批次编号 · 日期`),
> 写清:做了什么 / 实测数值 / 与预期不符的现象 / 截图存哪了。不删旧内容。
> Claude:每次会话开始时读本文件,处理完的批次移到底部"已处理归档"区。

---

(等待 Codex 对批次 2026-07-05-B 的汇报)

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
