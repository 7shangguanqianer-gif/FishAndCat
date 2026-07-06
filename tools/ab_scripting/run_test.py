# -*- coding: utf-8 -*-
# run_test.py — 在线闭环:仿真登录 → 启动 → 置 PRG_Test.xRunTests → 读回 iPassed/iFailed
import io
import time

RES = r"F:\abb_wh_work\tools\ab_scripting\runtest_result.txt"
PROJ = r"F:\abb_wh_work\plc\AB_Project\ABB_WH.project"

f = io.open(RES, "w", encoding="utf-8")
def log(s):
    try:
        f.write(s + u"\n")
    except Exception:
        f.write(repr(s) + u"\n")
    f.flush()

proj = projects.open(PROJ)                              # noqa: F821
app = proj.active_application
log(u"opened; active app ok")

onapp = online.create_online_application(app)           # noqa: F821
log(u"online app created; dir: %s"
    % u", ".join([a for a in dir(onapp) if not a.startswith("_")]))

# 仿真模式(若 API 在)
try:
    dev = onapp.application
    log(u"onapp.application = %s" % dev)
except Exception:
    pass
try:
    if hasattr(onapp, "is_simulation_mode"):
        log(u"is_simulation_mode = %s" % onapp.is_simulation_mode)
except Exception as e:
    log(u"simu check err %r" % e)

try:
    onapp.login(OnlineChangeOption.Try, True)           # noqa: F821
    log(u"LOGIN_OK; state=%s" % onapp.application_state)
except Exception as e:
    log(u"LOGIN_FAIL: %r" % e)
    proj.close()
    f.close()
    raise SystemExit

try:
    if str(onapp.application_state) != "run":
        onapp.start()
        time.sleep(2)
    log(u"STATE after start: %s" % onapp.application_state)
except Exception as e:
    log(u"start err %r" % e)

def wr(expr, val):
    for fn, args in [("write_value", (expr, 0, val)),
                     ("write_value", (expr, val)),
                     ("set_prepared_value", (expr, val))]:
        try:
            getattr(onapp, fn)(*args)
            return u"%s%s" % (fn, args)
        except Exception:
            continue
    return None

def rd(expr):
    for fn in ["read_value", "get_value"]:
        try:
            return getattr(onapp, fn)(expr)
        except Exception:
            continue
    return None

how = wr("PRG_Test.xRunTests", "TRUE")
log(u"write xRunTests via: %s" % how)
if how and "set_prepared" in how:
    try:
        onapp.write_prepared_values()
        log(u"write_prepared_values ok")
    except Exception as e:
        log(u"wpv err %r" % e)

time.sleep(3)
for var in ["PRG_Test.iPassed", "PRG_Test.iFailed", "PRG_Test.sLastFail",
            "PRG_Test.xAllPass"]:
    v = rd(var)
    log(u"%s = %s" % (var, v))

try:
    onapp.logout()
    log(u"LOGOUT_OK")
except Exception as e:
    log(u"logout err %r" % e)
proj.close()
log(u"=== RUNTEST_DONE ===")
f.close()
