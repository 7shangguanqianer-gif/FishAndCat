# AB 工程自动化(ScriptEngine)可行性调查(2026-07-06)

> 触发:用户问"能不能让 Claude 直接改 AB 文件,省掉口径切换重贴的手工步骤"。
> 结论:**手改 .project 二进制=不可行(已证);ScriptEngine 无头自动化=组件齐全、技术可行,
> 但落地前有一道"脚本许可是否激活"的闸门需一次测试确认。**

## 1. 为什么不能手改 .project(已证伪)

`plc/AB_Project/ABB_WH.project` 是全压缩/加密专有二进制:
- 魔数 `2389ed33`(非 zip/OLE/gzip/SQLite);首 64KB 熵 = **8.00 bits/byte**(满值=压缩或加密);
- 全文 grep `MOD 3`/`iPreRule`/`FC_IsPresetOccupied` **命中 0**——ST 源码不以明文存在;
- 旁有 `.precompilecache`/`.compileinfo`/`.bootinfo` 编译缓存+GUID 引用,手改源码后必失配。
→ 任何字节级修补=大概率损坏工程,违反文件安全红线。**否决。**

## 2. ScriptEngine 无头自动化:组件盘点(全部命中)

| 组件 | 路径 | 作用 |
|---|---|---|
| 主程序 | `C:\Program Files\ABB\AB2.9\AutomationBuilder\Common\AutomationBuilder.exe` | 无头入口(--runscript) |
| 脚本插件 | `.../PlugIns/dc937c18-.../4.1.0.0/ScriptEngine.plugin.dll` | CODESYS ScriptEngine |
| 解释器 | `.../LacBinaries/GAC_MSIL/IronPython/2.7.12.0/IronPython.dll` | 脚本语言=IronPython 2.7 |
| 脚本库 | `.../ScriptLib/4.1.0.0/`(完整 Python2.7 stdlib) | import 支持 |
| API 接口 | `.../CompatibilityInterfaces/ScriptEngine.dll` | 工程/POU 操作 API |
| 授权服务 | CodeMeter.exe + FNPLicensingService.exe **均在运行** | AB 本机已授权 |

启动快捷方式无 `--profile` 参数 → AB 用内置默认 profile,无头命令行比原生 CODESYS 简单。
调查时 AutomationBuilder.exe **未运行** → 工程未被占用(但 Codex 做批次 D 时会打开)。

## 3. 目标脚本形状(CODESYS ScriptEngine 标准 API)

```
AutomationBuilder.exe --noUI --runscript="sync_st.py"
# sync_st.py(IronPython,跑在 AB 内):
#   proj = projects.open(r"...\ABB_WH.project")
#   for name in ["02_GVL","03_Functions",...,"08_..."]:
#       pou = proj.find(name, recursive=True)[0]
#       pou.textual_implementation.replace(open(f"plc/{name}.st").read())
#   proj.compile()          # 期望 0 error
#   # 可选:online.login + PRG_Test → 读 iPassed
#   proj.save()
```
一次搭好 → 以后每次口径变更,ST 侧同步从"发批次等 Codex 15 分钟"变成"跑一条命令"。

## 4. 未消的唯一硬闸门 + 落地前提

- **脚本许可闸门**:ScriptEngine 插件 DLL 在场 ≠ 该 CodeMeter 授权含"脚本"功能项。
  部分 ABB AB 授权把脚本 API 单独收费——DLL 能加载但 API 首次调用可能拒绝。
  **验法**:AB 空闲时跑一次只读脚本(open→打印工程树→不 save),1 分钟见分晓。
- **为何本次调查不当场验**:①用户正让 Codex 在 AB 里做批次 D,同时无头开工程=文件锁冲突风险;
  ②验证"改+重编+过测试"闭环需多次迭代,不能压在今天的活线上。
- **落地成本**:首次搭建+验证约半天到一天(许可确认+写脚本+跑通 POU 替换+编译+测试回读)。

## 5. 建议(待用户拍板)

1. **今天**:批次 D 照常走 Codex(15 分钟,不阻塞);
2. **另起 spike**(AB 空闲时):先跑只读测试脚本过许可闸门 → 过了再写完整同步脚本;
   闸门没过=退回批次 D 常态,无损失;
3. 已证不是死路(最大杀手"无脚本组件"已排除),值不值这半天由投入产出定:
   口径今天已证会变,未来 ST 同步若还有多次,自动化摊薄快;若 ST 基本冻结,则手工批次够用。

## 6. 落地结果(2026-07-06,当日建成)

调查结论全部兑现:管线 `tools/ab_scripting/ab_sync.ps1` 一条命令完成 34 对象同步+编译+
保存+在线跑测试,首跑实测 **Compile 0 errors + iPassed=24/iFailed=0**(批次 D 由此闭环,
Codex 免执行)。脚本许可闸门实测通畅;完整命门与三小时排障实录(--profile 必填、
create_pou 的 language/return_type 坑、**IEC 保留字 r/s 潜伏 bug**、TextBlob 正常形态、
"在线读回独有值才是新代码生效的铁证")见 tools/ab_scripting/README.md。
