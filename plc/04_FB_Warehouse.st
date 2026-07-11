(* ============================================================
   04_FB_Warehouse.st — 功能块(FB,有状态)
   导入方法:每个 FUNCTION_BLOCK 建一个 POU(类型"功能块"),粘贴对应段落
   核心设计:扫描周期感知的分片执行 —— 批量分配与局部搜索都做成
   跨周期状态机,每个扫描周期只处理有限计算量(GVL_Param.nBatchPerCycle/
   nPairsPerCycle),不阻塞、不触发看门狗;xBusy/xDone 汇报进度。
   这是本方案的 PLC 原生工程点:优化算法以非阻塞方式跑在实时控制器上。
   ============================================================ *)

(* ---------- FB_InitWarehouse:初始化仓库(单周期) ---------- *)
FUNCTION_BLOCK FB_InitWarehouse
VAR_INPUT
    xExecute : BOOL;            // 上升沿触发
    iRule    : INT;             // 预占用解读(B1)
END_VAR
VAR_OUTPUT
    xDone     : BOOL;
    iPreCount : INT;            // 预占用格数(rule3=133官方/rule0=49/rule1=231/rule2=134,自检用)
END_VAR
VAR
    xOld : BOOL;
    x, y : INT;
END_VAR

IF xExecute AND NOT xOld THEN
    iPreCount := 0;
    FOR x := 0 TO GVL_Param.COLS - 1 DO
        FOR y := 0 TO GVL_Param.TIERS - 1 DO
            GVL_WH.aSlots[x, y].X         := x;
            GVL_WH.aSlots[x, y].Y         := y;
            GVL_WH.aSlots[x, y].CapCoef   := FC_CapCoef(y := y);
            GVL_WH.aSlots[x, y].MaxWeight := GVL_WH.aSlots[x, y].CapCoef * GVL_Param.BASE_CAP;
            GVL_WH.aSlots[x, y].MaxVolume := GVL_Param.CELL_VOL;
            GVL_WH.aSlots[x, y].PresetOcc := FC_IsPresetOccupied(x := x, y := y, iRule := iRule);
            GVL_WH.aSlots[x, y].Occupied  := GVL_WH.aSlots[x, y].PresetOcc;
            GVL_WH.aSlots[x, y].GoodsId   := 0;
            IF GVL_WH.aSlots[x, y].PresetOcc THEN
                iPreCount := iPreCount + 1;
                GVL_Visu.VisuSlotState[x, y] := 1;   // 深灰:预占用
            ELSE
                GVL_Visu.VisuSlotState[x, y] := 0;   // 浅灰:空闲
            END_IF
        END_FOR
    END_FOR
    xDone := TRUE;
END_IF
// 0711 修:完成即撤沿。本 FB 是"单拍完成+完成拍输入仍 TRUE+完成后停止调用"模式,
// 旧写法 xOld:=xExecute 会把 xOld 冻结在 TRUE,Reset 二次进入时沿失效→仓库不重建、
// xDone 残留 TRUE 令状态机瞬转(实测:Reset 后 aSlots 旧占位残留/统计跳算的根因之一)。
xOld := xExecute AND NOT xDone;
END_FUNCTION_BLOCK


(* ---------- FB_SelectSlot:单件货选位(单周期,400 仓位全扫描) ----------
   iStrategy: 0=seq 首个可行位(题面"连续存放"字面基线)
              1=near 行程时间最小
              2=score 多目标评分最小(主线)
   扫描顺序 x外层/y内层,平局保留先者 —— 与 Python 迭代序/tie-break 一字对齐 *)
FUNCTION_BLOCK FB_SelectSlot
VAR_INPUT
    iStrategy : INT;
    rGoodW    : REAL;
    rGoodF    : REAL;
    rGoodV    : REAL;
    rWMax     : REAL;           // 批次归一分母(由调用方维护)
    rFMax     : REAL;
END_VAR
VAR_OUTPUT
    xFound     : BOOL;
    iBestX     : INT;
    iBestY     : INT;
    rBestScore : REAL;
    rBestTime  : REAL;
END_VAR
VAR
    x, y      : INT;
    rS, rT    : REAL;
    xBetter   : BOOL;
END_VAR

xFound := FALSE;
iBestX := -1;  iBestY := -1;
rBestScore := 3.4E38;  rBestTime := 3.4E38;

FOR x := 0 TO GVL_Param.COLS - 1 DO
    FOR y := 0 TO GVL_Param.TIERS - 1 DO
        IF FC_CheckFeasible(x := x, y := y, rGoodW := rGoodW, rGoodV := rGoodV) THEN
            IF iStrategy = 0 THEN
                // seq:第一个可行位即返回
                xFound := TRUE;  iBestX := x;  iBestY := y;
                rBestTime  := FC_CalcTravelTime(x0 := 0, y0 := 0, x1 := x, y1 := y,
                                                xSimXY := GVL_Param.xSimultaneousXY);
                rBestScore := FC_CalcScore(rGoodW := rGoodW, rGoodF := rGoodF, x := x, y := y,
                                           rWMax := rWMax, rFMax := rFMax);
                RETURN;
            END_IF
            rT := FC_CalcTravelTime(x0 := 0, y0 := 0, x1 := x, y1 := y,
                                    xSimXY := GVL_Param.xSimultaneousXY);
            IF iStrategy = 1 THEN
                // near:按 (时间, 层, 列) 严格更小才替换(平局保先者=Python min 语义)
                xBetter := rT < rBestTime;
            ELSE
                // score:按 (评分, 时间) 严格更小;层/列由扫描顺序天然兜底
                rS := FC_CalcScore(rGoodW := rGoodW, rGoodF := rGoodF, x := x, y := y,
                                   rWMax := rWMax, rFMax := rFMax);
                xBetter := (rS < rBestScore) OR ((rS = rBestScore) AND (rT < rBestTime));
            END_IF
            IF xBetter THEN
                xFound := TRUE;  iBestX := x;  iBestY := y;  rBestTime := rT;
                IF iStrategy = 2 THEN rBestScore := rS;
                ELSE rBestScore := FC_CalcScore(rGoodW := rGoodW, rGoodF := rGoodF,
                                                x := x, y := y, rWMax := rWMax, rFMax := rFMax);
                END_IF
            END_IF
        END_IF
    END_FOR
END_FOR
END_FUNCTION_BLOCK


(* ---------- FB_AssignAllGoods:批量分配(分片状态机,跨扫描周期) ----------
   xUseRank=TRUE  → AWRA 模式:先按优先级排序(重货/高频先挑),再逐件选位
   xUseRank=FALSE → 在线模式:按到达顺序逐件选位(决赛交互场景等价)
   每周期只处理 nBatchPerCycle 件(排序阶段每周期 nSortOuter 个外层位),非阻塞 *)
FUNCTION_BLOCK FB_AssignAllGoods
VAR_INPUT
    xStart    : BOOL;           // 上升沿启动
    xUseRank  : BOOL;
    iStrategy : INT;            // 传给 FB_SelectSlot(0/1/2)
END_VAR
VAR_OUTPUT
    xBusy     : BOOL;
    xDone     : BOOL;
    iAssigned : INT;
    iFailed   : INT;
END_VAR
VAR
    xOld       : BOOL;
    iPhase     : INT;           // 0=空闲 1=算优先级+初始化索引 2=排序 3=分配 4=完成
    i, j, k    : INT;
    iCur       : INT;           // 分配游标(在 aRankIdx 上)
    iSortPos   : INT;           // 选择排序外层游标
    nSortOuter : INT := 20;     // 排序阶段每周期处理的外层位数
    iBestJ     : INT;
    iTmp       : INT;
    rWMax, rFMax, rVMax : REAL;
    fbSel      : FB_SelectSlot;
    iG         : INT;
END_VAR

IF xStart AND NOT xOld THEN
    IF GVL_WH.iGoodsCount > 0 THEN
        iPhase := 1;  xBusy := TRUE;  xDone := FALSE;
        iAssigned := 0;  iFailed := 0;  iCur := 1;  iSortPos := 1;
    END_IF
END_IF
xOld := xStart;

CASE iPhase OF
    1:  // ---- 归一分母 + 优先级 + 索引初始化(单周期,O(n)) ----
        rWMax := 0.0;  rFMax := 0.0;  rVMax := 0.0;
        FOR i := 1 TO GVL_WH.iGoodsCount DO
            IF GVL_WH.aGoods[i].Weight > rWMax THEN rWMax := GVL_WH.aGoods[i].Weight; END_IF
            IF GVL_WH.aGoods[i].Freq   > rFMax THEN rFMax := GVL_WH.aGoods[i].Freq;   END_IF
            IF GVL_WH.aGoods[i].Volume > rVMax THEN rVMax := GVL_WH.aGoods[i].Volume; END_IF
        END_FOR
        FOR i := 1 TO GVL_WH.iGoodsCount DO
            GVL_WH.aRankIdx[i] := i;
            GVL_WH.aGoods[i].Priority := FC_CalcPriority(
                rGoodF := GVL_WH.aGoods[i].Freq,  rGoodW := GVL_WH.aGoods[i].Weight,
                rGoodV := GVL_WH.aGoods[i].Volume,
                rFMax := rFMax, rWMax := rWMax, rVMax := rVMax);
        END_FOR
        IF xUseRank THEN iPhase := 2; ELSE iPhase := 3; END_IF

    2:  // ---- Rank:选择排序(优先级降序,平局按Id升序;分片:每周期 nSortOuter 位) ----
        k := 0;
        WHILE (k < nSortOuter) AND (iSortPos < GVL_WH.iGoodsCount) DO
            iBestJ := iSortPos;
            FOR j := iSortPos + 1 TO GVL_WH.iGoodsCount DO
                IF (GVL_WH.aGoods[GVL_WH.aRankIdx[j]].Priority >
                    GVL_WH.aGoods[GVL_WH.aRankIdx[iBestJ]].Priority)
                OR ((GVL_WH.aGoods[GVL_WH.aRankIdx[j]].Priority =
                     GVL_WH.aGoods[GVL_WH.aRankIdx[iBestJ]].Priority)
                    AND (GVL_WH.aRankIdx[j] < GVL_WH.aRankIdx[iBestJ])) THEN
                    iBestJ := j;
                END_IF
            END_FOR
            iTmp := GVL_WH.aRankIdx[iSortPos];
            GVL_WH.aRankIdx[iSortPos] := GVL_WH.aRankIdx[iBestJ];
            GVL_WH.aRankIdx[iBestJ]   := iTmp;
            iSortPos := iSortPos + 1;
            k := k + 1;
        END_WHILE
        IF iSortPos >= GVL_WH.iGoodsCount THEN iPhase := 3; END_IF

    3:  // ---- Assign:逐件选位(分片:每周期 nBatchPerCycle 件) ----
        k := 0;
        WHILE (k < GVL_Param.nBatchPerCycle) AND (iCur <= GVL_WH.iGoodsCount) DO
            iG := GVL_WH.aRankIdx[iCur];
            fbSel(iStrategy := iStrategy,
                  rGoodW := GVL_WH.aGoods[iG].Weight,
                  rGoodF := GVL_WH.aGoods[iG].Freq,
                  rGoodV := GVL_WH.aGoods[iG].Volume,
                  rWMax := rWMax, rFMax := rFMax);
            IF fbSel.xFound THEN
                GVL_WH.aSlots[fbSel.iBestX, fbSel.iBestY].Occupied := TRUE;
                GVL_WH.aSlots[fbSel.iBestX, fbSel.iBestY].GoodsId  := GVL_WH.aGoods[iG].Id;
                GVL_WH.aGoods[iG].Assigned   := TRUE;
                GVL_WH.aGoods[iG].X          := fbSel.iBestX;
                GVL_WH.aGoods[iG].Y          := fbSel.iBestY;
                GVL_WH.aGoods[iG].Score      := fbSel.rBestScore;
                GVL_WH.aGoods[iG].ExecTime   := fbSel.rBestTime;
                GVL_WH.aGoods[iG].PathLength := FC_CalcPathLen(x0 := 0, y0 := 0,
                                                x1 := fbSel.iBestX, y1 := fbSel.iBestY);
                GVL_Visu.VisuSlotState[fbSel.iBestX, fbSel.iBestY] := 2;   // 绿:已占
                iAssigned := iAssigned + 1;
            ELSE
                // 边界:无可行位 → 计数并报警文本(边界清单#9)
                GVL_WH.aGoods[iG].Assigned := FALSE;
                GVL_WH.aGoods[iG].X := -1;  GVL_WH.aGoods[iG].Y := -1;
                iFailed := iFailed + 1;
                GVL_Visu.VisuStatusText := CONCAT('NO_SLOT_GOODS_ID=',
                                                  INT_TO_STRING(GVL_WH.aGoods[iG].Id));
            END_IF
            iCur := iCur + 1;
            k := k + 1;
        END_WHILE
        IF iCur > GVL_WH.iGoodsCount THEN iPhase := 4; END_IF

    4:  // ---- 完成 ----
        xBusy := FALSE;  xDone := TRUE;  iPhase := 0;
END_CASE
END_FUNCTION_BLOCK


(* ---------- FB_LocalSwapImprove:局部搜索(AWRA-LS 第三段,分片状态机) ----------
   每轮 = 重定位阶段(逐货找更优空位)+ 成对交换阶段(互换后总分下降则换);
   有改进继续下一轮(≤nMaxLsRounds),无改进提前收敛。
   一切换位前重查物理约束(FC_FitsPhysical,边界清单#10)。 *)
FUNCTION_BLOCK FB_LocalSwapImprove
VAR_INPUT
    xStart : BOOL;
END_VAR
VAR_OUTPUT
    xBusy   : BOOL;
    xDone   : BOOL;
    iSwaps  : INT;
    iRelocs : INT;
    iRounds : INT;
END_VAR
VAR
    xOld       : BOOL;
    iPhase     : INT;           // 0=空闲 1=重定位 2=交换 3=轮末判定 4=完成
    xImproved  : BOOL;
    iCurR      : INT;           // 重定位游标(aRankIdx 序,与 Python 一致)
    iI, iJ     : INT;           // 交换双游标(i<j)
    k, x, y    : INT;
    iGi, iGj   : INT;
    rWMax, rFMax : REAL;
    i          : INT;
    rCur, rBest, rS, rOld, rNew : REAL;
    iBx, iBy   : INT;
    xiA, yiA, xjA, yjA : INT;
END_VAR

IF xStart AND NOT xOld THEN
    IF GVL_WH.iGoodsCount > 0 THEN
        // 归一分母与分配阶段口径一致
        rWMax := 0.0;  rFMax := 0.0;
        FOR i := 1 TO GVL_WH.iGoodsCount DO
            IF GVL_WH.aGoods[i].Weight > rWMax THEN rWMax := GVL_WH.aGoods[i].Weight; END_IF
            IF GVL_WH.aGoods[i].Freq   > rFMax THEN rFMax := GVL_WH.aGoods[i].Freq;   END_IF
        END_FOR
        iPhase := 1;  xBusy := TRUE;  xDone := FALSE;
        iSwaps := 0;  iRelocs := 0;  iRounds := 1;  xImproved := FALSE;
        iCurR := 1;  iI := 1;  iJ := 2;
    END_IF
END_IF
xOld := xStart;

CASE iPhase OF
    1:  // ---- 重定位:每周期 nBatchPerCycle 件,每件全库扫描更优空位 ----
        k := 0;
        WHILE (k < GVL_Param.nBatchPerCycle) AND (iCurR <= GVL_WH.iGoodsCount) DO
            iGi := GVL_WH.aRankIdx[iCurR];
            IF GVL_WH.aGoods[iGi].Assigned THEN
                rCur := FC_CalcScore(rGoodW := GVL_WH.aGoods[iGi].Weight,
                                     rGoodF := GVL_WH.aGoods[iGi].Freq,
                                     x := GVL_WH.aGoods[iGi].X, y := GVL_WH.aGoods[iGi].Y,
                                     rWMax := rWMax, rFMax := rFMax);
                rBest := rCur;  iBx := -1;  iBy := -1;
                FOR x := 0 TO GVL_Param.COLS - 1 DO
                    FOR y := 0 TO GVL_Param.TIERS - 1 DO
                        IF FC_CheckFeasible(x := x, y := y,
                                            rGoodW := GVL_WH.aGoods[iGi].Weight,
                                            rGoodV := GVL_WH.aGoods[iGi].Volume) THEN
                            rS := FC_CalcScore(rGoodW := GVL_WH.aGoods[iGi].Weight,
                                               rGoodF := GVL_WH.aGoods[iGi].Freq,
                                               x := x, y := y, rWMax := rWMax, rFMax := rFMax);
                            IF rS < rBest - 0.000001 THEN
                                rBest := rS;  iBx := x;  iBy := y;
                            END_IF
                        END_IF
                    END_FOR
                END_FOR
                IF iBx >= 0 THEN
                    // 搬移:旧位腾空,新位占用,货物记录/可视化联动
                    GVL_WH.aSlots[GVL_WH.aGoods[iGi].X, GVL_WH.aGoods[iGi].Y].Occupied := FALSE;
                    GVL_WH.aSlots[GVL_WH.aGoods[iGi].X, GVL_WH.aGoods[iGi].Y].GoodsId  := 0;
                    GVL_Visu.VisuSlotState[GVL_WH.aGoods[iGi].X, GVL_WH.aGoods[iGi].Y] := 0;
                    GVL_WH.aSlots[iBx, iBy].Occupied := TRUE;
                    GVL_WH.aSlots[iBx, iBy].GoodsId  := GVL_WH.aGoods[iGi].Id;
                    GVL_Visu.VisuSlotState[iBx, iBy] := 2;
                    GVL_WH.aGoods[iGi].X := iBx;  GVL_WH.aGoods[iGi].Y := iBy;
                    GVL_WH.aGoods[iGi].Score := rBest;
                    GVL_WH.aGoods[iGi].ExecTime := FC_CalcTravelTime(x0 := 0, y0 := 0,
                                        x1 := iBx, y1 := iBy, xSimXY := GVL_Param.xSimultaneousXY);
                    GVL_WH.aGoods[iGi].PathLength := FC_CalcPathLen(x0 := 0, y0 := 0, x1 := iBx, y1 := iBy);
                    iRelocs := iRelocs + 1;  xImproved := TRUE;
                END_IF
            END_IF
            iCurR := iCurR + 1;  k := k + 1;
        END_WHILE
        IF iCurR > GVL_WH.iGoodsCount THEN
            iPhase := 2;  iI := 1;  iJ := 2;
        END_IF

    2:  // ---- 成对交换:每周期 nPairsPerCycle 对 ----
        k := 0;
        WHILE (k < GVL_Param.nPairsPerCycle) AND (iI < GVL_WH.iGoodsCount) DO
            iGi := GVL_WH.aRankIdx[iI];  iGj := GVL_WH.aRankIdx[iJ];
            IF GVL_WH.aGoods[iGi].Assigned AND GVL_WH.aGoods[iGj].Assigned THEN
                xiA := GVL_WH.aGoods[iGi].X;  yiA := GVL_WH.aGoods[iGi].Y;
                xjA := GVL_WH.aGoods[iGj].X;  yjA := GVL_WH.aGoods[iGj].Y;
                // 换位前双向物理约束复查(承重/容积)
                IF FC_FitsPhysical(x := xjA, y := yjA, rGoodW := GVL_WH.aGoods[iGi].Weight,
                                   rGoodV := GVL_WH.aGoods[iGi].Volume)
                AND FC_FitsPhysical(x := xiA, y := yiA, rGoodW := GVL_WH.aGoods[iGj].Weight,
                                    rGoodV := GVL_WH.aGoods[iGj].Volume) THEN
                    rOld := FC_CalcScore(rGoodW := GVL_WH.aGoods[iGi].Weight, rGoodF := GVL_WH.aGoods[iGi].Freq,
                                         x := xiA, y := yiA, rWMax := rWMax, rFMax := rFMax)
                          + FC_CalcScore(rGoodW := GVL_WH.aGoods[iGj].Weight, rGoodF := GVL_WH.aGoods[iGj].Freq,
                                         x := xjA, y := yjA, rWMax := rWMax, rFMax := rFMax);
                    rNew := FC_CalcScore(rGoodW := GVL_WH.aGoods[iGi].Weight, rGoodF := GVL_WH.aGoods[iGi].Freq,
                                         x := xjA, y := yjA, rWMax := rWMax, rFMax := rFMax)
                          + FC_CalcScore(rGoodW := GVL_WH.aGoods[iGj].Weight, rGoodF := GVL_WH.aGoods[iGj].Freq,
                                         x := xiA, y := yiA, rWMax := rWMax, rFMax := rFMax);
                    IF rNew < rOld - 0.000001 THEN
                        GVL_WH.aSlots[xiA, yiA].GoodsId := GVL_WH.aGoods[iGj].Id;
                        GVL_WH.aSlots[xjA, yjA].GoodsId := GVL_WH.aGoods[iGi].Id;
                        GVL_WH.aGoods[iGi].X := xjA;  GVL_WH.aGoods[iGi].Y := yjA;
                        GVL_WH.aGoods[iGj].X := xiA;  GVL_WH.aGoods[iGj].Y := yiA;
                        GVL_WH.aGoods[iGi].ExecTime := FC_CalcTravelTime(x0 := 0, y0 := 0,
                                            x1 := xjA, y1 := yjA, xSimXY := GVL_Param.xSimultaneousXY);
                        GVL_WH.aGoods[iGj].ExecTime := FC_CalcTravelTime(x0 := 0, y0 := 0,
                                            x1 := xiA, y1 := yiA, xSimXY := GVL_Param.xSimultaneousXY);
                        GVL_WH.aGoods[iGi].PathLength := FC_CalcPathLen(x0 := 0, y0 := 0, x1 := xjA, y1 := yjA);
                        GVL_WH.aGoods[iGj].PathLength := FC_CalcPathLen(x0 := 0, y0 := 0, x1 := xiA, y1 := yiA);
                        iSwaps := iSwaps + 1;  xImproved := TRUE;
                    END_IF
                END_IF
            END_IF
            // 游标推进(i<j 上三角遍历)
            iJ := iJ + 1;
            IF iJ > GVL_WH.iGoodsCount THEN
                iI := iI + 1;  iJ := iI + 1;
            END_IF
            k := k + 1;
        END_WHILE
        IF iI >= GVL_WH.iGoodsCount THEN iPhase := 3; END_IF

    3:  // ---- 轮末判定 ----
        IF xImproved AND (iRounds < GVL_Param.nMaxLsRounds) THEN
            iRounds := iRounds + 1;  xImproved := FALSE;
            iCurR := 1;  iPhase := 1;               // 下一轮从重定位开始
        ELSE
            iPhase := 4;
        END_IF

    4:  // ---- 完成 ----
        xBusy := FALSE;  xDone := TRUE;  iPhase := 0;
END_CASE
END_FUNCTION_BLOCK


(* ---------- FB_Stats:统计计算(单周期;口径C1-C8,与 Python metrics 对齐) ---------- *)
FUNCTION_BLOCK FB_Stats
VAR_INPUT
    xExecute : BOOL;
END_VAR
VAR_OUTPUT
    xDone : BOOL;
END_VAR
VAR
    xOld : BOOL;
    i, x, y, nUsed : INT;
    rT, rFSum, rWSum, rFT, rWH : REAL;
END_VAR

IF xExecute AND NOT xOld THEN
    GVL_WH.stStats.PlacedCnt := 0;   GVL_WH.stStats.FailedCnt := 0;
    GVL_WH.stStats.TotalTime2Way := 0.0;  GVL_WH.stStats.PathTotal2Way := 0.0;
    GVL_WH.stStats.Energy := 0.0;    GVL_WH.stStats.ViolCnt := 0;
    rFSum := 0.0;  rWSum := 0.0;  rFT := 0.0;  rWH := 0.0;

    FOR i := 1 TO GVL_WH.iGoodsCount DO
        IF GVL_WH.aGoods[i].Assigned THEN
            GVL_WH.stStats.PlacedCnt := GVL_WH.stStats.PlacedCnt + 1;
            rT := GVL_WH.aGoods[i].ExecTime;
            GVL_WH.stStats.TotalTime2Way  := GVL_WH.stStats.TotalTime2Way  + 2.0 * rT;
            GVL_WH.stStats.PathTotal2Way  := GVL_WH.stStats.PathTotal2Way  + 2.0 * GVL_WH.aGoods[i].PathLength;
            rFSum := rFSum + GVL_WH.aGoods[i].Freq;
            rFT   := rFT   + GVL_WH.aGoods[i].Freq * rT;
            rWSum := rWSum + GVL_WH.aGoods[i].Weight;
            rWH   := rWH   + GVL_WH.aGoods[i].Weight * INT_TO_REAL(GVL_WH.aGoods[i].Y) * GVL_Param.CELL_H;
            // C8 违规复查:分配结果必须仍满足约束(恒0,非0=程序缺陷立即可见)
            IF (GVL_WH.aGoods[i].Weight > GVL_WH.aSlots[GVL_WH.aGoods[i].X, GVL_WH.aGoods[i].Y].MaxWeight)
            OR (GVL_WH.aGoods[i].Volume > GVL_WH.aSlots[GVL_WH.aGoods[i].X, GVL_WH.aGoods[i].Y].MaxVolume) THEN
                GVL_WH.stStats.ViolCnt := GVL_WH.stStats.ViolCnt + 1;
            END_IF
        ELSE
            GVL_WH.stStats.FailedCnt := GVL_WH.stStats.FailedCnt + 1;
        END_IF
    END_FOR

    IF GVL_WH.stStats.PlacedCnt > 0 THEN
        GVL_WH.stStats.AvgTime := GVL_WH.stStats.TotalTime2Way / INT_TO_REAL(GVL_WH.stStats.PlacedCnt);
    ELSE
        GVL_WH.stStats.AvgTime := 0.0;
    END_IF
    IF rFSum > 0.0 THEN GVL_WH.stStats.ExpRetrieval := rFT / rFSum; ELSE GVL_WH.stStats.ExpRetrieval := 0.0; END_IF
    IF rWSum > 0.0 THEN GVL_WH.stStats.CogHeight := rWH / rWSum;    ELSE GVL_WH.stStats.CogHeight := 0.0;    END_IF
    GVL_WH.stStats.Energy := rWH;                       // Σ 重量*高度 kg·m(C4)

    nUsed := 0;
    FOR x := 0 TO GVL_Param.COLS - 1 DO
        FOR y := 0 TO GVL_Param.TIERS - 1 DO
            IF GVL_WH.aSlots[x, y].Occupied THEN nUsed := nUsed + 1; END_IF
        END_FOR
    END_FOR
    GVL_WH.stStats.UtilPct := INT_TO_REAL(nUsed) / INT_TO_REAL(GVL_Param.COLS * GVL_Param.TIERS);

    // 同步可视化统计区
    GVL_Visu.VisuTotalTime := GVL_WH.stStats.TotalTime2Way;
    GVL_Visu.VisuAvgTime   := GVL_WH.stStats.AvgTime;
    GVL_Visu.VisuSpaceUtilization := GVL_WH.stStats.UtilPct;
    GVL_Visu.VisuViolationCount   := GVL_WH.stStats.ViolCnt;
    xDone := TRUE;
END_IF
// 0711 修:完成即撤沿(同 FB_InitWarehouse)。旧写法在"单拍完成+完成拍 xExecute=TRUE+
// 完成后不再被调用"下冻结 xOld→第二次批量统计跳算,显示残留 Reset 清的 0(实测复现)。
xOld := xExecute AND NOT xDone;
END_FUNCTION_BLOCK


(* ---------- FB_AnimatePath:堆垛机动画回放(L6 决赛可视化核心) ----------
   沿 VisuPath 的 L 形物理走线逐点推进 VisuCurrentX/Y,总时长 = 该点切比雪夫
   行程时间 × 回放倍率(口径 C2:显示走线为曼哈顿,时序按切比雪夫等比回放,
   两口径并列的动画化呈现)。先调 FB_BuildVisuPath 生成路径再启动本 FB。 *)
FUNCTION_BLOCK FB_AnimatePath
VAR_INPUT
    xStart      : BOOL;         // 上升沿启动回放
    rCycleTime  : REAL := 0.01; // 本任务周期 s(10ms 任务填 0.01)
    rSpeedScale : REAL := 5.0;  // 回放倍速(5=五倍速演示)
END_VAR
VAR_OUTPUT
    xBusy : BOOL;
    xDone : BOOL;
END_VAR
VAR
    xOld     : BOOL;
    rElapsed : REAL;            // 已回放的"仿真时间" s
    rTotal   : REAL;            // 目标点切比雪夫总时长 s
    iIdx     : INT;
END_VAR

IF xStart AND NOT xOld THEN
    IF GVL_Visu.VisuPathCount > 1 THEN
        rTotal := FC_CalcTravelTime(x0 := 0, y0 := 0,
                                    x1 := GVL_Visu.VisuTargetX, y1 := GVL_Visu.VisuTargetY,
                                    xSimXY := GVL_Param.xSimultaneousXY);
        IF rTotal <= 0.0 THEN rTotal := 0.001; END_IF
        rElapsed := 0.0;  xBusy := TRUE;  xDone := FALSE;
        GVL_Visu.VisuCurrentX := GVL_Visu.VisuPathX[0];
        GVL_Visu.VisuCurrentY := GVL_Visu.VisuPathY[0];
    END_IF
END_IF
xOld := xStart;

IF xBusy THEN
    IF GVL_Visu.VisuPathCount < 2 THEN
        // 回放途中路径被外部清除(复位/批量启动会清 VisuPathCount)→ 中止,
        // 否则下面 PathCount-1 = -1 会造成数组负索引越界(真实边界,勿删护栏)
        xBusy := FALSE;  xDone := TRUE;
    ELSE
        rElapsed := rElapsed + rCycleTime * rSpeedScale;
        // 路径索引 = 已过时间占比 × 路径点数(线性等比映射)
        iIdx := REAL_TO_INT(rElapsed / rTotal * INT_TO_REAL(GVL_Visu.VisuPathCount - 1));
        IF iIdx >= GVL_Visu.VisuPathCount - 1 THEN
            iIdx := GVL_Visu.VisuPathCount - 1;
            xBusy := FALSE;  xDone := TRUE;
        END_IF
        GVL_Visu.VisuCurrentX := GVL_Visu.VisuPathX[iIdx];
        GVL_Visu.VisuCurrentY := GVL_Visu.VisuPathY[iIdx];
    END_IF
END_IF
END_FUNCTION_BLOCK


(* ---------- FB_ScanLoadProbe:L4 扫描周期负载实测(AC500 实现章的实测数据源) ----------
   用法:在要测量的代码段前后各调一次:
     fbProbe(xStart := TRUE);   (* 段前 *)
     ... 被测代码(如 fbAssign 一个分片周期)...
     fbProbe(xStop := TRUE);    (* 段后 *)
   输出微秒级 单次/平均/最大 耗时与样本数 —— 报告里给出
   "10ms 任务周期下分片计算占用 X%(看门狗裕量 Y 倍)"的实测表。 *)
FUNCTION_BLOCK FB_ScanLoadProbe
VAR_INPUT
    xStart : BOOL;
    xStop  : BOOL;
END_VAR
VAR_OUTPUT
    rLastUs : REAL;             // 最近一次段耗时 µs
    rAvgUs  : REAL;
    rMaxUs  : REAL;
    nSamples: DINT;
END_VAR
VAR
    tT0     : LTIME;
    xArmed  : BOOL;
    rSumUs  : LREAL;
END_VAR

IF xStart THEN
    tT0 := LTIME();             // CODESYS 3.5 高精度单调时钟(ns 分辨率)
    xArmed := TRUE;
END_IF
IF xStop AND xArmed THEN
    rLastUs := LREAL_TO_REAL(LTIME_TO_LREAL(LTIME() - tT0) / 1000.0);   // ns→µs
    rSumUs := rSumUs + rLastUs;
    nSamples := nSamples + 1;
    IF rLastUs > rMaxUs THEN rMaxUs := rLastUs; END_IF
    rAvgUs := LREAL_TO_REAL(rSumUs / DINT_TO_LREAL(nSamples));
    xArmed := FALSE;
END_IF
END_FUNCTION_BLOCK


(* ---------- FB_BuildVisuPath:生成 L 形路径点(决赛可视化路径展示) ----------
   物理走线按"先水平后垂直"展开为逐格路径点(曼哈顿口径);
   执行时间按切比雪夫另算 —— 两口径并列,呼应 C2。 *)
FUNCTION_BLOCK FB_BuildVisuPath
VAR_INPUT
    xExecute : BOOL;
    iToX     : INT;
    iToY     : INT;
END_VAR
VAR_OUTPUT
    xDone : BOOL;
END_VAR
VAR
    xOld : BOOL;
    n, x, y : INT;
END_VAR

IF xExecute AND NOT xOld THEN
    n := 0;
    IF iToX >= 0 AND iToX <= GVL_Param.COLS - 1 AND iToY >= 0 AND iToY <= GVL_Param.TIERS - 1 THEN
        FOR x := 0 TO iToX DO                       // 水平段(含起点(0,0))
            GVL_Visu.VisuPathX[n] := x;  GVL_Visu.VisuPathY[n] := 0;  n := n + 1;
        END_FOR
        FOR y := 1 TO iToY DO                       // 垂直段
            GVL_Visu.VisuPathX[n] := iToX;  GVL_Visu.VisuPathY[n] := y;  n := n + 1;
        END_FOR
        GVL_Visu.VisuTargetX := iToX;  GVL_Visu.VisuTargetY := iToY;
        GVL_Visu.VisuPathLen  := FC_CalcPathLen(x0 := 0, y0 := 0, x1 := iToX, y1 := iToY);
        GVL_Visu.VisuExecTime := FC_CalcTravelTime(x0 := 0, y0 := 0, x1 := iToX, y1 := iToY,
                                                   xSimXY := GVL_Param.xSimultaneousXY);
    END_IF
    GVL_Visu.VisuPathCount := n;
    xDone := TRUE;
END_IF
xOld := xExecute;
END_FUNCTION_BLOCK


(* ---------- FB_VisuRefresh:可视化镜像刷新(L6,PRG_Main 尾部每周期常驻调用) ----------
   职责=把"算法语义层"翻译成"画面显示层",三件事:
   1. VisuSlotState[列,层] → VisuSlotColor[列,显示行]:状态→颜色查表 + 上下翻转
      (仓库层0在底、画面行0在顶,显示行 = TIERS-1-层)——画面矩形阵列只绑颜色数组;
   2. 路径叠加:VisuPath 各点在颜色层画蓝,但只叠加在空闲/预占格上
      (不写 VisuSlotState 语义层,避免"蓝色盖掉已占格后无法恢复"的状态污染);
   3. 堆垛机像素坐标:VisuCurrentX/Y(格)→ VisuCraneXpx/Ypx(px,含翻转),
      供堆垛机图元的 Absolute movement 绑定(图元设计位置放 (0,0),偏移即绝对)。
   开销:400 次查表+少量换算/周期 ≈ 微秒级,常驻无压力(L4 实测口径可佐证)。 *)
FUNCTION_BLOCK FB_VisuRefresh
VAR
    c, rw, k, iSt : INT;   // rw=显示行(r/s 是 IEC 置复位保留字,不可作变量名——0706 无头编译揪出的潜伏 bug)
END_VAR

// 1) 状态→颜色 + 上下翻转(显示行 r=0 是画面顶=层19)
//    块3 方向9:对比模式(CmdCompareMode 且已存快照)色源=aSnapState 冻结布局,
//    否则=实时 VisuSlotState;色表仍 FC_StateToColor 单源(画面标准 §2)
FOR c := 0 TO GVL_Param.COLS - 1 DO
    FOR rw := 0 TO GVL_Param.TIERS - 1 DO
        IF GVL_Visu.CmdCompareMode AND GVL_Visu.xSnapValid THEN
            iSt := GVL_Visu.aSnapState[c, GVL_Param.TIERS - 1 - rw];
        ELSE
            iSt := GVL_Visu.VisuSlotState[c, GVL_Param.TIERS - 1 - rw];
        END_IF
        GVL_Visu.VisuSlotColor[c, rw] := FC_StateToColor(iState := iSt);
    END_FOR
END_FOR

// 2) 路径叠加(蓝):只画在空闲/预占格上,已占/推荐格保持原色;
//    对比模式跳过——快照是纯布局对比,叠实时路径会误导(块3)
IF NOT (GVL_Visu.CmdCompareMode AND GVL_Visu.xSnapValid) THEN
    FOR k := 0 TO GVL_Visu.VisuPathCount - 1 DO
        IF k > 39 THEN EXIT; END_IF                   // 路径数组上限 40 点,防越界
        iSt := GVL_Visu.VisuSlotState[GVL_Visu.VisuPathX[k], GVL_Visu.VisuPathY[k]];
        IF iSt = 0 OR iSt = 1 THEN
            GVL_Visu.VisuSlotColor[GVL_Visu.VisuPathX[k],
                                   GVL_Param.TIERS - 1 - GVL_Visu.VisuPathY[k]] :=
                FC_StateToColor(iState := 4);
        END_IF
    END_FOR
END_IF

// 3) 堆垛机格坐标 → 像素坐标(图元锚点=左上角,大小=一个单元格)
GVL_Visu.VisuCraneXpx := GVL_Param.GRID_X0 + GVL_Visu.VisuCurrentX * GVL_Param.CELL_PX_W;
GVL_Visu.VisuCraneYpx := GVL_Param.GRID_Y0
    + (GVL_Param.TIERS - 1 - GVL_Visu.VisuCurrentY) * GVL_Param.CELL_PX_H;
END_FUNCTION_BLOCK


(* ---------- FB_GoodsInput:交互货物输入封装(评分细则6/7;0707 T2.2 从 PRG_Main 抽取) ----------
   功能:题面五属性(序号/名称/重量/频次/体积)输入 → 边界校验 → 写入货物表 → 即时推荐仓位。
         把"关键交互算法封装为功能块,IO 参数设计合理"(评分细则6)显式化。
   输入:xAdd 上升沿触发;iId/sName/rWeight/rFreq/rVolume = 题面五属性。
   输出:xOk 成功入表;xFound 有推荐位;iSugX/iSugY 推荐列/层;
         iErrId 错误码 0=ok / 1=满仓 / 2=负输入 / 3=无可行位。
   边界:满仓(≥MAX_GOODS)→iErrId=1;任一属性<0→iErrId=2;无可行位(如超重货)→iErrId=3。
   示例:xAdd 上升沿+合法轻货 → xOk=TRUE,xFound=TRUE,iSug=近位;超重货 → xOk=TRUE,iErrId=3。
   分层:可视化(推荐高亮/路径叠加/状态文本/报警灯)由调用方 PRG_Main 按本 FB 输出编排——
         本 FB 只算(可单元测试),PRG_Main 只画(画面职责)。 *)
FUNCTION_BLOCK FB_GoodsInput
VAR_INPUT
    xAdd    : BOOL;             // 添加触发(上升沿)
    iId     : INT;
    sName   : STRING[32];
    rWeight : REAL;
    rFreq   : REAL;
    rVolume : REAL;
END_VAR
VAR_OUTPUT
    xOk     : BOOL;             // 本次是否成功入表
    xFound  : BOOL;             // 是否有推荐仓位
    iSugX   : INT;              // 推荐列
    iSugY   : INT;              // 推荐层
    iErrId  : INT;             // 0=ok 1=满仓 2=负输入 3=无可行位
END_VAR
VAR
    xOld    : BOOL;
    i       : INT;
    rWMaxTmp, rFMaxTmp : REAL;
    fbSel   : FB_SelectSlot;
END_VAR

xOk := FALSE;  xFound := FALSE;  iErrId := 0;  iSugX := -1;  iSugY := -1;
IF xAdd AND NOT xOld THEN
    IF GVL_WH.iGoodsCount >= GVL_Param.MAX_GOODS THEN
        iErrId := 1;                                    // 边界:满仓拒收
    ELSIF rWeight < 0.0 OR rFreq < 0.0 OR rVolume < 0.0 THEN
        iErrId := 2;                                    // 边界:负属性拒收
    ELSE
        GVL_WH.iGoodsCount := GVL_WH.iGoodsCount + 1;
        GVL_WH.aGoods[GVL_WH.iGoodsCount].Id       := iId;
        GVL_WH.aGoods[GVL_WH.iGoodsCount].Name     := sName;
        GVL_WH.aGoods[GVL_WH.iGoodsCount].Weight   := rWeight;
        GVL_WH.aGoods[GVL_WH.iGoodsCount].Freq     := rFreq;
        GVL_WH.aGoods[GVL_WH.iGoodsCount].Volume   := rVolume;
        GVL_WH.aGoods[GVL_WH.iGoodsCount].Assigned := FALSE;
        xOk := TRUE;
        // 即时推荐(归一分母取当前批次最大,与 score 口径一致)
        rWMaxTmp := MAX(rWeight, 1.0);  rFMaxTmp := MAX(rFreq, 1.0);
        FOR i := 1 TO GVL_WH.iGoodsCount DO
            IF GVL_WH.aGoods[i].Weight > rWMaxTmp THEN rWMaxTmp := GVL_WH.aGoods[i].Weight; END_IF
            IF GVL_WH.aGoods[i].Freq   > rFMaxTmp THEN rFMaxTmp := GVL_WH.aGoods[i].Freq;   END_IF
        END_FOR
        fbSel(iStrategy := 2, rGoodW := rWeight, rGoodF := rFreq, rGoodV := rVolume,
              rWMax := rWMaxTmp, rFMax := rFMaxTmp);
        IF fbSel.xFound THEN
            xFound := TRUE;  iSugX := fbSel.iBestX;  iSugY := fbSel.iBestY;
        ELSE
            iErrId := 3;                                // 无可行位(如超重货连底层都放不下)
        END_IF
    END_IF
END_IF
xOld := xAdd;
END_FUNCTION_BLOCK


(* ---------- FB_QueryGood:单件查询(评分细则8"统计信息";块3 P3 查询页) ----------
   功能:按序号扫货物表 → 五属性+位置+路径长/行程时间(存量口径)+载货行程/装卸档
        (U2 拟真对照,调参区改 rLadenFactorVY/装卸三档此二值实时变)→ 网格青色高亮。
   输入:xQuery 上升沿触发;iId 查询序号。
   输出:直接写 GVL_Visu.Qry* 组(画面服务 FB,同 FB_VisuRefresh 先例);
        高亮=VisuSlotState 置 6,旧高亮恢复为 2(命中货必 Assigned=原状态已占用)。
   边界:iId<=0 → QryFound=FALSE;未找到 → 全字段清零;未分配货 → 位置=-1、时间组=0。
   示例:查演示批 Id=1 → QryFound=TRUE,位置/时间齐,该格变青;查 Id=999 → FALSE。 *)
FUNCTION_BLOCK FB_QueryGood
VAR_INPUT
    xQuery : BOOL;              // 查询触发(上升沿)
    iId    : INT;               // 查询序号
END_VAR
VAR
    xOld   : BOOL;
    i      : INT;
    iLastX : INT := -1;         // 上次高亮列(-1=无,清除用)
    iLastY : INT := -1;         // 上次高亮层
END_VAR

IF xQuery AND NOT xOld THEN
    // 清上次青色高亮(只清仍=6 的格,防误清其他状态;恢复为 2=已占用)
    IF iLastX >= 0 AND iLastY >= 0 THEN
        IF GVL_Visu.VisuSlotState[iLastX, iLastY] = 6 THEN
            GVL_Visu.VisuSlotState[iLastX, iLastY] := 2;
        END_IF
        iLastX := -1;  iLastY := -1;
    END_IF
    // 输出组清零(未命中时字段不残留上次结果)
    GVL_Visu.QryFound := FALSE;
    GVL_Visu.QryX := -1;            GVL_Visu.QryY := -1;
    GVL_Visu.QryName := '';         GVL_Visu.QryWeight := 0.0;
    GVL_Visu.QryFreq := 0.0;        GVL_Visu.QryVolume := 0.0;
    GVL_Visu.QryPathLen := 0.0;     GVL_Visu.QryExecTime := 0.0;
    GVL_Visu.QryTravelLaden := 0.0; GVL_Visu.QryHandleT := 0.0;
    IF iId > 0 THEN                                   // 边界:非正序号直接未找到
        FOR i := 1 TO GVL_WH.iGoodsCount DO
            IF GVL_WH.aGoods[i].Id = iId THEN
                GVL_Visu.QryFound  := TRUE;
                GVL_Visu.QryName   := GVL_WH.aGoods[i].Name;
                GVL_Visu.QryWeight := GVL_WH.aGoods[i].Weight;
                GVL_Visu.QryFreq   := GVL_WH.aGoods[i].Freq;
                GVL_Visu.QryVolume := GVL_WH.aGoods[i].Volume;
                IF GVL_WH.aGoods[i].Assigned THEN
                    GVL_Visu.QryX        := GVL_WH.aGoods[i].X;
                    GVL_Visu.QryY        := GVL_WH.aGoods[i].Y;
                    GVL_Visu.QryPathLen  := GVL_WH.aGoods[i].PathLength;
                    GVL_Visu.QryExecTime := GVL_WH.aGoods[i].ExecTime;
                    // U2 拟真对照:载货行程(垂直折减)+ 装卸三档(调参区实时联动)
                    GVL_Visu.QryTravelLaden := FC_TravelLaden(
                        x0 := 0, y0 := 0,
                        x1 := GVL_WH.aGoods[i].X, y1 := GVL_WH.aGoods[i].Y,
                        xSimXY := GVL_Param.xSimultaneousXY);
                    GVL_Visu.QryHandleT := FC_HandleTime(rW := GVL_WH.aGoods[i].Weight);
                    // 青色高亮 + 记住位置供下次清除
                    GVL_Visu.VisuSlotState[GVL_WH.aGoods[i].X, GVL_WH.aGoods[i].Y] := 6;
                    iLastX := GVL_WH.aGoods[i].X;
                    iLastY := GVL_WH.aGoods[i].Y;
                END_IF
                EXIT;                                 // 序号唯一,命中即止
            END_IF
        END_FOR
    END_IF
END_IF
xOld := xQuery;
END_FUNCTION_BLOCK


(* ---------- FB_RecordPage:统计记录页 10 行窗口(评分细则8;块3 P2) ----------
   功能:aGoods 全表 → 10 行显示窗口(aRow* 并行数组),翻页上升沿±10 并钳位;
        每周期常驻刷新(数据总最新;40 次数组访问,微秒级)。
   设计:窗口映射而非 400 行整表 —— WebVisu 渲染预算(画面标准 §6)+ 一屏一焦点(§3)。
   输入:xPageUp/xPageDown 翻页按钮(上升沿)。
   输出:直接写 GVL_Visu.aRow*/iRecTop/iRecTotal(画面服务 FB)。
   边界:iRecTop 钳位 [1, max(1, iGoodsCount-9)];窗口越界行 Id=0(画面按 0 显示空行);
        未分配货位置=-1、数值=0(与查询页口径一致)。
   示例:120 件表,iRecTop=1 显示 1..10;PageDown→11..20;拉到底 111..120 后再按不动。 *)
FUNCTION_BLOCK FB_RecordPage
VAR_INPUT
    xPageUp   : BOOL;           // 上翻(上升沿,-10)
    xPageDown : BOOL;           // 下翻(上升沿,+10)
END_VAR
VAR
    xUpOld, xDnOld : BOOL;
    k, idx         : INT;
END_VAR

// 翻页(上升沿)
IF xPageUp AND NOT xUpOld THEN
    GVL_Visu.iRecTop := GVL_Visu.iRecTop - 10;
END_IF
IF xPageDown AND NOT xDnOld THEN
    GVL_Visu.iRecTop := GVL_Visu.iRecTop + 10;
END_IF
xUpOld := xPageUp;
xDnOld := xPageDown;

// 钳位:上限先于下限(空表时两界都收敛到 1)
IF GVL_Visu.iRecTop > GVL_WH.iGoodsCount - 9 THEN
    GVL_Visu.iRecTop := GVL_WH.iGoodsCount - 9;
END_IF
IF GVL_Visu.iRecTop < 1 THEN
    GVL_Visu.iRecTop := 1;
END_IF
GVL_Visu.iRecTotal := GVL_WH.iGoodsCount;

// 10 行窗口映射(常驻:批量分配进行中翻表也能看到最新位置)
FOR k := 0 TO 9 DO
    idx := GVL_Visu.iRecTop + k;
    IF idx >= 1 AND idx <= GVL_WH.iGoodsCount THEN
        GVL_Visu.aRowId[k] := GVL_WH.aGoods[idx].Id;
        IF GVL_WH.aGoods[idx].Assigned THEN
            GVL_Visu.aRowX[k]       := GVL_WH.aGoods[idx].X;
            GVL_Visu.aRowY[k]       := GVL_WH.aGoods[idx].Y;
            GVL_Visu.aRowPathLen[k] := GVL_WH.aGoods[idx].PathLength;
            GVL_Visu.aRowExecT[k]   := GVL_WH.aGoods[idx].ExecTime;
        ELSE
            GVL_Visu.aRowX[k]       := -1;    // 未分配:位置=-1(画面显示 "-")
            GVL_Visu.aRowY[k]       := -1;
            GVL_Visu.aRowPathLen[k] := 0.0;
            GVL_Visu.aRowExecT[k]   := 0.0;
        END_IF
    ELSE
        GVL_Visu.aRowId[k]      := 0;         // 越界:空行(Id=0 约定)
        GVL_Visu.aRowX[k]       := -1;
        GVL_Visu.aRowY[k]       := -1;
        GVL_Visu.aRowPathLen[k] := 0.0;
        GVL_Visu.aRowExecT[k]   := 0.0;
    END_IF
END_FOR
END_FUNCTION_BLOCK
