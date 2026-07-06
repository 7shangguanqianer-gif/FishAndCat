(* ============================================================
   09_FB_ScanLoadProbeNs_备用.st — L4 兜底探针(候选③:SysTime 库时钟源)
   ⚠️ 备用件:仅当信箱批次 0705-B 的任务监视页读数也恒为 0 时才导入,平时不进工程。

   为什么要有它(root cause 记录):
   FB_ScanLoadProbe 用 LTIME() 差分,在 AB 仿真中恒为 0。最可能根因不是"分辨率不够",
   而是 **IEC 时间函数在一个扫描周期内返回缓存值**(任务开始时取一次,周期内不变)——
   若如此,"累计窗口摊薄法"(原候选②)同样无效:窗口内累加的每段差分仍是 0。
   兜底必须换时钟源:SysTime 库的 SysTimeGetNs/SysTimeGetUs 直接调操作系统计时器,
   不走 IEC 周期缓存。故候选顺序修订为 ①任务监视页 → ③本文件 → ④真机。

   导入方法(仅在需要时):
   1. AB 里 Application 下 Library Manager(库管理器)→ Add Library(添加库)→
      搜索 "SysTime"(SysTime, System 分类)→ 添加。找不到该库 → 停,截图汇报。
   2. 添加 POU-功能块 FB_ScanLoadProbeNs,粘贴本文件下方代码。
   3. 编译若报 SysTimeGetNs 参数名不符:在实现区把 SysTimeGetNs( 重新输入,
      按 AB 输入助手(F2)提示的形参名改(不同版本形参名可能是 pTimeNs/pUsTime 等,
      功能相同:把当前纳秒计数写进传入变量)。改完把实际形参名写进汇报。
   4. PLC_PRG 接线与原探针完全相同(fbProbeNs 换名即可),接口刻意保持一致。
   ============================================================ *)

FUNCTION_BLOCK FB_ScanLoadProbeNs
VAR_INPUT
    xStart : BOOL;              // 段前置 TRUE
    xStop  : BOOL;              // 段后置 TRUE
END_VAR
VAR_OUTPUT
    rLastUs : REAL;             // 最近一次段耗时 µs
    rAvgUs  : REAL;
    rMaxUs  : REAL;
    nSamples: DINT;
END_VAR
VAR
    tT0     : SYSTIME;          // 段前时刻 ns(SYSTIME=ULINT,SysTime 库定义)
    tT1     : SYSTIME;          // 段后时刻 ns
    xArmed  : BOOL;             // 已记录段前时刻,等待段后
    rSumUs  : LREAL;            // 累计和用 LREAL,防长跑精度丢失
    rDiffUs : REAL;
END_VAR

// 段前:取一次系统纳秒计数(直连 OS 计时器,不受 IEC 周期缓存影响)
IF xStart AND NOT xArmed THEN
    SysTimeGetNs(tT0);   // 位置传参,规避各版本形参名差异(0706 实测 3.5.17 无 pTimeNs)
    xArmed := TRUE;
END_IF

// 段后:再取一次,差分入统计
IF xStop AND xArmed THEN
    SysTimeGetNs(tT1);
    xArmed := FALSE;
    IF tT1 >= tT0 THEN                               // 防计数器回绕的负差
        rDiffUs := ULINT_TO_REAL(tT1 - tT0) / 1000.0;   // ns → µs
        rLastUs := rDiffUs;
        nSamples := nSamples + 1;
        rSumUs := rSumUs + REAL_TO_LREAL(rDiffUs);
        rAvgUs := LREAL_TO_REAL(rSumUs / DINT_TO_LREAL(nSamples));
        IF rDiffUs > rMaxUs THEN rMaxUs := rDiffUs; END_IF
    END_IF
END_IF
END_FUNCTION_BLOCK
