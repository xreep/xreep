"""Shared SVG helpers. Standard library only."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FONTS = json.loads((ROOT / "fonts" / "b64.json").read_text())

CHAR_W = 7.74          # 0.600 em advance at font-size 12.9
FONT_SIZE = 12.9
RAMP = " .`:-=+*cs#%@"

BASE_CSS = """
text{font-family:JB,'JetBrains Mono','DejaVu Sans Mono','Liberation Mono',monospace}
.fg{fill:#1f2328}.dim{fill:#656d76}.acc{fill:#0969da}
.rule{stroke:#d0d7de}.accs{stroke:#0969da}.accf{fill:#0969da}
@media (prefers-color-scheme:dark){
.fg{fill:#e6edf3}.dim{fill:#8b949e}.acc{fill:#58a6ff}
.rule{stroke:#30363d}.accs{stroke:#58a6ff}.accf{fill:#58a6ff}}
"""

def font_face(key, weight):
    return ("@font-face{font-family:JB;font-weight:%d;"
            "src:url(data:font/woff2;base64,%s) format('woff2')}" % (weight, FONTS[key]))

def svg(w, h, body, fonts=(("latin_r", 400), ("latin_b", 700)), label=""):
    css = "".join(font_face(k, wt) for k, wt in fonts) + BASE_CSS
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
            f'width="{w}" height="{h}" role="img" aria-label="{label}">'
            f'<title>{label}</title><style>{css}</style>{body}</svg>\n')

def write_if_changed(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text() == text:
        return False
    path.write_text(text)
    return True
