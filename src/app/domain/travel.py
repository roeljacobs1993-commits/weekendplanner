"""Flights, itineraries and stays: what a destination offers the group."""

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal, Self
from urllib.parse import urlparse

from pydantic import AfterValidator, AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from app.domain.confidence import Confidence

IataCode = Annotated[str, Field(pattern=r"^[A-Z]{3}$")]
# Upper bounds keep hostile or corrupt source data from overflowing into inf later on.
Euros = Annotated[Decimal, Field(ge=0, le=1_000_000)]
ShortText = Annotated[str, Field(min_length=1, max_length=200)]
Minutes = Annotated[int, Field(ge=0, le=24 * 60)]

ActivityCategory = Literal[
    "museums", "sights", "nightlife", "food", "escape_rooms", "nature", "sport_water", "markets"
]
ActivityCount = Annotated[int, Field(ge=0, le=1_000_000)]


def _web_url(value: str) -> str:
    # Links end up in the report and web UI; javascript: or data: links would run there.
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        msg = "must be an http(s) address"
        raise ValueError(msg)
    return value


WebUrl = Annotated[str, Field(min_length=1, max_length=2048), AfterValidator(_web_url)]


class _Model(BaseModel):
    # allow_inf_nan=False: NaN would compare as the best score after clamping.
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)


class FlightLeg(_Model):
    """One direct flight. Times carry their own (local) time zone."""

    origin_iata: IataCode
    destination_iata: IataCode
    departure: AwareDatetime
    arrival: AwareDatetime
    carrier: ShortText
    flight_number: ShortText
    price_per_person_eur: Euros
    source: ShortText
    confidence: Confidence
    booking_url: WebUrl | None = None

    @property
    def duration_minutes(self) -> int:
        return int((self.arrival - self.departure).total_seconds() // 60)

    @model_validator(mode="after")
    def _arrival_after_departure(self) -> Self:
        if self.arrival <= self.departure:
            msg = "arrival must be after departure"
            raise ValueError(msg)
        return self


class Itinerary(_Model):
    """Outbound and inbound flight to one destination city; the airports may differ."""

    city_code: IataCode
    # Airports of the destination city; defaults to the city code itself (e.g. OPO).
    destination_airports: list[IataCode] = Field(default_factory=list[str])
    outbound: FlightLeg
    inbound: FlightLeg
    outbound_access_minutes: Minutes
    inbound_access_minutes: Minutes
    # Getting the whole group to and from the departure airports (train, fuel, parking).
    ground_cost_eur: Euros
    group_booking_likely: bool = False

    @property
    def is_open_jaw(self) -> bool:
        return self.outbound.origin_iata != self.inbound.destination_iata

    @property
    def flight_price_per_person_eur(self) -> Decimal:
        return self.outbound.price_per_person_eur + self.inbound.price_per_person_eur

    @property
    def access_minutes(self) -> float:
        return (self.outbound_access_minutes + self.inbound_access_minutes) / 2

    @model_validator(mode="after")
    def _serves_the_destination(self) -> Self:
        airports = set(self.destination_airports) or {self.city_code}
        if (
            self.outbound.destination_iata not in airports
            or self.inbound.origin_iata not in airports
        ):
            msg = "outbound must arrive at and inbound depart from the destination city"
            raise ValueError(msg)
        return self


LivingRoom = Literal["confirmed", "likely", "unknown", "absent"]


class Stay(_Model):
    name: ShortText
    city_code: IataCode
    bedrooms: int = Field(ge=1)
    guests: int = Field(ge=1)
    # confirmed: seen by a person; likely: keyword heuristic on the listing; absent: none.
    living_room: LivingRoom
    price_total_eur: Euros
    # Always on a 0-10 scale: adapters convert 0-5 ratings (Airbnb, Google) by doubling.
    rating: float | None = Field(default=None, ge=0, le=10)
    url: WebUrl
    source: ShortText
    confidence: Confidence


class WeatherClimate(_Model):
    """Medians over ~30 years around the travel dates."""

    tmax_c: float = Field(ge=-60, le=60)
    sunshine_hours: float = Field(ge=0, le=24)
    rain_day_fraction: float = Field(ge=0, le=1)
    confidence: Confidence


class ActivityCounts(_Model):
    counts: dict[ActivityCategory, ActivityCount]
    wikivoyage_items: int | None = Field(default=None, ge=0, le=100_000)
    confidence: Confidence


class OriginalityInputs(_Model):
    monthly_pageviews: float | None = Field(default=None, ge=0, le=1e12)
    tourism_poi_per_km2: float | None = Field(default=None, ge=0, le=1e6)
    previous_visits: list[date] = Field(default_factory=list[date], max_length=50)
    confidence: Confidence
