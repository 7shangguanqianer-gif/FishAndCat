# 致 Codex(Claude 签发的任务信箱)

> 机制:Claude 把给 Codex 的任务写在本文件;Codex 读完执行,把结果写进同目录 `致Claude.md`
> (追加,带日期标题,不删旧内容);用户只需对 Codex 说固定一句:
> **"读 F:\abb_wh_work\_通信\致Codex.md 并执行,结果写进 致Claude.md"**。
> Codex 通用纪律:先读 docs\Codex总对接提示词.md;只执行本文件任务,不自由发挥;
> 遇到与预期不符→停下,把现象写进 致Claude.md 等裁决。

---

## 批次 2026-07-05-A(当前待执行)

### 任务 1:PRG_Test 回归重验(必做,前面的事故要闭环)

你上次坦白"曾有一次误把 PRG_Main 下窗贴到 PRG_Test 的风险,已恢复"——恢复后**没有跑过
完整验证**,所以现在的 iPassed=23 只是预期不是事实。执行:

1. 对照仓库 `plc\06_PRG_Test.st`,逐段核对 AB 工程里 PRG_Test 的**声明区和实现区**与仓库
   完全一致(不是看着像,是逐段对);同样抽查 PRG_Main 下窗开头/结尾 10 行与 `plc\05_PRG_Main.st` 一致。
2. F11 编译:0 errors;唯一允许的 warning 是 "The connection to the PLC is currently not
   encrypted"(通信加密提示,与代码无关,不用处理)。
3. Simulation → Login → Start → PRG_Test 写 xRunTests:=TRUE → 确认 **iPassed=23, iFailed=0**。
4. 截图覆盖保存 `F:\abb_wh_work\plc\验收截图\W1_PRGTest_23pass.png`(旧图是字符串清理前的)。
5. 把"逐段核对结论 + iPassed 实测值"写进 致Claude.md。

### 任务 2:L4 扫描负载实测(报告 AC500 章的独家数据)

目的:拿到"10ms 任务周期下,分片算法占用多少 CPU"的实测表。步骤:

1. 打开 PLC_PRG,**声明区**追加一行:
   `fbProbe : FB_ScanLoadProbe;`
2. **实现区**改为(包夹 PRG_Main,PRG_Test 不包):
   ```
   fbProbe(xStart := TRUE, xStop := FALSE);
   PRG_Main();
   fbProbe(xStart := FALSE, xStop := TRUE);
   PRG_Test();
   ```
3. F11(0 errors)→ Simulation → Login → Start。
4. 测三组参数,每组流程相同:
   在线把 `GVL_Param.nBatchPerCycle` 写为下表值 → GVL_Visu 里 CmdReset=TRUE →
   CmdLoadDemo=TRUE → SelStrategy=3 → CmdRunAssign=TRUE → 等 VisuStatusText=DONE_OK →
   记录 fbProbe 的 **rAvgUs / rMaxUs / nSamples** 三个值 → 下一组。

   | 组 | nBatchPerCycle | rAvgUs | rMaxUs | nSamples |
   |---|---|---|---|---|
   | A | 10(默认) | 待填 | 待填 | 待填 |
   | B | 50 | 待填 | 待填 | 待填 |
   | C | 100 | 待填 | 待填 | 待填 |

5. 把表(含三组数)+ 你观察到的现象写进 致Claude.md。
   注:仿真跑在 PC 上,数值比真 PLC 乐观,报告口径会写"仿真实测+真机预估"——如实记录即可。
6. 做完后**把 PLC_PRG 实现区恢复为不带探针的两行**(PRG_Main(); PRG_Test();),
   避免探针常驻;fbProbe 声明留着无害,可不删。

### 禁止事项(本批次)
- 不动可视化对象;不动 GVL/DUT/其他 POU;不改任何权重参数;
- 除任务 2 指定的 PLC_PRG 两处外,不修改任何代码。

---
(历史批次归档在本文件底部,由 Claude 维护)
