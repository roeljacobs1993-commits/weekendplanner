"""How trustworthy a score input is: live data beats cached data beats an estimate."""

from collections.abc import Iterable
from enum import StrEnum


class Confidence(StrEnum):
    LIVE = "live"
    CACHED = "cached"
    ESTIMATED = "estimated"

    @property
    def rank(self) -> int:
        return _RANK[self]


_RANK = {Confidence.LIVE: 2, Confidence.CACHED: 1, Confidence.ESTIMATED: 0}


def lowest_confidence(values: Iterable[Confidence]) -> Confidence:
    """A score is only as trustworthy as its weakest input."""
    return min(values, key=lambda c: c.rank)
