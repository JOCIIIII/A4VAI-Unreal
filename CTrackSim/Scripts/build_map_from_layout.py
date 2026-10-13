"""Place the C-Track layout (../../layout/ctrack_layout.json) into /Game/CTrack/Maps/CTrack.

Idempotent: actors tagged 'CTrackLayout' are deleted and re-spawned on every run.
Track frame == Unreal frame relative to the Start helipad (PlayerStart, NED origin), meters -> cm.

Moving obstacles: a mesh-less root actor named after the obstacle (e.g. RCCart_C) sits at the
ground point, like the Gazebo model origin; the parts are attached to it. GazeboDrone mirrors the
Gazebo model pose onto it by object name (simSetObjectPose).

Run headless:
  UnrealEditor-Cmd CTrackSim.uproject -run=pythonscript -script=Scripts/build_map_from_layout.py -nullrhi -unattended
"""
import json
import os
import uuid

import unreal

MAP_PATH = "/Game/CTrack/Maps/CTrack"
MAT_DIR = "/Game/CTrack/Materials"
BASE_MAT = f"{MAT_DIR}/M_CTrackColor"
TAG = "CTrackLayout"
M = 100.0

LAYOUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "layout", "ctrack_layout.json")

COLORS = {
    "orange": (1.0, 0.45, 0.0),
    "yellow": (1.0, 0.8, 0.0),
    "brown": (0.45, 0.3, 0.15),
    "blue": (0.2, 0.35, 0.8),
    "gray": (0.5, 0.5, 0.5),
    "green": (0.0, 0.5, 0.4),
    "white": (0.9, 0.9, 0.9),
}
MESHES = {
    "box": "/Engine/BasicShapes/Cube",          # 1 m cube, pivot at center
    "cylinder": "/Engine/BasicShapes/Cylinder",  # 1 m diameter x 1 m, pivot at center
}

asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
mel = unreal.MaterialEditingLibrary
eal = unreal.EditorAssetLibrary
level_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)


def base_material():
    if eal.does_asset_exist(BASE_MAT):
        return unreal.load_asset(BASE_MAT)
    mat = asset_tools.create_asset("M_CTrackColor", MAT_DIR, unreal.Material, unreal.MaterialFactoryNew())
    param = mel.create_material_expression(mat, unreal.MaterialExpressionVectorParameter, -300, 0)
    param.set_editor_property("parameter_name", "Color")
    param.set_editor_property("default_value", unreal.LinearColor(0.5, 0.5, 0.5, 1.0))
    mel.connect_material_property(param, "", unreal.MaterialProperty.MP_BASE_COLOR)
    rough = mel.create_material_expression(mat, unreal.MaterialExpressionConstant, -300, 200)
    rough.set_editor_property("r", 0.8)
    mel.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)
    mel.recompile_material(mat)
    eal.save_asset(BASE_MAT)
    return mat


DIRT_MAT = f"{MAT_DIR}/M_CTrackDirt"


def dirt_material():
    """Procedural dirt for the field: two world-position noises (5 m patches, 20 cm grain) blend
    dark and light soil browns; rough, no texture assets needed."""
    if eal.does_asset_exist(DIRT_MAT):
        return unreal.load_asset(DIRT_MAT)
    mat = asset_tools.create_asset("M_CTrackDirt", MAT_DIR, unreal.Material, unreal.MaterialFactoryNew())

    def noise(x, y, scale, levels):
        n = mel.create_material_expression(mat, unreal.MaterialExpressionNoise, x, y)
        for prop, val in (("scale", scale), ("levels", levels), ("output_min", 0.0), ("output_max", 1.0)):
            try:
                n.set_editor_property(prop, val)
            except Exception as e:  # property names differ between engine versions
                unreal.log_warning(f"dirt noise: {prop}: {e}")
        return n

    def color(x, y, rgb):
        c = mel.create_material_expression(mat, unreal.MaterialExpressionConstant3Vector, x, y)
        c.set_editor_property("constant", unreal.LinearColor(rgb[0], rgb[1], rgb[2], 1.0))
        return c

    patches = noise(-900, -100, 0.0015, 4)          # Unreal units: 1/cm -> ~5 m patches
    grain = noise(-900, 200, 0.05, 2)               # ~20 cm grain
    lerp = mel.create_material_expression(mat, unreal.MaterialExpressionLinearInterpolate, -500, 0)
    mel.connect_material_expressions(color(-700, -300, (0.17, 0.12, 0.08)), "", lerp, "A")
    mel.connect_material_expressions(color(-700, -200, (0.40, 0.30, 0.19)), "", lerp, "B")
    mel.connect_material_expressions(patches, "", lerp, "Alpha")
    shade = mel.create_material_expression(mat, unreal.MaterialExpressionLinearInterpolate, -500, 250)
    lo = mel.create_material_expression(mat, unreal.MaterialExpressionConstant, -700, 250)
    lo.set_editor_property("r", 0.8)
    hi = mel.create_material_expression(mat, unreal.MaterialExpressionConstant, -700, 320)
    hi.set_editor_property("r", 1.15)
    mel.connect_material_expressions(lo, "", shade, "A")
    mel.connect_material_expressions(hi, "", shade, "B")
    mel.connect_material_expressions(grain, "", shade, "Alpha")
    mul = mel.create_material_expression(mat, unreal.MaterialExpressionMultiply, -300, 100)
    mel.connect_material_expressions(lerp, "", mul, "A")
    mel.connect_material_expressions(shade, "", mul, "B")
    mel.connect_material_property(mul, "", unreal.MaterialProperty.MP_BASE_COLOR)
    rough = mel.create_material_expression(mat, unreal.MaterialExpressionConstant, -300, 300)
    rough.set_editor_property("r", 0.95)
    mel.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)
    mel.recompile_material(mat)
    eal.save_asset(DIRT_MAT)
    return mat


def color_material(color):
    path = f"{MAT_DIR}/MI_{color}"
    if eal.does_asset_exist(path):
        return unreal.load_asset(path)
    mi = asset_tools.create_asset(f"MI_{color}", MAT_DIR, unreal.MaterialInstanceConstant,
                                  unreal.MaterialInstanceConstantFactoryNew())
    mel.set_material_instance_parent(mi, base_material())
    r, g, b = COLORS.get(color, COLORS["gray"])
    mel.set_material_instance_vector_parameter_value(mi, "Color", unreal.LinearColor(r, g, b, 1.0))
    eal.save_asset(path)
    return mi


def spawn_shape(name, shape, size, color, x, y, z_bottom, yaw_deg=0.0, movable=False, collision=True):
    loc = unreal.Vector(x * M, y * M, (z_bottom + size[2] / 2) * M)
    actor = actor_sub.spawn_actor_from_class(unreal.StaticMeshActor, loc, unreal.Rotator(0, 0, yaw_deg))
    # AirSim's simSetObjectPose/simGetObjectPose look actors up by object name, not label
    actor.rename(name)
    actor.set_actor_label(name)
    comp = actor.static_mesh_component
    comp.set_mobility(unreal.ComponentMobility.MOVABLE if movable else unreal.ComponentMobility.STATIC)
    comp.set_static_mesh(unreal.load_asset(MESHES[shape]))
    comp.set_material(0, color_material(color))
    if not collision:
        comp.set_collision_profile_name("NoCollision")
    actor.set_actor_scale3d(unreal.Vector(*size))
    actor.tags = [TAG, name]
    actor.set_folder_path(f"CTrack/{name.split('_')[0]}")
    if actor.get_name() != name:
        unreal.log_warning(f"{name}: object name is '{actor.get_name()}' (rename refused)")
    return actor


def main():
    with open(LAYOUT) as f:
        lay = json.load(f)

    if not level_sub.load_level(MAP_PATH):
        raise RuntimeError(f"cannot load {MAP_PATH}; run create_base_map.py first")

    for a in actor_sub.get_all_level_actors():
        if a.actor_has_tag(TAG) or a.get_actor_label() == "Field_Ground":
            # free the name first: a destroyed actor keeps it until GC and rename() onto it is fatal
            a.rename(f"{a.get_name()}_old_{uuid.uuid4().hex[:8]}")
            actor_sub.destroy_actor(a)
        elif isinstance(a, unreal.PlayerStart):
            # NED origin on the ground so heights match Gazebo (ground z = 0)
            a.set_actor_location(unreal.Vector(0, 0, 0), False, False)

    # Ground: 1 m thick box with its top at Z=0. (The engine Plane has no simple collision,
    # so AirSim's own physics falls through it.)
    (x0, x1), (y0, y1) = lay["field"]["x_range"], lay["field"]["y_range"]
    ground = spawn_shape("Field_Ground", "box", [x1 - x0, y1 - y0, 1.0], "gray", (x0 + x1) / 2, (y0 + y1) / 2, -1.0)
    if lay["field"].get("ground", "dirt") == "dirt":
        ground.static_mesh_component.set_material(0, dirt_material())

    for o in lay["obstacles"]:
        spawn_shape(o["name"], o["shape"], o["size"], o["color"], *o["pos"], 0.0, o.get("yaw_deg", 0.0))

    for m in lay.get("moving_obstacles", []):
        sx, sy = m["start"]
        root = actor_sub.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(sx * M, sy * M, 0.0))
        root.rename(m["name"])
        root.set_actor_label(m["name"])
        root.static_mesh_component.set_mobility(unreal.ComponentMobility.MOVABLE)
        root.tags = [TAG, m["name"]]
        root.set_folder_path(f"CTrack/{m['name'].split('_')[0]}")
        for p in m["parts"]:
            ox, oy, oz = p["offset"]
            a = spawn_shape(f"{m['name']}_{p['name']}", p["shape"], p["size"], p["color"],
                            sx + ox, sy + oy, oz, movable=True)
            a.attach_to_actor(root, "", unreal.AttachmentRule.KEEP_WORLD,
                              unreal.AttachmentRule.KEEP_WORLD, unreal.AttachmentRule.KEEP_WORLD, False)

    for wz in lay.get("wind_zones", []):
        for i, (fx, fy) in enumerate(wz["fans"], 1):
            spawn_shape(f"{wz['name']}_Fan{i}", "box", wz["fan_size"], "green", fx, fy, 0.0)

    for wp, (x, y) in lay["waypoints"].items():
        color = "green" if wp in ("START", "GOAL") else "white"
        spawn_shape(f"Marker_{wp}", "cylinder", [1.0, 1.0, 0.01], color, x, y, 0.0, collision=False)

    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    if not unreal.EditorLoadingAndSavingUtils.save_map(world, MAP_PATH):
        raise RuntimeError(f"failed to save {MAP_PATH}")
    names = sorted(a.get_name() for a in actor_sub.get_all_level_actors() if a.actor_has_tag(TAG))
    unreal.log_warning(f"CTrack layout placed: {len(names)} actors: {', '.join(names)}")


main()
