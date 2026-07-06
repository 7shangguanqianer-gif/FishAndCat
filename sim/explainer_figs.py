# -*- coding: utf-8 -*-
"""
explainer_figs.py — 零基础示意图(figE 系列,给 1_给你看/项目通俗导览 配图)
与 fig1-14(数据图)的分工:figE 不含实验数据,纯概念示意,给完全不懂的读者建立画面感。
静态绘制、无随机、可重复再生。运行:python explainer_figs.py → figs/figE1-4
"""
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle, Circle

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False
HERE = os.path.dirname(os.path.abspath(__file__))
FIGS = os.path.join(HERE, "figs")
os.makedirs(FIGS, exist_ok=True)

C_FREE, C_PRE, C_HOT = "#ECECEC", "#707070", "#43A047"
C_CRANE, C_ACC = "#FF6D00", "#1565C0"


def fig_e1():
    """仓库场景:20×20 格子墙 + 预占用 + 承重递减 + I/O 口 + 堆垛机。"""
    fig, ax = plt.subplots(figsize=(8.6, 6.2))
    for c in range(20):
        for t in range(20):
            pre = ((c + t) % 3 == 0)   # 官方口径 sum(0706):x+y 能被3整除
            ax.add_patch(Rectangle((c, t), 0.92, 0.92,
                                   fc=C_PRE if pre else C_FREE,
                                   ec="white", lw=0.6))
    # 堆垛机(立柱+载货台)
    ax.add_patch(Rectangle((4.1, -0.05), 0.7, 20.0, fc="none",
                           ec=C_CRANE, lw=1.4, ls=(0, (4, 3))))
    ax.add_patch(Rectangle((3.9, 6.0), 1.1, 1.0, fc=C_CRANE, ec="none"))
    ax.annotate("堆垛机:横着跑+竖着升\n(两个方向同时动)", xy=(4.5, 7.1),
                xytext=(7.2, 22.3), fontsize=10.5, color=C_CRANE,
                arrowprops=dict(arrowstyle="->", color=C_CRANE, lw=1.2))
    # I/O 口
    ax.add_patch(FancyBboxPatch((-0.2, -2.6), 3.4, 1.5,
                                boxstyle="round,pad=0.12", fc="#FFF3E0",
                                ec=C_CRANE, lw=1.2))
    ax.text(1.5, -1.85, "存取口 I/O\n坐标(0,0)", ha="center", va="center",
            fontsize=10, color="#7A3E00")
    ax.annotate("", xy=(0.4, 0.1), xytext=(1.2, -1.0),
                arrowprops=dict(arrowstyle="->", color=C_CRANE, lw=1.4))
    # 承重递减
    ax.annotate("", xy=(20.9, 19.5), xytext=(20.9, 0.4),
                arrowprops=dict(arrowstyle="->", color="#B71C1C", lw=1.6))
    ax.text(21.25, 0.3, "第0层:限重100kg", fontsize=10, color="#B71C1C")
    ax.text(21.25, 18.9, "第19层:限重62kg", fontsize=10, color="#B71C1C")
    ax.text(21.25, 9.8, "每高一层\n承重-2%", fontsize=10.5, color="#B71C1C")
    # 预占用图例
    ax.add_patch(Rectangle((13.2, 21.2), 0.9, 0.9, fc=C_PRE, ec="white"))
    ax.text(14.4, 21.6, "= 预占用(x+y能被3整除,共133格)", fontsize=10,
            va="center", color="#404040")
    ax.set_title("赛题场景:一面 20列×20层 的“快递柜墙”(400 仓位)",
                 fontsize=13, pad=14)
    ax.set_xlim(-1.2, 27.5)
    ax.set_ylim(-3.2, 23.2)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(os.path.join(FIGS, "figE1_仓库示意.png"), dpi=300)
    plt.close(fig)


def _box(ax, x, y, w, h, text, fc, fontsize=10.5, tc="#202020"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.08",
                                fc=fc, ec="#606060", lw=1.0))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
            fontsize=fontsize, color=tc)


def _arrow(ax, x0, y0, x1, y1, color="#606060"):
    ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1),
                                 arrowstyle="-|>", mutation_scale=16,
                                 color=color, lw=1.4))


def fig_e2():
    """双层算法:在线打分器 vs 批量整理师。"""
    fig, ax = plt.subplots(figsize=(10.5, 6.0))
    # 左列:在线
    ax.text(2.6, 9.6, "第一层:在线打分器(平时值班)", fontsize=12.5,
            fontweight="bold", ha="center", color="#0D47A1")
    _box(ax, 0.6, 8.0, 4.0, 0.9, "来一箱货(五属性)", "#E3F2FD")
    _box(ax, 0.6, 6.3, 4.0, 1.1, "给 400 个格子各打一分\n(一个扫描周期内完成)", "#E3F2FD")
    _box(ax, 0.6, 4.6, 4.0, 0.9, "分数最低的格子胜出", "#E3F2FD")
    _box(ax, 0.6, 2.9, 4.0, 0.9, "放入 + 更新画面", "#E3F2FD")
    for y0, y1 in ((8.0, 7.45), (6.3, 5.55), (4.6, 3.85)):
        _arrow(ax, 2.6, y0, 2.6, y1)
    _box(ax, 0.4, 0.7, 4.4, 1.6,
         "扣分四项:\n跑得远(高频货)/ 重货放高\n举升费电 / 冷门货占黄金位(δ)",
         "#FFF8E1", fontsize=9.8)
    # 右列:批量
    ax.text(8.4, 9.6, "第二层:整理师 AWRA-LS(整批到齐)", fontsize=12.5,
            fontweight="bold", ha="center", color="#1B5E20")
    _box(ax, 6.4, 8.0, 4.0, 0.9, "Rank:重要的先挑位\n(高频/重/大排前面)", "#E8F5E9", 9.8)
    _box(ax, 6.4, 6.3, 4.0, 0.9, "Assign:按队伍顺序\n用同一个打分器选格", "#E8F5E9", 9.8)
    _box(ax, 6.4, 4.6, 4.0, 0.9, "Local Search:两两换位\n能降总分就换,降不动为止", "#E8F5E9", 9.8)
    _box(ax, 6.4, 2.9, 4.0, 0.9, "= 全局优化的“上界”", "#E8F5E9")
    for y0, y1 in ((8.0, 7.25), (6.3, 5.55), (4.6, 3.85)):
        _arrow(ax, 8.4, y0, 8.4, y1)
    # 中间 gap
    _arrow(ax, 4.65, 3.35, 6.35, 3.35, color="#B71C1C")
    ax.text(5.5, 3.75, "差 19.3%(H口径)\n=“不知道未来”的代价", ha="center",
            fontsize=9.8, color="#B71C1C")
    ax.text(8.4, 1.5, "两层用同一个打分公式\n→ 差距全部来自信息量,公平可比",
            ha="center", fontsize=10.2, color="#37474F",
            bbox=dict(boxstyle="round,pad=0.35", fc="#ECEFF1", ec="#90A4AE"))
    ax.set_xlim(0, 11)
    ax.set_ylim(0.3, 10.2)
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(os.path.join(FIGS, "figE2_双层算法.png"), dpi=300)
    plt.close(fig)


def fig_e3():
    """两把尺子:曼哈顿路径长度 vs 切比雪夫行程时间。"""
    fig, ax = plt.subplots(figsize=(9.2, 5.6))
    for c in range(10):
        for t in range(7):
            ax.add_patch(Rectangle((c, t), 0.92, 0.92, fc=C_FREE,
                                   ec="white", lw=0.6))
    ax.add_patch(Rectangle((8, 5), 0.92, 0.92, fc=C_HOT, ec="white"))
    ax.text(8.46, 5.46, "目标", ha="center", va="center", color="white",
            fontsize=9.5, fontweight="bold")
    ax.add_patch(Circle((0.46, 0.46), 0.34, fc=C_CRANE, ec="none"))
    ax.text(0.46, -0.55, "I/O(0,0)", ha="center", fontsize=9.5, color="#7A3E00")
    # 曼哈顿 L 形(蓝实线)
    ax.plot([0.46, 8.46, 8.46], [0.15, 0.15, 5.05], color="#1565C0",
            lw=2.4, solid_capstyle="round")
    ax.text(4.2, -0.75, "尺子①路径长度 = 横8格 + 竖5格 = 13m(曼哈顿,算磨损/损耗)",
            fontsize=10.5, color="#1565C0")
    # 切比雪夫:两轴同时动
    ax.annotate("", xy=(8.3, 0.8), xytext=(0.8, 0.8),
                arrowprops=dict(arrowstyle="->", color="#6A1B9A", lw=2.0))
    ax.annotate("", xy=(1.1, 5.3), xytext=(1.1, 1.1),
                arrowprops=dict(arrowstyle="->", color="#6A1B9A", lw=2.0))
    ax.text(4.6, 1.15, "横向同时跑:8m ÷ 2m/s = 4s", fontsize=10, color="#6A1B9A")
    ax.text(1.35, 3.4, "纵向同时升:\n5m ÷ 0.5m/s = 10s", fontsize=10, color="#6A1B9A")
    ax.text(0.0, 7.5, "尺子②行程时间 = max(4s, 10s) = 10s(切比雪夫:双轴同动,时间由慢的那个轴决定)",
            fontsize=10.5, color="#6A1B9A", fontweight="bold")
    ax.text(0.0, 6.85, "→ 两把尺子量的是两件事,报告里并列呈现;“路径短”不等于“时间短”(实测差可达 2.5 倍,F1)",
            fontsize=9.8, color="#37474F")
    ax.set_xlim(-0.6, 10.4)
    ax.set_ylim(-1.3, 8.2)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(os.path.join(FIGS, "figE3_两把尺子.png"), dpi=300)
    plt.close(fig)


def fig_e4():
    """扫描周期分片:大算法怎么塞进 10ms 心跳。"""
    fig, ax = plt.subplots(figsize=(10.5, 4.6))
    x = 0.4
    for k in range(5):
        ax.add_patch(Rectangle((x, 2.0), 1.9, 1.5, fc="#ECEFF1", ec="#607D8B", lw=1.1))
        ax.add_patch(Rectangle((x + 0.12, 2.12), 0.55, 1.26, fc="#BBDEFB", ec="none"))
        ax.add_patch(Rectangle((x + 0.72, 2.12), 0.5, 1.26, fc="#C8E6C9", ec="none"))
        ax.text(x + 0.4, 2.75, "常规\n控制", ha="center", va="center", fontsize=8.6)
        ax.text(x + 0.97, 2.75, "算法\n切片", ha="center", va="center", fontsize=8.6)
        ax.text(x + 0.95, 1.7, f"第{k+1}拍(10ms)", ha="center", fontsize=9)
        if k < 4:
            _arrow(ax, x + 1.9, 2.75, x + 2.12, 2.75)
        x += 2.12
    ax.add_patch(Rectangle((0.4, 3.75), 10.06, 0.001, fc="none"))
    ax.annotate("", xy=(10.5, 4.15), xytext=(0.4, 4.15),
                arrowprops=dict(arrowstyle="->", color="#1B5E20", lw=1.6))
    ax.text(5.4, 4.4, "一个大优化任务(如批量分配 120 箱)切成小片,跨很多拍完成——算法照常收敛,PLC 永不卡顿",
            ha="center", fontsize=10.3, color="#1B5E20")
    ax.text(5.4, 0.9, "看门狗规则:任何一拍超过 10ms 没干完 → 强制重启(所以绝不允许一次算到底)\n"
                      "每拍切多大有旋钮:nBatchPerCycle(每拍处理几箱)/ nPairsPerCycle(每拍评估几对换位)",
            ha="center", fontsize=9.6, color="#B71C1C",
            bbox=dict(boxstyle="round,pad=0.35", fc="#FFF3F3", ec="#E57373"))
    ax.set_xlim(0, 11)
    ax.set_ylim(0.3, 5.0)
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(os.path.join(FIGS, "figE4_扫描周期分片.png"), dpi=300)
    plt.close(fig)


if __name__ == "__main__":
    fig_e1()
    fig_e2()
    fig_e3()
    fig_e4()
    print("已生成:figs/figE1_仓库示意.png / figE2_双层算法.png / "
          "figE3_两把尺子.png / figE4_扫描周期分片.png")
