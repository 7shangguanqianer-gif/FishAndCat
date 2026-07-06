# -*- coding: utf-8 -*-
"""3D 回放动画 · 10 秒小样(混合渲染管线 PoC,0706 档 3 满配设计)。

管线(docs/3D动画设计_0706.md §3§4):
- 右侧 3D 视口 = PyVista off-screen(VTK 硬件 Z-buffer,遮挡根治,任意运镜);
- 品牌栏/KPI 横带/左列图表/字幕 = matplotlib(中文零障碍),持久 fig 逐帧只改动态元素;
- PIL 逐帧合成 → imageio-ffmpeg 出 mp4。
内容(档 3 样式):1 件长程货完整周期(梯形加减速去程→装卸驻留→空载回程),
泊松到达 1 件入队,故障注入 1 格(深红+锥标),相机全程环绕;3× 倍速(字幕标注)。
运动学=canonical A4/A4b 真参数逐帧积分;布局/行程=assignment CSV 真值;
队列/能耗数值=小样示意(正式版接帧事件流)。
输出:sim/figs/anim3d_sample_10s.mp4(1280×720,15fps,~10s)
用法:python tools/anim3d_sample.py
"""
import csv
import math
import os

import imageio_ffmpeg
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pyvista as pv
from matplotlib.patches import FancyBboxPatch, Rectangle
from PIL import Image

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV = os.path.join(ROOT, "sim", "out", "assignment_awra.csv")
OUT = os.path.join(ROOT, "sim", "figs", "anim3d_sample_10s.mp4")

N = 20
VX, VY, AX, AY = 2.0, 0.5, 0.5, 0.3
T_DWELL = 4.0
FPS, W, H = 15, 1280, 720
PV_BOX = (368, 134, 912, 560)                 # 3D 视口在整幅中的像素区(l,t,w,h)
C_BG, C_PANEL, C_TXT = "#F2F2F2", "#FFFFFF", "#1A1A1A"
C_BRAND_BG, C_BRAND_RED = "#1A1A1A", "#FF000F"
C_G = {"heavy": "#2E4A68", "mid": "#5B7A9D", "light": "#A9C0D8"}
C_SUG, C_PATH, C_ALARM = "#E7B800", "#3E7BD6", "#B71C1C"
C_FRAME, C_FLOOR, C_NAVY = "#8A8F98", "#E4E4E4", "#17365D"
ALARM_CELL = (17, 2)


# ---------------- 运动学(A4/A4b 梯形,与 sim axis_time 同族) ----------------
def axis_T(d, vmax, acc):
    if d <= 0:
        return 0.0
    if d >= vmax * vmax / acc:
        return d / vmax + vmax / acc
    return 2.0 * math.sqrt(d / acc)


def axis_pos(t, d, vmax, acc):
    """t 时刻单轴位置(0→d),对称梯形/三角。"""
    if d <= 0:
        return 0.0
    T = axis_T(d, vmax, acc)
    t = min(max(t, 0.0), T)
    if d >= vmax * vmax / acc:
        ta = vmax / acc
        if t < ta:
            return 0.5 * acc * t * t
        if t <= T - ta:
            return 0.5 * acc * ta * ta + vmax * (t - ta)
        return d - 0.5 * acc * (T - t) ** 2
    ta = math.sqrt(d / acc)
    if t < ta:
        return 0.5 * acc * t * t
    return d - 0.5 * acc * (T - t) ** 2


def axis_v(t, d, vmax, acc):
    if d <= 0:
        return 0.0
    T = axis_T(d, vmax, acc)
    if t < 0 or t > T:
        return 0.0
    vpk = vmax if d >= vmax * vmax / acc else acc * math.sqrt(d / acc)
    ta = vpk / acc
    if t < ta:
        return acc * t
    if t <= T - ta:
        return vpk
    return acc * (T - t)


def make_box(x0, x1, y0, y1, z0, z1):
    return pv.Box(bounds=(x0, x1, y0, y1, z0, z1))


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
        g["cls"] = "heavy" if g["w"] > q2 else ("mid" if g["w"] > q1 else "light")
    placed = goods[:11]
    cur = max(goods[11:], key=lambda g: g["col"])
    DX, DZ = float(cur["col"]), float(cur["tier"])

    Tx, Tz = axis_T(DX, VX, AX), axis_T(DZ, VY, AY)
    T_OUT = max(Tx, Tz)
    T_PLACE = T_OUT + T_DWELL
    T_TOTAL = T_PLACE + T_OUT                 # 空载回程同参数
    T_ALARM = T_PLACE + 0.30 * T_OUT
    DUR = 10.0
    SPEED = T_TOTAL / (DUR - 0.3)             # 结尾定格 0.3s
    FRAMES = int(DUR * FPS)

    t_travel0 = sum(g["t1"] for g in placed)
    n_resp0 = t_travel0 + T_DWELL * len(placed)

    # ================= matplotlib 持久仪表层 =================
    fig = plt.figure(figsize=(12.8, 7.2), dpi=100)
    fig.patch.set_facecolor(C_BG)

    bar = fig.add_axes([0, 0.915, 1, 0.085]); bar.set_axis_off()
    bar.add_patch(plt.Rectangle((0, 0), 1, 1, transform=bar.transAxes, color=C_BRAND_BG))
    bar.add_patch(plt.Rectangle((0, 0), 1, 0.06, transform=bar.transAxes, color=C_BRAND_RED))
    bar.text(0.012, 0.52, "ABB", color=C_BRAND_RED, fontsize=17, fontweight="bold",
             va="center", transform=bar.transAxes)
    bar.text(0.062, 0.52, "智储优控 · 3D 数字孪生回放", color="#FFFFFF",
             fontsize=14, fontweight="bold", va="center", transform=bar.transAxes)
    bar.text(0.988, 0.52,
             f"拟真档 3/3 · 泊松到达+装卸驻留+故障注入   |   {SPEED:.1f}× 倍速   |   SIM",
             color="#B7BCC4", fontsize=9, va="center", ha="right", transform=bar.transAxes)

    rib = fig.add_axes([0, 0.828, 1, 0.082]); rib.set_axis_off()
    kpi_defs = ["已入库", "到达排队", "累计行程", "平均响应", "累计能耗", "活动报警"]
    kpi_vals, kpi_cards = [], []
    for i, k in enumerate(kpi_defs):
        x = 0.012 + i * 0.1645
        card = FancyBboxPatch((x, 0.10), 0.152, 0.80, boxstyle="round,pad=0.008",
                              fc=C_PANEL, ec="#CCCCCC", lw=0.8, transform=rib.transAxes)
        rib.add_patch(card); kpi_cards.append(card)
        rib.text(x + 0.010, 0.62, k, fontsize=8, color="#666", transform=rib.transAxes)
        kpi_vals.append(rib.text(x + 0.010, 0.24, "", fontsize=11, color=C_TXT,
                                 fontweight="bold", transform=rib.transAxes))

    # 左 1:速度曲线(全时间轴静态画好,游标动)
    ax_v = fig.add_axes([0.048, 0.565, 0.235, 0.235]); ax_v.set_facecolor(C_PANEL)
    ts = np.linspace(0, T_TOTAL, 480)
    vx = [axis_v(t, DX, VX, AX) if t <= T_OUT else axis_v(t - T_PLACE, DX, VX, AX)
          for t in ts]
    vz = [axis_v(t, DZ, VY, AY) if t <= T_OUT else axis_v(t - T_PLACE, DZ, VY, AY)
          for t in ts]
    ax_v.plot(ts, vx, color=C_NAVY, lw=1.6, label=f"水平 vmax={VX}")
    ax_v.plot(ts, vz, color=C_G["mid"], lw=1.6, ls="--", label=f"垂直 vmax={VY}")
    ax_v.plot([T_OUT, T_PLACE], [0, 0], color=C_SUG, lw=3.0,
              solid_capstyle="butt", label="装卸驻留(G1)")
    cur_v = ax_v.axvline(0, color=C_SUG, lw=1.4)
    ax_v.set_title("堆垛机速度曲线:梯形加减速+装卸驻留(L1+G1)", fontsize=8.5,
                   color=C_TXT, pad=3)
    ax_v.set_ylabel("m/s", fontsize=7.5); ax_v.tick_params(labelsize=7)
    ax_v.grid(color="#E0E0E0", lw=0.5)
    ax_v.legend(fontsize=6.5, framealpha=0.9, loc="upper right")
    for s in ax_v.spines.values():
        s.set_color("#CCCCCC")

    # 左 2:到达队列(阶梯,随时间揭示)
    ax_q = fig.add_axes([0.048, 0.300, 0.235, 0.205]); ax_q.set_facecolor(C_PANEL)
    ARRIVE_T = 0.32 * T_OUT                  # 小样:途中到达 1 件(泊松示意)
    q_t = [0, ARRIVE_T, T_TOTAL]
    q_n = [3, 4, 4]
    (q_line,) = ax_q.step([0], [3], where="post", color=C_NAVY, lw=1.6)
    cur_q = ax_q.axvline(0, color=C_SUG, lw=1.4)
    ax_q.set_xlim(0, T_TOTAL); ax_q.set_ylim(0, 6)
    ax_q.set_title("入口到达队列长度(泊松到达 λ=G2)", fontsize=8.5, color=C_TXT, pad=3)
    ax_q.set_ylabel("件", fontsize=7.5); ax_q.tick_params(labelsize=7)
    ax_q.grid(color="#E0E0E0", lw=0.5)
    for s in ax_q.spines.values():
        s.set_color("#CCCCCC")

    # 左 3:单件响应分解(在途件琥珀,入库时转类色+加装卸段)
    ax_b = fig.add_axes([0.048, 0.048, 0.235, 0.192]); ax_b.set_facecolor(C_PANEL)
    show = placed[-7:] + [cur]
    names = [g["name"][-2:] for g in show]
    trav = [g["t1"] for g in show[:-1]] + [T_OUT]
    bars = ax_b.bar(range(len(show)), trav,
                    color=[C_G[g["cls"]] for g in show[:-1]] + [C_SUG], width=0.62)
    dws = ax_b.bar(range(len(show)), [T_DWELL] * (len(show) - 1) + [0],
                   bottom=trav, color="#C9CDD2", width=0.62)
    ax_b.set_xticks(range(len(show))); ax_b.set_xticklabels(names, fontsize=6.5)
    ax_b.set_title("单件响应时间分解 s(行程+装卸)", fontsize=8.5, color=C_TXT, pad=3)
    ax_b.tick_params(labelsize=7)
    ax_b.grid(axis="y", color="#E0E0E0", lw=0.5)
    for s in ax_b.spines.values():
        s.set_color("#CCCCCC")

    fig.text(0.006, 0.006,
             "10s 小样 · 混合渲染 PoC:3D=PyVista(真深度缓冲) 图表=matplotlib | 运动学/布局/行程=真值,队列/能耗=示意",
             fontsize=6.5, color="#999")
    leg = fig.text(0.995, 0.006,
                   "蓝系=货物重量三档 · 半透明灰=预占 · 琥珀=当前/目标 · 深红=报警",
                   fontsize=6.5, color="#777", ha="right")

    # ================= PyVista 3D 场景 =================
    pl = pv.Plotter(off_screen=True, window_size=(PV_BOX[2], PV_BOX[3]))
    pl.set_background(C_BG)
    try:
        pl.enable_anti_aliasing("msaa")
    except Exception:
        pass

    pl.add_mesh(make_box(-1, N + 3, -5, 3, -0.06, 0.0), color=C_FLOOR)      # 地面
    frame_parts = []
    for x in range(0, N + 1, 2):
        for y in (0.0, 1.0):
            frame_parts.append(make_box(x - 0.035, x + 0.035, y - 0.02, y + 0.02, 0, N))
    for z in range(0, N + 1, 4):
        for y in (0.0, 1.0):
            frame_parts.append(make_box(0, N, y - 0.02, y + 0.02, z - 0.035, z + 0.035))
    pl.add_mesh(pv.merge(frame_parts), color=C_FRAME)
    pl.add_mesh(make_box(-0.5, N + 0.5, -0.82, -0.68, -0.02, 0.06), color="#333333")  # 地轨

    pre = [make_box(x + 0.14, x + 0.86, 0.14, 0.86, z + 0.14, z + 0.86)
           for x in range(N) for z in range(N) if (x + z) % 3 == 0]
    pl.add_mesh(pv.merge(pre), color="#B5B9BD", opacity=0.55)
    try:
        pl.enable_depth_peeling()
    except Exception:
        pass

    for cls in ("light", "mid", "heavy"):
        ms = [make_box(g["col"] + 0.10, g["col"] + 0.90, 0.10, 0.90,
                       g["tier"] + 0.10, g["tier"] + 0.90)
              for g in placed if g["cls"] == cls]
        if ms:
            pl.add_mesh(pv.merge(ms), color=C_G[cls])

    mast = pl.add_mesh(make_box(-0.07, 0.07, -0.81, -0.69, 0.0, N), color="#1A1A1A")
    carriage = pl.add_mesh(make_box(-0.34, 0.34, -1.10, -0.42, -0.30, 0.30),
                           color="#3A3F45")
    carry = pl.add_mesh(make_box(-0.26, 0.26, -1.02, -0.50, -0.22, 0.22),
                        color=C_G[cur["cls"]])
    placed_new = pl.add_mesh(make_box(cur["col"] + 0.10, cur["col"] + 0.90, 0.10, 0.90,
                                      cur["tier"] + 0.10, cur["tier"] + 0.90),
                             color=C_G[cur["cls"]])
    tgt_wire = pl.add_mesh(make_box(cur["col"] + 0.04, cur["col"] + 0.96, 0.04, 0.96,
                                    cur["tier"] + 0.04, cur["tier"] + 0.96),
                           color=C_SUG, style="wireframe", line_width=3)
    path = pl.add_mesh(pv.Line((0.5, -0.75, 0.5),
                               (cur["col"] + 0.5, -0.75, cur["tier"] + 0.5)),
                       color=C_PATH, line_width=3)
    alarm_box = pl.add_mesh(make_box(ALARM_CELL[0] + 0.08, ALARM_CELL[0] + 0.92, 0.08,
                                     0.92, ALARM_CELL[1] + 0.08, ALARM_CELL[1] + 0.92),
                            color=C_ALARM)
    alarm_cone = pl.add_mesh(pv.Cone(center=(ALARM_CELL[0] + 0.5, 0.5, ALARM_CELL[1] + 1.7),
                                     direction=(0, 0, -1), height=0.7, radius=0.30),
                             color=C_ALARM)
    q_boxes = [pl.add_mesh(make_box(0.10, 0.90, -2.4 - i * 1.1, -1.6 - i * 1.1,
                                    0.0, 0.80), color="#A9C4DE") for i in range(5)]
    pl.add_mesh(pv.Cone(center=(0.5, -0.75, 0.35), direction=(0, 0, 1),
                        height=0.5, radius=0.22), color=C_ALARM)          # 入口标

    FOCAL = (N / 2, 0.5, 8.3)
    EL = math.radians(18)

    def set_cam(frac):
        az = math.radians(-68 + 14 * frac)
        R = 42.0                              # 半视场 42·tan16°≈12.0,货架 0..20 全入框
        pos = (FOCAL[0] + R * math.cos(EL) * math.cos(az),
               FOCAL[1] + R * math.cos(EL) * math.sin(az),
               FOCAL[2] + R * math.sin(EL))
        pl.camera_position = [pos, FOCAL, (0, 0, 1)]
        pl.camera.view_angle = 32.0           # 显式定视角(zoom() 会跨帧累积,禁用)

    # ================= 帧循环+合成 =================
    gen = imageio_ffmpeg.write_frames(OUT, size=(W, H), fps=FPS, quality=8)
    gen.send(None)
    for i in range(FRAMES):
        t = min(i / FPS * SPEED, T_TOTAL)
        # ---- 状态机 ----
        if t <= T_OUT:
            cx, cz = axis_pos(t, DX, VX, AX), axis_pos(t, DZ, VY, AY)
            phase = "out"
        elif t <= T_PLACE:
            cx, cz, phase = DX, DZ, "dwell"
        else:
            tb = t - T_PLACE
            cx, cz = DX - axis_pos(tb, DX, VX, AX), DZ - axis_pos(tb, DZ, VY, AY)
            phase = "back"
        T_XFER = T_OUT + 0.5 * T_DWELL        # 驻留中点=货箱交接入格
        placed_flag = t >= T_XFER
        alarm_flag = t >= T_ALARM
        qn = 4 if t >= ARRIVE_T else 3

        # ---- matplotlib 动态层 ----
        cur_v.set_xdata([t, t]); cur_q.set_xdata([t, t])
        xs = [0.0] + ([ARRIVE_T] if ARRIVE_T <= t else []) + [t]
        ys = [4 if x >= ARRIVE_T else 3 for x in xs]
        q_line.set_data(xs, ys)
        if placed_flag:
            bars[-1].set_color(C_G[cur["cls"]]); dws[-1].set_height(T_DWELL)
        n_in = len(placed) + (1 if placed_flag else 0)
        t_tr = t_travel0 + (T_OUT if placed_flag else 0)
        n_resp = n_resp0 + (T_OUT + T_DWELL if placed_flag else 0)
        vals = [f"{n_in}/20 件", f"{qn} 件", f"{t_tr:.1f} s",
                f"{n_resp/n_in:.1f} s", "0.45 kWh" if placed_flag else "0.42 kWh",
                "1(未确认)" if alarm_flag else "0"]
        for txt, v in zip(kpi_vals, vals):
            txt.set_text(v)
        kpi_vals[-1].set_color(C_ALARM if alarm_flag else C_TXT)
        kpi_cards[-1].set_edgecolor(C_ALARM if alarm_flag else "#CCCCCC")
        kpi_cards[-1].set_linewidth(1.4 if alarm_flag else 0.8)
        fig.canvas.draw()
        base = Image.fromarray(np.asarray(fig.canvas.buffer_rgba())).convert("RGB")

        # ---- PyVista 动态层 ----
        mast.SetPosition(cx + 0.5, 0, 0)
        carriage.SetPosition(cx + 0.5, 0, cz + 0.5)
        carry.SetPosition(cx + 0.5, 0, cz + 0.5)
        carry.SetVisibility(t < T_XFER)
        placed_new.SetVisibility(placed_flag)
        tgt_wire.SetVisibility(not placed_flag)
        path.SetVisibility(phase != "back")
        alarm_box.SetVisibility(alarm_flag)
        alarm_cone.SetVisibility(alarm_flag)
        for k, qb in enumerate(q_boxes):
            qb.SetVisibility(k < qn)
        set_cam(i / max(1, FRAMES - 1))
        pl.render()                            # off-screen 必须显式重渲,否则冻帧
        img3d = pl.screenshot(return_img=True)
        base.paste(Image.fromarray(img3d), (PV_BOX[0], PV_BOX[1]))

        gen.send(np.asarray(base).tobytes())
        if i % 30 == 0:
            print(f"frame {i}/{FRAMES} t={t:.1f}s phase={phase}")
    gen.close()
    plt.close(fig); pl.close()
    print(f"saved: {OUT}")


if __name__ == "__main__":
    main()
