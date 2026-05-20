#!/usr/bin/env python3
"""Offline failure-pattern mining over normalized feature tables (no API calls)."""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.metrics import accuracy_score, balanced_accuracy_score
from sklearn.model_selection import StratifiedKFold, cross_validate
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sklearn.tree import DecisionTreeClassifier, export_text

REPO_ROOT = Path(__file__).resolve().parents[1]
TARGET_COLUMNS = (
    "oracle_recoverable",
    "regression_risk",
    "both_wrong",
    "both_correct",
    "disagreement",
)
SUMMARY_TARGETS = (
    "oracle_recoverable",
    "regression_risk",
    "both_wrong",
    "disagreement",
)
REPRESENTATIVE_TARGETS = (
    "oracle_recoverable",
    "regression_risk",
    "both_wrong",
)

TRUE_TOKENS = {"1", "true", "t", "yes", "y"}
FALSE_TOKENS = {"0", "false", "f", "no", "n", "", "nan", "none", "null"}

SAFE_BASE_FEATURES = {
    "artifact_label",
    "source_artifact_path",
    "grouping_key",
    "example_id",
    "problem_id",
    "dataset",
    "provider",
    "model",
    "baseline_method",
    "frontier_method",
    "budget",
    "seed",
    "contamination_status",
    "has_full_log",
    "has_discovery_tree",
    "has_frontier_log",
    "answers_equal",
    "answer_length_baseline",
    "answer_length_frontier",
    "trace_length_baseline",
    "trace_length_frontier",
    "has_trace_baseline",
    "has_trace_frontier",
    "parse_success_baseline",
    "parse_success_frontier",
    "parser_error_status_baseline",
    "parser_error_status_frontier",
    "raw_status_baseline",
    "raw_status_frontier",
    "raw_error_baseline",
    "raw_error_frontier",
    "stop_reason_baseline",
    "stop_reason_frontier",
}

SAFE_PREFIXES = (
    "candidate_count_",
    "unique_answer_count_",
    "duplicate_answer_ratio_",
    "answer_family_count",
    "tree_",
    "expanded_node_count",
    "final_node_count",
    "branch_count",
    "max_depth",
    "duplicate_family_count",
    "prune_count",
    "incumbent_replacement_count",
    "total_tokens_",
    "prompt_tokens_",
    "completion_tokens_",
    "latency_",
    "estimated_cost_",
    "call_count_",
    "cumulative_spend",
    "score_margin_",
    "top2_gap_",
    "score_spread_",
    "selected_rank_",
)

BLOCKED_PREFIXES = (
    "oracle_",
    "regression_",
    "both_",
    "disagreement",
    "baseline_wrong_",
    "baseline_correct_",
    "frontier_correct",
    "baseline_correct",
    "gold_",
    "exact_match",
    "correct_candidate_present",
    "correct_family_present",
    "inference_available_feature_set",
    "offline_only_label_note",
    "needs_manual_review",
)

BLOCKED_EXACT = {
    "baseline_answer",
    "frontier_answer",
    "baseline_canonical_answer",
    "frontier_canonical_answer",
    "question",
    "baseline_trace_snippet",
    "frontier_trace_snippet",
}


def _to_bool(value: Any) -> int:
    text = str(value).strip().lower()
    if text in TRUE_TOKENS:
        return 1
    if text in FALSE_TOKENS:
        return 0
    try:
        return 1 if float(text) > 0 else 0
    except Exception:
        return 1 if bool(text) else 0


def _load_feature_table(path: Path) -> pd.DataFrame:
    if not path.is_file():
        raise FileNotFoundError(f"Missing feature table CSV: {path}")
    return pd.read_csv(path)


def _validate_targets(df: pd.DataFrame) -> None:
    missing = [t for t in TARGET_COLUMNS if t not in df.columns]
    if missing:
        raise ValueError(f"Missing required target columns: {missing}")


def _normalize_binary_targets(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for target in TARGET_COLUMNS:
        out[target] = out[target].map(_to_bool)
    return out


def _apply_filters(df: pd.DataFrame, artifact_filter: str, exclude_contaminated: bool) -> pd.DataFrame:
    out = df.copy()
    if artifact_filter:
        if "artifact_label" in out.columns:
            mask = out["artifact_label"].astype(str).str.contains(artifact_filter, case=False, na=False)
            out = out[mask]
        elif "source_artifact_path" in out.columns:
            mask = out["source_artifact_path"].astype(str).str.contains(artifact_filter, case=False, na=False)
            out = out[mask]
    if exclude_contaminated and "contamination_status" in out.columns:
        bad = {"contaminated", "yes", "true", "1"}
        mask = ~out["contamination_status"].astype(str).str.strip().str.lower().isin(bad)
        out = out[mask]
    return out.reset_index(drop=True)


def _is_blocked_feature(column: str) -> bool:
    if column in BLOCKED_EXACT:
        return True
    for prefix in BLOCKED_PREFIXES:
        if column.startswith(prefix):
            return True
    return False


def _feature_candidates(df: pd.DataFrame, target: str) -> list[str]:
    cols: list[str] = []
    for col in df.columns:
        if col == target or col in TARGET_COLUMNS:
            continue
        if _is_blocked_feature(col):
            continue
        if col in SAFE_BASE_FEATURES or any(col.startswith(p) for p in SAFE_PREFIXES):
            cols.append(col)
    return cols


def _infer_types(df: pd.DataFrame, features: list[str]) -> tuple[list[str], list[str]]:
    numeric: list[str] = []
    categorical: list[str] = []
    for col in features:
        series = df[col]
        if pd.api.types.is_bool_dtype(series) or pd.api.types.is_numeric_dtype(series):
            numeric.append(col)
            continue
        parsed = pd.to_numeric(series, errors="coerce")
        non_na = series.notna().sum()
        if non_na == 0:
            categorical.append(col)
            continue
        convertible_ratio = float(parsed.notna().sum()) / float(non_na)
        if convertible_ratio >= 0.95:
            numeric.append(col)
        else:
            categorical.append(col)
    return numeric, categorical


def _build_model_pipeline(numeric_features: list[str], categorical_features: list[str], max_depth: int, seed: int) -> Pipeline:
    num_pipe = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
        ]
    )
    cat_pipe = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore")),
        ]
    )
    preprocessor = ColumnTransformer(
        transformers=[
            ("num", num_pipe, numeric_features),
            ("cat", cat_pipe, categorical_features),
        ],
        sparse_threshold=0.0,
    )
    model = DecisionTreeClassifier(max_depth=max_depth, random_state=seed, class_weight="balanced")
    return Pipeline(steps=[("pre", preprocessor), ("clf", model)])


def _extract_rules_and_importance(model: Pipeline, feature_names: list[str]) -> tuple[str, list[dict[str, Any]]]:
    pre = model.named_steps["pre"]
    clf: DecisionTreeClassifier = model.named_steps["clf"]
    transformed_names = list(pre.get_feature_names_out(feature_names))
    rules = export_text(clf, feature_names=transformed_names)
    importances = clf.feature_importances_
    rows = []
    for name, score in zip(transformed_names, importances):
        if score <= 0:
            continue
        rows.append({"transformed_feature": name, "importance": float(score)})
    rows.sort(key=lambda r: r["importance"], reverse=True)
    return rules, rows


def _safe_cross_validate(model: Pipeline, X: pd.DataFrame, y: pd.Series, seed: int) -> dict[str, Any]:
    positives = int(y.sum())
    negatives = int((1 - y).sum())
    min_class = min(positives, negatives)
    if min_class < 2 or len(y) < 10:
        return {
            "cv_folds": 0,
            "accuracy_mean": None,
            "accuracy_std": None,
            "balanced_accuracy_mean": None,
            "balanced_accuracy_std": None,
            "note": "Insufficient class support for stratified CV.",
        }
    folds = min(5, min_class)
    cv = StratifiedKFold(n_splits=folds, shuffle=True, random_state=seed)
    scores = cross_validate(model, X, y, cv=cv, scoring=("accuracy", "balanced_accuracy"), n_jobs=None)
    return {
        "cv_folds": folds,
        "accuracy_mean": float(np.mean(scores["test_accuracy"])),
        "accuracy_std": float(np.std(scores["test_accuracy"])),
        "balanced_accuracy_mean": float(np.mean(scores["test_balanced_accuracy"])),
        "balanced_accuracy_std": float(np.std(scores["test_balanced_accuracy"])),
        "note": "",
    }


def _fit_tree(df: pd.DataFrame, target: str, feature_cols: list[str], max_depth: int, seed: int) -> tuple[dict[str, Any], str, list[dict[str, Any]], pd.Series]:
    numeric, categorical = _infer_types(df, feature_cols)
    X = df[feature_cols].copy()
    for col in numeric:
        X[col] = pd.to_numeric(X[col], errors="coerce")
    for col in categorical:
        X[col] = X[col].astype(str).replace({"nan": "missing"}).fillna("missing")

    y = df[target].astype(int)
    pipeline = _build_model_pipeline(numeric, categorical, max_depth=max_depth, seed=seed)
    cv_metrics = _safe_cross_validate(pipeline, X, y, seed)
    pipeline.fit(X, y)
    pred = pd.Series(pipeline.predict(X), index=df.index)
    train_acc = float(accuracy_score(y, pred))
    train_bal_acc = float(balanced_accuracy_score(y, pred))
    rules, feature_importance = _extract_rules_and_importance(pipeline, feature_cols)

    metrics = {
        "target": target,
        "n_rows": int(len(df)),
        "positive_count": int(y.sum()),
        "negative_count": int((1 - y).sum()),
        "positive_rate": float(y.mean()) if len(y) else 0.0,
        "numeric_feature_count": len(numeric),
        "categorical_feature_count": len(categorical),
        "total_feature_count": len(feature_cols),
        "train_accuracy": train_acc,
        "train_balanced_accuracy": train_bal_acc,
        "cv": cv_metrics,
    }
    return metrics, rules, feature_importance, pred


def _build_binned_frame(df: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    binned = pd.DataFrame(index=df.index)
    for col in features:
        series = df[col]
        if pd.api.types.is_numeric_dtype(series):
            num = pd.to_numeric(series, errors="coerce")
            unique_non_na = num.dropna().nunique()
            if unique_non_na >= 3:
                try:
                    bins = pd.qcut(num, q=3, labels=["low", "mid", "high"], duplicates="drop")
                    binned[col] = bins.astype(str).replace("nan", "missing")
                except Exception:
                    binned[col] = pd.cut(num, bins=3, labels=["low", "mid", "high"], include_lowest=True).astype(str).replace("nan", "missing")
            else:
                binned[col] = np.where(num.isna(), "missing", "value")
        else:
            text = series.astype(str).replace({"nan": "missing"}).fillna("missing")
            nunique = text.nunique(dropna=False)
            if nunique > 12:
                vc = text.value_counts(dropna=False)
                keep = set(vc.head(10).index.tolist())
                text = text.map(lambda x: x if x in keep else "other")
            binned[col] = text
    return binned


def _one_feature_rules(
    discrete_df: pd.DataFrame,
    targets_df: pd.DataFrame,
    min_support: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, set[int]]]:
    n = len(discrete_df)
    rule_rows: list[dict[str, Any]] = []
    binned_rows: list[dict[str, Any]] = []
    token_to_indices: dict[str, set[int]] = {}

    base_rates = {target: float(targets_df[target].mean()) for target in SUMMARY_TARGETS if target in targets_df.columns}

    for col in discrete_df.columns:
        vals = discrete_df[col].astype(str).fillna("missing")
        counts = vals.value_counts(dropna=False)
        for value, count in counts.items():
            support = float(count) / float(n) if n else 0.0
            if support < min_support:
                continue
            mask = vals == value
            idx = set(discrete_df.index[mask].tolist())
            token = f"{col}={value}"
            token_to_indices[token] = idx
            row_common = {
                "feature": col,
                "value": value,
                "count": int(count),
                "support": support,
            }
            for target in SUMMARY_TARGETS:
                if target not in targets_df.columns:
                    continue
                rate = float(targets_df.loc[mask, target].mean()) if int(count) else 0.0
                lift = (rate / base_rates[target]) if base_rates[target] > 0 else math.nan
                binned_rows.append(
                    {
                        **row_common,
                        "target": target,
                        "target_rate": rate,
                        "base_rate": base_rates[target],
                        "lift": lift,
                    }
                )
                rule_rows.append(
                    {
                        "rule_type": "single",
                        "rule": token,
                        "target": target,
                        "count": int(count),
                        "support": support,
                        "target_rate": rate,
                        "base_rate": base_rates[target],
                        "lift": lift,
                    }
                )
    return rule_rows, binned_rows, token_to_indices


def _two_feature_rules(
    token_to_indices: dict[str, set[int]],
    n_rows: int,
    targets_df: pd.DataFrame,
    min_support: float,
    max_pairs: int = 8000,
) -> list[dict[str, Any]]:
    pair_rows: list[dict[str, Any]] = []
    base_rates = {target: float(targets_df[target].mean()) for target in SUMMARY_TARGETS if target in targets_df.columns}

    tokens = sorted(token_to_indices.keys())
    used = 0
    for a_i in range(len(tokens)):
        if used >= max_pairs:
            break
        t1 = tokens[a_i]
        f1 = t1.split("=", 1)[0]
        idx1 = token_to_indices[t1]
        for b_i in range(a_i + 1, len(tokens)):
            if used >= max_pairs:
                break
            t2 = tokens[b_i]
            f2 = t2.split("=", 1)[0]
            if f1 == f2:
                continue
            idx2 = token_to_indices[t2]
            inter = idx1.intersection(idx2)
            count = len(inter)
            support = float(count) / float(n_rows) if n_rows else 0.0
            if support < min_support:
                continue
            used += 1
            if count == 0:
                continue
            ordered_idx = sorted(inter)
            for target in SUMMARY_TARGETS:
                if target not in targets_df.columns:
                    continue
                y = targets_df.loc[ordered_idx, target]
                rate = float(y.mean()) if count else 0.0
                lift = (rate / base_rates[target]) if base_rates[target] > 0 else math.nan
                pair_rows.append(
                    {
                        "rule_type": "pair",
                        "rule": f"{t1} & {t2}",
                        "target": target,
                        "count": count,
                        "support": support,
                        "target_rate": rate,
                        "base_rate": base_rates[target],
                        "lift": lift,
                    }
                )
    return pair_rows


def _mine_association_rules(discrete_df: pd.DataFrame, targets_df: pd.DataFrame, min_support: float) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, set[int]], str]:
    single_rows, binned_rows, token_to_indices = _one_feature_rules(discrete_df, targets_df, min_support=min_support)

    engine = "fallback_manual"
    mlxtend_rows: list[dict[str, Any]] = []
    try:
        from mlxtend.frequent_patterns import apriori, association_rules  # type: ignore

        transactions = []
        for _, row in discrete_df.iterrows():
            tokens = [f"{col}={row[col]}" for col in discrete_df.columns]
            transactions.append(tokens)

        all_tokens = sorted({tok for tx in transactions for tok in tx})
        token_index = {tok: i for i, tok in enumerate(all_tokens)}
        mat = np.zeros((len(transactions), len(all_tokens)), dtype=bool)
        for i, tx in enumerate(transactions):
            for tok in tx:
                mat[i, token_index[tok]] = True
        trans_df = pd.DataFrame(mat, columns=all_tokens)

        fi = apriori(trans_df, min_support=min_support, use_colnames=True)
        if not fi.empty:
            ar = association_rules(fi, metric="lift", min_threshold=1.0)
            for _, row in ar.iterrows():
                antecedent = " & ".join(sorted(row["antecedents"]))
                consequent = " & ".join(sorted(row["consequents"]))
                mlxtend_rows.append(
                    {
                        "rule_type": "mlxtend",
                        "rule": antecedent,
                        "target": consequent,
                        "count": int(round(row["support"] * len(discrete_df))),
                        "support": float(row["support"]),
                        "target_rate": None,
                        "base_rate": None,
                        "lift": float(row["lift"]),
                    }
                )
            engine = "mlxtend_plus_manual"
    except Exception:
        engine = "fallback_manual"

    pair_rows = _two_feature_rules(token_to_indices, n_rows=len(discrete_df), targets_df=targets_df, min_support=min_support)
    all_rows = single_rows + pair_rows + mlxtend_rows
    df_rules = pd.DataFrame(all_rows)
    if not df_rules.empty:
        df_rules = df_rules.sort_values(["target", "lift", "support", "count"], ascending=[True, False, False, False]).reset_index(drop=True)

    df_binned = pd.DataFrame(binned_rows)
    if not df_binned.empty:
        df_binned = df_binned.sort_values(["target", "lift", "support", "count"], ascending=[True, False, False, False]).reset_index(drop=True)
    return df_rules, df_binned, token_to_indices, engine


def _target_summary(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    total = len(df)
    for target in TARGET_COLUMNS:
        if target not in df.columns:
            continue
        count = int(df[target].sum())
        rows.append(
            {
                "target": target,
                "count": count,
                "total": int(total),
                "rate": float(count / total) if total else 0.0,
            }
        )
    return pd.DataFrame(rows)


def _feature_summary(df: pd.DataFrame, features: list[str], importances: list[dict[str, Any]]) -> pd.DataFrame:
    imp_by_base: dict[str, float] = defaultdict(float)
    for row in importances:
        name = str(row.get("transformed_feature", ""))
        score = float(row.get("importance", 0.0))
        if "__" in name:
            base = name.split("__", 1)[1].split("_", 1)[0]
        else:
            base = name
        imp_by_base[base] += score

    rows = []
    for col in features:
        series = df[col]
        missing = int(series.isna().sum())
        rows.append(
            {
                "feature": col,
                "dtype": str(series.dtype),
                "missing_count": missing,
                "missing_rate": float(missing / len(df)) if len(df) else 0.0,
                "n_unique_non_null": int(series.nunique(dropna=True)),
                "importance_proxy": float(imp_by_base.get(col, 0.0)),
            }
        )
    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values(["importance_proxy", "missing_rate"], ascending=[False, True])
    return out


def _target_by_artifact(df: pd.DataFrame) -> pd.DataFrame:
    key = "artifact_label" if "artifact_label" in df.columns else "source_artifact_path"
    if key not in df.columns:
        return pd.DataFrame()
    grouped = df.groupby(key, dropna=False)
    rows = []
    for artifact, grp in grouped:
        row = {"artifact": artifact, "count": int(len(grp))}
        for target in SUMMARY_TARGETS:
            row[f"{target}_rate"] = float(grp[target].mean()) if target in grp.columns else math.nan
            row[f"{target}_count"] = int(grp[target].sum()) if target in grp.columns else 0
        rows.append(row)
    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values("count", ascending=False)
    return out


def _target_by_method(df: pd.DataFrame) -> pd.DataFrame:
    if "baseline_method" not in df.columns and "frontier_method" not in df.columns:
        return pd.DataFrame()
    base = df.get("baseline_method", pd.Series(["missing"] * len(df), index=df.index)).astype(str)
    front = df.get("frontier_method", pd.Series(["missing"] * len(df), index=df.index)).astype(str)
    method_pair = base + "__VS__" + front
    temp = df.copy()
    temp["method_pair"] = method_pair

    rows = []
    for method, grp in temp.groupby("method_pair", dropna=False):
        row = {
            "method_pair": method,
            "baseline_method": str(grp["baseline_method"].iloc[0]) if "baseline_method" in grp.columns else "missing",
            "frontier_method": str(grp["frontier_method"].iloc[0]) if "frontier_method" in grp.columns else "missing",
            "count": int(len(grp)),
        }
        for target in SUMMARY_TARGETS:
            row[f"{target}_rate"] = float(grp[target].mean()) if target in grp.columns else math.nan
            row[f"{target}_count"] = int(grp[target].sum()) if target in grp.columns else 0
        rows.append(row)
    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values("count", ascending=False)
    return out


def _target_by_feature_bins(discrete_df: pd.DataFrame, targets_df: pd.DataFrame, min_support: float) -> pd.DataFrame:
    rows = []
    n = len(discrete_df)
    for col in discrete_df.columns:
        vals = discrete_df[col].astype(str).fillna("missing")
        counts = vals.value_counts(dropna=False)
        for value, count in counts.items():
            support = float(count) / float(n) if n else 0.0
            if support < min_support:
                continue
            mask = vals == value
            row = {
                "feature": col,
                "bin_or_value": value,
                "count": int(count),
                "support": support,
            }
            for target in SUMMARY_TARGETS:
                if target in targets_df.columns:
                    row[f"{target}_rate"] = float(targets_df.loc[mask, target].mean()) if count else 0.0
            rows.append(row)
    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values("support", ascending=False)
    return out


def _find_example_packets(feature_table_csv: Path) -> Path | None:
    candidate = feature_table_csv.parent / "example_case_packets.jsonl"
    return candidate if candidate.is_file() else None


def _load_example_packets(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None:
        return {}
    rows: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except Exception:
                continue
            ex_id = str(payload.get("example_id") or payload.get("case_id") or "").strip()
            if ex_id:
                rows[ex_id] = payload
    return rows


def _rows_matching_rule(discrete_df: pd.DataFrame, rule: str) -> pd.Series:
    parts = [p.strip() for p in rule.split("&")]
    mask = pd.Series([True] * len(discrete_df), index=discrete_df.index)
    for part in parts:
        if "=" not in part:
            return pd.Series([False] * len(discrete_df), index=discrete_df.index)
        feature, value = part.split("=", 1)
        feature = feature.strip()
        value = value.strip()
        if feature not in discrete_df.columns:
            return pd.Series([False] * len(discrete_df), index=discrete_df.index)
        mask = mask & (discrete_df[feature].astype(str) == value)
    return mask


def _representative_cases(
    df: pd.DataFrame,
    discrete_df: pd.DataFrame,
    rule_df: pd.DataFrame,
    packets: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for target in REPRESENTATIVE_TARGETS:
        target_positive = df[df[target] == 1] if target in df.columns else pd.DataFrame()
        if target_positive.empty:
            continue

        target_rules = rule_df[(rule_df.get("target") == target) & (rule_df.get("lift", 0) > 1.0)] if not rule_df.empty else pd.DataFrame()
        if not target_rules.empty:
            target_rules = target_rules.sort_values(["lift", "count"], ascending=[False, False]).head(6)

        selected_ids: list[str] = []
        if not target_rules.empty:
            for _, rr in target_rules.iterrows():
                mask = _rows_matching_rule(discrete_df, str(rr["rule"]))
                candidates = df[mask & (df[target] == 1)]
                for _, row in candidates.head(3).iterrows():
                    ex_id = str(row.get("example_id", "")).strip()
                    if ex_id and ex_id not in selected_ids:
                        selected_ids.append(ex_id)
                    if len(selected_ids) >= 5:
                        break
                if len(selected_ids) >= 5:
                    break

        if len(selected_ids) < 5:
            for _, row in target_positive.head(20).iterrows():
                ex_id = str(row.get("example_id", "")).strip()
                if ex_id and ex_id not in selected_ids:
                    selected_ids.append(ex_id)
                if len(selected_ids) >= 5:
                    break

        for ex_id in selected_ids[:5]:
            source = packets.get(ex_id, {})
            base = df[df["example_id"].astype(str) == ex_id].head(1)
            if base.empty:
                continue
            row0 = base.iloc[0]
            rows.append(
                {
                    "target": target,
                    "example_id": ex_id,
                    "artifact_label": str(row0.get("artifact_label", "")),
                    "baseline_method": str(row0.get("baseline_method", "")),
                    "frontier_method": str(row0.get("frontier_method", "")),
                    "dataset": str(row0.get("dataset", "")),
                    "provider": str(row0.get("provider", "")),
                    "has_full_log": int(_to_bool(row0.get("has_full_log", 0))),
                    "has_discovery_tree": int(_to_bool(row0.get("has_discovery_tree", 0))),
                    "has_frontier_log": int(_to_bool(row0.get("has_frontier_log", 0))),
                    "discovery_tree_pointer": str(row0.get("discovery_tree_pointer", "")),
                    "frontier_log_pointer": str(row0.get("frontier_log_pointer", "")),
                    "question": str(source.get("question") or row0.get("question") or "")[:280],
                    "baseline_answer": str(source.get("baseline_answer") or row0.get("baseline_answer") or "")[:120],
                    "frontier_answer": str(source.get("frontier_answer") or row0.get("frontier_answer") or "")[:120],
                }
            )
    return rows


def _interpretation(
    target: str,
    target_summary: pd.DataFrame,
    feature_summary: pd.DataFrame,
    rule_df: pd.DataFrame,
    target_by_method: pd.DataFrame,
) -> dict[str, Any]:
    top_features = feature_summary.head(8)["feature"].tolist() if not feature_summary.empty else []

    artifact_method_markers = {"artifact_label", "source_artifact_path", "baseline_method", "frontier_method", "grouping_key"}
    top_marker_hits = [f for f in top_features if f in artifact_method_markers]

    parse_signals = []
    if not rule_df.empty:
        parse_rows = rule_df[
            rule_df["rule"].astype(str).str.contains("parse_success|parser_error_status|raw_error|raw_status", case=False, na=False)
            & (rule_df["target"] == target)
            & (rule_df["lift"] > 1.0)
        ].head(5)
        parse_signals = parse_rows["rule"].astype(str).tolist()

    method_dominance = False
    if not target_by_method.empty:
        high_var = target_by_method.get(f"{target}_rate", pd.Series(dtype=float))
        if len(high_var) > 1 and high_var.max() - high_var.min() > 0.2:
            method_dominance = True

    recommended = "B"
    if parse_signals:
        recommended = "A"
    if any("candidate_count" in feat or "unique_answer_count" in feat for feat in top_features):
        recommended = "B"
    if all("method" in feat or "artifact" in feat for feat in top_features[:3]) and top_features:
        recommended = "C"

    recommendation_map = {
        "A": "manual audit of top high-lift case clusters",
        "B": "enrich feature table with more tree/frontier/candidate diversity features",
        "C": "add verifier scoring to high-log artifacts",
        "D": "collect more API cases only after logging schema/pattern targets are stable",
        "E": "implement a new gate feature only if the pattern is strong and inference-available",
    }

    base = target_summary[target_summary["target"] == target]
    base_rate = float(base["rate"].iloc[0]) if not base.empty else 0.0

    return {
        "target": target,
        "base_rate": base_rate,
        "top_features": top_features,
        "top_marker_hits": top_marker_hits,
        "method_or_artifact_dominated": bool(top_marker_hits),
        "method_dominance_gap_over_20pp": method_dominance,
        "parse_signals": parse_signals,
        "missing_for_reliable_diagnosis": [
            "verifier/reranker candidate-level scores",
            "candidate-family structural diversity details per seed",
            "stable per-step canonicalization/parse failure tags",
        ],
        "next_manual_audit": "Audit high-lift clusters with disagreement=1 and parse/canonicalization suspect flags first.",
        "recommended_next_step_code": recommended,
        "recommended_next_step": recommendation_map[recommended],
    }


def _render_report(
    *,
    args: argparse.Namespace,
    n_rows: int,
    missingness_rows: pd.DataFrame,
    target_summary: pd.DataFrame,
    tree_metrics: dict[str, Any],
    feature_summary: pd.DataFrame,
    rule_df: pd.DataFrame,
    interpretation_primary: dict[str, Any],
    interpretation_by_target: list[dict[str, Any]],
    representative_rows: list[dict[str, Any]],
) -> str:
    lines: list[str] = []
    lines.append("# Failure Pattern Mining Report")
    lines.append("")
    lines.append("Exploratory offline analysis only. This report does not establish algorithmic improvement.")
    lines.append("")
    lines.append("## Run Configuration")
    lines.append(f"- feature table: `{args.feature_table_csv}`")
    lines.append(f"- output dir: `{args.output_dir}`")
    lines.append(f"- primary target: `{args.target}`")
    lines.append(f"- min support: `{args.min_support}`")
    lines.append(f"- max tree depth: `{args.max_tree_depth}`")
    lines.append(f"- seed: `{args.seed}`")
    lines.append(f"- rows analyzed: `{n_rows}`")
    lines.append("")

    lines.append("## Target Summary")
    for _, row in target_summary.iterrows():
        lines.append(f"- {row['target']}: {int(row['count'])}/{int(row['total'])} ({row['rate']:.4f})")
    lines.append("")

    lines.append("## Feature Missingness")
    top_missing = missingness_rows.sort_values("missing_rate", ascending=False).head(10)
    for _, row in top_missing.iterrows():
        lines.append(f"- {row['feature']}: missing {int(row['missing_count'])}/{n_rows} ({row['missing_rate']:.4f})")
    lines.append("")

    lines.append("## Decision Tree (Exploratory)")
    lines.append(f"- class balance (`{args.target}` positive rate): {tree_metrics['positive_rate']:.4f}")
    lines.append(f"- train accuracy: {tree_metrics['train_accuracy']:.4f}")
    lines.append(f"- train balanced accuracy: {tree_metrics['train_balanced_accuracy']:.4f}")
    cv = tree_metrics["cv"]
    if cv.get("cv_folds", 0) > 0:
        lines.append(f"- CV accuracy: {cv['accuracy_mean']:.4f} ± {cv['accuracy_std']:.4f}")
        lines.append(f"- CV balanced accuracy: {cv['balanced_accuracy_mean']:.4f} ± {cv['balanced_accuracy_std']:.4f}")
    else:
        lines.append(f"- CV note: {cv.get('note', 'n/a')}")
    lines.append("- Top feature signals (importance proxy):")
    for _, row in feature_summary.head(10).iterrows():
        lines.append(f"  - {row['feature']}: {row['importance_proxy']:.4f}")
    lines.append("")

    lines.append("## Association / Binned Rules")
    if rule_df.empty:
        lines.append("- No rules met minimum support.")
    else:
        top_rules = rule_df[(rule_df["target"] == args.target)].head(10)
        for _, row in top_rules.iterrows():
            lift = row["lift"]
            lift_text = "nan" if pd.isna(lift) else f"{lift:.3f}"
            lines.append(
                f"- [{row['rule_type']}] {row['rule']} | support={row['support']:.3f} count={int(row['count'])} "
                f"target_rate={row['target_rate']:.3f} lift={lift_text}"
            )
    lines.append("")

    lines.append("## Interpretation")
    lines.append(f"- Oracle-recoverable distinguishing features (exploratory): {', '.join(interpretation_by_target[0]['top_features'][:6]) or 'none'}")
    lines.append(f"- Regression-risk distinguishing features (exploratory): {', '.join(interpretation_by_target[1]['top_features'][:6]) or 'none'}")
    lines.append(f"- Method/artifact dominated signals: {interpretation_primary['method_or_artifact_dominated']}")
    lines.append(
        f"- Parsing/canonicalization issue signals: {', '.join(interpretation_primary['parse_signals'][:4]) if interpretation_primary['parse_signals'] else 'no strong high-lift parse indicators'}"
    )
    lines.append("- Frontier collapse/redundancy diagnosis status: partial; candidate diversity fields exist but verifier/candidate scoring is absent.")
    lines.append(
        "- Missing for reliable diagnosis: "
        + "; ".join(interpretation_primary["missing_for_reliable_diagnosis"])
    )
    lines.append(f"- Suggested manual audit focus: {interpretation_primary['next_manual_audit']}")
    lines.append("")

    lines.append("## Representative Cases")
    if not representative_rows:
        lines.append("- No representative cases could be extracted.")
    else:
        by_target = Counter([r["target"] for r in representative_rows])
        for target, cnt in sorted(by_target.items()):
            lines.append(f"- {target}: {cnt} representatives")
    lines.append("")

    lines.append("## Recommended Next Step")
    lines.append(
        f"- {interpretation_primary['recommended_next_step_code']}: {interpretation_primary['recommended_next_step']}"
    )
    lines.append("")

    lines.append("## Claim Boundary")
    lines.append("- These outputs are exploratory pattern-mining diagnostics from existing artifacts only.")
    lines.append("- Do not claim method superiority based on this analysis alone.")
    return "\n".join(lines) + "\n"


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


def _write_df(path: Path, df: pd.DataFrame) -> None:
    df.to_csv(path, index=False)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feature-table-csv", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--target", default="oracle_recoverable")
    parser.add_argument("--min-support", type=float, default=0.05)
    parser.add_argument("--max-tree-depth", type=int, default=3)
    parser.add_argument("--seed", type=int, default=12345)
    parser.add_argument("--artifact-filter", default="")
    parser.add_argument("--exclude-contaminated", action="store_true")
    return parser.parse_args(argv)


def run(argv: list[str] | None = None) -> dict[str, Any]:
    args = parse_args(argv)

    if args.target not in TARGET_COLUMNS:
        raise ValueError(f"Unsupported target '{args.target}'. Expected one of: {TARGET_COLUMNS}")
    if args.min_support <= 0 or args.min_support > 1:
        raise ValueError("--min-support must be in (0, 1].")
    if args.max_tree_depth < 1:
        raise ValueError("--max-tree-depth must be >= 1.")

    feature_csv = Path(args.feature_table_csv).expanduser()
    out_dir = Path(args.output_dir).expanduser()

    df_raw = _load_feature_table(feature_csv)
    _validate_targets(df_raw)
    df = _normalize_binary_targets(df_raw)
    df = _apply_filters(df, args.artifact_filter, args.exclude_contaminated)
    if df.empty:
        raise ValueError("No rows remain after filtering.")

    feature_cols = _feature_candidates(df, target=args.target)
    if not feature_cols:
        raise ValueError("No valid predictor features found after safety filtering.")

    missingness_rows = _feature_summary(df, feature_cols, importances=[])

    tree_metrics, rules_text, importances, _ = _fit_tree(
        df=df,
        target=args.target,
        feature_cols=feature_cols,
        max_depth=args.max_tree_depth,
        seed=args.seed,
    )

    feature_summary = _feature_summary(df, feature_cols, importances)

    discrete_df = _build_binned_frame(df[feature_cols], feature_cols)
    rule_df, binned_df, _, association_engine = _mine_association_rules(
        discrete_df=discrete_df,
        targets_df=df[list(TARGET_COLUMNS)],
        min_support=args.min_support,
    )

    tgt_summary = _target_summary(df)
    by_artifact = _target_by_artifact(df)
    by_method = _target_by_method(df)
    by_feature_bins = _target_by_feature_bins(discrete_df, df[list(TARGET_COLUMNS)], min_support=args.min_support)

    packets = _load_example_packets(_find_example_packets(feature_csv))
    representative_rows = _representative_cases(df=df, discrete_df=discrete_df, rule_df=rule_df, packets=packets)

    interpretation_primary = _interpretation(
        target=args.target,
        target_summary=tgt_summary,
        feature_summary=feature_summary,
        rule_df=rule_df,
        target_by_method=by_method,
    )
    interpretation_by_target = [
        _interpretation(
            target=t,
            target_summary=tgt_summary,
            feature_summary=feature_summary,
            rule_df=rule_df,
            target_by_method=by_method,
        )
        for t in ("oracle_recoverable", "regression_risk", "both_wrong", "disagreement")
    ]

    out_dir.mkdir(parents=True, exist_ok=True)
    _write_df(out_dir / "target_summary.csv", tgt_summary)
    _write_df(out_dir / "feature_summary.csv", feature_summary)
    (out_dir / "decision_tree_rules.txt").write_text(rules_text, encoding="utf-8")
    _write_json(out_dir / "decision_tree_metrics.json", tree_metrics)
    _write_df(out_dir / "association_rule_candidates.csv", rule_df)
    _write_df(out_dir / "binned_feature_summary.csv", binned_df)
    _write_df(out_dir / "target_by_artifact.csv", by_artifact)
    _write_df(out_dir / "target_by_method.csv", by_method)
    _write_df(out_dir / "target_by_feature_bins.csv", by_feature_bins)
    _write_jsonl(out_dir / "representative_cases.jsonl", representative_rows)

    report = _render_report(
        args=args,
        n_rows=len(df),
        missingness_rows=missingness_rows,
        target_summary=tgt_summary,
        tree_metrics=tree_metrics,
        feature_summary=feature_summary,
        rule_df=rule_df,
        interpretation_primary=interpretation_primary,
        interpretation_by_target=interpretation_by_target,
        representative_rows=representative_rows,
    )
    (out_dir / "pattern_mining_report.md").write_text(report, encoding="utf-8")

    metrics = {
        "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "feature_table_csv": str(feature_csv),
        "output_dir": str(out_dir),
        "row_count": int(len(df)),
        "target": args.target,
        "min_support": float(args.min_support),
        "max_tree_depth": int(args.max_tree_depth),
        "seed": int(args.seed),
        "artifact_filter": args.artifact_filter,
        "exclude_contaminated": bool(args.exclude_contaminated),
        "feature_count": len(feature_cols),
        "association_engine": association_engine,
        "tree_metrics": tree_metrics,
        "target_counts": {t: int(df[t].sum()) for t in TARGET_COLUMNS},
        "target_rates": {t: float(df[t].mean()) for t in TARGET_COLUMNS},
        "representative_counts": dict(Counter([r["target"] for r in representative_rows])),
        "interpretation_primary": interpretation_primary,
        "safety": {
            "api_calls_made": False,
            "provider_calls_made": False,
            "training_large_models": False,
            "output_only_analysis": True,
        },
    }
    _write_json(out_dir / "metrics.json", metrics)
    return metrics


def main() -> int:
    try:
        run()
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
