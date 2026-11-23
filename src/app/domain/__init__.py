"""Domain models shared by the pipeline, the scoring and the user interfaces."""

from app.domain.confidence import Confidence, lowest_confidence
from app.domain.scores import DestinationScores, DimensionScore, ScoringParams
from app.domain.travel import (
    ActivityCounts,
    FlightLeg,
    Itinerary,
    OriginalityInputs,
    Stay,
    WeatherClimate,
)
from app.domain.trip import GeoPoint, StayRequirements, TimeWindow, TripConfig, Weights

__all__ = [
    "ActivityCounts",
    "Confidence",
    "DestinationScores",
    "DimensionScore",
    "FlightLeg",
    "GeoPoint",
    "Itinerary",
    "OriginalityInputs",
    "ScoringParams",
    "Stay",
    "StayRequirements",
    "TimeWindow",
    "TripConfig",
    "WeatherClimate",
    "Weights",
    "lowest_confidence",
]
