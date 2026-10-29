#!/usr/bin/env python3
"""Print issue.html to the press PDFs, render every page to PNG, and run the QA checks.

  python3 extract.py && python3 build.py && python3 render.py

press/AIDAN-JUDE-2024-MIXAM.pdf   saddle stitch, 8.75x11.25in pages, TrimBox 0.125in inset
press/AIDAN-JUDE-2024-FEDEX.pdf   same pages cropped to Letter trim, no bleed
qa/pNN.png, qa/contact.png, qa/spread-*.png
"""
import json, os, shutil, subprocess, sys
from playwright.sync_api import sync_playwright
from pypdf import PdfReader, PdfWriter
from pypdf.generic import RectangleObject
from PIL import Image, ImageDraw

D = os.path.dirname(os.path.abspath(__file__))
PRESS, QA = f"{D}/press", f"{D}/qa"
MIX, FDX = f"{PRESS}/AIDAN-JUDE-2024-MIXAM.pdf", f"{PRESS}/AIDAN-JUDE-2024-FEDEX.pdf"
SCRATCH = "/private/tmp/claude-501/-Users-aidan-Desktop-bricks/1dde7bd3-42bf-4979-acd1-3878cc216e75/scratchpad/editions-2024"

QA_JS = r"""() => {
  const out = {overflow: [], safe: [], imgs: [], ppi: []};
  const pgs = [...document.querySelectorAll('#book > .pg')];
  pgs.forEach((pg, i) => {
    const tr = pg.querySelector('.trim').getBoundingClientRect();
    // text outside the 0.25in safe area of the trim (folios sit at 0.4in from the foot)
    const walker = document.createTreeWalker(pg, NodeFilter.SHOW_TEXT);
    let n; while ((n = walker.nextNode())) {
      if (!n.textContent.trim()) continue;
      const r = document.createRange(); r.selectNodeContents(n);
      for (const q of r.getClientRects()) {
        // clipped continuation text inside a column is invisible: test against the column box
        const col = n.parentElement.closest('.col');
        if (col) { const c = col.getBoundingClientRect(); if (q.bottom <= c.top + 1 || q.top >= c.bottom - 1) continue; }
        if (q.left < tr.left + 24 || q.right > tr.right - 24 || q.top < tr.top + 24 || q.bottom > tr.bottom - 24)
          out.safe.push([i + 1, n.textContent.trim().slice(0, 40)]);
      }
    }
    pg.querySelectorAll('.col').forEach((c) => { if (c.scrollWidth > c.clientWidth + 1) out.overflow.push([i + 1, 'col wide']); });
    pg.querySelectorAll('img').forEach((im) => {
      const r = im.getBoundingClientRect();
      const col = im.closest('.col');
      if (col) { const c = col.getBoundingClientRect(); if (r.bottom <= c.top + 1 || r.top >= c.bottom - 1) return; }
      out.imgs.push([i + 1, im.getAttribute('src')]);
      out.ppi.push([i + 1, im.getAttribute('src'), Math.round(im.naturalWidth / (r.width / 96))]);
    });
  });
  return out;
}"""


def main():
    os.makedirs(PRESS, exist_ok=True)
    shutil.rmtree(QA, ignore_errors=True); os.makedirs(QA)
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 900, "height": 1200})
        pg.on("console", lambda m: print("console:", m.text) if m.type in ("error", "warning") else None)
        pg.on("pageerror", lambda e: print("PAGEERROR", e))
        pg.emulate_media(media="print")   # lay out under print metrics, or lines break differently in the PDF
        pg.goto("file://" + f"{D}/issue.html")
        pg.wait_for_selector("body[data-ready='1']", timeout=120000)
        rep = pg.evaluate("window.REPORT")
        qa = pg.evaluate(QA_JS)
        pg.emulate_media(media="print")
        pg.pdf(path=MIX, width="8.75in", height="11.25in", print_background=True, margin={"top": "0", "bottom": "0", "left": "0", "right": "0"}, prefer_css_page_size=True)
        b.close()
    json.dump({"report": rep, "qa": qa}, open(f"{QA}/report.json", "w"), indent=1)
    r = PdfReader(MIX)
    assert len(r.pages) == rep["pages"], (len(r.pages), rep["pages"])
    for W, out, trim_only in ((None, MIX, False), (None, FDX, True)):
        w = PdfWriter()
        for pgo in PdfReader(MIX).pages:
            top = float(pgo.mediabox.top)
            bleed = RectangleObject([0, top - 810, 630, top]); trim = RectangleObject([9, top - 801, 621, top - 9])
            if trim_only:
                pgo.mediabox = trim; pgo.cropbox = trim; pgo.bleedbox = trim; pgo.trimbox = trim
            else:
                pgo.mediabox = bleed; pgo.cropbox = bleed; pgo.bleedbox = bleed; pgo.trimbox = trim
            w.add_page(pgo)
        w.add_metadata({"/Title": "Aidan Jude — Selected writing 2024", "/Author": "Aidan Jude"})
        with open(out + ".tmp", "wb") as fh: w.write(fh)
        os.replace(out + ".tmp", out)
    # PNG of every page (trim + bleed), contact sheet, spreads
    subprocess.run(["pdftoppm", "-r", "60", "-png", MIX, f"{QA}/p"], check=True)
    pngs = sorted(f for f in os.listdir(QA) if f.startswith("p") and f.endswith(".png"))
    ims = [Image.open(f"{QA}/{f}") for f in pngs]
    tw, th = ims[0].size; cols = 8; rows = (len(ims) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * (tw + 12) + 12, rows * (th + 28) + 12), "#8a8784"); d = ImageDraw.Draw(sheet)
    for i, im in enumerate(ims):
        x = 12 + (i % cols) * (tw + 12); y = 12 + (i // cols) * (th + 28)
        sheet.paste(im, (x, y)); d.text((x, y + th + 4), str(i + 1), fill="white")
    sheet.save(f"{QA}/contact.png")
    n = len(pngs)
    def spread(a, name):  # a = 1-based left page; 0 means cover alone
        subprocess.run(["pdftoppm", "-r", "110", "-png", "-f", str(max(a, 1)), "-l", str(min(a + 1, n) if a else 1), MIX, f"{QA}/_s"], check=True)
        fs = sorted(f for f in os.listdir(QA) if f.startswith("_s"))
        parts = [Image.open(f"{QA}/{f}") for f in fs]
        S = Image.new("RGB", (sum(p.size[0] for p in parts), parts[0].size[1]), "white"); x = 0
        for p_ in parts: S.paste(p_, (x, 0)); x += p_.size[0]
        S.save(f"{QA}/spread-{name}.png")
        for f in fs: os.remove(f"{QA}/{f}")
    kinds = rep["kinds"]
    spread(0, "cover")
    spread(2, "contents")
    op = [i + 1 for i, k in enumerate(kinds) if "opener" in k]
    for j, o in enumerate(op):
        spread(o if o % 2 == 0 else o - 1, f"opener-{j + 1:02d}")
    pic = next(pn for pn, src, _ in qa["ppi"] if "may-24-02" in src)
    spread(pic if pic % 2 == 0 else pic - 1, "image")
    lit = next(i + 1 for i, k in enumerate(kinds) if k == "lit")
    spread(lit if lit % 2 == 0 else lit - 1, "literature")
    # fonts
    fonts = subprocess.run(["pdffonts", MIX], capture_output=True, text=True).stdout
    os.makedirs(SCRATCH, exist_ok=True)
    for f in os.listdir(QA):
        if f.startswith(("contact", "spread")): shutil.copy(f"{QA}/{f}", SCRATCH)
    # ---- verdicts
    srcs = [s for _, s in qa["imgs"]]
    content = json.load(open(f"{D}/content.json"))
    want = [b["file"] for p in content for b in [p["art"]] + p["body"] + ([p["lit"]["art"]] if p["lit"]["art"] else []) + p["lit"]["blocks"] if b.get("t") == "img" or b is p["art"]]
    print("pages", rep["pages"], "multiple of 4:", rep["pages"] % 4 == 0)
    for m in rep["months"]: print(" ", m)
    print("log", rep["log"])
    print("overflow", qa["overflow"]); print("outside safe area", qa["safe"][:20], len(qa["safe"]))
    dup = sorted({s for s in srcs if srcs.count(s) > 1}); miss = sorted(set(want) - set(srcs))
    print("duplicate images", dup); print("missing images", miss)
    print("under 200 ppi", [x for x in qa["ppi"] if x[2] < 200])
    emb = [l for l in fonts.splitlines()[2:]]
    print("fonts", len(emb), "all embedded:", all(" yes " in l for l in emb)); print(fonts)


if __name__ == "__main__":
    main()
