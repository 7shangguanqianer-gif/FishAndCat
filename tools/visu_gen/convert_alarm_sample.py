# -*- coding: utf-8 -*-
import io

SOURCE = r"F:\abb_wh_spike\visu_native_20260710_1225\AlarmTableExample.project"
OUTPUT = r"F:\abb_wh_spike\visu_native_20260710_1225\AlarmTableExample_AB29.project"
RESULT = r"F:\abb_wh_spike\visu_native_20260710_1225\convert_alarm_sample_result.txt"
out = io.open(RESULT, "w", encoding="utf-8")


def log(value):
    out.write(unicode(value) + u"\n")
    out.flush()


log(u"START")
try:
    project = projects.convert(SOURCE, OUTPUT, None, True)  # noqa: F821
    log(u"CONVERT_OK path=%s" % project.path)
    project.save()
    project.close()
    log(u"SAVE_CLOSE_OK")
except Exception as exc:
    log(u"CONVERT_FAIL %r" % exc)
log(u"DONE")
out.close()
