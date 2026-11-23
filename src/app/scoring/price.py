"""Price: total cost per person for flights, stay and getting to the airports."""

from app.domain import Confidence, DimensionScore, Itinerary, ScoringParams, Stay, TripConfig
from app.scoring._common import (
    MISSING_SCORE,
    confidence_nl,
    confidence_of,
    lin,
    nl_euros,
    nl_number,
)


def score_price(
    itinerary: Itinerary, stay: Stay | None, trip: TripConfig, params: ScoringParams
) -> DimensionScore:
    flight = float(itinerary.flight_price_per_person_eur)
    ground = float(itinerary.ground_cost_eur) / trip.group_size
    flights_confidence = confidence_of(
        [itinerary.outbound.confidence, itinerary.inbound.confidence]
    )
    if stay is None:
        return DimensionScore(
            value=MISSING_SCORE,
            confidence=Confidence.ESTIMATED,
            explanation=(
                f"Prijs {nl_number(MISSING_SCORE)}: geen data over het verblijf "
                f"(vlucht {nl_euros(flight)} p.p.); geschat."
            ),
            inputs={"flight_eur": flight, "ground_eur": ground},
        )
    stay_share = float(stay.price_total_eur) / trip.group_size
    per_person = flight + stay_share + ground
    high = params.price_high_eur
    if trip.budget_per_person_eur is not None:
        # The budget is the point where the price stops being acceptable at all.
        high = max(float(trip.budget_per_person_eur), params.price_low_eur + 1)
    value = lin(per_person, high, params.price_low_eur)
    explanation = (
        f"Prijs {nl_number(value)}: {nl_euros(per_person)} p.p. "
        f"(vlucht {nl_euros(flight)}, verblijf {nl_euros(stay_share)}, "
        f"vervoer {nl_euros(ground)}); vluchten {confidence_nl(flights_confidence)}, "
        f"verblijf {confidence_nl(stay.confidence)}."
    )
    return DimensionScore(
        value=value,
        confidence=confidence_of([flights_confidence, stay.confidence]),
        explanation=explanation,
        inputs={
            "per_person_eur": per_person,
            "flight_eur": flight,
            "stay_eur": stay_share,
            "ground_eur": ground,
        },
    )
