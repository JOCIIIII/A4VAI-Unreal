using UnrealBuildTool;

public class CTrackSim : ModuleRules
{
	public CTrackSim(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
		bEnableExceptions = Target.Platform != UnrealTargetPlatform.Linux;
		PublicDependencyModuleNames.AddRange(new string[] { "Core", "CoreUObject", "Engine", "InputCore" });
	}
}
