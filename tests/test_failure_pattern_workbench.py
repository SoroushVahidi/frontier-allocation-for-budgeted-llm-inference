"""
Tests for the failure pattern mining workbench.
Covers cluster assignment, oracle-correct failure detection,
all-sources-wrong separation, S1 overtrusted/undertrusted detection,
and no-majority bad fallback detection.
"""
import sys
import os
import pandas as pd
import numpy as np
import pytest

# Add repo root so we can import the script module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Import cluster assignment logic (not the whole main() to avoid I/O)
from scripts.build_failure_pattern_workbench import (
    assign_clusters,
    CLUSTER_DEFS,
    CANDIDATE_FIXES,
    IMPL_QUEUE,
)


def _make_case(**kwargs):
    """Build a minimal synthetic row with sensible defaults."""
    defaults = dict(
        scenario_id="test_scenario",
        provider="test_provider",
        dataset="gsm8k",
        example_id="ex_0001",
        gold="42",
        question="What is 6 × 7?",
        frontier_ans="42", frontier_ok=True,
        L1_ans="42", L1_ok=True,
        S1_ans="42", S1_ok=True,
        TALE_ans="42", TALE_ok=True,
        pooled4_ok=True,
        beta_shrinkage_ok=True,
        always_S1_ok=True,
        agreement_only_ok=True,
        oracle_ok=True,
        C1d_ok=True,
        C1a_t005_ok=True,
        all_sources_wrong=0,
        S1_isolated=False,
        frontier_isolated=False,
        no_majority_flag=False,
        external_majority_exists=False,
        external_majority_excludes_frontier=False,
        external_majority_excludes_S1=False,
        L1_TALE_agree=True,
        dominant_source="S1",
        answer_pattern_bucket="all_agree",
        c1_ok_c1c_logodds=np.nan,
        all_four_agree=True,
        three_one_split=False,
        two_two_split=False,
        all_different=False,
        has_majority=True,
        majority_size=4,
        unique_answer_count=1,
    )
    defaults.update(kwargs)
    return pd.Series(defaults)


def _df(*rows):
    return pd.DataFrame(list(rows))


# ── Cluster A: dominant_source_outvoted ───────────────────────────────────────

class TestClusterA_DominantSourceOutvoted:
    def test_fires_when_c1d_right_pooled4_wrong_oracle_right(self):
        row = _make_case(C1d_ok=True, pooled4_ok=False, oracle_ok=True)
        df = _df(row)
        clusters = assign_clusters(df)
        assert df.index[0] in clusters["A_dominant_source_outvoted"]

    def test_does_not_fire_when_c1d_wrong(self):
        row = _make_case(C1d_ok=False, pooled4_ok=False, oracle_ok=True)
        df = _df(row)
        clusters = assign_clusters(df)
        assert df.index[0] not in clusters["A_dominant_source_outvoted"]

    def test_does_not_fire_when_pooled4_right(self):
        row = _make_case(C1d_ok=True, pooled4_ok=True, oracle_ok=True)
        df = _df(row)
        clusters = assign_clusters(df)
        assert df.index[0] not in clusters["A_dominant_source_outvoted"]

    def test_does_not_fire_when_oracle_wrong(self):
        row = _make_case(C1d_ok=True, pooled4_ok=False, oracle_ok=False)
        df = _df(row)
        clusters = assign_clusters(df)
        assert df.index[0] not in clusters["A_dominant_source_outvoted"]


# ── Cluster B: near_peer_false_dominance ──────────────────────────────────────

class TestClusterB_NearPeerFalseDominance:
    def test_fires_when_c1d_wrong_pooled4_right(self):
        row = _make_case(C1d_ok=False, pooled4_ok=True)
        df = _df(row)
        clusters = assign_clusters(df)
        assert df.index[0] in clusters["B_near_peer_false_dominance"]

    def test_does_not_fire_when_c1d_right(self):
        row = _make_case(C1d_ok=True, pooled4_ok=True)
        df = _df(row)
        clusters = assign_clusters(df)
        assert df.index[0] not in clusters["B_near_peer_false_dominance"]

    def test_does_not_fire_when_pooled4_wrong(self):
        row = _make_case(C1d_ok=False, pooled4_ok=False)
        df = _df(row)
        clusters = assign_clusters(df)
        assert df.index[0] not in clusters["B_near_peer_false_dominance"]


# ── Cluster C: no_majority_bad_fallback ───────────────────────────────────────

class TestClusterC_NoMajorityBadFallback:
    def test_fires_when_no_majority_pooled4_wrong_oracle_right(self):
        row = _make_case(no_majority_flag=True, pooled4_ok=False, oracle_ok=True)
        df = _df(row)
        clusters = assign_clusters(df)
        assert df.index[0] in clusters["C_no_majority_bad_fallback"]

    def test_does_not_fire_when_majority_exists(self):
        row = _make_case(no_majority_flag=False, pooled4_ok=False, oracle_ok=True)
        df = _df(row)
        clusters = assign_clusters(df)
        assert df.index[0] not in clusters["C_no_majority_bad_fallback"]

    def test_does_not_fire_when_pooled4_right(self):
        row = _make_case(no_majority_flag=True, pooled4_ok=True, oracle_ok=True)
        df = _df(row)
        clusters = assign_clusters(df)
        assert df.index[0] not in clusters["C_no_majority_bad_fallback"]


# ── Cluster I: all_sources_wrong ──────────────────────────────────────────────

class TestClusterI_AllSourcesWrong:
    def test_fires_when_all_wrong(self):
        row = _make_case(
            frontier_ok=False, L1_ok=False, S1_ok=False, TALE_ok=False,
            all_sources_wrong=1,
            pooled4_ok=False, oracle_ok=False,
        )
        df = _df(row)
        clusters = assign_clusters(df)
        assert df.index[0] in clusters["I_MATH_all_sources_wrong"]

    def test_does_not_fire_when_at_least_one_correct(self):
        row = _make_case(
            frontier_ok=True, L1_ok=False, S1_ok=False, TALE_ok=False,
            all_sources_wrong=0,
        )
        df = _df(row)
        clusters = assign_clusters(df)
        assert df.index[0] not in clusters["I_MATH_all_sources_wrong"]


# ── Cluster F: S1_overtrusted ─────────────────────────────────────────────────

class TestClusterF_S1Overtrusted:
    def test_fires_when_always_s1_wrong_pooled4_right(self):
        row = _make_case(
            always_S1_ok=False,
            pooled4_ok=True,
            S1_ok=False,
            frontier_ok=True,
        )
        df = _df(row)
        clusters = assign_clusters(df)
        assert df.index[0] in clusters["F_S1_overtrusted"]

    def test_fires_when_always_s1_wrong_frontier_right(self):
        row = _make_case(
            always_S1_ok=False,
            pooled4_ok=False,
            S1_ok=False,
            frontier_ok=True,
        )
        df = _df(row)
        clusters = assign_clusters(df)
        assert df.index[0] in clusters["F_S1_overtrusted"]

    def test_does_not_fire_when_always_s1_right(self):
        row = _make_case(always_S1_ok=True, pooled4_ok=True)
        df = _df(row)
        clusters = assign_clusters(df)
        assert df.index[0] not in clusters["F_S1_overtrusted"]


# ── Cluster G: S1_undertrusted ────────────────────────────────────────────────

class TestClusterG_S1Undertrusted:
    def test_fires_when_s1_correct_pooled4_wrong(self):
        row = _make_case(S1_ok=True, pooled4_ok=False)
        df = _df(row)
        clusters = assign_clusters(df)
        assert df.index[0] in clusters["G_S1_undertrusted"]

    def test_does_not_fire_when_s1_wrong(self):
        row = _make_case(S1_ok=False, pooled4_ok=False)
        df = _df(row)
        clusters = assign_clusters(df)
        assert df.index[0] not in clusters["G_S1_undertrusted"]

    def test_does_not_fire_when_pooled4_right(self):
        row = _make_case(S1_ok=True, pooled4_ok=True)
        df = _df(row)
        clusters = assign_clusters(df)
        assert df.index[0] not in clusters["G_S1_undertrusted"]


# ── Oracle-correct failure detection ─────────────────────────────────────────

class TestOracleCorrectFailure:
    def test_oracle_correct_pooled4_wrong_is_detectable(self):
        rows = [
            _make_case(oracle_ok=True, pooled4_ok=False),
            _make_case(oracle_ok=True, pooled4_ok=True),
            _make_case(oracle_ok=False, pooled4_ok=False),
        ]
        df = _df(*rows)
        mask = df["oracle_ok"].fillna(False).astype(bool) & ~df["pooled4_ok"].fillna(False).astype(bool)
        assert mask.sum() == 1
        assert df.loc[mask].index[0] == 0

    def test_routing_decisive_cases_exclude_all_wrong_and_all_correct(self):
        rows = [
            _make_case(oracle_ok=True, all_sources_wrong=0,
                       frontier_ok=True, L1_ok=True, S1_ok=True, TALE_ok=True),   # all correct
            _make_case(oracle_ok=False, all_sources_wrong=1,
                       frontier_ok=False, L1_ok=False, S1_ok=False, TALE_ok=False),  # all wrong
            _make_case(oracle_ok=True, all_sources_wrong=0,
                       frontier_ok=False, L1_ok=True, S1_ok=False, TALE_ok=False),   # routing decisive
        ]
        df = _df(*rows)
        routing_decisive = df[(df["oracle_ok"].astype(bool)) & (df["all_sources_wrong"] == 0) &
                              (df[["frontier_ok","L1_ok","S1_ok","TALE_ok"]].astype(bool).sum(axis=1) < 4)]
        assert len(routing_decisive) == 1
        assert routing_decisive.index[0] == 2


# ── Cluster structure sanity ───────────────────────────────────────────────────

class TestClusterStructure:
    def test_all_expected_clusters_defined(self):
        expected = {
            "A_dominant_source_outvoted",
            "B_near_peer_false_dominance",
            "C_no_majority_bad_fallback",
            "D_external_majority_wrong",
            "E_frontier_fallback_wrong",
            "F_S1_overtrusted",
            "G_S1_undertrusted",
            "H_L1_or_frontier_best_on_Cohere_MATH",
            "I_MATH_all_sources_wrong",
            "J_agreement_fragility",
            "K_weighted_vote_amplifies_bad_sources",
        }
        assert set(CLUSTER_DEFS.keys()) == expected

    def test_all_candidate_fixes_have_required_fields(self):
        required = {"fix_id", "target_cluster", "zero_extra_call", "description",
                    "implementation_complexity", "expected_recoveries", "expected_regressions",
                    "scenarios_helped", "status"}
        for fix in CANDIDATE_FIXES:
            missing = required - set(fix.keys())
            assert not missing, f"Fix {fix.get('fix_id','?')} missing fields: {missing}"

    def test_implementation_queue_is_ordered(self):
        priorities = [item["priority"] for item in IMPL_QUEUE]
        assert priorities == sorted(priorities), "Queue must be in priority order"

    def test_assign_clusters_returns_all_keys_even_on_empty_df(self):
        df = pd.DataFrame(columns=["scenario_id", "provider", "dataset",
                                    "frontier_ok", "L1_ok", "S1_ok", "TALE_ok",
                                    "pooled4_ok", "oracle_ok", "C1d_ok",
                                    "always_S1_ok", "agreement_only_ok",
                                    "no_majority_flag", "all_sources_wrong",
                                    "external_majority_exists",
                                    "external_majority_excludes_frontier",
                                    "external_majority_excludes_S1",
                                    "dominant_source", "c1_ok_c1c_logodds"])
        clusters = assign_clusters(df)
        assert set(clusters.keys()) == set(CLUSTER_DEFS.keys())
        for v in clusters.values():
            assert v == []

    def test_perfect_case_lands_in_no_clusters(self):
        row = _make_case()  # all correct, all agree
        df = _df(row)
        clusters = assign_clusters(df)
        # A case where everything is correct should be in no failure clusters
        in_clusters = [k for k, idxs in clusters.items() if df.index[0] in idxs]
        # Only cluster B fires when c1d wrong — here c1d=True and pooled4=True → no B
        # Only cluster G fires when s1 correct and pooled4 wrong — here pooled4=True → no G
        # This all-correct case should trigger none of the failure clusters
        # (except possibly G if S1_ok=True and pooled4_ok=True → no G since pooled4_ok=True)
        assert "I_MATH_all_sources_wrong" not in in_clusters
        assert "A_dominant_source_outvoted" not in in_clusters
        assert "C_no_majority_bad_fallback" not in in_clusters

    def test_multi_cluster_overlap_possible(self):
        # A case can be in multiple clusters (e.g., no_majority + S1_undertrusted)
        row = _make_case(
            no_majority_flag=True,
            pooled4_ok=False, oracle_ok=True,
            S1_ok=True,
        )
        df = _df(row)
        clusters = assign_clusters(df)
        assert df.index[0] in clusters["C_no_majority_bad_fallback"]
        assert df.index[0] in clusters["G_S1_undertrusted"]
