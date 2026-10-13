#!/bin/bash
# Start Gazebo Classic + PX4 SITL (x8) for the C-Track field in one container.
# Start Unreal first (run_unreal.sh); GazeboDrone waits for its API port.
#   GUI=1 ./run_gazebo_px4.sh   also opens gzclient
#   LAYOUT=other.json ./run_gazebo_px4.sh   use another layout file
# Logs: gazebo/logs/   Stop: docker stop ctrack-sitl
set -e
HERE="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PX4_WS="${PX4_WS:-$HOME/Documents/A4VAI-SITL/PX4-Autopilot}"

LAYOUT="${LAYOUT:-${HERE}/../layout/ctrack_layout.json}"
"${HERE}/../layout/gen_gazebo_world.py" -l "${LAYOUT}" -o "${HERE}/worlds/ctrack.world"
mkdir -p "${HERE}/logs"
MIRROR_MODELS=$(python3 -c "import json,sys; print(','.join(m['name'] for m in json.load(open(sys.argv[1])).get('moving_obstacles', [])))" "${LAYOUT}")

docker run -d --rm --name ctrack-sitl --network host \
    -e SITL_AIRFRAME="${SITL_AIRFRAME:-x8}" -e GUI="${GUI}" -e MIRROR_MODELS="${MIRROR_MODELS}" \
    -e DISPLAY="${DISPLAY}" -v /tmp/.X11-unix:/tmp/.X11-unix \
    -v "${PX4_WS}":/home/user/workspace:ro \
    -v "${HERE}":/ctrack:ro \
    -v "${HERE}/logs":/ctrack-logs \
    --entrypoint bash px4io/px4-dev-simulation-focal:latest /ctrack/ctrack_sitl_entry.sh
echo "ctrack-sitl started; logs in ${HERE}/logs"
