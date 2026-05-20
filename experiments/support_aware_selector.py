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


# ─── FIX-3: Within-method verifier calibration guard ─────────────────────────
#
# Empirical note (from offline analysis, 2026-05-19):
# The available within-method verifier signal is answer_group_best_branch_scores
# from result_metadata. On both the diagnostic and promotion-grade sets, AGBS
# scores cluster at 0.8 (minimum) for ~85% of cases, with higher scores
# occurring primarily in single_weak_frontier_branch rows (handled by FIX-2).
# AGBS is counterintuitively anti-correlated with correctness when considered
# naively: low score (=0.8) → 84.6% correct; high score (>0.81) → 68.8% correct.
# This is because high-AGBS rows are dominated by SWFB cases, which FIX-2 handles.
# Within-method cross-case percentile ranking of AGBS does not provide additional
# discriminative signal beyond override_reason.
#
# FIX-3 therefore uses the only remaining actionable signal: verifier score
# absence (empty AGBS) in non-SWFB cases, which occurs for
# frontier_not_run_or_budget_exhausted rows. These cases have 33% accuracy
# (diagnostic) vs 73% overall; external majority fallback is a safe improvement.

FIX3_POLICY_NAME = "direct_reserve_semantic_frontier_v2_within_method_calibrated_v1"
FIX3_POLICY_VERSION = "1.0"
FIX3_POLICY_DESCRIPTION = (
    "Within-method verifier calibration guard (FIX-3): "
    "when override_reason == 'frontier_not_run_or_budget_exhausted' "
    "or verifier scores are absent for a non-SWFB row, "
    "prefer the external majority as the frontier had no usable calibrated score. "
    "Note: AGBS scores (0.8–0.975) are not discriminative beyond override_reason; "
    "see code comment for empirical details."
)

COMBINED_FIX123_POLICY_NAME = "direct_reserve_semantic_frontier_v2_support_lowdepth_calibrated_v1"
COMBINED_FIX123_POLICY_VERSION = "1.0"
COMBINED_FIX123_POLICY_DESCRIPTION = (
    "Combined FIX-1 + FIX-2 + FIX-3: "
    "FIX-1 (tie/PNS fix) → FIX-2 (low-depth fallback) → FIX-3 (verifier-absent fallback). "
    "Applied in precedence order; only one fix fires per row."
)


def get_agbs_best_score(result_metadata: dict[str, Any]) -> float | None:
    """Return the best branch verifier score across all answer groups, or None if absent."""
    if not isinstance(result_metadata, dict):
        return None
    agbs = result_metadata.get("answer_group_best_branch_scores") or {}
    if not agbs:
        return None
    try:
        return max(float(v) for v in agbs.values())
    except (TypeError, ValueError):
        return None


def is_verifier_score_absent_risk(result_metadata: dict[str, Any]) -> bool:
    """Return True if frontier verifier scores are absent in a non-SWFB context (FIX-3 trigger).

    FIX-2 already handles single_weak_frontier_branch. FIX-3 catches the
    remaining no-score cases: frontier_not_run_or_budget_exhausted and
    any other override where AGBS is empty.

    Gold-free: uses only override_reason and answer_group_best_branch_scores.
    """
    if not isinstance(result_metadata, dict):
        return False
    override = str(result_metadata.get("override_reason", "") or "")
    # FIX-2 handles SWFB; don't double-trigger
    if "single_weak_frontier_branch" in override:
        return False
    # Explicit budget-exhausted case
    if "frontier_not_run_or_budget_exhausted" in override:
        return True
    # Any other case where verifier scores are absent
    agbs_best = get_agbs_best_score(result_metadata)
    if agbs_best is None:
        return True
    return False


def apply_fix3_to_row(
    row: dict[str, Any],
    external_answers: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply FIX-3 verifier-calibration guard to a single frontier row.

    Args:
        row: per-example record dict (direct_reserve_semantic_frontier_v2).
        external_answers: method_name → final_answer_canonical for the same example_id.

    Returns:
        Copy of row with fix3_* fields added.
    """
    out = dict(row)
    method = str(row.get("method", ""))

    if "direct_reserve_semantic_frontier_v2" not in method:
        out["fix3_applied"] = False
        out["fix3_reason"] = "not_frontier_method"
        out["fix3_score_absent_risk"] = False
        out["fix3_answer_canonical"] = row.get("final_answer_canonical")
        out["fix3_answer_raw"] = row.get("final_answer_raw")
        return out

    rm = row.get("result_metadata")
    if isinstance(rm, str):
        import json as _json
        try:
            rm = _json.loads(rm)
        except Exception:
            rm = {}

    score_absent = is_verifier_score_absent_risk(rm or {})
    override_val = str((rm or {}).get("override_reason", "") or "")
    agbs_best = get_agbs_best_score(rm or {})
    current = row.get("final_answer_canonical") or row.get("selected_answer_canonical")

    out["fix3_score_absent_risk"] = score_absent
    out["fix3_original_answer"] = current
    out["fix3_override_reason"] = override_val
    out["fix3_agbs_best_score"] = agbs_best

    if not score_absent:
        out["fix3_applied"] = False
        out["fix3_reason"] = "not_triggered"
        out["fix3_answer_canonical"] = current
        out["fix3_answer_raw"] = current
        return out

    # FIX-3 triggered — attempt external majority fallback
    if external_answers:
        ext_ans, ext_meta = select_external_majority(external_answers)
    else:
        ext_ans, ext_meta = None, {"reason": "no_external_answers_available"}

    out["fix3_external_selection"] = ext_meta

    if ext_ans and ext_ans != _normalize_answer(current):
        out["fix3_applied"] = True
        out["fix3_reason"] = "verifier_score_absent_external_fallback"
        out["fix3_answer_canonical"] = ext_ans
        out["fix3_answer_raw"] = ext_ans
    else:
        out["fix3_applied"] = False
        out["fix3_reason"] = (
            "verifier_absent_but_no_better_external"
            if ext_ans
            else "verifier_absent_no_external_available"
        )
        out["fix3_answer_canonical"] = current
        out["fix3_answer_raw"] = current

    return out


def apply_combined_fix123_to_row(
    row: dict[str, Any],
    external_answers: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply FIX-1 → FIX-2 → FIX-3 in precedence order.

    Only one fix fires per row. FIX-1 takes top priority (frontier candidate),
    FIX-2 second (low-depth / SWFB), FIX-3 third (verifier score absent).

    Args:
        row: per-example record dict.
        external_answers: method_name → final_answer_canonical for same example_id.

    Returns:
        Copy of row with fix1_*, fix2_*, fix3_*, and combined123_* fields added.
    """
    # Step 1: apply FIX-1
    out = apply_support_aware_fix_to_row(row)

    if out.get("fix1_applied"):
        out["fix2_applied"] = False
        out["fix2_reason"] = "fix1_already_applied"
        out["fix2_is_low_depth"] = False
        out["fix3_applied"] = False
        out["fix3_reason"] = "fix1_already_applied"
        out["fix3_score_absent_risk"] = False
        out["combined123_answer_canonical"] = out.get("fix1_answer_canonical")
        out["combined123_answer_raw"] = out.get("fix1_answer_raw")
        out["combined123_policy_applied"] = "fix1"
        out["combined123_policy"] = COMBINED_FIX123_POLICY_NAME
        return out

    # Step 2: FIX-1 didn't fire — try FIX-2
    fix2_out = apply_fix2_to_row(out, external_answers=external_answers)
    for k, v in fix2_out.items():
        if k.startswith("fix2_") or k not in out:
            out[k] = v

    if fix2_out.get("fix2_applied"):
        out["fix3_applied"] = False
        out["fix3_reason"] = "fix2_already_applied"
        out["fix3_score_absent_risk"] = False
        out["combined123_answer_canonical"] = fix2_out.get("fix2_answer_canonical")
        out["combined123_answer_raw"] = fix2_out.get("fix2_answer_raw")
        out["combined123_policy_applied"] = "fix2"
        out["combined123_policy"] = COMBINED_FIX123_POLICY_NAME
        return out

    # Step 3: FIX-2 didn't fire — try FIX-3
    fix3_out = apply_fix3_to_row(out, external_answers=external_answers)
    for k, v in fix3_out.items():
        if k.startswith("fix3_") or k not in out:
            out[k] = v

    if fix3_out.get("fix3_applied"):
        out["combined123_answer_canonical"] = fix3_out.get("fix3_answer_canonical")
        out["combined123_answer_raw"] = fix3_out.get("fix3_answer_raw")
        out["combined123_policy_applied"] = "fix3"
    else:
        out["combined123_answer_canonical"] = _normalize_answer(
            row.get("final_answer_canonical") or row.get("selected_answer_canonical")
        )
        out["combined123_answer_raw"] = row.get("final_answer_raw")
        out["combined123_policy_applied"] = "original"

    out["combined123_policy"] = COMBINED_FIX123_POLICY_NAME
    return out


# ─── FIX-4: External unanimous consensus / TALE-complementarity gate ──────────
#
# Empirical note (from precise failure pattern mining, 2026-05-19):
# Pattern P1 found that when override_reason == "direct_frontier_agree" and all
# three external baselines unanimously agree on a different answer from frontier,
# the frontier answer is wrong in 100% of observed cases (promo-grade set).
# This happens because frontier and direct-reserve agree on the same candidate
# (1 branch each, CPC=2, confidence=0.5) while the alternative in the pool is
# the correct answer.  FIX-1 doesn't catch these because frontier_candidate ==
# incumbent.  The unanimous external signal is the only inference-available
# discriminator.
#
# Trigger is conservative: all 3 externals must agree AND override_reason must
# be "direct_frontier_agree" (not SWFB, which is handled by FIX-2).
# Precision on promo-grade: 2/2 = 100%.  Regression risk: 0 observed.

FIX4_POLICY_NAME = "direct_reserve_semantic_frontier_v2_external_consensus_gate_v1"
FIX4_POLICY_VERSION = "1.0"
FIX4_POLICY_DESCRIPTION = (
    "External unanimous consensus gate (FIX-4): "
    "when override_reason == 'direct_frontier_agree' and all three external baselines "
    "(l1_max, s1_budget_forcing, tale_prompt_budgeting) unanimously agree on an answer "
    "different from the frontier answer, prefer the unanimous external answer. "
    "Conservative: requires all 3/3 externals and direct_frontier_agree override only."
)

COMBINED_FIX24_POLICY_NAME = "direct_reserve_semantic_frontier_v2_lowdepth_external_consensus_v1"
COMBINED_FIX24_POLICY_VERSION = "1.0"
COMBINED_FIX24_POLICY_DESCRIPTION = (
    "Combined FIX-2 + FIX-4: "
    "FIX-2 (low-depth SWFB fallback) takes precedence; "
    "if not triggered, FIX-4 (external unanimous consensus gate) applies."
)

COMBINED_FIX1234_POLICY_NAME = "direct_reserve_semantic_frontier_v2_support_lowdepth_calibrated_consensus_v1"
COMBINED_FIX1234_POLICY_VERSION = "1.0"
COMBINED_FIX1234_POLICY_DESCRIPTION = (
    "Combined FIX-1 + FIX-2 + FIX-3 + FIX-4: "
    "FIX-1 (tie/PNS) → FIX-2 (low-depth SWFB) → FIX-3 (verifier-absent) → "
    "FIX-4 (external unanimous consensus). Applied in precedence order; only one fires."
)

# ─── FIX-5: TALE-default conservative agreement-region router ───────────────
#
# Goal: use TALE as the default answer, and only switch to a frontier-derived
# candidate in high-confidence agreement regions that are fully inference-available.
# Candidate frontier policy arm: FIX-2+FIX-4 combined answer.

FIX5_POLICY_NAME = "external_tale_default_frontier_switch_v1"
FIX5_POLICY_VERSION = "1.0"
FIX5_POLICY_DESCRIPTION = (
    "TALE-default conservative router (FIX-5): default to "
    "external_tale_prompt_budgeting, switch to frontier candidate "
    "(FIX-2+FIX-4 answer) only in precise high-confidence agreement regions. "
    "Never switch when externals unanimously disagree with frontier, when "
    "frontier is low-depth risk, or when required metadata/answers are missing."
)

_REQUIRED_EXTERNAL_METHODS = (
    "external_l1_max",
    "external_s1_budget_forcing",
    "external_tale_prompt_budgeting",
)


def external_unanimous_answer(
    external_answers: dict[str, Any],
    required_methods: tuple[str, ...] = _REQUIRED_EXTERNAL_METHODS,
) -> str | None:
    """Return the unanimous canonical answer if all required externals agree, else None.

    Returns None if any required method is missing or answers disagree.
    Gold-free: uses only the external methods' final_answer_canonical values.
    """
    normed: dict[str, str] = {}
    for m in required_methods:
        ans = external_answers.get(m)
        n = _normalize_answer(ans)
        if not n:
            return None  # missing or unparseable → no consensus
        normed[m] = n
    vals = set(normed.values())
    if len(vals) == 1:
        return next(iter(vals))
    return None  # disagreement among externals


def is_external_unanimous_against_frontier(
    frontier_answer: str | None,
    external_answers: dict[str, Any],
    result_metadata: dict[str, Any] | None = None,
) -> bool:
    """Return True if FIX-4 should fire (all 3 externals unanimous, differ from frontier).

    Conservative: when result_metadata is provided, also requires
    override_reason == 'direct_frontier_agree'.  If override_reason is absent or
    any other value, returns False (no broadening).

    Gold-free: no correctness or gold fields are used.
    """
    # Conservative override_reason gate
    if result_metadata is None:
        return False  # no metadata — do not trigger
    override = str(result_metadata.get("override_reason", "") or "")
    if override != "direct_frontier_agree":
        return False  # SWFB handled by FIX-2; missing handled conservatively

    unanimous = external_unanimous_answer(external_answers)
    if unanimous is None:
        return False  # missing or disagreeing externals

    frontier_norm = _normalize_answer(frontier_answer)
    if not frontier_norm:
        return False  # frontier answer not parseable

    return unanimous != frontier_norm


def apply_fix4_to_row(
    row: dict[str, Any],
    external_answers: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply FIX-4 external unanimous consensus gate to a single frontier row.

    Args:
        row: per-example record dict (direct_reserve_semantic_frontier_v2).
        external_answers: method_name → final_answer_canonical for the same example_id.

    Returns:
        Copy of row with fix4_* fields added.
    """
    out = dict(row)
    method = str(row.get("method", ""))

    if "direct_reserve_semantic_frontier_v2" not in method:
        out["fix4_applied"] = False
        out["fix4_reason"] = "not_frontier_method"
        out["fix4_answer_canonical"] = row.get("final_answer_canonical")
        out["fix4_answer_raw"] = row.get("final_answer_raw")
        return out

    rm = row.get("result_metadata")
    if isinstance(rm, str):
        import json as _json
        try:
            rm = _json.loads(rm)
        except Exception:
            rm = {}

    current = row.get("final_answer_canonical") or row.get("selected_answer_canonical")
    ext = external_answers or {}
    override_val = str((rm or {}).get("override_reason", "") or "")

    out["fix4_override_reason"] = override_val
    out["fix4_original_answer"] = current

    triggered = is_external_unanimous_against_frontier(
        frontier_answer=current,
        external_answers=ext,
        result_metadata=rm or {},
    )

    if not triggered:
        out["fix4_applied"] = False
        # Document reason for not triggering
        if rm is None or not isinstance(rm, dict):
            out["fix4_reason"] = "no_result_metadata"
        elif override_val != "direct_frontier_agree":
            out["fix4_reason"] = f"override_not_dfa:{override_val or 'missing'}"
        elif external_unanimous_answer(ext) is None:
            out["fix4_reason"] = "externals_not_unanimous_or_missing"
        else:
            out["fix4_reason"] = "external_consensus_matches_frontier"
        out["fix4_answer_canonical"] = current
        out["fix4_answer_raw"] = current
        return out

    # FIX-4 fires
    unanimous = external_unanimous_answer(ext)
    out["fix4_applied"] = True
    out["fix4_reason"] = "external_unanimous_consensus_over_direct_frontier_agree"
    out["fix4_unanimous_answer"] = unanimous
    out["fix4_answer_canonical"] = unanimous
    out["fix4_answer_raw"] = unanimous
    return out


def apply_combined_fix24_to_row(
    row: dict[str, Any],
    external_answers: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply FIX-2 then FIX-4 in precedence order (FIX-2 first).

    FIX-2 handles low-depth / SWFB via external majority.
    FIX-4 handles symmetric-tie + unanimous external consensus.
    Only one fires per row.

    Args:
        row: per-example record dict.
        external_answers: method_name → final_answer_canonical for same example_id.

    Returns:
        Copy of row with fix2_*, fix4_*, and combined24_* fields added.
    """
    # Step 1: try FIX-2
    fix2_out = apply_fix2_to_row(row, external_answers=external_answers)
    out = fix2_out

    if out.get("fix2_applied"):
        out["fix4_applied"] = False
        out["fix4_reason"] = "fix2_already_applied"
        out["fix4_answer_canonical"] = out.get("fix2_answer_canonical")
        out["fix4_answer_raw"] = out.get("fix2_answer_raw")
        out["combined24_answer_canonical"] = out.get("fix2_answer_canonical")
        out["combined24_answer_raw"] = out.get("fix2_answer_raw")
        out["combined24_policy_applied"] = "fix2"
        out["combined24_policy"] = COMBINED_FIX24_POLICY_NAME
        return out

    # Step 2: FIX-2 didn't fire — try FIX-4
    fix4_out = apply_fix4_to_row(out, external_answers=external_answers)
    for k, v in fix4_out.items():
        if k.startswith("fix4_") or k not in out:
            out[k] = v

    if fix4_out.get("fix4_applied"):
        out["combined24_answer_canonical"] = fix4_out.get("fix4_answer_canonical")
        out["combined24_answer_raw"] = fix4_out.get("fix4_answer_raw")
        out["combined24_policy_applied"] = "fix4"
    else:
        out["combined24_answer_canonical"] = _normalize_answer(
            row.get("final_answer_canonical") or row.get("selected_answer_canonical")
        )
        out["combined24_answer_raw"] = row.get("final_answer_raw")
        out["combined24_policy_applied"] = "original"

    out["combined24_policy"] = COMBINED_FIX24_POLICY_NAME
    return out


def apply_combined_fix1234_to_row(
    row: dict[str, Any],
    external_answers: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply FIX-1 → FIX-2 → FIX-3 → FIX-4 in precedence order.

    Only one fix fires per row.

    Args:
        row: per-example record dict.
        external_answers: method_name → final_answer_canonical for same example_id.

    Returns:
        Copy of row with fix1_*, fix2_*, fix3_*, fix4_*, and combined1234_* fields.
    """
    # Steps 1-3: reuse FIX-1+2+3 combined
    out = apply_combined_fix123_to_row(row, external_answers=external_answers)

    if out.get("combined123_policy_applied") in ("fix1", "fix2", "fix3"):
        # One of FIX-1/2/3 already fired
        out["fix4_applied"] = False
        out["fix4_reason"] = f"{out['combined123_policy_applied']}_already_applied"
        out["fix4_answer_canonical"] = out.get("combined123_answer_canonical")
        out["fix4_answer_raw"] = out.get("combined123_answer_raw")
        out["combined1234_answer_canonical"] = out.get("combined123_answer_canonical")
        out["combined1234_answer_raw"] = out.get("combined123_answer_raw")
        out["combined1234_policy_applied"] = out["combined123_policy_applied"]
        out["combined1234_policy"] = COMBINED_FIX1234_POLICY_NAME
        return out

    # Step 4: try FIX-4
    fix4_out = apply_fix4_to_row(out, external_answers=external_answers)
    for k, v in fix4_out.items():
        if k.startswith("fix4_") or k not in out:
            out[k] = v

    if fix4_out.get("fix4_applied"):
        out["combined1234_answer_canonical"] = fix4_out.get("fix4_answer_canonical")
        out["combined1234_answer_raw"] = fix4_out.get("fix4_answer_raw")
        out["combined1234_policy_applied"] = "fix4"
    else:
        out["combined1234_answer_canonical"] = _normalize_answer(
            row.get("final_answer_canonical") or row.get("selected_answer_canonical")
        )
        out["combined1234_answer_raw"] = row.get("final_answer_raw")
        out["combined1234_policy_applied"] = "original"

    out["combined1234_policy"] = COMBINED_FIX1234_POLICY_NAME
    return out


def external_agreement_signature(external_answers: dict[str, Any]) -> str:
    """Return a compact agreement signature for L1/S1/TALE answers.

    Example signatures:
    - ``l1=s1=tale``
    - ``l1=s1!=tale``
    - ``l1=tale!=s1``
    - ``all_different``
    - ``missing_external_answer``
    """
    l1 = _normalize_answer(external_answers.get("external_l1_max"))
    s1 = _normalize_answer(external_answers.get("external_s1_budget_forcing"))
    tale = _normalize_answer(external_answers.get("external_tale_prompt_budgeting"))
    if not l1 or not s1 or not tale:
        return "missing_external_answer"
    if l1 == s1 == tale:
        return "l1=s1=tale"
    if l1 == s1 != tale:
        return "l1=s1!=tale"
    if l1 == tale != s1:
        return "l1=tale!=s1"
    if s1 == tale != l1:
        return "s1=tale!=l1"
    return "all_different"


def is_tale_isolated(external_answers: dict[str, Any]) -> bool:
    """Return True when L1 and S1 agree but TALE differs."""
    return external_agreement_signature(external_answers) == "l1=s1!=tale"


def frontier_agrees_with_external_majority(
    frontier_answer: str | None,
    external_answers: dict[str, Any],
) -> bool:
    """Return True if frontier answer matches at least 2 of {L1, S1, TALE}."""
    from collections import Counter

    f = _normalize_answer(frontier_answer)
    if not f:
        return False
    vals: list[str] = []
    for m in _REQUIRED_EXTERNAL_METHODS:
        n = _normalize_answer(external_answers.get(m))
        if not n:
            return False
        vals.append(n)
    counts = Counter(vals)
    return counts.get(f, 0) >= 2


def should_switch_from_tale_to_frontier_v1(
    *,
    frontier_candidate_answer: str | None,
    tale_answer: str | None,
    external_answers: dict[str, Any],
    result_metadata: dict[str, Any] | None,
) -> tuple[bool, str]:
    """Return (should_switch, reason) for FIX-5 TALE-default router.

    Routing is conservative and fully inference-time:
    - default action is TALE
    - block switching on missing metadata/answers, unanimous externals against
      frontier, and low-depth frontier risk
    - allow switching only in precise agreement regions
    """
    if not isinstance(result_metadata, dict):
        return False, "blocked_missing_metadata"

    frontier_norm = _normalize_answer(frontier_candidate_answer)
    tale_norm = _normalize_answer(tale_answer)
    l1_norm = _normalize_answer(external_answers.get("external_l1_max"))
    s1_norm = _normalize_answer(external_answers.get("external_s1_budget_forcing"))

    if not frontier_norm or not tale_norm or not l1_norm or not s1_norm:
        return False, "blocked_missing_metadata"

    unanimous = external_unanimous_answer(external_answers)
    if unanimous and unanimous != frontier_norm:
        return False, "blocked_external_unanimous_against_frontier"

    if is_low_depth_risk(result_metadata):
        return False, "blocked_low_depth_frontier"

    override_reason = str(result_metadata.get("override_reason", "") or "")
    support_margin = result_metadata.get("support_margin")
    try:
        support_margin_val = float(support_margin) if support_margin is not None else None
    except (TypeError, ValueError):
        support_margin_val = None

    if support_margin_val is None:
        return False, "blocked_missing_metadata"

    # If switch target equals TALE, keep default.
    if frontier_norm == tale_norm:
        return False, "tale_default"

    # Region A: TALE isolated, L1/S1 agree with frontier candidate.
    if (
        override_reason == "direct_frontier_agree"
        and support_margin_val > 0.0
        and is_tale_isolated(external_answers)
        and l1_norm == s1_norm == frontier_norm
    ):
        return True, "frontier_switch_tale_isolated_l1_s1_agree"

    # Region B: majority external support for frontier and TALE differs.
    sig = external_agreement_signature(external_answers)
    if (
        override_reason == "direct_frontier_agree"
        and support_margin_val > 0.0
        and
        frontier_agrees_with_external_majority(frontier_norm, external_answers)
        and sig == "l1=s1!=tale"
    ):
        return True, "frontier_switch_external_majority_support"

    return False, "tale_default"


def apply_fix5_tale_default_router(
    row: dict[str, Any],
    external_answers: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply FIX-5 TALE-default conservative router to a frontier row.

    Candidate frontier arm is FIX-2+FIX-4 (combined24 answer). The router
    defaults to TALE and only switches when the conservative trigger fires.
    """
    out = dict(row)
    method = str(row.get("method", ""))
    if "direct_reserve_semantic_frontier_v2" not in method:
        out["fix5_applied"] = False
        out["fix5_reason"] = "not_frontier_method"
        out["fix5_answer_canonical"] = row.get("final_answer_canonical")
        out["fix5_answer_raw"] = row.get("final_answer_raw")
        out["fix5_policy"] = FIX5_POLICY_NAME
        return out

    rm = row.get("result_metadata")
    if isinstance(rm, str):
        import json as _json
        try:
            rm = _json.loads(rm)
        except Exception:
            rm = {}

    ext = external_answers or {}
    tale_answer = ext.get("external_tale_prompt_budgeting")
    tale_norm = _normalize_answer(tale_answer)

    # Candidate frontier arm = FIX-2 + FIX-4 answer
    combined24 = apply_combined_fix24_to_row(row, external_answers=ext)
    frontier_candidate = combined24.get("combined24_answer_canonical")
    frontier_candidate_norm = _normalize_answer(frontier_candidate)

    out["fix5_policy"] = FIX5_POLICY_NAME
    out["fix5_policy_version"] = FIX5_POLICY_VERSION
    out["fix5_external_agreement_signature"] = external_agreement_signature(ext)
    out["fix5_is_tale_isolated"] = is_tale_isolated(ext)
    out["fix5_frontier_candidate_from"] = "combined_fix24"
    out["fix5_frontier_candidate_canonical"] = frontier_candidate_norm
    out["fix5_tale_answer_canonical"] = tale_norm
    out["fix5_is_low_depth_frontier"] = is_low_depth_risk(rm or {})
    out["fix5_blocked_external_unanimous_against_frontier"] = bool(
        external_unanimous_answer(ext)
        and frontier_candidate_norm
        and external_unanimous_answer(ext) != frontier_candidate_norm
    )

    # If TALE is missing/unparseable, we cannot run a TALE-default policy safely.
    if not tale_norm:
        out["fix5_applied"] = False
        out["fix5_reason"] = "blocked_missing_metadata"
        out["fix5_answer_canonical"] = frontier_candidate_norm
        out["fix5_answer_raw"] = frontier_candidate_norm
        return out

    should_switch, reason = should_switch_from_tale_to_frontier_v1(
        frontier_candidate_answer=frontier_candidate_norm,
        tale_answer=tale_norm,
        external_answers=ext,
        result_metadata=rm or {},
    )

    if should_switch and frontier_candidate_norm:
        out["fix5_applied"] = True
        out["fix5_reason"] = reason
        out["fix5_answer_canonical"] = frontier_candidate_norm
        out["fix5_answer_raw"] = frontier_candidate_norm
        return out

    out["fix5_applied"] = False
    out["fix5_reason"] = reason
    out["fix5_answer_canonical"] = tale_norm
    out["fix5_answer_raw"] = tale_norm
    return out
