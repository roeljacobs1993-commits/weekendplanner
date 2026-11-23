import ast
from decimal import Decimal
from pathlib import Path

import pytest

from app.domain import TripConfig
from app.scoring import DestinationInputs, rank_destinations, score_destination
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


def city(code: str, name: str, flight_price: str) -> DestinationInputs:
    out = leg(destination_iata=code, price_per_person_eur=Decimal(flight_price))
    back = itinerary().inbound.model_copy(
        update={"origin_iata": code, "price_per_person_eur": Decimal(flight_price)}
    )
    return porto(
        city_code=code,
        city_name=name,
        itinerary=itinerary(city_code=code, outbound=out, inbound=back),
        stay=stay(city_code=code),
    )


def test_total_is_the_weighted_mean_of_the_four_dimensions() -> None:
    result = score_destination(trip(), porto(), TODAY)

    expected = (
        0.35 * result.price.value
        + 0.30 * result.quality.value
        + 0.20 * result.activities.value
        + 0.15 * result.originality.value
    )
    assert result.total == pytest.approx(expected)


def test_weights_from_the_trip_change_the_total() -> None:
    price_only = trip(weights={"price": 1, "quality": 0, "activities": 0, "originality": 0})

    result = score_destination(price_only, porto(), TODAY)

    assert result.total == pytest.approx(result.price.value)


def test_ranking_sorts_by_total_descending() -> None:
    destinations = [city("LIS", "Lissabon", "150"), city("OPO", "Porto", "60")]

    ranked = rank_destinations(trip(), destinations, TODAY)

    assert [d.city_code for d in ranked] == ["OPO", "LIS"]


def test_equal_totals_are_ordered_by_city_code() -> None:
    destinations = [city("SVQ", "Sevilla", "90"), city("BIO", "Bilbao", "90")]

    ranked = rank_destinations(trip(), destinations, TODAY)

    assert [d.city_code for d in ranked] == ["BIO", "SVQ"]


def test_input_order_does_not_change_the_ranking() -> None:
    destinations = [
        city("LIS", "Lissabon", "150"),
        city("OPO", "Porto", "60"),
        city("BIO", "Bilbao", "90"),
        city("SVQ", "Sevilla", "90"),
    ]

    forward = rank_destinations(trip(top_n=10), destinations, TODAY)
    backward = rank_destinations(trip(top_n=10), list(reversed(destinations)), TODAY)

    assert [d.city_code for d in forward] == [d.city_code for d in backward]


def test_ranking_returns_at_most_top_n() -> None:
    destinations = [city(code, code, "90") for code in ("AAA", "BBB", "CCC", "DDD")]

    ranked = rank_destinations(trip(top_n=3), destinations, TODAY)

    assert len(ranked) == 3


def test_flags_mark_open_jaw_group_booking_and_budget() -> None:
    back = itinerary().inbound.model_copy(update={"destination_iata": "DUS"})
    inputs = porto(itinerary=itinerary(inbound=back, group_booking_likely=True))

    result = score_destination(trip(budget_per_person_eur=300), inputs, TODAY)

    assert result.flags == ["open_jaw", "group_booking", "over_budget"]


def test_missing_stay_is_flagged() -> None:
    result = score_destination(trip(), porto(stay=None), TODAY)

    assert result.flags == ["no_stay"]
    assert result.price_per_person_eur is None


def test_scoring_params_can_be_overridden_in_the_trip_file() -> None:
    custom = trip(scoring={"price_low_eur": 100, "price_high_eur": 412})

    result = score_destination(custom, porto(), TODAY)

    assert custom.scoring.price_low_eur == 100
    assert result.price.value == pytest.approx(0.0)


def test_unknown_scoring_parameter_is_rejected() -> None:
    with pytest.raises(ValueError, match="price_lowest"):
        TripConfig.model_validate(trip().model_dump() | {"scoring": {"price_lowest": 1}})


SCORING_PACKAGE = Path(__file__).parents[2] / "src" / "app" / "scoring"
FORBIDDEN_MODULES = {
    "httpx",
    "requests",
    "socket",
    "urllib",
    "sqlalchemy",
    "sqlite3",
    "pathlib",
    "os",
    "io",
    "shutil",
    "subprocess",
    "tempfile",
    "glob",
}


def _scoring_trees() -> list[ast.AST]:
    return [ast.parse(p.read_text(encoding="utf-8")) for p in sorted(SCORING_PACKAGE.rglob("*.py"))]


def _imported_modules(tree: ast.AST) -> set[str]:
    plain = {
        a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names
    }
    from_ = {
        (n.module or "").split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)
    }
    return plain | from_


def _calls_open(tree: ast.AST) -> bool:
    return any(
        isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "open"
        for n in ast.walk(tree)
    )


def test_scoring_package_imports_no_io_modules() -> None:
    imported = set[str]().union(*(_imported_modules(tree) for tree in _scoring_trees()))

    assert imported & FORBIDDEN_MODULES == set()


def test_scoring_package_never_opens_files() -> None:
    assert not any(_calls_open(tree) for tree in _scoring_trees())
