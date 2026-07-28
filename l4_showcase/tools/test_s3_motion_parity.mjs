/* S3 运动学口径锁(0728 抽离步3 落)
 *
 * 存在意义:两页的速度差异是**真实的 sim 口径差异**,不是渲染 bug(0728 任务A 定论)。
 * 把 01/02 抽离前各自的原始实现逐字钉在这里当参照,与公共模块 src/s3_motion.js 跑密集网格比对——
 * 以后谁再想"顺手统一一下速度",这个测试会立刻红,而不是等到评委看出两页对不上。
 *
 * 参照来源(抽离前,git 可查):
 *   REF01 = 01_连续填仓.html 页内 axisT/axisPos/axisV + s3_fill_candidate_runtime.js:205-220 的
 *           motionAxis/motionPoint(含满载升降折减 vz = loaded ? VZ*0.8 : VZ)
 *   REF02 = s3_ac_runtime.js 的 axisTime/axisPosition/axisVelocity/motionPoint(带 motion 参数,
 *           含 constant_speed 匀速档;**不含**折减)
 * 判据:逐点 Object.is 相等(不是"约等于")。浮点必须一位不差,否则就是口径被动过。
 */
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const MOTION_PATH = path.join(HERE, "..", "src", "s3_motion.js");
const sandbox = {window: {}};
vm.runInNewContext(fs.readFileSync(MOTION_PATH, "utf8"), sandbox, {filename: MOTION_PATH});
const S3Motion = sandbox.window.S3Motion;

const VX = 2.0, VZ = 0.5, AX = 0.5, AZ = 0.3;
const clamp = (v, lo, hi) => v < lo ? lo : v > hi ? hi : v;

/* ---------- REF01:01 抽离前的原始实现(逐字) ---------- */
function refAxisT(d, vmax, acc) {
  if (d <= 0) return 0;
  return d >= vmax * vmax / acc ? d / vmax + vmax / acc : 2 * Math.sqrt(d / acc);
}
function refAxisPos(t, d, vmax, acc) {
  if (d <= 0) return 0;
  const T = refAxisT(d, vmax, acc); t = Math.min(Math.max(t, 0), T);
  if (d >= vmax * vmax / acc) {
    const ta = vmax / acc;
    if (t < ta) return .5 * acc * t * t;
    if (t <= T - ta) return .5 * acc * ta * ta + vmax * (t - ta);
    return d - .5 * acc * (T - t) * (T - t);
  }
  const ta = Math.sqrt(d / acc);
  return t < ta ? .5 * acc * t * t : d - .5 * acc * (T - t) * (T - t);
}
function refAxisV(t, d, vmax, acc) {
  if (d <= 0) return 0;
  const T = refAxisT(d, vmax, acc); if (t < 0 || t > T) return 0;
  const vpk = d >= vmax * vmax / acc ? vmax : acc * Math.sqrt(d / acc), ta = vpk / acc;
  if (t < ta) return acc * t; if (t <= T - ta) return vpk; return acc * (T - t);
}
function refMotionAxis01(time, distance, vmax, accel) {
  if (distance <= 0) return {position: 0, velocity: 0, total: 0};
  const total = refAxisT(distance, vmax, accel), t = clamp(time, 0, total);
  return {position: refAxisPos(t, distance, vmax, accel), velocity: refAxisV(t, distance, vmax, accel), total};
}
function refMotionPoint01(from, to, progress, loaded) {
  const dx = Math.abs(to[0] - from[0]), dz = Math.abs(to[1] - from[1]);
  const tx = refAxisT(dx, VX, AX), vz = loaded ? VZ * 0.8 : VZ, tz = refAxisT(dz, vz, AZ), total = Math.max(tx, tz);
  const t = clamp(progress, 0, 1) * total;
  const mx = refMotionAxis01(t, dx, VX, AX), mz = refMotionAxis01(t, dz, vz, AZ);
  return {x: from[0] + Math.sign(to[0] - from[0]) * mx.position,
    z: from[1] + Math.sign(to[1] - from[1]) * mz.position,
    vx: Math.sign(to[0] - from[0]) * mx.velocity, vz: Math.sign(to[1] - from[1]) * mz.velocity, total};
}

/* ---------- REF02:02 抽离前的原始实现(逐字) ---------- */
function refAxisTime(distance, vmax, accel, motion) {
  if (distance <= 0) return 0;
  if (motion === "constant_speed") return distance / vmax;
  return distance >= vmax * vmax / accel ? distance / vmax + vmax / accel : 2 * Math.sqrt(distance / accel);
}
function refAxisPosition(time, distance, vmax, accel, motion) {
  if (distance <= 0) return 0;
  const total = refAxisTime(distance, vmax, accel, motion), t = clamp(time, 0, total);
  if (motion === "constant_speed") return Math.min(distance, vmax * t);
  if (distance >= vmax * vmax / accel) {
    const ramp = vmax / accel;
    if (t < ramp) return 0.5 * accel * t * t;
    if (t <= total - ramp) return 0.5 * accel * ramp * ramp + vmax * (t - ramp);
    return distance - 0.5 * accel * (total - t) * (total - t);
  }
  const ramp = Math.sqrt(distance / accel);
  return t < ramp ? 0.5 * accel * t * t : distance - 0.5 * accel * (total - t) * (total - t);
}
function refAxisVelocity(time, distance, vmax, accel, motion) {
  if (distance <= 0) return 0;
  const total = refAxisTime(distance, vmax, accel, motion), t = clamp(time, 0, total);
  if (motion === "constant_speed") return t >= total ? 0 : vmax;
  const peak = distance >= vmax * vmax / accel ? vmax : accel * Math.sqrt(distance / accel);
  const ramp = peak / accel;
  if (t < ramp) return accel * t;
  if (t <= total - ramp) return peak;
  return Math.max(0, accel * (total - t));
}
function refMotionPoint02(from, to, u, motion) {
  const dx = Math.abs(to[0] - from[0]), dz = Math.abs(to[1] - from[1]);
  const tx = refAxisTime(dx, VX, AX, motion), tz = refAxisTime(dz, VZ, AZ, motion), total = Math.max(tx, tz);
  const t = clamp(u, 0, 1) * total;
  const sx = Math.sign(to[0] - from[0]), sz = Math.sign(to[1] - from[1]);
  return {
    x: from[0] + sx * refAxisPosition(t, dx, VX, AX, motion),
    z: from[1] + sz * refAxisPosition(t, dz, VZ, AZ, motion),
    vx: sx * refAxisVelocity(t, dx, VX, AX, motion),
    vz: sz * refAxisVelocity(t, dz, VZ, AZ, motion), total
  };
}

/* ---------- 网格 ---------- */
const CELLS = [0, 1, 2, 3, 5, 7, 9, 11, 13, 15, 17, 19];
const PROGRESS = [0, .001, .05, .17, .25, .33, .5, .67, .75, .83, .95, .999, 1];
const same = (a, b, label) => assert.ok(Object.is(a, b), `${label}: ${a} !== ${b}`);

test("单轴曲线:公共模块与 01 抽离前实现逐位相同(梯形档)", () => {
  let points = 0;
  for (const d of [0, .0001, .25, .5, 1, 2, 4, 8, 12, 19, 19.5, 20]) {
    for (const [vmax, acc] of [[VX, AX], [VZ, AZ], [VZ * 0.8, AZ]]) {
      const T = refAxisT(d, vmax, acc);
      same(S3Motion.axisTime(d, vmax, acc, undefined), T, `axisTime d=${d} v=${vmax}`);
      for (const f of [-0.1, 0, .13, .5, .87, 1, 1.4]) {
        const t = T * f;
        same(S3Motion.axisPosition(t, d, vmax, acc, undefined), refAxisPos(t, d, vmax, acc), `axisPosition d=${d} t=${t}`);
        /* 01 原实现在 t<0 / t>T 直接返回 0;公共模块先 clamp 再算,两者在这些点上必须同值 */
        const refV = (t < 0 || t > T) ? 0 : refAxisV(t, d, vmax, acc);
        same(S3Motion.axisVelocity(t, d, vmax, acc, undefined), refV, `axisVelocity d=${d} t=${t}`);
        points += 3;
      }
    }
  }
  assert.ok(points >= 700, `采样点过少:${points}`);
});

test("单轴曲线:公共模块与 02 抽离前实现逐位相同(梯形档 + 匀速档)", () => {
  for (const motion of ["trapezoid_accel", "constant_speed", undefined]) {
    for (const d of [0, .0001, .25, 1, 4, 12, 19, 20]) {
      for (const [vmax, acc] of [[VX, AX], [VZ, AZ]]) {
        const T = refAxisTime(d, vmax, acc, motion);
        same(S3Motion.axisTime(d, vmax, acc, motion), T, `axisTime ${motion} d=${d}`);
        for (const f of [0, .13, .5, .87, 1, 1.4]) {
          const t = T * f;
          same(S3Motion.axisPosition(t, d, vmax, acc, motion), refAxisPosition(t, d, vmax, acc, motion), `axisPosition ${motion} d=${d} t=${t}`);
          same(S3Motion.axisVelocity(t, d, vmax, acc, motion), refAxisVelocity(t, d, vmax, acc, motion), `axisVelocity ${motion} d=${d} t=${t}`);
        }
      }
    }
  }
});

test("01 双轴同步点:含满载升降折减 laden_vy_factor=0.8,与抽离前逐位相同", () => {
  let n = 0;
  for (const fx of CELLS) for (const tx of CELLS) for (const fz of [0, 6, 13, 19]) for (const tz of [0, 6, 13, 19]) {
    for (const loaded of [true, false]) for (const u of PROGRESS) {
      const ref = refMotionPoint01([fx, fz], [tx, tz], u, loaded);
      const got = S3Motion.point([fx, fz], [tx, tz], u, {vx: VX, vz: VZ, ax: AX, az: AZ, ladenVzFactor: loaded ? 0.8 : 1});
      same(got.x, ref.x, `x ${fx},${fz}→${tx},${tz} loaded=${loaded} u=${u}`);
      same(got.z, ref.z, `z ${fx},${fz}→${tx},${tz} loaded=${loaded} u=${u}`);
      same(got.vx, ref.vx, `vx ${fx},${fz}→${tx},${tz} loaded=${loaded} u=${u}`);
      same(got.vz, ref.vz, `vz ${fx},${fz}→${tx},${tz} loaded=${loaded} u=${u}`);
      same(got.total, ref.total, `total ${fx},${fz}→${tx},${tz} loaded=${loaded} u=${u}`);
      n += 5;
    }
  }
  assert.ok(n >= 100000, `采样点过少:${n}`);
});

test("02 双轴同步点:不含折减、支持匀速档,与抽离前逐位相同", () => {
  let n = 0;
  for (const motion of ["trapezoid_accel", "constant_speed"]) {
    for (const fx of CELLS) for (const tx of CELLS) for (const fz of [0, 6, 13, 19]) for (const tz of [0, 6, 13, 19]) {
      for (const u of PROGRESS) {
        const ref = refMotionPoint02([fx, fz], [tx, tz], u, motion);
        const got = S3Motion.point([fx, fz], [tx, tz], u, {vx: VX, vz: VZ, ax: AX, az: AZ, motion});
        same(got.x, ref.x, `x ${motion} ${fx},${fz}→${tx},${tz} u=${u}`);
        same(got.z, ref.z, `z ${motion} ${fx},${fz}→${tx},${tz} u=${u}`);
        same(got.vx, ref.vx, `vx ${motion}`); same(got.vz, ref.vz, `vz ${motion}`);
        same(got.total, ref.total, `total ${motion}`);
        n += 5;
      }
    }
  }
  assert.ok(n >= 200000, `采样点过少:${n}`);
});

test("两页口径差异必须仍然存在(反向断言:不许被'统一'掉)", () => {
  /* 取一段纯升降行程:满载(01)应比空载(02)慢,且慢的比例正是 1/0.8。 */
  const from = [5, 2], to = [5, 18];
  const laden = S3Motion.point(from, to, 1, {vx: VX, vz: VZ, ax: AX, az: AZ, ladenVzFactor: 0.8});
  const plain = S3Motion.point(from, to, 1, {vx: VX, vz: VZ, ax: AX, az: AZ});
  assert.ok(laden.total > plain.total, "满载升降折减必须让总时长变长");
  /* 长行程(达到最大速度)下 total = d/v + v/a,折减后可解析核对 */
  const d = 16, v = VZ * 0.8;
  assert.equal(laden.total, d / v + v / AZ);
  assert.equal(plain.total, d / VZ + VZ / AZ);
  /* 匀速档必须与梯形档不同(否则档1 LOD 白做) */
  const cs = S3Motion.point(from, to, 1, {vx: VX, vz: VZ, ax: AX, az: AZ, motion: S3Motion.CONSTANT});
  assert.equal(cs.total, d / VZ);
  assert.notEqual(cs.total, plain.total);
});
