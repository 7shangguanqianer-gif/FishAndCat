# -*- coding: utf-8 -*-
import io

PROJECT = r"F:\abb_wh_spike\visu_native_20260710_1225\AB_Project\ABB_WH.project"
RESULT = r"F:\abb_wh_spike\visu_native_20260710_1225\script_api_binding_smoke_result.txt"
EXPORT = r"F:\abb_wh_spike\visu_native_20260710_1225\VisuBindingSpike.xml"
VISU_NAME = "VisuBindingSpike"

out = io.open(RESULT, "w", encoding="utf-8")


def log(value):
    out.write(unicode(value) + u"\n")
    out.flush()


def setp(element, path, value):
    try:
        element.set_property(path, value)
        log(u"SET_OK %s=%r" % (path, value))
        return True
    except Exception as exc:
        log(u"SET_FAIL %s=%r error=%r" % (path, value, exc))
        return False


project = projects.open(PROJECT)  # noqa: F821
app = project.active_application
if project.find(VISU_NAME, True):
    log(u"ABORT: %s already exists" % VISU_NAME)
    project.close()
    out.close()
    raise SystemExit

visu = app.create_visualobject(VISU_NAME)
visu.begin_modify()
elements = visu.visual_element_list
factory = visu.input_action_factory
all_ok = True

dynamic = elements.add_element(VisualElementType.Rectangle)  # noqa: F821
for path, value in [
        ("Position.X", 40), ("Position.Y", 40),
        ("Position.Width", 240), ("Position.Height", 36),
        ("Texts.Text", "Status: %s"),
        ("Text variables.Text variable", "GVL_Visu.VisuStatusText")]:
    all_ok = setp(dynamic, path, value) and all_ok

numeric = elements.add_element(VisualElementType.Rectangle)  # noqa: F821
for path, value in [
        ("Position.X", 40), ("Position.Y", 90),
        ("Position.Width", 200), ("Position.Height", 36),
        ("Texts.Text", "%d"),
        ("Text variables.Text variable", "GVL_Visu.InGoodId")]:
    all_ok = setp(numeric, path, value) and all_ok
try:
    action = factory.create_write_variable(
        "GVL_Visu.InGoodId", "Numpad", "1", "", "货物 ID", False, False)
    numeric.add_input_action(action, InputActionEventType.OnMouseClick)  # noqa: F821
    log(u"ACTION_OK numeric write variable")
except Exception as exc:
    all_ok = False
    log(u"ACTION_FAIL numeric error=%r" % exc)

text_input = elements.add_element(VisualElementType.Rectangle)  # noqa: F821
for path, value in [
        ("Position.X", 40), ("Position.Y", 140),
        ("Position.Width", 200), ("Position.Height", 36),
        ("Texts.Text", "%s"),
        ("Text variables.Text variable", "GVL_Visu.InGoodName")]:
    all_ok = setp(text_input, path, value) and all_ok
try:
    action = factory.create_write_variable(
        "GVL_Visu.InGoodName", "Keypad", "", "", "货物名称", False, False)
    text_input.add_input_action(action, InputActionEventType.OnMouseClick)  # noqa: F821
    log(u"ACTION_OK text write variable")
except Exception as exc:
    all_ok = False
    log(u"ACTION_FAIL text error=%r" % exc)

nav = elements.add_element(VisualElementType.Button)  # noqa: F821
for path, value in [
        ("Position.X", 40), ("Position.Y", 200),
        ("Position.Width", 200), ("Position.Height", 36),
        ("Texts.Text", "Go VisuMain")]:
    all_ok = setp(nav, path, value) and all_ok
try:
    action = factory.create_change_shown_visualization(
        ChangeShownVisualizationType.Assignment, "VisuMain")  # noqa: F821
    nav.add_input_action(action, InputActionEventType.OnMouseClick)  # noqa: F821
    log(u"ACTION_OK navigation")
except Exception as exc:
    all_ok = False
    log(u"ACTION_FAIL navigation error=%r" % exc)

visu.end_modify()
log(u"ELEMENT_COUNT=%d" % len(visu.visual_element_list))
if not all_ok:
    log(u"ABORT: binding smoke failed; not saving")
    project.close()
    out.close()
    raise SystemExit

project.save()
log(u"SAVE_OK")
app.build()
for category in system.get_message_categories():  # noqa: F821
    try:
        messages = system.get_messages(category)  # noqa: F821
    except Exception:
        continue
    for message in messages or []:
        text = str(message)
        if ("Compile complete" in text or "Additional code checks complete" in text
                or "error" in text.lower()):
            log(u"BUILD_MESSAGE %s" % text)
project.export_native([visu], EXPORT)
log(u"EXPORT_OK")
project.close()
log(u"BINDING_SMOKE_DONE")
out.close()
