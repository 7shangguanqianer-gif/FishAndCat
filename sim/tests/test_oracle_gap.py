# -*- coding: utf-8 -*-
"""
test_oracle_gap.py — oracle_gap.py 回归测试(零依赖 unittest,风格同 test_sim.py)
运行:python -m unittest discover -s F:/abb_wh_work/sim/tests -v
     或 python F:/abb_wh_work/sim/tests/test_oracle_gap.py
     或 python -m pytest F:/abb_wh_work/sim/tests/test_oracle_gap.py -v

落地 docs/sim审查_0711pm.md 建议2("oracle_gap.py 新增的 VBS/SBS/gap/closed-gap
逻辑无任何自动化回归测试保护")。本文件只新增测试代码,不改动 oracle_gap.py /
instance_gen.py / strategy_lib.py / warehouse_sim.py 一个字。

锁定两件事:
  1. golden number 锁 —— 基于当前冻结的 13 场景×30 seed
     out/instgen_detail.csv，真实重跑 oracle_gap 的后处理/选择器流程；它会锁
     select_strategy 与 gap 聚合，但不会重新运行 warehouse_sim 或证明策略性能。
  2. 一票否决锁 —— SBS(词典序最优固定策略)选择必须先看 excess_fail 再看 gap
     均值:构造一个"exp_t 全场最低但 fail>0"的诱饵策略,断言它不会被选中。
     `sbs = min(FIXED, key=lambda s: (fixed_exf[s], fixed_glob[s]))` 这行是
     main() 内部代码,没有独立可调用的函数(审查已确认);做法是 monkeypatch
     oracle_gap.py 的 HERE/OUT/DETAIL 三个模块级路径常量,指向临时目录喂假
     数据,再调用真实的 og.main(),核对其写出的 CSV/summary —— 测的是真代码,
     不是重新实现一遍判定逻辑。三个 monkeypatch 均在 try/finally 里逐一还原,
     真实 out/oracle_gap*.csv 与 figs/fig13_oracle_gap.png 全程不受影响(已用
     独立脚本核验:调用前后 mtime/size 逐字节相同)。

改动上述任一文件后:先看这里红不红,红=口径变了或一票否决被打破,须走
canonical 变更流程核实是否有意为之。
"""
import csv
import os
import re
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import oracle_gap as og
import instance_gen as ig   # noqa: F401 (确认与 og 同源 import 路径可用)


def _read_all_rows(out_dir):
    """读 <out_dir>/oracle_gap.csv,返回 {selector: row} (仅 scenario=='ALL' 行)。"""
    path = os.path.join(out_dir, "oracle_gap.csv")
    with open(path, encoding="utf-8-sig") as fp:
        rows = list(csv.DictReader(fp))
    return {r["selector"]: r for r in rows if r["scenario"] == "ALL"}


def _sbs_of(all_rows, fixed):
    """复刻 oracle_gap.py 主流程里 SBS 的选择式:excess_fail 总数(此处用 exf_mean
    等价代入,同一 selector 组内实例数恒定,排序与用 sum 完全一致)→ gap 均值,
    词典序取最小。"""
    def gap_or_inf(row):
        return float(row["gap_mean"]) if row.get("gap_mean") not in ("", None) else float("inf")
    return min(fixed, key=lambda s: (float(all_rows[s]["exf_mean"]),
                                     gap_or_inf(all_rows[s])))


class TestOracleGapGoldenNumbers(unittest.TestCase):
    """A1 oracle gap 头条数字回归锁(docs/sim审查_0711pm.md 建议2②)。"""

    def test_det_lexicographic_attain_and_closed_gap(self):
        # 规模自证:golden number 的前提是"当前 13 场景×30 seed";数据源被误
        # 截断/误换时这里先报错,避免下面的数字巧合对上却锁错了范围。
        inst = og.load_detail()
        self.assertEqual(len(inst), 390)                       # 13 * 30
        self.assertEqual(len({k[0] for k in inst}), 13)
        self.assertEqual(len({k[1] for k in inst}), 30)

        # 真实重跑后处理，但所有生成物写入临时目录，正式 out/ 与 fig 不受测试污染。
        tmp = tempfile.mkdtemp(prefix="oracle_gap_golden_")
        orig_here, orig_out = og.HERE, og.OUT
        try:
            tmp_out = os.path.join(tmp, "out")
            os.makedirs(tmp_out, exist_ok=True)
            og.HERE, og.OUT = tmp, tmp_out
            og.main()
            all_rows = _read_all_rows(tmp_out)
        finally:
            og.HERE, og.OUT = orig_here, orig_out
            shutil.rmtree(tmp, ignore_errors=True)

        lex = all_rows["det_lexicographic"]
        attain = float(lex["attain_mean"])
        self.assertAlmostEqual(attain, 98.5, delta=0.1)        # 0711 pm 实跑=98.55

        sbs = _sbs_of(all_rows, og.FIXED)
        self.assertEqual(sbs, "awra")                          # 与审查文档报告一致
        gap_sbs = float(all_rows[sbs]["gap_mean"])
        gap_lex = float(lex["gap_mean"])
        closed = (gap_sbs - gap_lex) / gap_sbs * 100.0
        self.assertAlmostEqual(closed, 93.3, delta=0.1)        # 0711 pm 实跑=93.30


class TestOracleGapSBSVeto(unittest.TestCase):
    """SBS 一票否决回归锁(docs/sim审查_0711pm.md 建议2①;v1 教训:纯 gap 均值
    会把漏件策略选成 SBS,见 oracle_gap.py 模块 docstring 第 11-12 行)。"""

    SCN, SEED = "tiny_light", 2026   # 真实存在于 ig.SCENARIOS,货物由真代码生成
    # 诱饵表:tob 的 exp_t 全场最低(=1.0,gap 会是全场最负/看似最优),但 fail=5>0;
    # 其余 6 个固定策略 fail=0,其中 awra 是 fail=0 组里最快 → 应同时是 VBS 与 SBS。
    DATA = {
        "random": dict(exp_t=50.0, fail=0),
        "seq":    dict(exp_t=40.0, fail=0),
        "near":   dict(exp_t=20.0, fail=0),
        "score":  dict(exp_t=15.0, fail=0),
        "awra":   dict(exp_t=10.0, fail=0),
        "cb":     dict(exp_t=12.0, fail=0),
        "tob":    dict(exp_t=1.0,  fail=5),
    }

    def _write_fake_detail(self, path):
        with open(path, "w", newline="", encoding="utf-8-sig") as fp:
            w = csv.DictWriter(fp, fieldnames=["scenario", "seed", "strat", "exp_t",
                                               "fail", "viol", "heavy_tier", "energy"])
            w.writeheader()
            for s in og.FIXED:
                d = self.DATA[s]
                w.writerow(dict(scenario=self.SCN, seed=self.SEED, strat=s,
                                exp_t=d["exp_t"], fail=d["fail"],
                                viol=0, heavy_tier=1.0, energy=100.0))

    def test_sbs_vetoes_lowest_gap_strategy_with_excess_fail(self):
        tmp = tempfile.mkdtemp(prefix="oracle_gap_veto_")
        orig_here, orig_out, orig_detail = og.HERE, og.OUT, og.DETAIL
        try:
            tmp_out = os.path.join(tmp, "out")
            os.makedirs(tmp_out, exist_ok=True)
            fake_detail = os.path.join(tmp_out, "instgen_detail.csv")
            self._write_fake_detail(fake_detail)

            # monkeypatch 三个模块级路径常量(HERE 还决定 figs/ 落盘位置),不改
            # oracle_gap.py 源码一个字;main() 按全局变量取值,patch 后即生效。
            og.HERE, og.OUT, og.DETAIL = tmp, tmp_out, fake_detail
            og.main()

            all_rows = _read_all_rows(tmp_out)
            # 诱饵确实构造成立:tob 的 excess_fail>0；修复后它不再拥有可比 gap。
            self.assertGreater(float(all_rows["tob"]["exf_mean"]), 0.0)
            self.assertEqual(float(all_rows["awra"]["exf_mean"]), 0.0)
            self.assertEqual(all_rows["tob"]["gap_mean"], "")
            self.assertEqual(all_rows["tob"]["attain_mean"], "")

            # 核心断言①:按 CSV 数字复刻词典序选择式,tob 不得当选
            sbs = _sbs_of(all_rows, og.FIXED)
            self.assertEqual(sbs, "awra")
            self.assertNotEqual(sbs, "tob")

            # 核心断言②:直接读真代码自己写下的结论(summary.txt 里的 sbs 变量),
            # 不止是"用同一公式重算一遍"——证明 main() 内部真实决策也否决了 tob。
            with open(os.path.join(tmp_out, "oracle_gap_summary.txt"),
                     encoding="utf-8") as fp:
                summary = fp.read()
            m = re.search(r"SBS\([^)]*\)=\s*\*\*(\w+)\*\*", summary)
            self.assertIsNotNone(m, "summary.txt 格式变了,一票否决断言需要更新解析")
            self.assertEqual(m.group(1), "awra")
        finally:
            og.HERE, og.OUT, og.DETAIL = orig_here, orig_out, orig_detail
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    unittest.main(verbosity=2)
