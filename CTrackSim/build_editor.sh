#!/bin/bash
# Build the CTrackSim editor target with the local UE 5.8.2 install.
set -e
UE_ROOT="${UE_ROOT:-$HOME/Downloads/Linux_Unreal_Engine_5.8.2}"
PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
"$UE_ROOT/Engine/Build/BatchFiles/Linux/Build.sh" CTrackSimEditor Linux Development \
    -Project="$PROJECT_DIR/CTrackSim.uproject" -WaitMutex
