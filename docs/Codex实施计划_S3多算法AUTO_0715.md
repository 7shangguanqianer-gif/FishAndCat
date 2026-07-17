# S3 多算法 AUTO 实施计划（0715）

> 设计真相：`docs/Codex设计_S3多算法AUTO与货物实验补齐_0715.md`（critic 已裁决 Go-for-implementation）。  
> 候选页面：`l4_showcase/src/样张_S3_三方向候选.html`；用户确认前不覆盖 `样张_S3定稿.html`。  
> 纪律：不开 AB、不跑 `tools/ab_scripting`、不做 git 写；保留脏工作区，不改无关文件。  
> 监督：主 agent 执行；`gpt-5.6-sol` critic 在每个里程碑只读复核测试、口径和截图。

## 修改前基线

- `python sim/core_smoke.py`：32/32 PASS。
- `python l4_showcase/tools/test_s3_tier3_trace.py`：3/3 PASS，但只覆盖单 AWRA-LS→score trace。
- `node --check l4_showcase/src/s3_ac_runtime.js`：PASS。
- 基线绿不代表多算法、AUTO、CB/TOB 动态链、扫码退出或新实验已实现。

## 共用任务门

每个任务按以下顺序：

1. 在测试账本写入任务目标、输入、预期失败与不改范围。
2. 先写最小失败测试并确认它因目标能力缺失而失败。
3. 实现最小闭环，不顺手改 canonical 或全项目默认值。
4. 运行本任务测试 + `core_smoke` 中最小相关子集。
5. 把输出、hash、负结果写入 `_通信/codex_out/0715_S3多算法AUTO_测试账本.md`。
6. 将变更与测试交给独立 critic；阻断未关不得进下一依赖任务。

同一任务连续三次出现同类失败时，保存复现证据并暂停该分支，转做不依赖它的任务。

## 固定 Task 1~9

### Task 1：冻结规格、基线和文件责任

**文件**

- 已创建：`docs/Codex设计_S3多算法AUTO与货物实验补齐_0715.md`
- 创建：`_通信/codex_out/0715_S3多算法AUTO_测试账本.md`
- 更新：`l4_showcase/implementation-notes.md`

**验收**

- Go-for-implementation 回执落账。
- 记录当前候选 HTML/JS/trace SHA256、Python/Node 版本、三项基线命令。
- 明确 `core_smoke` 会再生 oracle-gap 输出，但当前再生后 git diff 为空。

### Task 2：版本化货物场景注册表与画像生成器

**文件**

- 创建：`sim/scenarios/cargo_dynamic_v1.json`
- 创建：`sim/cargo_scenarios.py`
- 创建：`sim/tests/test_cargo_scenarios.py`

**接口**

- `load_registry(version="cargo_dynamic_v1")`
- `build_initial_goods(scenario_id, seed)`
- `build_inbound_goods(scenario_id, seed, cycles)`
- `scenario_profile(goods)`
- `scenario_manifest(scenario_id)`

**测试门**

- E01~E18 全部可生成且 gid 唯一。
- E10/E11/E12 保持属性边际多重集，实测 Spearman 达阈值。
- E13 全部合法且接近重量/体积边界。
- E14 只在 inbound 注入 6 个非法货，初始库存全合法。
- E15 三个降级字段存在且不可被省略。
- 注册表字段、seed 段和 source hash 确定性一致。

### Task 3：参数化 workload、非法拒收与漂移契约

**文件**

- 修改：`sim/mixed_ops.py`
- 创建：`sim/tests/test_scenario_workload.py`

**接口**

- 保留 `build_workload(init_goods,n_cycles,seed)` 原行为和 golden 测试。
- 新增 `build_scenario_workload(initial_goods,inbound_goods,scenario,seed)`，返回周期记录、请求、dispatch mask、E18 advisory。

**测试门**

- 同场景/seed 重跑逐 gid 相同。
- 所有策略复用同一 workload hash。
- E14 100 周期=94 有效双命令+6 `REJECT_NO_DISPATCH`；非法货不进请求池，终局库存计数守恒。
- E18 三段 inbound 分布正确；周期 33/66 只写 next-batch advisory，不改变 active strategy。

### Task 4：把 `realism.run_tier3` 升级为唯一事件引擎

**文件**

- 修改：`sim/realism.py`
- 创建：`sim/tests/test_tier3_event_engine.py`

**接口**

- 保持旧 `run_tier3(...)` 返回指标兼容。
- 增加可选 `workload/events/fault_intervals/event_sink` 参数；实验和 trace exporter 共用同一循环。
- 预生成 busy-time 故障间隔序列并输出 hash。

**测试门**

- 旧四策略 seed=2026 指标逐值等于当前 baseline。
- 不开 event sink 时无额外输出；开 sink 时每周期含连续 phase、库存前后快照、gid owner 事件。
- `P50=resp[n//2]`、`P95=resp[min(n-1,int(n*.95))]` 回归锁。
- E14 拒收周期不进入响应样本，字段固定为 100/94/6/94。

### Task 5：七策略链与 AUTO 初始路由

**文件**

- 修改：`sim/mixed_ops.py`
- 修改：`sim/realism.py`
- 修改：`sim/strategy_lib.py`（只加显式辅助接口/理由，不改全局默认）
- 创建：`sim/tests/test_auto_strategy_dynamic.py`

**接口与链**

- `random→random / seq→seq / near→near / score→score / awra→score / cb→score / tob→score`。
- `AUTO` 显式调用 `objective="lexicographic"`，run 起点只选择一次。
- 输出 profile、picked、alt、阈值理由和 batch_known。

**测试门**

- S0 所有 n/density/skew/目标边界逐项通过。
- 只改 `w_mean/w_heavy` 时 v1 pick 不变，UI 不得声称重量参与分支。
- CB/TOB 初始布局与 `instance_gen` 同源；后续在线入库确为 score。
- AUTO 与 `select_strategy(...,objective="lexicographic")` 逐格一致。

### Task 6：风险矩阵 runner 与 smoke

**文件**

- 创建：`sim/cargo_dynamic_matrix.py`
- 创建：`sim/tests/test_cargo_dynamic_matrix.py`
- 输出：`sim/out/cargo_dynamic_matrix_{detail,agg,params}.csv`

**能力**

- 支持 `--stage s0|s1|s2|s3 --scenarios ... --seeds N --smoke`。
- 输出 workload/arrivals/noise/fault-stream hash、可行性、P50/P95、regret、CI、压力标签。
- S1 只用 2026..2035；S2/S3 使用规格中的独立 seed 段。

**测试门**

- smoke：E02/E10/E14/E15/E18 × 1 seed × 8 模式。
- 同一 `(scenario,seed)` 八模式四 hash 一致。
- AUTO/无 oracle 不可行时 regret=NA，不进入均值。
- E15 CSV 与标题含扩展压力降级字段。

### Task 7：45 trace + manifest 生成器

**文件**

- 重构：`l4_showcase/tools/generate_s3_tier3_trace.py`
- 更新：`l4_showcase/tools/test_s3_tier3_trace.py`
- 创建：`l4_showcase/out/s3_trace_manifest.js`
- 生成：`l4_showcase/out/s3_traces/*.js`（45 组合）

**测试门**

- exporter 只消费 Task 4 事件，不复制业务循环。
- 45 条目存在、schema 一致、payload hash 正确、单 trace ≤800 KB、index ≤100 KB。
- 所有权顺序完整；step 7 内含 OUTFEED→SCANNED→EXIT_MASK→CONSUMED。
- 单 trace 统计只作代表性回放；多 seed 数字指向聚合 CSV。

### Task 8：file:// trace store、3-cache 和错误恢复

**文件**

- 创建：`l4_showcase/src/s3_trace_store.js`
- 创建：`l4_showcase/tools/test_s3_trace_store.mjs`

**能力**

- 动态注入本地 `<script>`，不使用 fetch/CDN。
- 最多缓存 3 个 trace；淘汰时删除全局注册项和重资源引用。
- 加载失败显示算法/Tier/画像和重试按钮。

**测试门**

- 45 组合逐一加载、hash/schema 校验。
- 第 4 条加载触发 LRU 淘汰；无未处理 Promise/error。
- 缺文件、坏 hash、坏 schema 三类错误可见且可恢复。

### Task 9：收敛为一个页面状态机

**文件**

- 重构：`l4_showcase/src/样张_S3_三方向候选.html`
- 重写：`l4_showcase/src/s3_ac_runtime.js`
- 创建：`l4_showcase/tools/test_s3_runtime_contract.mjs`

**能力**

- 删除旧“三维/过程数据”双页和旧内联动画循环。
- 只保留一个 requestAnimationFrame、一个 pause、一个 QA 状态源。
- 五模式、三 Tier、三画像切换保持 `(seed,cycle,phase,progress)` 检查点。
- 左栏和 3D 的 gid、owner、slot、queue 全部同源。

**测试门**

- DOM 中无旧 modebar/dataView/第二视角死件。
- 算法切换不回到周期 0，不复用上一策略库存。
- console error=0；暂停/循环 20 次无重复 gid/mesh 增长。

## 自适应 Task 10~12

### Task 10：左栏密度、AUTO 理由与 tooltip 深化

根据 Task 6 的真实字段决定最终模块高度和默认展开层，不提前硬编码不存在的指标。

**固定验收**

- 左栏首屏无大片空白；五秒内可识别模式、场景、当前作业和下一动作。
- 候选评分与系统 KPI 分区。
- 所有 hover 同时支持键盘 focus，含定义、公式、样本、方向、SIM/source。
- AUTO 选中 CB/TOB 时显示“路由额外策略”，不伪装成第五个手动算法。

### Task 11：3D 物理、出库设备、镜头、灯光和颜色

根据真实阶段截图迭代，不凭包围盒一次拍板。

**固定验收**

- 货架/I-O/堆垛机/短出口线/扫码门/退出帘同框。
- gid 在扫码并通过退出帘后才隐藏；载货台交接后为空。
- 桅杆与载台 X 恒等，货叉不带回托板，货物不掉落/穿模。
- 133 个斜纹位在 3D 与规则图均可辨。
- 活动物蓝系底色 + 琥珀轮廓，和灰货架有足够对比；红色语义受控。
- 目标 DOM 标签清晰、不出界、不遮机构。

### Task 12：多视口双重 QA、S1/S2/S3 与视频

**顺序**

1. 先完成 1280×720、1366×768、1600×900、1920×1080 阶段截图和 manifest。
2. 主 agent 目检后交 critic 独立目检；任一阻断继续迭代 Task 10/11。
3. 页面视觉由用户确认后才跑完整 S1；按预注册规则跑独立 S2/S3。
4. 只有候选页面和实验口径均通过后，才用同一固定镜头制作视频；不引入额外视角。

**最终产物**

- 当前候选页面与本地依赖。
- 实验 CSV/manifest/负结果说明。
- 多阶段截图与双重 QA 回执。
- 用户确认后的视频及帧抽检。
- `_通信/codex_out/0715_S3多算法AUTO_完成回执.md`。

## 计划自审

- 设计规格 §1~§11 均至少映射到一个 Task。
- 未安排修改 `样张_S3定稿.html`、AB、git、用户文档或 canonical。
- 每项都有可执行测试门，不使用“以后补”“待实现”占位。
- 三个自适应任务只允许根据真实实验/截图调整画面参数，不允许改变物理或统计口径。
