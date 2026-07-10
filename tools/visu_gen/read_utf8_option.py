# -*- coding: utf-8 -*-
import io
import System

PROJECT = r"F:\abb_wh_spike\visu_native_20260710_1225\AB_Project\ABB_WH.project"
RESULT = r"F:\abb_wh_spike\visu_native_20260710_1225\read_utf8_option_result.txt"
TYPE_NAME = u"_3S.CoDeSys.LanguageModelManager.CompileOptions+LocalOptions"
out = io.open(RESULT, "w", encoding="utf-8")
project = projects.open(PROJECT)  # noqa: F821
target_type = None
for assembly in System.AppDomain.CurrentDomain.GetAssemblies():
    target_type = assembly.GetType(TYPE_NAME, False)
    if target_type is not None:
        break
flags = (System.Reflection.BindingFlags.Public
         | System.Reflection.BindingFlags.NonPublic
         | System.Reflection.BindingFlags.Static)
prop = target_type.GetProperty("Utf8Encoding", flags)
out.write(u"PRIMARY=%s\n" % project.primary)
out.write(u"DIRTY=%s\n" % project.dirty)
out.write(u"UTF8=%s\n" % prop.GetValue(None, None))
project.close()
out.close()
