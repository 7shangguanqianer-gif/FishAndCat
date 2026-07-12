# -*- coding: utf-8 -*-
# fix_p3_buttons_0712.py — 修补 P3 四个新按钮的点击动作。
# 现象: wash_visu_0712 建的 Holistic/Lexicographic/CB/TOB 按钮在线无响应;
#       同页 build 产物 Login(OnMouseDown/Up) 与导航钮(OnMouseClick) 均在线验证活。
# 假因: wash 在同一 begin_modify 会话里 remove_id 删元件后再 add+绑动作,
#       动作被静默丢弃(与 build 唯一结构差异)。
# 修法: 会话1只删旧4钮; 会话2纯新增重建, 每钮双绑 OnMouseDown+OnMouseClick
#       同值 execute(幂等赋值, 任一事件活即可)。0 errors 才保存。
import io

PROJECT = r"F:\abb_wh_work\plc\AB_Project\ABB_WH.project"
RESULT = r"F:\abb_wh_work\tools\ab_scripting\fix_p3_buttons_result.txt"

out = io.open(RESULT, "w", encoding="utf-8")
errors = []


def log(v):
    out.write(unicode(v) + u"\n")  # noqa: F821
    out.flush()


def setp(el, path, value):
    try:
        el.set_property(path, value)
    except Exception as exc:
        msg = u"SET_FAIL path=%s error=%r" % (path, exc)
        errors.append(msg)
        log(msg)


def add_button(visu, x, y, w, h, text):
    el = visu.visual_element_list.add_element(VisualElementType.Button)  # noqa: F821
    setp(el, "Position.X", x)
    setp(el, "Position.Y", y)
    setp(el, "Position.Width", w)
    setp(el, "Position.Height", h)
    setp(el, "Texts.Text", text)
    return el


def bind(visu, el, st_code):
    for ev in (InputActionEventType.OnMouseDown,      # noqa: F821
               InputActionEventType.OnMouseClick):    # noqa: F821
        try:
            action = visu.input_action_factory.create_execute_st_code(st_code)
            el.add_input_action(action, ev)
        except Exception as exc:
            msg = u"ACTION_FAIL ev=%r st=%s error=%r" % (ev, st_code, exc)
            errors.append(msg)
            log(msg)


BTNS = [
    (u"Holistic",      940, 316, 88, 26, "GVL_Visu.SelObjective := 0;"),
    (u"Lexicographic", 1032, 316, 130, 26, "GVL_Visu.SelObjective := 1;"),
    (u"CB",            940, 348, 60, 26, "GVL_Visu.SelStrategy := 4;"),
    (u"TOB",           1004, 348, 60, 26, "GVL_Visu.SelStrategy := 5;"),
]

project = projects.open(PROJECT)  # noqa: F821
log(u"OPEN_OK")
va = project.find("VisuAdmin", True)[0]
app = project.active_application
vel = va.visual_element_list
n0 = len(vel)
log(u"P3_BASE count=%d (expect 79)" % n0)

# ---- 会话1: 只删旧4钮(by text 精确匹配, 数目不符 ABORT) ----
va.begin_modify()
found = {}
for i in range(len(vel)):
    el = vel[i]
    try:
        t = el.get_property("Texts.Text")
    except Exception:
        continue
    for name, _x, _y, _w, _h, _st in BTNS:
        if t == name:
            found.setdefault(name, []).append(el.id)
miss = []
for name, _x, _y, _w, _h, _st in BTNS:
    if len(found.get(name, [])) != 1:
        miss.append(u"%s match=%d" % (name, len(found.get(name, []))))
if miss:
    for m in miss:
        log(u"MISS " + m)
    log(u"ABORT old buttons not uniquely found, NOT SAVED")
    va.end_modify()
    project.close()
    raise SystemExit
for name in found:
    vel.remove_id(found[name][0])
va.end_modify()
log(u"OLD_DELETED=4")

# ---- 会话2: 纯新增重建+双绑 ----
va.begin_modify()
for name, x, y, w, h, st in BTNS:
    el = add_button(va, x, y, w, h, name)
    bind(va, el, st)
va.end_modify()
log(u"NEW_BUILT=4 (dual-bound Down+Click)")
log(u"P3_DONE count=%d (expect %d)" % (len(vel), n0))

# ---- 编译 + 保存 ----
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
log(u"=== FIX_P3_BUTTONS_DONE ===")
