# -*- coding: utf-8 -*-
# sync_st.py — 把 plc/*.st 源文件同步进 AB 工程(替换各 POU/GVL/DUT 的文本)+ 编译 + 保存
# 运行环境双模式:
#   A) AutomationBuilder.exe --profile="Automation Builder 2.9" --noUI --runscript=本文件
#      → 解析 + 逐对象替换 + build + (0 错才) save;结果写 sync_result.txt
#   B) 本地 CPython 直接跑 → 只打印解析切分结果(开发自测,不碰工程)
# 语法纪律:IronPython 2.7 兼容(无 f-string / 无 pathlib;io.open 指定 utf-8)。
import io
import os
import re
import sys

BASE = r"F:\abb_wh_work\plc"
PROJ = os.path.join(BASE, "AB_Project", "ABB_WH.project")
RES = r"F:\abb_wh_work\tools\ab_scripting\sync_result.txt"

# 对象 → (源文件, 类型)   类型: pou=decl+impl / gvl=仅decl / dut=仅decl
MAP = [
    ("ST_Good",             "01_DUTs.st", "dut"),
    ("ST_Slot",             "01_DUTs.st", "dut"),
    ("ST_Stats",            "01_DUTs.st", "dut"),
    ("E_MainState",         "01_DUTs.st", "dut"),
    ("ST_TestVec",          "07_GVL_Data_generated.st", "dut"),
    ("ST_AwraCell",         "07_GVL_Data_generated.st", "dut"),
    ("GVL_Param",           "02_GVL.st", "gvl"),
    ("GVL_WH",              "02_GVL.st", "gvl"),
    ("GVL_Visu",            "02_GVL.st", "gvl"),
    ("FC_CapCoef",          "03_Functions.st", "pou"),
    ("FC_IsPresetOccupied", "03_Functions.st", "pou"),
    ("FC_CheckFeasible",    "03_Functions.st", "pou"),
    ("FC_FitsPhysical",     "03_Functions.st", "pou"),
    ("FC_AxisTime",         "03_Functions.st", "pou"),
    ("FC_CalcTravelTime",   "03_Functions.st", "pou"),
    ("FC_CalcDualCycleTime","03_Functions.st", "pou"),
    ("FC_CalcPathLen",      "03_Functions.st", "pou"),
    ("FC_TMax",             "03_Functions.st", "pou"),
    ("FC_CalcScore",        "03_Functions.st", "pou"),
    ("FC_CalcPriority",     "03_Functions.st", "pou"),
    ("FC_StateToColor",     "03_Functions.st", "pou"),
    ("FC_LoadDemoGoods",    "07_GVL_Data_generated.st", "pou"),
    ("FB_InitWarehouse",    "04_FB_Warehouse.st", "pou"),
    ("FB_SelectSlot",       "04_FB_Warehouse.st", "pou"),
    ("FB_AssignAllGoods",   "04_FB_Warehouse.st", "pou"),
    ("FB_LocalSwapImprove", "04_FB_Warehouse.st", "pou"),
    ("FB_Stats",            "04_FB_Warehouse.st", "pou"),
    ("FB_AnimatePath",      "04_FB_Warehouse.st", "pou"),
    ("FB_BuildVisuPath",    "04_FB_Warehouse.st", "pou"),
    ("FB_ScanLoadProbe",    "04_FB_Warehouse.st", "pou"),
    ("FB_VisuRefresh",      "04_FB_Warehouse.st", "pou"),
    ("FB_GoodsInput",       "04_FB_Warehouse.st", "pou"),
    ("PRG_Main",            "05_PRG_Main.st", "pou"),
    ("PRG_Test",            "06_PRG_Test.st", "pou"),
    ("GVL_Data",            "07_GVL_Data_generated.st", "gvl"),
    ("GVL_WeightPolicy",    "08_GVL_WeightPolicy_generated.st", "gvl"),
]

_res_f = [None]
def log(*a):
    line = " ".join([str(x) for x in a])
    if _res_f[0] is None:
        try:
            _res_f[0] = io.open(RES, "w", encoding="utf-8")
        except Exception:
            _res_f[0] = False
    if _res_f[0]:
        _res_f[0].write(line + u"\n")
        _res_f[0].flush()
    try:
        print(line)
    except Exception:
        pass


def read_file(name):
    p = os.path.join(BASE, name)
    fp = io.open(p, "r", encoding="utf-8-sig")
    try:
        return fp.read()
    finally:
        fp.close()


# ---------------- 解析:把源文件切成 {对象名: 段文本} ----------------
# 标记两种格式:(* ---------- 名字:说明 *)  和  (* ---------- 类型:名字 *)(07 生成文件)
SEC_RE = re.compile(u"^\\(\\* -{6,} (\\w+)[::]\\s*(\\w+)?", re.M)
TYPE_WORDS = ("DUT", "GVL", "POU", "FC", "FB", "PRG")
HEAD_RE = re.compile(
    u"^\\s*(FUNCTION_BLOCK|FUNCTION|PROGRAM)\\s+(\\w+)", re.M)


def split_sections(text):
    """按 (* ---------- ... 标记切段;无标记的单对象文件 → 整文件一段。"""
    marks = []
    for m in SEC_RE.finditer(text):
        name = m.group(1)
        if name in TYPE_WORDS and m.group(2):
            name = m.group(2)            # "DUT:ST_TestVec" → ST_TestVec
        marks.append((m.start(), name))
    if not marks:
        return None                      # 单对象文件
    out = {}
    for i, (pos, name) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(text)
        out[name] = text[pos:end]
    return out


def strip_file_banner(seg):
    """去掉文件级横幅注释((* ==== ... ==== *)),保留对象级注释。"""
    return re.sub(u"^\\(\\* ={10,}.*?={10,} \\*\\)\\s*", u"", seg, flags=re.S)


def split_decl_impl(seg):
    """POU 段 → (decl, impl):decl=头行+全部 VAR 块(到最后一个 END_VAR);
    impl=其后到 END_FUNCTION(_BLOCK)/END_PROGRAM 之前。"""
    m = HEAD_RE.search(seg)
    if not m:
        return None, None
    seg = seg[m.start():]                # 掐掉段首注释前缀(归 decl 会重复横幅,舍弃)
    lines = seg.splitlines()
    last_endvar = -1
    for i, ln in enumerate(lines):
        if re.match(u"^\\s*END_VAR\\b", ln):
            last_endvar = i
    if last_endvar < 0:                  # 无变量块:decl=头行
        last_endvar = 0
    decl = u"\n".join(lines[:last_endvar + 1])
    rest = lines[last_endvar + 1:]
    # 去尾:END_FUNCTION / END_FUNCTION_BLOCK / END_PROGRAM 及其后的注释尾巴
    impl_lines = []
    for ln in rest:
        if re.match(u"^\\s*END_(FUNCTION_BLOCK|FUNCTION|PROGRAM)\\b", ln):
            break
        impl_lines.append(ln)
    impl = u"\n".join(impl_lines).strip(u"\n")
    return decl, impl


def parse_all():
    """→ {objname: (kind, decl, impl_or_None)};并报告缺段。"""
    cache = {}
    result = {}
    missing = []
    for name, fname, kind in MAP:
        if fname not in cache:
            cache[fname] = read_file(fname)
        text = cache[fname]
        secs = split_sections(text)
        if secs is None:
            seg = strip_file_banner(text)
        elif name in secs:
            seg = secs[name]
        else:
            missing.append((name, fname))
            continue
        if kind == "pou":
            decl, impl = split_decl_impl(seg)
            if decl is None:
                missing.append((name, fname))
                continue
            result[name] = (kind, decl, impl)
        else:                            # gvl / dut:全段即 declaration
            result[name] = (kind, seg.strip(u"\n"), None)
    return result, missing


# ---------------- AB 侧执行 ----------------
def in_ab():
    try:
        projects                          # noqa: F821
        return True
    except NameError:
        return False


def replace_text(doc, text):
    """ScriptTextDocument 兼容替换:优先 .replace(),回退 .text 赋值。
    行尾统一 CRLF(CODESYS 编辑器 Windows 换行;纯 \\n 实测触发词法错乱)。"""
    text = text.replace(u"\r\n", u"\n").replace(u"\n", u"\r\n")
    if hasattr(doc, "replace"):
        doc.replace(text)
        return "replace()"
    try:
        doc.text = text
        return ".text="
    except Exception as e:
        raise RuntimeError("no usable set-method: %r" % (e,))


def create_missing(proj, name, kind, decl):
    """对象缺席时在 Application 下创建(POU 类型从 decl 头行判断;GVL 直接建)。"""
    apps = proj.find("Application", True)
    if not apps:
        raise RuntimeError("Application node not found")
    app = apps[0]
    if kind == "gvl":
        obj = app.create_gvl(name)
        log("CREATED_GVL:", name)
        return obj
    if kind == "dut":                        # 0707 补:DUT 分支(create_dut 动态 API 已证可用;
        obj = app.create_dut(name)           #   缺此分支时 DUT 会误落到下方 pou 分支建成 FB)
        log("CREATED_DUT:", name)
        return obj
    m = HEAD_RE.search(decl)
    head = m.group(1) if m else "FUNCTION_BLOCK"
    try:
        pt = {"FUNCTION_BLOCK": PouType.FunctionBlock,      # noqa: F821
              "FUNCTION": PouType.Function,                 # noqa: F821
              "PROGRAM": PouType.Program}[head]             # noqa: F821
    except NameError:
        raise RuntimeError("PouType enum unavailable")
    if head == "FUNCTION":
        # FUNCTION 必须给 return_type(create_pou 的 ValueError 实测):从头行解析
        mrt = re.search(u"FUNCTION\\s+\\w+\\s*:\\s*([\\w\\.]+)", decl)
        rettype = mrt.group(1) if mrt else "INT"
        obj = app.create_pou(name, pt, None, rettype)
        log("CREATED_POU:", name, "type=FUNCTION ret=%s" % rettype)
    else:
        obj = app.create_pou(name, pt)
        log("CREATED_POU:", name, "type=%s" % head)
    return obj


def run_ab(parsed, missing):
    proj = projects.open(PROJ)            # noqa: F821
    log("OPEN_OK", PROJ)
    n_ok, n_fail, n_absent = 0, 0, []
    for name, fname, kind in MAP:
        if name not in parsed:
            continue
        kind2, decl, impl = parsed[name]
        hits = proj.find(name, True)
        if not hits:
            try:
                obj = create_missing(proj, name, kind2, decl)
                hits = [obj]
            except Exception as e:
                n_absent.append(name)
                log("ABSENT_AND_CREATE_FAIL:", name, "(from %s)" % fname, repr(e))
                continue
        obj = hits[0]
        try:
            how = replace_text(obj.textual_declaration, decl)
            if impl is not None and hasattr(obj, "textual_implementation"):
                replace_text(obj.textual_implementation, impl)
            log("SYNCED:", name, "(%s, decl %d ch, impl %s ch, via %s)"
                % (kind2, len(decl), len(impl) if impl is not None else "-", how))
            n_ok += 1
        except Exception as e:
            log("SYNC_FAIL:", name, repr(e))
            n_fail += 1
    log("--- summary: synced=%d fail=%d absent=%s missing_in_src=%s"
        % (n_ok, n_fail, n_absent, [m[0] for m in missing]))

    # ---- 编译 ----
    app = None
    try:
        app = proj.active_application
        log("active_application:", app)
    except Exception as e:
        log("no active_application:", repr(e))
        hits = proj.find("Application", True)
        app = hits[0] if hits else None
    build_err = None
    if app is not None:
        try:
            app.build()
            log("BUILD_CALLED")
        except Exception as e:
            build_err = repr(e)
            log("BUILD_FAIL:", build_err)
    # 读编译消息(尽力而为,API 形状不定,全部 try)
    err_cnt = None
    try:
        cats = system.get_message_categories()          # noqa: F821
        total_err = 0
        for c in cats:
            try:
                msgs = system.get_messages(c)           # noqa: F821
            except Exception:
                continue
            for msg in msgs:
                s = str(msg)
                if "error" in s.lower():
                    total_err += 1
                    if total_err <= 10:
                        log("MSG_ERR:", s[:200])
        err_cnt = total_err
        log("message-scan error-like lines:", total_err)
    except Exception as e:
        log("msg scan unavailable:", repr(e))

    # ---- 保存策略:同步失败=不保存;编译异常也保存(源码已同步,GUI 可复查) ----
    if n_fail == 0 and not missing:
        proj.save()
        log("SAVE_OK")
    else:
        log("NOT_SAVED (sync failures or missing sections)")
    proj.close()
    log("CLOSE_OK")


def main():
    parsed, missing = parse_all()
    log("parsed objects: %d, missing sections: %s"
        % (len(parsed), [m[0] for m in missing]))
    if not in_ab():
        log("--- local mode: dump section stats ---")
        for name, fname, kind in MAP:
            if name in parsed:
                k, d, i = parsed[name]
                log("  %-22s %-4s decl=%5d  impl=%s" %
                    (name, k, len(d), (len(i) if i is not None else "-")))
        log("LOCAL_PARSE_DONE")
        return
    run_ab(parsed, missing)
    log("=== SYNC_DONE ===")


main()
if _res_f[0]:
    _res_f[0].close()
