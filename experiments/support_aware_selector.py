"""Offline support-aware / tie-aware selector variant for direct_reserve_semantic_frontier_v2.

FIX-1: When the selector ties (support_margin == 0, confidence_proxy <= 0.5)
and the frontier found a parseable candidate, prefer the frontier candidate.

This is an offline counterfactual evaluator only — it uses already-generated
result_metadata to apply a different selection rule without new API calls.

Gold-free: does not use gold_answer or exact_match as a feature.
Policy is frozen and labeled as a separate variant.
"""

from __future__ import annotations

import re
from typing import Any

# ─── Answer normalization (gold-free) ─────────────────────────────────────────

def _normalize_answer(answer: Any) -> str | None:
    """Normalize a raw answer string to a canonical group key."""
    s = str(answer or "").strip()
    if not s or s in {"None", "none", "__unknown__", ""}:
        return None
    s = re.sub(r"[\$,]", "", s)
    s = re.sub(r"\\boxed\{([^}]+)\}", r"\1", s)
    s = s.strip()
    # try numeric parse
    try:
        v = float(s)
        if v == int(v):
            return str(int(v))
        return f"{v:.4f}".rstrip("0").rstrip(".")
    except (ValueError, OverflowError):
        pass
    return s.lower()


def _is_parseable(answer: Any) -> bool:
    g = _normalize_answer(answer)
    return bool(g and g != "__unknown__")


# ─── FIX-1 core decision rule ─────────────────────────────────────────────────

POLICY_NAME = "direct_reserve_semantic_frontier_v2_support_aware_v1"
POLICY_VERSION = "1.0"
POLICY_DESCRIPTION = (
    "Offline support-aware selector (FIX-1): "
    "when support_margin == 0 and direct_reserve_confidence_proxy <= 0.5 "
    "and frontier_candidate_answer is parseable and different from incumbent, "
    "prefer frontier_candidate_answer."
)


def should_apply_support_aware_fix(
    *,
    support_margin: float | None,
    direct_reserve_confidence_proxy: float | None,
    frontier_candidate_answer: str | None,
    incumbent_answer: str | None,
) -> bool:
    """Return True if FIX-1 should override incumbent with frontier candidate.

    Decision is purely gold-free: no correctness labels or gold answers used.
    """
    if support_margin is None or direct_reserve_confidence_proxy is None:
        return False
    # Tie condition: exactly zero support margin and confidence at or below 0.5.
    # Negative margin means incumbent has more support — keep incumbent.
    # Positive margin means frontier already has more support — existing code handles it.
    if float(support_margin) != 0.0:
        return False
    if float(direct_reserve_confidence_proxy) > 0.5:
        return False
    # Frontier candidate must be parseable
    if not _is_parseable(frontier_candidate_answer):
        return False
    # Must differ from incumbent to avoid no-op switches
    inc_g = _normalize_answer(incumbent_answer)
    frc_g = _normalize_answer(frontier_candidate_answer)
    if inc_g and frc_g and inc_g == frc_g:
        return False
    return True


def apply_support_aware_fix(
    *,
    result_metadata: dict[str, Any],
    current_final_answer: str | None,
) -> tuple[str | None, dict[str, Any]]:
    """Apply FIX-1 to a single frontier row.

    Returns (new_answer, fix_metadata). If fix not triggered, new_answer
    equals current_final_answer and fix_metadata explains why.

    Args:
        result_metadata: the ``result_metadata`` dict from a per-example record.
        current_final_answer: the original selected answer (incumbent).

    Returns:
        (selected_answer, fix_meta) where fix_meta contains:
          - fix_applied: bool
          - fix_reason: str
          - original_answer: str|None
          - support_margin: float|None
          - confidence_proxy: float|None
          - frontier_candidate: str|None
    """
    if not isinstance(result_metadata, dict):
        return current_final_answer, {
            "fix_applied": False,
            "fix_reason": "no_result_metadata",
            "original_answer": current_final_answer,
        }

    sm = result_metadata.get("support_margin")
    cp = result_metadata.get("direct_reserve_confidence_proxy")
    fc = result_metadata.get("frontier_candidate_answer")

    try:
        sm = float(sm) if sm is not None else None
    except (TypeError, ValueError):
        sm = None
    try:
        cp = float(cp) if cp is not None else None
    except (TypeError, ValueError):
        cp = None

    fix_meta: dict[str, Any] = {
        "fix_applied": False,
        "fix_reason": "not_triggered",
        "original_answer": current_final_answer,
        "support_margin": sm,
        "confidence_proxy": cp,
        "frontier_candidate": str(fc) if fc is not None else None,
        "policy": POLICY_NAME,
        "policy_version": POLICY_VERSION,
    }

    triggered = should_apply_support_aware_fix(
        support_margin=sm,
        direct_reserve_confidence_proxy=cp,
        frontier_candidate_answer=fc,
        incumbent_answer=current_final_answer,
    )

    if triggered:
        fix_meta["fix_applied"] = True
        fix_meta["fix_reason"] = "tie_support_frontier_preferred"
        fix_meta["chosen_answer"] = str(fc)
        return str(fc), fix_meta

    # Document why not triggered
    if sm is None or cp is None:
        fix_meta["fix_reason"] = "missing_metadata"
    elif float(sm) > 0:
        fix_meta["fix_reason"] = "incumbent_has_majority_support"
    elif float(cp) > 0.5:
        fix_meta["fix_reason"] = "incumbent_has_high_confidence"
    elif not _is_parseable(fc):
        fix_meta["fix_reason"] = "frontier_candidate_not_parseable"
    else:
        fix_meta["fix_reason"] = "frontier_agrees_with_incumbent"

    return current_final_answer, fix_meta


def apply_support_aware_fix_to_row(row: dict[str, Any]) -> dict[str, Any]:
    """Apply FIX-1 to a complete per-example record dict.

    Only applies to direct_reserve_semantic_frontier_v2 rows.
    Returns a copy of the row with fix1_* fields added.
    """
    out = dict(row)
    method = str(row.get("method", ""))
    if "direct_reserve_semantic_frontier_v2" not in method:
        out["fix1_applied"] = False
        out["fix1_reason"] = "not_frontier_method"
        out["fix1_answer_canonical"] = row.get("final_answer_canonical")
        out["fix1_answer_raw"] = row.get("final_answer_raw")
        return out

    rm = row.get("result_metadata")
    if isinstance(rm, str):
        import json as _json
        try:
            rm = _json.loads(rm)
        except Exception:
            rm = {}

    current = row.get("final_answer_canonical") or row.get("selected_answer_canonical")
    new_answer, fix_meta = apply_support_aware_fix(
        result_metadata=rm or {},
        current_final_answer=current,
    )

    out["fix1_applied"] = fix_meta.get("fix_applied", False)
    out["fix1_reason"] = fix_meta.get("fix_reason", "unknown")
    out["fix1_answer_canonical"] = _normalize_answer(new_answer)
    out["fix1_answer_raw"] = new_answer
    out["fix1_support_margin"] = fix_meta.get("support_margin")
    out["fix1_confidence_proxy"] = fix_meta.get("confidence_proxy")
    out["fix1_frontier_candidate"] = fix_meta.get("frontier_candidate")
    out["fix1_original_answer"] = current
    return out
