# C-Track Sim (UE 5.8.2 + Cosys-AirSim 3.5.0 + PX4 v1.16 / Gazebo Classic)

Simulation of the C-Track flight test field (A: path planning around tents, B: path following
through a fan wind zone, C: collision avoidance between poles, a wall, a balloon figure and a
crossing RC cart).

Gazebo Classic does the dynamics (PX4 SITL, x8); Unreal + Cosys-AirSim renders and simulates the
lidar/cameras, fed with the vehicle pose by GazeboDrone (`ExternalPhysicsEngine`). Every obstacle
exists in both worlds at the same place: both are generated from `layout/ctrack_layout.json`.
Moving obstacles and the wind zone live in Gazebo (plugins); GazeboDrone mirrors the moving
obstacles onto Unreal actors of the same name.

```
layout/ctrack_layout.json        single source: waypoints, obstacles, RC cart, wind zone
layout/gen_gazebo_world.py       -> gazebo/worlds/ctrack.world (run by run_gazebo_px4.sh)
CTrackSim/                       Unreal project (map /Game/CTrack/Maps/CTrack)
  Scripts/create_base_map.py       empty map, lights, PlayerStart at Start H (run once)
  Scripts/build_map_from_layout.py ground + layout into the map (rerunnable)
  Scripts/make_s900_pawn.py        optional vehicle look (model not included, see below)
gazebo/
  run_gazebo_px4.sh                gzserver + x8 + GazeboDrone + PX4 in container ctrack-sitl
  ctrack_sitl_entry.sh             what runs inside that container
  plugins/src                      wind zone and moving obstacle Gazebo plugins
patches/cosys-airsim/            our changes to Cosys-AirSim 5.8-v3.5.0 (applied by setup_deps.sh)
settings/                        AirSim settings (see below)
tools/fly_ctrack_check.py        offboard flight over the route with consistency checks
setup_deps.sh                    builds the plugin, GazeboDrone and the Gazebo plugins
package.sh                       builds the release assets (packaged Unreal build, Gazebo binaries)
```

## Requirements
- Ubuntu 22.04 (tested) with an NVIDIA GPU (Vulkan)
- [Unreal Engine 5.8.2 for Linux](https://www.unrealengine.com/linux) (Epic account; not
  redistributable) - only for the editor project; the release build runs without it
- Docker with `px4io/px4-dev-simulation-focal`
- PX4-Autopilot v1.16 built for SITL with the gazebo-classic `x8` airframe (2000), laid out as
  `$PX4_WS/PX4-Autopilot/build/px4_sitl_default` (default `PX4_WS=~/Documents/A4VAI-SITL/PX4-Autopilot`)

## Setup without Unreal Engine (release build)
Download from the GitHub release and extract in the repository root:
```bash
mkdir -p packaged && tar -xzf CTrackSim-Linux.tar.gz -C packaged   # packaged/CTrackSim-Linux/
tar -xzf ctrack-gazebo-prebuilt.tar.gz                              # gazebo/bin, gazebo/plugins/build
```
`run_unreal.sh` then runs the packaged build (or set `CTRACK_PACKAGED=/path/to/CTrackSim-Linux`).
It uses Cosys-AirSim's default vehicle pawn. Instead of the prebuilt Gazebo binaries you can build
them without Unreal Engine: `./setup_deps.sh --gazebo-only`.

## Setup with Unreal Engine (editor project)
```bash
UE_ROOT=/path/to/Linux_Unreal_Engine_5.8.2 ./setup_deps.sh
```
Clones Cosys-AirSim `5.8-v3.5.0` into `~/Documents/InhouseSim-deps` (`DEPS_DIR`), applies
`patches/cosys-airsim`, builds AirLib with Unreal's bundled clang into `CTrackSim/Plugins/AirSim`
and the editor target, builds AirLib with gcc + GazeboDrone in the PX4 dev image
(`gazebo/bin/GazeboDrone`), and the Gazebo plugins (`gazebo/plugins/build`).
`./package.sh` builds the release assets from a clean clone (see the script).

## Run
```bash
./run_unreal.sh [settings.json]  # wait for the window / API port 41451
./gazebo/run_gazebo_px4.sh       # GUI=1 for gzclient, LAYOUT=other.json; logs in gazebo/logs/
# PX4: MAVLink udp 14540 (offboard) / 14550 (GCS) on localhost
docker stop ctrack-sitl          # stop
```
The PX4 workspace is mounted read-only; PX4 runs in its own rootfs, so its parameters start from
the airframe defaults every run. The container uses the host network.

Settings (all: `RPLIDAR_A3` CPU lidar, 32 channels, 10 Hz, vertical FOV -7..52 deg):

| file | use |
|---|---|
| `settings_gazebo.json` | Gazebo setup, range 40 m |
| `settings_gazebo_policy30m.json` | same, lidar points drawn in the view |
| `settings_gazebo_policy10m.json` | range 10 m |
| `settings_standalone.json` | AirSim only (SimpleFlight physics, spawn 1 m up) for quick checks |

## Vehicle look (S900) - not included
The Gazebo settings use an S900 octocopter look built by `CTrackSim/Scripts/make_s900_pawn.py`
from a 3D model that may not be redistributed, so the model and its imported assets are not in
this repository or the release build. Without them `run_unreal.sh` drops the pawn override and Cosys-AirSim uses its
default multirotor pawn; physics, sensors and poses are unchanged (only the look differs).
Note for the S900 pawn: its mesh has no collision, since the Cosys 3.5 lidar does not skip its own
vehicle and the -7 deg beams would hit the prop tips.

## Frames
Track frame (meters): origin = Start helipad, +X along the 100 m side, +Y toward the C lane, +Z up.
- Unreal: same axes; PlayerStart at the origin on the ground = AirSim NED origin.
- Gazebo (ENU): x = X, y = -Y, z = Z; the vehicle spawns at the origin facing +x.
- PX4 local NED: north = -Y, east = X.

## Layout
`layout/ctrack_layout.json` lists what each object is and which values are assumed rather than
measured (`assumed`). Changes so far: the pole field is 1-2-3 rows of 0.5 m poles (X 66 / 56 / 46,
6 m apart) instead of the drawing's 2+1+2 field, so an x8 (prop tips 0.77 m) fits through and the
lidar resolves them at range.

After editing the layout, regenerate the Unreal map (close Unreal first; the commandlet saves it):
```bash
UE=~/Downloads/Linux_Unreal_Engine_5.8.2
$UE/Engine/Binaries/Linux/UnrealEditor-Cmd "$PWD/CTrackSim/CTrackSim.uproject" \
    -run=pythonscript -script="$PWD/CTrackSim/Scripts/build_map_from_layout.py" -nullrhi -unattended
```
The Gazebo world is regenerated on every `run_gazebo_px4.sh`.

## Gazebo plugins
- `libctrack_wind_zone.so`: inside the box, drag F = 0.5 rho CdA |v_rel| v_rel on the vehicle
  (v_rel = wind - vehicle velocity). The PX4 x8 motor models have `enable_wind` off, so the stock
  `windy.world` wind does not act on the x8.
- `libctrack_moving_obstacle.so`: shuttles a kinematic model between two points; starts when the
  trigger model comes within `trigger_distance` of `trigger_point`.

## Patches to Cosys-AirSim 5.8-v3.5.0
- `0001` lidar: `DrawDebugPoints` drew from AirSim's physics thread, which asserts in UE 5.8;
  hit points are now drawn on the game thread (also fixes an out-of-range draw index).
- `0002` camera director: the "fly with me" view chases behind the vehicle along its heading.
- `0003` GazeboDrone: upstream applies the first entry of `~/pose/local/info` to the AirSim
  vehicle, but that order is not stable and moving obstacles appear in it. The vehicle is now
  selected by name (`GAZEBO_DRONE_MODEL`) and `GAZEBO_MIRROR_MODELS` are mirrored onto Unreal
  actors (simSetObjectPose).

## Known issues
- After Unreal has run for hours, GazeboDrone sometimes connects but never receives a pose
  (lidar keeps publishing from the spawn point). Restarting Unreal fixes it; cause unknown.

## License
MIT (`LICENSE`), which also covers the patches in `patches/`. Cosys-AirSim is MIT licensed
(Cosys-Lab / Microsoft); Unreal Engine is subject to the Unreal Engine EULA and is not part of
this repository.
