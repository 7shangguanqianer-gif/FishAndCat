# sim 代码审查 — oracle_gap.py 及依赖链(0711 pm,无人值守)

审查范围(按依赖链顺读,全文件通读):
- `sim/oracle_gap.py`(主体,267 行)
- `sim/instance_gen.py`(被 import 为 `ig`,274 行)
- `sim/strategy_lib.py`(被 import 为 `sl`,276 行)
- `sim/warehouse_sim.py`(被 `ig`/`sl` 共同 import 为 `ws`,557 行,链路终点)
- 交叉核对:`sim/out/instgen_detail.csv`、`instgen_agg.csv`、`detector_rules.md`、`oracle_gap*.csv`、`oracle_gap_summary.txt`、`sim/tests/test_sim.py`、`docs/canonical_assumptions.md`、`docs/技术方向总库_0711.md`、`docs/演示脚本v3_0711.md`

只读审查,未修改任何现有文件;唯一执行过的命令是任务书明确允许的 `python oracle_gap.py`(秒级纯后处理)及只读 `python -c`/独立校验脚本(脚本落在 scratchpad,不在仓库内)。

---

## 可复现性实测(任务书重点要求)

**✓ 实跑复现通过。**

- 命令:`cd F:\abb_wh_work\sim && python oracle_gap.py`
- 得数:检测器[lexicographic] 达 oracle **98.5%**、closed gap **93.3%**;SBS=**awra** 全局 gap 24.69%;最差场景 tiny_light 47.0%;固定策略 tob 因漏件被否决 excess_fail=**397**;holistic 档 heavy_tier 低 **6.6 倍**、energy 低 **32%**——与 `docs/技术方向总库_0711.md`(A1 行)、`docs/演示脚本v3_0711.md`(v4-1 行)头条数字**逐字一致**。
- 重跑前后 4 个输出文件(`oracle_gap.csv` / `oracle_gap_detail.csv` / `oracle_gap_profiles.csv` / `oracle_gap_summary.txt`)SHA256 **逐字节相同**,脚本本身 100% 确定性。
- 进一步核实(超出任务书要求,针对一个可疑信号做的加验):`warehouse_sim.py` 的文件修改时间(2026-07-07 01:22)晚于其上游数据 `out/instgen_detail.csv` 的生成时间(2026-07-06 21:45)约 3.5 小时,存在"代码已改、冻结数据未重跑"的潜在风险。为此用当前代码在内存中重算全部 **2730** 组合(13 场景×30 seed×7 策略)的 exp_t/fail/viol/heavy_tier/energy,与冻结 CSV 逐行比对,**0 处不一致**(容差 1e-6)。结论:当前代码确实仍能完全重现冻结数据,该 mtime 差异未造成实质性 staleness(大概率是同晚新增了未被本实验路径调用的 U2 载重运动学函数/常量)。
- 附加口径自检:全部 2730 次 run 的 `viol`(C8 违规数)总和 = **0**,符合 canonical 口径"任何有效方案必须=0"。

---

## 阻塞

**本次审查未发现阻塞级问题**(不影响当前 98.5%/93.3% 等头条数字的正确性与可复现性;下列均为已核实"当前数据下不触发"的潜在风险或方法论精度问题)。

---

## 建议

### 1. holistic 档在当前 13 场景×30 seed 中与固定策略 awra 完全退化重合,"三档并存"叙事的 holistic 腿实际未被验证
【严重度:建议(报告完整性风险,优先级最高)】
- 文件:`sim/strategy_lib.py:168-171`(`select_strategy` 的 holistic 分支)+ `sim/oracle_gap.py`(det_holistic 全流程)
- 问题描述:holistic 分支逻辑为 `if skew<0.35 and n<=20: return "near"; else: return "awra"`。经对 `out/oracle_gap_detail.csv` 实测统计,**全部 390 个实例 100% 选中 "awra"**,`near` 分支 0 次触发——即使是专为"极小批"设计的 `tiny_light`(n=20)场景,其 skew 最小值也只到 0.377,始终高于 0.35 门槛。因此 `det_holistic` 的 gap 均值(24.685%)与固定策略 `awra` 的 gap 均值(24.685%)**逐场景、逐 seed 完全相同**(bit-for-bit),`检测器[holistic]` 这一档在本实验里不是一个被验证过的"场景自适应检测器",而是"awra"的另一个名字。
- 触发场景:`docs/技术方向总库_0711.md`(A1 行)与 `oracle_gap_summary.txt` 均以"检测器三档并存,目标口径是输入(F18-3),不是单点押注"作为叙事支点;若答辩/评审追问"给我看一个 holistic 与固定 awra 不同的实例",目前拿不出来——这是叙事层面可被当场反驳的缺口,而非代码错误。
- 建议修法(只描述,不改码):
  (a) 在 13 场景族里补一个"极小批+无画像信息"组合(n≤20 且 skew<0.35,例如把 `flat_info` 的窄幅频次分布套到 n=20 批量上)专门激活 near 分支,让 holistic 档的两个分支都被至少一个实例覆盖;或
  (b) 若近期不便扩场景,在报告/演示口径里如实加一句"holistic 档的 near 分支覆盖的是画像无信息量的边界场景,当前 13 场景族未命中,留待决赛展望/额外验证",避免叙事过度延展到未验证的分支。

### 2. oracle_gap.py 新增的 VBS/SBS/gap/closed-gap 逻辑无任何自动化回归测试保护
【严重度:建议】
- 文件:`sim/tests/test_sim.py`(全文件,23 个 `test_*`,无一覆盖 `oracle_gap.py`/`instance_gen.ci95`/`strategy_lib.batch_profile`/`select_strategy`)
- 问题描述:任务书特别点名的"v1 教训"(纯 gap 均值把 tob 错选成 SBS)这次审查逐实例核验**已确认修复且无回归**(excess_fail 全局非负、vbs_fail 在同一实例的全部选择器间严格一致且等于 7 策略最小 fail,390/390 通过)。但这套一票否决词典序逻辑、以及 98.5%/93.3% 头条数字,目前完全没有测试锁定(对照:`test_h_caliber_headline_lock`/`test_legacy_and_h_lock` 已经在为其他头条数字做"回归锁"这件事,但没有覆盖到这个 0711 新增实验)。
- 触发场景:未来任何人调整 `select_strategy` 阈值、`FIXED` 策略列表、或 `warehouse_sim.py` 的评分/可行性逻辑时,没有测试会在"SBS 又被 tob 这类漏件策略骗走"或"98.5%变成别的数字"时报错,只能靠人工重新跑一遍 `oracle_gap.py` 肉眼核对。
- 建议修法:比照现有 `test_h_caliber_headline_lock` 的写法,新增 1-2 个回归测试:①断言 `sbs` 选择结果对"exf>0 的策略"具有一票否决(可用一个构造的假数据表);②对当前 13 场景数据锁定 `det_lexicographic`/`det_speed` 的全局 attain_mean 数值(golden number),阈值内浮动即报警。

### 3. oracle_gap.py 的逐实例 gap 计算对 VBS 分母无零值防护
【严重度:建议(当前数据下未触发,纯后处理脚本,崩溃不会静默出错)】
- 文件:`sim/oracle_gap.py:100`:`gap = (r["exp_t"] - vbs) / vbs * 100.0`
- 问题描述:同一行下方的 `attain`(第 101 行)对 `r["exp_t"]==0` 有显式保护(`if r["exp_t"] > 0 else 0.0`),后面聚合层的 closed gap(第 146-147 行)也对 `gap_sbs==0` 做了保护;唯独这里对 `vbs`(oracle 自身的 exp_t)完全没有保护。若某实例上词典序 oracle 选中的策略最终 0 件入库(`exp_t` 归零,详见下一条 finding 的成因),这一行会直接抛 `ZeroDivisionError`,整个 `oracle_gap.py` 崩溃退出。
- 触发场景:当前 13 场景×30 seed 全部 390 个实例中,7 个固定策略里"入库件数"最少的记录是 20(`tiny_light`,全部 20 件均入库),离 0 很远,故**当前不会触发**。但这条防线是"审查任务书第 5 条边界检查项"明确要求核实的类型,且脚本本身没有对未来新增场景(如后续要加更极端的高压/全非法场景)做任何防护声明。
- 建议修法:比照第 101 行的写法,在第 100 行加一条对称的 `vbs > 0` 判断,`vbs<=0` 时该实例的 gap 记为一个哨兵值(如 `None`/跳过并在 summary 里计数报警),而不是让整个脚本崩溃。

### 4. warehouse_sim.metrics() 的 hot_t/heavy_tier 在"策略 0 件入库"时会先于 oracle_gap.py 崩溃,是上一条 finding 的真正上游成因
【严重度:建议(当前数据下未触发)】
- 文件:`sim/warehouse_sim.py:392-395`
  ```
  hot = sorted(placed, key=lambda pg: -pg[0].freq)[:max(1, len(placed) // 5)]
  hot_t = sum(travel_time(c, t) for _, (c, t) in hot) / len(hot)      # 高频前20%均时
  heavy = sorted(placed, key=lambda pg: -pg[0].weight)[:max(1, len(placed) // 5)]
  heavy_tier = sum(t for _, (_, t) in heavy) / len(heavy)             # 重货前20%均层
  ```
- 问题描述:若某策略在某实例上 `placed` 为空列表(该策略 100% 失败),`hot`/`heavy` 也会是空列表,`len(hot)==0`/`len(heavy)==0`,两处除法都会抛 `ZeroDivisionError`。这个函数是 `instance_gen.py` 生成 `out/instgen_detail.csv` 这一冻结数据源时调用的(`_run()` → `ws.metrics(...)`),比 `oracle_gap.py` 更上游——真出现这种极端场景,连 CSV 都生成不出来,`oracle_gap.py` 根本没机会跑到第 100 行。
- 触发场景:当前数据里每个 (场景, seed, 策略) 组合的最小入库数是 20(`tiny_light` 全数入库,0 失败),离"0 件入库"的边界很远,**当前不会触发**;但这是纯 Python(无 numpy)代码,除零是硬 `raise` 而非静默产出 NaN——好处是过夜脚本会直接失败退出、不会误报虚假数字,坏处是万一未来加一个极端拒收场景(例如把 `illegal_mix` 的非法件比例调到接近 100%),`instance_gen.py` 数分钟的批跑会在中途崩溃,且没有 try/except 兜底,已经算出来的其余场景结果也可能不会落盘。
- 建议修法:在 `metrics()` 里对 `placed` 为空的情况显式短路(`hot_t`/`heavy_tier` 记 0.0 或 `None` 并在返回 dict 里带一个 `all_failed=True` 标记),而不是依赖调用方永远不产生空批次这一隐含假设。

### 5. energy 是未归一化的"批总量",与 exp_t/heavy_tier 两个已归一化的"批均值"混在同一张头条表格里跨场景池化,读者容易把"32% 更省能耗"误读成单件效率
【严重度:建议】
- 文件:`sim/warehouse_sim.py:388-395`(`metrics()` 内部对比):`exp_t` 按频次加权平均(第 388 行,已归一化)、`heavy_tier` 按前 20% 件数平均(第 395 行,已归一化),但 `energy` 是纯求和(第 389 行 `energy = sum(g.weight * t * CELL_H for g, (_, t) in placed)`,**未除以任何计数**);`sim/oracle_gap.py:127-139` 把 13 个场景(n 从 20 到 240 不等)的 390 个实例的 `energy` 原始总量直接等权做简单平均,汇总进 `ene_mean`。
- 问题描述:`energy` 作为"批总量"天然随批量 n 增大而增大;当前 13 场景族里 n=120 的场景占约 62%(8/13),混入 n=20(tiny_light)、n=60(light/heavy_sparse)、n=200/240(dense)后,`ene_mean` 这个池化均值实际上是"这个具体场景规模配比下的平均总能耗",而不是一个跟 `exp_t`/`heavy_tier` 一样可比的单件效率量。holistic vs speed 的对比(17685 vs 25891,"低 32%")是在同一批 390 实例上做的配对比较,方向性结论本身不受影响,但如果报告把"低 32%"和"低 6.6 倍(heavy_tier,已归一化)"并列呈现,容易让读者误以为两者是同类型的"单位效率"指标。
- 触发场景:`oracle_gap_summary.txt` 与 `docs/技术方向总库_0711.md` 已经把"heavy_tier 低 6.6 倍 + energy 低 32%"并列写成"安全溢价账"的两个并排证据。
- 建议修法:在报告文案里把 energy 明确标注为"390 实例总能耗池化均值(未按批量归一化)",或在 `metrics()` 里额外输出一个 `energy_per_item = energy/len(placed)` 供跨场景聚合专用,两个口径分开呈现。

### 6. oracle_gap.py 的"closed gap 与官方公式等价"这一表述,在跨实例聚合后并非严格的代数恒等,只在单实例层面成立
【严重度:建议(不改变已算出的数字,只是引用/论证精度问题)】
- 文件:`sim/oracle_gap.py:27-30`(docstring 引用)+ `146-147`(实际计算)
- 问题描述:docstring 称"gap 空间中 VBS 的 gap=0,故本脚本 `(gap_SBS−gap_sel)/gap_SBS` 等价于 Lindauer et al. 2019 的官方 closed gap 公式 `(SBS−sel)/(SBS−VBS)`"。这个等价关系**只在单个实例层面是平凡成立的**(因为每个实例自己的 `gap_VBS_i` 恒为 0)。但代码实际计算的是**先对 390 个实例的 per-instance 百分比 gap 取均值,再对这两个均值做一次比值**(`gap_sbs = mean_i(gap_SBS_i)`,`closed = (gap_sbs - mean_i(gap_sel_i)) / gap_sbs`),这是"聚合后的 gap 空间比值",而官方原始定义是在**原始性能量纲(如 exp_t 绝对值/PAR10)的均值**上做同样的比值。由于每个实例的 `exp_t_VBS_i`(分母)本身跨实例差异很大(不同场景规模、不同难度),"先归一化再求均值"与"先求均值再归一化"两种聚合顺序在数学上一般不是同一个数(除非所有实例的 `exp_t_VBS_i` 相等,而这里显然不是)。
- 触发场景:目前只是文档措辞层面"言之过满",不影响已输出的 93.3% 这个数字本身的自洽性(它是一个定义明确、可复现的量,只是不完全等同于文献原始公式的逐位复刻)。如果报告里把"closed gap=Lindauer 2019 官方指标"写成没有限定语的强引用,严谨的评审可能会质疑这个等价性推导。
- 建议修法:把 docstring 中"故本脚本…等价"这句改成更保守的表述,例如"本脚本在逐实例百分比 gap 空间中计算,与官方原始性能量纲公式同构但非聚合后逐位等价,是同一框架下的一个自洽变体"。

### 7. `rows_agg` 里 `scenario="ALL"` 这一行的 `gap_ci95` 是跨 13 个异质场景池化后的朴素 t 区间,并非分层抽样意义上的正确置信区间
【严重度:建议】
- 文件:`sim/oracle_gap.py:130-139`(`glob` 全局聚合)+ `sim/instance_gen.py:171-176`(`ci95` 定义,把输入当作一组独立同分布样本)
- 问题描述:`ci95()` 的假设是"传入的一组数值是同一总体的独立重复样本"。`glob[sel]["gap"]` 却是把 13 个均值/方差都明显不同的场景(如 `tiny_light` n=20 vs `dense_240` n=240)、各 30 个 seed,合并成 390 个数直接调用 `ci95`。当场景间差异(between-scenario)明显大于同场景内 30-seed 抽样噪声(within-scenario)时,这样算出来的 `gap_ci95`(如 ALL 行 det_lexicographic 的 1.65±0.458)在统计意义上**混淆了"场景间的系统差异"与"同场景内的随机噪声"**,并不是一个严格的分层置信区间;逐场景那些行(`rows_agg` 里 `scenario!=ALL` 的部分)才是统计上干净的 30-seed CI。
- 触发场景:头条数字引用的正是 ALL 行的 attain_mean/gap_mean(98.5%/1.65% 等),如果报告进一步把 `±0.458` 这个 CI95 半宽当作正式统计推断使用(比如做假设检验或误差棒宣传),需要谨慎。
- 建议修法:文案上把 ALL 行的 CI 标注为"跨场景池化的描述性区间,非分层抽样 CI",或改用分层公式(先算 13 个场景各自的 mean/var,再按场景数加权合并)重新给出一个统计上更严谨的全局区间。

---

## 风格

### 1. "检测器逐场景推荐核查(vs 0706 标定表 detector_rules.md)"一节只打印、不比对
【严重度:风格】
- 文件:`sim/oracle_gap.py:208-211`
- 问题描述:该小节标题写的是"…核查(lexicographic 档 vs 0706 标定表 detector_rules.md)",听起来像是自动交叉核验,但代码实际只是把 `det_lexicographic` 每个场景的推荐策略打印出来,并没有真的读取 `out/detector_rules.md` 并做逐行比对。本次审查手工核对了两者(结果一致:两份材料在 13 个场景上的推荐策略逐一相同),但这个"一致"目前完全依赖人工目视,脚本本身不会在未来两者出现分歧时报警。
- 建议修法:把 `out/detector_rules.md` 解析成 `{scenario: strat}` 字典,和 `det_lexicographic` 的 picks 做一次程序化 diff,不一致时在 summary 里显式标红,而不是仅并排打印。

---

## 正向确认清单(全部逐条核实,供交叉核对)

- **随机源全链路 grep 核查**:对 `oracle_gap.py`/`instance_gen.py`/`strategy_lib.py`/`warehouse_sim.py` 四个文件搜索所有 `random.`/`shuffle`/`sample`/`choice`/`triangular`/`uniform`/`paretovariate` 调用点,**无一例外**全部挂在显式 `random.Random(seed...)` 构造的实例上(`seed`、`seed+1`、`seed+31` 三种偏移,含义各自在注释里写明),不存在裸调用模块级 `random.xxx()` 的情况——同批实验"同数据同负载"的前提成立。
- **VBS 词典序一票否决逐实例核验**:对全部 390 个实例编程核验,`excess_fail` 无一为负,且 VBS 对应的 `fail` 值在同一实例的全部 10 个选择器(3 档检测器 + 7 固定策略)间严格一致,并等于 7 个固定策略里的最小 `fail`——`min(FIXED, key=lambda s: (fail, exp_t))` 的词典序实现没有漏洞,v1 那种"纯 gap 均值把漏件策略选成 SBS"的问题**没有回归**(tob 全局 gap 为 -3.09%,即"看似更快"但因 `excess_fail=397` 被正确排除出 SBS 候选)。
- **约束违规不变量**:全部 2730 次 run(13 场景×30 seed×7 策略)的 `viol` 求和 = 0,符合 canonical C8"任何有效方案必须=0"。
- **整数除法审查**:`strategy_lib.batch_profile` 的 `n // 5` 与 `warehouse_sim.metrics` 的 `len(placed) // 5` 都是"前 20% 件数"的故意整数化定义,两处口径一致,非疏漏。
- **CSV/summary/文档同源性**:`out/oracle_gap.csv`(ALL 行)、`out/oracle_gap_summary.txt`、`docs/技术方向总库_0711.md`、`docs/演示脚本v3_0711.md` 四处引用的 98.5%/93.3%/397/6.6 倍/32% 手工核对**逐一吻合**;`out/detector_rules.md`(标定表,文件 mtime 早于当前 instgen 数据约 4 小时)与当前 `instgen_agg.csv` 的对应数值(exp_t_mean/ci95/heavy_tier_mean)逐条核对**完全相同**,判定为同一套确定性代码先后两次运行的结果,非过期数据。
- **`illegal_mix` 结构性护栏**:6 件非法货(3 超重>100kg、3 超容积>1.0)在 `feasible()` 判据下对**任何**策略/任何 tier 都恒不可行,"fail 恒=非法件数"是结构保证而非经验巧合。
