# Overnight 断点文件(滚动更新;心跳 cron 与任何续跑会话以本文件为唯一真相源)

status: RUNNING
heartbeat: 2026-07-18 02:15 (+0800)
current: M1 verifier PASS 4/5,M2 结论文档已成;推进 M3 技术欠账

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
- [ ] M3 技术欠账:sim 测试回归(pytest 或 rtk test)+design_reviews/archive_0716 等未跟踪文件点名归档;**AB 日志 runtest_result.txt/sync_result.txt 不碰(夜间 AB 红线)**
- [ ] M4 #16 mixed:02_入出闭环.html+交互+新 QA+双命令调度设计稿(文档+sim 离线原型 30seed 配对vs顺序空驶节省%)
- [ ] M5 #17 T7:00_导览 04 章挂决赛四件实链+全页口径体检(77/0/动线/文物排除/旧术语)
- [ ] M6 T6:01 页 90s 定调片(候选,Playwright 录制,落 l4_showcase/media/)
- [ ] M7 报告周素材包+三课课件草稿(docs/,不碰 1_/2_)
- [ ] M8 03 页风格一致性体检(余量项)
- [ ] M9 终验 verifier+overnight-report.md+桌面面板同步

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
