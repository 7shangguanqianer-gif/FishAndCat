# -*- coding: utf-8 -*-
# dump_errors.py -- E7 编译错误探针:build 后不过滤 dump 全部消息(IronPython 2.7)
import io
import os

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "dump_errors_result.txt")
lines = []


def log(*parts):
    s = u" ".join([unicode(p) for p in parts])
    lines.append(s)


proj = projects.open(r"F:\abb_wh_work\plc\AB_Project\ABB_WH.project")  # noqa: F821
app = proj.active_application
app.build()
try:
    cats = system.get_message_categories()  # noqa: F821
    for c in cats:
        try:
            msgs = system.get_messages(c)  # noqa: F821
        except Exception:
            continue
        for m in msgs:
            try:
                sev = str(m.severity)
            except Exception:
                sev = "?"
            log(u"MSG[%s]:" % sev, unicode(m))
except Exception as e:
    log("scan fail", repr(e))
proj.close()
log("DONE")
fp = io.open(OUT, "w", encoding="utf-8")
fp.write(u"\n".join(lines))
fp.close()
