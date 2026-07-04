# -*- coding: utf-8 -*-
"""
nsga2_baseline.py — 手写轻量 NSGA-II 对照实验(W-004,零第三方依赖)
目的:用多目标进化算法画出(期望取货时间, 能耗)的 Pareto 前沿,
     度量轻量 AWRA-LS 离"理论可达最优"有多近——算法创新性(10%)的证据页。
建模:染色体 = 每件货物的仓位分配(全排列式指派);可行性由构造与修复保证
     (仓位唯一占用 + 层限重 + 容积;预占用格不可用)。
双目标:f1 = Σ(freq·t)/Σfreq(期望取货,切比雪夫单程,C3 口径,越小越好)
       f2 = Σ(weight·h)(能耗代理,C4 口径,越小越好)
算法:快速非支配排序 + 拥挤度 + 二元锦标赛 + 均匀交叉(冲突修复)+ 重放变异。
运行:python nsga2_baseline.py            (种群60 × 200代,约1-2分钟,seed固定)
     python nsga2_baseline.py --quick    (30×40 逻辑自检)
输出:out/pareto_front.csv + figs/fig6_pareto前沿.png + 控制台结论(按事实写)。
"""
import argparse
import csv
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import warehouse_sim as ws

HERE = os.path.dirname(os.path.abspath(__file__))
SEED, N_GOODS, RULE = 2026, 120, "and"


# ---------------- 问题定义 ----------------
class Problem:
    def __init__(self, goods, rule):
        self.goods = goods
        self.f_sum = sum(g.freq for g in goods)
        # 每件货可行仓位集(物理约束仅取决于层:体积恒≤1.0 可行,重量决定最高层)
        base = [(c, t) for c in range(ws.COLS) for t in range(ws.TIERS)
                if not ws.preoccupied(c, t, rule)]
        self.slots_of = []
        for g in goods:
            self.slots_of.append([s for s in base
                                  if g.weight <= ws.tier_cap(s[1]) and g.vol <= ws.CELL_VOL])
        self.t_cache = {s: ws.travel_time(*s) for s in base}

    def evaluate(self, chrom):
        f1 = sum(g.freq * self.t_cache[chrom[i]] for i, g in enumerate(self.goods)) / self.f_sum
        f2 = sum(g.weight * chrom[i][1] * ws.CELL_H for i, g in enumerate(self.goods))
        return (f1, f2)

    def random_individual(self, rng):
        """随机可行个体:随机顺序逐件挑随机可行空位。"""
        used, chrom = set(), [None] * len(self.goods)
        order = list(range(len(self.goods)))
        rng.shuffle(order)
        for i in order:
            cand = [s for s in self.slots_of[i] if s not in used]
            if not cand:
                return None                          # 极端不可行(本场景不会发生)
            s = rng.choice(cand)
            chrom[i] = s
            used.add(s)
        return chrom

    def repair(self, chrom, rng):
        """修复重复占用:后出现的冲突货物重挑可行空位。"""
        used, dup = set(), []
        for i, s in enumerate(chrom):
            if s in used:
                dup.append(i)
            else:
                used.add(s)
        for i in dup:
            cand = [s for s in self.slots_of[i] if s not in used]
            s = rng.choice(cand)
            chrom[i] = s
            used.add(s)
        return chrom


# ---------------- NSGA-II 核心 ----------------
def dominates(a, b):
    return (a[0] <= b[0] and a[1] <= b[1]) and (a[0] < b[0] or a[1] < b[1])


def fast_nondominated_sort(F):
    n = len(F)
    S = [[] for _ in range(n)]
    cnt = [0] * n
    fronts = [[]]
    for p in range(n):
        for q in range(n):
            if p == q:
                continue
            if dominates(F[p], F[q]):
                S[p].append(q)
            elif dominates(F[q], F[p]):
                cnt[p] += 1
        if cnt[p] == 0:
            fronts[0].append(p)
    i = 0
    while fronts[i]:
        nxt = []
        for p in fronts[i]:
            for q in S[p]:
                cnt[q] -= 1
                if cnt[q] == 0:
                    nxt.append(q)
        i += 1
        fronts.append(nxt)
    return fronts[:-1]


def crowding(front, F):
    d = {i: 0.0 for i in front}
    for m in range(2):
        srt = sorted(front, key=lambda i: F[i][m])
        d[srt[0]] = d[srt[-1]] = float("inf")
        span = F[srt[-1]][m] - F[srt[0]][m] or 1.0
        for k in range(1, len(srt) - 1):
            d[srt[k]] += (F[srt[k + 1]][m] - F[srt[k - 1]][m]) / span
    return d


def nsga2(prob, pop_size, gens, rng, log_every=50):
    pop = []
    while len(pop) < pop_size:
        ind = prob.random_individual(rng)
        if ind:
            pop.append(ind)
    F = [prob.evaluate(c) for c in pop]

    for gen in range(gens):
        fronts = fast_nondominated_sort(F)
        rank = {}
        for r, fr in enumerate(fronts):
            for i in fr:
                rank[i] = r
        crowd = {}
        for fr in fronts:
            crowd.update(crowding(fr, F))

        def tourney():
            a, b = rng.randrange(len(pop)), rng.randrange(len(pop))
            if (rank[a], -crowd[a]) < (rank[b], -crowd[b]):
                return pop[a]
            return pop[b]

        children = []
        while len(children) < pop_size:
            p1, p2 = tourney(), tourney()
            child = [p1[i] if rng.random() < 0.5 else p2[i] for i in range(len(p1))]
            child = prob.repair(child, rng)
            # 变异:重放 k 件
            for _ in range(3):
                if rng.random() < 0.9:
                    i = rng.randrange(len(child))
                    used = set(child)
                    cand = [s for s in prob.slots_of[i] if s not in used or s == child[i]]
                    child[i] = rng.choice(cand)
            children.append(child)

        # 精英合并 + 环境选择
        allpop = pop + children
        allF = F + [prob.evaluate(c) for c in children]
        fronts = fast_nondominated_sort(allF)
        newpop, newF = [], []
        for fr in fronts:
            if len(newpop) + len(fr) <= pop_size:
                newpop += [allpop[i] for i in fr]
                newF += [allF[i] for i in fr]
            else:
                cd = crowding(fr, allF)
                rest = sorted(fr, key=lambda i: -cd[i])[:pop_size - len(newpop)]
                newpop += [allpop[i] for i in rest]
                newF += [allF[i] for i in rest]
                break
        pop, F = newpop, newF
        if (gen + 1) % log_every == 0:
            f0 = fast_nondominated_sort(F)[0]
            best1 = min(F[i][0] for i in f0)
            best2 = min(F[i][1] for i in f0)
            print(f"  gen {gen+1}/{gens}: 前沿 {len(f0)} 点,best f1={best1:.3f} f2={best2:.0f}")
    front_idx = fast_nondominated_sort(F)[0]
    front = sorted({F[i] for i in front_idx})
    return front


# ---------------- 主流程 ----------------
def strategy_points(goods):
    """五策略在同一双目标平面上的落点(与 NSGA-II 同口径)。"""
    import random as _r
    w_max = max(g.weight for g in goods)
    f_max = max(g.freq for g in goods)
    fn = ws.make_score_fn(1.0, 0.6, 0.4, 0.15, w_max, f_max)
    pts = {}
    for name, strat in [("random", ws.strat_random(_r.Random(SEED + 1))),
                        ("seq", ws.strat_seq), ("near", ws.strat_near),
                        ("score", ws.strat_score)]:
        wh, placed, failed = ws.run_online(strat, goods, RULE, fn)
        m = ws.metrics(wh, placed, failed)
        pts[name] = (m["exp_t"], m["energy"])
    wh, placed, failed = ws.run_awra_ls(goods, RULE, fn, w_max, f_max)
    m = ws.metrics(wh, placed, failed)
    pts["awra"] = (m["exp_t"], m["energy"])
    return pts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pop", type=int, default=60)
    ap.add_argument("--gens", type=int, default=200)
    ap.add_argument("--quick", action="store_true")
    a = ap.parse_args()
    pop, gens = (30, 40) if a.quick else (a.pop, a.gens)

    goods = ws.gen_goods(N_GOODS, SEED)
    prob = Problem(goods, RULE)
    rng = random.Random(SEED)
    print(f"NSGA-II:pop={pop} gens={gens} seed={SEED},货物{N_GOODS}件,双目标(期望取货,能耗)")
    t0 = time.time()
    front = nsga2(prob, pop, gens, rng)
    print(f"完成:前沿 {len(front)} 点,耗时 {time.time()-t0:.0f}s")

    pts = strategy_points(goods)

    # ---- CSV ----
    os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
    path = os.path.join(HERE, "out", "pareto_front.csv")
    with open(path, "w", newline="", encoding="utf-8-sig") as fp:
        w = csv.writer(fp)
        w.writerow(["exp_retrieval_s", "energy_kgm", "source"])
        for f1, f2 in front:
            w.writerow([round(f1, 4), round(f2, 1), "nsga2_front"])
        for name, (f1, f2) in pts.items():
            w.writerow([round(f1, 4), round(f2, 1), name])

    # ---- gap 度量(awra 到前沿的归一化距离)----
    f1s = [p[0] for p in front] + [pts["awra"][0]]
    f2s = [p[1] for p in front] + [pts["awra"][1]]
    s1 = max(f1s) - min(f1s) or 1.0
    s2 = max(f2s) - min(f2s) or 1.0
    ax_, ay_ = pts["awra"]
    gap = min(((ax_ - q1) / s1) ** 2 + ((ay_ - q2) / s2) ** 2 for q1, q2 in front) ** 0.5
    dom_by = sum(1 for q in front if dominates(q, pts["awra"]))
    print(f"\nAWRA-LS 落点 ({ax_:.2f}s, {ay_:.0f}kg·m):到前沿归一化距离 {gap:.3f},"
          f"被前沿支配点数 {dom_by}/{len(front)}")

    # ---- fig6 ----
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, ax = plt.subplots(figsize=(7.2, 5))
    fx = [p[0] for p in front]
    fy = [p[1] for p in front]
    ax.plot(fx, fy, "o-", ms=4, lw=1, color="#7b1fa2", alpha=0.8,
            label=f"NSGA-II Pareto 前沿({len(front)}点,{pop}×{gens}代)")
    C = {"random": "#9e9e9e", "seq": "#8d6e63", "near": "#1976d2",
         "score": "#f9a825", "awra": "#2e7d32"}
    L = {"random": "随机", "seq": "顺序基线", "near": "就近贪心",
         "score": "多目标评分(在线)", "awra": "AWRA-LS(批量)"}
    for name, (x, y) in pts.items():
        ax.scatter(x, y, s=150 if name == "awra" else 90, color=C[name], zorder=3,
                   edgecolor="white", marker="*" if name == "awra" else "o", label=L[name])
    ax.set_xlabel("期望取货时间 (s) →越小越好")
    ax.set_ylabel("能耗代理 (kg·m) →越小越好")
    ax.set_title(f"AWRA-LS vs 进化算法 Pareto 前沿(seed={SEED},120件,and 规则)")
    ax.legend(fontsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    os.makedirs(os.path.join(HERE, "figs"), exist_ok=True)
    fig.savefig(os.path.join(HERE, "figs", "fig6_pareto前沿.png"), dpi=300)
    print(f"输出:{path} + figs/fig6_pareto前沿.png")


if __name__ == "__main__":
    main()
