# -*- coding: utf-8 -*-
"""F2 冒烟测试：只读验证 Factory I/O Modbus TCP Server 链路（不写任何执行器）。

前提：Factory I/O 已开、Automated Warehouse 场景已载入、驱动=Modbus TCP/IP Server
      绑定 Software Loopback Interface 1（127.0.0.1:502, Slave ID 1）。
点表依据：驱动面板默认映射（截图 img/F2_modbus_server_default_mapping_0712.png）。
"""
from pymodbus.client import ModbusTcpClient

SENSOR_NAMES = [
    "At Entry", "At Load", "At Left", "At Middle", "At Right",
    "At Unload", "At Exit", "Moving X", "Moving Z", "Start",
    "Reset", "Stop", "Emergency stop", "Auto", "FACTORY I/O (Running)",
]
COIL_NAMES = [
    "Entry Conveyor", "Load Conveyor", "Forks Left", "Forks Right", "Lift",
    "Unload Conveyor", "Exit Conveyor", "Start light", "Reset light", "Stop light",
]

def main():
    c = ModbusTcpClient("127.0.0.1", port=502)
    ok = c.connect()
    print(f"connect: {ok}")
    if not ok:
        raise SystemExit(1)

    di = c.read_discrete_inputs(0, count=15, slave=1)
    if di.isError():
        print(f"discrete_inputs ERROR: {di}")
    else:
        print("--- Discrete Inputs (sensors) ---")
        for i, name in enumerate(SENSOR_NAMES):
            print(f"  Input {i:2d} {name:24s} = {di.bits[i]}")

    co = c.read_coils(0, count=10, slave=1)
    if co.isError():
        print(f"coils ERROR: {co}")
    else:
        print("--- Coils (actuator commands) ---")
        for i, name in enumerate(COIL_NAMES):
            print(f"  Coil {i:2d} {name:24s} = {co.bits[i]}")

    hr = c.read_holding_registers(0, count=1, slave=1)
    if hr.isError():
        print(f"holding_registers ERROR: {hr}")
    else:
        print(f"--- Holding Reg 0 (Target Position) = {hr.registers[0]}")

    ir = c.read_input_registers(0, count=1, slave=1)
    print(f"--- Input Reg 0 = {'(no mapping / error: %s)' % ir if ir.isError() else ir.registers[0]}")

    c.close()
    print("SMOKE READ DONE")

if __name__ == "__main__":
    main()
