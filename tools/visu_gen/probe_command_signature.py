# -*- coding: utf-8 -*-
import io

PROJECT = r"F:\abb_wh_spike\visu_native_20260710_1225\AB_Project\ABB_WH.project"
RESULT = r"F:\abb_wh_spike\visu_native_20260710_1225\probe_command_signature_result.txt"

out = io.open(RESULT, "w", encoding="utf-8")


def log(value):
    out.write(unicode(value) + u"\n")
    out.flush()


project = projects.open(PROJECT)  # noqa: F821
for command in system.commands:  # noqa: F821
    if getattr(command, "name", u"") != u"Add Visual Element":
        continue
    log(u"type=%r" % command.GetType())
    log(u"execute_repr=%r" % command.execute)
    try:
        log(u"execute_doc=%r" % command.execute.__doc__)
    except Exception as exc:
        log(u"doc failed: %r" % exc)
    for method in command.GetType().GetMethods():
        if u"execute" not in method.Name.lower():
            continue
        log(u"method=%s" % method)
        for parameter in method.GetParameters():
            log(u"  parameter=%s type=%s optional=%s default=%r" % (
                parameter.Name,
                parameter.ParameterType.FullName,
                parameter.IsOptional,
                parameter.DefaultValue))
        log(u"  return=%s" % method.ReturnType.FullName)
project.close()
out.close()
