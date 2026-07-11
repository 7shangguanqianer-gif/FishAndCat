# -*- coding: utf-8 -*-
# build_three_pages_0713.py — 画面终局专场施工(方案丙:顶导航+流程栏;蓝图=docs/画面三页制施工蓝图_0711.md)
# 一次完成:P1 删临时三组+权重区/移已洗件按流程栏归位/增检测器·View·Tier·顶导航
#          P2 顶导航(回收 Back to P1 做 P1 tab)/ P3 VisuAdmin 全新建。
# 主动偏离蓝图(0713 工程判断,汇报待用户过目):
#   D1 地图 400 格不整体下移(蓝图字面 y90-560):避免 420 件搬移 + crane 像素常数 ST 联动;
#      顶导航条 y8-36,格栅 y40 起,零重叠;图例维持 2 列(不做横排)。
#   D2 回收两个已洗跳转钮做导航 tab(P1 的 P2 Records / P2 的 Back to P1)→ 洗单 19→17。
#   D3 State codes 说明箱迁 P3 诊断区(P1 ③区让位给按钮);P1 徽章 45/45 改 59/59。
# 安全:全部删除按坐标四元组精确匹配,数目不符=ABORT 不保存(fix_input_titles 先例);
#      移动目标缺失=ABORT 不保存(relayout_b 先例);VisuAdmin 已存在=ABORT(防重跑)。
# 洗单 17 处(施工后 computer use GUI 洗,见结果文件末尾清单)。
import io

PROJECT = r"F:\abb_wh_work\plc\AB_Project\ABB_WH.project"
RESULT = r"F:\abb_wh_work\tools\ab_scripting\build_three_pages_result.txt"

out = io.open(RESULT, "w", encoding="utf-8")
errors = []
wash = []          # 洗单收集:(page, x, y, label)


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


def q(s):
    return u"'" + s + u"'"          # IEC STRING 字面量(fix_input_titles 规范)


NUM = "VisuDialogs.Numpad"


def add_input(visu, x, y, w, h, text, variable, minimum, maximum, title):
    el = add_box(visu, x, y, w, h, text, variable)
    try:
        action = visu.input_action_factory.create_write_variable(
            variable, NUM, minimum, maximum, title, False, False)
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
    add_execute(visu, el, variable + " := TRUE;", InputActionEventType.OnMouseDown)   # noqa: F821
    add_execute(visu, el, variable + " := FALSE;", InputActionEventType.OnMouseUp)    # noqa: F821


def add_nav(visu, el, target):
    try:
        action = visu.input_action_factory.create_change_shown_visualization(
            ChangeShownVisualizationType.Assignment, target)  # noqa: F821
        el.add_input_action(action, InputActionEventType.OnMouseClick)  # noqa: F821
    except Exception as exc:
        msg = u"ACTION_FAIL navigation target=%s error=%r" % (target, exc)
        errors.append(msg)
        log(msg)


def frame(visu, x, y, w, h, title):
    add_box(visu, x, y, w, 2)
    add_box(visu, x, y + h - 2, w, 2)
    add_box(visu, x, y, 2, h)
    add_box(visu, x + w - 2, y, 2, h)
    add_box(visu, x + 8, y - 9, int(6.5 * len(title)) + 14, 18, title)


# ============================================================
project = projects.open(PROJECT)  # noqa: F821
log(u"OPEN_OK")

if project.find("VisuAdmin", True):
    log(u"ABORT VisuAdmin already exists (already built?)")
    project.close()
    raise SystemExit
vm = project.find("VisuMain", True)[0]
vs = project.find("VisuStats", True)[0]
app = project.active_application

# ============================================================
# P1 —— 删 / 移 / 增
# ============================================================
vel = vm.visual_element_list
n0 = len(vel)
log(u"P1_BASE count=%d (expect 540)" % n0)
vm.begin_modify()

# ---- 阶段A 删除清单(坐标四元组,64 项,缺一即 ABORT 不保存) ----
# A1: 0711 临时三组 29(图例第8格 (315,570)/(319,573) 保留,不在清单)
DEL = [
    (40, 594, 282, 82), (328, 594, 140, 82), (474, 594, 126, 82),
    (44, 598, 130, 16), (178, 598, 140, 16), (44, 618, 86, 20),
    (134, 618, 92, 20), (230, 618, 88, 20), (44, 640, 86, 20),
    (134, 640, 92, 20), (230, 640, 88, 20), (44, 662, 110, 18),
    (160, 662, 18, 18), (184, 662, 134, 18),
    (332, 598, 56, 16), (392, 598, 72, 16), (332, 618, 30, 20),
    (366, 618, 98, 20), (332, 640, 64, 20), (400, 640, 64, 20),
    (332, 662, 132, 16),
    (478, 598, 118, 16), (478, 618, 14, 20), (494, 618, 42, 20),
    (542, 618, 14, 20), (558, 618, 40, 20), (478, 640, 78, 20),
    (560, 640, 38, 20), (478, 662, 120, 16),
]
# A2: 权重区 9(4 标签+4 输入+Defaults;迁 P3 重建)
DEL += [
    (624, 616, 92, 24), (778, 616, 92, 24), (932, 616, 92, 24), (1086, 616, 92, 24),
    (720, 616, 56, 24), (874, 616, 56, 24), (1028, 616, 56, 24), (1182, 616, 56, 24),
    (620, 652, 300, 18),
]
# A3: 旧 5 组框线 20 + 组标题 5(流程栏框重画)
DEL += [
    (620, 96, 320, 2), (620, 266, 320, 2), (620, 96, 2, 172), (938, 96, 2, 172),
    (952, 96, 288, 2), (952, 266, 288, 2), (952, 96, 2, 172), (1238, 96, 2, 172),
    (620, 296, 620, 2), (620, 346, 620, 2), (620, 296, 2, 52), (1238, 296, 2, 52),
    (620, 376, 620, 2), (620, 578, 620, 2), (620, 376, 2, 204), (1238, 376, 2, 204),
    (620, 605, 620, 2), (620, 642, 620, 2), (620, 605, 2, 39), (1238, 605, 2, 39),
    (621, 80, 85, 18), (952, 80, 85, 18), (621, 278, 66, 18),
    (621, 358, 59, 18), (620, 586, 110, 18),
]
# A4: State codes 说明箱(迁 P3 诊断区重建)
DEL += [(900, 412, 330, 140)]

want = {}
for t in DEL:
    want[t] = want.get(t, 0) + 1          # 按计数匹配(兼容同坐标多件;当前清单实为 64 个唯一四元组)
found = {}
for i in range(len(vel)):
    el = vel[i]
    try:
        key = (el.get_property("Position.X"), el.get_property("Position.Y"),
               el.get_property("Position.Width"), el.get_property("Position.Height"))
    except Exception:
        continue
    if key in want:
        found.setdefault(key, []).append(el.id)
miss = []
for k in want:
    if len(found.get(k, [])) != want[k]:
        miss.append(u"%r expect=%d got=%d" % (k, want[k], len(found.get(k, []))))
if miss:
    for m in miss:
        log(u"DEL_MISS " + m)
    log(u"ABORT delete manifest mismatch (%d), NOT SAVED" % len(miss))
    vm.end_modify()
    project.close()
    raise SystemExit
n_del = 0
for k in found:
    for eid in found[k]:
        vel.remove_id(eid)
        n_del += 1
log(u"P1_DELETED=%d (expect %d)" % (n_del, len(DEL)))

# ---- 阶段B 移动(删除后重建索引;缺目标=ABORT 不保存) ----
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


def mv(el, x, y, w=None, h=None):
    if el is None:
        return
    el.set_property("Position.X", x)
    el.set_property("Position.Y", y)
    if w is not None:
        el.set_property("Position.Width", w)
    if h is not None:
        el.set_property("Position.Height", h)


# 顶栏:标题入导航条右区;P2 Records 钮回收为 P2 tab(已洗动作随行,长跑回归)
mv(one(u"Smart Storage Control - Warehouse Slot Optimization"), 640, 12, 600, 22)
mv(one(u"P2 Records"), 176, 8, 130, 28)
# ② 策略行 y308 -> y278
mv(one(u"FIFO"), 628, 278, 90, 32)
mv(one(u"Nearest"), 726, 278, 90, 32)
mv(one(u"Score"), 824, 278, 90, 32)
mv(one(u"AWRA-LS"), 922, 278, 100, 32)
mv(one(u"Current strategy: %d"), 1032, 278, 150, 32)
# ③ 运行按钮 y188/228 -> y426/466
mv(one(u"Run assign"), 960, 426, 128, 32)
mv(one(u"Animate"), 1100, 426, 128, 32)
mv(one(u"Save snapshot"), 960, 466, 128, 32)
mv(one(u"Live/Snapshot"), 1100, 466, 128, 32)
# ③ 统计 5 行(标签 by_text,值框 by_pos)y412..524 -> y422..518(节距 28->24)
STATS_MV = [(u"Total inbound / s", 412, 422), (u"Average item / s", 440, 446),
            (u"Space utilization / %", 468, 470), (u"Total path / m", 496, 494),
            (u"Violations", 524, 518)]
for txt, oldy, newy in STATS_MV:
    mv(one(txt), 628, newy, 150, 24)
    mv(at(784, oldy, 100, 24), 784, newy, 100, 24)
mv(one(u"Snapshot valid"), 628, 540, 150, 24)
mv(at(784, 552, 20, 20), 784, 540, 20, 20)
# ④ 当前件 y388 -> y578
mv(one(u"Target X"), 628, 578, 70, 24)
mv(at(702, 388, 50, 24), 702, 578, 50, 24)
mv(one(u"Target Y"), 760, 578, 70, 24)
mv(at(834, 388, 50, 24), 834, 578, 50, 24)
mv(one(u"Path m"), 892, 578, 60, 24)
mv(at(956, 388, 60, 24), 956, 578, 60, 24)
mv(one(u"Travel s"), 1024, 578, 64, 24)
mv(at(1092, 388, 60, 24), 1092, 578, 60, 24)
# 徽章:45/45 -> 59/59(过期数字),移到流程栏底
badge = one(u"Tests 45/45 | sim-ST cross-check | dwell=I/O")
if badge is not None:
    badge.set_property("Texts.Text", u"Tests 59/59 | sim-ST cross-check | dwell=I/O")
    mv(badge, 620, 616, 620, 18)

if missing:
    for m in missing:
        log(u"MOVE_MISS " + m)
    log(u"ABORT %d move targets missing, NOT SAVED" % len(missing))
    vm.end_modify()
    project.close()
    raise SystemExit
log(u"P1_MOVE_OK")

# ---- 阶段C 新增:导航条 / 流程栏框 / 检测器区 ----
# 导航条(y8-36;当前页=平面矩形无动作,其余=按钮绑跳转)
add_box(vm, 40, 8, 130, 28, u"P1 Console")
p3btn = add_button(vm, 312, 8, 130, 28, u"P3 Admin")
add_nav(vm, p3btn, "VisuAdmin")
wash.append((u"P1", 312, 8, u"nav P3 Admin"))
# 流程栏框:5 横线 + 2 竖线 + 4 段标签
for yy in (96, 266, 414, 566, 608):
    add_box(vm, 620, yy, 620, 2)
add_box(vm, 620, 96, 2, 514)
add_box(vm, 1238, 96, 2, 514)
for tag, yy in [(u"1 GOODS INPUT", 87), (u"2 STRATEGY + DETECTOR", 257),
                (u"3 RUN + STATS", 405), (u"4 CURRENT ITEM", 557)]:
    add_box(vm, 628, yy, int(6.5 * len(tag)) + 14, 18, tag)
# ② 检测器画像行(显示件,无动作不洗)
add_box(vm, 628, 320, 86, 20, u"N=%d", "GVL_Visu.VisuProfN")
add_box(vm, 720, 320, 100, 20, u"DENS=%.3f", "GVL_Visu.VisuProfDensity")
add_box(vm, 826, 320, 96, 20, u"SKEW=%.2f", "GVL_Visu.VisuProfSkew")
add_box(vm, 928, 320, 86, 20, u"W=%.1f", "GVL_Visu.VisuProfWMean")
add_box(vm, 1020, 320, 104, 20, u"HEAVY=%.2f", "GVL_Visu.VisuProfWHeavy")
add_box(vm, 1130, 320, 100, 20, u"STRAT=%d", "GVL_Visu.SelStrategy")
add_box(vm, 628, 344, 40, 20, u"REC:")
add_box(vm, 672, 344, 250, 20, u"%s", "GVL_Visu.VisuRecText")
add_box(vm, 1060, 344, 170, 20, u"Tier occ: %d", "GVL_Visu.VisuTierOcc")
# ② 控件行:Auto / View / Tier(3 处洗)
auto_btn = add_button(vm, 628, 374, 110, 26, u"Auto strategy")
add_execute(vm, auto_btn, "GVL_Visu.xAutoStrategy := NOT GVL_Visu.xAutoStrategy;")
wash.append((u"P1", 628, 374, u"Auto strategy toggle"))
add_lamp(vm, 744, 376, 22, 22, "GVL_Visu.xAutoStrategy")
add_box(vm, 772, 378, 130, 20, u"= auto apply")
view_btn = add_button(vm, 920, 374, 90, 26, u"View")
add_tap(vm, view_btn, "GVL_Visu.CmdViewCycle")
wash.append((u"P1", 920, 374, u"View cycle (state/freq/wear)"))
add_box(vm, 1016, 378, 80, 20, u"VIEW=%d", "GVL_Visu.iViewMode")
add_box(vm, 1104, 378, 36, 22, u"Tier")
add_input(vm, 1144, 374, 60, 26, u"%d", "GVL_Visu.InTierSel",
          u"-1", u"19", q(u"Tier highlight -1=off"))
wash.append((u"P1", 1144, 374, u"Tier select input"))

vm.end_modify()
log(u"P1_DONE count=%d" % len(vel))

# ============================================================
# P2 —— 顶导航(回收 Back to P1)+ 标题让位
# ============================================================
vel2 = vs.visual_element_list
log(u"P2_BASE count=%d" % len(vel2))
vs.begin_modify()
by_text2 = {}
by_pos2 = {}
for i in range(len(vel2)):
    el = vel2[i]
    try:
        t = el.get_property("Texts.Text")
    except Exception:
        t = None
    if t:
        by_text2.setdefault(t, []).append(el)
    try:
        key = (el.get_property("Position.X"), el.get_property("Position.Y"),
               el.get_property("Position.Width"), el.get_property("Position.Height"))
        by_pos2[key] = el
    except Exception:
        pass
miss2 = []
# 查询区大标题(650,6)删除(挡导航条;信息并入页标题)
qt = by_pos2.get((650, 6, 570, 30))
if qt is None:
    miss2.append(u"query title (650,6,570,30)")
# 页标题移导航条右区并改字(补 901/902/903 提示)
pt = by_pos2.get((40, 6, 400, 30))
if pt is None:
    miss2.append(u"page title (40,6,400,30)")
# Back to P1 回收为 P1 tab(已洗跳转动作随行)
bk = by_text2.get(u"Back to P1", [])
if len(bk) != 1:
    miss2.append(u"Back to P1 n=%d" % len(bk))
if miss2:
    for m in miss2:
        log(u"P2_MISS " + m)
    log(u"ABORT P2 targets missing, NOT SAVED")
    vs.end_modify()
    project.close()
    raise SystemExit
vel2.remove_id(qt.id)
pt.set_property("Texts.Text", u"Records / Query (demo IDs 901, 902, 903)")
mv(pt, 640, 12, 600, 22)
bk[0].set_property("Texts.Text", u"P1 Console")
mv(bk[0], 40, 8, 130, 28)
add_box(vs, 176, 8, 130, 28, u"P2 Records")
p3btn2 = add_button(vs, 312, 8, 130, 28, u"P3 Admin")
add_nav(vs, p3btn2, "VisuAdmin")
wash.append((u"P2", 312, 8, u"nav P3 Admin"))
vs.end_modify()
log(u"P2_DONE count=%d" % len(vel2))

# ============================================================
# P3 —— VisuAdmin 全新建
# ============================================================
va = app.create_visualobject("VisuAdmin")
log(u"P3_CREATED VisuAdmin")
va.begin_modify()
# 导航条 + 标题 + 状态镜像
p1btn3 = add_button(va, 40, 8, 130, 28, u"P1 Console")
add_nav(va, p1btn3, "VisuMain")
wash.append((u"P3", 40, 8, u"nav P1 Console"))
p2btn3 = add_button(va, 176, 8, 130, 28, u"P2 Records")
add_nav(va, p2btn3, "VisuStats")
wash.append((u"P3", 176, 8, u"nav P2 Records"))
add_box(va, 312, 8, 130, 28, u"P3 Admin")
add_box(va, 640, 12, 600, 22, u"P3 - Admin & Configuration")
add_box(va, 40, 44, 560, 24, u"Status: %s", "GVL_Visu.VisuStatusText")

# ---- ACCESS 组(A4)----
frame(va, 40, 100, 380, 164, u"ACCESS")
add_box(va, 52, 116, 60, 24, u"USER")
add_box(va, 116, 116, 220, 24, u"%s", "GVL_Visu.VisuUserText")
add_box(va, 52, 148, 60, 26, u"PIN")
add_input(va, 116, 148, 120, 26, u"%d", "GVL_Visu.InPinCode",
          u"0", u"9999", q(u"Admin PIN"))
wash.append((u"P3", 116, 148, u"PIN input"))
add_box(va, 252, 148, 50, 26, u"Fails")
add_box(va, 306, 148, 60, 26, u"%d", "PRG_Main.fbAuth.iFailCnt")
lg = add_button(va, 52, 184, 100, 30, u"Login")
add_tap(va, lg, "GVL_Visu.CmdLogin")
wash.append((u"P3", 52, 184, u"Login tap"))
lo = add_button(va, 160, 184, 100, 30, u"Logout")
add_tap(va, lo, "GVL_Visu.CmdLogout")
wash.append((u"P3", 160, 184, u"Logout tap"))
guard = add_box(va, 52, 224, 340, 20, u"Params guarded (login to change)")
setp(guard, "State variables.Invisible", "GVL_Visu.iUserLevel >= 1")

# ---- MAINTENANCE 组(A3)----
frame(va, 440, 100, 380, 164, u"MAINTENANCE")
add_box(va, 452, 116, 20, 26, u"X")
add_input(va, 476, 116, 60, 26, u"%d", "GVL_Visu.InMaintX",
          u"0", u"19", q(u"Column 0-19"))
wash.append((u"P3", 476, 116, u"Maint X input"))
add_box(va, 552, 116, 20, 26, u"Y")
add_input(va, 576, 116, 60, 26, u"%d", "GVL_Visu.InMaintY",
          u"0", u"19", q(u"Tier 0-19"))
wash.append((u"P3", 576, 116, u"Maint Y input"))
add_box(va, 652, 116, 150, 26, u"Blocked: %d", "GVL_Visu.VisuMaintCount")
mt = add_button(va, 452, 156, 120, 30, u"Set / Clear")
add_tap(va, mt, "GVL_Visu.CmdMaintToggle")
wash.append((u"P3", 452, 156, u"Maint Set/Clear tap"))
add_box(va, 452, 196, 350, 20, u"admin only - purple cells on P1 map")
add_box(va, 452, 224, 350, 20, u"survives Reset (physical state)")

# ---- WEIGHTS 组(迁自 P1;参数=fix_input_titles 原规格)----
frame(va, 840, 100, 400, 164, u"SCORE WEIGHTS")
WEIGHTS = [
    (u"Alpha eff.", 852, 116, "GVL_Param.rAlpha", u"Alpha efficiency"),
    (u"Beta stab.", 1032, 116, "GVL_Param.rBeta", u"Beta stability"),
    (u"Gamma en.", 852, 156, "GVL_Param.rGamma", u"Gamma energy"),
    (u"Delta res.", 1032, 156, "GVL_Param.rDelta", u"Delta reserve"),
]
for lab, x, y, var, title in WEIGHTS:
    add_box(va, x, y, 90, 26, lab)
    add_input(va, x + 94, y, 70, 26, u"%.2f", var, u"0", u"", q(title))
    wash.append((u"P3", x + 94, y, u"weight " + title))
add_box(va, 852, 196, 380, 20, u"Defaults: A=1.0 B=0.6 G=0.4 D=0.15")
add_box(va, 852, 224, 380, 20, u"guarded: admin login required")

# ---- A5 实测表(docs/A5执行时间实测_0711.md)----
frame(va, 40, 300, 780, 220, u"A5 EXECUTION TIME (measured 0711)")
A5 = [
    u"Group   Items  Cycles  Nominal   ms/item  placed/failed",
    u"S20      20     192    1.92 s     96.0      20/0",
    u"S120    120     560    5.60 s     46.7     120/0",
    u"S240    240    2056    20.6 s     85.7     240/0   (90% fill)",
    u"S240b   240    1880    18.8 s     78.3     240/0   (bigger slice)",
    u"Single-item suggest: <= 1 task cycle (10 ms, 400-slot scan)",
    u"Basis: cycle count x 10 ms nominal (PC-sim wall clock not used)",
]
yy = 316
for line in A5:
    add_box(va, 52, yy, 756, 22, line)
    yy += 26

# ---- 诊断/预留区(State codes 迁入 + RESERVED 留白)----
frame(va, 840, 300, 400, 220, u"DIAGNOSTICS / RESERVED")
add_box(va, 852, 316, 376, 120,
        u"State codes\nREADY / SUGGEST / ASSIGN_RUN\nIMPROVE / DONE_OK\n"
        u"ERR_* / ALARM_*\nCyan=query, Blue=path")
add_box(va, 852, 452, 340, 20, u"RESERVED (finals expansion)")

# ---- 页脚 ----
add_box(va, 40, 560, 800, 20,
        u"P3 admin page - new controls land here; P1 actions frozen (ISA-101)")
va.end_modify()
log(u"P3_DONE count=%d" % len(va.visual_element_list))

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
log(u"==== WASH LIST (%d) ====" % len(wash))
for pg, x, y, lab in wash:
    log(u"%s (%d,%d) %s" % (pg, x, y, lab))
project.close()
log(u"=== THREE_PAGES_DONE ===")
