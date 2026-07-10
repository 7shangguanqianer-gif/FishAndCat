# -*- coding: utf-8 -*-
import io

RESULT = r"F:\abb_wh_spike\visu_native_20260710_1225\scan_alarm_sample_simple.txt"
PROJECT = r"F:\abb_wh_spike\visu_native_20260710_1225\AlarmTableExample.project"
out = io.open(RESULT, "w", encoding="utf-8")


def log(value):
    out.write(unicode(value) + u"\n")
    out.flush()


log(u"START")
try:
    flags = VersionUpdateFlags.SilentMode | VersionUpdateFlags.UpdateAll  # noqa: F821
    project = projects.open(PROJECT, update_flags=flags)  # noqa: F821
except Exception as exc:
    log(u"OPEN_FAIL %r" % exc)
    out.close()
    raise SystemExit
log(u"OPEN_OK")
for term in [u"Alarm", u"Alarm Configuration", u"Application", u"Visualization", u"Visu", u"PLC_PRG"]:
    try:
        hits = project.find(term, True)
        log(u"FIND %s count=%d" % (term, len(hits)))
        for obj in hits:
            log(u"  %s type=%s visu=%s" % (
                obj.get_name(), unicode(getattr(obj, "type", u"?")),
                unicode(getattr(obj, "is_visualobject", False))))
    except Exception as exc:
        log(u"FIND_FAIL %s %r" % (term, exc))
project.close()
log(u"DONE")
out.close()
