# -*- coding: utf-8 -*-
# dump_errors.py — 一次性:导出编译错误全文(0711 C1/C2/C6 43 errors 排障)
import io

RESULT = r"F:\abb_wh_work\tools\ab_scripting\errors_result.txt"
PROJECT = r"F:\abb_wh_work\plc\AB_Project\ABB_WH.project"
out = io.open(RESULT, "w", encoding="utf-8")


def log(value):
    out.write(unicode(value) + u"\n")  # noqa: F821
    out.flush()


project = projects.open(PROJECT)  # noqa: F821
app = project.active_application
app.build()
for category in system.get_message_categories():  # noqa: F821
    try:
        messages = system.get_messages(category)  # noqa: F821
    except Exception:
        continue
    if not messages:
        continue
    for message in messages:
        severity = unicode(getattr(message, "severity", u"?"))  # noqa: F821
        text = unicode(message)  # noqa: F821
        if text.startswith(u"Compile complete") or u"----" in text[:8]:
            log(u"[%s] %s" % (severity, text))
            continue
        position = getattr(message, "position_text", u"")
        log(u"[%s] %s | %s" % (severity, text, position))
project.close()
log(u"=== ERRDUMP_DONE ===")
