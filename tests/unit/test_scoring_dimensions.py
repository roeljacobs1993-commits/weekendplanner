from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from app.domain import Confidence, ScoringParams
from app.scoring import (
    lin,
    score_activities,
    score_originality,
    score_price,
    score_quality,
)
from tests.unit.scoring_fixtures import (
    CET,
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


# --- lin -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("x", "expected"),
    [(0, 0.0), (5, 5.0), (10, 10.0), (-3, 0.0), (99, 10.0)],
)
def test_lin_rises_from_0_to_10_and_is_clamped(x: float, expected: float) -> None:
    assert lin(x, 0, 10) == expected


def test_lin_can_run_downwards() -> None:
    assert lin(250, 750, 250) == 10.0


# --- price -----------------------------------------------------------------


def test_price_at_the_low_end_scores_10() -> None:
    cheap = itinerary(
        outbound=leg(price_per_person_eur=Decimal("50")),
        inbound=itinerary().inbound.model_copy(update={"price_per_person_eur": Decimal("50")}),
        ground_cost_eur=Decimal("0"),
    )

    result = score_price(cheap, stay(price_total_eur=Decimal("1500")), trip(), PARAMS)

    assert result.value == 10.0


def test_price_at_or_above_the_high_end_scores_0() -> None:
    result = score_price(itinerary(), stay(price_total_eur=Decimal("9000")), trip(), PARAMS)

    assert result.value == 0.0


def test_price_in_between_is_linear() -> None:
    # 188 flights + 196 stay + 28 ground = 412 p.p. -> (750 - 412) / 500 * 10 = 6.76
    result = score_price(itinerary(), stay(), trip(), PARAMS)

    assert result.value == pytest.approx(6.76)
    assert result.inputs["per_person_eur"] == pytest.approx(412)


def test_budget_replaces_the_high_end_of_the_price_scale() -> None:
    result = score_price(itinerary(), stay(), trip(budget_per_person_eur=500), PARAMS)

    assert result.value == pytest.approx(3.52)


def test_price_without_a_stay_is_estimated_at_5() -> None:
    result = score_price(itinerary(), None, trip(), PARAMS)

    assert result.value == 5.0
    assert result.confidence is Confidence.ESTIMATED
    assert "geen data" in result.explanation


def test_price_confidence_is_the_weakest_input() -> None:
    result = score_price(itinerary(), stay(confidence=Confidence.ESTIMATED), trip(), PARAMS)

    assert result.confidence is Confidence.ESTIMATED


def test_price_explanation_is_dutch_with_amounts_and_confidence() -> None:
    result = score_price(itinerary(), stay(), trip(), PARAMS)

    assert result.explanation == (
        "Prijs 6,8: € 412 p.p. (vlucht € 188, verblijf € 196, vervoer € 28); "
        "vluchten live, verblijf gecachet."
    )


# --- quality ---------------------------------------------------------------


def test_quality_of_ideal_inputs_is_10() -> None:
    ideal = itinerary(
        outbound=leg(
            departure=datetime(2027, 3, 19, 15, 0, tzinfo=CET),
            arrival=datetime(2027, 3, 19, 15, 30, tzinfo=UTC),
        ),
        inbound=leg(
            origin_iata="OPO",
            destination_iata="EIN",
            departure=datetime(2027, 3, 22, 18, 0, tzinfo=CET),
            arrival=datetime(2027, 3, 22, 18, 30, tzinfo=UTC),
        ),
        outbound_access_minutes=30,
        inbound_access_minutes=30,
    )
    best_weather = weather(tmax_c=25, sunshine_hours=10, rain_day_fraction=0)

    result = score_quality(
        ideal, stay(living_room="confirmed", rating=9.5), best_weather, trip(), PARAMS
    )

    assert result.value == 10.0


def test_quality_of_the_worst_inputs_is_0() -> None:
    worst = itinerary(
        outbound=leg(
            departure=datetime(2027, 3, 19, 23, 0, tzinfo=CET),
            arrival=datetime(2027, 3, 20, 4, 0, tzinfo=UTC),
        ),
        inbound=leg(
            origin_iata="OPO",
            destination_iata="EIN",
            departure=datetime(2027, 3, 22, 6, 0, tzinfo=CET),
            arrival=datetime(2027, 3, 22, 10, 0, tzinfo=CET),
        ),
        outbound_access_minutes=150,
        inbound_access_minutes=150,
    )
    bad_weather = weather(tmax_c=2, sunshine_hours=0, rain_day_fraction=0.8)

    result = score_quality(worst, stay(living_room="absent"), bad_weather, trip(), PARAMS)

    assert result.value == 0.0


def test_quality_in_between_combines_flight_weather_and_stay() -> None:
    # flight: timing (10 + 8) / 2 = 9 (inbound 17:00, ideal 18:00 for "after 15:00"),
    # duration lin(150 avg, 240, 90) = 6, access lin(60, 150, 45) = 8.571 -> 7.857;
    # weather 0.4*9.231 + 0.3*7.5 + 0.3*5 = 7.442; stay likely = 7.
    result = score_quality(itinerary(), stay(), weather(), trip(), PARAMS)

    assert result.value == pytest.approx(0.40 * 7.8571 + 0.35 * 7.4423 + 0.25 * 7, abs=0.001)


def test_departure_off_the_ideal_time_loses_2_points_per_hour() -> None:
    # Outbound window 12:00-18:00: ideal 15:00. 13:00 is 2 hours off -> 6; inbound stays 8.
    early = itinerary(
        outbound=leg(
            departure=datetime(2027, 3, 19, 13, 0, tzinfo=CET),
            arrival=datetime(2027, 3, 19, 14, 30, tzinfo=UTC),
        )
    )

    result = score_quality(early, stay(), weather(), trip(), PARAMS)

    assert result.inputs["timing"] == pytest.approx((6 + 8) / 2)


def test_missing_weather_and_stay_count_as_5_and_estimated() -> None:
    result = score_quality(itinerary(), None, None, trip(), PARAMS)

    assert result.inputs["weather"] == 5.0
    assert result.inputs["stay"] == 5.0
    assert result.confidence is Confidence.ESTIMATED
    assert "weer geen data" in result.explanation


def test_stay_too_small_for_the_group_scores_0() -> None:
    result = score_quality(itinerary(), stay(bedrooms=4), weather(), trip(), PARAMS)

    assert result.inputs["stay"] == 0.0


def test_quality_explanation_is_dutch() -> None:
    result = score_quality(itinerary(), stay(), weather(), trip(), PARAMS)

    assert result.explanation == (
        "Kwaliteit 7,5: vluchten 7,9 (vertrektijden 9,0, vliegduur 6,0, reistijd 8,6), "
        "weer 7,4 (17 °C, 6,0 uur zon, 30% regendagen), verblijf 7,0 (woonkamer waarschijnlijk); "
        "gecachet."
    )


# --- activities ------------------------------------------------------------


def test_activities_at_saturation_in_every_category_score_10() -> None:
    result = score_activities(activities(), PARAMS)

    assert result.value == 10.0


def test_no_activities_at_all_score_0() -> None:
    result = score_activities(activities(counts={}, wikivoyage_items=0), PARAMS)

    assert result.value == 0.0


def test_activities_in_between_mix_amount_and_variety() -> None:
    # Only food at saturation: amount = 10/8 = 1.25, variety = 10 * 1/8 = 1.25 -> 1.25.
    result = score_activities(activities(counts={"food": 150}, wikivoyage_items=0), PARAMS)

    assert result.value == pytest.approx(1.25)


def test_wikivoyage_bonus_is_capped_at_10() -> None:
    result = score_activities(activities(wikivoyage_items=99), PARAMS)

    assert result.value == 10.0


def test_missing_activity_data_is_estimated_at_5() -> None:
    result = score_activities(None, PARAMS)

    assert (result.value, result.confidence) == (5.0, Confidence.ESTIMATED)
    assert result.explanation == "Activiteiten 5,0: geen data over activiteiten; geschat."


def test_activities_explanation_is_dutch() -> None:
    counts = {"food": 150, "sights": 12, "museums": 2}

    result = score_activities(activities(counts=counts, wikivoyage_items=18), PARAMS)

    assert result.explanation == (
        "Activiteiten 3,0: 2 van 8 categorieën met ruim aanbod "
        "(meeste: eten 150, bezienswaardigheden 12); 18 Wikivoyage-tips (+0,5); gecachet."
    )


# --- originality -----------------------------------------------------------


def test_little_known_quiet_place_scores_10() -> None:
    inputs = originality(monthly_pageviews=1_000, tourism_poi_per_km2=1)

    assert score_originality(inputs, TODAY, PARAMS).value == 10.0


def test_famous_crowded_place_scores_0() -> None:
    inputs = originality(monthly_pageviews=5_000_000, tourism_poi_per_km2=80)

    assert score_originality(inputs, TODAY, PARAMS).value == 0.0


def test_originality_in_between() -> None:
    # log10(100k) = 5 -> fame 5; density lin(27.5, 50, 5) = 5 -> 5.
    assert score_originality(originality(), TODAY, PARAMS).value == pytest.approx(5.0)


@pytest.mark.parametrize(
    ("visited", "penalty"),
    [(date(2025, 6, 1), 4.0), (date(2022, 6, 1), 2.0), (date(2015, 6, 1), 1.0)],
)
def test_earlier_visits_lower_originality_by_age(visited: date, penalty: float) -> None:
    result = score_originality(originality(previous_visits=[visited]), TODAY, PARAMS)

    assert result.value == pytest.approx(5.0 - penalty)


def test_visit_penalty_is_capped_and_never_below_0() -> None:
    visits = [date(2025, 1, 1), date(2025, 6, 1), date(2026, 1, 1)]

    result = score_originality(originality(previous_visits=visits), TODAY, PARAMS)

    assert result.value == 0.0
    assert result.inputs["penalty"] == 6.0


def test_missing_originality_parts_are_estimated() -> None:
    inputs = originality(monthly_pageviews=None)

    result = score_originality(inputs, TODAY, PARAMS)

    assert result.inputs["fame"] == 5.0
    assert result.confidence is Confidence.ESTIMATED


def test_originality_explanation_is_dutch() -> None:
    inputs = originality(previous_visits=[date(2025, 6, 1)])

    result = score_originality(inputs, TODAY, PARAMS)

    assert result.explanation == (
        "Originaliteit 1,0: bekendheid 5,0 (100.000 views/maand), drukte 5,0 (28 POI/km²); "
        "eerder bezocht in 2025 (-4,0); gecachet."
    )


def test_departure_timing_uses_the_clock_of_the_time_zone_in_the_data() -> None:
    # Sources must deliver local airport times. 14:00 UTC is read as 14:00, one hour before
    # the 15:00 ideal (-> 8), even though it is 15:00 in Eindhoven. Inbound stays 8.
    in_utc = itinerary(
        outbound=leg(
            departure=datetime(2027, 3, 19, 14, 0, tzinfo=UTC),
            arrival=datetime(2027, 3, 19, 16, 30, tzinfo=UTC),
        )
    )

    result = score_quality(in_utc, stay(), weather(), trip(), PARAMS)

    assert result.inputs["timing"] == pytest.approx((8 + 8) / 2)


def test_lin_with_equal_bounds_is_a_step() -> None:
    assert (lin(5, 5, 5), lin(4, 5, 5)) == (10.0, 0.0)


def test_window_without_bounds_never_penalises_the_departure_time() -> None:
    open_trip = trip(
        outbound={"date": "2027-03-19"},
        inbound={"date": "2027-03-22"},
    )

    result = score_quality(itinerary(), stay(), weather(), open_trip, PARAMS)

    assert result.inputs["timing"] == 10.0


def test_window_with_only_a_latest_time_has_its_ideal_before_it() -> None:
    # Outbound "before 18:00": ideal 15:00, so the 15:00 departure scores 10.
    before_six = trip(
        outbound={"date": "2027-03-19", "latest": "18:00"},
        inbound={"date": "2027-03-22", "earliest": "15:00", "latest": "21:00"},
    )

    result = score_quality(itinerary(), stay(), weather(), before_six, PARAMS)

    # Inbound 17:00 vs ideal 18:00 (middle of 15:00-21:00) -> 8.
    assert result.inputs["timing"] == pytest.approx((10 + 8) / 2)


def test_missing_living_room_counts_as_unknown_when_not_required() -> None:
    relaxed = trip(stay={"living_room_required": False})

    result = score_quality(itinerary(), stay(living_room="absent"), weather(), relaxed, PARAMS)

    assert result.inputs["stay"] == 5.0


def test_poor_rating_lowers_the_stay_score_by_one() -> None:
    result = score_quality(itinerary(), stay(rating=6.0), weather(), trip(), PARAMS)

    assert result.inputs["stay"] == 6.0


def test_missing_originality_data_is_estimated_at_5() -> None:
    result = score_originality(None, TODAY, PARAMS)

    assert (result.value, result.confidence) == (5.0, Confidence.ESTIMATED)


def test_missing_poi_density_counts_as_5() -> None:
    result = score_originality(originality(tourism_poi_per_km2=None), TODAY, PARAMS)

    assert result.inputs["density"] == 5.0
    assert "drukte geen data" in result.explanation


def test_quality_weights_must_not_all_be_zero() -> None:
    with pytest.raises(ValueError, match="at least one quality weight must be positive"):
        ScoringParams(quality_flight=0, quality_weather=0, quality_stay=0)
