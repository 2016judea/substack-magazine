#!/usr/bin/env python3
"""Drive the built reader in Chromium at phone and desktop size: console errors, layout time, pages that
overflow, pictures that fail, contents links that land on the wrong piece, arrow and swipe turns.
  python3 web/qa.py [url]      (default: serves web/public on :8765)   screenshots -> web/qa/"""
import json, os, subprocess, sys, time
from playwright.sync_api import sync_playwright
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = f"{HERE}/qa"; os.makedirs(OUT, exist_ok=True)
url = sys.argv[1] if len(sys.argv) > 1 else None
srv = None
if not url:
    srv = subprocess.Popen([sys.executable, "-m", "http.server", "8765", "-d", f"{HERE}/public"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1); url = "http://localhost:8765/"
CHECK = """() => {
  const pages=[...document.querySelectorAll('.page')];
  const over=[];
  pages.forEach((p,i)=>{const pr=p.getBoundingClientRect();const sc=pr.width/804;
    const tx=p.querySelector('.tx');if(tx&&tx.scrollHeight>tx.clientHeight+1)over.push([i+1,'tx',tx.scrollHeight-tx.clientHeight]);
    p.querySelectorAll('.tx > *').forEach(e=>{const r=e.getBoundingClientRect();if(r.right>pr.right+1||(r.bottom-pr.top)/sc>1044-40)over.push([i+1,e.tagName,Math.round((r.bottom-pr.top)/sc)])});
    p.querySelectorAll('.tx p, .tx li, .tx pre, .tx .verse').forEach(e=>{if(e.scrollWidth>e.clientWidth+1)over.push([i+1,'wide',e.tagName])})});
  return {n:pages.length,over,pieces:window.__pieces,log:window.__log};
}"""
res = {}
with sync_playwright() as pw:
    br = pw.chromium.launch()
    for name, vp, touch in [("phone", dict(width=390, height=844), True), ("desk", dict(width=1440, height=900), False)]:
        ctx = br.new_context(viewport=vp, device_scale_factor=2, has_touch=touch, is_mobile=touch)
        pg = ctx.new_page(); errs = []; bad = []
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("response", lambda r: bad.append((r.status, r.url)) if r.status >= 400 else None)
        t0 = time.time(); pg.goto(url); pg.wait_for_selector("#loading", state="detached", timeout=180000); dt = time.time() - t0
        # move every page into a measurable spot: the store is off-screen but laid out at full size
        r = pg.evaluate(CHECK)
        # pictures: force-load every one and check it decoded
        imgs = pg.evaluate("""async()=>{const im=[...document.querySelectorAll('.page img')];im.forEach(i=>i.loading='eager');
          await Promise.all(im.map(i=>i.complete?0:new Promise(r=>{i.onload=i.onerror=r})));return im.filter(i=>!i.naturalWidth).map(i=>i.src)}""")
        # contents links: each lands on the page whose first piece is that slug
        toc = pg.evaluate("""()=>[...document.querySelectorAll('.page.contents a[data-p]')].map(a=>[a.textContent.trim(),+a.dataset.p])""")
        pieces = r["pieces"]; wrong = []
        slugs = [x["slug"] for x in pg.evaluate("window.ISSUE")]
        for (t, p), s in zip(toc, slugs):
            if s not in (pieces[p - 1] or "").split(" ") or any(s in (pieces[k] or "").split(" ") for k in range(p - 1)): wrong.append((t, p, s))
        # navigation: arrow keys / swipe, then a contents link through the menu
        before = pg.inner_text("#pg")
        if touch:
            pg.evaluate("""()=>{const v=document.querySelector('#view');const T=(x)=>new Touch({identifier:1,target:v,clientX:x,clientY:400});
              v.dispatchEvent(new TouchEvent('touchstart',{touches:[T(320)],changedTouches:[T(320)],bubbles:true}));
              v.dispatchEvent(new TouchEvent('touchend',{touches:[],changedTouches:[T(120)],bubbles:true}))}""")
        else: pg.keyboard.press("ArrowRight")
        after = pg.inner_text("#pg")
        if not touch: pg.keyboard.press("ArrowLeft")
        back = pg.inner_text("#pg")
        pg.click("#tocbtn"); pg.click("#toc a[data-p]:nth-of-type(10)"); menu = pg.inner_text("#pg")
        res[name] = dict(load_s=round(dt, 1), pages=r["n"], errors=errs, http_bad=bad[:10], overflow=r["over"], broken_imgs=imgs, toc_wrong=wrong,
                         nav=[before, after, back, menu])
        # sample screenshots: cover, contents, each year opener, then a spread every so often, and the last
        n = r["n"]; yrs = [i + 1 for i, s in enumerate(pieces) if (s or "").startswith("movement:")]
        shots = sorted({1, 2, 3, n} | set(yrs) | set(range(4, n, 12)) | {y + 1 for y in yrs})
        pg.evaluate("document.querySelectorAll('.page img').forEach(i=>i.loading='eager')")
        for k in shots:
            pg.evaluate(f"""()=>{{const a=document.createElement('a');a.dataset.p={k};document.body.appendChild(a);a.click();a.remove()}}""")
            pg.wait_for_timeout(150); pg.screenshot(path=f"{OUT}/{name}-p{k:03d}.png")
        ctx.close()
    br.close()
if srv: srv.terminate()
print(json.dumps(res, indent=1, ensure_ascii=False))
