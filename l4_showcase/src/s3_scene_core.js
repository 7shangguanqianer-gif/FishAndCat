/* S3 三维公共场景内核(0728 3D 抽离步1:几何 + 材质)
 *
 * 背景:01_连续填仓.html 与 02_入出闭环.html 的三维母版同源自 tools/anim3d_formal.py,
 * 但长期各自内联在自己的 html 里独立演化,无共享文件——谁改了特性另一页不跟进,
 * 造成热力/FX/运动细节的全面代差(诊断见 docs/任务规划_0728_3D抽离与悬浮.md §1.1)。
 * 本文件把两页逐字相同的「场景搭建 + 材质表 + 几何契约」收敛为唯一实现;
 * 两页只保留各自的拓扑差异(交接台形态、传送带走线、目标 FX、镜头取景策略)。
 *
 * 载入契约(classic script,顶层 const 进全局词法环境,后续 <script> 可见):
 *   1. 必须在 lib/three.min.js 与 lib/OrbitControls.js 之后载入;
 *   2. 页面须在本文件之前声明 VISUAL(名称/背景/机位/焦点/fov/灯色)与 S3_SCENE_CONFIG(见下);
 *   3. 页面须已存在 #gl 挂载点;
 *   4. 页面在本文件之后补齐:交接台/桥/传送带走线/地贴文字/目标 FX 组装/setCamera/resizeScene。
 *
 * S3_SCENE_CONFIG 结构:
 *   infeed / outfeed  —— 入出链工位锚点字面量(两页数值不同,本文件只消费不改写)
 *   topology          —— TRANSFER_TOPOLOGY 字面量(runtime 的 validateVisualTopology 依赖)
 *   station           —— {sensorYOffset, bollardYOffset, bollardStyle:'amber'|'hazardStripe'}
 *   path              —— {arrowCountMin} 动态轨迹箭头数下限(02 允许虚线段显式 0 箭头)
 *
 * 红线:本文件不含运动学口径(axisT/axisPos/axisV 仍留在各页,步3 再抽),不含热力层与目标 FX
 * 组装(步2),不改任何 sim/trace/KPI 数值。IO / TRANSFER_ANCHOR / RACK 锚点一个数字不动。
 */
"use strict";
if (typeof VISUAL === "undefined") throw new Error("s3_scene_core: 页面必须先声明 VISUAL");
if (typeof S3_SCENE_CONFIG === "undefined") throw new Error("s3_scene_core: 页面必须先声明 S3_SCENE_CONFIG");

/* 黄金参照常量：tools/anim3d_formal.py:44-60,64-125,194-237,418-428 */
const N=20, Z0=-0.5;
const VX=2.0,VZ=0.5,AX=0.5,AZ=0.3,T_LOAD=4.0,T_DWELL=4.0;
/* canonical 仍只有一个逻辑 I/O=(0,0)。INFEED/OUTFEED 仅把 Factory I/O 的 Entry→Load、Unload→Exit 物理工位可视化；不进入 sim/KPI。 */
const IO={x:0.5,y:-0.75,z:0.5};
const INFEED=Object.freeze(Object.assign({},S3_SCENE_CONFIG.infeed));
const OUTFEED=Object.freeze(Object.assign({},S3_SCENE_CONFIG.outfeed));
const CONVEYOR_ENVELOPES=Object.freeze({
  infeed:Object.freeze({xMin:INFEED.x-.59,xMax:INFEED.x+.59,yMin:INFEED.entryY-.05,yMax:INFEED.loadY+.05}),
  outfeed:Object.freeze({xMin:OUTFEED.x-.59,xMax:OUTFEED.x+.59,yMin:OUTFEED.endY-.05,yMax:OUTFEED.startY+.05})
});
const TRANSFER_ANCHOR=Object.freeze({x:IO.x,y:IO.y,z:.55});
const TRANSFER_TOPOLOGY=Object.freeze(Object.assign({},S3_SCENE_CONFIG.topology));
/* 纵深严格回源 tools/anim3d_formal.py:201-213：单深位 0.95 m，不增加第二存储面。 */
const RACK=Object.freeze({frontY:0,backY:.95,backPanelY:1.005,depth:.95,loadY:.50,baseY:.40});
const C={bg:0xe7ecef,floor:0xcbd3d9,seam:0x8f9da7,pad:0xc1cbd1,body:0x526471,
  inner:0x3f4f5b,edge:0xc8d2d8,plinth:0x465761,cap:0x75848f,digit:'#4d5962',
  /* 仍是正式脚本的蓝色分级角色，但扩大明度/饱和度间隔，避免货物与货架、桅杆混成一片。 */
  heavy:0x102a43,mid:0x006bb6,light:0x42c7e6,lid:0x0b1f33,alarm:0xb71c1c,
  amber:0xe7b800,path:0xff6a00,returnPath:0x0084a8,rail:0x64717c,mast:0x123b62,carriage:0x376e9b,
  infeed:0x214e78,outfeed:0x0084a8};

const mount=document.getElementById('gl');
const renderer=new THREE.WebGLRenderer({antialias:true,preserveDrawingBuffer:true,alpha:false});
renderer.setPixelRatio(Math.min(devicePixelRatio,2));
renderer.outputEncoding=THREE.sRGBEncoding;renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=.78;
renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFSoftShadowMap;
renderer.setClearColor(VISUAL.bg);mount.appendChild(renderer.domElement);
const scene=new THREE.Scene();scene.background=new THREE.Color(VISUAL.bg);
const camera=new THREE.PerspectiveCamera(32,1,.1,180);camera.up.set(0,0,1);
const controls=new THREE.OrbitControls(camera,renderer.domElement);controls.enableDamping=true;controls.dampingFactor=.055;
controls.target.set(N/2,.5,8);
/* 总览预设是统一起点；允许受限 Orbit/Pan/Zoom 供评委检查，不允许钻入模型或落到地面下。 */
controls.enablePan=true;controls.screenSpacePanning=true;controls.minDistance=15;controls.maxDistance=56;
controls.minPolarAngle=THREE.MathUtils.degToRad(34);controls.maxPolarAngle=THREE.MathUtils.degToRad(86);

/* 不增加灯数量：按部件调节同色 emissive，拉开层板/阴影/前缘的明度角色。 */
const mat=(color,rough=.72,metal=.08,glow=.055)=>new THREE.MeshStandardMaterial({color,roughness:rough,metalness:metal,
  emissive:new THREE.Color(color).multiplyScalar(glow)});
const M={floor:mat(C.floor,.9,0,.018),pad:mat(C.pad,.82,.02,.025),body:mat(C.body,.68,.24,.03),inner:mat(C.inner,.88,.04,.01),
  edge:mat(C.edge,.55,.18,.08),major:mat(0x536572,.54,.32,.05),plinth:mat(C.plinth,.58,.34,.025),cap:mat(C.cap,.62,.26,.035),
  heavy:mat(C.heavy,.7,.06,.045),mid:mat(C.mid,.73,.05,.055),light:mat(C.light,.76,.04,.065),lid:mat(C.lid,.58,.16,.045),
  amber:mat(C.amber,.56,.04,.12),rail:mat(C.rail,.5,.5,.035),mast:mat(C.mast,.42,.5,.045),carriage:mat(C.carriage,.5,.35,.055)};
M.alarm=mat(C.alarm,.46,.05,.16);
M.floorRack=mat(0xb6c2ca,.91,0,.018);M.floorAisle=mat(0xa6b4bd,.92,0,.016);
M.floorIO=new THREE.MeshStandardMaterial({color:C.amber,roughness:.92,metalness:0,transparent:true,opacity:.14,depthWrite:false});
M.floorStripe=mat(0xf3f5f6,.88,0,.04);
M.deck=mat(0x6f7c87,.70,.24,.028);M.cavity=mat(0x35424e,.94,.02,.008);
M.rubber=mat(0x202830,.82,.08,.015);M.wood=mat(0x9b6a3c,.82,.02,.035);M.sensor=mat(0x26333e,.54,.28,.045);
M.rackBack=mat(0x33434f,.86,.10,.018);M.rackBrace=mat(0x667781,.60,.28,.035);M.foot=mat(0x53636e,.58,.30,.028);
M.scanFrame=mat(0x1f6f96,.48,.22,.095);
M.infeedRail=mat(C.infeed,.54,.30,.065);M.outfeedRail=mat(C.outfeed,.50,.26,.085);
M.scanBeam=new THREE.MeshBasicMaterial({color:0x41b6e6,transparent:true,opacity:.78,depthWrite:false});
M.exitCurtain=new THREE.MeshBasicMaterial({color:0x9fc7d8,transparent:true,opacity:.20,depthWrite:false,side:THREE.DoubleSide});
const reservedCanvas=document.createElement('canvas');reservedCanvas.width=128;reservedCanvas.height=128;const reserved2d=reservedCanvas.getContext('2d');
reserved2d.fillStyle='#65727d';reserved2d.fillRect(0,0,128,128);reserved2d.strokeStyle='#aeb8bf';reserved2d.lineWidth=8;
for(let i=-128;i<256;i+=28){reserved2d.beginPath();reserved2d.moveTo(i,128);reserved2d.lineTo(i+128,0);reserved2d.stroke();}
reserved2d.strokeStyle='#46535e';reserved2d.lineWidth=7;reserved2d.strokeRect(4,4,120,120);
const reservedTexture=new THREE.CanvasTexture(reservedCanvas);reservedTexture.anisotropy=renderer.capabilities.getMaxAnisotropy();
M.reserved=new THREE.MeshStandardMaterial({map:reservedTexture,color:0xffffff,roughness:.78,metalness:.04,emissive:new THREE.Color(0x182028).multiplyScalar(.05)});M.reservedMark=mat(0xcbd2d7,.62,.18,.07);
M.activeCargo=mat(0x42a5f5,.48,.10,.13);
function addBox(sx,sy,sz,x,y,z,material,cast=true,receive=true){
  const mesh=new THREE.Mesh(new THREE.BoxGeometry(sx,sy,sz),material);mesh.position.set(x,y,z);
  mesh.castShadow=cast;mesh.receiveShadow=receive;scene.add(mesh);return mesh;
}
function addInstances(sx,sy,sz,positions,material,cast=true,receive=true){
  const mesh=new THREE.InstancedMesh(new THREE.BoxGeometry(sx,sy,sz),material,positions.length),dummy=new THREE.Object3D();
  positions.forEach((p,i)=>{dummy.position.set(p[0],p[1],p[2]);dummy.updateMatrix();mesh.setMatrixAt(i,dummy.matrix);});
  mesh.instanceMatrix.needsUpdate=true;mesh.castShadow=cast;mesh.receiveShadow=receive;scene.add(mesh);return mesh;
}
const INSTANCE_BOUNDS_EPS=1e-7;
function deriveInstanceBounds(mesh,expectedMinY,expectedMaxY){
  mesh.geometry.computeBoundingBox();const local=mesh.geometry.boundingBox.clone(),matrix=new THREE.Matrix4(),box=new THREE.Box3(),bounds=new THREE.Box3().makeEmpty();
  const depths=[],failedIndices=[];let maxFrontError=0,maxBackError=0;
  for(let index=0;index<mesh.count;index++){
    mesh.getMatrixAt(index,matrix);box.copy(local).applyMatrix4(matrix);bounds.union(box);
    const depth=box.max.y-box.min.y,frontError=Math.abs(box.min.y-expectedMinY),backError=Math.abs(box.max.y-expectedMaxY);
    depths.push(depth);maxFrontError=Math.max(maxFrontError,frontError);maxBackError=Math.max(maxBackError,backError);
    if(frontError>INSTANCE_BOUNDS_EPS||backError>INSTANCE_BOUNDS_EPS||Math.abs(depth-(expectedMaxY-expectedMinY))>INSTANCE_BOUNDS_EPS)failedIndices.push(index);
  }
  const perInstance=Object.freeze({count:depths.length,minDepth:Math.min(...depths),maxDepth:Math.max(...depths),
    maxFrontError,maxBackError,failedIndices:Object.freeze(failedIndices),scannedFromInstanceMatrices:true});
  return Object.freeze({min:Object.freeze(bounds.min.toArray()),max:Object.freeze(bounds.max.toArray()),
    size:Object.freeze(bounds.getSize(new THREE.Vector3()).toArray()),count:mesh.count,perInstance,derivedFromInstanceMatrices:true});
}
function addSegmentInstances(segments,r,material){
  const mesh=new THREE.InstancedMesh(new THREE.CylinderGeometry(r,r,1,8),material,segments.length),dummy=new THREE.Object3D(),up=new THREE.Vector3(0,1,0);
  segments.forEach(([a,b],i)=>{const d=b.clone().sub(a),len=d.length();dummy.position.copy(a).add(b).multiplyScalar(.5);dummy.quaternion.setFromUnitVectors(up,d.normalize());dummy.scale.set(1,len,1);dummy.updateMatrix();mesh.setMatrixAt(i,dummy.matrix);});
  mesh.instanceMatrix.needsUpdate=true;mesh.castShadow=true;mesh.receiveShadow=true;scene.add(mesh);return mesh;
}
function partBox(parent,sx,sy,sz,x,y,z,material,cast=true,receive=true){
  const mesh=new THREE.Mesh(new THREE.BoxGeometry(sx,sy,sz),material);mesh.position.set(x,y,z);
  mesh.castShadow=cast;mesh.receiveShadow=receive;parent.add(mesh);return mesh;
}
function partCylinder(parent,r,depth,x,y,z,material,segments=16){
  const mesh=new THREE.Mesh(new THREE.CylinderGeometry(r,r,depth,segments),material);mesh.position.set(x,y,z);
  mesh.castShadow=true;mesh.receiveShadow=true;parent.add(mesh);return mesh;
}
function partFaceLabel(parent,text,x,y,z,w=.30,h=.12){
  const cv=document.createElement('canvas');cv.width=256;cv.height=96;const g=cv.getContext('2d');
  g.fillStyle='#edf1f4';g.fillRect(0,0,256,96);g.strokeStyle='#17365d';g.lineWidth=8;g.strokeRect(4,4,248,88);
  g.fillStyle='#17365d';g.font='700 46px "Microsoft YaHei", sans-serif';g.textAlign='center';g.textBaseline='middle';g.fillText(text,128,50);
  const mesh=new THREE.Mesh(new THREE.PlaneGeometry(w,h),new THREE.MeshBasicMaterial({map:new THREE.CanvasTexture(cv),transparent:false}));
  mesh.rotation.x=Math.PI/2;mesh.position.set(x,y,z);parent.add(mesh);return mesh;
}
function addFloorFlowLabel(text,x,y,color='#17365d'){
  const cv=document.createElement('canvas');cv.width=512;cv.height=128;const g=cv.getContext('2d');
  g.clearRect(0,0,512,128);g.fillStyle='rgba(247,249,250,.88)';g.fillRect(0,12,512,104);
  g.strokeStyle=color;g.lineWidth=7;g.strokeRect(4,16,504,96);g.fillStyle=color;
  g.font='800 54px "Microsoft YaHei", sans-serif';g.textAlign='center';g.textBaseline='middle';g.fillText(text,256,65);
  const mesh=new THREE.Mesh(new THREE.PlaneGeometry(2.20,.55),new THREE.MeshBasicMaterial({map:new THREE.CanvasTexture(cv),transparent:true,depthWrite:false}));
  mesh.position.set(x,y,Z0+.026);mesh.renderOrder=2;scene.add(mesh);return mesh;
}

/* T3 空间基底：x 围绕货架中心 10、y 围绕单巷道中心 IO.y=-.75 对称展开。 */
const FLOOR={x0:-7.5,x1:N+3,y0:-8.65,y1:7.15};
addBox(FLOOR.x1-FLOOR.x0,FLOOR.y1-FLOOR.y0,.08,(FLOOR.x0+FLOOR.x1)/2,(FLOOR.y0+FLOOR.y1)/2,Z0-.04,M.floor,false,true);
/* 货架基础区 / 设备轨道区 / I/O 交接区，均稍离地避免 Z-fighting。 */
addBox(N+1.4,1.9,.012,N/2,.50,Z0+.006,M.floorRack,false,true);
addBox(N+1.4,1.45,.014,N/2,IO.y-.01,Z0+.007,M.floorAisle,false,true);
/* 并行双线：入/出两条链各自有独立设备基底(01 的 T 形横向交接净空区由页面自行补铺)。 */
addBox(1.55,Math.abs(INFEED.loadY-INFEED.entryY)+.55,.016,INFEED.x,(INFEED.entryY+INFEED.loadY)/2,Z0+.009,M.floorIO,false,true);
addBox(1.55,Math.abs(OUTFEED.startY-OUTFEED.endY)+.55,.016,OUTFEED.x,(OUTFEED.startY+OUTFEED.endY)/2,Z0+.009,M.floorIO,false,true);
const seams=new THREE.Group();
function seamLine(a,b){const g=new THREE.BufferGeometry().setFromPoints([a,b]);seams.add(new THREE.Line(g,new THREE.LineBasicMaterial({color:C.seam})));}
for(let x=FLOOR.x0+1;x<FLOOR.x1;x+=2)seamLine(new THREE.Vector3(x,FLOOR.y0,Z0+.022),new THREE.Vector3(x,FLOOR.y1,Z0+.022));
for(let y=IO.y-6;y<=IO.y+6;y+=2)seamLine(new THREE.Vector3(FLOOR.x0,y,Z0+.022),new THREE.Vector3(FLOOR.x1,y,Z0+.022));
const floorOutline=new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints([
  new THREE.Vector3(FLOOR.x0,FLOOR.y0,Z0+.024),new THREE.Vector3(FLOOR.x1,FLOOR.y0,Z0+.024),
  new THREE.Vector3(FLOOR.x1,FLOOR.y1,Z0+.024),new THREE.Vector3(FLOOR.x0,FLOOR.y1,Z0+.024)
]),new THREE.LineBasicMaterial({color:0x7d8992}));scene.add(floorOutline);
scene.add(seams);
/* 轨道安全边界与端部停止线；中性白线不消费报警红或目标琥珀语义。 */
[IO.y-.79,IO.y+.79].forEach(y=>addBox(N+1.4,.035,.018,N/2,y,Z0+.022,M.floorStripe,false,false));
[-.70,N+.70].forEach(x=>addBox(.035,1.61,.018,x,IO.y,Z0+.022,M.floorStripe,false,false));

/* I/O 站与单深位货架：恢复正式脚本的 0.95 m 纵深；同材质重复件继续实例化。 */
addBox(1.4,1.7,.02,IO.x,IO.y-1.00,Z0+.01,M.pad,false,true);
/* 正式参照：底座 y=-.30..1.10；后背 y=.95..1.06；层板/立柱贯穿 y=0..95。 */
addBox(N+.6,1.40,.50,N/2,RACK.baseY,Z0+.25,M.plinth,true,true);
addBox(N,.11,N,N/2,RACK.backPanelY,N/2,M.rackBack,true,true);
  const CELL_FACE=.94,CELL_BACK_FRONT=.925,availableCellBacks=[],reservedCellVolumes=[];
  for(let x=0;x<N;x++)for(let z=0;z<N;z++){
    const reserved=(x+z)%3===0;
    (reserved?reservedCellVolumes:availableCellBacks).push([x+.5,reserved?RACK.depth/2:.9375,z+.5]);
  }
  if(reservedCellVolumes.length!==133)throw new Error(`预占格数量异常 ${reservedCellVolumes.length}`);
  /* 可用格仍是后腔；预占格改为 0..0.95 m 的完整封闭体。0.94 m 正好贴合 0.06 m 梁内缘，
     133 个封闭体前表面统一齐平 RACK.frontY，后表面统一齐平 RACK.backY，不是贴在格底/格后的薄片。 */
  addInstances(CELL_FACE,.025,CELL_FACE,availableCellBacks,M.inner,false,true);
  const reservedVolumeMesh=addInstances(CELL_FACE,RACK.depth,CELL_FACE,reservedCellVolumes,M.reserved,false,true),
    reservedBounds=deriveInstanceBounds(reservedVolumeMesh,RACK.frontY,RACK.backY);
  const reservedMinY=reservedBounds.min[1],reservedMaxY=reservedBounds.max[1],beamInnerInset=(1-CELL_FACE)/2;
  window.__S3_GEOMETRY_AUDIT=Object.freeze({rackDepth:RACK.depth,rackLoadY:RACK.loadY,beamWidth:.06,cellFace:CELL_FACE,
    availableFrontY:CELL_BACK_FRONT,reservedMinY,reservedMaxY,reservedDepth:reservedMaxY-reservedMinY,
    reservedCount:reservedVolumeMesh.count,availableCount:availableCellBacks.length,reservedBounds,reservedInstanceAudit:reservedBounds.perInstance,
    frontFlushError:Math.abs(reservedMinY-RACK.frontY),backFlushError:Math.abs(reservedMaxY-RACK.backY),
    beamInnerInset,beamInnerFitError:Math.abs(beamInnerInset-.03),actualBoundsDerived:reservedBounds.derivedFromInstanceMatrices});
addInstances(N,RACK.depth,.06,Array.from({length:N+1},(_,z)=>[N/2,RACK.depth/2,z]),M.body,true,true);
addInstances(.06,RACK.depth,N,Array.from({length:N+1},(_,x)=>[x,RACK.depth/2,N/2]),M.body,true,true);
/* 前缘保持浅色以读清 20×20，后框/腔体更暗，纵深由真实几何和阴影产生。 */
addInstances(N,.064,.072,Array.from({length:N+1},(_,z)=>[N/2,.01,z]),M.edge,true,true);
addInstances(.072,.064,N,Array.from({length:N+1},(_,x)=>[x,.01,N/2]),M.edge,true,true);
addInstances(N,.052,.052,Array.from({length:N+1},(_,z)=>[N/2,.93,z]),M.rackBrace,true,true);
const majorXs=Array.from({length:6},(_,index)=>index*4),majorPosts=[];
majorXs.forEach(x=>{majorPosts.push([x,.04,N/2],[x,.91,N/2]);});
addInstances(.10,.10,N+.16,majorPosts,M.major,true,true);
const depthTies=[];majorXs.forEach(x=>{for(let z=0;z<=N;z+=4)depthTies.push([x,RACK.depth/2,z]);});
addInstances(.10,RACK.depth,.10,depthTies,M.rackBrace,true,true);
const braceSegments=[];[0,N].forEach(x=>{for(let z=0;z<N;z+=4){const top=Math.min(N,z+4);
  braceSegments.push([new THREE.Vector3(x,.08,z+.14),new THREE.Vector3(x,.87,top-.14)]);
  braceSegments.push([new THREE.Vector3(x,.87,z+.14),new THREE.Vector3(x,.08,top-.14)]);
}});addSegmentInstances(braceSegments,.026,M.rackBrace);
const feet=[];majorXs.forEach(x=>{feet.push([x,.03,Z0+.025],[x,.92,Z0+.025]);});
addInstances(.30,.28,.05,feet,M.foot,true,true);
addBox(N+.6,1.28,.16,N/2,.46,N+.08,M.cap,true,true);

function makeLabel(text,x,z,scale=.9){
  const cv=document.createElement('canvas');cv.width=128;cv.height=64;const g=cv.getContext('2d');
  g.clearRect(0,0,128,64);g.font='700 36px Arial';g.textAlign='center';g.textBaseline='middle';g.fillStyle=C.digit;g.fillText(text,64,32);
  const sp=new THREE.Sprite(new THREE.SpriteMaterial({map:new THREE.CanvasTexture(cv),transparent:true,depthTest:true}));
  sp.scale.set(scale,scale*.5,1);sp.position.set(x,-.34,z);scene.add(sp);
}
/* 数字坐标不再贴在三维背景上；目标坐标由清晰 DOM 信标承担。 */

/* 官方 sum 规则预占封板已作为背板单元嵌入货架，不再在货架前表面叠放灰片。 */
/* 单巷道轨道：两条物理工位链只在展示层分流，绝不增加货架、堆垛机或容量。 */
addBox(N+1,.14,.08,N/2,IO.y,Z0+.04,M.rail,true,true);

/* 结构件统一为 Factory I/O 式中性钢灰；方向只由地贴、工位与动态路径编码
   (01:1828 先定的原则,02 于 0719 C1 跟进——两页并排不再像两套美术风格)。 */
M.infeedRail=M.outfeedRail=mat(0x6f7c87,.56,.34,.035);
function addConveyorRoller(x,y){const r=new THREE.Mesh(new THREE.CylinderGeometry(.045,.045,.92,12),M.edge);r.rotation.z=Math.PI/2;r.position.set(x,y,.15);r.castShadow=true;scene.add(r);}
function addConveyorLane(lane,nearY,farY,laneMaterial){
  const center=(nearY+farY)/2,len=Math.abs(nearY-farY),direction=Math.sign(farY-nearY)||1;
  [-.54,.54].forEach(dx=>addBox(.10,len+.10,.18,lane.x+dx,center,.08,laneMaterial,true,true));
  [nearY,center,farY].forEach(y=>[-.54,.54].forEach(dx=>addBox(.12,.12,.58,lane.x+dx,y,Z0+.29,laneMaterial,true,true)));
  for(let y=nearY;direction>0?y<=farY:y>=farY;y+=direction*.28)addConveyorRoller(lane.x,y);addConveyorRoller(lane.x,farY);
}

/* 入→装 与 卸→扫→出可见工位；仅做展示层物理语义，坐标仍映射 canonical (0,0)。 */
const stationCollisionSolids=[];
function stationSolid(mesh,label){mesh.userData.collisionLabel=label;stationCollisionSolids.push(mesh);return mesh;}
const entryGate=new THREE.Group();entryGate.name='entryGate';scene.add(entryGate);
[-.62,.62].forEach((dx,index)=>stationSolid(partBox(entryGate,.08,.08,.74,INFEED.x+dx,INFEED.entryY,.24,M.sensor),`ENTRY_POST_${index}`));
stationSolid(partBox(entryGate,1.30,.08,.10,INFEED.x,INFEED.entryY,1.04,M.body),'ENTRY_BEAM');partFaceLabel(entryGate,'入',INFEED.x,INFEED.entryY-.045,1.14,.34,.20);
const loadSign=new THREE.Group();loadSign.name='loadStation';scene.add(loadSign);partFaceLabel(loadSign,'装',INFEED.x,INFEED.loadY-.04,.245,.34,.16);
const unloadSign=new THREE.Group();unloadSign.name='unloadStation';scene.add(unloadSign);partFaceLabel(unloadSign,'卸',OUTFEED.x,OUTFEED.startY-.04,.245,.34,.16);

/* 出库链：UNLOAD 之后依次穿过 SCAN 与 EXIT 软帘；所有权边界与运行时位置严格共锚。 */
const scannerGate=new THREE.Group();scannerGate.name='scannerGate';scene.add(scannerGate);
[-.64,.64].forEach((dx,index)=>stationSolid(partBox(scannerGate,.09,.09,1.58,OUTFEED.x+dx,OUTFEED.scanY,.29,M.scanFrame),`SCAN_POST_${index}`));
stationSolid(partBox(scannerGate,1.37,.10,.12,OUTFEED.x,OUTFEED.scanY,1.04,M.scanFrame),'SCAN_BEAM');
[-.57,.57].forEach((dx,index)=>stationSolid(partBox(scannerGate,.13,.13,.13,OUTFEED.x+dx,OUTFEED.scanY-.055,.55,M.scanBeam,false,false),`SCAN_HEAD_${index}`));
partBox(scannerGate,1.05,.018,.026,OUTFEED.x,OUTFEED.scanY,.55,M.scanBeam,false,false);
addBox(1.35,.055,.016,OUTFEED.x,OUTFEED.scanY,Z0+.030,M.scanBeam,false,false);
partFaceLabel(scannerGate,'扫',OUTFEED.x,OUTFEED.scanY-.045,1.14,.34,.20);
const exitCurtain=new THREE.Group();exitCurtain.name='exitCurtain';scene.add(exitCurtain);
[-.64,.64].forEach((dx,index)=>stationSolid(partBox(exitCurtain,.09,.09,1.58,OUTFEED.x+dx,OUTFEED.maskY,.29,M.body),`EXIT_POST_${index}`));
stationSolid(partBox(exitCurtain,1.37,.10,.12,OUTFEED.x,OUTFEED.maskY,1.04,M.body),'EXIT_BEAM');
for(let dx=-.48;dx<=.481;dx+=.16)partBox(exitCurtain,.055,.018,1.00,OUTFEED.x+dx,OUTFEED.maskY,.50,M.exitCurtain,false,false);
partFaceLabel(exitCurtain,'出',OUTFEED.x,OUTFEED.maskY-.045,1.14,.34,.20);

/* 到位传感器与外缘防撞柱；中间通道保持净空，避免与托盘扫掠包络相交。
   两页差异只在工位 y 微调与防撞柱皮肤(02 于 0719 紫框整修换黄黑警示环纹),几何尺寸/碰撞包络同源。 */
const STATION_SENSOR_DY=S3_SCENE_CONFIG.station.sensorYOffset,BOLLARD_DY=S3_SCENE_CONFIG.station.bollardYOffset;
[[INFEED.x,INFEED.loadY+STATION_SENSOR_DY,0],[OUTFEED.x,OUTFEED.startY+STATION_SENSOR_DY,1]].forEach(([x,y,index])=>[-.62,.62].forEach(dx=>{
  stationSolid(addBox(.07,.07,.64,x+dx,y,Z0+.32,M.sensor,true,true),`STATION_SENSOR_${index}_${dx}`);
  stationSolid(addBox(.12,.12,.10,x+dx,y,Z0+.64,M.amber,true,true),`STATION_CAP_${index}_${dx}`);
}));
M.bollard=S3_SCENE_CONFIG.station.bollardStyle==='hazardStripe'
  ?(()=>{const cv=document.createElement('canvas');cv.width=8;cv.height=64;const g=cv.getContext('2d');
    for(let i=0;i<4;i++){g.fillStyle=i%2?'#1c2126':'#e7b800';g.fillRect(0,i*16,8,16);}
    const tx=new THREE.CanvasTexture(cv);tx.magFilter=THREE.NearestFilter;
    return new THREE.MeshStandardMaterial({map:tx,roughness:.58,metalness:.06});})()
  :M.amber;
[{x:INFEED.x-.78,y:INFEED.loadY+BOLLARD_DY},{x:OUTFEED.x+.78,y:OUTFEED.startY+BOLLARD_DY}].forEach((point,index)=>{
  stationSolid(addBox(.14,.14,.88,point.x,point.y,Z0+.44,M.bollard,true,true),`BOLLARD_${index}`);
  stationSolid(addBox(.19,.19,.08,point.x,point.y,Z0+.04,M.rubber,true,true),`BOLLARD_BASE_${index}`);
});

/* 运行时只根据当前 event 的 from/to 生成轨迹；分段线性 curve 保留物理拐折，不做样条平滑。 */
class PiecewiseLinearCurve extends THREE.Curve{
  constructor(points){super();this.points=points;}
  getPoint(t,target=new THREE.Vector3()){const f=Math.min(1,Math.max(0,t))*(this.points.length-1),i=Math.min(this.points.length-2,Math.floor(f));
    return target.copy(this.points[i]).lerp(this.points[i+1],f-i);}
}
const PATH_ARROW_MIN=S3_SCENE_CONFIG.path.arrowCountMin;
/* 0728 #23:按归一化 progress 截取点列,断点处线性插值补出精确端点(不补会在段间留缝)。
   注意 sampledMachinePath 是**按 progress 等分采样**而非按空间等距,所以 index/(n-1) 天然
   就是时间参数——运动学分段能直接落在点索引上,无需再做弧长参数化。 */
function sliceByProgress(points,from,to){
  const last=points.length-1,f=Math.max(0,Math.min(1,from))*last,t=Math.max(0,Math.min(1,to))*last;
  if(t-f<=1e-9)return[];
  const at=u=>{const i=Math.min(last-1,Math.floor(u));return points[i].clone().lerp(points[i+1],u-i);};
  const out=[at(f)];
  for(let i=Math.ceil(f+1e-9);i<=Math.floor(t-1e-9);i+=1)out.push(points[i].clone());
  out.push(at(t));
  return out.filter((point,index)=>index===0||point.distanceTo(out[index-1])>1e-6);
}
/* 0728 #23 场景内运动学分段(用户拍板「剖面图 + 场景分段路径」):
   加速 / 匀速 / 减速三段用**同色相 + 不同粗细与浓度**区分,不引入第三种颜色——路径颜色本身
   已编码操作类型(入库橙 / 空载蓝),再叠色相会与操作语义打架。匀速段粗而实、加减速段细而淡,
   即便打印成灰度或色觉异常也能靠粗细读出来。匀速段起止各放一个刻度环,把"何时到达 vmax /
   何时开始减速"钉在场景里,与 HUD 剖面图的两条段界线互为印证。 */
const KINEMATIC_BANDS=Object.freeze([
  Object.freeze({key:"accel",radiusScale:.58,opacityScale:.58}),
  Object.freeze({key:"cruise",radiusScale:1.30,opacityScale:1}),
  Object.freeze({key:"decel",radiusScale:.58,opacityScale:.58})
]);
function addPath(points,options={}){const group=new THREE.Group(),material=new THREE.MeshBasicMaterial({
    color:options.color??C.path,transparent:true,opacity:options.opacity??.2,depthWrite:false,depthTest:true}),
    haloMaterial=new THREE.MeshBasicMaterial({color:0xf7fbff,transparent:true,opacity:0,depthWrite:false,depthTest:false});
  const clean=points.filter((point,index)=>index===0||point.distanceTo(points[index-1])>1e-6);
  const materials=[material];const bands=[];
  material.userData.opacityScale=1;
  if(clean.length===1){const halo=new THREE.Mesh(new THREE.SphereGeometry(.22,10,8),haloMaterial),marker=new THREE.Mesh(new THREE.SphereGeometry(.14,10,8),material);
    halo.position.copy(clean[0]);marker.position.copy(clean[0]);group.add(halo,marker);}
  else{const curve=new PiecewiseLinearCurve(clean),segments=Math.max(12,clean.length-1);
    const halo=new THREE.Mesh(new THREE.TubeGeometry(curve,segments,options.haloRadius??.25,8,false),haloMaterial);group.add(halo);
    const radius=options.radius??.16;
    /* breaks=[匀速起, 匀速止](归一化 progress)。缺省或退化(三角形速度剖面、零行程)时
       回落成单段——不假装存在一个不存在的匀速平台。 */
    const breaks=options.kinematicBreaks;
    const usable=Array.isArray(breaks)&&breaks.length===2&&breaks[1]-breaks[0]>.02&&breaks[0]>.02&&breaks[1]<.98;
    if(usable){
      const ranges=[[0,breaks[0]],[breaks[0],breaks[1]],[breaks[1],1]];
      ranges.forEach((range,index)=>{
        const band=KINEMATIC_BANDS[index],piece=sliceByProgress(clean,range[0],range[1]);
        if(piece.length<2)return;
        const bandMaterial=index===1?material:new THREE.MeshBasicMaterial({
          color:material.color.getHex(),transparent:true,opacity:material.opacity*band.opacityScale,depthWrite:false,depthTest:true});
        bandMaterial.userData.opacityScale=band.opacityScale;
        if(index!==1)materials.push(bandMaterial);
        const tube=new THREE.Mesh(new THREE.TubeGeometry(new PiecewiseLinearCurve(piece),Math.max(8,piece.length-1),radius*band.radiusScale,8,false),bandMaterial);
        tube.userData.kinematicBand=band.key;group.add(tube);
        bands.push({key:band.key,from:range[0],to:range[1],radius:Number((radius*band.radiusScale).toFixed(4))});
      });
      /* 刻度环:法线对齐该点切向,才不会在斜行程上看成一个椭圆片。 */
      [breaks[0],breaks[1]].forEach(fr=>{
        const p=curve.getPoint(fr),p2=curve.getPoint(Math.min(1,fr+.01)),dir=p2.clone().sub(p);
        if(dir.lengthSq()<1e-8)return;dir.normalize();
        const ring=new THREE.Mesh(new THREE.TorusGeometry(radius*2.15,radius*.42,6,16),material);
        ring.position.copy(p);ring.quaternion.setFromUnitVectors(new THREE.Vector3(0,0,1),dir);
        ring.userData.kinematicMark=fr===breaks[0]?"cruiseStart":"cruiseEnd";group.add(ring);
      });
    }else{
      const mesh=new THREE.Mesh(new THREE.TubeGeometry(curve,segments,radius,8,false),material);group.add(mesh);
      bands.push({key:"single",from:0,to:1,radius:Number(radius.toFixed(4))});
    }
    /* PATH_ARROW_MIN:02 的虚线段允许显式 0 箭头,01 至少 1;默认 2 两页一致。 */
    const arrowCount=Math.max(PATH_ARROW_MIN,Math.min(3,options.arrowCount??2));
    Array.from({length:arrowCount},(_,index)=>(index+1)/(arrowCount+1)).forEach(fr=>{const p=curve.getPoint(fr),p2=curve.getPoint(Math.min(1,fr+.02)),dir=p2.clone().sub(p);
      if(dir.lengthSq()<1e-8)return;dir.normalize();const arrow=new THREE.Mesh(new THREE.ConeGeometry(.15,.36,10),material);
      arrow.position.copy(p);arrow.quaternion.setFromUnitVectors(new THREE.Vector3(0,1,0),dir);group.add(arrow);});}
  group.userData={operationKey:options.operationKey||null,kind:options.kind||null};scene.add(group);
  /* 统一外观入口:分段后各段有各自的材质与浓度系数,调用方不该(也不必)知道有几段。
     两页原先直接写 path.material.opacity/.depthTest/.color 的写法在分段路径上只会改到一段。 */
  function setAppearance(state){
    materials.forEach(item=>{
      if(state.colorHex!=null)item.color.setHex(state.colorHex);
      if(state.opacity!=null)item.opacity=state.opacity*(item.userData.opacityScale??1);
      if(state.depthTest!=null)item.depthTest=state.depthTest;
    });
    if(state.haloOpacity!=null)haloMaterial.opacity=state.haloOpacity;
  }
  function dispose(){materials.forEach(item=>item.dispose());haloMaterial.dispose();}
  return {group,material,haloMaterial,materials,bands,setAppearance,dispose,kinematic:usableBands(bands)};}
function usableBands(bands){return bands.length>1?Object.freeze(bands.map(band=>Object.freeze(band))):null;}
/* 目标位线框。 */
const targetMat=new THREE.LineBasicMaterial({color:C.amber,transparent:true,opacity:.9});
const targetBox=new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(.92,.92,.92)),targetMat);
targetBox.visible=false;scene.add(targetBox);
const targetPadMat=new THREE.MeshStandardMaterial({color:C.amber,roughness:.72,metalness:.02,emissive:new THREE.Color(C.amber).multiplyScalar(.18),transparent:true,opacity:.52,depthWrite:false});
const targetPad=addBox(.82,.76,.028,0,0,0,targetPadMat,false,false);targetPad.visible=false;
/* 0717 #28 拍板目标格强高亮:发光壳 + 格口面框(贴货架前表面,外 1.0 / 内 .72,不受格内体积遮挡)。
   实体归公共内核,组装成 window.__S3_TARGET_FX 由各页在尾部完成(两页 FX 语言仍有差,步2 收敛)。 */
const targetGlowMat=new THREE.MeshBasicMaterial({color:C.amber,transparent:true,opacity:.34,depthWrite:false,side:THREE.DoubleSide});
const targetGlow=new THREE.Mesh(new THREE.BoxGeometry(1.0,.96,1.0),targetGlowMat);
targetGlow.visible=false;targetGlow.renderOrder=3;scene.add(targetGlow);
const targetFaceShape=new THREE.Shape();
targetFaceShape.moveTo(-.5,-.5);targetFaceShape.lineTo(.5,-.5);targetFaceShape.lineTo(.5,.5);targetFaceShape.lineTo(-.5,.5);targetFaceShape.closePath();
const targetFaceHole=new THREE.Path();
targetFaceHole.moveTo(-.36,-.36);targetFaceHole.lineTo(.36,-.36);targetFaceHole.lineTo(.36,.36);targetFaceHole.lineTo(-.36,.36);targetFaceHole.closePath();
targetFaceShape.holes.push(targetFaceHole);
const targetFaceMat=new THREE.MeshBasicMaterial({color:C.amber,transparent:true,opacity:.92,depthWrite:false,side:THREE.DoubleSide});
const targetFace=new THREE.Mesh(new THREE.ShapeGeometry(targetFaceShape),targetFaceMat);
targetFace.rotation.x=Math.PI/2;/* shape xy 面 → 法线 -y(朝巷道),shape y → 世界 z(层高) */
targetFace.visible=false;targetFace.renderOrder=5;scene.add(targetFace);
/* 0717 #28 用户拍板的大头针式竖直箭头(0728 抽离步2 收进公共内核,两页共用同一实体与同一守卫;
   此前 02 有、01 被我按错误前提删掉,用户 0728 拍板「两页都保留」)。
   箭头必须沿 z(层高)竖直向下:镜头视线大致沿 +y,沿 y 的几何投影后近似一个点(首版教训)。 */
const targetArrowMat=new THREE.MeshBasicMaterial({color:C.amber,transparent:true,opacity:.96,depthWrite:false});
const targetArrow=new THREE.Group();
/* group 原点=箭头尖端;cone 默认尖朝 +y,rotateX(-90°) 后尖朝 -z(竖直向下)。 */
const targetArrowHead=new THREE.Mesh(new THREE.ConeGeometry(.50,1.1,14),targetArrowMat);
targetArrowHead.rotation.x=-Math.PI/2;targetArrowHead.position.z=.55;
const targetArrowTail=new THREE.Mesh(new THREE.CylinderGeometry(.16,.16,.66,10),targetArrowMat);
targetArrowTail.rotation.x=-Math.PI/2;targetArrowTail.position.z=1.43;
targetArrow.add(targetArrowHead,targetArrowTail);
targetArrow.visible=false;targetArrow.renderOrder=4;scene.add(targetArrow);
/* 箭头遮挡守卫(0728 实测修缺陷):旧实现只按水平距离判「已到位就收起」——
     const arrived = Math.abs(frame.machine.x - col) < .60
   实测(scratchpad/arrowsweep.mjs,168 帧采样)漏 4 帧:箭头插进载货台的条件是**三维**的——
   水平接近目标列 **且** 升降高度恰好扫过目标层,单看 x 判不出来。典型漏例:
     cyc2 LINK_TRAVEL p=.6,箭头世界 x=1.5、桅杆 x=2.14,载货台包络 x[1.72,2.56] z[1.36,3.04],
     箭头包络 x[1.01,1.99] z[2.31,4.07] → 三轴全重叠,而水平距离 0.64 > 阈值,守卫放行。
   改为对箭头包围盒与桅杆/载货台包围盒做真实相交判定,阈值不用猜、升降维度不再漏。
   注意:必须先写 arrow.position 再调本函数,最后才写 arrow.visible。 */
const __arrowBox=new THREE.Box3(),__partBox=new THREE.Box3();
function targetArrowBlocked(){
  targetArrow.updateMatrixWorld(true);__arrowBox.setFromObject(targetArrow);
  for(const part of [carrier,mast]){
    if(!part)continue;
    part.updateMatrixWorld(true);__partBox.setFromObject(part);
    if(!__partBox.isEmpty()&&__partBox.intersectsBox(__arrowBox))return true;
  }
  return false;
}
/* 目标 FX 契约:两页共用同一份(此前两页各自在页尾组装,内容不一致=同源分叉的又一处)。 */
window.__S3_TARGET_FX=Object.freeze({glow:targetGlow,glowMat:targetGlowMat,face:targetFace,faceMat:targetFaceMat,
  arrow:targetArrow,arrowMat:targetArrowMat,blocked:targetArrowBlocked,
  amber:new THREE.Color(C.amber),done:new THREE.Color(0x2f9e4f),arrowY:-.45,arrowZGap:1.34,floatAmp:.22});

/* 堆垛机：黄金单桅杆不变；功能细节随同一个 world X 组移动。 */
const mast=addBox(.24,.24,N+.5,IO.x,IO.y,(N+Z0)/2,M.mast,true,false);
const machineParts=[
  addBox(1.05,.86,.22,IO.x,IO.y,Z0+.17,M.carriage,true,true),
  addBox(.82,.48,.18,IO.x,IO.y,N-.02,M.mast,true,true),
  addBox(.46,.44,.42,IO.x,IO.y-.30,Z0+.44,M.lid,true,true)
];
const baseDetails=new THREE.Group();baseDetails.position.set(IO.x,IO.y,0);scene.add(baseDetails);machineParts.push(baseDetails);
[-.36,.36].forEach(x=>partCylinder(baseDetails,.15,.18,x,0,Z0+.15,M.rubber,20));
[-.58,.58].forEach(x=>partBox(baseDetails,.16,.48,.24,x,0,Z0+.24,M.rubber));
/* 驱动柜置于桅杆右侧、载货台包络之外；门缝、状态条与铭牌只增强功能识别，不进入碰撞体。 */
partBox(baseDetails,.26,.36,.58,.60,0,Z0+.48,M.lid);
partBox(baseDetails,.19,.010,.43,.60,-.185,Z0+.48,M.body,false,false);
partBox(baseDetails,.16,.012,.045,.60,-.192,Z0+.62,M.alarm,false,false);
partFaceLabel(baseDetails,'ABB',.60,-.194,Z0+.43,.15,.055);
const topDetails=new THREE.Group();topDetails.position.set(IO.x,IO.y,0);scene.add(topDetails);machineParts.push(topDetails);
partCylinder(topDetails,.20,.22,0,0,N-.04,M.rubber,24);partBox(topDetails,.78,.38,.12,0,0,N+.12,M.mast);
const beltGroup=new THREE.Group();beltGroup.position.set(IO.x,IO.y,0);scene.add(beltGroup);machineParts.push(beltGroup);
const liftBelts=[-.16,.16].map(x=>partBox(beltGroup,.035,.045,1,x,.02,N/2,M.lid,false,false));
/* 桅杆导轨、线缆链和维护横档：全部随 mast X 同步，仅补足设备尺度与功能细节。 */
const mastDetails=new THREE.Group();mastDetails.position.set(IO.x,IO.y,0);scene.add(mastDetails);machineParts.push(mastDetails);
[-.13,.13].forEach(x=>partBox(mastDetails,.035,.045,N+.10,x,-.13,(N+Z0)/2,M.edge,true,false));
partBox(mastDetails,.045,.052,N-.30,.19,.07,(N+Z0)/2,M.lid,false,false);
for(let z=.6;z<N;z+=2)partBox(mastDetails,.29,.038,.035,0,-.13,z,M.carriage,false,false);
const carrier=new THREE.Group();scene.add(carrier);
/* 载货台采用开式 U 型承载架；旧实心块会与木托盘/双叉占据同一体积，已删除。 */
const carriage=new THREE.Group();carrier.add(carriage);
[-.32,.32].forEach(x=>partBox(carriage,.08,.10,.78,x,-.38,.02,M.carriage));
partBox(carriage,.72,.10,.08,0,-.38,-.34,M.carriage);partBox(carriage,.72,.10,.08,0,-.38,.40,M.carriage);
[-.36,.36].forEach(x=>partBox(carrier,.08,.84,.07,x,.02,-.34,M.major));
[-.36,.36].forEach(x=>[-.31,.31].forEach(y=>partBox(carrier,.08,.10,.34,x,y,-.05,M.edge)));
/* 载货台护栏、提升导向与可动伸缩货叉。 */
[-.39,.39].forEach(x=>{partBox(carrier,.055,.055,.72,x,-.34,.08,M.edge);partBox(carrier,.055,.055,.72,x,.34,.08,M.edge);});
partBox(carrier,.84,.055,.055,0,-.34,.42,M.edge);[-.39,.39].forEach(x=>partBox(carrier,.055,.68,.055,x,0,.42,M.edge));
const forkGroup=new THREE.Group();carrier.add(forkGroup);const forks=[];
[-.18,.18].forEach(x=>forks.push(partBox(forkGroup,.12,1.10,.075,x,.30,-.28,M.lid)));
[-.18,.18].forEach(x=>partBox(forkGroup,.13,.055,.09,x,.83,-.28,M.amber,false,false));
/* 两个后置叉驱动座位于叉道外侧，既可见又不与叉体相交。 */
[-.35,.35].forEach(x=>partBox(carrier,.06,.14,.08,x,-.29,-.27,M.sensor));
const cargo=new THREE.Mesh(new THREE.BoxGeometry(.56,.54,.58),M.activeCargo);cargo.position.set(0,0,.05);cargo.castShadow=true;carrier.add(cargo);
const cargoOutline=new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(.575,.555,.595)),new THREE.LineBasicMaterial({color:C.amber,transparent:true,opacity:1}));cargoOutline.name='activeCargoAmberOutline';cargo.add(cargoOutline);
let forkExtension=0,forkDrop=0;
/* 货叉最大伸出 .80 m：叉尖距 y=.95 的货架背板前表面保留 50 mm，同时完整承托深 .60 m 的木托盘。 */
const FORK_MAX=.80,CARGO_REACH=RACK.loadY-TRANSFER_ANCHOR.y,CARGO_Z_OFFSET=.05,CARGO_DROP=.055,DROP_END=.55,TRANSFER_SPLIT=2.0,RETRACT_END=3.4;
if(Math.abs(TRANSFER_ANCHOR.y+CARGO_REACH-RACK.loadY)>1e-9)throw new Error('货物入架纵深锚点不连续');
cargo.visible=false;

/* 候选版多位置打光：环境填充 + 前上主光 + 背侧轮廓光 + 低强度相机补光。 */
const hemi=new THREE.HemisphereLight(0xf7fbff,0x8e9ba5,.48);scene.add(hemi);
const sun=new THREE.DirectionalLight(VISUAL.key,1.02);sun.position.set(12,-18,24);sun.target.position.set(10,0,10);scene.add(sun.target);
sun.castShadow=true;sun.shadow.mapSize.set(2048,2048);sun.shadow.bias=-.00035;sun.shadow.normalBias=.018;sun.shadow.radius=4;
Object.assign(sun.shadow.camera,{left:-34,right:34,top:30,bottom:-16,near:1,far:120});sun.shadow.camera.updateProjectionMatrix();scene.add(sun);
const rim=new THREE.DirectionalLight(VISUAL.rim,.36);rim.position.set(24,8,17);rim.target.position.set(10,.5,10);scene.add(rim.target);scene.add(rim);
const headlight=new THREE.DirectionalLight(0xffffff,.08);headlight.target.position.copy(controls.target);scene.add(headlight.target);scene.add(headlight);

const FOCAL=new THREE.Vector3(...VISUAL.look);
/* 允许检查纵深，但禁止 90° 侧视把 20×20 信息压成一条线。 */
controls.minAzimuthAngle=THREE.MathUtils.degToRad(-65);controls.maxAzimuthAngle=THREE.MathUtils.degToRad(65);
const CAMERA_LIMITS=Object.freeze({x:[-1.5,N+1.5],y:[FLOOR.y0+.6,RACK.backY-.12],z:[.8,N-.8]});
let cameraGuard=false;
function cameraSnapshot(){
  const dx=camera.position.x-controls.target.x,dy=camera.position.y-controls.target.y,planar=Math.max(.0001,Math.hypot(dx,dy));
  return {position:camera.position.toArray(),target:controls.target.toArray(),fov:camera.fov,zoom:camera.zoom,
    azimuth:controls.getAzimuthalAngle(),polar:controls.getPolarAngle(),frontality:-dy/planar,
    azimuthLimit:[controls.minAzimuthAngle,controls.maxAzimuthAngle]};
}
function constrainCamera(){
  if(cameraGuard)return;cameraGuard=true;
  controls.target.x=THREE.MathUtils.clamp(controls.target.x,...CAMERA_LIMITS.x);
  controls.target.y=THREE.MathUtils.clamp(controls.target.y,...CAMERA_LIMITS.y);
  controls.target.z=THREE.MathUtils.clamp(controls.target.z,...CAMERA_LIMITS.z);
  camera.position.z=Math.max(camera.position.z,Z0+.8);
  headlight.position.copy(camera.position);headlight.target.position.copy(controls.target);headlight.target.updateMatrixWorld();cameraGuard=false;
}
/* 页面尾部仍需自行提供:交接台/桥/传送带走线/地贴文字/__S3_TARGET_FX 组装/setCamera/resizeScene,
   并在 setCamera 定义后执行 controls.addEventListener('change',constrainCamera) 与首帧取景。 */
window.__S3_SCENE_CORE=Object.freeze({version:'0728-step1-geometry-materials',
  sharedFrom:['01_连续填仓.html','02_入出闭环.html'],config:S3_SCENE_CONFIG});
