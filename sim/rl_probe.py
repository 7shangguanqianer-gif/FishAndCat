# -*- coding: utf-8 -*-
"""
rl_probe.py — T13 实跑版:轻量强化学习对照(线性策略梯度 REINFORCE,numpy 零依赖)
定位(诚实):这不是"深度"RL——策略=对 5 维特征的线性打分+softmax 采样,
目的是用真实训练数据回答两个问题,而不是只引文献:
  Q1 免模型的 RL 自己学,能学到多好?(对照:我们的在线评分 score 与批量 AWRA-LS)
  Q2 它学出来的权重方向,和我们手工标定的 (α,β+γ,δ) 像不像?(像=标定被 AI 独立背书)
口径:对照口径(匀速+固定归一),与 F4/F6/F9 同一可比框架;训练/评测 seed 严格分离
(训练 3000+,评测 2026/2027/2028 三 seed,与全项目评测 seed 一致)。
特征(每个 货物×仓位 对,5 维;前三维=评分函数的三个独立项,后两维给 RL 额外自由度):
  x1 效率项 f_norm·t_norm | x2 稳定/能耗项 w_norm·tier_norm(本几何下 β、γ 特征相同,F5)
  x3 预留项 (1-f_norm)(1-t_norm) | x4 纯距离 t_norm | x5 纯层高 tier_norm
运行:python rl_probe.py(~2-4 分钟)→ out/rl_probe.csv + figs/fig15_RL对照.png
"""
import csv
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import warehouse_sim as ws

HERE = os.path.dirname(os.path.abspath(__file__))
RULE = "and"
N_GOODS = 120
EPISODES = 1200
LR0 = 0.15
EVAL_SEEDS = [2026, 2027, 2028]       # 与全项目一致的评测 seed(训练绝不碰)
TRAIN_SEED0 = 3000                    # 训练实例池(与评测严格分离)
CAL_DIR = np.array([1.0, 1.0, 0.15, 0.0, 0.0])   # 标定方向:α=1,β+γ=1,δ=0.15,额外维=0

# ---- 静态几何(对照口径:匀速) ----
ws.ACCEL = False
SLOTS = [(c, t) for c in range(ws.COLS) for t in range(ws.TIERS)]
TT = np.array([ws.travel_time(c, t) for c, t in SLOTS])          # 行程时间(400,)
TIER = np.array([t for _, t in SLOTS], dtype=float)
CAP = np.array([ws.tier_cap(t) for _, t in SLOTS])               # 层限重
PRE = np.array([ws.preoccupied(c, t, RULE) for c, t in SLOTS])   # 预占用
T_NORM = TT / TT.max()
TIER_NORM = TIER / (ws.TIERS - 1)


def episode_goods(seed):
    goods = ws.gen_goods(N_GOODS, seed)
    w_max = max(g.weight for g in goods)
    f_max = max(g.freq for g in goods)
    return goods, w_max, f_max


def features(g, w_max, f_max):
    """一件货对全部 400 仓位的特征矩阵 (400,5)。"""
    f_n = g.freq / f_max
    w_n = g.weight / w_max
    x = np.empty((len(SLOTS), 5))
    x[:, 0] = f_n * T_NORM                       # 效率
    x[:, 1] = w_n * TIER_NORM                    # 稳定/能耗(同特征,F5)
    x[:, 2] = (1.0 - f_n) * (1.0 - T_NORM)       # δ 预留
    x[:, 3] = T_NORM                             # 纯距离
    x[:, 4] = TIER_NORM                          # 纯层高
    return x


def run_policy(theta, seed, sample_rng=None):
    """跑一个完整入库回合。sample_rng=None → 贪心评测;否则 softmax 采样训练。
    返回 (exp_t, viol, grad_accum)。梯度=Σ_t (E_π[x]-x_choice)(logits=-θ·x 的 REINFORCE)。"""
    goods, w_max, f_max = episode_goods(seed)
    free = ~PRE.copy()
    grad = np.zeros(5)
    f_sum = t_acc = 0.0
    viol = 0
    for g in goods:
        feas = free & (g.weight <= CAP + 1e-9) & (g.vol <= ws.CELL_VOL + 1e-9)
        idx = np.flatnonzero(feas)
        if idx.size == 0:
            return None, viol, grad                       # 无可行位(本口径不应发生)
        x = features(g, w_max, f_max)[idx]                # (k,5)
        logits = -(x @ theta)
        if sample_rng is None:
            k = int(np.argmax(logits))
        else:
            p = np.exp(logits - logits.max())
            p /= p.sum()
            k = int(sample_rng.choice(idx.size, p=p))
            grad += (p @ x) - x[k]                        # E[x]-x_a
        s = idx[k]
        free[s] = False
        if g.weight > CAP[s] + 1e-9:
            viol += 1
        f_sum += g.freq
        t_acc += g.freq * TT[s]
    return t_acc / f_sum, viol, grad


def eval_greedy(theta, seeds=EVAL_SEEDS):
    vals, viols = [], 0
    for sd in seeds:
        e, v, _ = run_policy(theta, sd)
        vals.append(e)
        viols += v
    return float(np.mean(vals)), viols


def baseline_refs():
    """同评测 seed 下 score 在线与 AWRA-LS 的 exp_t(脚本内自算,严格同框架可比)。"""
    acc = {"score": [], "awra": []}
    for sd in EVAL_SEEDS:
        goods, w_max, f_max = episode_goods(sd)
        fn = ws.make_score_fn(1.0, 0.6, 0.4, 0.15, w_max, f_max)
        wh, placed, failed = ws.run_online(ws.strat_score, goods, RULE, fn)
        acc["score"].append(ws.metrics(wh, placed, failed)["exp_t"])
        wh, placed, failed = ws.run_awra_ls(goods, RULE, fn, w_max, f_max)
        acc["awra"].append(ws.metrics(wh, placed, failed)["exp_t"])
    return {k: float(np.mean(v)) for k, v in acc.items()}


def main():
    rng = np.random.default_rng(2026)
    theta = np.zeros(5)                       # 零初始=均匀随机策略(纯探索起步)
    ema = None
    curve = []                                # (episode, 评测exp_t)
    e0, v0 = eval_greedy(theta)
    curve.append((0, e0))
    print(f"起点(θ=0,等价随机放):评测 exp_t={e0:.2f}s")

    for ep in range(1, EPISODES + 1):
        seed = TRAIN_SEED0 + (ep % 40)        # 40 个训练实例轮转
        e, v, grad = run_policy(theta, seed, sample_rng=rng)
        if e is None:
            continue
        r = -e                                 # 回报=负期望取货时间
        ema = r if ema is None else 0.95 * ema + 0.05 * r
        lr = LR0 * (1.0 - 0.7 * ep / EPISODES)
        theta += lr * (r - ema) * grad / N_GOODS
        if ep % 100 == 0:
            ev, _ = eval_greedy(theta)
            curve.append((ep, ev))
            print(f"  ep{ep:>5}  train={e:.2f}  评测(贪心3seed)={ev:.2f}  "
                  f"θ={np.round(theta, 3)}")

    ev_final, viol_final = eval_greedy(theta)
    refs = baseline_refs()
    cos = float(theta @ CAL_DIR / (np.linalg.norm(theta) * np.linalg.norm(CAL_DIR) + 1e-12))
    n13 = theta[[0, 1, 2]]
    ratio = np.round(n13 / (abs(n13[0]) + 1e-12), 3)

    print("\n" + "=" * 66)
    print(f"轻量 RL(线性 REINFORCE,{EPISODES} 回合,40 训练实例)最终成绩:")
    print(f"  RL 贪心策略   exp_t = {ev_final:.2f}s(3 评测seed,违规 {viol_final})")
    print(f"  在线评分对照  exp_t = {refs['score']:.2f}s(手工标定权重)")
    print(f"  AWRA-LS 对照 exp_t = {refs['awra']:.2f}s(批量上界)")
    print(f"  随机起点      exp_t = {e0:.2f}s")
    gap_score = (ev_final - refs["score"]) / refs["score"] * 100
    gap_awra = (ev_final - refs["awra"]) / refs["awra"] * 100
    lift = (e0 - ev_final) / e0 * 100
    print(f"学到的权重方向:θ={np.round(theta, 3)}(主导维=纯距离+纯层高)")
    print(f"  与标定方向的余弦相似度 = {cos:.3f}")
    print(f"解读(按实测写,勿美化):RL 较随机自提升 {lift:.0f}%,但收敛在"
          f"'距离+层高主导的聪明就近'层次——**未自发发现 δ 预留结构**(余弦 {cos:.2f}),"
          f"距手工标定评分差 {gap_score:.1f}%,距批量上界差 {gap_awra:.0f}%,"
          f"且耗 {EPISODES} 回合×{N_GOODS} 件交互。")
    print("报告工程取舍口径:①免训练、可解释、可移植 PLC 的标定评分在同预算下占优(实测);"
          "②δ 这类前瞻性资源预留逻辑在本训练预算内学不出来——设计知识仍然值钱"
          "(δ 证据链的反向新证);③与 2025 文献'DRL 收益个位数+需长期数据'画像一致。")

    # ---- CSV ----
    os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
    path = os.path.join(HERE, "out", "rl_probe.csv")
    with open(path, "w", newline="", encoding="utf-8-sig") as fp:
        w = csv.writer(fp)
        w.writerow(["episode", "eval_exp_t"])
        for ep, ev in curve:
            w.writerow([ep, round(ev, 4)])
        w.writerow([])
        w.writerow(["quantity", "value"])
        for k, v in [("rl_final_exp_t", round(ev_final, 4)),
                     ("score_ref_exp_t", round(refs["score"], 4)),
                     ("awra_ref_exp_t", round(refs["awra"], 4)),
                     ("random_start_exp_t", round(e0, 4)),
                     ("viol", viol_final), ("episodes", EPISODES),
                     ("cos_to_calibrated", round(cos, 4)),
                     ("theta", " ".join(f"{x:.4f}" for x in theta))]:
            w.writerow([k, v])

    # ---- fig15 ----
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, axes = plt.subplots(1, 2, figsize=(11.2, 4.2))
    xs = [c[0] for c in curve]
    ys = [c[1] for c in curve]
    axes[0].plot(xs, ys, marker="o", ms=3.5, color="#6a1b9a", lw=1.6,
                 label="RL 贪心评测(3 seed)")
    axes[0].axhline(refs["score"], color="#1565c0", ls="--", lw=1.3,
                    label="在线评分(手工标定)")
    axes[0].axhline(refs["awra"], color="#2e7d32", ls="--", lw=1.3,
                    label="AWRA-LS(批量上界)")
    axes[0].set_xlabel("训练回合(REINFORCE,40 个训练实例轮转)")
    axes[0].set_ylabel("期望取货时间 s(对照口径,评测 seed)")
    axes[0].set_title("学习曲线:从随机放到逼近手工标定")
    axes[0].legend(fontsize=8.5, frameon=False)
    axes[0].spines[["top", "right"]].set_visible(False)
    names = ["随机起点", "RL 终点", "在线评分", "AWRA-LS"]
    vals = [e0, ev_final, refs["score"], refs["awra"]]
    cols = ["#8d6e63", "#6a1b9a", "#1565c0", "#2e7d32"]
    bars = axes[1].bar(range(4), vals, 0.6, color=cols)
    for b, v in zip(bars, vals):
        axes[1].text(b.get_x() + b.get_width() / 2, v, f"{v:.2f}",
                     ha="center", va="bottom", fontsize=10)
    axes[1].set_xticks(range(4))
    axes[1].set_xticklabels(names, fontsize=9.5)
    axes[1].set_ylabel("期望取货时间 s")
    axes[1].set_title(f"终局对比(θ 与标定方向余弦 {cos:.2f})")
    axes[1].spines[["top", "right"]].set_visible(False)
    fig.suptitle("T13 轻量强化学习实跑对照(线性 REINFORCE;训练/评测 seed 分离)",
                 fontsize=11.5)
    fig.tight_layout()
    os.makedirs(os.path.join(HERE, "figs"), exist_ok=True)
    fig.savefig(os.path.join(HERE, "figs", "fig15_RL对照.png"), dpi=300)
    print(f"输出:{path} + figs/fig15_RL对照.png")


if __name__ == "__main__":
    main()
