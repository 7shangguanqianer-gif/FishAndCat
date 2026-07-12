# 给 Claude Code：N5 独立发现逐条回源复核提示词

下面整段可直接交给 Claude Code：

---

你现在接手 `F:\abb_wh_work` 的 **N5 增量复核裁决**。N2–N4 已有各自审查/整改链，本轮不要重放或回滚旧批次；只处理 Codex 新完成的 N5-01～N5-35，并以你开始执行时的**当前磁盘**为唯一事实源。

重要并发提示：Codex 审计期间，已有其他进程修改过 `docs/ASK决策_0712.md`、`docs/接手任务表_0712.md`、`docs/接管启动提示词_0712pm.md`、`sim/d2_quantify.py`，AB 临时文件 `plc/AB_Project/ABB_WH.~u` 也在更新。不得用审计开始时的旧内容覆盖这些并发成果；每一项先重读当前文件，若已被修复，判为“当前已修复/原发现当时成立”，不要假装仍未修。

## 目标

独立、批判性地逐条裁决 N5-01～N5-35：

- `接受`：当前源代码/数据可复现，结论和严重度成立；
- `部分接受`：事实成立，但范围、数字、严重度或建议需修正；
- `不同意`：给出反证和正确结论；
- `当前已修复`：Codex 取证后被并发修改修掉，说明修复文件、行号和验证；
- `需 AB 动态验证`：静态证据不足，明确最小动态实验，但本轮不要打开 AB。

不要把 Codex 报告当结论抄写。阻塞/高项必须回到原始 `.py/.st/.csv/.log` 亲验，并尽量用独立小复算确认；负结果如实写。

## 先读顺序

1. `_通信/codex_out/N5_汇总回执_0712.md`
2. `_通信/codex_out/N5_P1_浮点精度与决胜规则复核_0712.md`
3. `_通信/codex_out/N5_P2_Reset与跨批状态污染复核_0712.md`
4. `_通信/codex_out/N5_P3_长跑溢出与计数寿命复核_0712.md`
5. `_通信/codex_out/N5_P4_失败队列与公平负载复核_0712.md`
6. `_通信/codex_out/N5_P5_种子置信区间与选择偏差复核_0712.md`
7. `_通信/codex_out/N5_P6_能耗年化吞吐单位链复核_0712.md`
8. `_通信/codex_out/N5_P7_权限多客户端与留痕复核_0712.md`
9. `_通信/codex_out/N5_P8_CSV日志产物结构与完整性复核_0712.md`
10. 对应 P1/P4/P5/P6/P8 JSON 与 `N5_P*_readonly_probe.py`；最后读 `_通信/致Claude.md` 顶部 N5 回执。

只读探针可这样重跑，不得覆盖 `sim/out`：

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
Get-ChildItem .\_通信\codex_out\N5_P*_readonly_probe.py |
  Sort-Object Name |
  ForEach-Object { python -B $_.FullName }
```

## 必须重点亲验的锚点

### P1：平局/浮点（N5-01～04）

- `warehouse_sim.py` near 的 total order 是否为 `(time,tier,col)`，ST 扫描是否实际等价 `(time,col,tier)`；亲验 `(0,1)` 与 `(4,0)` 同为 2s 的最小反例。
- 复算 13 场景×30 seed：Codex 报 390/390 布局分叉、共 12,540 件位置不同、exp_t差0、能耗相对差最大12.184%。判断“布局等价/指标等价”该如何准确表述。
- Rank 平局的 Goods ID 与数组 index 分歧；用合法非顺序正 ID `[100,1]` 复现。
- REAL32 代理只能叫 Python float32 proxy，不得冒充 AB；核对 13 场景 seed2026 仅 illegal_mix 2件分叉、演示20件0差。

### P2/P3：跨批与寿命（N5-05～12）

- 走读 AWRA→Reset→非AWRA：`SwapCnt/LsRounds` 是否继承；`SwapCnt` 是否漏记 relocation。
- 区分 batch reset 与 hard/session reset；不要把 Snapshot/View/Admin/维护/履历的保留误报成 bug，先按设计语义分类。
- ABB `INT` 是否16-bit；复核 `aSlotOps` 极端热点 5.94 天触32767、`iFailCnt` 无锁定、`iSwaps` 候选评估 O(n²) 上界399,000。注意“候选评估次数”不等于“接受 swap 次数”，分别裁决。

### P4：失败、arrival、公平性、生命周期（N5-13～16）

- 270行标定表、18组策略表：6个高密在线组选中方案有失败，且这些组15个候选是否确实都没有零失败；判断这是权重搜索空间不可行、策略容量不足还是选优 bug。
- 复核 `realism.py` 是否为每个策略按自身服务时长生成不同 arrival；改为 seq 共同 arrival 后，P95 是否由现表 AWRA 679.8<near 854.3 变为 near 651.1<AWRA 667.0。不要把反事实写成已落地主结果。
- `lifecycle_sim.py` 的 `LAG=5` 尾部是否未 flush：20/20 只读复算是否都 pending=5、库存115→flush后120、平均漏254.85s、final_q约恶化0.803s。

### P5：统计与选择偏差（N5-17～20）

- 标定 `[2026,7]`、所谓 holdout `[42,123,999]`、headline 五seed是否恰为并集，是否还存在真正 untouched final test。
- 用 t(4)=2.776 复算 H AWRA：均值8.402388、sample SD0.476878、95%CI `[7.81036,8.99442]`，半宽0.592027；确认对外应写 SD 还是 CI。
- 核对配对降幅均值61.839%、95%CI `[56.896,66.782]`；这是正面稳健锚，不要因测试集复用就说五seed算术无效。

### P6：年化、吞吐、CO2（N5-21～26）

- 代码是否把 500 ops/day 除以2成75,000 dual cycles/year；若“500次存取”被理解为500 dual cycles/day，绝对量是否正好翻倍。
- 同一 AWRA H：行程-only 230.44 ops/h；+15s/每个存或取后117.56；再+一次600s故障107.07。区分理论饱和容量、场景完成率、PLC实测。
- 独立查生态环境部官方来源：2023全国平均电力CO2因子0.5306、排除市场化非化石电力边界0.6096；判断项目0.581能否称“2023公布值”。
- 查 `docs/报告草稿_C3C5B14_0712.md` 当前是否仍有 `546.0→278.9` 却写省266.5；若并发已修，标“已修复”。

### P7：多客户端权限（N5-27～31）

- 只靠 ST/GVL 语义构造 A输PIN、B触发Login；确认 PIN/Cmd/iUserLevel/单个fbAuth是否全局，登录/登出是否必然影响全部客户端。
- T54–T56 是否只测单实例分支，不能证明 per-client 隔离。
- 核对是否有 timeout、lockout、client/user ID、actor+before/after append-only审计。
- 保留源码“单客户端演示、生产换 UserMgmt/CurrentClientId”的诚实边界；本轮不得把静态结论升级成 WebVisu 动态实测。

### P8：产物完整性与 oracle 语义（N5-32～35）

- 全扫37 CSV：验证无空/NaN/Inf/重复主键，detail↔agg基数与均值在舍入内一致。
- 亲验6份多section CSV；区分“字节损坏”与“非标准交换格式”。
- `consistency_probe.log` 是否仍为修复前12×30=390，而当前脚本已用 `len(SCENARIOS)`。
- `oracle_gap_detail.csv` 是否有58行 `gap<0/attain>100`，且58/58均 `excess_fail>0`；核对 dense_200=128.04%、dense_240=123.00%、ALL=103.93%。判断正确修法是N/A、分失败档还是重定义指标。

## 红线

- 本轮是**复核裁决，不是修复批次**。除新增复核回执外，不修改任何现有项目文件，不重生 DOCX/PPTX/CSV/图。
- 禁开 Automation Builder；禁运行 `tools/ab_scripting`、`ab_sync.ps1`；禁 git 写操作；禁 spawn 子代理。
- 不进入/修改 `1_给你看`、`2_你要操作`。
- 不把 Python 代理称 AB/AC500 真跑；AB 才能验证的项目单列。
- 官方网页核验只用一手来源；外部资料不能覆盖本项目真相源，但可纠正其来源年份/边界。

## 输出

新增 `docs/Claude_N5复核回执_0712.md`；若同名已存在，不覆盖，改用带当前时分的文件名。内容必须包括：

1. 总裁决计数：接受/部分接受/不同意/当前已修复/需AB验证。
2. **N5-01～N5-35 无遗漏矩阵**：状态、严重度、当前 `file:line`、复算证据、建议动作。
3. “Codex 取证后发生的并发漂移”专节，列出哪些发现已被当前文件修复或改变。
4. P0/P1/P2 建议清单，但不实施；说明哪些只需改话术，哪些需代码/测试，哪些必须AB动态验收。
5. 正面锚点清单，防止修复时误删有效行为。
6. 实际运行的只读命令、PASS/FAIL 与任何负结果。

最后在 `_通信/致Codex.md` 顶部追加一行简短回执，给出报告路径、裁决计数和最关键不同意/修正点。完成后停止，不自动扩 N6，也不开始修复。

---
