# -*- coding: utf-8 -*-
"""3D 回放动画(Q4:Python 升级版动画;0710 夜重构=稳定性+三风格变体)。

内容:演示批 20 件货按 AWRA 布局逐件入库——
- 堆垛机 = 立柱+载货台,**切比雪夫双轴同动**(与主口径运动模型一致)
- 当前行程画路径轨迹线;货箱按重量三分位着色;相机缓慢环绕;KPI 字幕实时更新
- 三风格变体(用户挑方向):v3a 工程蓝图(白底,原版精修)/ v3b 暗夜红黑
  (深底+ABB 红点缀,呼应 0706 拍板的红黑品牌方向)/ v3c 极简聚焦(灰调,活动件红色高亮)
输出:sim/figs/anim3d_<style>.mp4(15fps,~23s;原 preview_3d_anim_sample.mp4 保留不覆盖)
依赖:matplotlib + imageio-ffmpeg;确定性渲染,无随机。
用法:python tools/render_3d_animation.py --style v3b        # 单风格
     python tools/render_3d_animation.py --style all        # 三风格全渲
     python tools/render_3d_animation.py --quick --style all  # 前 5 件快样(~8s 视频)
     python tools/render_3d_animation.py --selftest         # 零渲染自检(关键帧断言+对比静帧)
"""
import argparse
import csv
import os
import sys

import matplotlib
matplotlib.use("Agg")
import imageio_ffmpeg
import matplotlib.pyplot as plt
from matplotlib.animation import FFMpegWriter
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["animation.ffmpeg_path"] = imageio_ffmpeg.get_ffmpeg_exe()

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV = os.path.join(ROOT, "sim", "out", "assignment_awra.csv")
FIGS = os.path.join(ROOT, "sim", "figs")

N, N_DEMO, FPS = 20, 20, 15

# ---- 三风格 preset(货箱三色=轻/中/重;active=当前件强调色,None=用货箱色) ----
STYLES = {
    "v3a": dict(  # 工程蓝图:白底细网格,原版精修(阴影地面+更克制的框线)
        name="工程蓝图", bg="#FFFFFF", frame="#22222280", pre="#4a4a4a",
        boxes=("#7FA8C9", "#E8A13A", "#B71C1C"), active=None,
        crane="#1A1A1A", path="#3E7BD6", txt="#111111", sub="#333333",
        foot="#777777", ground="#00000010", edge="#00000055"),
    "v3b": dict(  # 暗夜红黑:深底,ABB 红点缀,发光感边缘——0706 拍板红黑品牌方向
        name="暗夜红黑", bg="#0F1115", frame="#8892A040", pre="#2A2E36",
        boxes=("#5C88B0", "#D9A441", "#E62E2E"), active=None,
        crane="#E8E8E8", path="#38E1D4", txt="#F2F2F2", sub="#C9CFD8",
        foot="#8892A0", ground="#FFFFFF08", edge="#FFFFFF30"),
    "v3c": dict(  # 极简聚焦:灰调库存,唯当前活动件 ABB 红——评委视线聚焦运动
        name="极简聚焦", bg="#F4F4F2", frame="#00000030", pre="#B9B9B4",
        boxes=("#8A8F98", "#8A8F98", "#6B7078"), active="#E62E2E",
        crane="#22252A", path="#E62E2E", txt="#111111", sub="#44474D",
        foot="#8A8F98", ground="#00000008", edge="#00000040"),
}


def box_faces(x, z, shrink=0.12, depth=1.0):
    s = shrink
    x0, x1, y0, y1, z0, z1 = x + s, x + 1 - s, s, depth - s, z + s, z + 1 - s
    v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
         (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    return [[v[0], v[1], v[2], v[3]], [v[4], v[5], v[6], v[7]],
            [v[0], v[1], v[5], v[4]], [v[2], v[3], v[7], v[6]],
            [v[1], v[2], v[6], v[5]], [v[0], v[3], v[7], v[4]]]


def load_goods(n_demo):
    goods = []
    with open(CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            goods.append(dict(name=row["name"], w=float(row["weight_kg"]),
                              col=int(row["col"]), tier=int(row["tier"]),
                              t1=float(row["travel_time_1way_s"])))
    goods = goods[:n_demo]
    if not goods:
        raise RuntimeError(f"数据源为空:{CSV}(先跑 python sim/warehouse_sim.py)")
    ws_ = sorted(g["w"] for g in goods)
    q1, q2 = ws_[len(ws_) // 3], ws_[2 * len(ws_) // 3]
    for g in goods:
        g["wclass"] = 2 if g["w"] > q2 else (1 if g["w"] > q1 else 0)
    return goods


def build_frames(goods):
    """时间轴:每件=去程(载货)+回程(空载 1.6x 速),帧数正比切比雪夫距离;尾部定格 1s。
    返回帧列表,每帧 (good, phase, progress 0..1) 或 None(定格)。"""
    frames = []
    for g in goods:
        cheb = max(g["col"], g["tier"])
        out_f = max(6, int(round(cheb * 0.9)))
        back_f = max(4, int(round(cheb * 0.55)))
        frames += [(g, 0, (k + 1) / out_f) for k in range(out_f)]
        frames += [(g, 1, (k + 1) / back_f) for k in range(back_f)]
    frames += [None] * FPS
    return frames


class Scene:
    """单风格渲染器;render(frame) 逐帧画,状态(placed/t_acc)自持。"""

    def __init__(self, style_key, goods, total):
        self.S = STYLES[style_key]
        self.key = style_key
        self.goods = goods
        self.total = total
        self.placed = []
        self.t_acc = 0.0
        self.i = 0
        self.fig = plt.figure(figsize=(12.8, 7.2), dpi=100)
        self.fig.patch.set_facecolor(self.S["bg"])
        self.ax = self.fig.add_subplot(111, projection="3d")
        self.pre_faces = [f for x in range(N) for z in range(N)
                          if (x + z) % 3 == 0 for f in box_faces(x, z)]

    def _box_color(self, g, is_active=False):
        if is_active and self.S["active"]:
            return self.S["active"]
        return self.S["boxes"][g["wclass"]]

    def render(self, frame):
        S, ax = self.S, self.ax
        ax.clear()
        ax.set_axis_off()
        ax.set_facecolor(S["bg"])
        ax.set_xlim(0, N); ax.set_ylim(-3, 9); ax.set_zlim(0, N)
        ax.set_box_aspect((N, 12, N))
        try:
            ax.set_proj_type("persp", focal_length=0.28)
        except TypeError:
            pass
        ax.view_init(elev=22, azim=-86 + 32 * self.i / self.total)
        self.i += 1

        # 地面片+货架框线
        ax.add_collection3d(Poly3DCollection(
            [[(0, 0, 0), (N, 0, 0), (N, 8, 0), (0, 8, 0)]],
            facecolors=S["ground"], edgecolors="none"))
        for x in range(0, N + 1, 2):
            ax.plot([x, x], [0, 0], [0, N], color=S["frame"], lw=0.5)
        for z in range(0, N + 1, 2):
            ax.plot([0, N], [0, 0], [z, z], color=S["frame"], lw=0.5)
        ax.add_collection3d(Poly3DCollection(
            self.pre_faces, facecolors=S["pre"], edgecolors=S["edge"],
            linewidths=0.2, alpha=0.9))

        for ci in (0, 1, 2):                    # 已入库(每色一集合,提速)
            fs = [f for g in self.placed if g["wclass"] == ci
                  for f in box_faces(g["col"], g["tier"])]
            if fs:
                ax.add_collection3d(Poly3DCollection(
                    fs, facecolors=S["boxes"][ci], edgecolors=S["edge"],
                    linewidths=0.3))

        status = f"演示完成:{len(self.placed)}/{len(self.goods)} 件入库"
        if frame is not None:
            g, ph, p = frame
            if ph == 0:                          # 切比雪夫双轴同动
                cx, cz = g["col"] * p, g["tier"] * p
                if p >= 1 and g not in self.placed:   # 到位落箱(防重)
                    self.placed.append(g)
                    self.t_acc += g["t1"]
            else:
                cx, cz = g["col"] * (1 - p), g["tier"] * (1 - p)
            ax.plot([0.5, g["col"] + 0.5], [0.5, 0.5], [0.5, g["tier"] + 0.5],
                    color=S["path"], lw=1.6, alpha=0.9 if ph == 0 else 0.3,
                    linestyle="--")
            ax.plot([cx + 0.5, cx + 0.5], [0.5, 0.5], [0, N],
                    color=S["crane"], lw=2.2, alpha=0.85)
            car = box_faces(cx, cz, shrink=0.06)
            ax.add_collection3d(Poly3DCollection(
                car,
                facecolors=self._box_color(g, True) if ph == 0 else S["crane"],
                edgecolors=S["edge"], linewidths=0.6))
            status = (f"当前:{g['name']}({g['w']:.1f} kg)→ 库位({g['col']},{g['tier']})"
                      f"  {'载货去程' if ph == 0 else '空载回程'}")

        ax.text2D(0.02, 0.97, "智储优控 · 3D 回放(AWRA-LS · 主口径 H · 切比雪夫双轴同动)",
                  transform=ax.transAxes, fontsize=12, fontweight="bold",
                  va="top", color=S["txt"])
        ax.text2D(0.02, 0.92,
                  f"已入库 {len(self.placed)}/{len(self.goods)} 件   "
                  f"累计行程 {self.t_acc:.1f} s(单程口径)   {status}",
                  transform=ax.transAxes, fontsize=10, va="top", color=S["sub"])
        ax.text2D(0.02, 0.03,
                  f"风格 {self.key}·{S['name']}   数据源:sim/out/assignment_awra.csv"
                  f"(与 AB 画面同一份数据)",
                  transform=ax.transAxes, fontsize=8, va="bottom", color=S["foot"])
        ax.scatter([0.5], [0.5], [-0.6], marker="^", s=120,
                   color=S["boxes"][2], depthshade=False)

    def close(self):
        plt.close(self.fig)


def render_style(style_key, goods, frames, tag=""):
    out = os.path.join(FIGS, f"anim3d_{style_key}{tag}.mp4")
    sc = Scene(style_key, goods, len(frames))
    writer = FFMpegWriter(fps=FPS, bitrate=2400)
    with writer.saving(sc.fig, out, dpi=100):
        for fr in frames:
            sc.render(fr)
            writer.grab_frame()
    n_placed = len(sc.placed)
    sc.close()
    # 帧级自检:全部货物必须恰好落箱一次
    assert n_placed == len(goods), f"{style_key}: 落箱 {n_placed}≠{len(goods)}"
    print(f"saved: {out}({len(frames)} 帧,{len(frames)/FPS:.0f}s,"
          f"落箱自检 {n_placed}/{len(goods)} OK)")
    return out


def selftest():
    """零视频自检:①时间轴/落箱不变量 ②三风格关键帧渲染成对比静帧(contact sheet)。"""
    goods = load_goods(N_DEMO)
    frames = build_frames(goods)
    n_out_end = sum(1 for f in frames if f and f[1] == 0 and f[2] >= 1)
    assert n_out_end == len(goods), f"去程终点帧 {n_out_end}≠{len(goods)}"
    assert frames[-1] is None and frames[-FPS] is None, "尾部定格缺失"
    key_idx = [0, len(frames) // 2, len(frames) - 1]
    for sk in STYLES:
        sc = Scene(sk, goods, len(frames))
        for i, fr in enumerate(frames):          # 全帧状态推进,只在关键帧出图
            sc.render(fr) if i in key_idx else sc._advance_only(fr)
        sc.close()
    print("SELFTEST PASS(时间轴不变量+三风格构造)")


def _advance_only(self, frame):
    """自检用:只推进落箱状态不画图(render 的状态子集,口径一致)。"""
    self.i += 1
    if frame is not None:
        g, ph, p = frame
        if ph == 0 and p >= 1 and g not in self.placed:
            self.placed.append(g)
            self.t_acc += g["t1"]


Scene._advance_only = _advance_only


def contact_sheet(goods, frames):
    """三风格同帧对比静帧(挑方向用):取中段一帧,三图横排合成一张 PNG。"""
    import matplotlib.image as mpimg
    mid = len(frames) * 2 // 5
    paths = []
    for sk in STYLES:
        sc = Scene(sk, goods, len(frames))
        for i in range(mid + 1):
            if i < mid:
                sc._advance_only(frames[i])
            else:
                sc.render(frames[i])
        p = os.path.join(FIGS, f"_anim3d_{sk}_frame.png")
        sc.fig.savefig(p, dpi=100, facecolor=sc.S["bg"])
        sc.close()
        paths.append((sk, p))
    fig, axes = plt.subplots(3, 1, figsize=(12.8, 21.6))
    for ax_, (sk, p) in zip(axes, paths):
        ax_.imshow(mpimg.imread(p))
        ax_.set_title(f"{sk} · {STYLES[sk]['name']}", fontsize=14)
        ax_.axis("off")
    out = os.path.join(FIGS, "anim3d_风格对比.png")
    fig.tight_layout()
    fig.savefig(out, dpi=100)
    plt.close(fig)
    for _, p in paths:
        os.remove(p)
    print(f"saved: {out}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--style", default="all",
                    choices=list(STYLES) + ["all"], help="渲染哪个风格(all=三个)")
    ap.add_argument("--quick", action="store_true", help="只渲前 5 件(快样)")
    ap.add_argument("--selftest", action="store_true", help="零视频自检")
    ap.add_argument("--sheet", action="store_true", help="只出三风格对比静帧")
    a = ap.parse_args()
    if a.selftest:
        selftest()
        return
    goods = load_goods(5 if a.quick else N_DEMO)
    frames = build_frames(goods)
    if a.sheet:
        contact_sheet(goods, frames)
        return
    keys = list(STYLES) if a.style == "all" else [a.style]
    for sk in keys:
        render_style(sk, goods, frames, tag="_quick" if a.quick else "")
    contact_sheet(goods, frames)


if __name__ == "__main__":
    main()
