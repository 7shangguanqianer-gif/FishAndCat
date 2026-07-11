# -*- coding: utf-8 -*-
# audit_pages.py -- P1(VisuMain)+P2(VisuStats) 全元素几何审计探针(0711,只读零风险)
# 输出 TSV:PAGE/IDX/TYPE/NAME/X/Y/W/H/TEXT,供外部 Python 分析重叠/越界/文字宽度预算。
# 红线:纯 dump,不 set 任何属性,不 save。
import io

RES = r"F:\abb_wh_work\tools\ab_scripting\audit_pages_result.txt"
PROJ = r"F:\abb_wh_work\plc\AB_Project\ABB_WH.project"

f = io.open(RES, "w", encoding="utf-8")


def log(s):
    f.write(s + u"\n")
    f.flush()


def clean(v):
    if v is None:
        return u""
    try:
        s = unicode(v)  # noqa: F821
    except Exception:
        s = u"<?>"
    return s.replace(u"\t", u" ").replace(u"\r", u" ").replace(u"\n", u" ")


proj = projects.open(PROJ)  # noqa: F821

log(u"PAGE\tIDX\tTYPE\tNAME\tX\tY\tW\tH\tTEXT")
for page, objname in [(u"MAIN", "VisuMain"), (u"STATS", "VisuStats")]:
    hits = proj.find(objname, True)
    if not hits:
        log(u"%s\t-\tNOT_FOUND\t\t\t\t\t\t" % page)
        continue
    vel = hits[0].visual_element_list
    for i in range(len(vel)):
        el = vel[i]
        row = [page, unicode(i)]  # noqa: F821
        row.append(clean(type(el).__name__))
        nm = u""
        for path in ["Element name", "Name"]:
            try:
                nm = clean(el.get_property(path))
                if nm:
                    break
            except Exception:
                pass
        row.append(nm)
        for path in ["Position.X", "Position.Y",
                     "Position.Width", "Position.Height"]:
            try:
                row.append(clean(el.get_property(path)))
            except Exception:
                row.append(u"")
        try:
            row.append(clean(el.get_property("Texts.Text")))
        except Exception:
            row.append(u"")
        log(u"\t".join(row))

proj.close()
log(u"=== AUDIT_PAGES_DONE ===")
f.close()
