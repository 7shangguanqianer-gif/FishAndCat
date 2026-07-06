# -*- coding: utf-8 -*-
# lang_probe.py — 对比手工建 POU(FB_Stats)与脚本建 POU(FB_VisuRefresh)的实现语言
import io

RES = r"F:\abb_wh_work\tools\ab_scripting\lang_result.txt"
PROJ = r"F:\abb_wh_work\plc\AB_Project\ABB_WH.project"

f = io.open(RES, "w", encoding="utf-8")
def log(s):
    f.write(s + u"\n"); f.flush()

proj = projects.open(PROJ)                    # noqa: F821
for name in ["FB_Stats", "FB_VisuRefresh", "FC_StateToColor", "FC_CapCoef"]:
    hits = proj.find(name, True)
    if not hits:
        log(u"%s NOT FOUND" % name)
        continue
    obj = hits[0]
    attrs = [a for a in dir(obj) if ("lang" in a.lower() or "impl" in a.lower())]
    log(u"%s: lang/impl attrs=%s" % (name, attrs))
    for a in attrs:
        try:
            v = getattr(obj, a)
            if callable(v):
                try:
                    v = v()
                except Exception:
                    v = "<callable>"
            log(u"   %s = %s" % (a, v))
        except Exception as e:
            log(u"   %s -> err %r" % (a, e))
proj.close()
log(u"=== LANG_DONE ===")
f.close()
