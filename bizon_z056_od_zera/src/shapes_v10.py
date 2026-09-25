"""GIANTS .i3d.shapes, file version 10 (Farming Simulator 25): writer and reader.

Container: 4 byte header [version, 0, seed, 0], then an encrypted stream.
Every logical write (entity count, entity type, entity size, entity blob) is
encrypted separately and consumes whole 64 byte keystream blocks, exactly like
the engine reads it.  The keystream is a 20-round Salsa-style core keyed by a
16 word table row selected by the seed; words 8/9 hold the block counter.
"""
import struct
import numpy as np

VERSION = 10
SEED = 106
# Key table row for SEED (engine constant, needed for interoperability).
_KEY = np.array([0xE1E3E3E3, 0xE1E0E0DF, 0xDEE2E2E2, 0xDFDEDFE1, 0xDDE0E0DF, 0xA3E7DEDE,
                 0x1F212128, 0xA694582C, 0x969AA0A4, 0x8A999E96, 0x586B6C79, 0x3D424E4F,
                 0x2F3B4442, 0x533F3730, 0x89857865, 0x8C878B8C], dtype=np.uint32)

OPT_NORMALS, OPT_UV1, OPT_UV2, OPT_UV3, OPT_UV4 = 0x1, 0x2, 0x4, 0x8, 0x10
OPT_COLOR, OPT_SKIN, OPT_TANGENTS, OPT_SINGLE_WEIGHTS, OPT_GENERIC = 0x20, 0x40, 0x80, 0x100, 0x200


def _rol(x, n):
    return (x << np.uint32(n)) | (x >> np.uint32(32 - n))


def _keystream(first_block, nblocks):
    blocks = np.arange(first_block, first_block + nblocks, dtype=np.uint64)
    k = np.tile(_KEY, (nblocks, 1))
    k[:, 8] = (blocks & np.uint64(0xFFFFFFFF)).astype(np.uint32)
    k[:, 9] = (blocks >> np.uint64(32)).astype(np.uint32)
    t = k.copy()

    def q1(a, b, c, d):
        t[:, c] ^= _rol(t[:, b] + t[:, a], 7)
        t[:, d] ^= _rol(t[:, c] + t[:, a], 9)
        t[:, b] ^= _rol(t[:, c] + t[:, d], 13)
        t[:, a] ^= _rol(t[:, b] + t[:, d], 18)   # ror 14 == rol 18

    def q2(a, b, c, d):
        t[:, c] ^= _rol(t[:, b] + t[:, a], 7)
        t[:, d] ^= _rol(t[:, b] + t[:, c], 9)
        t[:, a] ^= _rol(t[:, c] + t[:, d], 13)
        t[:, b] ^= _rol(t[:, d] + t[:, a], 18)

    with np.errstate(over='ignore'):
        for _ in range(10):
            q1(0x0, 0xC, 0x4, 0x8)
            q1(0x5, 0x1, 0x9, 0xD)
            q1(0xA, 0x6, 0xE, 0x2)
            q1(0xF, 0xB, 0x3, 0x7)
            q2(0x3, 0x0, 0x1, 0x2)
            q2(0x4, 0x5, 0x6, 0x7)
            q1(0xA, 0x9, 0xB, 0x8)
            q2(0xE, 0xF, 0xC, 0xD)
        out = (k + t).astype('<u4')
    return out.tobytes()


class _Cipher:
    def __init__(self):
        self.block = 0

    def process(self, data):
        n = len(data)
        nb = (n + 63) // 64
        ks = np.frombuffer(_keystream(self.block, nb), dtype=np.uint8)[:n]
        self.block += nb
        return (np.frombuffer(bytes(data), dtype=np.uint8) ^ ks).tobytes()


class _W:
    def __init__(self):
        self.b = bytearray()

    def u16(self, v): self.b += struct.pack('<H', v)
    def u32(self, v): self.b += struct.pack('<I', v)
    def i32(self, v): self.b += struct.pack('<i', v)
    def f32(self, *v): self.b += struct.pack('<%df' % len(v), *v)
    def raw(self, d): self.b += d

    def align(self, n):
        while len(self.b) % n:
            self.b.append(0)


def serialize_shape(s):
    """s: dict(name, id, bv(4), options, subsets[(fv,nv,fi,ni,[uvd..])], slot_names,
    indices(uint array), positions(N,3), normals, tangents(N,4), uvs[list of (N,2) or None]*4,
    colors(N,4), skin_weights(N,4), skin_indices(N,k uint8), generic(N), attachments[(flags,floats,data)],
    vtx_compression)."""
    w = _W()
    name = s['name'].encode('latin-1')
    w.i32(len(name)); w.raw(name); w.align(4); w.u32(s['id'])
    w.f32(*s['bv'])
    idx = np.asarray(s['indices']).ravel()
    pos = np.asarray(s['positions'], dtype='<f4')
    nv = len(pos)
    opt = s['options']
    w.u32(len(idx)); w.u32(len(s['subsets'])); w.u32(nv); w.u32(opt)
    w.f32(s.get('vtx_compression', 0.0))
    uv_flags = [OPT_UV1, OPT_UV2, OPT_UV3, OPT_UV4]
    for fv, snv, fi, ni, dens in s['subsets']:
        w.u32(fv); w.u32(snv); w.u32(fi); w.u32(ni)
        di = 0
        for f in uv_flags:
            if opt & f:
                w.f32(dens[di]); di += 1
    for nm in s.get('slot_names') or [''] * len(s['subsets']):
        e = nm.encode('latin-1'); w.u16(len(e)); w.raw(e); w.align(2)
    w.align(4)
    w.raw(idx.astype('<u4' if nv > 0x10000 else '<u2').tobytes())
    w.align(4)
    w.raw(pos.tobytes())
    if opt & OPT_NORMALS:
        w.raw(np.asarray(s['normals'], dtype='<f4').tobytes())
    if opt & OPT_TANGENTS:
        w.raw(np.asarray(s['tangents'], dtype='<f4').tobytes())
    for i, f in enumerate(uv_flags):
        if opt & f:
            w.raw(np.asarray(s['uvs'][i], dtype='<f4').tobytes())
    if opt & OPT_COLOR:
        w.raw(np.asarray(s['colors'], dtype='<f4').tobytes())
    if opt & OPT_SKIN:
        if not opt & OPT_SINGLE_WEIGHTS:
            w.raw(np.asarray(s['skin_weights'], dtype='<f4').tobytes())
        w.raw(np.asarray(s['skin_indices'], dtype=np.uint8).tobytes())
    if opt & OPT_GENERIC:
        w.raw(np.asarray(s['generic'], dtype='<f4').tobytes())
    if s.get('attachments') is not None:
        w.u32(len(s['attachments']))
        for flags, floats, data in s['attachments']:
            w.u32(flags)
            if flags & 4:
                w.f32(*floats)
            w.i32(len(data)); w.raw(data)
    return bytes(w.b)


def write_file(path, entities):
    """entities: list of (type_int, plaintext_bytes)."""
    c = _Cipher()
    out = bytearray([VERSION, 0, SEED, 0])
    out += c.process(struct.pack('<i', len(entities)))
    for t, data in entities:
        out += c.process(struct.pack('<i', t))
        out += c.process(struct.pack('<i', len(data)))
        out += c.process(data)
    with open(path, 'wb') as f:
        f.write(out)


def read_file(path):
    """Decrypt a v10 file written with SEED; returns list of (type, plaintext)."""
    raw = open(path, 'rb').read()
    assert raw[0] == VERSION and raw[2] == SEED, 'unexpected header %r' % raw[:4]
    c = _Cipher(); pos = 4

    def take(n):
        nonlocal pos
        d = c.process(raw[pos:pos + n]); pos += n
        return d
    ents = []
    for _ in range(struct.unpack('<i', take(4))[0]):
        t = struct.unpack('<i', take(4))[0]
        n = struct.unpack('<i', take(4))[0]
        ents.append((t, take(n)))
    assert pos == len(raw), 'trailing bytes'
    return ents


def parse_shape(data):
    """Inverse of serialize_shape (used for validation)."""
    p = 0

    def rd(fmt):
        nonlocal p
        v = struct.unpack_from('<' + fmt, data, p); p += struct.calcsize('<' + fmt)
        return v

    def al(n):
        nonlocal p
        p += (-p) % n
    s = {}
    ln, = rd('i'); s['name'] = data[p:p + ln].decode('latin-1'); p += ln; al(4)
    s['id'], = rd('I'); s['bv'] = rd('4f')
    ncorner, nsub, nv, opt = rd('4I'); s['options'] = opt
    s['vtx_compression'], = rd('f')
    uv_flags = [OPT_UV1, OPT_UV2, OPT_UV3, OPT_UV4]
    subs = []
    for _ in range(nsub):
        fv, snv, fi, ni = rd('4I')
        dens = [rd('f')[0] for f in uv_flags if opt & f]
        subs.append((fv, snv, fi, ni, dens))
    s['subsets'] = subs
    names = []
    for _ in range(nsub):
        n, = rd('H'); names.append(data[p:p + n].decode('latin-1')); p += n; al(2)
    al(4); s['slot_names'] = names
    it = '<u4' if nv > 0x10000 else '<u2'
    isz = 4 if nv > 0x10000 else 2
    s['indices'] = np.frombuffer(data, it, ncorner, p); p += ncorner * isz; al(4)

    def arr(k):
        nonlocal p
        a = np.frombuffer(data, '<f4', nv * k, p).reshape(nv, k); p += nv * k * 4
        return a
    s['positions'] = arr(3)
    if opt & OPT_NORMALS: s['normals'] = arr(3)
    if opt & OPT_TANGENTS: s['tangents'] = arr(4)
    s['uvs'] = [arr(2) if opt & f else None for f in uv_flags]
    if opt & OPT_COLOR: s['colors'] = arr(4)
    if opt & OPT_SKIN:
        if not opt & OPT_SINGLE_WEIGHTS: s['skin_weights'] = arr(4)
        k = 1 if opt & OPT_SINGLE_WEIGHTS else 4
        s['skin_indices'] = np.frombuffer(data, np.uint8, nv * k, p).reshape(nv, k); p += nv * k
    if opt & OPT_GENERIC: s['generic'] = arr(1).ravel()
    s['attachments'] = None
    if p + 4 <= len(data):
        na, = rd('I'); atts = []
        for _ in range(na):
            fl, = rd('I'); fs = rd('3f') if fl & 4 else None
            n, = rd('i'); atts.append((fl, fs, data[p:p + n])); p += n
        s['attachments'] = atts
    s['_unread'] = len(data) - p
    return s


# ---------------------------------------------------------------- collision data
def convex_attachment(points):
    """Precooked convex hull block ("cm" v4) as stored by GIANTS for rigid bodies:
    margin, volume, centre of mass, inertia per unit mass about the shape origin,
    and the hull vertices shrunk inwards by the margin."""
    from scipy.spatial import ConvexHull, HalfspaceIntersection
    P = np.asarray(points, dtype=np.float64)
    hull = ConvexHull(P)
    half = (P.max(0) - P.min(0)) / 2
    margin = float(min(0.04, 0.2 * half.min()))
    c0 = P[hull.vertices].mean(0)
    vol = 0.0; com = np.zeros(3); tets = []
    for simplex in hull.simplices:
        a, b, c = P[simplex]
        if np.dot(np.cross(b - a, c - a), a - c0) < 0:
            b, c = c, b
        v = np.dot(a - c0, np.cross(b - c0, c - c0)) / 6.0
        vol += v; com += v * (a + b + c + c0) / 4.0; tets.append((v, a, b, c))
    com /= vol
    cov = np.zeros((3, 3))
    for v, a, b, c in tets:
        q = np.array([c0, a, b, c]) - com
        sm = q.sum(0)
        cov += v / 20.0 * (np.outer(sm, sm) + sum(np.outer(x, x) for x in q))
    cov /= vol
    inertia = np.trace(cov) * np.eye(3) - cov          # about the centre of mass
    inertia += np.dot(com, com) * np.eye(3) - np.outer(com, com)   # moved to the origin
    eq = hull.equations.copy()
    eq[:, 3] += margin
    shrunk = HalfspaceIntersection(eq, c0).intersections
    uniq = []
    for x in shrunk:
        if all(np.linalg.norm(x - u) > 1e-5 for u in uniq):
            uniq.append(x)
    verts = np.array(uniq, dtype='<f4')
    blob = b'cm' + struct.pack('<HI', 4, len(verts))
    blob += struct.pack('<14f', margin, vol, *com, *inertia.ravel())
    blob += verts.tobytes()
    return (2, None, blob)
