#!/bin/bash
# Launch the C-Track map with Cosys-AirSim driven by Gazebo (ExternalPhysicsEngine).
#   ./run_unreal.sh [settings.json]   (default: settings/settings_gazebo.json)
#   MAP=/Game/CTrack/Maps/CTrack ./run_unreal.sh   the C-Track field instead of the yard
HERE="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
UE_ROOT="${UE_ROOT:-$HOME/Downloads/Linux_Unreal_Engine_5.8.2}"
MAP="${MAP:-/Game/CTrack/Maps/Yard}"   # default: SLAM yard; MAP=/Game/CTrack/Maps/CTrack for C-Track
SETTINGS="$(readlink -f "${1:-${HERE}/settings/settings_gazebo.json}")"

# The S900 vehicle look is not in the public repository. Without it, drop the pawn override
# so Cosys-AirSim falls back to its default multirotor pawn (sensors and physics unchanged).
if [ ! -f "${HERE}/CTrackSim/Content/CTrack/Vehicles/BP_S900Pawn.uasset" ] && grep -q "BP_S900Pawn" "${SETTINGS}"; then
    FALLBACK="${TMPDIR:-/tmp}/ctrack_settings_default_pawn.json"
    python3 - "${SETTINGS}" "${FALLBACK}" <<'EOF'
import json, sys
s = json.load(open(sys.argv[1]))
s.pop("PawnPaths", None)
for v in s.get("Vehicles", {}).values():
    v.pop("PawnPath", None)
json.dump(s, open(sys.argv[2], "w"), indent=2)
EOF
    echo "[run_unreal.sh] S900 pawn not installed: using the default pawn (${FALLBACK})"
    SETTINGS="${FALLBACK}"
fi

exec "${UE_ROOT}/Engine/Binaries/Linux/UnrealEditor" "${HERE}/CTrackSim/CTrackSim.uproject" "${MAP}" \
    -game -windowed -ResX=1280 -ResY=720 -settings="${SETTINGS}"
