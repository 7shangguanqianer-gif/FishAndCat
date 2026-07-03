# 智储优控：基于AI算法及智能控制的立体仓储仓位优化 研究资料包

版本：2026-07-03  
用途：可直接作为 Claude Code / ClaudeCode 的补充上下文、实现依据和参考文献资料。  
检索口径：优先收集 2025-07-03 至 2026-07-03 的最新研究；对 2025 年上半年或更早但高度相关的论文/项目，单独放在“补充参考”，避免误标为最近一年成果。

---

## 0. 给 Claude Code 的使用说明

把本文件放入项目根目录，例如 `docs/research_brief.md`，然后让 Claude Code 先阅读本文件，再实现 Python 仿真、报告图表、ABB AC500 ST 代码骨架和可视化变量结构。建议给 Claude Code 的首条任务是：

```text
请先阅读 docs/research_brief.md。基于其中的 AWRA-LS 算法方案，实现一个 20x20 立体仓储仓位优化仿真项目：
1) 支持输入货物 id/name/weight/frequency/volume；
2) 根据赛题规则初始化 400 个仓位、承重系数和预占用仓位；
3) 实现 Random、Nearest、Rule-based、AWRA-LS 四种策略；
4) 输出每件货物的存放位置、路径、路径长度、执行时间和总统计；
5) 生成可用于报告的 CSV、图表和 ST 语言功能块骨架。
请保持工程结构清晰，并为每个函数写测试。
```

---

## 1. 赛题关键约束提炼

赛题名称：智储优控——基于 AI 算法及智能控制的立体仓储仓位优化。

核心任务不是“找到一个空仓位”，而是同时处理以下问题：

- 仓位分配：考虑货物重量、访问频次、体积、仓位承重、仓位占用状态。
- 路径规划：从起点到目标仓位的最优路径、路径长度和执行时间。
- 多目标优化：存取效率、空间利用率、设备损耗、承重安全、准确性。
- PLC 落地：基于 ABB AC500 PLC，用 ST 语言实现，关键算法封装成功能块。
- 可视化仿真：决赛要求在 Automation Builder / CODESYS 可视化中展示 20x20 仓位布局、占用状态、路径和统计信息。

决赛规定场景：

- 400 个仓位，布局为 20x20。
- 每个仓位长宽高相同。
- 最底层承重能力系数为 1.0，从底层到顶层承重能力系数递减 0.02。
- 坐标值能被 3 整除的仓位预设已占用。
- 从 (0,0) 开始连续存放。
- 可通过交互界面输入货物属性：序号、名称、重量、访问频次、体积。
- 输出存放位置、路径规划、路径长度、执行时间、完成全部仓位存储总时间。

关于“坐标值能被 3 整除”的工程歧义：建议把预占用规则封装成函数，不写死到主算法里。可选约定：

```text
方案 A：x % 3 == 0 且 y % 3 == 0 的仓位预占用。20x20 中有 7*7 = 49 个预占用仓位。
方案 B：按一维编号 index = y*20 + x，index % 3 == 0 的仓位预占用。20x20 中约有 134 个预占用仓位。
```

报告中应明确采用哪一个约定；代码中用 `IsPresetOccupied(x,y)` 封装，方便赛前根据老师解释切换。

---

## 2. 检索结论：最适合参赛的技术路线

近一年仓储优化研究的趋势是：仓位分配 SLAP 不再孤立求解，而是逐步与路径规划、设备调度、离散事件仿真、数字孪生、强化学习和启发式优化耦合。

但是，ABB AC500 PLC 的优势在实时控制、确定性逻辑、可靠 I/O 和工程稳定性，而不是在 PLC 上训练深度神经网络。因此推荐的参赛路线是：

```text
离线 AI / 仿真优化权重 + 在线 PLC 可解释评分决策 + 局部搜索修正 + 可视化数字孪生验证
```

也就是：

- Python 端：用于仿真、对比实验、参数寻优、图表生成。
- AI 角色：用强化学习/遗传算法/网格搜索/贝叶斯优化等方式离线寻找评分函数权重，或用于启发式排序策略设计。
- PLC 端：运行确定性的可解释算法，例如加权评分、可行性判断、路径时间计算、局部交换优化。
- 可视化端：展示仓位矩阵、路径、统计指标、异常边界判断。

推荐算法名称：

```text
AWRA-LS: Adaptive Weighted Rank-Assign with Local Search
中文名：自适应加权排序分配与局部搜索仓位优化算法
```

这个方案兼顾评分标准：模型准确性、PLC 实现、算法创新、可视化展示和演讲表达。

---

## 3. 最新一年高价值研究成果

### R1. Data-driven reinforcement learning-based optimization of shared warehouse storage locations

- 类型：论文，Computers & Industrial Engineering，Volume 206，August 2025，Article 111195。
- 作者：Zeyu Yang, Peihan Wen。
- DOI：10.1016/j.cie.2025.111195。
- 主要方法：数据同步 + 离线/实时指标计算 + DQN/PPO 强化学习 + 层级策略 + 动作掩码。
- 关键价值：该论文把共享仓储仓位配置建成数据驱动强化学习问题，通过多时间粒度指标反映 SKU 需求动态，并设计奖励机制优化拣选效率和成本。
- 对本赛题的启发：可以把访问频次、路径时间、重量风险、体积利用率和设备损耗组合成 reward/score；训练可放在 Python 仿真中，PLC 只运行训练后的权重和规则。
- 建议引用场景：报告中的“AI 算法选型依据”“强化学习与仓位分配关系”“动态访问频次建模”。
- 来源：ScienceDirect，https://www.sciencedirect.com/science/article/abs/pii/S0360835225003419

### R2. Large-Scale Storage Location Assignment via Hierarchical Reinforcement Learning: A Rank and Assign Approach

- 类型：论文，IEEE Transactions on Knowledge and Data Engineering，2025，Volume 37，Issue 11，Pages 6506-6520。
- 作者：Weihang Pan, Minghao Chen, Binbin Lin, Yafei Wang, Xinkui Zhao, Xiaofei He, Jieping Ye。
- 主要方法：Hierarchical Reinforcement Learning；将大规模仓位分配拆成 Ranking Agent 和 Assigning Agents。
- 核心思想：先对待分配对象排序，降低随机到达顺序的不确定性；再按 block/slot 两级分配，降低大规模离散动作空间维度；通过即时奖励缓解稀疏奖励。
- 对本赛题的启发：直接转化为参赛算法的“先排序，再分配”架构。先按高频、重量、体积计算优先级，再逐个扫描仓位选择最低成本位置。
- 建议引用场景：报告中的“Rank-Assign 算法创新点”“为什么不是简单贪心”。
- 来源：IEEE，https://ieeexplore.ieee.org/document/11159170/；IEEE Computer Society，https://www.computer.org/csdl/journal/tk/2025/11/11159170/29Vcfs2rAEU

### R3. Integrated Optimization Framework for AS/RS: Coupling Storage Allocation, Collaborative Scheduling, and Path Planning via Hybrid Meta-Heuristics

- 类型：论文，Applied Sciences，2026，16(8):3757。
- 作者：Dingnan Zhang, Boyang Liu, Enqi Yue, Dongsheng Wu。
- DOI：10.3390/app16083757。
- 主要方法：TVNS 用于仓位分配；PT-AHA 用于堆垛机/叉车协同调度；SA-WOA 用于堆垛机路径规划。
- 关键价值：这篇论文明确指出 AS/RS 效率受 storage allocation、equipment scheduling、path planning 三者耦合影响。它把路径规划建成受约束 TSP，把仓位分配做成多目标模型。
- 对本赛题的启发：报告中不要只写“仓位优化”，应写“仓位优化 + 路径规划 + 设备损耗 + 总时间统计”的集成框架。
- 可借鉴指标：效率、货架稳定性、物品相关性、路径长度、完成时间、故障恢复。
- 来源：MDPI，https://www.mdpi.com/2076-3417/16/8/3757

### R4. Deep reinforcement learning for dynamic order picking in warehouse operations

- 类型：论文，Computers & Operations Research，Volume 182，October 2025，Article 107112。
- 作者：Sasan Mahmoudinazlou, Abhay Sobhanan, Hadi Charkhgard, Ali Eshragh, George Dunn。
- DOI：10.1016/j.cor.2025.107112。
- 主要方法：将动态拣选建成 MDP，用深度强化学习处理订单动态到达和拣选路径决策。
- 对本赛题的启发：可把赛题建模成 MDP：状态为仓位占用和货物属性，动作为选择仓位/路径，奖励为时间、距离、设备损耗和承重惩罚。
- 注意：本赛题更适合借鉴 MDP 表达，而不是在 PLC 上部署 DRL 模型。
- 来源：ScienceDirect，https://www.sciencedirect.com/science/article/pii/S0305054825001406；代码资源，https://github.com/Sasanm88/DRL-Order-Picking

### R5. Warehouse storage and retrieval optimization via clustering, dynamical systems modeling, and GPU-accelerated routing

- 类型：论文，Applied Mathematical Modelling，Volume 154，2025，Article 116700；早期版本为 arXiv:2504.20655。
- 作者：Magnus Bengtsson, Jens Wittsten, Jonas Waidringer。
- DOI：10.1016/j.apm.2025.116700。
- 主要方法：把货位和订单流建成随时间演化的图；用无监督聚类形成紧凑订单区域；用 GPU 加速 Bellman-Ford 路由。
- 对本赛题的启发：20x20 规模不需要 GPU，但可以借鉴“高频/关联货物聚类靠近出入口”的思想，形成 BalancePenalty 或 ZonePolicy。
- 来源：ScienceDirect，https://www.sciencedirect.com/science/article/pii/S0307904X25007747；arXiv，https://arxiv.org/abs/2504.20655

### R6. Topology-aware and highly generalizable deep reinforcement learning for efficient retrieval in multi-deep storage systems

- 类型：论文，Journal of Intelligent Manufacturing，First online 2025-09-06，Volume 37，Pages 2503-2536，2026。
- 作者：Funing Li, Yuan Tian, Ruben Noortwyck, Jifeng Zhou, Liming Kuang, Robert Schulz。
- DOI：10.1007/s10845-025-02654-w。
- 主要方法：GNN + Transformer + DRL，用图结构表示多深位仓储拓扑和物品属性。
- 对本赛题的启发：可把 20x20 仓位视为网格图，用图距离和拓扑位置作为评分输入；GNN 作为报告创新展望，不建议直接上 PLC。
- 来源：Springer，https://link.springer.com/article/10.1007/s10845-025-02654-w；arXiv，https://arxiv.org/abs/2506.14787

### R7. Impact of Path Planning on Energy Use and Emissions in Four Way Shuttle Storage Systems

- 类型：会议章节，Lecture Notes in Mechanical Engineering，First Online 2026-05-10。
- 作者：Marco Ricci, Riccardo Accorsi, Ilaria Battarra, Giacomo Lupi, Riccardo Manzini, Gabriele Sirri。
- 主要方法：四向穿梭车 AS/RS 路径规划对能耗与排放影响的仿真比较。
- 对本赛题的启发：设备损耗指标可以不只写“磨损”，也可建模为水平移动、垂直提升、转向、启停、能耗估计。
- 来源：Springer，https://link.springer.com/chapter/10.1007/978-3-032-21154-5_10

### R8. AI-enhanced Digital Twin systems for warehouse logistics optimization: A review of challenges with solutions and future directions

- 类型：综述论文，ICT Express，2026，Volume 12，Issue 2，Pages 459-479。
- DOI：10.1016/j.icte.2026.01.009。
- 主要内容：综述 AI + Digital Twin + IoT 在仓库物流优化中的应用，涉及资源分配、路径规划、任务分配、库存管理、仓位分配等。
- 对本赛题的启发：决赛可视化仿真可以包装成“小型数字孪生”：PLC 状态变量为物理层，CODESYS/Automation Builder 可视化为虚拟层，算法为决策层。
- 来源：ScienceDirect，https://www.sciencedirect.com/science/article/pii/S2405959526000093

### R9. 6G-enabled digital twin-based smart warehouse for supply chain of things

- 类型：论文，Computing，2026，Volume 108，Article 79。
- 作者：Müge Erel-Özçevik, Yusuf Özçevik, Elif Bozkaya-Aras, Tuğçe Bilen。
- DOI：10.1007/s00607-026-01668-3。
- 主要方法：6G + Digital Twin + SLAP + Genetic Algorithm；面向实时、能耗感知的智能仓储决策。
- 对本赛题的启发：可以用 GA/启发式算法离线优化权重；可视化展示可称为 digital-twin-inspired simulation，而不是普通动画。
- 来源：Istanbul Technical University 机构页，https://research.itu.edu.tr/en/publications/6g-enabled-digital-twin-based-smart-warehouse-for-supply-chain-of/；代码来源，https://github.com/yusufozcevik/DT-based-Smart-Warehouse-for-SLAP

### R10. Optimizing multi-level shuttle-based puzzle storage systems with horizontal and vertical dynamics using integer programming and ALNS-IP

- 类型：论文，Scientific Reports，2026。
- 主要方法：整数规划 + ALNS-IP 混合启发式，考虑水平与垂直动态。
- 对本赛题的启发：适合借鉴“水平 + 垂直运动统一建模”和“大规模精确模型 + 启发式近似”的思路；20x20 小规模可以采用局部搜索代替 ALNS。
- 来源：Nature Scientific Reports，https://www.nature.com/articles/s41598-026-40383-z

### R11. Heuristic algorithm for path planning in high-density automated storage and retrieval system raw material box reorganization

- 类型：论文，Science Progress，2026。
- 作者：Yung-Chia Chang, Kuei-Hu Chang, Hsuan Yen。
- DOI：10.1177/00368504261446484。
- 主要方法：高密度 AS/RS 中原料箱重组的路径规划启发式算法；目标是减少阻塞箱移动。
- 对本赛题的启发：若目标仓位不可用或重排成本高，应设计“重排/换位成本”或在局部搜索中避免产生高阻塞风险位置。
- 来源：SAGE，https://journals.sagepub.com/doi/10.1177/00368504261446484

### R12. A bi-level math-heuristic algorithm for integrated optimization of task scheduling and storage location assignment in automated storage and retrieval systems

- 类型：论文，Journal of the Brazilian Society of Mechanical Sciences and Engineering，2026，Volume 48，Article 95。
- 作者：Weidong Xie, Rui Wang, Songyuan Liu, Gaosong Feng。
- DOI：10.1007/s40430-025-06057-z。
- 主要方法：双层数学启发式；外层优化出库任务顺序，内层将堆垛机移动成本建成任务与仓位之间的二分图权重，用 Hungarian algorithm 做匹配。
- 对本赛题的启发：如果只做入库，可采用“排序 + 分配”；如果加出库/批量任务，可把任务和仓位做成 assignment problem。比赛实现阶段可用简化版。
- 来源：Springer，https://link.springer.com/article/10.1007/s40430-025-06057-z

### R13. Generative AI-based optimization for high-mix warehouses: Integrating agentic LLMs and discrete event simulation

- 类型：论文，Computers & Industrial Engineering，2026，Volume 214，Article 111884。
- 作者：Hicham El Baz, Mohammed Khalil Ghali, Linda Andrus, Daehan Won, Sang Won Yoon, Yong Wang。
- DOI：10.1016/j.cie.2026.111884。
- 主要方法：Agentic LLM + Human-in-the-loop + 离散事件仿真，用于高混合仓库 slotting 优化。
- 对本赛题的启发：可以在报告中说明：LLM/Claude Code 用于生成候选策略、自动生成仿真实验与报告，而最终控制逻辑必须由确定性 PLC 算法执行。该论文很适合支持“AI 辅助仿真优化”的表述。
- 来源：ScienceDirect，https://www.sciencedirect.com/science/article/pii/S0360835226000859；SUNY 页面，https://researchconnect.suny.edu/en/publications/generative-ai-based-optimization-for-high-mix-warehouses-integrat/

### R14. Leveraging Knowledge Graphs and LLM Reasoning to Identify Operational Bottlenecks for Warehouse Planning Assistance

- 类型：arXiv 预印本，2025-07-23。
- 主要方法：把离散事件仿真输出转化为知识图谱，再由 LLM agent 生成查询、诊断瓶颈和效率问题。
- 对本赛题的启发：后处理阶段可以把仿真日志整理成结构化 CSV/JSON，让 Claude Code 自动生成瓶颈分析段落，例如“高频货物平均距离下降多少、重货平均层高是否降低”。
- 来源：arXiv，https://arxiv.org/abs/2507.17273

---

## 4. 稍早但高度相关的补充参考

这些资料不严格属于 2025-07-03 至 2026-07-03 窗口，但与赛题建模很贴近，可作为“背景研究”或“补充参考”。

### S1. Optimization of transporting time through load shuffling in automated storage/retrieval systems

- 类型：论文，2025。
- 主要方法：将 AS/RS load shuffling 建成 0-1 整数规划问题，通过重新分配已存货物降低后续运输时间。
- 对本赛题的启发：局部交换优化可以被解释为简化版 load shuffling。
- 来源：Springer，https://link.springer.com/article/10.1007/s13160-025-00701-w

### S2. Integrated optimization of storage space allocation and crane scheduling in automated storage and retrieval systems

- 类型：论文，Robotics and Computer-Integrated Manufacturing，2025，Volume 93，Article 102918。
- 主要方法：集成优化仓位分配和堆垛机/起重机调度。
- 对本赛题的启发：可用于解释“仓位分配与设备调度耦合”。
- 来源：ScienceDirect，https://www.sciencedirect.com/science/article/abs/pii/S0736584524002059

### S3. Storage Location Assignment in Emergency Reserve Warehouses: A Multi-Objective Optimization Algorithm

- 类型：论文，Mathematics，2025，13(10):1636。
- DOI：10.3390/math13101636。
- 主要方法：NSGA-II 与精英策略，考虑平面和三维存储配置、多目标仓位分配。
- 对本赛题的启发：多目标指标可包括效率、空间、稳定性、不同货物类型；可作为 NSGA-II/遗传算法对照方法。
- 来源：MDPI，https://www.mdpi.com/2227-7390/13/10/1636

### S4. The storage location assignment and picker routing problem

- 类型：论文，European Journal of Operational Research，2025。
- 主要方法：把 SLAP 与 picker routing problem 结合，并提出 Branch-Cut-and-Price 框架。
- 对本赛题的启发：从理论上支持“仓位分配会影响路径规划，二者应联合考虑”。
- 来源：ScienceDirect，https://www.sciencedirect.com/science/article/pii/S0377221725004394

---

## 5. 开源项目与工程资源

### P1. OpenFactoryTwin / OFacT

- 类型：开源数字孪生框架。
- 用途：生产与物流离散物料流系统的数字孪生建模，支持设计、规划和运行控制思路。
- 对本赛题的价值：参考其“资源、过程、订单、物料流、状态模型”的建模方式。
- 来源：https://github.com/OpenFactoryTwin/ofact；Zenodo，https://zenodo.org/records/13734527

### P2. Automated-Warehouse-DES

- 类型：Python + SimPy 离散事件仿真项目。
- 用途：评估和优化 AS/RS 的仓库配置、存储策略、运行策略、机械约束和可视化 dashboard。
- 对本赛题的价值：可参考其离散事件仿真结构，快速构造初赛验证图表。
- 来源：https://github.com/ShaileshDivey/Automated-Warehouse-DES

### P3. simulator-automatic-warehouse

- 类型：Python 自动仓库/垂直存储系统仿真库。
- 用途：提供自动仓库数字孪生和仿真器。
- 对本赛题的价值：可参考其“垂直仓储 + 货到人”建模方式。
- 来源：https://github.com/AndreVale69/simulator-automatic-warehouse

### P4. SA-Tabu

- 类型：仓位分配优化代码。
- 用途：Surrogate-assisted Tabu Search，用于大规模 Storage Location Assignment with Grouping Constraints。
- 对本赛题的价值：可参考 Tabu/local search 结构，把本赛题局部交换优化做成轻量版 Tabu。
- 来源：https://github.com/ShengranHu/SA-Tabu

### P5. DRL-Order-Picking

- 类型：动态拣选 DRL 论文代码资源。
- 用途：与 R4 论文相关，可参考仿真环境结构和 reward 设计。
- 来源：https://github.com/Sasanm88/DRL-Order-Picking

### P6. warehouse-simulator

- 类型：AS/RS 仓库仿真器。
- 用途：控制 crane、多输入输出，并默认使用 A* 规划路径。
- 对本赛题的价值：可参考 A* 路径规划/迷宫式路径可视化思路。20x20 单堆垛机场景可先用 Manhattan 路径。
- 来源：https://github.com/ironmann250/warehouse-simulator

### P7. ABB 官方 Automation Builder / AC500 / CODESYS 资源

- Automation Builder 是 ABB 面向 PLC、安全、驱动、运动和控制面板的集成编程、仿真、调试与维护环境；用于 AC500 PLC 和 CP600 控制面板。
- AC500 是 ABB 的可扩展 PLC 平台，适用于机器制造、基础设施和工业自动化。
- CODESYS ST 支持 IF、CASE、FOR、WHILE 等结构化文本语句，适合实现本赛题的数组扫描、边界判断、评分函数和功能块封装。
- CODESYS Visualization 可用于创建图形用户界面、面板、对话框等；ABB AC500 V3 也提供 WebVisualization 示例。
- 来源：
  - https://www.abb.com/global/en/areas/motion/digital-tools/automation-builder
  - https://www.abb.com/global/en/areas/motion/plc
  - https://www.abb.com/global/en/areas/motion/plc/training/application-examples
  - https://content.helpme-codesys.com/en/CODESYS%20Development%20System/_cds_programming_in_st.html
  - https://content.helpme-codesys.com/en/CODESYS%20Visualization/_visu_f_overview.html

---

## 6. 推荐算法：AWRA-LS

### 6.1 建模对象

仓位坐标：

```text
p = (x, y), x,y ∈ {0,1,...,19}
Start = (0,0)
```

建议把 `y` 解释为层高或纵向层号：

```text
CapCoef(y) = 1.0 - 0.02*y
```

因此：

```text
y = 0  -> 承重系数 1.00
y = 19 -> 承重系数 0.62
```

如果现场老师把 20x20 解释为平面布局而非层高，请仍然保留 `CapCoef(y)`，把 y 当作从底到顶的层序或行序即可；关键是报告中定义清楚。

货物结构：

```text
g_i = (id, name, weight_i, freq_i, volume_i)
```

仓位结构：

```text
slot(x,y) = (occupied, presetOccupied, capCoef, maxWeight, maxVolume, currentGoodsId)
```

### 6.2 可行性约束

仓位可选条件：

```text
Occupied(x,y) == false
PresetOccupied(x,y) == false
weight_i <= W_base * CapCoef(y)
volume_i <= V_slot
```

若不可行，评分直接设为极大值 `INF`。

### 6.3 路径与执行时间模型

基础路径长度用 Manhattan 距离：

```text
D(x,y) = abs(x - x0) + abs(y - y0)
```

若堆垛机水平和垂直不能同时运动：

```text
T(x,y) = abs(x-x0)/Vx + abs(y-y0)/Vy + T_load + T_unload
```

若堆垛机水平和垂直可同时运动：

```text
T(x,y) = max(abs(x-x0)/Vx, abs(y-y0)/Vy) + T_load + T_unload
```

比赛演示可以先采用“不能同时运动”的保守模型，比较容易解释和用 ST 实现。

### 6.4 多目标评分函数

对每个货物 `i` 和候选仓位 `p` 计算：

```text
Score(i,p) = α * FreqCost(i,p)
           + β * WearCost(p)
           + γ * WeightRisk(i,p)
           + δ * VolumePenalty(i,p)
           + η * BalancePenalty(p)
```

建议定义为归一化变量，方便 PLC 用 REAL 计算：

```text
FreqCost(i,p)      = norm(freq_i) * norm(T(p))
WearCost(p)        = kx*norm(abs(x)) + ky*norm(abs(y)) + ks*norm(turns_or_starts)
WeightRisk(i,p)    = norm(weight_i) * norm(y)       # 重货越倾向底层
VolumePenalty(i,p) = norm(volume_i) * fragmentation_or_slot_pressure
BalancePenalty(p)  = local_density_penalty or aisle_balance_penalty
```

基础权重建议：

```text
α = 0.45  # 访问频次和时间
β = 0.20  # 设备损耗/路径长度
γ = 0.25  # 重量与层高风险
δ = 0.05  # 体积/空间利用
η = 0.05  # 分布均衡
```

可以用 Python 在随机数据集上搜索更优权重，然后把权重写入 PLC 常量或 HMI 可调参数。

### 6.5 货物排序：Rank 阶段

借鉴 R2 的 Rank-Assign 思路，先对货物排序：

```text
Priority_i = λ1*norm(freq_i) + λ2*norm(weight_i) + λ3*norm(volume_i)
```

建议：

```text
λ1 = 0.50  # 高频优先
λ2 = 0.35  # 重货优先
λ3 = 0.15  # 大体积优先
```

排序原则：高频、重、大体积货物优先分配，避免后续只剩不合适仓位。

### 6.6 仓位分配：Assign 阶段

对排序后的每件货物，扫描 400 个仓位，选择可行且 Score 最低的位置：

```text
bestSlot = None
bestScore = INF
for y in 0..19:
  for x in 0..19:
    if CheckFeasible(good, slot[x][y]):
       score = CalcScore(good, slot[x][y])
       if score < bestScore:
          bestScore = score
          bestSlot = (x,y)
assign good to bestSlot
```

### 6.7 局部搜索：Local Search 阶段

分配完成后，尝试交换两个货物的位置。如果交换后总成本下降，则接受交换。

```text
TotalCost = Σ Score(i, assigned_slot_i)
for iter in 1..MaxIter:
  improved = false
  for each pair (i,j):
    if swap feasible and newTotalCost < oldTotalCost:
       accept swap
       improved = true
  if not improved:
       break
```

PLC 中为了确定性和实时性，建议限制：

```text
MaxIter <= 3 或 5
每周期只检查有限数量 pair，避免单周期过长
或在初赛仿真里做完整局部搜索，PLC 演示做轻量版本
```

---

## 7. PLC / ST 实现建议

### 7.1 数据类型建议

```pascal
TYPE ST_Good :
STRUCT
    Id          : INT;
    Name        : STRING[32];
    Weight      : REAL;
    Freq        : REAL;
    Volume      : REAL;
    Priority    : REAL;
    Assigned    : BOOL;
    X           : INT;
    Y           : INT;
    Score       : REAL;
    PathLength  : REAL;
    ExecTime    : REAL;
END_STRUCT
END_TYPE

TYPE ST_Slot :
STRUCT
    X             : INT;
    Y             : INT;
    Occupied      : BOOL;
    PresetOcc     : BOOL;
    CapCoef       : REAL;
    MaxWeight     : REAL;
    MaxVolume     : REAL;
    GoodsId       : INT;
END_STRUCT
END_TYPE
```

### 7.2 功能块划分

```text
FB_InitWarehouse
  初始化 20x20 仓位、预占用状态、承重系数、最大承重、最大体积。

FC_IsPresetOccupied
  输入 x,y，输出该仓位是否预占用。用于封装赛题歧义。

FC_CheckFeasible
  输入货物和仓位，判断 occupied、preset、weight、volume 是否满足。

FC_CalcPath
  输入起点和目标点，输出路径长度、执行时间、路径点数组。

FC_CalcScore
  输入货物、仓位、路径时间，输出多目标评分。

FB_SortGoodsByPriority
  对货物按 Priority 降序排序。若 ST 排序复杂，可用简单选择排序。

FB_SelectSlot
  对单个货物扫描 400 仓位，选择最低 Score 的可行仓位。

FB_AssignAllGoods
  调用排序、选仓、更新仓位状态。

FB_LocalSwapImprove
  对已分配结果执行有限次数局部交换优化。

FB_Stats
  统计总时间、平均时间、吞吐率、空间利用率、设备损耗、约束违规数。

GVL_Visualization
  存放可视化变量：仓位状态矩阵、当前路径、选中货物、统计结果。
```

### 7.3 边界判断清单

必须覆盖这些边界，否则评分中“边界判断充分合理”会扣分：

- x/y 越界。
- 所有仓位已满。
- 货物重量超过所有仓位最大承重。
- 货物体积超过单仓位体积。
- 预占用仓位不能被覆盖。
- 同一个货物不能重复分配。
- 同一个仓位不能分配给多个货物。
- 访问频次、重量、体积为负数时拒绝输入或修正为 0。
- 若没有可行仓位，输出错误码和可视化报警。
- 局部交换前后必须再次检查承重和体积约束。

### 7.4 ST 代码骨架片段

```pascal
FUNCTION FC_CapCoef : REAL
VAR_INPUT
    y : INT;
END_VAR
VAR
    yy : INT;
END_VAR

IF y < 0 THEN
    yy := 0;
ELSIF y > 19 THEN
    yy := 19;
ELSE
    yy := y;
END_IF;

FC_CapCoef := 1.0 - 0.02 * INT_TO_REAL(yy);
END_FUNCTION
```

```pascal
FUNCTION FC_CheckFeasible : BOOL
VAR_INPUT
    GoodWeight : REAL;
    GoodVolume : REAL;
    SlotOccupied : BOOL;
    SlotPresetOcc : BOOL;
    SlotMaxWeight : REAL;
    SlotMaxVolume : REAL;
END_VAR

FC_CheckFeasible := FALSE;

IF SlotOccupied THEN RETURN; END_IF;
IF SlotPresetOcc THEN RETURN; END_IF;
IF GoodWeight < 0.0 THEN RETURN; END_IF;
IF GoodVolume < 0.0 THEN RETURN; END_IF;
IF GoodWeight > SlotMaxWeight THEN RETURN; END_IF;
IF GoodVolume > SlotMaxVolume THEN RETURN; END_IF;

FC_CheckFeasible := TRUE;
END_FUNCTION
```

```pascal
FUNCTION FC_CalcTravelTime : REAL
VAR_INPUT
    x0 : INT;
    y0 : INT;
    x1 : INT;
    y1 : INT;
    Vx : REAL;
    Vy : REAL;
    TLoad : REAL;
    TUnload : REAL;
    SimultaneousXY : BOOL;
END_VAR
VAR
    dx : REAL;
    dy : REAL;
    tx : REAL;
    ty : REAL;
END_VAR

dx := ABS(INT_TO_REAL(x1 - x0));
dy := ABS(INT_TO_REAL(y1 - y0));

IF Vx <= 0.0 THEN Vx := 1.0; END_IF;
IF Vy <= 0.0 THEN Vy := 1.0; END_IF;

tx := dx / Vx;
ty := dy / Vy;

IF SimultaneousXY THEN
    IF tx > ty THEN
        FC_CalcTravelTime := tx + TLoad + TUnload;
    ELSE
        FC_CalcTravelTime := ty + TLoad + TUnload;
    END_IF;
ELSE
    FC_CalcTravelTime := tx + ty + TLoad + TUnload;
END_IF;
END_FUNCTION
```

---

## 8. Python 仿真实现建议

### 8.1 推荐项目结构

```text
warehouse_optimizer/
  README.md
  docs/
    research_brief.md
  data/
    sample_goods.csv
    results_awra_ls.csv
  src/
    __init__.py
    model.py              # Good, Slot, Warehouse 数据结构
    init_rules.py         # 预占用规则、承重规则
    path.py               # Manhattan/A*/time model
    scoring.py            # score 函数、归一化、权重
    optimizers.py         # Random/Nearest/RuleBased/AWRA_LS
    simulation.py         # 批量运行与统计
    visualization.py      # 20x20 热力图、路径图、对比图
    st_generator.py       # 可选：生成 ST 常量表或功能块骨架
  tests/
    test_feasible.py
    test_path.py
    test_scoring.py
    test_assignment.py
```

### 8.2 推荐输出文件

```text
assignment_results.csv
  good_id, name, weight, freq, volume, x, y, score, path_length, exec_time

summary_metrics.csv
  algorithm, total_time, avg_time, throughput, space_utilization, wear_index, violations

warehouse_layout.csv
  x, y, occupied, preset_occ, goods_id, cap_coef, max_weight

report_figures/
  total_time_comparison.png
  avg_path_length_comparison.png
  final_layout_heatmap.png
  high_freq_distance_comparison.png
  heavy_goods_layer_comparison.png
```

### 8.3 测试数据建议

至少生成三类货物数据：

```text
Case A：均匀分布。重量、频次、体积随机均匀。
Case B：高频偏态。少量货物访问频次很高，模拟电商爆品。
Case C：重货偏多。测试承重约束和底层优先策略。
```

每组货物数量建议：50、100、200、300，观察算法稳定性。

---

## 9. 报告验证实验设计

### 9.1 对比算法

```text
Random
  随机选择可行仓位，作为最低基线。

Nearest Empty
  选择距离 (0,0) 最近的可行空仓位，体现单目标路径最短。

Rule-based
  高频货物靠近入口，重货靠底层，大体积货物优先，体现工程规则。

AWRA-LS
  自适应加权排序分配 + 多目标评分 + 局部搜索。
```

### 9.2 评估指标

```text
TotalTime = Σ ExecTime_i
AvgTime = TotalTime / N
Throughput = N / TotalTime
AvgPathLength = Σ PathLength_i / N
SpaceUtilization = OccupiedSlots / 400
WearIndex = Σ(kx*|x| + ky*|y| + ks*starts_or_turns)
HeavyGoodsAvgLayer = average(y of top-weight goods)
HighFreqAvgDistance = average(distance of top-frequency goods)
ConstraintViolation = count(weight/volume/occupied violations)
```

### 9.3 预期结论表达

不要只写“本算法更优”，建议写成：

```text
与 Random 相比，AWRA-LS 显著降低总存储时间和平均路径长度。
与 Nearest Empty 相比，AWRA-LS 在保持较低路径成本的同时，减少重货高层存放风险。
与 Rule-based 相比，AWRA-LS 通过局部搜索降低局部最优影响，使总目标函数进一步下降。
所有实验中约束违规数为 0，证明模型满足工程安全性要求。
```

---

## 10. 决赛可视化方案

### 10.1 画面布局

推荐在 CODESYS / Automation Builder 可视化中分四块：

```text
左侧：20x20 仓位矩阵
  空闲：浅灰
  预占用：深灰
  已占用：绿色
  当前推荐仓位：黄色
  当前路径：蓝色
  不可行/报警：红色

右上：货物输入区
  id/name/weight/freq/volume
  Add/Assign/Reset/RunAll 按钮

右中：路径与仓位结果
  起点、终点、路径点、路径长度、执行时间、评分

右下：统计信息
  总时间、平均时间、吞吐率、空间利用率、设备损耗、违规数
```

### 10.2 可视化变量建议

```pascal
VAR_GLOBAL
    VisuSlotState : ARRAY[0..19, 0..19] OF INT;
    // 0=free, 1=preset occupied, 2=occupied, 3=current target, 4=path, 5=error

    VisuCurrentX : INT;
    VisuCurrentY : INT;
    VisuTargetX  : INT;
    VisuTargetY  : INT;

    VisuPathX : ARRAY[0..39] OF INT;
    VisuPathY : ARRAY[0..39] OF INT;
    VisuPathCount : INT;

    VisuTotalTime : REAL;
    VisuAvgTime : REAL;
    VisuSpaceUtilization : REAL;
    VisuWearIndex : REAL;
    VisuViolationCount : INT;
    VisuStatusText : STRING[128];
END_VAR
```

### 10.3 演示脚本

```text
1. 展示初始 20x20 仓库，预占用仓位已经标出。
2. 输入一件高频轻货，系统推荐靠近入口的位置。
3. 输入一件重货，系统推荐较低层位置。
4. 输入多件货物，运行批量分配，显示路径和总时间变化。
5. 切换对比算法，展示 AWRA-LS 总时间更低、违规数为 0。
6. 人为输入超重货物，展示边界判断和报警。
```

---

## 11. 评分维度对应策略

```text
模型准确性及验证报告 30%
  用多目标模型、约束检查、对比实验和图表支撑。

基于 ABB AC500 实现 30%
  用 ST 功能块、结构体、数组、边界判断、清晰注释体现工程能力。

算法创新性 10%
  用 Rank-Assign、AI 权重寻优、局部搜索、数字孪生验证作为创新点。

模型可视化仿真实现 20%
  用 20x20 矩阵、路径、状态颜色、统计面板、异常报警体现完成度。

演讲技巧 10%
  用“从随机存放到智能仓位优化”的递进故事讲清楚价值。
```

演讲主线建议：

```text
传统策略：能放就放，但没有考虑高频、重货和路径。
工程挑战：路径、承重、空间和设备损耗相互冲突。
我们的方案：先排序，再评分，再局部优化。
AI 作用：离线学习权重和策略，在线保证 PLC 可解释、稳定、实时。
验证结果：总时间下降、重货更靠低层、高频货更靠入口、约束违规为 0。
```

---

## 12. 关键实现取舍

### 12.1 不建议在 PLC 上直接训练深度学习模型

理由：

- 训练过程计算量大，不适合 PLC 周期任务。
- 难以解释，不利于边界判断和工程安全。
- 比赛评分重视 ST 功能块和可靠实现，不是深度模型复杂度。

更好的说法：

```text
本项目采用 AI-assisted optimization。深度强化学习、遗传算法或参数搜索用于离线学习评分权重与策略结构；PLC 在线执行确定性、可解释、可验证的轻量优化算法。
```

### 12.2 路径规划先做简单，再做扩展

基础版：Manhattan 路径，水平再垂直，或垂直再水平。

扩展版：若需要避开障碍，可加入 A*。但对于 20x20 堆垛机坐标，起点到仓位更多是堆垛机运动时间模型，A* 不一定必要。

### 12.3 体积因素的处理

题目说每个仓位长宽高一样，若每个仓位只放一件货物，则体积主要用于可行性判断：`volume <= V_slot`。

如果要体现空间利用率创新，可增加：

```text
VolumePenalty = volume / V_slot
```

或将货物分为大/中/小，优先让大体积货物分配到更低风险、路径更稳定的仓位。

### 12.4 设备损耗的处理

设备损耗可用近似指标，不需要真实电机模型：

```text
WearIndex = kx*水平移动距离 + ky*垂直移动距离 + ks*启停次数 + kt*转向次数
```

对于堆垛机，通常垂直提升比水平移动更耗能，可令 `ky > kx`。

---

## 13. 可直接交给 Claude Code 的实现需求清单

```text
目标：实现 AWRA-LS 立体仓储仓位优化仿真与 ABB AC500 ST 代码骨架。

必须实现：
1. 20x20 仓位初始化。
2. 承重系数 CapCoef(y)=1.0-0.02*y。
3. 预占用规则函数 IsPresetOccupied(x,y)，支持方案 A/B 切换。
4. 货物输入字段：id、name、weight、frequency、volume。
5. 可行性检查：occupied、preset、weight、volume。
6. 路径长度和执行时间计算。
7. 多目标评分函数。
8. 货物优先级排序。
9. Random、Nearest、Rule-based、AWRA-LS 四种算法。
10. 局部交换优化。
11. 输出 CSV 和统计指标。
12. 生成报告图表。
13. 生成 ST 语言结构体、函数、功能块骨架。
14. 单元测试覆盖边界场景。

优先级：
第一阶段先完成 Python 仿真和结果图。
第二阶段生成 ST 代码骨架。
第三阶段整理 PPT/Word 报告图表。
第四阶段对接 Automation Builder 可视化变量。
```

---

## 14. 参考文献与来源清单

[R1] Yang, Z.; Wen, P. Data-driven reinforcement learning-based optimization of shared warehouse storage locations. Computers & Industrial Engineering, 206, 111195, 2025. DOI: 10.1016/j.cie.2025.111195. https://www.sciencedirect.com/science/article/abs/pii/S0360835225003419

[R2] Pan, W.; Chen, M.; Lin, B.; Wang, Y.; Zhao, X.; He, X.; Ye, J. Large-Scale Storage Location Assignment via Hierarchical Reinforcement Learning: A Rank and Assign Approach. IEEE Transactions on Knowledge and Data Engineering, 37(11), 6506-6520, 2025. https://ieeexplore.ieee.org/document/11159170/

[R3] Zhang, D.; Liu, B.; Yue, E.; Wu, D. Integrated Optimization Framework for AS/RS: Coupling Storage Allocation, Collaborative Scheduling, and Path Planning via Hybrid Meta-Heuristics. Applied Sciences, 16(8), 3757, 2026. DOI: 10.3390/app16083757. https://www.mdpi.com/2076-3417/16/8/3757

[R4] Mahmoudinazlou, S.; Sobhanan, A.; Charkhgard, H.; Eshragh, A.; Dunn, G. Deep reinforcement learning for dynamic order picking in warehouse operations. Computers & Operations Research, 182, 107112, 2025. DOI: 10.1016/j.cor.2025.107112. https://www.sciencedirect.com/science/article/pii/S0305054825001406

[R5] Bengtsson, M.; Wittsten, J.; Waidringer, J. Warehouse storage and retrieval optimization via clustering, dynamical systems modeling, and GPU-accelerated routing. Applied Mathematical Modelling, 154, 116700, 2025. DOI: 10.1016/j.apm.2025.116700. https://www.sciencedirect.com/science/article/pii/S0307904X25007747

[R6] Li, F.; Tian, Y.; Noortwyck, R.; Zhou, J.; Kuang, L.; Schulz, R. Topology-aware and highly generalizable deep reinforcement learning for efficient retrieval in multi-deep storage systems. Journal of Intelligent Manufacturing, 2025/2026. DOI: 10.1007/s10845-025-02654-w. https://link.springer.com/article/10.1007/s10845-025-02654-w

[R7] Ricci, M.; Accorsi, R.; Battarra, I.; Lupi, G.; Manzini, R.; Sirri, G. Impact of Path Planning on Energy Use and Emissions in Four Way Shuttle Storage Systems. Springer LNME, 2026. https://link.springer.com/chapter/10.1007/978-3-032-21154-5_10

[R8] Alam, M. M.; Ugli, R. A. N.; Tanha, K. J.; Jun, T. AI-enhanced Digital Twin systems for warehouse logistics optimization: A review of challenges with solutions and future directions. ICT Express, 12(2), 459-479, 2026. DOI: 10.1016/j.icte.2026.01.009. https://www.sciencedirect.com/science/article/pii/S2405959526000093

[R9] Erel-Özçevik, M.; Özçevik, Y.; Bozkaya-Aras, E.; Bilen, T. 6G-enabled digital twin-based smart warehouse for supply chain of things. Computing, 108, 79, 2026. DOI: 10.1007/s00607-026-01668-3. https://research.itu.edu.tr/en/publications/6g-enabled-digital-twin-based-smart-warehouse-for-supply-chain-of/

[R10] Al Jneid, R.; Yiğit, V.; Keskin, M. E. Optimizing multi-level shuttle-based puzzle storage systems with horizontal and vertical dynamics using integer programming and ALNS-IP. Scientific Reports, 2026. https://www.nature.com/articles/s41598-026-40383-z

[R11] Chang, Y.-C.; Chang, K.-H.; Yen, H. Heuristic algorithm for path planning in high-density automated storage and retrieval system raw material box reorganization. Science Progress, 2026. DOI: 10.1177/00368504261446484. https://journals.sagepub.com/doi/10.1177/00368504261446484

[R12] Xie, W.; Wang, R.; Liu, S.; Feng, G. A bi-level math-heuristic algorithm for integrated optimization of task scheduling and storage location assignment in automated storage and retrieval systems. Journal of the Brazilian Society of Mechanical Sciences and Engineering, 48, 95, 2026. DOI: 10.1007/s40430-025-06057-z. https://link.springer.com/article/10.1007/s40430-025-06057-z

[R13] El Baz, H.; Ghali, M. K.; Andrus, L.; Won, D.; Yoon, S. W.; Wang, Y. Generative AI-based optimization for high-mix warehouses: Integrating agentic LLMs and discrete event simulation. Computers & Industrial Engineering, 214, 111884, 2026. DOI: 10.1016/j.cie.2026.111884. https://www.sciencedirect.com/science/article/pii/S0360835226000859

[R14] Parekh, R.; Gopalakrishnan, S.; Ahmad, Z.; Deodhar, A. Leveraging Knowledge Graphs and LLM Reasoning to Identify Operational Bottlenecks for Warehouse Planning Assistance. arXiv:2507.17273, 2025. https://arxiv.org/abs/2507.17273

[S1] Ishikura, H. et al. Optimization of transporting time through load shuffling in automated storage/retrieval systems. 2025. https://link.springer.com/article/10.1007/s13160-025-00701-w

[S2] Zhang, W.; Deng, Z.; Zhang, C.; Shen, W. Integrated optimization of storage space allocation and crane scheduling in automated storage and retrieval systems. Robotics and Computer-Integrated Manufacturing, 93, 102918, 2025. https://www.sciencedirect.com/science/article/abs/pii/S0736584524002059

[S3] Liang, C.; Cui, T.; Wei, Y.; Zhao, K.; Yue, X.; Wang, C. Storage Location Assignment in Emergency Reserve Warehouses: A Multi-Objective Optimization Algorithm. Mathematics, 13(10), 1636, 2025. DOI: 10.3390/math13101636. https://www.mdpi.com/2227-7390/13/10/1636

[S4] Prunet, T. et al. The storage location assignment and picker routing problem. European Journal of Operational Research, 2025. https://www.sciencedirect.com/science/article/pii/S0377221725004394

[P1] OpenFactoryTwin / OFacT. https://github.com/OpenFactoryTwin/ofact

[P2] Automated-Warehouse-DES. https://github.com/ShaileshDivey/Automated-Warehouse-DES

[P3] simulator-automatic-warehouse. https://github.com/AndreVale69/simulator-automatic-warehouse

[P4] SA-Tabu. https://github.com/ShengranHu/SA-Tabu

[P5] DRL-Order-Picking. https://github.com/Sasanm88/DRL-Order-Picking

[P6] warehouse-simulator. https://github.com/ironmann250/warehouse-simulator

[P7] ABB Automation Builder. https://www.abb.com/global/en/areas/motion/digital-tools/automation-builder

[P8] ABB PLC Automation / AC500. https://www.abb.com/global/en/areas/motion/plc

[P9] ABB PLC Application Examples. https://www.abb.com/global/en/areas/motion/plc/training/application-examples

[P10] CODESYS Structured Text. https://content.helpme-codesys.com/en/CODESYS%20Development%20System/_cds_programming_in_st.html

[P11] CODESYS Visualization Overview. https://content.helpme-codesys.com/en/CODESYS%20Visualization/_visu_f_overview.html
