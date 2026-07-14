# -*- coding: utf-8 -*-
"""
instance_gen.py — T1.1 实例发生器 + 30-seed 统计框架(块1地基件,U3)

职责(场景空间的单一定义点,T1.2 检测器标定 / T1.4 生命周期仿真都从这取):
  1. SCENARIOS  布局层场景注册表:货物数 × 重量/频次/体积分布,参数化生成;
                含用户质疑场景(全轻货/极小批/无画像信息)与漂移扫描(蓝图 ±30%);
                legacy 三场景直调 ws.gen_goods,与历史数字位级兼容。
  2. DYN_AXES   动态层场景轴(G2 到达 ρ / G3 画像噪声 σ / G4 故障画像),
                本文件只定义不消费——T1.4 全生命周期仿真按此扫描。
  3. 统计引擎   多 seed 复制:均值 ± 95% 置信区间半宽(t 分布);
                策略两两配对 t 检验(同 seed 同货物 = 公共随机数 CRN,天然配对);
                p 值:scipy 可用则精确,否则按硬编码临界值分级(核心零依赖)。

口径:指标沿 canonical C1-C8(ws.metrics);预占默认 sum(B1 官方答复口径);
     随机全按 seed 播种(B5);默认 30 seeds = [2026, 2027, ..., 2055]。

运行:python instance_gen.py                    # 全场景 × 30 seeds(数分钟)
     python instance_gen.py --seeds 3          # 冒烟
     python instance_gen.py --scenarios L120_skew,tiny_light
输出:out/instgen_detail.csv  逐 run 明细
     out/instgen_agg.csv     场景×策略聚合(mean/sd/ci95)
     out/instgen_pairs.csv   配对 t 检验表(显著性标记 *** ** * ns)
"""
import argparse
import csv
import math
import os
import random
import statistics as st
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import warehouse_sim as ws
import strategy_lib as sl

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")

try:
    from scipy import stats as _sps          # 可选增强:精确 p 值
except Exception:
    _sps = None


# ---------------- 1. 布局层场景注册表 ----------------
# 分布 DSL:("uniform", lo, hi) / ("tri", lo, hi, mode) / ("pareto", alpha, cap)
# legacy 字段非空时直调 ws.gen_goods(n, seed, legacy),保证与历史数字位级兼容。
_PARETO = ("pareto", 1.16, 100.0)             # 历史 skew 频次:80/20 长尾截断
SCENARIOS = {
    # -- legacy 组(历史兼容,报告主口径沿 L120_skew) --
    "L120_uniform": dict(n=120, legacy="uniform", desc="均匀基准(历史 Case A)"),
    "L120_skew":    dict(n=120, legacy="skew",    desc="高频偏态主口径(历史 Case B)"),
    "L120_heavy":   dict(n=120, legacy="heavy",   desc="重货偏多(历史 Case C)"),
    # -- 质疑组(0706 用户两问:轻货/小批量时贪心是否反超) --
    "tiny_light":   dict(n=20,  weight=("uniform", 5, 25),  freq=_PARETO,
                         vol=("uniform", 0.1, 0.9), desc="极小批全轻货(质疑场核心)"),
    "light_sparse": dict(n=60,  weight=("uniform", 5, 25),  freq=_PARETO,
                         vol=("uniform", 0.1, 0.9), desc="低密度全轻货"),
    "light_full":   dict(n=120, weight=("uniform", 5, 25),  freq=_PARETO,
                         vol=("uniform", 0.1, 0.9), desc="满批全轻货(承重约束失压)"),
    "flat_info":    dict(n=120, weight=("uniform", 5, 80),  freq=("uniform", 40, 60),
                         vol=("uniform", 0.1, 0.9), desc="频次窄幅=无画像信息(频次项失效场)"),
    # -- 压力组(密度/重量高压) --
    "dense_200":    dict(n=200, legacy="skew", desc="高密度 200 件(75% 填充)"),
    "dense_240":    dict(n=240, legacy="skew", desc="极限密度 240 件(90% 填充)"),
    "heavy_sparse": dict(n=60,  weight=("tri", 40, 80, 72), freq=_PARETO,
                         vol=("uniform", 0.1, 0.9), desc="低密度重货(承重高压+库位富余)"),
    # -- 漂移组(蓝图 U3:分布参数 ±30% 鲁棒扫描) --
    "drift_skewless": dict(n=120, weight=("uniform", 5, 80), freq=("pareto", 1.51, 100.0),
                           vol=("uniform", 0.1, 0.9), desc="偏态减弱(pareto α +30%)"),
    "drift_heavier":  dict(n=120, weight=("uniform", 20, 80), freq=_PARETO,
                           vol=("uniform", 0.1, 0.9), desc="重量整体上移(下界 +30% 量程)"),
    # -- 鲁棒组(0706 用户质疑:超载有没有考虑) --
    "illegal_mix":  dict(n=120, legacy="skew", illegal=6,
                         desc="混入 6 件非法货(3 件超重 w>100 全层不可行+3 件超容积 v>1.0)"
                              ",验证全策略优雅拒收且不崩溃(B4/A6 边界)"),
}

# ---------------- 2. 动态层场景轴(T1.4 消费;canonical G2-G4 的扫描版) ----------------
DYN_AXES = dict(
    arrival_rho=[0.35, 0.75, 0.90],    # G2 泊松到达设计负载(0.90=60s 动画实测口径)
    freq_noise_sigma=[0.0, 0.3, 0.5],  # G3 频次画像对数正态乘性噪声(0=完美画像)
    fault_mtbf_mttr=[(3000, 600)],     # G4 故障画像 (MTBF, MTTR) s,情景假设
)


def _draw(rng, spec):
    """按分布 DSL 抽一个值。"""
    kind = spec[0]
    if kind == "uniform":
        return rng.uniform(spec[1], spec[2])
    if kind == "tri":
        return rng.triangular(spec[1], spec[2], spec[3])
    if kind == "pareto":
        return min(spec[2], rng.paretovariate(spec[1]))
    raise ValueError(kind)


def gen_instance(name, seed):
    """场景名 + seed → 货物列表(确定性;legacy 走 ws.gen_goods 保位级兼容)。"""
    s = SCENARIOS[name]
    if s.get("legacy"):
        goods = ws.gen_goods(s["n"], seed, s["legacy"])
        k = s.get("illegal", 0)
        if k:                                  # 前 k 件改造成非法货(超重/超容积各半),
            rng = random.Random(seed + 31)     # 位置洗牌;全策略对其确定性拒收→placed
            idx = rng.sample(range(s["n"]), k)  # 集合仍相同,exp_t 可比性保持
            for j, i in enumerate(idx):
                g = goods[i]
                if j % 2 == 0:
                    g.weight = round(rng.uniform(101.0, 130.0), 1)   # > BASE_CAP,全层不可行
                else:
                    g.vol = round(rng.uniform(1.05, 1.30), 2)        # > CELL_VOL,超容积
        return goods
    rng = random.Random(seed)
    goods = []
    for i in range(s["n"]):                       # 每件按 w→f→v 顺序抽(同 gen_goods)
        w = round(_draw(rng, s["weight"]), 1)
        f = round(_draw(rng, s["freq"]), 2)
        v = round(_draw(rng, s["vol"]), 2)
        goods.append(ws.Good(i + 1, f"G{i+1:03d}", w, f, v))
    return goods


# ---------------- 3. 策略注册表(T1.2 新增候选时在此登记即可) ----------------
def _run(strat_name, goods, rule, seed):
    w_max = max(g.weight for g in goods)
    f_max = max(g.freq for g in goods)
    fn = ws.make_score_fn(1.0, 0.6, 0.4, 0.15, w_max, f_max)
    if strat_name == "awra":
        wh, placed, failed = ws.run_awra_ls(goods, rule, fn, w_max, f_max)
    elif strat_name == "cb":                  # Class-based storage(T1.2 新增)
        wh, placed, failed = sl.run_class_based(goods, rule)
    elif strat_name == "tob":                 # Full-turnover-based storage(T1.2 新增)
        wh, placed, failed = sl.run_full_turnover(goods, rule)
    elif strat_name == "random":
        wh, placed, failed = ws.run_online(ws.strat_random(random.Random(seed + 1)),
                                           goods, rule, fn)
    else:
        s = {"seq": ws.strat_seq, "near": ws.strat_near, "score": ws.strat_score}[strat_name]
        wh, placed, failed = ws.run_online(s, goods, rule, fn)
    return ws.metrics(wh, placed, failed)


STRATS = ["random", "seq", "near", "score", "awra", "cb", "tob"]
PAIRS = [("awra", "near"), ("awra", "score"), ("awra", "seq"), ("score", "near"),
         ("awra", "cb"), ("awra", "tob"), ("tob", "near")]
PAIR_METRICS = ["exp_t", "energy"]

# ---------------- 4. 统计引擎 ----------------
# t 双侧临界值表 {df: (α=.05, .01, .001)};查不到取更小 df(保守);∞ 行兜底。
_T_TABLE = {2: (4.303, 9.925, 31.599), 4: (2.776, 4.604, 8.610),
            9: (2.262, 3.250, 4.781), 19: (2.093, 2.861, 3.883),
            29: (2.045, 2.756, 3.659), 49: (2.010, 2.680, 3.500),
            10 ** 9: (1.960, 2.576, 3.291)}


def _t_crit(df):
    if _sps is not None:
        return tuple(_sps.t.ppf(1 - a / 2, df) for a in (0.05, 0.01, 0.001))
    known = [k for k in sorted(_T_TABLE) if k <= df] or [2]
    return _T_TABLE[known[-1]]


def ci95(vals):
    """(均值, 95%CI 半宽);n=1 时半宽为 0。"""
    m = st.mean(vals)
    if len(vals) < 2:
        return m, 0.0
    return m, _t_crit(len(vals) - 1)[0] * st.stdev(vals) / math.sqrt(len(vals))


def paired_t(a, b):
    """配对 t 检验(CRN 同 seed 配对;规范依据 Rossetti §4.4.2:CRN 下用 paired-t 而非
    两样本检验)。返回 (均差 a-b, 差值95%CI(lo,hi), t 值, p 标记, 精确 p 或 None)。
    差值 CI 按仿真界惯例报 [下界,上界],是否含 0 即显著性判读。"""
    d = [x - y for x, y in zip(a, b)]
    n = len(d)
    dm = st.mean(d)
    if n < 2 or st.pstdev(d) == 0.0:
        return dm, (dm, dm), 0.0, "ns", None
    sd = st.stdev(d)
    half = _t_crit(n - 1)[0] * sd / math.sqrt(n)
    t = dm / (sd / math.sqrt(n))
    crit = _t_crit(n - 1)
    mark = ("***" if abs(t) >= crit[2] else "**" if abs(t) >= crit[1]
            else "*" if abs(t) >= crit[0] else "ns")
    p = float(2 * _sps.t.sf(abs(t), n - 1)) if _sps is not None else None
    return dm, (dm - half, dm + half), t, mark, p


# ---------------- 5. 主流程 ----------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=30, help="复制次数(默认 30)")
    ap.add_argument("--scenarios", default="all", help="逗号分隔场景名,或 all")
    ap.add_argument("--rule", default="sum", choices=["sum", "and", "or", "linear"])
    ap.add_argument("--accel", action="store_true",
                    help="H口径:梯形加减速(A4b,ws.ACCEL=True);输出 *_accel.csv,不覆盖 legacy 匀速口径")
    a = ap.parse_args()
    if a.accel:
        ws.ACCEL = True          # F2 补跑:头条 H 口径下重算 exp_t(检测器画像基于货物属性,口径无关)
    suf = "_accel" if a.accel else ""
    seeds = [2026 + i for i in range(a.seeds)]
    names = list(SCENARIOS) if a.scenarios == "all" else a.scenarios.split(",")

    detail, agg, pairs = [], [], []
    for name in names:
        res = {s: [] for s in STRATS}             # strat -> [metrics per seed]
        for sd in seeds:
            goods = gen_instance(name, sd)
            for s in STRATS:
                m = _run(s, goods, a.rule, sd)
                res[s].append(m)
                detail.append(dict(scenario=name, seed=sd, strat=s, **m))
        for s in STRATS:
            row = dict(scenario=name, strat=s, n_runs=len(seeds))
            for k in ("exp_t", "energy", "heavy_tier", "hot_t"):
                m, h = ci95([r[k] for r in res[s]])
                row[k + "_mean"], row[k + "_ci95"] = round(m, 3), round(h, 3)
            # 相对精度自证(Law WSC2015 惯例:half-length 占点估计的百分比)
            row["exp_t_relci_pct"] = (round(row["exp_t_ci95"] / row["exp_t_mean"] * 100, 2)
                                      if row["exp_t_mean"] else 0.0)
            row["fail_mean"] = round(st.mean([r["fail"] for r in res[s]]), 2)
            row["viol_sum"] = sum(r["viol"] for r in res[s])
            agg.append(row)
        for x, y in PAIRS:
            for k in PAIR_METRICS:
                dm, (dlo, dhi), t, mark, p = paired_t([r[k] for r in res[x]],
                                                      [r[k] for r in res[y]])
                base = st.mean([r[k] for r in res[y]]) or 1.0
                pairs.append(dict(
                    scenario=name, metric=k, a=x, b=y,
                    diff_mean=round(dm, 3), diff_pct=round(dm / base * 100, 2),
                    diff_ci_lo=round(dlo, 3), diff_ci_hi=round(dhi, 3),
                    ci_covers_0=("yes" if dlo <= 0.0 <= dhi else "no"),
                    t=round(t, 2), sig=mark,
                    p=(f"{p:.2e}" if p is not None else ""),
                    fail_a=round(st.mean([r["fail"] for r in res[x]]), 2),
                    fail_b=round(st.mean([r["fail"] for r in res[y]]), 2)))

    os.makedirs(OUT, exist_ok=True)
    for fname, rows in ((f"instgen_detail{suf}.csv", detail), (f"instgen_agg{suf}.csv", agg),
                        (f"instgen_pairs{suf}.csv", pairs)):
        with open(os.path.join(OUT, fname), "w", newline="", encoding="utf-8-sig") as fp:
            w = csv.DictWriter(fp, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)

    # ---- 控制台摘要:每场景 exp_t 排名 + 关键配对 ----
    print(f"{'场景':<15}{'最优策略':<8}{'exp_t 均值±CI95':<22}"
          f"{'awra-near 差%':>13}{'显著':>5}  {'near 反超?'}")
    print("-" * 78)
    for name in names:
        rows = [r for r in agg if r["scenario"] == name]
        best = min(rows, key=lambda r: r["exp_t_mean"])
        pr = next(r for r in pairs if r["scenario"] == name
                  and r["a"] == "awra" and r["b"] == "near" and r["metric"] == "exp_t")
        flip = "← 是" if pr["diff_mean"] > 0 else ""
        print(f"{name:<15}{best['strat']:<8}"
              f"{best['exp_t_mean']:>8.2f} ± {best['exp_t_ci95']:<8.2f}    "
              f"{pr['diff_pct']:>10.2f}%{pr['sig']:>5}  {flip}")
    viol = sum(r["viol_sum"] for r in agg)
    print(f"\n全矩阵违规总数 = {viol}(必须为 0);{len(names)} 场景 × {len(seeds)} seeds"
          f" × {len(STRATS)} 策略 = {len(detail)} runs")
    print(f"CSV:{OUT}\\instgen_detail.csv / instgen_agg.csv / instgen_pairs.csv")
    if _sps is None:
        print("注:scipy 不可用,p 值按临界值分级(*/**/***),CI 用硬编码 t 表。")


if __name__ == "__main__":
    main()
