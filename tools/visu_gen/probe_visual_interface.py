# -*- coding: utf-8 -*-
import io

PROJECT = r"F:\abb_wh_spike\visu_native_20260710_1225\AB_Project\ABB_WH.project"
RESULT = r"F:\abb_wh_spike\visu_native_20260710_1225\probe_visual_interface_result.txt"

out = io.open(RESULT, "w", encoding="utf-8")


def log(value):
    out.write(unicode(value) + u"\n")
    out.flush()


project = projects.open(PROJECT)  # noqa: F821
app = project.active_application
visu = project.find("VisuMain", True)[0]

for label, obj, names in [
        ("app", app, ["create_visualobject", "create_visualization"]),
        ("visu", visu, ["is_visualobject", "visual_element_list",
                        "begin_modify", "end_modify"]),
]:
    log(u"===== %s =====" % label)
    for name in names:
        try:
            value = getattr(obj, name)
            log(u"%s: PRESENT type=%s repr=%r" % (
                name, type(value).__name__, value))
            if name == "visual_element_list":
                try:
                    log(u"  count=%d" % len(value))
                    log(u"  dir=%s" % u", ".join(
                        [n for n in dir(value) if not n.startswith("_")]))
                except Exception as exc:
                    log(u"  inspect failed: %r" % exc)
        except Exception as exc:
            log(u"%s: MISSING %r" % (name, exc))

project.close()
out.close()
