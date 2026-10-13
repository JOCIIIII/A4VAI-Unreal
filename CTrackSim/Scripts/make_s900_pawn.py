"""Vehicle look: the DJI S900 model (Unreal/dji_s900_camera_drone.glb, 8 rotors like the X8) on
Cosys-AirSim's flying pawn. Only the look changes - the vehicle is still Gazebo's X8, Unreal just
draws it at Gazebo's pose (ExternalPhysicsEngine).

  1. imports the GLB into /Game/CTrack/Vehicles/S900 as ONE static mesh (Interchange, combine
     all), and once more as separate parts into a temporary folder to measure the model
  2. BP_S900Pawn = copy of /AirSim/Blueprints/BP_FlyingPawn, its root BodyMesh emptied and the
     S900 mesh added under it as S900Mesh (the root's own transform is the vehicle pose), scaled
     to the X8's footprint (prop tips 0.77 m from the centre, the model's are 0.89 m), feet 44 cm
     below the centre (the X8 rests with its centre 0.44 m up), skids fore-aft (S900_YAW 0) - no
     collision (the lidar would see the prop tips - Cosys 3.5 does not skip the own vehicle); the
     quad's four propellers hidden (Rotation0..3 and the cameras stay - AirSim looks them up)

Then settings/settings_gazebo.json points the vehicle at it:
  "PawnPaths": {"S900": {"PawnBP": "Class'/Game/CTrack/Vehicles/BP_S900Pawn.BP_S900Pawn_C'"}},
  "Vehicles": {"SimpleFlight": {..., "PawnPath": "S900"}}

run (Unreal closed):
  $UE/Engine/Binaries/Linux/UnrealEditor-Cmd "$PWD/CTrackSim/CTrackSim.uproject" \\
      -run=pythonscript -script="$PWD/CTrackSim/Scripts/make_s900_pawn.py" -nullrhi -unattended
env: S900_GLB (default ../dji_s900_camera_drone.glb), S900_TIP_RADIUS_CM (77), S900_FEET_CM (-44),
     S900_YAW (degrees, default 0), S900_LOG (/tmp/ctrack/make_s900.txt)
"""
import math
import os

import unreal

HERE = os.path.dirname(os.path.abspath(__file__))
GLB = os.environ.get('S900_GLB', os.path.normpath(os.path.join(HERE, '..', '..', 'dji_s900_camera_drone.glb')))
DST = '/Game/CTrack/Vehicles/S900'
TMP = '/Game/CTrack/Vehicles/S900_parts_tmp'
BP_PATH = '/Game/CTrack/Vehicles/BP_S900Pawn'
TIP_CM = float(os.environ.get('S900_TIP_RADIUS_CM', '77'))
FEET_CM = float(os.environ.get('S900_FEET_CM', '-44'))
LOG = os.environ.get('S900_LOG', '/tmp/ctrack/make_s900.txt')

eal = unreal.EditorAssetLibrary
os.makedirs(os.path.dirname(LOG), exist_ok=True)
log = open(LOG, 'w')


def p(*a):
    s = ' '.join(str(x) for x in a)
    log.write(s + '\n')
    log.flush()
    unreal.log(s)


def import_glb(dest, combine):
    if eal.does_directory_exist(dest):
        eal.delete_directory(dest)
    eal.make_directory(dest)
    pipe = unreal.InterchangeGenericAssetsPipeline()
    mp = pipe.get_editor_property('mesh_pipeline')
    cur = mp.get_editor_property('combine_static_meshes_behavior')
    members = [n for n in dir(type(cur)) if n.isupper()]
    want = [n for n in members if ('ALL' in n if combine else ('NONE' in n or 'NOT' in n or 'SEPARATE' in n or 'NEVER' in n))]
    p(f'  combine behaviour options {members} (default {cur}) -> {want[:1]}')
    if want:
        mp.set_editor_property('combine_static_meshes_behavior', getattr(type(cur), want[0]))
    mp.set_editor_property('import_skeletal_meshes', False)
    cm = pipe.get_editor_property('common_meshes_properties')
    cm.set_editor_property('bake_meshes', True)

    params = unreal.ImportAssetParameters()
    params.is_automated = True
    params.replace_existing = True
    try:
        params.override_pipelines.append(pipe)
    except TypeError:
        params.override_pipelines.append(unreal.SoftObjectPath(pipe.get_path_name()))
    im = unreal.InterchangeManager.get_interchange_manager_scripted()
    src = unreal.InterchangeManager.create_source_data(GLB)
    ok = im.import_asset(dest, src, params)
    # save everything the import made (materials too: the importer leaves them unsaved, and a
    # mesh saved without them showed the default material)
    n_saved = 0
    for ref in (ok or []):
        path = str(ref).split("'")[1] if "'" in str(ref) else str(ref)
        obj = unreal.load_object(None, path)
        if obj is not None and eal.save_loaded_asset(obj, only_if_is_dirty=False):
            n_saved += 1
    p(f'  saved {n_saved} imported assets')
    meshes = []
    for path in eal.list_assets(dest, recursive=True):
        a = eal.load_asset(path)
        if isinstance(a, unreal.StaticMesh):
            meshes.append(a)
    p(f'import {"combined" if combine else "parts"} -> {dest}: ok={ok}, {len(meshes)} static meshes')
    return meshes


def front_yaw(parts):
    """yaw [deg] that turns the gimbal (the off-centre lower body part) to +X"""
    best = None
    for m in parts:
        b = m.get_bounds()
        o, e = b.origin, b.box_extent
        r = math.hypot(o.x, o.y)
        name = m.get_name()
        # the gimbal: a 'Drone' part hanging below, ~24 cm off the centre (glTF z +0.24)
        if 'Drone' in name and 10.0 < r < 40.0 and e.z > 15.0:
            p(f'  gimbal candidate {name}: origin ({o.x:.1f}, {o.y:.1f}, {o.z:.1f}) extent ({e.x:.1f}, {e.y:.1f}, {e.z:.1f})')
            if best is None or e.z > best[1]:
                best = (math.degrees(math.atan2(o.y, o.x)), e.z)
    if best is None:
        p('  no gimbal part found - yaw 0')
        return 0.0
    return -best[0]


def main():
    p('GLB', GLB)
    parts = import_glb(TMP, combine=False)
    # front = the model's x: its two landing skids run along x (legs at the sides, z +-0.38 m in
    # the glTF), as on a real S900; the model has no camera gimbal (front_yaw() picked a landing
    # gear retract part on one side and turned the vehicle 90 deg)
    yaw = float(os.environ.get('S900_YAW', '0'))
    # the model's extent from its parts (as imported: cm, z up, origin under the feet)
    half = max(max(abs(m.get_bounds().origin.x) + m.get_bounds().box_extent.x,
                   abs(m.get_bounds().origin.y) + m.get_bounds().box_extent.y) for m in parts)
    feet = min(m.get_bounds().origin.z - m.get_bounds().box_extent.z for m in parts)
    eal.delete_directory(TMP)
    scale = TIP_CM / half
    z_cm = FEET_CM - feet * scale
    p(f'model half-width {half:.1f} cm, feet {feet:.1f} cm -> scale {scale:.3f}, yaw {yaw:.1f}, z {z_cm:.1f} cm')
    meshes = import_glb(DST, combine=True)
    body = max(meshes, key=lambda m: m.get_bounds().box_extent.x * m.get_bounds().box_extent.y)
    b = body.get_bounds()
    p(f'body {body.get_path_name()}: origin ({b.origin.x:.1f}, {b.origin.y:.1f}, {b.origin.z:.1f}) '
      f'extent ({b.box_extent.x:.1f}, {b.box_extent.y:.1f}, {b.box_extent.z:.1f})')

    if eal.does_asset_exist(BP_PATH):
        eal.delete_asset(BP_PATH)
    # by object: the commandlet's asset registry has not scanned the AirSim plugin's content
    src_bp = unreal.load_asset('/AirSim/Blueprints/BP_FlyingPawn')
    bp = unreal.AssetToolsHelpers.get_asset_tools().duplicate_asset(
        BP_PATH.rsplit('/', 1)[1], BP_PATH.rsplit('/', 1)[0], src_bp)
    p('duplicated', bp.get_path_name() if bp else None)
    sub = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    lib = unreal.SubobjectDataBlueprintFunctionLibrary
    done = set()
    for h in sub.k2_gather_subobject_data_for_blueprint(bp):
        obj = lib.get_object(lib.get_data(h))
        name = str(lib.get_variable_name(lib.get_data(h)))
        if name in done or obj is None:
            continue
        done.add(name)
        if name == 'BodyMesh':
            # BodyMesh is the ROOT: its own offset / rotation are replaced by the vehicle pose (the
            # first version floated 0.44 m with the gimbal sideways), so it is emptied and the S900
            # hangs under it as a child with its own transform
            obj.set_editor_property('static_mesh', None)
            obj.set_collision_profile_name('NoCollision')
            params = unreal.AddNewSubobjectParams(parent_handle=h, new_class=unreal.StaticMeshComponent,
                                                  blueprint_context=bp)
            res = sub.add_new_subobject(params)
            nh = res[0] if isinstance(res, tuple) else res
            sub.rename_subobject(nh, unreal.Text('S900Mesh'))
            m = lib.get_object(lib.get_data(nh))
            m.set_editor_property('static_mesh', body)
            m.set_editor_property('relative_scale3d', unreal.Vector(scale, scale, scale))
            m.set_editor_property('relative_rotation', unreal.Rotator(roll=0.0, pitch=0.0, yaw=yaw))
            m.set_editor_property('relative_location', unreal.Vector(0.0, 0.0, z_cm))
            # no collision: Cosys-AirSim 3.5's lidar does not skip its own vehicle (UnrealLidarSensor
            # actorArray.Add(actor_) commented out), and the S900's prop tips (0.77 m out, 0.21 m up)
            # are inside the lowest beam (-7 deg from 0.3 m up). Gazebo does the physics.
            m.set_collision_profile_name('NoCollision')
            p(f'  BodyMesh (root) emptied; S900Mesh child: scale {scale:.3f}, yaw {yaw:.1f}, z {z_cm:.1f} cm, '
              f'collision {m.get_collision_profile_name()}')
        elif name.startswith('Prop'):
            obj.set_editor_property('visible', False)
            obj.set_editor_property('hidden_in_game', True)
            obj.set_collision_profile_name('NoCollision')
            p(f'  {name}: hidden, no collision')
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    eal.save_loaded_asset(bp)
    eal.save_loaded_asset(body)
    p('saved', BP_PATH)


try:
    main()
except Exception:
    import traceback
    p(traceback.format_exc())
log.close()
