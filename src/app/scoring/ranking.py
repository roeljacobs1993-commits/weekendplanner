"""Combine the four dimensions into a total and rank destinations deterministically."""

from collections import Counter
from datetime import date
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain import (
    ActivityCounts,
    DestinationScores,
    Itinerary,
    OriginalityInputs,
    Stay,
    TripConfig,
    WeatherClimate,
)
from app.scoring._common import weighted
from app.scoring.activities import score_activities
from app.scoring.originality import score_originality
from app.scoring.price import score_price
from app.scoring.quality import score_quality


class DestinationInputs(BaseModel):
    """Everything known about one destination; missing parts are scored as estimates."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    city_code: str = Field(pattern=r"^[A-Z]{3}$")
    city_name: str = Field(min_length=1, max_length=200)
    itinerary: Itinerary
    stay: Stay | None = None
    weather: WeatherClimate | None = None
    activities: ActivityCounts | None = None
    originality: OriginalityInputs | None = None

    @model_validator(mode="after")
    def _same_city(self) -> Self:
        if self.itinerary.city_code != self.city_code:
            msg = f"itinerary is for {self.itinerary.city_code}, not {self.city_code}"
            raise ValueError(msg)
        if self.stay is not None and self.stay.city_code != self.city_code:
            msg = f"stay is in {self.stay.city_code}, not {self.city_code}"
            raise ValueError(msg)
        return self


def score_destination(
    trip: TripConfig, inputs: DestinationInputs, today: date
) -> DestinationScores:
    params = trip.scoring
    price = score_price(inputs.itinerary, inputs.stay, trip, params)
    quality = score_quality(inputs.itinerary, inputs.stay, inputs.weather, trip, params)
    activities = score_activities(inputs.activities, params)
    originality = score_originality(inputs.originality, today, params)
    weights = trip.weights
    total = weighted(
        [
            (weights.price, price.value),
            (weights.quality, quality.value),
            (weights.activities, activities.value),
            (weights.originality, originality.value),
        ]
    )
    per_person = price.inputs.get("per_person_eur")
    return DestinationScores(
        city_code=inputs.city_code,
        city_name=inputs.city_name,
        itinerary=inputs.itinerary,
        stay=inputs.stay,
        price=price,
        quality=quality,
        activities=activities,
        originality=originality,
        total=total,
        price_per_person_eur=per_person,
        flags=_flags(trip, inputs, per_person),
    )


def rank_destinations(
    trip: TripConfig, destinations: list[DestinationInputs], today: date
) -> list[DestinationScores]:
    """Score every destination and return the best trip.top_n of them."""
    duplicates = sorted(
        code for code, n in Counter(d.city_code for d in destinations).items() if n > 1
    )
    if duplicates:
        # Two entries for one city would make the order depend on the input order.
        msg = f"duplicate destination {', '.join(duplicates)}"
        raise ValueError(msg)
    scored = [score_destination(trip, inputs, today) for inputs in destinations]
    return order_scores(scored)[: trip.top_n]


def order_scores(scores: list[DestinationScores]) -> list[DestinationScores]:
    """Best first: total, then price score, then city code, so ties are always resolved."""
    return sorted(scores, key=lambda s: (-s.total, -s.price.value, s.city_code))


def _flags(trip: TripConfig, inputs: DestinationInputs, per_person: float | None) -> list[str]:
    flags: list[str] = []
    if inputs.itinerary.is_open_jaw:
        flags.append("open_jaw")
    if inputs.itinerary.group_booking_likely:
        flags.append("group_booking")
    if inputs.stay is None:
        flags.append("no_stay")
    budget = trip.budget_per_person_eur
    if budget is not None and per_person is not None and per_person > float(budget):
        flags.append("over_budget")
    return flags
