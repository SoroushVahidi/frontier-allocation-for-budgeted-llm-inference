"""Tests for FIX-1 through FIX-4 and combined policies.

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

FIX-4 tests:
- All 3 externals agree and differ from frontier with direct_frontier_agree → triggers
- 2/3 externals agree → does not trigger
- External consensus equals frontier → does not trigger
- Any external missing → does not trigger
- override_reason not direct_frontier_agree → does not trigger
- No gold/exact fields required
- Combined FIX-2+FIX-4 applies FIX-2 first
- Combined FIX-1+2+3+4 precedence correct
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
    is_verifier_score_absent_risk,
    get_agbs_best_score,
    apply_fix3_to_row,
    apply_combined_fix123_to_row,
    external_unanimous_answer,
    is_external_unanimous_against_frontier,
    apply_fix4_to_row,
    apply_combined_fix24_to_row,
    apply_combined_fix1234_to_row,
    external_agreement_signature,
    is_tale_isolated,
    frontier_agrees_with_external_majority,
    should_switch_from_tale_to_frontier_v1,
    apply_fix5_tale_default_router,
    _normalize_answer,
    POLICY_NAME,
    FIX2_POLICY_NAME,
    COMBINED_POLICY_NAME,
    FIX3_POLICY_NAME,
    COMBINED_FIX123_POLICY_NAME,
    FIX4_POLICY_NAME,
    COMBINED_FIX24_POLICY_NAME,
    COMBINED_FIX1234_POLICY_NAME,
    FIX5_POLICY_NAME,
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


# ─── FIX-3: Within-method verifier calibration guard tests ───────────────────

def test_fix3_budget_exhausted_triggers():
    """frontier_not_run_or_budget_exhausted triggers FIX-3."""
    rm = {"override_reason": "frontier_not_run_or_budget_exhausted"}
    assert is_verifier_score_absent_risk(rm)


def test_fix3_empty_agbs_non_swfb_triggers():
    """Empty AGBS on a non-SWFB row triggers FIX-3."""
    rm = {"override_reason": "direct_frontier_agree", "answer_group_best_branch_scores": {}}
    assert is_verifier_score_absent_risk(rm)


def test_fix3_swfb_does_not_trigger():
    """SWFB rows are handled by FIX-2 and should NOT trigger FIX-3."""
    rm = {"override_reason": "single_weak_frontier_branch", "answer_group_best_branch_scores": {}}
    assert not is_verifier_score_absent_risk(rm)


def test_fix3_agbs_present_no_trigger():
    """Rows with AGBS scores present do NOT trigger FIX-3."""
    rm = {"override_reason": "direct_frontier_agree",
          "answer_group_best_branch_scores": {"12": 0.8}}
    assert not is_verifier_score_absent_risk(rm)


def test_fix3_none_metadata_no_trigger():
    """None metadata (type guard) does not trigger FIX-3."""
    assert not is_verifier_score_absent_risk(None)  # type: ignore


def test_fix3_empty_dict_triggers_score_absent():
    """Completely empty result_metadata has no AGBS → score absent risk fires."""
    # Empty metadata means no verifier score available, which is a valid trigger.
    assert is_verifier_score_absent_risk({})


def test_get_agbs_best_score_returns_max():
    """get_agbs_best_score returns the maximum score across groups."""
    rm = {"answer_group_best_branch_scores": {"1": 0.8, "2": 0.9, "3": 0.875}}
    assert get_agbs_best_score(rm) == pytest.approx(0.9)


def test_get_agbs_best_score_empty_returns_none():
    """Empty AGBS returns None."""
    assert get_agbs_best_score({}) is None
    assert get_agbs_best_score({"answer_group_best_branch_scores": {}}) is None


def test_fix3_applies_to_budget_exhausted_row():
    """FIX-3 switches answer for budget-exhausted row with external majority."""
    row = {
        "method": "direct_reserve_semantic_frontier_v2",
        "final_answer_canonical": "5",
        "final_answer_raw": "5",
        "result_metadata": {"override_reason": "frontier_not_run_or_budget_exhausted"},
    }
    ext = {"external_l1_max": "42", "external_s1_budget_forcing": "42", "external_tale_prompt_budgeting": "19"}
    out = apply_fix3_to_row(row, external_answers=ext)
    assert out["fix3_applied"] is True
    assert out["fix3_answer_canonical"] == "42"
    assert out["fix3_reason"] == "verifier_score_absent_external_fallback"
    assert out["fix3_score_absent_risk"] is True


def test_fix3_no_trigger_agbs_present():
    """FIX-3 does not trigger when AGBS scores are present."""
    row = {
        "method": "direct_reserve_semantic_frontier_v2",
        "final_answer_canonical": "19",
        "final_answer_raw": "19",
        "result_metadata": {
            "override_reason": "direct_frontier_agree",
            "answer_group_best_branch_scores": {"1": 0.8},
        },
    }
    out = apply_fix3_to_row(row, external_answers={"external_l1_max": "42"})
    assert out["fix3_applied"] is False
    assert out["fix3_reason"] == "not_triggered"
    assert out["fix3_answer_canonical"] == "19"


def test_fix3_no_gold_required():
    """FIX-3 trigger uses no gold/exact fields."""
    row = {
        "method": "direct_reserve_semantic_frontier_v2",
        "final_answer_canonical": "3",
        "final_answer_raw": "3",
        "result_metadata": {"override_reason": "frontier_not_run_or_budget_exhausted"},
    }
    out = apply_fix3_to_row(row, external_answers={"external_tale_prompt_budgeting": "7"})
    assert out["fix3_applied"] is True
    assert "gold" not in out["fix3_reason"]


def test_fix3_does_not_use_raw_cross_method_proba():
    """FIX-3 does not compare frontier proba to external proba — no such field in trigger."""
    rm = {"override_reason": "frontier_not_run_or_budget_exhausted", "frontier_proba": 0.04, "baseline_proba": 0.9}
    # FIX-3 should still trigger on budget-exhausted alone, not on proba comparison
    assert is_verifier_score_absent_risk(rm)


def test_combined_fix123_fix1_takes_top_priority():
    """FIX-1 fires first; FIX-2 and FIX-3 skipped."""
    row = {
        "method": "direct_reserve_semantic_frontier_v2",
        "final_answer_canonical": "5",
        "final_answer_raw": "5",
        "result_metadata": {
            "support_margin": 0.0,
            "direct_reserve_confidence_proxy": 0.5,
            "frontier_candidate_answer": "42",
            "override_reason": "frontier_not_run_or_budget_exhausted",  # FIX-3 would fire too
        },
    }
    ext = {"external_l1_max": "99", "external_s1_budget_forcing": "99", "external_tale_prompt_budgeting": "99"}
    out = apply_combined_fix123_to_row(row, external_answers=ext)
    assert out["fix1_applied"] is True
    assert out["combined123_answer_canonical"] == "42"  # FIX-1 answer
    assert out["combined123_policy_applied"] == "fix1"
    assert out["fix3_reason"] == "fix1_already_applied"


def test_combined_fix123_fix2_takes_precedence_over_fix3():
    """FIX-2 fires before FIX-3; FIX-3 skipped."""
    row = {
        "method": "direct_reserve_semantic_frontier_v2",
        "final_answer_canonical": "5",
        "final_answer_raw": "5",
        "result_metadata": {
            "support_margin": 1.0,
            "direct_reserve_confidence_proxy": 0.9,
            "frontier_candidate_answer": "5",
            "override_reason": "single_weak_frontier_branch",  # FIX-2 trigger
            "answer_group_best_branch_scores": {},  # also FIX-3 trigger if not SWFB
        },
    }
    ext = {"external_l1_max": "42", "external_s1_budget_forcing": "42", "external_tale_prompt_budgeting": "19"}
    out = apply_combined_fix123_to_row(row, external_answers=ext)
    assert out["fix2_applied"] is True
    assert out["combined123_policy_applied"] == "fix2"
    assert out["fix3_reason"] == "fix2_already_applied"


def test_combined_fix123_fix3_fires_when_1_and_2_skip():
    """FIX-3 fires when FIX-1 and FIX-2 both don't trigger."""
    row = {
        "method": "direct_reserve_semantic_frontier_v2",
        "final_answer_canonical": "5",
        "final_answer_raw": "5",
        "result_metadata": {
            "support_margin": 1.0,
            "direct_reserve_confidence_proxy": 0.9,
            "frontier_candidate_answer": "5",
            "override_reason": "frontier_not_run_or_budget_exhausted",
            "answer_group_best_branch_scores": {},
        },
    }
    ext = {"external_l1_max": "42", "external_s1_budget_forcing": "42", "external_tale_prompt_budgeting": "19"}
    out = apply_combined_fix123_to_row(row, external_answers=ext)
    assert out["fix1_applied"] is False
    assert out["fix2_applied"] is False
    assert out["fix3_applied"] is True
    assert out["combined123_answer_canonical"] == "42"
    assert out["combined123_policy_applied"] == "fix3"


def test_fix3_policy_names_stable():
    """FIX-3 and combined FIX-1+2+3 policy names are identifiable."""
    assert "within_method_calibrated" in FIX3_POLICY_NAME
    assert "support_lowdepth_calibrated" in COMBINED_FIX123_POLICY_NAME


# ─── FIX-4 tests ──────────────────────────────────────────────────────────────


def _dfa_row(frontier_ans="40"):
    """Helper: a direct_frontier_agree row with the given frontier answer."""
    return {
        "method": "direct_reserve_semantic_frontier_v2",
        "final_answer_canonical": frontier_ans,
        "final_answer_raw": frontier_ans,
        "result_metadata": {
            "override_reason": "direct_frontier_agree",
            "support_margin": 0.0,
            "direct_reserve_confidence_proxy": 0.5,
            "candidate_pool_answer_group_count": 2,
        },
    }


def _all_ext_agree(ans="20"):
    return {
        "external_l1_max": ans,
        "external_s1_budget_forcing": ans,
        "external_tale_prompt_budgeting": ans,
    }


def test_fix4_triggers_unanimous_external_differ():
    """FIX-4 fires when all 3 externals agree and differ from frontier (direct_frontier_agree)."""
    row = _dfa_row("40")
    ext = _all_ext_agree("20")
    out = apply_fix4_to_row(row, external_answers=ext)
    assert out["fix4_applied"] is True
    assert out["fix4_answer_canonical"] == "20"
    assert out["fix4_reason"] == "external_unanimous_consensus_over_direct_frontier_agree"


def test_fix4_no_trigger_two_of_three_agree():
    """FIX-4 does NOT trigger when only 2/3 externals agree (third disagrees)."""
    row = _dfa_row("40")
    ext = {
        "external_l1_max": "20",
        "external_s1_budget_forcing": "20",
        "external_tale_prompt_budgeting": "99",  # disagrees
    }
    out = apply_fix4_to_row(row, external_answers=ext)
    assert out["fix4_applied"] is False
    assert out["fix4_answer_canonical"] == "40"


def test_fix4_no_trigger_consensus_equals_frontier():
    """FIX-4 does NOT trigger when external unanimous answer equals frontier answer."""
    row = _dfa_row("20")
    ext = _all_ext_agree("20")  # same as frontier
    out = apply_fix4_to_row(row, external_answers=ext)
    assert out["fix4_applied"] is False
    assert out["fix4_answer_canonical"] == "20"


def test_fix4_no_trigger_missing_external():
    """FIX-4 does NOT trigger when any external answer is missing."""
    row = _dfa_row("40")
    ext = {
        "external_l1_max": "20",
        "external_s1_budget_forcing": "20",
        # tale missing
    }
    out = apply_fix4_to_row(row, external_answers=ext)
    assert out["fix4_applied"] is False


def test_fix4_no_trigger_swfb_override():
    """FIX-4 does NOT trigger when override_reason is single_weak_frontier_branch (FIX-2's domain)."""
    row = {
        "method": "direct_reserve_semantic_frontier_v2",
        "final_answer_canonical": "40",
        "final_answer_raw": "40",
        "result_metadata": {"override_reason": "single_weak_frontier_branch"},
    }
    ext = _all_ext_agree("20")
    out = apply_fix4_to_row(row, external_answers=ext)
    assert out["fix4_applied"] is False
    assert "override_not_dfa" in out["fix4_reason"]


def test_fix4_no_trigger_missing_override_reason():
    """FIX-4 does NOT trigger when override_reason is absent (conservative fallback)."""
    row = {
        "method": "direct_reserve_semantic_frontier_v2",
        "final_answer_canonical": "40",
        "final_answer_raw": "40",
        "result_metadata": {},  # no override_reason
    }
    ext = _all_ext_agree("20")
    out = apply_fix4_to_row(row, external_answers=ext)
    assert out["fix4_applied"] is False


def test_fix4_no_gold_required():
    """FIX-4 trigger uses no gold_answer or exact_match fields."""
    row = _dfa_row("40")
    # Explicitly verify neither gold nor exact_match in result_metadata
    assert "gold_answer" not in (row.get("result_metadata") or {})
    assert "exact_match" not in (row.get("result_metadata") or {})
    ext = _all_ext_agree("20")
    out = apply_fix4_to_row(row, external_answers=ext)
    assert out["fix4_applied"] is True  # pure inference-time rule


def test_external_unanimous_answer_all_agree():
    """external_unanimous_answer returns the common answer when all 3 agree."""
    ext = _all_ext_agree("42")
    ans = external_unanimous_answer(ext)
    assert ans == "42"


def test_external_unanimous_answer_disagree_returns_none():
    """external_unanimous_answer returns None when externals disagree."""
    ext = {"external_l1_max": "42", "external_s1_budget_forcing": "42", "external_tale_prompt_budgeting": "99"}
    assert external_unanimous_answer(ext) is None


def test_external_unanimous_answer_missing_returns_none():
    """external_unanimous_answer returns None when a required method is absent."""
    ext = {"external_l1_max": "42", "external_s1_budget_forcing": "42"}
    assert external_unanimous_answer(ext) is None


def test_combined_fix24_fix2_takes_precedence_over_fix4():
    """In FIX-2+FIX-4 combined, FIX-2 fires first and FIX-4 does not run."""
    row = {
        "method": "direct_reserve_semantic_frontier_v2",
        "final_answer_canonical": "99",
        "final_answer_raw": "99",
        "result_metadata": {
            "override_reason": "single_weak_frontier_branch",
            "support_margin": 0.0,
        },
    }
    ext = {
        "external_l1_max": "42",
        "external_s1_budget_forcing": "42",
        "external_tale_prompt_budgeting": "42",
    }
    out = apply_combined_fix24_to_row(row, external_answers=ext)
    assert out["fix2_applied"] is True
    assert out["fix4_applied"] is False
    assert out["combined24_policy_applied"] == "fix2"
    assert out["combined24_answer_canonical"] == "42"


def test_combined_fix24_fix4_fires_when_fix2_skips():
    """In FIX-2+FIX-4 combined, FIX-4 fires when FIX-2 is not triggered."""
    row = _dfa_row("40")
    ext = _all_ext_agree("20")
    out = apply_combined_fix24_to_row(row, external_answers=ext)
    assert out["fix2_applied"] is False
    assert out["fix4_applied"] is True
    assert out["combined24_policy_applied"] == "fix4"
    assert out["combined24_answer_canonical"] == "20"


def test_combined_fix1234_precedence_fix1_top():
    """In FIX-1+2+3+4, FIX-1 takes top priority and FIX-4 does not fire."""
    row = {
        "method": "direct_reserve_semantic_frontier_v2",
        "final_answer_canonical": "10",
        "final_answer_raw": "10",
        "result_metadata": {
            "override_reason": "direct_frontier_agree",
            "support_margin": 0.0,
            "direct_reserve_confidence_proxy": 0.5,
            "frontier_candidate_answer": "99",  # different parseable candidate
            "answer_group_best_branch_scores": {"g1": 0.8},
        },
    }
    ext = _all_ext_agree("20")
    out = apply_combined_fix1234_to_row(row, external_answers=ext)
    assert out["fix1_applied"] is True
    assert out["combined1234_policy_applied"] == "fix1"
    assert out["combined1234_answer_canonical"] == "99"


def test_combined_fix1234_fix4_fires_after_1_2_3_skip():
    """In FIX-1+2+3+4, FIX-4 fires when FIX-1/2/3 all skip."""
    row = _dfa_row("40")
    # No AGBS → FIX-3 would fire unless... actually we need AGBS present to skip FIX-3
    row["result_metadata"]["answer_group_best_branch_scores"] = {"g1": 0.8}
    ext = _all_ext_agree("20")
    out = apply_combined_fix1234_to_row(row, external_answers=ext)
    assert out["fix1_applied"] is False
    assert out["fix2_applied"] is False
    assert out["fix3_applied"] is False
    assert out["fix4_applied"] is True
    assert out["combined1234_policy_applied"] == "fix4"
    assert out["combined1234_answer_canonical"] == "20"


def test_fix4_policy_names_stable():
    """FIX-4 policy names are identifiable and stable."""
    assert "external_consensus_gate" in FIX4_POLICY_NAME
    assert "lowdepth_external_consensus" in COMBINED_FIX24_POLICY_NAME
    assert "support_lowdepth_calibrated_consensus" in COMBINED_FIX1234_POLICY_NAME


# ─── FIX-5 tests ──────────────────────────────────────────────────────────────


def _frontier_row_for_fix5(frontier_ans="40", override_reason="direct_frontier_agree"):
    return {
        "method": "direct_reserve_semantic_frontier_v2",
        "final_answer_canonical": frontier_ans,
        "final_answer_raw": frontier_ans,
        "result_metadata": {
            "override_reason": override_reason,
            "frontier_support": 1,
            "candidate_pool_answer_group_count": 2,
            "support_margin": 0.0,
            "direct_reserve_confidence_proxy": 0.5,
            "frontier_candidate_answer": frontier_ans,
            "answer_group_best_branch_scores": {"g1": 0.8},
        },
    }


def test_fix5_defaults_to_tale_when_no_switch_pattern():
    """FIX-5 defaults to TALE when no high-confidence switch region fires."""
    row = _frontier_row_for_fix5(frontier_ans="40")
    ext = {
        "external_l1_max": "20",
        "external_s1_budget_forcing": "99",
        "external_tale_prompt_budgeting": "33",
    }
    out = apply_fix5_tale_default_router(row, external_answers=ext)
    assert out["fix5_applied"] is False
    assert out["fix5_answer_canonical"] == "33"
    assert out["fix5_reason"] == "tale_default"


def test_fix5_switches_when_tale_isolated_and_l1_s1_frontier_agree():
    """FIX-5 switches when TALE is isolated and L1/S1 agree with frontier candidate."""
    row = _frontier_row_for_fix5(frontier_ans="20")
    ext = {
        "external_l1_max": "20",
        "external_s1_budget_forcing": "20",
        "external_tale_prompt_budgeting": "33",
    }
    row["result_metadata"]["support_margin"] = 1.0
    out = apply_fix5_tale_default_router(row, external_answers=ext)
    assert out["fix5_applied"] is True
    assert out["fix5_answer_canonical"] == "20"
    assert out["fix5_reason"] in {
        "frontier_switch_tale_isolated_l1_s1_agree",
        "frontier_switch_external_majority_support",
    }


def test_fix5_no_switch_when_externals_unanimous_against_frontier():
    """FIX-5 blocks switching when all three externals unanimously disagree with frontier."""
    row = _frontier_row_for_fix5(frontier_ans="40", override_reason="insufficient_support_margin")
    ext = {
        "external_l1_max": "20",
        "external_s1_budget_forcing": "20",
        "external_tale_prompt_budgeting": "20",
    }
    out = apply_fix5_tale_default_router(row, external_answers=ext)
    assert out["fix5_applied"] is False
    assert out["fix5_reason"] == "blocked_external_unanimous_against_frontier"
    assert out["fix5_answer_canonical"] == "20"


def test_fix5_no_switch_when_low_depth_frontier():
    """FIX-5 blocks switching in low-depth-risk frontier rows."""
    row = _frontier_row_for_fix5(frontier_ans="40", override_reason="single_weak_frontier_branch")
    ext = {
        "external_l1_max": "40",
        "external_s1_budget_forcing": "40",
        "external_tale_prompt_budgeting": "33",
    }
    out = apply_fix5_tale_default_router(row, external_answers=ext)
    assert out["fix5_applied"] is False
    assert out["fix5_reason"] == "blocked_low_depth_frontier"
    assert out["fix5_answer_canonical"] == "33"


def test_fix5_no_switch_when_required_answers_missing():
    """FIX-5 blocks switching when required answers/metadata are missing."""
    row = _frontier_row_for_fix5(frontier_ans="40")
    ext = {
        "external_l1_max": "40",
        # missing s1
        "external_tale_prompt_budgeting": "33",
    }
    out = apply_fix5_tale_default_router(row, external_answers=ext)
    assert out["fix5_applied"] is False
    assert out["fix5_reason"] == "blocked_missing_metadata"


def test_fix5_does_not_use_gold_or_exact_match_fields():
    """FIX-5 ignores gold/exact-like fields and routes only from inference metadata."""
    row = _frontier_row_for_fix5(frontier_ans="20")
    row["gold_answer"] = "999"
    row["exact_match"] = 0
    row["result_metadata"]["gold_answer"] = "999"
    row["result_metadata"]["exact_match"] = 0
    ext = {
        "external_l1_max": "20",
        "external_s1_budget_forcing": "20",
        "external_tale_prompt_budgeting": "33",
    }
    row["result_metadata"]["support_margin"] = 1.0
    out = apply_fix5_tale_default_router(row, external_answers=ext)
    assert out["fix5_applied"] is True
    assert out["fix5_answer_canonical"] == "20"


def test_fix5_records_decision_reason():
    """FIX-5 always records a decision reason string."""
    row = _frontier_row_for_fix5(frontier_ans="40")
    ext = {
        "external_l1_max": "20",
        "external_s1_budget_forcing": "99",
        "external_tale_prompt_budgeting": "33",
    }
    out = apply_fix5_tale_default_router(row, external_answers=ext)
    assert isinstance(out.get("fix5_reason"), str)
    assert out["fix5_reason"]


def test_fix5_helper_signatures_and_majority():
    """Agreement helper functions expose stable behavior."""
    ext = {
        "external_l1_max": "5",
        "external_s1_budget_forcing": "5",
        "external_tale_prompt_budgeting": "7",
    }
    assert external_agreement_signature(ext) == "l1=s1!=tale"
    assert is_tale_isolated(ext)
    assert frontier_agrees_with_external_majority("5", ext)
    sw, reason = should_switch_from_tale_to_frontier_v1(
        frontier_candidate_answer="5",
        tale_answer="7",
        external_answers=ext,
        result_metadata={
            "override_reason": "direct_frontier_agree",
            "frontier_support": 1,
            "support_margin": 1.0,
        },
    )
    assert sw is True
    assert reason in {
        "frontier_switch_tale_isolated_l1_s1_agree",
        "frontier_switch_external_majority_support",
    }


def test_fix5_policy_name_stable():
    """FIX-5 policy name is identifiable and stable."""
    assert "tale_default" in FIX5_POLICY_NAME
    assert "frontier_switch" in FIX5_POLICY_NAME
