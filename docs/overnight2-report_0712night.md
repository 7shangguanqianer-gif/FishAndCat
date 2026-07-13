# 挂机交接报告 #2（0712 夜 · /overnight 第二轮 · Factory I/O 快线+正线）

> 出发时间：2026-07-12 晚（用户 11 问拍板后离开）。本文件=本轮唯一交接真相源。
> **上一轮账本**=`overnight-report_0712pm.md`（出发单 T0-T6+续航 A/B/C 全绿，勿重做）。

## 〇、一页规格（/ask 终局交付，11 问拍板汇总）

**目标**：把项目往"完美作品"推进——本轮主攻 L2 层（Factory I/O 联动），验收物排序=①3b 实验结论（AB 仿真能否直连 OPC UA，成败均落档）②快线录屏素材③点表/可复现文档④CODESYS 兜底路线。**技术第一优先级，不操心完成时间。**

**范围（做什么）**：
- **快线**：Python 直控 Factory I/O 内置 Automated Warehouse 场景（Engine I/O SDK 优先，Modbus TCP 备选——Factory I/O 是 client，纯 Python 侧用 pymodbus 起 server 即可），跑通"堆垛机连续入库 3 箱"，出录屏素材。
- **正线**：3b 提前实验——AB 仿真 PLC（CODESYS 内核）能否开 OPC UA server 被外部 client 连接读写；通=Factory I/O OPC client 直连 AB；不通=CODESYS Control Win 官方安装器兜底。
- **配套**：IO 点映射表、驱动配置记录、试跑回归脚本、录屏排镜、实验笔记（全部可复现）。
- **双 AI 夜班**：Codex 阻塞已解（见 §二），我审它产出/解它阻塞/签新批次，每步双账本留痕。

**不做什么**：文档线（归 Codex）；三课课纲原件（2_你要操作，用户区）；报告 PPT 重生（用户明令延缓，等他确认 docx 后）；演示脚本 v4（用户未选）；账号/注册/密码类操作（撞到即记录换线）。

**关键决策（11 问拍板，2026-07-12 晚）**：
| # | 决策 | 内容 |
|---|---|---|
| 1 | PLC 路线 | **双线并行**：快线 Python 先出活+正线 AB 直连 OPC UA 同步探（3b 提前），不通落 CODESYS |
| 2 | 代码隔离 | 新产物进 `l2_factoryio/`；全程记录；成功后按 #10 回补 |
| 3 | 墙处置 | **版权/试用期顾虑全部解除，大胆操作**；账号/密码仍是安全红线（撞到记录换线） |
| 4 | 节奏 | **连续满负荷**：干到额度尽→自动醒→继续；1h 反思不停车；任务池尽则按"完美标准清单"从**整个作品**找优化点碾（仍不进文档线） |
| 5 | 素材口径 | 留档 `l2_factoryio/media/`+标注"Python 直控技术预演"；进不进报告等用户 |
| 6 | 验收排序 | 3b 实验结论第一（技术优先） |
| 7 | Codex 增量 | +对抗审查我的 L2 产出（明晨）；**PPT 延缓重生**（用户确认 docx 后再动，防返工） |
| 8 | 双 AI 夜班 | **全自动+双向留痕**：审产出/解阻塞/签新批次；每步写致Codex+本账本；用户文档区终审仍留用户 |
| 9 | 面板深度 | Codex 允许重构+六条设计约束+改前备份 |
| 10 | 回补边界 | **全自动一条龙**：L2 成功→合入主工程+重跑 75/0 复验+commit（自加保险：合前备份副本，复验红自动回滚） |
| 11 | 三课联动 | 3b 若成功：**三课取消/大改等用户重排**——我不动课纲，账本记"三课待重排"即可 |

**验收标准（用户回来可自查）**：
1. 3b 结论落 `l2_factoryio/3b_ab_opcua_实验记录.md`（成/败/证据截图/复现步骤）。
2. 快线若通：`l2_factoryio/media/` 有带口径标注的录屏+`io_map.md` 点表。
3. 每步 commit 可回溯；本账本时间线含每小时反思。
4. Codex 轨A 批次完成或其阻塞被我处置的全记录。
5. 流程改进笔记（用户点名：搜 skills/经验完善自动化流程）落 memory+本账本。

## 一、上下轮衔接与用户反馈
- **用户批评上轮值守太慢（55min/轮只巡检）**→ 本轮节奏改为**连续满负荷干活循环**，值守概念作废；反思在干活间隙写，不为反思停车。教训已进 memory。
- 上轮遗留：quiz 12 题备好未执行（等用户）；报告周 7/20（docx 化已提前给 Codex）；8 月打包事项已入档。

## 二、双 AI 夜班状态
- **Codex 阻塞（已解除）**：core_smoke 31/32——`sim/out/plc_evidence.csv` note 字段逗号未转义（**我 0712 中午的 bug**）。已修（全字段引号包裹+补 visu_interactions_verified 行），本机 core_smoke 复跑 **PASS**。已在致Codex 顶部通知重跑基线门+批次修正（PPT 延缓/新增对抗审查预告）。
- Codex 既定批次（已签发）：1_给你看 三份更新→docx 重生（**PPT 延缓**）→§6/B1/B10/30-seed 注入→面板优化（六约束+备份）。
- 待明晨：Codex 对抗审查我的 L2 产出（任务书我产出落盘后写）。

## 三、任务队列（本轮出发单）
| # | 任务 | 状态 | 备注 |
|---|---|---|---|
| F0 | 修 plc_evidence.csv+core_smoke 复跑+通知 Codex | ✅ | PASS，阻塞解除 |
| F1 | 流程改进搜索（overnight/computer-use agent 经验），落 memory+账本 | ✅ | 业界实践与既有机制高度吻合(原子任务/每步commit/测试门禁/账本)；**增量采纳**：①实验前先 commit 代码(crash 不丢活,F3/F4 执行铁律)②相位粒度 30-60min(1h 反思对齐)③禁触部署/凭据类(本就红线)。来源见账本尾注 |
| F2 | Factory I/O 首启侦察：打开→内置 Automated Warehouse 场景→I/O 点清单→驱动面板截图 | ✅ | **v2.5.10 Ultimate Edition**（状态栏实证）；无激活墙直进；Automated Warehouse 已载入；驱动全清单解锁（含 Modbus TCP/IP **Server**+OPC Client DA/UA）；默认映射拿全（15 In/10 Coil/HReg0=Target Position）；**网卡坑已修**（Meta Tunnel→Loopback）；pymodbus 3.8.6 只读冒烟 **PASS**。产物=`l2_factoryio/{io_map.md, f2_smoke_read.py, img/F2_*.png×3}` |
| F3 | 快线：SDK/Modbus 选型试验→Python"伪 PLC"驱动堆垛机入库 3 箱→录屏+点表 | 🟥 现场阻塞 | Modbus/空载机构/一次干净 G1-G3 已通；G4 无 Z、恢复后运输掉落、F6 后 G2 再次无 Z。禁止续跑/正式素材；总交接=`l2_factoryio/F3_现场故障与Claude接管_20260713.md` |
| F4 | 正线 3b：AB 仿真 PLC 开 OPC UA server 实验（Symbol Configuration 侦察→外部 client 连接读写）→结论落档 | ⬜ | 成败均是决赛材料 |
| F5 | 3b 通→Factory I/O OPC client 直连 AB 仿真联调；不通→CODESYS Control Win 兜底 | ⬜ | |
| F6 | 回补：按 #10 一条龙（备份→合入→75/0 复验→commit；红则回滚待拍板） | ⬜ | 仅在 F4/F5 成功后 |
| F7 | Codex 产出到达→审+回执+签后续 | ⬜ | 全自动+双留痕 |
| F8 | 任务池尽→"完美标准清单"扩展（全作品找优化点，非文档线） | ⬜ | 持续 |

### 0713 用户改拍：Factory I/O 路径 C + 保留自研 3D

- 原 F3“三箱快线→F4 OPC→F5 联调”改为 C0 安全门→C1 契约门→C2 离线编排门→C3 AB 握手门→C4 单任务在线门→C5 三任务在线门→C6 同源 3D 门。
- AB 保持 20×20 业务真相源；Python 仅做 400→54 显式代表映射、设备适配和 safe-stop；Factory I/O 不称 400 格物理孪生。
- 总体设计=`5a5c18c`，C0–C2 实施计划=`c9e9318`；F3 安全动作基线=`3abec42`，任务契约/映射=`dd57e0d`，JSONL 事件=`c5246a2`，三任务离线编排=`40bc068`。
- C0–C2 离线结果：`test_f3_stacker_control.py + test_task_contract.py + test_event_log.py + test_task_orchestrator.py` 共 **23/23 PASS**。覆盖 INBOUND/OUTBOUND/DUAL、safe-stop、safe-stop 二次失败、`request_seq` 冲突、进程重启幂等和中断任务 `RECOVERY_REQUIRED`。
- **未签绿项**：F3 现场碰撞/散落近景验收尚未关闭，AB OPC UA/任务队列尚未施工，自研 3D 尚未改读统一事件；禁止越门录正式素材或宣称完整控制闭环。
- 下一步先完成 F3 现场碰撞门，再进入 AB OPC UA，禁止越门录正式素材。

### 0713 12:12 Codex F3 现场终止与 Claude 接管回执

- **安全状态**：Factory I/O 与 Python 控制进程均已关闭；不保留可续跑货物或在线写入任务。HEAD=`f0bd29f`，工作树含大量用户/Claude 既有改动，本交接未提交、未推送。
- **干净链证据**：完整重启并修正 Emitter 强制值后，单箱 G1/G2/G3 到 cell 1 分别通过（`114630/114708/114747`）；G4 Right 到位后写 Lift=False 无 `Moving Z`，见 `l2_factoryio/logs/F3_diagnose_20260713_114828.log:5-10`。
- **恢复路线被现场否定**：`recover-lift→recover-retract` 只把机构撤回；随后把恢复货物运到 cell 30，I/O 报移动完成但用户画面确认掉落（`115743.log:5-14` + `img/F3_recovery_travel_drop_cell30_20260713_1158.jpg`）。当前代码已加入 `RECOVERY_UNSAFE`，但跨进程持久锁仍未实现。
- **F6 能力边界修正**：F6 后新 G1 通过，新 G2 在 Left 到位后 Lift 无 Z（`120146.log:6-11`）。故 F6 只清货，不等价于机构/输出复位；任一无 Z、恢复、掉落后必须完整退出并重启 Factory I/O。
- **Right 互锁排除**：空载 cell 1 探针在 `Right=True` 时下降 0.094 s 启动、约 1.98 s 落稳（`F3_mechanics_A_20260713_065413.log:9-20`）。优先根因转为载荷偏姿、与叉具/货架梁/周边几何接触或物理求解受约束。
- **几何复核**：官方 baseline 与 debug 均 45 个 Proxy；Rack/Stacker/Conveyors Position/Rotation 相同，只有 4 个 SafeguardL 四元数末位序列化差异。暂无证据是整套设备被移错；防护网只能在副本中按首次接触证据做单段 A/B，禁止整圈删除。
- **下一路线**：先离线补 `place-extend→视觉门→place-lower→支撑确认→retract`、跨进程 fault/reset epoch、负载感知 stop 与实体 Lift unknown 门；再完整应用重启、Emitter 单箱、斜俯视近景，target 30 仅作干净单变量 A/B。9/9 前 F3 保持红，不进 F4/F5/F6。
- **完整交接**：`l2_factoryio/F3_现场故障与Claude接管_20260713.md`；Claude 提示词=`l2_factoryio/ClaudeCode接管提示词_F3_20260713.md`；通信回执=`_通信/codex_out/0713_F3_Codex终止交接回执.md`。
- **用户约束刷新**：禁止所有 superpowers 系列 skills；旧实施计划开头的 REQUIRED superpowers 语句已废止。

### 0713 夜 Claude 接管 F3 · 5 轮 13 问拍板（本节=接管后最高拍板真相）

| # | 决策 | 内容 |
|---|---|---|
| 1 | 视觉门 | **全自主+每门录 10-20s 诊断视频逐帧回看**（单帧自判升级）；判断存档全留 |
| 2 | Codex 分工 | 先轨A文档批次（0713 回执自述未实施）→完成后回头对抗审查 Claude 的 H1；启动提示词已交用户 |
| 3 | push | **本夜批量授权**：仅限 `l2_factoryio/`、`docs/`（账本）、`_通信/` 三路径；用户文档线绝不入库 |
| 4 | Web API | **深挖优先级拉满**：H2 现场枚举全量 tags 找 X/Z 实体反馈；H1 预留有/无反馈双路径 |
| 5 | 箱型 | 调试阶段固定单一箱型（副本配置，记录可回滚）；9/9 正式验收恢复混出 |
| 6 | F3 绿后 | **顺进 F4**（AB OPC UA 3b 实验）；AB GUI 开着绝不跑 ab_scripting 照旧 |
| 7 | AB 许可 | 排程按"8/2 后无 AB"规划：F4/F5/终验录屏/演示录像全部 7 月内完成归档 |
| 8 | C6 自研 3D | F5 后立即做（同源 JSONL 双视图） |
| 9 | F6 回补 | C5 三任务联调绿后触发（不等 C6）；红则回滚待拍板 |
| 10 | **新常态机制** | **每完成一个 F 任务→Claude 即刻给 Codex 签发独立客观复核任务书**（交叉纠错常态化） |
| 11 | 报告周 | 本轮不进入报告线；只记录思路供后续书写（检查报告大纲与草稿映射是否跟上 L2） |
| 12 | **比赛形式澄清** | **初赛提交决赛全部任务、无现场答辩、一切通过提交文件夹呈现**（类似 ABB 语音任务）→ 素材终态=提交包内的视频/文档，不是现场表演脚本；待核实比赛要求原文后修正素材规格 |
| 13 | L2 科普 docx | 要，但等 L2 全线完工后一次性写（照 0712 画面科普模式） |

其余沿用：三连败冻结分支纪律、9/9 验收定义、口径红线（54 格代表性验证/不称物理孪生）、禁 superpowers skills、禁碰用户文档线/canonical。

## 四、时间线与反思
- **21:55 F2 开工（文件层侦察先行）**：`F:\Factory IO.exe`=Unity 2023.1.5f1 主程序（VersionInfo 是 Unity 版本，软件版本待 GUI）；注册表 HKCU/HKLM 均无 Real Games 键=**本机从未运行过，首启大概率进激活/试用流程**。`Factory IO_Data\Managed` 关键 DLL 清单：**Engine IO.dll（SDK 宿主端在场）**、Opc.UaFx.Client.dll（OPC UA client 驱动=F5 直连 AB 的宿主件）、ComDrvS7V6/S7PROSIM/Mhj.PLCSIMPlusConnector（西门子系）、**EmbedIO.dll（内嵌 HTTP server→疑似 v2023 Tags REST API，若实锤=快线第四路线：Python requests 即可读写 tag，比 Modbus 还简单）**、IronPython.dll（内置脚本引擎）、CLIC.Client.dll（Real Games 云许可客户端→⚠首启可能要账号，撞到=红线换线记录）。Modbus 无独立 DLL（应内嵌于 Control IO Engine.dll）。
- **22:07 F2 完成（用时 12min，GUI 零障碍）**：无激活墙直进 WELCOME→场景库双击载入 Automated Warehouse→状态栏实证 **v2.5.10 Ultimate Edition**→驱动面板全清单+Modbus Server 默认映射截图→pymodbus 冒烟 PASS。**快线路线就地修正**：v2.5.10 有 `Modbus TCP/IP Server` 驱动（compact 前查证的"Factory I/O 只能当 client"是旧版信息）→ F3 改为 **Factory I/O 当 server + Python pymodbus client 直连**，比预案（pymodbus 起 server 等它反连）少一层依赖；SDK 路线降为备选。**踩坑一枚**：驱动 CONFIGURATION 的 Network adapter 默认吸附 Clash 虚拟网卡 Meta Tunnel（Host=198.18.0.1），已改 Software Loopback Interface 1（Host 自动跟随 127.0.0.1）——不修这个 Python 连 127.0.0.1 必扑空，此坑值得进 memory（凡本机有代理虚拟网卡，工业软件的网卡绑定下拉都可能默认选错）。

## 五、待拍板清单
- （随夜间积累）

## 六、异常日志
- （随夜间积累）
