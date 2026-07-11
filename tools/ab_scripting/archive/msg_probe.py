# -*- coding: utf-8 -*-
# msg_probe.py — build 后 dump 错误消息对象全属性(定位错误宿主对象)+ POU 全成员表
import io

RES = r"F:\abb_wh_work\tools\ab_scripting\msg_result.txt"
PROJ = r"F:\abb_wh_work\plc\AB_Project\ABB_WH.project"

f = io.open(RES, "w", encoding="utf-8")
def log(s):
    try:
        f.write(s + u"\n")
    except Exception:
        f.write(repr(s) + u"\n")
    f.flush()

proj = projects.open(PROJ)                    # noqa: F821
app = proj.active_application
app.build()
log(u"BUILD_CALLED")

cats = system.get_message_categories()        # noqa: F821
shown = 0
for c in cats:
    try:
        msgs = system.get_messages(c)         # noqa: F821
    except Exception:
        continue
    for m in msgs:
        s = str(m)
        if ("expected" in s or "Unexpected" in s) and shown < 3:
            shown += 1
            log(u"=== MSG %d: %s" % (shown, s[:120]))
            for a in dir(m):
                if a.startswith("_"):
                    continue
                try:
                    v = getattr(m, a)
                    if callable(v):
                        continue
                    log(u"   .%s = %s" % (a, str(v)[:160]))
                except Exception as e:
                    log(u"   .%s -> %r" % (a, e))

log(u"--- FB_VisuRefresh full dir ---")
hits = proj.find("FB_VisuRefresh", True)
if hits:
    obj = hits[0]
    log(u" ".join([a for a in dir(obj) if not a.startswith("_")]))
proj.close()
log(u"=== MSG_DONE ===")
f.close()
