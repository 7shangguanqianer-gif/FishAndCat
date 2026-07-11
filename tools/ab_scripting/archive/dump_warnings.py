# -*- coding: utf-8 -*-
# dump_warnings.py — 一次性:导出编译消息全文(查 0711 的 "1 warnings" 明细)
import io

RES = r"F:\abb_wh_work\tools\ab_scripting\warnings_result.txt"
PROJ = r"F:\abb_wh_work\plc\AB_Project\ABB_WH.project"

f = io.open(RES, "w", encoding="utf-8")
def log(s):
    try:
        f.write(s + u"\n")
    except Exception:
        f.write(repr(s) + u"\n")
    f.flush()

proj = projects.open(PROJ)                                   # noqa: F821
log(u"OPEN_OK")
app = proj.active_application
app.build()
for c in system.get_message_categories():                    # noqa: F821
    try:
        msgs = system.get_messages(c)                        # noqa: F821
    except Exception:
        continue
    for m in msgs:
        s = str(m)
        low = s.lower()
        if ("warn" in low or s.startswith("Compile complete")
                or "C0" in s or "SA" in s[:8]):
            log(u"MSG: %s" % s)
proj.close()
log(u"=== DUMP_DONE ===")
