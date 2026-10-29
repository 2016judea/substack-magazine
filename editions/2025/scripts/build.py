#!/usr/bin/env python3
"""Aidan Jude, Selected writing 2025: build the issue as one HTML file that paginates itself.

  python3 scripts/extract.py   # freeze the 12 Periodicals posts of 2025 -> src/corpus.json, src/img/
  python3 scripts/build.py     # -> build/issue.html (+ build/img/, print-ready JPEGs)
  python3 scripts/press.py     # -> press/*.pdf, qa/*.png, and the programmatic checks

The design ("the fragment"): a 12-column grid on US Letter. His words are set in Instrument Sans,
ragged right, in an 8-column measure; section heads hang in a 3-column rail to the left, under a
hairline that marks each fragment. Lines set off as quotation (his blockquotes, pullquotes and
preformatted verse) are the only serif, Instrument Serif. Dates, folios, numbers and credits are
IBM Plex Mono. White is the material: every piece opens on a page of its own that holds only its
title, its date, and the image he led with.

Text is verbatim from the post HTML. The only things not carried over are Substack furniture:
the Share/Subscribe buttons and the two lines that introduce them (January), and empty paragraphs.
"""
import json, os, re, html
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC, OUT = f"{ROOT}/src", f"{ROOT}/build"
os.makedirs(f"{OUT}/img", exist_ok=True)

# --- credits -------------------------------------------------------------------------------
# A paragraph he wrote directly under an image as its credit becomes the credit (his words, set
# as a credit). Otherwise the credit is the image's alt text (Substack keeps the source page
# title there), shortened to the source itself, or the work when it is certain. No "via".
CREDIT_FROM_NEXT_P = {"january-25-01", "february-25-01", "south-africa-01", "april-25-01",
                      "june-25-01", "august-25-01", "september-25-01"}
CREDIT = {
    "september-25-02": "Jean Baudrillard, Simulacra and Simulation",   # alt: the Amazon page title
    "oct-25-04": "St. Peter's - The Dome",                              # alt, verbatim
    "oct-25-02": "BankingStrategist.com", "oct-25-03": "BankingStrategist.com",  # printed on the chart
    "april-25-02": "Jean-Pierre Luminet",
    "february-25-02": "The Brutalist", "february-25-03": "The Brutalist",
    "dec-25-pt2-01": "Train Dreams", "dec-25-pt2-03": "Train Dreams", "dec-25-pt2-04": "Train Dreams",
    "dec-25-pt2-05": "Train Dreams", "dec-25-pt2-06": "Train Dreams",
    "dec-25-03": "Yousuf Karsh", "dec-25-04": "Joseph Oriel Eaton",
}
FURNITURE = {"Thanks for reading my Substack. Feel free to:", "Or subscribe (don’t pledge me any money lol):"}
ATTR = re.compile(r"^\s*(<[bi]>)*\s*[—–-]\s*[A-Z][a-z]+\.? [A-Z]")  # "— Jack Kerouac (Dharma Bums)"

def text_of(h): return re.sub(r"<[^>]+>", "", h).strip()

def prep_image(fn):
    """Flatten to RGB JPEG q92, long side <= 2600 px (well past 300 ppi at any size it prints)."""
    base = os.path.splitext(fn)[0]; dst = f"{OUT}/img/{base}.jpg"
    im = Image.open(f"{SRC}/img/{fn}")
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA"); bg = Image.new("RGB", im.size, "white"); bg.paste(im, mask=im.split()[-1]); im = bg
    else: im = im.convert("RGB")
    if max(im.size) > 2600: im.thumbnail((2600, 2600), Image.LANCZOS)
    if not os.path.exists(dst): im.save(dst, "JPEG", quality=92, optimize=True)
    # a white-ground image (a book cover, a screenshot, a line drawing) gets a hairline edge so it
    # does not dissolve into the page
    g = im.convert("L"); w_, h_ = g.size; px = g.load()
    edge = [px[x, 0] for x in range(0, w_, 7)] + [px[x, h_ - 1] for x in range(0, w_, 7)] + [px[0, y] for y in range(0, h_, 7)] + [px[w_ - 1, y] for y in range(0, h_, 7)]
    white = sum(1 for v in edge if v > 235) / len(edge) > 0.6
    return f"img/{base}.jpg", im.size, white

def flatten(blocks, ctx=None):
    """Post blocks -> the flat list the paginator places. ctx marks quotation containers."""
    out = []
    for b in blocks:
        t = b["type"]
        if t == "img":
            key = os.path.splitext(b["file"])[0]; src, (w, h), white = prep_image(b["file"])
            out.append({"t": "img", "src": src, "pw": w, "ph": h, "key": key, "credit": CREDIT.get(key), "white": white})
        elif t == "p":
            h_ = b["html"].strip()
            if not text_of(h_) or text_of(h_) in FURNITURE: continue
            if out and out[-1]["t"] == "img" and out[-1]["key"] in CREDIT_FROM_NEXT_P and out[-1]["credit"] is None:
                out[-1]["credit"] = h_; continue
            cls = "attr" if ATTR.match(h_) else (ctx or "body")
            out.append({"t": "p", "html": h_, "cls": cls})
        elif t == "button": continue
        elif t in ("h2", "h3"): out.append({"t": "h2", "html": b["html"], "cls": "date" if t == "h3" else "sec"})
        elif t == "h4": out.append({"t": "h4", "html": b["html"]})
        elif t in ("ul", "ol"):
            def rows(lst, depth):
                for i, it in enumerate(lst["items"], 1):
                    out.append({"t": "li", "html": it["t"], "depth": depth, "mk": f"{i}." if lst["type"] == "ol" else "–", "cls": ctx or "body"})
                    for s in it["sub"]: rows(s, depth + 1)
            rows(b, 0)
        elif t == "pre":
            txt = b["text"]; m = re.match(r"^( *)", txt); lead = len(m.group(1))
            body = html.escape(txt[lead:].rstrip())
            cls = "attr" if ATTR.match(body) else "verse"
            out.append({"t": "pre", "lead": lead, "html": body, "cls": cls})
        elif t == "hr": out.append({"t": "hr"})
        elif t == "blockquote": out += flatten(b["blocks"], "quote")
        elif t == "pullquote": out += flatten(b["blocks"], "pull")
    return out

corpus = json.load(open(f"{SRC}/corpus.json"))
pieces = []
for i, p in enumerate(corpus, 1):
    pieces.append({"no": i, "slug": p["slug"], "title": p["title"], "subtitle": p["subtitle"], "date": p["date"],
                   "blocks": flatten(p["blocks"])})

tpl = open(f"{ROOT}/scripts/issue.template.html").read()
js = open(f"{ROOT}/scripts/paginate.js").read()
page = tpl.replace("/*PIECES*/", "const PIECES = " + json.dumps(pieces, ensure_ascii=False) + ";").replace("/*PAGINATE*/", js)
open(f"{OUT}/issue.html", "w").write(page)
n_img = sum(1 for p in pieces for b in p["blocks"] if b["t"] == "img")
print(len(pieces), "pieces,", n_img, "images ->", f"{OUT}/issue.html")
