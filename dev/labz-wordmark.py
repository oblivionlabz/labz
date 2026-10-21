#!/usr/bin/env python3
"""dev/labz-wordmark.py — generate the OBLIVION LABZ topbar mark as a real vector wordmark.

Provenance law (the same law dev/trace-logo.mjs states): the brand IS its letterforms, so the
mark must be DERIVED from a named typeface, never hand-drawn and never traced out of a diffusion
raster. This emits the actual glyph outlines of Cinzel Bold (SIL OFL 1.1, bundled at
dev/fonts/ — dev-time only; the SVG is the shipped artifact, so no font weight rides in the
frontend bundle), so the letterforms are auditable against the font and reproducible.

The output satisfies the contract test/brand-wordmark-mask.test.js pins:
  - exactly one <svg> root, numeric viewBox, no doctype / no xml-stylesheet PI
  - no "--" inside any XML comment (XML forbids it; the mask silently renders nothing)
  - >=1 <path> with a d longer than 200 chars
  - fill="currentColor" so the masked <span> paints var(--ph) and re-tints with the theme

Usage:  python3 dev/labz-wordmark.py [out.svg] [--text="OBLIVION LABZ"] [--tracking=0.055]
"""
import sys
from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen

REPO = Path(__file__).resolve().parent.parent
FONT = REPO / "dev" / "fonts" / "Cinzel-Bold.ttf"

argv = sys.argv[1:]
flag = lambda name, dflt: next(
    (a.split("=", 1)[1] for a in argv if a.startswith(f"--{name}=")), dflt)
OUT = next((a for a in argv if not a.startswith("--")),
           REPO / "frontend" / "assets" / "brand" / "labz-wordmark.svg")
TEXT = flag("text", "OBLIVION LABZ")
TRACKING = float(flag("tracking", "0.055"))   # em; the fansite-era wordmark wants air
SPACE = float(flag("space", "0.34"))          # em; word space

font = TTFont(str(FONT))
upm = font["head"].unitsPerEm
cmap = font.getBestCmap()
glyphs = font.getGlyphSet()

missing = [c for c in TEXT if c != " " and ord(c) not in cmap]
if missing:
    raise SystemExit(f"font has no glyph for: {''.join(missing)}")

x = 0.0
placed = []
for ch in TEXT:
    if ch == " ":
        x += upm * SPACE + upm * TRACKING
        continue
    g = glyphs[cmap[ord(ch)]]
    pen = SVGPathPen(g)
    g.draw(pen)
    d = pen.getCommands()
    if d:
        placed.append((x, d))
    x += g.width + upm * TRACKING

# TRUE outline bounds, not sCapHeight: Cinzel's caps overshoot the cap-height metric, and sizing the
# viewBox from the metric puts the glyph tops at negative y — clipped to an invisible mark. (Measured:
# the first cut rendered 1x1 content because of exactly this.)
from fontTools.pens.boundsPen import BoundsPen


class _Offset:
    """Re-project a glyph's pen calls to a pen origin, so one bounds pass sees the whole line."""
    def __init__(self, target, dx):
        self.t, self.dx = target, dx

    def moveTo(self, pt): self.t.moveTo((pt[0] + self.dx, pt[1]))
    def lineTo(self, pt): self.t.lineTo((pt[0] + self.dx, pt[1]))
    def curveTo(self, *pts): self.t.curveTo(*[(p[0] + self.dx, p[1]) for p in pts])
    def qCurveTo(self, *pts): self.t.qCurveTo(*[(p[0] + self.dx, p[1]) for p in pts if p])
    def closePath(self): self.t.closePath()
    def endPath(self): self.t.endPath()
    def addComponent(self, name, transform): self.t.addComponent(name, transform)


bp = BoundsPen(glyphs)
cursor = 0.0
for ch in TEXT:
    if ch == " ":
        cursor += upm * SPACE + upm * TRACKING
        continue
    g = glyphs[cmap[ord(ch)]]
    g.draw(_Offset(bp, cursor))
    cursor += g.width + upm * TRACKING

if not bp.bounds:
    raise SystemExit("no outline bounds — nothing to emit")
x0, y0, x1, y1 = bp.bounds

width = x1 - x0
height = y1 - y0
scale = 1000.0 / width
vw, vh = width * scale, height * scale
fmt = lambda v: "%g" % round(v, 3)

# translate so (x0, y0) maps to the viewBox origin, flip y, then scale.
# svg_y must equal (y1 - font_y) * scale, and transform="translate(a b) scale(s -s)" evaluates to
# svg_y = -s*font_y + b, so b is POSITIVE y1*scale. (A negative b here put the whole mark below the
# viewBox — the invisible-mark failure mode this file exists to avoid.)
tx, ty = -x0 * scale, y1 * scale
body = "".join(
    f'<path fill="currentColor" transform="translate({fmt(tx + ox * scale)} {fmt(ty)}) '
    f'scale({fmt(scale)} {fmt(-scale)})" d="{d}"/>'
    for ox, d in placed)

svg = (
    f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {fmt(vw)} {fmt(vh)}" '
    f'role="img" aria-label="{TEXT}">'
    f"<title>{TEXT}</title>"
    f"{body}</svg>\n")

Path(OUT).write_text(svg, encoding="utf-8")
print(f"wrote {OUT}  viewBox {fmt(vw)}x{fmt(vh)}  paths {len(placed)}  bytes {len(svg)}")
