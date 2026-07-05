# -*- coding: utf-8 -*-
"""
reslot_cycle.py — A2 周期重排闭环:布局熵漂移 + 夜间自愈(算法天花板路线 T10)
故事:仓库不是"摆好就完了",它要运行——
  白天:混合流在线决策(逐件到达,只能拿当下最优),布局质量随时间漂移劣化;
  中段:需求漂移事件(热货变冷、冷货变热,模拟季节/爆品切换)——布局与需求错配;
  夜间:低峰期批量重排(重定位+成对交换,与 AWRA-LS 第三段同一算子,PLC 侧
       FB_LocalSwapImprove 零新增复用),把布局拉回最优;重排本身消耗行车时间,
       按"取旧位→放新位→回"三段计成本,算净收益——不吃免费午餐的账。
对比:①不重排(纯在线漂移) ②每夜重排(自愈闭环),同一负载(B6 扩展)。
运行:python reslot_cycle.py [--cycles 600] [--day 100] [--no-drift]
输出:out/reslot_cycle.csv + figs/fig11_重排闭环.png
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


def layout_quality(wh, pos_of, goods_by_gid):
    """当前布局的期望取货时间(C3 口径,对在库货物)。"""
    fs = ts = 0.0
    for gid, (c, t) in pos_of.items():
        g = goods_by_gid[gid]
        fs += g.freq
        ts += g.freq * ws.travel_time(c, t)
    return ts / fs if fs else 0.0


def reslot_pass(wh, pos_of, goods_by_gid, day_len, budget_moves=20, margin=1.2):
    """夜间重排(成本感知,v2):重排是经济决策,不是免费优化——
    收益 = 到下次重排前的期望取货节省 = 2·[t(旧)−t(新)] × (该货频次/总频次 × day_len 次取货)
    成本 = 搬运行车三段 t(0→旧)+t(旧→新)+t(新→0)
    只执行 收益 > margin×成本 的候选,按净收益降序,最多 budget_moves 次(夜班时长预算)。
    朴素版(逢改善就搬)实测净亏 5 倍:每夜 ~660 次搬运烧光收益——这本身写进报告当反例。"""
    f_sum = sum(goods_by_gid[gid].freq for gid in pos_of) or 1.0
    cands = []
    for gid, (c0, t0) in pos_of.items():
        g = goods_by_gid[gid]
        t_old = ws.travel_time(c0, t0)
        best, bt = None, t_old
        for c in range(ws.COLS):
            for t in range(ws.TIERS):
                if wh.feasible(c, t, g):
                    tt = ws.travel_time(c, t)
                    if tt < bt - 1e-9:
                        bt, best = tt, (c, t)
        if best is None:
            continue
        picks = g.freq / f_sum * day_len                 # 下个"白天"的期望被取次数
        benefit = 2.0 * (t_old - bt) * picks             # 双程口径节省
        cost = (t_old + ws.travel_time_between(c0, t0, best[0], best[1])
                + ws.travel_time(*best))
        if benefit > margin * cost:
            cands.append((benefit - cost, "move", gid, (c0, t0), best))

    # 交换候选:热-远货 ↔ 冷-近货(近区满员时重定位无位可去,交换才是主力;
    # 交换按两次搬运计成本=保守,实际可经 I/O 缓存一趟完成)
    by_freq = sorted(pos_of.keys(), key=lambda g: -goods_by_gid[g].freq)
    hot, cold = by_freq[:40], by_freq[-60:]
    for gh in hot:
        g1 = goods_by_gid[gh]
        c1, t1 = pos_of[gh]
        th = ws.travel_time(c1, t1)
        for gc in cold:
            g2 = goods_by_gid[gc]
            c2, t2 = pos_of[gc]
            tc = ws.travel_time(c2, t2)
            if th <= tc + 1e-9:
                continue                                 # 热货本来就更近,不换
            if not (wh.fits(c2, t2, g1) and wh.fits(c1, t1, g2)):
                continue                                 # 承重/容积双向复查
            picks_h = g1.freq / f_sum * day_len
            picks_c = g2.freq / f_sum * day_len
            benefit = 2.0 * (th - tc) * (picks_h - picks_c)
            cost = ((th + ws.travel_time_between(c1, t1, c2, t2) + tc)
                    + (tc + ws.travel_time_between(c2, t2, c1, t1) + th))
            if benefit > margin * cost:
                cands.append((benefit - cost, "swap", (gh, gc), (c1, t1), (c2, t2)))

    cands.sort(key=lambda x: -x[0])
    moves = []
    for cand in cands:
        if len(moves) >= budget_moves:
            break
        if cand[1] == "move":
            _, _, gid, s0, s1 = cand
            g = goods_by_gid[gid]
            if pos_of[gid] != s0 or not wh.feasible(s1[0], s1[1], g):
                continue                                 # 位置被先执行的动作占了
            wh.remove(s0[0], s0[1])
            wh.put(s1[0], s1[1], g)
            pos_of[gid] = s1
            moves.append((gid, s0, s1))
        else:
            _, _, (gh, gc), s1, s2 = cand
            g1, g2 = goods_by_gid[gh], goods_by_gid[gc]
            if pos_of[gh] != s1 or pos_of[gc] != s2:
                continue
            if not (wh.fits(s2[0], s2[1], g1) and wh.fits(s1[0], s1[1], g2)):
                continue
            wh.grid[s1[0]][s1[1]], wh.grid[s2[0]][s2[1]] = g2, g1
            pos_of[gh], pos_of[gc] = s2, s1
            moves.append((gh, s1, s2))
            moves.append((gc, s2, s1))
    return moves


def move_cost(moves):
    """重排行车成本,返回 (时间s, 路径m):每次搬运 = I/O→旧位(空驶)+旧位→新位(载货)
    +新位→I/O(空驶)。保守口径:三段全计。路径按曼哈顿(C5 磨损代理)——搬运的
    "额外损耗"两种货币都记账;错误/损坏风险等未计价项由经济门槛的 margin=1.2 兜底。"""
    tot_t = tot_p = 0.0
    for _, (c0, t0), (c1, t1) in moves:
        tot_t += (ws.travel_time(c0, t0)
                  + ws.travel_time_between(c0, t0, c1, t1)
                  + ws.travel_time(c1, t1))
        tot_p += (ws.path_len(c0, t0)
                  + abs(c1 - c0) * ws.CELL_W + abs(t1 - t0) * ws.CELL_H
                  + ws.path_len(c1, t1))
    return tot_t, tot_p


THETA_DRIFT = 0.03      # 触发阈值:布局质量较"上次重排后基准"劣化超 3% 才开工(动态标准)


def simulate(policy, cycles, day_len, drift, seed, online="score"):
    """policy: 'none'=不重排 | 'nightly'=每夜必重排 | 'triggered'=漂移触发式(动态标准):
      夜间窗口先做一次零成本体检(当前布局质量 vs 上次重排后的基准),
      劣化 > THETA_DRIFT 才执行重排;体检通过=整夜休息(成本恰好为 0)。
      三级判据:①触发(漂移超阈)②单步放行(收益>margin×成本)③停止(夜班预算/无候选)。
    online: 回库在线决策用 'score'(频次感知)或 'near'(就近,不懂频次)。
    返回逐周期布局质量序列 + 累计账本(时间/路径两种货币+触发统计)。"""
    goods = ws.gen_goods(N_INIT, seed)
    w_max = max(g.weight for g in goods)
    f_max = max(g.freq for g in goods)
    fn_score = ws.make_score_fn(1.0, 0.6, 0.4, 0.15, w_max, f_max)

    wh, pos_of = None, None
    whl, placed, failed = ws.run_awra_ls(goods, RULE, fn_score, w_max, f_max)
    assert not failed
    wh = whl
    pos_of = {g.gid: p for g, p in placed}
    goods_by_gid = {g.gid: g for g in goods}

    # 负载(B7 循环访问口径):题面"访问频次"的本义 = 同一货物被反复存取
    # (工厂物料库:按需取用→加工/装配→回库);每周期取 1 件(∝频次),
    # 取出的货 LAG 周期后回库;每 10 次回库有 1 次汰换成新货(≈10% 周转)。
    # 负载只依赖货物身份与 seed → 两种策略面对完全相同的事件序列(公平)。
    LAG, TURNOVER = 5, 10
    new_goods = ws.gen_goods(cycles // TURNOVER + 2, seed + 7)
    for i, g in enumerate(new_goods):
        g.gid = 1000 + i + 1
        g.name = f"N{i+1:03d}"
    rng = random.Random(seed + 13)
    drift_at = cycles // 2 if drift else -1

    def score_g(g, c, t):
        return fn_score(g, c, t)

    quality, flow_time, reslot_time, reslot_moves = [], 0.0, 0.0, 0
    reslot_path = 0.0                     # 搬运磨损账(曼哈顿 m,C5)
    nights_run, nights_skip = 0, 0        # 触发统计
    q_ref = layout_quality(wh, pos_of, goods_by_gid)   # 触发基准=初始(AWRA)质量
    pool = list(goods)                    # 当前在库
    out_queue = []                        # (回库周期, 货物)
    new_idx = 0
    n_return = 0
    for k in range(cycles):
        # ---- 需求漂移事件:全部在场货物频次洗牌(同边际分布;两策略同 seed 同事件)----
        if k == drift_at:
            live = pool + [g for _, g in out_queue]
            freqs = [g.freq for g in live]
            random.Random(seed + 99).shuffle(freqs)
            for idx, g in enumerate(live):
                g.freq = freqs[idx]
        # ---- 到期回库(与本周期出库合成双命令) ----
        g_in, s_in = None, None
        if out_queue and out_queue[0][0] <= k:
            _, g_in = out_queue.pop(0)
            n_return += 1
            if n_return % TURNOVER == 0 and new_idx < len(new_goods):
                old = g_in
                g_in = new_goods[new_idx]        # 汰换:旧货退役,新货顶替
                g_in.freq = old.freq             # 承接需求槽位(频次守恒,防漂移叠加)
                new_idx += 1
            goods_by_gid[g_in.gid] = g_in
            strat_fn = ws.strat_score if online == "score" else ws.strat_near
            s_in = strat_fn(wh, g_in, score_g)
            assert s_in is not None
            wh.put(s_in[0], s_in[1], g_in)
            pos_of[g_in.gid] = s_in
            pool.append(g_in)
        # ---- 出库(∝频次) ----
        weights = [g.freq for g in pool]
        g_out = rng.choices(pool, weights=weights, k=1)[0]
        pool.remove(g_out)
        s_out = pos_of.pop(g_out.gid)
        out_queue.append((k + LAG, g_out))
        # ---- 计时:同周期有存有取=双命令联程,否则单命令往返 ----
        if s_in is not None:
            flow_time += (ws.travel_time(*s_in)
                          + ws.travel_time_between(s_in[0], s_in[1], s_out[0], s_out[1])
                          + ws.travel_time(*s_out))
        else:
            flow_time += 2 * ws.travel_time(*s_out)
        wh.remove(s_out[0], s_out[1])

        quality.append(layout_quality(wh, pos_of, goods_by_gid))
        # ---- 夜间窗口(成本感知+夜班预算;triggered 先过零成本体检) ----
        if policy in ("nightly", "triggered") and (k + 1) % day_len == 0 and k + 1 < cycles:
            if policy == "triggered":
                drift_now = (quality[-1] - q_ref) / q_ref if q_ref > 0 else 0.0
                if drift_now <= THETA_DRIFT:
                    nights_skip += 1          # 体检通过,整夜休息(成本 0)
                    continue
            moves = reslot_pass(wh, pos_of, goods_by_gid, day_len)
            mt, mp = move_cost(moves)
            reslot_time += mt
            reslot_path += mp
            reslot_moves += len(moves)
            nights_run += 1
            quality[-1] = layout_quality(wh, pos_of, goods_by_gid)
            q_ref = quality[-1]               # 重排后刷新触发基准
    return dict(quality=quality, flow=flow_time, reslot=reslot_time,
                moves=reslot_moves, path=reslot_path,
                nights_run=nights_run, nights_skip=nights_skip)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cycles", type=int, default=600)
    ap.add_argument("--day", type=int, default=100, help="每'天'的周期数(夜间重排间隔)")
    ap.add_argument("--no-drift", action="store_true", help="关闭中段需求漂移事件")
    a = ap.parse_args()
    drift = not a.no_drift

    print(f"重排闭环仿真:{a.cycles} 周期,每 {a.day} 周期一夜"
          f"{',第 ' + str(a.cycles//2) + ' 周期需求漂移' if drift else ',无漂移'},seed={SEED}")
    combos = [("near", "none"), ("near", "nightly"), ("near", "triggered"),
              ("score", "none"), ("score", "nightly"), ("score", "triggered")]
    lbl = {("near", "none"): "near在线·不重排(双无)",
           ("near", "nightly"): "near在线·每夜必排",
           ("near", "triggered"): "near在线·漂移触发(动态标准)",
           ("score", "none"): "score在线·不重排(在线自愈)",
           ("score", "nightly"): "score在线·每夜必排",
           ("score", "triggered"): "score在线·漂移触发(动态标准)"}
    color = {("near", "none"): "#c62828", ("near", "nightly"): "#ef6c00",
             ("near", "triggered"): "#8d6e63",
             ("score", "none"): "#1976d2", ("score", "nightly"): "#2e7d32",
             ("score", "triggered"): "#6a1b9a"}
    res = {}
    for online, pol in combos:
        res[(online, pol)] = simulate(pol, a.cycles, a.day, drift, SEED, online)

    import statistics as st
    print(f"\n{'组合':<26}{'均布局exp_t':>11}{'期末':>7}{'流转(s)':>9}"
          f"{'重排(s)':>8}{'搬运':>5}{'磨损(m)':>8}{'开工/休息':>9}{'净总时(s)':>10}")
    for key in combos:
        r = res[key]
        q = r["quality"]
        net = r["flow"] + r["reslot"]
        nights = f"{r['nights_run']}/{r['nights_skip']}"
        print(f"{lbl[key]:<26}{st.mean(q):>11.2f}{q[-1]:>7.2f}{r['flow']:>9.0f}"
              f"{r['reslot']:>8.0f}{r['moves']:>5}{r['path']:>8.0f}{nights:>9}{net:>10.0f}")
    nn = res[("near", "none")]["flow"]
    nr = res[("near", "nightly")]
    sn = res[("score", "none")]["flow"]
    sr = res[("score", "nightly")]
    nt = res[("near", "triggered")]
    stg = res[("score", "triggered")]
    print(f"\n结论四连:")
    print(f"①重排救笨策略:near+夜重排 净总时 {nr['flow']+nr['reslot']:.0f}s vs near裸奔 {nn:.0f}s"
          f"(净省 {(1-(nr['flow']+nr['reslot'])/nn)*100:.1f}%)")
    print(f"②在线智能自带自愈:score裸奔 {sn:.0f}s 已接近 near+重排——频次感知的在线决策"
          f"在每次回库时'免费重排'")
    print(f"③双保险:score+夜重排 {sr['flow']+sr['reslot']:.0f}s,对 score裸奔净"
          f"{'省' if sr['flow']+sr['reslot']<sn else '亏'} "
          f"{abs(1-(sr['flow']+sr['reslot'])/sn)*100:.1f}%——增量小因为在线已做对,"
          f"重排作为需求漂移的兜底")
    print(f"④动态标准(漂移>{THETA_DRIFT:.0%}才开工):score 触发式 开工{stg['nights_run']}夜/"
          f"休息{stg['nights_skip']}夜,净总时 {stg['flow']+stg['reslot']:.0f}s"
          f"(vs 每夜必排 {sr['flow']+sr['reslot']:.0f}s);near 触发式 开工{nt['nights_run']}夜/"
          f"休息{nt['nights_skip']}夜——标准自己会看策略下菜:布局稳就整夜休息,"
          f"漂移了才动手,自愈效果不打折")

    # ---- CSV ----
    os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
    path = os.path.join(HERE, "out", "reslot_cycle.csv")
    with open(path, "w", newline="", encoding="utf-8-sig") as fp:
        w = csv.writer(fp)
        w.writerow(["cycle"] + [f"q_{o}_{p}" for o, p in combos])
        for i in range(a.cycles):
            w.writerow([i + 1] + [round(res[k]["quality"][i], 4) for k in combos])
        w.writerow([])
        w.writerow(["online", "policy", "mean_quality", "final_quality", "flow_s",
                    "reslot_s", "moves", "reslot_path_m", "nights_run",
                    "nights_skip", "net_total_s"])
        for (o, p) in combos:
            r = res[(o, p)]
            w.writerow([o, p, round(st.mean(r["quality"]), 3),
                        round(r["quality"][-1], 3), round(r["flow"], 1),
                        round(r["reslot"], 1), r["moves"], round(r["path"], 1),
                        r["nights_run"], r["nights_skip"],
                        round(r["flow"] + r["reslot"], 1)])

    # ---- fig11 ----
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, ax = plt.subplots(figsize=(10.8, 4.6))
    xs = range(1, a.cycles + 1)

    def smooth(seq, win=25):
        """滑动平均:在库池逐周期变动使原始序列高频抖动,平滑后看趋势。"""
        out = []
        for i in range(len(seq)):
            lo = max(0, i - win + 1)
            out.append(sum(seq[lo:i + 1]) / (i + 1 - lo))
        return out

    for key in combos:
        ax.plot(xs, smooth(res[key]["quality"]), color=color[key],
                lw=1.5, ls="--" if key[1] == "triggered" else "-",
                label=lbl[key], alpha=0.95)
    for d in range(a.day, a.cycles, a.day):
        ax.axvline(d, color="#9e9e9e", ls=":", lw=0.5, alpha=0.5)
    if drift:
        ax.axvline(a.cycles // 2, color="#6a1b9a", ls="--", lw=1.4)
        ax.text(a.cycles // 2 + 5, ax.get_ylim()[1] * 0.97, "需求漂移事件",
                fontsize=9, color="#6a1b9a", va="top")
    ax.set_xlabel(f"循环访问周期(取用∝频次,LAG=5 回库,10%汰换;灰虚线=夜间窗口,每 {a.day} 周期)")
    ax.set_ylabel("布局质量:在库货物期望取货时间 (s)")
    ax.set_title("A2 重排闭环:在线智能 × 重排策略(不排/每夜/漂移触发)对照"
                 "(重排算子=FB_LocalSwapImprove,PLC 零新增;触发式虚线与每夜实线重合=本负载下每夜都该排)")
    ax.legend(fontsize=8, loc="upper left")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    os.makedirs(os.path.join(HERE, "figs"), exist_ok=True)
    fig.savefig(os.path.join(HERE, "figs", "fig11_重排闭环.png"), dpi=300)
    print(f"输出:{path} + figs/fig11_重排闭环.png")


if __name__ == "__main__":
    main()
