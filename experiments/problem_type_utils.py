from __future__ import annotations

import re


PROBLEM_TYPES: tuple[str, ...] = (
    "counting_combinatorics",
    "multi_step_arithmetic",
    "ratio_percent",
    "comparison",
    "unit_conversion",
    "algebra_like",
    "single_arithmetic",
    "unknown",
)


def classify_problem_type(question: str) -> str:
    q = (question or "").lower()
    if not q.strip():
        return "unknown"
    combinatorics_terms = (
        "how many",
        "ways",
        "choose",
        "arrange",
        "combination",
        "permutation",
        "different possible",
        "different",
        "distinct",
        "possible",
        "number of possible",
        "can be made",
        "can be selected",
        "outcomes",
        "pairs",
        "groups",
        "seating",
        "order",
    )
    if any(t in q for t in combinatorics_terms):
        return "counting_combinatorics"
    if any(t in q for t in ("percent", "%", "ratio", "fraction", "rate", "per ")):
        return "ratio_percent"
    if any(t in q for t in ("more than", "less than", "greater than", "fewer", "difference", "compared")):
        return "comparison"
    if any(t in q for t in ("km", "kilometer", "meter", "cm", "inch", "mile", "kg", "gram", "liter", "hour", "minute", "second")):
        return "unit_conversion"
    if any(t in q for t in ("equation", "solve for", "variable", "x =", "x=", "y =", "y=")):
        return "algebra_like"
    n_num = len(re.findall(r"[-+]?\d*\.?\d+", q))
    n_sent = len([s for s in re.split(r"[.!?]+", q) if s.strip()])
    if n_num >= 3 or n_sent >= 3:
        return "multi_step_arithmetic"
    if n_num >= 1:
        return "single_arithmetic"
    return "unknown"

