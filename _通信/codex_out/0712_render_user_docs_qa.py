# -*- coding: utf-8 -*-
"""Rasterize three WPS-exported user PDFs and build 2x2 contact sheets."""
from pathlib import Path
import sys

import fitz
from PIL import Image, ImageDraw

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent / "user_docs_wps_qa_0712"
for pdf in sorted(ROOT.glob("*.pdf")):
    out = ROOT / pdf.stem
    out.mkdir(exist_ok=True)
    doc = fitz.open(pdf)
    pages = []
    for index, page in enumerate(doc):
        pix = page.get_pixmap(matrix=fitz.Matrix(1.35, 1.35), alpha=False)
        path = out / f"page-{index + 1:02d}.png"
        pix.save(path)
        pages.append(path)
    tw, th = 760, 1000
    for start in range(0, len(pages), 4):
        sheet = Image.new("RGB", (tw * 2 + 60, th * 2 + 100), "#d9dde3")
        draw = ImageDraw.Draw(sheet)
        for offset, path in enumerate(pages[start:start + 4]):
            im = Image.open(path).convert("RGB")
            im.thumbnail((tw - 30, th - 50))
            x = 20 + (offset % 2) * (tw + 20)
            y = 45 + (offset // 2) * (th + 20)
            sheet.paste(im, (x + (tw - im.width) // 2, y))
            draw.text((x, 15 + (offset // 2) * (th + 20)), f"Page {start + offset + 1}", fill="black")
        sheet.save(out / f"montage-{start + 1:02d}-{min(start + 4, len(pages)):02d}.png")
    print(f"{pdf.stem}\tPAGES={len(pages)}\tMONTAGES={len(list(out.glob('montage-*.png')))}")
