# -*- coding: utf-8 -*-
# content_bisect.py — 内容级二分:定位 27 errors 的确切触发内容。不 save。
import io

RES = r"F:\abb_wh_work\tools\ab_scripting\content_result.txt"
PROJ = r"F:\abb_wh_work\plc\AB_Project\ABB_WH.project"

f = io.open(RES, "w", encoding="utf-8")
def log(s):
    try:
        f.write(s + u"\n")
    except Exception:
        f.write(repr(s) + u"\n")
    f.flush()

def build_and_report(tag):
    app.build()
    lines = []
    summary = u"?"
    for c in system.get_message_categories():          # noqa: F821
        try:
            msgs = system.get_messages(c)              # noqa: F821
        except Exception:
            continue
        for m in msgs:
            s = str(m)
            if s.startswith("Compile complete"):
                summary = s
            elif ("expected" in s or "Unexpected" in s or "Unknown" in s
                  or "not defined" in s or "instance" in s):
                lines.append(s[:150])
    log(u"[%s] %s" % (tag, summary))
    for s in lines[:8]:
        log(u"    ERR: %s" % s)

proj = projects.open(PROJ)                             # noqa: F821
app = proj.active_application
hits = proj.find("FB_VisuRefresh", True)
ti = hits[0].textual_implementation

CASES = [
    (u"minimal", u"GVL_Visu.VisuAlarm := GVL_Visu.VisuAlarm;"),
    (u"pure-FOR", u"FOR c := 0 TO GVL_Param.COLS - 1 DO\n"
                  u"    FOR r := 0 TO GVL_Param.TIERS - 1 DO\n"
                  u"        GVL_Visu.VisuSlotColor[c, r] := 16#00E8E8E8;\n"
                  u"    END_FOR\nEND_FOR"),
    (u"FOR+EN-comment", u"// state to color with flip r=0 top\n"
                  u"FOR c := 0 TO GVL_Param.COLS - 1 DO\n"
                  u"    FOR r := 0 TO GVL_Param.TIERS - 1 DO\n"
                  u"        GVL_Visu.VisuSlotColor[c, r] := 16#00E8E8E8;\n"
                  u"    END_FOR\nEND_FOR"),
    (u"FOR+CN-comment", u"// 1) 状态→颜色 + 上下翻转(显示行 r=0 是画面顶=层19)\n"
                  u"FOR c := 0 TO GVL_Param.COLS - 1 DO\n"
                  u"    FOR r := 0 TO GVL_Param.TIERS - 1 DO\n"
                  u"        GVL_Visu.VisuSlotColor[c, r] := 16#00E8E8E8;\n"
                  u"    END_FOR\nEND_FOR"),
    (u"FOR+call", u"FOR c := 0 TO GVL_Param.COLS - 1 DO\n"
                  u"    FOR r := 0 TO GVL_Param.TIERS - 1 DO\n"
                  u"        GVL_Visu.VisuSlotColor[c, r] :=\n"
                  u"            FC_StateToColor(iState := GVL_Visu.VisuSlotState[c, GVL_Param.TIERS - 1 - r]);\n"
                  u"    END_FOR\nEND_FOR"),
]
for tag, code in CASES:
    ti.replace(code)
    build_and_report(tag)

proj.close()
log(u"=== CONTENT_DONE ===")
f.close()
