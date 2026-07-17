# 给 Claude Code 的继续提示词（0713 终局交接版）

下面整段可直接复制给 Claude Code：

```text
接管并继续 F:\abb_wh_work 的 Factory I/O / F3 任务。不要依据旧聊天记忆猜状态，也不要重新论证用户已经拍板的“Factory I/O 路径 C + 保留并优化自研 3D”。Codex 已结束现场执行，只保留独立复核角色。

先完整按顺序读取：
1. F:\abb_wh_work\docs\overnight2-report_0712night.md
2. F:\abb_wh_work\l2_factoryio\F3_现场故障与Claude接管_20260713.md
3. F:\abb_wh_work\_通信\codex_out\0713_H1对抗审查.md
4. F:\abb_wh_work\_通信\codex_out\0713_F3终局交接与Claude接管.md
5. F:\abb_wh_work\l2_factoryio\io_map.md
6. F:\abb_wh_work\_通信\致Codex.md 顶部最新节

状态优先级：当前磁盘/实时只读检查 > 0713_H1对抗审查 > 0713_F3终局交接增量 > 12:12 旧总账中的历史快照。旧总账里“Factory I/O 已关闭”“代码未提交”等只描述 12:12 时点，不得当作当前状态。

Codex 13:24 的动态快照：Factory I/O PID 43236 自 13:04:22 在运行；未见 Python/ffmpeg；fault_state.json 为 RECOVERY_UNSAFE、cell 30、cargo_trust=false、phase=recover-retract、13:18:56。你接管时先只读重查，不能假定仍相同。当前 scene/旧货物一律视为不可信，不得 travel，不得用现有 reset-epoch 清锁继续。

关键裁决：H1 方向正确，但当前实现不签绿，先暂停自主带货 H3。85/85 离线测试已由 Codex 用六模块命令真实复现，不要争论测试数；问题是测试没有覆盖这些安全序列：

1. fault_state 文件缺失、删除或合法降级 JSON 会解锁；cargo_trust 不参与 is_locked。
2. 锁只守 f3_stacker_control CLI；f3_mechanics_probe、webapi emitter-pulse 和直接 Stacker 调用可绕过。
3. record_fault / record_phase_state / reset 都是无互斥的读改写，存在丢 fault；动作只在入口检查一次锁，有 TOCTOU。
4. reset-epoch 的完整重启只是 --operator-confirmed-restart 布尔旗标；preflight 不查四个 active-low 货物传感器、Emitter、货架/叉上/地面，非空场可通过。
5. safe_stop 在 fork snapshot 失败时先抛出，根本没有尝试 Target=0。
6. 双叉 C2+C3=True 会择一保持并主动清另一侧；陈旧 fork_hold 会先清现场真实叉，最后才报错；未校验线圈与 one-hot 限位一致，也未确认 X/Z 已停止。
7. pick/relift/place-lower 只在错误字符串含 NO START 时落锁；已启动后 TIMEOUT、Modbus error、Stop/E-stop、Ctrl-C、强杀均可能不落锁。
8. place-extend 的 last_phase 只在成功后写、只写不读、lift_command=None；强杀窗口没有 write-ahead intent。
9. place-lower NO START 落锁后，普通 recover-lift/recover-retract 又被全局 diagnose 锁挡住，恢复策略语义冲突；recover-lift 还允许无 Z 当作“可能已抬起”。

现在按以下顺序执行：

A. 先冻结现场写入并保存当前证据。不要使用当前货物继续试验。现有 safe_stop 尚未通过审查，退出/清场须采用人工外部安全流程，不得宣称软件已安全停机。

B. 离线实现 H1.1：
- 设备级单写者/命令租约；锁守门下沉到全部写入口。
- 状态 schema/version/revision，文件缺失或降级 fail-closed；fault 在竞态中永远优先。
- safe_stop 先独立 best-effort Target=0，再确认 Moving X/Z=False；叉状态须双快照+线圈/one-hot 限位一致，任何歧义不写叉/Lift并落锁。
- Lift/Fork/Target 写入前 durable transition_pending，真实 settle/视觉门后 completion；异常、取消、Stop/E-stop、强杀或下次启动发现 pending 都锁定。
- reset epoch 若拿不到可信 Factory I/O session/uptime/scene id，就明确降级为人工程序确认；空场门至少查 Entry/Load/Unload/Exit、Emitter force-off、Target/线圈/限位/稳定时间，并附可追溯视觉证据。
- 决定恢复路线：推荐故障后完整退出/清场并废弃误导性 recover；若保留，做成锁下唯一允许的窄恢复状态机，绝不恢复后 travel。

C. 测试先行并保留复现证据：在现有 85 项上新增删除/降级状态、两进程竞态、非空场 reset、snapshot 失败仍 Target0、双叉/陈旧 hold/线圈限位冲突、TIMEOUT/E-stop/强杀、所有旁路入口等测试。提供每模块计数、完整命令和日志。Mock 结果只称离线门，不称 Factory I/O 现场证据。

D. H1.1 离线绿后，按用户拍板的新常态机制，在 F:\abb_wh_work\_通信\致Codex.md 顶部签发独立复核任务书，列 commit/文件/测试/重点攻击面。Codex 接受前不要开始带货 H3。

E. 复核通过后先做空载安全语义现场试验：完整应用重启、新 debug 副本、Emitter force-off、空场证据；验证 Target stop、Pause/Stop/E-stop/断连、双叉歧义拒写。之后才用新箱、固定箱型、斜俯视固定机位和 10-20 秒视频逐帧执行 G1→G4 拆门。任一异常整轮作废，不原地续跑。

F. 只有拿到首次接触帧时才做局部 safeguard 单变量 A/B；禁止删除整圈、禁止移动 Rack/Stacker/整套输送带。target 30 只是完整重启+新箱的单变量 A/B，不是已验证解决方案。

G. F3 必须 cell 1/30/54 各 3 次、9/9 全绿后，才进入 F4 AB OPC UA→F5/C5→C6 同源自研3D→F6 回补。每个 F 级任务完成立即给 Codex 签独立复核任务书。

永久口径：20×20/400 是 ABB/算法/AB/ST/自研 3D 的业务真相；Factory I/O 2.5.10 只做 54 格代表性物理 I/O/时序/安全验证。不得称 400 格物理孪生、AC500/AB 实测闭环；Python 直控素材必须标“技术预演”。自研 3D 后续读取同一 task/event JSONL，形成同一任务双视图。

用户红线：禁止所有 superpowers 系列 skills；不碰 1_给你看、2_你要操作、canonical、报告/PPT、账号密码；PPT 等用户另行确认；不清理脏工作树，不用 git add . / git add -A / reset / checkout。Git/Push 只按 overnight2 最新明确授权范围执行，不扩大。

每个里程碑都更新 docs/overnight2-report_0712night.md，并记录：改了什么、测试命令/结果、现场证据、负结果、偏离计划、下一门。不要用通过测试替代物理验收，也不要为了赶进度跨门。
```
