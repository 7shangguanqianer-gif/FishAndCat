# -*- coding: utf-8 -*-
"""F3 快线：Python 直控 Factory I/O Automated Warehouse 堆垛机（Modbus TCP client）。

角色：Python 扮演"伪 PLC"，经 Modbus TCP 读传感器/写执行器，驱动堆垛机完成入库。
口径：本产物为"Python 直控技术预演"素材（非 AC500 控制回路）。

已核实事实（io_map.md + 官方文档 docs.factoryio.com/manual/parts/stations/）：
- Target Position(HReg0)：1-54=货位格，0=原地停，>54=rest 位(55)。
- Lift(Coil4)：True=平台微抬（取/放箱行程）。
- Forks Left(C2)/Right(C3)：双 ON=回中位；At Left/Middle/Right(I2/3/4)=叉臂位置到达(True=在位)。
- 箱检测传感器(At Entry/Load/Unload/Exit)=对射型：True=空，False=被物遮挡（有箱）。

安全护栏：任何等待超时 → 全输出清零 + Target=0，抛异常退出（挂机自愈由外层记录）。
用法：
  python f3_stacker_control.py probe    # 阶段实验：入料→取箱→存 1 号位（单箱全流程，详细日志）
  python f3_stacker_control.py demo 3   # 连续入库 3 箱到货位 [11, 24, 37]（演示动线）
"""
import sys
import time

from pymodbus.client import ModbusTcpClient

HOST, PORT, SLAVE = "127.0.0.1", 502, 1

# 点表（io_map.md）
IN_AT_ENTRY, IN_AT_LOAD, IN_AT_LEFT, IN_AT_MIDDLE, IN_AT_RIGHT = 0, 1, 2, 3, 4
IN_AT_UNLOAD, IN_AT_EXIT, IN_MOVING_X, IN_MOVING_Z = 5, 6, 7, 8
IN_RUNNING = 14
C_ENTRY_CONV, C_LOAD_CONV, C_FORKS_L, C_FORKS_R, C_LIFT = 0, 1, 2, 3, 4
C_UNLOAD_CONV, C_EXIT_CONV = 5, 6
HR_TARGET = 0
POS_REST = 55  # >54 = rest 位（正对载入台）

STEP_TIMEOUT = 30.0   # 单步等待上限（堆垛机全程移动可能十几秒）
POLL = 0.1


class Stacker:
    def __init__(self):
        self.c = ModbusTcpClient(HOST, port=PORT)
        if not self.c.connect():
            raise SystemExit("connect failed")
        r = self.c.read_discrete_inputs(IN_RUNNING, count=1, slave=SLAVE)
        if r.isError() or not r.bits[0]:
            raise SystemExit("Factory I/O 未在 RUN 状态（Input14=False）——先在 GUI 按播放")

    # --- 基础 IO ---
    def din(self, addr):
        r = self.c.read_discrete_inputs(addr, count=1, slave=SLAVE)
        if r.isError():
            raise RuntimeError(f"read input {addr}: {r}")
        return r.bits[0]

    def coil(self, addr, val):
        r = self.c.write_coil(addr, val, slave=SLAVE)
        if r.isError():
            raise RuntimeError(f"write coil {addr}: {r}")

    def target(self, pos):
        r = self.c.write_register(HR_TARGET, pos, slave=SLAVE)
        if r.isError():
            raise RuntimeError(f"write target {pos}: {r}")

    def wait(self, desc, pred, timeout=STEP_TIMEOUT):
        t0 = time.time()
        while time.time() - t0 < timeout:
            if pred():
                print(f"  [ok {time.time()-t0:5.1f}s] {desc}")
                return
            time.sleep(POLL)
        self.all_stop()
        raise RuntimeError(f"TIMEOUT({timeout}s) waiting: {desc}")

    def all_stop(self):
        """安全清零：所有输出 False + Target=0（原地停）。"""
        for a in (C_ENTRY_CONV, C_LOAD_CONV, C_FORKS_L, C_FORKS_R, C_LIFT,
                  C_UNLOAD_CONV, C_EXIT_CONV):
            try:
                self.coil(a, False)
            except Exception:
                pass
        try:
            self.target(0)
        except Exception:
            pass

    # --- 组合动作 ---
    def crane_settled(self):
        return (not self.din(IN_MOVING_X)) and (not self.din(IN_MOVING_Z))

    def goto(self, pos, desc=""):
        print(f"* Target Position = {pos} {desc}")
        self.target(pos)
        time.sleep(0.5)  # 给 Moving 信号起来的时间
        self.wait(f"crane settled @ {pos}", self.crane_settled)

    def forks_center(self):
        # 官方文档：双 ON = 回中
        self.coil(C_FORKS_L, True)
        self.coil(C_FORKS_R, True)
        self.wait("forks At Middle", lambda: self.din(IN_AT_MIDDLE))
        self.coil(C_FORKS_L, False)
        self.coil(C_FORKS_R, False)

    def forks_right(self):
        self.coil(C_FORKS_L, False)
        self.coil(C_FORKS_R, True)
        self.wait("forks At Right", lambda: self.din(IN_AT_RIGHT))

    def forks_left(self):
        self.coil(C_FORKS_R, False)
        self.coil(C_FORKS_L, True)
        self.wait("forks At Left", lambda: self.din(IN_AT_LEFT))

    def feed_one_box(self):
        """入料：入口两条带走箱到载入台（At Load 遮挡=False=有箱）。"""
        print("* 入料：Entry+Load Conveyor 走")
        self.coil(C_ENTRY_CONV, True)
        self.coil(C_LOAD_CONV, True)
        self.wait("box At Load (blocked)", lambda: not self.din(IN_AT_LOAD),
                  timeout=60)
        self.coil(C_ENTRY_CONV, False)
        self.coil(C_LOAD_CONV, False)

    def pick_from_load(self):
        """载入台取箱：rest 位 → 伸右叉 → 微抬 → 回中。"""
        self.goto(POS_REST, "(rest=载入台)")
        print("* 取箱")
        self.forks_right()
        self.coil(C_LIFT, True)
        time.sleep(1.2)  # Lift 无独立到位传感，给行程时间
        self.forks_center()

    def store_to(self, cell):
        """存入货位：移动(带箱,Lift 保持 True) → 伸左叉 → 放下 → 回中。"""
        self.goto(cell, f"(货位 {cell})")
        print(f"* 放箱 → 货位 {cell}")
        self.forks_left()
        self.coil(C_LIFT, False)
        time.sleep(1.2)
        self.forks_center()

    def store_one(self, cell):
        self.feed_one_box()
        self.pick_from_load()
        self.store_to(cell)
        print(f"=== 货位 {cell} 入库完成 ===\n")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "probe"
    s = Stacker()
    t0 = time.time()
    try:
        if mode == "probe":
            s.store_one(1)
        elif mode == "demo":
            n = int(sys.argv[2]) if len(sys.argv) > 2 else 3
            cells = [11, 24, 37][:n]
            for c in cells:
                s.store_one(c)
        else:
            raise SystemExit(f"unknown mode {mode}")
        print(f"ALL DONE in {time.time()-t0:.1f}s")
    except KeyboardInterrupt:
        print("interrupted -> all_stop")
        s.all_stop()
    except Exception as e:
        print(f"FAILED: {e}")
        s.all_stop()
        raise
    finally:
        s.c.close()


if __name__ == "__main__":
    main()
