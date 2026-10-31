#!/usr/bin/env python3
"""Pull every post of the Periodicals newsletter (aidanjude.substack.com ONLY, never randomaidan or
visionboards) and every image in it at the original upload resolution.

Archive: /api/v1/archive?sort=new&offset=N&limit=50, advancing by rows returned until a page comes
back empty (a page caps near 24 rows). Bodies: /api/v1/posts/<slug>. Sequential, one request at a
time: parallel paging draws HTTP 429 (2026-10-28). Falls back to the writing-topology html cache.

  python3 scripts/fetch.py      -> src/archive.json, src/posts/<slug>.json, src/orig/, src/img/, src/images.json
"""
import json, os, re, subprocess, time, urllib.parse
from PIL import Image, ImageOps
from bs4 import BeautifulSoup

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); S = f"{R}/src"
for d in ("posts", "img", "orig"): os.makedirs(f"{S}/{d}", exist_ok=True)
HOST = "https://aidanjude.substack.com"
CACHE = os.path.expanduser("~/Desktop/writing-topology/data/personal_corpus/cache/substack_html")
CORPUS = os.path.expanduser("~/Desktop/writing-topology/data/personal_corpus/substack_all.json")

def get(u, tries=6):
    code = "?"
    for k in range(tries):
        r = subprocess.run(["curl", "-sL", "-A", "Mozilla/5.0", "-w", "\n%{http_code}", u], capture_output=True, text=True).stdout
        body, code = r.rsplit("\n", 1)
        if code == "200": return body
        time.sleep(5 * (k + 1))
    raise RuntimeError(f"{code} {u}")

if not os.path.exists(f"{S}/archive.json"):
    rows, off = [], 0
    while True:
        d = json.loads(get(f"{HOST}/api/v1/archive?sort=new&offset={off}&limit=50"))
        if not d: break
        rows += d; off += len(d); time.sleep(1.5)
    json.dump(rows, open(f"{S}/archive.json", "w"))
rows = json.load(open(f"{S}/archive.json"))
posts = sorted({p["slug"]: p for p in rows if p.get("type", "newsletter") == "newsletter"}.values(), key=lambda p: p["post_date"])
posts = [p for p in posts if p["slug"] != "goodreads"]     # a page, not a post
nper = len(posts)

# Pieces from his other newsletter that he chose for this book (Aidan, 2026-10-30 and 10-31), placed in
# date order inside 2026. Only these, by name; nothing else from randomaidan ever goes in.
EXTRA_HOST = "https://randomaidan.substack.com"
EXTRA = ["short-stories", "collected-poems", "love-letters-to-some-girl-i-havent",
         "dream-comet", "dream-oratory", "dream-a-higher-power"]      # the three dreams added 10/31
for slug in EXTRA:
    fn = f"{S}/posts/{slug}.json"
    if not (os.path.exists(fn) and os.path.getsize(fn) > 100):
        open(fn, "w").write(get(f"{EXTRA_HOST}/api/v1/posts/{slug}")); time.sleep(1.5)
    d = json.load(open(fn)); posts.append(dict(slug=slug, post_date=d["post_date"], title=d["title"]))
posts.sort(key=lambda p: p["post_date"])

# reconcile with the corpus (aidanjude.substack.com rows only)
cor = [c for c in json.load(open(CORPUS)) if "aidanjude.substack.com" in c["url"]]
cs = {c["url"].rstrip("/").rsplit("/", 1)[1] for c in cor}; ps = {p["slug"] for p in posts} - set(EXTRA)
print(f"archive {nper} posts + {len(EXTRA)} chosen from randomaidan | corpus {len(cor)} | only archive {sorted(ps - cs)} | only corpus {sorted(cs - ps)}")
from collections import Counter
print(dict(sorted(Counter(p["post_date"][:4] for p in posts).items())))

for p in posts:
    fn = f"{S}/posts/{p['slug']}.json"
    if os.path.exists(fn) and os.path.getsize(fn) > 100: continue
    try:
        open(fn, "w").write(get(f"{HOST}/api/v1/posts/{p['slug']}")); time.sleep(1.5)
    except RuntimeError as e:
        print("API failed, using cache:", e)
        h = BeautifulSoup(open(f"{CACHE}/{p['slug']}.html").read(), "html.parser")
        body = h.select_one(".body.markup") or h.select_one(".available-content")
        json.dump(dict(p, body_html=str(body)), open(fn, "w"))

man = []
for p in posts:
    d = json.load(open(f"{S}/posts/{p['slug']}.json")); b = BeautifulSoup(d["body_html"], "html.parser")
    for i, im in enumerate(b.find_all("img")):
        a = json.loads(im.get("data-attrs") or "{}") if im.get("data-attrs") else {}
        m = re.search(r"(https%3A%2F%2Fsubstack-post-media.*)$", im["src"])
        orig = a.get("src") or (urllib.parse.unquote(m.group(1)) if m else im["src"])
        raw = f"{S}/orig/{p['slug']}-{i:02d}"
        if not os.path.exists(raw) or os.path.getsize(raw) == 0:
            subprocess.run(["curl", "-sL", "--retry", "3", "-o", raw, orig], check=True)
            if os.path.getsize(raw) < 500: subprocess.run(["curl", "-sL", "-o", raw, im["src"]], check=True)
        x = Image.open(raw); fmt = x.format; x.seek(0)          # animated GIFs print their first frame
        if fmt in ("JPEG", "MPO"): x = ImageOps.exif_transpose(x)  # phone photos carry an orientation tag
        if max(x.size) > 2800: x.thumbnail((2800, 2800), Image.LANCZOS)  # still >300 ppi at any size it prints
        line = fmt in ("PNG", "GIF")                              # screenshots stay lossless
        x = x.convert("RGBA"); bg = Image.new("RGBA", x.size, "white"); bg.alpha_composite(x); x = bg.convert("RGB")
        out = f"{S}/img/{p['slug']}-{i:02d}." + ("png" if line else "jpg")
        x.save(out, quality=94) if out.endswith("jpg") else x.save(out)
        man.append(dict(slug=p["slug"], i=i, file=os.path.relpath(out, R), orig=orig, alt=(im.get("alt") or "").strip(),
                        w=x.size[0], h=x.size[1], fmt=fmt))
json.dump(man, open(f"{S}/images.json", "w"), indent=1)
json.dump([dict(slug=p["slug"], date=p["post_date"], title=p["title"]) for p in posts], open(f"{S}/order.json", "w"), indent=1)
print(len(posts), "posts", len(man), "images")

# embeds print as the still the post showed (YouTube thumbnail, Spotify art), credited bare
emb = {}
for p in posts:
    b = BeautifulSoup(json.load(open(f"{S}/posts/{p['slug']}.json"))["body_html"], "html.parser")
    for k, x in enumerate(b.select("div.youtube-wrap, iframe.spotify-wrap, div.spotify-wrap")):
        a = json.loads(x.get("data-attrs") or "{}"); key = f"{p['slug']}-e{k}"; out = f"{S}/img/{key}.jpg"
        if "videoId" in a:
            o = json.loads(get(f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={a['videoId']}&format=json"))
            url = f"https://i.ytimg.com/vi/{a['videoId']}/maxresdefault.jpg"; cred = f"{o['author_name']}, “{o['title']}”"
        else: url = a.get("image"); cred = f"{a.get('subtitle','')}, “{a.get('title','')}”".strip(", ")
        if not os.path.exists(out): subprocess.run(["curl", "-sL", "-o", out, url], check=True)
        w, h = Image.open(out).size; emb[key] = dict(file=os.path.relpath(out, R), w=w, h=h, credit=cred)
json.dump(emb, open(f"{S}/embeds.json", "w"), indent=1); print(len(emb), "embeds")
