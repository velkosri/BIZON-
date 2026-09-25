"""Bizon Super Z056 (FMŻ Płock, 1976-94) with 4.2 m grain header, built from scratch.

Run: blender -b --python model.py -- <texdir> <out.blend>
Blender world: +X = left side of the machine, -Y = forward, +Z = up (metres)."""
import json
import math
import os
import random
import sys

import bpy
from mathutils import Vector, Matrix, Euler

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kit  # noqa: E402
from kit import (Mesh, node, MATS, CTX, v3, make_material, box_uv, rect_uv, cyl_uv, catmull, sag,  # noqa: E402
                 belt_outline, aim_matrix, TAU)

argv = sys.argv[sys.argv.index('--') + 1:]
TEX = os.path.abspath(argv[0])
OUT = os.path.abspath(argv[1])
ATLAS = json.load(open(os.path.join(TEX, 'atlas.json')))
R = random.Random(56)
rad = math.radians

bpy.ops.wm.read_factory_settings(use_empty=True)


# ================================================================ materials
def T(name, n=True, s=True):
    d = {'diffuse': os.path.join(TEX, name + '_diffuse.png')}
    if n:
        d['normal'] = os.path.join(TEX, name + '_normal.png')
    if s:
        d['specular'] = os.path.join(TEX, name + '_specular.png')
    return d


def materials():
    mk = make_material
    mk('paint_red', T('paint_red'), (0.33, 0.02, 0.015, 1), 0.45, game={'tile': 1.6})
    mk('paint_white', T('paint_white'), (0.66, 0.64, 0.56, 1), 0.45, game={'tile': 1.2})
    mk('paint_black', T('paint_black'), (0.015, 0.015, 0.014, 1), 0.55, game={'tile': 1.0})
    mk('paint_orange', T('paint_orange'), (0.66, 0.11, 0.01, 1), 0.5, game={'tile': 1.0})
    mk('metal', T('metal_worn'), (0.23, 0.22, 0.21, 1), 0.4, 0.9, game={'tile': 0.8})
    mk('galv', T('galvanized'), (0.4, 0.41, 0.4, 1), 0.4, 0.85, game={'tile': 0.5})
    mk('rubber', T('rubber'), (0.01, 0.01, 0.01, 1), 0.8, game={'tile': 0.8})
    mk('rust', T('heat_rust'), (0.17, 0.06, 0.02, 1), 0.8, game={'tile': 0.8})
    mk('tread', T('tread_plate'), (0.12, 0.12, 0.11, 1), 0.5, 0.6, game={'tile': 0.6})
    mk('seat', T('seat_vinyl'), (0.016, 0.013, 0.011, 1), 0.55, game={'tile': 0.5})
    mk('crate', T('crate_red'), (0.33, 0.01, 0.01, 1), 0.45, game={'tile': 0.5})
    mk('plastic', T('plastic_black'), (0.007, 0.007, 0.007, 1), 0.55, game={'tile': 0.5})
    mk('chrome', None, (0.75, 0.75, 0.74, 1), 0.08, 1.0)
    mk('glass', None, (0.07, 0.08, 0.075, 1), 0.03, 0.0, alpha=0.3, game={'alpha': True})
    mk('lens_clear', None, (0.85, 0.85, 0.82, 1), 0.03, transmission=0.9)
    mk('lens_amber', None, (1.0, 0.32, 0.0, 1), 0.05, transmission=0.6)
    mk('lens_red', None, (0.55, 0.01, 0.005, 1), 0.05, transmission=0.6)
    mk('lit_white', None, (1.0, 0.95, 0.85, 1), 0.1, emission=(1.0, 0.92, 0.78, 25.0), game={'emissive': True})
    mk('lit_amber', None, (1.0, 0.45, 0.02, 1), 0.1, emission=(1.0, 0.4, 0.02, 25.0), game={'emissive': True})
    mk('lit_red', None, (0.9, 0.03, 0.01, 1), 0.1, emission=(1.0, 0.02, 0.01, 25.0), game={'emissive': True})
    mk('bottle', None, (0.16, 0.06, 0.01, 1), 0.04, transmission=0.85, ior=1.5)
    mk('beer', None, (0.5, 0.22, 0.02, 1), 0.1, transmission=0.8, ior=1.33)
    mk('gold', None, (0.72, 0.52, 0.2, 1), 0.3, 1.0)
    mk('decal', {'diffuse': os.path.join(TEX, 'decals_diffuse.png'), 'alpha': True}, (1, 1, 1, 1), 0.4,
       game={'alpha': True, 'decal': True})
    mk('dark', None, (0.012, 0.011, 0.01, 1), 0.9)
    mk('red_gloss', None, (0.42, 0.01, 0.008, 1), 0.25)
    mk('green', None, (0.05, 0.12, 0.04, 1), 0.45)
    mk('wood', None, (0.25, 0.15, 0.07, 1), 0.75)
    mk('copper', None, (0.7, 0.35, 0.2, 1), 0.35, 1.0)
    mk('yellow', None, (0.8, 0.55, 0.02, 1), 0.4)


# ================================================================ small parts
def bolt_heads(m, pts, normal, r=0.009, h=0.007):
    n = v3(normal).normalized()
    for p in pts:
        p = v3(p)
        m.cyl(p, p + n * h, r, seg=6)


def bolts_along(m, p0, p1, count, normal, r=0.009):
    p0, p1 = v3(p0), v3(p1)
    bolt_heads(m, [p0.lerp(p1, (i + 0.5) / count) for i in range(count)], normal, r)


def flange_bearing(m, c, axis, r=0.07):
    c, ax = v3(c), v3(axis).normalized()
    q = Vector((0, 0, 1)).rotation_difference(ax)
    rot = q.to_matrix()
    m.box(c, (r * 2, r * 2, 0.018), bevel=0.012, rot=rot)
    m.cyl(c, c + ax * 0.045, r * 0.55, seg=16)
    m.cyl(c + ax * 0.045, c + ax * 0.06, r * 0.3, seg=12)
    for sx in (-1, 1):
        for sy in (-1, 1):
            p = c + rot @ Vector((sx * r * 0.7, sy * r * 0.7, 0.009))
            m.cyl(p, p + ax * 0.012, 0.009, seg=6)
    # grease nipple
    g = c + ax * 0.03 + rot @ Vector((0, r * 0.55, 0))
    m.cyl(g, g + rot @ Vector((0, 0.025, 0)), 0.005, seg=6)


def pulley(m, c, r, width=0.04, grooves=1, spokes=5, hub_r=0.045):
    """V-belt pulley, axis along X, centre c."""
    c = v3(c)
    w = width * grooves
    prof = [(hub_r, -w / 2 - 0.02), (r - 0.025, -w / 2 + 0.003)]
    x = -w / 2
    for g in range(grooves):
        prof += [(r, x), (r, x + 0.004), (r - width * 0.35, x + width / 2), (r, x + width - 0.004), (r, x + width)]
        x += width
    prof += [(r - 0.025, w / 2 - 0.003), (hub_r, w / 2 + 0.02)]
    rim_in = r - 0.03
    # outer ring as lathe (open), inner web/spokes
    m.lathe([(rim_in, -w / 2)] + prof[1:-1] + [(rim_in, w / 2)], 32, c, axis=(1, 0, 0))
    m.lathe([(rim_in, w / 2), (rim_in, -w / 2)], 32, c, axis=(1, 0, 0))
    m.cyl(c - Vector((w / 2 + 0.02, 0, 0)), c + Vector((w / 2 + 0.02, 0, 0)), hub_r, seg=16)
    if spokes:
        for i in range(spokes):
            a = TAU * i / spokes
            d = Vector((0, math.cos(a), math.sin(a)))
            p0, p1 = c + d * hub_r * 0.9, c + d * (rim_in + 0.005)
            m.box((p0 + p1) / 2, (0.016, (p1 - p0).length, 0.03),
                  rot=Vector((0, 1, 0)).rotation_difference(d).to_matrix())
    else:
        m.cyl(c - Vector((0.006, 0, 0)), c + Vector((0.006, 0, 0)), rim_in, seg=32)
    # key/bolt on hub
    m.cyl(c + Vector((w / 2 + 0.02, 0, 0)), c + Vector((w / 2 + 0.035, 0, 0)), hub_r * 0.55, seg=6)


def belt(m, x, c1, r1, c2, r2, w=0.022, t=0.012):
    pts = belt_outline(c1, r1 + t / 2, c2, r2 + t / 2)
    n = len(pts)
    bm = m.bm
    rings = []
    for i, (y, z) in enumerate(pts):
        y0, z0 = pts[i - 1]
        y2, z2 = pts[(i + 1) % n]
        ty, tz = y2 - y0, z2 - z0
        ln = math.hypot(ty, tz) or 1
        ny, nz = tz / ln, -ty / ln   # outward for CCW loop
        ring = []
        for dx, dr in ((-w / 2, -t / 2), (w / 2, -t / 2), (w / 2, t / 2), (-w / 2, t / 2)):
            ring.append(bm.verts.new((x + dx, y + ny * dr, z + nz * dr)))
        rings.append(ring)
    for i in range(n):
        a, b = rings[i], rings[(i + 1) % n]
        for k in range(4):
            l = (k + 1) % 4
            bm.faces.new((a[k], a[l], b[l], b[k]))


def hose(pts, r, mat='rubber', name='hose', per=6, parent=None, fittings=True):
    m = Mesh()
    path = catmull(pts, per)
    m.tube(path, r, seg=8)
    ob = m.done(name, mat, parent=parent)
    if fittings:
        f = Mesh()
        for a, b in ((path[0], path[1]), (path[-1], path[-2])):
            d = (b - a).normalized()
            f.cyl(a - d * 0.01, a + d * 0.035, r * 1.45, seg=6)
        f.done(name + '_fit', 'galv', parent=parent)
    return ob


def cable(pts, r=0.006, name='cable', per=5, parent=None, mat='plastic', clips=True):
    m = Mesh()
    path = catmull(pts, per)
    m.tube(path, r, seg=6, caps=False)
    ob = m.done(name, mat, parent=parent)
    if clips:
        c = Mesh()
        for i in range(0, len(path) - 1, max(3, per * 2)):
            p = path[i]
            d = (path[i + 1] - p).normalized()
            c.cyl(p - d * 0.008, p + d * 0.008, r * 1.9, seg=6)
        c.done(name + '_clips', 'galv', parent=parent)
    return ob


def decal_plane(name, center, u_axis, v_axis, size, region, parent=None, offset=0.002, mat='decal'):
    c, au, av = v3(center), v3(u_axis).normalized(), v3(v_axis).normalized()
    n = au.cross(av).normalized()
    c = c + n * offset
    m = Mesh()
    bm = m.bm
    hw, hh = size[0] / 2, size[1] / 2
    vs = [bm.verts.new(c + au * sx * hw + av * sy * hh) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    bm.faces.new(vs)
    ob = m.done_raw(name, mat, parent=parent, smooth=0)
    rect_uv(ob, ATLAS[region], au, av, c, size)
    return ob


def sheet_panel(m, p0, p1, normal_axis, thick=0.004, bevel=0.006):
    """Thin rectangular sheet (box) with rolled edges."""
    m.boxp(p0, p1, bevel=bevel)


def louvres(m, x, y0, y1, z0, z1, count, out_sign=1, depth=0.05):
    for i in range(count):
        z = z0 + (z1 - z0) * (i + 0.5) / count
        rot = Euler((rad(-35 * out_sign), 0, 0)).to_matrix()
        rot = Matrix.Rotation(rad(35), 3, 'Y') if False else rot
        m.box((x, (y0 + y1) / 2, z), (0.004, y1 - y0, (z1 - z0) / count * 1.25),
              rot=Matrix.Rotation(rad(40 * out_sign), 3, 'Y'))


def wire_grid(m, p0, u, v, nu, nv, r=0.0025):
    p0, u, v = v3(p0), v3(u), v3(v)
    for i in range(nu + 1):
        a = p0 + u * (i / nu)
        m.box(a + v / 2, (r * 2, r * 2, r * 2), rot=None) if False else None
        m.cyl(a, a + v, r, seg=4, cap=False)
    for j in range(nv + 1):
        a = p0 + v * (j / nv)
        m.cyl(a, a + u, r, seg=4, cap=False)


# ================================================================ tyres & rims
def tyre_agri(m, c, R, W, rim_r, lugs=22, lug_h=0.05, angle=0.32):
    """R-1 bar tyre, axis X, centre c."""
    c = v3(c)
    hw = W / 2
    core = R - lug_h
    prof = [(rim_r + 0.01, -hw * 0.82), (rim_r + 0.05, -hw * 0.95), (core - 0.18, -hw * 1.02),
            (core - 0.06, -hw * 0.99), (core - 0.01, -hw * 0.9), (core, -hw * 0.7), (core, 0),
            (core, hw * 0.7), (core - 0.01, hw * 0.9), (core - 0.06, hw * 0.99), (core - 0.18, hw * 1.02),
            (rim_r + 0.05, hw * 0.95), (rim_r + 0.01, hw * 0.82)]
    m.lathe(prof, 64, c, axis=(1, 0, 0))
    dth = lug_h * 0.9 / R
    for side in (-1, 1):
        for i in range(lugs):
            th0 = TAU * i / lugs + (0 if side > 0 else math.pi / lugs)
            segs = 3
            for s in range(segs):
                x_a = side * (0.03 + (hw - 0.02) * s / segs)
                x_b = side * (0.03 + (hw - 0.02) * (s + 1) / segs)
                ta = th0 + angle * (abs(x_a) / hw)
                tb = th0 + angle * (abs(x_b) / hw)
                pts = []
                for x, t in ((x_a, ta), (x_b, tb)):
                    for rr, ww in ((core - 0.004, dth * 1.25), (R, dth * 0.9)):
                        for sgn in (-1, 1):
                            a = t + sgn * ww
                            drop = 0.012 * (abs(x) / hw) ** 2
                            pts.append(c + Vector((x, math.cos(a) * (rr - drop), math.sin(a) * (rr - drop))))
                m.hull(pts)


def tyre_ribbed(m, c, R, W, rim_r, ribs=4):
    c = v3(c)
    hw = W / 2
    prof = [(rim_r + 0.01, -hw * 0.8), (rim_r + 0.04, -hw * 0.95), (R - 0.07, -hw * 1.02), (R - 0.02, -hw * 0.92)]
    xs = [-hw * 0.85 + i * (hw * 1.7) / (ribs * 2 - 1) for i in range(ribs * 2)]
    for i, x in enumerate(xs):
        prof.append((R if i % 2 == 0 else R - 0.02, x))
        prof.append((R if i % 2 == 0 else R - 0.02, x + (hw * 1.7) / (ribs * 2 - 1) * 0.85))
    prof += [(R - 0.02, hw * 0.92), (R - 0.07, hw * 1.02), (rim_r + 0.04, hw * 0.95), (rim_r + 0.01, hw * 0.8)]
    m.lathe(prof, 56, c, axis=(1, 0, 0))


def rim(m_rim, m_bolt, c, rim_r, W, side, holes=8, disc_off=0.0):
    """Steel agricultural rim, disc on the outer side (side=+1 left, -1 right)."""
    c = v3(c)
    hw = W / 2 * 0.86
    prof = [(rim_r + 0.022, -hw - 0.012), (rim_r + 0.012, -hw), (rim_r, -hw + 0.02), (rim_r - 0.012, -hw * 0.3),
            (rim_r - 0.02, 0), (rim_r - 0.012, hw * 0.3), (rim_r, hw - 0.02), (rim_r + 0.012, hw),
            (rim_r + 0.022, hw + 0.012)]
    m_rim.lathe(prof, 48, c, axis=(1, 0, 0))
    m_rim.lathe(list(reversed([(r - 0.008, x) for r, x in prof])), 48, c, axis=(1, 0, 0))
    dx = side * (hw * 0.25 + disc_off)
    dc = c + Vector((dx, 0, 0))
    disc = [(rim_r - 0.02, -0.006), (rim_r * 0.72, -0.006), (rim_r * 0.52, -0.03 * side), (rim_r * 0.3, -0.03 * side),
            (0.02, -0.03 * side), (0.02, -0.018 * side), (rim_r * 0.3, -0.018 * side), (rim_r * 0.52, -0.018 * side),
            (rim_r * 0.72, 0.006), (rim_r - 0.02, 0.006)]
    m_rim.lathe(disc, 48, dc, axis=(1, 0, 0))
    hub_x = dc + Vector((side * 0.03, 0, 0))
    m_rim.cyl(hub_x, hub_x + Vector((side * 0.11, 0, 0)), rim_r * 0.24, seg=20)
    m_rim.cyl(hub_x + Vector((side * 0.11, 0, 0)), hub_x + Vector((side * 0.14, 0, 0)), rim_r * 0.12, seg=16)
    for i in range(holes):
        a = TAU * i / holes
        p = hub_x + Vector((0, math.cos(a) * rim_r * 0.36, math.sin(a) * rim_r * 0.36))
        m_bolt.cyl(p, p + Vector((side * 0.022, 0, 0)), 0.013, seg=6)
        m_bolt.cyl(p, p + Vector((side * 0.035, 0, 0)), 0.006, seg=6)
        q = dc + Vector((side * 0.0, math.cos(a + math.pi / holes) * rim_r * 0.62, math.sin(a + math.pi / holes) * rim_r * 0.62))
        m_rim.cyl(q - Vector((0.01, 0, 0)), q + Vector((0.01, 0, 0)), rim_r * 0.08, seg=12, cap=True)
    # valve
    p = c + Vector((side * hw * 0.5, 0, rim_r - 0.01))
    m_bolt.cyl(p, p + Vector((side * 0.02, 0, 0.03)), 0.005, seg=6)


# ================================================================ combine
FW = dict(R=0.745, W=0.47, X=1.365, Z=0.725, rim=0.335)
RW = dict(R=0.43, W=0.26, X=1.00, Y=3.55, Z=0.425, rim=0.196)
FEED_PIVOT = Vector((0, -0.95, 1.42))
FEED_FRONT = Vector((0, -2.40, 0.72))


def body_lower(root):
    CTX['parent'] = root
    red = Mesh()
    # side walls with rolled edges and a stiffening bead
    for sx in (-1, 1):
        x = 0.81 * sx
        red.boxp((x - 0.004, -0.95, 0.62), (x + 0.004, 2.70, 2.16), bevel=0.003)
        for z in (1.05, 1.95):
            red.box((x + 0.006 * sx, 0.9, z), (0.012, 3.3, 0.035), bevel=0.01, seg=2)
        for y in (-0.5, 0.55, 1.35, 2.25):
            red.box((x + 0.007 * sx, y, 1.4), (0.014, 0.05, 1.45), bevel=0.012, seg=2)
        # inspection door with hinges & latch
        red.boxp((x + 0.004 * sx, 2.02, 0.72), (x + 0.018 * sx, 2.55, 1.02), bevel=0.008)
    red.boxp((-0.81, -0.95, 0.62), (0.81, 2.70, 0.66), bevel=0.01)      # sieve pan bottom
    red.boxp((-0.81, -0.97, 1.62), (0.81, -0.93, 2.14), bevel=0.01)    # front wall above feeder
    red.boxp((-0.81, 2.66, 0.62), (0.81, 2.70, 2.16), bevel=0.01)      # rear bulkhead
    # mounting frame rails under the top block
    red.boxp((-0.84, -0.9, 2.08), (-0.78, 2.9, 2.16), bevel=0.01)
    red.boxp((0.78, -0.9, 2.08), (0.84, 2.9, 2.16), bevel=0.01)
    red.done('body_lower', 'paint_red')
    b = Mesh()
    for sx in (-1, 1):
        x = 0.81 * sx
        bolts_along(b, (x + 0.014 * sx, -0.9, 1.05), (x + 0.014 * sx, 2.6, 1.05), 22, (sx, 0, 0))
        bolts_along(b, (x + 0.014 * sx, -0.9, 1.95), (x + 0.014 * sx, 2.6, 1.95), 22, (sx, 0, 0))
        for y in (2.04, 2.53):
            b.cyl((x + 0.018 * sx, y, 0.76), (x + 0.018 * sx, y, 0.98), 0.009, seg=8)
        b.box((x + 0.024 * sx, 2.285, 1.0), (0.02, 0.06, 0.03), bevel=0.005)
    b.done('body_bolts', 'paint_red')
    # front axle with final drive housings (black, cast)
    blk = Mesh()
    blk.cyl((-1.02, 0.0, FW['Z']), (1.02, 0.0, FW['Z']), 0.085, seg=20)
    for sx in (-1, 1):
        x = sx * 0.98
        blk.box((x, 0.0, FW['Z'] + 0.12), (0.2, 0.46, 0.5), bevel=0.06, seg=3)
        blk.cyl((x, 0.0, FW['Z']), (sx * 1.1, 0.0, FW['Z']), 0.2, seg=24)
        blk.cyl((sx * 0.86, 0.0, FW['Z'] + 0.12), (sx * 0.88, 0.0, FW['Z'] + 0.12), 0.26, seg=24)
        for i in range(10):
            a = TAU * i / 10
            p = Vector((sx * 1.1, 0.2 * 0.8 * math.cos(a), FW['Z'] + 0.2 * 0.8 * math.sin(a)))
            blk.cyl(p, p + Vector((sx * 0.015, 0, 0)), 0.011, seg=6)
        # brake drum & brake cylinder
        blk.cyl((sx * 0.84, -0.25, FW['Z'] + 0.02), (sx * 0.84, -0.25, FW['Z'] + 0.3), 0.035, seg=12)
        blk.box((sx * 0.8, 0.0, FW['Z'] + 0.43), (0.08, 0.3, 0.14), bevel=0.02)
    # gearbox between the axles (cast, with filler plug)
    blk.box((0.25, 0.08, FW['Z'] + 0.12), (0.5, 0.42, 0.45), bevel=0.05, seg=3)
    blk.cyl((0.25, 0.08, FW['Z'] + 0.35), (0.25, 0.08, FW['Z'] + 0.4), 0.03, seg=6)
    # longitudinal chassis beams under the sieve pan
    for sx in (-1, 1):
        blk.boxp((sx * 0.6 - 0.05, -0.5, 0.5), (sx * 0.6 + 0.05, 3.9, 0.62), bevel=0.012)
    blk.boxp((-0.65, 3.45, 0.5), (0.65, 3.65, 0.64), bevel=0.02)
    blk.done('axle_front', 'paint_black')
    # dark inner cavity visible through gaps
    d = Mesh()
    d.boxp((-0.79, -0.93, 0.68), (0.79, 2.64, 2.12))
    d.done('body_cavity', 'dark', smooth=0)


def top_block(root):
    """Grain tank (front) + engine enclosure (rear): the tall block of the Z056."""
    CTX['parent'] = root
    x0, x1, y0, y1, z0, z1 = -1.32, 1.32, -0.05, 2.95, 2.15, 3.58
    red = Mesh()
    red.boxp((x0, y0, z0), (x1, 1.40, z1), bevel=0.05, seg=3)     # tank
    red.boxp((x0, 1.42, z0), (x1, y1, z1), bevel=0.05, seg=3)     # engine enclosure
    red.boxp((x0 - 0.012, 1.385, z0 + 0.02), (x1 + 0.012, 1.435, z1 + 0.012), bevel=0.012)  # joint flange
    for sx in (-1, 1):
        x = sx * 1.32
        for z in (2.62, 3.12):
            red.box((x + 0.006 * sx, 0.67, z), (0.012, 1.3, 0.04), bevel=0.012, seg=2)
        red.box((x + 0.006 * sx, 0.67, 2.2), (0.012, 1.38, 0.05), bevel=0.012, seg=2)
    # tank funnel down to the body
    for sx in (-1, 1):
        red.hull([(sx * 0.8, y0 + 0.1, 2.16), (sx * 0.8, 1.35, 2.16), (sx * 1.3, y0 + 0.1, 2.16), (sx * 1.3, 1.35, 2.16),
                  (sx * 0.8, y0 + 0.1, 1.98), (sx * 0.8, 1.35, 1.98), (sx * 0.84, y0 + 0.1, 2.0), (sx * 0.84, 1.35, 2.0)])
    # roof: tank lid with hinges & handle, crown bead
    red.boxp((-1.0, 0.12, z1 - 0.01), (1.0, 1.25, z1 + 0.03), bevel=0.015)
    red.boxp((-0.35, 0.08, z1 + 0.02), (0.35, 0.14, z1 + 0.06), bevel=0.01)
    # pipe cradle on the rear-left corner
    red.boxp((1.30, 2.84, 2.95), (1.46, 2.92, 3.02), bevel=0.01)
    red.boxp((1.44, 2.84, 2.95), (1.47, 2.92, 3.16), bevel=0.008)
    red.done('top_block', 'paint_red')
    b = Mesh()
    for sx in (-1, 1):
        x = sx * 1.332
        bolts_along(b, (x, 1.41, 2.25), (x, 1.41, 3.5), 12, (sx, 0, 0))
        bolts_along(b, (x, 0.05, 2.2), (x, 1.3, 2.2), 10, (sx, 0, 0))
    bolts_along(b, (-1.2, 1.41, 3.595), (1.2, 1.41, 3.595), 18, (0, 0, 1))
    for x in (-0.8, 0.8):
        b.cyl((x, 1.21, z1 + 0.03), (x, 1.29, z1 + 0.03), 0.02, seg=10)
    b.done('top_bolts', 'galv')
    # front: grain sight glass & sample hatch, facing the cab
    g = Mesh()
    g.boxp((-0.35, y0 - 0.02, 2.75), (0.05, y0, 3.05), bevel=0.01)
    g.done('tank_window_frame', 'paint_black')
    gl = Mesh()
    gl.boxp((-0.33, y0 - 0.025, 2.77), (0.03, y0 - 0.018, 3.03))
    gl.done('tank_window', 'glass', own=1)
    grain = Mesh()
    grain.boxp((-0.32, y0 - 0.015, 2.78), (0.02, y0 - 0.01, 2.9))
    grain.done('tank_window_grain', 'yellow')
    # decals: BIZON on both sides of the tank, nameplate, warning, Tyskie
    decal_plane('decal_bizon_L', (1.325, 0.62, 3.3), (0, 1, 0), (0, 0, 1), (0.9, 0.27), 'bizon')
    decal_plane('decal_bizon_R', (-1.325, 0.62, 3.3), (0, -1, 0), (0, 0, 1), (0.9, 0.27), 'bizon')
    decal_plane('decal_warning_L', (1.325, 2.15, 2.28), (0, 1, 0), (0, 0, 1), (0.36, 0.11), 'warning')
    decal_plane('decal_tyskie_front', (0.62, y0 - 0.001, 3.08), (-1, 0, 0), (0, 0, 1), (0.62, 0.285), 'tyskie_big')
    decal_plane('decal_plate', (-0.85, y0 - 0.001, 2.45), (-1, 0, 0), (0, 0, 1), (0.2, 0.117), 'plate')


def engine_bay(root):
    CTX['parent'] = root
    # left: louvres + mesh window, see-through to the engine
    fr = Mesh()
    fr.boxp((1.318, 1.55, 2.38), (1.34, 2.85, 2.42), bevel=0.006)
    fr.boxp((1.318, 1.55, 3.38), (1.34, 2.85, 3.42), bevel=0.006)
    fr.boxp((1.318, 1.53, 2.38), (1.34, 1.57, 3.42), bevel=0.006)
    fr.boxp((1.318, 2.83, 2.38), (1.34, 2.87, 3.42), bevel=0.006)
    fr.boxp((1.318, 2.18, 2.4), (1.34, 2.22, 3.4), bevel=0.006)
    for i in range(13):
        z = 2.44 + i * 0.073
        fr.box((1.33, 1.87, z), (0.004, 0.6, 0.075), rot=Matrix.Rotation(rad(-38), 3, 'Y'))
    fr.done('louvres', 'paint_red')
    mesh = Mesh()
    wire_grid(mesh, (1.332, 2.22, 2.42), (0, 0.61, 0), (0, 0, 0.96), 40, 64, r=0.0022)
    mesh.done('engine_mesh_L', 'paint_black', smooth=0)
    # dark cavity behind (engine bay walls)
    cav = Mesh()
    cav.boxp((-1.3, 1.46, 2.18), (1.3, 2.93, 3.55))
    cav.done('engine_cavity', 'dark', smooth=0)
    engine(root)
    # right: radiator with rotary screen (screen spins with the engine)
    rh = Mesh()
    rh.lathe([(0.47, 0.0), (0.47, 0.06), (0.44, 0.08), (0.41, 0.08), (0.41, 0.0)], 40, (-1.32, 2.33, 2.93), axis=(-1, 0, 0))
    rh.boxp((-1.34, 1.8, 2.36), (-1.32, 2.86, 3.46), bevel=0.01)
    rh.done('radiator_housing', 'paint_red')
    scr_node = node('rotaryScreen', (-1.42, 2.33, 2.93), root)
    CTX['parent'] = scr_node
    s = Mesh()
    s.cyl((-1.40, 2.33, 2.93), (-1.46, 2.33, 2.93), 0.4, seg=40, cap=False)
    for i in range(8):
        a = TAU * i / 8
        d = Vector((0, math.cos(a), math.sin(a)))
        s.box(Vector((-1.46, 2.33, 2.93)) + d * 0.2, (0.012, 0.4, 0.03),
              rot=Vector((0, 1, 0)).rotation_difference(d).to_matrix())
    s.cyl((-1.40, 2.33, 2.93), (-1.49, 2.33, 2.93), 0.06, seg=16)
    s.done('rotary_screen_frame', 'paint_black')
    sm = Mesh()
    for k in range(-13, 14):
        z = 2.93 + k * 0.029
        hw = math.sqrt(max(0, 0.39 ** 2 - (k * 0.029) ** 2))
        sm.cyl((-1.458, 2.33 - hw, z), (-1.458, 2.33 + hw, z), 0.0022, seg=4, cap=False)
        y = 2.33 + k * 0.029
        sm.cyl((-1.456, y, 2.93 - hw), (-1.456, y, 2.93 + hw), 0.0022, seg=4, cap=False)
    sm.done('rotary_screen_mesh', 'galv', smooth=0)
    CTX['parent'] = root
    core = Mesh()
    core.boxp((-1.31, 1.95, 2.5), (-1.25, 2.72, 3.36), bevel=0.005)
    core.done('radiator_core', 'dark', smooth=0)
    # roof mesh over the engine, muffler, air filter
    rm = Mesh()
    rm.boxp((-0.9, 1.62, 3.575), (0.9, 1.66, 3.6), bevel=0.005)
    rm.boxp((-0.9, 2.74, 3.575), (0.9, 2.78, 3.6), bevel=0.005)
    rm.done('roof_grille_frame', 'paint_red')
    rmm = Mesh()
    wire_grid(rmm, (-0.88, 1.66, 3.592), (1.76, 0, 0), (0, 1.08, 0), 60, 36, r=0.002)
    rmm.done('roof_grille', 'paint_black', smooth=0)
    shake = node('engineShakeA', (0.62, 2.45, 3.85), root)
    shake2 = node('engineShakeB', (0.6212, 2.45, 3.85), shake)
    CTX['parent'] = shake2
    mf = Mesh()
    mf.lathe([(0.0, 2.0), (0.06, 2.0), (0.112, 2.03), (0.115, 2.06), (0.115, 2.84), (0.112, 2.87), (0.06, 2.9), (0.0, 2.9)],
             28, (0.62, 0, 3.84), axis=(0, 1, 0))
    mf.cyl((0.62, 2.4, 3.58), (0.62, 2.4, 3.76), 0.045, seg=14)
    mf.cyl((0.62, 2.9, 3.84), (0.62, 2.96, 3.84), 0.04, seg=14)
    mf.tube([(0.62, 2.95, 3.84), (0.62, 3.0, 3.86), (0.62, 3.02, 3.92), (0.62, 3.02, 4.08)], 0.04, seg=14)
    mf.done('muffler', 'rust')
    cl = Mesh()
    for y in (2.15, 2.72):
        cl.lathe([(0.118, -0.02), (0.125, -0.02), (0.125, 0.02), (0.118, 0.02)], 28, (0.62, y, 3.84), axis=(0, 1, 0))
        cl.boxp((0.6, y - 0.02, 3.58), (0.64, y + 0.02, 3.72), bevel=0.005)
    cl.done('muffler_clamps', 'paint_black')
    flap_node = node('exhaustFlap', (0.62, 2.98, 4.085), shake2)
    CTX['parent'] = flap_node
    fl = Mesh()
    fl.lathe([(0.0, 0.0), (0.05, 0.0), (0.05, 0.004), (0.0, 0.004)], 16, (0.62, 3.02, 4.087), axis=(0, 0, 1))
    fl.cyl((0.58, 2.98, 4.085), (0.66, 2.98, 4.085), 0.006, seg=8)
    fl.done('exhaust_flap', 'rust')
    CTX['parent'] = shake2
    af = Mesh()
    af.lathe([(0.0, 3.58), (0.14, 3.58), (0.145, 3.6), (0.145, 3.9), (0.13, 3.92), (0.06, 3.94), (0.06, 4.0),
              (0.1, 4.02), (0.1, 4.1), (0.05, 4.14), (0.0, 4.15)], 28, (-0.55, 2.25, 0), axis=(0, 0, 1))
    af.done('air_filter', 'paint_black')
    afb = Mesh()
    afb.lathe([(0.0, 4.0), (0.095, 4.0), (0.095, 4.09), (0.0, 4.09)], 24, (-0.55, 2.25, 0), axis=(0, 0, 1))
    afb.done('air_precleaner_bowl', 'glass', own=1)
    for i, (a, b) in enumerate((((-0.55, 2.25, 3.62), (-0.55, 2.1, 3.62)),)):
        pass
    CTX['parent'] = root
    node('exhaustNode', (0.62, 3.02, 4.12), root)


def engine(root):
    """SW-400 inline six, transverse, visible through the louvres and roof grille."""
    CTX['parent'] = node('engineShakeC', (0, 2.3, 2.85), root)
    CTX['parent'] = node('engineShakeD', (0.0012, 2.3, 2.85), CTX['parent'])
    par = CTX['parent']
    e = Mesh()
    e.boxp((-0.52, 2.12, 2.45), (0.5, 2.5, 2.95), bevel=0.03, seg=2)
    e.boxp((-0.5, 2.14, 2.95), (0.48, 2.46, 3.08), bevel=0.02)
    for i in range(6):
        x = -0.42 + i * 0.165
        e.boxp((x - 0.07, 2.16, 3.08), (x + 0.07, 2.44, 3.18), bevel=0.02)
        e.cyl((x, 2.3, 3.18), (x, 2.3, 3.2), 0.018, seg=6)
        e.cyl((x, 2.12, 3.02), (x, 2.02, 3.02), 0.03, seg=10)   # intake runners
        e.cyl((x, 2.48, 3.0), (x, 2.58, 3.02), 0.035, seg=10)   # exhaust ports
    e.cyl((-0.48, 2.02, 3.02), (0.46, 2.02, 3.02), 0.05, seg=14)   # intake manifold
    e.cyl((-0.48, 2.6, 3.02), (0.46, 2.6, 3.02), 0.055, seg=14)    # exhaust manifold
    e.tube([(0.46, 2.6, 3.02), (0.55, 2.55, 3.1), (0.62, 2.45, 3.3), (0.62, 2.4, 3.58)], 0.045, seg=12)
    e.boxp((-0.46, 2.18, 2.3), (0.46, 2.46, 2.45), bevel=0.02)     # sump
    e.lathe([(0.0, 0.0), (0.3, 0.0), (0.3, 0.12), (0.0, 0.12)], 36, (0.5, 2.3, 2.72), axis=(1, 0, 0))  # flywheel housing
    e.boxp((-0.2, 1.96, 2.55), (0.2, 2.12, 2.8), bevel=0.02)       # injection pump
    e.cyl((-0.25, 2.0, 2.6), (-0.25, 2.0, 2.78), 0.04, seg=12)      # fuel filter
    e.cyl((0.3, 1.98, 2.62), (0.3, 1.98, 2.82), 0.05, seg=14)        # oil filter
    e.cyl((-0.66, 2.24, 2.62), (-0.52, 2.24, 2.62), 0.07, seg=18)     # water pump
    e.cyl((-0.6, 2.46, 2.86), (-0.45, 2.46, 2.86), 0.08, seg=18)      # alternator
    e.done('engine_block', 'paint_black')
    for i in range(6):
        x = -0.42 + i * 0.165
        cable([(x, 2.3, 3.2), (x, 2.2, 3.24), (-0.1 + i * 0.02, 2.0, 3.1), (0.0, 1.98, 2.8)], r=0.004,
              name='injector_line_%d' % i, mat='metal', clips=False)
    CTX['parent'] = root


def rear_hood(root):
    CTX['parent'] = root
    red = Mesh()
    yf, yr = 2.70, 4.95
    for sx in (-1, 1):
        x = sx * 0.84
        red.poly_prism([(yf, 0.98), (yr, 1.1), (yr, 2.46), (yf, 2.62)], (x, 0, 0), (0, 1, 0), (0, 0, 1), (-sx, 0, 0), 0.006,
                       bevel=0.003)
        red.box((x + sx * 0.008, 3.8, 1.5), (0.012, 2.2, 0.04), bevel=0.01, seg=2)
        red.box((x + sx * 0.008, 3.8, 2.1), (0.012, 2.2, 0.04), bevel=0.01, seg=2)
        red.boxp((x + sx * 0.004, 3.2, 1.62), (x + sx * 0.02, 3.8, 1.98), bevel=0.008)   # side door
    red.hull([(-0.85, yf, 2.62), (0.85, yf, 2.62), (-0.85, yr, 2.46), (0.85, yr, 2.46),
              (-0.85, yf, 2.58), (0.85, yf, 2.58), (-0.85, yr, 2.42), (0.85, yr, 2.42)])
    red.boxp((-0.85, yr - 0.006, 1.32), (0.85, yr, 2.46), bevel=0.004)
    red.boxp((-0.87, yr - 0.03, 1.28), (0.87, yr + 0.01, 1.34), bevel=0.01)          # rear bumper lip
    for y in (3.3, 4.1):
        red.hull([(-0.86, y - 0.02, 2.6 - (y - yf) * 0.07), (0.86, y - 0.02, 2.6 - (y - yf) * 0.07),
                  (-0.86, y + 0.02, 2.6 - (y - yf) * 0.07), (0.86, y + 0.02, 2.6 - (y - yf) * 0.07),
                  (-0.86, y - 0.02, 2.64 - (y - yf) * 0.07), (0.86, y - 0.02, 2.64 - (y - yf) * 0.07),
                  (-0.86, y + 0.02, 2.64 - (y - yf) * 0.07), (0.86, y + 0.02, 2.64 - (y - yf) * 0.07)])
    red.done('rear_hood', 'paint_red')
    dk = Mesh()
    dk.boxp((-0.83, 2.72, 1.0), (0.83, 4.9, 1.02))
    dk.boxp((-0.83, 4.2, 1.02), (0.83, 4.92, 2.4))
    dk.done('hood_cavity', 'dark', smooth=0)
    # straw walkers: 5 keyed walkers on two crank phases (animated while threshing)
    for i in range(5):
        x = -0.64 + i * 0.32
        wn = node('walker%d' % (i + 1), (x, 3.6, 1.35), root)
        CTX['parent'] = wn
        w = Mesh()
        for s in range(5):
            y0 = 2.95 + s * 0.38
            z0 = 1.15 + s * 0.04
            w.poly_prism([(y0, z0), (y0 + 0.38, z0 + 0.06), (y0 + 0.38, z0 + 0.14), (y0 + 0.36, z0 + 0.16), (y0, z0 + 0.1)],
                         (x - 0.14, 0, 0), (0, 1, 0), (0, 0, 1), (1, 0, 0), 0.004)
            w.poly_prism([(y0, z0), (y0 + 0.38, z0 + 0.06), (y0 + 0.38, z0 + 0.14), (y0 + 0.36, z0 + 0.16), (y0, z0 + 0.1)],
                         (x + 0.14, 0, 0), (0, 1, 0), (0, 0, 1), (-1, 0, 0), 0.004)
            for k in range(5):
                yy = y0 + 0.03 + k * 0.07
                w.hull([(x - 0.13, yy, z0 + 0.1), (x + 0.13, yy, z0 + 0.1), (x - 0.13, yy + 0.05, z0 + 0.105),
                        (x + 0.13, yy + 0.05, z0 + 0.105), (x - 0.13, yy + 0.05, z0 + 0.14), (x + 0.13, yy + 0.05, z0 + 0.14)])
        w.done('walker%d_mesh' % (i + 1), 'galv')
    CTX['parent'] = root
    # rear lamps, reflectors, triangle, number plate, work light
    lamps = Mesh()
    for sx in (-1, 1):
        lamps.boxp((sx * 0.62 - 0.11, yr, 1.38), (sx * 0.62 + 0.11, yr + 0.06, 1.52), bevel=0.012)
        lamps.boxp((sx * 0.62 - 0.02, yr - 0.02, 1.34), (sx * 0.62 + 0.02, yr + 0.02, 1.4))
    lamps.boxp((-0.18, yr, 1.62), (0.18, yr + 0.03, 1.74), bevel=0.006)
    lamps.done('rear_lamp_housings', 'plastic')
    lr = Mesh()
    la = Mesh()
    for sx in (-1, 1):
        lr.boxp((sx * 0.62 - 0.1, yr + 0.06, 1.39), (sx * 0.62 + 0.0 * sx - 0.0, yr + 0.066, 1.51), bevel=0.004) if sx > 0 else \
            lr.boxp((sx * 0.62 + 0.0, yr + 0.06, 1.39), (sx * 0.62 + 0.1, yr + 0.066, 1.51), bevel=0.004)
        la.boxp((sx * 0.62 - 0.0 if sx > 0 else sx * 0.62 - 0.1, yr + 0.06, 1.39),
                (sx * 0.62 + 0.1 if sx > 0 else sx * 0.62 - 0.0, yr + 0.066, 1.51), bevel=0.004)
    lr.done('rear_lens_red', 'lens_red')
    la.done('rear_lens_amber', 'lens_amber')
    decal_plane('decal_triangle', (0.0, yr + 0.002, 2.02), (-1, 0, 0), (0, 0, 1), (0.36, 0.31), 'triangle')
    decal_plane('decal_plate_rear', (0.0, yr + 0.032, 1.68), (-1, 0, 0), (0, 0, 1), (0.34, 0.078), 'plate_rear')
    decal_plane('decal_super_L', (0.845, 3.95, 2.26), (0, 1, 0), (0, 0, 1), (0.95, 0.16), 'super')
    decal_plane('decal_super_R', (-0.845, 3.95, 2.26), (0, -1, 0), (0, 0, 1), (0.95, 0.16), 'super')
    decal_plane('decal_tyskie_hood_L', (0.845, 4.45, 1.86), (0, 1, 0), (0, 0, 1), (0.56, 0.256), 'tyskie_big')
    decal_plane('decal_tyskie_rear', (-0.45, yr + 0.002, 2.1), (-1, 0, 0), (0, 0, 1), (0.42, 0.192), 'tyskie_big')
    for sx in (-1, 1):
        decal_plane('decal_refl_%d' % sx, (sx * 0.62, yr + 0.001, 1.25), (-1, 0, 0), (0, 0, 1), (0.08, 0.05), 'refl_red')
    # lit versions (toggled by the game)
    for key, mat, sx in (('tail', 'lit_red', 1), ('tail', 'lit_red', -1)):
        m = Mesh()
        x0 = sx * 0.62 - 0.1 if sx > 0 else sx * 0.62
        m.boxp((x0, yr + 0.067, 1.39), (x0 + 0.1, yr + 0.07, 1.51))
        m.done('lit_tail_%s' % ('L' if sx > 0 else 'R'), mat, own=1, hidden=1)
    for sx in (1, -1):
        m = Mesh()
        x0 = sx * 0.62 if sx > 0 else sx * 0.62 - 0.1
        m.boxp((x0, yr + 0.067, 1.39), (x0 + 0.1, yr + 0.07, 1.51))
        m.done('lit_turn_rear_%s' % ('L' if sx > 0 else 'R'), 'lit_amber', own=1, hidden=1)
    m = Mesh()
    for sx in (1, -1):
        x0 = sx * 0.62 - 0.1 if sx > 0 else sx * 0.62
        m.boxp((x0 + 0.02, yr + 0.071, 1.41), (x0 + 0.08, yr + 0.074, 1.49))
    m.done('lit_brake', 'lit_red', own=1, hidden=1)


def platform_cab(root):
    CTX['parent'] = root
    zf = 2.14
    t = Mesh()
    t.boxp((-0.95, -1.55, zf - 0.012), (1.52, -0.05, zf), bevel=0.004)
    for k in range(6):
        z = 0.42 + k * 0.29
        y = -1.95 + (z - 0.4) / (zf - 0.4) * 0.45
        t.boxp((1.4, y - 0.1, z - 0.01), (1.62, y + 0.1, z + 0.004), bevel=0.003)
    t.done('platform_tread', 'tread')
    fr = Mesh()
    fr.boxp((-0.97, -1.57, zf - 0.08), (1.54, -1.51, zf - 0.01), bevel=0.01)
    fr.boxp((1.48, -1.57, zf - 0.08), (1.54, -0.05, zf - 0.01), bevel=0.01)
    fr.boxp((-0.97, -1.57, zf - 0.08), (-0.91, -0.05, zf - 0.01), bevel=0.01)
    for y in (-1.2, -0.6):
        fr.boxp((-0.9, y - 0.03, zf - 0.07), (1.5, y + 0.03, zf - 0.012), bevel=0.008)
    # platform brackets down to the body
    for sx in (-1, 1):
        fr.hull([(sx * 0.8, -0.95, 1.7), (sx * 0.8, -0.85, 1.7), (sx * 0.8, -1.5, zf - 0.08), (sx * 0.8, -0.85, zf - 0.08),
                 (sx * 0.84, -0.95, 1.7), (sx * 0.84, -0.85, 1.7), (sx * 0.84, -1.5, zf - 0.08), (sx * 0.84, -0.85, zf - 0.08)])
    fr.done('platform_frame', 'paint_red')
    # ladder rails + handrails (orange like the originals' safety rails)
    lad = Mesh()
    for yo in (-0.11, 0.11):
        lad.tube([(1.44, -1.5 + yo, zf), (1.58, -1.95 + yo, 0.38)], 0.018, seg=8)
    for yo in (-0.13, 0.13):
        lad.tube(catmull([(1.58, -1.93 + yo, 0.9), (1.52, -1.78 + yo, 1.8), (1.5, -1.62 + yo, zf + 0.95),
                          (1.5, -1.4 + yo, zf + 1.02)], 5), 0.016, seg=8)
    lad.tube([(1.5, -1.3, zf + 1.02), (1.5, -0.1, zf + 1.02)], 0.016, seg=8)
    lad.tube([(1.5, -1.3, zf + 0.55), (1.5, -0.1, zf + 0.55)], 0.013, seg=8)
    for y in (-1.3, -0.7, -0.1):
        lad.cyl((1.5, y, zf), (1.5, y, zf + 1.02), 0.016, seg=8)
    lad.tube([(-0.93, -1.53, zf + 1.0), (-0.93, -0.1, zf + 1.0)], 0.016, seg=8)
    for y in (-1.53, -0.8, -0.1):
        lad.cyl((-0.93, y, zf), (-0.93, y, zf + 1.0), 0.016, seg=8)
    lad.done('ladder_rails', 'paint_orange')
    # hydraulic valve block under the platform with linkage to the levers
    vb = Mesh()
    vb.boxp((-0.72, -1.12, 1.84), (-0.3, -0.92, 2.02), bevel=0.012)
    for k in range(3):
        x = -0.66 + k * 0.13
        vb.boxp((x - 0.05, -1.14, 1.86), (x + 0.05, -0.9, 2.0), bevel=0.008)
        vb.cyl((x, -1.14, 1.93), (x, -1.22, 1.93), 0.012, seg=8)
        vb.tube([(x, -1.22, 1.93), (x, -1.26, 1.97), (x + 0.02, -1.3, 2.1)], 0.006, seg=6)
        for dz in (-0.03, 0.03):
            vb.cyl((x, -0.9, 1.93 + dz), (x, -0.86, 1.93 + dz), 0.014, seg=6)
    vb.done('valve_block', 'paint_black')
    for k in range(3):
        x = -0.66 + k * 0.13
        hose([(x, -0.86, 1.96), (x + 0.05, -0.7, 1.9), (x + 0.2, -0.6, 1.75), (0.1 + k * 0.2, -0.55, 1.35)], 0.009,
             name='hose_valve_%d' % k, parent=root)
    # engine access ladder on the right rear of the top block, roof hand rail
    rl = Mesh()
    for y in (2.64, 2.9):
        rl.beam((-1.36, y, 2.18), (-1.36, y, 3.62), 0.012, 0.04, up=(0, 1, 0))
    for k in range(5):
        rl.cyl((-1.37, 2.64, 2.4 + k * 0.25), (-1.37, 2.9, 2.4 + k * 0.25), 0.012, seg=8)
    rl.tube(catmull([(-1.36, 2.64, 3.6), (-1.3, 2.64, 3.95), (-1.1, 2.62, 3.98), (-1.05, 2.3, 3.98), (-1.05, 1.7, 3.98),
                     (-1.1, 1.66, 3.8), (-1.12, 1.66, 3.6)], 4), 0.014, seg=8)
    rl.done('engine_ladder', 'paint_orange')
    cab(root)


def cab(root):
    CTX['parent'] = root
    x0, x1, y0, y1, z0, z1 = -0.72, 0.72, -1.38, -0.10, 2.15, 3.82
    lean = 0.12
    posts = Mesh()
    corners = [(x0, y0), (x1, y0), (x0, y1), (x1, y1)]
    for (x, y) in corners:
        top_y = y - (lean if y == y0 else 0)
        posts.beam((x, y, z0), (x, top_y, z1), 0.06, 0.045, up=(1, 0, 0))
    for (a, b) in (((x0, y0 - lean), (x1, y0 - lean)), ((x0, y1), (x1, y1)), ((x0, y0 - lean), (x0, y1)), ((x1, y0 - lean), (x1, y1))):
        posts.beam((a[0], a[1], z1), (b[0], b[1], z1), 0.055, 0.06)
    for (a, b) in (((x0, y0), (x1, y0)), ((x0, y0), (x0, y1)), ((x1, y0), (x1, y1)), ((x0, y1), (x1, y1))):
        posts.beam((a[0], a[1], 2.62), (b[0], b[1], 2.62), 0.045, 0.05)
    posts.beam((x1, -0.72, z0), (x1, -0.72 - lean * 0.2, z1), 0.05, 0.04, up=(1, 0, 0))   # door post
    for (a, b) in (((x0, y0), (x1, y0)), ((x0, y0), (x0, y1)), ((x1, y0), (x1, y1)), ((x0, y1), (x1, y1))):
        posts.beam((a[0], a[1], z0 + 0.03), (b[0], b[1], z0 + 0.03), 0.05, 0.06)
    posts.done('cab_frame', 'paint_black')
    seal = Mesh()
    for (a, b) in (((x0 + 0.03, y0 + 0.004, 2.65), (x1 - 0.03, y0 + 0.004, 2.65)),
                   ((x0 + 0.03, y0 - lean + 0.004, z1 - 0.035), (x1 - 0.03, y0 - lean + 0.004, z1 - 0.035))):
        seal.tube([a, b], 0.008, seg=6)
    seal.done('cab_seals', 'rubber')
    low = Mesh()
    low.boxp((x0, y0 + 0.01, z0), (x1, y0 + 0.03, 2.6), bevel=0.01)
    low.boxp((x0 - 0.01, y0, z0), (x0 + 0.01, y1, 2.6), bevel=0.01)
    low.boxp((x1 - 0.01, -0.72, z0), (x1 + 0.01, y1, 2.6), bevel=0.01)
    low.done('cab_lower_panels', 'paint_red')
    # door (left, glazed) with handle and hinges
    door = Mesh()
    door.tube([(x1 + 0.01, y0 + 0.02, 2.2), (x1 + 0.01, y0 + 0.02, 3.76), (x1 + 0.01, -0.73, 3.76), (x1 + 0.01, -0.73, 2.2)], 0.018, seg=6, caps=True)
    door.tube([(x1 + 0.01, -0.73, 2.2), (x1 + 0.01, y0 + 0.02, 2.2)], 0.018, seg=6)
    door.done('cab_door_frame', 'paint_black')
    hd = Mesh()
    hd.boxp((x1 + 0.025, -0.82, 3.0), (x1 + 0.04, -0.76, 3.02), bevel=0.004)
    for z in (2.4, 3.5):
        hd.cyl((x1 + 0.02, y0 + 0.02, z - 0.04), (x1 + 0.02, y0 + 0.02, z + 0.04), 0.012, seg=8)
    hd.done('cab_door_hw', 'chrome')
    gl = Mesh()
    bm = gl.bm

    def quad(a, b, c, d):
        vs = [bm.verts.new(v3(p)) for p in (a, b, c, d)]
        bm.faces.new(vs)
    quad((x0 + 0.03, y0 + 0.005, 2.64), (x1 - 0.03, y0 + 0.005, 2.64), (x1 - 0.03, y0 - lean + 0.005, z1 - 0.03), (x0 + 0.03, y0 - lean + 0.005, z1 - 0.03))
    quad((x0 + 0.03, y0 + 0.02, z0 + 0.05), (x1 - 0.03, y0 + 0.02, z0 + 0.05), (x1 - 0.03, y0 + 0.02, 2.6), (x0 + 0.03, y0 + 0.02, 2.6)) if False else None
    for sx, xs in ((-1, x0), (1, x1)):
        yb = y0 + 0.03 if sx < 0 else -0.71
        quad((xs, y1 - 0.03, 2.64), (xs, yb, 2.64), (xs, yb - (0.02 if sx < 0 else 0), z1 - 0.03), (xs, y1 - 0.03, z1 - 0.03))
    quad((x1 + 0.01, y0 + 0.04, 2.25), (x1 + 0.01, -0.75, 2.25), (x1 + 0.01, -0.75, 3.74), (x1 + 0.01, y0 + 0.04, 3.74))
    quad((x1 - 0.03, y1 - 0.004, 2.64), (x0 + 0.03, y1 - 0.004, 2.64), (x0 + 0.03, y1 - 0.004, z1 - 0.03), (x1 - 0.03, y1 - 0.004, z1 - 0.03))
    gl.done_raw('cab_glass', 'glass', own=1, smooth=0)
    # white fibreglass roof with drip rail, vent, lights, beacon
    roof = Mesh()
    roof.boxp((x0 - 0.1, y0 - lean - 0.12, z1 - 0.02), (x1 + 0.1, y1 + 0.06, z1 + 0.13), bevel=0.05, seg=3)
    roof.boxp((-0.25, -0.9, z1 + 0.12), (0.25, -0.5, z1 + 0.17), bevel=0.02, seg=2)
    roof.done('cab_roof', 'paint_white')
    decal_plane('decal_bizon_roof', (0.0, y0 - lean - 0.121, z1 + 0.055), (-1, 0, 0), (0, 0, 1), (0.42, 0.125), 'bizon')
    hw = Mesh()
    for sx in (-1, 1):
        # road lamps on the roof front corners (round)
        c = Vector((sx * 0.62, y0 - lean - 0.2, z1 + 0.03))
        hw.lathe([(0.0, 0.0), (0.07, 0.0), (0.085, 0.04), (0.088, 0.1), (0.0, 0.1)], 20, c + Vector((0, 0.08, 0)), axis=(0, -1, 0))
        hw.boxp((sx * 0.62 - 0.015, y0 - lean - 0.14, z1 - 0.02), (sx * 0.62 + 0.015, y0 - lean - 0.1, z1 + 0.04))
        # rectangular work lamps
        hw.boxp((sx * 0.25 - 0.08, y0 - lean - 0.2, z1 + 0.13), (sx * 0.25 + 0.08, y0 - lean - 0.12, z1 + 0.23), bevel=0.012)
        # indicators on the front corners
        hw.boxp((sx * 0.8 - 0.035, y0 - lean - 0.13, z1 + 0.0), (sx * 0.8 + 0.035, y0 - lean - 0.08, z1 + 0.06), bevel=0.008)
        # mirror arms and heads
        hw.tube([(sx * 0.73, y0 - 0.02, 3.3), (sx * 0.98, y0 - 0.12, 3.35), (sx * 1.02, y0 - 0.14, 3.45)], 0.012, seg=8)
        hw.lathe([(0.0, -0.012), (0.1, -0.012), (0.11, 0.0), (0.1, 0.02), (0.0, 0.025)], 20, (sx * 1.04, y0 - 0.16, 3.58), axis=(0, 1, 0))
        hw.tube([(sx * 1.02, y0 - 0.14, 3.45), (sx * 1.04, y0 - 0.15, 3.5)], 0.01, seg=6)
    hw.boxp((0.55, y1 - 0.02, z1 + 0.13), (0.65, y1 + 0.05, z1 + 0.22), bevel=0.01)   # rear work lamp
    hw.done('cab_lamps', 'paint_black')
    lens = Mesh()
    for sx in (-1, 1):
        c = Vector((sx * 0.62, y0 - lean - 0.2, z1 + 0.03))
        lens.lathe([(0.0, 0.0), (0.075, 0.0), (0.07, 0.012), (0.0, 0.02)], 20, c + Vector((0, -0.021, 0)), axis=(0, -1, 0))
        lens.boxp((sx * 0.25 - 0.07, y0 - lean - 0.205, z1 + 0.14), (sx * 0.25 + 0.07, y0 - lean - 0.2, z1 + 0.22))
    lens.boxp((0.56, y1 + 0.05, z1 + 0.14), (0.64, y1 + 0.055, z1 + 0.21))
    lens.done('cab_lenses', 'lens_clear')
    mir = Mesh()
    for sx in (-1, 1):
        mir.lathe([(0.0, 0.0), (0.095, 0.0), (0.095, 0.002), (0.0, 0.002)], 20, (sx * 1.04, y0 - 0.173, 3.58), axis=(0, -1, 0))
    mir.done('mirror_glass', 'chrome')
    ind = Mesh()
    for sx in (-1, 1):
        ind.boxp((sx * 0.8 - 0.03, y0 - lean - 0.135, z1 + 0.005), (sx * 0.8 + 0.03, y0 - lean - 0.13, z1 + 0.055))
    ind.done('cab_indicator_lens', 'lens_amber')
    for nm, mat, pts in (('lit_front', 'lit_white', [(sx * 0.62, y0 - lean - 0.2, z1 + 0.03) for sx in (-1, 1)]),):
        m = Mesh()
        for p in pts:
            m.lathe([(0.0, 0.0), (0.072, 0.0), (0.0, 0.004)], 20, Vector(p) + Vector((0, -0.024, 0)), axis=(0, -1, 0))
        m.done(nm, mat, own=1, hidden=1)
    m = Mesh()
    for sx in (-1, 1):
        m.boxp((sx * 0.25 - 0.068, y0 - lean - 0.209, z1 + 0.142), (sx * 0.25 + 0.068, y0 - lean - 0.206, z1 + 0.218))
    m.done('lit_work_front', 'lit_white', own=1, hidden=1)
    m = Mesh()
    m.boxp((0.565, y1 + 0.056, z1 + 0.142), (0.635, y1 + 0.059, z1 + 0.208))
    m.done('lit_work_rear', 'lit_white', own=1, hidden=1)
    for sx, nm in ((1, 'L'), (-1, 'R')):
        m = Mesh()
        m.boxp((sx * 0.8 - 0.028, y0 - lean - 0.138, z1 + 0.007), (sx * 0.8 + 0.028, y0 - lean - 0.136, z1 + 0.053))
        m.done('lit_turn_front_' + nm, 'lit_amber', own=1, hidden=1)
    # beacon (amber dome) and CB antenna on the roof
    bc = Mesh()
    bc.lathe([(0.0, 0.0), (0.08, 0.0), (0.08, 0.03), (0.0, 0.03)], 20, (-0.35, -0.3, z1 + 0.13), axis=(0, 0, 1))
    bc.done('beacon_base', 'plastic')
    bd = Mesh()
    bd.lathe([(0.0, 0.0), (0.07, 0.0), (0.07, 0.1), (0.05, 0.14), (0.0, 0.15)], 20, (-0.35, -0.3, z1 + 0.16), axis=(0, 0, 1))
    bd.done('beacon_dome', 'lens_amber')
    an = Mesh()
    an.cyl((0.6, -0.2, z1 + 0.13), (0.6, -0.2, z1 + 0.19), 0.025, seg=10)
    an.cyl((0.6, -0.2, z1 + 0.19), (0.6, -0.12, z1 + 1.45), 0.0025, seg=5)
    an.done('cb_antenna', 'plastic')
    wp = Mesh()
    for sx in (-0.3, 0.3):
        wp.tube([(sx, y0 - lean + 0.01, z1 - 0.06), (sx + 0.05, y0 - lean * 0.45 - 0.0, 3.25)], 0.006, seg=6)
        wp.boxp((sx + 0.02, y0 - lean * 0.45 - 0.01, 2.98), (sx + 0.035, y0 - lean * 0.45, 3.5))
    wp.done('wipers', 'plastic')
    cab_interior(root)


def cab_interior(root):
    CTX['parent'] = root
    zf = 2.15
    fl = Mesh()
    fl.boxp((-0.7, -1.36, zf), (0.7, -0.12, zf + 0.012))
    fl.done('cab_floor_mat', 'rubber')
    # seat on a sprung pedestal
    st = Mesh()
    st.boxp((-0.22, -0.72, 2.56), (0.28, -0.26, 2.66), bevel=0.04, seg=3)
    st.hull([(-0.22, -0.3, 2.64), (0.28, -0.3, 2.64), (-0.22, -0.2, 2.66), (0.28, -0.2, 2.66),
             (-0.2, -0.24, 3.18), (0.26, -0.24, 3.18), (-0.2, -0.14, 3.18), (0.26, -0.14, 3.18)])
    st.done('seat_cushions', 'seat')
    sp = Mesh()
    sp.boxp((-0.15, -0.62, 2.2), (0.21, -0.32, 2.3), bevel=0.01)
    sp.lathe([(0.045, 0.0), (0.045, 0.02)] + [(0.045 + 0.012 * ((k % 2) * 2 - 1) * 0.5, 0.02 + k * 0.022) for k in range(10)] +
             [(0.045, 0.24)], 12, (0.03, -0.47, 2.3), axis=(0, 0, 1))
    sp.boxp((-0.2, -0.7, 2.53), (0.26, -0.28, 2.56), bevel=0.005)
    sp.done('seat_base', 'paint_black')
    # steering column, wheel (own node), dashboard with gauges
    col = Mesh()
    col.tube([(0.03, -1.3, zf), (0.03, -1.2, 2.55), (0.03, -1.07, 2.98)], 0.035, seg=12)
    col.boxp((-0.2, -1.36, 2.52), (0.26, -1.18, 2.9), bevel=0.03, seg=2)
    col.done('steering_column', 'paint_black')
    for i, (key, x) in enumerate((('gauge_rpm', -0.1), ('gauge_speed', 0.16))):
        c = Vector((x, -1.18, 2.78))
        rng = Mesh()
        rng.lathe([(0.0, 0.0), (0.058, 0.0), (0.062, 0.012), (0.062, 0.02), (0.056, 0.02), (0.056, 0.004), (0.0, 0.004)], 24, c, axis=(0, 1, 0))
        rng.done('gauge_bezel_%d' % i, 'chrome')
        decal_plane('decal_%s' % key, c + Vector((0, 0.004, 0)), (-1, 0, 0), (0, 0, 1), (0.108, 0.108), key, offset=0.001)
        nd = node('needle_' + key.split('_')[1], c + Vector((0, 0.012, 0)), root)
        CTX['parent'] = nd
        n = Mesh()
        n.box(c + Vector((0, 0.012, 0.022)), (0.004, 0.002, 0.046))
        n.done('needle_%d' % i, 'lit_amber')
        CTX['parent'] = root
    sw = node('steeringWheel', (0.03, -1.04, 3.0), root, rot=Matrix.Rotation(rad(-35), 3, 'X'))
    CTX['parent'] = sw
    w = Mesh()
    ctr = Vector((0.03, -1.04, 3.0))
    rot = Matrix.Rotation(rad(-35), 3, 'X')
    ax = rot @ Vector((0, 0, 1))
    w.lathe([(0.2, -0.012), (0.212, -0.018), (0.224, -0.012), (0.226, 0.0), (0.224, 0.012), (0.212, 0.018), (0.2, 0.012), (0.198, 0.0)],
            40, ctr, axis=ax)
    for k in range(3):
        a = TAU * k / 3 + rad(90)
        d = rot @ Vector((math.cos(a), math.sin(a), 0))
        w.tube([ctr + d * 0.04, ctr + d * 0.205], 0.01, seg=6)
    w.cyl(ctr - ax * 0.03, ctr + ax * 0.02, 0.045, seg=16)
    w.done('steering_wheel', 'plastic')
    CTX['parent'] = root
    lv = Mesh()
    for i, (x, y, h, tilt) in enumerate(((0.38, -0.95, 0.45, 12), (0.44, -0.9, 0.42, -10), (0.5, -0.85, 0.4, 8),
                                         (-0.35, -0.95, 0.5, -15), (0.42, -0.62, 0.38, 20))):
        rot = Matrix.Rotation(rad(tilt), 3, 'Y')
        p0 = Vector((x, y, zf + 0.25))
        p1 = p0 + rot @ Vector((0, 0, h))
        lv.cyl(p0, p1, 0.008, seg=6)
        lv.sphere(p1, 0.022, seg=10, rings=6)
    lv.boxp((0.32, -1.02, zf), (0.56, -0.8, zf + 0.26), bevel=0.02)
    lv.boxp((-0.42, -1.0, zf), (-0.28, -0.88, zf + 0.28), bevel=0.02)
    lv.done('levers', 'plastic')
    pd = Mesh()
    for x in (-0.18, 0.0, 0.14):
        pd.boxp((x - 0.04, -1.28, zf + 0.1), (x + 0.04, -1.25, zf + 0.2), bevel=0.006)
        pd.cyl((x, -1.28, zf + 0.12), (x, -1.34, zf + 0.25), 0.01, seg=6)
    pd.done('pedals', 'metal')
    fx = Mesh()
    fx.lathe([(0.0, 0.0), (0.06, 0.0), (0.06, 0.34), (0.045, 0.37), (0.02, 0.38), (0.0, 0.38)], 16, (-0.58, -0.25, zf + 0.02), axis=(0, 0, 1))
    fx.done('extinguisher', 'red_gloss')
    fxb = Mesh()
    fxb.cyl((-0.58, -0.25, zf + 0.4), (-0.58, -0.25, zf + 0.44), 0.015, seg=8)
    fxb.tube([(-0.58, -0.25, zf + 0.42), (-0.52, -0.22, zf + 0.35), (-0.53, -0.2, zf + 0.15)], 0.006, seg=6)
    fxb.done('extinguisher_head', 'plastic')
    decal_plane('decal_warning_cab', (-0.715, -0.5, 2.4), (0, 1, 0), (0, 0, 1), (0.3, 0.093), 'warning', offset=-0.004)
    # Tyskie crate next to the seat, one bottle out
    tyskie_crate(Vector((0.44, -0.46, zf + 0.012)), root, 'crate_cab', missing=(3,), yaw=0.0)
    bottle(Vector((0.26, -1.0, zf + 0.012)), root, 'bottle_open', open_=True, tilt=0.0)
    # interior light, sun visor
    il = Mesh()
    il.boxp((-0.1, -0.35, 3.78), (0.1, -0.25, 3.81), bevel=0.01)
    il.done('cab_light', 'lens_clear')
    sv = Mesh()
    sv.boxp((-0.45, -1.46, 3.72), (0.1, -1.38, 3.73), bevel=0.004)
    sv.done('sun_visor', 'plastic')


def bottle(base, parent, name, open_=False, tilt=0.0, liquid=0.82):
    """Brown 0.5 l returnable bottle with label, neck label and crown cap."""
    CTX['parent'] = parent
    prof = [(0.0, 0.0), (0.028, 0.0), (0.0335, 0.004), (0.0345, 0.012), (0.0345, 0.145), (0.032, 0.165), (0.024, 0.188),
            (0.0145, 0.21), (0.0135, 0.235), (0.0145, 0.238), (0.0145, 0.246), (0.012, 0.25)]
    rot = Matrix.Rotation(tilt, 3, 'Y')
    ax = rot @ Vector((0, 0, 1))
    m = Mesh()
    rings = m.lathe(prof, 20, base, axis=ax, cap0=False)
    m.lathe([(0.012, 0.25), (0.0105, 0.25), (0.0105, 0.2), (0.03, 0.15), (0.0315, 0.01), (0.0, 0.006)], 20, base, axis=ax)
    m.done(name + '_glass', 'bottle')
    lb = Mesh()
    lb.lathe([(0.0348, 0.045), (0.0348, 0.13)], 20, base, axis=ax)
    ob = lb.done_raw(name + '_label', 'decal', smooth=30)
    cyl_uv(ob, ATLAS['label'], base, ax, 0.14, phase=0.0)
    nk = Mesh()
    nk.lathe([(0.0152, 0.195), (0.0142, 0.212)], 20, base, axis=ax)
    ob = nk.done_raw(name + '_neck', 'decal', smooth=30)
    cyl_uv(ob, ATLAS['neck'], base, ax, 0.02)
    if not open_:
        cp = Mesh()
        cp.lathe([(0.0, 0.254), (0.0148, 0.254), (0.0158, 0.248), (0.0162, 0.243), (0.0148, 0.24)], 21, base, axis=ax)
        cp.done(name + '_cap', 'gold')
    bl = Mesh()
    bl.lathe([(0.0, 0.008), (0.031, 0.01), (0.031, 0.15 * liquid), (0.0, 0.15 * liquid)], 16, base, axis=ax)
    bl.done(name + '_beer', 'beer')


def tyskie_crate(base, parent, name, missing=(), yaw=0.0):
    """Plastic 20 x 0.5 l crate (400 x 300 x 290 mm) with hand holes and dividers."""
    CTX['parent'] = parent
    L, W, H = 0.40, 0.30, 0.29
    rot = Matrix.Rotation(yaw, 3, 'Z')

    def P(x, y, z):
        return base + rot @ Vector((x, y, z))
    c = Mesh()
    t = 0.008
    for sx in (-1, 1):
        c.poly_prism([(-W / 2, 0), (W / 2, 0), (W / 2, H), (0.06, H), (0.06, H - 0.05), (-0.06, H - 0.05), (-0.06, H), (-W / 2, H)],
                     P(sx * L / 2, 0, 0), rot @ Vector((0, 1, 0)), rot @ Vector((0, 0, 1)), rot @ Vector((-sx, 0, 0)), t)
    for sy in (-1, 1):
        c.boxp(P(-L / 2, sy * W / 2 - t / 2, 0), P(L / 2, sy * W / 2 + t / 2, H), bevel=0.003)
        for k in range(4):
            c.boxp(P(-L / 2 + 0.03 + k * 0.1, sy * (W / 2 + 0.004) - 0.003, 0.02), P(-L / 2 + 0.07 + k * 0.1, sy * (W / 2 + 0.004) + 0.003, H - 0.04))
    c.boxp(P(-L / 2, -W / 2, 0), P(L / 2, W / 2, 0.008))
    for i in range(1, 5):
        x = -L / 2 + i * L / 5
        c.boxp(P(x - 0.002, -W / 2, 0), P(x + 0.002, W / 2, 0.18))
    for j in range(1, 4):
        y = -W / 2 + j * W / 4
        c.boxp(P(-L / 2, y - 0.002, 0), P(L / 2, y + 0.002, 0.18))
    c.done(name, 'crate')
    for sy in (-1, 1):
        decal_plane(name + '_print_%d' % sy, P(0, sy * (W / 2 + 0.0075), 0.2), rot @ Vector((sy * -1, 0, 0)) * -1 if sy < 0 else rot @ Vector((-1, 0, 0)),
                    rot @ Vector((0, 0, 1)), (0.3, 0.076), 'crate', parent=parent, offset=0.0) if False else None
    decal_plane(name + '_print_front', P(0, -(W / 2 + 0.0075), 0.2), rot @ Vector((1, 0, 0)), rot @ Vector((0, 0, 1)), (0.3, 0.076), 'crate', parent=parent, offset=0.0)
    decal_plane(name + '_print_back', P(0, (W / 2 + 0.0075), 0.2), rot @ Vector((-1, 0, 0)), rot @ Vector((0, 0, 1)), (0.3, 0.076), 'crate', parent=parent, offset=0.0)
    k = 0
    for i in range(5):
        for j in range(4):
            k += 1
            if k in missing:
                continue
            x = -L / 2 + (i + 0.5) * L / 5
            y = -W / 2 + (j + 0.5) * W / 4
            bottle(P(x, y, 0.01), parent, '%s_b%02d' % (name, k))


def feeder_house(root):
    fh = node('feederHouse', FEED_PIVOT, root)
    CTX['parent'] = fh
    d = FEED_FRONT - FEED_PIVOT
    ang = math.atan2(-d.z, -d.y)
    rot = Matrix.Rotation(ang, 3, 'X')
    L = d.length + 0.05
    mid = (FEED_PIVOT + FEED_FRONT) / 2
    m = Mesh()
    m.box(mid, (1.18, L, 0.46), bevel=0.03, seg=2, rot=rot)
    ax = d.normalized()
    up = rot @ Vector((0, 0, 1))
    for sx in (-1, 1):
        for k in range(4):
            p = FEED_PIVOT + ax * (0.25 + k * 0.38)
            m.box(p + Vector((sx * 0.595, 0, 0)), (0.012, 0.04, 0.44), rot=rot, bevel=0.005)
    # inspection door on top
    p = FEED_PIVOT + ax * 0.8 + up * 0.235
    m.box(p, (0.8, 0.6, 0.018), rot=rot, bevel=0.006)
    # front flange where the header hangs
    m.box(FEED_FRONT + ax * 0.0, (1.26, 0.06, 0.56), rot=rot, bevel=0.01)
    m.done('feeder_house', 'paint_red')
    b = Mesh()
    for sx in (-1, 1):
        bolts_along(b, FEED_PIVOT + Vector((sx * 0.6, 0, 0)) + up * 0.19, FEED_FRONT + Vector((sx * 0.6, 0, 0)) + up * 0.19, 12, (sx, 0, 0))
    for sx in (-0.3, 0.3):
        b.cyl(p + Vector((sx, 0, 0)) + up * 0.009, p + Vector((sx, 0, 0)) + up * 0.03, 0.02, seg=8)
    b.done('feeder_bolts', 'galv')
    # drive: sprocket and chain along the left side to the header input
    top_c = FEED_PIVOT + Vector((0.64, 0, 0))
    fr_c = FEED_FRONT + Vector((0.64, 0, 0)) - ax * 0.12
    ch = Mesh()
    belt(ch, 0.64, (top_c.y, top_c.z), 0.1, (fr_c.y, fr_c.z), 0.07, w=0.02, t=0.014)
    ch.done('feeder_chain', 'metal')
    g = Mesh()
    g.box((top_c + fr_c) / 2 + Vector((0.035, 0, 0)), (0.008, L - 0.1, 0.3), rot=rot, bevel=0.004)
    g.done('feeder_chain_guard', 'paint_red')
    sp = node('feederSprocket', top_c, fh)
    CTX['parent'] = sp
    s = Mesh()
    pulley(s, top_c, 0.1, width=0.025, spokes=0)
    s.done('feeder_sprocket', 'metal')
    CTX['parent'] = fh
    node('attacherJointCutter', FEED_FRONT - ax * 0.03, fh)
    # lift cylinder rods (move with the feeder) and their reference points
    for sx, nm in ((1, 'L'), (-1, 'R')):
        rod_ref = node('liftRodRef' + nm, FEED_PIVOT + ax * 0.95 - up * 0.26 + Vector((sx * 0.4, 0, 0)), fh)
        CTX['parent'] = fh
        br = Mesh()
        pp = FEED_PIVOT + ax * 0.95 - up * 0.23 + Vector((sx * 0.4, 0, 0))
        br.box(pp, (0.05, 0.1, 0.06), rot=rot, bevel=0.01)
        br.done('lift_bracket_' + nm, 'paint_red')
    CTX['parent'] = root
    for sx, nm in ((1, 'L'), (-1, 'R')):
        base = Vector((sx * 0.4, -0.35, 0.72))
        target = FEED_PIVOT + ax * 0.95 - up * 0.26 + Vector((sx * 0.4, 0, 0))
        # i3d +Z of a movingPart points at its reference point, i3d +Y stays up
        cn = node('liftCyl' + nm, base, root, rot=aim_matrix(-(target - base).normalized(), up=(0, 0, 1)))
        CTX['parent'] = cn
        dirv = (target - base).normalized()
        c = Mesh()
        c.cyl(base, base + dirv * 0.62, 0.042, seg=14)
        c.cyl(base - Vector((0.03, 0, 0)), base + Vector((0.03, 0, 0)), 0.03, seg=10)
        c.done('lift_cyl_' + nm, 'paint_black')
        rn = node('liftRod' + nm, base + dirv * 0.62, cn)
        CTX['parent'] = rn
        r = Mesh()
        r.cyl(base + dirv * 0.3, target, 0.022, seg=12)
        r.done('lift_rod_' + nm, 'chrome')
        CTX['parent'] = root
        hose([base + dirv * 0.05 + Vector((0, 0, 0.05)), base + Vector((0, 0.15, 0.25)), Vector((sx * 0.35, -0.8, 1.8)), Vector((-0.5, -0.95, 1.95))],
             0.011, name='hose_lift_' + nm, parent=root)


def drives_left(root):
    CTX['parent'] = root
    X = [0.87, 0.93, 0.99]
    P = {  # name: (y, z, r, plane, grooves, speed factor)
        'engPulley': (2.52, 2.0, 0.19, 1, 2, 1.0),
        'counterBig': (1.55, 1.62, 0.3, 1, 2, 0.62),
        'counterSmall': (1.55, 1.62, 0.13, 0, 1, 0.62),
        'drumVariator': (0.12, 1.5, 0.3, 0, 1, 0.27),
        'beater': (0.72, 1.9, 0.14, 2, 1, 0.9),
        'drumSmall': (0.12, 1.5, 0.12, 2, 1, 0.27),
        'fan': (0.66, 0.92, 0.17, 1, 1, 0.5),
        'counterFan': (1.55, 1.62, 0.1, 1, 1, 0.62),
        'sieve': (2.08, 0.96, 0.16, 2, 1, 0.35),
        'fanSmall': (0.66, 0.92, 0.09, 2, 1, 0.5),
        'walkerCrank': (3.18, 1.96, 0.24, 0, 1, 0.25),
        'counterWalker': (1.55, 1.62, 0.09, 2, 1, 0.62),
        'augerBottom': (1.12, 0.74, 0.11, 0, 1, 0.8),
    }
    # shafts + bearings
    sh = Mesh()
    for key in ('counterBig', 'drumVariator', 'beater', 'fan', 'sieve', 'augerBottom'):
        y, z = P[key][0], P[key][1]
        sh.cyl((0.8, y, z), (1.02, y, z), 0.022, seg=10)
        flange_bearing(sh, (0.815, y, z), (1, 0, 0), r=0.065)
    sh.cyl((0.84, 3.18, 1.96), (0.92, 3.18, 1.96), 0.03, seg=10)
    flange_bearing(sh, (0.845, 3.18, 1.96), (1, 0, 0), r=0.07)
    sh.done('left_shafts', 'paint_black')
    for key, (y, z, r, pl, gr, sp) in P.items():
        nd = node('pl_' + key, (X[pl], y, z), root, anim_speed=sp, anim_axis=1)
        CTX['parent'] = nd
        m = Mesh()
        pulley(m, (X[pl], y, z), r, width=0.034, grooves=gr, spokes=5 if r > 0.15 else 0)
        m.done(key + '_pulley', 'paint_black' if key not in ('drumVariator',) else 'metal')
        CTX['parent'] = root
    # variator second half + adjusting cylinder
    v = Mesh()
    v.lathe([(0.05, 0.0), (0.3, 0.025), (0.31, 0.03), (0.05, 0.05)], 32, (X[0] + 0.01, 0.12, 1.5), axis=(1, 0, 0))
    v.cyl((X[0] + 0.07, 0.12, 1.5), (X[0] + 0.16, 0.12, 1.5), 0.05, seg=14)
    v.done('variator_disc', 'metal')
    bl = Mesh()
    for a, b, pl in (('engPulley', 'counterBig', 1), ('counterSmall', 'drumVariator', 0), ('drumSmall', 'beater', 2),
                     ('counterFan', 'fan', 1), ('fanSmall', 'sieve', 2), ('counterWalker', 'walkerCrank', 2)):
        (y1, z1, r1, _, g1, _), (y2, z2, r2, _, g2, _) = P[a], P[b]
        for g in range(min(g1, g2)):
            belt(bl, X[pl] + (g - (min(g1, g2) - 1) / 2) * 0.034, (y1, z1), r1 - 0.012, (y2, z2), r2 - 0.012)
    bl.done('left_belts', 'rubber')
    # tensioners (arm + idler + spring)
    tn = Mesh()
    for (y, z, ay, az) in ((1.0, 1.33, 1.2, 1.1), (2.1, 1.35, 2.3, 1.2), (0.95, 1.95, 1.2, 2.05)):
        tn.tube([(0.95, ay, az), (0.95, y, z)], 0.015, seg=6)
        pulley(tn, (0.95, y, z), 0.06, width=0.03, spokes=0)
        spring = [(0.955, ay + 0.02 * math.cos(k * 1.3), az - 0.25 + k * 0.012) for k in range(20)]
        tn.tube(spring, 0.004, seg=4)
    tn.done('tensioners', 'paint_black')
    # guards: half-round over the engine pulley and the variator, mesh over the long belt
    gd = Mesh()
    gd.lathe([(0.24, 0.0), (0.24, 0.09), (0.22, 0.09)], 32, (0.9, 2.52, 2.0), axis=(1, 0, 0))
    gd.lathe([(0.36, 0.0), (0.36, 0.07), (0.34, 0.07)], 36, (0.84, 0.12, 1.5), axis=(1, 0, 0))
    gd.done('guards_round', 'paint_red')
    # remove lower halves of the round guards by covering only upper side: add back plates
    gm = Mesh()
    wire_grid(gm, (1.02, 1.62, 1.72), (0, 0.9, 0.28), (0, 0.0, 0.32), 30, 10, r=0.002)
    gm.done('guard_mesh', 'paint_black', smooth=0)
    gf = Mesh()
    gf.tube([(1.02, 1.62, 1.72), (1.02, 2.52, 2.0), (1.02, 2.52, 2.32), (1.02, 1.62, 2.04), (1.02, 1.62, 1.72)], 0.008, seg=6)
    gf.done('guard_mesh_frame', 'paint_red')
    # sieve eccentric rod & fan speed handwheel
    ex = Mesh()
    ex.tube([(1.0, 2.08, 0.96), (1.0, 2.6, 0.9)], 0.015, seg=8)
    ex.lathe([(0.1, -0.008), (0.11, 0.0), (0.1, 0.008)], 24, (1.05, 0.66, 0.92), axis=(1, 0, 0))
    for k in range(4):
        a = TAU * k / 4
        ex.tube([(1.05, 0.66, 0.92), (1.05, 0.66 + 0.1 * math.cos(a), 0.92 + 0.1 * math.sin(a))], 0.006, seg=6)
    ex.done('sieve_rod', 'metal')


def drives_right(root):
    CTX['parent'] = root
    el = Mesh()
    # grain elevator (bolted halves) and tailings elevator
    el.boxp((-0.97, 0.95, 0.62), (-0.81, 1.2, 2.2), bevel=0.012)
    el.boxp((-0.99, 0.93, 1.38), (-0.79, 1.22, 1.42), bevel=0.008)
    el.boxp((-1.0, 0.9, 2.0), (-0.81, 1.25, 2.3), bevel=0.02)
    el.boxp((-0.93, 1.82, 0.62), (-0.81, 2.0, 1.78), bevel=0.01)
    el.boxp((-0.95, 1.78, 1.62), (-0.81, 2.04, 1.82), bevel=0.015)
    # fuel tank with straps & filler, battery box, hydraulic tank, toolbox
    el.boxp((-1.2, 1.62, 1.22), (-0.83, 2.32, 1.95), bevel=0.05, seg=2)
    el.boxp((-1.23, -1.3, 1.64), (-0.93, -0.86, 1.94), bevel=0.02)
    el.boxp((-0.85, 4.1, 1.35), (-0.55, 4.6, 1.55), bevel=0.02) if False else None
    el.done('right_side_boxes', 'paint_red')
    bb = Mesh()
    for y in (1.75, 2.18):
        bb.boxp((-1.215, y - 0.02, 1.2), (-1.195, y + 0.02, 1.97), bevel=0.004)
    bb.cyl((-1.05, 1.97, 1.95), (-1.05, 1.97, 2.05), 0.05, seg=16)
    bb.cyl((-1.05, 1.97, 2.05), (-1.05, 1.97, 2.08), 0.055, seg=16)
    bolts_along(bb, (-0.972, 0.96, 1.4), (-0.972, 1.19, 1.4), 5, (-1, 0, 0))
    bolts_along(bb, (-0.972, 0.96, 0.9), (-0.972, 0.96, 2.0), 12, (-1, 0, 0))
    bolts_along(bb, (-0.972, 1.19, 0.9), (-0.972, 1.19, 2.0), 12, (-1, 0, 0))
    bb.done('right_hardware', 'paint_black')
    ht = Mesh()
    ht.lathe([(0.0, 0.0), (0.12, 0.0), (0.13, 0.02), (0.13, 0.48), (0.12, 0.5), (0.0, 0.5)], 24, (-1.0, -0.6, 1.9), axis=(0, 1, 0))
    ht.cyl((-1.0, -0.4, 2.02), (-1.0, -0.4, 2.08), 0.035, seg=12)
    ht.done('hydraulic_tank', 'paint_black')
    sg = Mesh()
    sg.cyl((-1.131, -0.35, 1.9), (-1.135, -0.35, 1.9), 0.025, seg=12)
    sg.done('hydraulic_sightglass', 'lens_amber')
    for key, (y, z, r, sp) in {'elevHead': (1.07, 2.14, 0.12, 0.8), 'counterR': (1.55, 1.62, 0.16, 0.62),
                               'augerR': (1.07, 0.74, 0.1, 0.8), 'tailHead': (1.9, 1.7, 0.09, 0.8)}.items():
        nd = node('pr_' + key, (-1.03, y, z), root, anim_speed=sp, anim_axis=1)
        CTX['parent'] = nd
        m = Mesh()
        pulley(m, (-1.03, y, z), r, width=0.032, spokes=4 if r > 0.13 else 0)
        m.done(key + '_pulley', 'paint_black')
        CTX['parent'] = root
    bl = Mesh()
    belt(bl, -1.03, (1.55, 1.62), 0.148, (1.07, 2.14), 0.108)
    belt(bl, -1.03, (1.07, 0.74), 0.088, (1.55, 1.62), 0.148) if False else None
    bl.done('right_belts', 'rubber')
    ch = Mesh()
    belt(ch, -1.06, (1.07, 0.74), 0.09, (1.9, 1.7), 0.08, w=0.016, t=0.012)
    ch.done('right_chain', 'metal')
    # battery with terminals + main cable to starter
    bt = Mesh()
    bt.boxp((-1.2, -1.27, 1.66), (-0.96, -0.89, 1.9), bevel=0.01)
    bt.done('battery', 'plastic')
    tm = Mesh()
    tm.cyl((-1.05, -1.2, 1.9), (-1.05, -1.2, 1.93), 0.012, seg=8)
    tm.cyl((-1.05, -0.96, 1.9), (-1.05, -0.96, 1.93), 0.012, seg=8)
    tm.done('battery_terminals', 'copper')
    decal_plane('decal_bizon_hood_R', (-0.855, 4.3, 1.8), (0, -1, 0), (0, 0, 1), (0.5, 0.15), 'bizon')


def wheels(root):
    CTX['parent'] = root
    specs = [('wheelFL', FW['X'], 0.0, FW, 1), ('wheelFR', -FW['X'], 0.0, FW, -1),
             ('wheelRL', RW['X'], RW['Y'], RW, 1), ('wheelRR', -RW['X'], RW['Y'], RW, -1)]
    for name, x, y, s, side in specs:
        c = Vector((x, y, s['Z']))
        repr_ = node(name, c, root)
        drv = node(name + '_drive', c, repr_)
        CTX['parent'] = drv
        t = Mesh()
        if s is FW:
            tyre_agri(t, c, s['R'], s['W'], s['rim'])
        else:
            tyre_ribbed(t, c, s['R'], s['W'], s['rim'])
        t.done(name + '_tyre', 'rubber')
        rm = Mesh()
        bo = Mesh()
        rim(rm, bo, c, s['rim'], s['W'], side, holes=8 if s is FW else 6)
        rm.done(name + '_rim', 'paint_red')
        bo.done(name + '_nuts', 'galv')
        CTX['parent'] = repr_
        if s is RW:
            # steering knuckle turns with the wheel
            k = Mesh()
            k.cyl(c + Vector((-side * 0.18, 0, 0)), c + Vector((-side * 0.06, 0, 0)), 0.05, seg=14)
            k.cyl(c + Vector((-side * 0.2, 0, -0.1)), c + Vector((-side * 0.2, 0, 0.16)), 0.045, seg=14)
            k.box(c + Vector((-side * 0.2, 0.14, 0.05)), (0.04, 0.26, 0.05), bevel=0.01)
            k.done(name + '_knuckle', 'paint_black')
        CTX['parent'] = root
    # rear steering axle (pendulum beam, tie rod, steering cylinder)
    ax = Mesh()
    zb = RW['Z'] + 0.12
    ax.boxp((-0.82, RW['Y'] - 0.08, zb - 0.07), (0.82, RW['Y'] + 0.08, zb + 0.07), bevel=0.025, seg=2)
    ax.cyl((0, RW['Y'] - 0.25, zb + 0.1), (0, RW['Y'] + 0.25, zb + 0.1), 0.06, seg=16)
    ax.boxp((-0.12, RW['Y'] - 0.3, zb + 0.08), (0.12, RW['Y'] + 0.3, 0.52), bevel=0.02)
    for sx in (-1, 1):
        ax.boxp((sx * 0.8 - 0.05, RW['Y'] - 0.07, zb - 0.2), (sx * 0.8 + 0.05, RW['Y'] + 0.07, zb + 0.12), bevel=0.02)
    ax.cyl((-0.78, RW['Y'] + 0.26, zb - 0.06), (0.78, RW['Y'] + 0.26, zb - 0.06), 0.02, seg=10)
    ax.done('rear_axle', 'paint_black')
    sc = Mesh()
    sc.cyl((0.1, RW['Y'] + 0.2, zb + 0.02), (0.55, RW['Y'] + 0.24, zb - 0.02), 0.035, seg=12)
    sc.done('steer_cyl', 'paint_black')
    sr = Mesh()
    sr.cyl((0.55, RW['Y'] + 0.24, zb - 0.02), (0.72, RW['Y'] + 0.26, zb - 0.05), 0.016, seg=10)
    sr.done('steer_rod', 'chrome')
    hose([(0.12, RW['Y'] + 0.2, zb + 0.06), (0.1, RW['Y'] + 0.0, 0.8), (0.3, 2.6, 0.72), (0.5, 1.5, 0.7)], 0.01, name='hose_steer_1', parent=root)
    hose([(0.5, RW['Y'] + 0.24, zb + 0.02), (0.4, RW['Y'] + 0.0, 0.82), (0.35, 2.6, 0.76), (0.55, 1.5, 0.74)], 0.01, name='hose_steer_2', parent=root)


def unloading_pipe(root):
    base = Vector((1.47, 0.12, 2.26))
    # fixed vertical auger housing (elbow) on the tank corner
    CTX['parent'] = root
    el = Mesh()
    el.cyl((1.47, 0.12, 1.98), (1.47, 0.12, 2.32), 0.15, seg=24)
    el.boxp((1.3, -0.02, 2.0), (1.47, 0.26, 2.22), bevel=0.03)
    el.done('pipe_elbow', 'paint_red')
    pn = node('pipeNode', base, root)
    CTX['parent'] = pn
    L, el_ang = 3.05, rad(15)
    d = Vector((0, math.cos(el_ang), math.sin(el_ang)))
    p0 = base + Vector((0, 0, 0.1))
    p1 = p0 + d * L
    m = Mesh()
    m.cyl(p0, p1, 0.118, seg=24)
    for k in range(1, 4):
        c = p0 + d * (L * k / 4)
        m.lathe([(0.125, -0.02), (0.132, -0.015), (0.132, 0.015), (0.125, 0.02)], 24, c, axis=d)
    m.lathe([(0.0, -0.02), (0.13, -0.02), (0.13, 0.05), (0.0, 0.05)], 24, p0, axis=(0, 0, 1))
    # spout pointing down with a rubber flap
    m.cyl(p1 - d * 0.1, p1 + d * 0.06, 0.13, seg=24)
    m.tube([p1, p1 + Vector((0, 0.02, -0.06)), p1 + Vector((0, 0.04, -0.26))], 0.105, seg=20)
    m.done('pipe_tube', 'paint_red')
    fl = Mesh()
    fl.cyl(p1 + Vector((0, 0.04, -0.25)), p1 + Vector((0, 0.045, -0.36)), 0.11, seg=20, cap=False)
    fl.done('pipe_flap', 'rubber')
    br = Mesh()
    for k in (0.2, 0.55):
        c = p0 + d * (L * k)
        br.cyl(c, c + Vector((0, 0, 0.22)), 0.012, seg=6)
    br.tube([p0 + d * 0.3 + Vector((0, 0, 0.2)), p0 + d * (L * 0.62) + Vector((0, 0, 0.16))], 0.012, seg=6)
    br.done('pipe_truss', 'paint_red')
    lamp = Mesh()
    lamp.boxp(p1 - d * 0.35 + Vector((-0.05, -0.05, 0.12)), p1 - d * 0.35 + Vector((0.05, 0.05, 0.2)), bevel=0.01)
    lamp.done('pipe_lamp', 'paint_black')
    node('dischargeNode', p1 + Vector((0, 0.045, -0.38)), pn)
    CTX['parent'] = root
    # swing cylinder
    c = Mesh()
    c.cyl((1.34, -0.02, 2.36), (1.52, 0.35, 2.4), 0.032, seg=12)
    c.done('pipe_swing_cyl', 'paint_black')
    hose([(1.35, -0.02, 2.4), (1.2, -0.1, 2.3), (0.9, -0.3, 2.1), (-0.4, -0.95, 1.98)], 0.009, name='hose_pipe', parent=root)


def wiring(root):
    """Main harness battery -> rear lamps, lamp feeds, starter cable, throttle/rev cables."""
    CTX['parent'] = root
    cable([(-1.08, -1.05, 1.92), (-0.95, -0.9, 2.05), (-0.86, -0.5, 2.1), (-0.86, 1.0, 2.1), (-0.86, 2.5, 2.1),
           (-0.87, 2.8, 2.4), (-0.86, 4.2, 2.35), (-0.7, 4.9, 1.55), (-0.62, 4.93, 1.45)], r=0.009, name='harness_main_R')
    cable([(-0.86, 4.2, 2.35), (0.0, 4.4, 2.5), (0.86, 4.2, 2.35), (0.7, 4.9, 1.55), (0.62, 4.93, 1.45)], r=0.007, name='harness_rear_L')
    cable([(-1.05, -0.96, 1.93), (-1.1, -0.8, 1.9), (-1.12, 0.0, 2.1), (-1.25, 1.2, 2.13), (-1.3, 2.1, 2.14), (-0.66, 2.3, 2.62)], r=0.011,
          name='starter_cable', mat='plastic')
    cable([(0.62, -1.62, 3.83), (0.66, -1.3, 3.84), (0.72, -1.2, 3.82), (0.73, -0.12, 3.8), (0.9, 0.0, 3.58), (1.2, 0.8, 3.59),
           (1.3, 2.3, 3.59), (0.62, 2.9, 3.62), (0.6, -0.09, 3.9)], r=0.006, name='roof_lamp_cable')
    cable([(0.0, -1.2, 2.9), (0.3, -1.3, 2.6), (0.72, -1.3, 2.4), (0.8, -0.9, 2.16), (0.84, 0.6, 2.18), (0.84, 2.2, 2.4),
           (0.5, 2.2, 2.62)], r=0.004, name='throttle_cable', mat='metal')
    cable([(0.16, -1.2, 2.78), (0.5, -1.35, 2.5), (0.86, -0.4, 2.15), (0.88, 0.12, 1.55)], r=0.004, name='rev_counter_cable', mat='metal')
    cable([(-0.8, 4.9, 2.4), (-0.6, 4.95, 2.3), (0.0, 4.97, 2.2), (0.0, 4.97, 1.74)], r=0.006, name='plate_lamp_cable')
    cable([(0.9, 0.2, 2.13), (0.95, -0.4, 2.12), (0.8, -1.2, 2.12), (0.62, -1.55, 2.2), (0.66, -1.6, 3.6)], r=0.007, name='harness_front_L')
    hose([(-0.95, -0.4, 1.95), (-0.6, -0.9, 1.9), (0.0, -0.95, 1.7), (0.5, -0.9, 1.25), (0.9, 0.12, 1.45)], 0.012,
         name='hose_variator', parent=root)
    hose([(-1.05, 1.95, 1.6), (-0.95, 2.1, 1.9), (-0.7, 2.1, 2.3), (-0.2, 2.02, 2.62)], 0.008, name='fuel_line_feed', parent=root)
    hose([(-0.15, 2.0, 2.7), (-0.6, 2.1, 2.3), (-0.98, 2.2, 1.95), (-1.1, 2.2, 1.97)], 0.006, name='fuel_line_return', parent=root)


def extras(root):
    CTX['parent'] = root
    # second Tyskie crate strapped on the platform next to the ladder
    tyskie_crate(Vector((1.18, -1.28, 2.14)), root, 'crate_platform', missing=(7, 8), yaw=rad(90))
    CTX['parent'] = root
    st = Mesh()
    st.tube([(1.02, -1.5, 2.2), (1.02, -1.5, 2.45), (1.02, -1.06, 2.45), (1.02, -1.06, 2.2)], 0.004, seg=4)
    st.tube([(1.34, -1.5, 2.2), (1.34, -1.5, 2.45), (1.34, -1.06, 2.45), (1.34, -1.06, 2.2)], 0.004, seg=4)
    st.tube([(1.0, -1.28, 2.45), (1.36, -1.28, 2.45)], 0.004, seg=4)
    st.done('crate_rope', 'yellow')
    # jerry can, shovel, wooden block, fire extinguisher on the ladder side
    jc = Mesh()
    jc.boxp((-0.9, -1.5, 2.15), (-0.72, -1.36, 2.6), bevel=0.02)
    jc.boxp((-0.87, -1.47, 2.6), (-0.75, -1.39, 2.64), bevel=0.01)
    jc.cyl((-0.76, -1.43, 2.6), (-0.74, -1.43, 2.68), 0.02, seg=10)
    jc.done('jerrycan', 'green')
    sh = Mesh()
    sh.cyl((-0.855, 3.0, 1.1), (-0.855, 4.3, 1.9), 0.016, seg=8)
    sh.hull([(-0.85, 2.82, 0.95), (-0.85, 3.08, 1.08), (-0.85, 2.92, 0.84), (-0.85, 3.2, 0.98),
             (-0.86, 2.82, 0.95), (-0.86, 3.08, 1.08), (-0.86, 2.92, 0.84), (-0.86, 3.2, 0.98)])
    sh.done('shovel', 'metal')
    wh = Mesh()
    wh.boxp((-0.866, 4.28, 1.86), (-0.845, 4.38, 1.95), bevel=0.01)
    wh.done('shovel_grip', 'wood')
    wb = Mesh()
    wb.boxp((0.86, 4.2, 1.02), (0.99, 4.5, 1.12), bevel=0.012)
    wb.done('wood_block', 'wood')
    tb = Mesh()
    tb.boxp((0.85, 4.1, 1.25), (1.02, 4.6, 1.48), bevel=0.015)
    tb.done('toolbox', 'paint_red')
    tbh = Mesh()
    tbh.boxp((1.02, 4.3, 1.32), (1.035, 4.4, 1.36), bevel=0.005)
    tbh.done('toolbox_latch', 'chrome')
    fx = Mesh()
    fx.lathe([(0.0, 0.0), (0.075, 0.0), (0.075, 0.46), (0.055, 0.5), (0.02, 0.52), (0.0, 0.52)], 18, (1.56, -1.0, 2.2), axis=(0, 0, 1))
    fx.done('extinguisher_ext', 'red_gloss')
    fxb = Mesh()
    for z in (2.3, 2.6):
        fxb.lathe([(0.078, -0.015), (0.082, -0.015), (0.082, 0.015), (0.078, 0.015)], 18, (1.56, -1.0, z), axis=(0, 0, 1))
    fxb.cyl((1.56, -1.0, 2.72), (1.56, -1.0, 2.77), 0.02, seg=8)
    fxb.done('extinguisher_ext_bands', 'plastic')
    # horn and Polish-style number plate holder on the front
    hn = Mesh()
    hn.lathe([(0.0, 0.0), (0.02, 0.0), (0.05, 0.1), (0.055, 0.12), (0.0, 0.12)], 16, (0.5, -1.52, 2.05), axis=(0, -1, 0))
    hn.done('horn', 'chrome')


def fs_nodes(root):
    """Cameras, character targets, lights, work areas, fuel fill target."""
    CTX['parent'] = root
    tgt = node('outdoorCameraTarget', (0, 1.4, 2.1), root)
    # i3d rotation (-15, 180, 0): arm points behind and up
    cam_rot = kit.i3d_euler_to_blender(-15, 180, 0)
    tgt.matrix_basis = root.matrix_world.inverted() @ (Matrix.Translation((0, 1.4, 2.1)) @ cam_rot.to_4x4())
    bpy.context.view_layer.update()
    oc = node('outdoorCamera', (0, 0, 0), tgt, i3d_kind='camera', fov=60.0, near=0.3, far=5000.0)
    oc.matrix_basis = Matrix.Translation(kit.i3d_to_blender_vec((0, 0, 14.0)))
    ic = node('indoorCamera', (0.03, -0.42, 3.36), root, rot=aim_matrix((0, -1, -0.12)), i3d_kind='camera', fov=68.0, near=0.1, far=5000.0)
    for i, p in enumerate(((0, -1.2, 3.6), (0, 1.5, 3.8), (0, 4.5, 2.6))):
        node('cameraRaycastNode%d' % (i + 1), p, root)
    node('playerSkin', (0.03, -0.44, 2.66), root)
    node('leftHandTarget', (0.21, -1.07, 3.04), root, rot=Matrix.Rotation(rad(-35), 3, 'X'))
    node('rightHandTarget', (-0.15, -1.07, 3.04), root, rot=Matrix.Rotation(rad(-35), 3, 'X'))
    node('leftFootTarget', (0.14, -1.2, 2.3), root)
    node('rightFootTarget', (-0.08, -1.2, 2.3), root)
    node('exitPoint', (2.3, -1.7, 0.0), root)
    node('enterReferenceNode', (1.7, -1.8, 1.0), root)
    # real lights (engine spot lights), aimed forward/back
    zf = 3.82
    for nm, p, d, typ in (('frontLightLow', (0.0, -1.72, zf + 0.03), (0, -1, -0.28), 0),
                          ('highBeam', (0.0, -1.72, zf + 0.03), (0, -1, -0.1), 3),
                          ('workLightFront', (0.0, -1.72, zf + 0.18), (0, -1, -0.55), 1),
                          ('workLightBack', (0.6, -0.02, zf + 0.18), (0, 1, -0.5), 2),
                          ('pipeLight', (1.47, 3.0, 3.35), (0.4, 0.3, -1.0), 1)):
        par = root
        if nm == 'pipeLight':
            par = bpy.data.objects['pipeNode']
        node(nm, p, par, rot=aim_matrix(d), i3d_kind='light', light_type=typ,
             range=45.0 if typ == 3 else 28.0, cone=60.0 if typ != 1 else 80.0)
    # combine straw work areas at the rear (swath / chopper)
    for nm in ('swath', 'chopper'):
        w = 0.8 if nm == 'swath' else 2.6
        node(nm + 'AreaStart', (w, 5.3, 0.3), root)
        node(nm + 'AreaWidth', (-w, 5.3, 0.3), root)
        node(nm + 'AreaHeight', (w, 5.8, 0.3), root)
    node('fuelFillNode', (-1.05, 1.97, 2.15), root)


def collisions_combine(root):
    CTX['parent'] = root
    def col(name, p0, p1, kind='child'):
        m = Mesh()
        m.boxp(p0, p1)
        return m.done(name, 'dark', smooth=0, col=kind)
    col('bizon_col_main', (-0.84, -1.0, 0.62), (0.84, 2.72, 2.2), 'main')
    col('col_top', (-1.33, -0.06, 2.1), (1.33, 2.96, 3.6))
    col('col_hood', (-0.86, 2.7, 1.0), (0.86, 4.97, 2.6))
    col('col_cab', (-0.8, -1.62, 2.1), (0.84, -0.08, 3.96))
    col('col_platform', (-0.97, -1.58, 1.95), (1.56, -0.04, 2.16))
    col('col_axle', (-1.02, -0.3, 0.55), (1.02, 0.3, 1.0))
    m = Mesh()
    m.boxp((-1.15, 1.9, 2.1), (-0.95, 2.05, 2.25))
    m.done('exactFillRootNodeFuel', 'dark', smooth=0, col='fill')


def build_combine():
    coll = bpy.data.collections.new('combine')
    bpy.context.scene.collection.children.link(coll)
    CTX['coll'] = coll
    root = node('bizonZ056_main_component', (0, 0, 0), None, i3d_component=1)
    CTX['parent'] = root
    body_lower(root)
    top_block(root)
    engine_bay(root)
    rear_hood(root)
    platform_cab(root)
    feeder_house(root)
    drives_left(root)
    drives_right(root)
    wheels(root)
    unloading_pipe(root)
    wiring(root)
    extras(root)
    fs_nodes(root)
    collisions_combine(root)
    return root


# ================================================================ header
def build_header():
    coll = bpy.data.collections.new('header')
    bpy.context.scene.collection.children.link(coll)
    CTX['coll'] = coll
    root = node('headerZ056_main_component', (0, 0, 0), None, i3d_component=1)
    CTX['parent'] = root
    yb, yk = -2.45, -3.98      # back wall / knife line
    hw = 2.15
    red = Mesh()
    red.boxp((-hw, yb - 0.01, 0.18), (hw, yb + 0.01, 1.0), bevel=0.004)                  # back wall
    red.hull([(-hw, yb, 0.18), (hw, yb, 0.18), (-hw, yk + 0.08, 0.1), (hw, yk + 0.08, 0.1),
              (-hw, yb, 0.2), (hw, yb, 0.2), (-hw, yk + 0.08, 0.12), (hw, yk + 0.08, 0.12)])     # floor pan
    red.boxp((-hw - 0.02, yb - 0.08, 0.96), (hw + 0.02, yb + 0.06, 1.1), bevel=0.02)      # top beam
    red.boxp((-hw - 0.02, yb - 0.1, 0.1), (hw + 0.02, yb + 0.04, 0.24), bevel=0.02)       # bottom beam
    for sx in (-1, 1):
        x = sx * (hw + 0.005)
        red.poly_prism([(yb + 0.06, 0.1), (yk - 0.05, 0.08), (yk - 0.05, 0.3), (yb - 0.5, 1.08), (yb + 0.06, 1.1)],
                       (x, 0, 0), (0, 1, 0), (0, 0, 1), (-sx, 0, 0), 0.008, bevel=0.003)
        red.hull([(x, yk - 0.05, 0.08), (x, yk - 0.05, 0.36), (x + sx * 0.08, yk - 0.05, 0.08), (x + sx * 0.08, yk - 0.05, 0.36),
                  (x + sx * 0.02, yk - 0.45, 0.1), (x + sx * 0.05, yk - 0.45, 0.1), (x + sx * 0.02, yk - 0.3, 0.2), (x + sx * 0.05, yk - 0.3, 0.2)])
    # opening into the feeder
    red.done('header_body', 'paint_red')
    dk = Mesh()
    dk.boxp((-0.56, yb + 0.012, 0.3), (0.56, yb + 0.015, 0.78))
    dk.done('header_throat', 'dark', smooth=0)
    fr = Mesh()
    fr.boxp((-0.7, yb + 0.01, 0.24), (0.7, yb + 0.06, 0.3), bevel=0.01)
    fr.boxp((-0.7, yb + 0.01, 0.78), (0.7, yb + 0.06, 0.84), bevel=0.01)
    for sx in (-1, 1):
        fr.boxp((sx * 0.62 - 0.03, yb + 0.01, 0.24), (sx * 0.62 + 0.03, yb + 0.06, 0.84), bevel=0.01)
    fr.done('header_hitch_frame', 'paint_black')
    # cutter bar: guards (fingers) + knife sections
    cb = Mesh()
    cb.boxp((-hw, yk + 0.02, 0.085), (hw, yk + 0.1, 0.115), bevel=0.006)
    n = int(2 * hw / 0.0762)
    for i in range(n):
        x = -hw + (i + 0.5) * 0.0762
        cb.hull([(x - 0.018, yk + 0.06, 0.09), (x + 0.018, yk + 0.06, 0.09), (x - 0.018, yk + 0.06, 0.12), (x + 0.018, yk + 0.06, 0.12),
                 (x - 0.006, yk - 0.12, 0.095), (x + 0.006, yk - 0.12, 0.095), (x - 0.004, yk - 0.12, 0.105), (x + 0.004, yk - 0.12, 0.105)])
    cb.done('cutter_guards', 'paint_black')
    kn_node = node('knife', (0, yk, 0.1), root)
    CTX['parent'] = kn_node
    kn = Mesh()
    kn.boxp((-hw, yk + 0.01, 0.098), (hw, yk + 0.03, 0.104))
    for i in range(n):
        x = -hw + (i + 0.5) * 0.0762
        kn.hull([(x - 0.036, yk + 0.02, 0.1), (x + 0.036, yk + 0.02, 0.1), (x - 0.008, yk - 0.06, 0.1), (x + 0.008, yk - 0.06, 0.1),
                 (x - 0.036, yk + 0.02, 0.104), (x + 0.036, yk + 0.02, 0.104), (x - 0.008, yk - 0.06, 0.104), (x + 0.008, yk - 0.06, 0.104)])
    kn.done('knife_sections', 'metal')
    CTX['parent'] = root
    # skids
    sk = Mesh()
    for x in (-1.6, -0.55, 0.55, 1.6):
        sk.hull([(x - 0.06, yb, 0.02), (x + 0.06, yb, 0.02), (x - 0.06, yk + 0.25, 0.02), (x + 0.06, yk + 0.25, 0.02),
                 (x - 0.06, yb, 0.12), (x + 0.06, yb, 0.12), (x - 0.06, yk + 0.12, 0.09), (x + 0.06, yk + 0.12, 0.09)])
    sk.done('skids', 'metal')
    # auger with opposing flights and centre fingers
    au_c = Vector((0, -2.98, 0.42))
    an = node('auger', au_c, root, anim_speed=1.0, anim_axis=1)
    CTX['parent'] = an
    a = Mesh()
    a.cyl((-hw + 0.03, au_c.y, au_c.z), (hw - 0.03, au_c.y, au_c.z), 0.14, seg=24)
    for side in (-1, 1):
        pts_o, pts_i = [], []
        steps = 120
        for k in range(steps + 1):
            t = k / steps
            x = side * (0.62 + t * (hw - 0.7))
            ang = side * t * (hw - 0.7) / 0.5 * TAU
            pts_o.append((x, au_c.y + 0.27 * math.cos(ang), au_c.z + 0.27 * math.sin(ang)))
            pts_i.append((x, au_c.y + 0.14 * math.cos(ang), au_c.z + 0.14 * math.sin(ang)))
        bm = a.bm
        vo = [bm.verts.new(p) for p in pts_o]
        vi = [bm.verts.new(p) for p in pts_i]
        vo2 = [bm.verts.new((p[0] + 0.006, p[1], p[2])) for p in pts_o]
        vi2 = [bm.verts.new((p[0] + 0.006, p[1], p[2])) for p in pts_i]
        for k in range(steps):
            bm.faces.new((vi[k], vo[k], vo[k + 1], vi[k + 1]))
            bm.faces.new((vi2[k + 1], vo2[k + 1], vo2[k], vi2[k]))
            bm.faces.new((vo[k], vo2[k], vo2[k + 1], vo[k + 1]))
    for k in range(10):
        x = -0.5 + k * 0.11
        ang = k * 1.1
        d = Vector((0, math.cos(ang), math.sin(ang)))
        a.cyl(Vector((x, au_c.y, au_c.z)) + d * 0.12, Vector((x, au_c.y, au_c.z)) + d * 0.3, 0.008, seg=6)
    a.done('auger_mesh', 'paint_red')
    CTX['parent'] = root
    # reel: arms, spiders, 6 tine bars with spring tines
    rc = Vector((0, -3.5, 1.3))
    arms = Mesh()
    for sx in (-1, 1):
        x = sx * (hw + 0.06)
        arms.boxp((x - 0.04, yb - 0.2, 1.02), (x + 0.04, rc.y + 0.05, 1.12), bevel=0.012)
        arms.cyl((x, yb - 0.15, 1.05), (x + 0.0, yb - 0.1, 0.55), 0.03, seg=10)
    arms.done('reel_arms', 'paint_red')
    rcyl = Mesh()
    for sx in (-1, 1):
        x = sx * (hw + 0.1)
        rcyl.cyl((x, yb - 0.25, 0.62), (x, rc.y + 0.45, 1.0), 0.03, seg=10)
    rcyl.done('reel_cylinders', 'paint_black')
    rn = node('reel', rc, root, anim_speed=0.35, anim_axis=1)
    CTX['parent'] = rn
    rl = Mesh()
    rl.cyl((-hw - 0.08, rc.y, rc.z), (hw + 0.08, rc.y, rc.z), 0.05, seg=16)
    for x in (-hw + 0.05, 0.0, hw - 0.05):
        for k in range(6):
            ang = TAU * k / 6
            d = Vector((0, math.cos(ang), math.sin(ang)))
            rl.box(Vector((x, rc.y, rc.z)) + d * 0.25, (0.012, 0.5, 0.035), rot=Vector((0, 1, 0)).rotation_difference(d).to_matrix())
    for k in range(6):
        ang = TAU * k / 6
        c = Vector((0, rc.y + 0.5 * math.cos(ang), rc.z + 0.5 * math.sin(ang)))
        rl.cyl(c - Vector((hw, 0, 0)), c + Vector((hw, 0, 0)), 0.025, seg=10)
    rl.done('reel_structure', 'paint_red')
    tn = Mesh()
    for k in range(6):
        ang = TAU * k / 6
        c = Vector((0, rc.y + 0.5 * math.cos(ang), rc.z + 0.5 * math.sin(ang)))
        for i in range(int(2 * hw / 0.1)):
            x = -hw + 0.05 + i * 0.1
            p0 = c + Vector((x, 0, 0))
            tn.cyl(p0, p0 + Vector((0, -0.03, -0.24)), 0.0035, seg=4, cap=False)
    tn.done('reel_tines', 'metal')
    CTX['parent'] = root
    # drive on the left end: belt + guard + knife wobble box
    dv = Mesh()
    dv.boxp((hw + 0.01, yb - 0.6, 0.2), (hw + 0.11, yb + 0.05, 0.95), bevel=0.02) if False else None
    for key, (y, z, r) in {'hdrInput': (yb - 0.1, 0.62, 0.13), 'hdrAuger': (au_c.y, au_c.z, 0.16)}.items():
        nd = node('pl_' + key, (hw + 0.07, y, z), root, anim_speed=0.8, anim_axis=1)
        CTX['parent'] = nd
        m = Mesh()
        pulley(m, (hw + 0.07, y, z), r, width=0.034, spokes=4)
        m.done(key + '_pulley', 'paint_black')
        CTX['parent'] = root
    belt(dv, hw + 0.07, (yb - 0.1, 0.62), 0.118, (au_c.y, au_c.z), 0.148)
    dv.done('header_belt', 'rubber')
    gd = Mesh()
    gd.boxp((hw + 0.11, yb - 0.75, 0.25), (hw + 0.12, yb + 0.02, 0.85), bevel=0.02)
    gd.boxp((hw + 0.0, yb - 0.75, 0.1), (hw + 0.1, yb - 0.55, 0.3), bevel=0.02)
    gd.done('header_drive_guard', 'paint_red')
    for sx in (-1, 1):
        decal_plane('decal_stripes_%d' % sx, (sx * (hw + 0.125), yb - 0.35, 0.55), (0, -sx, 0), (0, 0, 1), (0.34, 0.34), 'stripes',
                    offset=0.001)
    decal_plane('decal_bizon_header', (0.0, yb + 0.012, 0.93), (-1, 0, 0), (0, 0, 1), (0.6, 0.18), 'bizon') if False else None
    decal_plane('decal_bizon_header_back', (1.2, yb + 0.07, 1.03), (1, 0, 0), (0, 0, 1), (0.36, 0.105), 'bizon')
    # FS nodes
    node('attacherJointInput', FEED_FRONT - (FEED_FRONT - FEED_PIVOT).normalized() * 0.03, root)
    node('cutAreaStart', (hw - 0.02, yk - 0.05, 0.1), root)
    node('cutAreaWidth', (-hw + 0.02, yk - 0.05, 0.1), root)
    node('cutAreaHeight', (hw - 0.02, yk + 0.45, 0.1), root)
    node('groundReferenceNode', (0.0, yk + 0.3, 0.05), root)
    m = Mesh()
    m.boxp((-hw - 0.05, yk - 0.1, 0.08), (hw + 0.05, yb + 0.05, 1.12))
    m.done('header_col_main', 'dark', smooth=0, col='main')
    m = Mesh()
    m.boxp((-hw, rc.y - 0.55, rc.z - 0.55), (hw, rc.y + 0.55, rc.z + 0.55))
    m.done('header_col_reel', 'dark', smooth=0, col='child')
    return root


# ================================================================ main
materials()
combine = build_combine()
header = build_header()
CTX['coll'] = None
CTX['parent'] = None
# UVs: world box projection for tileable materials
for ob in bpy.data.objects:
    if ob.type == 'MESH' and not ob.get('keep_uv') and not ob.get('col'):
        mat = ob.data.materials[0]
        box_uv(ob, tile=mat['game'].get('tile', 1.0) if 'game' in mat else 1.0)
stats = {c.name: sum(len(o.data.polygons) for o in c.objects if o.type == 'MESH') for c in bpy.data.collections}
print('POLYGONS', stats, 'objects', len(bpy.data.objects))
bpy.ops.wm.save_as_mainfile(filepath=OUT)
