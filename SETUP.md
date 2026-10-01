# Setup

1. Actions > "bootstrap profile" > Run workflow. It downloads JetBrains Mono, subsets it,
   draws the headings and a placeholder portrait, then fills in the stats and the project list.
2. After that, "refresh profile" runs nightly at 05:17 UTC and keeps the stats current.
3. Portrait: replace the placeholder with a real one. Side-lit, tight crop, 1200px+.
   pip install pillow numpy opencv-python-headless rembg onnxruntime
   python3 scripts/portrait.py photo.jpg
   Commit assets/portrait.svg.

Notes
- Projects: every public repo is listed, forks and archived included. Nothing collapsed or cut off.
- Private repos cannot appear: the workflow token only sees public data.
- Language bars skip forks (set LANGS_INCLUDE_FORKS = True in scripts/generate_stats.py to count them).
- Fonts: JetBrains Mono, SIL OFL. The licence is fetched to fonts/OFL.txt by the bootstrap job.
