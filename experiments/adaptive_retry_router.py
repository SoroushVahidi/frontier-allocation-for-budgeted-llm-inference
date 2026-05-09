"""Offline adaptive retry router v3 (deterministic, no API calls)."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any


_RX_NUM = re.compile(r"\d+(?:\.\d+)?")


@dataclass(frozen=True)
class AdaptiveRouterV3Config:
    enable_percent_base_denominator: bool = False
    low_risk_base_threshold: int = 1
    high_risk_targeted_threshold: int = 3


def extract_target_quantity_cues(problem_text: str) -> dict[str, bool]:
    t = (problem_text or "").lower()
    return {
        "asks_total": any(x in t for x in ("how many in all", "total", "altogether", "combined")),
        "asks_remaining_or_left": any(x in t for x in ("left", "remaining", "remains")),
        "asks_difference": any(x in t for x in ("how many more", "difference", "than")),
        "asks_rate_or_unit": any(x in t for x in ("per ", "mph", "each hour", "each day", "rate")),
        "asks_money": any(x in t for x in ("$", "dollar", "cost", "profit", "wage", "salary", "price", "balance", "charge", "income")),
        "asks_time": any(x in t for x in ("minute", "hour", "day", "week", "month", "year")),
    }


def extract_number_role_cues(problem_text: str) -> dict[str, bool | int]:
    t = (problem_text or "").lower()
    numeric_count = len(_RX_NUM.findall(t))
    return {
        "numeric_count": numeric_count,
        "percent_or_fraction_cue": any(x in t for x in ("%", "percent", "fraction", "half", "third", "quarter")),
        "ratio_cue": any(x in t for x in ("ratio", "twice", "double", "half as", "as many")),
        "average_cue": "average" in t,
        "combinatorics_cue": any(x in t for x in ("ways", "choose", "split into", "groups such that")),
        "state_change_cue": any(x in t for x in ("after", "before", "then", "later", "in the end", "remaining", "remains")),
        "target_score_cue": any(x in t for x in ("score", "test", "target average")),
        "repeated_period_or_recurring_cue": any(x in t for x in ("every", "per", "each", "monthly", "yearly", "for about")),
        "has_subtraction_trap_verb": any(x in t for x in ("left", "remaining", "withheld", "minus", "fewer")),
        "has_addition_trap_structure": any(x in t for x in ("combined", "altogether", "in all", "plus")),
        "has_multi_operation_hint": sum(1 for x in ("and then", "after", "before", "twice", "half", "%") if x in t) >= 2,
    }


def compute_adaptive_retry_features(
    problem_text: str,
    first_pass_answer: str | None = None,
    first_pass_trace: str | None = None,
) -> dict[str, Any]:
    tq = extract_target_quantity_cues(problem_text)
    nr = extract_number_role_cues(problem_text)
    t = (problem_text or "").lower()

    likely_intermediate_quantity_ask = bool(tq["asks_difference"] and any(x in t for x in ("A has", "B has", "each adult")))
    potential_answer_echo_risk = bool(first_pass_answer and first_pass_answer in (first_pass_trace or ""))
    possible_base_denominator_risk = bool(nr["percent_or_fraction_cue"] and nr["repeated_period_or_recurring_cue"] and tq["asks_money"])

    risk_score = 0
    risk_score += 1 if nr["numeric_count"] >= 4 else 0
    risk_score += 1 if nr["has_multi_operation_hint"] else 0
    risk_score += 1 if nr["percent_or_fraction_cue"] else 0
    risk_score += 1 if likely_intermediate_quantity_ask else 0
    risk_score += 1 if possible_base_denominator_risk else 0

    return {
        **tq,
        **nr,
        "likely_intermediate_quantity_ask": likely_intermediate_quantity_ask,
        "potential_answer_echo_risk": potential_answer_echo_risk,
        "possible_base_denominator_risk": possible_base_denominator_risk,
        "adaptive_retry_risk_score": risk_score,
    }


def choose_adaptive_retry_scaffold_v3(
    problem_text: str,
    features: dict[str, Any],
    config: AdaptiveRouterV3Config,
) -> tuple[str, str, bool]:
    """Return (router_decision, chosen_scaffold_v3, held_back_percent_base)."""
    held_back = False
    candidates: list[str] = []

    if features["average_cue"] or features["target_score_cue"]:
        candidates.append("average_target_score")
    if features["combinatorics_cue"]:
        candidates.append("combinatorics_counting")
    if features["ratio_cue"] and not features["possible_base_denominator_risk"]:
        candidates.append("ratio_partition")
    if features["state_change_cue"] and (features["has_multi_operation_hint"] or features["asks_remaining_or_left"]):
        candidates.append("state_composition")
    if features["asks_rate_or_unit"]:
        candidates.append("rate_table_v1")
    if features["asks_money"] and features["has_multi_operation_hint"] and not features["possible_base_denominator_risk"]:
        candidates.append("quantity_ledger_v2_1")
    if features["asks_difference"]:
        candidates.append("target_difference_v1")
    if features["possible_base_denominator_risk"]:
        if config.enable_percent_base_denominator:
            candidates.append("percent_base_denominator")
        else:
            held_back = True

    # Dominance priority
    priority = [
        "average_target_score",
        "combinatorics_counting",
        "ratio_partition",
        "state_composition",
        "rate_table_v1",
        "quantity_ledger_v2_1",
        "target_difference_v1",
        "percent_base_denominator",
    ]
    dedup = []
    for p in priority:
        if p in candidates and p not in dedup:
            dedup.append(p)
    candidates = dedup

    has_strong_candidate = any(
        c in candidates for c in ("average_target_score", "combinatorics_counting", "ratio_partition", "state_composition")
    )
    if features["adaptive_retry_risk_score"] <= config.low_risk_base_threshold and not has_strong_candidate:
        return "base", "base_method_no_retry", held_back
    if not candidates:
        return "abstain", "unknown", held_back
    if len(candidates) >= 3 and features["adaptive_retry_risk_score"] < config.high_risk_targeted_threshold:
        return "abstain", "unknown", held_back
    return "targeted_retry", candidates[0], held_back


def should_trigger_discovery3_diversity_retry(
    problem_text: str,
    router_features: dict[str, Any],
    verifier_features: dict[str, Any],
    discovery3_metadata: dict[str, Any] | None = None,
) -> bool:
    """Deterministic gold-free trigger for discovery3 candidate-diversity retry.

    Percent-base only risk is intentionally held back by default to avoid broad behavior drift.
    """
    t = (problem_text or "").lower()
    md = discovery3_metadata or {}
    target_type = str(md.get("target_quantity_type") or "").strip().lower()
    allowed_target = {"entity_value", "rate", "ratio_part", "difference"}
    target_ok = (not target_type) or (target_type in allowed_target)

    state_risk = bool(verifier_features.get("state_update_risk")) or bool(router_features.get("state_change_cue"))
    ratio_risk = bool(verifier_features.get("ratio_partition_risk")) or bool(router_features.get("ratio_cue"))
    unknown_high_disagreement = bool(md.get("high_disagreement")) and str(md.get("reasoning_family_guess", "unknown")) == "unknown"
    no_confident_candidate = bool(md.get("no_confident_candidate"))
    percent_only = bool(verifier_features.get("percent_base_denominator_risk")) and not (state_risk or ratio_risk)

    if percent_only:
        return False
    if not target_ok:
        return False
    if state_risk or ratio_risk:
        return True
    if unknown_high_disagreement or no_confident_candidate:
        return True
    if any(x in t for x in ("after", "then", "before", "remaining")) and router_features.get("adaptive_retry_risk_score", 0) >= 2:
        return True
    return False
