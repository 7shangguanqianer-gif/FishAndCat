# tools/visu_gen — 画面程序化生成器与探针档案(0710,Codex 实战产出收编)

> 来源:`F:\abb_wh_spike\visu_native_20260710_1225\`(Codex 独立实验目录,一次性,故收编存档)。
> 战果:**批次 B/C 全部画面元素(VisuMain 477 + VisuStats 113)由脚本生成**,编译 0 错,
> PRG_Test 45/0,ST 文本对象零改动审计通过。交接报告=`docs/evidence_0710/`。

## 核心能力发现(改写项目自动化能力边界)

**ABB AB 2.9 内嵌的 CODESYS 已支持 `ScriptVisualization` 官方脚本 API**——可创建
Visualization、添加元素、设置属性与输入动作。三方证据链:
1. 网络考古(0710 枪1):2014-2024 官方零支持,唯一变数=CODESYS V3.5 SP21(2025-03)
   发布说明 "Scripting: Automated creation and design of visualizations using Python scripts";
2. **Codex 实战(0710)**:用该 API 在正式工程生成 590 个元素并通过全部验收——SP21 能力
   在 AB 2.9 存在的一手证明;
3. 0708 探针 `create_visualization=False` 不矛盾:当时探的是旧猜想名,真实入口是 SP21 新命名空间。

## 文件清单(按用途)

- `build_visu_pages_ascii.py` — **最终生成器**(ASCII 标签正式版;`build_visu_pages.py`/
  `_formal.py` 为中间版本)
- `audit_formal_visu.py` — 结构审计(元素计数/绑定统计/ST 文本对象逐对比较)
- `probe_visuelem_api.py`/`probe_visual_interface.py`/`probe_visu_commands.py`/
  `probe_input_action_api.py`/`script_api_smoke.py`/`script_api_binding_smoke.py`
  — ScriptVisualization API 能力探针(方法签名/输入动作/绑定烟测)
- `probe_utf8*/read_utf8_option.py/set_utf8_spike.py` — UTF8 编译选项探索
  (结论:脚本设置不持久,故正式 HMI 用 ASCII 标签)
- `convert_alarm_sample.py`/`scan_alarm_sample_simple.py` — AlarmTableExample 报警对象
  探索(结论:报警配置无公开脚本 API,批次 D 留 GUI)
- 其余 probe_*/headless_ping.py — 无头进程管理与反射探针

## 运行约束(Codex 教训,违反=事故)

1. 跑任何脚本前确认 **无 AutomationBuilder.exe 进程**(无头进程可能在 PowerShell 返回后仍活着);
2. 严禁双实例(锁工程/触发恢复提示);
3. 生成类脚本**先在副本工程上验证**再碰正式工程(spike 流程);
4. 正式工程回滚点:`plc/AB_Project/ABB_WH.before_visu_pages_20260710_140823.project.bak`
   (SHA256 185D6D5E…,交接报告 §5)。
5. **交付定义(0711 定案,输入失效攻坚战果)**:脚本建的任何**带输入动作**的元素,
   交付=**生成 → GUI 洗(逐元素 Input configuration→Configure...→OK 重存)→ 在线长跑验证**
   三段全过;"生成完编译过"不算完。机理与洗单=`docs/画面输入失效攻坚_0711.md` §3/§7、
   经验文档 §七(computer use 可代洗,21 处/约 40 分钟)。
