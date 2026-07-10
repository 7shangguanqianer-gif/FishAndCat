# -*- coding: utf-8 -*-
import io
import System

RESULT = r"F:\abb_wh_spike\visu_native_20260710_1225\probe_utf8_type_details_result.txt"
TARGETS = [
    u"_3S.CoDeSys.LanguageModelManager.CompileOptions",
    u"_3S.CoDeSys.LanguageModelManager.CompileOptions+LocalOptions",
    u"_3S.CoDeSys.Core.LanguageModel.ILMCompileOptions2",
    u"_3S.CoDeSys.VisualObject.VisualProjectSettingsProvider",
    u"_3S.CoDeSys.VisualObject.IVisualProjectSettingsProvider3",
    u"_3S.CoDeSys.LanguageModelManagerConfigurators.CompilePropertiesModel",
]
out = io.open(RESULT, "w", encoding="utf-8")


def log(value):
    out.write(unicode(value) + u"\n")
    out.flush()


assemblies = list(System.AppDomain.CurrentDomain.GetAssemblies())
flags = (System.Reflection.BindingFlags.Public
         | System.Reflection.BindingFlags.NonPublic
         | System.Reflection.BindingFlags.Instance
         | System.Reflection.BindingFlags.Static)
for target in TARGETS:
    typ = None
    for assembly in assemblies:
        typ = assembly.GetType(target, False)
        if typ is not None:
            break
    log(u"=== %s found=%s ===" % (target, typ is not None))
    if typ is None:
        continue
    log(u"ASSEMBLY %s" % typ.Assembly.FullName)
    log(u"CONSTRUCTORS")
    for constructor in typ.GetConstructors(flags):
        log(u"  %s" % unicode(constructor))
    log(u"PROPERTIES")
    for prop in typ.GetProperties(flags):
        log(u"  %s : %s read=%s write=%s" %
            (prop.Name, prop.PropertyType.FullName, prop.CanRead, prop.CanWrite))
    log(u"FIELDS")
    for field in typ.GetFields(flags):
        log(u"  %s : %s static=%s" %
            (field.Name, field.FieldType.FullName, field.IsStatic))
    log(u"METHODS")
    for method in typ.GetMethods(flags):
        log(u"  %s" % unicode(method))
log(u"DONE")
out.close()
