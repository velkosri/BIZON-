"""Unique UV atlas (uv1) + baked vehicleShader vmask for the GIANTS vehicleShader.

vmask channels (GIANTS convention): R = wear/scratch mask, G = ambient occlusion, B = dirt mask.
The shader samples the vmask with the second UV set, detail maps keep tiling on uv0.
"""
import math

import bpy
import numpy as np


def render_meshes(root):
    out = []
    for o in [root] + list(root.children_recursive):
        if o.type == "MESH" and o.get("export", True) and o.get("kind", "") in ("", "effect") \
                and not o.get("decal") and len(o.data.polygons):
            out.append(o)
    return out


def unwrap_atlas(objs, margin=0.0008):
    ctx = bpy.context
    for o in objs:
        me = o.data
        if "uv1" not in me.uv_layers:
            me.uv_layers.new(name="uv1")
        me.uv_layers.active = me.uv_layers["uv1"]
    for o in ctx.selected_objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    ctx.view_layer.objects.active = objs[0]
    # UV ops in background mode only touch UV-selected islands; sync makes "all faces" mean all islands
    ctx.scene.tool_settings.use_uv_select_sync = True
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=margin, area_weight=0.0,
                             scale_to_bounds=False)
    bpy.ops.uv.select_all(action="SELECT")
    bpy.ops.uv.average_islands_scale()
    bpy.ops.uv.pack_islands(rotate=True, margin=margin, shape_method="AABB")
    bpy.ops.object.mode_set(mode="OBJECT")
    for o in objs:
        o.data.uv_layers.active = o.data.uv_layers["uv0"]
        o.select_set(False)
    return uv_area_sum(objs)


def uv_area_sum(objs):
    """Sum of uv1 triangle areas: > 1 means overlapping islands."""
    tot = 0.0
    for o in objs:
        me = o.data
        uv = np.empty(len(me.loops) * 2, np.float32)
        me.uv_layers["uv1"].data.foreach_get("uv", uv)
        uv = uv.reshape(-1, 2)
        me.calc_loop_triangles()
        tri = np.empty(len(me.loop_triangles) * 3, np.int32)
        me.loop_triangles.foreach_get("loops", tri)
        t = uv[tri.reshape(-1, 3)]
        d1, d2 = t[:, 1] - t[:, 0], t[:, 2] - t[:, 0]
        tot += float(np.abs(d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0]).sum() / 2)
    return tot


def _materials(objs):
    mats = []
    for o in objs:
        for s in o.material_slots:
            if s.material and s.material not in mats:
                mats.append(s.material)
    return mats


def _bake(objs, img, kind, samples):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.render.bake.margin = 2
    sc.render.bake.use_clear = True
    for o in objs:
        o.data.uv_layers.active = o.data.uv_layers["uv1"]
    for m in _materials(objs):
        nt = m.node_tree
        n = nt.nodes.get("__bake_target") or nt.nodes.new("ShaderNodeTexImage")
        n.name = "__bake_target"
        n.image = img
        nt.nodes.active = n
    for o in bpy.context.selected_objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.bake(type=kind, uv_layer="uv1")
    return np.array(img.pixels[:], dtype=np.float32).reshape(img.size[1], img.size[0], 4)


def _emission_masks(m):
    """Temporarily route R=edge wear, B=height dirt (with noise) into an emission shader."""
    nt = m.node_tree
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    prev = [l.from_socket for l in nt.links if l.to_socket == out.inputs["Surface"]]
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 9.0
    noise.inputs["Detail"].default_value = 6.0
    nt.links.new(geo.outputs["Position"], noise.inputs["Vector"])

    def math_node(op, a, b, clamp=False):
        n = nt.nodes.new("ShaderNodeMath")
        n.operation = op
        n.use_clamp = clamp
        for i, v in enumerate((a, b)):
            if hasattr(v, "is_output"):
                nt.links.new(v, n.inputs[i])
            else:
                n.inputs[i].default_value = v
        return n.outputs[0]

    wear = math_node("MULTIPLY", math_node("SUBTRACT", geo.outputs["Pointiness"], 0.52), 10.0, True)
    wear = math_node("MULTIPLY", wear, math_node("ADD", noise.outputs["Fac"], 0.2), True)
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(geo.outputs["Position"], sep.inputs[0])
    low = math_node("SUBTRACT", 1.0, math_node("DIVIDE", sep.outputs["Z"], 2.6), True)
    dirt = math_node("MULTIPLY", math_node("POWER", low, 1.6), math_node("ADD", noise.outputs["Fac"], 0.35), True)
    comb = nt.nodes.new("ShaderNodeCombineColor")
    nt.links.new(wear, comb.inputs["Red"])
    comb.inputs["Green"].default_value = 1.0  # coverage marker (background stays 0)
    nt.links.new(dirt, comb.inputs["Blue"])
    em = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(comb.outputs[0], em.inputs["Color"])
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    return out, prev


def _blur(a, it=2):
    for _ in range(it):
        a = (a + np.roll(a, 1, 0) + np.roll(a, -1, 0) + np.roll(a, 1, 1) + np.roll(a, -1, 1)) / 5.0
    return a


def _strip_see_through():
    """Glass and alpha decals are see-through in game; drop their faces from copies while baking so they
    don't cast AO (ghost letters around decals, dark cab). Returns [(obj, original_mesh)] to restore."""
    import bmesh
    swapped = []
    for o in bpy.context.scene.objects:
        if o.type != "MESH" or o.hide_render:
            continue
        bad = {i for i, s in enumerate(o.material_slots) if s.material and s.material.get("fs_kind") in ("glass", "decal")}
        if not bad:
            continue
        me = o.data.copy()
        bm = bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.material_index in bad], context="FACES")
        bm.to_mesh(me)
        bm.free()
        swapped.append((o, o.data))
        o.data = me
    return swapped


def bake_vmask(objs, size, png_path, ao_samples=8):
    sc = bpy.context.scene
    if sc.world is None:
        sc.world = bpy.data.worlds.new("bakeWorld")
    sc.world.light_settings.distance = 0.6
    objs = [o for o in objs if not o.hide_render]
    img = bpy.data.images.new("vmask_bake", size, size, alpha=False, float_buffer=True)
    swapped = _strip_see_through()
    ao = _bake([o for o in objs if len(o.data.polygons)], img, "AO", ao_samples)[..., 0]
    for o, orig in swapped:
        tmp = o.data
        o.data = orig
        bpy.data.meshes.remove(tmp)
    saved = [(m,) + _emission_masks(m) for m in _materials(objs)]
    em = _bake(objs, img, "EMIT", 1)
    for m, out, prev in saved:
        nt = m.node_tree
        for l in [l for l in nt.links if l.to_socket == out.inputs["Surface"]]:
            nt.links.remove(l)
        for s in prev:
            nt.links.new(s, out.inputs["Surface"])
    # lifted AO: the game adds its own SSAO/shadows, a raw 0..1 occlusion reads far too dark
    ao = 0.3 + 0.7 * np.clip(_blur(ao) * 1.08, 0, 1) ** 0.7
    wear = np.clip(em[..., 0], 0, 1)
    dirt = np.clip(em[..., 2] * 0.75 + (1 - ao) * 0.5, 0, 1)
    # sub-pixel parts (bolts, thin wires) can miss every texel: give the empty atlas neutral values
    bg = em[..., 1] < 0.5
    ao[bg], wear[bg], dirt[bg] = 1.0, 0.0, 0.35
    rgba = np.stack([wear, ao, dirt, np.ones_like(ao)], -1)
    out = bpy.data.images.new("vmask_out", size, size, alpha=False)
    out.pixels[:] = rgba.reshape(-1)
    out.filepath_raw = png_path
    out.file_format = "PNG"
    out.save()
    for o in objs:
        o.data.uv_layers.active = o.data.uv_layers["uv0"]
    return png_path
