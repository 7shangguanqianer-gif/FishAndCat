# -*- coding: utf-8 -*-
# fix_p2_polish.py -- 0711 审计三小修(audit_pages 全面排查的产出)
# ①P2 表头补 2 底纹:'Path / m'(370,60) 'Travel / s'(500,60) 文本重名致 relayout_p2 漏网,按坐标定位
# ②P2 MODEL PARAMS 叠压:标题行(650,400,570,26)被组签(650,391)压 9px
#    → 改短文本 "(press Query again after editing)" 并移到签右侧同水平带 (754,391,466,18)
# ③P1 徽章踩线:48字×6.5=312px > 304px → 缩为 "Tests 45/45 | ..."(45字=292px)
# 红线:三处均为文本/装饰元素,与一切动作元素零接触。
import io

PROJECT = r"F:\abb_wh_work\plc\AB_Project\ABB_WH.project"
RESULT = r"F:\abb_wh_work\tools\ab_scripting\fix_p2_polish_result.txt"

out = io.open(RESULT, "w", encoding="utf-8")


def log(v):
    out.write(unicode(v) + u"\n")
    out.flush()


project = projects.open(PROJECT)  # noqa: F821


def by_pos(visu, x, y, w, h):
    vel = visu.visual_element_list
    for i in range(len(vel)):
        el = vel[i]
        try:
            if (el.get_property("Position.X") == x
                    and el.get_property("Position.Y") == y
                    and el.get_property("Position.Width") == w
                    and el.get_property("Position.Height") == h):
                return el
        except Exception:
            continue
    return None


# ---- P2 两修 ----
p2 = project.find("VisuStats", True)[0]
p2.begin_modify()

n = 0
for x, y, w, h in [(370, 60, 110, 26), (500, 60, 110, 26)]:
    el = by_pos(p2, x, y, w, h)
    if el is not None:
        el.set_property("Color variables.Normal state.Fill color",
                        "GVL_Visu.dwHeaderBg")
        n += 1
log(u"HEADER_BG_ADDED=%d (expect 2, total now 5)" % n)

title = by_pos(p2, 650, 400, 570, 26)
if title is not None:
    title.set_property("Texts.Text", u"(press Query again after editing)")
    title.set_property("Position.X", 754)
    title.set_property("Position.Y", 391)
    title.set_property("Position.Width", 466)
    title.set_property("Position.Height", 18)
    log(u"MODELPARAMS_TITLE_OK -> (754,391,466,18)")
else:
    log(u"MODELPARAMS_TITLE missing (skip)")

p2.end_modify()

# ---- P1 一修 ----
p1 = project.find("VisuMain", True)[0]
p1.begin_modify()
badge = by_pos(p1, 936, 652, 304, 18)
if badge is not None:
    badge.set_property("Texts.Text",
                       u"Tests 45/45 | sim-ST cross-check | dwell=I/O")
    log(u"BADGE_OK 45 chars = 292px < 304px")
else:
    log(u"BADGE missing (skip)")
p1.end_modify()

project.save()
log(u"SAVE_OK")
project.close()
log(u"=== FIX_P2_POLISH_DONE ===")
out.close()
