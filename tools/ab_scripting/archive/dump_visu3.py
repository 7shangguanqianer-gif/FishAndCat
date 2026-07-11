# -*- coding: utf-8 -*-
# dump_visu3.py — 画面自动化探针 3.0(最后一发;dir() 对 ExtendedObject 无效=块2已知坑,
# 改 hasattr/试调逐名探测 import/export/create 通道)
import io

RES = r"F:\abb_wh_work\tools\ab_scripting\dump_visu3_result.txt"
PROJ = r"F:\abb_wh_work\plc\AB_Project\ABB_WH.project"

f = io.open(RES, "w", encoding="utf-8")
def log(s):
    f.write(s + u"\n"); f.flush()

proj = projects.open(PROJ)                    # noqa: F821
apps = proj.find("Application", True)
app = apps[0] if apps else None
log(u"app: %r" % (app is not None))

# hasattr 扫荡(dir 不可信,逐名问)
PROJ_CANDS = ["export_native", "import_native", "export_xml", "import_xml",
              "save", "save_as", "get_children", "find", "create_folder",
              "export_plcopenxml", "import_plcopenxml"]
APP_CANDS = ["create_pou", "create_dut", "create_gvl", "create_visualization",
             "create_visualisation", "create_visu", "create_object",
             "add_object", "create_folder", "import_native", "export_native",
             "get_children", "create_task_configuration"]
log(u"===== hasattr(proj, X) =====")
for n in PROJ_CANDS:
    log(u"  %s: %r" % (n, hasattr(proj, n)))
log(u"===== hasattr(app, X) =====")
for n in APP_CANDS:
    log(u"  %s: %r" % (n, hasattr(app, n)))

proj.close()
log(u"=== DUMP_VISU3_DONE ===")
f.close()
