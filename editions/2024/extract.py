#!/usr/bin/env python3
"""Freeze the 2024 Periodicals posts (aidanjude.substack.com only) into content.json.

Text is carried verbatim: inline italic/bold/links are kept as markup, nothing is reworded.
Dropped: Substack's own widgets only (Subscribe/Share buttons, image-expand chrome).
Run: python3 extract.py            (fetches anything missing, then writes content.json)
"""
import json, os, re, time, urllib.parse, urllib.request
from bs4 import BeautifulSoup, NavigableString, Tag
from PIL import Image

D = os.path.dirname(os.path.abspath(__file__))
SRC = f"{D}/src"
UA = {"User-Agent": "Mozilla/5.0"}
YEAR = "2024"


def get(u):
    for t in range(5):
        try:
            return json.load(urllib.request.urlopen(urllib.request.Request(u, headers=UA)))
        except Exception as e:  # Substack throttles bursts
            time.sleep(2 + 2 * t)
    raise SystemExit("fetch failed: " + u)


def slugs():
    out, off = [], 0
    while True:
        page = get(f"https://aidanjude.substack.com/api/v1/archive?sort=new&offset={off}&limit=50")
        if not page:
            break
        out += page
        off += len(page)
    return [p["slug"] for p in sorted(out, key=lambda p: p["post_date"]) if p["post_date"].startswith(YEAR)]


# Higher-resolution copies of the same image he placed, where one is public (same work, same crop).
UPGRADE = {
    "april-24-01": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/68/Pillars_of_creation_2014_HST_WFC3-UVIS_full-res_denoised.jpg/1920px-Pillars_of_creation_2014_HST_WFC3-UVIS_full-res_denoised.jpg",
}


def fetch_img(slug, k, im):
    src = im["src"]
    m = re.search(r"(https%3A%2F%2F.*)$", src)
    orig = urllib.parse.unquote(m.group(1)) if m else src
    ext = os.path.splitext(urllib.parse.urlparse(orig).path)[1] or ".jpg"
    key = f"{slug}-{k:02d}"
    fn = f"{SRC}/img/{key}{ext}"
    if not os.path.exists(fn):
        try:
            urllib.request.urlretrieve(orig, fn)
        except Exception:
            urllib.request.urlretrieve(src, fn)
    if key in UPGRADE:
        up = f"{SRC}/img/{key}-hi.jpg"
        if not os.path.exists(up):
            req = urllib.request.Request(UPGRADE[key], headers={"User-Agent": "aidan-magazine/1.0 (personal print edition)"})
            data = urllib.request.urlopen(req).read()
            open(up, "wb").write(data)
        fn = up
    # browsers print webp/gif fine, but normalise to png/jpg so every PDF tool can count ppi
    if fn.endswith((".webp", ".gif")):
        png = fn.rsplit(".", 1)[0] + ".png"
        if not os.path.exists(png):
            Image.open(fn).convert("RGB").save(png)
        fn = png
    w, h = Image.open(fn).size
    return {"t": "img", "file": os.path.relpath(fn, D), "w": w, "h": h, "credit": (im.get("alt") or "").strip()}


KEEP_INLINE = {"em": "em", "i": "em", "strong": "strong", "b": "strong", "code": "code"}


def inline(node):
    """Inner HTML with only em/strong kept; links become plain text (print has no href)."""
    out = []
    for c in node.children:
        if isinstance(c, NavigableString):
            s = str(c)
            out.append(s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
        elif isinstance(c, Tag):
            if c.name in ("button", "svg", "script", "style"):
                continue
            if c.name == "br":
                out.append("<br>")
                continue
            tag = KEEP_INLINE.get(c.name)
            inner = inline(c)
            out.append(f"<{tag}>{inner}</{tag}>" if tag and inner.strip() else inner)
    return "".join(out)


def items(lst):
    res = []
    for li in lst.find_all("li", recursive=False):
        sub = [x for x in li.find_all(["ul", "ol"], recursive=False)]
        for x in sub:
            x.extract()
        paras = li.find_all("p", recursive=False)
        html = "<br>".join(inline(p) for p in paras) if paras else inline(li)
        res.append({"html": html.strip(), "sub": [{"ordered": x.name == "ol", "items": items(x)} for x in sub]})
    return res


def parse(slug):
    r = json.load(open(f"{SRC}/{slug}.json"))
    soup = BeautifulSoup(r["body_html"], "html.parser")
    blocks, k = [], 0
    for el in soup.find_all(recursive=False):
        cls = el.get("class") or []
        if "button-wrapper" in cls:
            continue
        if el.name == "div" and "captioned-image-container" in cls:
            for im in el.find_all("img"):
                blocks.append(fetch_img(slug, k, im))
                k += 1
            continue
        if el.name == "div" and "pullquote" in cls:
            blocks.append({"t": "hispull", "html": " ".join(inline(p) for p in el.find_all("p")) or inline(el)})
            continue
        if el.name in ("h1", "h2", "h3", "h4", "h5"):
            blocks.append({"t": "h", "lv": int(el.name[1]), "html": inline(el).strip()})
        elif el.name == "p":
            h = inline(el).strip()
            if h:
                blocks.append({"t": "p", "html": h})
        elif el.name in ("ul", "ol"):
            blocks.append({"t": "list", "ordered": el.name == "ol", "items": items(el)})
        elif el.name == "blockquote" and el.find("pre"):
            blocks.append({"t": "pre", "text": el.get_text()})   # verse he set as a quoted code block (Homer)
        elif el.name == "blockquote":
            blocks.append({"t": "bq", "paras": [inline(p).strip() for p in el.find_all("p")] or [inline(el).strip()]})
        elif el.name == "pre":
            blocks.append({"t": "pre", "text": el.get_text()})
        elif el.name == "hr":
            blocks.append({"t": "hr"})
        else:
            raise SystemExit(f"unhandled {el.name} {cls} in {slug}")

    # opener art = the first image + his italic caption under it (his own credit line)
    assert blocks[0]["t"] == "img", slug
    art = blocks.pop(0)
    cap = ""
    if blocks and blocks[0]["t"] == "p" and blocks[0]["html"].startswith("<em>"):
        cap = blocks.pop(0)["html"]
    art["credit_html"] = cap

    # "Some Literature" is his closing department every month; the sign-off follows it
    li = next(i for i, b in enumerate(blocks) if b["t"] == "h" and "Some Literature" in b["html"])
    lit_art = None
    # only the painted strip he set as a banner over the department (Jan); a body image stays in the body
    if li > 0 and blocks[li - 1]["t"] == "img" and blocks[li - 1]["w"] > 3 * blocks[li - 1]["h"]:
        lit_art = blocks.pop(li - 1)
        li -= 1
    tail = blocks[li + 1:]
    body = blocks[:li]
    si = next((i for i, b in enumerate(tail) if b["t"] == "p" and b["html"].startswith("Thanks for reading")), len(tail))
    lit = {"head": blocks[li]["html"], "art": lit_art, "blocks": tail[:si], "signoff": [b["html"] for b in tail[si:]]}
    return {
        "slug": slug, "title": r["title"], "subtitle": (r.get("subtitle") or "").strip(),
        "date": r["post_date"][:10], "art": art, "body": body, "lit": lit,
    }


def main():
    os.makedirs(f"{SRC}/img", exist_ok=True)
    ss = slugs()
    assert len(ss) == 9, ss  # cross-check: Periodicals had 9 posts dated 2024
    for s in ss:
        if not os.path.exists(f"{SRC}/{s}.json"):
            json.dump(get(f"https://aidanjude.substack.com/api/v1/posts/{s}"), open(f"{SRC}/{s}.json", "w"))
            time.sleep(1)
    posts = [parse(s) for s in ss]
    json.dump(posts, open(f"{D}/content.json", "w"), indent=1, ensure_ascii=False)
    for p in posts:
        print(p["date"], p["title"], len(p["body"]), "blocks; lit", len(p["lit"]["blocks"]), "signoff", len(p["lit"]["signoff"]))


if __name__ == "__main__":
    main()
