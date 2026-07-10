# -*- coding: utf-8 -*-
import io
import System

PROJECT = r"F:\abb_wh_spike\visu_native_20260710_1225\AB_Project\ABB_WH.project"
RESULT = r"F:\abb_wh_spike\visu_native_20260710_1225\set_utf8_spike_result.txt"
TYPE_NAME = u"_3S.CoDeSys.LanguageModelManager.CompileOptions+LocalOptions"
out = io.open(RESULT, "w", encoding="utf-8")


def log(value):
    out.write(unicode(value) + u"\n")
    out.flush()


project = projects.open(PROJECT)  # noqa: F821
target_type = None
for assembly in System.AppDomain.CurrentDomain.GetAssemblies():
    target_type = assembly.GetType(TYPE_NAME, False)
    if target_type is not None:
        break
if target_type is None:
    log(u"ABORT type not found")
    project.close()
    out.close()
    raise SystemExit

flags = (System.Reflection.BindingFlags.Public
         | System.Reflection.BindingFlags.NonPublic
         | System.Reflection.BindingFlags.Instance
         | System.Reflection.BindingFlags.Static)
for field_name in [u"SUB_KEY_COMPILE", u"UTF8_ENCODING"]:
    field = target_type.GetField(field_name, flags)
    log(u"CONST %s=%r" % (field_name, field.GetValue(None)))

utf8_property = target_type.GetProperty("Utf8Encoding", flags)
before = utf8_property.GetValue(None, None)
log(u"UTF8_BEFORE=%s" % before)
utf8_property.SetValue(None, True, None)
after = utf8_property.GetValue(None, None)
log(u"UTF8_AFTER=%s" % after)
if not after:
    log(u"ABORT setter did not persist in option service")
    project.close()
    out.close()
    raise SystemExit

# Option storage does not mark the project dirty by itself. A semantic no-op on
# the first existing warehouse cell forces the project container to serialize
# the updated compile option on save.
visu = project.find("VisuMain", True)[0]
visu.begin_modify()
visu.visual_element_list[0].set_property("Position.X", 40)
visu.end_modify()
log(u"DIRTY_AFTER_NOOP=%s" % project.dirty)
project.save()
log(u"SAVE_OK")
project.close()
log(u"DONE")
out.close()
