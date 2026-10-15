#!/bin/bash
# Start Gazebo Classic + PX4 SITL (x8) for the yard (or C-Track) layout in one container.
# Start Unreal first (run_unreal.sh); GazeboDrone waits for its API port.
#   GUI=1 ./run_gazebo_px4.sh   also opens gzclient
#   LAYOUT=other.json ./run_gazebo_px4.sh   use another layout file (default: the SLAM yard;
#                                           C-Track: LAYOUT=../layout/ctrack_layout.json)
# Logs: gazebo/logs/   Stop: docker stop ctrack-sitl
set -e
HERE="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PX4_WS="${PX4_WS:-$HOME/Documents/A4VAI-SITL/PX4-Autopilot}"

LAYOUT="${LAYOUT:-${HERE}/../layout/yard_slam_layout.json}"   # C-Track: LAYOUT=../layout/ctrack_layout.json
LAYOUT_DIR="$(dirname "$(readlink -f "${LAYOUT}")")"   # meshes in the layout are relative to it
"${HERE}/../layout/gen_gazebo_world.py" -l "${LAYOUT}" -o "${HERE}/worlds/ctrack.world" --mesh-root /ctrack-layout
mkdir -p "${HERE}/logs"
MIRROR_MODELS=$(python3 -c "import json,sys; print(','.join(m['name'] for m in json.load(open(sys.argv[1])).get('moving_obstacles', [])))" "${LAYOUT}")

# gzclient on the NVIDIA GPU (software GL draws a few FPS); NO_GPU=1 to skip
GPU_ARGS=()
if [ -n "${GUI}" ] && [ -z "${NO_GPU}" ] && command -v nvidia-smi >/dev/null; then
    GPU_ARGS=(--gpus all -e NVIDIA_DRIVER_CAPABILITIES=all -e __GLX_VENDOR_LIBRARY_NAME=nvidia)
fi

docker run -d --rm --name ctrack-sitl --network host "${GPU_ARGS[@]}" \
    -e SITL_AIRFRAME="${SITL_AIRFRAME:-x8}" -e GUI="${GUI}" -e MIRROR_MODELS="${MIRROR_MODELS}" \
    -e DISPLAY="${DISPLAY}" -v /tmp/.X11-unix:/tmp/.X11-unix \
    -v "${PX4_WS}":/home/user/workspace:ro \
    -v "${HERE}":/ctrack:ro \
    -v "${LAYOUT_DIR}":/ctrack-layout:ro \
    -v "${HERE}/logs":/ctrack-logs \
    --entrypoint bash px4io/px4-dev-simulation-focal:latest /ctrack/ctrack_sitl_entry.sh
echo "ctrack-sitl started; logs in ${HERE}/logs"
