"""Writes the FS25 XML files (modDesc, combine, header, sounds), store/brand icons and the mod zip.

Usage: python tools/make_mod.py build
Needs build/nodes.json from build_blender.py and the renders for the store images.
"""
import json
import os
import shutil
import sys
import xml.etree.ElementTree as ET
import zipfile

from PIL import Image, ImageDraw, ImageFont

BUILD = sys.argv[1] if len(sys.argv) > 1 else "build"
MOD_NAME = "FS25_BizonSuperZ056"
MOD = os.path.join(BUILD, "mod", MOD_NAME)
NODES = json.load(open(os.path.join(BUILD, "nodes.json")))
A = NODES["anim"]
VEH_C = "vehicles/bizonSuperZ056"
VEH_H = "vehicles/bizonHeader42"


def f3(v):
    return " ".join(("%.4g" % x).replace("-0", "0") if abs(x) < 5e-5 else "%.4g" % x for x in v)


class Mapper:
    def __init__(self, maps):
        self.maps = maps
        self.used = []

    def __call__(self, name):
        if name not in self.maps:
            raise KeyError("node '%s' missing in i3d" % name)
        if name not in self.used:
            self.used.append(name)
        return name

    def xml(self):
        return "\n".join('        <i3dMapping id="%s" node="%s"/>' % (n, self.maps[n]) for n in self.used)


AXIS = {"X": 1, "Y": 3, "Z": 2}  # blender axis -> GIANTS rotAxis


def anim_nodes(m, entries, fade_on=2, fade_off=3):
    out = []
    for name, ax, speed in entries:
        out.append('            <animationNode node="%s" rotSpeed="%d" rotAxis="%d" turnOnFadeTime="%g" '
                   'turnOffFadeTime="%g"/>' % (m(name), speed, AXIS[ax], fade_on, fade_off))
    return "\n".join(out)


def shaker_nodes(m, name, speed, fade_on=1.5, fade_off=2.5):
    ax = AXIS[A["shakers"][name]["axis"]]
    return ('            <animationNode node="%s" rotSpeed="%d" rotAxis="%d" turnOnFadeTime="%g" turnOffFadeTime="%g"/>\n'
            '            <animationNode node="%s" rotSpeed="%d" rotAxis="%d" turnOnFadeTime="%g" turnOffFadeTime="%g"/>'
            % (m(name + "A"), speed, ax, fade_on, fade_off, m(name + "B"), -speed, ax, fade_on, fade_off))


# ------------------------------------------------------------------ combine

def combine_xml():
    m = Mapper(NODES["combine"]["mappings"])
    for n in ("strawDropNode", "tankFillAuger", "attacherJointCutter"):  # used by sounds.xml linkNodes
        m(n)
    torque = "\n".join('                    <torque normRpm="%s" torque="%s"/>' % t for t in
                       (("0.45", "0.9"), ("0.5", "0.97"), ("0.59", "1"), ("0.72", "1"), ("0.86", "0.88"),
                        ("1", "0.72")))

    def motor(name, hp, scale, price):
        return f'''            <motorConfiguration name="{name}" hp="{hp}" price="{price}">
                <motor torqueScale="{scale}" minRpm="800" maxRpm="2200" maxForwardSpeed="20" maxBackwardSpeed="8" brakeForce="5" lowBrakeForceScale="0.1" accelerationLimit="0.9" dampingRateScale="1.6">
{torque}
                </motor>
                <transmission minForwardGearRatio="29" maxForwardGearRatio="420" minBackwardGearRatio="74" maxBackwardGearRatio="420" name="$l10n_info_transmission_cvt"/>
            </motorConfiguration>'''

    def wheel(dim, left, repr_, rear):
        extra = ' rotSpeed="-1" driveNode="%s"' % m(repr_.replace("axis", "wheel")) if rear else ""
        load, spring, damper = ("1.2", "40", "35") if rear else ("2.2", "60", "45")
        return (f'                    <wheel dimensions="{dim}" isLeft="{str(left).lower()}" hasTireTracks="true" hasParticles="true">\n'
                f'                        <physics tipOcclusionAreaGroupId="1" restLoad="{load}" repr="{m(repr_)}"{extra} forcePointRatio="0.4" initialCompression="30" suspTravel="0.1" spring="{spring}" damper="{damper}" frictionScale="1.6"/>\n'
                f'                    </wheel>')

    wheels_def = "\n".join([wheel("480_80R26", True, "wheelFrontLeft", False),
                            wheel("480_80R26", False, "wheelFrontRight", False),
                            wheel("460_70R24", True, "axisBackLeft", True),
                            wheel("460_70R24", False, "axisBackRight", True)])
    wheels_wide = "\n".join([wheel("650_75R32", True, "wheelFrontLeft", False),
                             wheel("650_75R32", False, "wheelFrontRight", False),
                             wheel("460_70R24", True, "axisBackLeft", True),
                             wheel("460_70R24", False, "axisBackRight", True)])
    shared = "\n".join(
        '        <sharedLight linkNode="%s" lightTypes="%d" filename="$data/shared/assets/lights/lizard/workingLight01.xml"/>'
        % (m(n), t) for n, t in (("workLightFL", 2), ("workLightFR", 2), ("workLightFL2", 2), ("workLightFR2", 2),
                                 ("workLightRearL", 1), ("workLightRearR", 1)))
    motor_nodes = "\n".join([shaker_nodes(m, "engineShake", 2700), shaker_nodes(m, "bodyShake", 2200),
                             anim_nodes(m, A["motor_rot"], 1.5, 3)])
    thresh = "\n".join([anim_nodes(m, A["thresh_rot"]),
                        '            <animationNode node="%s" rotSpeed="420" rotAxis="1" turnOnFadeTime="2" turnOffFadeTime="3"/>' % m(A["walkers"]["A"])]
                       + ['            <animationNode node="%s" rotSpeed="-420" rotAxis="1" turnOnFadeTime="2" turnOffFadeTime="3"/>' % m(b)
                          for b in A["walkers"]["B"]])
    pipe_rot = f3(A["pipeUnfoldRot"])
    jl, ju = f3(A["jointRotLower"]), f3(A["jointRotUpper"])
    hl, hu = "%.2f" % A["jointHeightLower"], "%.2f" % A["jointHeightUpper"]
    cyl_parts = "\n".join(
        f'''            <movingPart node="{m(c)}" referencePoint="{m(r)}" referenceFrame="{m(r)}" isActiveDirty="true" maxUpdateDistance="80">
                <translatingPart node="{m(c + 'Punch')}"/>
            </movingPart>''' for c, r in (("feederCylLeft", "feederCylRefLeft"), ("feederCylRight", "feederCylRefRight"),
                                          ("pipeCyl", "pipeCylRef")))
    needles = "\n".join(
        f'            <dashboard displayType="ROT" valueType="{vt}" node="{m(n + "NeedleRest")}" minRot="0 0 -135" maxRot="0 0 135" minValueRot="0" maxValueRot="{mx}"/>'
        for n, vt, mx in (("rpm", "rpm", 2500), ("speed", "speed", 30)))

    xml = f'''<?xml version="1.0" encoding="utf-8" standalone="no" ?>
<vehicle type="combineDrivable" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="https://validation.gdn.giants-software.com/xml/fs25/vehicle.xsd">
    <annotation>Bizon Super Z056 - fan made FS25 mod, built procedurally (Blender).</annotation>

    <storeData>
        <name>Super Z056</name>
        <specs>
            <power>105</power>
            <maxSpeed>20</maxSpeed>
            <combination xmlFilename="{VEH_H}/bizonHeader42.xml"/>
        </specs>
        <functions>
            <function>$l10n_function_combine</function>
            <function>$l10n_function_combineNeedsCutter</function>
        </functions>
        <image>{VEH_C}/store_bizonSuperZ056.dds</image>
        <price>38500</price>
        <lifetime>600</lifetime>
        <rotation>0</rotation>
        <brand>BIZON</brand>
        <category>harvesters</category>
        <shopTranslationOffset>0 0 0</shopTranslationOffset>
        <shopRotationOffset>0 0 0</shopRotationOffset>
    </storeData>

    <base>
        <typeDesc>$l10n_typeDesc_combine</typeDesc>
        <filename>{VEH_C}/bizonSuperZ056.i3d</filename>
        <sounds filename="{VEH_C}/sounds.xml" volumeFactor="0.9"/>
        <size width="3.0" length="7.6" height="4.2" lengthOffset="-1.6"/>
        <components>
            <component centerOfMass="0 1.15 -1.15" solverIterationCount="20" mass="6800"/>
        </components>
        <schemaOverlay attacherJointPosition="0 0" name="HARVESTER"/>
        <mapHotspot type="HARVESTER"/>
    </base>

    <powerConsumer ptoRpm="400" neededMaxPtoPower="10"/>

    <wheels>
        <wheelConfigurations tireCategories="HARVESTER TRACTOR TELEHANDLER">
            <wheelConfiguration name="$l10n_configuration_valueDefault" price="0" saveId="DEFAULT" numDynamicConfigurations="1">
                <wheels autoRotateBackSpeed="2.0">
{wheels_def}
                </wheels>
            </wheelConfiguration>
            <wheelConfiguration name="$l10n_configuration_valueWheelBroad" price="1800" saveId="BROAD" numDynamicConfigurations="1">
                <wheels autoRotateBackSpeed="2.0">
{wheels_wide}
                </wheels>
            </wheelConfiguration>
        </wheelConfigurations>
        <ackermannSteeringConfigurations>
            <ackermannSteering rotSpeed="35" rotMax="42" rotCenterWheel1="1" rotCenterWheel2="2"/>
        </ackermannSteeringConfigurations>
    </wheels>

    <lights>
{shared}
        <states>
            <state lightTypes="0"/>
            <state lightTypes="0 1"/>
            <state lightTypes="0 1 2"/>
            <state lightTypes="0 1 2 4"/>
        </states>
        <realLights>
            <low>
                <light node="{m('frontLightLow')}" lightTypes="0" excludedLightTypes="2 3"/>
                <light node="{m('highBeamLow')}" lightTypes="3"/>
                <light node="{m('workLightBackLow')}" lightTypes="1"/>
                <light node="{m('workLightFrontLow')}" lightTypes="2"/>
            </low>
            <high>
                <light node="{m('frontLightHigh')}" lightTypes="0" excludedLightTypes="2 3"/>
                <light node="{m('frontLightHigh2')}" lightTypes="0" excludedLightTypes="2 3"/>
                <light node="{m('backLightsHigh')}" lightTypes="0"/>
                <light node="{m('workLightBackHigh')}" lightTypes="1"/>
                <light node="{m('workLightFrontHigh')}" lightTypes="2"/>
                <light node="{m('highBeamHigh')}" lightTypes="3"/>
                <light node="{m('pipeLightHigh')}" lightTypes="4"/>
                <brakeLight node="{m('backLightsHigh')}"/>
                <turnLightLeft node="{m('turnLightLeftFront')}"/>
                <turnLightLeft node="{m('turnLightLeftBack')}"/>
                <turnLightRight node="{m('turnLightRightFront')}"/>
                <turnLightRight node="{m('turnLightRightBack')}"/>
                <interiorLight node="{m('interiorLight')}"/>
            </high>
        </realLights>
        <beaconLights>
            <beaconLight node="{m('beaconLight01')}" speed="0.015" filename="$data/shared/assets/beaconLights/lizard/beaconLight07.xml"/>
        </beaconLights>
    </lights>

    <enterable isTabbable="true">
        <enterReferenceNode node="{m('exitPoint')}"/>
        <exitPoint node="{m('exitPoint')}"/>
        <cameras>
            <camera node="{m('outdoorCamera1')}" rotatable="true" rotateNode="{m('outdoorCameraTarget')}" limit="true" useWorldXZRotation="true" rotMinX="-1.4" rotMaxX="1" transMin="6" transMax="40" translation="0 0 12" rotation="-20 180 0">
                <raycastNode node="{m('cameraRaycastNode1')}"/>
                <raycastNode node="{m('cameraRaycastNode2')}"/>
                <raycastNode node="{m('cameraRaycastNode3')}"/>
            </camera>
            <camera node="{m('indoorCamera1')}" rotation="-15 180 0" rotatable="true" limit="true" rotMinX="-1.1" rotMaxX="0.5" transMin="0" transMax="0" isInside="true"/>
        </cameras>
        <characterNode node="{m('playerSkin')}" cameraMinDistance="0.5">
            <target ikChain="rightFoot" targetNode="{m('playerRightFootTarget')}"/>
            <target ikChain="leftFoot" targetNode="{m('playerLeftFootTarget')}"/>
            <target ikChain="rightArm" targetNode="{m('playerRightHandTarget')}"/>
            <target ikChain="leftArm" targetNode="{m('playerLeftHandTarget')}"/>
        </characterNode>
    </enterable>

    <motorized>
        <consumerConfigurations>
            <consumerConfiguration>
                <consumer fillUnitIndex="2" usage="30" fillType="diesel"/>
            </consumerConfiguration>
        </consumerConfigurations>
        <differentialConfigurations>
            <differentialConfiguration>
                <differentials>
                    <differential torqueRatio="0.5" maxSpeedRatio="1.4" wheelIndex1="1" wheelIndex2="2"/>
                </differentials>
            </differentialConfiguration>
        </differentialConfigurations>
        <motorConfigurations>
{motor("SW-400 105 KM", 105, 0.44, 0)}
{motor("SW-680 150 KM", 150, 0.63, 4800)}
        </motorConfigurations>
        <exhaustEffects>
            <exhaustEffect node="{m('exhaustParticle')}" filename="$data/effects/exhaust/exhaust.i3d" minRpmColor="0.25 0.25 0.25 0.3" maxRpmColor="0.08 0.08 0.08 0.85" minRpmScale="0.08" maxRpmScale="0.75"/>
        </exhaustEffects>
        <animationNodes>
{motor_nodes}
        </animationNodes>
        <motorStartDuration>2600</motorStartDuration>
        <dashboards>
            <dashboard displayType="MULTI_STATE" valueType="ignitionState" node="{m('ignitionKey')}" doInterpolation="true">
                <state value="0" rotation="0 0 0"/>
                <state value="1" rotation="0 0 -40"/>
                <state value="2" rotation="0 0 -20"/>
            </dashboard>
{needles}
        </dashboards>
    </motorized>

    <drivable>
        <steeringWheel node="{m('steeringWheel')}" indoorRotation="720" outdoorRotation="20"/>
    </drivable>

    <attacherJoints>
        <attacherJoint jointType="cutter" node="{m('attacherJointCutter')}" lowerTransLimit="0 0 0" lowerRotLimit="0 0 15" dynamicLowerRotLimit="true" lockDownRotLimit="true" moveTime="3" comboTime="0" delayedObjectChanges="false" delayedObjectChangesOnAttach="true">
            <distanceToGround lower="{hl}" upper="{hu}"/>
            <rotationNode node="{m('attacherJointRot')}" lowerRotation="{jl}" upperRotation="{ju}" startRotation="0 0 0"/>
            <schema position="1 0" rotation="0" invertX="true"/>
            <attachSound template="headerAttach01" linkNode="{m('attacherJointCutter')}"/>
        </attacherJoint>
    </attacherJoints>

    <fillUnit>
        <fillUnitConfigurations>
            <fillUnitConfiguration>
                <fillUnits>
                    <fillUnit unitTextOverride="$l10n_unit_literShort" fillTypeCategories="combine" capacity="3200">
                        <exactFillRootNode node="{m('exactFillRootNode')}"/>
                    </fillUnit>
                    <fillUnit unitTextOverride="$l10n_unit_literShort" showOnHud="false" showInShop="false" fillTypes="diesel" capacity="180">
                        <exactFillRootNode node="{m('exactFillRootNodeFuel')}"/>
                    </fillUnit>
                </fillUnits>
            </fillUnitConfiguration>
        </fillUnitConfigurations>
    </fillUnit>

    <fillVolume>
        <fillVolumeConfigurations>
            <fillVolumeConfiguration>
                <volumes>
                    <volume node="{m('fillVolume')}" maxDelta="0.15" maxAllowedHeapAngle="15" fillUnitIndex="1"/>
                </volumes>
            </fillVolumeConfiguration>
        </fillVolumeConfigurations>
        <unloadInfos>
            <unloadInfo>
                <node node="{m('unloadInfo')}" width="0.4" length="0.4"/>
            </unloadInfo>
        </unloadInfos>
        <loadInfos>
            <loadInfo>
                <node node="{m('loadInfo')}" width="0.4" length="0.4"/>
            </loadInfo>
        </loadInfos>
    </fillVolume>

    <animations>
        <animation name="foldPipe" soundVolumeFactor="2.5">
            <part node="{m('pipe')}" startTime="0" endTime="5" startRot="0 0 0" endRot="{pipe_rot}"/>
            <sound template="hydraulicClose01" startTime="0.01" endTime="4.99" volumeScale="1.4" pitchScale="0.7" linkNode="{m('pipe')}"/>
            <sound template="cylinderPunch" startTime="0.1" direction="-1" volumeScale="0.4" pitchScale="1.4" linkNode="{m('pipe')}"/>
        </animation>
    </animations>

    <cylindered>
        <movingTools>
            <movingTool node="{m('pipe')}" playSound="true">
                <dependentPart node="{m('pipeCyl')}"/>
            </movingTool>
        </movingTools>
        <movingParts>
{cyl_parts}
        </movingParts>
    </cylindered>

    <turnOnVehicle turnOffIfNotAllowed="true"/>

    <workAreas>
        <workArea type="combineSwath" functionName="processCombineSwathArea" requiresGroundContact="false" disableBackwards="false">
            <area startNode="{m('workAreaStrawStart')}" widthNode="{m('workAreaStrawWidth')}" heightNode="{m('workAreaStrawHeight')}"/>
        </workArea>
        <workArea type="combineChopper" functionName="processCombineChopperArea" requiresGroundContact="false" disableBackwards="false">
            <area startNode="{m('workAreaChopperStart')}" widthNode="{m('workAreaChopperWidth')}" heightNode="{m('workAreaChopperHeight')}"/>
        </workArea>
    </workAreas>

    <combine fillUnitIndex="1" allowThreshingDuringRain="false">
        <swath available="true" workAreaIndex="1" isDefaultActive="true"/>
        <chopper available="true" workAreaIndex="2"/>
        <processing toggleTime="4.5"/>
        <animationNodes>
{thresh}
        </animationNodes>
    </combine>

    <pipe>
        <states num="2" unloading="2"/>
        <animation name="foldPipe" speedScale="1"/>
        <unloadingTriggers>
            <unloadingTrigger node="{m('trailerTrigger')}"/>
        </unloadingTriggers>
        <animationNodes>
            <animationNode node="{m('pipeAuger')}" rotAxis="3" rotSpeed="500"/>
        </animationNodes>
    </pipe>

    <dischargeable>
        <dischargeNode node="{m('dischargeNode')}" emptySpeed="45" fillUnitIndex="1" maxDistance="7">
            <raycast yOffset="1" useWorldNegYDirection="true"/>
            <info width="0.4" length="0.4" useRaycastHitPosition="true"/>
            <effects>
                <effectNode effectClass="PipeEffect" effectNode="{m('pipeEffect')}" materialType="pipe" delay="0" maxBending="0.8" extraDistance="0.1"/>
            </effects>
            <dischargeStateSound template="harvesterDischargeStartCabin" loops="1"/>
        </dischargeNode>
    </dischargeable>

    <suspensions>
        <suspension node="{m('seat')}" weight="90" minTranslation="-0.04 -0.06 0" maxTranslation="0.04 0.06 0" suspensionParametersX="18 3" suspensionParametersY="5 0.8" suspensionParametersZ="18 3"/>
        <suspension useCharacterTorso="true" weight="90" minRotation="0 -6 -6" maxRotation="0 6 6" suspensionParametersY="6 0.8" suspensionParametersZ="6 0.8"/>
    </suspensions>

    <ai>
        <agent frontWheelNodes="{m('wheelBackLeft')} {m('wheelBackRight')}"/>
        <collisionTrigger node="{m('aiCollisionNode')}" width="3.2" height="4.3"/>
    </ai>

    <foliageBending>
        <bendingNode wheelIndices="1 2" minZ="-0.6" maxZ="1.2" yOffset="0.45"/>
        <bendingNode wheelIndices="3 4" minZ="-4.1" maxZ="-2.9" yOffset="0.45"/>
        <bendingNode minX="-0.8" maxX="0.8" minZ="-5.4" maxZ="1.2" yOffset="0.5"/>
    </foliageBending>

    <wearable wearDuration="480" workMultiplier="5" fieldMultiplier="2"/>
    <washable dirtDuration="80" washDuration="1" workMultiplier="4" fieldMultiplier="2"/>

    <i3dMappings>
__MAPPINGS__
    </i3dMappings>
</vehicle>
'''
    return xml.replace("__MAPPINGS__", m.xml())


SOUNDS_COMBINE_T = '''<?xml version="1.0" encoding="utf-8" standalone="no" ?>
<sounds xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="https://validation.gdn.giants-software.com/xml/fs25/vehicle_sounds.xsd">
    <motorized>
        <sounds>
            <motorStart file="SND/bizon_motor_start.ogg" innerRadius="5" outerRadius="90" loops="1" linkNodeOffset="0 2.8 -3.1">
                <volume indoor="0.7" outdoor="1.4"/>
            </motorStart>
            <motorStop file="SND/bizon_motor_stop.ogg" innerRadius="5" outerRadius="90" loops="1" linkNodeOffset="0 2.8 -3.1">
                <volume indoor="0.6" outdoor="1.2"/>
            </motorStop>
            <!-- idle layer: steady diesel idle, fades out as the revs come up -->
            <motor file="SND/bizon_engine_idle_loop.ogg" innerRadius="5" outerRadius="80" linkNodeOffset="0 2.8 -3.1">
                <volume indoor="0.6" outdoor="1.2">
                    <modifier type="MOTOR_RPM_REAL" value="800" modifiedValue="1.0"/>
                    <modifier type="MOTOR_RPM_REAL" value="1300" modifiedValue="0.55"/>
                    <modifier type="MOTOR_RPM_REAL" value="1800" modifiedValue="0.15"/>
                    <modifier type="MOTOR_RPM_REAL" value="2200" modifiedValue="0.05"/>
                </volume>
                <pitch indoor="1" outdoor="1">
                    <modifier type="MOTOR_RPM_REAL" value="800" modifiedValue="0.95"/>
                    <modifier type="MOTOR_RPM_REAL" value="2200" modifiedValue="1.9"/>
                </pitch>
                <lowpassGain indoor="0.5" outdoor="1.0"/>
            </motor>
            <!-- working engine: old diesel under load, pitch follows the revs -->
            <motor file="SND/bizon_engine_load_loop.ogg" innerRadius="6" outerRadius="120" linkNodeOffset="0 2.8 -3.1">
                <volume indoor="0.8" outdoor="1.6">
                    <modifier type="MOTOR_RPM_REAL" value="800" modifiedValue="0.25"/>
                    <modifier type="MOTOR_RPM_REAL" value="1300" modifiedValue="0.6"/>
                    <modifier type="MOTOR_RPM_REAL" value="1800" modifiedValue="0.9"/>
                    <modifier type="MOTOR_RPM_REAL" value="2200" modifiedValue="1.0"/>
                    <modifier type="MOTOR_LOAD" value="0.0" modifiedValue="0.8"/>
                    <modifier type="MOTOR_LOAD" value="1.0" modifiedValue="1.15"/>
                </volume>
                <pitch indoor="1" outdoor="1">
                    <modifier type="MOTOR_RPM_REAL" value="800" modifiedValue="0.58"/>
                    <modifier type="MOTOR_RPM_REAL" value="1500" modifiedValue="0.82"/>
                    <modifier type="MOTOR_RPM_REAL" value="2200" modifiedValue="1.08"/>
                </pitch>
                <lowpassGain indoor="0.45" outdoor="1.0"/>
            </motor>
            <motor template="indoorCabinRumble" linkNodeOffset="-0.5 3.0 0.9" pitchScale="0.8"/>
            <motor template="indoorCabinRumble" linkNodeOffset="0.5 3.0 0.9" pitchScale="0.95"/>
            <motor template="transmissionHarvester01" pitchScale="0.85" volumeScale="0.9" linkNodeOffset="0 0.9 0"/>
        </sounds>
    </motorized>
    <lights>
        <sounds>
            <toggleLights template="switch01"/>
            <turnLight template="switchTurnlight"/>
        </sounds>
    </lights>
    <attacherJoints>
        <sounds>
            <hydraulic template="hydraulicOpen04" linkNode="attacherJointCutter" volumeScale="2"/>
        </sounds>
    </attacherJoints>
    <drivable>
        <sounds>
            <waterSplash template="waterSplash01" linkNode="attacherJointCutter"/>
        </sounds>
    </drivable>
    <combine>
        <sounds>
            <chopperWork template="harvesterChopper" linkNode="strawDropNode"/>
            <chopStraw template="chopStrawDischarge" linkNode="strawDropNode"/>
            <dropStraw template="dropStrawDischarge" linkNode="strawDropNode"/>
            <fill template="grainLargeFill" volumeScale="0.3" linkNode="tankFillAuger"/>
        </sounds>
    </combine>
    <turnOnVehicle>
        <sounds>
            <start template="combineThreshingSystemStart" volumeScale="0.4"/>
            <!-- real recording of a combine threshing: drum whine, walkers, sieves and belts -->
            <work file="SND/bizon_threshing_loop.ogg" innerRadius="6" outerRadius="140" linkNodeOffset="0 2.0 -1.5">
                <volume indoor="0.7" outdoor="1.5"/>
                <lowpassGain indoor="0.5" outdoor="1.0"/>
            </work>
            <stop template="combineThreshingSystemStop" volumeScale="0.4"/>
        </sounds>
    </turnOnVehicle>
    <honk>
        <sound template="honkJohnDeereHarvester"/>
    </honk>
</sounds>
'''

SOUNDS_COMBINE = SOUNDS_COMBINE_T.replace("SND/", VEH_C + "/sounds/")


# ------------------------------------------------------------------ header

def header_xml():
    m = Mapper(NODES["header"]["mappings"])
    hl, hu = "%.2f" % A["jointHeightLower"], "%.2f" % A["jointHeightUpper"]
    rot = anim_nodes(m, [("reel", "X", 200), ("auger", "X", 380)] + [tuple(e) for e in A["header_rot"]], 2, 3)
    xml = f'''<?xml version="1.0" encoding="utf-8" standalone="no" ?>
<vehicle type="cutter" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="https://validation.gdn.giants-software.com/xml/fs25/vehicle.xsd">
    <annotation>Bizon grain header 4.2 m - fan made FS25 mod.</annotation>
    <storeData>
        <name>Heder zbożowy 4,2 m</name>
        <specs>
            <workingWidth>4.2</workingWidth>
            <combination xmlFilename="{VEH_C}/bizonSuperZ056.xml"/>
        </specs>
        <functions>
            <function>$l10n_function_cutter</function>
        </functions>
        <image>{VEH_H}/store_bizonHeader42.dds</image>
        <price>6800</price>
        <lifetime>600</lifetime>
        <rotation>0</rotation>
        <brand>BIZON</brand>
        <category>cutters</category>
    </storeData>
    <base>
        <typeDesc>$l10n_typeDesc_cutter</typeDesc>
        <filename>{VEH_H}/bizonHeader42.i3d</filename>
        <size width="4.6" length="2.3" height="1.7" lengthOffset="0.9"/>
        <speedLimit value="10"/>
        <components>
            <component centerOfMass="0 -0.15 0.75" solverIterationCount="10" mass="1150"/>
        </components>
        <schemaOverlay attacherJointPosition="0 0" name="COMBINE_HEADER"/>
        <mapHotspot type="CUTTER"/>
    </base>
    <attachable>
        <inputAttacherJoints>
            <inputAttacherJoint node="{m('attacherJoint')}" jointType="cutter">
                <heightNode node="{m('heightNode01')}"/>
                <heightNode node="{m('heightNode02')}"/>
                <heightNode node="{m('heightNode03')}"/>
                <distanceToGround lower="{hl}" upper="{hu}"/>
            </inputAttacherJoint>
        </inputAttacherJoints>
    </attachable>
    <powerConsumer ptoRpm="540" neededMaxPtoPower="35"/>
    <groundReferenceNodes>
        <groundReferenceNode node="{m('groundReferenceNode')}" threshold="0.5"/>
    </groundReferenceNodes>
    <workAreas>
        <workArea type="cutter" functionName="processCutterArea" disableBackwards="true">
            <area startNode="{m('workAreaStart')}" widthNode="{m('workAreaWidth')}" heightNode="{m('workAreaHeight')}"/>
            <groundReferenceNode index="1"/>
            <testAreas autoGenerate="true" zOffset="0.5" xOffset="0" length="0.6" numAreas="6" areaWidthScale="0.25"/>
        </workArea>
    </workAreas>
    <animations>
        <animation name="knifeAnimation" looping="true">
            <part node="{m('knife')}" startTime="0" endTime="0.5" startTrans="0 0 0" endTrans="0.076 0 0"/>
            <part node="{m('knife')}" startTime="0.5" endTime="1" startTrans="0.076 0 0" endTrans="0 0 0"/>
        </animation>
    </animations>
    <cutter fruitTypeCategories="grainHeader">
        <animationNodes>
{rot}
        </animationNodes>
        <sounds>
            <cut template="cropCutting" volumeScale="1.3"/>
        </sounds>
    </cutter>
    <turnOnVehicle turnedOnByAttacherVehicle="true">
        <turnedOnAnimation name="knifeAnimation" speedScale="6" turnOnFadeTime="2" turnOffFadeTime="2"/>
        <sounds>
            <start template="harvesterToolStart" volumeScale="1.0"/>
            <work template="harvesterToolWork" volumeScale="0.8"/>
            <stop template="harvesterToolStop" volumeScale="1.0"/>
        </sounds>
    </turnOnVehicle>
    <ai>
        <areaMarkers leftNode="{m('aiMarkerLeft')}" rightNode="{m('aiMarkerRight')}" backNode="{m('aiMarkerBack')}"/>
        <collisionTrigger useSize="true"/>
        <agentAttachment useSize="true"/>
    </ai>
    <foliageBending>
        <bendingNode minX="-2.3" maxX="2.3" minZ="-0.1" maxZ="2.0" yOffset="0.4"/>
    </foliageBending>
    <wearable wearDuration="480" workMultiplier="5" fieldMultiplier="2"/>
    <washable dirtDuration="80" washDuration="1" workMultiplier="4" fieldMultiplier="2"/>
    <i3dMappings>
__MAPPINGS__
    </i3dMappings>
</vehicle>
'''
    return xml.replace("__MAPPINGS__", m.xml())


DESC_PL = """Legendarny Bizon Super Z056 z Płocka - stary, ale jary.

- silnik SW-400 105 KM (opcja: SW-680 150 KM)
- zbiornik ziarna 3200 l, rura wyładowcza z siłownikiem
- wytrząsacze, sita, sito obrotowe chłodnicy, pasy i koła pasowe w ruchu
- trzęsienie silnika i maszyny po odpaleniu, wytrząsacze chodzą przy młóceniu
- kabina z zegarami, kogut, halogeny, trąbki, gaśnica, łopata
- w kabinie skrzynka Tyskie z butelkami (szkło, etykiety, kapsle)
- prawdziwe nagrania: rozruch i praca diesla, wycie młocarni (CC0, BigSoundBank)
- heder zbożowy 4,2 m: nagarniacz, ślimak, kosa w ruchu

Mod fanowski, nieoficjalny. Logotypy marek to własne napisy, nie oryginalne znaki."""

DESC_EN = """The legendary Bizon Super Z056 from Plock, Poland.
105 hp SW-400 (optional 150 hp SW-680), 3200 l grain tank, 4.2 m grain header.
Running belts and pulleys, rotating radiator screen, straw walkers shaking while threshing,
engine and body vibration when running. Fan made, unofficial."""


def moddesc():
    return f'''<?xml version="1.0" encoding="utf-8" standalone="no"?>
<modDesc descVersion="101" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="https://validation.gdn.giants-software.com/xml/fs25/modDesc.xsd">
    <author>Hoplite (Blender procedural build)</author>
    <version>1.0.0.0</version>
    <title>
        <en>Bizon Super Z056 + Header 4.2 m</en>
        <pl>Bizon Super Z056 + Heder 4,2 m</pl>
        <de>Bizon Super Z056 + Schneidwerk 4,2 m</de>
    </title>
    <description>
        <en><![CDATA[{DESC_EN}]]></en>
        <pl><![CDATA[{DESC_PL}]]></pl>
        <de><![CDATA[{DESC_EN}]]></de>
    </description>
    <iconFilename>icon_bizonSuperZ056.dds</iconFilename>
    <multiplayer supported="true"/>
    <brands>
        <brand name="BIZON" title="Bizon" image="brand_bizon.dds"/>
    </brands>
    <storeItems>
        <storeItem xmlFilename="{VEH_C}/bizonSuperZ056.xml"/>
        <storeItem xmlFilename="{VEH_H}/bizonHeader42.xml"/>
    </storeItems>
</modDesc>
'''


# ------------------------------------------------------------------ images

def store_image(src, dst, size=512):
    im = Image.open(src).convert("RGBA")
    bb = im.getbbox()
    if bb:
        im = im.crop(bb)
    w, h = im.size
    s = max(w, h)
    canvas = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    canvas.alpha_composite(im, ((s - w) // 2, (s - h) // 2))
    canvas = canvas.resize((size, size), Image.LANCZOS)
    canvas.save(dst, "DDS", pixel_format="DXT5")
    return canvas


def brand_image(dst):
    im = Image.new("RGBA", (512, 256), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    f = ImageFont.truetype("/usr/share/fonts/truetype/freefont/FreeSansBoldOblique.ttf", 150)
    bb = d.textbbox((0, 0), "BIZON", font=f)
    d.text(((512 - bb[2] + bb[0]) / 2 - bb[0], (256 - bb[3] + bb[1]) / 2 - bb[1]), "BIZON", font=f,
           fill=(176, 18, 14, 255), stroke_width=4, stroke_fill=(255, 255, 255, 255))
    im.save(dst, "DDS", pixel_format="DXT5")
    im.save(dst.replace(".dds", "_preview.png"))


def icon_image(store_rgba, dst):
    bg = Image.new("RGBA", (256, 256), (200, 170, 90, 255))
    grad = ImageDraw.Draw(bg)
    for y in range(256):
        c = int(150 + 70 * (1 - y / 255))
        grad.line([(0, y), (256, y)], fill=(c, int(c * 0.85), int(c * 0.45), 255))
    bg.alpha_composite(store_rgba.resize((256, 256), Image.LANCZOS))
    bg.save(dst, "DDS", pixel_format="DXT1")
    bg.convert("RGB").save(dst.replace(".dds", "_preview.png"))


def main():
    files = {
        os.path.join(MOD, "modDesc.xml"): moddesc(),
        os.path.join(MOD, VEH_C, "bizonSuperZ056.xml"): combine_xml(),
        os.path.join(MOD, VEH_C, "sounds.xml"): SOUNDS_COMBINE,
        os.path.join(MOD, VEH_H, "bizonHeader42.xml"): header_xml(),
    }
    for p, txt in files.items():
        ET.fromstring(txt.encode("utf-8"))  # well-formedness check
        with open(p, "w", encoding="utf-8") as f:
            f.write(txt)
    for i3d in (os.path.join(MOD, VEH_C, "bizonSuperZ056.i3d"), os.path.join(MOD, VEH_H, "bizonHeader42.i3d")):
        ET.parse(i3d)
    shutil.copy(os.path.join(BUILD, "textures", "bizon_decals_diffuse.dds"), os.path.join(MOD, "textures"))
    snd_dir = os.path.join(MOD, VEH_C, "sounds")
    os.makedirs(snd_dir, exist_ok=True)
    for fn in os.listdir(os.path.join(BUILD, "sounds")):
        shutil.copy(os.path.join(BUILD, "sounds", fn), snd_dir)
    sc = os.path.join(BUILD, "store_combine.png")
    sh = os.path.join(BUILD, "store_header.png")
    if not os.path.exists(sc):  # preview builds have no store renders
        sc = sh = os.path.join(BUILD, "render_front_left.png")
    store_c = store_image(sc, os.path.join(MOD, VEH_C, "store_bizonSuperZ056.dds"))
    store_image(sh, os.path.join(MOD, VEH_H, "store_bizonHeader42.dds"))
    icon_image(store_c, os.path.join(BUILD, "icon_bizonSuperZ056.dds"))
    shutil.move(os.path.join(BUILD, "icon_bizonSuperZ056.dds"), os.path.join(MOD, "icon_bizonSuperZ056.dds"))
    brand_image(os.path.join(BUILD, "brand_bizon.dds"))
    shutil.move(os.path.join(BUILD, "brand_bizon.dds"), os.path.join(MOD, "brand_bizon.dds"))
    zpath = os.path.join(BUILD, MOD_NAME + ".zip")
    if os.path.exists(zpath):
        os.remove(zpath)
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for dp, _, fns in os.walk(MOD):
            for fn in sorted(fns):
                if fn.endswith("_preview.png"):
                    continue
                full = os.path.join(dp, fn)
                z.write(full, os.path.relpath(full, MOD))
    print("zip:", zpath, os.path.getsize(zpath) // 1024, "KB")
    for n in z.namelist() if False else zipfile.ZipFile(zpath).namelist():
        print("  ", n)


if __name__ == "__main__":
    main()
