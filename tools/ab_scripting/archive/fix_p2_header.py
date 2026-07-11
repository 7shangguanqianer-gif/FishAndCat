# -*- coding: utf-8 -*-
# fix_p2_header.py -- P2 RECORDS 表头行修复(0711 深夜;方案B=删重建 RELATIVE,AI 代拍板可翻案)
# 病理:Codex 生成器原生表头(VISU_ST_STYLE 系)绑 Color variables 后整行不渲染(层3变体;
#       官方文档另证 alpha 前缀不匹配也会隐身,但 FF 在 400 格 RELATIVE 重建件上已实证有效)。
# 修法:与 400 格病理同构——删 5 表头重建(add_element 默认 RELATIVE)+Fill 绑 dwHeaderBg+文字回填。
# 红线:y=60 坐标谓词锁定,防误删 QUERY 区同名 'Path / m'/'Travel / s'(y=272/300)。
import io

PROJECT = r"F:\abb_wh_work\plc\AB_Project\ABB_WH.project"
RESULT = r"F:\abb_wh_work\tools\ab_scripting\fix_p2_header_result.txt"

HEADERS = [  # (x, y, w, h, text) -- audit_pages 0711 实测五元组
    (40, 60, 90, 26, u"Goods ID"),
    (150, 60, 90, 26, u"Column X"),
    (260, 60, 90, 26, u"Tier Y"),
    (370, 60, 110, 26, u"Path / m"),
    (500, 60, 110, 26, u"Travel / s"),
]

out = io.open(RESULT, "w", encoding="utf-8")


def log(v):
    out.write(unicode(v) + u"\n")
    out.flush()


project = projects.open(PROJECT)  # noqa: F821
visu = project.find("VisuStats", True)[0]
vel = visu.visual_element_list
visu.begin_modify()

# ---- 1) y=60 谓词定位并删除旧表头 ----
n_removed = 0
for x, y, w, h, txt in HEADERS:
    victim = None
    for i in range(len(vel)):
        el = vel[i]
        try:
            if (el.get_property("Position.X") == x
                    and el.get_property("Position.Y") == y
                    and el.get_property("Position.Width") == w
                    and el.get_property("Position.Height") == h):
                victim = el
                break
        except Exception:
            continue
    if victim is None:
        log(u"MISS old header at (%d,%d) %r" % (x, y, txt))
        continue
    vel.remove_id(victim.id)
    n_removed += 1
log(u"REMOVED=%d (expect 5)" % n_removed)

# ---- 2) 重建 RELATIVE 表头(几何/文字同旧,Fill 绑 dwHeaderBg) ----
n_built = 0
for x, y, w, h, txt in HEADERS:
    el = vel.add_element(VisualElementType.Rectangle)  # noqa: F821
    el.set_property("Position.X", x)
    el.set_property("Position.Y", y)
    el.set_property("Position.Width", w)
    el.set_property("Position.Height", h)
    el.set_property("Texts.Text", txt)
    el.set_property("Color variables.Normal state.Fill color",
                    "GVL_Visu.dwHeaderBg")
    n_built += 1
log(u"REBUILT=%d (expect 5)" % n_built)

visu.end_modify()
project.save()
log(u"SAVE_OK total=%d" % len(vel))
project.close()
log(u"=== FIX_P2_HEADER_DONE ===")
out.close()
