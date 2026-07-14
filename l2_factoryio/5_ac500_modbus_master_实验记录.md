# 5 实验记录：AC500 仿真做 Modbus TCP 主站直驱 Factory I/O（F5，0713 夜）

> **⚠️ 复核裁决（Codex 0713 22:04，Claude 23:05 受理）：本文件的"首选仿真能力边界"
> 结论被打回，不再成立。** 详见文末【附录 A·复核裁决与重做】。有效结论收窄为：
> **编译/加载级可行性已证；运行期事务未通；未排除两个用法缺陷**——
> ①设备树未配置 `Protocols (Client Protocols) → Modbus TCP Client`（ABB 3ADR010980
> §5.1 要求，本轮从未做）；②AbbETrig3 边沿 FB 调用节奏违反官方语义。
> F5 状态=**重做待执行（用户 0713 夜已授权"现在就重做"）**。以下正文为原始记录，
> 其中被裁决推翻/修正的表述以附录 A 为准。
>
> （原结论，已被打回）~~部分结果 / 运行期负结果——主站事务从不完成，与 F4 同构，
> 疑需实机固件。~~ 不签绿口径维持：技术预演 + 编译/加载级可行性已证 + 运行期待核。

## 1. 目标与路线
- 路线来源：`3b_ab_opcua_实验记录.md` §4——OPC UA 直连不可行后的替代路线：
  AC500（仿真）ST 内用 Modbus TCP client 库直连 Factory I/O 的
  Modbus TCP Server（127.0.0.1:502），AC500 作为主站驱动仓储物理仿真。
- 载体：新增 POU **PRG_FIO_Bridge**（ABB_WH.project），最小闭环：
  FC2 读离散输入 addr1 = At Load（input1，低有效）+ FC5 写单线圈 coil7
  = Start light（HMI 指示灯，无物理副作用）作心跳。
- 被 PLC_PRG 每周期调用（`PRG_Main(); PRG_Test(); PRG_FIO_Bridge();`）。

## 2. 成功的部分（编译 / 加载 / 运行级）
| 步骤 | 结果 |
|---|---|
| 写 PRG_FIO_Bridge（ModTcpConfig fbCfg + ModTcpMast fbRead/fbWrite） | ✓ |
| 修正触发字段 `Enable→Execute`（ModTcpMast/ModTcpConfig 均 EXTENDS AbbETrig3） | ✓ |
| 修正 `Eth := 'ETH1'`（STRING 报错）→ `Eth := 0`（BYTE 接口索引） | ✓ |
| **Build 0 errors**；Messages 大量 `Generate code for MODTCPMAST / MODTCPCONFIG / MODBUSTCPCLIENT...` | ✓ 库已成功编入应用 |
| Login（Simulation）+ 全下载（Login with download）+ Start → RUN | ✓ |
| fbCfg（ModTcpConfig）：`xCfgDone=TRUE`、`ErrorID=NO_ERROR`、`Port=502` | ✓ 配置块自报成功 |
| wCycle 持续递增（程序正常循环，652+ 周期实测） | ✓ |

## 3. 失败点与证据链（运行期）
在线监控 fbRead（ModTcpMast）内部：
- **`ErrorID = ERR_INTERNAL_UNEXPECTED`**（bErr 瞬时 FALSE，但 ErrorID 已置）
- **连接资源指针 `pFC22 / pFC23 = 16#00000000`（NULL）**、`pBool / pWord = NULL`
- 连接级字段全 0：`dwIPAddress=0`、`wPort=0`、`byUnitID=0`、`byFunctionCode=0`
- 读专属字段却已正确填充：`wAddressRead=1`、`wNumRead=1`、`pbyBufferRead` 非空指向 awIn
- 接口输入全部正确：`IPAdr=2130706433`(=127.0.0.1)、`Fct=2`、`Addr=1`、`UnitID=1`、`Nb=1`、`Data=ADR(awIn)`
- 结果：`fbRead.Done` 从不为 TRUE、**`wReadOk` 恒为 0**（500+/652 周期无一次完成）

判定：**配置块自报 Done/NO_ERROR，但从未为主站产出可用连接资源**
（pFC22/pFC23 恒 NULL），主站遂 `ERR_INTERNAL_UNEXPECTED`、无事务。

## 4. 已排除 / 已尝试
- **端口通道干净**：502 处于 LISTEN，无任何已建立连接、无 Python client 竞争（netstat 实测）。Factory I/O 侧 `Modbus TCP/IP Server (Started)`、work_0713 场景加载。
- **触发字段**：Enable→Execute 修完（编译期确认 ModTcpMast/ModTcpConfig 均 AbbETrig3）。
- **配置块调用频率**：原代码 `IF NOT xCfgDone` 只调用一次 → 已改为**每扫描周期调用** `fbCfg(Execute:=TRUE)`（连接管理器须每周期运行）。改后 xCfgDone 仍 TRUE、但 pFC22/pFC23 仍 NULL、wReadOk 仍 0 —— **此改动未解决**。

## 5. 两个未定根因（需库示例/手册或实机区分）
1. **仿真运行期不支持出站 Modbus TCP 主站连接**（首选假设，与 F4 同构）：
   ModTcpConfig 在 VirtualAC500_V3 里对连接资源的内部注册是 no-op / 静默失败，
   留 pFC 指针 NULL；SysSocketABB 组件存在 ≠ 出站 client 事务在仿真可用。
   若成立，**任何代码改动都无效，需真实 AC500 固件/硬件**。
2. **桥接的异步 FB 调用节奏**（次要）：fbRead/fbWrite 经 xToggle 每隔一扫描才被调用，
   且 Execute 边沿只在首扫描产生一次；异步主站 FB 通常须**每扫描调用**直至 Done/Error。
   但此因解释不了 pFC 恒 NULL（那是配置-主站链路问题，非节奏问题），故权重低。
   区分需 ABB `AC500_ModbusTcp` 官方示例的 config↔mast 链接约定（Eth 索引 / 连接句柄）。

## 6. 结论口径（严格）
- 已证：主站库在 V3 仿真 **target 兼容**（编译 + codegen + 下载 + 加载 + FB 执行全通过）——这**杀死了 3b §4 的最大开放风险**（"target 检查可能拦截库"）。
- 未证：**实际 Modbus 主站事务在仿真运行期未完成**（连接资源建不出）。
- 因此 F5 **不签绿**。素材只可写"Python 直控技术预演 / 54 格代表性物理 I/O 验证 /
  AC500 主站桥接编译加载级可行性已证"，**禁称** AC500 闭环驱动、400 格孪生。

## 7. 待用户在场的下一步（不在无人值守 GUI 里盲试）
1. 查 ABB `AC500_ModbusTcp` 库自带示例工程的 ModTcpConfig↔ModTcpMast 链接写法
   （Eth 索引到底取什么、是否需共享连接句柄 / Slot / ADR 传引用）。
2. 若示例确认仿真可行 → 按其约定改 PRG_FIO_Bridge，masts 改每扫描调用，重测 wReadOk。
3. 若示例/文档表明须实机 → 归档为"实机部署直接可用"，与 F4 并列作"仿真边界"负结果。

## 8. 产出与备份
- 项目新增/改动：POU `PRG_FIO_Bridge`（编译 0 errors，已保存）、PLC_PRG 增一行调用。
- 备份：`ABB_WH.project.bak_0713_F5`（本轮 F5 改动前）。
- 场景侧无改动；Factory I/O work_0713 Modbus server 保持 Started。
- 口径同 3b：本实验证"仿真运行期主站连接未建立"，不代表 AC500 实机不支持
  （实机固件含完整 Modbus TCP 主站，为已知产品特性）。

---

## 附录 A · 复核裁决与重做（0713 22:04 Codex 复核 → 23:05 Claude 受理）

**裁决**（全文见 `_通信/codex_out/0713_F4F5复核.md`）：部分接受/打回——
"首选=仿真不支持出站 Modbus 主站连接"证据不足，不能签成能力边界。

**三条打回依据（Claude 复核后全部认账）**：
1. **设备树协议对象缺失（最可能主因）**：ABB 官方应用例 3ADR010980 §5.1——客户端
   需在 `Protocols (Client Protocols)` 下添加 **Modbus TCP Client**，`ModTcpMast`
   才能读写。本轮只写了 POU+引库，从未配置/核查设备树；`pFC22/pFC23=NULL +
   连接级字段全 0` 的最优解释=本地连接/协议栈资源未注册，而非仿真 stub。
2. **AbbETrig3 节奏违规**：官方语义=Execute 上升沿启动单次操作→**每周期持续调用直到
   Done/Error**→`Execute:=FALSE` 至少一周期→再上升沿。本轮"每扫描 TRUE"不产生新边沿
   （§4 的"修复尝试"因此无效），masts 经 xToggle 隔扫描调用直接违规；
   `BUSY/ERR_INTERNAL_IO_RETRY` 都是 "call again" 语义。
3. **错误码分类**：远端不通应报 `ERR_FAILED_CONNECT/ERR_TIMEOUT/ERR_CONNECTION_CLOSED`
   或 Modbus exception；实测 `ERR_INTERNAL_UNEXPECTED`+内部指针 NULL 指向本地资源未建。

**正文修正**：§2 "Eth:=0（BYTE 接口索引）✓" 改判——官方文档明示 `Eth` 为
**兼容性字段、被库忽略**（"input is ignored, existing for compatibility reasons
only"），取值不是决定因素，不应表述为"正确接口索引"。§5 两个"未定根因"作废，
以本附录三条依据取代。

**重做要点（Codex 5 条，用户已授权立即执行）**：
1. 先核查/添加设备树 `Protocols (Client Protocols) → Modbus TCP Client`，
   截图记录对象名/IP/Port/Unit/Active；
2. `ModTcpConfig` 按 AbbETrig3 语义：上升沿一次→等 Done/Error→拉低 ≥1 周期；
3. 事务块**每周期调用**直到 Done/Error；优先试 `ModTcpMast2`（3ADR010980：
   使用本地连接参数，不依赖 general config）；
4. 一次一个请求：FC2 读通再试 FC5；`ParallelProcessing:=FALSE`；完成拉低再触发；
5. **新判据**：配置完整+节奏正确后若报 `FAILED_CONNECT/TIMEOUT/CONNECTION_CLOSED`
   才讨论仿真 socket 边界；仍 `pFC=NULL/ERR_INTERNAL_UNEXPECTED` 则继续查
   Client Protocols 与库内部注册。

**连锁修正**：C4/C5/F6 在线门线"待真机"判决收回，改为"待 F5 重做结果"。
重做记录见【附录 B】。

外部出处：ABB 3ADR010980《AC500 V3 - Modbus TCP》、ABB Help ModTcpMast/ModTcpConfig
（URL 见复核回执文末）。

---

## 附录 B · 重做执行记录（0713 23:10-23:35，Codex 5 要点全部执行完毕）

> **结论先行：5 条重做要点全部落实后，症状分毫未变**——`pFC22/pFC23` 仍 NULL、
> 仍瞬时 `ERR_INTERNAL_UNEXPECTED_STATE`（每 2 扫描周期一错）、`wReadOk` 恒 0。
> 新增**端口差分实验**：Port=5020（无监听）与 Port=502（Factory I/O 在听）行为
> **完全一致**→ 协议栈从未发起任何 TCP 尝试（同步失败于触发周期）。
> **本轮不自签边界结论**（上次教训），全部证据回交 Codex 二审裁决。

### B1 要点执行情况（对照 Codex 5 条）

| # | 要点 | 执行 | 证据 |
|---|---|---|---|
| 1 | 设备树 `Protocols (Client Protocols)` 核查/添加 | ✅ **核实原本为空**（Codex 假设命中）→ 已添加 `Modbus_TCP_IP_Client`（ABB AG, 3.9.0.0, Bus cycle task=Task） | `media/f5_redo_0713/01`(空,改动前)/`02`(已加)/`03`(对象信息页).png |
| 2 | fbCfg 按 AbbETrig3 语义 | ✅ 更彻底：**删除 ModTcpConfig 依赖**，改用 ModTcpMast2 本地参数 | 代码（重做版 PRG_FIO_Bridge） |
| 3 | 事务块每周期调用+优先 ModTcpMast2 | ✅ 全新 6 态状态机：触发(上升沿)→每周期调用等 Done/Error→拉低≥1 周期→再触发；fbRead/fbWrite 均 ModTcpMast2（RespTimeout=2000/KeepAlive=1000/BIG/Port=502/ConnectTimeout=默认） | `04_重做代码_Build0错误.png`；本地库文档接口核对（AB_LibDoc modtcpmast2.html） |
| 4 | 一次一请求 | ✅ ParallelProcessing=FALSE；FC2 首通(xReadProven)后才启用 FC5；读写不并发 | 代码 |
| 5 | 新判据观测 | ✅ 见 B2 | `05`/`06`/`07`.png |

### B2 观测结果（Build 0 errors → 全下载 → RUN，仿真重启后满 2h 窗口）

- **Port=502（Factory I/O Modbus Server 在监听，无竞争连接）**：
  `fbRead.Error` 每次触发即出，`wReadErr` 以 ≈200 错/秒攀升（wCycle:wReadErr≈2:1
  =触发当周期同步失败）；`wReadOk=0`；`eReadErr=ERR_INTERNAL_UNEXPECTED_STATE`；
  瞬时采样 `fbRead.ErrorID` 在复位期显示 NO_ERROR（AbbETrig3 输出复位行为，正常）。
- **端口差分：fbRead Port=5020（无任何监听）**：行为**完全一致**——仍瞬时
  INTERNAL 错、wReadErr 同速攀升。**若栈真在发起 TCP，此处必须出现
  ERR_FAILED_CONNECT/ERR_TIMEOUT/ERR_CONNECTION_CLOSED 之一**（官方错误码表）；
  未出现 → 失败发生在任何网络动作之前。
- **协议对象已添加后的内部状态**（决定性）：`pFC22=16#00000000`、
  `pFC23=16#00000000`、`dwIPAddress=0`、`wPort=0`、`byUnitID=0`、
  `byFunctionCode=0`——与添加协议对象**之前完全相同**。
- 环境核对：`netstat` 502 LISTEN 无既有连接；仿真为新拉起实例（2h 窗口满额）；
  Build 0 errors；下载/RUN 正常；wCycle 正常攀升（程序在跑）。

### B3 移交 Codex 二审的问题

1. 五要点全部落实 + 端口差分证明"无任何 TCP 尝试" + pFC 恒 NULL——
   还有没有**未试过的配置面**？（候选：ETH1 NetConfig 的 IP 设置在仿真里的取值、
   协议对象的 Bus cycle task 绑定、是否需要 CM 通信模块级对象、
   虚拟运行时是否根本不加载 coupler 级协议栈服务。）
2. 若裁决为"虚拟运行时不服务 Modbus TCP Client 协议栈"，保守口径怎么写
   （同 F4 格式：只断言当前实例/本机安装，不断言产品线）。
3. `ERR_INTERNAL_UNEXPECTED_STATE` 在库内部的确切触发点（若可从库文档/例程判断），
   以坐实"同步失败于栈资源缺失"的机理解释。

### B4 工程状态

- 项目已保存：设备树含 `Modbus_TCP_IP_Client`（保留——按官方文档本就该有，
  对实机部署直接可用）；`PRG_FIO_Bridge` = 重做版（0 errors）。
- 全过程 7 张证据图：`l2_factoryio/media/f5_redo_0713/01-07*.png`。
- F5 状态：**重做完成，边界裁决权移交 Codex 二审**；C4/C5/F6 判决继续挂起待二审。
