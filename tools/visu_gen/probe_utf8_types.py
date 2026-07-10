# -*- coding: utf-8 -*-
import io
import System

RESULT = r"F:\abb_wh_spike\visu_native_20260710_1225\probe_utf8_types_result.txt"
out = io.open(RESULT, "w", encoding="utf-8")


def log(value):
    out.write(unicode(value) + u"\n")
    out.flush()


for assembly in System.AppDomain.CurrentDomain.GetAssemblies():
    asm_name = unicode(assembly.GetName().Name)
    low_asm = asm_name.lower()
    if not (u"compiler" in low_asm or u"language" in low_asm
            or u"project" in low_asm or u"object" in low_asm):
        continue
    try:
        types = assembly.GetTypes()
    except System.Reflection.ReflectionTypeLoadException as exc:
        types = [x for x in exc.Types if x is not None]
    except Exception:
        continue
    asm_logged = False
    for typ in types:
        try:
            full_name = unicode(typ.FullName or typ.Name)
            candidates = []
            for prop in typ.GetProperties():
                name = unicode(prop.Name)
                if u"utf" in name.lower() or u"encod" in name.lower():
                    candidates.append(u"PROP " + name + u":" + unicode(prop.PropertyType.FullName))
            for method in typ.GetMethods():
                name = unicode(method.Name)
                if u"utf" in name.lower() or u"encod" in name.lower():
                    candidates.append(u"METHOD " + unicode(method))
            for field in typ.GetFields():
                name = unicode(field.Name)
                if u"utf" in name.lower() or u"encod" in name.lower():
                    candidates.append(u"FIELD " + name + u":" + unicode(field.FieldType.FullName))
            if (u"utf" in full_name.lower() or u"encod" in full_name.lower()
                    or candidates):
                if not asm_logged:
                    log(u"=== ASSEMBLY %s ===" % asm_name)
                    asm_logged = True
                log(u"TYPE %s" % full_name)
                for item in candidates:
                    log(u"  %s" % item)
        except Exception:
            pass
log(u"DONE")
out.close()
