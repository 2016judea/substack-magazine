#!/usr/bin/env python3
"""The press files, from the fit that build.py settled (build/fit.json).

  press/AIDAN-JUDE-COMPLETE-INTERIOR.pdf   Mixam Perfect (PUR) inside pages, 8.5x11 + 0.125 in bleed
  press/AIDAN-JUDE-COMPLETE-COVER.pdf      the cover spread: back | spine | front, with bleed

Pagination: title page, contents spread, then the four parts. Each part divider is a left-hand page
facing its first essay. Where a divider would fall on a right-hand page, and to bring the inside
to a multiple of 4, a page carries one of his own lines (build.LINES), bottom-aligned.
Running heads and folios are drawn by a second Chromium document merged onto each page, so the
opener, divider and line pages carry none.
"""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build as Bd, content as C, fit as Ft
from pypdf import PdfReader, PdfWriter, Transformation
from pypdf.generic import RectangleObject

B, P = Bd.B, Bd.P
W, H, BL = Bd.W, Bd.H, Bd.BL
CAL_TEXT, CAL_COVER = 0.004, 0.010          # Mixam Satin 80lb Text / 100lb Cover, inches per leaf

def spine_in(pages):  # substack-magazine/public/app.js spineCalc: standard US plants
    import math
    return math.floor(pages / 2 * CAL_TEXT * 100 + 1e-6) / 100 + 0.01

def paginate(lengths):
    """plan + the essay -> first page map, from each essay's page count"""
    year = {s: C.Post(s, {}).year for s in C.SLUGS}
    plan, n, used = ["title", "contents"], 4, []      # pages 1, 2-3
    def line(after_year):
        cand = [i for i, (sl, t) in enumerate(Bd.LINES) if i not in used and year[sl] == after_year] or \
               [i for i in range(len(Bd.LINES)) if i not in used]
        used.append(cand[0]); return ("line", cand[0])
    toc = {}; prev = 2023
    for y in Bd.PARTS:
        if n % 2 == 1:                               # divider must be a left-hand (even) page
            plan.append(line(prev)); n += 1
        plan.append(("div", y)); n += 1
        for s in C.SLUGS:
            if year[s] != y: continue
            plan.append(("essay", s)); toc[s] = n; n += lengths[s]
        prev = y
    total = n - 1
    extra = (-total) % 4
    for _ in range(extra): plan.append(line(2026))
    return plan, toc, total + extra

def kinds(plan, lengths, posts):
    """per page: (kind, head text)"""
    out = []
    for it in plan:
        if it == "title": out.append(("title", ""))
        elif it == "contents": out += [("contents", ""), ("contents", "")]
        elif it[0] in ("div", "line"): out.append((it[0], ""))
        else:
            p = posts[it[1]]
            out.append(("opener", p.title))
            out += [("page", p.title)] * (lengths[it[1]] - 1)
    return out

def overlay_html(ks, press):
    b = BL if press else 0; PW, PH = W + 2 * b, H + 2 * b
    secs = []
    for i, (k, t) in enumerate(ks):
        n = i + 1; left = n % 2 == 0
        o = []
        if k in ("page", "opener"):
            x = f"left:{b + Bd.OUTER}pt" if left else f"right:{b + Bd.OUTER}pt"
            o.append(f'<div class="fo" style="{x};top:{b + H - 40}pt">{n}</div>')
        if k == "page":
            x = f"left:{b + Bd.OUTER}pt" if left else f"right:{b + Bd.OUTER}pt"
            o.append(f'<div class="rh" style="{x};top:{b + 33}pt;text-align:{"left" if left else "right"}">{Bd.esc(t)}</div>')
        secs.append(f'<section>{"".join(o)}</section>')
    ff = "".join(f"@font-face{{font-family:{n};src:url({Bd.F}/{n}.ttf)}}" for n in ("SSText-Regular", "SSCap-Regular"))
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{ff}
@page{{size:{PW}pt {PH}pt;margin:0}} body{{margin:0}} html{{-webkit-print-color-adjust:exact}}
section{{position:relative;width:{PW}pt;height:{PH}pt;break-after:page;overflow:hidden}}
.fo{{position:absolute;font:9pt/1 SSText-Regular;font-variant-numeric:oldstyle-nums;color:{Bd.INK}}}
.rh{{position:absolute;font:8.2pt/1 SSText-Regular;font-variant-caps:all-small-caps;letter-spacing:.16em;color:{Bd.MUTE};white-space:nowrap}}
</style></head><body>{"".join(secs)}</body></html>"""

NUMWORD = {51: "Fifty-one"}

def cover_front(press, n_pieces, ox):
    """Cover A, "Night", approved by Aidan 2026-10-30 (artifact 90b2e31e, periodicals-covers.html),
    ported verbatim: the prototype sizes in cqw (1% of the trim width). Mono line + rule at the top
    in vermilion, the name stacked large at the foot, the count alone beneath it (Credo's foot).
    Type and colour only, no image. ox = where the trim's left edge sits inside the panel."""
    b = BL if press else 0; q = W / 100
    L = ox + 7 * q; R = W - 14 * q
    cnt = f"{NUMWORD.get(n_pieces, n_pieces)} pieces"
    return (f'<div class="top" style="left:{L:.2f}pt;width:{R:.2f}pt;top:{b + 6 * q:.2f}pt;font-size:{2.6 * q:.2f}pt;'
            f'border-bottom:{.25 * q:.2f}pt solid {Bd.ACCD};padding-bottom:{2.4 * q:.2f}pt">Periodicals · 2023–2026</div>'
            f'<div class="name" style="left:{ox + 6.4 * q:.2f}pt;bottom:{b + 14 * q:.2f}pt;font-size:{21 * q:.2f}pt">Aidan<br>Jude</div>'
            f'<div class="ft" style="left:{L:.2f}pt;bottom:{b + 6 * q:.2f}pt;font-size:{2.4 * q:.2f}pt">{cnt}</div>')

COVER_CSS = """
.cv{{position:absolute;top:0;height:{PH}pt;background:{G};color:#f3efe6;overflow:hidden}}
.cv>div{{position:absolute;margin:0}}
.top,.ft{{font-family:SCP-Regular;letter-spacing:.16em;text-transform:uppercase;line-height:1.2;white-space:nowrap}}
.top{{color:{AC}}}
.ft{{color:#9aa3b5}}
.name{{font-family:SSDisp-Light;line-height:.86;letter-spacing:-.02em}}
.cv .st{{position:absolute;left:50%;top:50%;white-space:nowrap;transform:translate(-50%,-50%) rotate(90deg);
  font:{SZ}pt/1 SSText-Regular;font-variant-caps:all-small-caps;letter-spacing:.2em;color:{PA}}}
.cv .st em{{font-style:normal;color:{AC};margin-left:.9em}}
"""

def cover_doc(press, n_pieces, spine_pt=None, single=None):
    b = BL if press else 0; PH = H + 2 * b
    ff = "".join(f"@font-face{{font-family:{n};src:url({Bd.F}/{n}.ttf)}}" for n in ("SSDisp-Light", "SCP-Regular", "SSText-Regular", "SSText-Italic"))
    sz = min(10, (spine_pt or 0) * 0.42)
    css = COVER_CSS.format(PH=PH, G=Bd.GROUND, PA=Bd.PAPER, AC=Bd.ACCD, SZ=f"{sz:.1f}")
    if single:      # one page (FedEx): front or plain back
        PW = W + 2 * b
        inner = cover_front(press, n_pieces, b) if single == "front" else ""
        body = f'<div class="cv" style="left:0;width:{PW}pt">{inner}</div>'
    else:
        PW = 2 * W + spine_pt + 2 * b
        st = '<div class="st">Aidan Jude<em>2023–2026</em></div>' if spine_pt >= 18 else ""   # app.js: >= 0.25 in
        body = (f'<div class="cv" style="left:0;width:{b + W}pt"></div>'
                f'<div class="cv" style="left:{b + W}pt;width:{spine_pt}pt">{st}</div>'
                f'<div class="cv" style="left:{b + W + spine_pt}pt;width:{W + b}pt">{cover_front(press, n_pieces, 0)}</div>')
    return (f'<!doctype html><html><head><meta charset="utf-8"><style>{ff}@page{{size:{PW}pt {PH}pt;margin:0}}body{{margin:0}}'
            f'html{{-webkit-print-color-adjust:exact;print-color-adjust:exact}}{css}</style></head>'
            f'<body><div style="position:relative;width:{PW}pt;height:{PH}pt">{body}</div></body></html>')

def boxes(pdf, press, title, width=None):
    b = BL if press else 0
    r = PdfReader(pdf); w = PdfWriter()
    for pg in r.pages:
        PW = float(pg.mediabox.width); PH = float(pg.mediabox.height); y0 = float(pg.mediabox.bottom)
        box = RectangleObject([0, y0, PW, y0 + PH])
        pg.mediabox = box; pg.cropbox = box; pg.bleedbox = box
        pg.trimbox = RectangleObject([b, y0 + b, PW - b, y0 + PH - b]); w.add_page(pg)
    w.add_metadata({"/Title": title, "/Author": "Aidan Jude"})
    with open(pdf, "wb") as fh: w.write(fh)

def merge(base, over, out):
    r, o = PdfReader(base), PdfReader(over); w = PdfWriter()
    assert len(r.pages) == len(o.pages), (len(r.pages), len(o.pages))
    for a, b2 in zip(r.pages, o.pages):
        a.merge_page(b2); w.add_page(a)
    with open(out, "wb") as fh: w.write(fh)

def main():
    j = json.load(open(f"{B}/fit.json")); fit, tune = j["fit"], j["tune"]
    # page counts measured in the book itself (markers are DOM-identical in every render)
    def measure(rr, tune, fit, lengths):
        for it in range(8):
            plan, toc, total = paginate(lengths)
            htm, _, _ = Bd.document(True, plan, toc, tune, fit, marks=True)
            pdf = f"{B}/book-probe.pdf"; rr.pdf(htm, pdf, "book-probe")
            pages = Ft.read(pdf); sp = Ft.spans(pages)
            new = {s: z - a + 1 for s, (a, z) in sp.items()}
            if new == lengths: return lengths, pages, sp
            print("  measure:", {k: (lengths[k], new[k]) for k in new if new[k] != lengths.get(k)})
            lengths = new
        raise SystemExit("page counts did not settle")
    with Bd.Renderer() as rr:
        lengths, pages, sp = measure(rr, tune, fit, {s: 1 for s in C.SLUGS})
        # pad pages are the last resort: first take pages out of the pieces whose last page is
        # emptiest, by tightening their spacing (or their pictures) until the book needs none
        pads = lambda L: sum(1 for it in paginate(L)[0] if it[0] == "line")
        need = pads(lengths)
        print("pads needed", need)
        if need:
            fills = {s: Ft.fill(pages[z - 1]) for s, (a, z) in sp.items() if z > a}
            cands = [dict(ws=-.45, ls=-.005), dict(ws=-.6, ls=-.008), dict(fs=.85), dict(ws=-.45, ls=-.005, fs=.85)]
            gain = {}
            for c in cands:
                t2 = {k: dict(v) for k, v in tune.items()}; f2 = dict(fit)
                for s in fills:
                    if c.get("ws"): t2[s]["ws"] = c["ws"]
                    if c.get("ls"): t2[s]["ls"] = c["ls"]
                    if c.get("fs"): f2[f"*{s}"] = round(fit.get(f"*{s}", 1) * c["fs"], 3)
                plan, toc, _ = paginate(lengths)
                htm, _, _ = Bd.document(True, plan, toc, t2, f2, marks=True)
                rr.pdf(htm, f"{B}/shave.pdf", "shave"); pg2 = Ft.read(f"{B}/shave.pdf"); sp2 = Ft.spans(pg2)
                for s in fills:
                    a, z = sp2[s]
                    if z - a + 1 < lengths[s] and Ft.fill(pg2[z - 1]) > 0.3 and s not in gain: gain[s] = c
            order = sorted(gain, key=lambda s: fills[s])
            print("can shave:", {s: gain[s] for s in order})
            for s in order:
                if not pads(lengths): break
                bt, bf = dict(tune[s]), dict(fit)
                c = gain[s]
                if c.get("ws"): tune[s]["ws"] = c["ws"]
                if c.get("ls"): tune[s]["ls"] = c["ls"]
                if c.get("fs"): fit[f"*{s}"] = round(fit.get(f"*{s}", 1) * c["fs"], 3)
                L2, p2, s2 = measure(rr, tune, fit, lengths)
                if pads(L2) < pads(lengths): lengths, pages, sp = L2, p2, s2; print("  shaved", s, c, "pads now", pads(lengths))
                else: tune[s] = bt; fit.clear(); fit.update(bf)
        for rnd in range(3):
            mode = {s: C.Post(s, {}).mode for s in C.SLUGS}
            hf = Ft.heads_at_foot(pages, sp, mode)
            if not hf: break
            for n, s2, t in hf:
                w = [x for x in t.split() if len(x) > 3][:1]
                if mode[s2] == "one":     # a photo essay: smaller pictures pull the heading's text up with it
                    fit[f"*{s2}"] = round(fit.get(f"*{s2}", 1) * 0.92, 3); print("  shrink pictures", s2)
                elif w: tune.setdefault(s2, {}).setdefault("brk", []).append(w[0]); print("  break before", s2, w[0])
            lengths, pages, sp = measure(rr, tune, fit, lengths)
        json.dump(dict(fit=fit, tune=tune), open(f"{B}/fit-press.json", "w"), indent=1)
    plan, toc, total = paginate(lengths)
    print("interior pages", total, "| line pages", [Bd.LINES[it[1]][0] for it in plan if it[0] == "line"])
    posts = {s: C.Post(s, fit) for s in C.SLUGS}
    ks = kinds(plan, lengths, posts)
    assert len(ks) == total, (len(ks), total)
    sp_in = spine_in(total); sp_pt = sp_in * 72
    out = {}
    with Bd.Renderer() as rr:
        for press in (True,):          # Mixam only (Aidan, 2026-10-30: "i only order thru mixam")
            tag = "INTERIOR" if press else "FEDEX"
            # render WITH the probe markers, made transparent: the markers are what the page counts were
            # measured with, and leaving them out shifted one column balance by a page (10/30)
            htm, _, figs = Bd.document(press, plan, toc, tune, fit, marks=True)
            k = ".mk{position:absolute;font-size:5pt;line-height:0;color:#fff"; assert k in htm
            htm = htm.replace(k, k[:-4] + "transparent")
            raw = f"{B}/{tag.lower()}-raw.pdf"; rr.pdf(htm, raw, tag.lower())
            n = len(PdfReader(raw).pages)
            if n == total + 1:      # the last line page's flex box spills a page that holds only its marker
                last = PdfReader(raw).pages[-1]
                if not re.sub(r"@[a-z]:[^@]+@|\s", "", last.extract_text() or "") and not last.images:
                    w = PdfWriter(); [w.add_page(x) for x in PdfReader(raw).pages[:-1]]
                    with open(raw, "wb") as fh: w.write(fh)
                    n = total; print("  dropped the empty trailing page")
            assert n == total, f"{tag}: rendered {n} pages, plan says {total}"
            ov = f"{B}/{tag.lower()}-overlay.pdf"; rr.pdf(overlay_html(ks, press), ov, tag.lower() + "-overlay")
            body = f"{B}/{tag.lower()}-merged.pdf"; merge(raw, ov, body)
            if press:
                dst = f"{P}/AIDAN-JUDE-COMPLETE-INTERIOR.pdf"; os.replace(body, dst)
                boxes(dst, True, "Aidan Jude · Periodicals · 2023–2026 (inside pages)")
                cv = f"{P}/AIDAN-JUDE-COMPLETE-COVER.pdf"; rr.pdf(cover_doc(True, len(C.SLUGS), sp_pt), cv, "cover")
                boxes(cv, True, "Aidan Jude · Periodicals · 2023–2026 (cover)")
                out["interior"], out["cover"] = dst, cv
            else:
                fr, bk = f"{B}/fx-front.pdf", f"{B}/fx-back.pdf"
                rr.pdf(cover_doc(False, len(C.SLUGS), single="front"), fr, "fx-front")
                rr.pdf(cover_doc(False, len(C.SLUGS), single="back"), bk, "fx-back")
                w = PdfWriter()
                for f in (fr, body, bk):
                    for pg in PdfReader(f).pages: w.add_page(pg)
                dst = f"{P}/AIDAN-JUDE-COMPLETE-FEDEX.pdf"
                with open(dst, "wb") as fh: w.write(fh)
                boxes(dst, False, "Aidan Jude · Periodicals · 2023–2026")
                out["fedex"] = dst
    json.dump(dict(plan=plan, toc=toc, total=total, spine_in=sp_in, out=out, kinds=ks), open(f"{B}/press.json", "w"), indent=1)
    print(f"spine {sp_in:.2f} in ({sp_pt:.1f} pt) ->", out)

if __name__ == "__main__":
    main()
