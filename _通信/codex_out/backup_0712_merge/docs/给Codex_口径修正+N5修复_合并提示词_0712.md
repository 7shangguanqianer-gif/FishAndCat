# 给 Codex：口径修正 + N5 修复 + sim 方法 合并执行提示词（0712 最终版）

> 本文 **supersede** `docs/给Codex_口径修正提示词_0712.md`（其组1-4 执行清单被本文沿用引用）。转发**本文一份**即可，勿再单独转旧版。
> 用户转达方式（对 Codex 说）：
> **"读 `F:\abb_wh_work\docs\给Codex_口径修正+N5修复_合并提示词_0712.md` 并执行，结果写进 `_通信\致Claude.md`。"**

---

## 【提示词正文 · 复制给 Codex】

你现在执行 `F:\abb_wh_work` ABB 杯项目的**口径修正 + N5 修复 + sim 方法**三合一任务。**先读三份权威规格**，再动手：
1. `docs/Claude_N5复核回执_0712.md` —— N5-01~35 逐条裁决（**N5 修复的唯一规格**，含每条"建议动作"/严重度/当前 file:line）。
2. `docs/给Codex_口径修正提示词_0712.md` —— 口径修正 Phase1（**组1-4 + N4 增量执行清单全部沿用**，本文只做增删）。
3. `docs/Claude_N4复核回执_0712.md` + `docs/Claude_N2N3复核回执_0712.md` —— 口径字典与 N2-N4 裁决。

### ★ 地面真值（不可违反，摘自 N5回执/口径字典）
全部是 **sim 值**，绝不称 "AC500 实测/真跑"：
- **8.40**=5-seed H 均值(sample **SD** 非 CI)｜**8.6232**=sum H 单seed 回归锁(`test_sim.py:189`)｜**8.757/8.76**=**Python 加减速+静态 sim 结果**（**非** AC500 真跑、**非** PLC 代理，N4-01）｜**8.794** 只揭示 Python↔ST 分母差、**不进头条**｜**6.443**=匀速+静态(PLC 默认 `xUseAccel=FALSE`)｜**7.6202**=legacy and 历史锁(`test_sim.py:204`)。
- **98.5**=sim lexicographic 档，**不是** PLC 实测/理论上限(99.9/100)，且**必须绑定 `excess_fail=0` 前提**（见 N5-34）｜**81.6**=holistic 规则 390 实例 sim 评估。
- **59/0**=核心 ST+静态匀速黄金向量 AB 仿真通过｜**230 次/h、266.5kWh、48.9%、49.9/43.7/44.7、0.57** 全 sim。

### ★★ 红线（关键：ST 归属已重划，避免与 Claude 撞车）
- **禁改任何 `plc/*.st` 代码**（含 N5 的 ST 子集）。原因：N5-01/05/06/07/09/10/11 的 ST 改动与 Claude 待写的 **D-1 CB/TOB + N4-14~24** 落在**同一批 .st 文件**，为避冲突，**全部 ST 由 Claude 写**。你对 ST 只改"**文档里对 ST 能力的描述/注释话术**"（如 N5-01 的假"一字对齐"注释、A3/A4/C6 声称降级）。
- 禁开 Automation Builder；禁跑 `tools/ab_scripting`/`ab_sync.ps1`；禁 git 写。
- 改 `1_给你看/*.md` 后必须 `python tools/make_user_docs.py` 重生同名 DOCX；改 `sim/build_report.py`/`build_ppt.py` 后必须重生 `验证报告_draft.docx`/`答辩PPT_draft.pptx` + 文本抽取 + 逐页渲染 QA。
- 历史证据（F1-F17、旧审计、legacy 锁）加历史标签**保留不删**。
- **执行方式**：一次性认真改完全部，末尾输出**"总改动对照表（原句→改句→依据 file:line，按 A/B/C/D 分节）"**交 Claude 复核一次。

---

## A. 口径修正（沿用 `给Codex_口径修正提示词_0712.md` 组1-4 + N4 增量，全部执行）
按原提示词组1-4 逐条做，重点（根因优先）：
- **组1 真相源**：`canonical_assumptions.md:38-41` 头部 7.42/66.2%/74.3%/0.50 → **8.40±0.48/62.0%/67.3%/0.57**、H 锁 `7.6202→8.6232`（legacy 7.6202 标 `test_sim.py:204`）+ 加"PLC 默认 `xUseAccel=FALSE`"；`sim/headline.py:6,67` **and→sum**（不改脚本，文档改了会被下次 `python headline.py` 写回旧值——**这是所有 7.42 类漂移的根**）；`现状与任务.md:71,77,281,98`；`技术方向总库_0711.md` A1。
- **组2 报告/演示文本**、**组3 生成器/二进制**、**组4 渲染/审计**：照原清单。**8.757/8.76 一切"AC500 真跑/PLC 代理"称谓 → "Python 加减速+静态 sim 结果"**；98.5/holistic 统一用 **"AC500 当前部署 holistic(sim 评估 81.6%)；sim 另验 lexicographic 98.5%，完整路由依赖 PLC 未实现的 TOB/CB，该档补实现(方案乙 D-1)进行中"**。
- **图源铁律(N4-27)**：先改 `sim/plots.py`/`experiments.py` 口径标签与数据源，再改报告/PPT 生成器，**最后**重生二进制。
> 注：桌面 `智储优控_作战面板.html` 经 Claude 复核**已是最新诚实版（59/0、已标 sim）**，组4 里对面板的改动**跳过**，勿回退。

## B. N5 确认修复（规格=`Claude_N5复核回执_0712.md`，仅做其中 python/文档项；ST 项归 Claude）
**P0（最优先，直接威胁口径诚实红线）**
- **N5-34**〔`sim/oracle_gap.py:100-102` 展示层〕`excess_fail>0` 时 `gap/attain` 置 **N/A** 或先按失败档分层；**所有 98.5/99.9/>100% 话术必须写明"在 `excess_fail=0` 前提下"**（联动 A 的 98.5 措辞）。
- **N5-23**〔`sim/energy_report.py:39` + `canonical_assumptions.md:55`〕CO2 因子 0.581 标注错误（实为 2021 年度值，非"2023 公布"）：**二选一**——改标真实年份(2021)、或换 2023 官方值 **0.5306**(全国平均)/**0.6096**(不含市场化非化石)并注公告号（写入前请二次核对 mee.gov.cn 公告 2025年第47号原文）。
- **N5-17**〔`sim/headline.py`〕headline 5-seed=标定+holdout 并集、无 untouched final test、且违项目自定 U3(30-seed)：明标 **"5-seed 回归锚、非 U3 全量泛化证据"**，或按 U3 跑满 30 seed[2026..2055]+全新 final test。
- **N5-25**〔`docs/报告草稿_C3C5B14_0712.md:11`〕546.0→**545.4**（546.0−278.9=267.1≠266.5；545.4−278.9=266.5✓），禁混精度相减。
- **N5-01 话术部分**〔`plc/04_FB_Warehouse.st:59,101` **注释**〕删除虚假"与 Python 一字对齐/(时间,层,列)"，改为准确描述"near 平局按扫描序(时间,列,层)，与 Python(时间,层,列)不同"。**tie-break 代码统一=ST 改动，归 Claude，你只改注释话术。**

**P1（sim 方法/口径，归你）**
- **N5-18**〔`sim/headline.py:72,76`〕逐字标 "5-seed **sample SD**"；报告若给 95%CI 用半宽 **0.592**。
- **N5-21/22/24**〔`energy_report.py`/`canonical:55`/报告〕500→"单操作/日(=250 双周期/日)"消歧；230 次/h 补"行程-only 连续满载 sim 容量"边界并同步全材料；kWh 绝对量带"sim 净机械功情景换算"限定。
- **N5-32**〔`sim/out/consistency_probe.log`〕脚本已修(动态 len(SCENARIOS))、日志是旧产物：打包前重跑一次 `consistency_probe` 刷新 log，或引用处加"历史产物、场景计数已过期"脚注。
- **N5-33**〔6 份多段 CSV〕非损坏、是双段格式；`build_report.py` 内部已规避，但外部会错列：拆 `*_data.csv`+`*_params.csv` 或转 JSON/长表。

## C. sim 方法 F1/F2（用户 0712 定：并入 N5 一起修，不再"只加限定语"）
- **F1 = N5-13**〔`sim/adaptive_weights.py:94-97` + `verify_policy.py`〕在线高密度选优要 **fail-first**：无零失败候选时输出 `INFEASIBLE`，禁用幸存者 exp_t 选优；verify_policy 返回并断言 failed。
- **F2 = N5-14**〔`sim/realism.py:77,83-86`〕到达流**在策略循环外生成一次**（或直接给 λ），不按各策略反推 λ；报告勿把当前 P50/P95 当公平策略排名。
- 附 **N5-15**〔`sim/lifecycle_sim.py`〕加 drain phase 冲洗 pending，CSV 写 `pending_end/inventory_end/flush_time`；**N5-19**〔`adaptive_weights.py` online 分支〕加 replication 或报告选择稳定性/CI。
- **⚠ 改算法会移动 P50/P95 与部分头条数字**：改完**必须列"哪些数字变了、变多少"**交 Claude/用户，并**同步更新所有引用处**（报告/面板/canonical）。

## D. 整理体检增补（4 个只读代理新挖，原口径提示词可能未显式列的口径违例）
- `docs/DR-1_行业锚点_0712.md:12`：8.76 称"PLC 静态权重真跑" → sim 结果。
- `docs/答辩QA卡_C7_0712.md:18`："AC500 实测代理数字"（实测+代理自相矛盾，且与同文件 :70 冲突）→ "Python accel+static sim 代理值"。
- `docs/D2量化_0712.md:5,14,59,84`：反复称"AC500 真跑"（与同文件 :72 已写对处冲突）→ 统一 sim 结果称谓。
- `canonical_assumptions.md` 变更记录：补一条 **D-2 校准声明**（PLC 默认 `xUseAccel=FALSE`→6.443 vs 报告 H 口径 8.40=加减速+自适应，两口径差异沉淀进真相源）。
- **README 计数群**（纯计数/断链，非 sim 口径）：根 `README.md:26`(23→59)、`plc/README_PLC.md:13-16`(15/12/23→**17/15/59**),`:68-82`(measure_l4b 断链→`archive/`)、`tools/ab_scripting/README.md:3,10`(24→59)、`tools/visu_gen/README.md`(两页→三页 505+134+67、45→59)。
- `1_给你看/情报_往届与同类比赛.md:28,43`(23→59)：改 .md 后**必须** `python tools/make_user_docs.py` 重生 docx。

## 停手条件
D 完成即停。**以下不在本轮，归 Claude 或等用户单独授权**：
- **全部 ST 代码**（N5-01 tie-break 统一 / N5-05 SwapCnt 清零 / N5-06 RelocCnt / N5-09/10/11 INT→DINT / N5-07 CmdHardReset；以及 N4-14~24、方案乙 D-1 CB/TOB）。
- AB 在线长跑 / 400 件压测 / watchdog（需 AB，用户在场）。
- 提交包 manifest/requirements/allowlist（Claude 起草计划）。

---

## 【给用户的说明】
- 本文 = **"轨A 口径修正 + N5 修复(python/文档) + sim 方法 F1/F2 + 体检增补"** 四合一，转此一份 Codex 即可全做。
- **ST 全部留 Claude**（含 N5 的 ST 子集），避免与 D-1/N4 撞同一 .st 文件——这是相对最初"N5 交 Codex"的**必要修正**（否则双写冲突）。若你坚持 N5-ST 也给 Codex，须改为串行（Codex 先做 N5-ST → Claude 再做 N4/D-1），会更慢。
- Codex 改完输出"总改动对照表"，由 Claude 复核一遍再定稿。
