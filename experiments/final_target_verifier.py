"""Deterministic final-target verifier features (offline-safe, gold-free)."""

from __future__ import annotations

import re
from typing import Any


def _norm(text: str | None) -> str:
    return (text or "").strip().lower()


def extract_final_target_signature(problem_text: str) -> dict[str, bool]:
    t = _norm(problem_text)
    return {
        "asks_difference": any(x in t for x in ("how many more", "difference", "withheld", "less than", "more than")),
        "asks_total": any(x in t for x in ("in total", "total", "altogether", "combined", "in all")),
        "asks_remaining": any(x in t for x in ("remaining", "left", "remain", "remains")),
        "asks_ratio_part": any(x in t for x in ("ratio", "twice", "half", "part", "percentage of")),
        "asks_average_target": any(x in t for x in ("average", "mean", "score does she need", "score does he need")),
        "asks_state_value": any(x in t for x in ("how tall", "how much", "how many", "what was", "what is")),
    }


def detect_ratio_partition_risk(problem_text: str) -> bool:
    t = _norm(problem_text)
    return bool(
        ("ratio" in t)
        or ("twice as" in t)
        or ("half as" in t)
        or ("split into" in t and ("equal" in t or "groups" in t))
    )


def detect_percent_base_denominator_risk(problem_text: str) -> bool:
    t = _norm(problem_text)
    has_percent = "%" in t or "percent" in t
    has_base = any(x in t for x in ("of the total", "of the original", "of the capacity", "remaining", "base"))
    has_time = any(x in t for x in ("hour", "day", "week", "later", "after"))
    return bool(has_percent and (has_base or has_time))


def detect_state_update_risk(problem_text: str) -> bool:
    t = _norm(problem_text)
    cues = ("after", "then", "later", "before", "in the end", "started", "grew", "lost", "remaining")
    if sum(1 for c in cues if c in t) >= 2:
        return True
    # Percent/time multi-stage pattern (e.g., "...9% ... then 7% ...")
    if "then" in t and len(re.findall(r"\d+%", t)) >= 2:
        return True
    return False


def detect_final_target_mismatch_risk(
    problem_text: str,
    candidate_answer_text: str | None = None,
    candidate_trace: str | None = None,
) -> bool:
    t = _norm(problem_text)
    ans = _norm(candidate_answer_text)
    tr = _norm(candidate_trace)
    directional = any(x in t for x in ("withheld", "difference", "left", "remaining", "how many more"))
    sign_risk = directional and ans.startswith("-")
    target_restate_missing = directional and ("target" not in tr and "asked" not in tr)
    return bool(sign_risk or target_restate_missing)


def final_target_verifier_features(
    problem_text: str,
    candidate_answer_text: str | None = None,
    candidate_trace: str | None = None,
) -> dict[str, Any]:
    sig = extract_final_target_signature(problem_text)
    ratio_risk = detect_ratio_partition_risk(problem_text)
    percent_base_risk = detect_percent_base_denominator_risk(problem_text)
    state_risk = detect_state_update_risk(problem_text)
    mismatch_risk = detect_final_target_mismatch_risk(problem_text, candidate_answer_text, candidate_trace)
    t = _norm(problem_text)
    dropped_lowest_avg_risk = bool(
        ("average" in t)
        and any(x in t for x in ("drop", "remove", "lowest"))
        and "score" in t
    )
    sign_direction_cue = any(
        x in t for x in ("how many more", "more than", "less than", "difference", "withheld", "remaining")
    )
    return {
        **sig,
        "ratio_partition_risk": ratio_risk,
        "percent_base_denominator_risk": percent_base_risk,
        "state_update_risk": state_risk,
        "final_target_mismatch_risk": mismatch_risk,
        "dropped_lowest_average_risk": dropped_lowest_avg_risk,
        "sign_direction_cue": sign_direction_cue,
    }
