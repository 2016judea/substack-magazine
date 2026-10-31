#!/usr/bin/env python3
"""Read a rendered book back from its PDF and fix what CSS cannot see.

The probe render carries invisible 1 px markers (@e:slug@ on an essay's first page, @z:slug@
after its last word, @d:/@l:/@t:/@c: on the other pages); the press render does not, and the
markers are absolutely positioned, so both lay out identically.

Fixes, in order of visual cost:
  holes     a figure that did not fit at the foot of a column or page leaves a hole above it:
            shrink that figure to fit the hole (never below half its size)
  stubs     an essay's last page under a third full: tighten or loosen its word spacing and
            tracking, or scale its figures, whichever candidate fixes it at the lowest cost
  codas     the closing Some Literature passage sits at the foot of the essay's last page, and a
            one-page piece sits at the foot of its page, so the space left is composed, not empty
  widows    a page or column that opens on the last line of a paragraph: loosen that paragraph
"""
import re
import pdfplumber
import build as Bd

b = Bd.BL
TOPY, BOTY = Bd.TOP + b, Bd.TOP + b + Bd.TH
MID = None

def read(pdf):
    pages = []
    with pdfplumber.open(pdf) as d:
        for i, pg in enumerate(d.pages):
            ch = pg.chars
            # probe markers are the only white text in the book (5 pt, zero line height)
            white = lambda c: (lambda k: k is not None and len(k) >= 1 and all(abs(v - 1) < .02 for v in k))(c.get("non_stroking_color"))
            mk = "".join(c["text"] for c in ch if white(c))
            marks = re.findall(r"@([a-z]):([^@]+)@", mk)
            tiny = [w for w in pg.extract_words(extra_attrs=["non_stroking_color"]) if white(w)]
            btop = next((w["top"] for w in tiny if w["text"].startswith("@b:")), None)
            real = [c for c in ch if not white(c)]
            words = pg.extract_words(extra_attrs=["size", "fontname", "non_stroking_color"]) if real else []
            words = [w for w in words if not white(w)]
            ims = sorted(({"x0": m["x0"], "x1": m["x1"], "top": m["top"], "bottom": m["bottom"], "src": m["srcsize"]} for m in pg.images),
                         key=lambda m: (m["top"], m["x0"]))
            # left page: content starts at OUTER; right page: INNER (page 1 is a right page)
            left = (i + 1) % 2 == 0
            x0 = b + (Bd.OUTER if left else Bd.INNER)
            pages.append(dict(n=i + 1, marks=marks, btop=btop, words=words, images=ims, x0=x0, w=float(pg.width), h=float(pg.height)))
    return pages

def spans(pages):
    """essay slug -> (first page, last page). An essay ends on the page before the next section
    starts (every section opens a page); the last section ends on the last page."""
    import content as C
    slug = {re.sub(r"[^a-z0-9]", "", x): x for x in C.SLUGS}   # a 1 px hyphen can drop out of the PDF text
    starts = []
    for pg in pages:
        for k, v in pg["marks"]:
            if k in "edltc": starts.append((pg["n"], k, slug.get(re.sub(r"[^a-z0-9]", "", v), v)))
    starts.sort()
    out = {}
    for i, (n, k, v) in enumerate(starts):
        if k != "e": continue
        nxt = next((m for m, _, _ in starts[i + 1:] if m > n), len(pages) + 1)
        out[v] = (n, nxt - 1)
    return out

def items(pg):
    """content boxes inside the text block: words + images, with a column tag (0, 1 or 'span')"""
    x0 = pg["x0"]; mid = x0 + Bd.TW / 2
    out = []
    for w in pg["words"]:
        if TOPY - 3 <= w["top"] and w["bottom"] <= BOTY + 4:
            out.append(dict(t="w", x0=w["x0"], x1=w["x1"], top=w["top"], bottom=w["bottom"], text=w["text"], size=w["size"], font=w["fontname"]))
    for m in pg["images"]:
        out.append(dict(t="i", x0=m["x0"], x1=m["x1"], top=m["top"], bottom=m["bottom"], src=m["src"]))
    if pg.get("btop") is not None:      # an opener page: only the body, below the header, flows in columns
        out = [i for i in out if i["top"] >= pg["btop"] - 2]
    for it in out:
        if it["x1"] - it["x0"] > Bd.TW * 0.55 and it["x0"] < mid - 10 and it["x1"] > mid + 10: it["col"] = "span"
        else: it["col"] = 0 if (it["x0"] + it["x1"]) / 2 < mid else 1
    return out

def fill(pg):
    it = items(pg)
    if not it: return 0
    return (max(i["bottom"] for i in it) - TOPY) / Bd.TH

def figure_ids(pages, sp, figs_by_essay):
    """map (page, image index) -> figure id, on the pixel size of the embedded image"""
    out = {}
    for s, (a, z) in sp.items():
        left = list(figs_by_essay.get(s, []))
        for n in range(a, z + 1):
            for j, m in enumerate(pages[n - 1]["images"]):
                f = next((f for f in left if tuple(f["px"]) == tuple(m["src"])), None)
                if f: out[(n, j)] = f["id"]; left.remove(f)
    return out

def gaps(pages, sp, mode_of):
    """(page, slug, column, gap pt, the item that flows next, its page) at the foot of every
    column of every page of an essay except its last"""
    out = []
    for s, (a, z) in sp.items():
        two = mode_of[s] == "two"
        for n in range(a, z):
            it, nit = items(pages[n - 1]), items(pages[n])
            if not it: continue
            spn = [i for i in it if i["col"] == "span"]
            below = max([i["bottom"] for i in spn], default=0)
            for c in ([0, 1] if two else [0]):
                mine = [i for i in it if (not two) or i["col"] in (c, "span")]
                if two and c == 0:
                    # column 1 flows into column 2 of the same page, below the last spanner
                    pool = [i for i in it if i["col"] == 1 and i["top"] >= below - 1]
                    nxt_pg = n
                    if not pool: pool, nxt_pg = nit, n + 1
                else:
                    pool, nxt_pg = nit, n + 1
                if not mine or not pool: continue
                gap = BOTY - max(i["bottom"] for i in mine)
                topi = min(pool, key=lambda i: (round(i["top"]), i["x0"]))
                out.append((n, s, c, gap, topi, nxt_pg))
    return out

def holes(pages, sp, figs_by_essay, mode_of, fit):
    """{key: value} fixes for figures that left a hole above them, plus the holes left over"""
    fid = figure_ids(pages, sp, figs_by_essay)
    figs = {f["id"]: f for fs in figs_by_essay.values() for f in fs}
    fix, left = {}, []
    for n, s, c, gap, topi, nxt_pg in gaps(pages, sp, mode_of):
        if gap < 0.12 * Bd.TH: continue
        it = items(pages[n - 1])
        # a full-width figure with a hole under it (Chromium pushes the text after a spanner to the
        # next page when the rest will not fit beside it): let it run in a column instead
        lowest = max(it, key=lambda i: i["bottom"])
        if lowest["t"] == "i" and lowest["col"] == "span":
            j = pages[n - 1]["images"].index(next(m for m in pages[n - 1]["images"] if abs(m["top"] - lowest["top"]) < .5 and abs(m["x0"] - lowest["x0"]) < .5))
            f = fid.get((n, j))
            if f and figs[f]["kind"] == "span" and not fit.get(f + "#col"): fix[f + "#col"] = 1; continue
        pool = items(pages[nxt_pg - 1])
        img, lab = None, 0
        if topi["t"] == "i" and topi["top"] < TOPY + 30: img = topi
        elif topi["t"] == "w":
            # a label line kept with the figure under it ("Low Exposure:")
            below = sorted((i for i in pool if i["top"] > topi["bottom"] - 1 and (i["col"] == topi["col"] or i["col"] == "span" or topi["col"] == "span")), key=lambda i: i["top"])
            words_between = [i for i in below if i["t"] == "w" and i["top"] < (next((b["top"] for b in below if b["t"] == "i"), 1e9))]
            nxt_img = next((b for b in below if b["t"] == "i"), None)
            if nxt_img and nxt_img["top"] - topi["top"] < 60 and len({round(w["top"]) for w in words_between}) <= 1:
                img, lab = nxt_img, nxt_img["top"] - topi["top"]
        if img:
            ims = pages[nxt_pg - 1]["images"]
            j = next(k for k, m in enumerate(ims) if abs(m["top"] - img["top"]) < .5 and abs(m["x0"] - img["x0"]) < .5)
            f = fid.get((nxt_pg, j))
            if not f: left.append((n, s, f"unmatched figure gap {gap:.0f}")); continue
            h = img["bottom"] - img["top"]
            sc = (gap - 30 - lab) / h
            kind = figs[f]["kind"]
            if kind == "span" and not fit.get(f + "#col"): fix[f + "#col"] = 1
            elif sc >= 0.45 and h * sc >= 110: fix[f] = round(sc, 3)
            elif not fit.get(f + "#defer") and not lab: fix[f + "#defer"] = 1
            else: left.append((n, s, f"{f} needs {sc:.2f}"))
        else:
            left.append((n, s, f"col {c} gap {gap:.0f}pt before '{topi.get('text', 'img')}'"))
    return fix, left

def cost(pages, sp, mode_of):
    """per essay: hole area, stub, heads at foot, widows (lower is better)"""
    out = {s: 0.04 * (z - a + 1) for s, (a, z) in sp.items()}
    for n, s, c, gap, topi, nxt_pg in gaps(pages, sp, mode_of):
        if gap > 0.08 * Bd.TH: out[s] += gap / Bd.TH
    for s, (a, z) in sp.items():
        f = fill(pages[z - 1])
        if z > a and f < 0.3: out[s] += 0.3 + (0.3 - f) * 4
        elif z > a and mode_of[s] == "one" and f < 0.55: out[s] += (0.55 - f) * 2   # a photo page left half empty
    for n, s, t in heads_at_foot(pages, sp, mode_of): out[s] += 1
    for n, s, t in widows(pages, sp, mode_of): out[s] += 0.5
    return out

def last_fill(pages, sp):
    return {s: (z - a + 1, round(fill(pages[z - 1]), 3)) for s, (a, z) in sp.items()}

def widows(pages, sp, mode_of):
    """a column that opens on a paragraph's last line (short line, next line indented)"""
    out = []
    for s, (a, z) in sp.items():
        for n in range(a + 1, z + 1):
            pg = pages[n - 1]; it = [i for i in items(pg) if i["t"] == "w" and 9.9 < i["size"] < 10.6]
            for c in ([0, 1] if mode_of[s] == "two" else [0]):
                ws = [i for i in it if i["col"] == c]
                if not ws: continue
                L = {}
                for w in ws: L.setdefault(round(w["bottom"]), []).append(w)
                ks = sorted(L)
                if len(ks) < 2 or ks[0] > TOPY + 16: continue
                left = min(w["x0"] for k in ks[:6] for w in L[k])
                right = max(w["x1"] for k in ks[:6] for w in L[k])
                a0, nx = sorted(L[ks[0]], key=lambda w: w["x0"]), sorted(L[ks[1]], key=lambda w: w["x0"])
                if a0[0]["x0"] - left < 2 and right - a0[-1]["x1"] > 0.3 * (right - left) and nx[0]["x0"] - left > 6 and ks[1] - ks[0] < 16:
                    out.append((n, s, " ".join(w["text"] for w in a0)))
    return out

def heads_at_foot(pages, sp, mode_of):
    """a heading (italic deck 13.6 pt, dept small caps, his semibold sub) as the last line of a column"""
    out = []
    for s, (a, z) in sp.items():
        for n in range(a, z):
            pg = pages[n - 1]; it = [i for i in items(pg) if i["t"] == "w"]
            for c in ([0, 1] if mode_of[s] == "two" else [0]):
                ws = [i for i in it if i["col"] == c]
                if not ws: continue
                lb = max(w["bottom"] for w in ws)
                if BOTY - lb > 60: continue
                if any(i["t"] == "i" and i["top"] > lb for i in it if i["col"] in (c, "span")): continue
                lines = {}
                for w in ws: lines.setdefault(round(w["bottom"]), []).append(w)
                ks = sorted(lines)[-2:]
                ishead = lambda L: all("SSHead" in w["font"] or "Semibold" in w["font"] for w in L)
                last = lines[ks[-1]]
                txt = " ".join(w["text"] for w in last)
                label = txt.isupper()
                if ishead(last) or (len(ks) == 2 and ishead(lines[ks[0]]) and (label or len(txt) < 40)) or (label and len(txt) < 30):
                    hl = last if ishead(last) else lines[ks[0]]
                    out.append((n, s, " ".join(w["text"] for w in hl)))
    return out
