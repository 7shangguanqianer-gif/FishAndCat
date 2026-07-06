# -*- coding: utf-8 -*-
"""
test_sim.py — 仿真回归测试(零依赖 unittest)
运行:python -m unittest discover -s F:/abb_wh_work/sim/tests -v
     或 python F:/abb_wh_work/sim/tests/test_sim.py
锁定内容:几何/承重/预占用口径 + 实验发现 F2/F3 + F4 头条数字。
改动评分函数/参数后:先看这里红不红,红=口径变了,须走 canonical 变更流程。
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import warehouse_sim as ws


def _run_all(goods, rule="sum", delta=0.15):   # 0706 默认=官方口径;历史锁显式传 and
    w_max = max(g.weight for g in goods)
    f_max = max(g.freq for g in goods)
    fn = ws.make_score_fn(1.0, 0.6, 0.4, delta, w_max, f_max)
    out = {}
    for name, strat in [("seq", ws.strat_seq), ("near", ws.strat_near),
                        ("score", ws.strat_score)]:
        wh, placed, failed = ws.run_online(strat, goods, rule, fn)
        out[name] = (wh, placed, failed)
    wh, placed, failed = ws.run_awra_ls(goods, rule, fn, w_max, f_max)
    out["awra"] = (wh, placed, failed)
    return out


class TestGeometry(unittest.TestCase):
    def test_tier_cap(self):
        self.assertAlmostEqual(ws.tier_cap(0), 100.0)
        self.assertAlmostEqual(ws.tier_cap(19), 62.0)

    def test_chebyshev_time(self):
        # vx=2,vy=0.5:(19,19) 水平9.5s 垂直38s → 取慢轴38(A5 口径)
        self.assertAlmostEqual(ws.travel_time(19, 19), 38.0)
        self.assertAlmostEqual(ws.travel_time(19, 0), 9.5)
        self.assertAlmostEqual(ws.travel_time(0, 19), 38.0)

    def test_l1_axis_time_known_values(self):
        # 水平 vx=2,ax=0.5:临界距离 vmax²/a=8m
        self.assertAlmostEqual(ws.axis_time(19.0, 2.0, 0.5), 19 / 2 + 2 / 0.5)   # 梯形 13.5
        self.assertAlmostEqual(ws.axis_time(2.0, 2.0, 0.5), 4.0)                 # 三角 2√(2/0.5)
        self.assertAlmostEqual(ws.axis_time(8.0, 2.0, 0.5), 8.0)                 # 临界点两式相等
        self.assertAlmostEqual(ws.axis_time(0.0, 2.0, 0.5), 0.0)
        # 垂直 vy=0.5,ay=0.3:临界 0.8333m
        self.assertAlmostEqual(ws.axis_time(19.0, 0.5, 0.3), 19 / 0.5 + 0.5 / 0.3)  # 39.667

    def test_l1_accel_switch(self):
        # 开关默认关(匀速历史口径);开启后时间恒不小于匀速,且已知值正确
        self.assertFalse(ws.ACCEL)
        try:
            ws.ACCEL = True
            self.assertAlmostEqual(ws.travel_time(19, 19), 19 / 0.5 + 0.5 / 0.3)
            for c, t in [(0, 0), (1, 0), (5, 3), (19, 19), (0, 19), (10, 2)]:
                ws.ACCEL = True
                ta = ws.travel_time(c, t)
                ws.ACCEL = False
                tu = ws.travel_time(c, t)
                self.assertGreaterEqual(ta + 1e-12, tu, (c, t))
        finally:
            ws.ACCEL = False

    def test_l2_travel_between(self):
        # 任意两点行程(双命令周期地基):对称/自反/端点特例/三角不等式
        self.assertAlmostEqual(ws.travel_time_between(0, 0, 19, 19), 38.0)
        self.assertAlmostEqual(ws.travel_time_between(19, 19, 0, 0), 38.0)
        self.assertAlmostEqual(ws.travel_time_between(5, 2, 5, 2), 0.0)
        self.assertAlmostEqual(ws.travel_time(7, 3), ws.travel_time_between(0, 0, 7, 3))
        import random as _r
        rng = _r.Random(1)
        for _ in range(30):     # 经原点三角不等式 = 双命令节省非负的数学依据
            a = (rng.randrange(20), rng.randrange(20))
            b = (rng.randrange(20), rng.randrange(20))
            self.assertLessEqual(
                ws.travel_time_between(a[0], a[1], b[0], b[1]),
                ws.travel_time(*a) + ws.travel_time(*b) + 1e-9)

    def test_manhattan_path(self):
        self.assertAlmostEqual(ws.path_len(19, 19), 38.0)
        self.assertAlmostEqual(ws.path_len(3, 4), 7.0)

    def test_preoccupied_counts(self):
        # B1 四解读格数:sum=133(官方 0706)/ and=49 / or=231 / linear=134
        #(PRG_Test T05-T07 同口径,sum 断言随批次 D 加入 ST 侧)
        for rule, expect in [("sum", 133), ("and", 49), ("or", 231), ("linear", 134)]:
            n = sum(1 for c in range(20) for t in range(20)
                    if ws.preoccupied(c, t, rule))
            self.assertEqual(n, expect, rule)


class TestFeasibility(unittest.TestCase):
    def setUp(self):
        self.wh = ws.Warehouse("sum")     # 官方口径;(0,0) 在 sum 下同样预占

    def test_preset_blocked(self):
        g = ws.Good(1, "G", 10.0, 1.0, 0.5)
        self.assertFalse(self.wh.feasible(0, 0, g))    # (0,0) 预占
        self.assertTrue(self.wh.feasible(1, 0, g))

    def test_overweight_high_tier(self):
        g = ws.Good(1, "G", 81.0, 1.0, 0.5)
        self.assertFalse(self.wh.feasible(1, 10, g))   # t10 限重 80
        self.assertTrue(self.wh.feasible(1, 0, g))

    def test_oversize_volume(self):
        g = ws.Good(1, "G", 10.0, 1.0, 1.2)
        self.assertFalse(self.wh.feasible(1, 0, g))

    def test_occupied_blocked(self):
        g = ws.Good(1, "G", 10.0, 1.0, 0.5)
        self.wh.put(1, 0, g)
        g2 = ws.Good(2, "G2", 10.0, 1.0, 0.5)
        self.assertFalse(self.wh.feasible(1, 0, g2))


class TestFindings(unittest.TestCase):
    """实验发现回归(docs/实验发现.md)"""

    def test_f2_delta_zero_degenerates_to_near(self):
        goods = ws.gen_goods(120, 2026)
        out = _run_all(goods, delta=0.0)
        near_set = {pos for _, pos in out["near"][1]}
        score_set = {pos for _, pos in out["score"][1]}
        self.assertEqual(near_set, score_set)          # δ=0 → 占位集合完全相同

    def test_f2_delta_default_differs_and_wins_hot(self):
        goods = ws.gen_goods(120, 2026)
        out = _run_all(goods, delta=0.15)
        m_near = ws.metrics(*out["near"])
        m_score = ws.metrics(*out["score"])
        self.assertLess(m_score["exp_t"], m_near["exp_t"])
        self.assertLess(m_score["hot_t"], m_near["hot_t"])

    def test_f3_tight_capacity_greedy_fails_awra_survives(self):
        goods = ws.gen_goods(150, 2026)
        out = _run_all(goods, rule="or")
        self.assertGreater(len(out["near"][2]), 0)     # 在线贪心有失败件
        self.assertEqual(len(out["awra"][2]), 0)       # AWRA-LS Rank 全部成功

    def test_f4_legacy_and_headline_numbers(self):
        # 历史对照锁:0703-0705 主场景(and 49格/默认权重/匀速)——官方 0706 切 sum 后
        # 保留守卫 F 系列历史条目引用的数字;显式传 rule="and",不随默认口径漂移
        goods = ws.gen_goods(120, 2026)
        out = _run_all(goods, rule="and")
        m = {k: ws.metrics(*v) for k, v in out.items()}
        self.assertAlmostEqual(m["seq"]["exp_t"], 19.02, delta=0.01)
        self.assertAlmostEqual(m["near"]["exp_t"], 7.99, delta=0.01)
        self.assertAlmostEqual(m["score"]["exp_t"], 7.50, delta=0.01)
        self.assertAlmostEqual(m["awra"]["exp_t"], 5.39, delta=0.01)
        self.assertAlmostEqual(m["awra"]["heavy_tier"], 0.50, delta=0.01)
        for k in m:
            self.assertEqual(m[k]["viol"], 0, k)       # C8:违规恒0

    def test_h_caliber_headline_lock(self):
        # H 口径新锁(官方 sum 底图+0706 重标策略表,seed=2026 锁定值;经用户+官方批准的
        # 口径变更,变更记录=canonical v3.0 与 docs/B1B2官方答复_影响分析.md)
        self.assertEqual(ws.lookup_weights(120, "skew", "batch"), (0.05, 0.6))
        self.assertEqual(ws.lookup_weights(120, "skew", "online"), (0.10, 1.0))
        self.assertEqual(ws.lookup_weights(500, "skew", "batch"), (0.05, 0.6))  # 密度钳位240档
        try:
            ws.ACCEL = True
            goods = ws.gen_goods(120, 2026)
            wm = max(g.weight for g in goods)
            fm = max(g.freq for g in goods)
            d, bg = ws.lookup_weights(120, "skew", "batch")
            fn = ws.make_score_fn(1.0, bg / 2, bg / 2, d, wm, fm)
            wh, placed, failed = ws.run_awra_ls(goods, "sum", fn, wm, fm)
            m = ws.metrics(wh, placed, failed)
            self.assertAlmostEqual(m["exp_t"], 8.6232, delta=0.01)
            self.assertEqual(m["viol"], 0)
        finally:
            ws.ACCEL = False

    def test_legacy_and_h_lock(self):
        # 历史 H 锁(and 底图+当时策略表权重 (0.05,0.6) 硬编码,与新表解耦)
        try:
            ws.ACCEL = True
            goods = ws.gen_goods(120, 2026)
            wm = max(g.weight for g in goods)
            fm = max(g.freq for g in goods)
            fn = ws.make_score_fn(1.0, 0.3, 0.3, 0.05, wm, fm)
            wh, placed, failed = ws.run_awra_ls(goods, "and", fn, wm, fm)
            m = ws.metrics(wh, placed, failed)
            self.assertAlmostEqual(m["exp_t"], 7.6202, delta=0.01)
            self.assertEqual(m["viol"], 0)
        finally:
            ws.ACCEL = False

    def test_all_cases_zero_violation(self):
        for case in ("uniform", "skew", "heavy"):
            goods = ws.gen_goods(100, 7, case)
            out = _run_all(goods)
            for k, v in out.items():
                self.assertEqual(ws.metrics(*v)["viol"], 0, f"{case}/{k}")


class TestDeterminism(unittest.TestCase):
    def test_same_seed_same_result(self):
        a = [(g.weight, g.freq, g.vol) for g in ws.gen_goods(50, 42)]
        b = [(g.weight, g.freq, g.vol) for g in ws.gen_goods(50, 42)]
        self.assertEqual(a, b)

    def test_case_default_backcompat(self):
        # case 参数默认 skew 必须与历史(无参数)生成序完全一致(F4 数字依赖)
        a = [(g.weight, g.freq, g.vol) for g in ws.gen_goods(30, 2026)]
        b = [(g.weight, g.freq, g.vol) for g in ws.gen_goods(30, 2026, "skew")]
        self.assertEqual(a, b)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    unittest.main(verbosity=2)
