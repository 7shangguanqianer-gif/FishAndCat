# 给 Claude Code 的接管提示词（F3，2026-07-13）

下面整段可直接复制给 Claude Code：

```text
接管 F:\abb_wh_work 的 Factory I/O / F3 任务。不要从聊天记忆猜状态，也不要重新论证已拍板的 20×20 路线。

先按顺序完整读取：
1. F:\abb_wh_work\l2_factoryio\F3_现场故障与Claude接管_20260713.md（本次终止交接，现场最高优先）
2. F:\abb_wh_work\docs\overnight2-report_0712night.md（第二轮唯一上层账本）
3. F:\abb_wh_work\l2_factoryio\io_map.md
4. F:\abb_wh_work\l2_factoryio\0713_F3碰撞闭环与20x20边界设计.md
5. 当前 git status/diff，尤其：
   - l2_factoryio/f3_stacker_control.py
   - l2_factoryio/test_f3_stacker_control.py
   - l2_factoryio/f3_mechanics_probe.py
   - l2_factoryio/test_f3_mechanics_probe.py

硬事实：
- Codex 已终止现场；Factory I/O 与 Python 控制进程均关闭。
- F3 未通过：Modbus/空载机构/一次干净 G1-G3 可用，但 cell 1 G4 下放无 Z；恢复后带货移到 cell 30 时用户确认掉落；F6 后的新 G2 又出现 Lift 命令无 Z。
- F6 只能清货，不保证输出和实体 Lift 复位。异常后必须完整退出并重启 Factory I/O，不能接着上一箱。
- Right=True 不是 Lift 软件互锁：空载 A 探针已在 Right 保持下真实下降。
- 官方/Debug 场景 45 个 Proxy 的 Rack、Stacker、Conveyors 几何一致；暂无证据是整套设备被移错。
- 恢复后的货物姿态不可信，严禁 travel。target 30 只允许作为完整重启+新箱的单变量 A/B，不是已验证解决方案。
- 20×20/400 是 AB+算法业务真相；Factory I/O 只做 54 格代表性物理 I/O/时序验证；自研 3D 保留并最终读取同源任务/JSONL 事件。
- F4 AB OPC UA、F5 联调、F6 回补和正式录屏均未开始。

用户最新约束：禁止使用所有 superpowers 系列 skills。旧的 0713 实施计划开头若仍有 REQUIRED superpowers 字样，一律视为已废止。不要触碰 1_给你看、2_你要操作、账号密码、canonical 数字、报告/PPT；不要清理当前脏工作树；禁止 git add . / git add -A / reset/checkout。Push 必须再次得到用户明确授权。

接管后不要立刻启动 Factory I/O。先做 H0/H1：
1. 运行离线 py_compile、unittest、git diff --check，确认现有基线。
2. 审查 HEAD f0bd29f 之后的未提交 recovery 改动。保留“recover-lift/recover-retract 仅撤险、RECOVERY_UNSAFE 不可继续任务”的语义。
3. 先补五项 fail-closed 门：
   a) 把 G4 拆成 place-extend → 人工画面确认 → place-lower(必须真实 Z) → 人工确认货架承载 → retract；Right 到位后不得立即下放。
   b) 增加跨进程持久 fault/reset epoch；NO START、drop、recovery 后 cargo trust=false，完整应用重启+空场 preflight 才解锁。
   c) stop 从 C2/C3 与 Left/Middle/Right 读回重建叉保持；支撑未知时不得自动撤叉。
   d) 没有实体 Lift 高低位反馈时，把无 Z 标为 LIFT_POSITION_UNKNOWN，不能用线圈读回伪造成功。
   e) 为上述门增加离线测试，尤其验证 CLI 新进程不能用 --confirm flags 绕过 RECOVERY_UNSAFE。
4. 把有意义的实现/验证/偏差追加到 l2_factoryio/F3_现场故障与Claude接管_20260713.md 与 docs/overnight2-report_0712night.md；不要覆盖原始失败证据。

H1 全绿后才做 GUI：
1. 完整启动 F:\Factory IO.exe，载入
   C:\Users\86177\Documents\Factory IO\My Scenes\Automated WarehouAutomated Warehouse_debug_prebaseline_0713se.factoryio
   不修改官方基线。
2. EDIT 中确认 Web API；必要时 console 执行 app.web_server = True。
3. Emitter tag id=8e4549f8-74ed-4dd8-ab3d-b8ddb795e8c7。它曾是 isForced=true/forcedValue=true；普通 /api/tag/values 写 false 无效，必须用 PUT /api/tag/values-force 确认强制为 false。
4. RUN 后先空场 preflight：C0..C6=False、Target=0、Middle=True、Moving X/Z=False。失败则不生成货物。
5. 短暂 force Emitter true；At Entry 变为有货后立即 force false；用斜俯视固定机位确认全场只有一个托盘+箱体。
6. 分相位执行 G1/G2/G3；G4 只先伸 Right 并停在下放前人工门。任何倾斜/接触/无 Z，立刻保存日志+截图，持久 fault lock，退出应用；不要 F6 后续跑。
7. 第一个干净 A/B 可用 target 30，只用于判断 cell 1 是否特异。若首次接触明确指向单段防护网，再复制场景仅外移该段；禁止删除整圈或移动整套 Rack/Stacker/Conveyor。

正式验收仍是 1/30/54 各 3 次共 9/9；每次真实 Z START+SETTLE、画面无碰撞/勾挂/侧翻/掉落、日志与画面一致。9/9 前 F3 不签绿、不录正式素材、不进入 F4/F5/F6。

关键证据直接看：
- logs/F3_mechanics_A_20260713_065413.log
- logs/F3_diagnose_20260713_114630.log
- logs/F3_diagnose_20260713_114708.log
- logs/F3_diagnose_20260713_114747.log
- logs/F3_diagnose_20260713_114828.log
- logs/F3_diagnose_20260713_115529.log
- logs/F3_diagnose_20260713_115609.log
- logs/F3_diagnose_20260713_115743.log
- logs/F3_diagnose_20260713_120116.log
- logs/F3_diagnose_20260713_120146.log
- img/F3_cell1_place_no_z_20260713_1148.jpg
- img/F3_recovery_travel_drop_cell30_20260713_1158.jpg
- img/F3_recovery_travel_drop_cell30_crop_20260713_1158.png
- img/F3_postF6_pick_no_z_20260713_1201.jpg

每个阶段先报告：修改文件、验证命令/结果、物理证据、剩余风险、是否允许进入下一门。不要把“命令完成”写成“货物完成”。如果同一现场子问题连续失败 3 次，保留证据并暂停该分支，不继续暴力试错。
```
