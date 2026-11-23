"""Activities: how much there is to do, and how varied it is."""

import math

from app.domain import ActivityCounts, DimensionScore, ScoringParams
from app.scoring._common import clamp, confidence_nl, missing, nl_number, weighted

CATEGORY_NL = {
    "museums": "musea",
    "sights": "bezienswaardigheden",
    "nightlife": "uitgaan",
    "food": "eten",
    "escape_rooms": "escape rooms",
    "nature": "natuur",
    "sport_water": "sport en water",
    "markets": "markten",
}


def score_activities(counts: ActivityCounts | None, params: ScoringParams) -> DimensionScore:
    if counts is None:
        return missing("Activiteiten", "over activiteiten")
    saturation = params.activity_saturation
    per_category = {
        category: 10 * min(1.0, math.log1p(counts.counts.get(category, 0)) / math.log1p(sat))
        for category, sat in saturation.items()
    }
    amount = sum(per_category.values()) / len(per_category)
    rich = [
        category
        for category in saturation
        if counts.counts.get(category, 0) >= params.activity_rich_threshold
    ]
    variety = 10 * len(rich) / len(saturation)
    bonus = (
        params.wikivoyage_bonus
        if (counts.wikivoyage_items or 0) >= params.wikivoyage_bonus_threshold
        else 0.0
    )
    value = clamp(
        weighted([(params.activity_amount, amount), (params.activity_variety, variety)]) + bonus
    )
    return DimensionScore(
        value=value,
        confidence=counts.confidence,
        explanation=_explain(value, counts, rich, bonus, len(saturation)),
        inputs={"amount": amount, "variety": variety, "bonus": bonus},
    )


def _explain(
    value: float, counts: ActivityCounts, rich: list[str], bonus: float, categories: int
) -> str:
    top = sorted(counts.counts.items(), key=lambda item: (-item[1], item[0]))[:2]
    top_text = ", ".join(f"{CATEGORY_NL[name]} {count}" for name, count in top if count)
    parts = [f"{len(rich)} van {categories} categorieën met ruim aanbod"]
    if top_text:
        parts[0] += f" (meeste: {top_text})"
    if counts.wikivoyage_items:
        tips = f"{counts.wikivoyage_items} Wikivoyage-tips"
        if bonus:
            tips += f" (+{nl_number(bonus)})"
        parts.append(tips)
    return (
        f"Activiteiten {nl_number(value)}: {'; '.join(parts)}; {confidence_nl(counts.confidence)}."
    )
