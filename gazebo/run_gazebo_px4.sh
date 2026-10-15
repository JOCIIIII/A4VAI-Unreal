#!/bin/bash
# Start Gazebo Classic + PX4 SITL (x8) for a layout in one container: C-Track by default, the SLAM
# yard with CTRACK_MAP=Yard (the same variable run_unreal.sh takes; MAP also works).
# Start Unreal first (run_unreal.sh); GazeboDrone waits for its API port.
#   GUI=1 ./run_gazebo_px4.sh   also opens gzclient
#   LAYOUT=other.json ./run_gazebo_px4.sh   use another layout file (overrides the map's layout)
#   CTRACK_CONTAINER=name ./run_gazebo_px4.sh   container name (default ctrack-sitl), e.g. for tests
# Logs: gazebo/logs/   Stop: docker stop ctrack-sitl (or the name given)
set -e
HERE="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PX4_WS="${PX4_WS:-$HOME/Documents/A4VAI-SITL/PX4-Autopilot}"

MAP_NAME="$(basename "${CTRACK_MAP:-${MAP:-CTrack}}")"
case "${MAP_NAME}" in
    Yard) DEFAULT_LAYOUT=yard_slam_layout.json ;;
    *)    DEFAULT_LAYOUT=ctrack_layout.json ;;
esac
LAYOUT="${LAYOUT:-${HERE}/../layout/${DEFAULT_LAYOUT}}"
LAYOUT_DIR="$(dirname "$(readlink -f "${LAYOUT}")")"   # meshes in the layout are relative to it
"${HERE}/../layout/gen_gazebo_world.py" -l "${LAYOUT}" -o "${HERE}/worlds/ctrack.world" --mesh-root /ctrack-layout
mkdir -p "${HERE}/logs"
MIRROR_MODELS=$(python3 -c "import json,sys; print(','.join(m['name'] for m in json.load(open(sys.argv[1])).get('moving_obstacles', [])))" "${LAYOUT}")

# gzclient on the NVIDIA GPU (software GL draws a few FPS); NO_GPU=1 to skip
GPU_ARGS=()
if [ -n "${GUI}" ] && [ -z "${NO_GPU}" ] && command -v nvidia-smi >/dev/null; then
    GPU_ARGS=(--gpus all -e NVIDIA_DRIVER_CAPABILITIES=all -e __GLX_VENDOR_LIBRARY_NAME=nvidia)
fi

NAME="${CTRACK_CONTAINER:-ctrack-sitl}"
docker run -d --rm --name "${NAME}" --network host "${GPU_ARGS[@]}" \
    -e SITL_AIRFRAME="${SITL_AIRFRAME:-x8}" -e GUI="${GUI}" -e MIRROR_MODELS="${MIRROR_MODELS}" \
    -e DISPLAY="${DISPLAY}" -v /tmp/.X11-unix:/tmp/.X11-unix \
    -v "${PX4_WS}":/home/user/workspace:ro \
    -v "${HERE}":/ctrack:ro \
    -v "${LAYOUT_DIR}":/ctrack-layout:ro \
    -v "${HERE}/logs":/ctrack-logs \
    --entrypoint bash px4io/px4-dev-simulation-focal:latest /ctrack/ctrack_sitl_entry.sh
echo "${NAME} started; logs in ${HERE}/logs"
