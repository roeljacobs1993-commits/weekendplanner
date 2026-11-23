"""Trip configuration: the variables an organiser passes in, validated once at the boundary."""

from datetime import date, time
from decimal import Decimal
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.scores import ScoringParams


class _Model(BaseModel):
    # Frozen: a validated config is never mutated; overrides produce a new, re-validated one.
    # extra="forbid": a typo in a trip file must fail loudly instead of being ignored.
    model_config = ConfigDict(frozen=True, extra="forbid")


class GeoPoint(_Model):
    name: str = Field(min_length=1)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class TimeWindow(_Model):
    """A departure window on one date; a missing bound means open-ended."""

    date: date
    earliest: time | None = None
    latest: time | None = None

    @field_validator("earliest", "latest", mode="before")
    @classmethod
    def _reject_numeric_times(cls, value: object) -> object:
        # YAML 1.1 reads an unquoted 12:00 as the number 720, which pydantic would accept
        # as 720 seconds (00:12). Refuse numbers so that mistake can never pass silently.
        if isinstance(value, int | float) and not isinstance(value, bool):
            msg = "write times as quoted 'HH:MM'"
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def _earliest_before_latest(self) -> Self:
        if self.earliest is not None and self.latest is not None and self.earliest >= self.latest:
            msg = "earliest must be before latest"
            raise ValueError(msg)
        return self


class Weights(_Model):
    price: float = Field(default=0.35, ge=0)
    quality: float = Field(default=0.30, ge=0)
    activities: float = Field(default=0.20, ge=0)
    originality: float = Field(default=0.15, ge=0)

    @model_validator(mode="after")
    def _not_all_zero(self) -> Self:
        if self.price + self.quality + self.activities + self.originality <= 0:
            msg = "at least one weight must be positive"
            raise ValueError(msg)
        return self


class StayRequirements(_Model):
    """None means: derive from the trip (bedrooms from rooms_min, guests from group_size)."""

    bedrooms_min: int | None = Field(default=None, ge=1)
    guests_min: int | None = Field(default=None, ge=1)
    living_room_required: bool = True
    required: bool = True


class TripConfig(_Model):
    name: str = Field(min_length=1)
    home: GeoPoint
    group_size: int = Field(ge=1)
    rooms_min: int = Field(ge=1)
    persons_per_room: int = Field(default=2, ge=1)
    outbound: TimeWindow
    inbound: TimeWindow
    nonstop_only: bool = True
    max_drive_minutes: int = Field(default=150, gt=0)
    max_ov_minutes: int = Field(default=180, gt=0)
    top_n: Literal[3, 5, 10] = 5
    top_k_live: int = Field(default=12, ge=1)
    budget_per_person_eur: Decimal | None = Field(default=None, gt=0)
    weights: Weights = Weights()
    stay: StayRequirements = StayRequirements()
    scoring: ScoringParams = ScoringParams()

    @property
    def nights(self) -> int:
        return (self.inbound.date - self.outbound.date).days

    @property
    def required_bedrooms(self) -> int:
        """Bedrooms a stay must have: the explicit stay setting, else rooms_min."""
        explicit = self.stay.bedrooms_min
        return explicit if explicit is not None else self.rooms_min

    @property
    def required_guests(self) -> int:
        """Guests a stay must sleep: the explicit stay setting, else the group size."""
        explicit = self.stay.guests_min
        return explicit if explicit is not None else self.group_size

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.inbound.date <= self.outbound.date:
            msg = "inbound date must be after the outbound date"
            raise ValueError(msg)
        if self.rooms_min * self.persons_per_room < self.group_size:
            msg = "rooms_min x persons_per_room must be at least group_size"
            raise ValueError(msg)
        if self.top_k_live < self.top_n:
            msg = "top_k_live must be at least top_n"
            raise ValueError(msg)
        if self.required_bedrooms < self.rooms_min:
            msg = "stay.bedrooms_min must be at least rooms_min"
            raise ValueError(msg)
        if self.required_guests < self.group_size:
            msg = "stay.guests_min must be at least group_size"
            raise ValueError(msg)
        return self
