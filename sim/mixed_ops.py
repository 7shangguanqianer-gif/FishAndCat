# -*- coding: utf-8 -*-
"""
mixed_ops.py — L2 存取混合作业流仿真:补齐题面"存取效率(单位时间存取量)"的"取"半边
模型(canonical B6/C9/C10):
  初始:某策略完成 120 件入库(布局=该策略的产出);
  混合流:M 个周期,每周期 = 1 件新货入库 + 1 件在库货出库(出库请求按访问频次
  加权无放回抽样,池随入库演化;请求序列只依赖货物身份,对所有策略完全相同);
  单命令口径:两趟独立往返  T = 2·t(存位) + 2·t(取位)
  双命令口径:一趟联合行程  T = t(存位) + t(存位→取位) + t(取位)
             (存完顺路去取,省一次空驶回程——AS/RS 标准 dual command cycle)
  节省 = t(存)+t(取)−t(存→取) ≥ 0(切比雪夫满足三角不等式)。
指标:混合流总时间(两口径)、双命令节省%、吞吐(存取次数/小时,C9)、违规。
布局的价值在出库侧兑现:高频货放得近 → 抽中的取货行程短——这是"访问频次"闭环。
运行:python mixed_ops.py [--cycles 100] [--accel]
输出:out/mixed_ops.csv + figs/fig8_混合作业.png
"""
import argparse
import csv
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import warehouse_sim as ws

HERE = os.path.dirname(os.path.abspath(__file__))
SEED, N_INIT, RULE = 2026, 120, "and"
STRATS = ["seq", "near", "score", "awra"]
LBL = {"seq": "顺序基线", "near": "就近贪心", "score": "多目标评分(在线)",
       "awra": "AWRA-LS(批量)"}


def build_workload(init_goods, n_cycles, seed):
    """生成与策略无关的混合作业负载:
    新货序列(gen_goods 派生 seed)+ 出库请求序列(按频次加权无放回,池随入库演化)。
    只用货物身份,不看仓位 → 所有策略面对完全相同的负载(公平口径)。"""
    new_goods = ws.gen_goods(n_cycles, seed + 7)
    for i, g in enumerate(new_goods):               # 避免 gid 冲突:偏移编号
        g.gid = 1000 + i + 1
        g.name = f"N{i+1:03d}"
    rng = random.Random(seed + 13)
    pool = list(init_goods)
    requests = []                                    # 每周期出库的货物对象
    for k in range(n_cycles):
        weights = [g.freq for g in pool]
        g_out = rng.choices(pool, weights=weights, k=1)[0]
        pool.remove(g_out)
        requests.append(g_out)
        pool.append(new_goods[k])                    # 该周期新货入池,后续可能被取
    return new_goods, requests


def initial_layout(strat_name, goods, fn, w_max, f_max):
    if strat_name == "awra":
        wh, placed, failed = ws.run_awra_ls(goods, RULE, fn, w_max, f_max)
    else:
        strat = {"seq": ws.strat_seq, "near": ws.strat_near,
                 "score": ws.strat_score}[strat_name]
        wh, placed, failed = ws.run_online(strat, goods, RULE, fn)
    assert not failed, strat_name
    return wh, {g.gid: pos for g, pos in placed}


def run_mixed(strat_name, goods, new_goods, requests, fn, w_max, f_max,
              fn_batch=None):
    """跑混合流:入库决策用该策略的在线形式(awra 布局的后续入库用 score 在线,
    因为混合流是逐件到达场景——批量重排不适用于单件即时决策,如实声明)。
    fn_batch:awra 初始布局用的评分(H 口径下批量/在线权重不同,A1);缺省=fn。"""
    wh, pos_of = initial_layout(strat_name, goods, fn_batch or fn, w_max, f_max)
    online = {"seq": ws.strat_seq, "near": ws.strat_near,
              "score": ws.strat_score, "awra": ws.strat_score}[strat_name]
    tot_single = tot_dual = 0.0
    retr_t = []
    fails = viol = 0
    for g_in, g_out in zip(new_goods, requests):
        s_out = pos_of.pop(g_out.gid)
        s_in = online(wh, g_in, fn)
        if s_in is None:                             # 边界:无可行位(混合流不应发生)
            fails += 1
            t_out = ws.travel_time(*s_out)
            tot_single += 2 * t_out
            tot_dual += 2 * t_out
            wh.remove(s_out[0], s_out[1])
            continue
        if g_in.weight > ws.tier_cap(s_in[1]) or g_in.vol > ws.CELL_VOL:
            viol += 1
        t_in = ws.travel_time(*s_in)
        t_out = ws.travel_time(*s_out)
        t_link = ws.travel_time_between(s_in[0], s_in[1], s_out[0], s_out[1])
        tot_single += 2 * t_in + 2 * t_out
        tot_dual += t_in + t_link + t_out
        retr_t.append(t_out)
        wh.put(s_in[0], s_in[1], g_in)
        pos_of[g_in.gid] = s_in
        wh.remove(s_out[0], s_out[1])
    n_ops = 2 * len(new_goods)                       # 每周期=1存+1取
    return dict(tot_single=tot_single, tot_dual=tot_dual,
                saving=(1 - tot_dual / tot_single) * 100 if tot_single else 0.0,
                thr_single=n_ops / (tot_single / 3600) if tot_single else 0.0,
                thr_dual=n_ops / (tot_dual / 3600) if tot_dual else 0.0,
                avg_retr=sum(retr_t) / len(retr_t) if retr_t else 0.0,
                fails=fails, viol=viol)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cycles", type=int, default=100, help="混合周期数(默认100)")
    ap.add_argument("--accel", action="store_true", help="用 L1 加减速口径")
    ap.add_argument("--adaptive", action="store_true",
                    help="A1 自适应权重查表(报告主口径 H = --accel --adaptive)")
    a = ap.parse_args()
    if a.accel:
        ws.ACCEL = True

    goods = ws.gen_goods(N_INIT, SEED)
    w_max = max(g.weight for g in goods)
    f_max = max(g.freq for g in goods)
    if a.adaptive:
        d_on, bg_on = ws.lookup_weights(N_INIT, "skew", "online")
        d_ba, bg_ba = ws.lookup_weights(N_INIT, "skew", "batch")
        fn = ws.make_score_fn(1.0, bg_on / 2, bg_on / 2, d_on, w_max, f_max)
        fn_batch = ws.make_score_fn(1.0, bg_ba / 2, bg_ba / 2, d_ba, w_max, f_max)
    else:
        fn = ws.make_score_fn(1.0, 0.6, 0.4, 0.15, w_max, f_max)
        fn_batch = fn
    new_goods, requests = build_workload(goods, a.cycles, SEED)

    motion = ("梯形加减速" if ws.ACCEL else "匀速") + ("+自适应权重" if a.adaptive else "+固定权重")
    print(f"混合作业流:{a.cycles} 周期(每周期1存+1取,共{2*a.cycles}次作业),"
          f"口径={motion},seed={SEED}")
    print(f"{'策略':<16}{'单命令总时(s)':>13}{'双命令总时(s)':>13}{'节省':>7}"
          f"{'吞吐(双命令,次/h)':>17}{'出库均时(s)':>11}{'失败':>5}{'违规':>5}")
    rows = []
    for s in STRATS:
        m = run_mixed(s, goods, new_goods, requests, fn, w_max, f_max, fn_batch)
        rows.append((s, m))
        print(f"{LBL[s]:<16}{m['tot_single']:>13.0f}{m['tot_dual']:>13.0f}"
              f"{m['saving']:>6.1f}%{m['thr_dual']:>15.0f}{m['avg_retr']:>11.2f}"
              f"{m['fails']:>5}{m['viol']:>5}")

    base = dict(rows)["seq"]
    best = dict(rows)["awra"]
    print(f"\nawra 布局 vs seq 布局(双命令口径):混合流总时 "
          f"{base['tot_dual']:.0f}→{best['tot_dual']:.0f}s"
          f"(降 {(1-best['tot_dual']/base['tot_dual'])*100:.1f}%),"
          f"吞吐 {base['thr_dual']:.0f}→{best['thr_dual']:.0f} 次/h"
          f"(提 {(best['thr_dual']/base['thr_dual']-1)*100:.1f}%)")
    print(f"双命令 vs 单命令(awra 布局):节省 {best['saving']:.1f}% —— 存取联程省空驶")

    # ---- CSV ----
    os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
    path = os.path.join(HERE, "out", "mixed_ops.csv")
    with open(path, "w", newline="", encoding="utf-8-sig") as fp:
        w = csv.writer(fp)
        w.writerow(["strategy", "motion", "cycles", "tot_single_s", "tot_dual_s",
                    "saving_pct", "thr_single_ops_h", "thr_dual_ops_h",
                    "avg_retrieve_s", "fails", "viol"])
        for s, m in rows:
            w.writerow([s, "trapezoid" if ws.ACCEL else "uniform", a.cycles,
                        round(m["tot_single"], 1), round(m["tot_dual"], 1),
                        round(m["saving"], 2), round(m["thr_single"], 1),
                        round(m["thr_dual"], 1), round(m["avg_retr"], 3),
                        m["fails"], m["viol"]])

    # ---- fig8 ----
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, (axL, axR) = plt.subplots(1, 2, figsize=(12, 4.2))
    x = range(len(STRATS))
    w_ = 0.36
    axL.bar([i - w_ / 2 for i in x], [dict(rows)[s]["tot_single"] for s in STRATS],
            w_, color="#90a4ae", label="单命令(两趟独立往返)")
    axL.bar([i + w_ / 2 for i in x], [dict(rows)[s]["tot_dual"] for s in STRATS],
            w_, color="#2e7d32", label="双命令(存取联程)")
    for i, s in enumerate(STRATS):
        m = dict(rows)[s]
        axL.text(i + w_ / 2, m["tot_dual"], f"-{m['saving']:.0f}%",
                 ha="center", va="bottom", fontsize=9, color="#2e7d32")
    axL.set_xticks(list(x))
    axL.set_xticklabels([LBL[s] for s in STRATS], fontsize=8)
    axL.set_ylabel(f"{a.cycles}周期混合流总时间 (s)")
    axL.set_title("单命令 vs 双命令周期")
    axL.legend(fontsize=9)
    axL.spines[["top", "right"]].set_visible(False)
    thr = [dict(rows)[s]["thr_dual"] for s in STRATS]
    bars = axR.bar(x, thr, color=["#8d6e63", "#1976d2", "#f9a825", "#2e7d32"])
    for b, v in zip(bars, thr):
        axR.text(b.get_x() + b.get_width() / 2, v, f"{v:.0f}", ha="center",
                 va="bottom", fontsize=9)
    axR.set_xticks(list(x))
    axR.set_xticklabels([LBL[s] for s in STRATS], fontsize=8)
    axR.set_ylabel("吞吐(存取次数/小时,双命令)")
    axR.set_title("单位时间存取量(题面指标)——布局质量在出库侧兑现")
    axR.spines[["top", "right"]].set_visible(False)
    fig.suptitle(f"L2 存取混合作业流({a.cycles}周期,{motion}口径,seed={SEED})", fontsize=12)
    fig.tight_layout()
    os.makedirs(os.path.join(HERE, "figs"), exist_ok=True)
    fig.savefig(os.path.join(HERE, "figs", "fig8_混合作业.png"), dpi=300)
    print(f"输出:{path} + figs/fig8_混合作业.png")


if __name__ == "__main__":
    main()
