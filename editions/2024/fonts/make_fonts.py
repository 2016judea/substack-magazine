"""Static instances of the two OFL variable families (google/fonts main), so Chromium embeds
plain TrueType subsets in the PDF rather than a variable font."""
import os
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
D=os.path.dirname(os.path.abspath(__file__))
import urllib.request, urllib.parse
GF="https://raw.githubusercontent.com/google/fonts/main/ofl/"
SRCS={"ofl_bricolagegrotesque_BricolageGrotesque[opsz,wdth,wght].ttf":"bricolagegrotesque/BricolageGrotesque[opsz,wdth,wght].ttf",
 "ofl_newsreader_Newsreader[opsz,wght].ttf":"newsreader/Newsreader[opsz,wght].ttf",
 "ofl_newsreader_Newsreader-Italic[opsz,wght].ttf":"newsreader/Newsreader-Italic[opsz,wght].ttf",
 "NotoSerif.ttf":"notoserif/NotoSerif[wdth,wght].ttf","NotoEmoji.ttf":"notoemoji/NotoEmoji[wght].ttf"}
os.makedirs(f"{D}/src",exist_ok=True)
for fn,path in SRCS.items():   # all SIL OFL 1.1, from google/fonts
    if not os.path.exists(f"{D}/src/{fn}"): urllib.request.urlretrieve(GF+urllib.parse.quote(path),f"{D}/src/{fn}")
B=f"{D}/src/ofl_bricolagegrotesque_BricolageGrotesque[opsz,wdth,wght].ttf"
N=f"{D}/src/ofl_newsreader_Newsreader[opsz,wght].ttf"
NI=f"{D}/src/ofl_newsreader_Newsreader-Italic[opsz,wght].ttf"
OUT={
 "Display-XBold": (B,dict(opsz=96,wdth=75,wght=800)),
 "Display-Bold":  (B,dict(opsz=48,wdth=75,wght=700)),
 "Label-Semi":    (B,dict(opsz=12,wdth=100,wght=600)),
 "Label-Reg":     (B,dict(opsz=12,wdth=100,wght=400)),
 "Text-Reg":      (N,dict(opsz=10,wght=400)),
 "Text-Bold":     (N,dict(opsz=10,wght=620)),
 "Text-Italic":   (NI,dict(opsz=10,wght=400)),
 "Deck-Italic":   (NI,dict(opsz=36,wght=380)),
 "Deck-Reg":      (N,dict(opsz=36,wght=380)),
 "Deck-BoldItalic": (NI,dict(opsz=36,wght=600)),
 "Text-BoldItalic": (NI,dict(opsz=10,wght=620)),
}
for name,(src,loc) in OUT.items():
    f=TTFont(src); s=instantiateVariableFont(f,loc,inplace=False)
    s.save(f"{D}/{name}.ttf"); print(name)

# Fallback glyphs his text uses that the two families lack: U+2015 (Noto Serif) and U+1F680 (Noto Emoji), both OFL.
from fontTools import subset
def sub(src, loc, chars, out):
    f = TTFont(src); f = instantiateVariableFont(f, loc, inplace=False)
    o = subset.Options(); o.layout_features = []; s = subset.Subsetter(o); s.populate(unicodes=chars); s.subset(f); f.save(out); print(out)
sub(f"{D}/src/NotoSerif.ttf", dict(wght=400, wdth=100), [0x2015], f"{D}/Fallback-Bar.ttf")
sub(f"{D}/src/NotoEmoji.ttf", dict(wght=400), [0x1F680], f"{D}/Fallback-Emoji.ttf")
