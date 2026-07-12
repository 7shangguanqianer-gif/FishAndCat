# -*- coding: utf-8 -*-
"""
correlated_storage.py — 关联存储(correlated storage assignment)对照实验(0710 夜)
对标 deep-research 升级点第 2 项。仿 dwell_point.py 模式:CRN 配对、30 seed、采纳/YAGNI 定论。

机理前提(设计的出发点,报告可引):
  本项目机型=单元负载(unit-load)堆垛机。文献中 correlated storage 的经典收益通道
  (多件订单一次巡回,Frazelle & Sharp 1989)在 unit-load 下**不存在**——串行取货每件
  必回 I/O,订单响应 = Σ 各件独立往返,与族相对位置无关(解析恒等,无需实验)。
  唯一收益通道 = **双命令连段 t_link**(存取穿插,Han et al. 1987):若存入件与当期
  取出件位置相近,联程 t(存位→取位) 缩短。共现需求(如"卖出即补货"的同族补货)使
  "存入件的目标区域 ≈ 取出件所在区域"成为可能——这才是 unit-load 下关联存储的正确形态。

对照 2×2(YAGNI 判定结构):
  base      awra 初始布局 + score 在线(族盲,=现行主口径)
  corr      关联存储:初始布局族聚集交换(后处理)+ 在线放置偏向"在库同族质心"
            —— 需要族先验(共现统计),布局层+决策层双改造
  link      双命令感知:在线放置偏向"当期取货位"(零先验,当期 s_out 已知)
            —— 一行逻辑的更简单替代;若它吃掉全部收益 ⇒ corr 无独立价值 ⇒ YAGNI
  corr+link 两者叠加(收益是否可加)
  在线偏向实现 = top-K 重排:score 最优前 K=10 的可行位中选连段最短者——
  "几乎不牺牲主口径的前提下顺路",天然限制单件口径副作用;不动 make_score_fn(口径红线)。

共现负载:货物身份/属性/请求序列与 mixed_ops.build_workload 完全一致(CRN,与主口径
  可比);族=叠加元数据:初始 120 件随机分族(族大小 4,**随机族=保守侧**:不假设
  族内频次相似,真实"同类货频次相关"场景只会更利好 corr,文档声明此边界)。
  新货入族:以 θ 概率 = 当期取出货的族(补货语义),否则随机族。θ∈{0, 0.5, 1.0}。
  θ=0 自检:corr/link 应≈base(无共现时顺路无从谈起+无害性检验)。

指标:双命令总时 tot_dual(主)/连段均时 t_link/出库均时 avg_retr(布局质量副作用)/
  终局布局期望取货 exp2(Σf·2t/Σf,双程;族聚集是否牺牲单件口径)/违规。
统计:30 seed 配对(paired_t,协议同 instance_gen);n_init=120,cycles=100。
运行:python correlated_storage.py [--seeds 30] [--smoke]
输出:out/correlated_storage.csv(长表)+ 控制台定论表
"""
import argparse
import csv
import os
import random
import sys
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

N_INIT, CYCLES, RULE = 120, 100, "sum"
SEED0, N_SEEDS = 2026, 30
FAM_SIZE, K_RERANK, SWAP_ROUNDS = 4, 10, 3
THETAS = (0.0, 0.5, 1.0)
VARIANTS = ("base", "corr", "link", "corr_link")


def assign_families(goods, new_goods, requests, theta, seed):
    """族标签(gid→fid)。初始件随机分族(保守:族与频次无关);
    新货以 θ 概率随当期取出货入族(补货共现),否则随机族。"""
    rng = random.Random(seed + 31)
    gids = [g.gid for g in goods]
    rng.shuffle(gids)
    fam = {}
    for i, gid in enumerate(gids):
        fam[gid] = i // FAM_SIZE
    n_fam = (len(gids) + FAM_SIZE - 1) // FAM_SIZE
    for g_new, g_out in zip(new_goods, requests):
        if rng.random() < theta:
            fam[g_new.gid] = fam[g_out.gid]
        else:
            fam[g_new.gid] = rng.randrange(n_fam)
    return fam


def fam_pair_dist(wh_positions, fam):
    """族内两两连段时间总和(聚集度量;wh_positions: gid→(c,t))。"""
    import warehouse_sim as ws
    byf = {}
    for gid, pos in wh_positions.items():
        byf.setdefault(fam[gid], []).append(pos)
    tot = 0.0
    for plist in byf.values():
        for i in range(len(plist)):
            for j in range(i + 1, len(plist)):
                tot += ws.travel_time_between(*plist[i], *plist[j])
    return tot


def cluster_swap(wh, pos_of, fam):
    """初始布局族聚集后处理:同格互换(双向 fits 且非预占),接受族内连段总和下降;
    确定性全对扫描,SWAP_ROUNDS 轮或收敛。返回 (交换数, 前距, 后距)。"""
    import warehouse_sim as ws
    gids = sorted(pos_of.keys())
    d0 = fam_pair_dist(pos_of, fam)
    n_swap = 0
    for _ in range(SWAP_ROUNDS):
        improved = False
        for i in range(len(gids)):
            for j in range(i + 1, len(gids)):
                ga, gb = gids[i], gids[j]
                pa, pb = pos_of[ga], pos_of[gb]
                if fam[ga] == fam[gb]:
                    continue
                a = wh.grid[pa[0]][pa[1]]
                b = wh.grid[pb[0]][pb[1]]
                if not (wh.fits(pb[0], pb[1], a) and wh.fits(pa[0], pa[1], b)):
                    continue
                # 试交换:族内距离变化(只涉及 ga/gb 两族,增量计算)
                before = _two_goods_fam_cost(pos_of, fam, ga, gb, pa, pb)
                after = _two_goods_fam_cost(pos_of, fam, ga, gb, pb, pa)
                if after < before - 1e-9:
                    wh.grid[pa[0]][pa[1]], wh.grid[pb[0]][pb[1]] = b, a
                    pos_of[ga], pos_of[gb] = pb, pa
                    n_swap += 1
                    improved = True
        if not improved:
            break
    return n_swap, d0, fam_pair_dist(pos_of, fam)


def _two_goods_fam_cost(pos_of, fam, ga, gb, pa, pb):
    """ga@pa、gb@pb 时,两货与各自族友的连段和(交换增量评估)。"""
    import warehouse_sim as ws
    tot = 0.0
    for gid, pos in pos_of.items():
        if gid == ga or gid == gb:
            continue
        if fam[gid] == fam[ga]:
            tot += ws.travel_time_between(*pos, *pa)
        if fam[gid] == fam[gb]:
            tot += ws.travel_time_between(*pos, *pb)
    return tot


def exp2(pos_of, goods_by_gid):
    """终局布局期望取货(双程,Σf·2t/Σf)——族聚集的单件口径副作用探针。"""
    import warehouse_sim as ws
    num = den = 0.0
    for gid, pos in pos_of.items():
        f = goods_by_gid[gid].freq
        num += f * 2 * ws.travel_time(*pos)
        den += f
    return num / den if den else 0.0


def pick_slot(wh, good, fn, variant, s_out, fam, pos_of):
    """在线选位:base=score 原式;link/corr/corr_link=score 前 K 重排选连段最短。
    corr 目标=在库同族质心;link 目标=当期取货位;叠加取两距之和。"""
    import warehouse_sim as ws
    slots = wh.empty_feasible_slots(good)
    if not slots:
        return None
    key0 = lambda s: (fn(good, *s), ws.travel_time(*s), s[1], s[0])
    if variant == "base":
        return min(slots, key=key0)
    topk = sorted(slots, key=key0)[:K_RERANK]
    tgt_fam = None
    if variant in ("corr", "corr_link"):
        mates = [pos_of[g] for g in pos_of
                 if fam.get(g) == fam.get(good.gid) and g != good.gid]
        if mates:
            cx = sum(p[0] for p in mates) / len(mates)
            cy = sum(p[1] for p in mates) / len(mates)
            tgt_fam = (cx, cy)

    def aux(s):
        d = 0.0
        if variant in ("link", "corr_link"):
            d += ws.travel_time_between(s[0], s[1], s_out[0], s_out[1])
        if variant in ("corr", "corr_link") and tgt_fam is not None:
            d += ws.travel_time_between(s[0], s[1],
                                        round(tgt_fam[0]), round(tgt_fam[1]))
        return d
    return min(topk, key=lambda s: (aux(s), key0(s)))


def run_variant(variant, wh, pos_of, goods_by_gid, new_goods, requests, fn, fam):
    """混合流 100 周期(骨架同 mixed_ops.run_mixed,加变体选位)。"""
    import warehouse_sim as ws
    tot_dual = link_sum = 0.0
    retr_t = []
    fails = viol = 0
    for g_in, g_out in zip(new_goods, requests):
        s_out = pos_of.pop(g_out.gid)
        s_in = pick_slot(wh, g_in, fn, variant, s_out, fam, pos_of)
        if s_in is None:
            fails += 1
            wh.remove(s_out[0], s_out[1])
            continue
        if g_in.weight > ws.tier_cap(s_in[1]) or g_in.vol > ws.CELL_VOL:
            viol += 1
        t_in = ws.travel_time(*s_in)
        t_out = ws.travel_time(*s_out)
        t_link = ws.travel_time_between(s_in[0], s_in[1], s_out[0], s_out[1])
        tot_dual += t_in + t_link + t_out
        link_sum += t_link
        retr_t.append(t_out)
        wh.put(s_in[0], s_in[1], g_in)
        pos_of[g_in.gid] = s_in
        wh.remove(s_out[0], s_out[1])
        goods_by_gid[g_in.gid] = g_in
    n = len(retr_t)
    return dict(tot_dual=tot_dual, t_link_avg=link_sum / n if n else 0.0,
                avg_retr=sum(retr_t) / n if n else 0.0,
                exp2_final=exp2(pos_of, goods_by_gid), fails=fails, viol=viol)


def run_seed(args):
    """worker:单 seed 全部 θ×变体。awra 初始布局每 seed 只算一次(布局昂贵,
    交换/在线差异不影响初始解——CRN 严格配对)。"""
    seed = args
    import copy
    import warehouse_sim as ws
    from mixed_ops import build_workload, initial_layout

    goods = ws.gen_goods(N_INIT, seed)
    w_max = max(g.weight for g in goods)
    f_max = max(g.freq for g in goods)
    ws.ACCEL = True                                    # H 口径物理层
    d_on, bg_on = ws.lookup_weights(N_INIT, "skew", "online")
    d_ba, bg_ba = ws.lookup_weights(N_INIT, "skew", "batch")
    fn = ws.make_score_fn(1.0, bg_on / 2, bg_on / 2, d_on, w_max, f_max)
    fnb = ws.make_score_fn(1.0, bg_ba / 2, bg_ba / 2, d_ba, w_max, f_max)
    new_goods, requests = build_workload(goods, CYCLES, seed)
    wh0, pos0 = initial_layout("awra", goods, fnb, w_max, f_max)

    rows = []
    for theta in THETAS:
        fam = assign_families(goods, new_goods, requests, theta, seed)
        for variant in VARIANTS:
            wh = copy.deepcopy(wh0)
            pos_of = dict(pos0)
            swap_n = 0
            d_before = d_after = 0.0
            if variant in ("corr", "corr_link"):
                swap_n, d_before, d_after = cluster_swap(wh, pos_of, fam)
            gb = {g.gid: g for g in goods}
            m = run_variant(variant, wh, pos_of, gb, new_goods, requests, fn, fam)
            rows.append(dict(theta=theta, variant=variant, seed=seed,
                             swap_n=swap_n,
                             fam_dist_drop=round(1 - d_after / d_before, 4)
                             if d_before else 0.0, **{k: round(v, 4)
                             if isinstance(v, float) else v
                             for k, v in m.items()}))
    return rows


def mean(v):
    return sum(v) / len(v) if v else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=N_SEEDS)
    ap.add_argument("--smoke", action="store_true")
    a = ap.parse_args()
    seeds = [SEED0] if a.smoke else list(range(SEED0, SEED0 + a.seeds))
    from instance_gen import paired_t

    print(f"关联存储对照:{len(THETAS)} θ × {len(VARIANTS)} 变体 × {len(seeds)} seeds"
          f"(awra 初始布局每 seed 复用,top-K={K_RERANK} 重排)")
    results = []
    if a.smoke:
        for sd in seeds:
            results.extend(run_seed(sd))
    else:
        with ProcessPoolExecutor(max_workers=max(2, (os.cpu_count() or 4) - 2)) as ex:
            for i, rows in enumerate(ex.map(run_seed, seeds, chunksize=1)):
                results.extend(rows)
                if (i + 1) % 10 == 0:
                    print(f"  进度 {i + 1}/{len(seeds)}")

    os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
    path = os.path.join(HERE, "out", "correlated_storage.csv")
    with open(path, "w", newline="", encoding="utf-8-sig") as fp:
        w = csv.DictWriter(fp, fieldnames=list(results[0].keys()))
        w.writeheader()
        w.writerows(results)

    by = {}
    for r in results:
        by.setdefault((r["theta"], r["variant"]), {})[r["seed"]] = r

    print(f"\n{'θ':>4} {'变体':<10}{'双命令总时s':>11}{'Δvs base%':>10}{'CI95':>16}"
          f"{'连段均时s':>10}{'出库均时s':>10}{'终局exp2s':>10}{'违规':>5}")
    for theta in THETAS:
        base = by[(theta, "base")]
        for variant in VARIANTS:
            cur = by[(theta, variant)]
            td = [cur[s]["tot_dual"] for s in seeds]
            tl = mean([cur[s]["t_link_avg"] for s in seeds])
            ar = mean([cur[s]["avg_retr"] for s in seeds])
            e2 = mean([cur[s]["exp2_final"] for s in seeds])
            vi = sum(cur[s]["viol"] for s in seeds)
            if variant == "base":
                print(f"{theta:>4} {variant:<10}{mean(td):>11.0f}{'—':>10}{'—':>16}"
                      f"{tl:>10.2f}{ar:>10.2f}{e2:>10.2f}{vi:>5}")
                continue
            tb = [base[s]["tot_dual"] for s in seeds]
            dm, (lo, hi), t, sig, _ = paired_t(td, tb)
            dpct = dm / mean(tb) * 100
            print(f"{theta:>4} {variant:<10}{mean(td):>11.0f}{dpct:>9.2f}%"
                  f"{f'[{lo:.0f},{hi:.0f}]{sig}':>16}"
                  f"{tl:>10.2f}{ar:>10.2f}{e2:>10.2f}{vi:>5}")
    print(f"\n输出:{path}(判读:Δ<0 且 CI 不含 0 = 显著改善;"
          f"link≈corr_link ⇒ 族先验无独立价值)")


if __name__ == "__main__":
    main()
