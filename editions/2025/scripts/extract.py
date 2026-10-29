#!/usr/bin/env python3
"""Freeze the 2025 Periodicals posts (aidanjude.substack.com) into corpus.json: one entry per post,
a flat list of blocks in the order he set them, inline bold/italic kept as <b>/<i>.
Images are fetched at the original upload size (data-attrs src), not the 1456 px CDN copy.
Run: python3 scripts/extract.py   (reads src/archive_2025.json + src/posts/*.json, writes src/corpus.json, src/img/)"""
import json, os, re, subprocess, html
from bs4 import BeautifulSoup, NavigableString, Tag
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = f"{ROOT}/src"

def inline(el):
    out = []
    for c in el.children:
        if isinstance(c, NavigableString): out.append(html.escape(str(c), quote=False))
        elif c.name in ("strong", "b"): out.append("<b>" + inline(c) + "</b>")
        elif c.name in ("em", "i"): out.append("<i>" + inline(c) + "</i>")
        elif c.name == "br": out.append("<br>")
        elif c.name == "label": continue          # Substack's hidden "Text within this block..." label
        elif c.name in ("a", "span", "code", "u", "s", "sup", "sub"): out.append(inline(c))
        else: out.append(inline(c))
    return "".join(out)

def lst(el):
    items = []
    for li in el.find_all("li", recursive=False):
        own = [c for c in li.children if not (isinstance(c, Tag) and c.name in ("ul", "ol"))]
        txt = "".join(inline(c) if isinstance(c, Tag) else html.escape(str(c), quote=False) for c in own).strip()
        kids = [lst(s) for s in li.find_all(["ul", "ol"], recursive=False)]
        items.append({"t": txt, "sub": kids})
    return {"type": el.name, "items": items}

def blocks_of(node, out, imgs):
    for c in node.children:
        if isinstance(c, NavigableString):
            if c.strip(): out.append({"type": "p", "html": html.escape(c.strip())})
            continue
        cls = c.get("class") or []
        if c.name == "div" and "captioned-image-container" in cls or c.name == "figure":
            im = c.find("img"); a = json.loads(im.get("data-attrs") or "{}")
            src = a.get("src") or im["src"]
            imgs.append(src)
            out.append({"type": "img", "src": src, "alt": im.get("alt") or "", "w": int(im.get("width") or 0), "h": int(im.get("height") or 0)})
        elif c.name == "p" and "button-wrapper" in cls:
            out.append({"type": "button", "html": c.get_text(strip=True)})
        elif c.name == "p":
            out.append({"type": "p", "html": inline(c).strip()})
        elif c.name in ("h1", "h2", "h3", "h4", "h5"):
            out.append({"type": c.name, "html": inline(c).strip()})
        elif c.name in ("ul", "ol"):
            out.append(lst(c))
        elif c.name == "hr":
            out.append({"type": "hr"})
        elif c.name == "div" and "preformatted-block" in cls:
            out.append({"type": "pre", "text": c.find("pre").get_text()})
        elif c.name == "div" and "pullquote" in cls:
            inner = []; blocks_of(c, inner, imgs); out.append({"type": "pullquote", "blocks": inner})
        elif c.name == "blockquote":
            inner = []; blocks_of(c, inner, imgs); out.append({"type": "blockquote", "blocks": inner})
        elif c.name == "div":
            blocks_of(c, out, imgs)
        else:
            out.append({"type": "p", "html": inline(c).strip(), "_tag": c.name})

arch = json.load(open(f"{SRC}/archive_2025.json"))
corpus = []
os.makedirs(f"{SRC}/img", exist_ok=True)
for p in arch:
    j = json.load(open(f"{SRC}/posts/{p['slug']}.json"))
    out, imgs = [], []
    blocks_of(BeautifulSoup(j["body_html"], "html.parser"), out, imgs)
    k = 0
    def walk(bs):
        global k
        for b in bs:
            if b["type"] == "img":
                k += 1; ext = os.path.splitext(b["src"].split("?")[0])[1].lower() or ".jpg"
                fn = f"{p['slug']}-{k:02d}{ext}"; b["file"] = fn
                if not os.path.exists(f"{SRC}/img/{fn}") or os.path.getsize(f"{SRC}/img/{fn}") == 0:
                    subprocess.run(["curl", "-sL", "--retry", "3", "-o", f"{SRC}/img/{fn}", b["src"]], check=True)
            if "blocks" in b: walk(b["blocks"])
    walk(out)
    corpus.append({"slug": p["slug"], "title": j["title"], "subtitle": j.get("subtitle") or "", "date": j["post_date"][:10], "wordcount": j.get("wordcount"), "blocks": out})
    print(p["slug"], len(out), "blocks", k, "images")
json.dump(corpus, open(f"{SRC}/corpus.json", "w"), indent=1, ensure_ascii=False)
