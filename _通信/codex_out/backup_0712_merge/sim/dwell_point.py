# -*- coding: utf-8 -*-
"""
dwell_point.py — A10 堆垛机驻留点(dwell-point)策略对照实验(0708 实装)

背景:对标 deep-research F2——dwell-point 是 AS/RS 公认独立优化维度(Egbelu 1991/
Hwang & Lim 1993 四经典规则),我方基线未显式建模:现有口径(lifecycle_sim._t_store
末尾"空返 I/O"、_t_retrieve 从 I/O 出发)= 隐含"驻留点固定在 I/O"。
本实验回答:换驻留策略,出库/回库响应时间能降多少?ST 侧值得蒸馏哪一档?

策略(文献四规则 + 我方 ST 蒸馏候选):
  io     驻 I/O(0,0)          —— 基线=现状隐含口径
  last   驻上次作业结束位(不空驶) —— Egbelu 规则 4
  center 驻几何中点 (10,10)      —— minimax 稳健(对全库均匀请求)
  demand 驻期望最优点:400 格点全枚举 argmin E[下一作业第一段]  —— 精确(格点集上),
         E(D)=p_store·t(D→IO)+(1−p_store)·Σ f_i/Σf·t(D→pos_i),p_store=0.5(B6/B7
         存取 1:1 口径);逐格枚举而非重心近似=延续"规模小则精确解"哲学(LAP 锚同门)
  cog    驻频次加权重心(round 到格)—— O(n) 单周期,ST 蒸馏候选;与 demand 的 gap
         由本实验量化,gap 小则 ST 用 cog(证据链:sim 证明近似损失)

设计要点(为什么能一遍事件流五账本):
  驻留点只改**时间记账**,不改物流事件——取谁(∝频次)/回哪(strat_score)与驻留
  策略无关 → 五策略共享同一事件流,差值 100% 归因驻留策略,CRN 完美配对。
记账口径(五策略统一,与 lifecycle 口径可对照):
  出库响应 = travel(D→pos) 空载 + 取装 + laden(pos→IO) + 卸装;作业毕堆垛机在 I/O
  回库响应 = travel(D→IO) 空载 + 取装 + laden(IO→pos) + 放装;作业毕在 pos
  deadhead = 作业结束位 → D 的空驶(发生在空闲期,不计入响应;LAG=5 周期背书
  "空闲足够到达驻留点"的文献标准假设)。io 的回库空返 I/O 即其 deadhead——与旧
  _t_store"空返"数字同源,基线可对上。
更新时机:demand 每 day_len=40 周期重算(日更,与夜间维护节奏一致);cog 每周期更
  (O(n) 便宜是其卖点=ST 单周期可算);io/center 固定;last 逐作业。

负载(B7 循环访问简化版,隔离变量):AWRA-LS(δ=0.15 主口径)初始布局;每周期取 1 件
  (∝频次)→ LAG=5 周期后回库(strat_score 在线);不汰换、不夜间重排(排除布局漂移,
  纯测驻留点效应)。轴:n_init∈{120,240}(45%/90% 填充)×30 seeds×200 周期。

统计:均值±95%CI + 配对 t(vs io 基线),协议同 instance_gen(Law 2015/Rossetti)。
运行:python dwell_point.py [--seeds 30] [--cycles 200]
输出:out/dwell_point.csv + 控制台对照表 + demand vs cog gap(ST 蒸馏依据)
"""
import argparse
import csv
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
from instance_gen import ci95, paired_t

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
RULE, LAG, DAY_LEN = "sum", 5, 40
P_STORE = 0.5                       # 下一作业是回库的先验(B6/B7 存取 1:1)
POLICIES = ("io", "last", "center", "demand", "cog")
CENTER = (10, 10)                   # 几何中点(20×20 格,(9.5,9.5) 取右上格)
IO = (0, 0)


def expected_first_leg(d, stock, p_store=P_STORE):
    """驻留点 d 的期望下一作业第一段(评价函数,demand 优化目标 + 理论/实测互检)。
    stock: [(pos, freq)] 在库货;回库第一段=D→I/O,出库第一段=D→pos_i(∝频次)。"""
    t_store = ws.travel_time_between(d[0], d[1], 0, 0)
    f_sum = sum(f for _, f in stock)
    if f_sum <= 0.0:
        return p_store * t_store
    t_retr = sum(f * ws.travel_time_between(d[0], d[1], p[0], p[1])
                 for p, f in stock) / f_sum
    return p_store * t_store + (1.0 - p_store) * t_retr


def solve_dwell_exact(stock, p_store=P_STORE):
    """demand 驻留点:400 格点全枚举,精确最小化期望第一段(格点集上全局最优)。
    平局按 (t, y, x) 取最低层最左列(确定性,便于 ST 比对)。"""
    best, best_key = IO, None
    for y in range(ws.TIERS):
        for x in range(ws.COLS):
            t = expected_first_leg((x, y), stock, p_store)
            key = (t, y, x)
            if best_key is None or key < best_key:
                best, best_key = (x, y), key
    return best


def dwell_cog(stock):
    """cog 驻留点:频次加权重心 round 到格(O(n),ST 蒸馏候选 FC_DwellCog 同式)。"""
    f_sum = sum(f for _, f in stock)
    if f_sum <= 0.0:
        return IO
    cx = sum(p[0] * f for p, f in stock) / f_sum
    cy = sum(p[1] * f for p, f in stock) / f_sum
    return (min(ws.COLS - 1, max(0, round(cx))),
            min(ws.TIERS - 1, max(0, round(cy))))


def _resp_retrieve(d, pos, good):
    """出库响应:空载 D→pos + 取装 + 载货 pos→I/O + 卸装(作业毕在 I/O)。"""
    return (ws.travel_time_between(d[0], d[1], pos[0], pos[1])
            + ws.handle_time(good)
            + ws.travel_time_laden(pos[0], pos[1], 0, 0) + ws.handle_time(good))


def _resp_store(d, pos, good):
    """回库响应:空载 D→I/O + 取装 + 载货 I/O→pos + 放装(作业毕在 pos)。"""
    return (ws.travel_time_between(d[0], d[1], 0, 0) + ws.handle_time(good)
            + ws.travel_time_laden(0, 0, pos[0], pos[1]) + ws.handle_time(good))


def run_experiment(seed, n_init, cycles=200, p_store=P_STORE):
    """单 seed:一遍事件流,五策略并行记账(驻留点不改事件,CRN 完美配对)。
    p_store=demand 优化目标里"下一作业是回库"的先验:0.5=B6/B7 存取 1:1 主口径;
    0.0=纯出库视角(回库不急、只优化取货响应)——收益边界的敏感性轴。"""
    goods = ws.gen_goods(n_init, seed)
    w_max = max(g.weight for g in goods)
    f_max = max(g.freq for g in goods)
    fn = ws.make_score_fn(1.0, 0.6, 0.4, 0.15, w_max, f_max)
    wh, placed, failed = ws.run_awra_ls(goods, RULE, fn, w_max, f_max)
    assert not failed
    pos_of = {g.gid: p for g, p in placed}
    by_gid = {g.gid: g for g in goods}
    rng = random.Random(seed + 13)

    def stock_list():
        return [(pos_of[gid], by_gid[gid].freq) for gid in pos_of]

    # 每策略账本:D=当前驻留点;resp/dead=响应与空驶累计
    state = {p: dict(d=IO, retr=[], store=[], dead=0.0) for p in POLICIES}
    state["center"]["d"] = CENTER
    s0 = stock_list()
    state["demand"]["d"] = solve_dwell_exact(s0, p_store)
    state["cog"]["d"] = dwell_cog(s0)
    first_legs = {p: [] for p in POLICIES}          # 实测第一段(理论互检用)
    pending, fails = [], 0

    def account(kind, pos, good):
        """kind='retr'|'store';作业结束位:retr→I/O,store→pos。"""
        end = IO if kind == "retr" else pos
        for p in POLICIES:
            d = state[p]["d"]
            if kind == "retr":
                state[p]["retr"].append(_resp_retrieve(d, pos, good))
                first_legs[p].append(
                    ws.travel_time_between(d[0], d[1], pos[0], pos[1]))
            else:
                state[p]["store"].append(_resp_store(d, pos, good))
                first_legs[p].append(ws.travel_time_between(d[0], d[1], 0, 0))
            if p == "last":                          # 就地停,不空驶
                state[p]["d"] = end
            else:                                    # 空驶回各自驻留点
                state[p]["dead"] += ws.travel_time_between(
                    end[0], end[1], d[0], d[1])

    for k in range(cycles):
        due = [x for x in pending if x[0] <= k]
        pending = [x for x in pending if x[0] > k]
        for _, g in due:                             # 回库(在线选位,策略无关)
            pos = ws.strat_score(wh, g, fn)
            if pos is None:
                fails += 1
                continue
            wh.put(pos[0], pos[1], g)
            pos_of[g.gid] = pos
            account("store", pos, g)
        gids = list(pos_of.keys())
        if not gids:
            continue
        gid = rng.choices(gids, weights=[by_gid[x].freq for x in gids], k=1)[0]
        g = by_gid[gid]
        pos = pos_of.pop(gid)
        account("retr", pos, g)
        wh.remove(pos[0], pos[1])
        pending.append((k + LAG, g))
        stock = stock_list()
        state["cog"]["d"] = dwell_cog(stock)         # cog:每周期 O(n) 在线更新
        if (k + 1) % DAY_LEN == 0:                   # demand:日更(夜间维护节奏)
            state["demand"]["d"] = solve_dwell_exact(stock, p_store)

    out = {}
    for p in POLICIES:
        s = state[p]
        n_ops = len(s["retr"]) + len(s["store"])
        out[p] = dict(
            retr=st.mean(s["retr"]),
            store=st.mean(s["store"]) if s["store"] else 0.0,
            resp=st.mean(s["retr"] + s["store"]),
            dead=s["dead"] / max(n_ops, 1),          # 均次空驶(设备损耗代理)
            leg=st.mean(first_legs[p]),
        )
    out["fails"] = fails
    out["d_demand"] = state["demand"]["d"]           # 终局驻留点(退化可见性)
    out["d_cog"] = state["cog"]["d"]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=30)
    ap.add_argument("--cycles", type=int, default=200)
    ap.add_argument("--n-inits", default="120,240")
    ap.add_argument("--p-stores", default="0.5,0.0",
                    help="demand 先验敏感轴:0.5=存取1:1 主口径;0.0=纯出库视角")
    a = ap.parse_args()
    seeds = [2026 + i for i in range(a.seeds)]
    avail = ws.COLS * ws.TIERS - 133          # B1 sum 预占 133 格后的可用位
    os.makedirs(OUT, exist_ok=True)
    rows = []

    for n_init in [int(x) for x in a.n_inits.split(",")]:
        for p_store in [float(x) for x in a.p_stores.split(",")]:
            res = {p: [] for p in POLICIES}
            fails = 0
            d_dem, d_cog = {}, {}                 # 终局驻留点分布(退化可见性)
            for sd in seeds:
                m = run_experiment(sd, n_init, a.cycles, p_store)
                fails += m["fails"]
                d_dem[m["d_demand"]] = d_dem.get(m["d_demand"], 0) + 1
                d_cog[m["d_cog"]] = d_cog.get(m["d_cog"], 0) + 1
                for p in POLICIES:
                    res[p].append(m[p])
                    rows.append(dict(n_init=n_init, p_store=p_store, seed=sd,
                                     policy=p,
                                     **{k: round(v, 3)
                                        for k, v in m[p].items()}))
            print(f"\n=== 驻留点对照:n_init={n_init}"
                  f"({100 * n_init // avail}% 可用位填充)"
                  f",p_store={p_store}×{a.cycles} 周期×{a.seeds} seeds"
                  f",配对 vs io(CRN 同事件流) ===")
            print(f"{'策略':<8}{'总响应s':>10}{'出库s':>10}{'回库s':>10}"
                  f"{'均次空驶s':>11}{'vs io 差±95%CI':>24}{'显著':>5}")
            print("-" * 82)
            base = [r["resp"] for r in res["io"]]
            for p in POLICIES:
                va = [r["resp"] for r in res[p]]
                m_resp, _ = ci95(va)
                m_retr, _ = ci95([r["retr"] for r in res[p]])
                m_stor, _ = ci95([r["store"] for r in res[p]])
                m_dead, _ = ci95([r["dead"] for r in res[p]])
                if p == "io":
                    print(f"{p:<8}{m_resp:>10.2f}{m_retr:>10.2f}{m_stor:>10.2f}"
                          f"{m_dead:>11.2f}{'(基线)':>24}")
                else:
                    dm, (dlo, dhi), t, mark, _ = paired_t(va, base)
                    print(f"{p:<8}{m_resp:>10.2f}{m_retr:>10.2f}"
                          f"{m_stor:>10.2f}{m_dead:>11.2f}"
                          f"{dm:>10.2f} [{dlo:.2f},{dhi:.2f}]{mark:>5}")
            gap = [(x["leg"] - y["leg"]) for x, y in
                   zip(res["cog"], res["demand"])]
            gm, gh = ci95(gap)
            top_d = sorted(d_dem.items(), key=lambda kv: -kv[1])[:3]
            top_c = sorted(d_cog.items(), key=lambda kv: -kv[1])[:3]
            print(f"demand 终局驻留点 Top3: {top_d};cog Top3: {top_c}")
            print(f"cog vs demand 第一段 gap: {gm:+.3f}±{gh:.3f}s"
                  f"(ST 蒸馏依据);回库失败:{fails}(全策略共享事件流)")

    with open(os.path.join(OUT, "dwell_point.csv"), "w", newline="",
              encoding="utf-8-sig") as fp:
        w = csv.DictWriter(fp, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"\nCSV:{OUT}\\dwell_point.csv({len(rows)} 行)")


if __name__ == "__main__":
    main()
