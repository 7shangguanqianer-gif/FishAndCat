# -*- coding: utf-8 -*-
import io
import time

PROJECT = r"F:\abb_wh_spike\visu_native_20260710_1225\AB_Project\ABB_WH.project"
RESULT = r"F:\abb_wh_spike\visu_native_20260710_1225\run_test_spike_result.txt"
out = io.open(RESULT, "w", encoding="utf-8")


def log(value):
    out.write(unicode(value) + u"\n")
    out.flush()


project = projects.open(PROJECT)  # noqa: F821
app = project.active_application
online_app = online.create_online_application(app)  # noqa: F821
try:
    online_app.login(OnlineChangeOption.Try, True)  # noqa: F821
    log(u"LOGIN_OK state=%s" % online_app.application_state)
except Exception as exc:
    log(u"LOGIN_FAIL %r" % exc)
    project.close()
    out.close()
    raise SystemExit

if str(online_app.application_state) != "run":
    online_app.start()
    time.sleep(2)

written = False
for name, args in [("write_value", ("PRG_Test.xRunTests", 0, "TRUE")),
                   ("write_value", ("PRG_Test.xRunTests", "TRUE")),
                   ("set_prepared_value", ("PRG_Test.xRunTests", "TRUE"))]:
    try:
        getattr(online_app, name)(*args)
        if name == "set_prepared_value":
            online_app.write_prepared_values()
        log(u"WRITE_OK via=%s" % name)
        written = True
        break
    except Exception:
        pass
if not written:
    log(u"WRITE_FAIL")

time.sleep(3)
for variable in ["PRG_Test.iPassed", "PRG_Test.iFailed",
                 "PRG_Test.sLastFail", "PRG_Test.xAllPass"]:
    value = None
    for name in ["read_value", "get_value"]:
        try:
            value = getattr(online_app, name)(variable)
            break
        except Exception:
            pass
    log(u"%s = %s" % (variable, value))
try:
    online_app.logout()
    log(u"LOGOUT_OK")
except Exception as exc:
    log(u"LOGOUT_FAIL %r" % exc)
project.close()
log(u"RUN_TEST_SPIKE_DONE")
out.close()
