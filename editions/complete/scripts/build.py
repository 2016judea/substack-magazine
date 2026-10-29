#!/usr/bin/env python3
"""Aidan Jude — Selected writing · 2023–2026. Every Periodicals post, one magazine.

Design: one family, Source Serif 4, at the optical size each job needs (8 pt credits, 10 pt text,
18 pt decks, 60 pt display). Text 10.25/14 pt in two 241 pt columns on a 48-line page, the same
for every piece. Deep ink ground for the cover and the four part dividers; one accent, vermilion,
for dates, department heads and the part years. Four parts, one per year, chronological.

Layout is Chromium's own paged media, printed by Playwright, read back from the PDF to fix what CSS
cannot see (scripts/fit.py). Running heads and folios are a second Chromium document merged on top
(press.py) so opener, divider and line pages carry none.

  python3 scripts/fetch.py && python3 scripts/make_fonts.py && python3 scripts/build.py
"""
import html, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import content as C

R = C.R; B, P, Q = f"{R}/build", f"{R}/press", f"{R}/qa"
for d in (B, P, Q): os.makedirs(d, exist_ok=True)
F = f"file://{R}/fonts"

W, H, BL = 612, 792, 9
TOP, BOT, INNER, OUTER = 60, 60, 62, 48
TW, TH = W - INNER - OUTER, H - TOP - BOT          # 502 x 672 = 48 lines of 14 pt
LEAD = 14
INK, ACC, GROUND, PAPER, MUTE, ACCD = "#141b26", "#b5361b", "#101a2a", "#f7f3ec", "#5c6370", "#f0704a"
PARTS = [2023, 2024, 2025, 2026]

# His own lines, verbatim, for any page the book still needs after reflowing. One per post, none of
# them one of his pull quotes. Ordered so each lands in its own year where possible.
LINES = [
    ("september", "Align the sextant. Set a heading. Draw a footpath amongst the celestial vault."),
    ("october", "He simply did not know it yet."),
    ("july", "Water across rock. Caffeine for the soul."),
    ("december", "Groupthink isn’t sexy. It never was (and never will be)."),
    ("march-24", "To me, solitude is about recharging."),
    ("october-24", "Take time as you need it. There’s nothing a man can’t do tomorrow."),
    ("january", "Many beautiful things are like this. Impractical that is."),
    ("january-25", "There’s always this sense of calm when I catch their peaks in my rearview."),
    ("june-25", "Beauty in unexpected places."),
    ("south-africa", "You make time for the people you care about."),
    ("big-sky-journals-3", "Look left and the sky’s gone orange. Family dinner at elevation."),
    ("canadian-contiki", "Shook the rust off."),
    ("oct-26", "Autumn nights and oak trees with yellow leaves."),
    ("feb-26", "Operate on what you have."),
]

def esc(s): return html.escape(s, quote=False)

FONTS = ["SSText-Regular", "SSText-Italic", "SSText-Semibold", "SSText-SemiboldItalic", "SSCap-Regular", "SSCap-Italic",
         "SSDeck-Regular", "SSDeck-Italic", "SSDeck-Semibold", "SSHead-Italic", "SSDisp-Light", "SSDisp-Regular", "SSDisp-Semibold",
         "SSDisp-Bold", "SSDisp-LightItalic", "SSDisp-Italic", "SCP-Regular"]

def css(press, tune):
    b = BL if press else 0; PW, PH = W + 2 * b, H + 2 * b
    ff = "".join(f"@font-face{{font-family:{n};src:url({F}/{n}.ttf)}}"
                 f"@font-face{{font-family:{n};src:url({F}/NotoEmoji-Regular.ttf);unicode-range:U+1F000-1FAFF,U+2600-27BF,U+2B00-2BFF}}" for n in FONTS)
    t = "".join(f"#e-{k} .body{{letter-spacing:{v.get('ls',0)}em;word-spacing:{v.get('ws',0)}pt}}" for k, v in tune.items() if v.get("ls") or v.get("ws"))
    return ff + f"""
@page{{size:{PW}pt {PH}pt;margin:0}}
@page :left{{margin:{TOP+b}pt {INNER+b}pt {BOT+b}pt {OUTER+b}pt}}
@page :right{{margin:{TOP+b}pt {OUTER+b}pt {BOT+b}pt {INNER+b}pt}}
@page bleed{{margin:0}} @page bleed:left{{margin:0}} @page bleed:right{{margin:0}}
html{{-webkit-print-color-adjust:exact;print-color-adjust:exact}}
body{{margin:0;font:10.25pt/{LEAD}pt SSText-Regular;color:{INK};font-kerning:normal;font-variant-numeric:oldstyle-nums proportional-nums;
  text-rendering:optimizeLegibility;hyphens:auto;-webkit-hyphens:auto;widows:2;orphans:2;background:#fff;font-synthesis:none}}
em,i{{font-family:SSText-Italic;font-style:normal}} strong,b{{font-family:SSText-Semibold;font-weight:normal}}
strong em,em strong{{font-family:SSText-SemiboldItalic}}
section{{break-before:page}}
.mk{{position:absolute;font-size:1px;line-height:1px;color:#fff;white-space:nowrap}}

/* ---------- bleed pages: dividers ---------- */
.bleedp{{page:bleed;position:relative;width:{PW}pt;height:{PH}pt;overflow:hidden;background:{GROUND};color:{PAPER}}}
.divider .yr{{position:absolute;left:{b+OUTER-6}pt;bottom:{b+BOT-38}pt;font:300 236pt/1 SSDisp-Light;letter-spacing:-.035em;color:{PAPER}}}
.divider .rule{{position:absolute;left:{b+OUTER}pt;right:{b+INNER}pt;top:{b+TOP}pt;border-top:.75pt solid {ACCD}}}

/* ---------- title page, contents, line pages ---------- */
.titlep{{height:{TH}pt;position:relative}}
.titlep .t1{{position:absolute;left:0;right:0;top:150pt;text-align:center;font:64pt/1 SSDisp-Regular;letter-spacing:-.01em}}
.titlep .t2{{position:absolute;left:0;right:0;top:232pt;text-align:center;font:10pt/1 SSText-Regular;font-variant-caps:all-small-caps;letter-spacing:.2em;color:{ACC}}}
.contents{{height:{TH-2}pt;overflow:hidden;display:grid;grid-template-columns:1fr 1fr;column-gap:22pt;align-content:start}}
.contents h1{{grid-column:1/3;margin:0 0 30pt;font:38pt/40pt SSDisp-Regular;letter-spacing:-.01em;height:40pt}}
.contents .py{{font:26pt/1 SSDisp-Light;color:{ACC};margin:0 0 12pt;padding-top:8pt;border-top:.6pt solid {INK}}}
.toc{{display:grid;grid-template-columns:1fr auto;column-gap:10pt;row-gap:6.5pt}}
.toc .tt{{font:10.25pt/13pt SSText-Regular;hyphens:manual}} .toc .ts{{display:block;font:8.6pt/11pt SSText-Italic;color:{MUTE};hyphens:manual;margin-top:.5pt}}
.toc .tn{{font:10.25pt/13pt SSText-Regular;font-variant-numeric:oldstyle-nums tabular-nums;text-align:right}}
.linep{{height:{TH}pt;display:flex;flex-direction:column;justify-content:flex-end}}
.linep p{{margin:0;font:27pt/33pt SSDisp-Regular;letter-spacing:-.004em;hyphens:manual;max-width:410pt;text-wrap:balance}}

/* ---------- essay opener ---------- */
.ehead{{margin:0 0 18pt}}
.ehead .date{{font:8.6pt/1 SSText-Regular;font-variant-caps:all-small-caps;letter-spacing:.2em;color:{ACC};margin:0 0 10pt}}
.ehead h1{{margin:0;font:42pt/45pt SSDisp-Regular;letter-spacing:-.012em;hyphens:manual;text-wrap:balance}}
.ehead .deck{{margin:8pt 0 0;font:15pt/19pt SSDeck-Italic;hyphens:manual;text-wrap:balance;max-width:420pt}}
.ehead .hr{{border-top:.6pt solid {INK};margin-top:14pt}}
.ehead.side{{display:flex;gap:20pt;align-items:flex-start}} .ehead.side .htext{{flex:1}}
.ehead.side .hr{{display:none}}
.ehead.side figure.plate{{margin:0}}
.ehead.side{{border-bottom:.6pt solid {INK};padding-bottom:14pt}}
.ehead figure.plate{{margin:16pt 0 0}}

/* ---------- body ---------- */
.body{{column-count:2;column-gap:20pt;column-fill:balance}}
.body p{{margin:0;text-align:justify;text-indent:1em}}
.body p.hasurl{{text-align:left}}
.url{{word-break:break-all;hyphens:none;-webkit-hyphens:none}}
.body>p:first-child,.body>.mk+p,.body h2+p,.body h3+p,.body h4+p,.body p.bold+p,.body figure+p,.body blockquote+p,.body ol+p,.body ul+p,
.body .lit+p,.body pre+p,.body .brk+p,.body p.riff.first,.body .disp+p{{text-indent:0}}
h2.dept{{margin:16pt 0 8pt;padding-top:5pt;border-top:.6pt solid {INK};font:8.6pt/{LEAD}pt SSText-Semibold;font-variant-caps:all-small-caps;letter-spacing:.2em;color:{ACC};break-after:avoid;break-inside:avoid}}
.body>h2.dept:first-child,.body>.mk+h2.dept,.coda>h2.dept:first-child{{margin-top:0}}
h3.item{{margin:13pt 0 5pt;font:13.6pt/16pt SSHead-Italic;hyphens:manual;break-after:avoid;break-inside:avoid;text-align:left}}
h3.item.long{{font:11pt/14pt SSHead-Italic}}
.body>h3.item:first-child,.body>.mk+h3.item,h2.dept+h3.item{{margin-top:2pt}}
h4.sub{{margin:9pt 0 2pt;font:10.25pt/{LEAD}pt SSText-Semibold;break-after:avoid;break-inside:avoid}}
h3.item+h4.sub{{margin-top:3pt}}
p.bold{{margin-top:6pt!important;text-indent:0!important;text-align:left!important;break-after:avoid}}
ol,ul{{margin:4pt 0 5pt;padding-left:1.25em}} li{{margin:0 0 1.5pt;text-align:left}} li ol,li ul{{margin:1.5pt 0;padding-left:1.15em}}
ul{{list-style:none}} ul>li{{position:relative}} ul>li::before{{content:"–";position:absolute;left:-1em;color:{MUTE}}}
ol>li::marker{{font-variant-numeric:oldstyle-nums;color:{MUTE}}}
.lp{{display:block}}
blockquote{{margin:6pt 0 7pt;padding-left:10pt;border-left:.6pt solid {ACC}}}
blockquote p{{text-indent:0!important;text-align:left!important}} blockquote p+p{{margin-top:4pt!important}}
blockquote.pull{{margin:10pt 0 11pt;padding:0;border:0}}
blockquote.pull p{{font:13.6pt/17.5pt SSDeck-Italic;hyphens:manual;text-wrap:pretty}}
.lit{{margin:6pt 0 7pt}}
.lit .lt{{font-family:SSText-Italic;text-align:left;hyphens:manual}}
.lit.verse .lt{{white-space:pre-wrap}}
.lit.prose .lt p{{text-align:justify;hyphens:auto;text-indent:0}} .lit.prose .lt p+p{{text-indent:1em}}
.lit .att{{margin-top:5pt;font:8.6pt/12pt SSText-Regular;font-variant-caps:all-small-caps;letter-spacing:.12em;color:{MUTE}}}
p.riff{{}}
pre.code{{margin:6pt 0 7pt;font:8.2pt/12pt SCP-Regular;white-space:pre-wrap;color:{INK};font-variant-numeric:normal}}
.brk{{height:{LEAD}pt;margin:0;text-align:center}} .brk::before{{content:"";display:inline-block;width:24pt;border-top:.6pt solid {MUTE};vertical-align:middle}}
figure.fig{{margin:10pt 0 11pt;break-inside:avoid}} figure.fig img{{display:block}}
figure.fig .im{{margin:0}}
figure.span,figure.strip{{column-span:all;margin:12pt 0 14pt}}
.one .body{{column-count:auto;padding:0 {TW-331-85}pt 0 85pt}}
.one .body figure.fig{{margin-left:-85pt;margin-right:-{TW-331-85}pt}} .one .body figure.fig .im{{margin:0 auto}}
.one .body figure.full{{margin-top:12pt;margin-bottom:13pt}}
figure.strip .im{{margin:0 auto}}
figure.col .im{{margin:0 auto}}
.credit{{display:block;margin-top:3.5pt;font:7.4pt/9.4pt SSCap-Italic;color:{MUTE};text-align:right;hyphens:manual;letter-spacing:.01em}}
.credit span{{display:block}}
.cap{{display:block;margin-top:4pt;font:8.2pt/10.6pt SSCap-Italic;color:{MUTE};text-align:left;hyphens:manual}}
.coda{{column-span:all;margin:16pt auto 0;width:330pt;break-inside:avoid}}
.coda .im{{max-width:330pt}} .coda img{{max-width:330pt;height:auto!important}} .coda figure.fig{{margin:10pt 0}}
.coda h2.dept{{text-align:center;border-top:0;padding-top:0;margin-bottom:9pt}}
.coda .lit .lt{{font-size:10.25pt}}
.coda>p{{text-indent:0;text-align:left;margin:0 0 4pt}}
.coda blockquote{{border:0;padding:0;margin:6pt 0}}
.coda blockquote.pull{{max-width:330pt}}
.coda blockquote p{{font-family:SSText-Italic}}
.coda blockquote.pull p{{font:13pt/17pt SSDeck-Italic}}
.end::after{{content:"";display:inline-block;width:5pt;height:5pt;background:{ACC};margin-left:5pt;vertical-align:.5pt}}
p.disp{{margin:0 0 6pt!important;text-indent:0!important;text-align:left!important;hyphens:manual;break-after:avoid}}
p.disp.h1{{font:30pt/34pt SSDisp-Regular}} p.disp.h3{{font:19pt/23pt SSDeck-Regular}} p.disp.h4{{font:15pt/19pt SSDeck-Italic}} p.disp.h5{{font:12pt/16pt SSDeck-Italic}}
{t}
"""

def opener(p, fit):
    plate = p.plate_html()
    side = ""
    if plate:
        w = p.figs[-1]["w"]
        if w <= 260: side = " side"
    date = f'<div class="date">{esc(p.date)}</div>'
    h = f'<h1>{esc(p.title)}</h1>' + (f'<p class="deck">{esc(p.sub)}</p>' if p.sub else "")
    if side:
        return f'<header class="ehead side"><div class="htext">{date}{h}</div>{plate}</header>'
    return f'<header class="ehead">{date}{h}{plate}<div class="hr"></div></header>' if not plate else \
           f'<header class="ehead">{date}{h}{plate}</header>'

def end_mark(html_):
    # an accent square after the last word he wrote; none when the piece ends on a picture
    if html_.rstrip().endswith("</figure>"): return html_
    m = re.search(r"(?:\s*(?:</[^>]+>|<div class=\"brk\"></div>|<br>))*\s*$", html_)
    k = m.start()
    return html_[:k] + '<span class="end"></span>' + html_[k:]

def essay(p, fit, tune, marks):
    head = opener(p, fit)
    main, tail = p.body_html()
    mt = tune.get(p.slug, {}).get("coda_mt", 0)
    body = "".join(main)
    if tail:
        if tune.get(p.slug, {}).get("coda_inline"):      # it did not fit as a spanner: it runs in the columns
            body += end_mark("".join(tail))
        else:
            body += f'<div class="coda" style="padding-top:{mt:.1f}pt">{end_mark("".join(tail))}</div>'
    else:
        body = end_mark(body)
    from collections import Counter as _C
    for t, k in _C(tune.get(p.slug, {}).get("brk", [])).items():
        # a heading Chromium left at the foot of a column starts the next column; asked twice
        # (a column break is a no-op at the top of a column set under a spanner), the next page
        kind = "column" if p.mode == "two" and k == 1 else "page"
        for m in re.finditer(r'<(h[234]|p class="bold")[^>]*>(.*?)</(h[234]|p)>', body):
            if t in re.sub(r"<[^>]+>", "", m.group(2)):
                body = body[:m.start()] + body[m.start():].replace(">", f' style="break-before:{kind}">', 1)
                break
    pad = tune.get(p.slug, {}).get("body_mt", 0)
    mk = f'<div class="mk">{"@e:" + str(p.slug) + "@" if marks else ""}</div>'
    body = f'<div class="mk">{"@b:" + p.slug + "@" if marks else ""}</div>' + body
    mke = f'<span class="mk">{"@z:" + p.slug + "@" if marks else ""}</span>'
    return (f'<section class="essay {p.mode}" id="e-{p.slug}" data-year="{p.year}">{mk}{head}'
            f'<div class="body" style="padding-top:{pad:.1f}pt">{body}{mke}</div></section>')

def divider(y, marks):
    mk = f'<div class="mk">{"@d:" + str(y) + "@" if marks else ""}</div>'
    return f'<section class="bleedp divider">{mk}<div class="yr">{y}</div></section>'

def linepage(i, marks):
    mk = f'<div class="mk">{"@l:" + str(i) + "@" if marks else ""}</div>'
    return f'<section class="linep">{mk}<p>{esc(LINES[i][1])}</p></section>'

def contents(posts, toc, marks):
    mk = f'<div class="mk">{"@c:1@" if marks else ""}</div>'
    cols = []
    for y in PARTS:
        rows = "".join(f'<div class="tt">{esc(p.title)}<span class="ts">{esc(p.sub)}</span></div><div class="tn">{toc.get(p.slug, "")}</div>'
                       for p in posts if p.year == y)
        cols.append(f'<div class="part"><div class="py">{y}</div><div class="toc">{rows}</div></div>')
    # two pages: 2023 + 2024 on the left, 2025 + 2026 on the right
    return (f'<section class="contents">{mk}<h1>Contents</h1><div>{cols[0]}</div><div>{cols[1]}</div></section>'
            f'<section class="contents"><h1>&nbsp;</h1><div>{cols[2]}</div><div>{cols[3]}</div></section>')

def document(press, plan, toc=None, tune=None, fit=None, marks=True):
    """plan: list of ("title"|"contents"|("div",y)|("essay",slug)|("line",i))"""
    toc = toc or {}; tune = tune or {}; fit = fit or {}
    posts = {s: C.Post(s, fit) for s in C.SLUGS}
    parts = []
    for it in plan:
        if it == "title":
            parts.append(f'<section class="titlep"><div class="mk">{"@t:1@" if marks else ""}</div><div class="t1">Aidan Jude</div><div class="t2">Selected writing&nbsp;&nbsp;·&nbsp;&nbsp;2023–2026</div></section>')
        elif it == "contents": parts.append(contents(list(posts.values()), toc, marks))
        elif it[0] == "div": parts.append(divider(it[1], marks))
        elif it[0] == "essay": parts.append(essay(posts[it[1]], fit, tune, marks))
        elif it[0] == "line": parts.append(linepage(it[1], marks))
    figs = {f["id"]: f for p in posts.values() for f in p.figs}
    htm = (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Aidan Jude · Selected writing · 2023–2026</title>'
           f'<style>{css(press, tune)}</style></head><body>{"".join(parts)}</body></html>')
    return htm, posts, figs

def base_plan():
    plan = ["title", "contents"]
    for y in PARTS:
        plan.append(("div", y))
        plan += [("essay", s) for s in C.SLUGS if C.Post(s, {}).year == y]
    return plan

class Renderer:
    def __enter__(self):
        from playwright.sync_api import sync_playwright
        self.pw = sync_playwright().start(); self.br = self.pw.chromium.launch(); self.pg = self.br.new_page(); return self
    def __exit__(self, *a): self.br.close(); self.pw.stop()
    def pdf(self, htm, pdf, name):
        hp = f"{B}/{name}.html"; open(hp, "w").write(htm)
        self.pg.goto("file://" + hp); self.pg.wait_for_load_state("networkidle"); self.pg.evaluate("document.fonts.ready")
        self.pg.pdf(path=pdf, prefer_css_page_size=True, print_background=True)

def probe(rr, plan, tune, fit, name="probe"):
    import fit as Ft
    htm, posts, figs = document(True, plan, {}, tune, fit, marks=True)
    pdf = f"{B}/{name}.pdf"; rr.pdf(htm, pdf, name)
    pages = Ft.read(pdf); sp = Ft.spans(pages)
    fbe = {s: p.figs for s, p in posts.items()}
    mode = {s: p.mode for s, p in posts.items()}
    return pages, sp, fbe, mode, posts

CANDS = [dict(), dict(ws=-.4), dict(ws=.4), dict(ls=-.006), dict(ls=.006), dict(fs=.88), dict(fs=.76),
         dict(ws=-.45, ls=-.005), dict(ws=.5, ls=.006), dict(ws=-.4, fs=.88), dict(fs=.66), dict(fs=.56),
         dict(ws=-.45, ls=-.005, fs=.66)]

def with_cand(tune, fit, c):
    t = {s: dict(tune.get(s, {})) for s in C.SLUGS}; f = dict(fit)
    for s in C.SLUGS:
        if c.get("ws"): t[s]["ws"] = c["ws"]
        if c.get("ls"): t[s]["ls"] = c["ls"]
        if c.get("fs"): f[f"*{s}"] = c["fs"]
    return t, f

def fix_holes(rr, plan, tune, fit, rounds=3):
    import fit as Ft
    for rnd in range(rounds):
        pages, sp, fbe, mode, posts = probe(rr, plan, tune, fit)
        fx, left = Ft.holes(pages, sp, fbe, mode, fit)
        hf = Ft.heads_at_foot(pages, sp, mode)
        for n, sl, t in [h for h in hf if mode[h[1]] == "one"]:
            fit[f"*{sl}"] = round(fit.get(f"*{sl}", 1) * 0.92, 3)
        hf = [h for h in hf if mode[h[1]] == "two"]
        for n, sl, t in hf:
            w = [x for x in t.split() if len(x) > 3][:1]
            if w: tune.setdefault(sl, {}).setdefault("brk", []).append(" ".join(w)) if " ".join(w) not in tune.get(sl, {}).get("brk", []) else None
        print(f"  holes {rnd}: {len(pages)} pp, {len(fx)} figure fixes, {len(left)} left, {len(hf)} heads at foot")
        for k, v in fx.items():
            if k.endswith("#defer"): fit[k] = fit.get(k, 0) + 1
            elif k.endswith("#col"): fit[k] = 1
            else: fit[k] = round(fit.get(k, 1) * v, 3)
        if not fx and not hf: break
    return pages, sp, fbe, mode, posts, left

def main():
    import fit as Ft
    plan = [it for it in base_plan() if it[0] == "essay"]          # essays alone: each starts a page
    st = f"{B}/fit.json"
    fit, tune = ({}, {}) if "--fresh" in sys.argv or not os.path.exists(st) else (lambda j: (j["fit"], j["tune"]))(json.load(open(st)))
    with Renderer() as rr:
        if "--fresh" in sys.argv or not os.path.exists(st):
            print("stage 1: holes"); fix_holes(rr, plan, tune, fit)
            print("stage 2: candidates")
            table = {}
            for c in CANDS:
                t, f = with_cand(tune, fit, c)
                pages, sp, fbe, mode, posts = probe(rr, plan, t, f)
                cs = Ft.cost(pages, sp, mode); lf = Ft.last_fill(pages, sp)
                for sl in C.SLUGS: table.setdefault(sl, []).append((cs[sl] + 0.02 * CANDS.index(c) + 0.8 * (1 - c.get("fs", 1)), c, lf[sl]))
                print("  cand", c, round(sum(cs.values()), 2), len(pages))
            for sl in C.SLUGS:
                best = min(table[sl], key=lambda r: r[0])
                base = table[sl][0]
                c = best[1]
                if c.get("ws"): tune.setdefault(sl, {})["ws"] = c["ws"]
                if c.get("ls"): tune.setdefault(sl, {})["ls"] = c["ls"]
                if c.get("fs"): fit[f"*{sl}"] = c["fs"]
                if c: print(f"  {sl}: {base[2]} -> {c} {best[2]}  cost {base[0]:.2f}->{best[0]:.2f}")
            print("stage 3: holes again"); fix_holes(rr, plan, tune, fit, 3)
            json.dump(dict(fit=fit, tune=tune), open(st, "w"), indent=1)
        print("stage 4: compose last pages")
        for s in C.SLUGS: tune.setdefault(s, {}).pop("coda_mt", None); tune[s].pop("body_mt", None)
        for rnd in range(2):
            pages, sp, fbe, mode, posts = probe(rr, plan, tune, fit)
            moved = False
            for s2, (a, z) in sp.items():
                its = Ft.items(pages[z - 1])
                if not its: continue
                first = min(its, key=lambda i: i["top"])
                if z > a and bool(C.Post(s2, fit).body_html()[1]) and "Semibold" in first.get("font", "") and first.get("size", 0) < 9 \
                        and not tune[s2].get("coda_inline"):
                    tune[s2]["coda_inline"] = True; moved = True; print("  coda inline:", s2)
            if not moved: break
            fix_holes(rr, plan, tune, fit, 2)
        pages, sp, fbe, mode, posts = probe(rr, plan, tune, fit)
        before = {s2: z - a + 1 for s2, (a, z) in sp.items()}
        for s2, (a, z) in sp.items():
            g = Ft.BOTY - max(i["bottom"] for i in Ft.items(pages[z - 1]))
            has_coda = bool(C.Post(s2, fit).body_html()[1]) and not tune[s2].get("coda_inline")
            if has_coda and g > 20: tune[s2]["coda_mt"] = round(g - 14, 1)
            elif a == z and g > 0.12 * TH and posts[s2].mode == "one": tune[s2]["body_mt"] = round(g - 14, 1)
        pages, sp, fbe, mode, posts = probe(rr, plan, tune, fit)
        for s2, (a, z) in sp.items():
            if z - a + 1 != before[s2]:
                print("  compose grew", s2, "- reverting"); tune[s2].pop("coda_mt", None); tune[s2].pop("body_mt", None)
        json.dump(dict(fit=fit, tune=tune), open(st, "w"), indent=1)
        pages, sp, fbe, mode, posts = probe(rr, plan, tune, fit)
        lf = Ft.last_fill(pages, sp)
        report = dict(stubs={k: v for k, v in lf.items() if v[0] > 1 and v[1] < 0.3},
                      widows=Ft.widows(pages, sp, mode), heads=Ft.heads_at_foot(pages, sp, mode),
                      holes=[g[:4] for g in Ft.gaps(pages, sp, mode) if g[3] > 0.12 * TH],
                      lengths={k: v[0] for k, v in lf.items()})
        json.dump(report, open(f"{B}/report.json", "w"), indent=1)
        print("stubs", report["stubs"]); print("widows", report["widows"]); print("heads", report["heads"]); print("holes", len(report["holes"]))

if __name__ == "__main__":
    main()
