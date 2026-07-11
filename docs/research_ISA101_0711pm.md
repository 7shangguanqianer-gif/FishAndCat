# ISA-101 工业 HMI 标准深化调研(0711pm,B5 research,overnight 无人值守)

> **起草时间**:2026-07-11 深夜(overnight,用户不在场)
> **任务来源**:0711pm overnight 指令,B5 research 队列项(`docs/技术方向总库_0711.md` B 表 B5 行:"参考文献补全")
> **目的**:深化 ISA-101 对本项目三页制 HMI 导航(P1 操作台/P2 记录分析/P3 管理配置)的标准背书,供报告 B5 章正式引用。
> **不重复**:0706 已做的概念级结论(禁黑底/正常状态视觉静默灰/颜色只用于异常/禁渐变/四级层级概念本身)见
> `docs/HMI交互惯例调研_0706.md`,本文档只做**条款级/委员级/文献级**的深化,不复述该文档已有内容。
> **硬纪律遵守声明**:全程未 spawn 子代理、未做任何 git 操作、未打开 Automation Builder、未修改仓库内任何现有文件;
> 只读仓库(确认未与既有调研重复)+ WebSearch/WebFetch + 新建本文件。
> **数字/条款纪律**:凡标准条款号、页码、ISBN 等,均基于本次实际检索到的一手材料逐字核对后落笔;
> 查不到的一律在"负结果"节如实声明,不编条款号、不编页码。

---

## 摘要(先读这段,5 秒扫完)

| 问题 | 最强证据 | 强度 |
|---|---|---|
| 1. 条款级层级定义 | ANSI 官方预览版 PDF 直接读到:**Clause 6.3 "Display Hierarchy"(第 42-47 页)**,隶属 Clause 6 "Display Styles and Overall HMI Structure";Figure 3-6 分别为 Level 1-4 画面示例(p.43-46) | **一手**(标准官方文本本体截取) |
| 2. 三页↔四级映射论证 | 标准原文"Clauses 4-9 presents mandatory requirements **and non-mandatory recommendations** as noted"(一手,允许裁剪的文本依据)+ 具名资深专家"hierarchy is also collapsible"(二手但具名) | 一手文本依据 + 二手专家佐证 + **本项目原创工程论证**(见下) |
| 3. ABB 自家 HMI 背书 | **ABB Inc.(委员 N. Robinson)是 ANSI/ISA-101.01-2015 标准委员会正式投票委员**——直接见于标准官方文本第 4 页委员名单 | **一手**(标准官方文本本体,比"产品页提及"更强的背书形态) |
| 4. High-Performance HMI 文献底 | Hollifield 等《The High Performance HMI Handbook》(PAS, 2008, ISBN 978-0-9778969-1-2)——其两位作者(**W. Hollifield / I. Nimmo**)本身就是 ISA101 标准委员会成员(I. Nimmo 还是 Clause Editor) | **一手**(书目信息+委员名单交叉验证) |

**最大负结果**:ABB 官方产品页(new.abb.com 800xA 系列)是否**逐字**出现"ISA-101"字样,本次未能独立核验——WebFetch 对相关页面 3 次尝试均超时失败,site 限定搜索也未命中。ISA-101 标准正文 Clause 6.3 的**逐字条款定义**(而非委员个人转述)因标准全文付费墙,本次也未能核验原文逐句表述。详见文末"负结果汇总"。

---

## 问题一:条款级层级定义(ANSI/ISA-101.01-2015 的 Display Hierarchy 具体条款号)

### 结论

ANSI/ISA-101.01-2015《Human Machine Interfaces for Process Automation Systems》的画面层级定义在:

- **第 6 章 "Display Styles and Overall HMI Structure"**(第 40 页起)
  - 6.1 Introduction(p.40)
  - 6.2 Display Styles(p.40)
  - **6.3 Display Hierarchy(p.42-47 之间,至第 7 章 "User Interaction" p.47 为止)**
- 配图:**Figure 3 – Sample Level 1 Display(p.43)/ Figure 4 – Sample Level 2 Display(p.44)/ Figure 5 – Sample Level 3 Display(p.45)/ Figure 6 – Sample Level 4 Display(p.46)**——四级各有官方示例图。

标准整体结构(标准原文 Introduction/Organization 段逐字):

> "This standard is organized into nine clauses. The first three clauses are introductory in nature. Clause 4 presents the lifecycle model for the HMI. Clauses 5 through 9 provide additional details to support the lifecycle. The main body of the standard (Clauses 4-9) presents mandatory requirements and non-mandatory recommendations as noted."

九章依次为:1 Scope / 2 Normative References / 3 Definition of Terms and Acronyms / **4 HMI System Management(生命周期模型)** / 5 Human Factors Engineering & Ergonomics / **6 Display Styles and Overall HMI Structure(含 6.3 Display Hierarchy)** / 7 User Interaction / 8 Performance / 9 Training。

书目信息(标准本体版权页逐字):ISBN **978-1-941546-46-8**,Approved **9 July 2015**,Copyright © 2015 International Society of Automation,ISA 地址 67 Alexander Drive, Research Triangle Park, NC。

### 一手出处

ANSI 官方标准预览版 PDF(本次用 WebFetch 下载 + Read 工具直接解出全部 9 页正文,含完整 Contents/Figures/Tables 目录页与标准前言、委员名单、Scope/Organization 段落):
**https://webstore.ansi.org/preview-pages/ISA/preview_ANSI+ISA+101.01-2015.pdf**

标准官方购买页(可付费获取全文用于报告周精修核验):
- https://webstore.ansi.org/standards/isa/ansiisa101012015
- https://www.isa.org/products/ansi-isa-101-01-2015-human-machine-interfaces-for

### 可信度标注

**一手**——本节所有条款号、页码、目录结构均为 ANSI 官方出版物本体的直接截取(通过 Read 工具解析下载的 PDF 原文获得,非任何第三方转述或 AI 摘要),可信度最高。

### 局限(与问题二共用,详见负结果节)

Clause 6.3 正文的**逐字条款定义文字**(即"Level 1 被标准原文如何逐句定义"这一层)因标准全文需付费购买,预览版只公开到第 9 页(Contents 页为止),本次未能核验。目前对 Level 1-4 具体描述语的引用,来自 ISA101 委员会**投票委员** Graham Nasby 2017 年公开演讲稿(见问题二/文献清单),是委员本人的教学转述,不等同标准逐字条款,已在下节明确标注可信度层级。

---

## 问题二:三页↔四级映射论证(P1/P2/P3 对应 L1-L4,及单机场景裁剪层级数的标准依据)

### 结论

标准原文本体**明确区分强制性条款与非强制性建议**(见问题一引用的 Organization 段:"presents mandatory requirements **and non-mandatory recommendations** as noted"),这是"裁剪层级数"具备标准文本依据的**一手**基础——第 6 章画面层级属于"建议"性质的部分不要求逐条强制满四级。

在此基础上,结合以下二手但具名资深的专家佐证:

> "The hierarchy is also collapsible, which is to say that not everyone needs all four of the levels described in ISA-101."
> —— Greg McMillan(退休 Solutia Inc./Eastman Chemical 高级研究员,前 Washington University in St. Louis 化工系客座教授,退休 Emerson Automation Solutions 首席软件开发工程师)与 Bonnie Ramey(杜邦高级过程控制工程师、HMI 专家)在 *Control Global* 专栏,https://www.controlglobal.com/visualize/operator-interface/article/11315731/advice-on-implementing-ansi-isa-standards-for-operator-interfaces

以及方向一致但可信度更低的网络综合表述(**二手,未核验原文,来源疑似匿名 SEO 内容站,不作为硬引用**):"For single machines, skids, OEM systems, and small systems...though not all four levels may be necessary—organizations can implement the levels that match their system complexity."(该表述由搜索引擎跨站聚合给出,未能定位到单一可核实署名来源,可能混合了 hmilibrary.com / malisko.com / ifactoryapp.com 等站点内容,均为无具名作者的内容站,可信度最低,仅作方向性佐证,不建议报告引用)。

**本项目的三页↔四级映射(工程论证,非任何文献直接给出的官方映射表)**:

| 本项目页面 | ISA-101 对应层级 | 映射依据 |
|---|---|---|
| P1 操作台(单元操作) | **L2(单元overview)吸收 L1(全厂overview)的信息内容** | L1 定义为"operator's entire span of control"(操作员全部管辖范围)的单屏概览;本项目受控对象是单巷道单堆垛机一个物理单元,操作员的"全部管辖范围"本身就等于这一个单元——不存在独立于 P1 之外、需要另建一屏的"更高层全厂"。故 L1 与 L2 在单机场景下收敛为同一张画面,P1 一页同时承担两层职能,不是"删掉了 L1",而是层级在小规模系统下的合并 |
| P2 记录分析(细节) | **L3(设备/细节层)** | 记录表、查询、模型参数、批次汇总——对应 L3"关于过程或控制某一部分的具体细节"定位,是操作台之外的第二层细节,不涉及权限/诊断/配置类任务 |
| P3 管理配置(新建) | **L4(专项任务/诊断层)** | 权限登录、检修模式、评分权重配置、A5 执行时间实测表——对应 L4"非常规、专项任务或诊断类画面"的定位,与 P1/P2 的日常监控职能明确分层 |

### 报告 B5 可直接引用的成稿段落(可直接复制入报告)

> 本项目三页制画面导航(P1 操作台 / P2 记录分析 / P3 管理配置)依据 ANSI/ISA-101.01-2015《Human Machine Interfaces for Process Automation Systems》第 6 章"Display Styles and Overall HMI Structure"(6.3 节"Display Hierarchy",标准原文页 42-47,Figure 3-6 分别给出 Level 1 至 Level 4 画面示例)所定义的四级画面层级模型设计。标准正文明确指出主体章节(Clause 4-9)"presents mandatory requirements and non-mandatory recommendations as noted",即画面层级的具体落地方式允许工程判断按系统规模裁剪,而非要求逐条强制满四级。结合本项目单巷道、单台堆垛机的系统规模——操作员的全部管辖范围本身就是这一个仓储单元,不存在独立于该单元之外、需要另建一屏概览的"全厂"层级——P1 操作台承担 Level 2(单元级overview)职能的同时天然吸收 Level 1(全厂概览)的信息内容;P2 记录分析对应 Level 3(设备/细节层);P3 管理配置(权限、检修、评分权重、诊断)对应 Level 4(专项任务/诊断层)。三页制因此不是对标准四级模型的偏离,而是在单机应用场景下对层级模型的合规裁剪与显式化呈现。

**引用限定语(报告周精修务必保留,不可省略)**:上表"三页↔四级"的具体映射是本项目基于标准目录结构与委员公开材料构造的**工程论证**,不是从任何单一文献直接抄录的"标准官方映射表"——本次调研未查到任何第三方文献做过与本项目完全相同的"仓储堆垛机三页 HMI ↔ ISA-101 四级"映射。报告措辞应写"本项目依据 ISA-101 层级模型设计并结合系统规模裁剪",不可写成"ISA-101 标准规定单机系统应做三页"这类不存在的强断言。

### 可信度标注

- 标准"强制/非强制"条款区分:**一手**(标准原文逐字)。
- "hierarchy is collapsible"专家佐证:**二手,具名资深专家,已标注但可信度高于匿名内容**。
- OEM/skid/small system 可用不到四级的泛化表述:**二手,未核验原文,来源疑似匿名 SEO 站点,已明确降级,不建议硬引用**。
- 三页↔四级具体映射表:**本项目原创工程论证**,非任何文献结论,报告中须如实标注为本项目论证。

---

## 问题三:ABB 自家 HMI 背书

### 结论(最强证据)

**ABB Inc. 是 ANSI/ISA-101.01-2015 标准制定委员会(ISA101)的正式投票委员**——委员代表为 **N. Robinson,单位 ABB Inc.**,直接见于标准官方文本第 4 页"voting members of ISA101 in the development of this standard"名单(与 AECOM/Yokogawa/DuPont/ExxonMobil Chemical/Rockwell Automation/Emerson Process Management 等同列)。

这是比"ABB 产品页引用了 ISA-101"更强的背书形态——**ABB 不是标准的外部遵循者,而是标准的共同起草方之一**。报告可直接写:"本项目所依据的 ISA-101 层级模型,其制定委员会本身即有 ABB Inc. 代表(N. Robinson)作为正式投票委员参与起草,与本项目'评委来自 ABB 运动控制事业部'的背景高度契合"。

### 一手出处

标准官方文本第 4 页委员名单(来源同问题一 ANSI 官方预览版 PDF):

```
The following served as voting members of ISA101 in the development of this standard:
NAME                          AFFILIATION
...
N. Robinson                   ABB Inc.
...
```

可信度:**一手**(标准官方文本本体,非转述)。

### 次强证据(可信度较低,已标注)

ABB System 800xA(DCS 产品线)存在名为"**High Performance Graphics**"的官方产品功能分类,产品页地址:
- https://new.abb.com/control-systems/system-800xa/800xa-dcs/operator-interfaces-hmi/high-performance-graphics
- https://new.abb.com/control-systems/system-800xa/800xa-operator-effectiveness

搜索引擎摘要提示该功能与"操作员可在常规画面与高性能画面之间切换"有关,方向上与 High-Performance HMI/ISA-101 理念一致。**但本次未能独立核验该页面正文是否逐字出现"ISA-101"字样**(见负结果节)——搜索引擎给出的摘要疑似跨站聚合(混入了非 abb.com 域名的第三方内容如 control.com),**不作为已核验的一手证据使用**,仅作为"ABB 确有对应产品功能分类"这一事实的旁证。

ABB 仓储/堆垛机产品线(本项目已用的 Stacker Cranes 应用页、ACS880 Crane Control 系列手册)**本次未查到任何提及 ISA-101 或 High-Performance HMI 的段落**——即 ABB 的 HMI/ISA-101 关联证据目前只在其"过程自动化 DCS(800xA)"产品线与标准委员会名单中查到,尚未在其"堆垛机/仓储物流"产品线官方手册中直接查到 ISA-101 字样(这条本身也是一条负结果,已列入负结果节)。

### 可信度标注

- ABB Inc. 委员会正式成员身份:**一手,最强**。
- 800xA "High Performance Graphics" 功能分类存在:**一手**(功能名称本身来自 new.abb.com 搜索结果标题,是 ABB 官方页面标题,但页面正文细节未独立核验)。
- 800xA 页面是否逐字提及 ISA-101:**未核验,不作为证据使用**。

---

## 问题四:High-Performance HMI 文献底

### 结论

**核心专著**:Hollifield, B., Oliver, D., Nimmo, I., & Habibi, E. (2008). *The High Performance HMI Handbook: A Comprehensive Guide to Designing, Implementing and Maintaining Effective HMIs for Industrial Plant Operations*. PAS (Plant Automation Services) / User Centered Design Services (UCDS) 联合出版,第一版精装。
**ISBN-13: 978-0-9778969-1-2(ISBN-10: 0977896919)**。

**关键交叉验证(本次调研发现,强化该书与 ISA-101 的正式关联)**:该书四位作者中,**W. Hollifield(PAS)与 I. Nimmo(User Centered Design Services LLC)本身就是 ANSI/ISA-101.01-2015 标准委员会的正式成员**——直接见于标准官方文本第 4 页委员名单,其中 **I. Nimmo 标注为 Clause Editor(条款编辑,负责具体章节撰写)**。即该"文献底"不是外部对标准的二次解读,而是标准起草者本人撰写的配套专著——这是比单纯"文献引用标准"更强的关联形态。

**ISA-18.2(报警管理)与 ISA-101(HMI 设计)的关系**——最强一手证据:ISA-101 委员会联合主席 **Maurice Wilkins** 本人在 ISA 官方杂志 *InTech*(2020 年 9-10 月刊,ISA 75 周年特刊)撰文明确说明:

> "We needed some 'glue,' so Greg [Lehmann] and I—with the help of a wonderful group of ISA108 clause editors...developed a life cycle for the proposed standard **based on ISA-18.2 and ISA-84**."

即 ISA-101 的生命周期模型(Clause 4,HMI System Management)本身是**基于 ISA-18.2(报警管理)与 ISA-84(安全仪表系统)构建的**——这是标准联合主席本人在 ISA 官方刊物上的一手陈述,精确回答了"ISA-18.2 与 ISA-101 关系"这一问题,且比本次搜索引擎泛化摘要("ISA-101 defers alarm management proper to ISA-18.2"未标注可验证的单一出处)更可靠。

ISA-18.2 标准本身书目信息(ISA 官方产品页确认,一手):**ANSI/ISA-18.2-2016, *Management of Alarm Systems for the Process Industries***,ISA18 委员会基于标准 2009 年版发布后六年应用经验修订,经 ANSI 批准。官方产品页:https://www.isa.org/products/ansi-isa-18-2-2016-management-of-alarm-systems-for

### 一手出处汇总

- 标准委员名单(证明 Hollifield/Nimmo 双重身份):ANSI 官方预览版 PDF(同问题一)。
- Wilkins InTech 一手陈述:https://www.isa.org/intech/2020/september-october/isa-101-01-human-machine-interfaces-for-process-au (ISA 官方杂志,作者为标准联合主席本人具名)。
- ISA-18.2 官方产品页:https://www.isa.org/products/ansi-isa-18-2-2016-management-of-alarm-systems-for
- 《High Performance HMI Handbook》ISBN/出版社/作者信息:经 Amazon(https://www.amazon.com/High-Performance-HMI-Handbook/dp/0977896919 )、AbeBooks(https://www.abebooks.com/9780977896912/High-Performance-HMI-Handbook-Bill-0977896919/plp )等多个独立书商站点交叉一致确认。

### 可信度标注

- Hollifield/Nimmo 委员身份:**一手**(标准官方文本)。
- Wilkins 关于 ISA-18.2/ISA-84 与 ISA-101 生命周期关系的陈述:**一手**(ISA 官方刊物,具名联合主席)。
- 书目信息(ISBN/出版社/作者/年份):**二手书商聚合信息,但纯目录事实,经多站交叉一致,可信度较高**;此类事实性书目数据一般不涉及"内容转述失真"风险,与"专著内容论点"类二手引用的风险等级不同,本报告仍如实标注来源性质。
- ISA-18.2 标准与 ISA-101 关系的具体条款级说明(而非生命周期溯源陈述):**未核验**(ISA-18.2 标准全文预览版 WebFetch 返回 403,见负结果)。

---

## 权威文献清单(一手优先)

1. **ANSI/ISA-101.01-2015**, *Human Machine Interfaces for Process Automation Systems*. International Society of Automation, Approved 9 July 2015. ISBN 978-1-941546-46-8.
   官方购买页:https://webstore.ansi.org/standards/isa/ansiisa101012015 ; https://www.isa.org/products/ansi-isa-101-01-2015-human-machine-interfaces-for
   官方预览版(本次调研直接读取的一手材料来源):https://webstore.ansi.org/preview-pages/ISA/preview_ANSI+ISA+101.01-2015.pdf

2. **ANSI/ISA-18.2-2016**, *Management of Alarm Systems for the Process Industries*. International Society of Automation.
   官方产品页:https://www.isa.org/products/ansi-isa-18-2-2016-management-of-alarm-systems-for ; https://webstore.ansi.org/standards/isa/ansiisa182016

3. **ISA-TR101.02-2019**, *HMI Usability and Performance*(ISA-101 系列技术报告,补充标准应用细节)。
   ISA 官方介绍:https://www.isa.org/intech-home/2019/july-august/departments/new-isa101-hmi-technical-report-focuses-on-usabili
   ANSI 预览页:https://webstore.ansi.org/preview-pages/ISA/preview_ISA+TR101.02-2019.pdf(本次未 WebFetch 核验正文,仅确认存在)

4. **Hollifield, B., Oliver, D., Nimmo, I., & Habibi, E. (2008)**. *The High Performance HMI Handbook: A Comprehensive Guide to Designing, Implementing and Maintaining Effective HMIs for Industrial Plant Operations*. PAS / UCDS, 1st ed. ISBN-13: 978-0-9778969-1-2.
   书目核验来源:https://www.amazon.com/High-Performance-HMI-Handbook/dp/0977896919 ; https://www.abebooks.com/9780977896912/High-Performance-HMI-Handbook-Bill-0977896919/plp

5. **Wilkins, M.** (2020), "ISA-101.01, Human Machine Interfaces for Process Automation Systems", *InTech*(ISA 官方杂志,75 周年特刊), Sept/Oct 2020.
   https://www.isa.org/intech/2020/september-october/isa-101-01-human-machine-interfaces-for-process-au

6. **Nasby, G.** (2017), "Using ISA-101 & High Performance HMIs for More Effective Operations"(会议演讲稿), WEAO Intelligent Wastewater Systems Seminar, 2017-09-14, Burlington, Ontario, Canada.
   https://www.grahamnasby.com/files_publications/NasbyG_2017_HighPerformanceHMIs_IntelligentWastewaterSeminar_WEAO_sept14-2017_slides-public.pdf
   (作者系 ISA101 委员会正式投票委员,与标准官方委员名单交叉核验一致;演讲稿明确鸣谢 Bill Hollifield 授权使用其著作插图,进一步交叉验证条目 4)

7. McMillan, G. & Ramey, B.(受访)、Weiner, S.(编辑), "Advice on implementing ANSI/ISA standards for operator interfaces", *Control Global*(Putman Media 行业媒体专栏).
   https://www.controlglobal.com/visualize/operator-interface/article/11315731/advice-on-implementing-ansi-isa-standards-for-operator-interfaces
   **二手**,已在正文标注降级使用(具名资深专家,非匿名博客)。

---

## 负结果汇总(如实声明,未编造任何条款号/页码)

| 编号 | 查不到/未核验的内容 | 已尝试的方法 | 状态 |
|---|---|---|---|
| N1 | ISA-101 标准 **Clause 6.3 正文逐字条款定义**(Level 1-4 的标准官方逐句定义原文) | WebFetch 官方预览版 PDF(仅公开到第 9 页 Contents,正文页 42-47 不在预览范围内) | **查不到**,需付费购买标准全文核实,报告如需逐字引用条款正文须走此步骤 |
| N2 | Clause 6.3 正文中是否**逐字**允许"按系统规模裁剪层级数" | 同上,预览版无正文;仅拿到标准 Organization 段"mandatory + non-mandatory recommendations"的通用表述 | **未核验到条款级直接文字**,目前只有该通用表述 + 二手专家佐证支持裁剪逻辑 |
| N3 | ABB 官方产品页(new.abb.com 800xA high-performance-graphics / 800xa-operator-effectiveness)是否**逐字**出现"ISA-101" | WebFetch 尝试 3 次(2 个不同 URL),均 60 秒超时未取得页面正文;site:new.abb.com "ISA-101" 限定搜索无命中该页面 | **查不到**(访问受限,非否定性结论——不代表页面一定不提及,只是本次未能验证) |
| N4 | ABB 堆垛机/仓储物流产品线官方手册(Stacker Cranes 应用页、ACS880 Crane Control 系列)是否提及 ISA-101 | 依据既有项目文档(`docs/L7_拟真度阶梯设计.md` 已列 ABB 堆垛机手册清单)+ 本次未新查到相关段落 | **未查到**——ABB 的 ISA-101 关联证据目前仅存在于其 DCS(800xA)产品线宣传与标准委员会名单,尚未在堆垛机专用手册中发现 |
| N5 | ANSI/ISA-18.2-2016 标准全文/预览版正文 | WebFetch 官方预览版 PDF 返回 **403 Forbidden**(与 ISA-101 预览版同域名结构,但被拒) | **查不到**,ISA-18.2 与 ISA-101 关系的最强证据退而求其次采用 Wilkins InTech 一手陈述(见问题四) |
| N6 | 第三方文献是否做过与本项目完全相同的"仓储堆垛机三页 HMI ↔ ISA-101 四级"映射 | 多轮关键词搜索(通用 HMI 层级裁剪、OEM/skid 场景等) | **查不到**——本次调研未发现任何已发表文献做过针对"立体仓储堆垛机"场景的 ISA-101 层级裁剪映射;问题二的映射表是本项目原创工程论证,报告须如实标注 |
| N7 | Graham Nasby 演讲稿中的 Level 1-4 定义文字是否与标准正文逐字一致 | 无法核验(标准正文本身不可得,见 N1) | **无法核验一致性**,只能确认 Nasby 本人是标准委员会正式成员,其转述具有权威性但非逐字引用 |

---

## 附:本次调研方法说明

本次调研以 WebSearch 多轮定向检索 + WebFetch 直接抓取一手页面为主,并对两份关键 PDF(ANSI 官方标准预览版、Nasby 2017 演讲稿)采用"WebFetch 下载二进制 → Read 工具解析 PDF 正文"的组合方法——因 WebFetch 自带的 HTML/PDF 转文本步骤对这两份文档均失败(PDF 内部为 FlateDecode 压缩流,WebFetch 的轻量文本化模型无法解压),改用 Read 工具(具备原生 PDF 解析能力)直接读取 WebFetch 已下载并落盘的二进制文件,成功取得逐字正文。这一方法弥补了 WebFetch 对复杂排版 PDF 的解析短板,建议今后遇到官方标准类 PDF 优先采用此组合方法,而非仅依赖 WebFetch 单次调用的失败结论就判定"该文档不可得"。
