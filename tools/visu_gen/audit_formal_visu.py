# -*- coding: utf-8 -*-
import io

BEFORE = r"F:\abb_wh_spike\visu_native_20260710_1225\ABB_WH_before_visu_pages.project"
AFTER = r"F:\abb_wh_work\plc\AB_Project\ABB_WH.project"
RESULT = r"F:\abb_wh_spike\visu_native_20260710_1225\audit_formal_visu_result.txt"
MANAGER_XML = r"F:\abb_wh_spike\visu_native_20260710_1225\VisualizationManager_formal.xml"
out = io.open(RESULT, "w", encoding="utf-8")


def log(value):
    out.write(unicode(value) + u"\n")
    out.flush()


def collect_text(project):
    result = {}

    def walk(objects, prefix):
        for obj in objects:
            try:
                name = obj.get_name()
            except Exception:
                name = u"<noname>"
            key = prefix + u"/" + unicode(name)
            for attr in ["textual_declaration", "textual_implementation"]:
                try:
                    doc = getattr(obj, attr)
                    result[key + u":" + attr] = unicode(doc.text)
                except Exception:
                    pass
            try:
                walk(obj.get_children(False), key)
            except Exception:
                pass

    walk(project.get_children(False), u"")
    return result


before_project = projects.open(BEFORE)  # noqa: F821
before_text = collect_text(before_project)
before_project.close()
log(u"BEFORE_TEXT_OBJECTS=%d" % len(before_text))

after_project = projects.open(AFTER)  # noqa: F821
after_text = collect_text(after_project)
log(u"AFTER_TEXT_OBJECTS=%d" % len(after_text))

added = sorted(set(after_text) - set(before_text))
removed = sorted(set(before_text) - set(after_text))
changed = sorted(key for key in set(before_text) & set(after_text)
                 if before_text[key] != after_text[key])
log(u"TEXT_ADDED=%d" % len(added))
log(u"TEXT_REMOVED=%d" % len(removed))
log(u"TEXT_CHANGED=%d" % len(changed))
for key in added + removed + changed:
    log(u"TEXT_DIFF %s" % key)

for name in ["VisuMain", "VisuStats", "WebVisu", "Visualization Manager"]:
    hits = after_project.find(name, True)
    log(u"FIND %s=%d" % (name, len(hits)))
    for obj in hits:
        try:
            if obj.is_visualobject:
                log(u"  VISU %s elements=%d" %
                    (obj.get_name(), len(obj.visual_element_list)))
        except Exception:
            pass

manager_hits = after_project.find("Visualization Manager", True)
if manager_hits:
    after_project.export_native([manager_hits[0]], MANAGER_XML)
    log(u"MANAGER_EXPORT_OK")
after_project.close()
log(u"AUDIT_DONE")
out.close()
