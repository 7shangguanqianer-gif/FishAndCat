# -*- coding: utf-8 -*-
import io

PROJECT = r"F:\abb_wh_spike\visu_native_20260710_1225\AB_Project\ABB_WH.project"
RESULT = r"F:\abb_wh_spike\visu_native_20260710_1225\probe_project_settings_reflection_result.txt"
out = io.open(RESULT, "w", encoding="utf-8")


def log(value):
    out.write(unicode(value) + u"\n")
    out.flush()


project = projects.open(PROJECT)  # noqa: F821
settings = project.project_settings
for label, obj in [(u"project", project), (u"settings", settings)]:
    log(u"=== %s ===" % label)
    log(u"DIR %s" % u", ".join(sorted([unicode(x) for x in dir(obj)])))
    try:
        typ = obj.GetType()
        log(u"TYPE %s" % typ.FullName)
        log(u"INTERFACES")
        for iface in typ.GetInterfaces():
            log(u"  %s" % iface.FullName)
        log(u"PROPERTIES")
        for prop in typ.GetProperties():
            log(u"  %s : %s canread=%s canwrite=%s" %
                (prop.Name, prop.PropertyType.FullName, prop.CanRead, prop.CanWrite))
        log(u"METHODS")
        for method in typ.GetMethods():
            name = unicode(method.Name)
            low = name.lower()
            if (u"utf" in low or u"encod" in low or u"compil" in low
                    or u"option" in low or u"setting" in low or u"project" in low):
                log(u"  %s" % unicode(method))
    except Exception as exc:
        log(u"REFLECTION_FAIL %r" % exc)
project.close()
log(u"DONE")
out.close()
