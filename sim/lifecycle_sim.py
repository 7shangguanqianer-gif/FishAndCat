# -*- coding: utf-8 -*-
"""
lifecycle_sim.py — T1.4 U5 生命周期仿真:检验（可证伪）δ位置价值预留主张

问题:δ 项(罚"冷货占近位")的收益主张是"给未来热货留近位"——静态单批布局
看不到"未来",只有全生命周期(入库→按频次出库→回库→汰换→夜间重排的持续循环)
才能兑现或证伪。本实验=同负载 CRN 配对跑 δ=0.15 vs δ=0 两组,差值即 δ 净收益。

模型(负载逻辑同 reslot_cycle.simulate 的 B7 循环访问口径,复用其常量):
  初始:AWRA-LS 完成 120 件布局(fn 含各组 δ);
  每周期:取 1 件在库货(∝频次,循环访问);取出的货 LAG=5 周期后回库
        (score 在线决策,fn 含各组 δ);每 10 次回库汰换 1 次成新货(≈10% 周转);
  每 day_len=40 周期夜间窗口:reslot_pass 成本感知重排(复用 reslot_cycle)。
计时 = U2 载重口径(T1.3):
  出库 = 空载去 + 取货装卸 + 载货返(垂直×0.80) + 卸货装卸
  回库 = 装货装卸 + 载货去(垂直×0.80) + 放货装卸 + 空载返
  重排搬运 = 空去旧位 + 装卸 + 载货旧→新 + 装卸 + 空返;装卸=轻/中/重三档(handle_time)
指标:出库平均响应(全程/后半程——δ 效应在中后期兑现)、总作业时间、
     重排搬运开销、终局布局质量(layout_quality 复用)。
统计:30 seeds,均值±95%CI + 配对 t(CRN;协议依据 Law 2015 WSC/Rossetti §4.4.2)。

运行:python lifecycle_sim.py [--seeds 30] [--cycles 200]
输出:out/lifecycle_delta.csv + 控制台配对结论
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
from reslot_cycle import reslot_pass, layout_quality
from instance_gen import ci95, paired_t

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
RULE, N_INIT, LAG, TURNOVER = "sum", 120, 5, 10


def _t_retrieve(pos, good):
    """出库周期(U2 载重口径):空去+取装+载返+卸下。"""
    c, t = pos
    return (ws.travel_time(c, t) + ws.handle_time(good)
            + ws.travel_time_laden(c, t, 0, 0) + ws.handle_time(good))


def _t_store(pos, good):
    """回库/入库周期(U2 载重口径):装+载去+放+空返。"""
    c, t = pos
    return (ws.handle_time(good) + ws.travel_time_laden(0, 0, c, t)
            + ws.handle_time(good) + ws.travel_time(c, t))


def _t_move(old, new, good):
    """重排单步搬运(U2 口径):空去旧位+取装+载货旧→新+放卸+空返 I/O。"""
    return (ws.travel_time(*old) + ws.handle_time(good)
            + ws.travel_time_laden(old[0], old[1], new[0], new[1])
            + ws.handle_time(good) + ws.travel_time(*new))


def run_lifecycle(seed, delta, cycles=200, day_len=40, turnover=TURNOVER,
                  n_init=N_INIT):
    """单 seed 单 δ 组的全生命周期。负载只依赖 (seed, 常量) → 两组 CRN 配对成立。
    turnover=每几次回库汰换 1 次新货(10=10% 电工物料库画像 / 3≈33% / 2=50% 电商型)
    ——δ 预留项的收益前提是"未来有新热货流入",汰换率是其敏感性主轴(显式情景轴)。
    n_init=初始件数(120=45% 填充主口径;240=90% 高压——δ 收益条件"近位竞争"的检验场)。"""
    goods = ws.gen_goods(n_init, seed)
    w_max = max(g.weight for g in goods)
    f_max = max(g.freq for g in goods)
    fn = ws.make_score_fn(1.0, 0.6, 0.4, delta, w_max, f_max)

    wh, placed, failed = ws.run_awra_ls(goods, RULE, fn, w_max, f_max)
    assert not failed
    pos_of = {g.gid: p for g, p in placed}
    by_gid = {g.gid: g for g in goods}

    new_goods = ws.gen_goods(cycles // turnover + 2, seed + 7)
    for i, g in enumerate(new_goods):
        g.gid, g.name = 1000 + i + 1, f"N{i+1:03d}"
    rng = random.Random(seed + 13)

    retr, retr_late = [], []
    tot = reslot_t = 0.0
    n_moves = n_return = fails = 0
    pending = []                                   # (回库周期, good)
    ni = 0                                         # 汰换指针
    for k in range(cycles):
        # ---- 到期回库(score 在线,fn 同组 δ) ----
        due = [p for p in pending if p[0] <= k]
        pending = [p for p in pending if p[0] > k]
        for _, g in due:
            pos = ws.strat_score(wh, g, fn)
            if pos is None:                        # 边界:无可行位(如实计失败)
                fails += 1
                continue
            wh.put(pos[0], pos[1], g)
            pos_of[g.gid] = pos
            by_gid[g.gid] = g
            tot += _t_store(pos, g)
        # ---- 取 1 件(∝频次;负载只依赖身份与 seed) ----
        gids = list(pos_of.keys())
        if not gids:
            continue
        gid = rng.choices(gids, weights=[by_gid[x].freq for x in gids], k=1)[0]
        g = by_gid[gid]
        pos = pos_of.pop(gid)
        t_r = _t_retrieve(pos, g)
        tot += t_r
        retr.append(t_r)
        if k >= cycles // 2:
            retr_late.append(t_r)
        wh.remove(pos[0], pos[1])
        # ---- LAG 后回库;每 turnover 次回库汰换 1 次成新货 ----
        n_return += 1
        if n_return % turnover == 0 and ni < len(new_goods):
            back = new_goods[ni]
            ni += 1
        else:
            back = g
        pending.append((k + LAG, back))
        # ---- 夜间重排窗口 ----
        if (k + 1) % day_len == 0:
            moves = reslot_pass(wh, pos_of, by_gid, day_len=day_len)
            for mgid, old, new in moves:
                reslot_t += _t_move(old, new, by_gid[mgid])
            n_moves += len(moves)
    # ---- 观察窗结束后的 drain phase ----
    # pending 中仍是已取出但尚未回库的在途货；若直接 return，会把终局库存、
    # 总作业时间和 final_q 全部截尾。按到期顺序冲洗，不再触发新取货或夜间重排。
    flush_time = 0.0
    flush_count = 0
    for _, g in sorted(pending, key=lambda item: item[0]):
        pos = ws.strat_score(wh, g, fn)
        if pos is None:
            fails += 1
            continue
        wh.put(pos[0], pos[1], g)
        pos_of[g.gid] = pos
        by_gid[g.gid] = g
        t_s = _t_store(pos, g)
        tot += t_s
        flush_time += t_s
        flush_count += 1
    pending.clear()

    return dict(
        retr_mean=st.mean(retr) if retr else 0.0,
        retr_late=st.mean(retr_late) if retr_late else 0.0,
        tot_time=tot, reslot_t=reslot_t, moves=n_moves, fails=fails,
        pending_end=len(pending), inventory_end=len(pos_of),
        flush_time=flush_time, flush_count=flush_count,
        final_q=layout_quality(wh, pos_of, by_gid),
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=30)
    ap.add_argument("--cycles", type=int, default=200)
    ap.add_argument("--day-len", type=int, default=40)
    ap.add_argument("--turnovers", default="10,3,2",
                    help="汰换率敏感性轴:每几次回库换 1 新货(10=10%%/3≈33%%/2=50%%)")
    ap.add_argument("--n-init", type=int, default=N_INIT,
                    help="初始件数(120=45%% 填充主口径;240=90%% 高压检验场)")
    a = ap.parse_args()
    seeds = [2026 + i for i in range(a.seeds)]
    turnovers = [int(x) for x in a.turnovers.split(",")]

    rows = []
    os.makedirs(OUT, exist_ok=True)
    for tv in turnovers:
        res = {0.15: [], 0.0: []}
        for sd in seeds:
            for d in (0.15, 0.0):
                m = run_lifecycle(sd, d, a.cycles, a.day_len, turnover=tv,
                                  n_init=a.n_init)
                res[d].append(m)
                rows.append(dict(turnover=tv, seed=sd, delta=d,
                                 **{k: round(v, 3) if isinstance(v, float) else v
                                    for k, v in m.items()}))
        print(f"\n=== 汰换率 1/{tv}(≈{100 // tv}% 新货流入)"
              f":{a.cycles} 周期×{a.seeds} seeds,δ=0.15 vs δ=0 配对(U2 载重口径) ===")
        print(f"{'指标':<16}{'δ=0.15':>13}{'δ=0':>13}{'差[95%CI]':>24}{'显著':>5}")
        print("-" * 74)
        for key, lbl in (("retr_mean", "出库均响应 s"), ("retr_late", "后半程响应 s"),
                         ("tot_time", "总作业时 s"), ("reslot_t", "重排开销 s"),
                         ("final_q", "终局布局质量")):
            va = [r[key] for r in res[0.15]]
            vb = [r[key] for r in res[0.0]]
            ma, _ = ci95(va)
            mb, _ = ci95(vb)
            dm, (dlo, dhi), t, mark, p = paired_t(va, vb)
            print(f"{lbl:<16}{ma:>13.2f}{mb:>13.2f}{dm:>9.2f} [{dlo:.2f},{dhi:.2f}]{mark:>5}")
        print(f"失败:{sum(r['fails'] for r in res[0.15])}/{sum(r['fails'] for r in res[0.0])}"
              f";重排件数 δ组 {st.mean([r['moves'] for r in res[0.15]]):.1f}"
              f" / 无δ {st.mean([r['moves'] for r in res[0.0]]):.1f}")

    # 文件名按组区分(0710 修缮):默认组(120=45% 填充)沿用原名;其他 n_init 加后缀
    # ——此前两组共用一名互相覆盖,报告生成器永远只能注入后跑的一组
    fname = ("lifecycle_delta.csv" if a.n_init == N_INIT
             else f"lifecycle_delta_{a.n_init}.csv")
    with open(os.path.join(OUT, fname), "w", newline="",
              encoding="utf-8-sig") as fp:
        w = csv.DictWriter(fp, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"\nCSV:{OUT}\\{fname}({len(rows)} 行)")


if __name__ == "__main__":
    main()
