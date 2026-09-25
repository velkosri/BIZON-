"""Cycles renders of the model.

Run: blender -b bizon.blend --python render.py -- <texdir> <out.png> <view> <samples> <width> <height>"""
import math
import os
import sys

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index('--') + 1:]
TEX, OUT, VIEW = argv[0], argv[1], argv[2]
SAMPLES, W, H = int(argv[3]), int(argv[4]), int(argv[5])
STORE = VIEW.startswith('store')

sc = bpy.context.scene
sc.render.engine = 'CYCLES'
sc.cycles.device = 'CPU'
sc.cycles.samples = SAMPLES
sc.cycles.use_denoising = True
sc.cycles.max_bounces = 8
sc.cycles.transparent_max_bounces = 16
sc.render.resolution_x, sc.render.resolution_y = W, H
sc.render.film_transparent = False
sc.view_settings.view_transform = 'AgX'
sc.view_settings.look = 'AgX - Punchy'
sc.view_settings.exposure = -0.35
sc.render.threads_mode = 'AUTO'

for ob in bpy.data.objects:
    if ob.get('col') or ob.get('hidden'):
        ob.hide_render = True
# changing flags while iterating all_objects invalidates it, so snapshot the list first
hide_coll = {'store_combine': 'header', 'store_header': 'combine'}.get(VIEW)
if hide_coll:
    for ob in [o for o in bpy.data.objects if hide_coll in {c.name for c in o.users_collection}]:
        ob.hide_render = True
sc.render.film_transparent = STORE

# ------------------------------------------------------------- sky and sun
world = bpy.data.worlds.new('sky')
sc.world = world
world.use_nodes = True
nt = world.node_tree
bg = nt.nodes['Background']
sky = nt.nodes.new('ShaderNodeTexSky')
sky.sky_type = 'NISHITA'
sun_el, sun_az = math.radians(24), math.radians({'rear': 40, 'left': 150}.get(VIEW, 115))
sky.sun_elevation = sun_el
sky.sun_rotation = sun_az
sky.altitude = 200
sky.air_density = 1.2
sky.dust_density = 2.5
nt.links.new(sky.outputs['Color'], bg.inputs['Color'])
bg.inputs['Strength'].default_value = 0.24
sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN'))
sc.collection.objects.link(sun)
sun.data.energy = 3.0
sun.data.angle = math.radians(0.8)
sun.data.color = (1.0, 0.93, 0.82)
sun.rotation_euler = (math.pi / 2 - sun_el, 0, sun_az + math.pi / 2)

# ------------------------------------------------------------- stubble field
bpy.ops.mesh.primitive_plane_add(size=400, location=(0, 1.5, 0))
ground = bpy.context.active_object
if STORE:
    ground.hide_render = True
m = bpy.data.materials.new('soil')
m.use_nodes = True
b = m.node_tree.nodes['Principled BSDF']
tc = m.node_tree.nodes.new('ShaderNodeTexCoord')
mp = m.node_tree.nodes.new('ShaderNodeMapping')
mp.inputs['Scale'].default_value = (1 / 3.0, 1 / 3.0, 1)
m.node_tree.links.new(tc.outputs['Object'], mp.inputs['Vector'])
for key, inp in (('diffuse', 'Base Color'), ('normal', None)):
    t = m.node_tree.nodes.new('ShaderNodeTexImage')
    t.image = bpy.data.images.load(os.path.join(TEX, 'render_soil_%s.png' % key))
    m.node_tree.links.new(mp.outputs['Vector'], t.inputs['Vector'])
    if inp:
        m.node_tree.links.new(t.outputs['Color'], b.inputs[inp])
    else:
        t.image.colorspace_settings.name = 'Non-Color'
        nm = m.node_tree.nodes.new('ShaderNodeNormalMap')
        nm.inputs['Strength'].default_value = 1.2
        m.node_tree.links.new(t.outputs['Color'], nm.inputs['Color'])
        m.node_tree.links.new(nm.outputs['Normal'], b.inputs['Normal'])
b.inputs['Roughness'].default_value = 0.95
ground.data.materials.append(m)
# the far ground gets its own, larger texture scale plus noise so tiling does not show
mf = m.copy()
mf.name = 'soil_far'
for nd in mf.node_tree.nodes:
    if nd.type == 'MAPPING':
        nd.inputs['Scale'].default_value = (1 / 13.0, 1 / 13.0, 1)
nz = mf.node_tree.nodes.new('ShaderNodeTexNoise')
nz.inputs['Scale'].default_value = 0.08
mix = mf.node_tree.nodes.new('ShaderNodeMix')
mix.data_type = 'RGBA'
mix.blend_type = 'MULTIPLY'
bf = mf.node_tree.nodes['Principled BSDF']
src = bf.inputs['Base Color'].links[0].from_socket
mf.node_tree.links.new(src, mix.inputs[6])
mf.node_tree.links.new(nz.outputs['Color'], mix.inputs[7])
mix.inputs['Factor'].default_value = 0.35
mf.node_tree.links.new(mix.outputs[2], bf.inputs['Base Color'])
ground.data.materials[0] = mf
# stubble only on a patch around the machine (dense, like real cut wheat)
bpy.ops.mesh.primitive_plane_add(size=48, location=(0, 1.5, 0.002))
patch = bpy.context.active_object
patch.data.materials.append(m)
if STORE:
    patch.hide_render = True
straw = bpy.data.materials.new('straw')
straw.use_nodes = True
sb = straw.node_tree.nodes['Principled BSDF']
sb.inputs['Base Color'].default_value = (0.55, 0.42, 0.2, 1)
sb.inputs['Roughness'].default_value = 0.55
sb.inputs['Subsurface Weight'].default_value = 0.15
hi = straw.node_tree.nodes.new('ShaderNodeHairInfo')
ramp = straw.node_tree.nodes.new('ShaderNodeValToRGB')
ramp.color_ramp.elements[0].color = (0.36, 0.26, 0.12, 1)
ramp.color_ramp.elements[1].color = (0.78, 0.62, 0.32, 1)
straw.node_tree.links.new(hi.outputs['Random'], ramp.inputs['Fac'])
straw.node_tree.links.new(ramp.outputs['Color'], sb.inputs['Base Color'])
patch.data.materials.append(straw)
ps = patch.modifiers.new('stubble', 'PARTICLE_SYSTEM').particle_system
st = ps.settings
st.type = 'HAIR'
st.count = 0 if STORE else (650000 if SAMPLES > 20 else 120000)
st.hair_length = 0.12
st.material = 2
st.use_advanced_hair = True
st.normal_factor = 0.12
st.factor_random = 0.04
st.brownian_factor = 0.006
st.length_random = 0.5
st.root_radius = 0.0036
st.tip_radius = 0.003
st.radius_scale = 1.0
st.display_step = 2
st.render_step = 2

# ------------------------------------------------------------- camera
views = {
    'hero': ((7.4, -8.6, 2.35), (0.0, 0.6, 1.75), 34),
    'rear': ((-6.8, 11.2, 3.1), (0.0, 1.9, 1.7), 36),
    'left': ((5.2, 1.4, 1.55), (0.9, 1.35, 1.45), 30),
    'cab': ((2.35, -2.35, 3.25), (0.35, -0.72, 2.45), 32),
    'front': ((0.4, -11.5, 2.2), (0.0, -1.0, 1.6), 36),
    'engine': ((-3.8, 3.4, 3.5), (-1.2, 2.3, 3.0), 30),
    'store_combine': ((8.4, -8.8, 3.6), (0.0, 1.2, 1.8), 36),
    'store_header': ((4.6, -7.6, 2.4), (0.0, -3.2, 0.55), 38),
}
pos, tgt, lens = views[VIEW]
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
sc.collection.objects.link(cam)
cam.location = pos
d = Vector(tgt) - Vector(pos)
cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
cam.data.lens = lens
cam.data.sensor_width = 36
cam.data.dof.use_dof = VIEW in ('cab', 'left')
cam.data.dof.focus_distance = d.length
cam.data.dof.aperture_fstop = 5.6
sc.camera = cam
sc.render.filepath = OUT
bpy.ops.render.render(write_still=True)
print('RENDERED', OUT)
