# -*- coding: utf-8 -*-
r"""
doc_check.py — 文档联动自检(任务收尾五联动的第④步,防"执行单核账"类联动失效复发)
检查两类问题:
  A. 路径断链:扫描所有 .md 里引用的项目内路径(docs\xxx / sim\xxx / 1_给你看\xxx 等),
     验证文件真实存在(防搬家/改名后引用悬空);
  B. 易过时状态:静态文档(README/两份提示词/操作卡)里不允许出现"N 个用例/任务完成 N"
     类硬编码活状态——按模式扫描并报告(允许清单内的除外)。
退出码:0=全绿;1=有断链或违规(收尾流程必须处理后再提交)。
运行:python tools/doc_check.py
"""
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# A. 路径引用模式:反斜杠或正斜杠的项目内相对路径(常见目录前缀开头)
PATH_RE = re.compile(
    r"(?:docs|sim|plc|tools|_ref|1_给你看|2_你要操作)[\\/][\w\-./\\()一-鿿]+"
    r"\.(?:md|py|st|csv|png|docx|pdf|txt|bat)")
# 排除:代码块里的示例通配、明确标注为历史的行;
# "待产出"=显式的未来产物标记——文档里引用"执行后才会存在的文件"(截图/录屏等)
# 必须在同一行带上该标记,doc_check 才放行(防拿它当断链遮羞布:默认仍硬校验)
SKIP_LINE_HINTS = ("已迁移", "历史路径", "变更记录", "figs/fig", "figs\\fig",
                   "out/", "out\\", "待产出")   # 产物路径可再生,不作断链硬校验

# B. 易过时状态模式(只查"必须无状态"的静态文档)
STATELESS_DOCS = ["README.md", os.path.join("docs", "ClaudeCode接管提示词.md"),
                  os.path.join("docs", "Codex总对接提示词.md")]
VOLATILE_RE = re.compile(r"(\d+)\s*(?:个)?\s*(?:用例|任务完成|/1[0-9]\s*任务)")
VOLATILE_ALLOW = ("iPassed=59",)      # 最后一次有证据的AB基线；新计数须另行实跑后更新


def iter_md():
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in
                       (".git", "_ref", "out", "figs", "__pycache__", "AB_Project",
                        "backup_0712_merge")]
        for f in filenames:
            if f.endswith(".md"):
                yield os.path.join(dirpath, f)


def check_user_docx():
    """C. 用户层 Word 版新鲜度:1_给你看/2_你要操作 的每个 md 必须有同名 docx
    且 docx 不旧于 md(用户偏好:md 难读,一律配 Word;md=源,docx=生成物)。"""
    stale = []
    for d in ("1_给你看", "2_你要操作"):
        full = os.path.join(ROOT, d)
        if not os.path.isdir(full):
            continue
        for f in os.listdir(full):
            if f.endswith(".md"):
                md = os.path.join(full, f)
                dx = md[:-3] + ".docx"
                if not os.path.exists(dx):
                    stale.append(f"{d}\\{f} 缺同名 Word 版")
                elif os.path.getmtime(dx) + 2 < os.path.getmtime(md):
                    stale.append(f"{d}\\{f} 的 Word 版旧于 md")
    return stale


def main():
    broken, volatile = [], []
    for md in iter_md():
        rel_md = os.path.relpath(md, ROOT)
        try:
            text = open(md, encoding="utf-8").read()
        except UnicodeDecodeError:
            text = open(md, encoding="utf-8", errors="replace").read()
        for ln_no, line in enumerate(text.splitlines(), 1):
            if any(h in line for h in SKIP_LINE_HINTS):
                continue
            for m in PATH_RE.finditer(line):
                p = m.group(0).replace("\\", os.sep).replace("/", os.sep)
                if not os.path.exists(os.path.join(ROOT, p)):
                    broken.append(f"{rel_md}:{ln_no}  {m.group(0)}")
    for rel in STATELESS_DOCS:
        full = os.path.join(ROOT, rel)
        if not os.path.exists(full):
            broken.append(f"(自检清单本身断链){rel}")
            continue
        text = open(full, encoding="utf-8").read()
        for ln_no, line in enumerate(text.splitlines(), 1):
            if any(a in line for a in VOLATILE_ALLOW):
                continue
            if VOLATILE_RE.search(line):
                volatile.append(f"{rel}:{ln_no}  {line.strip()[:60]}")

    stale_docx = check_user_docx()
    ok = not broken and not volatile and not stale_docx
    if broken:
        print(f"❌ 路径断链 {len(broken)} 处:")
        for b in broken:
            print("  ", b)
    if volatile:
        print(f"❌ 静态文档含易过时状态 {len(volatile)} 处(改为'以命令输出为准'):")
        for v in volatile:
            print("  ", v)
    if stale_docx:
        print(f"❌ 用户层 Word 版缺失/过时 {len(stale_docx)} 处"
              f"(跑 python tools/make_user_docs.py):")
        for s in stale_docx:
            print("  ", s)
    if ok:
        print("✅ doc_check 全绿:路径引用完好,静态文档无易过时状态,用户层 Word 版齐且新")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
