# -*- coding: utf-8 -*-
# bisect_probe.py — 二分定位:极简 ST 灌入脚本建的两个 POU→build→数错误。不 save。
# 同时 dump 全局命名空间与 PouType,找语言枚举线索。
import io

RES = r"F:\abb_wh_work\tools\ab_scripting\bisect_result.txt"
PROJ = r"F:\abb_wh_work\plc\AB_Project\ABB_WH.project"

f = io.open(RES, "w", encoding="utf-8")
def log(s):
    try:
        f.write(s + u"\n")
    except Exception:
        f.write(repr(s) + u"\n")
    f.flush()

def count_errors():
    n = None
    for c in system.get_message_categories():          # noqa: F821
        try:
            msgs = system.get_messages(c)              # noqa: F821
        except Exception:
            continue
        for m in msgs:
            s = str(m)
            if s.startswith("Compile complete"):
                n = s
    return n

proj = projects.open(PROJ)                             # noqa: F821
app = proj.active_application

# 基线
app.build()
log(u"BASELINE: %s" % count_errors())

# 极简替换(不保存)
for name in ["FB_VisuRefresh", "FC_StateToColor"]:
    hits = proj.find(name, True)
    if hits:
        hits[0].textual_implementation.replace(u"GVL_Visu.VisuAlarm := GVL_Visu.VisuAlarm;")
        log(u"minimal impl -> %s" % name)
app.build()
log(u"AFTER_MINIMAL: %s" % count_errors())

# 语言枚举线索
try:
    log(u"PouType dir: %s" % ", ".join([a for a in dir(PouType)]))   # noqa: F821
except Exception as e:
    log(u"PouType dump err %r" % e)
g = list(globals().keys())
log(u"globals: %s" % ", ".join(sorted(g)))

proj.close()                                            # 不 save,工程磁盘版保持原样
log(u"=== BISECT_DONE ===")
f.close()
