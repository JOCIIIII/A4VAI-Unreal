using UnrealBuildTool;
using System.Collections.Generic;

public class CTrackSimEditorTarget : TargetRules
{
	public CTrackSimEditorTarget(TargetInfo Target) : base(Target)
	{
		DefaultBuildSettings = BuildSettingsVersion.V7;
		Type = TargetType.Editor;
		ExtraModuleNames.AddRange(new string[] { "CTrackSim" });
		IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
	}
}
