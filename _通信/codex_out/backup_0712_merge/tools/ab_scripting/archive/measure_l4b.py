# -*- coding: utf-8 -*-
# measure_l4b.py — L4 任务级负载实测(终版口径):完成周期数 + 挂钟时间
# 背景:周期内 µs 三时钟源(LTIME/Monitor/SysTimeGetNs)在 AB PC 仿真全部恒 0(0705-0706 实证)
#       → 改测任务级:探针 nSamples 每周期+1=周期计数器;脚本挂钟 50ms 轮询。
# 前提:工程当前含 FB_ScanLoadProbeNs+SysTime 库(measure_l4 已留);本脚本自行包夹+恢复。
import io
import re
import time

RES = r"F:\abb_wh_work\tools\ab_scripting\l4b_result.txt"
PROJ = r"F:\abb_wh_work\plc\AB_Project\ABB_WH.project"

f = io.open(RES, "w", encoding="utf-8")
def log(s):
    try:
        f.write(s + u"\n")
    except Exception:
        f.write(repr(s) + u"\n")
    f.flush()

proj = projects.open(PROJ)                                   # noqa: F821
log(u"OPEN_OK")
hits = proj.find("PLC_PRG", True)
plc = hits[0]
orig_decl = plc.textual_declaration.text
orig_impl = plc.textual_impl if False else plc.textual_implementation.text
probe_decl = orig_decl if "fbProbeNs" in orig_decl else re.sub(
    u"^VAR\\b", u"VAR\n    fbProbeNs : FB_ScanLoadProbeNs;", orig_decl, count=1, flags=re.M)
plc.textual_declaration.replace(probe_decl)
plc.textual_implementation.replace(
    u"fbProbeNs(xStart := TRUE);\nPRG_Main();\nfbProbeNs(xStop := TRUE);\nPRG_Test();")
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
results = []
if "-- 0 errors" in summary:
    GROUPS = [
        (u"A", 1, 200),
        (u"B", 5, 200),
        (u"C", 20, 200),
        (u"D", 20, 2000),
    ]
    onapp = online.create_online_application(app)            # noqa: F821
    try:
        onapp.login(OnlineChangeOption.Try, True)            # noqa: F821
        if str(onapp.application_state) != "run":
            onapp.start()
        time.sleep(1.5)
        log(u"login+start state=%s" % onapp.application_state)

        def wr(expr, val):
            onapp.set_prepared_value(expr, val)
            onapp.write_prepared_values()
        def rd(expr):
            return onapp.read_value(expr)
        def num(v):
            s = str(v)
            return int(re.sub(u"[^0-9-]", u"", s.split("#")[-1]))

        for tag, nbatch, npairs in GROUPS:
            try:
                wr("GVL_Param.nBatchPerCycle", str(nbatch))
                wr("GVL_Param.nPairsPerCycle", str(npairs))
                wr("GVL_Visu.CmdReset", "TRUE")
                time.sleep(1.0)
                wr("GVL_Visu.CmdLoadDemo", "TRUE")
                time.sleep(1.0)
                wr("GVL_Visu.SelStrategy", "3")
                time.sleep(0.3)
                n0 = num(rd("PLC_PRG.fbProbeNs.nSamples"))
                t0 = time.time()
                wr("GVL_Visu.CmdRunAssign", "TRUE")
                ok = False
                st = u""
                for _ in range(3600):                        # 50ms × 3600 = 180s 上限
                    time.sleep(0.05)
                    st = str(rd("GVL_Visu.VisuStatusText"))
                    if "DONE_OK" in st:
                        ok = True
                        break
                    if "DONE_FAILED" in st or "ERR" in st or "ALARM" in st:
                        break
                t1 = time.time()
                n1 = num(rd("PLC_PRG.fbProbeNs.nSamples"))
                cyc = n1 - n0
                wall = t1 - t0
                per = (wall * 1000.0 / cyc) if cyc else 0.0
                log(u"[%s] nBatch=%s nPairs=%s ok=%s status=%s cycles=%d wall=%.2fs per-cycle=%.2fms"
                    % (tag, nbatch, npairs, ok, st.strip(), cyc, wall, per))
                results.append((tag, nbatch, npairs, cyc, wall, per, ok))
            except Exception as e:
                log(u"[%s] FAIL %r" % (tag, e))
    except Exception as e:
        log(u"ONLINE FAIL %r" % e)
    finally:
        try:
            onapp.logout()
        except Exception:
            pass
else:
    log(u"!! probe build failed")

plc.textual_declaration.replace(orig_decl)
plc.textual_implementation.replace(orig_impl)
app.build()
proj.save()
log(u"restored+saved")
proj.close()

log(u"")
log(u"===== L4 任务级负载表(AB 仿真实测,seed 同演示批 20 件) =====")
log(u"组 | nBatchPerCycle | nPairsPerCycle | 完成周期数 | 挂钟 s | 平均周期间隔 ms | DONE_OK")
for tag, nb, np_, cyc, wall, per, ok in results:
    log(u"%s | %s | %s | %d | %.2f | %.2f | %s" % (tag, nb, np_, cyc, wall, per, ok))
log(u"=== L4B_DONE ===")
f.close()
