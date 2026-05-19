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


# ─── FIX-2: Low-depth / single-weak-frontier-branch guard ────────────────────

FIX2_POLICY_NAME = "direct_reserve_semantic_frontier_v2_low_depth_guard_v1"
FIX2_POLICY_VERSION = "1.0"
FIX2_POLICY_DESCRIPTION = (
    "Offline low-depth guard (FIX-2): "
    "when override_reason == 'single_weak_frontier_branch' (or frontier_support==0 with scattered pool), "
    "prefer the majority external-baseline answer over the weak frontier output."
)

COMBINED_POLICY_NAME = "direct_reserve_semantic_frontier_v2_support_aware_low_depth_guard_v1"
COMBINED_POLICY_VERSION = "1.0"
COMBINED_POLICY_DESCRIPTION = (
    "Combined FIX-1 + FIX-2: "
    "FIX-1 (tie/PNS fix) takes precedence; if not triggered, FIX-2 (low-depth fallback) applies."
)


def is_low_depth_risk(result_metadata: dict[str, Any]) -> bool:
    """Return True if frontier shows weak exploration signature (FIX-2 trigger).

    Gold-free: uses only override_reason and support counts from result_metadata.
    """
    if not isinstance(result_metadata, dict):
        return False
    override = str(result_metadata.get("override_reason", "") or "")
    if "single_weak_frontier_branch" in override:
        return True
    # Fallback: frontier_support == 0 with multiple competing candidate groups
    fr_sup = result_metadata.get("frontier_support")
    cpc = result_metadata.get("candidate_pool_answer_group_count")
    if fr_sup is not None and cpc is not None:
        try:
            if int(fr_sup) == 0 and int(cpc) >= 2:
                return True
        except (TypeError, ValueError):
            pass
    return False


def select_external_majority(
    external_answers: dict[str, Any],
) -> tuple[str | None, dict[str, Any]]:
    """Choose the answer most commonly agreed on by external baselines.

    Args:
        external_answers: mapping method_name → answer_canonical (raw string)

    Returns:
        (selected_answer_canonical, selection_meta)
    """
    from collections import Counter

    valid: dict[str, str] = {}
    for k, v in external_answers.items():
        norm = _normalize_answer(v)
        if norm:
            valid[k] = norm

    if not valid:
        return None, {"reason": "no_parseable_external_answer", "candidates": {}}

    counts = Counter(valid.values())
    most_common_ans, count = counts.most_common(1)[0]

    if count >= 2:
        chosen_method = next(k for k, v in valid.items() if v == most_common_ans)
        return most_common_ans, {
            "reason": "external_majority_vote",
            "vote_count": count,
            "total_baselines": len(valid),
            "chosen_method": chosen_method,
            "all_answers": dict(valid),
        }

    # No majority — use fixed priority order (best baseline first)
    for preferred in (
        "external_tale_prompt_budgeting",
        "external_s1_budget_forcing",
        "external_l1_max",
    ):
        if preferred in valid:
            return valid[preferred], {
                "reason": "external_no_majority_priority_fallback",
                "priority_method": preferred,
                "all_answers": dict(valid),
            }

    first_method, first_ans = next(iter(valid.items()))
    return first_ans, {"reason": "external_fallback_first", "method": first_method}


def apply_fix2_to_row(
    row: dict[str, Any],
    external_answers: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply FIX-2 low-depth guard to a single frontier row.

    Args:
        row: per-example record dict (direct_reserve_semantic_frontier_v2).
        external_answers: method_name → final_answer_canonical for the same example_id.
                          Pass None if not available (fix2 will not switch but will flag).

    Returns:
        Copy of row with fix2_* fields added.
    """
    out = dict(row)
    method = str(row.get("method", ""))

    if "direct_reserve_semantic_frontier_v2" not in method:
        out["fix2_applied"] = False
        out["fix2_reason"] = "not_frontier_method"
        out["fix2_is_low_depth"] = False
        out["fix2_answer_canonical"] = row.get("final_answer_canonical")
        out["fix2_answer_raw"] = row.get("final_answer_raw")
        return out

    rm = row.get("result_metadata")
    if isinstance(rm, str):
        import json as _json
        try:
            rm = _json.loads(rm)
        except Exception:
            rm = {}

    is_ld = is_low_depth_risk(rm or {})
    override_reason_val = str((rm or {}).get("override_reason", "") or "")
    current = row.get("final_answer_canonical") or row.get("selected_answer_canonical")

    out["fix2_is_low_depth"] = is_ld
    out["fix2_original_answer"] = current
    out["fix2_override_reason"] = override_reason_val

    if not is_ld:
        out["fix2_applied"] = False
        out["fix2_reason"] = "not_triggered"
        out["fix2_answer_canonical"] = current
        out["fix2_answer_raw"] = current
        return out

    # FIX-2 triggered — attempt external majority fallback
    if external_answers:
        ext_ans, ext_meta = select_external_majority(external_answers)
    else:
        ext_ans, ext_meta = None, {"reason": "no_external_answers_available"}

    out["fix2_external_selection"] = ext_meta

    if ext_ans and ext_ans != _normalize_answer(current):
        out["fix2_applied"] = True
        out["fix2_reason"] = "low_depth_external_fallback"
        out["fix2_answer_canonical"] = ext_ans
        out["fix2_answer_raw"] = ext_ans
    else:
        out["fix2_applied"] = False
        out["fix2_reason"] = (
            "low_depth_but_no_better_external"
            if ext_ans
            else "low_depth_no_external_available"
        )
        out["fix2_answer_canonical"] = current
        out["fix2_answer_raw"] = current

    return out


def apply_combined_fix_to_row(
    row: dict[str, Any],
    external_answers: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply FIX-1 then FIX-2 with FIX-1 taking precedence.

    FIX-1 handles tie/PNS using the frontier candidate.
    FIX-2 handles weak-exploration using the external majority.
    Only one fix fires per row; FIX-1 takes priority.

    Args:
        row: per-example record dict.
        external_answers: method_name → final_answer_canonical for same example_id.

    Returns:
        Copy of row with fix1_*, fix2_*, and combined_* fields added.
    """
    # Step 1: apply FIX-1
    out = apply_support_aware_fix_to_row(row)

    if out.get("fix1_applied"):
        # FIX-1 fired — skip FIX-2
        out["fix2_applied"] = False
        out["fix2_reason"] = "fix1_already_applied"
        out["fix2_is_low_depth"] = False
        out["fix2_answer_canonical"] = out.get("fix1_answer_canonical")
        out["fix2_answer_raw"] = out.get("fix1_answer_raw")
        out["combined_answer_canonical"] = out.get("fix1_answer_canonical")
        out["combined_answer_raw"] = out.get("fix1_answer_raw")
        out["combined_policy_applied"] = "fix1"
        out["combined_policy"] = COMBINED_POLICY_NAME
        return out

    # Step 2: FIX-1 didn't fire — try FIX-2
    fix2_out = apply_fix2_to_row(out, external_answers=external_answers)
    for k, v in fix2_out.items():
        if k.startswith("fix2_") or k not in out:
            out[k] = v

    if fix2_out.get("fix2_applied"):
        out["combined_answer_canonical"] = fix2_out.get("fix2_answer_canonical")
        out["combined_answer_raw"] = fix2_out.get("fix2_answer_raw")
        out["combined_policy_applied"] = "fix2"
    else:
        out["combined_answer_canonical"] = _normalize_answer(
            row.get("final_answer_canonical") or row.get("selected_answer_canonical")
        )
        out["combined_answer_raw"] = row.get("final_answer_raw")
        out["combined_policy_applied"] = "original"

    out["combined_policy"] = COMBINED_POLICY_NAME
    return out
