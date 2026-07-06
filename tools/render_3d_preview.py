# -*- coding: utf-8 -*-
"""3D 等轴测预览渲染(方案 1 效果实证,0706 Q4 补拍用)。

用现有 assignment CSV(sim/out/assignment_awra.csv)出一帧 20×20 立体货架等轴测图:
- 预占格(官方口径 (x+y)%3==0)= 深灰实体
- 已放货格 = 按重量三分位着色(重=深红 / 中=琥珀 / 轻=浅蓝),与 AB 画面配色同族
- 空格 = 不画(只留货架线框),入口 (0,0) 三角标记
输出:sim/figs/preview_3d_awra.png(300dpi,可直接进报告/PPT)
依赖:仅 matplotlib(零新依赖);seed 无关(纯确定性重绘)。
用法:python tools/render_3d_preview.py
"""
import csv
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV = os.path.join(ROOT, "sim", "out", "assignment_awra.csv")
OUT = os.path.join(ROOT, "sim", "figs", "preview_3d_awra.png")

N = 20          # 20 列 × 20 层
DEPTH = 1.0     # 货格进深(视觉用)

C_PRE = "#4a4a4a"     # 预占=深灰
C_HEAVY = "#B71C1C"   # 重货=深红(与报警色同源但语义不同:此图为宣传渲染,非 HMI)
C_MID = "#E8A13A"     # 中货=琥珀
C_LIGHT = "#7FA8C9"   # 轻货=浅蓝
C_FRAME = "#222222"   # 货架线框


def cuboid(x, z, color, alpha=1.0, shrink=0.12):
    """在 (col=x, tier=z) 画一个货箱,y 方向为进深。"""
    s = shrink
    x0, x1 = x + s, x + 1 - s
    y0, y1 = s, DEPTH - s
    z0, z1 = z + s, z + 1 - s
    v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
         (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    faces = [[v[0], v[1], v[2], v[3]], [v[4], v[5], v[6], v[7]],
             [v[0], v[1], v[5], v[4]], [v[2], v[3], v[7], v[6]],
             [v[1], v[2], v[6], v[5]], [v[0], v[3], v[7], v[4]]]
    pc = Poly3DCollection(faces, facecolors=color, edgecolors="#00000055",
                          linewidths=0.3, alpha=alpha)
    return pc


def main():
    goods = []
    with open(CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            goods.append((int(row["col"]), int(row["tier"]), float(row["weight_kg"])))

    ws = sorted(w for _, _, w in goods)
    q1, q2 = ws[len(ws) // 3], ws[2 * len(ws) // 3]

    fig = plt.figure(figsize=(11, 8))
    ax = fig.add_subplot(111, projection="3d")

    # 货架线框(竖梁+横梁,稀疏画避免糊)
    for x in range(0, N + 1, 2):
        ax.plot([x, x], [0, 0], [0, N], color=C_FRAME, lw=0.5, alpha=0.5)
    for z in range(0, N + 1, 2):
        ax.plot([0, N], [0, 0], [z, z], color=C_FRAME, lw=0.5, alpha=0.5)

    # 预占格(官方口径 sum)
    for x in range(N):
        for z in range(N):
            if (x + z) % 3 == 0:
                ax.add_collection3d(cuboid(x, z, C_PRE, alpha=0.9))

    # 货物格
    for x, z, w in goods:
        c = C_HEAVY if w > q2 else (C_MID if w > q1 else C_LIGHT)
        ax.add_collection3d(cuboid(x, z, c))

    # 入口 (0,0) 标记
    ax.scatter([0.5], [0.5], [-0.8], marker="^", s=180, color=C_HEAVY, depthshade=False)
    ax.text(0.5, 0.5, -2.6, "入口(0,0)", fontsize=9, ha="center")

    ax.set_xlim(0, N); ax.set_ylim(-3, 9); ax.set_zlim(0, N)
    ax.set_box_aspect((N, 12, N))
    ax.view_init(elev=22, azim=-76)
    try:
        ax.set_proj_type("persp", focal_length=0.28)   # 透视投影,增强纵深
    except TypeError:
        pass
    ax.set_axis_off()
    ax.set_title("20×20 立体仓库 · AWRA-LS 布局(主口径 H)· 3D 等轴测预览", fontsize=12)

    # 图例
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(fc=C_HEAVY, label="重货(上三分位)"),
                       Patch(fc=C_MID, label="中货"),
                       Patch(fc=C_LIGHT, label="轻货(下三分位)"),
                       Patch(fc=C_PRE, label="预占格 (x+y)%3==0")],
              loc="upper right", fontsize=8, framealpha=0.9)

    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
    plt.rcParams["axes.unicode_minus"] = False
    fig.tight_layout()
    fig.savefig(OUT, dpi=300, bbox_inches="tight")
    print(f"saved: {OUT}")


if __name__ == "__main__":
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
    plt.rcParams["axes.unicode_minus"] = False
    main()
