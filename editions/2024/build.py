#!/usr/bin/env python3
"""Aidan Jude, Selected writing 2024 — write issue.html from content.json.

The page is laid out in the browser by layout.js (two-column bands on an 18px baseline grid,
widow/orphan control, keep-with-next headings, span images and pull quotes) and printed by
render.py. Every word in the body comes from content.json; the only text added here is
structural (contents, folios, dates) plus pull quotes lifted verbatim from the same essay,
which this script asserts.
"""
import html, json, os, re

D = os.path.dirname(os.path.abspath(__file__))
YEAR = "2024"
NAME = "Aidan Jude"

# Pull quotes: (exact sentence from that month's body, paragraph it follows). Both asserted.
PULLS = {
    "january": [
        ("Many beautiful things are like this. Impractical that is.", "We rise and have breakfast as a group."),
        ("Stop trying to move so fast and seek ease in the simplicities of life.", "The remainder of the group joins up"),
    ],
    "february-24": [("Yeah you did. You tried to seduce them.", "This is ultimately what fascinates me")],
    "march-24": [("How can you have a deep understanding of yourself when you spend your life’s entirety caught up in everyone else?", "We stand on the brink of a technological revolution")],
    "april-24": [("No small talk. No ghosting. No bullshit.", "In short, gravitational collapse is responsible")],
    "may-24": [("Is that when we achieve “intelligence”?", "Human-esque consciousness is defined")],
    "august-24": [("Empathy for others grows with understanding. And you can’t judge that which cannot be fathomed.", "This morning’s self lecture centered")],
    "october-24": [("We’re living in the aftermath of a golden age.", "From the early 18th century")],
    "november-24": [("I’m a strong believer that you are what you attract.", "Creating something that succeeds at scale.")],
    "december-24": [("It’s the creative process itself that is inherently so rewarding.", "Black holes and their singularity defy nature.")],
}

MONTHS = "January February March April May June July August September October November December".split()


def plain(h):
    return html.unescape(re.sub(r"<[^>]+>", "", h))


def fmt_date(d):
    y, m, dd = d.split("-")
    return f"{MONTHS[int(m) - 1]} {int(dd)}, {y}"


def esc(s):
    return html.escape(s, quote=True)


def pre_lines(text, collapse=True):
    """Verse/riff from his code blocks: every line kept; runs of blank lines become one gap."""
    out, blank = [], 0
    for ln in text.rstrip("\n").split("\n"):
        if ln.strip() == "":
            blank += 1
            continue
        if blank and out:
            out.append(None)
        blank = 0
        out.append(ln.rstrip())
    return out


def img_block(b, role):
    return {"t": "img", "src": b["file"], "w": b["w"], "h": b["h"], "credit": esc(b.get("credit", "")), "role": role}


def flow_items(post):
    """Body blocks -> flat list of renderable items (dicts the JS paginator understands)."""
    items, pulls = [], list(PULLS.get(post["slug"], []))
    body_text = " ".join(plain(b.get("html", "")) for b in post["body"] if b["t"] == "p")
    for q, anchor in pulls:
        assert q in body_text, (post["slug"], q)
    after = {}
    for q, anchor in pulls:
        hits = [i for i, b in enumerate(post["body"]) if b["t"] == "p" and plain(b["html"]).startswith(anchor)]
        assert len(hits) == 1, (post["slug"], anchor, hits)
        after.setdefault(hits[0], []).append(q)
    prev = None
    for i, b in enumerate(post["body"]):
        t = b["t"]
        if t == "h":
            items.append({"t": f"h{min(b['lv'], 4) if b['lv'] >= 4 else 2}", "html": b["html"]})
        elif t == "p":
            label = bool(re.fullmatch(r"<strong>[^<]{1,40}</strong>", b["html"]))   # e.g. "References"
            items.append({"t": "p", "html": b["html"], "noindent": prev not in ("p",), "label": label})
        elif t == "bq":
            for k, ph in enumerate(b["paras"]):
                items.append({"t": "bq", "html": ph, "first": k == 0, "last": k == len(b["paras"]) - 1})
        elif t == "list":
            def walk(lst, depth):
                for n, it in enumerate(lst["items"], 1):
                    mark = f"{n}." if lst["ordered"] else "•"
                    items.append({"t": "li", "html": it["html"], "mark": mark, "depth": depth})
                    for s in it["sub"]:
                        walk(s, depth + 1)
            walk(b, 0)
            items[-1]["lastli"] = True
        elif t == "pre":
            lines = pre_lines(b["text"])
            gid = f"pre{i}"
            for k, ln in enumerate(lines):
                items.append({"t": "gap", "grp": gid} if ln is None else {"t": "vl", "text": esc(ln), "grp": gid})
            items[-1]["lastvl"] = True
        elif t == "img":
            items.append(img_block(b, "body"))
        elif t == "hispull":
            items.append({"t": "pull", "html": b["html"], "his": True})
        elif t == "hr":
            items.append({"t": "hr"})
        prev = t
        for q in after.get(i, []):
            items.append({"t": "pull", "html": esc(q)})
    return items


def lit_page(post):
    lit = post["lit"]
    parts = []
    if lit["art"]:
        parts.append(img_block(lit["art"], "lit"))
    for b in lit["blocks"]:
        if b["t"] == "pre":
            parts.append({"t": "litpre", "lines": [None if l is None else esc(l) for l in pre_lines(b["text"])]})
        elif b["t"] == "bq":
            parts.append({"t": "litbq", "paras": b["paras"]})
        elif b["t"] == "img":
            parts.append(img_block(b, "lit"))
        elif b["t"] == "p":
            parts.append({"t": "litp", "html": b["html"]})
        else:
            raise SystemExit("lit block " + b["t"])
    return {"head": lit["head"], "parts": parts, "signoff": lit["signoff"]}


def main():
    posts = json.load(open(f"{D}/content.json"))
    issue = []
    for n, p in enumerate(posts, 1):
        secs = [plain(b["html"]) for b in p["body"] if b["t"] == "h" and b["lv"] <= 3]
        issue.append({
            "n": n, "slug": p["slug"], "title": p["title"], "subtitle": p["subtitle"], "date": fmt_date(p["date"]),
            "sections": secs + [plain(p["lit"]["head"])],
            "art": {**img_block(p["art"], "opener"), "credit": p["art"]["credit_html"]},
            "items": flow_items(p), "lit": lit_page(p),
        })
    cfg = {"name": NAME, "year": YEAR, "count": len(issue), "posts": issue}
    tpl = open(f"{D}/template.html").read()
    out = tpl.replace("/*ISSUE*/null", json.dumps(cfg, ensure_ascii=False))
    open(f"{D}/issue.html", "w").write(out)
    words = sum(len(plain(b.get("html", "") or b.get("text", "")).split()) for p in posts for b in p["body"])
    print("issue.html:", len(issue), "pieces,", words, "body words")


if __name__ == "__main__":
    main()
