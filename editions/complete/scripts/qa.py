#!/usr/bin/env python3
"""Every page to PNG (trimmed to the trim box), a contact sheet laid out as reader spreads, and
spread PNGs on request.

  python3 scripts/qa.py <pdf> [dpi] [left pages of spreads, comma-separated]
"""
import glob, os, subprocess, sys
from PIL import Image, ImageDraw
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); Q = f"{R}/qa"
pdf = sys.argv[1]; dpi = int(sys.argv[2]) if len(sys.argv) > 2 else 100
spreads = [int(x) for x in sys.argv[3].split(",")] if len(sys.argv) > 3 and sys.argv[3] else []
out = f"{Q}/pages"; os.makedirs(out, exist_ok=True)
for f in glob.glob(f"{out}/p-*.png"): os.remove(f)
subprocess.run(["pdftoppm", "-r", str(dpi), "-png", "-cropbox", pdf, f"{out}/p"], check=True)
fs = sorted(glob.glob(f"{out}/p-*.png"), key=lambda f: int(f.rsplit("-", 1)[1][:-4]))
ims = [Image.open(f).convert("RGB") for f in fs]
b = round(9 / 72 * dpi)
if ims[0].width > 8.6 * dpi:      # press file: trim the bleed for viewing
    ims = [im.crop((b, b, im.width - b, im.height - b)) for im in ims]
    for f, im in zip(fs, ims): im.save(f)
w, h = ims[0].size; t = 0.26; tw, th = int(w * t), int(h * t)
rows = [[None, ims[0]]] + [[ims[k], ims[k + 1] if k + 1 < len(ims) else None] for k in range(1, len(ims), 2)]
per = 5; lines = (len(rows) + per - 1) // per; pad = 12
S = Image.new("RGB", (per * (2 * tw + pad) + pad, lines * (th + pad + 14) + pad), "#d6d2ca"); d = ImageDraw.Draw(S)
for k, r in enumerate(rows):
    x0 = pad + (k % per) * (2 * tw + pad); y0 = pad + (k // per) * (th + pad + 14)
    for j, im in enumerate(r):
        if im is None: continue
        S.paste(im.resize((tw, th), Image.LANCZOS), (x0 + j * tw, y0))
        d.text((x0 + j * tw + 3, y0 + th + 2), str(1 if k == 0 else 2 * k + j), fill="#333")
S.save(f"{Q}/contact-sheet.png")
# tiles of 8 pages (4 spreads) at a readable size, for page-by-page reading
os.makedirs(f"{Q}/sheets", exist_ok=True)
for f in glob.glob(f"{Q}/sheets/*.png"): os.remove(f)
sw, sh = int(w * 0.5), int(h * 0.5)
for s in range(0, len(rows), 2):
    grp = rows[s:s + 2]; T = Image.new("RGB", (2 * sw + 2 * 14, len(grp) * (sh + 24) + 10), "#d6d2ca"); dd = ImageDraw.Draw(T)
    for k, r in enumerate(grp):
        for j, im in enumerate(r):
            if im is None: continue
            T.paste(im.resize((sw, sh), Image.LANCZOS), (10 + j * sw, 10 + k * (sh + 24)))
            n = 1 if s + k == 0 else 2 * (s + k) + j
            dd.text((12 + j * sw, 12 + k * (sh + 24) + sh), f"p{n}", fill="#222")
    T.save(f"{Q}/sheets/s{s // 2 + 1:03d}.png")
for n in spreads:
    pair = [ims[0]] if n == 1 else [ims[n - 1], ims[n]] if n < len(ims) else [ims[n - 1]]
    sp = Image.new("RGB", (w * len(pair) + (8 if len(pair) == 2 else 0), h), "#d6d2ca")
    for j, im in enumerate(pair): sp.paste(im, (j * (w + 8), 0))
    sp.save(f"{Q}/spread-{n:03d}.png")
print(len(ims), "pages;", len(glob.glob(f"{Q}/sheets/*.png")), "sheets")
