# S3 评分修订 what-if 结论(负结果 · 证据先行的兑现)

> 结论一句话:**两个修订假设(τ 距离饱和 / f_max 动态化)在决胜的 skew 偏斜货流上均不满足预设判据,生产评分定义、数据门、ST、页面口径一切不动。**本文供用户清晨拍板;所有数字可复现(命令见 §六)。
>
> 落定日期 2026-07-18(承 0717 用户批准的「证据先行:数字支持才改生产」)。

## 一、背景与三个修订假设

现行生产评分(`sim/warehouse_sim.py` `make_score_fn` / `sim/fill_only.py` `_score_terms`)四项加权:效率 α·f·t、稳定 β·w·(tier/(TIERS-1))、能耗 γ·(w·tier·CELL_H)/(w_max·H_MAX)、位置保留 δ·(1-f)·(1-t)。其中 f=freq/f_max(f_max=100 常数),t=travel_time/t_max。

观感质疑两点催生修订假设:①冷门首件被送到最远角(观感过激);②skew 情景 max freq≈28 使 f_norm≤0.28,效率项疑似失活。对应:

| 变体 | 改动 | 预期收益 |
|---|---|---|
| **V1 τ** | 位置保留距离饱和:g=min(t_norm,τ)/τ,τ=0.5 | 冷门货「推到中远即止」,不再区分中远与最远角 → 首件不再送最远角 |
| **V2 dynfmax** | f_norm 分母=批次实际 max freq(替代常数 100) | 修 skew 下 f_norm 塌缩导致的效率项失活 |
| **V3 both** | 两者叠加 | — |

跑批脚本 `sim/score_whatif_sweep.py`:仅在本进程 monkeypatch `_score_terms`+`make_score_fn`,**生产文件零改动**;每 (case,seed) 完整复用 `build_shared_input`/`run_online_lane`,30 seed(2026–2055)× {skew, uniform} 两情景,SEQ/NEAR 同批只跑一次作守恒核查。

## 二、判据(0717 用户拍板的五条,全满足才改生产)

1. skew 四指标均值全不劣(容差 +0.5%);
2. skew 上 expected **或** hot20 逐 seed 配对改善 ≥20/30;
3. 首件收敛(不再 30/30 送最远角);
4. 满仓守恒(makespan/round-trip 路径逐 seed 全等)+ 违规零;
5. uniform 情景同样不劣。

## 三、实测(30 seed,均值;↑=劣化 ↓=改善,相对 baseline)

### skew(决胜偏斜货流)

| 指标 | baseline | V1 τ | V2 dynfmax | V3 both |
|---|---|---|---|---|
| expected_retrieval_s | 20.565 | 20.670 (**+0.51%**) | 20.565 (−0.00%) | 20.671 (+0.51%) |
| **hot20_retrieval_s**(主叙事) | 20.860 | 21.160 (**+1.44%**) | 20.852 (−0.04%) | 21.132 (+1.31%) |
| heavy20_mean_tier | 9.091 | 9.001 (−0.98%) | 9.111 (+0.23%) | 9.019 (−0.79%) |
| lift_work_proxy_kgm | 79997 | 80016 (+0.02%) | 80146 (+0.19%) | 80092 (+0.12%) |
| 逐 seed 配对改善 expected | — | 10/30 | 4/30 | 8/30 |
| 逐 seed 配对改善 hot20 | — | **4/30** | 4/30 | 5/30 |
| 首件落位 | (19,00)×29,(01,00)×1 | **(19,00)×30** | — | (19,00)×30 |

### uniform(对照均匀货流)

| 指标 | baseline | V1 τ | V3 both |
|---|---|---|---|
| expected_retrieval_s | 21.337 | 21.309 (−0.13%) | 21.309 (−0.13%) |
| hot20_retrieval_s | 21.101 | 21.050 (−0.24%) | 21.051 (−0.24%) |
| heavy20_mean_tier | 9.265 | 9.288 (+0.24%) | 9.287 (+0.24%) |
| 配对改善 expected / hot20 | — | 25/30 · **26/30** | 25/30 · 26/30 |
| 首件落位 | (01,00)×27,(19,00)×3 | (01,00)×26,(19,00)×4 | 同 τ |

守恒核查:两情景 makespan_s、round_trip_path_m 逐 seed 全等(`conserved=true`),违规全零(`violations_all_zero=true`)——满仓守恒下三算法占同一 267 格集合,四取货指标差异全部来自「货-格配对」。

## 四、判据逐条裁决

| 判据 | 结果 | 依据 |
|---|---|---|
| 1 skew 四指标全不劣(+0.5%) | **不满足** | hot20 +1.44%、expected +0.51%(踩容差边界外) |
| 2 skew expected 或 hot20 配对 ≥20/30 | **不满足** | expected 10/30、hot20 4/30(远低于 20) |
| 3 首件收敛 | **不满足** | τ 下首件 (19,00)×30,反比 baseline 的 29 更集中 |
| 4 守恒+违规零 | 满足 | 但为必要非充分 |
| 5 uniform 不劣 | 满足 | uniform 上 τ 反而略优 |

**五条中 1/2/3 于决胜 skew 全败 → 不改生产。**

## 五、机理(为何「合理的直觉」没兑现)

- **τ 饱和点错位**:τ=0.5 的饱和阈换算成距离是 0.5·t_max = **19 s**,对应高层(tier 高)。而冷门首件的目标 **(19,00)**(最远列、地面)travel_time=9.5 s、**t_norm=0.25**,落在饱和点**以下**——它没有被「饱和裁掉」,只是被线性重标定(0.25→0.5),相对吸引力排序未变,故首件仍 30/30 停在 (19,00)。真正被裁平的是最远角 (19,19)(t_norm=1.0),但两算法在该处保留项本就都=0,无差异。即:τ 想解决的「送最远角」现象,发生在它的饱和区之外。副作用是把中近层的保留梯度抬高,反噪 hot20 放置质量(+1.44%)。
- **dynfmax 是排序不变旋钮**:f_max 从 100 换成批次 max freq 只是对 f_norm 做全局线性缩放,不改变任意两格间的评分**相对**大小 → 放置序完全不变 → 四指标 ≈0.00%、配对改善数在 0~4/30 的噪声带。它修不了「效率项失活」,因为失活与否不影响**相对**择格。
- **情景反向**:τ 在 uniform 略有益、在 skew 有害——修订对货流分布敏感,以牺牲决胜情景换取对照情景的微利,不可取。

## 六、证据与复现

```
# 生成证据(项目根;生产文件零改动)
PYTHONIOENCODING=utf-8 python sim/score_whatif_sweep.py --seeds 30
# 关键格位 t_norm 复现(机理 §五)
PYTHONIOENCODING=utf-8 python -c "import sys;sys.path.insert(0,'sim');import warehouse_sim as ws;print('t_max=',ws.t_max_now());[print((c,t),ws.travel_time(c,t),ws.travel_time(c,t)/ws.t_max_now()) for c,t in [(19,0),(19,19)]]"
```

证据文件(已落盘):
- `l4_showcase/evidence/s3_score_whatif_skew_2026_2055.json`
- `l4_showcase/evidence/s3_score_whatif_uniform_2026_2055.json`

跑批脚本:`sim/score_whatif_sweep.py`(schema `s3-score-whatif-sweep-v1`)。

## 七、待用户拍板

- 本结论=**维持现状**(生产零改动),无需用户动作即可继续。若用户仍希望「首件不送最远角」纯观感诉求,可另开**呈现层**方案(如页面对冷门首件加「送远解说卡」——已在 #26 冷门送远解说卡实现,叙事上已正面转译该现象),而非改评分定义。此为观感 vs 评分定义的取舍,留用户定夺。
