"""Dump the Blender scene into a neutral format for build_i3d.py.

Run: blender -b bizon.blend --python export_scene.py -- <outdir>
For every vehicle collection writes <collection>.json (node tree, materials) and
<collection>.npz (vertex/index buffers, already in i3d axes: x, z, -y).
Static meshes below an empty are merged into one shape per empty (one subset per
material); meshes flagged `own` or `col` stay separate shape nodes."""
import json
import math
import os
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Matrix

OUT = sys.argv[sys.argv.index('--') + 1]
os.makedirs(OUT, exist_ok=True)
C4 = Matrix(((1, 0, 0, 0), (0, 0, 1, 0), (0, -1, 0, 0), (0, 0, 0, 1)))


def i3d_local(parent_mw, mw):
    local = C4 @ (parent_mw.inverted() @ mw) @ C4.transposed()
    t, q, s = local.decompose()
    e = q.to_matrix().to_euler('XYZ')
    return [round(x, 6) for x in t], [round(math.degrees(a), 5) for a in e]


def mesh_buffers(ob, node_mw):
    """Triangulated loops of `ob` expressed in the node frame, i3d axes."""
    me = ob.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    tmp = bpy.data.meshes.new('_tmp')
    bm.to_mesh(tmp)
    bm.free()
    nl = len(tmp.loops)
    if nl == 0:
        bpy.data.meshes.remove(tmp)
        return None
    has_uv = len(tmp.uv_layers) > 0
    if has_uv:
        tmp.calc_tangents(uvmap=tmp.uv_layers[0].name)
    vidx = np.zeros(nl, np.int64)
    tmp.loops.foreach_get('vertex_index', vidx)
    co = np.zeros(len(tmp.vertices) * 3)
    tmp.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)[vidx]
    nrm = np.zeros(nl * 3)
    tmp.corner_normals.foreach_get('vector', nrm)
    nrm = nrm.reshape(-1, 3)
    uv = np.zeros(nl * 2)
    tan = np.zeros(nl * 3)
    sign = np.ones(nl)
    if has_uv:
        tmp.uv_layers[0].data.foreach_get('uv', uv)
        tmp.loops.foreach_get('tangent', tan)
        tmp.loops.foreach_get('bitangent_sign', sign)
    uv = uv.reshape(-1, 2)
    tan = tan.reshape(-1, 3)
    bpy.data.meshes.remove(tmp)
    m = C4 @ node_mw.inverted() @ ob.matrix_world
    r = np.array(m.to_3x3())
    t = np.array(m.translation)
    pos = co @ r.T + t
    nrm = nrm @ r.T
    nrm /= np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-9)
    tan = tan @ r.T
    tl = np.linalg.norm(tan, axis=1, keepdims=True)
    tan = np.where(tl > 1e-9, tan / np.maximum(tl, 1e-9), np.array([1.0, 0, 0]))
    return pos, nrm, np.hstack([tan, sign[:, None]]), uv


def weld(pos, nrm, tan, uv):
    key = np.hstack([np.round(pos * 2e4), np.round(nrm * 500), np.round(uv * 4e4)]).astype(np.int64)
    _, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
    return pos[first], nrm[first], tan[first], uv[first], inv.ravel()


class Exporter:
    def __init__(self, coll):
        self.coll = coll
        self.materials = []
        self.mat_index = {}
        self.shapes = []
        self.arrays = {}

    def mat(self, m):
        if m.name not in self.mat_index:
            self.mat_index[m.name] = len(self.materials)
            self.materials.append({
                'name': m.name,
                'tex': dict(m.get('game_tex', {})),
                'color': list(m.get('game_color', [0.5, 0.5, 0.5, 1])),
                'rough': float(m.get('game_rough', 0.5)),
                'metal': float(m.get('game_metal', 0.0)),
                'alpha': float(m.get('game_alpha', 1.0)),
                'game': {k: (v if not hasattr(v, 'to_dict') else v.to_dict()) for k, v in dict(m.get('game', {})).items()},
            })
        return self.mat_index[m.name]

    def add_shape(self, name, objs, node_mw, collision=False):
        per_mat = {}
        for ob in objs:
            b = mesh_buffers(ob, node_mw)
            if b is None:
                continue
            mi = self.mat(ob.data.materials[0]) if ob.data.materials else 0
            per_mat.setdefault(mi, []).append(b)
        if not per_mat:
            return None
        P, N, Tn, U, I, subsets = [], [], [], [], [], []
        vbase = ibase = 0
        for mi in sorted(per_mat):
            pos = np.vstack([b[0] for b in per_mat[mi]])
            nrm = np.vstack([b[1] for b in per_mat[mi]])
            tan = np.vstack([b[2] for b in per_mat[mi]])
            uv = np.vstack([b[3] for b in per_mat[mi]])
            p, n, t, u, inv = weld(pos, nrm, tan, uv)
            tri = inv.reshape(-1, 3)
            # uv density: median texel ratio per triangle (texture streaming hint)
            a, b_, c = pos[0::3], pos[1::3], pos[2::3]
            wa = np.linalg.norm(np.cross(b_ - a, c - a), axis=1) / 2
            ua, ub, uc = uv[0::3], uv[1::3], uv[2::3]
            d1, d2 = ub - ua, uc - ua
            uva = np.abs(d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0]) / 2
            ok = (wa > 1e-10) & (uva > 1e-12)
            dens = float(np.clip(np.median(np.sqrt(uva[ok] / wa[ok])) if ok.any() else 1.0, 1e-3, 1.0))
            subsets.append([mi, vbase, len(p), ibase, tri.size, dens])
            P.append(p); N.append(n); Tn.append(t); U.append(u); I.append(tri.ravel() + vbase)
            vbase += len(p)
            ibase += tri.size
        sid = len(self.shapes)
        key = 's%d_' % sid
        self.arrays[key + 'pos'] = np.vstack(P).astype(np.float32)
        self.arrays[key + 'nrm'] = np.vstack(N).astype(np.float32)
        self.arrays[key + 'tan'] = np.vstack(Tn).astype(np.float32)
        self.arrays[key + 'uv'] = np.vstack(U).astype(np.float32)
        self.arrays[key + 'idx'] = np.concatenate(I).astype(np.uint32)
        self.shapes.append({'name': name, 'subsets': subsets, 'collision': collision})
        return sid

    def build_node(self, ob, parent_mw):
        t, r = i3d_local(parent_mw, ob.matrix_world)
        props = {k: ob[k] for k in ob.keys() if isinstance(ob[k], (int, float, str))}
        n = {'name': ob.name, 'kind': props.get('i3d_kind', 'tg'), 't': t, 'r': r, 'props': props, 'children': []}
        kids = [c for c in ob.children if c.name in self.coll.all_objects]
        meshes = [c for c in kids if c.type == 'MESH']
        empties = sorted([c for c in kids if c.type == 'EMPTY'], key=lambda c: c.name)
        mw = ob.matrix_world
        if props.get('i3d_component'):
            main = [c for c in meshes if c.get('col') == 'main']
            n['kind'] = 'shape'
            n['shape'] = self.add_shape(ob.name, main, mw, collision=True)
            n['phys'] = 'component'
        vis = [c for c in meshes if not c.get('own') and not c.get('col')]
        if vis:
            sid = self.add_shape(ob.name + '_vis', vis, mw)
            if sid is not None:
                n['children'].append({'name': ob.name + '_vis', 'kind': 'shape', 'shape': sid, 't': [0, 0, 0], 'r': [0, 0, 0],
                                      'props': {}, 'children': []})
        for c in sorted([c for c in meshes if c.get('own')], key=lambda c: c.name):
            sid = self.add_shape(c.name, [c], mw)
            n['children'].append({'name': c.name, 'kind': 'shape', 'shape': sid, 't': [0, 0, 0], 'r': [0, 0, 0],
                                  'props': {k: c[k] for k in c.keys() if isinstance(c[k], (int, float, str))}, 'children': []})
        for c in sorted([c for c in meshes if c.get('col') in ('child', 'fill')], key=lambda c: c.name):
            sid = self.add_shape(c.name, [c], mw, collision=True)
            n['children'].append({'name': c.name, 'kind': 'shape', 'shape': sid, 't': [0, 0, 0], 'r': [0, 0, 0],
                                  'props': {}, 'phys': c['col'], 'children': []})
        for e in empties:
            n['children'].append(self.build_node(e, mw))
        return n

    def run(self):
        roots = [o for o in self.coll.objects if o.get('i3d_component')]
        assert len(roots) == 1, roots
        tree = self.build_node(roots[0], Matrix())
        name = self.coll.name
        with open(os.path.join(OUT, name + '.json'), 'w') as f:
            json.dump({'name': name, 'materials': self.materials, 'shapes': self.shapes, 'root': tree}, f, indent=1)
        np.savez_compressed(os.path.join(OUT, name + '.npz'), **self.arrays)
        tris = sum(int(self.arrays['s%d_idx' % i].size // 3) for i in range(len(self.shapes)))
        print('EXPORTED', name, 'shapes', len(self.shapes), 'materials', len(self.materials), 'triangles', tris)


for coll in bpy.data.collections:
    if coll.name in ('combine', 'header'):
        Exporter(coll).run()
