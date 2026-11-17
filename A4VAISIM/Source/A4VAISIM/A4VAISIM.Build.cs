using UnrealBuildTool;

public class A4VAISIM : ModuleRules
{
	public A4VAISIM(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
		bEnableExceptions = Target.Platform != UnrealTargetPlatform.Linux;
		PublicDependencyModuleNames.AddRange(new string[] { "Core", "CoreUObject", "Engine", "InputCore", "EngineSettings" });
	}
}
