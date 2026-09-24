"""Generates the decal atlas + misc textures (PNG for Blender, DDS for the mod)."""
import json
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = sys.argv[1] if len(sys.argv) > 1 else "build/textures"
os.makedirs(OUT, exist_ok=True)

F = "/usr/share/fonts/truetype"
SANS_B = F + "/dejavu/DejaVuSans-Bold.ttf"
SERIF_B = F + "/dejavu/DejaVuSerif-Bold.ttf"
SANS_BO = F + "/freefont/FreeSansBoldOblique.ttf"
for p in (SANS_B, SERIF_B, SANS_BO):
    if not os.path.exists(p):
        raise SystemExit("missing font " + p)

W, H = 2048, 2048
atlas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
d = ImageDraw.Draw(atlas)
regions = {}


def region(name, box):
    x0, y0, x1, y1 = box
    # UV rect in Blender convention (v up from the bottom of the image)
    regions[name] = [x0 / W, 1 - y1 / H, x1 / W, 1 - y0 / H]


def text_center(box, txt, font, fill, stroke=0, stroke_fill=None, skew=0.0):
    x0, y0, x1, y1 = box
    layer = Image.new("RGBA", (x1 - x0, y1 - y0), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    bb = ld.textbbox((0, 0), txt, font=font, stroke_width=stroke)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    ld.text(((x1 - x0 - tw) / 2 - bb[0], (y1 - y0 - th) / 2 - bb[1]), txt, font=font, fill=fill,
            stroke_width=stroke, stroke_fill=stroke_fill)
    if skew:
        layer = layer.transform(layer.size, Image.AFFINE, (1, skew, -skew * layer.size[1] / 2, 0, 1, 0),
                                resample=Image.BICUBIC)
    atlas.alpha_composite(layer, (x0, y0))


def fit_font(path, txt, box, pad=0.9):
    w, h = box[2] - box[0], box[3] - box[1]
    size = int(h * pad)
    while size > 8:
        f = ImageFont.truetype(path, size)
        bb = f.getbbox(txt)
        if bb[2] - bb[0] <= w * pad and bb[3] - bb[1] <= h * pad:
            return f
        size -= 2
    return ImageFont.truetype(path, size)


# --- BIZON lettering (white with thin dark edge, classic factory look)
b = (0, 0, 1024, 256)
text_center(b, "BIZON", fit_font(SANS_BO, "BIZON", b, 0.86), (246, 244, 236, 255), 5, (40, 20, 18, 255))
region("bizon", b)
b = (1024, 0, 2048, 256)
text_center(b, "Super Z056", fit_font(SANS_BO, "Super Z056", b, 0.8), (246, 244, 236, 255), 4,
            (40, 20, 18, 255))
region("super", b)

# --- beer label: red oval, gold serif lettering (own lettering, not the brand artwork)
b = (0, 256, 1024, 704)
lab = Image.new("RGBA", (1024, 448), (0, 0, 0, 0))
ldr = ImageDraw.Draw(lab)
ldr.rounded_rectangle((6, 6, 1018, 442), 210, fill=(212, 175, 92, 255))
ldr.rounded_rectangle((22, 22, 1002, 426), 196, fill=(156, 18, 28, 255))
ldr.rounded_rectangle((40, 40, 984, 408), 180, outline=(226, 190, 104, 255), width=6)
atlas.alpha_composite(lab, (0, 256))
text_center((60, 300, 964, 600), "Tyskie", fit_font(SERIF_B, "Tyskie", (60, 300, 964, 600), 0.92),
            (236, 200, 112, 255), 3, (90, 10, 14, 255))
text_center((200, 590, 824, 670), "GRONIE", fit_font(SANS_B, "GRONIE", (200, 590, 824, 670), 0.8),
            (246, 236, 214, 255))
region("tyskie", b)


def crown(dr, cx, cy, w, col, outline=None):
    """Simple five-point royal crown."""
    h = w * 0.55
    pts = [(cx - w / 2, cy + h / 2), (cx - w / 2, cy - h * 0.1), (cx - w * 0.32, cy + h * 0.12),
           (cx - w * 0.2, cy - h * 0.45), (cx - w * 0.08, cy + h * 0.05), (cx, cy - h * 0.55),
           (cx + w * 0.08, cy + h * 0.05), (cx + w * 0.2, cy - h * 0.45), (cx + w * 0.32, cy + h * 0.12),
           (cx + w / 2, cy - h * 0.1), (cx + w / 2, cy + h / 2)]
    dr.polygon(pts, fill=col, outline=outline)
    for px, py in (pts[3], pts[5], pts[7], pts[1], pts[9]):
        r = w * 0.045
        dr.ellipse((px - r, py - r, px + r, py + r), fill=col, outline=outline)
    dr.rectangle((cx - w / 2, cy + h * 0.38, cx + w / 2, cy + h / 2), fill=outline or col)


GOLD = (214, 176, 92, 255)
GOLD_D = (150, 112, 44, 255)
RED = (158, 16, 28, 255)
CREAM = (244, 234, 206, 255)
SERIF_BI = F + "/dejavu/DejaVuSerif-BoldItalic.ttf"
if not os.path.exists(SERIF_BI):
    SERIF_BI = SERIF_B

# --- crate logo (moulded-in look, transparent background)
b = (1024, 256, 2048, 512)
lay = Image.new("RGBA", (1024, 256), (0, 0, 0, 0))
ld = ImageDraw.Draw(lay)
crown(ld, 120, 128, 150, (236, 226, 200, 255))
f = fit_font(SERIF_BI, "Tyskie", (0, 0, 760, 230), 0.9)
ld.text((230, 128), "Tyskie", font=f, fill=(240, 232, 214, 255), anchor="lm")
atlas.alpha_composite(lay, (b[0], b[1]))
region("crate", b)

# --- warning stripes
b = (1024, 512, 2048, 640)
stripe = Image.new("RGBA", (1024, 128), (240, 196, 20, 255))
sd = ImageDraw.Draw(stripe)
for x in range(-128, 1024 + 128, 96):
    sd.polygon([(x, 128), (x + 48, 128), (x + 176, 0), (x + 128, 0)], fill=(18, 18, 18, 255))
atlas.alpha_composite(stripe, (1024, 512))
region("stripes", b)

# --- maker plate
b = (1024, 640, 1536, 896)
d.rounded_rectangle(b, 18, fill=(196, 198, 196, 255), outline=(60, 60, 60, 255), width=6)
text_center((1044, 660, 1516, 760), "ZMŻ PŁOCK", fit_font(SANS_B, "ZMŻ PŁOCK", (1044, 660, 1516, 760), 0.8),
            (30, 30, 30, 255))
text_center((1044, 760, 1516, 820), "KOMBAJN ZBOŻOWY Z056",
            fit_font(SANS_B, "KOMBAJN ZBOŻOWY Z056", (1044, 760, 1516, 820), 0.8), (30, 30, 30, 255))
text_center((1044, 820, 1516, 876), "Nr fabr. 056-1987-0415",
            fit_font(SANS_B, "Nr fabr. 056-1987-0415", (1044, 820, 1516, 876), 0.8), (40, 40, 40, 255))
region("plate", b)

# --- polish flag
b = (1536, 640, 2048, 896)
d.rectangle((1536, 640, 2048, 768), fill=(245, 245, 245, 255))
d.rectangle((1536, 768, 2048, 896), fill=(212, 20, 60, 255))
region("flag", b)


# --- gauges (tachometer + speed)
def gauge(box, maxv, step, label):
    x0, y0, x1, y1 = box
    cx, cy, r = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2 - 8
    d.ellipse((x0 + 4, y0 + 4, x1 - 4, y1 - 4), fill=(18, 18, 18, 255), outline=(170, 170, 170, 255), width=8)
    f = ImageFont.truetype(SANS_B, int(r * 0.17))
    n = int(maxv / step)
    for i in range(n + 1):
        a = math.radians(225 - 270 * i / n)
        p0 = (cx + math.cos(a) * r * 0.78, cy - math.sin(a) * r * 0.78)
        p1 = (cx + math.cos(a) * r * 0.93, cy - math.sin(a) * r * 0.93)
        d.line([p0, p1], fill=(240, 240, 230, 255), width=6)
        t = str(int(i * step / (100 if maxv > 500 else 1)))
        tp = (cx + math.cos(a) * r * 0.6, cy - math.sin(a) * r * 0.6)
        bb = d.textbbox((0, 0), t, font=f)
        d.text((tp[0] - (bb[2] - bb[0]) / 2, tp[1] - (bb[3] - bb[1]) / 2 - bb[1]), t, font=f,
               fill=(240, 240, 230, 255))
    f2 = ImageFont.truetype(SANS_B, int(r * 0.12))
    bb = d.textbbox((0, 0), label, font=f2)
    d.text((cx - (bb[2] - bb[0]) / 2, cy + r * 0.12), label, font=f2, fill=(230, 120, 30, 255))


gauge((0, 1024, 512, 1536), 2500, 500, "obr/min x100")
region("gauge_rpm", (0, 1024, 512, 1536))
gauge((512, 1024, 1024, 1536), 30, 5, "km/h")
region("gauge_speed", (512, 1024, 1024, 1536))

# --- small stickers: "Nie stawać na podeście" warning, lube points
b = (1024, 896, 1536, 1024)
d.rectangle(b, fill=(240, 196, 20, 255))
text_center((1034, 900, 1526, 1020), "UWAGA! CZĘŚCI RUCHOME",
            fit_font(SANS_B, "UWAGA! CZĘŚCI RUCHOME", (1034, 900, 1526, 1020), 0.84), (20, 20, 20, 255))
region("warning", b)
b = (1536, 896, 2048, 1024)
d.rectangle(b, fill=(24, 24, 24, 255))
text_center((1546, 900, 2038, 1020), "SW-400  105 KM",
            fit_font(SANS_B, "SW-400  105 KM", (1546, 900, 2038, 1020), 0.8), (230, 230, 220, 255))
region("engine", b)

# --- bottle front label: gold paper, red shield, crown, script-like name, ribbon
b = (1024, 1280, 1536, 1792)
lab = Image.new("RGBA", (512, 512), CREAM)
ldr = ImageDraw.Draw(lab)
for y in range(512):  # warm paper gradient
    c = int(8 * math.sin(y / 512 * math.pi))
    ldr.line([(0, y), (512, y)], fill=(236 + c // 2, 222 + c // 2, 186, 255))
ldr.rectangle((0, 0, 511, 511), outline=GOLD_D, width=10)
ldr.rectangle((14, 14, 497, 497), outline=GOLD, width=5)
ldr.polygon([(86, 150), (426, 150), (426, 330), (256, 420), (86, 330)], fill=RED, outline=GOLD, width=8)
crown(ldr, 256, 92, 150, GOLD, GOLD_D)
f = fit_font(SERIF_BI, "Tyskie", (0, 0, 380, 140), 0.95)
ldr.text((256, 245), "Tyskie", font=f, fill=GOLD, anchor="mm", stroke_width=3, stroke_fill=(90, 10, 14, 255))
ldr.polygon([(40, 400), (472, 400), (452, 440), (472, 480), (40, 480), (60, 440)], fill=GOLD, outline=GOLD_D)
f = fit_font(SANS_B, "GRONIE", (0, 0, 300, 60), 0.9)
ldr.text((256, 440), "GRONIE", font=f, fill=RED, anchor="mm")
f = fit_font(SANS_B, "PIWO JASNE PEŁNE", (0, 0, 300, 30), 0.9)
ldr.text((256, 360), "PIWO JASNE PEŁNE", font=f, fill=CREAM, anchor="mm")
atlas.paste(lab, (b[0], b[1]))
region("bottle", b)

# --- bottle back label: small print
b = (1536, 1280, 2048, 1706)
lab = Image.new("RGBA", (512, 426), CREAM)
ldr = ImageDraw.Draw(lab)
ldr.rectangle((0, 0, 511, 425), outline=GOLD, width=8)
f1 = ImageFont.truetype(SANS_B, 30)
f2 = ImageFont.truetype(SANS_B, 22)
lines = [("Tyskie Gronie", f1), ("Piwo jasne pełne", f2), ("alk. 5,2% obj.", f2), ("0,5 l", f1),
         ("Butelka zwrotna", f2), ("Najlepiej spożyć przed:", f2), ("patrz kapsel", f2)]
y = 40
for t, fn in lines:
    ldr.text((256, y), t, font=fn, fill=(60, 30, 20, 255), anchor="mm")
    y += 52
for i in range(28):  # barcode
    x = 150 + i * 8
    ldr.rectangle((x, 370, x + (2 if i % 3 else 5), 410), fill=(20, 20, 20, 255))
atlas.paste(lab, (b[0], b[1]))
region("bottle_back", b)

# --- neck label
b = (0, 1792, 768, 2048)
lab = Image.new("RGBA", (768, 256), RED)
ldr = ImageDraw.Draw(lab)
ldr.rectangle((0, 0, 767, 30), fill=GOLD)
ldr.rectangle((0, 226, 767, 255), fill=GOLD)
crown(ldr, 120, 128, 110, GOLD, GOLD_D)
f = fit_font(SERIF_BI, "Tyskie", (0, 0, 420, 170), 0.9)
ldr.text((440, 128), "Tyskie", font=f, fill=GOLD, anchor="mm")
atlas.paste(lab, (b[0], b[1]))
region("neck", b)

# --- can wrap
b = (1536, 1024, 2048, 1280)
d.rectangle(b, fill=(176, 20, 30, 255))
d.rectangle((1536, 1024, 2048, 1044), fill=(212, 178, 96, 255))
d.rectangle((1536, 1260, 2048, 1280), fill=(212, 178, 96, 255))
text_center((1556, 1060, 2028, 1250), "Tyskie", fit_font(SERIF_B, "Tyskie", (1556, 1060, 2028, 1250), 0.8),
            (238, 204, 118, 255))
region("can", b)

# --- licence-plate style sign
b = (0, 1536, 1024, 1792)
d.rectangle(b, fill=(250, 250, 250, 255), outline=(20, 20, 20, 255), width=8)
d.rectangle((0, 1536, 110, 1792), fill=(20, 60, 170, 255))
text_center((120, 1546, 1014, 1782), "PLO 5617", fit_font(SANS_B, "PLO 5617", (120, 1546, 1014, 1782), 0.8),
            (20, 20, 20, 255))
region("plate_number", b)

atlas_img = atlas
atlas_img.save(os.path.join(OUT, "bizon_decals.png"))


def save_dds(img, path, fmt):
    img.save(path, "DDS", pixel_format=fmt)


save_dds(atlas_img, os.path.join(OUT, "bizon_decals_diffuse.dds"), "DXT5")

# flat normal for decals / generic (RGB 128,128,255)
Image.new("RGB", (64, 64), (128, 128, 255)).save(os.path.join(OUT, "flat_normal.png"))

json.dump(regions, open(os.path.join(OUT, "decal_regions.json"), "w"), indent=1)
print("ok", len(regions), "regions")
