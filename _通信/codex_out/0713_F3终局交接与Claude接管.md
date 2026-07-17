# F3 终局交接与 Claude Code 接管增量（2026-07-13 13:24）

> 用户决定：Codex 结束当前 Factory I/O 任务，由 Claude Code 继续。  
> 本文件是 **13:24 增量交接和阅读路由**，不是把 12:12 总账重写一遍。  
> 完整历史细节仍以 `l2_factoryio/F3_现场故障与Claude接管_20260713.md` 为主；H1 最新安全裁决以 `_通信/codex_out/0713_H1对抗审查.md` 为主。  
> 若旧文中的“进程已关闭/代码未提交”等现场快照与本文件冲突，只把旧句当历史时点，不当当前状态。

## 1. 接管时必须先读的真相链

按顺序读，不从聊天记忆推测：

1. `docs/overnight2-report_0712night.md`
   - 第二轮唯一上层账本；含 F0-F8、C 路线、13 项拍板和 H1/H2/H3 状态。
2. `l2_factoryio/F3_现场故障与Claude接管_20260713.md`
   - 12:12 前全部现场时间线、错判纠正、日志/截图索引、20×20/54 格边界、验收定义。
3. `_通信/codex_out/0713_H1对抗审查.md`
   - 13:24 对 H1 的独立安全审查；**当前最高优先增量裁决：H1 不签绿。**
4. `l2_factoryio/io_map.md`
   - active-low 货物输入、Fork/Lift/Target 语义和点表。
5. `l2_factoryio/0713_F3碰撞闭环与20x20边界设计.md`
   - C+自研 3D 路线设计；旧实施计划中的 superpowers 要求已被用户废止。
6. `_通信/致Codex.md:11-24`
   - 当前 Claude→Codex 任务与长期复核机制。

## 2. 当前总状态

### 2.1 哪些已完成

- F0：基线 CSV 修复、`core_smoke` 通过。
- F1：流程与挂机纪律落账。
- F2：Factory I/O 2.5.10 Ultimate、Automated Warehouse、Modbus TCP/IP Server、Loopback、15 In/10 Coil/Target 点表均已确认。
- C1/C2 离线层：20×20→54 代表映射、任务契约、JSONL 事件、INBOUND/OUTBOUND/DUAL 离线编排已存在。
- F3 的协议/机构基础：Python↔Modbus 可读写；空载机构探针可运行；一次完整重启后的单箱 G1 feed、G2 pick、G3 travel 到 cell 1 成功。
- H1 已有实现：G4 拆门、fault lock、负载感知 stop、部分 NO START 落锁、85 个离线测试。
- 轨 A 文档批次已完成且未回退；六项制品哈希仍与 0712 完成报告一致，PPT 仍延缓重生。

### 2.2 哪些仍是红灯

- **F3 未签绿。** 真实放货/恢复/运输出现无 Z、姿态失真和掉落。
- **H1 当前不签绿。** 持久锁可删除/降级绕过；reset 不证明重启/空场；safe_stop 读失败时不先 Target 0；存在多进程竞态、异常中断不落锁、双叉/陈旧 hold 危险写入。
- H3 单箱完整链未通过，H5 的 cell 1/30/54 各 3 次、9/9 未开始。
- F4 AB OPC UA 3b、F5 Factory I/O↔AB/CODESYS、C5 三任务在线、C6 自研 3D 同源事件、F6 主工程回补均未完成或不得越门。
- 正式视频素材不得把当前调试失败片段当完成证据。

### 2.3 13:24 动态快照（会漂移，接管先重查）

- Factory I/O 正在运行：PID 43236，StartTime 13:04:22。
- 未发现 Python/ffmpeg 控制进程。
- `l2_factoryio/fault_state.json`：`RECOVERY_UNSAFE`，cell 30，`cargo_trust=false`，记录于 13:18:56，phase=`recover-retract`。
- `l2_factoryio/logs/` 最新持久日志仍是 12:01 的 `F3_diagnose_20260713_120146.log`；当前 13 点现场动作没有对应新日志可供 Codex证明。
- Codex 遵守只读红线，未碰 Factory I/O、fault_state 或 `l2_factoryio/`。

这意味着：**当前 scene 不能视为新基线，当前货物不能续跑；不要因为 GUI 仍开着就直接 travel，也不要用现有 reset-epoch 清锁继续旧货。**

## 3. 现场失败事实（勿重新猜根因）

### 3.1 干净链到 G3

- `logs/F3_diagnose_20260713_114630.log`：单箱 feed 成功。
- `logs/F3_diagnose_20260713_114708.log`：pick 成功，Lift 有真实 Z 边沿，货物离开 At Load。
- `logs/F3_diagnose_20260713_114747.log`：带载到 cell 1 成功，近景当时仍在承载台。

### 3.2 G4 无 Z

- `logs/F3_diagnose_20260713_114828.log`：Right 到位、C3 保持后写 Lift=False，3 秒内没有 Moving Z。
- `img/F3_cell1_place_no_z_20260713_1148.jpg`：对应现场。
- 旧“zero-stroke accepted”结论已经作废；空载 A 探针证明正常下放应有真实 Z 边沿。

### 3.3 恢复后继续运输导致掉落

- `recover-lift → recover-retract` 只能撤险，不能证明货物姿态可信。
- `logs/F3_diagnose_20260713_115743.log` 的 I/O 虽显示到 cell 30，但用户斜俯视确认货物掉落。
- 证据：`img/F3_recovery_travel_drop_cell30_20260713_1158.jpg` 与 crop。
- 结论：任何 recovery 后严禁 travel；I/O 完成不等于货物完成。

### 3.4 F6 不能替代完整重启

- F6 后新 feed 成功：`logs/F3_diagnose_20260713_120116.log`。
- 随后的新 pick 在 Left 到位、Lift=True 后仍无 Z：`logs/F3_diagnose_20260713_120146.log`。
- 结论：F6 只清货，不保证输出/实体 Lift/物理求解状态归零。

### 3.5 已排除或降置信度的假设

- “Right=True 是 Lift 软件互锁”：基本排除。空载 A 探针在 Right 保持时下降真实启动并落稳，见 `logs/F3_mechanics_A_20260713_065413.log`。
- “Codex 把整套输送带/堆垛机移动错位”：当前证据不支持。官方 baseline 与 debug 场景各 45 Proxy；Rack、Stacker、Conveyors Position/Rotation 一致，仅 4 个 SafeguardL 四元数末位序列化差异。
- “删整圈防护网即可”：无证据。只有拿到首次接触帧后，才允许在副本中单独外移一个护栏段做 A/B。

### 3.6 仍需验证的高置信根因方向

- Lift 实体状态与命令读回不一致；命令线圈不是位置反馈。
- 托盘/箱体在取货或伸叉前已偏姿，可能与叉具、货架梁、局部护栏/立柱发生接触。
- 物理求解在带载/夹持几何下被约束，导致 Moving Z 不起或货物在回抽/运输时掉落。
- Factory I/O Pause/Stop/E-stop/Modbus 断连对保持型输出的真实语义尚未形成现场证据。

## 4. 20×20 与 Factory I/O 的最终职责边界

- 20×20/400 仓位是 ABB 业务、算法、AB/ST 与自研 3D 的真相。
- Factory I/O 2.5.10 原生 Numerical 目标只有 54 格；它只做 **54 格代表性物理 I/O/时序/安全验证**。
- 不得宣称 Factory I/O 是 400 格物理孪生，不得把 Python 直控说成 AC500/AB 闭环。
- 自研 3D 保留，后续通过同一 task/event JSONL 展示完整 20×20、复杂结构、策略解释。
- 两种 3D 有运动展示重合，但价值不同：Factory I/O 提供工业设备/协议/碰撞证据；自研 3D 提供完整规模/可解释镜头。最终应讲“同一任务的双视图”。

## 5. H1 对抗审查的必须修项

### 5.1 持久锁

1. 状态文件缺失、schema 降级、`cargo_trust!=True` 必须 fail-closed。
2. 锁守门必须覆盖 f3 CLI、mechanics probe、webapi emitter-pulse 与直接 Stacker 写入。
3. 用进程互斥/命令租约 + revision/CAS，防止 phase/reset 覆盖新 fault。
4. fault 当前态与 append-only 审计事件分离。

### 5.2 safe_stop

1. 先独立尝试 `Target=0`，再读叉状态。
2. 确认 Moving X/Z=False；失败升级外部安全链。
3. 用连续稳定快照校验线圈与 one-hot 限位。
4. 双叉、线圈/限位冲突、陈旧内存 hold 均不得改叉输出，应锁定。

### 5.3 transition journal

- Lift/Fork/Target 写入前先落 `transition_pending`；真实 settle/视觉门后写 completion。
- TIMEOUT、Modbus error、Stop/E-stop、Ctrl-C、强杀、下次启动发现 pending 都必须锁定。
- 当前只对字符串 `NO START` 落锁不够。

### 5.4 reset epoch

- 若能从 Web API 取得可信 session/uptime/scene id，就验证新旧 epoch；否则只能叫“人工确认重启”。
- 空场门至少覆盖 Entry/Load/Unload/Exit、Emitter force-off、Target/线圈/限位/稳定时间。
- 叉上、货架、地面/跌落区必须有可追溯视觉/API 证据。

### 5.5 恢复路线必须二选一

- 推荐：故障后只允许完整退出/清场，删除误导性的 recover 继续路径。
- 若保留 recover：必须是独占锁下的窄恢复状态机，不能一般解锁，更不能恢复后 travel。

## 6. Claude 接管执行顺序

### Step 0：冻结现场写入，保存当前证据

- 只读确认 PID、GUI 状态、fault_state、Emitter、scene 文件与是否有散落货物。
- 不使用当前货物继续任何动作。
- 若需要退出/清场，按人工外部安全流程处理；不要把现有 `safe_stop` 当已证明安全。

### Step 1：离线修 H1.1

按 5.1-5.5 修改；先补测试后改实现。不得触碰用户文档/canonical；保持用户禁用 superpowers skills。

### Step 2：离线复验并签 Codex 复核

- 运行现有 85 项 + 新增竞态/强杀/状态真值表测试。
- 保留可复现命令、测试数和日志。
- 在 `_通信/致Codex.md` 顶部签发 H1.1 独立复核；H1.1 未接受前不进入带货 H3。

### Step 3：现场安全语义试验（空载优先）

- 完整应用重启，新 debug 副本，Emitter force-off，空场证据。
- 先验证 Target stop、双叉异常拒写、Pause/Stop/E-stop/断连/进程退出。
- 这些不是货物验收，不能混入 9/9。

### Step 4：单箱单变量 H3

- 新箱、固定箱型、斜俯视固定机位、10-20 秒视频逐帧。
- G1→G2→G3 后，G4 只到 place-extend；通过 clearance/倾斜/勾挂门才 place-lower。
- 任一异常立即落锁、保存视频/日志、整轮作废，不原地续跑。
- target 30 只能是完整重启+新箱的单变量 A/B，不是万能替代货位。

### Step 5：条件式几何 A/B

- 只有首次接触帧明确指向某一 safeguard/立柱，才复制 scene，只改该单件。
- 控制时序、箱型、物理参数和几何不能同轮一起改。
- A/B 无改善立即撤销护栏假设，转叉具/托盘/货架梁/实体 Lift 状态。

### Step 6：F3 9/9 后才进入后续

- cell 1/30/54 各 3 次；每次无碰撞、无掉落、真实 Z、货架承载成立、故障门可复现。
- F3 绿后再做 F4 AB OPC UA；随后按结果进入 F5/C5/C6/F6。
- 每个 F 级任务完成后，按用户拍板给 Codex 签独立客观复核任务书。

## 7. 严禁事项

- 禁用所有 superpowers 系列 skills。
- 不把 F6 当完整重启，不从 recovery/drop/NO START 的旧货继续 travel。
- 不凭 I/O 日志单独宣告货物成功。
- 不删除整圈防护网，不移动 Rack/Stacker/整套输送带“对齐画面”。
- 不把 Factory I/O 写成 400 格物理孪生、AB/AC500 实测或完整闭环。
- 不触碰 `1_给你看/`、`2_你要操作/`、canonical、账号密码；PPT 仍等用户另行确认。
- 不清理脏工作树；禁止 `git add .`、`git add -A`、reset/checkout。
- Push 只有在用户明确授权的范围内执行；接管前先重读最新拍板。

## 8. 交接产物索引

- 完整旧总账：`l2_factoryio/F3_现场故障与Claude接管_20260713.md`
- 旧 Claude 提示词：`l2_factoryio/ClaudeCode接管提示词_F3_20260713.md`
- 本次 H1 审查：`_通信/codex_out/0713_H1对抗审查.md`
- 本增量交接：`_通信/codex_out/0713_F3终局交接与Claude接管.md`
- 最新可复制提示词：`_通信/codex_out/0713_给Claude继续F3提示词.md`
- 上层账本：`docs/overnight2-report_0712night.md`

## 9. Codex 最终状态

Codex 已完成本轮只读审查与落盘，不再操作 Factory I/O/F3。后续由 Claude Code 按上述顺序修 H1.1；待 Claude 签发新复核任务时，Codex 只做独立证据复核，不替代 Claude 继续现场控制。
