# -*- coding: utf-8 -*-
# lib_fix.py — 修 SysTime 库引用:枚举仓库准确名 → 清无效占位 → 加正确版本 → 编译验证。
import io
import re

RES = r"F:\abb_wh_work\tools\ab_scripting\libfix_result.txt"
PROJ = r"F:\abb_wh_work\plc\AB_Project\ABB_WH.project"

f = io.open(RES, "w", encoding="utf-8")
def log(s):
    try:
        f.write(s + u"\n")
    except Exception:
        f.write(repr(s) + u"\n")
    f.flush()

# ---- 1) 全局 librarymanager 模块:枚举仓库 ----
log(u"librarymanager dir: %s"
    % u", ".join([a for a in dir(librarymanager) if not a.startswith("_")]))   # noqa: F821
cands = []
try:
    repos = librarymanager.repositories                                        # noqa: F821
    for r in repos:
        try:
            libs = librarymanager.get_all_libraries(r)                         # noqa: F821
        except Exception:
            continue
        for L in libs:
            s = str(L)
            if "systime" in s.lower():
                cands.append(s)
except Exception as e:
    log(u"repo enum err %r" % e)
log(u"SysTime candidates in repo: %s" % u" || ".join(cands[:10]))

proj = projects.open(PROJ)                                                     # noqa: F821
apps = proj.find("Application", True)
app_node = apps[0]
libmgr = None
for o in app_node.get_children():
    if "Library Manager" in str(o.get_name()):
        libmgr = o
        break
log(u"proj libmgr dir: %s" % u", ".join([a for a in dir(libmgr) if not a.startswith("_")]))

# ---- 2) 现有引用清单(找无效占位) ----
try:
    cur = libmgr.get_libraries()
    for i, L in enumerate(cur):
        log(u"cur[%d] = %s" % (i, str(L)))
except Exception as e:
    log(u"get_libraries err %r" % e)

# 删掉之前加的无效 SysTime 占位(名字含 SysTime 的引用先移除再重加)
try:
    cur = libmgr.get_libraries()
    for L in list(cur):
        if "systime" in str(L).lower():
            try:
                libmgr.remove_library(str(L))
                log(u"removed stale ref: %s" % str(L))
            except Exception as e:
                log(u"remove fail %s: %r" % (str(L), e))
except Exception as e:
    log(u"cleanup err %r" % e)

# ---- 3) 加正确版本 ----
added = None
for cand in cands:
    try:
        libmgr.add_library(cand)
        added = cand
        log(u"ADD_OK: %s" % cand)
        break
    except Exception as e:
        log(u"add %s fail: %r" % (cand, e))
if added is None:
    log(u"!! no candidate added — trying plain names")
    for cand in ["SysTime", "SysTime, * (System)"]:
        try:
            libmgr.add_library(cand)
            added = cand
            log(u"ADD_OK: %s" % cand)
            break
        except Exception as e:
            log(u"add %s fail: %r" % (cand, e))

# ---- 4) 编译验证(灌探针版 PLC_PRG,内存态) ----
hits = proj.find("PLC_PRG", True)
plc = hits[0]
orig_decl = plc.textual_declaration.text
orig_impl = plc.textual_implementation.text
probe_decl = orig_decl if "fbProbeNs" in orig_decl else re.sub(
    u"^VAR\\b", u"VAR\n    fbProbeNs : FB_ScanLoadProbeNs;", orig_decl, count=1, flags=re.M)
plc.textual_declaration.replace(probe_decl)
plc.textual_implementation.replace(
    u"fbProbeNs(xStart := TRUE);\nPRG_Main();\nfbProbeNs(xStop := TRUE);\nPRG_Test();")
app = proj.active_application
app.build()
summary = u"?"
errs = []
for c in system.get_message_categories():                                      # noqa: F821
    try:
        msgs = system.get_messages(c)                                          # noqa: F821
    except Exception:
        continue
    for m in msgs:
        s = str(m)
        if s.startswith("Compile complete"):
            summary = s
        elif ("Unknown" in s or "not defined" in s or "Cannot" in s):
            errs.append(s[:150])
log(u"BUILD(probe with lib): %s" % summary)
for s in errs[:10]:
    log(u"  ERR: %s" % s)

# ---- 5) 恢复 PLC_PRG;若探针编译 0 错则保留库引用并 save ----
plc.textual_declaration.replace(orig_decl)
plc.textual_implementation.replace(orig_impl)
app.build()
proj.save()
log(u"restored+saved (library ref kept: %s)" % added)
proj.close()
log(u"=== LIBFIX_DONE ===")
f.close()
