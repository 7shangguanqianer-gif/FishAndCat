# -*- coding: utf-8 -*-
# analyze_audit.py -- 解析 audit_pages.py 的 TSV,三查:①越界 ②实体重叠 ③文字宽度预算
# 用法: python tools\ab_scripting\analyze_audit.py
# 过滤规则(降误报):
#   - 2px 边线条(w==2 或 h==2)与任何元素相交 = 组框线骑缝,正常
#   - 组标题签(高 18,骑在框线上)与边线相交 = 正常(已被上一条覆盖)
#   - 400 格网格(20x28 类尺寸的密铺)彼此相邻不算重叠(用严格相交:边界重合不报)
#   - crane(28x20 椭圆)叠在格子上 = 正常业务,跳过
# 文字预算:6.5px/字符(0710 方案B mock 教训),多行按最长行。
import io
import sys

TSV = r"F:\abb_wh_work\tools\ab_scripting\audit_pages_result.txt"
CANVAS = {"MAIN": (1280, 720), "STATS": (1280, 720)}  # 假设画布;超界仍报 max extent 供人判断
PX_PER_CHAR = 6.5

rows = []
with io.open(TSV, "r", encoding="utf-8") as f:
    header = f.readline()
    for line in f:
        line = line.rstrip(u"\n")
        if not line or line.startswith(u"==="):
            continue
        parts = line.split(u"\t")
        if len(parts) < 9:
            continue
        page, idx, typ, name, x, y, w, h, text = parts[:9]
        try:
            x, y, w, h = int(x), int(y), int(w), int(h)
        except ValueError:
            continue
        rows.append(dict(page=page, idx=int(idx), typ=typ, name=name,
                         x=x, y=y, w=w, h=h, text=text))

print("loaded %d elements" % len(rows))


def is_line(r):
    return r["w"] <= 2 or r["h"] <= 2


def is_crane(r):
    return (r["w"], r["h"]) == (28, 20)


def is_grid_cell(r):
    # P1 400 格:fix_element_look 几何谓词 (w,h) 属 {28,20} 组合的密铺格
    return r["page"] == "MAIN" and r["w"] == 28 and r["h"] == 20 and r["x"] < 620


def overlap(a, b):
    ix = min(a["x"] + a["w"], b["x"] + b["w"]) - max(a["x"], b["x"])
    iy = min(a["y"] + a["h"], b["y"] + b["h"]) - max(a["y"], b["y"])
    return (ix, iy) if ix > 0 and iy > 0 else None


def label(r):
    t = r["text"][:28] if r["text"] else (r["name"] or r["typ"])
    return u"#%d(%d,%d %dx%d)%r" % (r["idx"], r["x"], r["y"], r["w"], r["h"], t)


for page in ["MAIN", "STATS"]:
    els = [r for r in rows if r["page"] == page]
    print(u"\n===== %s: %d elements =====" % (page, len(els)))
    cw, ch = CANVAS[page]
    mx = max(r["x"] + r["w"] for r in els)
    my = max(r["y"] + r["h"] for r in els)
    print(u"max extent: x=%d y=%d (canvas assumed %dx%d)" % (mx, my, cw, ch))

    print(u"--- [1] out-of-canvas ---")
    n = 0
    for r in els:
        if r["x"] < 0 or r["y"] < 0 or r["x"] + r["w"] > cw or r["y"] + r["h"] > ch:
            print(u"  OOB " + label(r))
            n += 1
    print(u"  (%d)" % n)

    print(u"--- [2] solid-solid overlaps ---")
    solids = [r for r in els
              if not is_line(r) and not is_crane(r) and not is_grid_cell(r)]
    n = 0
    seen = set()
    for i in range(len(solids)):
        for j in range(i + 1, len(solids)):
            a, b = solids[i], solids[j]
            ov = overlap(a, b)
            if ov:
                key = (a["idx"], b["idx"])
                if key in seen:
                    continue
                seen.add(key)
                print(u"  OVL %dx%d  %s <-> %s" % (ov[0], ov[1], label(a), label(b)))
                n += 1
    print(u"  (%d)" % n)

    print(u"--- [3] text width budget (6.5px/char) ---")
    n = 0
    for r in els:
        if not r["text"]:
            continue
        longest = max(len(s) for s in r["text"].split(u"\\n")) if u"\\n" in r["text"] \
            else max(len(s) for s in r["text"].splitlines() or [r["text"]])
        need = longest * PX_PER_CHAR
        if need > r["w"] + 1:
            print(u"  TXT need=%dpx has=%dpx  %s" % (need, r["w"], label(r)))
            n += 1
    print(u"  (%d)" % n)

print(u"\n=== ANALYZE_DONE ===")
