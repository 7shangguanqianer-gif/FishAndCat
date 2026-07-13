# Factory I/O · Automated Warehouse 场景 I/O 点表（F2 侦察产物，0712）

> 环境实测：FACTORY I/O **v2.5.10 Ultimate Edition**（`F:\Factory IO.exe`，状态栏截图 `img/F2_ultimate_edition_scene_loaded_0712.png`）。
> 驱动：**Modbus TCP/IP Server**（Factory I/O 当 server，Python 用 pymodbus **client** 直连——比预案"pymodbus 起 server 等它连"依赖更少）。
> 绑定：`127.0.0.1:502`，Slave ID `1`，Auto start ✓。
> ⚠ 网卡坑（已修）：CONFIGURATION 里 Network adapter 默认落在 **Meta Tunnel**（Clash 虚拟网卡 198.18.0.1），Python 连 127.0.0.1 会扑空；已改 **Software Loopback Interface 1**，Host 自动变 127.0.0.1。Clash 开关不再影响链路。
>
> **0713 现场纠错（G2/G4 待画面终签）：** 当前固定机位与有效取箱边沿支持“Left=载入输送带侧、Right=货架侧”；0712 初稿把两侧写反。以下点表已按当前工作假设修正，最终只以 G2 真实承载与 G4 真实入架画面为准，不能只凭限位信号宣告成立。
>
> **0713 实物极性复核（进程重启后，入口托盘+箱体画面与 Modbus 同步取证）：** Automated Warehouse 的货物传感器 At Entry/Load/Unload/Exit 在当前 Modbus 映射中为 **active-low**：`False=有货遮挡`、`True=空`。现场快照为入口有货 `At Entry=False`，其余空位 `At Load/Unload/Exit=True`。此前仅凭 F6 后远景把 `At Load=False` 判为空载的结论已作废。

## 默认映射（驱动面板自动生成，截图 `img/F2_modbus_server_default_mapping_0712.png`）

### Discrete Inputs（传感器，Python 读 `read_discrete_inputs(0, count=15, slave=1)`）
| 地址 | 点名 | 类型 | 含义 |
|---|---|---|---|
| Input 0 | At Entry | Bool | 入口输送带箱到位 |
| Input 1 | At Load | Bool | 载入位（堆垛机取箱口）箱到位 |
| Input 2 | At Left | Bool | 叉臂在左（当前工作假设：伸向载入输送带侧） |
| Input 3 | At Middle | Bool | 叉臂居中（收回） |
| Input 4 | At Right | Bool | 叉臂在右（当前工作假设：伸向货架侧） |
| Input 5 | At Unload | Bool | 卸载位箱到位 |
| Input 6 | At Exit | Bool | 出口输送带箱到位 |
| Input 7 | Moving X | Bool | 堆垛机水平移动中 |
| Input 8 | Moving Z | Bool | 堆垛机垂直移动中 |
| Input 9 | Start | Bool | 面板 Start 按钮 |
| Input 10 | Reset | Bool | 面板 Reset 按钮 |
| Input 11 | Stop | Bool | 面板 Stop 按钮（常闭，静态 True） |
| Input 12 | Emergency stop | Bool | 急停（常闭，静态 True） |
| Input 13 | Auto | Bool | 手/自动选择开关 |
| Input 14 | FACTORY I/O (Running) | Bool | 仿真运行中（RUN 状态才 True） |

### Coils（执行器，Python 写 `write_coil(addr, val, slave=1)`）
| 地址 | 点名 | 含义 |
|---|---|---|
| Coil 0 | Entry Conveyor | 入口输送带走 |
| Coil 1 | Load Conveyor | 载入输送带走 |
| Coil 2 | Forks Left | 叉臂伸左（当前工作假设：载入输送带侧；G2 画面终签） |
| Coil 3 | Forks Right | 叉臂伸右（当前工作假设：货架侧；G4 画面终签） |
| Coil 4 | Lift | 叉臂升（取/放箱行程） |
| Coil 5 | Unload Conveyor | 卸载输送带走 |
| Coil 6 | Exit Conveyor | 出口输送带走 |
| Coil 7 | Start light | 面板灯 |
| Coil 8 | Reset light | 面板灯 |
| Coil 9 | Stop light | 面板灯 |

### Holding Register（Python 写 `write_register(0, val, slave=1)`）
| 地址 | 点名 | 含义 |
|---|---|---|
| Holding Reg 0 | Target Position | 堆垛机目标货位号（int；具体编号规则见 F3 实验记录） |

## 叉臂取放动作契约（0713 现场实锤）

`Forks Left` / `Forks Right` 是**保持型命令**，不是到限位即撤销的脉冲命令：命令撤销后，机构会自动回 `Middle`。此前在 `At Left` / `At Right` 到位后立即撤销，导致取放过程中的货物被叉臂拉回；该逻辑不得再使用。

正确序列如下（向左或向右只选择对应的一路叉臂输出）：

1. 令目标方向叉臂输出 `True`，并持续保持；另一方向输出保持 `False`。
2. 在叉臂保持伸出期间切换 `Lift` 完成取货或放货，并等待升降行程结束、货物落稳。
3. 如需人工视觉确认，继续保持叉臂输出，不得因已到 `At Left` / `At Right` 而释放。
4. 完成确认后，将 `Forks Left=False` **且** `Forks Right=False`；叉臂才释放并自动回 `Middle`。应确认 `At Middle=True` 后再进入下一相位。

`Lift` 每次 True/False 状态转换都必须看到真实 `Moving Z` 启动沿和稳定结束；`NO START` 表示物理状态与线圈读回失配，必须停在当前人工门处理。不得再以“零行程”或固定 dwell 代替 Z 运动证据。0713 空载 A 探针已确认：`Forks Right=True` 保持期间写 `Lift=False`，`Moving Z` 可在约 0.094 s 启动并约 1.98 s 落稳，因此 Right 保持本身不是本轮掉箱根因。

### 恢复相位：`relift`

若固定机位画面已由操作员确认货物仍在承载台，同时叉臂在 `Middle`、当前 cell 位置已确认且 `Lift=False`，则先写 `Lift=True` 进入 `relift` 恢复。Factory I/O 没有承载台 cargo-present 反馈，`At Load` 只能证明载入位未被遮挡，不能代替上述人工画面门。该恢复步骤**不得移动 X，也不得动作任一叉臂**；仅在升举状态恢复并重新确认现场条件后，才可继续后续流程。

## 冒烟验证（`f2_smoke_read.py`，0712 实测 PASS）
- `connect: True`；15 inputs / 10 coils / HReg0 / IReg0 全部读通零报错。
- 编辑模式（未 RUN）下 Input 14 = False，符合预期；Emergency stop / Stop 常闭显 True。

## 本机可用驱动全清单（Ultimate 证据，截图 `img/F2_driver_list_all_unlocked_0712.png`）
None / Advantech USB 4704 & 4750 / Allen-Bradley Logix5000 / Micro800 / MicroLogix / SLC 5-05 / Automgen Server / Control I/O / MHJ / **Modbus TCP/IP Client** / **Modbus TCP/IP Server** / **OPC Client DA/UA**（← F5 直连 AB 的关键件）/ Siemens LOGO! / S7-200-300-400 / S7-1200-1500 / S7-PLCSIM。

## 路线判定（对 F3/F5 的输出）
- **F3 快线选型=Modbus TCP/IP Server 驱动 + pymodbus client**（依赖最少、工业标准协议、故事性最好）。Engine I/O SDK（Ultimate 已解锁）记为备选不实施，除非 Modbus 撞墙。
- **F5 正线联调件已确认在场**：OPC Client DA/UA 驱动（Factory I/O 侧）；成败只取决于 F4（AB 仿真 PLC 能否开 OPC UA server）。
