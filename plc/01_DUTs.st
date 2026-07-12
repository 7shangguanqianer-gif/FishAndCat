(* ============================================================
   01_DUTs.st — 数据类型定义(DUT)
   项目:智储优控 · 立体仓储仓位优化(2026 ABB杯 赛道一)
   目标平台:ABB AC500 V3(CODESYS V3.5 内核),ST 语言
   导入方法:Automation Builder 中 Application 右键 → 添加对象 → DUT,
            每个 TYPE 建一个 DUT,粘贴对应段落(详见 README_PLC.md)
   口径依据:docs/canonical_assumptions.md(A1-A9/B1-B5/C1-C8)
   ============================================================ *)

(* ---------- ST_Good:货物(题面五元组 + 分配结果字段) ---------- *)
TYPE ST_Good :
STRUCT
    Id          : INT;          // 序号(题面属性1)
    Name        : STRING[32];   // 名称(题面属性2)
    Weight      : REAL;         // 重量 kg(题面属性3)
    Freq        : REAL;         // 访问频次(题面属性4)
    Volume      : REAL;         // 体积 m3(题面属性5)
    Priority    : REAL;         // Rank阶段优先级(λ1*频次+λ2*重量+λ3*体积,归一后)
    Assigned    : BOOL;         // 是否已分配
    X           : INT;          // 分配结果:列(0..19,水平)
    Y           : INT;          // 分配结果:层(0..19,垂直,0=底层)
    Score       : REAL;         // 分配时的多目标评分
    PathLength  : REAL;         // 单程曼哈顿路径长度 m(口径C2)
    ExecTime    : REAL;         // 单程切比雪夫行程时间 s(口径C2)
END_STRUCT
END_TYPE

(* ---------- ST_Slot:仓位 ---------- *)
TYPE ST_Slot :
STRUCT
    X           : INT;          // 列 0..19
    Y           : INT;          // 层 0..19(0=底层)
    Occupied    : BOOL;         // 已占用(含预占用)
    PresetOcc   : BOOL;         // 预占用(题面:坐标能被3整除,解读见 FC_IsPresetOccupied)
    CapCoef     : REAL;         // 承重系数 = 1.0 - 0.02*Y(题面给定)
    MaxWeight   : REAL;         // 限重 = CapCoef * BASE_CAP(口径A6)
    MaxVolume   : REAL;         // 容积上限 = CELL_VOL(口径B4)
    GoodsId     : INT;          // 存放的货物Id,0=无
END_STRUCT
END_TYPE

(* ---------- ST_Stats:统计信息(决赛可视化统计栏数据源) ---------- *)
TYPE ST_Stats :
STRUCT
    PlacedCnt      : INT;       // 成功入库件数
    FailedCnt      : INT;       // 无可行位件数(边界:必须可见可报警)
    TotalTime2Way  : REAL;      // 入库总时间 s,双程口径(C1)
    AvgTime        : REAL;      // 平均单件双程时间 s
    ExpRetrieval   : REAL;      // 期望取货时间 s,频次加权单程(C3)
    Energy         : REAL;      // 能耗代理 Σ重量*高度 kg·m(C4)
    CogHeight      : REAL;      // 载荷重心高度 m(C6)
    PathTotal2Way  : REAL;      // 路径总长 m,双程曼哈顿(C5 损耗代理)
    UtilPct        : REAL;      // 空间利用率 =已占/400(C7,含预占)
    ViolCnt        : INT;       // 约束违规数,必须恒为0(C8;0712 轨B N4-20 扩为一致性扫描)
    SwapCnt        : DINT;      // 局部搜索接受的成对交换次数(0712 轨B N5-06 正名/N5-10 加宽;
                                //   批统计,批开工与 Reset 双清零=N5-05)
    RelocCnt       : DINT;      // 局部搜索接受的重定位次数(0712 轨B N5-06 新增,与 SwapCnt 分列)
    LsRounds       : INT;       // 局部搜索实际轮数(≤nMaxLsRounds,INT 足)
END_STRUCT
END_TYPE

(* ---------- E_MainState:主程序状态机 ---------- *)
TYPE E_MainState :
(
    STATE_IDLE       := 0,      // 待机
    STATE_INIT       := 10,     // 初始化仓库(预占用/承重)
    STATE_WAIT_INPUT := 20,     // 等待交互输入货物 / 载入演示批次
    STATE_ASSIGN     := 30,     // 批量分配运行中(分片,跨扫描周期)
    STATE_IMPROVE    := 40,     // 局部搜索改进中(分片,跨扫描周期)
    STATE_STATS      := 50,     // 统计计算
    STATE_DONE       := 60,     // 完成,结果可视化
    STATE_FAULT      := 70      // 故障(输入非法/无可行位等,看 GVL_Visu.StatusText)
);
END_TYPE
