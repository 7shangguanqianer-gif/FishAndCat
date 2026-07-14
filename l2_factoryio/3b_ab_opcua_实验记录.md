# 3b 实验记录：AB 仿真 PLC 试开 OPC UA server（F4，0713 夜）

> 结论先行：**负结果（组件级证据，Codex 独立复核已接受·0713 22:04）**——AB 2.9 的
> **当前 `VirtualAC500_V3` 仿真实例**未加载 OPC UA server runtime 组件
> （CmpOPCUAServer/CmpOPCUAStack），本机本轮无法用 AC500 仿真 PLC 作 OPC UA server；
> Symbol Configuration 只证明符号发布数据已生成，不能替代 server 组件。
> **保守口径（按复核修正）**：只断言"当前实例/本机安装未加载"，不断言"一切 AC500 V3
> 仿真永不可能通过 add-on 获得"。Codex 补查了实际加载的 %TEMP% 实例 cfg 与安装模板
> cfg 组件段一致（复核回执 `_通信/codex_out/0713_F4F5复核.md` F4-1/F4-2）。
> **F5 替代路线已验证编译级可行性**（见 §4；F5 运行期结论后被复核打回重做，见 5_ 文档）。

## 1. 实验步骤（全部成功的部分）

| 步骤 | 结果 |
|---|---|
| 打开 ABB_WH.project（改动前备份 `ABB_WH.project.bak_0713_F4`） | ✓ AC500 V3 / PM5650-2ETH |
| Application 右键 Add object → Symbol Configuration | ✓ 「Support OPC UA features」默认勾选，Optimized Layout |
| Build | ✓ 0 errors, 1 warning（历史正常态） |
| Symbol Configuration 勾选发布 GVL_Data / GVL_Param / GVL_WH | ✓ |
| Online → Login [PLC_AC500_V3]（Simulation 模式）→ 下载 | ✓ Program loaded |
| F5 启动 → RUN | ✓ 仿真 PLC 运行 |

## 2. 失败点与证据链

- `Test-NetConnection localhost:4840` → **False**（OPC UA 标准端口未监听）
- 仿真进程 `VirtualAC500_V3`（本轮 PID 58656）仅监听 **11740**（CODESYS 编程协议）
- **组件级证据**（runtime 目录 `C:\Program Files\ABB\AB2.9\AutomationBuilder\VAC500\V3_2.9.0`）：
  - 目录内 **0 个** OPC 相关文件
  - `CODESYSControl.cfg` 的 `[ComponentManager]` 共 104 个组件，**无
    CmpOPCUAServer/CmpOPCUAStack**（全清单见 cfg；含 CmpIecVarAccess=74、
    SysSocket=32、SysSocketABB=97、CmpVisuServer=70 等）

判定：Symbol Configuration 的 OPC UA 发布配置本身正确且已随下载传输，
但 server 宿主组件在仿真 runtime 中不存在——**实机固件才有 OPC UA server**。

## 3. 对 F5 原计划的影响

- 原 F5 路线「Factory I/O OPC Client DA/UA 直连 AB 仿真」**不可行**（server 侧不存在）。
- CODESYS 兜底同样不可行：本机未装 CODESYS（实测），下载需注册账号（红线不做）。

## 4. F5 替代路线（组件级可行性已验证）

**AC500 ST 内用 Modbus TCP client 库直连 Factory I/O 的 Modbus TCP Server
（127.0.0.1:502）**：

- 仿真 runtime 含 **SysSocket + SysSocketABB** 组件 → IEC 级 Modbus TCP
  client 库（AB Modbus 库 / CAA NBS）可在仿真中运行
- Factory I/O 侧已就绪：work 场景 Modbus Server (Started)，点表 15 in
  /10 coil/1 hreg（io_map.md）
- 叙事加分：AC500（仿真）作为 Modbus 主站直接驱动仓储物理仿真
  ——比 OPC 中转更贴近「AC500 实现智储优控」的比赛主线
- 风险：AB Modbus client 库在 V3 仿真的实际可用性需 F5 实测（库依赖
  的 target 检查可能拦截）；Factory I/O Modbus server 单连接数待确认
  （Python 监控与 AC500 主站并存时）。

## 5. 其他产出

- 项目新增 Symbol Configuration（GVL×3 发布）——对实机部署直接可用，
  保留不回退；`.bak_0713_F4` 为改动前备份。
- 口径：本实验只证明「仿真 runtime 无 OPC UA 组件」，不代表 AC500
  实机不支持（实机固件含 OPC UA server，为已知产品特性）。
