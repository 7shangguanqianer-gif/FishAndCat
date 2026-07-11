# -*- coding: utf-8 -*-
# measure_l4c.py — A5 执行时间实测(0711 总库 A5;measure_l4b 的 400 库位规模版)
# 口径:任务级完成周期数(周期内 µs 三时钟源 AB 仿真恒 0,0705-0706 三源实证,勿再试);
#       X ms/件 = 完成周期数×10ms÷件数;真机预估=周期数×10ms 标称。
# 组设计:S20 基线衔接旧四组 / S120 报告主口径规模 / S240=90% 填充(dense_240 对齐)
#         / S240b 分片加大(伸缩性) / S1 单件推荐行为级即时验证(50ms 轮询上界)。
# 装货:FC_LoadDemoGoods 为追加式(0711 实证),连按 N 次 CmdLoadDemo = 20N 件;
#       疫苗(命令消费即复位)保证脚本每次写 TRUE 都构成新沿。
import io
import re
import time

RES = r"F:\abb_wh_work\tools\ab_scripting\l4c_result.txt"
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
orig_impl = plc.textual_implementation.text
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
    # (tag, load 次数=20N 件, nBatchPerCycle, nPairsPerCycle)
    GROUPS = [
        (u"S20",   1, 10, 200),
        (u"S120",  6, 10, 200),
        (u"S240", 12, 10, 200),
        (u"S240b", 12, 20, 2000),
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

        for tag, nloads, nbatch, npairs in GROUPS:
            try:
                wr("GVL_Param.nBatchPerCycle", str(nbatch))
                wr("GVL_Param.nPairsPerCycle", str(npairs))
                wr("GVL_Visu.CmdReset", "TRUE")
                time.sleep(1.0)
                for _i in range(nloads):
                    wr("GVL_Visu.CmdLoadDemo", "TRUE")
                    time.sleep(0.4)
                ngoods = num(rd("GVL_WH.iGoodsCount"))
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
                per_item = (cyc * 10.0 / ngoods) if ngoods else 0.0   # 10ms 任务标称
                placed = num(rd("GVL_WH.stStats.PlacedCnt"))
                failed = num(rd("GVL_WH.stStats.FailedCnt"))
                log(u"[%s] n=%d nBatch=%s nPairs=%s ok=%s status=%s cycles=%d "
                    u"wall=%.2fs per-item=%.2fms placed=%d failed=%d"
                    % (tag, ngoods, nbatch, npairs, ok, st.strip(), cyc, wall,
                       per_item, placed, failed))
                results.append((tag, ngoods, nbatch, npairs, cyc, wall, per_item,
                                placed, failed, ok))
            except Exception as e:
                log(u"[%s] FAIL %r" % (tag, e))

        # ---- S1:单件推荐行为级即时验证(加 1 件→读回 SUGGEST;50ms 轮询=上界粗验;
        #      定义级证据=FB_SelectSlot 无分片单 call 完成,含 400 格全扫) ----
        try:
            wr("GVL_Visu.CmdReset", "TRUE")
            time.sleep(1.0)
            wr("GVL_Visu.InGoodId", "1")
            wr("GVL_Visu.InGoodWeight", "12.5")
            wr("GVL_Visu.InGoodFreq", "8.0")
            wr("GVL_Visu.InGoodVolume", "0.4")
            time.sleep(0.2)
            t0 = time.time()
            wr("GVL_Visu.CmdAddGood", "TRUE")
            sug = u""
            for _ in range(40):                              # 2s 上限
                time.sleep(0.05)
                sug = str(rd("GVL_Visu.VisuStatusText"))
                if "SUGGEST" in sug:
                    break
            dt = (time.time() - t0) * 1000.0
            log(u"[S1] single-item suggest latency(wall upper bound) = %.0fms status=%s"
                % (dt, sug.strip()))
        except Exception as e:
            log(u"[S1] FAIL %r" % e)
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
log(u"===== A5 执行时间表(AB 仿真任务级实测;10ms 任务标称;演示批追加装货) =====")
log(u"组 | 件数 | nBatch | nPairs | 完成周期数 | 挂钟 s | ms/件 | placed | failed | DONE_OK")
for tag, n, nb, np_, cyc, wall, per, pl, fl, ok in results:
    log(u"%s | %d | %s | %s | %d | %.2f | %.2f | %d | %d | %s"
        % (tag, n, nb, np_, cyc, wall, per, pl, fl, ok))
log(u"=== L4C_DONE ===")
