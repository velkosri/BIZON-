"""Write FS25 .i3d + binary .i3d.shapes from the export_scene.py dump.

Collision shapes get the precooked convex block the engine expects, visual
shapes carry normals, tangents and one UV set.  Returns the node name -> index
path table used for <i3dMappings>."""
import json
import os
import numpy as np

import shapes_v10 as S

VEHICLE_GROUP, VEHICLE_MASK = '0x10004', '0xfe3ffb83'       # FS25 preset VEHICLE
FILL_GROUP, FILL_MASK = '0x40000000', '0x20000000'           # FS25 preset EXACT_FILL_ROOT_NODE


def fmt(v):
    return ' '.join(('%.6g' % x) for x in v)


def esc(s):
    return (str(s).replace('&', '&amp;').replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;'))


def build(dump_dir, coll, out_dir, base_name, tex_rel):
    data = json.load(open(os.path.join(dump_dir, coll + '.json')))
    arr = np.load(os.path.join(dump_dir, coll + '.npz'))
    # ---------------------------------------------------------------- files & materials
    files, file_ids = [], {}

    def fid(path):
        rel = tex_rel + '/' + os.path.splitext(os.path.basename(path))[0] + '.dds'
        if rel not in file_ids:
            file_ids[rel] = len(files) + 1
            files.append(rel)
        return file_ids[rel]
    mat_xml = []
    for i, m in enumerate(data['materials']):
        g = m['game']
        attrs = ['name="%s"' % esc(m['name']), 'materialId="%d"' % (i + 1)]
        inner = []
        tex = m['tex']
        smooth = 1.0 - m['rough']
        if tex.get('diffuse'):
            inner.append('<Texture fileId="%d"/>' % fid(tex['diffuse']))
        else:
            attrs.append('diffuseColor="%s"' % fmt(m['color'][:3] + [m['alpha'] if g.get('alpha') else 1.0]))
        if tex.get('normal'):
            inner.append('<Normalmap fileId="%d"/>' % fid(tex['normal']))
        if tex.get('specular'):
            inner.append('<Glossmap fileId="%d"/>' % fid(tex['specular']))
        else:
            attrs.append('specularColor="%s"' % fmt([smooth, 0.5, m['metal']]))
        if g.get('emissive'):
            attrs.append('emissiveColor="%s"' % fmt(m['color'][:3] + [1.0]))
        if g.get('alpha'):
            attrs.append('alphaBlending="true"')
        mat_xml.append('    <Material %s>%s</Material>' % (' '.join(attrs), ''.join(inner)) if inner else
                       '    <Material %s/>' % ' '.join(attrs))
    # ---------------------------------------------------------------- shapes
    entities = []
    for sid, sh in enumerate(data['shapes']):
        k = 's%d_' % sid
        pos, nrm, tan, uv, idx = arr[k + 'pos'], arr[k + 'nrm'], arr[k + 'tan'], arr[k + 'uv'], arr[k + 'idx']
        lo, hi = pos.min(0), pos.max(0)
        ctr = (lo + hi) / 2
        rad = float(np.linalg.norm(pos - ctr, axis=1).max())
        subsets = [(fv, nv, fi, ni, [d]) for (mi, fv, nv, fi, ni, d) in sh['subsets']]
        if sh['collision']:
            s = {'name': sh['name'] + 'Shape', 'id': sid + 1, 'bv': [*ctr, rad], 'options': S.OPT_NORMALS | S.OPT_UV1,
                 'subsets': subsets, 'slot_names': [''] * len(subsets), 'indices': idx, 'positions': pos, 'normals': nrm,
                 'uvs': [uv, None, None, None], 'attachments': [S.convex_attachment(pos[np.unique(idx)])]}
        else:
            s = {'name': sh['name'] + 'Shape', 'id': sid + 1, 'bv': [*ctr, rad],
                 'options': S.OPT_NORMALS | S.OPT_UV1 | S.OPT_TANGENTS, 'subsets': subsets,
                 'slot_names': [''] * len(subsets), 'indices': idx, 'positions': pos, 'normals': nrm, 'tangents': tan,
                 'uvs': [uv, None, None, None], 'attachments': []}
        entities.append((1, S.serialize_shape(s)))
    S.write_file(os.path.join(out_dir, base_name + '.i3d.shapes'), entities)
    # ---------------------------------------------------------------- scene
    mappings = {}
    lines = []
    counter = [0]

    def emit(n, depth, path):
        counter[0] += 1
        nid = counter[0]
        mappings[n['name']] = path
        pad = '  ' * depth
        a = ['name="%s"' % esc(n['name'])]
        if any(abs(x) > 1e-7 for x in n['t']):
            a.append('translation="%s"' % fmt(n['t']))
        if any(abs(x) > 1e-5 for x in n['r']):
            a.append('rotation="%s"' % fmt(n['r']))
        p = n.get('props', {})
        kind = n['kind']
        if kind == 'shape':
            sh = data['shapes'][n['shape']]
            a.append('shapeId="%d"' % (n['shape'] + 1))
            phys = n.get('phys')
            if phys == 'component':
                a += ['dynamic="true"', 'compound="true"', 'collisionFilterGroup="%s"' % VEHICLE_GROUP,
                      'collisionFilterMask="%s"' % VEHICLE_MASK]
            elif phys == 'child':
                a += ['compoundChild="true"', 'density="0.001"', 'collisionFilterGroup="%s"' % VEHICLE_GROUP,
                      'collisionFilterMask="%s"' % VEHICLE_MASK]
            elif phys == 'fill':
                a += ['kinematic="true"', 'compound="true"', 'collisionFilterGroup="%s"' % FILL_GROUP,
                      'collisionFilterMask="%s"' % FILL_MASK]
            elif phys == 'trigger':
                # FS25 preset FILL_TRIGGER: detects trailers (FILLABLE group) under the pipe
                a += ['kinematic="true"', 'compound="true"', 'trigger="true"', 'collisionFilterGroup="0x20000000"',
                      'collisionFilterMask="0x40000000"']
            mats = [str(s[0] + 1) for s in sh['subsets']]
            decal_only = all(data['materials'][s[0]]['game'].get('alpha') for s in sh['subsets'])
            a.append('castsShadows="%s"' % ('false' if (phys or decal_only) else 'true'))
            a.append('receiveShadows="%s"' % ('false' if phys else 'true'))
            if phys:
                a.append('nonRenderable="true"')
            a.append('materialIds="%s"' % ', '.join(mats))
            if phys == 'component':
                a.append('clipDistance="300"')
            tag = 'Shape'
        elif kind == 'light':
            typ = int(p.get('light_type', 0))
            col = {0: '0.85 0.85 0.8', 3: '0.85 0.85 0.8', 1: '0.9 0.9 0.85', 2: '0.9 0.9 0.85'}.get(typ, '1 1 1')
            a += ['type="spot"', 'color="%s"' % col, 'emitDiffuse="true"', 'emitSpecular="true"',
                  'range="%g"' % float(p.get('range', 30)), 'coneAngle="%g"' % float(p.get('cone', 60)), 'dropOff="3"',
                  'clipDistance="75"']
            tag = 'Light'
        elif kind == 'camera':
            a += ['fov="%g"' % float(p.get('fov', 60)), 'nearClip="%g"' % float(p.get('near', 0.3)),
                  'farClip="%g"' % float(p.get('far', 5000))]
            tag = 'Camera'
        else:
            tag = 'TransformGroup'
        if p.get('hidden'):
            a.append('visibility="false"')
        a.append('nodeId="%d"' % nid)
        kids = n['children']
        if kids:
            lines.append('%s<%s %s>' % (pad, tag, ' '.join(a)))
            for i, c in enumerate(kids):
                emit(c, depth + 1, (path + str(i)) if path.endswith('>') else '%s|%d' % (path, i))
            lines.append('%s</%s>' % (pad, tag))
        else:
            lines.append('%s<%s %s/>' % (pad, tag, ' '.join(a)))
    emit(data['root'], 2, '0>')
    xml = ['<?xml version="1.0" encoding="iso-8859-1"?>',
           '<i3D name="%s" version="1.6" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
           'xsi:noNamespaceSchemaLocation="http://i3d.giants.ch/schema/i3d-1.6.xsd">' % base_name,
           '  <Asset>', '    <Export program="bizon_z056_od_zera build_i3d.py" version="1.0"/>', '  </Asset>', '  <Files>']
    xml += ['    <File fileId="%d" filename="%s"/>' % (i + 1, f) for i, f in enumerate(files)]
    xml += ['  </Files>', '  <Materials>'] + mat_xml + ['  </Materials>',
                                                         '  <Shapes externalShapesFile="%s.i3d.shapes">' % base_name,
                                                         '  </Shapes>', '  <Scene>'] + lines + ['  </Scene>', '</i3D>', '']
    with open(os.path.join(out_dir, base_name + '.i3d'), 'w', encoding='iso-8859-1') as f:
        f.write('\n'.join(xml))
    return mappings, files, data
