"""Combine the four dimensions into a total and rank destinations deterministically."""

from datetime import date

from pydantic import BaseModel, ConfigDict

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

    model_config = ConfigDict(frozen=True, extra="forbid")

    city_code: str
    city_name: str
    itinerary: Itinerary
    stay: Stay | None = None
    weather: WeatherClimate | None = None
    activities: ActivityCounts | None = None
    originality: OriginalityInputs | None = None


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
    """Best first: total, then price score, then city code, so ties are always resolved."""
    scored = [score_destination(trip, inputs, today) for inputs in destinations]
    scored.sort(key=lambda s: (-s.total, -s.price.value, s.city_code))
    return scored[: trip.top_n]


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
