# 5 实验记录：AC500 仿真做 Modbus TCP 主站直驱 Factory I/O（F5，0713 夜）

> 结论先行：**部分结果 / 运行期负结果（证据链清晰）**——AC500 V3 仿真里，
> AC500_ModbusTcp 主站库能**编译、下载、加载、运行**，配置块（ModTcpConfig）
> 自报 `Done + NO_ERROR`，但主站事务块（ModTcpMast）取不到连接资源
> （内部连接指针 pFC22/pFC23 = NULL、ErrorID = `ERR_INTERNAL_UNEXPECTED`），
> **实际 Modbus 事务从不完成**（wReadOk 恒为 0）。
> 与 F4 的 OPC UA 结果同构：库/组件在仿真里"半可用"，真实连接能力疑需实机固件。
> **不签绿；口径仅为"技术预演 + 编译/加载级可行性已证 + 运行期连接待核"。**

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
