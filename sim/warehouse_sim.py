# -*- coding: utf-8 -*-
"""
warehouse_sim.py — 立体仓储仓位优化仿真 v2(零依赖,任何 Python 3.8+ 直接跑)

场景 = 决赛题面:20列 x 20层 = 400 仓位;底层承重系数 1.0,每升一层 -0.02;
坐标能被 3 整除的仓位预设占用(解读方式可选);货物从 I/O 口 (0,0) 出发存入。

五种策略同一批货物对比(分两组):
  [在线组] 货物按到达顺序逐件决策(决赛交互场景,PLC 实时可跑)
    random 随机基线 —— 随机挑一个可行空位(最低基线)
    seq    顺序基线 —— 从 (0,0) 起找第一个可行空位(题面"连续存放"字面做法)
    near   就近贪心 —— 行程时间最小的可行空位(单目标)
    score  多目标评分 —— 高频放近 + 重货放低 + 能耗 + 位置价值预留(主线在线版)
  [批量组] 全部货物已知,整批优化(初赛验证上界,对应 AWRA-LS)
    awra   AWRA-LS —— Rank(优先级排序)→ Assign(逐件评分选位)→ Local Search(重定位+交换)

口径(与 docs/canonical_assumptions.md 一致):
  行程时间 = 切比雪夫 max(x/vx, y/vy)   —— 堆垛机水平/垂直双电机同时运动(AS/RS 标准)
  路径长度 = 曼哈顿 x位移 + y位移        —— 物理走线长度,决赛统计栏用
  入库总时间 = 双程(I/O→仓位→I/O)累计;装卸时间暂不计(canonical 待定项)

用法示例:
  python warehouse_sim.py                        # 默认 120 件货,seed=2026
  python warehouse_sim.py --goods 200 --seed 7 --rule linear
  python warehouse_sim.py --map --csv out        # 打印占用图 + 导出 CSV 到 out/
"""
import argparse
import csv
import math
import os
import random
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# ---------------- 参数(与 canonical_assumptions 对应) ----------------
COLS, TIERS = 20, 20          # A1: 20列(x 水平) x 20层(y 垂直)
CELL_W, CELL_H = 1.0, 1.0     # A2: 仓位尺寸 1m
VX, VY = 2.0, 0.5             # A4: 堆垛机水平/垂直最大速度 m/s
AX, AY = 0.5, 0.3             # A4b(L1): 水平/垂直加减速 m/s²(默认待确认,行业典型量级)
ACCEL = False                 # L1 开关:False=匀速(基础口径,历史数字) True=梯形速度曲线
BASE_CAP = 100.0              # A6: 底层仓位限重 kg(层k限重 = (1-0.02k)*BASE_CAP)
CELL_VOL = 1.0                # B4: 仓位容积 m^3

H_MAX = (TIERS - 1) * CELL_H


def axis_time(d, vmax, acc):
    """L1 单轴行程时间:对称加减速、静止起止的梯形/三角速度曲线。
    d ≥ vmax²/acc(能到峰速):t = d/vmax + vmax/acc(梯形,比匀速恒多 vmax/acc)
    d < vmax²/acc(到不了峰速):t = 2·√(d/acc)(三角)
    匀速模型系统性低估短程时间——近位并不"免费",这正是本升级的建模意义。"""
    if d <= 0.0:
        return 0.0
    if d >= vmax * vmax / acc:
        return d / vmax + vmax / acc
    return 2.0 * math.sqrt(d / acc)


def travel_time_between(c0, t0, c1, t1):
    """任意两点间切比雪夫行程时间(L2 双命令周期用;ST 侧 FC_CalcTravelTime 同签名)。
    ACCEL=False 匀速(基础口径);True 梯形速度曲线(L1 工程口径,A4b)。"""
    dx, dy = abs(c1 - c0) * CELL_W, abs(t1 - t0) * CELL_H
    if ACCEL:
        return max(axis_time(dx, VX, AX), axis_time(dy, VY, AY))
    return max(dx / VX, dy / VY)


def travel_time(col, tier):
    """I/O口(0,0)到仓位的行程时间(单程),= travel_time_between(0,0,col,tier)。"""
    return travel_time_between(0, 0, col, tier)


def t_max_now():
    """全库最远仓位单程时间(评分归一分母,跟随当前运动模型口径)。"""
    return travel_time(COLS - 1, TIERS - 1)


T_MAX = t_max_now()           # 兼容旧引用(匀速口径下的常量;评分工厂内部用 t_max_now)


def tier_cap(tier):
    """层承重:底层(tier=0)系数1.0,每层递减0.02(题面给定)。"""
    return (1.0 - 0.02 * tier) * BASE_CAP


def path_len(col, tier):
    """曼哈顿路径长度(单程):物理走线 = 水平位移 + 垂直位移。
    注意:路径长度对横/竖等权,不同策略的路径总和可能相同而时间差数倍
    (垂直轴慢4倍)——这正是优化目标必须取时间口径的原因(实验可复现)。"""
    return col * CELL_W + tier * CELL_H


def preoccupied(col, tier, rule):
    """B1 预占用解读(原题面歧义,四种都能跑):
    sum    : x+y 之和能被3整除(133格)—— **官方答复口径(2026-07-06),现行默认**
    and    : x、y 都能被3整除(49格)   —— 资料包方案A(0703-0705 历史主口径)
    linear : 仓位线性编号能被3整除(134格)—— 资料包方案B
    or     : x 或 y 能被3整除(231格)
    """
    if rule == "sum":
        return (col + tier) % 3 == 0
    if rule == "and":
        return col % 3 == 0 and tier % 3 == 0
    if rule == "or":
        return col % 3 == 0 or tier % 3 == 0
    if rule == "linear":
        return (col * TIERS + tier) % 3 == 0
    raise ValueError(rule)


# ---------------- 货物 ----------------
class Good:
    __slots__ = ("gid", "name", "weight", "freq", "vol")

    def __init__(self, gid, name, weight, freq, vol):
        self.gid, self.name = gid, name
        self.weight, self.freq, self.vol = weight, freq, vol


def gen_goods(n, seed, case="skew"):
    """B3/B5:属性随机但按 seed 确定性生成(策略间公平、结果可复现)。
    三类分布(资料包 §8.3 测试数据建议;默认 skew 与历史数字兼容):
      uniform Case A 均匀:重量/频次/体积全均匀(基准场景)
      skew    Case B 高频偏态:频次帕累托 80/20(电商爆品场景,默认)
      heavy   Case C 重货偏多:重量偏向高值(承重约束高压场景)
    """
    rng = random.Random(seed)
    goods = []
    for i in range(n):
        if case == "heavy":
            w = round(max(5.0, min(80.0, rng.triangular(5.0, 80.0, 72.0))), 1)
        else:
            w = round(rng.uniform(5.0, 80.0), 1)
        if case == "uniform":
            f = round(rng.uniform(1.0, 100.0), 2)
        else:
            f = min(100.0, round(rng.paretovariate(1.16), 2))   # 长尾截断到100
        v = round(rng.uniform(0.1, 0.9), 2)
        goods.append(Good(i + 1, f"G{i+1:03d}", w, f, v))
    return goods


# ---------------- 仓库 ----------------
class Warehouse:
    def __init__(self, rule):
        # grid[col][tier] = None(空) / "PRE"(预占) / Good
        self.grid = [[None] * TIERS for _ in range(COLS)]
        for c in range(COLS):
            for t in range(TIERS):
                if preoccupied(c, t, rule):
                    self.grid[c][t] = "PRE"

    def feasible(self, col, tier, good):
        """边界判断(将来 1:1 移植进 ST 功能块 FC_CheckFeasible):
        空位 + 不超该层限重 + 不超容积。"""
        return (self.grid[col][tier] is None
                and good.weight <= tier_cap(tier)
                and good.vol <= CELL_VOL)

    def fits(self, col, tier, good):
        """不查占用、只查物理约束(局部搜索换位时用:目标位即将腾出)。"""
        return good.weight <= tier_cap(tier) and good.vol <= CELL_VOL

    def empty_feasible_slots(self, good):
        return [(c, t) for c in range(COLS) for t in range(TIERS)
                if self.feasible(c, t, good)]

    def put(self, col, tier, good):
        assert self.grid[col][tier] is None
        self.grid[col][tier] = good

    def remove(self, col, tier):
        g = self.grid[col][tier]
        assert isinstance(g, Good)
        self.grid[col][tier] = None
        return g


# ---------------- 场景自适应权重策略表(A1/T11,2026-07-04 拍板①采纳) ----------------
# 来源:adaptive_weights.py 18场景×15组合×2seeds 标定 + verify_policy.py 留出seed泛化验证通过
# (批量留出增益均值 6.88% 全正,违规0)。此表是"已定口径"的一部分,与 plc/08 生成文件同源;
# 重标定必须两处同步并重跑验证。键:(密度档, 分布, 模式) → (δ, β+γ)。
WEIGHT_POLICY = {
    (120, "uniform", "online"): (0.20, 0.6), (120, "uniform", "batch"): (0.15, 0.6),
    (120, "skew", "online"): (0.10, 1.0),    (120, "skew", "batch"): (0.05, 0.6),
    (120, "heavy", "online"): (0.10, 0.6),   (120, "heavy", "batch"): (0.10, 0.6),
    (240, "uniform", "online"): (0.20, 0.6), (240, "uniform", "batch"): (0.15, 0.6),
    (240, "skew", "online"): (0.20, 0.6),    (240, "skew", "batch"): (0.05, 0.6),
    (240, "heavy", "online"): (0.20, 0.6),   (240, "heavy", "batch"): (0.15, 0.6),
    (330, "uniform", "online"): (0.20, 0.6), (330, "uniform", "batch"): (0.20, 0.6),
    (330, "skew", "online"): (0.20, 0.6),    (330, "skew", "batch"): (0.05, 0.6),
    (330, "heavy", "online"): (0.20, 0.6),   (330, "heavy", "batch"): (0.20, 0.6),
}


def lookup_weights(n_goods, case, mode):
    """场景→权重查表(PLC 侧对应 plc/08 的 aPolicyDelta/aPolicyBG)。
    密度档:<180→120档,<285→240档,否则330档;未知场景回落固定默认。"""
    dens = 120 if n_goods < 180 else (240 if n_goods < 285 else 330)
    return WEIGHT_POLICY.get((dens, case, mode), (0.15, 1.0))


# ---------------- 多目标评分(在线 score 与批量 AWRA-LS 共用同一目标函数) ----------------
def make_score_fn(alpha, beta, gamma, delta, w_max, f_max):
    """score = α·(频次/最大)·(时间/最大)   —— 高频货放远处要罚(效率)
             + β·(重量/最大)·(层高/最大)   —— 重货放高层要罚(稳定/安全)
             + γ·(重量·高度)/(最大做功)    —— 提升做功要罚(能耗,绿色指标)
             + δ·(1-频次归一)·(1-时间归一) —— 冷门货占近位要罚(位置价值预留)
    第四项是在线决策的关键:近位是稀缺资源,冷门货占了热门货就没了;
    没有它,在线评分会退化成"就近贪心"(δ=0 时占位集合与 near 完全相同,实验可复现)。
    δ 初标定 0.15(单 seed 甜点:同占位集合内配对更优,W2 做多 seed 精标)。"""
    tmax = t_max_now()                      # 归一分母跟随当前运动模型口径(L1)
    def score(good, col, tier):
        t_norm = travel_time(col, tier) / tmax
        f_norm = good.freq / f_max
        eff = f_norm * t_norm
        stab = (good.weight / w_max) * (tier / (TIERS - 1))
        energy = (good.weight * tier * CELL_H) / (w_max * H_MAX)
        resv = (1.0 - f_norm) * (1.0 - t_norm)
        return alpha * eff + beta * stab + gamma * energy + delta * resv
    return score


# ---------------- 在线组策略(逐件到达,不知未来) ----------------
def strat_random(rng):
    def strat(wh, good, score_fn):
        slots = wh.empty_feasible_slots(good)
        return rng.choice(slots) if slots else None
    return strat


def strat_seq(wh, good, score_fn):
    """顺序基线:从(0,0)起按 列->层 顺序第一个可行位(题面"连续存放"字面解)。"""
    for c in range(COLS):
        for t in range(TIERS):
            if wh.feasible(c, t, good):
                return c, t
    return None


def strat_near(wh, good, score_fn):
    """就近贪心:行程时间最小的可行位;平局取更低层、更小列(确定性)。"""
    slots = wh.empty_feasible_slots(good)
    if not slots:
        return None
    return min(slots, key=lambda s: (travel_time(*s), s[1], s[0]))


def strat_score(wh, good, score_fn):
    """多目标评分(在线主线):取 score 最小的可行位。"""
    slots = wh.empty_feasible_slots(good)
    if not slots:
        return None
    return min(slots, key=lambda s: (score_fn(good, *s), travel_time(*s), s[1], s[0]))


def run_online(strategy, goods, rule, score_fn):
    wh = Warehouse(rule)
    placed, failed = [], []
    for g in goods:                      # 按到达顺序
        pos = strategy(wh, g, score_fn)
        if pos is None:
            failed.append(g)
            continue
        wh.put(pos[0], pos[1], g)
        placed.append((g, pos))
    return wh, placed, failed


# ---------------- 批量组:AWRA-LS(Rank -> Assign -> Local Search) ----------------
def run_awra_ls(goods, rule, score_fn, w_max, f_max,
                lam=(0.50, 0.35, 0.15), max_iter=5):
    """自适应加权排序分配+局部搜索(资料包推荐架构,对应文献 Rank-and-Assign 思想):
    Rank   先按优先级排序:高频、重、大体积优先(λ=0.50/0.35/0.15),
           把"随机到达"转成"重要者先挑",天然缓解在线贪心的先占问题;
    Assign 按序逐件选 score 最小的可行位(与在线 score 同一目标函数,便于比 gap);
    LS     两类邻域迭代改进:①重定位(移到更优空位)②成对交换(互换后总分下降),
           每步换位前重查承重/容积约束(边界清单要求),直至无改进或达 max_iter 轮。
    """
    v_max = max(g.vol for g in goods)
    l1, l2, l3 = lam

    def priority(g):
        return (l1 * g.freq / f_max + l2 * g.weight / w_max + l3 * g.vol / v_max)

    order = sorted(goods, key=lambda g: (-priority(g), g.gid))   # Rank(平局按序号,确定性)

    wh = Warehouse(rule)
    pos_of, failed = {}, []
    for g in order:                                               # Assign
        slots = wh.empty_feasible_slots(g)
        if not slots:
            failed.append(g)
            continue
        best = min(slots, key=lambda s: (score_fn(g, *s), travel_time(*s), s[1], s[0]))
        wh.put(best[0], best[1], g)
        pos_of[g.gid] = best

    placed_goods = [g for g in order if g.gid in pos_of]

    for _ in range(max_iter):                                     # Local Search
        improved = False
        # ① 重定位:移到能降分的空可行位
        for g in placed_goods:
            c0, t0 = pos_of[g.gid]
            cur = score_fn(g, c0, t0)
            slots = wh.empty_feasible_slots(g)
            if not slots:
                continue
            best = min(slots, key=lambda s: score_fn(g, *s))
            if score_fn(g, *best) < cur - 1e-12:
                wh.remove(c0, t0)
                wh.put(best[0], best[1], g)
                pos_of[g.gid] = best
                improved = True
        # ② 成对交换:互换可行且总分下降
        n = len(placed_goods)
        for i in range(n):
            gi = placed_goods[i]
            for j in range(i + 1, n):
                gj = placed_goods[j]
                pi, pj = pos_of[gi.gid], pos_of[gj.gid]
                if not (wh.fits(pj[0], pj[1], gi) and wh.fits(pi[0], pi[1], gj)):
                    continue                                      # 交换后必须仍满足承重/容积
                old = score_fn(gi, *pi) + score_fn(gj, *pj)
                new = score_fn(gi, *pj) + score_fn(gj, *pi)
                if new < old - 1e-12:
                    wh.grid[pi[0]][pi[1]], wh.grid[pj[0]][pj[1]] = gj, gi
                    pos_of[gi.gid], pos_of[gj.gid] = pj, pi
                    improved = True
        if not improved:
            break

    placed = [(g, pos_of[g.gid]) for g in goods if g.gid in pos_of]  # 按原到达序输出
    return wh, placed, failed


# ---------------- 评估 ----------------
def metrics(wh, placed, failed):
    tot_time2 = sum(2 * travel_time(c, t) for _, (c, t) in placed)      # C1 双程
    tot_path2 = sum(2 * path_len(c, t) for _, (c, t) in placed)         # C5 损耗代理
    f_sum = sum(g.freq for g, _ in placed) or 1.0
    exp_t = sum(g.freq * travel_time(c, t) for g, (c, t) in placed) / f_sum  # C3
    energy = sum(g.weight * t * CELL_H for g, (_, t) in placed)         # C4 kg·m
    w_sum = sum(g.weight for g, _ in placed) or 1.0
    cog = sum(g.weight * t * CELL_H for g, (_, t) in placed) / w_sum    # C6
    hot = sorted(placed, key=lambda pg: -pg[0].freq)[:max(1, len(placed) // 5)]
    hot_t = sum(travel_time(c, t) for _, (c, t) in hot) / len(hot)      # 高频前20%均时
    heavy = sorted(placed, key=lambda pg: -pg[0].weight)[:max(1, len(placed) // 5)]
    heavy_tier = sum(t for _, (_, t) in heavy) / len(heavy)             # 重货前20%均层
    viol = sum(1 for g, (c, t) in placed
               if g.weight > tier_cap(t) or g.vol > CELL_VOL)           # C8 复查
    used = sum(1 for c in range(COLS) for t in range(TIERS) if wh.grid[c][t])
    return dict(n=len(placed), fail=len(failed), tot_time2=tot_time2,
                exp_t=exp_t, hot_t=hot_t, heavy_tier=heavy_tier, energy=energy,
                cog=cog, path=tot_path2, util=used / (COLS * TIERS), viol=viol)


def ascii_map(wh, goods_sorted_freq):
    """占用图:#=预占 .=空 A/B/C=按访问频次分档的货(A最热)。顶层在上。"""
    n = len(goods_sorted_freq)
    rank = {g.gid: i for i, g in enumerate(goods_sorted_freq)}
    lines = []
    for t in range(TIERS - 1, -1, -1):
        row = []
        for c in range(COLS):
            cell = wh.grid[c][t]
            if cell is None:
                row.append(".")
            elif cell == "PRE":
                row.append("#")
            else:
                r = rank[cell.gid] / max(1, n - 1)
                row.append("A" if r < 0.2 else ("B" if r < 0.5 else "C"))
        lines.append(f"{t:2d}|" + "".join(row))
    lines.append("   ^ (0,0)=I/O口")
    lines.append("   " + "".join(str(c % 10) for c in range(COLS)) + "  (列号个位)")
    return "\n".join(lines)


# ---------------- CSV 导出(报告数据源,utf-8-sig 便于 Excel 直开) ----------------
def export_csv(outdir, results, args):
    os.makedirs(outdir, exist_ok=True)
    sp = os.path.join(outdir, "summary_metrics.csv")
    with open(sp, "w", newline="", encoding="utf-8-sig") as fp:
        w = csv.writer(fp)
        w.writerow(["strategy", "mode", "n_placed", "n_failed", "total_time_2way_s",
                    "expected_retrieval_s", "hot20_avg_s", "heavy20_avg_tier",
                    "energy_kgm", "cog_m", "path_2way_m", "utilization", "violations",
                    "goods", "seed", "rule", "alpha", "beta", "gamma", "delta"])
        for name, mode, _, m in results:
            w.writerow([name, mode, m["n"], m["fail"], round(m["tot_time2"], 1),
                        round(m["exp_t"], 3), round(m["hot_t"], 3),
                        round(m["heavy_tier"], 2), round(m["energy"], 0),
                        round(m["cog"], 3), round(m["path"], 0),
                        round(m["util"], 4), m["viol"],
                        args.goods, args.seed, args.rule,
                        args.alpha, args.beta, args.gamma, args.delta])
    for name, mode, placed, _ in results:
        ap = os.path.join(outdir, f"assignment_{name}.csv")
        with open(ap, "w", newline="", encoding="utf-8-sig") as fp:
            w = csv.writer(fp)
            w.writerow(["good_id", "name", "weight_kg", "freq", "volume_m3",
                        "col", "tier", "travel_time_1way_s", "path_len_1way_m"])
            for g, (c, t) in placed:
                w.writerow([g.gid, g.name, g.weight, g.freq, g.vol, c, t,
                            round(travel_time(c, t), 3), round(path_len(c, t), 1)])
    return sp


def main():
    ap = argparse.ArgumentParser(description="立体仓储仓位优化仿真 v2")
    ap.add_argument("--goods", type=int, default=120, help="货物数量(默认120)")
    ap.add_argument("--seed", type=int, default=2026, help="随机种子(默认2026,B5)")
    ap.add_argument("--rule", choices=["and", "or", "linear", "sum"], default="and",
                    help="预占用解读(B1,默认and=x,y都被3整除)")
    ap.add_argument("--case", choices=["uniform", "skew", "heavy"], default="skew",
                    help="货物分布:A均匀/B高频偏态(默认)/C重货偏多")
    ap.add_argument("--accel", action="store_true",
                    help="L1:启用梯形速度曲线(加减速)口径;默认匀速(历史口径)")
    ap.add_argument("--adaptive", action="store_true",
                    help="A1:场景自适应权重查表(报告主口径 H = --accel --adaptive)")
    ap.add_argument("--alpha", type=float, default=1.0, help="评分权重:效率项")
    ap.add_argument("--beta", type=float, default=0.6, help="评分权重:稳定项")
    ap.add_argument("--gamma", type=float, default=0.4, help="评分权重:能耗项")
    ap.add_argument("--delta", type=float, default=0.15, help="评分权重:位置价值预留项")
    ap.add_argument("--ls-iter", type=int, default=5, help="AWRA-LS 局部搜索最大轮数")
    ap.add_argument("--map", action="store_true", help="打印 near/score/awra 占用图")
    ap.add_argument("--csv", metavar="DIR", default=None,
                    help="导出 CSV 到指定目录(summary+各策略assignment)")
    a = ap.parse_args()

    global ACCEL
    if a.accel:
        ACCEL = True

    goods = gen_goods(a.goods, a.seed, a.case)
    w_max = max(g.weight for g in goods)
    f_max = max(g.freq for g in goods)
    by_freq = sorted(goods, key=lambda g: -g.freq)
    if a.adaptive:
        d_on, bg_on = lookup_weights(a.goods, a.case, "online")
        d_ba, bg_ba = lookup_weights(a.goods, a.case, "batch")
        score_fn = make_score_fn(1.0, bg_on / 2, bg_on / 2, d_on, w_max, f_max)
        score_fn_batch = make_score_fn(1.0, bg_ba / 2, bg_ba / 2, d_ba, w_max, f_max)
    else:
        score_fn = make_score_fn(a.alpha, a.beta, a.gamma, a.delta, w_max, f_max)
        score_fn_batch = score_fn

    pre = sum(1 for c in range(COLS) for t in range(TIERS) if preoccupied(c, t, a.rule))
    motion = (f"梯形加减速(ax={AX} ay={AY})" if ACCEL else "匀速") + "·切比雪夫"
    print(f"场景:{COLS}列x{TIERS}层={COLS*TIERS}仓位 | 预占用[{a.rule}]={pre}格 "
          f"| 货物{a.goods}件 seed={a.seed} | vx={VX} vy={VY} 底层限重{BASE_CAP}kg")
    print(f"口径:时间={motion}双程,路径=曼哈顿双程,能耗=Σ重量x高度(kg·m);"
          f"权重 α={a.alpha} β={a.beta} γ={a.gamma} δ={a.delta}\n")

    results = []
    online = [("random", strat_random(random.Random(a.seed + 1))),
              ("seq", strat_seq), ("near", strat_near), ("score", strat_score)]
    for name, fn in online:
        wh, placed, failed = run_online(fn, goods, a.rule, score_fn)
        results.append((name, "在线", placed, metrics(wh, placed, failed)))
        if a.map and name in ("near", "score"):
            globals().setdefault("_maps", []).append((name, wh))
    wh, placed, failed = run_awra_ls(goods, a.rule, score_fn_batch, w_max, f_max,
                                     max_iter=a.ls_iter)
    results.append(("awra", "批量", placed, metrics(wh, placed, failed)))
    if a.map:
        globals().setdefault("_maps", []).append(("awra", wh))

    label = {"random": "random 随机基线", "seq": "seq    顺序基线",
             "near": "near   就近贪心", "score": "score  多目标评分",
             "awra": "awra   AWRA-LS"}
    hdr = (f"{'策略':<16}{'组':<4}{'入库':>4}{'失败':>4}{'总时(s)':>9}{'期望取货(s)':>12}"
           f"{'热货均时(s)':>12}{'重货均层':>9}{'能耗(kg·m)':>11}{'重心(m)':>8}{'违规':>5}")
    print(hdr)
    print("-" * len(hdr))
    for name, mode, _, m in results:
        print(f"{label[name]:<16}{mode:<4}{m['n']:>4}{m['fail']:>4}{m['tot_time2']:>9.0f}"
              f"{m['exp_t']:>12.2f}{m['hot_t']:>12.2f}{m['heavy_tier']:>9.2f}"
              f"{m['energy']:>11.0f}{m['cog']:>8.2f}{m['viol']:>5}")

    mm = {name: m for name, _, _, m in results}
    def drop(x, y):
        return (1 - y / x) * 100
    print(f"\nscore vs near(在线内):期望取货 {mm['near']['exp_t']:.2f}→{mm['score']['exp_t']:.2f}s"
          f"(降 {drop(mm['near']['exp_t'], mm['score']['exp_t']):.1f}%),"
          f"热货均时 {mm['near']['hot_t']:.2f}→{mm['score']['hot_t']:.2f}s"
          f"(降 {drop(mm['near']['hot_t'], mm['score']['hot_t']):.1f}%)")
    print(f"awra vs score(批量上界):期望取货 {mm['score']['exp_t']:.2f}→{mm['awra']['exp_t']:.2f}s"
          f"(降 {drop(mm['score']['exp_t'], mm['awra']['exp_t']):.1f}%),"
          f"能耗 {mm['score']['energy']:.0f}→{mm['awra']['energy']:.0f} kg·m"
          f"(降 {drop(mm['score']['energy'], mm['awra']['energy']):.1f}%)")
    print(f"awra vs seq(对题面基线):期望取货 {mm['seq']['exp_t']:.2f}→{mm['awra']['exp_t']:.2f}s"
          f"(降 {drop(mm['seq']['exp_t'], mm['awra']['exp_t']):.1f}%),"
          f"能耗降 {drop(mm['seq']['energy'], mm['awra']['energy']):.1f}%")

    if a.map:
        for name, wh_m in globals().get("_maps", []):
            print(f"\n[{label[name].strip()}] 占用图(#预占 .空 A热 B温 C冷,顶层在上):")
            print(ascii_map(wh_m, by_freq))

    if a.csv:
        p = export_csv(a.csv, results, a)
        print(f"\nCSV 已导出:{p} + 各策略 assignment_*.csv")

    print("\nTODO(W2):δ多seed精标、NSGA-II Pareto前沿对照、matplotlib图表、装卸时间/加减速模型")


if __name__ == "__main__":
    main()
