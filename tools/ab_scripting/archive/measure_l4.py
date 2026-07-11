# -*- coding: utf-8 -*-
# measure_l4.py — L4 负载实测全自动(候选③ SysTimeGetNs 探针,监视页路线 0706 证伪后启用)
# 流程:导 SysTime 库 → 建 FB_ScanLoadProbeNs(ST)→ PLC_PRG 临时包夹 → build →
#       四组(IDLE/A/B/C)每组独立 login(统计清零)在线测量 → 恢复 PLC_PRG → build+save。
# 输出:l4_result.txt(全过程)+ 表格段(直接可抄进报告/CSV)。
import io
import re
import time

RES = r"F:\abb_wh_work\tools\ab_scripting\l4_result.txt"
PROJ = r"F:\abb_wh_work\plc\AB_Project\ABB_WH.project"
SRC09 = r"F:\abb_wh_work\plc\09_FB_ScanLoadProbeNs_备用.st"

f = io.open(RES, "w", encoding="utf-8")
def log(s):
    try:
        f.write(s + u"\n")
    except Exception:
        f.write(repr(s) + u"\n")
    f.flush()

HEAD_RE = re.compile(u"^\\s*(FUNCTION_BLOCK|FUNCTION|PROGRAM)\\s+(\\w+)", re.M)

def split_di(text):
    m = HEAD_RE.search(text)
    seg = text[m.start():]
    lines = seg.splitlines()
    lastev = -1
    for i, ln in enumerate(lines):
        if re.match(u"^\\s*END_VAR\\b", ln):
            lastev = i
    decl = u"\n".join(lines[:lastev + 1])
    impl_lines = []
    for ln in lines[lastev + 1:]:
        if re.match(u"^\\s*END_(FUNCTION_BLOCK|FUNCTION|PROGRAM)\\b", ln):
            break
        impl_lines.append(ln)
    return decl, u"\n".join(impl_lines).strip(u"\n")

proj = projects.open(PROJ)                                   # noqa: F821
log(u"OPEN_OK")

# ---- 1) SysTime 库 ----
apps = proj.find("Application", True)
app_node = apps[0]
libmgr = None
for o in app_node.get_children():
    try:
        nm = o.get_name()
    except Exception:
        continue
    if "Library Manager" in str(nm):
        libmgr = o
        break
if libmgr is None:
    log(u"!! Library Manager not found")
else:
    log(u"LibraryManager found; dir: %s"
        % u", ".join([a for a in dir(libmgr) if "lib" in a.lower()]))
    added = False
    try:
        if any("SysTime" in str(x) for x in libmgr.get_libraries()):
            added = True
            log(u"SysTime ref already present")
    except Exception:
        pass
    for call in ([] if added else [
                 lambda: libmgr.add_placeholder("SysTime", "SysTime, 3.5.17.0 (System)"),
                 lambda: libmgr.add_library("SysTime, 3.5.17.0 (System)")]):
        try:
            call()
            added = True
            log(u"SysTime library ADD_OK")
            break
        except Exception as e:
            log(u"add attempt fail: %r" % (e,))
    if not added:
        try:
            libs = [str(x) for x in libmgr.get_libraries()]
            log(u"existing libs: %s" % u"; ".join(libs[:30]))
            if any("SysTime" in x for x in libs):
                log(u"SysTime already present")
                added = True
        except Exception as e:
            log(u"get_libraries fail %r" % e)
    if not added:
        log(u"!! cannot ensure SysTime — abort before touching code")
        proj.close()
        f.close()
        raise SystemExit

# ---- 2) FB_ScanLoadProbeNs 对象 ----
src = io.open(SRC09, encoding="utf-8-sig").read()
src = re.sub(u"^\\(\\* ={10,}.*?={10,} \\*\\)\\s*", u"", src, flags=re.S)
decl9, impl9 = split_di(src)
hits = proj.find("FB_ScanLoadProbeNs", True)
if hits:
    obj9 = hits[0]
    log(u"FB_ScanLoadProbeNs exists")
else:
    obj9 = app_node.create_pou("FB_ScanLoadProbeNs",
                               PouType.FunctionBlock,          # noqa: F821
                               ImplementationLanguages.st)     # noqa: F821
    log(u"FB_ScanLoadProbeNs CREATED (ST)")
obj9.textual_declaration.replace(decl9)
obj9.textual_implementation.replace(impl9)
log(u"FB filled (decl %d, impl %d)" % (len(decl9), len(impl9)))

# ---- 3) PLC_PRG 临时包夹(保留原文,测完恢复) ----
hits = proj.find("PLC_PRG", True)
plc = hits[0]
orig_decl = plc.textual_declaration.text
orig_impl = plc.textual_implementation.text
log(u"PLC_PRG original decl: %r" % orig_decl[:200])
log(u"PLC_PRG original impl: %r" % orig_impl[:200])
probe_decl = orig_decl
if "fbProbeNs" not in probe_decl:
    if re.search(u"^VAR\\b", probe_decl, re.M):
        probe_decl = re.sub(u"^VAR\\b",
                            u"VAR\n    fbProbeNs : FB_ScanLoadProbeNs;",
                            probe_decl, count=1, flags=re.M)
    else:
        probe_decl = probe_decl + u"\nVAR\n    fbProbeNs : FB_ScanLoadProbeNs;\nEND_VAR"
probe_impl = (u"fbProbeNs(xStart := TRUE);\n"
              u"PRG_Main();\n"
              u"fbProbeNs(xStop := TRUE);\n"
              u"PRG_Test();")
plc.textual_declaration.replace(probe_decl)
plc.textual_implementation.replace(probe_impl)
log(u"PLC_PRG wrapped with probe")

# ---- 4) build ----
app = proj.active_application
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
log(u"BUILD(probe): %s" % summary)
restore_needed = True
results = []
if "-- 0 errors" not in summary:
    log(u"!! probe build failed — restoring immediately, no online run")
else:
    # ---- 5) 四组测量 ----
    GROUPS = [
        (u"IDLE", None, None, False),
        (u"A", 1, 200, True),
        (u"B", 20, 200, True),
        (u"C", 20, 2000, True),
    ]
    for tag, nbatch, npairs, run_assign in GROUPS:
        onapp = online.create_online_application(app)        # noqa: F821
        try:
            onapp.login(OnlineChangeOption.Try, True)        # noqa: F821
            if str(onapp.application_state) != "run":
                onapp.start()
            time.sleep(1.5)
            log(u"[%s] login+start ok state=%s" % (tag, onapp.application_state))

            def wr(expr, val):
                onapp.set_prepared_value(expr, val)
            def flush():
                onapp.write_prepared_values()
            def rd(expr):
                return onapp.read_value(expr)

            if run_assign:
                wr("GVL_Param.nBatchPerCycle", str(nbatch))
                wr("GVL_Param.nPairsPerCycle", str(npairs))
                flush()
                for btn in ["CmdReset", "CmdLoadDemo"]:
                    wr("GVL_Visu.%s" % btn, "TRUE")
                    flush()
                    time.sleep(1.0)
                wr("GVL_Visu.SelStrategy", "3")
                flush()
                wr("GVL_Visu.CmdRunAssign", "TRUE")
                flush()
                # 轮询 DONE_OK(上限 180s)
                ok = False
                for _ in range(180):
                    time.sleep(1.0)
                    st = str(rd("GVL_Visu.VisuStatusText"))
                    if "DONE_OK" in st:
                        ok = True
                        break
                    if "DONE_FAILED" in st or "ERR" in st:
                        log(u"[%s] abnormal status: %s" % (tag, st))
                        break
                log(u"[%s] status wait done ok=%s" % (tag, ok))
            else:
                time.sleep(20)                                # IDLE 空跑采样

            avg = rd("PLC_PRG.fbProbeNs.rAvgUs")
            mx = rd("PLC_PRG.fbProbeNs.rMaxUs")
            last = rd("PLC_PRG.fbProbeNs.rLastUs")
            n = rd("PLC_PRG.fbProbeNs.nSamples")
            log(u"[%s] rAvgUs=%s rMaxUs=%s rLastUs=%s nSamples=%s"
                % (tag, avg, mx, last, n))
            results.append((tag, nbatch, npairs, avg, mx, last, n))
        except Exception as e:
            log(u"[%s] ONLINE FAIL: %r" % (tag, e))
        finally:
            try:
                onapp.logout()
            except Exception:
                pass
        time.sleep(1.0)

# ---- 6) 恢复 PLC_PRG ----
plc.textual_declaration.replace(orig_decl)
plc.textual_implementation.replace(orig_impl)
app.build()
summary2 = u"?"
for c in system.get_message_categories():                    # noqa: F821
    try:
        msgs = system.get_messages(c)                        # noqa: F821
    except Exception:
        continue
    for m in msgs:
        s = str(m)
        if s.startswith("Compile complete"):
            summary2 = s
log(u"BUILD(restored): %s" % summary2)
if "-- 0 errors" in summary2:
    proj.save()
    log(u"SAVE_OK (PLC_PRG restored; FB_ScanLoadProbeNs+SysTime kept, harmless)")
else:
    log(u"!! restore build failed — NOT saved")
proj.close()

log(u"")
log(u"===== L4 结果表(SysTimeGetNs 探针,AB 仿真) =====")
log(u"组 | nBatch | nPairs | AvgUs | MaxUs | LastUs | nSamples")
for tag, nb, np_, avg, mx, last, n in results:
    log(u"%s | %s | %s | %s | %s | %s | %s"
        % (tag, nb, np_, avg, mx, last, n))
log(u"=== L4_DONE ===")
f.close()
