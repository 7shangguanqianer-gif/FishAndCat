# -*- coding: utf-8 -*-
"""仓储格子 4 版风格方案(0706 用户"全部推倒重设计"指令;PyVista 渲染=与正式动画同引擎)。

V1 钢构写实:橙色钢立柱+逐层横梁+瓦楞纸箱色货物+木托盘——真实仓库气质;
V2 格柜剖面:实体背板+纵横隔板成真格子,货箱嵌格,预占=哑灰封板——"格子"表达最强;
V3 暗色孪生:深底+青色全息线框格+半透明发光货箱——监控大屏/数字孪生气质;
V4 极简浮雕:白墙+浅刻格线+彩块浮出——数据墙/信息设计气质(GitHub 热力墙的 3D 版)。
共通:同一数据(assignment CSV 前 20 件+预占 133+报警格)、同一相机,只比风格。
输出:sim/figs/rack_style_{1..4}_*.png + rack_styles_overview.png(2×2 对比总览)
用法:python tools/render_rack_styles.py
"""
import csv
import math
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import numpy as np
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


def box(x0, x1, y0, y1, z0, z1):
    return pv.Box(bounds=(x0, x1, y0, y1, z0, z1))


def cell_box(x, z, shrink=0.10, y0=0.10, y1=0.90):
    s = shrink
    return box(x + s, x + 1 - s, y0, y1, z + s, z + 1 - s)


def new_plotter(bg):
    pl = pv.Plotter(off_screen=True, window_size=WSZ)
    pl.set_background(bg)
    try:
        pl.enable_anti_aliasing("msaa")
    except Exception:
        pass
    return pl


def set_cam(pl, az_deg=-68, el_deg=18, R=42.0, focal=(N / 2, 0.5, 8.3)):
    az, el = math.radians(az_deg), math.radians(el_deg)
    pos = (focal[0] + R * math.cos(el) * math.cos(az),
           focal[1] + R * math.cos(el) * math.sin(az),
           focal[2] + R * math.sin(el))
    pl.camera_position = [pos, focal, (0, 0, 1)]
    pl.camera.view_angle = 32.0


def add_crane(pl, x=9.0, z=6.0, mast_color="#1A1A1A", car_color="#3A3F45"):
    pl.add_mesh(box(-0.5, N + 0.5, -0.82, -0.68, -0.02, 0.06), color="#333333")
    m = box(x + 0.43, x + 0.57, -0.81, -0.69, 0, N)
    pl.add_mesh(m, color=mast_color)
    pl.add_mesh(box(x + 0.16, x + 0.84, -1.10, -0.42, z + 0.20, z + 0.80),
                color=car_color)


# ---------------- V1 钢构写实 ----------------
def style1():
    pl = new_plotter("#EFEAE3")
    pl.add_mesh(box(-2, N + 4, -6, 3, -0.08, 0.0), color="#55585C")          # 地坪
    posts = [box(x - 0.05, x + 0.05, y - 0.05, y + 0.05, 0, N)
             for x in range(0, N + 1, 2) for y in (0.0, 1.0)]
    pl.add_mesh(pv.merge(posts), color="#D96C1E")                            # 橙钢立柱
    beams = [box(0, N, y - 0.022, y + 0.022, z - 0.028, z + 0.028)
             for z in range(0, N + 1) for y in (0.0, 1.0)]
    pl.add_mesh(pv.merge(beams), color="#46586B")                            # 逐层横梁
    pallets, boxes = {"p": []}, {"heavy": [], "mid": [], "light": [], "pre": []}
    for x, z in PRE:
        pallets["p"].append(box(x + 0.06, x + 0.94, 0.06, 0.94, z + 0.03, z + 0.09))
        boxes["pre"].append(box(x + 0.14, x + 0.86, 0.14, 0.86, z + 0.09, z + 0.70))
    for g in GOODS:
        x, z = g["col"], g["tier"]
        pallets["p"].append(box(x + 0.06, x + 0.94, 0.06, 0.94, z + 0.03, z + 0.09))
        h = {"heavy": 0.80, "mid": 0.68, "light": 0.56}[g["cls"]]
        boxes[g["cls"]].append(box(x + 0.10, x + 0.90, 0.10, 0.90, z + 0.09, z + h))
    pl.add_mesh(pv.merge(pallets["p"]), color="#9C7B45")                     # 木托盘
    for cls, col in (("heavy", "#7E4E1F"), ("mid", "#A56A2E"),
                     ("light", "#C08F4F"), ("pre", "#74787C")):
        pl.add_mesh(pv.merge(boxes[cls]), color=col)
    pl.add_mesh(cell_box(*ALARM, shrink=0.10, y0=0.10, y1=0.86), color="#B71C1C")
    add_crane(pl, mast_color="#2B2B2B", car_color="#D96C1E")
    pl.add_mesh(pv.Cone(center=(0.5, -0.75, 0.35), direction=(0, 0, 1),
                        height=0.5, radius=0.22), color="#B71C1C")
    return pl


# ---------------- V2 格柜剖面 ----------------
def style2():
    pl = new_plotter("#FFFFFF")
    pl.add_mesh(box(-2, N + 4, -6, 3, -0.08, 0.0), color="#E8E8E8")
    pl.add_mesh(box(0, N, 0.95, 1.06, 0, N), color="#D8DADC")                # 背板
    shelves = [box(0, N, 0.0, 0.95, z - 0.032, z + 0.032) for z in range(N + 1)]
    parts = [box(x - 0.032, x + 0.032, 0.0, 0.95, 0, N) for x in range(N + 1)]
    pl.add_mesh(pv.merge(shelves + parts), color="#C6C9CC")                  # 纵横隔板
    covers, goods = [], {"heavy": [], "mid": [], "light": []}
    for x, z in PRE:                                                         # 预占=封板
        covers.append(box(x + 0.09, x + 0.91, -0.03, 0.05, z + 0.09, z + 0.91))
    pl.add_mesh(pv.merge(covers), color="#9AA0A5")
    for g in GOODS:
        goods[g["cls"]].append(cell_box(g["col"], g["tier"], 0.14, 0.16, 0.88))
    for cls, col in (("heavy", "#2E4A68"), ("mid", "#5B7A9D"), ("light", "#A9C0D8")):
        if goods[cls]:
            pl.add_mesh(pv.merge(goods[cls]), color=col)
    pl.add_mesh(cell_box(*ALARM, 0.14, 0.16, 0.88), color="#B71C1C")
    pl.add_mesh(cell_box(*ALARM, 0.03, -0.02, 0.94), color="#B71C1C",
                style="wireframe", line_width=4)
    add_crane(pl, mast_color="#1A1A1A", car_color="#5B7A9D")
    pl.add_mesh(pv.Cone(center=(0.5, -0.75, 0.35), direction=(0, 0, 1),
                        height=0.5, radius=0.22), color="#B71C1C")
    return pl


# ---------------- V3 暗色孪生 ----------------
def style3():
    pl = new_plotter("#0E1420")
    pl.add_mesh(box(-2, N + 4, -6, 3, -0.06, 0.0), color="#131A26")
    lines = []
    for x in range(-2, N + 5, 2):
        lines.append(pv.Line((x, -6, 0.01), (x, 3, 0.01)))
    for y in range(-6, 4, 2):
        lines.append(pv.Line((-2, y, 0.01), (N + 4, y, 0.01)))
    pl.add_mesh(pv.merge(lines), color="#123B44", line_width=1)              # 地面网格
    cells = [cell_box(x, z, 0.03, 0.03, 0.97) for x in range(N) for z in range(N)]
    pl.add_mesh(pv.merge(cells), color="#17E9E0", style="wireframe",
                line_width=1, opacity=0.35)                                  # 全息格框
    goods = {"heavy": [], "mid": [], "light": []}
    for g in GOODS:
        goods[g["cls"]].append(cell_box(g["col"], g["tier"], 0.12))
    for cls, col in (("heavy", "#FF8A3D"), ("mid", "#B36BFF"), ("light", "#29D8FF")):
        if goods[cls]:
            pl.add_mesh(pv.merge(goods[cls]), color=col, opacity=0.88)
    pre = [cell_box(x, z, 0.16) for x, z in PRE]
    pl.add_mesh(pv.merge(pre), color="#39424E", opacity=0.5)
    pl.add_mesh(cell_box(*ALARM, 0.10), color="#FF2D4C")
    pl.add_mesh(cell_box(*ALARM, 0.02), color="#FF2D4C", style="wireframe",
                line_width=3)
    try:
        pl.enable_depth_peeling()
    except Exception:
        pass
    add_crane(pl, mast_color="#17E9E0", car_color="#0E6E78")
    return pl


# ---------------- V4 极简浮雕 ----------------
def style4():
    pl = new_plotter("#FFFFFF")
    pl.add_light(pv.Light(light_type="headlight", intensity=0.65))          # 提亮白墙
    pl.add_mesh(box(-1.2, N + 1.2, 0.50, 0.62, -1.2, N + 1.2), color="#FAFAFA")  # 白墙
    lines = []
    for x in range(N + 1):
        lines.append(pv.Line((x, 0.495, 0), (x, 0.495, N)))
    for z in range(N + 1):
        lines.append(pv.Line((0, 0.495, z), (N, 0.495, z)))
    pl.add_mesh(pv.merge(lines), color="#E0E0E0", line_width=1)              # 浅刻格线
    pre = [box(x + 0.16, x + 0.84, 0.34, 0.50, z + 0.16, z + 0.84) for x, z in PRE]
    pl.add_mesh(pv.merge(pre), color="#DDE0E3")                              # 浅浮雕
    goods = {"heavy": [], "mid": [], "light": []}
    for g in GOODS:
        goods[g["cls"]].append(box(g["col"] + 0.10, g["col"] + 0.90, -0.15, 0.50,
                                   g["tier"] + 0.10, g["tier"] + 0.90))
    for cls, col in (("heavy", "#2E4A68"), ("mid", "#5B7A9D"), ("light", "#A9C0D8")):
        if goods[cls]:
            pl.add_mesh(pv.merge(goods[cls]), color=col)
    pl.add_mesh(box(ALARM[0] + 0.10, ALARM[0] + 0.90, -0.38, 0.50,
                    ALARM[1] + 0.10, ALARM[1] + 0.90), color="#B71C1C")      # 报警最凸
    return pl


def main():
    styles = [("1_steel", "V1 钢构写实", style1, {}),
              ("2_cabinet", "V2 格柜剖面", style2, {}),
              ("3_neon", "V3 暗色孪生", style3, {}),
              ("4_relief", "V4 极简浮雕", style4,
               dict(R=48.0, focal=(N / 2, 0.5, 10.0)))]
    paths = []
    for key, label, fn, cam in styles:
        pl = fn()
        set_cam(pl, **cam)
        pl.render()
        out = os.path.join(FIGS, f"rack_style_{key}.png")
        img = pl.screenshot(return_img=True)
        Image.fromarray(img).save(out)
        pl.close()
        paths.append((out, label))
        print(f"saved: {out}")

    # 2×2 对比总览
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
    out = os.path.join(FIGS, "rack_styles_overview.png")
    sheet.save(out)
    print(f"saved: {out}")


if __name__ == "__main__":
    main()
