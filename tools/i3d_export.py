"""Blender -> GIANTS i3d (XML scene) + binary .i3d.shapes exporter for the Bizon build.

Axis conversion Blender (X right, Y fwd, Z up) -> GIANTS (X left, Y up, Z fwd): g = (-x, z, y),
a proper rotation, so winding and tangent handedness are preserved.
"""
import math
import os
import sys
from xml.sax.saxutils import quoteattr

import bmesh
import bpy
import numpy as np
from mathutils import Matrix

sys.path.insert(0, os.path.dirname(__file__))
from i3d_shapes import OPT_CPU_MESH, Shape, box_collision_attachment, write_shapes  # noqa: E402

C = Matrix(((-1, 0, 0, 0), (0, 0, 1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))
CI = C.inverted()

COL_GROUP = "0x10004"
COL_MASK = "0xfffffbff"

SHARED = {
    "white": "$data/shared/white_diffuse.png",
    "normal": "$data/shared/default_normal.png",
    "vmask": "$data/shared/default_vmask.png",
    "shader": "$data/shaders/vehicleShader.xml",
}


def fmt(v):
    s = "%.6g" % v
    return "0" if s in ("-0", "0") else s


def g_matrix(m):
    return C @ m @ CI


def g_euler_deg(m):
    """GIANTS XYZ euler (degrees) of a Blender rotation/matrix."""
    e = g_matrix(m.to_4x4()).to_euler("XYZ")
    return tuple(math.degrees(a) for a in e)


def to_g(arr):
    """(N,3) blender -> giants axes."""
    out = np.empty_like(arr)
    out[:, 0] = -arr[:, 0]
    out[:, 1] = arr[:, 2]
    out[:, 2] = arr[:, 1]
    return out


def make_twosided(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    uv = bm.loops.layers.uv.get("uv0")
    faces = list(bm.faces)
    for f in faces:
        vs = [bm.verts.new(v.co) for v in reversed(f.verts)]
        nf = bm.faces.new(vs)
        nf.material_index = f.material_index
        if uv:
            for nl, ol in zip(nf.loops, reversed(f.loops)):
                nl[uv].uv = ol[uv].uv
    bm.to_mesh(obj.data)
    bm.free()


class Exporter:
    def __init__(self, out_dir, name, local_files=None):
        self.out_dir = out_dir
        self.name = name
        self.files = {}
        self.materials = {}
        self.mat_xml = []
        self.shapes = []
        self.node_id = 1
        self.mappings = {}
        self.lines = []
        self.local_files = local_files or {}

    # ------------------------------------------------------------ files/materials
    def file_id(self, path):
        if path not in self.files:
            self.files[path] = len(self.files) + 1
        return self.files[path]

    def material_id(self, mat):
        key = mat.name if mat else "__default"
        if key in self.materials:
            return self.materials[key]
        mid = len(self.materials) + 1
        self.materials[key] = mid
        kind = mat.get("fs_kind", "vehicle") if mat else "default"
        name = quoteattr(key + "_mat")
        if kind == "vehicle" and mat.name != "inv":
            det = __import__("blender_kit").DETAIL[mat["fs_detail"]]
            col = mat["fs_color"]
            x = ['    <Material name=%s materialId="%d" customShaderId="%d">' % (name, mid, self.file_id(SHARED["shader"])),
                 '      <Texture fileId="%d"/>' % self.file_id(SHARED["white"]),
                 '      <Normalmap fileId="%d"/>' % self.file_id(SHARED["normal"]),
                 '      <Glossmap fileId="%d"/>' % self.file_id(SHARED["vmask"]),
                 '      <Custommap name="detailSpecular" fileId="%d"/>' % self.file_id(det[1]),
                 '      <Custommap name="detailNormal" fileId="%d"/>' % self.file_id(det[2]),
                 '      <Custommap name="detailDiffuse" fileId="%d"/>' % self.file_id(det[0]),
                 '      <CustomParameter name="colorScale" value="%s %s %s"/>' % tuple(fmt(c) for c in col)]
            params = mat.get("fs_params")
            for k in ("smoothnessScale", "clearCoatIntensity", "clearCoatSmoothness"):
                if params and k in params:
                    x.append('      <CustomParameter name="%s" value="%s"/>' % (k, fmt(params[k])))
            x.append('    </Material>')
        elif kind == "glass":
            col = mat["fs_color"]
            x = ['    <Material name=%s materialId="%d" diffuseColor="%s %s %s %s" specularColor="1 1 1" alphaBlending="true">'
                 % (name, mid, fmt(col[0]), fmt(col[1]), fmt(col[2]), fmt(mat["fs_alpha"])),
                 '      <Normalmap fileId="%d"/>' % self.file_id(SHARED["normal"]),
                 '    </Material>']
        elif kind == "decal":
            x = ['    <Material name=%s materialId="%d" alphaBlending="true">' % (name, mid),
                 '      <Texture fileId="%d"/>' % self.file_id(self.local_files["decals"]),
                 '      <Normalmap fileId="%d"/>' % self.file_id(SHARED["normal"]),
                 '    </Material>']
        else:
            x = ['    <Material name=%s materialId="%d" diffuseColor="0.5 0.5 0.5 1"/>' % (name, mid)]
        self.mat_xml += x
        return mid

    # ------------------------------------------------------------ meshes
    def mesh_shape(self, obj, render=True):
        dg = bpy.context.evaluated_depsgraph_get()
        me = bpy.data.meshes.new_from_object(obj.evaluated_get(dg))
        bm = bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.triangulate(bm, faces=bm.faces)
        bm.to_mesh(me)
        bm.free()
        has_uv = "uv0" in me.uv_layers
        if not has_uv:
            me.uv_layers.new(name="uv0")
        uv1_name = "uv1" if "uv1" in me.uv_layers else "uv0"
        me.calc_tangents(uvmap="uv0")
        nl = len(me.loops)
        vco = np.empty(len(me.vertices) * 3, np.float32)
        me.vertices.foreach_get("co", vco)
        vco = vco.reshape(-1, 3)
        vidx = np.empty(nl, np.int32)
        me.loops.foreach_get("vertex_index", vidx)
        nrm = np.empty(nl * 3, np.float32)
        me.loops.foreach_get("normal", nrm)
        tan = np.empty(nl * 3, np.float32)
        me.loops.foreach_get("tangent", tan)
        bsign = np.empty(nl, np.float32)
        me.loops.foreach_get("bitangent_sign", bsign)
        uv0 = np.empty(nl * 2, np.float32)
        me.uv_layers["uv0"].data.foreach_get("uv", uv0)
        uv1 = np.empty(nl * 2, np.float32)
        me.uv_layers[uv1_name].data.foreach_get("uv", uv1)
        npoly = len(me.polygons)
        mat_idx = np.empty(npoly, np.int32)
        me.polygons.foreach_get("material_index", mat_idx)
        loop_start = np.empty(npoly, np.int32)
        me.polygons.foreach_get("loop_start", loop_start)
        mats = [m for m in me.materials]
        bpy.data.meshes.remove(me)

        pos = to_g(vco[vidx])
        nrm = to_g(nrm.reshape(-1, 3))
        tan = to_g(tan.reshape(-1, 3))
        # GIANTS/Mikk tangent w; mirrored UVs keep their sign
        tan4 = np.concatenate([tan, bsign[:, None]], 1)
        uv0 = uv0.reshape(-1, 2)
        uv1 = uv1.reshape(-1, 2)
        tri_loops = loop_start[:, None] + np.arange(3)[None, :]

        vbufs = {k: [] for k in ("pos", "nrm", "tan", "uv0", "uv1")}
        indices, subsets, mat_ids = [], [], []
        vbase = 0
        ibase = 0
        for mi in sorted(set(mat_idx.tolist())):
            tris = tri_loops[mat_idx == mi].reshape(-1)
            attr = np.concatenate([pos[tris], nrm[tris], tan4[tris], uv0[tris], uv1[tris]], 1)
            key = np.round(attr, 5)
            uniq, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
            inv = inv.reshape(-1)
            a = attr[first]
            vbufs["pos"].append(a[:, 0:3])
            vbufs["nrm"].append(a[:, 3:6])
            vbufs["tan"].append(a[:, 6:10])
            vbufs["uv0"].append(a[:, 10:12])
            vbufs["uv1"].append(a[:, 12:14])
            indices.append(inv + vbase)
            subsets.append((vbase, len(a), ibase, len(inv)))
            vbase += len(a)
            ibase += len(inv)
            m = mats[mi] if mi < len(mats) else None
            mat_ids.append(self.material_id(m))
        cat = {k: np.concatenate(v) for k, v in vbufs.items()}
        idx = np.concatenate(indices)
        sid = len(self.shapes) + 1
        if render:
            shape = Shape(obj.name + "Shape", sid, cat["pos"], idx, cat["nrm"], cat["tan"],
                          [cat["uv0"], cat["uv1"]], subsets)
        else:
            shape = Shape(obj.name + "Shape", sid, cat["pos"], idx, cat["nrm"], None, [cat["uv0"]], subsets)
        kind = obj.get("kind", "")
        if kind in ("col_root", "col", "trigger", "exactfill"):
            shape.raw_tail = box_collision_attachment(cat["pos"])
        elif kind == "fillvol":
            shape.options_high |= OPT_CPU_MESH
        self.shapes.append(shape)
        return sid, ",".join(str(m) for m in mat_ids), len(idx) // 3

    # ------------------------------------------------------------ scene graph
    def transform_attrs(self, obj, is_root):
        m = obj.matrix_world if is_root else obj.matrix_local
        loc, rot, sca = g_matrix(m).decompose()
        eul = rot.to_euler("XYZ")
        t = " ".join(fmt(v) for v in loc)
        r = " ".join(fmt(math.degrees(a)) for a in eul)
        if obj.get("g_trans"):
            t = obj["g_trans"]
        if obj.get("g_rot"):
            r = obj["g_rot"]
        s = ""
        if any(abs(v - 1) > 1e-4 for v in sca):
            s = ' scale="%s"' % " ".join(fmt(v) for v in (sca[0], sca[1], sca[2]))
        out = ""
        if t != "0 0 0":
            out += ' translation="%s"' % t
        if r != "0 0 0":
            out += ' rotation="%s"' % r
        return out + s

    def node(self, obj, path, depth, is_root=False):
        if not obj.get("export", True):
            return
        self.mappings[obj.name] = path
        ind = "  " * (depth + 2)
        nid = self.node_id
        self.node_id += 1
        tr = self.transform_attrs(obj, is_root)
        name = quoteattr(obj.name)
        kids = [c for c in sorted(obj.children, key=lambda o: o.get("order", 0)) if c.get("export", True)]
        kind = obj.get("kind", "")
        if obj.type == "MESH":
            render = kind in ("", "effect")
            sid, mids, ntri = self.mesh_shape(obj, render=render)
            attrs = ""
            if kind == "col_root":
                attrs = (' dynamic="true" compound="true" collisionFilterGroup="%s" collisionFilterMask="%s"'
                         ' clipDistance="300" nonRenderable="true"' % (COL_GROUP, COL_MASK))
            elif kind == "col":
                attrs = (' compoundChild="true" collisionFilterGroup="%s" collisionFilterMask="%s" density="0.001"'
                         ' nonRenderable="true"' % (COL_GROUP, COL_MASK))
            elif kind == "trigger":
                attrs = (' kinematic="true" compound="true" trigger="true" collisionFilterGroup="0x20000000"'
                         ' collisionFilterMask="0x40000000" nonRenderable="true"')
            elif kind == "exactfill":
                attrs = (' kinematic="true" compound="true" collisionFilterGroup="0x40000000"'
                         ' collisionFilterMask="0x20000000" nonRenderable="true"')
            elif kind == "fillvol":
                attrs = ' clipDistance="300" nonRenderable="true"'
            elif kind == "effect":
                attrs = ' clipDistance="100"'
            else:
                clip = obj.get("clip", 300 if ntri > 200 else 120)
                attrs = ' clipDistance="%d"' % clip
            head = '%s<Shape name=%s%s shapeId="%d"%s nodeId="%d" castsShadows="true" receiveShadows="true" materialIds="%s"' % (
                ind, name, tr, sid, attrs, nid, mids)
        elif kind == "camera":
            head = '%s<Camera name=%s%s nodeId="%d" fov="%s" nearClip="%s" farClip="5000" orthographicHeight="1"' % (
                ind, name, tr, nid, fmt(obj.get("fov", 60)), fmt(obj.get("near", 0.3)))
        elif kind == "light":
            head = ('%s<Light name=%s%s clipDistance="75" nodeId="%d" type="spot" color="%s" emitDiffuse="true"'
                    ' emitSpecular="true" range="%s" coneAngle="%s" dropOff="3"') % (
                ind, name, tr, nid, obj["color"], fmt(obj["range"]), fmt(obj["cone"]))
        else:
            head = '%s<TransformGroup name=%s%s nodeId="%d"' % (ind, name, tr, nid)
        tag = {"MESH": "Shape"}.get(obj.type, {"camera": "Camera", "light": "Light"}.get(kind, "TransformGroup"))
        if not kids:
            self.lines.append(head + "/>")
            return
        self.lines.append(head + ">")
        for i, c in enumerate(kids):
            cp = path + ("|" if not path.endswith(">") else "") + str(i)
            self.node(c, cp, depth + 1)
        self.lines.append("%s</%s>" % (ind, tag))

    def export(self, roots):
        for i, r in enumerate(roots):
            self.node(r, "%d>" % i, 0, is_root=True)
        shapes_name = self.name + ".i3d.shapes"
        with open(os.path.join(self.out_dir, shapes_name), "wb") as f:
            f.write(write_shapes(self.shapes, seed=77))
        out = ['<?xml version="1.0" encoding="iso-8859-1"?>', "",
               '<i3D name="%s.i3d" version="1.6" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
               'xsi:noNamespaceSchemaLocation="http://i3d.giants.ch/schema/i3d-1.6.xsd">' % self.name,
               "  <Asset>", '    <Export program="Bizon build (Blender %s)" version="1.0"/>' % bpy.app.version_string,
               "  </Asset>", "", "  <Files>"]
        for p, fid in sorted(self.files.items(), key=lambda kv: kv[1]):
            out.append('    <File fileId="%d" filename=%s/>' % (fid, quoteattr(p)))
        out += ["  </Files>", "", "  <Materials>"] + self.mat_xml + ["  </Materials>", "",
                                                                        '  <Shapes externalShapesFile="%s">' % shapes_name,
                                                                        "  </Shapes>", "", "  <Scene>"]
        out += self.lines
        out += ["  </Scene>", "", "</i3D>", ""]
        with open(os.path.join(self.out_dir, self.name + ".i3d"), "w", encoding="iso-8859-1") as f:
            f.write("\n".join(out))
        tris = sum(len(s.indices) // 3 for s in self.shapes)
        return {"mappings": self.mappings, "shapes": len(self.shapes), "tris": tris, "materials": len(self.materials)}


def prepare_for_export(root):
    """Auto UVs, two-sided glass, then merge static mesh leaves per parent node."""
    import blender_kit as K
    objs = [root] + list(root.children_recursive)
    for o in objs:
        if o.type == "MESH" and o.get("export", True):
            K.auto_uv(o)
            if o.get("twosided"):
                make_twosided(o)
    names = [o.name for o in objs if o.get("export", True) and o.type in ("EMPTY", "MESH")]
    for n in names:
        p = bpy.data.objects.get(n)
        if p is not None:
            K.join_children(p)
