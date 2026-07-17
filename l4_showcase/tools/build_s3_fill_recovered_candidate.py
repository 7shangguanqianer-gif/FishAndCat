#!/usr/bin/env python3
"""Build the recovered S3 fill candidate from the mature visual mother.

The builder is intentionally strict: every replacement must match exactly once.
It never edits the formal S3 page or the visual mother in place.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "l4_showcase" / "src" / "archive_候选历史" / "样张_S3_三方向候选.html"
OUTPUT = ROOT / "l4_showcase" / "src" / "archive_候选历史" / "样张_S3_fill恢复候选.html"
MANIFEST = ROOT / "l4_showcase" / "design_reviews" / "0716_S3_fill恢复候选_manifest.json"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def build() -> dict:
    source_bytes = SOURCE.read_bytes()
    # Normalize the generated candidate only; the source bytes and source hash stay untouched.
    text = source_bytes.decode("utf-8").replace("\r\n", "\n")

    text = replace_once(
        text,
        "document.title=`智储优控 · S3 A重做 · ${VISUAL.name}`;",
        "document.title=`智储优控 · S3 连续填满恢复候选 · ${VISUAL.name}`;\n"
        "document.documentElement.dataset.s3Mode='fill-only-candidate';",
        "candidate title",
    )

    old_topology = """/* canonical 仍只有一个逻辑 I/O=(0,0)。INFEED/OUTFEED 仅把 Factory I/O 的 Entry→Load、Unload→Exit 物理工位可视化；不进入 sim/KPI。 */
const IO={x:0.5,y:-0.75,z:0.5};
const STATION_Y=IO.y-1.75;
const INFEED=Object.freeze({y:STATION_Y,entryX:IO.x-4.40,loadX:IO.x-.90,z:.55,width:1.02});
const OUTFEED=Object.freeze({y:STATION_Y,startX:IO.x+.90,scanX:IO.x+2.05,maskX:IO.x+3.20,endX:IO.x+4.40,z:.55,width:1.02});
const TRANSFER_ANCHOR=Object.freeze({x:IO.x,y:IO.y,z:.55});
const CONVEYOR_ENVELOPES=Object.freeze({
  infeed:Object.freeze({xMin:INFEED.entryX-.05,xMax:INFEED.loadX+.05,yMin:INFEED.y-.59,yMax:INFEED.y+.59}),
  outfeed:Object.freeze({xMin:OUTFEED.startX-.05,xMax:OUTFEED.endX+.05,yMin:OUTFEED.y-.59,yMax:OUTFEED.y+.59})
});
/* 同一直线但不共带：入口段与出口段横向分列 I/O 两侧，画面可同时看见且没有方向争用。 */
const TRANSFER_TOPOLOGY=Object.freeze({logicalOrigin:[0,0],visualOnly:true,singleAisle:true,singleRackFace:true,
  collinear:true,collinearAxis:'x',sharedBelt:false,oppositeSides:true,rackFrontY:0});"""
    new_topology = """/* canonical 仍只有一个逻辑 I/O=(0,0)。两条物理链仅在展示层映射该锚点，不进入 sim/KPI。 */
const IO={x:0.5,y:-0.75,z:0.5};
/* 同侧并行双链：两条链沿 y 轴垂直货架，横向 T 形转接台只做互锁交接。 */
const INFEED=Object.freeze({x:-0.45,entryY:-5.55,loadY:-1.55,z:.55,width:1.02,direction:'toward-rack'});
const OUTFEED=Object.freeze({x:1.45,startY:-1.55,scanY:-2.75,maskY:-3.95,endY:-5.55,z:.55,width:1.02,direction:'away-from-rack'});
const CROSSBAR=Object.freeze({xMin:INFEED.x,xMax:OUTFEED.x,y:INFEED.loadY,z:.55});
const TRANSFER_ANCHOR=Object.freeze({x:IO.x,y:IO.y,z:.55});
const CONVEYOR_ENVELOPES=Object.freeze({
  infeed:Object.freeze({xMin:INFEED.x-.59,xMax:INFEED.x+.59,yMin:INFEED.entryY-.05,yMax:INFEED.loadY+.05}),
  outfeed:Object.freeze({xMin:OUTFEED.x-.59,xMax:OUTFEED.x+.59,yMin:OUTFEED.endY-.05,yMax:OUTFEED.startY+.05})
});
const TRANSFER_TOPOLOGY=Object.freeze({logicalOrigin:[0,0],visualOnly:true,singleAisle:true,singleRackFace:true,
  parallel:true,parallelAxis:'y',sharedBelt:false,sameSide:true,tJunction:true,rackFrontY:0});"""
    text = replace_once(text, old_topology, new_topology, "same-side T topology constants")

    old_floor_io = """/* 共轴但分段的入/出库链使用一条连续设备基底；I/O 横向转接区另铺小基底。 */
addBox(OUTFEED.endX-INFEED.entryX+.70,2.30,.016,(INFEED.entryX+OUTFEED.endX)/2,STATION_Y,Z0+.009,M.floorIO,false,true);
addBox(3.10,2.10,.017,IO.x,(STATION_Y+IO.y)/2,Z0+.010,M.floorIO,false,true);"""
    new_floor_io = """/* 同侧并行双链各自有独立设备基底；T 形横向交接台与逻辑 I/O 另设连续净空区。 */
addBox(1.55,Math.abs(INFEED.loadY-INFEED.entryY)+.55,.016,INFEED.x,(INFEED.entryY+INFEED.loadY)/2,Z0+.009,M.floorIO,false,true);
addBox(1.55,Math.abs(OUTFEED.startY-OUTFEED.endY)+.55,.016,OUTFEED.x,(OUTFEED.startY+OUTFEED.endY)/2,Z0+.009,M.floorIO,false,true);
addBox(Math.abs(CROSSBAR.xMax-CROSSBAR.xMin)+1.20,1.40,.017,IO.x,CROSSBAR.y,Z0+.010,M.floorIO,false,true);
addBox(1.20,Math.abs(CROSSBAR.y-IO.y)+.70,.017,IO.x,(CROSSBAR.y+IO.y)/2,Z0+.011,M.floorIO,false,true);"""
    text = replace_once(text, old_floor_io, new_floor_io, "same-side T floor pads")

    old_geometry = """/* 官方 sum 规则预占封板已作为背板单元嵌入货架，不再在货架前表面叠放灰片。 */
/* 单巷道轨道 + 同一逻辑 I/O 前端的两条物理工位链。两条链只在展示层分流，绝不增加货架、堆垛机或容量。 */
addBox(N+1,.14,.08,N/2,IO.y,Z0+.04,M.rail,true,true);
addBox(1.05,.76,.16,IO.x,IO.y-.38,Z0+.10,M.amber,true,true);

function addTransferBridge(from,to,material){
  const dx=to.x-from.x,dy=to.y-from.y,len=Math.hypot(dx,dy),bridge=new THREE.Mesh(new THREE.BoxGeometry(len,.62,.13),material);
  bridge.position.set((from.x+to.x)/2,(from.y+to.y)/2,.095);bridge.rotation.z=Math.atan2(dy,dx);bridge.castShadow=true;bridge.receiveShadow=true;scene.add(bridge);return bridge;
}
function addConveyorRoller(x,y){const r=new THREE.Mesh(new THREE.CylinderGeometry(.045,.045,.92,12),M.edge);r.position.set(x,y,.15);r.castShadow=true;scene.add(r);}
function addConveyorLane(lane,nearX,farX,laneMaterial){
  const center=(nearX+farX)/2,len=Math.abs(nearX-farX),direction=Math.sign(farX-nearX)||1;
  [-.54,.54].forEach(dy=>addBox(len+.10,.10,.18,center,lane.y+dy,.08,laneMaterial,true,true));
  [nearX,center,farX].forEach(x=>[-.54,.54].forEach(dy=>addBox(.12,.12,.58,x,lane.y+dy,Z0+.29,laneMaterial,true,true)));
  for(let x=nearX;direction>0?x<=farX:x>=farX;x+=direction*.28)addConveyorRoller(x,lane.y);addConveyorRoller(farX,lane.y);
}
addConveyorLane(INFEED,INFEED.entryX,INFEED.loadX,M.infeedRail);
addConveyorLane(OUTFEED,OUTFEED.startX,OUTFEED.endX,M.outfeedRail);
addTransferBridge({x:INFEED.loadX,y:INFEED.y},TRANSFER_ANCHOR,M.infeedRail);
addTransferBridge(TRANSFER_ANCHOR,{x:OUTFEED.startX,y:OUTFEED.y},M.outfeedRail);
addFloorFlowLabel('入库  →',(INFEED.entryX+INFEED.loadX)/2,STATION_Y-.83,'#17365d');
addFloorFlowLabel('→  出库',(OUTFEED.startX+OUTFEED.endX)/2,STATION_Y-.83,'#2f7895');

/* 入→装 与 卸→扫→出可见工位；仅做展示层物理语义，坐标仍映射 canonical (0,0)。 */
const stationCollisionSolids=[];
function stationSolid(mesh,label){mesh.userData.collisionLabel=label;stationCollisionSolids.push(mesh);return mesh;}
const entryGate=new THREE.Group();entryGate.name='entryGate';scene.add(entryGate);
[-.62,.62].forEach((dy,index)=>stationSolid(partBox(entryGate,.08,.08,.74,INFEED.entryX,INFEED.y+dy,.24,M.sensor),`ENTRY_POST_${index}`));
stationSolid(partBox(entryGate,.08,1.30,.10,INFEED.entryX,INFEED.y,1.04,M.body),'ENTRY_BEAM');partFaceLabel(entryGate,'入',INFEED.entryX,INFEED.y-.665,1.14,.34,.20);
const loadSign=new THREE.Group();loadSign.name='loadStation';scene.add(loadSign);partFaceLabel(loadSign,'装',INFEED.loadX,INFEED.y-.56,.245,.34,.16);
const unloadSign=new THREE.Group();unloadSign.name='unloadStation';scene.add(unloadSign);partFaceLabel(unloadSign,'卸',OUTFEED.startX,OUTFEED.y-.56,.245,.34,.16);

/* 出库链：UNLOAD 之后依次穿过 SCAN 与 EXIT 软帘；所有权边界与运行时位置严格共锚。 */
const scannerGate=new THREE.Group();scannerGate.name='scannerGate';scene.add(scannerGate);
[-.64,.64].forEach((dy,index)=>stationSolid(partBox(scannerGate,.09,.09,1.58,OUTFEED.scanX,OUTFEED.y+dy,.29,M.scanFrame),`SCAN_POST_${index}`));
stationSolid(partBox(scannerGate,.10,1.37,.12,OUTFEED.scanX,OUTFEED.y,1.04,M.scanFrame),'SCAN_BEAM');
[-.57,.57].forEach((dy,index)=>stationSolid(partBox(scannerGate,.13,.13,.13,OUTFEED.scanX-.055,OUTFEED.y+dy,.55,M.scanBeam,false,false),`SCAN_HEAD_${index}`));
partBox(scannerGate,.018,1.05,.026,OUTFEED.scanX,OUTFEED.y,.55,M.scanBeam,false,false);
addBox(.055,1.35,.016,OUTFEED.scanX,OUTFEED.y,Z0+.030,M.scanBeam,false,false);
partFaceLabel(scannerGate,'扫',OUTFEED.scanX,OUTFEED.y-.665,1.14,.34,.20);
const exitCurtain=new THREE.Group();exitCurtain.name='exitCurtain';scene.add(exitCurtain);
[-.64,.64].forEach((dy,index)=>stationSolid(partBox(exitCurtain,.09,.09,1.58,OUTFEED.maskX,OUTFEED.y+dy,.29,M.body),`EXIT_POST_${index}`));
stationSolid(partBox(exitCurtain,.10,1.37,.12,OUTFEED.maskX,OUTFEED.y,1.04,M.body),'EXIT_BEAM');
for(let dy=-.48;dy<=.481;dy+=.16)partBox(exitCurtain,.018,.055,1.00,OUTFEED.maskX,OUTFEED.y+dy,.50,M.exitCurtain,false,false);
partFaceLabel(exitCurtain,'出',OUTFEED.maskX,OUTFEED.y-.665,1.14,.34,.20);

/* 双工位到位传感器与外缘防撞柱；中间通道保持净空，避免旧版与托盘扫掠包络相交。 */
[INFEED,OUTFEED].forEach((lane,index)=>[-.62,.62].forEach(dy=>{
  const x=index===0?INFEED.loadX-.18:OUTFEED.startX+.18;
  stationSolid(addBox(.07,.07,.64,x,lane.y+dy,Z0+.32,M.sensor,true,true),`STATION_SENSOR_${index}_${dy}`);
  stationSolid(addBox(.12,.12,.10,x,lane.y+dy,Z0+.64,M.amber,true,true),`STATION_CAP_${index}_${dy}`);
}));
[{x:INFEED.loadX-.25,y:INFEED.y-.78},{x:OUTFEED.startX+.25,y:OUTFEED.y-.78}].forEach((point,index)=>{
  stationSolid(addBox(.14,.14,.88,point.x,point.y,Z0+.44,M.amber,true,true),`BOLLARD_${index}`);
  stationSolid(addBox(.19,.19,.08,point.x,point.y,Z0+.04,M.rubber,true,true),`BOLLARD_BASE_${index}`);
});"""
    new_geometry = """/* 官方 sum 规则预占封板已作为背板单元嵌入货架，不再在货架前表面叠放灰片。 */
/* 单巷道轨道 + 同侧并行双链。两条链与货架垂直，在 T 形互锁台映射到唯一逻辑 I/O。 */
addBox(N+1,.14,.08,N/2,IO.y,Z0+.04,M.rail,true,true);
addBox(2.36,.88,.16,IO.x,CROSSBAR.y,Z0+.10,M.major,true,true);
addBox(.92,.84,.16,IO.x,(CROSSBAR.y+IO.y)/2,Z0+.10,M.amber,true,true);

function addTransferBridge(from,to,material,width=.62){
  const dx=to.x-from.x,dy=to.y-from.y,len=Math.hypot(dx,dy),bridge=new THREE.Mesh(new THREE.BoxGeometry(len,width,.13),material);
  bridge.position.set((from.x+to.x)/2,(from.y+to.y)/2,.095);bridge.rotation.z=Math.atan2(dy,dx);bridge.castShadow=true;bridge.receiveShadow=true;scene.add(bridge);return bridge;
}
/* 结构件统一为 Factory I/O 式中性钢灰；方向只由地贴、工位与动态路径编码。 */
M.infeedRail=M.outfeedRail=mat(0x6f7c87,.56,.34,.035);
function addConveyorRollerY(x,y){const r=new THREE.Mesh(new THREE.CylinderGeometry(.045,.045,.92,12),M.edge);r.rotation.z=Math.PI/2;r.position.set(x,y,.15);r.castShadow=true;scene.add(r);}
function addConveyorLaneY(lane,nearY,farY,laneMaterial){
  const center=(nearY+farY)/2,len=Math.abs(nearY-farY),direction=Math.sign(farY-nearY)||1;
  [-.54,.54].forEach(dx=>addBox(.10,len+.10,.18,lane.x+dx,center,.08,laneMaterial,true,true));
  [nearY,center,farY].forEach(y=>[-.54,.54].forEach(dx=>addBox(.12,.12,.58,lane.x+dx,y,Z0+.29,laneMaterial,true,true)));
  for(let y=nearY;direction>0?y<=farY:y>=farY;y+=direction*.28)addConveyorRollerY(lane.x,y);addConveyorRollerY(lane.x,farY);
}
addConveyorLaneY(INFEED,INFEED.entryY,INFEED.loadY,M.infeedRail);
addConveyorLaneY(OUTFEED,OUTFEED.startY,OUTFEED.endY,M.outfeedRail);
addTransferBridge({x:CROSSBAR.xMin,y:CROSSBAR.y},{x:CROSSBAR.xMax,y:CROSSBAR.y},M.major,.70);
addTransferBridge({x:IO.x,y:CROSSBAR.y},TRANSFER_ANCHOR,M.amber,.70);
addFloorFlowLabel('入库  ↑',INFEED.x,(INFEED.entryY+INFEED.loadY)/2,'#214e78');
addFloorFlowLabel('出库  ↓',OUTFEED.x,(OUTFEED.startY+OUTFEED.endY)/2,'#0084a8');

/* 入→装 与 卸→扫→出工位沿 y 轴布置；工位横梁跨 x，避免与货物流向混淆。 */
const stationCollisionSolids=[];
function stationSolid(mesh,label){mesh.userData.collisionLabel=label;stationCollisionSolids.push(mesh);return mesh;}
const entryGate=new THREE.Group();entryGate.name='entryGate';scene.add(entryGate);
[-.62,.62].forEach((dx,index)=>stationSolid(partBox(entryGate,.08,.08,.74,INFEED.x+dx,INFEED.entryY,.24,M.sensor),`ENTRY_POST_${index}`));
stationSolid(partBox(entryGate,1.30,.08,.10,INFEED.x,INFEED.entryY,1.04,M.body),'ENTRY_BEAM');partFaceLabel(entryGate,'入',INFEED.x,INFEED.entryY-.045,1.14,.34,.20);
const loadSign=new THREE.Group();loadSign.name='loadStation';scene.add(loadSign);partFaceLabel(loadSign,'装',INFEED.x,INFEED.loadY-.04,.245,.34,.16);
const unloadSign=new THREE.Group();unloadSign.name='unloadStation';scene.add(unloadSign);partFaceLabel(unloadSign,'卸',OUTFEED.x,OUTFEED.startY-.04,.245,.34,.16);

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

/* 传感器与防撞柱只放在两条链的外缘；T 形横向交接区保持净空。 */
[[INFEED.x,INFEED.loadY,0],[OUTFEED.x,OUTFEED.startY,1]].forEach(([x,y,index])=>[-.62,.62].forEach(dx=>{
  stationSolid(addBox(.07,.07,.64,x+dx,y,Z0+.32,M.sensor,true,true),`STATION_SENSOR_${index}_${dx}`);
  stationSolid(addBox(.12,.12,.10,x+dx,y,Z0+.64,M.amber,true,true),`STATION_CAP_${index}_${dx}`);
}));
[{x:INFEED.x-.78,y:INFEED.loadY-.24},{x:OUTFEED.x+.78,y:OUTFEED.startY-.24}].forEach((point,index)=>{
  stationSolid(addBox(.14,.14,.88,point.x,point.y,Z0+.44,M.amber,true,true),`BOLLARD_${index}`);
  stationSolid(addBox(.19,.19,.08,point.x,point.y,Z0+.04,M.rubber,true,true),`BOLLARD_BASE_${index}`);
});"""
    text = replace_once(text, old_geometry, new_geometry, "same-side T conveyor geometry")

    text = replace_once(
        text,
        "<script src=\"../out/s3_trace_manifest.js\"></script>\n<script src=\"../out/s1_comparison_evidence.js\"></script>\n<script src=\"./s3_trace_store.js\"></script>\n<script src=\"./s3_ac_runtime.js\"></script>",
        "<script src=\"./s3_fill_store.js\"></script>\n<script src=\"./s3_fill_candidate_runtime.js\"></script>",
        "fill runtime scripts",
    )

    css = r"""
  /* 0716 fill-only candidate: one visible job source, capacity bookmarks and Chinese-first evidence. */
  html[data-s3-mode="fill-only-candidate"] #comparisonMini,
  html[data-s3-mode="fill-only-candidate"] #faultStateBanner,
  html[data-s3-mode="fill-only-candidate"] #cycleReset{display:none!important}
  html[data-s3-mode="fill-only-candidate"] #workHud{grid-template-rows:auto auto auto auto minmax(0,1fr) auto;
    grid-template-areas:"head head" "controls controls" "decision decision" "bookmark bookmark" "map insight" "phase insight"}
  html[data-s3-mode="fill-only-candidate"] #insightStack{grid-row:5/7}
  html[data-s3-mode="fill-only-candidate"] #phaseRail{align-self:start}
  html[data-s3-mode="fill-only-candidate"] #phaseSegments{grid-template-columns:repeat(7,minmax(0,1fr))!important}
  #fillBookmarks{grid-area:bookmark;border:1px solid #b9c3ca;border-left:4px solid #ff000f;background:#fff;padding:7px 8px}
  #fillBookmarks .fillHead{display:flex;align-items:baseline;justify-content:space-between;gap:8px;margin-bottom:6px}
  #fillBookmarks .fillHead b{font-size:11px;color:#17202b}#fillBookmarks .fillHead span{font:8px/1.2 Consolas,monospace;color:#65717c}
  #fillBookmarkButtons{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:3px}
  #fillBookmarkButtons button{min-width:0;border:1px solid #bcc5cc;background:#edf1f3;padding:5px 2px;color:#24313a;font:800 9px/1.15 Consolas,"Microsoft YaHei",sans-serif;cursor:pointer}
  #fillBookmarkButtons button small{display:block;margin-top:2px;color:#66717a;font-size:7.5px}
  #fillBookmarkButtons button[aria-current="true"]{border-color:#ff000f;background:#fff4f2;box-shadow:inset 0 -3px #ff000f;color:#111}
  #fillEvidence{margin-top:6px;display:grid;grid-template-columns:repeat(4,minmax(0,1fr));border-top:1px solid #d6dde2}
  #fillEvidence span{padding:5px 4px;border-right:1px solid #d6dde2;color:#65717c;font-size:8px}#fillEvidence span:last-child{border-right:0}
  #fillEvidence b{display:block;color:#17202b;font:800 10px/1.2 Consolas,monospace}
  #decisionWrap .decisionLine{display:flex;justify-content:space-between;gap:8px;padding:4px 0;border-bottom:1px solid #e1e6e9;font-size:9px}
  #decisionWrap .decisionLine:last-child{border-bottom:0}#decisionWrap .decisionLine b{color:#17365d}
  #decisionWrap .cand{grid-template-columns:40px 58px minmax(82px,1fr) 30px;font-family:Consolas,"Microsoft YaHei",sans-serif}
  #decisionWrap .cand>span:nth-child(3){text-align:right;color:#17365d;font-weight:700;white-space:nowrap}
  #decisionWrap .candidateTop{margin-top:5px;padding:5px 6px;background:#edf3f6;font:8px/1.35 Consolas,"Microsoft YaHei",sans-serif}
  #processGuide{padding:6px 7px;border:1px solid #bfc7cd;background:#fff;min-height:0}
  .processGuideHead{display:flex;justify-content:space-between;gap:5px;align-items:baseline;padding-bottom:5px;border-bottom:1px solid #d6dde2}
  .processGuideHead b{font-size:9.5px}.processGuideHead span{color:#69757e;font-size:7px;white-space:nowrap}
  #processGuideRows{display:grid;gap:3px;margin-top:5px}.processGuideRow{display:grid;grid-template-columns:18px minmax(0,1fr);gap:2px 5px;padding:4px 5px;border-left:3px solid #aeb8bf;background:#f1f4f6}
  .processGuideRow i{grid-row:1/3;align-self:center;width:17px;height:17px;border-radius:50%;background:#6d7b85;color:#fff;font:800 8px/17px Consolas,monospace;text-align:center;font-style:normal}
  .processGuideRow b{font-size:8.5px;line-height:1.15}.processGuideRow span{overflow:hidden;color:#5f6b74;font-size:7px;line-height:1.2;white-space:nowrap;text-overflow:ellipsis}
  .processGuideRow.active{border-left-color:#ff000f;background:#fff3ef}.processGuideRow.active i{background:#ff000f}.processGuideRow.active b{color:#b4000b}
  @media(max-height:780px){#processGuide{display:none}}
  #sceneDock #reserveRuleBadge .out{display:none}
  #releaseBadge{position:absolute;z-index:8;right:14px;top:12px;padding:6px 8px;border:1px solid #b8c2ca;background:#fffffff2;color:#33414b;font:8px/1.35 Consolas,monospace;box-shadow:0 2px 10px #32414e18}
  #releaseBadge b{display:block;color:#17365d;font-size:9px}
"""
    text = replace_once(text, "</style>", css + "\n</style>", "fill candidate CSS")

    output_bytes = text.encode("utf-8")
    OUTPUT.write_bytes(output_bytes)
    manifest = {
        "schema_version": "s3-fill-recovered-candidate-build-v1",
        "status": "CANDIDATE_ONLY_FORMAL_FROZEN",
        "source": str(SOURCE.relative_to(ROOT)).replace("\\", "/"),
        "source_sha256": sha256_bytes(source_bytes),
        "output": str(OUTPUT.relative_to(ROOT)).replace("\\", "/"),
        "output_sha256": sha256_bytes(output_bytes),
        "locked_changes": [
            "same-side parallel dual lanes perpendicular to rack with T transfer",
            "file-protocol fill-only store/runtime",
            "single visible current-job source",
            "capacity bookmarks derive from one active release",
        ],
        "formal_page_untouched": "l4_showcase/src/样张_S3定稿.html",
    }
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=True, indent=2))
