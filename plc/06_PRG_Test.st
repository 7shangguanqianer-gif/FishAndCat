(* ============================================================
   06_PRG_Test.st — 边界与一致性测试程序
   导入方法:POU 类型"程序",可挂到同一任务或手动调用;
   置 xRunTests:=TRUE 单次运行,看 iPassed/iFailed/aResult。
   覆盖:资料包 §7.3 边界判断清单 + Python↔ST 评分一致性向量
   (向量由 sim/export_st_vectors.py 生成于 07_GVL_Data_generated.st,
    与仿真同源 —— 这是"PLC 实现与验证报告数字互相背书"的证据链)
   注意:测试会改写仓库状态,跑完请按 CmdReset 重新初始化再演示。
   ============================================================ *)
PROGRAM PRG_Test
VAR
    xRunTests : BOOL;                       // 置 TRUE 触发(自动复位)
    iPassed   : INT;
    iFailed   : INT;
    xAllPass  : BOOL;
    N_CASES   : INT := 23;                  // 用例总数(加用例先改这里,防空槽误计)
    aResult   : ARRAY[1..24] OF BOOL;       // 各用例结果(TRUE=通过)
    sLastFail : STRING[64];                 // 最后失败的用例名(排错入口)
    fbInit    : FB_InitWarehouse;
    fbSel     : FB_SelectSlot;
    i, x, y, n : INT;
    rV        : REAL;
    iVecFail  : INT;
END_VAR

IF xRunTests THEN
    xRunTests := FALSE;
    iPassed := 0;  iFailed := 0;  sLastFail := '';
    FOR i := 1 TO 24 DO aResult[i] := TRUE; END_FOR

    // ---- T01-T04 承重系数:正常/顶层/负钳位/越上钳位 ----
    aResult[1] := ABS(FC_CapCoef(y := 0)  - 1.0)  < 0.0001;
    aResult[2] := ABS(FC_CapCoef(y := 19) - 0.62) < 0.0001;
    aResult[3] := ABS(FC_CapCoef(y := -5) - 1.0)  < 0.0001;
    aResult[4] := ABS(FC_CapCoef(y := 25) - 0.62) < 0.0001;

    // ---- T05-T07 预占用三种解读的格数(49/231/134) ----
    n := 0;
    FOR x := 0 TO 19 DO FOR y := 0 TO 19 DO
        IF FC_IsPresetOccupied(x := x, y := y, iRule := 0) THEN n := n + 1; END_IF
    END_FOR END_FOR
    aResult[5] := (n = 49);
    n := 0;
    FOR x := 0 TO 19 DO FOR y := 0 TO 19 DO
        IF FC_IsPresetOccupied(x := x, y := y, iRule := 1) THEN n := n + 1; END_IF
    END_FOR END_FOR
    aResult[6] := (n = 231);
    n := 0;
    FOR x := 0 TO 19 DO FOR y := 0 TO 19 DO
        IF FC_IsPresetOccupied(x := x, y := y, iRule := 2) THEN n := n + 1; END_IF
    END_FOR END_FOR
    aResult[7] := (n = 134);

    // ---- T08-T10 行程时间双模型 + 路径长度(vx=2.0, vy=0.5 时的已知值) ----
    rV := FC_CalcTravelTime(x0 := 0, y0 := 0, x1 := 19, y1 := 19, xSimXY := TRUE);
    aResult[8] := ABS(rV - 38.0) < 0.001;                       // 切比雪夫 max(9.5, 38)
    rV := FC_CalcTravelTime(x0 := 0, y0 := 0, x1 := 19, y1 := 19, xSimXY := FALSE);
    aResult[9] := ABS(rV - 47.5) < 0.001;                       // 顺序 9.5+38
    aResult[10] := ABS(FC_CalcPathLen(x0 := 0, y0 := 0, x1 := 19, y1 := 19) - 38.0) < 0.001;

    // ---- 初始化仓库(rule=0),供可行性/选位用例使用 ----
    fbInit(xExecute := FALSE, iRule := 0);
    fbInit(xExecute := TRUE,  iRule := 0);

    // ---- T11-T16 可行性边界:正常/预占/超重/负重/超容/越界 ----
    aResult[11] :=      FC_CheckFeasible(x := 1,  y := 0,  rGoodW := 80.0, rGoodV := 0.5);
    aResult[12] := NOT  FC_CheckFeasible(x := 0,  y := 0,  rGoodW := 10.0, rGoodV := 0.5);  // (0,0)预占
    aResult[13] := NOT  FC_CheckFeasible(x := 1,  y := 10, rGoodW := 81.0, rGoodV := 0.5);  // cap=80
    aResult[14] := NOT  FC_CheckFeasible(x := 1,  y := 0,  rGoodW := -1.0, rGoodV := 0.5);
    aResult[15] := NOT  FC_CheckFeasible(x := 1,  y := 0,  rGoodW := 10.0, rGoodV := 1.2);
    aResult[16] := NOT  FC_CheckFeasible(x := 20, y := 0,  rGoodW := 10.0, rGoodV := 0.5);

    // ---- T17 超重货全库无可行位(>100kg 连底层都放不下) ----
    fbSel(iStrategy := 2, rGoodW := 150.0, rGoodF := 50.0, rGoodV := 0.5,
          rWMax := 150.0, rFMax := 100.0);
    aResult[17] := NOT fbSel.xFound;

    // ---- T18 满仓无可行位(边界#所有仓位已满) ----
    FOR x := 0 TO 19 DO FOR y := 0 TO 19 DO
        GVL_WH.aSlots[x, y].Occupied := TRUE;
    END_FOR END_FOR
    fbSel(iStrategy := 2, rGoodW := 10.0, rGoodF := 1.0, rGoodV := 0.5,
          rWMax := 10.0, rFMax := 1.0);
    aResult[18] := NOT fbSel.xFound;
    fbInit(xExecute := FALSE, iRule := 0);          // 恢复
    fbInit(xExecute := TRUE,  iRule := 0);

    // ---- T19 评分一致性向量(Python 导出,容差1e-3;见 07_GVL_Data_generated.st) ----
    iVecFail := 0;
    FOR i := 1 TO GVL_Data.N_TESTVEC DO
        rV := FC_CalcScore(rGoodW := GVL_Data.aTestVec[i].W,
                           rGoodF := GVL_Data.aTestVec[i].F,
                           x := GVL_Data.aTestVec[i].X, y := GVL_Data.aTestVec[i].Y,
                           rWMax := GVL_Data.aTestVec[i].WMax,
                           rFMax := GVL_Data.aTestVec[i].FMax);
        IF ABS(rV - GVL_Data.aTestVec[i].ExpScore) >= 0.001 THEN
            iVecFail := iVecFail + 1;
        END_IF
    END_FOR
    aResult[19] := (iVecFail = 0);

    // ---- T20 行程时间一致性向量(同上) ----
    iVecFail := 0;
    FOR i := 1 TO GVL_Data.N_TESTVEC DO
        rV := FC_CalcTravelTime(x0 := 0, y0 := 0,
                                x1 := GVL_Data.aTestVec[i].X, y1 := GVL_Data.aTestVec[i].Y,
                                xSimXY := TRUE);
        IF ABS(rV - GVL_Data.aTestVec[i].ExpTime) >= 0.001 THEN
            iVecFail := iVecFail + 1;
        END_IF
    END_FOR
    aResult[20] := (iVecFail = 0);

    // ---- T21 演示批次载入自检(件数与来源标记) ----
    GVL_WH.iGoodsCount := 0;
    FC_LoadDemoGoods();
    aResult[21] := (GVL_WH.iGoodsCount = GVL_Data.N_DEMO);

    // ---- T22 L1 加减速口径一致性向量(与 Python 梯形模型逐条比对) ----
    GVL_Param.xUseAccel := TRUE;
    iVecFail := 0;
    FOR i := 1 TO GVL_Data.N_TESTVEC DO
        rV := FC_CalcTravelTime(x0 := 0, y0 := 0,
                                x1 := GVL_Data.aTestVec[i].X, y1 := GVL_Data.aTestVec[i].Y,
                                xSimXY := TRUE);
        IF ABS(rV - GVL_Data.aTestVec[i].ExpTimeAccel) >= 0.001 THEN
            iVecFail := iVecFail + 1;
        END_IF
    END_FOR
    GVL_Param.xUseAccel := FALSE;               // 恢复默认口径
    aResult[22] := (iVecFail = 0);

    // ---- T23 双命令周期:已知值 + 不劣于单命令(C10) ----
    // 存(5,2) 取(10,5),匀速切比雪夫:t存=max(2.5,4)=4, t间=max(2.5,6)=6, t取=max(5,10)=10
    rV := FC_CalcDualCycleTime(iStoreX := 5, iStoreY := 2, iRetrX := 10, iRetrY := 5);
    aResult[23] := (ABS(rV - 20.0) < 0.001)
                   AND (rV <= 2.0 * 4.0 + 2.0 * 10.0 + 0.001);

    // ---- 汇总 ----
    FOR i := 1 TO N_CASES DO
        IF aResult[i] THEN iPassed := iPassed + 1;
        ELSE
            iFailed := iFailed + 1;
            sLastFail := CONCAT('T', INT_TO_STRING(i));
        END_IF
    END_FOR
    xAllPass := (iFailed = 0);
END_IF
END_PROGRAM
