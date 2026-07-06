# -*- coding: utf-8 -*-
# sig_probe.py — 把探针版 PLC_PRG+FB 灌入(内存态)→ build → dump 9 errors 明细 → 恢复,不 save。
# 目的:拿到 SysTimeGetNs 真实签名不匹配的具体错误文本。
import io
import re

RES = r"F:\abb_wh_work\tools\ab_scripting\sig_result.txt"
PROJ = r"F:\abb_wh_work\plc\AB_Project\ABB_WH.project"

f = io.open(RES, "w", encoding="utf-8")
def log(s):
    try:
        f.write(s + u"\n")
    except Exception:
        f.write(repr(s) + u"\n")
    f.flush()

proj = projects.open(PROJ)                                   # noqa: F821
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
for c in system.get_message_categories():                    # noqa: F821
    try:
        msgs = system.get_messages(c)                        # noqa: F821
    except Exception:
        continue
    for m in msgs:
        s = str(m)
        if ("error" in s.lower() or "expected" in s or "Unknown" in s
                or "not defined" in s or "Cannot" in s or "C0" in s):
            log(u"MSG: %s" % s[:250])

plc.textual_declaration.replace(orig_decl)
plc.textual_implementation.replace(orig_impl)
proj.close()
log(u"=== SIG_DONE (not saved) ===")
f.close()
