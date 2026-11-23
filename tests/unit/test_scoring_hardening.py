"""Review findings of T-003: boundaries, untrusted input and ranking ties."""

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.domain import ActivityCounts, ScoringParams, Weights
from app.scoring import (
    DestinationInputs,
    order_scores,
    rank_destinations,
    score_activities,
    score_destination,
    score_originality,
    score_price,
    score_quality,
)
from tests.unit.scoring_fixtures import (
    TODAY,
    activities,
    itinerary,
    leg,
    originality,
    stay,
    trip,
    weather,
)

PARAMS = ScoringParams()


def porto(**overrides: object) -> DestinationInputs:
    data: dict[str, object] = {
        "city_code": "OPO",
        "city_name": "Porto",
        "itinerary": itinerary(),
        "stay": stay(),
        "weather": weather(),
        "activities": activities(),
        "originality": originality(),
    }
    data.update(overrides)
    return DestinationInputs.model_validate(data)


# --- ranking ties ------------------------------------------------------------


def test_equal_totals_are_ordered_by_price_score_before_city_code() -> None:
    base = score_destination(trip(), porto(), TODAY)
    cheaper_later_code = base.model_copy(
        update={
            "city_code": "ZZZ",
            "total": 7.0,
            "price": base.price.model_copy(update={"value": 8.0}),
        }
    )
    pricier_earlier_code = base.model_copy(
        update={
            "city_code": "AAA",
            "total": 7.0,
            "price": base.price.model_copy(update={"value": 6.0}),
        }
    )

    ordered = order_scores([pricier_earlier_code, cheaper_later_code])

    assert [s.city_code for s in ordered] == ["ZZZ", "AAA"]


def test_duplicate_destinations_are_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate destination OPO"):
        rank_destinations(trip(), [porto(), porto()], TODAY)


def test_destination_code_must_match_the_itinerary() -> None:
    with pytest.raises(ValidationError, match="itinerary is for OPO, not LIS"):
        porto(city_code="LIS")


def test_stay_must_be_in_the_destination_city() -> None:
    with pytest.raises(ValidationError, match="stay is in LIS, not OPO"):
        porto(stay=stay(city_code="LIS"))


# --- boundaries ---------------------------------------------------------------


def test_price_exactly_at_the_high_end_scores_0() -> None:
    # 188 flights + 28 ground + 534 stay share = 750 p.p.
    result = score_price(itinerary(), stay(price_total_eur=Decimal("5340")), trip(), PARAMS)

    assert result.value == 0.0


def test_budget_at_or_below_the_low_end_is_raised_just_above_it() -> None:
    # Budget 200 < 250: the scale becomes 251 -> 250, so 412 p.p. scores 0.
    result = score_price(itinerary(), stay(), trip(budget_per_person_eur=200), PARAMS)

    assert result.value == 0.0


def test_wikivoyage_bonus_starts_exactly_at_the_threshold() -> None:
    result = score_activities(activities(counts={"food": 150}, wikivoyage_items=15), PARAMS)

    assert result.inputs["bonus"] == 0.5


def test_excellent_rating_adds_one_point_to_the_stay() -> None:
    result = score_quality(itinerary(), stay(rating=9.5), weather(), trip(), PARAMS)

    assert result.inputs["stay"] == 8.0


def test_stay_for_too_few_guests_scores_0() -> None:
    result = score_quality(itinerary(), stay(guests=9), weather(), trip(), PARAMS)

    assert result.inputs["stay"] == 0.0


def test_future_visit_dates_are_ignored() -> None:
    inputs = originality(previous_visits=[date(2027, 6, 1)])

    result = score_originality(inputs, TODAY, PARAMS)

    assert result.inputs["penalty"] == 0.0


# --- untrusted numbers ----------------------------------------------------------


def test_nan_temperature_is_rejected() -> None:
    with pytest.raises(ValidationError, match="finite number"):
        weather(tmax_c=float("nan"))


def test_infinite_scoring_parameter_is_rejected() -> None:
    with pytest.raises(ValidationError, match="finite number"):
        ScoringParams(price_high_eur=float("inf"))


def test_infinite_weight_is_rejected() -> None:
    with pytest.raises(ValidationError, match="finite number"):
        Weights(price=float("inf"))


def test_physically_impossible_temperature_is_rejected() -> None:
    with pytest.raises(ValidationError, match="tmax_c"):
        weather(tmax_c=99)


def test_negative_activity_count_is_rejected() -> None:
    with pytest.raises(ValidationError, match="greater than or equal to 0"):
        ActivityCounts.model_validate({"counts": {"food": -1}, "confidence": "cached"})


def test_unknown_activity_category_is_rejected() -> None:
    with pytest.raises(ValidationError, match="museum"):
        ActivityCounts.model_validate({"counts": {"museum": 3}, "confidence": "cached"})


# --- untrusted text ---------------------------------------------------------------


@pytest.mark.parametrize("url", ["javascript:alert(1)", "data:text/html,x", "ftp://x.org/a"])
def test_stay_links_must_be_web_addresses(url: str) -> None:
    with pytest.raises(ValidationError, match="http"):
        stay(url=url)


def test_booking_links_must_be_web_addresses() -> None:
    with pytest.raises(ValidationError, match="http"):
        leg(booking_url="javascript:alert(1)")


def test_overlong_stay_name_is_rejected() -> None:
    with pytest.raises(ValidationError, match="at most 200 characters"):
        stay(name="x" * 201)


def test_overlong_visit_history_is_rejected() -> None:
    with pytest.raises(ValidationError, match="at most 50 items"):
        originality(previous_visits=[date(2020, 1, 1)] * 51)


# --- scoring parameters -------------------------------------------------------------


def test_partial_saturation_override_keeps_the_other_categories() -> None:
    params = ScoringParams.model_validate({"activity_saturation": {"food": 100}})

    assert params.activity_saturation["food"] == 100
    assert params.activity_saturation["museums"] == 30
    assert len(params.activity_saturation) == 8


@pytest.mark.parametrize("saturation", [{"food": 0}, {"museum": 10}])
def test_invalid_saturation_is_rejected(saturation: dict[str, int]) -> None:
    with pytest.raises(ValidationError):
        ScoringParams.model_validate({"activity_saturation": saturation})


@pytest.mark.parametrize(
    ("low", "high", "message"),
    [
        ("flight_minutes_best", "flight_minutes_worst", "flight_minutes_best must be below"),
        ("tmax_worst_c", "tmax_best_c", "tmax_worst_c must be below"),
        ("poi_density_quiet", "poi_density_crowded", "poi_density_quiet must be below"),
        ("pageviews_log10_unknown", "pageviews_log10_famous", "pageviews_log10_unknown must be"),
        ("rating_poor", "rating_good", "rating_poor must be below"),
        ("visit_recent_years", "visit_middle_years", "visit_recent_years must be below"),
    ],
)
def test_inverted_ranges_are_rejected(low: str, high: str, message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        ScoringParams.model_validate({low: 10, high: 5})


def test_living_room_scores_are_tunable() -> None:
    params = ScoringParams(stay_likely_score=8)

    result = score_quality(itinerary(), stay(), weather(), trip(), params)

    assert result.inputs["stay"] == 8.0


def test_weather_weights_are_tunable() -> None:
    params = ScoringParams(weather_temperature=1, weather_sunshine=0, weather_rain=0)

    result = score_quality(itinerary(), stay(), weather(tmax_c=18), trip(), params)

    assert result.inputs["weather"] == 10.0


def test_drive_limit_must_exceed_the_ideal_access_time() -> None:
    with pytest.raises(ValidationError, match="max_drive_minutes must be above"):
        trip(max_drive_minutes=40)


@pytest.mark.parametrize(
    ("weights", "group"),
    [
        ({"weather_temperature": 0, "weather_sunshine": 0, "weather_rain": 0}, "weather"),
        ({"activity_amount": 0, "activity_variety": 0}, "activity"),
        ({"originality_fame": 0, "originality_density": 0}, "originality"),
    ],
)
def test_each_weight_group_needs_a_positive_weight(weights: dict[str, float], group: str) -> None:
    with pytest.raises(ValidationError, match=f"at least one {group} weight must be positive"):
        ScoringParams.model_validate(weights)


def test_activity_weights_are_tunable() -> None:
    params = ScoringParams(activity_amount=1, activity_variety=0, wikivoyage_bonus=0)

    result = score_activities(activities(counts={"food": 150}), params)

    # Only the amount counts: food at saturation, 7 empty categories -> 10 / 8.
    assert result.value == pytest.approx(1.25)


def test_originality_weights_are_tunable() -> None:
    params = ScoringParams(originality_fame=1, originality_density=0)

    result = score_originality(originality(tourism_poi_per_km2=80), TODAY, params)

    # Density would be 0 but no longer counts; fame for 100k views is 5.
    assert result.value == pytest.approx(5.0)


def test_rating_bonus_is_tunable() -> None:
    params = ScoringParams(rating_bonus=2)

    result = score_quality(itinerary(), stay(rating=9.5), weather(), trip(), params)

    assert result.inputs["stay"] == 9.0


def test_rating_thresholds_are_tunable() -> None:
    params = ScoringParams(rating_poor=8)

    result = score_quality(itinerary(), stay(rating=7.5), weather(), trip(), params)

    assert result.inputs["stay"] == 6.0


@pytest.mark.parametrize(
    "url",
    [
        "https:evil.example",
        "//host.example/x",
        " javascript:alert(1)",
        "java\tscript:alert(1)",
        "https://x.nl) [Boek hier](javascript:alert(1)",
        'https://x.nl/"><script>',
        "https://user:pw@x.nl/",
        "https://x.nl/a)[Boek](javascript:alert(1))",
    ],
)
def test_malformed_or_injecting_links_are_rejected(url: str) -> None:
    with pytest.raises(ValidationError):
        stay(url=url)


@pytest.mark.parametrize("amount", ["NaN", "Infinity", "1E+400"])
def test_non_finite_or_huge_euro_amounts_are_rejected(amount: str) -> None:
    with pytest.raises(ValidationError):
        stay(price_total_eur=Decimal(amount))


def test_huge_weight_is_rejected() -> None:
    with pytest.raises(ValidationError, match="less than or equal to 100"):
        Weights(price=1e308)


def test_huge_budget_is_rejected() -> None:
    with pytest.raises(ValidationError, match="budget_per_person_eur"):
        trip(budget_per_person_eur=Decimal("1E+400"))


def test_clamp_refuses_nan_instead_of_returning_the_best_score() -> None:
    from app.scoring._common import clamp

    with pytest.raises(ValueError, match="NaN"):
        clamp(float("nan"))


@pytest.mark.parametrize(
    "url",
    [
        "https://www.booking.com/hotel/pt/casa.nl.html?checkin=2027-03-19&group_adults=10",
        "https://en.wikipedia.org/wiki/Porto_(city)",
        "https://xn--bcher-kva.de/a%20b",
    ],
)
def test_ordinary_booking_and_reference_links_are_accepted(url: str) -> None:
    assert stay(url=url).url == url
