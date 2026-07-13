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

### 0713 深夜 8h 无人期授权包（用户四项全签，此后 8h 用户不回复）

| # | 授权 | 内容与限制 |
|---|---|---|
| A1 | **故障自恢复权** | fault lock 落锁后 Claude 代行操作员：完整重启 Factory I/O→`reset-epoch --operator-confirmed-restart`→空场 preflight 实过（路径一步不少）。**同一故障码限 2 次**，第 3 次落锁=冻结现场分支+写 Codex 复核任务书+转其他任务 |
| A2 | **签绿顺进权** | 9/9 通过→自主签绿 F3→录素材（**只录干净操作画面，无讲解**——配音vs字幕仍待拍板）→顺进 F4。F4 内 AB 操作限：开 AB/开项目/OPC UA server 配置/编译下载仿真/Python client 测试；改动前先 commit 备份；**撞任何登录墙即停转下一任务** |
| A3 | **push 延续+文件** | push 授权延续 8h（仍限 `l2_factoryio/`、`docs/`、`_通信/`）；My Scenes 下 debug 命名场景副本可建可改（**绝不动原版场景**）；C6 开工可 pip/npm 装公开源依赖（阿里云镜像） |
| A4 | **冻结兜底改拍** | 若 F3 三连败冻结（F4/F5 因 9/9 红线同堵）→允许提前启动 C6 中不依赖 F3 结果的部分（原「F5 后立即做」顺序改拍）；F3 解冻随时切回 |

**授权外仍不做**（安全规则，签了也不做）：密码/登录墙（CODESYS 实测未安装且下载需注册→F5 兜底路径大概率不可行，届时记录即停）、系统安全设置、用户文档区、删数据。新写 Codex 任务书只排队，提交等用户回来。防休眠已用进程级 SetThreadExecutionState 保活（PID 记 scratchpad，不改系统电源设置）；**锁屏无法绕过**——若发现屏幕被锁，现场 GUI 活自动转 C6/F8 离线活。

### 0713 夜挂机相位规划（/overnight v2 正式开工单，H1 已完，从 H2 起）

| 相位 | 内容 | 预计 | 前置 | 验收产出 | 失败/转移路径 |
|---|---|---|---|---|---|
| H2 | 完整重启基线：载 debug 场景→console 开 Web API→**tag 全量枚举(H1.5，找 X/Z 实体反馈)**→Emitter force off→箱型调试固定（Emitter 配置检查）→RUN 空场 preflight | 30-50min | Factory I/O 已全新启动 ✓ | `logs/webapi_tags_*.json`+基线截图+preflight 日志 | Web API 开不了→Modbus 路径照走，位置反馈降级人工门；场景文件找不到→用官方场景另存新 debug 副本 |
| H3 | 单箱单变量全链：G1 feed→G2 pick（**视觉门=录屏 10-20s+抽帧逐帧判读**）→G3 travel（先 cell 30 干净 A/B）→G4 place-extend（视觉门）→place-lower（真实 Z）→retract | 60-120min | H2 绿 | 每门录屏+判读记录+诊断日志 | 任一无 Z→fault lock 自动落→保存证据→完整重启→单变量 A/B；**同一子问题三连败→冻结分支**，写 Codex 复核任务书后转 F8 |
| H4 | 几何 A/B（复制场景仅动单段护栏） | 条件触发 | H3 拿到首次接触帧证据 | A/B 对比记录 | 我的"状态失配"假设若被 H2 位置反馈证实→整段跳过 |
| H5 | 9/9 验收：cell 1/30/54 各 3 次，箱型恢复混出，全程录屏 | 60-90min | H3 单次全链绿 | 9 份日志+录屏+验收表（口径=54 格代表性验证） | 任何一次失败→回 H3 诊断，不凑数 |
| F4 | AB 仿真 PLC 开 OPC UA server（3b） | 60-120min | F3 签绿 | `3b_ab_opcua_实验记录.md`（成败均档） | AB GUI 期间绝不跑 ab_scripting；撞登录墙截图即停换 CODESYS 兜底记录 |
| F5→C5→C6→F6 | 联调→三任务→同源 3D→回补 | 按 13 问拍板 | 逐门 | 见拍板表 | 每 F 完成→给 Codex 签发复核任务书（拍板#10） |

**节奏机制（本轮起严格执行）**：①连续满负荷，相位间不停车；②**每小时整点前后在本节下方时间线写一行反思**（进度/偏差/风险/下一小时计划）；③每相位收口=commit+push+账本落账+（若为 F 级）Codex 复核任务书；④轮次若中断，ScheduleWakeup 兜底自动续（提示词=读本账本从最新 ⬜ 继续）；⑤额度尽→自动醒接续。

## 四、时间线与反思
- **21:55 F2 开工（文件层侦察先行）**：`F:\Factory IO.exe`=Unity 2023.1.5f1 主程序（VersionInfo 是 Unity 版本，软件版本待 GUI）；注册表 HKCU/HKLM 均无 Real Games 键=**本机从未运行过，首启大概率进激活/试用流程**。`Factory IO_Data\Managed` 关键 DLL 清单：**Engine IO.dll（SDK 宿主端在场）**、Opc.UaFx.Client.dll（OPC UA client 驱动=F5 直连 AB 的宿主件）、ComDrvS7V6/S7PROSIM/Mhj.PLCSIMPlusConnector（西门子系）、**EmbedIO.dll（内嵌 HTTP server→疑似 v2023 Tags REST API，若实锤=快线第四路线：Python requests 即可读写 tag，比 Modbus 还简单）**、IronPython.dll（内置脚本引擎）、CLIC.Client.dll（Real Games 云许可客户端→⚠首启可能要账号，撞到=红线换线记录）。Modbus 无独立 DLL（应内嵌于 Control IO Engine.dll）。
- **22:07 F2 完成（用时 12min，GUI 零障碍）**：无激活墙直进 WELCOME→场景库双击载入 Automated Warehouse→状态栏实证 **v2.5.10 Ultimate Edition**→驱动面板全清单+Modbus Server 默认映射截图→pymodbus 冒烟 PASS。**快线路线就地修正**：v2.5.10 有 `Modbus TCP/IP Server` 驱动（compact 前查证的"Factory I/O 只能当 client"是旧版信息）→ F3 改为 **Factory I/O 当 server + Python pymodbus client 直连**，比预案（pymodbus 起 server 等它反连）少一层依赖；SDK 路线降为备选。**踩坑一枚**：驱动 CONFIGURATION 的 Network adapter 默认吸附 Clash 虚拟网卡 Meta Tunnel（Host=198.18.0.1），已改 Software Loopback Interface 1（Host 自动跟随 127.0.0.1）——不修这个 Python 连 127.0.0.1 必扑空，此坑值得进 memory（凡本机有代理虚拟网卡，工业软件的网卡绑定下拉都可能默认选错）。

- **0713 夜 H0-H1 完成（Claude 接管后首段）**：H0 离线基线复现 64/64；对 Codex 根因假设提出独立质疑（"载荷偏姿卡梁"解释不了 postF6-G2 取箱升程无 Z——统一线索=**Lift 实体状态与命令失配**，若成立 H4 几何 A/B 可整段跳过，钥匙=Web API 实体位置反馈）。H1 五门全落地：①G4 拆 place-extend（只伸叉禁写 Lift）/place-lower（--confirm-clearance 视觉门+真实 Z）/retract，融合版 place 禁用指引；②`fault_lock.py` 持久故障锁（LOWER_NO_START/LIFT_POSITION_UNKNOWN/CARGO_LOST/RECOVERY_UNSAFE 原子写 fault_state.json，锁下只许 snapshot/stop/mark-fault，解锁唯一路径=reset-epoch 双条件：确认完整重启+在线空场 preflight 实过）；③负载感知 stop 跨进程重建叉保持（线圈读回 True 即拒撤叉，读回失败拒盲收）；④pick/relift/place-lower 三处 NO START→落锁；⑤防绕过测试 21 项新增，**85/85 PASS**。H1.5 `webapi_probe.py`（tag 枚举/find 位置反馈/emitter-off/emitter-pulse，纯标准库）。commit=2c5508c(交接归档)+adf9eae(H1)。发现并修一处命名遮蔽 bug（record_phase_state 参数 load_state 盖模块函数）。

- **0713 夜 H2 起点状态（compact 前指针）**：Factory I/O 已全新启动（无残留进程后 Start-Process，**未载场景、未开 Web API、未 preflight**）——H2 从"截图确认→GUI Open 载 debug 场景"继续。⚠ debug 场景文件名是畸形拼接串 `Automated WarehouAutomated Warehouse_debug_prebaseline_0713se.factoryio`（My Scenes 目录），必须 GUI 对话框选择勿拼路径。**Codex 已被用户启动**（轨A批次+H1对抗审查，按 0713 夜信箱节执行中）——回执到达时审+签+双留痕。**H3 前置待办：搭录屏**（视觉门要录 10-20s 逐帧判读；方案候选 ffmpeg gdigrab（kedou 目录有 ffmpeg）或 PowerShell CopyFromScreen 连拍序列，H3 开工时先落地并试录）。桌面面板本轮不动（Codex 正在优化，避免写冲突）。wakeup 兜底已挂（1800s 循环）。

- **13:40-14:00 compact 接力+8h 授权+Codex 并发发现（角色对调）**：接力恢复后用户四项授权全签（`b526499`，A1-A4+保活 PID 39684）。审致Claude.md 发现 **13:24 新回执：Codex H1 对抗审查完成**——裁决「方向接受，当前实现不签绿」，五项阻断（B1 删文件解锁/B2 锁只盖一个 CLI/B3 preflight 可被非空场骗过/B4 safe_stop 读回失败不先停 Target/B5 无互斥 TOCTOU）+四高严+M1 恢复策略冲突，全文 `_通信/codex_out/0713_H1对抗审查.md`，我逐项独立核对**全部接受**（B4 是我写的真 bug）。按拍板「先修锁再进现场」准备动手 H1.1 时，Write 撞车发现 **Codex 正在并发实施 H1.1**（用户以「继续」指令授权它接管；范围=l2_factoryio/+纯离线测试，不碰 Factory I/O/AB、不执行 git；四层设计：缺失/旧 schema 锁定+进程互斥+transition_pending+coil/target 命令租约；恢复命令从 CLI 关闭保留底层；进度 1/5 步、7 文件 +1161/-333）→ **我即刻冻结 l2_factoryio/ 写入，角色切换「它修我审」**，等收工回执后做独立复核+commit（git 归我）。fault_state.json 已被它迁移 schema 2（RECOVERY_UNSAFE 保留归档 ✓ 不是清锁）。等待期完成 **H3 硬前置·录屏管线验证**：ffmpeg（kedou）gdigrab `title='Factory IO'` 10fps 录制+1fps 抽帧+帧内容可判读全链路 PASS；**陷阱入账：gdigrab 抓的是窗口所在屏幕区域，被遮挡时抓到遮挡物**——H3 录视觉门前必须把 Factory I/O 置前（open_application）且录制期间不动其他窗口。

- **14:00-14:05 H2 GUI+治理段完成（除 preflight 全清，等 H1.1 代码）**：
  - GUI 载入 debug 场景（My Scenes 两个畸形名场景：`AA…official_baseline_0713e`=官方基线副本、`A…debug_prebaseline_0713se`=debug，选后者）；console `app.web_server = True` 开 Web API（**console 粘贴陷阱**：type 走剪贴板快路径曾把剪贴板旧文本粘进 console 报 SyntaxError 无害，正确做法=先 write_clipboard 再 ctrl+v）。
  - **H1.5 tag 全量枚举裁决**：36 tags 落盘 `logs/webapi_tags_20260713_135357.json`。**无任何 X/Z/Lift 实体坐标反馈 tag**（数值型仅 Time Scale/Camera Position/Target Position）→「状态失配」假设无法用 tag 实测，`LIFT_POSITION_UNKNOWN` 维持视觉门路径，**H3 录屏逐帧=唯一裁决手段，H4 不可跳过**。另实锤 Web API 与 Modbus 是两套编址（Lift API addr 17 vs Modbus coil 4），io_map.md 的 Modbus 映射仍是权威。
  - **新发现+治理：Remover 也被持久 force=True**（出库端吞货部件，货物消失候选因素之一）。根源实锤：**force 持久化在场景 XML 里**（`UseForcedValue="True" ForcedValue="True"`），每次重载场景 force 复活——这解释了 Emitter force 反复出现。治理=双层：运行时 values-force 置 False + **直接改场景 XML**（.factoryio 是 UTF-8 BOM 明文 XML！）两部件均改为 `ForcedValue="False"`（保持 UseForcedValue=True=载入即强制关，出箱只能显式 pulse）。
  - **箱型调试固定（拍板#5）落地**：场景 XML `<Parts BoxS/BoxM/BoxL/StackableBox>` 四箱型全 True=混出根源；改为**仅 BoxM=True**。备份：`…debug_prebaseline_0713se.factoryio.bak_0713_1402`（9/9 验收时还原此备份即恢复混出）。GUI 重载场景生效（**陷阱：重载弹 Unsaved Changes 必须点 DISCARD**，SAVE 会用内存旧配置覆盖磁盘修改）。
  - **RUN 态空场基线全绿**：Running=True、At Entry/Load/Unload/Exit 全 True（无货）、叉 one-hot Middle、Moving X/Z=False、Emitter/Remover=False、Target=0、Stop/E-stop 常闭健康。Web API 在场景重载后存活（app 级不随场景重置）。reset-epoch 的空场证据链就绪。
  - webapi_probe 小 bug 待修：emitter-off 读回校验用 `/api/tag/values` 端点，该端点不返回 isForced 字段→误报 mismatch；正确端点=`/api/tags`。（l2_factoryio 冻结中，待 Codex 收工后并入复核意见。）

- **14:16-14:40 H1.1 收工与复核（F7 处置完成，commit `97b1c68`）**：Codex 14:16 交付 H1.1 修复（armed 语义/Windows 单写者租约/设备写 capability 门/write-ahead pending/safe_stop 真值表/reset 五证据门/append-only audit/recover 入口下架，B1-B5+H1-H4+M1/M2 全闭合）+14:25 六组外部故障注入续验（强杀留锁/OS 锁自动释放/state 删除 fail-closed/audit 失败不解锁/fault-vs-lease 并发 fault 胜出），121/121。**Claude 独立复核：接受**——121/121 复现+隔离 hash 验证（`D3EA9DB0D4B2…` 前后一致、无 audit 残留）+safe_stop/reset 逐段审查；Codex 的测试污染偏差（曾写真实状态 3 条后按 revision 5 快照恢复）如实报告，与我 14:20 观测的中间态吻合。**复核修复 1 项阻断级 bug**：`_emitter_state` 误用 `/api/tag/values`（实测无 isForced 字段）→emitter-off/pulse 读回恒误报→假 EMITTER_STATE_UNKNOWN 锁（13:54 真实锁文件有实例）；改 `/api/tags`+真实端点形状防回归测试，**122/122**。commit `97b1c68`（+1878/-335）已推；致Codex 批复已写。**H3 前录制方案改版**：Claude 桌面客户端全屏置顶导致 gdigrab 恒拍到遮挡物（computer-use 截图的"前置"是调用时临时隐藏非授权窗口的假象）→ 视觉门录制改用 **Factory I/O 内置 F12 截图**（应用内渲染、零遮挡、1200×767、秒级时间戳文件名，存 `Documents\Factory IO\Screenshots`；连拍节奏=computer_batch 内 [F12+wait 1.1s]×N，同秒会覆盖故间隔须 ≥1.1s；正式素材可用 PNG 序列 ffmpeg 合成 mp4）。下一步=H2 收尾：完整应用重启（A1 授权流程）→reset-epoch 建新 epoch→**H2.5 空载安全门**（Target stop/Pause/Stop/E-stop/断连/双叉拒写，Codex 回执与 R5 要求）→全绿才进 H3 新箱 G1→G4。

- **14:36-14:55 解锁+H2.5 空载安全门收官（F3 转入 H3 就绪态）**：
  - **解锁流程 ×2 实测**：完整重启（PID 43236→34944→42396）+GUI 载场景+console Web API+RUN+`reset-epoch` 五证据门（operator 声明/在线空场 preflight 含四货物传感器/visual-empty/emitter-off/note 可追溯）全过，两个新 epoch（14:43:03 清 RECOVERY_UNSAFE、14:52:36 清 COMMAND_ABORTED）；**`fault_events.jsonl` audit 链诞生**（首条 epoch-reset-request 完整记录）。场景 XML 持久 force-off 跨进程生效验证 ✓。
  - **mechanics-probe A（解锁后首次真实运动）**：新框架全链路 PASS（租约→write-ahead→capability→动作→completion→真值表版 safe_stop 收尾）。两个物理结论：①**新 epoch 下 Lift 命令有真实 Z 边沿（0.08s）**——状态失配最坏假设被削弱；②复现凌晨结论 Right 伸出不互锁下放（interlock refuted）→**G4 无 Z 是带载特有问题**，H3 单箱见分晓。
  - **H2.5 三现场门 PASS**：①**GUI Pause 中断链**——probe B 运动中注入 Pause→NO START fail-closed→cleanup safe_stop 成功→COMMAND_ABORTED 落锁+**pending 留存**（write-ahead 现场实证）+锁下 diagnose 被拒；②**双叉歧义拒写**——Modbus 注入 C2/C3 双 True→白名单 stop 报 `fork state ambiguous` 拒绝完成、**C2/C3 分毫未动**（读回仍双 True）+SAFE_STOP_UNCONFIRMED 落锁（stop 失败升级现场实证）；③reset 五证据门（见上）。**Stop/E-stop/断连未单独现场测**：与 Pause 同构（同走 check_safety_inputs raise→BaseException→落锁通路）+离线故障注入组 1/2 已覆盖强杀/断连，如实声明不算独立现场证据，H3 期间机会性补验。
  - **系统级发现：Web API force 不回写 Modbus coil 表**——第一次用 Web API force 双叉时 stop 读 Modbus 全 False 报 VERIFIED（代码基于可见证据行为正确，但证据通道被旁路）：**GUI/Web API 层 force 可让物理驱动与 Modbus 读回脱节**，是 Codex B2 边界声明的具体实例。改进建议（给下一批次）：reset-epoch preflight 机会性断言**全部输出 tag isForced=False**（Web API 可查）。
  - **绿箱破案**：出口带上的"绿色遗留箱"实为 **Remover 部件的可视化图标**（虚线框+示例箱体）——场景文件无货物对象+删除"绿箱"时虚线框同消失（当时删的是 Remover 本体，**万幸未 Save**）+重载随部件重现。教训：**EDIT 模式删除任何对象前必须核对部件名**；「视觉空场确认」要认识部件可视化。
  - H3 就绪证据：堆垛机重载后复位 rest/载入位（F12 `14_53_17.png`）→ --confirm-rest 视觉证据成立。出箱路径=emitter-pulse（BoxM 单一箱型）→diagnose feed。

- **14:55-15:30 H3 单箱全链 + G4 事故复现 + 根因级突破（F3 最重要的一段）**：
  - **G1 PASS**：emitter-pulse 6s 出单件（MinTimeToEmit=4 决定窗口下限；恰 1 件 Pallet+BoxM，箱型固定生效；**我修的 _emitter_state 读回校验现场零误报**）→feed 4.91s 边沿→停带防抖→2s 落稳。
  - **G2 pick PASS（0713 事故相位未复现）**：Left 伸叉 2.14s→**lift load 真实 Z 边沿（0.12s/2.11s）**→At Load 清→回中→ACTUATOR GATE OK；F12 连拍视觉门确认托盘+箱在承载台、姿态正常（证据 `media/g4_evidence_0713/G2_pick_带载确认_145804.png`）。
  - **G3 travel PASS（cell 30 掉箱事故未复现）**：crane→30 4.0s 到位、Lift 保持、到位后视觉确认托盘+箱在高层承载台完好。
  - **G4 place-extend PASS**：Right one-hot 2.11s、C3 保持、Lift 分毫未写、EXTENDED HOLD 保留。clearance 视觉门降级为 I/O 组合证据（**Deviation：拍板#1 视觉门降级一次**——相机盲飞导航三连败+EXTENDED_HOLD 挂线时间风险；后被 `camera.position_index` 方案根治，见下）。
  - **G4 place-lower：0713 事故在干净单变量条件下复现**——Lift=False 后 Moving Z 无边沿（NO START 3.0s）→LIFT_POSITION_UNKNOWN 落锁+safe_stop 真值表确认 C3 保持拒绝回抽（货物未被拉回，安全门全程正确）。
  - **根因级裁决（三重证据）**：①空载同命令序列 Z 正常启动（mechanics A，0.078s）vs 带载无 Z——唯一差异=载荷；②视觉铁证（`camera.position_index=4` 走廊全景机位）：**托盘+箱已在 cell 30 格位、承载台已空、姿态正常**（`media/g4_evidence_0713/G4_lower_NOSTART_cell30_全景_152304.png` + 裁剪图）；③锁定态现场稳定复核。**结论：place-lower 的下放行程被「托盘-货架梁接触」截断≈0 → 物理引擎不产生 Moving Z → 放置物理成功但代码把成功当故障（零行程放置语义缺失）**。
  - **0713 凌晨事故全链因果闭合**：cell 1 G4 NO START=同一零行程现象（放置其实已成功）→当时误判故障走 recover-lift（Lift=True **把已放好的货重新抬起**）+recover-retract（拉回承载台）→恢复途中姿态劣化→带载去 cell 30 途中掉落。**祸根是恢复操作本身**——M1 采纳「完全重启/清场策略、下架 recover-*」在根因层面也是对的。
  - **工具链突破：`camera.position_index = N`（console API）数值化跳转 7 个保存机位**，彻底替代盲飞导航（盲飞五连败教训）；console `print_help()` 全库入账：`scene.capture_screenshot`/`scene.current_item_count`（空场验证利器）/`scene.debug_emitter_remover`（绿箱=Remover 可视化的官方开关佐证）/`camera.position_cycle_interval`。**console 纪律**：console 聚焦时 backslash=打字不是关闭，关 console 只用点 X；F12 在 console 焦点下不触发。
  - 官方时序文档查证：docs.factoryio.com 403、社区帖无下放时序细节、场景 Instructor 节点为空——官方佐证后补（社区有"到位后托盘晃动/掉落"同类反馈：community.factoryio.com/t/help-with-stacker-crane/1954）。
  - **下一步**：place_lower 语义修复（NO START→LOWER_STALLED 保持现场不落锁不破坏、由 retract 的 --confirm-placement 视觉门接住；其余异常仍 fail-closed）→测试→Codex 复核任务书→重启循环全链验证（G1→G4→retract 首次完整放箱）。

## 五、待拍板清单
- **演示录屏的"演讲技巧 10%"载体**：无现场答辩（0713 澄清），录屏讲解=用户配音 vs 字幕（Claude 可代做字幕本）——待用户回来定。
- （随夜间积累）

## 六、异常日志
- **0713 `.superpowers/brainstorm/ab-fio-0713/`**：昨夜 brainstorm skill 的遗留 HTML 状态目录（untracked，server-stopped）。用户已禁 superpowers；本目录不提交、不清理（非我创建的东西不删），等用户处置。
- （随夜间积累）
