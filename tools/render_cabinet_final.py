# -*- coding: utf-8 -*-
"""V2c 蓝灰工程柜 · 定稿细化版(0706 三轮:用户拍 V2c+两修改;本文件=正式动画的场景规格)。

用户指令:①货箱去掉正面标签;②预占格=柜体同色封死。
细节优化(本轮新增):柜体底座+顶帽 / 底座刻列号数字(真实货架位号惯例)/
地坪分缝线+入口站台垫 / 堆垛机海军蓝+货叉托板 / 入口锥红→琥珀(红=报警专属纪律)/
描边条变细(0.042→0.036)。
输出:sim/figs/cabinet_final_full.png(全景)+ cabinet_final_closeup.png(特写验细节)
用法:python tools/render_cabinet_final.py
"""
import csv
import math
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import pyvista as pv
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV = os.path.join(ROOT, "sim", "out", "assignment_awra.csv")
FIGS = os.path.join(ROOT, "sim", "figs")
N = 20
ALARM = (17, 2)
WSZ = (1500, 950)

# V2c 定稿色板
C = dict(bg="#F6F7F9", floor="#E4E6E9", seam="#D5D8DC", pad="#D8DBDF",
         body="#C9CFD6", inner="#AEB6BF", edge="#EDF1F5", plinth="#A7AFB8",
         cap="#B4BBC3", digit="#5F6870",
         heavy="#17365D", mid="#4A6FA5", light="#9DBBDD", lid="#122A47",
         alarm="#B71C1C", amber="#E7B800", rail="#7C838B",
         mast="#17365D", carriage="#4A6FA5")

Z0 = -0.5          # 地坪顶面(柜体底座 -0.5..0,货架 0..20)


def load_goods():
    goods = []
    with open(CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            goods.append(dict(w=float(row["weight_kg"]), col=int(row["col"]),
                              tier=int(row["tier"])))
    goods = goods[:20]
    ws = sorted(g["w"] for g in goods)
    q1, q2 = ws[len(ws) // 3], ws[2 * len(ws) // 3]
    for g in goods:
        g["cls"] = "heavy" if g["w"] > q2 else ("mid" if g["w"] > q1 else "light")
    return goods


def box(x0, x1, y0, y1, z0, z1):
    return pv.Box(bounds=(x0, x1, y0, y1, z0, z1))


def digit_mesh(s, height, center, color_unused=None):
    """立体数字,正面朝 -y(观察侧)。"""
    m = pv.Text3D(s, depth=0.03)
    b = m.bounds
    h = b[3] - b[2] if (b[3] - b[2]) > 0 else 1.0   # Text3D 的字高在 y 方向
    m.scale(height / h, inplace=True)
    m.rotate_x(90, inplace=True)                     # 立起来,面朝 -y
    b = m.bounds
    m.translate((center[0] - (b[0] + b[1]) / 2,
                 center[1] - b[2],
                 center[2] - (b[4] + b[5]) / 2), inplace=True)
    return m


def build(pl):
    goods = load_goods()
    pre = [(x, z) for x in range(N) for z in range(N) if (x + z) % 3 == 0]

    pl.add_light(pv.Light(position=(34, -30, 42), focal_point=(10, 0, 10),
                          intensity=0.35))
    pl.add_light(pv.Light(light_type="headlight", intensity=0.25))

    # 地坪+分缝线+入口站台垫
    pl.add_mesh(box(-2, N + 4, -6, 3, Z0 - 0.08, Z0), color=C["floor"])
    seams = [pv.Line((x, -6, Z0 + 0.004), (x, 3, Z0 + 0.004))
             for x in range(-2, N + 5, 4)]
    seams += [pv.Line((-2, y, Z0 + 0.004), (N + 4, y, Z0 + 0.004))
              for y in range(-6, 4, 2)]
    pl.add_mesh(pv.merge(seams), color=C["seam"], line_width=1)
    pl.add_mesh(box(-0.2, 1.2, -2.6, -0.9, Z0, Z0 + 0.02), color=C["pad"])

    # 柜体:底座/背板/内衬/隔板/描边/顶帽
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

    # 底座列号(每 5 列)
    for n in range(0, N + 1, 5):
        pl.add_mesh(digit_mesh(str(n), 0.30, (n + 0.5 if n < N else n - 0.5,
                                              -0.305, -0.26)), color=C["digit"])

    # 预占=柜体同色封死(仅靠光影分辨,官方口径的"不存在的格")
    covers = [box(x + 0.10, x + 0.90, -0.008, 0.05, z + 0.10, z + 0.90)
              for x, z in pre]
    pl.add_mesh(pv.merge(covers), color=C["body"])

    # 货箱:主体+盖沿(无标签)
    bodies = {"heavy": [], "mid": [], "light": []}
    lids = []
    for g in goods:
        x, z = g["col"], g["tier"]
        bodies[g["cls"]].append(box(x + 0.15, x + 0.85, 0.14, 0.86, z + 0.14, z + 0.72))
        lids.append(box(x + 0.13, x + 0.87, 0.12, 0.88, z + 0.72, z + 0.84))
    for cls in bodies:
        if bodies[cls]:
            pl.add_mesh(pv.merge(bodies[cls]), color=C[cls])
    pl.add_mesh(pv.merge(lids), color=C["lid"])

    # 报警格:红箱+格口红框
    ax_, az_ = ALARM
    pl.add_mesh(box(ax_ + 0.14, ax_ + 0.86, 0.12, 0.88, az_ + 0.14, az_ + 0.86),
                color=C["alarm"])
    pl.add_mesh(box(ax_ + 0.03, ax_ + 0.97, -0.03, 0.05, az_ + 0.03, az_ + 0.97),
                color=C["alarm"], style="wireframe", line_width=5)

    # 堆垛机:地轨+海军蓝立柱+载货台+货叉托板;入口琥珀锥
    pl.add_mesh(box(-0.5, N + 0.5, -0.82, -0.68, Z0, Z0 + 0.08), color=C["rail"])
    pl.add_mesh(box(8.43, 8.57, -0.81, -0.69, Z0, N), color=C["mast"])
    pl.add_mesh(box(8.16, 8.84, -1.10, -0.42, 4.70, 5.30), color=C["carriage"])
    pl.add_mesh(box(8.22, 8.48, -0.42, 0.10, 4.66, 4.72), color=C["lid"])
    pl.add_mesh(box(8.52, 8.78, -0.42, 0.10, 4.66, 4.72), color=C["lid"])
    pl.add_mesh(pv.Cone(center=(0.5, -0.75, Z0 + 0.30), direction=(0, 0, 1),
                        height=0.5, radius=0.22), color=C["amber"])


def shot(cam, out):
    pl = pv.Plotter(off_screen=True, window_size=WSZ)
    pl.set_background(C["bg"])
    try:
        pl.enable_anti_aliasing("msaa")
    except Exception:
        pass
    build(pl)
    az, el = math.radians(cam["az"]), math.radians(cam["el"])
    focal, R = cam["focal"], cam["R"]
    pos = (focal[0] + R * math.cos(el) * math.cos(az),
           focal[1] + R * math.cos(el) * math.sin(az),
           focal[2] + R * math.sin(el))
    pl.camera_position = [pos, focal, (0, 0, 1)]
    pl.camera.view_angle = cam.get("va", 32.0)
    pl.render()
    Image.fromarray(pl.screenshot(return_img=True)).save(out)
    pl.close()
    print(f"saved: {out}")


def main():
    shot(dict(az=-68, el=18, R=42.0, focal=(N / 2, 0.5, 8.0)),
         os.path.join(FIGS, "cabinet_final_full.png"))
    shot(dict(az=-58, el=12, R=13.0, focal=(15.8, 0.4, 2.6)),
         os.path.join(FIGS, "cabinet_final_closeup.png"))


if __name__ == "__main__":
    main()
