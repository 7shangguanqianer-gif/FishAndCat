# -*- coding: utf-8 -*-
# fix_p2_gen.py -- 0711:P2 写变量动作哑,唯一画面级差异=UniqueIdGenerator=12(远低于
# 对象数,后建动作疑 id 撞车;P1=60 工作)。修法:①探 add_element 是否推进计数器
# ②推高到 >=240 ③删 7 输入框按原参重建(动作重新分配到安全 id 区)④export 自查。
# 若计数器推不动 → 不保存退出,转"GUI 新建画面迁移"兜底(报告标注)。
import io
import re

PROJECT = r"F:\abb_wh_work\plc\AB_Project\ABB_WH.project"
RESULT = r"F:\abb_wh_work\tools\ab_scripting\fix_p2_gen_result.txt"
XML_TMP = r"F:\abb_wh_work\tools\ab_scripting\p2gen_check.xml"

out = io.open(RESULT, "w", encoding="utf-8")


def log(v):
    out.write(unicode(v) + u"\n")
    out.flush()


NUM = "VisuDialogs.Numpad"


def q(s):
    return u"'" + s + u"'"


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
visu = project.find("VisuStats", True)[0]
vel = visu.visual_element_list


def read_gen():
    project.export_native([visu], XML_TMP)
    xml = io.open(XML_TMP, encoding="utf-8").read()
    m = re.search(r'UniqueIdGenerator" Type="string">(\d+)<', xml)
    return int(m.group(1)) if m else -1


g0 = read_gen()
log(u"gen before=%d, elements=%d" % (g0, len(vel)))

visu.begin_modify()
# ---- 探:add 3 个 dummy 推不推计数器 ----
dummies = []
for _ in range(3):
    el = vel.add_element(VisualElementType.Rectangle)  # noqa: F821
    el.set_property("Position.X", 1500)
    el.set_property("Position.Y", 700)
    el.set_property("Position.Width", 8)
    el.set_property("Position.Height", 8)
    dummies.append(el.id)
visu.end_modify()
g1 = read_gen()
log(u"gen after +3 dummies=%d" % g1)

if g1 <= g0:
    # 推不动:清 dummy,不保存退出
    visu.begin_modify()
    for did in dummies:
        vel.remove_id(did)
    visu.end_modify()
    log(u"ABORT generator not advancing; fallback=GUI-created page migration")
    project.close()
    log(u"=== FIX_P2_GEN_ABORTED ===")
    out.close()
    raise SystemExit

# ---- 推高到 >=240 ----
visu.begin_modify()
need = 240 - g1
step = g1 - g0                        # 3 个 dummy 推了 step → 每个约 step/3
while need > 0:
    el = vel.add_element(VisualElementType.Rectangle)  # noqa: F821
    el.set_property("Position.X", 1500)
    el.set_property("Position.Y", 700)
    el.set_property("Position.Width", 8)
    el.set_property("Position.Height", 8)
    dummies.append(el.id)
    need -= max(1, step // 3)
for did in dummies:
    vel.remove_id(did)
log(u"dummies used=%d, removed all" % len(dummies))

# ---- 删 7 输入框(坐标匹配)重建 ----
found = {}
for i in range(len(vel)):
    el = vel[i]
    try:
        key = (el.get_property("Position.X"), el.get_property("Position.Y"),
               el.get_property("Position.Width"), el.get_property("Position.Height"))
    except Exception:
        continue
    for t in STATS:
        if key == (t[0], t[1], t[2], t[3]):
            found[key] = el.id
log(u"input boxes matched=%d (expect 7)" % len(found))
if len(found) != 7:
    log(u"ABORT match failure, not saving")
    visu.end_modify()
    project.close()
    log(u"=== FIX_P2_GEN_ABORTED ===")
    out.close()
    raise SystemExit
for key in found:
    vel.remove_id(found[key])
for (x, y, w, h, text, var, itype, mn, mx, title) in STATS:
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

g2 = read_gen()
log(u"gen final=%d, elements=%d" % (g2, len(vel)))
project.save()
log(u"SAVE_OK")
project.close()
log(u"=== FIX_P2_GEN_DONE ===")
out.close()
