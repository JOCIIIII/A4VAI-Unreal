#!/bin/bash
# Launch the C-Track map with Cosys-AirSim driven by Gazebo (ExternalPhysicsEngine).
#   ./run_unreal.sh [settings.json]   (default: settings/settings_gazebo.json)
# Uses the packaged build (no Unreal Engine install needed) when present:
#   $CTRACK_PACKAGED, or packaged/CTrackSim-Linux/ (release asset, extracted here).
# Otherwise runs the editor project with $UE_ROOT.
HERE="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
UE_ROOT="${UE_ROOT:-$HOME/Downloads/Linux_Unreal_Engine_5.8.2}"
PACKAGED="${CTRACK_PACKAGED:-${HERE}/packaged/CTrackSim-Linux}"
SETTINGS="$(readlink -f "${1:-${HERE}/settings/settings_gazebo.json}")"

if [ -x "${PACKAGED}/CTrackSim.sh" ]; then
    MODE=packaged
else
    MODE=editor
fi

# The S900 vehicle look is not in the public repository or the packaged build. Without it, drop
# the pawn override so Cosys-AirSim uses its default multirotor pawn (sensors and physics unchanged).
if { [ "${MODE}" = packaged ] || [ ! -f "${HERE}/CTrackSim/Content/CTrack/Vehicles/BP_S900Pawn.uasset" ]; } \
        && grep -q "BP_S900Pawn" "${SETTINGS}"; then
    FALLBACK="${TMPDIR:-/tmp}/ctrack_settings_default_pawn.json"
    python3 - "${SETTINGS}" "${FALLBACK}" <<'EOF'
import json, sys
s = json.load(open(sys.argv[1]))
s.pop("PawnPaths", None)
for v in s.get("Vehicles", {}).values():
    v.pop("PawnPath", None)
json.dump(s, open(sys.argv[2], "w"), indent=2)
EOF
    echo "[run_unreal.sh] S900 pawn not available: using the default pawn (${FALLBACK})"
    SETTINGS="${FALLBACK}"
fi

if [ "${MODE}" = packaged ]; then
    echo "[run_unreal.sh] packaged build: ${PACKAGED}"
    exec "${PACKAGED}/CTrackSim.sh" /Game/CTrack/Maps/CTrack \
        -windowed -ResX=1280 -ResY=720 -settings="${SETTINGS}"
fi
exec "${UE_ROOT}/Engine/Binaries/Linux/UnrealEditor" "${HERE}/CTrackSim/CTrackSim.uproject" /Game/CTrack/Maps/CTrack \
    -game -windowed -ResX=1280 -ResY=720 -settings="${SETTINGS}"
