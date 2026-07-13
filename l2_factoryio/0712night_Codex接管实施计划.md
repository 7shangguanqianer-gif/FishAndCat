# Factory I/O 第二轮挂机接管实施计划

> **执行者说明：** 以 `docs/overnight2-report_0712night.md` 为唯一账本；从首个未完成项 F3 继续，不重做 F0-F2，不重新论证已拍板事项。

**目标：** 先完成并实证 Python 直控 Automated Warehouse 的单箱/三箱入库，再按账本条件推进 AB OPC UA、联调与主工程回补；所有结论都以可重放日志、截图/录屏和测试结果为准。

**架构：** 主线独占 Factory I/O GUI、127.0.0.1:502、AB GUI、提交和账本。Terra 只承担与现场状态解耦的只读复核或独立静态检查，避免并发写同一工作树和争用仿真端口。

**技术栈：** Factory I/O 2.5.10 Ultimate、pymodbus/Modbus TCP、Python、Automation Builder 2.9 / OPC UA、PowerShell、Git。

---

## 0. 接管冻结与边界

**允许写入：** `l2_factoryio/`、`docs/overnight2-report_0712night.md`；后续只有 F6 获准且绿灯时才按账本回补主工程。

**禁止触碰：** `1_给你看/`、`2_你要操作/`、账号密码；canonical 只写提案；不把当前工作树中其他历史改动带入提交。

- [x] 核对 HEAD/远端：`32c46c8`，F2 和 F3 实验前 v1 已推送。
- [x] 核对未提交现场：`f3_stacker_control.py` 有 v2 实验改动；`rdrag.ps1` 未跟踪。
- [x] 核对运行现场：Factory I/O PID 127296，`127.0.0.1:502` 可读，Input14=True。
- [x] 冻结失败快照：At Load=False、At Middle=True、Lift=True、Target=19；取箱动作后箱仍占据载入位。
- [ ] 保存现场截图和结构化 I/O 快照；移除或明确排除与核心控制无关的 `rdrag.ps1`。

## 1. F3 单动作诊断与最小修复

**文件：**
- 修改：`l2_factoryio/f3_stacker_control.py`
- 新建：`l2_factoryio/test_f3_stacker_control.py`
- 新建：`l2_factoryio/f3_experiment_0712.md`
- 证据：`l2_factoryio/img/F3_*`、`l2_factoryio/logs/F3_*`

- [ ] 先读取官方 Automated Warehouse Station 动作定义，逐项校正叉向、Lift 电平、Target Position 和传感器语义。
- [ ] 增加只读 `snapshot` 与逐动作日志；每个命令记录输入、线圈、目标寄存器和耗时。
- [ ] 把安全停机与动作时序做成可注入/可单测的最小结构；先写失败测试，再改代码。
- [ ] 复位场景后依次验证：feed、goto rest、伸叉、Lift、回中；每次只改变一个变量。
- [ ] 单箱入库成功后再跑 3 箱；任何红灯先全停并保留日志，不用相机视角替代 I/O 证据。
- [ ] 运行 `py_compile`、单元测试和只读 smoke；对准确文件执行 `git add`，提交并推送。
- [ ] 更新唯一账本 F3 状态、命令、证据、失败尝试与口径“Python 直控技术预演”。

## 2. F4 AB 仿真 PLC OPC UA 3b

**前置：** F3 已绿；先独立提交并确保 Factory I/O 输出安全清零。GUI 操作由主线独占。

**文件：**
- 新建：`l2_factoryio/f4_opcua_0712.md`
- 证据：`l2_factoryio/img/F4_*`、`l2_factoryio/logs/F4_*`

- [ ] 备份 AB 工程/相关配置，记录版本与当前进程。
- [ ] 在 AB 仿真 PLC 中试开 OPC UA server，记录 endpoint、证书/匿名策略和变量可见性。
- [ ] 用独立 OPC UA client 做最小读写，不先接 Factory I/O。
- [ ] 成败均落档；失败时只转 F5 既定兜底，不修改 canonical。
- [ ] 精确提交并推送 F4 证据与账本更新。

## 3. F5 联调或 CODESYS 兜底

- [ ] OPC UA 成功：Factory I/O 切 OPC Client DA/UA，先一输入一输出，再全点表。
- [ ] OPC UA 失败：按账本转 CODESYS/Modbus 兜底，保留 AB 失败证据，不包装为 AB 闭环。
- [ ] 输出边界明确的联调记录、点表、复现命令和截图；精确提交并推送。

## 4. F6 主工程回补门

- [ ] 只有 F5 绿灯才进入：备份 → 最小合入 → `75/0` 全量复验 → 精确提交并推送。
- [ ] 任一回归红灯立即回滚本步骤自身改动；不覆盖工作树中既有用户改动。
- [ ] canonical 只形成提案，不直接修改权威数字。

## 5. F7/F8 自审与扩展

- [ ] F7：主线完成现场验收；Terra 对已落盘代码/日志做独立静态复核，不操作 GUI、不写共享文件。
- [ ] F8：仅在 F0-F7 队列清空后，从全作品扩展非文档线任务；新决策记待拍板，不停车。
- [ ] 每小时把反思直接追加到账本，不中断执行；自动续跑只使用平台提供的长期任务机制，不用无监督键鼠脚本代替确认。

## 6. 提交纪律

- [ ] 每次提交前执行 `git status --short` 和 `git diff --cached --name-only`。
- [ ] 禁止 `git add -A`、`git add .`；只暂存本阶段明确文件。
- [ ] 提交后运行对应最小复验再 push；记录 commit hash 到唯一账本。
- [ ] 不提交 `rdrag.ps1`，除非它成为可复现测试的必要组成且通过安全审查。
