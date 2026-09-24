#!/bin/sh
# Full rebuild: textures -> Blender model/export/renders -> XML + zip -> static validation.
set -e
OUT=${1:-build/final}
BLENDER=${BLENDER:-blender}
PY=${PY:-python3}
mkdir -p "$OUT"
$PY tools/make_textures.py "$OUT/textures"
BIZON_TEX="$OUT/textures" "$BLENDER" -b --python-exit-code 1 -P tools/build_blender.py -- "$OUT" final > "$OUT/blender.log" 2>&1
$PY tools/make_mod.py "$OUT"
$PY tools/validate_mod.py "$OUT/FS25_BizonSuperZ056.zip"
