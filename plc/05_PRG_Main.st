(* ============================================================
   05_PRG_Main.st — 主程序(状态机)
   导入方法:POU 类型"程序(Program)",挂到循环任务(建议周期 10ms)
   演示流程(决赛口径):初始化 → 交互输入/载入演示批次 → 批量分配
   → 局部搜索(AWRA-LS)→ 统计 → 可视化呈现;全程非阻塞。
   ============================================================ *)
PROGRAM PRG_Main
VAR
    eState      : E_MainState := E_MainState.STATE_IDLE;
    fbInit      : FB_InitWarehouse;
    fbAssign    : FB_AssignAllGoods;
    fbImprove   : FB_LocalSwapImprove;
    fbStats     : FB_Stats;
    fbPath      : FB_BuildVisuPath;
    fbSelOne    : FB_SelectSlot;        // 单件交互添加时即时推荐用
    xKickInit, xKickAssign, xKickImprove, xKickStats : BOOL;
    xUseRank    : BOOL;
    iStrat      : INT;
    i           : INT;
    rWMaxTmp, rFMaxTmp : REAL;
    xAddOld, xDemoOld, xRunOld, xResetOld : BOOL;
END_VAR

// ---------- 全局按钮:复位(任意状态可触发) ----------
IF GVL_Visu.CmdReset AND NOT xResetOld THEN
    GVL_WH.iGoodsCount := 0;
    GVL_WH.stStats.PlacedCnt := 0;  GVL_WH.stStats.FailedCnt := 0;
    GVL_Visu.VisuStatusText := '复位:仓库重新初始化';
    eState := E_MainState.STATE_INIT;
END_IF
xResetOld := GVL_Visu.CmdReset;

CASE eState OF
    // ---------- 待机:上电自动进入初始化 ----------
    E_MainState.STATE_IDLE:
        eState := E_MainState.STATE_INIT;

    // ---------- 初始化仓库 ----------
    E_MainState.STATE_INIT:
        xKickInit := TRUE;
        fbInit(xExecute := xKickInit, iRule := GVL_Param.iPreRule);
        IF fbInit.xDone THEN
            xKickInit := FALSE;
            GVL_Visu.VisuStatusText := CONCAT('就绪:预占用格数=', INT_TO_STRING(fbInit.iPreCount));
            eState := E_MainState.STATE_WAIT_INPUT;
        END_IF

    // ---------- 等待输入(决赛交互:逐件添加 / 载入演示批 / 启动批量) ----------
    E_MainState.STATE_WAIT_INPUT:
        // 按钮1:添加单件货物(题面五属性),并即时给出推荐仓位(黄色高亮)
        IF GVL_Visu.CmdAddGood AND NOT xAddOld THEN
            IF GVL_WH.iGoodsCount >= GVL_Param.MAX_GOODS THEN
                GVL_Visu.VisuStatusText := '错误:货物表已满(400)';         // 边界#表满
            ELSIF GVL_Visu.InGoodWeight < 0.0 OR GVL_Visu.InGoodFreq < 0.0
                  OR GVL_Visu.InGoodVolume < 0.0 THEN
                GVL_Visu.VisuStatusText := '错误:重量/频次/体积不得为负';   // 边界#负输入
            ELSE
                GVL_WH.iGoodsCount := GVL_WH.iGoodsCount + 1;
                GVL_WH.aGoods[GVL_WH.iGoodsCount].Id     := GVL_Visu.InGoodId;
                GVL_WH.aGoods[GVL_WH.iGoodsCount].Name   := GVL_Visu.InGoodName;
                GVL_WH.aGoods[GVL_WH.iGoodsCount].Weight := GVL_Visu.InGoodWeight;
                GVL_WH.aGoods[GVL_WH.iGoodsCount].Freq   := GVL_Visu.InGoodFreq;
                GVL_WH.aGoods[GVL_WH.iGoodsCount].Volume := GVL_Visu.InGoodVolume;
                GVL_WH.aGoods[GVL_WH.iGoodsCount].Assigned := FALSE;
                // 即时推荐(演示脚本第2/3步:输入高频轻货→近位;重货→低层)
                rWMaxTmp := MAX(GVL_Visu.InGoodWeight, 1.0);
                rFMaxTmp := MAX(GVL_Visu.InGoodFreq, 1.0);
                FOR i := 1 TO GVL_WH.iGoodsCount DO
                    IF GVL_WH.aGoods[i].Weight > rWMaxTmp THEN rWMaxTmp := GVL_WH.aGoods[i].Weight; END_IF
                    IF GVL_WH.aGoods[i].Freq   > rFMaxTmp THEN rFMaxTmp := GVL_WH.aGoods[i].Freq;   END_IF
                END_FOR
                fbSelOne(iStrategy := 2,
                         rGoodW := GVL_Visu.InGoodWeight, rGoodF := GVL_Visu.InGoodFreq,
                         rGoodV := GVL_Visu.InGoodVolume,
                         rWMax := rWMaxTmp, rFMax := rFMaxTmp);
                IF fbSelOne.xFound THEN
                    GVL_Visu.VisuSlotState[fbSelOne.iBestX, fbSelOne.iBestY] := 3;  // 黄:推荐
                    fbPath(xExecute := TRUE, iToX := fbSelOne.iBestX, iToY := fbSelOne.iBestY);
                    fbPath(xExecute := FALSE, iToX := fbSelOne.iBestX, iToY := fbSelOne.iBestY);
                    GVL_Visu.VisuStatusText := CONCAT('推荐仓位 X=',
                        CONCAT(INT_TO_STRING(fbSelOne.iBestX),
                        CONCAT(' Y=', INT_TO_STRING(fbSelOne.iBestY))));
                ELSE
                    GVL_Visu.VisuStatusText := '报警:该货物无可行仓位!';   // 边界#9 可视化报警
                END_IF
            END_IF
        END_IF
        xAddOld := GVL_Visu.CmdAddGood;

        // 按钮2:载入演示批次(GVL_Data,由 Python seed=2026 导出,保证与仿真同源)
        IF GVL_Visu.CmdLoadDemo AND NOT xDemoOld THEN
            FC_LoadDemoGoods();
            GVL_Visu.VisuStatusText := CONCAT('演示批次已载入,件数=',
                                              INT_TO_STRING(GVL_WH.iGoodsCount));
        END_IF
        xDemoOld := GVL_Visu.CmdLoadDemo;

        // 按钮3:运行批量分配
        IF GVL_Visu.CmdRunAssign AND NOT xRunOld THEN
            IF GVL_WH.iGoodsCount = 0 THEN
                GVL_Visu.VisuStatusText := '错误:请先输入货物';
            ELSE
                // 策略选择:0=seq 1=near 2=score(在线) 3=AWRA-LS(批量=Rank+score+LS)
                xUseRank := (GVL_Visu.SelStrategy = 3);
                IF GVL_Visu.SelStrategy = 3 THEN iStrat := 2; ELSE iStrat := GVL_Visu.SelStrategy; END_IF
                xKickAssign := TRUE;
                eState := E_MainState.STATE_ASSIGN;
            END_IF
        END_IF
        xRunOld := GVL_Visu.CmdRunAssign;

    // ---------- 批量分配(分片运行中) ----------
    E_MainState.STATE_ASSIGN:
        fbAssign(xStart := xKickAssign, xUseRank := xUseRank, iStrategy := iStrat);
        xKickAssign := FALSE;
        GVL_Visu.VisuStatusText := CONCAT('分配中... 已入库=', INT_TO_STRING(fbAssign.iAssigned));
        IF fbAssign.xDone THEN
            IF GVL_Visu.SelStrategy = 3 THEN
                xKickImprove := TRUE;
                eState := E_MainState.STATE_IMPROVE;
            ELSE
                xKickStats := TRUE;
                eState := E_MainState.STATE_STATS;
            END_IF
        END_IF

    // ---------- 局部搜索(仅 AWRA-LS,分片运行中) ----------
    E_MainState.STATE_IMPROVE:
        fbImprove(xStart := xKickImprove);
        xKickImprove := FALSE;
        GVL_Visu.VisuStatusText := CONCAT('优化中... 轮=',
            CONCAT(INT_TO_STRING(fbImprove.iRounds),
            CONCAT(' 交换=', INT_TO_STRING(fbImprove.iSwaps))));
        IF fbImprove.xDone THEN
            GVL_WH.stStats.SwapCnt  := fbImprove.iSwaps;
            GVL_WH.stStats.LsRounds := fbImprove.iRounds;
            xKickStats := TRUE;
            eState := E_MainState.STATE_STATS;
        END_IF

    // ---------- 统计 ----------
    E_MainState.STATE_STATS:
        fbStats(xExecute := xKickStats);
        xKickStats := FALSE;
        IF fbStats.xDone THEN
            GVL_Visu.VisuWearIndex := GVL_WH.stStats.PathTotal2Way;   // 损耗代理=路径总长(C5)
            eState := E_MainState.STATE_DONE;
        END_IF

    // ---------- 完成:结果驻留可视化;失败件数非0则黄色警示文本 ----------
    E_MainState.STATE_DONE:
        IF GVL_WH.stStats.FailedCnt > 0 THEN
            GVL_Visu.VisuStatusText := CONCAT('完成(有失败!) 失败件数=',
                                              INT_TO_STRING(GVL_WH.stStats.FailedCnt));
        ELSE
            GVL_Visu.VisuStatusText := '完成:全部入库,违规=0';
        END_IF
        // 停留本状态;CmdReset 重来(顶部全局处理)

    E_MainState.STATE_FAULT:
        ;   // 预留:严重故障驻留(当前边界均以文本报警+拒绝操作处理)
END_CASE
END_PROGRAM
