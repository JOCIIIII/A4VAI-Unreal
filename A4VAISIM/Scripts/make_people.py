"""People for search missions: UE5's template mannequins (Manny, Quinn) as STATIC meshes in /Game/CTrack/People,
so Cosys-AirSim can spawn them anywhere at runtime (simSpawnObject spawns static meshes by name; simListAssets
lists them) and the lidar sees them (complex-as-simple collision). Standing = the reference pose; a lying person is
the same mesh spawned rotated.

  1. copy the template's Mannequins content in (NOT committed - only the converter needs it):
       cp -r $UE/Templates/TemplateResources/High/Characters/Content/Mannequins/{Meshes,Materials,Textures,Rigs} \\
             A4VAISIM/Content/Characters/Mannequins/
  2. run (Unreal closed; GeometryScripting is an editor plugin of the project):
       $UE/Engine/Binaries/Linux/UnrealEditor-Cmd "$PWD/A4VAISIM/A4VAISIM.uproject" \\
           -run=pythonscript -script="$PWD/A4VAISIM/Scripts/make_people.py" -nullrhi -unattended
  3. remove A4VAISIM/Content/Characters again; the static meshes keep the project's own materials
     (Config/DefaultGame.ini cooks /Game/CTrack/People although no map places them)

Meshes: SM_Person_Manny, SM_Person_Quinn (feet at the origin, about 1.8 / 1.7 m tall, X forward).
env: PEOPLE_LOG (default /tmp/ctrack/make_people.txt)
"""
import os

import unreal

LOG = os.environ.get('PEOPLE_LOG', '/tmp/ctrack/make_people.txt')
DST = '/Game/CTrack/People'
SOURCES = {'SM_Person_Manny': '/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple',
           'SM_Person_Quinn': '/Game/Characters/Mannequins/Meshes/SKM_Quinn_Simple'}
# clothes-like colours from the project's own material instances (no template textures in the build)
MATERIALS = {'SM_Person_Manny': ['/Game/CTrack/Materials/MI_blue', '/Game/CTrack/Materials/MI_gray'],
             'SM_Person_Quinn': ['/Game/CTrack/Materials/MI_brown', '/Game/CTrack/Materials/MI_gray']}

os.makedirs(os.path.dirname(LOG), exist_ok=True)
log = open(LOG, 'w')


def say(msg):
    unreal.log(msg)
    log.write(msg + '\n')
    log.flush()


al = unreal.EditorAssetLibrary
gs = unreal.GeometryScript_AssetUtils
for name, src in SOURCES.items():
    skm = unreal.load_asset(src)
    if skm is None:
        say(f'{name}: {src} not found - copy the template mannequins first')
        continue
    mesh = unreal.DynamicMesh()
    opts = unreal.GeometryScriptCopyMeshFromAssetOptions()
    lod = unreal.GeometryScriptMeshReadLOD()
    res = gs.copy_mesh_from_skeletal_mesh(skm, mesh, opts, lod)
    out = res[-1] if isinstance(res, tuple) else None
    say(f'{name}: copied {src} ({mesh.get_triangle_count() if hasattr(mesh, "get_triangle_count") else "?"} triangles, '
        f'outcome {out})')
    path = f'{DST}/{name}'
    if al.does_asset_exist(path):
        al.delete_asset(path)
    copts = unreal.GeometryScriptCreateNewStaticMeshAssetOptions()
    copts.set_editor_property('enable_collision', True)
    copts.set_editor_property('collision_mode', unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
    res = unreal.GeometryScript_NewAssetUtils.create_new_static_mesh_asset_from_mesh(mesh, path, copts)
    sm = res[0] if isinstance(res, tuple) else res
    if sm is None:
        say(f'{name}: creating {path} failed: {res}')
        continue
    mats = [unreal.load_asset(m) for m in MATERIALS[name]]
    slots = sm.get_editor_property('static_materials')
    for i in range(len(slots)):
        m = mats[min(i, len(mats) - 1)]
        if m is not None:
            sm.set_material(i, m)
    box = sm.get_bounding_box()
    say(f'{name}: {path}, {len(slots)} material slots, bounds min {box.min} max {box.max}')
    al.save_asset(path, only_if_is_dirty=False)
say('done')
log.close()
