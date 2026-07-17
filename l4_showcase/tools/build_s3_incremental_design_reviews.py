# -*- coding: utf-8 -*-
"""从成熟 S3 母版机械派生三套增量排版候选；不重画三维场景。"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "l4_showcase" / "src"
SOURCE = SRC / "archive_候选历史" / "样张_S3_三方向候选.html"
GATE_ROOT = ROOT / "l4_showcase" / "out" / "s3_fill_data_gate"
OUTPUTS = {
    "left": SRC / "样张_S3_母版增量方案_1_顶部横排.html",
    "map": SRC / "样张_S3_母版增量方案_2_地图侧列.html",
    "insight": SRC / "样张_S3_母版增量方案_3_证据卡组.html",
}
MANIFEST = ROOT / "l4_showcase" / "design_reviews" / "0716_S3_母版增量方案_manifest.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def gate_release() -> dict:
    pointer = json.loads((GATE_ROOT / "latest.json").read_text(encoding="utf-8"))
    return {
        "release_id": pointer["release_id"],
        "manifest_payload_sha256": pointer["manifest_payload_sha256"],
    }


COMMON_CSS = r"""
<style id="s3IncrementalReviewCss">
  /* 仅评审排版层：三维实体、相机、光照、运动学、trace 与交互代码来自母版。 */
  #incrementalReviewMark{display:grid;gap:1px;justify-items:end;margin-left:auto;color:#53616b;
    font:700 7px/1.25 Consolas,"Microsoft YaHei",monospace;white-space:nowrap}
  #incrementalReviewMark b{color:#b0000b;font:800 8px/1.2 "Microsoft YaHei",sans-serif}
  #withdrawnReviewBanner{position:fixed;z-index:9999;left:50%;top:10px;transform:translateX(-50%);
    max-width:min(760px,calc(100vw - 32px));padding:8px 14px;border:2px solid #b0000b;background:#fff7f7;
    color:#7a0008;box-shadow:0 5px 18px #17202b33;text-align:center;font:800 12px/1.45 "Microsoft YaHei",sans-serif}
  #withdrawnReviewBanner small{display:block;margin-top:2px;color:#4e5961;font-weight:600}
  #fillBookmarks{z-index:12;box-sizing:border-box;display:grid;grid-template-columns:auto repeat(6,minmax(0,1fr));
    align-items:stretch;overflow:hidden;background:#f8fafb;border:1px solid #aeb8bf;color:#1b2831;
    font-family:"Microsoft YaHei",sans-serif;box-shadow:0 3px 10px #17202b12}
  #fillBookmarks .bookTitle{min-width:92px;padding:4px 7px;display:grid;align-content:center;border-right:1px solid #c8d0d5}
  #fillBookmarks .bookTitle b{font-size:8.5px}#fillBookmarks .bookTitle span{margin-top:2px;color:#68747d;font:7px/1 Consolas,monospace}
  #fillBookmarks button{min-width:0;padding:3px 2px;display:grid;align-content:center;border:0;border-right:1px solid #d4dade;
    background:#fff;color:#26343e;cursor:default;font:700 8px/1.05 Consolas,"Microsoft YaHei",monospace}
  #fillBookmarks button:last-child{border-right:0}#fillBookmarks button strong{font-size:9px}#fillBookmarks button small{margin-top:2px;color:#6a757d;font-size:6.5px}
  #fillBookmarks button[data-active="true"]{background:#fff3ad;box-shadow:inset 0 -3px #e7b800;color:#17202b}
  #fillBookmarks button[data-end="true"]{background:#eef3f6}
  #linkedEvidenceChip{display:inline-flex;align-items:center;margin-left:6px;padding:2px 5px;background:#17365d;color:#fff;
    font:700 7px/1 "Microsoft YaHei",sans-serif;white-space:nowrap}
  html[data-incremental-layout="left"] #fillBookmarks{grid-area:fill;height:34px}
  html[data-incremental-layout="left"] #workHud{grid-template-rows:auto 34px auto auto auto auto minmax(66px,1fr);
    grid-template-areas:"head head" "fill fill" "task task" "controls controls" "decision decision" "map insight" "phase insight"}
  html[data-incremental-layout="map"] #slotMapWrap{display:grid;grid-template-columns:minmax(0,1fr) 66px;
    grid-template-rows:auto auto minmax(0,1fr) auto;grid-template-areas:"mapHead mapHead" "mapRule mapRule" "mapCanvas fill" "mapKey mapKey";gap:4px 6px}
  html[data-incremental-layout="map"] #slotMapWrap .mapHead{grid-area:mapHead}
  html[data-incremental-layout="map"] #slotMapWrap .mapRule{grid-area:mapRule;margin-top:0}
  html[data-incremental-layout="map"] #slotMap{grid-area:mapCanvas;width:100%;height:auto!important;margin-top:0;align-self:center}
  html[data-incremental-layout="map"] #slotMapWrap .mapKey{grid-area:mapKey;margin-top:0}
  html[data-incremental-layout="map"] #fillBookmarks{grid-area:fill;height:100%;min-height:0;grid-template-columns:1fr;grid-template-rows:auto repeat(6,minmax(0,1fr));box-shadow:none}
  html[data-incremental-layout="map"] #fillBookmarks .bookTitle{min-width:0;padding:4px;text-align:center;border-right:0;border-bottom:1px solid #c8d0d5}
  html[data-incremental-layout="map"] #fillBookmarks .bookTitle span{display:none}
  html[data-incremental-layout="map"] #fillBookmarks button{border-right:0;border-bottom:1px solid #d4dade;padding:2px 1px}
  html[data-incremental-layout="insight"] #workHud{grid-template-columns:minmax(0,1.08fr) minmax(205px,.92fr)}
  html[data-incremental-layout="insight"] #insightStack{grid-template-rows:auto auto minmax(48px,.72fr) auto auto auto}
  html[data-incremental-layout="insight"] #fillBookmarks{order:-1;height:82px;grid-template-columns:repeat(3,minmax(0,1fr));grid-template-rows:23px repeat(2,1fr);box-shadow:none}
  html[data-incremental-layout="insight"] #fillBookmarks .bookTitle{grid-column:1/4;min-width:0;padding:3px 5px;display:flex;align-items:center;justify-content:space-between;border-right:0;border-bottom:1px solid #c8d0d5}
  html[data-incremental-layout="insight"] #fillBookmarks .bookTitle span{margin:0}
  html[data-incremental-layout="insight"] #fillBookmarks button{font-size:8.5px}
  @media(max-width:1380px), (max-height:780px){
    #fillBookmarks .bookTitle{min-width:80px;padding-left:5px;padding-right:5px}
    #fillBookmarks .bookTitle span,#fillBookmarks button small{display:none}
    html[data-incremental-layout="left"] #fillBookmarks{height:29px}
    html[data-incremental-layout="left"] #workHud{grid-template-rows:auto 29px auto auto auto auto minmax(58px,1fr)}
    html[data-incremental-layout="insight"] #workHud{grid-template-columns:minmax(0,1.08fr) minmax(185px,.92fr)}
    html[data-incremental-layout="insight"] #fillBookmarks{height:68px}
  }
</style>
"""


def review_script(layout: str, source_hash: str, release: dict) -> str:
    names = {
        "left": "方案 1 · 顶部横排书签",
        "map": "方案 2 · 地图侧列书签",
        "insight": "方案 3 · 证据卡组书签",
    }
    counts = ((0, 133), (67, 200), (134, 267), (201, 334), (241, 374), (267, 400))
    buttons = "".join(
        f'<button type="button" aria-disabled="true" data-active="{str(m == 134).lower()}" '
        f'data-end="{str(m in (0, 267)).lower()}"><strong>{m}/267</strong><small>{t}/400</small></button>'
        for m, t in counts
    )
    return f"""
<script id="s3IncrementalReviewScript">
(function(){{
  const layout={json.dumps(layout)}, sourceHash={json.dumps(source_hash)}, release={json.dumps(release, ensure_ascii=False)};
  document.documentElement.dataset.incrementalLayout=layout;
  document.documentElement.dataset.reviewStatus='withdrawn';
  document.title={json.dumps('已撤销 · ' + names[layout], ensure_ascii=False)};
  const withdrawn=document.createElement('div');withdrawn.id='withdrawnReviewBanner';
  withdrawn.innerHTML='已撤销评审资格：此版保留了重复作业信息，且容量书签尚未与货位图 / 三维状态接线。<small>仅作失败证据，不得作为视觉方案或正式实现基线。</small>';
  document.body.append(withdrawn);
  const head=document.getElementById('railHead');
  const mark=document.createElement('div');mark.id='incrementalReviewMark';
  mark.innerHTML=`<b>${{{json.dumps(names[layout])}}}</b><span>母版 ${{sourceHash.slice(0,8)}} · fill ${{release.release_id.slice(0,8)}} · loader 未接线</span>`;
  head.append(mark);
  const bookmarks=document.createElement('nav');bookmarks.id='fillBookmarks';bookmarks.setAttribute('aria-label','容量稳定书签结构预览');
  bookmarks.innerHTML='<div class="bookTitle"><b>容量书签 B</b><span>结构预览 · 不触发跳转</span></div>'+{json.dumps(buttons, ensure_ascii=False)};
  if(layout==='left'){{document.getElementById('workHud').insertBefore(bookmarks,document.getElementById('taskline'));}}
  else if(layout==='map'){{document.getElementById('slotMapWrap').append(bookmarks);}}
  else{{document.getElementById('insightStack').prepend(bookmarks);}}
  const mapHead=document.querySelector('#slotMapWrap .mapHead>div');
  if(mapHead){{const chip=document.createElement('span');chip.id='linkedEvidenceChip';chip.textContent='D · 2D↔3D 同目标';mapHead.append(chip);}}
  requestAnimationFrame(()=>{{window.dispatchEvent(new Event('resize'));}});
}})();
</script>
"""


def build() -> dict:
    source_bytes = SOURCE.read_bytes()
    source_hash = hashlib.sha256(source_bytes).hexdigest()
    source = source_bytes.decode("utf-8")
    release = gate_release()
    if source.count("</head>") != 1 or source.count("</body>") != 1:
        raise RuntimeError("mother HTML must contain exactly one head/body terminator")
    records = []
    for layout, output in OUTPUTS.items():
        injected_script = review_script(layout, source_hash, release)
        generated = source.replace("</head>", COMMON_CSS + "\n</head>", 1)
        generated = generated.replace(
            "</body>", injected_script + "\n</body>", 1
        )
        recovered = generated.replace(COMMON_CSS + "\n", "", 1).replace(
            injected_script + "\n", "", 1
        )
        if recovered != source:
            raise RuntimeError(f"mother recovery mismatch for layout {layout}")
        output.write_text(generated, encoding="utf-8")
        records.append({
            "layout": layout,
            "path": str(output.relative_to(ROOT)).replace("\\", "/"),
            "file_sha256": sha256(output),
            "source_recovery_verified": True,
        })
    result = {
        "schema_version": "s3-incremental-design-review-v2",
        "review_status": "WITHDRAWN_FAIL_EVIDENCE_ONLY",
        "withdrawal_reasons": [
            "duplicate task summary remained in the mother layout",
            "fill bookmarks were not bound to the active 2D/3D state",
            "previous QA checked presence and overflow but not semantic equivalence",
        ],
        "source": str(SOURCE.relative_to(ROOT)).replace("\\", "/"),
        "source_sha256": source_hash,
        "preservation_contract": (
            "generated files contain the complete mother HTML plus one review CSS block and one review script; "
            "no 3D geometry, camera, light, motion, trace, store, or runtime source is replaced"
        ),
        "fill_release": release,
        "outputs": records,
    }
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return result


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=True, sort_keys=True, indent=2))
