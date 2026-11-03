#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "CTrackSwayActor.generated.h"

/**
 * Base of a swaying figure (the balloon "sky dancer"): its root sits on the ground and tilts back and
 * forth, so whatever is attached to it sways about its foot. Unreal only (what the lidar and the
 * cameras see); the Gazebo collider stays upright.
 */
UCLASS()
class CTRACKSIM_API ACTrackSwayActor : public AActor
{
	GENERATED_BODY()

public:
	ACTrackSwayActor();

	/** Height of the swaying figure (cm): TopAmplitude is reached there. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Sway")
	float Height = 400.0f;

	/** Sideways travel of the top (cm, +-). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Sway")
	float TopAmplitude = 30.0f;

	/** Sway frequency (Hz). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Sway")
	float Frequency = 1.0f;

	/** Direction of the sway in the horizontal plane (deg, 0 = +X, 90 = +Y). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Sway")
	float DirectionDeg = 90.0f;

	virtual void Tick(float DeltaSeconds) override;
};
