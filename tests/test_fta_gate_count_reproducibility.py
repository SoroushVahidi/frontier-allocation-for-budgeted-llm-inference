"""Tests for FTA / FIX-2+FIX-4 gate-count and no-leakage guarantees.

These tests do not require the full 300-row validation dataset. They use a
small synthetic fixture that exercises the three gate outcomes:
  - FIX-2 fires (SWFB row → external majority substitution)
  - FIX-4 fires (direct_frontier_agree + all-3 externals unanimous)
  - No gate (normal row, no trigger condition met)

They verify:
  1. Gate counts add up to total row count.
  2. gate/selection logic uses no gold_answer or exact_match fields.
  3. Applying FTA twice (idempotency) produces the same answer.
  4. `experiments/fta_policy.py` public names are importable and consistent.
"""

from __future__ import annotations

import pytest
from experiments.support_aware_selector import apply_combined_fix24_to_row
from experiments.fta_policy import (
    apply_fta_to_row,
    fta_fix2_trigger,
    fta_fix4_trigger,
    FTA_POLICY_NAME,
)


# ─── Fixture builders ────────────────────────────────────────────────────────

def _swfb_row(frontier_ans: str = "99") -> dict:
    """Row that should trigger FIX-2 (single_weak_frontier_branch)."""
    return {
        "method": "direct_reserve_semantic_frontier_v2",
        "final_answer_canonical": frontier_ans,
        "final_answer_raw": frontier_ans,
        "result_metadata": {"override_reason": "single_weak_frontier_branch"},
    }


def _dfa_row(frontier_ans: str = "40") -> dict:
    """Row that may trigger FIX-4 (direct_frontier_agree, no SWFB)."""
    return {
        "method": "direct_reserve_semantic_frontier_v2",
        "final_answer_canonical": frontier_ans,
        "final_answer_raw": frontier_ans,
        "result_metadata": {
            "override_reason": "direct_frontier_agree",
            "frontier_support": 2,
            "candidate_pool_answer_group_count": 2,
        },
    }


def _normal_row(frontier_ans: str = "7") -> dict:
    """Normal row: strong majority, no trigger conditions met."""
    return {
        "method": "direct_reserve_semantic_frontier_v2",
        "final_answer_canonical": frontier_ans,
        "final_answer_raw": frontier_ans,
        "result_metadata": {
            "override_reason": "direct_frontier_agree",
            "frontier_support": 3,
            "candidate_pool_answer_group_count": 2,
        },
    }


def _all_ext(ans: str) -> dict:
    return {
        "external_l1_max": ans,
        "external_s1_budget_forcing": ans,
        "external_tale_prompt_budgeting": ans,
    }


# ─── Gate-count reproducibility ──────────────────────────────────────────────

class TestGateCountReproducibility:
    """Mini-fixture: 5 rows covering all three gate outcomes."""

    def _build_batch(self):
        rows = [
            ("fix2", _swfb_row("99"), _all_ext("42")),   # FIX-2 fires
            ("fix2", _swfb_row("55"), _all_ext("42")),   # FIX-2 fires (second)
            ("fix4", _dfa_row("40"), _all_ext("20")),    # FIX-4 fires
            ("none", _normal_row("7"), _all_ext("7")),   # no gate (external agrees with frontier)
            ("none", _normal_row("7"), {"external_l1_max": "1", "external_s1_budget_forcing": "2", "external_tale_prompt_budgeting": "3"}),
        ]
        return rows

    def test_gate_counts_sum_to_row_count(self):
        batch = self._build_batch()
        fix2_count = fix4_count = none_count = 0
        for _, row, ext in batch:
            out = apply_combined_fix24_to_row(row, external_answers=ext)
            if out["fix2_applied"]:
                fix2_count += 1
            elif out["fix4_applied"]:
                fix4_count += 1
            else:
                none_count += 1
        assert fix2_count + fix4_count + none_count == len(batch)

    def test_fix2_fires_expected_count(self):
        batch = self._build_batch()
        fix2_count = sum(
            1 for _, row, ext in batch
            if apply_combined_fix24_to_row(row, external_answers=ext)["fix2_applied"]
        )
        assert fix2_count == 2  # two SWFB rows

    def test_fix4_fires_expected_count(self):
        batch = self._build_batch()
        fix4_count = sum(
            1 for _, row, ext in batch
            if apply_combined_fix24_to_row(row, external_answers=ext)["fix4_applied"]
        )
        assert fix4_count == 1  # one unanimous-external-against-frontier row

    def test_fix2_and_fix4_never_both_fire(self):
        batch = self._build_batch()
        for _, row, ext in batch:
            out = apply_combined_fix24_to_row(row, external_answers=ext)
            assert not (out["fix2_applied"] and out["fix4_applied"]), (
                "FIX-2 and FIX-4 must never both fire on the same row"
            )


# ─── No gold / no exact-match leakage ────────────────────────────────────────

class TestNoGoldLeakage:
    def test_fix2_trigger_ignores_gold_fields(self):
        rm = {"override_reason": "single_weak_frontier_branch", "gold_answer": "42", "exact_match": 1}
        assert fta_fix2_trigger(rm)  # still fires based on override_reason, not gold

    def test_fix4_trigger_ignores_gold_fields(self):
        row = _dfa_row("40")
        row["result_metadata"]["gold_answer"] = "20"
        row["result_metadata"]["exact_match"] = 0
        ext = _all_ext("20")
        out = apply_combined_fix24_to_row(row, external_answers=ext)
        assert out["fix4_applied"] is True  # fired on inference features, not gold

    def test_output_does_not_expose_gold_fields(self):
        row = _swfb_row("99")
        ext = _all_ext("42")
        out = apply_combined_fix24_to_row(row, external_answers=ext)
        assert "gold_answer" not in out
        assert "exact_match" not in out


# ─── Idempotency ─────────────────────────────────────────────────────────────

class TestIdempotency:
    def test_applying_fta_twice_is_idempotent(self):
        """After FTA fires once, re-applying on the updated answer is safe."""
        row = _swfb_row("99")
        ext = _all_ext("42")
        out1 = apply_combined_fix24_to_row(row, external_answers=ext)
        # Simulate re-applying on the post-FTA answer
        row2 = dict(row)
        row2["final_answer_canonical"] = out1["combined24_answer_canonical"]
        out2 = apply_combined_fix24_to_row(row2, external_answers=ext)
        assert out2["combined24_answer_canonical"] == out1["combined24_answer_canonical"]


# ─── fta_policy.py public API ────────────────────────────────────────────────

class TestFtaPolicyModule:
    def test_apply_fta_to_row_matches_direct(self):
        row = _dfa_row("40")
        ext = _all_ext("20")
        direct = apply_combined_fix24_to_row(row, external_answers=ext)
        via_policy = apply_fta_to_row(row, external_answers=ext)
        assert direct == via_policy

    def test_fta_policy_name_is_stable(self):
        assert "lowdepth" in FTA_POLICY_NAME.lower() or "fix2" in FTA_POLICY_NAME.lower()
        assert "consensus" in FTA_POLICY_NAME.lower() or "fix4" in FTA_POLICY_NAME.lower()

    def test_fta_fix2_trigger_exported(self):
        rm = {"override_reason": "single_weak_frontier_branch"}
        assert fta_fix2_trigger(rm) is True

    def test_fta_fix4_trigger_exported(self):
        row = _dfa_row("40")
        ext = _all_ext("20")
        assert fta_fix4_trigger(
            frontier_answer="40",
            external_answers=ext,
            result_metadata=row["result_metadata"],
        ) is True
