#!/usr/bin/env python3
"""Generate the Gazebo Classic world from a layout (default ctrack_layout.json; yard_slam_layout.json for the yard).

Track frame -> Gazebo ENU: x = X, y = -Y, z = Z, yaw = -yaw (see ctrack_layout.json).
Spawn the vehicle at the Start helipad (Gazebo origin) facing +x so the AirSim view
(fed by GazeboDrone) lines up with the Unreal map.

Usage: ./gen_gazebo_world.py [-o worlds/ctrack.world]
"""
import argparse
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))

COLORS = {
    "orange": "1.0 0.45 0.0 1",
    "yellow": "1.0 0.8 0.0 1",
    "brown": "0.45 0.3 0.15 1",
    "blue": "0.2 0.35 0.8 1",
    "gray": "0.5 0.5 0.5 1",
    "green": "0.0 0.5 0.4 1",
    "white": "0.9 0.9 0.9 1",
}

# Same physics block as PX4's gazebo-classic worlds (250 Hz lockstep with SITL)
PHYSICS = """    <physics name='default_physics' default='0' type='ode'>
      <gravity>0 0 -9.8066</gravity>
      <ode>
        <solver>
          <type>quick</type>
          <iters>10</iters>
          <sor>1.3</sor>
          <use_dynamic_moi_rescaling>0</use_dynamic_moi_rescaling>
        </solver>
        <constraints>
          <cfm>0</cfm>
          <erp>0.2</erp>
          <contact_max_correcting_vel>100</contact_max_correcting_vel>
          <contact_surface_layer>0.001</contact_surface_layer>
        </constraints>
      </ode>
      <max_step_size>0.004</max_step_size>
      <real_time_factor>1</real_time_factor>
      <real_time_update_rate>250</real_time_update_rate>
      <magnetic_field>6.0e-6 2.3e-5 -4.2e-5</magnetic_field>
    </physics>"""


def to_gz(x, y, z=0.0, yaw_deg=0.0):
    return f"{x:.3f} {-y:.3f} {z:.3f} 0 0 {math.radians(-yaw_deg):.6f}"


def geometry(shape, size):
    if shape == "box":
        return f"<box><size>{size[0]} {size[1]} {size[2]}</size></box>"
    if shape == "cylinder":
        return f"<cylinder><radius>{size[0] / 2}</radius><length>{size[2]}</length></cylinder>"
    raise ValueError(f"unsupported shape: {shape}")


def material(color):
    rgba = COLORS.get(color, COLORS["gray"])
    return f"<material><ambient>{rgba}</ambient><diffuse>{rgba}</diffuse></material>"


def shape_elems(name, shape, size, color, pose="0 0 0 0 0 0", collision=True, visual=True):
    geo = geometry(shape, size)
    out = []
    if collision:
        out.append(f"        <collision name='{name}_collision'><pose>{pose}</pose>"
                   f"<geometry>{geo}</geometry></collision>")
    if visual:
        out.append(f"        <visual name='{name}_visual'><pose>{pose}</pose>"
                   f"<geometry>{geo}</geometry>{material(color)}</visual>")
    return "\n".join(out)


def mesh_model(m, mesh_root):
    """Static mesh from the layout "meshes" list (.obj, already in Gazebo ENU, metres)."""
    uri = f"file://{mesh_root}/{m['file']}.obj"
    rgba = "{} {} {} 1".format(*m.get("rgb", (0.5, 0.5, 0.5)))
    geo = f"<geometry><mesh><uri>{uri}</uri></mesh></geometry>"
    coll = (f"        <collision name='{m['name']}_collision'>{geo}</collision>\n"
            if m.get("collision", False) else "")
    return f"""    <model name='{m['name']}'>
      <static>true</static>
      <link name='link'>
{coll}        <visual name='{m['name']}_visual'>{geo}<material><ambient>{rgba}</ambient><diffuse>{rgba}</diffuse></material></visual>
      </link>
    </model>"""


def static_model(name, shape, size, color, x, y, yaw_deg=0.0, collision=True, z=0.0, visual=True):
    return f"""    <model name='{name}'>
      <static>true</static>
      <pose>{to_gz(x, y, z + size[2] / 2, yaw_deg)}</pose>
      <link name='link'>
{shape_elems(name, shape, size, color, collision=collision, visual=visual)}
      </link>
    </model>"""


def moving_model(m):
    # Kinematic link with gravity off, model origin on the ground: moved by the
    # libctrack_moving_obstacle plugin and mirrored to Unreal by GazeboDrone.
    parts = []
    for p in m["parts"]:
        ox, oy, oz = p["offset"]
        pose = f"{ox:.3f} {-oy:.3f} {oz + p['size'][2] / 2:.3f} 0 0 0"
        parts.append(shape_elems(p["name"], p["shape"], p["size"], p["color"], pose))
    sx, sy = m["start"]
    return f"""    <model name='{m['name']}'>
      <static>false</static>
      <pose>{to_gz(sx, sy)}</pose>
      <link name='link'>
        <gravity>false</gravity>
        <kinematic>true</kinematic>
{chr(10).join(parts)}
      </link>
    </model>"""


def vec_gz(x, y, z=0.0):
    return f"{x:.3f} {-y:.3f} {z:.3f}"


def moving_plugin(m):
    sx, sy = m["start"]
    ex, ey = m["end"]
    trig = ""
    if m.get("trigger_model"):
        trig = (f"\n      <trigger_model>{m['trigger_model']}</trigger_model>"
                f"\n      <trigger_distance>{m.get('trigger_distance', 10.0)}</trigger_distance>")
        if m.get("trigger_point"):
            trig += f"\n      <trigger_point>{vec_gz(*m['trigger_point'])}</trigger_point>"
    return f"""    <plugin name='{m['name']}_motion' filename='libctrack_moving_obstacle.so'>
      <model>{m['name']}</model>
      <start>{vec_gz(sx, sy)}</start>
      <end>{vec_gz(ex, ey)}</end>
      <speed>{m['speed_mps']}</speed>
      <loop>{str(m.get('loop', True)).lower()}</loop>{trig}
    </plugin>"""


def wind_plugin(wz):
    (x0, x1), (y0, y1), (z0, z1) = wz["x_range"], wz["y_range"], wz["z_range"]
    dx, dy, dz = (c * wz["speed_mps"] for c in wz["direction"])
    return f"""    <plugin name='{wz['name']}' filename='libctrack_wind_zone.so'>
      <model>{wz.get('vehicle_model', 'x8')}</model>
      <min>{x0:.3f} {-y1:.3f} {z0:.3f}</min>
      <max>{x1:.3f} {-y0:.3f} {z1:.3f}</max>
      <velocity>{dx:.3f} {-dy:.3f} {dz:.3f}</velocity>
      <cd_area>{wz.get('cd_area', 0.1)}</cd_area>
    </plugin>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-l", "--layout", default=os.path.join(HERE, "ctrack_layout.json"))
    ap.add_argument("-o", "--output", default=os.path.join(HERE, "..", "gazebo", "worlds", "ctrack.world"))
    ap.add_argument("--mesh-root", help="where the layout's directory is seen by gzserver "
                    "(default: its host path); mesh files are relative to it")
    args = ap.parse_args()
    mesh_root = args.mesh_root or os.path.dirname(os.path.abspath(args.layout))

    with open(args.layout) as f:
        lay = json.load(f)

    models = []
    plugins = [moving_plugin(m) for m in lay.get("moving_obstacles", [])]
    plugins += [wind_plugin(wz) for wz in lay.get("wind_zones", [])]
    for o in lay["obstacles"]:
        models.append(static_model(o["name"], o["shape"], o["size"], o["color"],
                                   *o["pos"], o.get("yaw_deg", 0.0), z=o.get("z", 0.0),
                                   visual=o.get("visual", True)))
    for m in lay.get("meshes", []):
        models.append(mesh_model(m, mesh_root))
    for m in lay.get("moving_obstacles", []):
        models.append(moving_model(m))
    for wz in lay.get("wind_zones", []):
        for i, (fx, fy) in enumerate(wz["fans"], 1):
            models.append(static_model(f"{wz['name']}_Fan{i}", "box", wz["fan_size"], "green", fx, fy))
    # Waypoint markers: visual only, 1 m discs flush with the ground
    for wp, (x, y) in lay["waypoints"].items():
        color = "green" if wp in ("START", "GOAL") else "white"
        models.append(static_model(f"Marker_{wp}", "cylinder", [1.0, 1.0, 0.01], color, x, y, collision=False))

    gui = ""
    if "gui_camera" in lay:   # gzclient start view: x y z roll pitch yaw (Gazebo frame)
        gui = ("    <gui><camera name='user_camera'><pose>{} {} {} {} {} {}</pose></camera></gui>\n"
               .format(*lay["gui_camera"]))

    world = f"""<?xml version="1.0" ?>
<!-- Generated by gen_gazebo_world.py from {os.path.basename(args.layout)}. Do not edit by hand. -->
<sdf version="1.6">
  <world name="default">
{gui}    <include>
      <uri>model://sun</uri>
    </include>
    <include>
      <uri>model://ground_plane</uri>
    </include>
{chr(10).join(models)}
{chr(10).join(plugins)}
{PHYSICS}
  </world>
</sdf>
"""
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w") as f:
        f.write(world)
    print(f"wrote {os.path.abspath(args.output)} ({len(models)} models, {len(plugins)} plugins)")


if __name__ == "__main__":
    main()
