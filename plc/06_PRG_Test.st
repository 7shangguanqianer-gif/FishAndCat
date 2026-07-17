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
VAR CONSTANT
    N_CASES   : INT := 77;                  // 用例总数(0717 治理D 扩容 T77 FC_TMax 口径;常量化=N4-08,在线不可改)
END_VAR
VAR
    xRunTests : BOOL;                       // 置 TRUE 触发(自动复位)
    iPassed   : INT;
    iFailed   : INT;
    xAllPass  : BOOL;
    aResult   : ARRAY[1..77] OF BOOL;       // 各用例结果(TRUE=通过;上界与 N_CASES 同步维护)
    sLastFail : STRING[64];                 // 最后失败的用例名(排错入口)
    fbInit    : FB_InitWarehouse;
    fbSel     : FB_SelectSlot;
    fbAssign  : FB_AssignAllGoods;          // T25 端到端:AWRA 分配状态机
    fbImprove : FB_LocalSwapImprove;        // T25 端到端:局部搜索状态机
    fbStats   : FB_Stats;                   // T25 端到端:终局统计
    fbGoodsInputT : FB_GoodsInput;          // T41:货物输入封装测试
    fbQueryT  : FB_QueryGood;               // T42:单件查询测试(块3)
    fbRetrT   : FB_RetrieveGood;            // T76:取出演示测试(E7,0716;xInstant 直通)
    fbRecPageT : FB_RecordPage;             // T43:记录页窗口测试(块3)
    fbDetT    : FB_SceneDetect;             // T49-T53:场景检测器测试(A2,0711)
    fbCT      : FB_AssignClassTurnover;     // T63-T65:CB/TOB 批量分配测试(0712 轨B)
    fbAuthT   : FB_UserAuth;                // T54:两级权限测试(A4,0711)
    fbGuardT  : FB_ParamGuard;              // T55:调参守卫测试(A4,0711)
    fbVisuT   : FB_VisuRefresh;             // T59:层高亮/层计数测试(C1,0711)
    iRet      : INT;                        // T56:FC_MaintToggle 返回码
    dwBefore  : DWORD;                      // T59:高亮前色值(相对锚)
    i, x, y, n : INT;
    rV        : REAL;
    iVecFail  : INT;
    iAwraPosDiff : INT;                     // T25 逐位分歧计数(信息性;0=终局布局与 sim 逐位一致)
    iCtPosDiff   : INT;                     // T68/T69 CB/TOB 逐位分歧计数(0712 轨B)
END_VAR

IF xRunTests THEN
    xRunTests := FALSE;
    iPassed := 0;  iFailed := 0;  sLastFail := '';
    FOR i := 1 TO N_CASES DO aResult[i] := TRUE; END_FOR   // R6:全量初始化,防漏写新测试继承旧值

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

    // ---- T42-T45 块3 画面服务(0708;前置=T41 留下的表:aGoods[1]=Id1轻货/aGoods[2]=Id3超重,count=2) ----
    GVL_Param.xUseAccel := FALSE;           // 测试自给自足:显式匀速口径(防前序用例遗留开关)
    GVL_Param.xSimultaneousXY := TRUE;      // 同上:显式切比雪夫主口径(T42 拟真锚 7.5s 依赖)

    // T42 FB_QueryGood:未分配/已分配+高亮+拟真字段/未找到清旧高亮/非正Id 四分支
    // (a) 未分配货:找得到,属性对,位置=-1
    fbQueryT(xQuery := FALSE, iId := 1);
    fbQueryT(xQuery := TRUE,  iId := 1);
    aResult[42] := GVL_Visu.QryFound AND (ABS(GVL_Visu.QryWeight - 10.0) < 0.001)
                   AND (GVL_Visu.QryX = -1);
    // (b) 手工落位 (2,3) 再查:位置/路径/高亮/拟真对照全齐
    //     手算锚:laden(0,0→2,3)=MAX(2/2, 3/(0.5×0.8))=MAX(1.0,7.5)=7.5s;10kg→轻档 6.0s
    GVL_WH.aGoods[1].Assigned := TRUE;
    GVL_WH.aGoods[1].X := 2;   GVL_WH.aGoods[1].Y := 3;
    GVL_WH.aGoods[1].PathLength := 5.0;  GVL_WH.aGoods[1].ExecTime := 6.0;
    fbQueryT(xQuery := FALSE, iId := 1);
    fbQueryT(xQuery := TRUE,  iId := 1);
    aResult[42] := aResult[42] AND GVL_Visu.QryFound
                   AND (GVL_Visu.QryX = 2) AND (GVL_Visu.QryY = 3)
                   AND (ABS(GVL_Visu.QryPathLen - 5.0) < 0.001)
                   AND (GVL_Visu.VisuSlotState[2, 3] = 6)
                   AND (ABS(GVL_Visu.QryTravelLaden - 7.5) < 0.001)
                   AND (ABS(GVL_Visu.QryHandleT - 6.0) < 0.001);
    // (c) 查不存在 Id:Found=FALSE 且旧青色高亮恢复为已占用 2
    fbQueryT(xQuery := FALSE, iId := 999);
    fbQueryT(xQuery := TRUE,  iId := 999);
    aResult[42] := aResult[42] AND (NOT GVL_Visu.QryFound)
                   AND (GVL_Visu.VisuSlotState[2, 3] = 2);
    // (d) 非正 Id:直接未找到(边界)
    fbQueryT(xQuery := FALSE, iId := -1);
    fbQueryT(xQuery := TRUE,  iId := -1);
    aResult[42] := aResult[42] AND (NOT GVL_Visu.QryFound);

    // T43 FB_RecordPage:窗口映射/空行约定/小表钳位/大表翻页钳位
    // (a) 2 件小表:顶行=1,行0=Id1(已落位 X=2),行1=Id3(未分配 X=-1),行2=空(Id=0)
    fbRecPageT(xPageUp := FALSE, xPageDown := FALSE);
    aResult[43] := (GVL_Visu.iRecTop = 1) AND (GVL_Visu.aRowId[0] = 1)
                   AND (GVL_Visu.aRowX[0] = 2) AND (GVL_Visu.aRowId[1] = 3)
                   AND (GVL_Visu.aRowX[1] = -1) AND (GVL_Visu.aRowId[2] = 0)
                   AND (GVL_Visu.iRecTotal = 2);
    // (b) 小表下翻:钳位拉回 1(2 件表无第二页)
    fbRecPageT(xPageUp := FALSE, xPageDown := TRUE);
    aResult[43] := aResult[43] AND (GVL_Visu.iRecTop = 1);
    // (c) 造 25 件大表验证翻页链:1→11→16(25-9 钳位)→6(上翻);毕恢复 count=2
    GVL_WH.iGoodsCount := 25;
    fbRecPageT(xPageUp := FALSE, xPageDown := FALSE);   // 沿复位
    fbRecPageT(xPageUp := FALSE, xPageDown := TRUE);
    aResult[43] := aResult[43] AND (GVL_Visu.iRecTop = 11);
    fbRecPageT(xPageUp := FALSE, xPageDown := FALSE);
    fbRecPageT(xPageUp := FALSE, xPageDown := TRUE);
    aResult[43] := aResult[43] AND (GVL_Visu.iRecTop = 16);
    fbRecPageT(xPageUp := FALSE, xPageDown := FALSE);
    fbRecPageT(xPageUp := TRUE,  xPageDown := FALSE);
    aResult[43] := aResult[43] AND (GVL_Visu.iRecTop = 6);
    GVL_WH.iGoodsCount := 2;

    // T44 FC_HandleTime 三档边界(0.1 间隙避单精度,块2 惯例):29.9轻/30.1中/60.0中含/60.1重
    aResult[44] := (ABS(FC_HandleTime(rW := 29.9) - 6.0)  < 0.001)
                   AND (ABS(FC_HandleTime(rW := 30.1) - 8.5)  < 0.001)
                   AND (ABS(FC_HandleTime(rW := 60.0) - 8.5)  < 0.001)
                   AND (ABS(FC_HandleTime(rW := 60.1) - 12.5) < 0.001);

    // T45 FC_TravelLaden:垂直折减/水平不折减/顺序分支/非法系数保护
    // 手算锚(匀速):laden(0,0→10,10)切比雪夫=MAX(10/2, 10/0.4)=25.0(空载同点=20.0)
    aResult[45] := (ABS(FC_TravelLaden(x0:=0, y0:=0, x1:=10, y1:=10, xSimXY:=TRUE) - 25.0) < 0.001)
                   AND (ABS(FC_CalcTravelTime(x0:=0, y0:=0, x1:=10, y1:=10, xSimXY:=TRUE) - 20.0) < 0.001);
    // 水平纯移动:折减只作用垂直 → 与空载同值 5.0
    aResult[45] := aResult[45]
                   AND (ABS(FC_TravelLaden(x0:=0, y0:=0, x1:=10, y1:=0, xSimXY:=TRUE) - 5.0) < 0.001);
    // 顺序模型分支:5+25=30.0
    aResult[45] := aResult[45]
                   AND (ABS(FC_TravelLaden(x0:=0, y0:=0, x1:=10, y1:=10, xSimXY:=FALSE) - 30.0) < 0.001);
    // 非法折减系数保护:0.0 → 不折减(=空载 20.0);毕恢复默认 0.80
    GVL_Param.rLadenFactorVY := 0.0;
    aResult[45] := aResult[45]
                   AND (ABS(FC_TravelLaden(x0:=0, y0:=0, x1:=10, y1:=10, xSimXY:=TRUE) - 20.0) < 0.001);
    GVL_Param.rLadenFactorVY := 0.80;

    // ============ 0711 A2-A4:T46-T56(检修挂起/场景检测器/两级权限) ============

    // ---- T46-T48 检修挂起(A3,putaway block 语义;干净仓:sum 口径 133 预占) ----
    fbInit(xExecute := FALSE, iRule := 3);
    fbInit(xExecute := TRUE,  iRule := 3);
    // T46 挂起→选位不可行;恢复→立即回池(挂起/恢复双向)
    GVL_WH.aMaintBlock[1, 0] := TRUE;
    aResult[46] := NOT FC_CheckFeasible(x := 1, y := 0, rGoodW := 10.0, rGoodV := 0.5);
    GVL_WH.aMaintBlock[1, 0] := FALSE;
    aResult[46] := aResult[46]
                   AND FC_CheckFeasible(x := 1, y := 0, rGoodW := 10.0, rGoodV := 0.5);
    // T47 集成:near 轻货首选 (1,0)(t=0.5s);挂起后绕行次优 (2,0)(t=1.0s);恢复后回 (1,0)
    GVL_WH.aMaintBlock[1, 0] := TRUE;
    fbSel(iStrategy := 1, rGoodW := 10.0, rGoodF := 50.0, rGoodV := 0.5,
          rWMax := 100.0, rFMax := 100.0);
    aResult[47] := fbSel.xFound AND (fbSel.iBestX = 2) AND (fbSel.iBestY = 0);
    GVL_WH.aMaintBlock[1, 0] := FALSE;
    fbSel(iStrategy := 1, rGoodW := 10.0, rGoodF := 50.0, rGoodV := 0.5,
          rWMax := 100.0, rFMax := 100.0);
    aResult[47] := aResult[47] AND fbSel.xFound AND (fbSel.iBestX = 1) AND (fbSel.iBestY = 0);
    // T48 交换目标位检修=禁入(FC_FitsPhysical;检修位存量可换走、新货不得换进)
    GVL_WH.aMaintBlock[2, 0] := TRUE;
    aResult[48] := NOT FC_FitsPhysical(x := 2, y := 0, rGoodW := 10.0, rGoodV := 0.5);
    GVL_WH.aMaintBlock[2, 0] := FALSE;
    aResult[48] := aResult[48]
                   AND FC_FitsPhysical(x := 2, y := 0, rGoodW := 10.0, rGoodV := 0.5);

    // ---- T49-T53 场景检测器(A2;画像手算锚+推荐分支全覆盖) ----
    // 5 件手工批:freq 10/20/30/40/100(和=200),w 10/20/30/70/80 → n=5;
    // density=5/267=0.018727;top=MAX(1,5/5)=1 件 → skew=100/200=0.5;
    // w_mean=210/5=42.0;w_heavy(>60kg)=2/5=0.4
    FOR i := 1 TO 5 DO
        GVL_WH.aGoods[i].Id := i;  GVL_WH.aGoods[i].Volume := 0.5;
        GVL_WH.aGoods[i].Assigned := FALSE;
    END_FOR
    GVL_WH.aGoods[1].Freq := 10.0;   GVL_WH.aGoods[1].Weight := 10.0;
    GVL_WH.aGoods[2].Freq := 20.0;   GVL_WH.aGoods[2].Weight := 20.0;
    GVL_WH.aGoods[3].Freq := 30.0;   GVL_WH.aGoods[3].Weight := 30.0;
    GVL_WH.aGoods[4].Freq := 40.0;   GVL_WH.aGoods[4].Weight := 70.0;
    GVL_WH.aGoods[5].Freq := 100.0;  GVL_WH.aGoods[5].Weight := 80.0;
    GVL_WH.iGoodsCount := 5;
    FOR i := 1 TO 10 DO fbDetT(xForce := FALSE); IF fbDetT.xValid THEN EXIT; END_IF END_FOR
    // T49 画像位级(容差 1e-3,块2 一致性惯例)
    aResult[49] := fbDetT.xValid
                   AND (GVL_Visu.VisuProfN = 5)
                   AND (ABS(GVL_Visu.VisuProfDensity - 0.018727) < 0.001)
                   AND (ABS(GVL_Visu.VisuProfSkew - 0.5) < 0.001)
                   AND (ABS(GVL_Visu.VisuProfWMean - 42.0) < 0.001)
                   AND (ABS(GVL_Visu.VisuProfWHeavy - 0.4) < 0.001);
    // T50 批量推荐:skew 0.5>=0.35 → AWRA(holistic 全要素档)
    aResult[50] := (fbDetT.iRecBatch = 3);
    // T51 在线推荐:n=5<=20 → near(F18-2 极小批降级)
    aResult[51] := (fbDetT.iRecOnline = 1);
    // T52 均匀批(freq 全 50→skew=0.2<0.35 且 n<=20):批量/在线均 near;xForce 重算路径
    FOR i := 1 TO 5 DO GVL_WH.aGoods[i].Freq := 50.0; END_FOR
    fbDetT(xForce := FALSE);
    FOR i := 1 TO 10 DO fbDetT(xForce := TRUE); IF fbDetT.xValid THEN EXIT; END_IF END_FOR
    aResult[52] := fbDetT.xValid AND (fbDetT.iRecBatch = 1) AND (fbDetT.iRecOnline = 1)
                   AND (ABS(GVL_Visu.VisuProfSkew - 0.2) < 0.001);
    // T53 大批高偏(n=21>20,skew=(100+10*3)/300=0.4333>=0.35):批量 AWRA/在线 score
    FOR i := 1 TO 20 DO
        GVL_WH.aGoods[i].Id := i;      GVL_WH.aGoods[i].Freq := 10.0;
        GVL_WH.aGoods[i].Weight := 50.0;  GVL_WH.aGoods[i].Volume := 0.5;
    END_FOR
    GVL_WH.aGoods[21].Id := 21;  GVL_WH.aGoods[21].Freq := 100.0;
    GVL_WH.aGoods[21].Weight := 50.0;  GVL_WH.aGoods[21].Volume := 0.5;
    GVL_WH.iGoodsCount := 21;
    FOR i := 1 TO 10 DO fbDetT(xForce := FALSE); IF fbDetT.xValid THEN EXIT; END_IF END_FOR
    aResult[53] := fbDetT.xValid AND (fbDetT.iRecBatch = 3) AND (fbDetT.iRecOnline = 2)
                   AND (ABS(GVL_Visu.VisuProfSkew - 0.43333) < 0.001);
    GVL_WH.iGoodsCount := 2;                        // 对齐 T43 尾惯例,防状态外溢

    // ---- T54-T55 两级权限(A4:登录三段 + 守卫回滚) ----
    // T54 错码拒登(计数+1)→ 对码升管理员 → 登出回操作员
    fbAuthT(xLogin := FALSE, iPin := 0, xLogout := FALSE);
    fbAuthT(xLogin := TRUE,  iPin := 1111, xLogout := FALSE);
    aResult[54] := (fbAuthT.iLevel = 0) AND (fbAuthT.iFailCnt = 1);
    fbAuthT(xLogin := FALSE, iPin := 0, xLogout := FALSE);
    fbAuthT(xLogin := TRUE,  iPin := GVL_Param.ADMIN_PIN, xLogout := FALSE);
    aResult[54] := aResult[54] AND (fbAuthT.iLevel = 1);
    fbAuthT(xLogin := FALSE, iPin := 0, xLogout := TRUE);
    aResult[54] := aResult[54] AND (fbAuthT.iLevel = 0);
    // T55 守卫:管理员改参被保持;操作员级越权改动一周期内回滚
    fbGuardT(iLevel := 1);                          // 首 call:快照=现值(0.15)
    GVL_Param.rDelta := 0.99;                       // 管理员改参
    fbGuardT(iLevel := 1);                          // 快照刷新=0.99
    fbGuardT(iLevel := 0);                          // 降级:合法值保持
    aResult[55] := (ABS(GVL_Param.rDelta - 0.99) < 0.001);
    GVL_Param.rDelta := 0.5;                        // 操作员越权改
    fbGuardT(iLevel := 0);                          // 守卫回滚到 0.99
    aResult[55] := aResult[55] AND (ABS(GVL_Param.rDelta - 0.99) < 0.001);
    GVL_Param.rDelta := 0.15;                       // 恢复默认并刷快照(防外溢)
    fbGuardT(iLevel := 1);

    // ---- T56 检修权限门(FC_MaintToggle 四分支:需管理员/挂起/恢复/越界) ----
    n := GVL_Visu.VisuMaintCount;                   // 相对基准(在线演示可能已有检修格)
    iRet := FC_MaintToggle(x := 5, y := 5, iLevel := 0);
    aResult[56] := (iRet = 2) AND NOT GVL_WH.aMaintBlock[5, 5];
    iRet := FC_MaintToggle(x := 5, y := 5, iLevel := 1);
    aResult[56] := aResult[56] AND (iRet = 0) AND GVL_WH.aMaintBlock[5, 5]
                   AND (GVL_Visu.VisuMaintCount = n + 1);
    iRet := FC_MaintToggle(x := 5, y := 5, iLevel := 1);
    aResult[56] := aResult[56] AND (iRet = 1) AND NOT GVL_WH.aMaintBlock[5, 5]
                   AND (GVL_Visu.VisuMaintCount = n);
    iRet := FC_MaintToggle(x := -1, y := 0, iLevel := 1);
    aResult[56] := aResult[56] AND (iRet = 3);

    // ============ 0711 C1/C2/C6:T57-T59(热力色阶/仓位履历/层高亮) ============

    // ---- T57 FC_HeatColor 三段端点 + 防除 + FC_BlendLight 黑白极值(手算锚) ----
    aResult[57] := (FC_HeatColor(rVal := 0.0,   rMax := 100.0) = DWORD#16#FF1565C0)
               AND (FC_HeatColor(rVal := 50.0,  rMax := 100.0) = DWORD#16#FFFFD600)
               AND (FC_HeatColor(rVal := 100.0, rMax := 100.0) = DWORD#16#FFE53935)
               AND (FC_HeatColor(rVal := 5.0,   rMax := 0.0)   = DWORD#16#FF1565C0)
               AND (FC_BlendLight(dw := DWORD#16#FF000000) = DWORD#16#FF737373)
               AND (FC_BlendLight(dw := DWORD#16#FFFFFFFF) = DWORD#16#FFFFFFFF);

    // ---- T58 aSlotOps 履历 + aSlotFreq 布局态(小批端到端:2 件 score 落位) ----
    fbInit(xExecute := FALSE, iRule := 3);
    fbInit(xExecute := TRUE,  iRule := 3);              // aSlotFreq 随批清;aSlotOps 履历保留
    aResult[58] := (ABS(GVL_WH.aSlotFreq[10, 10]) < 0.0001);   // init 后布局态干净
    GVL_WH.aGoods[1].Id := 1;  GVL_WH.aGoods[1].Weight := 10.0;
    GVL_WH.aGoods[1].Freq := 5.0;  GVL_WH.aGoods[1].Volume := 0.5;
    GVL_WH.aGoods[1].Assigned := FALSE;
    GVL_WH.aGoods[2].Id := 2;  GVL_WH.aGoods[2].Weight := 20.0;
    GVL_WH.aGoods[2].Freq := 3.0;  GVL_WH.aGoods[2].Volume := 0.5;
    GVL_WH.aGoods[2].Assigned := FALSE;
    GVL_WH.iGoodsCount := 2;
    fbAssign(xStart := FALSE, xUseRank := FALSE, iStrategy := 2);
    fbAssign(xStart := TRUE,  xUseRank := FALSE, iStrategy := 2);
    n := 0;
    WHILE fbAssign.xBusy AND (n < 100000) DO
        fbAssign(xStart := TRUE, xUseRank := FALSE, iStrategy := 2);
        n := n + 1;
    END_WHILE
    // R8:先判两件 Assigned 再做坐标索引(IEC AND 不短路,失败路径 X=-1 会越界读)
    IF GVL_WH.aGoods[1].Assigned AND GVL_WH.aGoods[2].Assigned THEN
        aResult[58] := aResult[58]
               AND (ABS(GVL_WH.aSlotFreq[GVL_WH.aGoods[1].X, GVL_WH.aGoods[1].Y] - 5.0) < 0.0001)
               AND (GVL_WH.aSlotOps[GVL_WH.aGoods[1].X, GVL_WH.aGoods[1].Y] >= 1)
               AND (GVL_WH.aSlotOps[GVL_WH.aGoods[2].X, GVL_WH.aGoods[2].Y] >= 1);
    ELSE
        aResult[58] := FALSE;
    END_IF

    // ---- T59 层高亮集成:计数正确 + 高亮色=FC_BlendLight(原色)(相对锚,免猜状态色) ----
    // R8:T58 失败路径(X=-1)防御——未分配则直接判红,不做坐标索引
    IF NOT GVL_WH.aGoods[1].Assigned THEN
        aResult[59] := FALSE;
    ELSE
    GVL_Visu.InTierSel := -1;
    fbVisuT();                                          // 无高亮基准帧
    x := GVL_WH.aGoods[1].X;  y := GVL_WH.aGoods[1].Y;
    dwBefore := GVL_Visu.VisuSlotColor[x, GVL_Param.TIERS - 1 - y];
    aResult[59] := (GVL_Visu.VisuTierOcc = 0);
    GVL_Visu.InTierSel := y;
    fbVisuT();                                          // 高亮该层
    aResult[59] := aResult[59] AND (GVL_Visu.VisuTierOcc >= 1)
               AND (GVL_Visu.VisuSlotColor[x, GVL_Param.TIERS - 1 - y]
                    = FC_BlendLight(dw := dwBefore));
    GVL_Visu.InTierSel := -1;                           // 恢复,防外溢
    GVL_WH.iGoodsCount := 2;
    END_IF                                              // R8:T59 防御分支收口

    // ============ 0712 轨B:T60-T75(平局统一/容量护栏/CB-TOB/隐患清扫;逐阶段实现) ============

    // ---- T60 near 平局全序=(时间,层,列)=Python(N5-01 统一):等时对(0,1)vs(4,0)须选(4,0) ----
    //      travel(0,1)=max(0, 1*CELL_H/rVy)=2.0 = travel(4,0)=max(4*CELL_W/rVx, 0)=2.0
    //      (默认参数 1.0/2.0/0.5;两值均为精确二进制数,REAL 相等判定安全)
    fbInit(xExecute := FALSE, iRule := 3);
    fbInit(xExecute := TRUE,  iRule := 3);
    FOR x := 0 TO GVL_Param.COLS - 1 DO
        FOR y := 0 TO GVL_Param.TIERS - 1 DO
            GVL_WH.aSlots[x, y].Occupied := TRUE;       // 全库置占,只留两个等时可行位
        END_FOR
    END_FOR
    GVL_WH.aSlots[0, 1].Occupied := FALSE;
    GVL_WH.aSlots[4, 0].Occupied := FALSE;
    GVL_WH.aMaintBlock[0, 1] := FALSE;                  // 防御:确保无检修残留
    GVL_WH.aMaintBlock[4, 0] := FALSE;
    fbSel(iStrategy := 1, rGoodW := 10.0, rGoodF := 5.0, rGoodV := 0.5,
          rWMax := 10.0, rFMax := 5.0);
    aResult[60] := fbSel.xFound AND (fbSel.iBestX = 4) AND (fbSel.iBestY = 0);
    fbInit(xExecute := FALSE, iRule := 3);              // 恢复干净态(防外溢到后续)
    fbInit(xExecute := TRUE,  iRule := 3);

    // ---- T61 FC_LoadDemoGoods 满仓护栏(N4-15:395+20>400 拒载不部分写入;空仓正常加载) ----
    fbInit(xExecute := FALSE, iRule := 3);
    fbInit(xExecute := TRUE,  iRule := 3);
    GVL_WH.iGoodsCount := 395;
    aResult[61] := NOT FC_LoadDemoGoods() AND (GVL_WH.iGoodsCount = 395);
    GVL_WH.iGoodsCount := 0;
    aResult[61] := aResult[61] AND FC_LoadDemoGoods()
                   AND (GVL_WH.iGoodsCount = GVL_Data.N_DEMO);
    // R1:二次载入必须被 ID 冲突拒载(表内已有 Id 1..20),件数不变
    aResult[61] := aResult[61] AND (NOT FC_LoadDemoGoods())
                   AND (GVL_WH.iGoodsCount = GVL_Data.N_DEMO);

    // ---- T62 守卫回滚后评分立即用恢复值(N4-14 配套:值级生效;时序前置由 PRG_Main 结构保证) ----
    fbGuardT(iLevel := 1);                              // 刷快照=现值(0.15,T55 已恢复)
    rV := FC_CalcScore(rGoodW := 50.0, rGoodF := 50.0, x := 5, y := 5,
                       rWMax := 100.0, rFMax := 100.0); // 合法参数评分基准
    GVL_Param.rDelta := 0.99;                           // 模拟越权写(非管理员)
    fbGuardT(iLevel := 0);                              // 守卫回滚 rDelta
    aResult[62] := (ABS(FC_CalcScore(rGoodW := 50.0, rGoodF := 50.0, x := 5, y := 5,
                        rWMax := 100.0, rFMax := 100.0) - rV) < 0.0001);

    // ---- T63 CB 类界+空闲序跳过语义(freq 60/25/10/5→A/B/C/C;starts=[0,1,2];
    //      频次刻意远离 0.70/0.90 边界(acc=60/85/95/100)防 REAL32↔float64 舍入翻类;
    //      iRule=0=and 口径 49 格预占(x、y 均被3整除,含(0,0)/(3,0));空闲时间序头=
    //      (1,0),(2,0),(4,0),(0,1),(1,1),(2,1)…;期望坐标由 Python run_class_based(goods,"and")
    //      机器验证(勿手算):A→(1,0);B skip1→(4,0);C1 skip2→(1,1);C2 skip2→(2,1)) ----
    fbInit(xExecute := FALSE, iRule := 0);
    fbInit(xExecute := TRUE,  iRule := 0);
    GVL_WH.aGoods[1].Id := 1;  GVL_WH.aGoods[1].Weight := 10.0;
    GVL_WH.aGoods[1].Freq := 60.0;  GVL_WH.aGoods[1].Volume := 0.5;  GVL_WH.aGoods[1].Assigned := FALSE;
    GVL_WH.aGoods[2].Id := 2;  GVL_WH.aGoods[2].Weight := 10.0;
    GVL_WH.aGoods[2].Freq := 25.0;  GVL_WH.aGoods[2].Volume := 0.5;  GVL_WH.aGoods[2].Assigned := FALSE;
    GVL_WH.aGoods[3].Id := 3;  GVL_WH.aGoods[3].Weight := 10.0;
    GVL_WH.aGoods[3].Freq := 10.0;  GVL_WH.aGoods[3].Volume := 0.5;  GVL_WH.aGoods[3].Assigned := FALSE;
    GVL_WH.aGoods[4].Id := 4;  GVL_WH.aGoods[4].Weight := 10.0;
    GVL_WH.aGoods[4].Freq := 5.0;   GVL_WH.aGoods[4].Volume := 0.5;  GVL_WH.aGoods[4].Assigned := FALSE;
    GVL_WH.iGoodsCount := 4;
    fbCT(xStart := FALSE, iMode := 4);
    fbCT(xStart := TRUE,  iMode := 4);
    n := 0;
    WHILE fbCT.xBusy AND (n < 100000) DO
        fbCT(xStart := TRUE, iMode := 4);
        n := n + 1;
    END_WHILE
    aResult[63] := (GVL_WH.iCbClass[1] = 0) AND (GVL_WH.iCbClass[2] = 1)
               AND (GVL_WH.iCbClass[3] = 2) AND (GVL_WH.iCbClass[4] = 2)
               AND (GVL_WH.aCbStarts[0] = 0) AND (GVL_WH.aCbStarts[1] = 1)
               AND (GVL_WH.aCbStarts[2] = 2)
               AND (GVL_WH.aGoods[1].X = 1) AND (GVL_WH.aGoods[1].Y = 0)
               AND (GVL_WH.aGoods[2].X = 4) AND (GVL_WH.aGoods[2].Y = 0)
               AND (GVL_WH.aGoods[3].X = 1) AND (GVL_WH.aGoods[3].Y = 1)
               AND (GVL_WH.aGoods[4].X = 2) AND (GVL_WH.aGoods[4].Y = 1)
               AND (fbCT.iAssigned = 4) AND (fbCT.iFailed = 0);

    // ---- T64 CB 近满仓:钳位(空闲≤类起点→试最后空闲格)+满仓 fail(freq 60/25/15→A/B/C,
    //      acc=60/85/100 远离边界;仅留 (0,0),(9,9):A→(0,0);B skip1 空闲仅1→钳位落(9,9);
    //      C skip2 空闲0→fail) ----
    fbInit(xExecute := FALSE, iRule := 0);
    fbInit(xExecute := TRUE,  iRule := 0);
    FOR x := 0 TO GVL_Param.COLS - 1 DO
        FOR y := 0 TO GVL_Param.TIERS - 1 DO
            GVL_WH.aSlots[x, y].Occupied := TRUE;
        END_FOR
    END_FOR
    GVL_WH.aSlots[0, 0].Occupied := FALSE;
    GVL_WH.aSlots[9, 9].Occupied := FALSE;
    GVL_WH.aGoods[1].Id := 1;  GVL_WH.aGoods[1].Weight := 10.0;
    GVL_WH.aGoods[1].Freq := 60.0;  GVL_WH.aGoods[1].Volume := 0.5;  GVL_WH.aGoods[1].Assigned := FALSE;
    GVL_WH.aGoods[2].Id := 2;  GVL_WH.aGoods[2].Weight := 10.0;
    GVL_WH.aGoods[2].Freq := 25.0;  GVL_WH.aGoods[2].Volume := 0.5;  GVL_WH.aGoods[2].Assigned := FALSE;
    GVL_WH.aGoods[3].Id := 3;  GVL_WH.aGoods[3].Weight := 10.0;
    GVL_WH.aGoods[3].Freq := 15.0;  GVL_WH.aGoods[3].Volume := 0.5;  GVL_WH.aGoods[3].Assigned := FALSE;
    GVL_WH.iGoodsCount := 3;
    fbCT(xStart := FALSE, iMode := 4);
    fbCT(xStart := TRUE,  iMode := 4);
    n := 0;
    WHILE fbCT.xBusy AND (n < 100000) DO
        fbCT(xStart := TRUE, iMode := 4);
        n := n + 1;
    END_WHILE
    aResult[64] := (GVL_WH.aGoods[1].X = 0) AND (GVL_WH.aGoods[1].Y = 0)
               AND (GVL_WH.aGoods[2].X = 9) AND (GVL_WH.aGoods[2].Y = 9)
               AND (NOT GVL_WH.aGoods[3].Assigned)
               AND (fbCT.iAssigned = 2) AND (fbCT.iFailed = 1);

    // ---- T65 TOB 周转序(freq 5/50/20→放置序 Id2,Id3,Id1;iRule=0=and 预占含(0,0),
    //      期望由 Python run_full_turnover(goods,"and") 机器验证:(1,0),(2,0),(4,0)) ----
    fbInit(xExecute := FALSE, iRule := 0);
    fbInit(xExecute := TRUE,  iRule := 0);
    GVL_WH.aGoods[1].Id := 1;  GVL_WH.aGoods[1].Weight := 10.0;
    GVL_WH.aGoods[1].Freq := 5.0;   GVL_WH.aGoods[1].Volume := 0.5;  GVL_WH.aGoods[1].Assigned := FALSE;
    GVL_WH.aGoods[2].Id := 2;  GVL_WH.aGoods[2].Weight := 10.0;
    GVL_WH.aGoods[2].Freq := 50.0;  GVL_WH.aGoods[2].Volume := 0.5;  GVL_WH.aGoods[2].Assigned := FALSE;
    GVL_WH.aGoods[3].Id := 3;  GVL_WH.aGoods[3].Weight := 10.0;
    GVL_WH.aGoods[3].Freq := 20.0;  GVL_WH.aGoods[3].Volume := 0.5;  GVL_WH.aGoods[3].Assigned := FALSE;
    GVL_WH.iGoodsCount := 3;
    fbCT(xStart := FALSE, iMode := 5);
    fbCT(xStart := TRUE,  iMode := 5);
    n := 0;
    WHILE fbCT.xBusy AND (n < 100000) DO
        fbCT(xStart := TRUE, iMode := 5);
        n := n + 1;
    END_WHILE
    aResult[65] := (GVL_WH.aGoods[2].X = 1) AND (GVL_WH.aGoods[2].Y = 0)
               AND (GVL_WH.aGoods[3].X = 2) AND (GVL_WH.aGoods[3].Y = 0)
               AND (GVL_WH.aGoods[1].X = 4) AND (GVL_WH.aGoods[1].Y = 0)
               AND (fbCT.iAssigned = 3) AND (fbCT.iFailed = 0);

    // ---- T66 检测器 lexicographic 三分支(n=200→CB(4);60→AWRA(3);120→TOB(5)) ----
    fbInit(xExecute := FALSE, iRule := 0);
    fbInit(xExecute := TRUE,  iRule := 0);
    FOR i := 1 TO 200 DO
        GVL_WH.aGoods[i].Id := i;  GVL_WH.aGoods[i].Weight := 10.0;
        GVL_WH.aGoods[i].Freq := 5.0;  GVL_WH.aGoods[i].Volume := 0.5;
        GVL_WH.aGoods[i].Assigned := FALSE;
    END_FOR
    GVL_WH.iGoodsCount := 200;                          // density=200/267=0.749≥0.70
    n := 0;
    fbDetT(iObjective := 1);
    WHILE NOT fbDetT.xValid AND (n < 1000) DO
        fbDetT(iObjective := 1);
        n := n + 1;
    END_WHILE
    aResult[66] := fbDetT.xValid AND (fbDetT.iRecBatch = 4);
    GVL_WH.iGoodsCount := 60;                           // density=0.225≤0.25 且 n>20
    n := 0;
    fbDetT(iObjective := 1);
    WHILE NOT fbDetT.xValid AND (n < 1000) DO
        fbDetT(iObjective := 1);
        n := n + 1;
    END_WHILE
    aResult[66] := aResult[66] AND fbDetT.xValid AND (fbDetT.iRecBatch = 3);
    GVL_WH.iGoodsCount := 120;                          // density=0.449→主导档
    n := 0;
    fbDetT(iObjective := 1);
    WHILE NOT fbDetT.xValid AND (n < 1000) DO
        fbDetT(iObjective := 1);
        n := n + 1;
    END_WHILE
    aResult[66] := aResult[66] AND fbDetT.xValid AND (fbDetT.iRecBatch = 5);

    // ---- T67 tiny_light 防回归(n=20,density=0.075:n≤20→TOB(5) 而非 AWRA;
    //      st_ifelse 旧生成文本漏 n>20 条件曾误路由,权威=select_strategy) ----
    GVL_WH.iGoodsCount := 20;
    n := 0;
    fbDetT(iObjective := 1);
    WHILE NOT fbDetT.xValid AND (n < 1000) DO
        fbDetT(iObjective := 1);
        n := n + 1;
    END_WHILE
    aResult[67] := fbDetT.xValid AND (fbDetT.iRecBatch = 5);
    GVL_WH.iGoodsCount := 0;                            // 清场防外溢
    fbDetT(iObjective := 0);

    // ---- T68 CB 全流程终局一致性(端到端黄金向量;同 T25 哲学:逐位+聚合+计数+违规0;
    //      向量源=07_GVL_Data aCbExpect/CB_*(sum 官方口径,匀速,seed2026 20件)) ----
    GVL_Param.xUseAccel := FALSE;
    GVL_WH.iGoodsCount := 0;
    fbInit(xExecute := FALSE, iRule := 3);
    fbInit(xExecute := TRUE,  iRule := 3);              // sum 官方口径(133 预占)
    FC_LoadDemoGoods();
    fbCT(xStart := FALSE, iMode := 4);
    fbCT(xStart := TRUE,  iMode := 4);
    n := 0;
    WHILE fbCT.xBusy AND (n < 100000) DO
        fbCT(xStart := TRUE, iMode := 4);
        n := n + 1;
    END_WHILE
    fbStats(xExecute := FALSE);
    fbStats(xExecute := TRUE);
    iCtPosDiff := 0;
    FOR i := 1 TO GVL_Data.N_CB DO
        IF (GVL_WH.aGoods[GVL_Data.aCbExpect[i].Id].X <> GVL_Data.aCbExpect[i].X)
        OR (GVL_WH.aGoods[GVL_Data.aCbExpect[i].Id].Y <> GVL_Data.aCbExpect[i].Y) THEN
            iCtPosDiff := iCtPosDiff + 1;
        END_IF
    END_FOR
    aResult[68] := (iCtPosDiff = 0)
       AND (GVL_WH.stStats.PlacedCnt = GVL_Data.CB_PLACED)
       AND (GVL_WH.stStats.FailedCnt = GVL_Data.CB_FAILED)
       AND (ABS(GVL_WH.stStats.ExpRetrieval - GVL_Data.CB_EXPT) < 0.001)
       AND (ABS(GVL_WH.stStats.Energy      - GVL_Data.CB_ENERGY) < 0.01)
       AND (GVL_WH.stStats.ViolCnt = 0);

    // ---- T69 TOB 全流程终局一致性(同 T68;向量源=aTobExpect/TOB_*) ----
    GVL_WH.iGoodsCount := 0;
    fbInit(xExecute := FALSE, iRule := 3);
    fbInit(xExecute := TRUE,  iRule := 3);
    FC_LoadDemoGoods();
    fbCT(xStart := FALSE, iMode := 5);
    fbCT(xStart := TRUE,  iMode := 5);
    n := 0;
    WHILE fbCT.xBusy AND (n < 100000) DO
        fbCT(xStart := TRUE, iMode := 5);
        n := n + 1;
    END_WHILE
    fbStats(xExecute := FALSE);
    fbStats(xExecute := TRUE);
    iCtPosDiff := 0;
    FOR i := 1 TO GVL_Data.N_TOB DO
        IF (GVL_WH.aGoods[GVL_Data.aTobExpect[i].Id].X <> GVL_Data.aTobExpect[i].X)
        OR (GVL_WH.aGoods[GVL_Data.aTobExpect[i].Id].Y <> GVL_Data.aTobExpect[i].Y) THEN
            iCtPosDiff := iCtPosDiff + 1;
        END_IF
    END_FOR
    aResult[69] := (iCtPosDiff = 0)
       AND (GVL_WH.stStats.PlacedCnt = GVL_Data.TOB_PLACED)
       AND (GVL_WH.stStats.FailedCnt = GVL_Data.TOB_FAILED)
       AND (ABS(GVL_WH.stStats.ExpRetrieval - GVL_Data.TOB_EXPT) < 0.001)
       AND (ABS(GVL_WH.stStats.Energy      - GVL_Data.TOB_ENERGY) < 0.01)
       AND (GVL_WH.stStats.ViolCnt = 0);
    GVL_WH.iGoodsCount := 0;                            // 清场防外溢
    fbInit(xExecute := FALSE, iRule := 3);
    fbInit(xExecute := TRUE,  iRule := 3);

    // ---- T70 ID 契约(N4-16):iId<=0 拒收;重复 Id 拒收;正常唯一 Id 通过 ----
    fbInit(xExecute := FALSE, iRule := 0);
    fbInit(xExecute := TRUE,  iRule := 0);
    GVL_WH.iGoodsCount := 0;
    fbGoodsInputT(xAdd := FALSE, iId := 0, sName := 'X',
                  rWeight := 10.0, rFreq := 5.0, rVolume := 0.5);
    fbGoodsInputT(xAdd := TRUE,  iId := 0, sName := 'X',
                  rWeight := 10.0, rFreq := 5.0, rVolume := 0.5);
    aResult[70] := (NOT fbGoodsInputT.xOk) AND (fbGoodsInputT.iErrId = 4)
               AND (GVL_WH.iGoodsCount = 0);
    fbGoodsInputT(xAdd := FALSE, iId := 7, sName := 'A',
                  rWeight := 10.0, rFreq := 5.0, rVolume := 0.5);
    fbGoodsInputT(xAdd := TRUE,  iId := 7, sName := 'A',
                  rWeight := 10.0, rFreq := 5.0, rVolume := 0.5);
    aResult[70] := aResult[70] AND fbGoodsInputT.xOk AND (GVL_WH.iGoodsCount = 1);
    fbGoodsInputT(xAdd := FALSE, iId := 7, sName := 'B',
                  rWeight := 10.0, rFreq := 5.0, rVolume := 0.5);
    fbGoodsInputT(xAdd := TRUE,  iId := 7, sName := 'B',
                  rWeight := 10.0, rFreq := 5.0, rVolume := 0.5);
    aResult[70] := aResult[70] AND (NOT fbGoodsInputT.xOk)
               AND (fbGoodsInputT.iErrId = 4) AND (GVL_WH.iGoodsCount = 1);

    // ---- T71 分片钳位(N4-18):nBatchPerCycle=0 时批量仍收敛(MAX(1,·) 防静默挂起) ----
    fbInit(xExecute := FALSE, iRule := 0);
    fbInit(xExecute := TRUE,  iRule := 0);
    x := GVL_Param.nBatchPerCycle;                      // 暂存,测后恢复
    GVL_Param.nBatchPerCycle := 0;
    GVL_WH.aGoods[1].Id := 1;  GVL_WH.aGoods[1].Weight := 10.0;
    GVL_WH.aGoods[1].Freq := 5.0;  GVL_WH.aGoods[1].Volume := 0.5;
    GVL_WH.aGoods[1].Assigned := FALSE;
    GVL_WH.aGoods[2].Id := 2;  GVL_WH.aGoods[2].Weight := 20.0;
    GVL_WH.aGoods[2].Freq := 3.0;  GVL_WH.aGoods[2].Volume := 0.5;
    GVL_WH.aGoods[2].Assigned := FALSE;
    GVL_WH.iGoodsCount := 2;
    fbAssign(xStart := FALSE, xUseRank := FALSE, iStrategy := 2);
    fbAssign(xStart := TRUE,  xUseRank := FALSE, iStrategy := 2);
    n := 0;
    WHILE fbAssign.xBusy AND (n < 100000) DO
        fbAssign(xStart := TRUE, xUseRank := FALSE, iStrategy := 2);
        n := n + 1;
    END_WHILE
    aResult[71] := fbAssign.xDone AND GVL_WH.aGoods[1].Assigned
               AND GVL_WH.aGoods[2].Assigned;
    GVL_Param.nBatchPerCycle := x;                      // 恢复
    // R6:nPairsPerCycle/nMaxLsRounds=0 同样钳位(局搜仍收敛不挂起)
    x := GVL_Param.nPairsPerCycle;  y := GVL_Param.nMaxLsRounds;
    GVL_Param.nPairsPerCycle := 0;  GVL_Param.nMaxLsRounds := 0;
    fbImprove(xStart := FALSE);
    fbImprove(xStart := TRUE);
    n := 0;
    WHILE fbImprove.xBusy AND (n < 100000) DO
        fbImprove(xStart := TRUE);
        n := n + 1;
    END_WHILE
    aResult[71] := aResult[71] AND fbImprove.xDone;
    GVL_Param.nPairsPerCycle := x;  GVL_Param.nMaxLsRounds := y;

    // ---- T72 违规一致性扫描(N4-20 扩):干净批=0;手动弄脏一件的记录坐标→检出>=1 ----
    fbStats(xExecute := FALSE);
    fbStats(xExecute := TRUE);                          // T71 的 2 件干净布局
    aResult[72] := (GVL_WH.stStats.ViolCnt = 0);
    GVL_WH.aGoods[1].X := 15;  GVL_WH.aGoods[1].Y := 15;   // 记录改到无货格(格侧未动)
    fbStats(xExecute := FALSE);
    fbStats(xExecute := TRUE);
    aResult[72] := aResult[72] AND (GVL_WH.stStats.ViolCnt >= 1);
    // R2:幽灵格((17,18) 非预占;占用+GoodsId 指向不存在货物)由计数平衡现形→违规再+1
    GVL_WH.aSlots[17, 18].Occupied := TRUE;
    GVL_WH.aSlots[17, 18].GoodsId := 999;
    fbStats(xExecute := FALSE);
    fbStats(xExecute := TRUE);
    aResult[72] := aResult[72] AND (GVL_WH.stStats.ViolCnt >= 2);
    GVL_WH.aSlots[17, 18].Occupied := FALSE;            // 清理幽灵格
    GVL_WH.aSlots[17, 18].GoodsId := 0;

    // ---- T73 检修真冻结(N4-23/A3):冻结源位存量不被重定位搬走;解除后允许搬 ----
    fbInit(xExecute := FALSE, iRule := 0);
    fbInit(xExecute := TRUE,  iRule := 0);
    GVL_WH.aGoods[1].Id := 1;  GVL_WH.aGoods[1].Weight := 10.0;
    GVL_WH.aGoods[1].Freq := 50.0;  GVL_WH.aGoods[1].Volume := 0.5;
    GVL_WH.aGoods[1].Assigned := TRUE;                  // 手动放远位(19,19):高频货在远位=必有更优
    GVL_WH.aGoods[1].X := 19;  GVL_WH.aGoods[1].Y := 19;
    GVL_WH.aSlots[19, 19].Occupied := TRUE;
    GVL_WH.aSlots[19, 19].GoodsId := 1;
    GVL_WH.aRankIdx[1] := 1;
    GVL_WH.iGoodsCount := 1;
    GVL_WH.aMaintBlock[19, 19] := TRUE;                 // 冻结源位
    fbImprove(xStart := FALSE);
    fbImprove(xStart := TRUE);
    n := 0;
    WHILE fbImprove.xBusy AND (n < 100000) DO
        fbImprove(xStart := TRUE);
        n := n + 1;
    END_WHILE
    aResult[73] := (GVL_WH.aGoods[1].X = 19) AND (GVL_WH.aGoods[1].Y = 19);  // 未被搬走
    GVL_WH.aMaintBlock[19, 19] := FALSE;                // 解除冻结
    fbImprove(xStart := FALSE);
    fbImprove(xStart := TRUE);
    n := 0;
    WHILE fbImprove.xBusy AND (n < 100000) DO
        fbImprove(xStart := TRUE);
        n := n + 1;
    END_WHILE
    aResult[73] := aResult[73]
               AND ((GVL_WH.aGoods[1].X <> 19) OR (GVL_WH.aGoods[1].Y <> 19));  // 搬到更优位
    GVL_WH.iGoodsCount := 0;                            // 清场

    // ---- T74 FC_TMax 除零钳位(N4-24):rVx=0 不炸且>0;恢复后=38.0(max(9.5,38)) ----
    rV := GVL_Param.rVx;
    GVL_Param.rVx := 0.0;
    // R4:非法速度回落 1.0 与行程函数同源→分母恰=38(max(19/1.0, 19/0.5)),非仅">0"
    aResult[74] := (ABS(FC_TMax() - 38.0) < 0.001);
    GVL_Param.rVx := rV;
    aResult[74] := aResult[74] AND (ABS(FC_TMax() - 38.0) < 0.001);

    // ---- T75 CT 忙时重入护栏(R7):运行中二次 xStart 沿+改 iMode 均被忽略——
    //      不重启(否则重复放置 iAssigned=8)、不切档(否则第3件走 TOB 落 (4,0) 而非 CB 的 (1,1))。
    //      场景=T63 同款 4 件(and 口径机器验证布局 (1,0)/(4,0)/(1,1)/(2,1))。
    //      注:计数器饱和(N5-09/10/11)为类型级改动由编译+回归覆盖;PRG_Main 行为项
    //      (N5-05 清零/N4-17 锁存/N4-22 快照)由演示预演人工验证(PRG_Test 测不到主状态机)。 ----
    fbInit(xExecute := FALSE, iRule := 0);
    fbInit(xExecute := TRUE,  iRule := 0);
    GVL_WH.aGoods[1].Id := 1;  GVL_WH.aGoods[1].Weight := 10.0;
    GVL_WH.aGoods[1].Freq := 60.0;  GVL_WH.aGoods[1].Volume := 0.5;  GVL_WH.aGoods[1].Assigned := FALSE;
    GVL_WH.aGoods[2].Id := 2;  GVL_WH.aGoods[2].Weight := 10.0;
    GVL_WH.aGoods[2].Freq := 25.0;  GVL_WH.aGoods[2].Volume := 0.5;  GVL_WH.aGoods[2].Assigned := FALSE;
    GVL_WH.aGoods[3].Id := 3;  GVL_WH.aGoods[3].Weight := 10.0;
    GVL_WH.aGoods[3].Freq := 10.0;  GVL_WH.aGoods[3].Volume := 0.5;  GVL_WH.aGoods[3].Assigned := FALSE;
    GVL_WH.aGoods[4].Id := 4;  GVL_WH.aGoods[4].Weight := 10.0;
    GVL_WH.aGoods[4].Freq := 5.0;   GVL_WH.aGoods[4].Volume := 0.5;  GVL_WH.aGoods[4].Assigned := FALSE;
    GVL_WH.iGoodsCount := 4;
    fbCT(xStart := FALSE, iMode := 4);
    fbCT(xStart := TRUE,  iMode := 4);                  // 启动(CB)
    FOR i := 1 TO 3 DO
        fbCT(xStart := TRUE, iMode := 4);               // 驱动数拍(序表插入排序中,仍 busy)
    END_FOR
    fbCT(xStart := FALSE, iMode := 5);                  // 中途落沿+改档
    fbCT(xStart := TRUE,  iMode := 5);                  // 二次上升沿:应被 iPhase 门忽略
    n := 0;
    WHILE fbCT.xBusy AND (n < 100000) DO
        fbCT(xStart := TRUE, iMode := 5);
        n := n + 1;
    END_WHILE
    aResult[75] := fbCT.xDone AND (fbCT.iAssigned = 4) AND (fbCT.iFailed = 0)
               AND (GVL_WH.aGoods[3].X = 1) AND (GVL_WH.aGoods[3].Y = 1);   // CB 语义保持=锁存生效
    GVL_WH.iGoodsCount := 0;                            // 清场
    fbInit(xExecute := FALSE, iRule := 3);
    fbInit(xExecute := TRUE,  iRule := 3);

    // ---- T76 FB_RetrieveGood 取出演示(E7 0716;赛题行22"存取效率"动作侧):
    //      不存在REJ/未分配REJ/正常取出落账/取后查询口径 四分支;xInstant 直通单周期断言 ----
    fbInit(xExecute := FALSE, iRule := 0);
    fbInit(xExecute := TRUE,  iRule := 0);              // 干净仓(标准预占)
    GVL_WH.aGoods[1].Id := 1;  GVL_WH.aGoods[1].Name := 'R1';
    GVL_WH.aGoods[1].Weight := 10.0;  GVL_WH.aGoods[1].Freq := 5.0;  GVL_WH.aGoods[1].Volume := 0.5;
    GVL_WH.aGoods[1].Assigned := TRUE;  GVL_WH.aGoods[1].X := 2;  GVL_WH.aGoods[1].Y := 3;
    GVL_WH.aSlots[2, 3].Occupied := TRUE;  GVL_WH.aSlots[2, 3].GoodsId := 1;
    GVL_WH.aGoods[2].Id := 2;  GVL_WH.aGoods[2].Name := 'R2';
    GVL_WH.aGoods[2].Weight := 10.0;  GVL_WH.aGoods[2].Freq := 5.0;  GVL_WH.aGoods[2].Volume := 0.5;
    GVL_WH.aGoods[2].Assigned := FALSE;
    GVL_WH.iGoodsCount := 2;
    GVL_Visu.iRetrievedCount := 0;
    GVL_WH.aSlotOps[2, 3] := UDINT#0;                   // 存取计数清零(UDINT 零基锚,避免向 INT 读出)
    // (a) 不存在 Id=999 → REJ 完成脉冲,计数不动
    fbRetrT(xRetrieve := FALSE, iId := 999, xInstant := TRUE);
    fbRetrT(xRetrieve := TRUE,  iId := 999, xInstant := TRUE);
    aResult[76] := fbRetrT.xDone AND (GVL_Visu.iRetrievedCount = 0);
    // (b) 未分配 Id=2 → REJ,格位不动
    fbRetrT(xRetrieve := FALSE, iId := 2, xInstant := TRUE);
    fbRetrT(xRetrieve := TRUE,  iId := 2, xInstant := TRUE);
    aResult[76] := aResult[76] AND (GVL_Visu.iRetrievedCount = 0) AND GVL_WH.aSlots[2, 3].Occupied;
    // (c) 正常取出 Id=1:格位释放/货物转未分配/取出计数+1/存取损耗计数+1(C6 口径)
    fbRetrT(xRetrieve := FALSE, iId := 1, xInstant := TRUE);
    fbRetrT(xRetrieve := TRUE,  iId := 1, xInstant := TRUE);
    aResult[76] := aResult[76] AND (NOT GVL_WH.aSlots[2, 3].Occupied)
                   AND (GVL_WH.aSlots[2, 3].GoodsId = 0)
                   AND (NOT GVL_WH.aGoods[1].Assigned)
                   AND (GVL_Visu.iRetrievedCount = 1)
                   AND (GVL_WH.aSlotOps[2, 3] = UDINT#1);
    // (d) 取后查询同 Id:找得到但未分配(QryX=-1)—— 与查询页口径自洽
    fbQueryT(xQuery := FALSE, iId := 1);
    fbQueryT(xQuery := TRUE,  iId := 1);
    aResult[76] := aResult[76] AND GVL_Visu.QryFound AND (GVL_Visu.QryX = -1);
    GVL_WH.iGoodsCount := 0;                            // 清场恢复
    fbInit(xExecute := FALSE, iRule := 3);
    fbInit(xExecute := TRUE,  iRule := 3);

    // ---- T77 FC_TMax 跟随 xUseAccel 口径(0717 治理D;深审 P1-3) ----
    //      匀速:TMax=MAX(19/2, 19/0.5)=38.0;
    //      加减速:ty=FC_AxisTime(19,0.5,0.3)=19/0.5+0.5/0.3=39.6667(v²/a=0.833<d 梯形段),
    //             tx=FC_AxisTime(19,2,0.5)=9.5+4=13.5,TMax=39.6667;
    //      同口径下全库最远格 tNorm=分子/分母 恒 1.0(位置保留项 1-tNorm 不再为负)。
    GVL_Param.xUseAccel := FALSE;
    aResult[77] := (ABS(FC_TMax() - 38.0) < 0.001);
    GVL_Param.xUseAccel := TRUE;
    rV := FC_CalcTravelTime(x0 := 0, y0 := 0,
                            x1 := GVL_Param.COLS - 1, y1 := GVL_Param.TIERS - 1,
                            xSimXY := TRUE) / FC_TMax();
    aResult[77] := aResult[77] AND (ABS(FC_TMax() - 39.666667) < 0.001)
                   AND (ABS(rV - 1.0) < 0.000001);
    GVL_Param.xUseAccel := FALSE;               // 恢复默认口径(测试自给自足)

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
