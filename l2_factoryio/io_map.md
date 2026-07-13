# Factory I/O · Automated Warehouse 场景 I/O 点表（F2 侦察产物，0712）

> 环境实测：FACTORY I/O **v2.5.10 Ultimate Edition**（`F:\Factory IO.exe`，状态栏截图 `img/F2_ultimate_edition_scene_loaded_0712.png`）。
> 驱动：**Modbus TCP/IP Server**（Factory I/O 当 server，Python 用 pymodbus **client** 直连——比预案"pymodbus 起 server 等它连"依赖更少）。
> 绑定：`127.0.0.1:502`，Slave ID `1`，Auto start ✓。
> ⚠ 网卡坑（已修）：CONFIGURATION 里 Network adapter 默认落在 **Meta Tunnel**（Clash 虚拟网卡 198.18.0.1），Python 连 127.0.0.1 会扑空；已改 **Software Loopback Interface 1**，Host 自动变 127.0.0.1。Clash 开关不再影响链路。

## 默认映射（驱动面板自动生成，截图 `img/F2_modbus_server_default_mapping_0712.png`）

### Discrete Inputs（传感器，Python 读 `read_discrete_inputs(0, count=15, slave=1)`）
| 地址 | 点名 | 类型 | 含义 |
|---|---|---|---|
| Input 0 | At Entry | Bool | 入口输送带箱到位 |
| Input 1 | At Load | Bool | 载入位（堆垛机取箱口）箱到位 |
| Input 2 | At Left | Bool | 叉臂在左（伸向货架侧） |
| Input 3 | At Middle | Bool | 叉臂居中（收回） |
| Input 4 | At Right | Bool | 叉臂在右（伸向输送带侧） |
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
| Coil 2 | Forks Left | 叉臂伸左（货架侧） |
| Coil 3 | Forks Right | 叉臂伸右（输送带侧） |
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

## 冒烟验证（`f2_smoke_read.py`，0712 实测 PASS）
- `connect: True`；15 inputs / 10 coils / HReg0 / IReg0 全部读通零报错。
- 编辑模式（未 RUN）下 Input 14 = False，符合预期；Emergency stop / Stop 常闭显 True。

## 本机可用驱动全清单（Ultimate 证据，截图 `img/F2_driver_list_all_unlocked_0712.png`）
None / Advantech USB 4704 & 4750 / Allen-Bradley Logix5000 / Micro800 / MicroLogix / SLC 5-05 / Automgen Server / Control I/O / MHJ / **Modbus TCP/IP Client** / **Modbus TCP/IP Server** / **OPC Client DA/UA**（← F5 直连 AB 的关键件）/ Siemens LOGO! / S7-200-300-400 / S7-1200-1500 / S7-PLCSIM。

## 路线判定（对 F3/F5 的输出）
- **F3 快线选型=Modbus TCP/IP Server 驱动 + pymodbus client**（依赖最少、工业标准协议、故事性最好）。Engine I/O SDK（Ultimate 已解锁）记为备选不实施，除非 Modbus 撞墙。
- **F5 正线联调件已确认在场**：OPC Client DA/UA 驱动（Factory I/O 侧）；成败只取决于 F4（AB 仿真 PLC 能否开 OPC UA server）。
