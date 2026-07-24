# Codex 任务 A · 3D 速度口径统一(01 ↔ 02)

## 0. 项目底座(自包含,codex 必读)

- 仓库根:`F:\abb_wh_work`;展示站:`F:\abb_wh_work\l4_showcase`(src/ 页面与 runtime,tools/ 测试)。
- 无构建的 classic-script 前端(three.js 内联);两页 runtime:`src/s3_fill_candidate_runtime.js`(01)、`src/s3_ac_runtime.js`(02)。
- QA/回归命令(cwd=`F:\abb_wh_work\l4_showcase`):
  - 契约:`node tools/test_s3_runtime_contract.mjs` → 期望 `tests 30 / pass 30 / fail 0`
  - 01QA:`node tools/capture_s3_layout_a_qa.mjs` → 期望 `PASS 61/61`
  - 02QA:`node tools/capture_s3_mixed_layout_a_qa.mjs` → 期望 `PASS 8/8`
  - uniform:`node tools/capture_s3_fill_uniform_qa.mjs` → 期望 `PASS 8/8`
- Playwright 底座(所有 capture 脚本共用):Chromium `C:/Users/86177/AppData/Local/ms-playwright/chromium-1223/chrome-win64/chrome.exe`,args `['--use-angle=d3d11','--enable-unsafe-swiftshader']`;静态服务器 root 必须=仓库根,MIME 含 .html/.js/.css/.json/.png/.jpg/.mp4;playwright 包解析见 `tools/capture_s3_layout_a_qa.mjs:29-38`(codex 环境若有 playwright 直接用)。
- 红线见 `docs/全站设计规范_0724.md` §6。**本任务只碰速度显示的运行时算法,严禁改动 sim/trace/manifest 与契约锚定的时长/位置口径。**

## 1. 背景与精确诊断(已核实,勿重新臆测)

用户反馈:01 与 02 的 3D 演示,同为 1 倍速时货物/设备**速度显示数值不一致**。

**诊断(已核实到行)**:
- 运动学常量**两页逐字完全相同**:`const VX = 2.0, VZ = 0.5, AX = 0.5, AZ = 0.3, FORK_MAX = 1.2;`(01 在 `s3_fill_candidate_runtime.js:39`,02 在 `s3_ac_runtime.js:19`)。**峰值速度、加速度全一致,勿改这些值。**
- 演示倍率(1×)只压缩时间,不改 m/s 物理量,**不是倍率问题**。
- 差异真实来源仅两处:
  1. **载货升降降速**:01 有 `vz = loaded ? VZ * 0.8 : VZ`(`s3_fill_candidate_runtime.js:214`),即载货时 Z 轴上限降到 0.4 m/s;02 无此降速(`s3_ac_runtime.js:688-689` 直接用 `axisVelocity(t, dz, VZ, AZ, motion)`,载货不降速)。
  2. **运动模式**:02 有 `motion` 参数(`constant_speed` 匀速档 vs 加减速,见 `s3_ac_runtime.js:650/657/668/671`),匀速档速度恒=vmax;01 只有加减速一种(`motionAxis`/`axisV` 无 motion 参数)。

## 2. 目标与改动方案(用户拍板:统一底层运动学,保留 02 匀速档)

**目标**:1 倍速、**默认档(加减速)**下,01 与 02 在**同一作业阶段**(如满载 X 轴行走、空载 Z 轴升降)的速度显示数值一致。02 的匀速档(拟真档)作为卖点保留,不强加给 01。

**改动**:
1. **统一载货降速规则**——这是唯一的物理参数分歧。二选一,codex 判断并说明理由:
   - 方案 i(倾向,更真实):02 默认档也加载货 Z 轴降速(`loaded ? VZ*0.8 : VZ`),与 01 一致。**前提**:必须实测确认给 02 加降速后,`node tools/capture_s3_mixed_layout_a_qa.mjs` 与契约不回归(02 的速度是运行时显示量;若契约/02QA 有对速度峰值或腿时长的断言,须核对不破坏——腿时长由 trace 时刻差决定,不由显示速度决定,理论上安全,但必须实测证实)。
   - 方案 ii(更简单):01 去掉载货降速(`vz = VZ`),与 02 一致。代价:01 失去"载货降速"这一真实性细节。
   - **禁**:改 VX/VZ/AX/AZ 的值;改任何 trace/manifest/契约锚定量。
2. **默认档运动学同源**:确认 01 的 `motionAxis`/`axisV`/`axisT` 与 02 的默认(加减速)分支 `axisVelocity`/`axisPosition` 数学等价(同 vmax/accel 下加减速曲线一致)。若有细微算法差异(如加速段/匀速段/减速段的临界处理不同),对齐到同一套公式。可抽共享函数或使两处逐字等价(无构建环境:可各自改成等价实现,或提取到一个两页都 `<script src>` 引入的共享 js——若提取,须两页 html 都引入且不破坏加载顺序)。
3. 02 匀速档分支(`motion === "constant_speed"`)保留不动。

## 3. 验收标准(须实测,数字原样贴报告)

1. **速度一致性实测**(核心):写一个一次性对比脚本(可放 scratchpad,不入库),用 Playwright 加载 01 与 02,各自 seek 到「满载 X 轴行走中段」与「空载 Z 轴升降中段」两个可比阶段,读 `__S3_FILL_QA.snapshot()` / 02 对应 QA 快照的 `machine.vx/vz`,证明默认档同阶段数值一致(容差 <0.01 m/s)。贴对比表。
2. **回归全绿**:契约 30/30 fail0、01QA 61/61、02QA 8/8、uniform 8/8。四条命令实测输出原样贴。
3. 若选方案 i(改 02),额外确认 02 的腿时长/省一趟等 KPI(`renderOpsEvidence`)口径未变(载货降速改的是显示速度,不是 trace 时刻;但须核对 02QA 无相关断言回归)。

## 4. 交付格式(markdown)

改动文件与 `git diff --stat`;载货降速方案(i/ii)选择与理由;速度一致性对比表(两阶段×两页 vx/vz);四条回归命令原样输出;是否抽共享函数及如何不破坏加载顺序;遇到的问题与处理。**不 commit**,报告后由主会话验收。
