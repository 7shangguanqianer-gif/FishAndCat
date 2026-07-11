# -*- coding: utf-8 -*-
# relayout_p2.py -- P2 版1「对齐P1分组风」施工(0711 用户拍板;设计稿=2_你要操作/P2排版三方案_0711.html)
# 内容:4 组边线框+组标题签 / 表头底纹(绑 GVL_Visu.dwHeaderBg) / 说明行改字(治 Total goods 困惑)
#      / 三只 Lamp 换红色图像的属性路径探针(探通则设,不通留 GUI)。
# 红线:7 个输入框(已 GUI 洗活)与一切既有动作元素**零接触**——只加装饰、只改静态文本/表头绑定。
# 前置:AB 关闭;跑完必 ab_sync(02 GVL 新常量 dwHeaderBg 需同步)再 GUI F11 终验。
import io

PROJECT = r"F:\abb_wh_work\plc\AB_Project\ABB_WH.project"
RESULT = r"F:\abb_wh_work\tools\ab_scripting\relayout_p2_result.txt"

out = io.open(RESULT, "w", encoding="utf-8")


def log(v):
    out.write(unicode(v) + u"\n")
    out.flush()


project = projects.open(PROJECT)  # noqa: F821
visu = project.find("VisuStats", True)[0]
vel = visu.visual_element_list
visu.begin_modify()

by_text = {}
for i in range(len(vel)):
    el = vel[i]
    try:
        t = el.get_property("Texts.Text")
    except Exception:
        continue
    if t:
        by_text.setdefault(t, []).append(el)


def one(text):
    els = by_text.get(text, [])
    return els[0] if len(els) == 1 else None


def deco(x, y, w, h, text=None, fill=None):
    el = vel.add_element(VisualElementType.Rectangle)  # noqa: F821
    el.set_property("Position.X", x)
    el.set_property("Position.Y", y)
    el.set_property("Position.Width", w)
    el.set_property("Position.Height", h)
    if text is not None:
        el.set_property("Texts.Text", text)
    if fill:
        el.set_property("Color variables.Normal state.Fill color", fill)
    return el


def frame(x, y, w, h, title):
    deco(x, y, w, 2)
    deco(x, y + h - 2, w, 2)
    deco(x, y, 2, h)
    deco(x + w - 2, y, 2, h)
    deco(x + 8, y - 9, int(6.5 * len(title)) + 14, 18, text=title)


# ---- 4 组边线框+签(坐标含既有元素全集,留 8px 内边距) ----
frame(32, 52, 620, 396, u"RECORDS")            # 表头60+10行(90..362)+说明378+翻页410..444
frame(32, 464, 620, 190, u"SUMMARY")           # 标题472+5行(506..642)
frame(642, 52, 598, 336, u"QUERY")             # 查询行60+结果(104..380)
frame(642, 400, 598, 148, u"MODEL PARAMS")     # 标题400+调参(434..524)
log(u"FRAMES_OK 4 groups")

# ---- 表头底纹(5 个表头框绑 dwHeaderBg) ----
n_hdr = 0
for t in [u"Goods ID", u"Column X", u"Tier Y", u"Path / m", u"Travel / s"]:
    el = one(t)
    if el is not None:
        el.set_property("Color variables.Normal state.Fill color",
                        "GVL_Visu.dwHeaderBg")
        n_hdr += 1
log(u"HEADER_BG=%d (expect 5)" % n_hdr)

# ---- 说明行改字(治 "Total goods=1" 流程困惑) ----
note = one(u"Paged aGoods records. Business ID is not the array index.")
if note is not None:
    note.set_property(
        "Texts.Text",
        u"Paged aGoods records. Run batch assign on P1 first, then view here.")
    log(u"NOTE_TEXT_OK")
else:
    log(u"NOTE_TEXT missing (skip)")

# ---- Lamp 红色图像属性路径探针(P2 Found 灯;通则 P1 两灯下轮同法) ----
lamp = None
for i in range(len(vel)):
    el = vel[i]
    try:
        if (el.get_property("Position.X") == 1080
                and el.get_property("Position.Y") == 60):
            lamp = el
            break
    except Exception:
        continue
if lamp is None:
    log(u"LAMP not found at (1080,60)")
else:
    for path, val in [("Image settings.Image", "Red"),
                      ("Image settings.Image", "red"),
                      ("Image", "Red"), ("Lamp image", "Red"),
                      ("Image settings.Lamp", "Red")]:
        try:
            lamp.set_property(path, val)
            log(u"LAMP_SET_OK %s=%s" % (path, val))
            break
        except Exception as e:
            log(u"LAMP_TRY %s FAIL %r" % (path, e))

visu.end_modify()
project.save()
log(u"SAVE_OK total=%d" % len(vel))
project.close()
log(u"=== RELAYOUT_P2_DONE ===")
out.close()
