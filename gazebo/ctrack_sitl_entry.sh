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

gzserver --verbose /ctrack/worlds/ctrack.world > ${LOG}/gzserver.log 2>&1 &

# Spawn at the Start helipad facing +x (Track +X): must match the Unreal PlayerStart
while gz model --verbose --spawn-file=${PX4_SRC}/Tools/simulation/gazebo-classic/sitl_gazebo-classic/models/${MODEL}/${MODEL}.sdf \
        --model-name=${MODEL} -x 0 -y 0 -z 0 -Y 0 2>&1 | grep -q "An instance of Gazebo is not running"; do
    sleep 1
done
echo "[ctrack] ${MODEL} spawned"

if [ -n "${GUI}" ]; then
    gzclient > ${LOG}/gzclient.log 2>&1 &
fi

# GazeboDrone: Gazebo pose of ${MODEL} -> AirSim vehicle, moving obstacles -> Unreal actors
# of the same name (restart if it drops)
(until timeout 2 bash -c "exec 3<>/dev/tcp/${AIRSIM_HOST}/41451" 2>/dev/null; do sleep 0.5; done
 while true; do
     GAZEBO_DRONE_MODEL=${MODEL} GAZEBO_MIRROR_MODELS=${MIRROR_MODELS} /ctrack/bin/GazeboDrone
     echo "[ctrack] GazeboDrone exited ($?) - restarting in 2 s"
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
