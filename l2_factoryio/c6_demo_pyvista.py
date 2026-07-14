"""C6 demo · PyVista 栈（电影感离线渲染路线）。

按 0713 夜拍板：20×20 逻辑仓单场景 / 数据=真实 AWRA 落位 CSV / 悬浮 KPI /
各展所长（本栈卖点=VTK 硬件 Z-buffer 无遮挡穿帮 + 原生 mp4 电影感运镜）。

产出（Desktop\\C6_demo评审\\PyVista\\）：
- awra_布局成形_12s.mp4       —— 120 件按分配序逐件入库 + 缓慢环绕运镜 + KPI 浮层
- 视角A_等轴测.png / 视角B_正面高位.png / 视角C_低角走廊.png —— 终态三候选视角

色板纪律（服从 v3）：货物=蓝系三档（按重量分级，重货深蓝沉底叙事）；
琥珀=当前正在放置件；不用红（红为报警专属，demo 无报警情节）。

用法： python c6_demo_pyvista.py           # 全量（视频+静帧）
       python c6_demo_pyvista.py --stills  # 只出三张静帧（快速检查）
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import numpy as np
import pyvista as pv

# ---------- 常量 ----------
HERE = Path(__file__).resolve().parent
CSV_PATH = HERE.parent / "sim" / "out" / "assignment_awra.csv"
OUT_DIR = Path(r"C:\Users\86177\Desktop\C6_demo评审\PyVista")

COLS, TIERS = 20, 20          # 20 列 × 20 层逻辑仓
CELL_W, CELL_H, CELL_D = 1.0, 0.6, 0.8   # 单元格 宽(x)/高(z)/深(y)
GAP = 0.12                    # 格间距
FPS = 24
PLACE_EVERY = 2               # 每 2 帧入一件 → 120 件 = 240 帧 = 10s
TAIL_ORBIT = 48               # 片尾环绕 2s
FONT_CANDIDATES = [r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\msyh.ttf",
                   r"C:\Windows\Fonts\simhei.ttf"]

# 蓝系三档（浅→深 = 轻→重），琥珀=正在放置
BLUE_LIGHT = "#9ecae8"
BLUE_MID = "#4f8fc4"
BLUE_DEEP = "#1b4f8a"
AMBER = "#f2b13d"
FRAME_GRAY = "#3a4656"
FLOOR_GRAY = "#20262e"


def load_goods() -> list[dict]:
    rows: list[dict] = []
    with open(CSV_PATH, encoding="utf-8-sig") as fp:
        for r in csv.DictReader(fp):
            rows.append({
                "id": int(r["good_id"]),
                "col": int(r["col"]),
                "tier": int(r["tier"]),
                "weight": float(r["weight_kg"]),
                "travel": float(r["travel_time_1way_s"]),
            })
    return rows


def weight_color(w: float, w33: float, w66: float) -> str:
    if w <= w33:
        return BLUE_LIGHT
    if w <= w66:
        return BLUE_MID
    return BLUE_DEEP


def cell_center(col: int, tier: int) -> tuple[float, float, float]:
    x = col * (CELL_W + GAP)
    z = tier * (CELL_H + GAP)
    return (x, 0.0, z)


def find_cjk_font() -> str | None:
    for p in FONT_CANDIDATES:
        if Path(p).exists():
            return p
    return None


def build_static_scene(pl: pv.Plotter) -> None:
    """地面 + 货架骨架(线框柱梁) + I/O 口标记。"""
    span_x = COLS * (CELL_W + GAP)
    span_z = TIERS * (CELL_H + GAP)
    floor = pv.Plane(center=(span_x / 2 - CELL_W / 2, 0.6, -0.45),
                     direction=(0, 0, 1), i_size=span_x + 6, j_size=4.5)
    pl.add_mesh(floor, color=FLOOR_GRAY, ambient=0.35)

    # 货架骨架：每列一根立柱(前后两根合并观感)、每 4 层一道横梁，克制不喧宾
    frame = pv.MultiBlock()
    for c in range(COLS + 1):
        x = c * (CELL_W + GAP) - (CELL_W + GAP) / 2
        frame.append(pv.Cube(center=(x, 0.0, span_z / 2 - CELL_H / 2),
                             x_length=0.06, y_length=CELL_D * 0.9, z_length=span_z))
    for t in range(0, TIERS + 1, 4):
        z = t * (CELL_H + GAP) - (CELL_H + GAP) / 2
        frame.append(pv.Cube(center=(span_x / 2 - CELL_W / 2, 0.0, z),
                             x_length=span_x, y_length=CELL_D * 0.9, z_length=0.05))
    pl.add_mesh(frame.combine(), color=FRAME_GRAY, opacity=0.55)

    # I/O 口：col 0 地面侧琥珀薄板（空间叙事锚点：近 I/O=近原点）
    io = pv.Cube(center=(0.0, 0.9, -0.38), x_length=1.6, y_length=1.4, z_length=0.1)
    pl.add_mesh(io, color=AMBER, opacity=0.9)


CAMERAS = {
    "A_等轴测": dict(azim=-35, elev=22, zoom=1.0),
    "B_正面高位": dict(azim=-5, elev=32, zoom=1.05),
    "C_低角走廊": dict(azim=-62, elev=8, zoom=0.9),
}


def set_camera(pl: pv.Plotter, azim: float, elev: float, zoom: float) -> None:
    span_x = COLS * (CELL_W + GAP)
    span_z = TIERS * (CELL_H + GAP)
    focus = (span_x / 2 - CELL_W / 2, 0.0, span_z * 0.45)
    dist = span_x * 1.55 / zoom
    a, e = np.radians(azim), np.radians(elev)
    pos = (focus[0] + dist * np.sin(a) * np.cos(e),
           focus[1] - dist * np.cos(a) * np.cos(e),
           focus[2] + dist * np.sin(e))
    pl.camera_position = [pos, focus, (0, 0, 1)]


def kpi_text(placed: int, total: int, mean_travel: float) -> str:
    return (f"AWRA-LS 布局回放(sim)\n"
            f"已入库  {placed:>3d} / {total}\n"
            f"平均单程 {mean_travel:5.2f} s")


def main() -> None:
    stills_only = "--stills" in sys.argv
    goods = load_goods()
    total = len(goods)
    ws = sorted(g["weight"] for g in goods)
    w33, w66 = ws[len(ws) // 3], ws[2 * len(ws) // 3]
    font = find_cjk_font()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pv.OFF_SCREEN = True
    pl = pv.Plotter(off_screen=True, window_size=(1280, 720))
    pl.set_background("#0d1117")
    build_static_scene(pl)

    def add_good_mesh(g: dict, current: bool) -> None:
        color = AMBER if current else weight_color(g["weight"], w33, w66)
        cube = pv.Cube(center=cell_center(g["col"], g["tier"]),
                       x_length=CELL_W * 0.92, y_length=CELL_D, z_length=CELL_H * 0.9)
        pl.add_mesh(cube, color=color, name=f"good{g['id']}",
                    smooth_shading=False, ambient=0.25)

    text_kwargs = dict(position="upper_left", font_size=13, color="#e6edf3")
    if font:
        text_kwargs["font_file"] = font

    # ---------- 三张终态候选视角静帧 ----------
    for g in goods:
        add_good_mesh(g, current=False)
    mean_travel = float(np.mean([g["travel"] for g in goods]))
    pl.add_text(kpi_text(total, total, mean_travel), name="kpi", **text_kwargs)
    for name, cam in CAMERAS.items():
        set_camera(pl, **cam)
        pl.render()   # off_screen 下改相机不会自动重渲染, 不显式 render 则 screenshot 拿缓存帧
        pl.screenshot(OUT_DIR / f"视角{name}.png")
        print(f"[still] 视角{name}.png")

    if stills_only:
        pl.close()
        return

    # ---------- 12s 电影感成形动画 ----------
    for g in goods:  # 清空货物重来（保留骨架/地面/文本）
        pl.remove_actor(f"good{g['id']}")
    movie = OUT_DIR / "awra_布局成形_12s.mp4"
    pl.open_movie(str(movie), framerate=FPS, quality=7)

    placed: list[dict] = []
    frames_total = total * PLACE_EVERY + TAIL_ORBIT
    prev_id: int | None = None
    for frame in range(frames_total):
        # 逐件放置：琥珀闪入 → 下一件时转蓝定格
        if frame % PLACE_EVERY == 0 and frame // PLACE_EVERY < total:
            if prev_id is not None:
                g_prev = goods[len(placed) - 1]
                pl.remove_actor(f"good{g_prev['id']}")
                add_good_mesh(g_prev, current=False)
            g = goods[len(placed)]
            add_good_mesh(g, current=True)
            placed.append(g)
            prev_id = g["id"]
            mt = float(np.mean([x["travel"] for x in placed]))
            pl.add_text(kpi_text(len(placed), total, mt), name="kpi", **text_kwargs)
        # 缓慢环绕：方位角 -55° → -15°
        azim = -55 + 40 * frame / frames_total
        elev = 14 + 10 * np.sin(np.pi * frame / frames_total)
        set_camera(pl, azim=azim, elev=elev, zoom=1.0)
        pl.render()   # 同上: 确保本帧真实重渲染
        pl.write_frame()
    pl.close()
    print(f"[movie] {movie}  ({frames_total} 帧 @ {FPS}fps)")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    main()
