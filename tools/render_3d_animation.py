# -*- coding: utf-8 -*-
"""3D 回放动画小样(Q4 终拍:Python 升级版动画,30 秒验货版)。

内容:演示批 20 件货按 AWRA 布局逐件入库——
- 堆垛机 = 立柱+载货台,**切比雪夫双轴同动**(水平/垂直同时走,与主口径运动模型一致)
- 当前行程画路径轨迹线;货箱按重量三分位着色(与静态图/AB 画面同族)
- 相机全程缓慢环绕;左上角 KPI 字幕实时更新(件数/累计行程时间/当前货物)
输出:sim/figs/preview_3d_anim_sample.mp4(15fps,约 30s)
依赖:matplotlib + imageio-ffmpeg(提供 ffmpeg 二进制);确定性渲染,无随机。
用法:python tools/render_3d_animation.py
"""
import csv
import os

import matplotlib
matplotlib.use("Agg")
import imageio_ffmpeg
import matplotlib.pyplot as plt
from matplotlib.animation import FFMpegWriter
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["animation.ffmpeg_path"] = imageio_ffmpeg.get_ffmpeg_exe()

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV = os.path.join(ROOT, "sim", "out", "assignment_awra.csv")
OUT = os.path.join(ROOT, "sim", "figs", "preview_3d_anim_sample.mp4")

N = 20
N_DEMO = 20          # 演示批 20 件(与 AB 画面 DEMO_LOADED_N 一致)
FPS = 15
C_PRE, C_HEAVY, C_MID, C_LIGHT = "#4a4a4a", "#B71C1C", "#E8A13A", "#7FA8C9"
C_CRANE, C_PATH, C_FRAME = "#1A1A1A", "#3E7BD6", "#222222"


def box_faces(x, z, shrink=0.12, depth=1.0):
    s = shrink
    x0, x1, y0, y1, z0, z1 = x + s, x + 1 - s, s, depth - s, z + s, z + 1 - s
    v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
         (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    return [[v[0], v[1], v[2], v[3]], [v[4], v[5], v[6], v[7]],
            [v[0], v[1], v[5], v[4]], [v[2], v[3], v[7], v[6]],
            [v[1], v[2], v[6], v[5]], [v[0], v[3], v[7], v[4]]]


def main():
    goods = []
    with open(CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            goods.append(dict(name=row["name"], w=float(row["weight_kg"]),
                              col=int(row["col"]), tier=int(row["tier"]),
                              t1=float(row["travel_time_1way_s"])))
    goods = goods[:N_DEMO]
    ws = sorted(g["w"] for g in goods)
    q1, q2 = ws[len(ws) // 3], ws[2 * len(ws) // 3]
    for g in goods:
        g["color"] = C_HEAVY if g["w"] > q2 else (C_MID if g["w"] > q1 else C_LIGHT)

    # ---- 时间轴:每件货=去程(载货)+回程(空载,1.6x 速),帧数正比切比雪夫距离 ----
    segs = []                 # (good, phase, n_frames) phase: 0=去 1=回
    for g in goods:
        cheb = max(g["col"], g["tier"])
        out_f = max(6, int(round(cheb * 0.9)))
        back_f = max(4, int(round(cheb * 0.55)))
        segs.append((g, 0, out_f))
        segs.append((g, 1, back_f))
    total = sum(s[2] for s in segs) + FPS  # 结尾定格 1 秒
    print(f"frames={total} (~{total/FPS:.0f}s)")

    fig = plt.figure(figsize=(12.8, 7.2), dpi=100)
    ax = fig.add_subplot(111, projection="3d")

    pre_faces = [f for x in range(N) for z in range(N)
                 if (x + z) % 3 == 0 for f in box_faces(x, z)]

    # 帧序列展开:每帧=(good_idx, phase, 0..1 进度)
    frames = []
    for gi, (g, ph, nf) in enumerate(segs):
        for k in range(nf):
            frames.append((g, ph, (k + 1) / nf))
    frames += [None] * FPS   # 定格

    placed, t_acc = [], [0.0]

    def render(frame):
        ax.clear()
        ax.set_axis_off()
        ax.set_xlim(0, N); ax.set_ylim(-3, 9); ax.set_zlim(0, N)
        ax.set_box_aspect((N, 12, N))
        try:
            ax.set_proj_type("persp", focal_length=0.28)
        except TypeError:
            pass
        idx = render.i
        render.i += 1
        ax.view_init(elev=22, azim=-86 + 32 * idx / total)   # 相机环绕

        for x in range(0, N + 1, 2):
            ax.plot([x, x], [0, 0], [0, N], color=C_FRAME, lw=0.5, alpha=0.5)
        for z in range(0, N + 1, 2):
            ax.plot([0, N], [0, 0], [z, z], color=C_FRAME, lw=0.5, alpha=0.5)
        ax.add_collection3d(Poly3DCollection(
            pre_faces, facecolors=C_PRE, edgecolors="#00000033", linewidths=0.2, alpha=0.9))

        for color in (C_LIGHT, C_MID, C_HEAVY):    # 已入库(每色一集合,提速)
            fs = [f for g in placed if g["color"] == color
                  for f in box_faces(g["col"], g["tier"])]
            if fs:
                ax.add_collection3d(Poly3DCollection(
                    fs, facecolors=color, edgecolors="#00000055", linewidths=0.3))

        status = "演示完成:20/20 件入库"
        if frame is not None:
            g, ph, p = frame
            # 切比雪夫双轴同动:两轴同时按各自比例推进
            if ph == 0:
                cx, cz = g["col"] * p, g["tier"] * p
            else:
                cx, cz = g["col"] * (1 - p), g["tier"] * (1 - p)
                if p >= 1 and g not in placed:
                    pass
            if ph == 0 and p >= 1:                 # 到位:落箱
                placed.append(g); t_acc[0] += g["t1"]
            # 路径轨迹(去程画满,回程淡化)
            ax.plot([0.5, g["col"] + 0.5], [0.5, 0.5], [0.5, g["tier"] + 0.5],
                    color=C_PATH, lw=1.6, alpha=0.9 if ph == 0 else 0.3, linestyle="--")
            # 堆垛机:立柱+载货台(载货=带货箱色,空载=黑)
            ax.plot([cx + 0.5, cx + 0.5], [0.5, 0.5], [0, N],
                    color=C_CRANE, lw=2.2, alpha=0.85)
            car = box_faces(cx, cz, shrink=0.06)
            ax.add_collection3d(Poly3DCollection(
                car, facecolors=g["color"] if ph == 0 else "#333333",
                edgecolors="#000", linewidths=0.6))
            status = (f"当前:{g['name']}({g['w']:.1f} kg)→ 库位({g['col']},{g['tier']})"
                      f"  {'载货去程' if ph == 0 else '空载回程'}")

        ax.text2D(0.02, 0.97, "智储优控 · 3D 回放(AWRA-LS · 主口径 H · 切比雪夫双轴同动)",
                  transform=ax.transAxes, fontsize=12, fontweight="bold", va="top")
        ax.text2D(0.02, 0.92,
                  f"已入库 {len(placed)}/{N_DEMO} 件   累计行程 {t_acc[0]:.1f} s   {status}",
                  transform=ax.transAxes, fontsize=10, va="top", color="#333")
        ax.text2D(0.02, 0.03, "数据源:sim/out/assignment_awra.csv(与 AB 画面同一份数据)",
                  transform=ax.transAxes, fontsize=8, va="bottom", color="#777")
        ax.scatter([0.5], [0.5], [-0.6], marker="^", s=120, color=C_HEAVY, depthshade=False)

    render.i = 0
    writer = FFMpegWriter(fps=FPS, bitrate=2400)
    with writer.saving(fig, OUT, dpi=100):
        for fr in frames:
            render(fr)
            writer.grab_frame()
    print(f"saved: {OUT}")


if __name__ == "__main__":
    main()
