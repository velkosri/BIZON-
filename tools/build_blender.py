"""Blender entry point: blender -b -P tools/build_blender.py -- <out_dir> [preview|final|none]

Builds the Bizon + header, exports both to i3d/.i3d.shapes, writes the node map for the XML
generator and renders beauty/store images.
"""
import json
import math
import os
import sys

import bpy
from mathutils import Euler, Vector

sys.path.insert(0, os.path.dirname(__file__))
import bizon_model as B  # noqa: E402
import i3d_export as X  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = os.path.abspath(argv[0] if argv else "build")
MODE = argv[1] if len(argv) > 1 else "preview"
MOD = os.path.join(OUT, "mod", "FS25_BizonSuperZ056")

bpy.ops.wm.read_factory_settings(use_empty=True)
B.materials()
comb = B.build_combine()
head = B.build_header()

# ---- data for the XML generator (GIANTS space)
anim = dict(B.ANIM)
anim["pipeUnfoldRot"] = X.g_euler_deg(Euler((0, 0, math.radians(B.ANIM["pipe"]["unfoldZ"]))).to_matrix())
anim["jointRotLower"] = X.g_euler_deg(Euler((math.radians(-B.ANIM["feeder"]["lowerRot"]), 0, 0)).to_matrix())
anim["jointRotUpper"] = X.g_euler_deg(Euler((math.radians(-B.ANIM["feeder"]["upperRot"]), 0, 0)).to_matrix())


def feeder_mouth_height(deg_down):
    rot = bpy.data.objects["attacherJointRot"]
    rot.rotation_euler = (math.radians(-deg_down), 0, 0)
    bpy.context.view_layer.update()
    h = bpy.data.objects["attacherJointCutter"].matrix_world.translation.z
    rot.rotation_euler = (0, 0, 0)
    bpy.context.view_layer.update()
    return h


anim["jointHeightLower"] = feeder_mouth_height(B.ANIM["feeder"]["lowerRot"])
anim["jointHeightUpper"] = feeder_mouth_height(B.ANIM["feeder"]["upperRot"])


if MODE != "render-only":
    for d in ("vehicles/bizonSuperZ056", "vehicles/bizonHeader42", "textures"):
        os.makedirs(os.path.join(MOD, d), exist_ok=True)
    X.prepare_for_export(comb)
    X.prepare_for_export(head)
    ex = X.Exporter(os.path.join(MOD, "vehicles/bizonSuperZ056"), "bizonSuperZ056",
                    {"decals": "../../textures/bizon_decals_diffuse.dds"})
    info_c = ex.export([comb])
    exh = X.Exporter(os.path.join(MOD, "vehicles/bizonHeader42"), "bizonHeader42",
                     {"decals": "../../textures/bizon_decals_diffuse.dds"})
    info_h = exh.export([head])
    json.dump({"combine": info_c, "header": info_h, "anim": anim}, open(os.path.join(OUT, "nodes.json"), "w"),
              indent=1, default=list)
    print("EXPORT combine shapes=%d tris=%d mats=%d | header shapes=%d tris=%d" % (
        info_c["shapes"], info_c["tris"], info_c["materials"], info_h["shapes"], info_h["tris"]))

def fit_camera(cam, margin=1.08):
    """Frame every render-visible mesh from the camera's current direction."""
    bpy.context.view_layer.update()
    pts = []
    for o in bpy.data.objects:
        if o.type == "MESH" and not o.hide_render and o.visible_get():
            pts.extend(c for corner in o.bound_box for c in (o.matrix_world @ Vector(corner)))
    loc, _ = cam.camera_fit_coords(bpy.context.evaluated_depsgraph_get(), pts)
    cam.location = loc
    cam.data.lens /= margin


if MODE in ("preview", "final", "render-only", "blend"):
    final = MODE != "preview"
    import blender_kit as K
    for n in [o.name for o in bpy.data.objects if o.type == "EMPTY" and not o.get("export", True)]:
        o = bpy.data.objects.get(n)
        if o is not None:
            K.join_children(o, render_only=True)
    sc = B.setup_render_scene((1920, 1080) if final else (960, 540))
    sc.cycles.samples = 40 if final else 16
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.adaptive_threshold = 0.05
    sc.render.use_persistent_data = True
    B.attach_header_for_render(head, feeder_rot_deg=-6)
    shots = {
        "render_front_left": ((-10.0, 8.6, 3.5), (0.1, -0.9, 1.75), 40),
        "render_rear_right": ((9.2, -11.0, 4.2), (0, -1.9, 1.8), 42, 0.55),
        "render_left_detail": ((-5.6, -1.3, 2.25), (-0.8, -1.45, 1.9), 28),
        "render_engine_bay": ((-4.3, -4.6, 4.4), (-0.7, -1.85, 2.55), 30, 0.3),
        "render_cab_right": ((4.6, 4.2, 4.4), (0.6, 0.6, 2.7), 34, 0.6),
        "render_beer_crate": ((-0.6, 1.22, 2.92), (-0.5, 0.6, 2.36), 28, 1.5),
        "render_beer_bottle": ((-0.3, 1.28, 2.62), (-0.55, 0.84, 2.37), 42, 1.6),
        "render_wheel": ((-3.4, 2.2, 1.05), (-1.25, 0.0, 0.68), 38),
    }
    only = os.environ.get("BIZON_SHOTS")
    if only:
        shots = {k: v for k, v in shots.items() if k in only.split(",")}
    base_exp = sc.view_settings.exposure
    for name, shot in (shots.items() if MODE != "blend" else ()):
        loc, tgt, lens = shot[:3]
        sc.view_settings.exposure = base_exp + (shot[3] if len(shot) > 3 else 0)
        cam = B.add_camera("cam_" + name, loc, tgt, lens)
        sc.camera = cam
        sc.render.filepath = os.path.join(OUT, name + ".png")
        bpy.ops.render.render(write_still=True)
        print("RENDERED", sc.render.filepath)
    sc.view_settings.exposure = base_exp if MODE != "blend" else sc.view_settings.exposure
    if final and MODE != "blend":
        # store image: transparent background, no ground
        for n in ("ground", "stubbleEmitter", "swathEmitter"):
            if n in bpy.data.objects:
                bpy.data.objects[n].hide_render = True
        sc.render.film_transparent = True
        sc.render.resolution_x = sc.render.resolution_y = 768
        sc.cycles.samples = int(os.environ.get("BIZON_STORE_SAMPLES", "48"))
        # more side-on than 45 deg so the vertical unloading tube does not cover the BIZON lettering
        cam = B.add_camera("cam_store", (-12.5, 8.5, 4.8), (0.3, -0.4, 1.6), 40)
        sc.camera = cam
        fit_camera(cam)
        sc.render.filepath = os.path.join(OUT, "store_combine.png")
        bpy.ops.render.render(write_still=True)
        # header only
        for o in bpy.data.objects:
            o["_hr"] = o.hide_render
        keep = set([head.name] + [c.name for c in head.children_recursive])
        for o in bpy.data.objects:
            if o.type != "CAMERA" and o.type != "LIGHT" and o.name not in keep:
                o.hide_render = True
        cam = B.add_camera("cam_store_h", tuple(Vector(head.matrix_world.translation) + Vector((-4.5, 5.5, 2.8))),
                           tuple(Vector(head.matrix_world.translation) + Vector((0, 0.8, -0.2))), 32)
        sc.camera = cam
        fit_camera(cam)
        sc.render.filepath = os.path.join(OUT, "store_header.png")
        bpy.ops.render.render(write_still=True)
        for o in bpy.data.objects:
            o.hide_render = o.get("_hr", o.hide_render)
    if MODE == "blend":
        sc.camera = B.add_camera("cam_view", (-10.0, 8.6, 3.5), (0.1, -0.9, 1.75), 40)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "bizonSuperZ056.blend"))
