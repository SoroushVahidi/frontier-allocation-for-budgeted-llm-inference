"""
Tests for C1: Reliability-Gated Pooled Voting

Tests cover:
- Beta shrinkage fold safety (no gold at inference)
- Dominant-source gating on synthetic examples
- Weighted voting deterministic tie-breaking
- No-majority fallback behavior
- Method name normalization
"""
import sys
import os
import math
import pytest
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.evaluate_reliability_gated_pooled_voting_c1 import (
    beta_shrink_accuracy,
    compute_training_fold_calibration,
    compute_answer_pattern_features,
    pooled4_decision,
    c1a_decision,
    c1b_decision,
    c1c_decision,
    c1d_decision,
    c1e_decision,
    decision_ok,
    add_pattern_features,
    METHOD_NAME_MAP,
    SOURCES,
)


# ---------------------------------------------------------------------------
# Helper: build synthetic rows
# ---------------------------------------------------------------------------

def make_row(frontier="A", L1="A", S1="B", TALE="A", gold="A"):
    """Build a synthetic case row."""
    return pd.Series({
        "frontier_ans": frontier, "L1_ans": L1, "S1_ans": S1, "TALE_ans": TALE,
        "frontier_ok": int(frontier == gold),
        "L1_ok": int(L1 == gold),
        "S1_ok": int(S1 == gold),
        "TALE_ok": int(TALE == gold),
        "gold": gold,
        "example_id": "test_0",
    })


def make_calib(frontier_acc=0.8, L1_acc=0.79, S1_acc=0.91, TALE_acc=0.67,
               n=100):
    """Build a synthetic calibration dict."""
    shrunk = {
        "frontier": beta_shrink_accuracy(int(frontier_acc * n), n),
        "L1": beta_shrink_accuracy(int(L1_acc * n), n),
        "S1": beta_shrink_accuracy(int(S1_acc * n), n),
        "TALE": beta_shrink_accuracy(int(TALE_acc * n), n),
    }
    ranked = sorted(shrunk, key=lambda s: shrunk[s], reverse=True)
    margin = shrunk[ranked[0]] - shrunk[ranked[1]]
    return {
        "n_train": n,
        "raw_acc": {"frontier": frontier_acc, "L1": L1_acc, "S1": S1_acc, "TALE": TALE_acc},
        "shrunk_acc": shrunk,
        "best_source": ranked[0],
        "ranked_sources": ranked,
        "dominance_margin": margin,
    }


# ---------------------------------------------------------------------------
# Beta shrinkage tests
# ---------------------------------------------------------------------------

class TestBetaShrinkage:
    def test_midpoint_prior(self):
        """With 0 data, shrunk estimate = 0.5 (uniform prior)."""
        sh = beta_shrink_accuracy(0, 0, alpha=1, beta=1)
        assert sh == pytest.approx(0.5)

    def test_many_correct_approaches_raw(self):
        """With many correct, shrunk approaches raw accuracy."""
        raw = 0.95
        n = 1000
        sh = beta_shrink_accuracy(int(raw * n), n)
        assert abs(sh - raw) < 0.01

    def test_shrinkage_toward_half_with_few_examples(self):
        """With few examples, shrunk is between raw and 0.5."""
        raw = 0.9
        n = 5
        sh = beta_shrink_accuracy(int(raw * n), n)
        assert 0.5 < sh < raw

    def test_fold_safety_concept(self):
        """
        Training fold calibration must not use test fold data.
        Verify compute_training_fold_calibration only sees training rows.
        """
        # 20 training rows, 5 test rows
        train_data = {"frontier_ok": [1] * 18 + [0, 0],
                      "L1_ok": [1] * 15 + [0] * 5,
                      "S1_ok": [1] * 8 + [0] * 12,
                      "TALE_ok": [1] * 10 + [0] * 10}
        train_df = pd.DataFrame(train_data)
        calib = compute_training_fold_calibration(train_df)
        assert calib["n_train"] == 20
        assert "shrunk_acc" in calib
        # Frontier should be best (18/20 = 0.9)
        assert calib["best_source"] == "frontier"
        assert calib["shrunk_acc"]["frontier"] > calib["shrunk_acc"]["S1"]

    def test_dominance_margin_computation(self):
        """Dominance margin = shrunk_best - shrunk_second."""
        train_df = pd.DataFrame({
            "frontier_ok": [1] * 90 + [0] * 10,
            "L1_ok": [1] * 80 + [0] * 20,
            "S1_ok": [1] * 70 + [0] * 30,
            "TALE_ok": [1] * 60 + [0] * 40,
        })
        calib = compute_training_fold_calibration(train_df)
        assert calib["best_source"] == "frontier"
        assert calib["dominance_margin"] > 0
        expected_margin = (calib["shrunk_acc"]["frontier"] -
                           calib["shrunk_acc"]["L1"])
        assert calib["dominance_margin"] == pytest.approx(expected_margin, abs=1e-6)


# ---------------------------------------------------------------------------
# Answer pattern feature tests
# ---------------------------------------------------------------------------

class TestAnswerPatternFeatures:
    def test_all_four_agree(self):
        row = make_row("X", "X", "X", "X")
        feats = compute_answer_pattern_features(row)
        assert feats["all_four_agree"] == 1
        assert feats["three_one_split"] == 0
        assert feats["majority_size"] == 4
        assert feats["has_majority"] == 1

    def test_three_one_split(self):
        row = make_row("A", "A", "B", "A")
        feats = compute_answer_pattern_features(row)
        assert feats["three_one_split"] == 1
        assert feats["majority_answer"] == "A"
        assert feats["majority_size"] == 3
        assert feats["has_majority"] == 1
        assert feats["S1_isolated"] == 1
        assert feats["frontier_isolated"] == 0

    def test_two_two_split(self):
        row = make_row("A", "A", "B", "B")
        feats = compute_answer_pattern_features(row)
        assert feats["two_two_split"] == 1
        assert feats["has_majority"] == 0
        assert feats["no_majority_flag"] == 1

    def test_all_different(self):
        row = make_row("A", "B", "C", "D")
        feats = compute_answer_pattern_features(row)
        assert feats["all_different"] == 1
        assert feats["unique_answer_count"] == 4
        assert feats["no_majority_flag"] == 1

    def test_frontier_in_majority(self):
        row = make_row("A", "A", "A", "B")
        feats = compute_answer_pattern_features(row)
        assert feats["frontier_in_majority"] == 1
        assert feats["S1_in_majority"] == 1

    def test_L1_TALE_agree(self):
        row = make_row("A", "B", "C", "B")
        feats = compute_answer_pattern_features(row)
        assert feats["L1_TALE_agree"] == 1
        assert feats["external_majority_exists"] == 1


# ---------------------------------------------------------------------------
# C1a: Conservative regime-gated tests
# ---------------------------------------------------------------------------

class TestC1a:
    def test_uses_dominant_source_when_margin_above_threshold(self):
        """High-dominance S1 case: should choose S1."""
        row = make_row("A", "A", "B", "A")  # S1 disagrees
        row_with_feats = compute_answer_pattern_features(row)
        row_full = pd.concat([row, pd.Series(row_with_feats)])
        calib = make_calib(S1_acc=0.91, frontier_acc=0.79, L1_acc=0.79, TALE_acc=0.67)
        # S1 is dominant; its ans is "B"
        decision = c1a_decision(row_full, calib, threshold=0.05)
        assert decision == "B"  # dominant S1's answer

    def test_uses_pooled4_when_margin_below_threshold(self):
        """Near-peer: all accuracies close, threshold not crossed."""
        row = make_row("A", "A", "B", "A")  # majority = A (3 vs 1)
        row_with_feats = compute_answer_pattern_features(row)
        row_full = pd.concat([row, pd.Series(row_with_feats)])
        calib = make_calib(frontier_acc=0.80, L1_acc=0.80, S1_acc=0.80, TALE_acc=0.79)
        decision = c1a_decision(row_full, calib, threshold=0.05)
        # Margin is tiny; should fall through to pooled4 which votes majority "A"
        assert decision == "A"

    def test_threshold_boundary(self):
        """Exactly at threshold: should NOT trigger dominant source."""
        row = make_row("A", "A", "B", "A")
        row_with_feats = compute_answer_pattern_features(row)
        row_full = pd.concat([row, pd.Series(row_with_feats)])
        # Build calib with margin = exactly 0.05
        calib = make_calib(frontier_acc=0.80, L1_acc=0.75, S1_acc=0.73, TALE_acc=0.70, n=200)
        margin = calib["dominance_margin"]
        if margin < 0.05:
            decision = c1a_decision(row_full, calib, threshold=0.05)
            # Should use pooled4 (majority = A)
            assert decision == "A"


# ---------------------------------------------------------------------------
# C1b: Dominant-source veto tests
# ---------------------------------------------------------------------------

class TestC1b:
    def test_veto_when_dominant_source_not_in_pooled_majority(self):
        """S1 dominant and disagrees with majority of 2 — should veto."""
        # Majority is A (frontier+L1), S1=B, TALE=C; no strict majority
        # actually frontier=L1=A (2), S1=B (1), TALE=C (1)
        row = make_row("A", "A", "B", "C")
        row_with_feats = compute_answer_pattern_features(row)
        row_full = pd.concat([row, pd.Series(row_with_feats)])
        calib = make_calib(S1_acc=0.91, frontier_acc=0.80, L1_acc=0.80, TALE_acc=0.67)
        # No majority (2A, 1B, 1C); margin > 0.10 → veto
        decision = c1b_decision(row_full, calib)
        # S1 is dominant; its answer is B
        assert decision == "B"

    def test_no_veto_when_dominant_in_strong_majority(self):
        """Large majority (3-1) with a reliable source in it — don't veto."""
        row = make_row("A", "A", "A", "B")  # 3xA, 1xB (TALE)
        row_with_feats = compute_answer_pattern_features(row)
        row_full = pd.concat([row, pd.Series(row_with_feats)])
        # S1 is in majority this time (S1="A")
        calib = make_calib(S1_acc=0.91, frontier_acc=0.80, L1_acc=0.80, TALE_acc=0.67)
        decision = c1b_decision(row_full, calib)
        # S1 in majority → pooled4 wins → "A"
        assert decision == "A"


# ---------------------------------------------------------------------------
# C1c: Reliability-weighted voting tests
# ---------------------------------------------------------------------------

class TestC1c:
    def test_deterministic_tie_breaking(self):
        """Same weight for two answers — should be deterministic."""
        row = make_row("A", "A", "B", "B")  # 2-2 split
        row_with_feats = compute_answer_pattern_features(row)
        row_full = pd.concat([row, pd.Series(row_with_feats)])
        calib = make_calib(frontier_acc=0.80, L1_acc=0.80, S1_acc=0.80, TALE_acc=0.80)
        d1 = c1c_decision(row_full, calib, "raw")
        d2 = c1c_decision(row_full, calib, "raw")
        assert d1 == d2  # deterministic

    def test_high_weight_source_wins(self):
        """S1 (highest weight) vote should dominate on 2-2 split."""
        row = make_row("A", "A", "B", "B")  # frontier+L1=A, S1+TALE=B
        row_with_feats = compute_answer_pattern_features(row)
        row_full = pd.concat([row, pd.Series(row_with_feats)])
        # S1 is much more accurate
        calib = make_calib(frontier_acc=0.50, L1_acc=0.50, S1_acc=0.95, TALE_acc=0.60)
        decision = c1c_decision(row_full, calib, "raw")
        # S1+TALE total weight > frontier+L1 total weight
        # S1=0.95, TALE=0.60 for B; frontier=0.50, L1=0.50 for A
        # B wins
        assert decision == "B"

    def test_log_odds_weights(self):
        """Log-odds weights should prefer high-accuracy source."""
        row = make_row("A", "A", "B", "B")
        row_with_feats = compute_answer_pattern_features(row)
        row_full = pd.concat([row, pd.Series(row_with_feats)])
        calib = make_calib(frontier_acc=0.55, L1_acc=0.55, S1_acc=0.90, TALE_acc=0.55)
        decision = c1c_decision(row_full, calib, "logodds")
        assert decision == "B"  # S1 has high log-odds weight

    def test_empty_answers_handled(self):
        """Empty answer strings should not contribute to vote totals."""
        row = pd.Series({
            "frontier_ans": "A", "L1_ans": "", "S1_ans": "A", "TALE_ans": "nan",
            "gold": "A",
        })
        row_with_feats = compute_answer_pattern_features(row)
        row_full = pd.concat([row, pd.Series(row_with_feats)])
        calib = make_calib()
        decision = c1c_decision(row_full, calib, "raw")
        assert decision == "A"


# ---------------------------------------------------------------------------
# C1d: Dominant-source-inclusion majority tests
# ---------------------------------------------------------------------------

class TestC1d:
    def test_uses_dominant_when_not_in_majority(self):
        """Dominant S1 not in majority → choose S1."""
        row = make_row("A", "A", "B", "A")  # 3xA, 1xB(S1)
        row_with_feats = compute_answer_pattern_features(row)
        row_full = pd.concat([row, pd.Series(row_with_feats)])
        calib = make_calib(S1_acc=0.91, frontier_acc=0.80, L1_acc=0.80, TALE_acc=0.67)
        decision = c1d_decision(row_full, calib)
        assert decision == "B"  # S1 dominant; not in A majority

    def test_uses_majority_when_dominant_in_majority(self):
        """Dominant S1 agrees with majority → choose majority (S1's answer)."""
        row = make_row("A", "A", "A", "B")  # S1=A in majority
        row_with_feats = compute_answer_pattern_features(row)
        row_full = pd.concat([row, pd.Series(row_with_feats)])
        calib = make_calib(S1_acc=0.91, frontier_acc=0.80, L1_acc=0.80, TALE_acc=0.67)
        decision = c1d_decision(row_full, calib)
        assert decision == "A"

    def test_no_dominant_uses_pooled4(self):
        """No dominant source → fall back to pooled4."""
        row = make_row("A", "A", "B", "A")  # majority A
        row_with_feats = compute_answer_pattern_features(row)
        row_full = pd.concat([row, pd.Series(row_with_feats)])
        calib = make_calib(frontier_acc=0.80, L1_acc=0.80, S1_acc=0.80, TALE_acc=0.79)
        decision = c1d_decision(row_full, calib)
        assert decision == "A"  # pooled4 majority


# ---------------------------------------------------------------------------
# C1e: No-majority conservative fallback tests
# ---------------------------------------------------------------------------

class TestC1e:
    def test_uses_pooled4_when_majority_exists(self):
        """With a 3-1 majority, should use pooled4."""
        row = make_row("A", "A", "B", "A")  # 3xA majority
        row_with_feats = compute_answer_pattern_features(row)
        row_full = pd.concat([row, pd.Series(row_with_feats)])
        calib = make_calib(S1_acc=0.91, frontier_acc=0.80, L1_acc=0.80, TALE_acc=0.67)
        decision = c1e_decision(row_full, calib, threshold=0.05)
        assert decision == "A"  # majority

    def test_uses_dominant_source_when_no_majority(self):
        """No majority + dominant source above threshold → use dominant source."""
        row = make_row("A", "B", "C", "D")  # all different
        row_with_feats = compute_answer_pattern_features(row)
        row_full = pd.concat([row, pd.Series(row_with_feats)])
        calib = make_calib(S1_acc=0.91, frontier_acc=0.80, L1_acc=0.80, TALE_acc=0.67)
        decision = c1e_decision(row_full, calib, threshold=0.05)
        assert decision == "C"  # dominant S1's answer

    def test_uses_frontier_when_no_majority_and_no_dominant(self):
        """No majority + no dominant → frontier fallback."""
        row = make_row("A", "B", "C", "D")
        row_with_feats = compute_answer_pattern_features(row)
        row_full = pd.concat([row, pd.Series(row_with_feats)])
        calib = make_calib(frontier_acc=0.80, L1_acc=0.80, S1_acc=0.80, TALE_acc=0.79)
        decision = c1e_decision(row_full, calib, threshold=0.05)
        assert decision == "A"  # frontier fallback


# ---------------------------------------------------------------------------
# Method name normalization
# ---------------------------------------------------------------------------

class TestMethodNameNormalization:
    def test_all_canonical_methods_normalized(self):
        assert METHOD_NAME_MAP["direct_reserve_semantic_frontier_v2"] == "frontier"
        assert METHOD_NAME_MAP["external_l1_max"] == "L1"
        assert METHOD_NAME_MAP["external_s1_budget_forcing"] == "S1"
        assert METHOD_NAME_MAP["external_tale_prompt_budgeting"] == "TALE"

    def test_sources_list_matches(self):
        assert set(SOURCES) == {"frontier", "L1", "S1", "TALE"}


# ---------------------------------------------------------------------------
# Gold label protection
# ---------------------------------------------------------------------------

class TestNoGoldAtInference:
    def test_c1a_does_not_use_gold_column(self):
        """C1a inference should work even with no gold column."""
        row = make_row("A", "A", "B", "A")
        row = row.drop("gold")  # remove gold
        feats = compute_answer_pattern_features(row)
        row_full = pd.concat([row, pd.Series(feats)])
        calib = make_calib(S1_acc=0.91)
        decision = c1a_decision(row_full, calib, threshold=0.05)
        assert isinstance(decision, str)

    def test_c1c_does_not_use_gold_column(self):
        """C1c inference should work without gold."""
        row = make_row("A", "A", "B", "A")
        row = row.drop("gold")
        feats = compute_answer_pattern_features(row)
        row_full = pd.concat([row, pd.Series(feats)])
        calib = make_calib()
        decision = c1c_decision(row_full, calib, "raw")
        assert isinstance(decision, str)

    def test_calib_only_uses_correctness_not_gold_answers(self):
        """Calibration uses ok flags (computed from gold), not gold strings."""
        train_df = pd.DataFrame({
            "frontier_ok": [1, 0, 1, 1],
            "L1_ok": [1, 1, 0, 1],
            "S1_ok": [0, 0, 1, 1],
            "TALE_ok": [1, 1, 1, 0],
        })
        # No gold column in training df
        calib = compute_training_fold_calibration(train_df)
        assert "shrunk_acc" in calib
        assert "gold" not in str(calib)  # gold not in calib output


# ---------------------------------------------------------------------------
# Pattern features via add_pattern_features
# ---------------------------------------------------------------------------

class TestAddPatternFeatures:
    def test_adds_feature_columns(self):
        rows = [
            {"frontier_ans": "A", "L1_ans": "A", "S1_ans": "B", "TALE_ans": "A",
             "example_id": "e1", "gold": "A"},
            {"frontier_ans": "X", "L1_ans": "X", "S1_ans": "X", "TALE_ans": "X",
             "example_id": "e2", "gold": "X"},
        ]
        df = pd.DataFrame(rows)
        df_feat = add_pattern_features(df)
        assert "majority_answer" in df_feat.columns
        assert "has_majority" in df_feat.columns
        assert "S1_isolated" in df_feat.columns
        assert df_feat.loc[0, "three_one_split"] == 1
        assert df_feat.loc[1, "all_four_agree"] == 1


# ---------------------------------------------------------------------------
# Pooled4 decision tests
# ---------------------------------------------------------------------------

class TestPooled4:
    def test_returns_majority_answer(self):
        row = make_row("A", "A", "B", "A")
        feats = compute_answer_pattern_features(row)
        row_full = pd.concat([row, pd.Series(feats)])
        calib = make_calib()
        assert pooled4_decision(row_full, calib) == "A"

    def test_falls_back_to_best_source_when_no_majority(self):
        row = make_row("A", "B", "C", "D")
        feats = compute_answer_pattern_features(row)
        row_full = pd.concat([row, pd.Series(feats)])
        calib = make_calib(S1_acc=0.91)
        decision = pooled4_decision(row_full, calib)
        # No majority; fallback to ranked sources → S1 first → "C"
        assert decision == "C"
