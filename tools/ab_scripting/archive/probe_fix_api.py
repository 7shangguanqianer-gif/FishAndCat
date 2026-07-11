# -*- coding: utf-8 -*-
# probe_fix_api.py -- 0710 夜:为"修 16 处输入 title"探三件事(只读,不保存):
#   ①visual_element_list 有无删除元素能力 ②get_property 能否读输入配置/文本
#   ③Application 的 Library Manager 对象与加库 API(VisuDialogs 注入用)
import io

PROJECT = r"F:\abb_wh_work\plc\AB_Project\ABB_WH.project"
RESULT = r"F:\abb_wh_work\tools\ab_scripting\probe_fix_api_result.txt"

out = io.open(RESULT, "w", encoding="utf-8")


def log(v):
    out.write(unicode(v) + u"\n")
    out.flush()


project = projects.open(PROJECT)  # noqa: F821

# ---- 1) visual_element_list 能力 ----
visu = project.find("VisuMain", True)[0]
vel = visu.visual_element_list
log(u"[1] vel type=%s" % type(vel).__name__)
log(u"[1] vel dir=%s" % u", ".join([n for n in dir(vel) if not n.startswith("_")]))
try:
    log(u"[1] len(vel)=%d" % len(vel))
except Exception as e:
    log(u"[1] len FAIL %r" % e)

# ---- 2) get_property 通道(拿第 5 个元素当样本;再扫元素找 Texts.Text 命中) ----
e0 = vel[0]
for path in ["Texts.Text", "Position.X", "Inputconfiguration",
             "Input configuration", "Inputconfiguration.OnMouseClick"]:
    try:
        v = e0.get_property(path)
        log(u"[2] get(%s)=%r" % (path, v))
    except Exception as ex:
        log(u"[2] get(%s) FAIL %r" % (path, ex))

# 扫出带 Texts.Text 的元素若干,打印 id+文本(用于定位 16 个输入框的近邻标签)
hits = 0
i = 0
while True:
    try:
        el = vel[i]
    except Exception:
        break
    try:
        t = el.get_property("Texts.Text")
        if t:
            log(u"[2] elem id=%s text=%r" % (el.id, t))
            hits += 1
            if hits >= 12:
                log(u"[2] ... (truncated)")
                break
    except Exception:
        pass
    i += 1
log(u"[2] scanned=%d" % i)

# ---- 3) Library Manager 对象与加库 API ----
apps = project.find("Application", True)
app = apps[0]
for child in app.get_children(False):
    try:
        nm = child.get_name(False)
    except Exception:
        nm = u"?"
    log(u"[3] app child: %s type=%s" % (nm, type(child).__name__))
    if u"ibrary" in unicode(nm):
        log(u"[3] LIBMAN dir=%s" % u", ".join(
            [n for n in dir(child) if not n.startswith("_")]))

project.close()
log(u"=== PROBE_FIX_API_DONE ===")
out.close()
