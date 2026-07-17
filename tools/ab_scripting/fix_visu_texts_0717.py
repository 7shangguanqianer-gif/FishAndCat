# -*- coding: utf-8 -*-
# fix_visu_texts_0717.py -- 治理D 画面过时文案两处(0716 回执瑕疵3 + Tests 计数):
#   P2 VisuStats 标题 "... demo IDs 901, 902, 903 ..." -> "... demo IDs 1..20 ..."(实际 demo ID=1..20)
#   P1 VisuMain 底部 "Tests 75/75" -> "Tests 77/77"(0717 T77 扩容后的自检基线;随 N_CASES 维护)
# 防呆:逐页扫描 Texts.Text,子串命中才替换;零命中记 NOT_FOUND(不误改);改后 save。
import io

RES = r"F:\abb_wh_work\tools\ab_scripting\fix_visu_texts_result.txt"
PROJ = r"F:\abb_wh_work\plc\AB_Project\ABB_WH.project"

f = io.open(RES, "w", encoding="utf-8")


def log(s):
    f.write(s + u"\n")
    f.flush()


REPLACEMENTS = [
    (u"901, 902, 903", u"1..20"),
    (u"901,902,903", u"1..20"),
    (u"75/75", u"77/77"),
]

proj = projects.open(PROJ)  # noqa: F821
changed = 0
for objname in ["VisuMain", "VisuStats", "VisuAdmin"]:
    hits = proj.find(objname, True)
    if not hits:
        log(u"%s NOT_FOUND_PAGE" % objname)
        continue
    vel = hits[0].visual_element_list
    for i in range(len(vel)):
        el = vel[i]
        try:
            txt = el.get_property("Texts.Text")
        except Exception:
            continue
        if txt is None:
            continue
        txt = unicode(txt)  # noqa: F821
        new = txt
        for old_s, new_s in REPLACEMENTS:
            if old_s in new:
                new = new.replace(old_s, new_s)
        if new != txt:
            el.set_property("Texts.Text", new)
            changed += 1
            log(u"%s[%d] CHANGED: %r -> %r" % (objname, i, txt, new))

if changed > 0:
    proj.save()
    log(u"SAVED changed=%d" % changed)
else:
    log(u"NOT_FOUND no matching text; nothing saved")
proj.close()
log(u"=== FIX_VISU_TEXTS_DONE ===")
f.close()
