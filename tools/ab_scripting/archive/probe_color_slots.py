# -*- coding: utf-8 -*-
# probe_color_slots.py -- 0710 深夜:定案 400 格颜色绑定挂在哪个属性槽。
# 方法:加 2 个测试矩形,分别往 Normal/Alarm 两个颜色变量槽写标记串,export XML 后
# 比对标记串落到的属性 Id,与 400 格现有绑定的 Id 401380312 对照。
# 全程不 save(export 不需要保存;测试矩形随不保存而消失)。
import io

PROJECT = r"F:\abb_wh_work\plc\AB_Project\ABB_WH.project"
RESULT = r"F:\abb_wh_work\tools\ab_scripting\probe_color_slots_result.txt"
XML = r"F:\abb_wh_work\tools\ab_scripting\probe_color_slots.xml"

out = io.open(RESULT, "w", encoding="utf-8")


def log(v):
    out.write(unicode(v) + u"\n")
    out.flush()


project = projects.open(PROJECT)  # noqa: F821
visu = project.find("VisuMain", True)[0]
vel = visu.visual_element_list
visu.begin_modify()

CANDS = [
    ("MARK_NORMAL_FILL", ["Color variables.Normal state.Fill color",
                          "Colorvariables.Normalstate.Fillcolor",
                          "Color variables.Fill color"]),
    ("MARK_ALARM_FILL", ["Color variables.Alarm state.Fill color",
                         "Colorvariables.Alarmstate.Fillcolor"]),
    ("MARK_TOGGLE", ["Color variables.Toggle color variable",
                     "Color variables.Toggle color"]),
    ("MARK_FRAME_N", ["Color variables.Normal state.Frame color"]),
]
for mark, paths in CANDS:
    el = vel.add_element(VisualElementType.Rectangle)  # noqa: F821
    el.set_property("Position.X", 1500)
    el.set_property("Position.Y", 40)
    el.set_property("Position.Width", 10)
    el.set_property("Position.Height", 10)
    okpath = None
    for p in paths:
        try:
            el.set_property(p, mark)
            okpath = p
            break
        except Exception as e:
            log(u"TRY_FAIL %s <- %s : %r" % (p, mark, e))
    log(u"%s => %s" % (mark, okpath if okpath else u"ALL PATHS FAILED"))
visu.end_modify()

project.export_native([visu], XML)
log(u"EXPORT_OK")
project.close()          # 不 save:测试矩形不留痕
log(u"=== PROBE_COLOR_SLOTS_DONE ===")
out.close()
