"""Bizon Super Z056 body, rebuilt after photos of real Z056 Super machines (1987-1989).

Layout (front axle at y=0; Blender X right, Y forward, Z up):
  * tall block behind the operator platform: grain tank in front, transverse SW-400 engine bay behind it
    (louvres + wire mesh on the left, radiator with rotary screen on the right, muffler and oil-bath air
    cleaner on the roof), overhanging the narrow threshing body on a sloped hopper;
  * lower straw-walker hood to the rear, walkers showing at the straw outlet behind a rubber curtain;
  * belt drives exposed on the left, elevators, hydraulics and the ladder on the right.
Large surfaces are thin sheets with both faces modelled, slight oil-canning and dents, joined by formed
bends, angle profiles, joint strips and rows of painted-over bolts.
"""
import math
import random

import bmesh
import bpy
from mathutils import Matrix, Vector, noise

import blender_kit as K
import bizon_engine as EN
from blender_kit import belt, box, cyl, decal, empty, gear, hose, poly_prism, pulley, sweep, tube

XT, YTF, YTE, YTR = 1.12, 0.34, -1.05, -2.35     # tall block: half width, front, tank|engine seam, rear
ZTB, ZTOP, RB = 1.95, 3.40, 0.045                 # side wall foot, roof, formed edge radius
XL, YLF, YLS, ZHB = 0.80, 0.45, -2.60, 1.66       # threshing body: half width, front, step, hopper foot
XLR = 0.66                                         # rear body half width (clears the steered rear wheels)
XH, YHR, ZH0, ZHT = 0.86, -5.0, 1.55, 2.72        # straw walker hood
ENGINE = Vector((0.05, -1.70, 2.45))              # SW-400 origin; crank along X, flywheel on the left
PTO = Vector((-1.24, -1.70, 2.41))                # engine output pulley (main drive)
SCREEN = Vector((XT + 0.10, -1.70, 2.65))         # rotary screen centre
MUFFLER_X = 0.35
EXHAUST_TIP = Vector((MUFFLER_X, -2.46, 4.0))
FUEL_TANK = Vector((0.45, -2.78, 2.98))
VALVES = Vector((0.95, 0.56, 1.80))

ANIM = {}
REG = {}


# ------------------------------------------------------------------ helpers

def _steps(a, b, step):
    n = max(1, int(round(abs(b - a) / step)))
    return [a + (b - a) * i / n for i in range(n + 1)]


def _rot_to(d):
    """4x4 rotation taking local +Z onto direction d."""
    d = Vector(d).normalized()
    return d.to_track_quat("Z", "X" if abs(d.y) > 0.9 else "Y").to_matrix().to_4x4()


def _breaks(L, cell, cuts):
    cuts = [min(max(c, 0.0), L) for c in cuts]
    n = max(1, int(math.ceil(L / cell)))
    grid = [L * i / n for i in range(1, n)]
    vals = [0.0, L] + cuts + [g for g in grid if all(abs(g - c) > cell * 0.3 for c in cuts)]
    out = []
    for v in sorted(vals):
        if not out or v - out[-1] > 1e-4:
            out.append(v)
    return out


def sheet(name, origin, u, v, w, h, mat, parent, t=0.004, cell=0.075, amp=0.0022, dents=0, holes=(), seed=None):
    """Thin formed panel spanning origin + u*[0,w] + v*[0,h] (outward normal u x v).

    Low-frequency oil-canning and a few dents, fading out towards the clamped edges; holes are
    (u0, u1, v0, v1) rectangles, the grid snaps to them and their rims are closed."""
    O = Vector(origin)
    U, V = Vector(u).normalized(), Vector(v).normalized()
    N = U.cross(V).normalized()
    rnd = random.Random(seed if seed is not None else sum(map(ord, name)) * 7)
    us = _breaks(w, cell, [c for hh in holes for c in hh[:2]])
    vs = _breaks(h, cell, [c for hh in holes for c in hh[2:]])
    off = Vector((rnd.uniform(0, 90), rnd.uniform(0, 90), rnd.uniform(0, 90)))
    dl = [(rnd.uniform(0.12, 0.88) * w, rnd.uniform(0.1, 0.9) * h, rnd.uniform(0.07, 0.15),
           rnd.uniform(0.002, 0.0045)) for _ in range(dents)]

    def disp(a, b):
        f = math.sqrt(max(0.0, math.sin(math.pi * a / w)) * max(0.0, math.sin(math.pi * b / h)))
        d = amp * f * (noise.noise(Vector((a * 1.7, b * 1.7, 0.5)) + off) +
                       0.35 * noise.noise(Vector((a * 5.3, b * 5.3, 2.5)) + off))
        for cu, cv, r, dep in dl:
            q = ((a - cu) ** 2 + (b - cv) ** 2) / (r * r)
            if q < 9.0:
                d -= dep * math.exp(-q) * f
        return d

    def in_hole(a, b):
        return any(u0 < a < u1 and v0 < b < v1 for u0, u1, v0, v1 in holes)

    cells = [(i, j) for i in range(len(us) - 1) for j in range(len(vs) - 1)
             if not in_hole((us[i] + us[i + 1]) / 2, (vs[j] + vs[j + 1]) / 2)]
    used = set()
    for i, j in cells:
        used.update(((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)))
    bm = bmesh.new()
    vo, vi = {}, {}
    for i, j in used:
        a, b = us[i], vs[j]
        base = O + U * a + V * b
        d = disp(a, b)
        vo[i, j] = bm.verts.new(base + N * d)
        vi[i, j] = bm.verts.new(base + N * (d - t))
    cnt = {}
    for i, j in cells:
        q = ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1))
        bm.faces.new([vo[k] for k in q])
        bm.faces.new([vi[k] for k in reversed(q)])
        for k in range(4):
            e = frozenset((q[k], q[(k + 1) % 4]))
            cnt[e] = cnt.get(e, 0) + 1
    for i, j in cells:
        q = ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1))
        for k in range(4):
            a_, b_ = q[k], q[(k + 1) % 4]
            if cnt[frozenset((a_, b_))] == 1:
                bm.faces.new((vo[b_], vo[a_], vi[a_], vi[b_]))
    return K.mesh_from_bm(name, bm, mat, parent, smooth_angle=40)


def bend(name, c0, c1, e1, e2, r, mat, parent, t=0.004, segs=6):
    """Formed quarter-round sheet edge around the axis c0->c1, from direction e1 to e2."""
    c0, c1, e1, e2 = map(Vector, (c0, c1, e1, e2))
    arc = [math.pi / 2 * k / segs for k in range(segs + 1)]
    bm = bmesh.new()
    rings = []
    for c in (c0, c1):
        rings.append(([bm.verts.new(c + (e1 * math.cos(a) + e2 * math.sin(a)) * r) for a in arc],
                      [bm.verts.new(c + (e1 * math.cos(a) + e2 * math.sin(a)) * (r - t)) for a in arc]))
    (o0, i0), (o1, i1) = rings
    for k in range(segs):
        bm.faces.new((o0[k], o0[k + 1], o1[k + 1], o1[k]))
        bm.faces.new((i0[k + 1], i0[k], i1[k], i1[k + 1]))
        bm.faces.new((o0[k + 1], o0[k], i0[k], i0[k + 1]))
        bm.faces.new((o1[k], o1[k + 1], i1[k + 1], i1[k]))
    bm.faces.new((o0[0], o1[0], i1[0], i0[0]))
    bm.faces.new((o1[-1], o0[-1], i0[-1], i1[-1]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return K.mesh_from_bm(name, bm, mat, parent, smooth_angle=50)


def angle(name, a, b, n1, n2, mat="red", parent=None, s=0.045, t=0.005):
    """Angle profile over an outside corner a->b; n1, n2 are the outward normals of the two faces."""
    a, b, A, B = Vector(a), Vector(b), Vector(n1), Vector(n2)
    prof = [(0, -s), (t, -s), (t, t), (-s, t), (-s, 0), (0, 0)]
    bm = bmesh.new()
    ra = [bm.verts.new(a + A * p + B * q) for p, q in prof]
    rb = [bm.verts.new(b + A * p + B * q) for p, q in prof]
    for k in range(6):
        kk = (k + 1) % 6
        bm.faces.new((ra[k], ra[kk], rb[kk], rb[k]))
    bm.faces.new(ra)
    bm.faces.new(list(reversed(rb)))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return K.mesh_from_bm(name, bm, mat, parent, smooth_angle=30)


def bolts(name, pts, normal, mat="red", parent=None, r=0.0085, h=0.0065, washer=True):
    """Hex bolt heads (with washers) sitting on a surface with the given outward normal."""
    R = _rot_to(normal)
    bm = bmesh.new()
    for p in pts:
        T = Matrix.Translation(Vector(p)) @ R
        if washer:
            res = bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=8, radius1=r * 1.5,
                                        radius2=r * 1.5, depth=0.003)
            bmesh.ops.transform(bm, matrix=T @ Matrix.Translation((0, 0, -0.0005)), verts=res["verts"])
        res = bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=6, radius1=r, radius2=r * 0.9,
                                    depth=h)
        bmesh.ops.transform(bm, matrix=T @ Matrix.Translation((0, 0, h / 2 - 0.001)), verts=res["verts"])
    return K.mesh_from_bm(name, bm, mat, parent, smooth_angle=25)


def bead(name, a, b, normal, mat="red", parent=None, w=0.036, hgt=0.0075):
    """Pressed stiffening bead along a->b on a panel, tapering into the sheet at both ends."""
    a, b, N = Vector(a), Vector(b), Vector(normal).normalized()
    T = b - a
    L = T.length
    T.normalize()
    S = T.cross(N).normalized()
    tap = w * 1.6
    xs = sorted(set([tap * f for f in (0, 0.2, 0.45, 0.7)] + [L - tap * f for f in (0, 0.2, 0.45, 0.7)] +
                    _steps(tap, L - tap, 0.08)))
    prof = [(math.cos(math.pi * k / 8), math.sin(math.pi * k / 8)) for k in range(9)]
    bm = bmesh.new()
    rings = []
    for x in xs:
        sc = math.sin(min(1.0, min(x, L - x) / tap) * math.pi / 2)
        rings.append([bm.verts.new(a + T * x + S * (c * w * 0.5 * max(sc, 0.3)) + N * (s * hgt * sc - 0.002))
                      for c, s in prof])
    for i in range(len(rings) - 1):
        for k in range(8):
            bm.faces.new((rings[i][k], rings[i + 1][k], rings[i + 1][k + 1], rings[i][k + 1]))
    return K.mesh_from_bm(name, bm, mat, parent, smooth_angle=70)


def wire_mesh(name, origin, u, v, w, h, mat="metalDark", parent=None, pitch=0.04, r=0.0022):
    """Welded wire mesh (guards, grilles)."""
    O = Vector(origin)
    U, V = Vector(u).normalized(), Vector(v).normalized()
    N = U.cross(V).normalized()
    bm = bmesh.new()

    def rod(p0, p1):
        d = p1 - p0
        res = bmesh.ops.create_cone(bm, cap_ends=False, segments=5, radius1=r, radius2=r, depth=d.length)
        bmesh.ops.transform(bm, matrix=Matrix.Translation((p0 + p1) / 2) @ _rot_to(d), verts=res["verts"])
    nu, nv = max(1, round(w / pitch)), max(1, round(h / pitch))
    for i in range(nu + 1):
        rod(O + U * (w * i / nu) + N * r, O + U * (w * i / nu) + V * h + N * r)
    for j in range(nv + 1):
        rod(O + V * (h * j / nv) - N * r * 0.3, O + V * (h * j / nv) + U * w - N * r * 0.3)
    return K.mesh_from_bm(name, bm, mat, parent, smooth_angle=80)


def disc_mesh(name, center, radius, parent, pitch=0.032, r=0.0024, mat="galv"):
    """Perforated screen face in the YZ plane: wire chords clipped to a circle."""
    C = Vector(center)
    bm = bmesh.new()
    n = int(radius / pitch)
    for axis in (0, 1):
        for k in range(-n, n + 1):
            c = k * pitch
            half = math.sqrt(max(radius * radius - c * c, 0.0))
            if half < 0.01:
                continue
            if axis == 0:
                p0, p1 = C + Vector((0, c, -half)), C + Vector((0, c, half))
            else:
                p0, p1 = C + Vector((0.002, -half, c)), C + Vector((0.002, half, c))
            d = p1 - p0
            res = bmesh.ops.create_cone(bm, cap_ends=False, segments=5, radius1=r, radius2=r, depth=d.length)
            bmesh.ops.transform(bm, matrix=Matrix.Translation((p0 + p1) / 2) @ _rot_to(d), verts=res["verts"])
    return K.mesh_from_bm(name, bm, mat, parent, smooth_angle=80)


SQ = lambda s: [(-s, -s), (s, -s), (s, s), (-s, s)]  # noqa: E731


def frame_rect(name, corners, mat, parent, s=0.014):
    return sweep(name, corners, 0, mat, parent, closed=True, profile=SQ(s))


def smooth_path(pts, n=6):
    """Catmull-Rom through the control points."""
    P = [Vector(p) for p in pts]
    out = []
    for i in range(len(P) - 1):
        p0, p1, p2, p3 = P[max(i - 1, 0)], P[i], P[i + 1], P[min(i + 2, len(P) - 1)]
        for k in range(n):
            t = k / n
            out.append(0.5 * (2 * p1 + (p2 - p0) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t +
                              (3 * p1 - p0 - 3 * p2 + p3) * t * t * t))
    out.append(P[-1])
    return out


def cable(name, pts, r, mat, parent, clips=(), clip_mat="metalDark", n=6, verts=6):
    """Cable/hose through control points with P-clips at the given control-point indices."""
    o = sweep(name, smooth_path(pts, n), r, mat, parent, verts=verts)
    for k, idx in enumerate(clips):
        p = Vector(pts[idx])
        d = Vector(pts[min(idx + 1, len(pts) - 1)]) - Vector(pts[max(idx - 1, 0)])
        c = tube("%s_clip%d" % (name, k), r * 1.9, r * 1.02, 0.014, (0, 0, 0), clip_mat, parent, axis="Z", verts=10)
        c.rotation_euler = _rot_to(d).to_euler()
        c.location = p
    return o


def flange_bearing(name, loc, sx, parent):
    """4-bolt flange bearing on a side wall (sx = outward direction)."""
    x, y, z = loc
    box(name + "Plate", (0.012, 0.13, 0.13), (x, y, z), "metalDark", parent, bevel=0.012)
    cyl(name + "Boss", 0.05, 0.05, (x + sx * 0.03, y, z), "metalDark", parent, axis="X", verts=20, bevel=0.006)
    bolts(name + "Bolts", [(x + sx * 0.006, y + dy, z + dz) for dy in (-0.045, 0.045) for dz in (-0.045, 0.045)],
          (sx, 0, 0), "steel", parent, r=0.007, washer=False)
    cyl(name + "Grease", 0.006, 0.025, (x + sx * 0.03, y, z + 0.06), "yellow", parent, axis="Z", verts=6)


def door(name, x, sx, y0, y1, z0, z1, parent, handle_at_front=True):
    """Proud access door with rubber seal, two hinges and a T-latch."""
    w, h = abs(y0 - y1), z1 - z0
    ya, yb = max(y0, y1), min(y0, y1)
    xo = x + sx * 0.006
    if sx < 0:
        sheet(name, (xo, ya, z0), (0, -1, 0), (0, 0, 1), w, h, "red", parent, t=0.003, amp=0.0012)
    else:
        sheet(name, (xo, yb, z0), (0, 1, 0), (0, 0, 1), w, h, "red", parent, t=0.003, amp=0.0012)
    xs = x + sx * 0.004
    frame_rect(name + "Seal", [(xs, ya + 0.008, z0 - 0.008), (xs, yb - 0.008, z0 - 0.008),
                               (xs, yb - 0.008, z1 + 0.008), (xs, ya + 0.008, z1 + 0.008)], "rubber", parent, s=0.005)
    hy, ly = (yb, ya) if handle_at_front else (ya, yb)
    for k, z in enumerate((z0 + 0.1, z1 - 0.1)):
        cyl("%sHinge%d" % (name, k), 0.011, 0.09, (x + sx * 0.016, hy, z), "metalDark", parent, axis="Z", verts=10)
        box("%sLeaf%d" % (name, k), (0.004, 0.07, 0.07), (x + sx * 0.011, hy + (0.035 if hy == yb else -0.035), z),
            "metalDark", parent, bevel=0.002)
    lz = (z0 + z1) / 2
    ly2 = ly + (-0.06 if ly == ya else 0.06)
    cyl(name + "LatchBoss", 0.018, 0.02, (x + sx * 0.018, ly2, lz), "steel", parent, axis="X", verts=12)
    box(name + "LatchT", (0.012, 0.018, 0.08), (x + sx * 0.032, ly2, lz), "metalDark", parent, bevel=0.004)


def louvres(name, xf, sx, ya, yb, z0, z1, n, parent, ang=0.62):
    """Pressed louvre slats in a side opening at x=xf (sx outward), slats running along Y."""
    h = (z1 - z0) / n
    L = abs(ya - yb) - 0.012
    yc = (ya + yb) / 2
    for i in range(n):
        zc = z0 + h * (i + 0.5)
        box("%sSlat%d" % (name, i), (0.003, L, h * 1.3), (xf + sx * 0.25 * h * 1.3 * math.sin(ang), yc, zc), "red",
            parent, bevel=0.001, rot=(0, -sx * ang, 0))
    xs = xf + sx * 0.012
    frame_rect(name + "Frame", [(xs, ya, z0), (xs, yb, z0), (xs, yb, z1), (xs, ya, z1)], "red", parent, s=0.013)


def mesh_window(name, xf, sx, ya, yb, z0, z1, parent):
    xm = xf + sx * 0.004
    if sx < 0:
        wire_mesh(name, (xm, ya, z0), (0, -1, 0), (0, 0, 1), abs(ya - yb), z1 - z0, "metalDark", parent)
    else:
        wire_mesh(name, (xm, yb, z0), (0, 1, 0), (0, 0, 1), abs(ya - yb), z1 - z0, "metalDark", parent)
    xs = xf + sx * 0.012
    frame_rect(name + "Frame", [(xs, ya, z0), (xs, yb, z0), (xs, yb, z1), (xs, ya, z1)], "red", parent, s=0.013)


def guard_arc(name, x, c, r, a0, a1, width, parent, n=16):
    pts = [(x, c[0] + math.cos(a) * r, c[1] + math.sin(a) * r) for a in
           [a0 + (a1 - a0) * k / n for k in range(n + 1)]]
    return sweep(name, pts, 0, "red", parent, profile=[(-width / 2, -0.003), (width / 2, -0.003),
                                                       (width / 2, 0.003), (-width / 2, 0.003)])


# ------------------------------------------------------------------ body parts

def build(body, shake_engine, anim, reg):
    global ANIM, REG
    ANIM, REG = anim, reg
    tall_block(body)
    tank_details(body)
    engine_bay(body, shake_engine)
    lower_body(body)
    rear_hood(body)
    right_side(body)
    left_drives(body)
    wiring(body)


def tall_block(p):
    t = empty("tallBlock", (0, 0, 0), p)
    zs = ZTOP - RB
    hs = zs - ZTB
    wt, we = YTF - YTE, YTE - YTR
    sheet("tankSideL", (-XT, YTF, ZTB), (0, -1, 0), (0, 0, 1), wt, hs, "red", t, dents=3)
    sheet("tankSideR", (XT, YTE, ZTB), (0, 1, 0), (0, 0, 1), wt, hs, "red", t, dents=2)
    # engine bay sides: left = louvres over two mesh windows (PTO bearing between them), right = radiator
    sheet("engSideL", (-XT, YTE, ZTB), (0, -1, 0), (0, 0, 1), we, hs, "red", t, dents=2,
          holes=[(0.10, 1.20, 0.80, 1.30), (0.10, 0.50, 0.12, 0.70), (0.80, 1.20, 0.12, 0.70)])
    sheet("engSideR", (XT, YTR, ZTB), (0, 1, 0), (0, 0, 1), we, hs, "red", t, dents=1,
          holes=[(0.20, 1.10, 0.25, 1.15)])
    wtop = 2 * (XT - RB)
    sheet("tankTop", (-XT + RB, YTE, ZTOP), (1, 0, 0), (0, 1, 0), wtop, wt, "red", t, dents=1,
          holes=[(0.22, wtop - 0.22, 0.20, wt - 0.18)])
    sheet("engTop", (-XT + RB, YTR, ZTOP), (1, 0, 0), (0, 1, 0), wtop, we, "red", t,
          holes=[(0.18, wtop - 0.18, 0.14, we - 0.14)])
    for sx in (-1, 1):
        bend("topBend%d" % sx, (sx * (XT - RB), YTR, ZTOP - RB), (sx * (XT - RB), YTF, ZTOP - RB), (sx, 0, 0),
             (0, 0, 1), RB, "red", t)
    sheet("tankFront", (XT, YTF, ZTB), (-1, 0, 0), (0, 0, 1), 2 * XT, ZTOP - ZTB, "red", t, dents=1)
    hr = ZTOP - ZHT + 0.05
    sheet("engRear", (-XT, YTR, ZHT - 0.05), (1, 0, 0), (0, 0, 1), 2 * XT, hr, "red", t,
          holes=[(0.28, 2 * XT - 0.28, 0.12, hr - 0.10)])
    for sx in (-1, 1):
        sheet("engRearLow%d" % sx, ((-XT if sx < 0 else XH), YTR, ZTB), (1, 0, 0), (0, 0, 1), XT - XH,
              ZHT - 0.05 - ZTB, "red", t, amp=0.001)
    # sloped hopper under the overhang + closing triangles
    hl = Vector((XT - XL, 0, ZTB - ZHB)).length
    sheet("hopperL", (-XL, YTF, ZHB), (0, -1, 0), (-(XT - XL), 0, ZTB - ZHB), YTF - YTR, hl, "red", t, amp=0.0015)
    sheet("hopperR", (XL, YTR, ZHB), (0, 1, 0), (XT - XL, 0, ZTB - ZHB), YTF - YTR, hl, "red", t, amp=0.0015)
    for sx in (-1, 1):
        tri = [(sx * XL, ZHB), (sx * XT, ZTB), (sx * XL, ZTB)]
        poly_prism("hopperEndF%d" % sx, tri, 0.004, "red", t, plane="XZ", offset=YTF - 0.004)
        poly_prism("hopperEndR%d" % sx, tri, 0.004, "red", t, plane="XZ", offset=YTR)
    # corner angles, seam strips, lips
    for sx in (-1, 1):
        angle("cornerF%d" % sx, (sx * XT, YTF, ZTB), (sx * XT, YTF, ZTOP), (sx, 0, 0), (0, 1, 0), "red", t)
        angle("cornerR%d" % sx, (sx * XT, YTR, ZTB), (sx * XT, YTR, ZTOP), (sx, 0, 0), (0, -1, 0), "red", t)
        box("seamStrip%d" % sx, (0.006, 0.055, hs), (sx * (XT + 0.003), YTE, ZTB + hs / 2), "red", t, bevel=0.002)
        sweep("bottomLip%d" % sx, [(sx * (XT + 0.004), YTF, ZTB + 0.006), (sx * (XT + 0.004), YTR, ZTB + 0.006)],
              0.011, "red", t, verts=10)
    angle("topEdgeF", (-XT, YTF, ZTOP), (XT, YTF, ZTOP), (0, 0, 1), (0, 1, 0), "red", t)
    angle("topEdgeR", (-XT, YTR, ZTOP), (XT, YTR, ZTOP), (0, 0, 1), (0, -1, 0), "red", t)
    box("seamTop", (2 * XT - 0.12, 0.055, 0.006), (0, YTE, ZTOP + 0.003), "red", t, bevel=0.002)
    zc = _steps(ZTB + 0.07, ZTOP - 0.07, 0.13)
    for sx in (-1, 1):
        bolts("boltsCornerF%d" % sx, [(sx * (XT + 0.005), YTF - 0.022, z) for z in zc], (sx, 0, 0), "red", t)
        bolts("boltsCornerR%d" % sx, [(sx * (XT + 0.005), YTR + 0.022, z) for z in zc], (sx, 0, 0), "red", t)
        bolts("boltsSeam%d" % sx, [(sx * (XT + 0.006), YTE, z) for z in _steps(ZTB + 0.06, zs - 0.03, 0.12)],
              (sx, 0, 0), "red", t)
        bolts("boltsLip%d" % sx, [(sx * (XT + 0.003), y, ZTB + 0.035) for y in _steps(YTR + 0.08, YTF - 0.08, 0.16)],
              (sx, 0, 0), "red", t, r=0.007)
        for z in (2.40, 2.95):
            bead("tankBead%d_%d" % (sx, int(z * 100)), (sx * XT, YTF - 0.14, z), (sx * XT, YTE + 0.14, z), (sx, 0, 0),
                 "red", t)
    bolts("boltsFront", [(sx * (XT - 0.022), YTF + 0.005, z) for sx in (-1, 1) for z in zc], (0, 1, 0), "red", t)
    xt = _steps(-XT + 0.08, XT - 0.08, 0.15)
    bolts("boltsTopF", [(x, YTF - 0.022, ZTOP + 0.005) for x in xt], (0, 0, 1), "red", t)
    bolts("boltsTopR", [(x, YTR + 0.022, ZTOP + 0.005) for x in xt], (0, 0, 1), "red", t)
    for z in (2.35, 2.82):
        bead("frontBead%d" % int(z * 100), (-XT + 0.15, YTF, z), (XT - 0.15, YTF, z), (0, 1, 0), "red", t)
    for sx, nrm in ((-1, "-X"), (1, "+X")):
        # kept behind the vertical unloading auger tube at the front left corner
        decal("dBizon%d" % sx, (sx * (XT + 0.0045), -0.46, 3.13), (1.0, 0.25), REG["bizon"], "decals",
              t, nrm)
        decal("dSuper%d" % sx, (sx * (XT + 0.0045), -0.46, 2.68), (0.6, 0.15), REG["super"], "decals",
              t, nrm)


def tank_details(p):
    t = empty("tankDetails", (0, 0, 0), p)
    x0, x1 = -XT + RB + 0.22, XT - RB - 0.22
    y0, y1 = YTE + 0.20, YTF - 0.18
    z = ZTOP + 0.02
    sweep("tankCoaming", [(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)], 0, "red", t, closed=True,
          profile=[(-0.004, -0.03), (0.004, -0.03), (0.004, 0.03), (-0.004, 0.03)])
    for i, x in enumerate(_steps(x0 + 0.07, x1 - 0.07, 0.11)):
        box("tankGridX%d" % i, (0.008, y1 - y0, 0.03), (x, (y0 + y1) / 2, ZTOP + 0.035), "galv", t, bevel=0.001)
    for i, y in enumerate(_steps(y0 + 0.06, y1 - 0.06, 0.3)):
        box("tankGridY%d" % i, (x1 - x0, 0.008, 0.02), (0, y, ZTOP + 0.05), "galv", t, bevel=0.001)
    fa = empty("tankFillAuger", (0.35, -0.40, 3.22), t)
    ANIM.setdefault("thresh_rot", []).append(("tankFillAuger", "Y", -420))
    cyl("tankFillAugerShaft", 0.03, 1.2, (0, 0, 0), "steel", fa, axis="Y", verts=10)
    for i in range(12):
        box("tankFillFlight%d" % i, (0.22, 0.012, 0.05), (0, -0.55 + i * 0.1, 0), "galv", fa, bevel=0,
            rot=(0, i * 0.9, 0))
    tube("tankFillAugerTube", 0.13, 0.12, 0.3, (0.35, -0.85, 3.22), "red", t, axis="Y", verts=24)
    # sight glass low on the left side, window in the front wall towards the operator
    sx_, sy, sz = -XT - 0.004, 0.02, 2.30
    tube("sightBezel", 0.075, 0.052, 0.014, (sx_ - 0.007, sy, sz), "chrome", t, axis="X", verts=28)
    cyl("sightGlass", 0.055, 0.006, (sx_ - 0.004, sy, sz), "glass", t, axis="X", verts=24)
    cyl("sightBack", 0.055, 0.004, (sx_ + 0.004, sy, sz), "black", t, axis="X", verts=24)
    bolts("sightScrews", [(sx_ - 0.012, sy + math.cos(a) * 0.064, sz + math.sin(a) * 0.064)
                          for a in (0.785, 2.356, 3.927, 5.498)], (-1, 0, 0), "steel", t, r=0.005, h=0.004,
          washer=False)
    box("tankWindowFrame", (0.5, 0.02, 0.3), (-0.42, YTF + 0.012, 3.05), "metalDark", t, bevel=0.008)
    box("tankWindow", (0.42, 0.012, 0.22), (-0.42, YTF + 0.022, 3.05), "glass", t, bevel=0.004)
    # foot of the vertical unloading auger: cross auger out of the tank + elbow gearbox
    cyl("unloadCross", 0.1, 0.24, (-XT - 0.1, 0.12, 2.25), "red", t, axis="X", verts=24)
    tube("unloadCrossFlange", 0.135, 0.1, 0.012, (-XT - 0.008, 0.12, 2.25), "red", t, axis="X", verts=24)
    box("unloadElbow", (0.24, 0.24, 0.26), (-1.3, 0.12, 2.2), "red", t, bevel=0.035, segs=4)
    bolts("unloadElbowBolts", [(-1.3 + dx, 0.12 + dy, 2.335) for dx in (-0.08, 0.08) for dy in (-0.08, 0.08)],
          (0, 0, 1), "red", t, r=0.007)
    # tank-full sensor on the roof
    cyl("tankSensor", 0.035, 0.06, (0.72, 0.05, ZTOP + 0.03), "black", t, axis="Z", verts=16, bevel=0.005)


def engine_bay(p, se):
    e = empty("engineBay", (0, 0, 0), p)
    em = empty("engineMounted", (0, 0, 0), se)
    box("engineFloor", (2 * XT - 0.04, YTE - YTR - 0.02, 0.02), (0, (YTE + YTR) / 2, ZTB + 0.012), "red", e,
        bevel=0.003)
    for k, y in enumerate((-1.48, -1.92)):
        box("engineBearer%d" % k, (1.5, 0.07, 0.09), (0.05, y, ZTB + 0.065), "red", e, bevel=0.006)
    blk = empty("engineBlock", tuple(ENGINE), em, rot=(0, 0, -math.pi / 2))
    EN.build_sw400(blk, ANIM)
    # main drive: clutch housing on the flywheel, shaft through the wall, twin-groove pulley outside
    xf = ENGINE.x - 0.59
    cyl("ptoClutchHousing", 0.16, 0.1, (xf - 0.05, PTO.y, PTO.z), "engineGrey", em, axis="X", verts=32, r2=0.12,
        bevel=0.006)
    cyl("ptoShaft", 0.035, xf - PTO.x + 0.02, ((xf + PTO.x) / 2, PTO.y, PTO.z), "steel", em, axis="X", verts=16)
    pl = pulley("pEngineOut", 0.19, 0.075, tuple(PTO), "red", em, spokes=5, axis="X")
    tube("pEngineOut_groove2", 0.19 * 0.93, 0.19 * 0.8, 0.075 * 0.3, (-0.022, 0, 0), "metalDark", pl, axis="X",
         verts=40)
    ANIM.setdefault("motor_rot", []).append(("pEngineOut", "X", 900))
    flange_bearing("ptoBearing", (-XT - 0.008, PTO.y, PTO.z), -1, e)
    # radiator, shroud and fan behind the rotary screen
    rc = Vector((XT - 0.17, SCREEN.y, SCREEN.z))
    box("radiatorCore", (0.09, 0.84, 0.84), tuple(rc), "black", e, bevel=0.005)
    for i in range(24):
        box("radFin%d" % i, (0.094, 0.82, 0.004), (rc.x, rc.y, rc.z - 0.4 + i * 0.0348), "metalDark", e, bevel=0)
    for k, dz in enumerate((0.47, -0.47)):
        box("radTank%d" % k, (0.13, 0.9, 0.1), (rc.x, rc.y, rc.z + dz), "black", e, bevel=0.025)
    cyl("radCapNeck", 0.03, 0.06, (rc.x, rc.y + 0.3, rc.z + 0.55), "black", e, axis="Z")
    cyl("radCap", 0.042, 0.02, (rc.x, rc.y + 0.3, rc.z + 0.59), "steel", e, axis="Z", verts=20, bevel=0.004)
    tube("fanShroud", 0.40, 0.375, 0.14, (XT - 0.29, SCREEN.y, SCREEN.z), "black", e, axis="X", verts=40)
    fan = empty("engineFan", (XT - 0.33, SCREEN.y, SCREEN.z), em)
    ANIM["motor_rot"].append(("engineFan", "X", 900))
    cyl("fanHub", 0.07, 0.05, (0, 0, 0), "metalDark", fan, axis="X", verts=16)
    for k in range(6):
        a = k * math.pi / 3
        d = Vector((0, math.cos(a), math.sin(a)))
        tau = Vector((0, -math.sin(a), math.cos(a)))
        wdir = tau * math.cos(0.45) + Vector((1, 0, 0)) * math.sin(0.45)
        sweep("fanBlade%d" % k, [d * 0.07, d * 0.35], 0, "black", fan, twist_up=tuple(wdir.cross(d)),
              profile=[(-0.05, -0.003), (0.05, -0.003), (0.05, 0.003), (-0.05, 0.003)])
    hose("radHoseTop", (ENGINE.x + 0.5, ENGINE.y, ENGINE.z + 0.3), (rc.x - 0.05, rc.y - 0.2, rc.z + 0.47), 0.02, 0.028,
         "hoseBlack", e)
    hose("radHoseBottom", (ENGINE.x + 0.54, ENGINE.y, ENGINE.z + 0.14), (rc.x - 0.05, rc.y + 0.25, rc.z - 0.47),
         0.06, 0.028, "hoseBlack", e)
    # rotary screen: spinning perforated drum in a square cowl, stationary suction wand over its face
    sc = empty("radiatorScreen", tuple(SCREEN), e)
    ANIM["motor_rot"].append(("radiatorScreen", "X", 90))
    tube("screenDrum", 0.44, 0.415, 0.12, (0, 0, 0), "red", sc, axis="X", verts=56)
    disc_mesh("screenFace", (0.056, 0, 0), 0.415, sc)
    for k, r in enumerate((0.14, 0.28)):
        tube("screenRing%d" % k, r + 0.008, r - 0.008, 0.01, (0.06, 0, 0), "red", sc, axis="X", verts=40)
    for k in range(6):
        a = k * math.pi / 3
        box("screenSpoke%d" % k, (0.012, 0.03, 0.4), (0.064, math.cos(a) * 0.2, math.sin(a) * 0.2), "red", sc,
            bevel=0.003, rot=(a - math.pi / 2, 0, 0))
    cyl("screenHub", 0.06, 0.08, (0.07, 0, 0), "metalDark", sc, axis="X", verts=20, bevel=0.006)
    for k, (dy, dz, sy, sz) in enumerate(((0, 0.452, 0.91, 0.006), (0, -0.452, 0.91, 0.006),
                                           (0.452, 0, 0.006, 0.91), (-0.452, 0, 0.006, 0.91))):
        box("screenCowl%d" % k, (0.08, sy, sz), (XT + 0.04, SCREEN.y + dy, SCREEN.z + dz), "red", e, bevel=0.002)
    box("screenWand", (0.05, 0.11, 0.4), (SCREEN.x + 0.1, SCREEN.y - 0.06, SCREEN.z + 0.2), "red", e, bevel=0.014)
    cable("screenWandPipe", [(SCREEN.x + 0.12, SCREEN.y - 0.06, SCREEN.z + 0.42),
                             (SCREEN.x + 0.14, SCREEN.y - 0.25, SCREEN.z + 0.5),
                             (SCREEN.x + 0.1, SCREEN.y - 0.52, SCREEN.z + 0.3),
                             (XT + 0.07, SCREEN.y - 0.56, ZTB + 0.12)], 0.045, "red", e, verts=14)
    # left louvres and mesh windows, roof and rear grilles
    louvres("louvreL", -XT, -1, YTE - 0.10, YTE - 1.20, ZTB + 0.80, ZTB + 1.30, 8, e)
    for k, (u0, u1) in enumerate(((0.10, 0.50), (0.80, 1.20))):
        mesh_window("engMeshL%d" % k, -XT, -1, YTE - u0, YTE - u1, ZTB + 0.12, ZTB + 0.70, e)
    gx0, gx1, gy0, gy1 = -XT + RB + 0.18, XT - RB - 0.18, YTR + 0.14, YTE - 0.14
    wire_mesh("engTopMesh", (gx0, gy0, ZTOP + 0.004), (1, 0, 0), (0, 1, 0), gx1 - gx0, gy1 - gy0, "metalDark", e,
              pitch=0.05)
    frame_rect("engTopFrame", [(gx0, gy0, ZTOP + 0.012), (gx1, gy0, ZTOP + 0.012), (gx1, gy1, ZTOP + 0.012),
                               (gx0, gy1, ZTOP + 0.012)], "red", e, s=0.013)
    rz0, rz1 = ZHT - 0.05 + 0.12, ZTOP - 0.10
    wire_mesh("engRearMesh", (-XT + 0.28, YTR - 0.004, rz0), (1, 0, 0), (0, 0, 1), 2 * XT - 0.56, rz1 - rz0,
              "metalDark", e)
    frame_rect("engRearFrame", [(-XT + 0.28, YTR - 0.012, rz0), (XT - 0.28, YTR - 0.012, rz0),
                                (XT - 0.28, YTR - 0.012, rz1), (-XT + 0.28, YTR - 0.012, rz1)], "red", e, s=0.013)
    # exhaust: manifold -> up through the roof -> horizontal muffler -> tail pipe with rain flap
    man = Vector((ENGINE.x, ENGINE.y + 0.26, ENGINE.z + 0.19))
    sweep("exhaustDown", smooth_path([man, man + Vector((0.1, 0.1, 0.12)), (MUFFLER_X, ENGINE.y + 0.4, 3.0),
                                      (MUFFLER_X, ENGINE.y + 0.4, 3.5), (MUFFLER_X, ENGINE.y + 0.34, 3.62)], 5),
          0.045, "rust", em, verts=14)
    cyl("muffler", 0.12, 0.9, (MUFFLER_X, -1.80, 3.62), "steelDirty", em, axis="Y", verts=28, bevel=0.025)
    for k, y in enumerate((-1.48, -2.12)):
        tube("mufflerClamp%d" % k, 0.127, 0.119, 0.035, (MUFFLER_X, y, 3.62), "metalDark", em, axis="Y", verts=28)
        box("mufflerLeg%d" % k, (0.04, 0.03, 0.16), (MUFFLER_X, y, 3.46), "metalDark", em, bevel=0.004)
    sweep("exhaustTail", smooth_path([(MUFFLER_X, -2.24, 3.62), (MUFFLER_X, -2.38, 3.64), (MUFFLER_X, -2.46, 3.76),
                                      tuple(EXHAUST_TIP)], 4), 0.042, "rust", em, verts=14)
    flap = empty("exhaustFlap", tuple(EXHAUST_TIP + Vector((0, 0.06, 0))), em)
    cyl("exhaustFlapMesh", 0.058, 0.006, (0, -0.06, 0.004), "rust", flap, axis="Z", verts=16)
    cyl("exhaustFlapPin", 0.008, 0.07, (0, 0, 0.004), "metalDark", flap, axis="X", verts=8)
    ANIM["exhaustFlap"] = "exhaustFlap"
    EN.build_air_filter(e, (-0.45, -1.95, 3.63), tuple(ENGINE + Vector((0, -0.27, 0.33))))
    EN.build_fuel_tank(e, tuple(FUEL_TANK))
    decal("dEngine", (XT + 0.0045, SCREEN.y, ZTB + 0.13), (0.36, 0.09), REG["engine"], "decals", e, "+X")


def lower_body(p):
    lb = empty("lowerBody", (0, 0, 0), p)
    zt = ZHB + 0.04
    wf = YLF - YLS
    sheet("lowerSideL", (-XL, YLF, 0.62), (0, -1, 0), (0, 0, 1), wf, zt - 0.62, "red", lb, dents=3)
    sheet("lowerSideR", (XL, YLS, 0.62), (0, 1, 0), (0, 0, 1), wf, zt - 0.62, "red", lb, dents=3)
    for sx in (-1, 1):
        box("lowerFill%d" % sx, (0.004, YLF - YTF + 0.02, 2.18 - zt), (sx * XL, (YLF + YTF) / 2, (zt + 2.18) / 2),
            "red", lb, bevel=0.001)
        box("lowerStep%d" % sx, (XL - XLR, 0.004, ZH0 - 0.62), (sx * (XL + XLR) / 2, YLS, (ZH0 + 0.62) / 2), "red",
            lb, bevel=0.001)
        box("hoodUnder%d" % sx, (XH - XLR, YTR - YHR, 0.004), (sx * (XH + XLR) / 2, (YTR + YHR) / 2, ZH0), "red", lb,
            bevel=0.001)
    box("lowerFrontTop", (2 * XL, YLF - YTF + 0.02, 0.004), (0, (YLF + YTF) / 2, 2.18), "red", lb, bevel=0.001)
    sheet("lowerFront", (XL, YLF, 0.62), (-1, 0, 0), (0, 0, 1), 2 * XL, 2.18 - 0.62, "red", lb,
          holes=[(0.18, 2 * XL - 0.18, 0.40, 1.26)])
    yr = YHR + 0.30
    sheet("rearSideL", (-XLR, YLS, 0.85), (0, -1, 0), (0, 0, 1), YLS - yr, ZH0 + 0.03 - 0.85, "red", lb, dents=2)
    sheet("rearSideR", (XLR, yr, 0.85), (0, 1, 0), (0, 0, 1), YLS - yr, ZH0 + 0.03 - 0.85, "red", lb, dents=2)
    box("rearBottom", (2 * XLR, YLS - yr, 0.004), (0, (YLS + yr) / 2, 0.85), "red", lb, bevel=0.001)
    box("rearSill", (2 * XLR, 0.004, 0.15), (0, yr, 0.925), "red", lb, bevel=0.001)
    # underside: sieve box, cross augers, stone trap
    box("sieveBox", (1.4, 2.6, 0.22), (0, -2.0, 0.52), "red", lb, bevel=0.02)
    box("sieveBoxLip", (1.3, 0.05, 0.1), (0, -3.28, 0.47), "metalDark", lb)
    for i, y in enumerate((-0.55, -0.95)):
        cyl("bottomAuger%d" % i, 0.11, 1.62, (0, y, 0.52), "red", lb, axis="X", verts=24)
        cyl("bottomAugerBearing%d" % i, 0.06, 1.72, (0, y, 0.52), "metalDark", lb, axis="X", verts=12)
    box("stoneTrap", (1.2, 0.3, 0.2), (0, 0.25, 0.72), "metalDark", lb, bevel=0.01)
    yb = _steps(YLS + 0.06, YLF - 0.06, 0.16)
    for sx in (-1, 1):
        bead("lowerBead%d" % sx, (sx * XL, 0.30, 1.50), (sx * XL, YLS + 0.15, 1.50), (sx, 0, 0), "red", lb)
        bolts("lowerBoltsTop%d" % sx, [(sx * (XL + 0.004), y, zt - 0.03) for y in yb], (sx, 0, 0), "red", lb,
              r=0.0075)
        bolts("lowerBoltsBot%d" % sx, [(sx * (XL + 0.004), y, 0.66) for y in yb], (sx, 0, 0), "red", lb, r=0.0075)
        angle("lowerCornerF%d" % sx, (sx * XL, YLF, 0.62), (sx * XL, YLF, 2.18), (sx, 0, 0), (0, 1, 0), "red", lb,
              s=0.04)
        bolts("rearBolts%d" % sx, [(sx * (XLR + 0.004), y, 0.9) for y in _steps(yr + 0.06, YLS - 0.06, 0.16)],
              (sx, 0, 0), "red", lb, r=0.0075)
        door("sieveDoor%d" % sx, sx * XL, sx, -1.25, -2.15, 0.74, 1.30, lb)
    decal("dWarnBelt", (-(XL + 0.004), -0.95, 1.30), (0.44, 0.11), REG["warning"], "decals", lb, "-X")
    decal("dPlateR", (XL + 0.004, 0.12, 1.30), (0.26, 0.13), REG["plate"], "decals", lb, "+X")
    for sx, nrm in ((-1, "-X"), (1, "+X")):
        decal("dStripe%d" % sx, (sx * (XL + 0.004), 0.25, 0.76), (0.4, 0.05), REG["stripes"], "decals", lb, nrm)


def rear_hood(p):
    h = empty("rearHood", (0, 0, 0), p)
    hs = ZHT - RB - ZH0
    L = YTR - (YHR + RB)
    sheet("hoodSideL", (-XH, YTR, ZH0), (0, -1, 0), (0, 0, 1), L, hs, "red", h, dents=3)
    sheet("hoodSideR", (XH, YHR + RB, ZH0), (0, 1, 0), (0, 0, 1), L, hs, "red", h, dents=3)
    wtop = 2 * (XH - RB)
    sheet("hoodTop", (-XH + RB, YHR + RB, ZHT), (1, 0, 0), (0, 1, 0), wtop, L, "red", h, dents=2)
    sheet("hoodRear", (-XH + RB, YHR, 1.95), (1, 0, 0), (0, 0, 1), wtop, ZHT - RB - 1.95, "red", h, dents=1)
    for sx in (-1, 1):
        bend("hoodBend%d" % sx, (sx * (XH - RB), YHR + RB, ZHT - RB), (sx * (XH - RB), YTR, ZHT - RB), (sx, 0, 0),
             (0, 0, 1), RB, "red", h)
        bend("hoodBendV%d" % sx, (sx * (XH - RB), YHR + RB, 1.95), (sx * (XH - RB), YHR + RB, ZHT - RB), (sx, 0, 0),
             (0, -1, 0), RB, "red", h)
        EN.ball("hoodCorner%d" % sx, RB, (sx * (XH - RB), YHR + RB, ZHT - RB), "red", h, segs=12)
        sweep("hoodRearEdge%d" % sx, [(sx * XH, YHR + RB, ZH0), (sx * XH, YHR + RB, 1.95)], 0.008, "red", h, verts=8)
        angle("hoodLip%d" % sx, (sx * XH, YTR, ZH0), (sx * XH, YHR + RB, ZH0), (sx, 0, 0), (0, 0, -1), "red", h,
              s=0.035)
        bolts("hoodLipBolts%d" % sx, [(sx * (XH + 0.005), y, ZH0 + 0.02) for y in _steps(YHR + 0.12, YTR - 0.08, 0.16)],
              (sx, 0, 0), "red", h, r=0.007)
        bolts("hoodJoint%d" % sx, [(sx * (XH + 0.004), YTR - 0.025, z) for z in _steps(ZH0 + 0.08, ZHT - 0.1, 0.13)],
              (sx, 0, 0), "red", h)
        bead("hoodBead%d" % sx, (sx * XH, YTR - 0.15, 2.55), (sx * XH, YHR + 0.2, 2.55), (sx, 0, 0), "red", h)
    bend("hoodBendRear", (-XH + RB, YHR + RB, ZHT - RB), (XH - RB, YHR + RB, ZHT - RB), (0, -1, 0), (0, 0, 1), RB,
         "red", h)
    door("hoodDoorR", XH, 1, -3.15, -3.95, 1.72, 2.42, h, handle_at_front=False)
    # straw outlet: curtain bar and rubber flaps in front of the walker ends
    sweep("strawCurtainBar", [(-XH + 0.03, YHR - 0.015, 1.94), (XH - 0.03, YHR - 0.015, 1.94)], 0.012, "metalDark",
          h, verts=8)
    for i in range(6):
        box("strawFlap%d" % i, (0.268, 0.008, 0.48), (-0.675 + i * 0.27, YHR - 0.022, 1.70), "rubber", h, bevel=0.002,
            rot=(0.04 * ((i % 3) - 1), 0, 0))
    wroot = empty("walkers", (0, -4.05, 1.72), h)
    wa = empty("walkerShakeA", (0, 0, 0), wroot)
    for ph, (off, idx) in enumerate(((0.04, (0, 2)), (-0.04, (1, 3)))):
        wb = empty("walkerShakeB%d" % ph, (0, 0, off), wa)
        for i in idx:
            EN.hollow_walker("walker%d" % i, -0.57 + i * 0.38, wb)
    ANIM["walkers"] = {"A": "walkerShakeA", "B": ["walkerShakeB0", "walkerShakeB1"]}
    for sx in (-1, 1):
        box("chafferFrame%d" % sx, (0.03, 0.42, 0.08), (sx * 0.6, YHR + 0.12, 0.93), "galv", h, bevel=0.005)
    for k in range(10):
        box("chafferSlat%d" % k, (1.16, 0.035, 0.004), (0, YHR + 0.30 - k * 0.04, 0.93), "galv", h, bevel=0,
            rot=(0.6, 0, 0))
    # rear face: lamps on brackets, reflectors, slow-vehicle triangle, number plate
    for sx in (-1, 1):
        box("lampBracket%d" % sx, (0.1, 0.02, 0.26), (sx * 0.62, YHR - 0.008, 2.17), "black", h, bevel=0.004)
        tl = empty("tailLight%d" % sx, (sx * 0.62, YHR - 0.03, 2.25), h)
        cyl("tailLightBody%d" % sx, 0.06, 0.05, (0, 0, 0), "black", tl, axis="Y")
        cyl("tailLightGlass%d" % sx, 0.052, 0.012, (0, -0.03, 0), "redGlass", tl, axis="Y")
        ta = empty("turnRear%d" % sx, (sx * 0.62, YHR - 0.03, 2.10), h)
        cyl("turnRearBody%d" % sx, 0.05, 0.05, (0, 0, 0), "black", ta, axis="Y")
        cyl("turnRearGlass%d" % sx, 0.043, 0.012, (0, -0.03, 0), "amberGlass", ta, axis="Y")
        box("reflector%d" % sx, (0.1, 0.008, 0.05), (sx * 0.42, YHR - 0.006, 2.0), "redGlass", h, bevel=0.003)
    o = poly_prism("slowSign", [(-0.2, 0), (0.2, 0), (0, 0.35)], 0.02, "orangeRefl", h, plane="XZ",
                   offset=YHR - 0.03)
    o.location = (0, 0, 2.2)
    o = poly_prism("slowSignInner", [(-0.12, 0.06), (0.12, 0.06), (0, 0.26)], 0.004, "redClean", h, plane="XZ",
                   offset=YHR - 0.034)
    o.location = (0, 0, 2.2)
    box("plateHolder", (0.38, 0.01, 0.11), (0, YHR - 0.01, 2.06), "black", h, bevel=0.003)
    decal("dPlateNr", (0, YHR - 0.016, 2.06), (0.34, 0.085), REG["plate_number"], "decals", h, "-Y")
    flag(h, Vector((1.0, YTR + 0.12, ZTOP)))


def flag(p, base):
    sweep("flagPole", [tuple(base), tuple(base + Vector((0, 0, 1.25)))], 0.012, "steel", p, verts=8)
    cyl("flagPoleFoot", 0.03, 0.06, tuple(base + Vector((0, 0, 0.03))), "metalDark", p, axis="Z", verts=12)
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("uv0")
    nu, nv, w, hh = 10, 5, 0.6, 0.38
    top = base.z + 1.2
    vs = [[bm.verts.new((base.x + math.sin(i / nu * 5.0) * 0.05 * i / nu, base.y - i / nu * w,
                         top - hh + j / nv * hh)) for i in range(nu + 1)] for j in range(nv + 1)]
    u0, v0, u1, v1 = REG["flag"]
    for j in range(nv):
        for i in range(nu):
            f = bm.faces.new((vs[j][i], vs[j][i + 1], vs[j + 1][i + 1], vs[j + 1][i]))
            for loop, (a, b) in zip(f.loops, ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1))):
                loop[uv].uv = (u0 + (u1 - u0) * a / nu, v0 + (v1 - v0) * b / nv)
    o = K.mesh_from_bm("flag", bm, "decals", p, smooth_angle=80)
    o["keep_uv"] = True
    o["twosided"] = True


def right_side(p):
    r = empty("rightSide", (0, 0, 0), p)
    ex, ey = XL + 0.08, -0.92
    box("elevator", (0.16, 0.30, 1.55), (ex, ey, 0.45 + 0.775), "red", r, bevel=0.01)
    for sy in (-1, 1):
        box("elevatorFlange%d" % sy, (0.05, 0.012, 1.45), (ex, ey + sy * 0.155, 1.2), "red", r, bevel=0.002)
    bolts("elevatorBolts", [(ex + 0.083, ey + sy * 0.12, z) for sy in (-1, 1) for z in _steps(0.6, 1.6, 0.14)],
          (1, 0, 0), "red", r, r=0.007)
    box("elevatorFoot", (0.22, 0.4, 0.25), (ex, ey, 0.55), "red", r, bevel=0.025)
    door("elevatorFlap", ex + 0.08, 1, ey + 0.1, ey - 0.1, 0.72, 0.92, r)
    box("elevatorHead", (0.28, 0.26, 0.3), (0.82, ey, 3.12), "red", r, bevel=0.03)
    box("elevatorSpout", (0.4, 0.12, 0.12), (0.6, ey + 0.02, 3.2), "red", r, bevel=0.02)
    box("returnsElevator", (0.12, 0.2, 1.1), (XL + 0.06, -1.32, 0.95), "red", r, bevel=0.01)
    for nm, y, z, rr, teeth in (("sprElevFoot", ey, 0.55, 0.1, 18), ("sprReturns", -1.32, 0.5, 0.08, 14)):
        s = empty(nm, (XL + 0.2, y, z), r)
        gear(nm + "_g", rr, 0.02, teeth, (0, 0, 0), "metalDark", s)
        cyl(nm + "_hub", 0.03, 0.05, (0, 0, 0), "steel", s, axis="X", verts=10)
        ANIM.setdefault("thresh_rot", []).append((nm, "X", 500))
    belt("elevChain", XL + 0.2, (ey, 0.55), 0.106, (-1.32, 0.5), 0.086, mat="metalDark", parent=r, w=0.016, t=0.012)
    # hydraulics: oil tank with sight gauge, valve bank, suction hose
    cyl("hydTank", 0.14, 0.6, (1.0, 0.95, 1.55), "red", r, axis="Y", verts=28, bevel=0.01)
    cyl("hydTankCap", 0.04, 0.05, (1.0, 1.05, 1.7), "black", r, axis="Z", verts=16)
    cyl("hydSight", 0.025, 0.01, (1.0, 1.255, 1.55), "lampGlass", r, axis="Y", verts=16)
    for k, y in enumerate((0.74, 1.16)):
        tube("hydStrap%d" % k, 0.147, 0.14, 0.03, (1.0, y, 1.55), "metalDark", r, axis="Y", verts=28)
    box("valveBlock", (0.18, 0.28, 0.16), tuple(VALVES), "metalDark", r, bevel=0.01)
    for i in range(4):
        cyl("valveSpool%d" % i, 0.012, 0.08, (VALVES.x, VALVES.y - 0.105 + i * 0.07, VALVES.z + 0.12), "chrome", r,
            axis="Z", verts=8)
    # battery (front right, under the platform)
    bb = empty("batteryBox", (1.0, 1.35, 1.72), r)
    box("batteryCase", (0.3, 0.42, 0.28), (0, 0, 0), "black", bb, bevel=0.01)
    box("batteryLid", (0.32, 0.44, 0.03), (0, 0, 0.155), "red", bb, bevel=0.01)
    cyl("batteryPos", 0.018, 0.03, (-0.08, 0.12, 0.19), "copper", bb, axis="Z", verts=8)
    cyl("batteryNeg", 0.018, 0.03, (-0.08, -0.12, 0.19), "steel", bb, axis="Z", verts=8)
    # grease gun and spare V-belts hanging on the body
    gg = empty("greaseGun", (XL + 0.045, -2.3, 1.15), r)
    cyl("greaseGunBody", 0.035, 0.3, (0, 0, 0), "red", gg, axis="Y")
    sweep("greaseGunHose", [(0, 0.15, 0), (0.02, 0.25, -0.05), (0.0, 0.3, -0.15)], 0.006, "rubber", gg, verts=6)
    box("greaseGunClip", (0.03, 0.04, 0.08), (-0.03, 0, 0), "metalDark", gg, bevel=0.003)
    for i in range(2):
        pts = [(XH + 0.02 + math.cos(a) * 0.01, -3.05 + math.sin(a) * 0.14 + i * 0.03, 2.25 - math.cos(a) * 0.2)
               for a in [2 * math.pi * k / 24 for k in range(24)]]
        sweep("spareBelt%d" % i, pts, 0.008, "rubberBelt", r, closed=True, verts=6)
    sweep("beltHook", [(XH, -3.05, 2.47), (XH + 0.04, -3.05, 2.47), (XH + 0.04, -3.05, 2.43)], 0.008, "steel", r,
          verts=6)
    # ladder up the right side of the hood to the engine roof
    lx = XH + 0.09
    ys = (-2.42, -2.78)
    for k, y in enumerate(ys):
        sweep("ladderRStringer%d" % k, [(lx, y, 0.55), (lx, y, ZHT + 0.02)], 0, "red", r,
              profile=[(-0.004, -0.025), (0.004, -0.025), (0.004, 0.025), (-0.004, 0.025)])
        for z in (1.8, 2.5):
            box("ladderRStay%d_%d" % (k, int(z * 10)), (lx - XH, 0.025, 0.03), ((lx + XH) / 2, y, z), "red", r,
                bevel=0.004)
        cable("ladderRRail%d" % k, [(lx, y, ZHT), (lx, y, 3.2), (lx - 0.02, y + 0.03, 3.32),
                                    (lx - 0.1, YTR - 0.01, 3.32)] if k == 0 else
              [(lx, y, ZHT), (lx, y, 3.05), (lx - 0.03, y + 0.03, 3.12), (lx - 0.12, y + 0.08, 3.1),
               (lx - 0.12, y + 0.08, ZHT)], 0.016, "red", r, verts=10)
    box("ladderRStayLow0", (lx - XL, 0.025, 0.03), ((lx + XL) / 2, ys[0], 1.0), "red", r, bevel=0.004)
    box("ladderRStayLow1", (lx - XLR, 0.025, 0.03), ((lx + XLR) / 2, ys[1], 1.0), "red", r, bevel=0.004)
    for i, z in enumerate(_steps(0.66, 2.5, 0.28)):
        box("ladderRRung%d" % i, (0.05, abs(ys[1] - ys[0]), 0.024), (lx, sum(ys) / 2, z), "tread", r, bevel=0.003)


def left_drives(p):
    d = empty("leftDrives", (0, 0, 0), p)
    P = {  # name: (x, y, z, r, spokes, mat, rpm-ish speed)
        "pCounter": (-1.24, -1.52, 1.28, 0.30, 6, "cream", 520),
        "pCounterWalker": (-1.07, -1.52, 1.28, 0.20, 5, "red", 520),
        "pCounterSmall": (-0.95, -1.52, 1.28, 0.14, 4, "red", 520),
        "pCounterFan": (-0.87, -1.52, 1.28, 0.11, 0, "metalDark", 520),
        "pDrumVariator": (-0.95, 0.38, 1.42, 0.37, 6, "cream", 430),
        "pFan": (-0.87, -0.45, 0.75, 0.20, 5, "red", 900),
        "pWalkerCrank": (-1.07, -3.05, 1.82, 0.30, 5, "red", 380),
        "pWalkerSmall": (-0.95, -3.05, 1.82, 0.12, 0, "metalDark", 380),
        "pSieve": (-0.95, -2.30, 1.00, 0.16, 4, "red", 700),
    }
    em = {}
    for nm, (x, y, z, r, sp, mat, spd) in P.items():
        em[nm] = pulley(nm, r, 0.05 if r > 0.15 else 0.04, (x, y, z), mat, d, spokes=sp, axis="X")
        ANIM.setdefault("thresh_rot", []).append((nm, "X", spd))
    # variator: movable half on the drum shaft + adjusting spindle up to the platform
    cyl("variatorDisc2", 0.36, 0.03, (0.06, 0, 0), "cream", em["pDrumVariator"], axis="X", verts=48, r2=0.27)
    vx, vy, vz = P["pDrumVariator"][:3]
    sweep("variatorSpindle", [(vx + 0.09, vy, vz), (vx + 0.1, vy + 0.15, vz + 0.4), (vx + 0.1, vy + 0.4, 2.1)], 0.012,
          "steel", d, verts=8)
    for nm, x0, x1, y, z in (("shaftCounter", -1.30, -XL, -1.52, 1.28), ("shaftDrum", -1.0, -XL, vy, vz),
                             ("shaftFan", -0.92, -XL, -0.45, 0.75), ("shaftWalker", -1.12, -XH, -3.05, 1.82),
                             ("shaftSieve", -1.0, -XL, -2.30, 1.00)):
        cyl(nm, 0.03, abs(x1 - x0), ((x0 + x1) / 2, y, z), "steel", d, axis="X", verts=12)
        flange_bearing(nm + "Brg", (x1 - 0.008, y, z), -1, d)
    pos = {k: v[:4] for k, v in P.items()}
    pos["pEngineOut"] = (PTO.x, PTO.y, PTO.z, 0.19)
    for nm, x, a, b, w in (("beltMain", -1.222, "pEngineOut", "pCounter", 0.022),
                           ("beltMain2", -1.258, "pEngineOut", "pCounter", 0.022),
                           ("beltWalker", -1.07, "pCounterWalker", "pWalkerCrank", 0.035),
                           ("beltDrum", -0.95, "pCounterSmall", "pDrumVariator", 0.038),
                           ("beltFan", -0.87, "pCounterFan", "pFan", 0.028),
                           ("beltSieve", -0.95, "pWalkerSmall", "pSieve", 0.028)):
        belt(nm, x, pos[a][1:3], pos[a][3] * 0.9, pos[b][1:3], pos[b][3] * 0.9, parent=d, w=w)
    # spring-loaded idlers on the main and drum belts
    for nm, x, pivot, roller, anchor in (
            ("idlerMain", -1.24, (-1.14, -2.12, 2.1), (-1.24, -1.97, 1.86), (-1.14, -2.25, 2.55)),
            ("idlerDrum", -0.95, (-0.86, -0.55, 1.62), (-0.95, -0.58, 1.33), (-0.86, -0.25, 1.62))):
        pv, ro, an = Vector(pivot), Vector(roller), Vector(anchor)
        sweep(nm + "Arm", [pv, Vector((x, pv.y, pv.z)), ro], 0.014, "metalDark", d, verts=8)
        pulley(nm + "Roller", 0.055, 0.045, tuple(ro), "metalDark", d, spokes=0, axis="X")
        mid = Vector((x, pv.y, pv.z)).lerp(ro, 0.5)
        EN.helix(nm + "Spring", mid, an, 0.016, 12, 0.0035, "steel", d)
        box(nm + "Anchor", (0.03, 0.05, 0.05), tuple(an), "metalDark", d, bevel=0.004)
        box(nm + "Bracket", (abs(pv.x - x) + 0.03, 0.05, 0.05), ((pv.x + x) / 2, pv.y, pv.z), "red", d, bevel=0.005)
    # guards: half-rings over the variator and the engine pulley, mesh guard over the main belts
    guard_arc("guardVariator", vx - 0.005, (vy, vz), 0.45, 0.25, 2.9, 0.1, d)
    for k, a in enumerate((0.25, 2.9)):
        box("guardVariatorStay%d" % k, (0.14, 0.025, 0.025), (vx + 0.07, vy + math.cos(a) * 0.45,
                                                              vz + math.sin(a) * 0.45), "red", d, bevel=0.004)
    guard_arc("guardEngineOut", PTO.x, (PTO.y, PTO.z), 0.25, 0.3, 2.85, 0.12, d)
    box("guardEngineOutStay", (0.14, 0.025, 0.025), (PTO.x + 0.07, PTO.y, PTO.z + 0.25), "red", d, bevel=0.004)
    wire_mesh("guardMainMesh", (-1.30, -1.35, 1.62), (0, -1, 0), (0, 0, 1), 0.55, 0.52, "metalDark", d, pitch=0.035)
    frame_rect("guardMainFrame", [(-1.30, -1.35, 1.62), (-1.30, -1.90, 1.62), (-1.30, -1.90, 2.14),
                                  (-1.30, -1.35, 2.14)], "red", d, s=0.012)
    for k, (y, z) in enumerate(((-1.35, 2.14), (-1.90, 2.14))):
        box("guardMainStay%d" % k, (0.18, 0.02, 0.02), (-1.21, y, z), "red", d, bevel=0.003)


def wiring(p):
    w = empty("wiring", (0, 0, 0), p)
    xh = XH + 0.012
    loom = [(0.92, 1.30, 1.84), (0.90, 0.95, 1.62), (0.84, 0.35, 1.60), (0.83, -0.55, 1.60), (0.99, -0.72, 1.58),
            (0.99, -1.14, 1.58), (0.83, -1.50, 1.60), (0.83, -2.30, 1.60), (xh, -2.60, 1.62), (xh, -3.60, 1.62),
            (xh, -4.70, 1.62), (xh, YHR + 0.06, 1.8), (0.70, YHR - 0.014, 2.02), (0.62, YHR - 0.014, 2.18)]
    cable("rearLoom", loom, 0.0095, "wireBlack", w, clips=range(1, len(loom) - 2))
    cable("tailCross", [(0.62, YHR - 0.014, 2.18), (0.3, YHR - 0.014, 1.99), (-0.3, YHR - 0.014, 1.99),
                        (-0.62, YHR - 0.014, 2.18)], 0.005, "wireBlack", w, clips=(1, 2))
    start = Vector((-0.36, 0.27, -0.13))  # starter in engine-local space
    st = ENGINE + Vector((start.y, -start.x, start.z))
    cable("cableStarter", [(0.92, 1.47, 1.91), (0.95, 1.2, 1.7), (0.86, 0.4, 1.56), (0.86, -0.55, 1.55),
                           (1.0, -0.85, 1.52), (1.0, -1.2, 1.52), (0.86, -1.6, 1.62), (0.7, -1.9, 1.85),
                           (0.3, -1.98, 2.02), (-0.1, -1.98, 2.2), tuple(st)], 0.012, "wireRed", w, clips=(2, 3, 6))
    alt = ENGINE + Vector((0.5, -0.2, 0.12))
    cable("wireAlt", [tuple(alt), (alt.x, alt.y - 0.05, alt.z - 0.1), (0.7, -2.05, 2.2), (0.8, -2.1, 1.98),
                      (0.84, -2.2, 1.7), (0.83, -2.3, 1.61)], 0.006, "wireRed", w)
    # rear work lamps: up the ladder side of the hood, along the rear roof edge
    cable("wireWorkRear", [(xh, -2.60, 1.62), (xh, -2.47, 2.3), (xh, -2.40, 2.68), (0.95, YTR - 0.014, 2.9),
                           (0.95, YTR - 0.014, 3.36), (0.3, YTR - 0.014, 3.36), (-0.95, YTR - 0.014, 3.36),
                           (-0.95, YTR - 0.05, 3.45)], 0.006, "wireBlack", w, clips=(2, 3, 4, 5, 6))
    cable("wireWorkRearR", [(0.95, YTR - 0.014, 3.36), (0.95, YTR - 0.05, 3.45)], 0.006, "wireBlack", w)
    # senders + throttle cable from the engine over the tank roof to the gauges on the tank front
    roof = [(1.05, -1.05, 3.425), (1.05, -0.5, 3.43), (1.05, 0.0, 3.43), (1.05, 0.28, 3.43)]
    cable("senderLoom", [(0.3, -1.55, 2.62), (0.6, -1.3, 2.9), (0.95, -1.12, 3.25)] + roof +
          [(1.02, YTF + 0.014, 3.35), (0.7, YTF + 0.014, 3.30), (0.64, YTF + 0.03, 3.22)], 0.007, "wireBlack", w,
          clips=(3, 4, 5, 6, 8))
    cable("throttleCable", [(0.1, -1.95, 2.42), (0.3, -1.6, 2.7), (0.93, -1.12, 3.22)] +
          [(x - 0.03, y, z) for x, y, z in roof] +
          [(0.99, YTF + 0.016, 3.3), (0.9, YTF + 0.03, 2.8), (0.62, 0.62, 2.36)], 0.005, "black", w)
    cable("tachoCable", [(-1.0, 0.38, 1.42), (-1.02, 0.42, 1.7), (-0.9, 0.43, 2.05), (-0.72, 0.42, 2.15),
                         (-0.5, YTF + 0.014, 2.35), (-0.2, YTF + 0.014, 2.9), (0.2, YTF + 0.03, 3.14)], 0.0055,
          "black", w, clips=(4, 5))
    cable("wireTankSensor", [(0.72, 0.05, ZTOP + 0.06), (0.9, 0.1, ZTOP + 0.03), (1.05, 0.2, 3.43)], 0.004,
          "wireBlack", w)
    # hydraulic hoses: valve bank -> up the tank front -> over the roof edge -> pipe swing cylinder
    for k, dx in enumerate((0.0, 0.028)):
        cable("hosePipe%d" % k, [(VALVES.x - 0.03 + dx, VALVES.y - 0.06, VALVES.z + 0.08),
                                 (1.0 + dx, 0.42, 2.05), (1.06 + dx, YTF + 0.02, 2.4), (1.07 + dx, YTF + 0.02, 3.3),
                                 (1.0, YTF - 0.03 - dx, 3.435), (0.2, YTF - 0.03 - dx, 3.44),
                                 (-0.9, YTF - 0.03 - dx, 3.44), (-1.05 + dx, 0.18, 3.435), (-1.07 + dx, -0.4, 3.43),
                                 (-1.1 + dx, -0.88, 3.4), (-1.2, -1.0 + dx, 3.31)], 0.011, "hoseBlack", w,
              clips=(2, 3, 5, 6, 8) if k == 0 else ())
    for nm, a, b, sag, r in (("hoseFeederL", (0.9, 0.5, 1.74), (-0.42, 0.42, 0.92), 0.35, 0.013),
                             ("hoseFeederR", (0.95, 0.52, 1.74), (0.42, 0.42, 0.92), 0.25, 0.013),
                             ("hoseReel1", (0.92, 0.66, 1.74), (0.62, 1.05, 1.05), 0.2, 0.011),
                             ("hoseReel2", (0.97, 0.66, 1.74), (0.66, 1.05, 1.02), 0.22, 0.011),
                             ("hoseSuction", (1.0, 0.7, 1.45), (0.2, 0.1, 0.92), 0.15, 0.025)):
        hose(nm, a, b, sag, r, "hoseBlack", w)
    # fuel feed and return between the roof tank and the injection pump
    for k, dx in enumerate((0.0, 0.03)):
        cable("fuelLine%d" % k, [(0.35 + dx, -2.62, 2.74), (0.3 + dx, -2.5, 2.7), (0.2 + dx, -2.3, 2.6),
                                 (0.1 + dx, -2.05, 2.46), (0.05 + dx, -1.97, 2.41)], 0.005, "black", w)
