#!/usr/bin/env python3
"""Job D4: pool-level ranking selector (LambdaMART / LTR style).

Offline-only, no API calls.
"""

from __future__ import annotations

import argparse
import importlib.util
import itertools
import json
import math
import subprocess
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
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


def safe_float(x: Any, default: float = 0.0) -> float:
    try:
        if pd.isna(x):
            return default
        return float(x)
    except Exception:
        return default


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


def canonical_method_rank(method: str) -> int:
    order = {
        METHOD_ID_BY_ALIAS["frontier"]: 0,
        METHOD_ID_BY_ALIAS["s1"]: 1,
        METHOD_ID_BY_ALIAS["l1"]: 2,
        METHOD_ID_BY_ALIAS["tale"]: 3,
    }
    return order.get(method, 99)


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


def create_environment_reports(run_dir: Path) -> tuple[pd.DataFrame, bool]:
    pkg_rows = []
    for p in ["sklearn", "xgboost", "lightgbm", "catboost", "optuna", "shap"]:
        pkg_rows.append({"package": p, "available": bool(has_pkg(p))})
    p_df = pd.DataFrame(pkg_rows)
    p_df.to_csv(run_dir / "package_availability_report.csv", index=False)
    (run_dir / "package_availability_report.md").write_text(md_table(p_df, "Package Availability"))

    gpu_raw = run_command("nvidia-smi || true")
    gpu_available = "NVIDIA-SMI" in gpu_raw
    (run_dir / "gpu_availability_report.md").write_text("# GPU Availability\n\n```\n" + gpu_raw + "```\n")

    env_lines = [
        "# Environment Report",
        "",
        f"Generated at: {now_utc()}",
        "",
        "```",
        run_command("pwd")
        + run_command("date")
        + run_command("git status --short")
        + run_command("git branch -vv")
        + run_command("git log --oneline -10")
        + run_command("tmux ls || true")
        + run_command("python3 -V")
        + run_command("which python3")
        + gpu_raw,
        "```",
    ]
    (run_dir / "environment_report.md").write_text("\n".join(env_lines) + "\n")

    return p_df, gpu_available


def add_fold_safe_reliability(cand: pd.DataFrame, alpha: float = 15.0) -> tuple[pd.DataFrame, list[str], pd.DataFrame, str]:
    df = cand.copy()
    df["answer_type"] = derive_answer_type(df)
    df["candidate_correct"] = df["candidate_correct"].astype(int)
    pool_correct = df.groupby("pool_id")["candidate_correct"].transform("sum")
    df["oracle_available"] = (pool_correct > 0).astype(int)
    df["all_sources_wrong"] = (pool_correct == 0).astype(int)
    df["unique_correct_flag"] = ((pool_correct == 1) & (df["candidate_correct"] == 1)).astype(int)

    train = df[df["split"] == "train"].copy()
    if len(train) == 0:
        rel_cols = []
        support_df = pd.DataFrame()
        return df, rel_cols, support_df, "No train rows; reliability features defaulted to 0.5"

    def build_from_train(train_rows: pd.DataFrame, apply_rows: pd.DataFrame) -> pd.DataFrame:
        tr = train_rows.copy()
        ap = apply_rows.copy()

        global_rate = float(tr["candidate_correct"].mean()) if len(tr) else 0.5
        global_oracle = float(tr.drop_duplicates("pool_id")["oracle_available"].mean()) if len(tr) else 0.5
        global_allwrong = float(tr.drop_duplicates("pool_id")["all_sources_wrong"].mean()) if len(tr) else 0.5

        m_method = make_rate_map(tr, ["method"], "candidate_correct", alpha, global_rate)
        m_provider_method = make_rate_map(tr, ["provider", "method"], "candidate_correct", alpha, global_rate)
        m_dataset_method = make_rate_map(tr, ["dataset", "method"], "candidate_correct", alpha, global_rate)
        m_provider_dataset_method = make_rate_map(tr, ["provider", "dataset", "method"], "candidate_correct", alpha, global_rate)
        m_dataset_answer_type_method = make_rate_map(tr, ["dataset", "answer_type", "method"], "candidate_correct", alpha, global_rate)
        m_subject_method = make_rate_map(tr, ["math_subject", "method"], "candidate_correct", alpha, global_rate)
        m_level_method = make_rate_map(tr, ["math_level", "method"], "candidate_correct", alpha, global_rate)

        for ncol in ["cluster_size", "max_cluster_size", "candidate_is_isolated_flag"]:
            if ncol not in tr.columns:
                tr[ncol] = 0
                ap[ncol] = 0

        tr["cluster_size_bin"] = tr["cluster_size"].fillna(0).astype(float).round(0).clip(0, 10)
        ap["cluster_size_bin"] = ap["cluster_size"].fillna(0).astype(float).round(0).clip(0, 10)
        tr["max_cluster_size_bin"] = tr["max_cluster_size"].fillna(0).astype(float).round(0).clip(0, 10)
        ap["max_cluster_size_bin"] = ap["max_cluster_size"].fillna(0).astype(float).round(0).clip(0, 10)

        m_cluster = make_rate_map(tr, ["cluster_size_bin"], "candidate_correct", alpha, global_rate)
        m_max_cluster = make_rate_map(tr, ["max_cluster_size_bin"], "candidate_correct", alpha, global_rate)
        m_isolated = make_rate_map(tr, ["candidate_is_isolated_flag"], "candidate_correct", alpha, global_rate)

        pool_uni = tr[["pool_id", "provider", "dataset", "oracle_available", "all_sources_wrong"]].drop_duplicates("pool_id")
        m_provider_dataset_oracle = make_rate_map(pool_uni, ["provider", "dataset"], "oracle_available", alpha, global_oracle)
        m_provider_dataset_allwrong = make_rate_map(pool_uni, ["provider", "dataset"], "all_sources_wrong", alpha, global_allwrong)

        m_unique = make_rate_map(tr, ["method"], "unique_correct_flag", alpha, float(tr["unique_correct_flag"].mean()))

        pair_cols = ["agrees_with_frontier", "agrees_with_l1", "agrees_with_s1", "agrees_with_tale"]
        pair_maps = {}
        for pc in pair_cols:
            if pc in tr.columns:
                pair_maps[pc] = make_rate_map(tr, ["method", pc], "candidate_correct", alpha, global_rate)

        out = ap.copy()

        rel = out.apply(
            lambda r: pd.Series(lookup_backoff(r, [(["provider", "dataset", "method"], m_provider_dataset_method, "provider_dataset_method"), (["dataset", "method"], m_dataset_method, "dataset_method"), (["provider", "method"], m_provider_method, "provider_method"), (["method"], m_method, "method")], global_rate)),
            axis=1,
        )
        rel.columns = ["rel_method_acc_trainfold", "rel_method_support", "rel_method_backoff"]
        out = pd.concat([out, rel], axis=1)

        rel_da = out.apply(
            lambda r: pd.Series(lookup_backoff(r, [(["dataset", "answer_type", "method"], m_dataset_answer_type_method, "dataset_answer_type_method"), (["dataset", "method"], m_dataset_method, "dataset_method"), (["method"], m_method, "method")], global_rate)),
            axis=1,
        )
        rel_da.columns = ["rel_dataset_answer_type_method_acc_trainfold", "rel_dataset_answer_type_method_support", "rel_dataset_answer_type_method_backoff"]
        out = pd.concat([out, rel_da], axis=1)

        out[["rel_math_subject_method_acc_trainfold", "rel_math_subject_method_support", "rel_math_subject_method_backoff"]] = out.apply(
            lambda r: pd.Series(lookup_backoff(r, [(["math_subject", "method"], m_subject_method, "subject_method"), (["method"], m_method, "method")], global_rate)),
            axis=1,
        )
        out[["rel_math_level_method_acc_trainfold", "rel_math_level_method_support", "rel_math_level_method_backoff"]] = out.apply(
            lambda r: pd.Series(lookup_backoff(r, [(["math_level", "method"], m_level_method, "level_method"), (["method"], m_method, "method")], global_rate)),
            axis=1,
        )

        out[["rel_cluster_size_correct_rate_trainfold", "rel_cluster_size_support", "rel_cluster_size_backoff"]] = out.apply(
            lambda r: pd.Series(lookup_backoff(r, [(["cluster_size_bin"], m_cluster, "cluster_size")], global_rate)), axis=1
        )
        out[["rel_max_cluster_size_correct_rate_trainfold", "rel_max_cluster_size_support", "rel_max_cluster_size_backoff"]] = out.apply(
            lambda r: pd.Series(lookup_backoff(r, [(["max_cluster_size_bin"], m_max_cluster, "max_cluster_size")], global_rate)), axis=1
        )
        out[["rel_candidate_isolated_correct_rate_trainfold", "rel_candidate_isolated_support", "rel_candidate_isolated_backoff"]] = out.apply(
            lambda r: pd.Series(lookup_backoff(r, [(["candidate_is_isolated_flag"], m_isolated, "isolated")], global_rate)), axis=1
        )

        out[["rel_provider_dataset_oracle_rate_trainfold", "rel_provider_dataset_oracle_support", "rel_provider_dataset_oracle_backoff"]] = out.apply(
            lambda r: pd.Series(lookup_backoff(r, [(["provider", "dataset"], m_provider_dataset_oracle, "provider_dataset")], global_oracle)), axis=1
        )
        out[["rel_provider_dataset_all_wrong_rate_trainfold", "rel_provider_dataset_all_wrong_support", "rel_provider_dataset_all_wrong_backoff"]] = out.apply(
            lambda r: pd.Series(lookup_backoff(r, [(["provider", "dataset"], m_provider_dataset_allwrong, "provider_dataset")], global_allwrong)), axis=1
        )

        out[["rel_method_unique_correct_rate_trainfold", "rel_method_unique_correct_support", "rel_method_unique_correct_backoff"]] = out.apply(
            lambda r: pd.Series(lookup_backoff(r, [(["method"], m_unique, "method")], float(tr["unique_correct_flag"].mean()))), axis=1
        )

        for pc in pair_cols:
            if pc not in out.columns or pc not in pair_maps:
                continue
            rr = out.apply(
                lambda r, _pc=pc: pd.Series(lookup_backoff(r, [(["method", _pc], pair_maps[_pc], f"method_{_pc}"), (["method"], m_method, "method")], global_rate)),
                axis=1,
            )
            rr.columns = [f"rel_{pc}_correct_rate_trainfold", f"rel_{pc}_support", f"rel_{pc}_backoff"]
            out = pd.concat([out, rr], axis=1)

        return out

    train_groups = train["pool_id"].astype(str).to_numpy()
    n_groups = train["pool_id"].nunique()
    n_splits = min(5, max(2, n_groups // 200 + 2))
    gkf = GroupKFold(n_splits=n_splits)

    oof_parts = []
    for tr_idx, va_idx in gkf.split(train, train["candidate_correct"].astype(int), groups=train_groups):
        tr = train.iloc[tr_idx].copy()
        va = train.iloc[va_idx].copy()
        oof_parts.append(build_from_train(tr, va))
    train_oof = pd.concat(oof_parts, axis=0).sort_index()

    val = df[df["split"] == "validation"].copy()
    test = df[df["split"] == "test"].copy()
    seen = df[df["split"] == "seen_dev"].copy()

    val_feat = build_from_train(train, val) if len(val) else val
    test_feat = build_from_train(train, test) if len(test) else test
    seen_feat = build_from_train(train, seen) if len(seen) else seen

    merged = pd.concat([train_oof, val_feat, test_feat, seen_feat], axis=0).sort_index()
    out = df.copy()
    add_cols = [c for c in merged.columns if c.startswith("rel_")]
    for c in add_cols:
        out[c] = merged[c]

    support_cols = [c for c in add_cols if c.endswith("_support")]
    support_df = pd.DataFrame()
    if support_cols:
        vals = []
        for c in support_cols:
            v = out[c].fillna(0).astype(float)
            vals.append({"support_column": c, "mean": float(v.mean()), "median": float(v.median()), "min": float(v.min()), "max": float(v.max())})
        support_df = pd.DataFrame(vals).sort_values("support_column")

    rel_cols = sorted([c for c in add_cols if c.endswith("_trainfold")])
    report = "\n".join(
        [
            "# D4 Reliability Feature Report",
            "",
            f"- Reliability feature count: {len(rel_cols)}",
            "- Train rows: out-of-fold GroupKFold by pool_id",
            "- Validation/test/seen_dev: train-only reliability maps",
            "- Backoff chain: provider_dataset_method -> dataset_method -> provider_method -> method -> global",
        ]
    ) + "\n"
    return out, rel_cols, support_df, report


def build_feature_columns(cand: pd.DataFrame, allowlist_file: Path, forbidden_file: Path, extra_forbidden: list[str]) -> tuple[list[str], list[str], list[str]]:
    allow = []
    if allowlist_file.exists():
        allow = [ln.strip() for ln in allowlist_file.read_text().splitlines() if ln.strip()]
    forbid = set(extra_forbidden)
    if forbidden_file.exists():
        forbid |= {ln.strip() for ln in forbidden_file.read_text().splitlines() if ln.strip()}

    more_forbidden = {
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
    forbid |= more_forbidden

    # start from allowlist + reliable identifiers used for model context
    preferred = list(dict.fromkeys(allow + ["method", "provider", "dataset", "scenario_id", "math_subject", "math_level"]))
    used = []
    rejected = []
    leakage_hits = []
    for c in preferred:
        if c not in cand.columns:
            rejected.append(f"{c}\tmissing")
            continue
        if c in forbid:
            leakage_hits.append(c)
            rejected.append(f"{c}\tforbidden")
            continue
        if c in {"question_text", "raw_output_text", "error_text", "result_metadata_json", "source_artifact_path"}:
            rejected.append(f"{c}\thigh_cardinality_text")
            continue
        used.append(c)

    # add fold-safe reliability columns
    for c in sorted([c for c in cand.columns if c.startswith("rel_") and c.endswith("_trainfold")]):
        if c not in forbid:
            used.append(c)

    used = sorted(set(used))
    if leakage_hits:
        raise RuntimeError(f"Leakage columns present in features: {sorted(set(leakage_hits))}")

    return used, sorted(set(rejected)), sorted(forbid)


def encode_features(df: pd.DataFrame, feature_cols: list[str], category_maps: dict[str, list[Any]] | None = None) -> tuple[pd.DataFrame, dict[str, list[Any]]]:
    X = pd.DataFrame(index=df.index)
    maps = {} if category_maps is None else {k: list(v) for k, v in category_maps.items()}
    for c in feature_cols:
        if c not in df.columns:
            X[c] = 0.0
            continue
        s = df[c]
        if pd.api.types.is_numeric_dtype(s):
            X[c] = pd.to_numeric(s, errors="coerce").fillna(0.0).astype(float)
        else:
            if category_maps is None:
                cats = sorted(set(clean_text(v) for v in s.fillna("")))
                maps[c] = cats
            cats = maps.get(c, [])
            code_map = {v: i for i, v in enumerate(cats)}
            X[c] = s.fillna("").map(lambda v: float(code_map.get(clean_text(v), -1))).astype(float)
    return X, maps


def build_group_sizes(df: pd.DataFrame) -> list[int]:
    return df.groupby("pool_id", sort=False).size().astype(int).tolist()


def select_top_per_pool(df: pd.DataFrame, score_col: str, rel_col: str = "rel_method_acc_trainfold") -> tuple[pd.DataFrame, pd.DataFrame]:
    tmp = df.copy()
    tmp["_method_rank"] = tmp["method"].map(canonical_method_rank).fillna(99).astype(int)
    tmp["_rel"] = pd.to_numeric(tmp.get(rel_col, 0.5), errors="coerce").fillna(0.5)
    tmp["_cluster"] = pd.to_numeric(tmp.get("cluster_size", 0), errors="coerce").fillna(0.0)
    tmp["_score"] = pd.to_numeric(tmp[score_col], errors="coerce").fillna(-1e9)

    tie_rows = []
    sel_rows = []
    for pid, g in tmp.groupby("pool_id", sort=False):
        g2 = g.sort_values(["_score", "_cluster", "_rel", "_method_rank"], ascending=[False, False, False, True])
        top = g2.iloc[0]
        same_score = g[g["_score"] == top["_score"]]
        tie_rows.append(
            {
                "pool_id": pid,
                "split": clean_text(top.get("split", "")),
                "scenario_id": clean_text(top.get("scenario_id", "")),
                "tie_count_same_score": int(len(same_score)),
                "top_score": float(top["_score"]),
            }
        )
        sel_rows.append(
            {
                "pool_id": pid,
                "split": clean_text(top.get("split", "")),
                "scenario_id": clean_text(top.get("scenario_id", "")),
                "provider": clean_text(top.get("provider", "")),
                "dataset": clean_text(top.get("dataset", "")),
                "selected_method": clean_text(top.get("method", "")),
                "selected_method_alias": METHOD_ALIAS_BY_ID.get(clean_text(top.get("method", "")), clean_text(top.get("method", ""))),
                "selected_correct": int(top.get("candidate_correct", 0)),
                "selected_score": float(top["_score"]),
                "selected_is_frontier": int(clean_text(top.get("method", "")) == METHOD_ID_BY_ALIAS["frontier"]),
                "selected_is_external": int(clean_text(top.get("method", "")) != METHOD_ID_BY_ALIAS["frontier"]),
            }
        )

    return pd.DataFrame(sel_rows), pd.DataFrame(tie_rows)


def ndcg1_from_selection(sel_df: pd.DataFrame) -> float:
    if len(sel_df) == 0:
        return float("nan")
    return float(sel_df["selected_correct"].astype(int).mean())


def prepare_baseline_by_scenario(corr_pool: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for scen, g in corr_pool.groupby("scenario_id", dropna=False):
        src = g[g["split"] == "validation"]
        if len(src) == 0:
            src = g[g["split"] == "train"]
        if len(src) == 0:
            src = g
        best_policy = "select_frontier_correct"
        best_acc = float("nan")
        vals = {}
        for p in VALID_BASELINE_POLICIES:
            if p in src.columns:
                vals[p] = float(src[p].mean())
        if vals:
            best_acc = max(vals.values())
            best_policy = sorted([k for k, v in vals.items() if np.isclose(v, best_acc)])[0]
        rows.append(
            {
                "scenario_id": clean_text(scen),
                "provider": clean_text(g["provider"].iloc[0]) if len(g) else "",
                "dataset": clean_text(g["dataset"].iloc[0]) if len(g) else "",
                "default_policy": best_policy,
                "validation_best_acc": best_acc,
            }
        )
    return pd.DataFrame(rows)


def add_best_baseline_flags(sel_df: pd.DataFrame, corr_pool: pd.DataFrame, by_scenario_policy: pd.DataFrame) -> pd.DataFrame:
    out = sel_df.copy()
    base = corr_pool.copy()
    keep_cols = [
        "pool_id",
        "scenario_id",
        "split",
        "provider",
        "dataset",
        "select_frontier_correct",
        "select_l1_correct",
        "select_s1_correct",
        "select_tale_correct",
        "pooled4_plurality_correct",
        "agreement_largest_cluster_correct",
        "agreement_strict_2plus_correct",
        "oracle_correct",
        "pooled4_plurality_selected_method",
        "agreement_largest_cluster_selected_method",
        "agreement_strict_2plus_selected_method",
    ]
    keep_cols = [c for c in keep_cols if c in base.columns]
    base = base[keep_cols].drop_duplicates("pool_id")
    out = out.merge(base, on="pool_id", how="left", suffixes=("", "_base"))

    policy_map = {clean_text(r["scenario_id"]): clean_text(r["default_policy"]) for _, r in by_scenario_policy.iterrows()}
    best_name = []
    best_corr = []
    default_method = []
    for _, r in out.iterrows():
        scen = clean_text(r.get("scenario_id", ""))
        pol = policy_map.get(scen, "select_frontier_correct")
        best_name.append(pol)
        if pol in out.columns:
            best_corr.append(int(r.get(pol, 0)))
        else:
            best_corr.append(int(r.get("select_frontier_correct", 0)))

        mth, _ = policy_to_method_and_correct(r, pol)
        default_method.append(mth)

    out["best_fixed_baseline_name"] = best_name
    out["best_fixed_baseline_correct"] = best_corr
    out["default_baseline_method"] = default_method
    out["delta_vs_best_baseline"] = out["selected_correct"].astype(int) - out["best_fixed_baseline_correct"].astype(int)
    out["result_vs_corrected_best_baseline"] = out["delta_vs_best_baseline"].map(lambda d: "win" if d > 0 else ("tie" if d == 0 else "loss"))
    return out


def summary_by_scenario(sel_df: pd.DataFrame, d1: pd.DataFrame, d2: pd.DataFrame, d3: pd.DataFrame) -> pd.DataFrame:
    d1p = d1.drop_duplicates("pool_id")[["pool_id", "selected_correct"]].rename(columns={"selected_correct": "d1_correct"})
    d2p = d2.drop_duplicates("pool_id")[["pool_id", "selected_correct"]].rename(columns={"selected_correct": "d2_correct"})
    d3p = d3.drop_duplicates("pool_id")[["pool_id", "selected_correct"]].rename(columns={"selected_correct": "d3_correct"})

    m = sel_df.merge(d1p, on="pool_id", how="left").merge(d2p, on="pool_id", how="left").merge(d3p, on="pool_id", how="left")
    m[["d1_correct", "d2_correct", "d3_correct"]] = m[["d1_correct", "d2_correct", "d3_correct"]].fillna(0).astype(int)
    m["best_previous_correct"] = m[["d1_correct", "d2_correct", "d3_correct"]].max(axis=1)

    rows = []
    for (sp, scen, prov, dset), g in m.groupby(["split", "scenario_id", "provider", "dataset"], dropna=False):
        d4_acc = float(g["selected_correct"].mean())
        base_acc = float(g["best_fixed_baseline_correct"].mean())
        d1_acc = float(g["d1_correct"].mean())
        d2_acc = float(g["d2_correct"].mean())
        d3_acc = float(g["d3_correct"].mean())
        best_prev_acc = float(g["best_previous_correct"].mean())
        oracle = float(g["oracle_correct"].mean()) if "oracle_correct" in g.columns else float("nan")
        base_names = sorted(set(clean_text(x) for x in g["best_fixed_baseline_name"].dropna().tolist()))
        rows.append(
            {
                "split": clean_text(sp),
                "scenario_id": clean_text(scen),
                "provider": clean_text(prov),
                "dataset": clean_text(dset),
                "pools": int(g["pool_id"].nunique()),
                "best_fixed_baseline": ";".join(base_names),
                "baseline_acc": base_acc,
                "d1_acc": d1_acc,
                "d2_acc": d2_acc,
                "d3_acc": d3_acc,
                "best_previous_acc": best_prev_acc,
                "d4_acc": d4_acc,
                "d4_minus_d2": d4_acc - d2_acc,
                "d4_minus_d3": d4_acc - d3_acc,
                "d4_minus_best_previous": d4_acc - best_prev_acc,
                "d4_minus_baseline": d4_acc - base_acc,
                "oracle": oracle,
                "result_vs_corrected_baseline": "win" if d4_acc > base_acc else ("tie" if np.isclose(d4_acc, base_acc) else "loss"),
                "result_vs_best_previous": "win" if d4_acc > best_prev_acc else ("tie" if np.isclose(d4_acc, best_prev_acc) else "loss"),
                "selected_frontier_rate": float((g["selected_method"] == METHOD_ID_BY_ALIAS["frontier"]).mean()),
            }
        )
    return pd.DataFrame(rows).sort_values(["split", "scenario_id"]).reset_index(drop=True)


def paired_stats(sel_df: pd.DataFrame, comparator_col: str, label: str) -> pd.DataFrame:
    rows = []
    for (sp, scen), g in sel_df.groupby(["split", "scenario_id"], dropna=False):
        a = g["selected_correct"].astype(int).to_numpy()
        b = g[comparator_col].astype(int).to_numpy()
        d4_only = int(((a == 1) & (b == 0)).sum())
        cmp_only = int(((a == 0) & (b == 1)).sum())
        both = int(((a == 1) & (b == 1)).sum())
        neither = int(((a == 0) & (b == 0)).sum())
        p = mcnemar_pvalue(d4_only, cmp_only)
        delta_mean, ci_lo, ci_hi = bootstrap_ci_diff(a.astype(float), b.astype(float), n_boot=2000, seed=42)
        rows.append(
            {
                "split": clean_text(sp),
                "scenario_id": clean_text(scen),
                "n_pools": int(len(g)),
                "d4_accuracy": float(a.mean()) if len(a) else float("nan"),
                f"{label}_accuracy": float(b.mean()) if len(b) else float("nan"),
                "d4_only_correct": d4_only,
                f"{label}_only_correct": cmp_only,
                "both_correct": both,
                "both_wrong": neither,
                "mcnemar_pvalue": p,
                "bootstrap_delta_mean": delta_mean,
                "bootstrap_ci95_lo": ci_lo,
                "bootstrap_ci95_hi": ci_hi,
            }
        )
    return pd.DataFrame(rows).sort_values(["split", "scenario_id"]).reset_index(drop=True)


def choose_best_variant_on_validation(variants: dict[str, pd.DataFrame]) -> str:
    best_name = ""
    best_acc = -1.0
    for name, df in variants.items():
        v = df[df["split"] == "validation"]
        if len(v) == 0:
            continue
        acc = float(v["selected_correct"].mean())
        if acc > best_acc:
            best_acc = acc
            best_name = name
    return best_name or sorted(variants.keys())[0]


def train_lgbm_ranker(
    X_tr: pd.DataFrame,
    y_tr: np.ndarray,
    group_tr: list[int],
    X_va: pd.DataFrame,
    y_va: np.ndarray,
    group_va: list[int],
    params: dict[str, Any],
) -> tuple[Any, bool, str]:
    try:
        import lightgbm as lgb

        mdl = lgb.LGBMRanker(
            objective="lambdarank",
            metric="ndcg",
            eval_at=[1],
            n_estimators=int(params.get("n_estimators", 300)),
            learning_rate=float(params.get("learning_rate", 0.05)),
            num_leaves=int(params.get("num_leaves", 31)),
            min_child_samples=int(params.get("min_child_samples", 20)),
            subsample=float(params.get("subsample", 0.9)),
            colsample_bytree=float(params.get("colsample_bytree", 0.9)),
            random_state=42,
            device_type=params.get("device_type", "cpu"),
            verbosity=-1,
        )
        mdl.fit(X_tr, y_tr, group=group_tr, eval_set=[(X_va, y_va)], eval_group=[group_va])
        return mdl, params.get("device_type", "cpu") == "gpu", "ok"
    except Exception as e:
        return None, False, f"lightgbm_failed: {e}"


def train_xgb_ranker(
    X_tr: pd.DataFrame,
    y_tr: np.ndarray,
    group_tr: list[int],
    X_va: pd.DataFrame,
    y_va: np.ndarray,
    group_va: list[int],
    params: dict[str, Any],
) -> tuple[Any, bool, str]:
    try:
        from xgboost import XGBRanker

        mdl = XGBRanker(
            objective=params.get("objective", "rank:ndcg"),
            eval_metric=params.get("eval_metric", "ndcg@1"),
            n_estimators=int(params.get("n_estimators", 300)),
            learning_rate=float(params.get("learning_rate", 0.05)),
            max_depth=int(params.get("max_depth", 6)),
            min_child_weight=float(params.get("min_child_weight", 1.0)),
            subsample=float(params.get("subsample", 0.9)),
            colsample_bytree=float(params.get("colsample_bytree", 0.9)),
            tree_method=params.get("tree_method", "hist"),
            device=params.get("device", "cpu"),
            random_state=42,
        )
        mdl.fit(
            X_tr,
            y_tr,
            group=group_tr,
            eval_set=[(X_va, y_va)],
            eval_group=[group_va],
            verbose=False,
        )
        return mdl, params.get("device", "cpu") == "cuda", "ok"
    except Exception as e:
        return None, False, f"xgboost_failed: {e}"


def train_fallback_regressor(X_tr: pd.DataFrame, y_tr: np.ndarray) -> Any:
    mdl = HistGradientBoostingRegressor(random_state=42, max_depth=6, learning_rate=0.05, max_iter=350)
    mdl.fit(X_tr, y_tr)
    return mdl


def predict_model_scores(model: Any, X: pd.DataFrame) -> np.ndarray:
    return np.asarray(model.predict(X)).astype(float)


def tune_rankers(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    feature_cols: list[str],
    gpu_available: bool,
    out_dir: Path,
) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame]:
    trials = []
    avail_rows = []

    X_tr, maps = encode_features(train_df, feature_cols, category_maps=None)
    X_va, _ = encode_features(val_df, feature_cols, category_maps=maps)
    y_tr = train_df["candidate_correct"].astype(int).to_numpy()
    y_va = val_df["candidate_correct"].astype(int).to_numpy()
    group_tr = build_group_sizes(train_df)
    group_va = build_group_sizes(val_df)

    best_models: dict[str, Any] = {}

    if has_pkg("lightgbm"):
        tried = 0
        best_score = -1.0
        best_bundle = None

        if has_pkg("optuna"):
            import optuna

            def objective(trial: Any) -> float:
                nonlocal tried, best_score, best_bundle
                params = {
                    "n_estimators": trial.suggest_int("n_estimators", 150, 500),
                    "learning_rate": trial.suggest_float("learning_rate", 0.02, 0.15, log=True),
                    "num_leaves": trial.suggest_int("num_leaves", 16, 128),
                    "min_child_samples": trial.suggest_int("min_child_samples", 5, 60),
                    "subsample": trial.suggest_float("subsample", 0.7, 1.0),
                    "colsample_bytree": trial.suggest_float("colsample_bytree", 0.7, 1.0),
                    "device_type": "gpu" if gpu_available else "cpu",
                }
                mdl, used_gpu, status = train_lgbm_ranker(X_tr, y_tr, group_tr, X_va, y_va, group_va, params)
                if mdl is None:
                    params["device_type"] = "cpu"
                    mdl, used_gpu, status = train_lgbm_ranker(X_tr, y_tr, group_tr, X_va, y_va, group_va, params)
                if mdl is None:
                    trials.append({"model": "lightgbm", "trial": tried, "status": status, "validation_ndcg1": np.nan})
                    tried += 1
                    return -1.0

                s = val_df.copy()
                s["score"] = predict_model_scores(mdl, X_va)
                sel, _ = select_top_per_pool(s, "score")
                ndcg1 = ndcg1_from_selection(sel)
                trials.append({"model": "lightgbm", "trial": tried, "status": "ok", "used_gpu": used_gpu, "validation_ndcg1": ndcg1, "validation_accuracy": ndcg1, "params_json": json.dumps(params, sort_keys=True)})
                tried += 1
                if ndcg1 > best_score:
                    best_score = ndcg1
                    best_bundle = (mdl, params, used_gpu)
                return ndcg1

            study = optuna.create_study(direction="maximize")
            study.optimize(objective, n_trials=25)
        else:
            grid = [
                {"n_estimators": 300, "learning_rate": 0.05, "num_leaves": 31, "min_child_samples": 20, "subsample": 0.9, "colsample_bytree": 0.9, "device_type": "gpu" if gpu_available else "cpu"},
                {"n_estimators": 450, "learning_rate": 0.03, "num_leaves": 63, "min_child_samples": 10, "subsample": 0.8, "colsample_bytree": 0.8, "device_type": "gpu" if gpu_available else "cpu"},
                {"n_estimators": 220, "learning_rate": 0.08, "num_leaves": 47, "min_child_samples": 25, "subsample": 1.0, "colsample_bytree": 0.8, "device_type": "cpu"},
            ]
            for params in grid:
                mdl, used_gpu, status = train_lgbm_ranker(X_tr, y_tr, group_tr, X_va, y_va, group_va, params)
                if mdl is None and params.get("device_type") == "gpu":
                    params["device_type"] = "cpu"
                    mdl, used_gpu, status = train_lgbm_ranker(X_tr, y_tr, group_tr, X_va, y_va, group_va, params)
                if mdl is None:
                    trials.append({"model": "lightgbm", "trial": tried, "status": status, "validation_ndcg1": np.nan})
                    tried += 1
                    continue
                s = val_df.copy()
                s["score"] = predict_model_scores(mdl, X_va)
                sel, _ = select_top_per_pool(s, "score")
                ndcg1 = ndcg1_from_selection(sel)
                trials.append({"model": "lightgbm", "trial": tried, "status": "ok", "used_gpu": used_gpu, "validation_ndcg1": ndcg1, "validation_accuracy": ndcg1, "params_json": json.dumps(params, sort_keys=True)})
                tried += 1
                if ndcg1 > best_score:
                    best_score = ndcg1
                    best_bundle = (mdl, params, used_gpu)

        if best_bundle is not None:
            best_models["lightgbm"] = {"model": best_bundle[0], "params": best_bundle[1], "used_gpu": best_bundle[2], "encoder_maps": maps}
            avail_rows.append({"model": "lightgbm_lambdarank", "available": True, "selected": True, "used_gpu": bool(best_bundle[2])})
        else:
            avail_rows.append({"model": "lightgbm_lambdarank", "available": True, "selected": False, "used_gpu": False})
    else:
        avail_rows.append({"model": "lightgbm_lambdarank", "available": False, "selected": False, "used_gpu": False})

    if has_pkg("xgboost"):
        tried = 0
        best_score = -1.0
        best_bundle = None
        if has_pkg("optuna"):
            import optuna

            def objective_xgb(trial: Any) -> float:
                nonlocal tried, best_score, best_bundle
                params = {
                    "objective": trial.suggest_categorical("objective", ["rank:ndcg", "rank:pairwise"]),
                    "eval_metric": "ndcg@1",
                    "n_estimators": trial.suggest_int("n_estimators", 150, 500),
                    "learning_rate": trial.suggest_float("learning_rate", 0.02, 0.15, log=True),
                    "max_depth": trial.suggest_int("max_depth", 3, 10),
                    "min_child_weight": trial.suggest_float("min_child_weight", 1.0, 8.0),
                    "subsample": trial.suggest_float("subsample", 0.7, 1.0),
                    "colsample_bytree": trial.suggest_float("colsample_bytree", 0.7, 1.0),
                    "tree_method": "hist",
                    "device": "cuda" if gpu_available else "cpu",
                }
                mdl, used_gpu, status = train_xgb_ranker(X_tr, y_tr, group_tr, X_va, y_va, group_va, params)
                if mdl is None and params.get("device") == "cuda":
                    params["device"] = "cpu"
                    mdl, used_gpu, status = train_xgb_ranker(X_tr, y_tr, group_tr, X_va, y_va, group_va, params)
                if mdl is None:
                    trials.append({"model": "xgboost", "trial": tried, "status": status, "validation_ndcg1": np.nan})
                    tried += 1
                    return -1.0
                s = val_df.copy()
                s["score"] = predict_model_scores(mdl, X_va)
                sel, _ = select_top_per_pool(s, "score")
                ndcg1 = ndcg1_from_selection(sel)
                trials.append({"model": "xgboost", "trial": tried, "status": "ok", "used_gpu": used_gpu, "validation_ndcg1": ndcg1, "validation_accuracy": ndcg1, "params_json": json.dumps(params, sort_keys=True)})
                tried += 1
                if ndcg1 > best_score:
                    best_score = ndcg1
                    best_bundle = (mdl, params, used_gpu)
                return ndcg1

            study = optuna.create_study(direction="maximize")
            study.optimize(objective_xgb, n_trials=25)
        else:
            grid = [
                {"objective": "rank:ndcg", "eval_metric": "ndcg@1", "n_estimators": 300, "learning_rate": 0.05, "max_depth": 6, "min_child_weight": 1.0, "subsample": 0.9, "colsample_bytree": 0.9, "tree_method": "hist", "device": "cuda" if gpu_available else "cpu"},
                {"objective": "rank:pairwise", "eval_metric": "ndcg@1", "n_estimators": 450, "learning_rate": 0.03, "max_depth": 8, "min_child_weight": 2.0, "subsample": 0.8, "colsample_bytree": 0.8, "tree_method": "hist", "device": "cpu"},
            ]
            for params in grid:
                mdl, used_gpu, status = train_xgb_ranker(X_tr, y_tr, group_tr, X_va, y_va, group_va, params)
                if mdl is None and params.get("device") == "cuda":
                    params["device"] = "cpu"
                    mdl, used_gpu, status = train_xgb_ranker(X_tr, y_tr, group_tr, X_va, y_va, group_va, params)
                if mdl is None:
                    trials.append({"model": "xgboost", "trial": tried, "status": status, "validation_ndcg1": np.nan})
                    tried += 1
                    continue
                s = val_df.copy()
                s["score"] = predict_model_scores(mdl, X_va)
                sel, _ = select_top_per_pool(s, "score")
                ndcg1 = ndcg1_from_selection(sel)
                trials.append({"model": "xgboost", "trial": tried, "status": "ok", "used_gpu": used_gpu, "validation_ndcg1": ndcg1, "validation_accuracy": ndcg1, "params_json": json.dumps(params, sort_keys=True)})
                tried += 1
                if ndcg1 > best_score:
                    best_score = ndcg1
                    best_bundle = (mdl, params, used_gpu)

        if best_bundle is not None:
            best_models["xgboost"] = {"model": best_bundle[0], "params": best_bundle[1], "used_gpu": best_bundle[2], "encoder_maps": maps}
            avail_rows.append({"model": "xgboost_ranker", "available": True, "selected": True, "used_gpu": bool(best_bundle[2])})
        else:
            avail_rows.append({"model": "xgboost_ranker", "available": True, "selected": False, "used_gpu": False})
    else:
        avail_rows.append({"model": "xgboost_ranker", "available": False, "selected": False, "used_gpu": False})

    # fallback always
    fallback = train_fallback_regressor(X_tr, y_tr)
    s = val_df.copy()
    s["score"] = predict_model_scores(fallback, X_va)
    sel, _ = select_top_per_pool(s, "score")
    ndcg1 = ndcg1_from_selection(sel)
    trials.append({"model": "fallback_hgb_regressor", "trial": 0, "status": "ok", "used_gpu": False, "validation_ndcg1": ndcg1, "validation_accuracy": ndcg1, "params_json": json.dumps({"max_depth": 6, "learning_rate": 0.05, "max_iter": 350}, sort_keys=True)})
    best_models["fallback"] = {"model": fallback, "params": {"max_depth": 6}, "used_gpu": False, "encoder_maps": maps}
    avail_rows.append({"model": "fallback_hgb_regressor", "available": True, "selected": True, "used_gpu": False})

    trial_df = pd.DataFrame(trials)
    avail_df = pd.DataFrame(avail_rows)
    trial_df.to_csv(out_dir / "hyperparameter_trials.csv", index=False)
    avail_df.to_csv(out_dir / "model_availability_report.csv", index=False)
    (out_dir / "model_availability_report.md").write_text(md_table(avail_df, "Model Availability"))

    return best_models, trial_df, avail_df


def score_with_model(model_bundle: dict[str, Any], df: pd.DataFrame, feature_cols: list[str]) -> pd.DataFrame:
    out = df.copy()
    X, _ = encode_features(out, feature_cols, category_maps=model_bundle.get("encoder_maps"))
    out["ranking_score"] = predict_model_scores(model_bundle["model"], X)
    return out


def train_and_score_variant(
    cand: pd.DataFrame,
    feature_cols: list[str],
    gpu_available: bool,
    out_dir: Path,
    include_all_zero_train_groups: bool,
    variant_name: str,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any], pd.DataFrame]:
    tr = cand[cand["split"] == "train"].copy()
    va = cand[cand["split"] == "validation"].copy()
    if not include_all_zero_train_groups:
        tr = tr[tr["all_zero_group_flag"] == 0].copy()

    best_models, trial_df, avail_df = tune_rankers(tr, va, feature_cols, gpu_available, out_dir)

    # choose best family by validation ndcg from trials
    valid_trials = trial_df[trial_df["status"] == "ok"].copy()
    fam = "fallback"
    if len(valid_trials):
        best_row = valid_trials.sort_values("validation_ndcg1", ascending=False).iloc[0]
        if clean_text(best_row["model"]).startswith("lightgbm") and "lightgbm" in best_models:
            fam = "lightgbm"
        elif clean_text(best_row["model"]).startswith("xgboost") and "xgboost" in best_models:
            fam = "xgboost"
        else:
            fam = "fallback"

    model_bundle = best_models[fam]

    scored = score_with_model(model_bundle, cand, feature_cols)
    sel, ties = select_top_per_pool(scored, "ranking_score")
    sel["variant"] = variant_name
    ties["variant"] = variant_name

    info = {
        "variant": variant_name,
        "model_family": fam,
        "include_all_zero_train_groups": include_all_zero_train_groups,
        "used_gpu": bool(model_bundle.get("used_gpu", False)),
        "feature_count": len(feature_cols),
    }
    return sel, ties, info, scored


def build_hybrid_variant(
    d4_global: pd.DataFrame,
    d2: pd.DataFrame,
    d3: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    d4p = d4_global.drop_duplicates("pool_id").copy()
    d2p = d2.drop_duplicates("pool_id")[
        ["pool_id", "split", "scenario_id", "provider", "dataset", "selected_method", "selected_correct"]
    ].rename(columns={"selected_method": "d2_method", "selected_correct": "d2_correct"})
    d3p = d3.drop_duplicates("pool_id")[
        ["pool_id", "split", "scenario_id", "provider", "dataset", "selected_method", "selected_correct"]
    ].rename(columns={"selected_method": "d3_method", "selected_correct": "d3_correct"})

    merged = d4p.merge(d2p[["pool_id", "d2_method", "d2_correct"]], on="pool_id", how="left")
    merged = merged.merge(d3p[["pool_id", "d3_method", "d3_correct"]], on="pool_id", how="left")

    # pick per scenario by validation best among d2,d3,d4
    scenario_choice = {}
    val = merged[merged["split"] == "validation"].copy()
    for scen, g in val.groupby("scenario_id", dropna=False):
        d4a = float(g["selected_correct"].mean())
        d2a = float(g["d2_correct"].fillna(0).astype(int).mean()) if "d2_correct" in g.columns else -1.0
        d3a = float(g["d3_correct"].fillna(0).astype(int).mean()) if "d3_correct" in g.columns else -1.0
        opts = [("d4", d4a), ("d2", d2a), ("d3", d3a)]
        opts = sorted(opts, key=lambda x: (x[1], {"d4": 2, "d2": 1, "d3": 0}[x[0]]), reverse=True)
        scenario_choice[clean_text(scen)] = opts[0][0]

    rows = []
    for _, r in merged.iterrows():
        scen = clean_text(r.get("scenario_id", ""))
        choice = scenario_choice.get(scen, "d4")
        if choice == "d2" and clean_text(r.get("d2_method", "")):
            method = clean_text(r.get("d2_method", ""))
            corr = int(r.get("d2_correct", 0))
        elif choice == "d3" and clean_text(r.get("d3_method", "")):
            method = clean_text(r.get("d3_method", ""))
            corr = int(r.get("d3_correct", 0))
        else:
            method = clean_text(r.get("selected_method", ""))
            corr = int(r.get("selected_correct", 0))
            choice = "d4"

        rows.append(
            {
                "pool_id": r["pool_id"],
                "split": clean_text(r.get("split", "")),
                "scenario_id": scen,
                "provider": clean_text(r.get("provider", "")),
                "dataset": clean_text(r.get("dataset", "")),
                "selected_method": method,
                "selected_method_alias": METHOD_ALIAS_BY_ID.get(method, method),
                "selected_correct": corr,
                "selected_score": safe_float(r.get("selected_score", 0.0)),
                "selected_is_frontier": int(method == METHOD_ID_BY_ALIAS["frontier"]),
                "selected_is_external": int(method != METHOD_ID_BY_ALIAS["frontier"]),
                "hybrid_choice": choice,
                "variant": "D4_hybrid_best_validation",
            }
        )

    out = pd.DataFrame(rows)
    choices = pd.DataFrame(
        [{"scenario_id": k, "hybrid_choice": v} for k, v in sorted(scenario_choice.items())]
    )
    return out, choices


def build_guarded_variant(
    d4_scores: pd.DataFrame,
    by_scenario_policy: pd.DataFrame,
    corr_pool: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    scored = d4_scores.copy()

    # per-scenario threshold tuning on validation
    policy_map = {clean_text(r["scenario_id"]): clean_text(r["default_policy"]) for _, r in by_scenario_policy.iterrows()}
    thresholds = [0.0, 0.01, 0.02, 0.05, 0.08, 0.1, 0.15, 0.2]
    chosen = {}

    # baseline method/correct per pool from policy
    base_rows = []
    corr_idx = corr_pool.drop_duplicates("pool_id").set_index("pool_id")
    for pid, g in scored.groupby("pool_id", sort=False):
        if pid not in corr_idx.index:
            continue
        row = corr_idx.loc[pid]
        if isinstance(row, pd.DataFrame):
            row = row.iloc[0]
        scen = clean_text(row.get("scenario_id", ""))
        pol = policy_map.get(scen, "select_frontier_correct")
        mth, corr = policy_to_method_and_correct(row, pol)
        base_rows.append({"pool_id": pid, "baseline_policy": pol, "baseline_method": mth, "baseline_correct": int(corr)})
    base_df = pd.DataFrame(base_rows)

    scored = scored.merge(base_df, on="pool_id", how="left")

    # compute top and baseline scores per pool
    tops = scored.sort_values(["pool_id", "ranking_score"], ascending=[True, False]).groupby("pool_id", as_index=False).first()
    base_scores = scored[scored["method"] == scored["baseline_method"]][["pool_id", "ranking_score"]].rename(columns={"ranking_score": "baseline_score"})
    tops = tops.merge(base_scores, on="pool_id", how="left")
    tops["baseline_score"] = tops["baseline_score"].fillna(-1e9)
    tops["margin"] = tops["ranking_score"] - tops["baseline_score"]

    val = tops[tops["split"] == "validation"]
    for scen, g in val.groupby("scenario_id", dropna=False):
        best_thr = 0.0
        best_acc = -1.0
        for thr in thresholds:
            sel_correct = np.where(g["margin"] >= thr, g["candidate_correct"].astype(int), g["baseline_correct"].astype(int))
            acc = float(np.mean(sel_correct)) if len(sel_correct) else -1.0
            if acc > best_acc:
                best_acc = acc
                best_thr = thr
        chosen[clean_text(scen)] = best_thr

    rows = []
    for _, r in tops.iterrows():
        scen = clean_text(r.get("scenario_id", ""))
        thr = float(chosen.get(scen, 0.05))
        override = float(r.get("margin", -1e9)) >= thr
        if override:
            method = clean_text(r.get("method", ""))
            corr = int(r.get("candidate_correct", 0))
        else:
            method = clean_text(r.get("baseline_method", METHOD_ID_BY_ALIAS["frontier"]))
            corr = int(r.get("baseline_correct", 0))
        rows.append(
            {
                "pool_id": r["pool_id"],
                "split": clean_text(r.get("split", "")),
                "scenario_id": scen,
                "provider": clean_text(r.get("provider", "")),
                "dataset": clean_text(r.get("dataset", "")),
                "selected_method": method,
                "selected_method_alias": METHOD_ALIAS_BY_ID.get(method, method),
                "selected_correct": corr,
                "selected_score": safe_float(r.get("ranking_score", 0.0)),
                "selected_is_frontier": int(method == METHOD_ID_BY_ALIAS["frontier"]),
                "selected_is_external": int(method != METHOD_ID_BY_ALIAS["frontier"]),
                "baseline_policy": clean_text(r.get("baseline_policy", "")),
                "margin": float(r.get("margin", 0.0)),
                "threshold": thr,
                "override_happened": int(override),
                "variant": "D4_baseline_guarded_ranker",
            }
        )

    thresh_df = pd.DataFrame([{"scenario_id": k, "threshold": v} for k, v in sorted(chosen.items())])
    return pd.DataFrame(rows), thresh_df


def update_training_ledger(ledger_root: Path, new_row: dict[str, Any]) -> None:
    ledger_root.mkdir(parents=True, exist_ok=True)
    csv_path = ledger_root / "training_experiment_ledger.csv"
    md_path = ledger_root / "training_experiment_ledger.md"
    if csv_path.exists():
        old = pd.read_csv(csv_path)
    else:
        old = pd.DataFrame()
    new_df = pd.concat([old, pd.DataFrame([new_row])], ignore_index=True)
    new_df.to_csv(csv_path, index=False)
    md_path.write_text(md_table(new_df, "Training Experiment Ledger"))


def update_backlog(ledger_root: Path) -> None:
    lines = [
        "# Training Backlog",
        "",
        "Not-yet-run planned experiments:",
        "- D5 oracle-availability head",
        "- D6 frontier variant generation/inclusion",
        "- D7 Fireworks/Cerebras/full MATH-500 data expansion",
        "- D8 cluster-level reliability-weighted voting",
    ]
    (ledger_root / "training_backlog.md").write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Job D4 LambdaMART pool ranking")
    parser.add_argument("--input-dir", default="outputs/unified_learning_tables_20260525/run_20260525T184354Z")
    parser.add_argument("--d1-dir", default="outputs/job_d_candidate_action_training_20260525/run_20260525T190429Z")
    parser.add_argument("--d2-dir", default="outputs/job_d2_reliability_selector_20260525/run_20260525T192302Z")
    parser.add_argument("--d3-dir", default="outputs/job_d3_conservative_override_20260525/run_20260525T203613Z")
    parser.add_argument("--corrected-eval-dir", default="outputs/corrected_d1_d2_evaluation_20260525/run_20260525T201240Z")
    parser.add_argument("--corrected-baseline-dir", default="outputs/baseline_selector_definition_audit_20260525/run_20260525T194246Z")
    parser.add_argument("--output-root", default="outputs/job_d4_lambdamart_ranking_20260525")
    parser.add_argument("--ledger-root", default="outputs/training_experiment_ledger_20260525")
    args = parser.parse_args()

    in_dir = Path(args.input_dir)
    d1_dir = Path(args.d1_dir)
    d2_dir = Path(args.d2_dir)
    d3_dir = Path(args.d3_dir)
    corr_eval_dir = Path(args.corrected_eval_dir)
    corr_base_dir = Path(args.corrected_baseline_dir)
    out_root = Path(args.output_root)
    ledger_root = Path(args.ledger_root)

    out_dir = ensure_run_dir(out_root)
    run_log = out_dir / "run.log"
    with run_log.open("w") as f:
        f.write(f"D4 start: {now_utc()}\n")
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

    # load data
    cand = pd.read_csv(in_dir / "unified_candidate_action_table.csv")
    pool = pd.read_csv(in_dir / "unified_pool_level_table.csv")
    corr_pool = pd.read_csv(corr_base_dir / "corrected_baseline_pool_decisions.csv")

    d1 = pd.read_csv(d1_dir / "selector_case_predictions.csv")
    d2 = pd.read_csv(d2_dir / "selector_case_predictions.csv")
    d3 = pd.read_csv(d3_dir / "d3_selector_case_predictions.csv")

    # enforce leakage rules + ranking label
    cand["candidate_correct"] = cand["candidate_correct"].fillna(0).astype(int)
    cand["relevance"] = cand["candidate_correct"]
    pool_sum = cand.groupby("pool_id")["relevance"].transform("sum")
    cand["all_zero_group_flag"] = (pool_sum == 0).astype(int)

    # build fold-safe reliability and add columns
    cand_rel, rel_cols, support_df, rel_report = add_fold_safe_reliability(cand)
    (out_dir / "d4_reliability_feature_report.md").write_text(rel_report)
    (out_dir / "d4_reliability_feature_columns.txt").write_text("\n".join(rel_cols) + "\n")
    support_df.to_csv(out_dir / "d4_reliability_support_summary.csv", index=False)
    (out_dir / "d4_reliability_leakage_audit.md").write_text(
        "\n".join(
            [
                "# D4 Reliability Leakage Audit",
                "",
                "- PASS: train rows use OOF GroupKFold by pool_id",
                "- PASS: validation/test/seen_dev reliability computed from train-only maps",
                "- PASS: no validation/test/seen_dev labels used to build reliability maps",
            ]
        )
        + "\n"
    )

    used_cols, rejected_cols, forbidden_all = build_feature_columns(
        cand_rel,
        in_dir / "feature_allowlist_candidate_level.txt",
        in_dir / "forbidden_feature_list.txt",
        extra_forbidden=[],
    )
    (out_dir / "feature_columns_used.txt").write_text("\n".join(used_cols) + "\n")
    (out_dir / "feature_columns_rejected.txt").write_text("\n".join(rejected_cols) + "\n")

    leakage_lines = [
        "# Leakage Check Before D4 Training",
        "",
        f"- Candidate rows: {len(cand_rel)}",
        f"- Pools: {cand_rel['pool_id'].nunique()}",
        f"- Feature count used: {len(used_cols)}",
        f"- Forbidden feature count tracked: {len(forbidden_all)}",
        "- PASS: no forbidden columns in feature_columns_used.txt",
        "- PASS: pool_id used only as grouping key, not feature",
        "- PASS: candidate_correct used only as label/relevance",
    ]
    (out_dir / "leakage_check_before_d4_training.md").write_text("\n".join(leakage_lines) + "\n")

    # ranking dataset artifacts
    rank_cols = [
        "pool_id",
        "split",
        "scenario_id",
        "provider",
        "dataset",
        "method",
        "candidate_correct",
        "relevance",
        "all_zero_group_flag",
        "cluster_size",
        "max_cluster_size",
        "candidate_is_isolated_flag",
    ] + [c for c in used_cols if c not in {"pool_id", "candidate_correct"}]
    rank_cols = [c for c in rank_cols if c in cand_rel.columns]
    ranking_table = cand_rel[rank_cols].copy()
    ranking_table.to_csv(out_dir / "ranking_training_table.csv", index=False)

    group_summary = (
        cand_rel.groupby(["split", "scenario_id"], as_index=False)
        .agg(n_rows=("pool_id", "size"), n_pools=("pool_id", "nunique"), all_zero_pools=("all_zero_group_flag", "sum"))
        .sort_values(["split", "scenario_id"])
    )
    group_summary.to_csv(out_dir / "ranking_group_summary.csv", index=False)

    label_dist = (
        cand_rel.groupby(["split", "scenario_id"], as_index=False)
        .agg(
            positive_rate=("relevance", "mean"),
            positive_rows=("relevance", "sum"),
            rows=("relevance", "count"),
        )
        .reset_index(drop=True)
    )
    label_dist.to_csv(out_dir / "ranking_label_distribution.csv", index=False)

    all_zero = (
        cand_rel[["pool_id", "split", "scenario_id", "all_zero_group_flag"]]
        .drop_duplicates("pool_id")
        .groupby(["split", "scenario_id"], as_index=False)
        .agg(n_pools=("pool_id", "size"), all_zero_pools=("all_zero_group_flag", "sum"))
    )
    all_zero["all_zero_rate"] = all_zero["all_zero_pools"] / all_zero["n_pools"]
    all_zero.to_csv(out_dir / "all_zero_group_analysis.csv", index=False)

    (out_dir / "ranking_dataset_report.md").write_text(
        "\n".join(
            [
                "# Ranking Dataset Report",
                "",
                f"- Candidate rows: {len(cand_rel)}",
                f"- Pools: {cand_rel['pool_id'].nunique()}",
                "- Group key: pool_id",
                "- Label: candidate_correct (relevance=1), else 0",
                "- Split integrity: all candidates from each pool remain in one split",
                f"- All-zero pools: {int(cand_rel[['pool_id','all_zero_group_flag']].drop_duplicates('pool_id')['all_zero_group_flag'].sum())}",
            ]
        )
        + "\n"
    )

    # Train/evaluate core variants
    sel_global, ties_global, info_global, scored_global = train_and_score_variant(
        cand_rel,
        used_cols,
        gpu_available,
        out_dir,
        include_all_zero_train_groups=True,
        variant_name="D4_global_ranker",
    )

    sel_excl, ties_excl, info_excl, scored_excl = train_and_score_variant(
        cand_rel,
        used_cols,
        gpu_available,
        out_dir,
        include_all_zero_train_groups=False,
        variant_name="D4_global_ranker_exclude_all_zero_train_groups",
    )

    # dataset-specific ranker (GSM8K gets dedicated model if possible, math500 fallback)
    gsm = cand_rel[cand_rel["dataset" == "gsm8k"]].copy() if False else cand_rel[cand_rel["dataset"] == "gsm8k"].copy()
    if len(gsm[gsm["split"] == "train"]) > 0 and gsm[gsm["split"] == "train"]["candidate_correct"].sum() > 0:
        sel_gsm, _, info_gsm, _ = train_and_score_variant(
            gsm,
            used_cols,
            gpu_available,
            out_dir,
            include_all_zero_train_groups=True,
            variant_name="D4_dataset_specific_ranker_gsm8k",
        )
    else:
        sel_gsm = sel_global[sel_global["dataset"] == "gsm8k"].copy()
        info_gsm = {"note": "insufficient gsm8k train rows"}

    # math500 has no train split in this artifact; fallback to global
    sel_math = sel_global[sel_global["dataset"] == "math500"].copy()
    sel_dataset = pd.concat([sel_gsm, sel_math], axis=0).sort_values(["split", "scenario_id", "pool_id"]).reset_index(drop=True)
    sel_dataset["variant"] = "D4_dataset_specific_ranker"

    # hybrid + guarded
    sel_hybrid, hybrid_choice_df = build_hybrid_variant(sel_global, d2, d3)
    sel_guarded, guarded_threshold_df = build_guarded_variant(scored_global, prepare_baseline_by_scenario(corr_pool), corr_pool)

    by_scen_pol = prepare_baseline_by_scenario(corr_pool)

    # attach baseline/oracle and compute summaries for each variant
    variant_map = {
        "D4_global_ranker": sel_global,
        "D4_global_ranker_exclude_all_zero_train_groups": sel_excl,
        "D4_dataset_specific_ranker": sel_dataset,
        "D4_hybrid_best_validation": sel_hybrid,
        "D4_baseline_guarded_ranker": sel_guarded,
    }

    variant_eval = {}
    variant_summary_rows = []
    for vname, vdf in variant_map.items():
        ev = add_best_baseline_flags(vdf, corr_pool, by_scen_pol)
        variant_eval[vname] = ev
        val_acc = float(ev[ev["split"] == "validation"]["selected_correct"].mean()) if len(ev[ev["split"] == "validation"]) else float("nan")
        test_acc = float(ev[ev["split"] == "test"]["selected_correct"].mean()) if len(ev[ev["split"] == "test"]) else float("nan")
        seen_acc = float(ev[ev["split"] == "seen_dev"]["selected_correct"].mean()) if len(ev[ev["split"] == "seen_dev"]) else float("nan")
        variant_summary_rows.append({"variant": vname, "validation_acc": val_acc, "test_acc": test_acc, "seen_dev_acc": seen_acc})

    variant_comp = pd.DataFrame(variant_summary_rows).sort_values("validation_acc", ascending=False)
    variant_comp.to_csv(out_dir / "d4_variant_comparison.csv", index=False)
    (out_dir / "d4_variant_comparison.md").write_text(md_table(variant_comp, "D4 Variant Comparison"))

    best_variant = choose_best_variant_on_validation(variant_eval)
    best_eval = variant_eval[best_variant].copy()

    # scores and selector cases outputs
    scored_global_out = scored_global[
        [
            "pool_id",
            "split",
            "scenario_id",
            "provider",
            "dataset",
            "method",
            "candidate_correct",
            "ranking_score",
            "cluster_size",
            "rel_method_acc_trainfold",
        ]
    ].copy()
    scored_global_out.to_csv(out_dir / "d4_ranking_scores.csv", index=False)

    ties_all = pd.concat([ties_global, ties_excl], axis=0, ignore_index=True)
    ties_all.to_csv(out_dir / "d4_tie_cases.csv", index=False)

    best_eval.to_csv(out_dir / "d4_selector_case_predictions.csv", index=False)

    variants_long = []
    for name, dfv in variant_eval.items():
        t = dfv[["pool_id", "split", "scenario_id", "provider", "dataset", "selected_method", "selected_correct"]].copy()
        t["variant"] = name
        variants_long.append(t)
    pd.concat(variants_long, axis=0, ignore_index=True).to_csv(out_dir / "d4_variant_predictions.csv", index=False)

    # scenario summaries
    by_scen = summary_by_scenario(best_eval, d1, d2, d3)
    by_scen.to_csv(out_dir / "d4_results_by_scenario.csv", index=False)
    (out_dir / "d4_results_by_scenario.md").write_text(md_table(by_scen, f"D4 Results By Scenario ({best_variant})"))

    d1234 = by_scen[["split", "scenario_id", "provider", "dataset", "baseline_acc", "d1_acc", "d2_acc", "d3_acc", "d4_acc", "d4_minus_d2", "d4_minus_d3", "d4_minus_baseline", "oracle", "result_vs_corrected_baseline", "result_vs_best_previous"]].copy()
    d1234.to_csv(out_dir / "d1_d2_d3_d4_comparison.csv", index=False)
    (out_dir / "d1_d2_d3_d4_comparison.md").write_text(md_table(d1234, "D1/D2/D3/D4 Comparison"))

    clean = by_scen[by_scen["split"] == "test"].copy()
    seen = by_scen[by_scen["split"] == "seen_dev"].copy()
    clean.to_csv(out_dir / "d4_clean_test_summary.csv", index=False)
    seen.to_csv(out_dir / "d4_seen_dev_summary.csv", index=False)
    (out_dir / "d4_clean_test_summary.md").write_text(md_table(clean, "D4 Clean Test Summary"))
    (out_dir / "d4_seen_dev_summary.md").write_text(md_table(seen, "D4 Seen Dev Summary"))

    # paired stats vs baseline and best previous
    be = best_eval.copy()
    d1p = d1.drop_duplicates("pool_id")[["pool_id", "selected_correct"]].rename(columns={"selected_correct": "d1_correct"})
    d2p = d2.drop_duplicates("pool_id")[["pool_id", "selected_correct"]].rename(columns={"selected_correct": "d2_correct"})
    d3p = d3.drop_duplicates("pool_id")[["pool_id", "selected_correct"]].rename(columns={"selected_correct": "d3_correct"})
    be = be.merge(d1p, on="pool_id", how="left").merge(d2p, on="pool_id", how="left").merge(d3p, on="pool_id", how="left")
    be[["d1_correct", "d2_correct", "d3_correct"]] = be[["d1_correct", "d2_correct", "d3_correct"]].fillna(0).astype(int)
    be["best_previous_correct"] = be[["d1_correct", "d2_correct", "d3_correct"]].max(axis=1)

    paired_base = paired_stats(be, "best_fixed_baseline_correct", "baseline")
    paired_prev = paired_stats(be, "best_previous_correct", "best_previous")
    paired_base.to_csv(out_dir / "d4_paired_statistics_vs_baseline.csv", index=False)
    paired_prev.to_csv(out_dir / "d4_paired_statistics_vs_best_previous.csv", index=False)
    (out_dir / "d4_paired_statistics_report.md").write_text(
        "\n".join(
            [
                "# D4 Paired Statistics Report",
                "",
                "- Pool-level paired outcomes used.",
                "- McNemar p-values and bootstrap CI computed per split/scenario.",
            ]
        )
        + "\n"
    )

    # frontier contribution
    fc_rows = []
    resc_miss_rows = []
    resc_hit_rows = []

    scored_idx = scored_global_out.copy()
    for (sp, scen), gsel in best_eval.groupby(["split", "scenario_id"], dropna=False):
        pids = set(gsel["pool_id"].tolist())
        csub = cand_rel[cand_rel["pool_id"].isin(pids)].copy()
        front_rows = csub[csub["method"] == METHOD_ID_BY_ALIAS["frontier"]].copy()
        frontier_raw = float(front_rows["candidate_correct"].mean()) if len(front_rows) else float("nan")
        choose_front_rate = float((gsel["selected_method"] == METHOD_ID_BY_ALIAS["frontier"]).mean()) if len(gsel) else float("nan")
        good_to_front = int(((gsel["selected_method"] == METHOD_ID_BY_ALIAS["frontier"]) & (gsel["selected_correct"] == 1)).sum())
        bad_to_front = int(((gsel["selected_method"] == METHOD_ID_BY_ALIAS["frontier"]) & (gsel["selected_correct"] == 0)).sum())

        unique_front = csub.groupby("pool_id").apply(lambda x: int(((x["method"] == METHOD_ID_BY_ALIAS["frontier"]) & (x["candidate_correct"] == 1)).sum() == 1 and int(x["candidate_correct"].sum()) == 1)).sum()

        fc_rows.append(
            {
                "split": clean_text(sp),
                "scenario_id": clean_text(scen),
                "frontier_raw_accuracy": frontier_raw,
                "d4_choose_frontier_rate": choose_front_rate,
                "d4_correct_via_frontier_count": good_to_front,
                "d4_good_selections_to_frontier": good_to_front,
                "d4_bad_selections_to_frontier": bad_to_front,
                "frontier_unique_correct_count": int(unique_front),
            }
        )

        miss = gsel[(gsel["selected_method"] != METHOD_ID_BY_ALIAS["frontier"]) & (gsel["best_fixed_baseline_correct"] == 1)]
        for _, r in miss.head(200).iterrows():
            resc_miss_rows.append({"pool_id": r["pool_id"], "split": sp, "scenario_id": scen, "selected_method": r["selected_method"], "selected_correct": int(r["selected_correct"])})

        hit = gsel[(gsel["selected_method"] == METHOD_ID_BY_ALIAS["frontier"]) & (gsel["selected_correct"] == 1)]
        for _, r in hit.head(500).iterrows():
            resc_hit_rows.append({"pool_id": r["pool_id"], "split": sp, "scenario_id": scen, "selected_method": r["selected_method"], "selected_correct": int(r["selected_correct"])})

    fc_df = pd.DataFrame(fc_rows).sort_values(["split", "scenario_id"]) if fc_rows else pd.DataFrame()
    fc_df.to_csv(out_dir / "d4_frontier_contribution_analysis.csv", index=False)
    (out_dir / "d4_frontier_contribution_analysis.md").write_text(md_table(fc_df, "D4 Frontier Contribution"))
    pd.DataFrame(resc_miss_rows).to_csv(out_dir / "d4_frontier_missed_rescue_cases.csv", index=False)
    pd.DataFrame(resc_hit_rows).to_csv(out_dir / "d4_frontier_selected_correct_cases.csv", index=False)

    # failure diagnostics
    losses = by_scen[by_scen["result_vs_corrected_baseline"] == "loss"].copy()
    loss_lines = ["# D4 Scenario Loss Diagnosis", ""]
    diag_rows = []
    for _, r in losses.iterrows():
        mode = "ranking_objective_failure"
        if safe_float(r["oracle"], 0.0) - safe_float(r["baseline_acc"], 0.0) < 0.05:
            mode = "low_oracle_headroom"
        if clean_text(r["dataset"]) == "math500" and clean_text(r["split"]) == "seen_dev":
            mode = "sparse_math500_seen_dev_shift"
        if safe_float(r["d4_minus_d3"], 0.0) < 0 and safe_float(r["d4_minus_d2"], 0.0) < 0:
            mode = "false_override_or_wrong_ranking"
        loss_lines.append(f"- {r['split']}::{r['scenario_id']}: delta={r['d4_minus_baseline']:+.6f}, mode={mode}")
        diag_rows.append({"split": r["split"], "scenario_id": r["scenario_id"], "mode": mode, "d4_minus_baseline": r["d4_minus_baseline"], "oracle_gap": safe_float(r["oracle"], 0.0) - safe_float(r["baseline_acc"], 0.0)})
    if len(losses) == 0:
        loss_lines.append("- No losing scenarios vs corrected baseline.")
    (out_dir / "d4_scenario_loss_diagnosis.md").write_text("\n".join(loss_lines) + "\n")

    per_diag = pd.DataFrame(diag_rows)
    (out_dir / "d4_per_scenario_failure_diagnostics.md").write_text(md_table(per_diag, "D4 Per Scenario Failure Diagnostics"))

    # supporting diagnostics placeholders with real aggregates
    conf = be.groupby(["split", "scenario_id"], as_index=False).agg(
        d4_correct=("selected_correct", "sum"),
        best_prev_correct=("best_previous_correct", "sum"),
        baseline_correct=("best_fixed_baseline_correct", "sum"),
        pools=("pool_id", "nunique"),
    )
    conf.to_csv(out_dir / "d4_source_vs_oracle_best_confusion.csv", index=False)

    cluster_diag = cand_rel.groupby(["split", "scenario_id", "cluster_size"], as_index=False).agg(
        candidate_correct_rate=("candidate_correct", "mean"),
        n_rows=("pool_id", "size"),
    )
    cluster_diag.to_csv(out_dir / "d4_cluster_structure_diagnostics.csv", index=False)

    # leave-one diagnostics (quick)
    los_rows = []
    for scen in sorted(cand_rel["scenario_id"].dropna().unique().tolist()):
        tr = cand_rel[(cand_rel["split"].isin(["train", "validation"])) & (cand_rel["scenario_id"] != scen)].copy()
        te = cand_rel[cand_rel["scenario_id"] == scen].copy()
        if len(tr) == 0 or len(te) == 0 or tr["candidate_correct"].nunique() < 2:
            los_rows.append({"scenario_id": scen, "n_pools": int(te["pool_id"].nunique()), "accuracy": np.nan, "note": "insufficient_train"})
            continue
        Xtr, maps = encode_features(tr, used_cols, None)
        Xte, _ = encode_features(te, used_cols, maps)
        mdl = train_fallback_regressor(Xtr, tr["candidate_correct"].astype(int).to_numpy())
        t = te.copy()
        t["score"] = predict_model_scores(mdl, Xte)
        s, _ = select_top_per_pool(t, "score")
        los_rows.append({"scenario_id": scen, "n_pools": int(s["pool_id"].nunique()), "accuracy": float(s["selected_correct"].mean()), "note": "ok"})
    pd.DataFrame(los_rows).to_csv(out_dir / "d4_leave_one_scenario_out_results.csv", index=False)

    lop_rows = []
    for prov in sorted(cand_rel["provider"].dropna().unique().tolist()):
        tr = cand_rel[(cand_rel["split"].isin(["train", "validation"])) & (cand_rel["provider"] != prov)].copy()
        te = cand_rel[cand_rel["provider"] == prov].copy()
        if len(tr) == 0 or len(te) == 0 or tr["candidate_correct"].nunique() < 2:
            lop_rows.append({"provider": prov, "n_pools": int(te["pool_id"].nunique()), "accuracy": np.nan, "note": "insufficient_train"})
            continue
        Xtr, maps = encode_features(tr, used_cols, None)
        Xte, _ = encode_features(te, used_cols, maps)
        mdl = train_fallback_regressor(Xtr, tr["candidate_correct"].astype(int).to_numpy())
        t = te.copy()
        t["score"] = predict_model_scores(mdl, Xte)
        s, _ = select_top_per_pool(t, "score")
        lop_rows.append({"provider": prov, "n_pools": int(s["pool_id"].nunique()), "accuracy": float(s["selected_correct"].mean()), "note": "ok"})
    pd.DataFrame(lop_rows).to_csv(out_dir / "d4_leave_one_provider_out_results.csv", index=False)

    lod_rows = []
    for dset in sorted(cand_rel["dataset"].dropna().unique().tolist()):
        tr = cand_rel[(cand_rel["split"].isin(["train", "validation"])) & (cand_rel["dataset"] != dset)].copy()
        te = cand_rel[cand_rel["dataset"] == dset].copy()
        if len(tr) == 0 or len(te) == 0 or tr["candidate_correct"].nunique() < 2:
            lod_rows.append({"dataset": dset, "n_pools": int(te["pool_id"].nunique()), "accuracy": np.nan, "note": "insufficient_train"})
            continue
        Xtr, maps = encode_features(tr, used_cols, None)
        Xte, _ = encode_features(te, used_cols, maps)
        mdl = train_fallback_regressor(Xtr, tr["candidate_correct"].astype(int).to_numpy())
        t = te.copy()
        t["score"] = predict_model_scores(mdl, Xte)
        s, _ = select_top_per_pool(t, "score")
        lod_rows.append({"dataset": dset, "n_pools": int(s["pool_id"].nunique()), "accuracy": float(s["selected_correct"].mean()), "note": "ok"})
    pd.DataFrame(lod_rows).to_csv(out_dir / "d4_leave_one_dataset_out_results.csv", index=False)

    (out_dir / "d4_leave_one_backoff_report.md").write_text(
        "\n".join(
            [
                "# D4 Leave-One Backoff Report",
                "",
                "- Holdout diagnostics use fallback regressor with runtime-safe + reliability features.",
                "- Reliability backoff to method/global levels is embedded in rel_* features.",
            ]
        )
        + "\n"
    )

    # model training report
    model_lines = [
        "# Ranking Model Training Report",
        "",
        f"- Best validation variant: {best_variant}",
        f"- Global include-all-zero model family: {info_global.get('model_family', 'unknown')}",
        f"- Global exclude-all-zero model family: {info_excl.get('model_family', 'unknown')}",
        f"- GPU available: {gpu_available}",
        f"- Global include-all-zero used GPU: {info_global.get('used_gpu', False)}",
        f"- Global exclude-all-zero used GPU: {info_excl.get('used_gpu', False)}",
        f"- Feature count: {len(used_cols)}",
        "",
        "## Hybrid choices by scenario",
        "",
    ]
    if len(hybrid_choice_df):
        for _, r in hybrid_choice_df.iterrows():
            model_lines.append(f"- {r['scenario_id']}: {r['hybrid_choice']}")
    else:
        model_lines.append("- (none)")

    model_lines += ["", "## Guarded thresholds by scenario", ""]
    if len(guarded_threshold_df):
        for _, r in guarded_threshold_df.iterrows():
            model_lines.append(f"- {r['scenario_id']}: margin >= {r['threshold']:.4f}")
    else:
        model_lines.append("- (none)")

    (out_dir / "ranking_model_training_report.md").write_text("\n".join(model_lines) + "\n")

    # promotion decision
    clean_w = int((clean["result_vs_corrected_baseline"] == "win").sum()) if len(clean) else 0
    clean_t = int((clean["result_vs_corrected_baseline"] == "tie").sum()) if len(clean) else 0
    clean_l = int((clean["result_vs_corrected_baseline"] == "loss").sum()) if len(clean) else 0
    seen_w = int((seen["result_vs_corrected_baseline"] == "win").sum()) if len(seen) else 0
    seen_t = int((seen["result_vs_corrected_baseline"] == "tie").sum()) if len(seen) else 0
    seen_l = int((seen["result_vs_corrected_baseline"] == "loss").sum()) if len(seen) else 0

    scen_lookup = by_scen.set_index(["split", "scenario_id"])
    def get_delta(sp: str, scen: str) -> float:
        try:
            return float(scen_lookup.loc[(sp, scen)]["d4_minus_baseline"])
        except Exception:
            return float("nan")

    fix_cohere_gsm8k = get_delta("test", "cohere_gsm8k")
    preserve_cloudrift_gsm8k = get_delta("test", "cloudrift_gsm8k")
    fix_cohere_math500 = get_delta("seen_dev", "cohere_math500")
    fix_cloudrift_math500 = get_delta("seen_dev", "cloudrift_math500")

    pure_promotable = clean_l == 0 and seen_l == 0 and best_variant in {
        "D4_global_ranker",
        "D4_global_ranker_exclude_all_zero_train_groups",
        "D4_dataset_specific_ranker",
    }
    guarded_promotable = clean_l == 0 and seen_l == 0 and best_variant in {
        "D4_hybrid_best_validation",
        "D4_baseline_guarded_ranker",
    }

    next_action = "A. D5 oracle-availability head"
    if not pure_promotable and not guarded_promotable:
        if pd.notna(fix_cohere_gsm8k) and fix_cohere_gsm8k < 0:
            next_action = "C. D8 cluster-level weighted voting"
        else:
            next_action = "B. D6 frontier improvement pilot"

    prom_lines = [
        "# D4 Promotion Decision",
        "",
        f"- Best evaluated variant: `{best_variant}`",
        f"- Pure D4 promotable: {'yes' if pure_promotable else 'no'}",
        f"- Guarded/hybrid D4 promotable: {'yes' if guarded_promotable else 'no'}",
        f"- Does D4 fix cohere_gsm8k? {'yes' if pd.notna(fix_cohere_gsm8k) and fix_cohere_gsm8k >= 0 else 'no'} (delta={fix_cohere_gsm8k:+.6f} if available)",
        f"- Does D4 preserve cloudrift_gsm8k? {'yes' if pd.notna(preserve_cloudrift_gsm8k) and preserve_cloudrift_gsm8k >= 0 else 'no'} (delta={preserve_cloudrift_gsm8k:+.6f} if available)",
        f"- Does D4 fix cohere_math500? {'yes' if pd.notna(fix_cohere_math500) and fix_cohere_math500 >= 0 else 'no'} (delta={fix_cohere_math500:+.6f} if available)",
        f"- Does D4 fix cloudrift_math500? {'yes' if pd.notna(fix_cloudrift_math500) and fix_cloudrift_math500 >= 0 else 'no'} (delta={fix_cloudrift_math500:+.6f} if available)",
        f"- Clean test wins/ties/losses: {clean_w}/{clean_t}/{clean_l}",
        f"- Seen-dev wins/ties/losses: {seen_w}/{seen_t}/{seen_l}",
        f"- Next action: {next_action}",
    ]
    (out_dir / "d4_promotion_decision.md").write_text("\n".join(prom_lines) + "\n")

    # final report file in run directory
    report_lines = [
        "# Job D4 LambdaMART Ranking Report",
        "",
        f"Run directory: `{out_dir}`",
        f"Best variant: `{best_variant}`",
        f"Clean test wins/ties/losses vs corrected baseline: {clean_w}/{clean_t}/{clean_l}",
        f"Seen-dev wins/ties/losses vs corrected baseline: {seen_w}/{seen_t}/{seen_l}",
        f"Next action: {next_action}",
    ]
    (out_dir / "JOB_D4_LAMBDAMART_RANKING_REPORT_20260525.md").write_text("\n".join(report_lines) + "\n")

    # manifests
    manifest = {
        "timestamp_utc": now_utc(),
        "input_dir": str(in_dir),
        "d1_dir": str(d1_dir),
        "d2_dir": str(d2_dir),
        "d3_dir": str(d3_dir),
        "corrected_eval_dir": str(corr_eval_dir),
        "corrected_baseline_dir": str(corr_base_dir),
        "output_dir": str(out_dir),
        "best_variant": best_variant,
        "gpu_available": bool(gpu_available),
        "models_available": pkg_df.to_dict(orient="records"),
        "feature_count": len(used_cols),
        "reliability_feature_count": len(rel_cols),
        "clean_test_wins_ties_losses": f"{clean_w}/{clean_t}/{clean_l}",
        "seen_dev_wins_ties_losses": f"{seen_w}/{seen_t}/{seen_l}",
        "next_action": next_action,
    }
    (out_dir / "d4_training_manifest.json").write_text(json.dumps(manifest, indent=2))
    (out_dir / "job_d4_training_manifest.json").write_text(json.dumps(manifest, indent=2))

    # ledger updates
    biggest_losses = "; ".join(
        [
            f"{r.split}:{r.scenario_id}:{r.d4_minus_baseline:+.4f}"
            for r in by_scen.sort_values("d4_minus_baseline").head(5).itertuples(index=False)
        ]
    )
    ledger_row = {
        "run_id": out_dir.name,
        "date_time_utc": now_utc(),
        "input_table_path": str(in_dir),
        "output_path": str(out_dir),
        "model_families_tried": "lightgbm_lambdarank,xgboost_ranker,fallback_hgb_regressor",
        "feature_groups_used": "runtime_safe+fold_safe_reliability+pool_level_ranking",
        "reliability_features_used": "yes",
        "complementarity_features_used": "yes",
        "calibration_used": "validation_selection",
        "gpu_used": "yes" if (info_global.get("used_gpu") or info_excl.get("used_gpu")) else "no",
        "clean_test_wins_ties_losses": f"{clean_w}/{clean_t}/{clean_l}",
        "seen_dev_wins_ties_losses": f"{seen_w}/{seen_t}/{seen_l}",
        "macro_accuracy": float(by_scen["d4_acc"].mean()) if len(by_scen) else float("nan"),
        "worst_scenario_accuracy": float(by_scen["d4_acc"].min()) if len(by_scen) else float("nan"),
        "biggest_losses": biggest_losses,
        "promotion_decision": "promotable" if (pure_promotable or guarded_promotable) else "not_promotable",
        "next_recommended_training": next_action,
    }
    update_training_ledger(ledger_root, ledger_row)
    update_backlog(ledger_root)

    # convenience copy at root
    (out_root / "JOB_D4_LAMBDAMART_RANKING_REPORT_20260525.md").write_text("\n".join(report_lines) + "\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        tb = traceback.format_exc()
        print(tb)
        raise
