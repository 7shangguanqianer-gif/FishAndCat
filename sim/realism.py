# -*- coding: utf-8 -*-
"""
realism.py — L7 拟真度阶梯:三档同管线对比(档1 数据模型 / 档2 主口径H / 档3 工业场景)
设计(docs/L7_拟真度阶梯设计.md,0705 用户拍板"分3档展示"):
  三档共用同一管线 = 初始入库 120 件 + 混合流 100 周期(每周期1存+1取,双命令),
  只差拟真开关,保证跨档可比:
    档1 = 匀速 + 固定权重 + 固定节拍 + 无装卸 + 频次全知 + 无故障(对照口径,文献可比)
    档2 = 梯形加减速 + 自适应权重(= 主口径 H,复用 mixed_ops.run_mixed 保证数字同源)
    档3 = 档2 物理口径 + 泊松到达(峰谷) + 装卸时间 + 频次估计噪声 + 故障注入
  档3 定位=「全拟真验证」:证明主口径结论(策略排序/降幅方向/违规0)在最真实场景下成立;
  头条 H 锁不动,本脚本不进回归门(与 sensitivity.py 同例)。
跨档可比指标:出库均时(纯行程,C3 流版)/ 双命令服务总时 / 违规;
档3 专属指标:响应时间 P50/P95(含排队)、利用率、故障停机——工业客户视角(可用性)。
口径纪律:装卸时间只进"服务时间/忙时",不进"出库行程均时"——后者跨档同定义。
运行:python realism.py            → out/realism_matrix.csv + figs/fig16_拟真度阶梯.png
     python realism.py --quick    → 30 周期自检
"""
import argparse
import csv
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import warehouse_sim as ws
from mixed_ops import LBL, STRATS, build_workload, initial_layout, run_mixed

HERE = os.path.dirname(os.path.abspath(__file__))
SEED, N_INIT, RULE = 2026, 120, "and"

# ---- 档3 拟真参数(占位值,标注〔G*〕待 deep-research 回填后进 canonical G 节)----
HANDLE_S = 15.0        # 〔G1〕单次存/取的装卸附加时间 s(I/O 侧+货位侧两次货叉循环合计)
RHO_PEAK = 0.75        # 〔G2〕高峰时段堆垛机目标利用率(决定泊松到达强度)
RHO_OFF = 0.35         # 〔G2〕低谷时段目标利用率
FREQ_SIGMA = 0.30      # 〔G3〕访问频次估计噪声:f_est = f_true·exp(N(0,σ²)) 对数正态乘性
MTBF_S = 3000.0        # 〔G4〕忙时平均无故障时间 s(占位:保证百周期流内可见 1~2 次)
MTTR_S = 600.0         # 〔G4〕平均修复时间 s


def noisy_clone(goods, sigma, seed):
    """频次估计噪声:决策侧用 f_est 克隆(布局/评分都基于估计值),
    真实需求抽样(build_workload 的 requests)仍用 f_true——现实=画像不准但需求是真的。
    返回 gid 对齐的克隆列表;sigma=0 时返回原对象(档1/2 路径零扰动)。"""
    if sigma <= 0:
        return list(goods)
    rng = random.Random(seed)
    out = []
    for g in goods:
        c = ws.Good(g.gid, g.name, g.weight, g.freq * math.exp(rng.gauss(0.0, sigma)),
                    g.vol)
        out.append(c)
    return out


def run_tier3(strat_name, goods, new_goods, requests, fn, w_max, f_max,
              fn_batch=None, cycles=100, seed=SEED):
    """档3 事件驱动混合流:单服务台(1台堆垛机)+ 泊松到达(峰谷交替)+
    装卸常数 + 频次噪声(经克隆注入)+ 故障注入(忙时 Exp(MTBF),修 MTTR)。
    负载(new_goods/requests 的身份序列)与档1/2 完全相同——只叠拟真层,公平口径。"""
    # 决策侧全部用带噪克隆;pos_of 按 gid 记位,取货按 gid 查位,与真值对象解耦
    goods_est = noisy_clone(goods, FREQ_SIGMA, seed + 21)
    new_est = noisy_clone(new_goods, FREQ_SIGMA, seed + 22)
    wh, pos_of = initial_layout(strat_name, goods_est, fn_batch or fn, w_max, f_max)
    online = {"seq": ws.strat_seq, "near": ws.strat_near,
              "score": ws.strat_score, "awra": ws.strat_score}[strat_name]

    # 无约束平均"任务对"服务时长(行程+装卸)→ 反推泊松到达强度 λ=ρ/E[pair]
    #(自适应估计,避免拍第二个脑袋;用档2 同负载的均值近似)
    probe = run_mixed(strat_name, goods_est, new_est, requests, fn, w_max, f_max,
                      fn_batch)
    e_pair = probe["tot_dual"] / cycles + 2 * HANDLE_S

    rng_arr = random.Random(seed + 23)
    rng_fail = random.Random(seed + 29)
    # 峰谷交替:前半高峰、后半低谷(每档同一到达序列种子,策略间同到达流)
    arrivals, t = [], 0.0
    for k in range(cycles):
        rho = RHO_PEAK if k < cycles // 2 else RHO_OFF
        t += rng_arr.expovariate(rho / e_pair)
        arrivals.append(t)
    next_fail_busy = rng_fail.expovariate(1.0 / MTBF_S)   # 按忙时累计触发

    crane_free = 0.0
    busy_acc = 0.0
    tot_dual = 0.0
    retr_t, resp = [], []
    fails = viol = n_down = 0
    downtime = 0.0
    for k, (g_in, g_out) in enumerate(zip(new_est, requests)):
        s_out = pos_of.pop(g_out.gid)
        s_in = online(wh, g_in, fn)
        if s_in is None:
            fails += 1
            wh.remove(s_out[0], s_out[1])
            continue
        if g_in.weight > ws.tier_cap(s_in[1]) or g_in.vol > ws.CELL_VOL:
            viol += 1
        t_in = ws.travel_time(*s_in)
        t_link = ws.travel_time_between(s_in[0], s_in[1], s_out[0], s_out[1])
        t_out = ws.travel_time(*s_out)
        service = t_in + t_link + t_out + 2 * HANDLE_S    # 双命令:存取各一次装卸
        start = max(arrivals[k], crane_free)
        # 故障:服务把忙时钟推过触发点 → 本单内插入一次修复(修完继续)
        if busy_acc + service > next_fail_busy:
            service += MTTR_S
            downtime += MTTR_S
            n_down += 1
            next_fail_busy = busy_acc + service + rng_fail.expovariate(1.0 / MTBF_S)
        finish = start + service
        crane_free = finish
        busy_acc += service
        tot_dual += t_in + t_link + t_out                 # 纯行程(跨档可比口径)
        retr_t.append(t_out)
        resp.append(finish - arrivals[k])
        wh.put(s_in[0], s_in[1], g_in)
        pos_of[g_in.gid] = s_in
        wh.remove(s_out[0], s_out[1])
    resp.sort()
    n = len(resp)
    makespan = crane_free
    return dict(tot_dual=tot_dual,
                busy_total=busy_acc,
                avg_retr=sum(retr_t) / len(retr_t) if retr_t else 0.0,
                resp_p50=resp[n // 2] if n else 0.0,
                resp_p95=resp[min(n - 1, int(n * 0.95))] if n else 0.0,
                util=(busy_acc - downtime) / makespan if makespan else 0.0,
                n_down=n_down, downtime=downtime,
                fails=fails, viol=viol)


def tier12(tier, goods, new_goods, requests, cycles):
    """档1/档2:直接复用 mixed_ops.run_mixed(与 F8 数字同源)。"""
    w_max = max(g.weight for g in goods)
    f_max = max(g.freq for g in goods)
    ws.ACCEL = (tier == 2)
    if tier == 2:
        d_on, bg_on = ws.lookup_weights(N_INIT, "skew", "online")
        d_ba, bg_ba = ws.lookup_weights(N_INIT, "skew", "batch")
        fn = ws.make_score_fn(1.0, bg_on / 2, bg_on / 2, d_on, w_max, f_max)
        fnb = ws.make_score_fn(1.0, bg_ba / 2, bg_ba / 2, d_ba, w_max, f_max)
    else:
        fn = ws.make_score_fn(1.0, 0.6, 0.4, 0.15, w_max, f_max)
        fnb = fn
    out = {}
    for s in STRATS:
        m = run_mixed(s, goods, new_goods, requests, fn, w_max, f_max, fnb)
        out[s] = dict(tot_dual=m["tot_dual"], avg_retr=m["avg_retr"],
                      busy_total=m["tot_dual"], resp_p50=None, resp_p95=None,
                      util=None, n_down=0, downtime=0.0,
                      fails=m["fails"], viol=m["viol"])
    return out


def tier3(goods, new_goods, requests, cycles):
    w_max = max(g.weight for g in goods)
    f_max = max(g.freq for g in goods)
    ws.ACCEL = True                                       # 档3 = 档2 物理口径之上叠拟真
    d_on, bg_on = ws.lookup_weights(N_INIT, "skew", "online")
    d_ba, bg_ba = ws.lookup_weights(N_INIT, "skew", "batch")
    fn = ws.make_score_fn(1.0, bg_on / 2, bg_on / 2, d_on, w_max, f_max)
    fnb = ws.make_score_fn(1.0, bg_ba / 2, bg_ba / 2, d_ba, w_max, f_max)
    return {s: run_tier3(s, goods, new_goods, requests, fn, w_max, f_max, fnb,
                         cycles=cycles)
            for s in STRATS}


def main():
    global HANDLE_S
    ap = argparse.ArgumentParser()
    ap.add_argument("--cycles", type=int, default=100)
    ap.add_argument("--quick", action="store_true", help="30 周期快速自检")
    ap.add_argument("--handle", type=float, default=None,
                    help="覆盖装卸时间 s/次(canonical G1;敏感性扫描用,如 10/15/20)")
    a = ap.parse_args()
    if a.handle is not None:
        HANDLE_S = a.handle
    cycles = 30 if a.quick else a.cycles

    goods = ws.gen_goods(N_INIT, SEED)
    new_goods, requests = build_workload(goods, cycles, SEED)

    print(f"L7 拟真度阶梯:{cycles} 周期混合流,seed={SEED}")
    print(f"档3 拟真参数(占位,待研究回填):装卸 {HANDLE_S}s/次,ρ峰谷 "
          f"{RHO_PEAK}/{RHO_OFF},频次噪声 σ={FREQ_SIGMA},MTBF/MTTR "
          f"{MTBF_S:.0f}/{MTTR_S:.0f}s")
    tiers = {1: tier12(1, goods, new_goods, requests, cycles),
             2: tier12(2, goods, new_goods, requests, cycles),
             3: tier3(goods, new_goods, requests, cycles)}
    TNAME = {1: "档1 数据模型", 2: "档2 主口径H", 3: "档3 工业场景"}

    for t in (1, 2, 3):
        print(f"\n—— {TNAME[t]} ——")
        hdr = f"{'策略':<14}{'出库均时s':>9}{'行程总时s':>10}{'违规':>5}"
        if t == 3:
            hdr += f"{'响应P50s':>9}{'响应P95s':>9}{'利用率':>7}{'故障':>5}"
        print(hdr)
        for s in STRATS:
            m = tiers[t][s]
            line = f"{LBL[s]:<14}{m['avg_retr']:>9.2f}{m['tot_dual']:>10.0f}{m['viol']:>5}"
            if t == 3:
                line += (f"{m['resp_p50']:>9.0f}{m['resp_p95']:>9.0f}"
                         f"{m['util']:>7.2f}{m['n_down']:>5}")
            print(line)
        d = (1 - tiers[t]["awra"]["avg_retr"] / tiers[t]["seq"]["avg_retr"]) * 100
        print(f"  awra vs seq 出库均时降幅:{d:.1f}%")

    # 阶梯核心句
    drops = {t: (1 - tiers[t]["awra"]["avg_retr"] / tiers[t]["seq"]["avg_retr"]) * 100
             for t in (1, 2, 3)}
    order_keep = all(
        tiers[t]["awra"]["avg_retr"] < tiers[t]["score"]["avg_retr"]
        < tiers[t]["seq"]["avg_retr"] for t in (1, 2, 3))
    print(f"\n★阶梯结论:awra 较 seq 出库均时降幅 档1 {drops[1]:.1f}% → 档2 "
          f"{drops[2]:.1f}% → 档3 {drops[3]:.1f}%;"
          f"策略排序三档{'保持' if order_keep else '变化(需定位!)'};"
          f"违规合计 {sum(tiers[t][s]['viol'] for t in tiers for s in STRATS)}")

    # ---- CSV ----
    os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
    path = os.path.join(HERE, "out", "realism_matrix.csv")
    with open(path, "w", newline="", encoding="utf-8-sig") as fp:
        w = csv.writer(fp)
        w.writerow(["tier", "strategy", "avg_retrieve_s", "travel_dual_s",
                    "busy_total_s", "resp_p50_s", "resp_p95_s", "util",
                    "n_down", "downtime_s", "fails", "viol"])
        for t in (1, 2, 3):
            for s in STRATS:
                m = tiers[t][s]
                w.writerow([t, s, round(m["avg_retr"], 3), round(m["tot_dual"], 1),
                            round(m["busy_total"], 1),
                            "" if m["resp_p50"] is None else round(m["resp_p50"], 1),
                            "" if m["resp_p95"] is None else round(m["resp_p95"], 1),
                            "" if m["util"] is None else round(m["util"], 3),
                            m["n_down"], round(m["downtime"], 1),
                            m["fails"], m["viol"]])
        w.writerow([])
        w.writerow(["param", "value", "note"])
        for k, v, note in [
            ("handle_s", HANDLE_S, "G1 占位待回填"),
            ("rho_peak", RHO_PEAK, "G2 占位待回填"),
            ("rho_off", RHO_OFF, "G2 占位待回填"),
            ("freq_sigma", FREQ_SIGMA, "G3 占位待回填"),
            ("mtbf_s", MTBF_S, "G4 占位待回填"),
            ("mttr_s", MTTR_S, "G4 占位待回填"),
            ("cycles", cycles, ""), ("seed", SEED, "")]:
            w.writerow([k, v, note])

    # ---- fig16 ----
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, (axL, axR) = plt.subplots(1, 2, figsize=(12.5, 4.4))
    colors = {"seq": "#8d6e63", "near": "#1976d2", "score": "#f9a825",
              "awra": "#2e7d32"}
    xs = [1, 2, 3]
    for s in STRATS:
        ys = [tiers[t][s]["avg_retr"] for t in xs]
        axL.plot(xs, ys, "o-", color=colors[s], label=LBL[s], linewidth=2)
    for t in xs:
        axL.text(t, tiers[t]["awra"]["avg_retr"] - 0.35,
                 f"-{drops[t]:.0f}%", ha="center", fontsize=9, color="#2e7d32")
    axL.set_xticks(xs)
    axL.set_xticklabels([TNAME[t] for t in xs], fontsize=9)
    axL.set_ylabel("出库均时 s(纯行程口径,跨档可比)")
    axL.set_title("三档拟真下的布局质量:结论方向不变,数字逐档更真")
    axL.legend(fontsize=8)
    axL.spines[["top", "right"]].set_visible(False)

    w_ = 0.36
    x3 = range(len(STRATS))
    p50 = [tiers[3][s]["resp_p50"] for s in STRATS]
    p95 = [tiers[3][s]["resp_p95"] for s in STRATS]
    axR.bar([i - w_ / 2 for i in x3], p50, w_, color="#90a4ae", label="响应 P50")
    axR.bar([i + w_ / 2 for i in x3], p95, w_, color="#c62828", label="响应 P95")
    axR.set_xticks(list(x3))
    axR.set_xticklabels([LBL[s] for s in STRATS], fontsize=8)
    axR.set_ylabel("任务响应时间 s(到达→完成,含排队/装卸/故障)")
    axR.set_title(f"档3 工业视角:响应分位与可用性(故障注入 "
                  f"{tiers[3]['awra']['n_down']} 次示例)")
    axR.legend(fontsize=9)
    axR.spines[["top", "right"]].set_visible(False)
    fig.suptitle(f"L7 拟真度阶梯({cycles}周期混合流,seed={SEED};"
                 f"档3参数为占位值,待行业数据回填)", fontsize=12)
    fig.tight_layout()
    os.makedirs(os.path.join(HERE, "figs"), exist_ok=True)
    fig.savefig(os.path.join(HERE, "figs", "fig16_拟真度阶梯.png"), dpi=300)
    print(f"输出:{path} + figs/fig16_拟真度阶梯.png")


if __name__ == "__main__":
    main()
