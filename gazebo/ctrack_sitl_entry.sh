#!/bin/bash
# Runs inside the ctrack-sitl container (px4io/px4-dev-simulation-focal, host network):
# gzserver (ctrack.world) + x8 at the Start helipad + GazeboDrone -> AirSim + PX4 SITL.
# The PX4 workspace is mounted read-only; PX4 runs in its own rootfs under /tmp.
set -e
PX4_SRC=/home/user/workspace/PX4-Autopilot
PX4_BUILD=${PX4_SRC}/build/px4_sitl_default
MODEL=${SITL_AIRFRAME:-x8}
AIRSIM_HOST=${AIRSIM_HOST:-127.0.0.1}
LOG=/ctrack-logs
mkdir -p ${LOG}

source ${PX4_SRC}/Tools/simulation/gazebo-classic/setup_gazebo.bash ${PX4_SRC} ${PX4_BUILD} > /dev/null
export GAZEBO_PLUGIN_PATH=${GAZEBO_PLUGIN_PATH}:/ctrack/plugins/build
# Gazebo transport on loopback: everything that uses it (gzserver, gz, gzclient, GazeboDrone) runs in
# this container. On the host network it would otherwise advertise the first external interface
# (LAN, Wi-Fi or VPN address, whichever is up when each process starts), which can change or drop.
export GAZEBO_IP=127.0.0.1

gzserver --verbose /ctrack/worlds/ctrack.world > ${LOG}/gzserver.log 2>&1 &

# Spawn at the Start helipad facing +x (Track +X): must match the Unreal PlayerStart.
# (SITL-Runner's harness rewrites this pose with sed: keep the string below as it is.)
SPAWN="--model-name=${MODEL} -x 0 -y 0 -z 0 -Y 0"
GROUND=/ctrack/worlds/ctrack.ground.json
if [ -f "${GROUND}" ]; then
    # the ground relief is a collider in this world: start the vehicle's origin 0.5 m above the
    # highest ground under it, so the unarmed vehicle drops onto the relief. (Spawning into it, as
    # z 0 does on the flat ground plane, leaves the body stuck in the mesh: a trimesh doesn't push
    # a sunk body out like the plane does.)
    SPAWN=$(python3 - "${GROUND}" ${SPAWN} <<'PY'
import json, sys
g = json.load(open(sys.argv[1])); a = sys.argv[2:]
x, y = float(a[a.index("-x") + 1]), float(a[a.index("-y") + 1])
(ox, oy), c, H = g["origin"], g["cell"], g["heights"]
r = 0.8   # vehicle footprint radius [m]
i0, i1 = max(0, int((x - r - ox) // c)), min(len(H), int((x + r - ox) // c) + 2)
j0, j1 = max(0, int((y - r - oy) // c)), min(len(H[0]), int((y + r - oy) // c) + 2)
hs = [H[i][j] for i in range(i0, i1) for j in range(j0, j1) if H[i][j] is not None]
k = a.index("-z") + 1
a[k] = "%.3f" % max(float(a[k]), max(hs) + 0.5 if hs else 0.0)
print(" ".join(a))
PY
) || SPAWN="--model-name=${MODEL} -x 0 -y 0 -z 0 -Y 0"
    echo "[ctrack] spawn on the ground relief: ${SPAWN}"
fi
while gz model --verbose --spawn-file=${PX4_SRC}/Tools/simulation/gazebo-classic/sitl_gazebo-classic/models/${MODEL}/${MODEL}.sdf \
        ${SPAWN} 2>&1 | grep -q "An instance of Gazebo is not running"; do
    sleep 1
done
echo "[ctrack] ${MODEL} spawned"

if [ -n "${GUI}" ]; then
    gzclient > ${LOG}/gzclient.log 2>&1 &
fi

# GazeboDrone: Gazebo pose of ${MODEL} -> AirSim vehicle, moving obstacles -> Unreal actors
# of the same name. Restarted if it exits, and if it has printed no pose 30 s after starting
# (it prints the poses of its first message; it has been seen stuck after "Connected!").
POSE_LINES='^(local|global) \('
(until timeout 2 bash -c "exec 3<>/dev/tcp/${AIRSIM_HOST}/41451" 2>/dev/null; do sleep 0.5; done
 while true; do
     before=$(grep -cE "${POSE_LINES}" ${LOG}/gazebodrone.log || true)
     GAZEBO_DRONE_MODEL=${MODEL} GAZEBO_MIRROR_MODELS=${MIRROR_MODELS} /ctrack/bin/GazeboDrone &
     pid=$!
     for i in $(seq 1 30); do
         sleep 1
         [ "$(grep -cE "${POSE_LINES}" ${LOG}/gazebodrone.log)" -gt "${before}" ] && break
         kill -0 ${pid} 2>/dev/null || break
     done
     if kill -0 ${pid} 2>/dev/null && [ "$(grep -cE "${POSE_LINES}" ${LOG}/gazebodrone.log)" -le "${before}" ]; then
         echo "[ctrack] GazeboDrone got no pose in 30 s - restarting it"
         kill ${pid} 2>/dev/null || true
     fi
     rc=0; wait ${pid} || rc=$?   # set -e: a failed wait must not end the loop
     echo "[ctrack] GazeboDrone exited (${rc}) - restarting in 2 s"
     sleep 2
 done) > ${LOG}/gazebodrone.log 2>&1 &

case "${MODEL}" in
    x8)   export PX4_SYS_AUTOSTART=2000 ;;
    iris) export PX4_SYS_AUTOSTART=10015 ;;
esac
export PX4_SIM_MODEL=gazebo-classic_${MODEL}
mkdir -p /tmp/px4_rootfs
cd /tmp/px4_rootfs
${PX4_BUILD}/bin/px4 -d -w /tmp/px4_rootfs ${PX4_BUILD}/etc > ${LOG}/px4.log 2>&1 &

wait
