# -*- coding: utf-8 -*-
# fix_group_frames.py -- 0710:修"组框盖按钮"——整面透明矩形在 z 序顶层会截获点击
# (透明只是看得穿,不是点得穿)。改为 4×5=20 条 2px 边线条:只占边线带,内容区零遮挡。
# 组标题签(骑缝小签)保留——它们不压任何交互元素。
import io

PROJECT = r"F:\abb_wh_work\plc\AB_Project\ABB_WH.project"
RESULT = r"F:\abb_wh_work\tools\ab_scripting\fix_group_frames_result.txt"

out = io.open(RESULT, "w", encoding="utf-8")


def log(v):
    out.write(unicode(v) + u"\n")
    out.flush()


project = projects.open(PROJECT)  # noqa: F821
visu = project.find("VisuMain", True)[0]
vel = visu.visual_element_list
visu.begin_modify()

GROUPS = [(620, 80, 320, 188), (952, 80, 288, 188), (620, 280, 620, 68),
          (620, 360, 620, 220), (620, 592, 620, 52)]

# 删 5 个整面组框(按坐标四元组识别)
removed = 0
for i in range(len(vel) - 1, -1, -1):
    el = vel[i]
    try:
        key = (el.get_property("Position.X"), el.get_property("Position.Y"),
               el.get_property("Position.Width"), el.get_property("Position.Height"))
    except Exception:
        continue
    if key in [(x, y, w, h) for (x, y, w, h) in GROUPS]:
        # 防误删:整面组框无文本;组内恰好同尺寸的交互元素不存在(坐标即框)
        try:
            t = el.get_property("Texts.Text")
        except Exception:
            t = None
        if not t:
            vel.remove_id(el.id)
            removed += 1
log(u"removed_frames=%d (expect 5)" % removed)
if removed != 5:
    log(u"ABORT unexpected frame count, not saving")
    visu.end_modify()
    project.close()
    log(u"=== FIX_FRAMES_ABORTED ===")
    out.close()
    raise SystemExit


def strip(x, y, w, h):
    el = vel.add_element(VisualElementType.Rectangle)  # noqa: F821
    el.set_property("Position.X", x)
    el.set_property("Position.Y", y)
    el.set_property("Position.Width", w)
    el.set_property("Position.Height", h)


for (x, y, w, h) in GROUPS:
    strip(x, y, w, 2)                 # 上
    strip(x, y + h - 2, w, 2)         # 下
    strip(x, y, 2, h)                 # 左
    strip(x + w - 2, y, 2, h)         # 右
log(u"strips added=20")

visu.end_modify()
project.save()
log(u"SAVE_OK total=%d" % len(vel))
project.close()
log(u"=== FIX_FRAMES_DONE ===")
out.close()
