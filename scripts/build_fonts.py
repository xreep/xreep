#!/usr/bin/env python3
"""Fetch JetBrains Mono (SIL OFL) and subset it into base64 woff2 -> fonts/b64.json.
Run locally or in CI. Needs: pip install fonttools brotli"""
import base64, io, json, urllib.request
from pathlib import Path
from fontTools import subset

ROOT = Path(__file__).resolve().parent.parent
F = ROOT / "fonts"
BASE = "https://raw.githubusercontent.com/JetBrains/JetBrainsMono/master/"
RAMP = " .`:-=+*cs#%@"
LATIN = "".join(chr(c) for c in range(32, 127)) + "\u00b7\u2013\u2014"
HEADINGS = "about stats year languages projects"

def fetch(name, url):
    p = F / name
    if not p.exists():
        F.mkdir(exist_ok=True)
        p.write_bytes(urllib.request.urlopen(url, timeout=60).read())
    return p

def sub(src, text):
    o = subset.Options()
    o.flavor, o.layout_features, o.hinting = "woff2", [], False
    font = subset.load_font(str(src), o)
    s = subset.Subsetter(o); s.populate(text=text); s.subset(font)
    buf = io.BytesIO(); subset.save_font(font, buf, o)
    return base64.b64encode(buf.getvalue()).decode()

if __name__ == "__main__":
    reg = fetch("JetBrainsMono-Regular.ttf", BASE + "fonts/ttf/JetBrainsMono-Regular.ttf")
    bold = fetch("JetBrainsMono-Bold.ttf", BASE + "fonts/ttf/JetBrainsMono-Bold.ttf")
    fetch("OFL.txt", BASE + "OFL.txt")
    out = {"ramp": sub(reg, RAMP), "latin_r": sub(reg, LATIN),
           "latin_b": sub(bold, LATIN), "headings": sub(bold, HEADINGS)}
    (F / "b64.json").write_text(json.dumps(out))
    for k, v in out.items():
        print(f"{k:9s} {len(v) * 3 // 4 / 1024:.1f} KB")
