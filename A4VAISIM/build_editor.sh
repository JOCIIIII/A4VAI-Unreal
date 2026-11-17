#!/bin/bash
# Build the A4VAISIM editor target with the local UE 5.8.2 install.
set -e
PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
# Lab PC layout: this project is 00_Unreal/00_Map/A4VAISIM, next to 01_Cosys (Cosys-AirSim source), 02_Engine
# (Unreal Engine) and 03_Dist (packaged builds); elsewhere ~/Downloads and ~/Documents/InhouseSim-deps.
UE_ROOT="${UE_ROOT:-$(d="${PROJECT_DIR}/../../02_Engine/Linux_Unreal_Engine_5.8.2"; [ -d "$d" ] && readlink -f "$d" || echo "$HOME/Downloads/Linux_Unreal_Engine_5.8.2")}"
"$UE_ROOT/Engine/Build/BatchFiles/Linux/Build.sh" A4VAISIMEditor Linux Development \
    -Project="$PROJECT_DIR/A4VAISIM.uproject" -WaitMutex
