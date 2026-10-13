#!/bin/bash
# Build the release assets from a clean clone of this repository (so nothing outside git, e.g.
# the S900 model, can end up in the build):
#   CTrackSim-Linux.tar.gz        packaged Unreal build (Shipping, without .debug files)
#   ctrack-gazebo-prebuilt.tar.gz GazeboDrone + Gazebo plugins (px4-dev-simulation-focal)
#   UE_ROOT=... ./package.sh [git ref, default HEAD]   -> $OUT (default ~/Documents/InhouseSim-deps/package/release)
set -e
HERE="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
UE_ROOT="${UE_ROOT:-$HOME/Downloads/Linux_Unreal_Engine_5.8.2}"
DEPS_DIR="${DEPS_DIR:-$HOME/Documents/InhouseSim-deps}"
WORK="${WORK:-${DEPS_DIR}/package}"
OUT="${OUT:-${WORK}/release}"
REF="${1:-HEAD}"

rm -rf "${WORK}/src" "${WORK}/out"
mkdir -p "${WORK}" "${OUT}"
git clone -q "${HERE}" "${WORK}/src" && git -C "${WORK}/src" checkout -q "${REF}"
echo "packaging $(git -C "${WORK}/src" describe --tags --always)"

# Plugin (patched Cosys + clang AirLib) and Gazebo binaries, built into the clean clone
UE_ROOT="${UE_ROOT}" DEPS_DIR="${DEPS_DIR}" "${WORK}/src/setup_deps.sh"

"${UE_ROOT}/Engine/Build/BatchFiles/RunUAT.sh" BuildCookRun \
    -project="${WORK}/src/CTrackSim/CTrackSim.uproject" -noP4 -platform=Linux -clientconfig=Shipping \
    -build -cook -stage -pak -archive -archivedirectory="${WORK}/out" -utf8output -unattended

rm -rf "${WORK}/CTrackSim-Linux"
rsync -a --exclude '*.debug' "${WORK}/out/Linux/" "${WORK}/CTrackSim-Linux/"
if find "${WORK}/CTrackSim-Linux" -type f -print0 | xargs -0 strings -n 5 | grep -qi "s900"; then
    echo "S900 content found in the packaged build - not packing"; exit 1
fi
tar -C "${WORK}" -czf "${OUT}/CTrackSim-Linux.tar.gz" CTrackSim-Linux
tar -C "${WORK}/src" -czf "${OUT}/ctrack-gazebo-prebuilt.tar.gz" gazebo/bin/GazeboDrone \
    gazebo/plugins/build/libctrack_wind_zone.so gazebo/plugins/build/libctrack_moving_obstacle.so
(cd "${OUT}" && sha256sum CTrackSim-Linux.tar.gz ctrack-gazebo-prebuilt.tar.gz | tee SHA256SUMS)
