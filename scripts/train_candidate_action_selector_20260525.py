#!/usr/bin/env python3
"""Offline Job D: train/evaluate candidate-action selector from unified tables.

No API calls. Uses local artifacts only.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from pandas.api.types import is_numeric_dtype
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss, roc_auc_score
from sklearn.preprocessing import OneHotEncoder


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
    if not root.exists():
        root.mkdir(parents=True, exist_ok=True)
    run = root / slug_now()
    run.mkdir(parents=True, exist_ok=False)
    return run


def run_command(cmd: str) -> str:
    p = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return f"$ {cmd}\n{p.stdout}{p.stderr}\n"


def has_pkg(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def available_fixed_policy_baseline_cols(df: pd.DataFrame) -> list[str]:
    """Return valid fixed-policy baselines present in df.

    Preference is corrected plurality/agreement columns when available.
    """
    preferred = [
        "select_frontier_correct",
        "select_l1_correct",
        "select_s1_correct",
        "select_tale_correct",
        "pooled4_plurality_correct",
        "agreement_largest_cluster_correct",
        "agreement_strict_2plus_correct",
        # legacy compatibility
        "pooled4_correct",
        "agreement_only_correct",
    ]
    return [c for c in preferred if c in df.columns]


def best_fixed_policy_for_group(g: pd.DataFrame, baseline_cols: list[str]) -> tuple[str, float]:
    vals = {c: float(g[c].mean()) for c in baseline_cols if c in g.columns}
    if not vals:
        return "", float("nan")
    best_val = max(vals.values())
    best_names = sorted([k for k, v in vals.items() if np.isclose(v, best_val)])
    return ";".join(best_names), float(best_val)


def ece_score(y_true: np.ndarray, y_prob: np.ndarray, bins: int = 10) -> float:
    y_true = y_true.astype(float)
    y_prob = np.clip(y_prob.astype(float), 1e-6, 1 - 1e-6)
    edges = np.linspace(0.0, 1.0, bins + 1)
    ece = 0.0
    n = len(y_true)
    if n == 0:
        return float("nan")
    for i in range(bins):
        lo, hi = edges[i], edges[i + 1]
        mask = (y_prob >= lo) & (y_prob < hi if i < bins - 1 else y_prob <= hi)
        m = int(mask.sum())
        if m == 0:
            continue
        acc = y_true[mask].mean()
        conf = y_prob[mask].mean()
        ece += (m / n) * abs(acc - conf)
    return float(ece)


@dataclass
class ModelPack:
    name: str
    estimator: Any
    kind: str


def build_models(availability: dict[str, bool]) -> tuple[list[ModelPack], list[dict[str, Any]]]:
    rows = []
    models: list[ModelPack] = []

    models.append(
        ModelPack(
            "logistic_regression",
            LogisticRegression(max_iter=2000, n_jobs=None, solver="lbfgs"),
            "linear",
        )
    )
    rows.append({"model": "logistic_regression", "available": True, "used": True, "note": "sklearn"})

    models.append(
        ModelPack(
            "random_forest",
            RandomForestClassifier(
                n_estimators=400,
                random_state=42,
                min_samples_leaf=1,
                n_jobs=-1,
            ),
            "tree",
        )
    )
    rows.append({"model": "random_forest", "available": True, "used": True, "note": "sklearn"})

    models.append(
        ModelPack(
            "hist_gradient_boosting",
            HistGradientBoostingClassifier(
                random_state=42,
                max_depth=8,
                learning_rate=0.05,
                max_iter=300,
            ),
            "tree",
        )
    )
    rows.append({"model": "hist_gradient_boosting", "available": True, "used": True, "note": "sklearn"})

    if availability.get("xgboost"):
        from xgboost import XGBClassifier

        models.append(
            ModelPack(
                "xgboost",
                XGBClassifier(
                    n_estimators=350,
                    max_depth=8,
                    learning_rate=0.05,
                    subsample=0.9,
                    colsample_bytree=0.9,
                    random_state=42,
                    objective="binary:logistic",
                    eval_metric="logloss",
                    n_jobs=-1,
                ),
                "tree",
            )
        )
        rows.append({"model": "xgboost", "available": True, "used": True, "note": "installed"})
    else:
        rows.append({"model": "xgboost", "available": False, "used": False, "note": "not installed"})

    if availability.get("lightgbm"):
        from lightgbm import LGBMClassifier

        models.append(
            ModelPack(
                "lightgbm",
                LGBMClassifier(
                    n_estimators=350,
                    learning_rate=0.05,
                    num_leaves=63,
                    random_state=42,
                    objective="binary",
                    n_jobs=-1,
                ),
                "tree",
            )
        )
        rows.append({"model": "lightgbm", "available": True, "used": True, "note": "installed"})
    else:
        rows.append({"model": "lightgbm", "available": False, "used": False, "note": "not installed"})

    if availability.get("catboost"):
        from catboost import CatBoostClassifier

        models.append(
            ModelPack(
                "catboost",
                CatBoostClassifier(
                    loss_function="Logloss",
                    random_seed=42,
                    verbose=False,
                ),
                "tree",
            )
        )
        rows.append({"model": "catboost", "available": True, "used": True, "note": "installed"})
    else:
        rows.append({"model": "catboost", "available": False, "used": False, "note": "not installed"})

    return models, rows


def prepare_features(
    df: pd.DataFrame,
    allowed_features: list[str],
    forbidden: set[str],
) -> tuple[pd.DataFrame, list[str], list[str], dict[str, Any]]:
    present = [c for c in allowed_features if c in df.columns]
    rejected = [c for c in allowed_features if c not in df.columns]

    filtered = [c for c in present if c not in forbidden]
    rejected.extend(sorted(c for c in present if c in forbidden))

    leakage_hits = [c for c in filtered if c in forbidden]
    if leakage_hits:
        raise RuntimeError(f"Leakage columns remained in filtered feature set: {leakage_hits}")

    X = df[filtered].copy()

    # Force known text-heavy fields into categorical handling to avoid parsing risk
    for col in ["extracted_answer", "normalized_answer", "answer_cluster_id", "clustering_version", "dataset_family", "provider_family", "model_family", "model_type_known", "math_subject"]:
        if col in X.columns:
            X[col] = X[col].astype("string")

    for col in X.columns:
        if X[col].dtype == "bool":
            X[col] = X[col].astype(int)

    # Coerce numerics when mostly numeric
    for col in X.columns:
        if is_numeric_dtype(X[col]):
            continue
        converted = pd.to_numeric(X[col], errors="coerce")
        if converted.notna().mean() > 0.98:
            X[col] = converted

    numeric_cols = [c for c in X.columns if is_numeric_dtype(X[c])]
    categorical_cols = [c for c in X.columns if c not in numeric_cols]

    meta = {
        "n_features_input": len(allowed_features),
        "n_features_present": len(present),
        "n_features_used": len(filtered),
        "n_numeric": len(numeric_cols),
        "n_categorical": len(categorical_cols),
    }
    return X, filtered, rejected, meta


def fit_transformer(X_train: pd.DataFrame, X_all: dict[str, pd.DataFrame]) -> tuple[dict[str, np.ndarray], list[str], dict[str, Any]]:
    num_cols = [c for c in X_train.columns if is_numeric_dtype(X_train[c])]
    # Keep only numeric columns with at least one observed value in train.
    num_cols = [c for c in num_cols if X_train[c].notna().any()]
    cat_cols = [c for c in X_train.columns if c not in num_cols]

    num_imp = SimpleImputer(strategy="median")
    if num_cols:
        X_num_train_df = X_train[num_cols].replace([np.inf, -np.inf], np.nan)
        X_num_train = num_imp.fit_transform(X_num_train_df)
    else:
        X_num_train = np.empty((len(X_train), 0))
    if cat_cols:
        X_cat_train_imp = (
            X_train[cat_cols]
            .copy()
            .astype("string")
            .fillna("__MISSING__")
            .astype(str)
            .to_numpy()
        )
    else:
        X_cat_train_imp = np.empty((len(X_train), 0), dtype=object)

    if cat_cols:
        enc = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
        X_cat_train = enc.fit_transform(X_cat_train_imp)
        cat_names = enc.get_feature_names_out(cat_cols).tolist()
    else:
        enc = None
        X_cat_train = np.empty((len(X_train), 0))
        cat_names = []

    X_train_mat = np.hstack([X_num_train, X_cat_train])

    out = {"train": X_train_mat}
    for key, Xd in X_all.items():
        if key == "train":
            continue
        if num_cols:
            X_num_df = Xd[num_cols].replace([np.inf, -np.inf], np.nan)
            X_num = num_imp.transform(X_num_df)
        else:
            X_num = np.empty((len(Xd), 0))
        if cat_cols:
            X_cat_i = (
                Xd[cat_cols]
                .copy()
                .astype("string")
                .fillna("__MISSING__")
                .astype(str)
                .to_numpy()
            )
        else:
            X_cat_i = np.empty((len(Xd), 0), dtype=object)
        X_cat = enc.transform(X_cat_i) if enc is not None else np.empty((len(Xd), 0))
        out[key] = np.hstack([X_num, X_cat])

    feature_names = list(num_cols) + cat_names
    meta = {
        "numeric_columns": num_cols,
        "categorical_columns": cat_cols,
        "transformed_feature_count": len(feature_names),
    }
    return out, feature_names, meta


def safe_candidate_metrics(y_true: np.ndarray, y_prob: np.ndarray) -> dict[str, float]:
    y_true = y_true.astype(int)
    y_prob = np.clip(y_prob.astype(float), 1e-6, 1 - 1e-6)
    out = {
        "candidate_brier": float(np.mean((y_prob - y_true) ** 2)) if len(y_true) else float("nan"),
        "candidate_log_loss": float(log_loss(y_true, y_prob, labels=[0, 1])) if len(np.unique(y_true)) > 1 else float("nan"),
        "candidate_auc": float(roc_auc_score(y_true, y_prob)) if len(np.unique(y_true)) > 1 else float("nan"),
    }
    return out


def select_by_pool(df_split: pd.DataFrame, probs: np.ndarray) -> pd.DataFrame:
    tmp = df_split.copy()
    tmp["pred_prob"] = probs
    method_rank = {
        "direct_reserve_semantic_frontier_v2": 0,
        "external_l1_max": 1,
        "external_s1_budget_forcing": 2,
        "external_tale_prompt_budgeting": 3,
    }
    tmp["_method_rank"] = tmp["method"].map(method_rank).fillna(99).astype(int)
    tmp = tmp.sort_values(["pool_id", "pred_prob", "_method_rank"], ascending=[True, False, True])
    selected = tmp.groupby("pool_id", as_index=False).first()
    selected = selected.drop(columns=["_method_rank"])
    selected["selected_correct"] = selected["candidate_correct"].astype(int)
    selected["selected_method_alias"] = selected["method_family"]
    selected["selected_is_frontier"] = (selected["method"] == "direct_reserve_semantic_frontier_v2").astype(int)
    selected["selected_is_external"] = 1 - selected["selected_is_frontier"]
    return selected


def evaluate_split(
    model_name: str,
    split_name: str,
    df_split: pd.DataFrame,
    probs: np.ndarray,
) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame]:
    y_true = df_split["candidate_correct"].astype(int).to_numpy()
    cand = safe_candidate_metrics(y_true, probs)
    selected = select_by_pool(df_split, probs)

    by_scenario = (
        selected.groupby(["scenario_id", "provider", "dataset"], as_index=False)
        .agg(
            n_pools=("pool_id", "count"),
            learned_accuracy=("selected_correct", "mean"),
            selector_frontier_rate=("selected_is_frontier", "mean"),
            selector_external_rate=("selected_is_external", "mean"),
        )
    )

    macro = float(by_scenario["learned_accuracy"].mean()) if len(by_scenario) else float("nan")
    worst = float(by_scenario["learned_accuracy"].min()) if len(by_scenario) else float("nan")

    overall = {
        "model": model_name,
        "split": split_name,
        "n_candidate_rows": int(len(df_split)),
        "n_pools": int(selected["pool_id"].nunique()),
        "pool_selected_accuracy": float(selected["selected_correct"].mean()) if len(selected) else float("nan"),
        "macro_scenario_accuracy": macro,
        "worst_scenario_accuracy": worst,
        **cand,
    }

    by_scenario.insert(0, "model", model_name)
    by_scenario.insert(1, "split", split_name)
    return overall, by_scenario, selected


def pool_baseline_comparison(
    selected_df: pd.DataFrame,
    baseline_df: pd.DataFrame,
    split_name: str,
) -> pd.DataFrame:
    use_cols = [
        "pool_id",
        "scenario_id",
        "provider",
        "dataset",
        "split",
        "select_frontier_correct",
        "select_l1_correct",
        "select_s1_correct",
        "select_tale_correct",
        "pooled4_correct",
        "agreement_only_correct",
        "oracle_correct",
    ]
    b = baseline_df[use_cols].copy()
    merged = selected_df[["pool_id", "selected_correct", "selected_method_alias", "method", "pred_prob"]].merge(b, on="pool_id", how="left")

    # IMPORTANT: scenario-level fixed-policy baseline avoids row-wise oracle-like max logic.
    baseline_scope = b[b["pool_id"].isin(selected_df["pool_id"])].copy()
    fixed_cols = available_fixed_policy_baseline_cols(baseline_scope)
    raw_cols = [c for c in ["select_frontier_correct", "select_l1_correct", "select_s1_correct", "select_tale_correct"] if c in baseline_scope.columns]

    learned = (
        merged.groupby(["scenario_id", "provider", "dataset"], as_index=False)
        .agg(
            pools=("pool_id", "count"),
            learned_accuracy=("selected_correct", "mean"),
        )
    )
    oracle = (
        baseline_scope.groupby(["scenario_id", "provider", "dataset"], as_index=False)
        .agg(oracle_ceiling=("oracle_correct", "mean"))
    )

    rows = []
    for _, r in learned.iterrows():
        mask = (
            (baseline_scope["scenario_id"] == r["scenario_id"])
            & (baseline_scope["provider"] == r["provider"])
            & (baseline_scope["dataset"] == r["dataset"])
        )
        g = baseline_scope[mask]
        best_name, best_val = best_fixed_policy_for_group(g, fixed_cols)
        _, best_raw_val = best_fixed_policy_for_group(g, raw_cols)
        rows.append(
            {
                "scenario_id": r["scenario_id"],
                "provider": r["provider"],
                "dataset": r["dataset"],
                "best_overall_baseline_name": best_name,
                "best_overall_baseline_correct": best_val,
                "best_raw_baseline_correct": best_raw_val,
            }
        )
    scen_base = pd.DataFrame(rows)
    by_scenario = learned.merge(scen_base, on=["scenario_id", "provider", "dataset"], how="left").merge(
        oracle, on=["scenario_id", "provider", "dataset"], how="left"
    )
    by_scenario = by_scenario.rename(
        columns={
            "best_overall_baseline_correct": "best_baseline_accuracy",
            "best_raw_baseline_correct": "best_raw_baseline_accuracy",
        }
    )
    by_scenario["delta_vs_best_baseline"] = by_scenario["learned_accuracy"] - by_scenario["best_baseline_accuracy"]
    by_scenario["oracle_gap_recovered"] = by_scenario.apply(
        lambda r: ((r["learned_accuracy"] - r["best_baseline_accuracy"]) / (r["oracle_ceiling"] - r["best_baseline_accuracy"]))
        if (r["oracle_ceiling"] - r["best_baseline_accuracy"]) > 0 else np.nan,
        axis=1,
    )
    by_scenario["result"] = by_scenario["delta_vs_best_baseline"].map(lambda d: "win" if d > 0 else ("tie" if d == 0 else "loss"))
    by_scenario.insert(0, "split", split_name)

    # Keep row-level legacy fields for diagnostics, but do not use them as headline baseline.
    merged = merged.merge(
        scen_base[["scenario_id", "provider", "dataset", "best_overall_baseline_name", "best_overall_baseline_correct"]],
        on=["scenario_id", "provider", "dataset"],
        how="left",
    )
    merged["delta_vs_best_baseline"] = merged["selected_correct"] - merged["best_overall_baseline_correct"]
    merged["win_tie_loss_vs_best_baseline"] = merged["delta_vs_best_baseline"].map(lambda d: "win" if d > 0 else ("tie" if d == 0 else "loss"))

    return by_scenario, merged


def md_table(df: pd.DataFrame, title: str) -> str:
    lines = [f"# {title}", ""]
    if df.empty:
        lines.append("(no rows)")
        return "\n".join(lines) + "\n"
    cols = list(df.columns)
    lines.append("| " + " | ".join(cols) + " |")
    lines.append("|" + "|".join(["---"] * len(cols)) + "|")
    for _, r in df.iterrows():
        lines.append("| " + " | ".join(clean_text(r[c]) for c in cols) + " |")
    return "\n".join(lines) + "\n"


def fit_platt(y_val: np.ndarray, p_val: np.ndarray, p_target: np.ndarray) -> np.ndarray:
    p_val = np.clip(p_val.astype(float), 1e-6, 1 - 1e-6)
    p_target = np.clip(p_target.astype(float), 1e-6, 1 - 1e-6)
    logit = np.log(p_val / (1 - p_val)).reshape(-1, 1)
    logit_t = np.log(p_target / (1 - p_target)).reshape(-1, 1)
    lr = LogisticRegression(max_iter=2000)
    lr.fit(logit, y_val.astype(int))
    return lr.predict_proba(logit_t)[:, 1]


def leave_one_group_eval(
    title: str,
    candidate_df: pd.DataFrame,
    baseline_df: pd.DataFrame,
    X_full: pd.DataFrame,
    group_col: str,
    best_model_factory: Any,
    run_dir: Path,
) -> pd.DataFrame:
    clean = candidate_df[candidate_df["split"].isin(["train", "validation", "test"])].copy()
    groups = sorted(clean[group_col].dropna().unique().tolist())
    rows = []

    for g in groups:
        train_idx = clean.index[clean[group_col] != g]
        test_idx = clean.index[clean[group_col] == g]
        if len(test_idx) == 0 or len(train_idx) == 0:
            continue
        y_train = candidate_df.loc[train_idx, "candidate_correct"].astype(int)
        y_test = candidate_df.loc[test_idx, "candidate_correct"].astype(int)
        if y_train.nunique() < 2:
            rows.append({
                group_col: g,
                "n_candidate_rows": len(test_idx),
                "n_pools": int(candidate_df.loc[test_idx, "pool_id"].nunique()),
                "learned_accuracy": np.nan,
                "best_baseline_accuracy": np.nan,
                "delta_vs_best_baseline": np.nan,
                "note": "train_target_single_class",
            })
            continue

        X_train = X_full.loc[train_idx]
        X_test = X_full.loc[test_idx]

        model, transformer, feature_names = best_model_factory(X_train, y_train)
        Xt = transformer(X_test)
        if hasattr(model, "predict_proba"):
            probs = model.predict_proba(Xt)[:, 1]
        else:
            probs = model.predict(Xt).astype(float)

        selected = select_by_pool(candidate_df.loc[test_idx], probs)

        b = baseline_df[baseline_df["pool_id"].isin(selected["pool_id"])].copy()
        if len(b):
            cols = available_fixed_policy_baseline_cols(b)
            _, best_baseline_acc = best_fixed_policy_for_group(b, cols)
        else:
            best_baseline_acc = np.nan

        learned_acc = selected["selected_correct"].mean() if len(selected) else np.nan
        rows.append(
            {
                group_col: g,
                "n_candidate_rows": int(len(test_idx)),
                "n_pools": int(selected["pool_id"].nunique()),
                "learned_accuracy": float(learned_acc),
                "best_baseline_accuracy": float(best_baseline_acc),
                "delta_vs_best_baseline": float(learned_acc - best_baseline_acc) if pd.notna(best_baseline_acc) else np.nan,
                "note": "ok",
            }
        )

    out = pd.DataFrame(rows)
    out.to_csv(run_dir / f"{title}.csv", index=False)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Job D candidate-action training")
    parser.add_argument("--input-dir", default="outputs/unified_learning_tables_20260525/run_20260525T184354Z")
    parser.add_argument("--output-root", default="outputs/job_d_candidate_action_training_20260525")
    args = parser.parse_args()

    in_dir = Path(args.input_dir)
    out_root = Path(args.output_root)
    run_dir = ensure_run_dir(out_root)

    # run log with required state refresh commands
    with (run_dir / "run.log").open("w") as f:
        f.write(f"Generated at: {now_utc()}\n\n")
        f.write(run_command("pwd"))
        f.write(run_command("date"))
        f.write(run_command("git status --short"))
        f.write(run_command("git branch -vv"))
        f.write(run_command("git log --oneline -10"))
        f.write(run_command("tmux ls || true"))
        f.write(run_command("python3 -V"))
        f.write(run_command("which python3"))

    candidate_df = pd.read_csv(in_dir / "unified_candidate_action_table.csv")
    pool_df = pd.read_csv(in_dir / "unified_pool_level_table.csv")
    baseline_df = pd.read_csv(in_dir / "baseline_pool_decisions.csv")
    baseline_summary_df = pd.read_csv(in_dir / "baseline_summary_by_scenario.csv")

    allowlist = [x.strip() for x in (in_dir / "feature_allowlist_candidate_level.txt").read_text().splitlines() if x.strip()]
    forbidden = {x.strip() for x in (in_dir / "forbidden_feature_list.txt").read_text().splitlines() if x.strip()}

    # Ensure target exists and types
    candidate_df["candidate_correct"] = candidate_df["candidate_correct"].map(bool_int)
    candidate_df["split"] = candidate_df["split"].astype(str)

    X_df, used_cols, rejected_cols, feat_meta = prepare_features(candidate_df, allowlist, forbidden)

    # leakage check report
    leakage_lines = [
        "# Leakage Check Before Training",
        "",
        f"Input candidate rows: {len(candidate_df)}",
        f"Runtime allowlist count (requested): {len(allowlist)}",
        f"Feature columns used: {len(used_cols)}",
        f"Rejected columns: {len(rejected_cols)}",
        "",
        "Forbidden columns from policy were excluded from model features.",
        "Train/validation/test are used for clean metrics; seen_dev reported separately.",
    ]
    (run_dir / "leakage_check_before_training.md").write_text("\n".join(leakage_lines) + "\n")
    (run_dir / "feature_columns_used.txt").write_text("\n".join(used_cols) + "\n")
    (run_dir / "feature_columns_rejected.txt").write_text("\n".join(sorted(set(rejected_cols))) + "\n")

    # availability
    availability = {
        "xgboost": has_pkg("xgboost"),
        "lightgbm": has_pkg("lightgbm"),
        "catboost": has_pkg("catboost"),
        "shap": has_pkg("shap"),
    }
    models, availability_rows = build_models(availability)
    availability_df = pd.DataFrame(availability_rows)
    availability_df.to_csv(run_dir / "model_availability_report.csv", index=False)
    (run_dir / "model_availability_report.md").write_text(md_table(availability_df, "Model Availability Report"))

    # split masks
    split_masks = {
        "train": candidate_df["split"] == "train",
        "validation": candidate_df["split"] == "validation",
        "test": candidate_df["split"] == "test",
        "seen_dev": candidate_df["split"] == "seen_dev",
    }

    # pre-transform data based on train split
    train_idx = candidate_df.index[split_masks["train"]]
    if len(train_idx) == 0:
        raise RuntimeError("No train split rows found.")

    X_train_df = X_df.loc[train_idx]
    X_by_split_df = {
        "train": X_df.loc[split_masks["train"]],
        "validation": X_df.loc[split_masks["validation"]],
        "test": X_df.loc[split_masks["test"]],
        "seen_dev": X_df.loc[split_masks["seen_dev"]],
    }

    X_mats, transformed_feature_names, transform_meta = fit_transformer(X_train_df, X_by_split_df)

    y_by_split = {
        k: candidate_df.loc[split_masks[k], "candidate_correct"].astype(int).to_numpy()
        for k in split_masks
    }

    # Train/evaluate all models
    overall_rows = []
    by_scenario_rows = []
    split_rows = []
    selected_by_model_split: dict[tuple[str, str], pd.DataFrame] = {}
    probs_by_model_split: dict[tuple[str, str], np.ndarray] = {}
    fit_models: dict[str, Any] = {}

    for mp in models:
        y_train = y_by_split["train"]
        if len(np.unique(y_train)) < 2:
            raise RuntimeError("Train target has only one class; cannot train classifier.")

        est = mp.estimator
        est.fit(X_mats["train"], y_train)
        fit_models[mp.name] = est

        for split_name in ["train", "validation", "test", "seen_dev"]:
            Xs = X_mats[split_name]
            ys = y_by_split[split_name]
            df_split = candidate_df.loc[split_masks[split_name]].copy()
            if len(df_split) == 0:
                continue

            if hasattr(est, "predict_proba"):
                probs = est.predict_proba(Xs)[:, 1]
            elif hasattr(est, "decision_function"):
                score = est.decision_function(Xs)
                probs = 1.0 / (1.0 + np.exp(-score))
            else:
                probs = est.predict(Xs).astype(float)

            probs = np.clip(probs.astype(float), 1e-6, 1 - 1e-6)
            probs_by_model_split[(mp.name, split_name)] = probs

            overall, by_scenario, selected = evaluate_split(mp.name, split_name, df_split, probs)
            overall_rows.append(overall)
            by_scenario_rows.append(by_scenario)
            selected_by_model_split[(mp.name, split_name)] = selected

    overall_df = pd.DataFrame(overall_rows)
    by_scenario_df = pd.concat(by_scenario_rows, ignore_index=True) if by_scenario_rows else pd.DataFrame()

    # choose best uncalibrated by validation macro then worst then pool acc
    val = overall_df[overall_df["split"] == "validation"].copy()
    val = val.sort_values(["macro_scenario_accuracy", "worst_scenario_accuracy", "pool_selected_accuracy"], ascending=[False, False, False])
    best_model = val.iloc[0]["model"]

    # Calibration (Platt on validation)
    calib_rows = []
    y_val = y_by_split["validation"]
    p_val = probs_by_model_split[(best_model, "validation")]
    do_cal = len(np.unique(y_val)) > 1

    for sp in ["test", "seen_dev"]:
        if (best_model, sp) not in probs_by_model_split:
            continue
        p_raw = probs_by_model_split[(best_model, sp)]
        y_true = y_by_split[sp]
        df_sp = candidate_df.loc[split_masks[sp]].copy()

        raw_sel = select_by_pool(df_sp, p_raw)
        raw_acc = float(raw_sel["selected_correct"].mean()) if len(raw_sel) else float("nan")

        if do_cal and len(y_val) > 0:
            p_cal = fit_platt(y_val, p_val, p_raw)
            cal_sel = select_by_pool(df_sp, p_cal)
            cal_acc = float(cal_sel["selected_correct"].mean()) if len(cal_sel) else float("nan")
        else:
            p_cal = p_raw.copy()
            cal_acc = raw_acc

        calib_rows.append(
            {
                "model": best_model,
                "split": sp,
                "uncalibrated_brier": float(np.mean((p_raw - y_true) ** 2)) if len(y_true) else np.nan,
                "calibrated_brier": float(np.mean((p_cal - y_true) ** 2)) if len(y_true) else np.nan,
                "uncalibrated_ece": ece_score(y_true, p_raw),
                "calibrated_ece": ece_score(y_true, p_cal),
                "uncalibrated_pool_accuracy": raw_acc,
                "calibrated_pool_accuracy": cal_acc,
            }
        )
    calib_df = pd.DataFrame(calib_rows)

    # Split summary for best model
    best_overall = overall_df[overall_df["model"] == best_model].copy()
    split_results = best_overall[[
        "model", "split", "n_candidate_rows", "n_pools", "pool_selected_accuracy", "macro_scenario_accuracy",
        "worst_scenario_accuracy", "candidate_auc", "candidate_log_loss", "candidate_brier"
    ]].copy()

    # Baseline comparison for clean test and seen_dev
    comparison_rows = []
    case_comparison_rows = []
    for sp in ["test", "seen_dev"]:
        selected = selected_by_model_split.get((best_model, sp))
        if selected is None:
            continue
        by_scen, per_pool = pool_baseline_comparison(selected, baseline_df, sp)
        comparison_rows.append(by_scen)
        case_comparison_rows.append(per_pool)

    baseline_comp_df = pd.concat(comparison_rows, ignore_index=True) if comparison_rows else pd.DataFrame()
    case_comp_df = pd.concat(case_comparison_rows, ignore_index=True) if case_comparison_rows else pd.DataFrame()

    # Per-scenario model results (learned only, all splits)
    model_results_by_scenario = by_scenario_df.merge(
        baseline_summary_df.rename(columns={"n_pools": "baseline_n_pools"}),
        on=["scenario_id", "provider", "dataset"],
        how="left",
        suffixes=("", "_baseline"),
    )

    # seen-dev diagnostic table
    seen_dev_diag = model_results_by_scenario[(model_results_by_scenario["model"] == best_model) & (model_results_by_scenario["split"] == "seen_dev")].copy()
    seen_dev_diag = seen_dev_diag[["model", "split", "scenario_id", "provider", "dataset", "n_pools", "learned_accuracy", "selector_frontier_rate", "selector_external_rate"]]

    # leave-one diagnostics using best model type
    def train_best_factory(X_train_df: pd.DataFrame, y_train: pd.Series):
        mats, feat_names, _meta = fit_transformer(X_train_df, {"train": X_train_df})
        Xmat = mats["train"]
        # recreate estimator class with same type
        name_to_pack = {m.name: m for m in models}
        mp = name_to_pack[best_model]
        est = mp.estimator.__class__(**mp.estimator.get_params())
        est.fit(Xmat, y_train.to_numpy())

        def tx(X_any: pd.DataFrame):
            mats2, _fn, _m = fit_transformer(X_train_df, {"train": X_train_df, "x": X_any})
            return mats2["x"]

        return est, tx, feat_names

    loso_df = leave_one_group_eval(
        "leave_one_scenario_out_results",
        candidate_df,
        baseline_df,
        X_df,
        "scenario_id",
        train_best_factory,
        run_dir,
    )
    lopo_df = leave_one_group_eval(
        "leave_one_provider_out_results",
        candidate_df,
        baseline_df,
        X_df,
        "provider",
        train_best_factory,
        run_dir,
    )
    lodo_df = leave_one_group_eval(
        "leave_one_dataset_out_results",
        candidate_df,
        baseline_df,
        X_df,
        "dataset",
        train_best_factory,
        run_dir,
    )

    # Case-level diagnostics for best model on test+seen_dev
    selected_test = selected_by_model_split.get((best_model, "test"), pd.DataFrame())
    selected_seen = selected_by_model_split.get((best_model, "seen_dev"), pd.DataFrame())
    selector_cases = pd.concat([selected_test.assign(split="test"), selected_seen.assign(split="seen_dev")], ignore_index=True)
    if len(selector_cases):
        selector_cases = selector_cases.merge(
            baseline_df[["pool_id", "select_frontier_correct", "select_l1_correct", "select_s1_correct", "select_tale_correct", "pooled4_correct", "agreement_only_correct", "oracle_correct"]],
            on="pool_id",
            how="left",
        )

    if len(selector_cases):
        baseline_cols = ["select_frontier_correct", "select_l1_correct", "select_s1_correct", "select_tale_correct", "pooled4_correct", "agreement_only_correct"]
        selector_cases["best_baseline_correct"] = selector_cases[baseline_cols].max(axis=1)
        selector_cases["best_baseline_name"] = selector_cases[baseline_cols].idxmax(axis=1)
        selector_cases["selector_only_correct"] = ((selector_cases["selected_correct"] == 1) & (selector_cases["best_baseline_correct"] == 0)).astype(int)
        selector_cases["baseline_only_correct"] = ((selector_cases["selected_correct"] == 0) & (selector_cases["best_baseline_correct"] == 1)).astype(int)
        selector_cases["both_correct"] = ((selector_cases["selected_correct"] == 1) & (selector_cases["best_baseline_correct"] == 1)).astype(int)
        selector_cases["both_wrong"] = ((selector_cases["selected_correct"] == 0) & (selector_cases["best_baseline_correct"] == 0)).astype(int)

    false_overrides = selector_cases[(selector_cases["best_baseline_correct"] == 1) & (selector_cases["selected_correct"] == 0)].copy() if len(selector_cases) else pd.DataFrame()
    oracle_missed = selector_cases[(selector_cases["oracle_correct"] == 1) & (selector_cases["selected_correct"] == 0)].copy() if len(selector_cases) else pd.DataFrame()
    all_wrong_high_conf = selector_cases[(selector_cases["oracle_correct"] == 0) & (selector_cases["pred_prob"] >= 0.9)].copy() if len(selector_cases) else pd.DataFrame()

    # Failure diagnostics per scenario
    scen_diag = []
    if len(selector_cases):
        for (sp, scen, prov, ds), g in selector_cases.groupby(["split", "scenario_id", "provider", "dataset"]):
            chosen = g["method"].value_counts().to_dict()
            scen_diag.append(
                {
                    "split": sp,
                    "scenario_id": scen,
                    "provider": prov,
                    "dataset": ds,
                    "pools": int(len(g)),
                    "selector_correct": int(g["selected_correct"].sum()),
                    "best_baseline_correct": int(g["best_baseline_correct"].sum()),
                    "both_correct": int(g["both_correct"].sum()),
                    "selector_only_correct": int(g["selector_only_correct"].sum()),
                    "baseline_only_correct": int(g["baseline_only_correct"].sum()),
                    "both_wrong": int(g["both_wrong"].sum()),
                    "oracle_available_but_selector_missed": int(((g["oracle_correct"] == 1) & (g["selected_correct"] == 0)).sum()),
                    "all_sources_wrong": int((g["oracle_correct"] == 0).sum()),
                    "frontier_selection_rate": float((g["method"] == "direct_reserve_semantic_frontier_v2").mean()),
                    "external_selection_rate": float((g["method"] != "direct_reserve_semantic_frontier_v2").mean()),
                    "frontier_correct_selected_count": int(((g["method"] == "direct_reserve_semantic_frontier_v2") & (g["selected_correct"] == 1)).sum()),
                    "l1_correct_selected_count": int(((g["method"] == "external_l1_max") & (g["selected_correct"] == 1)).sum()),
                    "s1_correct_selected_count": int(((g["method"] == "external_s1_budget_forcing") & (g["selected_correct"] == 1)).sum()),
                    "tale_correct_selected_count": int(((g["method"] == "external_tale_prompt_budgeting") & (g["selected_correct"] == 1)).sum()),
                    "method_choice_counts_json": json.dumps(chosen, sort_keys=True),
                }
            )
    scen_diag_df = pd.DataFrame(scen_diag)

    # Frontier contribution analysis
    frontier_rows = []
    if len(selector_cases):
        test_cases = selector_cases[selector_cases["split"] == "test"].copy()
        # Need per-pool probabilities from best model on test for simulation without frontier
        cand_test = candidate_df.loc[split_masks["test"]].copy()
        p_test = probs_by_model_split.get((best_model, "test"))
        cand_test["pred_prob"] = p_test if p_test is not None else np.nan

        for (scen, prov, ds), g in test_cases.groupby(["scenario_id", "provider", "dataset"]):
            pool_ids = set(g["pool_id"].tolist())
            gt = cand_test[cand_test["pool_id"].isin(pool_ids)].copy()
            # simulate selector without frontier candidate
            gt_no_frontier = gt[gt["method"] != "direct_reserve_semantic_frontier_v2"].copy()
            if len(gt_no_frontier):
                sim_sel = select_by_pool(gt_no_frontier, gt_no_frontier["pred_prob"].to_numpy())
                no_frontier_acc = float(sim_sel["selected_correct"].mean()) if len(sim_sel) else np.nan
            else:
                no_frontier_acc = np.nan

            unique_frontier_correct = gt.groupby("pool_id").apply(
                lambda x: int(
                    ((x["method"] == "direct_reserve_semantic_frontier_v2") & (x["candidate_correct"] == 1)).any()
                    and (x.loc[x["method"] != "direct_reserve_semantic_frontier_v2", "candidate_correct"].sum() == 0)
                )
            ).sum()

            with_frontier_acc = float(g["selected_correct"].mean())
            frontier_rows.append(
                {
                    "scenario_id": scen,
                    "provider": prov,
                    "dataset": ds,
                    "frontier_raw_accuracy": float(g["select_frontier_correct"].mean()) if "select_frontier_correct" in g else np.nan,
                    "selector_chooses_frontier_rate": float((g["method"] == "direct_reserve_semantic_frontier_v2").mean()),
                    "selector_correct_via_frontier_count": int(((g["method"] == "direct_reserve_semantic_frontier_v2") & (g["selected_correct"] == 1)).sum()),
                    "frontier_unique_correct_count": int(unique_frontier_correct),
                    "selector_accuracy_with_frontier": with_frontier_acc,
                    "selector_accuracy_without_frontier_simulated": float(no_frontier_acc) if pd.notna(no_frontier_acc) else np.nan,
                    "accuracy_drop_when_frontier_removed": float(with_frontier_acc - no_frontier_acc) if pd.notna(no_frontier_acc) else np.nan,
                }
            )
    frontier_df = pd.DataFrame(frontier_rows)

    # feature importance
    fi_rows = []
    best_est = fit_models[best_model]
    if hasattr(best_est, "feature_importances_"):
        imp = np.asarray(best_est.feature_importances_)
        for f, v in zip(transformed_feature_names, imp):
            fi_rows.append({"model": best_model, "feature": f, "importance": float(v), "source": "feature_importances_"})
    # logistic coeffs always included for baseline interpretation
    lr_est = fit_models.get("logistic_regression")
    if lr_est is not None and hasattr(lr_est, "coef_"):
        coef = np.asarray(lr_est.coef_).reshape(-1)
        for f, v in zip(transformed_feature_names, coef):
            fi_rows.append({"model": "logistic_regression", "feature": f, "importance": float(v), "source": "coefficient"})
    fi_df = pd.DataFrame(fi_rows)

    # Write requested outputs
    overall_df.to_csv(run_dir / "model_results_overall.csv", index=False)
    model_results_by_scenario.to_csv(run_dir / "model_results_by_scenario.csv", index=False)
    (run_dir / "model_results_by_scenario.md").write_text(md_table(model_results_by_scenario, "Model Results By Scenario"))

    baseline_comp_df.to_csv(run_dir / "baseline_comparison_by_scenario.csv", index=False)
    (run_dir / "baseline_comparison_by_scenario.md").write_text(md_table(baseline_comp_df, "Baseline Comparison By Scenario"))

    split_results.to_csv(run_dir / "split_results.csv", index=False)
    seen_dev_diag.to_csv(run_dir / "seen_dev_diagnostic_results.csv", index=False)
    calib_df.to_csv(run_dir / "calibrated_vs_uncalibrated_results.csv", index=False)

    # leave-one files already written in helper; rewrite with requested names exactly if needed
    loso_df.to_csv(run_dir / "leave_one_scenario_out_results.csv", index=False)
    lopo_df.to_csv(run_dir / "leave_one_provider_out_results.csv", index=False)
    lodo_df.to_csv(run_dir / "leave_one_dataset_out_results.csv", index=False)

    fi_df.to_csv(run_dir / "feature_importance.csv", index=False)

    selector_cases.to_csv(run_dir / "selector_case_predictions.csv", index=False)
    selector_cases.to_csv(run_dir / "selector_case_changes_vs_best_baseline.csv", index=False)
    false_overrides.to_csv(run_dir / "false_overrides.csv", index=False)
    oracle_missed.to_csv(run_dir / "oracle_available_but_selector_wrong.csv", index=False)
    all_wrong_high_conf.to_csv(run_dir / "all_sources_wrong_high_confidence.csv", index=False)

    frontier_df.to_csv(run_dir / "frontier_contribution_analysis.csv", index=False)
    (run_dir / "frontier_contribution_analysis.md").write_text(md_table(frontier_df, "Frontier Contribution Analysis"))

    scen_diag_md = md_table(scen_diag_df, "Per Scenario Failure Diagnostics")
    (run_dir / "per_scenario_failure_diagnostics.md").write_text(scen_diag_md)

    # Promotion decision
    test_comp = baseline_comp_df[baseline_comp_df["split"] == "test"].copy()
    all_tie_or_win = bool((test_comp["delta_vs_best_baseline"] >= 0).all()) if len(test_comp) else False
    best_macro_model = val.iloc[0]["model"] if len(val) else ""
    worst_score = val.iloc[0]["worst_scenario_accuracy"] if len(val) else np.nan
    losing = test_comp[test_comp["delta_vs_best_baseline"] < 0][["scenario_id", "delta_vs_best_baseline"]] if len(test_comp) else pd.DataFrame()

    prom_lines = [
        "# Promotion Decision",
        "",
        f"Best model by validation macro-average: `{best_macro_model}`",
        f"Best model validation worst-scenario accuracy: {worst_score:.6f}" if pd.notna(worst_score) else "Best model validation worst-scenario accuracy: n/a",
        "",
        f"Is any learned model best or tied-best in all clean test scenarios? {'Yes' if all_tie_or_win else 'No'}",
        "",
        "Scenarios still losing on clean test:",
    ]
    if losing.empty:
        prom_lines.append("- none")
    else:
        for _, r in losing.iterrows():
            prom_lines.append(f"- {r['scenario_id']}: delta={r['delta_vs_best_baseline']:.6f}")

    prom_lines.extend(
        [
            "",
            "Loss diagnosis heuristic:",
            "- If oracle ceiling is low and all baselines are low: likely low oracle ceiling / missing-provider issue.",
            "- If oracle ceiling high but learned < baseline: likely feature learning/ranking issue.",
            "",
            "Recommended next step option:",
            "- C. add fold-safe reliability features (while preserving leakage guardrails).",
        ]
    )
    (run_dir / "promotion_decision.md").write_text("\n".join(prom_lines) + "\n")

    # Human summary report
    test_rows = baseline_comp_df[baseline_comp_df["split"] == "test"].copy()
    seen_rows = baseline_comp_df[baseline_comp_df["split"] == "seen_dev"].copy()

    report_lines = [
        "# JOB_D_TRAINING_REPORT_20260525",
        "",
        f"Input directory: `{in_dir}`",
        f"Output directory: `{run_dir}`",
        "",
        "## Best model",
        f"- {best_model}",
        "",
        "## Clean test summary",
    ]
    if test_rows.empty:
        report_lines.append("- no test rows")
    else:
        for _, r in test_rows.iterrows():
            report_lines.append(
                f"- {r['scenario_id']}: baseline={r['best_baseline_accuracy']:.4f}, learned={r['learned_accuracy']:.4f}, delta={r['delta_vs_best_baseline']:+.4f}, oracle={r['oracle_ceiling']:.4f}, result={r['result']}"
            )

    report_lines.extend(["", "## Seen-dev diagnostics"])
    if seen_rows.empty:
        report_lines.append("- no seen_dev rows")
    else:
        for _, r in seen_rows.iterrows():
            report_lines.append(
                f"- {r['scenario_id']}: baseline={r['best_baseline_accuracy']:.4f}, learned={r['learned_accuracy']:.4f}, delta={r['delta_vs_best_baseline']:+.4f}, oracle={r['oracle_ceiling']:.4f}, result={r['result']}"
            )

    report_lines.extend(
        [
            "",
            "## Leakage status",
            "- PASS (allowlist + forbidden exclusion enforced before training)",
        ]
    )
    (run_dir / "JOB_D_TRAINING_REPORT_20260525.md").write_text("\n".join(report_lines) + "\n")

    # Manifest
    training_manifest = {
        "generated_at": now_utc(),
        "input_dir": str(in_dir),
        "output_dir": str(run_dir),
        "data": {
            "candidate_rows": int(len(candidate_df)),
            "pool_rows": int(pool_df["pool_id"].nunique()),
            "split_counts": candidate_df["split"].value_counts().to_dict(),
        },
        "feature_meta": feat_meta,
        "transform_meta": transform_meta,
        "model_availability": availability,
        "models_trained": [m.name for m in models],
        "best_model": best_model,
    }
    (run_dir / "training_manifest.json").write_text(json.dumps(training_manifest, indent=2) + "\n")
    (run_dir / "job_d_training_manifest.json").write_text(json.dumps(training_manifest, indent=2) + "\n")

    print(json.dumps({
        "output_dir": str(run_dir),
        "best_model": best_model,
        "test_rows": len(test_rows),
        "seen_dev_rows": len(seen_rows),
    }, indent=2))


if __name__ == "__main__":
    main()
