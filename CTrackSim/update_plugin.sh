#!/bin/bash
# Sync the Cosys-AirSim plugin (built AirLib included) into this project.
# Run after (re)building Cosys-AirSim with: ./build.sh --ue-root "$UE_ROOT"
set -e
COSYS_ROOT="${COSYS_ROOT:-$HOME/Documents/InhouseSim-deps/cosys-airsim-3.5.0}"
PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

mkdir -p "$PROJECT_DIR/Plugins"
rsync -a --exclude 'temp' --delete "$COSYS_ROOT/Unreal/Plugins/AirSim" "$PROJECT_DIR/Plugins/"
rsync -a --exclude 'temp' --delete "$COSYS_ROOT/AirLib" "$PROJECT_DIR/Plugins/AirSim/Source/"
echo "Cosys-AirSim plugin synced from $COSYS_ROOT"
