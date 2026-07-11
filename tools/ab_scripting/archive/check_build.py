# -*- coding: utf-8 -*-
# check_build.py — 打开工程→build→dump 全部消息(定位 2 errors 的具体内容)
import io

RES = r"F:\abb_wh_work\tools\ab_scripting\check_result.txt"
PROJ = r"F:\abb_wh_work\plc\AB_Project\ABB_WH.project"

f = io.open(RES, "w", encoding="utf-8")
def log(*a):
    line = u" ".join([unicode(x) if not isinstance(x, str) else x for x in a]) \
        if False else " ".join([str(x) for x in a])
    f.write(line + u"\n"); f.flush()
    try:
        print(line)
    except Exception:
        pass

proj = projects.open(PROJ)                       # noqa: F821
log("OPEN_OK")
app = proj.active_application
app.build()
log("BUILD_CALLED")

try:
    cats = system.get_message_categories()       # noqa: F821
    log("categories:", len(cats))
    for c in cats:
        try:
            msgs = system.get_messages(c)        # noqa: F821
        except Exception as e:
            continue
        if not msgs:
            continue
        log("--- category", c, "msgs:", len(msgs))
        for m in msgs:
            try:
                sev = getattr(m, "severity", "?")
            except Exception:
                sev = "?"
            try:
                pos = getattr(m, "position_text", "")
            except Exception:
                pos = ""
            log("  [%s] %s | %s" % (sev, str(m)[:300], pos))
except Exception as e:
    log("MSG_DUMP_FAIL:", repr(e))

proj.close()
log("=== CHECK_DONE ===")
f.close()
