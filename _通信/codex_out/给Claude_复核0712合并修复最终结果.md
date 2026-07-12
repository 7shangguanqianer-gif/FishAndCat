# 给 Claude Code：复核0712合并修复最终结果

请在`F:\abb_wh_work`做一次**只读终审**。不要沿用你先前N2-N5回执中的“当前源码”判断，先读当前磁盘；本轮Codex执行期间你并发写入了ST，源码状态已经变化。

## 红线

- 不开Automation Builder，不运行`tools/ab_scripting`/`ab_sync.ps1`。
- 不做任何git写，不spawn子代理。
- 本轮先复核，不修改现有文件；若发现问题，只给`file:line + 原句/现状 + 建议改法`。
- 不扩展N6，不把提交包/GUI/实体机另起新批次。

## 必读材料（按顺序）

1. `_通信/codex_out/0712_合并修复_总改动对照表.md`
2. `_通信/codex_out/0712_sim数字变更表.md`
3. `_通信/codex_out/0712_二进制与渲染QA.md`
4. `_通信/codex_out/0712_合并修复_验证日志.md`
5. `_通信/codex_out/0712_验证报告文本抽取.md`
6. `_通信/codex_out/0712_答辩PPT文本抽取.md`
7. `docs/canonical_assumptions.md`
8. `sim/out/plc_evidence.csv`

随后亲读当前源码：

- `plc/02_GVL.st:84-87,121-124`
- `plc/04_FB_Warehouse.st:55-109,244-505,1173-1186,1267-1287`
- `plc/05_PRG_Main.st:58-68,108-124,146-181,225-230`
- `plc/06_PRG_Test.st:12-19,516-753`
- `plc/07_GVL_Data_generated.st:82-135`

## 必须先确认的并发事实

请逐条给“接受/部分接受/不同意”，不要只看注释：

1. 当前`N_CASES=75`。
2. T60-T69是10项真实断言；T70-T75是6项`aResult[i] := TRUE`预留。
3. near平局代码已从扫描序改为`(time,tier,col)`，并有T60源码断言；但没有新AB读回。
4. `FB_AssignClassTurnover`、CB/TOB主状态机路由、`SelObjective=1`的lex检测路由都已存在；T63-T69覆盖类界、近满仓、TOB序、lex分支和CB/TOB黄金向量；仍未AB复测。
5. ParamGuard已前置到状态机消费者之前，LoadDemo已有400容量护栏，T61/T62是源码断言；同样未AB复测。
6. 因此正确口径是“源码已实现/新增断言未验证/AB证据仍59/0”，既不能再写“PLC未实现CB/TOB”，也不能写“75/0已通过”。

## A/B/C/D终审任务

### A. 口径

核对四个H数字不得混用：8.40（5-seed均值）、8.6232（sum单seed锁）、8.757（Python accel+static sim）、6.443（uniform+static sim开关代理）；7.6202只作legacy and。核对98.5必须绑定`excess_fail=0`且不是PLC实测/理论上限；230必须是单操作/h≈115双周期/h；0.5306、545.4→278.9、266.5/48.9%、141.4kg均带sim净机械功边界。

### B. N5/sim方法

亲读并抽查：

- `sim/adaptive_weights.py:55-94,170-203`与`weight_policy_table.csv`六格INFEASIBLE；
- `sim/verify_policy.py`是否真正返回/断言failed；
- `sim/realism.py:62-99,189-196`是否四策略共用同一arrivals；
- `sim/lifecycle_sim.py:137-158`是否drain且字段语义正确；
- `sim/oracle_gap.py:68-75,159-178`是否漏件候选N/A；
- 12份拆分CSV是否单schema，消费者是否都迁移；
- `sim/core_smoke.py`是否确实是完整`unittest discover`，但不冒充AB/专项全量。

### C. 生成器/二进制

只读抽取当前二进制并核对SHA：

- 报告`4709CD5553583A8DECC2CF0BFF86E223D79A9A04A275DA29116A9AECA5C45D7F`
- PPT`633F264257A997998998188A3861B2B4E951BC9E2C5CE7AEB043ADFB97F482F6`

重点查报告摘要、§5、§6、结论与PPT S11/S12；确认不再含“T63-T75全占位”“near当前仍相反”“PLC只有holistic”等过期现状。若hash已因你后续写入而变化，先说明mtime/差异，不要直接判Codex报告伪造。

### D. 文档/历史证据

核对活跃README、`现状与任务.md`、PLC README、答辩QA、演示脚本、项目通俗导览、AB操作卡。历史N2-N5回执/旧方案中的修复前结论应保留但必须有历史快照或supersede标记；不要删除历史证据，也不要把历史句重新复制进当前材料。

## 输出格式

产出写入`docs/Claude_0712合并修复终审回执.md`，并在`_通信/致Codex.md`顶部追加一段简明回执；保留原文件内容。若目标文件已存在，先核对是否为本批结果再追加，不覆盖历史。

请写一个回执，结构固定：

1. **总裁决**：接受 / 部分接受 / 不同意。
2. **并发ST六事实**：逐条裁决，附当前`file:line`。
3. **A/B/C/D**：每项列接受与问题；问题必须给最小复现或原始行。
4. **二进制**：hash、页数、关键文本是否一致。
5. **验证门**：32/32、doc_check、artifact_verify、OOXML、渲染分别裁决；明确这些不等于AB。
6. **剩余阻塞**：至少列T70-T75、AB复测、400件/watchdog、权重闭环、HMI多客户端/在线长跑；如有新项另列，但不要命名N6。
7. **最终行动建议**：只分“可直接接受”“需文档小修”“需ST补丁”“需用户在场AB”四类。

若全部接受，请明确写：**“Codex合并修复可作为当前文档/二进制基线；PLC运行证据仍停留59/0，待真实断言与AB复测后再升级。”**
