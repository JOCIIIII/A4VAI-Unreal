using UnrealBuildTool;
using System.Collections.Generic;

public class A4VAISIMTarget : TargetRules
{
	public A4VAISIMTarget(TargetInfo Target) : base(Target)
	{
		DefaultBuildSettings = BuildSettingsVersion.V7;
		Type = TargetType.Game;
		ExtraModuleNames.AddRange(new string[] { "A4VAISIM" });
		if (Target.Platform == UnrealTargetPlatform.Linux)
			bUsePCHFiles = false;
	}
}
