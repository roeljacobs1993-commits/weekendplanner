"""Quality: how convenient the flights are, the expected weather and how well the stay fits."""

from datetime import time

from app.domain import (
    Confidence,
    DimensionScore,
    FlightLeg,
    Itinerary,
    ScoringParams,
    Stay,
    TimeWindow,
    TripConfig,
    WeatherClimate,
)
from app.scoring._common import (
    MISSING_SCORE,
    clamp,
    confidence_nl,
    confidence_of,
    lin,
    nl_number,
    weighted,
)

_LIVING_ROOM_NL = {
    "confirmed": "woonkamer bevestigd",
    "likely": "woonkamer waarschijnlijk",
    "unknown": "woonkamer onbekend",
    "absent": "geen woonkamer",
}


def score_quality(
    itinerary: Itinerary,
    stay: Stay | None,
    weather: WeatherClimate | None,
    trip: TripConfig,
    params: ScoringParams,
) -> DimensionScore:
    timing = (
        _timing(itinerary.outbound, trip.outbound, params)
        + _timing(itinerary.inbound, trip.inbound, params)
    ) / 2
    duration_minutes = (
        itinerary.outbound.duration_minutes + itinerary.inbound.duration_minutes
    ) / 2
    duration = lin(duration_minutes, params.flight_minutes_worst, params.flight_minutes_best)
    access = lin(itinerary.access_minutes, trip.max_drive_minutes, params.access_minutes_best)
    flight = (timing + duration + access) / 3

    weather_score, weather_text = _weather(weather, params)
    stay_score, stay_text = _stay(stay, trip, params)
    value = weighted(
        [
            (params.quality_flight, flight),
            (params.quality_weather, weather_score),
            (params.quality_stay, stay_score),
        ]
    )
    confidence = confidence_of(
        [
            itinerary.outbound.confidence,
            itinerary.inbound.confidence,
            weather.confidence if weather is not None else Confidence.ESTIMATED,
            stay.confidence if stay is not None else Confidence.ESTIMATED,
        ]
    )
    explanation = (
        f"Kwaliteit {nl_number(value)}: vluchten {nl_number(flight)} "
        f"(vertrektijden {nl_number(timing)}, vliegduur {nl_number(duration)}, "
        f"reistijd {nl_number(access)}), {weather_text}, {stay_text}; "
        f"{confidence_nl(confidence)}."
    )
    return DimensionScore(
        value=value,
        confidence=confidence,
        explanation=explanation,
        inputs={
            "flight": flight,
            "timing": timing,
            "duration": duration,
            "access": access,
            "weather": weather_score,
            "stay": stay_score,
        },
    )


def _timing(leg: FlightLeg, window: TimeWindow, params: ScoringParams) -> float:
    """10 at the ideal departure time, minus a penalty per hour away from it."""
    ideal = _ideal_hour(window, params)
    if ideal is None:
        return 10.0
    # Local clock time at the departure airport, as the time zone in the data says.
    departure = _hours(leg.departure.timetz())
    return clamp(10 - params.penalty_per_hour_off_ideal * abs(departure - ideal))


def _ideal_hour(window: TimeWindow, params: ScoringParams) -> float | None:
    earliest = _hours(window.earliest) if window.earliest is not None else None
    latest = _hours(window.latest) if window.latest is not None else None
    if earliest is not None and latest is not None:
        return (earliest + latest) / 2
    if earliest is not None:
        return earliest + params.open_window_ideal_offset_hours
    if latest is not None:
        return latest - params.open_window_ideal_offset_hours
    return None


def _hours(moment: time) -> float:
    return moment.hour + moment.minute / 60 + moment.second / 3600


def _weather(weather: WeatherClimate | None, params: ScoringParams) -> tuple[float, str]:
    if weather is None:
        return MISSING_SCORE, "weer geen data"
    score = weighted(
        [
            (
                params.weather_temperature,
                lin(weather.tmax_c, params.tmax_worst_c, params.tmax_best_c),
            ),
            (params.weather_sunshine, lin(weather.sunshine_hours, 0, params.sunshine_best_hours)),
            (params.weather_rain, lin(weather.rain_day_fraction, params.rain_fraction_worst, 0)),
        ]
    )
    text = (
        f"weer {nl_number(score)} ({nl_number(weather.tmax_c, 0)} °C, "
        f"{nl_number(weather.sunshine_hours)} uur zon, "
        f"{nl_number(weather.rain_day_fraction * 100, 0)}% regendagen)"
    )
    return score, text


def _stay(stay: Stay | None, trip: TripConfig, params: ScoringParams) -> tuple[float, str]:
    if stay is None:
        return MISSING_SCORE, "verblijf geen data"
    if stay.bedrooms < trip.required_bedrooms or stay.guests < trip.required_guests:
        return 0.0, "verblijf 0,0 (te klein voor de groep)"
    score = _living_room_score(stay, trip, params)
    if stay.rating is not None and score > 0:
        if stay.rating >= params.rating_good:
            score += params.rating_bonus
        elif stay.rating < params.rating_poor:
            score -= params.rating_bonus
    score = clamp(score)
    return score, f"verblijf {nl_number(score)} ({_LIVING_ROOM_NL[stay.living_room]})"


def _living_room_score(stay: Stay, trip: TripConfig, params: ScoringParams) -> float:
    if stay.living_room == "confirmed":
        return params.stay_confirmed_score
    if stay.living_room == "likely":
        return params.stay_likely_score
    if stay.living_room == "absent" and trip.stay.living_room_required:
        return 0.0
    return params.stay_unknown_score
