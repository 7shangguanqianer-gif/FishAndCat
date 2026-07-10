# -*- coding: utf-8 -*-
import io

PROJECT = r"F:\abb_wh_spike\visu_native_20260710_1225\AB_Project\ABB_WH.project"
RESULT = r"F:\abb_wh_spike\visu_native_20260710_1225\probe_visu_commands_result.txt"

out = io.open(RESULT, "w", encoding="utf-8")


def log(value):
    out.write(unicode(value) + u"\n")
    out.flush()


def public_names(value):
    return [name for name in dir(value) if not name.startswith("_")]


project = projects.open(PROJECT)  # noqa: F821
log(u"===== system =====")
log(u", ".join(public_names(system)))  # noqa: F821
log(u"===== matching commands =====")

for command in system.commands:  # noqa: F821
    name = getattr(command, "name", u"")
    description = getattr(command, "description", u"")
    combined = u"%s %s" % (name, description)
    if (u"visual element" in combined.lower()
            or u"visualization element" in combined.lower()
            or u"multiply" in combined.lower()):
        log(u"---")
        log(u"name=%r" % name)
        log(u"description=%r" % description)
        log(u"guid=%r" % getattr(command, "guid", None))
        log(u"tokens=%r" % getattr(command, "tokens", None))
        log(u"dir=%s" % u", ".join(public_names(command)))

log(u"===== VisualElementType values =====")
for value in VisualElementType.GetValues(VisualElementType):  # noqa: F821
    log(u"%s=%s" % (value, int(value)))

project.close()
out.close()
