# -*- coding: utf-8 -*-
"""
export_st_vectors.py — 生成 plc/07_GVL_Data_generated.st
把 Python 仿真的货物数据与期望值导出成 ST 代码,保证 PLC 侧与仿真同源:
  1) 演示批次 aDemoGoods(seed=2026 前 N_DEMO 件,决赛演示/答辩用同一批货)
  2) 一致性测试向量 aTestVec(FC_CalcScore / FC_CalcTravelTime 的期望值,
     PRG_Test T19/T20 以 1e-3 容差比对 —— Python 双精度 vs PLC REAL 单精度)
运行:python export_st_vectors.py   (在 sim/ 目录或任意处,输出到 ../plc/)
改动 warehouse_sim.py 的评分函数/参数后必须重跑本脚本(单一真相源纪律)。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import warehouse_sim as ws

N_DEMO = 20
SEED = 2026

goods = ws.gen_goods(N_DEMO, SEED)
w_max = max(g.weight for g in goods)
f_max = max(g.freq for g in goods)
score_fn = ws.make_score_fn(1.0, 0.6, 0.4, 0.15, w_max, f_max)  # 与 canonical E 默认一致

# 测试向量:前10件货 × 有代表性的仓位(近/远/高/低)
probe_slots = [(1, 0), (5, 2), (10, 5), (19, 19), (0, 1), (3, 3), (7, 10),
               (15, 1), (2, 18), (12, 7)]
vecs = []
for g, (c, t) in zip(goods[:10], probe_slots):
    vecs.append((g.weight, g.freq, c, t, w_max, f_max,
                 score_fn(g, c, t), ws.travel_time(c, t)))

L = []
L.append("(* ============================================================")
L.append("   07_GVL_Data_generated.st — 生成文件,勿手改!")
L.append(f"   由 sim/export_st_vectors.py 生成(seed={SEED},N_DEMO={N_DEMO},")
L.append("   评分权重 α=1.0 β=0.6 γ=0.4 δ=0.15 = canonical E 默认)")
L.append("   导入:TYPE 段建 DUT;GVL_Data 段建 GVL;FC_LoadDemoGoods 建 POU(函数)")
L.append("   ============================================================ *)")
L.append("")
L.append("(* ---------- DUT:ST_TestVec ---------- *)")
L.append("TYPE ST_TestVec :")
L.append("STRUCT")
L.append("    W        : REAL;   // 货物重量")
L.append("    F        : REAL;   // 货物频次")
L.append("    X        : INT;    // 候选仓位列")
L.append("    Y        : INT;    // 候选仓位层")
L.append("    WMax     : REAL;   // 归一分母")
L.append("    FMax     : REAL;")
L.append("    ExpScore : REAL;   // Python 期望评分(双精度算出,容差1e-3比对)")
L.append("    ExpTime  : REAL;   // Python 期望切比雪夫时间")
L.append("END_STRUCT")
L.append("END_TYPE")
L.append("")
L.append("(* ---------- GVL:GVL_Data ---------- *)")
L.append("VAR_GLOBAL CONSTANT")
L.append(f"    N_DEMO    : INT := {N_DEMO};")
L.append(f"    N_TESTVEC : INT := {len(vecs)};")
L.append("END_VAR")
L.append("VAR_GLOBAL")
L.append("    aTestVec : ARRAY[1..10] OF ST_TestVec := [")
for i, (w, f, c, t, wm, fm, es, et) in enumerate(vecs):
    sep = "," if i < len(vecs) - 1 else ""
    L.append(f"        (W := {w}, F := {f}, X := {c}, Y := {t}, "
             f"WMax := {wm}, FMax := {fm}, "
             f"ExpScore := {es:.6f}, ExpTime := {et:.6f}){sep}")
L.append("    ];")
L.append("END_VAR")
L.append("")
L.append("(* ---------- FC_LoadDemoGoods:载入演示批次(与 Python 仿真同源同 seed) ---------- *)")
L.append("FUNCTION FC_LoadDemoGoods : BOOL")
L.append("VAR")
L.append("    n : INT;")
L.append("END_VAR")
L.append("n := GVL_WH.iGoodsCount;")
for g in goods:
    L.append(f"n := n + 1;  GVL_WH.aGoods[n].Id := {g.gid};  "
             f"GVL_WH.aGoods[n].Name := '{g.name}';")
    L.append(f"GVL_WH.aGoods[n].Weight := {g.weight};  GVL_WH.aGoods[n].Freq := {g.freq};  "
             f"GVL_WH.aGoods[n].Volume := {g.vol};  GVL_WH.aGoods[n].Assigned := FALSE;")
L.append("GVL_WH.iGoodsCount := n;")
L.append("FC_LoadDemoGoods := TRUE;")
L.append("END_FUNCTION")

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "plc",
                   "07_GVL_Data_generated.st")
with open(out, "w", encoding="utf-8") as fp:
    fp.write("\n".join(L) + "\n")
print(f"已生成 {os.path.normpath(out)}")
print(f"演示批次 {N_DEMO} 件(seed={SEED}),测试向量 {len(vecs)} 条")
for i, (w, f, c, t, wm, fm, es, et) in enumerate(vecs[:3], 1):
    print(f"  vec{i}: W={w} F={f} slot=({c},{t}) -> score={es:.6f} time={et:.3f}")
