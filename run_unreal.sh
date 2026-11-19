#!/bin/bash
# Launch a map with Cosys-AirSim driven by Gazebo (ExternalPhysicsEngine).
#   ./run_unreal.sh [settings.json]   (default: settings/settings_gazebo.json)
#   SCENARIO_MAP=Yard ./run_unreal.sh   the SLAM yard instead of the test map (default Scenario);
#                                     a name in /Game/Scenario/Maps or a full map path (MAP also works)
#   SCENARIO_VSYNC=1 ./run_unreal.sh    pace frames to the display (VSync): unpaced frames (5-12 ms) shown on a
#                                     60 Hz screen or in a screen recording make the motion judder
# Uses the packaged build (no Unreal Engine install needed) when present:
#   $SCENARIO_PACKAGED, or packaged/A4VAISIM-Linux/ (release asset, extracted here).
# Otherwise runs the editor project with $UE_ROOT.
HERE="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
# Lab PC layout: this repository is 00_Unreal/00_Map, next to 01_Cosys (Cosys-AirSim source), 02_Engine
# (Unreal Engine) and 03_Dist (packaged builds); elsewhere ~/Downloads and ~/Documents/InhouseSim-deps.
UE_ROOT="${UE_ROOT:-$(d="${HERE}/../02_Engine/Linux_Unreal_Engine_5.8.2"; [ -d "$d" ] && readlink -f "$d" || echo "$HOME/Downloads/Linux_Unreal_Engine_5.8.2")}"
PACKAGED="${SCENARIO_PACKAGED:-${HERE}/packaged/A4VAISIM-Linux}"
MAP="${SCENARIO_MAP:-${MAP:-Scenario}}"
[[ "${MAP}" == /* ]] || MAP="/Game/Scenario/Maps/${MAP}"
SETTINGS="$(readlink -f "${1:-${HERE}/settings/settings_gazebo.json}")"

LAUNCHER="${PACKAGED}/A4VAISIM.sh"
if [ -x "${LAUNCHER}" ]; then
    MODE=packaged
else
    MODE=editor
fi

# The S900 vehicle look is not in the public repository or the packaged build. Without it, drop
# the pawn override so Cosys-AirSim uses its default multirotor pawn (sensors and physics unchanged).
if { [ "${MODE}" = packaged ] || [ ! -f "${HERE}/A4VAISIM/Content/Scenario/Vehicles/BP_S900Pawn.uasset" ]; } \
        && grep -q "BP_S900Pawn" "${SETTINGS}"; then
    FALLBACK="${TMPDIR:-/tmp}/scenario_settings_default_pawn.json"
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

EXTRA=()
[ "${SCENARIO_VSYNC:-0}" = 1 ] && EXTRA+=("-ExecCmds=r.VSync 1")
echo "[run_unreal.sh] map ${MAP}${EXTRA:+ (VSync)}"
if [ "${MODE}" = packaged ]; then
    echo "[run_unreal.sh] packaged build: ${PACKAGED}"
    exec "${LAUNCHER}" "${MAP}" \
        -windowed -ResX=1280 -ResY=720 -settings="${SETTINGS}" "${EXTRA[@]}"
fi
exec "${UE_ROOT}/Engine/Binaries/Linux/UnrealEditor" "${HERE}/A4VAISIM/A4VAISIM.uproject" "${MAP}" \
    -game -windowed -ResX=1280 -ResY=720 -settings="${SETTINGS}" "${EXTRA[@]}"
