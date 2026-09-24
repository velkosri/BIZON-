"""Bizon Super Z056 + 4.2 m grain header, built procedurally in Blender.

Every node that the FS25 XML references is created as a named empty/mesh; the exporter
turns names into i3dMappings. Blender axes: X right, Y forward, Z up (vehicle left = -X).
"""
import json
import math
import os
import sys

import bpy
from mathutils import Euler, Matrix, Vector

sys.path.insert(0, os.path.dirname(__file__))
import blender_kit as K  # noqa: E402
import bizon_detail as D  # noqa: E402
import bizon_engine as EN  # noqa: E402
from blender_kit import box, cyl, empty, hose, pulley, sweep, tube, decal, belt, rivets, gear, poly_prism  # noqa

TEX = os.environ.get("BIZON_TEX", "build/textures")
REG = json.load(open(os.path.join(TEX, "decal_regions.json")))
DECALS = os.path.abspath(os.path.join(TEX, "bizon_decals.png"))

R_F = 0.714   # 480/80R26
R_R = 0.627   # 460/70R24
SUSP_F = 0.07  # repr node sits above the rest position by suspTravel*(1-initialCompression)
FRONT_X = 1.23
REAR_X = 0.98
WHEELBASE = 3.5
PIVOT = Vector((0, 0.55, 1.45))   # feeder pivot
FEEDER_ANGLE = math.radians(20)
FEEDER_LEN = 1.75
# feeder tilt when lowered; keeps the cutterbar ~5 cm and the header collision ~10 cm above flat ground,
# otherwise the locked-pitch joint presses the header into the terrain and the parked combine creeps
FEEDER_LOWER = 6

ANIM = {}  # extra data for XML generation (converted to GIANTS space by the exporter)


def materials():
    M = K.material
    # old, sun-faded factory paint: little clear coat; values follow base-game calibrated materials
    old_paint = {"smoothnessScale": 0.7, "clearCoatIntensity": 0.15, "clearCoatSmoothness": 0.35}
    M("red", (0.62, 0.045, 0.035), 0.42, detail="calPaint", grime=0.45, params=old_paint)
    M("redClean", (0.66, 0.06, 0.05), 0.35, detail="calPaint", grime=0.15,
      params={"smoothnessScale": 0.85, "clearCoatIntensity": 0.4, "clearCoatSmoothness": 0.7})
    M("cream", (0.86, 0.82, 0.70), 0.45, detail="calPaint", grime=0.4, params=old_paint)
    M("yellow", (0.93, 0.70, 0.08), 0.45, detail="calPaint", grime=0.3, params=old_paint)
    M("black", (0.03, 0.03, 0.03), 0.55, detail="paint", grime=0.2)
    M("metalDark", (0.16, 0.16, 0.16), 0.5, 0.7, detail="scratched", grime=0.3)
    M("steel", (0.55, 0.55, 0.56), 0.35, 1.0, detail="silver")
    M("galv", (0.62, 0.63, 0.64), 0.45, 1.0, detail="galvanized", grime=0.2)
    M("chrome", (0.9, 0.9, 0.9), 0.08, 1.0, detail="chrome")
    M("rust", (0.35, 0.16, 0.08), 0.8, 0.2, detail="scratched", grime=0.6)
    M("rubber", (0.025, 0.025, 0.025), 0.75, detail="rubber")
    M("rubberBelt", (0.04, 0.04, 0.04), 0.7, detail="rubber")
    M("tire", (0.03, 0.03, 0.03), 0.85, detail="rubber")
    M("tread", (0.45, 0.45, 0.46), 0.5, 1.0, detail="tread", grime=0.4)
    M("seat", (0.10, 0.09, 0.08), 0.6, detail="leather")
    M("plasticBlack", (0.04, 0.04, 0.045), 0.5, detail="plastic")
    M("wood", (0.45, 0.30, 0.16), 0.7, detail="wood")
    M("engineGrey", (0.30, 0.34, 0.33), 0.5, 0.3, detail="castIron", grime=0.7,
      params={"smoothnessScale": 0.8, "clearCoatIntensity": 0.1, "clearCoatSmoothness": 0.2})
    M("hoseBlack", (0.02, 0.02, 0.02), 0.6, detail="rubber")
    M("wireRed", (0.55, 0.02, 0.02), 0.5, detail="plastic")
    M("wireBlack", (0.02, 0.02, 0.02), 0.5, detail="plastic")
    M("copper", (0.72, 0.42, 0.24), 0.3, 1.0, detail="silver")
    M("brownGlass", (0.18, 0.08, 0.02), 0.08, detail="plastic")
    M("crateRed", (0.48, 0.05, 0.07), 0.55, detail="plastic")
    M("gold", (0.83, 0.66, 0.30), 0.3, 1.0, detail="silver")
    M("glass", (0.55, 0.62, 0.62), 0.05, alpha=0.22, fs="glass")
    M("lampGlass", (0.95, 0.95, 0.9), 0.05, alpha=0.5, fs="glass")
    M("redGlass", (0.8, 0.05, 0.03), 0.1, fs="glass", alpha=0.85)
    M("amberGlass", (0.95, 0.5, 0.05), 0.1, fs="glass", alpha=0.85)
    M("orangeRefl", (0.95, 0.35, 0.05), 0.3, detail="plastic")
    M("decals", (1, 1, 1), 0.5, image=DECALS, fs="decal")
    M("mirror", (0.8, 0.8, 0.8), 0.02, 1.0, detail="chrome")
    M("grain", (0.85, 0.66, 0.30), 0.8, detail="plastic")
    M("inv", (0.5, 0.5, 0.5), 0.5, detail="paint")  # non-rendered helpers
    M("rimPaint", (0.80, 0.76, 0.64), 0.45, detail="calPaint", grime=0.4, params=old_paint)
    M("steelDirty", (0.35, 0.34, 0.32), 0.5, 0.8, detail="scratched")
    M("bottleGlass", (0.36, 0.16, 0.04), 0.03, alpha=0.8, fs="glass")
    M("beerLiquid", (0.75, 0.45, 0.08), 0.05, alpha=0.9, fs="glass")
    M("goldFoil", (0.86, 0.68, 0.30), 0.25, 1.0, detail="silver")
    M("goldCap", (0.80, 0.62, 0.26), 0.3, 1.0, detail="silver")


def helper_mesh(name, size, loc, parent, kind, props=None):
    """Invisible helper shape (collision, trigger, fill volume...)."""
    o = box(name, size, loc, "inv", parent, bevel=0)
    if parent is None:
        # component roots stay at the vehicle origin; offset the geometry instead
        o.data.transform(Matrix.Translation(Vector(loc)))
        o.location = (0, 0, 0)
    o["kind"] = kind
    o["nomerge"] = True
    o.hide_render = True
    for k, v in (props or {}).items():
        o[k] = v
    return o


def ball(name, r, loc, mat, parent, squash=1.0):
    import bmesh
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=18, v_segments=10, radius=r)
    if squash != 1.0:
        bmesh.ops.scale(bm, vec=Vector((1, 1, squash)), verts=bm.verts)
    return K.mesh_from_bm(name, bm, mat, parent, loc, smooth_angle=85)


# =============================================================== COMBINE

def build_combine():
    root = helper_mesh("bizon_main_component1", (1.5, 5.0, 1.6), (0, -1.9, 1.45), None, "col_root")
    root.hide_render = True
    base = empty("bizon_root", (0, 0, 0), root)

    build_wheels(base)
    vis = empty("vis", (0, 0, 0), base)
    shake_body = shaker(vis, "bodyShake", axis="Y", r=0.0015)
    body = empty("body", (0, 0, 0), shake_body)
    build_frame(body)
    build_axles(body, base)
    build_housing(body)
    build_grain_tank(body)
    build_cab(body, base)
    build_platform(body)
    shake_engine = shaker(vis, "engineShake", axis="X", r=0.0035, loc=(0, -3.1, 2.8))
    build_engine(shake_engine, base)
    build_rear(body, base)
    build_left_drives(body, base)
    build_right_side(body)
    build_electrics(body)
    build_extras(body)
    build_feeder(base)
    build_pipe(base, body)
    build_functional(base)
    build_collisions(root)
    return root


def shaker(parent, name, axis="X", r=0.002, loc=(0, 0, 0)):
    """Counter-rotating pair: outer spins +w, inner (offset r) spins -w -> pure circular vibration."""
    a = empty(name + "A", loc, parent)
    off = {"X": (0, 0, r), "Y": (r, 0, 0), "Z": (r, 0, 0)}[axis]
    b = empty(name + "B", off, a)
    inner = empty(name + "Content", (-loc[0] - off[0], -loc[1] - off[1], -loc[2] - off[2]), b)
    ANIM.setdefault("shakers", {})[name] = {"axis": axis, "r": r}
    return inner


def build_wheels(base):
    w = empty("wheels", (0, 0, 0), base)
    for side, sx in (("Left", -1), ("Right", 1)):
        wf = empty("wheelFront" + side, (sx * FRONT_X, 0, R_F + SUSP_F), w)
        ak = empty("axisBack" + side, (sx * REAR_X, -WHEELBASE, R_R + SUSP_F), w)
        empty("wheelBack" + side, (0, 0, 0), ak)
        # render-only tires/rims (the game loads its own tire library models)
        # render-only tyres/rims; in game the FS25 tyre library model for the same size is used
        D.wheel("rw_front" + side, (sx * FRONT_X, 0, R_F), R_F, 0.48, 0.3302, sx, lug_h=0.052, n_lugs=22,
                size_txt="18.4-26")
        D.wheel("rw_back" + side, (sx * REAR_X, -WHEELBASE, R_R), R_R, 0.44, 0.3048, sx, lug_h=0.035, n_lugs=24,
                lug_angle=30, size_txt="16.9-24")
    return w



def build_frame(p):
    # longitudinal frame rails under the housing
    for sx in (-1, 1):
        box("frameRail%d" % sx, (0.12, 5.2, 0.16), (sx * 0.72, -2.0, 0.62), "red", p, bevel=0.01)
    for y in (0.3, -1.2, -2.6, -4.2):
        box("frameCross%.1f" % y, (1.44, 0.1, 0.1), (0, y, 0.6), "red", p, bevel=0.008)


def build_axles(p, base):
    # front drive axle with final drives and central gearbox
    box("frontAxleBeam", (2.1, 0.24, 0.24), (0, 0, R_F), "red", p, bevel=0.02)
    for sx in (-1, 1):
        cyl("finalDrive%d" % sx, 0.24, 0.22, (sx * 0.98, 0, R_F), "red", p, verts=32, bevel=0.01)
        cyl("finalDriveCover%d" % sx, 0.2, 0.04, (sx * 1.1, 0, R_F), "metalDark", p, verts=32)
        box("finalDriveTop%d" % sx, (0.2, 0.36, 0.4), (sx * 0.98, 0.0, R_F + 0.3), "red", p, bevel=0.03)
        cyl("brakeDrum%d" % sx, 0.14, 0.1, (sx * 0.8, 0, R_F), "metalDark", p, verts=24)
    box("gearbox", (0.55, 0.45, 0.42), (0, 0.02, R_F + 0.05), "red", p, bevel=0.03)
    box("gearboxCover", (0.4, 0.3, 0.05), (0, 0.02, R_F + 0.28), "metalDark", p, bevel=0.01)
    cyl("gearboxInput", 0.07, 0.3, (0.2, -0.15, R_F + 0.25), "metalDark", p, axis="Y")
    # rear steering axle (pendulum) with knuckles and tie rod
    ry = -WHEELBASE
    box("rearAxleBeam", (1.7, 0.18, 0.2), (0, ry, R_R + 0.02), "red", p, bevel=0.015)
    cyl("rearAxlePivot", 0.08, 0.35, (0, ry, R_R + 0.02), "metalDark", p, axis="Y")
    box("rearAxleBracket", (0.3, 0.28, 0.5), (0, ry, R_R + 0.3), "red", p, bevel=0.02)
    for sx in (-1, 1):
        cyl("kingpin%d" % sx, 0.06, 0.32, (sx * 0.84, ry, R_R + 0.02), "metalDark", p, axis="Z")
        box("steerArm%d" % sx, (0.06, 0.28, 0.05), (sx * 0.84, ry - 0.16, R_R - 0.08), "metalDark", p)
    cyl("tieRod", 0.022, 1.66, (0, ry - 0.3, R_R - 0.08), "steel", p, axis="X", verts=12)
    cyl("steerCylinder", 0.045, 0.55, (-0.35, ry + 0.05, R_R + 0.15), "metalDark", p, axis="X", verts=16)
    cyl("steerCylinderRod", 0.02, 0.35, (-0.02, ry + 0.05, R_R + 0.15), "chrome", p, axis="X", verts=12)
    hose("steerHose1", (-0.62, ry + 0.05, R_R + 0.17), (-0.5, ry + 0.9, 1.2), 0.1, 0.012, "hoseBlack", p)
    hose("steerHose2", (-0.1, ry + 0.05, R_R + 0.17), (-0.45, ry + 0.9, 1.25), 0.1, 0.012, "hoseBlack", p)


def side_panel(name, x, y0, y1, z0, z1, p, sx, mat="red", ribs=4):
    t = 0.03
    box(name, (t, y0 - y1, z1 - z0), (x, (y0 + y1) / 2, (z0 + z1) / 2), mat, p, bevel=0.008)
    for i in range(ribs):
        y = y1 + (y0 - y1) * (i + 0.5) / ribs
        box(name + "_rib%d" % i, (0.025, 0.04, z1 - z0 - 0.06), (x + sx * 0.025, y, (z0 + z1) / 2), mat, p,
            bevel=0.006)
    rivets(name + "_rivT", (x + sx * 0.02, y0 - 0.03, z1 - 0.03), (x + sx * 0.02, y1 + 0.03, z1 - 0.03),
           max(3, int((y0 - y1) / 0.12)), "red", p)
    rivets(name + "_rivB", (x + sx * 0.02, y0 - 0.03, z0 + 0.03), (x + sx * 0.02, y1 + 0.03, z0 + 0.03),
           max(3, int((y0 - y1) / 0.12)), "red", p)


def build_housing(p):
    # threshing/cleaning housing: side walls, top deck, front face, underside sieve box
    for sx in (-1, 1):
        x = sx * 0.78
        side_panel("housingSideFront%d" % sx, x, 0.45, -1.3, 0.62, 2.35, p, sx, ribs=4)
        side_panel("housingSideMid%d" % sx, x, -1.33, -2.8, 0.62, 2.35, p, sx, ribs=3)
        side_panel("housingSideRear%d" % sx, x, -2.83, -4.1, 0.9, 2.35, p, sx, ribs=3)
        # inspection door with handles and hinges
        box("inspDoor%d" % sx, (0.02, 0.62, 0.5), (x + sx * 0.03, -2.0, 1.25), "red", p, bevel=0.01)
        box("inspDoorHandle%d" % sx, (0.03, 0.14, 0.025), (x + sx * 0.05, -1.8, 1.25), "metalDark", p)
        for z in (1.05, 1.45):
            cyl("inspHinge%d_%.2f" % (sx, z), 0.012, 0.06, (x + sx * 0.045, -2.31, z), "metalDark", p, axis="Z")
    box("housingTop", (1.62, 4.5, 0.04), (0, -1.8, 2.35), "red", p, bevel=0.01)
    box("housingFront", (1.56, 0.04, 0.9), (0, 0.46, 1.9), "red", p, bevel=0.01)
    box("sieveBox", (1.4, 2.6, 0.22), (0, -2.0, 0.52), "red", p, bevel=0.02)
    box("sieveBoxLip", (1.3, 0.05, 0.1), (0, -3.28, 0.47), "metalDark", p)
    # bottom augers (clean grain + returns) along X under the housing
    for i, y in enumerate((-0.55, -0.95)):
        cyl("bottomAuger%d" % i, 0.11, 1.62, (0, y, 0.52), "red", p, axis="X", verts=24)
        cyl("bottomAugerBearing%d" % i, 0.06, 1.72, (0, y, 0.52), "metalDark", p, axis="X", verts=12)
    # drum cover bulge
    cyl("drumCover", 0.36, 1.58, (0, 0.05, 1.3), "red", p, axis="X", verts=36)
    # stone trap
    box("stoneTrap", (1.2, 0.3, 0.2), (0, 0.25, 0.72), "metalDark", p, bevel=0.01)


def build_grain_tank(p):
    # trapezoid cross-section tank, 3.2 m3
    y0, y1 = 0.32, -2.25
    prof = [(-0.8, 2.37), (0.8, 2.37), (1.14, 2.85), (1.14, 3.46), (-1.14, 3.46), (-1.14, 2.85)]
    prof_yz = [(y, z) for (x, z) in prof for y in ()]  # noqa: F841 (placeholder, not used)
    # build as XZ polygon extruded along Y
    o = poly_prism("grainTank", prof, y0 - y1, "red", p, plane="XZ", offset=y1, bevel=0.012)
    # top rim + reinforcement bands
    for sx in (-1, 1):
        box("tankRim%d" % sx, (0.06, y0 - y1 + 0.04, 0.06), (sx * 1.15, (y0 + y1) / 2, 3.47), "red", p, bevel=0.01)
        for i, y in enumerate((-0.2, -0.95, -1.7)):
            box("tankBand%d_%d" % (sx, i), (0.035, 0.05, 0.6), (sx * 1.155, y, 3.15), "red", p, bevel=0.006)
    for y in (y0 + 0.02, y1 - 0.02):
        box("tankRimF%.2f" % y, (2.36, 0.06, 0.06), (0, y, 3.47), "red", p, bevel=0.01)
    # top grid cover (galvanized mesh bars)
    for i in range(12):
        x = -1.05 + i * (2.1 / 11)
        box("tankGridX%d" % i, (0.012, y0 - y1 - 0.1, 0.02), (x, (y0 + y1) / 2, 3.49), "galv", p, bevel=0)
    for i in range(9):
        y = y1 + 0.1 + i * ((y0 - y1 - 0.2) / 8)
        box("tankGridY%d" % i, (2.2, 0.012, 0.02), (0, y, 3.5), "galv", p, bevel=0)
    # inspection window on the front (seen from the cab)
    box("tankWindowFrame", (0.5, 0.03, 0.3), (0.35, y0 + 0.012, 3.12), "metalDark", p, bevel=0.01)
    box("tankWindow", (0.42, 0.02, 0.22), (0.35, y0 + 0.02, 3.12), "glass", p, bevel=0.005)
    # filling auger (visible through the grid, spins while threshing)
    fa = empty("tankFillAuger", (0.35, -0.4, 3.25), p)
    ANIM.setdefault("thresh_rot", []).append(("tankFillAuger", "Y", -420))
    cyl("tankFillAugerShaft", 0.03, 1.4, (0, 0, 0), "steel", fa, axis="Y", verts=10)
    for i in range(14):
        box("tankFillFlight%d" % i, (0.24, 0.012, 0.05), (0, -0.65 + i * 0.1, 0), "galv", fa, bevel=0,
            rot=(0, i * 0.9, 0))
    # decals
    decal("dBizonL", (-1.182, -0.72, 3.13), (1.3, 0.325), REG["bizon"], "decals", p, "-X")
    decal("dBizonR", (1.182, -0.72, 3.13), (1.3, 0.325), REG["bizon"], "decals", p, "+X")
    decal("dPlateR", (0.797, 0.12, 2.12), (0.26, 0.13), REG["plate"], "decals", p, "+X")
    decal("dSuperMidL", (-0.797, -3.75, 1.15), (0.66, 0.165), REG["super"], "decals", p, "-X")
    decal("dWarnR", (0.797, -2.0, 0.83), (0.6, 0.075), REG["stripes"], "decals", p, "+X")


def build_cab(p, base):
    cab = empty("cab", (0, 0, 0), p)
    x0, x1 = -0.72, 0.72
    yf, yb = 1.45, 0.35
    zf, zt = 2.2, 3.82
    # frame pillars (front pillars lean forward at the top: classic Bizon cab)
    lean = 0.18
    pillars = [((x0, yf, zf), (x0, yf + lean, zt)), ((x1, yf, zf), (x1, yf + lean, zt)),
               ((x0, yb, zf), (x0, yb, zt)), ((x1, yb, zf), (x1, yb, zt)),
               ((x0, (yf + yb) / 2 + 0.05, zf), (x0, (yf + yb) / 2 + 0.05 + lean * 0.4, zt))]
    for i, (a, b) in enumerate(pillars):
        prof = [(math.cos(t) * 0.028 * (1.25 if abs(math.cos(t)) > 0.7 else 1), math.sin(t) * 0.028)
                for t in [2 * math.pi * k / 12 for k in range(12)]]
        sweep("cabPillar%d" % i, [a, b], 0, "black", cab, profile=prof)
    # lower cab body (sheet metal up to window line) + door
    box("cabLowerBack", (1.44, 0.04, 0.55), (0, yb, zf + 0.28), "red", cab, bevel=0.01)
    box("cabLowerRight", (0.03, 1.1, 0.5), (x1, 0.9, zf + 0.25), "red", cab, bevel=0.01)
    box("cabDoorLower", (0.03, 0.6, 0.45), (x0, 1.12, zf + 0.25), "red", cab, bevel=0.01)
    box("cabDoorHandle", (0.03, 0.12, 0.025), (x0 - 0.03, 0.9, zf + 0.62), "chrome", cab)
    box("cabFloor", (1.44, 1.1, 0.04), (0, 0.9, zf), "tread", cab, bevel=0.005)
    # roof: cream, with overhang and rain gutter
    box("cabRoof", (1.62, 1.45, 0.1), (0, 0.98, zt + 0.05), "cream", cab, bevel=0.035, segs=3)
    box("cabRoofTop", (1.4, 1.2, 0.06), (0, 0.98, zt + 0.12), "cream", cab, bevel=0.03, segs=3)
    box("cabVisor", (1.5, 0.22, 0.03), (0, yf + lean + 0.12, zt - 0.02), "black", cab, bevel=0.01,
        rot=(-0.25, 0, 0))
    # glass
    def glass(name, corners):
        import bmesh
        bm = bmesh.new()
        vs = [bm.verts.new(c) for c in corners]
        bm.faces.new(vs)
        o = K.mesh_from_bm(name, bm, "glass", cab, smooth_angle=None)
        o["twosided"] = True
        return o
    glass("glassFront", [(x0 + 0.02, yf, zf + 0.5), (x1 - 0.02, yf, zf + 0.5),
                         (x1 - 0.02, yf + lean, zt - 0.02), (x0 + 0.02, yf + lean, zt - 0.02)])
    glass("glassFrontLow", [(x0 + 0.02, yf, zf + 0.05), (x1 - 0.02, yf, zf + 0.05),
                            (x1 - 0.02, yf, zf + 0.48), (x0 + 0.02, yf, zf + 0.48)])
    glass("glassBack", [(x1 - 0.02, yb, zf + 0.58), (x0 + 0.02, yb, zf + 0.58),
                        (x0 + 0.02, yb, zt - 0.02), (x1 - 0.02, yb, zt - 0.02)])
    glass("glassRight", [(x1, yb + 0.02, zf + 0.52), (x1, yf - 0.02, zf + 0.52),
                         (x1, yf + lean - 0.02, zt - 0.02), (x1, yb + 0.02, zt - 0.02)])
    glass("glassDoor", [(x0, yf - 0.02, zf + 0.5), (x0, 0.83, zf + 0.5),
                        (x0, 0.83 + lean * 0.4, zt - 0.02), (x0, yf + lean - 0.02, zt - 0.02)])
    glass("glassLeftRear", [(x0, 0.8, zf + 0.5), (x0, yb + 0.02, zf + 0.5),
                            (x0, yb + 0.02, zt - 0.02), (x0, 0.8 + lean * 0.35, zt - 0.02)])
    # window rubber seals
    for i, (a, b) in enumerate([((x0, yf, zf + 0.5), (x1, yf, zf + 0.5)),
                                ((x0, yf + lean, zt - 0.03), (x1, yf + lean, zt - 0.03))]):
        sweep("cabSeal%d" % i, [a, b], 0.012, "rubber", cab, verts=6)
    # wipers (static)
    for sx in (-0.3, 0.3):
        sweep("wiper%.1f" % sx, [(sx, yf + 0.03, zf + 0.62), (sx - 0.12, yf + 0.03 + lean * 0.45, zf + 1.1)], 0.008,
              "black", cab, verts=6)
        cyl("wiperMotor%.1f" % sx, 0.03, 0.06, (sx, yf - 0.02, zf + 0.6), "black", cab, axis="Y")
    # mirrors on arms
    for sx in (-1, 1):
        a = Vector((sx * 0.74, yf + 0.05, zt - 0.3))
        b = Vector((sx * 1.12, yf + 0.25, zt - 0.2))
        sweep("mirrorArm%d" % sx, [a, a + Vector((sx * 0.2, 0.1, 0.05)), b], 0.012, "black", cab, verts=8)
        box("mirrorHead%d" % sx, (0.2, 0.05, 0.3), tuple(b + Vector((0, 0, -0.1))), "black", cab, bevel=0.015)
        box("mirrorGlass%d" % sx, (0.18, 0.012, 0.27), tuple(b + Vector((0, -0.028, -0.1))), "mirror", cab,
            bevel=0.004)
    # interior
    seat = empty("seat", (0.0, 0.62, zf), cab)
    box("seatPlate", (0.42, 0.42, 0.03), (0, 0.02, 0.02), "metalDark", seat, bevel=0.008)
    cyl("seatBellows", 0.13, 0.2, (0, 0.02, 0.14), "rubber", seat, axis="Z", verts=24)
    for i in range(4):
        tube("seatBellowsRib%d" % i, 0.14, 0.12, 0.018, (0, 0.02, 0.07 + i * 0.045), "rubber", seat, axis="Z",
             verts=24)
    box("seatPan", (0.46, 0.44, 0.05), (0, 0.02, 0.27), "metalDark", seat, bevel=0.01)
    box("seatCushion", (0.5, 0.48, 0.12), (0, 0.02, 0.36), "seat", seat, bevel=0.05, segs=4)
    box("seatBack", (0.5, 0.1, 0.55), (0, -0.2, 0.7), "seat", seat, bevel=0.045, segs=4, rot=(0.12, 0, 0))
    box("seatHeadRest", (0.3, 0.08, 0.14), (0, -0.25, 1.06), "seat", seat, bevel=0.035, segs=4, rot=(0.12, 0, 0))
    for sx in (-1, 1):
        box("seatArm%d" % sx, (0.06, 0.34, 0.055), (sx * 0.29, 0.0, 0.58), "seat", seat, bevel=0.025, segs=3)
        sweep("seatArmPost%d" % sx, [(sx * 0.29, -0.14, 0.3), (sx * 0.29, -0.14, 0.56)], 0.012, "metalDark", seat,
              verts=8)
    # sloped toe board with rubber mat in front of the pedals (feet rest here, nothing pokes out)
    box("toeBoard", (1.3, 0.035, 0.46), (0, 1.33, zf + 0.21), "red", cab, bevel=0.012, rot=(-0.42, 0, 0))
    box("toeMat", (1.0, 0.012, 0.4), (0, 1.31, zf + 0.21), "rubber", cab, bevel=0.004, rot=(-0.42, 0, 0))
    box("floorMat", (0.56, 0.62, 0.012), (0, 0.9, zf + 0.026), "rubber", cab, bevel=0.004)
    # steering column + wheel (driver geometry follows the shipped Claas Arion: feet ~0.46 m ahead of and
    # ~0.42 m below the hip node)
    col_base = Vector((0, 1.24, zf + 0.02))
    col_top = Vector((0, 0.98, zf + 0.88))
    sweep("steerColumn", [col_base, col_top], 0.032, "black", cab, verts=16)
    shroud_top = col_base.lerp(col_top, 0.72)
    sweep("steerShroud", [col_base.lerp(col_top, 0.25), shroud_top], 0.055, "black", cab, verts=20)
    cyl("steerShroudCap", 0.055, 0.03, tuple(shroud_top), "black", cab, rot=(math.atan2(-(col_top - col_base).y,
        (col_top - col_base).z), 0, 0), r2=0.04, verts=20)
    # Drivable spins the steeringWheel node about its local Y (GIANTS) = Blender local Z, so the
    # column tilt lives on the parent and the wheel itself keeps an identity rotation.
    axis = (col_top - col_base).normalized()
    tilt = math.atan2(-axis.y, axis.z)
    swt = empty("steeringColumnTilt", tuple(col_top), cab, rot=(tilt, 0, 0))
    swr = empty("steeringWheel", (0, 0, 0), swt)
    rim_pts = [(math.cos(2 * math.pi * k / 48) * 0.19, math.sin(2 * math.pi * k / 48) * 0.19, 0) for k in range(48)]
    sweep("steerRim", rim_pts, 0.017, "black", swr, verts=12, closed=True)
    for i in range(3):
        a = i * 2 * math.pi / 3 + math.pi / 2
        sweep("steerSpoke%d" % i, [(math.cos(a) * 0.035, math.sin(a) * 0.035, -0.03),
                                   (math.cos(a) * 0.11, math.sin(a) * 0.11, -0.012),
                                   (math.cos(a) * 0.18, math.sin(a) * 0.18, 0)], 0.009, "steel", swr, verts=10)
    cyl("steerHub", 0.045, 0.05, (0, 0, -0.03), "black", swr, axis="Z", verts=24, bevel=0.008)
    ball("steerHubCap", 0.035, (0, 0, -0.005), "black", swr, squash=0.45)
    # dashboard with round gauges + needles
    dash = empty("dash", (0, 1.28, zf + 0.85), cab)
    box("dashPanel", (0.7, 0.05, 0.22), (0, 0, 0), "black", dash, bevel=0.03, segs=4, rot=(-0.5, 0, 0))
    box("dashHood", (0.74, 0.14, 0.025), (0, -0.05, 0.11), "black", dash, bevel=0.012, segs=3, rot=(-0.15, 0, 0))
    box("dashPedestal", (0.3, 0.14, 0.7), (0, 0.06, -0.42), "black", dash, bevel=0.035, segs=4)
    for nm, x, reg in (("rpm", -0.18, "gauge_rpm"), ("speed", 0.18, "gauge_speed")):
        g = decal("gauge_" + nm, (x, -0.035, 0.012), (0.12, 0.12), REG[reg], "decals", dash, "-Y")
        g.rotation_euler = (-0.5, 0, 0)
        tube("gaugeBezel_" + nm, 0.066, 0.06, 0.012, (x, -0.036, 0.013), "chrome", dash, axis="Y")
        n = empty(nm + "Needle", (x, -0.045, 0.017), dash, rot=(-0.5, 0, 0))
        needle_rest = empty(nm + "NeedleRest", (0, 0, 0), n)
        box(nm + "NeedleMesh", (0.005, 0.002, 0.05), (0, 0, 0.022), "orangeRefl", needle_rest, bevel=0)
        ANIM.setdefault("needles", []).append(nm + "Needle")
    for i in range(5):
        cyl("dashSwitch%d" % i, 0.008, 0.02, (-0.1 + i * 0.05, -0.02, -0.07), "chrome", dash, axis="Y")
    ik = empty("ignitionKey", (0.28, -0.03, -0.06), dash)
    box("ignitionKeyMesh", (0.012, 0.03, 0.03), (0, -0.015, 0), "steel", ik, bevel=0.003)
    # levers: throttle, header, reel, variator
    for i, (x, h, knob) in enumerate(((0.33, 0.55, "red"), (0.38, 0.5, "black"), (0.43, 0.48, "yellow"),
                                       (-0.35, 0.45, "black"))):
        z0 = zf + (0.3 if x > 0 else 0.25)
        sweep("lever%d" % i, [(x, 0.8, z0), (x, 0.83, z0 + h * 0.6), (x, 0.87, z0 + h)], 0.009, "steel", cab,
              verts=10)
        cyl("leverBoot%d" % i, 0.03, 0.07, (x, 0.8, z0 + 0.03), "rubber", cab, axis="Z", r2=0.012, verts=16)
        ball("leverKnob%d" % i, 0.024, (x, 0.87, z0 + h + 0.015), knob, cab, squash=1.15)
    box("leverConsole", (0.18, 0.4, 0.3), (0.38, 0.78, zf + 0.15), "red", cab, bevel=0.04, segs=4)
    box("leverConsoleTop", (0.16, 0.36, 0.012), (0.38, 0.78, zf + 0.302), "rubber", cab, bevel=0.004)
    for i, x in enumerate((-0.14, 0.12, 0.24)):
        box("pedal%d" % i, (0.08, 0.025, 0.13), (x, 1.12, zf + 0.13), "rubber", cab, bevel=0.012, segs=3,
            rot=(-0.7, 0, 0))
        sweep("pedalArm%d" % i, [(x, 1.15, zf + 0.12), (x, 1.25, zf + 0.2), (x, 1.36, zf + 0.3)], 0.011,
              "metalDark", cab, verts=8)
    # beer crate on the cab floor in the left rear corner, next to the seat
    D.beer_crate("beerCrate", (-0.51, 0.56, zf + 0.022), cab, REG, rot_z=math.pi / 2 + 0.05, full=19)
    D.beer_bottle("beerOpen", (-0.56, 0.86, zf + 0.022), cab, REG, opened=True, rot_z=2.2)
    # radio + CB, sun-visor stickers
    box("radio", (0.2, 0.15, 0.06), (0.4, 1.25, zt - 0.1), "black", cab, bevel=0.01)
    # beacon mounting plate, flush on the roof top (the FS beacon model sits on it)
    box("beaconMount", (0.2, 0.2, 0.014), (BEACON_SPOT[0], BEACON_SPOT[1], zt + 0.157), "black", cab, bevel=0.004)
    box("radioFace", (0.18, 0.005, 0.045), (0.4, 1.325, zt - 0.1), "steel", cab, bevel=0)
    sweep("cbAntenna", [(0.6, 0.45, zt + 0.12), (0.6, 0.45, zt + 1.0)], 0.004, "black", cab, verts=6)
    cyl("cbAntennaBase", 0.03, 0.05, (0.6, 0.45, zt + 0.14), "black", cab, axis="Z")
    # roof lamps (render placeholders, real lamps are FS shared assets at the link nodes)
    for nm, loc in LAMP_SPOTS.items():
        rl = empty("rlamp_" + nm, loc, None, props={"export": False})
        o = cyl(nm + "_r", 0.08, 0.1, (0, 0, 0), "black", rl, axis="Y")
        o["export"] = False
        o = cyl(nm + "_rg", 0.07, 0.01, (0, 0.055, 0), "lampGlass", rl, axis="Y")
        o["export"] = False
    # horn trumpets (chrome, typical add-on)
    for i, (x, ln) in enumerate(((0.35, 0.34), (0.47, 0.42))):
        cyl("horn%d" % i, 0.045, ln, (x, 0.6, zt + 0.2), "chrome", cab, axis="Y", r2=0.015, verts=20)
        box("hornBracket%d" % i, (0.03, 0.05, 0.05), (x, 0.6, zt + 0.16), "black", cab)
    EN.cab_details(cab, zf, zt, yf, yb, x0, x1, lean)
    return cab


LAMP_SPOTS = {
    "workLightFL": (-0.62, 1.66, 3.97),
    "workLightFR": (0.62, 1.66, 3.97),
    "workLightFL2": (-0.25, 1.68, 3.97),
    "workLightFR2": (0.25, 1.68, 3.97),
}
# away from the horn trumpets (x 0.35..0.47), top of beaconMount = roof top 3.97 + 0.014
BEACON_SPOT = (-0.35, 0.62, 3.984)



def build_platform(p):
    zf = 2.18
    box("platform", (2.4, 1.55, 0.05), (0, 0.85, zf - 0.03), "tread", p, bevel=0.008)
    box("platformEdgeF", (2.42, 0.06, 0.12), (0, 1.62, zf - 0.06), "red", p, bevel=0.01)
    for sx in (-1, 1):
        box("platformEdgeS%d" % sx, (0.06, 1.55, 0.12), (sx * 1.2, 0.85, zf - 0.06), "red", p, bevel=0.01)
        box("platformBrace%d" % sx, (0.06, 0.06, 0.9), (sx * 1.0, 1.3, zf - 0.5), "red", p, bevel=0.01,
            rot=(0.5, 0, 0))
    # railings (yellow like the factory ones)
    rail_pts_l = [(-1.18, 0.12, zf), (-1.18, 0.12, zf + 1.0), (-1.18, 0.62, zf + 1.0)]
    rail_pts_r = [(1.18, 0.12, zf), (1.18, 0.12, zf + 1.0), (1.18, 1.58, zf + 1.0), (1.18, 1.58, zf)]
    sweep("railL", rail_pts_l, 0.02, "yellow", p, verts=10)
    sweep("railR", rail_pts_r, 0.02, "yellow", p, verts=10)
    sweep("railRmid", [(1.18, 0.12, zf + 0.5), (1.18, 1.58, zf + 0.5)], 0.015, "yellow", p, verts=8)
    sweep("railFront", [(0.75, 1.6, zf), (0.75, 1.6, zf + 1.0), (1.18, 1.58, zf + 1.0)], 0.02, "yellow", p,
          verts=10)
    sweep("railFrontL", [(-0.75, 1.6, zf), (-0.75, 1.6, zf + 1.0), (-0.95, 1.6, zf + 1.0)], 0.02, "yellow", p,
          verts=10)
    # ladder on the left, in front of the left wheel
    lad = empty("ladder", (-1.12, 1.25, 0), p)
    for sx in (-0.2, 0.2):
        sweep("ladderStringer%.1f" % sx, [(sx, 0.0, 0.35), (sx, 0.18, zf)], 0.018, "yellow", lad, verts=8)
    for i in range(6):
        z = 0.45 + i * (zf - 0.55) / 5.5
        yy = 0.18 * (z - 0.35) / (zf - 0.35)
        box("ladderStep%d" % i, (0.38, 0.12, 0.025), (0, yy, z), "tread", lad, bevel=0.004)
    sweep("ladderGrab", [(-0.25, 0.2, zf), (-0.25, 0.25, zf + 0.9), (-0.25, 0.0, zf + 1.0)], 0.017, "yellow",
          lad, verts=8)
    # headlights on the front railing + turn signals
    for sx in (-1, 1):
        hl = empty("headlight%d" % sx, (sx * 0.95, 1.66, zf + 1.02), p)
        cyl("headlightBody%d" % sx, 0.09, 0.12, (0, 0, 0), "black", hl, axis="Y", verts=24)
        cyl("headlightGlass%d" % sx, 0.08, 0.01, (0, 0.065, 0), "lampGlass", hl, axis="Y", verts=24)
        tube("headlightRing%d" % sx, 0.092, 0.08, 0.02, (0, 0.06, 0), "chrome", hl, axis="Y", verts=24)
        box("headlightBracket%d" % sx, (0.03, 0.03, 0.12), (0, -0.02, -0.1), "black", hl)
        tl = empty("turnFront%d" % sx, (sx * 1.18, 1.64, zf + 0.75), p)
        box("turnFrontBody%d" % sx, (0.08, 0.06, 0.08), (0, 0, 0), "black", tl, bevel=0.01)
        box("turnFrontGlass%d" % sx, (0.07, 0.01, 0.07), (0, 0.03, 0), "amberGlass", tl, bevel=0.004)
    # fire extinguisher on the left railing
    ex = empty("extinguisher", (-1.1, 0.25, zf + 0.05), p)
    cyl("extBody", 0.07, 0.45, (0, 0, 0.25), "redClean", ex, axis="Z", verts=20)
    cyl("extTop", 0.03, 0.06, (0, 0, 0.5), "black", ex, axis="Z")
    sweep("extHose", [(0.03, 0, 0.52), (0.08, 0.02, 0.4), (0.075, 0.02, 0.15)], 0.008, "rubber", ex, verts=6)
    box("extBracket", (0.02, 0.16, 0.05), (0, -0.06, 0.3), "black", ex)


def build_engine(p, base):
    """Engine bay behind the tank: SW-400 block, air filter, radiator + rotating screen (left)."""
    e = empty("engineBay", (0, 0, 0), p)
    y0, y1 = -2.28, -3.95
    # side covers: right side louvered panel, left side open frame around radiator screen
    box("engineDeck", (1.72, y0 - y1, 0.04), (0, (y0 + y1) / 2, 2.38), "red", e, bevel=0.01)
    box("engineRoofF", (1.72, 0.5, 0.05), (0, y0 - 0.25, 3.3), "red", e, bevel=0.015)
    box("engineRoofR", (1.72, 0.45, 0.05), (0, y1 + 0.23, 3.3), "red", e, bevel=0.015)
    for sx in (-1, 1):
        for y in (y0 - 0.02, y1 + 0.02):
            box("enginePost%d_%.1f" % (sx, y), (0.05, 0.05, 0.92), (sx * 0.84, y, 2.84), "red", e, bevel=0.008)
    # right side louvres
    box("engineSideR", (0.03, 0.55, 0.8), (0.86, y0 - 0.35, 2.8), "red", e, bevel=0.008)
    for i in range(8):
        box("louvre%d" % i, (0.05, 0.5, 0.02), (0.88, y0 - 0.35, 2.48 + i * 0.09), "red", e, bevel=0.004,
            rot=(0, -0.5, 0))
    decal("dEngine", (0.878, y1 + 0.5, 3.05), (0.36, 0.09), REG["engine"], "decals", e, "+X")
    # rear right cover with hinged louvred door, handle and hinges
    box("engineSideR2", (0.03, 0.95, 0.8), (0.86, y1 + 0.55, 2.8), "red", e, bevel=0.01)
    for i in range(6):
        box("louvreR2_%d" % i, (0.04, 0.7, 0.018), (0.885, y1 + 0.6, 2.55 + i * 0.075), "red", e, bevel=0.004,
            rot=(0, -0.5, 0))
    box("engineDoorHandle", (0.04, 0.12, 0.03), (0.89, y1 + 0.2, 2.95), "metalDark", e, bevel=0.006)
    for z in (2.5, 3.1):
        cyl("engineHinge%.1f" % z, 0.014, 0.08, (0.885, y1 + 1.02, z), "metalDark", e, axis="Z", verts=10)
    # expanded-metal style top grille between the roof sections (air in for the radiator)
    gy0, gy1 = y0 - 0.5, y1 + 0.45
    for i in range(24):
        x = -0.8 + i * (1.6 / 23)
        box("topGrillX%d" % i, (0.01, gy0 - gy1, 0.025), (x, (gy0 + gy1) / 2, 3.3), "metalDark", e, bevel=0)
    for i in range(12):
        y = gy1 + i * ((gy0 - gy1) / 11)
        box("topGrillY%d" % i, (1.64, 0.01, 0.02), (0, y, 3.315), "metalDark", e, bevel=0)
    # left: shroud around the rotating screen
    tube("screenShroud", 0.5, 0.45, 0.12, (-0.84, -3.1, 2.82), "red", e, axis="X", verts=56)
    box("engineSideL_F", (0.03, 0.3, 0.8), (-0.86, y0 - 0.17, 2.8), "red", e, bevel=0.01)
    box("engineSideL_R", (0.03, 0.35, 0.8), (-0.86, y1 + 0.2, 2.8), "red", e, bevel=0.01)
    # engine block
    blk = empty("engineBlock", (0.05, -3.1, 2.75), e)
    EN.build_sw400(blk, ANIM)
    # oil-bath air cleaner above the roof, hose down to the intake manifold inlet
    EN.build_air_filter(e, (0.45, y1 + 0.6, 3.45), (0.32, -3.1, 3.08))
    # exhaust: vertical pipe with rain flap
    ex = [(-0.35, -3.1, 3.0), (-0.45, -3.2, 3.2), (-0.45, -3.25, 3.4), (-0.45, -3.25, 4.05)]
    sweep("exhaustPipe", ex, 0.055, "rust", e, verts=16)
    cyl("muffler", 0.11, 0.6, (-0.45, -3.25, 3.55), "black", e, axis="Z", verts=24)
    flap = empty("exhaustFlap", (-0.45, -3.19, 4.05), e)
    cyl("exhaustFlapMesh", 0.065, 0.01, (0, -0.06, 0.005), "rust", flap, axis="Z", verts=16)
    ANIM["exhaustFlap"] = "exhaustFlap"
    # radiator + rotating screen drum on the left side
    box("radiator", (0.12, 0.9, 0.78), (-0.72, -3.1, 2.8), "black", e, bevel=0.01)
    for i in range(12):
        box("radFin%d" % i, (0.13, 0.86, 0.01), (-0.72, -3.1, 2.44 + i * 0.065), "metalDark", e, bevel=0)
    scr = empty("radiatorScreen", (-0.86, -3.1, 2.82), e)
    ANIM.setdefault("motor_rot", []).append(("radiatorScreen", "X", 90))
    tube("screenDrumRim", 0.43, 0.39, 0.1, (0, 0, 0), "red", scr, axis="X", verts=48)
    cyl("screenMesh", 0.39, 0.02, (-0.02, 0, 0), "metalDark", scr, axis="X", verts=48)
    for i in range(10):
        a = i * math.pi / 5
        box("screenBar%d" % i, (0.03, 0.8, 0.03), (-0.04, 0, 0), "red", scr, bevel=0.004, rot=(a, 0, 0))
    for i in range(4):
        box("screenWiper%d" % i, (0.02, 0.36, 0.05), (-0.055, math.cos(i * math.pi / 2) * 0.18,
                                                   math.sin(i * math.pi / 2) * 0.18), "rubber", scr,
            bevel=0.005, rot=(i * math.pi / 2 + math.pi / 2, 0, 0))
    cyl("screenHub", 0.06, 0.08, (-0.06, 0, 0), "metalDark", scr, axis="X")
    # radiator hoses + expansion tank
    hose("radHoseTop", (-0.66, -2.8, 3.1), (-0.15, -2.55, 3.05), 0.05, 0.03, "hoseBlack", e)
    hose("radHoseBot", (-0.66, -3.4, 2.5), (-0.15, -3.4, 2.5), 0.05, 0.03, "hoseBlack", e)
    cyl("expansionTank", 0.08, 0.3, (-0.55, -2.55, 3.2), "cream", e, axis="Y", verts=20)
    # diesel tank behind the engine (right)
    EN.build_fuel_tank(e, (0.5, y1 - 0.05, 2.7))
    hose("fuelLine", (0.35, y1 + 0.1, 2.5), (0.3, -3.1, 2.6), 0.08, 0.008, "hoseBlack", e)
    return e


def build_rear(p, base):
    # straw walker hood sloping down to the back + walkers visible at the rear
    y0, y1 = -4.1, -5.3
    hood = [(y0, 2.37), (y1 + 0.2, 1.95), (y1, 1.85), (y1, 1.5), (y0, 1.5)]
    for sx in (-1, 1):
        poly_prism("hoodSide%d" % sx, hood, 0.03, "red", p, plane="YZ", offset=sx * 0.78 - (0.03 if sx > 0 else 0))
    # hood roof (bent sheet)
    box("hoodRoof", (1.6, 1.25, 0.03), (0, (y0 + y1) / 2 + 0.05, 2.14), "red", p, bevel=0.008,
        rot=(math.atan2(0.42, 1.2), 0, 0))
    decal("dSuperL", (-0.795, -4.62, 1.78), (0.8, 0.2), REG["super"], "decals", p, "-X")
    decal("dSuperR", (0.795, -4.62, 1.78), (0.8, 0.2), REG["super"], "decals", p, "+X")
    decal("dWarnL", (-0.795, -2.05, 0.83), (0.6, 0.075), REG["stripes"], "decals", p, "-X")
    # straw curtain flaps
    for i in range(6):
        box("strawFlap%d" % i, (0.25, 0.01, 0.4), (-0.63 + i * 0.252, y1 - 0.02, 1.62), "rubber", p, bevel=0.003)
    # walkers (4) sawtooth ends, shaken in two phases by counter-rotating pairs
    wroot = empty("walkers", (0, -4.28, 1.3), p)
    wa = empty("walkerShakeA", (0, 0, 0), wroot)
    for ph, (off, idx) in enumerate(((0.04, (0, 2)), (-0.04, (1, 3)))):
        wb = empty("walkerShakeB%d" % ph, (0, 0, off), wa)
        for i in idx:
            x = -0.57 + i * 0.38
            EN.hollow_walker("walker%d" % i, x, wb)
    ANIM["walkers"] = {"A": "walkerShakeA", "B": ["walkerShakeB0", "walkerShakeB1"]}
    # chaff spreader / sieve outlet under the rear
    for sx in (-1, 1):
        box("chafferFrame%d" % sx, (0.03, 0.4, 0.08), (sx * 0.65, -3.45, 0.62), "galv", p, bevel=0.005)
    for k in range(10):
        box("chafferSlat%d" % k, (1.28, 0.035, 0.004), (0, -3.63 + k * 0.04, 0.62), "galv", p, bevel=0,
            rot=(0.6, 0, 0))
    # rear: tail lights, turn signals, slow vehicle triangle, number plate
    for sx in (-1, 1):
        tl = empty("tailLight%d" % sx, (sx * 0.72, y1 - 0.02, 1.62), p)
        cyl("tailLightBody%d" % sx, 0.06, 0.05, (0, 0, 0), "black", tl, axis="Y")
        cyl("tailLightGlass%d" % sx, 0.052, 0.01, (0, -0.03, 0), "redGlass", tl, axis="Y")
        ta = empty("turnRear%d" % sx, (sx * 0.72, y1 - 0.02, 1.47), p)
        cyl("turnRearBody%d" % sx, 0.05, 0.05, (0, 0, 0), "black", ta, axis="Y")
        cyl("turnRearGlass%d" % sx, 0.043, 0.01, (0, -0.03, 0), "amberGlass", ta, axis="Y")
    tri = [(-0.2, 0), (0.2, 0), (0, 0.35)]
    poly_prism("slowSign", tri, 0.02, "orangeRefl", p, plane="XZ", offset=y1 - 0.05)
    for o in (bpy.data.objects["slowSign"],):
        o.location = (0, 0, 1.95)
    innertri = [(-0.12, 0.06), (0.12, 0.06), (0, 0.26)]
    poly_prism("slowSignInner", innertri, 0.022, "redClean", p, plane="XZ", offset=y1 - 0.052)
    bpy.data.objects["slowSignInner"].location = (0, 0, 1.95)
    decal("dPlateNr", (0, y1 - 0.035, 1.45), (0.34, 0.085), REG["plate_number"], "decals", p, "-Y")
    # rear ladder to the engine deck
    for sx in (0.55, 0.85):
        sweep("rearLadder%.2f" % sx, [(sx, -4.05, 1.0), (sx, -4.0, 2.4)], 0.014, "yellow", p, verts=8)
    for i in range(4):
        sweep("rearLadderStep%d" % i, [(0.55, -4.03, 1.2 + i * 0.3), (0.85, -4.03, 1.2 + i * 0.3)], 0.012,
              "yellow", p, verts=6)
    # flag pole with polish flag at rear right corner of the engine deck
    sweep("flagPole", [(0.8, -3.9, 3.3), (0.8, -3.9, 4.6)], 0.012, "steel", p, verts=8)
    flag_mesh(p)


def flag_mesh(p):
    import bmesh
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("uv0")
    nu, nv = 10, 5
    w, h = 0.6, 0.38
    vs = []
    for j in range(nv + 1):
        row = []
        for i in range(nu + 1):
            u = i / nu
            row.append(bm.verts.new((0.8 + math.sin(u * 5.0) * 0.05 * u, -3.9 - u * w, 4.58 - h + j / nv * h)))
        vs.append(row)
    u0, v0, u1, v1 = REG["flag"]
    for j in range(nv):
        for i in range(nu):
            f = bm.faces.new((vs[j][i], vs[j][i + 1], vs[j + 1][i + 1], vs[j + 1][i]))
            for loop, (a, b) in zip(f.loops, ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1))):
                loop[uv].uv = (u0 + (u1 - u0) * a / nu, v0 + (v1 - v0) * b / nv)
    o = K.mesh_from_bm("flag", bm, "decals", p, smooth_angle=80)
    o["keep_uv"] = True
    o["twosided"] = True


def build_left_drives(p, base):
    """Left side: engine -> countershaft -> drum variator, fan, walkers, sieves, elevator chains."""
    x = -0.9
    d = empty("leftDrives", (0, 0, 0), p)
    parts = {
        # name: (y, z, r, spokes)
        "pEngineOut": (-2.55, 2.5, 0.2, 5),
        "pCounter": (-1.35, 2.05, 0.32, 6),
        "pCounterSmall": (-1.35, 2.05, 0.14, 4),
        "pDrumVariator": (0.05, 1.3, 0.42, 6),
        "pFan": (-0.45, 0.75, 0.2, 5),
        "pWalkerCrank": (-3.05, 1.82, 0.3, 5),
        "pSieve": (-1.9, 0.95, 0.16, 4),
        "pBeater": (-0.6, 1.6, 0.18, 4),
    }
    xs = {"pEngineOut": x - 0.02, "pCounter": x, "pCounterSmall": x - 0.07, "pDrumVariator": x - 0.04,
          "pFan": x - 0.07, "pWalkerCrank": x, "pSieve": x - 0.07, "pBeater": x}
    speeds = {"pEngineOut": 900, "pCounter": 520, "pCounterSmall": 520, "pDrumVariator": 430, "pFan": 900,
              "pWalkerCrank": 380, "pSieve": 700, "pBeater": 800}
    for nm, (y, z, r, sp) in parts.items():
        mat = "cream" if nm in ("pDrumVariator", "pCounter") else "red"
        pulley(nm, r, 0.05, (xs[nm], y, z), mat, d, spokes=sp, axis="X")
        ANIM.setdefault("thresh_rot" if nm != "pEngineOut" else "motor_rot", []).append((nm, "X", speeds[nm]))
        # shaft stubs + bearing housings into the wall
        cyl(nm + "_shaft", 0.03, abs(xs[nm] + 0.78) + 0.05, ((xs[nm] - 0.78) / 2, y, z), "steel", d, axis="X")
        box(nm + "_bearing", (0.03, 0.14, 0.14), (-0.8, y, z), "metalDark", d, bevel=0.02)
    # variator second half (movable disc) + adjustment spindle
    cyl("variatorDisc2", 0.4, 0.03, (x - 0.1, 0.05, 1.3), "cream", d, axis="X", verts=48, r2=0.3)
    sweep("variatorSpindle", [(x - 0.12, 0.05, 1.3), (x - 0.2, 0.25, 1.9), (x - 0.2, 0.9, 2.1)], 0.012, "steel",
          d, verts=8)
    # belts
    belt("beltMain", x - 0.005, (-2.55, 2.5), 0.2, (-1.35, 2.05), 0.32, parent=d, w=0.022)
    belt("beltMain2", x - 0.035, (-2.55, 2.5), 0.2, (-1.35, 2.05), 0.32, parent=d, w=0.022)
    belt("beltDrum", x - 0.07, (-1.35, 2.05), 0.14, (0.05, 1.3), 0.3, parent=d, w=0.04)
    belt("beltFan", x - 0.07, (-0.45, 0.75), 0.2, (-1.35, 2.05), 0.14, parent=d, w=0.03)
    belt("beltWalker", x, (-3.05, 1.82), 0.3, (-1.35, 2.05), 0.32, parent=d, w=0.04)
    belt("beltSieve", x - 0.07, (-1.9, 0.95), 0.16, (-3.05, 1.82), 0.12, parent=d, w=0.03)
    # tensioner arms with springs
    for i, (y, z, y2, z2) in enumerate(((-2.2, 2.55, -2.3, 2.1), (-0.75, 1.9, -0.85, 1.5))):
        sweep("tensionArm%d" % i, [(x - 0.03, y2, z2), (x - 0.03, y, z)], 0.015, "metalDark", d, verts=8)
        pulley("tensionRoller%d" % i, 0.06, 0.05, (x - 0.02, y, z), "metalDark", d, spokes=0)
        coil = []
        for k in range(60):
            t = k / 59
            a = t * 2 * math.pi * 10
            coil.append((x - 0.03 + math.cos(a) * 0.018, y2 + (y2 - 0.3 - y2) * t * 0 - 0.05 - t * 0.3,
                         z2 - 0.05 + math.sin(a) * 0.018))
        sweep("tensionSpring%d" % i, coil, 0.004, "steel", d, verts=5)
    # chain drives to the elevator / feeder (sprockets + chains)
    for nm, y, z, r, t in (("sprElev", -0.7, 0.55, 0.1, 18), ("sprElevTop", -0.9, 3.1, 0.08, 14)):
        s = empty(nm, (x + 0.02, y, z), d)
        gear(nm + "_g", r, 0.02, t, (0, 0, 0), "metalDark", s)
        ANIM.setdefault("thresh_rot", []).append((nm, "X", 500))
    # belt guards (half-open, as on the real machine the side covers swing up)
    box("guardTop", (0.03, 2.4, 0.03), (x - 0.2, -2.1, 2.9), "red", d, bevel=0.005)
    sweep("guardFrame", [(x - 0.2, -3.4, 2.9), (x - 0.2, -3.4, 2.3), (-0.8, -3.4, 2.3)], 0.012, "red", d,
          verts=6)
    decal("dWarnBelt", (-0.797, -1.35, 2.3), (0.44, 0.11), REG["warning"], "decals", d, "-X")
    # grease nipples
    for i, (y, z) in enumerate(((-3.1, 2.44), (-1.35, 1.76), (0.05, 0.92), (-3.05, 1.55))):
        cyl("grease%d" % i, 0.008, 0.03, (-0.82, y, z), "yellow", d, axis="X", verts=6)


def build_right_side(p):
    r = empty("rightSide", (0, 0, 0), p)
    x = 0.86
    # grain elevator housing up into the tank + chain cover
    box("elevator", (0.16, 0.3, 2.55), (x, -0.62, 1.9), "red", r, bevel=0.01)
    box("elevatorHead", (0.2, 0.42, 0.3), (x - 0.05, -0.62, 3.2), "red", r, bevel=0.02)
    box("elevatorFoot", (0.22, 0.4, 0.25), (x, -0.62, 0.58), "red", r, bevel=0.02)
    rivets("elevRiv", (x + 0.085, -0.5, 0.8), (x + 0.085, -0.5, 3.0), 18, "red", r, normal="+X")
    box("returnsElevator", (0.12, 0.22, 1.6), (x, -1.02, 1.3), "red", r, bevel=0.01)
    # hydraulic tank + valve block + hoses
    cyl("hydTank", 0.14, 0.6, (1.0, 0.95, 1.55), "red", r, axis="Y", verts=24)
    cyl("hydTankCap", 0.04, 0.05, (1.0, 1.05, 1.7), "black", r, axis="Z")
    box("valveBlock", (0.18, 0.28, 0.16), (0.95, 0.35, 1.72), "metalDark", r, bevel=0.01)
    for i in range(4):
        cyl("valveSpool%d" % i, 0.012, 0.08, (0.95, 0.24 + i * 0.07, 1.84), "chrome", r, axis="Z", verts=8)
    # battery box with cables
    bb = empty("batteryBox", (1.0, 1.35, 1.72), r)
    box("batteryCase", (0.3, 0.42, 0.28), (0, 0, 0), "black", bb, bevel=0.01)
    box("batteryLid", (0.32, 0.44, 0.03), (0, 0, 0.155), "red", bb, bevel=0.01)
    cyl("batteryPos", 0.018, 0.03, (-0.08, 0.12, 0.19), "copper", bb, axis="Z", verts=8)
    cyl("batteryNeg", 0.018, 0.03, (-0.08, -0.12, 0.19), "steel", bb, axis="Z", verts=8)
    # toolbox + spare V-belts hanging + grease gun
    box("toolbox", (0.26, 0.5, 0.26), (1.0, -1.7, 2.0), "red", r, bevel=0.02)
    box("toolboxLid", (0.28, 0.52, 0.03), (1.0, -1.7, 2.14), "red", r, bevel=0.01)
    box("toolboxLatch", (0.03, 0.06, 0.04), (1.14, -1.7, 2.08), "chrome", r)
    for i in range(2):
        pts = [(0.93 + math.cos(a) * 0.01, -2.6 + math.sin(a) * 0.14 + i * 0.03, 2.05 - 0.2 - math.cos(a) * 0.2)
               for a in [2 * math.pi * k / 24 for k in range(24)]]
        sweep("spareBelt%d" % i, pts, 0.008, "rubberBelt", r, closed=True, verts=6)
    sweep("beltHook", [(0.88, -2.6, 2.1), (0.94, -2.6, 2.1), (0.94, -2.6, 2.05)], 0.008, "steel", r, verts=6)
    ggun = empty("greaseGun", (1.02, -1.0, 2.0), r)
    cyl("greaseGunBody", 0.035, 0.3, (0, 0, 0), "red", ggun, axis="Y")
    sweep("greaseGunHose", [(0, 0.15, 0), (0.02, 0.25, -0.05), (0.0, 0.3, -0.15)], 0.006, "rubber", ggun, verts=6)
    # hydraulic hoses: valves -> feeder cylinders / pipe cylinder / header coupling
    hose("hoseFeederL", (0.9, 0.3, 1.72), (-0.42, 0.42, 0.92), 0.35, 0.013, "hoseBlack", r)
    hose("hoseFeederR", (0.95, 0.32, 1.72), (0.42, 0.42, 0.92), 0.25, 0.013, "hoseBlack", r)
    hose("hoseReel1", (0.92, 0.45, 1.72), (0.62, 1.05, 1.05), 0.2, 0.011, "hoseBlack", r)
    hose("hoseReel2", (0.97, 0.45, 1.72), (0.66, 1.05, 1.02), 0.22, 0.011, "hoseBlack", r)
    hose("hosePipe", (0.9, 0.2, 1.72), (-1.1, 0.0, 2.8), 0.1, 0.012, "hoseBlack", r, da=(0, 0, 1),
         db=(-1, 0, 0))
    hose("hoseSuction", (1.0, 0.7, 1.45), (0.2, 0.1, R_F + 0.2), 0.15, 0.025, "hoseBlack", r)


def build_electrics(p):
    e = empty("electrics", (0, 0, 0), p)
    # battery -> starter (thick cables), battery -> fuse box (cab), fuse box -> lights, horn, rear loom
    hose("cableStarter", (0.92, 1.47, 1.9), (0.35, -2.65, 2.55), 0.25, 0.012, "wireRed", e)
    hose("cableGround", (0.92, 1.23, 1.9), (0.75, 1.0, 1.6), 0.08, 0.012, "wireBlack", e)
    box("fuseBox", (0.04, 0.22, 0.16), (0.745, 0.6, 2.62), "black", e, bevel=0.008)
    box("fuseBoxLid", (0.01, 0.2, 0.14), (0.768, 0.6, 2.62), "plasticBlack", e, bevel=0.003)
    hose("cableFuse", (0.92, 1.35, 1.9), (0.76, 0.55, 2.55), 0.1, 0.009, "wireRed", e)
    # front loom: under the platform to the front edge, then up the railing uprights to the lamps
    # (never through the cab: those wires showed as black lines across the windscreen)
    for sx in (-1, 1):
        up = [(0.8, 0.66, 2.12), (0.8, 1.5, 2.12), (sx * 0.77, 1.56, 2.12), (sx * 0.77, 1.62, 2.2)]
        sweep("wireHead%d" % sx, up + [(sx * 0.77, 1.62, 3.1), (sx * 0.85, 1.62, 3.18), (sx * 0.93, 1.6, 3.18)],
              0.005, "wireBlack", e, verts=6)
        sweep("wireTurn%d" % sx, [(p[0] + 0.012 * sx, p[1], p[2]) for p in up] +
              [(sx * 0.785, 1.62, 2.9), (sx * 1.0, 1.62, 2.93), (sx * 1.15, 1.62, 2.93)], 0.005, "wireBlack", e,
              verts=6)
    # rear loom along the right housing wall with clips
    loom = [(0.8, 0.55, 2.3), (0.81, -0.3, 2.25), (0.81, -1.5, 2.25), (0.81, -2.8, 2.25), (0.81, -4.0, 2.0),
            (0.75, -5.25, 1.62)]
    sweep("rearLoom", loom, 0.009, "wireBlack", e, verts=6)
    for i, pnt in enumerate(loom[1:-1]):
        box("loomClip%d" % i, (0.02, 0.03, 0.03), pnt, "metalDark", e)
    hose("wireTailL", (0.75, -5.25, 1.62), (-0.72, -5.28, 1.62), 0.05, 0.005, "wireBlack", e)
    # horn wires + alternator
    hose("wireHorn", (0.76, 0.6, 2.7), (0.42, 0.6, 3.95), 0.05, 0.004, "wireRed", e)
    hose("wireAlt", (0.3, -2.6, 2.87), (0.8, -2.2, 2.35), 0.1, 0.006, "wireRed", e)


def build_extras(p):
    x = empty("extras", (0, 0, 0), p)
    # shovel on the side (every Bizon has one)
    sh = empty("shovel", (-0.82, -3.7, 1.3), x)
    sweep("shovelHandle", [(0, 0.0, 0), (0, 0.9, 0.5)], 0.018, "wood", sh, verts=8)
    box("shovelBlade", (0.02, 0.24, 0.3), (0, -0.08, -0.12), "metalDark", sh, bevel=0.01, rot=(0.5, 0, 0))
    box("shovelHolder", (0.05, 0.05, 0.05), (0.02, 0.5, 0.28), "black", sh)
    # beacon placeholder on the cab roof (same spot as the beaconLight01 link node)
    bc = empty("rbeacon", BEACON_SPOT, None, props={"export": False})
    o = cyl("beaconBase_r", 0.08, 0.05, (0, 0, 0), "black", bc, axis="Z")
    o["export"] = False
    o = cyl("beaconDome_r", 0.07, 0.14, (0, 0, 0.09), "amberGlass", bc, axis="Z", r2=0.04)
    o["export"] = False



def feeder_point(t, s, z_off=0.0):
    """Point along the feeder axis in pivot-local space (y fwd, z up) at distance t, height offset s."""
    a = FEEDER_ANGLE
    return Vector((0, math.cos(a) * t + math.sin(a) * s, -math.sin(a) * t + math.cos(a) * s + z_off))


def build_feeder(base):
    rot = empty("attacherJointRot", tuple(PIVOT), base)
    f = empty("feeder", (0, 0, 0), rot)
    a = FEEDER_ANGLE
    L = FEEDER_LEN
    mid = feeder_point(L / 2, 0)
    box("feederBox", (1.18, L, 0.62), tuple(mid), "red", f, bevel=0.02, rot=(-a, 0, 0))
    for sx in (-1, 1):
        for i in range(3):
            c = feeder_point(0.3 + i * 0.55, 0.0)
            box("feederRib%d_%d" % (sx, i), (0.03, 0.05, 0.6), (sx * 0.605, c.y, c.z), "red", f, bevel=0.005,
                rot=(-a, 0, 0))
    # front flange (mouth) with header hooks
    m = feeder_point(L, 0)
    box("feederFlange", (1.3, 0.06, 0.74), tuple(m), "red", f, bevel=0.01, rot=(-a, 0, 0))
    for sx in (-1, 1):
        h = feeder_point(L - 0.02, 0.38)
        box("feederHook%d" % sx, (0.1, 0.12, 0.08), (sx * 0.45, h.y, h.z), "metalDark", f, bevel=0.01,
            rot=(-a, 0, 0))
    # feeder chain drive (top shaft, left sprocket + chain)
    top_front = feeder_point(L - 0.15, 0.2)
    top_back = feeder_point(0.15, 0.2)
    for nm, c in (("feederSprF", top_front), ("feederSprB", top_back)):
        s = empty(nm, (-0.63, c.y, c.z), f)
        gear(nm + "_g", 0.09, 0.02, 14, (0, 0, 0), "metalDark", s)
        ANIM.setdefault("thresh_rot", []).append((nm, "X", 400))
    chain = belt_like = K.belt_path((top_back.y, top_back.z), 0.09, (top_front.y, top_front.z), 0.09)
    sweep("feederChain", [Vector((-0.64, q.x, q.y)) for q in chain], 0, "metalDark", f, closed=True,
          profile=[(-0.008, -0.006), (0.008, -0.006), (0.008, 0.006), (-0.008, 0.006)], twist_up=(1, 0, 0))
    # attacher joint node at the mouth; tilted up by the lower rotation so the header sits level when lowered
    aj = empty("attacherJointCutter", tuple(m + Vector((0, 0.03, 0))), rot, rot=(math.radians(FEEDER_LOWER), 0, 0))
    ANIM["feeder"] = {"lowerRot": FEEDER_LOWER, "upperRot": -18, "mouth": list(m + PIVOT)}
    # hydraulic lift cylinders (chassis -> feeder underside)
    for sx, side in ((-1, "Left"), (1, "Right")):
        ref_local = feeder_point(1.05, -0.33)
        ref = empty("feederCylRef" + side, (sx * 0.42, ref_local.y, ref_local.z), rot)
        base_pt = Vector((sx * 0.42, 0.28, 0.82))
        target = PIVOT + Vector((sx * 0.42, ref_local.y, ref_local.z))
        cylinder_pair(base, "feederCyl" + side, base_pt, target, 0.045, 0.022)
    # rubber curtain + stone guard under the mouth
    c = feeder_point(L - 0.1, -0.35)
    box("feederSkid", (1.0, 0.25, 0.03), (0, c.y, c.z), "metalDark", f, bevel=0.005, rot=(-a, 0, 0))
    return rot


def cylinder_pair(parent, name, base_pt, target, r_barrel, r_rod, barrel=0.6, rod=0.62):
    """Hydraulic cylinder for a <movingPart>: node local +Y (GIANTS +Z) aims at the target; the punch
    child sits at the target and its rod reaches back into the barrel."""
    base_pt, target = Vector(base_pt), Vector(target)
    d = target - base_pt
    L = d.length
    q = d.normalized().to_track_quat("Y", "Z")
    c = empty(name, tuple(base_pt), parent)
    c.rotation_mode = "QUATERNION"
    c.rotation_quaternion = q
    blen = L * barrel
    cyl(name + "_barrel", r_barrel, blen, (0, blen / 2, 0), "red", c, axis="Y", verts=16)
    cyl(name + "_eye", r_barrel * 0.8, r_barrel * 1.6, (0, 0, 0), "metalDark", c, axis="X", verts=12)
    punch = empty(name + "Punch", (0, L, 0), c)
    cyl(name + "_rod", r_rod, L * rod, (0, -L * rod / 2, 0), "chrome", punch, axis="Y", verts=12)
    cyl(name + "_rodEye", r_rod * 1.6, r_rod * 3, (0, 0, 0), "metalDark", punch, axis="X", verts=10)
    ANIM.setdefault("cylinders", []).append(name)
    return c


def build_pipe(base, body):
    """Unloading auger: vertical tube on the left front of the tank, swinging horizontal pipe."""
    px, py, pz = -1.3, 0.12, 3.36
    sweep("pipeVertical", [(px, py, 2.25), (px, py, pz - 0.05)], 0.1, "red", body, verts=20)
    box("pipeVertBracket", (0.22, 0.12, 0.12), (px + 0.12, py, 2.6), "red", body, bevel=0.01)
    box("pipeVertBracket2", (0.2, 0.12, 0.12), (px + 0.1, py, 3.1), "red", body, bevel=0.01)
    cyl("pipeTurret", 0.14, 0.1, (px, py, pz - 0.02), "metalDark", body, axis="Z", verts=24)
    # rest cradle at the rear
    sweep("pipeCradle", [(-0.85, -3.3, 2.38), (-1.3, -3.3, 3.2), (-1.3, -3.3, 3.26)], 0.02, "red", body, verts=8)
    box("pipeCradleCup", (0.25, 0.08, 0.05), (-1.3, -3.3, 3.26), "rubber", body, bevel=0.01)
    pipe = empty("pipe", (px, py, pz), base)
    L = 3.5
    sweep("pipeTube", [(0, -0.05, 0.02), (0, -0.25, 0.05), (0, -L, 0.05)], 0.105, "red", pipe, verts=24)
    for i in range(4):
        y = -0.6 - i * 0.8
        tube("pipeBand%d" % i, 0.118, 0.1, 0.05, (0, y, 0.05), "red", pipe, axis="Y", verts=24)
    # spout pointing down + rubber sleeve
    sweep("pipeSpout", [(0, -L, 0.05), (0, -L - 0.12, 0.0), (0, -L - 0.15, -0.2)], 0.1, "red", pipe, verts=20)
    cyl("pipeSleeve", 0.105, 0.15, (0, -L - 0.15, -0.3), "rubber", pipe, axis="Z", verts=20)
    # auger visible in the spout, spins while unloading
    sa = empty("pipeAuger", (0, -L + 0.05, 0.05), pipe)
    for i in range(6):
        box("pipeAugerFlight%d" % i, (0.17, 0.012, 0.04), (0, i * 0.02, 0), "galv", sa, bevel=0, rot=(0, i * 1.0, 0))
    ANIM["pipeAuger"] = "pipeAuger"
    # pipe work light + wires
    pl = empty("pipeLamp", (0.12, -2.8, 0.2), pipe)
    cyl("pipeLampBody", 0.05, 0.08, (0, 0, 0), "black", pl, axis="Z")
    sweep("pipeLampWire", [(0.1, -0.2, 0.12), (0.11, -1.5, 0.15), (0.12, -2.8, 0.18)], 0.004, "wireBlack", pipe,
          verts=6)
    empty("dischargeNode", (0, -L - 0.15, -0.38), pipe)
    eff = empty("pipeEffectNode", (0, -L - 0.15, -0.38), pipe, rot=(math.radians(-90), 0, 0))
    pipe_effect_mesh(eff)
    helper_mesh("trailerTrigger", (3.2, 3.2, 3.6), (0, -L - 0.15, -1.8), pipe, "trigger")
    # swing cylinder: from the tank wall to an arm on the pipe
    empty("pipeCylRef", (0.0, -0.5, -0.05), pipe)
    box("pipeArm", (0.06, 0.1, 0.12), (0.0, -0.5, -0.05), "metalDark", pipe, bevel=0.01)
    box("pipeCylBracket", (0.08, 0.12, 0.12), (-1.17, -1.0, 3.3), "red", body, bevel=0.01)
    cylinder_pair(base, "pipeCyl", (-1.2, -1.0, 3.31), Vector((px, py - 0.5, pz - 0.05)), 0.035, 0.018,
                  barrel=0.95, rod=0.95)
    ANIM["pipe"] = {"node": "pipe", "unfoldZ": -90}
    return pipe


def pipe_effect_mesh(parent):
    """Tube 0..10 m along local +Y (GIANTS +Z) with the UV layout the PipeEffect shader bends."""
    import bmesh
    bm = bmesh.new()
    uv0 = bm.loops.layers.uv.new("uv0")
    uv1 = bm.loops.layers.uv.new("uv1")
    rings, seg = 60, 20
    grid = []
    for i in range(rings + 1):
        y = 10.0 * i / rings
        grid.append([bm.verts.new((math.cos(2 * math.pi * k / seg) * 0.136, y,
                                   math.sin(2 * math.pi * k / seg) * 0.105)) for k in range(seg)])
    for i in range(rings):
        for k in range(seg):
            kk = (k + 1) % seg
            f = bm.faces.new((grid[i][k], grid[i + 1][k], grid[i + 1][kk], grid[i][kk]))
            for loop, (ii, ki) in zip(f.loops, ((i, k), (i + 1, k), (i + 1, k + 1), (i, k + 1))):
                val = (ii / rings, ki / seg - 0.5)
                loop[uv0].uv = val
                loop[uv1].uv = val
    o = K.mesh_from_bm("pipeEffect", bm, "inv", parent, smooth_angle=80)
    o["keep_uv"] = True
    o["kind"] = "effect"
    o["nomerge"] = True
    o.hide_render = True
    return o


def build_functional(base):
    f = empty("functional", (0, 0, 0), base)
    zf = 2.2
    empty("exitPoint", (-1.7, 1.3, 0.1), f)
    # character in the seat, IK targets on wheel and pedals
    empty("playerSkin", (0.0, 0.62, zf + 0.52), f)
    empty("playerRightFootTarget", (0.13, 1.08, zf + 0.1), f, props={"g_rot": "0 -10 0"})
    empty("playerLeftFootTarget", (-0.14, 1.08, zf + 0.1), f, props={"g_rot": "0 10 0"})
    empty("playerRightHandTarget", (0.17, 0.94, zf + 0.9), f)
    empty("playerLeftHandTarget", (-0.17, 0.94, zf + 0.9), f)
    cams = empty("cameras", (0, 0, 0), f)
    tgt = empty("outdoorCameraTarget", (0, -1.4, 2.4), cams, props={"g_rot": "-20 180 0"})
    empty("outdoorCamera1", (0, 0, 0), tgt, props={"kind": "camera", "g_trans": "0 0 12", "fov": 54.4})
    empty("indoorCamera1", (0.0, 0.62, zf + 1.2), cams, props={"kind": "camera", "g_rot": "-15 180 0", "fov": 75,
                                                               "near": 0.1})
    empty("cameraRaycastNode1", (0, 1.5, 3.2), cams)
    empty("cameraRaycastNode2", (0, -1.0, 3.6), cams)
    empty("cameraRaycastNode3", (0, -4.6, 2.2), cams)
    # FS shared light link nodes (the game loads the lamp models)
    sl = empty("sharedLights", (0, 0, 0), f)
    for nm, loc in LAMP_SPOTS.items():
        empty(nm, loc, sl, props={"g_rot": "10 0 0"})
    empty("workLightRearL", (-0.7, -4.05, 3.38), sl, props={"g_rot": "15 180 0"})
    empty("workLightRearR", (0.7, -4.05, 3.38), sl, props={"g_rot": "15 180 0"})
    empty("beaconLight01", BEACON_SPOT, sl)
    # real lights (spot lights shine along local -Z in GIANTS)
    rl = empty("realLights", (0, 0, 0), f)
    L = lambda n, loc, rot, col, rng, cone, extra=None: empty(n, loc, rl, props=dict(
        kind="light", g_rot=rot, color=col, range=rng, cone=cone, **(extra or {})))
    L("frontLightLow", (0, 1.7, 3.2), "-15 180 0", "0.85 0.85 0.8", 20, 80)
    L("frontLightHigh", (-0.95, 1.72, 3.2), "-12 180 0", "0.85 0.85 0.8", 25, 70)
    L("frontLightHigh2", (0.95, 1.72, 3.2), "-12 180 0", "0.85 0.85 0.8", 25, 70)
    L("highBeamLow", (0, 1.7, 3.2), "-8 180 0", "0.85 0.85 0.8", 30, 60)
    L("highBeamHigh", (0, 1.72, 3.2), "-6 180 0", "0.85 0.85 0.8", 40, 50)
    L("workLightFrontLow", (0, 1.7, 3.95), "-25 180 0", "0.85 0.85 1", 22, 120)
    L("workLightFrontHigh", (0, 1.72, 3.95), "-30 180 0", "0.85 0.85 1", 28, 100)
    L("workLightBackLow", (0, -4.1, 3.4), "-25 0 0", "0.9 0.9 1", 15, 120)
    L("workLightBackHigh", (0, -4.1, 3.4), "-30 0 0", "0.9 0.9 1", 18, 110)
    L("backLightsHigh", (0, -5.35, 1.6), "-10 0 0", "0.5 0 0", 3, 130)
    L("turnLightLeftFront", (-1.18, 1.7, 2.93), "0 180 0", "0.31 0.14 0", 4, 120)
    L("turnLightRightFront", (1.18, 1.7, 2.93), "0 180 0", "0.31 0.14 0", 4, 120)
    L("turnLightLeftBack", (-0.72, -5.35, 1.47), "0 0 0", "0.31 0.14 0", 3, 120)
    L("turnLightRightBack", (0.72, -5.35, 1.47), "0 0 0", "0.31 0.14 0", 3, 120)
    L("interiorLight", (0, 0.9, 3.75), "-90 0 0", "0.6 0.55 0.45", 2, 140)
    L("pipeLightHigh", (-1.3, -0.4, 3.6), "-60 -90 0", "0.9 0.9 1", 12, 100)
    # work areas: straw swath behind the machine, chopper wider spread
    wa = empty("workAreas", (0, 0, 0), f)
    empty("workAreaStrawStart", (0.5, -5.4, 0), wa)
    empty("workAreaStrawWidth", (-0.5, -5.4, 0), wa)
    empty("workAreaStrawHeight", (0.5, -6.3, 0), wa)
    empty("workAreaChopperStart", (0, -5.4, 0), wa)
    empty("workAreaChopperWidth", (2.1, -9.0, 0), wa)
    empty("workAreaChopperHeight", (-2.1, -9.0, 0), wa)
    # fill volume + fill helpers
    tank = empty("tankNodes", (0, 0, 0), f)
    fv = helper_mesh("fillVolume", (2.1, 2.45, 0.95), (0, -0.96, 2.95), tank, "fillvol")
    helper_mesh("exactFillRootNode", (1.9, 2.2, 0.5), (0, -0.96, 3.1), tank, "exactfill")
    helper_mesh("exactFillRootNodeFuel", (0.5, 0.45, 0.5), (0.5, -4.0, 2.7), tank, "exactfill")
    empty("unloadInfo", (-1.0, 0.1, 2.5), tank)
    empty("loadInfo", (0.35, -0.4, 3.2), tank)
    empty("exhaustParticle", (-0.45, -3.25, 4.1), f, props={"g_rot": "-90 0 0"})
    empty("aiCollisionNode", (0, 2.5, 1.5), f)
    empty("strawDropNode", (0, -5.35, 1.5), f)


def build_collisions(root):
    base = root.children[0] if root.children else root
    c = empty("collisions", (0, 0, 0), bpy.data.objects["bizon_root"])
    helper_mesh("colTank", (2.3, 2.6, 1.1), (0, -0.96, 2.92), c, "col")
    helper_mesh("colCab", (1.5, 1.3, 1.75), (0, 0.9, 3.05), c, "col")
    helper_mesh("colEngine", (1.7, 1.7, 1.0), (0, -3.1, 2.85), c, "col")
    helper_mesh("colPlatform", (2.4, 1.5, 0.3), (0, 0.85, 2.05), c, "col")
    helper_mesh("colHood", (1.6, 1.3, 0.9), (0, -4.7, 1.9), c, "col")
    helper_mesh("colFrontAxle", (2.0, 0.4, 0.5), (0, 0, R_F + 0.1), c, "col")


# =============================================================== HEADER

HW = 4.2   # cutting width


def build_header():
    """Grain header; origin = input attacher joint at the feeder mouth. Header floor sits ~0.5 m below."""
    root = helper_mesh("bizonHeader_main_component1", (4.4, 1.5, 0.5), (0, 0.85, -0.21), None, "col_root")
    base = empty("header_root", (0, 0, 0), root)
    v = empty("hvis", (0, 0, 0), base)
    half = HW / 2 + 0.12
    # back wall with feeder opening frame, floor, top beam
    box("hBackWallL", (half - 0.62, 0.04, 0.9), (-(half + 0.62) / 2, 0, -0.1), "red", v, bevel=0.01)
    box("hBackWallR", (half - 0.62, 0.04, 0.9), ((half + 0.62) / 2, 0, -0.1), "red", v, bevel=0.01)
    box("hBackWallTop", (1.24, 0.04, 0.12), (0, 0, 0.3), "red", v, bevel=0.01)
    box("hMouthFrame", (1.34, 0.08, 0.78), (0, -0.03, -0.12), "metalDark", v, bevel=0.01)
    box("hTopBeam", (2 * half, 0.18, 0.16), (0, 0.02, 0.42), "red", v, bevel=0.02)
    prof = [(0.0, -0.55), (1.55, -0.55), (1.62, -0.5), (0.3, -0.5), (0.0, -0.3)]
    poly_prism("hFloor", [(y, z) for y, z in prof], 2 * half, "galv", v, plane="YZ", offset=-half)
    box("hFloorUnder", (2 * half, 1.6, 0.03), (0, 0.8, -0.58), "red", v, bevel=0.005)
    # side panels with crop dividers
    for sx in (-1, 1):
        side = [(-0.05, 0.45), (0.6, 0.45), (1.25, 0.1), (2.05, -0.45), (1.6, -0.6), (-0.05, -0.6)]
        poly_prism("hSide%d" % sx, side, 0.03, "red", v, plane="YZ", offset=sx * half - (0.03 if sx > 0 else 0))
        decal("dHStripe%d" % sx, (sx * (half + 0.018), 0.8, -0.3), (0.9, 0.11), REG["stripes"], "decals", v,
              "+X" if sx > 0 else "-X")
        # skid shoes
        box("hSkid%d" % sx, (0.1, 1.0, 0.04), (sx * (half - 0.25), 0.9, -0.62), "metalDark", v, bevel=0.01)
    decal("dHBizon", (0.0, 0.12, 0.42), (0.9, 0.225), REG["bizon"], "decals", v, "+Y")
    # cutter bar: guards + knife (animated)
    box("hCutterBar", (2 * half - 0.1, 0.08, 0.05), (0, 1.58, -0.52), "metalDark", v, bevel=0.005)
    for i in range(int(HW / 0.076)):
        x = -HW / 2 + 0.038 + i * 0.076
        poly_prism("hGuard%d" % i, [(1.6, 0.0), (1.8, 0.012), (1.6, 0.03)], 0.02, "metalDark", v, plane="YZ",
                   offset=x - 0.01).location = (0, 0, -0.545)
    knife = empty("knife", (0, 0, 0), base)
    tri = []
    for i in range(int(HW / 0.076)):
        x = -HW / 2 + i * 0.076
        tri.append((x, 1.62))
        tri.append((x + 0.038, 1.7))
    tri.append((HW / 2, 1.62))
    tri += [(HW / 2, 1.6), (-HW / 2, 1.6)]
    kn = poly_prism("knifeSections", tri, 0.006, "steel", knife, plane="XY", offset=-0.525)
    ANIM["knife"] = "knife"
    # auger with helical flights (left & right handed towards the middle) + finger drum
    aug = empty("auger", (0, 0.55, -0.28), base)
    cyl("augerTube", 0.17, 2 * half - 0.1, (0, 0, 0), "red", aug, axis="X", verts=28)
    for sgn in (-1, 1):
        pts = []
        for k in range(160):
            t = k / 159
            xx = sgn * (0.62 + t * (half - 0.72))
            a = sgn * t * 2 * math.pi * 5
            pts.append((xx, math.cos(a) * 0.23, math.sin(a) * 0.23))
        sweep("augerFlight%d" % sgn, pts, 0, "red", aug, profile=[(-0.05, -0.004), (0.05, -0.004), (0.05, 0.004),
                                                                  (-0.05, 0.004)], twist_up=(1, 0, 0))
    for i in range(8):
        a = i * math.pi / 4
        cyl("augerFinger%d" % i, 0.008, 0.2, (-0.3 + (i % 4) * 0.2, math.cos(a) * 0.2, math.sin(a) * 0.2),
            "steel", aug, axis="Z", rot=(a + math.pi / 2, 0, 0), verts=6)
    # reel on arms (reel height cylinders)
    for sx in (-1, 1):
        sweep("hReelArm%d" % sx, [(sx * (half - 0.05), -0.05, 0.42), (sx * (half - 0.05), 1.3, 0.7)], 0,
              "red", v, profile=[(-0.03, -0.05), (0.03, -0.05), (0.03, 0.05), (-0.03, 0.05)])
        sweep("hReelCyl%d" % sx, [(sx * (half + 0.04), 0.0, 0.0), (sx * (half + 0.04), 0.9, 0.55)], 0.03, "metalDark",
              v, verts=10)
        sweep("hReelCylRod%d" % sx, [(sx * (half + 0.04), 0.9, 0.55), (sx * (half + 0.04), 1.0, 0.62)], 0.015,
              "chrome", v, verts=8)
        hose("hReelHose%d" % sx, (sx * (half + 0.04), 0.05, 0.02), (sx * 0.6, -0.05, 0.1), 0.1, 0.01,
             "hoseBlack", v)
    reel = empty("reel", (0, 1.3, 0.7), base)
    cyl("reelShaft", 0.04, 2 * half - 0.05, (0, 0, 0), "metalDark", reel, axis="X", verts=12)
    nb = 5
    for i in range(nb):
        a = 2 * math.pi * i / nb
        c = (math.cos(a) * 0.55, math.sin(a) * 0.55)
        cyl("reelBat%d" % i, 0.022, 2 * half - 0.2, (0, c[0], c[1]), "galv", reel, axis="X", verts=12)
        for j in range(int((2 * half - 0.3) / 0.1)):
            x = -half + 0.2 + j * 0.1
            tine = [(x, c[0], c[1]), (x, c[0] * 0.98, c[1] - 0.03), (x + 0.01, c[0] * 0.9, c[1] - 0.2),
                    (x + 0.01, c[0] * 0.84, c[1] - 0.26)]
            sweep("reelTine%d_%d" % (i, j), tine, 0.0035, "plasticBlack" if j % 2 else "steel", reel, verts=5)
        for sx in (-1, 0, 1):
            sweep("reelSpoke%d_%d" % (i, sx), [(sx * (half - 0.25), 0, 0), (sx * (half - 0.25), c[0], c[1])], 0.018,
                  "red", reel, verts=8)
    for sx in (-1, 0, 1):
        tube("reelSpider%d" % sx, 0.1, 0.04, 0.03, (sx * (half - 0.25), 0, 0), "red", reel, verts=16)
    ANIM["reel"] = "reel"
    # left drive: input shaft + chain to auger + belt to reel
    dx = -half - 0.07
    for nm, y, z, r in (("hDriveIn", 0.05, -0.25, 0.12), ("hDriveAuger", 0.55, -0.28, 0.16),
                        ("hDriveReel", 1.3, 0.7, 0.2)):
        pulley(nm, r, 0.04, (dx, y, z), "cream" if nm == "hDriveReel" else "red", base, spokes=5)
        ANIM.setdefault("header_rot", []).append((nm, "X", {"hDriveIn": 700, "hDriveAuger": 420,
                                                           "hDriveReel": 220}[nm]))
    belt("hBeltAuger", dx - 0.01, (0.05, -0.25), 0.12, (0.55, -0.28), 0.16, parent=v, w=0.03)
    belt("hBeltReel", dx - 0.01, (0.55, -0.28), 0.1, (1.3, 0.7), 0.2, parent=v, w=0.03)
    box("hDriveGuard", (0.03, 1.3, 0.25), (dx - 0.06, 0.6, -0.1), "red", v, bevel=0.01)
    # functional nodes
    f = empty("hfunctional", (0, 0, 0), base)
    empty("attacherJoint", (0, 0, 0), f)
    for i, x in enumerate((-HW / 2 + 0.2, 0.0, HW / 2 - 0.2)):
        empty("heightNode%02d" % (i + 1), (x, 1.5, -0.6), f)
    empty("groundReferenceNode", (0, 1.5, -0.62), f)
    empty("workAreaStart", (-HW / 2, 1.7, -0.5), f)
    empty("workAreaWidth", (HW / 2, 1.7, -0.5), f)
    empty("workAreaHeight", (-HW / 2, 0.7, -0.5), f)
    empty("aiMarkerLeft", (-HW / 2, 1.7, -0.5), f)
    empty("aiMarkerRight", (HW / 2, 1.7, -0.5), f)
    empty("aiMarkerBack", (-HW / 2, 0.2, -0.5), f)
    hc = empty("hcollisions", (0, 0, 0), base)
    helper_mesh("colHReel", (2 * half, 1.2, 0.6), (0, 1.1, 0.7), hc, "col")
    return root


# =============================================================== RENDER SCENE


def attach_header_for_render(header_root, feeder_rot_deg=-4):
    """Place the header where it sits when attached (feeder slightly raised)."""
    rot = bpy.data.objects["attacherJointRot"]
    rot.rotation_euler = (math.radians(-feeder_rot_deg), 0, 0)  # blender +X tilt = raise
    bpy.context.view_layer.update()
    aj = bpy.data.objects["attacherJointCutter"]
    hj = bpy.data.objects["attacherJoint"]
    header_root.matrix_world = aj.matrix_world @ (hj.matrix_world.inverted() @ header_root.matrix_world)
    bpy.context.view_layer.update()


def setup_render_scene(res=(1920, 1080)):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 96
    sc.cycles.use_denoising = True
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.film_transparent = False
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Punchy"
    sc.view_settings.exposure = -0.55
    D.field_scene()
    D.apply_render_look()
    # grain heap in the tank (render only, seen through the top grid)
    import bmesh
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=24, y_segments=30, size=1.0)
    for v in bm.verts:
        x, y = v.co.x * 1.1, v.co.y * 1.25
        v.co = Vector((x, y - 0.97, 3.28 + 0.12 * math.cos(x * 1.4) * math.cos(y * 1.2)
                       + 0.02 * math.sin(x * 23 + y * 17)))
    heap = K.mesh_from_bm("grainHeap", bm, "grain", None, smooth_angle=80)
    heap["export"] = False
    return sc


def add_camera(name, loc, target, lens=40):
    cam = bpy.data.cameras.new(name)
    cam.lens = lens
    o = bpy.data.objects.new(name, cam)
    bpy.context.scene.collection.objects.link(o)
    o.location = loc
    d = Vector(target) - Vector(loc)
    o.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    o["export"] = False
    return o
