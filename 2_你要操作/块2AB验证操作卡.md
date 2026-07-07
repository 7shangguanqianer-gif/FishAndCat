# 块2 AB 验证操作卡(0707;你对照执行,验证块1-2 的 PLC 成果)

> 目的:在 Automation Builder(AB)里把块2 更新的 PLC 代码跑一遍,确认 iPassed=40/0。
> 我无法本地编译 ST(没有 AB),所以这一步只能你来跑;我已离线用 consistency_probe
> 证明"代码忠实移植则会绿"。跑完把结果(iPassed 值+任何红的用例名)发我。

## 0. 前置(1 分钟)

1. 先关掉 Word 里开着的 `2_你要操作\官方群提问清单.docx`(它锁住了没法重生成);
2. 命令行跑 `python tools/make_user_docs.py`(补齐用户层 docx,让 doc_check 变绿)。

## 1. 同步块2 改动的 PLC 文件到 AB

块2 改了两个文件,需要在 AB 里更新(改内容只在 .st 源,AB 里粘贴对应段落):

### 1a. `07_GVL_Data_generated.st`(生成文件,块2 新增了 T25 数据)

- **新增一个 DUT**:`ST_AwraCell`(TYPE 段第二个,在 ST_TestVec 之后)——
  Application 右键→添加对象→DUT,命名 `ST_AwraCell`,粘贴那段 STRUCT(Id/X/Y);
- **更新 GVL_Data**:整段 `VAR_GLOBAL CONSTANT`(多了 N_AWRA/AWRA_PLACED/LAM_F/W/V/
  MAX_LS_ROUNDS)+ `VAR_GLOBAL`(多了 aAwraExpect 数组 + AWRA_EXPT/ENERGY/COG)重新粘贴;
- FC_LoadDemoGoods 不变。

### 1b. `06_PRG_Test.st`(整段替换 PRG_Test 内容)

- 整个 PRG_Test 的 VAR 段 + 逻辑重新粘贴(变化:N_CASES=40、数组[1..40]、新增
  fbAssign/fbImprove/fbStats 三个 FB 实例 + iAwraPosDiff 变量;新增 T25-T40 用例)。

> 提示:07 是"生成文件"——以后改了 sim 的评分/参数,必须重跑 `python sim/export_st_vectors.py`
> 再把 07 粘回 AB,否则 T19/T20/T25 会红(这是设计出来的护栏,不是 bug)。

## 2. 跑测试

1. 菜单 在线→仿真(Simulation)勾选→登录(Login)→运行(Run);
2. 在 PRG_Test 里把 `xRunTests` 置 `TRUE`(它会自动复位);
3. 看这几个变量:
   - **`iPassed` 期望 = 40**
   - **`iFailed` 期望 = 0**
   - `xAllPass` 期望 = TRUE
   - **`iAwraPosDiff` 期望 = 0**(T25 终局布局与 sim 逐位一致的信息量)

## 3. 绿了什么样 / 红了怎么排

- **全绿**:iPassed=40, iFailed=0, xAllPass=TRUE, iAwraPosDiff=0 → 块2 PLC 侧验证通过;
- **红了**:看 `sLastFail`(显示最后一个失败用例名,如 `T30`),对照排错:
  - **T19/T20/T22/T25 红**:大概率忘了重新粘贴 07(改了 sim 没同步 ST)——重跑 export 再粘;
  - **T24 红**:预占格数,确认 iRule=3 走 sum 口径(x+y 被3整除=133);
  - **T25 红且 iAwraPosDiff>0**:AWRA 终局布局与 sim 不一致——把 iAwraPosDiff 值发我;
  - **T26-T40 红**:边界用例,把红的编号发我(每个用例注释里写了测什么)。

## 4. 演示流程快速验证(可选,确认交互闭环)

CmdReset → CmdLoadDemo(载入20件)→ SelStrategy:=3(AWRA)→ CmdRunAssign →
观察 fbAssign/fbImprove 分片推进(xBusy→xDone)→ 看 GVL_WH.stStats.ViolCnt **必须=0**。

## 5. 把结果发我

只需告诉我:**iPassed 是多少 / 有没有红的用例(编号)/ iAwraPosDiff 是多少**。
- 全绿 → 我们定 FB_GoodsInput 取舍,然后开块3;
- 有红 → 我按你给的用例编号定位修复(大概率是 07/06 粘贴同步问题)。
