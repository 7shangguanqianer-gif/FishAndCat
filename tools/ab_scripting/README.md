# AB 工程自动化管线(ScriptEngine 无头同步,2026-07-06 建成)

> **证据边界（0712）**：59/0是最后一次有AB读回依据的基线。当前工作区声明75项：T60-T69为真实断言，T70-T75为恒TRUE预留，并含CB/TOB/lex新增源码；本轮未AB复测，不得把源码计数、源码存在或新增断言当新测试证据。

**一条命令可把 `plc/*.st` 源码同步进AB工程、编译、保存并在线跑当前PRG_Test；本轮未执行：**

```powershell
powershell -File tools\ab_scripting\ab_sync.ps1            # 全套(约 3-5 分钟)
powershell -File tools\ab_scripting\ab_sync.ps1 -SyncOnly  # 只同步+编译,不在线测试
```

历史59项基线绿灯：`Compile complete -- 0 errors` + `iPassed = INT#59, iFailed = INT#0`（仅干净初态+当前参数）。任何新计数必须先消除占位断言并真实跑AB，不能沿用此历史绿灯。
**前提:AB 没有被人工开着**(工程文件独占);跑完想人工看,再打开 AB 即可。

## 文件(0711 治理后:根目录=现役管线,archive/=考古)

| 文件 | 作用 |
|---|---|
| ab_sync.ps1 | 入口包装(两步串联+绿灯判定;绿灯现为 **iPassed=59**,0711 A2-A4+C1/C2/C6 扩容) |
| sync_st.py | 核心:解析 .st 源→46 对象(POU/GVL/DUT)→逐对象 replace→缺席自动创建→build→save;**0711 护栏:源内 POU 未登记 MAP 即报 NOT_IN_MAP**(防"忘登记→静默跳过→not defined 级联",当日 43 错实案) |
| run_test.py | 在线闭环:login(仿真)→start→读回 iPassed/iFailed |
| run_probe.ps1 | 通用一次性 ScriptEngine 脚本跑手(-Script x.py -Result y.txt) |
| audit_pages.py + analyze_audit.py | 画面审计对:dump 两页全元素几何 TSV → 外部三查(越界/重叠/文字预算) |
| **archive/**(63 件) | 0706-0711 战役的一次性修复枪/探针/结果留档(fix_*/relayout_*/probe_*/dump_* 等)。只读考古,不再维护;需要 XML dump 时跑 archive/dump_visu*.py(产物已 gitignore);measure_l4c.py=0711 A5 四组实测(结果落 docs/A5执行时间实测_0711.md,复跑先拷回根目录) |

## 治理规约(0711 立)

- **可再生大文件不入库**:ScriptEngine XML dump(*.xml 已 gitignore)、AB 编译缓存(白名单模式)、sim/out+figs;
- **一次性脚本执行完→归 archive/**,根目录只留可复用管线;
- **实验区规约**:类 `F:\abb_wh_spike` 的独立实验目录,收编精华(脚本+README)进 work 后,整目录 tar.gz 归档留底、原目录删除(0711 实例:visu_native → tools/visu_gen 27 件 + spike 下 20.7MB tar.gz);
- 画面类脚本交付三段律:生成→GUI 洗→在线长跑(visu_gen/README §5)。

## 命门与教训(0706 首建实录,含一次三小时排障)

1. **`.project` 是加密二进制**(熵 8.0),永远不要手改;唯一正道=ScriptEngine API。
2. 无头命令行:`AutomationBuilder.exe --profile="Automation Builder 2.9" --noUI --runscript="x.py"`
   ——**--profile 必填**(缺了静默退出 exit=1);脚本语言 IronPython 2.7(无 f-string)。
3. `create_pou` 三坑:①FUNCTION 必须传 return_type ②language 必须显式 `ImplementationLanguages.st`
   (默认吃 profile 默认语言)③创建后才能 replace 文本。
4. **排障最大陷阱:编译错误 `'TO' expected instead of 'r'` 之类"碎 token 雨"不是管线坏,
   是源码变量名撞 IEC 保留字**——`r`/`s` 是置位/复位限定符,不可作变量名(FB_VisuRefresh
   曾用 `r` 做循环变量,从未编译过所以一直潜伏;GUI 里同样会炸,只是没人贴过)。
   写 ST 用描述性变量名,单字母只信 c/i/k/x/y。
5. 对象文本 replace 后以 `TextBlobForSerialisation` 形态入库——这是正常持久化形态,
   编译器直接消费,别被 export_native 的 XML 吓到。
6. 验证新代码真进了运行时的铁证=在线读回只有新代码才有的真实断言结果；单改`N_CASES`或把占位项设TRUE不构成证据。
   "编译 0 错误"本身不证明编译的是新文本。

## 与信箱批次的分工(更新后)

- **口径/代码类同步(原批次 D 类)→ 本管线一条命令,不再发 Codex**;
- **GUI 画面搭建**(可视化元件/Multiply visu element/录屏)→ 仍走 Codex 批次(操作卡);
- **任务监视页抄表**(批次 B 类,需人眼读 Monitor 页)→ 仍走 Codex 批次。
