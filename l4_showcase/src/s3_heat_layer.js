/* S3 货位热度层公共模块(0728 3D 抽离步2:热力 + 热区包络)
 *
 * 背景与设计依据(0718 #26-2 → 0719 改版,两页各自演化后由本文件收敛):
 *  - 热度属于**位置**不属于货物:行业惯例(Slot3D / WarehouseBlueprint)是「按库位的拣选活跃度给库位
 *    着色」。故货箱本体保留等级色(重/中/轻,是稳定性与能耗评分维度),热度由**货位前罩**承载。
 *  - 前罩而非顶盖:0719 用户反馈「3D 基本看不到热力」——贴在箱顶/箱后的薄片在正视角只露 1-2 px。
 *    改成贴货格前脸、覆盖整个格口的半透明罩,总览尺度上「热门贴底近 I/O」一眼可读。
 *  - opacity .78:实测 .45 时黄罩 × 蓝箱混成绿色、色阶失真;.78 热度主导保真。
 *  - 色阶冷端用中性浅灰 #aeb8c0 而非蓝:货箱等级色本身是蓝系,冷蓝会与蓝箱撞色糊成一片;
 *    中性灰让低频不抢注意力,注意力预算留给热门。
 *  - instanceColor 必须按容量预分配:three.js 的 setColorAt 首调时按当时 count 分配,count=0 时
 *    会分配成 Float32Array(0),之后所有 setColorAt 写入虚空(两页都踩过这个坑)。
 *
 * 用法(classic script,挂 window.S3HeatLayer,须在 three.js 之后、各页 runtime 之前载入):
 *   const heatColor = S3HeatLayer.createColorScale(THREE);
 *   const cellHeatMesh = S3HeatLayer.createCellHeatMesh(THREE, {group, capacity, frontY, thickness});
 *   const hotZone = S3HeatLayer.createHotZone(THREE, {scene, loadY, depth});
 * 两页只差三个数:容量、前罩所在的 y(取决于该页货箱尺寸留出的净空带)、热区最少格数。
 */
"use strict";
(function (root) {
  /* 色阶三段插值:冷=中性浅灰 → 琥珀 → 热红;t 由访问频次的秩归一化(非 min-max,
     规避 skew 分布下线性归一把绝大多数货挤在冷端)。 */
  const RAMP = Object.freeze({cold: 0xaeb8c0, mid: 0xe7b800, hot: 0xc0392b});
  /* 热区包络:半透明琥珀体 + 亮描边。fillOpacity 压到 .10 是为了不盖住罩内的热度色阶——
     包络负责「圈出聚集在哪」,色阶负责「每格多热」,两层各司其职。 */
  const ZONE = Object.freeze({fill: 0xe7b800, fillOpacity: .10, edge: 0xffb100, edgeOpacity: .95, pad: .14, depthPad: .12});
  const COVER = Object.freeze({width: .96, height: .96, thickness: .02, opacity: .78});

  function createColorScale(THREE) {
    const COLD = new THREE.Color(RAMP.cold), MID = new THREE.Color(RAMP.mid), HOT = new THREE.Color(RAMP.hot);
    const scratch = new THREE.Color();
    return function heatColor(t) {
      t = t < 0 ? 0 : t > 1 ? 1 : t;
      return t < .5 ? scratch.copy(COLD).lerp(MID, t * 2) : scratch.copy(MID).lerp(HOT, (t - .5) * 2);
    };
  }

  /* 货位前罩:整格 .96 × .96 的薄板,法线沿 y(朝巷道),白基色让 instanceColor 就是最终热度色。 */
  function createCellHeatMesh(THREE, options) {
    const o = options || {};
    const width = o.width == null ? COVER.width : o.width;
    const height = o.height == null ? COVER.height : o.height;
    const thickness = o.thickness == null ? COVER.thickness : o.thickness;
    const opacity = o.opacity == null ? COVER.opacity : o.opacity;
    const capacity = o.capacity;
    const mesh = new THREE.InstancedMesh(
      new THREE.BoxGeometry(width, thickness, height),
      /* MeshBasicMaterial 平涂不受光,instanceColor 满饱和呈现;depthWrite:false 规避 three.js
         透明黑块(issue 27170);本场景全部前罩共面同深、实例互不重叠,故 InstancedMesh
         无内建实例排序的已知限制不适用。 */
      new THREE.MeshBasicMaterial({color: 0xffffff, transparent: true, opacity, depthWrite: false}),
      capacity);
    mesh.count = 0; mesh.castShadow = false; mesh.receiveShadow = false;
    mesh.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(capacity * 3).fill(1), 3);
    if (o.group) o.group.add(mesh);
    mesh.userData.heatCover = Object.freeze({width, height, thickness, opacity, frontY: o.frontY});
    return mesh;
  }

  /* 热区包络:传入热门货实际所在的格子集合({col, tier}),取其包围盒。
     不是「预设一块金区」——包络必须由真实放置结果推出来,否则就是编造论证。 */
  function createHotZone(THREE, options) {
    const o = options || {}, minCells = o.minCells == null ? 1 : o.minCells;
    const mat = new THREE.MeshBasicMaterial({color: ZONE.fill, transparent: true, opacity: ZONE.fillOpacity,
      depthWrite: false, side: THREE.DoubleSide});
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1), mat);
    mesh.visible = false; mesh.renderOrder = 2; o.scene.add(mesh);
    const edges = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(1, 1, 1)),
      new THREE.LineBasicMaterial({color: ZONE.edge, transparent: true, opacity: ZONE.edgeOpacity}));
    edges.visible = false; edges.renderOrder = 6; o.scene.add(edges);
    const api = {
      mesh, edges, ready: false, bounds: null,
      update(cells) {
        const list = Array.isArray(cells) ? cells : [];
        if (list.length < minCells) { api.ready = false; api.bounds = null; return false; }
        let minCol = Infinity, maxCol = -Infinity, minTier = Infinity, maxTier = -Infinity;
        list.forEach(c => {
          minCol = Math.min(minCol, c.col); maxCol = Math.max(maxCol, c.col);
          minTier = Math.min(minTier, c.tier); maxTier = Math.max(maxTier, c.tier);
        });
        const cx = (minCol + maxCol + 1) / 2, cz = (minTier + maxTier + 1) / 2;
        const sx = (maxCol - minCol + 1) + ZONE.pad, sz = (maxTier - minTier + 1) + ZONE.pad, sy = o.depth + ZONE.depthPad;
        mesh.position.set(cx, o.loadY, cz); mesh.scale.set(sx, sy, sz);
        edges.position.copy(mesh.position); edges.scale.copy(mesh.scale);
        api.ready = true;
        api.bounds = {minCol, maxCol, minTier, maxTier, cells: list.length, center: [cx, cz], size: [sx, sz]};
        return true;
      },
      setVisible(on) { mesh.visible = edges.visible = !!(on && api.ready); }
    };
    return api;
  }

  root.S3HeatLayer = Object.freeze({RAMP, ZONE, COVER, createColorScale, createCellHeatMesh, createHotZone});
})(typeof window !== "undefined" ? window : globalThis);
