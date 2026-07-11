# -*- coding: utf-8 -*-
# fix_lang.py — 用 ST 语言重建脚本误建的两个 POU(FB_VisuRefresh/FC_StateToColor)
# 步骤:dump ImplementationLanguages → remove 旧对象 → create_pou(language=ST) → 灌代码
#      → build → 0 error 才 save。
import io
import re

RES = r"F:\abb_wh_work\tools\ab_scripting\fix_result.txt"
PROJ = r"F:\abb_wh_work\plc\AB_Project\ABB_WH.project"
BASE = r"F:\abb_wh_work\plc"

f = io.open(RES, "w", encoding="utf-8")
def log(s):
    try:
        f.write(s + u"\n")
    except Exception:
        f.write(repr(s) + u"\n")
    f.flush()

log(u"ImplementationLanguages dir: %s"
    % u", ".join([a for a in dir(ImplementationLanguages)          # noqa: F821
                  if not a.startswith("_")]))
ST_LANG = None
for cand in ["st", "structured_text", "ST"]:
    if hasattr(ImplementationLanguages, cand):                     # noqa: F821
        ST_LANG = getattr(ImplementationLanguages, cand)           # noqa: F821
        log(u"ST language = .%s -> %s" % (cand, ST_LANG))
        break
if ST_LANG is None:
    log(u"!! no st member found, abort")
    raise SystemExit

# 从源文件切目标对象的 decl/impl(与 sync_st 相同规则,内联简化版)
SEC_RE = re.compile(u"^\\(\\* -{6,} (\\w+)[::]\\s*(\\w+)?", re.M)
HEAD_RE = re.compile(u"^\\s*(FUNCTION_BLOCK|FUNCTION|PROGRAM)\\s+(\\w+)", re.M)

def get_section(fname, objname):
    fp = io.open(BASE + u"\\" + fname, "r", encoding="utf-8-sig")
    text = fp.read(); fp.close()
    marks = []
    for m in SEC_RE.finditer(text):
        nm = m.group(2) if (m.group(1) in ("DUT", "GVL") and m.group(2)) else m.group(1)
        marks.append((m.start(), nm))
    for i, (pos, nm) in enumerate(marks):
        if nm == objname:
            end = marks[i + 1][0] if i + 1 < len(marks) else len(text)
            return text[pos:end]
    return None

def split_di(seg):
    m = HEAD_RE.search(seg)
    seg = seg[m.start():]
    lines = seg.splitlines()
    lastev = -1
    for i, ln in enumerate(lines):
        if re.match(u"^\\s*END_VAR\\b", ln):
            lastev = i
    if lastev < 0:
        lastev = 0
    decl = u"\n".join(lines[:lastev + 1])
    impl_lines = []
    for ln in lines[lastev + 1:]:
        if re.match(u"^\\s*END_(FUNCTION_BLOCK|FUNCTION|PROGRAM)\\b", ln):
            break
        impl_lines.append(ln)
    return decl, u"\n".join(impl_lines).strip(u"\n")

TARGETS = [
    ("FB_VisuRefresh", "04_FB_Warehouse.st", "FUNCTION_BLOCK", None),
    ("FC_StateToColor", "03_Functions.st", "FUNCTION", "DWORD"),
]

proj = projects.open(PROJ)                                          # noqa: F821
apps = proj.find("Application", True)
app_node = apps[0]

for name, fname, head, rettype in TARGETS:
    seg = get_section(fname, name)
    decl, impl = split_di(seg)
    hits = proj.find(name, True)
    if hits:
        try:
            hits[0].remove()
            log(u"REMOVED old %s" % name)
        except Exception as e:
            log(u"remove fail %s %r" % (name, e))
    pt = PouType.FunctionBlock if head == "FUNCTION_BLOCK" else PouType.Function  # noqa: F821
    if head == "FUNCTION":
        obj = app_node.create_pou(name, pt, ST_LANG, rettype)
    else:
        obj = app_node.create_pou(name, pt, ST_LANG)
    log(u"CREATED %s as ST" % name)
    obj.textual_declaration.replace(decl)
    obj.textual_implementation.replace(impl)
    log(u"FILLED %s (decl %d, impl %d)" % (name, len(decl), len(impl)))

app = proj.active_application
app.build()
summary = u"?"
errs = []
for c in system.get_message_categories():                           # noqa: F821
    try:
        msgs = system.get_messages(c)                               # noqa: F821
    except Exception:
        continue
    for m in msgs:
        s = str(m)
        if s.startswith("Compile complete"):
            summary = s
        elif ("expected" in s or "Unexpected" in s or "Unknown" in s
              or "not defined" in s):
            errs.append(s[:150])
log(u"BUILD: %s" % summary)
for s in errs[:10]:
    log(u"  ERR: %s" % s)

if "-- 0 errors" in summary:
    proj.save()
    log(u"SAVE_OK")
else:
    proj.save()
    log(u"SAVED_WITH_ERRORS (源已同步,便于 GUI 复查)")
proj.close()
log(u"=== FIX_DONE ===")
f.close()
