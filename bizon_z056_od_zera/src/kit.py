"""Geometry helpers for building the Bizon in Blender (bpy + bmesh).

Convention: Blender world, +X = vehicle left, -Y = forward, +Z = up.
Every mesh object keeps an identity transform; vertices are in world space.
Empties created with node() are the i3d TransformGroups (pivots)."""
import math
import bpy
import bmesh
from mathutils import Vector, Matrix, Euler

MATS = {}
CTX = {'parent': None, 'coll': None}
TAU = math.tau
# Blender (x, y, z) -> i3d (x, z, -y)
C_B2I = Matrix(((1, 0, 0), (0, 0, 1), (0, -1, 0)))


def i3d_euler_to_blender(rx, ry, rz):
    """Rotation given as i3d Euler degrees (extrinsic X, Y, Z) expressed in Blender axes."""
    ri = Euler((math.radians(rx), math.radians(ry), math.radians(rz)), 'XYZ').to_matrix()
    return C_B2I.transposed() @ ri @ C_B2I


def i3d_to_blender_vec(v):
    return C_B2I.transposed() @ Vector(v)


def v3(p):
    return Vector((float(p[0]), float(p[1]), float(p[2])))


def link(ob):
    (CTX['coll'] or bpy.context.scene.collection).objects.link(ob)


def node(name, loc=(0, 0, 0), parent=None, rot=None, **props):
    e = bpy.data.objects.new(name, None)
    e.empty_display_size = 0.08
    link(e)
    par = parent if parent is not None else CTX['parent']
    m = Matrix.Translation(v3(loc))
    if rot is not None:
        m = m @ (rot.to_4x4() if hasattr(rot, 'to_4x4') else rot)
    if par is not None:
        e.parent = par
        e.matrix_parent_inverse = Matrix()
        e.matrix_basis = par.matrix_world.inverted() @ m
    else:
        e.matrix_basis = m
    e['i3d'] = 'tg'
    for k, v in props.items():
        e[k] = v
    bpy.context.view_layer.update()
    return e


def aim_matrix(direction, up=(0, 0, 1)):
    """Rotation whose local +Y (= i3d -Z, the look/shine axis of GIANTS lights and
    cameras) points along `direction` and local +Z (= i3d +Y) is as close to `up`."""
    y = v3(direction).normalized()
    z = v3(up)
    x = y.cross(z)
    if x.length < 1e-6:
        x = Vector((1, 0, 0))
    x.normalize()
    z = x.cross(y).normalized()
    return Matrix((x, y, z)).transposed()


def finish(bm, name, mat, parent=None, smooth=35, keep_uv=False, **props):
    me = bpy.data.meshes.new(name)
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    if len(me.vertices) == 0:
        bpy.data.meshes.remove(me)
        return None
    ob = bpy.data.objects.new(name, me)
    link(ob)
    if isinstance(mat, str):
        mat = MATS[mat]
    me.materials.append(mat)
    if smooth:
        me.shade_smooth()
        me.set_sharp_from_angle(angle=math.radians(smooth))
    else:
        me.shade_flat()
    par = parent if parent is not None else CTX['parent']
    if par is not None:
        ob.parent = par
        ob.matrix_parent_inverse = par.matrix_world.inverted()
    if keep_uv:
        ob['keep_uv'] = 1
    for k, v in props.items():
        ob[k] = v
    return ob


class Mesh:
    """Accumulates geometry in one bmesh, then becomes one object."""

    def __init__(self):
        self.bm = bmesh.new()

    # ---------------------------------------------------------- primitives
    def box(self, c, s, bevel=0.0, seg=1, rot=None):
        m = Matrix.Translation(v3(c))
        if rot is not None:
            m = m @ rot.to_4x4()
        m = m @ Matrix.Diagonal((s[0], s[1], s[2], 1))
        vs = bmesh.ops.create_cube(self.bm, size=1.0, matrix=m)['verts']
        if bevel > 0:
            es = list({e for v in vs for e in v.link_edges})
            bmesh.ops.bevel(self.bm, geom=es, offset=bevel, segments=seg, affect='EDGES',
                            profile=0.5, clamp_overlap=True)
        return vs

    def boxp(self, p0, p1, bevel=0.0, seg=1):
        p0, p1 = v3(p0), v3(p1)
        return self.box((p0 + p1) / 2, [abs(a - b) for a, b in zip(p1, p0)], bevel, seg)

    def beam(self, p0, p1, w, h, bevel=0.004, up=(0, 0, 1)):
        """Rectangular section beam from p0 to p1 (w across, h along `up`)."""
        p0, p1 = v3(p0), v3(p1)
        d = p1 - p0
        y = d.normalized()
        z = v3(up)
        x = y.cross(z)
        if x.length < 1e-6:
            x = y.cross(Vector((1, 0, 0)))
        x.normalize()
        z = x.cross(y).normalized()
        rot = Matrix((x, y, z)).transposed()
        return self.box((p0 + p1) / 2, (w, d.length, h), bevel=bevel, rot=rot)

    def cyl(self, p0, p1, r, seg=16, cap=True, r2=None):
        p0, p1 = v3(p0), v3(p1)
        d = p1 - p0
        q = Vector((0, 0, 1)).rotation_difference(d.normalized())
        m = Matrix.Translation((p0 + p1) / 2) @ q.to_matrix().to_4x4()
        return bmesh.ops.create_cone(self.bm, cap_ends=cap, cap_tris=False, segments=seg,
                                     radius1=r, radius2=r if r2 is None else r2,
                                     depth=d.length, matrix=m)['verts']

    def sphere(self, c, r, seg=12, rings=8, scale=(1, 1, 1)):
        m = Matrix.Translation(v3(c)) @ Matrix.Diagonal((scale[0], scale[1], scale[2], 1))
        return bmesh.ops.create_uvsphere(self.bm, u_segments=seg, v_segments=rings, radius=r, matrix=m)['verts']

    def lathe(self, prof, seg, origin, axis=(0, 0, 1), cap0=False, cap1=False, phase=0.0):
        """prof: [(radius, height)] along axis."""
        ax = v3(axis).normalized()
        q = Vector((0, 0, 1)).rotation_difference(ax)
        m = Matrix.Translation(v3(origin)) @ q.to_matrix().to_4x4()
        bm = self.bm
        rings = []
        for r, h in prof:
            if r < 1e-6:
                rings.append([bm.verts.new(m @ Vector((0, 0, h)))])
                continue
            rings.append([bm.verts.new(m @ Vector((r * math.cos(phase + TAU * i / seg),
                                                   r * math.sin(phase + TAU * i / seg), h)))
                          for i in range(seg)])
        for a, b in zip(rings, rings[1:]):
            if len(a) == 1 and len(b) == 1:
                continue
            for i in range(seg):
                j = (i + 1) % seg
                if len(a) == 1:
                    bm.faces.new((a[0], b[i], b[j]))
                elif len(b) == 1:
                    bm.faces.new((a[i], b[0], a[j]))
                else:
                    bm.faces.new((a[i], b[i], b[j], a[j]))
        if cap0 and len(rings[0]) > 1:
            bm.faces.new(list(reversed(rings[0])))
        if cap1 and len(rings[-1]) > 1:
            bm.faces.new(rings[-1])
        return rings

    def tube(self, pts, r, seg=8, caps=True, twist_up=(0, 0, 1)):
        """Sweep a circle along a polyline (parallel transport frames)."""
        pts = [v3(p) for p in pts]
        n = len(pts)
        if n < 2:
            return
        tangents = []
        for i in range(n):
            if i == 0:
                t = pts[1] - pts[0]
            elif i == n - 1:
                t = pts[-1] - pts[-2]
            else:
                t = (pts[i + 1] - pts[i]).normalized() + (pts[i] - pts[i - 1]).normalized()
            tangents.append(t.normalized() if t.length > 1e-9 else Vector((0, 0, 1)))
        up = v3(twist_up)
        nrm = tangents[0].cross(up)
        if nrm.length < 1e-6:
            nrm = tangents[0].cross(Vector((1, 0, 0)))
        nrm.normalize()
        bm = self.bm
        rings = []
        for i in range(n):
            if i > 0:
                rot = tangents[i - 1].rotation_difference(tangents[i])
                nrm = (rot @ nrm).normalized()
            b = tangents[i].cross(nrm).normalized()
            rr = r[i] if isinstance(r, (list, tuple)) else r
            rings.append([bm.verts.new(pts[i] + rr * (math.cos(TAU * k / seg) * nrm + math.sin(TAU * k / seg) * b))
                          for k in range(seg)])
        for a, b in zip(rings, rings[1:]):
            for k in range(seg):
                l = (k + 1) % seg
                bm.faces.new((a[k], b[k], b[l], a[l]))
        if caps:
            bm.faces.new(list(reversed(rings[0])))
            bm.faces.new(rings[-1])

    def poly_prism(self, outline, p0, axis_u, axis_v, normal, thick, bevel=0.0):
        """Extrude a 2D outline [(u,v)] placed at p0 in plane (axis_u, axis_v)."""
        p0, au, av, nn = v3(p0), v3(axis_u), v3(axis_v), v3(normal).normalized()
        bm = self.bm
        bot = [bm.verts.new(p0 + u * au + v * av) for u, v in outline]
        top = [bm.verts.new(x.co + nn * thick) for x in bot]
        f0 = bm.faces.new(list(reversed(bot)))
        f1 = bm.faces.new(top)
        k = len(bot)
        for i in range(k):
            j = (i + 1) % k
            bm.faces.new((bot[i], bot[j], top[j], top[i]))
        if bevel > 0:
            es = list({e for v in bot + top for e in v.link_edges})
            bmesh.ops.bevel(bm, geom=es, offset=bevel, segments=1, affect='EDGES', clamp_overlap=True)
        return bot, top

    def hull(self, pts):
        vs = [self.bm.verts.new(v3(p)) for p in pts]
        bmesh.ops.convex_hull(self.bm, input=vs)

    def done(self, name, mat, **kw):
        bmesh.ops.recalc_face_normals(self.bm, faces=self.bm.faces)
        return finish(self.bm, name, mat, **kw)

    def done_raw(self, name, mat, **kw):
        return finish(self.bm, name, mat, **kw)


# ------------------------------------------------------------------ curves
def catmull(points, per=6):
    pts = [v3(p) for p in points]
    if len(pts) < 3:
        a, b = pts
        return [a.lerp(b, i / per) for i in range(per + 1)]
    out = []
    ext = [pts[0] * 2 - pts[1]] + pts + [pts[-1] * 2 - pts[-2]]
    for i in range(1, len(ext) - 2):
        p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
        for s in range(per):
            t = s / per
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(pts[-1])
    return out


def sag(p0, p1, depth, n=10):
    p0, p1 = v3(p0), v3(p1)
    return [p0.lerp(p1, i / n) - Vector((0, 0, depth * 4 * (i / n) * (1 - i / n))) for i in range(n + 1)]


def belt_outline(c1, r1, c2, r2, n=14):
    """Open-belt path around two pulleys in the YZ plane (centres (y,z))."""
    (y1, z1), (y2, z2) = c1, c2
    dx, dz = y2 - y1, z2 - z1
    d = math.hypot(dx, dz)
    base = math.atan2(dz, dx)
    a = math.acos(max(-1, min(1, (r1 - r2) / d)))
    pts = []
    # arc on pulley 1 from base+a to base+2pi-a (the far side)
    for i in range(n + 1):
        t = base + a + (TAU - 2 * a) * i / n
        pts.append((y1 + r1 * math.cos(t), z1 + r1 * math.sin(t)))
    for i in range(n + 1):
        t = base - a + 2 * a * i / n
        pts.append((y2 + r2 * math.cos(t), z2 + r2 * math.sin(t)))
    return pts


# ---------------------------------------------------------------- materials
def make_material(name, tex=None, color=(0.5, 0.5, 0.5, 1), rough=0.5, metal=0.0,
                  alpha=1.0, emission=None, transmission=0.0, ior=1.45, normal_strength=1.0,
                  game=None):
    """tex: dict(diffuse=path, normal=path, specular=path) with specular R=smoothness,
    G=metallic.  `game` carries i3d material hints for the exporter."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes['Principled BSDF']
    out = nt.nodes['Material Output']
    b.inputs['Base Color'].default_value = color
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    b.inputs['Alpha'].default_value = alpha
    b.inputs['IOR'].default_value = ior
    if transmission:
        b.inputs['Transmission Weight'].default_value = transmission
    if emission:
        b.inputs['Emission Color'].default_value = emission[:3] + (1,)
        b.inputs['Emission Strength'].default_value = emission[3] if len(emission) > 3 else 5.0
    uv = nt.nodes.new('ShaderNodeUVMap')
    if tex:
        if tex.get('diffuse'):
            t = nt.nodes.new('ShaderNodeTexImage')
            t.image = bpy.data.images.load(tex['diffuse'], check_existing=True)
            nt.links.new(uv.outputs['UV'], t.inputs['Vector'])
            nt.links.new(t.outputs['Color'], b.inputs['Base Color'])
            if alpha < 1.0 or tex.get('alpha'):
                nt.links.new(t.outputs['Alpha'], b.inputs['Alpha'])
        if tex.get('specular'):
            t = nt.nodes.new('ShaderNodeTexImage')
            t.image = bpy.data.images.load(tex['specular'], check_existing=True)
            t.image.colorspace_settings.name = 'Non-Color'
            nt.links.new(uv.outputs['UV'], t.inputs['Vector'])
            sep = nt.nodes.new('ShaderNodeSeparateColor')
            nt.links.new(t.outputs['Color'], sep.inputs['Color'])
            inv = nt.nodes.new('ShaderNodeMath')
            inv.operation = 'SUBTRACT'
            inv.inputs[0].default_value = 1.0
            nt.links.new(sep.outputs['Red'], inv.inputs[1])
            nt.links.new(inv.outputs['Value'], b.inputs['Roughness'])
            nt.links.new(sep.outputs['Blue'], b.inputs['Metallic'])
        if tex.get('normal'):
            t = nt.nodes.new('ShaderNodeTexImage')
            t.image = bpy.data.images.load(tex['normal'], check_existing=True)
            t.image.colorspace_settings.name = 'Non-Color'
            nt.links.new(uv.outputs['UV'], t.inputs['Vector'])
            nm = nt.nodes.new('ShaderNodeNormalMap')
            nm.inputs['Strength'].default_value = normal_strength
            nt.links.new(t.outputs['Color'], nm.inputs['Color'])
            nt.links.new(nm.outputs['Normal'], b.inputs['Normal'])
    if alpha < 1.0 or (tex and tex.get('alpha')):
        m.surface_render_method = 'BLENDED' if alpha < 0.99 else 'DITHERED'
    m['game'] = dict(game or {})
    m['game_color'] = list(color)
    m['game_rough'] = rough
    m['game_metal'] = metal
    m['game_alpha'] = alpha
    if tex:
        m['game_tex'] = {k: v for k, v in tex.items() if isinstance(v, str)}
    MATS[name] = m
    return m


def box_uv(ob, tile=1.5):
    """World-space box projection, 1 UV = `tile` metres (tileable textures)."""
    me = ob.data
    bm = bmesh.new()
    bm.from_mesh(me)
    uvl = bm.loops.layers.uv.verify()
    mw = ob.matrix_world
    rot = mw.to_3x3()
    for f in bm.faces:
        n = rot @ f.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        for lp in f.loops:
            c = mw @ lp.vert.co
            if ax == 0:
                u, v = c.y * (1 if n.x > 0 else -1), c.z
            elif ax == 1:
                u, v = c.x * (-1 if n.y > 0 else 1), c.z
            else:
                u, v = c.x, c.y * (1 if n.z > 0 else -1)
            lp[uvl].uv = (u / tile, v / tile)
    bm.to_mesh(me)
    bm.free()


def rect_uv(ob, rect, axis_u, axis_v, origin, size):
    """Planar mapping of a decal onto an atlas rectangle (u0,v0,u1,v1)."""
    me = ob.data
    bm = bmesh.new()
    bm.from_mesh(me)
    uvl = bm.loops.layers.uv.verify()
    au, av, o = v3(axis_u), v3(axis_v), v3(origin)
    u0, v0, u1, v1 = rect
    for f in bm.faces:
        for lp in f.loops:
            d = lp.vert.co - o
            s = d.dot(au) / size[0] + 0.5
            t = d.dot(av) / size[1] + 0.5
            lp[uvl].uv = (u0 + (u1 - u0) * s, v0 + (v1 - v0) * t)
    bm.to_mesh(me)
    bm.free()
    ob['keep_uv'] = 1


def cyl_uv(ob, rect, origin, axis, height, phase=0.0):
    """Wrap a cylindrical label: u = angle, v = along axis."""
    me = ob.data
    bm = bmesh.new()
    bm.from_mesh(me)
    uvl = bm.loops.layers.uv.verify()
    o, ax = v3(origin), v3(axis).normalized()
    ref = ax.orthogonal().normalized()
    ref2 = ax.cross(ref)
    u0, v0, u1, v1 = rect
    for f in bm.faces:
        angs = []
        for lp in f.loops:
            d = lp.vert.co - o
            angs.append(math.atan2(d.dot(ref2), d.dot(ref)))
        if max(angs) - min(angs) > math.pi:
            angs = [a + TAU if a < 0 else a for a in angs]
        for lp, a in zip(f.loops, angs):
            d = lp.vert.co - o
            s = ((a + phase) / TAU) % 1.0 if max(angs) < TAU else (a + phase) / TAU
            t = d.dot(ax) / height + 0.5
            lp[uvl].uv = (u0 + (u1 - u0) * s, v0 + (v1 - v0) * t)
    bm.to_mesh(me)
    bm.free()
    ob['keep_uv'] = 1
