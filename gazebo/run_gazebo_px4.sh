#!/bin/bash
# Start Gazebo Classic + PX4 SITL (x8) for a layout in one container: test map by default, the SLAM
# yard with SCENARIO_MAP=Yard (the same variable run_unreal.sh takes; MAP also works).
# Start Unreal first (run_unreal.sh); GazeboDrone waits for its API port.
#   GUI=1 ./run_gazebo_px4.sh   also opens gzclient
#   LAYOUT=other.json ./run_gazebo_px4.sh   use another layout file (overrides the map's layout)
#   SCENARIO_CONTAINER=name ./run_gazebo_px4.sh   container name (default scenario-sitl), e.g. for tests
# Logs: gazebo/logs/   Stop: docker stop scenario-sitl (or the name given)
set -e
HERE="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PX4_WS="${PX4_WS:-$HOME/Documents/A4VAI-SITL/PX4-Autopilot}"

MAP_NAME="$(basename "${SCENARIO_MAP:-${MAP:-Scenario}}")"
case "${MAP_NAME}" in
    Yard) DEFAULT_LAYOUT=yard_slam_layout.json ;;
    *)    DEFAULT_LAYOUT=scenario_layout.json ;;
esac
LAYOUT="${LAYOUT:-${HERE}/../layout/${DEFAULT_LAYOUT}}"
LAYOUT_DIR="$(dirname "$(readlink -f "${LAYOUT}")")"   # meshes in the layout are relative to it
"${HERE}/../layout/gen_gazebo_world.py" -l "${LAYOUT}" -o "${HERE}/worlds/scenario.world" --mesh-root /scenario-layout
mkdir -p "${HERE}/logs"
MIRROR_MODELS=$(python3 -c "import json,sys; print(','.join(m['name'] for m in json.load(open(sys.argv[1])).get('moving_obstacles', [])))" "${LAYOUT}")

# gzclient on the NVIDIA GPU (software GL draws a few FPS); NO_GPU=1 to skip
GPU_ARGS=()
if [ -n "${GUI}" ] && [ -z "${NO_GPU}" ] && command -v nvidia-smi >/dev/null; then
    GPU_ARGS=(--gpus all -e NVIDIA_DRIVER_CAPABILITIES=all -e __GLX_VENDOR_LIBRARY_NAME=nvidia)
fi

NAME="${SCENARIO_CONTAINER:-scenario-sitl}"
docker run -d --rm --name "${NAME}" --network host "${GPU_ARGS[@]}" \
    -e SITL_AIRFRAME="${SITL_AIRFRAME:-x8}" -e GUI="${GUI}" -e MIRROR_MODELS="${MIRROR_MODELS}" \
    -e DISPLAY="${DISPLAY}" -v /tmp/.X11-unix:/tmp/.X11-unix \
    -v "${PX4_WS}":/home/user/workspace:ro \
    -v "${HERE}":/scenario:ro \
    -v "${LAYOUT_DIR}":/scenario-layout:ro \
    -v "${HERE}/logs":/scenario-logs \
    --entrypoint bash px4io/px4-dev-simulation-focal:latest /scenario/scenario_sitl_entry.sh
echo "${NAME} started; logs in ${HERE}/logs"
