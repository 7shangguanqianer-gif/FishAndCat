# -*- coding: utf-8 -*-
import io

PROJECT = r"F:\abb_wh_spike\visu_native_20260710_1225\AB_Project\ABB_WH.project"
RESULT = r"F:\abb_wh_spike\visu_native_20260710_1225\probe_visuelem_api_result.txt"

out = io.open(RESULT, "w", encoding="utf-8")


def log(text):
    out.write(unicode(text) + u"\n")
    out.flush()


def public_names(value):
    try:
        return [name for name in dir(value) if not name.startswith("_")]
    except Exception as exc:
        return [u"<dir failed: %r>" % exc]


project = projects.open(PROJECT)  # noqa: F821
visu_hits = project.find("VisuMain", True)
visu = visu_hits[0] if visu_hits else None

log(u"project opened: %r" % (project is not None))
log(u"VisuMain found: %r" % (visu is not None))

for name in ["visuelemrepository", "visuelemsigning", "VisualElementType"]:
    try:
        value = globals()[name]
        log(u"===== %s =====" % name)
        log(u"type: %s" % type(value).__name__)
        log(u"dir: %s" % u", ".join(public_names(value)))
        try:
            log(u"repr: %r" % value)
        except Exception:
            pass
    except Exception as exc:
        log(u"%s unavailable: %r" % (name, exc))

if visu is not None:
    log(u"===== VisuMain =====")
    log(u"type: %s" % type(visu).__name__)
    log(u"dir: %s" % u", ".join(public_names(visu)))
    try:
        log(u"embedded types: %r" % visu.embedded_object_types)
    except Exception as exc:
        log(u"embedded types failed: %r" % exc)

try:
    log(u"===== visu-related commands =====")
    for command in system.commands:  # noqa: F821
        text = u"%s %s" % (getattr(command, "name", u""),
                            getattr(command, "description", u""))
        if u"visu" in text.lower() or u"visual" in text.lower():
            log(text)
except Exception as exc:
    log(u"command scan failed: %r" % exc)

project.close()
out.close()
