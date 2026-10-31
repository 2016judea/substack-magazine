#!/usr/bin/env python3
"""Run checks.js over every page at phone and desktop size; exit 1 if any rule is broken.
   python3 web/check.py [url]   (default: serves web/public)"""
import json, os, subprocess, sys, time
from playwright.sync_api import sync_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
url = sys.argv[1] if len(sys.argv) > 1 else None; srv = None
if not url:
    srv = subprocess.Popen([sys.executable, "-m", "http.server", "8766", "-d", f"{HERE}/public"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1); url = "http://localhost:8766/"
JS = open(f"{HERE}/checks.js").read()
fail = 0
with sync_playwright() as pw:
    br = pw.chromium.launch()
    for name, vp in [("desk", dict(width=1440, height=900)), ("single", dict(width=820, height=1100))]:
        pg = br.new_page(viewport=vp); pg.goto(url); pg.wait_for_selector("#loading", state="detached", timeout=120000)
        r = pg.evaluate(JS); n = pg.evaluate("document.querySelectorAll('.page').length")
        print(name, n, "pages ·", " ".join(f"{k}={len(v)}" for k, v in r.items()))
        for k, v in r.items():
            for x in v[:40]: print("  ", k, x)
        fail += sum(len(v) for k, v in r.items() if k != "hole")
        pg.close()
    br.close()
if srv: srv.terminate()
sys.exit(1 if fail else 0)
