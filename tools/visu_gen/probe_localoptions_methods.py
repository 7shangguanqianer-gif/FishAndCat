# -*- coding: utf-8 -*-
import io
import System

RESULT = r"F:\abb_wh_spike\visu_native_20260710_1225\probe_localoptions_methods_result.txt"
out = io.open(RESULT, "w", encoding="utf-8")


def log(value):
    out.write(unicode(value) + u"\n")
    out.flush()


assembly = [x for x in System.AppDomain.CurrentDomain.GetAssemblies()
            if unicode(x.GetName().Name) == u"LanguageModelManager.plugin"][0]
for type_name in [u"_3S.CoDeSys.LanguageModelManager.CompileOptions",
                  u"_3S.CoDeSys.LanguageModelManager.CompileOptions+LocalOptions"]:
    typ = assembly.GetType(type_name)
    log(u"=== %s ===" % type_name)
    flags = (System.Reflection.BindingFlags.Public
             | System.Reflection.BindingFlags.NonPublic
             | System.Reflection.BindingFlags.Instance
             | System.Reflection.BindingFlags.Static)
    for method in typ.GetMethods(flags):
        if method.Name in ["GetProjectOptionKey", "SetCompileOption", "GetCompileOption",
                           "get_Utf8Encoding", "set_Utf8Encoding",
                           "get_UTF8Encoding", "set_UTF8Encoding", "Update"]:
            log(u"%s static=%s abstract=%s public=%s family=%s private=%s" %
                (unicode(method), method.IsStatic, method.IsAbstract, method.IsPublic,
                 method.IsFamily, method.IsPrivate))
            try:
                body = method.GetMethodBody()
                data = body.GetILAsByteArray() if body is not None else None
                log(u"  IL=%s" % (u" ".join([u"%02X" % b for b in data]) if data else u"<none>"))
            except Exception as exc:
                log(u"  IL_FAIL %r" % exc)
log(u"DONE")
out.close()
