(* ============================================================
   06_PRG_Test.st — 边界与一致性测试程序
   导入方法:POU 类型"程序",可挂到同一任务或手动调用;
   置 xRunTests:=TRUE 单次运行,看 iPassed/iFailed/aResult。
   覆盖:资料包 §7.3 边界判断清单 + Python↔ST 评分一致性向量 + B1 官方口径(T24)
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
    N_CASES   : INT := 41;                  // 用例总数(0707 +T41 FB_GoodsInput 封装)
    aResult   : ARRAY[1..45] OF BOOL;       // 各用例结果(TRUE=通过;预留至45)
    sLastFail : STRING[64];                 // 最后失败的用例名(排错入口)
    fbInit    : FB_InitWarehouse;
    fbSel     : FB_SelectSlot;
    fbAssign  : FB_AssignAllGoods;          // T25 端到端:AWRA 分配状态机
    fbImprove : FB_LocalSwapImprove;        // T25 端到端:局部搜索状态机
    fbStats   : FB_Stats;                   // T25 端到端:终局统计
    fbGoodsInputT : FB_GoodsInput;          // T41:货物输入封装测试
    i, x, y, n : INT;
    rV        : REAL;
    iVecFail  : INT;
    iAwraPosDiff : INT;                     // T25 逐位分歧计数(信息性;0=终局布局与 sim 逐位一致)
END_VAR

IF xRunTests THEN
    xRunTests := FALSE;
    iPassed := 0;  iFailed := 0;  sLastFail := '';
    FOR i := 1 TO 45 DO aResult[i] := TRUE; END_FOR

    // ---- T01-T04 承重系数:正常/顶层/负钳位/越上钳位 ----
    aResult[1] := ABS(FC_CapCoef(y := 0)  - 1.0)  < 0.0001;
    aResult[2] := ABS(FC_CapCoef(y := 19) - 0.62) < 0.0001;
    aResult[3] := ABS(FC_CapCoef(y := -5) - 1.0)  < 0.0001;
    aResult[4] := ABS(FC_CapCoef(y := 25) - 0.62) < 0.0001;

    // ---- T05-T07 预占用历史三解读格数(49/231/134;官方口径 sum 见 T24) ----
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

    // ---- T24 B1 官方口径(2026-07-06 答复):x+y 之和被3整除 = 133 格 ----
    // 官方原话"x+y 和能被3整除";含 (0,0) 格,呈对角条纹;与 Python 侧
    // test_preoccupied_counts 的 sum=133 断言同口径(双实现同步铁律)
    n := 0;
    FOR x := 0 TO 19 DO FOR y := 0 TO 19 DO
        IF FC_IsPresetOccupied(x := x, y := y, iRule := 3) THEN n := n + 1; END_IF
    END_FOR END_FOR
    aResult[24] := (n = 133);

    // ---- T25 AWRA-LS 全流程终局一致性(端到端护栏;0707,sim/consistency_probe 离线证明可绿) ----
    // 驱动 Rank+Assign+LS 分片状态机跑到 xDone(WHILE 内推进,测试不计实时性),
    // 比对终局:①聚合统计容差(主判据,对单双精度局部最优鲁棒,同 T19/T20 哲学)
    //          ②终局布局逐位(信息性 iAwraPosDiff;G1/G2 零触发时应为 0,见 gap 表)
    // 向量源:07_GVL_Data_generated.st 的 aAwraExpect / AWRA_EXPT/ENERGY/COG(sum 官方口径,匀速)
    GVL_Param.xUseAccel := FALSE;                    // 与 export 同口径(匀速)
    GVL_WH.iGoodsCount := 0;
    fbInit(xExecute := FALSE, iRule := 3);
    fbInit(xExecute := TRUE,  iRule := 3);           // sum 官方口径(133 预占)
    FC_LoadDemoGoods();                              // 20 件 seed2026,与 sim 同源
    // -- 驱动 AWRA 分配(xUseRank=TRUE 排序模式,score 策略=2) --
    fbAssign(xStart := FALSE, xUseRank := TRUE, iStrategy := 2);
    fbAssign(xStart := TRUE,  xUseRank := TRUE, iStrategy := 2);
    n := 0;
    WHILE fbAssign.xBusy AND (n < 100000) DO
        fbAssign(xStart := TRUE, xUseRank := TRUE, iStrategy := 2);
        n := n + 1;
    END_WHILE
    // -- 驱动局部搜索到收敛 --
    fbImprove(xStart := FALSE);
    fbImprove(xStart := TRUE);
    n := 0;
    WHILE fbImprove.xBusy AND (n < 1000000) DO
        fbImprove(xStart := TRUE);
        n := n + 1;
    END_WHILE
    // -- 终局统计 --
    fbStats(xExecute := FALSE);
    fbStats(xExecute := TRUE);
    // -- 逐位信息性检查(aGoods 索引==Id,见 FC_LoadDemoGoods) --
    iAwraPosDiff := 0;
    FOR i := 1 TO GVL_Data.N_AWRA DO
        IF (GVL_WH.aGoods[GVL_Data.aAwraExpect[i].Id].X <> GVL_Data.aAwraExpect[i].X)
        OR (GVL_WH.aGoods[GVL_Data.aAwraExpect[i].Id].Y <> GVL_Data.aAwraExpect[i].Y) THEN
            iAwraPosDiff := iAwraPosDiff + 1;
        END_IF
    END_FOR
    // -- 主判据:逐位一致(演示批 consistency_probe 证 G1/G2 零触发,故逐位可作主判据)
    //    + 聚合容差 + 计数精确 + 违规0(多重护栏) --
    aResult[25] := (iAwraPosDiff = 0)
       AND (GVL_WH.stStats.PlacedCnt = GVL_Data.AWRA_PLACED)
       AND (GVL_WH.stStats.FailedCnt = GVL_Data.AWRA_FAILED)
       AND (ABS(GVL_WH.stStats.ExpRetrieval - GVL_Data.AWRA_EXPT) < 0.001)
       AND (ABS(GVL_WH.stStats.Energy      - GVL_Data.AWRA_ENERGY) < 0.01)
       AND (ABS(GVL_WH.stStats.CogHeight   - GVL_Data.AWRA_COG) < 0.001)
       AND (GVL_WH.stStats.ViolCnt = 0);

    // ---- T26-T35 边界判断扩充(0707,评分细则5"边界判断充分";纯函数断言,手算期望) ----
    // 重置干净仓库(T25 跑满;and 口径 rule0 供边界测试,MaxWeight[y]=CapCoef(y)*100)
    GVL_WH.iGoodsCount := 0;
    fbInit(xExecute := FALSE, iRule := 0);
    fbInit(xExecute := TRUE,  iRule := 0);
    GVL_Param.xUseAccel := FALSE;
    // T26-T27 坐标越界(FC_CheckFeasible 显式范围检查,先于数组访问,不靠 CheckBounds 钳位)
    aResult[26] := NOT FC_CheckFeasible(x := -1, y := 0,  rGoodW := 10.0, rGoodV := 0.5);  // 负列
    aResult[27] := NOT FC_CheckFeasible(x := 0,  y := 20, rGoodW := 10.0, rGoodV := 0.5);  // 越层(y>19)
    // T28-T29 负属性(显式拒绝)
    aResult[28] := NOT FC_CheckFeasible(x := 5, y := 0, rGoodW := -1.0, rGoodV := 0.5);    // 负重
    aResult[29] := NOT FC_CheckFeasible(x := 5, y := 0, rGoodW := 10.0, rGoodV := -0.1);   // 负容
    // T30-T31 承重边界(y=10 限重80/y=19 限重62;留 0.1 间隙避单精度噪声)
    aResult[30] :=     FC_CheckFeasible(x := 1, y := 10, rGoodW := 79.9, rGoodV := 0.5)
               AND NOT FC_CheckFeasible(x := 1, y := 10, rGoodW := 80.1, rGoodV := 0.5);
    aResult[31] :=     FC_CheckFeasible(x := 1, y := 19, rGoodW := 61.9, rGoodV := 0.5)
               AND NOT FC_CheckFeasible(x := 1, y := 19, rGoodW := 62.1, rGoodV := 0.5);
    // T32 容积边界(CELL_VOL=1.0)
    aResult[32] :=     FC_CheckFeasible(x := 1, y := 0, rGoodW := 10.0, rGoodV := 0.99)
               AND NOT FC_CheckFeasible(x := 1, y := 0, rGoodW := 10.0, rGoodV := 1.01);
    // T33-T34 归一分母为0保护(不除零崩溃,返回有限非负;枪I:REAL除零=INF/NaN 依系统)
    rV := FC_CalcScore(rGoodW := 10.0, rGoodF := 5.0, x := 1, y := 0, rWMax := 0.0, rFMax := 0.0);
    // 归一保护后 rFMax→1、F=5>1 使 fNorm=5、resv=(1-5)*.. 为负,score 可负——本用例只验
    // "除零保护生效=返回有限值不崩"(NaN 令两比较皆 FALSE、INF 令 <1E6 FALSE,故此区间≡有限数)
    aResult[33] := (rV > -1.0E6) AND (rV < 1.0E6);
    rV := FC_CalcPriority(rGoodF := 5.0, rGoodW := 10.0, rGoodV := 0.5,
                          rFMax := 0.0, rWMax := 0.0, rVMax := 0.0);
    aResult[34] := (rV >= 0.0) AND (rV < 100.0);
    // T35 优先级单调性(同重同体积,高频→优先级更高;Rank 阶段正确性)
    aResult[35] := FC_CalcPriority(rGoodF := 100.0, rGoodW := 10.0, rGoodV := 0.5,
                                   rFMax := 100.0, rWMax := 100.0, rVMax := 1.0)
                 > FC_CalcPriority(rGoodF := 1.0, rGoodW := 10.0, rGoodV := 0.5,
                                   rFMax := 100.0, rWMax := 100.0, rVMax := 1.0);

    // ---- T36-T40 选位策略边界(0707;FB_SelectSlot 各策略正确性;仓库=上面 rule0 干净态) ----
    // T36 seq 策略:首个可行位((0,0)预占 → 扫描到 (0,1))
    fbSel(iStrategy := 0, rGoodW := 10.0, rGoodF := 5.0, rGoodV := 0.5, rWMax := 10.0, rFMax := 5.0);
    aResult[36] := fbSel.xFound AND (fbSel.iBestX = 0) AND (fbSel.iBestY = 1);
    // T37 near 策略:行程时间最小可行位((1,0) travel=max(0.5,0)=0.5 全库最小)
    fbSel(iStrategy := 1, rGoodW := 10.0, rGoodF := 5.0, rGoodV := 0.5, rWMax := 10.0, rFMax := 5.0);
    aResult[37] := fbSel.xFound AND (fbSel.iBestX = 1) AND (fbSel.iBestY = 0);
    // T38 score 策略:有解(多目标评分选位)
    fbSel(iStrategy := 2, rGoodW := 10.0, rGoodF := 5.0, rGoodV := 0.5, rWMax := 10.0, rFMax := 5.0);
    aResult[38] := fbSel.xFound;
    // T39 中重货 90kg 只能进低层(限重≥90 → 层 y≤5),仍有解
    fbSel(iStrategy := 1, rGoodW := 90.0, rGoodF := 5.0, rGoodV := 0.5, rWMax := 90.0, rFMax := 5.0);
    aResult[39] := fbSel.xFound AND (fbSel.iBestY <= 5);
    // T40 FB_SelectSlot 无副作用:同输入重复调用结果一致(纯功能,只读仓库)
    fbSel(iStrategy := 2, rGoodW := 25.0, rGoodF := 8.0, rGoodV := 0.5, rWMax := 25.0, rFMax := 8.0);
    x := fbSel.iBestX;  y := fbSel.iBestY;
    fbSel(iStrategy := 2, rGoodW := 25.0, rGoodF := 8.0, rGoodV := 0.5, rWMax := 25.0, rFMax := 8.0);
    aResult[40] := (fbSel.iBestX = x) AND (fbSel.iBestY = y);

    // ---- T41 FB_GoodsInput 封装(评分细则6/7;0707 T2.2 抽取):正常/负输入/超重无位 三分支 ----
    GVL_WH.iGoodsCount := 0;
    fbInit(xExecute := FALSE, iRule := 0);
    fbInit(xExecute := TRUE,  iRule := 0);
    // (a) 正常轻货 → xOk & xFound & 入表(count=1)
    fbGoodsInputT(xAdd := FALSE, iId := 1, sName := 'A', rWeight := 10.0, rFreq := 5.0, rVolume := 0.5);
    fbGoodsInputT(xAdd := TRUE,  iId := 1, sName := 'A', rWeight := 10.0, rFreq := 5.0, rVolume := 0.5);
    aResult[41] := fbGoodsInputT.xOk AND fbGoodsInputT.xFound AND (GVL_WH.iGoodsCount = 1);
    // (b) 负输入 → 拒收 iErrId=2,不入表(count 仍 1;新上升沿=先落再起)
    fbGoodsInputT(xAdd := FALSE, iId := 2, sName := 'B', rWeight := -1.0, rFreq := 5.0, rVolume := 0.5);
    fbGoodsInputT(xAdd := TRUE,  iId := 2, sName := 'B', rWeight := -1.0, rFreq := 5.0, rVolume := 0.5);
    aResult[41] := aResult[41] AND (NOT fbGoodsInputT.xOk) AND (fbGoodsInputT.iErrId = 2)
                   AND (GVL_WH.iGoodsCount = 1);
    // (c) 超重货 150kg → 入表但无可行位 iErrId=3、xFound=FALSE(新上升沿)
    fbGoodsInputT(xAdd := FALSE, iId := 3, sName := 'C', rWeight := 150.0, rFreq := 5.0, rVolume := 0.5);
    fbGoodsInputT(xAdd := TRUE,  iId := 3, sName := 'C', rWeight := 150.0, rFreq := 5.0, rVolume := 0.5);
    aResult[41] := aResult[41] AND fbGoodsInputT.xOk AND (NOT fbGoodsInputT.xFound)
                   AND (fbGoodsInputT.iErrId = 3);

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
