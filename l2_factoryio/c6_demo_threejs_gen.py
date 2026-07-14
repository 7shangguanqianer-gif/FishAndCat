"""C6 demo · Three.js 栈生成器（交互路线）。

读取与 PyVista demo 同一份 AWRA CSV，生成自包含本地 HTML（引用 ./lib/three.min.js
r128 + OrbitControls.js，均已本地化，零外网依赖）。

各展所长（本栈卖点）：鼠标拖拽/滚轮缩放自由视角、逐件回放可播/暂停/重置、
三个与 PyVista 对齐的预设视角按钮（公平对比）、内置「录制 15s」按钮
（canvas.captureStream + MediaRecorder → 自动下载 webm——两栈都交视频的落地）。

色板纪律同 PyVista：蓝系三档按重量、琥珀=正在放置/IO 口、无红。

用法： python c6_demo_threejs_gen.py
产出： Desktop\\C6_demo评审\\ThreeJS\\awra_交互回放.html
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CSV_PATH = HERE.parent / "sim" / "out" / "assignment_awra.csv"
OUT = Path(r"C:\Users\86177\Desktop\C6_demo评审\ThreeJS\awra_交互回放.html")


def load_goods() -> list[dict]:
    rows = []
    with open(CSV_PATH, encoding="utf-8-sig") as fp:
        for r in csv.DictReader(fp):
            rows.append({
                "id": int(r["good_id"]),
                "col": int(r["col"]),
                "tier": int(r["tier"]),
                "w": float(r["weight_kg"]),
                "t": float(r["travel_time_1way_s"]),
            })
    return rows


TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>C6 demo · Three.js 交互回放（AWRA-LS, sim）</title>
<style>
  html,body{margin:0;height:100%;background:#0d1117;color:#e6edf3;
    font-family:"Microsoft YaHei",system-ui,sans-serif;overflow:hidden}
  #hud{position:fixed;top:12px;left:14px;z-index:9;font-size:14px;line-height:1.8;
    background:rgba(13,17,23,.72);border:1px solid #2d3644;border-radius:10px;padding:10px 14px}
  #hud b{color:#f2b13d}
  #bar{position:fixed;bottom:12px;left:50%;transform:translateX(-50%);z-index:9;display:flex;gap:8px}
  button{background:#161b22;color:#e6edf3;border:1px solid #2d3644;border-radius:8px;
    padding:6px 14px;font-size:13px;cursor:pointer}
  button:hover{background:#1c2330}
  button.rec{border-color:#f2b13d;color:#f2b13d}
  #tip{position:fixed;right:14px;top:12px;z-index:9;font-size:12px;color:#9aa7b8;text-align:right}
</style>
</head>
<body>
<div id="hud">AWRA-LS 布局回放(sim)<br>已入库 <b id="n">0</b> / <span id="total">?</span><br>平均单程 <b id="mt">0.00</b> s</div>
<div id="tip">拖拽=旋转 · 滚轮=缩放 · 右键拖=平移<br>视角与 PyVista 版 A/B/C 对齐</div>
<div id="bar">
  <button id="play">▶ 播放</button>
  <button id="reset">⟲ 重置</button>
  <button data-cam="A">视角A 等轴测</button>
  <button data-cam="B">视角B 正面高位</button>
  <button data-cam="C">视角C 低角走廊</button>
  <button id="rec" class="rec">● 录制 15s → webm</button>
</div>
<script src="./lib/three.min.js"></script>
<script src="./lib/OrbitControls.js"></script>
<script>
const GOODS = __GOODS__;
const COLS=20, TIERS=20, CW=1.0, CH=0.6, CD=0.8, GAP=0.12;
const SPANX=COLS*(CW+GAP), SPANZ=TIERS*(CH+GAP);
const W_SORTED=[...GOODS].map(g=>g.w).sort((a,b)=>a-b);
const W33=W_SORTED[Math.floor(W_SORTED.length/3)], W66=W_SORTED[Math.floor(2*W_SORTED.length/3)];
const BLUES=[0x9ecae8,0x4f8fc4,0x1b4f8a], AMBER=0xf2b13d;

const scene=new THREE.Scene(); scene.background=new THREE.Color(0x0d1117);
const camera=new THREE.PerspectiveCamera(50, innerWidth/innerHeight, .1, 500);
const renderer=new THREE.WebGLRenderer({antialias:true, preserveDrawingBuffer:true});
renderer.setSize(innerWidth,innerHeight); renderer.setPixelRatio(devicePixelRatio);
document.body.appendChild(renderer.domElement);
const controls=new THREE.OrbitControls(camera, renderer.domElement);
controls.target.set(SPANX/2-CW/2, 0, SPANZ*0.45); controls.enableDamping=true;

scene.add(new THREE.AmbientLight(0xffffff,.55));
const dir=new THREE.DirectionalLight(0xffffff,.75); dir.position.set(-30,-40,60); scene.add(dir);

// 地面 / 骨架 / IO 口（Z 轴向上与 PyVista 对齐: three 默认 y-up, 这里直接用 z 当高度并把相机 up 设 z）
camera.up.set(0,0,1);
const floor=new THREE.Mesh(new THREE.PlaneGeometry(SPANX+6,4.5),
  new THREE.MeshLambertMaterial({color:0x20262e}));
floor.position.set(SPANX/2-CW/2, .6, -.45); scene.add(floor);
const frameMat=new THREE.MeshLambertMaterial({color:0x3a4656,transparent:true,opacity:.55});
for(let c=0;c<=COLS;c++){const m=new THREE.Mesh(new THREE.BoxGeometry(.06,CD*.9,SPANZ),frameMat);
  m.position.set(c*(CW+GAP)-(CW+GAP)/2,0,SPANZ/2-CH/2);scene.add(m);}
for(let t=0;t<=TIERS;t+=4){const m=new THREE.Mesh(new THREE.BoxGeometry(SPANX,CD*.9,.05),frameMat);
  m.position.set(SPANX/2-CW/2,0,t*(CH+GAP)-(CH+GAP)/2);scene.add(m);}
const io=new THREE.Mesh(new THREE.BoxGeometry(1.6,1.4,.1),
  new THREE.MeshLambertMaterial({color:AMBER})); io.position.set(0,.9,-.38); scene.add(io);

// 货物
const boxGeo=new THREE.BoxGeometry(CW*.92, CD, CH*.9);
const mats=BLUES.map(c=>new THREE.MeshLambertMaterial({color:c}));
const amberMat=new THREE.MeshLambertMaterial({color:AMBER});
function tierOf(w){return w<=W33?0:(w<=W66?1:2);}
const meshes=GOODS.map(g=>{
  const m=new THREE.Mesh(boxGeo, mats[tierOf(g.w)]);
  m.position.set(g.col*(CW+GAP), 0, g.tier*(CH+GAP)); m.visible=false; scene.add(m);
  return m;});

// 预设视角(与 PyVista set_camera 同参数化)
function setCam(azim,elev,zoom){
  const f=controls.target, dist=SPANX*1.55/zoom, a=azim*Math.PI/180, e=elev*Math.PI/180;
  camera.position.set(f.x+dist*Math.sin(a)*Math.cos(e), f.y-dist*Math.cos(a)*Math.cos(e), f.z+dist*Math.sin(e));
  camera.lookAt(f);}
const CAMS={A:[-35,22,1.0], B:[-5,32,1.05], C:[-62,8,0.9]};
setCam(...CAMS.A);
document.querySelectorAll('[data-cam]').forEach(b=>b.onclick=()=>setCam(...CAMS[b.dataset.cam]));

// 回放状态机
let idx=0, playing=false, acc=0, lastMesh=null;
const PLACE_MS=100;   // 每件 100ms ≈ PyVista 每 2 帧@24fps
const nEl=document.getElementById('n'), mtEl=document.getElementById('mt');
document.getElementById('total').textContent=GOODS.length;
let travelSum=0;
function step(){
  if(idx>=GOODS.length){playing=false;return;}
  if(lastMesh) lastMesh.material=mats[tierOf(GOODS[idx-1].w)];
  const g=GOODS[idx], m=meshes[idx];
  m.visible=true; m.material=amberMat; lastMesh=m;
  travelSum+=g.t; idx++;
  nEl.textContent=idx; mtEl.textContent=(travelSum/idx).toFixed(2);}
document.getElementById('play').onclick=e=>{playing=!playing;e.target.textContent=playing?'❚❚ 暂停':'▶ 播放';};
document.getElementById('reset').onclick=()=>{idx=0;travelSum=0;playing=false;lastMesh=null;
  meshes.forEach(m=>m.visible=false);nEl.textContent=0;mtEl.textContent='0.00';
  document.getElementById('play').textContent='▶ 播放';};

// 录制(官方机制: canvas.captureStream + MediaRecorder)
document.getElementById('rec').onclick=()=>{
  const stream=renderer.domElement.captureStream(30);
  let mime='video/webm;codecs=vp9';
  if(!MediaRecorder.isTypeSupported(mime)) mime='video/webm;codecs=vp8';
  const rec=new MediaRecorder(stream,{mimeType:mime,videoBitsPerSecond:6_000_000});
  const chunks=[]; rec.ondataavailable=e=>chunks.push(e.data);
  rec.onstop=()=>{const a=document.createElement('a');
    a.href=URL.createObjectURL(new Blob(chunks,{type:'video/webm'}));
    a.download='awra_threejs_录制15s.webm'; a.click();};
  document.getElementById('reset').click(); document.getElementById('play').click();
  rec.start(); setTimeout(()=>rec.stop(), 15000);};

let last=performance.now();
function loop(now){
  requestAnimationFrame(loop);
  if(playing){acc+=now-last; while(acc>=PLACE_MS){acc-=PLACE_MS; step();}} else {acc=0;}
  last=now; controls.update(); renderer.render(scene,camera);}
requestAnimationFrame(loop);
addEventListener('resize',()=>{camera.aspect=innerWidth/innerHeight;
  camera.updateProjectionMatrix();renderer.setSize(innerWidth,innerHeight);});
</script>
</body>
</html>
"""


def main() -> None:
    goods = load_goods()
    html = TEMPLATE.replace("__GOODS__", json.dumps(goods, separators=(",", ":")))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    print(f"[html] {OUT}  ({len(goods)} 件内嵌)")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    main()
