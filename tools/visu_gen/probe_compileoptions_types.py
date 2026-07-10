# -*- coding: utf-8 -*-
import io
import System

RESULT = r"F:\abb_wh_spike\visu_native_20260710_1225\probe_compileoptions_types_result.txt"
out = io.open(RESULT, "w", encoding="utf-8")


def log(value):
    out.write(unicode(value) + u"\n")
    out.flush()


assembly = None
for item in System.AppDomain.CurrentDomain.GetAssemblies():
    if unicode(item.GetName().Name) == u"LanguageModelManager.plugin":
        assembly = item
        break
root = assembly.GetType(u"_3S.CoDeSys.LanguageModelManager.CompileOptions")
local = assembly.GetType(u"_3S.CoDeSys.LanguageModelManager.CompileOptions+LocalOptions")
log(u"ROOT base=%s abstract=%s sealed=%s" %
    (root.BaseType.FullName, root.IsAbstract, root.IsSealed))
log(u"LOCAL base=%s abstract=%s sealed=%s" %
    (local.BaseType.FullName, local.IsAbstract, local.IsSealed))
for nested in root.GetNestedTypes(System.Reflection.BindingFlags.Public
                                  | System.Reflection.BindingFlags.NonPublic):
    log(u"NESTED %s base=%s abstract=%s" %
        (nested.FullName, nested.BaseType.FullName, nested.IsAbstract))
for typ in assembly.GetTypes():
    base = typ.BaseType
    while base is not None:
        if base == local:
            log(u"DERIVED %s abstract=%s" % (typ.FullName, typ.IsAbstract))
            for constructor in typ.GetConstructors(
                    System.Reflection.BindingFlags.Public
                    | System.Reflection.BindingFlags.NonPublic
                    | System.Reflection.BindingFlags.Instance):
                log(u"  CTOR %s" % unicode(constructor))
            break
        base = base.BaseType
log(u"DONE")
out.close()
