from datetime import date, time
from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from app.domain import Confidence, TimeWindow, TripConfig, Weights, lowest_confidence


def trip_data(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "name": "test-trip",
        "home": {"name": "Nijmegen", "lat": 51.8425, "lon": 5.8528},
        "group_size": 10,
        "rooms_min": 5,
        "persons_per_room": 2,
        "outbound": {"date": "2027-03-19", "earliest": "12:00", "latest": "18:00"},
        "inbound": {"date": "2027-03-22", "earliest": "15:00"},
    }
    data.update(overrides)
    return data


def test_valid_trip_applies_defaults() -> None:
    trip = TripConfig.model_validate(trip_data())

    assert trip.nonstop_only is True
    assert trip.max_drive_minutes == 150
    assert trip.max_ov_minutes == 180
    assert trip.top_n == 5
    assert trip.top_k_live == 12
    assert trip.budget_per_person_eur is None
    assert trip.weights == Weights()


def test_nights_are_derived_from_the_dates() -> None:
    trip = TripConfig.model_validate(trip_data())

    assert trip.nights == 3


def test_stay_requirements_default_to_rooms_and_group_size() -> None:
    trip = TripConfig.model_validate(trip_data())

    assert trip.required_bedrooms == 5
    assert trip.required_guests == 10
    assert trip.stay.bedrooms_min is None
    assert trip.stay.living_room_required is True


def test_explicit_stay_requirements_take_precedence() -> None:
    trip = TripConfig.model_validate(trip_data(stay={"bedrooms_min": 6, "guests_min": 12}))

    assert trip.required_bedrooms == 6
    assert trip.required_guests == 12


def test_changing_rooms_after_a_round_trip_still_validates() -> None:
    dumped = TripConfig.model_validate(trip_data()).model_dump()

    trip = TripConfig.model_validate(dumped | {"rooms_min": 6})

    assert trip.required_bedrooms == 6


def test_inbound_must_be_after_outbound() -> None:
    data = trip_data(inbound={"date": "2027-03-19"})

    with pytest.raises(ValidationError, match="inbound date must be after the outbound date"):
        TripConfig.model_validate(data)


def test_time_window_earliest_must_be_before_latest() -> None:
    with pytest.raises(ValidationError, match="earliest must be before latest"):
        TimeWindow(date=date(2027, 3, 19), earliest=time(18, 0), latest=time(12, 0))


def test_time_window_with_equal_bounds_is_rejected() -> None:
    with pytest.raises(ValidationError, match="earliest must be before latest"):
        TimeWindow(date=date(2027, 3, 19), earliest=time(12, 0), latest=time(12, 0))


def test_open_ended_time_window_is_allowed() -> None:
    window = TimeWindow(date=date(2027, 3, 22), earliest=time(15, 0))

    assert window.latest is None


def test_group_size_must_be_positive() -> None:
    with pytest.raises(ValidationError, match="group_size"):
        TripConfig.model_validate(trip_data(group_size=0))


def test_rooms_must_fit_the_whole_group() -> None:
    data = trip_data(rooms_min=4)

    with pytest.raises(ValidationError, match="rooms_min x persons_per_room must be at least"):
        TripConfig.model_validate(data)


@pytest.mark.parametrize("top_n", [4, 0, 20])
def test_top_n_must_be_3_5_or_10(top_n: int) -> None:
    with pytest.raises(ValidationError, match="top_n"):
        TripConfig.model_validate(trip_data(top_n=top_n))


def test_top_k_live_must_cover_top_n() -> None:
    data = trip_data(top_n=10, top_k_live=8)

    with pytest.raises(ValidationError, match="top_k_live must be at least top_n"):
        TripConfig.model_validate(data)


def test_top_k_live_equal_to_top_n_is_allowed() -> None:
    trip = TripConfig.model_validate(trip_data(top_n=10, top_k_live=10))

    assert trip.top_k_live == 10


@pytest.mark.parametrize("field", ["price", "quality", "activities", "originality"])
def test_negative_weight_is_rejected(field: str) -> None:
    with pytest.raises(ValidationError, match="greater than or equal to 0"):
        Weights.model_validate({field: -1})


def test_weights_must_not_all_be_zero() -> None:
    with pytest.raises(ValidationError, match="at least one weight must be positive"):
        Weights(price=0, quality=0, activities=0, originality=0)


def test_stay_bedrooms_below_rooms_min_is_rejected() -> None:
    data = trip_data(stay={"bedrooms_min": 3})

    with pytest.raises(ValidationError, match=r"stay\.bedrooms_min must be at least rooms_min"):
        TripConfig.model_validate(data)


def test_stay_guests_below_group_size_is_rejected() -> None:
    data = trip_data(stay={"guests_min": 8})

    with pytest.raises(ValidationError, match=r"stay\.guests_min must be at least group_size"):
        TripConfig.model_validate(data)


def test_budget_must_be_positive() -> None:
    with pytest.raises(ValidationError, match="budget_per_person_eur"):
        TripConfig.model_validate(trip_data(budget_per_person_eur=0))


def test_budget_is_kept_as_decimal() -> None:
    trip = TripConfig.model_validate(trip_data(budget_per_person_eur="499.50"))

    assert trip.budget_per_person_eur == Decimal("499.50")


def test_unknown_field_is_rejected_to_catch_typos() -> None:
    with pytest.raises(ValidationError, match="group_szie"):
        TripConfig.model_validate(trip_data(group_szie=10))


def test_home_latitude_must_be_on_earth() -> None:
    data = trip_data(home={"name": "Nowhere", "lat": 95, "lon": 5})

    with pytest.raises(ValidationError, match=r"home\.lat"):
        TripConfig.model_validate(data)


def test_lowest_confidence_picks_the_weakest_input() -> None:
    result = lowest_confidence([Confidence.LIVE, Confidence.ESTIMATED, Confidence.CACHED])

    assert result is Confidence.ESTIMATED


def test_lowest_confidence_of_live_inputs_is_live() -> None:
    assert lowest_confidence([Confidence.LIVE, Confidence.LIVE]) is Confidence.LIVE
