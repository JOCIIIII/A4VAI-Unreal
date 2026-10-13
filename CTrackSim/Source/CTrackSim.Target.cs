using UnrealBuildTool;
using System.Collections.Generic;

public class CTrackSimTarget : TargetRules
{
	public CTrackSimTarget(TargetInfo Target) : base(Target)
	{
		DefaultBuildSettings = BuildSettingsVersion.V7;
		Type = TargetType.Game;
		ExtraModuleNames.AddRange(new string[] { "CTrackSim" });
		if (Target.Platform == UnrealTargetPlatform.Linux)
			bUsePCHFiles = false;
	}
}
