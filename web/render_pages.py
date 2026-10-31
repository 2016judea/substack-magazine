#!/usr/bin/env python3
"""Render every page of the built reader to web/qa/pages/pNNN.png at 820 px (single pages), for the
page-by-page inspection.  python3 web/render_pages.py [first last]"""
import os, subprocess, sys, time
from playwright.sync_api import sync_playwright
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = f"{HERE}/qa/pages"; os.makedirs(OUT, exist_ok=True)
srv = subprocess.Popen([sys.executable, "-m", "http.server", "8767", "-d", f"{HERE}/public"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); time.sleep(1)
with sync_playwright() as pw:
    br = pw.chromium.launch(); pg = br.new_page(viewport=dict(width=820, height=1100), device_scale_factor=1)
    pg.goto("http://localhost:8767/"); pg.wait_for_selector("#loading", state="detached")
    n = pg.evaluate("document.querySelectorAll('.page').length")
    a, z = (int(sys.argv[1]), int(sys.argv[2])) if len(sys.argv) > 2 else (1, n)
    for k in range(a, z + 1):
        pg.evaluate(f"()=>{{const a=document.createElement('a');a.dataset.p={k};document.body.appendChild(a);a.click();a.remove();document.querySelectorAll('#spread img').forEach(i=>i.loading='eager')}}")
        pg.wait_for_function("[...document.querySelectorAll('#spread img')].every(i=>i.complete)", timeout=20000)
        pg.wait_for_timeout(250); pg.locator("#spread .page").first.screenshot(path=f"{OUT}/p{k:03d}.png")
    br.close()
srv.terminate(); print(n, "pages")
