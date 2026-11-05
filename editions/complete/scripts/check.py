#!/usr/bin/env python3
"""Press checks on the built PDFs. Exit 1 on any failure.

  - interior a multiple of 4; TrimBox inset 9 pt and BleedBox = MediaBox (press), trim only (FedEx)
  - every font embedded
  - no image printed twice; every image's effective ppi (flag < 200)
  - no text inside the outer 0.25 in of the trim (bleed pages excepted: they carry no text there)
  - body exactly 152 pages; inner covers one page each, no folio
  - all 57 pieces present (51 Periodicals posts + the 6 randomaidan pieces he chose), in date order, each opening on its own page under its own title
  - no other text from randomaidan.substack.com or visionboards (8-word shingles against the corpus);
    only ALLOWED, by slug, may come from randomaidan
  - every word he wrote is in the book: body + inner back cover (token multiset of each post vs the PDFs)
  - the contents on the inner front cover gives every piece its opener page
"""
import hashlib, json, os, re, subprocess, sys
from collections import Counter
import pdfplumber
from pypdf import PdfReader
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build as Bd, content as C
from bs4 import BeautifulSoup

R = Bd.R; bad = []
pj = json.load(open(f"{Bd.B}/press.json"))
INT, CV = pj["out"]["interior"], pj["out"]["cover"]
IF, IB = pj["out"]["inner_front"], pj["out"]["inner_back"]

def check_boxes(f, bl, w, h):
    r = PdfReader(f)
    for i, p in enumerate(r.pages):
        mb, tb, bb = [[round(float(v), 2) for v in x] for x in (p.mediabox, p.trimbox, p.bleedbox)]
        # Chromium rounds the page size by up to ~0.3 pt (the cover's computed spine); 0.5 pt = 0.007 in
        near = lambda a, b: all(abs(x - y) <= 0.5 for x, y in zip(a, b))
        if not near(mb, [0, 0, w + 2 * bl, h + 2 * bl]) or not near(tb, [bl, bl, w + bl, h + bl]) or bb != mb:
            bad.append(f"{os.path.basename(f)} p{i+1}: boxes media {mb} trim {tb} bleed {bb}"); break
    return len(r.pages)

n = check_boxes(INT, 9, 612, 792)
if n % 4: bad.append(f"interior: {n} pages, not a multiple of 4")
if n != 152: bad.append(f"interior: {n} pages, his Mixam cart is set to 152")
for f in (IF, IB):
    if check_boxes(f, 9, 612, 792) != 1: bad.append(f"{os.path.basename(f)}: not one page")

sw = 2 * 612 + pj["spine_in"] * 72
check_boxes(CV, 9, sw, 792)
print(f"interior {n} pp (multiple of 4: {n % 4 == 0}); cover spread {sw/72:.3f} x 11 in trim, spine {pj['spine_in']:.2f} in")

for f in (INT, CV, IF, IB):
    rows = subprocess.run(["pdffonts", f], capture_output=True, text=True).stdout.splitlines()[2:]
    ne = [l for l in rows if l.split()[-5] != "yes"]
    names = sorted({l.split()[0].split("+")[-1] for l in rows})
    if ne: bad.append(f"{os.path.basename(f)}: fonts not embedded {ne}")
    print(os.path.basename(f), "fonts:", ", ".join(names))

kinds = pj["kinds"]
hs, low, ppis = [], [], []
texts, reading = [], []
def proc(i, pg, k, label):
        for im in pg.images:
            hs.append((hashlib.md5(im["stream"].get_data()).hexdigest(), label))
            ppi = im["srcsize"][0] / ((im["x1"] - im["x0"]) / 72); ppis.append(ppi)
            if ppi < 199.5: low.append((label, round(ppi)))
        if k != "div":
            for c in pg.chars:
                if c["size"] < 1.5: continue
                if c["x0"] < 27 or c["x1"] > pg.width - 27 or c["top"] < 27 or c["bottom"] > pg.height - 27:
                    bad.append(f"{label}: text in the outer 0.25 in: {c['text']!r}"); break
        txt = (pg.extract_text() or "").replace("ʼ", "’")
        if k != "innerfront": texts.append(txt)
        if k in ("innerfront", "innerback") and re.search(r"(?m)^\s*\d{1,3}\s*$", "\n".join(l for l in txt.split("\n")[-2:])) and k == "innerback":
            bad.append(f"{label}: carries a folio")
        if k == "innerfront": return txt
        # words in reading order: column by column, a line-end hyphen rejoined with the next line
        mid = pg.width / 2 + ((48 - 62) / 2 if (i + 1) % 2 == 0 else (62 - 48) / 2)
        ws = [w for w in pg.extract_words(keep_blank_chars=False) if w["bottom"] - w["top"] > 1.5 and 60 < w["top"] < pg.height - 60]
        ws.sort(key=lambda w: (0 if w["x0"] < mid else 1, round(w["top"]), w["x0"]))
        out = reading
        for w in ws:
            t = w["text"].replace("ʼ", "’")
            if out and re.search(r"[A-Za-z][-‐]$", out[-1]) and re.match(r"[a-z]", t): out[-1] = out[-1][:-1] + "\u0001" + t
            else: out.append(t)
with pdfplumber.open(INT) as d:
    for i, pg in enumerate(d.pages): proc(i, pg, kinds[i][0], f"p{i+1}")
with pdfplumber.open(IB) as d: proc(152, d.pages[0], "innerback", "inner back")    # a right-hand page
with pdfplumber.open(IF) as d: contents_txt = proc(1, d.pages[0], "innerfront", "inner front")

cnt = Counter(h for h, _ in hs); dup = [(h[:8], [p for hh, p in hs if hh == h]) for h, c in cnt.items() if c > 1]
if dup: bad.append(f"repeated images: {dup}")
print(f"images {len(hs)} drawn, {len(dup)} repeated; ppi min {min(ppis):.0f}, median {sorted(ppis)[len(ppis)//2]:.0f}; under 200: {low}")
if low: bad.append(f"{len(low)} images under 200 ppi")

# every post, in order, on its own opener page
plan = pj["plan"]; toc = pj["toc"]
order = [it[1] for it in plan if isinstance(it, list) and it[0] == "essay"]
if order != C.SLUGS: bad.append("essay order differs from post order")
dates = [C.Post(s, {}).dt for s in order]
if dates != sorted(dates): bad.append("posts not chronological")
miss = []
for s in order:
    t = C.Post(s, {}).title
    pgt = texts[toc[s] - 1].replace("\n", " ")
    if re.sub(r"\s+", "", t) not in re.sub(r"\s+", "", pgt): miss.append((s, toc[s]))
if miss: bad.append(f"titles not found on their opener pages: {miss}")
flat_toc = re.sub(r"\s+", "", contents_txt.replace("ʼ", "’"))
wrong = [s for s in order if re.sub(r"\s+", "", C.Post(s, {}).title) + str(toc[s]) not in flat_toc]
if wrong: bad.append(f"contents page numbers wrong or missing: {wrong}")
print(f"contents (inner front): {len(order) - len(wrong)}/{len(order)} titles with their page numbers")
print(f"posts: {len(order)} in the book, {len(set(order))} distinct, chronological {dates == sorted(dates)}, openers found {len(order) - len(miss)}/{len(order)}")

# nothing from randomaidan or visionboards
cor = json.load(open(os.path.expanduser("~/Desktop/workspace/writing-topology/data/personal_corpus/substack_all.json")))
ALLOWED = {"short-stories", "collected-poems", "love-letters-to-some-girl-i-havent",   # Aidan, 2026-10-30
           "dream-comet", "dream-oratory", "dream-a-higher-power"}                       # and 2026-10-31
foreign = [c for c in cor if "aidanjude.substack.com" not in c["url"] and c["url"].rstrip("/").rsplit("/", 1)[1] not in ALLOWED]
assert len(C.SLUGS) == 57 and ALLOWED <= set(C.SLUGS), len(C.SLUGS)
if set(C.SLUGS) - ALLOWED - {c["url"].rstrip("/").rsplit("/", 1)[1] for c in cor if "aidanjude.substack.com" in c["url"]}:
    bad.append("a piece that is neither a Periodicals post nor an allowed randomaidan piece")
tok = lambda t: re.findall(r"[a-z0-9’']+", t.lower().replace("’", "'"))
book = tok(" ".join(texts).replace("-\n", ""))
ours = set()
for s in C.SLUGS: ours |= {" ".join(tok(C.Post(s, {}).soup.get_text(" "))[k:k + 8]) for k in range(0, 4000)}
sh = {" ".join(book[k:k + 8]) for k in range(len(book) - 8)}
hits = 0; hit_posts = []
for c in foreign:
    ft = tok(BeautifulSoup(c.get("body") or "", "html.parser").get_text(" "))
    fs = {" ".join(ft[k:k + 8]) for k in range(len(ft) - 8)} - ours
    h = len(fs & sh)
    if h: hits += h; hit_posts.append((c["url"].split("/")[2], c["title"][:30], h))
print(f"foreign text: {len(foreign)} randomaidan/visionboards posts checked, {hits} shared 8-word runs {hit_posts[:5]}")
if hits: bad.append(f"text shared with other newsletters: {hit_posts[:5]}")
# his reading list (Oct 26) links to his own posts there; the address may print, his other writing may not
def _foreign(t):
    # pdfplumber interleaves two columns, so a wrapped address arrives in pieces: count its head only
    t = re.sub(r"randomaidan\.(s(u(b(s(t(a(c(k)?)?)?)?)?)?)?)?", "", re.sub(r"\s", "", t))
    return "randomaidan" in t or "visionboard" in t.lower()
if any(_foreign(t) for t in texts): bad.append("a page names randomaidan / visionboards")

# verbatim: every word of every post (minus web furniture) is in the book
src = Counter()
for s in C.SLUGS:
    p = C.Post(s, {})
    for el in p.top:
        for lab in el.find_all("label"): lab.decompose()
        t = el.get_text(" ")
        for k, v in C.EMOJI.items(): t = t.replace(k, v)      # shortcodes print as the emoji he typed
        for a in el.find_all("a"):                           # "[LINK]" prints as its address (content.shows_url)
            if C.shows_url(a) and a.get_text("").strip().upper() == "LINK": t = t.replace(a.get_text(" "), " ", 1)
        src.update(re.findall(r"[A-Za-z0-9]+", t))
    src.update(re.findall(r"[A-Za-z0-9]+", p.title)); src.update(re.findall(r"[A-Za-z0-9]+", p.sub))
full = " ".join(reading).lower()
src = Counter({k.lower(): 0 for k in src}) + Counter(k.lower() for k in src.elements())
got = (Counter(re.findall(r"[a-z0-9]+", full.replace("\u0001", ""))) | Counter(re.findall(r"[a-z0-9]+", full.replace("\u0001", "-")))) + Counter(re.findall(r"[A-Za-z0-9]+", re.sub(r"(?<=[\w/.-]) (?=[\w./-])", "", " ".join(re.findall(r"\S*https?://\S*|\S+/\S+", full.replace("\u0001", ""))))))
missing = {k: v - got[k] for k, v in src.items() if got[k] < v}
# a word hyphenated across a column or page boundary whose halves are not adjacent in reading order
frags = Counter(re.findall(r"([a-z]+)[-‐](?:\s|$)", full.replace("\u0001", "- ")))
tails = Counter(re.findall(r"[a-z]+", full))
for k in list(missing):
    if any(frags[k[:j]] and tails[k[j:]] for j in range(2, len(k) - 1)): del missing[k]
# inside a URL set with break-all, a word can wrap anywhere: look for it with line breaks removed
flat = re.sub(r"[\s\u0001]+", "", full)
for k in list(missing):
    if flat.count(k) >= src[k]: del missing[k]
# the left-out repeat of the August '23 strip carries no words; anything missing is real
print(f"verbatim: {sum(src.values())} source words, {sum(missing.values())} missing {dict(list(missing.items())[:20])}")
if sum(missing.values()) > 0: bad.append(f"missing words {dict(list(missing.items())[:20])}")

print("\n".join("FAIL " + x for x in bad) or "all checks pass"); sys.exit(1 if bad else 0)
