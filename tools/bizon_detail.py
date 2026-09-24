"""High detail parts: agricultural tyres + rims, Tyskie-style bottle and crate, and the Cycles
render look (PBR textures, wear, dust, HDRI field scene with stubble).

Blender axes: X right, Y forward, Z up. Wheel axis = X.
"""
import math
import os

import bmesh
import bpy
from mathutils import Matrix, Vector

import blender_kit as K

ASSETS = os.environ.get("BIZON_ASSETS", "/tmp/assets")
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


# ================================================================== tyre

def _carcass_profile(w, r_crown, rim_r):
    """(x, rho) half profile from the bead to the tread centre; mirrored for the other half."""
    bead_x = w * 0.38
    pts = [(bead_x, rim_r + 0.015), (bead_x + w * 0.04, rim_r + 0.05)]
    # sidewall bulge
    mid = rim_r + (r_crown - rim_r) * 0.55
    for i in range(1, 8):
        t = i / 8
        rho = rim_r + 0.05 + (r_crown - 0.06 - rim_r - 0.05) * t
        bulge = math.sin(t * math.pi) * w * 0.08
        pts.append((bead_x + w * 0.04 + bulge, rho))
    # shoulder round-over to the crown
    sh_r = 0.07
    cx, cz = w / 2 - sh_r, r_crown - sh_r
    for i in range(0, 7):
        a = i / 6 * math.pi / 2
        pts.append((cx + math.cos(a) * sh_r, cz + math.sin(a) * sh_r))
    # slightly crowned tread
    for i in range(1, 6):
        x = cx * (1 - i / 5)
        pts.append((x, r_crown + 0.006 * (1 - (x / cx) ** 2)))
    return pts


def _rho_at(profile, x):
    """Carcass outer radius at axial x (tread/shoulder part)."""
    x = abs(x)
    best = None
    for (x0, r0), (x1, r1) in zip(profile, profile[1:]):
        lo, hi = min(x0, x1), max(x0, x1)
        if lo - 1e-6 <= x <= hi + 1e-6 and r0 > profile[0][1] + 0.1 and r1 > profile[0][1] + 0.1:
            t = 0 if hi == lo else (x - x0) / (x1 - x0)
            r = r0 + (r1 - r0) * t
            best = r if best is None else max(best, r)
    return best if best is not None else profile[-1][1]


def agri_tyre(name, r, w, rim_r, parent, sx, lug_h=0.05, n_lugs=22, lug_angle=38, label="STOMIL",
              size_txt="18.4-26", segs=96):
    """R-1 style bias tractor/harvester tyre: round carcass, staggered chevron lugs wrapping over the
    shoulder, sidewall with raised lettering and rim protector ring."""
    e = K.empty(name, (0, 0, 0), parent)
    rc = r - lug_h
    prof = _carcass_profile(w, rc, rim_r)
    full = [(-x, p) for x, p in prof] + [(x, p) for x, p in reversed(prof)]
    bm = bmesh.new()
    rings = []
    for i in range(segs):
        a = 2 * math.pi * i / segs
        rings.append([bm.verts.new((x, math.cos(a) * p, math.sin(a) * p)) for x, p in full])
    m = len(full)
    for i in range(segs):
        a, b = rings[i], rings[(i + 1) % segs]
        for k in range(m - 1):
            bm.faces.new((a[k], b[k], b[k + 1], a[k + 1]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    K.mesh_from_bm(name + "_carcass", bm, "tire", e, smooth_angle=50)

    # lugs
    bm = bmesh.new()
    tan_a = math.tan(math.radians(lug_angle))
    pitch = 2 * math.pi / n_lugs
    for side in (-1, 1):
        for i in range(n_lugs):
            th0 = i * pitch + (pitch / 2 if side > 0 else 0)
            xs = [0.015 + (w / 2 - 0.008 - 0.015) * j / 11 for j in range(12)]
            ring = []
            for j, x in enumerate(xs):
                rho = _rho_at(prof, x)
                h = lug_h * min(1.0, 0.45 + j * 0.25)
                if x > w / 2 - 0.06:  # lug face follows the shoulder down
                    h *= 0.95
                th = th0 + side * 0 + (x * tan_a) / rc
                wb, wt = 0.075, 0.052  # base/top width along the circumference
                quad = []
                for (ww, hh) in ((-wb, 0.0), (wb, 0.0), (wt, h), (-wt, h)):
                    rr = rho - 0.004 + hh
                    t2 = th + (ww / 2) / rr
                    quad.append(bm.verts.new((side * x, math.cos(t2) * rr, math.sin(t2) * rr)))
                ring.append(quad)
            for a, b in zip(ring, ring[1:]):
                for k in range(4):
                    kk = (k + 1) % 4
                    bm.faces.new((a[k], a[kk], b[kk], b[k]))
            bm.faces.new(list(reversed(ring[0])))
            bm.faces.new(ring[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    K.mesh_from_bm(name + "_lugs", bm, "tire", e, smooth_angle=30)

    # sidewall lettering (outer side only) + rim protector ring
    ring_r = rim_r + 0.07
    K.tube(name + "_rimGuard", ring_r + 0.018, ring_r - 0.006, 0.02, (sx * (w * 0.43 + 0.012), 0, 0), "tire", e,
           axis="X", verts=segs)
    txt_r = rim_r + (rc - rim_r) * 0.55
    t_txt = (txt_r - rim_r - 0.05) / (rc - 0.11 - rim_r)
    x_side = w * 0.42 + w * 0.08 * math.sin(t_txt * math.pi) - 0.002
    for k, (txt, a0, size) in enumerate(((label, 90, 0.07), (size_txt, 270, 0.06), ("T-49  10PR", 20, 0.04))):
        sidewall_text(name + "_txt%d" % k, txt, txt_r, math.radians(a0), size, sx * x_side, sx, e)
    return e


def sidewall_text(name, txt, radius, a_center, size, x_plane, sx, parent, depth=0.004):
    cu = bpy.data.curves.new(name, "FONT")
    cu.body = txt
    cu.font = bpy.data.fonts.load(FONT, check_existing=True)
    cu.size = size
    cu.extrude = depth
    cu.align_x = "CENTER"
    cu.align_y = "CENTER"
    tmp = bpy.data.objects.new(name + "_tmp", cu)
    bpy.context.scene.collection.objects.link(tmp)
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(tmp.evaluated_get(dg))
    bpy.data.objects.remove(tmp)
    bm = bmesh.new()
    bm.from_mesh(me)
    bpy.data.meshes.remove(me)
    for v in bm.verts:
        u, h, d = v.co.x, v.co.y, v.co.z
        a = a_center - sx * u / radius
        rr = radius + h
        v.co = Vector((x_plane + sx * d, math.cos(a) * rr, math.sin(a) * rr))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return K.mesh_from_bm(name, bm, "tire", parent, smooth_angle=30)


def agri_rim(name, rim_r, rim_w, parent, sx, holes=8, mat="rimPaint"):
    """Drop-centre rim with flanges, dished centre disc with oval vent holes, hub, studs, nuts, valve."""
    e = K.empty(name, (0, 0, 0), parent)
    hw = rim_w / 2
    prof = [(-hw - 0.01, rim_r + 0.035), (-hw, rim_r + 0.04), (-hw + 0.012, rim_r + 0.012),
            (-hw + 0.06, rim_r), (-hw * 0.35, rim_r - 0.004), (-hw * 0.25, rim_r - 0.06),
            (hw * 0.25, rim_r - 0.06), (hw * 0.35, rim_r - 0.004), (hw - 0.06, rim_r),
            (hw - 0.012, rim_r + 0.012), (hw, rim_r + 0.04), (hw + 0.01, rim_r + 0.035)]
    bm = bmesh.new()
    segs = 80
    rings = []
    for i in range(segs):
        a = 2 * math.pi * i / segs
        rings.append([bm.verts.new((x, math.cos(a) * p, math.sin(a) * p)) for x, p in prof])
    for i in range(segs):
        a, b = rings[i], rings[(i + 1) % segs]
        for k in range(len(prof) - 1):
            bm.faces.new((a[k], b[k], b[k + 1], a[k + 1]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    rim = K.mesh_from_bm(name + "_band", bm, mat, e, smooth_angle=40)
    rim.modifiers.new("solid", "SOLIDIFY").thickness = 0.006
    # dished disc, cut with oval holes
    disc_r = rim_r - 0.06
    disc_x = sx * hw * 0.1
    dprof = [(disc_x, disc_r), (disc_x + sx * 0.03, disc_r * 0.72), (disc_x + sx * 0.06, disc_r * 0.42),
             (disc_x + sx * 0.07, 0.13)]
    bm = bmesh.new()
    rings = []
    for i in range(64):
        a = 2 * math.pi * i / 64
        rings.append([bm.verts.new((x, math.cos(a) * p, math.sin(a) * p)) for x, p in dprof])
    for i in range(64):
        a, b = rings[i], rings[(i + 1) % 64]
        for k in range(len(dprof) - 1):
            bm.faces.new((a[k], b[k], b[k + 1], a[k + 1]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    disc = K.mesh_from_bm(name + "_disc", bm, mat, e, smooth_angle=40)
    disc.modifiers.new("solid", "SOLIDIFY").thickness = 0.01
    cutters = []
    for i in range(holes):
        a = 2 * math.pi * (i + 0.5) / holes
        rr = disc_r * 0.62
        c = K.cyl(name + "_hole%d" % i, 0.055, 0.4, (disc_x, math.cos(a) * rr, math.sin(a) * rr), "inv", e,
                  axis="X", verts=20)
        c.scale = (1, 1, 1)
        c.data.transform(Matrix.Scale(1.45, 4, (0, math.cos(a), math.sin(a))))
        cutters.append(c)
    _boolean_cut(disc, cutters)
    # hub, studs + nuts, cap
    K.cyl(name + "_hub", 0.13, 0.08, (disc_x + sx * 0.09, 0, 0), "metalDark", e, axis="X", verts=32, bevel=0.01)
    K.cyl(name + "_cap", 0.07, 0.07, (disc_x + sx * 0.15, 0, 0), "metalDark", e, axis="X", verts=24, r2=0.05)
    for i in range(8):
        a = 2 * math.pi * i / 8
        p = (disc_x + sx * 0.085, math.cos(a) * 0.105, math.sin(a) * 0.105)
        K.cyl(name + "_nut%d" % i, 0.017, 0.028, p, "steelDirty", e, axis="X", verts=6)
        K.cyl(name + "_stud%d" % i, 0.009, 0.045, (p[0] + sx * 0.02, p[1], p[2]), "steelDirty", e, axis="X",
              verts=8)
    # valve stem through the rim
    K.cyl(name + "_valve", 0.006, 0.05, (sx * hw * 0.3, 0, rim_r - 0.04), "rubber", e, axis="X", verts=8)
    K.cyl(name + "_valveCap", 0.005, 0.015, (sx * (hw * 0.3 + 0.03), 0, rim_r - 0.04), "steel", e, axis="X",
          verts=8)
    return e


def _boolean_cut(obj, cutters):
    for c in cutters:
        mod = obj.modifiers.new("cut", "BOOLEAN")
        mod.operation = "DIFFERENCE"
        mod.object = c
        mod.solver = "EXACT"
        c.hide_render = True
        c.hide_viewport = True
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(obj.evaluated_get(dg))
    obj.modifiers.clear()
    old = obj.data
    obj.data = me
    bpy.data.meshes.remove(old)
    for c in cutters:
        bpy.data.objects.remove(c)


def apply_modifiers(obj):
    if not obj.modifiers:
        return
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(obj.evaluated_get(dg))
    obj.modifiers.clear()
    old = obj.data
    obj.data = me
    bpy.data.meshes.remove(old)


def wheel(name, loc, r, w, rim_r, sx, parent=None, export=False, **kw):
    e = K.empty(name, loc, parent, props={"export": export})
    agri_tyre(name + "_tyre", r, w, rim_r, e, sx, **kw)
    agri_rim(name + "_rim", rim_r, w * 0.8, e, sx)
    for o in e.children_recursive:
        o["export"] = export
        if o.type == "MESH":
            apply_modifiers(o)
    return e


# ================================================================== beer

BOTTLE_PROFILE = [  # (radius, z) in metres, Polish 0.5 l returnable brown bottle
    (0.0, 0.002), (0.024, 0.0), (0.031, 0.003), (0.0335, 0.012), (0.0335, 0.145), (0.033, 0.158),
    (0.030, 0.172), (0.024, 0.186), (0.018, 0.198), (0.0145, 0.21), (0.0132, 0.225), (0.0132, 0.232),
    (0.0148, 0.234), (0.0148, 0.243), (0.0135, 0.245)]


def lathe(name, profile, mat, parent, loc=(0, 0, 0), segs=28, cap_top=False, smooth=40):
    bm = bmesh.new()
    rings = []
    for i in range(segs):
        a = 2 * math.pi * i / segs
        rings.append([bm.verts.new((math.cos(a) * r, math.sin(a) * r, z)) for r, z in profile])
    n = len(profile)
    for i in range(segs):
        a, b = rings[i], rings[(i + 1) % segs]
        for k in range(n - 1):
            if profile[k][0] == 0 and profile[k + 1][0] == 0:
                continue
            bm.faces.new((a[k], a[k + 1], b[k + 1], b[k]))
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    if cap_top:
        top = [r[-1] for r in rings]
        top = [v for v in top if v.is_valid]
        if len(top) > 2:
            bm.faces.new(top)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return K.mesh_from_bm(name, bm, mat, parent, loc, smooth_angle=smooth)


def label_band(name, radius, z0, z1, a0, a1, region, parent, segs=16):
    """Curved label following the bottle body, textured with an atlas region."""
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("uv0")
    u0, v0, u1, v1 = region
    cols = []
    for i in range(segs + 1):
        a = a0 + (a1 - a0) * i / segs
        cols.append((bm.verts.new((math.cos(a) * radius, math.sin(a) * radius, z0)),
                     bm.verts.new((math.cos(a) * radius, math.sin(a) * radius, z1))))
    for i in range(segs):
        f = bm.faces.new((cols[i][0], cols[i + 1][0], cols[i + 1][1], cols[i][1]))
        uu0 = u0 + (u1 - u0) * i / segs
        uu1 = u0 + (u1 - u0) * (i + 1) / segs
        for loop, (a, b) in zip(f.loops, ((uu0, v0), (uu1, v0), (uu1, v1), (uu0, v1))):
            loop[uv].uv = (a, b)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    for f in bm.faces:  # outward
        c = f.calc_center_median()
        if f.normal.dot(Vector((c.x, c.y, 0))) < 0:
            f.normal_flip()
    o = K.mesh_from_bm(name, bm, "decals", parent, smooth_angle=80)
    o["keep_uv"] = True
    o["decal"] = True
    return o


def beer_bottle(name, loc, parent, reg, opened=False, rot_z=0.0, segs=24):
    e = K.empty(name, loc, parent, rot=(0, 0, rot_z))
    outer = lathe(name + "_glass", BOTTLE_PROFILE, "bottleGlass", e, segs=segs)
    sol = outer.modifiers.new("wall", "SOLIDIFY")
    sol.thickness = 0.0028
    sol.offset = -1
    apply_modifiers(outer)
    # beer inside, filled up into the neck
    liq = [(0.0, 0.004), (0.029, 0.004), (0.0305, 0.012), (0.0305, 0.145), (0.0275, 0.172), (0.021, 0.186),
           (0.015, 0.198), (0.0115, 0.206), (0.0, 0.206)]
    lathe(name + "_beer", liq, "beerLiquid", e, segs=segs)
    # body label (front + back), neck foil, shoulder label
    label_band(name + "_lbl", 0.0338, 0.055, 0.128, -1.05, 1.05, reg["bottle"], e)
    label_band(name + "_lblBack", 0.0338, 0.07, 0.11, math.pi - 0.7, math.pi + 0.7, reg["bottle_back"], e)
    neck = [(0.0137, 0.214), (0.0134, 0.222), (0.0134, 0.2325), (0.0151, 0.2345), (0.0151, 0.2435)]
    if not opened:
        lathe(name + "_foil", neck, "goldFoil", e, segs=segs)
        cap = []
        for i in range(42):
            a = 2 * math.pi * i / 42
            cap.append(0.0158 if i % 2 == 0 else 0.0150)
        crown(name + "_cap", e, 0.2435, cap)
    label_band(name + "_neckLbl", 0.0192, 0.188, 0.2, -0.9, 0.9, reg["neck"], e, segs=10)
    return e


def crown(name, parent, z, radii, h=0.0065):
    bm = bmesh.new()
    n = len(radii)
    bot = [bm.verts.new((math.cos(2 * math.pi * i / n) * r, math.sin(2 * math.pi * i / n) * r, z - 0.0005))
           for i, r in enumerate(radii)]
    top = [bm.verts.new((math.cos(2 * math.pi * i / n) * 0.0138, math.sin(2 * math.pi * i / n) * 0.0138,
                         z + h)) for i in range(n)]
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((bot[i], bot[j], top[j], top[i]))
    bm.faces.new(top)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return K.mesh_from_bm(name, bm, "goldCap", parent, smooth_angle=60)


def beer_crate(name, loc, parent, reg, rot_z=0.0, full=19):
    """20 x 0.5 l returnable plastic crate: rounded shell, side windows, hand holds, divider grid."""
    e = K.empty(name, loc, parent, rot=(0, 0, rot_z))
    L, W, H = 0.40, 0.30, 0.27
    # shell: rounded box, hollowed with solidify, cut with windows and hand holds
    sh = K.box(name + "_shell", (W, L, H), (0, 0, H / 2), "crateRed", e, bevel=0.022, segs=4)
    bm = bmesh.new()
    bm.from_mesh(sh.data)
    top = [f for f in bm.faces if f.normal.z > 0.9 and f.calc_center_median().z > H / 2 - 0.01]
    bmesh.ops.delete(bm, geom=top, context="FACES")
    bm.to_mesh(sh.data)
    bm.free()
    sol = sh.modifiers.new("wall", "SOLIDIFY")
    sol.thickness = 0.006
    sol.offset = -1
    apply_modifiers(sh)
    cut = []
    for sx in (-1, 1):  # hand holds on the short sides
        c = K.box(name + "_hh%d" % sx, (0.12, 0.2, 0.035), (0, sx * L / 2, H - 0.045), "inv", e, bevel=0.016,
                  segs=3)
        cut.append(c)
    for sx in (-1, 1):  # window rows on the long sides
        for i in range(5):
            y = -0.15 + i * 0.075
            c = K.box(name + "_win%d_%d" % (sx, i), (0.2, 0.05, 0.075), (sx * W / 2, y, 0.07), "inv", e,
                      bevel=0.01, segs=2)
            cut.append(c)
    for sx in (-1, 1):
        for i in range(3):
            x = -0.085 + i * 0.085
            c = K.box(name + "_wins%d_%d" % (sx, i), (0.05, 0.2, 0.075), (x, sx * L / 2, 0.07), "inv", e,
                      bevel=0.01, segs=2)
            cut.append(c)
    _boolean_cut(sh, cut)
    # rim band + stacking ribs
    for sx in (-1, 1):  # thickened top rim (frame, not a lid)
        K.box(name + "_rimX%d" % sx, (0.014, L + 0.008, 0.02), (sx * (W / 2 - 0.003), 0, H - 0.012), "crateRed", e,
              bevel=0.005)
        K.box(name + "_rimY%d" % sx, (W + 0.008, 0.014, 0.02), (0, sx * (L / 2 - 0.003), H - 0.012), "crateRed", e,
              bevel=0.005)
    for sx in (-1, 1):
        for i in range(4):
            K.box(name + "_rib%d_%d" % (sx, i), (0.008, 0.012, H - 0.06), (sx * (W / 2 + 0.003), -0.12 + i * 0.08,
                                                                          H / 2 + 0.01), "crateRed", e, bevel=0.003)
    # divider grid
    for i in range(1, 4):
        K.box(name + "_divX%d" % i, (0.004, L - 0.02, 0.16), (-W / 2 + i * W / 4, 0, 0.09), "crateRed", e, bevel=0)
    for i in range(1, 5):
        K.box(name + "_divY%d" % i, (W - 0.02, 0.004, 0.16), (0, -L / 2 + i * L / 5, 0.09), "crateRed", e, bevel=0)
    # logo panels on both long sides (above the windows)
    for sx in (-1, 1):
        K.decal(name + "_logo%d" % sx, (sx * (W / 2 + 0.0015), 0, 0.19), (0.3, 0.075), reg["crate"], "decals", e,
                "+X" if sx > 0 else "-X")
    # bottles
    k = 0
    for ix in range(4):
        for iy in range(5):
            if k >= full:
                break
            x = -W / 2 + W / 8 + ix * W / 4
            y = -L / 2 + L / 10 + iy * L / 5
            beer_bottle(name + "_b%d%d" % (ix, iy), (x, y, 0.008), e, reg, rot_z=(ix * 1.7 + iy * 2.3) % 6.28)
            k += 1
    return e


# ================================================================== render look

def _img(path, colorspace="sRGB"):
    im = bpy.data.images.load(path, check_existing=True)
    im.colorspace_settings.name = colorspace
    return im


def _tex(nt, vec, name, colorspace="sRGB", blend=0.25):
    n = nt.nodes.new("ShaderNodeTexImage")
    n.image = _img(os.path.join(ASSETS, name), colorspace)
    n.projection = "BOX"
    n.projection_blend = blend
    nt.links.new(vec, n.inputs["Vector"])
    return n


def _vec(nt, scale):
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (scale, scale, scale)
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    return mp.outputs["Vector"], tc


def _math(nt, op, a, b=None, clamp=False):
    n = nt.nodes.new("ShaderNodeMath")
    n.operation = op
    n.use_clamp = clamp
    for i, v in enumerate((a, b)):
        if v is None:
            continue
        if isinstance(v, (int, float)):
            n.inputs[i].default_value = v
        else:
            nt.links.new(v, n.inputs[i])
    return n.outputs[0]


def _mix(nt, fac, a, b):
    n = nt.nodes.new("ShaderNodeMix")
    n.data_type = "RGBA"
    for key, v in (("Factor", fac), ("A", a), ("B", b)):
        if isinstance(v, tuple):
            n.inputs[key].default_value = v
        elif isinstance(v, (int, float)):
            n.inputs[key].default_value = v
        else:
            nt.links.new(v, n.inputs[key])
    return n.outputs["Result"]


def _dust_mask(nt, tc, height=1.3, amount=0.55):
    """More dust low on the machine and in cavities."""
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs[0])
    # object space z is local; use world position instead
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    sepw = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(geo.outputs["Position"], sepw.inputs[0])
    low = _math(nt, "SUBTRACT", 1.0, _math(nt, "DIVIDE", sepw.outputs["Z"], height), clamp=True)
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 3.0
    noise.inputs["Detail"].default_value = 6
    nt.links.new(geo.outputs["Position"], noise.inputs["Vector"])
    sepn = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(geo.outputs["Normal"], sepn.inputs[0])
    top = _math(nt, "MULTIPLY", _math(nt, "MAXIMUM", sepn.outputs["Z"], 0.0), 0.35)
    m = _math(nt, "ADD", _math(nt, "POWER", low, 1.6), top)
    m = _math(nt, "MULTIPLY", m, _math(nt, "ADD", noise.outputs["Fac"], 0.1))
    return _math(nt, "MULTIPLY", m, amount, clamp=True)


def paint_material(mat, color_lin, rough=0.42, rust=0.6, dust=0.55, scale=0.9):
    """Painted steel: real paint texture (green_metal_rust recoloured), rust streaks kept, worn edges,
    dust from the ground up."""
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(bsdf.outputs[0], out.inputs[0])
    vec, tc = _vec(nt, scale)
    diff = _tex(nt, vec, "green_metal_rust_diff_2k.jpg")
    rgh = _tex(nt, vec, "green_metal_rust_rough_2k.jpg", "Non-Color")
    nor = _tex(nt, vec, "green_metal_rust_nor_gl_2k.jpg", "Non-Color")
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(diff.outputs["Color"], sep.inputs[0])
    # paint mask: green dominates -> original paint; else rust/stain
    g_minus = _math(nt, "SUBTRACT", sep.outputs["Green"], _math(nt, "MAXIMUM", sep.outputs["Red"], sep.outputs["Blue"]))
    paint_m = _math(nt, "MULTIPLY", g_minus, 14.0, clamp=True)
    lum = _math(nt, "MULTIPLY", sep.outputs["Green"], 3.2, clamp=False)
    tint = _mix(nt, 0.0, (*color_lin, 1), (*color_lin, 1))
    cmul = nt.nodes.new("ShaderNodeMix")
    cmul.data_type = "RGBA"
    cmul.blend_type = "MULTIPLY"
    cmul.inputs["Factor"].default_value = 1.0
    nt.links.new(tint, cmul.inputs["A"])
    lum_c = nt.nodes.new("ShaderNodeCombineColor")
    for ch in ("Red", "Green", "Blue"):
        nt.links.new(_math(nt, "ADD", _math(nt, "MULTIPLY", lum, 0.45), 0.62), lum_c.inputs[ch])
    nt.links.new(lum_c.outputs[0], cmul.inputs["B"])
    rust_col = diff.outputs["Color"]
    rust_amt = _math(nt, "MULTIPLY", _math(nt, "SUBTRACT", 1.0, paint_m), rust, clamp=True)
    col = _mix(nt, rust_amt, cmul.outputs["Result"], rust_col)
    # worn edges -> dark primer/steel
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    edge = _math(nt, "MULTIPLY", _math(nt, "SUBTRACT", geo.outputs["Pointiness"], 0.53), 9.0, clamp=True)
    en = nt.nodes.new("ShaderNodeTexNoise")
    en.inputs["Scale"].default_value = 18
    en.inputs["Detail"].default_value = 8
    nt.links.new(geo.outputs["Position"], en.inputs["Vector"])
    edge = _math(nt, "MULTIPLY", edge, _math(nt, "MULTIPLY", en.outputs["Fac"], 1.6), clamp=True)
    col = _mix(nt, edge, col, (0.05, 0.045, 0.04, 1))
    dm = _dust_mask(nt, tc, amount=dust)
    col = _mix(nt, dm, col, (0.30, 0.24, 0.16, 1))
    nt.links.new(col, bsdf.inputs["Base Color"])
    r = _math(nt, "ADD", _math(nt, "MULTIPLY", rgh.outputs["Color"], 0.5), rough * 0.6)
    r = _math(nt, "ADD", r, _math(nt, "MULTIPLY", dm, 0.5), clamp=True)
    nt.links.new(r, bsdf.inputs["Roughness"])
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nm.inputs["Strength"].default_value = 0.6
    nt.links.new(nor.outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs[0], bsdf.inputs["Normal"])
    bsdf.inputs["Coat Weight"].default_value = 0.08


def textured_material(mat, diff_name, rough_name, nor_name, tint=None, scale=1.0, metal=0.0, nstr=1.0,
                      dust=0.4, rough_add=0.0):
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(bsdf.outputs[0], out.inputs[0])
    vec, tc = _vec(nt, scale)
    col = _tex(nt, vec, diff_name).outputs["Color"] if diff_name else (*tint, 1)
    if diff_name and tint:
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        mix.blend_type = "MULTIPLY"
        mix.inputs["Factor"].default_value = 1.0
        nt.links.new(col, mix.inputs["A"])
        mix.inputs["B"].default_value = (*tint, 1)
        col = mix.outputs["Result"]
    dm = _dust_mask(nt, tc, amount=dust)
    col = _mix(nt, dm, col, (0.28, 0.22, 0.15, 1))
    nt.links.new(col, bsdf.inputs["Base Color"])
    if rough_name:
        r = _math(nt, "ADD", _tex(nt, vec, rough_name, "Non-Color").outputs["Color"], rough_add, clamp=True)
        nt.links.new(_math(nt, "ADD", r, _math(nt, "MULTIPLY", dm, 0.4), clamp=True), bsdf.inputs["Roughness"])
    if nor_name:
        nm = nt.nodes.new("ShaderNodeNormalMap")
        nm.inputs["Strength"].default_value = nstr
        nt.links.new(_tex(nt, vec, nor_name, "Non-Color").outputs["Color"], nm.inputs["Color"])
        nt.links.new(nm.outputs[0], bsdf.inputs["Normal"])
    bsdf.inputs["Metallic"].default_value = metal


def glass_material(mat, color, rough=0.02, ior=1.52):
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Transmission Weight"].default_value = 1.0
    b.inputs["Roughness"].default_value = rough
    b.inputs["IOR"].default_value = ior
    nt.links.new(b.outputs[0], out.inputs[0])


def thin_glass(mat, color):
    """Window pane: no refraction (panes are single sheets), reflection by fresnel."""
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    tr.inputs["Color"].default_value = (*color, 1)
    gl = nt.nodes.new("ShaderNodeBsdfGlossy")
    gl.inputs["Roughness"].default_value = 0.03
    fr = nt.nodes.new("ShaderNodeLayerWeight")
    fr.inputs["Blend"].default_value = 0.12
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(fr.outputs["Fresnel"], mix.inputs[0])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(gl.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs[0])


def liquid_material(mat):
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    b.inputs["Base Color"].default_value = (1, 0.75, 0.3, 1)
    b.inputs["Transmission Weight"].default_value = 1.0
    b.inputs["Roughness"].default_value = 0.0
    b.inputs["IOR"].default_value = 1.34
    vol = nt.nodes.new("ShaderNodeVolumeAbsorption")
    vol.inputs["Color"].default_value = (0.95, 0.55, 0.12, 1)
    vol.inputs["Density"].default_value = 30.0
    nt.links.new(b.outputs[0], out.inputs["Surface"])
    nt.links.new(vol.outputs[0], out.inputs["Volume"])


def apply_render_look():
    M = bpy.data.materials
    for name in ("red", "redClean", "cream", "yellow", "engineGrey", "black", "rimPaint"):
        m = M.get(name)
        if m:
            lin = tuple(m["fs_color"])
            if name in ("red", "redClean"):
                # AgX + warm HDRI desaturate the in-game red towards brown; push it back to Bizon signal red
                lin = (0.78, 0.028, 0.02)
            paint_material(m, lin, rust={"red": 0.28, "cream": 0.4, "rimPaint": 0.35}.get(name, 0.3),
                           dust={"black": 0.35, "red": 0.5}.get(name, 0.4), scale=0.8)
    textured_material(M["tread"], "metal_plate_diff_2k.jpg", "metal_plate_rough_2k.jpg", "metal_plate_nor_gl_2k.jpg",
                      scale=1.2, metal=0.6, dust=0.5)
    for n in ("rust",):
        textured_material(M[n], "rusty_painted_metal_diff_2k.jpg", "rusty_painted_metal_rough_2k.jpg",
                          "rusty_painted_metal_nor_gl_2k.jpg", tint=(0.5, 0.4, 0.35), scale=2.5, metal=0.3)
    for n in ("tire", "rubber", "rubberBelt", "hoseBlack"):
        textured_material(M[n], None, "rubberized_track_rough_2k.jpg", "rubberized_track_nor_gl_2k.jpg",
                          tint=(0.018, 0.018, 0.017), scale=4.0, nstr=0.5, dust=0.7 if n == "tire" else 0.3,
                          rough_add=0.35)
    thin_glass(M["glass"], (0.8, 0.86, 0.84))
    glass_material(M["lampGlass"], (0.95, 0.95, 0.9))
    glass_material(M["bottleGlass"], (0.42, 0.17, 0.035), rough=0.015)
    liquid_material(M["beerLiquid"])
    m = M["decals"]
    b = m.node_tree.nodes.get("Principled BSDF")
    if b:
        b.inputs["Roughness"].default_value = 0.55
    m.blend_method = "HASHED"


def _fade_to_backplate(mat, r0, r1):
    """Soil turns transparent with distance so the HDRI's own field continues to the horizon."""
    nt = mat.node_tree
    out = [n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"][0]
    surf = out.inputs["Surface"].links[0].from_socket
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    dist = nt.nodes.new("ShaderNodeVectorMath")
    dist.operation = "LENGTH"
    nt.links.new(geo.outputs["Position"], dist.inputs[0])
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = r0
    mr.inputs["From Max"].default_value = r1
    nt.links.new(dist.outputs["Value"], mr.inputs["Value"])
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(mr.outputs["Result"], mix.inputs[0])
    nt.links.new(surf, mix.inputs[1])
    nt.links.new(tr.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])


def field_scene(center=(0, -1.5)):
    """HDRI (harvested field, CC0 Poly Haven) + textured soil with Cycles-hair stubble."""
    sc = bpy.context.scene
    world = bpy.data.worlds.new("harvest")
    sc.world = world
    world.use_nodes = True
    nt = world.node_tree
    env = nt.nodes.new("ShaderNodeTexEnvironment")
    env.image = _img(os.path.join(ASSETS, "harvest_2k.hdr"), "Linear Rec.709")
    mp = nt.nodes.new("ShaderNodeMapping")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp.inputs["Rotation"].default_value = (0, 0, math.radians(120))
    nt.links.new(tc.outputs["Generated"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], env.inputs["Vector"])
    nt.links.new(env.outputs["Color"], nt.nodes["Background"].inputs["Color"])
    nt.nodes["Background"].inputs["Strength"].default_value = 1.0
    # soil
    bpy.ops.mesh.primitive_plane_add(size=400, location=(0, 0, 0))
    g = bpy.context.active_object
    g.name = "ground"
    g["export"] = False
    gm = bpy.data.materials.new("soil")
    gm.use_nodes = True
    textured_material(gm, "dry_mud_field_001_diff_2k.jpg", "dry_mud_field_001_rough_2k.jpg",
                      "dry_mud_field_001_nor_gl_2k.jpg", scale=0.35, dust=0.0)
    _fade_to_backplate(gm, 26.0, 45.0)
    g.data.materials.append(gm)
    # stubble patch with hair particles
    bpy.ops.mesh.primitive_plane_add(size=1, location=(center[0], center[1], 0.001))
    s = bpy.context.active_object
    s.name = "stubbleEmitter"
    s.scale = (34, 40, 1)
    s["export"] = False
    bpy.ops.object.transform_apply(scale=True)
    sm = bpy.data.materials.new("stubble")
    sm.use_nodes = True
    snt = sm.node_tree
    hb = snt.nodes["Principled BSDF"]
    hi = snt.nodes.new("ShaderNodeHairInfo")
    ramp = snt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.22, 0.17, 0.07, 1)
    ramp.color_ramp.elements[1].color = (0.75, 0.6, 0.3, 1)
    snt.links.new(hi.outputs["Random"], ramp.inputs["Fac"])
    snt.links.new(ramp.outputs["Color"], hb.inputs["Base Color"])
    hb.inputs["Roughness"].default_value = 0.7
    s.data.materials.append(gm)
    s.data.materials.append(sm)
    ps = s.modifiers.new("stubble", "PARTICLE_SYSTEM").particle_system
    st = ps.settings
    st.type = "HAIR"
    st.count = 260000
    st.hair_length = 0.13
    st.use_advanced_hair = True
    st.emit_from = "FACE"
    st.distribution = "JIT"
    # advanced hair: length comes from the emission velocity, not hair_length
    st.normal_factor = 0.13
    st.factor_random = 0.03
    st.length_random = 0.6
    st.brownian_factor = 0.02
    st.material_slot = "stubble"
    st.root_radius = 0.0025
    st.tip_radius = 0.0012
    st.radius_scale = 1.0
    st.display_step = 2
    st.render_step = 2
    # raked straw swath behind the machine
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, -14.0, 0.004))
    sw = bpy.context.active_object
    sw.name = "swathEmitter"
    sw.scale = (0.9, 17, 1)
    sw["export"] = False
    bpy.ops.object.transform_apply(scale=True)
    sw.data.materials.append(gm)
    sw.data.materials.append(sm)
    ps2 = sw.modifiers.new("straw", "PARTICLE_SYSTEM").particle_system
    st2 = ps2.settings
    st2.type = "HAIR"
    st2.count = 60000
    st2.hair_length = 0.35
    st2.use_advanced_hair = True
    st2.normal_factor = 0.03
    st2.tangent_factor = 0.3
    st2.phase_factor_random = 2.0
    st2.rotation_mode = "NOR"
    st2.use_rotations = True
    st2.rotation_factor_random = 1.0
    st2.factor_random = 0.12
    st2.material_slot = "stubble"
    st2.root_radius = 0.0025
    st2.tip_radius = 0.0015
    st2.brownian_factor = 0.08
    return g
