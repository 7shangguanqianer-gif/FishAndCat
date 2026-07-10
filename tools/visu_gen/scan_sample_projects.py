# -*- coding: utf-8 -*-
import io

RESULT = r"F:\abb_wh_spike\visu_native_20260710_1225\sample_project_scan.txt"
SAMPLES = [
    r"F:\abb_wh_spike\visu_native_20260710_1225\AlarmTableExample.project",
]

out = io.open(RESULT, "w", encoding="utf-8")


def log(value):
    out.write(unicode(value) + u"\n")
    out.flush()


for path in SAMPLES:
    log(u"=== %s ===" % path)
    try:
        project = projects.open(path)  # noqa: F821
    except Exception as exc:
        log(u"OPEN_FAIL %r" % exc)
        continue
    try:
        for obj in project.get_children(True):
            try:
                name = obj.get_name()
            except Exception:
                name = u"?"
            flags = []
            for flag in ["is_visualobject", "is_application", "is_folder"]:
                try:
                    if getattr(obj, flag):
                        flags.append(flag)
                except Exception:
                    pass
            type_text = unicode(getattr(obj, "type", u"?"))
            if (u"alarm" in unicode(name).lower() or u"visu" in unicode(name).lower()
                    or u"alarm" in type_text.lower() or flags):
                log(u"OBJ name=%s type=%s flags=%s" %
                    (name, type_text, u",".join(flags)))
                if "is_visualobject" in flags:
                    try:
                        log(u"  VISU_COUNT=%d" % len(obj.visual_element_list))
                    except Exception as exc:
                        log(u"  VISU_COUNT_FAIL %r" % exc)
    finally:
        project.close()
        log(u"CLOSED")

out.close()
