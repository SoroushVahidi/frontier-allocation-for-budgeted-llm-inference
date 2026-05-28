"""
Tests for router_v2_improvement_campaign (2026-05-24)

Tests cover:
- Expanded features are legal (no leaky columns)
- Leaky names rejected by auditor
- Fold-safe calibration feature construction
- Official-only headline excludes auxiliary rows
- No train/test overlap
- Deterministic outputs
- Model outputs valid binary actions
- Output artifact integrity
"""

import sys
import math
import numpy as np
import pandas as pd
import pytest
from pathlib import Path

REPO = Path("/home/soroush/frontier-allocation-for-budgeted-llm-inference")
OUT = REPO / "outputs" / "router_v2_improvement_campaign_20260524"

sys.path.insert(0, str(REPO / "scripts"))
from router_v2_improvement_campaign import (
    audit_feature,
    assert_no_leakage,
    build_expanded_features,
    build_foldsafe_calibration,
    build_action_labels,
    BASE_FEATURES,
)


# ---- Fixtures ----

@pytest.fixture
def mini_df():
    """Minimal synthetic case table (20 rows, 4 scenarios × 5)."""
    rng = np.random.RandomState(42)
    n = 20
    pool = ["12", "42", "100", "7"]
    fa = rng.choice(pool, size=n).tolist()
    la = rng.choice(pool, size=n).tolist()
    sa = rng.choice(pool, size=n).tolist()
    ta = rng.choice(pool, size=n).tolist()
    return pd.DataFrame({
        "example_id": [f"ex_{i}" for i in range(n)],
        "question": [f"Question {i}?" for i in range(n)],
        "frontier_ans": fa, "L1_ans": la, "S1_ans": sa, "TALE_ans": ta,
        "unique_answer_count": rng.randint(1, 5, n),
        "majority_size": rng.randint(1, 5, n),
        "has_majority": rng.randint(0, 2, n),
        "all_four_agree": rng.randint(0, 2, n),
        "all_different": rng.randint(0, 2, n),
        "two_two_split": rng.randint(0, 2, n),
        "three_one_split": rng.randint(0, 2, n),
        "frontier_in_majority": rng.randint(0, 2, n),
        "S1_in_majority": rng.randint(0, 2, n),
        "S1_isolated": rng.randint(0, 2, n),
        "frontier_isolated": rng.randint(0, 2, n),
        "L1_TALE_agree": rng.randint(0, 2, n),
        "external_majority_exists": rng.randint(0, 2, n),
        "external_majority_size": rng.randint(1, 4, n),
        "external_majority_excludes_frontier": rng.randint(0, 2, n),
        "external_majority_excludes_S1": rng.randint(0, 2, n),
        "no_majority_flag": rng.randint(0, 2, n),
        "question_length": rng.randint(10, 200, n),
        "question_number_count": rng.randint(0, 10, n),
        "question_has_equation_flag": rng.randint(0, 2, n),
        "has_fraction": rng.randint(0, 2, n),
        "has_equation": rng.randint(0, 2, n),
        "scenario_id": [f"scen_{i % 4}" for i in range(n)],
        "provider": ["cohere" if i < 10 else "mistral" for i in range(n)],
        "dataset": ["openai/gsm8k" if i < 10 else "MATH-500" for i in range(n)],
        "n_valid_sources": [4] * n,
        "pooled4_ok": rng.randint(0, 2, n),
        "S1_ok": rng.randint(0, 2, n),
        "frontier_ok": rng.randint(0, 2, n),
        "L1_ok": rng.randint(0, 2, n),
        "TALE_ok": rng.randint(0, 2, n),
    })


# ============================================================
# 1. Expanded features are legal
# ============================================================

def test_expanded_features_are_legal(mini_df):
    """All expanded features must pass the leakage audit."""
    expanded = build_expanded_features(mini_df)
    for f in expanded.columns:
        verdict = audit_feature(f)
        assert verdict == "LEGAL", f"Feature '{f}' failed legality audit: {verdict}"


def test_base_features_are_legal():
    """All 22 base features must pass legality audit."""
    for f in BASE_FEATURES:
        verdict = audit_feature(f)
        assert verdict == "LEGAL", f"Base feature '{f}' is illegal: {verdict}"


def test_no_leakage_passes_on_legal_features(mini_df):
    """assert_no_leakage should not raise for a clean feature list."""
    expanded = build_expanded_features(mini_df)
    all_feats = [f for f in BASE_FEATURES if f in mini_df.columns]
    all_feats += [f for f in expanded.columns if f not in all_feats]
    assert_no_leakage(all_feats)  # Must not raise


# ============================================================
# 2. Leaky names are rejected
# ============================================================

@pytest.mark.parametrize("leaky", [
    "pooled4_ok", "frontier_ok", "S1_ok", "L1_ok", "TALE_ok",
    "oracle_best_action_ok", "all_sources_wrong", "all_sources_correct",
    "only_frontier_correct", "gold", "frontier_ans", "L1_ans",
])
def test_exact_leaky_names_rejected(leaky):
    verdict = audit_feature(leaky)
    assert verdict != "LEGAL", f"'{leaky}' should be rejected, got: {verdict}"


@pytest.mark.parametrize("leaky_pattern", [
    "some_oracle_score", "my_gold_feature",
    "all_sources_summary", "only_s1_wrong", "my_feature_ok",
])
def test_pattern_leaky_names_rejected(leaky_pattern):
    verdict = audit_feature(leaky_pattern)
    assert verdict != "LEGAL", f"Pattern-leaky '{leaky_pattern}' should be rejected"


def test_assert_no_leakage_raises():
    """assert_no_leakage must raise ValueError when a leaky feature is included."""
    with pytest.raises(ValueError, match="LEAKAGE"):
        assert_no_leakage(["unique_answer_count", "pooled4_ok"])


# ============================================================
# 3. Fold-safe calibration feature construction
# ============================================================

def test_calibration_features_shapes(mini_df):
    """Calibration train/test shapes must match input df sizes."""
    df_tr = mini_df.iloc[:12].reset_index(drop=True)
    df_te = mini_df.iloc[12:16].reset_index(drop=True)
    y_tr = np.array([1, 0] * 6)
    c_tr, c_te = build_foldsafe_calibration(df_tr, df_te, y_tr)
    assert len(c_tr) == len(df_tr)
    assert len(c_te) == len(df_te)


def test_calibration_features_finite(mini_df):
    """After fillna(0), calibration features must be finite."""
    df_tr = mini_df.iloc[:12].reset_index(drop=True)
    df_te = mini_df.iloc[12:16].reset_index(drop=True)
    y_tr = np.ones(12)
    c_tr, c_te = build_foldsafe_calibration(df_tr, df_te, y_tr)
    assert np.isfinite(c_tr.fillna(0).values).all()
    assert np.isfinite(c_te.fillna(0).values).all()


def test_calibration_features_legal(mini_df):
    """All calibration feature names must pass legality audit."""
    df_tr = mini_df.iloc[:12].reset_index(drop=True)
    df_te = mini_df.iloc[12:16].reset_index(drop=True)
    y_tr = np.zeros(12)
    c_tr, _ = build_foldsafe_calibration(df_tr, df_te, y_tr)
    for col in c_tr.columns:
        verdict = audit_feature(col)
        assert verdict == "LEGAL", f"Calibration feat '{col}' not legal: {verdict}"


def test_calibration_no_test_label_leakage(mini_df):
    """Different train label distributions → different calibration features.

    If test labels leaked, this would be identical regardless of y_train.
    """
    df_tr = mini_df.iloc[:12].reset_index(drop=True)
    df_te = mini_df.iloc[12:14].reset_index(drop=True)
    c_tr1, c_te1 = build_foldsafe_calibration(df_tr, df_te, np.ones(12))
    c_tr2, c_te2 = build_foldsafe_calibration(df_tr, df_te, np.zeros(12))
    # At least some calibration columns should differ between y=1 and y=0 training
    if len(c_te1.columns) > 0:
        diff = (c_te1.fillna(0) - c_te2.fillna(0)).abs().max().max()
        assert diff > 0, "Calibration features unchanged across different y_train — possible test-label leakage"


# ============================================================
# 4. Official-only headline excludes auxiliary rows
# ============================================================

def test_official_headline_shape():
    """Official4 case table must have exactly 1200 rows, 4 × 300."""
    df = pd.read_csv(OUT / "improvement_official4_case_table.csv")
    assert len(df) == 1200
    counts = df["scenario_id"].value_counts().to_dict()
    assert counts == {
        "cohere_gsm8k": 300,
        "mistral_gsm8k": 300,
        "cohere_math500": 300,
        "mistral_math500": 300,
    }


def test_no_duplicates_in_official():
    """No duplicate (example_id, scenario_id) pairs in official case table.

    Global example_id uniqueness is NOT required: MATH-500 IDs appear in
    both cohere_math500 and mistral_math500 scenarios.
    """
    df = pd.read_csv(OUT / "improvement_official4_case_table.csv")
    n_unique_pairs = df[["example_id", "scenario_id"]].drop_duplicates().shape[0]
    assert n_unique_pairs == 1200, (
        f"Expected 1200 unique (example_id, scenario_id) pairs, got {n_unique_pairs}"
    )


# ============================================================
# 5. No train/test overlap
# ============================================================

def test_no_train_test_overlap(mini_df):
    """StratifiedKFold splits must produce disjoint index sets."""
    from sklearn.model_selection import StratifiedKFold
    y = mini_df["pooled4_ok"].values
    skf = StratifiedKFold(n_splits=4, shuffle=True, random_state=42)
    X = np.zeros((len(mini_df), 1))
    for tr_i, te_i in skf.split(X, y):
        overlap = set(tr_i) & set(te_i)
        assert len(overlap) == 0, f"Train/test overlap found: {overlap}"


# ============================================================
# 6. Deterministic outputs
# ============================================================

def test_expanded_features_deterministic(mini_df):
    """build_expanded_features must produce identical results on repeated calls."""
    f1 = build_expanded_features(mini_df)
    f2 = build_expanded_features(mini_df)
    pd.testing.assert_frame_equal(f1, f2)


def test_more_features_than_base(mini_df):
    """Expanded feature set must contain strictly more features than 22."""
    expanded = build_expanded_features(mini_df)
    base_avail = [f for f in BASE_FEATURES if f in mini_df.columns]
    total = len(base_avail) + len(expanded.columns)
    assert total > 22, f"Expected > 22 total features, got {total}"


def test_no_duplicate_feature_names(mini_df):
    """Expanded features must have unique names."""
    expanded = build_expanded_features(mini_df)
    names = list(expanded.columns)
    assert len(names) == len(set(names)), f"Duplicate feature names: {names}"


# ============================================================
# 7. Model outputs valid actions
# ============================================================

def test_action_labels_binary(mini_df):
    """All action label arrays must be binary (0 or 1 only)."""
    al = build_action_labels(mini_df)
    assert len(al) > 0, "No action labels built"
    for name, y in al.items():
        assert set(np.unique(y)).issubset({0, 1}), (
            f"Action '{name}' has non-binary values: {np.unique(y)}"
        )


def test_lgb_model_binary_output(mini_df):
    """LightGBM predictions must be 0 or 1."""
    import lightgbm as lgb
    al = build_action_labels(mini_df)
    expanded = build_expanded_features(mini_df)
    base_avail = [f for f in BASE_FEATURES if f in mini_df.columns]
    X = pd.concat([mini_df[base_avail], expanded], axis=1).fillna(0).values
    y = al["pooled4"]
    model = lgb.LGBMClassifier(n_estimators=10, random_state=42, verbose=-1)
    model.fit(X, y)
    preds = model.predict(X)
    assert set(np.unique(preds)).issubset({0, 1}), f"Bad predictions: {np.unique(preds)}"


# ============================================================
# 8. Output artifact integrity (post-campaign)
# ============================================================

def test_repeated_cv_results_exist():
    """Repeated CV results file must exist and have at least 1 model row."""
    csv = OUT / "improvement_repeated_cv_all_models.csv"
    assert csv.exists(), f"Missing: {csv}"
    df = pd.read_csv(csv)
    assert len(df) >= 1


def test_feature_whitelist_no_leaky_names():
    """Feature whitelist must contain no leaky column names."""
    wl = pd.read_csv(OUT / "improvement_feature_whitelist.csv")
    bad_tokens = ["_ok", "oracle", "gold", "all_sources", "only_", "wrong",
                  "correct", "label", "target"]
    for name in wl["feature_name"].astype(str).str.lower():
        for tok in bad_tokens:
            # Allow "correct" as prefix only if it's a pattern match
            assert tok not in name, f"Leaky token '{tok}' in feature '{name}'"


def test_loso_results_exist():
    """LOSO results must cover all 4 scenarios."""
    loso = pd.read_csv(OUT / "improvement_loso_summary.csv")
    assert len(loso) == 4
    assert (loso["accuracy"] >= 0).all() and (loso["accuracy"] <= 1).all()


def test_provider_heldout_results_exist():
    """Provider heldout must have 2 rows (cohere↔mistral both directions)."""
    df = pd.read_csv(OUT / "improvement_provider_heldout.csv")
    assert len(df) == 2
    assert (df["accuracy"] >= 0).all() and (df["accuracy"] <= 1).all()


def test_dataset_heldout_results_exist():
    """Dataset heldout must have 2 rows (gsm8k↔math both directions)."""
    df = pd.read_csv(OUT / "improvement_dataset_heldout.csv")
    assert len(df) == 2
    assert (df["accuracy"] >= 0).all() and (df["accuracy"] <= 1).all()


def test_manifest_and_report_exist():
    """Manifest JSON and campaign report must exist."""
    assert (OUT / "manifest.json").exists(), "manifest.json missing"
    assert (REPO / "docs" / "ROUTER_V2_IMPROVEMENT_CAMPAIGN_20260524.md").exists()
    manifest = __import__("json").loads(
        (OUT / "manifest.json").read_text()
    )
    assert manifest.get("api_calls_launched") is False
    assert manifest.get("active_jobs_touched") is False
    assert manifest.get("commit_push") is False


def test_ablation_results_exist():
    """Ablation summary must exist with at least 3 variants."""
    df = pd.read_csv(OUT / "improvement_ablation_summary.csv")
    assert len(df) >= 3
    assert "mean_accuracy" in df.columns


def test_candidate_decision_table_exists():
    """Candidate decision table must exist with a recommendation column."""
    df = pd.read_csv(OUT / "improvement_candidate_decision_table.csv")
    # Accept either "model" or "candidate" as the ID column (different runs use different names)
    has_id_col = "model" in df.columns or "candidate" in df.columns
    assert has_id_col, f"Expected 'model' or 'candidate' column, got: {list(df.columns)}"
    assert "recommendation" in df.columns, f"Missing 'recommendation', columns: {list(df.columns)}"

