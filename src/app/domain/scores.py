"""Scores per destination, and the tunable constants behind them."""

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.confidence import Confidence
from app.domain.travel import Itinerary, Stay

ACTIVITY_SATURATION = {
    "museums": 30,
    "sights": 50,
    "nightlife": 40,
    "food": 150,
    "escape_rooms": 5,
    "nature": 20,
    "sport_water": 15,
    "markets": 5,
}


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ScoringParams(_Model):
    """Every constant of the scoring formulas (ARCHITECTURE.md §6); overridable per trip."""

    price_low_eur: float = Field(default=250, gt=0)
    price_high_eur: float = Field(default=750, gt=0)

    quality_flight: float = Field(default=0.40, ge=0)
    quality_weather: float = Field(default=0.35, ge=0)
    quality_stay: float = Field(default=0.25, ge=0)

    penalty_per_hour_off_ideal: float = Field(default=2.0, ge=0)
    # Where "ideal" lies in a window with only one bound, e.g. "after 15:00".
    open_window_ideal_offset_hours: float = Field(default=3.0, ge=0)
    flight_minutes_best: float = Field(default=90, gt=0)
    flight_minutes_worst: float = Field(default=240, gt=0)
    access_minutes_best: float = Field(default=45, ge=0)

    tmax_worst_c: float = 5
    tmax_best_c: float = 18
    sunshine_best_hours: float = Field(default=8, gt=0)
    rain_fraction_worst: float = Field(default=0.6, gt=0, le=1)

    activity_saturation: dict[str, int] = Field(default_factory=lambda: dict(ACTIVITY_SATURATION))
    activity_rich_threshold: int = Field(default=3, ge=1)
    wikivoyage_bonus_threshold: int = Field(default=15, ge=0)
    wikivoyage_bonus: float = Field(default=0.5, ge=0)

    pageviews_log10_famous: float = 6
    pageviews_log10_unknown: float = 4
    poi_density_crowded: float = Field(default=50, gt=0)
    poi_density_quiet: float = Field(default=5, ge=0)
    visit_penalty_recent: float = Field(default=4, ge=0)
    visit_penalty_middle: float = Field(default=2, ge=0)
    visit_penalty_old: float = Field(default=1, ge=0)
    visit_penalty_max: float = Field(default=6, ge=0)

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.price_low_eur >= self.price_high_eur:
            msg = "price_low_eur must be below price_high_eur"
            raise ValueError(msg)
        if self.quality_flight + self.quality_weather + self.quality_stay <= 0:
            msg = "at least one quality weight must be positive"
            raise ValueError(msg)
        return self


class DimensionScore(_Model):
    value: float = Field(ge=0, le=10)
    confidence: Confidence
    explanation: str
    inputs: dict[str, float] = Field(default_factory=dict)


class DestinationScores(_Model):
    city_code: str
    city_name: str
    itinerary: Itinerary
    stay: Stay | None
    price: DimensionScore
    quality: DimensionScore
    activities: DimensionScore
    originality: DimensionScore
    total: float = Field(ge=0, le=10)
    price_per_person_eur: float | None
    flags: list[str] = Field(default_factory=list)
