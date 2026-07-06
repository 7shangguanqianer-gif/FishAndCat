# -*- coding: utf-8 -*-
"""3D 动画正式版 · 单帧设计图(0706 用户反馈后的改版方案,先看图再做视频)。

改版四要点(对应用户反馈):
1. 构图=左图表右 3D(dashboard 式):左列 速度曲线+单件耗时+KPI 卡,右侧 3D 场景;
2. 风格与 v3 设计稿统一:黑底红字品牌顶栏 + ISA-101 灰工作区;红色只留报警(货物改蓝系渐变);
3. 场景全 3D 化(修"2D 背景+3D 盒子"突兀):地面平面+货架立柱横梁+堆垛机地轨,盒子不再悬浮;
4. 遮挡修复:全部盒子并入单一 Poly3DCollection(逐面 zsort),不再按集合静态排序。
数据全真:布局=sim/out/assignment_awra.csv;速度曲线=canonical A4/A4b 参数(VX2.0/VY0.5,AX0.5/AY0.3)。
输出:sim/figs/design_3d_dashboard_tier2.png(1920×1080)
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
OUT = os.path.join(ROOT, "sim", "figs", "design_3d_dashboard_tier2.png")

N = 20
VX, VY, AX, AY = 2.0, 0.5, 0.5, 0.3          # canonical A4/A4b
# v3 统一色板:红只留报警;货物=蓝系三档;推荐/当前=琥珀
C_BG, C_PANEL, C_TXT = "#F2F2F2", "#FFFFFF", "#1A1A1A"
C_BRAND_BG, C_BRAND_RED = "#1A1A1A", "#FF000F"
C_PRE = "#B4B9BE"
C_G_HEAVY, C_G_MID, C_G_LIGHT = "#2E4A68", "#5B7A9D", "#A9C0D8"
C_SUG, C_PATH, C_ALARM = "#E7B800", "#3E7BD6", "#B71C1C"
C_FRAME, C_FLOOR = "#8A8F98", "#E4E4E4"


def box_faces(x, z, y0=0.10, y1=0.90, shrink=0.12):
    s = shrink
    x0, x1, z0, z1 = x + s, x + 1 - s, z + s, z + 1 - s
    v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
         (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    return [[v[0], v[1], v[2], v[3]], [v[4], v[5], v[6], v[7]],
            [v[0], v[1], v[5], v[4]], [v[2], v[3], v[7], v[6]],
            [v[1], v[2], v[6], v[5]], [v[0], v[3], v[7], v[4]]]


def trapezoid_profile(d, vmax, acc, n=240):
    """返回 (t数组, v数组):静止起止对称梯形/三角速度曲线,总时长同 sim axis_time。"""
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
        if t < t_a:
            v = acc * t
        elif t > T - t_a:
            v = acc * (T - t)
        else:
            v = vmax
        ts.append(t); vs.append(v)
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

    cur_i = 7                       # 定格时刻:第 8 件在途
    placed, cur = goods[:cur_i], goods[cur_i]
    p = 0.55                        # 当前行程进度(位置比例)
    cx, cz = cur["col"] * p, cur["tier"] * p
    t_placed = sum(g["t1"] for g in placed)

    fig = plt.figure(figsize=(12.8, 7.2), dpi=150)
    fig.patch.set_facecolor(C_BG)

    # ---------- 品牌顶栏(与 v3 设计稿页眉同构) ----------
    bar = fig.add_axes([0, 0.915, 1, 0.085]); bar.set_axis_off()
    bar.set_facecolor(C_BRAND_BG)
    bar.add_patch(plt.Rectangle((0, 0), 1, 1, transform=bar.transAxes,
                                color=C_BRAND_BG, zorder=0))
    bar.add_patch(plt.Rectangle((0, 0), 1, 0.06, transform=bar.transAxes,
                                color=C_BRAND_RED, zorder=1))
    bar.text(0.012, 0.52, "ABB", color=C_BRAND_RED, fontsize=17, fontweight="bold",
             va="center", transform=bar.transAxes)
    bar.text(0.062, 0.52, "智储优控 · 3D 数字孪生回放", color="#FFFFFF",
             fontsize=14, fontweight="bold", va="center", transform=bar.transAxes)
    bar.text(0.988, 0.52, "拟真档 2/3 · 梯形加减速+存取混合   |   2026-07-06 14:32:05   |   SIM",
             color="#B7BCC4", fontsize=9, va="center", ha="right", transform=bar.transAxes)

    # ---------- 左列 1:速度曲线(档 2 的特色主图) ----------
    ax_v = fig.add_axes([0.050, 0.575, 0.285, 0.285])
    ax_v.set_facecolor(C_PANEL)
    tx, vx_, Tx = trapezoid_profile(cur["col"] * 1.0, VX, AX)
    ty, vy_, Ty = trapezoid_profile(cur["tier"] * 1.0, VY, AY)
    ax_v.plot(tx, vx_, color="#17365D", lw=1.8, label=f"水平轴 vmax={VX}m/s")
    ax_v.fill_between(tx, vx_, color="#17365D", alpha=0.10)
    ax_v.plot(ty, vy_, color="#5B7A9D", lw=1.8, ls="--", label=f"垂直轴 vmax={VY}m/s")
    t_cur = p * max(Tx, Ty)
    ax_v.axvline(t_cur, color=C_SUG, lw=1.6)
    ax_v.text(t_cur + 0.15, VX * 0.93, "当前", color="#8B6914", fontsize=8)
    ax_v.set_title("堆垛机速度曲线(L1 梯形加减速 · 双轴同动)", fontsize=9.5, color=C_TXT, pad=4)
    ax_v.set_xlabel("时间 s", fontsize=8); ax_v.set_ylabel("速度 m/s", fontsize=8)
    ax_v.tick_params(labelsize=7.5)
    ax_v.grid(color="#E0E0E0", lw=0.5)
    ax_v.legend(fontsize=7.5, framealpha=0.9)
    for s in ax_v.spines.values():
        s.set_color("#CCCCCC")

    # ---------- 左列 2:单件入库行程时间(真数据) ----------
    ax_b = fig.add_axes([0.050, 0.205, 0.285, 0.285])
    ax_b.set_facecolor(C_PANEL)
    names = [g["name"][-2:] for g in goods[:cur_i + 1]]
    times = [g["t1"] for g in goods[:cur_i + 1]]
    colors = [g["color"] for g in goods[:cur_i]] + [C_SUG]
    ax_b.bar(range(len(times)), times, color=colors, width=0.62)
    avg = sum(times[:-1]) / max(1, len(times) - 1)
    ax_b.axhline(avg, color="#888", lw=1.0, ls=":")
    ax_b.text(0.02, avg + 0.35, f"已入库均值 {avg:.1f}s", fontsize=7.5, color="#666")
    ax_b.set_xticks(range(len(times))); ax_b.set_xticklabels(names, fontsize=7)
    ax_b.set_title("单件入库行程时间 s(琥珀=当前 G008 在途)", fontsize=9.5, color=C_TXT, pad=4)
    ax_b.tick_params(labelsize=7.5)
    ax_b.grid(axis="y", color="#E0E0E0", lw=0.5)
    for s in ax_b.spines.values():
        s.set_color("#CCCCCC")

    # ---------- 左列 3:KPI 卡(ISA:正常不着色) ----------
    ax_k = fig.add_axes([0.050, 0.045, 0.285, 0.115]); ax_k.set_axis_off()
    kpis = [("已入库", f"{len(placed)}/20 件"), ("累计行程", f"{t_placed:.1f} s"),
            ("平均单件", f"{t_placed/len(placed):.1f} s")]
    for i, (k, v) in enumerate(kpis):
        x = i * 0.345
        ax_k.add_patch(FancyBboxPatch((x, 0.06), 0.315, 0.88,
                       boxstyle="round,pad=0.012", fc=C_PANEL, ec="#CCCCCC",
                       transform=ax_k.transAxes))
        ax_k.text(x + 0.157, 0.68, k, fontsize=8.5, color="#666",
                  ha="center", transform=ax_k.transAxes)
        ax_k.text(x + 0.157, 0.30, v, fontsize=11.5, color=C_TXT, fontweight="bold",
                  ha="center", transform=ax_k.transAxes)

    # ---------- 右侧:全 3D 场景 ----------
    ax3 = fig.add_axes([0.345, 0.015, 0.655, 0.885], projection="3d")
    ax3.set_facecolor(C_BG)
    ax3.set_xlim(-0.5, N + 0.5); ax3.set_ylim(-4, 5); ax3.set_zlim(0, N)
    ax3.set_box_aspect((N + 1, 9, N), zoom=1.24)
    ax3.view_init(elev=18, azim=-68)
    try:
        ax3.set_proj_type("persp", focal_length=0.35)
    except TypeError:
        pass
    ax3.set_axis_off()

    # 地面平面 + 地面网格线(消"悬浮感")
    floor = [[(-1, -5, 0), (N + 1, -5, 0), (N + 1, 3, 0), (-1, 3, 0)]]
    ax3.add_collection3d(Poly3DCollection(floor, facecolors=C_FLOOR,
                                          edgecolors="none", zsort="min"))
    for x in range(0, N + 1, 4):
        ax3.plot([x, x], [-5, 3], [0, 0], color="#D2D2D2", lw=0.5)
    for y in (-4, -2, 0, 2):
        ax3.plot([-1, N + 1], [y, y], [0, 0], color="#D2D2D2", lw=0.5)

    # 货架立柱+横梁(前后两排,真 3D 框架)
    for x in range(0, N + 1, 2):
        for y in (0.0, 1.0):
            ax3.plot([x, x], [y, y], [0, N], color=C_FRAME, lw=0.7, alpha=0.75)
    for z in range(0, N + 1, 4):
        for y in (0.0, 1.0):
            ax3.plot([0, N], [y, y], [z, z], color=C_FRAME, lw=0.5, alpha=0.6)

    # 全部盒子并入单一集合(遮挡修复):预占+已入库+在途载货
    faces, fcolors = [], []
    pre_rgba = (0.71, 0.73, 0.75, 0.60)          # 预占=半透明"封格",非实体货箱
    for x in range(N):
        for z in range(N):
            if (x + z) % 3 == 0:
                for f in box_faces(x, z, shrink=0.14):
                    faces.append(f); fcolors.append(pre_rgba)
    for g in placed:
        for f in box_faces(g["col"], g["tier"], shrink=0.10):
            faces.append(f); fcolors.append(g["color"])
    # 在途货箱(在堆垛机载货台上,y 位于货架前方)
    for f in box_faces(cx, cz, y0=-1.15, y1=-0.35, shrink=0.10):
        faces.append(f); fcolors.append(cur["color"])
    ax3.add_collection3d(Poly3DCollection(faces, facecolors=fcolors,
                                          edgecolors="#00000044", linewidths=0.25,
                                          zsort="average"))

    # 目标格:琥珀线框高亮
    tgt = Poly3DCollection(box_faces(cur["col"], cur["tier"], shrink=0.06),
                           facecolors=(0, 0, 0, 0), edgecolors=C_SUG, linewidths=1.6)
    ax3.add_collection3d(tgt)

    # 堆垛机:地轨+立柱+路径
    ax3.plot([-0.5, N + 0.5], [-0.75, -0.75], [0, 0], color="#333", lw=2.4)   # 地轨
    ax3.plot([cx + 0.5, cx + 0.5], [-0.75, -0.75], [0, N], color="#1A1A1A", lw=2.6)  # 立柱
    ax3.plot([0.5, cur["col"] + 0.5], [-0.75, -0.75], [0.5, cur["tier"] + 0.5],
             color=C_PATH, lw=1.5, ls="--", alpha=0.9)                        # 当前路径
    ax3.scatter([0.5], [-0.75], [0.15], marker="^", s=110, color=C_ALARM, depthshade=False)
    ax3.text(0.5, -0.75, -2.3, "入口(0,0)", fontsize=8, ha="center", color="#555")

    ax3.text2D(0.985, 0.02,
               "库位色:蓝系=货物重量三档 · 灰=预占(133) · 琥珀=当前/推荐 · 深红=报警(档3 故障注入时出现)",
               transform=ax3.transAxes, fontsize=7.5, color="#777", ha="right")

    fig.text(0.006, 0.008,
             "数据源:sim/out/assignment_awra.csv + canonical A4/A4b 参数 | 三档动画共用本构图,徽章/图表内容随档位切换",
             fontsize=7, color="#999")
    fig.savefig(OUT, dpi=150, facecolor=C_BG)
    print(f"saved: {OUT}")


if __name__ == "__main__":
    main()
