#!/usr/bin/env python3
"""Job D3: conservative override / baseline-guarded selector.

Offline-only. Uses existing artifacts and no API calls.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import subprocess
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss, roc_auc_score
from sklearn.model_selection import GroupKFold


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def slug_now() -> str:
    return datetime.now(timezone.utc).strftime("run_%Y%m%dT%H%M%SZ")


def clean_text(x: Any) -> str:
    if x is None:
        return ""
    if isinstance(x, float) and math.isnan(x):
        return ""
    return str(x)


def bool_int(x: Any) -> int:
    if isinstance(x, bool):
        return int(x)
    s = clean_text(x).strip().lower()
    if s in {"1", "true", "yes"}:
        return 1
    if s in {"0", "false", "no", ""}:
        return 0
    try:
        return int(float(s) != 0.0)
    except Exception:
        return 0


def ensure_run_dir(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    run = root / slug_now()
    run.mkdir(parents=True, exist_ok=False)
    return run


def run_command(cmd: str) -> str:
    p = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return f"$ {cmd}\n{p.stdout}{p.stderr}\n"


def has_pkg(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def md_table(df: pd.DataFrame, title: str) -> str:
    lines = [f"# {title}", ""]
    if df.empty:
        lines.append("(no rows)")
        return "\n".join(lines) + "\n"
    cols = list(df.columns)
    lines.append("| " + " | ".join(cols) + " |")
    lines.append("|" + "|".join(["---"] * len(cols)) + "|")
    for _, r in df.iterrows():
        vals = []
        for c in cols:
            v = r[c]
            if isinstance(v, float):
                vals.append(f"{v:.6f}")
            else:
                vals.append(clean_text(v))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines) + "\n"


def mcnemar_pvalue(b: int, c: int) -> float:
    if b + c == 0:
        return 1.0
    if has_pkg("scipy"):
        from scipy.stats import binomtest

        return float(binomtest(min(b, c), n=b + c, p=0.5, alternative="two-sided").pvalue)
    stat = (abs(b - c) - 1) ** 2 / (b + c)
    return float(math.exp(-0.5 * stat))


def bootstrap_ci_diff(a: np.ndarray, b: np.ndarray, n_boot: int = 2000, seed: int = 42) -> tuple[float, float, float]:
    if len(a) == 0:
        return float("nan"), float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    idx = np.arange(len(a))
    deltas = []
    for _ in range(n_boot):
        s = rng.choice(idx, size=len(idx), replace=True)
        deltas.append(float(a[s].mean() - b[s].mean()))
    deltas = np.array(deltas)
    return float(np.mean(deltas)), float(np.quantile(deltas, 0.025)), float(np.quantile(deltas, 0.975))


METHOD_ID_BY_ALIAS = {
    "frontier": "direct_reserve_semantic_frontier_v2",
    "s1": "external_s1_budget_forcing",
    "l1": "external_l1_max",
    "tale": "external_tale_prompt_budgeting",
}

METHOD_ALIAS_BY_ID = {v: k for k, v in METHOD_ID_BY_ALIAS.items()}

VALID_BASELINE_POLICIES = [
    "select_frontier_correct",
    "select_l1_correct",
    "select_s1_correct",
    "select_tale_correct",
    "pooled4_plurality_correct",
    "agreement_largest_cluster_correct",
    "agreement_strict_2plus_correct",
]


def policy_to_method_and_correct(pool_row: pd.Series, policy: str) -> tuple[str, int]:
    if policy == "select_frontier_correct":
        return METHOD_ID_BY_ALIAS["frontier"], int(pool_row.get("select_frontier_correct", 0))
    if policy == "select_l1_correct":
        return METHOD_ID_BY_ALIAS["l1"], int(pool_row.get("select_l1_correct", 0))
    if policy == "select_s1_correct":
        return METHOD_ID_BY_ALIAS["s1"], int(pool_row.get("select_s1_correct", 0))
    if policy == "select_tale_correct":
        return METHOD_ID_BY_ALIAS["tale"], int(pool_row.get("select_tale_correct", 0))

    if policy == "pooled4_plurality_correct":
        alias = clean_text(pool_row.get("pooled4_plurality_selected_method", "frontier")).strip().lower()
        return METHOD_ID_BY_ALIAS.get(alias, METHOD_ID_BY_ALIAS["frontier"]), int(pool_row.get("pooled4_plurality_correct", 0))

    if policy == "agreement_largest_cluster_correct":
        alias = clean_text(pool_row.get("agreement_largest_cluster_selected_method", "frontier")).strip().lower()
        return METHOD_ID_BY_ALIAS.get(alias, METHOD_ID_BY_ALIAS["frontier"]), int(pool_row.get("agreement_largest_cluster_correct", 0))

    if policy == "agreement_strict_2plus_correct":
        alias = clean_text(pool_row.get("agreement_strict_2plus_selected_method", "frontier")).strip().lower()
        return METHOD_ID_BY_ALIAS.get(alias, METHOD_ID_BY_ALIAS["frontier"]), int(pool_row.get("agreement_strict_2plus_correct", 0))

    return METHOD_ID_BY_ALIAS["frontier"], int(pool_row.get("select_frontier_correct", 0))


def safe_float(x: Any, default: float = 0.0) -> float:
    try:
        if pd.isna(x):
            return default
        return float(x)
    except Exception:
        return default


def pick_default_policies(
    corr_pool: pd.DataFrame,
    corrected_eval: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    scenarios = sorted(corr_pool["scenario_id"].dropna().unique().tolist())

    for scen in scenarios:
        sub = corr_pool[corr_pool["scenario_id"] == scen].copy()
        source_split = ""
        source = pd.DataFrame()
        fallback_reason = ""

        if len(sub[sub["split"] == "validation"]) > 0:
            source_split = "validation"
            source = sub[sub["split"] == "validation"].copy()
        elif len(sub[sub["split"] == "train"]) > 0:
            source_split = "train"
            source = sub[sub["split"] == "train"].copy()
        else:
            source_split = "fallback_corrected_eval"
            fallback_reason = "validation/train unavailable"

        best_policy = "select_frontier_correct"
        best_acc = float("nan")

        if len(source):
            vals = {}
            for p in VALID_BASELINE_POLICIES:
                if p in source.columns:
                    vals[p] = float(source[p].mean())
            if vals:
                best_acc = max(vals.values())
                best_policy = sorted([k for k, v in vals.items() if np.isclose(v, best_acc)])[0]
        else:
            # fallback to corrected eval table
            csub = corrected_eval[corrected_eval["scenario_id"] == scen].copy()
            if len(csub):
                nm = clean_text(csub["corrected_best_fixed_baseline"].iloc[0]).split(";")[0]
                if nm in VALID_BASELINE_POLICIES:
                    best_policy = nm
                best_acc = safe_float(csub["baseline_accuracy"].iloc[0], float("nan"))
                fallback_reason = fallback_reason or "from corrected evaluation summary"

        rows.append(
            {
                "scenario_id": scen,
                "provider": clean_text(sub["provider"].iloc[0]) if len(sub) else "",
                "dataset": clean_text(sub["dataset"].iloc[0]) if len(sub) else "",
                "selection_split": source_split,
                "default_policy": best_policy,
                "default_policy_validation_accuracy": best_acc,
                "fallback_reason": fallback_reason,
            }
        )

    return pd.DataFrame(rows).sort_values(["provider", "dataset"]).reset_index(drop=True)


def add_fold_safe_reliability(cand: pd.DataFrame) -> tuple[pd.DataFrame, list[str], str]:
    df = cand.copy()
    df["candidate_correct"] = df["candidate_correct"].map(bool_int)

    rel_cols = [
        "rel_method_acc_trainfold",
        "rel_provider_method_acc_trainfold",
        "rel_scenario_method_acc_trainfold",
    ]
    for c in rel_cols:
        df[c] = np.nan

    train = df[df["split"] == "train"].copy()
    if len(train) == 0:
        for c in rel_cols:
            df[c] = 0.5
        return df, rel_cols, "No train rows; reliability features defaulted to 0.5"

    global_rate = float(train["candidate_correct"].mean())

    def map_rates(src: pd.DataFrame) -> tuple[dict[Any, float], dict[Any, float], dict[Any, float]]:
        m1 = src.groupby("method")["candidate_correct"].mean().to_dict()
        m2 = src.groupby(["provider", "method"])["candidate_correct"].mean().to_dict()
        m3 = src.groupby(["scenario_id", "method"])["candidate_correct"].mean().to_dict()
        return m1, m2, m3

    # OOF for train by pool_id
    train_idx = train.index.to_numpy()
    groups = train["pool_id"].to_numpy()
    n_unique_groups = len(pd.unique(groups))
    n_splits = max(2, min(5, n_unique_groups))

    if n_unique_groups >= 2:
        gkf = GroupKFold(n_splits=n_splits)
        for tr_rel, va_rel in gkf.split(train_idx, groups=groups):
            rel_src = train.iloc[tr_rel].copy()
            va_rows = train.iloc[va_rel].copy()
            m1, m2, m3 = map_rates(rel_src)

            vals1 = []
            vals2 = []
            vals3 = []
            for _, r in va_rows.iterrows():
                vals1.append(safe_float(m1.get(r["method"], global_rate), global_rate))
                vals2.append(safe_float(m2.get((r["provider"], r["method"]), m1.get(r["method"], global_rate)), global_rate))
                vals3.append(safe_float(m3.get((r["scenario_id"], r["method"]), m1.get(r["method"], global_rate)), global_rate))
            df.loc[va_rows.index, "rel_method_acc_trainfold"] = vals1
            df.loc[va_rows.index, "rel_provider_method_acc_trainfold"] = vals2
            df.loc[va_rows.index, "rel_scenario_method_acc_trainfold"] = vals3

    # train-full maps for non-train
    m1f, m2f, m3f = map_rates(train)
    nontrain = df["split"] != "train"
    for idx, r in df[nontrain].iterrows():
        v1 = safe_float(m1f.get(r["method"], global_rate), global_rate)
        v2 = safe_float(m2f.get((r["provider"], r["method"]), v1), v1)
        v3 = safe_float(m3f.get((r["scenario_id"], r["method"]), v1), v1)
        df.at[idx, "rel_method_acc_trainfold"] = v1
        df.at[idx, "rel_provider_method_acc_trainfold"] = v2
        df.at[idx, "rel_scenario_method_acc_trainfold"] = v3

    for c in rel_cols:
        df[c] = df[c].fillna(global_rate).astype(float)

    rep = "\n".join(
        [
            "# D3 Reliability Feature Report",
            "",
            "Fold-safe reliability features created:",
            "- Train rows: OOF GroupKFold by pool_id",
            "- Non-train rows: train-only maps",
            f"- Reliability columns: {', '.join(rel_cols)}",
            f"- Train global correct rate: {global_rate:.6f}",
        ]
    ) + "\n"
    return df, rel_cols, rep


def choose_feature_columns(df: pd.DataFrame) -> tuple[list[str], list[str], list[str]]:
    forbidden = {
        "candidate_correct",
        "candidate_correct_exact",
        "candidate_correct_combined",
        "gold_answer_for_labeling_only",
        "oracle_available",
        "all_sources_wrong",
        "correct_answer_cluster_id",
        "correct_methods_json",
        "source_correct_vector_json",
        "candidate_is_unique_correct",
        "candidate_in_correct_cluster",
        "example_uid",
        "original_example_id",
        "question_hash",
        "source_artifact_path",
        "source_record_index",
        "row_id",
        "pool_id",
    }
    hard_drop = {
        "question_text",
        "raw_output_text",
        "result_metadata_json",
        "normalized_answer",
        "extracted_answer",
        "error_text",
        "status",
        "run_timestamp",
        "model_id",
        "method_family",
        "label_source",
        "candidate_parse_failure_label",
    }

    explicit = [
        "provider",
        "dataset",
        "scenario_id",
        "method",
        "math_subject",
        "math_level",
        "cluster_size",
        "max_cluster_size",
        "distinct_answer_count",
        "agreement_entropy",
        "parse_success",
        "malformed_output_flag",
        "truncation_suspected_flag",
        "answer_length_chars",
        "output_length_chars",
        "output_length_tokens_approx",
        "normalized_answer_length_chars",
        "answer_is_empty",
        "boxed_answer_present",
        "multiple_boxed_answers",
        "numeric_answer_flag",
        "integer_answer_flag",
        "fraction_answer_flag",
        "expression_answer_flag",
        "negative_answer_flag",
        "answer_contains_variable",
        "answer_contains_units",
        "answer_magnitude_abs",
        "problem_length_chars",
        "problem_length_tokens_approx",
        "problem_numeric_token_count",
        "problem_variable_token_count",
        "is_frontier_method_flag",
        "is_external_method_flag",
        "agrees_with_frontier",
        "agrees_with_l1",
        "agrees_with_s1",
        "agrees_with_tale",
        "all_answers_same_flag",
        "all_answers_different_flag",
        "no_majority_flag",
        "candidate_is_isolated_flag",
        "candidate_in_largest_cluster_flag",
        "majority_includes_frontier",
        "majority_includes_s1",
        "majority_excludes_frontier",
        "majority_excludes_s1",
        "rel_method_acc_trainfold",
        "rel_provider_method_acc_trainfold",
        "rel_scenario_method_acc_trainfold",
    ]

    use_cols = []
    rejected = []

    for c in explicit:
        if c not in df.columns:
            continue
        if c in forbidden or c in hard_drop:
            rejected.append(c)
            continue
        use_cols.append(c)

    # Override-specific engineered columns (if present)
    for c in [
        "baseline_method",
        "baseline_parse_success",
        "baseline_cluster_size",
        "baseline_rel_method_acc",
        "cand_vs_base_cluster_delta",
        "cand_vs_base_parse_delta",
        "cand_vs_base_rel_method_delta",
        "cand_agrees_with_baseline_answer",
    ]:
        if c in df.columns and c not in forbidden:
            use_cols.append(c)

    use_cols = sorted(dict.fromkeys(use_cols))
    rejected = sorted(dict.fromkeys(rejected + [c for c in df.columns if c in forbidden]))

    cat_cols = [c for c in use_cols if df[c].dtype == object]
    return use_cols, cat_cols, rejected


def encode_features(train_df: pd.DataFrame, other_df: pd.DataFrame, cols: list[str], cat_cols: list[str]) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    tr = train_df[cols].copy()
    te = other_df[cols].copy()

    num_cols = [c for c in cols if c not in cat_cols]
    for c in num_cols:
        tr[c] = pd.to_numeric(tr[c], errors="coerce")
        te[c] = pd.to_numeric(te[c], errors="coerce")

    if num_cols:
        # Column-wise robust median imputation that tolerates all-NaN columns.
        for c in num_cols:
            med = tr[c].median(skipna=True)
            if pd.isna(med):
                med = 0.0
            tr[c] = tr[c].fillna(med)
            te[c] = te[c].fillna(med)

    tr_cat = pd.get_dummies(tr[cat_cols], dummy_na=True) if cat_cols else pd.DataFrame(index=tr.index)
    te_cat = pd.get_dummies(te[cat_cols], dummy_na=True) if cat_cols else pd.DataFrame(index=te.index)

    tr_cat, te_cat = tr_cat.align(te_cat, join="left", axis=1, fill_value=0)

    Xtr = pd.concat([tr[num_cols], tr_cat], axis=1)
    Xte = pd.concat([te[num_cols], te_cat], axis=1)

    meta = {
        "feature_count": int(Xtr.shape[1]),
        "numeric_cols": num_cols,
        "categorical_cols": cat_cols,
    }
    return Xtr, Xte, meta


@dataclass
class ModelSpec:
    name: str
    family: str
    params: dict[str, Any]
    gpu_used: bool


def train_model(spec: ModelSpec, X_train: pd.DataFrame, y_train: np.ndarray) -> Any:
    if spec.family == "logreg":
        m = LogisticRegression(**spec.params)
        m.fit(X_train, y_train)
        return m
    if spec.family == "rf":
        m = RandomForestClassifier(**spec.params)
        m.fit(X_train, y_train)
        return m
    if spec.family == "hgb":
        m = HistGradientBoostingClassifier(**spec.params)
        m.fit(X_train, y_train)
        return m
    if spec.family == "xgboost":
        from xgboost import XGBClassifier

        m = XGBClassifier(**spec.params)
        m.fit(X_train, y_train)
        return m
    if spec.family == "lightgbm":
        import lightgbm as lgb

        m = lgb.LGBMClassifier(**spec.params)
        m.fit(X_train, y_train)
        return m
    raise ValueError(f"unknown family {spec.family}")


def predict_prob(model: Any, X: pd.DataFrame) -> np.ndarray:
    if hasattr(model, "predict_proba"):
        p = model.predict_proba(X)
        if p.ndim == 2 and p.shape[1] >= 2:
            return p[:, 1].astype(float)
        return p.reshape(-1).astype(float)
    if hasattr(model, "decision_function"):
        z = model.decision_function(X)
        return 1.0 / (1.0 + np.exp(-z))
    y = model.predict(X)
    return np.asarray(y, dtype=float)


def evaluate_policy(
    split_name: str,
    rows_df: pd.DataFrame,
    scores: np.ndarray,
    defaults_by_pool: pd.DataFrame,
    tau_global: float | None = None,
    tau_by_scenario: dict[str, float] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    sub = rows_df.copy()
    sub["score"] = scores

    dp = defaults_by_pool.copy()
    dp = dp[dp["split"] == split_name].copy()

    decisions = []
    for pool_id, g in dp.groupby("pool_id"):
        scen = clean_text(g["scenario_id"].iloc[0])
        default_method = clean_text(g["baseline_method"].iloc[0])
        default_correct = int(g["baseline_correct"].iloc[0])
        oracle = int(g["oracle_correct"].iloc[0])

        cand = sub[sub["pool_id"] == pool_id].copy()
        thr = tau_global if tau_by_scenario is None else float(tau_by_scenario.get(scen, tau_global if tau_global is not None else 0.99))

        override = False
        chosen_method = default_method
        chosen_correct = default_correct
        chosen_score = float("nan")

        if len(cand):
            top = cand.sort_values("score", ascending=False).iloc[0]
            if safe_float(top["score"], 0.0) >= safe_float(thr, 0.99):
                override = True
                chosen_method = clean_text(top["override_candidate_method"])
                chosen_correct = int(top["candidate_correct"])
                chosen_score = float(top["score"])

        ov_kind = "none"
        if override:
            if chosen_correct > default_correct:
                ov_kind = "good"
            elif chosen_correct < default_correct:
                ov_kind = "bad"
            else:
                ov_kind = "neutral"

        decisions.append(
            {
                "pool_id": pool_id,
                "split": split_name,
                "scenario_id": scen,
                "provider": clean_text(g["provider"].iloc[0]),
                "dataset": clean_text(g["dataset"].iloc[0]),
                "baseline_policy": clean_text(g["baseline_policy"].iloc[0]),
                "baseline_method": default_method,
                "baseline_correct": default_correct,
                "oracle_correct": oracle,
                "override_threshold": thr,
                "override_happened": int(override),
                "override_kind": ov_kind,
                "selected_method": chosen_method,
                "selected_correct": int(chosen_correct),
                "selected_score": chosen_score,
            }
        )

    dec = pd.DataFrame(decisions)
    if dec.empty:
        by = pd.DataFrame()
    else:
        by = (
            dec.groupby(["split", "scenario_id", "provider", "dataset"], as_index=False)
            .agg(
                pools=("pool_id", "count"),
                default_baseline_accuracy=("baseline_correct", "mean"),
                d3_accuracy=("selected_correct", "mean"),
                oracle=("oracle_correct", "mean"),
                override_coverage=("override_happened", "mean"),
                good_override_count=("override_kind", lambda x: int((x == "good").sum())),
                bad_override_count=("override_kind", lambda x: int((x == "bad").sum())),
            )
        )
    return dec, by


def choose_best_threshold_policy(
    val_rows: pd.DataFrame,
    val_scores: np.ndarray,
    defaults_by_pool: pd.DataFrame,
    out_dir: Path,
) -> tuple[str, float, dict[str, float], pd.DataFrame, pd.DataFrame]:
    taus = [0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95, 0.99]
    val_scored = val_rows.copy()
    val_scored["score"] = val_scores

    # Default val baseline (from default policy)
    val_default = defaults_by_pool[defaults_by_pool["split"] == "validation"].copy()
    default_val_acc = float(val_default["baseline_correct"].mean()) if len(val_default) else float("nan")

    g_rows = []
    best_tau = 0.99
    best_acc = -1.0
    best_cov = 0.0

    for tau in taus:
        dec, by = evaluate_policy("validation", val_rows, val_scores, defaults_by_pool, tau_global=tau)
        acc = float(dec["selected_correct"].mean()) if len(dec) else float("nan")
        cov = float(dec["override_happened"].mean()) if len(dec) else 0.0
        good = int((dec["override_kind"] == "good").sum()) if len(dec) else 0
        bad = int((dec["override_kind"] == "bad").sum()) if len(dec) else 0
        delta = acc - default_val_acc if pd.notna(default_val_acc) and pd.notna(acc) else float("nan")
        g_rows.append(
            {
                "policy": "global",
                "threshold": tau,
                "validation_accuracy": acc,
                "validation_default_accuracy": default_val_acc,
                "validation_delta_vs_default": delta,
                "validation_override_coverage": cov,
                "validation_good_overrides": good,
                "validation_bad_overrides": bad,
            }
        )
        if pd.notna(acc) and acc > best_acc:
            best_acc = acc
            best_tau = tau
            best_cov = cov

    # conservative no-regression global
    cons_tau = 0.99
    for tau in taus:
        row = [r for r in g_rows if r["threshold"] == tau][0]
        if pd.notna(row["validation_accuracy"]) and row["validation_accuracy"] >= default_val_acc and row["validation_override_coverage"] > 0:
            cons_tau = tau
    cons_row = [r for r in g_rows if r["threshold"] == cons_tau][0]
    g_rows.append(
        {
            "policy": "conservative_no_regression",
            "threshold": cons_tau,
            "validation_accuracy": cons_row["validation_accuracy"],
            "validation_default_accuracy": default_val_acc,
            "validation_delta_vs_default": cons_row["validation_delta_vs_default"],
            "validation_override_coverage": cons_row["validation_override_coverage"],
            "validation_good_overrides": cons_row["validation_good_overrides"],
            "validation_bad_overrides": cons_row["validation_bad_overrides"],
        }
    )
    global_df = pd.DataFrame(g_rows)

    # per-scenario threshold with eps constraints
    eps_list = [0.000, 0.002, 0.005, 0.010]
    by_rows = []
    by_scenario_thresholds: dict[str, float] = {}

    val_scen_default = (
        defaults_by_pool[defaults_by_pool["split"] == "validation"]
        .groupby("scenario_id", as_index=False)
        .agg(default_accuracy=("baseline_correct", "mean"))
    )
    val_scen_default_map = {clean_text(r["scenario_id"]): float(r["default_accuracy"]) for _, r in val_scen_default.iterrows()}

    val_scenarios = sorted(val_rows["scenario_id"].dropna().unique().tolist())

    for eps in eps_list:
        tmp_thr = {}
        for scen in val_scenarios:
            rs = val_scored[val_scored["scenario_id"] == scen].copy()
            if rs.empty:
                continue
            target = val_scen_default_map.get(scen, float("nan"))
            best_s_acc = -1.0
            best_s_tau = 0.99
            for tau in taus:
                dec, _ = evaluate_policy("validation", rs, rs["score"].to_numpy(), defaults_by_pool[defaults_by_pool["scenario_id"] == scen], tau_global=tau)
                sacc = float(dec["selected_correct"].mean()) if len(dec) else float("nan")
                if pd.isna(target) or pd.isna(sacc):
                    continue
                if sacc >= target - eps:
                    if sacc > best_s_acc or (np.isclose(sacc, best_s_acc) and tau > best_s_tau):
                        best_s_acc = sacc
                        best_s_tau = tau
            tmp_thr[scen] = best_s_tau
            by_rows.append(
                {
                    "epsilon": eps,
                    "scenario_id": scen,
                    "selected_threshold": best_s_tau,
                    "validation_default_accuracy": target,
                    "validation_selected_accuracy": best_s_acc if best_s_acc >= 0 else float("nan"),
                    "constraint_satisfied": int(best_s_acc >= (target - eps)) if pd.notna(target) and best_s_acc >= 0 else 0,
                }
            )

        # evaluate this epsilon policy overall on validation
        dec_eps, _ = evaluate_policy("validation", val_rows, val_scores, defaults_by_pool, tau_global=best_tau, tau_by_scenario=tmp_thr)
        eacc = float(dec_eps["selected_correct"].mean()) if len(dec_eps) else float("nan")
        ecov = float(dec_eps["override_happened"].mean()) if len(dec_eps) else float("nan")
        global_df = pd.concat(
            [
                global_df,
                pd.DataFrame(
                    [
                        {
                            "policy": f"per_scenario_eps_{eps:.3f}",
                            "threshold": float("nan"),
                            "validation_accuracy": eacc,
                            "validation_default_accuracy": default_val_acc,
                            "validation_delta_vs_default": eacc - default_val_acc if pd.notna(eacc) and pd.notna(default_val_acc) else float("nan"),
                            "validation_override_coverage": ecov,
                            "validation_good_overrides": int((dec_eps["override_kind"] == "good").sum()) if len(dec_eps) else 0,
                            "validation_bad_overrides": int((dec_eps["override_kind"] == "bad").sum()) if len(dec_eps) else 0,
                        }
                    ]
                ),
            ],
            ignore_index=True,
        )

        if abs(eps - 0.005) < 1e-9:
            by_scenario_thresholds = tmp_thr

    by_df = pd.DataFrame(by_rows)

    # selected policy: conservative if it preserves default and has nonzero coverage; else best global
    selected_policy = "conservative_no_regression"
    selected_global_tau = cons_tau
    selected_scen_thr = {}

    cons_val = global_df[global_df["policy"] == "conservative_no_regression"]
    if len(cons_val) and pd.notna(cons_val["validation_accuracy"].iloc[0]) and cons_val["validation_accuracy"].iloc[0] >= default_val_acc:
        selected_policy = "conservative_no_regression"
        selected_global_tau = cons_tau
    else:
        top = global_df[global_df["policy"] == "global"].sort_values("validation_accuracy", ascending=False).iloc[0]
        selected_policy = "global_best"
        selected_global_tau = float(top["threshold"])

    # If eps=0.005 has better val and no-regression globally, prefer it
    eps_row = global_df[global_df["policy"] == "per_scenario_eps_0.005"]
    if len(eps_row):
        if pd.notna(eps_row["validation_accuracy"].iloc[0]) and pd.notna(default_val_acc):
            if eps_row["validation_accuracy"].iloc[0] >= default_val_acc and eps_row["validation_accuracy"].iloc[0] >= global_df[global_df["policy"] == selected_policy]["validation_accuracy"].iloc[0]:
                selected_policy = "per_scenario_eps_0.005"
                selected_global_tau = best_tau
                selected_scen_thr = by_scenario_thresholds

    (out_dir / "threshold_sweep_global.csv").write_text(global_df.to_csv(index=False))
    (out_dir / "threshold_sweep_by_scenario.csv").write_text(by_df.to_csv(index=False))

    pol_lines = [
        "# Selected Threshold Policy",
        "",
        f"selected_policy: {selected_policy}",
        f"global_threshold_fallback: {selected_global_tau}",
        f"default_validation_accuracy: {default_val_acc}",
        f"per_scenario_threshold_count: {len(selected_scen_thr)}",
    ]
    (out_dir / "selected_threshold_policy.md").write_text("\n".join(pol_lines) + "\n")

    return selected_policy, selected_global_tau, selected_scen_thr, global_df, by_df


def main() -> None:
    parser = argparse.ArgumentParser(description="Job D3 conservative override training")
    parser.add_argument("--input-dir", default="outputs/unified_learning_tables_20260525/run_20260525T184354Z")
    parser.add_argument("--d2-dir", default="outputs/job_d2_reliability_selector_20260525/run_20260525T192302Z")
    parser.add_argument("--corrected-eval-dir", default="outputs/corrected_d1_d2_evaluation_20260525/run_20260525T201240Z")
    parser.add_argument("--corrected-baseline-dir", default="outputs/baseline_selector_definition_audit_20260525/run_20260525T194246Z")
    parser.add_argument("--output-root", default="outputs/job_d3_conservative_override_20260525")
    parser.add_argument("--ledger-root", default="outputs/training_experiment_ledger_20260525")
    args = parser.parse_args()

    in_dir = Path(args.input_dir)
    d2_dir = Path(args.d2_dir)
    corr_eval_dir = Path(args.corrected_eval_dir)
    corr_base_dir = Path(args.corrected_baseline_dir)
    out_dir = ensure_run_dir(Path(args.output_root))

    # run log + env
    with (out_dir / "run.log").open("w") as f:
        f.write(f"Generated at: {now_utc()}\n\n")
        f.write(run_command("pwd"))
        f.write(run_command("date"))
        f.write(run_command("git status --short"))
        f.write(run_command("git branch -vv"))
        f.write(run_command("git log --oneline -10"))
        f.write(run_command("tmux ls || true"))
        f.write(run_command("python3 -V"))
        f.write(run_command("which python3"))
        f.write(run_command("nvidia-smi || true"))

    pkg_rows = []
    for p in ["sklearn", "xgboost", "lightgbm", "catboost", "optuna", "shap"]:
        pkg_rows.append({"package": p, "available": has_pkg(p)})
    pkg_df = pd.DataFrame(pkg_rows)
    pkg_df.to_csv(out_dir / "package_availability_report.csv", index=False)
    (out_dir / "package_availability_report.md").write_text(md_table(pkg_df, "Package Availability"))

    gpu_raw = run_command("nvidia-smi || true")
    (out_dir / "gpu_availability_report.md").write_text("# GPU Availability Report\n\n```text\n" + gpu_raw + "\n```\n")

    env_lines = [
        "# Environment Report",
        "",
        run_command("pwd") + run_command("date") + run_command("git status --short") + run_command("git branch -vv") + run_command("git log --oneline -10") + run_command("tmux ls || true") + run_command("python3 -V") + run_command("which python3") + gpu_raw,
    ]
    (out_dir / "environment_report.md").write_text("\n".join(env_lines) + "\n")

    # load data
    cand = pd.read_csv(in_dir / "unified_candidate_action_table.csv")
    pool = pd.read_csv(in_dir / "unified_pool_level_table.csv")
    corr_pool = pd.read_csv(corr_base_dir / "corrected_baseline_pool_decisions.csv")
    corr_summary = pd.read_csv(corr_base_dir / "corrected_baseline_summary_by_scenario.csv") if (corr_base_dir / "corrected_baseline_summary_by_scenario.csv").exists() else pd.DataFrame()
    d2_cases = pd.read_csv(d2_dir / "selector_case_predictions.csv") if (d2_dir / "selector_case_predictions.csv").exists() else pd.DataFrame()
    corrected_eval = pd.read_csv(corr_eval_dir / "corrected_d1_vs_d2_by_scenario.csv")

    # basic normalization
    cand["candidate_correct"] = cand["candidate_correct"].map(bool_int)

    # default policies
    default_policy = pick_default_policies(corr_pool, corrected_eval)
    default_policy.to_csv(out_dir / "d3_default_policy_by_scenario.csv", index=False)
    (out_dir / "d3_default_policy_by_scenario.md").write_text(md_table(default_policy, "D3 Default Policy By Scenario"))

    # map per-pool defaults
    dp = corr_pool.merge(default_policy[["scenario_id", "default_policy", "selection_split"]], on="scenario_id", how="left")
    base_methods, base_corrects = [], []
    for _, r in dp.iterrows():
        m, c = policy_to_method_and_correct(r, clean_text(r["default_policy"]))
        base_methods.append(m)
        base_corrects.append(c)
    dp["baseline_method"] = base_methods
    dp["baseline_correct"] = base_corrects

    # fold-safe reliability
    cand_rel, rel_cols, rel_report = add_fold_safe_reliability(cand)
    (out_dir / "d3_reliability_feature_report.md").write_text(rel_report)
    (out_dir / "d3_reliability_feature_columns.txt").write_text("\n".join(rel_cols) + "\n")
    (out_dir / "d3_reliability_leakage_audit.md").write_text(
        "\n".join(
            [
                "# D3 Reliability Leakage Audit",
                "",
                "- Train rows use OOF GroupKFold by pool_id",
                "- Validation/test/seen_dev reliability derived from train-only maps",
                "- No validation/test/seen_dev labels used to build reliability stats",
                f"- Reliability columns: {len(rel_cols)}",
            ]
        )
        + "\n"
    )

    # build baseline row lookup by pool/method
    cand_key = cand_rel[["pool_id", "method", "candidate_correct", "normalized_answer", "cluster_size", "parse_success", "rel_method_acc_trainfold"]].copy()

    merged = cand_rel.merge(
        dp[["pool_id", "scenario_id", "provider", "dataset", "split", "default_policy", "selection_split", "baseline_method", "baseline_correct", "oracle_correct"]],
        on=["pool_id", "scenario_id", "provider", "dataset", "split"],
        how="inner",
    )

    # attach baseline method row features for same pool
    base_rows = cand_key.rename(
        columns={
            "method": "baseline_method",
            "candidate_correct": "baseline_method_correct_from_candidate",
            "normalized_answer": "baseline_answer",
            "cluster_size": "baseline_cluster_size",
            "parse_success": "baseline_parse_success",
            "rel_method_acc_trainfold": "baseline_rel_method_acc",
        }
    )
    merged = merged.merge(base_rows, on=["pool_id", "baseline_method"], how="left")

    # keep non-default candidate actions only
    ov = merged[merged["method"] != merged["baseline_method"]].copy()

    ov["candidate_correct"] = ov["candidate_correct"].map(bool_int)
    ov["baseline_correct"] = ov["baseline_correct"].map(bool_int)
    ov["override_good"] = ((ov["candidate_correct"] == 1) & (ov["baseline_correct"] == 0)).astype(int)
    ov["override_bad"] = ((ov["candidate_correct"] == 0) & (ov["baseline_correct"] == 1)).astype(int)
    ov["neutral"] = 1 - np.maximum(ov["override_good"], ov["override_bad"])

    ov["override_candidate_method"] = ov["method"]
    ov["cand_agrees_with_baseline_answer"] = (ov["normalized_answer"].fillna("") == ov["baseline_answer"].fillna("")).astype(int)
    ov["cand_vs_base_cluster_delta"] = ov["cluster_size"].fillna(0) - ov["baseline_cluster_size"].fillna(0)
    ov["cand_vs_base_parse_delta"] = ov["parse_success"].fillna(0) - ov["baseline_parse_success"].fillna(0)
    ov["cand_vs_base_rel_method_delta"] = ov["rel_method_acc_trainfold"].fillna(0.5) - ov["baseline_rel_method_acc"].fillna(0.5)

    ov.to_csv(out_dir / "override_training_table.csv", index=False)

    # labels distribution
    label_df = pd.DataFrame(
        [
            {"label": "override_good", "count": int(ov["override_good"].sum()), "rate": float(ov["override_good"].mean()) if len(ov) else float("nan")},
            {"label": "override_bad", "count": int(ov["override_bad"].sum()), "rate": float(ov["override_bad"].mean()) if len(ov) else float("nan")},
            {"label": "neutral", "count": int(ov["neutral"].sum()), "rate": float(ov["neutral"].mean()) if len(ov) else float("nan")},
        ]
    )
    label_df.to_csv(out_dir / "override_label_distribution.csv", index=False)
    (out_dir / "override_label_distribution.md").write_text(md_table(label_df, "Override Label Distribution"))

    # feature selection and leakage audit
    use_cols, cat_cols, rejected = choose_feature_columns(ov)
    (out_dir / "feature_columns_used.txt").write_text("\n".join(use_cols) + "\n")
    (out_dir / "feature_columns_rejected.txt").write_text("\n".join(rejected) + "\n")

    leakage_lines = [
        "# Leakage Check Before D3 Training",
        "",
        f"Override rows: {len(ov)}",
        f"Features used: {len(use_cols)}",
        f"Features rejected: {len(rejected)}",
        "No forbidden correctness/gold/id fields used as model features.",
        "Split discipline: train for fitting, validation for threshold tuning, test/seen_dev final evaluation.",
    ]
    (out_dir / "leakage_check_before_d3_training.md").write_text("\n".join(leakage_lines) + "\n")

    # split data
    tr = ov[ov["split"] == "train"].copy()
    va = ov[ov["split"] == "validation"].copy()
    te = ov[ov["split"] == "test"].copy()
    sd = ov[ov["split"] == "seen_dev"].copy()

    if len(tr) == 0 or len(va) == 0:
        raise RuntimeError("D3 needs train and validation override rows")

    Xtr, Xva, feat_meta = encode_features(tr, va, use_cols, cat_cols)
    ytr = tr["override_good"].astype(int).to_numpy()
    yva = va["override_good"].astype(int).to_numpy()

    Xte = encode_features(tr, te, use_cols, cat_cols)[1]
    Xsd = encode_features(tr, sd, use_cols, cat_cols)[1]

    # model availability + training
    avail = {
        "xgboost": has_pkg("xgboost"),
        "lightgbm": has_pkg("lightgbm"),
        "catboost": has_pkg("catboost"),
        "optuna": has_pkg("optuna"),
        "shap": has_pkg("shap"),
    }

    pos = int(ytr.sum())
    neg = int((1 - ytr).sum())
    spw = float(neg / max(pos, 1))

    specs: list[ModelSpec] = [
        ModelSpec("logreg_balanced", "logreg", {"max_iter": 2000, "class_weight": "balanced"}, False),
        ModelSpec("rf_balanced", "rf", {"n_estimators": 300, "max_depth": 12, "random_state": 42, "n_jobs": -1, "class_weight": "balanced_subsample"}, False),
        ModelSpec("hgb", "hgb", {"learning_rate": 0.06, "max_depth": 8, "max_iter": 300, "random_state": 42}, False),
    ]
    if avail["xgboost"]:
        specs.append(
            ModelSpec(
                "xgboost",
                "xgboost",
                {
                    "n_estimators": 250,
                    "max_depth": 7,
                    "learning_rate": 0.05,
                    "subsample": 0.9,
                    "colsample_bytree": 0.9,
                    "objective": "binary:logistic",
                    "eval_metric": "logloss",
                    "scale_pos_weight": spw,
                    "tree_method": "hist",
                    "device": "cuda",
                    "n_jobs": -1,
                    "random_state": 42,
                },
                True,
            )
        )
    if avail["lightgbm"]:
        specs.append(
            ModelSpec(
                "lightgbm",
                "lightgbm",
                {
                    "n_estimators": 350,
                    "learning_rate": 0.04,
                    "num_leaves": 63,
                    "subsample": 0.9,
                    "colsample_bytree": 0.9,
                    "objective": "binary",
                    "device": "gpu",
                    "n_jobs": -1,
                    "random_state": 42,
                    "class_weight": "balanced",
                },
                True,
            )
        )

    model_avail_rows = []
    hyper_trials = []

    # defaults by pool table
    defaults_by_pool = (
        dp[
            [
                "pool_id",
                "split",
                "scenario_id",
                "provider",
                "dataset",
                "default_policy",
                "baseline_method",
                "baseline_correct",
                "oracle_correct",
            ]
        ]
        .rename(columns={"default_policy": "baseline_policy"})
        .drop_duplicates("pool_id")
    )

    best_model = ""
    best_val_acc = -1.0
    best_val_scores = None
    best_test_scores = None
    best_seen_scores = None

    for spec in specs:
        ok = True
        note = "ok"
        gpu_used = spec.gpu_used
        try:
            model = train_model(spec, Xtr, ytr)
            pva = predict_prob(model, Xva)
            pte = predict_prob(model, Xte) if len(te) else np.array([])
            psd = predict_prob(model, Xsd) if len(sd) else np.array([])

            # quick model-level validation using best global threshold
            taus = [0.5, 0.6, 0.7, 0.8, 0.9]
            best_local = -1.0
            best_tau_local = 0.9
            for tau in taus:
                dec, _ = evaluate_policy("validation", va, pva, defaults_by_pool, tau_global=tau)
                acc = float(dec["selected_correct"].mean()) if len(dec) else float("nan")
                if pd.notna(acc) and acc > best_local:
                    best_local = acc
                    best_tau_local = tau

            auc = float(roc_auc_score(yva, pva)) if len(np.unique(yva)) > 1 else float("nan")
            ll = float(log_loss(yva, np.clip(pva, 1e-6, 1 - 1e-6))) if len(np.unique(yva)) > 1 else float("nan")

            hyper_trials.append(
                {
                    "model": spec.name,
                    "params": json.dumps(spec.params, sort_keys=True),
                    "val_candidate_auc": auc,
                    "val_candidate_log_loss": ll,
                    "val_policy_best_tau": best_tau_local,
                    "val_policy_best_accuracy": best_local,
                }
            )

            if best_local > best_val_acc:
                best_val_acc = best_local
                best_model = spec.name
                best_val_scores = pva
                best_test_scores = pte
                best_seen_scores = psd

        except Exception as e:
            ok = False
            note = f"failed:{type(e).__name__}:{clean_text(e)}"
            if spec.family == "xgboost" and spec.gpu_used:
                try:
                    spec_cpu = ModelSpec(spec.name + "_cpu_fallback", "xgboost", {**spec.params, "device": "cpu"}, False)
                    model = train_model(spec_cpu, Xtr, ytr)
                    pva = predict_prob(model, Xva)
                    pte = predict_prob(model, Xte) if len(te) else np.array([])
                    psd = predict_prob(model, Xsd) if len(sd) else np.array([])
                    dec, _ = evaluate_policy("validation", va, pva, defaults_by_pool, tau_global=0.8)
                    acc = float(dec["selected_correct"].mean()) if len(dec) else float("nan")
                    ok = True
                    note = "cpu_fallback_ok"
                    gpu_used = False
                    hyper_trials.append(
                        {
                            "model": spec_cpu.name,
                            "params": json.dumps(spec_cpu.params, sort_keys=True),
                            "val_candidate_auc": float(roc_auc_score(yva, pva)) if len(np.unique(yva)) > 1 else float("nan"),
                            "val_candidate_log_loss": float(log_loss(yva, np.clip(pva, 1e-6, 1 - 1e-6))) if len(np.unique(yva)) > 1 else float("nan"),
                            "val_policy_best_tau": 0.8,
                            "val_policy_best_accuracy": acc,
                        }
                    )
                    if pd.notna(acc) and acc > best_val_acc:
                        best_val_acc = acc
                        best_model = spec_cpu.name
                        best_val_scores = pva
                        best_test_scores = pte
                        best_seen_scores = psd
                except Exception:
                    pass
            if spec.family == "lightgbm" and spec.gpu_used:
                try:
                    spec_cpu = ModelSpec(spec.name + "_cpu_fallback", "lightgbm", {**spec.params, "device": "cpu"}, False)
                    model = train_model(spec_cpu, Xtr, ytr)
                    pva = predict_prob(model, Xva)
                    pte = predict_prob(model, Xte) if len(te) else np.array([])
                    psd = predict_prob(model, Xsd) if len(sd) else np.array([])
                    dec, _ = evaluate_policy("validation", va, pva, defaults_by_pool, tau_global=0.8)
                    acc = float(dec["selected_correct"].mean()) if len(dec) else float("nan")
                    ok = True
                    note = "cpu_fallback_ok"
                    gpu_used = False
                    hyper_trials.append(
                        {
                            "model": spec_cpu.name,
                            "params": json.dumps(spec_cpu.params, sort_keys=True),
                            "val_candidate_auc": float(roc_auc_score(yva, pva)) if len(np.unique(yva)) > 1 else float("nan"),
                            "val_candidate_log_loss": float(log_loss(yva, np.clip(pva, 1e-6, 1 - 1e-6))) if len(np.unique(yva)) > 1 else float("nan"),
                            "val_policy_best_tau": 0.8,
                            "val_policy_best_accuracy": acc,
                        }
                    )
                    if pd.notna(acc) and acc > best_val_acc:
                        best_val_acc = acc
                        best_model = spec_cpu.name
                        best_val_scores = pva
                        best_test_scores = pte
                        best_seen_scores = psd
                except Exception:
                    pass

        model_avail_rows.append(
            {
                "model": spec.name,
                "available": True,
                "gpu_attempted": spec.gpu_used,
                "gpu_used": gpu_used if ok else False,
                "status": "ok" if ok else "failed",
                "note": note,
            }
        )

    # unavailable packages modeled as not available rows
    if not avail["xgboost"]:
        model_avail_rows.append({"model": "xgboost", "available": False, "gpu_attempted": False, "gpu_used": False, "status": "not_available", "note": "package missing"})
    if not avail["lightgbm"]:
        model_avail_rows.append({"model": "lightgbm", "available": False, "gpu_attempted": False, "gpu_used": False, "status": "not_available", "note": "package missing"})
    if not avail["catboost"]:
        model_avail_rows.append({"model": "catboost", "available": False, "gpu_attempted": False, "gpu_used": False, "status": "not_available", "note": "package missing"})

    model_avail_df = pd.DataFrame(model_avail_rows)
    model_avail_df.to_csv(out_dir / "model_availability_report.csv", index=False)
    (out_dir / "model_availability_report.md").write_text(md_table(model_avail_df, "Model Availability Report"))

    htr = pd.DataFrame(hyper_trials)
    htr.to_csv(out_dir / "hyperparameter_trials.csv", index=False)

    if best_model == "" or best_val_scores is None:
        raise RuntimeError("No D3 model successfully trained")

    # threshold policy selection
    policy_name, tau_global, tau_by_scenario, thr_global_df, thr_by_df = choose_best_threshold_policy(va, best_val_scores, defaults_by_pool, out_dir)

    # evaluate final policy on test/seen_dev
    test_dec, test_by = evaluate_policy("test", te, best_test_scores if best_test_scores is not None else np.array([]), defaults_by_pool, tau_global=tau_global, tau_by_scenario=tau_by_scenario if policy_name.startswith("per_scenario") else None)
    seen_dec, seen_by = evaluate_policy("seen_dev", sd, best_seen_scores if best_seen_scores is not None else np.array([]), defaults_by_pool, tau_global=tau_global, tau_by_scenario=tau_by_scenario if policy_name.startswith("per_scenario") else None)

    all_dec = pd.concat([test_dec, seen_dec], ignore_index=True)
    all_dec.to_csv(out_dir / "d3_selector_case_predictions.csv", index=False)
    all_dec.to_csv(out_dir / "d3_override_decisions.csv", index=False)

    all_dec[all_dec["override_kind"] == "bad"].to_csv(out_dir / "d3_false_overrides.csv", index=False)
    all_dec[all_dec["override_kind"] == "good"].to_csv(out_dir / "d3_good_overrides.csv", index=False)
    all_dec[(all_dec["oracle_correct"] == 1) & (all_dec["selected_correct"] == 0)].to_csv(out_dir / "d3_oracle_available_but_wrong.csv", index=False)

    # scenario-level results
    d3_by = pd.concat([test_by, seen_by], ignore_index=True)

    d1d2 = pd.read_csv(corr_eval_dir / "corrected_d1_vs_d2_by_scenario.csv")
    use = d1d2[["split", "scenario_id", "provider", "dataset", "corrected_best_fixed_baseline", "baseline_accuracy", "d1_accuracy", "d2_accuracy", "oracle"]].copy()

    res = d3_by.merge(use, on=["split", "scenario_id", "provider", "dataset"], how="left", suffixes=("", "_corr"))
    res["best_fixed_baseline"] = res["corrected_best_fixed_baseline"]
    res["baseline_accuracy"] = res["baseline_accuracy"]
    res["d3_accuracy"] = res["d3_accuracy"]
    res["d3_minus_d2"] = res["d3_accuracy"] - res["d2_accuracy"]
    res["d3_minus_baseline"] = res["d3_accuracy"] - res["baseline_accuracy"]
    res["result_vs_corrected_best_baseline"] = res["d3_minus_baseline"].map(lambda d: "win" if d > 0 else ("tie" if d == 0 else "loss"))
    res["result_vs_default_baseline"] = (res["d3_accuracy"] - res["default_baseline_accuracy"]).map(lambda d: "win" if d > 0 else ("tie" if d == 0 else "loss"))
    res["oracle_gap"] = res["oracle"] - res["d3_accuracy"]

    d3_cols = [
        "split",
        "scenario_id",
        "provider",
        "dataset",
        "pools",
        "best_fixed_baseline",
        "baseline_accuracy",
        "d1_accuracy",
        "d2_accuracy",
        "d3_accuracy",
        "d3_minus_d2",
        "d3_minus_baseline",
        "oracle",
        "override_coverage",
        "good_override_count",
        "bad_override_count",
        "result_vs_corrected_best_baseline",
        "result_vs_default_baseline",
    ]
    d3_out = res[d3_cols].copy()
    d3_out.to_csv(out_dir / "d3_results_by_scenario.csv", index=False)
    (out_dir / "d3_results_by_scenario.md").write_text(md_table(d3_out, "D3 Results By Scenario"))

    d123 = res[["split", "scenario_id", "provider", "dataset", "baseline_accuracy", "d1_accuracy", "d2_accuracy", "d3_accuracy", "d3_minus_d2", "d3_minus_baseline", "oracle", "override_coverage"]].copy()
    d123.to_csv(out_dir / "d1_d2_d3_comparison.csv", index=False)
    (out_dir / "d1_d2_d3_comparison.md").write_text(md_table(d123, "D1 D2 D3 Comparison"))

    clean_sum = d3_out[d3_out["split"] == "test"].copy()
    seen_sum = d3_out[d3_out["split"] == "seen_dev"].copy()

    clean_summary = pd.DataFrame(
        [
            {
                "split": "test",
                "scenarios": int(len(clean_sum)),
                "wins": int((clean_sum["result_vs_corrected_best_baseline"] == "win").sum()),
                "ties": int((clean_sum["result_vs_corrected_best_baseline"] == "tie").sum()),
                "losses": int((clean_sum["result_vs_corrected_best_baseline"] == "loss").sum()),
                "mean_d3_minus_d2": float(clean_sum["d3_minus_d2"].mean()) if len(clean_sum) else float("nan"),
                "mean_d3_minus_baseline": float(clean_sum["d3_minus_baseline"].mean()) if len(clean_sum) else float("nan"),
            }
        ]
    )
    seen_summary = pd.DataFrame(
        [
            {
                "split": "seen_dev",
                "scenarios": int(len(seen_sum)),
                "wins": int((seen_sum["result_vs_corrected_best_baseline"] == "win").sum()),
                "ties": int((seen_sum["result_vs_corrected_best_baseline"] == "tie").sum()),
                "losses": int((seen_sum["result_vs_corrected_best_baseline"] == "loss").sum()),
                "mean_d3_minus_d2": float(seen_sum["d3_minus_d2"].mean()) if len(seen_sum) else float("nan"),
                "mean_d3_minus_baseline": float(seen_sum["d3_minus_baseline"].mean()) if len(seen_sum) else float("nan"),
            }
        ]
    )
    clean_summary.to_csv(out_dir / "d3_clean_test_summary.csv", index=False)
    seen_summary.to_csv(out_dir / "d3_seen_dev_summary.csv", index=False)
    (out_dir / "d3_clean_test_summary.md").write_text(md_table(clean_summary, "D3 Clean Test Summary"))
    (out_dir / "d3_seen_dev_summary.md").write_text(md_table(seen_summary, "D3 Seen Dev Summary"))

    # paired stats
    paired_base_rows = []
    paired_d2_rows = []

    # scenario best corrected baseline per split/scenario for pool-level paired compares
    best_policy_map = {}
    for (sp, scen), g in corr_pool[corr_pool["split"].isin(["test", "seen_dev"])].groupby(["split", "scenario_id"]):
        vals = {p: float(g[p].mean()) for p in VALID_BASELINE_POLICIES if p in g.columns}
        if not vals:
            continue
        best = max(vals.values())
        best_policy = sorted([k for k, v in vals.items() if np.isclose(v, best)])[0]
        best_policy_map[(sp, scen)] = best_policy

    pool_best_base = []
    for _, r in all_dec.iterrows():
        pol = best_policy_map.get((r["split"], r["scenario_id"]), "select_frontier_correct")
        row = corr_pool[corr_pool["pool_id"] == r["pool_id"]]
        val = int(row[pol].iloc[0]) if len(row) and pol in row.columns else int(row["select_frontier_correct"].iloc[0])
        pool_best_base.append(val)
    all_dec["best_fixed_baseline_correct"] = pool_best_base

    d2_case = pd.read_csv(d2_dir / "selector_case_predictions.csv")
    d2_case = d2_case[d2_case["split"].isin(["test", "seen_dev"])][["pool_id", "split", "selected_correct"]].rename(columns={"selected_correct": "d2_selected_correct"})
    all_dec = all_dec.merge(d2_case, on=["pool_id", "split"], how="left")

    for sp in ["test", "seen_dev"]:
        s = all_dec[all_dec["split"] == sp].copy()
        if s.empty:
            continue
        d = s["selected_correct"].astype(int).to_numpy()
        b = s["best_fixed_baseline_correct"].astype(int).to_numpy()
        both_correct = int(((d == 1) & (b == 1)).sum())
        d_only = int(((d == 1) & (b == 0)).sum())
        b_only = int(((d == 0) & (b == 1)).sum())
        both_wrong = int(((d == 0) & (b == 0)).sum())
        p = mcnemar_pvalue(d_only, b_only)
        m, lo, hi = bootstrap_ci_diff(d.astype(float), b.astype(float), n_boot=1000, seed=42)
        paired_base_rows.append(
            {
                "split": sp,
                "both_correct": both_correct,
                "d3_only_correct": d_only,
                "baseline_only_correct": b_only,
                "both_wrong": both_wrong,
                "mcnemar_pvalue": p,
                "bootstrap_delta_mean": m,
                "bootstrap_ci_low": lo,
                "bootstrap_ci_high": hi,
            }
        )

        d2 = s["d2_selected_correct"].fillna(0).astype(int).to_numpy()
        both_correct = int(((d == 1) & (d2 == 1)).sum())
        d3_only = int(((d == 1) & (d2 == 0)).sum())
        d2_only = int(((d == 0) & (d2 == 1)).sum())
        both_wrong = int(((d == 0) & (d2 == 0)).sum())
        p = mcnemar_pvalue(d3_only, d2_only)
        m, lo, hi = bootstrap_ci_diff(d.astype(float), d2.astype(float), n_boot=1000, seed=42)
        paired_d2_rows.append(
            {
                "split": sp,
                "both_correct": both_correct,
                "d3_only_correct": d3_only,
                "d2_only_correct": d2_only,
                "both_wrong": both_wrong,
                "mcnemar_pvalue": p,
                "bootstrap_delta_mean": m,
                "bootstrap_ci_low": lo,
                "bootstrap_ci_high": hi,
            }
        )

    pd.DataFrame(paired_base_rows).to_csv(out_dir / "d3_paired_statistics_vs_baseline.csv", index=False)
    pd.DataFrame(paired_d2_rows).to_csv(out_dir / "d3_paired_statistics_vs_d2.csv", index=False)
    (out_dir / "d3_paired_statistics_report.md").write_text(
        "\n".join(
            [
                "# D3 Paired Statistics Report",
                "",
                f"Best D3 model: {best_model}",
                f"Selected threshold policy: {policy_name}",
                f"Global threshold fallback: {tau_global}",
            ]
        )
        + "\n"
    )

    # frontier contribution
    fr_rows = []
    fr_missed = []
    fr_selected = []

    for (sp, scen, prov, ds), g in all_dec.groupby(["split", "scenario_id", "provider", "dataset"]):
        cpool = corr_pool[(corr_pool["split"] == sp) & (corr_pool["scenario_id"] == scen)]
        frontier_raw = float(cpool["select_frontier_correct"].mean()) if len(cpool) else float("nan")
        choose_front = (g["selected_method"] == METHOD_ID_BY_ALIAS["frontier"]).astype(int)
        good_front = ((g["selected_method"] == METHOD_ID_BY_ALIAS["frontier"]) & (g["selected_correct"] == 1)).astype(int)
        default_front = (g["baseline_method"] == METHOD_ID_BY_ALIAS["frontier"]).astype(int)

        # simulate removing frontier from selected outputs: if selected frontier and override, fallback to baseline; if baseline is frontier fallback no change for simplicity
        no_front_correct = []
        for _, r in g.iterrows():
            if clean_text(r["selected_method"]) == METHOD_ID_BY_ALIAS["frontier"]:
                no_front_correct.append(int(r["baseline_correct"]))
            else:
                no_front_correct.append(int(r["selected_correct"]))

        acc = float(g["selected_correct"].mean())
        acc_no_front = float(np.mean(no_front_correct)) if len(no_front_correct) else float("nan")

        fr_rows.append(
            {
                "split": sp,
                "scenario_id": scen,
                "provider": prov,
                "dataset": ds,
                "frontier_raw_accuracy": frontier_raw,
                "default_policy_uses_frontier_rate": float(default_front.mean()),
                "d3_chooses_frontier_rate": float(choose_front.mean()),
                "d3_correct_via_frontier_count": int(good_front.sum()),
                "d3_good_overrides_to_frontier": int(((g["override_kind"] == "good") & (g["selected_method"] == METHOD_ID_BY_ALIAS["frontier"])).sum()),
                "d3_bad_overrides_to_frontier": int(((g["override_kind"] == "bad") & (g["selected_method"] == METHOD_ID_BY_ALIAS["frontier"])).sum()),
                "d3_accuracy": acc,
                "d3_accuracy_without_frontier_simulated": acc_no_front,
                "accuracy_drop_when_frontier_removed": float(acc - acc_no_front),
            }
        )

        miss = g[(g["baseline_method"] == METHOD_ID_BY_ALIAS["frontier"]) & (g["baseline_correct"] == 1) & (g["selected_correct"] == 0)].copy()
        if len(miss):
            fr_missed.append(miss)
        selc = g[(g["selected_method"] == METHOD_ID_BY_ALIAS["frontier"]) & (g["selected_correct"] == 1)].copy()
        if len(selc):
            fr_selected.append(selc)

    fr_df = pd.DataFrame(fr_rows)
    fr_df.to_csv(out_dir / "d3_frontier_contribution_analysis.csv", index=False)
    (out_dir / "d3_frontier_contribution_analysis.md").write_text(md_table(fr_df, "D3 Frontier Contribution Analysis"))
    (pd.concat(fr_missed, ignore_index=True) if fr_missed else pd.DataFrame(columns=all_dec.columns)).to_csv(out_dir / "d3_frontier_missed_rescue_cases.csv", index=False)
    (pd.concat(fr_selected, ignore_index=True) if fr_selected else pd.DataFrame(columns=all_dec.columns)).to_csv(out_dir / "d3_frontier_selected_correct_cases.csv", index=False)

    # failure diagnostics
    fail = d3_out[d3_out["result_vs_corrected_best_baseline"] == "loss"].copy()
    diag_rows = []
    loss_lines = ["# D3 Scenario Loss Diagnosis", ""]
    for _, r in d3_out.iterrows():
        scen = r["scenario_id"]
        sub = all_dec[(all_dec["split"] == r["split"]) & (all_dec["scenario_id"] == scen)]
        bad_over = int((sub["override_kind"] == "bad").sum())
        no_over = int(((sub["override_happened"] == 0) & (sub["baseline_correct"] == 0) & (sub["selected_correct"] == 0)).sum())
        mode = "false_override" if bad_over > no_over else "missed_needed_override"
        if r["oracle"] - r["baseline_accuracy"] < 0.05:
            mode = "low_oracle_ceiling"
        diag_rows.append(
            {
                "split": r["split"],
                "scenario_id": scen,
                "provider": r["provider"],
                "dataset": r["dataset"],
                "d3_minus_baseline": float(r["d3_minus_baseline"]),
                "override_coverage": float(r["override_coverage"]),
                "bad_overrides": bad_over,
                "top_error_mode": mode,
                "recommended_fix": "increase threshold" if mode == "false_override" else "lower threshold / add ranking features",
            }
        )
        loss_lines.append(f"- {r['split']}::{scen}: delta={r['d3_minus_baseline']:+.6f}, mode={mode}")

    diag_df = pd.DataFrame(diag_rows)
    diag_df.to_csv(out_dir / "d3_per_scenario_failure_diagnostics.md", index=False)
    # also write markdown table for requested path
    (out_dir / "d3_per_scenario_failure_diagnostics.md").write_text(md_table(diag_df, "D3 Per Scenario Failure Diagnostics"))
    (out_dir / "d3_scenario_loss_diagnosis.md").write_text("\n".join(loss_lines) + "\n")

    # leave-one diagnostics (feasible lightweight; use best model scores by scenario subset)
    loso_rows = []
    for scen in sorted(ov[ov["split"].isin(["test", "seen_dev"])]["scenario_id"].unique().tolist()):
        sub = ov[(ov["split"].isin(["test", "seen_dev"])) & (ov["scenario_id"] == scen)].copy()
        if sub.empty:
            continue
        # use selected threshold policy as backoff
        split_for_eval = "test" if len(sub[sub["split"] == "test"]) else "seen_dev"
        ss = sub[sub["split"] == split_for_eval].copy()
        # compute scores from chosen model using train encoder columns
        Xs = encode_features(tr, ss, use_cols, cat_cols)[1]
        # refit chosen model quickly
        chosen_spec = next((s for s in specs if s.name == best_model or (best_model.startswith(s.name) and "fallback" in best_model)), specs[0])
        model = train_model(chosen_spec, Xtr, ytr)
        ps = predict_prob(model, Xs)
        dec, _ = evaluate_policy(split_for_eval, ss, ps, defaults_by_pool, tau_global=tau_global, tau_by_scenario=tau_by_scenario if policy_name.startswith("per_scenario") else None)
        acc = float(dec["selected_correct"].mean()) if len(dec) else float("nan")
        loso_rows.append({"scenario_id": scen, "split": split_for_eval, "n_pools": int(dec["pool_id"].nunique()) if len(dec) else 0, "d3_accuracy": acc, "note": "lightweight_backoff_eval"})

    lopo_rows = []
    for prov in sorted(ov[ov["split"].isin(["test", "seen_dev"])]["provider"].unique().tolist()):
        ss = ov[(ov["split"].isin(["test", "seen_dev"])) & (ov["provider"] == prov)].copy()
        if ss.empty:
            continue
        split_for_eval = "test" if len(ss[ss["split"] == "test"]) else "seen_dev"
        ss = ss[ss["split"] == split_for_eval].copy()
        Xs = encode_features(tr, ss, use_cols, cat_cols)[1]
        chosen_spec = next((s for s in specs if s.name == best_model or (best_model.startswith(s.name) and "fallback" in best_model)), specs[0])
        model = train_model(chosen_spec, Xtr, ytr)
        ps = predict_prob(model, Xs)
        dec, _ = evaluate_policy(split_for_eval, ss, ps, defaults_by_pool, tau_global=tau_global, tau_by_scenario=tau_by_scenario if policy_name.startswith("per_scenario") else None)
        acc = float(dec["selected_correct"].mean()) if len(dec) else float("nan")
        lopo_rows.append({"provider": prov, "split": split_for_eval, "n_pools": int(dec["pool_id"].nunique()) if len(dec) else 0, "d3_accuracy": acc, "note": "lightweight_backoff_eval"})

    lodo_rows = []
    for ds in sorted(ov[ov["split"].isin(["test", "seen_dev"])]["dataset"].unique().tolist()):
        ss = ov[(ov["split"].isin(["test", "seen_dev"])) & (ov["dataset"] == ds)].copy()
        if ss.empty:
            continue
        split_for_eval = "test" if len(ss[ss["split"] == "test"]) else "seen_dev"
        ss = ss[ss["split"] == split_for_eval].copy()
        Xs = encode_features(tr, ss, use_cols, cat_cols)[1]
        chosen_spec = next((s for s in specs if s.name == best_model or (best_model.startswith(s.name) and "fallback" in best_model)), specs[0])
        model = train_model(chosen_spec, Xtr, ytr)
        ps = predict_prob(model, Xs)
        dec, _ = evaluate_policy(split_for_eval, ss, ps, defaults_by_pool, tau_global=tau_global, tau_by_scenario=tau_by_scenario if policy_name.startswith("per_scenario") else None)
        acc = float(dec["selected_correct"].mean()) if len(dec) else float("nan")
        lodo_rows.append({"dataset": ds, "split": split_for_eval, "n_pools": int(dec["pool_id"].nunique()) if len(dec) else 0, "d3_accuracy": acc, "note": "lightweight_backoff_eval"})

    pd.DataFrame(loso_rows).to_csv(out_dir / "d3_leave_one_scenario_out_results.csv", index=False)
    pd.DataFrame(lopo_rows).to_csv(out_dir / "d3_leave_one_provider_out_results.csv", index=False)
    pd.DataFrame(lodo_rows).to_csv(out_dir / "d3_leave_one_dataset_out_results.csv", index=False)
    (out_dir / "d3_leave_one_backoff_report.md").write_text(
        "\n".join(
            [
                "# D3 Leave-One Backoff Report",
                "",
                "Lightweight leave-one diagnostics were computed with the selected D3 policy and global/per-scenario threshold backoff.",
                "When held-out groups lacked tailored validation thresholds, global threshold fallback was used.",
            ]
        )
        + "\n"
    )

    # promotion decision
    clean = d3_out[d3_out["split"] == "test"].copy()
    seen = d3_out[d3_out["split"] == "seen_dev"].copy()
    clean_w = int((clean["result_vs_corrected_best_baseline"] == "win").sum())
    clean_t = int((clean["result_vs_corrected_best_baseline"] == "tie").sum())
    clean_l = int((clean["result_vs_corrected_best_baseline"] == "loss").sum())
    seen_w = int((seen["result_vs_corrected_best_baseline"] == "win").sum())
    seen_t = int((seen["result_vs_corrected_best_baseline"] == "tie").sum())
    seen_l = int((seen["result_vs_corrected_best_baseline"] == "loss").sum())

    preserve_d2_wins = bool(((d3_out["d3_minus_d2"] >= 0).all())) if len(d3_out) else False
    cohere_gsm8k = d3_out[(d3_out["split"] == "test") & (d3_out["scenario_id"] == "cohere_gsm8k")]
    fix_cohere_gsm8k = bool((cohere_gsm8k["d3_minus_baseline"] >= 0).all()) if len(cohere_gsm8k) else False

    next_opt = "A. D4 LambdaMART/ranking"
    if clean_l > 0:
        next_opt = "A. D4 LambdaMART/ranking"
    if clean_l == 0 and seen_l > 0:
        next_opt = "B. D5 oracle head"
    if clean_l > 0 and not fix_cohere_gsm8k:
        next_opt = "C. D6 frontier improvement pilot"

    prom_lines = [
        "# D3 Promotion Decision",
        "",
        f"Does D3 win/tie all clean test scenarios? {'Yes' if clean_l == 0 else 'No'}",
        f"Does D3 win/tie all seen-dev scenarios? {'Yes' if seen_l == 0 else 'No'}",
        f"Does D3 improve over D2 on mean scenario accuracy? {'Yes' if float(d3_out['d3_minus_d2'].mean()) > 0 else 'No'}",
        f"Does D3 preserve D2 wins (non-regression per scenario)? {'Yes' if preserve_d2_wins else 'No'}",
        f"Does D3 fix cohere_gsm8k? {'Yes' if fix_cohere_gsm8k else 'No'}",
        f"Clean W/T/L: {clean_w}/{clean_t}/{clean_l}",
        f"Seen-dev W/T/L: {seen_w}/{seen_t}/{seen_l}",
        f"Recommended next job: {next_opt}",
    ]
    (out_dir / "d3_promotion_decision.md").write_text("\n".join(prom_lines) + "\n")

    # training ledger update
    ledger_root = Path(args.ledger_root)
    ledger_root.mkdir(parents=True, exist_ok=True)
    csv_path = ledger_root / "training_experiment_ledger.csv"
    md_path = ledger_root / "training_experiment_ledger.md"
    backlog_path = ledger_root / "training_backlog.md"

    row = {
        "run_id": out_dir.name,
        "date_time_utc": now_utc(),
        "input_table_path": str(in_dir),
        "output_path": str(out_dir),
        "model_families_tried": ",".join(sorted({s.family for s in specs})),
        "feature_groups_used": "runtime_safe+fold_safe_reliability+override_delta_features",
        "reliability_features_used": "yes",
        "complementarity_features_used": "partial",
        "calibration_used": "threshold_tuning_validation",
        "gpu_used": "yes" if bool(model_avail_df["gpu_used"].fillna(False).any()) else "no",
        "clean_test_wins_ties_losses": f"{clean_w}/{clean_t}/{clean_l}",
        "seen_dev_wins_ties_losses": f"{seen_w}/{seen_t}/{seen_l}",
        "macro_accuracy": float(d3_out["d3_accuracy"].mean()) if len(d3_out) else float("nan"),
        "worst_scenario_accuracy": float(d3_out["d3_accuracy"].min()) if len(d3_out) else float("nan"),
        "biggest_losses": "; ".join(
            [
                f"{r.split}:{r.scenario_id}:{r.d3_minus_baseline:+.4f}"
                for r in d3_out.sort_values("d3_minus_baseline").head(3).itertuples(index=False)
            ]
        )
        if len(d3_out)
        else "",
        "promotion_decision": "promotable" if (clean_l == 0 and seen_l == 0) else "not_promotable",
        "next_recommended_training": next_opt,
    }

    if csv_path.exists():
        led = pd.read_csv(csv_path)
    else:
        led = pd.DataFrame(columns=list(row.keys()))
    led = pd.concat([led, pd.DataFrame([row])], ignore_index=True)
    led.to_csv(csv_path, index=False)

    (md_path).write_text(md_table(led, "Training Experiment Ledger"))

    backlog_lines = [
        "# Training Backlog",
        "",
        "Not-yet-run planned experiments:",
        "- D4 LambdaMART/pool-ranking",
        "- D5 oracle-availability head",
        "- D6 frontier variant generation/inclusion",
        "- D7 Fireworks/Cerebras/full MATH-500 data expansion",
    ]
    backlog_path.write_text("\n".join(backlog_lines) + "\n")

    # manifests + reports
    manifest = {
        "generated_at": now_utc(),
        "input_dir": str(in_dir),
        "d2_dir": str(d2_dir),
        "corrected_eval_dir": str(corr_eval_dir),
        "corrected_baseline_dir": str(corr_base_dir),
        "output_dir": str(out_dir),
        "rows": {
            "candidate_rows": int(len(cand)),
            "override_rows": int(len(ov)),
            "pool_rows": int(len(dp)),
            "split_override_rows": {
                "train": int((ov["split"] == "train").sum()),
                "validation": int((ov["split"] == "validation").sum()),
                "test": int((ov["split"] == "test").sum()),
                "seen_dev": int((ov["split"] == "seen_dev").sum()),
            },
        },
        "best_model": best_model,
        "selected_threshold_policy": {
            "policy": policy_name,
            "tau_global": tau_global,
            "scenario_threshold_count": len(tau_by_scenario),
        },
    }
    (out_dir / "d3_training_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (out_dir / "job_d3_training_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

    ofm = {
        "features_used": use_cols,
        "categorical_features": cat_cols,
        "reliability_features": rel_cols,
    }
    (out_dir / "override_feature_manifest.json").write_text(json.dumps(ofm, indent=2) + "\n")

    # final job report
    rep_lines = [
        "# JOB_D3_CONSERVATIVE_OVERRIDE_REPORT_20260525",
        "",
        f"Input: `{in_dir}`",
        f"Corrected baseline input: `{corr_base_dir}`",
        f"Output: `{out_dir}`",
        "",
        f"Best D3 model: `{best_model}`",
        f"Threshold policy: `{policy_name}` (global fallback tau={tau_global})",
        f"Clean test wins/ties/losses: {clean_w}/{clean_t}/{clean_l}",
        f"Seen-dev wins/ties/losses: {seen_w}/{seen_t}/{seen_l}",
        f"Next action: {next_opt}",
    ]
    (out_dir / "JOB_D3_CONSERVATIVE_OVERRIDE_REPORT_20260525.md").write_text("\n".join(rep_lines) + "\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}")
        print(traceback.format_exc())
        raise
