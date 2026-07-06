# AB 工程自动化管线(ScriptEngine 无头同步,2026-07-06 建成)

**一条命令把 `plc/*.st` 源码同步进 AB 工程、编译、保存、在线跑 24 用例:**

```powershell
powershell -File tools\ab_scripting\ab_sync.ps1            # 全套(约 3-5 分钟)
powershell -File tools\ab_scripting\ab_sync.ps1 -SyncOnly  # 只同步+编译,不在线测试
```

绿灯标志:`Compile complete -- 0 errors` + `iPassed = INT#24, iFailed = INT#0`。
**前提:AB 没有被人工开着**(工程文件独占);跑完想人工看,再打开 AB 即可。

## 文件

| 文件 | 作用 |
|---|---|
| ab_sync.ps1 | 入口包装(两步串联+绿灯判定) |
| sync_st.py | 核心:解析 8 个 .st 文件→34 对象(POU/GVL/DUT)→逐对象 replace(decl+impl)→缺席对象自动创建(**必须显式传 ImplementationLanguages.st + FUNCTION 的 return_type**)→build→0 错才有意义→save。本地 CPython 直接跑=只测解析不碰工程 |
| run_test.py | 在线闭环:login(仿真)→start→set_prepared_value 置 PRG_Test.xRunTests→读回 iPassed/iFailed/sLastFail |
| probe/check_build/dump_pou/…py | 诊断工具箱(排障时单发使用,方法同 ab_sync 内的调用方式) |

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
6. 验证新代码真进了运行时的铁证=在线读回只有新代码才有的值(如 T24 的 iPassed=24),
   "编译 0 错误"本身不证明编译的是新文本。

## 与信箱批次的分工(更新后)

- **口径/代码类同步(原批次 D 类)→ 本管线一条命令,不再发 Codex**;
- **GUI 画面搭建**(可视化元件/Multiply visu element/录屏)→ 仍走 Codex 批次(操作卡);
- **任务监视页抄表**(批次 B 类,需人眼读 Monitor 页)→ 仍走 Codex 批次。
