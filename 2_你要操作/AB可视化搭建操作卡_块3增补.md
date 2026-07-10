# AB 可视化操作卡 · 块3 增补(0708;配合存量卡使用)

> **前提**:你已照《AB可视化搭建操作卡.md》搭好 P1 主画面(网格/堆垛机/输入区/按钮/统计)。
> 本卡只写**块3 新增**:P2 统计查询页、输入控件升级、快照对比、Alarm Banner、WebVisu、
> V1-V5 验证、演示脚本 v2。预计 2~3 小时(含验证半天可拆开做)。
> **ST 侧已全部就绪**:ab_sync 实跑 iPassed=45/0(0708),画面只做"绑定显示"零逻辑。

---

## 0. 第 0 步:同步 ST(一条命令,替代旧卡的手工粘贴)

关掉 AB(管线要独占工程),PowerShell 里:
```
powershell -File F:\abb_wh_work\tools\ab_scripting\ab_sync.ps1
```
约 5 分钟,末行看到 `=== ALL GREEN: iPassed=45 iFailed=0 ===` 即成。之后打开 AB 搭画面。
> 旧卡 §1 的"整段替换粘贴"作废——0707 起管线自动同步,这就是它的价值。

## 1. P1 主画面升级(在现有 VisuMain 上改)

### 1.1 输入框升级为专业键盘(纠正旧卡 §5.2 的两处)
旧卡写的 `OnMouseDown` 应为 **OnMouseClick**(官方文档统一用法);且当时没配键盘类型。
五个输入框逐个改:选中 → Input configuration → **OnMouseClick** → Write a Variable:

| 框 | Input type | Min / Max(拒绝式:超范围不写入) |
|---|---|---|
| 编号 InGoodId | `VisuDialogs.Numpad` | 1 / 400 |
| 名称 InGoodName | `VisuDialogs.Keypad`(字母键盘) | — |
| 重量 InGoodWeight | `VisuDialogs.Numpad` | 0 / 200 |
| 频次 InGoodFreq | `VisuDialogs.Numpad` | 0 / 100 |
| 体积 InGoodVolume | `VisuDialogs.Numpad` | 0 / 1.0 |

> Min/Max 是防呆第一道关;超限直接被键盘拒绝。PLC 侧 iErrId=2 仍兜底(双保险)。

### 1.2 名称下拉(可选增强,5 分钟)
工具箱 常用控件 → **Combo Box, Array**,放名称框旁(约 24 高):
- 属性 Data array = `GVL_Visu.astrNames`(10 个常用货名,ST 侧已备);
- 属性 Variable(选中索引)= `GVL_Visu.iNameSel`。
选中即自动填入名称框(PRG 同步,消费即复位),仍可 Keypad 手输覆盖——两不误。

### 1.3 快照对比(方向9,两个按钮 + 一个指示灯)
放在"运行分配"按钮附近:
| 元素 | 配置 |
|---|---|
| 按钮`保存快照` | Input configuration → Tap variable = `GVL_Visu.CmdSaveSnap` |
| 按钮`对比模式` | Input configuration → **Toggle variable** = `GVL_Visu.CmdCompareMode`(开关型,按一下保持) |
| 灯(Lamp) | Variable = `GVL_Visu.xSnapValid`(绿=已有快照可对比) |
对比模式开=网格显示快照(冻结布局),关=实时。**没存过快照时开关无效**(PLC 已防)。

### 1.4 工程徽章角标(底部右角,静态文本一个)
文本域,无边框,小字号(10-11),内容(一行):
```
在线测试 45/45 · sim-ST 双实现互证 · 驻留点=I/O(400格枚举最优)
```
> 数字 45 随用例数走,以后加用例记得同步改这里(文档禁硬编码过时数字)。

## 2. P2 统计查询页(新建画面,块3 主交付)

### 2.1 新建
Application 右键 → 添加对象 → 可视化 → 名字 `VisuStats`。布局(画面标准 §3):
```
┌────────────────────────────────┬──────────────────┐
│ 记录表(10行×5列)+ 翻页        │ 单件查询区        │
│                                │ 拟真调参区        │
├────────────────────────────────┴──────────────────┤
│ 总计栏(复用统计5量)+ [返回主画面]按钮             │
└───────────────────────────────────────────────────┘
```

### 2.2 记录表(倍增法,5 列各倍增一次,共 5 次操作)
表头 5 个静态文本:`序号  列  层  路径m  用时s`(x≈40 起,y=60)。
**每列一个模板文本域 + 竖向倍增 10 个**(和旧卡网格倍增同技巧,一维版):
| 列 | 模板文本域 Text | Text variable(占位符写法) | 倍增 |
|---|---|---|---|
| 序号 | `%d` | `GVL_Visu.aRowId[$FIRSTDIM$]` | FIRSTDIM 数量10,竖向偏移28 |
| 列 | `%d` | `GVL_Visu.aRowX[$FIRSTDIM$]` | 同上 |
| 层 | `%d` | `GVL_Visu.aRowY[$FIRSTDIM$]` | 同上 |
| 路径 | `%.1f` | `GVL_Visu.aRowPathLen[$FIRSTDIM$]` | 同上 |
| 用时 | `%.2f` | `GVL_Visu.aRowExecT[$FIRSTDIM$]` | 同上 |
> 约定:序号=0 的行是空行;位置=-1 表示"已入表未分配"。可加一行静态小字注明。

翻页三件套(表下方):
- 按钮`▲上页` Tap variable=`GVL_Visu.CmdPageUp`;按钮`▼下页`=`GVL_Visu.CmdPageDown`;
- 文本域 `第%d行起` ← `GVL_Visu.iRecTop`;`共%d件` ← `GVL_Visu.iRecTotal`。

### 2.3 单件查询区(右上)
| 元素 | 配置 |
|---|---|
| 输入框`查询序号` | `%d` ← `GVL_Visu.InQueryId`;OnMouseClick→Write→Numpad,Min1/Max400 |
| 按钮`查询` | Tap variable = `GVL_Visu.CmdQuery` |
| 结果文本域×8(竖排) | `名称:%s`←QryName;`重量:%.1f`←QryWeight;`频次:%.1f`←QryFreq;`体积:%.2f`←QryVolume;`位置:(%d`←QryX + `,%d)`←QryY;`路径:%.1f m`←QryPathLen;`用时:%.2f s`←QryExecTime |
| 拟真对照×2(重点!) | `载货行程:%.2f s`←`GVL_Visu.QryTravelLaden`;`装卸:%.1f s`←`GVL_Visu.QryHandleT` |
| 找到灯 | Lamp ← `GVL_Visu.QryFound` |
> 查询命中后**主画面网格该格变青色**(状态6)——评委在 P1 也能看到高亮。

### 2.4 拟真调参区(右下,做法=旧卡 §5.7 权重区)
6 个输入框(Write a Variable→Numpad),全在 **GVL_Param**:
| 标签 | Text | 变量 | 默认 |
|---|---|---|---|
| 垂直折减 | `%.2f` | `GVL_Param.rLadenFactorVY` | 0.80 |
| 轻档上限kg | `%.0f` | `GVL_Param.rHandleW1` | 30 |
| 中档上限kg | `%.0f` | `GVL_Param.rHandleW2` | 60 |
| 轻装卸s | `%.1f` | `GVL_Param.rHandleT1` | 6.0 |
| 中装卸s | `%.1f` | `GVL_Param.rHandleT2` | 8.5 |
| 重装卸s | `%.1f` | `GVL_Param.rHandleT3` | 12.5 |
静态小字:`默认 0.80/30/60/6.0/8.5/12.5,演示后改回`。
**演示联动**:改折减 0.80→1.00 → 查询区"载货行程"数字**立即变小**(垂直不再折减)。

### 2.5 总计栏 + 页面切换
- 总计栏:复用旧卡 §5.6 的 5 个统计变量(VisuTotalTime 等),横排一行;
- P1↔P2 切换:两画面各放一个按钮,Input configuration → **Change shown visualization**,
  目标分别填 `VisuStats` / `VisuMain`。

## 3. Alarm Banner 报警条(一手配方,块3施工依据 §2)

1. Application 右键 → 添加对象 → **报警配置(Alarm Configuration)**;
2. 其下建 **Alarm Class**:名 `AC_High`,优先级 0,确认方式 REQ(需确认);
3. 建 **Alarm Group**:名 `AG_WH`,组内加一条:Observation type=**Digital**,
   Expression=`GVL_Visu.VisuAlarm`,比较 `= TRUE`,Message 填 `Warehouse alarm: no feasible slot / invalid input`;
4. VisuMain 底部拖 **Alarm Banner** 元素(工具箱 报警管理器类):高约 32,宽=画面宽;
   属性 Alarm groups 取消 All 只勾 `AG_WH`;Filter=Newest;列=Timestamp+Message;
5. 确认按钮:Banner 旁小按钮`确认`,先在 GVL_Visu 手动加一行 `xAckAlarm : BOOL;`?
   ——**不用**:Banner 属性 Acknowledgement→Variable 直接填 `GVL_Visu.CmdReset` 亦可
   (复位即确认,语义相容);想独立确认再告诉我加变量。
> 注意:AB **IDE 在线预览里 Banner 不渲染是正常的**(官方限制只针对 IDE 预览);
> 登录下载后的画面/WebVisu 里才显示——别在预览里误判"没做出来"。

## 4. WebVisu 发布(V4 前置:先 Simulation 本机验证)

1. 设备树 **Visualization Manager** 右键 → 添加对象 → **WebVisu**;
2. 其属性:Start visualization = `VisuMain`;.htm 名默认 `webvisu.htm`;
3. 编译下载启动(Simulation 即可)→ 浏览器开 `http://localhost:8080/webvisu.htm`;
4. 手机同网段也能开(把 localhost 换电脑 IP)——演示加分项。
> 真机 AC500 部署才涉及 ABB 许可档(V4 未查实);Simulation/录屏线不受影响。

## 5. V1-V5 最小验证(半天;结果直接决定后续路线,逐项记录)

| # | 操作 | 判定 | 记录到 |
|---|---|---|---|
| V1 | WebVisu 打开 P1(400 格已倍增) | 拖动/刷新流畅=过;卡顿→记录格数阈值 | 验收截图目录 |
| V2 | 工具箱找 **Path3D** 元素,放空画面绑任意 REAL 数组试渲染;WebVisu 里开 | 能显示=真3D 路线;不能=2.5D 伪3D(已是预案) | 同上 |
| V3 | 步骤3 的 Banner 在 WebVisu 里触发一次报警 | Banner 出现记录=过 | 同上 |
| V4 | AB 帮助/许可管理器搜 WebVisu 许可要求(真机档) | 记下原文一句话 | 告诉我 |
| V5 | PLC 节点属性看 CODESYS 内核版本号 | 3.5.x.x 记下 | 告诉我 |

## 6. 演示脚本 v2(存量七步之间插新步,标 ★=块3 新增)

| 步 | 操作 | 预期/讲解词 |
|---|---|---|
| 1-3 | 同存量卡 | 初始/轻高频/重货 |
| 4 | 批量分配(评分策略) | DONE_OK,记总时间 |
| ★4b | 切到 P2 统计页,翻页看记录 | "每件货的位置/路径/用时全程可查,总计栏对账" |
| ★4c | 查询区输入 1 → 查询 | "单件五属性+双口径时间;回主画面看,该格青色高亮" |
| ★4d | 调参:垂直折减 0.80→1.00,再看载货行程 | "满载折减是 U2 载重建模,参数可调、数字实时变——改回 0.80" |
| ★5a | **保存快照**(评分策略布局留底) | 快照灯亮 |
| 5b | 复位→载入→AWRA-LS→运行分配 | DONE_OK,总时间更小 |
| ★5c | 开**对比模式**来回切 | "同批货:评分策略 vs AWRA-LS 布局并排对比——热点向 I/O 口收拢,这就是优化的形状" |
| 6 | 超重货报警(同存量) | 红灯 + **★Banner 弹出带时间戳报警行** |
| 7 | 现场调权重(同存量) | δ=0 退化演示 |
| ★8 | 浏览器开 WebVisu(可手机) | "同一画面 Web 发布,无需安装任何软件" |

## 7. 验收清单 v2(增量)

- [ ] ab_sync 全绿 45/0(第 0 步);
- [ ] 五输入框全部弹专业键盘,超范围被拒(试:重量输 300 → 拒绝);
- [ ] 名称下拉选中即填入,手输仍可覆盖;
- [ ] P2 记录表 10 行随批量分配填充,翻页钳位正确(2 件时按下页不动);
- [ ] 查询 Id=1:九个字段齐 + 主画面青色高亮;查 999:找到灯灭;
- [ ] 调参区改折减,查询"载货行程"实时变;改回默认;
- [ ] 快照对比:保存→切换,两布局肉眼可辨;
- [ ] Banner 在下载后画面出现报警行(IDE 预览不显示≠故障);
- [ ] WebVisu localhost:8080 可开且可操作;
- [ ] V1-V5 五项结果记录并反馈给我。

## 8. 常见坑(增量)

| 症状 | 解法 |
|---|---|
| 倍增后文本全显示同一行 | 占位符必须是 `$FIRSTDIM$`(美元号包裹),且倍增对话框第一维数量=10 |
| ComboBox 不出下拉 | Data array 必须绑数组本体 `GVL_Visu.astrNames`(不带下标) |
| 对比模式按了没反应 | 先"保存快照"(灯亮才有对比源);PLC 侧 xSnapValid 防呆 |
| Banner 空白 | ①IDE 预览不渲染(正常)②Alarm group 勾选是否只勾 AG_WH ③触发过报警才有行 |
| WebVisu 打不开 | 下载后应用必须 **Start**(Web 服务随应用启停);端口被占换 8081(Manager 里改) |
| 调参改完数字不变 | 查询是"上升沿"计算——改参后**再按一次查询**刷新 |
