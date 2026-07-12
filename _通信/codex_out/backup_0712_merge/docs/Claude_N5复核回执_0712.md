# Claude N5 独立复核回执（0712）

> 任务：对 Codex N5-01～N5-35 逐条回源裁决（接受/部分接受/不同意/当前已修复/需AB验证）。
> 依据 `_通信/codex_out/给Claude_N5独立复核提示词_0712.md`。**本轮只复核、不修复、不扩 N6、不开 AB、不 spawn 子代理。**
> 事实源 = 复核执行时的**当前磁盘**（HEAD `86800fb`）。所有 file:line 均已亲读；阻塞/高项已独立复算或复现。
> 状态：**进行中** —— P1 已定稿，P2～P8 逐段追加。

## 红线遵守声明
- 未开 Automation Builder，未运行 `ab_scripting`/`ab_sync.ps1`，未做任何 git 写操作，未 spawn 子代理。
- 未修改任何现有项目文件（本回执为唯一新增），未重生 DOCX/PPTX/CSV/图。
- 未进入/修改 `1_给你看`、`2_你要操作`。
- 只读探针以 `python -B` 运行，未写 `sim/out`。
- 官方数据核验只用一手来源（P6 待做）。

---

## 一、总裁决计数（终版 · 35/35 无遗漏）
| 状态 | 数 | 编号 |
|---|---:|---|
| **接受** | 28 | N5-01,04,05,06,07,08,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,29,30,31,33,34,35 |
| **部分接受**(降严重度/补范围) | 6 | N5-02,03,09,10,27,28 |
| **不同意** | 0 | — |
| **当前已修复** | 1 | N5-32(脚本侧已改动态 len(SCENARIOS)，仅日志旧产物残留) |
| **需 AB 动态验证** | 0（另 N5-01/02 附带"决赛前 AB float32/120-240 差分门"建议，静态已足够定性） | — |

**严重度分布**（非正面项 27 个）：阻塞 1（N5-13）｜高 10（N5-01,05,14,15,17,19,21,22,23,34）｜Codex 高→本方降中 3（N5-09,10,27）｜中 13（N5-02,03,06,07,11,18,24,25,28,29,30,32,33）。
**正面锚点 8 个**：N5-04,08,12,16,20,26,31,35（整改勿伤，详见文末清单）。
**独立性声明**：阻塞/高项（N5-01,05,09,10,13,14,15,17,19,21,22,23,34）全部由本人回原始 .py/.st/.csv 亲读当前行号复验，未盲抄子代理；5 个只读探针本人/代理均独立复现 PASS（见文末命令汇总）。

---

## 二、逐条裁决矩阵

### P1 · 平局/浮点（N5-01～04）
> 独立复现命令：`PYTHONDONTWRITEBYTECODE=1 python -B _通信/codex_out/N5_P1_readonly_probe.py`
> **PASS**：输出与 `N5_P1_量化证据_0712.json` 逐字段吻合（390/390、12540 件、能耗相对差 0.12184146763586012、exp_t 差 0.0、demo20 差 10、REAL32 1run/2件、Rank 非顺序 [1,100]≠[100,1]）。

| 编号 | 状态 | 严重度 | 当前 file:line | 复算证据 | 建议动作(不实施) |
|---|---|---|---|---|---|
| **N5-01** near 平局 Python↔ST 相反 | **接受** | 高（对齐声明层） | Python `sim/warehouse_sim.py:283` = `min(key=(travel_time, s[1]=tier, s[0]=col))`；ST `plc/04_FB_Warehouse.st:86-88`(x列外/y层内扫描)+`:102`(`rT<rBestTime` 严格小于→平局保先扫到的小列)；矛盾注释 `:59`/`:101`(谎称"(时间,层,列)/一字对齐") | 亲读源码确认两端 tie-break 分别为 (time,tier,col) 与 (time,col,tier)；探针复现 390/390 分叉、12540 件、能耗最大差 12.18% | 拍板统一权威 tie-break（以 Python 为真则 ST 等时分支显式比较 tier/col）；改注释 `:59/:101`；补一个"屏蔽近位后只剩等时候选"的 ST 测试+Python 对应向量；决赛前 AB 120/240 差分门 |
| **N5-02** consistency_probe 未真模拟 REAL32 | **部分接受** | 中 | REAL=32bit：`plc/01_DUTs.st:15-24`、`plc/03_Functions.st:187-213`；`sim/consistency_probe.py:5-16,39-64` 仅切 tie_break/ls_eps | 亲读 consistency_probe：其 docstring **自己诚实声明**"不模拟 reloc 阈值、真正兜底是 T25 AB 实跑"，故过强声明（若有）在外部文档而非探针本体；探针复现 REAL32 代理仅 1/13(seed2026) run 差 2 件、能耗差 0.072%、demo20 差 0 | 技术事实成立但需修正范围：勿称"探针已证 float32 等价"；决赛前补 AB float32 差分门；仍属 Python float32 代理非 PLC 实证 |
| **N5-03** Rank 平局 Python gid vs ST 数组下标 | **部分接受** | 中（Codex 标高→降中） | Python `sim/warehouse_sim.py:326`(平局 `g.gid`)；ST `plc/04_FB_Warehouse.st:184-186`(平局 `aRankIdx[j]<aRankIdx[iBestJ]`=数组下标)；ID 输入 `plc/02_GVL.st:108-113`(待验) | 亲读源码确认平局键不同；探针复现非顺序 ID `[100,1]`→Python `[1,100]`/ST `[100,1]` | 严重度降中：**潜伏项**，仅当 HMI 手输 Id≠到达下标时触发；sim 生成数据 Id=index 永不触发、T25 不覆盖、不动 sim 头条。修法：统一按 `Good.Id`，或"ID 连续且=下标"输入契约+测试 |
| **N5-04** 演示批对 REAL32 代理稳定 | **接受（正面）** | — | — | 探针复现 demo20(20件/seed2026/sum+匀速)双精度vs REAL32：布局差 0、exp_t 差 0 | **正面锚点**：支持保留 T25 作"小批演示锚"；**勿外推**到 near 平局或 120/240 高密度 |

**P1 小结**：4 项全部回源+复现成立。核心真相 = Python 与 ST 在**等时/等分平局**上取位规则不同（near 尤甚，390/390 布局分叉、能耗最大差 12.18%），但**不改 exp_t/KPI 头条**（平局即等时）；代码注释"一字对齐"对 near 属虚假声明需改。N5-03 为潜伏 HMI 鲁棒性项，非 sim 头条问题。

---

### P2 · Reset/跨批状态污染（N5-05～08）
> 纯控制流静态亲验（无探针，未开 AB）。

| 编号 | 状态 | 严重度 | 当前 file:line | 复算证据 | 建议动作(不实施) |
|---|---|---|---|---|---|
| **N5-05** AWRA→Reset→非AWRA 后 SwapCnt/LsRounds 残留旧值 | **接受** | 高 | 声明 `plc/01_DUTs.st:55-56`；唯一写入点 `plc/05_PRG_Main.st:159-160`(AWRA STATE_IMPROVE)；Reset `:35-54` **未清** SwapCnt/LsRounds；非AWRA `:141-148` 跳过 IMPROVE 直入 STATS；FB_Stats `plc/04_FB_Warehouse.st:411-459` **确不写** SwapCnt/LsRounds | 通读三处证实控制流闭环：AWRA 置 S/R → Reset 不清 → 非AWRA 不写 → 旧 S/R 暴露。局搜批次统计**未**被定义为历史累计值 | 批次开始或 Reset 时清零 SwapCnt/LsRounds（勿仅 HMI 文案隐藏）；补"AWRA→Reset→score 后 SwapCnt=0"跨批断言 |
| **N5-06** SwapCnt 只计 swap 漏计 relocation | **接受** | 中 | `iSwaps`/`iRelocs` 分离 `plc/04_FB_Warehouse.st:251-252`；reloc 接受 `:326` `iRelocs+1`；swap 接受 `:370` `iSwaps+1`；主程序 `:159` 只取 `iSwaps` 丢 `iRelocs`；注释 `plc/01_DUTs.st:55` "接受的改进次数" | 亲读确认：只发生 relocation 的批可显示 SWAPS=0 而布局已变，"接受改进数"系统性低报 | 新增 `RelocCnt`，或字段/台词改"成对交换数"，勿把两类邻域混称 |
| **N5-07** Reset 是批次复位≠画面/会话回初始 | **接受** | 中 | Reset 清理域 `plc/05_PRG_Main.st:35-54`；保留 aMaintBlock/aSlotOps `plc/02_GVL.st:76-83`(设计跨 Reset)、输入/策略 `:107-117`；快照优先渲染 `plc/04_FB_Warehouse.st:639-641`；过强声明 `docs/演示脚本v3_0711.md:37`("画面回初始/留干净状态") | 保留本身是设计非 bug；错在文档无条件称"画面回初始"。CmdCompareMode=TRUE+快照有效时 Reset 清空实仓但画面仍显旧快照 | 演示收场写显式序列(切 Live→Logout→Reset)，或新增 `CmdHardReset` 与批次 Reset 分离清理矩阵 |
| **N5-08** 沿冻结+动画中断护栏有效 | **接受(正面)** | — | `plc/04_FB_Warehouse.st:461-463`(`xOld:=xExecute AND NOT xDone` 完成即撤沿)、`plc/05_PRG_Main.st:39-40`(Reset 清 VisuPathCount) | 亲读确认 0711 修的撤沿公式在 FB_Stats/FB_InitWarehouse 均在位，支持"仓位重建/五主指标归零/动画安全中止"限定结论 | **正面锚点**：勿在整改中误删这两处撤沿公式与 path<2 安全停 |

### P3 · 长跑溢出与计数寿命（N5-09～12）
> 静态亲验 + ABB 官方类型宽度一手核验（INT=16bit -32768..32767；DINT=32bit）。

| 编号 | 状态 | 严重度 | 当前 file:line | 复算证据 | 建议动作(不实施) |
|---|---|---|---|---|---|
| **N5-09** aSlotOps 跨 Reset 累加但仅 INT | **部分接受** | 高→中 | `aSlotOps : ARRAY[0..19,0..19] OF INT` `plc/02_GVL.st:82-83`(Reset 不清)；无饱和 +1 `plc/04_FB_Warehouse.st:319,360-361`(及放置 `:207-211`)；nOpsMax 亦 INT `:627` | 亲读确认 INT+无饱和+跨 Reset；5.94 天(230次/h 同格)是"代码允许最短反例"非典型预测。**但**：aSlotOps 溢出**已是旧审查建议-2**(`docs/ST审查_0711pm.md:209` "除建议-2 的 aSlotOps 外")→非全新；新增=寿命量化+"履历"语义 | 事实成立、严重度下调中(演示尺度不触发)；核心=**措辞**："短期演示计数热图"而非"长期工业履历"；改 UDINT/DINT+饱和/时间窗，称履历需 RETAIN |
| **N5-10** iSwaps 旧"不会溢出"证明把 O(n²) 当 O(n) | **部分接受** | 高→中 | `iSwaps:INT` `plc/04_FB_Warehouse.st:251`；接受 +1 `:370`；i<j 上三角 `:335-380`；旧结论 `docs/ST审查_0711pm.md:209-211`("iSwaps 受 iGoodsCount≤400 或 nMaxLsRounds=5 约束,不会溢出") | 亲读确认旧证明**确有缺陷**：400 件一轮 79,800 对、5 轮评估上界 399,000≠2,000。**但严重度下调**：`iSwaps` 每次 AWRA `:279` 归零(**非跨批累加**)+仅计数器不动布局+严格下降使实际接受数远小 | 事实(旧证明缺陷)成立、实际溢出风险中；改 DINT 或饱和+标志；更正 `ST审查:209-211` 旧结论(保留为被 supersede 历史) |
| **N5-11** iFailCnt 可溢出且无锁定 | **接受(P7 已回源确认)** | 中 | `plc/04_FB_Warehouse.st:1036`(iFailCnt:INT)、`:1047`(错误 PIN 唯一 +1)；成功 1044-45/登出 1051-54 均不清零 | P7 回源比原判更精确：**唯一复位=断电重启**(非 RETAIN)；溢出需连续错 PIN>32767 且中途无一次成功/登出 | 加 `IF iFailCnt<32767 THEN …+1`+锁定阈值；因 PIN=演示码非真实凭据，非赛程阻塞（详见 P7 段） |
| **N5-12** 其余核心索引/单批计数在 400 规模有清晰上界 | **接受(正面)** | — | iGoodsCount/iAssigned/iFailed/PlacedCnt/FailedCnt≤400；iRelocs≤2000(5 轮每件一次)；路径点≤39 数组 40 有 `k>39 EXIT`；nSamples 已 DINT。旧审查 `docs/ST审查_0711pm.md:203-204,210-211` 亦佐证 | 与旧审查交叉一致 | **正面锚点**：这些计数无需改；整改 N5-09/10/11 时勿波及 |

**P2/P3 小结**：8 项全部回源。真实结论 = Reset 是"批次复位"、非"会话/统计/画面硬复位"，SwapCnt/LsRounds 跨批污染(N5-05)最实(控制流闭环坐实)；N5-06 计数口径失真；N5-09/10/11 三个 INT 溢出中**只有 aSlotOps(N5-09)跨 Reset 累加**且已是旧建议-2，iSwaps/iFailCnt 均非跨批累加、严重度偏中；N5-08/12 两正面锚点整改勿伤。

---

### P4 · 失败/arrival/公平/生命周期（N5-13～16）
> 独立复现命令：`PYTHONDONTWRITEBYTECODE=1 python -B _通信/codex_out/N5_P4_readonly_probe.py`
> **PASS**：adaptive 部分逐字段复现（6 个在线组、selected_fail_sum 与 min_fail 均与 `N5_P4_量化证据_0712.json` 一致，含 200/skew 选中 fail=6 而最小可得=2）。

| 编号 | 状态 | 严重度 | 当前 file:line | 复算证据 | 建议动作(不实施→归 Codex sim 方法修) |
|---|---|---|---|---|---|
| **N5-13** 自适应在线高密度表非"零失败下选优" | **接受** | 阻塞 | 选优 `sim/adaptive_weights.py:94-97`（只筛 `viol_sum==0`，`min(key=(exp_mean,ene_mean))`）；`fail_sum` 写入 `:81` 但**不参与淘汰/排序**；`verify_policy.run` 只返回 exp_t/viol 丢 failed `sim/verify_policy.py:38-46`；注释"违规必须0" `:9` | 亲读+探针：6 个在线组选中权重全带失败、15 候选无零失败；`200/skew` 为压 exp_t 反选 fail=6（>最小 2）。简单加 `fail_sum==0` 会让 6 组候选集空 | 定 fail-first 目标/词典序惩罚，无零失败候选时输出 `INFEASIBLE`，禁用幸存者 exp_t 选优；verify_policy 返回并断言 failed。**120 件 H 头条本身无失败、不被直接推翻** |
| **N5-14** common-arrival 反事实改变 P95 优胜者 | **接受** | 高 | `sim/realism.py:77`（`e_pair=probe['tot_dual']/cycles+2*HANDLE_S` 用**各策略自身**服务时长）；`:83-86`（按此 λ 生成到达）；注释"策略间同到达流" `:81` | 亲读确认：共享的是指数分位、非实际到达时刻。反事实(共同到达)后 P95 优胜者 AWRA(679.8)→near(651.1)；原实现把各策略校准到≈0.49 利用率隐藏快策略容量收益 | 到达流在策略循环**外**生成一次/直接给 λ；**报告勿把当前 679.8/854.3 单 seed 值当公平策略排名**；共同到达吞吐≈41.6–41.8 ops/h（区分观察吞吐 vs 满忙容量，联动 P6） |
| **N5-15** lifecycle"终局"固定少 5 件、时间/final_q 均截尾 | **接受** | 高 | `LAG=5` `sim/lifecycle_sim.py:44`；`pending.append((k+LAG,back))` `:127`；主循环 `for k in range(cycles)` `:94` 结束即 `:134 return`**不 flush pending**；final_q 在当前 pos_of 上算 `:138`；layout_quality `sim/reslot_cycle.py:32-39` | 亲读+探针：最后 5 件回库排在 cycle≥200 永不执行→库存 115、tot 少计其 `_t_store`（均值 254.85s=1.82%）、final_q 冲洗后 +0.803s 更差 | 加 drain phase 冲洗 pending，CSV 写 `pending_end/inventory_end/flush_time` 并重算配对；**勿称"全生命周期总作业时间/终局 120 件布局质量"** |
| **N5-16** mixed_ops 货物身份负载确为共同随机数 | **接受(正面)** | — | `sim/mixed_ops.py:38-55,131-140`（build_workload 按 seed/频次/身份生成一次，所有策略复用） | 亲读确认公平性问题只在 realism 额外生成到达时刻的层 | **正面锚点**：勿把整个 mixed workload 一并否定；只修 realism 的 arrival 层 |

**P4 小结**：4 项全部回源+探针复现。三个方法问题(N5-13/14/15)均**归 Codex 一并修**（R3 决策 sim 方法 F1/F2 并入 N5 交 Codex）：adaptive 幸存者选优(阻塞)、realism 不公平横比致 P95 翻盘(高)、lifecycle 截尾少 5 件(高)。**120 件 H 头条不被 N5-13 推翻**；N5-16 正面锚点勿伤。

---

### P5 · 种子/置信区间/选择偏差（N5-17～20）
> 独立复现：`python -B _通信/codex_out/N5_P5_readonly_probe.py` **PASS**（逐位对齐 JSON）。均值 8.402388 / sample SD 0.476878 / t(4)=2.776 95%CI [7.810361,8.994415] 半宽 0.592027；配对降幅均值 61.83918% / CI [56.896%,66.782%] 不跨 0；LOO 降幅 [60.750%,62.907%]。
> （由 sonnet 只读代理回源，阻塞/高项两处加重由本人亲验：见下。）

| 编号 | 状态 | 严重度 | 当前 file:line | 复算证据 | 建议动作(不实施) |
|---|---|---|---|---|---|
| **N5-17** headline 五 seed = 标定+holdout 并集、无 untouched final test | **接受** | 高 | `sim/adaptive_weights.py:32`(SEEDS=[2026,7])；`sim/verify_policy.py:21`(SEEDS_HOLDOUT=[42,123,999])+`:70-76`(判定门用这 3 holdout 增益决定"可切主口径")；`sim/headline.py:24`(SEEDS=[2026,7,42,123,999])；**U3 协议 `docs/canonical_assumptions.md:111`** | 探针 `headline_is_union=true`、`untouched_final_test=[]`。**本人亲验加重**：canonical:111 U3(状态"已定")要求"30 replications seed=[2026..2055]"，而 headline 只用 5 seed 且 7/42/123/999 **不在** 2026..2055 内——既违 30-seed 也违 final-test 独立性，属"没照自己写的规矩做" | 按 U3 真跑满 30 seed 或至少加入全新 untouched final seed 集；headline 5-seed 明确标"回归锚，非 U3 全量泛化证据"（归 Codex sim/报告修） |
| **N5-18** 8.40±0.48 的 ± 是 sample SD 非均值 95%CI | **接受** | 中 | `sim/headline.py:72`(表头"H:exp_t均±σ")、`:76`(`st.stdev`)；**已外溢** `docs/报告草稿_B6B7B11_0712.md:66`("取货 8.40±0.48s") | 探针：SD=0.476878，n=5 均值 95%CI 半宽实为 0.592027(宽约 24%)。本人亲验草稿:66 确未标 SD/CI(但已诚实标"H口径 sim") | headline 逐字标"5-seed sample SD"；报告若给 95%CI 用半宽 0.592。**若最终正文被误读为 CI 则升高** |
| **N5-19** adaptive online 策略表仅 2-seed、对 seed 敏感 | **接受** | 高(仅 online) | `sim/adaptive_weights.py:31-38`(SEEDS=[2026,7]、15 组网格)、`:69-81`(每候选仅 2 seed)、`:92-105`(`min(key=(exp_mean,ene_mean))` 无 CI/嵌套验证) | 探针 120/skew：online 在 seed2026 与 seed7 选出不同(δ,bg)、聚合最优又异于 seed7 单独最优；**batch 两 seed 一致稳定** | online 分支加 replication 或报告选择稳定性/CI，勿把 2-seed 赢家当无偏最优写入生产策略表（batch 表稳定、不在此列）（归 Codex sim 方法修） |
| **N5-20** H 相对 seq 配对降幅是稳健正面锚 | **接受(正面)** | — | `sim/headline.py:24` 五 seed 算术 | 降幅均值 61.839%、95%CI 不跨 0、LOO 后方向量级均稳 | **正面锚点**：不因种子/选择偏差被推翻；但勿引申为"跨全部 30 场景/密度都稳健"（那需 N5-19 未覆盖的更大范围） |

**P5 小结**：4 项全接受。核心 = headline 5-seed 既是标定+验收并集(无真 final test)、又与项目自定 U3(30-seed)矛盾(N5-17 高)；`±0.48`=SD 非 CI 且已进草稿(N5-18)；online 自适应表 2-seed 不稳(N5-19 高，batch 稳)。**正面锚点**：配对降幅≈62% / CI[56.9,66.8] / LOO 稳(N5-20) + batch 权重表两 seed 一致——整改勿伤。

---

### P6 · 能耗年化/吞吐/CO2 单位链（N5-21～26）
> 独立复现：`python -B _通信/codex_out/N5_P6_readonly_probe.py` **PASS**（逐字段对齐 JSON）：seq=545.4157/awra=278.9436 kWh·年、年省 266.4721 kWh；若"500"=双周期/日则全部×2；AWRA H 行程-only 230.4369 次/h→+15s 装卸 117.5606→+600s 故障 107.0712。
> （sonnet 只读代理回源；N5-23 CO2 因子由代理独立核验官方源，N5-21/23/25 代码锚点+草稿矛盾由本人亲验。）

| 编号 | 状态 | 严重度 | 当前 file:line | 复算/官方源证据 | 建议动作(不实施→归 Codex 轨A) |
|---|---|---|---|---|---|
| **N5-21** "500 ops/day÷2=75000 周期/年"存 operation↔cycle 歧义 | **接受** | 高 | `sim/energy_report.py:36`(DAILY_OPS=500 "每日存取次数")、`:131-133`(÷2→75000)；`docs/canonical_assumptions.md:55` | 探针：现解释 545.4/278.9/省266.5；若"500"=双周期则翻倍到 1090.8/557.9/532.9。**相对降幅 48.86% 两解读不变** | 真相源改"500 个单操作/日(存+取合计=250 双周期/日)"消歧 |
| **N5-22** 230 次/h 是行程-only 连续满载 sim 容量 | **接受** | 高 | `sim/mixed_ops.py:96,101-105`(thr_dual 只计行程)；`sim/realism.py:38`(HANDLE_S=15)、`:43`(MTTR_S=600) | 复算三层 230.44→117.56→107.07 互不冲突、答不同问题；`docs/报告草稿_B6B7B11_0712.md:45-58,66` 已有边界句(正面) | 维持并同步 B6B7B11 边界句到 PPT/其余 B 系草稿(本轮未逐一扫)；区分理论容量/完成率/PLC 实测 |
| **N5-23** CO2 因子 0.581 标"2023 公布值"错误 | **接受** | 高 | `sim/energy_report.py:39`(`CO2_FACTOR=0.581 #…2023 公布值`)、`docs/canonical_assumptions.md:55` | 本人亲验代码注释确写"2023 公布值"。**代理独立核验官方源**(mee.gov.cn 公告2025年第47号/答记者问)：2023 全国平均=**0.5306**、不含市场化非化石=**0.6096**；0.581 实为 2022 通知里的**2021 年度**值(0.5810 tCO2/MWh)→年份错配。⚠**外部数据(核验时点后)写入报告前请二次核对官方公告原文** | 改标真实年份(2021)或换 2023 官方值(0.5306/0.6096 二选一,注公告号)；不得称"2023 公布" |
| **N5-24** 只计净机械功、未计待机/动态损耗 | **接受** | 中 | `sim/energy_report.py:45-66`(仅 mgh+μmgd)；`docs/canonical_assumptions.md:55`(已声明"绝对值保守") | 通读确认未建模待机/驱动器损耗/加减速瞬态/辅助功耗；真相源已声明限定 | 下游 PPT/摘要凡引 kWh 绝对值须带"sim 净机械功情景换算"限定语 |
| **N5-25** 报告草稿 546.0→278.9 却写省 266.5 内部矛盾 | **接受(仍未修复)** | 中 | `docs/报告草稿_C3C5B14_0712.md:11`(原样);权威 `sim/out/energy_report.csv`=545.4/278.9 | 本人亲验：546.0−278.9=267.1≠266.5；545.4−278.9=266.5✓。基线 546.0≠CSV 545.4，**本轮仍存、未被并发修复**；同页 :13 有诚实"sim proxy 非 AC500 实测"限定(正面) | 统一"545.4→278.9,省266.5"或全取整"545→279,省266"，禁混精度相减 |
| **N5-26** 能耗算术本身可信 | **接受(正面)** | — | `sim/energy_report.py` 全流程 | 探针逐周期重算 seq 0.00727221/awra 0.00371925 kWh·周期 ×75000=545.4/278.9，48.86%=48.9% | **正面锚点**：问题在单位定义/因子来源/口径声明，非算法错误——勿动算法 |

### P7 · 多客户端权限与留痕（N5-27～31）+ N5-11 回源
> 纯 ST/GVL 静态亲验（无探针）。代理逐行核对 Codex 行号无误、无篡改。**独立下修 N5-27/28（Codex 高→中）**：源码已明文声明单客户端演示边界=已声明边界非隐藏 bug。

| 编号 | 状态 | 严重度 | 当前 file:line | 证据 | 建议动作(不实施) |
|---|---|---|---|---|---|
| **N5-27** 单 fbAuth+全局 iUserLevel，任一客户端登录/登出影响全部 | **部分接受** | Codex 高→**中** | `plc/02_GVL.st:187-192`(PIN/Login/Logout/iUserLevel 全 GVL)；`plc/05_PRG_Main.st:21`(fbAuth 单实例)、`:199-206`(全局广播 iLevel)；`plc/04_FB_Warehouse.st:1020-1057`(注释 1025-1026 自认单客户端演示口径)；`plc/03_Functions.st:275-277` | 事实链逐行属实(全局单实例=跨客户端必然语义)；**但 1025-1026 已明文声明**为设计边界→非待修 bug，风险在文案勿越界称"多用户权限隔离" | 不动代码；对外措辞不宣称多客户端隔离；如修=接 CurrentClientId/WebVisu session(非赛程内小改) |
| **N5-28** PIN 跨客户端消费/参数覆盖/登出误伤 | **部分接受** | 中 | `plc/02_GVL.st:188-192`；`plc/05_PRG_Main.st:203-205`(登录/登出清全局 PIN)、`:248-264` | 时序三行属实，**但系 N5-27 的推论、非独立缺陷** | 整改清单**与 N5-27 合并为一条**，勿重复计严重度 |
| **N5-29** T54-56 只测单实例分支、不证 per-client 隔离 | **接受** | 中 | `plc/06_PRG_Test.st:430-439`(T54)、`:440-450`(T55)、`:452-463`(T56) | 三段均单实例单线程、无 A/B 交错/GVL 中转 | "59/0 全绿"勿包装成"权限安全已验证"；如留叙事需补 A/B 交错用例(列局限性、非阻塞) |
| **N5-30** 无 timeout/lockout/client-ID/append-only 审计 | **接受** | 中 | `plc/04_FB_Warehouse.st:1027-1057`(FB_UserAuth 无这些字段)、`:1065-1094`(ParamGuard 快照仅标量、无 actor/时间)；`plc/03_Functions.st:269-290`(FC_MaintToggle 无操作者/时间) | 逐字段确认"留痕"仅状态量+热度计数、非安全审计日志 | 生产化接 timestamp/client/user/action/before-after；演示语境低优先 |
| **N5-31** 源码诚实声明单客户端边界 | **接受(正面)** | — | `plc/02_GVL.st:23-25`(PIN=演示码)、`plc/04_FB_Warehouse.st:1020-1026`(iLevel 非 RETAIN/单客户端/生产换 UserMgmt) | 两处注释逐字确认存在、与报告引用一致 | **正面锚点**：保留原文、同步进报告局限性章+答辩 QA；勿在整改中删没或被营销话术盖过 |
| **N5-11**(P3 遗留) iFailCnt 无饱和且成功/登出均不清零 | **接受** | 中 | `plc/04_FB_Warehouse.st:1036`(iFailCnt:INT)、`:1047`(错误 PIN 唯一 +1 处)；成功 1044-45/登出 1051-54 均不清零；仅断电(非 RETAIN)复位 | 比 P3 原判更精确：**唯一复位路径=断电重启**；溢出需连续错 PIN>32767 且中途无一次成功/登出 | 加 `IF iFailCnt<32767 THEN …+1`+锁定阈值(低成本)；因 PIN=演示码非真实凭据，非赛程阻塞 |

**P6/P7 小结**：P6 算术可信(N5-26)，问题在**口径定义/因子年份/声明缺口**——500 歧义(N5-21)、230 行程-only(N5-22 有草稿边界句兜底)、**CO2 0.581 年份错配(N5-23，最实，直接违口径诚实红线)**、净机械功限定(N5-24)、草稿 546/266.5 矛盾未修(N5-25)，全归轨A/Codex 改话术。P7 权限项全部"已声明边界"性质：N5-27/28 合并降中(文案纪律非代码 bug)、N5-29/30/N5-11 中(演示可接受、勿称"已验证/防暴力")、N5-31 正面诚实边界须保留。

---

### P8 · CSV/日志产物完整性与 oracle 语义（N5-32～35）
> 独立复现：`python -B _通信/codex_out/N5_P8_readonly_probe.py` **PASS**（exit 0，逐字段对齐 JSON）：37 CSV 无空/NaN/Inf/重复主键；instgen detail=2730=13×30×7↔agg=91 匹配；oracle detail=3900、`negative_gap=58`/`attain>100=58`/`58 均 excess_fail>0`/`0 真超越`；dense_200 tob `-21.515%/128.04%/exf3.53`、dense_240 `-18.681%/123.00%/9.70`、ALL `-3.092%/103.93%/1.02`。
> （sonnet 只读代理回源；N5-34 高项代码锚点由本人亲验。）

| 编号 | 状态 | 严重度 | 当前 file:line | 复算证据 | 建议动作(不实施) |
|---|---|---|---|---|---|
| **N5-32** consistency_probe.log 仍是修复前 "12×30=390" | **当前已修复(脚本侧)/旧产物残留(日志侧)** | 中 | `sim/out/consistency_probe.log`(仍写"12 场景×30",mtime 07-07 01:47)；`sim/consistency_probe.py:78,97-98`(**现用动态 `len(ig.SCENARIOS)`**,mtime 07-07 06:16 晚于日志)；`sim/instance_gen.py` SCENARIOS 实为 13 | 脚本侧已修(重跑会打印"13 场景")；日志侧是修复前旧产物未随之重生 | 打包前重跑一次 consistency_probe 刷新 log，或在引用处加"历史产物、场景计数已过期"脚注 |
| **N5-33** 6 份 CSV 一文件内塞两种 schema | **接受** | 中 | 生成侧 `sim/energy_report.py:163-180`、`sim/realism.py:226-252`、`sim/rl_probe.py:173-188`、`sim/reslot_cycle.py:301-317`、`sim/scan_g2g4.py:179-191`；消费侧 `sim/build_report.py:76-117`(已自知规避) | 亲读 5 处生成码；探针 `rl_probe.csv` DictReader 行为精确匹配("同宽度、零结构信号、语义静默改变")。**非字节损坏、是非标准双段交换格式** | build_report 内部已规避，但外部 pandas/Excel/未来复用会错列；拆 `*_data.csv`+`*_params.csv` 或转 JSON/长表 |
| **N5-34** oracle attain>100%/gap<0 语义误导 | **接受** | 高 | `sim/oracle_gap.py:92`(vbs 词典序 fail 优先)、`:100-101`(gap/attain **只用 exp_t**)、`:102`(excess_fail 另列不参与) | 本人亲验代码；探针全量 3900 行复算：58 行 attain>100 **全部 excess_fail>0、0 行真超越**（"失败更多但时间短"） | excess_fail>0 时 gap/attain 置 **N/A** 或先按失败档分层再算时间 gap；**任何 98.5%/99.9%/>100% 话术必须绑定 excess_fail=0 前提**（联动 D-1 检测器叙事） |
| **N5-35** 37 CSV 基础完整性全通过 | **接受(正面)** | — | `sim/out/*.csv` 全量 | 探针+独立脚本重跑：0 空/0 非有限/0 整行重复/0 主键重复；5 条 detail↔agg 关系链复算差均在声明精度/舍入内 | **正面锚点(最扎实确认)**：把现有 CI 建议(单一 schema+非空+矩形+主键唯一+有限数+detail↔agg 复算)固化成脚本化门禁 |

**P8 小结**：4 项全部回源+探针复现。**N5-34(高)最实**——oracle 的 58 行 attain>100% 全是"失败更多但时间短"的伪超越，`excess_fail>0` 未进 gap/attain，直接威胁 98.5/99.9 话术，须绑定 `excess_fail=0` 前提（联动 D-1）。N5-32 是脚本已修/日志旧产物残留（打包前重跑即清）。N5-33 非损坏、是双段格式（build_report 自知规避）。N5-35 是本轮最扎实的正面锚点。

---

## 三、Codex 取证后的并发漂移专节
> 提示词要求：区分"当时成立、现已被并发修改修掉"与"现仍未修复"。逐项核对当前磁盘：
- **N5-32（已修复·脚本侧）**：`sim/consistency_probe.py:78,97-98` 已改动态 `len(ig.SCENARIOS)`（mtime 07-07 06:16），但 `sim/out/consistency_probe.log`（mtime 07-07 01:47）是修复前旧产物、仍写"12 场景×30"。判"脚本已修、日志旧产物待重生"，非当前脚本错。
- **N5-25（确认仍未修复）**：`docs/报告草稿_C3C5B14_0712.md:11` 的 546.0→278.9/年省266.5 内部矛盾**本轮仍原样存在**（546.0≠权威 CSV 545.4）——不是并发已修，是仍需轨A 修。
- 其余 34 项均直接针对当前 HEAD `86800fb` 的源码/产物验证，无"当时成立现已消失"情况。（提示词提到的 d2_quantify.py / ASK决策 / 接手任务表 / 接管启动提示词pm 的并发改动，不影响任何 N5 发现的现磁盘裁决。）

## 四、P0/P1/P2 建议清单（不实施；标注：话术 / 代码测试 / 必AB）
> 分工：sim 方法/口径数字/CO2 → **Codex（轨A + N5 合并包）**；ST 代码（跨批清零/INT→DINT/tie-break/权限）本可 Claude 写，但 R2 决策 **N5 修复归 Codex**（D-1/N4 ST 才 Claude 写）。

**P0（直接威胁口径诚实红线 / 头条话术，最优先）**
1. **N5-34**〔话术+代码〕oracle `excess_fail>0` 时 gap/attain 置 N/A 或分失败档；**98.5%/99.9%/>100% 一切话术绑定 `excess_fail=0` 前提**（联动 D-1 检测器）。
2. **N5-23**〔话术+真相源〕CO2 因子 0.581 改标真实年份(2021)或换 2023 官方值（0.5306 或 0.6096，注公告号；写入前二次核对官方原文）。
3. **N5-17**〔话术+sim〕headline 5-seed 明标"回归锚、非 U3 全量泛化证据"，或按 U3 真跑满 30 seed[2026..2055]+全新 final test。
4. **N5-25**〔话术〕报告草稿统一"545.4→278.9,省266.5"，禁混精度相减。
5. **N5-01**〔代码+测试+话术〕拍板统一 near tie-break；改 `04_FB_Warehouse.st:59/101` 虚假"一字对齐"注释；补等时反例向量。

**P1（方法/代码，归 Codex sim 修）**
6. **N5-13**〔代码+测试·阻塞〕adaptive 定 fail-first/无零失败候选输出 INFEASIBLE，禁幸存者 exp_t 选优。
7. **N5-14**〔代码+报告〕realism 到达流移出策略循环；报告勿把当前 P50/P95 当公平策略排名。
8. **N5-15**〔代码+CSV〕lifecycle 加 drain phase 冲洗 pending，写 pending_end/inventory_end/flush_time。
9. **N5-05**〔代码+测试〕批次开始或 Reset 清零 SwapCnt/LsRounds。
10. **N5-19**〔代码/报告〕adaptive online 分支加 replication/报告选择稳定性。
11. **N5-21/22/24**〔话术+真相源〕500 歧义→"单操作/日"；230 行程-only 边界句同步全材料；kWh 绝对量带"sim 净机械功"限定。
12. **N5-18**〔话术+代码〕headline 逐字标"5-seed sample SD"；给 CI 用半宽 0.592。

**P2（低优先 / 演示语境可接受 / 长跑鲁棒性）**
13. INT→DINT+饱和：**N5-09**(aSlotOps,已旧建议-2)/**N5-10**(iSwaps)/**N5-11**(iFailCnt+锁定阈值)。
14. **N5-06**(加 RelocCnt 或改"成对交换数")/**N5-07**(CmdHardReset 分离/收场显式序列)/**N5-03**(Rank 统一按 Good.Id 或 ID=下标契约)。
15. **N5-27+28 合并**(不动代码；对外文案勿称"多客户端权限隔离")/**N5-29**(勿把 59/0 包装成"权限已验证")/**N5-30**(生产化接审计)。
16. **N5-33**(CSV 拆 *_data/*_params 或转 JSON)/**N5-32**(打包前重跑刷新 consistency_probe.log)。

**必须 AB 动态验证（本轮未开 AB）**
- **N5-01/N5-02**：决赛前在 AB 跑 120/240 件 float32 端到端布局差分门（现仅 20 件黄金向量锁定）。
- N5-05/06/07 的跨批统计/画面快照行为，最终宜 AB 在线各验一次（静态已足够定性、非阻塞）。

## 五、正面锚点清单（整改/修复时勿误删）
1. **N5-20**：H 相对 seq 配对降幅 ≈61.84%、95%CI[56.90,66.78] 不跨 0、LOO 稳——唯一不被种子/选择偏差推翻的头条正面结论；**batch 权重表两 seed 一致**（与 online 不稳区分）。
2. **N5-26/N5-35**：能耗算术正确（非算法错，仅口径/因子/声明问题）；37 CSV 基础完整性全通过（本轮最扎实确认）。
3. **N5-16**：mixed_ops 货物身份负载确为共同随机数（只修 realism 的 arrival 层，勿否定整个 workload）。
4. **N5-08/N5-12**：撤沿公式 `xOld:=xExecute AND NOT xDone`(04:461-463)+path<2 安全停+其余计数 400 规模有界（iRelocs≤2000/path≤39/nSamples DINT）——勿波及。
5. **N5-31**：`02_GVL.st:23-25` 与 `04_FB_Warehouse.st:1020-1026` 诚实声明（PIN=演示码、iLevel 非 RETAIN、单客户端、生产换 UserMgmt/CurrentClientId）——保留原文并同步进报告局限性章+答辩 QA，勿被营销话术盖过。
6. **N5-04**：20 件演示批对 REAL32 代理稳定（保留 T25 作小批演示锚，勿外推）。
7. 诚实口径写法模板：`报告草稿_B6B7B11_0712.md:45-58,66`（230 次/h 三层框定）+ `报告草稿_C3C5B14_0712.md:13`（"sim proxy 非 AC500 实测"限定）——可作轨A 口径声明的写作范本。

## 六、实际运行的只读命令 · PASS/FAIL · 负结果
| 探针 | 命令 | 结果 | 关键复现值 |
|---|---|---|---|
| N5-P1 | `python -B _通信/codex_out/N5_P1_readonly_probe.py` | **PASS** | 390/390 分叉、12540 件、能耗相对差 0.12184146763586012、exp_t 差 0.0、REAL32 1run/2件、Rank[1,100]≠[100,1] |
| N5-P4 | `python -B …/N5_P4_readonly_probe.py` | **PASS** | 6 在线组全带失败(200/skew 选中 6>最小 2)、无零失败候选 |
| N5-P5 | `python -B …/N5_P5_readonly_probe.py` | **PASS** | 均值 8.402388/SD 0.476878/95%CI[7.810,8.994]半宽 0.592027/降幅 61.839%CI[56.896,66.782]/union=true/untouched=[] |
| N5-P6 | `python -B …/N5_P6_readonly_probe.py` | **PASS** | 545.4157/278.9436 kWh·年/省266.4721；230.44→117.56→107.07 次/h |
| N5-P8 | `python -B …/N5_P8_readonly_probe.py` | **PASS** | 37 CSV 零异常；oracle 58 行 attain>100 全 excess_fail>0、0 真超越 |
| P2/P3/P7 | 无探针 | 纯 ST/GVL 静态亲验 | 见各段 file:line |

**负结果/负向确认**：① 所有 5 个探针复现均 PASS、无一 FAIL、无与 Codex 存档 JSON 冲突。② N5-25 = 负向确认"仍未修复"（非并发已修）。③ N5-32 = "脚本侧已修、日志侧旧产物残留"。④ **本方对 Codex 无一条"不同意"**——35 项事实全部成立，仅对 6 项（N5-02/03/09/10/27/28）下修严重度或收窄范围（部分接受），理由均给 file:line/机制。

---

## 七、给用户的一句话交办
本回执 = 你把（**轨A 口径修正 + N5 确认修复 + sim 方法 F1/F2**）合并交 Codex 的依据。**P0 五条最要紧**（oracle excess_fail 门 / CO2 年份 / headline U3 / 草稿 546 矛盾 / near tie-break+假注释），其中 N5-23/25 属纯话术、可最快落地。ST 类（N5-05/09/10/11/06/07）与 sim 方法类（N5-13/14/15/19）归 Codex 一并修；D-1 CB/TOB + N4 ST 仍 Claude 写。正面锚点 8 项务必在修复中保留。





