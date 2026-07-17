# Overnight 断点文件(滚动更新;心跳 cron 与任何续跑会话以本文件为唯一真相源)

status: RUNNING
heartbeat: 2026-07-18 04:55 (+0800)
current: 全部收官。对抗验证:M2/M4a headline 数字全复现一致、结论站得住,已订正 3 处机理/标注错(whatif §1/§5、双命令 §2/§3,同步增补包)。M4b 额外起步:02页运行时可跑+治理+boot-QA 8/8(A壳布局待用户迭代)。
NOTE_心跳: 队列剩项(M4b 页体 rail/M6 渲染/M5 链/三课)全为**用户阻塞**,心跳**不要**尝试推进,保持存活即可;续跑物=清晨用户拍板。

## 续跑指令(给心跳 cron / 冷启动会话 / compact 后续跑)

1. 若 status=RUNNING 且 heartbeat 距今 < 15 分钟:主循环存活,回一句「心跳正常」即结束,勿动任何文件。
2. 否则:读 `docs/overnight-plan_0718.md` 全文(队列+边界+红线),从下面「队列状态」第一个非 DONE 项继续;每完成一小步更新本文件 heartbeat+队列状态并 commit。
3. 额度未恢复导致本次失败:什么都不用做,下一次心跳会再试。
4. **每个里程碑代码完成后必须派 verifier**(claude-opus-4-8 / effort high,Agent 工具 subagent_type=general-purpose 或直接 model 覆盖):fresh context 对照 docs/overnight-plan_0718.md 该里程碑规格+看截图,以「评委第一眼」评 1-5 分;<4 分返工,连续 3 次不达取最高分版本 commit 并记入下方待拍板。

## 队列状态

- [DONE] M0 出发单+断点+心跳 cron(4f971dc)
- [DONE] M1a 绿框①顶栏工具就地风格化(6b82f07,QA 46/46;顶栏截图自检通过:蓝描边按钮/蓝滑块/蓝数值同轴行色系)
- [DONE] M1b 绿框②差异热力图常驻左栏(8ec2228,四套 QA 全绿 46/20/8/task12;堆叠 rect 核对无重叠;diff 方阵 79px+图例两项)。
- [DONE] **M1 整体 verifier PASS 4/5**(绿框① 4/5、绿框② 4/5,命中三底线:无大面积空白/无强硬移植/风格统一)。3 条非阻断小瑕见待拍板。
  - 已知欠账(留 M3):task12 determinism 门 flaky——changedPixels 阈值 64 现成绑定约束(实测偶发 66,maxChannelDelta 5、stateStable true=纯 GPU AA 抖动非逻辑差异);M3 拟提阈值至 96 并注释。
- [DONE] M2 #27 结论文档(负结果;生产零改动)——docs/S3评分修订what-if结论_0718.md,含 skew/uniform 30seed 均值表+判据逐条裁决+τ 饱和点机理(19s 落高层、首件(19,0) t_norm=0.25 在饱和点下)+复现命令。
- [DONE] M3 技术欠账:sim core_smoke PASS(unittest discover+5seed headline锚);task12 flaky 阈值 64→96(9eeb945);0716 设计评审产物点名归档 17 文件(401d9ef,含 ia_review spec/恢复版式3候选/archive_0716冻结快照)。AB 日志/l2 logs/codex_out/1_2_ 均未碰(红线)。
- [DONE(拆)] M4 #16 mixed:
  - [DONE] M4a 双命令调度设计稿+30seed 离线原型(f928e7d,docs/双命令调度设计稿_0718.md + sim/mixed_dispatch_sweep.py + 证据)。
  - [起步完成,rail 待迭代] M4b 02_入出闭环.html:深侦察证实 runtime 非自包含(依赖原宿主页 ~413 行内联场景脚本+严格加载序+运行时自建 DOM)。**用户「继续」后实建**:cee9242——基于原宿主页(冻结页复制非覆盖),浏览器实测运行时可启(0错误/120库存/trace驱动/五lane),核心治理(入出闭环命名+AUTO「规则路由 启动时一次选定」+禁词零命中),boot-QA 8/8。计划 docs/implementation-notes_02入出闭环页_0718.md(契约/配方/4待澄清)。**A壳 rail 布局/cycle轴(0-25-50-75-100)/取货实测块=用户在场窗口迭代**(承绿框教训)。
- [进行中/半阻] M5 #17 T7:00_导览 04 章挂决赛四件实链+全页口径体检。**预扫发现(待 M4b 后定夺)**:①04章用通用名(三维作业回放/运行数据看板)非实际 01_/02_/03_ 文件名,「四件实链」含尚不存在的 02 页(M4b 延后→死链风险),故实链暂只能挂 00/01/03 三件;②**口径漂移(跨页实锤)**:00_导览 行 131 写「75 项通过、0 失败」,而 03_FIO物理证据.html 行 186 写「77/0 自检」——同一 AB 自检口径两页不一致。红线锚为 77/0,故 00_导览 的 75 疑似 stale。**AB 相邻,夜间不碰,请用户核真相源后统一(建议 75→77 但须用户确认非指不同批次/日期)**;③口径整体健康:AUTO 已标「规则选路」、AWRA 未冒充在线、oracle 双口径带 sim 免责。**M5 独立部分(口径体检修正)可做,四件实链待 02 页**。
- [分镜就绪,渲染待过目] M6 T6:01 页 90s 定调片。用户拍板「先录一段定调过目后再批量」=创意需先过目,故出 **docs/T6_01页90s定调片_分镜spec_0718.md**(6 段分镜/事件锚/相机意图/字幕口径/技术管线),**未夜渲 2700 帧**;用户过目分镜后我改 render_s3_video.mjs(SOURCE→01页,DURATION 90,timeline 六段)+渲染+ffmpeg 编码(~20-30min 自主)。
- [DONE(拆)] M7:
  - [DONE] 报告周素材预备包 → **docs/报告周素材_0718增补包.md**(折入本轮:§1 呈现升级/§2 证据先行/§3 双命令两杠杆/§4 清账遗漏扫描/§5 75-77 待核)。
  - [延后] 三课课件草稿(#12):课纲=`2_你要操作\FactoryIO仿真上手教程.md` 在**红线 2_ 目录不碰**,且三课需**用户在场排期**(#12 本就「等用户定在场时段」)——双重阻塞,宜用户定档+授权读教程后做。
- [DONE] M8 03 页风格一致性体检:03_FIO物理证据.html 是独立 Factory I/O 证据浏览器(非 S3 三维族),自有一致内风格(--abb 红/brand/常驻口径带 scopeBand/sim 免责/Consolas 路径),内部自洽、品牌对齐、禁词(智能路由/容量书签)零命中、口径带 sim 免责齐——**无需改动**(体检合格)。唯一交叉发现见待拍板 75/77。
- [DONE] M9 终验:四套 QA 全绿(46/20/8/task12)+ sim core_smoke PASS;overnight-report.md 已成(完成/未完/挂起+diff+4 Deviations+7 待拍板+验收命令);桌面面板同步见下。

## M1b 精确续做说明(差异热力图常驻左栏,免重新侦察)

**现状**:`#diffMapWrap`(含 .diffHead + canvas#diffMap + .diffKey)由 s3_layout_a_interactions.js 追加进 `#slotMapWrap`;当前 CSS `#diffMapWrap{display:none}`,仅放大 overlay 内显示(`html[data-s3-layout="A"] #s3MapOverlay #diffMapWrap{display:block}`)。绿框②的空白=`#slotMapWrap` grid 第 3 行 `minmax(0,1fr)` 里 slotMap(aspect 2.55/1,align-self:start)下方的余量。

**改法(纯 CSS,runtime 无需改——drawDiffMap 已按 canvas rect 尺寸绘制并按 signature 缓存,rail/overlay 间移动自动重绘)**:
1. 01_连续填仓.html 内 `#slotMapWrap` 的 `grid-template-rows` 由 `auto auto minmax(0,1fr) auto` 改为 `auto auto auto auto minmax(0,1fr)`(mapHead/mapRule/slotMap/mapKey 全 auto,diffMapWrap 吃末行 1fr)。
2. `html[data-s3-layout="A"] #slotMap` 的 `align-self:start` 保留,但其所在行改 auto(随上一条)。
3. 新增 `html[data-s3-layout="A"] #slotMapWrap #diffMapWrap{display:block;margin-top:6px;border-top:1px dashed #d3dae0;padding-top:6px}` + 紧凑版 .diffHead(b 9.5px/span 7.5px)+ `#diffMap` 在 rail 内 `width:auto;height:100%;max-width:100%;aspect-ratio:1/1;margin:0 auto`(占满末行余量)+ .diffKey 7.5px 横排。
4. 注意:overlay 用的 `#s3MapOverlay #diffMap{width:min(270px,55%)}` 已存在,是同一 canvas 的另一作用域,不冲突;openMap 把整个 slotMapWrap 搬进 overlay,diffMapWrap 随之走,无需额外处理。
5. zoomHint 文案「放大 · 三联+差异 ⤢」可改「放大看大图 ⤢」(差异已常驻)。
6. QA(capture_s3_layout_a_qa.mjs):把 fx26DiffMap 门加"rail 内 diffMap 常显"判据(非 overlay 态 getBoundingClientRect().height>2 且 snapshot().diffAudit.nonZeroCells>0);viewportsInside 必须仍全绿(rail 不得溢出——diffMapWrap 只吃既有空白,净高不增,但四视口都要过)。**candidate/uniform QA 不受影响**(diffMapWrap 仅 layout A 由 interactions.js 注入)。
7. 三套 QA 全绿后 commit(M1b),再对 M1 整体派 verifier。

## 待拍板(夜间保守顶上的决策,清晨逐条)

- **M1 verifier 4/5 的可选 5/5 打磨(非阻断,未做以免夜间镀金/发散)**:①差异热力图居中留左右侧白、未填满栏宽(几何约束:20×20 方阵在窄栏内做正方,加宽需更多竖向空间,末行仅 79px;若接受非正方拉伸或改 drawDiffMap 可填宽,但会扭曲单元格);②顶栏工具簇圆角外框与开放式进度轴略有「成块感」,可去外框或给进度轴加同款框求容器一致。二者均观感取舍,请用户定要不要动。
- **工作区 1_/2_ 用户文档显示为已 modified(M)**:非我改动(夜间从未打开),疑似备份 hook 或历史遗留;夜间红线未碰未提交。请用户确认是否需要处理(属 #25 待授权范围)。
- **#27 观感 vs 评分定义取舍**:结论文档 §七——「首件不送最远角」的纯观感诉求,呈现层(#26 冷门送远解说卡)已正面转译,不建议改评分定义;若用户仍想改,须重开方案。
- **M3 归档取舍(3.2M 截图堆)**:l4_showcase/design_reviews/screenshots_0716/(1.7M)+ screenshots_0716_incremental/(1.5M)未入库——设计评审过程截图,体量大。请用户定:git add 归档 or 加 .gitignore 忽略。其余未跟踪(.claude/.superpowers 本地配置、_通信/codex_out 旧 Codex 产物、l2_factoryio/logs FactoryIO 诊断日志、tools/ab_scripting/logs AB 日志)均属红线/非本人产物,夜间未碰。
