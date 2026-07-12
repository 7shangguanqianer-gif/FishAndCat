# Factory I/O 上手教程:在真正的仿真软件里跑我们的仓库(0706)

> 你要学的不是"看动画",而是**数字孪生的完整闭环**:3D 虚拟工厂(Factory I/O)← 工业通信(OPC UA/Modbus)→ 真实 PLC 程序(我们的 CODESYS/AC500 代码)。
> 三课设计,每课有验收点;总时间盒 **1-1.5 天**(学习支线,别吃主线 R1/批次 C)。

## 0. 它是什么、和我们的 Python 动画什么关系

- Factory I/O = 葡萄牙 Real Games 出的 3D 工厂仿真软件:内置传送带/传感器/机械手/**堆垛机立体仓库**等部件,有物理引擎(货箱会掉、会堵、会被光电开关挡住);它自己不跑逻辑——**逻辑由外接的 PLC 跑**,它只当"虚拟工厂"。
- 与我们已有产出的分工:Python 混合渲染动画=**呈现层**(讲算法故事,数据同源可控);Factory I/O=**控制验证层**(证明我们的 ST 代码在带物理的环境里真能开动一台堆垛机)。两者不互替。
- 已知硬约束(0706 调研,docs/待拍板_可视化3D与推进_0706.md):内置仓库场景 **54 格位**,不是我们的 400 格——所以它的定位是**学习+决赛展望的孪生验证平台**,初赛演示载体仍是已拍板的录屏动画。

## 第一课:装好+玩转内置仓库场景(约 2 小时)

**目标:不连 PLC,先把软件本身玩明白。**

1. 注册+下载:https://factoryio.com/ → Download → 注册账号 → 装最新版;首次启动登录账号激活 **30 天试用(= Ultimate 全功能)**。
   - 试用条款(官方社区,明说可用于学校作业):https://community.factoryio.com/t/student-free-trial-terms-and-conditions/2147
2. 打开内置场景:`File → Open` → 场景库选 **Automated Warehouse**(自动化立体仓库)。
   - 场景说明(先通读一遍):https://docs.factoryio.com/manual/scenes/automated-warehouse/
3. 学三种相机(录屏运镜的基本功):
   - **Orbit** 轨道相机(默认):右键拖=旋转,滚轮=缩放,中键拖=平移;
   - **Fly** 飞行相机:自由飞越,WASD 移动+右键转向;
   - **First Person** 第一人称:在车间里"走路"。
   - 文档:https://docs.factoryio.com/manual/navigation/ ;演示视频:https://www.youtube.com/watch?v=gwj1-UnQvmo
4. 先让它自己动起来:点顶栏 **RUN**,再打开 `File → Drivers`(快捷键 F4),Driver 选 **None(手动)**——左侧是传感器(只读),右侧是执行器(可点):手动勾选堆垛机的目标位/移动位,观察它怎么响应。
5. **验收点**:①能用三种相机各录一段 10 秒屏(用 Win+G 或 OBS);②说得出这个场景有哪几类传感器/执行器(截图 Drivers 窗口发我)。

## 第二课:连通 CODESYS 软 PLC(约半天,核心课)

**目标:官方标准路径先走通——CODESYS Control Win(软 PLC)+ OPC UA,保证第一次连接就成功。**
(为什么不直接连 AB/AC500:AC500 **PC 仿真模式**的 OPC UA/Modbus 服务能力是未验证项,第一次学习要走官方铺好的路,变量最少;AC500 挑战放第三课。)

1. 装标准 CODESYS(免费):https://store.codesys.com/ 注册下载 **CODESYS Development System V3**(含 Control Win 软 PLC,SP18 以上)。
   - 它和你熟悉的 AB 是同族——AB 就是 ABB 定制的 CODESYS,界面逻辑一致,ST 语法完全相同。
2. 照官方教程逐步做(教程带截图,以它为准):
   - **CODESYS + OPC UA 教程**:https://docs.factoryio.com/tutorials/codesys/setting-up/codesys-opc-ua-sp18/
   - 要点顺序:CODESYS 新建工程(Control Win)→ 建 GVL 变量 → Symbol Configuration 勾选变量发布 → 下载运行软 PLC → Factory I/O `Drivers → OPC Client UA` → 填 endpoint(教程给的本机地址)→ CONNECT → 左右两栏把场景的传感器/执行器**映射**到 PLC 变量。
3. 写最小控制程序(ST,就 10 行):比如"光电传感器挡住 → 传送带停"。先用 **Sorting by Height (Easy)** 这类简单场景练映射,再回 Automated Warehouse。
4. 控制堆垛机:Automated Warehouse 场景的堆垛机接口(读官方场景页的 I/O 表):目标格位号(整数)+ 移动指令 + 到位/载货反馈。写一段 ST:按顺序把 3 个货箱送进 3 个不同格位。
5. **验收点**:录一段 30 秒屏——你的 ST 代码驱动堆垛机连续入库 3 箱;把 ST 片段发我,我讲评(这段代码就是我们 FB_Warehouse 逻辑的"外部世界版")。

## 第三课(挑战课,可选):接上我们真正的项目

**目标:把第二课的"玩具逻辑"换成我们的真算法。三选一,难度递增:**

- **3a. 移植评分算法**:把我们 03_Functions.st 里的 FC_CalcTravelTime/评分函数拷进 CODESYS 工程,让堆垛机按**我们算法选的格位**入库(54 格内做个小映射表)。这一步的意义:算法在带物理引擎的环境里闭环。
- **3b. AC500 直连实验**(未验证项,当实验做):AB 里我们的工程开 PLC 仿真 → 查 AC500 V3 的 OPC UA Server/Symbol 配置在仿真模式是否可用 → Factory I/O 指向它。**成败都是有价值的结论**(成=决赛展望里写"已验证 AC500 直连孪生";败=记录卡点,改用 Control Win 桥接)。
- **3c. 扩容实验**(对应你之前的 Q4 倾向):自定义场景里拖货架搭 20×20,试堆垛机寻址上限——通了,决赛就有"400 格真孪生"的路线图。
- **验收点**:任一条的实验记录(哪怕是"卡在哪一步"的截图)——按项目规矩,负结果也是结果。

## 常见坑(先打预防针)

1. 试用期从**激活日**起算 30 天——别提前太久激活,建议第一课当天再激活(倒推:8/26 前留完整窗口);
2. OPC UA 连不上先查三件:软 PLC 是否 RUN / Symbol Configuration 是否下载 / Windows 防火墙放行;
3. Factory I/O 的 RUN 和 CODESYS 的 RUN 是两个开关,都要开;
4. 场景文件另存到 F:\abb_wh_work\factoryio\(新建目录),别存默认位置——纳入我们的 git 备份线;
5. 显卡要求不高,但笔记本记得插电+高性能模式,物理引擎掉帧会让堆垛机"漂移"。

## 学到什么(这条支线的知识账)

- **数字孪生三层**:数据/算法层(我们的 sim)— 控制层(PLC/ST)— 物理呈现层(Factory I/O 或我们的动画)——三层解耦、接口标准化,这就是工业 4.0 教材里"虚拟调试 (Virtual Commissioning)"的完整小闭环;
- **OPC UA**:工业界的"USB 协议"——跨厂商设备互认变量的标准;简历/答辩里"用 OPC UA 做过虚拟调试"是硬通货;
- 举一反三:同样的闭环换个壳=汽车 HIL 台架(ECU=PLC,车辆动力学软件=Factory I/O)、电网 RTDS 半实物仿真。
