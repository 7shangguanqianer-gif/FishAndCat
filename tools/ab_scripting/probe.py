# -*- coding: utf-8 -*-
# probe.py — AB ScriptEngine 只读探针(IronPython 2.7,跑在 AutomationBuilder.exe 内)
# 目的:①确认无头脚本能启动 ②确认脚本许可激活 ③把工程 POU 树与 API 形状打印出来,
#       供第二遍写完整同步脚本用。全程只读,绝不 save。
# 结果写入 probe_result.txt(即使 stdout 被吞也能读到)。
import sys

RES = r"F:\abb_wh_work\tools\ab_scripting\probe_result.txt"
PROJ = r"F:\abb_wh_work\plc\AB_Project\ABB_WH.project"

f = open(RES, "w")
def log(*a):
    line = " ".join(str(x) for x in a)
    f.write(line + "\n"); f.flush()
    try:
        print(line)
    except Exception:
        pass

log("=== AB ScriptEngine probe start ===")
try:
    log("python:", sys.version)
except Exception as e:
    log("sys.version err:", e)

# 全局对象存在性(ScriptEngine 注入 projects/system/online/device)
for g in ["projects", "system", "online", "device"]:
    log("global '%s' present:" % g, g in dir(__builtins__) or g in globals())

opened = None
try:
    log("opening project ...")
    opened = projects.open(PROJ)      # noqa: F821  (ScriptEngine 全局)
    log("OPEN_OK path:", getattr(opened, "path", "?"))
except Exception as e:
    log("OPEN_FAIL:", repr(e))

def walk(node, depth=0, maxdepth=3):
    if depth > maxdepth:
        return
    try:
        kids = node.get_children()
    except Exception:
        kids = []
    for c in kids:
        try:
            nm = c.get_name()
        except Exception:
            nm = "<no name>"
        has_impl = hasattr(c, "textual_implementation")
        has_decl = hasattr(c, "textual_declaration")
        log("  " * depth + "- %s   [impl=%s decl=%s]" % (nm, has_impl, has_decl))
        walk(c, depth + 1, maxdepth)

if opened is not None:
    try:
        log("--- project tree (POU names as AB sees them) ---")
        walk(opened, 0, 3)
    except Exception as e:
        log("WALK_FAIL:", repr(e))
    # 找一个已知 POU,dump 其 API 形状(供写 replace 用)
    try:
        hits = opened.find("Functions", True)   # 可能匹配 03_Functions
        log("find('Functions') hits:", len(hits))
        if hits:
            obj = hits[0]
            log("sample obj name:", obj.get_name())
            ti = getattr(obj, "textual_implementation", None)
            if ti is not None:
                log("textual_implementation methods:",
                    [m for m in dir(ti) if not m.startswith("_")])
    except Exception as e:
        log("FIND_FAIL:", repr(e))
    try:
        opened.close()      # 不 save
        log("CLOSE_OK (no save)")
    except Exception as e:
        log("CLOSE_FAIL:", repr(e))

log("=== PROBE_DONE ===")
f.close()
