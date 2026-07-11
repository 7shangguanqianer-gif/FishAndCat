# -*- coding: utf-8 -*-
# probe_p2_head.py -- 0711:P2 整页"写变量弹键盘"哑而 P1 正常。VisuMain=GUI 建,
# VisuStats=ScriptVisualization 建 → 导出两画面对象,diff 元素列表以外的画面级字段。
# 只读:export 不需要 save。
import io

PROJECT = r"F:\abb_wh_work\plc\AB_Project\ABB_WH.project"
RESULT = r"F:\abb_wh_work\tools\ab_scripting\probe_p2_head_result.txt"
XML_MAIN = r"F:\abb_wh_work\tools\ab_scripting\p2diag_main.xml"
XML_STATS = r"F:\abb_wh_work\tools\ab_scripting\p2diag_stats.xml"

out = io.open(RESULT, "w", encoding="utf-8")


def log(v):
    out.write(unicode(v) + u"\n")
    out.flush()


project = projects.open(PROJECT)  # noqa: F821
vm = project.find("VisuMain", True)[0]
vs = project.find("VisuStats", True)[0]
project.export_native([vm], XML_MAIN)
log(u"EXPORT_MAIN_OK")
project.export_native([vs], XML_STATS)
log(u"EXPORT_STATS_OK")
project.close()
log(u"=== P2_HEAD_EXPORT_DONE ===")
out.close()
