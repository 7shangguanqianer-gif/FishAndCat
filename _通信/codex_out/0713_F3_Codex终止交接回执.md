# 0713 F3 Codex 终止交接回执

时间：2026-07-13 12:12（America/Chicago）

## 结论

- 已按用户指令停止当前 Factory I/O 任务；Factory I/O 与 Python 控制进程均已关闭。
- F3 状态为 **控制链部分通过、物理搬运未通过**，不能签绿。
- 已把完整时间线、现场证据、路线变化、代码状态、根因假设、禁止项、下一步安全门和验收条件落到：
  - `l2_factoryio/F3_现场故障与Claude接管_20260713.md`
- 已把可直接复制给 Claude Code 的接管提示词落到：
  - `l2_factoryio/ClaudeCode接管提示词_F3_20260713.md`

## 最高优先的新现场事实

1. cell 1 的干净 G1/G2/G3 通过，G4 Right 到位后 `Lift=False` 无 `Moving Z`，见 `logs/F3_diagnose_20260713_114828.log:5-10`。
2. 恢复回中后的货物从 cell 1 移到 cell 30 时，I/O 显示运动完成，但用户画面确认掉落，见 `logs/F3_diagnose_20260713_115743.log:5-14` 与 `img/F3_recovery_travel_drop_cell30_20260713_1158.jpg`。
3. F6 后新 G1 成功，但新 G2 又出现 Lift 无 Z，见 `logs/F3_diagnose_20260713_120146.log:6-11`。因此 F6 不能等价于完整机构/输出复位。
4. 空载探针证明 `Right=True` 时 Lift 能真实下降，见 `logs/F3_mechanics_A_20260713_065413.log:9-20`；Right 软件互锁基本排除。
5. 官方基线与 debug 场景 45 个 Proxy 的 Rack/Stacker/Conveyors 几何一致，仅四个 SafeguardL 四元数末位序列化差异；无证据是整套设备错位。

## 路线变更

- 任一 `NO START`、recovery、drop 后，禁止继续带载 travel；保存证据并完整退出 Factory I/O。
- F6 只作清货，不作为可信 reset epoch。
- 下一步先离线拆 G4：`place-extend → 视觉门 → place-lower → 支撑确认 → retract`，并增加跨进程 fault lock；完成前不重启现场。
- target 30 仅可作为完整重启+新箱的干净单变量 A/B，不是解决方案。
- 20×20 仍由 AB/算法与自研 3D 完整表达；Factory I/O 只称 54 格代表性物理 I/O/时序验证。

## 未执行

- 未开始 F4 AB OPC UA、F5 联调/CODESYS、F6 主工程回补。
- 未录正式素材。
- 未修改 canonical、报告/PPT、`1_给你看/`、`2_你要操作/`。
- 未提交、未推送；工作树含大量他人既有改动，Claude 必须精确暂存。
- 遵照用户要求，未使用任何 superpowers 系列 skills。

## 终止前离线验证

- `py_compile` PASS。
- F3 控制器/机构探针/任务契约/事件日志/编排器：**64/64 tests PASS**。
- Factory I/O/Python 进程复核：`NO_MATCHING_PROCESS`。
