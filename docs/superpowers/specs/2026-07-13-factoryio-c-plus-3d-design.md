# Factory I/O 路径 C + 自研 3D 优化设计

**日期：** 2026-07-13  
**状态：** 用户已拍板“C + 保留自研 3D并优化”  
**主张边界：** Factory I/O 是 54 格代表性执行层；AB 与自研 3D 承担严格 20×20 / 400 格业务真相。任何产物不得把 54 格称为 400 格物理孪生。

## 1. 目标与非目标

### 目标

建立一条可复现的控制链：AB 根据货物属性、约束和策略生成 20×20 逻辑任务，经过显式 400→54 代表性映射下发给 Factory I/O，设备执行 INBOUND、OUTBOUND、DUAL 三类任务并回传 Running、Done、Fault；自研 3D 使用同一 Task ID 和事件日志重放完整 20×20 业务过程。

最终让三个画面分别回答：

- AB：为什么选择这个逻辑库位；
- 自研 3D：完整 400 格仓库中发生了什么；
- Factory I/O：代表工位能否按真实 I/O 时序安全执行并反馈。

### 非目标

- 不在 Factory I/O v2.5.10 中伪造严格 20×20 物理堆垛机；
- 不把 Python 桥接器称为 AC500 或 PLC 控制器；
- 不用 3D 动画证明 H、吞吐、能耗或策略优势，这些仍由 canonical、sim 和测试锁证明；
- 不在碰撞闭环未通过前录制正式演示；
- 不为了画面丰富引入第二套货物、库存或 KPI 真相源。

## 2. 相对原 F0–F8 节奏的变化

原计划把 F3 定义为 Python 连续入库三箱的“快线”，随后才做 F4 AB OPC UA 和 F5 联调。路径 C 会引入任务队列、三种作业、重试和事件日志；如果仍按原节奏，单箱动作、AB 任务和 3D 回放会形成三套互不约束的状态。

新节奏改为“安全门 → 契约门 → 离线编排门 → AB 握手门 → 单任务在线门 → 三任务在线门 → 同源 3D 门”：

1. **C0 安全门**：完成 F3 碰撞根因、落稳、safe-stop 和近景验收；
2. **C1 契约门**：冻结 Task、Status、Fault、Mapping 和 Event 五类数据；
3. **C2 离线编排门**：用 FakeAdapter 验证 INBOUND、OUTBOUND、DUAL、幂等和故障状态机；
4. **C3 AB 握手门**：AB 拥有业务队列与调度，Python 只接收一个已锁存活动任务；
5. **C4 单任务在线门**：先让一条 INBOUND 完成 Decision→Ack→Running→Done；
6. **C5 三任务在线门**：依次验收 INBOUND、OUTBOUND、DUAL 和一次故障恢复；
7. **C6 同源 3D 门**：自研 3D 改读同一事件日志，显示同一 Task ID、逻辑格、代表格和状态；
8. **C7 证据门**：执行固定脚本、多轮近景验收、录屏和口径审计。

因此不再把“三箱快线录屏”作为 F3 终点。F3 只负责证明安全设备原语；正式素材要等到 C4 以后。

## 3. 总体架构与所有权

```text
货物属性/约束/策略
        │
        ▼
AB 20×20 业务层
  - Task Queue / Dispatcher
  - logical target (col 0..19, tier 0..19)
  - strategy/reason/KPI snapshot
        │ OPC UA sequence handshake
        ▼
Python L2 Bridge
  - task snapshot validation
  - 400→54 representative mapping verification
  - safety sub-state / timeout / event log
        │ Modbus TCP or Factory I/O OPC client
        ▼
Factory I/O 54格设备层
  - conveyor / fork / lift / crane
  - Moving / limit / drop / timeout feedback

同一 Event Log ───────────────► 自研 20×20 3D 回放
```

所有权规则：

- **AB 是业务真相源**：货物、任务类型、先后顺序、逻辑库位和策略解释由 AB 产生；
- **Python 是设备适配器**：不得自行改选逻辑库位或改任务顺序；它可以拒绝非法任务并安全停机；
- **Factory I/O 是物理 I/O 证据源**：只报告代表设备动作与传感器状态；
- **自研 3D 是解释性回放**：只消费事件，不反向控制 AB 或 Factory I/O。

## 4. 统一任务契约

### 任务类型

- `INBOUND`：I/O 点取入库货物 → 存入逻辑目标对应代表格 → 返回 rest；
- `OUTBOUND`：从逻辑源对应代表格取货 → 返回 I/O 点卸载 → 返回 rest；
- `DUAL`：从 I/O 点携入库货物 → 存入目标格 → 前往出库源格取货 → 返回 I/O 点卸载；

### 状态

`QUEUED → DISPATCHED → ACKED → RUNNING → DONE`。异常进入 `FAULT`；仅在尚未取得货物且设备已回到可证明安全的 rest/middle 状态时允许一次自动重试。取得货物后的异常不得盲目重放，由操作员 Reset 后重新建单。

### 必需字段

- `task_id`：单调递增 `UDINT`，贯穿 AB、Python、Factory I/O 证据和自研 3D；
- `operation`：1=INBOUND、2=OUTBOUND、3=DUAL；
- `goods_id`：业务货物 ID；
- `logical_source` / `logical_target`：0..399，按 `tier * 20 + col`；
- `physical_source` / `physical_target`：1..54，按 `tier * 9 + col + 1`；
- `strategy_id` 与 `reason_code`：保留 AB 决策解释；
- `request_seq` / `ack_seq`：采用序号握手，避免 PLC 扫描周期脉冲丢失；
- `status`、`phase`、`progress`、`fault_code`、`actual_cell`；
- `mapping_version`：固定为 `grid20x20_to_grid9x6_v1`。

### 400→54 代表性映射

逻辑坐标归一化量化到 9×6：

```text
physical_col  = round(logical_col  * 8 / 19)
physical_tier = round(logical_tier * 5 / 19)
physical_cell = physical_tier * 9 + physical_col + 1
```

映射保留相对远近和高低，不宣称容量、占用或碰撞等价。多个逻辑格可能映射到同一代表格；在线演示队列必须避免同时占用冲突，若冲突则任务在 AB 侧保持等待并显示 `REPRESENTATIVE_CELL_BUSY`，不得由 Python 偷换格位。

## 5. AB 路径 C 组件

新增组件按职责拆分：

- `ST_L2Task`：固定任务快照；
- `E_L2TaskStatus` / `E_L2Fault`：状态和故障枚举；
- `FB_L2TaskQueue`：固定容量环形队列，拒绝溢出并保持 FIFO；
- `FB_L2Dispatcher`：只在无活动任务、设备 Ready 且代表格无冲突时派发；
- `FB_L2Handshake`：锁存活动任务，管理 request/ack/status 序号；
- `GVL_L2`：仅暴露 OPC UA 所需标量与 HMI 镜像，避免直接导出复杂数组；
- HMI：队列深度、活动 Task ID、业务格→代表格、阶段、进度、故障、Reset，不复制现有 400 格热力图。

路径 C 不改变 AWRA-LS、CB、TOB 的选位函数。第一版任务由已分配货物生成，避免调度功能反向污染算法基线。

## 6. Python 设备适配与错误处理

现有 `f3_stacker_control.py` 保留为低层设备原语，拆出的上层模块不得直接操作 Modbus 地址：

- `fio_adapter.py`：封装 feed、pick、store、retrieve、unload、safe_stop；
- `task_contract.py`：类型、验证、映射和 JSON 序列化；
- `task_orchestrator.py`：单活动任务状态机和事件输出；
- `opc_bridge.py`：只负责 AB OPC UA 节点读写，不包含动作序列；
- `event_log.py`：追加写 JSONL，事件至少含时间、Task ID、状态、阶段、逻辑格、代表格和故障。

故障优先级为：`ESTOP/STOP → DROPPED_LOAD → CARGO_LOST → COLLISION_OR_STALL → TIMEOUT → IO_ERROR → CONTRACT_ERROR`。任何故障先执行 safe-stop，再写 `FAULT`；safe-stop 本身失败必须保留原故障和停机失败两条事件。

## 7. 自研 3D 优化

保留 PyVista/VTK 的严格 20×20 画面和现有视觉风格，不重做渲染器。优化集中在数据与证据一致性：

1. 把 `build_events()` 的硬编码演示源抽象为 `EventSource`；
2. 支持读取统一 JSONL，同时保留现有 deterministic fallback 供离线回归；
3. 画面固定显示 Task ID、Operation、Strategy、logical cell 和 mapped physical cell；
4. 增加小型“20×20 → 9×6 代表映射”示意，不把 54 格叠成 400 格；
5. 故障字幕来自事件 `fault_code`，不再由动画时间轴自行制造不同事实；
6. 输出分为 30 秒答辩版和完整证据版，两者使用同一事件文件与渲染参数清单。

## 8. 测试与验收

### 离线门禁

- task contract：边界、序列化、映射角点与单调性；
- queue/dispatcher：FIFO、满队列、重复 Task ID、代表格冲突；
- orchestrator：三类任务的完整阶段序列；
- fault：每类故障都必须落 `FAULT` 且调用 safe-stop；
- idempotency：同一 `request_seq` 不得执行两次；
- event log：每个状态迁移只追加一次，终态可重建；
- 3D event source：同一日志产生一致 Task ID、逻辑格和故障字幕。

### 在线门禁

1. F3 碰撞关闭后，对代表格 1、30、54 各执行三轮；
2. C4 单条 INBOUND 连续三次无碰撞、侧翻、散落、超时；
3. C5 依次执行 INBOUND、OUTBOUND、DUAL；
4. 注入一次可控传感器/超时故障，验证 Fault→safe-stop→人工 Reset→新 Task；
5. AB、JSONL、自研 3D 和 Factory I/O 录屏中的 Task ID 全部一致；
6. 正式口径审计不得出现“Factory I/O 400 格”“Python=AC500”“3D 回放=物理验证”。

## 9. 提交与回滚

- 每个门禁独立 commit，提交前只暂存本门禁文件；
- 现有用户/Claude 脏文件不纳入提交；
- AB 文件修改前备份；AB GUI 关闭后才运行 `ab_sync`；
- 每个在线门禁红灯都停在当前层，不向后扩展；
- 自研 3D 原有 `anim3d_formal_60s.mp4` 保留，新输出使用新文件名，不覆盖历史证据。

## 10. 完成判据

路径 C 完成必须同时满足：AB 产生并派发三类任务；Factory I/O 返回三类任务终态；故障可安全停机且不重复执行；统一日志可重建全过程；自研 3D 使用同一日志展示严格 20×20；所有 54/400 边界在画面和文档中明确。缺一项只能称阶段性技术预演，不能称完整控制闭环。
