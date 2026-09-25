"""Assemble the FS25 mod: i3d/shapes, vehicle XMLs, modDesc, DDS textures, icons,
sounds, then validate node references and zip it.

Usage: python make_mod.py <dumpdir> <texdir> <sounddir> <imagesdir> <outzip>"""
import json
import os
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_i3d  # noqa: E402

DUMP, TEX, SND, IMG, OUTZIP = sys.argv[1:6]
MOD = 'FS25_Bizon_Z056_Super'
STAGE = os.path.join(os.path.dirname(os.path.abspath(DUMP)), 'stage', MOD)
shutil.rmtree(STAGE, ignore_errors=True)
os.makedirs(os.path.join(STAGE, 'textures'))
os.makedirs(os.path.join(STAGE, 'sounds'))


def find(node, name):
    if node['name'] == name:
        return node
    for c in node['children']:
        r = find(c, name)
        if r:
            return r
    return None


def fv(v):
    return ' '.join('%.4g' % x for x in v)


# ------------------------------------------------------------------ i3d
maps_c, files_c, dump_c = build_i3d.build(DUMP, 'combine', STAGE, 'bizonZ056', 'textures')
maps_h, files_h, dump_h = build_i3d.build(DUMP, 'header', STAGE, 'headerZ056', 'textures')

# ------------------------------------------------------------------ textures -> DDS
alpha_tex = {'decals_diffuse'}
for rel in sorted(set(files_c + files_h)):
    name = os.path.splitext(os.path.basename(rel))[0]
    src = os.path.join(TEX, name + '.png')
    comp = 'dxt5' if name in alpha_tex else 'dxt1'
    subprocess.run(['convert', src, '-define', 'dds:compression=%s' % comp, '-define', 'dds:mipmaps=8',
                    os.path.join(STAGE, rel)], check=True)


def to_dds(src, dst, size, comp='dxt5'):
    subprocess.run(['convert', src, '-resize', '%dx%d' % size, '-background', 'none', '-gravity', 'center', '-extent',
                    '%dx%d' % size, '-define', 'dds:compression=%s' % comp, '-define', 'dds:mipmaps=0', dst], check=True)


# brand logo from the decal atlas, mod icon from the hero render (square crop)
atlas = json.load(open(os.path.join(TEX, 'atlas.json')))
dec = Image.open(os.path.join(TEX, 'decals_diffuse.png'))
u0, v0, u1, v1 = atlas['bizon']
W, H = dec.size
dec.crop((int(u0 * W), int((1 - v1) * H), int(u1 * W), int((1 - v0) * H))).save(os.path.join(IMG, 'brand_bizon.png'))
hero = Image.open(os.path.join(IMG, 'render_hero.png')).convert('RGB')
hw_, hh_ = hero.size
side = min(hw_, hh_)
hero.crop(((hw_ - side) // 2, 0, (hw_ + side) // 2, side)).resize((512, 512), Image.LANCZOS).save(os.path.join(IMG, 'icon_mod.png'))
to_dds(os.path.join(IMG, 'store_bizonZ056.png'), os.path.join(STAGE, 'store_bizonZ056.dds'), (512, 512))
to_dds(os.path.join(IMG, 'store_headerZ056.png'), os.path.join(STAGE, 'store_headerZ056.dds'), (512, 512))
to_dds(os.path.join(IMG, 'icon_mod.png'), os.path.join(STAGE, 'icon_bizonZ056.dds'), (512, 512), comp='dxt1')
to_dds(os.path.join(IMG, 'brand_bizon.png'), os.path.join(STAGE, 'brand_bizon.dds'), (512, 256))
for f in os.listdir(SND):
    if f.endswith('.ogg'):
        shutil.copy(os.path.join(SND, f), os.path.join(STAGE, 'sounds', f))


def mappings_xml(maps, used):
    out = ['    <i3dMappings>']
    for name in sorted(used, key=lambda n: maps[n]):
        out.append('        <i3dMapping id="%s" node="%s"/>' % (name, maps[name]))
    out.append('    </i3dMappings>')
    return '\n'.join(out)


def mods(lst):
    return ''.join('<modifier type="MOTOR_RPM_REAL" value="%g" modifiedValue="%g"/>' % p for p in lst or [])


def sound(tag, f, offset, inner=3, outer=70, vol=1.0, indoor=0.6, loops=0, fade='', vmods=None, pmods=None):
    # loops="0" = endless; without it a sample plays once and goes silent
    s = '<%s file="sounds/%s" linkNodeOffset="%s" innerRadius="%g" outerRadius="%g" volumeScale="%g" loops="%d"%s>' % (
        tag, f, offset, inner, outer, vol, loops, (' ' + fade) if fade else '')
    s += '<volume indoor="%g" outdoor="1">%s</volume>' % (indoor, mods(vmods))
    if pmods:
        s += '<pitch indoor="1" outdoor="1">%s</pitch>' % mods(pmods)
    return s + '</%s>' % tag


def anim_node(name, speed, axis=1, on=1.5, off=2.5):
    return '<animationNode node="%s" rotSpeed="%g" rotAxis="%d" turnOnFadeTime="%g" turnOffFadeTime="%g"/>' % (
        name, speed, axis, on, off)


# ------------------------------------------------------------------ combine XML
root_c = dump_c['root']
walker_parts = []
crank_r, period, steps = 0.045, 0.36, 8
import math  # noqa: E402
for i in range(1, 6):
    n = find(root_c, 'walker%d' % i)
    t0 = n['t']
    phase = 0 if i % 2 else math.pi
    for s in range(steps):
        a0 = phase + 2 * math.pi * s / steps
        a1 = phase + 2 * math.pi * (s + 1) / steps
        p0 = [t0[0], t0[1] + crank_r * math.sin(a0), t0[2] + crank_r * math.cos(a0)]
        p1 = [t0[0], t0[1] + crank_r * math.sin(a1), t0[2] + crank_r * math.cos(a1)]
        walker_parts.append('<part node="walker%d" startTime="%.4f" endTime="%.4f" startTrans="%s" endTrans="%s"/>' % (
            i, period * s / steps, period * (s + 1) / steps, fv(p0), fv(p1)))
pulleys_left = ['engPulley', 'counterBig', 'counterSmall', 'drumVariator', 'beater', 'drumSmall', 'fan', 'counterFan', 'sieve',
                'fanSmall', 'walkerCrank', 'counterWalker', 'augerBottom']
speed_of = {}


def collect_speeds(n):
    if 'anim_speed' in n.get('props', {}):
        speed_of[n['name']] = n['props']['anim_speed']
    for c in n['children']:
        collect_speeds(c)


collect_speeds(root_c)
thresh_nodes = [anim_node(k, -1500 * v, 1) for k, v in sorted(speed_of.items()) if k.startswith(('pl_', 'pr_'))]
thresh_nodes.append(anim_node('feederSprocket', -700, 1))
motor_nodes = [anim_node('rotaryScreen', 160, 1, 1.0, 3.0),
               anim_node('engineShakeA', 7200, 3, 0.6, 0.8), anim_node('engineShakeB', -7200, 3, 0.6, 0.8),
               anim_node('engineShakeC', 6600, 3, 0.6, 0.8), anim_node('engineShakeD', -6600, 3, 0.6, 0.8)]

used_c = set()


def U(name):
    assert name in maps_c, 'missing node ' + name
    used_c.add(name)
    return name


wheel_xml = []
for nm, left, fr in (('wheelFL', True, True), ('wheelFR', False, True), ('wheelRL', True, False), ('wheelRR', False, False)):
    if fr:
        phys = ('<physics repr="%s" driveNode="%s_drive" radius="0.745" width="0.47" mass="0.38" restLoad="3.0" '
                'suspTravel="0.08" initialCompression="40" spring="92" damper="37" forcePointRatio="0.35" '
                'rotSpeed="0" brakeFactor="1" frictionScale="1.2" tireType="mud"/>') % (U(nm), nm)
    else:
        phys = ('<physics repr="%s" driveNode="%s_drive" radius="0.43" width="0.26" mass="0.12" restLoad="0.9" '
                'suspTravel="0.08" initialCompression="40" spring="28" damper="11" forcePointRatio="0.3" '
                'rotSpeed="1" brakeFactor="0" frictionScale="1.0" tireType="mud"/>') % (U(nm), nm)
    U(nm + '_drive')
    wheel_xml.append('<wheel isLeft="%s" hasTireTracks="true" hasParticles="true">%s</wheel>' % (
        'true' if left else 'false', phys))

for n in ('steeringWheel', 'outdoorCamera', 'outdoorCameraTarget', 'indoorCamera', 'cameraRaycastNode1', 'cameraRaycastNode2',
          'cameraRaycastNode3', 'playerSkin', 'leftHandTarget', 'rightHandTarget', 'leftFootTarget', 'rightFootTarget', 'exitPoint',
          'enterReferenceNode', 'frontLightLow', 'highBeam', 'workLightFront', 'workLightBack', 'pipeLight', 'lit_front',
          'lit_work_front', 'lit_work_rear', 'lit_tail_L', 'lit_tail_R', 'lit_brake', 'lit_turn_front_L', 'lit_turn_rear_L',
          'lit_turn_front_R', 'lit_turn_rear_R', 'attacherJointCutter', 'feederHouse', 'exactFillRootNodeFuel', 'pipeNode',
          'pipeUnloadingTrigger', 'dischargeNode', 'exhaustFlap', 'exhaustNode', 'swathAreaStart', 'swathAreaWidth',
          'swathAreaHeight', 'chopperAreaStart',
          'chopperAreaWidth', 'chopperAreaHeight', 'rotaryScreen', 'engineShakeA', 'engineShakeB', 'engineShakeC', 'engineShakeD',
          'feederSprocket', 'needle_rpm', 'needle_speed', 'liftCylL', 'liftCylR', 'liftRodL', 'liftRodR', 'liftRodRefL',
          'liftRodRefR', 'bizonZ056_main_component') + tuple('walker%d' % i for i in range(1, 6)) + tuple(speed_of):
    U(n)

combine_xml = '''<?xml version="1.0" encoding="utf-8" standalone="no"?>
<vehicle type="combineDrivable">
    <annotation>Bizon Super Z056 (FMZ Plock 1976-1994) - FS25 mod, modelled from scratch in Blender</annotation>
    <storeData>
        <name>Super Z056</name>
        <specs>
            <power>100</power>
            <maxSpeed>21</maxSpeed>
        </specs>
        <functions>
            <function>$l10n_function_combine</function>
        </functions>
        <image>store_bizonZ056.dds</image>
        <price>38000</price>
        <lifetime>600</lifetime>
        <rotation>0</rotation>
        <brand>BIZON</brand>
        <category>harvesters</category>
        <shopTranslationOffset>0 0 0</shopTranslationOffset>
        <shopRotationOffset>0 0 0</shopRotationOffset>
    </storeData>
    <base>
        <typeDesc>$l10n_typeDesc_combine</typeDesc>
        <filename>bizonZ056.i3d</filename>
        <size width="3.3" length="6.7" height="4.0" lengthOffset="-1.65"/>
        <speedLimit value="21"/>
        <components>
            <component centerOfMass="0 1.45 -1.2" solverIterationCount="20" mass="7300"/>
        </components>
        <schemaOverlay attacherJointPosition="0 0" name="HARVESTER"/>
        <mapHotspot type="HARVESTER"/>
    </base>
    <wheels>
        <wheelConfigurations>
            <wheelConfiguration name="$l10n_configuration_valueDefault" price="0">
                <wheels autoRotateBackSpeed="1.6">
                    %(wheels)s
                </wheels>
            </wheelConfiguration>
        </wheelConfigurations>
        <ackermannSteeringConfigurations>
            <ackermannSteering rotSpeed="38" rotMax="40" rotCenterWheel1="1" rotCenterWheel2="2"/>
        </ackermannSteeringConfigurations>
    </wheels>
    <motorized>
        <differentialConfigurations>
            <differentialConfiguration>
                <differentials>
                    <differential torqueRatio="0.5" maxSpeedRatio="1.3" wheelIndex1="1" wheelIndex2="2"/>
                </differentials>
            </differentialConfiguration>
        </differentialConfigurations>
        <motorConfigurations>
            <motorConfiguration name="SW-400" hp="100" price="0">
                <motor torqueScale="0.36" minRpm="850" maxRpm="2350" maxForwardSpeed="21" maxBackwardSpeed="8" brakeForce="4" lowBrakeForceScale="0.4" dampingRateScale="1.4">
                    <torque normRpm="0.36" torque="0.8"/>
                    <torque normRpm="0.5" torque="0.94"/>
                    <torque normRpm="0.64" torque="1"/>
                    <torque normRpm="0.8" torque="0.96"/>
                    <torque normRpm="0.94" torque="0.89"/>
                    <torque normRpm="1" torque="0.62"/>
                </motor>
                <transmission minForwardGearRatio="28" maxForwardGearRatio="320" minBackwardGearRatio="70" maxBackwardGearRatio="320" name="$l10n_info_transmission_hydrostatic"/>
            </motorConfiguration>
        </motorConfigurations>
        <consumerConfigurations>
            <consumerConfiguration>
                <consumer fillUnitIndex="2" usage="22" fillType="diesel"/>
            </consumerConfiguration>
        </consumerConfigurations>
        <motorStartDuration>2600</motorStartDuration>
        <exhaustFlap node="exhaustFlap" maxRot="38" rotationAxis="1"/>
        <animationNodes>
            %(motor_nodes)s
        </animationNodes>
        <dashboards>
            <dashboard displayType="ROT" valueType="rpm" node="needle_rpm" minRot="0 0 135" maxRot="0 0 -135" minValueRot="0" maxValueRot="2500"/>
            <dashboard displayType="ROT" valueType="speed" node="needle_speed" minRot="0 0 135" maxRot="0 0 -135" minValueRot="0" maxValueRot="25"/>
        </dashboards>
        <sounds>
            %(motor_sounds)s
        </sounds>
    </motorized>
    <drivable>
        <steeringWheel node="steeringWheel" indoorRotation="720" outdoorRotation="120"/>
        <cruiseControl maxSpeed="20"/>
    </drivable>
    <enterable>
        <enterReferenceNode node="enterReferenceNode"/>
        <exitPoint node="exitPoint"/>
        <cameras>
            <camera node="outdoorCamera" rotatable="true" rotateNode="outdoorCameraTarget" limit="true" useWorldXZRotation="true" rotMinX="-1.3" rotMaxX="0.9" transMin="6" transMax="32">
                <raycastNode node="cameraRaycastNode1"/>
                <raycastNode node="cameraRaycastNode2"/>
                <raycastNode node="cameraRaycastNode3"/>
            </camera>
            <camera node="indoorCamera" rotatable="true" limit="true" rotMinX="-1.2" rotMaxX="1.2" transMin="0" transMax="0" isInside="true"/>
        </cameras>
        <characterNode node="playerSkin" cameraMinDistance="1.5">
            <target ikChain="leftArm" targetNode="leftHandTarget"/>
            <target ikChain="rightArm" targetNode="rightHandTarget"/>
            <target ikChain="leftFoot" targetNode="leftFootTarget"/>
            <target ikChain="rightFoot" targetNode="rightFootTarget"/>
        </characterNode>
    </enterable>
    <lights>
        <states>
            <state lightTypes="0"/>
            <state lightTypes="0 1 2"/>
            <state lightTypes="0 1 2 3"/>
        </states>
        <realLights>
            <low>
                <light node="frontLightLow" lightTypes="0" excludedLightTypes="3"/>
                <light node="highBeam" lightTypes="3"/>
                <light node="workLightFront" lightTypes="1"/>
                <light node="workLightBack" lightTypes="2"/>
                <light node="pipeLight" lightTypes="1"/>
            </low>
            <high>
                <light node="frontLightLow" lightTypes="0" excludedLightTypes="3"/>
                <light node="highBeam" lightTypes="3"/>
                <light node="workLightFront" lightTypes="1"/>
                <light node="workLightBack" lightTypes="2"/>
                <light node="pipeLight" lightTypes="1"/>
            </high>
        </realLights>
        <defaultLights>
            <defaultLight node="lit_front" toggleVisibility="true" lightTypes="0"/>
            <defaultLight node="lit_tail_L" toggleVisibility="true" lightTypes="0"/>
            <defaultLight node="lit_tail_R" toggleVisibility="true" lightTypes="0"/>
            <defaultLight node="lit_work_front" toggleVisibility="true" lightTypes="1"/>
            <defaultLight node="lit_work_rear" toggleVisibility="true" lightTypes="2"/>
        </defaultLights>
        <brakeLights>
            <brakeLight node="lit_brake" toggleVisibility="true"/>
        </brakeLights>
        <turnLights>
            <turnLightLeft node="lit_turn_front_L" toggleVisibility="true"/>
            <turnLightLeft node="lit_turn_rear_L" toggleVisibility="true"/>
            <turnLightRight node="lit_turn_front_R" toggleVisibility="true"/>
            <turnLightRight node="lit_turn_rear_R" toggleVisibility="true"/>
        </turnLights>
    </lights>
    <attacherJoints>
        <attacherJoint node="attacherJointCutter" jointType="cutter" allowsJointLimitMovement="false" allowsLowering="true" moveTime="2.5" lowerRotLimit="0 0 0" upperRotLimit="0 0 0" lowerTransLimit="0 0 0" upperTransLimit="0 0 0" lockDownRotLimit="true" lockUpRotLimit="true">
            <rotationNode node="feederHouse" lowerRotation="0 0 0" upperRotation="-20 0 0"/>
            <distanceToGround lower="0.73" upper="1.27"/>
            <schema position="0 0" rotation="0" invertX="false"/>
        </attacherJoint>
    </attacherJoints>
    <cylindered>
        <movingParts>
            <movingPart node="liftCylL" referencePoint="liftRodRefL" referenceFrame="bizonZ056_main_component">
                <translatingPart node="liftRodL"/>
            </movingPart>
            <movingPart node="liftCylR" referencePoint="liftRodRefR" referenceFrame="bizonZ056_main_component">
                <translatingPart node="liftRodR"/>
            </movingPart>
        </movingParts>
    </cylindered>
    <fillUnit>
        <fillUnitConfigurations>
            <fillUnitConfiguration>
                <fillUnits>
                    <fillUnit unitTextOverride="$l10n_unit_literShort" showOnHud="true" fillTypeCategories="combine" capacity="3000"/>
                    <fillUnit unitTextOverride="$l10n_unit_literShort" showOnHud="false" showInShop="false" fillTypes="diesel" capacity="200">
                        <exactFillRootNode node="exactFillRootNodeFuel"/>
                    </fillUnit>
                </fillUnits>
            </fillUnitConfiguration>
        </fillUnitConfigurations>
    </fillUnit>
    <combine fillUnitIndex="1" allowThreshingDuringRain="false">
        <swath available="true" isDefaultActive="true" workAreaIndex="1"/>
        <chopper available="true" workAreaIndex="2"/>
        <sounds>
            %(combine_sounds)s
        </sounds>
    </combine>
    <turnOnVehicle turnOffIfNotAllowed="true">
        <turnedOnAnimation name="threshingShake" turnOnFadeTime="1.5" turnOffFadeTime="2.5" speedScale="1"/>
        <animationNodes>
            %(thresh_nodes)s
        </animationNodes>
    </turnOnVehicle>
    <pipe dischargeNodeIndex="1" automaticDischarge="true">
        <unloadingTriggers>
            <unloadingTrigger node="pipeUnloadingTrigger"/>
        </unloadingTriggers>
        <states num="2" unloading="2" turnOnAllowed="1 2"/>
        <pipeNodes>
            <pipeNode node="pipeNode" rotationSpeeds="0 22 0">
                <state rotation="0 0 0"/>
                <state rotation="0 -95 0"/>
            </pipeNode>
        </pipeNodes>
    </pipe>
    <dischargeable>
        <dischargeNode node="dischargeNode" fillUnitIndex="1" emptySpeed="35" maxDistance="7" canDischargeToGround="true" canDischargeToObject="true">
            <info width="0.6" length="0.6"/>
            <raycast useWorldNegYDirection="true"/>
        </dischargeNode>
    </dischargeable>
    <workAreas>
        <workArea type="combineSwath" functionName="processCombineSwathArea" requiresGroundContact="false">
            <area startNode="swathAreaStart" widthNode="swathAreaWidth" heightNode="swathAreaHeight"/>
        </workArea>
        <workArea type="combineChopper" functionName="processCombineChopperArea" requiresGroundContact="false">
            <area startNode="chopperAreaStart" widthNode="chopperAreaWidth" heightNode="chopperAreaHeight"/>
        </workArea>
    </workAreas>
    <animations>
        <animation name="threshingShake" looping="true">
            %(walker_parts)s
        </animation>
    </animations>
    <washable dirtDuration="90" washDuration="1" workMultiplier="4" fieldMultiplier="2"/>
    <wearable wearDuration="600" workMultiplier="4" fieldMultiplier="2"/>
%(mappings)s
</vehicle>
'''
motor_sounds = [
    sound('motorStart', 'motor_start.ogg', '0.6 3.6 -2.3', 4, 80, 1.0, 0.55, loops=1),
    sound('motorStop', 'motor_stop.ogg', '0.6 3.6 -2.3', 4, 80, 0.9, 0.55, loops=1),
    # idle layer fades out and the loaded diesel fades in as the revs rise; pitch shifts stay small
    sound('motor', 'engine_idle_loop.ogg', '0.6 3.6 -2.3', 4, 90, 0.9, 0.5, fade='fadeIn="0.3" fadeOut="0.4"',
          vmods=[(850, 1.0), (1400, 0.55), (2000, 0.0)], pmods=[(850, 1.0), (1500, 1.35)]),
    sound('motor', 'engine_load_loop.ogg', '0.6 3.6 -2.3', 4, 110, 1.0, 0.5, fade='fadeIn="0.3" fadeOut="0.4"',
          vmods=[(850, 0.3), (1300, 0.85), (2350, 1.1)], pmods=[(850, 0.62), (2000, 1.0), (2350, 1.12)]),
]
combine_sounds = [
    sound('start', 'threshing_start.ogg', '0 1.6 -1.0', 4, 70, 1.1, 0.45, loops=1),
    sound('stop', 'threshing_stop.ogg', '0 1.6 -1.0', 4, 70, 1.1, 0.45, loops=1),
    sound('work', 'threshing_loop.ogg', '0 1.6 -1.0', 4, 90, 1.2, 0.45, fade='fadeIn="0.5" fadeOut="0.8"'),
]
xml_c = combine_xml % {
    'wheels': '\n                    '.join(wheel_xml),
    'motor_nodes': '\n            '.join(motor_nodes),
    'motor_sounds': '\n            '.join(motor_sounds),
    'combine_sounds': '\n            '.join(combine_sounds),
    'thresh_nodes': '\n            '.join(thresh_nodes),
    'walker_parts': '\n            '.join(walker_parts),
    'mappings': mappings_xml(maps_c, used_c),
}

# ------------------------------------------------------------------ header XML
root_h = dump_h['root']
used_h = set()
for n in ('headerZ056_main_component', 'attacherJointInput', 'reel', 'auger', 'knife', 'pl_hdrInput', 'pl_hdrAuger', 'cutAreaStart',
          'cutAreaWidth', 'cutAreaHeight', 'groundReferenceNode'):
    assert n in maps_h, n
    used_h.add(n)
kt = find(root_h, 'knife')['t']
knife_parts = []
for s in range(4):
    x0 = [0.0, 0.038, 0.0, -0.038][s]
    x1 = [0.038, 0.0, -0.038, 0.0][s]
    knife_parts.append('<part node="knife" startTime="%.4f" endTime="%.4f" startTrans="%s" endTrans="%s"/>' % (
        0.0625 * s, 0.0625 * (s + 1), fv([kt[0] + x0, kt[1], kt[2]]), fv([kt[0] + x1, kt[1], kt[2]])))
header_xml = '''<?xml version="1.0" encoding="utf-8" standalone="no"?>
<vehicle type="cutter">
    <annotation>Bizon grain header 4.2 m for Super Z056 - FS25 mod, modelled from scratch</annotation>
    <storeData>
        <name>Heder 4,2 m (Z056)</name>
        <specs>
            <workingWidth>4.2</workingWidth>
        </specs>
        <functions>
            <function>$l10n_function_cutter</function>
        </functions>
        <image>store_headerZ056.dds</image>
        <price>7500</price>
        <lifetime>600</lifetime>
        <rotation>0</rotation>
        <brand>BIZON</brand>
        <category>cutters</category>
        <shopTranslationOffset>0 0 0</shopTranslationOffset>
        <shopRotationOffset>0 0 0</shopRotationOffset>
    </storeData>
    <base>
        <typeDesc>$l10n_typeDesc_cutter</typeDesc>
        <filename>headerZ056.i3d</filename>
        <size width="4.6" length="2.1" height="1.9" lengthOffset="3.25"/>
        <speedLimit value="12"/>
        <components>
            <component centerOfMass="0 0.55 3.2" solverIterationCount="20" mass="1150"/>
        </components>
        <schemaOverlay attacherJointPosition="0 0" name="COMBINE_HEADER"/>
    </base>
    <attachable>
        <inputAttacherJoints>
            <inputAttacherJoint node="attacherJointInput" jointType="cutter" lowerRotationOffset="0" upperRotationOffset="0" allowsLowering="true" isDefaultLowered="false">
                <distanceToGround lower="0.73" upper="1.27"/>
            </inputAttacherJoint>
        </inputAttacherJoints>
        <brakeForce force="0"/>
    </attachable>
    <cutter fruitTypeCategories="GRAINHEADER" allowCuttingWhileRaised="false" movingDirection="1" strawRatio="1">
        <animationNodes>
            <animationNode node="reel" rotSpeed="140" rotAxis="1" turnOnFadeTime="1.5" turnOffFadeTime="2"/>
            <animationNode node="auger" rotSpeed="-520" rotAxis="1" turnOnFadeTime="1.5" turnOffFadeTime="2"/>
            <animationNode node="pl_hdrInput" rotSpeed="-900" rotAxis="1" turnOnFadeTime="1.5" turnOffFadeTime="2"/>
            <animationNode node="pl_hdrAuger" rotSpeed="-520" rotAxis="1" turnOnFadeTime="1.5" turnOffFadeTime="2"/>
        </animationNodes>
    </cutter>
    <turnOnVehicle turnedOnByAttacherVehicle="true">
        <turnedOnAnimation name="knifeMove" turnOnFadeTime="0.6" turnOffFadeTime="1.2" speedScale="1"/>
    </turnOnVehicle>
    <groundReferenceNodes>
        <groundReferenceNode node="groundReferenceNode" threshold="0.35" chargeValue="1"/>
    </groundReferenceNodes>
    <workAreas>
        <workArea type="cutter" functionName="processCutterArea" requiresGroundContact="true">
            <area startNode="cutAreaStart" widthNode="cutAreaWidth" heightNode="cutAreaHeight"/>
            <groundReferenceNode index="1"/>
        </workArea>
    </workAreas>
    <animations>
        <animation name="knifeMove" looping="true">
            %(knife_parts)s
        </animation>
    </animations>
    <washable dirtDuration="90" washDuration="1" workMultiplier="4" fieldMultiplier="2"/>
    <wearable wearDuration="600" workMultiplier="4" fieldMultiplier="2"/>
%(mappings)s
</vehicle>
''' % {'knife_parts': '\n            '.join(knife_parts), 'mappings': mappings_xml(maps_h, used_h)}

moddesc = '''<?xml version="1.0" encoding="utf-8" standalone="no"?>
<modDesc descVersion="98">
    <author>Hoplite</author>
    <version>1.0.1.0</version>
    <title>
        <en>Bizon Super Z056</en>
        <de>Bizon Super Z056</de>
        <pl>Bizon Super Z056</pl>
    </title>
    <description>
        <en><![CDATA[Bizon Super Z056 combine (FMZ Plock, 1976-1994) with a 4.2 m grain header, modelled from scratch.

- SW-400 six cylinder, 100 hp, hydrostatic drive up to 21 km/h, rear axle steering
- 3000 l grain tank, swinging unloading auger, straw swath or chopper
- engine vibration, exhaust rain flap, spinning radiator screen
- all belt drives turn and the straw walkers shake while threshing
- extras: two crates of Tyskie, fire extinguisher, jerry can, CB antenna]]></en>
        <pl><![CDATA[Kombajn Bizon Super Z056 (FMŻ Płock, 1976-1994) z hederem zbożowym 4,2 m, wymodelowany od zera.

- silnik SW-400, 6 cylindrów, 100 KM, napęd hydrostatyczny do 21 km/h, skrętna tylna oś
- zbiornik 3000 l, obracana rura wyładowcza, pokos ze słomy albo sieczkarnia
- drgania silnika, klapka na wydechu, obracające się sito chłodnicy
- przy młóceniu kręcą się wszystkie pasy i koła pasowe, wytrząsacze chodzą
- dodatki: dwie skrzynki Tyskie, gaśnica, kanister, antena CB]]></pl>
    </description>
    <iconFilename>icon_bizonZ056.dds</iconFilename>
    <multiplayer supported="true"/>
    <brands>
        <brand name="BIZON" title="Bizon" image="brand_bizon.dds"/>
    </brands>
    <storeItems>
        <storeItem xmlFilename="bizonZ056.xml"/>
        <storeItem xmlFilename="headerZ056.xml"/>
    </storeItems>
</modDesc>
'''
for name, text in (('bizonZ056.xml', xml_c), ('headerZ056.xml', header_xml), ('modDesc.xml', moddesc)):
    with open(os.path.join(STAGE, name), 'w', encoding='utf-8') as f:
        f.write(text)

# ------------------------------------------------------------------ validation
problems = []
for name in ('bizonZ056.xml', 'headerZ056.xml', 'modDesc.xml', 'bizonZ056.i3d', 'headerZ056.i3d'):
    try:
        ET.parse(os.path.join(STAGE, name))
    except ET.ParseError as e:
        problems.append('%s: %s' % (name, e))
for xmlname, maps in (('bizonZ056.xml', maps_c), ('headerZ056.xml', maps_h)):
    tree = ET.parse(os.path.join(STAGE, xmlname))
    ids = {m.get('id') for m in tree.iter('i3dMapping')}
    for el in tree.iter():
        for att in ('node', 'repr', 'driveNode', 'rotateNode', 'targetNode', 'referencePoint', 'referenceFrame', 'startNode',
                    'widthNode', 'heightNode'):
            v = el.get(att)
            if v and not v.startswith('0>') and v not in ids:
                problems.append('%s: <%s %s="%s"> not mapped' % (xmlname, el.tag, att, v))
    for m in tree.iter('i3dMapping'):
        if maps.get(m.get('id')) != m.get('node'):
            problems.append('%s: mapping %s mismatch' % (xmlname, m.get('id')))
for rel in ['modDesc.xml', 'icon_bizonZ056.dds', 'brand_bizon.dds', 'store_bizonZ056.dds', 'store_headerZ056.dds',
            'bizonZ056.i3d.shapes', 'headerZ056.i3d.shapes'] + files_c + files_h:
    if not os.path.exists(os.path.join(STAGE, rel)):
        problems.append('missing file ' + rel)
for tree_name in ('bizonZ056.xml',):
    t = ET.parse(os.path.join(STAGE, tree_name))
    for el in t.iter():
        f = el.get('file')
        if f and not os.path.exists(os.path.join(STAGE, f)):
            problems.append('missing sound ' + f)
if problems:
    print('\n'.join(problems))
    sys.exit(1)

os.makedirs(os.path.dirname(os.path.abspath(OUTZIP)), exist_ok=True)
if os.path.exists(OUTZIP):
    os.remove(OUTZIP)
with zipfile.ZipFile(OUTZIP, 'w', zipfile.ZIP_DEFLATED) as z:
    for dp, _, fs in os.walk(STAGE):
        for f in sorted(fs):
            p = os.path.join(dp, f)
            z.write(p, os.path.relpath(p, STAGE))
print('MOD OK ->', OUTZIP, '%.1f MB' % (os.path.getsize(OUTZIP) / 1e6))
