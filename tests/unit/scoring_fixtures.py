"""Shared, realistic inputs for the scoring tests (Porto, 19-22 March 2027)."""

from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from app.domain import (
    ActivityCounts,
    Confidence,
    FlightLeg,
    Itinerary,
    OriginalityInputs,
    Stay,
    TripConfig,
    WeatherClimate,
)

CET = timezone(timedelta(hours=1))
TODAY = date(2026, 11, 23)


def trip(**overrides: Any) -> TripConfig:
    data: dict[str, Any] = {
        "name": "test",
        "home": {"name": "Nijmegen", "lat": 51.8425, "lon": 5.8528},
        "group_size": 10,
        "rooms_min": 5,
        "outbound": {"date": "2027-03-19", "earliest": "12:00", "latest": "18:00"},
        "inbound": {"date": "2027-03-22", "earliest": "15:00"},
    }
    data.update(overrides)
    return TripConfig.model_validate(data)


def leg(**overrides: Any) -> FlightLeg:
    data: dict[str, Any] = {
        "origin_iata": "EIN",
        "destination_iata": "OPO",
        "departure": datetime(2027, 3, 19, 15, 0, tzinfo=CET),
        "arrival": datetime(2027, 3, 19, 16, 30, tzinfo=UTC),
        "carrier": "Transavia",
        "flight_number": "HV6123",
        "price_per_person_eur": Decimal("89"),
        "source": "serpapi",
        "confidence": Confidence.LIVE,
    }
    data.update(overrides)
    return FlightLeg.model_validate(data)


def itinerary(**overrides: Any) -> Itinerary:
    data: dict[str, Any] = {
        "city_code": "OPO",
        "outbound": leg(),
        "inbound": leg(
            origin_iata="OPO",
            destination_iata="EIN",
            departure=datetime(2027, 3, 22, 17, 0, tzinfo=UTC),
            arrival=datetime(2027, 3, 22, 20, 30, tzinfo=CET),
            flight_number="HV6124",
            price_per_person_eur=Decimal("99"),
        ),
        "outbound_access_minutes": 60,
        "inbound_access_minutes": 60,
        "ground_cost_eur": Decimal("280"),
    }
    data.update(overrides)
    return Itinerary.model_validate(data)


def stay(**overrides: Any) -> Stay:
    data: dict[str, Any] = {
        "name": "Casa do Rio",
        "city_code": "OPO",
        "bedrooms": 5,
        "guests": 10,
        "living_room": "likely",
        "price_total_eur": Decimal("1960"),
        "url": "https://example.org/casa-do-rio",
        "source": "serpapi",
        "confidence": Confidence.CACHED,
    }
    data.update(overrides)
    return Stay.model_validate(data)


def weather(**overrides: Any) -> WeatherClimate:
    data: dict[str, Any] = {
        "tmax_c": 17.0,
        "sunshine_hours": 6.0,
        "rain_day_fraction": 0.3,
        "confidence": Confidence.CACHED,
    }
    data.update(overrides)
    return WeatherClimate.model_validate(data)


def activities(**overrides: Any) -> ActivityCounts:
    data: dict[str, Any] = {
        "counts": {
            "museums": 30,
            "sights": 50,
            "nightlife": 40,
            "food": 150,
            "escape_rooms": 5,
            "nature": 20,
            "sport_water": 15,
            "markets": 5,
        },
        "wikivoyage_items": 20,
        "confidence": Confidence.CACHED,
    }
    data.update(overrides)
    return ActivityCounts.model_validate(data)


def originality(**overrides: Any) -> OriginalityInputs:
    data: dict[str, Any] = {
        "monthly_pageviews": 100_000.0,
        "tourism_poi_per_km2": 27.5,
        "previous_visits": [],
        "confidence": Confidence.CACHED,
    }
    data.update(overrides)
    return OriginalityInputs.model_validate(data)
