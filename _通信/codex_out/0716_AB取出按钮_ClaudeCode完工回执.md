# 0716 AB 可视化「取出」按钮 · Claude Code 完工回执

- 完成时间:2026-07-16 22:46(接管自 Codex 20:58 中止交接)
- 执行人:Claude Code(computer use 直操 Automation Builder 2.9 GUI)
- 依据:`.claude/handoffs/2026-07-16-205841-ab-retrieve-button-claude-takeover.md` + `_通信/codex_out/0716_ClaudeCode接管提示词_AB取出按钮.md`

## 一、裁决与结果

**P1/P2 冲突裁决:落 P2 VisuStats 查询组**(任务书标题写 P1 系签发笔误;查询输入框/Query/命中灯/Found 实际全在 P2,施工卡 :57、蓝图 :87-88、报告§6 :12 三方一致)。

**最终布局(设计坐标,已在线验证)**:
| 元素 | 位置 | 备注 |
|---|---|---|
| ID 输入框 | 790,60 (170×30) | 原样,复用 GVL_Visu.InQueryId |
| Query 按钮 | 970,60 (100×30) | GenElemInst_65,OnMouseDown=`CmdQuery:=TRUE` / OnMouseUp=`:=FALSE` |
| **Retrieve 按钮(新增)** | 1080,60 (100×30) | GenElemInst_387,OnMouseDown=`CmdRetrieve:=TRUE` / OnMouseUp=`:=FALSE`,Toggle/Tap/Hotkey 全空(纯瞬时) |
| 命中灯 | 1080,**104** (32×30) | 下移让位,变量 GVL_Visu.QryFound 不变 |
| Found 框 | 1118,**104** (102×30) | 下移让位 |

- 「已取出 N 件」可选文本:**按预案跳过**(y60/y104 两行已满,QUERY 组无自然空位,挤入伤可读性)。
- 按钮文本:**Retrieve(英文)**,偏离任务书字面「取出」——中文在当前 visu 字符集运行时渲染为 `??`(编译警告 C0555 应验,工程 visu 未开 Unicode、全页面无中文先例)。开 Unicode 属 Visualization Manager 全局设置,超出本批边界未动。
- 编译:最终 **Build complete -- 0 errors**(仅 1 常驻警告=PLC 连接未加密);中途出现过的 2×C0555(GlobalTextList 中「取出」旧条目)已随 login-download 全量重建自动消失。

## 二、在线闭环验证(22:26–22:42 实测,PC 仿真)

1. Login(Simulation)→ download → RUN
2. P1 `Load demo` → Status: **DEMO_LOADED_N=20**
3. P1 `Run assign` → Status: **DONE_OK**(N=20, DENS=0.075, REC=AWRA_HOLISTIC)
4. P2 Query ID=1 → **G001 @ (1,0)**,Weight 13.9 / Freq 1.8 / Vol 0.51,Found 灯亮
5. **按 Retrieve** → 取出状态机执行(全程约 12s,见瑕疵④)
6. 终态验证:
   - GVL_Visu 在线值:**iRetrievedCount = 1**、QryX = **-1**、CmdRetrieve 已复位 FALSE
   - P2 复查 Query 1:Name=G001 仍可查,**Position X/Y = -1/-1**(未分配),Path/Travel/Handling 全 0
   - P2 RECORDS 表首行同步:Goods 1 → Column/Tier = **-1/-1**
   - P1 网格:格 (1,0) 已非 Occupied 绿
7. Logout → 关闭 AB → `Get-Process` 验证 AutomationBuilder/VirtualAC500 **无残留进程**

结论:**Load demo → Run assign → Query → Retrieve → 复查 全链路在线闭环打通**;Query 原有行为未破坏(第 4 步即证)。

## 三、事故账(全部已就地修复,如实记录)

1. **复制粘贴三连失败→误改原件**:AB 的 Edit 菜单无 Copy/Paste;Ctrl+C/V 与右键 Copy→Paste 均未实际产生副本(粘贴静默无效)。导致初版施工把**原 Query 按钮就地改造**成了取出按钮(Text/双 ST 全改),在线首验时发现 Query 消失。修复:原按钮(65)洗回 Query 全套配置,从 Visualization Toolbox **拖拽新建** Button(387)配成 Retrieve。**教训:AB 里复制元素只信「工具箱拖新建+逐项配置」;Element name / Text ID 都不是稳定指认依据(Text ID 每次重建重分配:449→766→1241)。**
2. **中文文本运行时乱码**:「取出」在线渲染 `??` → 改 Retrieve(见上)。
3. **Element name 一度被误写为 "104"**(Properties 面板刷新时序导致焦点落错行)→ 当即 Ctrl+Z 撤销,复验无残留。
4. **Int16 溢出弹窗一次**(双击数值格未全选,"1080" 追加成 "10551080",复刻 Codex 60104 事故)→ 弹窗确认后 AB 自动恢复原值全选态,重输成功。**定式:数值格双击后一律 Home+Shift+End 强制全选再输入。**

## 四、发现的展示层瑕疵(涉改 ST,本批红线内不动,移交下批)

1. **RETRIEVED_OK 状态文本被覆盖**:取出 commit 后 VisuStatusText 仍显示 DONE_OK(疑 PRG_Main 对 assign 完成态的常驻写回把单次写入盖掉)。数据层落账(count/格位/Assigned)全部正确,仅状态行不显示。
2. **取出路径蓝色残留**:取出完成后格 (1,0) 显示路径蓝(4)而非空闲灰(0)——FB_RetrieveGood 回程路径的 VisuSlotState 清理不完全。
3. **P2 标题文案过时**:「Records / Query (demo IDs 901, 902, 903)」与实际 demo ID(1..20)不符——ID=901 实测 Found=FALSE/位置-1,ID=1 即 G001。改文案属画面文本编辑,连同上两条一起进下批。
4. **取出全程约 12 秒**:去/回程 travel 随 rSpeedScale=5 缩放,但两端 handling(6s×2)不缩放——录屏演示时预留等待,或下批把 handling 也纳入缩放。
   > **⚠️ 0717 勘误:此条机理归因作废。** 源码核查(FB_RetrieveGood 全体)证实取出流程不含任何 handling 等待——rHandleT1..T3(6/8.5/12.5s)仅用于查询显示列与统计;0717 两次在线实测取出均在 ~1 秒内落账完成(G001 切比雪夫 0.5 s / 5 倍速),状态行直接印 "oneway 0.5 s"。0716 的"12 秒"观测应为当时操作与页面刷新间隔,归因"handling 不缩放"写错了。**教训:能复现≠断言有据,机理句必须回到源码。**

## 五、负结果与待补

- **证据截图未落盘**:4 张关键截图(P2 取后查询快照 / P1 全景 / GVL_Visu 在线值 / P2 双按钮渲染)在会话内查验完毕,但 save_to_disk 未返回文件路径,全盘搜索无产物。**2 分钟重演脚本**:开 AB → Login(online change)→ F5 → P1 Load demo → Run assign → P2 输 1 → Query → Retrieve → 等 12s → 复查 Query → 截图。所有控件已就位,无需任何再配置。
  > **✅ 0717 已补拍归档**(治理 D ST 修复后的干净重演,全新 download 初态):`l4_showcase/evidence/ab_retrieve_0717/` 四帧——01 P1 分配 DONE_OK 全景(Tests 77/77 新文案)/02 P2 Query1=G001@(1,0) 命中(标题已改 demo IDs 1..20)/03 P2 Retrieve 后首行 -1/-1 落账/04 P1 "RETRIEVED_OK G1 oneway 0.5 s" 驻留显示+格位无蓝残留。瑕疵①②③在线复核全部修复生效;截图工具 save_to_disk 仍不产文件,本批改用 PowerShell CopyFromScreen 落盘(grab.ps1 模式)。
- P1 底部「Tests 75/75」静态文案未随 76/0 更新(历史文案,属 #11 清账范围)。
  > **✅ 0717 已修**:随治理 D 批次改为「Tests 77/77」(fix_visu_texts_0717.py,在线复核显示正确)。

## 六、红线遵守

- AB GUI 开启期间未运行 tools/ab_scripting ✓(全程 GUI 直操)
- 未改 ST / sim / canonical / 用户文档 ✓
- 无任何 Git 写 ✓(工作区其他任务的 M/?? 未触碰)
- Codex 未保存半成品已按交接指示丢弃(关闭选"否"),磁盘从 SHA 04A6607B 干净基线重开 ✓
- `plc/AB_Project/ABB_WH.project` 已保存(本批预期产物:P2 新增 Retrieve 按钮+灯/Found 移位),AB 已关闭 ✓
