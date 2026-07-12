# -*- coding: utf-8 -*-
# wash_visu_0712.py — 画面洗(克制版,用户0712拍板):
#   P1 只改字: badge "Tests 59/59..." -> "Tests 75/75..."(75/0 第四轮 AB 复验后的真实数)
#   P3 重构右下 DIAGNOSTICS/RESERVED 区(840,300,400,220) -> 上=STRATEGY+OBJECTIVE 新组
#     (Holistic/Lexicographic 切档 + CB/TOB 手选 + Detector 推荐镜像), 下=精简 DIAGNOSTICS。
#   P1 其余零改动(ISA-101 frozen, 三页制施工时立的规矩)。
# 安全护栏(仿 build_three_pages_0713.py 先例):
#   目标元件按 text/坐标四元组精确匹配, 数目不符 = ABORT 不保存;
#   VisuAdmin 不存在(未施工工程) = ABORT; 编译非 0 errors = 不保存。
# 语法纪律: IronPython 2.7(无 f-string); AB --noUI --runscript 执行。
import io

PROJECT = r"F:\abb_wh_work\plc\AB_Project\ABB_WH.project"
RESULT = r"F:\abb_wh_work\tools\ab_scripting\wash_visu_result.txt"

out = io.open(RESULT, "w", encoding="utf-8")
errors = []


def log(v):
    out.write(unicode(v) + u"\n")  # noqa: F821
    out.flush()


def setp(el, path, value):
    try:
        el.set_property(path, value)
    except Exception as exc:
        msg = u"SET_FAIL path=%s value=%r error=%r" % (path, value, exc)
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


def add_execute(visu, el, st_code):
    try:
        action = visu.input_action_factory.create_execute_st_code(st_code)
        el.add_input_action(action, InputActionEventType.OnMouseClick)  # noqa: F821
    except Exception as exc:
        msg = u"ACTION_FAIL execute st=%s error=%r" % (st_code, exc)
        errors.append(msg)
        log(msg)


# ============================================================
project = projects.open(PROJECT)  # noqa: F821
log(u"OPEN_OK")

hits = project.find("VisuAdmin", True)
if not hits:
    log(u"ABORT VisuAdmin missing (three-pages build not applied?)")
    project.close()
    raise SystemExit
va = hits[0]
vm = project.find("VisuMain", True)[0]
app = project.active_application

# ============================================================
# P1 —— badge 改字(唯一改动)
# ============================================================
vel = vm.visual_element_list
vm.begin_modify()
OLD_BADGE = u"Tests 59/59 | sim-ST cross-check | dwell=I/O"
NEW_BADGE = u"Tests 75/75 | sim-ST cross-check | dwell=I/O"
badges = []
for i in range(len(vel)):
    el = vel[i]
    try:
        if el.get_property("Texts.Text") == OLD_BADGE:
            badges.append(el)
    except Exception:
        pass
if len(badges) != 1:
    log(u"ABORT badge match=%d (expect 1), NOT SAVED" % len(badges))
    vm.end_modify()
    project.close()
    raise SystemExit
badges[0].set_property("Texts.Text", NEW_BADGE)
vm.end_modify()
log(u"P1_BADGE_OK 59/59 -> 75/75")

# ============================================================
# P3 —— 右下区重构(外框 4 线保留, 内容换血)
# ============================================================
vel3 = va.visual_element_list
n0 = len(vel3)
log(u"P3_BASE count=%d (expect 67)" % n0)
va.begin_modify()

# ---- 目标定位(标题按文本匹配——0712 课: 坐标四元组对 frame() 算宽元件不可靠,
#      上轮 (848,291,157,18) miss; 文本匹配 badge 已验证可靠。删 2 仍坐标匹配已命中) ----
title_cand = []
del_keys = {(852, 316, 376, 120): [], (852, 452, 340, 20): []}
for i in range(len(vel3)):
    el = vel3[i]
    try:
        t = el.get_property("Texts.Text")
    except Exception:
        t = None
    if t == u"DIAGNOSTICS / RESERVED":
        title_cand.append(el)
    try:
        key = (el.get_property("Position.X"), el.get_property("Position.Y"),
               el.get_property("Position.Width"), el.get_property("Position.Height"))
    except Exception:
        continue
    if key in del_keys:
        del_keys[key].append(el.id)
miss = []
if len(title_cand) != 1:
    miss.append(u"title text match=%d (expect 1)" % len(title_cand))
for k in del_keys:
    if len(del_keys[k]) != 1:
        miss.append(u"%r expect=1 got=%d" % (k, len(del_keys[k])))
if miss:
    for m in miss:
        log(u"P3_MISS " + m)
    # 诊断 dump: y 280-305 元件的坐标四元组+文本, 定位漂移原因
    for i in range(len(vel3)):
        el = vel3[i]
        try:
            y = el.get_property("Position.Y")
            if 280 <= y <= 305:
                log(u"DUMP y-band: (%r,%r,%r,%r) text=%r" % (
                    el.get_property("Position.X"), y,
                    el.get_property("Position.Width"),
                    el.get_property("Position.Height"),
                    el.get_property("Texts.Text")))
        except Exception:
            pass
    log(u"ABORT P3 targets missing, NOT SAVED")
    va.end_modify()
    project.close()
    raise SystemExit
title_el = title_cand[0]

# 组标题改字 + 宽度适配
title_el.set_property("Texts.Text", u"STRATEGY + OBJECTIVE")
title_el.set_property("Position.Width", 144)
# 删 State codes 说明箱 + RESERVED 标签
for k in del_keys:
    vel3.remove_id(del_keys[k][0])
log(u"P3_TITLE_OK + DELETED=2")

# ---- 上块 STRATEGY + OBJECTIVE(y316-424) ----
add_box(va, 852, 316, 84, 26, u"Obj: %d", "GVL_Visu.SelObjective")
b_hol = add_button(va, 940, 316, 88, 26, u"Holistic")
add_execute(va, b_hol, "GVL_Visu.SelObjective := 0;")
b_lex = add_button(va, 1032, 316, 130, 26, u"Lexicographic")
add_execute(va, b_lex, "GVL_Visu.SelObjective := 1;")

add_box(va, 852, 348, 84, 26, u"Strat: %d", "GVL_Visu.SelStrategy")
b_cb = add_button(va, 940, 348, 60, 26, u"CB")
add_execute(va, b_cb, "GVL_Visu.SelStrategy := 4;")
b_tob = add_button(va, 1004, 348, 60, 26, u"TOB")
add_execute(va, b_tob, "GVL_Visu.SelStrategy := 5;")
add_box(va, 1072, 351, 150, 20, u"(0-3 on P1)")

add_box(va, 852, 380, 80, 20, u"Detector:")
add_box(va, 936, 380, 288, 20, u"%s", "GVL_Visu.VisuRecText")
add_box(va, 852, 404, 372, 18, u"pick here, then Run assign on P1")

# ---- 分隔线 + 下块 DIAGNOSTICS(y430-518) ----
add_box(va, 840, 430, 400, 2)
add_box(va, 848, 421, 85, 18, u"DIAGNOSTICS")
add_box(va, 852, 446, 376, 20,
        u"State: READY / SUGGEST / ASSIGN_RUN / IMPROVE / DONE_OK / ERR_*")
add_box(va, 852, 472, 376, 20, u"Map: cyan=query  blue=path  purple=maintenance")

va.end_modify()
log(u"P3_DONE count=%d (expect %d)" % (len(vel3), n0 - 2 + 14))

# ============================================================
# 编译 + 保存(0 errors 才保存)
# ============================================================
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
log(u"")
log(u"==== GUI VERIFY LIST (4 new buttons, test online) ====")
log(u"P3 (940,316) Holistic  -> SelObjective=0")
log(u"P3 (1032,316) Lexicographic -> SelObjective=1")
log(u"P3 (940,348) CB  -> SelStrategy=4")
log(u"P3 (1004,348) TOB -> SelStrategy=5")
project.close()
log(u"=== WASH_VISU_DONE ===")
