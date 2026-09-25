#!/bin/sh
# Full rebuild: textures -> Blender model -> renders -> i3d/shapes -> FS25 mod zip.
# Usage: BLENDER=/path/to/blender sh build.sh [samples]
set -e
cd "$(dirname "$0")"
BLENDER=${BLENDER:-blender}
SAMPLES=${1:-160}
B=../build/z056
mkdir -p $B/tex $B/dump $B/sounds $B/img dist
python3 src/textures.py $B/tex
python3 src/real_sounds.py $B/snd_src $B/sounds
$BLENDER -b --factory-startup --python src/model.py -- $B/tex $B/bizon.blend
$BLENDER -b $B/bizon.blend --python src/export_scene.py -- $B/dump
for v in store_combine store_header; do
  $BLENDER -b $B/bizon.blend --python src/render.py -- $B/tex $B/img/$(echo $v | sed 's/store_combine/store_bizonZ056/;s/store_header/store_headerZ056/').png $v 48 1024 1024
done
for v in hero rear left cab; do
  $BLENDER -b $B/bizon.blend --python src/render.py -- $B/tex $B/img/render_$v.png $v $SAMPLES 1920 1080
done
python3 src/make_mod.py $B/dump $B/tex $B/sounds $B/img dist/FS25_Bizon_Z056_Super.zip
cp $B/img/render_*.png dist/
