"""Reader/writer for GIANTS Engine binary .i3d.shapes files (file version 10, FS25).

Container layout: 4 byte header [version, 0, seed, 0] followed by a stream that
is XOR-ciphered per read call (the block counter advances by ceil(n/64) per call),
so writing must mirror the engine's read sequence exactly.
"""
import struct

import numpy as np

from shapes_cipher_keys import KEY_CONST

OPT_NORMALS = 0x01
OPT_UV1 = 0x02
OPT_COLOR = 0x20
OPT_SKIN = 0x40
OPT_TANGENTS = 0x80
OPT_GENERIC = 0x200


class Cipher:
    def __init__(self, seed):
        k = list(KEY_CONST[(seed << 4):(seed << 4) + 16])
        k[8] = k[9] = 0
        self.key = np.asarray(k, dtype=np.uint32)

    @staticmethod
    def _rol(v, b):
        return (v << np.uint32(b)) | (v >> np.uint32(32 - b))

    @staticmethod
    def _ror(v, b):
        return (v >> np.uint32(b)) | (v << np.uint32(32 - b))

    def process(self, data, block_index):
        """Returns (ciphered bytes, next block index). Symmetric."""
        n = len(data)
        nblocks = (n + 63) // 64
        padded = bytes(data) + b"\0" * (nblocks * 64 - n)
        buf = np.frombuffer(padded, dtype="<u4").copy().reshape(nblocks, 16)
        ctr = np.uint64(block_index) + np.arange(nblocks, dtype=np.uint64)
        key = np.tile(self.key, (nblocks, 1))
        key[:, 8] = (ctr & np.uint64(0xFFFFFFFF)).astype(np.uint32)
        key[:, 9] = (ctr >> np.uint64(32)).astype(np.uint32)
        t = key.copy()
        rol, ror = self._rol, self._ror
        with np.errstate(over="ignore"):
            def s1(a, b, c, d):
                t[:, c] ^= rol(t[:, b] + t[:, a], 7)
                t[:, d] ^= rol(t[:, c] + t[:, a], 9)
                t[:, b] ^= rol(t[:, c] + t[:, d], 13)
                t[:, a] ^= ror(t[:, b] + t[:, d], 14)

            def s2(a, b, c, d):
                t[:, c] ^= rol(t[:, b] + t[:, a], 7)
                t[:, d] ^= rol(t[:, b] + t[:, c], 9)
                t[:, a] ^= rol(t[:, c] + t[:, d], 13)
                t[:, b] ^= ror(t[:, d] + t[:, a], 14)

            for _ in range(10):
                s1(0x0, 0xC, 0x4, 0x8)
                s1(0x5, 0x1, 0x9, 0xD)
                s1(0xA, 0x6, 0xE, 0x2)
                s1(0xF, 0xB, 0x3, 0x7)
                s2(0x3, 0x0, 0x1, 0x2)
                s2(0x4, 0x5, 0x6, 0x7)
                s1(0xA, 0x9, 0xB, 0x8)
                s2(0xE, 0xF, 0xC, 0xD)
            buf ^= key + t
        return buf.reshape(-1).tobytes()[:n], block_index + nblocks


class Shape:
    """Plain (non-skinned) mesh. positions/normals: (N,3), tangents: (N,4), uvs: list of (N,2),
    indices: flat triangle list, subsets: (first_vertex, num_vertices, first_index, num_indices)."""

    def __init__(self, name, shape_id, positions, indices, normals=None, tangents=None,
                 uvs=(), subsets=None, uv_densities=None, slot_names=None, options_high=0,
                 vtx_compression=0.0, raw_tail=b"\0\0\0\0", colors=None):
        self.name = name
        self.id = shape_id
        self.positions = np.asarray(positions, dtype="<f4").reshape(-1, 3)
        self.indices = np.asarray(indices).reshape(-1)
        self.normals = None if normals is None else np.asarray(normals, dtype="<f4").reshape(-1, 3)
        self.tangents = None if tangents is None else np.asarray(tangents, dtype="<f4").reshape(-1, 4)
        self.colors = None if colors is None else np.asarray(colors, dtype="<f4").reshape(-1, 4)
        self.uvs = [np.asarray(u, dtype="<f4").reshape(-1, 2) for u in uvs]
        self.subsets = subsets or [(0, len(self.positions), 0, len(self.indices))]
        self.uv_densities = uv_densities
        self.slot_names = slot_names or [""] * len(self.subsets)
        self.options_high = options_high
        self.vtx_compression = vtx_compression
        # attachment count + attachments; default none (engine cooks collision hulls itself)
        self.raw_tail = raw_tail
        self.bounding = None

    def options(self):
        o = 0
        if self.normals is not None:
            o |= OPT_NORMALS
        for i in range(len(self.uvs)):
            o |= OPT_UV1 << i
        if self.colors is not None:
            o |= OPT_COLOR
        if self.tangents is not None:
            o |= OPT_TANGENTS
        return o | self.options_high

    def bounding_sphere(self):
        if self.bounding is not None:
            return self.bounding
        p = self.positions.astype(np.float64)
        c = (p.min(0) + p.max(0)) / 2
        r = float(np.sqrt(((p - c) ** 2).sum(1)).max())
        return (float(c[0]), float(c[1]), float(c[2]), r)

    def serialize(self):
        out = bytearray()

        def align(n):
            while len(out) % n:
                out.append(0)

        name = self.name.encode("ascii", "replace")
        out += struct.pack("<i", len(name)) + name
        align(4)
        nv = len(self.positions)
        out += struct.pack("<I", self.id)
        out += struct.pack("<4f", *self.bounding_sphere())
        out += struct.pack("<IIII", len(self.indices), len(self.subsets), nv, self.options())
        out += struct.pack("<f", self.vtx_compression)
        for si, (fv, snv, fi, ni) in enumerate(self.subsets):
            out += struct.pack("<IIII", fv, snv, fi, ni)
            for ui in range(len(self.uvs)):
                out += struct.pack("<f", self.uv_densities[si][ui] if self.uv_densities else 1.0)
        for sn in self.slot_names:
            b = sn.encode("ascii")
            out += struct.pack("<H", len(b)) + b
            align(2)
        align(4)
        out += self.indices.astype("<u4" if nv > 0x10000 else "<u2").tobytes()
        align(4)
        out += self.positions.tobytes()
        if self.normals is not None:
            out += self.normals.tobytes()
        if self.tangents is not None:
            out += self.tangents.tobytes()
        for u in self.uvs:
            out += u.tobytes()
        if self.colors is not None:
            out += self.colors.tobytes()
        out += self.raw_tail
        return bytes(out)


def write_shapes(shapes, seed=77, version=10):
    cipher = Cipher(seed)
    out = bytearray([version, 0, seed, 0])
    block = 0

    def put(b):
        nonlocal block
        enc, block = cipher.process(b, block)
        out.extend(enc)

    put(struct.pack("<i", len(shapes)))
    for s in shapes:
        data = s.serialize()
        put(struct.pack("<i", 1))
        put(struct.pack("<i", len(data)))
        put(data)
    return bytes(out)


def read_raw_entities(raw):
    """Decrypt a shapes file into (version, seed, [(type, data)], trailing bytes)."""
    version, seed = raw[0], raw[2]
    cipher = Cipher(seed)
    pos, block = 4, 0

    def get(n):
        nonlocal pos, block
        dec, block = cipher.process(raw[pos:pos + n], block)
        pos += n
        return dec

    count = struct.unpack("<i", get(4))[0]
    ents = []
    for _ in range(count):
        t = struct.unpack("<i", get(4))[0]
        size = struct.unpack("<i", get(4))[0]
        ents.append((t, get(size)))
    return version, seed, ents, raw[pos:]


def parse_shape(data):
    """Parse a v10 non-skinned shape entity back into a Shape (used for verification)."""
    p = 0

    def rd(fmt):
        nonlocal p
        v = struct.unpack_from(fmt, data, p)
        p += struct.calcsize(fmt)
        return v

    def align(n):
        nonlocal p
        p += (-p) % n

    (nl,) = rd("<i")
    name = data[p:p + nl].decode("latin-1")
    p += nl
    align(4)
    (sid,) = rd("<I")
    bound = rd("<4f")
    corners, nsub, nv, opts = rd("<IIII")
    (vc,) = rd("<f")
    nuv = sum(1 for i in range(4) if opts & (OPT_UV1 << i))
    subsets, dens = [], []
    for _ in range(nsub):
        subsets.append(rd("<IIII"))
        dens.append(rd("<%df" % nuv) if nuv else ())
    names = []
    for _ in range(nsub):
        (n,) = rd("<H")
        names.append(data[p:p + n].decode("latin-1"))
        p += n
        align(2)
    align(4)
    isz = 4 if nv > 0x10000 else 2
    idx = np.frombuffer(data, dtype="<u4" if isz == 4 else "<u2", count=corners, offset=p)
    p += corners * isz
    align(4)

    def arr(k):
        nonlocal p
        a = np.frombuffer(data, dtype="<f4", count=nv * k, offset=p).reshape(nv, k)
        p += nv * k * 4
        return a

    if opts & (OPT_SKIN | OPT_GENERIC):
        raise ValueError("skinned/generic shapes not supported")
    pos = arr(3)
    nrm = arr(3) if opts & OPT_NORMALS else None
    tan = arr(4) if opts & OPT_TANGENTS else None
    uvs = [arr(2) for i in range(4) if opts & (OPT_UV1 << i)]
    col = arr(4) if opts & OPT_COLOR else None
    s = Shape(name, sid, pos, idx, nrm, tan, uvs, subsets, dens, names,
              opts & ~0x3FF, vc, data[p:], col)
    s.bounding = bound
    return s
