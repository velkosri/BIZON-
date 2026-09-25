"""Byte-exact round trip of an original FS25 .i3d.shapes file through shapes_v10.

Usage: python test_shapes_roundtrip.py <file.i3d.shapes written with seed 106>
Checks the cipher/container, the shape layout and the precooked collision block.
"""
import sys
import os
import struct
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
import shapes_v10 as S

path = sys.argv[1]
ents = S.read_file(path)
tmp = path + '.roundtrip'
S.write_file(tmp, ents)
assert open(tmp, 'rb').read() == open(path, 'rb').read(), 'container round trip differs'
os.remove(tmp)
print('container round trip OK:', len(ents), 'entities')
bad = 0
for t, data in ents:
    s = S.parse_shape(data)
    again = S.serialize_shape(s)
    if again != data:
        bad += 1
        print('  layout mismatch', s['name'], len(again), len(data))
    for fl, fs, blob in s['attachments'] or []:
        if blob[:2] != b'cm':
            continue
        idx = s['indices'].reshape(-1, 3)
        used = s['positions'][np.unique(idx)]
        mine = S.convex_attachment(used)[2]
        a = np.frombuffer(blob[8:64], '<f4'); b = np.frombuffer(mine[8:64], '<f4')
        n0 = struct.unpack_from('<I', blob, 4)[0]; n1 = struct.unpack_from('<I', mine, 4)[0]
        va = np.frombuffer(blob[64:], '<f4').reshape(-1, 3); vb = np.frombuffer(mine[64:], '<f4').reshape(-1, 3)
        same_verts = all(np.min(np.linalg.norm(vb - x, axis=1)) < 2e-3 for x in va)
        ok = n0 == n1 and np.allclose(a, b, atol=2e-3, rtol=2e-3) and same_verts
        print('  collision %-28s verts %d/%d props %s hull %s' % (s['name'], n0, n1, 'OK' if np.allclose(a, b, atol=2e-3, rtol=2e-3) else 'DIFF', 'OK' if same_verts else 'DIFF'))
        bad += 0 if ok else 1
print('shape layout round trip:', 'OK' if not bad else '%d problems' % bad)
sys.exit(1 if bad else 0)
