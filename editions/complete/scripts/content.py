"""His posts, as HTML for the magazine. Verbatim: every element of each post's body_html is mapped
to a typeset element (heading levels, bold lines, lists and their nesting, quotes, verse, code),
never re-worded. Dropped is web furniture only: Substack's subscribe widget and buttons, the
"Thanks for reading my Substack" / "Link to this post" / "Or subscribe:" lines that sit on them,
and the hidden "Text within this block will maintain its original spacing" label.
"""
import datetime, html, json, os, re
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup, NavigableString, Tag

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S = f"{R}/src"
ORDER = json.load(open(f"{S}/order.json"))
SLUGS = [o["slug"] for o in ORDER]
IMGS = {(m["slug"], m["i"]): m for m in json.load(open(f"{S}/images.json"))}
EMB = json.load(open(f"{S}/embeds.json"))

# Posts up to and including September '25 open on a painting or film still with his own line under
# it naming the work. That line is his credit for it and is set as the plate's credit.
CAPTIONED = set(SLUGS[:SLUGS.index("september-25") + 1])

# Credits: bare source, nothing else, never "via". From each <img alt> (Substack keeps the title of
# the page he found it on) or what the image itself shows. Missing = no credit line.
CREDIT = {
    ("january-part-1", 1): "Monroe County (Pa.) Correctional Facility",
    ("january-part-1", 2): "Pan Macmillan",
    ("march", 1): "Real Python, “Image Segmentation Using Color Spaces in OpenCV + Python”",
    ("june", 0): None,
    ("june", 1): "NASA’s Goddard Space Flight Center / Jeremy Schnittman",
    ("july", 1): "Solar Schools, “Magnets and Electricity”",
    ("july", 2): "NASA CR-185163, “The Gevaltig,” 1989",
    ("july", 3): "Sci.News",
    ("july", 4): "Kip Thorne, The Science of Interstellar, 2014",
    ("october", 3): "“How Computers Store and Transmit Data”",
    ("october", 6): "Ex Machina, 2014",
    ("december", 1): "The Conversation, “Curious Kids: How does the Moon, being so far away, affect the tides on Earth?”",
    ("december", 2): "Astronomy.com, “Do black holes have bottoms?”",
    ("december", 3): "Wikipedia, “Spaghettification”",
    ("february-24", 1): "“Relativity”",
    ("march-24", 1): "Boston Dynamics",
    ("april-24", 1): "NASA, ESA and the Hubble Heritage Team, Pillars of Creation, 2014",
    ("april-24", 2): "“The Formation of White Dwarf Stars”",
    ("may-24", 2): "Past Lives, 2023",
    ("may-24", 3): "Ad Astra, 2019",
    ("may-24", 4): "Blade Runner 2049, 2017",
    ("august-24", 2): "NASA, Messier 106",
    ("april-25", 1): "Jean-Pierre Luminet, 1978",
    ("september-25", 1): "Jean Baudrillard, Simulacra and Simulation",
    ("oct-25", 3): "St. Peter’s, the Dome",
    ("oct-26-pt2", 3): "Francis Danby, The Deluge, exhibited 1840",
}
# The same painted strip ran in August '23 and again under the essay he re-shared in December '25.
# An issue never prints a work twice, so the second printing is left out (the essay text stays).
SKIP_IMG = {("dec-25", 5)}

URL = re.compile(r"(https?://\S+)")
# Substack keeps some emoji as shortcodes in body_html; the characters he typed, not the codes
BR_PARAS = {"short-stories", "dream-comet", "dream-oratory", "dream-a-higher-power"}
VERSE_PARAS = {"love-letters-to-some-girl-i-havent"}   # each <p> is a line of verse, set flush left
NUMBERED = {"short-stories"}   # h2 "One".."Six" number the stories; set at the sub-head level   # prose whose paragraphs Substack joined with <br><br>
EMOJI = {":eyes:": "👀", ":flame:": "🔥", ":rocket:": "🚀"}
# his recurring departments (2023, January '24): the h2s that group pieces rather than title one
DEPTS = {"The News", "Ideas", "Creative Riff", "Preface", "Journal"}
def esc(s): return html.escape(s, quote=False)

def inline(node):
    out = []
    for c in node.children:
        if isinstance(c, NavigableString):
            t = str(c)
            for k, v in EMOJI.items(): t = t.replace(k, v)
            t = esc(t); parts = URL.split(t)
            out.append("".join(f'<span class="url">{x}</span>' if URL.fullmatch(x) else re.sub(r"(?<=\w)/(?=\w)", "/<wbr>", x) for x in parts))
        elif c.name == "label": continue
        elif c.name in ("em", "i"): out.append(f"<em>{inline(c)}</em>")
        elif c.name in ("strong", "b"): out.append(f"<strong>{inline(c)}</strong>")
        elif c.name == "br": out.append("<br>")
        elif c.name == "a" and shows_url(c):
            h = RESOLVED.get(c["href"], c["href"])
            u = re.sub(r"[#?].*$", "", re.sub(r"^https?://(www\.)?", "", h)).rstrip("/")
            lab = inline(c)
            # "[LINK]" becomes the address itself; a title keeps its words, the address after them
            out.append(f'<span class="url">{esc(u)}</span>' if lab.strip().upper() == "LINK" else f'{lab} <span class="url">{esc(u)}</span>')
        else: out.append(inline(c))
    return "".join(out)

# A link whose words point somewhere ("here", "Article Link", a reading list of titles) leads to
# nothing on paper, so its address prints after it (Aidan, 2026-10-30: "page 274 needs urls! leads
# to nothing as it stands"). A name linked mid-sentence (an artist, a Wikipedia term) reads fine
# without one and stays as he wrote it.
# a newsletter's click-tracker resolved to the page it lands on (curl -IL, 2026-10-30)
RESOLVED = {"https://ben-evans.us6.list-manage.com/track/click?u=b98e2de85f03865f1d38de74f&id=30abb71520&e=0ddb081094":
            "https://www.aboutamazon.com/news/retail/amazon-shopping-app-buy-for-me-brands"}
POINTER = re.compile(r"^(here|link|article( link)?|full (story|article|interview|report)|source|read (it|more)|this|podcast( link)?|website|the report)$", re.I)
def shows_url(a):
    h = a.get("href", "")
    if not h.startswith("http") or a.find("img") or URL.fullmatch(a.get_text("").strip()): return False
    if "substack.com/subscribe" in h or "substack.com/app" in h: return False
    # art never gets an address, only outside reading does (Aidan, 2026-10-30): photographers'
    # pages, and a credit line under a picture ("Shot By: …", "Reference: NASA")
    if re.search(r"lomography\.com|instagram\.com|flickr\.com|artsy\.net", h): return False
    prev = a.previous_sibling
    if isinstance(prev, str) and re.search(r"(shot by|reference|credit|via|photo|image)\s*:?\s*$", prev, re.I): return False
    t = re.sub(r"\s+", " ", a.get_text(" ")).strip()
    if not t: return False
    if POINTER.match(t.strip(".:!—- ")): return True
    prev = a.previous_sibling
    if isinstance(prev, str) and re.search(r"(→|->|:)\s*$", prev): return True     # "the whole poem → Poetry Foundation: …"
    blk = a.find_parent(["p", "li"])
    if blk is None or blk.find_parent("figcaption"): return False
    own = re.sub(r"\s+", " ", "".join(x if isinstance(x, str) else x.get_text(" ") for x in blk.contents if getattr(x, "name", None) not in ("ul", "ol"))).strip()
    rest = own.replace(t, "", 1)
    rest = re.sub(r"\[?link\]?|by\b.*|[\s\-–—:→>.,()\[\]]", "", rest, flags=re.I)
    return rest == ""

def text(el): return el.get_text(" ", strip=True)

CTA = re.compile(r"^(Thanks for reading my Substack|Link to this post:|Or subscribe|Or:$|Feel free to:?$)")
def is_cta(el):
    if not isinstance(el, Tag): return False
    cl = el.get("class") or []
    if "button-wrapper" in cl or "subscription-widget-wrap-editor" in cl: return True
    return el.name == "p" and bool(CTA.match(text(el)))

def post_date(d):
    t = datetime.datetime.fromisoformat(d["post_date"].replace("Z", "+00:00")).astimezone(ZoneInfo("America/Chicago"))
    return t, f"{t.strftime('%B')} {t.day}, {t.year}"

def typeset_title(t):
    t = re.sub(r"'(\d\d)\b", "’\\1", t.strip())        # the year's apostrophe, as a typesetter would
    return t.replace("‘25", "’25")                       # his February '25 title has a left quote for it

class Post:
    def __init__(self, slug, fit):
        d = json.load(open(f"{S}/posts/{slug}.json")); self.d = d
        self.slug = slug; self.fit = fit                 # fit: dict of per-figure scale overrides
        self.title = typeset_title(d["title"]); self.sub = (d.get("subtitle") or "").strip()
        self.dt, self.date = post_date(d); self.year = self.dt.year
        # 2023-24 are long monthly letters, set in two columns; from 2025 the posts are notes and
        # photographs, set in one column with the pictures at full measure
        self.mode = "two"
        self.soup = BeautifulSoup(d["body_html"], "html.parser")
        self.top = [e for e in self.soup.children if isinstance(e, Tag) and not is_cta(e)]
        while self.top and self.top[-1].name == "p" and not self.top[-1].get_text(strip=True): self.top.pop()
        names = {e.name for e in self.soup.find_all(["h2", "h3", "h4", "h5"])}
        # Heading levels as he used them. Where a post has h2 over h3/h4, the h2s are departments
        # (The News, Ideas, Some Literature) and the h3/h4 are its pieces; otherwise his h2 (or h3)
        # is the piece's own title.
        h2s = {text(h) for h in self.soup.find_all("h2")}
        self.dept_level = "h2" if h2s & DEPTS and self.year <= 2024 else None
        self.imgn = 0; self.embn = 0; self.figs = []; self.sec = ""
        self.plate, self.plate_cap, self.body_els = self.split()
        # A post that is mostly photographs (under ~110 words a picture) is set as a photo essay:
        # one column, the pictures at full measure. Everything else runs in two columns.
        nimg = len(self.soup.find_all("img"))
        if nimg and len(self.soup.get_text(" ").split()) / nimg < 110: self.mode = "one"

    # ------------------------------------------------------------------ opener
    def split(self):
        els = list(self.top); plate = None; cap = []
        if els and els[0].find("img") and els[0].name == "div":
            plate = els.pop(0)
            if self.slug in CAPTIONED:
                while els and els[0].name == "p" and len(text(els[0])) < 220:
                    cap.append(els.pop(0))
        return plate, cap, els

    def figure(self, el, role="body"):
        out = []
        for img in el.find_all("img"):
            i = self.imgn; self.imgn += 1
            if (self.slug, i) in SKIP_IMG: continue
            m = IMGS[(self.slug, i)]
            fc = el.find("figcaption"); fc = fc.get_text(" ", strip=True) if fc else ""
            cred = CREDIT.get((self.slug, i), "")
            out.append(self.fig(m, f"{self.slug}-{i:02d}", cred or "", fc, role))
        return "".join(out)

    def fig(self, m, fid, credit, cap, role, embed=False):
        w, h = m["w"], m["h"]; ar = w / h
        flat = m["file"].endswith(".png") and not embed
        nat = w * 72 / 200                                   # widest it prints at 200 ppi
        strip = ar > 3
        if role == "plate": kind = "plate"
        elif self.mode == "one": kind = "strip" if strip else "full"
        elif strip or self.sec == "Some Literature" or self.fit.get(fid + "#col"): kind = "col"
        elif ar >= 1.15 and min(502, nat, 380 * ar) >= 400: kind = "span"     # a spanner earns the full width
        else: kind = "col"
        maxw = {"plate": 502, "strip": 392, "span": 502, "col": 241, "full": 502}[kind]
        maxh = {"plate": 330, "strip": 120, "span": 380, "col": 380, "full": 400}[kind]
        if embed and ar < 1.3: maxw = min(maxw, 160)
        sc = self.fit.get(fid, 1) * self.fit.get(f"*{self.slug}", 1)
        fw = min(maxw, nat); fh = fw / ar
        if fh > maxh: fh = maxh; fw = fh * ar
        fw *= sc; fh *= sc
        ppi = w / (fw / 72)
        self.figs.append(dict(id=fid, ppi=round(ppi), w=round(fw, 1), h=round(fh, 1), kind=kind, px=(w, h)))
        cr = f'<figcaption class="credit">{esc(credit)}</figcaption>' if credit else ""
        cp = f'<figcaption class="cap">{esc(cap)}</figcaption>' if cap else ""
        src = f"file://{R}/{m['file']}"
        return (f'<figure class="fig {kind}" id="{fid}" data-h="{fh:.1f}"><div class="im" style="width:{fw:.2f}pt">'
                f'<img src="{src}" style="width:{fw:.2f}pt;height:{fh:.2f}pt">{cp or cr}</div></figure>')

    def plate_html(self):
        if self.plate is None: return ""
        if self.plate.find("img") is None: return ""
        i = self.imgn; self.imgn += 1; m = IMGS[(self.slug, i)]
        fc = self.plate.find("figcaption"); fc = fc.get_text(" ", strip=True) if fc else ""
        lines = "".join(f"<span>{inline(p)}</span>" for p in self.plate_cap)
        h = self.fig(m, f"{self.slug}-{i:02d}", "", "", "plate")
        cred = lines or (esc(fc) if fc else "")
        if cred: h = h.replace("</div></figure>", f'<figcaption class="credit pc">{cred}</figcaption></div></figure>')
        return h

    # ------------------------------------------------------------------ body blocks
    def pre(self, el):
        t = el.get_text()
        t = t.replace(" ", " ")
        if not t.strip(): return ""
        if re.search(r"^\s*##\s*\S.*##\s*$", t, re.M) and self.sec not in ("Creative Riff", "Riff"):
            # his collected poems in one block: each "## TITLE ##" line titles the poem under it
            out = []
            for m in re.finditer(r"^\s*##\s*(.+?)\s*##[ \t]*\n(.*?)(?=^\s*##\s*\S.*##\s*$|\Z)", t, re.M | re.S):
                body = [l.rstrip() for l in m.group(2).strip("\n").split("\n")]
                while body and not body[-1].strip(): body.pop()
                body = self.unspace(body)
                out.append(f'<h3 class="item">{esc(m.group(1))}</h3><div class="lit verse poem"><div class="lt">{esc(chr(10).join(body))}</div></div>')
            return "".join(out)
        if re.fullmatch(r"[\s01HELOI\-]+", t) or "{" in t:
            return f'<pre class="code">{esc(t.rstrip())}</pre>'
        if self.sec in ("Creative Riff", "Riff"):
            parts, out = [x for x in re.split(r"\n\s*\n", t.strip("\n")) if x.strip()], []
            first = True
            for x in parts:
                m = re.fullmatch(r"\s*##\s*(.+?)\s*##\s*", x)
                if m: out.append(f'<h3 class="item riffhead">{esc(m.group(1))}</h3>'); first = True; continue
                out.append(f'<p class="riff{" first" if first else ""}">{esc(x.strip())}</p>'); first = False
            return "".join(out)
        lines = t.strip("\n").split("\n")
        k = next((i for i, l in enumerate(lines) if i > 0 and re.match(r"\s*(-|—|―|- )\s*\S", l) and len(l) < 70), None)
        body, att = (lines[:k], lines[k:]) if k is not None else (lines, [])
        while body and not body[-1].strip(): body.pop()
        if body and body[-1].strip() == "---": body.pop()
        while body and not body[-1].strip(): body.pop()
        nonempty = [l for l in body if l.strip()]
        verse = sum(len(l) for l in nonempty) / max(1, len(nonempty)) < 72 and len(nonempty) > 1
        # his blank line between verse lines is how Substack spaced them; a stanza break is two
        if verse: body = self.unspace(body)
        a = "".join(f'<div class="att">{esc(l.strip())}</div>' for l in att if l.strip())
        bt = esc("\n".join(body))
        if not verse:
            bt = "".join(f"<p>{esc(x.strip())}</p>" for x in re.split(r"\n\s*\n", "\n".join(body)) if x.strip())
        return f'<div class="lit {"verse" if verse else "prose"}"><div class="lt">{bt}</div>{a}</div>'

    @staticmethod
    def unspace(lines):
        """Substack's code block double-spaces verse typed line by line: every line is followed by
        a blank one, and a stanza break is two or more. One blank = a line break, more = a stanza.
        Verse typed without those blanks keeps its spacing exactly."""
        gaps, blank, seen = [], 0, False
        for l in lines:
            if l.strip():
                if seen: gaps.append(blank)
                seen = True; blank = 0
            else: blank += 1
        if not gaps or min(gaps) == 0: return [l.rstrip() for l in lines]
        out, blank = [], 0
        for l in lines:
            if l.strip():
                if out and blank >= 2: out.append("")
                out.append(l.rstrip()); blank = 0
            else: blank += 1
        return out

    def lst(self, el):
        items = []
        for li in el.find_all("li", recursive=False):
            parts = []
            for c in li.children:
                if isinstance(c, Tag) and c.name in ("ol", "ul"): parts.append(self.lst(c))
                elif isinstance(c, Tag) and c.name == "p": parts.append(f"<span class='lp'>{inline(c)}</span>")
                elif isinstance(c, Tag): parts.append(inline(c))
                elif str(c).strip(): parts.append(esc(str(c)))
            items.append(f"<li>{''.join(parts)}</li>")
        return f"<{el.name}>{''.join(items)}</{el.name}>"

    def heading(self, el):
        n = el.name; t = inline(el).strip()
        if not text(el): return ""
        if self.slug in NUMBERED and n == "h2":      # his numbered parts (One, Two ...) as sub-heads
            return f'<h4 class="sub">{t}</h4>'
        if self.slug == "oct-26-pt2":           # his collage of display lines: the heading sizes are the poem
            return f'<p class="disp {n}">{t}</p>'
        if n == "h1": n = "h2"
        if n == "h2":
            self.sec = text(el)
            if self.dept_level == "h2" or self.sec in ("Some Literature",):
                return f'<h2 class="dept">{t}</h2>'
            return f'<h3 class="item">{t}</h3>'
        if n in ("h3", "h4"):
            if self.dept_level: return f'<h3 class="item">{t}</h3>' if n == "h3" or "h3" not in {x.name for x in self.soup.find_all("h3")} else f'<h4 class="sub">{t}</h4>'
            if n == "h3": return f'<h3 class="item{" long" if len(text(el)) > 90 else ""}">{t}</h3>'
            return f'<h4 class="sub">{t}</h4>'
        return f'<h4 class="sub">{t}</h4>'

    def block(self, el):
        n, cl = el.name, el.get("class") or []
        if is_cta(el): return ""
        if n in ("h1", "h2", "h3", "h4", "h5"): return self.heading(el)
        if n == "p":
            if not el.get_text(strip=True) and not el.find("img"): return ""
            if el.find("img"): return self.figure(el)
            bold = "".join(x.get_text() for x in el.find_all(["strong", "b"]) if not x.find_parent(["strong", "b"]))
            if bold.strip() and bold.strip() == el.get_text().strip():
                return f'<p class="bold">{inline(el)}</p>'
            c = ' class="hasurl"' if URL.search(el.get_text()) else ""
            h = inline(el)
            if self.slug in BR_PARAS and "<br><br>" in h:
                # his paragraph break typed as a blank line inside one paragraph: set as paragraphs
                return "".join(f"<p{c}>{x.strip()}</p>" for x in h.split("<br><br>") if x.strip())
            if self.slug in VERSE_PARAS: return f'<p class="vl">{h}</p>'
            return f"<p{c}>{h}</p>"
        if n in ("ol", "ul"): return self.lst(el)
        if n == "blockquote":
            if el.find("pre"):
                return "".join(self.block(c) for c in el.find_all(recursive=False) if isinstance(c, Tag))
            if el.find("p"):
                return '<blockquote>' + "".join(self.block(c) or "" for c in el.find_all(recursive=False)) + "</blockquote>"
            return f"<blockquote><p>{inline(el)}</p></blockquote>"
        if "pullquote" in cl:
            ps = el.find_all("p") or [el]
            return '<blockquote class="pull">' + "".join(f'<p>{inline(p).strip()}</p>' for p in ps) + "</blockquote>"
        if "preformatted-block" in cl or "highlighted_code_block" in cl: return self.pre(el.find("pre"))
        if n == "pre": return self.pre(el)
        if "youtube-wrap" in cl or (n == "iframe" and "spotify-wrap" in cl):
            k = f"{self.slug}-e{self.embn}"; self.embn += 1; e = EMB[k]
            return self.fig(e, k, e["credit"], "", "body", embed=True)
        if el.find("img"): return self.figure(el)
        if el.find("hr") or n == "hr": return '<div class="brk"></div>'
        if n == "div" and not el.get_text(strip=True): return ""
        raise SystemExit(f"unhandled {self.slug}: {str(el)[:200]}")

    def body_html(self):
        bl = [self.block(e) for e in self.body_els]
        bl = [x for x in bl if x]
        bl = [x for k, x in enumerate(bl) if not (x == '<div class="brk"></div>' and k and bl[k - 1] == x)]  # his doubled rule: one break
        # a figure too tall for the hole above it may follow the next paragraph instead: still after
        # the passage it belongs to, never before it
        k = 0
        while k < len(bl) - 1:
            m = re.match(r'<figure class="fig \w+" id="([^"]+)"', bl[k])
            n = self.fit.get(m.group(1) + "#defer", 0) if m else 0
            j = k
            while n and j < len(bl) - 1 and bl[j + 1].startswith("<p") and 'class="disp' not in bl[j + 1]:
                bl[j], bl[j + 1] = bl[j + 1], bl[j]; j += 1; n -= 1
            k = j + 1
        # the department that closes most issues (Some Literature) is the coda: it spans the page
        out, coda = [], None
        for i, b in enumerate(bl):
            if coda is None and b.startswith('<h2 class="dept">Some Literature') and i >= len(bl) - 8:
                coda = i
        if coda is not None:
            main, tail = bl[:coda], bl[coda:]
        else:
            main, tail = bl, []
        return main, tail

    def words(self):
        return len(self.soup.get_text(" ").split())
