# -*- coding: utf-8 -*-
# probe_warn.py — 扫工程编译消息,打印 warning/error 具体内容(AB 内 --runscript)
import io
RES = r"F:\abb_wh_work\tools\ab_scripting\probe_warn_result.txt"
_f = io.open(RES, "w", encoding="utf-8")
def log(*a):
    try:
        _f.write(u" ".join([unicode(x) for x in a]) + u"\n"); _f.flush()
    except Exception:
        pass
proj = projects.open(r"F:\abb_wh_work\plc\AB_Project\ABB_WH.project")
app = proj.find("Application", True)[0]
try:
    app.build(); log("BUILD_CALLED")
except Exception as e:
    log("build fail:", repr(e))
try:
    cats = system.get_message_categories()
    for c in cats:
        try:
            msgs = system.get_messages(c)
        except Exception:
            continue
        for m in msgs:
            s = str(m)
            low = s.lower()
            if "warning" in low or "error" in low:
                log("MSG:", s[:300])
except Exception as e:
    log("msg scan fail:", repr(e))
proj.close(); log("=== PROBE_WARN_DONE ===")
_f.close()
