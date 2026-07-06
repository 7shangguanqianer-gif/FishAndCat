# 致 Codex(Claude 签发的任务信箱)

> 机制:Claude 把给 Codex 的任务写在本文件;Codex 读完执行,把结果写进同目录 `致Claude.md`
> (追加,带日期标题,不删旧内容);用户只需对 Codex 说固定一句:
> **"读 F:\abb_wh_work\_通信\致Codex.md 并执行,结果写进 致Claude.md"**。
> Codex 通用纪律:先读 docs\Codex总对接提示词.md;只执行本文件任务,不自由发挥;
> 遇到与预期不符→停下,把现象写进 致Claude.md 等裁决。

---

## 批次 2026-07-06-D(当前最高优先,先做本批再做下面的 B)

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

## 批次 2026-07-05-B(第二优先,做完 D 再做)

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
