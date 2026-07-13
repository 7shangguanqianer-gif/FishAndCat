# 提交包 manifest / requirements / allowlist 草案（0712 overnight T4）

> 性质：**草案，全部待用户拍板**。8/26 官方提交（无准确格式要求，按既定"AB工程+ST源码+报告+复现包"双备份方案）。
> ⚠ 硬约束：AB 许可证约 8/2 到期——凡需开 AB 的终验/导出/录屏须在此之前完成。

## 一、交付物清单（manifest v0）

| # | 交付物 | 源路径 | 状态 | 备注 |
|---|---|---|---|---|
| 1 | AB 工程文件 | `plc/AB_Project/ABB_WH.project` | ✅ 就绪 | 75/0 全真实断言+画面收口版；提交前最后跑一轮 ab_sync 取终验时间戳 |
| 2 | ST 源码（文本双备份） | `plc/*.st`（01-08+README_PLC.md） | ✅ 就绪 | 与工程内容同源（sync_st.py 管线保证） |
| 3 | 设计验证报告 docx | `2_你要操作/`（Codex 轨A 维护） | 🟡 报告周 | B1 重做/§6 新章/30-seed 注入后由 build_report.py 重生 |
| 4 | 答辩 PPT | 同上（build_ppt.py 重生） | 🟡 报告周 | |
| 5 | 复现包（sim 全套） | `sim/*.py` + `sim/out/` 关键 CSV | ✅ 代码就绪 | 见 requirements；out/ 可由脚本再生，建议附关键 CSV（headline_numbers/final_test_30seed/oracle_gap）省评委跑批时间 |
| 6 | 演示录屏 | 待录（B13 规格） | ⬜ 7/20 后 | 用户在场；动线=画面科普 docx §四 |
| 7 | 画面科普/操作说明（可选加分） | `docs/画面科普_三页界面指南_0712.docx` | ✅ 就绪 | 含三页实景截图；可作评委快速上手指南 |
| 8 | 测试证据 | `tools/ab_scripting/logs/`（终验轮） | ✅ 机制就绪 | 每轮自动存档；提交附最后一轮 sync+runtest |

## 二、requirements（复现包依赖）

```
# 核心仿真（headline.py / final_test_30seed.py / warehouse_sim.py / strategy_lib.py / oracle_gap.py）
# ——纯 Python 标准库，零第三方依赖，Python ≥3.9

# 图表与文档再生（可选，仅当评委要重生图/报告/PPT）
matplotlib        # 图 fig1-15
scipy             # instance_gen 分布 + lap_optimal 匈牙利下界
numpy             # lap_optimal
python-docx       # build_report.py 报告重生
python-pptx       # build_ppt.py PPT 重生
```
安装：`pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/`（requirements.txt 待生成，上表即内容）。
验证命令三连（评委 5 分钟）：`python sim/core_smoke.py`（32/32 锁）→ `python sim/headline.py`（~1min 头条）→ `python sim/final_test_30seed.py`（~30s U3 泛化）。

## 三、allowlist（打包白名单）——按"评委可见"整理

**进包**：
- `plc/`（工程+ST+README_PLC）
- `sim/*.py`、`sim/out/` 关键 CSV（headline_numbers.csv、final_test_30seed*.csv、oracle_gap*.csv/txt、detector_rules.md）、`sim/figs/`
- 报告 docx + PPT（终版）
- `docs/` 白名单子集：canonical_assumptions.md（口径声明）、画面科普 docx、A5 执行时间实测——**其余 docs/ 过程文档不进包**（内部工作记录）
- `README.md`（改写为评委版导读后进包，当前版含内部流程需洗）
- 录屏文件

**不进包（内部区）**：
- `_通信/`（双 AI 协作信箱）、`1_给你看/`、`2_你要操作/` 工作副本（报告终版单独拷出）
- `.git/`、`tools/`（ab_scripting 为内部工具链；若评委问自动化可现场展示）
- `docs/` 全部过程性文档（复核回执/审查/overnight 报告/接管提示词等）

**校验**：打包后生成 SHA256SUMS（`Get-FileHash -Algorithm SHA256`），与报告附录"证据溯源页"(B9)交叉引用。

## 四、拍板结果（0712 晚，用户）
1. sim/out 关键 CSV：**附** ✓。
2. 文件进度同步展示：**已即时执行**——docs/README.md 新增"项目进度一页速览"（简洁八行表）；README 评委版洗版=8 月打包时做。
3. tools/ 附录展示：**8 月打包阶段再定**（本轮仅记录）。
4. 双备份形态：**两个 zip（工程包+复现包）** ✓；打包执行=8 月。
