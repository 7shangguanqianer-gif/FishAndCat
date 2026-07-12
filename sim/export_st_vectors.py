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
    ws.ACCEL = False
    t_uni = ws.travel_time(c, t)
    sc = score_fn(g, c, t)
    ws.ACCEL = True
    t_acc = ws.travel_time(c, t)                 # L1 梯形口径期望值(T22 用)
    ws.ACCEL = False
    vecs.append((g.weight, g.freq, c, t, w_max, f_max, sc, t_uni, t_acc))

# ---- AWRA-LS 全流程终局向量(T25 端到端护栏;0707,匀速+sum官方口径)----
ws.ACCEL = False
LAM = (0.50, 0.35, 0.15)
MAX_LS = 5
wh_a, placed_a, failed_a = ws.run_awra_ls(goods, "sum", score_fn, w_max, f_max,
                                          lam=LAM, max_iter=MAX_LS)
pos_by_id = {g.gid: (c, t) for g, (c, t) in placed_a}
awra_cells = [(gid, pos_by_id[gid][0], pos_by_id[gid][1]) for gid in sorted(pos_by_id)]
m_a = ws.metrics(wh_a, placed_a, failed_a)

# ---- CB/TOB 全流程终局向量(T68/T69 端到端护栏;0712 轨B D-1,匀速+sum 官方口径,
#      与 plc/FB_AssignClassTurnover 一字对齐——改 strategy_lib 后必须重跑本脚本)----
import strategy_lib as sl
wh_cb, placed_cb, failed_cb = sl.run_class_based(goods, "sum")
pos_cb = {g.gid: p for g, p in placed_cb}
cb_cells = [(gid, pos_cb[gid][0], pos_cb[gid][1]) for gid in sorted(pos_cb)]
m_cb = ws.metrics(wh_cb, placed_cb, failed_cb)
wh_tob, placed_tob, failed_tob = sl.run_full_turnover(goods, "sum")
pos_tob = {g.gid: p for g, p in placed_tob}
tob_cells = [(gid, pos_tob[gid][0], pos_tob[gid][1]) for gid in sorted(pos_tob)]
m_tob = ws.metrics(wh_tob, placed_tob, failed_tob)

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
L.append("    ExpTime  : REAL;   // Python 期望切比雪夫时间(匀速口径)")
L.append("    ExpTimeAccel : REAL;   // Python 期望时间(L1 梯形加减速口径,T22 比对)")
L.append("END_STRUCT")
L.append("END_TYPE")
L.append("")
L.append("(* ---------- DUT:ST_AwraCell(T25 终局布局向量) ---------- *)")
L.append("TYPE ST_AwraCell :")
L.append("STRUCT")
L.append("    Id : INT;    // 货物序号")
L.append("    X  : INT;    // 终局列")
L.append("    Y  : INT;    // 终局层")
L.append("END_STRUCT")
L.append("END_TYPE")
L.append("")
L.append("(* ---------- GVL:GVL_Data ---------- *)")
L.append("VAR_GLOBAL CONSTANT")
L.append(f"    N_DEMO    : INT := {N_DEMO};")
L.append(f"    N_TESTVEC : INT := {len(vecs)};")
L.append(f"    N_AWRA    : INT := {len(awra_cells)};   // T25 终局向量件数")
L.append(f"    AWRA_PLACED : INT := {m_a['n'] - m_a['fail']};")
L.append(f"    AWRA_FAILED : INT := {m_a['fail']};")
L.append(f"    LAM_F : REAL := {LAM[0]};   // Rank λ 频次(单源,ST FC_CalcPriority 应引用)")
L.append(f"    LAM_W : REAL := {LAM[1]};   // Rank λ 重量")
L.append(f"    LAM_V : REAL := {LAM[2]};   // Rank λ 体积")
L.append(f"    MAX_LS_ROUNDS : INT := {MAX_LS};   // LS 最大轮数(单源,ST nMaxLsRounds 应引用)")
L.append("END_VAR")
L.append("VAR_GLOBAL")
L.append("    aTestVec : ARRAY[1..10] OF ST_TestVec := [")
for i, (w, f, c, t, wm, fm, es, et, eta) in enumerate(vecs):
    sep = "," if i < len(vecs) - 1 else ""
    L.append(f"        (W := {w}, F := {f}, X := {c}, Y := {t}, "
             f"WMax := {wm}, FMax := {fm}, "
             f"ExpScore := {es:.6f}, ExpTime := {et:.6f}, ExpTimeAccel := {eta:.6f}){sep}")
L.append("    ];")
# ---- T25 终局布局向量 + 期望聚合统计 ----
L.append(f"    aAwraExpect : ARRAY[1..{len(awra_cells)}] OF ST_AwraCell := [")
for i, (gid, cx, cy) in enumerate(awra_cells):
    sep = "," if i < len(awra_cells) - 1 else ""
    L.append(f"        (Id := {gid}, X := {cx}, Y := {cy}){sep}")
L.append("    ];")
L.append(f"    AWRA_EXPT   : REAL := {m_a['exp_t']:.6f};   // 期望取货时间(ExpRetrieval 比对,容差1e-3)")
L.append(f"    AWRA_ENERGY : REAL := {m_a['energy']:.6f};  // 能耗 kg·m(Energy 比对)")
L.append(f"    AWRA_COG    : REAL := {m_a['cog']:.6f};     // 重心高(CogHeight 比对)")
# ---- T68/T69:CB/TOB 终局布局向量+期望聚合(0712 轨B D-1;复用 ST_AwraCell) ----
L.append(f"    N_CB      : INT := {len(cb_cells)};   // T68 CB 终局向量件数")
L.append(f"    aCbExpect : ARRAY[1..{len(cb_cells)}] OF ST_AwraCell := [")
for i, (gid, cx, cy) in enumerate(cb_cells):
    sep = "," if i < len(cb_cells) - 1 else ""
    L.append(f"        (Id := {gid}, X := {cx}, Y := {cy}){sep}")
L.append("    ];")
L.append(f"    CB_EXPT   : REAL := {m_cb['exp_t']:.6f};")
L.append(f"    CB_ENERGY : REAL := {m_cb['energy']:.6f};")
L.append(f"    CB_PLACED : INT := {m_cb['n'] - m_cb['fail']};")
L.append(f"    CB_FAILED : INT := {m_cb['fail']};")
L.append(f"    N_TOB      : INT := {len(tob_cells)};   // T69 TOB 终局向量件数")
L.append(f"    aTobExpect : ARRAY[1..{len(tob_cells)}] OF ST_AwraCell := [")
for i, (gid, cx, cy) in enumerate(tob_cells):
    sep = "," if i < len(tob_cells) - 1 else ""
    L.append(f"        (Id := {gid}, X := {cx}, Y := {cy}){sep}")
L.append("    ];")
L.append(f"    TOB_EXPT   : REAL := {m_tob['exp_t']:.6f};")
L.append(f"    TOB_ENERGY : REAL := {m_tob['energy']:.6f};")
L.append(f"    TOB_PLACED : INT := {m_tob['n'] - m_tob['fail']};")
L.append(f"    TOB_FAILED : INT := {m_tob['fail']};")
L.append("END_VAR")
L.append("")
L.append("(* ---------- FC_LoadDemoGoods:载入演示批次(与 Python 仿真同源同 seed) ---------- *)")
L.append("FUNCTION FC_LoadDemoGoods : BOOL")
L.append("VAR")
L.append("    n : INT;")
L.append("END_VAR")
L.append("// 0712 轨B N4-15:满仓护栏(拒载不部分写入;调用点另有同判断=双保险,T61 锁)")
L.append("IF GVL_WH.iGoodsCount + GVL_Data.N_DEMO > GVL_Param.MAX_GOODS THEN")
L.append("    FC_LoadDemoGoods := FALSE;")
L.append("    RETURN;")
L.append("END_IF")
L.append("// 0712 轨B R1:ID 冲突拒载(演示批固定 Id 1..N_DEMO;表内已有任一同域 Id 即整批拒绝,")
L.append("//   防重复身份破坏查询/统计唯一性契约=N4-16 的演示批入口闭环;二次载入自然被拒,T61 锁)")
L.append("FOR n := 1 TO GVL_WH.iGoodsCount DO")
L.append("    IF (GVL_WH.aGoods[n].Id >= 1) AND (GVL_WH.aGoods[n].Id <= GVL_Data.N_DEMO) THEN")
L.append("        FC_LoadDemoGoods := FALSE;")
L.append("        RETURN;")
L.append("    END_IF")
L.append("END_FOR")
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
print(f"演示批次 {N_DEMO} 件(seed={SEED}),测试向量 {len(vecs)} 条(含加减速期望值)")
print(f"AWRA 终局向量 {len(awra_cells)} 件(sum 口径,placed={m_a['n']-m_a['fail']} "
      f"failed={m_a['fail']} exp_t={m_a['exp_t']:.3f} energy={m_a['energy']:.1f})")
for i, (w, f, c, t, wm, fm, es, et, eta) in enumerate(vecs[:3], 1):
    print(f"  vec{i}: W={w} F={f} slot=({c},{t}) -> score={es:.6f} "
          f"t_uni={et:.3f} t_acc={eta:.3f}")
