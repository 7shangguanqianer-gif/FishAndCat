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
// 边界清单:越界 / 负属性 / 检修挂起 / 占用(含预占) / 超重 / 超容积
IF x < 0 OR x > GVL_Param.COLS - 1 OR y < 0 OR y > GVL_Param.TIERS - 1 THEN RETURN; END_IF
IF rGoodW < 0.0 OR rGoodV < 0.0 THEN RETURN; END_IF
IF GVL_WH.aMaintBlock[x, y] THEN RETURN; END_IF      // A3 putaway block:检修位禁新入库
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
// A3:交换目标位检修中=禁入(检修位上的货可被换走,但别的货不得换进来——
//     与 SAP EWM putaway block"存量可出、新增禁入"语义一致)
IF GVL_WH.aMaintBlock[x, y] THEN RETURN; END_IF
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


(* ---------- FC_TMax:全库最远仓位单程时间(评分归一分母) ----------
   0712 轨B N4-24+R4:速度<=0 回落 1.0——与 FC_CalcTravelTime(:129-130) **同一安全值**,
   保证非法速度下分子/分母同源、tNorm 不失真(旧 0.001 版会把分母吹到 19000,评分坍缩)。
   公式恒匀速=已知口径(N4-01,不随 xUseAccel 变)。 *)
FUNCTION FC_TMax : REAL
VAR
    rVxSafe, rVySafe : REAL;
END_VAR
rVxSafe := GVL_Param.rVx;  IF rVxSafe <= 0.0 THEN rVxSafe := 1.0; END_IF
rVySafe := GVL_Param.rVy;  IF rVySafe <= 0.0 THEN rVySafe := 1.0; END_IF
FC_TMax := MAX(INT_TO_REAL(GVL_Param.COLS - 1) * GVL_Param.CELL_W / rVxSafe,
               INT_TO_REAL(GVL_Param.TIERS - 1) * GVL_Param.CELL_H / rVySafe);
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
   颜色 DWORD 格式 = RGBA 16#AARRGGBB,前导字节 AA 为透明度:FF=不透明,00=全透明
   (官方 "Color definition in RGBA color space";AB2.9 Visualization Manager 的
   半透明绘制默认开启,前导字节按 alpha 解释——0710 实证:16#00RRGGBB 渲染为全透明,
   画面 400 格因此"看不见颜色",修为 16#FF 前缀)。
   状态编码与 GVL_Visu.VisuSlotState 注释一一对应:0空闲/1预占/2占用/3推荐/4路径/5报警。
   改配色只改这里——画面 400 个矩形元件不写死任何颜色(单一真相源)。 *)
FUNCTION FC_StateToColor : DWORD
VAR_INPUT
    iState : INT;
END_VAR
CASE iState OF
    0: FC_StateToColor := 16#FFE8E8E8;   // 空闲:浅灰
    1: FC_StateToColor := 16#FF707070;   // 预占用:深灰
    2: FC_StateToColor := 16#FF43A047;   // 已占用:绿
    3: FC_StateToColor := 16#FFFFC107;   // 当前推荐:黄
    4: FC_StateToColor := 16#FF42A5F5;   // 路径:蓝
    5: FC_StateToColor := 16#FFE53935;   // 报警:红
    6: FC_StateToColor := 16#FF26C6DA;   // 查询高亮:青(块3 P3,FB_QueryGood 置位)
    7: FC_StateToColor := 16#FF8E24AA;   // 检修挂起:紫(A3,FB_VisuRefresh 按 aMaintBlock 叠加)
ELSE
    FC_StateToColor := 16#FFFF00FF;      // 未知状态:品红(醒目,便于发现bug)
END_CASE
END_FUNCTION


(* ---------- FC_MaintToggle:检修挂起/恢复翻转(A3,0711) ----------
   语义=SAP EWM bin blocking 的 putaway block:挂起只禁"新入库"(FC_CheckFeasible/
   FC_FitsPhysical 已排除),已有货物原地冻结、查询照常;恢复即重新入分配池。
   需管理员(iLevel>=1)——检修是设备物理操作,权限门与 A4 联动。
   返回码:0=已挂起 1=已恢复 2=需管理员 3=坐标越界。
   带副作用(写 GVL_WH.aMaintBlock / GVL_Visu.VisuMaintCount),风格同 FC_LoadDemoGoods。 *)
FUNCTION FC_MaintToggle : INT
VAR_INPUT
    x      : INT;
    y      : INT;
    iLevel : INT;               // 当前用户级(FB_UserAuth 输出)
END_VAR
IF iLevel < 1 THEN
    FC_MaintToggle := 2;  RETURN;
END_IF
IF x < 0 OR x > GVL_Param.COLS - 1 OR y < 0 OR y > GVL_Param.TIERS - 1 THEN
    FC_MaintToggle := 3;  RETURN;
END_IF
IF GVL_WH.aMaintBlock[x, y] THEN
    GVL_WH.aMaintBlock[x, y] := FALSE;
    GVL_Visu.VisuMaintCount := GVL_Visu.VisuMaintCount - 1;
    FC_MaintToggle := 1;
ELSE
    GVL_WH.aMaintBlock[x, y] := TRUE;
    GVL_Visu.VisuMaintCount := GVL_Visu.VisuMaintCount + 1;
    FC_MaintToggle := 0;
END_IF
END_FUNCTION


(* ---------- FC_HeatColor:热力色阶(C2/C6,0711) ----------
   值→蓝(冷)→黄(中)→红(热)三段线性插值,工业监控惯例。
   端点:0=16#FF1565C0 蓝 / 0.5=16#FFFFD600 黄 / 1=16#FFE53935 红;rMax<=0 返回蓝(防除)。
   RGBA 前导 FF=不透明(0710 实证:00 前缀渲染全透明)。 *)
FUNCTION FC_HeatColor : DWORD
VAR_INPUT
    rVal : REAL;
    rMax : REAL;
END_VAR
VAR
    rT, rSeg : REAL;       // 勿用 t/d 等单字母(TIME/DATE 字面量前缀保留,同 0706 r/s 教训)
    iR, iG, iB : INT;
END_VAR
IF rMax <= 0.0 THEN
    FC_HeatColor := 16#FF1565C0;  RETURN;
END_IF
rT := rVal / rMax;
IF rT < 0.0 THEN rT := 0.0; END_IF
IF rT > 1.0 THEN rT := 1.0; END_IF
IF rT < 0.5 THEN
    rSeg := rT * 2.0;                            // 蓝(21,101,192)→黄(255,214,0)
    iR := REAL_TO_INT(21.0  + (255.0 - 21.0)  * rSeg);
    iG := REAL_TO_INT(101.0 + (214.0 - 101.0) * rSeg);
    iB := REAL_TO_INT(192.0 + (0.0   - 192.0) * rSeg);
ELSE
    rSeg := (rT - 0.5) * 2.0;                    // 黄(255,214,0)→红(229,57,53)
    iR := REAL_TO_INT(255.0 + (229.0 - 255.0) * rSeg);
    iG := REAL_TO_INT(214.0 + (57.0  - 214.0) * rSeg);
    iB := REAL_TO_INT(0.0   + (53.0  - 0.0)   * rSeg);
END_IF
FC_HeatColor := 16#FF000000
    OR SHL(INT_TO_DWORD(iR), 16) OR SHL(INT_TO_DWORD(iG), 8) OR INT_TO_DWORD(iB);
END_FUNCTION


(* ---------- FC_BlendLight:向白混色 45%(C1 层高亮,0711) ----------
   任意底色(状态/热力)上的选中层加亮通道:每通道 c := c + (255-c)*0.45。 *)
FUNCTION FC_BlendLight : DWORD
VAR_INPUT
    dw : DWORD;
END_VAR
VAR
    iR, iG, iB : INT;
END_VAR
iR := DWORD_TO_INT(SHR(dw, 16) AND 16#FF);
iG := DWORD_TO_INT(SHR(dw, 8) AND 16#FF);
iB := DWORD_TO_INT(dw AND 16#FF);
iR := REAL_TO_INT(INT_TO_REAL(iR) + (255.0 - INT_TO_REAL(iR)) * 0.45);
iG := REAL_TO_INT(INT_TO_REAL(iG) + (255.0 - INT_TO_REAL(iG)) * 0.45);
iB := REAL_TO_INT(INT_TO_REAL(iB) + (255.0 - INT_TO_REAL(iB)) * 0.45);
FC_BlendLight := 16#FF000000
    OR SHL(INT_TO_DWORD(iR), 16) OR SHL(INT_TO_DWORD(iG), 8) OR INT_TO_DWORD(iB);
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
