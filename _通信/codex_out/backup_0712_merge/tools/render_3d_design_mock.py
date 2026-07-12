# -*- coding: utf-8 -*-
"""3D 动画正式版 · 单帧设计图 v2(0706 二轮反馈:档 3 满配锚点,左右 3:7)。

设计原则(防返工,docs/3D动画设计_0706.md §1a):
- **档 3 满配版面**:泊松到达+装卸驻留+故障注入的全部信息元素都在版面上;
  档 2/1 同版面置灰降档(面板标"本档未建模"),版面零返工;
- 左:右 = 3:7;KPI 升级为品牌栏下横带 6 卡;左列三图=速度曲线(含驻留平台)/
  到达队列(泊松)/单件耗时分解(行程+装卸堆叠);
- 右侧 3D 增量:入口到达队列实体箱、报警格深红+浮标、历史路径残影、目标格高亮;
- 正式版动画=PyVista 渲 3D 视口(真 Z-buffer)+matplotlib 图表字幕,本设计图仍用
  matplotlib 单集合(静态视角够用)。
数值口径:布局=assignment CSV 真值;速度曲线=canonical A4/A4b 真参数;
档 3 队列/驻留/能耗数值=版面示意(正式版接帧事件流真数据,底部已标注)。
输出:sim/figs/design_3d_dashboard_tier3.png(1920×1080)
用法:python tools/render_3d_design_mock.py
"""
import csv
import math
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV = os.path.join(ROOT, "sim", "out", "assignment_awra.csv")
OUT = os.path.join(ROOT, "sim", "figs", "design_3d_dashboard_tier3.png")

N = 20
VX, VY, AX, AY = 2.0, 0.5, 0.5, 0.3          # canonical A4/A4b
T_DWELL = 4.0                                 # 装卸驻留示意(正式版取 G1 口径)
C_BG, C_PANEL, C_TXT = "#F2F2F2", "#FFFFFF", "#1A1A1A"
C_BRAND_BG, C_BRAND_RED = "#1A1A1A", "#FF000F"
C_G_HEAVY, C_G_MID, C_G_LIGHT = "#2E4A68", "#5B7A9D", "#A9C0D8"
C_SUG, C_PATH, C_ALARM = "#E7B800", "#3E7BD6", "#B71C1C"
C_FRAME, C_FLOOR, C_NAVY = "#8A8F98", "#E4E4E4", "#17365D"


def box_faces(x, z, y0=0.10, y1=0.90, shrink=0.12):
    s = shrink
    x0, x1, z0, z1 = x + s, x + 1 - s, z + s, z + 1 - s
    v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
         (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    return [[v[0], v[1], v[2], v[3]], [v[4], v[5], v[6], v[7]],
            [v[0], v[1], v[5], v[4]], [v[2], v[3], v[7], v[6]],
            [v[1], v[2], v[6], v[5]], [v[0], v[3], v[7], v[4]]]


def free_box_faces(xc, yc, zc, dx, dy, dz):
    """任意位置的盒面(排队箱/载货台用),中心 (xc,yc,zc),半尺寸 d*。"""
    x0, x1, y0, y1, z0, z1 = xc - dx, xc + dx, yc - dy, yc + dy, zc - dz, zc + dz
    v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
         (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    return [[v[0], v[1], v[2], v[3]], [v[4], v[5], v[6], v[7]],
            [v[0], v[1], v[5], v[4]], [v[2], v[3], v[7], v[6]],
            [v[1], v[2], v[6], v[5]], [v[0], v[3], v[7], v[4]]]


def trapezoid_profile(d, vmax, acc, t0=0.0, n=160):
    if d >= vmax * vmax / acc:
        t_a = vmax / acc
        T = d / vmax + vmax / acc
    else:
        t_a = math.sqrt(d / acc)
        T = 2.0 * t_a
        vmax = acc * t_a
    ts, vs = [], []
    for i in range(n + 1):
        t = T * i / n
        v = acc * t if t < t_a else (acc * (T - t) if t > T - t_a else vmax)
        ts.append(t0 + t); vs.append(v)
    return ts, vs, T


def main():
    goods = []
    with open(CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            goods.append(dict(name=row["name"], w=float(row["weight_kg"]),
                              col=int(row["col"]), tier=int(row["tier"]),
                              t1=float(row["travel_time_1way_s"])))
    goods = goods[:20]
    ws = sorted(g["w"] for g in goods)
    q1, q2 = ws[len(ws) // 3], ws[2 * len(ws) // 3]
    for g in goods:
        g["color"] = C_G_HEAVY if g["w"] > q2 else (C_G_MID if g["w"] > q1 else C_G_LIGHT)

    cur_i = 11                      # 档3定格:第 12 件在途,3 件排队,1 格报警
    placed = goods[:cur_i]
    cur = max(goods[cur_i:], key=lambda g: g["col"])   # 选长程件,水平梯形曲线完整可见
    p = 0.55
    cx, cz = cur["col"] * p, cur["tier"] * p
    t_placed = sum(g["t1"] for g in placed)
    alarm_cell = (17, 2)

    fig = plt.figure(figsize=(12.8, 7.2), dpi=150)
    fig.patch.set_facecolor(C_BG)

    # ---------- 品牌顶栏 ----------
    bar = fig.add_axes([0, 0.915, 1, 0.085]); bar.set_axis_off()
    bar.add_patch(plt.Rectangle((0, 0), 1, 1, transform=bar.transAxes,
                                color=C_BRAND_BG, zorder=0))
    bar.add_patch(plt.Rectangle((0, 0), 1, 0.06, transform=bar.transAxes,
                                color=C_BRAND_RED, zorder=1))
    bar.text(0.012, 0.52, "ABB", color=C_BRAND_RED, fontsize=17, fontweight="bold",
             va="center", transform=bar.transAxes)
    bar.text(0.062, 0.52, "智储优控 · 3D 数字孪生回放", color="#FFFFFF",
             fontsize=14, fontweight="bold", va="center", transform=bar.transAxes)
    bar.text(0.988, 0.52, "拟真档 3/3 · 泊松到达+装卸驻留+故障注入   |   2026-07-06 14:32:05   |   SIM",
             color="#B7BCC4", fontsize=9, va="center", ha="right", transform=bar.transAxes)

    # ---------- KPI 横带(6 卡;ISA:仅异常着色) ----------
    rib = fig.add_axes([0, 0.828, 1, 0.082]); rib.set_axis_off()
    kpis = [("已入库", f"{cur_i}/20 件", C_TXT), ("到达排队", "3 件", C_TXT),
            ("累计行程", f"{t_placed:.1f} s", C_TXT), ("平均响应", "11.2 s", C_TXT),
            ("累计能耗", "0.42 kWh", C_TXT), ("活动报警", "1(未确认)", C_ALARM)]
    for i, (k, v, vc) in enumerate(kpis):
        x = 0.012 + i * 0.1645
        rib.add_patch(FancyBboxPatch((x, 0.10), 0.152, 0.80,
                      boxstyle="round,pad=0.008", fc=C_PANEL,
                      ec=C_ALARM if vc == C_ALARM else "#CCCCCC",
                      lw=1.4 if vc == C_ALARM else 0.8, transform=rib.transAxes))
        rib.text(x + 0.010, 0.62, k, fontsize=8, color="#666", transform=rib.transAxes)
        rib.text(x + 0.010, 0.24, v, fontsize=11, color=vc, fontweight="bold",
                 transform=rib.transAxes)

    # ---------- 左列 1:速度曲线(梯形+装卸驻留平台) ----------
    ax_v = fig.add_axes([0.048, 0.565, 0.235, 0.235])
    ax_v.set_facecolor(C_PANEL)
    tx, vx_, Tx = trapezoid_profile(cur["col"] * 1.0, VX, AX)
    ty, vy_, Ty = trapezoid_profile(cur["tier"] * 1.0, VY, AY)
    T_out = max(Tx, Ty)
    ax_v.plot(tx, vx_, color=C_NAVY, lw=1.6, label=f"水平 vmax={VX}")
    ax_v.fill_between(tx, vx_, color=C_NAVY, alpha=0.10)
    ax_v.plot(ty, vy_, color=C_G_MID, lw=1.6, ls="--", label=f"垂直 vmax={VY}")
    # 装卸驻留平台(v=0)+ 回程
    ax_v.plot([T_out, T_out + T_DWELL], [0, 0], color=C_SUG, lw=3.0,
              solid_capstyle="butt", label="装卸驻留(G1)")
    tb, vb, Tb = trapezoid_profile(cur["col"] * 1.0, VX, AX, t0=T_out + T_DWELL)
    ax_v.plot(tb, vb, color=C_NAVY, lw=1.2, alpha=0.45)
    t_cur = p * T_out
    ax_v.axvline(t_cur, color=C_SUG, lw=1.4)
    ax_v.set_title("堆垛机速度曲线:梯形加减速+装卸驻留(L1+G1)",
                   fontsize=8.5, color=C_TXT, pad=3)
    ax_v.set_ylabel("m/s", fontsize=7.5)
    ax_v.tick_params(labelsize=7)
    ax_v.grid(color="#E0E0E0", lw=0.5)
    ax_v.legend(fontsize=6.5, framealpha=0.9, loc="upper right")
    for s in ax_v.spines.values():
        s.set_color("#CCCCCC")

    # ---------- 左列 2:到达队列长度(泊松,档 3 专属) ----------
    ax_q = fig.add_axes([0.048, 0.300, 0.235, 0.205])
    ax_q.set_facecolor(C_PANEL)
    qt = [0, 8, 14, 22, 30, 41, 47, 55, 62, 70, 78, 85, 90]
    qn = [0, 1, 2, 1, 2, 3, 2, 3, 2, 3, 4, 3, 3]
    ax_q.step(qt, qn, where="post", color=C_NAVY, lw=1.6)
    ax_q.fill_between(qt, qn, step="post", color=C_NAVY, alpha=0.10)
    ax_q.axvline(90, color=C_SUG, lw=1.4)
    ax_q.set_title("入口到达队列长度(泊松到达 λ=G2)", fontsize=8.5, color=C_TXT, pad=3)
    ax_q.set_ylabel("件", fontsize=7.5)
    ax_q.set_ylim(0, 5); ax_q.tick_params(labelsize=7)
    ax_q.grid(color="#E0E0E0", lw=0.5)
    for s in ax_q.spines.values():
        s.set_color("#CCCCCC")

    # ---------- 左列 3:单件响应时间分解(行程+驻留堆叠;真行程值) ----------
    ax_b = fig.add_axes([0.048, 0.048, 0.235, 0.192])
    ax_b.set_facecolor(C_PANEL)
    show = goods[cur_i - 7:cur_i + 1]
    names = [g["name"][-2:] for g in show]
    trav = [g["t1"] for g in show]
    dwell = [T_DWELL] * len(show)
    cols = [g["color"] for g in show[:-1]] + [C_SUG]
    ax_b.bar(range(len(show)), trav, color=cols, width=0.62, label="行程")
    ax_b.bar(range(len(show)), dwell, bottom=trav, color="#C9CDD2",
             width=0.62, label="装卸")
    ax_b.set_xticks(range(len(show))); ax_b.set_xticklabels(names, fontsize=6.5)
    ax_b.set_title("单件响应时间分解 s(琥珀=在途)", fontsize=8.5, color=C_TXT, pad=3)
    ax_b.tick_params(labelsize=7)
    ax_b.legend(fontsize=6.5, ncol=2, framealpha=0.9)
    ax_b.grid(axis="y", color="#E0E0E0", lw=0.5)
    for s in ax_b.spines.values():
        s.set_color("#CCCCCC")

    # ---------- 右侧:全 3D 场景(档 3 满配) ----------
    ax3 = fig.add_axes([0.288, 0.012, 0.712, 0.800], projection="3d")
    ax3.set_facecolor(C_BG)
    ax3.set_xlim(-0.5, N + 0.5); ax3.set_ylim(-4, 5); ax3.set_zlim(0, N)
    ax3.set_box_aspect((N + 1, 9, N), zoom=1.30)
    ax3.view_init(elev=18, azim=-68)
    try:
        ax3.set_proj_type("persp", focal_length=0.35)
    except TypeError:
        pass
    ax3.set_axis_off()

    floor = [[(-1, -5, 0), (N + 1, -5, 0), (N + 1, 3, 0), (-1, 3, 0)]]
    ax3.add_collection3d(Poly3DCollection(floor, facecolors=C_FLOOR,
                                          edgecolors="none", zsort="min"))
    for x in range(0, N + 1, 4):
        ax3.plot([x, x], [-5, 3], [0, 0], color="#D2D2D2", lw=0.5)
    for y in (-4, -2, 0, 2):
        ax3.plot([-1, N + 1], [y, y], [0, 0], color="#D2D2D2", lw=0.5)
    for x in range(0, N + 1, 2):
        for y in (0.0, 1.0):
            ax3.plot([x, x], [y, y], [0, N], color=C_FRAME, lw=0.7, alpha=0.75)
    for z in range(0, N + 1, 4):
        for y in (0.0, 1.0):
            ax3.plot([0, N], [y, y], [z, z], color=C_FRAME, lw=0.5, alpha=0.6)

    faces, fcolors = [], []
    pre_rgba = (0.71, 0.73, 0.75, 0.60)
    for x in range(N):
        for z in range(N):
            if (x + z) % 3 == 0:
                for f in box_faces(x, z, shrink=0.14):
                    faces.append(f); fcolors.append(pre_rgba)
    for g in placed:
        for f in box_faces(g["col"], g["tier"], shrink=0.10):
            faces.append(f); fcolors.append(g["color"])
    for f in box_faces(*alarm_cell, shrink=0.08):          # 报警格(档3:故障注入)
        faces.append(f); fcolors.append(C_ALARM)
    for f in free_box_faces(cx + 0.5, -0.75, cz + 0.5, 0.42, 0.40, 0.42):  # 在途箱
        faces.append(f); fcolors.append(cur["color"])
    for i in range(3):                                      # 入口到达队列 3 箱
        for f in free_box_faces(0.5, -2.0 - i * 1.1, 0.42, 0.40, 0.42, 0.42):
            faces.append(f); fcolors.append((0.66, 0.77, 0.87, 1.0))
    ax3.add_collection3d(Poly3DCollection(faces, facecolors=fcolors,
                                          edgecolors="#00000044", linewidths=0.25,
                                          zsort="average"))

    tgt = Poly3DCollection(box_faces(cur["col"], cur["tier"], shrink=0.05),
                           facecolors=(0, 0, 0, 0), edgecolors=C_SUG, linewidths=1.6)
    ax3.add_collection3d(tgt)
    alm = Poly3DCollection(box_faces(*alarm_cell, shrink=0.06),      # 报警=深红+黑粗边(Q2)
                           facecolors=(0, 0, 0, 0), edgecolors="#000000", linewidths=1.8)
    ax3.add_collection3d(alm)

    # 历史路径残影(最近 3 件,淡化)+ 当前路径
    for g in placed[-3:]:
        ax3.plot([0.5, g["col"] + 0.5], [-0.75, -0.75], [0.5, g["tier"] + 0.5],
                 color=C_PATH, lw=0.9, ls="--", alpha=0.18)
    ax3.plot([0.5, cur["col"] + 0.5], [-0.75, -0.75], [0.5, cur["tier"] + 0.5],
             color=C_PATH, lw=1.6, ls="--", alpha=0.95)

    ax3.plot([-0.5, N + 0.5], [-0.75, -0.75], [0, 0], color="#333", lw=2.4)
    ax3.plot([cx + 0.5, cx + 0.5], [-0.75, -0.75], [0, N], color="#1A1A1A", lw=2.6)
    ax3.scatter([0.5], [-0.75], [0.15], marker="^", s=110, color=C_ALARM, depthshade=False)
    ax3.text(0.5, -0.75, -2.6, "入口/出口(0,0)", fontsize=8, ha="center", color="#555")
    ax3.text(1.6, -2.0, 1.6, "到达队列", fontsize=8, color="#456", ha="left")
    ax3.text(alarm_cell[0] + 0.5, 0, alarm_cell[1] + 2.2, "▲ 故障",
             fontsize=9, color=C_ALARM, ha="center", fontweight="bold")

    ax3.text2D(0.99, 0.015,
               "蓝系=货物重量三档 · 半透明灰=预占(133) · 琥珀=当前/目标 · 深红=报警 · 残影=历史路径",
               transform=ax3.transAxes, fontsize=7.5, color="#777", ha="right")

    fig.text(0.006, 0.006,
             "布局/行程=assignment_awra.csv 真值;速度曲线=canonical A4/A4b 真参数;档3队列/驻留/能耗=版面示意,正式版接帧事件流(tier1/2/3 同一 schema)"
             " | 档2/1=同版面置灰降档",
             fontsize=6.5, color="#999")
    fig.savefig(OUT, dpi=150, facecolor=C_BG)
    print(f"saved: {OUT}")


if __name__ == "__main__":
    main()
