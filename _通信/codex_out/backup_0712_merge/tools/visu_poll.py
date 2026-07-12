# -*- coding: utf-8 -*-
"""
visu_poll.py — T3.4 实时联动:Modbus TCP 轮询客户端(骨架,0710 夜)

⚠️ 状态:**未实机验证**。依据=docs/块3施工依据_0708.md §3b(0710 定向枪,官方一手配方):
  AC500 V3 设备树 ETH 口加 "Modbus TCP/IP Server",变量经 %MW 直映射暴露;
  FC03 单请求 ≤125 寄存器 → 400 格拆 4 段读。
两个待实测点(施工依据 §3b 第 4 条,本骨架已参数化,实测后定值):
  ①二维数组线性化顺序(IEC 惯例=行优先,--order 可切) ②REAL 字序(--word-order 可切)。

ST 侧对应规格(GVL_Modbus 镜像区,**待 Codex 画面完工、ab_sync 解锁后实装**):
  VAR_GLOBAL
      (* 快照协议:PRG_Main 每周期 ①iMbSeqHead:=iMbSeqHead+1 ②整赋拷贝 ③iMbSeqTail:=iMbSeqHead
         Python 读完 4 段后校验 head==tail —— 解决 4 段读非原子的撕裂问题 *)
      aMbSlotState AT %MW0   : ARRAY[0..19, 0..19] OF INT;   (* [列,显示行] 状态码0..6 *)
      iMbCraneXpx  AT %MW400 : INT;
      iMbCraneYpx  AT %MW401 : INT;
      iMbCurrentX  AT %MW402 : INT;
      iMbCurrentY  AT %MW403 : INT;
      iMbTargetX   AT %MW404 : INT;
      iMbTargetY   AT %MW405 : INT;
      rMbPathLen   AT %MD203 : REAL;                          (* =%MW406..407,偶字对齐 *)
      rMbExecTime  AT %MD204 : REAL;                          (* =%MW408..409 *)
      iMbStatus    AT %MW410 : INT;                           (* bit0=Alarm bit1=SnapValid *)
      iMbSeqHead   AT %MW411 : INT;
      iMbSeqTail   AT %MW412 : INT;
  END_VAR
  (镜像拷贝顺带解决原子性:拷贝瞬间=打包窗口;零侵入现有 GVL_Visu/45 用例。)

自测(零依赖,不需要 pymodbus/PLC):python tools/visu_poll.py --selftest
真连(待实机):python tools/visu_poll.py --host 127.0.0.1 [--order col --word-order little]
"""
import argparse
import struct
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

COLS, TIERS = 20, 20
N_GRID = COLS * TIERS                      # 400 寄存器
CHUNK = 100                                # 4 段读(FC03 上限 125,取整百留裕量)
SCALAR_BASE, SCALAR_COUNT = 400, 13        # MW400..412(含快照序号头尾)
MAX_SNAP_RETRY = 3


class VisuPoller:
    """轮询器。client 注入(鸭子类型:read_holding_registers(address, count)→
    有 .registers 的对象),生产用 pymodbus,自测用 FakeClient。"""

    def __init__(self, client, order="row", word_order="big"):
        assert order in ("row", "col") and word_order in ("big", "little")
        self.client = client
        self.order = order                 # row=[列][行]连续(IEC 惯例,待实测)
        self.word_order = word_order       # REAL 双字序(待实测)

    def _read(self, address, count):
        rr = self.client.read_holding_registers(address, count)
        regs = getattr(rr, "registers", None)
        if not regs or len(regs) != count:
            raise ConnectionError(f"read {address}+{count} failed: {rr}")
        return regs

    def _decode_real(self, w0, w1):
        pair = (w0, w1) if self.word_order == "big" else (w1, w0)
        return struct.unpack(">f", struct.pack(">HH", *pair))[0]

    @staticmethod
    def _to_int16(u):
        return u - 0x10000 if u >= 0x8000 else u

    def poll(self):
        """一帧:4 段格网 + 1 段标量;快照序号头尾一致才接受(撕裂重试)。"""
        for _ in range(MAX_SNAP_RETRY):
            grid_regs = []
            for k in range(0, N_GRID, CHUNK):
                grid_regs.extend(self._read(k, CHUNK))
            sc = self._read(SCALAR_BASE, SCALAR_COUNT)
            head, tail = sc[11], sc[12]
            if head == tail:
                break
        else:
            raise RuntimeError(f"快照序号 {MAX_SNAP_RETRY} 次仍不一致(head≠tail)")

        vals = [self._to_int16(u) for u in grid_regs]
        grid = [[0] * TIERS for _ in range(COLS)]
        for i, v in enumerate(vals):
            if self.order == "row":        # [列][行] 连续:i = c*TIERS + t
                c, t = divmod(i, TIERS)
            else:                          # 列优先备选:i = t*COLS + c
                t, c = divmod(i, COLS)
            grid[c][t] = v
        return dict(
            grid=grid, snap_seq=head,
            crane_px=(self._to_int16(sc[0]), self._to_int16(sc[1])),
            current=(self._to_int16(sc[2]), self._to_int16(sc[3])),
            target=(self._to_int16(sc[4]), self._to_int16(sc[5])),
            path_len=self._decode_real(sc[6], sc[7]),
            exec_time=self._decode_real(sc[8], sc[9]),
            alarm=bool(sc[10] & 1), snap_valid=bool(sc[10] & 2))


def connect(host, port=502):
    """生产连接(延迟导入,自测路径零依赖)。"""
    from pymodbus.client import ModbusTcpClient   # pip install pymodbus -i 阿里云源
    c = ModbusTcpClient(host, port=port)
    if not c.connect():
        raise ConnectionError(f"connect {host}:{port} failed")
    return c


# ---------------- 自测(FakeClient 注入,验证解码/分段/撕裂协议) ----------------
class _RR:
    def __init__(self, regs):
        self.registers = regs


class FakeClient:
    """构造已知寄存器映像;可模拟前 N 帧撕裂(head≠tail)。"""

    def __init__(self, torn_reads=0):
        self.regs = [0] * (SCALAR_BASE + SCALAR_COUNT)
        for i in range(N_GRID):            # 格网=下标本身(验证重排最敏感的填充)
            self.regs[i] = i % 7
        self.regs[400], self.regs[401] = 56, 380
        self.regs[402:406] = [2, 3, 19, 0]
        self.regs[406:408] = list(struct.unpack(">HH", struct.pack(">f", 23.0)))
        self.regs[408:410] = list(struct.unpack(">HH", struct.pack(">f", 7.5)))
        self.regs[410] = 0b10               # SnapValid=1, Alarm=0
        self.regs[411] = self.regs[412] = 5
        self.torn = torn_reads
        self.n_reads = 0

    def read_holding_registers(self, address, count):
        self.n_reads += 1
        out = list(self.regs[address:address + count])
        if self.torn > 0 and address == SCALAR_BASE:
            out[12] = out[11] - 1           # tail 落后 → 撕裂帧
            self.torn -= 1
        return _RR(out)


def selftest():
    ok = True

    def check(name, cond):
        nonlocal ok
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
        ok = ok and cond

    fc = FakeClient()
    p = VisuPoller(fc, order="row", word_order="big")
    f = p.poll()
    check("分段读次数=5(4 格网段+1 标量段)", fc.n_reads == 5)
    check("行优先重排:grid[1][3] == (1*20+3)%7", f["grid"][1][3] == (1 * 20 + 3) % 7)
    check("行优先重排:grid[19][19] == 399%7", f["grid"][19][19] == 399 % 7)
    check("REAL big 解码 path_len=23.0", abs(f["path_len"] - 23.0) < 1e-6)
    check("REAL big 解码 exec_time=7.5", abs(f["exec_time"] - 7.5) < 1e-6)
    check("标量/位域(crane/alarm/snap_valid)",
          f["crane_px"] == (56, 380) and not f["alarm"] and f["snap_valid"])

    p2 = VisuPoller(FakeClient(), order="col", word_order="big")
    f2 = p2.poll()
    check("列优先重排:grid[3][1] == (1*20+3)%7", f2["grid"][3][1] == (1 * 20 + 3) % 7)

    fc3 = FakeClient()
    w0, w1 = fc3.regs[406], fc3.regs[407]
    fc3.regs[406], fc3.regs[407] = w1, w0   # 制造小字序映像
    f3 = VisuPoller(fc3, order="row", word_order="little").poll()
    check("REAL little 字序解码", abs(f3["path_len"] - 23.0) < 1e-6)

    fc4 = FakeClient(torn_reads=1)
    f4 = VisuPoller(fc4).poll()
    check("撕裂帧重试后成功(1 帧撕裂→第 2 帧接受)", f4["snap_seq"] == 5)
    try:
        VisuPoller(FakeClient(torn_reads=99)).poll()
        check("持续撕裂应抛异常", False)
    except RuntimeError:
        check("持续撕裂应抛异常", True)

    print("SELFTEST", "ALL PASS" if ok else "HAS FAILURES")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--host", default=None)
    ap.add_argument("--port", type=int, default=502)
    ap.add_argument("--order", choices=("row", "col"), default="row")
    ap.add_argument("--word-order", choices=("big", "little"), default="big")
    ap.add_argument("--interval", type=float, default=0.2, help="轮询间隔 s")
    a = ap.parse_args()
    if a.selftest:
        sys.exit(selftest())
    if not a.host:
        ap.error("--host 必填(或用 --selftest)")
    p = VisuPoller(connect(a.host, a.port), order=a.order, word_order=a.word_order)
    while True:                             # 最小演示循环:打印堆垛机与报警状态
        t0 = time.time()
        f = p.poll()
        occ = sum(1 for c in range(COLS) for t in range(TIERS) if f["grid"][c][t] == 2)
        print(f"seq={f['snap_seq']} crane_px={f['crane_px']} 占用={occ} "
              f"alarm={f['alarm']} 往返={1000 * (time.time() - t0):.0f}ms")
        time.sleep(a.interval)


if __name__ == "__main__":
    main()
