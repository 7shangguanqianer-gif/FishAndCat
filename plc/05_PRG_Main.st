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
    fbGoodsInput : FB_GoodsInput;       // 交互货物输入封装(0707 T2.2,替代内联逻辑+fbSelOne)
    fbVisu      : FB_VisuRefresh;       // L6:颜色镜像+堆垛机像素坐标,每周期常驻
    fbAnim      : FB_AnimatePath;       // L6:堆垛机沿路径回放动画(CmdAnimate 触发)
    fbQuery     : FB_QueryGood;         // 块3 P3:单件查询(细则8,常驻)
    fbRecPage   : FB_RecordPage;        // 块3 P2:记录页 10 行窗口(细则8,常驻)
    xKickInit, xKickAssign, xKickImprove, xKickStats : BOOL;
    xUseRank    : BOOL;
    iStrat      : INT;
    c2, t2      : INT;                  // 清除推荐高亮用循环变量
    xDemoOld, xRunOld, xResetOld : BOOL;
    xSnapOld    : BOOL;                 // 块3:快照按钮沿检测
END_VAR

// ---------- 全局按钮:复位(任意状态可触发) ----------
IF GVL_Visu.CmdReset AND NOT xResetOld THEN
    GVL_WH.iGoodsCount := 0;
    GVL_WH.stStats.PlacedCnt := 0;  GVL_WH.stStats.FailedCnt := 0;
    GVL_Visu.VisuStatusText := 'RESET_INIT';
    GVL_Visu.VisuAlarm := FALSE;                    // 复位清报警灯
    GVL_Visu.VisuPathCount := 0;                    // 复位清路径叠加
    GVL_Visu.VisuCurrentX := 0;                     // 堆垛机归位 I/O 口(左下角)
    GVL_Visu.VisuCurrentY := 0;
    // 0711 修:复位同时清统计/路径显示残留(旧版遗留 186.0/370 等旧批数字误导评委)
    GVL_Visu.VisuTotalTime := 0.0;
    GVL_Visu.VisuAvgTime := 0.0;
    GVL_Visu.VisuSpaceUtilization := 0.0;
    GVL_Visu.VisuWearIndex := 0.0;
    GVL_Visu.VisuViolationCount := 0;
    GVL_Visu.VisuPathLen := 0.0;
    GVL_Visu.VisuExecTime := 0.0;
    GVL_Visu.VisuTargetX := 0;
    GVL_Visu.VisuTargetY := 0;
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
            GVL_Visu.VisuStatusText := CONCAT('READY_PRECOUNT=', INT_TO_STRING(fbInit.iPreCount));
            eState := E_MainState.STATE_WAIT_INPUT;
        END_IF

    // ---------- 等待输入(决赛交互:逐件添加 / 载入演示批 / 启动批量) ----------
    E_MainState.STATE_WAIT_INPUT:
        // 按钮1:添加单件货物(五属性)——逻辑封装进 FB_GoodsInput(0707 T2.2),PRG 只编排可视化
        fbGoodsInput(xAdd := GVL_Visu.CmdAddGood,
                     iId := GVL_Visu.InGoodId, sName := GVL_Visu.InGoodName,
                     rWeight := GVL_Visu.InGoodWeight, rFreq := GVL_Visu.InGoodFreq,
                     rVolume := GVL_Visu.InGoodVolume);
        IF fbGoodsInput.xOk THEN
            IF fbGoodsInput.xFound THEN
                GVL_Visu.VisuSlotState[fbGoodsInput.iSugX, fbGoodsInput.iSugY] := 3;  // 黄:推荐
                fbPath(xExecute := TRUE,  iToX := fbGoodsInput.iSugX, iToY := fbGoodsInput.iSugY);
                fbPath(xExecute := FALSE, iToX := fbGoodsInput.iSugX, iToY := fbGoodsInput.iSugY);
                GVL_Visu.VisuStatusText := CONCAT('SUGGEST_X=',
                    CONCAT(INT_TO_STRING(fbGoodsInput.iSugX),
                    CONCAT('_Y=', INT_TO_STRING(fbGoodsInput.iSugY))));
                GVL_Visu.VisuAlarm := FALSE;                   // 推荐成功清报警灯
            ELSE
                GVL_Visu.VisuStatusText := 'ALARM_NO_FEASIBLE_SLOT';   // 边界#9 超重货无位
                GVL_Visu.VisuAlarm := TRUE;                    // 红灯(演示第6步)
            END_IF
        ELSIF fbGoodsInput.iErrId = 1 THEN
            GVL_Visu.VisuStatusText := 'ERR_GOODS_FULL_400';   // 边界:满仓
            GVL_Visu.VisuAlarm := TRUE;
        ELSIF fbGoodsInput.iErrId = 2 THEN
            GVL_Visu.VisuStatusText := 'ERR_NEG_INPUT';        // 边界:负输入
            GVL_Visu.VisuAlarm := TRUE;
        END_IF

        // 按钮2:载入演示批次(GVL_Data,由 Python seed=2026 导出,保证与仿真同源)
        IF GVL_Visu.CmdLoadDemo AND NOT xDemoOld THEN
            FC_LoadDemoGoods();
            GVL_Visu.VisuStatusText := CONCAT('DEMO_LOADED_N=',
                                              INT_TO_STRING(GVL_WH.iGoodsCount));
            GVL_Visu.VisuAlarm := FALSE;                // 新批次开始,清报警灯与旧路径
            GVL_Visu.VisuPathCount := 0;
        END_IF
        xDemoOld := GVL_Visu.CmdLoadDemo;

        // 按钮3:运行批量分配
        IF GVL_Visu.CmdRunAssign AND NOT xRunOld THEN
            IF GVL_WH.iGoodsCount = 0 THEN
                GVL_Visu.VisuStatusText := 'ERR_NO_GOODS';
                GVL_Visu.VisuAlarm := TRUE;
            ELSE
                // 进入批量前清交互阶段残留:推荐黄格回写空闲(推荐只会盖在空闲格上,
                // fbSelOne 只选可行空位,故直接回写0安全)+ 路径叠加清除 + 报警灯灭
                FOR c2 := 0 TO GVL_Param.COLS - 1 DO
                    FOR t2 := 0 TO GVL_Param.TIERS - 1 DO
                        IF GVL_Visu.VisuSlotState[c2, t2] = 3 THEN
                            GVL_Visu.VisuSlotState[c2, t2] := 0;
                        END_IF
                    END_FOR
                END_FOR
                GVL_Visu.VisuPathCount := 0;
                GVL_Visu.VisuAlarm := FALSE;
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
        GVL_Visu.VisuStatusText := CONCAT('ASSIGN_RUN_PLACED=', INT_TO_STRING(fbAssign.iAssigned));
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
        GVL_Visu.VisuStatusText := CONCAT('IMPROVE_R=',
            CONCAT(INT_TO_STRING(fbImprove.iRounds),
            CONCAT('_SWAPS=', INT_TO_STRING(fbImprove.iSwaps))));
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

    // ---------- 完成:结果驻留可视化;失败件数非0则警示文本+红灯 ----------
    E_MainState.STATE_DONE:
        IF GVL_WH.stStats.FailedCnt > 0 THEN
            GVL_Visu.VisuStatusText := CONCAT('DONE_FAILED_N=',
                                              INT_TO_STRING(GVL_WH.stStats.FailedCnt));
            GVL_Visu.VisuAlarm := TRUE;    // 与其他异常态一致:有货无位=红灯(0705补)
        ELSE
            GVL_Visu.VisuStatusText := 'DONE_OK';
        END_IF
        // 停留本状态;CmdReset 重来(顶部全局处理)

    E_MainState.STATE_FAULT:
        ;   // 预留:严重故障驻留(当前边界均以文本报警+拒绝操作处理)
END_CASE

// ---------- L6 常驻段(每周期,与状态机无关) ----------
// 块3 P2/P3:记录页窗口+单件查询(常驻:DONE 后评委翻表/查询仍可用)
fbRecPage(xPageUp := GVL_Visu.CmdPageUp, xPageDown := GVL_Visu.CmdPageDown);
fbQuery(xQuery := GVL_Visu.CmdQuery, iId := GVL_Visu.InQueryId);
// 块3 方向9:快照保存(上升沿把当前布局冻结为对比基准,CmdCompareMode 切换显示)
IF GVL_Visu.CmdSaveSnap AND NOT xSnapOld THEN
    GVL_Visu.aSnapState := GVL_Visu.VisuSlotState;      // 同型数组整体赋值
    GVL_Visu.xSnapValid := TRUE;
    GVL_Visu.VisuStatusText := 'SNAP_SAVED';
END_IF
xSnapOld := GVL_Visu.CmdSaveSnap;
// 块3:名称下拉同步(ComboBox 写入下标,消费即复位=一次性写入不锁手输)
IF GVL_Visu.iNameSel >= 0 AND GVL_Visu.iNameSel <= 9 THEN
    GVL_Visu.InGoodName := GVL_Visu.astrNames[GVL_Visu.iNameSel];
    GVL_Visu.iNameSel := -1;
END_IF
// 动画回放:CmdAnimate 上升沿触发,堆垛机图元沿当前 VisuPath 走到目标格
// (rCycleTime 与本任务周期一致:10ms 任务填 0.01;改任务周期须同步这里)
fbAnim(xStart := GVL_Visu.CmdAnimate, rCycleTime := 0.01, rSpeedScale := 5.0);
// ---------- 0711 疫苗:脉冲命令消费即复位(段尾,所有消费者已跑完) ----------
// 防两类实测事故:①MouseUp 事件丢失致命令卡 TRUE(Load demo 风暴 N=260)
// ②输入积压在 download 后突发重放。复位后命令只存活一个扫描周期,天然免疫。
// 注意:CmdCompareMode 是翻转开关、SelStrategy 是 INT 档位,均不得复位。
GVL_Visu.CmdAddGood   := FALSE;
GVL_Visu.CmdLoadDemo  := FALSE;
GVL_Visu.CmdRunAssign := FALSE;
GVL_Visu.CmdReset     := FALSE;
GVL_Visu.CmdAnimate   := FALSE;
GVL_Visu.CmdSaveSnap  := FALSE;
GVL_Visu.CmdQuery     := FALSE;
GVL_Visu.CmdPageUp    := FALSE;
GVL_Visu.CmdPageDown  := FALSE;
// 颜色镜像+堆垛机像素坐标刷新(画面所有动态元件的数据源,必须在 fbAnim 之后)
fbVisu();
END_PROGRAM
