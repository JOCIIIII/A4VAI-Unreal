"""Create an empty base map: CTRACK_MAP (default /Game/CTrack/Maps/Yard; C-Track: /Game/CTrack/Maps/CTrack).

Frame: Unreal world origin = Start helipad (H). +X along the 100 m track direction
(left->right in the layout drawing), +Y toward the C (collision avoidance) lane, +Z up.
Field: 100 m x 50 m, X in [-5, 95] m, Y in [-12, 38] m. A lane at Y=0, C lane at Y=26 m.
Obstacles are added later from the shared obstacle definition (Unreal + Gazebo).

Run headless:
  UnrealEditor-Cmd CTrackSim.uproject -run=pythonscript -script=Scripts/create_base_map.py -nullrhi -unattended
"""
import os

import unreal

MAP_PATH = os.environ.get("CTRACK_MAP", "/Game/CTrack/Maps/Yard")
M = 100.0  # Unreal units (cm) per meter

FIELD_X = (-5.0, 95.0)
FIELD_Y = (-12.0, 38.0)

level_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

if unreal.EditorAssetLibrary.does_asset_exist(MAP_PATH):
    unreal.log_warning(f"{MAP_PATH} already exists, leaving it untouched")
else:
    level_sub.new_level(MAP_PATH)

    def spawn(cls, loc_m, rot=unreal.Rotator(0, 0, 0), label=None):
        a = actor_sub.spawn_actor_from_class(cls, unreal.Vector(*(v * M for v in loc_m)), rot)
        if label:
            a.set_actor_label(label)
        return a

    # Ground and obstacles: build_map_from_layout.py
    cx, cy = sum(FIELD_X) / 2, sum(FIELD_Y) / 2

    # Lighting
    sun = spawn(unreal.DirectionalLight, (cx, cy, 50.0), unreal.Rotator(0, -50, 30), "Sun")
    sun.light_component.set_editor_property("atmosphere_sun_light", True)
    spawn(unreal.SkyAtmosphere, (0, 0, 0), label="SkyAtmosphere")
    sky = spawn(unreal.SkyLight, (0, 0, 10.0), label="SkyLight")
    sky.light_component.set_editor_property("real_time_capture", True)
    spawn(unreal.ExponentialHeightFog, (0, 0, 0), label="HeightFog")

    # Vehicle spawn: Start helipad (AirSim NED origin), on the ground so heights match Gazebo
    spawn(unreal.PlayerStart, (0.0, 0.0, 0.0), label="PlayerStart_StartH")

    level_sub.save_current_level()
    unreal.log(f"Created {MAP_PATH}")
