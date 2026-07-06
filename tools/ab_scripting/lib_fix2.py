# -*- coding: utf-8 -*-
# lib_fix2.py — SysTime 符号不可见三连修:①placeholder 正规引用 ②命名空间限定 ③诊断兜底
import io
import re

RES = r"F:\abb_wh_work\tools\ab_scripting\libfix2_result.txt"
PROJ = r"F:\abb_wh_work\plc\AB_Project\ABB_WH.project"

f = io.open(RES, "w", encoding="utf-8")
def log(s):
    try:
        f.write(s + u"\n")
    except Exception:
        f.write(repr(s) + u"\n")
    f.flush()

def build_summary(app):
    app.build()
    summary = u"?"
    errs = []
    for c in system.get_message_categories():                    # noqa: F821
        try:
            msgs = system.get_messages(c)                        # noqa: F821
        except Exception:
            continue
        for m in msgs:
            s = str(m)
            if s.startswith("Compile complete"):
                summary = s
            elif ("Unknown" in s or "not defined" in s or "Cannot" in s
                  or "ambiguous" in s.lower()):
                errs.append(s[:160])
    return summary, errs

proj = projects.open(PROJ)                                       # noqa: F821
apps = proj.find("Application", True)
app_node = apps[0]
app = proj.active_application
libmgr = None
for o in app_node.get_children():
    if "Library Manager" in str(o.get_name()):
        libmgr = o
        break

# 探针版 PLC_PRG(整个会话保持,最后恢复)
hits = proj.find("PLC_PRG", True)
plc = hits[0]
orig_decl = plc.textual_declaration.text
orig_impl = plc.textual_implementation.text
probe_decl = orig_decl if "fbProbeNs" in orig_decl else re.sub(
    u"^VAR\\b", u"VAR\n    fbProbeNs : FB_ScanLoadProbeNs;", orig_decl, count=1, flags=re.M)
plc.textual_declaration.replace(probe_decl)
plc.textual_implementation.replace(
    u"fbProbeNs(xStart := TRUE);\nPRG_Main();\nfbProbeNs(xStop := TRUE);\nPRG_Test();")

ok = False

# ---- 方案1:placeholder 正规引用 ----
try:
    for L in list(libmgr.get_libraries()):
        if "systime" in str(L).lower():
            try:
                libmgr.remove_library(str(L))
                log(u"[1] removed %s" % str(L))
            except Exception as e:
                log(u"[1] remove fail %r" % e)
    try:
        libmgr.add_placeholder("SysTime", "SysTime, 3.5.17.0 (System)")
        log(u"[1] add_placeholder OK")
    except Exception as e:
        log(u"[1] add_placeholder fail: %r — fallback add_library" % (e,))
        libmgr.add_library("SysTime, 3.5.17.0 (System)")
    s1, e1 = build_summary(app)
    log(u"[1] BUILD: %s" % s1)
    for x in e1[:6]:
        log(u"    ERR: %s" % x)
    ok = "-- 0 errors" in s1
except Exception as e:
    log(u"[1] scheme fail %r" % e)

# ---- 方案2:FB 内命名空间限定 SysTime. ----
if not ok:
    hits9 = proj.find("FB_ScanLoadProbeNs", True)
    fb = hits9[0]
    d9 = fb.textual_declaration.text
    i9 = fb.textual_implementation.text
    d9n = d9.replace(u": SYSTIME;", u": SysTime.SYSTIME;")
    i9n = i9.replace(u"SysTimeGetNs(", u"SysTime.SysTimeGetNs(")
    fb.textual_declaration.replace(d9n)
    fb.textual_implementation.replace(i9n)
    s2, e2 = build_summary(app)
    log(u"[2] BUILD(namespace-qualified): %s" % s2)
    for x in e2[:6]:
        log(u"    ERR: %s" % x)
    ok = "-- 0 errors" in s2
    if not ok:
        fb.textual_declaration.replace(d9)
        fb.textual_implementation.replace(i9)

# ---- 方案3:诊断——列 AC500_Pm 等库中的时间函数候选 ----
if not ok:
    try:
        for L in libmgr.get_libraries():
            log(u"[3] lib: %s" % str(L))
    except Exception:
        pass

# ---- 收尾:成功→保留探针接线并 save(直接可跑测量);失败→恢复原样 save ----
if ok:
    proj.save()
    log(u"PROBE READY & SAVED (PLC_PRG 保持包夹,measure 可直接在线跑)")
else:
    plc.textual_declaration.replace(orig_decl)
    plc.textual_implementation.replace(orig_impl)
    app.build()
    proj.save()
    log(u"restored to non-probe state, saved")
proj.close()
log(u"=== LIBFIX2_DONE ok=%s ===" % ok)
f.close()
