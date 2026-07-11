(* ============================================================
   crane_3boxes.st — 三课·第二课教具②:堆垛机按序入库 3 箱
   目标:用最小状态机把 3 个货箱依次送进 3 个不同格位——
        这是主线 ST(400 库位分配)在“带物理引擎的世界”里的微缩证据,
        录屏进决赛展望「孪生成熟度阶梯」L2 实证层。
   Factory I/O 场景:Automated Warehouse(内置 54 格)或 Stacker Crane 单元。

   接口约定(FIO Stacker Crane 部件,tag 名以 FIO 驱动窗口实际显示为准;
   若你的版本 tag 不同,只改变量映射,状态机骨架不动——对不上喊 Codex 陪查):
     → iTargetPos  写目标格位编号(FIO “Target Position”,1..54;0=入库口/原位)
     → xLift       叉臂动作(FIO “Lift”:TRUE=托起/放下动作,随场景定义)
     ← xMovingX    水平移动中(FIO “Moving X”)
     ← xMovingZ    垂直移动中(FIO “Moving Z”)
     ← xAtLoad     入库口有箱(光电/“Box at load”类传感器)
   学生操作流程同 belt_stop.st(粘贴→Symbol Configuration→下载→OPC 映射→双 RUN)。

   验收:按 Start 后,3 个箱子被依次放进格位 5 / 18 / 31(三个不同巷道位置,
   演示“算法指定格位”而不是“就近乱放”);全程无手动干预。录 30 秒屏。
   ============================================================ *)
PROGRAM PLC_PRG
VAR
    // ---- 映射到 Factory I/O ----
    xStart     : BOOL;                  // ← Start 按钮
    xAtLoad    : BOOL;                  // ← 入库口有箱传感器
    xMovingX   : BOOL;                  // ← 堆垛机水平移动中
    xMovingZ   : BOOL;                  // ← 堆垛机垂直移动中
    iTargetPos : INT;                   // → 目标格位(0=回入库口)
    xLift      : BOOL;                  // → 叉臂动作
    // ---- 内部 ----
    iStep      : INT := 0;              // 状态机:0待命 10取箱 20去目标 30放箱 40回程 90完成
    iBoxIdx    : INT := 0;              // 已入库箱数(0..3)
    aSlot      : ARRAY[1..3] OF INT := [5, 18, 31];   // “算法给定”的三个目标格位
    xBusy      : BOOL;                  // 堆垛机在动(两轴任一)
    tonSettle  : TON;                   // 到位去抖:停稳 0.5s 才算到位
    tonAlarm   : TON;                   // 单步看门狗:20s 不完成=报警(演示防呆)
    xStepAlarm : BOOL;
END_VAR

xBusy := xMovingX OR xMovingZ;
tonSettle(IN := NOT xBusy, PT := T#500MS);          // 停稳计时
tonAlarm(IN := (iStep > 0) AND (iStep < 90), PT := T#20S);
IF tonAlarm.Q THEN                                   // 看门狗:卡步报警并回待命
    xStepAlarm := TRUE;
    iStep := 0;
END_IF

CASE iStep OF
    0:  // 待命:按 Start 且入库口有箱 → 开始
        xLift := FALSE;
        iTargetPos := 0;                             // 停在入库口
        IF xStart AND xAtLoad AND (iBoxIdx < 3) THEN
            xStepAlarm := FALSE;
            iStep := 10;
        END_IF

    10: // 取箱:在入库口做叉取动作(FIO 里 Lift 在 load 位=取箱)
        xLift := TRUE;
        IF tonSettle.Q THEN                          // 动作到位(停稳)
            iStep := 20;
        END_IF

    20: // 载箱去目标格:写目标位,等两轴到位停稳
        iTargetPos := aSlot[iBoxIdx + 1];
        IF xBusy THEN
            iStep := 25;                             // 确认已起动,再等停稳(防“还没动就误判到位”)
        END_IF
    25:
        IF tonSettle.Q THEN
            iStep := 30;
        END_IF

    30: // 放箱:叉臂收回(FIO 里 Lift 复位=放下)
        xLift := FALSE;
        IF tonSettle.Q THEN
            iBoxIdx := iBoxIdx + 1;
            iStep := 40;
        END_IF

    40: // 空载回入库口,准备下一箱
        iTargetPos := 0;
        IF xBusy THEN
            iStep := 45;
        END_IF
    45:
        IF tonSettle.Q THEN
            IF iBoxIdx >= 3 THEN
                iStep := 90;                         // 3 箱完成
            ELSE
                iStep := 0;                          // 等下一箱(xAtLoad)
            END_IF
        END_IF

    90: // 完成:驻留(重跑=FIO 复位场景 + 这里手动把 iBoxIdx/iStep 清零)
        ;
END_CASE
END_PROGRAM

(* 教学点(Codex 讲评提纲,对应主线 ST 的同款手法):
   1. 状态机(CASE)= 主线 05_PRG_Main 同构:每步只做一件事,完成条件明确;
   2. “先确认起动、再等停稳”(20→25)= 防抖两段式,主线 fbAssign 的 xBusy/xDone 同思想;
   3. TON 看门狗 = 任何真实设备控制都要的防卡步兜底;
   4. aSlot 数组 = “格位由算法给”:第三课 3a 就是把这 3 个数换成评分函数算出来的。
   常见坑:堆垛机不动=Target Position 没映射或量纲不对(有的版本按格号、有的按毫米);
   Lift 语义相反=把 10/30 两步的 TRUE/FALSE 互换。 *)
