#include "CTrackSimGameInstance.h"

#include "GameMapsSettings.h"
#include "Misc/CommandLine.h"
#include "Misc/PackageName.h"
#include "Misc/Parse.h"

void UCTrackSimGameInstance::StartGameInstance()
{
#if UE_BUILD_SHIPPING
	FString Map;
	const TCHAR* CommandLine = FCommandLine::Get();
	if (FParse::Token(CommandLine, Map, false) && !Map.StartsWith(TEXT("-"))) {
		Map.Split(TEXT("?"), &Map, nullptr);  // options after '?' are not part of the package name
		if (Map.StartsWith(TEXT("/")) && FPackageName::DoesPackageExist(Map)) {
			UGameMapsSettings::SetGameDefaultMap(Map);
		}
		else {
			UE_LOG(LogTemp, Warning, TEXT("CTrackSim: map %s not found, starting on the default map"), *Map);
		}
	}
#endif
	Super::StartGameInstance();
}
