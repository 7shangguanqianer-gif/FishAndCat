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
    fbAssignCT  : FB_AssignClassTurnover;   // 0712 轨B D-1:CB/TOB 批量分配
    fbImprove   : FB_LocalSwapImprove;
    fbStats     : FB_Stats;
    fbPath      : FB_BuildVisuPath;
    fbGoodsInput : FB_GoodsInput;       // 交互货物输入封装(0707 T2.2,替代内联逻辑+fbSelOne)
    fbVisu      : FB_VisuRefresh;       // L6:颜色镜像+堆垛机像素坐标,每周期常驻
    fbAnim      : FB_AnimatePath;       // L6:堆垛机沿路径回放动画(CmdAnimate 触发)
    fbQuery     : FB_QueryGood;         // 块3 P3:单件查询(细则8,常驻)
    fbRetrieve  : FB_RetrieveGood;      // E7(0716):取出演示(CmdRetrieve 触发,复用 InQueryId;常驻)
    fbRecPage   : FB_RecordPage;        // 块3 P2:记录页 10 行窗口(细则8,常驻)
    fbSceneDet  : FB_SceneDetect;       // A2:场景检测器(画像→推荐,常驻自动重算)
    fbAuth      : FB_UserAuth;          // A4:两级权限登录(常驻)
    fbGuard     : FB_ParamGuard;        // A4:调参守卫(常驻,双闸之二)
    xKickInit, xKickAssign, xKickImprove, xKickStats : BOOL;
    xUseRank    : BOOL;
    iStrat      : INT;
    c2, t2      : INT;                  // 清除推荐高亮用循环变量
    xDemoOld, xRunOld, xResetOld : BOOL;
    xSnapOld    : BOOL;                 // 块3:快照按钮沿检测
    xMaintOld   : BOOL;                 // A3:检修按钮沿检测
    iMaintRet   : INT;                  // A3:FC_MaintToggle 返回码
    xViewOld    : BOOL;                 // C2/C6:视图循环按钮沿检测
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
    // 0712 轨B N5-05:批次局搜统计跨批清零(AWRA→Reset→非AWRA 曾残留旧 SwapCnt/LsRounds)
    GVL_WH.stStats.SwapCnt := 0;
    GVL_WH.stStats.LsRounds := 0;
    GVL_WH.stStats.RelocCnt := 0;
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

// ---------- A4 登录/登出+调参守卫(0712 轨B N4-14:前置到状态机之前) ----------
// 原在段尾常驻区=守卫晚于消费者:越权改参可在同一扫描周期内先被 fbAssign 等用于选位、
// 落位副作用不可回滚。前置后:守卫先回滚,消费者永远读干净值。PIN 消费即清。
fbAuth(xLogin := GVL_Visu.CmdLogin, iPin := GVL_Visu.InPinCode,
       xLogout := GVL_Visu.CmdLogout);
GVL_Visu.iUserLevel := fbAuth.iLevel;
GVL_Visu.VisuUserText := fbAuth.sUserText;
IF GVL_Visu.CmdLogin OR GVL_Visu.CmdLogout THEN
    GVL_Visu.InPinCode := 0;
END_IF
// 0712 轨B R3:批运行中冻结参数编辑(fbGuard 对一切写回滚)——单批口径不混参数版本
fbGuard(iLevel := fbAuth.iLevel,
        xFreeze := (eState = E_MainState.STATE_ASSIGN)
                OR (eState = E_MainState.STATE_IMPROVE)
                OR (eState = E_MainState.STATE_STATS));

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
        ELSIF fbGoodsInput.iErrId = 4 THEN
            GVL_Visu.VisuStatusText := 'ERR_BAD_ID';           // 0712 轨B N4-16:非正/重复 ID
            GVL_Visu.VisuAlarm := TRUE;
        END_IF

        // 按钮2:载入演示批次(GVL_Data,由 Python seed=2026 导出,保证与仿真同源)
        // 0712 轨B N4-15:满仓护栏(第21次连点曾可写 aGoods[401] 越界;拒载不部分写入,T61 锁)
        IF GVL_Visu.CmdLoadDemo AND NOT xDemoOld THEN
            IF GVL_WH.iGoodsCount + GVL_Data.N_DEMO <= GVL_Param.MAX_GOODS THEN
                FC_LoadDemoGoods();
                GVL_Visu.VisuStatusText := CONCAT('DEMO_LOADED_N=',
                                                  INT_TO_STRING(GVL_WH.iGoodsCount));
                GVL_Visu.VisuAlarm := FALSE;            // 新批次开始,清报警灯与旧路径
                GVL_Visu.VisuPathCount := 0;
            ELSE
                GVL_Visu.VisuStatusText := 'ERR_DEMO_FULL_400';
                GVL_Visu.VisuAlarm := TRUE;
            END_IF
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
                // 策略选择:0=seq 1=near 2=score 3=AWRA-LS 4=CB 5=TOB(0712 轨B D-1)
                xUseRank := (GVL_Visu.SelStrategy = 3);
                IF GVL_Visu.SelStrategy = 3 THEN iStrat := 2; ELSE iStrat := GVL_Visu.SelStrategy; END_IF
                // iStrat=4/5 由 STATE_ASSIGN 转发给 FB_AssignClassTurnover(启动即锁存)
                // 0712 轨B N5-05:批开工双保险清零(与 Reset 清零并存,防跨批残留)
                GVL_WH.stStats.SwapCnt := 0;
                GVL_WH.stStats.LsRounds := 0;
                GVL_WH.stStats.RelocCnt := 0;
                xKickAssign := TRUE;
                eState := E_MainState.STATE_ASSIGN;
            END_IF
        END_IF
        xRunOld := GVL_Visu.CmdRunAssign;

    // ---------- 批量分配(分片运行中) ----------
    E_MainState.STATE_ASSIGN:
        IF (iStrat = 4) OR (iStrat = 5) THEN
            // 0712 轨B D-1:CB/TOB 专用批量 FB(无 LS 阶段,完成直入统计;iStrat 启动已锁存)
            fbAssignCT(xStart := xKickAssign, iMode := iStrat);
            xKickAssign := FALSE;
            GVL_Visu.VisuStatusText := CONCAT('ASSIGN_RUN_PLACED=',
                                              INT_TO_STRING(fbAssignCT.iAssigned));
            IF fbAssignCT.xDone THEN
                xKickStats := TRUE;
                eState := E_MainState.STATE_STATS;
            END_IF
        ELSE
            fbAssign(xStart := xKickAssign, xUseRank := xUseRank, iStrategy := iStrat);
            xKickAssign := FALSE;
            GVL_Visu.VisuStatusText := CONCAT('ASSIGN_RUN_PLACED=', INT_TO_STRING(fbAssign.iAssigned));
            IF fbAssign.xDone THEN
                // 0712 轨B N4-17:用启动时锁存的 xUseRank 判断,不重读实时 SelStrategy
                // (旧写法=运行中切换策略档会错进/错过 LS 阶段的竞态)
                IF xUseRank THEN
                    xKickImprove := TRUE;
                    eState := E_MainState.STATE_IMPROVE;
                ELSE
                    xKickStats := TRUE;
                    eState := E_MainState.STATE_STATS;
                END_IF
            END_IF
        END_IF

    // ---------- 局部搜索(仅 AWRA-LS,分片运行中) ----------
    E_MainState.STATE_IMPROVE:
        fbImprove(xStart := xKickImprove);
        xKickImprove := FALSE;
        GVL_Visu.VisuStatusText := CONCAT('IMPROVE_R=',
            CONCAT(INT_TO_STRING(fbImprove.iRounds),
            CONCAT('_SWAPS=', CONCAT(DINT_TO_STRING(fbImprove.iSwaps),
            CONCAT('_RELOC=', DINT_TO_STRING(fbImprove.iRelocs))))));   // R6:两类邻域分列显示
        IF fbImprove.xDone THEN
            GVL_WH.stStats.SwapCnt  := fbImprove.iSwaps;
            GVL_WH.stStats.RelocCnt := fbImprove.iRelocs;   // 0712 轨B N5-06:重定位分列,不再漏计
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
// E7 取出演示(细则口径:赛题行22"存取效率"动作侧;复用查询输入框序号,倍速与 CmdAnimate 一致)
fbRetrieve(xRetrieve := GVL_Visu.CmdRetrieve, iId := GVL_Visu.InQueryId,
           rCycleTime := 0.01, rSpeedScale := 5.0, xInstant := FALSE);
// A2 场景检测器:货物表变化/切目标档 自动重算画像+推荐;Auto 开=推荐直写策略档(人工覆盖=关 Auto)
fbSceneDet(iObjective := GVL_Visu.SelObjective);
IF fbSceneDet.xValid AND GVL_Visu.xAutoStrategy THEN
    GVL_Visu.SelStrategy := fbSceneDet.iRecBatch;
END_IF
// A4 登录/守卫已前置到状态机之前(0712 轨B N4-14,见文件顶部)——此处不再重复调用
// A3 检修挂起/恢复(需管理员;putaway block 语义:禁新入库,存量冻结可查询)
IF GVL_Visu.CmdMaintToggle AND NOT xMaintOld THEN
    iMaintRet := FC_MaintToggle(x := GVL_Visu.InMaintX, y := GVL_Visu.InMaintY,
                                iLevel := fbAuth.iLevel);
    CASE iMaintRet OF
        0: GVL_Visu.VisuStatusText := CONCAT('MAINT_SET_X=',
               CONCAT(INT_TO_STRING(GVL_Visu.InMaintX),
               CONCAT('_Y=', INT_TO_STRING(GVL_Visu.InMaintY))));
        1: GVL_Visu.VisuStatusText := CONCAT('MAINT_CLR_X=',
               CONCAT(INT_TO_STRING(GVL_Visu.InMaintX),
               CONCAT('_Y=', INT_TO_STRING(GVL_Visu.InMaintY))));
        2: GVL_Visu.VisuStatusText := 'ERR_MAINT_NEED_ADMIN';
        3: GVL_Visu.VisuStatusText := 'ERR_MAINT_RANGE';
    END_CASE
END_IF
xMaintOld := GVL_Visu.CmdMaintToggle;
// C2/C6 视图循环:状态→频次热力→损耗热力→状态(操作员可用,分析视图)
IF GVL_Visu.CmdViewCycle AND NOT xViewOld THEN
    GVL_Visu.iViewMode := (GVL_Visu.iViewMode + 1) MOD 3;
    CASE GVL_Visu.iViewMode OF
        0: GVL_Visu.VisuStatusText := 'VIEW_STATE';
        1: GVL_Visu.VisuStatusText := 'VIEW_HEAT_FREQ';
        2: GVL_Visu.VisuStatusText := 'VIEW_HEAT_WEAR';
    END_CASE
END_IF
xViewOld := GVL_Visu.CmdViewCycle;
// 块3 方向9:快照保存(上升沿把当前布局冻结为对比基准,CmdCompareMode 切换显示)
// 0712 轨B N4-22:从 aSlots 重建纯占用态(0空闲/1预占/2占用),不再整体抄 VisuSlotState
// (后者混有推荐3/路径4/查询高亮6 等瞬态色,中途保存会污染"优化前后"对比基线)
IF GVL_Visu.CmdSaveSnap AND NOT xSnapOld THEN
    FOR c2 := 0 TO GVL_Param.COLS - 1 DO
        FOR t2 := 0 TO GVL_Param.TIERS - 1 DO
            IF GVL_WH.aSlots[c2, t2].Occupied THEN
                IF GVL_WH.aSlots[c2, t2].PresetOcc AND (GVL_WH.aSlots[c2, t2].GoodsId = 0) THEN
                    GVL_Visu.aSnapState[c2, t2] := 1;   // 预占(无货)
                ELSE
                    GVL_Visu.aSnapState[c2, t2] := 2;   // 已占
                END_IF
            ELSE
                GVL_Visu.aSnapState[c2, t2] := 0;       // 空闲
            END_IF
        END_FOR
    END_FOR
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
// 注意:CmdCompareMode/xAutoStrategy 是翻转开关、SelStrategy 是 INT 档位,均不得复位。
GVL_Visu.CmdAddGood   := FALSE;
GVL_Visu.CmdLoadDemo  := FALSE;
GVL_Visu.CmdRunAssign := FALSE;
GVL_Visu.CmdReset     := FALSE;
GVL_Visu.CmdAnimate   := FALSE;
GVL_Visu.CmdSaveSnap  := FALSE;
GVL_Visu.CmdQuery     := FALSE;
GVL_Visu.CmdRetrieve  := FALSE;     // E7(0716)
GVL_Visu.CmdPageUp    := FALSE;
GVL_Visu.CmdPageDown  := FALSE;
GVL_Visu.CmdLogin     := FALSE;     // A4(0711)
GVL_Visu.CmdLogout    := FALSE;
GVL_Visu.CmdMaintToggle := FALSE;   // A3(0711)
GVL_Visu.CmdViewCycle := FALSE;     // C2/C6(0711;iViewMode 是档位、InTierSel 是数值,均不复位)
// 颜色镜像+堆垛机像素坐标刷新(画面所有动态元件的数据源,必须在 fbAnim 之后)
fbVisu();
END_PROGRAM
