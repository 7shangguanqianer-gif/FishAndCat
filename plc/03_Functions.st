(* ============================================================
   03_Functions.st — 纯函数(FC,无状态,可单元测试)
   导入方法:Application 右键 → 添加对象 → POU,类型选"功能(Function)",
            每个 FUNCTION 建一个 POU,粘贴对应段落
   一致性:每个函数与 sim/warehouse_sim.py 同名逻辑一字对齐,
          由 sim/export_st_vectors.py 生成的测试向量在 PRG_Test 中比对
   ============================================================ *)

(* ---------- FC_CapCoef:层承重系数(题面:底层1.0,每层-0.02) ---------- *)
FUNCTION FC_CapCoef : REAL
VAR_INPUT
    y : INT;                    // 层号 0..19
END_VAR
VAR
    yy : INT;
END_VAR
// 边界:越界钳位(边界判断清单#1)
IF y < 0 THEN
    yy := 0;
ELSIF y > GVL_Param.TIERS - 1 THEN
    yy := GVL_Param.TIERS - 1;
ELSE
    yy := y;
END_IF
FC_CapCoef := 1.0 - 0.02 * INT_TO_REAL(yy);
END_FUNCTION


(* ---------- FC_IsPresetOccupied:预占用判定(B1 三种解读封装,赛前可切) ---------- *)
FUNCTION FC_IsPresetOccupied : BOOL
VAR_INPUT
    x     : INT;
    y     : INT;
    iRule : INT;                // 0=and(49格) 1=or(231格) 2=linear(134格)
END_VAR
FC_IsPresetOccupied := FALSE;
IF x < 0 OR x > GVL_Param.COLS - 1 OR y < 0 OR y > GVL_Param.TIERS - 1 THEN
    RETURN;                     // 越界视为不可用由 FC_CheckFeasible 把关,这里仅答"是否预占"
END_IF
CASE iRule OF
    0: FC_IsPresetOccupied := (x MOD 3 = 0) AND (y MOD 3 = 0);
    1: FC_IsPresetOccupied := (x MOD 3 = 0) OR  (y MOD 3 = 0);
    2: FC_IsPresetOccupied := ((x * GVL_Param.TIERS + y) MOD 3 = 0);
ELSE
    FC_IsPresetOccupied := (x MOD 3 = 0) AND (y MOD 3 = 0);   // 非法规则回落默认
END_CASE
END_FUNCTION


(* ---------- FC_CheckFeasible:仓位可行性(边界判断核心) ---------- *)
FUNCTION FC_CheckFeasible : BOOL
VAR_INPUT
    x          : INT;           // 目标仓位
    y          : INT;
    rGoodW     : REAL;          // 货物重量
    rGoodV     : REAL;          // 货物体积
END_VAR
FC_CheckFeasible := FALSE;
// 边界清单:越界 / 负属性 / 占用(含预占) / 超重 / 超容积
IF x < 0 OR x > GVL_Param.COLS - 1 OR y < 0 OR y > GVL_Param.TIERS - 1 THEN RETURN; END_IF
IF rGoodW < 0.0 OR rGoodV < 0.0 THEN RETURN; END_IF
IF GVL_WH.aSlots[x, y].Occupied THEN RETURN; END_IF
IF rGoodW > GVL_WH.aSlots[x, y].MaxWeight THEN RETURN; END_IF
IF rGoodV > GVL_WH.aSlots[x, y].MaxVolume THEN RETURN; END_IF
FC_CheckFeasible := TRUE;
END_FUNCTION


(* ---------- FC_FitsPhysical:仅物理约束(局部交换用:目标位即将腾出,不查占用) ---------- *)
FUNCTION FC_FitsPhysical : BOOL
VAR_INPUT
    x      : INT;
    y      : INT;
    rGoodW : REAL;
    rGoodV : REAL;
END_VAR
FC_FitsPhysical := FALSE;
IF x < 0 OR x > GVL_Param.COLS - 1 OR y < 0 OR y > GVL_Param.TIERS - 1 THEN RETURN; END_IF
IF rGoodW < 0.0 OR rGoodV < 0.0 THEN RETURN; END_IF
IF rGoodW > GVL_WH.aSlots[x, y].MaxWeight THEN RETURN; END_IF
IF rGoodV > GVL_WH.aSlots[x, y].MaxVolume THEN RETURN; END_IF
FC_FitsPhysical := TRUE;
END_FUNCTION


(* ---------- FC_CalcTravelTime:行程时间(A5/A9:双模型开关) ----------
   主口径 = 切比雪夫:水平/垂直双电机同时运动,取慢轴(AS/RS 文献标准)
   对照   = 顺序模型:先水平后垂直(资料包保守模型,答辩演示差异用)   *)
FUNCTION FC_CalcTravelTime : REAL
VAR_INPUT
    x0, y0, x1, y1  : INT;      // 起点/终点(格坐标)
    xSimXY          : BOOL;     // TRUE=切比雪夫 FALSE=顺序
END_VAR
VAR
    dx, dy, tx, ty : REAL;
    vx, vy         : REAL;
END_VAR
dx := ABS(INT_TO_REAL(x1 - x0)) * GVL_Param.CELL_W;
dy := ABS(INT_TO_REAL(y1 - y0)) * GVL_Param.CELL_H;
// 边界:速度非法保护(边界清单#8思想:非法输入修正)
vx := GVL_Param.rVx;  IF vx <= 0.0 THEN vx := 1.0; END_IF
vy := GVL_Param.rVy;  IF vy <= 0.0 THEN vy := 1.0; END_IF
tx := dx / vx;
ty := dy / vy;
IF xSimXY THEN
    FC_CalcTravelTime := MAX(tx, ty) + GVL_Param.rTLoad + GVL_Param.rTUnload;
ELSE
    FC_CalcTravelTime := tx + ty + GVL_Param.rTLoad + GVL_Param.rTUnload;
END_IF
END_FUNCTION


(* ---------- FC_CalcPathLen:路径长度(曼哈顿,口径C2:与时间并列呈现不混用) ---------- *)
FUNCTION FC_CalcPathLen : REAL
VAR_INPUT
    x0, y0, x1, y1 : INT;
END_VAR
FC_CalcPathLen := ABS(INT_TO_REAL(x1 - x0)) * GVL_Param.CELL_W
                + ABS(INT_TO_REAL(y1 - y0)) * GVL_Param.CELL_H;
END_FUNCTION


(* ---------- FC_TMax:全库最远仓位单程时间(评分归一分母) ---------- *)
FUNCTION FC_TMax : REAL
FC_TMax := MAX(INT_TO_REAL(GVL_Param.COLS - 1) * GVL_Param.CELL_W / GVL_Param.rVx,
               INT_TO_REAL(GVL_Param.TIERS - 1) * GVL_Param.CELL_H / GVL_Param.rVy);
END_FUNCTION


(* ---------- FC_CalcScore:多目标评分(与 Python make_score_fn 一字对齐) ----------
   score = α·(频次/最大)·(时间/最大)   效率:高频货放远处要罚
         + β·(重量/最大)·(层/最高层)   稳定:重货放高层要罚
         + γ·(重量·高度)/(最大做功)    能耗:提升做功要罚(绿色指标)
         + δ·(1-频次归一)·(1-时间归一) 预留:冷门货占近位要罚(F2:无此项退化为就近贪心)
   注意:时间项用切比雪夫(xSimultaneousXY=TRUE 的主口径),归一分母 FC_TMax  *)
FUNCTION FC_CalcScore : REAL
VAR_INPUT
    rGoodW  : REAL;             // 货物重量
    rGoodF  : REAL;             // 货物频次
    x, y    : INT;              // 候选仓位
    rWMax   : REAL;             // 当前批次最大重量(归一)
    rFMax   : REAL;             // 当前批次最大频次(归一)
END_VAR
VAR
    tNorm, fNorm, hMax : REAL;
    eff, stab, energy, resv : REAL;
END_VAR
// 边界:归一分母保护
IF rWMax <= 0.0 THEN rWMax := 1.0; END_IF
IF rFMax <= 0.0 THEN rFMax := 1.0; END_IF
hMax := INT_TO_REAL(GVL_Param.TIERS - 1) * GVL_Param.CELL_H;

tNorm  := FC_CalcTravelTime(x0 := 0, y0 := 0, x1 := x, y1 := y,
                            xSimXY := GVL_Param.xSimultaneousXY) / FC_TMax();
fNorm  := rGoodF / rFMax;
eff    := fNorm * tNorm;
stab   := (rGoodW / rWMax) * (INT_TO_REAL(y) / INT_TO_REAL(GVL_Param.TIERS - 1));
energy := (rGoodW * INT_TO_REAL(y) * GVL_Param.CELL_H) / (rWMax * hMax);
resv   := (1.0 - fNorm) * (1.0 - tNorm);

FC_CalcScore := GVL_Param.rAlpha * eff + GVL_Param.rBeta * stab
              + GVL_Param.rGamma * energy + GVL_Param.rDelta * resv;
END_FUNCTION


(* ---------- FC_CalcPriority:Rank 阶段优先级(AWRA-LS 第一段) ----------
   高频、重、大体积优先分配 —— λ2 重量权重保证紧库存下重货先占低层(F3) *)
FUNCTION FC_CalcPriority : REAL
VAR_INPUT
    rGoodF : REAL;
    rGoodW : REAL;
    rGoodV : REAL;
    rFMax  : REAL;
    rWMax  : REAL;
    rVMax  : REAL;
END_VAR
IF rFMax <= 0.0 THEN rFMax := 1.0; END_IF
IF rWMax <= 0.0 THEN rWMax := 1.0; END_IF
IF rVMax <= 0.0 THEN rVMax := 1.0; END_IF
FC_CalcPriority := GVL_Param.rLambda1 * rGoodF / rFMax
                 + GVL_Param.rLambda2 * rGoodW / rWMax
                 + GVL_Param.rLambda3 * rGoodV / rVMax;
END_FUNCTION
