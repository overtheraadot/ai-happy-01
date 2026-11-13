#!/usr/bin/env python3
"""Butterfly on the Nose -- make.fun ai-happy-01 entry.

Draws a single 1024x1024 PNG with nothing but the Python 3 standard
library (zlib for the PNG encoder). No files are read, no network is
touched, and a fixed seed makes the output byte-identical on every run.

The scene: a joyful golden retriever puppy in a sunny wildflower
meadow at golden hour, mid-giggle -- eyes squeezed happily shut, mouth
open, tongue out -- while a bright orange butterfly lands right on its
nose. Big shapes, a warm palette, no text: it has to read at a glance
and still land at ~300 px.
"""

import math
import os
import struct
import zlib
from random import Random

SIZE = 1024
HORIZON = 640          # y where sky ends and meadow begins
SEED = 20261113


# ---------------------------------------------------------------- palette
class Pal:
    SKY = [  # (stop, rgb) gradient, top -> horizon; golden hour
        (0.00, (255, 205, 118)),
        (0.50, (255, 190, 128)),
        (1.00, (255, 168, 128)),
    ]
    SUN = (255, 238, 175)
    SUN_GLOW = (255, 205, 110)
    CLOUD = (255, 246, 226)
    HILL_BACK = (168, 196, 118)
    HILL_FRONT = (124, 172, 90)
    MEADOW_HI = (152, 198, 102)
    MEADOW_LO = (96, 152, 72)
    GRASS_DK = (78, 132, 60)
    GRASS_LT = (178, 214, 120)
    FUR = (232, 178, 96)        # golden retriever gold
    FUR_DK = (198, 138, 58)     # floppy ears
    FUR_LT = (248, 214, 150)    # face / chest cream-gold
    MUZZLE = (252, 230, 182)
    NOSE = (62, 40, 28)
    MOUTH = (122, 62, 46)
    TONGUE = (238, 122, 132)
    EYE = (92, 56, 30)
    BLUSH = (246, 150, 128)
    FLOWER = [  # petal colours
        (255, 255, 255),
        (244, 140, 178),
        (255, 214, 90),
        (186, 140, 220),
        (255, 150, 80),
    ]
    FLOWER_CTR = (255, 196, 60)
    BUTTERFLY = (255, 150, 52)
    BUTTERFLY2 = (255, 210, 70)
    BUTTERFLY3 = (255, 255, 255)
    WING_DK = (70, 42, 28)


# ---------------------------------------------------------------- canvas
class Canvas:
    """A flat RGB buffer with a few scanline drawing primitives."""

    def __init__(self, w, h):
        self.w = w
        self.h = h
        self.px = bytearray(w * h * 3)

    def hline(self, y, x0, x1, rgb):
        if y < 0 or y >= self.h:
            return
        x0 = max(0, int(x0))
        x1 = min(self.w - 1, int(x1))
        if x1 < x0:
            return
        n = x1 - x0 + 1
        i = (y * self.w + x0) * 3
        self.px[i:i + 3 * n] = bytes(rgb) * n

    def hline_alpha(self, y, x0, x1, rgb, alpha):
        if y < 0 or y >= self.h or alpha <= 0.0:
            return
        if alpha >= 1.0:
            self.hline(y, x0, x1, rgb)
            return
        x0 = max(0, int(x0))
        x1 = min(self.w - 1, int(x1))
        if x1 < x0:
            return
        a = int(alpha * 256)
        ia = 256 - a
        r, g, b = rgb
        i = (y * self.w + x0) * 3
        for _ in range(x1 - x0 + 1):
            self.px[i] = (r * a + self.px[i] * ia) >> 8
            self.px[i + 1] = (g * a + self.px[i + 1] * ia) >> 8
            self.px[i + 2] = (b * a + self.px[i + 2] * ia) >> 8
            i += 3

    def dot(self, x, y, rgb, alpha=1.0):
        if 0 <= x < self.w and 0 <= y < self.h and alpha > 0.0:
            a = int(alpha * 256)
            ia = 256 - a
            i = (y * self.w + x) * 3
            self.px[i] = (rgb[0] * a + self.px[i] * ia) >> 8
            self.px[i + 1] = (rgb[1] * a + self.px[i + 1] * ia) >> 8
            self.px[i + 2] = (rgb[2] * a + self.px[i + 2] * ia) >> 8

    def disc(self, cx, cy, r, rgb, alpha=1.0):
        r = int(r)
        for y in range(max(0, cy - r), min(self.h - 1, cy + r) + 1):
            dy = y - cy
            dx = int(math.sqrt(max(0, r * r - dy * dy)))
            self.hline_alpha(y, cx - dx, cx + dx, rgb, alpha)

    def ellipse(self, cx, cy, rx, ry, rgb, alpha=1.0):
        rx, ry = int(rx), int(ry)
        for y in range(max(0, cy - ry), min(self.h - 1, cy + ry) + 1):
            t = (y - cy) / ry
            dx = int(rx * math.sqrt(max(0.0, 1.0 - t * t)))
            self.hline_alpha(y, cx - dx, cx + dx, rgb, alpha)

    def poly(self, pts, rgb, alpha=1.0):
        """Scanline polygon fill."""
        edges = []
        n = len(pts)
        for i in range(n):
            x0, y0 = pts[i]
            x1, y1 = pts[(i + 1) % n]
            if y0 != y1:
                edges.append((y0, y1, x0, x1))
        ymin = max(0, int(min(p[1] for p in pts)))
        ymax = min(self.h - 1, int(max(p[1] for p in pts)))
        for y in range(ymin, ymax + 1):
            xs = []
            for y0, y1, x0, x1 in edges:
                if (y0 <= y < y1) or (y1 <= y < y0):
                    xs.append(x0 + (y - y0) / (y1 - y0) * (x1 - x0))
            xs.sort()
            for i in range(0, len(xs) - 1, 2):
                self.hline_alpha(y, math.ceil(xs[i]), math.floor(xs[i + 1]),
                                 rgb, alpha)

    def glow(self, cx, cy, r, rgb, peak):
        """Soft radial glow, quadratic falloff."""
        r2 = r * r
        R, G, B = rgb
        for y in range(max(0, cy - r), min(self.h - 1, cy + r) + 1):
            dy = y - cy
            dy2 = dy * dy
            span = int(math.sqrt(max(0, r2 - dy2)))
            for x in range(max(0, cx - span), min(self.w - 1, cx + span) + 1):
                dx = x - cx
                f = 1.0 - (dx * dx + dy2) / r2
                if f <= 0.0:
                    continue
                a = int(peak * f * f * 256)
                if a <= 0:
                    continue
                ia = 256 - a
                i = (y * self.w + x) * 3
                self.px[i] = (R * a + self.px[i] * ia) >> 8
                self.px[i + 1] = (G * a + self.px[i + 1] * ia) >> 8
                self.px[i + 2] = (B * a + self.px[i + 2] * ia) >> 8

    def thick_polyline(self, pts, radius, rgb, alpha=1.0):
        for x, y in pts:
            self.disc(x, y, radius, rgb, alpha)

    def rot_ellipse(self, cx, cy, rx, ry, ang_deg, rgb, alpha=1.0):
        """Ellipse rotated by ang_deg (clockwise, degrees)."""
        a = math.radians(ang_deg)
        ca, sa = math.cos(a), math.sin(a)
        pts = []
        for k in range(28):
            th = 2 * math.pi * k / 28
            ex, ey = rx * math.cos(th), ry * math.sin(th)
            pts.append((int(cx + ex * ca - ey * sa),
                        int(cy + ex * sa + ey * ca)))
        self.poly(pts, rgb, alpha)


def quad_bezier(p0, p1, p2, steps):
    pts = []
    for i in range(steps + 1):
        t = i / steps
        u = 1.0 - t
        pts.append((
            int(u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0]),
            int(u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1]),
        ))
    return pts


def lerp_stops(stops, t):
    for i in range(len(stops) - 1):
        t0, c0 = stops[i]
        t1, c1 = stops[i + 1]
        if t <= t1:
            f = 0.0 if t1 == t0 else (t - t0) / (t1 - t0)
            return tuple(int(c0[k] + (c1[k] - c0[k]) * f) for k in range(3))
    return stops[-1][1]


# ---------------------------------------------------------------- scene
def paint_sky(cv):
    for y in range(HORIZON):
        cv.hline(y, 0, SIZE - 1, lerp_stops(Pal.SKY, y / HORIZON))
    # low golden sun, upper right, with a warm halo
    cv.glow(790, 210, 330, Pal.SUN_GLOW, 0.32)
    cv.disc(790, 210, 86, Pal.SUN)
    cv.disc(790, 210, 78, (255, 243, 200))
    # a few soft clouds, kept clear of the sun
    for cx, cy, rx, ry in [(170, 130, 120, 26), (430, 80, 150, 24),
                           (120, 300, 100, 22), (620, 330, 90, 20)]:
        cv.ellipse(cx, cy, rx, ry, Pal.CLOUD, 0.32)
        cv.ellipse(cx + 30, cy - 12, rx // 2, ry // 2 + 6, Pal.CLOUD, 0.30)


def paint_hills(cv):
    cv.poly([(0, HORIZON), (0, 600), (140, 566), (300, 606), (470, 572),
             (640, 612), (820, 576), (1024, 608), (1024, HORIZON)],
            Pal.HILL_BACK)
    cv.poly([(0, HORIZON), (0, 636), (180, 612), (380, 644), (560, 618),
             (760, 648), (1024, 622), (1024, HORIZON)], Pal.HILL_FRONT)


def paint_meadow(cv, rng):
    for y in range(HORIZON, SIZE):
        t = (y - HORIZON) / (SIZE - HORIZON)
        c = tuple(int(Pal.MEADOW_HI[k] + (Pal.MEADOW_LO[k] - Pal.MEADOW_HI[k]) * t)
                  for k in range(3))
        cv.hline(y, 0, SIZE - 1, c)
    # warm sunlight pooling on the grass
    cv.ellipse(512, 830, 430, 130, (255, 220, 130), 0.10)


def paint_grass(cv, rng):
    for _ in range(120):
        x = rng.randrange(10, 1014)
        y = rng.randrange(HORIZON + 20, 1010)
        h = rng.randrange(10, 26)
        lean = rng.randrange(-8, 9)
        col = rng.choice([Pal.GRASS_DK, Pal.GRASS_LT, Pal.MEADOW_LO])
        cv.poly([(x, y), (x + lean, y - h), (x + 4, y)], col, 0.85)


def paint_flower(cv, cx, cy, r, petal, centre):
    for k in range(5):
        th = 2 * math.pi * k / 5 - math.pi / 2
        px = cx + int(r * 0.62 * math.cos(th))
        py = cy + int(r * 0.62 * math.sin(th))
        cv.disc(px, py, int(r * 0.48), petal)
    cv.disc(cx, cy, int(r * 0.42), centre)


def paint_flowers(cv, rng):
    # scattered meadow flowers, small-to-medium, none over the puppy
    for _ in range(46):
        x = rng.randrange(30, 994)
        y = rng.randrange(HORIZON + 30, 1000)
        if (x - 512) ** 2 + (y - 800) ** 2 < 330 ** 2:
            continue  # keep the puppy clear
        r = rng.choice([9, 11, 13, 15])
        paint_flower(cv, x, y, r, rng.choice(Pal.FLOWER), Pal.FLOWER_CTR)
    # big soft-focus foreground blooms framing the bottom corners
    for cx, cy, r, petal in [(88, 952, 42, (244, 140, 178)),
                             (946, 936, 46, (255, 255, 255)),
                             (150, 990, 34, (255, 214, 90)),
                             (890, 994, 36, (186, 140, 220))]:
        paint_flower(cv, cx, cy, r, petal, Pal.FLOWER_CTR)


def paint_butterfly(cv, cx, cy, size, wing, angle=0, flap=1.0):
    """Two pairs of wings, seen from above, tilted by angle."""
    a = math.radians(angle)
    ca, sa = math.cos(a), math.sin(a)

    def wing_pts(dx, dy, rx, ry, tilt):
        t = math.radians(tilt)
        ct, st = math.cos(t), math.sin(t)
        pts = []
        for k in range(22):
            th = 2 * math.pi * k / 22
            ex, ey = rx * math.cos(th), ry * math.sin(th)
            wx, wy = ex * ct - ey * st, ex * st + ey * ct
            pts.append((int(cx + (dx + wx) * ca - (dy + wy) * sa),
                        int(cy + (dx + wx) * sa + (dy + wy) * ca)))
        return pts

    s = size / 40.0
    up = int(26 * s * flap)
    # upper wings, then lower wings, both sides
    for sgn in (-1, 1):
        cv.poly(wing_pts(sgn * 16 * s, -14 * s, 20 * s, up, sgn * -18),
                wing, 0.95)
        cv.poly(wing_pts(sgn * 14 * s, 12 * s, 15 * s, 13 * s, sgn * 22),
                wing, 0.95)
        # pale spot on each upper wing
        cv.disc(int(cx + sgn * 16 * s * ca + 14 * s * sa),
                int(cy + sgn * 16 * s * sa - 14 * s * ca),
                int(4 * s), (255, 255, 255), 0.9)
    # body + antennae
    cv.thick_polyline(quad_bezier((cx, cy - 16 * s), (cx, cy), (cx, cy + 18 * s), 8),
                      int(3 * s), Pal.WING_DK)
    cv.thick_polyline(quad_bezier((cx, cy - 16 * s), (cx - 8 * s, cy - 30 * s),
                                  (cx - 12 * s, cy - 34 * s), 8),
                      1, Pal.WING_DK)
    cv.thick_polyline(quad_bezier((cx, cy - 16 * s), (cx + 8 * s, cy - 30 * s),
                                  (cx + 12 * s, cy - 34 * s), 8),
                      1, Pal.WING_DK)


def paint_puppy(cv):
    # ---- body: big golden mass filling the lower centre, cropped below;
    # its top tucks under the chin so head and body read as one puppy
    cv.ellipse(512, 960, 315, 300, Pal.FUR)
    cv.ellipse(512, 880, 185, 165, Pal.FUR_LT)      # cream chest
    # ---- front paws, outlined so they read against the chest
    for px in (410, 614):
        cv.ellipse(px, 955, 76, 60, Pal.FUR_DK)
        cv.ellipse(px, 955, 70, 54, Pal.FUR_LT)
        for dx in (-18, 12):
            cv.thick_polyline([(px + dx, 938), (px + dx, 970)], 2,
                              Pal.FUR_DK, 0.7)

    # ---- floppy ears, hanging beside the head
    cv.rot_ellipse(306, 520, 58, 132, 24, Pal.FUR_DK)
    cv.rot_ellipse(718, 520, 58, 132, -24, Pal.FUR_DK)
    cv.rot_ellipse(318, 530, 34, 96, 24, (214, 156, 74))
    cv.rot_ellipse(706, 530, 34, 96, -24, (214, 156, 74))

    # ---- head
    cv.disc(512, 480, 205, Pal.FUR)
    cv.ellipse(512, 505, 168, 152, Pal.FUR_LT)      # lighter face front
    # forehead tuft: three little spikes of fur
    cv.poly([(470, 300), (492, 268), (506, 300)], Pal.FUR)
    cv.poly([(500, 296), (524, 262), (538, 298)], Pal.FUR)
    cv.poly([(528, 298), (552, 270), (562, 302)], Pal.FUR)

    # ---- happy closed eyes: squeezed-shut arches
    for ex0 in (388, 572):
        arc = quad_bezier((ex0, 448), (ex0 + 34, 412), (ex0 + 68, 448), 16)
        cv.thick_polyline(arc, 8, Pal.EYE)
    # ---- rosy cheeks
    cv.disc(392, 566, 30, Pal.BLUSH, 0.5)
    cv.disc(632, 566, 30, Pal.BLUSH, 0.5)

    # ---- muzzle, nose, open smiling mouth, tongue
    cv.ellipse(512, 585, 132, 92, Pal.MUZZLE)
    cv.ellipse(512, 522, 44, 30, Pal.NOSE)
    cv.disc(498, 512, 6, (255, 255, 255), 0.85)    # nose glint
    cv.ellipse(512, 610, 50, 38, Pal.MOUTH)
    cv.ellipse(512, 626, 32, 28, Pal.TONGUE)
    cv.thick_polyline([(512, 606), (512, 640)], 2, (190, 80, 80), 0.8)
    # smile creases sweeping up from the mouth corners
    cv.thick_polyline(quad_bezier((462, 606), (446, 578), (438, 556), 10),
                      3, Pal.EYE, 0.8)
    cv.thick_polyline(quad_bezier((562, 606), (578, 578), (586, 556), 10),
                      3, Pal.EYE, 0.8)
    # whisker dots on the muzzle
    for dx, dy in [(-84, -8), (-92, 12), (84, -8), (92, 12), (-70, 22), (70, 22)]:
        cv.disc(512 + dx, 585 + dy, 3, Pal.FUR_DK, 0.7)

    # ---- the surprise: a butterfly has landed on the puppy's nose
    paint_butterfly(cv, 512, 468, 46, Pal.BUTTERFLY, angle=0, flap=0.55)


def paint_flying_butterflies(cv):
    paint_butterfly(cv, 168, 238, 44, Pal.BUTTERFLY2, angle=-18, flap=1.0)
    paint_butterfly(cv, 856, 306, 40, Pal.BUTTERFLY, angle=14, flap=0.8)
    paint_butterfly(cv, 812, 138, 34, Pal.BUTTERFLY3, angle=8, flap=1.0)
    paint_butterfly(cv, 240, 420, 30, Pal.BUTTERFLY3, angle=-10, flap=0.9)


# ---------------------------------------------------------------- PNG out
def encode_png(cv):
    raw = bytearray()
    for y in range(cv.h):
        raw.append(0)  # filter: none
        raw += cv.px[y * cv.w * 3:(y + 1) * cv.w * 3]
    comp = zlib.compress(bytes(raw), 9)

    def chunk(tag, data):
        out = struct.pack(">I", len(data)) + tag + data
        return out + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", cv.w, cv.h, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", comp)
    png += chunk(b"IEND", b"")
    return png


def main():
    rng = Random(SEED)
    cv = Canvas(SIZE, SIZE)
    paint_sky(cv)
    paint_hills(cv)
    paint_meadow(cv, rng)
    paint_grass(cv, rng)
    paint_flowers(cv, rng)
    paint_puppy(cv)
    paint_flying_butterflies(cv)

    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", ".")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "entry.png")
    data = encode_png(cv)
    with open(path, "wb") as f:
        f.write(data)
    print(f"wrote {path} ({len(data)} bytes)")


if __name__ == "__main__":
    main()
