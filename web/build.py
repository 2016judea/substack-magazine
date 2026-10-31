#!/usr/bin/env python3
"""Periodicals on the web: all 51 posts (plus the three randomaidan pieces he chose) in Credo's reader, typeset in the print edition's face and colours.

  python3 web/build.py      ->  web/public/index.html + web/public/img/

Text and pictures come from editions/complete/scripts/content.py (read, never written): the same parse
the print book uses, so web and print hold the same words, the same pictures and the same credits. The
reader is Credo's (web/reader.html, copied verbatim from ~/Desktop/credo/scripts/reader.html at cc67f79);
every change to it is a checked string replacement below, so the port stays auditable.

Identity from editions/complete/scripts/build.py: Source Serif 4 for display and text, Source Code Pro
for the mono, deep ink ground for the cover and the four year openers, vermilion for the one accent.
"""
import html, json, os, re, shutil, subprocess, sys
sys.dont_write_bytecode = True          # importing content.py must not write into editions/complete
HERE = os.path.dirname(os.path.abspath(__file__))
ED = os.path.join(os.path.dirname(HERE), "editions", "complete")
sys.path.insert(0, f"{ED}/scripts")
import content as C
from bs4 import BeautifulSoup, NavigableString, Tag

PUB = f"{HERE}/public"; IMG = f"{PUB}/img"
os.makedirs(IMG, exist_ok=True)
# print tokens (build.py): INK, ACC, GROUND, PAPER, MUTE, ACCD
src = open(f"{ED}/scripts/build.py").read()
INK, ACC, GROUND, PAPER, MUTE, ACCD = re.search(r'^INK, ACC, GROUND, PAPER, MUTE, ACCD = (.+)$', src, re.M).group(1).replace('"', "").split(", ")

# ---------- text: content.py's HTML -> the reader's blocks ----------
def inl(node):
    """inline HTML -> the reader's marked text: \x01em\x02, \x03strong\x04, \x05 = line break"""
    out = []
    for c in node.children:
        if isinstance(c, NavigableString): out.append(str(c)); continue
        if c.name == "wbr": continue
        if c.name == "br": out.append("\x05"); continue
        if c.name == "em": out.append("\x01" + inl(c) + "\x02"); continue
        if c.name == "strong": out.append("\x03" + inl(c) + "\x04"); continue
        if c.name == "span" and "url" in (c.get("class") or []): out.append("\x06" + c.get_text("").replace("\u200b", "") + "\x07"); continue
        out.append(inl(c))
    return "".join(out)

def clean(v): return re.sub(r"[ \t\r\n]+", " ", v).strip()

USED = []
def img_block(fig, first=False):
    im = fig.find("img"); f = im["src"].split("/src/img/")[-1]
    m = next(x for x in C.IMGS.values() if x["file"].endswith("/" + f)) if not re.search(r"-e\d+\.", f) else C.EMB[f.rsplit(".", 1)[0]]
    kind = [k for k in fig["class"] if k != "fig"][0]
    cap = fig.find("figcaption")
    capt = "\n".join(clean(s.get_text("")) for s in cap.find_all("span")) if cap and cap.find("span") else (clean(cap.get_text("")) if cap else "")
    USED.append(f)
    # widths on the 707.5 px measure, in the print book's proportions (502 pt measure, 241 pt column)
    mw = {"plate": 707.5, "span": 707.5, "full": 707.5, "strip": 707.5, "col": 400}[kind]
    mh = {"plate": 520, "span": 520, "full": 600, "strip": 200, "col": 440}[kind]
    return {"t": "img", "src": f"img/{f}", "w": m["w"], "h": m["h"], "cap": capt, "mw": mw, "mh": mh}

def linkify(h):
    """a list item's (already escaped) HTML: each printed address becomes a link, its text unchanged"""
    def a(m):
        u = m.group(1).replace("<wbr>", ""); href = re.sub(r"[.,;:!?)\]”’\"']+$", "", u)
        full = href if re.match(r"https?://", href) else "https://" + href
        return f'<a class="url" href="{html.escape(full)}" target="_blank" rel="noopener">{href}</a>{u[len(href):]}'
    return re.sub(r'<span class="url">(.*?)</span>', a, h)

def li_html(li):
    """a list item as HTML: content.py already escaped it; nested lists stay nested"""
    return "".join(str(c) for c in li.children)

def blocks_for(p):
    plate = p.plate_html(); main, tail = p.body_html()
    soup = BeautifulSoup(plate + "".join(main) + "".join(tail), "html.parser")
    out = []
    for e in soup.find_all(recursive=False):
        cl = e.get("class") or []
        if e.name == "figure": out.append(img_block(e)); continue
        # a head is set in its own face: the bold or italic run Substack wrapped round a whole head adds nothing
        if e.name == "h2": out.append({"t": "dept", "v": re.sub("[\x01-\x04]", "", clean(inl(e)))}); continue
        if e.name == "h3": out.append({"t": "h3", "v": re.sub("[\x03\x04]", "", clean(inl(e)))}); continue
        if e.name == "h4" or (e.name == "p" and "bold" in cl): out.append({"t": "h4", "v": clean(inl(e))}); continue
        if e.name == "p":
            b = {"t": "p", "v": clean(inl(e))}
            if "disp" in cl: b["cls"] = "disp " + [c for c in cl if c != "disp"][0]
            elif "riff" in cl: b["cls"] = "riff"
            elif "vl" in cl: b["cls"] = "vl"          # a line of verse he set as a paragraph: no drop cap
            out.append(b); continue
        if e.name in ("ul", "ol"):
            # nested lists flatten to one item per line of his list, each keeping its depth and number,
            # so a long nested item can break between its sub-items instead of moving whole
            def walk(lst, d):
                for k, li in enumerate(lst.find_all("li", recursive=False)):
                    own = linkify("".join(str(c) for c in li.children if not (isinstance(c, Tag) and c.name in ("ul", "ol"))))
                    out.append({"t": "li", "v": own, "ord": lst.name == "ol", "n": k + 1, "d": d})
                    for sub_ in li.find_all(["ul", "ol"], recursive=False): walk(sub_, d + 1)
            walk(e, 0)
            continue
        if e.name == "blockquote":
            cls = "pull" if "pull" in cl else "q"
            for q in e.find_all("p"): out.append({"t": "p", "v": clean(inl(q)), "cls": cls})
            continue
        if e.name == "div" and "lit" in cl:
            lt = e.find(class_="lt")
            if "verse" in cl:
                for st in re.split(r"\n\s*\n", lt.get_text()):
                    if st.strip(): out.append({"t": "verse", "v": st.strip("\n")})
            else:
                for q in lt.find_all("p"): out.append({"t": "p", "v": clean(inl(q)), "cls": "lit"})
            for a in e.find_all(class_="att"): out.append({"t": "p", "v": clean(a.get_text()), "cls": "att"})
            continue
        if e.name == "pre": out.append({"t": "code", "v": e.get_text()}); continue
        if e.name == "div" and "brk" in cl: out.append({"t": "brk"}); continue
        raise SystemExit(f"unhandled {p.slug}: {str(e)[:120]}")
    # an empty paragraph from a stray <br> is dropped
    return [b for b in out if b["t"] in ("img", "brk", "code", "verse") or clean(b.get("v", "").replace("\x05", " "))]

PIECES = []
for s in C.SLUGS:
    p = C.Post(s, {})
    PIECES.append(dict(slug=s, title=p.title, deck=p.sub, eyebrow=p.date, mov=str(p.year), blocks=blocks_for(p), mode=p.mode))
assert len(PIECES) == 54, len(PIECES)   # 51 Periodicals posts + 3 randomaidan pieces he chose (10/30)
assert len(USED) == len(set(USED)), [u for u in USED if USED.count(u) > 1]   # no picture printed twice

# ---------- pictures: his files, sized for a screen (long edge 1600 px), never upscaled ----------
from PIL import Image
def web_name(f):
    # a photograph saved as PNG ships as JPEG; a flat PNG (diagram, screenshot) stays PNG
    return f[:-4] + ".jpg" if f.endswith(".png") and f in PHOTO_PNG else f
PHOTO_PNG = set()
for f in USED:
    if f.endswith(".png") and os.path.getsize(f"{ED}/src/img/{f}") > 1_200_000:
        im = Image.open(f"{ED}/src/img/{f}")
        if im.mode not in ("RGBA", "LA", "P") or im.getextrema()[-1][0] == 255: PHOTO_PNG.add(f)
for b in (b for f in PIECES for b in f["blocks"] if b["t"] == "img"):
    b["src"] = "img/" + web_name(b["src"][4:])
for f in USED:
    s_ = f"{ED}/src/img/{f}"; d = f"{IMG}/{web_name(f)}"
    if os.path.exists(d) and os.path.getmtime(d) >= os.path.getmtime(s_): continue
    im = Image.open(s_); im.thumbnail((1600, 1600), Image.LANCZOS)
    if d.endswith(".jpg"): im.convert("RGB").save(d, "JPEG", quality=82, optimize=True, progressive=True)
    else: im.save(d, "PNG", optimize=True)
keep = {web_name(f) for f in USED}
for f in os.listdir(IMG):
    if f not in keep: os.remove(f"{IMG}/{f}")

# ---------- the reader ----------
tpl = open(f"{HERE}/reader.html").read()
YEARS = ["2023", "2024", "2025", "2026"]
J = dict(name="Aidan Jude", span="2023–2026", movements=[dict(num=y, title="") for y in YEARS], figs={}, refs=[], plates={}, closing=[], imgShrink=45)

def sub(a, b, n=1):
    global tpl
    assert tpl.count(a) == n, (tpl.count(a), a[:80]); tpl = tpl.replace(a, b)

# head: title, description, private proof, the print edition's faces
sub("<title>__NAME__ No. 1</title>", "<title>Aidan Jude · Periodicals · 2023–2026</title>")
sub('<meta name="description" content="__DESC__">', '<meta name="description" content="Aidan Jude. Periodicals, 2023–2026.">\n<meta name="robots" content="noindex">')
sub("family=DM+Serif+Display:ital@0;1&family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;1,6..72,400&family=JetBrains+Mono:wght@400;500;700",
    "family=Source+Serif+4:ital,opsz,wght@0,8..60,300;0,8..60,400;0,8..60,600;1,8..60,300;1,8..60,400;1,8..60,600&family=Source+Code+Pro:wght@400;500;700")
sub(':root{--p:#ffffff;--k:#0e0e0e;--r:#d8321e;--g:#8a8a86;--l:#e4e4e0;--disp:"DM Serif Display",serif;--body:"Newsreader",Georgia,serif;--mono:"JetBrains Mono",monospace;',
    f':root{{--p:#ffffff;--k:{INK};--r:{ACC};--g:{MUTE};--l:#e4e2dc;--disp:"Source Serif 4",Georgia,serif;--body:"Source Serif 4",Georgia,serif;--mono:"Source Code Pro",ui-monospace,monospace;--ground:{GROUND};--paper:{PAPER};--accd:{ACCD};')
sub("const NS='http://www.w3.org/2000/svg',K='#0e0e0e',R='#d8321e',G='#8a8a86',LC='#e4e4e0',MONO='JetBrains Mono',DISP='DM Serif Display';",
    f"const NS='http://www.w3.org/2000/svg',K='{INK}',R='{ACC}',G='{MUTE}',LC='#e4e2dc',MONO='Source Code Pro',DISP='Source Serif 4';")
sub("const faces=['400 22px Newsreader','italic 400 22px Newsreader','500 22px Newsreader','400 77px \"DM Serif Display\"','500 16px \"JetBrains Mono\"','700 24px \"JetBrains Mono\"'];",
    "const faces=['400 22px \"Source Serif 4\"','italic 400 22px \"Source Serif 4\"','600 22px \"Source Serif 4\"','300 77px \"Source Serif 4\"','400 77px \"Source Serif 4\"','italic 400 38px \"Source Serif 4\"','400 16px \"Source Code Pro\"','500 16px \"Source Code Pro\"'];")
# the bar: his name, the run
sub('<header id="bar"><span class="wm">__NAME__</span><span class="sub">No. 1 · 2023–2026</span>', '<header id="bar"><span class="wm">Aidan Jude</span><span class="sub">Periodicals · 2023–2026</span>')
# a line break inside a paragraph (his <br>) survives the word splitter as \x05
sub(".replace(/\\u0003([^\\u0004]*)\\u0004/g,'<b>$1</b>')}", ".replace(/\\u0003([^\\u0004]*)\\u0004/g,'<b>$1</b>').replace(/\\u0005/g,'<br>')}")
# every address he prints (content.py's .url spans, carried as \x06…\x07) is a real link opening in a new tab;
# the text stays exactly as printed, trailing punctuation stays outside the href
sub(".replace(/\\u0005/g,'<br>')}", ".replace(/\\u0005/g,'<br>').replace(/\\u0006([^\\u0007]*)\\u0007/g,(m,u)=>{const h=u.replace(/[.,;:!?)\\]\u201d\u2019\\x22']+$/,'');const full=/^https?:\\/\\//.test(h)?h:'https://'+h;return `<a class=\"url\" href=\"${full.replace(/&amp;/g,'&').replace(/&/g,'&amp;').replace(/\\x22/g,'%22')}\" target=\"_blank\" rel=\"noopener\">${h}</a>`+u.slice(h.length)})}")
# a paragraph split across pages can cut an italic or bold run in two: each half closes or reopens its own run
sub("function H(s){return esc(s)", "function bal(s,o,c){let d=0,pre='';for(const ch of s){if(ch===o)d++;else if(ch===c){if(d)d--;else pre+=o}}return pre+s+c.repeat(d)}\nfunction H(s){s=bal(bal(String(s),'\\u0001','\\u0002'),'\\u0003','\\u0004');return esc(s)")
# front cover: his name and the run, nothing else, on the ink ground
sub("""function coverPage(){const p=newPage('cover');
  p.insertAdjacentHTML('afterbegin',`<div class="mast"><b>${esc(J.name)}</b><span>No. ${J.no||1} · ${esc(J.span)}</span></div>
<div class="fc-line">${J.coverLine}</div>
<div class="fc-eq"><small>${esc(J.count)} essays</small></div>`)}""",
    """function coverPage(){const p=newPage('cover ink');
  p.insertAdjacentHTML('afterbegin',`<div class="cv-sub">Periodicals · ${esc(J.span)}</div><div class="cv-name">Aidan<br>Jude</div>`)}""")
sub("""function backPage(){const p=newPage('back');const a=J.backPlate;""",
    """function backPage(){const p=newPage('back ink');p.insertAdjacentHTML('afterbegin',`<div class="bc"><div class="ft"><span>Aidan Jude</span><span>Saint Paul, Minnesota</span><span>aidanjude.substack.com</span></div></div>`);return;const a=J.backPlate;""")
# a year opens on the ink ground: the year, nothing else (the print book's divider)
sub("""function movementPage(m){const p=newPage('mov');p.dataset.piece='movement:'+m.num;
  const t=el('div','tx');t.innerHTML=`<div class="num-r">${esc(m.num)}</div><h2>${esc(m.title)}</h2>`;p.appendChild(t);t.appendChild(figure(m.fig));return p}""",
    """function movementPage(m){const p=newPage('mov ink');p.dataset.piece='movement:'+m.num;
  p.innerHTML=`<div class="yr-rule"></div><div class="yr">${esc(m.num)}</div>`;return p}""")
# blocks this book has that Credo's issues did not: department heads, sub-heads, his lists as he nested them,
# verse stanzas, code, the section break; and a picture's own size class
sub("""  if(b.t==='img'){const f=figure({kind:'img',name:'',right:'',src:b.src,cap:b.cap});const i=f.querySelector('img');const h=Math.min(420,707.5*(b.h||3)/(b.w||4));i.style.height=h+'px';i.style.width=Math.min(707.5,h*(b.w||4)/(b.h||3))+'px';return f}""",
    """  if(b.t==='img'){const f=figure({kind:'img',name:'',right:'',src:b.src,cap:b.cap});const i=f.querySelector('img');i.style.maxHeight='none';const mw=b.mw||707.5;let w=Math.min(mw,b.w),h=w*b.h/b.w;if(h>(b.mh||420)){h=b.mh||420;w=h*b.w/b.h}i.style.height=h+'px';i.style.width=w+'px';return f}
  if(b.t==='dept')return el('h5','dept',H(b.v));
  if(b.t==='h4')return el('h4',null,H(b.v));
  if(b.t==='verse')return el('div','verse',esc(b.v));
  if(b.t==='code')return el('pre','code',esc(b.v));
  if(b.t==='brk')return el('div','brk');""")
sub("""function splitPara(f,b){let words=b.v.split(/\\s+/),guard=0,cut=false;
  while(words.length&&guard++<80){const p=el('p',b.lede&&guard===1?'lede':b.num?'num':null,H(words.join(' ')));""",
    """function splitPara(f,b){let words=b.v.split(/\\s+/),guard=0,cut=false;
  while(words.length&&guard++<80){const p=el('p',b.lede&&guard===1?'lede':b.num?'num':(b.cls||null),H(words.join(' ')));""")
# lists: ordered or not, items carry their own (already escaped) HTML so nesting survives
sub("const node=b.t==='li'?el('ul',null,`<li>${H(b.v)}</li>`):blockEl(b);", "const node=b.t==='li'?el(b.ord?'ol':'ul',null,`<li>${b.v}</li>`):blockEl(b);")
sub("""      if(!ul||ul.parentNode!==fl){ul=el('ul');if(!place(ul)){freshPage(f.slug);place(ul)}}
      const li=el('li',null,H(b.v));ul.appendChild(li);if(fits())continue;ul.removeChild(li);if(!ul.children.length)fl.removeChild(ul);
      freshPage(f.slug);ul=el('ul');fl.appendChild(ul);ul.appendChild(li);continue}""",
    """      const mk=()=>{const u=el(b.ord?'ol':'ul','d'+(b.d||0));if(b.ord)u.start=b.n;u.dataset.d=b.d||0;return u};
      if(!ul||ul.parentNode!==fl||(b.ord&&b.n===1)||ul.tagName!==(b.ord?'OL':'UL')||+ul.dataset.d!==(b.d||0)){ul=mk();if(!place(ul)){nextPage(f.slug);ul=mk();place(ul)}}
      const li=el('li',null,b.v);ul.appendChild(li);if(fits())continue;ul.removeChild(li);if(!ul.children.length)fl.removeChild(ul);
      const carry=[];{const isOne=e=>e&&/^(UL|OL)$/.test(e.tagName)&&e.children.length===1&&e.offsetHeight<LINE*1.5;const lc=fl.lastElementChild;if(isOne(lc)&&fl.children.length>1&&!/^(UL|OL)$/.test(lc.previousElementSibling.tagName)){carry.push(lc);fl.removeChild(lc)}}
      const same=carry.includes(ul);nextPage(f.slug);carry.forEach(c=>fl.appendChild(c));if(!same){ul=mk();fl.appendChild(ul)}ul.appendChild(li);continue}""")
# (one line of a list left alone at the foot of a page goes over with the rest of it)
# a run of heads (department, then piece title) keeps with the text under the last of them
sub("    else{need+=(j>i?GAP:0)+Math.min(h,fl.clientHeight*0.9);break}}", "    else if(b.t==='h3'||b.t==='h4'||b.t==='dept'){need+=(j>i?GAP:0)+h}\n    else if(lines>=2*LINE-2)break\n    else if(b.t==='img'){need+=(j>i?GAP:0)+h*0.45;if(!blocks[j+1]||blocks[j+1].t==='img')break}\n    else{need+=(j>i?GAP:0)+Math.min(h,fl.clientHeight*0.9);break}}")
# (a picture under a head can be set down to 45% to stay with it, so the head asks only that much room; two lines of
# text under a head already keep it company, so a picture after them does not drag the head overleaf)
# a head left at the foot of a page goes over with the text it heads (a department head, a piece title, a sub-head)
sub("    freshPage(f.slug)}}\n", "    nextPage(f.slug)}}\nfunction nextPage(slug){const carry=[];{const lc=fl&&fl.lastElementChild,pv=lc&&lc.previousElementSibling;if(lc&&lc.tagName==='P'&&!lc.dataset.split&&lc.offsetHeight<1.5*LINE&&pv&&pv.matches('h3,h4,h5.dept')&&fl.children.length>2)carry.unshift(fl.removeChild(lc))}while(fl&&fl.lastElementChild&&fl.lastElementChild.matches('h3,h4,h5.dept')&&fl.children.length>1)carry.unshift(fl.removeChild(fl.lastElementChild));freshPage(slug);carry.forEach(n=>fl.appendChild(n))}\n")
sub("    freshPage(f.slug);if(!place(node)){fl.appendChild(node)}", "    nextPage(f.slug);if(!place(node)){fl.appendChild(node)}")
sub("fl.removeChild(node);freshPage(f.slug);place(node)", "fl.removeChild(node);nextPage(f.slug);place(node)")
# a picture that will not fit the room left (even at 45% of its size) lets the text after it fill the page,
# and opens the next page instead: a layout that absorbs a gap beats a hole (aetas-nova-issue rule 9). Never when his
# line before it ends in a colon: that line introduces the picture, which must follow it directly
sub("if(OPT.capOrd===ORD)fl.style.bottom=(48.24+OPT.capBy)+'px'}", "if(OPT.capOrd===ORD)fl.style.bottom=(48.24+OPT.capBy)+'px';if(DEFER){const d=DEFER;DEFER=null;fl.appendChild(d)}}\nlet DEFER=null;")
sub("  ORD=0;PENDING=[];if(fl&&OPT.tight)", "  ORD=0;PENDING=[];DEFER=null;if(fl&&OPT.tight)")
sub("  for(let bi=hasLede?1:0;bi<f.blocks.length;bi++){const b=f.blocks[bi];", "  for(let bi=hasLede?1:0;bi<f.blocks.length;bi++){const b=f.blocks[bi];if(DEFER&&b.t!=='p'&&b.t!=='li')nextPage(f.slug);")
sub("    nextPage(f.slug);if(!place(node)){fl.appendChild(node)}", "    if(b.t==='img'&&!DEFER&&room()>START_ROOM*0.6&&!(f.blocks[bi-1]&&/[:：]\\s*$/.test(f.blocks[bi-1].v||''))&&f.blocks[bi+1]&&(f.blocks[bi+1].t==='p'||f.blocks[bi+1].t==='li')){DEFER=node;continue}\n    if(b.t==='img'&&f.blocks[bi-1]&&/[:：]\\s*$/.test(f.blocks[bi-1].v||'')){const lc=fl.lastElementChild;if(lc&&lc.tagName==='P'&&!lc.dataset.split&&fl.children.length>1){if(lc.offsetHeight>4.5*LINE){const pb=f.blocks[bi-1],w=pb.v.split(/\\s+/),cls=lc.className;let n=w.length-1;const ln=t=>{const q=el('p',cls||null,H(t));fl.appendChild(q);const h=q.offsetHeight;fl.removeChild(q);return Math.round(h/LINE)};while(n>1&&ln(w.slice(n).join(' '))<2)n--;lc.innerHTML=H(w.slice(0,n).join(' '));lc.dataset.split='a';const tl=el('p',cls||null,H(w.slice(n).join(' ')));tl.dataset.split='b';freshPage(f.slug);fl.appendChild(tl)}else{fl.removeChild(lc);nextPage(f.slug);fl.appendChild(lc)}if(!place(node))fl.appendChild(node);continue}}\n    nextPage(f.slug);if(!place(node)){fl.appendChild(node)}")
sub("  if(PENDING.length){flushFigures(f.slug);fl=null}", "  if(DEFER)nextPage(f.slug);\n  if(PENDING.length){flushFigures(f.slug);fl=null}")
# a head of any rank keeps with what follows it
sub("if(b.t==='h3'&&bi<f.blocks.length-1){", "if((b.t==='h3'||b.t==='h4'||b.t==='dept')&&bi<f.blocks.length-1){")
# a head never asks for more than 60% of a page below it
sub("  return GAP+need}", "  return Math.min(GAP+need,fl.clientHeight*0.6)}")
# a head over a picture stays when a third of the page is left: the picture is set smaller, or the text fills under the head
# a head that would be pushed overleaf by the picture above it: set that picture smaller (to 45%) so the head stays
sub("if(room()<needFor(f.blocks,bi+1)){fl.removeChild(node);nextPage(f.slug);place(node)}", "if(room()<needFor(f.blocks,bi+1))shrinkAbove(node,needFor(f.blocks,bi+1));if(room()<needFor(f.blocks,bi+1)&&!(room()>fl.clientHeight*0.3&&f.blocks[bi+1].t==='img')){fl.removeChild(node);nextPage(f.slug);place(node)}")
sub("function nextPage(slug){", "function shrinkAbove(node,need){const pr=node.previousElementSibling;const im=pr&&pr.matches('figure.fig')&&pr.querySelector('img');if(!im)return;const w0=parseFloat(im.style.width),h0=parseFloat(im.style.height);for(let k=95;k>=45;k-=5){im.style.width=(w0*k/100)+'px';im.style.height=(h0*k/100)+'px';if(room()>=need)return}im.style.width=w0+'px';im.style.height=h0+'px'}\nfunction nextPage(slug){")
# pictures load when their page is shown, not all 157 at once
sub("else if(spec.kind==='img'){const i=el('img');i.src=spec.src;", "else if(spec.kind==='img'){const i=el('img');i.loading='lazy';i.decoding='async';i.src=spec.src;")
# his subtitle stands under the title, in the opener
sub("const h=el('h2',null,H(f.title));", "const h=el('h2',null,H(f.title)+(f.deck?`<span class=\"deck\">${H(f.deck)}</span>`:''));")
# a piece that opens on a line of verse set as a paragraph takes no drop cap
sub("const hasLede=f.blocks[0]&&f.blocks[0].t==='p';", "const hasLede=f.blocks[0]&&f.blocks[0].t==='p'&&f.blocks[0].cls!=='vl';")
# contents: four years over two pages (2023 and 2024, then 2025 and 2026); no colophon
sub("  const contents=newPage('contents');", "  const contents=newPage('contents'),contents2=newPage('contents');")
sub("""  contents.insertAdjacentHTML('beforeend',`<div class="tx"><div class="eyebrow">Contents</div><div class="toc-list">${secs.map(s=>`<h5>${esc(s.m.num)} · ${esc(s.m.title)}</h5>`+s.items.map(f=>`<a href="#p${firstPage[f.slug]}" data-p="${firstPage[f.slug]}"><span>${H(f.title)}</span><i class="d"></i><b>${firstPage[f.slug]}</b></a>`).join('')).join('')}</div><p class="colophon">${esc(J.name)} · No. ${J.no||1} · ${J.sub?esc(J.sub)+' · ':''}${esc(J.span)} · ${pages.length} pages · Set in DM Serif Display, Newsreader and JetBrains Mono</p></div>`);""",
    """  const tocSec=s=>`<h5>${esc(s.m.num)}</h5>`+s.items.map(f=>`<a href="#p${firstPage[f.slug]}" data-p="${firstPage[f.slug]}"><span>${H(f.title)}</span><i class="d"></i><b>${firstPage[f.slug]}</b></a>`).join('');
  contents.insertAdjacentHTML('beforeend',`<div class="tx"><div class="eyebrow">Contents</div><div class="toc-list">${secs.slice(0,2).map(tocSec).join('')}</div></div>`);
  contents2.insertAdjacentHTML('beforeend',`<div class="tx"><div class="eyebrow">&nbsp;</div><div class="toc-list">${secs.slice(2).map(tocSec).join('')}</div></div>`);""")
sub("""<a href="#p2" data-p="2"><b>2</b><span>Contents</span></a>`+secs.map(s=>`<h5>${esc(s.m.num)} · ${esc(s.m.title)}</h5>`""",
    """<a href="#p2" data-p="2"><b>2</b><span>Contents</span></a>`+secs.map(s=>`<h5>${esc(s.m.num)}</h5>`""")
# the issue's own CSS, after Credo's
CSS = """
/* ---------- Periodicals: the print edition's face and colours on Credo's page ---------- */
body{font-optical-sizing:auto}
.page.ink{background:var(--ground);color:var(--paper)}
/* cover: direction A "Night", approved 2026-10-30 (scratchpad/periodicals-covers.html .a), ported at 1cqw = 8.04px */
.cv-sub{position:absolute;left:56.28px;right:56.28px;top:48.24px;margin:0;padding-bottom:19.3px;border-bottom:2.01px solid #f0704a;font:500 20.9px var(--mono);letter-spacing:.16em;text-transform:uppercase;color:#f0704a}
.cv-name{position:absolute;left:51.46px;bottom:112.56px;font:300 168.84px/.86 var(--disp);letter-spacing:-.02em;color:#f3efe6}
.cv-ft{position:absolute;left:56.28px;bottom:48.24px;font:500 19.3px var(--mono);letter-spacing:.16em;text-transform:uppercase;color:#9aa3b5}
.page.mov .yr-rule{position:absolute;left:48.24px;right:48.24px;top:40.2px;border-top:1px solid var(--accd)}
.page.mov .yr{position:absolute;left:38px;bottom:20px;font:300 300px/1 var(--disp);letter-spacing:-.035em;color:var(--paper)}
.page.back .bc{inset:auto 48.24px 40.2px}
.page.back .bc{background:none}.page.back .bc .ft{display:flex;justify-content:space-between;border-top-color:var(--accd);color:var(--paper);font:400 15.28px var(--mono);letter-spacing:.1em;text-transform:uppercase}
#bar .wm{font-weight:400}
.tx h2{font-weight:400;letter-spacing:-.02em}
.tx h2 .deck{display:block;margin-top:16px;font:italic 400 27px/1.3 var(--body);letter-spacing:0;text-wrap:balance}
.tx p.lede::first-letter{font-weight:400}
.tx h3{font:italic 400 36px/1.12 var(--disp);letter-spacing:-.005em}
.tx h4{font:600 22.11px/1.4 var(--body)}
.tx h5.dept{font:500 16.08px/1.2 var(--mono);letter-spacing:.16em;text-transform:uppercase;color:var(--r);border-top:1px solid var(--k);padding-top:12px}
.tx p{overflow-wrap:break-word}
.tx p.q{font-style:normal}
.tx p.pull{font:italic 400 30px/1.35 var(--body)}
.tx p.lit,.tx p.riff{font-style:normal}
.tx p.lit{font-style:italic}
.tx p.att{font:400 15.28px var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--g)}
.tx p.disp{margin:0}.tx p.disp.h1{font:400 56px/1.05 var(--disp)}.tx p.disp.h3{font:400 36px/1.2 var(--disp)}.tx p.disp.h4{font:italic 400 28px/1.3 var(--disp)}.tx p.disp.h5{font:italic 400 24px/1.3 var(--disp)}
.tx .verse{font:italic 400 22.11px/1.5 var(--body);white-space:pre-wrap}
.tx pre.code{font:400 15px/1.5 var(--mono);white-space:pre-wrap;overflow-wrap:anywhere;color:var(--k)}
.tx .brk{height:16px;display:flex;align-items:center;justify-content:center}.tx .brk::before{content:"";width:40px;border-top:1px solid var(--g)}
.tx ol{padding-left:1.4em;font:400 22.11px/1.5 var(--body)}.tx ol li+li{margin-top:5px}
.tx li ul,.tx li ol{margin:4px 0;padding-left:1.2em}
.tx ul.d1,.tx ol.d1{padding-left:2.3em}.tx ul.d2,.tx ol.d2{padding-left:3.5em}.tx ul.d3,.tx ol.d3{padding-left:4.7em}
.tx ul.d1{list-style-type:circle}.tx ul.d2,.tx ul.d3{list-style-type:square}
.tx :is(ul,ol)+:is(ul,ol){margin-top:-12px}
.tx .lp{display:block}
.tx .url{overflow-wrap:anywhere}
.tx a.url{color:inherit;text-decoration:underline;text-decoration-thickness:1px;text-underline-offset:3px;text-decoration-color:var(--g)}
.fig figcaption{white-space:pre-line;font-size:14px;line-height:1.45}
.page.contents .toc-list{gap:1px;font-size:18px;line-height:1.2}
.page.contents .toc-list h5{font:300 34px/1 var(--disp);letter-spacing:-.01em;text-transform:none;margin:12px 0 6px;padding-top:10px;border-top:1px solid var(--k)}
.page.contents .toc-list h5:first-child{margin-top:4px}
"""
sub("</style>", CSS + "</style>")
out = tpl.replace("/*__DATA__*/", "window.ISSUE=" + json.dumps(PIECES, ensure_ascii=False) + ";window.J=" + json.dumps(J, ensure_ascii=False) + ";")
assert "__NAME__" not in out and "No. 1" not in out.replace("J.no||1", "")
open(f"{PUB}/index.html", "w").write(out)
words = sum(len(b.get("v", "").split()) for f in PIECES for b in f["blocks"] if b["t"] != "img")
mb = sum(os.path.getsize(f"{IMG}/{f}") for f in keep) / 1e6
print(f"{len(PIECES)} pieces, {words} words, {len(USED)} pictures ({mb:.1f} MB) -> {PUB}/index.html")

# the typesetting rules, over every page (web/check.py): a broken rule fails the build
if "--no-check" not in sys.argv:
    rc = subprocess.run([sys.executable, f"{HERE}/check.py"]).returncode
    if rc: sys.exit("check.py failed: see the pages listed above")
