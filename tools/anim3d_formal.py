# -*- coding: utf-8 -*-
"""3D 回放动画 · 1 分钟正式版(0706;V2c 定稿场景+档 3 满配 dashboard+混合渲染)。

架构(防返工):渲染器消费**事件流**(events 列表:pick/place/arrive/fault,
含时刻与几何)——本版由 build_events() 内联生成(运动学=A4/A4b 真参数,
到达=固定 seed 泊松);档 3 完整版把 build_events 换成读 sim 导出 CSV,渲染器不改。
内容:11 件已入库续播,连续入库 9 件(G012-G020),泊松到达补队列,中途故障注入;
左列=当前行程速度曲线(每趟重绘)+到达队列+20 件响应分解;相机全程环绕。
输出:sim/figs/anim3d_formal_60s.mp4(1280×720,15fps,约 60s)
用法:python tools/anim3d_formal.py
"""
import csv
import math
import os
import random
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import imageio_ffmpeg
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pyvista as pv
from matplotlib.patches import FancyBboxPatch
from PIL import Image

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV = os.path.join(ROOT, "sim", "out", "assignment_awra.csv")
OUT = os.path.join(ROOT, "sim", "figs", "anim3d_formal_60s.mp4")

N = 20
VX, VY, AX, AY = 2.0, 0.5, 0.5, 0.3
T_DWELL = 4.0
FPS, W, H = 15, 1280, 720
PV_BOX = (368, 134, 912, 560)
DUR = 60.0
ALARM = (17, 2)
Z0 = -0.5

C = dict(bg="#F6F7F9", floor="#E4E6E9", seam="#D5D8DC", pad="#D8DBDF",
         body="#C9CFD6", inner="#AEB6BF", edge="#EDF1F5", plinth="#A7AFB8",
         cap="#B4BBC3", digit="#5F6870",
         heavy="#17365D", mid="#4A6FA5", light="#9DBBDD", lid="#122A47",
         alarm="#B71C1C", amber="#E7B800", path="#3E7BD6", rail="#7C838B",
         mast="#17365D", carriage="#4A6FA5",
         panel="#FFFFFF", txt="#1A1A1A", brand="#1A1A1A", brand_red="#FF000F",
         navy="#17365D")


# ---------------- 运动学(A4/A4b) ----------------
def axis_T(d, vmax, acc):
    if d <= 0:
        return 0.0
    if d >= vmax * vmax / acc:
        return d / vmax + vmax / acc
    return 2.0 * math.sqrt(d / acc)


def axis_pos(t, d, vmax, acc):
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


def load_goods():
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
    return goods


def build_events(goods):
    """事件流(档 3 完整版换成读 sim 导出,同结构):
    trips=[{good,t0,T_out,T_place,T_end}];arrivals=[t];fault_t。"""
    trips, t = [], 0.0
    for g in goods[11:20]:
        T_out = max(axis_T(g["col"], VX, AX), axis_T(g["tier"], VY, AY))
        trips.append(dict(g=g, t0=t, T_out=T_out, T_place=t + T_out + T_DWELL,
                          T_xfer=t + T_out + 0.5 * T_DWELL,
                          T_end=t + 2 * T_out + T_DWELL))
        t = trips[-1]["T_end"]
    T_sim = t
    rng = random.Random(42)                      # 固定 seed(工程纪律)
    # 到达均值 30s:单件服务≈27s → ρ≈0.9(稳定排队;16s 时 ρ=1.7 队列爆炸,0706 实测教训)
    arrivals, ta = [], 0.0
    while True:
        ta += rng.expovariate(1 / 30.0)
        if ta >= T_sim:
            break
        arrivals.append(ta)
    fault_t = trips[4]["T_place"] + 1.5          # 第 5 件入库后故障注入
    return trips, arrivals, fault_t, T_sim


def queue_at(t, trips, arrivals, q0=3):
    q = q0
    for a in arrivals:
        if a <= t:
            q += 1
    for tr in trips:
        if tr["t0"] <= t:
            q -= 1
    return max(q, 0)


def box(x0, x1, y0, y1, z0, z1):
    return pv.Box(bounds=(x0, x1, y0, y1, z0, z1))


def digit_mesh(s, height, center):
    m = pv.Text3D(s, depth=0.03)
    b = m.bounds
    h = b[3] - b[2] if (b[3] - b[2]) > 0 else 1.0
    m.scale(height / h, inplace=True)
    m.rotate_x(90, inplace=True)
    b = m.bounds
    m.translate((center[0] - (b[0] + b[1]) / 2, center[1] - b[2],
                 center[2] - (b[4] + b[5]) / 2), inplace=True)
    return m


def build_static_scene(pl, goods):
    """V2c 定稿柜体(tools/render_cabinet_final.py 同规格)+ 前 11 件货。"""
    pre = [(x, z) for x in range(N) for z in range(N) if (x + z) % 3 == 0]
    pl.add_light(pv.Light(position=(34, -30, 42), focal_point=(10, 0, 10),
                          intensity=0.35))
    pl.add_light(pv.Light(light_type="headlight", intensity=0.25))
    pl.add_mesh(box(-2, N + 4, -6, 3, Z0 - 0.08, Z0), color=C["floor"])
    seams = [pv.Line((x, -6, Z0 + 0.004), (x, 3, Z0 + 0.004))
             for x in range(-2, N + 5, 4)]
    seams += [pv.Line((-2, y, Z0 + 0.004), (N + 4, y, Z0 + 0.004))
              for y in range(-6, 4, 2)]
    pl.add_mesh(pv.merge(seams), color=C["seam"], line_width=1)
    pl.add_mesh(box(-0.2, 1.2, -2.6, -0.9, Z0, Z0 + 0.02), color=C["pad"])
    pl.add_mesh(box(-0.3, N + 0.3, -0.30, 1.10, Z0, 0.0), color=C["plinth"])
    pl.add_mesh(box(0, N, 0.95, 1.06, 0, N), color=C["body"])
    inner = [box(x + 0.05, x + 0.95, 0.925, 0.95, z + 0.05, z + 0.95)
             for x in range(N) for z in range(N)]
    pl.add_mesh(pv.merge(inner), color=C["inner"])
    shelves = [box(0, N, 0.0, 0.95, z - 0.030, z + 0.030) for z in range(N + 1)]
    parts = [box(x - 0.030, x + 0.030, 0.0, 0.95, 0, N) for x in range(N + 1)]
    pl.add_mesh(pv.merge(shelves + parts), color=C["body"])
    edges = ([box(0, N, -0.022, 0.042, z - 0.036, z + 0.036) for z in range(N + 1)]
             + [box(x - 0.036, x + 0.036, -0.022, 0.042, 0, N) for x in range(N + 1)])
    pl.add_mesh(pv.merge(edges), color=C["edge"])
    pl.add_mesh(box(-0.3, N + 0.3, -0.18, 1.10, N, N + 0.16), color=C["cap"])
    for n in range(0, N + 1, 5):
        pl.add_mesh(digit_mesh(str(n), 0.30, (n + 0.5 if n < N else n - 0.5,
                                              -0.305, -0.26)), color=C["digit"])
    covers = [box(x + 0.10, x + 0.90, -0.008, 0.05, z + 0.10, z + 0.90)
              for x, z in pre]
    pl.add_mesh(pv.merge(covers), color=C["body"])
    bodies = {"heavy": [], "mid": [], "light": []}
    lids = []
    for g in goods[:11]:
        x, z = g["col"], g["tier"]
        bodies[g["cls"]].append(box(x + 0.15, x + 0.85, 0.14, 0.86,
                                    z + 0.14, z + 0.72))
        lids.append(box(x + 0.13, x + 0.87, 0.12, 0.88, z + 0.72, z + 0.84))
    for cls in bodies:
        if bodies[cls]:
            pl.add_mesh(pv.merge(bodies[cls]), color=C[cls])
    pl.add_mesh(pv.merge(lids), color=C["lid"])
    pl.add_mesh(box(-0.5, N + 0.5, -0.82, -0.68, Z0, Z0 + 0.08), color=C["rail"])
    pl.add_mesh(pv.Cone(center=(0.5, -0.75, Z0 + 0.30), direction=(0, 0, 1),
                        height=0.5, radius=0.22), color=C["amber"])


def main():
    goods = load_goods()
    trips, arrivals, fault_t, T_sim = build_events(goods)
    SPEED = T_sim / (DUR - 1.5)
    FRAMES = int(DUR * FPS)
    print(f"T_sim={T_sim:.1f}s speed={SPEED:.2f}x frames={FRAMES}")

    base_travel = sum(g["t1"] for g in goods[:11])

    # ================= matplotlib 仪表层 =================
    fig = plt.figure(figsize=(12.8, 7.2), dpi=100)
    fig.patch.set_facecolor("#F2F2F2")
    bar = fig.add_axes([0, 0.915, 1, 0.085]); bar.set_axis_off()
    bar.add_patch(plt.Rectangle((0, 0), 1, 1, transform=bar.transAxes,
                                color=C["brand"]))
    bar.add_patch(plt.Rectangle((0, 0), 1, 0.06, transform=bar.transAxes,
                                color=C["brand_red"]))
    bar.text(0.012, 0.52, "ABB", color=C["brand_red"], fontsize=17,
             fontweight="bold", va="center", transform=bar.transAxes)
    bar.text(0.062, 0.52, "智储优控 · 3D 数字孪生回放", color="#FFFFFF",
             fontsize=14, fontweight="bold", va="center", transform=bar.transAxes)
    bar.text(0.988, 0.52,
             f"拟真档 3/3 · 泊松到达+装卸驻留+故障注入 | {SPEED:.1f}× 倍速 | SIM",
             color="#B7BCC4", fontsize=9, va="center", ha="right",
             transform=bar.transAxes)

    rib = fig.add_axes([0, 0.828, 1, 0.082]); rib.set_axis_off()
    kpi_defs = ["已入库", "到达排队", "累计行程", "平均响应", "累计能耗", "活动报警"]
    kpi_vals, kpi_cards = [], []
    for i, k in enumerate(kpi_defs):
        x = 0.012 + i * 0.1645
        card = FancyBboxPatch((x, 0.10), 0.152, 0.80, boxstyle="round,pad=0.008",
                              fc=C["panel"], ec="#CCCCCC", lw=0.8,
                              transform=rib.transAxes)
        rib.add_patch(card); kpi_cards.append(card)
        rib.text(x + 0.010, 0.62, k, fontsize=8, color="#666",
                 transform=rib.transAxes)
        kpi_vals.append(rib.text(x + 0.010, 0.24, "", fontsize=11, color=C["txt"],
                                 fontweight="bold", transform=rib.transAxes))

    ax_v = fig.add_axes([0.048, 0.565, 0.235, 0.235]); ax_v.set_facecolor(C["panel"])
    ax_q = fig.add_axes([0.048, 0.300, 0.235, 0.205]); ax_q.set_facecolor(C["panel"])
    ax_b = fig.add_axes([0.048, 0.048, 0.235, 0.192]); ax_b.set_facecolor(C["panel"])

    # 队列曲线(全时间轴预计算,游标揭示)
    ev_t = sorted([0.0] + arrivals + [tr["t0"] for tr in trips] + [T_sim])
    q_steps_t, q_steps_n = [], []
    for tt in ev_t:
        q_steps_t.append(tt); q_steps_n.append(queue_at(tt, trips, arrivals))
    (q_line,) = ax_q.step([0], [q_steps_n[0]], where="post", color=C["navy"], lw=1.6)
    cur_q = ax_q.axvline(0, color=C["amber"], lw=1.4)
    ax_q.set_xlim(0, T_sim); ax_q.set_ylim(0, max(q_steps_n) + 1.5)
    ax_q.set_title("入口到达队列长度(泊松到达 λ=G2)", fontsize=8.5,
                   color=C["txt"], pad=3)
    ax_q.set_ylabel("件", fontsize=7.5); ax_q.tick_params(labelsize=7)
    ax_q.grid(color="#E0E0E0", lw=0.5)
    for s in ax_q.spines.values():
        s.set_color("#CCCCCC")

    # 响应分解:20 槽位,前 11 件点亮,其余随入库点亮
    names = [g["name"][-2:] for g in goods]
    trav0 = [g["t1"] if i < 11 else 0 for i, g in enumerate(goods)]
    bars = ax_b.bar(range(20), trav0,
                    color=[C[g["cls"]] for g in goods], width=0.62)
    dws = ax_b.bar(range(20), [T_DWELL if i < 11 else 0 for i in range(20)],
                   bottom=trav0, color="#C9CDD2", width=0.62)
    ax_b.set_xticks(range(20)); ax_b.set_xticklabels(names, fontsize=5.5)
    ax_b.set_ylim(0, 22)
    ax_b.set_title("单件响应时间分解 s(行程+装卸;琥珀=在途)", fontsize=8.5,
                   color=C["txt"], pad=3)
    ax_b.tick_params(labelsize=7)
    ax_b.grid(axis="y", color="#E0E0E0", lw=0.5)
    for s in ax_b.spines.values():
        s.set_color("#CCCCCC")

    fig.text(0.006, 0.006,
             "运动学/布局/行程=canonical A4/A4b+assignment 真值 | 到达=固定seed泊松 | 能耗=示意 | 事件流驱动(档3完整版接sim导出)",
             fontsize=6.5, color="#999")
    fig.text(0.995, 0.006,
             "V2c 蓝灰工程柜 · 封板=预占(133) · 琥珀=当前/目标 · 深红=报警",
             fontsize=6.5, color="#777", ha="right")

    speed_artists = {"trip": None}

    def redraw_speed(tr):
        ax_v.clear(); ax_v.set_facecolor(C["panel"])
        g = tr["g"]
        dx, dz = float(g["col"]), float(g["tier"])
        T_out = tr["T_out"]
        ts = np.linspace(0, 2 * T_out + T_DWELL, 400)
        vx = [axis_v(t, dx, VX, AX) if t <= T_out
              else axis_v(t - T_out - T_DWELL, dx, VX, AX) for t in ts]
        vz = [axis_v(t, dz, VY, AY) if t <= T_out
              else axis_v(t - T_out - T_DWELL, dz, VY, AY) for t in ts]
        ax_v.plot(ts, vx, color=C["navy"], lw=1.6, label=f"水平 vmax={VX}")
        ax_v.plot(ts, vz, color=C["mid"], lw=1.6, ls="--", label=f"垂直 vmax={VY}")
        ax_v.plot([T_out, T_out + T_DWELL], [0, 0], color=C["amber"], lw=3.0,
                  solid_capstyle="butt", label="装卸驻留(G1)")
        ax_v.set_title(f"当前行程速度曲线:{g['name']} → 库位({g['col']},{g['tier']})",
                       fontsize=8.5, color=C["txt"], pad=3)
        ax_v.set_ylabel("m/s", fontsize=7.5); ax_v.tick_params(labelsize=7)
        ax_v.set_ylim(0, 2.3)
        ax_v.grid(color="#E0E0E0", lw=0.5)
        ax_v.legend(fontsize=6.5, framealpha=0.9, loc="upper right")
        for s in ax_v.spines.values():
            s.set_color("#CCCCCC")
        speed_artists["cursor"] = ax_v.axvline(0, color=C["amber"], lw=1.4)
        speed_artists["trip"] = tr

    redraw_speed(trips[0])

    # ================= PyVista 场景 =================
    pl = pv.Plotter(off_screen=True, window_size=(PV_BOX[2], PV_BOX[3]))
    pl.set_background("#F2F2F2")
    try:
        pl.enable_anti_aliasing("msaa")
    except Exception:
        pass
    build_static_scene(pl, goods)

    mast = pl.add_mesh(box(-0.07, 0.07, -0.81, -0.69, Z0, N), color=C["mast"])
    carriage = pl.add_mesh(box(-0.34, 0.34, -1.10, -0.42, -0.30, 0.30),
                           color=C["carriage"])
    forks = pl.add_mesh(pv.merge([box(-0.28, -0.02, -0.42, 0.10, -0.32, -0.26),
                                  box(0.02, 0.28, -0.42, 0.10, -0.32, -0.26)]),
                        color=C["lid"])
    tgt = pl.add_mesh(box(0.04, 0.96, 0.04, 0.96, 0.04, 0.96), color=C["amber"],
                      style="wireframe", line_width=3)
    carried, placed_b, placed_l, paths = [], [], [], []
    for tr in trips:
        g = tr["g"]
        carried.append(pl.add_mesh(box(-0.26, 0.26, -1.02, -0.50, -0.22, 0.22),
                                   color=C[g["cls"]]))
        x, z = g["col"], g["tier"]
        placed_b.append(pl.add_mesh(box(x + 0.15, x + 0.85, 0.14, 0.86,
                                        z + 0.14, z + 0.72), color=C[g["cls"]]))
        placed_l.append(pl.add_mesh(box(x + 0.13, x + 0.87, 0.12, 0.88,
                                        z + 0.72, z + 0.84), color=C["lid"]))
        paths.append(pl.add_mesh(pv.Line((0.5, -0.75, 0.5),
                                         (x + 0.5, -0.75, z + 0.5)),
                                 color=C["path"], line_width=3))
    alarm_box = pl.add_mesh(box(ALARM[0] + 0.14, ALARM[0] + 0.86, 0.12, 0.88,
                                ALARM[1] + 0.14, ALARM[1] + 0.86), color=C["alarm"])
    alarm_wire = pl.add_mesh(box(ALARM[0] + 0.03, ALARM[0] + 0.97, -0.03, 0.05,
                                 ALARM[1] + 0.03, ALARM[1] + 0.97),
                             color=C["alarm"], style="wireframe", line_width=5)
    alarm_cone = pl.add_mesh(pv.Cone(center=(ALARM[0] + 0.5, 0.5, ALARM[1] + 1.7),
                                     direction=(0, 0, -1), height=0.7, radius=0.30),
                             color=C["alarm"])
    q_boxes = [pl.add_mesh(box(0.10, 0.90, -2.4 - i * 1.1, -1.6 - i * 1.1,
                               Z0 + 0.02, Z0 + 0.82), color="#A9C4DE")
               for i in range(5)]

    FOCAL = (N / 2, 0.5, 8.0)
    EL = math.radians(18)

    def set_cam(frac):
        az = math.radians(-72 + 16 * frac)
        R = 42.0
        pos = (FOCAL[0] + R * math.cos(EL) * math.cos(az),
               FOCAL[1] + R * math.cos(EL) * math.sin(az),
               FOCAL[2] + R * math.sin(EL))
        pl.camera_position = [pos, FOCAL, (0, 0, 1)]
        pl.camera.view_angle = 32.0

    def trip_at(t):
        for tr in trips:
            if tr["t0"] <= t < tr["T_end"]:
                return tr
        return None

    # ================= 帧循环 =================
    gen = imageio_ffmpeg.write_frames(OUT, size=(W, H), fps=FPS, quality=8)
    gen.send(None)
    for i in range(FRAMES):
        t = min(i / FPS * SPEED, T_sim)
        tr = trip_at(t)
        n_placed = 11 + sum(1 for x in trips if t >= x["T_xfer"])
        qn = queue_at(t, trips, arrivals)
        fault = t >= fault_t
        t_travel = base_travel + sum(x["T_out"] for x in trips if t >= x["T_xfer"])
        n_resp = t_travel + T_DWELL * n_placed

        # ---- mpl 更新 ----
        if tr is not None and speed_artists["trip"] is not tr:
            redraw_speed(tr)
        if tr is not None:
            speed_artists["cursor"].set_xdata([t - tr["t0"], t - tr["t0"]])
        k = len([x for x in q_steps_t if x <= t])
        q_line.set_data(q_steps_t[:k] + [t], q_steps_n[:k] + [qn])
        cur_q.set_xdata([t, t])
        for j, x in enumerate(trips):
            gi = 11 + j
            if t >= x["T_xfer"]:
                bars[gi].set_height(x["T_out"])
                bars[gi].set_color(C[x["g"]["cls"]])
                dws[gi].set_y(x["T_out"]); dws[gi].set_height(T_DWELL)
            elif tr is x:
                bars[gi].set_height(x["T_out"])
                bars[gi].set_color(C["amber"])
        vals = [f"{n_placed}/20 件", f"{qn} 件", f"{t_travel:.1f} s",
                f"{n_resp/max(n_placed,1):.1f} s",
                f"{0.42 + 0.006*(n_placed-11):.2f} kWh",
                "1(未确认)" if fault else "0"]
        for txt, v in zip(kpi_vals, vals):
            txt.set_text(v)
        kpi_vals[-1].set_color(C["alarm"] if fault else C["txt"])
        kpi_cards[-1].set_edgecolor(C["alarm"] if fault else "#CCCCCC")
        kpi_cards[-1].set_linewidth(1.4 if fault else 0.8)
        fig.canvas.draw()
        base = Image.fromarray(np.asarray(fig.canvas.buffer_rgba())).convert("RGB")

        # ---- pv 更新 ----
        for j, x in enumerate(trips):
            g = x["g"]
            if tr is x:
                tt = t - x["t0"]
                if tt <= x["T_out"]:
                    cx = axis_pos(tt, g["col"], VX, AX)
                    cz = axis_pos(tt, g["tier"], VY, AY)
                    ph = "out"
                elif t <= x["T_place"]:
                    cx, cz, ph = float(g["col"]), float(g["tier"]), "dwell"
                else:
                    tb = t - x["T_place"]
                    cx = g["col"] - axis_pos(tb, g["col"], VX, AX)
                    cz = g["tier"] - axis_pos(tb, g["tier"], VY, AY)
                    ph = "back"
                mast.SetPosition(cx + 0.5, 0, 0)
                carriage.SetPosition(cx + 0.5, 0, cz + 0.5)
                forks.SetPosition(cx + 0.5, 0, cz + 0.5)
                carried[j].SetPosition(cx + 0.5, 0, cz + 0.5)
                carried[j].SetVisibility(t < x["T_xfer"])
                tgt.SetPosition(g["col"], 0, g["tier"])
                tgt.SetVisibility(t < x["T_xfer"])
                paths[j].SetVisibility(ph != "back")
            else:
                carried[j].SetVisibility(False)
                paths[j].SetVisibility(False)
            placed_b[j].SetVisibility(t >= x["T_xfer"])
            placed_l[j].SetVisibility(t >= x["T_xfer"])
        if tr is None:
            tgt.SetVisibility(False)
        alarm_box.SetVisibility(fault)
        alarm_wire.SetVisibility(fault)
        alarm_cone.SetVisibility(fault)
        for kk, qb in enumerate(q_boxes):
            qb.SetVisibility(kk < min(qn, 5))
        set_cam(i / max(1, FRAMES - 1))
        pl.render()
        base.paste(Image.fromarray(pl.screenshot(return_img=True)),
                   (PV_BOX[0], PV_BOX[1]))
        gen.send(np.asarray(base).tobytes())
        if i % 100 == 0:
            print(f"frame {i}/{FRAMES} t={t:.1f}s placed={n_placed} q={qn}")
    gen.close()
    plt.close(fig); pl.close()
    print(f"saved: {OUT}")


if __name__ == "__main__":
    main()
