#!/usr/bin/env python3
"""Print build/issue.html to press PDFs, render every page to PNG, and run the checks.

  python3 scripts/press.py            # PDFs + PNGs + checks
  python3 scripts/press.py --png      # PNGs + checks only (faster while iterating)

Mixam: each page is 8.75 x 11.25 in (8.5 x 11 trim + 0.125 in bleed a side) with BleedBox = MediaBox
and TrimBox inset 9 pt. <= 96 pages -> one saddle-stitch PDF, cover = page 1. > 96 -> PUR interior
+ a cover spread whose spine is spineCalc() from substack-magazine/public/app.js.
FedEx: letter pages without bleed (cropped to trim), the cover's ground inside a 0.25 in border, as the tool does.
"""
import os, sys, json, math, subprocess, shutil
from playwright.sync_api import sync_playwright
from pypdf import PdfReader, PdfWriter
from pypdf.generic import RectangleObject
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRESS, QA = f"{ROOT}/press", f"{ROOT}/qa"
os.makedirs(PRESS, exist_ok=True); os.makedirs(f"{QA}/pages", exist_ok=True)
PNG_ONLY = "--png" in sys.argv
SCRATCH = "/private/tmp/claude-501/-Users-aidan-Desktop-bricks/1dde7bd3-42bf-4979-acd1-3878cc216e75/scratchpad/editions-2025"

CHECKS = r"""() => {
  const out = {overflow: [], widow: [], headfoot: [], imgs: [], pages: window.__pages, layout: window.__layout};
  const LIVE_B = 984, SAFE = 12;
  for (const s of document.querySelectorAll('.sheet')) {
    const pn = +s.dataset.page, trim = s.querySelector('.trim'), tr = trim.getBoundingClientRect();
    const its = [...trim.querySelectorAll('.it')];
    for (const e of its) {
      const r = e.getBoundingClientRect(), x0 = r.left - tr.left, y0 = r.top - tr.top, x1 = r.right - tr.left, y1 = r.bottom - tr.top;
      if (e.classList.contains('cov')) { if (e.scrollWidth > e.clientWidth + 1) out.overflow.push([pn, 'cover text wider than sheet']); continue; }
      if (x0 < SAFE - .5 || y0 < SAFE - .5 || x1 > 816 - SAFE + .5 || y1 > 1056 - SAFE + .5) out.overflow.push([pn, e.className, 'outside safe area', Math.round(x0), Math.round(y0), Math.round(x1), Math.round(y1)]);
      const body = !e.classList.contains('fo') && !e.classList.contains('cr');
      if (body && e.tagName !== 'svg' && y1 > LIVE_B + 1.5) out.overflow.push([pn, e.className, 'below the text area', Math.round(y1), (e.textContent || '').slice(0, 40)]);
      if (e.scrollHeight > e.clientHeight + 1 && e.tagName === 'DIV') out.overflow.push([pn, e.className, 'clipped']);
      if (e.dataset && (e.dataset.split === '1' || e.dataset.cont === '1')) {
        const lh = parseFloat(getComputedStyle(e).lineHeight), n = Math.round(r.height / lh);
        if (n < 2) out.widow.push([pn, n, (e.textContent || '').slice(0, 50)]);
      }
      if (e.tagName === 'IMG') {
        const pw = +e.dataset.pw, w = r.width / 96, ppi = pw / w;
        out.imgs.push([pn, e.dataset.key, Math.round(ppi), +(r.width / 96).toFixed(2)]);
      }
    }
    // a rail heading must have something beside or under it on its own page
    for (const h of trim.querySelectorAll('.sec,.date')) {
      const hy = h.getBoundingClientRect().top;
      const after = its.some(e => e !== h && !e.classList.contains('sec') && !e.classList.contains('date') && !e.classList.contains('rule') && !e.classList.contains('fo') && e.getBoundingClientRect().bottom > hy + 20 && e.getBoundingClientRect().left - tr.left >= 290);
      if (!after) out.headfoot.push([pn, h.textContent]);
    }
    for (const h of trim.querySelectorAll('.h4')) {
      const hb = h.getBoundingClientRect().bottom - tr.top;
      if (hb > LIVE_B - 40) out.headfoot.push([pn, 'h4 at foot', h.textContent]);
    }
  }
  return out;
}"""

def render(fedex=False):
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 900, "height": 1200}, device_scale_factor=1)
        msgs = []; pg.on("console", lambda m: msgs.append(m.text))
        pg.goto("file://" + f"{ROOT}/build/issue.html")
        pg.wait_for_function("window.__done === true", timeout=600000)
        pg.wait_for_timeout(500)
        pg.evaluate("Promise.all([...document.images].map(i => i.complete ? 0 : new Promise(r => i.onload = i.onerror = r)))")
        res = {"log": msgs}
        if not fedex:
            res["checks"] = pg.evaluate(CHECKS)
            # every page to PNG
            shutil.rmtree(f"{QA}/pages", ignore_errors=True); os.makedirs(f"{QA}/pages")
            rects = pg.evaluate("[...document.querySelectorAll('.sheet')].map(s => { const r = s.getBoundingClientRect(); return [r.left + scrollX, r.top + scrollY]; })")
            for i, (x, y) in enumerate(rects, 1):
                pg.screenshot(path=f"{QA}/pages/p{i:03d}.png", clip={"x": x, "y": y, "width": 840, "height": 1080}, full_page=True, animations="disabled")
            res["n"] = len(rects)
        else:
            pg.add_style_tag(content=".sheet.ground{box-shadow:inset 0 0 0 36px #fff}")
        if not PNG_ONLY:
            pg.emulate_media(media="print")
            path = f"{PRESS}/_raw{'_fedex' if fedex else ''}.pdf"
            pg.pdf(path=path, width="840px", height="1080px", print_background=True, margin={"top": "0", "bottom": "0", "left": "0", "right": "0"}, prefer_css_page_size=True)
            res["pdf"] = path
        b.close()
        return res

def boxes(src, dst, trim_only=False):
    r = PdfReader(src); w = PdfWriter()
    for pgo in r.pages:
        H = float(pgo.mediabox.top)
        bleed = RectangleObject([0, H - 810, 630, H]); trim = RectangleObject([9, H - 801, 621, H - 9])
        if trim_only:
            pgo.mediabox = trim; pgo.cropbox = trim; pgo.trimbox = trim; pgo.bleedbox = trim
        else:
            pgo.mediabox = bleed; pgo.cropbox = bleed; pgo.bleedbox = bleed; pgo.trimbox = trim
        w.add_page(pgo)
    with open(dst, "wb") as fh: w.write(fh)
    os.remove(src)

def contact_sheet(n):
    # spreads as they fall in the bound book: 1 alone, then (2,3), (4,5) ... , last alone
    pages = [Image.open(f"{QA}/pages/p{i:03d}.png").convert("RGB") for i in range(1, n + 1)]
    tw, th = 280, 360
    spreads = [[0]] + [[i, i + 1] for i in range(1, n - 1, 2)] + [[n - 1]]
    cols = 4; rows = math.ceil(len(spreads) / cols)
    sheet = Image.new("RGB", (cols * (2 * tw + 40) + 40, rows * (th + 40) + 40), (205, 205, 205))
    for k, sp in enumerate(spreads):
        x0 = 40 + (k % cols) * (2 * tw + 40); y0 = 40 + (k // cols) * (th + 40)
        for j, idx in enumerate(sp):
            im = pages[idx].crop((12, 12, 828, 1068)).resize((tw, th), Image.LANCZOS)
            x = x0 + (tw if (len(sp) == 1 and idx == 0) else (0 if len(sp) == 1 else j * tw))
            sheet.paste(im, (x, y0))
    sheet.save(f"{QA}/contact-sheet.png")
    return spreads

def spread_png(a, b_, name):
    ims = [Image.open(f"{QA}/pages/p{i:03d}.png").convert("RGB").crop((12, 12, 828, 1068)) for i in ([a] if b_ is None else [a, b_])]
    W = sum(i.width for i in ims); s = Image.new("RGB", (W, ims[0].height), "white"); x = 0
    for i in ims: s.paste(i, (x, 0)); x += i.width
    s.save(f"{QA}/{name}.png")

if __name__ == "__main__":
    res = render()
    for m in res["log"]: print("  js:", m)
    c = res["checks"]; n = res["n"]
    print(f"{n} pages (multiple of 4: {n % 4 == 0})")
    print("overflow:", c["overflow"] or "none")
    print("widows/orphans (<2 lines):", c["widow"] or "none")
    print("headings at foot:", c["headfoot"] or "none")
    keys = [k for _, k, _, _ in c["imgs"]]
    corpus = json.load(open(f"{ROOT}/src/corpus.json"))
    want = []
    def walk(bs):
        for b in bs:
            if b["type"] == "img": want.append(os.path.splitext(b["file"])[0])
            if "blocks" in b: walk(b["blocks"])
    for p in corpus: walk(p["blocks"])
    dup = sorted({k for k in keys if keys.count(k) > 1}); miss = sorted(set(want) - set(keys))
    print(f"images: {len(keys)} placed of {len(want)} in the posts; duplicates: {dup or 'none'}; missing: {miss or 'none'}")
    low = [x for x in c["imgs"] if x[2] < 200]
    print("images under 200 ppi:", low or "none")
    json.dump(c, open(f"{QA}/checks.json", "w"), indent=1)
    contact_sheet(n)
    # representative spreads: the cover, the contents facing the first opener, a diary spread,
    # images with text, and the last spread of the year
    for a, b_, name in ((1, None, "spread-cover"), (2, 3, "spread-contents-opener"), (10, 11, "spread-opener-south-africa"),
                        (12, 13, "spread-diary"), (38, 39, "spread-images-film"), (44, 45, "spread-images-portraits"), (52, 53, "spread-train-dreams")):
        spread_png(a, b_, name)
    os.makedirs(SCRATCH, exist_ok=True)
    for f in os.listdir(QA):
        if f.endswith(".png"): shutil.copy(f"{QA}/{f}", SCRATCH)
    if not PNG_ONLY:
        if n <= 96:
            boxes(res["pdf"], f"{PRESS}/AIDAN-JUDE-2025-MIXAM-SADDLE.pdf")
        else:
            raise SystemExit("over 96 pages: write the PUR path")
        rf = render(fedex=True); boxes(rf["pdf"], f"{PRESS}/AIDAN-JUDE-2025-FEDEX-LETTER.pdf", trim_only=True)
        for f in sorted(os.listdir(PRESS)):
            if f.endswith(".pdf"):
                r = PdfReader(f"{PRESS}/{f}"); p0 = r.pages[0]
                print(f, len(r.pages), "pages, media", [round(float(v), 1) for v in p0.mediabox], "trim", [round(float(v), 1) for v in p0.trimbox], f"{os.path.getsize(f'{PRESS}/{f}') / 1e6:.1f} MB")
        out = subprocess.run(["pdffonts", f"{PRESS}/AIDAN-JUDE-2025-MIXAM-SADDLE.pdf"], capture_output=True, text=True).stdout
        print(out)
