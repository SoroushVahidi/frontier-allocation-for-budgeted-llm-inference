"""Gold-free max-support tiebreak using frontier vs direct answer-group mass (diagnostic helpers)."""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

from experiments.data import extract_final_answer


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


def simulate_tiebreak_adjusted_prediction_from_metadata(
    metadata: dict[str, Any],
) -> tuple[str | None, dict[str, Any]]:
    """Offline-only: re-evaluate tiebreak using fields saved in ``result_metadata`` (no gold)."""
    md = dict(metadata or {})
    ag = md.get("answer_group_support_counts") or {}
    direct_trace = list(md.get("direct_reserve_attempts") or [])
    final_s = md.get("final_answer")
    if final_s is not None:
        final_s = str(final_s).strip() or None
    merged_hist = build_merged_support_histogram_for_tiebreak(
        dict(ag) if isinstance(ag, dict) else {},
        final_answer=final_s,
        direct_trace=direct_trace,
    )
    prev_g = normalize_answer_group_key(final_s) if final_s else ""
    if not prev_g:
        prev_g = "__unknown__"
    chosen_g, t_inner = resolve_frontier_bias_max_support_tiebreak(
        merged_hist,
        dict(md.get("frontier_answer_group_counts") or {}),
        dict(md.get("direct_answer_group_counts") or {}),
        previous_group_key=str(prev_g),
    )
    out_meta = {
        "frontier_tiebreak_enabled": True,
        **t_inner,
    }
    if chosen_g is None:
        return final_s, out_meta
    picked = pick_answer_text_for_normalized_group(
        chosen_g,
        direct_answers=[],
        incumbent_answer=md.get("direct_reserve_answer"),
        frontier_answer=md.get("frontier_candidate_answer"),
        frontier_metadata=dict(md.get("frontier_candidate_metadata") or md.get("frontier_metadata") or {}),
        selector_candidate_pool=list(md.get("selector_candidate_pool") or []),
    )
    if picked is None:
        out_meta["frontier_tiebreak_triggered"] = False
        out_meta["frontier_tiebreak_selected_group"] = ""
        out_meta["frontier_tiebreak_reason"] = str(out_meta.get("frontier_tiebreak_reason") or "") + "_answer_lookup_failed"
        return final_s, out_meta
    return picked, out_meta


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
