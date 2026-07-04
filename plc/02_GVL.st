(* ============================================================
   02_GVL.st — 全局变量列表
   导入方法:Application 右键 → 添加对象 → 全局变量列表(GVL),
            建三个 GVL:GVL_Param / GVL_WH / GVL_Visu,分别粘贴对应段落
   注意:参数与 Python 仿真 sim/warehouse_sim.py 顶部常量一一对应,
        改任何一边必须同步另一边并重跑一致性向量(README_PLC.md 流程)
   ============================================================ *)

(* ---------- GVL_Param:场景与算法参数 ---------- *)
VAR_GLOBAL CONSTANT
    COLS        : INT  := 20;       // 列数(A1)
    TIERS       : INT  := 20;       // 层数(A1)
    MAX_GOODS   : INT  := 400;      // 货物数组上限(=仓位总数)
    CELL_W      : REAL := 1.0;      // 仓位宽 m(A2)
    CELL_H      : REAL := 1.0;      // 仓位高 m(A2)
    BASE_CAP    : REAL := 100.0;    // 底层限重 kg(A6)
    CELL_VOL    : REAL := 1.0;      // 仓位容积 m3(B4)
END_VAR

VAR_GLOBAL
    // ---- 设备参数(A4;非常量:答辩时可现场演示灵敏度) ----
    rVx             : REAL := 2.0;      // 堆垛机水平速度 m/s
    rVy             : REAL := 0.5;      // 堆垛机垂直速度 m/s
    rTLoad          : REAL := 0.0;      // 装货时间 s(A8:暂不计,保留接口)
    rTUnload        : REAL := 0.0;      // 卸货时间 s(A8)
    xSimultaneousXY : BOOL := TRUE;     // TRUE=切比雪夫(主口径A5) FALSE=顺序模型(A9对照)
    // ---- L1 梯形速度曲线(A4b;与 Python ACCEL/AX/AY 一字对齐) ----
    xUseAccel       : BOOL := FALSE;    // FALSE=匀速(基础口径,历史数字) TRUE=加减速工程口径
    rAx             : REAL := 0.5;      // 水平加减速 m/s²
    rAy             : REAL := 0.3;      // 垂直加减速 m/s²

    // ---- 预占用规则(B1 题面歧义,三解读可切) ----
    iPreRule        : INT := 0;         // 0=x且y被3整除(49格) 1=或(231格) 2=线性编号(134格)

    // ---- 多目标评分权重(canonical E,HMI 可调,默认=Python 标定值) ----
    rAlpha          : REAL := 1.0;      // 效率项:频次*时间
    rBeta           : REAL := 0.6;      // 稳定项:重量*层高
    rGamma          : REAL := 0.4;      // 能耗项:提升做功
    rDelta          : REAL := 0.15;     // 位置价值预留项(δ=0会退化成就近贪心,实验发现F2)

    // ---- AWRA-LS Rank 权重(canonical E) ----
    rLambda1        : REAL := 0.50;     // 频次优先
    rLambda2        : REAL := 0.35;     // 重量优先(紧库存下保证重货有低层位,实验发现F3)
    rLambda3        : REAL := 0.15;     // 体积优先

    // ---- 扫描周期分片参数(非阻塞设计:单周期计算量受控,防看门狗超时) ----
    nBatchPerCycle  : INT := 10;        // 分配阶段:每扫描周期处理货物件数
    nPairsPerCycle  : INT := 200;       // 局部搜索:每扫描周期评估交换对数
    nMaxLsRounds    : INT := 5;         // 局部搜索最大轮数(120件实测2-3轮收敛)
END_VAR

(* ---------- GVL_WH:仓库与货物运行数据 ---------- *)
VAR_GLOBAL
    aSlots      : ARRAY[0..19, 0..19] OF ST_Slot;   // [列,层]
    aGoods      : ARRAY[1..400] OF ST_Good;          // 货物表(1..iGoodsCount 有效)
    iGoodsCount : INT := 0;                          // 当前货物数
    aRankIdx    : ARRAY[1..400] OF INT;              // Rank阶段排序后的货物下标
    stStats     : ST_Stats;                          // 统计结果
END_VAR

(* ---------- GVL_Visu:可视化接口(决赛 CODESYS Visualization 绑定这里) ----------
   资料包 §10.2 结构,状态编码:
   0=空闲(浅灰) 1=预占用(深灰) 2=已占用(绿) 3=当前推荐(黄) 4=路径(蓝) 5=报警(红) *)
VAR_GLOBAL
    VisuSlotState   : ARRAY[0..19, 0..19] OF INT;
    VisuCurrentX    : INT;                  // 堆垛机当前位置(演示动画用)
    VisuCurrentY    : INT;
    VisuTargetX     : INT;                  // 当前目标仓位
    VisuTargetY     : INT;
    VisuPathX       : ARRAY[0..39] OF INT;  // 当前路径点序列(L形:先水平后垂直展开)
    VisuPathY       : ARRAY[0..39] OF INT;
    VisuPathCount   : INT;
    VisuPathLen     : REAL;                 // 当前路径长度 m(曼哈顿,口径C2)
    VisuExecTime    : REAL;                 // 当前执行时间 s(切比雪夫,口径C2)
    VisuStatusText  : STRING[128];          // 状态/报警文本
    // ---- 统计面板(FB_Stats 写入) ----
    VisuTotalTime          : REAL;          // 完成全部存储总时间 s(双程,C1)
    VisuAvgTime            : REAL;          // 平均单件时间 s
    VisuSpaceUtilization   : REAL;          // 空间利用率(C7)
    VisuWearIndex          : REAL;          // 设备损耗代理=路径总长 m(C5)
    VisuViolationCount     : INT;           // 违规数(C8,恒0)
    // ---- 输入区(HMI 交互:决赛"可通过交互界面输入货物属性"要求) ----
    InGoodId        : INT;
    InGoodName      : STRING[32];
    InGoodWeight    : REAL;
    InGoodFreq      : REAL;
    InGoodVolume    : REAL;
    CmdAddGood      : BOOL;                 // 按钮:添加单件货物
    CmdLoadDemo     : BOOL;                 // 按钮:载入演示批次(Python seed=2026 导出)
    CmdRunAssign    : BOOL;                 // 按钮:运行批量分配(AWRA-LS)
    CmdReset        : BOOL;                 // 按钮:复位重来
    SelStrategy     : INT := 2;             // 策略选择 0=seq 1=near 2=score(在线) 3=AWRA-LS(批量)
END_VAR
