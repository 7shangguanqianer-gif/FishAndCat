(* ============================================================
   belt_stop.st — 三课·第二课教具①:光电挡停传送带(10 行热身)
   目标:证明「CODESYS Control Win(软 PLC)→ OPC UA → Factory I/O」全链路通。
   Factory I/O 场景:From A to B(或任何“一条传送带+一个漫反射光电”的场景)。

   学生操作(亲手做,Codex 陪跑):
   1. CODESYS 新建标准工程(设备选 CODESYS Control Win V3 x64),POU 语言 ST;
   2. 把本文件的 VAR 段与逻辑段分别粘进 PLC_PRG 的声明区/实现区;
   3. 添加 Symbol Configuration(勾选 PLC_PRG 全部变量)→ 编译 → 下载 → RUN;
   4. Factory I/O:File→Drivers→OPC Client DA/UA→ 连本机 CODESYS,
      按下面注释把变量映射到场景部件(以 FIO 驱动窗口显示的实际 tag 为准);
   5. FIO 点 RUN(注意:FIO 的 RUN 和 CODESYS 的 RUN 是两个开关,都要开)。

   验收(教程口径):箱子走到光电前,传送带自动停;拿走箱子(FIO 里拖走
   或复位场景),按 Start 后带子再走。录 30 秒屏发回 Claude。
   ============================================================ *)
PROGRAM PLC_PRG
VAR
    // ---- 映射到 Factory I/O(名字→FIO 部件,方向以 PLC 视角) ----
    xSensor  : BOOL;    // ← FIO “Diffuse Sensor”(检测到箱子=TRUE)
    xStart   : BOOL;    // ← FIO “Start Button”(绿色,按下=TRUE)
    xStop    : BOOL;    // ← FIO “Stop Button”(红色,注意:FIO 惯例常闭,松开=TRUE、按下=FALSE)
    xBeltRun : BOOL;    // → FIO “Belt Conveyor”(TRUE=运转)
    // ---- 内部 ----
    xRun     : BOOL;    // 运行自保持
END_VAR

// 启停自保持:Start 置位;Stop(常闭断开)复位——工业启停最小骨架
IF xStart THEN
    xRun := TRUE;
END_IF
IF NOT xStop THEN                   // 常闭按钮:按下时信号变 FALSE
    xRun := FALSE;
END_IF

// 核心一行:运行中 且 光电没被挡住 → 带子转;箱子到位即停
xBeltRun := xRun AND NOT xSensor;
END_PROGRAM

(* 常见坑(卡住先看这里,再喊 Codex):
   1. 带子不转:FIO 是否 RUN?CODESYS 是否 RUN?两个开关缺一不可;
   2. 变量全灰/映射窗口空:Symbol Configuration 没下载——重新编译+下载;
   3. Stop 一按就永远停:你的场景 Stop 按钮可能是常开——把 NOT xStop 改成 xStop;
   4. 光电不变化:FIO 里传感器 tag 没映射到 xSensor,或映射了别的传感器。 *)
