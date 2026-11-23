"""Scores per destination, and the tunable constants behind them."""

from typing import Annotated, Self, cast

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.confidence import Confidence
from app.domain.travel import ActivityCategory, Itinerary, Stay

ACTIVITY_SATURATION: dict[ActivityCategory, int] = {
    "museums": 30,
    "sights": 50,
    "nightlife": 40,
    "food": 150,
    "escape_rooms": 5,
    "nature": 20,
    "sport_water": 15,
    "markets": 5,
}

Weight = Annotated[float, Field(ge=0, le=100)]
Score = Annotated[float, Field(ge=0, le=10)]


class _Model(BaseModel):
    # allow_inf_nan=False: an infinite parameter would turn every score into NaN.
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)


class ScoringParams(_Model):
    """Every constant of the scoring formulas (ARCHITECTURE.md §6); overridable per trip."""

    price_low_eur: float = Field(default=250, gt=0, le=100_000)
    price_high_eur: float = Field(default=750, gt=0, le=100_000)

    quality_flight: Weight = 0.40
    quality_weather: Weight = 0.35
    quality_stay: Weight = 0.25

    penalty_per_hour_off_ideal: float = Field(default=2.0, ge=0, le=10)
    # Where "ideal" lies in a window with only one bound, e.g. "after 15:00".
    open_window_ideal_offset_hours: float = Field(default=3.0, ge=0, le=24)
    flight_minutes_best: float = Field(default=90, gt=0, le=24 * 60)
    flight_minutes_worst: float = Field(default=240, gt=0, le=24 * 60)
    access_minutes_best: float = Field(default=45, ge=0, le=24 * 60)

    weather_temperature: Weight = 0.4
    weather_sunshine: Weight = 0.3
    weather_rain: Weight = 0.3
    tmax_worst_c: float = Field(default=5, ge=-60, le=60)
    tmax_best_c: float = Field(default=18, ge=-60, le=60)
    sunshine_best_hours: float = Field(default=8, gt=0, le=24)
    rain_fraction_worst: float = Field(default=0.6, gt=0, le=1)

    stay_confirmed_score: Score = 10
    stay_likely_score: Score = 7
    stay_unknown_score: Score = 5
    rating_good: float = Field(default=9, ge=0, le=10)
    rating_poor: float = Field(default=7, ge=0, le=10)
    rating_bonus: float = Field(default=1, ge=0, le=10)

    activity_saturation: dict[ActivityCategory, Annotated[int, Field(ge=1, le=1_000_000)]] = Field(
        default_factory=lambda: dict(ACTIVITY_SATURATION)
    )
    activity_rich_threshold: int = Field(default=3, ge=1)
    activity_amount: Weight = 0.6
    activity_variety: Weight = 0.4
    wikivoyage_bonus_threshold: int = Field(default=15, ge=0)
    wikivoyage_bonus: float = Field(default=0.5, ge=0, le=10)

    originality_fame: Weight = 0.6
    originality_density: Weight = 0.4
    pageviews_log10_famous: float = Field(default=6, ge=0, le=12)
    pageviews_log10_unknown: float = Field(default=4, ge=0, le=12)
    poi_density_crowded: float = Field(default=50, gt=0, le=1e6)
    poi_density_quiet: float = Field(default=5, ge=0, le=1e6)
    visit_recent_years: float = Field(default=2, gt=0, le=100)
    visit_middle_years: float = Field(default=5, gt=0, le=100)
    visit_penalty_recent: float = Field(default=4, ge=0, le=10)
    visit_penalty_middle: float = Field(default=2, ge=0, le=10)
    visit_penalty_old: float = Field(default=1, ge=0, le=10)
    visit_penalty_max: float = Field(default=6, ge=0, le=10)

    @field_validator("activity_saturation", mode="before")
    @classmethod
    def _merge_with_default_saturation(cls, value: object) -> object:
        # Overriding one category must not silently drop the other seven.
        if isinstance(value, dict):
            # Keys and values are validated by the field type after this merge.
            overrides = cast("dict[str, object]", value)
            return {**ACTIVITY_SATURATION, **overrides}
        return value

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        ranges = [
            ("price_low_eur", self.price_low_eur, "price_high_eur", self.price_high_eur),
            (
                "flight_minutes_best",
                self.flight_minutes_best,
                "flight_minutes_worst",
                self.flight_minutes_worst,
            ),
            ("tmax_worst_c", self.tmax_worst_c, "tmax_best_c", self.tmax_best_c),
            (
                "poi_density_quiet",
                self.poi_density_quiet,
                "poi_density_crowded",
                self.poi_density_crowded,
            ),
            (
                "pageviews_log10_unknown",
                self.pageviews_log10_unknown,
                "pageviews_log10_famous",
                self.pageviews_log10_famous,
            ),
            ("rating_poor", self.rating_poor, "rating_good", self.rating_good),
            (
                "visit_recent_years",
                self.visit_recent_years,
                "visit_middle_years",
                self.visit_middle_years,
            ),
        ]
        for low_name, low, high_name, high in ranges:
            if low >= high:
                msg = f"{low_name} must be below {high_name}"
                raise ValueError(msg)
        groups = {
            "quality": (self.quality_flight, self.quality_weather, self.quality_stay),
            "weather": (self.weather_temperature, self.weather_sunshine, self.weather_rain),
            "activity": (self.activity_amount, self.activity_variety),
            "originality": (self.originality_fame, self.originality_density),
        }
        for group, weights in groups.items():
            if sum(weights) <= 0:
                msg = f"at least one {group} weight must be positive"
                raise ValueError(msg)
        return self


class DimensionScore(_Model):
    value: float = Field(ge=0, le=10)
    confidence: Confidence
    explanation: str
    inputs: dict[str, float] = Field(default_factory=dict[str, float])


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
    flags: list[str] = Field(default_factory=list[str])
