# -*- coding: utf-8 -*-
# dump_visu.py — 块3 画面自动化探针(0708,只读零风险)
# 目的:①列对象树(找可视化对象的真实类型)②把 VisuMain 导出成 native XML 看结构
#       ③dump 可视化对象的属性接口(找 textual/xml 直读通道)
# 结论去向:XML 可解 → 画面程序化生成路线成立;黑盒 → 回操作卡手搭。
import io

RES = r"F:\abb_wh_work\tools\ab_scripting\dump_visu_result.txt"
XML1 = r"F:\abb_wh_work\tools\ab_scripting\visu_main_native.xml"
XML2 = r"F:\abb_wh_work\tools\ab_scripting\visu_mgr_native.xml"
PROJ = r"F:\abb_wh_work\plc\AB_Project\ABB_WH.project"

f = io.open(RES, "w", encoding="utf-8")
def log(s):
    f.write(s + u"\n"); f.flush()

proj = projects.open(PROJ)                    # noqa: F821

# ---- 1) 对象树全列(名字+类型名;可视化对象类型点名) ----
log(u"===== OBJECT TREE =====")
def walk(objs, depth):
    for o in objs:
        try:
            nm = o.get_name(False)
        except Exception:
            try:
                nm = o.get_name()
            except Exception:
                nm = u"<noname>"
        tn = type(o).__name__
        log(u"%s%s  [%s]" % (u"  " * depth, nm, tn))
        try:
            walk(o.get_children(False), depth + 1)
        except Exception:
            pass
walk(proj.get_children(False), 0)

# ---- 2) 找可视化相关对象 ----
def find_first(name):
    hits = proj.find(name, True)
    return hits[0] if hits else None

visu = find_first("VisuMain")
mgr  = find_first("Visualization Manager")
log(u"")
log(u"VisuMain found: %r" % (visu is not None))
log(u"VisuManager found: %r" % (mgr is not None))

# ---- 3) VisuMain 属性接口(找直读通道) ----
if visu is not None:
    log(u"===== VisuMain dir() =====")
    names = [n for n in dir(visu) if not n.startswith("_")]
    log(u", ".join(names))
    for attr in ["textual_declaration", "textual_implementation", "xml", "get_xml"]:
        log(u"has %s: %r" % (attr, hasattr(visu, attr)))

# ---- 4) native export(官方支持含 visu;多签名逐试) ----
def try_export(obj, dest, tag):
    if obj is None:
        log(u"%s: skip (not found)" % tag)
        return
    tried = []
    # 签名1:proj.export_native(objects, destination)
    try:
        proj.export_native([obj], dest)
        log(u"%s: EXPORT_OK via proj.export_native(list, dest)" % tag)
        return
    except Exception as e:
        tried.append(u"proj.export_native(list,dest): %r" % e)
    # 签名2:带 recursive
    try:
        proj.export_native([obj], dest, True)
        log(u"%s: EXPORT_OK via proj.export_native(list, dest, True)" % tag)
        return
    except Exception as e:
        tried.append(u"proj.export_native(list,dest,True): %r" % e)
    # 签名3:对象自带
    try:
        obj.export_native(dest)
        log(u"%s: EXPORT_OK via obj.export_native(dest)" % tag)
        return
    except Exception as e:
        tried.append(u"obj.export_native(dest): %r" % e)
    for t in tried:
        log(u"%s: FAIL %s" % (tag, t))

try_export(visu, XML1, u"VisuMain")
try_export(mgr,  XML2, u"VisuManager")

proj.close()
log(u"=== DUMP_VISU_DONE ===")
f.close()
