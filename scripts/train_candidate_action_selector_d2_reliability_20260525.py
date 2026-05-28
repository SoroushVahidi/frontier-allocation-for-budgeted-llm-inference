#!/usr/bin/env python3
"""Job D2: reliability/complementarity-augmented candidate-action selector.

Offline-only, leakage-aware training.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import random
import subprocess
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from pandas.api.types import is_numeric_dtype
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss, roc_auc_score
from sklearn.model_selection import GroupKFold
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
        lines.append("| " + " | ".join(clean_text(r[c]) for c in cols) + " |")
    return "\n".join(lines) + "\n"


def ece_score(y_true: np.ndarray, y_prob: np.ndarray, bins: int = 10) -> float:
    if len(y_true) == 0:
        return float("nan")
    y_true = y_true.astype(float)
    y_prob = np.clip(y_prob.astype(float), 1e-6, 1 - 1e-6)
    edges = np.linspace(0.0, 1.0, bins + 1)
    ece = 0.0
    for i in range(bins):
        lo, hi = edges[i], edges[i + 1]
        mask = (y_prob >= lo) & (y_prob < hi if i < bins - 1 else y_prob <= hi)
        m = int(mask.sum())
        if m == 0:
            continue
        ece += (m / len(y_true)) * abs(float(y_true[mask].mean() - y_prob[mask].mean()))
    return float(ece)


def mcnemar_pvalue(b: int, c: int) -> float:
    # exact binomial two-sided if scipy unavailable fallback approx
    if b + c == 0:
        return 1.0
    if has_pkg("scipy"):
        from scipy.stats import binomtest

        return float(binomtest(min(b, c), n=b + c, p=0.5, alternative="two-sided").pvalue)
    # continuity-corrected chi-square approx
    stat = (abs(b - c) - 1) ** 2 / (b + c)
    # conservative fallback without scipy cdf
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


def canonical_method_rank(method: str) -> int:
    # stable tie-break: frontier, s1, l1, tale
    order = {
        "direct_reserve_semantic_frontier_v2": 0,
        "external_s1_budget_forcing": 1,
        "external_l1_max": 2,
        "external_tale_prompt_budgeting": 3,
    }
    return order.get(method, 99)


def method_alias(method: str) -> str:
    return {
        "direct_reserve_semantic_frontier_v2": "frontier",
        "external_l1_max": "l1",
        "external_s1_budget_forcing": "s1",
        "external_tale_prompt_budgeting": "tale",
    }.get(method, method)


def best_baseline_per_row(row: pd.Series) -> tuple[str, float]:
    cols = [
        "select_frontier_correct",
        "select_l1_correct",
        "select_s1_correct",
        "select_tale_correct",
        "pooled4_correct",
        "agreement_only_correct",
    ]
    vals = {c: float(row[c]) for c in cols if pd.notna(row.get(c))}
    if not vals:
        return "", float("nan")
    m = max(vals.values())
    ks = sorted([k for k, v in vals.items() if v == m])
    return ks[0], m


def available_fixed_policy_baseline_cols(df: pd.DataFrame) -> list[str]:
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


def derive_answer_type(df: pd.DataFrame) -> pd.Series:
    out = np.where(df.get("numeric_answer_flag", 0).astype(int) == 1, "numeric", "other")
    out = np.where(df.get("expression_answer_flag", 0).astype(int) == 1, "expression", out)
    out = np.where(df.get("fraction_answer_flag", 0).astype(int) == 1, "fraction", out)
    out = np.where(df.get("answer_is_empty", 0).astype(int) == 1, "empty", out)
    return pd.Series(out, index=df.index)


def smoothed_rate(correct: float, n: float, global_rate: float, alpha: float = 20.0) -> float:
    return float((correct + alpha * global_rate) / (n + alpha))


def make_rate_map(df: pd.DataFrame, keys: list[str], y_col: str, alpha: float, global_rate: float) -> dict[tuple[Any, ...], tuple[float, int]]:
    g = df.groupby(keys, dropna=False)[y_col].agg(["sum", "count"]).reset_index()
    out: dict[tuple[Any, ...], tuple[float, int]] = {}
    for _, r in g.iterrows():
        key = tuple(r[k] for k in keys)
        n = int(r["count"])
        rate = smoothed_rate(float(r["sum"]), n, global_rate, alpha=alpha)
        out[key] = (rate, n)
    return out


def lookup_backoff(row: pd.Series, maps: list[tuple[list[str], dict[tuple[Any, ...], tuple[float, int]], str]], default_rate: float) -> tuple[float, int, str]:
    for keys, mp, name in maps:
        key = tuple(row[k] for k in keys)
        val = mp.get(key)
        if val is not None:
            return val[0], val[1], name
    return float(default_rate), 0, "global"


def build_reliability_from_train(train_rows: pd.DataFrame, apply_rows: pd.DataFrame, alpha: float = 20.0) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Compute reliability/complementarity features from train_rows only and apply to apply_rows."""
    tr = train_rows.copy()
    ap = apply_rows.copy()

    tr["answer_type"] = derive_answer_type(tr)
    ap["answer_type"] = derive_answer_type(ap)

    # Global priors
    global_rate = float(tr["candidate_correct"].mean()) if len(tr) else 0.5
    global_oracle = float(tr.drop_duplicates("pool_id")["oracle_available"].mean()) if len(tr) else 0.5
    global_all_wrong = float(tr.drop_duplicates("pool_id")["all_sources_wrong"].mean()) if len(tr) else 0.5

    # Base maps
    m_method = make_rate_map(tr, ["method"], "candidate_correct", alpha, global_rate)
    m_provider = make_rate_map(tr, ["provider"], "candidate_correct", alpha, global_rate)
    m_provider_method = make_rate_map(tr, ["provider", "method"], "candidate_correct", alpha, global_rate)
    m_dataset_method = make_rate_map(tr, ["dataset", "method"], "candidate_correct", alpha, global_rate)
    m_provider_dataset_method = make_rate_map(tr, ["provider", "dataset", "method"], "candidate_correct", alpha, global_rate)
    m_dataset_answer_type_method = make_rate_map(tr, ["dataset", "answer_type", "method"], "candidate_correct", alpha, global_rate)
    m_subject_method = make_rate_map(tr, ["math_subject", "method"], "candidate_correct", alpha, global_rate)
    m_level_method = make_rate_map(tr, ["math_level", "method"], "candidate_correct", alpha, global_rate)

    # Pool/scenario reliability maps (pool-level labels projected to candidate rows)
    pool_unique = tr[["pool_id", "provider", "dataset", "oracle_available", "all_sources_wrong"]].drop_duplicates("pool_id")
    m_provider_dataset_oracle = make_rate_map(pool_unique, ["provider", "dataset"], "oracle_available", alpha, global_oracle)
    m_provider_dataset_allwrong = make_rate_map(pool_unique, ["provider", "dataset"], "all_sources_wrong", alpha, global_all_wrong)
    m_dataset_oracle = make_rate_map(pool_unique, ["dataset"], "oracle_available", alpha, global_oracle)
    m_provider_oracle = make_rate_map(pool_unique, ["provider"], "oracle_available", alpha, global_oracle)

    # Cluster/agreement maps
    m_cluster_size = make_rate_map(tr, ["cluster_size"], "candidate_correct", alpha, global_rate)
    m_max_cluster_size = make_rate_map(tr, ["max_cluster_size"], "candidate_correct", alpha, global_rate)
    m_isolated = make_rate_map(tr, ["candidate_is_isolated_flag"], "candidate_correct", alpha, global_rate)
    m_no_majority = make_rate_map(tr, ["no_majority_flag"], "candidate_correct", alpha, global_rate)

    # method + majority-includes-method map using per-method alias flag
    tr = tr.copy()
    ap = ap.copy()
    tr["majority_includes_method_flag"] = tr.apply(
        lambda r: int(r[f"majority_includes_{method_alias(r['method'])}"]) if f"majority_includes_{method_alias(r['method'])}" in tr.columns else 0,
        axis=1,
    )
    ap["majority_includes_method_flag"] = ap.apply(
        lambda r: int(r[f"majority_includes_{method_alias(r['method'])}"]) if f"majority_includes_{method_alias(r['method'])}" in ap.columns else 0,
        axis=1,
    )
    m_majority_includes_method = make_rate_map(tr, ["method", "majority_includes_method_flag"], "candidate_correct", alpha, global_rate)

    # pairwise agreement reliability by method
    pair_cols = ["agrees_with_frontier", "agrees_with_l1", "agrees_with_s1", "agrees_with_tale"]
    pair_maps = {}
    for pc in pair_cols:
        pair_maps[pc] = make_rate_map(tr, ["method", pc], "candidate_correct", alpha, global_rate)

    # Complementarity maps
    m_unique_correct = make_rate_map(tr, ["method"], "candidate_is_unique_correct", alpha, float(tr["candidate_is_unique_correct"].mean()))

    # default method (best raw on train)
    method_acc = tr.groupby("method")["candidate_correct"].mean().to_dict()
    default_method = sorted(method_acc.items(), key=lambda kv: (-kv[1], canonical_method_rank(kv[0])))[0][0] if method_acc else "external_s1_budget_forcing"

    # pool x method correctness matrix
    piv = tr.pivot_table(index="pool_id", columns="method", values="candidate_correct", aggfunc="max")
    for m in ["direct_reserve_semantic_frontier_v2", "external_l1_max", "external_s1_budget_forcing", "external_tale_prompt_budgeting", default_method]:
        if m not in piv.columns:
            piv[m] = 0

    comp_rows = []
    for m in ["direct_reserve_semantic_frontier_v2", "external_l1_max", "external_s1_budget_forcing", "external_tale_prompt_budgeting"]:
        a = piv[m].fillna(0).astype(int)
        b_s1 = piv["external_s1_budget_forcing"].fillna(0).astype(int)
        b_front = piv["direct_reserve_semantic_frontier_v2"].fillna(0).astype(int)
        d = piv[default_method].fillna(0).astype(int)
        n = len(piv)

        both_wrong_s1 = int(((a == 0) & (b_s1 == 0)).sum())
        both_wrong_front = int(((a == 0) & (b_front == 0)).sum())
        both_correct_s1 = int(((a == 1) & (b_s1 == 1)).sum())
        a_only_s1 = int(((a == 1) & (b_s1 == 0)).sum())
        b_only_s1 = int(((a == 0) & (b_s1 == 1)).sum())
        rescue = int(((a == 1) & (d == 0)).sum())
        default_wrong = int((d == 0).sum())

        comp_rows.append(
            {
                "method": m,
                "rel_method_rescue_rate_trainfold": smoothed_rate(rescue, default_wrong, global_rate, alpha),
                "rel_method_error_overlap_with_s1_trainfold": smoothed_rate(both_wrong_s1, n, 1 - global_rate, alpha),
                "rel_method_error_overlap_with_frontier_trainfold": smoothed_rate(both_wrong_front, n, 1 - global_rate, alpha),
                "rel_pair_both_correct_rate_trainfold": smoothed_rate(both_correct_s1, n, global_rate, alpha),
                "rel_pair_a_only_correct_rate_trainfold": smoothed_rate(a_only_s1, n, global_rate, alpha),
                "rel_pair_b_only_correct_rate_trainfold": smoothed_rate(b_only_s1, n, global_rate, alpha),
                "rel_pair_support": n,
            }
        )
    comp_df = pd.DataFrame(comp_rows)

    # Apply to rows with backoff chains
    out = ap.copy()
    support_rows = []

    # A. source/method reliability with backoff
    maps_acc = [
        (["provider", "dataset", "method"], m_provider_dataset_method, "provider_dataset_method"),
        (["dataset", "method"], m_dataset_method, "dataset_method"),
        (["provider", "method"], m_provider_method, "provider_method"),
        (["method"], m_method, "method"),
    ]
    out[["rel_provider_dataset_method_acc_trainfold", "rel_provider_dataset_method_support", "rel_provider_dataset_method_backoff"]] = out.apply(
        lambda r: pd.Series(lookup_backoff(r, maps_acc, global_rate)), axis=1
    )

    out[["rel_method_acc_trainfold", "rel_method_support", "_m"]] = out.apply(
        lambda r: pd.Series(lookup_backoff(r, [(["method"], m_method, "method")], global_rate)), axis=1
    )
    out[["rel_provider_acc_trainfold", "rel_provider_support", "_p"]] = out.apply(
        lambda r: pd.Series(lookup_backoff(r, [(["provider"], m_provider, "provider")], global_rate)), axis=1
    )
    out[["rel_provider_method_acc_trainfold", "rel_provider_method_support", "_pm"]] = out.apply(
        lambda r: pd.Series(lookup_backoff(r, [(["provider", "method"], m_provider_method, "provider_method"), (["method"], m_method, "method")], global_rate)), axis=1
    )
    out[["rel_dataset_method_acc_trainfold", "rel_dataset_method_support", "_dm"]] = out.apply(
        lambda r: pd.Series(lookup_backoff(r, [(["dataset", "method"], m_dataset_method, "dataset_method"), (["method"], m_method, "method")], global_rate)), axis=1
    )
    out[["rel_dataset_answer_type_method_acc_trainfold", "rel_dataset_answer_type_method_support", "_datm"]] = out.apply(
        lambda r: pd.Series(lookup_backoff(r, [(["dataset", "answer_type", "method"], m_dataset_answer_type_method, "dataset_answer_type_method"), (["dataset", "method"], m_dataset_method, "dataset_method"), (["method"], m_method, "method")], global_rate)), axis=1
    )
    out[["rel_math_subject_method_acc_trainfold", "rel_math_subject_method_support", "_msm"]] = out.apply(
        lambda r: pd.Series(lookup_backoff(r, [(["math_subject", "method"], m_subject_method, "math_subject_method"), (["dataset", "method"], m_dataset_method, "dataset_method"), (["method"], m_method, "method")], global_rate)), axis=1
    )
    out[["rel_math_level_method_acc_trainfold", "rel_math_level_method_support", "_mlm"]] = out.apply(
        lambda r: pd.Series(lookup_backoff(r, [(["math_level", "method"], m_level_method, "math_level_method"), (["dataset", "method"], m_dataset_method, "dataset_method"), (["method"], m_method, "method")], global_rate)), axis=1
    )

    # B. pool/scenario reliability
    out[["rel_provider_dataset_oracle_rate_trainfold", "rel_provider_dataset_oracle_support", "_pdo"]] = out.apply(
        lambda r: pd.Series(lookup_backoff(r, [(["provider", "dataset"], m_provider_dataset_oracle, "provider_dataset"), (["dataset"], m_dataset_oracle, "dataset"), (["provider"], m_provider_oracle, "provider")], global_oracle)), axis=1
    )
    out[["rel_provider_dataset_all_wrong_rate_trainfold", "rel_provider_dataset_all_wrong_support", "_pdw"]] = out.apply(
        lambda r: pd.Series(lookup_backoff(r, [(["provider", "dataset"], m_provider_dataset_allwrong, "provider_dataset")], global_all_wrong)), axis=1
    )
    out[["rel_dataset_oracle_rate_trainfold", "rel_dataset_oracle_support", "_do"]] = out.apply(
        lambda r: pd.Series(lookup_backoff(r, [(["dataset"], m_dataset_oracle, "dataset")], global_oracle)), axis=1
    )
    out[["rel_provider_oracle_rate_trainfold", "rel_provider_oracle_support", "_po"]] = out.apply(
        lambda r: pd.Series(lookup_backoff(r, [(["provider"], m_provider_oracle, "provider")], global_oracle)), axis=1
    )

    # C. cluster/agreement reliability
    out[["rel_cluster_size_correct_rate_trainfold", "rel_cluster_size_support", "_cs"]] = out.apply(
        lambda r: pd.Series(lookup_backoff(r, [(["cluster_size"], m_cluster_size, "cluster_size")], global_rate)), axis=1
    )
    out[["rel_max_cluster_size_correct_rate_trainfold", "rel_max_cluster_size_support", "_mcs"]] = out.apply(
        lambda r: pd.Series(lookup_backoff(r, [(["max_cluster_size"], m_max_cluster_size, "max_cluster_size")], global_rate)), axis=1
    )
    out[["rel_candidate_isolated_correct_rate_trainfold", "rel_candidate_isolated_support", "_iso"]] = out.apply(
        lambda r: pd.Series(lookup_backoff(r, [(["candidate_is_isolated_flag"], m_isolated, "candidate_isolated")], global_rate)), axis=1
    )
    out[["rel_no_majority_correct_rate_trainfold", "rel_no_majority_support", "_nm"]] = out.apply(
        lambda r: pd.Series(lookup_backoff(r, [(["no_majority_flag"], m_no_majority, "no_majority")], global_rate)), axis=1
    )
    out[["rel_majority_includes_method_correct_rate_trainfold", "rel_majority_includes_method_support", "_mim"]] = out.apply(
        lambda r: pd.Series(lookup_backoff(r, [(["method", "majority_includes_method_flag"], m_majority_includes_method, "method_majority_includes")], global_rate)), axis=1
    )

    # pair agreement correctness rate by method/agreement flag
    for pc in ["agrees_with_frontier", "agrees_with_l1", "agrees_with_s1", "agrees_with_tale"]:
        out[[f"rel_{pc}_correct_rate_trainfold", f"rel_{pc}_support", f"_{pc}_b"]] = out.apply(
            lambda r, _pc=pc: pd.Series(lookup_backoff(r, [(["method", _pc], pair_maps[_pc], f"method_{_pc}"), (["method"], m_method, "method")], global_rate)),
            axis=1,
        )

    # D. complementarity
    out = out.merge(comp_df, on="method", how="left")
    out[["rel_method_unique_correct_rate_trainfold", "rel_method_unique_correct_support", "_mu"]] = out.apply(
        lambda r: pd.Series(lookup_backoff(r, [(["method"], m_unique_correct, "method_unique")], float(tr["candidate_is_unique_correct"].mean()))), axis=1
    )

    # fill any remaining NA complementarity with priors
    for c in [
        "rel_method_rescue_rate_trainfold",
        "rel_method_error_overlap_with_s1_trainfold",
        "rel_method_error_overlap_with_frontier_trainfold",
        "rel_pair_both_correct_rate_trainfold",
        "rel_pair_a_only_correct_rate_trainfold",
        "rel_pair_b_only_correct_rate_trainfold",
    ]:
        if c in out.columns:
            out[c] = out[c].fillna(global_rate)

    # Build support summary
    support_cols = [c for c in out.columns if c.endswith("_support")]
    supp = []
    for c in support_cols:
        s = out[c].astype(float)
        supp.append({
            "feature_support_col": c,
            "min_support": float(np.nanmin(s)) if len(s) else np.nan,
            "p25_support": float(np.nanquantile(s, 0.25)) if len(s) else np.nan,
            "median_support": float(np.nanmedian(s)) if len(s) else np.nan,
            "p75_support": float(np.nanquantile(s, 0.75)) if len(s) else np.nan,
            "max_support": float(np.nanmax(s)) if len(s) else np.nan,
            "zero_support_rows": int((s == 0).sum()) if len(s) else 0,
            "row_count": int(len(s)),
        })
    support_df = pd.DataFrame(supp)

    # cleanup temp columns
    drop_tmp = [c for c in out.columns if c.startswith("_") and c.endswith(("m", "p", "pm", "dm", "datm", "msm", "mlm", "pdo", "pdw", "do", "po", "cs", "mcs", "iso", "nm", "mim", "b", "mu"))]
    out = out.drop(columns=drop_tmp, errors="ignore")
    return out, support_df


def build_oof_reliability(train_df: pd.DataFrame, n_splits: int = 5, alpha: float = 20.0) -> tuple[pd.DataFrame, pd.DataFrame]:
    gkf = GroupKFold(n_splits=n_splits)
    groups = train_df["pool_id"]
    out_parts = []
    support_parts = []

    for fold, (tri, vai) in enumerate(gkf.split(train_df, train_df["candidate_correct"], groups=groups), start=1):
        tr = train_df.iloc[tri].copy()
        va = train_df.iloc[vai].copy()
        va_feat, supp = build_reliability_from_train(tr, va, alpha=alpha)
        va_feat["_oof_fold"] = fold
        out_parts.append(va_feat)
        supp["fold"] = fold
        support_parts.append(supp)

    out_df = pd.concat(out_parts, ignore_index=True).sort_values("row_id").reset_index(drop=True)
    support_df = pd.concat(support_parts, ignore_index=True)
    return out_df, support_df


def add_reliability_features(candidate_df: pd.DataFrame, alpha: float = 20.0) -> tuple[pd.DataFrame, list[str], pd.DataFrame, str]:
    train = candidate_df[candidate_df["split"] == "train"].copy()
    val = candidate_df[candidate_df["split"] == "validation"].copy()
    test = candidate_df[candidate_df["split"] == "test"].copy()
    seen = candidate_df[candidate_df["split"] == "seen_dev"].copy()

    train_oof, support_oof = build_oof_reliability(train, n_splits=5, alpha=alpha)
    val_feat, support_val = build_reliability_from_train(train, val, alpha=alpha)
    test_feat, support_test = build_reliability_from_train(train, test, alpha=alpha)
    seen_feat, support_seen = build_reliability_from_train(train, seen, alpha=alpha)

    rel_cols = sorted(
        [
            c
            for c in train_oof.columns
            if c.startswith("rel_") or c in {"answer_type", "majority_includes_method_flag"}
        ]
    )

    keep_cols = ["row_id"] + rel_cols
    combined = pd.concat(
        [train_oof[keep_cols], val_feat[keep_cols], test_feat[keep_cols], seen_feat[keep_cols]],
        ignore_index=True,
    )
    out = candidate_df.merge(combined, on="row_id", how="left")

    support_all = pd.concat(
        [
            support_oof.assign(split="train_oof"),
            support_val.assign(split="validation"),
            support_test.assign(split="test"),
            support_seen.assign(split="seen_dev"),
        ],
        ignore_index=True,
    )

    report = [
        "# Fold-Safe Reliability Feature Report",
        "",
        "Reliability/complementarity features were computed with strict split safety:",
        "- Train rows: out-of-fold GroupKFold by pool_id (no in-fold target leakage)",
        "- Validation/test/seen_dev rows: statistics computed from train split only",
        "- Backoff chain with Laplace-style smoothing used for sparse groups",
        f"- Smoothing alpha: {alpha}",
        f"- Reliability feature columns: {len(rel_cols)}",
    ]
    return out, rel_cols, support_all, "\n".join(report) + "\n"


def prepare_features(df: pd.DataFrame, base_allowlist: list[str], forbidden: set[str], extra_rel_cols: list[str]) -> tuple[pd.DataFrame, list[str], list[str], dict[str, Any]]:
    requested = list(base_allowlist) + [c for c in extra_rel_cols if c not in base_allowlist]
    present = [c for c in requested if c in df.columns]
    rejected = [c for c in requested if c not in df.columns]

    filtered = [c for c in present if c not in forbidden]
    rejected.extend(sorted(c for c in present if c in forbidden))
    leakage_hits = [c for c in filtered if c in forbidden]
    if leakage_hits:
        raise RuntimeError(f"Leakage columns remained in filtered feature set: {leakage_hits}")

    X = df[filtered].copy()
    # textual/category casts
    for col in [
        "extracted_answer",
        "normalized_answer",
        "answer_cluster_id",
        "clustering_version",
        "dataset_family",
        "provider_family",
        "model_family",
        "model_type_known",
        "math_subject",
        "answer_type",
    ]:
        if col in X.columns:
            X[col] = X[col].astype("string")

    for col in X.columns:
        if X[col].dtype == "bool":
            X[col] = X[col].astype(int)

    # soft numeric coercion
    for col in X.columns:
        if is_numeric_dtype(X[col]):
            continue
        converted = pd.to_numeric(X[col], errors="coerce")
        if converted.notna().mean() > 0.985:
            X[col] = converted

    numeric_cols = [c for c in X.columns if is_numeric_dtype(X[c])]
    categorical_cols = [c for c in X.columns if c not in numeric_cols]

    meta = {
        "n_features_requested": len(requested),
        "n_features_present": len(present),
        "n_features_used": len(filtered),
        "n_numeric": len(numeric_cols),
        "n_categorical": len(categorical_cols),
    }
    return X, filtered, rejected, meta


def fit_transformer(X_train: pd.DataFrame, X_all: dict[str, pd.DataFrame]) -> tuple[dict[str, np.ndarray], list[str], dict[str, Any]]:
    num_cols = [c for c in X_train.columns if is_numeric_dtype(X_train[c]) and X_train[c].notna().any()]
    cat_cols = [c for c in X_train.columns if c not in num_cols]

    num_imp = SimpleImputer(strategy="median")
    if num_cols:
        X_num_train_df = X_train[num_cols].replace([np.inf, -np.inf], np.nan)
        X_num_train = num_imp.fit_transform(X_num_train_df)
    else:
        X_num_train = np.empty((len(X_train), 0))

    if cat_cols:
        X_cat_train = X_train[cat_cols].astype("string").fillna("__MISSING__").astype(str).to_numpy()
        enc = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
        X_cat_train_ohe = enc.fit_transform(X_cat_train)
        cat_names = enc.get_feature_names_out(cat_cols).tolist()
    else:
        enc = None
        X_cat_train_ohe = np.empty((len(X_train), 0))
        cat_names = []

    out = {"train": np.hstack([X_num_train, X_cat_train_ohe])}
    for k, Xd in X_all.items():
        if k == "train":
            continue
        if num_cols:
            X_num = num_imp.transform(Xd[num_cols].replace([np.inf, -np.inf], np.nan))
        else:
            X_num = np.empty((len(Xd), 0))
        if cat_cols:
            X_cat = Xd[cat_cols].astype("string").fillna("__MISSING__").astype(str).to_numpy()
            X_cat_ohe = enc.transform(X_cat)
        else:
            X_cat_ohe = np.empty((len(Xd), 0))
        out[k] = np.hstack([X_num, X_cat_ohe])

    feature_names = list(num_cols) + cat_names
    meta = {
        "numeric_columns": num_cols,
        "categorical_columns": cat_cols,
        "transformed_feature_count": len(feature_names),
    }
    return out, feature_names, meta


def select_by_pool(df_split: pd.DataFrame, probs: np.ndarray, method_priority: dict[str, float] | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    tmp = df_split.copy()
    tmp["pred_prob"] = probs
    tmp["method_priority_train"] = tmp["method"].map(method_priority or {}).fillna(0.0)
    tmp["stable_method_rank"] = tmp["method"].map(canonical_method_rank)

    # tie detection (same prob per pool, rounded)
    pgrp = tmp.groupby("pool_id")["pred_prob"].agg(["max", "count"]).reset_index()
    ties = []
    for pid, g in tmp.groupby("pool_id"):
        mx = g["pred_prob"].max()
        ties.append({"pool_id": pid, "tie_case_flag": int((np.isclose(g["pred_prob"], mx)).sum() > 1)})
    ties_df = pd.DataFrame(ties)

    tmp = tmp.sort_values(
        ["pool_id", "pred_prob", "cluster_size", "method_priority_train", "stable_method_rank"],
        ascending=[True, False, False, False, True],
    )
    selected = tmp.groupby("pool_id", as_index=False).first()
    selected = selected.merge(ties_df, on="pool_id", how="left")
    selected["selected_correct"] = selected["candidate_correct"].astype(int)
    selected["selected_method"] = selected["method"]
    selected["selected_method_alias"] = selected["method_family"]
    selected["selected_probability"] = selected["pred_prob"]
    selected["selected_is_frontier"] = (selected["method"] == "direct_reserve_semantic_frontier_v2").astype(int)
    selected["selected_is_external"] = 1 - selected["selected_is_frontier"]
    return selected, ties_df


def safe_candidate_metrics(y_true: np.ndarray, y_prob: np.ndarray) -> dict[str, float]:
    y_true = y_true.astype(int)
    y_prob = np.clip(y_prob.astype(float), 1e-6, 1 - 1e-6)
    return {
        "candidate_brier": float(np.mean((y_prob - y_true) ** 2)) if len(y_true) else float("nan"),
        "candidate_log_loss": float(log_loss(y_true, y_prob, labels=[0, 1])) if len(np.unique(y_true)) > 1 else float("nan"),
        "candidate_auc": float(roc_auc_score(y_true, y_prob)) if len(np.unique(y_true)) > 1 else float("nan"),
    }


def evaluate_split(model_name: str, split_name: str, df_split: pd.DataFrame, probs: np.ndarray, method_priority: dict[str, float]) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    y_true = df_split["candidate_correct"].astype(int).to_numpy()
    cand_metrics = safe_candidate_metrics(y_true, probs)
    selected, ties_df = select_by_pool(df_split, probs, method_priority=method_priority)

    by_scenario = (
        selected.groupby(["scenario_id", "provider", "dataset"], as_index=False)
        .agg(
            n_pools=("pool_id", "count"),
            learned_accuracy=("selected_correct", "mean"),
            selector_frontier_rate=("selected_is_frontier", "mean"),
            selector_external_rate=("selected_is_external", "mean"),
            tie_case_rate=("tie_case_flag", "mean"),
        )
    )

    overall = {
        "model": model_name,
        "split": split_name,
        "n_candidate_rows": int(len(df_split)),
        "n_pools": int(selected["pool_id"].nunique()),
        "pool_selected_accuracy": float(selected["selected_correct"].mean()) if len(selected) else float("nan"),
        "macro_scenario_accuracy": float(by_scenario["learned_accuracy"].mean()) if len(by_scenario) else float("nan"),
        "worst_scenario_accuracy": float(by_scenario["learned_accuracy"].min()) if len(by_scenario) else float("nan"),
        "tie_case_rate": float(selected["tie_case_flag"].mean()) if len(selected) else float("nan"),
        **cand_metrics,
    }

    by_scenario.insert(0, "model", model_name)
    by_scenario.insert(1, "split", split_name)
    return overall, by_scenario, selected, ties_df


def pool_baseline_comparison(selected_df: pd.DataFrame, baseline_df: pd.DataFrame, split_name: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    cols = [
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
    b = baseline_df[cols].copy()
    merged = selected_df.merge(b, on="pool_id", how="left")

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
    oracle = baseline_scope.groupby(["scenario_id", "provider", "dataset"], as_index=False).agg(oracle_ceiling=("oracle_correct", "mean"))

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
                "best_baseline_name": best_name,
                "best_baseline_accuracy": best_val,
                "best_raw_baseline_accuracy": best_raw_val,
            }
        )
    scen_base = pd.DataFrame(rows)
    by_scenario = learned.merge(scen_base, on=["scenario_id", "provider", "dataset"], how="left").merge(
        oracle, on=["scenario_id", "provider", "dataset"], how="left"
    )
    by_scenario["delta_vs_best_baseline"] = by_scenario["learned_accuracy"] - by_scenario["best_baseline_accuracy"]
    by_scenario["oracle_gap_recovered"] = by_scenario.apply(
        lambda r: ((r["learned_accuracy"] - r["best_baseline_accuracy"]) / (r["oracle_ceiling"] - r["best_baseline_accuracy"]))
        if (r["oracle_ceiling"] - r["best_baseline_accuracy"]) > 0 else np.nan,
        axis=1,
    )
    by_scenario["result"] = by_scenario["delta_vs_best_baseline"].map(lambda d: "win" if d > 0 else ("tie" if d == 0 else "loss"))
    by_scenario.insert(0, "split", split_name)

    # Keep row-level fields for diagnostics; scenario headline uses fixed-policy aggregation above.
    merged = merged.merge(
        scen_base[["scenario_id", "provider", "dataset", "best_baseline_name", "best_baseline_accuracy"]],
        on=["scenario_id", "provider", "dataset"],
        how="left",
    )
    merged["best_baseline_correct"] = merged["best_baseline_accuracy"]
    merged["delta_vs_best_baseline"] = merged["selected_correct"] - merged["best_baseline_correct"]
    merged["result"] = merged["delta_vs_best_baseline"].map(lambda d: "win" if d > 0 else ("tie" if d == 0 else "loss"))
    return by_scenario, merged


@dataclass
class ModelSpec:
    name: str
    family: str
    params: dict[str, Any]
    gpu_used: bool


def train_model_by_spec(spec: ModelSpec, X_train: np.ndarray, y_train: np.ndarray, X_val: np.ndarray | None = None, y_val: np.ndarray | None = None) -> Any:
    if spec.family == "logreg":
        est = LogisticRegression(**spec.params)
        est.fit(X_train, y_train)
        return est
    if spec.family == "rf":
        est = RandomForestClassifier(**spec.params)
        est.fit(X_train, y_train)
        return est
    if spec.family == "hgb":
        est = HistGradientBoostingClassifier(**spec.params)
        est.fit(X_train, y_train)
        return est
    if spec.family == "xgboost":
        from xgboost import XGBClassifier

        est = XGBClassifier(**spec.params)
        fit_kwargs = {}
        if X_val is not None and y_val is not None and "early_stopping_rounds" in spec.params:
            es = spec.params.get("early_stopping_rounds")
            fit_kwargs = {
                "eval_set": [(X_val, y_val)],
                "verbose": False,
            }
            # move early stopping out of params if needed
            if "early_stopping_rounds" in est.get_params():
                pass
            else:
                fit_kwargs["early_stopping_rounds"] = es
        est.fit(X_train, y_train, **fit_kwargs)
        return est
    if spec.family == "lightgbm":
        from lightgbm import LGBMClassifier

        est = LGBMClassifier(**spec.params)
        est.fit(X_train, y_train)
        return est
    if spec.family == "catboost":
        from catboost import CatBoostClassifier

        est = CatBoostClassifier(**spec.params)
        est.fit(X_train, y_train)
        return est
    raise ValueError(spec.family)


def predict_prob(est: Any, X: np.ndarray) -> np.ndarray:
    if hasattr(est, "predict_proba"):
        p = est.predict_proba(X)[:, 1]
    elif hasattr(est, "decision_function"):
        s = est.decision_function(X)
        p = 1.0 / (1.0 + np.exp(-s))
    else:
        p = est.predict(X).astype(float)
    return np.clip(p.astype(float), 1e-6, 1 - 1e-6)


def objective_validation_macro(est: Any, X_val: np.ndarray, y_val_rows: pd.DataFrame, method_priority: dict[str, float]) -> tuple[float, float, float]:
    p = predict_prob(est, X_val)
    _, by_scen, selected, _ = evaluate_split("tmp", "validation", y_val_rows, p, method_priority)
    macro = float(by_scen["learned_accuracy"].mean()) if len(by_scen) else -1.0
    worst = float(by_scen["learned_accuracy"].min()) if len(by_scen) else -1.0
    acc = float(selected["selected_correct"].mean()) if len(selected) else -1.0
    return macro, worst, acc


def tune_xgboost(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_val: np.ndarray,
    val_rows: pd.DataFrame,
    method_priority: dict[str, float],
    use_gpu: bool,
    trials_max: int,
) -> tuple[ModelSpec, pd.DataFrame]:
    trials = []

    if has_pkg("optuna"):
        import optuna

        sampler = optuna.samplers.TPESampler(seed=42)
        study = optuna.create_study(direction="maximize", sampler=sampler)

        def objective(trial):
            params = {
                "n_estimators": trial.suggest_int("n_estimators", 150, 500),
                "max_depth": trial.suggest_int("max_depth", 4, 10),
                "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.2, log=True),
                "subsample": trial.suggest_float("subsample", 0.7, 1.0),
                "colsample_bytree": trial.suggest_float("colsample_bytree", 0.7, 1.0),
                "min_child_weight": trial.suggest_float("min_child_weight", 1.0, 10.0),
                "reg_lambda": trial.suggest_float("reg_lambda", 0.1, 10.0, log=True),
                "reg_alpha": trial.suggest_float("reg_alpha", 1e-6, 1.0, log=True),
                "scale_pos_weight": trial.suggest_float("scale_pos_weight", 0.5, 2.0),
                "random_state": 42,
                "objective": "binary:logistic",
                "eval_metric": "logloss",
                "n_jobs": -1,
                "tree_method": "hist",
            }
            if use_gpu:
                params["device"] = "cuda"
            spec = ModelSpec("xgboost_trial", "xgboost", params, gpu_used=use_gpu)
            try:
                est = train_model_by_spec(spec, X_train, y_train, X_val=X_val, y_val=val_rows["candidate_correct"].astype(int).to_numpy())
                macro, worst, acc = objective_validation_macro(est, X_val, val_rows, method_priority)
                score = macro + 0.05 * worst
                trials.append({"model": "xgboost", "trial": trial.number, "status": "ok", "gpu_used": use_gpu, "score": score, "macro": macro, "worst": worst, "pool_acc": acc, "params_json": json.dumps(params, sort_keys=True)})
                return score
            except Exception as e:
                trials.append({"model": "xgboost", "trial": trial.number, "status": f"failed:{type(e).__name__}", "gpu_used": use_gpu, "score": -1e9, "macro": np.nan, "worst": np.nan, "pool_acc": np.nan, "params_json": json.dumps(params, sort_keys=True)})
                return -1e9

        study.optimize(objective, n_trials=trials_max, show_progress_bar=False)
        bp = dict(study.best_params)
        params = {
            **bp,
            "random_state": 42,
            "objective": "binary:logistic",
            "eval_metric": "logloss",
            "n_jobs": -1,
            "tree_method": "hist",
        }
        if use_gpu:
            params["device"] = "cuda"
        best_spec = ModelSpec("xgboost", "xgboost", params, gpu_used=use_gpu)
        return best_spec, pd.DataFrame(trials)

    # fallback manual random search
    rng = random.Random(42)
    best_score = -1e9
    best_params = None
    for t in range(min(trials_max, 25)):
        params = {
            "n_estimators": rng.randint(180, 450),
            "max_depth": rng.randint(4, 10),
            "learning_rate": 10 ** rng.uniform(math.log10(0.01), math.log10(0.2)),
            "subsample": rng.uniform(0.75, 1.0),
            "colsample_bytree": rng.uniform(0.75, 1.0),
            "scale_pos_weight": rng.uniform(0.6, 1.8),
            "random_state": 42,
            "objective": "binary:logistic",
            "eval_metric": "logloss",
            "n_jobs": -1,
            "tree_method": "hist",
        }
        if use_gpu:
            params["device"] = "cuda"
        spec = ModelSpec("xgboost_trial", "xgboost", params, gpu_used=use_gpu)
        try:
            est = train_model_by_spec(spec, X_train, y_train)
            macro, worst, acc = objective_validation_macro(est, X_val, val_rows, method_priority)
            score = macro + 0.05 * worst
            trials.append({"model": "xgboost", "trial": t, "status": "ok", "gpu_used": use_gpu, "score": score, "macro": macro, "worst": worst, "pool_acc": acc, "params_json": json.dumps(params, sort_keys=True)})
            if score > best_score:
                best_score = score
                best_params = params
        except Exception as e:
            trials.append({"model": "xgboost", "trial": t, "status": f"failed:{type(e).__name__}", "gpu_used": use_gpu, "score": -1e9, "macro": np.nan, "worst": np.nan, "pool_acc": np.nan, "params_json": json.dumps(params, sort_keys=True)})

    if best_params is None:
        best_params = {
            "n_estimators": 300,
            "max_depth": 8,
            "learning_rate": 0.05,
            "subsample": 0.9,
            "colsample_bytree": 0.9,
            "random_state": 42,
            "objective": "binary:logistic",
            "eval_metric": "logloss",
            "n_jobs": -1,
            "tree_method": "hist",
        }
        if use_gpu:
            best_params["device"] = "cuda"
    return ModelSpec("xgboost", "xgboost", best_params, gpu_used=use_gpu), pd.DataFrame(trials)


def tune_lightgbm(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_val: np.ndarray,
    val_rows: pd.DataFrame,
    method_priority: dict[str, float],
    use_gpu: bool,
    trials_max: int,
) -> tuple[ModelSpec, pd.DataFrame]:
    trials = []

    rng = random.Random(43)
    best_score = -1e9
    best_params = None

    # keep practical
    for t in range(min(trials_max, 25)):
        params = {
            "n_estimators": rng.randint(150, 450),
            "learning_rate": 10 ** rng.uniform(math.log10(0.01), math.log10(0.2)),
            "num_leaves": rng.randint(31, 127),
            "subsample": rng.uniform(0.75, 1.0),
            "colsample_bytree": rng.uniform(0.75, 1.0),
            "random_state": 42,
            "objective": "binary",
            "n_jobs": -1,
        }
        if use_gpu:
            params["device"] = "gpu"
        spec = ModelSpec("lightgbm_trial", "lightgbm", params, gpu_used=use_gpu)
        try:
            est = train_model_by_spec(spec, X_train, y_train)
            macro, worst, acc = objective_validation_macro(est, X_val, val_rows, method_priority)
            score = macro + 0.05 * worst
            trials.append({"model": "lightgbm", "trial": t, "status": "ok", "gpu_used": use_gpu, "score": score, "macro": macro, "worst": worst, "pool_acc": acc, "params_json": json.dumps(params, sort_keys=True)})
            if score > best_score:
                best_score = score
                best_params = params
        except Exception as e:
            trials.append({"model": "lightgbm", "trial": t, "status": f"failed:{type(e).__name__}", "gpu_used": use_gpu, "score": -1e9, "macro": np.nan, "worst": np.nan, "pool_acc": np.nan, "params_json": json.dumps(params, sort_keys=True)})

    if best_params is None:
        best_params = {
            "n_estimators": 300,
            "learning_rate": 0.05,
            "num_leaves": 63,
            "random_state": 42,
            "objective": "binary",
            "n_jobs": -1,
        }
        if use_gpu:
            best_params["device"] = "gpu"
    return ModelSpec("lightgbm", "lightgbm", best_params, gpu_used=use_gpu), pd.DataFrame(trials)


def create_environment_reports(run_dir: Path) -> tuple[pd.DataFrame, bool]:
    # package checks
    pkgs = ["sklearn", "xgboost", "lightgbm", "catboost", "optuna", "shap"]
    avail = [{"package": p, "available": has_pkg(p)} for p in pkgs]
    p_df = pd.DataFrame(avail)
    p_df.to_csv(run_dir / "package_availability_report.csv", index=False)
    (run_dir / "package_availability_report.md").write_text(md_table(p_df, "Package Availability"))

    # gpu availability
    gpu_raw = run_command("nvidia-smi || true")
    gpu_ok = "NVIDIA-SMI" in gpu_raw
    (run_dir / "gpu_availability_report.md").write_text("# GPU Availability Report\n\n```text\n" + gpu_raw + "\n```\n")

    env_lines = [
        "# Environment Report",
        "",
        f"Generated at: {now_utc()}",
        "",
        "```text",
        run_command("pwd") + run_command("date") + run_command("git status --short") + run_command("git branch -vv") + run_command("git log --oneline -10") + run_command("tmux ls || true") + run_command("python3 -V") + run_command("which python3") + gpu_raw,
        "```",
    ]
    (run_dir / "environment_report.md").write_text("\n".join(env_lines) + "\n")
    return p_df, gpu_ok


def update_training_ledger(
    ledger_root: Path,
    d1_run: Path,
    d2_run: Path,
    d2_summary: dict[str, Any],
) -> None:
    ledger_root.mkdir(parents=True, exist_ok=True)
    csv_path = ledger_root / "training_experiment_ledger.csv"
    md_path = ledger_root / "training_experiment_ledger.md"
    backlog_path = ledger_root / "training_backlog.md"

    rows = []
    # seed D1 entry from known run
    d1_comp = pd.read_csv(d1_run / "baseline_comparison_by_scenario.csv") if (d1_run / "baseline_comparison_by_scenario.csv").exists() else pd.DataFrame()
    d1_test = d1_comp[d1_comp["split"] == "test"] if len(d1_comp) else pd.DataFrame()
    d1_seen = d1_comp[d1_comp["split"] == "seen_dev"] if len(d1_comp) else pd.DataFrame()
    d1_w = int((d1_test["result"] == "win").sum()) if len(d1_test) else 0
    d1_t = int((d1_test["result"] == "tie").sum()) if len(d1_test) else 0
    d1_l = int((d1_test["result"] == "loss").sum()) if len(d1_test) else 0
    d1_sw = int((d1_seen["result"] == "win").sum()) if len(d1_seen) else 0
    d1_st = int((d1_seen["result"] == "tie").sum()) if len(d1_seen) else 0
    d1_sl = int((d1_seen["result"] == "loss").sum()) if len(d1_seen) else 0

    d1_over = pd.read_csv(d1_run / "model_results_overall.csv") if (d1_run / "model_results_overall.csv").exists() else pd.DataFrame()
    d1_best = "xgboost"
    if len(d1_over):
        d1v = d1_over[d1_over["split"] == "validation"].sort_values(["macro_scenario_accuracy", "worst_scenario_accuracy"], ascending=False)
        if len(d1v):
            d1_best = str(d1v.iloc[0]["model"])

    rows.append(
        {
            "run_id": d1_run.name,
            "date_time_utc": now_utc(),
            "input_table_path": "outputs/unified_learning_tables_20260525/run_20260525T184354Z",
            "output_path": str(d1_run),
            "model_families_tried": "logreg,rf,hgb,xgboost,lightgbm",
            "feature_groups_used": "base_runtime_allowlist",
            "reliability_features_used": "no",
            "complementarity_features_used": "no",
            "calibration_used": "yes",
            "gpu_used": "unknown",
            "clean_test_wins_ties_losses": f"{d1_w}/{d1_t}/{d1_l}",
            "seen_dev_wins_ties_losses": f"{d1_sw}/{d1_st}/{d1_sl}",
            "macro_accuracy": float(d1_over[(d1_over['model']==d1_best) & (d1_over['split']=='test')]['macro_scenario_accuracy'].iloc[0]) if len(d1_over[(d1_over['model']==d1_best) & (d1_over['split']=='test')]) else np.nan,
            "worst_scenario_accuracy": float(d1_over[(d1_over['model']==d1_best) & (d1_over['split']=='test')]['worst_scenario_accuracy'].iloc[0]) if len(d1_over[(d1_over['model']==d1_best) & (d1_over['split']=='test')]) else np.nan,
            "biggest_losses": "cohere_gsm8k(clean), cohere_math500(cloudrift_math500/mistral_math500 seen_dev)",
            "promotion_decision": "not fully promotable",
            "next_recommended_training": "D2 reliability/complementarity features",
        }
    )

    rows.append(
        {
            "run_id": d2_run.name,
            "date_time_utc": now_utc(),
            "input_table_path": "outputs/unified_learning_tables_20260525/run_20260525T184354Z",
            "output_path": str(d2_run),
            "model_families_tried": d2_summary.get("model_families_tried", ""),
            "feature_groups_used": d2_summary.get("feature_groups_used", ""),
            "reliability_features_used": "yes",
            "complementarity_features_used": "yes",
            "calibration_used": "yes",
            "gpu_used": "yes" if d2_summary.get("gpu_used") else "no",
            "clean_test_wins_ties_losses": d2_summary.get("clean_wtl", ""),
            "seen_dev_wins_ties_losses": d2_summary.get("seen_wtl", ""),
            "macro_accuracy": d2_summary.get("macro_accuracy_test", np.nan),
            "worst_scenario_accuracy": d2_summary.get("worst_accuracy_test", np.nan),
            "biggest_losses": d2_summary.get("biggest_losses", ""),
            "promotion_decision": d2_summary.get("promotion_decision", ""),
            "next_recommended_training": d2_summary.get("next_action", ""),
        }
    )

    df = pd.DataFrame(rows)
    df.to_csv(csv_path, index=False)
    md = md_table(df, "Training Experiment Ledger")
    md_path.write_text(md)

    backlog_lines = [
        "# Training Backlog",
        "",
        "Not-yet-run planned experiments:",
        "- D3 ranking/LambdaMART objective",
        "- D4 oracle-availability two-stage head",
        "- D5 frontier-variant inclusion after new frontier generation",
        "- D6 external-provider expansion after Fireworks/Cerebras complete",
        "- D7 clean MATH-500 final-test training/evaluation when clean split is available",
    ]
    backlog_path.write_text("\n".join(backlog_lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Job D2 reliability selector training")
    parser.add_argument("--input-dir", default="outputs/unified_learning_tables_20260525/run_20260525T184354Z")
    parser.add_argument("--d1-run", default="outputs/job_d_candidate_action_training_20260525/run_20260525T190429Z")
    parser.add_argument("--output-root", default="outputs/job_d2_reliability_selector_20260525")
    parser.add_argument("--ledger-root", default="outputs/training_experiment_ledger_20260525")
    parser.add_argument("--xgb-trials", type=int, default=30)
    parser.add_argument("--lgbm-trials", type=int, default=20)
    parser.add_argument("--alpha", type=float, default=20.0)
    args = parser.parse_args()

    in_dir = Path(args.input_dir)
    d1_dir = Path(args.d1_run)
    out_dir = ensure_run_dir(Path(args.output_root))

    # Base run log
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

    pkg_df, gpu_available = create_environment_reports(out_dir)

    # Load data
    candidate = pd.read_csv(in_dir / "unified_candidate_action_table.csv")
    pool = pd.read_csv(in_dir / "unified_pool_level_table.csv")
    baseline = pd.read_csv(in_dir / "baseline_pool_decisions.csv")
    baseline_summary = pd.read_csv(in_dir / "baseline_summary_by_scenario.csv")

    allowlist = [x.strip() for x in (in_dir / "feature_allowlist_candidate_level.txt").read_text().splitlines() if x.strip()]
    forbidden_file = {x.strip() for x in (in_dir / "forbidden_feature_list.txt").read_text().splitlines() if x.strip()}
    extra_forbidden = {
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
    forbidden = forbidden_file | extra_forbidden

    candidate["candidate_correct"] = candidate["candidate_correct"].map(bool_int)
    candidate["oracle_available"] = candidate["candidate_correct"].groupby(candidate["pool_id"]).transform("max").astype(int)
    candidate["all_sources_wrong"] = 1 - candidate["oracle_available"]

    # Build fold-safe reliability/complementarity features
    cand_rel, rel_cols, support_df, rel_report = add_reliability_features(candidate, alpha=args.alpha)

    # Reliability reports
    (out_dir / "fold_safe_reliability_feature_report.md").write_text(rel_report)
    (out_dir / "reliability_feature_columns.txt").write_text("\n".join(sorted(rel_cols)) + "\n")
    support_df.to_csv(out_dir / "reliability_feature_support_summary.csv", index=False)

    leak_rel_lines = [
        "# Reliability Feature Leakage Audit",
        "",
        "Reliability features were built with strict fold safety:",
        "- train rows via out-of-fold GroupKFold",
        "- validation/test/seen_dev from train-only stats",
        "- no validation/test/seen_dev labels used in stat construction",
        f"Reliability feature count: {len(rel_cols)}",
    ]
    (out_dir / "reliability_feature_leakage_audit.md").write_text("\n".join(leak_rel_lines) + "\n")

    # Prepare final features
    X_df, used_cols, rejected_cols, feat_meta = prepare_features(cand_rel, allowlist, forbidden, rel_cols)
    (out_dir / "feature_columns_base_used.txt").write_text("\n".join(used_cols) + "\n")
    (out_dir / "feature_columns_forbidden_rejected.txt").write_text("\n".join(sorted(set(rejected_cols))) + "\n")

    leakage_lines = [
        "# Leakage Check Before D2 Training",
        "",
        f"Candidate rows: {len(cand_rel)}",
        f"Requested base allowlist features: {len(allowlist)}",
        f"Reliability/complementarity features added: {len(rel_cols)}",
        f"Total features used: {len(used_cols)}",
        f"Rejected/forbidden features: {len(rejected_cols)}",
        "",
        "No forbidden feature columns were passed into model training matrix.",
        "Split integrity: seen_dev excluded from model selection and used diagnostic-only.",
    ]
    (out_dir / "leakage_check_before_d2_training.md").write_text("\n".join(leakage_lines) + "\n")

    # Split data
    masks = {
        "train": cand_rel["split"] == "train",
        "validation": cand_rel["split"] == "validation",
        "test": cand_rel["split"] == "test",
        "seen_dev": cand_rel["split"] == "seen_dev",
    }

    train_rows = cand_rel[masks["train"]].copy()
    val_rows = cand_rel[masks["validation"]].copy()
    test_rows = cand_rel[masks["test"]].copy()
    seen_rows = cand_rel[masks["seen_dev"]].copy()

    # method priority learned from train reliability
    method_priority = train_rows.groupby("method")["rel_provider_dataset_method_acc_trainfold"].mean().to_dict()

    X_mats, transformed_feature_names, transform_meta = fit_transformer(
        X_df[masks["train"]],
        {
            "train": X_df[masks["train"]],
            "validation": X_df[masks["validation"]],
            "test": X_df[masks["test"]],
            "seen_dev": X_df[masks["seen_dev"]],
        },
    )

    y = {
        k: cand_rel.loc[masks[k], "candidate_correct"].astype(int).to_numpy()
        for k in masks
    }

    # package + model availability
    pkg_availability = {
        "xgboost": has_pkg("xgboost"),
        "lightgbm": has_pkg("lightgbm"),
        "catboost": has_pkg("catboost"),
        "optuna": has_pkg("optuna"),
        "shap": has_pkg("shap"),
    }

    model_rows = [
        {"model": "logistic_regression", "available": True, "gpu_attempted": False, "gpu_used": False, "note": "class_weight=balanced"},
        {"model": "random_forest", "available": True, "gpu_attempted": False, "gpu_used": False, "note": "class_weight=balanced"},
        {"model": "hist_gradient_boosting", "available": True, "gpu_attempted": False, "gpu_used": False, "note": "sklearn"},
        {"model": "xgboost", "available": pkg_availability["xgboost"], "gpu_attempted": gpu_available and pkg_availability["xgboost"], "gpu_used": False, "note": "tuned"},
        {"model": "lightgbm", "available": pkg_availability["lightgbm"], "gpu_attempted": gpu_available and pkg_availability["lightgbm"], "gpu_used": False, "note": "tuned"},
        {"model": "catboost", "available": pkg_availability["catboost"], "gpu_attempted": gpu_available and pkg_availability["catboost"], "gpu_used": False, "note": "not installed fallback"},
    ]

    # Model specs
    specs: list[ModelSpec] = [
        ModelSpec("logistic_regression", "logreg", {"max_iter": 4000, "solver": "lbfgs", "class_weight": "balanced"}, gpu_used=False),
        ModelSpec("random_forest", "rf", {"n_estimators": 500, "random_state": 42, "n_jobs": -1, "class_weight": "balanced_subsample"}, gpu_used=False),
        ModelSpec("hist_gradient_boosting", "hgb", {"random_state": 42, "max_depth": 8, "learning_rate": 0.05, "max_iter": 350}, gpu_used=False),
    ]

    hyper_trials = []

    # Tune XGBoost with GPU fallback
    if pkg_availability["xgboost"]:
        xgb_gpu_ok = False
        xgb_trials_df = pd.DataFrame()
        xgb_spec = None
        if gpu_available:
            try:
                xgb_spec_gpu, tr_gpu = tune_xgboost(X_mats["train"], y["train"], X_mats["validation"], val_rows, method_priority, use_gpu=True, trials_max=args.xgb_trials)
                # smoke fit best
                _ = train_model_by_spec(xgb_spec_gpu, X_mats["train"], y["train"], X_val=X_mats["validation"], y_val=y["validation"])
                xgb_gpu_ok = True
                xgb_spec = xgb_spec_gpu
                xgb_trials_df = tr_gpu
            except Exception:
                xgb_gpu_ok = False
                hyper_trials.append({"model": "xgboost", "trial": -1, "status": "gpu_failed_fallback_cpu", "gpu_used": True, "score": np.nan, "macro": np.nan, "worst": np.nan, "pool_acc": np.nan, "params_json": "{}"})
        if not xgb_gpu_ok:
            xgb_spec_cpu, tr_cpu = tune_xgboost(X_mats["train"], y["train"], X_mats["validation"], val_rows, method_priority, use_gpu=False, trials_max=args.xgb_trials)
            xgb_spec = xgb_spec_cpu
            xgb_trials_df = tr_cpu
        specs.append(xgb_spec)
        hyper_trials.extend(xgb_trials_df.to_dict("records"))
        for r in model_rows:
            if r["model"] == "xgboost":
                r["gpu_used"] = bool(xgb_spec.gpu_used)
                r["note"] = f"selected_params={json.dumps(xgb_spec.params, sort_keys=True)}"

    # Tune LightGBM with GPU fallback
    if pkg_availability["lightgbm"]:
        lgb_gpu_ok = False
        lgb_trials_df = pd.DataFrame()
        lgb_spec = None
        if gpu_available:
            try:
                lgb_spec_gpu, tr_gpu = tune_lightgbm(X_mats["train"], y["train"], X_mats["validation"], val_rows, method_priority, use_gpu=True, trials_max=args.lgbm_trials)
                _ = train_model_by_spec(lgb_spec_gpu, X_mats["train"], y["train"])
                lgb_gpu_ok = True
                lgb_spec = lgb_spec_gpu
                lgb_trials_df = tr_gpu
            except Exception:
                lgb_gpu_ok = False
                hyper_trials.append({"model": "lightgbm", "trial": -1, "status": "gpu_failed_fallback_cpu", "gpu_used": True, "score": np.nan, "macro": np.nan, "worst": np.nan, "pool_acc": np.nan, "params_json": "{}"})
        if not lgb_gpu_ok:
            lgb_spec_cpu, tr_cpu = tune_lightgbm(X_mats["train"], y["train"], X_mats["validation"], val_rows, method_priority, use_gpu=False, trials_max=args.lgbm_trials)
            lgb_spec = lgb_spec_cpu
            lgb_trials_df = tr_cpu
        specs.append(lgb_spec)
        hyper_trials.extend(lgb_trials_df.to_dict("records"))
        for r in model_rows:
            if r["model"] == "lightgbm":
                r["gpu_used"] = bool(lgb_spec.gpu_used)
                r["note"] = f"selected_params={json.dumps(lgb_spec.params, sort_keys=True)}"

    model_avail_df = pd.DataFrame(model_rows)
    model_avail_df.to_csv(out_dir / "package_availability_report.csv", index=False)
    (out_dir / "package_availability_report.md").write_text(md_table(model_avail_df, "Package/Model Availability"))

    pd.DataFrame(hyper_trials).to_csv(out_dir / "hyperparameter_trials.csv", index=False)

    # Train/evaluate models
    overall_rows = []
    by_scenario_frames = []
    selected_by_model_split: dict[tuple[str, str], pd.DataFrame] = {}
    prob_by_model_split: dict[tuple[str, str], np.ndarray] = {}
    fit_models: dict[str, Any] = {}

    for spec in specs:
        try:
            est = train_model_by_spec(spec, X_mats["train"], y["train"], X_val=X_mats["validation"], y_val=y["validation"])
        except Exception:
            # fail-safe skip model but continue
            traceback_text = traceback.format_exc()
            with (out_dir / "run.log").open("a") as f:
                f.write(f"\nMODEL_FAILED {spec.name}\n{traceback_text}\n")
            continue

        fit_models[spec.name] = est

        for split in ["train", "validation", "test", "seen_dev"]:
            rows = cand_rel[masks[split]].copy()
            if len(rows) == 0:
                continue
            probs = predict_prob(est, X_mats[split])
            prob_by_model_split[(spec.name, split)] = probs
            overall, by_scen, selected, ties = evaluate_split(spec.name, split, rows, probs, method_priority)
            overall_rows.append(overall)
            by_scenario_frames.append(by_scen)
            selected_by_model_split[(spec.name, split)] = selected

    overall_df = pd.DataFrame(overall_rows)
    by_scenario_df = pd.concat(by_scenario_frames, ignore_index=True) if by_scenario_frames else pd.DataFrame()

    if overall_df.empty:
        raise RuntimeError("No models trained successfully.")

    val_df = overall_df[overall_df["split"] == "validation"].sort_values(
        ["macro_scenario_accuracy", "worst_scenario_accuracy", "pool_selected_accuracy"],
        ascending=[False, False, False],
    )
    best_model = str(val_df.iloc[0]["model"])

    # Calibration for best model
    cal_rows = []
    y_val = y["validation"]
    p_val = prob_by_model_split[(best_model, "validation")]

    for split in ["test", "seen_dev"]:
        if (best_model, split) not in prob_by_model_split:
            continue
        p_raw = prob_by_model_split[(best_model, split)]
        y_true = y[split]
        rows = cand_rel[masks[split]].copy()

        raw_selected, _ = select_by_pool(rows, p_raw, method_priority)
        raw_acc = float(raw_selected["selected_correct"].mean()) if len(raw_selected) else np.nan

        # Platt
        if len(np.unique(y_val)) > 1 and len(y_val) > 0:
            logit_val = np.log(np.clip(p_val, 1e-6, 1 - 1e-6) / (1 - np.clip(p_val, 1e-6, 1 - 1e-6))).reshape(-1, 1)
            logit_tgt = np.log(np.clip(p_raw, 1e-6, 1 - 1e-6) / (1 - np.clip(p_raw, 1e-6, 1 - 1e-6))).reshape(-1, 1)
            platt = LogisticRegression(max_iter=3000)
            platt.fit(logit_val, y_val)
            p_platt = platt.predict_proba(logit_tgt)[:, 1]
        else:
            p_platt = p_raw.copy()

        platt_selected, _ = select_by_pool(rows, p_platt, method_priority)
        platt_acc = float(platt_selected["selected_correct"].mean()) if len(platt_selected) else np.nan

        # Isotonic if enough positives/negatives
        if len(np.unique(y_val)) > 1 and len(y_val) >= 200:
            iso = IsotonicRegression(out_of_bounds="clip")
            iso.fit(p_val, y_val)
            p_iso = iso.predict(p_raw)
            iso_selected, _ = select_by_pool(rows, p_iso, method_priority)
            iso_acc = float(iso_selected["selected_correct"].mean()) if len(iso_selected) else np.nan
            iso_brier = float(np.mean((p_iso - y_true) ** 2))
            iso_ece = ece_score(y_true, p_iso)
        else:
            p_iso = p_raw.copy()
            iso_acc = raw_acc
            iso_brier = float(np.mean((p_raw - y_true) ** 2)) if len(y_true) else np.nan
            iso_ece = ece_score(y_true, p_raw)

        cal_rows.append(
            {
                "model": best_model,
                "split": split,
                "uncalibrated_acc": raw_acc,
                "platt_acc": platt_acc,
                "isotonic_acc": iso_acc,
                "uncalibrated_brier": float(np.mean((p_raw - y_true) ** 2)) if len(y_true) else np.nan,
                "platt_brier": float(np.mean((p_platt - y_true) ** 2)) if len(y_true) else np.nan,
                "isotonic_brier": iso_brier,
                "uncalibrated_log_loss": float(log_loss(y_true, p_raw, labels=[0, 1])) if len(np.unique(y_true)) > 1 else np.nan,
                "platt_log_loss": float(log_loss(y_true, p_platt, labels=[0, 1])) if len(np.unique(y_true)) > 1 else np.nan,
                "isotonic_log_loss": float(log_loss(y_true, np.clip(p_iso, 1e-6, 1 - 1e-6), labels=[0, 1])) if len(np.unique(y_true)) > 1 else np.nan,
                "uncalibrated_ece": ece_score(y_true, p_raw),
                "platt_ece": ece_score(y_true, p_platt),
                "isotonic_ece": iso_ece,
            }
        )
    cal_df = pd.DataFrame(cal_rows)
    cal_df.to_csv(out_dir / "calibrated_vs_uncalibrated_results.csv", index=False)

    cal_report = [
        "# Calibration Report",
        "",
        f"Best model selected on validation: `{best_model}`",
        "Calibration variants evaluated using validation-fit mappings only: raw, Platt, isotonic.",
    ]
    (out_dir / "calibration_report.md").write_text("\n".join(cal_report) + "\n")

    # overall/split outputs
    overall_df.to_csv(out_dir / "model_results_overall.csv", index=False)
    by_scenario_df = by_scenario_df.merge(
        baseline_summary.rename(columns={"n_pools": "baseline_n_pools"}),
        on=["scenario_id", "provider", "dataset"],
        how="left",
    )
    by_scenario_df.to_csv(out_dir / "model_results_by_scenario.csv", index=False)
    (out_dir / "model_results_by_scenario.md").write_text(md_table(by_scenario_df, "Model Results By Scenario"))

    best_split_df = overall_df[overall_df["model"] == best_model][
        [
            "model",
            "split",
            "n_candidate_rows",
            "n_pools",
            "pool_selected_accuracy",
            "macro_scenario_accuracy",
            "worst_scenario_accuracy",
            "tie_case_rate",
            "candidate_auc",
            "candidate_log_loss",
            "candidate_brier",
        ]
    ].copy()
    best_split_df.to_csv(out_dir / "split_results.csv", index=False)

    # selector predictions for best model
    selector_cases = []
    for split in ["test", "seen_dev"]:
        rows = cand_rel[masks[split]].copy()
        probs = prob_by_model_split[(best_model, split)]
        selected, ties_df = select_by_pool(rows, probs, method_priority)
        selected["split"] = split
        selector_cases.append(selected)
    selector_cases_df = pd.concat(selector_cases, ignore_index=True)

    # attach baseline fields
    base_cols = [
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
    selector_cases_df = selector_cases_df.merge(baseline[base_cols], on="pool_id", how="left", suffixes=("", "_base"))
    selector_cases_df["all_sources_wrong"] = 1 - selector_cases_df["oracle_correct"].fillna(0).astype(int)

    # best baseline row-wise
    bb = selector_cases_df.apply(lambda r: best_baseline_per_row(r), axis=1)
    selector_cases_df["best_baseline_name"] = [x[0] for x in bb]
    selector_cases_df["best_baseline_correct"] = [x[1] for x in bb]
    selector_cases_df["delta_vs_best_baseline"] = selector_cases_df["selected_correct"] - selector_cases_df["best_baseline_correct"]
    selector_cases_df["result"] = selector_cases_df["delta_vs_best_baseline"].map(lambda d: "win" if d > 0 else ("tie" if d == 0 else "loss"))

    selector_cases_df.to_csv(out_dir / "selector_case_predictions.csv", index=False)

    # baseline comparison by scenario
    comp_frames = []
    for split in ["test", "seen_dev"]:
        sub = selector_cases_df[selector_cases_df["split"] == split].copy()
        if sub.empty:
            continue
        base_sub = baseline[baseline["pool_id"].isin(sub["pool_id"])].copy()
        fixed_cols = available_fixed_policy_baseline_cols(base_sub)
        by = (
            sub.groupby(["scenario_id", "provider", "dataset"], as_index=False)
            .agg(
                pools=("pool_id", "count"),
                learned_accuracy=("selected_correct", "mean"),
            )
        )
        rows = []
        for _, rr in by.iterrows():
            mask = (
                (base_sub["scenario_id"] == rr["scenario_id"])
                & (base_sub["provider"] == rr["provider"])
                & (base_sub["dataset"] == rr["dataset"])
            )
            g = base_sub[mask]
            best_name, best_acc = best_fixed_policy_for_group(g, fixed_cols)
            oracle = float(g["oracle_correct"].mean()) if len(g) else float("nan")
            rows.append(
                {
                    "scenario_id": rr["scenario_id"],
                    "provider": rr["provider"],
                    "dataset": rr["dataset"],
                    "best_baseline_name": best_name,
                    "best_baseline_accuracy": best_acc,
                    "oracle_ceiling": oracle,
                }
            )
        by = by.merge(pd.DataFrame(rows), on=["scenario_id", "provider", "dataset"], how="left")
        by["delta_vs_best_baseline"] = by["learned_accuracy"] - by["best_baseline_accuracy"]
        by["result"] = by["delta_vs_best_baseline"].map(lambda d: "win" if d > 0 else ("tie" if d == 0 else "loss"))
        by.insert(0, "split", split)
        comp_frames.append(by)
    comp_df = pd.concat(comp_frames, ignore_index=True) if comp_frames else pd.DataFrame()
    comp_df.to_csv(out_dir / "baseline_comparison_by_scenario.csv", index=False)
    (out_dir / "baseline_comparison_by_scenario.md").write_text(md_table(comp_df, "Baseline Comparison By Scenario"))

    seen_dev_diag = comp_df[comp_df["split"] == "seen_dev"].copy()
    seen_dev_diag.to_csv(out_dir / "seen_dev_diagnostic_results.csv", index=False)

    # D1 vs D2 comparison
    d1_comp = pd.read_csv(d1_dir / "baseline_comparison_by_scenario.csv")
    d1_simple = d1_comp[["split", "scenario_id", "provider", "dataset", "learned_accuracy"]].rename(columns={"learned_accuracy": "d1_accuracy"})
    d2_simple = comp_df[["split", "scenario_id", "provider", "dataset", "learned_accuracy", "best_baseline_accuracy", "oracle_ceiling"]].rename(columns={"learned_accuracy": "d2_accuracy"})
    d1d2 = d2_simple.merge(d1_simple, on=["split", "scenario_id", "provider", "dataset"], how="left")
    d1d2["d2_minus_d1"] = d1d2["d2_accuracy"] - d1d2["d1_accuracy"]
    d1d2["improved_vs_d1"] = d1d2["d2_minus_d1"].map(lambda d: "improved" if d > 0 else ("tie" if d == 0 else "regressed"))
    d1d2.to_csv(out_dir / "d1_vs_d2_comparison.csv", index=False)
    (out_dir / "d1_vs_d2_comparison.md").write_text(md_table(d1d2, "D1 vs D2 Comparison"))

    # Paired statistics D2 vs baselines
    paired_base_rows = []
    paired_d1_rows = []
    for split in ["test", "seen_dev"]:
        sub = selector_cases_df[selector_cases_df["split"] == split].copy()
        if sub.empty:
            continue
        a = sub["selected_correct"].astype(int).to_numpy()
        b = sub["best_baseline_correct"].astype(int).to_numpy()
        both_correct = int(((a == 1) & (b == 1)).sum())
        d2_only = int(((a == 1) & (b == 0)).sum())
        base_only = int(((a == 0) & (b == 1)).sum())
        both_wrong = int(((a == 0) & (b == 0)).sum())
        m = mcnemar_pvalue(d2_only, base_only)
        mean_d, lo, hi = bootstrap_ci_diff(a.astype(float), b.astype(float), n_boot=3000, seed=42)
        paired_base_rows.append(
            {
                "split": split,
                "both_correct": both_correct,
                "d2_only_correct": d2_only,
                "baseline_only_correct": base_only,
                "both_wrong": both_wrong,
                "mcnemar_pvalue": m,
                "bootstrap_delta_mean": mean_d,
                "bootstrap_delta_ci_low": lo,
                "bootstrap_delta_ci_high": hi,
            }
        )

        # vs D1
        d1_sel = pd.read_csv(d1_dir / "selector_case_predictions.csv")
        d1s = d1_sel[d1_sel["split"] == split][["pool_id", "selected_correct"]].rename(columns={"selected_correct": "d1_selected_correct"})
        mrg = sub[["pool_id", "selected_correct"]].merge(d1s, on="pool_id", how="inner")
        if len(mrg):
            a2 = mrg["selected_correct"].astype(int).to_numpy()
            b2 = mrg["d1_selected_correct"].astype(int).to_numpy()
            both_correct2 = int(((a2 == 1) & (b2 == 1)).sum())
            d2_only2 = int(((a2 == 1) & (b2 == 0)).sum())
            d1_only2 = int(((a2 == 0) & (b2 == 1)).sum())
            both_wrong2 = int(((a2 == 0) & (b2 == 0)).sum())
            m2 = mcnemar_pvalue(d2_only2, d1_only2)
            mean_d2, lo2, hi2 = bootstrap_ci_diff(a2.astype(float), b2.astype(float), n_boot=3000, seed=43)
            paired_d1_rows.append(
                {
                    "split": split,
                    "both_correct": both_correct2,
                    "d2_only_correct": d2_only2,
                    "d1_only_correct": d1_only2,
                    "both_wrong": both_wrong2,
                    "mcnemar_pvalue": m2,
                    "bootstrap_delta_mean": mean_d2,
                    "bootstrap_delta_ci_low": lo2,
                    "bootstrap_delta_ci_high": hi2,
                }
            )

    paired_base_df = pd.DataFrame(paired_base_rows)
    paired_d1_df = pd.DataFrame(paired_d1_rows)
    paired_base_df.to_csv(out_dir / "paired_statistics_d2_vs_baselines.csv", index=False)
    paired_d1_df.to_csv(out_dir / "paired_statistics_d2_vs_d1.csv", index=False)

    ps_rep = [
        "# Paired Statistics Report",
        "",
        "D2 vs best baseline and D2 vs D1 computed on pool-level paired outcomes.",
    ]
    (out_dir / "paired_statistics_report.md").write_text("\n".join(ps_rep) + "\n")

    # Frontier contribution analysis
    frontier_rows = []
    frontier_missed = []
    frontier_selected_correct = []
    for split in ["test", "seen_dev"]:
        sub = selector_cases_df[selector_cases_df["split"] == split].copy()
        cand_split = cand_rel[masks[split]].copy()
        probs = prob_by_model_split[(best_model, split)]
        cand_split["pred_prob"] = probs
        for (sc, pr, ds), g in sub.groupby(["scenario_id", "provider", "dataset"]):
            pools = set(g["pool_id"])
            pool_rows = cand_split[cand_split["pool_id"].isin(pools)].copy()
            no_front = pool_rows[pool_rows["method"] != "direct_reserve_semantic_frontier_v2"].copy()
            if len(no_front):
                sim_sel, _ = select_by_pool(no_front, no_front["pred_prob"].to_numpy(), method_priority)
                acc_no_front = float(sim_sel["selected_correct"].mean()) if len(sim_sel) else np.nan
            else:
                acc_no_front = np.nan

            uniq_front = pool_rows.groupby("pool_id").apply(
                lambda x: int(
                    ((x["method"] == "direct_reserve_semantic_frontier_v2") & (x["candidate_correct"] == 1)).any()
                    and (x.loc[x["method"] != "direct_reserve_semantic_frontier_v2", "candidate_correct"].sum() == 0)
                )
            ).sum()

            # missed rescue cases: frontier correct but selector not frontier and incorrect
            miss = g[(g["select_frontier_correct"] == 1) & (g["selected_is_frontier"] == 0) & (g["selected_correct"] == 0)].copy()
            if len(miss):
                frontier_missed.append(miss)

            sel_corr = g[(g["selected_is_frontier"] == 1) & (g["selected_correct"] == 1)].copy()
            if len(sel_corr):
                frontier_selected_correct.append(sel_corr)

            frontier_rows.append(
                {
                    "scenario_id": sc,
                    "provider": pr,
                    "dataset": ds,
                    "split": split,
                    "frontier_raw_accuracy": float(g["select_frontier_correct"].mean()),
                    "selector_chooses_frontier_rate": float(g["selected_is_frontier"].mean()),
                    "selector_correct_via_frontier_count": int(((g["selected_is_frontier"] == 1) & (g["selected_correct"] == 1)).sum()),
                    "frontier_unique_correct_count": int(uniq_front),
                    "external_selection_rate": float((g["selected_is_frontier"] == 0).mean()),
                    "correct_selected_frontier": int(((g["selected_method"] == "direct_reserve_semantic_frontier_v2") & (g["selected_correct"] == 1)).sum()),
                    "correct_selected_l1": int(((g["selected_method"] == "external_l1_max") & (g["selected_correct"] == 1)).sum()),
                    "correct_selected_s1": int(((g["selected_method"] == "external_s1_budget_forcing") & (g["selected_correct"] == 1)).sum()),
                    "correct_selected_tale": int(((g["selected_method"] == "external_tale_prompt_budgeting") & (g["selected_correct"] == 1)).sum()),
                    "selector_accuracy_with_frontier": float(g["selected_correct"].mean()),
                    "selector_accuracy_without_frontier_simulated": float(acc_no_front) if pd.notna(acc_no_front) else np.nan,
                    "accuracy_drop_when_frontier_removed": float(g["selected_correct"].mean() - acc_no_front) if pd.notna(acc_no_front) else np.nan,
                }
            )

    frontier_df = pd.DataFrame(frontier_rows)
    frontier_df.to_csv(out_dir / "frontier_contribution_analysis.csv", index=False)
    (out_dir / "frontier_contribution_analysis.md").write_text(md_table(frontier_df, "Frontier Contribution Analysis"))

    if frontier_missed:
        pd.concat(frontier_missed, ignore_index=True).to_csv(out_dir / "frontier_missed_rescue_cases.csv", index=False)
    else:
        pd.DataFrame(columns=selector_cases_df.columns).to_csv(out_dir / "frontier_missed_rescue_cases.csv", index=False)

    if frontier_selected_correct:
        pd.concat(frontier_selected_correct, ignore_index=True).to_csv(out_dir / "frontier_selected_correct_cases.csv", index=False)
    else:
        pd.DataFrame(columns=selector_cases_df.columns).to_csv(out_dir / "frontier_selected_correct_cases.csv", index=False)

    # Failure diagnostics
    false_overrides = selector_cases_df[(selector_cases_df["best_baseline_correct"] == 1) & (selector_cases_df["selected_correct"] == 0)].copy()
    oracle_miss = selector_cases_df[(selector_cases_df["oracle_correct"] == 1) & (selector_cases_df["selected_correct"] == 0)].copy()
    all_wrong_hi = selector_cases_df[(selector_cases_df["oracle_correct"] == 0) & (selector_cases_df["selected_probability"] >= 0.9)].copy()
    false_overrides.to_csv(out_dir / "false_overrides.csv", index=False)
    oracle_miss.to_csv(out_dir / "oracle_available_but_selector_wrong.csv", index=False)
    all_wrong_hi.to_csv(out_dir / "all_sources_wrong_high_confidence.csv", index=False)

    # per-scenario failure diagnostics
    scen_diag = (
        selector_cases_df.groupby(["split", "scenario_id", "provider", "dataset"], as_index=False)
        .agg(
            pools=("pool_id", "count"),
            selector_correct=("selected_correct", "sum"),
            best_baseline_correct=("best_baseline_correct", "sum"),
            both_correct=("selected_correct", lambda x: int(((x == 1)).sum())),
            frontier_selection_rate=("selected_is_frontier", "mean"),
            external_selection_rate=("selected_is_external", "mean"),
            oracle_available_but_selector_missed=("oracle_correct", lambda x: int((x == 1).sum())),
            all_sources_wrong=("all_sources_wrong", "sum"),
        )
    )
    (out_dir / "per_scenario_failure_diagnostics.md").write_text(md_table(scen_diag, "Per Scenario Failure Diagnostics"))

    # scenario loss diagnosis
    loss_diag_lines = ["# Scenario Loss Diagnosis", ""]
    losses = comp_df[comp_df["result"] == "loss"] if len(comp_df) else pd.DataFrame()
    for _, r in losses.iterrows():
        scenario = r["scenario_id"]
        split = r["split"]
        sub = selector_cases_df[(selector_cases_df["scenario_id"] == scenario) & (selector_cases_df["split"] == split)]
        if sub.empty:
            continue
        all_wrong_rate = float(sub["all_sources_wrong"].mean())
        frontier_under = float(((sub["select_frontier_correct"] == 1) & (sub["selected_is_frontier"] == 0)).mean())
        if all_wrong_rate > 0.35:
            mode = "low oracle ceiling / all-sources-wrong"
            fix = "new provider generation or frontier improvement"
        elif frontier_under > 0.1:
            mode = "undertrusts frontier"
            fix = "frontier-aware ranking objective and frontier rescue features"
        else:
            mode = "feature ranking mismatch"
            fix = "D3 ranking/LambdaMART or D4 two-stage oracle head"
        loss_diag_lines.append(f"- {split} {scenario}: mode={mode}; recommended_fix={fix}")
    if len(losses) == 0:
        loss_diag_lines.append("- No losing scenarios in reported splits.")
    (out_dir / "scenario_loss_diagnosis.md").write_text("\n".join(loss_diag_lines) + "\n")

    # Leave-one diagnostics with backoff report
    backoff_lines = [
        "# Leave-One Backoff Report",
        "",
        "Leave-one evaluations use train-group-only mappings with backoff to dataset/method/global.",
        "Held-out groups use only statistics from non-held-out clean rows.",
    ]

    def run_leave_one(group_col: str, out_name: str) -> pd.DataFrame:
        clean = cand_rel[cand_rel["split"].isin(["train", "validation", "test"])].copy()
        groups = sorted(clean[group_col].dropna().unique().tolist())
        rows = []
        for g in groups:
            train_sub = clean[clean[group_col] != g].copy()
            test_sub = clean[clean[group_col] == g].copy()
            if len(train_sub) == 0 or len(test_sub) == 0:
                continue

            # recompute reliability from train_sub only
            tr_only = train_sub[train_sub["split"] == "train"].copy()
            if tr_only.empty:
                rows.append({group_col: g, "n_pools": int(test_sub["pool_id"].nunique()), "learned_accuracy": np.nan, "best_baseline_accuracy": np.nan, "delta_vs_best_baseline": np.nan, "note": "no_train_rows"})
                continue

            tr_oof, _ = build_oof_reliability(tr_only, n_splits=min(5, max(2, tr_only["pool_id"].nunique() // 200 + 2)), alpha=args.alpha)
            # For model train/eval in leave-one, apply train-only mappings to all subsets
            tr_feat, _ = build_reliability_from_train(tr_only, train_sub, alpha=args.alpha)
            te_feat, _ = build_reliability_from_train(tr_only, test_sub, alpha=args.alpha)

            X_tr_df, _, _, _ = prepare_features(tr_feat, allowlist, forbidden, rel_cols)
            X_te_df, _, _, _ = prepare_features(te_feat, allowlist, forbidden, rel_cols)
            mats, _, _ = fit_transformer(X_tr_df, {"train": X_tr_df, "test": X_te_df})

            y_tr = tr_feat["candidate_correct"].astype(int).to_numpy()
            if len(np.unique(y_tr)) < 2:
                rows.append({group_col: g, "n_pools": int(test_sub["pool_id"].nunique()), "learned_accuracy": np.nan, "best_baseline_accuracy": np.nan, "delta_vs_best_baseline": np.nan, "note": "single_class_train"})
                continue

            # train best model family with selected params
            best_spec = next((s for s in specs if s.name == best_model), specs[0])
            est = train_model_by_spec(best_spec, mats["train"], y_tr)
            p = predict_prob(est, mats["test"])
            sel, _ = select_by_pool(te_feat, p, method_priority)

            b = baseline[baseline["pool_id"].isin(sel["pool_id"])].copy()
            if len(b):
                cols = available_fixed_policy_baseline_cols(b)
                _, best_base = best_fixed_policy_for_group(b, cols)
            else:
                best_base = np.nan
            lacc = sel["selected_correct"].mean() if len(sel) else np.nan
            rows.append({group_col: g, "n_pools": int(sel["pool_id"].nunique()), "learned_accuracy": float(lacc), "best_baseline_accuracy": float(best_base), "delta_vs_best_baseline": float(lacc - best_base) if pd.notna(best_base) else np.nan, "note": "ok"})
        df = pd.DataFrame(rows)
        df.to_csv(out_dir / out_name, index=False)
        return df

    loso = run_leave_one("scenario_id", "leave_one_scenario_out_results.csv")
    lopo = run_leave_one("provider", "leave_one_provider_out_results.csv")
    lodo = run_leave_one("dataset", "leave_one_dataset_out_results.csv")
    (out_dir / "leave_one_backoff_report.md").write_text("\n".join(backoff_lines) + "\n")

    # Feature importance
    fi_rows = []
    best_est = fit_models[best_model]
    if hasattr(best_est, "feature_importances_"):
        imp = np.asarray(best_est.feature_importances_)
        for f, v in zip(transformed_feature_names, imp):
            fi_rows.append({"model": best_model, "feature": f, "importance": float(v), "source": "feature_importances_"})
    if "logistic_regression" in fit_models and hasattr(fit_models["logistic_regression"], "coef_"):
        coef = np.asarray(fit_models["logistic_regression"].coef_).reshape(-1)
        for f, v in zip(transformed_feature_names, coef):
            fi_rows.append({"model": "logistic_regression", "feature": f, "importance": float(v), "source": "coefficient"})
    pd.DataFrame(fi_rows).to_csv(out_dir / "feature_importance.csv", index=False)

    # Promotion decision
    test_comp = comp_df[comp_df["split"] == "test"].copy()
    seen_comp = comp_df[comp_df["split"] == "seen_dev"].copy()
    clean_all_tie_or_win = bool((test_comp["delta_vs_best_baseline"] >= 0).all()) if len(test_comp) else False
    seen_math_improved = bool((d1d2[(d1d2["split"] == "seen_dev") & (d1d2["dataset"] == "math500")]["d2_minus_d1"] > 0).any()) if len(d1d2) else False
    d2_better_than_d1 = bool((d1d2["d2_minus_d1"].mean() > 0)) if len(d1d2) else False

    biggest_losses = []
    if len(test_comp):
        for _, r in test_comp.sort_values("delta_vs_best_baseline").head(3).iterrows():
            biggest_losses.append(f"{r['split']}:{r['scenario_id']}:{r['delta_vs_best_baseline']:.4f}")
    if len(seen_comp):
        for _, r in seen_comp.sort_values("delta_vs_best_baseline").head(3).iterrows():
            biggest_losses.append(f"{r['split']}:{r['scenario_id']}:{r['delta_vs_best_baseline']:.4f}")

    next_action = "B. D3 ranking/LambdaMART"
    if clean_all_tie_or_win and d2_better_than_d1:
        next_action = "Promote D2 and run confirmation holdout"

    prom_lines = [
        "# Promotion Decision",
        "",
        f"Best validation model: `{best_model}`",
        f"D2 best/tied-best in all clean test scenarios: {'Yes' if clean_all_tie_or_win else 'No'}",
        f"D2 better than D1 overall: {'Yes' if d2_better_than_d1 else 'No'}",
        f"D2 improves MATH-500 seen-dev in at least one scenario: {'Yes' if seen_math_improved else 'No'}",
        "",
        "Main losses:",
    ]
    if biggest_losses:
        prom_lines.extend([f"- {x}" for x in biggest_losses])
    else:
        prom_lines.append("- none")
    prom_lines.extend(
        [
            "",
            f"Promotable as current best learned selector: {'Yes' if clean_all_tie_or_win and d2_better_than_d1 else 'No'}",
            f"Next recommended action: {next_action}",
            "",
            "Option decision: B (D3 ranking/LambdaMART) if not promotable.",
        ]
    )
    (out_dir / "promotion_decision.md").write_text("\n".join(prom_lines) + "\n")

    # ledger update
    clean_w = int((test_comp["result"] == "win").sum()) if len(test_comp) else 0
    clean_t = int((test_comp["result"] == "tie").sum()) if len(test_comp) else 0
    clean_l = int((test_comp["result"] == "loss").sum()) if len(test_comp) else 0
    seen_w = int((seen_comp["result"] == "win").sum()) if len(seen_comp) else 0
    seen_t = int((seen_comp["result"] == "tie").sum()) if len(seen_comp) else 0
    seen_l = int((seen_comp["result"] == "loss").sum()) if len(seen_comp) else 0

    d2_summary = {
        "model_families_tried": ",".join(sorted({s.name for s in specs})),
        "feature_groups_used": "base_allowlist+fold_safe_reliability+complementarity",
        "gpu_used": any(r["gpu_used"] for r in model_rows),
        "clean_wtl": f"{clean_w}/{clean_t}/{clean_l}",
        "seen_wtl": f"{seen_w}/{seen_t}/{seen_l}",
        "macro_accuracy_test": float(overall_df[(overall_df['model'] == best_model) & (overall_df['split'] == 'test')]['macro_scenario_accuracy'].iloc[0]) if len(overall_df[(overall_df['model'] == best_model) & (overall_df['split'] == 'test')]) else np.nan,
        "worst_accuracy_test": float(overall_df[(overall_df['model'] == best_model) & (overall_df['split'] == 'test')]['worst_scenario_accuracy'].iloc[0]) if len(overall_df[(overall_df['model'] == best_model) & (overall_df['split'] == 'test')]) else np.nan,
        "biggest_losses": "; ".join(biggest_losses),
        "promotion_decision": "promotable" if clean_all_tie_or_win and d2_better_than_d1 else "not_promotable",
        "next_action": next_action,
    }
    update_training_ledger(Path(args.ledger_root), d1_dir, out_dir, d2_summary)

    # main report
    rep_lines = [
        "# JOB_D2_RELIABILITY_SELECTOR_REPORT_20260525",
        "",
        f"Input: `{in_dir}`",
        f"D1 reference: `{d1_dir}`",
        f"Output: `{out_dir}`",
        "",
        f"Best D2 model: `{best_model}`",
        f"Clean test wins/ties/losses: {clean_w}/{clean_t}/{clean_l}",
        f"Seen-dev wins/ties/losses: {seen_w}/{seen_t}/{seen_l}",
        f"Next action: {next_action}",
    ]
    (out_dir / "JOB_D2_RELIABILITY_SELECTOR_REPORT_20260525.md").write_text("\n".join(rep_lines) + "\n")

    # manifests
    manifest = {
        "generated_at": now_utc(),
        "input_dir": str(in_dir),
        "d1_run": str(d1_dir),
        "output_dir": str(out_dir),
        "rows": {
            "candidate_rows": int(len(cand_rel)),
            "pool_rows": int(cand_rel["pool_id"].nunique()),
            "split_counts": cand_rel["split"].value_counts().to_dict(),
        },
        "best_model": best_model,
        "feature_meta": feat_meta,
        "transform_meta": transform_meta,
        "reliability_feature_count": len(rel_cols),
        "model_availability": pkg_availability,
        "gpu_available": gpu_available,
        "gpu_used_models": [r["model"] for r in model_rows if r["gpu_used"]],
        "models_trained": sorted(set(overall_df["model"].tolist())),
    }
    (out_dir / "training_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (out_dir / "job_d2_training_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

    print(json.dumps({
        "output_dir": str(out_dir),
        "best_model": best_model,
        "clean_wtl": f"{clean_w}/{clean_t}/{clean_l}",
        "seen_wtl": f"{seen_w}/{seen_t}/{seen_l}",
        "next_action": next_action,
    }, indent=2))


if __name__ == "__main__":
    main()
