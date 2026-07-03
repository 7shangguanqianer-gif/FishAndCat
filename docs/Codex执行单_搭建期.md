# Codex 执行单(搭建期,2026-07-03 签发)

> 使用方式:每个任务的「给 Codex 的提示词」整段复制给 Codex 执行。
> Codex 冷启动须知(写进每个提示词开头了):先读 F:\abb_wh_work\现状与任务.md 和
> docs\canonical_assumptions.md;数字口径只认 canonical;所有随机必须固定 seed;
> 改评分函数/场景参数必须重跑 sim/export_st_vectors.py + 回归测试,红了先查同步而不是改容差。
> 优先级:A=立即 B=本周 C=等前置完成 D=按周计划到点再做。

---

## W-001(A)环境补齐与自检

**给 Codex 的提示词:**
```
项目:F:\abb_wh_work(2026 ABB杯 智储优控,先读 现状与任务.md)。
任务:补齐并自检本机环境。
1) 检查 python --version(需3.8+)、matplotlib(已装则跳过);缺则
   python -m pip install matplotlib -i https://mirrors.aliyun.com/pypi/simple/
   (本机走 Clash 代理时 pip 直连易断,统一用阿里云源,不要用默认源重试浪费时间)
2) 跑 python F:\abb_wh_work\sim\run_all.py,确认末尾"全部完成",
   且回归测试 15/15 OK、实验矩阵"全矩阵违规总数 = 0"。
3) Automation Builder 用户正在装,你不负责装它,但生成一份安装后自检清单存
   F:\abb_wh_work\docs\AB安装自检.md,内容:①启动 AB 确认版本≥2.8;②License Manager
   里激活免费 Basic 许可证(装完首次启动会引导,选 Basic license 免费注册即可);
   ③新建测试工程选 AC500 V3 任一 CPU(如 PM5650)能进入 CODESYS 编辑器;
   ④菜单里能找到 在线→仿真(Simulation) 选项。除 AB 外无须装任何其他软件
   (CODESYS 内核、可视化编辑器都在 AB 里;不需要单独装 CODESYS/CP600 Panel Builder)。
产出:AB安装自检.md + 运行日志摘要贴回。不要动 sim/ 与 plc/ 下任何代码。
```

## W-002(A)回归哨兵(每次会话开始/结束跑)

**给 Codex 的提示词:**
```
项目:F:\abb_wh_work。跑 python sim\tests\test_sim.py,15 用例须全 OK。
若有失败:不要改测试、不要改容差,检查 git/文件改动定位是谁动了口径,
报告差异并停下等用户裁决(canonical 变更流程)。
```

## W-003(B)评分权重多 seed 精标

**给 Codex 的提示词:**
```
项目:F:\abb_wh_work(先读 现状与任务.md、docs\canonical_assumptions.md §E、docs\实验发现.md F2)。
任务:把单 seed 初标定升级为多 seed 精标。
1) 新建 sim\calibrate.py:网格 δ∈{0.05..0.30 步0.05} × β∈{0.4,0.6,0.8} × γ∈{0.2,0.4,0.6},
   α 固定 1.0;每组合跑 5 seeds(2026,7,42,123,999)×120件×and 规则,策略只跑 near/score/awra;
   记录 exp_t/hot_t/energy/cog 的 mean±std 到 sim\out\calibration.csv。
2) 选优准则(按序):①score 的 exp_t 均值 ≤ near 的 exp_t 均值;②hot_t 均值最小;
   ③energy 均值不劣于 near 5% 以上。输出推荐组合及依据。
3) 只报告推荐值,不要直接改 warehouse_sim.py 默认值——权重是口径,改动走 canonical 流程:
   用户批准后才改默认值+同步 canonical E+重跑 export_st_vectors.py+全量回归。
产出:calibrate.py、calibration.csv、推荐结论(贴回)。
```

## W-004(C,可选创新加分)NSGA-II 对照实验

**给 Codex 的提示词:**
```
项目:F:\abb_wh_work。任务:给 AWRA-LS 加一个多目标进化算法对照(报告"算法创新性"素材)。
1) pip install pymoo -i https://mirrors.aliyun.com/pypi/simple/(失败则纯手写简化 NSGA-II,
   染色体=货物到仓位的分配排列,不引第三方也可)。
2) 新建 sim\nsga2_baseline.py:双目标(频次加权期望取货时间, 能耗),约束=承重/容积/占用,
   种群50、代数100、seed 固定;输出 Pareto 前沿点集 CSV + 图 sim\figs\fig6_pareto前沿.png,
   图上叠加 AWRA-LS 单点(seed=2026,120件,and)看它落在前沿哪个位置。
3) 结论按事实写:若 AWRA-LS 接近前沿→"轻量算法逼近进化算法前沿";若差距大→如实记录
   gap(负结果也是工程叙事,不许美化)。运行时间控制在 5 分钟内。
产出:nsga2_baseline.py、fig6、结论段(贴回)。不改现有文件。
```

## W-005(C,等 AB 装好,人机协作)Automation Builder 工程搭建

Codex 不能点 GUI,此任务 = Codex 出详细操作卡,用户照卡点鼠标,Codex 核对结果。

**给 Codex 的提示词:**
```
项目:F:\abb_wh_work。用户已装好 Automation Builder。任务:引导建 PLC 工程。
1) 读 plc\README_PLC.md,把 §1-§2 展开成逐步操作卡(每步一句话+预期界面反馈),
   存 docs\AB建工程操作卡.md;导入顺序:DUT(01,07的TYPE)→GVL(02,07的GVL)→
   函数(03,07的FC_LoadDemoGoods)→功能块(04)→程序(05,06)→任务配置(10ms 挂 PRG_Main)。
2) 用户完成后让其提供:PRG_Test 运行截图(iPassed 值)、编译输出。
   期望 iPassed=21;若编译报错,按报错逐条给修改建议(常见:AB 版本语法差异、
   枚举前缀、CONCAT 嵌套层数限制),把实际改动记录进 README_PLC.md §4 已知注意项。
产出:AB建工程操作卡.md + 问题修复记录。
```

## W-006(B)报告图打磨

**给 Codex 的提示词:**
```
项目:F:\abb_wh_work。任务:打磨 sim\plots.py 的 fig2 占用热力图可读性(不改数据口径):
1) 预占用格不再借用色带端点(-1),改为独立灰色(masked array + cmap.set_bad 或双层绘制);
   空位=白、预占=中灰、货物=YlOrRd 按频次热度。
2) 三联图共享 colorbar 保持,加图例说明三种格子;字号统一 9-11pt。
3) 重跑 python sim\plots.py,人眼检查三张图差异可辨识(near 热货散、awra 热货聚 I/O 角)。
产出:plots.py diff + 新 fig2。其余四图不动。
```

## W-007(D,按排期 W4=7/27 周启动)决赛可视化

前置:W-005 完成。内容:按 plc\README_PLC.md §5 + _ref 资料包 §10 做 CODESYS 可视化画面
(20×20 网格绑 VisuSlotState、输入区、统计区、六步演示脚本),录屏。届时签发详细提示词。

## W-008(D,报告周签发)WORD/PPT 生成

沿语音赛模式(python-docx 生成器,数字从 out/*.csv 读,禁 hardcode)或手写——
等用户在第二轮问题里拍板工具链后签发。

---
## 签发状态跟踪

| 任务 | 优先级 | 状态 |
|---|---|---|
| W-001 环境补齐自检 | A | 待签发 |
| W-002 回归哨兵 | A | 待签发(常驻) |
| W-003 权重精标 | B | 待签发 |
| W-004 NSGA-II 对照 | C | 用户拍板后签发 |
| W-005 AB 建工程 | C | 等 AB 装完 |
| W-006 fig2 打磨 | B | 待签发 |
| W-007 决赛可视化 | D | 7/27 周 |
| W-008 报告生成 | D | 报告周 |
