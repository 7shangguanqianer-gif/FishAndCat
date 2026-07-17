# -*- coding: utf-8 -*-
"""Rasterize the WPS-exported report PDF and build 2x2 contact sheets for visual QA."""
from pathlib import Path
import sys

import fitz
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
PDF = ROOT / "0712_验证报告_WPS_QA.pdf"
OUT = ROOT / "report_wps_qa_0712"
OUT.mkdir(exist_ok=True)

doc = fitz.open(PDF)
pages = []
for index, page in enumerate(doc):
    pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
    path = OUT / f"page-{index + 1:02d}.png"
    pix.save(path)
    pages.append(path)

thumb_w, thumb_h = 850, 1100
for group_start in range(0, len(pages), 4):
    sheet = Image.new("RGB", (thumb_w * 2 + 60, thumb_h * 2 + 100), "#d9dde3")
    draw = ImageDraw.Draw(sheet)
    for offset, path in enumerate(pages[group_start:group_start + 4]):
        im = Image.open(path).convert("RGB")
        im.thumbnail((thumb_w - 30, thumb_h - 50))
        x = 20 + (offset % 2) * (thumb_w + 20)
        y = 45 + (offset // 2) * (thumb_h + 20)
        sheet.paste(im, (x + (thumb_w - im.width) // 2, y))
        draw.text((x, 15 + (offset // 2) * (thumb_h + 20)), f"Page {group_start + offset + 1}", fill="black")
    out = OUT / f"montage-{group_start + 1:02d}-{min(group_start + 4, len(pages)):02d}.png"
    sheet.save(out)

print(f"PAGES={len(pages)}")
for p in sorted(OUT.glob("montage-*.png")):
    print(p)
