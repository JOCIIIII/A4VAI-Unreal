#pragma once

#include "CoreMinimal.h"
#include "Engine/GameInstance.h"

#include "CTrackSimGameInstance.generated.h"

// Lets a Shipping build start on the map given on its command line (run_unreal.sh passes
// /Game/CTrack/Maps/<map>). UE ignores that map in Shipping unless the target defines
// UE_ALLOW_MAP_OVERRIDE_IN_SHIPPING, which needs a unique build environment an installed engine
// cannot build; so the map is made the default map before the engine browses to it.
UCLASS()
class UCTrackSimGameInstance : public UGameInstance
{
	GENERATED_BODY()

public:
	virtual void StartGameInstance() override;
};
