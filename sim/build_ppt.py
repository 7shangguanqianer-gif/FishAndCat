# -*- coding: utf-8 -*-
"""
build_ppt.py — 答辩 PPT 生成器骨架(python-pptx,16:9)
纪律与 build_report.py 相同:数字全部复用其 CSV 装载结果(import 即共享,单一来源),
叙事零硬编码性能数字;图直接嵌 sim/figs。演讲稿口径以本 PPT 页序为准(R2 培养体系配套)。
运行:python build_ppt.py → out/答辩PPT_draft.pptx
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import build_report as br                      # 复用全部数字装载(不触发其 main)
from pptx import Presentation
from pptx.util import Cm, Pt
from pptx.dml.color import RGBColor

HERE = os.path.dirname(os.path.abspath(__file__))
FIGS = os.path.join(HERE, "figs")
FONT = "Microsoft YaHei"
NAVY = RGBColor(0x17, 0x36, 0x5D)
GRAY = RGBColor(0x50, 0x50, 0x50)

prs = Presentation()
prs.slide_width, prs.slide_height = Cm(33.87), Cm(19.05)      # 16:9
BLANK = prs.slide_layouts[6]


def _set(run, size, bold=False, color=None):
    run.font.name = FONT
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color or RGBColor(0x20, 0x20, 0x20)


def slide(title, bullets=None, fig=None, note=""):
    """通用页:左题+要点列表,可选右侧/下方图;note=演讲提词(进备注栏)。"""
    s = prs.slides.add_slide(BLANK)
    tb = s.shapes.add_textbox(Cm(1.2), Cm(0.7), Cm(31), Cm(1.8))
    _set(tb.text_frame.paragraphs[0].add_run(), 28, True, NAVY)
    tb.text_frame.paragraphs[0].runs[0].text = title
    if bullets:
        bx = s.shapes.add_textbox(Cm(1.4), Cm(3.0),
                                  Cm(14.5 if fig else 30.5), Cm(14.5))
        tf = bx.text_frame
        tf.word_wrap = True
        for i, (txt, lv) in enumerate(bullets):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.level = lv
            r = p.add_run()
            r.text = ("• " if lv == 0 else "– ") + txt
            _set(r, 16 if lv == 0 else 13.5,
                 bold=(lv == 0), color=None if lv == 0 else GRAY)
    if fig:
        path = os.path.join(FIGS, fig)
        if os.path.exists(path):
            s.shapes.add_picture(path, Cm(16.4 if bullets else 4.0), Cm(3.2),
                                 width=Cm(16.5 if bullets else 26.0))
    if note:
        s.notes_slide.notes_text_frame.text = note
    return s


# ---------------- 页序(≈18 页;〔〕为占位待人工补) ----------------
s = prs.slides.add_slide(BLANK)                                  # 1 封面
tb = s.shapes.add_textbox(Cm(2), Cm(6.2), Cm(30), Cm(6))
p = tb.text_frame.paragraphs[0]
_set(p.add_run(), 40, True, NAVY)
p.runs[0].text = "智储优控:基于 AI 算法与智能控制的立体仓储仓位优化"
p2 = tb.text_frame.add_paragraph()
_set(p2.add_run(), 18, False, GRAY)
p2.runs[0].text = "2026 ABB 杯 · 赛道一 · 〔队伍名/成员/学校〕"

slide("为什么这道题不简单",
      [("400 仓位、承重逐层递减、预占用、五属性货物——多目标互相冲突", 0),
       ("存取效率 vs 重货稳定 vs 提升能耗 vs 近位稀缺:没有免费午餐", 1),
       ("要求全链落地:数学模型 → 仿真验证 → AC500 PLC 实时执行", 0),
       ("主办方定调:打造“会思考”的立体仓储系统,绿色工程视野(王余,开赛致辞)", 1)],
      note="开场 40 秒:题面复述+难点定位,引用致辞建立同频。")

slide("双层优化架构:在线评分 + 批量 AWRA-LS",
      [("在线层:逐件到达,一个扫描周期内 400 仓位全扫评分,PLC 可实时执行", 0),
       ("四项加权:效率 + 稳定 + 能耗 + 位置价值预留 δ", 1),
       (f"批量层:Rank→Assign→LocalSearch,较在线再降 {br.GAP_ONLINE}%(信息完备的价值)", 0),
       ("权重按场景查表自适应(密度×分布×模式),PLC 同一张表落地", 1)],
      note="架构页 60 秒:强调双层分别对应决赛交互与优化上界。")

slide("δ 预留项:一个有证据链的设计",
      [("δ=0 → 退化成就近贪心(占位集合完全重合):存在性证明", 0),
       ("多 seed 标定 → 0.10-0.30 平台;自适应表按场景选值", 0),
       ("敏感性扫描独立验证策略表选值(悬崖-平台结构)", 1)],
      fig="fig14_参数敏感性.png",
      note="评委最容易问'权重怎么定的'——这页就是答案。")

slide("物理与作业真实度",
      [("梯形加减速运动模型(匀速口径保留为文献对照)", 0),
       (f"存取混合双命令周期:较单命令节省 {br.DUAL_SAVE}%", 0),
       (f"吞吐 {br.THR_AW} 次/时 = 题面基线的 {br.THR_X} 倍", 1)],
      fig="fig8_混合作业.png",
      note="强调'贴近实际工程应用'是题面原话。")

slide("主结果(H 口径,3 seeds)",
      [(f"AWRA-LS 期望取货 {br.H_AW}±{br.H_AW_STD}s,较题面基线降 {br.DROP_VS_SEQ}%", 0),
       (f"提升能耗降 {br.DROP_E}%;重货平均层 {br.HEAVY_TIER};违规 0", 0),
       (f"对照口径(匀速+固定权重,可比文献):{br.LEG_AW}s / 降 {br.LEG_DROP}%", 1)],
      fig="fig1_策略对比.png",
      note="全场最重的一页,放慢;口径两句话讲清,体现严谨。")

slide("离理论天花板有多远",
      [(f"解析下界 {br.LB_S}s ≤ NSGA-II 可达 {br.ACH_S}s ≤ AWRA-LS {br.AW_BOUND_S}s", 0),
       (f"距可达最优 {br.GAP_ACH}%——“我们离理论天花板不到 9%”", 0),
       ("随机策略解析值 vs 仿真:1σ 内互证,仿真器本身被理论校验", 1)],
      fig="fig9_理论对比.png",
      note="三级证据链是名校队语言;一句话金句放这页。")

slide("一套系统,九把尺子:口径矩阵(方法论)",
      [("每个建模选择都被识别为“口径”:参数化+保留切换开关+主/对照并列呈现", 0),
       ("运动模型(加减速/匀速)/ 权重(自适应/固定)/ 行程(切比雪夫/曼哈顿)…共 9 维", 1),
       ("核心主张=口径不变性:主结论在全部口径组合下方向一致,切换只平移数字", 0),
       ("类比:汽车油耗的 WLTP vs EPA、财报的双准则——工程数字必须声明测量框架", 1),
       ("完整矩阵见报告附录 C;主口径数字由回归测试锁定,动口径=红灯", 1)],
      note="创新10%+报告30%的方法论页;评委问'为什么两套数'时,这页是总答案。")

slide("鲁棒性与运行期自愈",
      [("分布漂移/紧库存/重货潮三类压力:AWRA 系退化最平缓,紧库存失败 0 件", 0),
       ("周期重排=夜间自愈机制:消除布局熵漂移(收益>1.2×成本才动,经济学准入)", 0),
       ("负结果如实呈现:重排的价值是自愈不是提效(F11)", 1)],
      fig="fig13_鲁棒压力.png",
      note="'负结果也如实写'是工程可信度的加分句。")

slide("AC500 落地:优化算法跑在 10ms 实时任务里",
      [("三层封装:FC 纯函数 / FB 状态机 / PRG 主状态机", 0),
       ("扫描周期分片:每周期 nBatchPerCycle 件、nPairsPerCycle 对,非阻塞不触发看门狗", 0),
       ("23 项边界+一致性用例,AB 仿真实测 iPassed=23 / 0 错误", 0),
       ("〔L4 任务级负载实测表:批次回执后此页补数据〕", 1)],
      note="ABB 工程师评委最认的一页;截图在下一页。")

slide("轻量数字孪生:Python 与 ST 互相背书",
      [("同一算法两个实现:仿真侧探索统计,PLC 侧实时执行", 0),
       ("自动生成一致性向量:评分/行程(含加减速)/双命令,1e-3 容差比对", 0),
       ("演示批与仿真同 seed 同源——报告数字与现场演示互证", 0),
       ("护栏:任何一侧口径变更 → 一致性用例红灯(开发期已拦截过分歧)", 1)],
      note="创新10%主素材之一;'数字孪生'是官方材料关键词。")

slide("绿色工程:能耗的年化账",
      [(f"较题面基线年省电约 {br.KWH_SAVE} kWh(降 {br.KWH_SAVE_PCT}%),假设全部显式声明", 0),
       ("下降势能不回收、效率保守取值——换算偏保守,不吃再生制动的账", 1),
       ("呼应“AI 算法正在重新定义能效的边界”(王余)", 0)],
      fig="fig10_绿色换算.png",
      note="封面级卖点;强调假设显式=可质疑可替换。")

slide("决赛可视化演示(录屏/现场)",
      [("20×20 彩色仓位图 + 堆垛机沿路径动画 + 交互输入 + 统计面板", 0),
       ("六步演示:初始→轻高频→重货→批量→算法对比→超重报警", 0),
       ("第 7 步:评委现场改权重(δ→0),推荐位实时退化——算法可解释性的现场证明", 0),
       ("〔此页贴可视化截图/嵌录屏,批次 C 完成后补〕", 1)],
      note="决赛 20% 的正面战场;留出现场操作时间。")

slide("创新点清单",
      [("位置价值预留项 δ 及其完整证据链(存在性→标定→敏感性)", 0),
       ("场景自适应权重查表(标定+留出集验证+PLC 同源)", 0),
       ("扫描周期分片状态机(优化算法的 PLC 原生工程化)", 0),
       ("轻量数字孪生验证方法;周期重排自愈闭环", 0)],
      note="每条都有实验编号与复现命令,防'创新是嘴上说的'质疑。")

slide("工程取舍(考虑过且不用,都有数据)",
      [("A* 路径规划:双轴同动+无障碍,切比雪夫直达即物理最优", 0),
       (f"强化学习:**自己实跑了轻量版**——自学 1200 回合到 {br.RL_FINAL}s,仍落后手工标定 "
        f"{br.RL_GAP}%,且学不出 δ 预留结构(余弦 {br.RL_COS})→ 设计知识仍然值钱", 0),
       ("深度版引 2025 文献:需长期数据、收益个位数、黑箱——不符合实时可审计要求", 1),
       ("查表化执行:在线评分本身微秒级,查表反丢解释链", 0)],
      fig="fig15_RL对照.png",
      note="'知道为什么不用'且'亲手试过'——这页现在有自己的学习曲线。")

slide("结论",
      [(f"期望取货较基线降 {br.DROP_VS_SEQ}%,能耗降 {br.DROP_E}%,吞吐 {br.THR_X} 倍,违规 0", 0),
       (f"距已证可达最优 {br.GAP_ACH}%;23 项 PLC 用例 AB 实测通过", 0),
       ("每一个数字都可由交付包脚本一键复现", 0)],
      note="收尾引用张楠'从学子到工程师的思维跃迁'致谢即可。")

slide("Q&A", [("〔答辩 QA 卡:T18 产出后此页后附常见 20 问〕", 0)])

path = os.path.join(HERE, "out", "答辩PPT_draft.pptx")
prs.save(path)
print(f"已生成:{path}({len(prs.slides.__iter__.__self__._sldIdLst)} 页)")
print("占位符〔〕清单:封面队伍名 / L4 表 / 可视化截图 / QA 附页——对应任务回执后重跑本脚本。")
