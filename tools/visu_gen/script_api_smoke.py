# -*- coding: utf-8 -*-
import io

PROJECT = r"F:\abb_wh_spike\visu_native_20260710_1225\AB_Project\ABB_WH.project"
RESULT = r"F:\abb_wh_spike\visu_native_20260710_1225\script_api_smoke_result.txt"
EXPORT = r"F:\abb_wh_spike\visu_native_20260710_1225\VisuScriptSpike.xml"
VISU_NAME = "VisuScriptSpike"

out = io.open(RESULT, "w", encoding="utf-8")


def log(value):
    out.write(unicode(value) + u"\n")
    out.flush()


def set_property(element, path, value):
    try:
        element.set_property(path, value)
        actual = element.get_property(path)
        log(u"SET_OK %s=%r actual=%r" % (path, value, actual))
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
log(u"CREATE_VISU_OK %s" % visu.get_name())
all_ok = True

visu.begin_modify()
elements = visu.visual_element_list

rect = elements.add_element(VisualElementType.Rectangle)  # noqa: F821
for path, value in [
        ("Position.X", 40), ("Position.Y", 40),
        ("Position.Width", 240), ("Position.Height", 40),
        ("Texts.Text", "SCRIPT API SMOKE"),
]:
    all_ok = set_property(rect, path, value) and all_ok

button = elements.add_element(VisualElementType.Button)  # noqa: F821
for path, value in [
        ("Position.X", 40), ("Position.Y", 100),
        ("Position.Width", 160), ("Position.Height", 40),
        ("Texts.Text", "RESET TEST"),
]:
    all_ok = set_property(button, path, value) and all_ok
try:
    action = visu.input_action_factory.create_execute_st_code(
        "GVL_Visu.CmdReset := TRUE;")
    button.add_input_action(action, InputActionEventType.OnMouseClick)  # noqa: F821
    log(u"ACTION_OK button OnMouseClick execute ST")
except Exception as exc:
    all_ok = False
    log(u"ACTION_FAIL button error=%r" % exc)

lamp = elements.add_element(VisualElementType.Lamp)  # noqa: F821
for path, value in [
        ("Position.X", 230), ("Position.Y", 100),
        ("Position.Width", 40), ("Position.Height", 40),
        ("Variable", "GVL_Visu.VisuAlarm"),
]:
    all_ok = set_property(lamp, path, value) and all_ok

ellipse = elements.add_element(VisualElementType.Ellipse)  # noqa: F821
for path, value in [
        ("Position.X", 40), ("Position.Y", 180),
        ("Position.Width", 28), ("Position.Height", 20),
        ("Absolute movement.Movement.X", "GVL_Visu.VisuCraneXpx"),
        ("Absolute movement.Movement.Y", "GVL_Visu.VisuCraneYpx"),
]:
    all_ok = set_property(ellipse, path, value) and all_ok

visu.end_modify()
log(u"ELEMENT_COUNT=%d" % len(visu.visual_element_list))

if not all_ok:
    log(u"ABORT: one or more properties/actions failed; not saving")
    project.close()
    out.close()
    raise SystemExit

project.save()
log(u"SAVE_OK")
app.build()
log(u"BUILD_CALLED")

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
log(u"EXPORT_OK %s" % EXPORT)
project.close()
log(u"SMOKE_DONE")
out.close()
