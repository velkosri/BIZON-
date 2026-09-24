"""Small modelling toolkit on top of bpy/bmesh used by the Bizon build script.

Blender axes: X right, Y forward, Z up. Vehicle left side is -X.
"""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

MATS = {}

# FS25 detail library sets: (diffuse, specular, normal)
DL = "$data/shared/detailLibrary/"
DETAIL = {
    "paintOld": (DL + "nonMetallic/metal/metalPaintedOld_diffuse.png", DL + "nonMetallic/metal/metalPaintedOld_specular.png", DL + "flat_normal.png"),
    "paint": (DL + "nonMetallic/metal/metalPainted_diffuse.png", DL + "nonMetallic/metal/metalPainted_specular.png", DL + "flat_normal.png"),
    "galvanized": (DL + "metallic/metalGalvanized_diffuse.png", DL + "metallic/metalGalvanized_specular.png", DL + "metallic/metalGalvanized_normal.png"),
    "scratched": (DL + "metallic/scratched_diffuse.png", DL + "metallic/scratched_specular.png", DL + "flat_normal.png"),
    "silver": (DL + "metallic/silverScratched_diffuse.png", DL + "metallic/silverScratched_specular.png", DL + "flat_normal.png"),
    "chrome": (DL + "metallic/clear_diffuse.png", DL + "metallic/clear_specular.png", DL + "flat_normal.png"),
    "rubber": (DL + "nonMetallic/rubber/rubber_diffuse.png", DL + "nonMetallic/rubber/rubber_specular.png", DL + "nonMetallic/rubber/rubber_normal.png"),
    "tread": (DL + "metallic/steelTreadPlate_diffuse.png", DL + "metallic/steelTreadPlate_specular.png", DL + "metallic/steelTreadPlate_normal.png"),
    "plastic": (DL + "nonMetallic/plastic/plasticPainted_diffuse.png", DL + "nonMetallic/plastic/plasticPainted_specular.png", DL + "flat_normal.png"),
    "leather": (DL + "nonMetallic/leather/leather1_diffuse.png", DL + "nonMetallic/leather/leather1_specular.png", DL + "nonMetallic/leather/leather1_normal.png"),
    "fabric": (DL + "nonMetallic/fabric/fabric2_diffuse.png", DL + "nonMetallic/fabric/fabric2_specular.png", DL + "nonMetallic/fabric/fabric2_normal.png"),
    "wood": (DL + "nonMetallic/wood/wood1_diffuse.png", DL + "nonMetallic/wood/wood1_specular.png", DL + "nonMetallic/wood/wood1_normal.png"),
}


def srgb_to_lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def material(key, rgb, rough=0.5, metal=0.0, detail="paint", alpha=1.0, emission=None, image=None,
             grime=0.0, fs=None):
    """rgb given in sRGB 0..1. fs: 'glass' | 'decal' | 'emissive' | None (vehicleShader)."""
    lin = tuple(srgb_to_lin(c) for c in rgb)
    m = bpy.data.materials.new(key)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*lin, 1)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    if image:
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = bpy.data.images.load(image, check_existing=True)
        nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
        nt.links.new(tex.outputs["Alpha"], bsdf.inputs["Alpha"])
        m.blend_method = "HASHED" if hasattr(m, "blend_method") else None
    if alpha < 1:
        bsdf.inputs["Alpha"].default_value = alpha
        bsdf.inputs["Transmission Weight"].default_value = 0.0
    if emission:
        bsdf.inputs["Emission Color"].default_value = (*emission, 1)
        bsdf.inputs["Emission Strength"].default_value = 4.0
    if grime > 0:
        _add_grime(nt, bsdf, lin, grime)
    m["fs_kind"] = fs or "vehicle"
    m["fs_detail"] = detail
    m["fs_color"] = list(lin)
    m["fs_alpha"] = alpha
    if image:
        m["fs_image"] = image
    MATS[key] = m
    return m


def _add_grime(nt, bsdf, lin, amount):
    """Render-only wear: noise driven darkening/desaturation + roughness variation."""
    tc = nt.nodes.new("ShaderNodeTexCoord")
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 6.0
    noise.inputs["Detail"].default_value = 8.0
    nt.links.new(tc.outputs["Object"], noise.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.45
    ramp.color_ramp.elements[1].position = 0.75
    nt.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.inputs["A"].default_value = (*lin, 1)
    dirt = (lin[0] * 0.35 + 0.02, lin[1] * 0.35 + 0.018, lin[2] * 0.3 + 0.012, 1)
    dirt = (lin[0] * 0.3 + 0.03, lin[1] * 0.3 + 0.022, lin[2] * 0.25 + 0.012, 1)
    mix.inputs["B"].default_value = dirt
    mul = nt.nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    mul.inputs[1].default_value = amount
    nt.links.new(ramp.outputs["Color"], mul.inputs[0])
    nt.links.new(mul.outputs[0], mix.inputs["Factor"])
    nt.links.new(mix.outputs["Result"], bsdf.inputs["Base Color"])
    rmix = nt.nodes.new("ShaderNodeMapRange")
    rmix.inputs["To Min"].default_value = bsdf.inputs["Roughness"].default_value
    rmix.inputs["To Max"].default_value = min(1.0, bsdf.inputs["Roughness"].default_value + 0.35)
    nt.links.new(mul.outputs[0], rmix.inputs["Value"])
    nt.links.new(rmix.outputs["Result"], bsdf.inputs["Roughness"])


# ---------------------------------------------------------------- objects


def link(obj, parent=None):
    bpy.context.scene.collection.objects.link(obj)
    if parent is not None:
        obj.parent = parent
    return obj


def empty(name, loc=(0, 0, 0), parent=None, rot=None, props=None):
    """Transform group. loc/rot are relative to parent (parent is assumed unrotated unless rot given)."""
    e = bpy.data.objects.new(name, None)
    e.empty_display_size = 0.15
    link(e, parent)
    e.location = loc
    if rot is not None:
        e.rotation_euler = rot
    for k, v in (props or {}).items():
        e[k] = v
    return e


def mesh_from_bm(name, bm, mat, parent=None, loc=(0, 0, 0), smooth_angle=35, props=None):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    if isinstance(mat, (list, tuple)):
        for m in mat:
            me.materials.append(MATS[m] if isinstance(m, str) else m)
    else:
        me.materials.append(MATS[mat] if isinstance(mat, str) else mat)
    for p in me.polygons:
        p.use_smooth = True
    if smooth_angle is not None:
        me.set_sharp_from_angle(angle=math.radians(smooth_angle))
    o = bpy.data.objects.new(name, me)
    link(o, parent)
    o.location = loc
    for k, v in (props or {}).items():
        o[k] = v
    return o


def _bm_transform(bm, loc=(0, 0, 0), rot=(0, 0, 0), scale=None):
    m = Matrix.Translation(Vector(loc)) @ Matrix.Rotation(rot[2], 4, "Z") @ Matrix.Rotation(rot[1], 4, "Y") \
        @ Matrix.Rotation(rot[0], 4, "X")
    if scale:
        m = m @ Matrix.Diagonal((*scale, 1))
    bmesh.ops.transform(bm, matrix=m, verts=bm.verts)


def box(name, size, loc, mat, parent=None, bevel=0.01, rot=(0, 0, 0), segs=2, props=None):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
    if bevel > 0:
        # sheet-metal look: never razor sharp, folded edges scale with the part
        off = min(max(bevel, min(0.03, min(size) * 0.22)), min(size) * 0.45)
        bmesh.ops.bevel(bm, geom=bm.edges[:] + bm.verts[:], offset=off, segments=max(segs, 3),
                        affect="EDGES", profile=0.5)
    _bm_transform(bm, (0, 0, 0), rot)
    return mesh_from_bm(name, bm, mat, parent, loc, props=props)


def cyl(name, r, depth, loc, mat, parent=None, axis="X", verts=24, r2=None, cap=True, bevel=0.0,
        rot=None, props=None, smooth=35):
    """Cylinder/cone along axis ('X','Y','Z'), centered at loc."""
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=cap, cap_tris=False, segments=verts, radius1=r,
                          radius2=r if r2 is None else r2, depth=depth)
    if bevel > 0:
        edges = [e for e in bm.edges if len(e.link_faces) == 2 and
                 abs(e.link_faces[0].normal.dot(e.link_faces[1].normal)) < 0.3]
        bmesh.ops.bevel(bm, geom=edges, offset=bevel, segments=2, affect="EDGES")
    r_ = {"X": (0, math.pi / 2, 0), "Y": (math.pi / 2, 0, 0), "Z": (0, 0, 0)}[axis] if rot is None else rot
    _bm_transform(bm, (0, 0, 0), r_)
    return mesh_from_bm(name, bm, mat, parent, loc, smooth_angle=smooth, props=props)


def tube(name, r_out, r_in, depth, loc, mat, parent=None, axis="X", verts=32, props=None):
    bm = bmesh.new()
    res = bmesh.ops.create_circle(bm, cap_ends=False, segments=verts, radius=r_out)
    outer = res["verts"]
    res2 = bmesh.ops.create_circle(bm, cap_ends=False, segments=verts, radius=r_in)
    inner = res2["verts"]
    faces = []
    for i in range(verts):
        j = (i + 1) % verts
        faces.append(bm.faces.new((outer[i], outer[j], inner[j], inner[i])))
    ext = bmesh.ops.extrude_face_region(bm, geom=faces)
    vs = [g for g in ext["geom"] if isinstance(g, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=Vector((0, 0, depth)), verts=vs)
    bmesh.ops.translate(bm, vec=Vector((0, 0, -depth / 2)), verts=bm.verts)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    r_ = {"X": (0, math.pi / 2, 0), "Y": (math.pi / 2, 0, 0), "Z": (0, 0, 0)}[axis]
    _bm_transform(bm, (0, 0, 0), r_)
    return mesh_from_bm(name, bm, mat, parent, loc, props=props)


def sweep(name, pts, r, mat, parent=None, verts=10, closed=False, profile=None, props=None, twist_up=None):
    """Sweep a circle (or given 2D profile list) along a polyline of Vector points (parent space)."""
    pts = [Vector(p) for p in pts]
    if profile is None:
        profile = [(math.cos(2 * math.pi * i / verts) * r, math.sin(2 * math.pi * i / verts) * r)
                   for i in range(verts)]
    n = len(pts)
    bm = bmesh.new()
    rings = []
    up_ref = Vector(twist_up) if twist_up else None
    prev_side = None
    for i, p in enumerate(pts):
        if closed:
            t = (pts[(i + 1) % n] - pts[i - 1])
        else:
            t = (pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)])
        t.normalize()
        if up_ref is not None:
            side = t.cross(up_ref)
            if side.length < 1e-6:
                side = prev_side or Vector((1, 0, 0))
        elif prev_side is None:
            ref = Vector((0, 0, 1)) if abs(t.z) < 0.9 else Vector((1, 0, 0))
            side = t.cross(ref)
        else:
            side = prev_side - t * prev_side.dot(t)  # parallel transport
        side.normalize()
        prev_side = side
        up = side.cross(t).normalized()
        ring = [bm.verts.new(p + side * a + up * b) for a, b in profile]
        rings.append(ring)
    m = len(profile)
    last = n if closed else n - 1
    for i in range(last):
        a, b = rings[i], rings[(i + 1) % n]
        for k in range(m):
            kk = (k + 1) % m
            bm.faces.new((a[k], a[kk], b[kk], b[k]))
    if not closed:
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return mesh_from_bm(name, bm, mat, parent, (0, 0, 0), smooth_angle=60, props=props)


def bezier_pts(p0, p1, p2, p3, n=16):
    p0, p1, p2, p3 = map(Vector, (p0, p1, p2, p3))
    out = []
    for i in range(n + 1):
        t = i / n
        out.append((1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1 + 3 * (1 - t) * t * t * p2 + t ** 3 * p3)
    return out


def hose(name, a, b, sag=0.15, r=0.012, mat="rubber", parent=None, da=None, db=None, n=18):
    """Flexible hose/cable between points a and b with sag and optional start/end directions."""
    a, b = Vector(a), Vector(b)
    L = (b - a).length
    da = Vector(da).normalized() if da else (b - a).normalized()
    db = Vector(db).normalized() if db else (b - a).normalized()
    p1 = a + da * L * 0.35 + Vector((0, 0, -sag))
    p2 = b - db * L * 0.35 + Vector((0, 0, -sag))
    return sweep(name, bezier_pts(a, p1, p2, b, n), r, mat, parent, verts=8)


def poly_prism(name, pts2d, depth, mat, parent=None, plane="YZ", offset=0.0, bevel=0.0, props=None):
    """Extrude a 2D polygon. plane 'YZ': pts are (y,z), extruded along X from offset to offset+depth."""
    bm = bmesh.new()
    vs = []
    for a, b in pts2d:
        if plane == "YZ":
            vs.append(bm.verts.new((offset, a, b)))
        elif plane == "XZ":
            vs.append(bm.verts.new((a, offset, b)))
        else:
            vs.append(bm.verts.new((a, b, offset)))
    f = bm.faces.new(vs)
    bmesh.ops.recalc_face_normals(bm, faces=[f])
    ext = bmesh.ops.extrude_face_region(bm, geom=[f])
    v2 = [g for g in ext["geom"] if isinstance(g, bmesh.types.BMVert)]
    d = {"YZ": (depth, 0, 0), "XZ": (0, depth, 0), "XY": (0, 0, depth)}[plane]
    bmesh.ops.translate(bm, vec=Vector(d), verts=v2)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if bevel > 0:
        bmesh.ops.bevel(bm, geom=bm.edges[:], offset=bevel, segments=3, affect="EDGES", clamp_overlap=True,
                        profile=0.5)
    return mesh_from_bm(name, bm, mat, parent, props=props)


def decal(name, center, size, region, mat, parent=None, normal="-X", props=None):
    """Flat quad textured with an atlas region [u0, v0, u1, v1], facing along `normal`."""
    w, h = size
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("uv0")
    # local quad in XY facing +Z, then rotate
    co = [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)]
    vs = [bm.verts.new((x, y, 0)) for x, y in co]
    f = bm.faces.new(vs)
    u0, v0, u1, v1 = region
    for loop, (uu, vv) in zip(f.loops, ((u0, v0), (u1, v0), (u1, v1), (u0, v1))):
        loop[uv].uv = (uu, vv)
    rots = {
        "-X": Matrix.Rotation(-math.pi / 2, 4, "Z") @ Matrix.Rotation(math.pi / 2, 4, "X"),
        "+X": Matrix.Rotation(math.pi / 2, 4, "Z") @ Matrix.Rotation(math.pi / 2, 4, "X"),
        "+Y": Matrix.Rotation(math.pi, 4, "Z") @ Matrix.Rotation(math.pi / 2, 4, "X"),
        "-Y": Matrix.Rotation(math.pi / 2, 4, "X"),
        "+Z": Matrix.Identity(4),
    }
    bmesh.ops.transform(bm, matrix=rots[normal], verts=bm.verts)
    o = mesh_from_bm(name, bm, mat, parent, center, smooth_angle=None, props=props)
    o["keep_uv"] = True
    o["decal"] = True
    return o


def gear(name, r, width, teeth, loc, mat, parent=None, axis="X", tooth_h=None, props=None):
    """Sprocket/pulley-like toothed disk."""
    th = tooth_h or r * 0.12
    pts = []
    for i in range(teeth * 2):
        a = math.pi * 2 * i / (teeth * 2)
        rr = r + (th if i % 2 == 0 else 0)
        pts.append((math.cos(a) * rr, math.sin(a) * rr))
    o = poly_prism(name, pts, width, mat, parent, plane="XY", offset=-width / 2)
    r_ = {"X": (0, math.pi / 2, 0), "Y": (math.pi / 2, 0, 0), "Z": (0, 0, 0)}[axis]
    o.data.transform(Matrix.Rotation(r_[1], 4, "Y") @ Matrix.Rotation(r_[0], 4, "X"))
    o.location = loc
    return o


def pulley(name, r, width, loc, mat, parent=None, spokes=5, axis="X", hub_mat="metalDark", groove=True):
    """V-belt pulley with visible spokes (so rotation reads in game). Built around its own origin
    under an empty so it can spin. Returns the empty."""
    e = empty(name, loc, parent)
    rim_w = width
    rim = tube(name + "_rim", r, r * 0.82, rim_w, (0, 0, 0), mat, e, axis=axis, verts=40)
    if groove:
        tube(name + "_groove", r * 0.93, r * 0.8, rim_w * 0.45, (0, 0, 0), "metalDark", e, axis=axis, verts=40)
    cyl(name + "_hub", r * 0.22, width * 1.3, (0, 0, 0), hub_mat, e, axis=axis, verts=20)
    for i in range(spokes):
        a = math.pi * 2 * i / spokes
        ln = r * 0.62
        c = (math.cos(a) * r * 0.5, math.sin(a) * r * 0.5)
        if axis == "X":
            b = box(name + "_sp%d" % i, (width * 0.5, ln, r * 0.12), (0, c[0], c[1]), mat, e, bevel=0.004,
                    rot=(a, 0, 0))
        elif axis == "Y":
            b = box(name + "_sp%d" % i, (ln, width * 0.5, r * 0.12), (c[0], 0, c[1]), mat, e, bevel=0.004,
                    rot=(0, -a, 0))
        else:
            b = box(name + "_sp%d" % i, (ln, r * 0.12, width * 0.5), (c[0], c[1], 0), mat, e, bevel=0.004,
                    rot=(0, 0, a))
    return e


def belt_path(c1, r1, c2, r2, n_arc=14):
    """Closed outer-tangent path around two circles in the (y, z) plane. Returns list of (y, z)."""
    c1, c2 = Vector(c1), Vector(c2)
    d = c2 - c1
    L = d.length
    base = math.atan2(d.y, d.x)
    phi = math.acos(max(-1.0, min(1.0, (r1 - r2) / L)))
    pts = []
    # arc on circle 1 from base+phi to base+2pi-phi
    a0, a1 = base + phi, base + 2 * math.pi - phi
    for i in range(n_arc + 1):
        a = a0 + (a1 - a0) * i / n_arc
        pts.append(c1 + Vector((math.cos(a), math.sin(a))) * r1)
    a0, a1 = base - phi, base + phi
    for i in range(n_arc + 1):
        a = a0 + (a1 - a0) * i / n_arc
        pts.append(c2 + Vector((math.cos(a), math.sin(a))) * r2)
    return pts


def belt(name, x, c1, r1, c2, r2, mat="rubberBelt", parent=None, w=0.03, t=0.022):
    pts2 = belt_path(c1, r1, c2, r2)
    pts = [Vector((x, p.x, p.y)) for p in pts2]
    # profile: first coord radial (thickness), second axial (belt width)
    prof = [(-t / 2, -w / 2), (t / 2, -w / 2), (t / 2, w / 2), (-t / 2, w / 2)]
    return sweep(name, pts, 0, mat, parent, closed=True, profile=prof, twist_up=(1, 0, 0))


def rivets(name, p0, p1, n, mat, parent=None, r=0.008, normal="-X"):
    p0, p1 = Vector(p0), Vector(p1)
    bm = bmesh.new()
    for i in range(n):
        p = p0.lerp(p1, i / max(1, n - 1))
        res = bmesh.ops.create_uvsphere(bm, u_segments=6, v_segments=4, radius=r)
        bmesh.ops.translate(bm, vec=p, verts=res["verts"])
    return mesh_from_bm(name, bm, mat, parent, smooth_angle=80)


def join_children(parent_obj, name=None, render_only=False):
    """Merge direct mesh children flagged mergeable into a single mesh (per parent) for export."""
    kids = [c for c in parent_obj.children if c.type == "MESH" and not c.get("nomerge") and not c.children
            and (c.get("export", True) or render_only)]
    if len(kids) < 2:
        return kids[0] if kids else None
    ctx = bpy.context
    for o in ctx.selected_objects:
        o.select_set(False)
    for k in kids:
        k.select_set(True)
    ctx.view_layer.objects.active = kids[0]
    with ctx.temp_override(active_object=kids[0], selected_editable_objects=kids, selected_objects=kids):
        bpy.ops.object.join()
    o = kids[0]
    o.name = name or (parent_obj.name + "_vis")
    o.data.name = o.name
    return o


def auto_uv(obj, scale=1.0):
    """Box-projected UV (1 UV unit per metre / scale) in object space; keeps existing decal UVs."""
    if obj.get("keep_uv"):
        return
    me = obj.data
    bm = bmesh.new()
    bm.from_mesh(me)
    uv = bm.loops.layers.uv.get("uv0") or bm.loops.layers.uv.new("uv0")
    for f in bm.faces:
        n = f.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        for loop in f.loops:
            co = loop.vert.co
            if ax == 0:
                loop[uv].uv = (co.y * scale, co.z * scale)
            elif ax == 1:
                loop[uv].uv = (co.x * scale, co.z * scale)
            else:
                loop[uv].uv = (co.x * scale, co.y * scale)
    bm.to_mesh(me)
    bm.free()
