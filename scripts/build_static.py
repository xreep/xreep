#!/usr/bin/env python3
"""Draw the section headings (assets/hd-*.svg). Standard library only."""
from svgkit import ROOT, svg, write_if_changed

W, H, SIZE = 800, 36, 14
for name in ("about", "stats", "year", "languages", "activity", "projects"):
    tw = len(name) * SIZE * 0.6
    body = (f'<text x="0" y="24" font-size="{SIZE}" font-weight="700" class="fg">{name}</text>'
            f'<line x1="{tw + 14:.1f}" y1="19" x2="{W}" y2="19" class="rule" stroke-width="1"/>')
    out = svg(W, H, body, fonts=(("headings", 700),), label=name)
    write_if_changed(ROOT / "assets" / f"hd-{name}.svg", out)
    print("hd-%s.svg" % name)
