using UnrealBuildTool;
using System.Collections.Generic;

public class A4VAISIMEditorTarget : TargetRules
{
	public A4VAISIMEditorTarget(TargetInfo Target) : base(Target)
	{
		DefaultBuildSettings = BuildSettingsVersion.V7;
		Type = TargetType.Editor;
		ExtraModuleNames.AddRange(new string[] { "A4VAISIM" });
		IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
	}
}
