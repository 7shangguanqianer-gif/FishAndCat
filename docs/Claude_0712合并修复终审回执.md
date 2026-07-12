# Claude 0712 合并修复终审回执

> 依据 `_通信/codex_out/给Claude_复核0712合并修复最终结果.md` 做只读终审。事实源=**此刻磁盘**。
> 终审期间红线遵守：未新开 Automation Builder、复核动作未跑 ab_scripting、未 git 写、未 spawn 子代理、未扩 N6。
> ⚠ **时点声明**：Codex 取证与本终审之间，Claude 轨B 又推进了一个阶段（隐患清扫 11 项+T70-74 真实断言）并完成三轮 ab_sync。凡 Codex 报告与本回执冲突处，均为"事实再前进"，非任何一方伪报；本回执以最新事实为准。

## 1. 总裁决：**接受**

**Codex 合并修复可作为当前文档/二进制基线。** 其取证时点的"PLC 运行证据仍 59/0"结论在当时正确；本终审时点该证据已由轨B 三轮 ab_sync 升级为 **75/0**（见第 5 节），相关登记文件（plc_evidence.csv / canonical C11 / README:49 三态句）由 Claude 在本回执后做事实性刷新，**不构成对 Codex 修复的否定**。

## 2. 并发 ST 六事实逐条裁决（以此刻磁盘）

| # | Codex 断言（取证时点） | 裁决 | 此刻磁盘证据 |
|---|---|---|---|
| 1 | N_CASES=75 | **接受** | `plc/06_PRG_Test.st:18`（VAR CONSTANT，N4-08 一并常量化） |
| 2 | T60-T69 真实断言；T70-T75 恒 TRUE 预留 | **接受(时点)+已前进** | 此刻 **T60-T74 均为真实断言**（T70 ID契约/T71 钳位/T72 违规扫描/T73 检修冻结/T74 FC_TMax 钳位，`06:747-849` 区），仅 **T75 预留**（附注释说明覆盖边界：类型级改动由编译+回归覆盖、PRG_Main 行为项由演示预演验证） |
| 3 | near 平局已改 (time,tier,col)+T60；无新 AB 读回 | **接受(时点)+已前进** | 代码 `04:101-106`；**T60 已于阶段 0+1 验收 AB 实测通过**（75/0 第一轮） |
| 4 | CB/TOB/lex/T63-69 已存在；未 AB 复测 | **接受(时点)+已前进** | `FB_AssignClassTurnover` `04:244-505`、lex 路由 `04:1279-1291`、主链 `05:146-181`；**已于阶段 2 验收 AB 实测通过**（第二轮 75/0，含 T68/T69 黄金向量逐位一致） |
| 5 | ParamGuard 前置、LoadDemo 护栏、T61/62 未复测 | **接受(时点)+已前进** | `05:58-68`(前置)、`05:108-124`(护栏)；**T61/T62 已 AB 实测通过**（第一轮 75/0） |
| 6 | 正确口径="源码已实现/断言未验证/证据 59/0" | **接受(时点)+需刷新** | 该三态分离原则（canonical C11）**保留且正确**；仅数值需刷新为："AB PC 仿真在线读回最新基线=**75/0**（0712 三轮：阶段0+1 / 阶段2 / 阶段3 各一轮，`tools/ab_scripting/runtest_result.txt` + 三份运行日志），范围=核心 ST+黄金向量+T60-74 新断言；**400 件压测/watchdog/在线长跑/实体 AC500 仍无证据**" |

## 3. A/B/C/D 终审

**A 口径 — 接受，零问题。** 亲验 `canonical_assumptions.md:38-45`（四 H 数字分立+回归锚声明）、`:57`(C9 230.4 单操作/h≈115.2 双周期/h)、`:59`(C4b 0.5306+公告号+545.4→278.9+141.4kg+净机械功边界)、`:60`(C11 证据分离)；`README.md:47-49` 三态句精准。四个 H 数字在全部抽查材料中无一混用。

**B N5/sim 方法 — 接受，零问题。** 亲读四处核心：`sim/oracle_gap.py:68-78`（comparable_gap：excess_fail>0→(None,None)）；`sim/adaptive_weights.py:55-87`（select_policy fail-first+INFEASIBLE+min_fail；winner_stability 不伪造 n=2 CI）+`:93-94`（--emit-st fail closed）；`sim/realism.py:62-99`（build_arrivals 策略外一次生成、run_tier3 强制共享否则 raise）；`sim/lifecycle_sim.py:137-160`（drain+flush_time/count+pending_end/inventory_end+final_q 在 flush 后）。数字变更表如实报告负结果（drain 后 δ=0.15 总时反而 +2.69~4.53%、P95 赢家 AWRA→near、6 格 INFEASIBLE）——诚实红线执行到位。

**C 生成器/二进制 — 接受。** SHA256 本机复算：报告 `4709CD…C45D7F`、PPT `633F26…F482F6`，与 Codex 报告**逐字节一致**（大小 3,159,462 / 1,572,082 B，mtime 07-12 04:17）。二进制生成于轨B 阶段 0-3 之前，其内"T60-69 未复测/证据 59/0"表述在生成时点正确——**下次重生时按第 6 节刷新**，当前不构成阻塞（报告草稿本就标 draft）。

**D 文档/历史证据 — 接受。** 抽验 README:49、plc_evidence.csv（三态结构化登记）、历史回执 supersede 标注（N4/N5 回执、D1D2 处理方案、ST 补丁计划头部快照说明均在）。"修复前结论"全部保留且带历史标记，未见历史句回流现役材料。

## 4. 二进制
- 报告 20 页 / PPT 18 张（WPS 渲染+Poppler PNG 逐页抽查无溢出乱码，Codex QA 日志）；OOXML validator 全 PASS；文本抽取无"全占位/near 相反/仅 holistic"过期句。
- SHA 与页数均与 Codex 报告一致，**无伪造迹象**。

## 5. 验证门（明确：以下均 ≠ AB 证据）
| 门 | 结果 | 裁决 |
|---|---|---|
| core_smoke 32/32（含 8.40/8.6232/7.6202/N-A 锁） | PASS | 接受 |
| doc_check / artifact_verify / OOXML / 渲染 QA | PASS | 接受 |
| **AB PC 仿真在线读回（终审时点最新）** | **75/0 × 三轮**（0712 轨B 阶段0+1、阶段2、阶段3；`Compile 0 errors`+`xAllPass=TRUE` 三次） | **新事实**，取代"仍 59/0"；范围=核心 ST+黄金向量（AWRA/CB/TOB 三套逐位锁）+T60-74；**不外推**至 400 件压测/watchdog/长跑/实体机 |

## 6. 剩余阻塞（不命名新批次）
1. ~~T70-T75 恒 TRUE~~ → 已解决至仅 T75 预留（覆盖边界见其注释）；~~AB 复测~~ → 已三轮 75/0。
2. **400 件压测 / watchdog / FB_SceneDetect 最坏耗时实测**（N4-21）——需 AB 在线+用户在场。
3. **场景权重表未接 PLC 运行时闭环**（D-2 遗留；6 高密 online 格 sim 已判 INFEASIBLE，接入前提被削弱，建议报告周降级叙事而非补实现）。
4. **HMI 多客户端隔离无证据**（N5-27~31 诚实边界保留）；**三页在线长跑/画面 17 处/演示预演+重录**——需用户在场（轨B 完工后即可约）。
5. 提交包 manifest/requirements/allowlist——待单独授权（Claude 可先草案）。
6. 二进制下次重生时同步 75/0 三态新值（见第 7 节）。

## 7. 最终行动建议
- **可直接接受**：Codex 全部 A/B/C/D 修复；canonical/README/plc_evidence 的三态分离原则；两份二进制作为当前 draft 基线。
- **需文档小修**（事实性刷新，Claude 本回执后立即执行）：`sim/out/plc_evidence.csv` 与 `canonical C11` 的证据值 59/0→75/0（附三轮读回来源）；`README.md:49` 三态句同步；下次 build_report/build_ppt 重生时吸收。
- **需 ST 补丁**：无（轨B 已完工全绿）。
- **需用户在场 AB**：演示预演（切 SelObjective=lex → 检测器路由 CB/TOB → 手选 4/5 各跑一批）；三页在线长跑；400 件压测/watchdog（可选，决赛前）。

**结论句（按 Codex 要求格式，按最新事实修订）**："Codex 合并修复可作为当前文档/二进制基线；PLC 运行证据已由轨B 三轮 ab_sync 升级为 75/0（核心 ST+三套黄金向量+T60-74），400 件压测/watchdog/在线长跑/实体机证据仍为空，待用户在场场次后再升级。"
