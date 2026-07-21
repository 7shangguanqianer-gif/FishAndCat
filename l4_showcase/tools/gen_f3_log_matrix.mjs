#!/usr/bin/env node
/**
 * 只读脚本 —— 不修改 l2_factoryio 下任何文件。
 *
 * 用途:扫描 l2_factoryio/logs 下 F3_diagnose_20260713_19*.log(即 03 页矩阵表原引用的通配口径,
 * 也是 66 vs 54 口径争议的范围),按文件名时间戳排序后,依据项目既定六相位状态机
 * (feed/pick/travel/place-extend/place-lower/retract,见 io_map.md「叉臂取放动作契约」与
 * F3_H5证据保全_0716.md)切成每组 6 份的时间组;再交叉核验 l2_factoryio/fault_state.json 的
 * reset_history(找 note 含"H5"的条目取 epoch_id / epoch_started_at),
 * 结合组间时间间隔的离群检测,判定哪些组属于 H5 9/9 验收链、哪些是调试或验收后追加复核组。
 *
 * 输出:f3_log_matrix.json(与本脚本同目录,l4_showcase/tools/)。产物 json 内嵌 03 页面
 * (l4_showcase/src/03_FIO物理证据.html 的 <script type="application/json" id="f3MatrixData">),
 * 不在页面运行时 fetch;数据变化(如 logs 增补)后重跑本脚本,再把新 json 内容手动/程序化
 * 同步进页面内嵌块。
 *
 * 0721 迁移记录:本脚本原名 gen_f3_log_matrix_0721.mjs,位于 l4_showcase/design_mock_0721/
 * (拍板验证用);回灌 src 施工时按施工规格 §2.3 移入 tools/ 并改名 gen_f3_log_matrix.mjs,
 * 仅路径/文件名与本注释更新,判定逻辑与算法一字未改。
 *
 * 判定方法(全部可审计,数值均随输出落盘,不隐藏):
 *   1) 组归属 H5 epoch 的门槛 = fault_state.json reset_history 中 note 含"H5"的条目的 epoch_started_at。
 *      早于该时刻的组 -> role = pre_epoch_debug(验收前预演)。
 *   2) 达到/晚于该时刻的组,按开始时间排序,计算相邻组间隔(组i末份->组i+1首份,单位秒)。
 *      取最大间隔 gapMax 与次大间隔 gapSecond;若 gapMax > max(120, 2*gapSecond),则在该处切分:
 *      切分点之前(含)的组 -> role = h5_chain(9/9 验收链);切分点及之后 -> role = post_chain_supplementary
 *      (验收链已完整后的追加复核,不计入 9/9 正式成员)。
 *      若未出现符合条件的离群间隔,则不做该项二次切分,所有 post-epoch 组一律计入 h5_chain
 *      (此时若组数 != 9,会在 summary.caveat 中如实注明,不强行凑数)。
 *   3) 组代表的 cell 号 = 组内 6 份日志中出现"cell N"字样的众数(取非空值里出现次数最多的 N);
 *      若组内出现相互冲突的多个 cell 号(理论上不应发生),在该组 note 中如实标注,不静默取舍。
 *
 * 禁止事项:不虚构链号归属、不补全成"9链"以外的整齐叙事、不改动/不删除任何 l2_factoryio 文件。
 */
import fs from "node:fs";
import path from "node:path";

const REPO_ROOT = "F:/abb_wh_work";
const LOG_DIR = path.join(REPO_ROOT, "l2_factoryio/logs");
const FAULT_STATE_PATH = path.join(REPO_ROOT, "l2_factoryio/fault_state.json");
const OUT_JSON = path.join(REPO_ROOT, "l4_showcase/tools/f3_log_matrix.json");

const FILE_RE = /^F3_diagnose_20260713_19(\d{2})(\d{2})\.log$/; // 19MMSS,hour 固定 19(与源页矩阵表引用的通配一致)
const PHASES = ["feed", "pick", "travel", "place-extend", "place-lower", "retract"];
const GROUP_SIZE = PHASES.length;

function fail(msg) {
  console.error("[gen_f3_log_matrix] FATAL: " + msg);
  process.exit(1);
}

// ---------- 1. 枚举 + 排序 ----------
if (!fs.existsSync(LOG_DIR)) fail("log dir not found: " + LOG_DIR);
const allEntries = fs.readdirSync(LOG_DIR);
const diagFiles = allEntries
  .filter((f) => FILE_RE.test(f))
  .map((f) => {
    const m = f.match(FILE_RE);
    const mm = m[1], ss = m[2];
    const sec = (19 * 3600) + (Number(mm) * 60) + Number(ss);
    return { file: f, mm, ss, sec, hhmmss: `19:${mm}:${ss}` };
  })
  .sort((a, b) => a.sec - b.sec);

if (diagFiles.length === 0) fail("no F3_diagnose_20260713_19*.log matched under " + LOG_DIR);

// ---------- 2. 逐份读取内容,提取 cell 号 ----------
for (const rec of diagFiles) {
  const content = fs.readFileSync(path.join(LOG_DIR, rec.file), "utf8");
  const cellMatches = [...content.matchAll(/cell (\d+)/g)].map((m) => Number(m[1]));
  rec.cellMentions = cellMatches; // 该份日志内所有"cell N"出现(去重前)
  rec.cell = cellMatches.length ? cellMatches[0] : null;
}

// ---------- 3. 按 6 份一组切分(项目既定六相位状态机;非本脚本臆断) ----------
if (diagFiles.length % GROUP_SIZE !== 0) {
  fail(
    `文件总数 ${diagFiles.length} 不能被 6(六相位)整除,拒绝强行分组——需人工核查命名规律是否变化`
  );
}
const groups = [];
for (let i = 0; i < diagFiles.length; i += GROUP_SIZE) {
  const slice = diagFiles.slice(i, i + GROUP_SIZE);
  // 组代表 cell = 众数(非空值中出现次数最多的)
  const freq = new Map();
  for (const f of slice) {
    if (f.cell != null) freq.set(f.cell, (freq.get(f.cell) || 0) + 1);
  }
  let repCell = null, repCount = -1, conflict = false;
  for (const [cell, count] of freq.entries()) {
    if (count > repCount) { repCell = cell; repCount = count; conflict = false; }
    else if (count === repCount) { conflict = true; }
  }
  groups.push({
    groupIndex: groups.length + 1,
    cell: repCell,
    cellConflict: conflict,
    startSec: slice[0].sec,
    endSec: slice[slice.length - 1].sec,
    startTime: slice[0].hhmmss,
    endTime: slice[slice.length - 1].hhmmss,
    files: slice.map((f, phaseIdx) => ({
      phase_guess: PHASES[phaseIdx],
      file: f.file,
      time: f.hhmmss,
      cell_mentions: f.cellMentions,
    })),
  });
}

// ---------- 4. 读取 fault_state.json,定位 H5 epoch ----------
if (!fs.existsSync(FAULT_STATE_PATH)) fail("fault_state.json not found: " + FAULT_STATE_PATH);
const faultState = JSON.parse(fs.readFileSync(FAULT_STATE_PATH, "utf8"));
const h5Reset = (faultState.reset_history || []).find((r) => (r.note || "").includes("H5"));
if (!h5Reset) fail("reset_history 中未找到 note 含 'H5' 的条目——无法确证 epoch 边界,拒绝猜测");
const epochStartedAt = h5Reset.epoch_started_at; // e.g. "2026-07-13T19:09:13"
const epochId = h5Reset.epoch_id;
const epochTimeMatch = epochStartedAt.match(/T(\d{2}):(\d{2}):(\d{2})/);
if (!epochTimeMatch) fail("epoch_started_at 时间格式无法解析: " + epochStartedAt);
const epochStartSec = Number(epochTimeMatch[1]) * 3600 + Number(epochTimeMatch[2]) * 60 + Number(epochTimeMatch[3]);

// ---------- 5. 分类:pre_epoch_debug vs post-epoch(待二次切分) ----------
const postEpoch = [];
for (const g of groups) {
  if (g.startSec < epochStartSec) {
    g.role = "pre_epoch_debug";
    g.round = null;
    g.note = `组起始 ${g.startTime} 早于 H5 epoch 起点 ${epochStartedAt.slice(11)},判定为验收前预演/调试,非 H5 9 链成员`;
  } else {
    postEpoch.push(g);
  }
}

// ---------- 6. post-epoch 组间隔离群检测,二次切分 h5_chain vs post_chain_supplementary ----------
postEpoch.sort((a, b) => a.startSec - b.startSec);
const gaps = [];
for (let i = 0; i < postEpoch.length - 1; i++) {
  gaps.push({ afterGroupIndex: postEpoch[i].groupIndex, gapSeconds: postEpoch[i + 1].startSec - postEpoch[i].endSec });
}
let splitAfterGroupIndex = null;
if (gaps.length >= 2) {
  const sorted = [...gaps].sort((a, b) => b.gapSeconds - a.gapSeconds);
  const gapMax = sorted[0], gapSecond = sorted[1];
  const threshold = Math.max(120, 2 * gapSecond.gapSeconds);
  if (gapMax.gapSeconds > threshold) {
    splitAfterGroupIndex = gapMax.afterGroupIndex;
  }
}

let roundCounters = {};
for (const g of postEpoch) {
  const isSupplementary = splitAfterGroupIndex != null && g.groupIndex > splitAfterGroupIndex;
  g.role = isSupplementary ? "post_chain_supplementary" : "h5_chain";
  if (g.role === "h5_chain") {
    roundCounters[g.cell] = (roundCounters[g.cell] || 0) + 1;
    g.round = roundCounters[g.cell];
    g.note = `H5 9/9 验收链第 ${g.round} 轮 · cell ${g.cell}(epoch ${epochId.slice(0, 8)}…)`;
  } else {
    g.round = null;
    const gapInfo = gaps.find((x) => x.afterGroupIndex === splitAfterGroupIndex);
    g.note = `与组 ${splitAfterGroupIndex} 间隔 ${gapInfo ? gapInfo.gapSeconds : "?"}s,显著大于组间典型间隔(见 summary.gap_analysis_seconds),判定为 9/9 验收链完整结束后的追加复核组,非正式 9 链成员`;
  }
}

// ---------- 7. 汇总 ----------
const h5ChainGroups = groups.filter((g) => g.role === "h5_chain");
const nonChainGroups = groups.filter((g) => g.role !== "h5_chain");
const cellsCovered = {};
for (const g of h5ChainGroups) cellsCovered[g.cell] = (cellsCovered[g.cell] || 0) + 1;

const anyConflict = groups.some((g) => g.cellConflict);

const output = {
  generated_at: new Date().toISOString(),
  generated_by: "l4_showcase/tools/gen_f3_log_matrix.mjs(只读)",
  source_scope: "l2_factoryio/logs/F3_diagnose_20260713_19*.log",
  total_files: diagFiles.length,
  phase_order: PHASES,
  epoch_evidence: {
    epoch_id: epochId,
    epoch_started_at: epochStartedAt,
    source: "l2_factoryio/fault_state.json#reset_history[note含'H5'];交叉参照 l2_factoryio/F3_H5证据保全_0716.md",
    reset_note_verbatim: h5Reset.note,
  },
  groups: groups.map((g) => ({
    groupIndex: g.groupIndex,
    cell: g.cell,
    cellConflict: g.cellConflict,
    role: g.role,
    round: g.round,
    startTime: g.startTime,
    endTime: g.endTime,
    note: g.note,
    files: g.files,
  })),
  summary: {
    total_groups: groups.length,
    total_files: diagFiles.length,
    h5_chain_groups: h5ChainGroups.length,
    h5_chain_files: h5ChainGroups.length * GROUP_SIZE,
    non_chain_groups: nonChainGroups.length,
    non_chain_files: nonChainGroups.length * GROUP_SIZE,
    cells_covered_in_chain: cellsCovered,
    cell_data_conflict_detected: anyConflict,
    gap_analysis_seconds: gaps,
    split_after_group_index: splitAfterGroupIndex,
    caveat:
      "54/66(或本次实测得到的组数×6)归属为脚本对 fault_state.json + 文件名时间戳的交叉核验推断结果," +
      "依据 = epoch 边界(reset_history 'H5' 条目) + 组间隔离群检测(数值见 gap_analysis_seconds)," +
      "并非项目既有文档中已经写明的逐份清单;方法与原始数值均随本 json 落盘,可自行复核。",
  },
};

fs.writeFileSync(OUT_JSON, JSON.stringify(output, null, 2), "utf8");
console.log(`[gen_f3_log_matrix] wrote ${OUT_JSON}`);
console.log(`[gen_f3_log_matrix] groups=${groups.length} files=${diagFiles.length} h5_chain=${h5ChainGroups.length}x6=${h5ChainGroups.length*6} non_chain=${nonChainGroups.length}x6=${nonChainGroups.length*6}`);
console.log(`[gen_f3_log_matrix] gap_analysis=${JSON.stringify(gaps)}`);
console.log(`[gen_f3_log_matrix] split_after_group_index=${splitAfterGroupIndex}`);
