#!/usr/bin/env python3
"""Tsuru no Yoru -- The Paper Crane Night.

A deterministic generative-art program for the make.fun bounty
"Make the coolest art" (coolest-art-01).

What it does
------------
Draws one original 1024x1024 piece of art, ukiyo-e inspired, entirely
procedurally with the Python standard library only:

  * a deep indigo night sky with a seeded star field and one shooting star
  * a huge vermilion sun with a gold ring, glowing over the sea
  * a large white origami paper crane in flight -- the hero of the piece --
    built from flat shaded facets with gold fold lines and a vermilion crown
  * three small distant cranes for depth
  * a band of stylised Hokusai-like waves with white foam crests

There is no network access, no randomness that is not seeded, and no
external asset: the same run always writes the same bytes, so the two
sandbox runs required by the bounty produce identical files.

Output
------
Writes ``entry.png`` into ``$MAKEFUN_OUTPUT_DIR`` (the sandbox's /output),
or into ``/output`` when the variable is not set. The PNG is encoded by
hand with zlib (colour type 2, 8-bit RGB, per-row filter choice), so the
program needs nothing beyond the standard library.

Run locally:
    mkdir -p out && MAKEFUN_OUTPUT_DIR=out python3 main.py
"""

import binascii
import hashlib
import math
import os
import random
import struct
import zlib

# ---------------------------------------------------------------- canvas ---
W = 1024
H = 1024
SEED = 20261113  # fixed seed: every run draws the same picture

canvas = bytearray(W * H * 3)

# --------------------------------------------------------------- palette ---
INK = (10, 14, 38)          # deepest night
SKY_TOP = (7, 11, 36)
SKY_MID = (16, 27, 69)
SKY_LOW = (30, 58, 95)      # horizon glow
SUN = (238, 74, 36)         # vermilion
SUN_DARK = (214, 58, 26)
SUN_GLOW = (255, 106, 61)
GOLD = (242, 193, 78)
PAPER = (247, 245, 238)     # crane paper, lit
PAPER_SHADOW = (227, 231, 242)
PAPER_DEEP = (203, 211, 230)
PAPER_FAR = (199, 208, 228)  # far wing, in shade
FOAM = (245, 248, 252)
WAVE_BACK = (12, 62, 78)
WAVE_MID = (15, 90, 110)
WAVE_FRONT = (23, 128, 154)
CLOUD = (38, 56, 104)

rng = random.Random(SEED)


# ------------------------------------------------------------ primitives ---
def hline(x0, x1, y, color):
    """Fill a horizontal span of pixels (clipped)."""
    if y < 0 or y >= H:
        return
    x0 = max(0, int(x0))
    x1 = min(W - 1, int(x1))
    if x1 < x0:
        return
    n = x1 - x0 + 1
    i = (y * W + x0) * 3
    canvas[i:i + n * 3] = bytes(color) * n


def blend_px(x, y, color, alpha):
    """Alpha-blend one pixel over the canvas."""
    if 0 <= x < W and 0 <= y < H and alpha > 0:
        i = (y * W + x) * 3
        a = alpha
        canvas[i] = int(color[0] * a + canvas[i] * (1 - a) + 0.5)
        canvas[i + 1] = int(color[1] * a + canvas[i + 1] * (1 - a) + 0.5)
        canvas[i + 2] = int(color[2] * a + canvas[i + 2] * (1 - a) + 0.5)


def fill_poly(pts, color):
    """Scanline-fill a polygon given as [(x, y), ...]."""
    ys = [p[1] for p in pts]
    y0 = max(0, int(math.floor(min(ys))))
    y1 = min(H - 1, int(math.ceil(max(ys))))
    n = len(pts)
    for y in range(y0, y1 + 1):
        yc = y + 0.5
        xs = []
        for i in range(n):
            x0, ya = pts[i]
            x1, yb = pts[(i + 1) % n]
            if ya == yb:
                continue
            lo, hi = (ya, yb) if ya < yb else (yb, ya)
            if lo <= yc < hi:
                t = (yc - ya) / (yb - ya)
                xs.append(x0 + t * (x1 - x0))
        xs.sort()
        for k in range(0, len(xs) - 1, 2):
            xa = int(math.ceil(xs[k] - 0.5))
            xb = int(math.floor(xs[k + 1] - 0.5))
            hline(xa, xb, y, color)


def fill_circle(cx, cy, r, color):
    """Fill a disc (float centre/radius allowed)."""
    r = float(r)
    y0 = max(0, int(math.floor(cy - r)))
    y1 = min(H - 1, int(math.ceil(cy + r)))
    for y in range(y0, y1 + 1):
        dy = (y + 0.5) - cy
        d2 = r * r - dy * dy
        if d2 < 0:
            continue
        dx = math.sqrt(d2)
        hline(cx - dx, cx + dx, y, color)


def fill_circle_alpha(cx, cy, r, color, alpha):
    """Fill a disc with a constant alpha over the canvas."""
    r = float(r)
    y0 = max(0, int(math.floor(cy - r)))
    y1 = min(H - 1, int(math.ceil(cy + r)))
    for y in range(y0, y1 + 1):
        dy = (y + 0.5) - cy
        d2 = r * r - dy * dy
        if d2 < 0:
            continue
        dx = math.sqrt(d2)
        for x in range(max(0, int(cx - dx)), min(W - 1, int(cx + dx)) + 1):
            blend_px(x, y, color, alpha)


def ring(cx, cy, r, w, color):
    """Draw a circle outline of width w."""
    ro = r + w / 2.0
    ri = r - w / 2.0
    y0 = max(0, int(math.floor(cy - ro)))
    y1 = min(H - 1, int(math.ceil(cy + ro)))
    for y in range(y0, y1 + 1):
        dy = (y + 0.5) - cy
        d2o = ro * ro - dy * dy
        if d2o < 0:
            continue
        xo = math.sqrt(d2o)
        d2i = ri * ri - dy * dy
        xi = math.sqrt(d2i) if d2i > 0 else 0.0
        hline(cx - xo, cx - xi, y, color)
        hline(cx + xi, cx + xo, y, color)


def line(x0, y0, x1, y1, w, color, alpha=1.0):
    """Draw a thick line by stamping discs along it."""
    dist = math.hypot(x1 - x0, y1 - y0)
    steps = max(1, int(dist / max(1.0, w * 0.35)))
    for i in range(steps + 1):
        t = i / steps
        x = x0 + (x1 - x0) * t
        y = y0 + (y1 - y0) * t
        if alpha >= 1.0:
            fill_circle(x, y, w / 2.0, color)
        else:
            fill_circle_alpha(x, y, w / 2.0, color, alpha)


def soft_disc(cx, cy, r, color, strength):
    """Radial glow: colour fading smoothly to nothing at radius r."""
    r = float(r)
    x0 = max(0, int(cx - r))
    x1 = min(W - 1, int(cx + r))
    y0 = max(0, int(cy - r))
    y1 = min(H - 1, int(cy + r))
    for y in range(y0, y1 + 1):
        dy = (y + 0.5 - cy) / r
        for x in range(x0, x1 + 1):
            dx = (x + 0.5 - cx) / r
            d2 = dx * dx + dy * dy
            if d2 < 1.0:
                a = strength * (1.0 - d2) * (1.0 - d2)
                blend_px(x, y, color, a)


def soft_ellipse(cx, cy, rx, ry, color, strength):
    """Soft elliptical glow, same falloff as soft_disc."""
    x0 = max(0, int(cx - rx))
    x1 = min(W - 1, int(cx + rx))
    y0 = max(0, int(cy - ry))
    y1 = min(H - 1, int(cy + ry))
    for y in range(y0, y1 + 1):
        dy = (y + 0.5 - cy) / ry
        for x in range(x0, x1 + 1):
            dx = (x + 0.5 - cx) / rx
            d2 = dx * dx + dy * dy
            if d2 < 1.0:
                a = strength * (1.0 - d2) * (1.0 - d2)
                blend_px(x, y, color, a)


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t + 0.5) for i in range(3))


# ------------------------------------------------------------- the scene ---
def draw_sky():
    """Three-stop vertical gradient, deep indigo to horizon teal-blue."""
    for y in range(H):
        t = y / (H - 1)
        if t < 0.55:
            c = lerp(SKY_TOP, SKY_MID, t / 0.55)
        else:
            c = lerp(SKY_MID, SKY_LOW, (t - 0.55) / 0.45)
        hline(0, W - 1, y, c)


SUN_C = (800, 190)
SUN_R = 120


def draw_stars():
    """Seeded star field (kept out of the sun disc) plus one shooting star."""
    for _ in range(240):
        x = rng.uniform(0, W)
        y = rng.uniform(0, 780)
        if math.hypot(x - SUN_C[0], y - SUN_C[1]) < SUN_R + 18:
            continue
        r = rng.choice([0.8, 1.0, 1.2, 1.5, 1.8])
        warm = rng.random() < 0.25
        col = (255, 226, 170) if warm else (235, 240, 255)
        a = rng.uniform(0.35, 1.0)
        if r <= 1.0:
            blend_px(int(x), int(y), col, a)
        else:
            fill_circle_alpha(x, y, r, col, a)
    # a few bright stars with a four-point sparkle
    for _ in range(10):
        x = rng.uniform(40, W - 40)
        y = rng.uniform(40, 620)
        if math.hypot(x - SUN_C[0], y - SUN_C[1]) < SUN_R + 30:
            continue
        L = rng.uniform(5, 10)
        fill_circle_alpha(x, y, 1.8, (255, 255, 255), 0.95)
        line(x - L, y, x + L, y, 1.2, (255, 255, 255), 0.85)
        line(x, y - L, x, y + L, 1.2, (255, 255, 255), 0.85)
    # one faint shooting star, upper left
    x0, y0, x1, y1 = 205, 92, 118, 168
    for i in range(26):
        t = i / 25
        a = 0.75 * (1 - t)
        fill_circle_alpha(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t,
                          1.6, (255, 255, 255), a)
    fill_circle_alpha(x0, y0, 2.4, (255, 255, 255), 0.95)


def draw_sun():
    """The great vermilion sun: glow, disc, ukiyo-e bands, gold ring."""
    soft_disc(SUN_C[0], SUN_C[1], 265, SUN_GLOW, 0.30)
    fill_circle(SUN_C[0], SUN_C[1], SUN_R, SUN)
    # three darker horizontal bands across the disc, woodblock style
    for dy in (-52, 0, 52):
        cy = SUN_C[1] + dy
        for yy in range(int(cy) - 2, int(cy) + 3):
            dyy = (yy + 0.5) - SUN_C[1]
            d2 = SUN_R * SUN_R - dyy * dyy
            if d2 > 0:
                hw = math.sqrt(d2)
                hline(SUN_C[0] - hw, SUN_C[0] + hw, yy, SUN_DARK)
    ring(SUN_C[0], SUN_C[1], SUN_R + 12, 3.5, GOLD)


def draw_clouds():
    """A few soft, barely-there cloud bands."""
    soft_ellipse(210, 305, 250, 24, CLOUD, 0.5)
    soft_ellipse(830, 565, 300, 28, CLOUD, 0.45)
    soft_ellipse(520, 118, 190, 18, CLOUD, 0.4)


def mini_crane(cx, cy, s, color):
    """A tiny distant crane silhouette, facing right."""
    def P(pts):
        return [(cx + x * s, cy + y * s) for x, y in pts]

    fill_poly(P([(-2, -2), (-6, -34), (26, -4)]), color)          # near wing
    fill_poly(P([(-18, 2), (6, -4), (22, 2), (6, 8)]), color)     # body
    fill_poly(P([(18, 0), (30, -14), (26, 2)]), color)            # neck
    fill_poly(P([(30, -14), (40, -12), (31, -8)]), color)         # head
    fill_poly(P([(-18, 2), (-34, 10), (-16, 8)]), color)          # tail


def draw_crane():
    """The hero: a large white origami crane in flight, facing right.

    Built from flat facets like folded paper: a bright near wing split
    into three facets by gold fold lines, a darker far wing behind the
    body, a kite-shaped body, a long neck, a gold beak and a vermilion
    crown. A soft glow behind it lifts it off the night sky.
    """
    soft_disc(430, 400, 330, (143, 168, 255), 0.12)

    # far wing, in shade behind the body
    fill_poly([(470, 452), (650, 150), (585, 430)], PAPER_FAR)
    line(515, 435, 618, 215, 2.5, GOLD, 0.9)

    # tail feathers, long and sweeping back
    fill_poly([(345, 472), (185, 452), (340, 498)], PAPER_SHADOW)
    fill_poly([(345, 492), (205, 525), (350, 514)], PAPER_DEEP)

    # body: a flat kite, lit upper facet and shaded lower one
    fill_poly([(585, 462), (465, 428), (330, 480)], PAPER)
    fill_poly([(585, 462), (330, 480), (450, 520)], PAPER_SHADOW)

    # near wing: three facets fanning up from one fold point
    fold = (470, 330)
    fill_poly([(455, 432), (268, 150), fold], PAPER)
    fill_poly([(268, 150), fold, (620, 380)], PAPER_SHADOW)
    fill_poly([fold, (620, 380), (455, 432)], PAPER_DEEP)
    # gold fold lines
    line(455, 432, fold[0], fold[1], 2.5, GOLD, 0.95)
    line(268, 150, fold[0], fold[1], 2.5, GOLD, 0.95)
    line(620, 380, fold[0], fold[1], 2.5, GOLD, 0.95)

    # neck, head, beak, eye, crown -- drawn last so they sit in front
    # of the wing root and read clearly against the sky. The neck is
    # shaded a touch darker than the wing so it separates from it, with
    # a gold line along its leading edge.
    fill_poly([(558, 448), (598, 432), (662, 308), (642, 326)], PAPER_SHADOW)
    line(598, 432, 662, 308, 2.5, GOLD, 0.95)
    fill_poly([(662, 308), (690, 292), (672, 330)], PAPER)
    fill_poly([(686, 296), (716, 306), (682, 314)], GOLD)
    fill_circle(672, 308, 3.5, INK)
    fill_poly([(666, 300), (678, 288), (674, 312)], SUN)


def wave_crest(x, amp, freq, phase, base):
    return base + amp * math.sin(x * freq + phase)


def draw_waves():
    """Three layered stylised waves with white foam crests, Hokusai-like."""
    layers = [
        (WAVE_BACK, 830, 26, 0.012, 1.2),
        (WAVE_MID, 880, 30, 0.010, 2.6),
        (WAVE_FRONT, 935, 34, 0.008, 4.0),
    ]
    for color, base, amp, freq, phase in layers:
        pts = [(x, wave_crest(x, amp, freq, phase, base))
               for x in range(0, W + 1, 8)]
        pts += [(W, H), (0, H)]
        fill_poly(pts, color)
        # foam: a white line tracing the crest, plus scattered dots
        prev = None
        for x in range(0, W + 1, 16):
            p = (x, wave_crest(x, amp, freq, phase, base))
            if prev is not None:
                line(prev[0], prev[1], p[0], p[1], 3, FOAM, 0.9)
            prev = p
        for _ in range(34):
            x = rng.uniform(0, W)
            y = wave_crest(x, amp, freq, phase, base) + rng.uniform(2, 16)
            fill_circle_alpha(x, y, rng.uniform(1.5, 3.5), FOAM, 0.85)


def draw():
    draw_sky()
    draw_stars()
    draw_sun()
    draw_clouds()
    mini_crane(170, 235, 0.55, (247, 245, 238))
    mini_crane(920, 335, 0.42, (247, 245, 238))
    mini_crane(315, 128, 0.34, (235, 240, 250))
    draw_crane()
    draw_waves()


# ------------------------------------------------------------ PNG encode ---
def png_chunk(ctype, data):
    chunk = ctype + data
    return struct.pack(">I", len(data)) + chunk + struct.pack(
        ">I", binascii.crc32(chunk) & 0xFFFFFFFF)


def encode_png():
    """Encode the RGB canvas as a PNG (colour type 2, 8-bit).

    Each row gets the smallest of filters None/Sub/Up by the usual
    sum-of-absolute-values heuristic, then one zlib stream at level 9.
    Fully deterministic for a fixed canvas.
    """
    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    raw = bytearray()
    prev = bytes(W * 3)
    for y in range(H):
        row = bytes(canvas[y * W * 3:(y + 1) * W * 3])
        cands = []
        # filter 0: None
        cands.append((0, row))
        # filter 1: Sub (byte - byte 3 back)
        sub = bytearray(row)
        for i in range(3, len(sub)):
            sub[i] = (sub[i] - row[i - 3]) & 0xFF
        cands.append((1, bytes(sub)))
        # filter 2: Up (byte - byte above)
        up = bytearray(row)
        for i in range(len(up)):
            up[i] = (up[i] - prev[i]) & 0xFF
        cands.append((2, bytes(up)))

        def cost(b):
            return sum(v if v < 128 else 256 - v for v in b)

        ftype, fdata = min(cands, key=lambda c: cost(c[1]))
        raw.append(ftype)
        raw.extend(fdata)
        prev = row
    idat = zlib.compress(bytes(raw), 9)
    png = b"\x89PNG\r\n\x1a\n"
    png += png_chunk(b"IHDR", ihdr)
    png += png_chunk(b"IDAT", idat)
    png += png_chunk(b"IEND", b"")
    return png


def main():
    draw()
    png = encode_png()
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "entry.png")
    with open(path, "wb") as f:
        f.write(png)
    digest = hashlib.sha256(png).hexdigest()
    print(f"wrote {path} ({len(png)} bytes, {W}x{H}, sha256={digest})")
    if len(png) > 1048576:
        print("WARNING: over the 1 MiB limit", file=__import__("sys").stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
