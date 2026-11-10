"""Generate the interior of a Christian Christmas coloring book for kids.

Every story page tells part of the Nativity story with a Bible verse (KJV,
public domain), a theme word, and a "Think about it" question for
families or Sunday school classes.

    python3 coloring-book/make_coloring_book.py [--author "Your Name"]

Writes coloring-book/kdp/interior.pdf, ready for Amazon KDP paperback:
8.5 x 11 in trim, no bleed, black ink, all fonts embedded, 32 pages.
Each coloring page is printed on a right-hand page with a color-test
page behind it so markers do not bleed into the next picture.
Requires: reportlab. Run make_cover.py afterwards for the color cover.
"""

import argparse
import math
import os

from reportlab.lib.colors import black, white
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import simpleSplit
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

W, H = letter
LW = 3.0
AX, AY, AW, AH = 50, 235, 512, 455  # art area on verse pages
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "kdp", "interior.pdf")
BOOK_TITLE = "Jesus Is Born!"
BOOK_SUBTITLE = "A Christmas Coloring Book of Bible Verses"
YEAR = 2026
# Shrink every page about its center so the art clears KDP's minimum
# margins (0.375 in gutter, 0.25 in outside) with room to spare: the
# outer frame lands about 0.5 in from every trim edge.
PAGE_SCALE = 0.94

_LIB = "/usr/share/fonts/truetype/liberation"
FONTS = {
    "Title": os.path.join(HERE, "fonts", "Fredoka-Bold.ttf"),
    "Round": os.path.join(HERE, "fonts", "Fredoka-Medium.ttf"),
    "Sans": os.path.join(_LIB, "LiberationSans-Regular.ttf"),
    "Sans-Bold": os.path.join(_LIB, "LiberationSans-Bold.ttf"),
    "Serif-Italic": os.path.join(_LIB, "LiberationSerif-Italic.ttf"),
    "Serif-Bold": os.path.join(_LIB, "LiberationSerif-Bold.ttf"),
    "Serif-BoldItalic": os.path.join(_LIB, "LiberationSerif-BoldItalic.ttf"),
}


def register_fonts():
    """KDP rejects PDFs with unembedded fonts, so every font is a TrueType file."""
    for name, path in FONTS.items():
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, path))

c = None  # active canvas
PAL = {}  # fill colors by part name; empty = black-and-white line art


def fc(key):
    c.setFillColor(PAL.get(key, white))


class palette:
    """with palette(robe=..., skin=...): color the parts drawn inside."""

    def __init__(self, **kw):
        self.kw = kw

    def __enter__(self):
        global PAL
        self.old = PAL
        PAL = dict(PAL, **self.kw)

    def __exit__(self, *a):
        global PAL
        PAL = self.old


# ---------------------------------------------------------------- primitives

def start():
    """Begin a page: scale it into KDP's safe area."""
    c.saveState()
    c.translate(W / 2, H / 2)
    c.scale(PAGE_SCALE, PAGE_SCALE)
    c.translate(-W / 2, -H / 2)
    reset()


def end_page():
    c.restoreState()
    c.showPage()


def reset():
    c.setLineWidth(LW)
    c.setLineJoin(1)
    c.setLineCap(1)
    c.setStrokeColor(black)
    c.setFillColor(white)


def lw(w):
    c.setLineWidth(w)


def P():
    return c.beginPath()


def draw(p, fill=1, stroke=1):
    c.drawPath(p, fill=fill, stroke=stroke)


def circle(x, y, r, fill=1):
    c.circle(x, y, r, stroke=1, fill=fill)


def ellipse(cx, cy, rx, ry, fill=1):
    c.ellipse(cx - rx, cy - ry, cx + rx, cy + ry, stroke=1, fill=fill)


def rellipse(cx, cy, rx, ry, deg):
    c.saveState()
    c.translate(cx, cy)
    c.rotate(deg)
    ellipse(0, 0, rx, ry)
    c.restoreState()


def poly(pts, close=True, fill=1):
    p = P()
    p.moveTo(*pts[0])
    for q in pts[1:]:
        p.lineTo(*q)
    if close:
        p.close()
    draw(p, fill=fill if close else 0)


def line(x1, y1, x2, y2):
    c.line(x1, y1, x2, y2)


def dot(x, y, r):
    c.setFillColor(black)
    c.circle(x, y, r, stroke=0, fill=1)
    c.setFillColor(white)


def arc(cx, cy, r, start, extent):
    c.arc(cx - r, cy - r, cx + r, cy + r, start, extent)


def rect(x, y, w, h, r=0):
    if r:
        c.roundRect(x, y, w, h, r, stroke=1, fill=1)
    else:
        c.rect(x, y, w, h, stroke=1, fill=1)


def hollow(fn, w=10, key=None):
    """Stroke a path thick in black, then thinner in white: a colorable band."""
    lw(w)
    fn()
    c.setStrokeColor(PAL.get(key, white))
    lw(w - 2 * LW)
    fn()
    c.setStrokeColor(black)
    lw(LW)


def scallops(p, pts, bulge):
    """Append bumpy curves through pts; positive bulge bows to the right of travel."""
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        dx, dy = bx - ax, by - ay
        L = math.hypot(dx, dy) or 1
        nx, ny = dy / L, -dx / L
        b = bulge * L
        p.curveTo(ax + dx * .2 + nx * b, ay + dy * .2 + ny * b,
                  ax + dx * .8 + nx * b, ay + dy * .8 + ny * b, bx, by)


def blob(circles, key="cloud"):
    """Union of circles as one outline (cloud, wool)."""
    fc(key)
    for x, y, r in circles:
        circle(x, y, r)
    for x, y, r in circles:
        c.circle(x, y, max(r - LW, 1), stroke=0, fill=1)


def clipped(path_fn, inner_fn):
    c.saveState()
    p = path_fn()
    c.clipPath(p, stroke=0, fill=0)
    inner_fn()
    c.restoreState()
    draw(path_fn(), fill=0)


# ---------------------------------------------------------------- shapes

def star(cx, cy, ro, ri=None, n=5, rot=90):
    ri = ri or ro * 0.45
    pts = []
    for i in range(2 * n):
        r = ro if i % 2 == 0 else ri
        a = math.radians(rot + i * 180 / n)
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    fc("star")
    poly(pts)


def sparkle(cx, cy, r):
    star(cx, cy, r, r * 0.28, n=4)


def bstar(cx, cy, r):
    """The Star of Bethlehem: eight points with a long ray pointing down."""
    lw(2)
    for i in range(8):
        a = math.radians(90 + 11.25 + i * 45)
        line(cx + r * .5 * math.cos(a), cy + r * .5 * math.sin(a),
             cx + r * .9 * math.cos(a), cy + r * .9 * math.sin(a))
    lw(LW)
    pts = []
    for i in range(16):
        a = math.radians(90 + i * 22.5)
        if i % 2:
            rr = r * 0.26
        elif i == 8:
            rr = r * 1.7
        elif i % 4 == 0:
            rr = r
        else:
            rr = r * 0.55
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    fc("bstar")
    poly(pts)
    fc("bstar_c")
    circle(cx, cy, r * 0.16)


def sky(points):
    for i, (x, y) in enumerate(points):
        if i % 3 == 0:
            sparkle(x, y, 9)
        else:
            star(x, y, 9 if i % 2 else 7)


def heart(cx, cy, s):
    fc("heart")
    p = P()
    p.moveTo(cx, cy - s)
    p.curveTo(cx - 1.25 * s, cy - 0.1 * s, cx - 0.75 * s, cy + 1.0 * s, cx, cy + 0.42 * s)
    p.curveTo(cx + 0.75 * s, cy + 1.0 * s, cx + 1.25 * s, cy - 0.1 * s, cx, cy - s)
    p.close()
    draw(p)


def cloud(cx, cy, s):
    blob([(cx - .8 * s, cy, .4 * s), (cx - .35 * s, cy + .25 * s, .5 * s),
          (cx + .25 * s, cy + .3 * s, .55 * s), (cx + .8 * s, cy + .05 * s, .4 * s),
          (cx, cy - .1 * s, .5 * s), (cx - .45 * s, cy - .15 * s, .35 * s),
          (cx + .5 * s, cy - .15 * s, .35 * s)])


def holly_leaf(x, y, L, deg):
    c.saveState()
    c.translate(x, y)
    c.rotate(deg)
    w = L * 0.36
    top = [(0, 0), (.25 * L, .8 * w), (.5 * L, w), (.75 * L, .8 * w), (L, 0)]
    bot = [(L, 0), (.75 * L, -.8 * w), (.5 * L, -w), (.25 * L, -.8 * w), (0, 0)]
    p = P()
    p.moveTo(0, 0)
    scallops(p, top, 0.22)
    scallops(p, bot, 0.22)
    p.close()
    fc("leaf")
    draw(p)
    lw(1.8)
    line(0, 0, .85 * L, 0)
    lw(LW)
    c.restoreState()


def holly(x, y, s, flip=False):
    d = -1 if flip else 1
    holly_leaf(x, y, s, 90 + d * 70)
    holly_leaf(x, y, s, 90 + d * 15)
    fc("berry")
    for dx, dy in ((0, 0), (.22, .1), (.05, .25)):
        circle(x + d * dx * s, y + dy * s, .13 * s)


def hills(y_left, y_mid, y_right, bottom=0, width=AW):
    p = P()
    p.moveTo(0, bottom)
    p.lineTo(0, y_left)
    p.curveTo(width * .25, y_left + 40, width * .35, y_mid, width * .55, y_mid)
    p.curveTo(width * .75, y_mid, width * .85, y_right + 10, width, y_right)
    p.lineTo(width, bottom)
    p.close()
    fc("hills")
    draw(p)


def grass(x, y, s=1):
    lw(2)
    for dx, h, lean in ((-6, 14, -4), (0, 20, 0), (6, 14, 4)):
        line(x + dx * s, y, x + (dx + lean) * s, y + h * s)
    lw(LW)


# ---------------------------------------------------------------- people

def face(x, y, r, smile=True, closed=False):
    if closed:
        lw(1.8)
        arc(x - r * .35, y + r * .15, r * .16, 200, 140)
        arc(x + r * .35, y + r * .15, r * .16, 200, 140)
        lw(LW)
    else:
        dot(x - r * .35, y + r * .12, r * .11)
        dot(x + r * .35, y + r * .12, r * .11)
    if smile:
        lw(2)
        arc(x, y - r * .05, r * .42, 215, 110)
        lw(LW)


def robe_path(x, y, h, flare=0.27, top=0.76, wavy=False):
    p = P()
    sh = 0.13 if not wavy else 0.1
    p.moveTo(x - sh * h, y + top * h)
    p.curveTo(x - (sh + .06) * h, y + .55 * h, x - (flare - .01) * h, y + .2 * h,
              x - flare * h, y)
    if wavy:
        n = 6
        pts = [(x - flare * h + i * 2 * flare * h / n, y) for i in range(n + 1)]
        scallops(p, pts, 0.25)
    else:
        p.lineTo(x + flare * h, y)
    p.curveTo(x + (flare - .01) * h, y + .2 * h, x + (sh + .06) * h, y + .55 * h,
              x + sh * h, y + top * h)
    p.curveTo(x + .06 * h, y + (top + .04) * h, x - .06 * h, y + (top + .04) * h,
              x - sh * h, y + top * h)
    p.close()
    return p


def robe(x, y, h, flare=0.27, wavy=False, belt=True):
    fc("robe")
    draw(robe_path(x, y, h, flare, wavy=wavy))
    if belt:
        def band():
            fc("belt")
            rect(x - .4 * h, y + .44 * h, .8 * h, .055 * h)
        clipped(lambda: robe_path(x, y, h, flare, wavy=wavy), band)
    lw(2)
    c.bezier(x - .07 * h, y + .42 * h, x - .08 * h, y + .3 * h,
             x - .1 * h, y + .15 * h, x - .12 * h, y + .03 * h)
    c.bezier(x + .07 * h, y + .42 * h, x + .08 * h, y + .3 * h,
             x + .1 * h, y + .15 * h, x + .12 * h, y + .03 * h)
    lw(LW)


def arms(x, y, h, mode):
    fc("sleeve")
    if mode in ("fold", "pray", "gift"):
        p = P()
        p.moveTo(x - .17 * h, y + .72 * h)
        p.curveTo(x - .16 * h, y + .6 * h, x - .08 * h, y + .52 * h, x - .03 * h, y + .52 * h)
        p.lineTo(x + .03 * h, y + .52 * h)
        p.curveTo(x + .08 * h, y + .52 * h, x + .16 * h, y + .6 * h, x + .17 * h, y + .72 * h)
        p.curveTo(x + .12 * h, y + .7 * h, x + .06 * h, y + .62 * h, x, y + .61 * h)
        p.curveTo(x - .06 * h, y + .62 * h, x - .12 * h, y + .7 * h, x - .17 * h, y + .72 * h)
        p.close()
        draw(p)
        fc("skin")
        if mode == "pray":
            ellipse(x, y + .6 * h, .028 * h, .06 * h)
            lw(1.5)
            line(x, y + .55 * h, x, y + .65 * h)
            lw(LW)
        elif mode == "fold":
            circle(x, y + .545 * h, .032 * h)
    for side in (-1, 1):
        m = mode
        if mode == "trumpet":
            m = "up" if side == 1 else "out"
        fc("sleeve")
        if m == "up":
            poly([(x + side * .1 * h, y + .73 * h), (x + side * .3 * h, y + .95 * h),
                  (x + side * .24 * h, y + 1.0 * h), (x + side * .05 * h, y + .64 * h)])
            fc("skin")
            circle(x + side * .29 * h, y + 1.0 * h, .03 * h)
        elif m == "out":
            poly([(x + side * .11 * h, y + .74 * h), (x + side * .33 * h, y + .56 * h),
                  (x + side * .3 * h, y + .5 * h), (x + side * .09 * h, y + .62 * h)])
            fc("skin")
            circle(x + side * .33 * h, y + .52 * h, .03 * h)


def crown(x, hy, hr, kind):
    fc("crown")
    if kind == "points":
        y0 = hy + hr * .55
        poly([(x - hr * .85, y0), (x - hr * .85, y0 + hr * .95), (x - hr * .42, y0 + hr * .5),
              (x, y0 + hr * 1.15), (x + hr * .42, y0 + hr * .5), (x + hr * .85, y0 + hr * .95),
              (x + hr * .85, y0)])
        for px, py in ((-.85, .95), (0, 1.15), (.85, .95)):
            circle(x + px * hr, y0 + py * hr, hr * .13)
        circle(x, y0 + hr * .25, hr * .14)
    elif kind == "turban":
        ellipse(x, hy + hr * .75, hr * 1.2, hr * .62)
        lw(2)
        arc(x, hy + hr * .2, hr * 1.0, 50, 80)
        lw(LW)
        p = P()
        p.moveTo(x, hy + hr * .55)
        p.curveTo(x - hr * .3, hy + hr * .85, x - hr * .1, hy + hr * 1.1, x, hy + hr * 1.15)
        p.curveTo(x + hr * .1, hy + hr * 1.1, x + hr * .3, hy + hr * .85, x, hy + hr * .55)
        draw(p)
        c.bezier(x, hy + hr * 1.15, x + hr * .3, hy + hr * 1.6, x + hr * .8, hy + hr * 1.7,
                 x + hr * 1.1, hy + hr * 1.5)
    elif kind == "tall":
        poly([(x - hr * .8, hy + hr * .5), (x, hy + hr * 2.3), (x + hr * .8, hy + hr * .5)])
        rect(x - hr * .9, hy + hr * .45, hr * 1.8, hr * .3)
        star(x, hy + hr * 1.2, hr * .3)


def gift_small(x, y, s, kind):
    fc("gift")
    if kind == "box":
        rect(x - s * .5, y - s * .45, s, s * .8)
        rect(x - s * .1, y - s * .45, s * .2, s * .8)
        rellipse(x - s * .18, y + s * .45, s * .2, s * .1, 25)
        rellipse(x + s * .18, y + s * .45, s * .2, s * .1, -25)
        circle(x, y + s * .38, s * .08)
    elif kind == "jar":
        p = P()
        p.moveTo(x - s * .2, y + s * .3)
        p.curveTo(x - s * .65, y + s * .1, x - s * .5, y - s * .5, x, y - s * .5)
        p.curveTo(x + s * .5, y - s * .5, x + s * .65, y + s * .1, x + s * .2, y + s * .3)
        p.close()
        draw(p)
        rect(x - s * .28, y + s * .28, s * .56, s * .14)
        circle(x, y + s * .5, s * .08)
        lw(2)
        line(x - s * .45, y - s * .1, x + s * .45, y - s * .1)
        lw(LW)
    elif kind == "chest":
        rect(x - s * .55, y - s * .45, s * 1.1, s * .6)
        p = P()
        p.moveTo(x - s * .55, y + s * .15)
        p.curveTo(x - s * .55, y + s * .5, x + s * .55, y + s * .5, x + s * .55, y + s * .15)
        p.close()
        draw(p)
        rect(x - s * .1, y + s * .02, s * .2, s * .2)


def person(x, y, h, hood=False, beard=False, crown_kind=None, staff=False, halo=False,
           headcloth=False, arm_mode="fold", gift=None, smile=True):
    hy, hr = y + .86 * h, .075 * h
    if staff:
        sx = x + .24 * h

        def crook():
            p = P()
            p.moveTo(sx, y)
            p.lineTo(sx, y + .95 * h)
            p.curveTo(sx, y + 1.03 * h, sx - .1 * h, y + 1.03 * h, sx - .1 * h, y + .96 * h)
            c.drawPath(p, stroke=1, fill=0)
        hollow(crook, 10, "staff")
    if halo:
        fc("halo")
        circle(x, hy + .01 * h, hr * 1.65)
    if hood:
        p = P()
        p.moveTo(x - .15 * h, y + .66 * h)
        p.curveTo(x - .17 * h, y + .95 * h, x - .08 * h, y + 1.0 * h, x, y + 1.0 * h)
        p.curveTo(x + .08 * h, y + 1.0 * h, x + .17 * h, y + .95 * h, x + .15 * h, y + .66 * h)
        p.close()
    elif headcloth:
        p = P()
        p.moveTo(x - .12 * h, y + .7 * h)
        p.curveTo(x - .13 * h, y + .92 * h, x - .07 * h, y + .96 * h, x, y + .96 * h)
        p.curveTo(x + .07 * h, y + .96 * h, x + .13 * h, y + .92 * h, x + .12 * h, y + .7 * h)
        p.close()
    robe(x, y, h)
    if hood or headcloth:
        fc("hood")
        draw(p)
    arms(x, y, h, "fold" if gift else arm_mode)
    fc("skin")
    circle(x, hy, hr)
    if headcloth:
        fc("hood")
        p = P()
        p.moveTo(x - hr * 1.08, hy + hr * .3)
        p.curveTo(x - hr * 1.1, hy + hr * 1.5, x + hr * 1.1, hy + hr * 1.5, x + hr * 1.08, hy + hr * .3)
        p.close()
        draw(p)
        fc("belt")
        rect(x - hr * 1.12, hy + hr * .25, hr * 2.24, hr * .3, hr * .1)
    face(x, hy, hr, smile=smile and not beard)
    if beard:
        p = P()
        p.moveTo(x - hr * .95, hy - hr * .05)
        p.curveTo(x - hr * .9, hy - hr * 1.5, x + hr * .9, hy - hr * 1.5, x + hr * .95, hy - hr * .05)
        p.curveTo(x + hr * .55, hy - hr * .55, x - hr * .55, hy - hr * .55, x - hr * .95, hy - hr * .05)
        p.close()
        fc("beard")
        draw(p)
        lw(2)
        arc(x, hy - hr * .55, hr * .22, 200, 140)
        lw(LW)
    if crown_kind:
        crown(x, hy, hr, crown_kind)
    if gift:
        gift_small(x, y + .56 * h, .14 * h, gift)


def wing(h):
    p = P()
    p.moveTo(0, .03 * h)
    p.curveTo(-.1 * h, .28 * h, -.36 * h, .33 * h, -.5 * h, .24 * h)
    pts = [(-.5 * h, .24 * h), (-.44 * h, .1 * h), (-.36 * h, -.02 * h), (-.26 * h, -.12 * h),
           (-.14 * h, -.2 * h), (-.03 * h, -.24 * h)]
    scallops(p, pts, 0.32)
    p.close()
    fc("wing")
    draw(p)
    lw(2)
    c.bezier(-.04 * h, 0, -.12 * h, .17 * h, -.3 * h, .2 * h, -.42 * h, .14 * h)
    for px, py in pts[2:-1]:
        c.bezier(-.06 * h, -.02 * h, px * .4, py * .3, px * .75, py * .8, px * .92, py * .92)
    lw(LW)


def angel(x, y, h, arm_mode="up"):
    for side in (-1, 1):
        c.saveState()
        c.translate(x + side * .06 * h, y + .64 * h)
        c.scale(-side, 1)
        wing(h)
        c.restoreState()
    hy, hr = y + .86 * h, .075 * h
    robe(x, y, h, flare=.32, wavy=True)
    lw(2)
    arc(x, y + .76 * h, .05 * h, 200, 140)
    lw(LW)
    arms(x, y, h, arm_mode)
    blob([(x, hy + hr * .15, hr * 1.18), (x - hr * .9, hy - hr * .3, hr * .45),
          (x + hr * .9, hy - hr * .3, hr * .45)], "hair")
    fc("skin")
    circle(x, hy, hr)
    face(x, hy, hr)
    fc("halo")
    ellipse(x, hy + hr * 1.6, hr * .95, hr * .3)
    fc("halo_in")
    ellipse(x, hy + hr * 1.6, hr * .6, hr * .14)
    if arm_mode == "trumpet":
        ax_, ay_ = x + .03 * h, y + .82 * h
        bx_, by_ = x + .36 * h, y + 1.04 * h
        dx, dy = bx_ - ax_, by_ - ay_
        L = math.hypot(dx, dy)
        ux, uy = dx / L, dy / L
        nx, ny = -uy, ux
        t, b = .014 * h, .07 * h
        m = .68
        fc("trumpet")
        mx, my = ax_ + dx * m, ay_ + dy * m
        poly([(ax_ + nx * t, ay_ + ny * t), (mx + nx * t, my + ny * t), (bx_ + nx * b, by_ + ny * b),
              (bx_ - nx * b, by_ - ny * b), (mx - nx * t, my - ny * t), (ax_ - nx * t, ay_ - ny * t)])
        rellipse(bx_, by_, .022 * h, b, math.degrees(math.atan2(dy, dx)))
        fc("skin")
        circle(x + .29 * h, y + 1.0 * h, .03 * h)


def baby(cx, cy, s, halo=True):
    if halo:
        fc("halo")
        circle(cx - .27 * s, cy + .04 * s, .15 * s)
    fc("swaddle")
    ellipse(cx + .05 * s, cy, .3 * s, .1 * s)
    lw(2)
    for dx in (-.05, .08, .2):
        c.bezier(cx + dx * s, cy + .1 * s, cx + (dx + .04) * s, cy + .03 * s,
                 cx + (dx + .04) * s, cy - .03 * s, cx + dx * s, cy - .1 * s)
    lw(LW)
    fc("skin")
    circle(cx - .27 * s, cy + .03 * s, .09 * s)
    face(cx - .27 * s, cy + .03 * s, .09 * s, closed=True)


def manger(cx, y, w, with_baby=True):
    for side in (-1, 1):
        hollow(lambda: line(cx + side * .42 * w, y, cx + side * .2 * w, y + .4 * w), 10, "wood")
        hollow(lambda: line(cx + side * .2 * w, y, cx + side * .42 * w, y + .4 * w), 10, "wood")
    pts = [(cx - .48 * w, y + .55 * w)]
    n = 12
    for i in range(1, n):
        px = cx - .48 * w + i * .96 * w / n
        pts.append((px, y + (.7 if i % 2 else .6) * w))
    pts.append((cx + .48 * w, y + .55 * w))
    fc("hay")
    poly(pts)
    if with_baby:
        baby(cx + .02 * w, y + .62 * w, w)
    fc("wood")
    poly([(cx - .52 * w, y + .57 * w), (cx + .52 * w, y + .57 * w),
          (cx + .4 * w, y + .3 * w), (cx - .4 * w, y + .3 * w)])
    lw(2)
    line(cx - .46 * w, y + .44 * w, cx + .46 * w, y + .44 * w)
    lw(LW)


# ---------------------------------------------------------------- animals

def sheep(x, y, s, flip=False, lying=False):
    c.saveState()
    c.translate(x, y)
    if flip:
        c.scale(-1, 1)
    by = .3 * s if lying else .55 * s
    if not lying:
        fc("legs")
        for lx in (-.36, -.16, .2, .38):
            rect((lx - .05) * s, 0, .1 * s, .38 * s, .04 * s)
    fc("wool")
    circle(-.64 * s, by + .08 * s, .1 * s)
    blob([(-.45 * s, by, .2 * s), (-.25 * s, by + .2 * s, .22 * s), (0, by + .25 * s, .22 * s),
          (.25 * s, by + .2 * s, .22 * s), (.45 * s, by, .2 * s), (.25 * s, by - .18 * s, .2 * s),
          (0, by - .2 * s, .2 * s), (-.25 * s, by - .18 * s, .2 * s), (0, by, .3 * s)], "wool")
    fc("sheepface")
    rellipse(.48 * s, by + .22 * s, .12 * s, .05 * s, 20)
    rellipse(.78 * s, by + .22 * s, .12 * s, .05 * s, -20)
    ellipse(.63 * s, by + .1 * s, .15 * s, .2 * s)
    blob([(.56 * s, by + .3 * s, .07 * s), (.63 * s, by + .33 * s, .07 * s),
          (.7 * s, by + .3 * s, .07 * s)], "wool")
    dot(.57 * s, by + .13 * s, .022 * s)
    dot(.69 * s, by + .13 * s, .022 * s)
    lw(2)
    arc(.63 * s, by - .0 * s, .04 * s, 220, 100)
    lw(LW)
    c.restoreState()


def donkey(x, y, s, flip=False):
    c.saveState()
    c.translate(x, y)
    if flip:
        c.scale(-1, 1)
    fc("donkey")
    hollow(lambda: c.bezier(-.48 * s, .82 * s, -.6 * s, .8 * s, -.62 * s, .6 * s, -.6 * s, .48 * s), 9, "donkey")
    fc("donkey")
    rellipse(-.6 * s, .44 * s, .04 * s, .08 * s, 0)
    for lx in (-.38, -.24, .22, .36):
        rect((lx - .045) * s, 0, .09 * s, .62 * s, .03 * s)
        lw(2)
        line((lx - .045) * s, .07 * s, (lx + .045) * s, .07 * s)
        lw(LW)
    fc("donkey")
    rellipse(.5 * s, 1.43 * s, .045 * s, .17 * s, 20)
    rellipse(.62 * s, 1.42 * s, .045 * s, .17 * s, -5)
    poly([(.28 * s, .86 * s), (.48 * s, 1.27 * s), (.66 * s, 1.2 * s), (.52 * s, .72 * s)])
    pts = []
    for i in range(7):
        t = i / 6
        bx, by = .28 + t * .2, .86 + t * .41
        pts.append(((bx - (.035 if i % 2 else 0)) * s, (by + (.02 if i % 2 else 0)) * s))
    poly(pts, close=False)
    fc("donkey")
    ellipse(0, .78 * s, .52 * s, .25 * s)
    rellipse(.66 * s, 1.18 * s, .22 * s, .11 * s, -35)
    fc("muzzle")
    rellipse(.81 * s, 1.04 * s, .1 * s, .085 * s, -35)
    dot(.6 * s, 1.27 * s, .022 * s)
    dot(.84 * s, 1.02 * s, .015 * s)
    c.restoreState()


def dove(x, y, s, flip=False):
    c.saveState()
    c.translate(x, y)
    if flip:
        c.scale(-1, 1)
    poly([(-.35 * s, .02 * s), (-.85 * s, .2 * s), (-.8 * s, -.05 * s), (-.85 * s, -.25 * s)])
    ellipse(0, 0, .45 * s, .2 * s)
    circle(.42 * s, .15 * s, .16 * s)
    poly([(.56 * s, .2 * s), (.72 * s, .14 * s), (.56 * s, .1 * s)])
    dot(.45 * s, .2 * s, .025 * s)
    p = P()
    p.moveTo(-.25 * s, .08 * s)
    p.curveTo(-.3 * s, .5 * s, -.1 * s, .85 * s, .1 * s, .95 * s)
    scallops(p, [(.1 * s, .95 * s), (.12 * s, .7 * s), (.14 * s, .45 * s), (.15 * s, .2 * s)], .3)
    p.close()
    draw(p)
    lw(2)
    line(.7 * s, .12 * s, .95 * s, -.05 * s)
    lw(LW)
    for t, d in ((.3, 1), (.55, -1), (.8, 1)):
        px, py = .7 + .25 * t, .12 - .17 * t
        rellipse((px + .03) * s, (py + d * .05) * s, .07 * s, .03 * s, d * 35)
    c.restoreState()


# ---------------------------------------------------------------- places & things

def stable(x0, y0, w, h):
    def wall():
        p = P()
        p.moveTo(x0, y0)
        p.lineTo(x0, y0 + .69 * h)
        p.lineTo(x0 + .5 * w, y0 + .94 * h)
        p.lineTo(x0 + w, y0 + .69 * h)
        p.lineTo(x0 + w, y0)
        p.close()
        return p
    fc("wall")
    draw(wall())

    def planks():
        lw(2)
        for i in range(1, 12):
            px = x0 + i * w / 12
            line(px, y0, px, y0 + h)
        lw(LW)
    clipped(wall, planks)
    fc("wood")
    rect(x0, y0, .05 * w, .72 * h)
    rect(x0 + .95 * w, y0, .05 * w, .72 * h)
    fc("roof")
    poly([(x0 - .07 * w, y0 + .7 * h), (x0 + .5 * w, y0 + h), (x0 + 1.07 * w, y0 + .7 * h),
          (x0 + 1.04 * w, y0 + .63 * h), (x0 + .5 * w, y0 + .91 * h), (x0 - .04 * w, y0 + .63 * h)])
    lw(1.8)
    for i in range(1, 12):
        t = i / 12
        lx, ly = x0 - .055 * w + t * .555 * w, y0 + .665 * h + t * .29 * h
        line(lx, ly, lx + .02 * w, ly + .05 * h)
        rx = x0 + 1.055 * w - t * .555 * w
        line(rx, ly, rx - .02 * w, ly + .05 * h)
    lw(LW)


def house(x, y, w, h, dome=False):
    fc("dome")
    if dome:
        p = P()
        p.moveTo(x + .1 * w, y + h)
        p.curveTo(x + .1 * w, y + h + .55 * w, x + .9 * w, y + h + .55 * w, x + .9 * w, y + h)
        p.close()
        draw(p)
    fc("house")
    rect(x, y, w, h)
    rect(x - 2, y + h - 5, w + 4, 6)
    fc("door")
    ww = w * .22
    p = P()
    p.moveTo(x + w * .5 - ww * .7, y)
    p.lineTo(x + w * .5 - ww * .7, y + h * .38)
    p.curveTo(x + w * .5 - ww * .7, y + h * .55, x + w * .5 + ww * .7, y + h * .55, x + w * .5 + ww * .7, y + h * .38)
    p.lineTo(x + w * .5 + ww * .7, y)
    draw(p)
    rect(x + w * .15, y + h * .62, ww, ww)
    rect(x + w * .85 - ww, y + h * .62, ww, ww)


def palm(x, y, h):
    p = P()
    p.moveTo(x - .05 * h, y)
    p.curveTo(x - .02 * h, y + .4 * h, x + .02 * h, y + .7 * h, x + .06 * h, y + .9 * h)
    p.lineTo(x + .1 * h, y + .9 * h)
    p.curveTo(x + .07 * h, y + .7 * h, x + .05 * h, y + .4 * h, x + .05 * h, y)
    p.close()
    fc("trunk")
    draw(p)
    lw(2)
    for i in range(1, 9):
        t = i / 9
        cx_ = x + (-.0 + .08 * t * t) * h
        arc(cx_, y + t * .9 * h + .03 * h, .05 * h, 220, 100)
    lw(LW)
    tx, ty = x + .08 * h, y + .9 * h
    for ang in (160, 125, 85, 50, 15, 195, -15):
        c.saveState()
        c.translate(tx, ty)
        c.rotate(ang)
        L = .42 * h
        p = P()
        p.moveTo(0, 0)
        p.curveTo(.3 * L, .25 * L, .75 * L, .2 * L, L, -.12 * L)
        p.curveTo(.7 * L, 0, .3 * L, -.05 * L, 0, 0)
        p.close()
        fc("frond")
        draw(p)
        lw(1.8)
        c.bezier(0, 0, .3 * L, .1 * L, .7 * L, .08 * L, L, -.12 * L)
        lw(LW)
        c.restoreState()
    fc("coconut")
    for dx, dy in ((-.03, -.03), (.03, -.05), (.0, -.08)):
        circle(tx + dx * h, ty + dy * h, .035 * h)


def scroll(cx, cy, w, h):
    rect(cx - w / 2, cy - h / 2, w, h)
    for yy in (cy + h / 2, cy - h / 2):
        rect(cx - w / 2 - 14, yy - 12, w + 28, 24, 12)
        circle(cx - w / 2 - 20, yy, 10)
        circle(cx + w / 2 + 20, yy, 10)


def gift_box(x, y, w, h, bow=True):
    if bow:
        rellipse(x + w / 2 - w * .17, y + h + w * .1, w * .2, w * .1, 25)
        rellipse(x + w / 2 + w * .17, y + h + w * .1, w * .2, w * .1, -25)
    rect(x, y, w, h * .8)
    rect(x - w * .05, y + h * .8 - 2, w * 1.1, h * .22)
    rect(x + w * .42, y, w * .16, h * .8)
    rect(x + w * .42, y + h * .8 - 2, w * .16, h * .22)
    if bow:
        circle(x + w / 2, y + h + w * .04, w * .07)


def candle(cx, y, w, h):
    top = y + h
    lw(2)
    for ang in range(0, 360, 30):
        a = math.radians(ang)
        fx, fy = cx, top + w * .55
        line(fx + math.cos(a) * w * .55, fy + math.sin(a) * w * .7,
             fx + math.cos(a) * w * .8, fy + math.sin(a) * w * .95)
    lw(LW)
    ellipse(cx, y, w * .95, w * .22)
    p = P()
    p.moveTo(cx - w / 2, y)
    p.lineTo(cx - w / 2, top - 10)
    scallops(p, [(cx - w / 2, top - 10), (cx - w / 6, top), (cx + w / 6, top - 6), (cx + w / 2, top)], .15)
    p.lineTo(cx + w / 2, y)
    p.close()
    draw(p)
    lw(2)
    p = P()
    p.moveTo(cx - w / 2, top - 10)
    p.curveTo(cx - w * .4, top - 40, cx - w * .3, top - 40, cx - w * .3, top - 8)
    c.drawPath(p, stroke=1, fill=0)
    line(cx, top, cx, top + 12)
    lw(LW)
    for sc in (1, .55):
        p = P()
        fy = top + 12
        p.moveTo(cx, fy)
        p.curveTo(cx - w * .35 * sc, fy + w * .2 * sc, cx - w * .1 * sc, fy + w * .6 * sc, cx, fy + w * 1.0 * sc)
        p.curveTo(cx + w * .1 * sc, fy + w * .6 * sc, cx + w * .35 * sc, fy + w * .2 * sc, cx, fy)
        p.close()
        draw(p)


def xmas_tree(cx, y, h):
    rect(cx - .05 * h, y, .1 * h, .1 * h)
    tiers = [(.07, .5, .78), (.33, .66, .6), (.56, .9, .42)]
    for base, apex, width in tiers:
        bw = width * h
        p = P()
        p.moveTo(cx, y + apex * h)
        p.lineTo(cx + bw / 2, y + base * h)
        n = 6
        pts = [(cx + bw / 2 - i * bw / n, y + base * h) for i in range(n + 1)]
        scallops(p, pts, .25)
        p.close()
        draw(p)
    lw(2)
    c.bezier(cx - .3 * h, y + .2 * h, cx - .1 * h, y + .13 * h, cx + .1 * h, y + .16 * h, cx + .3 * h, y + .28 * h)
    c.bezier(cx - .22 * h, y + .44 * h, cx - .05 * h, y + .37 * h, cx + .1 * h, y + .4 * h, cx + .23 * h, y + .48 * h)
    c.bezier(cx - .14 * h, y + .66 * h, cx - .03 * h, y + .61 * h, cx + .06 * h, y + .63 * h, cx + .14 * h, y + .69 * h)
    lw(LW)
    for ox, oy in ((-.25, .12), (.2, .13), (-.05, .25), (.18, .38), (-.18, .36),
                   (.1, .55), (-.1, .53), (0, .74)):
        circle(cx + ox * h, y + oy * h, .022 * h)
        rect(cx + ox * h - .008 * h, y + oy * h + .018 * h, .016 * h, .012 * h)
    star(cx, y + .92 * h, .06 * h)


def treasure_chest(x, y, w, h):
    for i, (dx, dy) in enumerate(((-.05, .0), (-.1, .07), (1.0, .0), (1.05, .07), (1.0, .14))):
        ellipse(x + dx * w, y + dy * h + 6, w * .09, 6)
    rect(x, y, w, h * .62)
    p = P()
    p.moveTo(x - 4, y + h * .62)
    p.curveTo(x - 4, y + h * 1.05, x + w + 4, y + h * 1.05, x + w + 4, y + h * .62)
    p.close()
    draw(p)
    for fx in (.18, .82):
        rect(x + fx * w - 6, y, 12, h * .62)
        def band(fx=fx):
            p = P()
            p.moveTo(x + fx * w - 6, y + h * .62)
            p.lineTo(x + fx * w - 6, y + h * .9)
            p.lineTo(x + fx * w + 6, y + h * .9)
            p.lineTo(x + fx * w + 6, y + h * .62)
            p.close()
            draw(p)
        band()
    rect(x + w / 2 - 14, y + h * .45, 28, 30, 4)
    dot(x + w / 2, y + h * .45 + 18, 3)
    line(x + w / 2, y + h * .45 + 16, x + w / 2, y + h * .45 + 8)
    for dx, dy in ((.3, .95), (.5, 1.0), (.7, .95)):
        sparkle(x + dx * w, y + dy * h + 20, 9)


def incense_jar(cx, y, w, h):
    lw(2.5)
    for dx in (-.15, .12):
        p = P()
        p.moveTo(cx + dx * w, y + h + 8)
        p.curveTo(cx + dx * w - 20, y + h + 30, cx + dx * w + 20, y + h + 50, cx + dx * w, y + h + 75)
        c.drawPath(p, stroke=1, fill=0)
    lw(LW)
    rect(cx - w * .35, y, w * .7, h * .08, 4)
    p = P()
    p.moveTo(cx - w * .15, y + h * .08)
    p.curveTo(cx - w * .7, y + h * .25, cx - w * .55, y + h * .8, cx - w * .25, y + h * .82)
    p.lineTo(cx + w * .25, y + h * .82)
    p.curveTo(cx + w * .55, y + h * .8, cx + w * .7, y + h * .25, cx + w * .15, y + h * .08)
    p.close()
    draw(p)
    rect(cx - w * .32, y + h * .8, w * .64, h * .1, 5)
    p = P()
    p.moveTo(cx - w * .25, y + h * .9)
    p.curveTo(cx - w * .25, y + h * 1.05, cx + w * .25, y + h * 1.05, cx + w * .25, y + h * .9)
    p.close()
    draw(p)
    circle(cx, y + h * 1.03, w * .06)
    lw(2)
    for i, yy in enumerate((.3, .55)):
        line(cx - w * .5, y + yy * h, cx + w * .5, y + yy * h)
    lw(LW)
    for dx in (-.25, 0, .25):
        star(cx + dx * w, y + .43 * h, w * .07)


def myrrh_bottle(cx, y, w, h):
    rect(cx - w * .12, y + h * .55, w * .24, h * .32)
    rect(cx - w * .19, y + h * .85, w * .38, h * .05, 3)
    p = P()
    p.moveTo(cx - w * .1, y + h * .9)
    p.curveTo(cx - w * .14, y + h * 1.0, cx + w * .14, y + h * 1.0, cx + w * .1, y + h * .9)
    p.close()
    draw(p)
    circle(cx, y + h * .3, w * .48)
    rect(cx - w * .35, y - 2, w * .7, h * .06, 4)
    for dy in (.18, .42):
        lw(2)
        p = P()
        n = 8
        p.moveTo(cx - w * .43, y + dy * h)
        for i in range(1, n + 1):
            p.lineTo(cx - w * .43 + i * w * .86 / n, y + (dy + (.04 if i % 2 else 0)) * h)
        c.drawPath(p, stroke=1, fill=0)
        lw(LW)
    heart(cx, y + h * .32, w * .1)


def crescent(cx, cy, R):
    p = P()
    p.arc(cx - R, cy - R, cx + R, cy + R, 60, 240)
    c2 = cx + .35 * R
    r2 = .879 * R
    p.arcTo(c2 - r2, cy - r2, c2 + r2, cy + r2, -80.2, -199.6)
    p.close()
    draw(p)


# ---------------------------------------------------------------- page chrome

def bubble_text(x, y, text, size, font="Title", width=2.2, space=1.5):
    c.saveState()
    tw = c.stringWidth(text, font, size) + space * (len(text) - 1)
    t = c.beginText()
    t.setTextRenderMode(2)
    t.setFont(font, size)
    t.setCharSpace(space)
    t.setTextOrigin(x - tw / 2, y)
    t.textLine(text)
    c.setLineWidth(width)
    c.setFillColor(white)
    c.setStrokeColor(black)
    c.drawText(t)
    c.restoreState()


def fit_bubble(x, y, text, size, maxw, **kw):
    font = kw.get("font", "Title")
    while c.stringWidth(text, font, size) + 1.5 * len(text) > maxw and size > 14:
        size -= 1
    bubble_text(x, y, text, size, **kw)


def plain(x, y, text, font, size, align="center"):
    c.setFillColor(black)
    c.setFont(font, size)
    if align == "center":
        c.drawCentredString(x, y, text)
    elif align == "right":
        c.drawRightString(x, y, text)
    else:
        c.drawString(x, y, text)
    c.setFillColor(white)


def frame(num=None):
    lw(2.5)
    c.roundRect(20, 20, W - 40, H - 40, 18, stroke=1, fill=0)
    lw(1.2)
    c.roundRect(27, 27, W - 54, H - 54, 14, stroke=1, fill=0)
    lw(LW)
    for x, y in ((24, 24), (W - 24, 24), (24, H - 24), (W - 24, H - 24)):
        star(x, y, 12)
    if num:
        plain(W / 2, 31, f"{num}", "Sans", 9)


def verse_box(verse, ref, theme, question):
    x, y, w, h = 46, 44, W - 92, 178
    lw(2.5)
    c.roundRect(x, y, w, h, 14, stroke=1, fill=0)
    lw(LW)
    label = f"THEME: {theme.upper()}"
    lwid = c.stringWidth(label, "Sans-Bold", 13) + 30
    lw(2.5)
    rect(x + 20, y + h - 14, lwid, 28, 14)
    lw(LW)
    plain(x + 20 + lwid / 2, y + h - 4.5, label, "Sans-Bold", 13)
    star(x + w - 30, y + h, 12)

    size = 17
    while True:
        lines = simpleSplit(f"“{verse}”", "Serif-Italic", size, w - 50)
        qlines = simpleSplit("Think about it: " + question, "Sans", 12, w - 70)
        need = len(lines) * size * 1.22 + 22 + len(qlines) * 15 + 34
        if need <= h - 10 or size <= 12:
            break
        size -= 0.5
    ty = y + h - 30 - size * .8
    for ln in lines:
        plain(W / 2, ty, ln, "Serif-Italic", size)
        ty -= size * 1.22
    plain(x + w - 26, ty - 2, f"— {ref} (KJV)", "Sans-Bold", 12.5, align="right")
    qy = y + 14 + (len(qlines) - 1) * 15
    lw(1.5)
    c.line(x + 24, qy + 20, x + w - 24, qy + 20)
    lw(LW)
    heart(x + 34, qy + 4, 7)
    for i, ln in enumerate(qlines):
        if i == 0:
            c.setFillColor(black)
            c.setFont("Sans-Bold", 12)
            c.drawString(x + 48, qy, "Think about it:")
            off = c.stringWidth("Think about it: ", "Sans-Bold", 12)
            c.setFont("Sans", 12)
            c.drawString(x + 48 + off, qy, ln[len("Think about it: "):])
            c.setFillColor(white)
        else:
            plain(x + 48, qy - i * 15, ln, "Sans", 12, align="left")


def verse_page(num, title, verse, ref, theme, question, art):
    start()
    frame(num)
    fit_bubble(W / 2, 712, title, 38, W - 90)
    c.saveState()
    c.translate(AX, AY)
    clip = c.beginPath()
    clip.rect(-8, -8, AW + 16, AH + 16)
    c.clipPath(clip, stroke=0, fill=0)
    reset()
    art()
    c.restoreState()
    reset()
    verse_box(verse, ref, theme, question)
    end_page()


# ---------------------------------------------------------------- scenes

def art_promise():
    sky([(40, 420), (120, 380), (60, 300), (470, 300), (300, 440), (200, 430), (480, 430)])
    bstar(256, 408, 34)
    dove(430, 360, 55, flip=True)
    dove(80, 360, 45)
    scroll(256, 190, 270, 240)
    for i, word in enumerate(("Wonderful", "Counsellor", "The Mighty God", "Prince of Peace")):
        bubble_text(256, 268 - i * 52, word, 30, font="Serif-Bold", width=1.8, space=1)
    holly(40, 20, 50)
    holly(472, 20, 50, flip=True)


def art_gabriel():
    lw(2)
    line(0, 40, AW, 40)
    for i in range(-4, 10):
        line(256 + i * 60, 40, 256 + i * 90, 0)
    lw(LW)
    sky([(30, 420), (470, 420), (330, 400), (40, 250), (480, 300)])
    angel(170, 60, 255, "up")
    person(400, 40, 240, hood=True, arm_mode="pray")
    for x, y in ((300, 330), (85, 400), (255, 430)):
        sparkle(x, y, 11)


def art_journey():
    sky([(30, 430), (110, 400), (190, 440), (470, 440), (400, 360), (60, 340)])
    bstar(390, 400, 30)
    hills(230, 300, 285, bottom=30)
    for hx, hy, hw, hh, dome in ((300, 296, 40, 34, False), (345, 300, 46, 40, True),
                                 (398, 296, 38, 30, False), (440, 290, 44, 36, False)):
        house(hx, hy, hw, hh, dome)
    palm(30, 200, 130)
    lw(LW)
    line(0, 30, AW, 30)
    donkey(220, 30, 150)
    person(205, 128, 135, hood=True, arm_mode="fold")
    rect(160, 112, 105, 42, 10)
    lw(1.8)
    for i in range(1, 8):
        line(160 + i * 13, 112, 160 + i * 13, 104)
    lw(LW)
    person(430, 30, 225, beard=True, headcloth=True, staff=True)
    for gx in (40, 120, 360, 500):
        grass(gx, 30)


def art_nativity():
    sky([(30, 430), (100, 400), (420, 440), (480, 390), (180, 440), (330, 440)])
    bstar(256, 415, 28)
    lw(LW)
    line(0, 30, AW, 30)
    stable(40, 30, 432, 330)
    person(132, 30, 190, hood=True, arm_mode="pray", halo=True)
    person(382, 30, 210, beard=True, headcloth=True, staff=True)
    manger(256, 30, 150)
    for gx in (10, 230, 300, 500):
        grass(gx, 30)


def art_shepherds():
    crescent(430, 400, 34)
    sky([(30, 430), (90, 380), (170, 440), (250, 400), (320, 440), (360, 370),
         (480, 340), (200, 340), (40, 310)])
    hills(150, 200, 170, bottom=20)
    sheep(375, 150, 60, lying=True)
    lw(LW)
    person(115, 20, 260, headcloth=True, staff=True, arm_mode="fold")
    sheep(300, 20, 95)
    sheep(445, 25, 75, flip=True)
    for gx in (30, 220, 380, 500):
        grass(gx, 22)


def art_good_news():
    sky([(30, 420), (90, 360), (470, 420), (420, 350), (40, 260), (490, 260)])
    for x, y in ((70, 300), (440, 290), (260, 440)):
        sparkle(x, y, 13)
    angel(256, 175, 245, "up")
    lw(LW)
    hills(110, 140, 120, bottom=0)
    person(70, 10, 150, headcloth=True, staff=True, arm_mode="out")
    person(170, 10, 140, headcloth=True, beard=True, arm_mode="pray")
    sheep(360, 10, 70)
    sheep(460, 15, 55, flip=True)


def art_glory():
    sky([(30, 430), (130, 420), (380, 430), (480, 420), (256, 445), (40, 330), (480, 330)])
    angel(95, 150, 165, "pray")
    angel(417, 150, 165, "pray")
    angel(256, 115, 225, "trumpet")
    cloud(95, 145, 60)
    cloud(417, 145, 60)
    cloud(256, 105, 85)
    cloud(60, 30, 40)
    cloud(450, 35, 45)
    for x, y in ((180, 30), (330, 40)):
        sparkle(x, y, 12)


def art_wisemen():
    sky([(30, 430), (110, 400), (200, 440), (290, 420), (480, 440), (60, 330)])
    bstar(420, 395, 32)
    hills(180, 220, 200, bottom=30)
    palm(10, 150, 170)
    lw(LW)
    line(0, 30, AW, 30)
    person(105, 30, 200, beard=True, crown_kind="points", gift="chest")
    person(255, 30, 210, crown_kind="turban", gift="jar")
    person(405, 30, 195, beard=True, crown_kind="tall", gift="box")
    for gx in (30, 180, 330, 490):
        grass(gx, 30)


def art_gifts():
    sky([(40, 420), (120, 440), (390, 440), (470, 410), (256, 300)])
    bstar(256, 405, 30)
    treasure_chest(40, 90, 150, 130)
    incense_jar(256, 90, 120, 170)
    myrrh_bottle(420, 90, 115, 190)
    lw(LW)
    line(0, 88, AW, 88)
    bubble_text(115, 45, "GOLD", 28)
    bubble_text(256, 45, "FRANKINCENSE", 19)
    bubble_text(420, 45, "MYRRH", 28)


def art_emmanuel():
    sky([(40, 430), (470, 430), (256, 445), (30, 230), (480, 230), (120, 440), (390, 440)])
    fit_bubble(256, 330, "EMMANUEL", 80, 500, width=2.6)
    bubble_text(256, 250, "GOD WITH US", 52, width=2.4)
    manger(256, 15, 150)
    heart(90, 100, 34)
    heart(422, 100, 34)
    for x, y in ((150, 190), (362, 190), (40, 40), (472, 40)):
        sparkle(x, y, 12)


def art_light():
    sky([(40, 430), (110, 380), (400, 440), (470, 380), (60, 260), (450, 250)])
    candle(256, 50, 110, 230)
    holly(170, 50, 55, flip=True)
    holly(342, 50, 55)
    lw(LW)
    for x, y, s in ((70, 140, 22), (440, 140, 22), (100, 320, 16), (410, 320, 16)):
        star(x, y, s)


def art_love():
    sky([(40, 430), (100, 360), (420, 420), (470, 340), (40, 250), (480, 250)])
    xmas_tree(256, 25, 425)
    heart(256, 205, 46)
    bubble_text(256, 205, "JESUS", 18, width=1.4, space=1)
    gift_box(60, 25, 80, 70)
    gift_box(140, 25, 50, 45)
    gift_box(360, 25, 60, 55)
    gift_box(420, 25, 70, 80)
    lw(LW)
    line(0, 25, AW, 25)


# ---------------------------------------------------------------- special pages

def title_page():
    start()
    frame()
    bubble_text(W / 2, 690, "Jesus Is Born!", 64, width=3)
    plain(W / 2, 652, "A Christmas Coloring Book of Bible Verses", "Sans-Bold", 18)
    c.saveState()
    c.translate(AX, 190)
    reset()
    sky([(30, 400), (100, 430), (410, 430), (480, 400), (60, 300), (450, 300)])
    bstar(256, 380, 40)
    angel(100, 120, 190, "pray")
    angel(412, 120, 190, "pray")
    cloud(100, 115, 55)
    cloud(412, 115, 55)
    lw(LW)
    line(0, 0, AW, 0)
    manger(256, 0, 190)
    sheep(70, 0, 80)
    sheep(445, 0, 80, flip=True)
    c.restoreState()
    reset()
    lw(2.5)
    c.roundRect(70, 60, W - 140, 100, 14, stroke=1, fill=0)
    lw(LW)
    for i, ln in enumerate(simpleSplit(
            "“For unto you is born this day in the city of David a Saviour, "
            "which is Christ the Lord.”", "Serif-Italic", 18, W - 190)):
        plain(W / 2, 128 - i * 23, ln, "Serif-Italic", 18)
    plain(W / 2, 74, "— Luke 2:11", "Sans-Bold", 13)
    end_page()


THEMES = [
    ("Hope", "God Promised a Savior"), ("Faith", "Mary Says Yes to God"),
    ("Trust", "The Trip to Bethlehem"), ("Humility", "Born in a Manger"),
    ("God Sees Everyone", "Shepherds in the Field"), ("Joy", "Good News of Great Joy"),
    ("Praise & Peace", "Glory to God!"), ("Seeking Jesus", "Following the Star"),
    ("Giving", "Gifts for the King"), ("God With Us", "His Name Is Emmanuel"),
    ("Light", "Jesus, the Light"), ("Love", "God's Greatest Gift"),
]


def belongs_page(num):
    start()
    frame(num)
    bubble_text(W / 2, 700, "This Book Belongs To:", 38)
    lw(2)
    line(110, 640, W - 110, 640)
    lw(LW)
    star(90, 646, 14)
    star(W - 90, 646, 14)
    holly(70, 560, 45)
    holly(W - 70, 560, 45, flip=True)

    plain(W / 2, 585, "The Christmas Story in 12 Pictures", "Sans-Bold", 18)
    y = 552
    for i, (theme, title) in enumerate(THEMES):
        col = 0 if i < 6 else 1
        row = i % 6
        x = 75 + col * 245
        yy = y - row * 34
        circle(x + 10, yy + 4, 12)
        plain(x + 10, yy, str(i + 1), "Sans-Bold", 11)
        plain(x + 30, yy + 4, title, "Sans-Bold", 12, align="left")
        plain(x + 30, yy - 10, f"Theme: {theme}", "Sans", 10, align="left")

    lw(2)
    c.roundRect(60, 60, W - 120, 270, 14, stroke=1, fill=0)
    lw(LW)
    plain(W / 2, 302, "A Note for Parents & Teachers", "Sans-Bold", 16)
    note = ("Each page tells one part of the true Christmas story from the Bible. "
            "Before your child colors, read the verse aloud together. Talk about "
            "the theme word and the “Think about it” question at the bottom "
            "of the page. Do one page a day for the twelve days before Christmas, "
            "or use the pages in Sunday school, children’s church, or family "
            "devotions. The last pages invite your child to draw their favorite part "
            "of the story and to write a Christmas prayer to Jesus. Scripture is quoted "
            "from the King James Version.")
    ty = 275
    for ln in simpleSplit(note, "Sans", 12.5, W - 170):
        plain(W / 2, ty, ln, "Sans", 12.5)
        ty -= 17
    plain(W / 2, 90, "“Glory to God in the highest!” — Luke 2:14",
          "Serif-Italic", 14)
    end_page()


def draw_page(num):
    start()
    frame(num)
    fit_bubble(W / 2, 712, "Draw Your Favorite Part!", 38, W - 90)
    plain(W / 2, 680, "Draw your favorite part of the Christmas story inside the box.",
          "Sans", 14)
    lw(2.5)
    c.roundRect(60, 150, W - 120, 510, 16, stroke=1, fill=0)
    lw(LW)
    for x, y in ((60, 150), (W - 60, 150), (60, 660), (W - 60, 660)):
        star(x, y, 16)
    plain(80, 110, "My picture is about:", "Sans-Bold", 14, align="left")
    lw(2)
    line(230, 108, W - 80, 108)
    line(80, 75, W - 80, 75)
    lw(LW)
    end_page()


def prayer_page(num):
    start()
    frame(num)
    fit_bubble(W / 2, 712, "My Christmas Prayer", 40, W - 90)
    holly(70, 690, 40)
    holly(W - 70, 690, 40, flip=True)
    plain(W / 2, 670, "Write or draw a prayer to thank Jesus for coming to earth.",
          "Sans", 14)
    plain(90, 625, "Dear Jesus,", "Serif-BoldItalic", 22, align="left")
    lw(1.8)
    for i in range(8):
        y = 590 - i * 38
        c.setDash(4, 5)
        line(90, y, W - 90, y)
    c.setDash()
    plain(W - 90, 270, "Love,  ____________________", "Serif-BoldItalic", 20, align="right")
    lw(2)
    c.roundRect(70, 60, W - 140, 175, 14, stroke=1, fill=0)
    lw(LW)
    plain(W / 2, 208, "A Prayer to Pray Together", "Sans-Bold", 15)
    prayer = ("Dear God, thank You for sending baby Jesus to be our Savior. "
              "Thank You that You are always with us. Help me to love others, "
              "share Your good news, and shine Your light this Christmas. "
              "Happy birthday, Jesus! In Jesus’ name, Amen.")
    ty = 182
    for ln in simpleSplit(prayer, "Serif-Italic", 16, W - 200):
        plain(W / 2, ty, ln, "Serif-Italic", 16)
        ty -= 21
    heart(110, 85, 14)
    heart(W - 110, 85, 14)
    star(W / 2, 82, 14)
    end_page()


# ---------------------------------------------------------------- book

PAGES = [
    ("God Promised a Savior",
     "For unto us a child is born, unto us a son is given: and his name shall be called "
     "Wonderful, Counsellor, The mighty God, The everlasting Father, The Prince of Peace.",
     "Isaiah 9:6", "Hope",
     "Long before Jesus was born, God promised He would come. God always keeps His "
     "promises! What is one promise God has made to you?", art_promise),
    ("Mary Says Yes to God",
     "And the angel said unto her, Fear not, Mary: for thou hast found favour with God. "
     "And, behold, thou shalt ... bring forth a son, and shalt call his name JESUS.",
     "Luke 1:30-31", "Faith",
     "Mary trusted God even when she did not understand everything. When can you "
     "trust God?", art_gabriel),
    ("The Trip to Bethlehem",
     "And Joseph also went up from Galilee ... unto the city of David, which is called "
     "Bethlehem ... with Mary his espoused wife.",
     "Luke 2:4-5", "Trust",
     "Mary and Joseph took a long trip and trusted God to take care of them. How does "
     "God take care of you?", art_journey),
    ("Born in a Manger",
     "And she brought forth her firstborn son, and wrapped him in swaddling clothes, and "
     "laid him in a manger; because there was no room for them in the inn.",
     "Luke 2:7", "Humility",
     "The King of all kings was born in a stable! Why do you think God chose such a "
     "simple, humble place?", art_nativity),
    ("Shepherds in the Field",
     "And there were in the same country shepherds abiding in the field, keeping watch "
     "over their flock by night.",
     "Luke 2:8", "God Sees Everyone",
     "God shared the news first with ordinary shepherds. Everyone matters to God, "
     "including you! Who can you tell about Jesus?", art_shepherds),
    ("Good News of Great Joy",
     "Fear not: for, behold, I bring you good tidings of great joy, which shall be to all "
     "people. For unto you is born this day in the city of David a Saviour, which is "
     "Christ the Lord.",
     "Luke 2:10-11", "Joy",
     "Jesus is the best news ever! What makes your heart happy when you think about "
     "Jesus?", art_good_news),
    ("Glory to God!",
     "Glory to God in the highest, and on earth peace, good will toward men.",
     "Luke 2:14", "Praise & Peace",
     "The angels sang praises to God. What is your favorite song to sing to God? Sing "
     "it while you color!", art_glory),
    ("Following the Star",
     "Where is he that is born King of the Jews? for we have seen his star in the east, "
     "and are come to worship him.",
     "Matthew 2:2", "Seeking Jesus",
     "The wise men traveled very far to find Jesus. How can you look for Jesus every "
     "day? (Hint: prayer and reading the Bible!)", art_wisemen),
    ("Gifts for the King",
     "And when they were come into the house, they saw the young child with Mary his "
     "mother, and fell down, and worshipped him: and ... they presented unto him gifts; "
     "gold, and frankincense, and myrrh.",
     "Matthew 2:11", "Giving",
     "The wise men gave Jesus their best gifts. What gift can you give Jesus this year? "
     "(Your love, your kindness, your heart!)", art_gifts),
    ("His Name Is Emmanuel",
     "Behold, a virgin shall be with child, and shall bring forth a son, and they shall "
     "call his name Emmanuel, which being interpreted is, God with us.",
     "Matthew 1:23", "God With Us",
     "Emmanuel means “God with us.” Jesus is with you at home, at school, and "
     "everywhere you go!", art_emmanuel),
    ("Jesus, the Light",
     "I am the light of the world: he that followeth me shall not walk in darkness, but "
     "shall have the light of life.",
     "John 8:12", "Light",
     "Christmas lights remind us that Jesus is the Light of the World. How can you shine "
     "His light for others?", art_light),
    ("God's Greatest Gift",
     "For God so loved the world, that he gave his only begotten Son, that whosoever "
     "believeth in him should not perish, but have everlasting life.",
     "John 3:16", "Love",
     "Jesus is the greatest gift of all! Who can you show God’s love to this "
     "Christmas?", art_love),
]


def copyright_page(num, author):
    start()
    owner = f" {author}" if author else ""
    lines = [
        (f"{BOOK_TITLE} {BOOK_SUBTITLE}", "Sans-Bold", 12),
        (f"Copyright \u00a9 {YEAR}{owner}. All rights reserved.", "Sans", 11),
        ("", "Sans", 6),
        ("No part of this book may be reproduced without written permission,", "Sans", 10),
        ("except that a parent or teacher may copy pages for use with their own", "Sans", 10),
        ("children or class.", "Sans", 10),
        ("", "Sans", 6),
        ("Scripture quotations are from the King James Version (public domain).", "Sans", 10),
        ("", "Sans", 6),
        ("Coloring tip: slip a sheet of paper behind the page when you use markers.", "Sans", 10),
    ]
    y = 230
    for text, font, size in lines:
        if text:
            plain(W / 2, y, text, font, size)
        y -= size + 6
    star(W / 2, 260, 10)
    plain(W / 2, 31, str(num), "Sans", 9)
    end_page()


def color_test_page(num):
    """Back of a coloring page: soaks up marker bleed and lets kids try colors."""
    start()
    plain(W / 2, 700, "Test Your Colors Here", "Round", 20)
    plain(W / 2, 680, "Try your crayons, pencils, or markers in the shapes below.", "Sans", 11)
    lw(2)
    for i in range(12):
        col, row = i % 4, i // 4
        x, y = 156 + col * 100, 600 - row * 100
        if i % 3 == 0:
            circle(x, y, 32)
        elif i % 3 == 1:
            star(x, y, 38, 17)
        else:
            heart(x, y + 10, 30)
    lw(LW)
    plain(W / 2, 290, "\u201cFor God so loved the world\u2026\u201d \u2014 John 3:16", "Serif-Italic", 14)
    plain(W / 2, 31, str(num), "Sans", 9)
    end_page()


def last_page(num):
    start()
    frame(num)
    bubble_text(W / 2, 560, "Merry Christmas!", 56, width=2.6)
    bubble_text(W / 2, 470, "Jesus Loves You!", 44, width=2.4)
    heart(W / 2, 360, 50)
    for x, y in ((150, 380), (W - 150, 380), (200, 300), (W - 200, 300)):
        star(x, y, 18)
    plain(W / 2, 220, "\u201cWe love him, because he first loved us.\u201d", "Serif-Italic", 18)
    plain(W / 2, 196, "\u2014 1 John 4:19", "Sans-Bold", 13)
    end_page()


def build(path=OUT, author=""):
    """Lay out the KDP interior. Coloring pages fall on right-hand (odd) pages."""
    global c
    register_fonts()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    c = canvas.Canvas(path, pagesize=letter, initialFontName="Sans")
    c.setTitle(f"{BOOK_TITLE} {BOOK_SUBTITLE}")
    c.setAuthor(author or BOOK_TITLE)
    c.setSubject("Christian Christmas coloring book for kids with KJV Bible verses")
    title_page()                     # 1
    copyright_page(2, author)        # 2
    belongs_page(3)                  # 3
    color_test_page(4)               # 4
    num = 5
    for title, verse, ref, theme, q, art in PAGES:
        verse_page(num, title, verse, ref, theme, q, art)
        color_test_page(num + 1)
        num += 2
    draw_page(num)                   # 29
    color_test_page(num + 1)         # 30
    prayer_page(num + 2)             # 31
    last_page(num + 3)               # 32
    pages = c.getPageNumber() - 1
    c.save()
    return path, pages


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--author", default="", help="name printed on the copyright page")
    args = ap.parse_args()
    out, pages = build(author=args.author)
    print(f"Wrote {out} ({pages} pages)")
