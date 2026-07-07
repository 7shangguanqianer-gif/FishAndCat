# -*- coding: utf-8 -*-
# fix_awracell.py — 把 sync 误建为 FB 的 ST_AwraCell 改成真 DUT(AB 内 --runscript)
# 安全:只有"删旧+建新 DUT"都成功才 save;任一失败则不 save(工程保持原 FB 版本,功能不受影响)
import io
RES = r"F:\abb_wh_work\tools\ab_scripting\fix_awracell_result.txt"
_f = io.open(RES, "w", encoding="utf-8")
def log(*a):
    try:
        _f.write(u" ".join([unicode(x) for x in a]) + u"\n"); _f.flush()
    except Exception:
        pass
PROJ = r"F:\abb_wh_work\plc\AB_Project\ABB_WH.project"
DECL = (u"TYPE ST_AwraCell :\r\nSTRUCT\r\n    Id : INT;\r\n"
        u"    X  : INT;\r\n    Y  : INT;\r\nEND_STRUCT\r\nEND_TYPE")

proj = projects.open(PROJ)
apps = proj.find("Application", True); app = apps[0]
log("app create* methods:", [m for m in dir(app) if "creat" in m.lower()])

# 1) 删旧 ST_AwraCell(FB)
removed = False
for obj in proj.find("ST_AwraCell", True):
    log("existing ST_AwraCell:", str(obj)[:80])
    log("  remove-ish:", [m for m in dir(obj) if "remov" in m.lower() or "delet" in m.lower()])
    for meth in ("remove", "delete"):
        if hasattr(obj, meth):
            try:
                getattr(obj, meth)(); removed = True; log("  removed via", meth); break
            except Exception as e:
                log("  ", meth, "fail:", repr(e))
    if not removed:
        try:
            obj.parent.remove_object(obj); removed = True; log("  removed via parent.remove_object")
        except Exception as e:
            log("  parent.remove_object fail:", repr(e))

# 2) 建 DUT
created = False
if hasattr(app, "create_dut"):
    try:
        dut = app.create_dut("ST_AwraCell")
        dut.textual_declaration.replace(DECL)
        created = True; log("created DUT via create_dut")
    except Exception as e:
        log("create_dut fail:", repr(e))
else:
    log("app has NO create_dut")

# 3) 条件 save
if removed and created:
    try:
        app.build(); log("BUILD_CALLED")
    except Exception as e:
        log("build fail:", repr(e))
    proj.save(); log("SAVED_OK")
else:
    log("NOT_SAVED (removed=%s created=%s) -> 工程保持原 FB 版本,功能不受影响" % (removed, created))
proj.close(); log("=== FIX_DONE ===")
_f.close()
