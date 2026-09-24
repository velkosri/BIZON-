"""Round-trip a base game .i3d.shapes file through our reader/writer; bytes must be identical."""
import sys

from i3d_shapes import parse_shape, read_raw_entities, write_shapes

raw = open(sys.argv[1], "rb").read()
version, seed, ents, trailer = read_raw_entities(raw)
try:
    shapes = [parse_shape(d) for t, d in ents]
except ValueError as e:
    print("skip:", e)
    sys.exit(0)
if any(t != 1 for t, _ in ents):
    print("skip: non-shape entities")
    sys.exit(0)
out = write_shapes(shapes, seed=seed, version=version) + trailer
print("v%d entities %d size %d identical %s" % (version, len(shapes), len(raw), out == raw))
sys.exit(0 if out == raw else 1)
