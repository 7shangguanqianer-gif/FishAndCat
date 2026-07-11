# -*- coding: utf-8 -*-
# relayout_b.py -- 0710 方案B「分组工程面板」施工(用户拍板;设计稿=2_你要操作/画面排版三方案_0710.html)
# 治:#1 权重标签截断 #2 crane 无色 #3 图例无色样 #4 右缘呼吸边(≤1240) #5 徽章死数字
#  +:右面板重排五分组(INPUT/COMMANDS/STRATEGY/RESULTS/WEIGHTS),细线组框+组标题。
# 手法:
#  - 既有元素按 (Texts.Text 精确文本) 或 (坐标四元组) 双通道定位;任一目标缺失=ABORT 不保存;
#  - 组框矩形 Normal Fill 绑 GVL_Visu.dwTransparent(alpha=00 全透明→只显边线,不盖内容);
#  - crane/色块走 Color variables 通道(静态填色 API 不存在,0710 实证);
#  - 所有框宽按 6.5px/字符 预算校验(方案B mock 重叠教训)。
import io

PROJECT = r"F:\abb_wh_work\plc\AB_Project\ABB_WH.project"
RESULT = r"F:\abb_wh_work\tools\ab_scripting\relayout_b_result.txt"

out = io.open(RESULT, "w", encoding="utf-8")


def log(v):
    out.write(unicode(v) + u"\n")
    out.flush()


project = projects.open(PROJECT)  # noqa: F821
visu = project.find("VisuMain", True)[0]
vel = visu.visual_element_list
visu.begin_modify()

# ---------- 索引既有元素 ----------
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


# ---------- 布局表(全显式坐标;右面板 x∈[620,1240]) ----------
# 组1 GOODS INPUT (620,80)-(940,268)
mv(one(u"ID"), 628, 108, 60, 26);      mv(at(690, 90, 190, 26), 694, 108, 238, 26)
mv(one(u"Name"), 628, 140, 60, 26);    mv(at(690, 122, 190, 26), 694, 140, 238, 26)
mv(one(u"Weight"), 628, 172, 60, 26);  mv(at(690, 154, 190, 26), 694, 172, 238, 26)
mv(one(u"Freq"), 628, 204, 60, 26);    mv(at(690, 186, 190, 26), 694, 204, 238, 26)
mv(one(u"Volume"), 628, 236, 60, 26);  mv(at(690, 218, 190, 26), 694, 236, 238, 26)
# 组2 COMMANDS (952,80)-(1240,268);按钮 2 列 x=960/1100 宽128,行 y=108/148/188/228
mv(one(u"Add goods"), 960, 108, 128, 32);     mv(one(u"Load demo"), 1100, 108, 128, 32)
mv(one(u"Reset"), 960, 148, 128, 32);         mv(one(u"P2 Records"), 1100, 148, 128, 32)
mv(one(u"Run assign"), 960, 188, 128, 32);    mv(one(u"Animate"), 1100, 188, 128, 32)
mv(one(u"Save snapshot"), 960, 228, 128, 32); mv(one(u"Live/Snapshot"), 1100, 228, 128, 32)
# 组3 STRATEGY (620,280)-(1240,348);Mode 小框语义被组标题取代 → 删除
mode_el = one(u"Mode")
if mode_el is not None:
    vel.remove_id(mode_el.id)
mv(one(u"FIFO"), 628, 308, 90, 32);   mv(one(u"Nearest"), 726, 308, 90, 32)
mv(one(u"Score"), 824, 308, 90, 32);  mv(one(u"AWRA-LS"), 922, 308, 100, 32)
mv(one(u"Current strategy: %d"), 1032, 308, 150, 32)
# 组4 RESULTS (620,360)-(1240,580);label 与配对值框成对迁移(旧值框坐标=生成器公式)
mv(one(u"Target X"), 628, 388, 70, 24);  mv(at(696, 430, 50, 24), 702, 388, 50, 24)
mv(one(u"Target Y"), 760, 388, 70, 24);  mv(at(826, 430, 50, 24), 834, 388, 50, 24)
mv(one(u"Path m"), 892, 388, 60, 24);    mv(at(960, 430, 64, 24), 956, 388, 60, 24)
mv(one(u"Travel s"), 1024, 388, 64, 24); mv(at(1110, 430, 64, 24), 1092, 388, 60, 24)
STATS = [(u"Total inbound / s", 480, 412), (u"Average item / s", 508, 440),
         (u"Space utilization / %", 536, 468), (u"Total path / m", 564, 496),
         (u"Violations", 592, 524)]
for txt, oldy, y in STATS:
    mv(one(txt), 628, y, 150, 24)
    mv(at(776, oldy, 150, 24), 784, y, 100, 24)
mv(one(u"Snapshot valid"), 628, 552, 150, 24)
mv(at(1062, 381, 32, 32), 784, 552, 20, 20)      # 快照灯:随文本迁入结果组
sc = one(u"State codes\nREADY / SUGGEST / ASSIGN_RUN\nIMPROVE / DONE_OK\nERR_* / ALARM_*\nCyan=query, Blue=path")
mv(sc, 900, 412, 330, 140)
# 组5 SCORE WEIGHTS (620,592)-(1240,644);标签短化+92px,4 组 x=624/778/932/1086
WEIGHTS = [(u"Alpha efficiency", u"Alpha eff.", 624, "GVL_Param.rAlpha"),
           (u"Beta stability", u"Beta stab.", 778, "GVL_Param.rBeta"),
           (u"Gamma energy", u"Gamma en.", 932, "GVL_Param.rGamma"),
           (u"Delta reserve", u"Delta res.", 1086, "GVL_Param.rDelta")]
for full, short, x, _var in WEIGHTS:
    lab = one(full)
    if lab is not None:
        lab.set_property("Texts.Text", short)
        mv(lab, x, 616, 92, 24)
# 权重输入框(fix_input_titles 重建的已知坐标)
mv(at(688, 626, 58, 26), 624 + 96, 616, 56, 24)
mv(at(818, 626, 58, 26), 778 + 96, 616, 56, 24)
mv(at(948, 626, 58, 26), 932 + 96, 616, 56, 24)
mv(at(1078, 626, 58, 26), 1086 + 96, 616, 56, 24)
# Defaults + 徽章行 y=652(Banner 680 之上,无重叠)
mv(one(u"Defaults: A=1.0 B=0.6 G=0.4 D=0.15"), 620, 652, 300, 18)
badge = one(u"Online tests 45/45 - sim/ST cross-check - dwell point=I/O")
if badge is not None:
    badge.set_property("Texts.Text", u"Tests all green | sim-ST cross-check | dwell=I/O")
    mv(badge, 936, 652, 304, 18)
# 状态行/报警灯:右缘校验(灯 1200+32=1232≤1240 ✓ 不动);Status 不动

if missing:
    for m in missing:
        log(u"MISS " + m)
    log(u"ABORT %d targets missing, not saving" % len(missing))
    visu.end_modify()
    project.close()
    log(u"=== RELAYOUT_ABORTED ===")
    out.close()
    raise SystemExit
log(u"MOVE_OK all targets")


# ---------- 新增:组框(透明填充)+组标题+色块+crane 上色 ----------
def deco_rect(x, y, w, h, fill_binding=None, text=None):
    el = vel.add_element(VisualElementType.Rectangle)  # noqa: F821
    el.set_property("Position.X", x)
    el.set_property("Position.Y", y)
    el.set_property("Position.Width", w)
    el.set_property("Position.Height", h)
    if fill_binding:
        el.set_property("Color variables.Normal state.Fill color", fill_binding)
    if text is not None:
        el.set_property("Texts.Text", text)
    return el


TRANS = "GVL_Visu.dwTransparent"
GROUPS = [(620, 80, 320, 188, u"GOODS INPUT"),
          (952, 80, 288, 188, u"COMMANDS"),
          (620, 280, 620, 68, u"STRATEGY"),
          (620, 360, 620, 220, u"RESULTS"),
          (620, 592, 620, 52, u"SCORE WEIGHTS")]
for x, y, w, h, title in GROUPS:
    deco_rect(x, y, w, h, fill_binding=TRANS)            # 边线框(透明填充,不盖内容)
    deco_rect(x + 8, y - 9, int(6.5 * len(title)) + 14, 18, fill_binding=None,
              text=title)                                 # 组标题小签(白底盖框线,骑缝)
log(u"GROUPS_OK")

# 图例色块:按文本动态定位 7 个图例框,色样内嵌框内左端(居中文本不顶左端,不盖字)
LEGEND = [u"0 Empty (light gray)", u"1 Preset (dark gray)", u"2 Occupied (green)",
          u"3 Recommended (yellow)", u"4 Path (blue)", u"5 Alarm (red)",
          u"6 Query (cyan)"]
n_sw = 0
for i, txt in enumerate(LEGEND):
    box = one(txt)
    if box is None:
        continue
    bx = box.get_property("Position.X")
    by = box.get_property("Position.Y")
    bh = box.get_property("Position.Height")
    deco_rect(bx + 4, by + (bh - 16) // 2, 16, 16,
              fill_binding="GVL_Visu.aLegendColor[%d]" % i)
    n_sw += 1
log(u"LEGEND_SWATCHES=%d" % n_sw)

# crane 上橙色(0,0,28,20 的椭圆)
crane = by_pos.get((0, 0, 28, 20))
if crane is not None:
    crane.set_property("Color variables.Normal state.Fill color",
                       "GVL_Visu.dwCraneColor")
    log(u"CRANE_COLOR_OK")
else:
    log(u"CRANE not found (skip)")

visu.end_modify()
project.save()
log(u"SAVE_OK total=%d" % len(vel))
project.close()
log(u"=== RELAYOUT_B_DONE ===")
out.close()
