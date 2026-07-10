# -*- coding: utf-8 -*-
# dump_visu2.py — 画面自动化探针 2.0(0708)
# 发现1.0:工程无任何画面(用户没搭过)→ 改测"程序化创建"能力:
#   ①dump Application 的 create_* 工厂方法 ②若有 create_visualization:建 VisuProbe→
#   export_native 拿最小 XML 骨架→remove 清理 ③全程不 proj.save() = 零持久化风险。
import io

RES = r"F:\abb_wh_work\tools\ab_scripting\dump_visu2_result.txt"
XML = r"F:\abb_wh_work\tools\ab_scripting\visu_probe_native.xml"
PROJ = r"F:\abb_wh_work\plc\AB_Project\ABB_WH.project"

f = io.open(RES, "w", encoding="utf-8")
def log(s):
    f.write(s + u"\n"); f.flush()

proj = projects.open(PROJ)                    # noqa: F821

# ---- 1) 找 Application 对象(create_pou 等工厂都挂它上,sync_st.py 同款定位) ----
apps = proj.find("Application", True)
app = apps[0] if apps else None
log(u"Application found: %r" % (app is not None))

if app is not None:
    names = [n for n in dir(app) if not n.startswith("_")]
    log(u"===== Application dir() =====")
    log(u", ".join(names))
    log(u"")
    cands = [n for n in names if "visu" in n.lower() or "creat" in n.lower()
             or "import" in n.lower() or "export" in n.lower()]
    log(u"factory/io candidates: %s" % u", ".join(cands))

    # ---- 2) 尝试创建最小画面(不 save,零持久) ----
    made = None
    for meth, args in [
        ("create_visualization", ("VisuProbe",)),
        ("create_visualisation", ("VisuProbe",)),
        ("create_visu",          ("VisuProbe",)),
    ]:
        fn = getattr(app, meth, None)
        if fn is None:
            log(u"no method: %s" % meth)
            continue
        try:
            made = fn(*args)
            log(u"CREATED via %s: %r  type=%s" % (meth, made, type(made).__name__))
            break
        except Exception as e:
            log(u"%s FAILED: %r" % (meth, e))

    # ---- 3) 建成则 dump 接口 + export_native 拿骨架 ----
    if made is not None:
        mnames = [n for n in dir(made) if not n.startswith("_")]
        log(u"===== VisuProbe dir() =====")
        log(u", ".join(mnames))
        try:
            proj.export_native([made], XML)
            log(u"EXPORT_OK -> visu_probe_native.xml")
        except Exception as e:
            log(u"proj.export_native list FAILED: %r" % e)
            try:
                proj.export_native(made, XML)
                log(u"EXPORT_OK(single) -> visu_probe_native.xml")
            except Exception as e2:
                log(u"export_native single FAILED: %r" % e2)
        try:
            made.remove()
            log(u"REMOVED VisuProbe (no save anyway)")
        except Exception as e:
            log(u"remove FAILED: %r" % e)

# ---- 4) 顺便:project 级 import/export 能力(将来 import_native 回填用) ----
pnames = [n for n in dir(proj) if not n.startswith("_")]
pio = [n for n in pnames if "import" in n.lower() or "export" in n.lower()]
log(u"")
log(u"project import/export methods: %s" % u", ".join(pio))

proj.close()                                   # 不 save:一切改动不落盘
log(u"=== DUMP_VISU2_DONE ===")
f.close()
