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
    // ---- L6 可视化画面几何常量(单位 px;与 2_你要操作/AB可视化搭建操作卡 的元件坐标同源) ----
    GRID_X0     : INT := 40;        // 仓位网格左上角 X(左侧留层号标签)
    GRID_Y0     : INT := 40;        // 仓位网格左上角 Y(顶部留标题)
    CELL_PX_W   : INT := 28;        // 单格宽(20列=560px,网格右缘 x=600)
    CELL_PX_H   : INT := 20;        // 单格高(20层=400px,网格下缘 y=440)
    // ---- A4 两级权限(0711):演示 PIN,非真实凭据;变量层方案依据=内置 visu
    //      Access Rights 无 ScriptEngine 接口,无法被画面生成管线驱动(官方文档核实) ----
    ADMIN_PIN   : INT := 2026;      // 管理员登录码(演示口径;生产化换 visu UserMgmt)
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

    // ---- U2 载重运动学(块3 拟真调参区,画面可调;默认=canonical U2/sim 同值) ----
    // 消费者:FC_TravelLaden(垂直折减)/FC_HandleTime(装卸三档);不进现有评分/测试链路(零回归)
    rLadenFactorVY  : REAL := 0.80;     // 满载垂直速度折减(Mecalux 0.818 圆整,水平不折减=行业惯例)
    rHandleW1       : REAL := 30.0;     // 装卸档界1:轻货上限 kg
    rHandleW2       : REAL := 60.0;     // 装卸档界2:中货上限 kg(>W2 为重货)
    rHandleT1       : REAL := 6.0;      // 轻货装卸 s(单次货叉全循环)
    rHandleT2       : REAL := 8.5;      // 中货装卸 s
    rHandleT3       : REAL := 12.5;     // 重货装卸 s

    // ---- 预占用规则(B1;2026-07-06 官方答复后默认=3,四解读全保留可切) ----
    iPreRule        : INT := 3;         // 3=x+y被3整除(133格,官方口径) 0=且(49格) 1=或(231格) 2=线性(134格)

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
    // ---- A3 检修挂起(0711):独立于 aSlots 的物理状态层,Reset/重分配不清
    //      语义=SAP EWM bin blocking 的 putaway block:禁新入库(选位/分配/交换均排除),
    //      已有货物原地冻结、查询照常;非 RETAIN(断电清零=演示安全默认) ----
    aMaintBlock : ARRAY[0..19, 0..19] OF BOOL;       // TRUE=该格检修挂起
    // ---- C2/C6 热力图数据层(0711 批次前置令) ----
    aSlotFreq   : ARRAY[0..19, 0..19] OF REAL;       // C2:格上货物频次(布局态,fbInit 清)
    aSlotOps    : ARRAY[0..19, 0..19] OF UDINT;      // C6:布局操作/写入热图计数(放置/搬移/交换各+1;
                                                     //     Reset 不清;0712 轨B N5-09:INT→UDINT 防长跑溢出,
                                                     //     非 RETAIN=断电清零,故称"计数热图"勿称长期履历)
    // ---- 0712 轨B D-1:CB 分级存储辅助(FB_AssignClassTurnover 批开工构建,批内只读) ----
    aSlotOrder  : ARRAY[1..400] OF INT;              // 全库时间序表(编码 x*100+y;(travel,tier,col)升序)
    iCbClass    : ARRAY[1..400] OF INT;              // 货物类别 0/1/2=A/B/C(按货物下标索引)
    aCbStarts   : ARRAY[0..2] OF INT;                // 各类在"空闲格序"上的起点偏移(静态件数累计)
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
                                            //          4=CB 分级存储 5=TOB 全周转(0712 轨B D-1)
    SelObjective    : INT := 0;             // 检测器目标档 0=holistic(默认) 1=lexicographic(0712 轨B;
                                            //   演示"现场切词典序档"入口,P3 管理页开关绑定)
    // ---- L6 决赛画面增补(元件绑定方法见 2_你要操作/AB可视化搭建操作卡.md) ----
    VisuSlotColor   : ARRAY[0..19, 0..19] OF DWORD;
        // [列,显示行] 单元格填充色(16#00RRGGBB);显示行0=画面顶(=层19),
        // 上下翻转+状态→颜色查表由 FB_VisuRefresh 每周期重算——画面矩形阵列只绑这一个数组
    VisuCraneXpx    : INT;                  // 堆垛机图元 X 像素(FB_VisuRefresh 从 VisuCurrentX 换算)
    VisuCraneYpx    : INT;                  // 堆垛机图元 Y 像素(含上下翻转)
    VisuAlarm       : BOOL;                 // 报警灯:超重/负输入/无可行位=TRUE(演示第6步,红灯元件)
    CmdAnimate      : BOOL;                 // 按钮:堆垛机沿当前路径回放动画(FB_AnimatePath)
    // ---- 块3 P3 单件查询页(评分细则8"单件查询";FB_QueryGood 填充,状态6=青色高亮) ----
    InQueryId       : INT;                  // 查询输入:货物序号
    CmdQuery        : BOOL;                 // 按钮:执行查询
    QryFound        : BOOL;                 // 查到与否(FALSE 时下方字段无效)
    QryX            : INT;                  // 位置列
    QryY            : INT;                  // 位置层
    QryName         : STRING[32];
    QryWeight       : REAL;
    QryFreq         : REAL;
    QryVolume       : REAL;
    QryPathLen      : REAL;                 // 路径长度 m(曼哈顿,C2)
    QryExecTime     : REAL;                 // 行程时间 s(切比雪夫单程,存量口径)
    QryTravelLaden  : REAL;                 // 载货行程 s(垂直×rLadenFactorVY,U2 拟真对照)
    QryHandleT      : REAL;                 // 单次装卸 s(三档,U2)——调参区改档界/时长此值实时变
    // ---- 块3 P2 统计记录页(评分细则8;FB_RecordPage 10 行窗口映射,禁 400 行整表压渲染) ----
    iRecTop         : INT;                  // 窗口顶行(1 基,指向 aGoods 下标)
    CmdPageUp       : BOOL;                 // 按钮:上翻 10 行
    CmdPageDown     : BOOL;                 // 按钮:下翻 10 行
    iRecTotal       : INT;                  // 总行数(=iGoodsCount,表头"共 N 件"用)
    aRowId          : ARRAY[0..9] OF INT;   // 10 行窗口:序号(0=空行)
    aRowX           : ARRAY[0..9] OF INT;   // 位置列(未分配=-1)
    aRowY           : ARRAY[0..9] OF INT;   // 位置层
    aRowPathLen     : ARRAY[0..9] OF REAL;  // 路径长度 m
    aRowExecT       : ARRAY[0..9] OF REAL;  // 行程时间 s
    // ---- 块3 快照对比(方向9:一键切换"优化前 vs 优化后",D 档叙事) ----
    CmdSaveSnap     : BOOL;                 // 按钮:把当前布局存为对比基准(如 seq 基线)
    CmdCompareMode  : BOOL;                 // 开关:TRUE=显示快照 FALSE=显示实时(FB_VisuRefresh 选源)
    xSnapValid      : BOOL;                 // 已存过快照(未存时 CompareMode 无效,防显示垃圾)
    aSnapState      : ARRAY[0..19, 0..19] OF INT;  // 快照:VisuSlotState 的冻结副本
    // ---- 块3 名称下拉+手输(ComboBox Array 写 INT 下标,PRG 同步回 InGoodName) ----
    iNameSel        : INT := -1;            // ComboBox 选中下标(-1=未选,手输优先)
    astrNames       : ARRAY[0..9] OF STRING[32] :=
        ['BEARING','MOTOR','GEARBOX','VALVE','PUMP','SENSOR','CABLE','PANEL','FILTER','RELAY'];
        // 常用货物名(ASCII,C0555 规避;演示可选,亦可 Keypad 手输)
    // ---- 块3 画面排版 B(0710):装饰/图例常量——脚本设不了静态填色(0710 实证),
    //      全部走已验证的 Color variables 动态通道;RGBA 前导 FF=不透明,00=全透明 ----
    dwCraneColor    : DWORD := 16#FFFF6D00;         // 堆垛机橙
    dwTransparent   : DWORD := 16#00FFFFFF;         // 全透明填充(分组框矩形只显边线,不盖内容)
    dwHeaderBg      : DWORD := 16#FFE8EAF0;         // P2 记录表表头底纹(版1 排版,0711)
    aLegendColor    : ARRAY[0..7] OF DWORD :=       // 图例色样,与 FC_StateToColor 状态 0..7 一致
        [16#FFE8E8E8, 16#FF707070, 16#FF43A047, 16#FFFFC107,
         16#FF42A5F5, 16#FFE53935, 16#FF26C6DA, 16#FF8E24AA];
    // ---- A2 场景检测器(0711 驾驶舱连击:批次画像→推荐策略;FB_SceneDetect 填充) ----
    VisuProfN       : INT;                  // 画像:批量大小
    VisuProfDensity : REAL;                 // 画像:密度 n/267(sum 口径可用位)
    VisuProfSkew    : REAL;                 // 画像:频次偏斜度(top20% 件频次占比)
    VisuProfWMean   : REAL;                 // 画像:重量均值 kg
    VisuProfWHeavy  : REAL;                 // 画像:重货(>60kg)占比
    VisuRecStrategy : INT := -1;            // 推荐策略档位(SelStrategy 语义;-1=无数据)
    VisuRecText     : STRING[64];           // 推荐文本(ASCII 状态码,画面静态中文标签对照)
    xAutoStrategy   : BOOL := FALSE;        // 开关:TRUE=推荐自动写入 SelStrategy(人工覆盖=关)
    // ---- A3 检修画面接口 ----
    InMaintX        : INT;                  // 检修目标列
    InMaintY        : INT;                  // 检修目标层
    CmdMaintToggle  : BOOL;                 // 按钮:挂起/恢复翻转(需管理员)
    VisuMaintCount  : INT;                  // 当前检修格数
    // ---- C1/C2/C6 视图层(0711 批次前置令:层高亮+双热力图,画面终局一次施工) ----
    iViewMode       : INT := 0;             // 0=状态视图 1=频次热力(C2) 2=损耗热力(C6)
    CmdViewCycle    : BOOL;                 // 按钮:视图循环切换(脉冲)
    InTierSel       : INT := -1;            // C1 层高亮选择(-1=关,0..19=该层加亮)
    VisuTierOcc     : INT;                  // C1:选中层的在货格数(FB_VisuRefresh 计)
    // ---- A4 两级权限画面接口(变量层双闸:画面元素锁定 + ST 侧参数守卫回滚) ----
    InPinCode       : INT;                  // 登录码输入(消费即清,画面不放回显元件)
    CmdLogin        : BOOL;                 // 按钮:登录
    CmdLogout       : BOOL;                 // 按钮:登出
    iUserLevel      : INT := 0;             // 0=操作员 1=管理员(画面锁定绑定源;非 RETAIN)
    VisuUserText    : STRING[32];           // 'USER=OPERATOR' / 'USER=ADMIN' / 'LOGIN_FAIL'
END_VAR
