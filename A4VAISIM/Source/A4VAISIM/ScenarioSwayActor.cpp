#include "ScenarioSwayActor.h"

#include "Components/SceneComponent.h"
#include "Engine/World.h"

AScenarioSwayActor::AScenarioSwayActor()
{
	PrimaryActorTick.bCanEverTick = true;
	USceneComponent* Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	Root->SetMobility(EComponentMobility::Movable);
	SetRootComponent(Root);
}

void AScenarioSwayActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	// tilt about the horizontal axis normal to the sway direction, so the top moves +-TopAmplitude
	const double TiltDeg = FMath::RadiansToDegrees(FMath::Atan2(TopAmplitude, FMath::Max(Height, 1.0f)))
		* FMath::Sin(2.0 * PI * Frequency * GetWorld()->GetTimeSeconds());
	const FVector Dir = FRotator(0.0, DirectionDeg, 0.0).Vector();
	const FVector Axis = FVector::CrossProduct(FVector::UpVector, Dir); // tilting about it moves the top along Dir
	SetActorRotation(FQuat(Axis, FMath::DegreesToRadians(TiltDeg)));
}
