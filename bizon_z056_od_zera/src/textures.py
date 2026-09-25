"""Procedural, tileable PBR textures and the decal atlas (numpy + Pillow).

Every map is generated from periodic spectral noise, so tiles repeat without
seams.  Specular maps follow the GIANTS layout: R = smoothness, G = metallic.
Usage: python textures.py <outdir>"""
import json
import math
import os
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

OUT = sys.argv[1] if len(sys.argv) > 1 else 'build/tex'
os.makedirs(OUT, exist_ok=True)


def pnoise(n, beta, seed, lo=1.0, hi=None):
    rng = np.random.default_rng(seed)
    spec = np.fft.fft2(rng.standard_normal((n, n)))
    f = np.fft.fftfreq(n) * n
    fr = np.sqrt(f[:, None] ** 2 + f[None, :] ** 2)
    fr[0, 0] = 1.0
    amp = fr ** (-beta)
    amp[fr < lo] = 0
    if hi:
        amp[fr > hi] = 0
    r = np.real(np.fft.ifft2(spec * amp))
    r -= r.mean()
    return r / (r.std() + 1e-9)


def blur_v(a, k):
    """Periodic box blur along image rows (vertical streaks)."""
    out = np.zeros_like(a)
    for i in range(-k, k + 1):
        out += np.roll(a, i, axis=0)
    return out / (2 * k + 1)


def blur(a, k):
    out = np.zeros_like(a)
    for i in range(-k, k + 1):
        out += np.roll(a, i, axis=0) + np.roll(a, i, axis=1)
    return out / (2 * (2 * k + 1))


def sstep(x, a, b):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def lines(n, count, lmin, lmax, width, seed, vertical_bias=0.0):
    rng = np.random.default_rng(seed)
    img = Image.new('L', (n, n), 0)
    d = ImageDraw.Draw(img)
    for _ in range(count):
        x, y = rng.uniform(0, n, 2)
        ang = rng.uniform(0, math.pi)
        if vertical_bias and rng.random() < vertical_bias:
            ang = math.pi / 2 + rng.normal(0, 0.15)
        ln = rng.uniform(lmin, lmax)
        dx, dy = math.cos(ang) * ln, math.sin(ang) * ln
        val = int(rng.uniform(90, 255))
        for ox in (-n, 0, n):
            for oy in (-n, 0, n):
                d.line((x + ox, y + oy, x + dx + ox, y + dy + oy), fill=val, width=width)
    return np.asarray(img, dtype=np.float32) / 255.0


def normal_from_height(h, strength):
    gx = (np.roll(h, -1, axis=1) - np.roll(h, 1, axis=1)) * 0.5 * strength
    gy = (np.roll(h, -1, axis=0) - np.roll(h, 1, axis=0)) * 0.5 * strength
    nz = np.ones_like(h)
    ln = np.sqrt(gx * gx + gy * gy + nz * nz)
    # OpenGL style (green = +V); image rows run downwards, so V gradient flips sign
    return np.stack([-gx / ln, gy / ln, nz / ln], -1)


def srgb(c):
    return np.array(c, dtype=np.float32) / 255.0


def save(name, arr, mode='RGB'):
    a = np.clip(arr, 0, 1)
    Image.fromarray((a * 255 + 0.5).astype(np.uint8), mode).save(os.path.join(OUT, name + '.png'))


def save_set(name, col, height, hstrength, smooth, metal):
    save(name + '_diffuse', col)
    save(name + '_normal', normal_from_height(height, hstrength) * 0.5 + 0.5)
    # GIANTS default shader gloss map: R = smoothness, G = specular (F0), B = metallic
    save(name + '_specular', np.stack([smooth, np.full_like(smooth, 0.5), metal], -1))


def mix(a, b, t):
    return a * (1 - t[..., None]) + b * t[..., None]


# ------------------------------------------------------------------ painted steel
def painted(name, n, base, seed, fade_col, dirt_col, gloss, dirt_amt=0.45, chips=1.0, scratches=900,
            rust_amt=0.6):
    low = pnoise(n, 2.4, seed, 1, 6)
    mid = pnoise(n, 1.8, seed + 1, 4, 48)
    fine = pnoise(n, 0.9, seed + 2, 48)
    streak = blur_v(pnoise(n, 1.4, seed + 3, 3, 120), n // 48)
    col = srgb(base)[None, None, :] * (1 + 0.05 * mid[..., None] + 0.025 * fine[..., None])
    fade = sstep(low, -0.2, 1.8) * 0.38
    col = mix(col, srgb(fade_col)[None, None, :] * (1 + 0.04 * mid[..., None]), fade)
    dirt = np.clip(sstep(streak * 0.7 + mid * 0.35, 0.35, 2.1) * dirt_amt + sstep(fine, 1.5, 3.5) * 0.12, 0, 1)
    col = mix(col, srgb(dirt_col)[None, None, :] * (1 + 0.1 * fine[..., None]), dirt)
    # paint chips: rust halo, primer ring, bare steel core
    cn = pnoise(n, 0.7, seed + 4, 30) + 0.35 * mid
    chip = sstep(cn, 2.75 - 0.25 * chips, 3.05 - 0.25 * chips)
    core = sstep(cn, 3.1, 3.4)
    halo = np.clip(sstep(cn, 2.35, 2.75) - chip, 0, 1) * rust_amt
    col = mix(col, srgb((96, 52, 30))[None, None, :] * (1 + 0.2 * fine[..., None]), halo * 0.8)
    col = mix(col, srgb((72, 70, 64))[None, None, :], chip)
    col = mix(col, srgb((128, 126, 120))[None, None, :] * (1 + 0.15 * fine[..., None]), core)
    sc = lines(n, scratches, n * 0.006, n * 0.04, 1, seed + 5) * sstep(mid, -1.0, 1.0)
    col = mix(col, np.clip(col * 1.25 + 0.05, 0, 1), sc * 0.55)
    smooth = np.clip(gloss * (1 - 0.65 * dirt) - 0.25 * chip + 0.05 * fine - 0.2 * halo + 0.1 * core, 0.05, 0.95)
    metal = np.clip(core * 0.9 + sc * 0.2, 0, 1)
    height = 0.25 * pnoise(n, 1.1, seed + 6, 90) - 1.2 * chip - 0.5 * sc + 0.2 * dirt
    save_set(name, col, height, 1.6, smooth, metal)


def metal_worn(name, n, seed):
    mid = pnoise(n, 1.6, seed, 3, 60)
    fine = pnoise(n, 0.8, seed + 1, 60)
    brushed = blur(pnoise(n, 0.5, seed + 2, 100), 1)
    brushed = np.roll(np.stack([np.roll(brushed[i], i % 7) for i in range(n)]), 0)
    base = srgb((132, 130, 124))[None, None, :] * (1 + 0.06 * mid[..., None] + 0.04 * brushed[..., None])
    rust = sstep(pnoise(n, 1.3, seed + 3, 4, 90) + 0.4 * fine, 1.2, 2.4)
    oil = sstep(mid, 0.6, 2.0) * 0.6
    col = mix(base, srgb((105, 58, 32))[None, None, :] * (1 + 0.25 * fine[..., None]), rust)
    col = mix(col, srgb((38, 34, 30))[None, None, :], oil * 0.7)
    smooth = np.clip(0.62 - 0.45 * rust - 0.1 * oil + 0.05 * brushed, 0.05, 0.9)
    metal = np.clip(0.95 - 0.85 * rust - 0.3 * oil, 0, 1)
    height = 0.3 * fine - 0.8 * rust * (0.5 + 0.5 * fine) + 0.1 * brushed
    save_set(name, col, height, 1.2, smooth, metal)


def galvanized(name, n, seed):
    rng = np.random.default_rng(seed)
    pts = rng.uniform(0, n, (220, 2))
    yy, xx = np.mgrid[0:n, 0:n]
    best = np.full((n, n), 1e9)
    lab = np.zeros((n, n))
    vals = rng.uniform(-1, 1, len(pts))
    for (px, py), v in zip(pts, vals):
        dx = np.minimum(abs(xx - px), n - abs(xx - px))
        dy = np.minimum(abs(yy - py), n - abs(yy - py))
        d = dx * dx + dy * dy
        m = d < best
        best[m] = d[m]
        lab[m] = v
    fine = pnoise(n, 1.0, seed + 1, 30)
    col = srgb((168, 170, 168))[None, None, :] * (1 + 0.08 * lab[..., None] + 0.03 * fine[..., None])
    white = sstep(pnoise(n, 1.5, seed + 2, 3, 40), 1.0, 2.5)
    col = mix(col, srgb((200, 198, 190))[None, None, :], white * 0.5)
    smooth = np.clip(0.55 + 0.12 * lab - 0.3 * white, 0.1, 0.9)
    save(name + '_diffuse', col)
    save(name + '_specular', np.stack([smooth, np.full_like(smooth, 0.5), np.clip(0.9 - 0.6 * white, 0, 1)], -1))
    save(name + '_normal', normal_from_height(0.3 * lab + 0.2 * fine, 0.8) * 0.5 + 0.5)


def rubber(name, n, seed, base=(24, 24, 23), dust=(92, 84, 72), dust_amt=0.35):
    mid = pnoise(n, 1.7, seed, 3, 50)
    fine = pnoise(n, 0.9, seed + 1, 50)
    col = srgb(base)[None, None, :] * (1 + 0.08 * fine[..., None])
    d = np.clip(sstep(mid + 0.4 * fine, 0.3, 2.2) * dust_amt, 0, 1)
    col = mix(col, srgb(dust)[None, None, :], d)
    smooth = np.clip(0.22 - 0.15 * d + 0.03 * fine, 0.02, 0.5)
    save_set(name, col, 0.4 * fine + 0.3 * d, 1.0, smooth, np.zeros_like(smooth))


def heat_rust(name, n, seed):
    low = pnoise(n, 2.0, seed, 1, 10)
    mid = pnoise(n, 1.5, seed + 1, 8, 80)
    fine = pnoise(n, 0.8, seed + 2, 80)
    col = mix(srgb((118, 62, 34))[None, None, :] * np.ones((n, n, 1)), srgb((58, 36, 26))[None, None, :] * np.ones((n, n, 1)), sstep(low, -0.5, 1.2))
    col = mix(col, srgb((150, 88, 48))[None, None, :], sstep(mid, 0.8, 2.2) * 0.6)
    col = mix(col, srgb((20, 18, 17))[None, None, :], sstep(blur_v(mid, 20) + 0.5 * low, 0.8, 2.0) * 0.7)
    col *= (1 + 0.12 * fine[..., None])
    smooth = np.clip(0.18 + 0.05 * fine, 0.05, 0.4)
    save_set(name, col, 0.6 * mid + 0.5 * fine, 2.0, smooth, np.clip(0.2 - 0.1 * mid, 0, 1))


def tread_plate(name, n, seed):
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    cell = n / 40.0
    h = np.zeros((n, n), np.float32)
    for ang, off in ((math.radians(35), 0.0), (math.radians(-35), 0.5)):
        u = (xx * math.cos(ang) + yy * math.sin(ang)) / cell
        v = (-xx * math.sin(ang) + yy * math.cos(ang)) / cell
        cu = u - np.round(u)
        cv = (v + off) - np.round(v + off)
        # alternate cells get the other orientation
        sel = ((np.floor(xx / cell) + np.floor(yy / cell)) % 2 == (0 if off == 0 else 1))
        bump = np.clip(1 - (cu / 0.42) ** 2 - (cv / 0.13) ** 2, 0, 1)
        h = np.where(sel, np.maximum(h, bump), h)
    fine = pnoise(n, 0.9, seed, 40)
    mid = pnoise(n, 1.6, seed + 1, 3, 40)
    base = srgb((96, 96, 92))[None, None, :] * (1 + 0.06 * fine[..., None])
    dirt = np.clip((1 - h) * sstep(mid, -0.6, 1.4) * 0.8, 0, 1)
    col = mix(base, srgb((70, 60, 48))[None, None, :], dirt)
    col = mix(col, srgb((150, 150, 146))[None, None, :], h * 0.35)
    smooth = np.clip(0.35 + 0.3 * h - 0.2 * dirt, 0.05, 0.9)
    save_set(name, col, 3.0 * h + 0.2 * fine, 2.5, smooth, np.clip(0.7 * (1 - dirt), 0, 1))


def vinyl(name, n, seed):
    fine = pnoise(n, 0.7, seed, 60)
    cr = lines(n, 260, n * 0.01, n * 0.05, 1, seed + 1)
    col = srgb((34, 30, 27))[None, None, :] * (1 + 0.1 * fine[..., None])
    col = mix(col, srgb((70, 64, 58))[None, None, :], cr * 0.5)
    smooth = np.clip(0.45 + 0.05 * fine - 0.2 * cr, 0.05, 0.8)
    save_set(name, col, 0.3 * fine - cr, 1.5, smooth, np.zeros_like(smooth))


def plastic(name, n, seed, base, gloss=0.5):
    fine = pnoise(n, 0.8, seed, 50)
    mid = pnoise(n, 1.6, seed + 1, 3, 40)
    sc = lines(n, 300, n * 0.005, n * 0.03, 1, seed + 2)
    col = srgb(base)[None, None, :] * (1 + 0.03 * fine[..., None] + 0.05 * mid[..., None])
    col = mix(col, np.clip(col * 1.3, 0, 1), sc * 0.4)
    smooth = np.clip(gloss - 0.2 * sc + 0.03 * fine - 0.1 * sstep(mid, 0.8, 2), 0.05, 0.9)
    save_set(name, col, 0.15 * fine - 0.5 * sc, 1.0, smooth, np.zeros_like(smooth))


def soil(name, n, seed):
    """Render-only field ground."""
    low = pnoise(n, 2.2, seed, 1, 8)
    mid = pnoise(n, 1.4, seed + 1, 8, 120)
    fine = pnoise(n, 0.8, seed + 2, 120)
    col = mix(srgb((92, 74, 54))[None, None, :] * np.ones((n, n, 1)), srgb((150, 128, 88))[None, None, :] * np.ones((n, n, 1)), sstep(low + 0.4 * mid, -0.8, 1.6))
    col *= 1 + 0.18 * fine[..., None]
    straw = lines(n, 5000, n * 0.004, n * 0.03, 1, seed + 3)
    col = mix(col, srgb((196, 170, 110))[None, None, :], straw * 0.8)
    save_set(name, col, 0.8 * mid + 0.6 * fine + 1.2 * straw, 3.0, np.clip(0.15 + 0.1 * straw, 0, 1), np.zeros((n, n)))


# ------------------------------------------------------------------ decal atlas
FONT_DIRS = ['/usr/share/fonts/truetype/dejavu', '/usr/share/fonts/truetype/freefont']
FONT_ALIASES = {
    'DejaVuSans-BoldOblique.ttf': ['FreeSansBoldOblique.ttf'],
    'DejaVuSansCondensed-Bold.ttf': ['FreeSansBold.ttf'],
    'DejaVuSerif-BoldItalic.ttf': ['FreeSerifBoldItalic.ttf'],
    'DejaVuSerif-Bold.ttf': ['DejaVuSerif-Bold.ttf', 'FreeSerifBold.ttf'],
}


def font(name, size):
    for cand in [name] + FONT_ALIASES.get(name, []):
        for d in FONT_DIRS:
            p = os.path.join(d, cand)
            if os.path.exists(p):
                return ImageFont.truetype(p, size)
    return ImageFont.truetype(os.path.join(FONT_DIRS[0], 'DejaVuSans-Bold.ttf'), size)


def atlas(n=2048):
    img = Image.new('RGBA', (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    regions = {}

    def reg(key, x0, y0, x1, y1):
        regions[key] = (x0 / n, 1 - y1 / n, x1 / n, 1 - y0 / n)

    def centered(box, text, f, fill, dy=0):
        x0, y0, x1, y1 = box
        l, t, r, b = d.textbbox((0, 0), text, font=f)
        d.text(((x0 + x1 - (r - l)) / 2 - l, (y0 + y1 - (b - t)) / 2 - t + dy), text, font=f, fill=fill)

    red = (178, 22, 20, 255)
    white = (238, 236, 228, 255)
    # 1. BIZON logo sticker (white plate, red lettering, bison silhouette)
    x0, y0, x1, y1 = 0, 0, 1024, 300
    d.rounded_rectangle((x0 + 4, y0 + 4, x1 - 4, y1 - 4), 28, fill=white, outline=red, width=10)
    fb = font('DejaVuSans-BoldOblique.ttf', 190)
    centered((x0 + 300, y0, x1 - 20, y1), 'BIZON', fb, red, dy=4)
    bison = [(40, 230), (60, 150), (95, 110), (150, 88), (205, 95), (235, 70), (262, 78), (275, 110), (262, 140),
             (270, 175), (250, 205), (228, 205), (222, 236), (196, 236), (192, 200), (130, 205), (118, 238),
             (92, 238), (90, 200), (70, 212), (62, 238)]
    d.polygon([(x + x0 + 10, y + y0 - 10) for x, y in bison], fill=red)
    d.polygon([(248, 80), (240, 52), (256, 70)], fill=red)
    reg('bizon', x0, y0, x1, y1)
    # 2. SUPER Z056 lettering (white, transparent background)
    x0, y0, x1, y1 = 0, 310, 1024, 480
    centered((x0, y0, x1, y1), 'SUPER  Z056', font('DejaVuSansCondensed-Bold.ttf', 150), white)
    reg('super', x0, y0, x1, y1)
    # 3. nameplate (aluminium, engraved)
    x0, y0, x1, y1 = 1040, 0, 1552, 300
    rng = np.random.default_rng(3)
    plate = (rng.normal(0, 6, (y1 - y0, x1 - x0)) + 178).clip(0, 255).astype(np.uint8)
    img.paste(Image.fromarray(np.stack([plate, plate, plate - 4, np.full_like(plate, 255)], -1), 'RGBA'), (x0, y0))
    ink = (40, 40, 42, 255)
    for (cx, cy) in ((x0 + 18, y0 + 18), (x1 - 18, y0 + 18), (x0 + 18, y1 - 18), (x1 - 18, y1 - 18)):
        d.ellipse((cx - 9, cy - 9, cx + 9, cy + 9), fill=(120, 118, 112, 255), outline=ink)
    d.text((x0 + 40, y0 + 22), 'FMŻ', font=font('DejaVuSans-BoldOblique.ttf', 58), fill=ink)
    small = font('DejaVuSansCondensed-Bold.ttf', 24)
    rows = ['FABRYKA MASZYN ŻNIWNYCH', 'w PŁOCKU', 'Symbol wyrobu   Z056 SUPER', 'Nr maszyny        5264',
            'Rok budowy        1986', 'Ciężar netto     7300 kg', 'Made in Poland']
    for i, t in enumerate(rows):
        d.text((x0 + 175 if i < 2 else x0 + 40, y0 + 30 + i * 36 if i < 2 else y0 + 100 + (i - 2) * 36), t, font=small, fill=ink)
    reg('plate', x0, y0, x1, y1)
    # 4. crate print (white on transparent)
    x0, y0, x1, y1 = 1040, 310, 1552, 440
    centered((x0, y0, x1, y1 - 30), 'TYSKIE', font('DejaVuSerif-Bold.ttf', 92), white)
    centered((x0, y1 - 40, x1, y1), 'BROWARY TYSKIE  ·  ZWROTNA', font('DejaVuSansCondensed-Bold.ttf', 22), white)
    reg('crate', x0, y0, x1, y1)
    # 5. bottle front label (cream/gold shield with red lettering)
    x0, y0, x1, y1 = 0, 500, 640, 900
    gold = (206, 164, 74, 255)
    cream = (240, 228, 196, 255)
    d.rounded_rectangle((x0 + 6, y0 + 6, x1 - 6, y1 - 6), 60, fill=cream, outline=gold, width=16)
    d.rounded_rectangle((x0 + 40, y0 + 40, x1 - 40, y1 - 40), 40, outline=(150, 20, 24, 255), width=5)
    d.polygon([(x0 + 270, y0 + 70), (x0 + 290, y0 + 110), (x0 + 320, y0 + 80), (x0 + 350, y0 + 110), (x0 + 370, y0 + 70),
               (x0 + 360, y0 + 130), (x0 + 280, y0 + 130)], fill=gold)
    centered((x0, y0 + 120, x1, y0 + 270), 'Tyskie', font('DejaVuSerif-BoldItalic.ttf', 128), (160, 18, 22, 255))
    centered((x0, y0 + 262, x1, y0 + 330), 'GRONIE', font('DejaVuSerif-Bold.ttf', 58), (40, 30, 26, 255))
    centered((x0, y0 + 328, x1, y0 + 372), 'PIWO JASNE PEŁNE  ·  0,5 l', font('DejaVuSansCondensed-Bold.ttf', 24), (60, 40, 30, 255))
    reg('label', x0, y0, x1, y1)
    # 6. neck label
    x0, y0, x1, y1 = 660, 500, 1300, 580
    d.rectangle((x0, y0, x1, y1), fill=(160, 18, 22, 255))
    d.rectangle((x0, y0 + 8, x1, y0 + 14), fill=gold)
    d.rectangle((x0, y1 - 14, x1, y1 - 8), fill=gold)
    centered((x0, y0, x1, y1), 'TYSKIE  ·  TYSKIE  ·  TYSKIE', font('DejaVuSerif-Bold.ttf', 34), cream)
    reg('neck', x0, y0, x1, y1)
    # 7. gauges
    for gi, (key, top, sub) in enumerate((('gauge_rpm', 25, 'x100 obr/min'), ('gauge_speed', 25, 'km/h'))):
        x0, y0 = 1320 + gi * 300, 500
        x1, y1 = x0 + 280, y0 + 280
        cx, cy, R = (x0 + x1) / 2, (y0 + y1) / 2, 132
        d.ellipse((cx - R, cy - R, cx + R, cy + R), fill=(18, 18, 18, 255), outline=(150, 150, 150, 255), width=6)
        for k in range(0, top + 1):
            a = math.radians(225 - 270 * k / top)
            r0 = R - (26 if k % 5 == 0 else 14)
            d.line((cx + r0 * math.cos(a), cy - r0 * math.sin(a), cx + (R - 8) * math.cos(a), cy - (R - 8) * math.sin(a)),
                   fill=(235, 235, 230, 255), width=5 if k % 5 == 0 else 2)
            if k % 5 == 0:
                t = str(k)
                f = font('DejaVuSansCondensed-Bold.ttf', 26)
                l, tt, r, b = d.textbbox((0, 0), t, font=f)
                rr = R - 50
                d.text((cx + rr * math.cos(a) - (r - l) / 2, cy - rr * math.sin(a) - (b - tt) / 2 - tt), t, font=f, fill=(235, 235, 230, 255))
        centered((x0, cy + 30, x1, cy + 70), sub, font('DejaVuSansCondensed-Bold.ttf', 18), (220, 220, 210, 255))
        reg(key, x0, y0, x1, y1)
    # 8. slow moving vehicle triangle
    x0, y0, x1, y1 = 0, 920, 300, 1180
    d.polygon([(x0 + 150, y0 + 5), (x1 - 5, y1 - 5), (x0 + 5, y1 - 5)], fill=(200, 20, 18, 255))
    d.polygon([(x0 + 150, y0 + 60), (x1 - 52, y1 - 32), (x0 + 52, y1 - 32)], fill=(255, 110, 20, 255))
    reg('triangle', x0, y0, x1, y1)
    # 9. warning sticker
    x0, y0, x1, y1 = 320, 920, 900, 1100
    d.rectangle((x0, y0, x1, y1), fill=(250, 208, 30, 255), outline=(20, 20, 20, 255), width=8)
    d.polygon([(x0 + 90, y0 + 22), (x0 + 160, y1 - 22), (x0 + 20, y1 - 22)], outline=(20, 20, 20, 255), width=8)
    centered((x0 + 60, y1 - 150, x0 + 120, y1 - 40), '!', font('DejaVuSans-Bold.ttf', 80), (20, 20, 20, 255))
    d.text((x0 + 190, y0 + 22), 'UWAGA!', font=font('DejaVuSans-Bold.ttf', 56), fill=(20, 20, 20, 255))
    d.text((x0 + 190, y0 + 92), 'Nie zbliżać się do pracujących', font=font('DejaVuSansCondensed-Bold.ttf', 26), fill=(20, 20, 20, 255))
    d.text((x0 + 190, y0 + 124), 'zespołów maszyny', font=font('DejaVuSansCondensed-Bold.ttf', 26), fill=(20, 20, 20, 255))
    reg('warning', x0, y0, x1, y1)
    # 10. licence plate (Polish agricultural style)
    x0, y0, x1, y1 = 920, 920, 1440, 1040
    d.rounded_rectangle((x0, y0, x1, y1), 12, fill=(240, 240, 236, 255), outline=(20, 20, 20, 255), width=6)
    d.rectangle((x0 + 6, y0 + 6, x0 + 70, y1 - 6), fill=(20, 60, 170, 255))
    centered((x0 + 6, y1 - 50, x0 + 70, y1 - 8), 'PL', font('DejaVuSans-Bold.ttf', 30), (255, 255, 255, 255))
    centered((x0 + 74, y0, x1 - 6, y1), 'CPL 56Z6', font('DejaVuSansCondensed-Bold.ttf', 80), (20, 20, 20, 255))
    reg('plate_rear', x0, y0, x1, y1)
    # 11. red/white hazard stripes
    x0, y0, x1, y1 = 1460, 920, 1720, 1180
    st = Image.new('RGBA', (x1 - x0, y1 - y0), (245, 245, 240, 255))
    sd = ImageDraw.Draw(st)
    for k in range(-8, 8):
        a = k * 45
        sd.polygon([(a, 260), (a + 25, 260), (a + 285, 0), (a + 260, 0)], fill=(205, 20, 20, 255))
    img.paste(st, (x0, y0))
    reg('stripes', x0, y0, x1, y1)
    # 12. big Tyskie sticker (oval)
    x0, y0, x1, y1 = 0, 1200, 700, 1520
    d.ellipse((x0 + 5, y0 + 5, x1 - 5, y1 - 5), fill=(160, 18, 22, 255), outline=gold, width=14)
    d.ellipse((x0 + 40, y0 + 40, x1 - 40, y1 - 40), outline=cream, width=4)
    centered((x0, y0 + 60, x1, y0 + 230), 'Tyskie', font('DejaVuSerif-BoldItalic.ttf', 150), cream)
    centered((x0, y0 + 215, x1, y0 + 275), 'GRONIE  ·  OD 1629', font('DejaVuSerif-Bold.ttf', 40), gold)
    reg('tyskie_big', x0, y0, x1, y1)
    # 13. dark vent / grille backing
    x0, y0, x1, y1 = 720, 1200, 980, 1460
    d.rectangle((x0, y0, x1, y1), fill=(12, 12, 12, 255))
    reg('black', x0, y0, x1, y1)
    # 14. seat patch white strip for text-free areas
    x0, y0, x1, y1 = 1000, 1200, 1100, 1300
    d.rectangle((x0, y0, x1, y1), fill=(235, 235, 230, 255))
    reg('white', x0, y0, x1, y1)
    # 15. reflector (red) and amber pattern
    for k, (key, colr) in enumerate((('refl_red', (190, 16, 12)), ('refl_amber', (255, 128, 10)))):
        x0, y0 = 1120 + k * 220, 1200
        x1, y1 = x0 + 200, y0 + 200
        d.rectangle((x0, y0, x1, y1), fill=colr + (255,))
        for i in range(0, 200, 20):
            for j in range(0, 200, 20):
                d.polygon([(x0 + i + 10, y0 + j), (x0 + i + 20, y0 + j + 10), (x0 + i + 10, y0 + j + 20), (x0 + i, y0 + j + 10)],
                          fill=tuple(min(255, int(c * 1.35)) for c in colr) + (255,))
        reg(key, x0, y0, x1, y1)
    img.save(os.path.join(OUT, 'decals_diffuse.png'))
    with open(os.path.join(OUT, 'atlas.json'), 'w') as f:
        json.dump(regions, f, indent=1)


if __name__ == '__main__':
    painted('paint_red', 2048, (138, 19, 14), 11, fade_col=(158, 48, 36), dirt_col=(112, 92, 72), gloss=0.58,
            dirt_amt=0.5)
    painted('paint_white', 1024, (214, 210, 196), 21, fade_col=(226, 222, 206), dirt_col=(140, 126, 104), gloss=0.55,
            dirt_amt=0.5)
    painted('paint_black', 1024, (30, 30, 29), 31, fade_col=(52, 50, 47), dirt_col=(84, 72, 58), gloss=0.42,
            dirt_amt=0.55, chips=0.6, scratches=600)
    painted('paint_orange', 1024, (214, 92, 18), 41, fade_col=(224, 124, 60), dirt_col=(120, 96, 70), gloss=0.5,
            dirt_amt=0.4, chips=0.5, scratches=400)
    metal_worn('metal_worn', 1024, 51)
    galvanized('galvanized', 512, 61)
    rubber('rubber', 1024, 71)
    heat_rust('heat_rust', 1024, 81)
    tread_plate('tread_plate', 1024, 91)
    vinyl('seat_vinyl', 512, 101)
    plastic('crate_red', 512, 111, (156, 18, 20), gloss=0.55)
    plastic('plastic_black', 512, 121, (20, 20, 20), gloss=0.45)
    soil('render_soil', 2048, 131)
    atlas()
    print('textures ->', OUT)
