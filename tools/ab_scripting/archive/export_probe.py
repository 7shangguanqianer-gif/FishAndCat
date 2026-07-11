# -*- coding: utf-8 -*-
# export_probe.py — 导出好/坏两个 POU 的 native XML 供本地 diff
import io

RES = r"F:\abb_wh_work\tools\ab_scripting\export_result.txt"
PROJ = r"F:\abb_wh_work\plc\AB_Project\ABB_WH.project"
OUT = r"F:\abb_wh_work\tools\ab_scripting"

f = io.open(RES, "w", encoding="utf-8")
def log(s):
    try:
        f.write(s + u"\n")
    except Exception:
        f.write(repr(s) + u"\n")
    f.flush()

proj = projects.open(PROJ)                     # noqa: F821
for name in ["FB_Stats", "FB_VisuRefresh"]:
    hits = proj.find(name, True)
    if not hits:
        log(u"%s NOT FOUND" % name)
        continue
    dest = OUT + u"\\" + name + u".export.xml"
    try:
        proj.export_native(hits[0], dest)
        log(u"EXPORTED %s -> %s" % (name, dest))
    except Exception as e:
        log(u"export_native(obj, path) fail: %r" % (e,))
        try:
            proj.export_native([hits[0]], dest)
            log(u"EXPORTED(list) %s" % name)
        except Exception as e2:
            log(u"export_native([obj], path) fail: %r" % (e2,))
proj.close()
log(u"=== EXPORT_DONE ===")
f.close()
