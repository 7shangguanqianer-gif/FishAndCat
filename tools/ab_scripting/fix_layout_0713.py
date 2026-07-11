# -*- coding: utf-8 -*-
# fix_layout_0713.py — 三页制施工后几何微调(audit 三查的 4 处 P1 真碰撞)
#   ①四个流程段标签 x628→x1080(右缝位,上下净空逐格核过):
#     628 位压 Volume 行底 5px / 擦统计首行 1px
#   ②统计 5 行 y422..518 → y420,444,468,492,516;快照对 y540 → y542
#     (Violations 与 Snapshot valid 叠 2px → 改后紧邻分隔线 y566 无交)
# 只动无动作装饰/文本件,已洗件零接触。缺目标=ABORT 不保存。
import io

PROJECT = r"F:\abb_wh_work\plc\AB_Project\ABB_WH.project"
RESULT = r"F:\abb_wh_work\tools\ab_scripting\fix_layout_result.txt"

out = io.open(RESULT, "w", encoding="utf-8")


def log(v):
    out.write(unicode(v) + u"\n")  # noqa: F821
    out.flush()


project = projects.open(PROJECT)  # noqa: F821
vm = project.find("VisuMain", True)[0]
vel = vm.visual_element_list
vm.begin_modify()

by_text = {}
by_pos = {}
for i in range(len(vel)):
    el = vel[i]
    try:
        t = el.get_property("Texts.Text")
    except Exception:
        t = None
    if t:
        by_text.setdefault(t, []).append(el)
    try:
        key = (el.get_property("Position.X"), el.get_property("Position.Y"),
               el.get_property("Position.Width"), el.get_property("Position.Height"))
        by_pos[key] = el
    except Exception:
        pass
missing = []


def one(text):
    els = by_text.get(text, [])
    if len(els) != 1:
        missing.append(u"text=%r n=%d" % (text, len(els)))
        return None
    return els[0]


def at(x, y, w, h):
    el = by_pos.get((x, y, w, h))
    if el is None:
        missing.append(u"pos=%r" % ((x, y, w, h),))
    return el


def mv(el, x, y):
    if el is None:
        return
    el.set_property("Position.X", x)
    el.set_property("Position.Y", y)


# ① 段标签右移
mv(one(u"1 GOODS INPUT"), 1080, 87)
mv(one(u"2 STRATEGY + DETECTOR"), 1080, 257)
mv(one(u"3 RUN + STATS"), 1080, 405)
mv(one(u"4 CURRENT ITEM"), 1080, 557)
# ② 统计行 + 快照对
STATS = [(u"Total inbound / s", 422, 420), (u"Average item / s", 446, 444),
         (u"Space utilization / %", 470, 468), (u"Total path / m", 494, 492),
         (u"Violations", 518, 516)]
for txt, oldy, newy in STATS:
    mv(one(txt), 628, newy)
    mv(at(784, oldy, 100, 24), 784, newy)
mv(one(u"Snapshot valid"), 628, 542)
mv(at(784, 540, 20, 20), 784, 542)

if missing:
    for m in missing:
        log(u"MISS " + m)
    log(u"ABORT %d targets missing, NOT SAVED" % len(missing))
    vm.end_modify()
    project.close()
    raise SystemExit

vm.end_modify()
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
project.close()
log(u"=== FIX_LAYOUT_DONE ===")
