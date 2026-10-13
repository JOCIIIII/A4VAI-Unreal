#!/bin/bash
# Build everything this repo needs from Cosys-AirSim 5.8-v3.5.0 + patches/cosys-airsim/*.patch:
#   1. AirLib with Unreal's bundled clang -> CTrackSim/Plugins/AirSim, CTrackSim editor build
#   2. AirLib with gcc + GazeboDrone (px4-dev-simulation-focal image) -> gazebo/bin/GazeboDrone
#   3. Gazebo plugins -> gazebo/plugins/build
# Needs: Unreal Engine 5.8.2 (UE_ROOT), docker with px4io/px4-dev-simulation-focal, git, wget, unzip.
#   UE_ROOT=/path/to/Linux_Unreal_Engine_5.8.2 ./setup_deps.sh
#   ./setup_deps.sh --gazebo-only    only 2 and 3 (no Unreal Engine; use the packaged build)
set -e
GAZEBO_ONLY=0
[ "$1" = "--gazebo-only" ] && GAZEBO_ONLY=1
HERE="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
UE_ROOT="${UE_ROOT:-$HOME/Downloads/Linux_Unreal_Engine_5.8.2}"
DEPS_DIR="${DEPS_DIR:-$HOME/Documents/InhouseSim-deps}"
COSYS_TAG=5.8-v3.5.0
COSYS="${DEPS_DIR}/cosys-airsim-3.5.0"
COSYS_GCC="${DEPS_DIR}/cosys-airsim-3.5.0-gcc"
PX4_DEV_IMAGE=px4io/px4-dev-simulation-focal:latest

if [ ${GAZEBO_ONLY} = 0 ] && [ ! -x "${UE_ROOT}/Engine/Binaries/Linux/UnrealEditor" ]; then
    echo "UE_ROOT=${UE_ROOT} is not an Unreal Engine install (use --gazebo-only with the packaged build)"
    exit 1
fi

# Cosys-AirSim source at the release tag, with our patches
if [ ! -d "${COSYS}" ]; then
    mkdir -p "${DEPS_DIR}"
    git clone --depth 1 --branch ${COSYS_TAG} https://github.com/Cosys-Lab/Cosys-AirSim.git "${COSYS}"
fi
for p in "${HERE}"/patches/cosys-airsim/*.patch; do
    if git -C "${COSYS}" apply --reverse --check "$p" 2>/dev/null; then
        echo "already applied: $(basename "$p")"
    else
        git -C "${COSYS}" apply "$p" && echo "applied: $(basename "$p")"
    fi
done

# Same downloads as Cosys setup.sh, without its sudo apt-get
cd "${COSYS}"
if [ ! -d external/rpclib/rpclib-2.3.1 ]; then
    wget -q https://github.com/WouterJansen/rpclib/archive/refs/tags/v2.3.1.zip
    rm -rf external/rpclib && mkdir -p external/rpclib && unzip -q v2.3.1.zip -d external/rpclib && rm v2.3.1.zip
fi
if [ ! -d AirLib/deps/eigen3 ]; then
    wget -q -O eigen3.zip https://github.com/WouterJansen/eigen/archive/refs/tags/3.4.1r.zip
    unzip -q eigen3.zip -d temp_eigen && mkdir -p AirLib/deps/eigen3 && mv temp_eigen/eigen*/Eigen AirLib/deps/eigen3
    rm -rf temp_eigen eigen3.zip
fi

# 1. Unreal plugin (UE's clang + sysroot so the static libs link into the engine)
if [ ${GAZEBO_ONLY} = 0 ]; then
    ./build.sh --ue-root "${UE_ROOT}"
    COSYS_ROOT="${COSYS}" "${HERE}/CTrackSim/update_plugin.sh"
    UE_ROOT="${UE_ROOT}" "${HERE}/CTrackSim/build_editor.sh"
fi

# 2. GazeboDrone (gcc AirLib, links against Gazebo 11 in the PX4 dev image)
rsync -a --delete --exclude build_release --exclude build_debug --exclude 'Unreal/Environments' \
    --exclude 'Unreal/Plugins/AirSim/Source/AirLib' --exclude 'AirLib/lib' "${COSYS}/" "${COSYS_GCC}/"
docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp -v "${COSYS_GCC}":/src -w /src --entrypoint bash ${PX4_DEV_IMAGE} -c '
    ./build.sh --gcc &&
    rm -rf GazeboDrone/build && mkdir GazeboDrone/build && cd GazeboDrone/build &&
    cmake -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_STANDARD=17 -DCMAKE_EXE_LINKER_FLAGS=-L/src/build_release/output/lib .. &&
    make -j"$(nproc)"'
mkdir -p "${HERE}/gazebo/bin"
cp "${COSYS_GCC}/GazeboDrone/build/GazeboDrone" "${HERE}/gazebo/bin/GazeboDrone"

# 3. Gazebo plugins (wind zone, moving obstacle)
docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp -v "${HERE}/gazebo/plugins":/src -w /src --entrypoint bash ${PX4_DEV_IMAGE} -c '
    mkdir -p build && cd build && cmake .. && make -j"$(nproc)"'

echo "Done. Next: ./run_unreal.sh and ./gazebo/run_gazebo_px4.sh"
