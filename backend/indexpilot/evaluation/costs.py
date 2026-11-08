import math


def cost_reduction(baseline: float | None, candidate: float | None) -> float | None:
    if (
        baseline is None
        or candidate is None
        or not math.isfinite(baseline)
        or not math.isfinite(candidate)
        or baseline <= 0
        or candidate < 0
    ):
        return None
    value = (1 - candidate / baseline) * 100
    return value if math.isfinite(value) else None


def weighted_cost(values) -> float | None:
    terms = []
    for frequency, cost in values:
        if (
            cost is None
            or not math.isfinite(cost)
            or cost < 0
            or not math.isfinite(frequency)
            or frequency <= 0
        ):
            return None
        term = frequency * cost
        if not math.isfinite(term):
            return None
        terms.append(term)
    try:
        return math.fsum(terms)
    except OverflowError:
        return None
