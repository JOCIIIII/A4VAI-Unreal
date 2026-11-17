#!/bin/bash
# Sync the Cosys-AirSim plugin (built AirLib included) into this project.
# Run after (re)building Cosys-AirSim with: ./build.sh --ue-root "$UE_ROOT"
set -e
PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
# Lab PC layout: this project is 00_Unreal/00_Map/A4VAISIM, next to 01_Cosys (Cosys-AirSim source), 02_Engine
# (Unreal Engine) and 03_Dist (packaged builds); elsewhere ~/Downloads and ~/Documents/InhouseSim-deps.
COSYS_ROOT="${COSYS_ROOT:-$(d="${PROJECT_DIR}/../../01_Cosys"; [ -d "$d" ] && readlink -f "$d" || echo "$HOME/Documents/InhouseSim-deps")/cosys-airsim-3.5.0}"

mkdir -p "$PROJECT_DIR/Plugins"
rsync -a --exclude 'temp' --delete "$COSYS_ROOT/Unreal/Plugins/AirSim" "$PROJECT_DIR/Plugins/"
rsync -a --exclude 'temp' --delete "$COSYS_ROOT/AirLib" "$PROJECT_DIR/Plugins/AirSim/Source/"
echo "Cosys-AirSim plugin synced from $COSYS_ROOT"
