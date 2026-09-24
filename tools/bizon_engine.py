"""Detailed SW-400 style 6-cylinder inline diesel for the open Bizon engine bay, plus cab wiring/detail
helpers. Engine local frame: +Y = front of the engine (towards the cab), +X = right, origin = block centre."""
import math

import bmesh
from mathutils import Vector

import blender_kit as K
from blender_kit import box, cyl, empty, hose, poly_prism, pulley, sweep, tube

PITCH = 0.155
CYL_Y = [(i - 2.5) * PITCH for i in range(6)]


def ball(name, r, loc, mat, parent, squash=1.0, segs=18):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=max(6, segs // 2), radius=r)
    if squash != 1.0:
        bmesh.ops.scale(bm, vec=Vector((1, 1, squash)), verts=bm.verts)
    return K.mesh_from_bm(name, bm, mat, parent, loc, smooth_angle=85)


def hexbolt(name, loc, parent, axis="Z", r=0.009, h=0.012, mat="metalDark"):
    return cyl(name, r, h, loc, mat, parent, axis=axis, verts=6, smooth=0)


def helix(name, a, b, r_coil, turns, r_wire, mat, parent, n_per_turn=10):
    """Coiled cable (CB mic lead) from a to b."""
    a, b = Vector(a), Vector(b)
    d = b - a
    t = d.normalized()
    side = t.cross(Vector((0, 0, 1)) if abs(t.z) < 0.9 else Vector((1, 0, 0))).normalized()
    up = side.cross(t).normalized()
    n = int(turns * n_per_turn)
    pts = [a + d * (i / n) + (side * math.cos(i / n_per_turn * 2 * math.pi) +
                              up * math.sin(i / n_per_turn * 2 * math.pi)) * r_coil for i in range(n + 1)]
    return sweep(name, pts, r_wire, mat, parent, verts=6)


def build_sw400(blk, anim):
    """Everything hangs under `blk` (the engineBlock empty that the engine shaker moves)."""
    # ---- crankcase: cast cross-section with flared skirt, scalloped water jackets per cylinder
    prof = [(-0.2, -0.2), (0.2, -0.2), (0.225, -0.08), (0.205, 0.0), (0.2, 0.125), (-0.2, 0.125), (-0.205, 0.0),
            (-0.225, -0.08)]
    poly_prism("crankcase", prof, 0.94, "engineGrey", blk, plane="XZ", offset=-0.47, bevel=0.012)
    for sx in (-1, 1):
        for i, y in enumerate(CYL_Y):
            cyl("jacket%d_%d" % (sx, i), 0.066, 0.17, (sx * 0.165, y, 0.035), "engineGrey", blk, axis="Z", verts=20,
                bevel=0.008)
        for i in range(7):
            y = -0.43 + i * (0.86 / 6)
            box("skirtRib%d_%d" % (sx, i), (0.03, 0.018, 0.13), (sx * 0.215, y, -0.13), "engineGrey", blk,
                bevel=0.006)
        for i, y in enumerate((-0.31, 0.0, 0.31)):
            cyl("corePlug%d_%d" % (sx, i), 0.021, 0.012, (sx * 0.232, y, 0.03), "steel", blk, axis="X", verts=16)
    box("headGasket", (0.4, 0.94, 0.008), (0, 0, 0.129), "metalDark", blk, bevel=0)
    # ---- six individual heads + rocker covers (SW-680 family look), head studs, acorn nuts
    for i, y in enumerate(CYL_Y):
        box("head%d" % i, (0.38, 0.148, 0.12), (0, y, 0.192), "engineGrey", blk, bevel=0.012, segs=3)
        for sx in (-1, 1):
            for sy in (-1, 1):
                hexbolt("headNut%d_%d_%d" % (i, sx, sy), (sx * 0.165, y + sy * 0.055, 0.258), blk)
        box("rockerCover%d" % i, (0.27, 0.128, 0.065), (0.0, y, 0.286), "engineGrey", blk, bevel=0.028, segs=4)
        cyl("rockerNut%d" % i, 0.014, 0.022, (0.0, y, 0.326), "metalDark", blk, axis="Z", verts=12)
        inj = empty("injector%d" % i, (0.15, y, 0.255), blk, rot=(0, math.radians(28), 0))
        cyl("injBody%d" % i, 0.014, 0.1, (0, 0, 0.02), "steel", inj, axis="Z", verts=12)
        box("injClamp%d" % i, (0.05, 0.028, 0.012), (-0.01, 0, -0.012), "metalDark", inj, bevel=0.003)
        cyl("injCap%d" % i, 0.011, 0.02, (0, 0, 0.078), "metalDark", inj, axis="Z", verts=6, smooth=0)
        cyl("exhBoss%d" % i, 0.035, 0.04, (-0.2, y, 0.19), "engineGrey", blk, axis="X", verts=16)
    cyl("oilFiller", 0.024, 0.05, (0.0, CYL_Y[1], 0.345), "yellow", blk, axis="Z", verts=16)
    ball("oilFillerCap", 0.026, (0.0, CYL_Y[1], 0.372), "yellow", blk, squash=0.5)
    leak = [Vector((0.187, y, 0.335)) for y in CYL_Y]
    sweep("leakOff", [leak[0] + Vector((0, -0.08, -0.02))] + leak + [leak[-1] + Vector((0.04, 0.08, -0.08))],
          0.0035, "hoseBlack", blk, verts=6)
    # ---- injection pump (right, low) with 6 delivery valves, governor and throttle linkage
    pp = empty("injPumpAsm", (0.3, 0.02, -0.06), blk)
    box("injPumpBody", (0.12, 0.46, 0.16), (0, 0, 0), "engineGrey", pp, bevel=0.02, segs=3)
    box("injPumpFlange", (0.05, 0.5, 0.05), (-0.07, 0, -0.06), "engineGrey", pp, bevel=0.01)
    cyl("injGovernor", 0.075, 0.15, (0, -0.3, -0.005), "engineGrey", pp, axis="Y", verts=24, bevel=0.01)
    cyl("injDrive", 0.05, 0.08, (0, 0.27, -0.01), "metalDark", pp, axis="Y", verts=20)
    box("liftPump", (0.05, 0.08, 0.07), (0.075, 0.04, -0.02), "engineGrey", pp, bevel=0.01)
    cyl("primerKnob", 0.012, 0.04, (0.11, 0.04, 0.0), "black", pp, axis="X", verts=10)
    lever = empty("throttleArm", (0.07, -0.3, 0.05), pp)
    box("throttleArmMesh", (0.012, 0.012, 0.09), (0, 0, 0.04), "steel", lever, bevel=0.002, rot=(0.4, 0, 0))
    sweep("throttleRod", [(0.37, -0.28, 0.03), (0.4, -0.1, 0.12), (0.42, 0.45, 0.2)], 0.004, "steel", blk, verts=6)
    valves = []
    for i, y in enumerate(CYL_Y):
        vy = y * 0.95 + 0.02
        cyl("deliveryValve%d" % i, 0.016, 0.05, (0.3, vy, 0.045), "steel", blk, axis="Z", verts=12)
        hexbolt("deliveryNut%d" % i, (0.3, vy, 0.074), blk, r=0.012, h=0.015, mat="steel")
        valves.append(Vector((0.3, vy, 0.082)))
    # injection pipes: pump outlet -> up the block side -> over the head to the injector top
    s28, c28 = math.sin(math.radians(28)), math.cos(math.radians(28))
    for i, (v, y) in enumerate(zip(valves, CYL_Y)):
        top = Vector((0.15 + s28 * 0.085, y, 0.255 + c28 * 0.085))
        mid = Vector((0.29, y, 0.2))
        pts = K.bezier_pts(v, v + Vector((0, 0, 0.05)), mid + Vector((0, 0, -0.04)), mid, 6)[:-1] + \
            K.bezier_pts(mid, mid + Vector((0, 0, 0.06)), top + Vector((0.05, 0, 0.03)), top, 6)
        sweep("injPipe%d" % i, pts, 0.0042, "steel", blk, verts=6)
    for z in (0.16, 0.24):
        box("pipeClamp%.2f" % z, (0.018, 0.84, 0.014), (0.28, 0.0, z), "metalDark", blk, bevel=0.003)
    for j, y in enumerate((0.3, 0.4)):
        cyl("fuelFilter%d" % j, 0.042, 0.15, (0.33, y, 0.06), "cream", blk, axis="Z", verts=24, bevel=0.006)
        cyl("fuelFilterHead%d" % j, 0.047, 0.03, (0.33, y, 0.15), "engineGrey", blk, axis="Z", verts=24)
        hexbolt("fuelFilterBolt%d" % j, (0.33, y, 0.172), blk, r=0.01)
    box("fuelFilterBracket", (0.02, 0.2, 0.06), (0.275, 0.35, 0.15), "metalDark", blk, bevel=0.004)
    hose("fuelHoseA", (0.33, 0.3, 0.17), (0.375, 0.06, -0.05), 0.05, 0.006, "hoseBlack", blk)
    hose("fuelHoseB", (0.33, 0.4, 0.17), (0.34, 0.6, -0.1), 0.06, 0.006, "hoseBlack", blk)
    # ---- intake manifold (right, high) with runners and inlet elbow
    sweep("intakeManifold", [(0.235, -0.42, 0.2), (0.235, 0.42, 0.2)], 0.036, "engineGrey", blk, verts=16)
    for i, y in enumerate(CYL_Y):
        sweep("intakeRunner%d" % i, [(0.235, y, 0.2), (0.19, y, 0.195)], 0.03, "engineGrey", blk, verts=14)
    for sy in (-1, 1):
        cyl("intakeCap%d" % sy, 0.04, 0.02, (0.235, sy * 0.43, 0.2), "engineGrey", blk, axis="Y", verts=16)
    sweep("intakeInlet", [(0.235, 0.0, 0.22), (0.25, 0.0, 0.3), (0.27, 0.0, 0.33)], 0.038, "engineGrey", blk,
          verts=16)
    # ---- exhaust manifold (left): cast runners into a collector, outlet to the exhaust pipe
    for i, y in enumerate(CYL_Y):
        sweep("exhRunner%d" % i, [(-0.2, y, 0.19), (-0.25, y, 0.19), (-0.285, y * 0.85, 0.2)], 0.028, "rust", blk,
              verts=14)
        box("exhFlange%d" % i, (0.012, 0.07, 0.07), (-0.222, y, 0.19), "rust", blk, bevel=0.006)
    sweep("exhCollector", [(-0.29, -0.36, 0.2), (-0.29, 0.36, 0.2)], 0.044, "rust", blk, verts=18)
    sweep("exhOutlet", [(-0.29, 0.0, 0.22), (-0.33, 0.0, 0.25), (-0.4, 0.0, 0.25)], 0.05, "rust", blk, verts=16)
    # ---- oil pan with flange bolts and drain plug, oil filter, dipstick
    box("oilPan", (0.36, 0.86, 0.14), (0, -0.02, -0.27), "engineGrey", blk, bevel=0.035, segs=4)
    box("oilPanFlange", (0.43, 0.92, 0.016), (0, -0.02, -0.2), "engineGrey", blk, bevel=0.005)
    for sx in (-1, 1):
        for k in range(8):
            hexbolt("panBolt%d_%d" % (sx, k), (sx * 0.2, -0.44 + k * 0.12, -0.21), blk, r=0.007, h=0.01)
    hexbolt("drainPlug", (0.0, -0.25, -0.345), blk, r=0.014, h=0.014)
    box("oilFilterBoss", (0.05, 0.1, 0.08), (-0.225, 0.14, -0.08), "engineGrey", blk, bevel=0.01)
    cyl("oilFilter", 0.055, 0.17, (-0.285, 0.14, -0.1), "redClean", blk, axis="Z", verts=28, bevel=0.01)
    for k in range(3):
        tube("oilFilterRib%d" % k, 0.058, 0.054, 0.006, (-0.285, 0.14, -0.14 + k * 0.04), "redClean", blk,
             axis="Z", verts=28)
    sweep("dipstickTube", [(-0.215, -0.12, -0.14), (-0.24, -0.12, 0.0), (-0.25, -0.12, 0.3)], 0.006, "steel", blk,
          verts=8)
    tube("dipstickRing", 0.02, 0.013, 0.006, (-0.25, -0.12, 0.33), "yellow", blk, axis="X", verts=16)
    cyl("oilSender", 0.012, 0.03, (0.22, 0.25, -0.03), "steel", blk, axis="X", verts=6, smooth=0)
    # ---- flywheel housing (rear) with bolt ring, timing cover (front), engine feet on rubber mounts
    cyl("flywheelHousing", 0.28, 0.12, (0, -0.53, -0.04), "engineGrey", blk, axis="Y", r2=0.23, verts=40, bevel=0.01)
    for k in range(10):
        a = k * 2 * math.pi / 10
        hexbolt("bellBolt%d" % k, (math.cos(a) * 0.255, -0.47, -0.04 + math.sin(a) * 0.255), blk, axis="Y",
                r=0.008, h=0.012)
    box("timingCover", (0.4, 0.05, 0.34), (0, 0.49, -0.03), "engineGrey", blk, bevel=0.03, segs=3)
    for sx in (-1, 1):
        for sy in (-1, 1):
            y = sy * 0.38
            box("engineFoot%d_%d" % (sx, sy), (0.11, 0.07, 0.05), (sx * 0.26, y, -0.2), "engineGrey", blk,
                bevel=0.01)
            cyl("engineMountRubber%d_%d" % (sx, sy), 0.035, 0.06, (sx * 0.29, y, -0.25), "rubber", blk, axis="Z",
                verts=16)
            box("engineMountBracket%d_%d" % (sx, sy), (0.1, 0.09, 0.012), (sx * 0.29, y, -0.285), "metalDark", blk,
                bevel=0.003)
    # ---- water pump, thermostat housing, alternator with bracket, starter with solenoid
    cyl("waterPump", 0.07, 0.07, (0, 0.54, 0.14), "engineGrey", blk, axis="Y", verts=24, bevel=0.01)
    box("thermostatHousing", (0.07, 0.07, 0.06), (-0.2, 0.47, 0.25), "engineGrey", blk, bevel=0.012)
    sweep("thermostatNeck", [(-0.2, 0.47, 0.27), (-0.2, 0.52, 0.29), (-0.2, 0.56, 0.3)], 0.026, "engineGrey", blk,
          verts=14)
    cyl("tempSender", 0.011, 0.03, (-0.16, 0.47, 0.26), "steel", blk, axis="X", verts=6, smooth=0)
    pulley("alternatorPulley", 0.05, 0.03, (0.2, 0.6, 0.12), "metalDark", blk, spokes=0, axis="Y")
    cyl("alternator", 0.085, 0.15, (0.2, 0.5, 0.12), "steel", blk, axis="Y", verts=24, bevel=0.008)
    for k in range(5):
        tube("altRib%d" % k, 0.089, 0.083, 0.008, (0.2, 0.44 + k * 0.03, 0.12), "steel", blk, axis="Y", verts=24)
    sweep("altStrap", [(0.12, 0.56, 0.02), (0.19, 0.56, 0.0), (0.26, 0.56, 0.05)], 0.008, "metalDark", blk,
          verts=6)
    box("altBracket", (0.12, 0.02, 0.05), (0.14, 0.44, 0.07), "metalDark", blk, bevel=0.004)
    pulley("crankPulley", 0.1, 0.04, (0, 0.6, -0.15), "metalDark", blk, spokes=4, axis="Y")
    pulley("fanPulley", 0.08, 0.04, (0, 0.6, 0.2), "metalDark", blk, spokes=4, axis="Y")
    anim.setdefault("motor_rot", []).extend([("alternatorPulley", "Y", 1500), ("crankPulley", "Y", 700),
                                             ("fanPulley", "Y", 900)])
    loop = [(0, -0.26), (0.28, 0.12), (0.0, 0.29), (-0.09, 0.2), (-0.1, -0.15)]
    sweep("fanBelt", [Vector((x, 0.6, z)) for x, z in loop], 0, "rubberBelt", blk, closed=True,
          profile=[(-0.012, -0.006), (0.012, -0.006), (0.012, 0.006), (-0.012, 0.006)], twist_up=(0, 1, 0))
    cyl("starter", 0.062, 0.25, (0.27, -0.36, -0.13), "black", blk, axis="Y", verts=24, bevel=0.008)
    cyl("starterNose", 0.045, 0.06, (0.27, -0.5, -0.13), "engineGrey", blk, axis="Y", verts=20)
    cyl("solenoid", 0.034, 0.13, (0.27, -0.36, -0.045), "steel", blk, axis="Y", verts=16, bevel=0.005)
    hexbolt("solenoidTerm", (0.27, -0.28, -0.045), blk, axis="Y", r=0.009, h=0.02, mat="copper")
    # ---- gear-type hydraulic pump off the timing case with suction/pressure hoses
    box("hydPumpBody", (0.09, 0.11, 0.1), (-0.2, 0.55, -0.13), "engineGrey", blk, bevel=0.012)
    cyl("hydPumpFlange", 0.06, 0.02, (-0.2, 0.505, -0.13), "engineGrey", blk, axis="Y", verts=20)
    hose("hydSuction", (-0.2, 0.6, -0.08), (-0.55, 0.55, -0.36), 0.05, 0.022, "hoseBlack", blk,
         da=(0, 0, 1), db=(0, 0, -1))
    hose("hydPressure", (-0.25, 0.58, -0.13), (-0.5, 0.75, -0.36), 0.04, 0.012, "hoseBlack", blk,
         da=(-1, 0, 0), db=(0, 0, -1))
    for nm, p in (("hydFit1", (-0.2, 0.6, -0.08)), ("hydFit2", (-0.25, 0.58, -0.13))):
        hexbolt(nm, p, blk, axis="X", r=0.016, h=0.02, mat="steel")
    # ---- engine wiring: starter main cable, alternator lead, senders, loom with ties
    hose("cableStarter", (0.27, -0.28, -0.045), (0.75, 0.1, -0.37), 0.08, 0.009, "wireBlack", blk)
    hose("cableAlt", (0.2, 0.42, 0.18), (0.27, -0.28, -0.04), 0.03, 0.005, "wireRed", blk)
    hose("wireOilSender", (0.232, 0.25, -0.03), (0.3, -0.2, 0.2), 0.04, 0.0025, "wireBlack", blk)
    hose("wireTempSender", (-0.145, 0.47, 0.26), (0.05, 0.4, 0.36), 0.03, 0.0025, "wireBlack", blk)
    sweep("engineLoom", [(0.05, 0.4, 0.36), (0.1, 0.0, 0.37), (0.2, -0.3, 0.33), (0.3, -0.45, 0.2)], 0.007,
          "wireBlack", blk, verts=6)
    for k, p in enumerate(((0.1, 0.0, 0.37), (0.2, -0.3, 0.33))):
        box("loomTie%d" % k, (0.02, 0.008, 0.02), p, "plasticBlack", blk, bevel=0.002)


def build_fuel_tank(e, loc):
    """Rounded steel diesel tank with straps, filler neck, cap on a chain, sender and drain."""
    t = empty("fuelTankAsm", loc, e)
    box("fuelTank", (0.52, 0.46, 0.5), (0, 0, 0), "red", t, bevel=0.07, segs=5)
    for k, y in enumerate((-0.13, 0.13)):
        sweep("tankStrap%d" % k, [(-0.28, y, -0.26), (-0.28, y, 0.2), (-0.22, y, 0.265), (0.22, y, 0.265),
                                  (0.28, y, 0.2), (0.28, y, -0.26)], 0, "metalDark", t,
              profile=[(-0.003, -0.018), (0.003, -0.018), (0.003, 0.018), (-0.003, 0.018)], twist_up=(0, 1, 0))
        cyl("strapBolt%d" % k, 0.008, 0.05, (0.29, y, -0.25), "steel", t, axis="Z", verts=6, smooth=0)
    cyl("fillerNeck", 0.045, 0.08, (0.12, 0.1, 0.28), "red", t, axis="Z", verts=20)
    cyl("fuelCap", 0.058, 0.03, (0.12, 0.1, 0.33), "black", t, axis="Z", verts=24, bevel=0.006)
    for k in range(8):
        a = k * math.pi / 4
        box("capGrip%d" % k, (0.012, 0.012, 0.028), (0.12 + math.cos(a) * 0.058, 0.1 + math.sin(a) * 0.058, 0.33),
            "black", t, bevel=0.002)
    hose("capChain", (0.12, 0.05, 0.32), (0.12, -0.02, 0.26), 0.02, 0.003, "steel", t)
    cyl("levelSender", 0.04, 0.02, (-0.12, -0.08, 0.255), "steel", t, axis="Z", verts=6, smooth=0)
    hose("senderWire", (-0.12, -0.08, 0.27), (-0.3, -0.2, 0.0), 0.05, 0.0025, "wireBlack", t)
    hexbolt("tankDrain", (0.0, 0.0, -0.255), t, r=0.014, h=0.012)


def build_air_filter(e, loc, outlet):
    """Oil-bath air cleaner with clear pre-cleaner bowl, clamps, rubber hose down to the manifold."""
    f = empty("airFilterAsm", loc, e)
    cyl("airFilter", 0.13, 0.4, (0, 0, 0), "black", f, axis="Z", verts=32, bevel=0.01)
    cyl("oilBathBowl", 0.14, 0.12, (0, 0, -0.22), "black", f, axis="Z", verts=32, bevel=0.012)
    for k in range(3):
        a = k * 2 * math.pi / 3
        box("bowlClip%d" % k, (0.014, 0.02, 0.09), (math.cos(a) * 0.145, math.sin(a) * 0.145, -0.17), "steel", f,
            bevel=0.003, rot=(0, 0, a))
    cyl("precleanerStem", 0.05, 0.08, (0, 0, 0.24), "black", f, axis="Z", verts=24)
    cyl("precleanerBowl", 0.085, 0.12, (0, 0, 0.34), "lampGlass", f, axis="Z", verts=28)
    cyl("precleanerCap", 0.095, 0.03, (0, 0, 0.415), "black", f, axis="Z", verts=28, r2=0.06, bevel=0.005)
    tube("filterBand", 0.136, 0.13, 0.03, (0, 0, 0.05), "steel", f, axis="Z", verts=32)
    o = Vector(outlet) - Vector(loc)
    pts = K.bezier_pts(Vector((0.14, 0, -0.1)), Vector((0.3, 0, -0.1)), o + Vector((0.0, 0.0, 0.25)), o, 14)
    sweep("intakeHose", pts, 0.042, "hoseBlack", f, verts=16)
    for k, idx in enumerate((1, len(pts) - 2)):
        d = (pts[idx + 1] - pts[idx - 1]).normalized()
        ring = tube("intakeClamp%d" % k, 0.05, 0.042, 0.014, (0, 0, 0), "steel", f, axis="Z", verts=20)
        ring.rotation_euler = d.to_track_quat("Z", "Y").to_euler()
        ring.location = pts[idx]


def cab_details(cab, zf, zt, yf, yb, x0, x1, lean):
    """Wiring looms, fuse box, switches, extra gauges, cab fan, dome light, CB mic lead, lever linkage."""
    for sx, x in ((-1, x0 + 0.045), (1, x1 - 0.045)):
        a, b = Vector((x, yf - 0.03, zf + 0.5)), Vector((x, yf + lean - 0.04, zt - 0.06))
        pts = [Vector((x * 0.7, yf - 0.05, zf + 0.72))] + [a.lerp(b, k / 5) for k in range(6)] + \
              [Vector((x, yf + lean - 0.2, zt - 0.05)), Vector((x, yb + 0.1, zt - 0.05))]
        sweep("pillarLoom%d" % sx, pts, 0.0075, "wireBlack", cab, verts=6)
        for k in range(1, 5):
            box("loomClip%d_%d" % (sx, k), (0.02, 0.012, 0.018), tuple(a.lerp(b, k / 5)), "plasticBlack", cab,
                bevel=0.002)
    # fuse box under the dash with fuses and hanging wires
    fb = empty("fuseBox", (0.22, yf - 0.1, zf + 0.58), cab)
    box("fuseBoxBody", (0.2, 0.05, 0.11), (0, 0, 0), "plasticBlack", fb, bevel=0.008)
    for k, m in enumerate(("redClean", "yellow", "steel", "redClean", "cream", "yellow", "steel", "redClean")):
        box("fuse%d" % k, (0.016, 0.012, 0.03), (-0.075 + k * 0.021, -0.03, 0.01), m, fb, bevel=0.002)
    for k, (m, end) in enumerate((("wireRed", (0.3, yf - 0.25, zf + 0.05)),
                                  ("wireBlack", (0.15, yf - 0.2, zf + 0.04)),
                                  ("wireRed", (-0.05, yf - 0.02, zf + 0.62)),
                                  ("wireBlack", (0.3, yf - 0.02, zf + 0.9)))):
        hose("fuseWire%d" % k, (0.18 + k * 0.03, yf - 0.1, zf + 0.53), end, 0.1, 0.004, m, cab)
    # extra small gauges (oil pressure, coolant temp, volts), warning lamps, toggle switches
    dash = empty("dashExtras", (0, yf - 0.17, zf + 0.85), cab, rot=(-0.5, 0, 0))
    for k, x in enumerate((-0.28, 0.0, 0.28)):
        z = -0.075 if k == 1 else -0.06
        cyl("miniGaugeFace%d" % k, 0.032, 0.006, (x, -0.03, z), "black", dash, axis="Y", verts=20)
        tube("miniGaugeBezel%d" % k, 0.037, 0.031, 0.01, (x, -0.033, z), "chrome", dash, axis="Y", verts=20)
        box("miniGaugeNeedle%d" % k, (0.003, 0.002, 0.026), (x + 0.006, -0.037, z + 0.006), "orangeRefl", dash,
            bevel=0, rot=(0, 0.6 - k * 0.5, 0))
    for k, m in enumerate(("redGlass", "amberGlass", "lampGlass", "redGlass", "amberGlass")):
        cyl("warnLamp%d" % k, 0.009, 0.012, (-0.08 + k * 0.04, -0.03, 0.085), m, dash, axis="Y", verts=12)
        tube("warnBezel%d" % k, 0.012, 0.009, 0.008, (-0.08 + k * 0.04, -0.032, 0.085), "chrome", dash, axis="Y",
             verts=12)
    for k in range(6):
        x = -0.2 + k * 0.08 if k < 3 else 0.04 + (k - 3) * 0.08
        cyl("toggleBase%d" % k, 0.01, 0.012, (x, -0.03, -0.1), "chrome", dash, axis="Y", verts=10)
        sweep("toggleLever%d" % k, [(x, -0.035, -0.1), (x, -0.06, -0.09)], 0.003, "chrome", dash, verts=6)
    # dome light + speaker in the headliner, small cab fan on the right pillar
    box("headliner", (x1 - x0 - 0.06, yf - yb - 0.05, 0.015), (0, (yf + yb) / 2 + 0.05, zt - 0.02), "cream", cab,
        bevel=0.004)
    cyl("domeLight", 0.05, 0.02, (0, (yf + yb) / 2, zt - 0.035), "lampGlass", cab, axis="Z", verts=20)
    tube("domeRim", 0.055, 0.05, 0.02, (0, (yf + yb) / 2, zt - 0.035), "plasticBlack", cab, axis="Z", verts=20)
    cyl("speaker", 0.06, 0.02, (-0.45, yb + 0.25, zt - 0.035), "plasticBlack", cab, axis="Z", verts=20)
    fan = empty("cabFan", (x1 - 0.1, yf - 0.02, zt - 0.2), cab, rot=(0, 0, math.radians(-35)))
    for k in range(3):
        tube("fanCage%d" % k, 0.075 - k * 0.022, 0.07 - k * 0.022, 0.004, (0, -0.03, 0), "chrome", fan, axis="Y",
             verts=24)
    for k in range(8):
        box("fanCageBar%d" % k, (0.15, 0.003, 0.003), (0, -0.03, 0), "chrome", fan, bevel=0, rot=(0, k * math.pi / 8, 0))
    for k in range(4):
        a = k * math.pi / 2 + 0.3
        box("fanBlade%d" % k, (0.055, 0.004, 0.028), (math.cos(a) * 0.035, -0.015, math.sin(a) * 0.035),
            "plasticBlack", fan, bevel=0.002, rot=(0.35, -a, 0))
    cyl("fanMotor", 0.03, 0.05, (0, 0.02, 0), "plasticBlack", fan, axis="Y", verts=16)
    box("fanMount", (0.02, 0.06, 0.02), (0, 0.06, 0), "metalDark", fan, bevel=0.003)
    # CB mic on a hook with coiled lead to the radio
    box("micHook", (0.02, 0.01, 0.03), (0.52, yf - 0.1, zt - 0.2), "metalDark", cab, bevel=0.002)
    box("cbMic", (0.05, 0.03, 0.07), (0.52, yf - 0.12, zt - 0.25), "plasticBlack", cab, bevel=0.012, segs=3)
    helix("micLead", (0.52, yf - 0.12, zt - 0.29), (0.42, yf - 0.2, zt - 0.14), 0.01, 9, 0.0022, "plasticBlack",
          cab)
    # lever gate plate and linkage rods through the floor
    box("leverGate", (0.13, 0.3, 0.008), (0.38, 0.8, zf + 0.308), "plasticBlack", cab, bevel=0.002)
    for k, x in enumerate((0.33, 0.38, 0.43)):
        box("gateSlot%d" % k, (0.012, 0.2, 0.01), (x, 0.8, zf + 0.31), "metalDark", cab, bevel=0)
    # inner door handle and window latch
    box("doorInnerHandle", (0.02, 0.1, 0.02), (x0 + 0.03, 1.0, zf + 0.62), "metalDark", cab, bevel=0.005)
    box("windowLatch", (0.02, 0.05, 0.015), (x0 + 0.02, 0.9, zf + 1.1), "chrome", cab, bevel=0.003)


def hollow_walker(name, x, parent):
    """Straw walker as a sheet-metal trough: sawtooth side plates, perforated step plates, bottom pan."""
    teeth = []
    for s in range(5):
        y = 0.35 - s * 0.24
        teeth += [(y, 0.0), (y - 0.18, 0.12)]
    side = teeth + [(-0.95, 0.0), (-0.95, -0.12), (0.35, -0.12)]
    for sx in (-1, 1):
        poly_prism("%s_side%d" % (name, sx), side, 0.008, "galv", parent, plane="YZ",
                   offset=x + sx * 0.165 - (0.008 if sx > 0 else 0))
    box(name + "_pan", (0.33, 1.28, 0.008), (x, -0.3, -0.12), "galv", parent, bevel=0)
    a = math.atan2(0.12, 0.18)
    L = math.hypot(0.18, 0.12)
    for s in range(5):
        y = 0.35 - s * 0.24
        c = (y - 0.09, 0.06)
        box("%s_step%d" % (name, s), (0.32, L, 0.006), (x, c[0], c[1]), "galv", parent, bevel=0, rot=(-a, 0, 0))
        for h in range(3):
            cyl("%s_hole%d_%d" % (name, s, h), 0.018, 0.008, (x - 0.1 + h * 0.1, c[0], c[1] + 0.004), "metalDark",
                parent, axis="Z", verts=10, rot=(-a, 0, 0))
