# -*- coding: utf-8 -*-
"""V2 格柜剖面 · 4 版详细设计(0706 二轮:用户拍 V2 后要求"更美观+4 种详细设计")。

美观升级(四版共用的结构语言):
- 每格内衬深一档薄片 → 格子有进深阴影,立体感;
- 隔板前缘描边条(与柜体撞色)→ 精致格口;
- 货箱=主体+深色盖沿+正面小标签 → 不再是"色块";
- 侧上方点光+弱头灯 → 隔板阴影层次;
- 报警格=红箱+格口红框条。
四版气质:a 珍珠白展柜 / b 炭灰工业柜 / c 蓝灰工程柜(与报告 PPT 同族)/ d 暖米轻奢柜。
输出:sim/figs/cabinet_{a..d}_*.png + cabinet_variants_overview.png
用法:python tools/render_cabinet_variants.py
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
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV = os.path.join(ROOT, "sim", "out", "assignment_awra.csv")
FIGS = os.path.join(ROOT, "sim", "figs")
N = 20
ALARM = (17, 2)
WSZ = (1500, 950)


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


GOODS = load_goods()
PRE = [(x, z) for x in range(N) for z in range(N) if (x + z) % 3 == 0]
OCC = {(g["col"], g["tier"]) for g in GOODS} | set(PRE) | {ALARM}


def box(x0, x1, y0, y1, z0, z1):
    return pv.Box(bounds=(x0, x1, y0, y1, z0, z1))


def build_cabinet(pl, P):
    """P: 配色方案 dict(body/inner/edge/cover/goods{}/lid_dark/alarm/floor)。"""
    pl.add_mesh(box(-2, N + 4, -6, 3, -0.08, 0.0), color=P["floor"])
    pl.add_mesh(box(0, N, 0.95, 1.06, 0, N), color=P["body"])                # 背板
    inner = [box(x + 0.05, x + 0.95, 0.925, 0.95, z + 0.05, z + 0.95)
             for x in range(N) for z in range(N)]
    pl.add_mesh(pv.merge(inner), color=P["inner"])                           # 格内衬(进深阴影)
    shelves = [box(0, N, 0.0, 0.95, z - 0.030, z + 0.030) for z in range(N + 1)]
    parts = [box(x - 0.030, x + 0.030, 0.0, 0.95, 0, N) for x in range(N + 1)]
    pl.add_mesh(pv.merge(shelves + parts), color=P["body"])                  # 隔板
    edges = ([box(0, N, -0.025, 0.045, z - 0.042, z + 0.042) for z in range(N + 1)]
             + [box(x - 0.042, x + 0.042, -0.025, 0.045, 0, N) for x in range(N + 1)])
    pl.add_mesh(pv.merge(edges), color=P["edge"])                            # 格口描边
    covers = [box(x + 0.10, x + 0.90, -0.012, 0.06, z + 0.10, z + 0.90)
              for x, z in PRE]
    pl.add_mesh(pv.merge(covers), color=P["cover"])                          # 预占封板
    bodies = {k: [] for k in P["goods"]}
    lids, labels = [], []
    for g in GOODS:
        x, z = g["col"], g["tier"]
        bodies[g["cls"]].append(box(x + 0.15, x + 0.85, 0.14, 0.86, z + 0.14, z + 0.72))
        lids.append(box(x + 0.13, x + 0.87, 0.12, 0.88, z + 0.72, z + 0.84))
        labels.append(box(x + 0.38, x + 0.62, 0.115, 0.145, z + 0.30, z + 0.52))
    for cls, col in P["goods"].items():
        if bodies[cls]:
            pl.add_mesh(pv.merge(bodies[cls]), color=col)
    pl.add_mesh(pv.merge(lids), color=P["lid"])                              # 盖沿
    pl.add_mesh(pv.merge(labels), color="#F5F5F0")                           # 标签
    ax_, az_ = ALARM
    pl.add_mesh(box(ax_ + 0.14, ax_ + 0.86, 0.12, 0.88, az_ + 0.14, az_ + 0.86),
                color=P["alarm"])
    pl.add_mesh(box(ax_ + 0.03, ax_ + 0.97, -0.03, 0.05, az_ + 0.03, az_ + 0.97),
                color=P["alarm"], style="wireframe", line_width=5)           # 格口红框
    # 堆垛机+入口
    pl.add_mesh(box(-0.5, N + 0.5, -0.82, -0.68, -0.02, 0.06), color=P["rail"])
    pl.add_mesh(box(8.43, 8.57, -0.81, -0.69, 0, N), color=P["mast"])
    pl.add_mesh(box(8.16, 8.84, -1.10, -0.42, 5.20, 5.80), color=P["edge"])
    pl.add_mesh(pv.Cone(center=(0.5, -0.75, 0.35), direction=(0, 0, 1),
                        height=0.5, radius=0.22), color=P["alarm"])


VARIANTS = {
    "a": dict(label="V2a 珍珠白展柜", bg="#FFFFFF", floor="#EDEAE4",
              body="#F2EFEA", inner="#DBD5CA", edge="#FFFFFF", cover="#D8D2C6",
              goods={"heavy": "#2E4A68", "mid": "#5B7A9D", "light": "#A9C0D8"},
              lid="#243A52", alarm="#B71C1C", rail="#8A8A86", mast="#3A3A38"),
    "b": dict(label="V2b 炭灰工业柜", bg="#202226", floor="#26282C",
              body="#3A3E44", inner="#2C3035", edge="#565B62", cover="#6A6F76",
              goods={"heavy": "#2196C9", "mid": "#64B5E3", "light": "#A6D4F0"},
              lid="#17739C", alarm="#FF3B30", rail="#17191C", mast="#0E0F11"),
    "c": dict(label="V2c 蓝灰工程柜", bg="#F6F7F9", floor="#E4E6E9",
              body="#C9CFD6", inner="#AEB6BF", edge="#EDF1F5", cover="#8E979E",
              goods={"heavy": "#17365D", "mid": "#4A6FA5", "light": "#9DBBDD"},
              lid="#122A47", alarm="#B71C1C", rail="#7C838B", mast="#2B2F34"),
    "d": dict(label="V2d 暖米轻奢柜", bg="#FBF8F2", floor="#E8E0D2",
              body="#D9CBB4", inner="#C2B296", edge="#F1E9DA", cover="#B7A98F",
              goods={"heavy": "#3E6E8E", "mid": "#6E9BB4", "light": "#A3C4D6"},
              lid="#2F5670", alarm="#B71C1C", rail="#9A8F7B", mast="#4A4438"),
}


def main():
    paths = []
    for key, P in VARIANTS.items():
        pl = pv.Plotter(off_screen=True, window_size=WSZ)
        pl.set_background(P["bg"])
        try:
            pl.enable_anti_aliasing("msaa")
        except Exception:
            pass
        pl.add_light(pv.Light(position=(34, -30, 42), focal_point=(10, 0, 10),
                              intensity=0.35))
        pl.add_light(pv.Light(light_type="headlight", intensity=0.25))
        build_cabinet(pl, P)
        az, el, R = math.radians(-68), math.radians(18), 42.0
        focal = (N / 2, 0.5, 8.3)
        pos = (focal[0] + R * math.cos(el) * math.cos(az),
               focal[1] + R * math.cos(el) * math.sin(az),
               focal[2] + R * math.sin(el))
        pl.camera_position = [pos, focal, (0, 0, 1)]
        pl.camera.view_angle = 32.0
        pl.render()
        out = os.path.join(FIGS, f"cabinet_{key}.png")
        Image.fromarray(pl.screenshot(return_img=True)).save(out)
        pl.close()
        paths.append((out, P["label"]))
        print(f"saved: {out}")

    font = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 42)
    w, h = WSZ
    sheet = Image.new("RGB", (w * 2 + 60, h * 2 + 160), "#FFFFFF")
    dr = ImageDraw.Draw(sheet)
    for i, (p, label) in enumerate(paths):
        im = Image.open(p)
        x = 20 + (i % 2) * (w + 20)
        y = 70 + (i // 2) * (h + 80)
        sheet.paste(im, (x, y))
        dr.text((x + 10, y - 55), label, fill="#1A1A1A", font=font)
    out = os.path.join(FIGS, "cabinet_variants_overview.png")
    sheet.save(out)
    print(f"saved: {out}")


if __name__ == "__main__":
    main()
