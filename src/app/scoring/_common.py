"""Small pure helpers shared by the scoring functions: scales and Dutch formatting."""

import math
from collections.abc import Iterable
from decimal import Decimal

from app.domain import Confidence, DimensionScore, lowest_confidence

MISSING_SCORE = 5.0

_CONFIDENCE_NL = {
    Confidence.LIVE: "live",
    Confidence.CACHED: "gecachet",
    Confidence.ESTIMATED: "geschat",
}


def lin(x: float, a: float, b: float) -> float:
    """Linear from 0 (at a) to 10 (at b), clamped to [0, 10]. Works for a > b too."""
    if a == b:
        return 10.0 if x == b else 0.0
    return clamp(10 * (x - a) / (b - a))


def clamp(value: float, low: float = 0.0, high: float = 10.0) -> float:
    # min()/max() would turn NaN into the best score; a NaN here is always a bug upstream.
    if math.isnan(value):
        msg = "score is NaN"
        raise ValueError(msg)
    return max(low, min(high, value))


def weighted(parts: Iterable[tuple[float, float]]) -> float:
    """Weighted mean of (weight, score) pairs; weights are validated to sum above zero."""
    pairs = list(parts)
    total_weight = sum(weight for weight, _ in pairs)
    return sum(weight * score for weight, score in pairs) / total_weight


def confidence_of(values: Iterable[Confidence]) -> Confidence:
    return lowest_confidence(values)


def confidence_nl(confidence: Confidence) -> str:
    return _CONFIDENCE_NL[confidence]


def nl_number(value: float, decimals: int = 1) -> str:
    """Dutch notation: 7,4 and 120.000."""
    text = f"{value:,.{decimals}f}"
    return text.replace(",", "_").replace(".", ",").replace("_", ".")


def nl_euros(value: float | Decimal) -> str:
    return f"€ {nl_number(float(value), 0)}"


def missing(label: str, reason: str) -> DimensionScore:
    return DimensionScore(
        value=MISSING_SCORE,
        confidence=Confidence.ESTIMATED,
        explanation=f"{label} {nl_number(MISSING_SCORE)}: geen data {reason}; geschat.",
    )
