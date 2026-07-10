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


(* ---------- FC_IsPresetOccupied:预占用判定(B1 四解读封装;官方口径=3,2026-07-06 答复落地) ---------- *)
FUNCTION FC_IsPresetOccupied : BOOL
VAR_INPUT
    x     : INT;
    y     : INT;
    iRule : INT;                // 3=sum(133格,官方) 0=and(49格) 1=or(231格) 2=linear(134格)
END_VAR
FC_IsPresetOccupied := FALSE;
IF x < 0 OR x > GVL_Param.COLS - 1 OR y < 0 OR y > GVL_Param.TIERS - 1 THEN
    RETURN;                     // 越界视为不可用由 FC_CheckFeasible 把关,这里仅答"是否预占"
END_IF
CASE iRule OF
    3: FC_IsPresetOccupied := ((x + y) MOD 3 = 0);            // 官方口径(0706):x+y 之和能被3整除
    0: FC_IsPresetOccupied := (x MOD 3 = 0) AND (y MOD 3 = 0);
    1: FC_IsPresetOccupied := (x MOD 3 = 0) OR  (y MOD 3 = 0);
    2: FC_IsPresetOccupied := ((x * GVL_Param.TIERS + y) MOD 3 = 0);
ELSE
    FC_IsPresetOccupied := ((x + y) MOD 3 = 0);               // 非法规则回落官方口径
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


(* ---------- FC_AxisTime:L1 单轴行程时间(梯形/三角速度曲线) ----------
   与 Python axis_time 一字对齐:d≥v²/a → d/v+v/a(梯形);否则 2·√(d/a)(三角)。
   匀速模型系统性低估短程时间(实验发现 F7:对优化布局低估 43.5%)。 *)
FUNCTION FC_AxisTime : REAL
VAR_INPUT
    d    : REAL;                // 行程距离 m(非负)
    vmax : REAL;                // 峰值速度 m/s
    acc  : REAL;                // 加减速 m/s²
END_VAR
IF d <= 0.0 THEN
    FC_AxisTime := 0.0;
    RETURN;
END_IF
IF vmax <= 0.0 THEN vmax := 1.0; END_IF     // 非法输入保护
IF acc  <= 0.0 THEN acc  := 0.1; END_IF
IF d >= vmax * vmax / acc THEN
    FC_AxisTime := d / vmax + vmax / acc;
ELSE
    FC_AxisTime := 2.0 * SQRT(d / acc);
END_IF
END_FUNCTION


(* ---------- FC_CalcTravelTime:行程时间(A5/A9/A4b 三开关) ----------
   主口径 = 切比雪夫:双电机同动取慢轴;xSimXY=FALSE 退化为顺序模型(对照)。
   GVL_Param.xUseAccel=TRUE 时轴时间用梯形曲线(L1 工程口径),与 Python 同全局开关。 *)
FUNCTION FC_CalcTravelTime : REAL
VAR_INPUT
    x0, y0, x1, y1  : INT;      // 起点/终点(格坐标;支持任意两点,双命令周期用)
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
IF GVL_Param.xUseAccel THEN
    tx := FC_AxisTime(d := dx, vmax := vx, acc := GVL_Param.rAx);
    ty := FC_AxisTime(d := dy, vmax := vy, acc := GVL_Param.rAy);
ELSE
    tx := dx / vx;
    ty := dy / vy;
END_IF
IF xSimXY THEN
    FC_CalcTravelTime := MAX(tx, ty) + GVL_Param.rTLoad + GVL_Param.rTUnload;
ELSE
    FC_CalcTravelTime := tx + ty + GVL_Param.rTLoad + GVL_Param.rTUnload;
END_IF
END_FUNCTION


(* ---------- FC_CalcDualCycleTime:L2 双命令周期时间(C10 口径) ----------
   一趟联合行程:I/O→存位(带货)→取位(空驶联程)→I/O(带货);
   节省 = 单命令(2t存+2t取) − 本值 ≥ 0(切比雪夫三角不等式,有 Python 测试)。 *)
FUNCTION FC_CalcDualCycleTime : REAL
VAR_INPUT
    iStoreX, iStoreY : INT;     // 存位
    iRetrX,  iRetrY  : INT;     // 取位
END_VAR
FC_CalcDualCycleTime :=
      FC_CalcTravelTime(x0 := 0, y0 := 0, x1 := iStoreX, y1 := iStoreY,
                        xSimXY := GVL_Param.xSimultaneousXY)
    + FC_CalcTravelTime(x0 := iStoreX, y0 := iStoreY, x1 := iRetrX, y1 := iRetrY,
                        xSimXY := GVL_Param.xSimultaneousXY)
    + FC_CalcTravelTime(x0 := iRetrX, y0 := iRetrY, x1 := 0, y1 := 0,
                        xSimXY := GVL_Param.xSimultaneousXY);
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


(* ---------- FC_StateToColor:仓位状态码 → 画面填充色(L6 可视化) ----------
   颜色 DWORD 格式 16#00RRGGBB(CODESYS 颜色变量约定);
   状态编码与 GVL_Visu.VisuSlotState 注释一一对应:0空闲/1预占/2占用/3推荐/4路径/5报警。
   改配色只改这里——画面 400 个矩形元件不写死任何颜色(单一真相源)。 *)
FUNCTION FC_StateToColor : DWORD
VAR_INPUT
    iState : INT;
END_VAR
CASE iState OF
    0: FC_StateToColor := 16#00E8E8E8;   // 空闲:浅灰
    1: FC_StateToColor := 16#00707070;   // 预占用:深灰
    2: FC_StateToColor := 16#0043A047;   // 已占用:绿
    3: FC_StateToColor := 16#00FFC107;   // 当前推荐:黄
    4: FC_StateToColor := 16#0042A5F5;   // 路径:蓝
    5: FC_StateToColor := 16#00E53935;   // 报警:红
    6: FC_StateToColor := 16#0026C6DA;   // 查询高亮:青(块3 P3,FB_QueryGood 置位)
ELSE
    FC_StateToColor := 16#00FF00FF;      // 未知状态:品红(醒目,便于发现bug)
END_CASE
END_FUNCTION


(* ---------- FC_TravelLaden:载货行程时间(U2 载重运动学,块3 拟真对照) ----------
   功能:垂直轴速度 × GVL_Param.rLadenFactorVY(满载折减,默认0.80),水平不折减;
        xUseAccel/xSimXY 开关行为与 FC_CalcTravelTime 完全同构(sim travel_time_laden 一字对齐)。
   输入:x0,y0,x1,y1 格坐标;xSimXY TRUE=切比雪夫 FALSE=顺序模型
   输出:载货行程时间 s(纯行程,不含装卸——装卸另用 FC_HandleTime,避免双计 rTLoad)
   边界:速度/折减系数非法(<=0)钳回安全值;dx/dy 由 ABS 保证非负
   示例:laden(0,0→10,10) 主口径 vy=0.5×0.8=0.4 → MAX(10/2, 10/0.4)=25.0s(空载 20.0s,T45 锚)
   消费:FB_QueryGood(QryTravelLaden);不进评分/分配链路(零回归设计) *)
FUNCTION FC_TravelLaden : REAL
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
// 边界:速度与折减系数非法保护(调参区可被改出非法值,拒绝依赖画面侧校验)
vx := GVL_Param.rVx;  IF vx <= 0.0 THEN vx := 1.0; END_IF
vy := GVL_Param.rVy;  IF vy <= 0.0 THEN vy := 1.0; END_IF
IF GVL_Param.rLadenFactorVY > 0.0 AND GVL_Param.rLadenFactorVY <= 1.0 THEN
    vy := vy * GVL_Param.rLadenFactorVY;    // 满载垂直折减(仅垂直,U2 口径)
END_IF
IF GVL_Param.xUseAccel THEN
    tx := FC_AxisTime(d := dx, vmax := vx, acc := GVL_Param.rAx);
    ty := FC_AxisTime(d := dy, vmax := vy, acc := GVL_Param.rAy);
ELSE
    tx := dx / vx;
    ty := dy / vy;
END_IF
IF xSimXY THEN
    FC_TravelLaden := MAX(tx, ty);
ELSE
    FC_TravelLaden := tx + ty;
END_IF
END_FUNCTION


(* ---------- FC_HandleTime:装卸时间三档(U2 可变装卸,块3 拟真对照) ----------
   功能:按货物重量查三档装卸时长(轻<=W1→T1 / 中<=W2→T2 / 重>W2→T3);
        档界与时长全部 GVL_Param 参数化 = 画面调参区旋钮(改档界/时长,查询页数字实时变)。
   输入:rW 货物重量 kg(定义域>=0;负值落轻货档,入口校验由 FB_GoodsInput iErrId=2 兜底)
   输出:单次装卸时间 s(货叉全循环;sim handle_time 一字对齐,默认档 6.0/8.5/12.5)
   边界:档界被调成 W1>W2 时按 ELSIF 顺序自然判定(W1 优先),无崩溃路径
   示例:29.9→6.0 / 30.1→8.5 / 60.1→12.5(T44 三档边界锚,0.1 间隙避单精度) *)
FUNCTION FC_HandleTime : REAL
VAR_INPUT
    rW : REAL;                  // 货物重量 kg
END_VAR
IF rW <= GVL_Param.rHandleW1 THEN
    FC_HandleTime := GVL_Param.rHandleT1;
ELSIF rW <= GVL_Param.rHandleW2 THEN
    FC_HandleTime := GVL_Param.rHandleT2;
ELSE
    FC_HandleTime := GVL_Param.rHandleT3;
END_IF
END_FUNCTION
