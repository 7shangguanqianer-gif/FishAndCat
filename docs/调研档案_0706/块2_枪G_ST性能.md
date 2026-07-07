No new load-bearing facts beyond what's confirmed. Compiling final answer.

# ST 大数组与算法性能——调研结果

## 1. 400 元素数组遍历 / 200×400 嵌套循环对扫描周期的影响量级

- **无具体量级实测数据(未找到)**。多个来源(CODESYS Forge、PLCtalk)反复确认"FOR/WHILE 循环处理不当会导致 jitter、消耗过多 CPU 周期",但均未给出 400 元素规模的具体微秒/毫秒数字。[可信度:摘要级,量级数字缺失]
  - Sources: [CODESYS Forge 讨论](https://forge.codesys.com/forge/talk/Engineering/thread/21322e0d96/), [PLCtalk 循环讨论](https://www.plctalk.net/forums/threads/the-fear-of-for-to-and-while-loops.122448/)
- CODESYS 循环任务默认周期为 **20ms**(可调)。[可信度:摘要级,来自 CODESYS 帮助文档二手转述,建议自行核对 Task Configuration 页面原文]
  - Source: [Task Configuration](https://content.helpme-codesys.com/en/CODESYS%20Development%20System/_cds_f_task_configuration.html)
- 明确惯例:**常量起止边界的 FOR 循环**不会引入 jitter;**变量边界**的循环才会引入不确定性。建议在循环前检查边界。[可信度:摘要级,多来源一致]
  - Sources: [ControlByte blog](https://controlbyte.tech/blog/codesys-program-flow-control-if-case-and-loops/), [RealPars](https://www.realpars.com/blog/codesys-plc-programming)
- **未找到**任何 200×400(8万次)嵌套循环在 AC500 级 PLC 上的实测扫描周期增量数据(无论官方还是第三方)。这一点需要自行在目标硬件上实测(建议:用 `TIME()` 或 CmpIecTask 相关 API 打点测量,见下方状态机资料)。

**状态机分片(state machine slicing)惯例:**
- 惯用模式:用 CASE 语句实现状态机,每个 PLC 扫描周期只处理循环的一部分(如固定数量的索引/元素),索引变量作为 FB 的静态/持久变量保存进度,下个周期从上次位置继续。这是行业通用做法,但**未找到官方 CODESYS/PLCopen 发布的"标准分片模式"完整示例代码**,只有社区文章描述了该模式的概念。[可信度:摘要级——概念确认,但没有可直接引用的官方"标准"代码]
  - Sources: [Stefan Henneken - IEC 61131-3 State Pattern](https://stefanhenneken.net/2018/11/17/iec-61131-3-the-state-pattern/), [FB_CaseStateMachine (GitHub)](https://github.com/FellowWithLaptop/FB_CaseStateMachine), [HEMELIX 状态机文章](https://www.hemelix.com/plc/state-machine-in-structured-text/)
- 官方最佳实践建议(非分片本身,而是规避长循环风险):**不要在循环体(周期同步执行)中直接跑 FOR/WHILE**,应将耗时计算放到**低优先级独立任务**,以事件方式异步触发+回调获取结果。[可信度:摘要级]
  - Source: [PLCtalk 循环讨论](https://www.plctalk.net/forums/threads/the-fear-of-for-to-and-while-loops.122448/)

## 2. PLC 上 200 元素排序——算法选择与性能数据

- IEC 61131-3 / CODESYS **标准库确实不含排序函数**(TwinCAT 默认库同样没有),需自行实现。多来源明确说明这是行业通识,非某个厂商的特例缺陷。[可信度:摘要级,多来源一致]
  - Source: [PLCCoder.com](https://www.plccoder.com/code-jam-with-st/)
- **未找到 PLCopen 官方排序函数库**。搜索 plcopen.org 相关结果只涉及运动控制(Motion Control)、安全(Safety)、通信类 function block 标准,没有排序相关的标准或库。[可信度:较高——多次搜索交叉验证均无结果,判定为"确实不存在官方 PLCopen 排序库",而非搜索遗漏]
  - Source: [PLCopen Downloads](https://www.plcopen.org/downloads/), [PLCopen Standards](https://www.plcopen.org/standards/)
- **未找到**任何厂商(Beckhoff/Schneider/ABB/Siemens)官方发布的"排序函数块库"。
- **未找到**插入排序/冒泡/希尔排序在 200 元素规模下、PLC 平台上的具体基准性能数据(毫秒级实测)。仅有通用计算机科学层面的结论(希尔排序对 100 条记录规模已明显优于 O(n²) 排序),**该结论来自桌面/服务器 CPU 场景,非 PLC 环境**,不能直接照搬到 PLC 扫描周期估算。[可信度:已核对——结论来源与场景不匹配,需自行在 AC500 上实测]
  - Source: [OpenDSA 排序算法实证比较](https://opendsa-server.cs.vt.edu/ODSA/Books/Everything/html/SortingEmpirical.html)

**结论:** 排序算法选择(插入 vs 希尔)在 200 元素规模下,教科书级 CS 结论支持希尔排序优于纯插入/冒泡,但没有 PLC 平台特定验证数据支撑——这是个需要自行在 AC500 上做基准测试的空白点,不要假设可以直接套用桌面 CPU 的结论(PLC 时钟频率、无分支预测优化、ST 编译器优化水平都可能不同)。

## 3. REAL vs INT/DINT 运算相对成本

- 有一个**具体量化数据但来自 Rockwell ControlLogix 平台,非 AC500**:REAL 类型的 ADD 运算耗时约为 DINT 的 **6.5 倍**。[可信度:摘要级,二手转述,且平台不匹配——ControlLogix 用的是 Rockwell 专有运行时,AC500 是 CODESYS 内核,不能直接套用这个倍数]
  - Source: [Industrial Monitor Direct - Floating Point vs Fixed Point](https://industrialmonitordirect.com/blogs/knowledgebase/floating-point-vs-fixed-point-in-plc-programming-complete-guide)
- 一般性说法:"现代 32 位 PLC 上 DINT 运算不比 INT 慢""现代 PLC 普遍带硬件 FPU,REAL 处理效率高"。**但未找到 AC500(基于其 CPU 型号,如 PM5xx/PM6xx 系列 ARM/x86 内核)具体是否带硬件 FPU 的确认信息**,这是需要单独查 ABB AC500 CPU 硬件规格书的点。
- 关于是否该做**定点化(缩放整数)**:找到的建议**恰好相反**于"惯例是定点化"的预设——多个来源建议"模拟量缩放场景直接用 REAL 算、存 REAL,定点整数写法会让代码变得不透明,精度收益通常不值得维护成本"。[可信度:摘要级,但方向明确、多来源未见反例]
  - Source: [Control.com - Understanding Floating Point Numbers in PLC](https://control.com/technical-articles/floating-point-numbers-in-plc-programming/)

**结论:** "定点化是惯例"这一假设在我的搜索中**没有得到支持**,反而找到相反建议。如果 AC500 确认带硬件 FPU(需另查硬件手册),REAL 运算在现代 32 位 PLC 上性能损失可能不足以抵消定点化带来的代码复杂度/可维护性代价。是否定点化应该基于 AC500 实际 CPU 型号的 FPU 情况和实测数据决定,而非行业惯例假设。

## 4. CODESYS 任务看门狗默认行为

- **触发条件:** 任务实际执行时间超过设定的看门狗时间(watchdog time)时触发;另有 "Omitted Cycle" 看门狗,在任务本该启动却未启动时触发。[可信度:摘要级]
- **默认行为:** 超时后**该任务被挂起(suspended)**,以防止控制器/任务卡死。其他任务可能仍在运行,但可视化(visualization)等可能失效。[可信度:摘要级,来自 CODESYS Forge 用户讨论 + 官方文档转述,建议原文核对 sensitivity 参数细节]
  - Sources: [CODESYS Forge - Handle watchdog timeout](https://forge.codesys.com/forge/talk/Engineering/thread/1051f7ec6a/), [Task Configuration 官方页](https://content.helpme-codesys.com/en/CODESYS%20Development%20System/_cds_obj_task_configuration.html)
- **配置方式:**
  - Task Configuration 中有 "sensitivity" 参数,决定看门狗超时可以被触发前允许超限的次数。[可信度:摘要级]
  - 可通过 **`CmpIecTask` 库**的 `IecTaskDisableWatchdog` / `IecTaskEnableWatchdog` 函数在代码中临时禁用/启用看门狗(常用于初始化等确实需要更长时间的周期)。关键细节:
    - `IecTaskDisableWatchdog` **仅对当前周期**生效;
    - `IecTaskEnableWatchdog` **要到下一个 IEC 周期才生效**,并非调用后立即生效;
    - 若禁用后忘记重新启用,**下一周期会自动重新启用**看门狗(不会永久失效)。
    - 用法示例: `hIecTask := IecTaskGetCurrent(0); IecTaskDisableWatchdog(hIecTask); ... IecTaskEnableWatchdog(hIecTask);` [可信度:已核对——直接来自 Schneider Electric 官方 CmpIecTask 文档页,函数名与参数描述具体明确]
  - Sources: [IecTaskDisableWatchdog (FUN) - Schneider 官方文档](https://product-help.schneider-electric.com/Machine%20Expert/V1.1/en/CmpIecTask/topics/iectaskdisablewatchdog.htm), [IecTaskEnableWatchdog (FUN)](https://product-help.schneider-electric.com/Machine%20Expert/V1.1/en/CmpIecTask/topics/iectaskenablewatchdog.htm), [CmpIecTask Library 文档索引](https://content.helpme-codesys.com/en/libs/CmpIecTask/Current/index.html)
  - 也可以通过 Task Configuration 配置**异常处理程序(exception handler)**捕获看门狗超时事件,自行设置全局变量标志、触发报警等自定义响应逻辑。[可信度:摘要级]
- **未找到 AC500 上看门狗的默认具体数值**(是否与通用 CODESYS 默认值一致、ABB 是否有自己的出厂预设),需要在 Automation Builder 的 Task Configuration 界面直接查看/实测确认。

---

## 汇总:关键空白与建议自测项

| 问题 | 状态 | 建议行动 |
|---|---|---|
| 200×400 嵌套循环在 AC500 上的实际耗时 | 未找到任何量级数据 | 自行用 `TIME()` 打点,在 Automation Builder 里跑一次实测,这是唯一可靠数据源 |
| PLCopen/厂商官方排序库 | 确认不存在 | 自行实现,选希尔排序(比插入/冒泡更优,但仍需 PLC 端实测验证) |
| AC500 CPU 是否带硬件 FPU | 未找到 | 查 AC500 目标 CPU 型号(如 PM573/PM590 等)的硬件数据手册 |
| AC500 看门狗默认时间值 | 未找到具体数值 | 直接在 Automation Builder Task Configuration 界面查看 |
| "定点化是惯例"假设 | 证据方向相反 | 不要预设需要定点化;先测 REAL 在 AC500 上的真实开销,再决定 |

举一反三:这类"PLC 上跑重计算"的调研普遍存在同一个坑——网上大量通用 PLC/CS 领域的经验法则,但几乎没有特定厂商特定 CPU 型号的量化数据,最终都要落到你自己在目标硬件上打点实测这一步,调研只能帮你排除明显错误方向、缩小实验设计范围。