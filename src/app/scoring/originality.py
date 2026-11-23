"""Originality: less famous, less crowded and not visited before scores higher."""

import math
from datetime import date

from app.domain import Confidence, DimensionScore, OriginalityInputs, ScoringParams
from app.scoring._common import (
    MISSING_SCORE,
    confidence_nl,
    confidence_of,
    lin,
    missing,
    nl_number,
)

_DAYS_PER_YEAR = 365.25
_RECENT_YEARS = 2
_MIDDLE_YEARS = 5


def score_originality(
    inputs: OriginalityInputs | None, today: date, params: ScoringParams
) -> DimensionScore:
    if inputs is None:
        return missing("Originaliteit", "over bekendheid en drukte")
    confidences = [inputs.confidence]
    if inputs.monthly_pageviews is None:
        fame, fame_text = MISSING_SCORE, "bekendheid geen data"
        confidences.append(Confidence.ESTIMATED)
    else:
        views = max(inputs.monthly_pageviews, 1.0)
        fame = lin(math.log10(views), params.pageviews_log10_famous, params.pageviews_log10_unknown)
        fame_text = f"bekendheid {nl_number(fame)} ({nl_number(views, 0)} views/maand)"
    if inputs.tourism_poi_per_km2 is None:
        density, density_text = MISSING_SCORE, "drukte geen data"
        confidences.append(Confidence.ESTIMATED)
    else:
        poi = inputs.tourism_poi_per_km2
        density = lin(poi, params.poi_density_crowded, params.poi_density_quiet)
        density_text = f"drukte {nl_number(density)} ({nl_number(poi, 0)} POI/km²)"
    base = 0.6 * fame + 0.4 * density
    penalty = min(
        params.visit_penalty_max,
        sum(_visit_penalty(visit, today, params) for visit in inputs.previous_visits),
    )
    value = max(0.0, base - penalty)
    confidence = confidence_of(confidences)
    parts = [f"{fame_text}, {density_text}"]
    if inputs.previous_visits:
        years = ", ".join(str(visit.year) for visit in sorted(inputs.previous_visits))
        parts.append(f"eerder bezocht in {years} (-{nl_number(penalty)})")
    return DimensionScore(
        value=value,
        confidence=confidence,
        explanation=(
            f"Originaliteit {nl_number(value)}: {'; '.join(parts)}; {confidence_nl(confidence)}."
        ),
        inputs={"fame": fame, "density": density, "penalty": penalty},
    )


def _visit_penalty(visited: date, today: date, params: ScoringParams) -> float:
    years_ago = (today - visited).days / _DAYS_PER_YEAR
    if years_ago < _RECENT_YEARS:
        return params.visit_penalty_recent
    if years_ago < _MIDDLE_YEARS:
        return params.visit_penalty_middle
    return params.visit_penalty_old
