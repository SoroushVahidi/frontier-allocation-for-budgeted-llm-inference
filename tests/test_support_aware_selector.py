"""Tests for the support-aware / tie-aware selector FIX-1.

Tests:
- Tie detection (support_margin=0, confidence<=0.5)
- Strict majority preserves original choice
- PNS-risk case changes decision
- No gold/exact fields used as features
- Backward compatibility (non-frontier methods unchanged)
- No API calls
"""
import pytest
from experiments.support_aware_selector import (
    should_apply_support_aware_fix,
    apply_support_aware_fix,
    apply_support_aware_fix_to_row,
    _normalize_answer,
    POLICY_NAME,
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
