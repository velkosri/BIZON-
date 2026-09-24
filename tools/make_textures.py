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

# --- crate side panel (dark red plastic with embossed-looking name)
b = (1024, 256, 2048, 512)
d.rectangle(b, fill=(122, 14, 20, 255))
for i in range(6):
    d.rectangle((b[0] + 20 + i * 168, b[1] + 16, b[0] + 160 + i * 168, b[1] + 60), fill=(98, 10, 16, 255))
text_center((1064, 330, 2008, 500), "TYSKIE", fit_font(SANS_B, "TYSKIE", (1064, 330, 2008, 500), 0.8),
            (222, 186, 100, 255))
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

# --- bottle label (small, round-cornered)
b = (1024, 1024, 1536, 1280)
lab = Image.new("RGBA", (512, 256), (0, 0, 0, 0))
ldr = ImageDraw.Draw(lab)
ldr.rectangle((0, 0, 512, 256), fill=(206, 170, 88, 255))
ldr.rectangle((0, 40, 512, 216), fill=(150, 16, 26, 255))
atlas.alpha_composite(lab, (1024, 1024))
text_center((1044, 1070, 1516, 1230), "Tyskie", fit_font(SERIF_B, "Tyskie", (1044, 1070, 1516, 1230), 0.86),
            (236, 200, 112, 255))
region("bottle", b)

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
