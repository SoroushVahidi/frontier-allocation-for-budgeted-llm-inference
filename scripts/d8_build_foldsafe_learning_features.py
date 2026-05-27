#!/usr/bin/env python3
"""Build D8 fold-safe candidate and pool feature tables from unified learning tables.

No API calls. Offline only.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold

METHODS = [
    "direct_reserve_semantic_frontier_v2",
    "external_l1_max",
    "external_s1_budget_forcing",
    "external_tale_prompt_budgeting",
]
METHOD_ALIAS = {
    "direct_reserve_semantic_frontier_v2": "frontier",
    "external_l1_max": "l1",
    "external_s1_budget_forcing": "s1",
    "external_tale_prompt_budgeting": "tale",
}


def bool_int(x: Any) -> int:
    if isinstance(x, bool):
        return int(x)
    if x is None:
        return 0
    s = str(x).strip().lower()
    if s in {"1", "true", "yes"}:
        return 1
    if s in {"0", "false", "no", "", "nan", "none"}:
        return 0
    try:
        return int(float(s) != 0.0)
    except Exception:
        return 0


def safe_float(x: Any, d: float = 0.0) -> float:
    try:
        if pd.isna(x):
            return d
        return float(x)
    except Exception:
        return d


def logit(p: float) -> float:
    p = min(max(float(p), 1e-6), 1.0 - 1e-6)
    return float(math.log(p / (1.0 - p)))


def smoothed_rate(correct: float, n: float, prior: float, alpha: float) -> float:
    return float((correct + alpha * prior) / (n + alpha))


def method_pair_key(a: str, b: str) -> str:
    aa = METHOD_ALIAS.get(a, a)
    bb = METHOD_ALIAS.get(b, b)
    return f"{aa}_vs_{bb}"


def load_data(unified_dir: Path, baseline_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    cand = pd.read_csv(unified_dir / "unified_candidate_action_table.csv")
    base = pd.read_csv(baseline_dir / "corrected_baseline_pool_decisions.csv")

    cand = cand[cand["method"].isin(METHODS)].copy()
    cand["candidate_correct"] = cand["candidate_correct"].map(bool_int)

    keep = [
        "pool_id",
        "scenario_id",
        "provider",
        "dataset",
        "split",
        "select_frontier_correct",
        "select_l1_correct",
        "select_s1_correct",
        "select_tale_correct",
        "pooled4_plurality_correct",
        "agreement_largest_cluster_correct",
        "agreement_strict_2plus_correct",
        "oracle_correct",
    ]
    base = base[[c for c in keep if c in base.columns]].copy()
    for c in [c for c in base.columns if c.endswith("_correct")]:
        base[c] = pd.to_numeric(base[c], errors="coerce").fillna(0).astype(int)

    return cand, base


def map_pool_labels(cand: pd.DataFrame, base: pd.DataFrame) -> pd.DataFrame:
    b = base.copy()
    b["oracle_available"] = b.get("oracle_correct", 0).map(bool_int)
    b["all_sources_wrong"] = 1 - b["oracle_available"]
    pool_lbl = b[["pool_id", "scenario_id", "provider", "dataset", "split", "oracle_available", "all_sources_wrong"]].drop_duplicates(
        "pool_id"
    )
    out = cand.merge(pool_lbl, on=["pool_id", "scenario_id", "provider", "dataset", "split"], how="left")
    out["oracle_available"] = out["oracle_available"].fillna(0).astype(int)
    out["all_sources_wrong"] = out["all_sources_wrong"].fillna(0).astype(int)
    return out


def apply_foldsafe_features(df: pd.DataFrame, alpha: float = 20.0, random_state: int = 42) -> pd.DataFrame:
    out = df.copy()

    rel_cols = [
        "rel_scenario_method_acc_foldsafe",
        "rel_scenario_method_logodds_foldsafe",
        "rel_dataset_method_acc_foldsafe",
        "rel_provider_method_acc_foldsafe",
        "rel_unique_correct_rate_scenario_method_foldsafe",
    ]
    comp_cols = []
    for m in METHODS:
        a = METHOD_ALIAS[m]
        comp_cols.extend(
            [
                f"comp_disagree_rate_{a}_foldsafe",
                f"comp_rescue_rate_{a}_foldsafe",
            ]
        )

    for c in rel_cols + comp_cols:
        out[c] = np.nan

    train = out[out["split"] == "train"].copy()
    if train.empty:
        for c in rel_cols + comp_cols:
            out[c] = out[c].fillna(0.5)
        return out

    global_rate = float(train["candidate_correct"].mean())

    # unique-correct per pool/method in each source fold
    def fill_apply(src: pd.DataFrame, apply: pd.DataFrame) -> pd.DataFrame:
        src = src.copy()
        apply = apply.copy()

        # reliability maps
        g_sm = src.groupby(["scenario_id", "method"])["candidate_correct"].agg(["sum", "count"]).reset_index()
        g_dm = src.groupby(["dataset", "method"])["candidate_correct"].agg(["sum", "count"]).reset_index()
        g_pm = src.groupby(["provider", "method"])["candidate_correct"].agg(["sum", "count"]).reset_index()

        map_sm = {
            (r["scenario_id"], r["method"]): smoothed_rate(float(r["sum"]), float(r["count"]), global_rate, alpha)
            for _, r in g_sm.iterrows()
        }
        map_dm = {
            (r["dataset"], r["method"]): smoothed_rate(float(r["sum"]), float(r["count"]), global_rate, alpha)
            for _, r in g_dm.iterrows()
        }
        map_pm = {
            (r["provider"], r["method"]): smoothed_rate(float(r["sum"]), float(r["count"]), global_rate, alpha)
            for _, r in g_pm.iterrows()
        }

        pool_m = src.pivot_table(index="pool_id", columns="method", values="candidate_correct", aggfunc="max").fillna(0)
        for m in METHODS:
            if m not in pool_m.columns:
                pool_m[m] = 0

        # unique-correct maps
        unique_rows = []
        for pid, row in pool_m.iterrows():
            if row.sum() == 1:
                m = row[row == 1].index[0]
                unique_rows.append((pid, m, 1))
            else:
                for m in METHODS:
                    unique_rows.append((pid, m, 0))
        unique_df = pd.DataFrame(unique_rows, columns=["pool_id", "method", "unique_correct"])
        src_u = src[["pool_id", "scenario_id", "method"]].drop_duplicates().merge(unique_df, on=["pool_id", "method"], how="left")
        map_unique = (
            src_u.groupby(["scenario_id", "method"])["unique_correct"].mean().to_dict()
            if not src_u.empty
            else {}
        )

        # complementarity maps by scenario and method pair
        # disagreement and ordered rescue P(m correct | other wrong)
        comp_dis = {}
        comp_res = {}
        comp_prior = 0.5
        for scen, g in src.groupby("scenario_id"):
            pm = g.pivot_table(index="pool_id", columns="method", values="candidate_correct", aggfunc="max").fillna(0)
            for m in METHODS:
                if m not in pm.columns:
                    pm[m] = 0
            for m in METHODS:
                for o in METHODS:
                    if m == o:
                        continue
                    mm = pm[m].values
                    oo = pm[o].values
                    disagree = float(np.mean(mm != oo)) if len(pm) else 0.0
                    denom = float(np.sum(oo == 0))
                    rescue = float(np.sum((mm == 1) & (oo == 0)) / denom) if denom > 0 else comp_prior
                    comp_dis[(scen, m, o)] = disagree
                    comp_res[(scen, m, o)] = rescue

        # fill apply rows
        vals = []
        for _, r in apply.iterrows():
            scen = r["scenario_id"]
            meth = r["method"]
            ds = r["dataset"]
            prov = r["provider"]

            sm = map_sm.get((scen, meth), global_rate)
            dm = map_dm.get((ds, meth), sm)
            pmr = map_pm.get((prov, meth), dm)
            uq = map_unique.get((scen, meth), 0.0)

            row = {
                "rel_scenario_method_acc_foldsafe": sm,
                "rel_scenario_method_logodds_foldsafe": logit(sm),
                "rel_dataset_method_acc_foldsafe": dm,
                "rel_provider_method_acc_foldsafe": pmr,
                "rel_unique_correct_rate_scenario_method_foldsafe": uq,
            }

            for om in METHODS:
                a = METHOD_ALIAS[om]
                row[f"comp_disagree_rate_{a}_foldsafe"] = comp_dis.get((scen, meth, om), 0.5)
                row[f"comp_rescue_rate_{a}_foldsafe"] = comp_res.get((scen, meth, om), 0.5)
            vals.append(row)

        filled = apply.copy()
        fill_df = pd.DataFrame(vals, index=apply.index)
        for c in fill_df.columns:
            filled[c] = fill_df[c]
        return filled

    train_idx = train.index.to_numpy()
    groups = train["pool_id"].to_numpy()
    n_groups = len(pd.unique(groups))
    if n_groups >= 2:
        n_splits = max(2, min(5, n_groups))
        gkf = GroupKFold(n_splits=n_splits)
        for tr_loc, va_loc in gkf.split(train_idx, groups=groups):
            src = train.iloc[tr_loc].copy()
            ap = train.iloc[va_loc].copy()
            filled = fill_apply(src, ap)
            out.loc[filled.index, rel_cols + comp_cols] = filled[rel_cols + comp_cols].values

    # train-full for non-train (validation/test/seen_dev)
    nontrain = out[out["split"] != "train"].copy()
    if not nontrain.empty:
        filled_nt = fill_apply(train, nontrain)
        out.loc[filled_nt.index, rel_cols + comp_cols] = filled_nt[rel_cols + comp_cols].values

    # fallback any remaining NaN
    for c in rel_cols + comp_cols:
        out[c] = pd.to_numeric(out[c], errors="coerce").fillna(0.5)

    return out


def build_pool_features(cand_feat: pd.DataFrame) -> pd.DataFrame:
    g = cand_feat.groupby(["pool_id", "scenario_id", "provider", "dataset", "split"], dropna=False)
    rows = []
    for (pid, scen, prov, ds, spl), sub in g:
        row = {
            "pool_id": pid,
            "scenario_id": scen,
            "provider": prov,
            "dataset": ds,
            "split": spl,
            "n_candidates": int(len(sub)),
            "n_distinct_clusters": int(pd.to_numeric(sub.get("distinct_answer_count", pd.Series([np.nan])), errors="coerce").max())
            if "distinct_answer_count" in sub.columns
            else int(sub.get("answer_cluster_id", pd.Series(dtype=str)).nunique()),
            "largest_cluster_size": float(pd.to_numeric(sub.get("max_cluster_size", pd.Series([np.nan])), errors="coerce").max())
            if "max_cluster_size" in sub.columns
            else float("nan"),
            "agreement_entropy": float(pd.to_numeric(sub.get("agreement_entropy", pd.Series([np.nan])), errors="coerce").mean())
            if "agreement_entropy" in sub.columns
            else float("nan"),
            "oracle_available": int(sub["oracle_available"].max()) if "oracle_available" in sub.columns else 0,
            "all_sources_wrong": int(sub["all_sources_wrong"].max()) if "all_sources_wrong" in sub.columns else 0,
        }
        for m in METHODS:
            ms = sub[sub["method"] == m]
            a = METHOD_ALIAS[m]
            if ms.empty:
                row[f"pool_rel_acc_{a}"] = 0.5
                row[f"pool_rel_logodds_{a}"] = 0.0
                row[f"pool_unique_rate_{a}"] = 0.0
            else:
                row[f"pool_rel_acc_{a}"] = float(ms["rel_scenario_method_acc_foldsafe"].iloc[0])
                row[f"pool_rel_logodds_{a}"] = float(ms["rel_scenario_method_logodds_foldsafe"].iloc[0])
                row[f"pool_unique_rate_{a}"] = float(ms["rel_unique_correct_rate_scenario_method_foldsafe"].iloc[0])
        rows.append(row)
    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--unified-dir", required=True)
    ap.add_argument("--baseline-dir", required=True)
    ap.add_argument("--output-dir", required=True)
    args = ap.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    unified_dir = Path(args.unified_dir)
    baseline_dir = Path(args.baseline_dir)

    cand, base = load_data(unified_dir, baseline_dir)
    cand = map_pool_labels(cand, base)
    cand_feat = apply_foldsafe_features(cand)

    # forbidden check
    forbidden = [
        "gold_answer_for_labeling_only",
        "candidate_correct",
        "candidate_correct_exact",
        "candidate_correct_combined",
        "source_correct_vector_json",
        "oracle_available",
        "all_sources_wrong",
        "candidate_in_correct_cluster",
        "candidate_is_unique_correct",
        "example_uid",
        "original_example_id",
        "question_hash",
    ]

    pool_feat = build_pool_features(cand_feat)

    cand_path = out_dir / "d8_candidate_features.csv"
    pool_path = out_dir / "d8_pool_features.csv"
    cand_feat.to_csv(cand_path, index=False)
    pool_feat.to_csv(pool_path, index=False)

    # schema
    schema = {
        "candidate_rows": int(len(cand_feat)),
        "pool_rows": int(pool_feat["pool_id"].nunique()),
        "candidate_columns": cand_feat.columns.tolist(),
        "pool_columns": pool_feat.columns.tolist(),
        "foldsafe_feature_columns": [c for c in cand_feat.columns if c.endswith("_foldsafe")],
        "forbidden_columns": forbidden,
        "notes": [
            "train rows use out-of-fold pool-grouped feature construction",
            "non-train rows use train-only statistics",
            "no API calls",
        ],
    }
    (out_dir / "d8_feature_schema.json").write_text(json.dumps(schema, indent=2))

    check = {
        "forbidden_in_candidate_table": [c for c in forbidden if c in cand_feat.columns],
        "forbidden_allowed_for_label_only": True,
        "runtime_feature_subset_requires_explicit_model_allowlist": True,
    }
    (out_dir / "d8_forbidden_columns_check.json").write_text(json.dumps(check, indent=2))

    rpt = [
        "# D8 Feature Build Report",
        "",
        f"- Unified input: `{unified_dir}`",
        f"- Corrected baseline input: `{baseline_dir}`",
        f"- Candidate rows: {len(cand_feat)}",
        f"- Pool rows: {pool_feat['pool_id'].nunique()}",
        f"- Scenarios: {cand_feat['scenario_id'].nunique()}",
        f"- Splits: {sorted(cand_feat['split'].dropna().astype(str).unique().tolist())}",
        "- Fold-safe features: scenario/dataset/provider method reliability + pairwise complementarity.",
        "- Leakage discipline: train OOF by pool_id; non-train uses train-only statistics.",
    ]
    (out_dir / "d8_feature_build_report.md").write_text("\n".join(rpt) + "\n")


if __name__ == "__main__":
    main()
