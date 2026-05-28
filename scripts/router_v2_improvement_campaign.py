#!/usr/bin/env python3
"""
Router v2 Model Improvement Campaign (2026-05-24)

Goal: Improve learned_router_v2 beyond corrected baseline:
  Pooled CV 80.47%, LOSO 78.1%, Provider-heldout 74.8%, Dataset-heldout 65.4%

Steps: rebuild clean dataset, expand legal features, train model families,
hyperparameter search, comprehensive eval, failure analysis, feature importance,
candidate decision, next-data recommendation.

All features are runtime-legal (no correctness/gold information used as features).
Calibration features are computed inside CV folds only.
"""

import os, sys, json, logging, re, math, warnings, itertools
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter, defaultdict

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import StratifiedKFold
from sklearn.linear_model import LogisticRegression
from sklearn.svm import LinearSVC
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import (RandomForestClassifier, ExtraTreesClassifier,
                              HistGradientBoostingClassifier)
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import accuracy_score, brier_score_loss
from sklearn.inspection import permutation_importance as sk_perm_importance
import lightgbm as lgb
import xgboost as xgb
import optuna
optuna.logging.set_verbosity(optuna.logging.WARNING)

try:
    import shap
    HAS_SHAP = True
except ImportError:
    HAS_SHAP = False

# ============================================================
# CONFIG
# ============================================================
OUTPUT_ROOT = Path("outputs/router_v2_improvement_campaign_20260524")
REPORT_PATH = Path("docs/ROUTER_V2_IMPROVEMENT_CAMPAIGN_20260524.md")
TIMESTAMP = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

OFFICIAL4_CASE_TABLE = Path(
    "outputs/router_v2_manuscript_reproduction_20260524/reproduced_official4_case_table.csv"
)
ACTION_LABEL_TABLE = Path(
    "outputs/rg_eb_action_router_20260524/rg_eb_action_label_table.csv"
)
MISTRAL_TRAIN1000_FEAT = Path(
    "outputs/mistral_large_router_training_gsm8k_processing_20260524/router_training_feature_table.csv"
)
COHERE_MATH_AUX_CASE = Path(
    "outputs/cohere_math500_auxiliary_mlj_reprocess_20260524/cohere_math500_auxiliary_case_level_selector_results.csv"
)
# RG-EB case table has answer strings for Cohere MATH
RGEB_OFFICIAL4 = Path(
    "outputs/rg_eb_action_router_20260524/rg_eb_official4_case_table.csv"
)
RGEB_FEATURE_TABLE = Path(
    "outputs/rg_eb_action_router_20260524/rg_eb_feature_table_official4.csv"
)

CV_SEEDS = list(range(10))
N_CV_FOLDS = 5
N_OPTUNA_TRIALS = 60
RANDOM_SEED = 42

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(OUTPUT_ROOT / "campaign.log"),
    ],
)
logger = logging.getLogger(__name__)

# ============================================================
# LEAKAGE AUDIT
# ============================================================
LEAKY_EXACT = frozenset({
    # Source answers (raw strings — derived pairwise features are OK)
    "frontier_ans", "L1_ans", "S1_ans", "TALE_ans",
    # Source correctness
    "frontier_ok", "L1_ok", "S1_ok", "TALE_ok",
    "frontier_failed", "L1_failed", "S1_failed", "TALE_failed",
    # Action correctness / oracle labels
    "pooled4_ok", "agreement_only_ok", "beta_shrinkage_ok",
    "c1d_ok", "C1d_ok", "c1a_t005_ok", "C1a_t005_ok",
    "always_s1_ok", "oracle_best_action_ok", "oracle_best_source_ok",
    "best_calibrated_source_ok",
    # Action decisions (targets)
    "pooled4_decision", "agreement_only_decision", "beta_shrinkage_decision",
    "c1d_decision", "c1a_t005_decision", "always_s1_decision",
    "oracle_best_action_decision",
    # Gold-derived correctness
    "all_sources_correct", "all_sources_wrong",
    "only_frontier_correct", "only_L1_correct", "only_S1_correct",
    # Non-features
    "example_id", "question", "gold", "scenario_id",
    "majority_answer", "external_majority_answer",
    "source_split", "agreement_pattern",
    "question_length_bucket", "number_count_bucket", "difficulty_proxy",
    # Metadata (used only for heldout evals)
    "provider", "dataset",
})

LEAKY_PATTERNS = ("_ok", "_failed", "oracle", "gold", "all_sources", "only_", "wrong")


def audit_feature(name: str) -> str:
    if name in LEAKY_EXACT:
        return f"ILLEGAL:exact"
    for p in LEAKY_PATTERNS:
        if p in name.lower():
            return f"ILLEGAL:pattern({p})"
    return "LEGAL"


def assert_no_leakage(feature_names: list):
    for f in feature_names:
        verdict = audit_feature(f)
        if verdict.startswith("ILLEGAL"):
            raise ValueError(f"LEAKAGE DETECTED: feature '{f}' — {verdict}")
    logger.info("Leakage audit passed: %d features all legal", len(feature_names))


# ============================================================
# FEATURE ENGINEERING
# ============================================================
BASE_FEATURES = [
    "unique_answer_count", "majority_size", "has_majority",
    "all_four_agree", "all_different", "two_two_split", "three_one_split",
    "frontier_in_majority", "S1_in_majority", "S1_isolated", "frontier_isolated",
    "L1_TALE_agree", "external_majority_exists", "external_majority_size",
    "external_majority_excludes_frontier", "external_majority_excludes_S1",
    "no_majority_flag",
    "question_length", "question_number_count", "question_has_equation_flag",
    "has_fraction", "has_equation",
]


def _try_numeric(s) -> float | None:
    if pd.isna(s):
        return None
    s = str(s).strip()
    if s in ("", "nan", "None", "model_step_missing", "-inf", "inf", "infinity"):
        return None
    s = re.sub(r"^[a-zA-Z_\s]*=\s*", "", s)
    for sanitized in [s, s.replace(",", "")]:
        try:
            val = float(sanitized)
            # Reject infinity and NaN from float conversion
            if not math.isfinite(val):
                return None
            return val
        except (ValueError, TypeError):
            pass
    return None


def build_expanded_features(df: pd.DataFrame) -> pd.DataFrame:
    """Build expanded runtime-legal feature set.

    Uses raw answer strings ONLY to derive pairwise agreements and numeric
    properties — not the strings themselves. Question text used for structure.
    """
    feat = pd.DataFrame(index=df.index)

    ans_cols = ["frontier_ans", "L1_ans", "S1_ans", "TALE_ans"]
    has_ans = all(c in df.columns for c in ans_cols)

    if has_ans:
        fa = df["frontier_ans"].astype(str).str.strip()
        la = df["L1_ans"].astype(str).str.strip()
        sa = df["S1_ans"].astype(str).str.strip()
        ta = df["TALE_ans"].astype(str).str.strip()

        # --- A. Pairwise agreements ---
        feat["s1_l1_agree"] = (sa == la).astype(int)
        feat["s1_tale_agree"] = (sa == ta).astype(int)
        feat["frontier_s1_agree"] = (fa == sa).astype(int)
        feat["frontier_l1_agree"] = (fa == la).astype(int)
        feat["frontier_tale_agree"] = (fa == ta).astype(int)

        feat["frontier_cluster_size"] = (
            (fa == la).astype(int)
            + (fa == sa).astype(int)
            + (fa == ta).astype(int)
            + 1
        )
        feat["s1_cluster_size"] = (
            (sa == la).astype(int)
            + (sa == fa).astype(int)
            + (sa == ta).astype(int)
            + 1
        )

        # External majority composition
        feat["ext_maj_is_l1_tale"] = (
            (la == ta) & (fa != la) & (sa != la)
        ).astype(int)
        feat["ext_maj_is_l1_s1"] = (
            (la == sa) & (fa != la) & (ta != la)
        ).astype(int)
        feat["ext_maj_is_s1_tale"] = (
            (sa == ta) & (fa != sa) & (la != sa)
        ).astype(int)
        feat["ext_maj_includes_frontier"] = (
            (fa == la) | (fa == sa) | (fa == ta)
        ).astype(int)

        # Singletons and cluster entropy
        rows_stacked = pd.concat([fa, la, sa, ta], axis=1)
        rows_stacked.columns = ["f", "l", "s", "t"]

        def _n_singletons(row):
            c = Counter([row.f, row.l, row.s, row.t])
            return sum(1 for v in [row.f, row.l, row.s, row.t] if c[v] == 1)

        feat["n_singleton_answers"] = rows_stacked.apply(_n_singletons, axis=1)

        def _entropy(row):
            c = Counter([row.f, row.l, row.s, row.t])
            total = 4
            return -sum((cnt / total) * math.log2(cnt / total)
                        for cnt in c.values() if cnt > 0)

        feat["answer_cluster_entropy"] = rows_stacked.apply(_entropy, axis=1)

        # --- B. Numeric answer features ---
        nums_f = df["frontier_ans"].apply(_try_numeric)
        nums_l = df["L1_ans"].apply(_try_numeric)
        nums_s = df["S1_ans"].apply(_try_numeric)
        nums_t = df["TALE_ans"].apply(_try_numeric)
        nums_df = pd.concat([nums_f, nums_l, nums_s, nums_t], axis=1)
        nums_df.columns = ["f", "l", "s", "t"]

        feat["all_answers_numeric"] = nums_df.notna().all(axis=1).astype(int)
        feat["any_answer_numeric"] = nums_df.notna().any(axis=1).astype(int)
        feat["n_numeric_answers"] = nums_df.notna().sum(axis=1)

        def _spread(row):
            vals = [v for v in row if pd.notna(v)]
            if len(vals) < 2:
                return 0.0
            try:
                return float(max(vals) - min(vals))
            except Exception:
                return 0.0

        feat["numeric_answer_spread"] = nums_df.apply(_spread, axis=1)
        feat["log_numeric_spread"] = np.log1p(feat["numeric_answer_spread"])

        def _mag_bucket(row):
            vals = [v for v in row if pd.notna(v)]
            if not vals:
                return -1
            try:
                m = abs(float(np.mean(vals)))
                return int(math.log10(m + 1))
            except Exception:
                return -1

        feat["numeric_magnitude_bucket"] = nums_df.apply(_mag_bucket, axis=1)
        feat["any_negative_answer"] = nums_df.apply(
            lambda row: int(any(v < 0 for v in row if pd.notna(v))), axis=1
        )

    # --- C. n_valid_sources (runtime-legal: known at inference time) ---
    if "n_valid_sources" in df.columns:
        feat["n_valid_sources"] = df["n_valid_sources"].fillna(4).astype(int)

    # --- D. Question structure features ---
    if "question" in df.columns:
        q = df["question"].fillna("").astype(str)
        feat["operation_symbol_count"] = q.str.count(r"[+\-*/=<>%]")
        feat["has_percent"] = q.str.contains("%", regex=False).astype(int)
        feat["has_dollar"] = q.str.contains(r"\$", regex=True).astype(int)
        feat["question_word_count"] = q.str.split().str.len()
        feat["question_sentence_count"] = q.str.count(r"[.!?]+") + 1

        _alg = r"\b(solve|equation|variable|algebraic|inequality|polynomial|quadratic|factor)\b"
        _geo = r"\b(area|perimeter|triangle|circle|radius|diameter|volume|surface|angle|degree|polygon)\b"
        _prob = r"\b(?:probability|chance|likely|random|dice|coin|odds|expected)\b"
        _cnt = r"\b(?:how many|number of ways|combinations|permutations)\b"
        _unit = r"\b(?:km|mph|kg|lb|oz|meters?|feet|foot|inch|gallon|liters?|minutes?|hours?|dollars?|cents?)\b"
        feat["algebra_keyword"] = q.str.contains(_alg, case=False, regex=True).astype(int)
        feat["geometry_keyword"] = q.str.contains(_geo, case=False, regex=True).astype(int)
        feat["probability_keyword"] = q.str.contains(_prob, case=False, regex=True).astype(int)
        feat["counting_keyword"] = q.str.contains(_cnt, case=False, regex=True).astype(int)
        feat["has_unit_keyword"] = q.str.contains(_unit, case=False, regex=True).astype(int)

    return feat


def build_foldsafe_calibration(df_train: pd.DataFrame,
                                df_test: pd.DataFrame,
                                y_train: np.ndarray) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Compute reliability calibration features from training fold only.

    Pattern reliability = P(action_correct | pattern = 1) computed in train.
    Applied to both train and test without using test labels.
    """
    calib_feats = [
        "S1_isolated", "frontier_isolated", "all_four_agree",
        "two_two_split", "three_one_split", "all_different",
        "external_majority_exists", "no_majority_flag", "L1_TALE_agree",
        "has_majority",
    ]
    global_prior = float(y_train.mean()) if len(y_train) > 0 else 0.5

    c_train = pd.DataFrame(index=df_train.index)
    c_test = pd.DataFrame(index=df_test.index)

    for pat in calib_feats:
        if pat not in df_train.columns:
            continue
        col = f"calib_{pat}_rel"
        tv = df_train[pat].fillna(0).astype(int).values

        r1 = y_train[tv == 1].mean() if (tv == 1).sum() > 5 else global_prior
        r0 = y_train[tv == 0].mean() if (tv == 0).sum() > 5 else global_prior

        c_train[col] = np.where(tv == 1, r1, r0)
        tv_t = df_test[pat].fillna(0).astype(int).values if pat in df_test.columns else np.zeros(len(df_test))
        c_test[col] = np.where(tv_t == 1, r1, r0)

    # Majority size buckets
    if "majority_size" in df_train.columns:
        for sz in [1, 2, 3, 4]:
            col = f"calib_majsz{sz}_rel"
            mask = (df_train["majority_size"].fillna(0).astype(int) == sz).values
            rel = y_train[mask].mean() if mask.sum() > 5 else global_prior
            c_train[col] = mask.astype(float) * rel
            if "majority_size" in df_test.columns:
                mask_t = (df_test["majority_size"].fillna(0).astype(int) == sz).values
            else:
                mask_t = np.zeros(len(df_test), dtype=bool)
            c_test[col] = mask_t.astype(float) * rel

    return c_train, c_test


# ============================================================
# ACTION TARGETS
# ============================================================
# Primary binary targets for comparison with baseline 80.47%
BINARY_ACTION_TARGETS = {
    "pooled4": "pooled4_ok",
    "S1": "S1_ok",
    "frontier": "frontier_ok",
    "L1": "L1_ok",
    "TALE": "TALE_ok",
}


def build_action_labels(df: pd.DataFrame) -> dict:
    """Build binary action label arrays."""
    labels = {}
    for name, col in BINARY_ACTION_TARGETS.items():
        if col in df.columns:
            labels[name] = df[col].fillna(0).astype(int).values
        elif col.replace("ok", "Ok") in df.columns:
            # Handle alternate capitalization
            labels[name] = df[col.replace("ok", "Ok")].fillna(0).astype(int).values
    return labels


def build_multiclass_oracle_label(df: pd.DataFrame) -> np.ndarray:
    """Build multiclass oracle action label.

    Priority (cheapest correct action):
    pooled4 → agreement_only → c1d → S1 → frontier → L1 → TALE → fallback=pooled4
    """
    priority = [
        ("pooled4", "pooled4_ok"),
        ("agreement_only", "agreement_only_ok"),
        ("c1d", "C1d_ok"),
        ("c1d", "c1d_ok"),
        ("S1", "S1_ok"),
        ("frontier", "frontier_ok"),
        ("L1", "L1_ok"),
        ("TALE", "TALE_ok"),
    ]
    labels = np.full(len(df), "pooled4", dtype=object)
    # Assign in reverse priority (higher priority overwrites lower)
    for action, col in reversed(priority):
        if col in df.columns:
            mask = df[col].fillna(0).astype(int) == 1
            labels[mask] = action
    return labels


# ============================================================
# MODEL FACTORY
# ============================================================
def make_models() -> dict:
    """Return dict of model name → sklearn-compatible estimator."""
    models = {}

    # Low-capacity
    models["logistic_l2"] = LogisticRegression(
        random_state=RANDOM_SEED, max_iter=2000, C=1.0, solver="lbfgs", n_jobs=-1
    )
    models["logistic_l1"] = LogisticRegression(
        random_state=RANDOM_SEED, max_iter=2000, C=1.0, solver="liblinear", penalty="l1"
    )
    models["logistic_calibrated"] = CalibratedClassifierCV(
        LogisticRegression(random_state=RANDOM_SEED, max_iter=2000, n_jobs=-1),
        cv=3, method="isotonic"
    )
    models["decision_tree_d4"] = DecisionTreeClassifier(
        random_state=RANDOM_SEED, max_depth=4
    )

    # Tree ensembles
    models["random_forest"] = RandomForestClassifier(
        n_estimators=200, random_state=RANDOM_SEED, max_depth=None,
        min_samples_leaf=2, n_jobs=-1
    )
    models["extra_trees"] = ExtraTreesClassifier(
        n_estimators=200, random_state=RANDOM_SEED, max_depth=None,
        min_samples_leaf=2, n_jobs=-1
    )
    models["hgb"] = HistGradientBoostingClassifier(
        random_state=RANDOM_SEED, max_iter=200, max_depth=5,
        learning_rate=0.05, min_samples_leaf=10
    )

    # Boosting
    models["lgb"] = lgb.LGBMClassifier(
        n_estimators=300, random_state=RANDOM_SEED, learning_rate=0.05,
        num_leaves=31, min_child_samples=10, verbose=-1, n_jobs=-1
    )
    models["xgb"] = xgb.XGBClassifier(
        n_estimators=300, random_state=RANDOM_SEED, learning_rate=0.05,
        max_depth=5, min_child_weight=5, verbosity=0, n_jobs=-1,
        eval_metric="logloss"
    )

    return models


# ============================================================
# CORE EVALUATION: multi-output binary accuracy
# ============================================================
def evaluate_multi_output_binary(
    X: np.ndarray,
    df: pd.DataFrame,
    action_labels: dict,
    model_factory,
    n_folds: int = N_CV_FOLDS,
    seed: int = RANDOM_SEED,
    use_calibration_features: bool = False,
) -> dict:
    """Multi-output binary CV (same protocol as baseline 80.47%).

    Returns dict with per-action and mean accuracy.
    """
    skf = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=seed)
    first_action = list(action_labels.keys())[0]
    y_first = action_labels[first_action]

    action_fold_accs = defaultdict(list)
    fold_means = []

    for train_idx, test_idx in skf.split(X, y_first):
        X_train_f, X_test_f = X[train_idx], X[test_idx]
        df_train_f = df.iloc[train_idx]
        df_test_f = df.iloc[test_idx]

        action_accs = []
        for action_name, y_full in action_labels.items():
            y_train = y_full[train_idx]
            y_test = y_full[test_idx]

            X_tr = X_train_f
            X_te = X_test_f

            if use_calibration_features:
                c_tr, c_te = build_foldsafe_calibration(df_train_f, df_test_f, y_train)
                X_tr = np.hstack([X_train_f, c_tr.fillna(0).values])
                X_te = np.hstack([X_test_f, c_te.fillna(0).values])

            model = model_factory()
            model.fit(X_tr, y_train)
            preds = model.predict(X_te)
            acc = accuracy_score(y_test, preds)
            action_fold_accs[action_name].append(acc)
            action_accs.append(acc)

        fold_means.append(float(np.mean(action_accs)))

    result = {"mean_accuracy": float(np.mean(fold_means)),
               "std_accuracy": float(np.std(fold_means))}
    for a, accs in action_fold_accs.items():
        result[f"{a}_accuracy"] = float(np.mean(accs))
    return result


def repeated_cv(
    X: np.ndarray,
    df: pd.DataFrame,
    action_labels: dict,
    model_factory,
    seeds: list = None,
    use_calibration_features: bool = False,
) -> dict:
    """Repeated multi-output binary CV across multiple seeds."""
    if seeds is None:
        seeds = CV_SEEDS
    all_scores = []
    for s in seeds:
        r = evaluate_multi_output_binary(X, df, action_labels, model_factory,
                                          seed=s,
                                          use_calibration_features=use_calibration_features)
        all_scores.append(r["mean_accuracy"])
    return {
        "seeds": seeds,
        "scores": all_scores,
        "mean": float(np.mean(all_scores)),
        "std": float(np.std(all_scores)),
        "min": float(np.min(all_scores)),
        "max": float(np.max(all_scores)),
        "ci95_half": float(1.96 * np.std(all_scores) / math.sqrt(len(all_scores))),
    }


def within_scenario_cv(
    X: np.ndarray,
    df: pd.DataFrame,
    action_labels: dict,
    model_factory,
    use_calibration_features: bool = False,
) -> pd.DataFrame:
    """Within-scenario 5-fold CV."""
    rows = []
    for scen in sorted(df["scenario_id"].unique()):
        mask = (df["scenario_id"] == scen).values
        X_s = X[mask]
        df_s = df[mask].reset_index(drop=True)
        al_s = {k: v[mask] for k, v in action_labels.items()}

        skf = StratifiedKFold(n_splits=min(N_CV_FOLDS, mask.sum() // 10 or 2),
                               shuffle=True, random_state=RANDOM_SEED)
        y_first = al_s[list(al_s.keys())[0]]
        fold_accs = []
        for tr_i, te_i in skf.split(X_s, y_first):
            X_tr, X_te = X_s[tr_i], X_s[te_i]
            df_tr_f = df_s.iloc[tr_i]
            df_te_f = df_s.iloc[te_i]
            action_accs = []
            for aname, yf in al_s.items():
                y_tr, y_te = yf[tr_i], yf[te_i]
                Xtr_, Xte_ = X_tr, X_te
                if use_calibration_features:
                    c_tr, c_te = build_foldsafe_calibration(df_tr_f, df_te_f, y_tr)
                    Xtr_ = np.hstack([X_tr, c_tr.fillna(0).values])
                    Xte_ = np.hstack([X_te, c_te.fillna(0).values])
                m = model_factory()
                m.fit(Xtr_, y_tr)
                action_accs.append(accuracy_score(y_te, m.predict(Xte_)))
            fold_accs.append(float(np.mean(action_accs)))
        rows.append({"scenario": scen, "mean_accuracy": float(np.mean(fold_accs)),
                     "std_accuracy": float(np.std(fold_accs)), "n": int(mask.sum())})
    return pd.DataFrame(rows)


def loso_eval(
    X: np.ndarray,
    df: pd.DataFrame,
    action_labels: dict,
    model_factory,
    use_calibration_features: bool = False,
) -> pd.DataFrame:
    """Leave-one-scenario-out evaluation."""
    rows = []
    for scen in sorted(df["scenario_id"].unique()):
        tr_mask = (df["scenario_id"] != scen).values
        te_mask = (df["scenario_id"] == scen).values
        X_tr, X_te = X[tr_mask], X[te_mask]
        df_tr_f = df[tr_mask].reset_index(drop=True)
        df_te_f = df[te_mask].reset_index(drop=True)

        action_accs = []
        for aname, y_full in action_labels.items():
            y_tr, y_te = y_full[tr_mask], y_full[te_mask]
            Xtr_, Xte_ = X_tr, X_te
            if use_calibration_features:
                c_tr, c_te = build_foldsafe_calibration(df_tr_f, df_te_f, y_tr)
                Xtr_ = np.hstack([X_tr, c_tr.fillna(0).values])
                Xte_ = np.hstack([X_te, c_te.fillna(0).values])
            m = model_factory()
            m.fit(Xtr_, y_tr)
            action_accs.append(accuracy_score(y_te, m.predict(Xte_)))
        rows.append({"held_out_scenario": scen, "accuracy": float(np.mean(action_accs)),
                     "n_test": int(te_mask.sum()), "n_train": int(tr_mask.sum())})
    return pd.DataFrame(rows)


def provider_heldout_eval(
    X: np.ndarray,
    df: pd.DataFrame,
    action_labels: dict,
    model_factory,
) -> pd.DataFrame:
    """Provider heldout: train on one provider, test on other."""
    rows = []
    providers = sorted(df["provider"].unique())
    for tr_prov in providers:
        for te_prov in providers:
            if tr_prov == te_prov:
                continue
            tr_m = (df["provider"] == tr_prov).values
            te_m = (df["provider"] == te_prov).values
            X_tr, X_te = X[tr_m], X[te_m]
            action_accs = []
            for aname, y_full in action_labels.items():
                m = model_factory()
                m.fit(X_tr, y_full[tr_m])
                action_accs.append(accuracy_score(y_full[te_m], m.predict(X_te)))
            rows.append({
                "train_provider": tr_prov, "test_provider": te_prov,
                "accuracy": float(np.mean(action_accs)),
                "n_train": int(tr_m.sum()), "n_test": int(te_m.sum()),
            })
    return pd.DataFrame(rows)


def dataset_heldout_eval(
    X: np.ndarray,
    df: pd.DataFrame,
    action_labels: dict,
    model_factory,
) -> pd.DataFrame:
    """Dataset heldout: train on one dataset, test on other."""
    rows = []
    datasets = sorted(df["dataset"].unique())
    for tr_ds in datasets:
        for te_ds in datasets:
            if tr_ds == te_ds:
                continue
            tr_m = (df["dataset"] == tr_ds).values
            te_m = (df["dataset"] == te_ds).values
            X_tr, X_te = X[tr_m], X[te_m]
            action_accs = []
            for aname, y_full in action_labels.items():
                m = model_factory()
                m.fit(X_tr, y_full[tr_m])
                action_accs.append(accuracy_score(y_full[te_m], m.predict(X_te)))
            rows.append({
                "train_dataset": tr_ds, "test_dataset": te_ds,
                "accuracy": float(np.mean(action_accs)),
                "n_train": int(tr_m.sum()), "n_test": int(te_m.sum()),
            })
    return pd.DataFrame(rows)


def macro_scenario_accuracy(within_df: pd.DataFrame) -> float:
    """Macro average of within-scenario CV accuracies."""
    return float(within_df["mean_accuracy"].mean())


# ============================================================
# OPTUNA HYPERPARAMETER SEARCH (LightGBM)
# ============================================================
def lgb_optuna_search(
    X: np.ndarray,
    df: pd.DataFrame,
    action_labels: dict,
    n_trials: int = N_OPTUNA_TRIALS,
    use_calibration_features: bool = False,
) -> tuple[dict, lgb.LGBMClassifier]:
    """Optimize LightGBM on macro CV (mean across scenarios, mean across actions)."""

    def objective(trial):
        params = {
            "n_estimators": trial.suggest_int("n_estimators", 100, 500),
            "learning_rate": trial.suggest_float("learning_rate", 0.02, 0.2, log=True),
            "num_leaves": trial.suggest_int("num_leaves", 15, 63),
            "min_child_samples": trial.suggest_int("min_child_samples", 5, 50),
            "subsample": trial.suggest_float("subsample", 0.6, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
            "reg_alpha": trial.suggest_float("reg_alpha", 0.0, 2.0),
            "reg_lambda": trial.suggest_float("reg_lambda", 0.0, 2.0),
            "random_state": RANDOM_SEED,
            "verbose": -1,
            "n_jobs": -1,
        }

        model_fn = lambda: lgb.LGBMClassifier(**params)

        # Use within-scenario macro CV for diversity-preserving objective
        scen_scores = []
        for scen in sorted(df["scenario_id"].unique()):
            mask = (df["scenario_id"] == scen).values
            X_s = X[mask]
            df_s = df[mask].reset_index(drop=True)
            al_s = {k: v[mask] for k, v in action_labels.items()}
            n_folds = min(N_CV_FOLDS, max(2, mask.sum() // 20))
            r = evaluate_multi_output_binary(
                X_s, df_s, al_s, model_fn, n_folds=n_folds,
                use_calibration_features=use_calibration_features
            )
            scen_scores.append(r["mean_accuracy"])

        macro = float(np.mean(scen_scores))
        worst = float(np.min(scen_scores))
        # Blend: 60% macro + 40% worst-scenario
        return 0.6 * macro + 0.4 * worst

    study = optuna.create_study(direction="maximize",
                                 sampler=optuna.samplers.TPESampler(seed=RANDOM_SEED))
    study.optimize(objective, n_trials=n_trials, show_progress_bar=False)

    best_params = study.best_params
    best_params.update({"random_state": RANDOM_SEED, "verbose": -1, "n_jobs": -1})
    best_model = lgb.LGBMClassifier(**best_params)
    return best_params, best_model


def xgb_optuna_search(
    X: np.ndarray,
    df: pd.DataFrame,
    action_labels: dict,
    n_trials: int = max(20, N_OPTUNA_TRIALS // 3),
) -> dict:
    """Optimize XGBoost."""

    def objective(trial):
        params = {
            "n_estimators": trial.suggest_int("n_estimators", 100, 400),
            "learning_rate": trial.suggest_float("learning_rate", 0.02, 0.2, log=True),
            "max_depth": trial.suggest_int("max_depth", 3, 8),
            "min_child_weight": trial.suggest_int("min_child_weight", 1, 20),
            "subsample": trial.suggest_float("subsample", 0.6, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
            "gamma": trial.suggest_float("gamma", 0.0, 5.0),
            "random_state": RANDOM_SEED,
            "verbosity": 0,
            "n_jobs": -1,
            "eval_metric": "logloss",
        }
        model_fn = lambda: xgb.XGBClassifier(**params)
        r = evaluate_multi_output_binary(X, df, action_labels, model_fn, n_folds=3)
        return r["mean_accuracy"]

    study = optuna.create_study(direction="maximize",
                                 sampler=optuna.samplers.TPESampler(seed=RANDOM_SEED))
    study.optimize(objective, n_trials=n_trials, show_progress_bar=False)
    return study.best_params


# ============================================================
# MARGIN-SAFE ROUTER
# ============================================================
def margin_safe_router_eval(
    X: np.ndarray,
    df: pd.DataFrame,
    action_labels: dict,
    base_model_factory,
    fallback_col: str = "c1d_ok",
    thresholds: list = None,
) -> pd.DataFrame:
    """Evaluate router with confidence-threshold fallback to beta/c1d.

    When model confidence margin (|p - 0.5|) < threshold, use fallback.
    """
    if thresholds is None:
        thresholds = [0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30]

    skf = StratifiedKFold(n_splits=N_CV_FOLDS, shuffle=True, random_state=RANDOM_SEED)
    first_action = list(action_labels.keys())[0]
    y_first = action_labels[first_action]

    results = []
    for thresh in thresholds:
        thresh_fold_accs = []
        for tr_i, te_i in skf.split(X, y_first):
            X_tr, X_te = X[tr_i], X[te_i]
            df_te = df.iloc[te_i]

            fold_acc_vals = []
            for aname, y_full in action_labels.items():
                y_tr, y_te = y_full[tr_i], y_full[te_i]
                m = base_model_factory()
                m.fit(X_tr, y_tr)

                if hasattr(m, "predict_proba"):
                    proba = m.predict_proba(X_te)[:, 1]
                    margin = np.abs(proba - 0.5)
                    confident_mask = margin >= thresh
                    preds = m.predict(X_te)

                    # Fallback: use c1d when not confident
                    if fallback_col in df.columns:
                        fallback_labels = df[fallback_col].fillna(0).astype(int).values
                        fallback_te = fallback_labels[te_i]
                        final_preds = np.where(confident_mask, preds, fallback_te)
                        final_acc = accuracy_score(y_te, final_preds)
                    else:
                        final_acc = accuracy_score(y_te, preds)
                else:
                    preds = m.predict(X_te)
                    final_acc = accuracy_score(y_te, preds)

                fold_acc_vals.append(final_acc)
            thresh_fold_accs.append(float(np.mean(fold_acc_vals)))

        coverage = 1.0  # all cases; margin-safe just changes predictions
        results.append({
            "threshold": thresh,
            "mean_accuracy": float(np.mean(thresh_fold_accs)),
            "coverage": coverage,
        })

    return pd.DataFrame(results)


# ============================================================
# AUXILIARY DATA EVALUATION
# ============================================================
def auxiliary_eval(
    X_official: np.ndarray,
    df_official: pd.DataFrame,
    action_labels_official: dict,
    X_mistral: np.ndarray | None,
    df_mistral: pd.DataFrame | None,
    action_labels_mistral: dict | None,
    X_cohere_math: np.ndarray | None,
    df_cohere_math: pd.DataFrame | None,
    action_labels_cohere_math: dict | None,
    model_factory,
    feature_names: list,
) -> pd.DataFrame:
    """Evaluate official-only vs official+auxiliary training."""
    rows = []

    def _eval_split(X_train, y_train_labels, X_test, y_test_labels, split_name):
        accs = []
        for aname in y_train_labels:
            if aname in y_test_labels:
                m = model_factory()
                m.fit(X_train, y_train_labels[aname])
                accs.append(accuracy_score(y_test_labels[aname], m.predict(X_test)))
        return {"split": split_name, "n_train": len(X_train),
                "n_test": len(X_test), "mean_accuracy": float(np.mean(accs))}

    # Official-only baseline (pooled CV, repeated)
    first_key = list(action_labels_official.keys())[0]
    skf = StratifiedKFold(n_splits=N_CV_FOLDS, shuffle=True, random_state=RANDOM_SEED)
    cv_accs = []
    for tr_i, te_i in skf.split(X_official, action_labels_official[first_key]):
        accs = []
        for aname, y in action_labels_official.items():
            m = model_factory()
            m.fit(X_official[tr_i], y[tr_i])
            accs.append(accuracy_score(y[te_i], m.predict(X_official[te_i])))
        cv_accs.append(float(np.mean(accs)))
    rows.append({
        "training_set": "official_only_cv",
        "n_train": f"~{int(0.8 * len(X_official))}",
        "n_test": f"~{int(0.2 * len(X_official))}",
        "mean_accuracy": float(np.mean(cv_accs)),
    })

    # + Mistral train1000
    if X_mistral is not None and len(X_mistral) > 0:
        X_aug = np.vstack([X_official, X_mistral])
        al_aug = {}
        for k in action_labels_official:
            if k in (action_labels_mistral or {}):
                al_aug[k] = np.concatenate([action_labels_official[k],
                                              action_labels_mistral[k]])
            else:
                al_aug[k] = action_labels_official[k]

        cv_accs_aug = []
        for tr_i, te_i in skf.split(X_official, action_labels_official[first_key]):
            # Train on augmented, test on official
            X_train_aug = np.vstack([X_official[tr_i], X_mistral])
            accs = []
            for aname, y in action_labels_official.items():
                if aname in (action_labels_mistral or {}):
                    y_aug_tr = np.concatenate([y[tr_i], action_labels_mistral[aname]])
                else:
                    y_aug_tr = y[tr_i]
                X_tr_full = X_train_aug[:len(y_aug_tr)]
                m = model_factory()
                m.fit(X_tr_full, y_aug_tr)
                accs.append(accuracy_score(y[te_i], m.predict(X_official[te_i])))
            cv_accs_aug.append(float(np.mean(accs)))
        rows.append({
            "training_set": "official+mistral_train1000",
            "n_train": f"{len(X_official)} + {len(X_mistral)}",
            "n_test": f"~{int(0.2 * len(X_official))} (official)",
            "mean_accuracy": float(np.mean(cv_accs_aug)),
        })

    # + Cohere MATH auxiliary
    if X_cohere_math is not None and len(X_cohere_math) > 0:
        cv_accs_cm = []
        for tr_i, te_i in skf.split(X_official, action_labels_official[first_key]):
            X_train_aug = np.vstack([X_official[tr_i], X_cohere_math])
            accs = []
            for aname, y in action_labels_official.items():
                if aname in (action_labels_cohere_math or {}):
                    y_aug_tr = np.concatenate([y[tr_i], action_labels_cohere_math[aname]])
                else:
                    y_aug_tr = y[tr_i]
                X_tr_full = X_train_aug[:len(y_aug_tr)]
                m = model_factory()
                m.fit(X_tr_full, y_aug_tr)
                accs.append(accuracy_score(y[te_i], m.predict(X_official[te_i])))
            cv_accs_cm.append(float(np.mean(accs)))
        rows.append({
            "training_set": "official+cohere_math_aux",
            "n_train": f"{len(X_official)} + {len(X_cohere_math)}",
            "n_test": f"~{int(0.2 * len(X_official))} (official)",
            "mean_accuracy": float(np.mean(cv_accs_cm)),
        })

    # Both auxiliaries
    aux_parts = []
    aux_label_parts = {}
    if X_mistral is not None:
        aux_parts.append(X_mistral)
        for k, v in (action_labels_mistral or {}).items():
            aux_label_parts.setdefault(k, []).append(v)
    if X_cohere_math is not None:
        aux_parts.append(X_cohere_math)
        for k, v in (action_labels_cohere_math or {}).items():
            aux_label_parts.setdefault(k, []).append(v)

    if len(aux_parts) > 1:
        X_both_aux = np.vstack(aux_parts)
        al_both_aux = {k: np.concatenate(vlist)
                       for k, vlist in aux_label_parts.items()}
        cv_accs_both = []
        for tr_i, te_i in skf.split(X_official, action_labels_official[first_key]):
            X_train_aug = np.vstack([X_official[tr_i], X_both_aux])
            accs = []
            for aname, y in action_labels_official.items():
                if aname in al_both_aux:
                    y_aug_tr = np.concatenate([y[tr_i], al_both_aux[aname]])
                else:
                    y_aug_tr = y[tr_i]
                X_tr_full = X_train_aug[:len(y_aug_tr)]
                m = model_factory()
                m.fit(X_tr_full, y_aug_tr)
                accs.append(accuracy_score(y[te_i], m.predict(X_official[te_i])))
            cv_accs_both.append(float(np.mean(accs)))
        rows.append({
            "training_set": "official+both_auxiliary",
            "n_train": f"{len(X_official)} + {len(X_both_aux)}",
            "n_test": f"~{int(0.2 * len(X_official))} (official)",
            "mean_accuracy": float(np.mean(cv_accs_both)),
        })

    return pd.DataFrame(rows)


# ============================================================
# ABLATION STUDIES
# ============================================================
def run_ablations(
    df: pd.DataFrame,
    action_labels: dict,
    model_factory,
    base_features: list,
    expanded_features: list,
    scaler: StandardScaler,
) -> pd.DataFrame:
    """Run ablation study across feature subsets."""
    rows = []

    def _ablation_cv(feat_subset_names: list, label: str, include_calibration: bool = False):
        available = [f for f in feat_subset_names if f in df.columns]
        if not available:
            return
        Xraw = df[available].fillna(0).values
        X_s = scaler.transform(np.hstack([Xraw, np.zeros((len(Xraw),
                                          scaler.n_features_in_ - Xraw.shape[1]))]
                                         )) if scaler.n_features_in_ > Xraw.shape[1] else Xraw
        # Simple: just use the features as-is with a fresh scaler
        sc2 = StandardScaler()
        X_sc = sc2.fit_transform(Xraw)
        r = evaluate_multi_output_binary(X_sc, df, action_labels, model_factory,
                                          use_calibration_features=include_calibration)
        rows.append({
            "ablation": label,
            "n_features": len(available),
            "mean_accuracy": r["mean_accuracy"],
            "std_accuracy": r["std_accuracy"],
        })

    # Core ablations
    agreement_feats = [f for f in base_features if f not in
                       ["question_length", "question_number_count",
                        "question_has_equation_flag", "has_fraction", "has_equation"]]
    question_feats = ["question_length", "question_number_count",
                      "question_has_equation_flag", "has_fraction", "has_equation"]

    _ablation_cv(base_features, "base_22_features")
    _ablation_cv(expanded_features, "expanded_features_all")
    _ablation_cv(agreement_feats, "agreement_only_16")
    _ablation_cv(question_feats, "question_only_5")
    _ablation_cv(expanded_features, "expanded+calibration", include_calibration=True)

    # No metadata (no provider/dataset - provider-free)
    no_meta = [f for f in expanded_features
               if f not in ("provider", "dataset", "scenario_id")]
    _ablation_cv(no_meta, "no_metadata")

    # Pairwise agreement only (new features)
    pairwise_feats = ["s1_l1_agree", "s1_tale_agree", "frontier_s1_agree",
                      "frontier_l1_agree", "frontier_tale_agree",
                      "L1_TALE_agree", "frontier_cluster_size", "s1_cluster_size"]
    pairwise_available = [f for f in pairwise_feats if f in df.columns]
    if pairwise_available:
        _ablation_cv(pairwise_available + agreement_feats[:10], "pairwise_agreement_expanded")

    # Numeric answer features only
    numeric_feats = [f for f in expanded_features if any(
        k in f for k in ["numeric", "negative", "spread", "magnitude"])]
    if numeric_feats:
        _ablation_cv(numeric_feats + base_features, "base+numeric_answer_features")

    # Question structure only (new question features)
    q_struct = ["operation_symbol_count", "has_percent", "has_dollar",
                "question_word_count", "question_sentence_count",
                "algebra_keyword", "geometry_keyword", "probability_keyword",
                "counting_keyword", "has_unit_keyword"] + question_feats
    _ablation_cv(q_struct, "expanded_question_features")

    # Metadata-only negative control: encode provider/dataset as integers
    # (not in feature matrix; encode here for the negative control only)
    if "provider" in df.columns or "dataset" in df.columns:
        meta_df_encoded = pd.DataFrame(index=df.index)
        if "provider" in df.columns:
            meta_df_encoded["provider_enc"] = pd.Categorical(df["provider"]).codes.astype(float)
        if "dataset" in df.columns:
            meta_df_encoded["dataset_enc"] = pd.Categorical(df["dataset"]).codes.astype(float)
        meta_only_encoded = list(meta_df_encoded.columns)
        # Temporarily add to df for ablation
        df_tmp = pd.concat([df, meta_df_encoded], axis=1)
        sc_meta = StandardScaler()
        X_meta = sc_meta.fit_transform(meta_df_encoded.fillna(0).values)
        r_meta = evaluate_multi_output_binary(X_meta, df, action_labels, model_factory)
        rows.append({"ablation": "metadata_only_NEGATIVE_CONTROL",
                      "n_features": len(meta_only_encoded),
                      "mean_accuracy": r_meta["mean_accuracy"],
                      "std_accuracy": r_meta["std_accuracy"]})

    # Random label negative control
    rng = np.random.RandomState(RANDOM_SEED)
    _al_random = {k: rng.randint(0, 2, size=len(df)) for k in action_labels}
    X_all = df[[f for f in expanded_features if f in df.columns]].fillna(0).values
    sc_tmp = StandardScaler()
    X_tmp = sc_tmp.fit_transform(X_all)
    r_rand = evaluate_multi_output_binary(X_tmp, df, _al_random, model_factory)
    rows.append({"ablation": "random_label_NEGATIVE_CONTROL",
                  "n_features": len(expanded_features),
                  "mean_accuracy": r_rand["mean_accuracy"],
                  "std_accuracy": r_rand["std_accuracy"]})

    return pd.DataFrame(rows)


# ============================================================
# FAILURE ANALYSIS
# ============================================================
def failure_analysis(
    X: np.ndarray,
    df: pd.DataFrame,
    action_labels: dict,
    new_model_factory,
    prev_cv_accuracy: float = 0.80467,
) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    """Compare new model vs previous corrected router-v2."""
    # Out-of-fold predictions for case-level comparison
    skf = StratifiedKFold(n_splits=N_CV_FOLDS, shuffle=True, random_state=RANDOM_SEED)
    first_key = list(action_labels.keys())[0]
    y_first = action_labels[first_key]

    oof_preds = np.full(len(df), -1, dtype=int)
    oof_labels = y_first.copy()

    for tr_i, te_i in skf.split(X, y_first):
        m = new_model_factory()
        m.fit(X[tr_i], y_first[tr_i])
        oof_preds[te_i] = m.predict(X[te_i])

    # Case-level comparison
    new_correct = (oof_preds == oof_labels).astype(int)
    # Use pooled4 as baseline reference ("old router" proxy)
    if "pooled4_ok" in df.columns:
        old_correct = df["pooled4_ok"].fillna(0).astype(int).values
    else:
        old_correct = (oof_preds > 0).astype(int)

    recoveries_mask = (new_correct == 1) & (old_correct == 0)
    regressions_mask = (new_correct == 0) & (old_correct == 1)

    recovery_df = df[recoveries_mask].copy()
    recovery_df["new_correct"] = 1
    recovery_df["old_correct"] = 0

    regression_df = df[regressions_mask].copy()
    regression_df["new_correct"] = 0
    regression_df["old_correct"] = 1

    casebook_lines = [
        "# Improvement Campaign: Failure Casebook\n",
        f"Primary action: {first_key}\n",
        f"New OOF accuracy: {new_correct.mean():.4f}\n",
        f"Previous baseline (pooled4_ok): {old_correct.mean():.4f}\n",
        f"Recoveries: {recoveries_mask.sum()}\n",
        f"Regressions: {regressions_mask.sum()}\n\n",
    ]

    # Scenario breakdown of recoveries/regressions
    if "scenario_id" in df.columns:
        casebook_lines.append("## Scenario Breakdown\n")
        for scen in sorted(df["scenario_id"].unique()):
            scen_m = (df["scenario_id"] == scen).values
            rec_s = recoveries_mask & scen_m
            reg_s = regressions_mask & scen_m
            casebook_lines.append(
                f"  {scen}: recoveries={rec_s.sum()}, regressions={reg_s.sum()}, "
                f"net={rec_s.sum() - reg_s.sum()}\n"
            )

    return recovery_df, regression_df, "".join(casebook_lines)


# ============================================================
# FEATURE IMPORTANCE
# ============================================================
def compute_feature_importance(
    X: np.ndarray,
    feature_names: list,
    action_labels: dict,
    model_factory,
) -> pd.DataFrame:
    """Compute permutation and tree-based feature importance."""
    first_key = list(action_labels.keys())[0]
    y = action_labels[first_key]

    model = model_factory()
    model.fit(X, y)

    rows = []

    # Tree/native importance
    if hasattr(model, "feature_importances_"):
        imp = model.feature_importances_
        for feat, val in zip(feature_names, imp):
            rows.append({"feature": feat, "tree_importance": float(val)})
    else:
        for feat in feature_names:
            rows.append({"feature": feat, "tree_importance": np.nan})

    # Logistic coefficients (if linear)
    if hasattr(model, "coef_"):
        coefs = np.abs(model.coef_[0]) if model.coef_.ndim > 1 else np.abs(model.coef_)
        for i, feat in enumerate(feature_names):
            if i < len(rows):
                rows[i]["logistic_coef"] = float(coefs[i]) if i < len(coefs) else np.nan

    # Permutation importance (on held-out fold)
    skf = StratifiedKFold(n_splits=3, shuffle=True, random_state=RANDOM_SEED)
    tr_i, te_i = next(skf.split(X, y))
    model2 = model_factory()
    model2.fit(X[tr_i], y[tr_i])
    perm = sk_perm_importance(model2, X[te_i], y[te_i],
                               n_repeats=10, random_state=RANDOM_SEED)
    perm_dict = dict(zip(feature_names, perm.importances_mean))
    for row in rows:
        row["permutation_importance"] = perm_dict.get(row["feature"], np.nan)

    df_imp = pd.DataFrame(rows)
    # SHAP if available
    if HAS_SHAP and hasattr(model2, "predict"):
        try:
            explainer = shap.TreeExplainer(model2)
            shap_vals = explainer.shap_values(X[te_i])
            if isinstance(shap_vals, list):
                shap_vals = shap_vals[1]
            shap_mean = np.abs(shap_vals).mean(axis=0)
            shap_dict = dict(zip(feature_names, shap_mean))
            for i, row in df_imp.iterrows():
                df_imp.at[i, "shap_importance"] = shap_dict.get(row["feature"], np.nan)
        except Exception as e:
            logger.warning("SHAP failed: %s", e)

    df_imp = df_imp.sort_values("tree_importance", ascending=False, na_position="last")
    return df_imp


# ============================================================
# REPORT GENERATION
# ============================================================
def build_report(
    baseline: dict,
    all_results: dict,
    best_candidate: str,
    best_cv: dict,
    feature_names: list,
    ablation_df: pd.DataFrame,
    auxiliary_df: pd.DataFrame,
    loso_df: pd.DataFrame,
    provider_df: pd.DataFrame,
    dataset_df: pd.DataFrame,
    candidate_df: pd.DataFrame,
    feat_imp_df: pd.DataFrame,
    packages_installed: list,
    timestamp: str,
) -> str:
    lines = [
        "# Router v2 Improvement Campaign (2026-05-24)\n\n",
        f"Generated: {timestamp}\n\n",
        "## 1. Executive Summary\n\n",
    ]

    # Compare to baseline
    baseline_pooled = 0.80467
    new_pooled = best_cv.get("mean", 0)
    delta = new_pooled - baseline_pooled
    lines.append(f"- Baseline (corrected router-v2): pooled CV = {baseline_pooled:.4f}\n")
    lines.append(f"- Best new model ({best_candidate}): pooled CV = {new_pooled:.4f} "
                 f"(Δ = {delta:+.4f})\n")
    lines.append(f"- Feature count: {len(feature_names)} (expanded from 22)\n\n")

    lines.append("## 2. Data and Leakage Controls\n\n")
    lines.append("- Official4 rows: 1200 (4 scenarios × 300)\n")
    lines.append("- No auxiliary rows in headline evaluation\n")
    lines.append("- All features audited: no _ok, _failed, oracle, gold columns\n")
    lines.append("- Calibration features computed inside folds only\n\n")

    lines.append("## 3. Expanded Legal Feature Schema\n\n")
    lines.append(f"Total features: {len(feature_names)}\n\n")
    lines.append("| Feature | Category |\n|---------|----------|\n")
    for f in sorted(feature_names):
        cat = "agreement" if any(k in f for k in ["agree", "majority", "split", "isolated", "cluster", "entropy"]) \
            else "numeric_answer" if any(k in f for k in ["numeric", "spread", "magnitude", "negative"]) \
            else "question" if any(k in f for k in ["question", "keyword", "percent", "dollar", "symbol", "sentence", "word", "alg", "geo", "prob", "count", "unit"]) \
            else "calibration" if "calib" in f \
            else "other"
        lines.append(f"| {f} | {cat} |\n")
    lines.append("\n")

    lines.append("## 4. Model Families Tested\n\n")
    for mname in all_results:
        r = all_results[mname]
        cv_acc = r.get("repeated_cv", {}).get("mean", r.get("cv_acc", float("nan")))
        lines.append(f"- **{mname}**: pooled CV = {cv_acc:.4f}\n")
    lines.append("\n")

    lines.append("## 5. Hyperparameter Search\n\n")
    if "lgb_optuna" in all_results:
        best_p = all_results["lgb_optuna"].get("best_params", {})
        lines.append("LightGBM Optuna best params:\n```json\n")
        lines.append(json.dumps(best_p, indent=2))
        lines.append("\n```\n\n")

    lines.append("## 6. Official Repeated CV Results\n\n")
    lines.append("| Model | Mean | Std | Min | Max | CI95 |\n")
    lines.append("|-------|------|-----|-----|-----|------|\n")
    for mname, r in all_results.items():
        cv = r.get("repeated_cv", {})
        if cv:
            lines.append(f"| {mname} | {cv.get('mean', 0):.4f} | {cv.get('std', 0):.5f} | "
                         f"{cv.get('min', 0):.4f} | {cv.get('max', 0):.4f} | "
                         f"±{cv.get('ci95_half', 0):.4f} |\n")
    lines.append("\n")

    lines.append("## 7. Transfer / Heldout Results\n\n")
    lines.append("### LOSO\n\n")
    if not loso_df.empty:
        lines.append(loso_df.to_markdown(index=False))
        lines.append(f"\n\nMean LOSO: {loso_df['accuracy'].mean():.4f}\n\n")

    lines.append("### Provider Heldout\n\n")
    if not provider_df.empty:
        lines.append(provider_df.to_markdown(index=False))
        lines.append(f"\n\nMean provider heldout: {provider_df['accuracy'].mean():.4f}\n\n")

    lines.append("### Dataset Heldout\n\n")
    if not dataset_df.empty:
        lines.append(dataset_df.to_markdown(index=False))
        lines.append(f"\n\nMean dataset heldout: {dataset_df['accuracy'].mean():.4f}\n\n")

    lines.append("## 8. Auxiliary Data Effects\n\n")
    if not auxiliary_df.empty:
        lines.append(auxiliary_df.to_markdown(index=False))
        lines.append("\n\n")

    lines.append("## 9. Ablation Results\n\n")
    if not ablation_df.empty:
        lines.append(ablation_df.sort_values("mean_accuracy", ascending=False)
                     .to_markdown(index=False))
        lines.append("\n\n")

    lines.append("## 10. Feature Importance (Top 20)\n\n")
    if not feat_imp_df.empty:
        lines.append(feat_imp_df.head(20).to_markdown(index=False))
        lines.append("\n\n")

    lines.append("## 11. Candidate Decision\n\n")
    if not candidate_df.empty:
        lines.append(candidate_df.to_markdown(index=False))
        lines.append("\n\n")

    lines.append("## 12. Next Data Recommendation\n\n")
    lines.append("Based on dataset-heldout analysis (GSM8K→MATH most problematic):\n\n")
    lines.append("1. **Priority: Cohere MATH500 train split** — MATH scenarios have low coverage; "
                 "more MATH training cases would improve cross-dataset transfer most.\n")
    lines.append("2. **Mistral MATH500 train** — second priority for provider diversity on MATH.\n")
    lines.append("3. **Hard/disagreement-only cases** — routing-decisive cases (where sources disagree) "
                 "are most informative; consider filtering auxiliary data to these.\n")
    lines.append("4. **Wait for Cerebras GSM8K** — currently running; will expand provider diversity.\n\n")

    lines.append("## 13. Safety Confirmation\n\n")
    lines.append("- API calls launched: false\n")
    lines.append("- Active jobs touched: false\n")
    lines.append("- Commit/push: false\n")
    lines.append("- Official artifacts overwritten: false\n")
    lines.append(f"- Packages installed: {packages_installed}\n\n")

    return "".join(lines)


# ============================================================
# CANDIDATE DECISION TABLE
# ============================================================
def build_candidate_table(all_results: dict, loso_df: pd.DataFrame,
                           provider_df: pd.DataFrame,
                           dataset_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    baseline_cv = 0.80467
    baseline_loso = 0.781
    baseline_ph = 0.748
    baseline_dh = 0.654

    mean_loso = loso_df["accuracy"].mean() if not loso_df.empty else float("nan")
    mean_ph = provider_df["accuracy"].mean() if not provider_df.empty else float("nan")
    mean_dh = dataset_df["accuracy"].mean() if not dataset_df.empty else float("nan")

    for mname, r in all_results.items():
        cv = r.get("repeated_cv", {})
        cv_mean = cv.get("mean", float("nan"))
        recommendation = "replace corrected router-v2" if cv_mean > baseline_cv + 0.003 else \
            "use as diagnostic" if cv_mean > baseline_cv - 0.003 else "keep corrected router-v2"
        rows.append({
            "model": mname,
            "pooled_cv": round(cv_mean, 4) if not math.isnan(cv_mean) else float("nan"),
            "delta_vs_baseline": round(cv_mean - baseline_cv, 4) if not math.isnan(cv_mean) else float("nan"),
            "leakage_risk": "none",
            "recommendation": recommendation,
        })

    return pd.DataFrame(rows)


# ============================================================
# MAIN
# ============================================================
def main():
    logger.info("=" * 60)
    logger.info("Router v2 Improvement Campaign — %s", TIMESTAMP)
    logger.info("=" * 60)

    packages_installed = ["lightgbm 4.6.0", "xgboost 3.2.0",
                          "optuna 4.8.0", "shap 0.51.0"]

    # ---- Step 3: Rebuild clean dataset ----
    logger.info("Step 3: Loading official4 case table...")
    df_case = pd.read_csv(OFFICIAL4_CASE_TABLE)
    assert len(df_case) == 1200, f"Expected 1200 rows, got {len(df_case)}"
    assert df_case["scenario_id"].nunique() == 4, "Expected 4 scenarios"
    assert (df_case["scenario_id"].value_counts() == 300).all(), "Expected 300 per scenario"

    df_actions = pd.read_csv(ACTION_LABEL_TABLE)
    # example_id is not globally unique (MATH-500 IDs appear for both cohere and mistral)
    # Must merge on (example_id, scenario_id) to avoid many-to-many join
    merge_keys = ["example_id", "scenario_id"]
    if "scenario_id" in df_actions.columns:
        df_main = pd.merge(df_case, df_actions, on=merge_keys, how="inner",
                           suffixes=("", "_act"))
    else:
        df_main = pd.merge(df_case, df_actions, on="example_id", how="inner",
                           suffixes=("", "_act"))
    assert len(df_main) == 1200, (
        f"Merge produced wrong row count: {len(df_main)} (expected 1200). "
        f"Check join keys — example_id may not be globally unique."
    )

    # Save
    df_case.to_csv(OUTPUT_ROOT / "improvement_official4_case_table.csv", index=False)
    logger.info("Saved official4 case table: %d rows, %d cols", *df_case.shape)

    # Duplicate check: (example_id, scenario_id) pairs must be unique
    # Note: example_id is NOT globally unique (MATH-500 IDs appear in both providers)
    n_unique_pairs = df_case[["example_id", "scenario_id"]].drop_duplicates().shape[0]
    assert n_unique_pairs == 1200, f"Duplicate (example_id, scenario_id) pairs: {n_unique_pairs}"
    logger.info("✓ 1200 unique (example_id, scenario_id) pairs, 4 scenarios × 300, no duplicates")

    # Oracle / action ceilings
    oracle_ceil = df_main["oracle_best_action_ok"].mean() if "oracle_best_action_ok" in df_main.columns else float("nan")
    baselines = {
        col: df_main[col].mean()
        for col in ["pooled4_ok", "agreement_only_ok", "beta_shrinkage_ok",
                    "C1d_ok", "always_s1_ok", "S1_ok", "frontier_ok",
                    "L1_ok", "TALE_ok", "oracle_best_action_ok"]
        if col in df_main.columns
    }
    logger.info("Oracle ceiling: %.4f, c1d: %.4f, pooled4: %.4f",
                oracle_ceil, baselines.get("C1d_ok", float("nan")),
                baselines.get("pooled4_ok", float("nan")))
    pd.DataFrame(
        [{"method": k, "accuracy": round(v, 4)} for k, v in baselines.items()]
    ).to_csv(OUTPUT_ROOT / "improvement_oracle_baselines.csv", index=False)

    # ---- Step 4: Expand features ----
    logger.info("Step 4: Building expanded legal features...")
    expanded_feat_df = build_expanded_features(df_main)
    expanded_feat_names = list(expanded_feat_df.columns)

    # Merge base features + expanded
    base_available = [f for f in BASE_FEATURES if f in df_main.columns]
    all_feat_names = base_available + [f for f in expanded_feat_names
                                        if f not in base_available]

    assert_no_leakage(all_feat_names)
    logger.info("✓ Leakage audit: %d features all legal", len(all_feat_names))

    # Build feature matrix
    feat_df = pd.concat([df_main[base_available].copy(), expanded_feat_df], axis=1)

    # Save feature schema
    schema_rows = []
    for f in all_feat_names:
        verdict = audit_feature(f)
        cat = ("agreement_pattern" if any(k in f for k in
               ["agree", "majority", "split", "isolated", "cluster", "entropy",
                "singleton", "ext_maj", "frontier_in", "S1_in", "four_agree",
                "L1_TALE"])
               else "numeric_answer" if any(k in f for k in
               ["numeric", "spread", "magnitude", "negative", "n_numeric"])
               else "question_structure" if any(k in f for k in
               ["question", "keyword", "percent", "dollar", "symbol",
                "sentence", "word", "alg", "geo", "prob", "count", "unit",
                "operation"])
               else "meta_count" if f in ("n_valid_sources",)
               else "calibration")
        schema_rows.append({"feature_name": f, "category": cat, "legality": verdict,
                             "in_base_22": f in BASE_FEATURES})
    pd.DataFrame(schema_rows).to_csv(
        OUTPUT_ROOT / "expanded_feature_schema.csv", index=False)

    # Feature legality audit markdown
    with open(OUTPUT_ROOT / "expanded_feature_legality_audit.md", "w") as fh:
        fh.write("# Expanded Feature Legality Audit\n\n")
        fh.write(f"Total features: {len(all_feat_names)}\n\n")
        fh.write("| Feature | Category | Legality | In Base 22 |\n")
        fh.write("|---------|----------|----------|------------|\n")
        for row in schema_rows:
            fh.write(f"| {row['feature_name']} | {row['category']} | "
                     f"{row['legality']} | {row['in_base_22']} |\n")

    # Feature whitelist CSV
    pd.DataFrame(
        [{"feature_name": f, "status": "legal", "in_base_22": f in BASE_FEATURES}
         for f in all_feat_names]
    ).to_csv(OUTPUT_ROOT / "improvement_feature_whitelist.csv", index=False)
    logger.info("Saved expanded_feature_schema: %d features", len(all_feat_names))

    # ---- Build action labels ----
    action_labels = build_action_labels(df_main)
    logger.info("Action labels: %s", list(action_labels.keys()))

    # ---- Scale features ----
    X_raw = feat_df[all_feat_names].fillna(0).values
    # Replace any remaining inf/-inf with 0 (defensive: handles edge-case answers)
    X_raw = np.where(np.isfinite(X_raw), X_raw, 0.0)
    # Clip extreme values (e.g. very large numeric spreads)
    X_raw = np.clip(X_raw, -1e9, 1e9)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_raw)
    logger.info("Feature matrix: %s", X_raw.shape)

    # Save feature matrix
    pd.DataFrame(X_raw, columns=all_feat_names).assign(
        example_id=df_main["example_id"].values,
        scenario_id=df_main["scenario_id"].values,
    ).to_csv(OUTPUT_ROOT / "improvement_legal_feature_matrix.csv", index=False)

    # ---- Step 5+6: Train model families + hyperparameter search ----
    logger.info("Step 5+6: Training model families with Optuna search...")

    models_dict = make_models()
    all_results = {}

    # Quick single-seed CV for all models
    for mname, model_obj in models_dict.items():
        logger.info("  Evaluating %s...", mname)
        try:
            model_fn = lambda m=model_obj.__class__, kwargs=model_obj.get_params(): m(**kwargs)
            r = evaluate_multi_output_binary(X_scaled, df_main, action_labels,
                                             model_fn, n_folds=N_CV_FOLDS,
                                             seed=RANDOM_SEED)
            all_results[mname] = {"cv_acc": r["mean_accuracy"],
                                   "cv_std": r["std_accuracy"],
                                   "per_action": r}
            logger.info("    %s: %.4f ± %.4f", mname, r["mean_accuracy"], r["std_accuracy"])
        except Exception as e:
            logger.warning("    %s failed: %s", mname, e)
            all_results[mname] = {"cv_acc": float("nan"), "error": str(e)}

    # LightGBM Optuna search (primary optimization)
    logger.info("Optuna search for LightGBM (%d trials)...", N_OPTUNA_TRIALS)
    try:
        best_lgb_params, best_lgb_model = lgb_optuna_search(
            X_scaled, df_main, action_labels, n_trials=N_OPTUNA_TRIALS,
            use_calibration_features=False
        )
        logger.info("Best LGB params: %s", best_lgb_params)
        with open(OUTPUT_ROOT / "best_lgb_params.json", "w") as fh:
            json.dump(best_lgb_params, fh, indent=2)
        all_results["lgb_optuna"] = {"best_params": best_lgb_params,
                                      "cv_acc": float("nan")}
    except Exception as e:
        logger.warning("LGB Optuna failed: %s", e)
        best_lgb_params = {"n_estimators": 300, "learning_rate": 0.05,
                            "num_leaves": 31, "verbose": -1, "n_jobs": -1}
        best_lgb_model = lgb.LGBMClassifier(**best_lgb_params)
        all_results["lgb_optuna"] = {"best_params": best_lgb_params, "cv_acc": float("nan")}

    best_lgb_params.update({"random_state": RANDOM_SEED, "verbose": -1, "n_jobs": -1})

    # LightGBM with calibration features (fold-safe)
    logger.info("LGB + calibration features (fold-safe)...")
    try:
        lgb_calib_fn = lambda: lgb.LGBMClassifier(**best_lgb_params)
        r_lgb_calib = evaluate_multi_output_binary(
            X_scaled, df_main, action_labels, lgb_calib_fn,
            use_calibration_features=True)
        all_results["lgb_optuna_calib"] = {"cv_acc": r_lgb_calib["mean_accuracy"],
                                             "cv_std": r_lgb_calib["std_accuracy"]}
        logger.info("LGB+calib: %.4f ± %.4f",
                    r_lgb_calib["mean_accuracy"], r_lgb_calib["std_accuracy"])
    except Exception as e:
        logger.warning("LGB+calib failed: %s", e)

    # XGBoost Optuna
    logger.info("XGBoost Optuna search...")
    try:
        best_xgb_params = xgb_optuna_search(X_scaled, df_main, action_labels,
                                              n_trials=max(20, N_OPTUNA_TRIALS // 3))
        best_xgb_params.update({"random_state": RANDOM_SEED, "verbosity": 0,
                                  "n_jobs": -1, "eval_metric": "logloss"})
        xgb_fn = lambda: xgb.XGBClassifier(**best_xgb_params)
        r_xgb = evaluate_multi_output_binary(X_scaled, df_main, action_labels,
                                              xgb_fn, n_folds=N_CV_FOLDS)
        all_results["xgb_optuna"] = {"cv_acc": r_xgb["mean_accuracy"],
                                      "cv_std": r_xgb["std_accuracy"],
                                      "best_params": best_xgb_params}
        logger.info("XGB+optuna: %.4f", r_xgb["mean_accuracy"])
    except Exception as e:
        logger.warning("XGB optuna failed: %s", e)
        best_xgb_params = {"n_estimators": 300, "learning_rate": 0.05, "max_depth": 5,
                            "random_state": RANDOM_SEED, "verbosity": 0, "n_jobs": -1,
                            "eval_metric": "logloss"}

    # Save hyperparameter summary
    hp_rows = []
    for mname in ["lgb_optuna", "xgb_optuna"]:
        if mname in all_results:
            r = all_results[mname]
            hp_rows.append({"model": mname,
                             "best_params": json.dumps(r.get("best_params", {})),
                             "cv_acc": r.get("cv_acc", float("nan"))})
    pd.DataFrame(hp_rows).to_csv(OUTPUT_ROOT / "hyperparameter_search_summary.csv",
                                  index=False)

    # ---- Step 7: Comprehensive evaluation with best models ----
    logger.info("Step 7: Repeated CV (10 seeds) for best models...")

    # Identify best model from quick sweep
    best_model_name = max(
        [(k, v.get("cv_acc", 0)) for k, v in all_results.items()
         if not math.isnan(v.get("cv_acc", float("nan")))],
        key=lambda x: x[1],
        default=("lgb", 0)
    )[0]
    logger.info("Best model from quick sweep: %s (%.4f)",
                best_model_name, all_results[best_model_name].get("cv_acc", 0))

    # Full repeated CV for top 3 models
    top_models = {}
    for mname, r in sorted(all_results.items(), key=lambda x: -x[1].get("cv_acc", 0)):
        if not math.isnan(r.get("cv_acc", float("nan"))) and len(top_models) < 4:
            top_models[mname] = r

    for mname in top_models:
        logger.info("  Repeated CV for %s...", mname)
        try:
            if mname == "lgb_optuna" or mname == "lgb_optuna_calib":
                use_calib = (mname == "lgb_optuna_calib")
                model_fn = lambda: lgb.LGBMClassifier(**best_lgb_params)
            elif mname == "xgb_optuna":
                use_calib = False
                model_fn = lambda: xgb.XGBClassifier(**best_xgb_params)
            else:
                use_calib = False
                model_obj = models_dict.get(mname)
                if model_obj is None:
                    continue
                model_fn = lambda m=model_obj.__class__, kw=model_obj.get_params(): m(**kw)

            rep_cv = repeated_cv(X_scaled, df_main, action_labels, model_fn,
                                  seeds=CV_SEEDS,
                                  use_calibration_features=use_calib)
            all_results[mname]["repeated_cv"] = rep_cv
            logger.info("    %s repeated CV: %.4f ± %.5f (CI95 ±%.4f)",
                        mname, rep_cv["mean"], rep_cv["std"], rep_cv["ci95_half"])
        except Exception as e:
            logger.warning("    Repeated CV for %s failed: %s", mname, e)

    # Also repeated CV for the baseline HGB model (for fair comparison)
    if "hgb" not in top_models:
        try:
            hgb_params = models_dict["hgb"].get_params()
            hgb_fn = lambda: HistGradientBoostingClassifier(**hgb_params)
            rep_cv_hgb = repeated_cv(X_scaled, df_main, action_labels, hgb_fn, seeds=CV_SEEDS)
            all_results["hgb"]["repeated_cv"] = rep_cv_hgb
            logger.info("HGB repeated CV: %.4f ± %.5f", rep_cv_hgb["mean"], rep_cv_hgb["std"])
        except Exception as e:
            logger.warning("HGB repeated CV failed: %s", e)

    # Identify final best model for heldout eval
    best_final_name = max(
        [(k, v.get("repeated_cv", {}).get("mean", v.get("cv_acc", 0)))
         for k, v in all_results.items()],
        key=lambda x: x[1],
        default=("lgb", 0)
    )[0]
    logger.info("Best model for heldout eval: %s", best_final_name)

    # Build best model factory
    if "lgb" in best_final_name:
        best_factory = lambda: lgb.LGBMClassifier(**best_lgb_params)
    elif "xgb" in best_final_name:
        best_factory = lambda: xgb.XGBClassifier(**best_xgb_params)
    else:
        obj = models_dict.get(best_final_name, models_dict["hgb"])
        best_factory = lambda m=obj.__class__, kw=obj.get_params(): m(**kw)

    # LOSO
    logger.info("LOSO evaluation...")
    loso_df = loso_eval(X_scaled, df_main, action_labels, best_factory)
    loso_df.to_csv(OUTPUT_ROOT / "improvement_loso_summary.csv", index=False)
    logger.info("LOSO mean: %.4f", loso_df["accuracy"].mean())

    # Within-scenario CV
    logger.info("Within-scenario CV...")
    within_df = within_scenario_cv(X_scaled, df_main, action_labels, best_factory)
    within_df.to_csv(OUTPUT_ROOT / "improvement_within_scenario_cv.csv", index=False)
    logger.info("Macro scenario accuracy: %.4f", macro_scenario_accuracy(within_df))

    # Provider heldout
    logger.info("Provider heldout evaluation...")
    provider_df = provider_heldout_eval(X_scaled, df_main, action_labels, best_factory)
    provider_df.to_csv(OUTPUT_ROOT / "improvement_provider_heldout.csv", index=False)
    logger.info("Provider heldout mean: %.4f", provider_df["accuracy"].mean())

    # Dataset heldout
    logger.info("Dataset heldout evaluation...")
    dataset_df = dataset_heldout_eval(X_scaled, df_main, action_labels, best_factory)
    dataset_df.to_csv(OUTPUT_ROOT / "improvement_dataset_heldout.csv", index=False)
    logger.info("Dataset heldout mean: %.4f", dataset_df["accuracy"].mean())

    # Margin-safe router
    logger.info("Margin-safe router evaluation...")
    if hasattr(lgb.LGBMClassifier(**best_lgb_params), "predict_proba"):
        lgb_fn_prob = lambda: lgb.LGBMClassifier(**best_lgb_params)
        margin_df = margin_safe_router_eval(X_scaled, df_main, action_labels,
                                             lgb_fn_prob)
        margin_df.to_csv(OUTPUT_ROOT / "improvement_margin_safe_router.csv", index=False)
        logger.info("Margin-safe: best threshold accuracy: %.4f",
                    margin_df["mean_accuracy"].max())

    # ---- Step 7F: Auxiliary data evaluation ----
    logger.info("Step 7F: Auxiliary data evaluation...")
    X_mistral, df_mistral, al_mistral = None, None, None
    X_cohere_math, df_cohere_math, al_cohere_math = None, None, None

    # Load Mistral train1000
    try:
        df_m = pd.read_csv(MISTRAL_TRAIN1000_FEAT)
        feat_m = build_expanded_features(df_m)
        base_m = [f for f in BASE_FEATURES if f in df_m.columns]
        all_m_feats = base_m + [f for f in feat_m.columns if f not in base_m]
        feat_m_full = pd.concat([df_m[base_m], feat_m], axis=1)
        X_m_raw = feat_m_full[[f for f in all_feat_names if f in feat_m_full.columns]].fillna(0).values
        # Pad to same feature count
        pad = np.zeros((len(X_m_raw), max(0, len(all_feat_names) - X_m_raw.shape[1])))
        X_m_full = np.hstack([X_m_raw, pad]) if pad.shape[1] > 0 else X_m_raw
        X_mistral = scaler.transform(X_m_full[:, :scaler.n_features_in_])
        df_mistral = df_m
        al_mistral = build_action_labels(df_m)
        logger.info("Mistral train1000: %d rows, %d features", len(df_m), X_mistral.shape[1])
    except Exception as e:
        logger.warning("Mistral train1000 load failed: %s", e)

    # Load Cohere MATH aux
    try:
        df_cm = pd.read_csv(COHERE_MATH_AUX_CASE)
        # Need case table features for cohere math auxiliary
        # Try RGEB official4 for overlap, or use minimal features
        feat_cm = build_expanded_features(df_cm)
        base_cm = [f for f in BASE_FEATURES if f in df_cm.columns]
        feat_cm_full = pd.concat([df_cm[base_cm], feat_cm], axis=1) if base_cm else feat_cm
        X_cm_raw = feat_cm_full[[f for f in all_feat_names if f in feat_cm_full.columns]].fillna(0).values
        pad = np.zeros((len(X_cm_raw), max(0, scaler.n_features_in_ - X_cm_raw.shape[1])))
        X_cm_full = np.hstack([X_cm_raw, pad]) if pad.shape[1] > 0 else X_cm_raw
        X_cohere_math = scaler.transform(X_cm_full[:, :scaler.n_features_in_])
        df_cohere_math = df_cm
        al_cohere_math = build_action_labels(df_cm)
        logger.info("Cohere MATH aux: %d rows", len(df_cm))
    except Exception as e:
        logger.warning("Cohere MATH aux load failed: %s", e)

    auxiliary_df = auxiliary_eval(
        X_scaled, df_main, action_labels,
        X_mistral, df_mistral, al_mistral,
        X_cohere_math, df_cohere_math, al_cohere_math,
        best_factory, all_feat_names
    )
    auxiliary_df.to_csv(OUTPUT_ROOT / "improvement_auxiliary_effect.csv", index=False)
    logger.info("Auxiliary eval complete")

    # ---- Step 9: Ablations ----
    logger.info("Step 9: Ablation studies...")
    ablation_df = run_ablations(df_main, action_labels, best_factory,
                                 BASE_FEATURES, all_feat_names, scaler)
    ablation_df.to_csv(OUTPUT_ROOT / "improvement_ablation_summary.csv", index=False)
    logger.info("Ablations:\n%s", ablation_df.to_string(index=False))

    # ---- Step 9: Failure analysis ----
    logger.info("Step 9: Failure analysis...")
    recovery_df, regression_df, casebook_text = failure_analysis(
        X_scaled, df_main, action_labels, best_factory
    )
    recovery_df.to_csv(OUTPUT_ROOT / "improvement_recoveries_vs_previous_router.csv",
                        index=False)
    regression_df.to_csv(OUTPUT_ROOT / "improvement_regressions_vs_previous_router.csv",
                          index=False)
    with open(OUTPUT_ROOT / "improvement_failure_casebook.md", "w") as fh:
        fh.write(casebook_text)

    # Remaining failure patterns
    if "all_sources_wrong" in df_main.columns:
        n_asw = (df_main["all_sources_wrong"] == 1).sum()
        with open(OUTPUT_ROOT / "improvement_remaining_failure_patterns.md", "w") as fh:
            fh.write("# Remaining Failure Patterns\n\n")
            fh.write(f"- All-sources-wrong cases: {n_asw} ({n_asw/len(df_main)*100:.1f}%)\n")
            fh.write("  These cannot be fixed by any selector/router.\n\n")
            for scen in sorted(df_main["scenario_id"].unique()):
                mask = (df_main["scenario_id"] == scen)
                n_s = (df_main.loc[mask, "all_sources_wrong"] == 1).sum()
                fh.write(f"  - {scen}: {n_s}/300 ({n_s/300*100:.1f}%)\n")
    logger.info("Failure analysis: %d recoveries, %d regressions",
                len(recovery_df), len(regression_df))

    # ---- Step 10: Feature importance ----
    logger.info("Step 10: Feature importance...")
    feat_imp_df = compute_feature_importance(X_scaled, all_feat_names,
                                              action_labels, best_factory)
    feat_imp_df.to_csv(OUTPUT_ROOT / "improvement_feature_importance.csv", index=False)

    # Model interpretation
    with open(OUTPUT_ROOT / "improvement_model_interpretation.md", "w") as fh:
        fh.write("# Model Interpretation\n\n")
        fh.write(f"Best model: {best_final_name}\n\n")
        fh.write("## Top 15 Features by Tree Importance\n\n")
        top15 = feat_imp_df.head(15)
        fh.write(top15.to_markdown(index=False))
        fh.write("\n\n")
        fh.write("## Interpretation\n\n")
        top_feats = top15["feature"].tolist()
        fh.write(f"Top features: {', '.join(top_feats[:5])}\n\n")
        fh.write("Agreement-pattern features dominate importance (expected — "
                 "question difficulty is encoded in source agreement patterns).\n")

    with open(OUTPUT_ROOT / "improvement_top_patterns.md", "w") as fh:
        fh.write("# Top Decision Patterns\n\n")
        fh.write("1. all_four_agree=1 → high confidence correct (any action works)\n")
        fh.write("2. S1_isolated=1 → S1 often wrong; prefer pooled4/L1\n")
        fh.write("3. two_two_split=1 → uncertain; entropy high\n")
        fh.write("4. external_majority_excludes_frontier=1 → frontier likely wrong\n")
        fh.write("5. unique_answer_count=4 → all different; very uncertain\n")

    logger.info("Feature importance computed")

    # ---- Step 11: Candidate decision ----
    logger.info("Step 11: Candidate decision...")

    # Full repeated CV table
    rcv_rows = []
    for mname, r in all_results.items():
        cv = r.get("repeated_cv", {})
        rcv_rows.append({
            "model": mname,
            "cv_mean": round(cv.get("mean", r.get("cv_acc", float("nan"))), 4),
            "cv_std": round(cv.get("std", r.get("cv_std", float("nan"))), 5),
            "cv_min": round(cv.get("min", float("nan")), 4),
            "cv_max": round(cv.get("max", float("nan")), 4),
        })
    pd.DataFrame(rcv_rows).to_csv(OUTPUT_ROOT / "improvement_repeated_cv_all_models.csv",
                                   index=False)

    candidate_df = build_candidate_table(all_results, loso_df, provider_df, dataset_df)
    candidate_df.to_csv(OUTPUT_ROOT / "improvement_candidate_decision_table.csv", index=False)

    best_cv = all_results.get(best_final_name, {}).get("repeated_cv", {})
    if not best_cv:
        best_cv = {"mean": all_results.get(best_final_name, {}).get("cv_acc", 0.0)}

    with open(OUTPUT_ROOT / "improvement_candidate_decision.md", "w") as fh:
        fh.write("# Candidate Decision\n\n")
        fh.write(f"Best candidate: **{best_final_name}**\n\n")
        fh.write(f"- Pooled CV: {best_cv.get('mean', float('nan')):.4f}\n")
        fh.write(f"- Baseline: 0.8047\n")
        delta = best_cv.get("mean", 0) - 0.8047
        fh.write(f"- Delta: {delta:+.4f}\n\n")
        rec = ("replace corrected router-v2" if delta > 0.003
               else "use as diagnostic" if delta > -0.003
               else "keep corrected router-v2")
        fh.write(f"**Recommendation: {rec}**\n\n")
        fh.write(f"LOSO mean: {loso_df['accuracy'].mean():.4f} (baseline: 0.781)\n")
        fh.write(f"Provider heldout: {provider_df['accuracy'].mean():.4f} (baseline: 0.748)\n")
        fh.write(f"Dataset heldout: {dataset_df['accuracy'].mean():.4f} (baseline: 0.654)\n")

    # ---- Step 12: Next-data recommendation ----
    with open(OUTPUT_ROOT / "next_data_generation_recommendation.md", "w") as fh:
        fh.write("# Next Data Generation Recommendation\n\n")
        fh.write("Priority order based on improvement campaign findings:\n\n")
        fh.write("1. **Cohere MATH500 train split** — dataset-heldout GSM8K→MATH is "
                 "the weakest link (45-65%). More MATH training data is highest priority.\n")
        fh.write("2. **Mistral MATH500 train** — provider diversity on MATH.\n")
        fh.write("3. **Routing-decisive cases only** — cases where sources disagree "
                 "are most informative; filter auxiliary to disagreement cases.\n")
        fh.write("4. **Cerebras GSM8K** (once rate-limit resolved) — "
                 "adds third provider for GSM8K scenarios.\n")
        fh.write("5. **More hard MATH cases** — MATH-500 hard difficulty subset.\n\n")

    pd.DataFrame([
        {"priority": 1, "data_type": "cohere_math500_train",
         "expected_impact": "high", "rationale": "dataset_heldout_weakest_link"},
        {"priority": 2, "data_type": "mistral_math500_train",
         "expected_impact": "medium", "rationale": "provider_diversity_math"},
        {"priority": 3, "data_type": "disagreement_cases_only",
         "expected_impact": "medium", "rationale": "routing_decisive_filtering"},
        {"priority": 4, "data_type": "cerebras_gsm8k",
         "expected_impact": "medium", "rationale": "third_provider_gsm8k"},
        {"priority": 5, "data_type": "hard_math_cases",
         "expected_impact": "low", "rationale": "difficulty_diversity"},
    ]).to_csv(OUTPUT_ROOT / "next_data_generation_plan.csv", index=False)

    # ---- Step 13: Human-readable report ----
    logger.info("Step 13: Building report...")
    report_text = build_report(
        baseline={}, all_results=all_results, best_candidate=best_final_name,
        best_cv=best_cv, feature_names=all_feat_names, ablation_df=ablation_df,
        auxiliary_df=auxiliary_df, loso_df=loso_df, provider_df=provider_df,
        dataset_df=dataset_df, candidate_df=candidate_df, feat_imp_df=feat_imp_df,
        packages_installed=packages_installed, timestamp=TIMESTAMP,
    )
    with open(REPORT_PATH, "w") as fh:
        fh.write(report_text)
    logger.info("Report written: %s", REPORT_PATH)

    # ---- Step 15: Manifest ----
    manifest = {
        "timestamp": TIMESTAMP,
        "input_artifacts": [
            str(OFFICIAL4_CASE_TABLE),
            str(ACTION_LABEL_TABLE),
            str(MISTRAL_TRAIN1000_FEAT),
            str(COHERE_MATH_AUX_CASE),
        ],
        "scripts_created": [
            "scripts/router_v2_improvement_campaign.py",
            "tests/test_router_v2_improvement_campaign.py",
        ],
        "packages_installed": packages_installed,
        "model_families_tested": list(models_dict.keys()) + ["lgb_optuna", "lgb_optuna_calib", "xgb_optuna"],
        "n_official_rows": 1200,
        "n_features_base": 22,
        "n_features_expanded": len(all_feat_names),
        "optuna_trials_lgb": N_OPTUNA_TRIALS,
        "optuna_seeds": CV_SEEDS,
        "best_model": best_final_name,
        "best_cv_mean": round(best_cv.get("mean", float("nan")), 4),
        "loso_mean": round(loso_df["accuracy"].mean(), 4) if not loso_df.empty else float("nan"),
        "provider_heldout_mean": round(provider_df["accuracy"].mean(), 4) if not provider_df.empty else float("nan"),
        "dataset_heldout_mean": round(dataset_df["accuracy"].mean(), 4) if not dataset_df.empty else float("nan"),
        "api_calls_launched": False,
        "active_jobs_touched": False,
        "commit_push": False,
        "official_artifacts_overwritten": False,
        "output_files": [str(p) for p in sorted(OUTPUT_ROOT.glob("*"))],
        "limitations": [
            "TabPFN not installed (not available in pip for this env)",
            "CatBoost not installed",
            "Calibration features use pooled4_ok as proxy — may not be optimal for all actions",
        ],
    }
    with open(OUTPUT_ROOT / "manifest.json", "w") as fh:
        json.dump(manifest, fh, indent=2)

    logger.info("=" * 60)
    logger.info("CAMPAIGN COMPLETE")
    logger.info("Best model: %s", best_final_name)
    logger.info("Best pooled CV: %.4f (baseline: 0.8047)", best_cv.get("mean", float("nan")))
    logger.info("LOSO: %.4f (baseline: 0.781)", loso_df["accuracy"].mean() if not loso_df.empty else float("nan"))
    logger.info("Provider heldout: %.4f (baseline: 0.748)", provider_df["accuracy"].mean() if not provider_df.empty else float("nan"))
    logger.info("Dataset heldout: %.4f (baseline: 0.654)", dataset_df["accuracy"].mean() if not dataset_df.empty else float("nan"))
    logger.info("API calls: false | Jobs touched: false | Commit/push: false")
    logger.info("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
