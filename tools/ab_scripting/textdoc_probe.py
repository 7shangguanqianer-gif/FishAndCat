# -*- coding: utf-8 -*-
# textdoc_probe.py — dump ScriptTextDocument 成员表 + 行为实验:多行 replace 后 length/行数
import io

RES = r"F:\abb_wh_work\tools\ab_scripting\textdoc_result.txt"
PROJ = r"F:\abb_wh_work\plc\AB_Project\ABB_WH.project"

f = io.open(RES, "w", encoding="utf-8")
def log(s):
    try:
        f.write(s + u"\n")
    except Exception:
        f.write(repr(s) + u"\n")
    f.flush()

proj = projects.open(PROJ)                             # noqa: F821
hits = proj.find("FB_VisuRefresh", True)
obj = hits[0]
ti = obj.textual_implementation

log(u"--- dir(textual_implementation) ---")
members = [a for a in dir(ti)]
log(u", ".join(members))

for a in ["length", "linecount", "line_count", "text"]:
    try:
        v = getattr(ti, a)
        log(u"%s = %s" % (a, str(v)[:120]))
    except Exception as e:
        log(u"%s -> %r" % (a, e))

# 行为实验:三行文本 replace 后,再读 linecount(不 save)
test = u"GVL_Visu.VisuAlarm := FALSE;\nGVL_Visu.VisuAlarm := FALSE;\nGVL_Visu.VisuAlarm := FALSE;"
ti.replace(test)
log(u"after 3-line replace:")
for a in ["length", "linecount", "line_count"]:
    try:
        log(u"  %s = %s" % (a, str(getattr(ti, a))))
    except Exception as e:
        pass
try:
    t = ti.text
    log(u"  text repr: %s" % repr(t)[:200])
except Exception as e:
    log(u"  text read err %r" % e)

proj.close()                                            # 不 save
log(u"=== TEXTDOC_DONE ===")
f.close()
