# -*- coding: utf-8 -*-
import io

RESULT = r"F:\abb_wh_spike\visu_native_20260710_1225\build_messages.txt"
PROJECT = r"F:\abb_wh_spike\visu_native_20260710_1225\AB_Project\ABB_WH.project"
out = io.open(RESULT, "w", encoding="utf-8")


def log(value):
    out.write(unicode(value) + u"\n")
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
    log(u"CATEGORY %s count=%d" % (category, len(messages)))
    for message in messages:
        severity = getattr(message, "severity", u"?")
        position = getattr(message, "position_text", u"")
        log(u"[%s] %s | %s" % (severity, unicode(message), position))
project.close()
out.close()
