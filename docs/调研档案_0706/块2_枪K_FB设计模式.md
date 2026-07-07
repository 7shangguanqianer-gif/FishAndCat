Good — this gives a concrete OSCAT array-function interface pattern (ADR+SIZEOF or VAR_IN_OUT). Enough material collected. Compiling final output.

```
调研结果：功能块接口设计模式（PLCopen Execute/Done/Busy/Error/ErrorID、VAR_IN_OUT、算法类FB范例）

【1. PLCopen Execute/Done/Busy/Error/ErrorID 接口模式——是否事实标准，是否适用算法类FB】

- 一手规范：PLCopen "Function Blocks for Motion Control – Part 1" v2.0
  https://plcopen.org/system/files/downloads/plcopen_motion_control_part_1_version_2.0.pdf
  可信度：摘要级（PDF为图像/二进制流，WebFetch无法提取文本，未能逐字核对原文；内容来自搜索引擎摘要+其他信息源交叉印证）
  要点：
  - Busy/Done/Error/CommandAborted 四个输出互斥，同一时刻只能有一个为TRUE；Execute为TRUE时必须有一个输出为TRUE。
  - Execute为FALSE→TRUE的上升沿触发命令，且只有当Busy=FALSE时才能被新的上升沿再次触发。
  - Execute下降沿会复位 Done/Error/ErrorID/Busy（前提是FB当前不是"active"状态）；若命令执行中Execute提前变FALSE，输出会保持到命令完成，以保证至少一个扫描周期内呈现有效状态。
  - MC_Stop 有特例：Done=TRUE时 Busy/Active 仍保持TRUE，直到Execute被复位为止。

- 关键结论——是否为"事实标准"且可推广到非运动控制FB：
  来源：ControlDesign《How to create PLCopen-compliant function blocks》(2017)
  https://www.controldesign.com/articles/2017/how-to-create-plcopen-compliant-function-blocks/
  可信度：摘要级（WebFetch实际抓取到文章正文并做了引用式提炼，非逐字复制，但信息源可信——该文由PLCopen官方相关渠道撰写/引用官方指南）
  原文要点（转述）：
  - PLCopen 官方定义了两大类FB模型："Execute model"（边沿触发）和"Enable model"（电平触发），目的就是"extend these to fit other application areas, and helping users to specify and implement consistent sets of FB libraries for their own usage"——即官方明确说这套模式设计初衷就是给用户（机器制造商、系统集成商）复用到自己的FB库，不限于运动控制。
  - PLCopen 已经把这套模式用到"motion control, safety and communication"等多个应用领域，作为可复用FB库设计的通用基础模式。
  - 结论：这确实是IEC 61131-3生态里事实上的FB接口设计惯例（尤其在CODESYS/TwinCAT系工具链中被广泛采用），但它源自"运动控制"规范、后被PLCopen官方声明推广为通用惯例——不是IEC 61131-3标准本身强制规定的语法，而是行业惯例/最佳实践。适用于算法类FB是官方认可的推广用法，但你在评审稿里应说明"借鉴PLCopen通用FB模式"而非"运动控制标准"，避免误导评委以为你用了运动控制功能。

【2. 长任务FB启动握手：Execute边沿 vs Enable电平】

- 来源同上（Beckhoff infosys 官方文档 + ControlDesign文章）
  https://infosys.beckhoff.com/content/1033/tcplclib_tc2_mc2/70043531.html （Beckhoff对PLCopen通用规则的官方实现说明，可信度：已核对原文，WebFetch抓取到完整正文）
  https://www.controldesign.com/articles/2017/how-to-create-plcopen-compliant-function-blocks/ （可信度：摘要级）

  原文要点：
  - Execute模型（边沿触发）："those that are initialized (started) at a rising input and stay active until finalized or aborted"——适合"启动一次、跑到完成"的长任务，比如你的批量分配算法（一次Execute触发，跑若干扫描周期直到Done/Error）。
  - Enable模型（电平触发）："those that are active as long as the corresponding input is high"——适合"每周期都要处理新值"的场景："if the requirement is to be able to process a new value in each cycle, an edge-triggered model cannot serve as a solution"。
  - 边沿检测本身需要至少2个PLC扫描周期（因为需要记住上一周期状态做比较）。
  - 结论：你的批量分配算法（读一次200件货清单，跑一次排序+局部搜索，可能跨多个扫描周期完成）属于典型"长任务"场景，应该用 Execute（边沿触发）模型，而不是 Enable（电平触发）——这与直觉一致：Execute+Busy+Done+Error+ErrorID 组合，Busy期间FB内部维护状态机分步执行（比如本周期处理10件、下周期再处理10件，避免看门狗超时）。

【3. VAR_IN_OUT 用于大数组传递——CODESYS官方说明】

- 一手来源：CODESYS官方帮助文档 "Variable: VAR_IN_OUT"
  https://content.helpme-codesys.com/en/CODESYS%20Development%20System/_cds_vartypes_var_in_out.html
  可信度：已核对原文（WebFetch成功抓取正文并逐句引用）

  原文要点（英文原文转述）：
  - VAR_IN_OUT 是"formal pass-by-reference parameter"，属于POU接口的一部分。
  - 关键收益（避免拷贝）："At runtime, no copies are generated when parameters are passed. Instead, the formal variable receives a reference to the actual variable passed remotely."——这正是你200件货数组传递需要的：避免每次调用FB都拷贝整个数组，直接传引用。
  - 可读可写：FB内部对VAR_IN_OUT的修改会直接影响调用方原变量（实参），FB退出后修改依然生效——这也符合"原地排序/原地局部搜索"的需求（不需要额外OUTPUT数组把结果拷贝回去）。
  - 限制：
    1. VAR_IN_OUT 不能像VAR_INPUT/VAR_OUTPUT那样通过 `<FB实例名>.<变量名>` 远程读写。
    2. 不能直接传常量/字面量作为实参。
    3. 传STRING时，实参和形参长度建议一致，否则可能被意外篡改。
    4. 位变量（BOOL等bit类型）不能直接作为VAR_IN_OUT实参，需要中间变量。
  - 另有CODESYS论坛佐证（可信度：摘要级，未逐字核对）：FB接口的VAR_IN_OUT可声明变长数组（`ARRAY[*] OF ...`），配合 `LOWER_BOUND`/`UPPER_BOUND` 算子在运行时确定实际数组边界——这对你"200件货，但库位20x20=400"这种规模可变的场景有直接参考价值，可以设计成通用FB处理任意数量的待分配货物，而非硬编码200。
    来源：CODESYS Forge 论坛帖 https://forge.codesys.com/forge/talk/CODESYS-V2/thread/d1ffb170a3/ 及 官方 "Data Type: ARRAY OF" 文档 https://content.helpme-codesys.com/en/CODESYS%20Development%20System/_cds_datatype_array.html

【4. 算法类FB（非运动控制）的公开设计范例】

- 范例：OSCAT Basic 库的数组处理函数/功能块（如 `_ARRAY_SORT`, `_ARRAY_MEDIAN`, `_ARRAY_INIT`, `_ARRAY_SHUFFLE` 等）
  可信度：摘要级（未能直接抓取PDF原文；oscat.de旧域名已重定向到 https://eclipse.dev/oscat，新文档搬到 oscat.readthedocs.io / oscat-basic.readthedocs.io，均未逐字核对，信息来自搜索引擎摘要+CODESYS论坛交叉印证）
  接口风格要点（转述，非逐字引用）：
  - 老版本（FUNCTION级，非FB）常用"指针+字节数"传参风格：`ARRAY_VAR(ADR(Array), SIZEOF(Array))`，即传数组首地址+SIZEOF，在内部按字节/类型大小遍历——这是IEC 61131-3早期（无VAR_IN_OUT数组语法支持时）的惯用做法，本质上和VAR_IN_OUT思路一致（避免拷贝），但更底层、类型不安全，现代CODESYS/TwinCAT一般不推荐新代码这样写。
  - 部分函数块用 VAR_IN_OUT 数组直接原地修改（如排序类），调用后"数组已经是排序好的状态"——即FB不返回新数组，而是通过VAR_IN_OUT原地改写传入数组，调用方直接读原数组即可，无需额外输出参数。
  - 未找到 OSCAT 是否对这类算法FB也套用了完整的Execute/Busy/Done/Error/ErrorID模式（未能获取PDF正文核实，需要人工下载 http://www.oscat.de/images/OSCATBasic/oscat_basic333_en.pdf 或访问 https://oscat-basic.readthedocs.io 核对具体FB声明代码）。

  来源列表：
  - https://forge.codesys.com/forge/talk/Engineering/thread/f6edee4d92/ （Oscat Basic - Array sort function 论坛讨论，摘要级）
  - https://github.com/RWTH-EBC/AixOCAT/wiki/OSCAT-BASIC-Arrays （摘要级）
  - https://eclipse.dev/oscat （OSCAT新官方主页，已核对：库已迁移至Eclipse基金会+GitHub github.com/eclipse-oscat，文档迁至readthedocs）

- 第二个范例：未找到。搜索未能定位到另一个有代表性的开源算法类FB库（如专门做优化/调度算法的公开IEC 61131-3库）给出完整对比。若需要，可考虑追加检索 Beremiz、OpenPLC自带库、或学术论文中公开的ST代码仓库（如GitHub搜"IEC 61131-3 optimization function block"），本轮未展开。

【未能核实/建议人工复核的部分】
1. PLCopen Part 1 v2.0 官方PDF原文（Execute/Done/Busy/Error/ErrorID互斥规则、边沿复位规则）——WebFetch两次尝试均因PDF为扫描/图像流而失败，现有引用均转引自搜索引擎摘要和二手网页（Beckhoff、ControlDesign），建议答辩/评审材料引用时用二手来源（Beckhoff infosys页面文字已核对原文，可直接引用），或让Claude用户本地打开PDF人工核对页码。
2. OSCAT Basic 库具体FB声明代码（ST源码级别）——未直接抓到PDF文本，建议后续用 `WebFetch` 对 https://oscat-basic.readthedocs.io 逐个功能块页面核对，或直接下载ST源码用Read工具本地核对更可靠。
3. PLCopen "Coding Guidelines"（TC2 Software Assembly/Construction Guidelines）原文——只查到入口链接 https://www.plcopen.org/guidelines/software-construction-guidelines/ 及下载页 https://www.plcopen.org/download_file/force/ff60e817-eee5-442d-b718-a357a7279c7e/342/，未打开核对具体条款文字，如评审要引用"官方编码规范原文"建议人工下载核对。
```