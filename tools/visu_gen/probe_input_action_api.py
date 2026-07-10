# -*- coding: utf-8 -*-
import io

PROJECT = r"F:\abb_wh_spike\visu_native_20260710_1225\AB_Project\ABB_WH.project"
RESULT = r"F:\abb_wh_spike\visu_native_20260710_1225\probe_input_action_api_result.txt"

out = io.open(RESULT, "w", encoding="utf-8")


def log(value):
    out.write(unicode(value) + u"\n")
    out.flush()


def inspect_attr(label, obj, name):
    try:
        value = getattr(obj, name)
        log(u"%s.%s PRESENT type=%s repr=%r" % (
            label, name, type(value).__name__, value))
        return value
    except Exception as exc:
        log(u"%s.%s MISSING %r" % (label, name, exc))
        return None


project = projects.open(PROJECT)  # noqa: F821
visu = project.find("VisuMain", True)[0]
element = visu.visual_element_list[0]

factory = inspect_attr("visu", visu, "input_action_factory")
if factory is not None:
    log(u"factory dir=%s" % u", ".join(
        [name for name in dir(factory) if not name.startswith("_")]))

for name in ["add_input_action", "remove_input_action", "set_property",
             "get_property", "id"]:
    inspect_attr("element", element, name)

log(u"element dir=%s" % u", ".join(
    [name for name in dir(element) if not name.startswith("_")]))

project.close()
out.close()
