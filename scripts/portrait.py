#!/usr/bin/env python3
"""Photo -> self-typing ASCII portrait (assets/portrait.svg).
Real portrait needs: pip install pillow numpy opencv-python-headless rembg onnxruntime
  python3 scripts/portrait.py photo.jpg
  python3 scripts/portrait.py --placeholder xreep   # pillow + numpy only"""
import argparse
import numpy as np
from PIL import Image
from svgkit import ROOT, CHAR_W, FONT_SIZE, RAMP, svg, write_if_changed

LH = 13.6        # line height

def enhance(gray):
    import cv2
    g = cv2.bilateralFilter(gray, 9, 40, 40)
    g = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8)).apply(g)
    return ((g / 255.0) ** 1.7 * 255).astype(np.uint8)       # darkening curve

def to_rows(gray, cols):
    h, w = gray.shape
    rows = max(1, round(cols * (h / w) * 0.48))
    small = np.asarray(Image.fromarray(gray).resize((cols, rows), Image.LANCZOS)) / 255.0
    idx = np.clip(((1 - small) * (len(RAMP) - 1)).round().astype(int), 0, len(RAMP) - 1)
    return ["".join(RAMP[i] for i in r).rstrip() for r in idx]

def typing_svg(lines, cols, display=460):
    W, H = cols * CHAR_W, len(lines) * LH + 4
    body, dur, stag = "", 0.9, 0.09
    for i, ln in enumerate(lines):
        b, y = i * stag, i * LH
        body += (f'<clipPath id="c{i}"><rect x="0" y="{y:.1f}" width="0" height="{LH}">'
                 f'<animate attributeName="width" from="0" to="{W:.1f}" dur="{dur}s" begin="{b:.2f}s" fill="freeze"/>'
                 f'</rect></clipPath>'
                 f'<text x="0" y="{y + LH - 3:.1f}" font-size="{FONT_SIZE}" class="fg" xml:space="preserve" '
                 f'clip-path="url(#c{i})">{ln}</text>'
                 f'<rect y="{y + 1:.1f}" width="{CHAR_W}" height="{LH - 3}" class="accf" opacity="0">'
                 f'<set attributeName="opacity" to="1" begin="{b:.2f}s"/>'
                 f'<animate attributeName="x" from="0" to="{W:.1f}" dur="{dur}s" begin="{b:.2f}s" fill="freeze"/>'
                 f'<set attributeName="opacity" to="0" begin="{b + dur:.2f}s" fill="freeze"/></rect>')
    out = svg(round(W), round(H), body, fonts=(("ramp", 400),), label="ASCII portrait")
    return out.replace(f'width="{round(W)}" height="{round(H)}"', f'width="{display}" height="{round(display * H / W)}"', 1)

def cutout(path):
    from rembg import remove
    rgba = remove(Image.open(path).convert("RGB")).convert("RGBA")
    bg = Image.new("RGBA", rgba.size, (255, 255, 255, 255)); bg.alpha_composite(rgba)
    return np.array(bg.convert("L"))

def placeholder(text):
    from PIL import ImageDraw, ImageFont
    f = ImageFont.truetype(str(ROOT / "fonts" / "JetBrainsMono-Bold.ttf"), 360)
    im = Image.new("L", (1500, 520), 255); d = ImageDraw.Draw(im)
    box = d.textbbox((0, 0), text, font=f)
    d.text(((1500 - box[2] + box[0]) // 2 - box[0], (520 - box[3] + box[1]) // 2 - box[1]), text, font=f, fill=0)
    return np.array(im)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("photo", nargs="?"); ap.add_argument("--placeholder")
    ap.add_argument("--cols", type=int, default=90); ap.add_argument("--no-cutout", action="store_true")
    a = ap.parse_args()
    if a.placeholder:
        g = placeholder(a.placeholder)
    elif a.photo:
        g = enhance(np.array(Image.open(a.photo).convert("L")) if a.no_cutout else cutout(a.photo))
    else:
        ap.error("give a photo or --placeholder TEXT")
    lines = to_rows(g, a.cols)
    write_if_changed(ROOT / "assets" / "portrait.svg", typing_svg(lines, a.cols))
    print(f"portrait.svg: {a.cols} cols x {len(lines)} rows")
