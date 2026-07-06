# -*- coding: utf-8 -*-
# dump_pou.py — 读回 FB_VisuRefresh 在 AB 内的 decl/impl 文本(repr 级,看换行/不可见字符)
import io

RES = r"F:\abb_wh_work\tools\ab_scripting\dump_result.txt"
PROJ = r"F:\abb_wh_work\plc\AB_Project\ABB_WH.project"

f = io.open(RES, "w", encoding="utf-8")
def log(s):
    f.write(s + u"\n"); f.flush()

proj = projects.open(PROJ)                    # noqa: F821
for name in ["FB_VisuRefresh", "FC_StateToColor"]:
    hits = proj.find(name, True)
    if not hits:
        log(u"%s: NOT FOUND" % name)
        continue
    obj = hits[0]
    for attr in ["textual_declaration", "textual_implementation"]:
        doc = getattr(obj, attr, None)
        if doc is None:
            continue
        try:
            t = doc.text
        except Exception as e:
            log(u"%s.%s: text read fail %r" % (name, attr, e))
            continue
        log(u"===== %s.%s len=%d =====" % (name, attr, len(t)))
        log(u"--repr first 400--")
        log(repr(t[:400]))
        log(u"--repr last 200--")
        log(repr(t[-200:]))
proj.close()
log(u"=== DUMP_DONE ===")
f.close()
