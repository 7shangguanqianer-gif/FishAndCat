/* S3 双轴运动学公共模块(0728 3D 抽离步3)
 *
 * 红线:本文件**只搬运,不改数值口径**。两页原有实现的数学表达式逐字保留;两页之间真实存在的
 * 口径差异(见下)由调用方传参声明,绝不在这里"统一"掉——改任何一边都会让显示速度与该页
 * trace 的时刻脱节,那才是真 bug(0728 任务A 已定论)。
 *
 * 两页口径差异(可复现,来源已核):
 *  - 01 连续填仓:数据门 payload.shared_input_provenance.motion.model =
 *      trapezoid_accel_plus_laden_vertical_factor,含满载升降折减 laden_vy_factor = 0.8
 *      (来源 sim/warehouse_sim.py:78,行业依据 Mecalux 0.818 / Muvro 0.667 取 0.80)。
 *      渲染侧对应 point() 的 ladenVzFactor 参数。
 *  - 02 存取闭环:trace meta.motion = trapezoid_accel,**不含**折减(ladenVzFactor = 1);
 *      另有 constant_speed 匀速档(档1 数据模型 LOD)走 motion 分支。
 *
 * 抽离前两页各有一份实现,且 02 页 html 里还留着一份**从未被调用**的 axisT/axisPos/axisV
 * 死代码(02 的 runtime 用的是自己带 motion 参数的那套)——一并清掉。
 *
 * 载入契约:classic script,挂 window.S3Motion,须在各页 runtime 之前载入。
 */
"use strict";
(function (root) {
  const CONSTANT = "constant_speed";
  const clamp = (value, low, high) => value < low ? low : value > high ? high : value;

  /* 梯形加减速总时长;匀速档退化为 d / vmax。 */
  function axisTime(distance, vmax, accel, motion) {
    if (distance <= 0) return 0;
    if (motion === CONSTANT) return distance / vmax;
    return distance >= vmax * vmax / accel ? distance / vmax + vmax / accel : 2 * Math.sqrt(distance / accel);
  }

  function axisPosition(time, distance, vmax, accel, motion) {
    if (distance <= 0) return 0;
    const total = axisTime(distance, vmax, accel, motion), t = clamp(time, 0, total);
    if (motion === CONSTANT) return Math.min(distance, vmax * t);
    if (distance >= vmax * vmax / accel) {
      const ramp = vmax / accel;
      if (t < ramp) return 0.5 * accel * t * t;
      if (t <= total - ramp) return 0.5 * accel * ramp * ramp + vmax * (t - ramp);
      return distance - 0.5 * accel * (total - t) * (total - t);
    }
    const ramp = Math.sqrt(distance / accel);
    return t < ramp ? 0.5 * accel * t * t : distance - 0.5 * accel * (total - t) * (total - t);
  }

  function axisVelocity(time, distance, vmax, accel, motion) {
    if (distance <= 0) return 0;
    const total = axisTime(distance, vmax, accel, motion), t = clamp(time, 0, total);
    if (motion === CONSTANT) return t >= total ? 0 : vmax;
    const peak = distance >= vmax * vmax / accel ? vmax : accel * Math.sqrt(distance / accel);
    const ramp = peak / accel;
    if (t < ramp) return accel * t;
    if (t <= total - ramp) return peak;
    return Math.max(0, accel * (total - t));
  }

  function axisState(time, distance, vmax, accel, motion) {
    if (distance <= 0) return {position: 0, velocity: 0, total: 0};
    const total = axisTime(distance, vmax, accel, motion), t = clamp(time, 0, total);
    return {position: axisPosition(t, distance, vmax, accel, motion),
      velocity: axisVelocity(t, distance, vmax, accel, motion), total};
  }

  /* 双轴同步点:两轴各自按自己的梯形曲线走,总时长取二者较大者(慢轴决定节拍)。
     options = {vx, vz, ax, az, motion, ladenVzFactor} —— ladenVzFactor 缺省 1(不折减)。 */
  function point(from, to, u, options) {
    const o = options || {};
    const motion = o.motion;
    const dx = Math.abs(to[0] - from[0]), dz = Math.abs(to[1] - from[1]);
    /* 折减只作用于升降轴 vz;水平轴 vx 不受载荷影响(与 sim 一致)。 */
    const vzEffective = o.vz * (o.ladenVzFactor == null ? 1 : o.ladenVzFactor);
    const tx = axisTime(dx, o.vx, o.ax, motion), tz = axisTime(dz, vzEffective, o.az, motion);
    const total = Math.max(tx, tz);
    const t = clamp(u, 0, 1) * total;
    const sx = Math.sign(to[0] - from[0]), sz = Math.sign(to[1] - from[1]);
    const mx = axisState(t, dx, o.vx, o.ax, motion), mz = axisState(t, dz, vzEffective, o.az, motion);
    return {x: from[0] + sx * mx.position, z: from[1] + sz * mz.position,
      vx: sx * mx.velocity, vz: sz * mz.velocity, total};
  }

  root.S3Motion = Object.freeze({CONSTANT, axisTime, axisPosition, axisVelocity, axisState, point});
})(typeof window !== "undefined" ? window : globalThis);
