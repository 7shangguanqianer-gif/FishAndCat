# -*- coding: utf-8 -*-
# fix_input_titles.py -- 0710 夜:修画面 34 编译错(根因两个,一次修完):
#   ①create_write_variable 的 title 传了裸文本(Goods ID 等)→ 被当 IEC 表达式解析报 C0002
#     修法=包 IEC 单引号 'Goods ID'
#   ②input_type 传短名 "Numpad" → C0077 Unknown type: Numpad_VISU_STRUCT
#     修法=全限定 VisuDialogs.Numpad / VisuDialogs.Keypad(官方文档口径,同增补卡 §1.1)
# 策略:ScriptVisualization 无法读改已有输入动作(probe_input_action_api 证实无
#   remove_input_action / 无动作枚举)→ 删 16 个输入框元素(vel.remove_id)按原参数重建。
# 安全:坐标+尺寸四元组精确匹配;匹配数不符 = 不保存退出(工程零改动)。
# 另:探 Library Manager 加库 API,能加则注入 VisuDialogs(与全限定名双保险)。
import io

PROJECT = r"F:\abb_wh_work\plc\AB_Project\ABB_WH.project"
RESULT = r"F:\abb_wh_work\tools\ab_scripting\fix_input_titles_result.txt"

out = io.open(RESULT, "w", encoding="utf-8")


def log(v):
    out.write(unicode(v) + u"\n")
    out.flush()


def q(s):
    return u"'" + s + u"'"          # IEC STRING 字面量


NUM = "VisuDialogs.Numpad"
KEY = "VisuDialogs.Keypad"
# (x, y, w, h, text, variable, input_type, min, max, title)
MAIN = [
    (690, 90, 190, 26, u"%d", "GVL_Visu.InGoodId", NUM, u"1", u"", q(u"Goods ID")),
    (690, 122, 190, 26, u"%s", "GVL_Visu.InGoodName", KEY, u"", u"", q(u"Goods name")),
    (690, 154, 190, 26, u"%.1f", "GVL_Visu.InGoodWeight", NUM, u"0", u"200", q(u"Weight kg")),
    (690, 186, 190, 26, u"%.1f", "GVL_Visu.InGoodFreq", NUM, u"0", u"100", q(u"Access frequency")),
    (690, 218, 190, 26, u"%.2f", "GVL_Visu.InGoodVolume", NUM, u"0", u"1.0", q(u"Volume m3")),
    (688, 626, 58, 26, u"%.2f", "GVL_Param.rAlpha", NUM, u"0", u"", q(u"Alpha efficiency")),
    (818, 626, 58, 26, u"%.2f", "GVL_Param.rBeta", NUM, u"0", u"", q(u"Beta stability")),
    (948, 626, 58, 26, u"%.2f", "GVL_Param.rGamma", NUM, u"0", u"", q(u"Gamma energy")),
    (1078, 626, 58, 26, u"%.2f", "GVL_Param.rDelta", NUM, u"0", u"", q(u"Delta reserve")),
]
STATS = [
    (790, 60, 170, 30, u"%d", "GVL_Visu.InQueryId", NUM, u"1", u"", q(u"Query goods ID")),
    (826, 434, 100, 26, u"%.2f", "GVL_Param.rLadenFactorVY", NUM, u"0", u"1", q(u"Vertical load factor")),
    (826, 466, 100, 26, u"%.2f", "GVL_Param.rHandleW1", NUM, u"0", u"200", q(u"Light/medium W1")),
    (826, 498, 100, 26, u"%.2f", "GVL_Param.rHandleW2", NUM, u"0", u"200", q(u"Medium/heavy W2")),
    (1126, 434, 100, 26, u"%.2f", "GVL_Param.rHandleT1", NUM, u"0", u"", q(u"Light handling T1")),
    (1126, 466, 100, 26, u"%.2f", "GVL_Param.rHandleT2", NUM, u"0", u"", q(u"Medium handling T2")),
    (1126, 498, 100, 26, u"%.2f", "GVL_Param.rHandleT3", NUM, u"0", u"", q(u"Heavy handling T3")),
]

project = projects.open(PROJECT)  # noqa: F821


def fix_visu(name, targets):
    visu = project.find(name, True)[0]
    vel = visu.visual_element_list
    visu.begin_modify()
    want = {}
    for t in targets:
        want[(t[0], t[1], t[2], t[3])] = t
    found = {}
    for i in range(len(vel)):
        el = vel[i]
        try:
            key = (el.get_property("Position.X"), el.get_property("Position.Y"),
                   el.get_property("Position.Width"),
                   el.get_property("Position.Height"))
        except Exception:
            continue
        if key in want:
            found[key] = el.id
    log(u"%s: expect=%d matched=%d (total elements=%d)" % (
        name, len(targets), len(found), len(vel)))
    if len(found) != len(targets):
        for k in want:
            if k not in found:
                log(u"  MISS %r" % (k,))
        visu.end_modify()
        return False
    for key in found:
        vel.remove_id(found[key])
    for (x, y, w, h, text, var, itype, mn, mx, title) in targets:
        el = vel.add_element(VisualElementType.Rectangle)  # noqa: F821
        el.set_property("Position.X", x)
        el.set_property("Position.Y", y)
        el.set_property("Position.Width", w)
        el.set_property("Position.Height", h)
        el.set_property("Texts.Text", text)
        el.set_property("Text variables.Text variable", var)
        action = visu.input_action_factory.create_write_variable(
            var, itype, mn, mx, title, False, False)
        el.add_input_action(action, InputActionEventType.OnMouseClick)  # noqa: F821
    visu.end_modify()
    log(u"%s: removed+rebuilt %d, now total=%d" % (
        name, len(targets), len(vel)))
    return True


ok1 = fix_visu("VisuMain", MAIN)
ok2 = fix_visu("VisuStats", STATS)

# ---- VisuDialogs 库注入(尽力而为,不阻塞主修复) ----
app = project.find("Application", True)[0]
libman = None
for child in app.get_children(False):
    try:
        if unicode(child.get_name(False)) == u"Library Manager":
            libman = child
            break
    except Exception:
        pass
if libman is None:
    log(u"LIBMAN not found")
else:
    for meth in ["add_placeholder", "add_library", "add_managed_library"]:
        log(u"libman.%s hasattr=%r" % (meth, hasattr(libman, meth)))
    added = False
    for meth, args in [("add_placeholder", ("VisuDialogs",)),
                       ("add_library", ("VisuDialogs, * (System)",)),
                       ("add_library", ("VisuDialogs",))]:
        fn = getattr(libman, meth, None)
        if fn is None:
            continue
        try:
            fn(*args)
            log(u"LIB_ADD_OK via %s %r" % (meth, args))
            added = True
            break
        except Exception as e:
            log(u"LIB_ADD_FAIL %s %r -> %r" % (meth, args, e))
    if not added:
        log(u"LIB_ADD: none worked (rely on qualified dialog name)")

if ok1 and ok2:
    project.save()
    log(u"SAVE_OK")
else:
    log(u"NOT_SAVED (match failure, project untouched)")
project.close()
log(u"=== FIX_DONE ===")
out.close()
