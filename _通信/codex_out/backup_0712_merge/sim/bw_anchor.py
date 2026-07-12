# -*- coding: utf-8 -*-
"""
bw_anchor.py — T1.4 Bozer-White 复现锚专节数据(0706 枪E 调研定题)

目的:仿真器可信度外部锚。BW 1984 连续闭式(单程 E=T(1/2+b²/6),
E(TB)=T(1/3+b²/6−b³/30);Le-Duc 2005 教材级核对,Roodbergen&Vis 2009 交叉)
vs 我们的离散 20×20 精确期望——文献只有定性"离散连续差异小"(Lee et al. 1999)
**无具体数字**,本实验自产可复现数字,构成报告贡献点之一。

三个对照(每个都给偏差%):
  ① 纯离散化误差:全格(无预占)离散精确期望 vs BW 连续闭式,规格扫描
     10×10/20×20/40×40/80×80 展示收敛趋势(20×20 为主口径行);
  ② 我们场景口径:sum 预占(B1 官方)后可用位期望 vs BW 连续——总偏差
     =离散化+预占几何效应,报告分行归因;
  ③ 恒速 vs 梯形加减速(ACCEL 双口径)的离散期望差%,对照文献量级
     E(SC) 6-12%/E(DC) 10-16%(Oser & Drobir 2012,弯道式 AS/RS,量级参照)。

运行:python bw_anchor.py     输出:out/bw_anchor.csv + 控制台表
"""
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import warehouse_sim as ws

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")


def bw_continuous(cols, tiers):
    """BW 连续闭式(匀速):单程 E=T(1/2+b²/6),E(TB)=T(1/3+b²/6−b³/30)。"""
    t_x = (cols - 1) * ws.CELL_W / ws.VX
    t_y = (tiers - 1) * ws.CELL_H / ws.VY
    T = max(t_x, t_y)
    b = min(t_x, t_y) / T if T else 0.0
    return T * (0.5 + b * b / 6.0), T * (1.0 / 3.0 + b * b / 6.0 - b ** 3 / 30.0), b, T


def discrete_esc(slots):
    """离散精确单程期望:给定库位集上 travel_time 均值(随机存储=均匀)。"""
    return sum(ws.travel_time(c, t) for c, t in slots) / len(slots)


def discrete_etb(slots, cap=None):
    """离散精确两点间期望(全对;大规格用步长抽稀控制 O(n²))。"""
    n = len(slots)
    step = max(1, n // (cap or n))
    sub = slots[::step]
    m = len(sub)
    tot = 0.0
    for i in range(m):
        ci, ti = sub[i]
        for j in range(m):
            if i != j:
                tot += ws.travel_time_between(ci, ti, sub[j][0], sub[j][1])
    return tot / (m * (m - 1))


def main():
    rows = []
    print("① 纯离散化误差(全格,无预占;匀速口径)")
    print(f"{'规格':<9}{'b':>6}{'E单程:连续':>11}{'离散':>9}{'偏差%':>8}"
          f"{'E(TB):连续':>11}{'离散':>9}{'偏差%':>8}")
    print("-" * 74)
    base = (ws.COLS, ws.TIERS)
    for n in (10, 20, 40, 80):
        ws.COLS = ws.TIERS = n
        slots = [(c, t) for c in range(n) for t in range(n)]
        e_bw, etb_bw, b, T = bw_continuous(n, n)
        e_d = discrete_esc(slots)
        etb_d = discrete_etb(slots, cap=1600)          # ≥40×40 抽稀防 O(n⁴)
        dev_sc = (e_d - e_bw) / e_bw * 100
        dev_tb = (etb_d - etb_bw) / etb_bw * 100
        mark = " ←主口径" if n == 20 else ""
        print(f"{n}x{n:<6}{b:>6.2f}{e_bw:>11.3f}{e_d:>9.3f}{dev_sc:>7.2f}%"
              f"{etb_bw:>11.3f}{etb_d:>9.3f}{dev_tb:>7.2f}%{mark}")
        rows.append(dict(exp="grid_full", size=f"{n}x{n}", b=round(b, 3),
                         esc_bw=round(e_bw, 3), esc_disc=round(e_d, 3),
                         esc_dev_pct=round(dev_sc, 3),
                         etb_bw=round(etb_bw, 3), etb_disc=round(etb_d, 3),
                         etb_dev_pct=round(dev_tb, 3)))
    ws.COLS, ws.TIERS = base

    print("\n② 我们场景口径(20x20,sum 预占 133 格后 267 可用位)vs BW 连续")
    slots_sum = [(c, t) for c in range(ws.COLS) for t in range(ws.TIERS)
                 if not ws.preoccupied(c, t, "sum")]
    e_bw, etb_bw, b, T = bw_continuous(ws.COLS, ws.TIERS)
    e_d = discrete_esc(slots_sum)
    etb_d = discrete_etb(slots_sum)
    print(f"E单程:连续 {e_bw:.3f} vs 场景离散 {e_d:.3f} → 总偏差 "
          f"{(e_d - e_bw) / e_bw * 100:.2f}%(=离散化+预占几何效应)")
    print(f"E(TB) :连续 {etb_bw:.3f} vs 场景离散 {etb_d:.3f} → 总偏差 "
          f"{(etb_d - etb_bw) / etb_bw * 100:.2f}%")
    rows.append(dict(exp="scene_sum", size="20x20-267", b=round(b, 3),
                     esc_bw=round(e_bw, 3), esc_disc=round(e_d, 3),
                     esc_dev_pct=round((e_d - e_bw) / e_bw * 100, 3),
                     etb_bw=round(etb_bw, 3), etb_disc=round(etb_d, 3),
                     etb_dev_pct=round((etb_d - etb_bw) / etb_bw * 100, 3)))

    print("\n③ 恒速 vs 梯形加减速(离散全格+场景口径;文献量级参照 6-16%)")
    for label, slots in (("全格", [(c, t) for c in range(ws.COLS)
                                  for t in range(ws.TIERS)]),
                         ("sum预占后", slots_sum)):
        ws.ACCEL = False
        e0, etb0 = discrete_esc(slots), discrete_etb(slots)
        ws.ACCEL = True
        e1, etb1 = discrete_esc(slots), discrete_etb(slots)
        ws.ACCEL = False
        d_sc = (e1 - e0) / e0 * 100
        d_tb = (etb1 - etb0) / etb0 * 100
        print(f"{label}:E单程 匀速 {e0:.3f} → 梯形 {e1:.3f}(+{d_sc:.2f}%);"
              f"E(TB) {etb0:.3f} → {etb1:.3f}(+{d_tb:.2f}%)")
        rows.append(dict(exp="accel_" + ("full" if label == "全格" else "sum"),
                         size="20x20", b=round(b, 3),
                         esc_bw=round(e0, 3), esc_disc=round(e1, 3),
                         esc_dev_pct=round(d_sc, 3),
                         etb_bw=round(etb0, 3), etb_disc=round(etb1, 3),
                         etb_dev_pct=round(d_tb, 3)))

    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "bw_anchor.csv"), "w", newline="",
              encoding="utf-8-sig") as fp:
        w = csv.DictWriter(fp, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"\nCSV:{OUT}\\bw_anchor.csv({len(rows)} 行)")


if __name__ == "__main__":
    main()
