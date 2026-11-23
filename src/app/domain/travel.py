"""Flights, itineraries and stays: what a destination offers the group."""

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from app.domain.confidence import Confidence

IataCode = Annotated[str, Field(pattern=r"^[A-Z]{3}$")]
Euros = Annotated[Decimal, Field(ge=0)]


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class FlightLeg(_Model):
    """One direct flight. Times carry their own (local) time zone."""

    origin_iata: IataCode
    destination_iata: IataCode
    departure: AwareDatetime
    arrival: AwareDatetime
    carrier: str = Field(min_length=1)
    flight_number: str = Field(min_length=1)
    price_per_person_eur: Euros
    source: str = Field(min_length=1)
    confidence: Confidence
    booking_url: str | None = None

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
    outbound_access_minutes: int = Field(ge=0)
    inbound_access_minutes: int = Field(ge=0)
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
    name: str = Field(min_length=1)
    city_code: IataCode
    bedrooms: int = Field(ge=1)
    guests: int = Field(ge=1)
    # confirmed: seen by a person; likely: keyword heuristic on the listing; absent: none.
    living_room: LivingRoom
    price_total_eur: Euros
    rating: float | None = Field(default=None, ge=0, le=10)
    url: str = Field(min_length=1)
    source: str = Field(min_length=1)
    confidence: Confidence


class WeatherClimate(_Model):
    """Medians over ~30 years around the travel dates."""

    tmax_c: float
    sunshine_hours: float = Field(ge=0, le=24)
    rain_day_fraction: float = Field(ge=0, le=1)
    confidence: Confidence


class ActivityCounts(_Model):
    counts: dict[str, int]
    wikivoyage_items: int | None = Field(default=None, ge=0)
    confidence: Confidence


class OriginalityInputs(_Model):
    monthly_pageviews: float | None = Field(default=None, ge=0)
    tourism_poi_per_km2: float | None = Field(default=None, ge=0)
    previous_visits: list[date] = Field(default_factory=list[date])
    confidence: Confidence
