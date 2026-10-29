#!/usr/bin/env python3
"""Instance Instrument Sans (a variable font) into static TTFs. Chromium embeds a variable font in a
PDF as Type 3 glyph procedures; static instances embed as ordinary TrueType, which presses prefer."""
import os
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer
F = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fonts")
for src, style in (("InstrumentSans-VF.ttf", ""), ("InstrumentSans-Italic-VF.ttf", "Italic")):
    for wght in (400, 500, 600):
        dst = f"{F}/InstrumentSans-{wght}{style}.ttf"
        if os.path.exists(dst): continue
        f = instancer.instantiateVariableFont(TTFont(f"{F}/{src}"), {"wght": wght, "wdth": 100}, updateFontNames=True)
        f.save(dst); print(dst)
