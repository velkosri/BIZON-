"""Static checks for the built mod zip (no game required).

- every XML/i3d is well formed
- every i3dMapping path resolves to a node with that exact name in the i3d scene
- every node referenced by an XML attribute has an i3dMapping
- every mod-relative file referenced from XML/i3d exists in the zip
- .i3d.shapes decode and every <Shape shapeId> exists in the shapes file
"""
import io
import os
import re
import sys
import xml.etree.ElementTree as ET
import zipfile

sys.path.insert(0, os.path.dirname(__file__))
from i3d_shapes import parse_shape, read_raw_entities  # noqa: E402

NODE_ATTRS = {"node", "repr", "driveNode", "linkNode", "rotateNode", "targetNode", "referencePoint",
              "referenceFrame", "effectNode", "startNode", "widthNode", "heightNode", "leftNode", "rightNode",
              "backNode"}


def scene_lookup(root, path):
    rootidx, _, rest = path.partition(">")
    scene = root.find("Scene")
    nodes = [n for n in scene]
    n = nodes[int(rootidx)]
    for part in [p for p in rest.split("|") if p != ""]:
        n = [c for c in n if c.tag in ("TransformGroup", "Shape", "Light", "Camera", "ReferenceNode")][int(part)]
    return n


def main(zpath):
    z = zipfile.ZipFile(zpath)
    names = set(z.namelist())
    errors, checks = [], 0

    def xml(name):
        return ET.fromstring(z.read(name))

    desc = xml("modDesc.xml")
    for si in desc.iter("storeItem"):
        vpath = si.get("xmlFilename")
        v = xml(vpath)
        vdir = os.path.dirname(vpath)
        i3d_path = v.find("base/filename").text
        i3d = xml(i3d_path)
        idir = os.path.dirname(i3d_path)
        maps = {m.get("id"): m.get("node") for m in v.iter("i3dMapping")}
        for mid, p in maps.items():
            checks += 1
            try:
                n = scene_lookup(i3d, p)
                if n.get("name") != mid:
                    errors.append("%s: mapping %s -> %s points to '%s'" % (vpath, mid, p, n.get("name")))
            except (IndexError, ValueError) as e:
                errors.append("%s: mapping %s -> %s unresolved (%s)" % (vpath, mid, p, e))
        for el in v.iter():
            for a in NODE_ATTRS & set(el.attrib):
                val = el.get(a)
                for tok in val.split():
                    if el.tag in ("physics",) or a in ("node", "linkNode") or True:
                        checks += 1
                        if tok not in maps and not re.match(r"^\d+>", tok):
                            errors.append("%s: <%s %s='%s'> has no i3dMapping" % (vpath, el.tag, a, tok))
        # files referenced with mod-relative paths
        refs = [v.find("storeData/image").text, i3d_path]
        snd = v.find("base/sounds")
        if snd is not None:
            refs.append(snd.get("filename"))
            if snd.get("filename") in names:
                for el in xml(snd.get("filename")).iter():
                    ln = el.get("linkNode")
                    if ln:
                        checks += 1
                        if ln not in maps:
                            errors.append("%s: sound linkNode '%s' has no i3dMapping" % (snd.get("filename"), ln))
                    fn = el.get("file")
                    if fn and not fn.startswith("$data"):
                        checks += 1
                        if fn not in names:
                            errors.append("%s: missing sound file %s" % (snd.get("filename"), fn))
        for r in refs:
            checks += 1
            if r not in names:
                errors.append("%s: missing file %s" % (vpath, r))
        for f in i3d.iter("File"):
            fn = f.get("filename")
            if fn.startswith("$data"):
                continue
            full = os.path.normpath(os.path.join(idir, fn)).replace("\\", "/")
            checks += 1
            if full not in names:
                errors.append("%s: missing i3d file %s" % (i3d_path, full))
        shapes_file = os.path.join(idir, i3d.find("Shapes").get("externalShapesFile"))
        _, _, ents, _ = read_raw_entities(z.read(shapes_file))
        ids = {parse_shape(d).id for _, d in ents}
        for s in i3d.iter("Shape"):
            checks += 1
            if int(s.get("shapeId")) not in ids:
                errors.append("%s: shapeId %s missing in shapes" % (i3d_path, s.get("shapeId")))
        mats = {m.get("materialId") for m in i3d.iter("Material")}
        for s in i3d.iter("Shape"):
            for mid in s.get("materialIds").split(","):
                checks += 1
                if mid not in mats:
                    errors.append("%s: material %s missing" % (i3d_path, mid))
        print("%-45s mappings=%d shapes=%d" % (vpath, len(maps), len(ids)))
    for fn in ("icon_bizonSuperZ056.dds", "brand_bizon.dds"):
        checks += 1
        if fn not in names:
            errors.append("missing " + fn)
    print("checks: %d, errors: %d" % (checks, len(errors)))
    for e in errors:
        print("  ERROR", e)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
