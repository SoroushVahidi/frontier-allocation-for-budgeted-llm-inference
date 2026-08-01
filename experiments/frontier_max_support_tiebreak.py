"""Gold-free max-support tiebreak using frontier vs direct answer-group mass (diagnostic helpers)."""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

from experiments.data import extract_final_answer

LETTER_RE = re.compile(r"^[A-Da-d]$")
NEAR_TIE_SUPPORT_GAP_THRESHOLD = 1
FORBIDDEN_TIEBREAK_FEATURE_KEYS = frozenset(
    {
        "gold_answer",
        "gold_in_tree",
        "is_correct",
        "oracle",
        "exact_match",
        "correct_answer",
        "d6_bucket",
        "d9_bucket",
    }
)


def normalize_answer_group_key(text: str | None) -> str:
    """Match ``controllers._normalize_answer`` grouping for histogram keys (no gold)."""
    if text is None:
        return ""
    stripped = str(text).strip()
    nums = re.findall(r"[-+]?\d+(?:\.\d+)?", stripped.replace(",", ""))
    if nums:
        value = nums[-1]
        if value.endswith(".0"):
            value = value[:-2]
        return value
    return stripped.lower()


def commit_surrogate_group_key(
    final_answer: str | None,
    direct_trace: list[dict[str, Any]] | None,
) -> str | None:
    """Runtime-legal commit key: final answer if present, else last JSON-ish direct response extraction."""
    if final_answer is not None and str(final_answer).strip():
        g = normalize_answer_group_key(str(final_answer))
        return g or None
    if not direct_trace:
        return None
    last = direct_trace[-1]
    ext = extract_final_answer(str(last.get("response_text") or ""))
    if ext is None or not str(ext).strip():
        return None
    g = normalize_answer_group_key(str(ext))
    return g or None


def build_merged_support_histogram_for_tiebreak(
    answer_group_support_counts: dict[str, Any],
    *,
    final_answer: str | None,
    direct_trace: list[dict[str, Any]] | None,
) -> dict[str, int]:
    """Merge controller ``answer_group_support_counts`` with a singleton commit surrogate when needed.

    Mirrors offline selector-loss bookkeeping: if the repair/surface commit group is absent from the
    combined histogram, add a single count so low-support frontier vs brittle-parse ties are visible.
    """
    merged: Counter[str] = Counter()
    if isinstance(answer_group_support_counts, dict):
        for k, v in answer_group_support_counts.items():
            ks = str(k).strip()
            if not ks or ks == "__unknown__":
                continue
            try:
                merged[ks] += int(v)
            except Exception:
                continue
    cg = commit_surrogate_group_key(final_answer, direct_trace)
    if cg and cg != "__unknown__" and cg not in merged:
        merged[cg] += 1
    return dict(merged)


def resolve_frontier_bias_max_support_tiebreak(
    merged_support: dict[str, int],
    frontier_answer_group_counts: dict[str, Any],
    direct_answer_group_counts: dict[str, Any],
    *,
    previous_group_key: str,
) -> tuple[str | None, dict[str, Any]]:
    """Among max-total-support ties, prefer higher frontier mass then lower direct mass; else keep prior.

    Returns ``(chosen_group_key_or_none, metadata)`` where ``None`` means keep caller's prediction.
    """
    meta: dict[str, Any] = {
        "frontier_tiebreak_triggered": False,
        "frontier_tiebreak_selected_group": "",
        "frontier_tiebreak_previous_group": str(previous_group_key).strip() or "__unknown__",
        "frontier_tiebreak_reason": "not_evaluated",
    }
    if not isinstance(merged_support, dict) or not merged_support:
        meta["frontier_tiebreak_reason"] = "empty_merged_support"
        return None, meta
    if not isinstance(frontier_answer_group_counts, dict) or not frontier_answer_group_counts:
        meta["frontier_tiebreak_reason"] = "missing_frontier_answer_group_counts"
        return None, meta
    if not isinstance(direct_answer_group_counts, dict):
        meta["frontier_tiebreak_reason"] = "missing_direct_answer_group_counts"
        return None, meta

    def _fc(g: str) -> int:
        try:
            return int(frontier_answer_group_counts.get(g, 0) or 0)
        except Exception:
            return 0

    def _dc(g: str) -> int:
        try:
            return int(direct_answer_group_counts.get(g, 0) or 0)
        except Exception:
            return 0

    try:
        max_support = max(int(v) for v in merged_support.values())
    except Exception:
        meta["frontier_tiebreak_reason"] = "invalid_merged_support_values"
        return None, meta

    tied = sorted(
        [
            str(g).strip()
            for g, c in merged_support.items()
            if str(g).strip() not in {"", "__unknown__"} and int(c) == int(max_support)
        ]
    )
    if len(tied) <= 1:
        meta["frontier_tiebreak_reason"] = "no_max_support_tie"
        meta["frontier_tiebreak_selected_group"] = ""
        return None, meta

    eff_prev = str(previous_group_key).strip() or "__unknown__"
    if eff_prev == "__unknown__":
        eff_prev = tied[0]
    meta["frontier_tiebreak_previous_group"] = str(eff_prev)

    ranked = sorted(tied, key=lambda g: (-_fc(g), _dc(g), g))
    top_f = _fc(ranked[0])
    top_direct = _dc(ranked[0])
    fully_tied = all(_fc(g) == top_f and _dc(g) == top_direct for g in tied)
    if fully_tied:
        meta["frontier_tiebreak_reason"] = "still_tied_all_criteria_keep_current"
        meta["frontier_tiebreak_selected_group"] = ""
        return None, meta

    chosen = ranked[0]
    if str(chosen) == str(eff_prev):
        meta["frontier_tiebreak_reason"] = "tiebreak_keeps_current_group"
        meta["frontier_tiebreak_selected_group"] = ""
        return None, meta

    meta["frontier_tiebreak_triggered"] = True
    meta["frontier_tiebreak_selected_group"] = str(chosen)
    meta["frontier_tiebreak_reason"] = "prefer_frontier_mass_then_lower_direct_mass"
    return str(chosen), meta


def clean_answer_text_for_tiebreak(answer: Any) -> str:
    return str(answer or "").strip()


def is_runtime_answer_text_valid(answer: str | None, *, question: str = "") -> bool:
    """Gold-free validity check for tie-break ranking (not evaluation correctness)."""
    text = clean_answer_text_for_tiebreak(answer)
    if not text:
        return False
    lowered = text.lower()
    if lowered in {"__unknown__", "unknown", "none", "null"}:
        return False
    if "Answer with a single letter" in (question or ""):
        return bool(LETTER_RE.match(text)) or lowered == "none"
    nums = re.findall(r"[-+]?\d+(?:\.\d+)?", text.replace(",", ""))
    if nums:
        return True
    if lowered in {"0", "1"}:
        return False
    return True


def _group_branch_diversity(
    group_key: str,
    *,
    strategy_family_counts: dict[str, Any] | None,
    selector_candidate_pool: list[dict[str, Any]] | None,
    frontier_final_states: list[dict[str, Any]] | None,
) -> int:
    if isinstance(strategy_family_counts, dict):
        fam = strategy_family_counts.get(group_key)
        if isinstance(fam, dict) and fam:
            return len(fam)
    sources: set[str] = set()
    for collection in (selector_candidate_pool, frontier_final_states):
        if not isinstance(collection, list):
            continue
        for row in collection:
            if not isinstance(row, dict):
                continue
            pred = str(row.get("predicted_answer") or "").strip()
            norm = str(row.get("normalized_answer") or row.get("answer_group") or "").strip()
            group = norm or (normalize_answer_group_key(pred) if pred else "")
            if group != group_key:
                continue
            sid = str(
                row.get("branch_id")
                or row.get("candidate_id")
                or row.get("source")
                or row.get("source_id")
                or row.get("strategy_family")
                or row.get("source_family")
                or ""
            ).strip()
            if sid:
                sources.add(sid)
    return len(sources)


def resolve_conservative_answer_group_tiebreak(
    merged_support: dict[str, int],
    *,
    previous_group_key: str,
    previous_answer: str | None,
    direct_answers: list[str | None] | None = None,
    incumbent_answer: str | None = None,
    frontier_answer: str | None = None,
    strategy_family_counts: dict[str, Any] | None = None,
    selector_candidate_pool: list[dict[str, Any]] | None = None,
    frontier_final_states: list[dict[str, Any]] | None = None,
    question: str = "",
    near_tie_gap_threshold: int = NEAR_TIE_SUPPORT_GAP_THRESHOLD,
) -> tuple[str | None, dict[str, Any]]:
    """Conservative gated tie-break among tied/near-tied answer groups (gold-free)."""
    prev_g = str(previous_group_key).strip() or "__unknown__"
    meta: dict[str, Any] = {
        "frontier_max_support_tiebreak_applied": False,
        "frontier_max_support_tiebreak_reason": "not_evaluated",
        "frontier_max_support_tiebreak_candidate_count": 0,
        "frontier_max_support_tiebreak_support_gap": None,
    }
    if not isinstance(merged_support, dict) or not merged_support:
        meta["frontier_max_support_tiebreak_reason"] = "empty_support_histogram"
        return None, meta

    normalized_counts: dict[str, int] = {}
    for key, val in merged_support.items():
        ks = str(key).strip()
        if not ks or ks == "__unknown__":
            continue
        try:
            normalized_counts[ks] = int(val)
        except Exception:
            continue
    if not normalized_counts:
        meta["frontier_max_support_tiebreak_reason"] = "no_normalizable_groups"
        return None, meta

    sorted_groups = sorted(normalized_counts.items(), key=lambda kv: (-kv[1], kv[0]))
    top_support = int(sorted_groups[0][1])
    second_support = int(sorted_groups[1][1]) if len(sorted_groups) > 1 else 0
    support_gap = int(top_support - second_support) if len(sorted_groups) > 1 else None
    meta["frontier_max_support_tiebreak_candidate_count"] = len(sorted_groups)
    meta["frontier_max_support_tiebreak_support_gap"] = support_gap

    selected_support = int(normalized_counts.get(prev_g, 0))
    other_supports = [
        int(s) for g, s in normalized_counts.items() if g not in {"", "__unknown__"} and g != prev_g
    ]
    if not other_supports:
        meta["frontier_max_support_tiebreak_reason"] = "single_answer_group"
        return None, meta

    gap_threshold = max(0, int(near_tie_gap_threshold))
    max_other = max(other_supports)
    if selected_support > max_other + gap_threshold:
        meta["frontier_max_support_tiebreak_reason"] = "clear_support_winner"
        return None, meta

    contenders = [
        g
        for g, s in normalized_counts.items()
        if g not in {"", "__unknown__"} and abs(int(s) - selected_support) <= gap_threshold
    ]
    if len(contenders) < 2:
        meta["frontier_max_support_tiebreak_reason"] = "insufficient_contenders"
        return None, meta

    prev_valid = is_runtime_answer_text_valid(previous_answer, question=question)
    if not prev_valid:
        top_contenders = [g for g, s in normalized_counts.items() if int(s) == top_support]
        if len(top_contenders) >= 2:
            contenders = top_contenders

    def representative_for(group: str) -> str | None:
        return pick_answer_text_for_normalized_group(
            group,
            direct_answers=list(direct_answers or []),
            incumbent_answer=incumbent_answer,
            frontier_answer=frontier_answer,
            frontier_metadata={"final_branch_states": list(frontier_final_states or [])},
            selector_candidate_pool=list(selector_candidate_pool or []),
        )

    def rank_key(group: str) -> tuple[int, int, int, int, int, str]:
        rep = representative_for(group)
        support = int(normalized_counts.get(group, 0))
        valid = 1 if is_runtime_answer_text_valid(rep, question=question) else 0
        diversity = _group_branch_diversity(
            group,
            strategy_family_counts=strategy_family_counts,
            selector_candidate_pool=selector_candidate_pool,
            frontier_final_states=frontier_final_states,
        )
        clean_len = len(clean_answer_text_for_tiebreak(rep)) if rep else 9999
        incumbent_bonus = 1 if group == prev_g else 0
        return (valid, support, diversity, -clean_len, incumbent_bonus, group)

    ranked = sorted(contenders, key=rank_key, reverse=True)
    chosen_g = ranked[0]
    if str(chosen_g) == str(prev_g):
        meta["frontier_max_support_tiebreak_reason"] = "tiebreak_keeps_incumbent"
        return None, meta

    meta["frontier_max_support_tiebreak_applied"] = True
    meta["frontier_max_support_tiebreak_reason"] = "conservative_secondary_criteria"
    return str(chosen_g), meta


def apply_gated_conservative_answer_group_tiebreak(
    final_answer: str | None,
    *,
    enabled: bool,
    answer_group_support_counts: dict[str, Any],
    direct_trace: list[dict[str, Any]] | None,
    direct_answers: list[str | None] | None,
    incumbent_answer: str | None,
    frontier_answer: str | None,
    frontier_meta: dict[str, Any] | None,
    question: str = "",
) -> tuple[str | None, dict[str, Any]]:
    """Apply gated conservative tie-break; returns (answer, metadata)."""
    before = final_answer
    before_s = str(before or "")
    frontier_meta = dict(frontier_meta or {})
    tiebreak_meta: dict[str, Any] = {
        "frontier_max_support_tiebreak_enabled": bool(enabled),
        "frontier_max_support_tiebreak_applied": False,
        "frontier_max_support_tiebreak_reason": "disabled" if not enabled else "not_evaluated",
        "frontier_max_support_tiebreak_before_answer": before_s,
        "frontier_max_support_tiebreak_after_answer": before_s,
        "frontier_max_support_tiebreak_candidate_count": 0,
        "frontier_max_support_tiebreak_support_gap": None,
        "frontier_tiebreak_enabled": bool(enabled),
        "frontier_tiebreak_triggered": False,
        "frontier_tiebreak_selected_group": "",
        "frontier_tiebreak_previous_group": "",
        "frontier_tiebreak_reason": "disabled" if not enabled else "not_evaluated",
    }
    if not enabled:
        return final_answer, tiebreak_meta

    prev_g = normalize_answer_group_key(before) or "__unknown__"
    tiebreak_meta["frontier_tiebreak_previous_group"] = prev_g
    merged_hist = build_merged_support_histogram_for_tiebreak(
        dict(answer_group_support_counts) if isinstance(answer_group_support_counts, dict) else {},
        final_answer=before,
        direct_trace=list(direct_trace or []),
    )
    strategy_families = frontier_meta.get("answer_group_strategy_family_counts")
    final_states = frontier_meta.get("final_branch_states")
    chosen_g, inner = resolve_conservative_answer_group_tiebreak(
        merged_hist,
        previous_group_key=prev_g,
        previous_answer=before,
        direct_answers=list(direct_answers or []),
        incumbent_answer=incumbent_answer,
        frontier_answer=frontier_answer,
        strategy_family_counts=strategy_families if isinstance(strategy_families, dict) else None,
        selector_candidate_pool=None,
        frontier_final_states=final_states if isinstance(final_states, list) else None,
        question=question,
    )
    tiebreak_meta.update(inner)
    tiebreak_meta["frontier_max_support_tiebreak_before_answer"] = before_s

    if chosen_g is None:
        tiebreak_meta["frontier_max_support_tiebreak_after_answer"] = before_s
        tiebreak_meta["frontier_tiebreak_reason"] = str(
            tiebreak_meta.get("frontier_max_support_tiebreak_reason") or "no_change"
        )
        return final_answer, tiebreak_meta

    picked = pick_answer_text_for_normalized_group(
        chosen_g,
        direct_answers=list(direct_answers or []),
        incumbent_answer=incumbent_answer,
        frontier_answer=frontier_answer,
        frontier_metadata=frontier_meta,
        selector_candidate_pool=None,
    )
    if picked is None:
        tiebreak_meta["frontier_max_support_tiebreak_applied"] = False
        tiebreak_meta["frontier_tiebreak_triggered"] = False
        tiebreak_meta["frontier_tiebreak_selected_group"] = ""
        tiebreak_meta["frontier_max_support_tiebreak_after_answer"] = before_s
        tiebreak_meta["frontier_max_support_tiebreak_reason"] = (
            str(tiebreak_meta.get("frontier_max_support_tiebreak_reason") or "tiebreak") + "_answer_lookup_failed"
        )
        tiebreak_meta["frontier_tiebreak_reason"] = tiebreak_meta["frontier_max_support_tiebreak_reason"]
        return final_answer, tiebreak_meta

    tiebreak_meta["frontier_max_support_tiebreak_applied"] = True
    tiebreak_meta["frontier_max_support_tiebreak_after_answer"] = str(picked)
    tiebreak_meta["frontier_tiebreak_triggered"] = True
    tiebreak_meta["frontier_tiebreak_selected_group"] = str(chosen_g)
    tiebreak_meta["frontier_tiebreak_reason"] = str(
        tiebreak_meta.get("frontier_max_support_tiebreak_reason") or "conservative_secondary_criteria"
    )
    return str(picked).strip(), tiebreak_meta


def simulate_tiebreak_adjusted_prediction_from_metadata(
    metadata: dict[str, Any],
    *,
    question: str = "",
) -> tuple[str | None, dict[str, Any]]:
    """Offline-only: re-evaluate gated conservative tiebreak from saved metadata (no gold)."""
    md = dict(metadata or {})
    ag = md.get("answer_group_support_counts") or {}
    direct_trace = list(md.get("direct_reserve_attempts") or [])
    final_s = md.get("final_answer")
    if final_s is not None:
        final_s = str(final_s).strip() or None
    if not isinstance(ag, dict) or not ag:
        return final_s, {
            "frontier_max_support_tiebreak_enabled": True,
            "frontier_max_support_tiebreak_applied": False,
            "frontier_max_support_tiebreak_reason": "missing_answer_group_support_counts",
        }

    frontier_meta = dict(md.get("frontier_candidate_metadata") or md.get("frontier_metadata") or {})
    if not frontier_meta.get("final_branch_states") and isinstance(md.get("final_branch_states"), list):
        frontier_meta["final_branch_states"] = list(md.get("final_branch_states") or [])
    if not frontier_meta.get("answer_group_strategy_family_counts"):
        frontier_meta["answer_group_strategy_family_counts"] = dict(
            md.get("answer_group_strategy_family_counts") or {}
        )

    adjusted, t_meta = apply_gated_conservative_answer_group_tiebreak(
        final_s,
        enabled=True,
        answer_group_support_counts=dict(ag),
        direct_trace=direct_trace,
        direct_answers=[],
        incumbent_answer=md.get("direct_reserve_answer"),
        frontier_answer=md.get("frontier_candidate_answer"),
        frontier_meta=frontier_meta,
        question=question,
    )
    return adjusted, t_meta


def pick_answer_text_for_normalized_group(
    group_key: str,
    *,
    direct_answers: list[str | None],
    incumbent_answer: str | None,
    frontier_answer: str | None,
    frontier_metadata: dict[str, Any] | None,
    selector_candidate_pool: list[dict[str, Any]] | None,
) -> str | None:
    """Map a normalized group key to a concrete answer string (gold-free)."""
    g = str(group_key).strip()
    if not g or g == "__unknown__":
        return None

    def _matches(val: str | None) -> bool:
        if val is None:
            return False
        return normalize_answer_group_key(str(val)) == g

    if _matches(frontier_answer):
        return str(frontier_answer).strip() if frontier_answer is not None else None
    if _matches(incumbent_answer):
        return str(incumbent_answer).strip() if incumbent_answer is not None else None
    for a in direct_answers:
        if _matches(a):
            return None if a is None else str(a).strip()

    if isinstance(selector_candidate_pool, list):
        for row in selector_candidate_pool:
            if not isinstance(row, dict):
                continue
            pa = row.get("predicted_answer")
            na = row.get("normalized_answer")
            if _matches(str(pa) if pa is not None else None) or _matches(str(na) if na is not None else None):
                if pa is not None and str(pa).strip():
                    return str(pa).strip()
                if na is not None and str(na).strip():
                    return str(na).strip()

    fm = frontier_metadata or {}
    for s in fm.get("final_branch_states") or []:
        if not isinstance(s, dict):
            continue
        pa = s.get("predicted_answer")
        if _matches(str(pa) if pa is not None else None) and pa is not None and str(pa).strip():
            return str(pa).strip()
    for ev in fm.get("action_trace") or []:
        if not isinstance(ev, dict):
            continue
        if str(ev.get("action") or "").strip().lower() != "expand":
            continue
        ea = ev.get("extracted_answer")
        if ea is not None and str(ea).strip() and _matches(str(ea)):
            return str(ea).strip()
    return None
