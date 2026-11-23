from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.domain import Confidence, DimensionScore, ScoringParams, Stay
from tests.unit.scoring_fixtures import CET, itinerary, leg


def test_flight_duration_respects_time_zones() -> None:
    # 15:00 in CET is 14:00 UTC, so landing at 16:40 UTC is a 160-minute flight.
    flight = leg(
        departure=datetime(2027, 3, 19, 15, 0, tzinfo=CET),
        arrival=datetime(2027, 3, 19, 16, 40, tzinfo=UTC),
    )

    assert flight.duration_minutes == 160


def test_flight_times_must_include_a_time_zone() -> None:
    with pytest.raises(ValidationError, match="timezone"):
        leg(departure=datetime(2027, 3, 19, 15, 0))


def test_arrival_must_be_after_departure() -> None:
    with pytest.raises(ValidationError, match="arrival must be after departure"):
        leg(arrival=datetime(2027, 3, 19, 13, 0, tzinfo=UTC))


def test_negative_price_is_rejected() -> None:
    with pytest.raises(ValidationError, match="price_per_person_eur"):
        leg(price_per_person_eur=Decimal("-1"))


def test_iata_codes_must_be_three_capital_letters() -> None:
    with pytest.raises(ValidationError, match="origin_iata"):
        leg(origin_iata="ein")


def test_itinerary_returning_to_the_departure_airport_is_not_open_jaw() -> None:
    assert itinerary().is_open_jaw is False


def test_itinerary_returning_to_another_airport_is_open_jaw() -> None:
    inbound = itinerary().inbound.model_copy(update={"destination_iata": "DUS"})

    assert itinerary(inbound=inbound).is_open_jaw is True


def test_flight_price_per_person_adds_both_legs() -> None:
    assert itinerary().flight_price_per_person_eur == Decimal("188.00")


def test_itinerary_legs_must_serve_the_destination() -> None:
    with pytest.raises(ValidationError, match="outbound must arrive at and inbound depart from"):
        itinerary(city_code="LIS")


def test_itinerary_may_use_another_airport_of_the_same_city() -> None:
    trip = itinerary(
        city_code="LON",
        destination_airports=["LGW", "STN"],
        outbound=leg(destination_iata="LGW"),
        inbound=leg(origin_iata="STN", destination_iata="EIN"),
    )

    assert trip.city_code == "LON"


def test_stay_must_have_at_least_one_bedroom() -> None:
    with pytest.raises(ValidationError, match="bedrooms"):
        Stay(
            name="Casa",
            city_code="OPO",
            bedrooms=0,
            guests=10,
            living_room="confirmed",
            price_total_eur=Decimal("1500"),
            url="https://example.org/casa",
            source="csv",
            confidence=Confidence.CACHED,
        )


def test_dimension_score_must_be_between_0_and_10() -> None:
    with pytest.raises(ValidationError, match="less than or equal to 10"):
        DimensionScore(value=10.5, confidence=Confidence.LIVE, explanation="x")


def test_scoring_params_defaults_follow_the_architecture() -> None:
    params = ScoringParams()

    assert params.price_low_eur == 250
    assert params.price_high_eur == 750
    assert (params.quality_flight, params.quality_weather, params.quality_stay) == (
        0.40,
        0.35,
        0.25,
    )


def test_scoring_params_reject_an_inverted_price_range() -> None:
    with pytest.raises(ValidationError, match="price_low_eur must be below price_high_eur"):
        ScoringParams(price_low_eur=800, price_high_eur=750)
