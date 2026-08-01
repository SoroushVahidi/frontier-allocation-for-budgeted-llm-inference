"""Gold-free selection helpers for direct+frontier hybrid seed overlay (no API)."""

from __future__ import annotations

from typing import Any

from experiments.frontier_max_support_tiebreak import normalize_answer_group_key


def _filtered_frontier_counts(fc: dict[str, Any]) -> dict[str, int]:
    """Drop obvious evaluation/oracle keys so hybrid logic cannot key off gold artifacts."""
    out: dict[str, int] = {}
    if not isinstance(fc, dict):
        return out
    for k, v in fc.items():
        ks = str(k).strip()
        if not ks or ks == "__unknown__":
            continue
        low = ks.lower()
        if "gold" in low or "oracle" in low:
            continue
        try:
            out[ks] = int(v)
        except Exception:
            continue
    return out


def frontier_has_useful_answer_group_evidence(
    *,
    frontier_override_triggered: bool,
    tiebreak_triggered: bool,
    frontier_support_counts: dict[str, Any],
) -> bool:
    """True when frontier/tiebreak signals justify keeping the baseline commitment."""
    if frontier_override_triggered or tiebreak_triggered:
        return True
    fc = _filtered_frontier_counts(frontier_support_counts)
    if not fc:
        return False
    positives = [k for k, v in fc.items() if int(v or 0) > 0]
    if len(positives) >= 2:
        return True
    try:
        mx = max(int(v) for v in fc.values())
    except ValueError:
        mx = 0
    return mx >= 2


def resolve_direct_hybrid_seed_overlay(
    *,
    baseline_final_answer: str | None,
    hybrid_seed_answer: str | None,
    frontier_override_triggered: bool,
    tiebreak_triggered: bool,
    frontier_support_counts: dict[str, Any],
) -> tuple[str | None, dict[str, Any]]:
    """Prefer baseline when frontier evidence is useful; else allow hybrid seed if it disagrees."""
    meta: dict[str, Any] = {
        "direct_hybrid_overlay_applied": False,
        "direct_hybrid_overlay_reason": "disabled_or_no_seed",
        "direct_hybrid_overlay_previous_answer": baseline_final_answer,
    }
    seed_s = str(hybrid_seed_answer or "").strip()
    if not seed_s:
        meta["direct_hybrid_overlay_reason"] = "empty_seed"
        return baseline_final_answer, meta

    strong = frontier_has_useful_answer_group_evidence(
        frontier_override_triggered=bool(frontier_override_triggered),
        tiebreak_triggered=bool(tiebreak_triggered),
        frontier_support_counts=frontier_support_counts,
    )
    if strong:
        meta["direct_hybrid_overlay_reason"] = "keep_baseline_strong_frontier_or_tiebreak"
        return baseline_final_answer, meta

    seed_g = normalize_answer_group_key(seed_s)
    base_g = normalize_answer_group_key(str(baseline_final_answer or "").strip())
    if seed_g and base_g and seed_g == base_g:
        meta["direct_hybrid_overlay_reason"] = "seed_matches_baseline_group"
        return baseline_final_answer, meta

    meta["direct_hybrid_overlay_applied"] = True
    meta["direct_hybrid_overlay_reason"] = "weak_frontier_use_hybrid_seed"
    meta["direct_hybrid_overlay_chosen_answer"] = seed_s
    return seed_s, meta


def gold_like_histogram_keys_present(*, frontier_support_counts: dict[str, Any]) -> bool:
    """Test helper: detect suspicious evaluation keys without using values for decisions."""
    if not isinstance(frontier_support_counts, dict):
        return False
    return any("gold" in str(k).lower() or "oracle" in str(k).lower() for k in frontier_support_counts.keys())
