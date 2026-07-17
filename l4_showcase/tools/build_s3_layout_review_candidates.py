#!/usr/bin/env python3
"""Build three layout-only reviews from the recovered S3 fill candidate.

All variants preserve the same verified store, runtime and Three.js scene.
They differ only in rail width and the relative emphasis of map/process evidence.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "l4_showcase" / "src" / "archive_候选历史" / "样张_S3_fill恢复候选.html"
OUTDIR = ROOT / "l4_showcase" / "src"
REVIEWDIR = ROOT / "l4_showcase" / "design_reviews" / "0716_S3_恢复版式"
MANIFEST = REVIEWDIR / "manifest.json"


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


VARIANTS = {
    "1_均衡双栏": {
        "summary": "2D 容量图与七步说明并列；信息密度和三维面积最均衡。",
        "css": """
html[data-layout="balanced"]{--rail-w:clamp(500px,32.5vw,624px)}
html[data-layout="balanced"] #workHud{grid-template-columns:minmax(0,1.24fr) minmax(160px,.76fr)}
html[data-layout="balanced"] #processGuideRows{gap:3px}
""",
    },
    "2_地图主证": {
        "summary": "放大 20×20 同源地图；七步说明压缩，适合强调 0→267 填满证据。",
        "css": """
html[data-layout="map-first"]{--rail-w:clamp(540px,38vw,660px)}
html[data-layout="map-first"] #workHud{grid-template-columns:minmax(0,1fr);grid-template-rows:auto auto auto auto minmax(0,1fr) auto;
  grid-template-areas:"head" "controls" "decision" "bookmark" "map" "phase"}
html[data-layout="map-first"] #insightStack{display:none}
html[data-layout="map-first"] #slotMapWrap{grid-column:1;align-self:stretch;min-height:0;height:100%;max-height:100%;box-sizing:border-box;
  display:grid;grid-template-rows:auto auto minmax(0,1fr) auto;overflow:hidden}
html[data-layout="map-first"] #slotMap{width:auto!important;height:100%!important;min-height:0;max-width:100%;max-height:100%;
  aspect-ratio:1/1;justify-self:center;align-self:center}
html[data-layout="map-first"] #phaseRail{grid-column:1}
@media(max-width:1380px){
  html[data-layout="map-first"]{--rail-w:clamp(500px,41vw,560px)}
}
""",
    },
    "3_流程主证": {
        "summary": "扩大七步目的与当前高亮；地图仍完整，适合评委理解动作链。",
        "css": """
html[data-layout="process-first"]{--rail-w:clamp(560px,37vw,640px)}
html[data-layout="process-first"] #workHud{grid-template-columns:minmax(250px,.94fr) minmax(270px,1.06fr)}
html[data-layout="process-first"] #insightStack{display:block;overflow:hidden}
html[data-layout="process-first"] #insightStack>:not(#processGuide){display:none}
html[data-layout="process-first"] #processGuide{display:flex;height:100%;padding:8px 9px;flex-direction:column}
html[data-layout="process-first"] #processGuideRows{flex:1;grid-template-rows:repeat(7,minmax(0,1fr));gap:5px}
html[data-layout="process-first"] .processGuideRow{padding:6px 7px}
html[data-layout="process-first"] .processGuideRow span{font-size:8px;white-space:normal}
@media(max-width:1380px){
  html[data-layout="process-first"]{--rail-w:clamp(520px,42vw,570px)}
  html[data-layout="process-first"] #workHud{grid-template-columns:minmax(220px,.95fr) minmax(240px,1.05fr)}
  html[data-layout="process-first"] .processGuideRow{padding:4px 5px}
  html[data-layout="process-first"] .processGuideRow span{display:none}
}
@media(max-height:780px){html[data-layout="process-first"] #processGuide{display:flex}}
""",
    },
}


def build() -> dict:
    source_bytes = SOURCE.read_bytes()
    source_text = source_bytes.decode("utf-8").replace("\r\n", "\n")
    OUTDIR.mkdir(parents=True, exist_ok=True)
    REVIEWDIR.mkdir(parents=True, exist_ok=True)
    outputs = []
    layout_ids = {
        "1_均衡双栏": "balanced",
        "2_地图主证": "map-first",
        "3_流程主证": "process-first",
    }
    for key, spec in VARIANTS.items():
        layout_id = layout_ids[key]
        text = replace_once(
            source_text,
            "document.documentElement.dataset.s3Mode='fill-only-candidate';",
            "document.documentElement.dataset.s3Mode='fill-only-candidate';\n"
            f"document.documentElement.dataset.layout='{layout_id}';",
            f"{key} layout marker",
        )
        css = (
            "\n/* 0716 layout-only review; store/runtime/Three.js scene are identical. */\n"
            + spec["css"].strip()
            + "\n"
        )
        text = replace_once(text, "</style>", css + "</style>", f"{key} review css")
        text = replace_once(
            text,
            "智储优控 · S3 连续填满恢复候选",
            f"智储优控 · S3 版式候选 {key}",
            f"{key} title",
        )
        output = OUTDIR / f"样张_S3_版式候选_{key}.html"
        payload = text.encode("utf-8")
        output.write_bytes(payload)
        outputs.append(
            {
                "id": key,
                "layout": layout_id,
                "summary": spec["summary"],
                "file": output.relative_to(ROOT).as_posix(),
                "sha256": sha256(payload),
            }
        )
    manifest = {
        "schema_version": "s3-fill-layout-review-v1",
        "status": "REVIEW_ONLY_FORMAL_FROZEN",
        "source": SOURCE.relative_to(ROOT).as_posix(),
        "source_sha256": sha256(source_bytes),
        "invariants": [
            "same s3_fill_store.js",
            "same s3_fill_candidate_runtime.js",
            "same mature Three.js scene and camera",
            "same current semantic QA contract; assertion count is read from each qa_report.json",
            "layout-only CSS differences",
        ],
        "outputs": outputs,
        "formal_page_untouched": "l4_showcase/src/样张_S3定稿.html",
        "note": "HTML 必须位于 src，才能复用母版的相对资源路径；design_reviews 中同名旧文件仅为失败证据。",
    }
    MANIFEST.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=True, indent=2))
