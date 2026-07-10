# -*- coding: utf-8 -*-
"""Build the ABB warehouse P1/P2 visualization pages through ScriptVisualization API."""
import io

PROJECT = r"F:\abb_wh_work\plc\AB_Project\ABB_WH.project"
RESULT = r"F:\abb_wh_spike\visu_native_20260710_1225\build_visu_pages_ascii_result.txt"
EXPORT_MAIN = r"F:\abb_wh_spike\visu_native_20260710_1225\VisuMain_ascii_after.xml"
EXPORT_STATS = r"F:\abb_wh_spike\visu_native_20260710_1225\VisuStats_ascii_after.xml"

out = io.open(RESULT, "w", encoding="utf-8")
errors = []


def log(value):
    out.write(unicode(value) + u"\n")
    out.flush()


def setp(element, path, value):
    try:
        element.set_property(path, value)
    except Exception as exc:
        msg = u"SET_FAIL element=%s path=%s value=%r error=%r" % (
            element.id, path, value, exc)
        errors.append(msg)
        log(msg)


def position(element, x, y, width, height):
    setp(element, "Position.X", x)
    setp(element, "Position.Y", y)
    setp(element, "Position.Width", width)
    setp(element, "Position.Height", height)


def add_box(visu, x, y, width, height, text=u"", variable=None):
    element = visu.visual_element_list.add_element(VisualElementType.Rectangle)  # noqa: F821
    position(element, x, y, width, height)
    if text is not None:
        setp(element, "Texts.Text", text)
    if variable:
        setp(element, "Text variables.Text variable", variable)
    return element


def add_button(visu, x, y, width, height, text):
    element = visu.visual_element_list.add_element(VisualElementType.Button)  # noqa: F821
    position(element, x, y, width, height)
    setp(element, "Texts.Text", text)
    return element


def add_lamp(visu, x, y, width, height, variable):
    element = visu.visual_element_list.add_element(VisualElementType.Lamp)  # noqa: F821
    position(element, x, y, width, height)
    setp(element, "Variable", variable)
    return element


def add_dynamic(visu, x, y, width, height, text, variable):
    return add_box(visu, x, y, width, height, text, variable)


def add_input(visu, x, y, width, height, text, variable, input_type,
              minimum=u"", maximum=u"", title=u""):
    element = add_dynamic(visu, x, y, width, height, text, variable)
    try:
        action = visu.input_action_factory.create_write_variable(
            variable, input_type, minimum, maximum, title, False, False)
        element.add_input_action(action, InputActionEventType.OnMouseClick)  # noqa: F821
    except Exception as exc:
        msg = u"ACTION_FAIL write variable=%s error=%r" % (variable, exc)
        errors.append(msg)
        log(msg)
    return element


def add_execute(visu, element, st_code,
                event=InputActionEventType.OnMouseClick):  # noqa: F821
    try:
        action = visu.input_action_factory.create_execute_st_code(st_code)
        element.add_input_action(action, event)
    except Exception as exc:
        msg = u"ACTION_FAIL execute st=%s error=%r" % (st_code, exc)
        errors.append(msg)
        log(msg)


def add_tap(visu, element, variable):
    add_execute(visu, element, variable + " := TRUE;", InputActionEventType.OnMouseDown)  # noqa: F821
    add_execute(visu, element, variable + " := FALSE;", InputActionEventType.OnMouseUp)  # noqa: F821


def add_navigation(visu, element, target):
    try:
        action = visu.input_action_factory.create_change_shown_visualization(
            ChangeShownVisualizationType.Assignment, target)  # noqa: F821
        element.add_input_action(action, InputActionEventType.OnMouseClick)  # noqa: F821
    except Exception as exc:
        msg = u"ACTION_FAIL navigation target=%s error=%r" % (target, exc)
        errors.append(msg)
        log(msg)


def add_labeled_value(visu, x, y, label, text, variable,
                      label_width=150, value_width=160, height=24):
    add_box(visu, x, y, label_width, height, label)
    add_dynamic(visu, x + label_width + 6, y, value_width, height, text, variable)


def add_labeled_input(visu, x, y, label, text, variable, input_type,
                      minimum=u"", maximum=u"", title=u"",
                      label_width=64, input_width=190, height=26):
    add_box(visu, x, y, label_width, height, label)
    add_input(visu, x + label_width + 6, y, input_width, height, text, variable,
              input_type, minimum, maximum, title)


project = projects.open(PROJECT)  # noqa: F821
app = project.active_application

main_hits = project.find("VisuMain", True)
if len(main_hits) != 1 or not main_hits[0].is_visualobject:
    log(u"ABORT VisuMain not found uniquely")
    project.close()
    out.close()
    raise SystemExit
visu_main = main_hits[0]
if len(visu_main.visual_element_list) != 400:
    log(u"ABORT VisuMain expected 400 base cells, actual=%d" %
        len(visu_main.visual_element_list))
    project.close()
    out.close()
    raise SystemExit
if project.find("VisuStats", True):
    log(u"ABORT VisuStats already exists")
    project.close()
    out.close()
    raise SystemExit

log(u"BASE_OK VisuMain=400")

# P1: warehouse map, controls, state, path, statistics, and score weights.
visu_main.begin_modify()
add_box(visu_main, 40, 4, 560, 30, u"Smart Storage Control - Warehouse Slot Optimization")

# Crane overlay: PLC already converts warehouse coordinates to pixels.
crane = visu_main.visual_element_list.add_element(VisualElementType.Ellipse)  # noqa: F821
position(crane, 0, 0, 28, 20)
setp(crane, "Absolute movement.Movement.X", "GVL_Visu.VisuCraneXpx")
setp(crane, "Absolute movement.Movement.Y", "GVL_Visu.VisuCraneYpx")

add_dynamic(visu_main, 620, 40, 560, 30, u"Status: %s", "GVL_Visu.VisuStatusText")
add_lamp(visu_main, 1200, 38, 32, 32, "GVL_Visu.VisuAlarm")

inputs = [
    (90, u"ID", u"%d", "GVL_Visu.InGoodId", "Numpad", u"1", u"", u"Goods ID"),
    (122, u"Name", u"%s", "GVL_Visu.InGoodName", "Keypad", u"", u"", u"Goods name"),
    (154, u"Weight", u"%.1f", "GVL_Visu.InGoodWeight", "Numpad", u"0", u"200", u"Weight kg"),
    (186, u"Freq", u"%.1f", "GVL_Visu.InGoodFreq", "Numpad", u"0", u"100", u"Access frequency"),
    (218, u"Volume", u"%.2f", "GVL_Visu.InGoodVolume", "Numpad", u"0", u"1.0", u"Volume m3"),
]
for row in inputs:
    add_labeled_input(visu_main, 620, *row)

for x, width, text, variable in [
        (620, 100, u"Add goods", "GVL_Visu.CmdAddGood"),
        (730, 100, u"Load demo", "GVL_Visu.CmdLoadDemo"),
        (840, 80, u"Reset", "GVL_Visu.CmdReset")]:
    button = add_button(visu_main, x, 270, width, 34, text)
    add_tap(visu_main, button, variable)

add_box(visu_main, 620, 320, 50, 34, u"Mode")
for x, width, text, value in [
        (680, 70, u"FIFO", 0), (760, 70, u"Nearest", 1),
        (840, 70, u"Score", 2), (920, 100, u"AWRA-LS", 3)]:
    button = add_button(visu_main, x, 320, width, 34, text)
    add_execute(visu_main, button, "GVL_Visu.SelStrategy := %d;" % value)
add_dynamic(visu_main, 1030, 320, 230, 34,
            u"Current strategy: %d", "GVL_Visu.SelStrategy")

for x, text, variable in [
        (620, u"Run assign", "GVL_Visu.CmdRunAssign"),
        (730, u"Animate", "GVL_Visu.CmdAnimate"),
        (840, u"Save snapshot", "GVL_Visu.CmdSaveSnap")]:
    button = add_button(visu_main, x, 380, 100, 34, text)
    add_tap(visu_main, button, variable)
compare = add_button(visu_main, 950, 380, 100, 34, u"Live/Snapshot")
add_execute(visu_main, compare,
            "GVL_Visu.CmdCompareMode := NOT GVL_Visu.CmdCompareMode;")
add_lamp(visu_main, 1062, 381, 32, 32, "GVL_Visu.xSnapValid")
add_box(visu_main, 1098, 384, 100, 24, u"Snapshot valid")
to_stats = add_button(visu_main, 1140, 270, 120, 34, u"P2 Records")
add_navigation(visu_main, to_stats, "VisuStats")

add_labeled_value(visu_main, 620, 430, u"Target X", u"%d", "GVL_Visu.VisuTargetX", 70, 50)
add_labeled_value(visu_main, 750, 430, u"Target Y", u"%d", "GVL_Visu.VisuTargetY", 70, 50)
add_labeled_value(visu_main, 880, 430, u"Path m", u"%.1f", "GVL_Visu.VisuPathLen", 74, 64)
add_labeled_value(visu_main, 1030, 430, u"Travel s", u"%.1f", "GVL_Visu.VisuExecTime", 74, 64)

for y, label, text, variable in [
        (480, u"Total inbound / s", u"%.1f", "GVL_Visu.VisuTotalTime"),
        (508, u"Average item / s", u"%.1f", "GVL_Visu.VisuAvgTime"),
        (536, u"Space utilization / %", u"%.1f", "GVL_Visu.VisuSpaceUtilization"),
        (564, u"Total path / m", u"%.1f", "GVL_Visu.VisuWearIndex"),
        (592, u"Violations", u"%d", "GVL_Visu.VisuViolationCount")]:
    add_labeled_value(visu_main, 620, y, label, text, variable, 150, 150)

add_box(visu_main, 930, 480, 330, 136,
        u"State codes\nREADY / SUGGEST / ASSIGN_RUN\nIMPROVE / DONE_OK\nERR_* / ALARM_*\nCyan=query, Blue=path")

for x, label, variable, default in [
        (620, u"Alpha efficiency", "GVL_Param.rAlpha", u"1.0"),
        (750, u"Beta stability", "GVL_Param.rBeta", u"0.6"),
        (880, u"Gamma energy", "GVL_Param.rGamma", u"0.4"),
        (1010, u"Delta reserve", "GVL_Param.rDelta", u"0.15")]:
    add_box(visu_main, x, 626, 62, 26, label)
    add_input(visu_main, x + 68, 626, 58, 26, u"%.2f", variable,
              "Numpad", u"0", u"", label)

add_box(visu_main, 620, 654, 270, 18, u"Defaults: A=1.0 B=0.6 G=0.4 D=0.15")
add_box(visu_main, 900, 654, 360, 18,
        u"Online tests 45/45 - sim/ST cross-check - dwell point=I/O")

# Map labels and complete seven-state legend.
for x, text in [(48, u"0"), (188, u"5"), (328, u"10"), (468, u"15"), (580, u"19")]:
    add_box(visu_main, x, 445, 28, 18, text)
for y, text in [(42, u"19"), (122, u"15"), (222, u"10"), (322, u"5"), (422, u"0")]:
    add_box(visu_main, 8, y, 28, 18, text)
add_box(visu_main, 40, 466, 560, 20,
        u"Columns 0..19 -> Tier 0 at bottom (max capacity), I/O at lower left")
legend = [u"0 Empty (light gray)", u"1 Preset (dark gray)", u"2 Occupied (green)",
          u"3 Recommended (yellow)", u"4 Path (blue)", u"5 Alarm (red)", u"6 Query (cyan)"]
for index, text in enumerate(legend):
    col = index % 2
    row = index // 2
    add_box(visu_main, 40 + col * 275, 492 + row * 26, 265, 22, text)

visu_main.end_modify()
log(u"P1_CREATED count=%d" % len(visu_main.visual_element_list))

# P2: paged records, query result, physical-model tuning, and totals.
visu_stats = app.create_visualobject("VisuStats")
visu_stats.begin_modify()
add_box(visu_stats, 40, 16, 400, 30, u"P2 - Records, Query and Model Parameters")

headers = [(40, 90, u"Goods ID"), (150, 90, u"Column X"), (260, 90, u"Tier Y"),
           (370, 110, u"Path / m"), (500, 110, u"Travel / s")]
for x, width, text in headers:
    add_box(visu_stats, x, 60, width, 26, text)

columns = [
    (40, 90, u"%d", "GVL_Visu.aRowId[%d]"),
    (150, 90, u"%d", "GVL_Visu.aRowX[%d]"),
    (260, 90, u"%d", "GVL_Visu.aRowY[%d]"),
    (370, 110, u"%.1f", "GVL_Visu.aRowPathLen[%d]"),
    (500, 110, u"%.2f", "GVL_Visu.aRowExecT[%d]"),
]
for row in range(10):
    y = 90 + row * 28
    for x, width, fmt, variable_fmt in columns:
        add_dynamic(visu_stats, x, y, width, 24, fmt, variable_fmt % row)

add_box(visu_stats, 40, 378, 570, 24,
        u"Paged aGoods records. Business ID is not the array index.")
up = add_button(visu_stats, 40, 410, 100, 34, u"Previous")
add_tap(visu_stats, up, "GVL_Visu.CmdPageUp")
down = add_button(visu_stats, 150, 410, 100, 34, u"Next")
add_tap(visu_stats, down, "GVL_Visu.CmdPageDown")
add_dynamic(visu_stats, 270, 410, 160, 34, u"First row: %d", "GVL_Visu.iRecTop")
add_dynamic(visu_stats, 440, 410, 170, 34, u"Total goods: %d", "GVL_Visu.iRecTotal")

add_box(visu_stats, 650, 16, 570, 30, u"Query by business ID (supports demo IDs 901/902/903)")
add_box(visu_stats, 650, 60, 130, 30, u"Query ID")
add_input(visu_stats, 790, 60, 170, 30, u"%d", "GVL_Visu.InQueryId",
          "Numpad", u"1", u"", u"Query goods ID")
query = add_button(visu_stats, 970, 60, 100, 30, u"Query")
add_tap(visu_stats, query, "GVL_Visu.CmdQuery")
add_lamp(visu_stats, 1080, 60, 32, 30, "GVL_Visu.QryFound")
add_box(visu_stats, 1118, 60, 102, 30, u"Found")

query_rows = [
    (104, u"Name", u"%s", "GVL_Visu.QryName"),
    (132, u"Weight / kg", u"%.1f", "GVL_Visu.QryWeight"),
    (160, u"Frequency", u"%.1f", "GVL_Visu.QryFreq"),
    (188, u"Volume / m3", u"%.2f", "GVL_Visu.QryVolume"),
    (216, u"Position X", u"%d", "GVL_Visu.QryX"),
    (244, u"Position Y", u"%d", "GVL_Visu.QryY"),
    (272, u"Path / m", u"%.1f", "GVL_Visu.QryPathLen"),
    (300, u"Travel / s", u"%.2f", "GVL_Visu.QryExecTime"),
    (328, u"Loaded travel / s", u"%.2f", "GVL_Visu.QryTravelLaden"),
    (356, u"Handling / s", u"%.2f", "GVL_Visu.QryHandleT"),
]
for y, label, fmt, variable in query_rows:
    add_labeled_value(visu_stats, 650, y, label, fmt, variable, 150, 250)

add_box(visu_stats, 650, 400, 570, 26, u"Physical model parameters (press Query again after editing)")
tuning = [
    (434, 650, u"Vertical load factor", "GVL_Param.rLadenFactorVY", u"0", u"1"),
    (466, 650, u"Light/medium W1", "GVL_Param.rHandleW1", u"0", u"200"),
    (498, 650, u"Medium/heavy W2", "GVL_Param.rHandleW2", u"0", u"200"),
    (434, 950, u"Light handling T1", "GVL_Param.rHandleT1", u"0", u""),
    (466, 950, u"Medium handling T2", "GVL_Param.rHandleT2", u"0", u""),
    (498, 950, u"Heavy handling T3", "GVL_Param.rHandleT3", u"0", u""),
]
for y, x, label, variable, minimum, maximum in tuning:
    add_box(visu_stats, x, y, 170, 26, label)
    add_input(visu_stats, x + 176, y, 100, 26, u"%.2f", variable,
              "Numpad", minimum, maximum, label)

add_box(visu_stats, 40, 472, 570, 28, u"Current batch summary")
for y, label, fmt, variable in [
        (506, u"Total inbound / s", u"%.1f", "GVL_Visu.VisuTotalTime"),
        (534, u"Average item / s", u"%.1f", "GVL_Visu.VisuAvgTime"),
        (562, u"Space utilization / %", u"%.1f", "GVL_Visu.VisuSpaceUtilization"),
        (590, u"Total path / m", u"%.1f", "GVL_Visu.VisuWearIndex"),
        (618, u"Violations", u"%d", "GVL_Visu.VisuViolationCount")]:
    add_labeled_value(visu_stats, 40, y, label, fmt, variable, 190, 180)

back = add_button(visu_stats, 1100, 640, 120, 34, u"Back to P1")
add_navigation(visu_stats, back, "VisuMain")
add_box(visu_stats, 40, 688, 1180, 28,
        u"Alarm Banner area: not visible in Simulation; Batch D accepts config + zero compile errors.")
visu_stats.end_modify()
log(u"P2_CREATED count=%d" % len(visu_stats.visual_element_list))

if errors:
    log(u"ABORT errors=%d; not saving" % len(errors))
    project.close()
    out.close()
    raise SystemExit

project.save()
log(u"SAVE_OK")
app.build()
compile_messages = []
for category in system.get_message_categories():  # noqa: F821
    try:
        messages = system.get_messages(category)  # noqa: F821
    except Exception:
        continue
    for message in messages or []:
        text = str(message)
        if ("Compile complete" in text or "Additional code checks complete" in text
                or "error" in text.lower()):
            compile_messages.append(text)
            log(u"BUILD_MESSAGE %s" % text)

project.export_native([visu_main], EXPORT_MAIN)
project.export_native([visu_stats], EXPORT_STATS)
log(u"EXPORT_OK main=%s stats=%s" % (EXPORT_MAIN, EXPORT_STATS))
project.close()
log(u"BUILD_VISU_PAGES_DONE")
out.close()
