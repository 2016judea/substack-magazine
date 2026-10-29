#!/usr/bin/env python3
"""Static instances of Source Serif 4 (OFL, google/fonts main) at the optical sizes the magazine
uses, plus Source Code Pro for his code blocks. One family throughout; the optical size changes
with the point size, the way the face was drawn to be used. Static TrueType so Chromium embeds
plain subsets with distinct names (updateFontNames=True, else every weight embeds as -Regular).

  python3 scripts/make_fonts.py      -> fonts/*.ttf
"""
import os, urllib.request
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

D = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fonts")
S = f"{D}/src"; os.makedirs(S, exist_ok=True)
GH = "https://raw.githubusercontent.com/google/fonts/main/ofl/"
SRC = {"R": "sourceserif4/SourceSerif4%5Bopsz,wght%5D.ttf", "I": "sourceserif4/SourceSerif4-Italic%5Bopsz,wght%5D.ttf",
       "M": "sourcecodepro/SourceCodePro%5Bwght%5D.ttf", "E": "notoemoji/NotoEmoji%5Bwght%5D.ttf"}
for k, f in SRC.items():
    out = f"{S}/{os.path.basename(f).replace('%5B', '[').replace('%5D', ']')}"
    if not os.path.exists(out): urllib.request.urlretrieve(GH + f, out)
    SRC[k] = out
for lic, f in (("OFL-sourceserif4.txt", "sourceserif4/OFL.txt"), ("OFL-sourcecodepro.txt", "sourcecodepro/OFL.txt"), ("OFL-notoemoji.txt", "notoemoji/OFL.txt")):
    if not os.path.exists(f"{D}/{lic}"): urllib.request.urlretrieve(GH + f, f"{D}/{lic}")

# name: (source, {axis: value})
OUT = {
    "SSText-Regular": ("R", dict(opsz=10, wght=400)), "SSText-Italic": ("I", dict(opsz=10, wght=400)),
    "SSText-Semibold": ("R", dict(opsz=10, wght=600)), "SSText-SemiboldItalic": ("I", dict(opsz=10, wght=600)),
    "SSCap-Regular": ("R", dict(opsz=8, wght=400)), "SSCap-Italic": ("I", dict(opsz=8, wght=400)),
    "SSDeck-Regular": ("R", dict(opsz=18, wght=400)), "SSDeck-Italic": ("I", dict(opsz=18, wght=400)),
    "SSDeck-Semibold": ("R", dict(opsz=18, wght=600)),
    "SSHead-Italic": ("I", dict(opsz=18, wght=400)),   # = SSDeck-Italic, named apart so the fitter can tell a heading
    "SSDisp-Light": ("R", dict(opsz=60, wght=300)), "SSDisp-Regular": ("R", dict(opsz=60, wght=400)),
    "SSDisp-Semibold": ("R", dict(opsz=60, wght=600)), "SSDisp-Bold": ("R", dict(opsz=60, wght=700)),
    "SSDisp-LightItalic": ("I", dict(opsz=60, wght=300)), "SSDisp-Italic": ("I", dict(opsz=60, wght=400)),
    "SCP-Regular": ("M", dict(wght=400)), "NotoEmoji-Regular": ("E", dict(wght=400)),
}
for name, (k, ax) in OUT.items():
    s = instantiateVariableFont(TTFont(SRC[k]), ax, inplace=False, updateFontNames=True)
    # unique family per instance so Chromium cannot substitute one for another
    for rec in s["name"].names:
        if rec.nameID in (1, 16): rec.string = name.split("-")[0] + "-" + name.split("-")[1]
        if rec.nameID in (4, 6): rec.string = name
    s.save(f"{D}/{name}.ttf"); print(name)
