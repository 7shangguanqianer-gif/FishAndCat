# -*- coding: utf-8 -*-
# add_cockpit_0711.py — 画面一波流增量施工(0711 总库 A2-A4 画面侧)
# 纯增量:只 add_element,不删不改任何既有元素(21 处已 GUI 洗动作零接触)。
# 布局依据 audit_pages 实测:P1 左下 x40-600 y598-676 全空;图例第8格位 (315,570) 空缺。
# 新动作元素 7 处(洗单,施工后必须 GUI 洗):AUTO toggle / PIN Numpad / LOGIN tap /
# LOGOUT tap / MaintX Numpad / MaintY Numpad / MAINT tap。
# 防重跑护栏:检测到 'SCENE DETECTOR' 文本即 ABORT。
import io

PROJECT = r"F:\abb_wh_work\plc\AB_Project\ABB_WH.project"
RESULT = r"F:\abb_wh_work\tools\ab_scripting\add_cockpit_result.txt"

out = io.open(RESULT, "w", encoding="utf-8")
errors = []


def log(v):
    out.write(unicode(v) + u"\n")  # noqa: F821
    out.flush()


def setp(el, path, value):
    try:
        el.set_property(path, value)
    except Exception as exc:
        msg = u"SET_FAIL id=%s path=%s value=%r error=%r" % (el.id, path, value, exc)
        errors.append(msg)
        log(msg)


def position(el, x, y, w, h):
    setp(el, "Position.X", x)
    setp(el, "Position.Y", y)
    setp(el, "Position.Width", w)
    setp(el, "Position.Height", h)


def add_box(visu, x, y, w, h, text=u"", variable=None):
    el = visu.visual_element_list.add_element(VisualElementType.Rectangle)  # noqa: F821
    position(el, x, y, w, h)
    if text is not None:
        setp(el, "Texts.Text", text)
    if variable:
        setp(el, "Text variables.Text variable", variable)
    return el


def add_button(visu, x, y, w, h, text):
    el = visu.visual_element_list.add_element(VisualElementType.Button)  # noqa: F821
    position(el, x, y, w, h)
    setp(el, "Texts.Text", text)
    return el


def add_lamp(visu, x, y, w, h, variable):
    el = visu.visual_element_list.add_element(VisualElementType.Lamp)  # noqa: F821
    position(el, x, y, w, h)
    setp(el, "Variable", variable)
    return el


def add_input(visu, x, y, w, h, text, variable, input_type,
              minimum=u"", maximum=u"", title=u""):
    el = add_box(visu, x, y, w, h, text, variable)
    try:
        action = visu.input_action_factory.create_write_variable(
            variable, input_type, minimum, maximum, title, False, False)
        el.add_input_action(action, InputActionEventType.OnMouseClick)  # noqa: F821
    except Exception as exc:
        msg = u"ACTION_FAIL write variable=%s error=%r" % (variable, exc)
        errors.append(msg)
        log(msg)
    return el


def add_execute(visu, el, st_code, event=None):
    if event is None:
        event = InputActionEventType.OnMouseClick  # noqa: F821
    try:
        action = visu.input_action_factory.create_execute_st_code(st_code)
        el.add_input_action(action, event)
    except Exception as exc:
        msg = u"ACTION_FAIL execute st=%s error=%r" % (st_code, exc)
        errors.append(msg)
        log(msg)


def add_tap(visu, el, variable):
    add_execute(visu, el, variable + " := TRUE;", InputActionEventType.OnMouseDown)  # noqa: F821
    add_execute(visu, el, variable + " := FALSE;", InputActionEventType.OnMouseUp)  # noqa: F821


project = projects.open(PROJECT)  # noqa: F821
log(u"OPEN_OK")
hits = project.find("VisuMain", True)
if len(hits) != 1:
    log(u"ABORT VisuMain not found uniquely")
    project.close()
    raise SystemExit
vm = hits[0]
vel = vm.visual_element_list

# ---- 防重跑护栏 ----
n_before = len(vel)
for i in range(n_before):
    try:
        if unicode(vel[i].get_property("Texts.Text")) == u"SCENE DETECTOR":  # noqa: F821
            log(u"ABORT already built (SCENE DETECTOR found), count=%d" % n_before)
            project.close()
            raise SystemExit
    except SystemExit:
        raise
    except Exception:
        pass
log(u"BASE_OK P1 count=%d" % n_before)

vm.begin_modify()

# ---- 图例第 8 格:检修紫(315,570 与既有图例同规格) ----
add_box(vm, 315, 570, 265, 22, u"7 Maintenance (purple)")
sw = add_box(vm, 319, 573, 16, 16, u"")
setp(sw, "Color variables.Normal state.Fill color", "GVL_Visu.aLegendColor[7]")

# ---- 三分组框(透明填充只显边线,B 版分组风) ----
for gx, gw in [(40, 282), (328, 140), (474, 126)]:
    box = add_box(vm, gx, 594, gw, 82, u"")
    setp(box, "Color variables.Normal state.Fill color", "GVL_Visu.dwTransparent")

# ---- 组1 场景检测器(A2 驾驶舱:画像+推荐+Auto 开关) x40-322 ----
add_box(vm, 44, 598, 130, 16, u"SCENE DETECTOR")
add_box(vm, 178, 598, 140, 16, u"%s", "GVL_Visu.VisuRecText")
add_box(vm, 44, 618, 86, 20, u"N=%d", "GVL_Visu.VisuProfN")
add_box(vm, 134, 618, 92, 20, u"DENS=%.3f", "GVL_Visu.VisuProfDensity")
add_box(vm, 230, 618, 88, 20, u"SKEW=%.2f", "GVL_Visu.VisuProfSkew")
add_box(vm, 44, 640, 86, 20, u"W=%.1f", "GVL_Visu.VisuProfWMean")
add_box(vm, 134, 640, 92, 20, u"HEAVY=%.2f", "GVL_Visu.VisuProfWHeavy")
add_box(vm, 230, 640, 88, 20, u"STRAT=%d", "GVL_Visu.SelStrategy")
auto_btn = add_button(vm, 44, 662, 110, 18, u"Auto strategy")
add_execute(vm, auto_btn,
            "GVL_Visu.xAutoStrategy := NOT GVL_Visu.xAutoStrategy;")
add_lamp(vm, 160, 662, 18, 18, "GVL_Visu.xAutoStrategy")
add_box(vm, 184, 662, 134, 18, u"lamp on = auto apply")

# ---- 组2 权限(A4 变量层双闸的画面侧) x328-468 ----
add_box(vm, 332, 598, 56, 16, u"ACCESS")
add_box(vm, 392, 598, 72, 16, u"%s", "GVL_Visu.VisuUserText")
add_box(vm, 332, 618, 30, 20, u"PIN")
add_input(vm, 366, 618, 98, 20, u"%d", "GVL_Visu.InPinCode",
          "Numpad", u"0", u"9999", u"Admin PIN")
lg = add_button(vm, 332, 640, 64, 20, u"Login")
add_tap(vm, lg, "GVL_Visu.CmdLogin")
lo = add_button(vm, 400, 640, 64, 20, u"Logout")
add_tap(vm, lo, "GVL_Visu.CmdLogout")
locked = add_box(vm, 332, 662, 132, 16, u"Params guarded")
setp(locked, "State variables.Invisible", "GVL_Visu.iUserLevel >= 1")

# ---- 组3 检修(A3 putaway block 的画面侧) x474-600 ----
add_box(vm, 478, 598, 118, 16, u"MAINTENANCE")
add_box(vm, 478, 618, 14, 20, u"X")
add_input(vm, 494, 618, 42, 20, u"%d", "GVL_Visu.InMaintX",
          "Numpad", u"0", u"19", u"Column 0-19")
add_box(vm, 542, 618, 14, 20, u"Y")
add_input(vm, 558, 618, 40, 20, u"%d", "GVL_Visu.InMaintY",
          "Numpad", u"0", u"19", u"Tier 0-19")
mt = add_button(vm, 478, 640, 78, 20, u"Set / Clear")
add_tap(vm, mt, "GVL_Visu.CmdMaintToggle")
add_box(vm, 560, 640, 38, 20, u"%d", "GVL_Visu.VisuMaintCount")
add_box(vm, 478, 662, 120, 16, u"admin only, purple")

vm.end_modify()
n_after = len(vm.visual_element_list)
log(u"ADDED=%d total=%d" % (n_after - n_before, n_after))

app = project.active_application
app.build()
summary = u"?"
for c in system.get_message_categories():                    # noqa: F821
    try:
        msgs = system.get_messages(c)                        # noqa: F821
    except Exception:
        continue
    for m in msgs:
        s = str(m)
        if s.startswith("Compile complete"):
            summary = s
log(u"BUILD: %s" % summary)
if "-- 0 errors" in summary:
    project.save()
    log(u"SAVE_OK")
else:
    log(u"!! NOT SAVED (compile errors)")
log(u"ERRORS=%d" % len(errors))
project.close()
log(u"=== COCKPIT_DONE ===")
