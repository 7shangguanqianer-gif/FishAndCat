# 智储优控赛题深度研究资料包：AI 仓位优化、AS/RS 调度与 ABB AC500 落地

生成日期：2026-07-04  
面向对象：Claude Code / 后续算法与工程实现代理  
资料包路径：`C:\Users\86177\Documents\ABB_Warehouse_Slotting_Research_20260704`

## 0. 结论先行

这道赛题不适合把“AI”理解为在 AC500 PLC 上实时跑深度模型。更可落地、更容易得分的路线是：

1. **Python/仿真侧做 AI 与优化**：用 weighted heuristic、GA/NSGA、MILP、GNN-GA、PPO/DRL 或 contextual bandit 生成仓位优先级、策略表和对照实验。
2. **PLC/ST 侧做确定性执行**：在 AC500 ST 中实现候选仓位过滤、查表落位、A* 或简化网格路径规划、状态机、边界判断和统计输出。
3. **Automation Builder/WebVisu 做可视化**：显示 20x20 仓位占用、路径、路径长度、执行时间、总时间、货物属性输入和异常状态。
4. **报告中突出“AI + 工业控制解耦”**：AI 负责离线学习/优化，PLC 负责可解释、安全、实时执行。这样能同时满足算法创新、PLC 可实现性和演示稳定性。

本资料包已经同时执行了两条研究线：

- `parallel-deep-research`：使用 Parallel `ultra-fast` 托管深研，run id 为 `trun_fd7dfa0033114ddbb56289862b216fcc`，原始结果见 `parallel/abb-warehouse-slotting-parallel-api-result.md`。[S01]
- `deep-research` 本地证据链：下载并抽取 5 个 PDF，克隆 6 个参考项目，整理来源、证据和风险，结果见 `sources/*.jsonl` 和本报告。[S02-S15]

## 1. 赛题建模拆解

赛题的核心不是“找一个最漂亮的 AI 模型”，而是一个带工业约束的 storage location assignment problem：

- 输入：货物序号、名称、重量、访问频次、体积。
- 仓位：400 个位置，20x20 布局。
- 预占用：坐标值能被 3 整除的仓位预设占用。建议代码里明确成 `x % 3 == 0 OR y % 3 == 0` 或 `x % 3 == 0 AND y % 3 == 0`，二者结果差异很大，报告中必须说明。
- 承重：底层承重系数 1.0，向上每层递减 0.02。
- 输出：存放位置、到达路径、路径长度、执行时间、全部仓位存储总时间。
- 实现：初赛 ST 代码与仿真报告；决赛 Automation Builder 可视化。

推荐把每个仓位定义为：

```text
SlotID = y * 20 + x
x in [0, 19]
y in [0, 19]
occupied: BOOL
bearing_coeff[y] = 1.0 - 0.02 * y
distance_to_io = abs(x - io_x) + abs(y - io_y)
zone = near / middle / far
```

推荐把每个货物定义为：

```text
ItemID
Weight
Volume
AccessFreq
WeightClass
VolumeClass
PriorityScore
```

可行性过滤：

```text
feasible(item, slot) =
  NOT slot.occupied
  AND item.weight <= base_capacity * bearing_coeff[slot.y]
  AND item.volume <= slot_volume
```

推荐评分函数：

```text
score(item, slot) =
  w1 * normalized_travel_time(slot)
  + w2 * normalized_bearing_penalty(item, slot)
  + w3 * normalized_volume_waste(item, slot)
  - w4 * normalized_access_frequency(item)
  + w5 * zone_balance_penalty(slot)
```

PLC 侧不需要求全局最优；PLC 侧只要在可行候选集中快速选择最优得分或策略表给出的仓位。

## 2. 2025/2026 资料中的有效方向

### 2.1 图建模 + 聚类 + 路径优化

2025 arXiv 论文将产品位置和订单流表示为时间演化图，使用无监督聚类形成紧凑订单区域，并用并行 Bellman-Ford/GPU 加速处理路由。[S02]

对赛题的可用点：

- 把 20x20 仓位作为图节点。
- 把相邻格或堆垛机可达边作为图边。
- 把访问频次、重量、体积、承重余量、占用状态作为节点特征。
- 用聚类形成 `near/middle/far` 或 `A/B/C` 区域。
- 路径规划在 PLC 里不需要 GPU；使用 A* 或预计算距离矩阵即可。

批判点：

- GPU routing 对 400 仓位赛题过度复杂。
- 论文偏大型仓储；竞赛报告可引用其图/聚类思想，不建议复刻 GPU 方案。

### 2.2 DRL 存储分配与补货

2025 RMFS 论文使用 DRL 学习库存货架存储分配与补货策略，目标是降低机器人执行检索/补货活动的平均 cycle time，实验显示相对最佳决策规则最高约 5.4% 改善。[S03]

对赛题的可用点：

- 用 DRL 训练“货物属性 -> 仓位区域”的策略。
- 使用 action masking 屏蔽已占用、承重不足、体积不合规的仓位。
- 把状态空间降维为区域特征，而不是 400 个动作全展开。
- 可以用 SHAP 或简单特征贡献图解释策略，服务报告展示。

批判点：

- DRL 在线推理和训练环境都不适合直接放到 AC500 PLC。
- 竞赛中 DRL 最适合作为 Python 仿真创新项，输出策略表给 ST。

### 2.3 Contextual Bandit 实时调参

2026 Amazon arXiv 论文比较了 LR+GDO、XGBoost+Bayesian Optimization 和 Bayesian Contextual Bandits，用于实时仓库 sorter diversion cost function 调参，强调低延迟、在线学习和 emulator 冷启动。[S04]

对赛题的可用点：

- 不把 bandit 用于路径规划，而用于调节 `w1..w5` 权重。
- 不同负载场景下自动选择偏“距离最短”、偏“承重安全”、偏“空间利用率”的权重组合。
- 作为“智能控制”亮点，比大规模深度 RL 更容易解释。

批判点：

- sorter diversion 不是 slotting，本质是成本权重控制经验迁移。
- 若时间紧，bandit 可只写进扩展方案，不作为初赛主线。

### 2.4 Apriori + GA 的储位/路径联合优化

2025 双区仓库论文将 Apriori 关联规则用于识别订单商品关联，再通过改进遗传算法优化仓储布局与多车拣选路径，并用 Matlab 仿真验证。[S05]

对赛题的可用点：

- 如果赛题没有历史订单，可用访问频次模拟订单关联。
- GA 个体可以编码为 400 个仓位分配序列。
- 适合作为“算法创新”报告主体，因为它比纯打分启发式更有比赛感。

批判点：

- GA 不应在 PLC 上实时运行。
- 必须加 baseline：随机、ABC、最近 I/O、只按重量分层。否则报告说服力不足。

### 2.5 Parallel 托管深研发现但需二次核验的 2025/2026 方向

Parallel 发现了若干较新的候选方向：[S01]

- IEEE 2025：大规模 storage location assignment 的 hierarchical RL / rank-and-assign 方法。[S16]
- ACM 2025：GNN + metaheuristic/GA 的自动化仓储储位优化。[S17]
- MethodsX 2025：warehouse design、storage location assignment、order picking 的 bi-level 优化。[S18]
- Siemens 2025：stacker crane motion profile / double cycle 工程指南。[S19]

这些方向有价值，但需要注意：

- IEEE/ACM 可能有 paywall，本资料包尚未下载原文 PDF。
- Parallel 给出的数值提升不要未经核验就写进正式报告。
- 可先把它们作为“2025/2026 前沿趋势”，再让 Claude Code 后续继续检索/下载。

## 3. 推荐算法路线

### 3.1 最稳主线：分层加权启发式 + A*

这是最容易在 AC500 ST 里落地的方案。

流程：

1. 生成候选仓位集合：过滤占用、承重、体积。
2. 计算 score。
3. 对高频货物优先靠近 I/O。
4. 对重货优先低层。
5. 对大体积货物优先减少空间碎片。
6. 对路径执行 A* 或曼哈顿路径。
7. 输出位置、路径、长度、时间。

优点：

- ST 实现确定性强。
- 评委容易理解。
- 可作为所有 AI 方法的 baseline。

缺点：

- 算法创新性不够，必须叠加 GA/DRL/GNN 或 multi-objective optimizer 才有亮点。

### 3.2 推荐竞赛主线：离线多目标优化 + PLC 查表执行

建议主方案命名为：

```text
H-MOASP: Hybrid Multi-Objective AI Slotting Planner
```

组成：

- Baseline：ABC / weighted scoring。
- Optimizer：NSGA-II/NSGA-III 或 GA。
- Optional AI：GNN/DRL 生成仓位 priority heatmap。
- PLC：读取 `SlotPriority[ItemClass, SlotID]` 或 `BestSlot[ItemID]`。
- Path：A* 或预计算距离矩阵。
- Visualization：WebVisu 20x20 热力图 + 路径线 + 统计面板。

适配评分：

- 模型准确性：多目标函数 + 约束清晰。
- AC500 实现：ST Function Block、数组、状态机、边界判断。
- 创新：AI/GA/DRL/GNN 作为策略生成。
- 可视化：WebVisu/Automation Builder 真实展示。

### 3.3 高风险高亮点：GNN-GA / HRL

适合写在报告的“创新扩展”或“决赛增强”中：

- GNN：每个仓位节点输入 `[x,y,occupied,bearing_coeff,distance_to_io,neighbor_freq]`。
- GA：个体为货物到仓位的映射。
- HRL：上层选择 zone，下层选择 slot。

不建议直接做成唯一主方案：

- 数据不足时 GNN/RL 容易显得装饰化。
- PLC 端无法自然解释神经网络内部决策。
- 比赛现场 demo 更看重稳定可运行。

## 4. AC500 ST 功能块建议

建议 Claude Code 后续按以下 Function Block 拆分：

```text
TYPE T_Item :
STRUCT
    Id : INT;
    Weight : REAL;
    Volume : REAL;
    AccessFreq : REAL;
END_STRUCT
END_TYPE

TYPE T_Slot :
STRUCT
    Id : INT;
    X : INT;
    Y : INT;
    Occupied : BOOL;
    BearingCoeff : REAL;
    Score : REAL;
END_STRUCT
END_TYPE
```

Function Blocks：

```text
FB_InitWarehouse
  - 初始化 20x20 仓位
  - 设置坐标、承重系数、预占用状态

FB_CheckFeasible
  - 输入 item, slot
  - 输出 feasible, reason_code

FB_ScoreSlot
  - 输入 item, slot, weights
  - 输出 score

FB_SelectSlot
  - 遍历 400 个仓位
  - 找最小 score 的 feasible slot

FB_PathPlanAStar
  - 输入 start, target, occupied grid
  - 输出 path array, path length, status

FB_StoreTaskController
  - 状态机：IDLE / VALIDATE / SELECT / PLAN / EXECUTE / DONE / ERROR

FB_Statistics
  - 单次执行时间
  - 累计总时间
  - 成功数、失败数、平均路径长度
```

ST 边界判断必须包括：

- 无可行仓位。
- 重量超过最低层承重。
- 体积超过单仓位容量。
- 起点/终点被占用或不可达。
- 路径数组溢出。
- 访问频次为负数或非法输入。
- 全部仓位已满。

## 5. Automation Builder / WebVisu 可视化建议

ABB WebVisualization 示例明确覆盖可视化配置、Visualization Manager、WebVisu、数组表格、XY Plot、Traces、Trends、移动端可视化等内容。[S06]

建议界面：

- 左侧：20x20 仓位网格。
- 颜色：
  - 灰色：预占用。
  - 蓝色：空闲。
  - 橙色：候选仓位。
  - 绿色：最终仓位。
  - 红色：不可行/错误。
- 顶部：货物输入区。
- 右侧：统计区。
- 底部：路径数组或路径列表。

建议数据绑定：

```text
GridCellColor[0..399]
PathX[0..MAX_PATH]
PathY[0..MAX_PATH]
SelectedSlotID
PathLength
ExecutionTimeMs
TotalStoreTimeMs
ErrorCode
```

如果时间允许，可额外用 Three.js 或外部 Python/HTML 做 3D 可视化；但 AC500/WebVisu 的 2D 网格必须优先完成。

## 6. 开源项目怎么用

| 项目 | 本地路径 | 用途 | 迁移建议 |
|---|---|---|---|
| MetaSimOpt | `projects/MetaSimOpt` | 神经网络 surrogate + simulation optimization，关联 2025 AS/RS order sequencing | 用作“仿真优化”思路，不必整包引入 |
| warehouse-simulator | `projects/warehouse-simulator` | AS/RS crane simulator，默认 A* | 最适合直接改成 20x20 赛题原型 |
| simulator-automatic-warehouse | `projects/simulator-automatic-warehouse` | 自动仓库 digital twin / simulator | 用于仿真工程结构参考 |
| Warehouse-Optimization | `projects/Warehouse-Optimization` | PPO 仓库布局优化 notebook | 用于 RL baseline 和可视化图 |
| picking-route | `projects/picking-route` | 订单批处理、路径优化、Streamlit app | 用于路径统计和报告图表 |
| task-assignment-robotic-warehouse | `projects/task-assignment-robotic-warehouse` | 多机器人仓库环境、A*、碰撞处理 | 适合决赛增强，不适合初赛主线 |

## 7. 下载原文与未下载项

已下载 PDF：

- `papers/2025_arxiv_warehouse_storage_retrieval_clustering_gpu_routing.pdf` [S02]
- `papers/2025_drl_realtime_inventory_rack_rmfs.pdf` [S03]
- `papers/2026_arxiv_bayesian_contextual_bandits_warehouse_sorter.pdf` [S04]
- `papers/2025_optimizing_storage_and_picking_routes_dual_zone_warehouses.pdf` [S05]
- `papers/ABB_AC500_V3_WebVisualization_Demonstration_Example.pdf` [S06]

已抽取文本：

- `sources/pdf_text/*.txt`

未下载或 link-only：

- IEEE 2025 HRL：需要 IEEE 权限或手动下载。[S16]
- ACM 2025 GNN-GA：需要 ACM 权限或手动下载。[S17]
- MethodsX 2025 bi-level：Parallel 找到 PMC 页面，建议下一步优先下载。[S18]
- MDPI 多篇 2025/2026：本机下载时被 403 拒绝，拒绝页保存在 `logs/*_access_denied.html`。[S20]

## 8. 建议验证实验

Claude Code 后续应实现以下实验表：

| 实验 | 方法 | 指标 | 目的 |
|---|---|---|---|
| E0 | 随机仓位 | 总路径、平均路径、失败率 | 最低 baseline |
| E1 | 最近 I/O | 总路径、承重违规数 | 简单启发式 |
| E2 | ABC/访问频次分区 | 路径、空间利用率 | 类存储 baseline |
| E3 | 加权评分 | 路径、承重余量、空间碎片 | 主工程 baseline |
| E4 | GA/NSGA | Pareto 曲线、计算时间 | 算法创新 |
| E5 | PPO/DRL 或 GNN-GA | 训练曲线、测试集表现 | AI 创新 |
| E6 | ST 移植版本 | 扫描周期、边界错误、路径一致性 | AC500 落地 |

推荐不要只报一个“优化后总时间”，必须报：

- 平均路径长度。
- 总存储时间。
- 高访问频次货物平均距离。
- 重货低层命中率。
- 空间利用率。
- 约束违规率。
- ST 运行时间或仿真周期。

## 9. 风险与批判性判断

1. **过度 AI 化是风险**：如果直接声称“PLC 上跑 GNN/RL”，容易被评委质疑实时性、确定性和安全性。
2. **2025/2026 论文不一定更适合落地**：很多新论文解决的是大规模 RMFS、港口堆场、sorter 或仿真优化，和 20x20 单堆垛机场景不完全一致。
3. **Parallel 的部分发现需二次核验**：IEEE/ACM/MethodsX 条目很有价值，但未全部下载，不能未经核验引用精确百分比。
4. **MDPI 被 403 阻止**：本资料包保留了链接与失败记录，不把拒绝页伪装成原文。
5. **坐标整除 3 的解释必须明确**：`AND` 与 `OR` 对预占用数量影响很大，是建模报告容易被挑刺的点。
6. **承重模型要定量**：只写“重货放底层”不够，要写 `bearing_coeff[y] = 1 - 0.02*y` 和 feasible mask。

## 10. 给 Claude Code 的下一步任务提示

建议直接给 Claude Code：

```text
请读取 C:\Users\86177\Documents\ABB_Warehouse_Slotting_Research_20260704\deep_research_report.md 和 sources/sources.jsonl。
基于其中建议，为 ABB 智储优控赛题实现一个 Python 仿真原型：
1. 20x20 仓位建模，支持坐标整除 3 预占用。
2. 货物输入字段：id/name/weight/access_freq/volume。
3. 实现 random、nearest-I/O、ABC、weighted scoring、GA/NSGA 至少 4 个算法。
4. 实现 A* 或确定性路径规划，输出路径、路径长度、执行时间。
5. 生成可视化：仓位热力图、路径图、算法对比图。
6. 生成可移植到 ABB AC500 ST 的数据结构和 Function Block 设计说明。
7. 所有数值指标写入 CSV 和 Markdown 报告。
```

## 11. 最推荐的最终参赛叙事

建议标题：

```text
面向 ABB AC500 的混合智能立体仓储仓位优化：离线 AI 策略生成与 PLC 确定性控制
```

核心卖点：

- 不是单纯 AI，也不是单纯 PLC；是 AI 与工业控制的边界清楚。
- Python/AI 层解决多目标优化与策略生成。
- AC500/ST 层解决实时、安全、可解释执行。
- WebVisu/Automation Builder 层解决可视化和演示。
- 对 2025/2026 前沿有覆盖，但实现不被新论文复杂度绑架。

最适合初赛提交的方案：

```text
Weighted Scoring + GA/NSGA offline optimizer + A* path planner + ST Function Blocks + WebVisu grid
```

最适合决赛增强的方案：

```text
GNN/PPO-generated slot heatmap + OPC UA strategy update + Automation Builder/WebVisu 2D/3D visualization
```
