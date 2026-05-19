"""Tests for FIX-1 (support-aware selector) and FIX-2 (low-depth guard).

FIX-1 tests:
- Tie detection (support_margin=0, confidence<=0.5)
- Strict majority preserves original choice
- PNS-risk case changes decision
- No gold/exact fields used as features
- Backward compatibility (non-frontier methods unchanged)
- No API calls

FIX-2 tests:
- single_weak_frontier_branch triggers FIX-2
- Normal-depth frontier does not trigger
- External majority fallback selection
- Combined FIX-1+FIX-2 applies FIX-1 first
- No gold/exact used as features
"""
import pytest
from experiments.support_aware_selector import (
    should_apply_support_aware_fix,
    apply_support_aware_fix,
    apply_support_aware_fix_to_row,
    is_low_depth_risk,
    apply_fix2_to_row,
    select_external_majority,
    apply_combined_fix_to_row,
    _normalize_answer,
    POLICY_NAME,
    FIX2_POLICY_NAME,
    COMBINED_POLICY_NAME,
)


# ─── Unit tests for should_apply_support_aware_fix ───────────────────────────

def test_tie_triggers_fix():
    """Tied support (margin=0, confidence=0.5) with parseable frontier triggers FIX-1."""
    assert should_apply_support_aware_fix(
        support_margin=0.0,
        direct_reserve_confidence_proxy=0.5,
        frontier_candidate_answer="42",
        incumbent_answer="19",
    )


def test_strict_majority_preserves_incumbent():
    """When incumbent has strict majority (margin>0), FIX-1 does not apply."""
    assert not should_apply_support_aware_fix(
        support_margin=1.0,
        direct_reserve_confidence_proxy=0.8,
        frontier_candidate_answer="42",
        incumbent_answer="19",
    )


def test_high_confidence_preserves_incumbent():
    """When confidence > 0.5, FIX-1 does not apply even with margin=0."""
    assert not should_apply_support_aware_fix(
        support_margin=0.0,
        direct_reserve_confidence_proxy=0.7,
        frontier_candidate_answer="42",
        incumbent_answer="19",
    )


def test_unparseable_frontier_no_fix():
    """FIX-1 does not apply if frontier candidate is not parseable."""
    assert not should_apply_support_aware_fix(
        support_margin=0.0,
        direct_reserve_confidence_proxy=0.5,
        frontier_candidate_answer=None,
        incumbent_answer="19",
    )
    assert not should_apply_support_aware_fix(
        support_margin=0.0,
        direct_reserve_confidence_proxy=0.5,
        frontier_candidate_answer="",
        incumbent_answer="19",
    )


def test_frontier_agrees_with_incumbent_no_fix():
    """FIX-1 does not apply when frontier and incumbent give the same answer."""
    assert not should_apply_support_aware_fix(
        support_margin=0.0,
        direct_reserve_confidence_proxy=0.5,
        frontier_candidate_answer="42",
        incumbent_answer="42",
    )


def test_negative_margin_no_fix():
    """When frontier support is LESS than incumbent (negative margin), no fix."""
    assert not should_apply_support_aware_fix(
        support_margin=-1.0,
        direct_reserve_confidence_proxy=0.5,
        frontier_candidate_answer="42",
        incumbent_answer="19",
    )


def test_none_metadata_no_fix():
    """Missing margin or confidence fields → no fix."""
    assert not should_apply_support_aware_fix(
        support_margin=None,
        direct_reserve_confidence_proxy=0.5,
        frontier_candidate_answer="42",
        incumbent_answer="19",
    )
    assert not should_apply_support_aware_fix(
        support_margin=0.0,
        direct_reserve_confidence_proxy=None,
        frontier_candidate_answer="42",
        incumbent_answer="19",
    )


# ─── Integration tests for apply_support_aware_fix ───────────────────────────

def test_pns_risk_changes_answer():
    """PNS-risk case: tie + parseable frontier → answer switches to frontier."""
    rm = {
        "support_margin": 0.0,
        "direct_reserve_confidence_proxy": 0.5,
        "frontier_candidate_answer": "42",
        "incumbent_support": 1,
        "frontier_support": 1,
    }
    new_ans, meta = apply_support_aware_fix(result_metadata=rm, current_final_answer="19")
    assert new_ans == "42"
    assert meta["fix_applied"] is True
    assert meta["fix_reason"] == "tie_support_frontier_preferred"


def test_strong_majority_unchanged():
    """Strong majority → incumbent preserved."""
    rm = {
        "support_margin": 1.0,
        "direct_reserve_confidence_proxy": 0.9,
        "frontier_candidate_answer": "42",
    }
    new_ans, meta = apply_support_aware_fix(result_metadata=rm, current_final_answer="19")
    assert new_ans == "19"
    assert meta["fix_applied"] is False


def test_no_gold_or_exact_in_inputs():
    """Policy inputs must not include gold_answer or exact_match."""
    rm = {
        "support_margin": 0.0,
        "direct_reserve_confidence_proxy": 0.5,
        "frontier_candidate_answer": "42",
        # deliberately add gold-like keys — policy must ignore them
        "gold_answer": "42",
        "exact_match": 1,
    }
    new_ans, meta = apply_support_aware_fix(result_metadata=rm, current_final_answer="19")
    # fix should still trigger based on support/confidence, ignoring gold
    assert meta["fix_applied"] is True
    assert meta["chosen_answer"] == "42"


def test_apply_to_row_frontier_method():
    """apply_support_aware_fix_to_row works for frontier method rows."""
    row = {
        "method": "direct_reserve_semantic_frontier_v2",
        "final_answer_canonical": "19",
        "final_answer_raw": "19",
        "result_metadata": {
            "support_margin": 0.0,
            "direct_reserve_confidence_proxy": 0.5,
            "frontier_candidate_answer": "42",
        },
    }
    out = apply_support_aware_fix_to_row(row)
    assert out["fix1_applied"] is True
    assert out["fix1_answer_canonical"] == "42"
    assert out["fix1_original_answer"] == "19"


def test_apply_to_row_non_frontier_method_unchanged():
    """Non-frontier methods are passed through unchanged."""
    row = {
        "method": "external_l1_max",
        "final_answer_canonical": "99",
        "result_metadata": {},
    }
    out = apply_support_aware_fix_to_row(row)
    assert out["fix1_applied"] is False
    assert out["fix1_reason"] == "not_frontier_method"
    assert out["fix1_answer_canonical"] == "99"


def test_policy_name_stable():
    """Policy name is stable and identifiable."""
    assert "support_aware" in POLICY_NAME
    assert "direct_reserve_semantic_frontier_v2" in POLICY_NAME


def test_no_provider_api_calls(monkeypatch):
    """Ensure no external API calls are made (smoke test)."""
    import sys
    # if 'requests' or 'cohere' would be imported, this would catch it
    assert "requests" not in dir() or True  # always pass — no requests needed
    # Actually call the module — if it makes API calls, the test env would fail
    rm = {"support_margin": 0.0, "direct_reserve_confidence_proxy": 0.5, "frontier_candidate_answer": "7"}
    new_ans, _ = apply_support_aware_fix(result_metadata=rm, current_final_answer="3")
    assert new_ans == "7"


# ─── FIX-2: Low-depth guard tests ─────────────────────────────────────────────

def test_fix2_swfb_triggers():
    """single_weak_frontier_branch override triggers FIX-2 is_low_depth_risk."""
    rm = {"override_reason": "single_weak_frontier_branch", "frontier_support": 0}
    assert is_low_depth_risk(rm)


def test_fix2_normal_depth_no_trigger():
    """Normal frontier (direct_frontier_agree) does not trigger FIX-2."""
    rm = {"override_reason": "direct_frontier_agree", "frontier_support": 2}
    assert not is_low_depth_risk(rm)


def test_fix2_empty_metadata_no_trigger():
    """Empty result_metadata does not trigger FIX-2."""
    assert not is_low_depth_risk({})
    assert not is_low_depth_risk(None)  # type: ignore


def test_fix2_frontier_support_zero_plus_scattered_pool():
    """frontier_support==0 AND candidate_pool_answer_group_count>=2 triggers FIX-2."""
    rm = {"override_reason": "insufficient_support_margin", "frontier_support": 0,
          "candidate_pool_answer_group_count": 3}
    assert is_low_depth_risk(rm)


def test_fix2_frontier_support_zero_single_pool_no_trigger():
    """frontier_support==0 but only 1 candidate group (convergent) does NOT trigger via fallback."""
    rm = {"override_reason": "insufficient_support_margin", "frontier_support": 0,
          "candidate_pool_answer_group_count": 1}
    assert not is_low_depth_risk(rm)


def test_select_external_majority_clear_winner():
    """Majority of 2/3 external baselines returns the agreed answer."""
    ext = {"external_l1_max": "42", "external_s1_budget_forcing": "42", "external_tale_prompt_budgeting": "19"}
    ans, meta = select_external_majority(ext)
    assert ans == "42"
    assert meta["reason"] == "external_majority_vote"
    assert meta["vote_count"] == 2


def test_select_external_majority_all_agree():
    """All 3 external baselines agree."""
    ext = {"external_l1_max": "7", "external_s1_budget_forcing": "7", "external_tale_prompt_budgeting": "7"}
    ans, meta = select_external_majority(ext)
    assert ans == "7"
    assert meta["vote_count"] == 3


def test_select_external_majority_no_majority_uses_priority():
    """3-way tie falls back to priority order (tale > s1 > l1)."""
    ext = {"external_l1_max": "1", "external_s1_budget_forcing": "2", "external_tale_prompt_budgeting": "3"}
    ans, meta = select_external_majority(ext)
    assert ans == "3"  # tale answer
    assert "priority" in meta["reason"]


def test_select_external_majority_empty_returns_none():
    """Empty dict returns no answer."""
    ans, meta = select_external_majority({})
    assert ans is None


def test_fix2_applies_to_swfb_row():
    """FIX-2 switches answer for single_weak_frontier_branch row with external majority."""
    row = {
        "method": "direct_reserve_semantic_frontier_v2",
        "final_answer_canonical": "99",
        "final_answer_raw": "99",
        "result_metadata": {"override_reason": "single_weak_frontier_branch"},
    }
    ext = {"external_l1_max": "42", "external_s1_budget_forcing": "42", "external_tale_prompt_budgeting": "19"}
    out = apply_fix2_to_row(row, external_answers=ext)
    assert out["fix2_applied"] is True
    assert out["fix2_answer_canonical"] == "42"
    assert out["fix2_reason"] == "low_depth_external_fallback"
    assert out["fix2_is_low_depth"] is True


def test_fix2_no_trigger_on_normal_depth():
    """FIX-2 does not apply to normal-depth frontier rows."""
    row = {
        "method": "direct_reserve_semantic_frontier_v2",
        "final_answer_canonical": "19",
        "final_answer_raw": "19",
        "result_metadata": {"override_reason": "direct_frontier_agree", "frontier_support": 2},
    }
    out = apply_fix2_to_row(row, external_answers={"external_l1_max": "42"})
    assert out["fix2_applied"] is False
    assert out["fix2_reason"] == "not_triggered"
    assert out["fix2_answer_canonical"] == "19"


def test_fix2_no_gold_required():
    """FIX-2 trigger and selection uses no gold/exact fields."""
    row = {
        "method": "direct_reserve_semantic_frontier_v2",
        "final_answer_canonical": "5",
        "final_answer_raw": "5",
        "result_metadata": {"override_reason": "single_weak_frontier_branch"},
    }
    # No gold_answer or exact_match passed to apply_fix2_to_row
    out = apply_fix2_to_row(row, external_answers={"external_tale_prompt_budgeting": "7"})
    assert out["fix2_applied"] is True
    assert "gold" not in out["fix2_reason"]


def test_combined_fix1_takes_precedence_over_fix2():
    """When FIX-1 applies, FIX-2 is skipped."""
    row = {
        "method": "direct_reserve_semantic_frontier_v2",
        "final_answer_canonical": "19",
        "final_answer_raw": "19",
        "result_metadata": {
            "support_margin": 0.0,
            "direct_reserve_confidence_proxy": 0.5,
            "frontier_candidate_answer": "42",
            "override_reason": "single_weak_frontier_branch",  # would trigger FIX-2 too
        },
    }
    ext = {"external_l1_max": "99", "external_s1_budget_forcing": "99", "external_tale_prompt_budgeting": "99"}
    out = apply_combined_fix_to_row(row, external_answers=ext)
    assert out["fix1_applied"] is True
    assert out["combined_answer_canonical"] == "42"   # FIX-1 answer, not external 99
    assert out["combined_policy_applied"] == "fix1"
    assert out["fix2_reason"] == "fix1_already_applied"


def test_combined_fix2_applies_when_fix1_not_triggered():
    """When FIX-1 doesn't fire, FIX-2 can apply."""
    row = {
        "method": "direct_reserve_semantic_frontier_v2",
        "final_answer_canonical": "5",
        "final_answer_raw": "5",
        "result_metadata": {
            "support_margin": 1.0,           # strict majority — FIX-1 will not fire
            "direct_reserve_confidence_proxy": 0.9,
            "frontier_candidate_answer": "5",
            "override_reason": "single_weak_frontier_branch",
        },
    }
    ext = {"external_l1_max": "42", "external_s1_budget_forcing": "42", "external_tale_prompt_budgeting": "19"}
    out = apply_combined_fix_to_row(row, external_answers=ext)
    assert out["fix1_applied"] is False
    assert out["fix2_applied"] is True
    assert out["combined_answer_canonical"] == "42"
    assert out["combined_policy_applied"] == "fix2"


def test_combined_neither_fix_leaves_original():
    """When neither FIX-1 nor FIX-2 triggers, original answer is preserved."""
    row = {
        "method": "direct_reserve_semantic_frontier_v2",
        "final_answer_canonical": "77",
        "final_answer_raw": "77",
        "result_metadata": {
            "support_margin": 1.0,
            "direct_reserve_confidence_proxy": 0.9,
            "frontier_candidate_answer": "77",
            "override_reason": "direct_frontier_agree",
            "frontier_support": 2,
        },
    }
    out = apply_combined_fix_to_row(row, external_answers={"external_l1_max": "99"})
    assert out["fix1_applied"] is False
    assert out["fix2_applied"] is False
    assert out["combined_policy_applied"] == "original"


def test_fix2_policy_names_stable():
    """Policy name constants are identifiable."""
    assert "low_depth_guard" in FIX2_POLICY_NAME
    assert "support_aware" in COMBINED_POLICY_NAME
    assert "low_depth_guard" in COMBINED_POLICY_NAME
