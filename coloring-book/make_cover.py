"""Build the full-color KDP paperback cover (back + spine + front, with bleed).

    python3 coloring-book/make_cover.py [--pages 32] [--paper white|cream]

Writes coloring-book/kdp/cover.pdf and a front-cover preview PNG
(coloring-book/kdp/front-cover-preview.png, needs pdftoppm).

KDP cover math (paperback, black ink interior):
  spine  = pages x 0.002252 in (white paper) or 0.0025 in (cream)
  width  = 0.125 bleed + 8.5 back + spine + 8.5 front + 0.125 bleed
  height = 0.125 bleed + 11 + 0.125 bleed
Books under 79 pages may not have spine text, so the spine is left plain.
The lower right of the back cover is left clear for KDP's barcode.
"""

import argparse
import os
import shutil
import subprocess

from reportlab.lib.colors import HexColor, white
from reportlab.pdfgen import canvas

import make_coloring_book as B

IN = 72
BLEED = 0.125 * IN
TRIM_W, TRIM_H = 8.5 * IN, 11 * IN
SPINE_PER_PAGE = {"white": 0.002252, "cream": 0.0025}

SKY_TOP = HexColor("#0B1640")
SKY_MID = HexColor("#22306E")
SKY_LOW = HexColor("#5B3C8C")
GOLD = HexColor("#FFC93C")
GOLD_DK = HexColor("#E89B12")
CREAM = HexColor("#FFF6DC")
RED = HexColor("#C8202F")
RED_DK = HexColor("#8E1220")
GREEN = HexColor("#3E9B47")
GREEN_DK = HexColor("#2A6E34")
NAVY = HexColor("#13204F")
SKIN = HexColor("#F3C9A1")

MARY = dict(robe=HexColor("#6FA8E8"), hood=HexColor("#2F62B8"), sleeve=HexColor("#6FA8E8"),
            belt=HexColor("#FFFFFF"), skin=SKIN, halo=GOLD)
JOSEPH = dict(robe=HexColor("#B9773D"), hood=HexColor("#E7B866"), sleeve=HexColor("#B9773D"),
              belt=HexColor("#7A4A1F"), skin=SKIN, beard=HexColor("#6B4423"),
              staff=HexColor("#9C6B3C"))
ANGEL = dict(robe=white, sleeve=white, belt=GOLD, wing=HexColor("#FFF3C4"),
             hair=HexColor("#F2B84B"), skin=SKIN, halo=GOLD, halo_in=GOLD, trumpet=GOLD)
SHEEP = dict(wool=HexColor("#FFFDF5"), sheepface=HexColor("#F2D7C0"), legs=HexColor("#5A4636"))
MANGER = dict(wood=HexColor("#9A5E2A"), hay=HexColor("#F4C542"), swaddle=white,
              skin=SKIN, halo=GOLD)
STABLE = dict(wall=HexColor("#F8D98F"), wood=HexColor("#8A5428"), roof=HexColor("#6E3F1C"))
NIGHT = dict(star=GOLD, bstar=GOLD, bstar_c=white, hills=GREEN, leaf=GREEN_DK,
             berry=RED, heart=RED, cloud=white, trunk=HexColor("#9A6A3A"),
             frond=HexColor("#3C8D3F"), coconut=HexColor("#6B4423"))


def mix(a, b, t):
    return HexColor("#%02X%02X%02X" % tuple(
        round((getattr(a, k) * (1 - t) + getattr(b, k) * t) * 255) for k in ("red", "green", "blue")))


def sky_at(y, total_h):
    t = max(0.0, min(1.0, y / total_h))
    return mix(SKY_LOW, SKY_MID, t / 0.5) if t < 0.5 else mix(SKY_MID, SKY_TOP, (t - 0.5) / 0.5)


def text_fill(x, y, text, font, size, color, align="center"):
    c = B.c
    c.setFillColor(color)
    c.setFont(font, size)
    {"center": c.drawCentredString, "left": c.drawString,
     "right": c.drawRightString}[align](x, y, text)


def outlined(x, y, text, font, size, fill, edge, halo=white, edge_w=3.0, halo_w=10.0, space=1.0):
    """Bold title lettering: a wide halo stroke, then the colored letters."""
    c = B.c
    tw = c.stringWidth(text, font, size) + space * (len(text) - 1)
    for mode, col, wid in ((1, halo, halo_w), (2, fill, edge_w)):
        c.saveState()
        t = c.beginText()
        t.setTextRenderMode(mode)
        t.setFont(font, size)
        t.setCharSpace(space)
        t.setTextOrigin(x - tw / 2, y)
        t.textLine(text)
        c.setLineJoin(1)
        c.setLineWidth(wid)
        c.setStrokeColor(halo if mode == 1 else edge)
        c.setFillColor(col)
        c.drawText(t)
        c.restoreState()


def fit_size(text, font, size, maxw):
    while B.c.stringWidth(text, font, size) > maxw and size > 10:
        size -= 1
    return size


def ribbon(cx, cy, w, h, text, color=RED, dark=RED_DK):
    c = B.c
    c.setStrokeColor(HexColor("#000000"))
    c.setLineWidth(2.5)
    c.setLineJoin(1)
    tail = h * 0.9
    for side in (-1, 1):
        x0 = cx + side * (w / 2 - tail * 0.4)
        x1 = cx + side * (w / 2 + tail)
        c.setFillColor(dark)
        B.poly([(x0, cy - h / 2 - 8), (x1, cy - h / 2 - 8), (x1 - side * tail * 0.45, cy - 8 + 0),
                (x1, cy + h / 2 - 8), (x0, cy + h / 2 - 8)])
    c.setFillColor(color)
    B.rect(cx - w / 2, cy - h / 2, w, h, 6)
    size = fit_size(text, "Title", 24, w - 30)
    text_fill(cx, cy - size * 0.35, text, "Title", size, white)


def stars_field(x0, y0, w, h, seed):
    """Little gold stars and white specks scattered over the sky."""
    import random
    rnd = random.Random(seed)
    c = B.c
    c.setStrokeColor(HexColor("#000000"))
    for _ in range(int(w * h / 9000)):
        x, y = x0 + rnd.random() * w, y0 + rnd.random() * h
        if rnd.random() < 0.35:
            c.setLineWidth(1.6)
            with B.palette(star=GOLD):
                B.star(x, y, rnd.uniform(5, 9))
        else:
            c.setFillColor(CREAM)
            c.circle(x, y, rnd.uniform(0.8, 1.8), stroke=0, fill=1)


def glow(cx, cy, r, total_h, color=HexColor("#FFE58A")):
    """A soft halo made with a radial blend into the sky (no transparency)."""
    c = B.c
    c.saveState()
    p = c.beginPath()
    p.circle(cx, cy, r)
    c.clipPath(p, stroke=0, fill=0)
    c.radialGradient(cx, cy, r, (color, sky_at(cy, total_h)), extend=False)
    c.restoreState()


# ---------------------------------------------------------------- front

def ground(off, pts, color):
    """A hill that runs from the back cover's bleed edge to the front's."""
    c = B.c
    right = TRIM_W + BLEED
    p = c.beginPath()
    p.moveTo(-off, -BLEED)
    p.lineTo(-off, pts[0])
    p.curveTo(-off * 0.5, pts[0], -150, pts[1] - 60, 0, pts[1])
    p.curveTo(120, pts[1] + 50, 200, pts[2] + 5, 330, pts[2])
    p.curveTo(450, pts[2] - 5, 520, pts[3] + 5, right, pts[3])
    p.lineTo(right, -BLEED)
    p.close()
    c.setFillColor(color)
    c.setStrokeColor(HexColor("#000000"))
    c.setLineWidth(B.LW)
    c.drawPath(p, fill=1, stroke=1)


def front(total_h, spine):
    """Front cover in trim coordinates (0..612 x 0..792), drawn with bleed overhang."""
    c = B.c
    B.reset()
    off = TRIM_W + spine + BLEED  # distance to the back cover's outer bleed edge
    ground(off, (70, 190, 295, 235), GREEN_DK)
    with B.palette(**NIGHT):
        B.palm(30, 205, 190)
        B.palm(520, 200, 170)
    ground(off, (40, 120, 190, 170), GREEN)

    glow(306, 520, 95, total_h)
    with B.palette(**NIGHT):
        B.bstar(306, 520, 46)

    with B.palette(**STABLE):
        B.stable(110, 140, 392, 300)
    with B.palette(**MARY):
        B.person(195, 140, 175, hood=True, arm_mode="pray", halo=True)
    with B.palette(**JOSEPH):
        B.person(420, 140, 190, beard=True, headcloth=True, staff=True)
    with B.palette(**MANGER):
        B.manger(306, 140, 140)

    with B.palette(**SHEEP):
        B.sheep(80, 55, 85)
        B.sheep(540, 60, 75, flip=True)
    with B.palette(**NIGHT):
        for gx, gy in ((250, 120), (380, 110), (470, 130), (40, 70)):
            B.grass(gx, gy)

    # title block
    outlined(306, 682, "Jesus Is Born!", "Title",
             fit_size("Jesus Is Born!", "Title", 84, 520), GOLD, RED_DK,
             halo=white, edge_w=3, halo_w=12)
    ribbon(306, 620, 430, 40, "A Christmas Coloring Book of Bible Verses")

    # bottom banner + age badge
    c.setLineWidth(2.5)
    c.setStrokeColor(HexColor("#000000"))
    c.setFillColor(CREAM)
    B.rect(120, 30, 372, 38, 19)
    text_fill(306, 43, "The Nativity Story in 12 Pictures to Color", "Round", 16.5, NAVY)
    c.setFillColor(RED)
    bx, by = 532, 545
    c.circle(bx, by, 40, stroke=1, fill=1)
    c.setStrokeColor(GOLD)
    c.setLineWidth(2)
    c.circle(bx, by, 34, stroke=1, fill=0)
    text_fill(bx, by + 7, "Ages", "Title", 15, white)
    text_fill(bx, by - 15, "4-8", "Title", 22, white)


# ---------------------------------------------------------------- back

def thumb(x, y, w, h, art, caption):
    """A small black-and-white preview of an inside page."""
    c = B.c
    c.setLineWidth(2.5)
    c.setStrokeColor(HexColor("#000000"))
    c.setFillColor(white)
    B.rect(x, y, w, h, 10)
    c.saveState()
    p = c.beginPath()
    p.roundRect(x + 4, y + 4, w - 8, h - 8, 7)
    c.clipPath(p, stroke=0, fill=0)
    s = (w - 16) / B.AW
    c.translate(x + 8, y + 26)
    c.scale(s, s)
    B.reset()
    old, B.PAL = B.PAL, {}
    art()
    B.PAL = old
    c.restoreState()
    text_fill(x + w / 2, y + 9, caption, "Round", 10.5, NAVY)


def back():
    c = B.c
    B.reset()
    outlined(306, 718, "Share the True Meaning", "Title", 36, GOLD, RED_DK,
             halo=white, edge_w=2, halo_w=8)
    outlined(306, 676, "of Christmas!", "Title", 36, GOLD, RED_DK,
             halo=white, edge_w=2, halo_w=8)

    # blurb card
    c.setLineWidth(2.5)
    c.setStrokeColor(HexColor("#000000"))
    c.setFillColor(CREAM)
    B.rect(54, 430, 504, 220, 16)
    blurb = ("Color your way through the Christmas story, straight from the Bible! "
             "From God’s promise of a Savior to the angel’s visit, the manger in "
             "Bethlehem, the shepherds, and the wise men following the star, every "
             "page helps kids learn why we celebrate.")
    from reportlab.lib.utils import simpleSplit
    y = 622
    for ln in simpleSplit(blurb, "Sans", 13.5, 456):
        text_fill(306, y, ln, "Sans", 13.5, NAVY)
        y -= 18
    y -= 8
    items = ["12 big, easy-to-color Bible story pictures",
             "A King James Bible verse on every page",
             "A faith theme and a “Think about it” question",
             "One picture per sheet, so markers won’t bleed through",
             "“Draw Your Favorite Part” and “My Christmas Prayer” pages"]
    for it in items:
        c.setLineWidth(1.4)
        with B.palette(star=GOLD):
            B.star(100, y + 4.5, 7.5)
        text_fill(116, y, it, "Sans-Bold", 12.5, NAVY, align="left")
        y -= 21

    # look inside
    text_fill(306, 398, "Look inside!", "Title", 20, GOLD)
    tw, th = 150, 150
    for i, (art, cap) in enumerate(((B.art_nativity, "Born in a Manger"),
                                    (B.art_glory, "Glory to God!"),
                                    (B.art_wisemen, "Following the Star"))):
        thumb(66 + i * (tw + 15), 220, tw, th, art, cap)

    # verse, kept left of the barcode area (KDP: lower right, ~2 x 1.2 in)
    text_fill(48, 190, "“Fear not: for, behold, I bring you good", "Serif-Italic", 15,
              CREAM, align="left")
    text_fill(48, 171, "tidings of great joy, which shall be to all", "Serif-Italic", 15,
              CREAM, align="left")
    text_fill(48, 152, "people.”", "Serif-Italic", 15, CREAM, align="left")
    text_fill(48, 130, "— Luke 2:10", "Sans-Bold", 12.5, GOLD, align="left")
    with B.palette(leaf=GREEN, berry=RED):
        B.holly(70, 40, 38)
        B.holly(130, 40, 38, flip=True)


# ---------------------------------------------------------------- assemble

def build(pages=32, paper="white", out=None):
    B.register_fonts()
    out = out or os.path.join(B.HERE, "kdp", "cover.pdf")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    spine = pages * SPINE_PER_PAGE[paper] * IN
    full_w = 2 * BLEED + 2 * TRIM_W + spine
    full_h = 2 * BLEED + TRIM_H
    c = B.c = canvas.Canvas(out, pagesize=(full_w, full_h), initialFontName="Sans")
    c.setTitle(f"{B.BOOK_TITLE} {B.BOOK_SUBTITLE} - cover")

    # one continuous night sky across back, spine and front
    c.linearGradient(0, 0, 0, full_h, (SKY_LOW, SKY_MID, SKY_TOP), (0, 0.5, 1), extend=True)
    stars_field(0, full_h * 0.35, full_w, full_h * 0.65, seed=7)

    c.saveState()
    c.translate(BLEED + TRIM_W + spine, BLEED)
    front(full_h, spine)
    c.restoreState()
    c.saveState()
    c.translate(BLEED, BLEED)
    back()
    c.restoreState()
    c.save()

    preview = None
    if shutil.which("pdftoppm"):
        base = os.path.join(os.path.dirname(out), "front-cover-preview")
        dpi = 150
        x = int((BLEED + TRIM_W + spine) / IN * dpi)
        subprocess.run(["pdftoppm", "-png", "-r", str(dpi), "-singlefile",
                        "-x", str(x), "-y", str(int(BLEED / IN * dpi)),
                        "-W", str(int(8.5 * dpi)), "-H", str(int(11 * dpi)), out, base], check=True)
        preview = base + ".png"
    return out, full_w / IN, full_h / IN, spine / IN, preview


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Build the KDP wraparound cover.")
    ap.add_argument("--pages", type=int, default=32, help="interior page count")
    ap.add_argument("--paper", choices=sorted(SPINE_PER_PAGE), default="white")
    a = ap.parse_args()
    out, w, h, s, prev = build(a.pages, a.paper)
    print(f"Wrote {out}: {w:.4f} x {h:.4f} in, spine {s:.4f} in")
    if prev:
        print("Preview", prev)
