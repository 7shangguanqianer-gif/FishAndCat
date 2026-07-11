# -*- coding: utf-8 -*-
# fix_element_look.py -- 0710 深夜终局修复:400 格不显色根因=元素"外观来源"处于
# STYLE 模式(Id 1225741287='VISU_ST_STYLE',GUI 模板默认),颜色被全局样式接管,
# Normal state Fill color 绑定被无视。probe_color_slots diff 定案。
# 修法 A(首选):探 set_property 路径把 400 格切到 RELATIVE(原地改,零结构变动);
# 修法 B(兜底):删除 400 格按几何反推重建(脚本新元素默认 RELATIVE)+重建 crane
#              保 z 序(顺便补橙色填充——生成器漏设,白椭圆看不清)。
# 安全:400 格识别=严格几何谓词(28x20 网格阵列);任何阶段计数不符→不保存退出。
import io

PROJECT = r"F:\abb_wh_work\plc\AB_Project\ABB_WH.project"
RESULT = r"F:\abb_wh_work\tools\ab_scripting\fix_element_look_result.txt"

out = io.open(RESULT, "w", encoding="utf-8")


def log(v):
    out.write(unicode(v) + u"\n")
    out.flush()


project = projects.open(PROJECT)  # noqa: F821
visu = project.find("VisuMain", True)[0]
vel = visu.visual_element_list
visu.begin_modify()

# ---- 探路:在临时矩形上找"外观来源"的 property 路径与合法值 ----
probe = vel.add_element(VisualElementType.Rectangle)  # noqa: F821
probe.set_property("Position.X", 1500)
probe.set_property("Position.Y", 40)
probe.set_property("Position.Width", 10)
probe.set_property("Position.Height", 10)
PATHS = ["Element look", "Element Look", "Look", "Element behavior",
         "Elementlook", "Element style", "Style"]
VALUES = ["Relative", "VISU_ST_RELATIVE", "relative"]
combo = None
for p in PATHS:
    try:
        cur = probe.get_property(p)
        log(u"probe get(%s)=%r" % (p, cur))
    except Exception as e:
        log(u"probe get(%s) FAIL %r" % (p, e))
        continue
    for v in VALUES:
        try:
            probe.set_property(p, v)
            back = probe.get_property(p)
            log(u"probe set(%s,%s) -> readback %r" % (p, v, back))
            combo = (p, v)
            break
        except Exception as e:
            log(u"probe set(%s,%s) FAIL %r" % (p, v, e))
    if combo:
        break
vel.remove_id(probe.id)
log(u"COMBO=%r" % (combo,))

# ---- 识别 400 格(严格几何谓词)与 crane ----
grid_ids = {}
crane_id = None
for i in range(len(vel)):
    el = vel[i]
    try:
        x = el.get_property("Position.X")
        y = el.get_property("Position.Y")
        w = el.get_property("Position.Width")
        h = el.get_property("Position.Height")
    except Exception:
        continue
    if (w == 28 and h == 20 and 40 <= x <= 572 and 40 <= y <= 420
            and (x - 40) % 28 == 0 and (y - 40) % 20 == 0):
        c = (x - 40) // 28
        r = (y - 40) // 20
        grid_ids[(c, r)] = el.id
    if w == 28 and h == 20 and x == 0 and y == 0:
        crane_id = el.id
log(u"grid matched=%d crane=%r" % (len(grid_ids), crane_id))
if len(grid_ids) != 400:
    log(u"ABORT grid count != 400, not saving")
    visu.end_modify()
    project.close()
    log(u"=== FIX_LOOK_ABORTED ===")
    out.close()
    raise SystemExit

mode = None
if combo:
    # ---- 修法 A:原地切 RELATIVE ----
    p, v = combo
    fails = 0
    for key in grid_ids:
        el = None
        for i in range(len(vel)):
            if vel[i].id == grid_ids[key]:
                el = vel[i]
                break
        try:
            el.set_property(p, v)
        except Exception as e:
            fails += 1
            log(u"A_FAIL %r %r" % (key, e))
    log(u"A done fails=%d" % fails)
    mode = u"A" if fails == 0 else None

if mode is None:
    # ---- 修法 B:删除重建 400 格 + 重建 crane(保 z 序+补橙色) ----
    log(u"fallback B: rebuild grid")
    for key in grid_ids:
        vel.remove_id(grid_ids[key])
    for r in range(20):
        for c in range(20):
            el = vel.add_element(VisualElementType.Rectangle)  # noqa: F821
            el.set_property("Position.X", 40 + 28 * c)
            el.set_property("Position.Y", 40 + 20 * r)
            el.set_property("Position.Width", 28)
            el.set_property("Position.Height", 20)
            el.set_property("Color variables.Normal state.Fill color",
                            "GVL_Visu.VisuSlotColor[%d, %d]" % (c, r))
    if crane_id is not None:
        vel.remove_id(crane_id)
        crane = vel.add_element(VisualElementType.Ellipse)  # noqa: F821
        crane.set_property("Position.X", 0)
        crane.set_property("Position.Y", 0)
        crane.set_property("Position.Width", 28)
        crane.set_property("Position.Height", 20)
        crane.set_property("Absolute movement.Movement.X", "GVL_Visu.VisuCraneXpx")
        crane.set_property("Absolute movement.Movement.Y", "GVL_Visu.VisuCraneYpx")
        try:
            crane.set_property("Colors.Fill color", -37632)   # 16#FFFF6D00 橙
            log(u"crane fill int OK")
        except Exception as e:
            log(u"crane fill int FAIL %r" % e)
    mode = u"B"
    log(u"B done, total=%d" % len(vel))

visu.end_modify()
project.save()
log(u"SAVE_OK mode=%s" % mode)
project.close()
log(u"=== FIX_LOOK_DONE ===")
out.close()
