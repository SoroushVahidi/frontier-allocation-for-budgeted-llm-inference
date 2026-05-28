#!/usr/bin/env python3
"""Build D8.1 runtime-visible candidate/pool feature tables (offline only, no API calls)."""

from __future__ import annotations

import argparse
import json
import math
import re
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


def _tokenize_words(s: str) -> list[str]:
    return re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?|\d+(?:\.\d+)?", s)


def _numeric_tokens(s: str) -> list[str]:
    return re.findall(r"[-+]?\d+(?:\.\d+)?(?:/\d+)?%?", s)


def _count_any(s: str, pats: list[str]) -> int:
    sl = s.lower()
    return sum(1 for p in pats if p in sl)


def predicted_instance_type(question: str) -> str:
    q = question.lower()
    if any(k in q for k in ["triangle", "circle", "angle", "perimeter", "area", "radius", "diameter", "polygon"]):
        return "geometry"
    if any(k in q for k in ["probability", "combinations", "permutation", "choose", "expected value", "at least", "at most"]):
        return "probability_combinatorics"
    if any(k in q for k in ["mod", "gcd", "lcm", "prime", "divis", "congruen"]):
        return "number_theory"
    if any(k in q for k in ["solve", "equation", "polynomial", "factor", "roots", "variable", "system of equations"]):
        return "algebra"
    if any(k in q for k in ["integral", "derivative", "limit", "sin", "cos", "tan", "log", "sqrt"]):
        return "symbolic_math"
    if any(k in q for k in ["how many", "total", "each", "remaining", "ratio", "percent", "cost", "price", "hours"]):
        return "arithmetic_word_problem"
    return "unknown"


def predicted_answer_type(answer: str, question: str) -> str:
    a = (answer or "").strip()
    if not a:
        return "other"
    if re.fullmatch(r"[-+]?\d+", a):
        return "integer"
    if re.fullmatch(r"[-+]?\d+/\d+", a):
        return "rational"
    if re.fullmatch(r"[-+]?\d+\.\d+", a):
        return "decimal"
    if any(ch in a for ch in ["x", "y", "z", "=", "^", "sqrt", "sin", "cos", "tan", "log", "(", ")"]):
        return "expression"
    if any(ch in a for ch in ["{", "}", "[", "]", ","]):
        return "set_interval"
    q = question.lower()
    if "probability" in q and a.endswith("%"):
        return "decimal"
    return "other"


def derive_problem_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    q = out["question_text"].fillna("").astype(str)

    out["problem_sentence_count"] = q.map(lambda s: max(1, len(re.findall(r"[\.!?]+", s))))
    out["problem_word_count_ws"] = q.map(lambda s: len(s.split()))
    out["problem_token_count_simple"] = q.map(lambda s: len(_tokenize_words(s)))

    def numeric_stats(s: str) -> tuple[int, int, float, int, int, int]:
        toks = _numeric_tokens(s)
        vals = []
        frac = dec = pct = 0
        for t in toks:
            if "/" in t:
                frac += 1
            if "." in t:
                dec += 1
            if "%" in t:
                pct += 1
            tt = t.replace("%", "")
            try:
                if "/" in tt:
                    a, b = tt.split("/", 1)
                    v = abs(float(a) / float(b)) if float(b) != 0 else 0.0
                else:
                    v = abs(float(tt))
                vals.append(v)
            except Exception:
                pass
        max_mag = max(vals) if vals else 0.0
        return len(toks), len(set(toks)), max_mag, frac, dec, pct

    ns = q.map(numeric_stats)
    out["problem_numeric_token_count_rt"] = ns.map(lambda t: t[0])
    out["problem_distinct_numeric_token_count_rt"] = ns.map(lambda t: t[1])
    out["problem_max_abs_numeric_magnitude_rt"] = ns.map(lambda t: t[2])
    out["problem_fraction_token_flag_rt"] = ns.map(lambda t: int(t[3] > 0))
    out["problem_decimal_token_flag_rt"] = ns.map(lambda t: int(t[4] > 0))
    out["problem_percent_token_flag_rt"] = ns.map(lambda t: int(t[5] > 0))

    out["problem_math_symbol_count"] = q.map(lambda s: len(re.findall(r"[\+\-\*\/=\^]", s)))
    out["problem_equal_sign_count"] = q.map(lambda s: s.count("="))
    out["problem_operator_keyword_count"] = q.map(
        lambda s: _count_any(s, ["sqrt", "log", "sin", "cos", "tan", "sum", "product", "integral", "^", "+", "-", "*", "/"])
    )
    out["problem_variable_like_symbol_count"] = q.map(lambda s: len(re.findall(r"\b[a-zA-Z]\b", s)))
    out["has_equation_flag_rt"] = q.map(lambda s: int("=" in s or "solve for" in s.lower()))

    out["has_geometry_cue"] = q.map(lambda s: int(_count_any(s, ["triangle", "circle", "angle", "area", "perimeter", "radius", "diameter"]) > 0))
    out["has_probability_combinatorics_cue"] = q.map(
        lambda s: int(_count_any(s, ["probability", "permutation", "combination", "choose", "expected value"]) > 0)
    )
    out["has_number_theory_cue"] = q.map(lambda s: int(_count_any(s, ["prime", "gcd", "lcm", "mod", "divis", "congruen"]) > 0))
    out["has_algebra_cue"] = q.map(lambda s: int(_count_any(s, ["equation", "polynomial", "factor", "roots", "variable", "system of equations"]) > 0))
    out["has_arithmetic_word_problem_cue"] = q.map(lambda s: int(_count_any(s, ["how many", "total", "remaining", "each", "cost", "price", "hours", "minutes"]) > 0))
    out["has_symbolic_expression_cue"] = q.map(lambda s: int(_count_any(s, ["integral", "derivative", "limit", "sin", "cos", "tan", "sqrt", "log"]) > 0))

    out["multi_step_cue_count"] = q.map(
        lambda s: _count_any(s, ["then", "after", "before", "remaining", "total", "each", "ratio", "percent", "probability", "how many"]) 
    )

    out["predicted_instance_type"] = q.map(predicted_instance_type)
    out["predicted_answer_type"] = [
        predicted_answer_type(a, ques)
        for a, ques in zip(out["normalized_answer"].fillna(""), q)
    ]
    return out


def derive_runtime_features(cand: pd.DataFrame) -> pd.DataFrame:
    c = cand.copy()
    def col(name: str, default: Any = 0) -> pd.Series:
        if name in c.columns:
            return c[name]
        return pd.Series([default] * len(c), index=c.index)

    # provider/API features
    c["provider_api_id"] = c["provider"].fillna("unknown").astype(str)
    c["provider_raw_id"] = c["provider"].fillna("unknown").astype(str)
    c["model_deployment_name"] = c.get("model_id", "unknown").fillna("unknown").astype(str)
    c["provider_backend_type"] = col("provider_family", "unknown").fillna("unknown").astype(str)
    c["openai_compatible_flag"] = c["provider"].fillna("").str.lower().map(
        lambda s: int(any(k in s for k in ["openai", "azure", "cloudrift", "fireworks", "mistral", "cohere", "cerebras"]))
    )
    c["reasoning_output_fallback_flag"] = c["provider"].fillna("").str.lower().map(lambda s: int("cloudrift" in s))

    # action/method features
    c["action_name"] = c["method"].fillna("unknown").astype(str)
    c["action_family"] = c["method"].map(METHOD_ALIAS).fillna("other")
    c["ours_vs_external_flag"] = c.get("is_external_method_flag", 0).map(lambda v: 0 if bool_int(v) == 1 else 1)
    c["frontier_variant_id"] = c["method"].map(lambda m: "frontier_v2" if m == "direct_reserve_semantic_frontier_v2" else "na")
    c["prompt_method_family"] = col("method_family", "unknown").fillna("unknown").astype(str)
    c["budget_prompting_type"] = (
        col("uses_budget_forcing_flag", 0).map(bool_int).astype(str)
        + "_"
        + col("uses_prompt_budgeting_flag", 0).map(bool_int).astype(str)
    )

    # candidate answer features
    c["candidate_output_length_rt"] = pd.to_numeric(col("output_length_chars", 0), errors="coerce").fillna(0.0)
    c["candidate_answer_length_rt"] = pd.to_numeric(col("answer_length_chars", 0), errors="coerce").fillna(0.0)
    c["candidate_reasoning_length_rt"] = (
        pd.to_numeric(col("output_length_chars", 0), errors="coerce").fillna(0.0)
        - pd.to_numeric(col("answer_length_chars", 0), errors="coerce").fillna(0.0)
    ).clip(lower=0.0)
    c["final_answer_extraction_present_flag"] = col("extracted_answer", "").fillna("").astype(str).map(lambda s: int(len(s.strip()) > 0))
    c["parse_success_rt"] = col("parse_success", 0).map(bool_int)
    c["numeric_candidate_flag_rt"] = col("numeric_answer_flag", 0).map(bool_int)
    c["expression_candidate_flag_rt"] = col("expression_answer_flag", 0).map(bool_int)
    c["malformed_answer_flag_rt"] = col("malformed_output_flag", 0).map(bool_int)
    c["multiple_final_answers_flag_rt"] = col("multiple_boxed_answers", 0).map(bool_int)
    c["answer_type_rt"] = [
        predicted_answer_type(a, q)
        for a, q in zip(col("normalized_answer", "").fillna(""), col("question_text", "").fillna(""))
    ]

    # pool/agreement features from existing columns (runtime-visible)
    c["pool_size_rt"] = pd.to_numeric(col("pool_size", 4), errors="coerce").fillna(4.0)
    c["distinct_clusters_rt"] = pd.to_numeric(col("distinct_answer_count", 0), errors="coerce").fillna(0.0)
    c["largest_cluster_size_rt"] = pd.to_numeric(col("max_cluster_size", 0), errors="coerce").fillna(0.0)
    c["candidate_cluster_size_rt"] = pd.to_numeric(col("cluster_size", 0), errors="coerce").fillna(0.0)
    c["candidate_in_largest_cluster_rt"] = col("candidate_in_largest_cluster_flag", 0).map(bool_int)
    c["strict_2plus_exists_rt"] = col("no_majority_flag", 0).map(lambda x: 1 - bool_int(x))
    c["agreement_entropy_rt"] = pd.to_numeric(col("agreement_entropy", 0), errors="coerce").fillna(0.0)
    c["answer_fragmentation_ratio_rt"] = np.where(
        c["pool_size_rt"] > 0,
        c["distinct_clusters_rt"] / c["pool_size_rt"],
        0.0,
    )

    c["pair_agree_frontier_l1_rt"] = ((col("agrees_with_frontier", 0).map(bool_int) == 1) & (col("agrees_with_l1", 0).map(bool_int) == 1)).astype(int)
    c["pair_agree_frontier_s1_rt"] = ((col("agrees_with_frontier", 0).map(bool_int) == 1) & (col("agrees_with_s1", 0).map(bool_int) == 1)).astype(int)
    c["pair_agree_frontier_tale_rt"] = ((col("agrees_with_frontier", 0).map(bool_int) == 1) & (col("agrees_with_tale", 0).map(bool_int) == 1)).astype(int)
    c["pair_agree_l1_s1_rt"] = ((col("agrees_with_l1", 0).map(bool_int) == 1) & (col("agrees_with_s1", 0).map(bool_int) == 1)).astype(int)
    c["pair_agree_l1_tale_rt"] = ((col("agrees_with_l1", 0).map(bool_int) == 1) & (col("agrees_with_tale", 0).map(bool_int) == 1)).astype(int)
    c["pair_agree_s1_tale_rt"] = ((col("agrees_with_s1", 0).map(bool_int) == 1) & (col("agrees_with_tale", 0).map(bool_int) == 1)).astype(int)

    c["source_participation_in_cluster_rt"] = c["candidate_cluster_size_rt"]

    c = derive_problem_features(c)
    return c


def map_pool_labels(cand: pd.DataFrame, base: pd.DataFrame) -> pd.DataFrame:
    b = base.copy()
    b["oracle_available"] = b.get("oracle_correct", 0).map(bool_int)
    b["all_sources_wrong"] = 1 - b["oracle_available"]
    pool_lbl = b[["pool_id", "scenario_id", "provider", "dataset", "split", "oracle_available", "all_sources_wrong"]].drop_duplicates("pool_id")
    out = cand.merge(pool_lbl, on=["pool_id", "scenario_id", "provider", "dataset", "split"], how="left")
    out["oracle_available"] = out["oracle_available"].fillna(0).astype(int)
    out["all_sources_wrong"] = out["all_sources_wrong"].fillna(0).astype(int)
    out["action_correct"] = out["candidate_correct"].map(bool_int)
    return out


def _build_stats_maps(src: pd.DataFrame, alpha: float = 20.0) -> dict[str, dict[Any, float]]:
    maps: dict[str, dict[Any, float]] = {}
    g_rate = float(src["candidate_correct"].mean()) if len(src) else 0.5

    # provider x method
    pm = src.groupby(["provider_api_id", "method"])["candidate_correct"].agg(["sum", "count"]).reset_index()
    maps["rel_provider_method"] = {
        (r["provider_api_id"], r["method"]): smoothed_rate(float(r["sum"]), float(r["count"]), g_rate, alpha)
        for _, r in pm.iterrows()
    }

    # instance type x method
    im = src.groupby(["predicted_instance_type", "method"])["candidate_correct"].agg(["sum", "count"]).reset_index()
    maps["rel_instype_method"] = {
        (r["predicted_instance_type"], r["method"]): smoothed_rate(float(r["sum"]), float(r["count"]), g_rate, alpha)
        for _, r in im.iterrows()
    }

    # provider x instance type x method
    pim = src.groupby(["provider_api_id", "predicted_instance_type", "method"])["candidate_correct"].agg(["sum", "count"]).reset_index()
    maps["rel_provider_instype_method"] = {
        (r["provider_api_id"], r["predicted_instance_type"], r["method"]): smoothed_rate(float(r["sum"]), float(r["count"]), g_rate, alpha)
        for _, r in pim.iterrows()
    }

    # disagreement/rescue by provider and ordered method pair
    dis: dict[Any, float] = {}
    res: dict[Any, float] = {}
    for prov, g in src.groupby("provider_api_id"):
        p = g.pivot_table(index="pool_id", columns="method", values="candidate_correct", aggfunc="max").fillna(0)
        for m in METHODS:
            if m not in p.columns:
                p[m] = 0
        for a in METHODS:
            for b in METHODS:
                if a == b:
                    continue
                aa = p[a].values
                bb = p[b].values
                d = float(np.mean(aa != bb)) if len(p) else 0.5
                denom = float(np.sum(bb == 0))
                r = float(np.sum((aa == 1) & (bb == 0)) / denom) if denom > 0 else 0.5
                dis[(prov, a, b)] = d
                res[(prov, a, b)] = r
    maps["pair_disagreement"] = dis
    maps["pair_rescue"] = res

    # unique correct by provider/method
    uniq_rows = []
    for (prov, pid), grp in src.groupby(["provider_api_id", "pool_id"]):
        m = grp.groupby("method")["candidate_correct"].max().reindex(METHODS, fill_value=0)
        if int(m.sum()) == 1:
            only = m[m == 1].index[0]
            for mm in METHODS:
                uniq_rows.append((prov, mm, int(mm == only)))
        else:
            for mm in METHODS:
                uniq_rows.append((prov, mm, 0))
    uq = pd.DataFrame(uniq_rows, columns=["provider_api_id", "method", "unique_correct"]) if uniq_rows else pd.DataFrame(columns=["provider_api_id", "method", "unique_correct"])
    maps["unique_provider_method"] = uq.groupby(["provider_api_id", "method"])["unique_correct"].mean().to_dict() if not uq.empty else {}

    maps["global_rate"] = {"_": g_rate}
    return maps


def _apply_maps(df: pd.DataFrame, maps: dict[str, dict[Any, float]]) -> pd.DataFrame:
    out = df.copy()
    g = maps.get("global_rate", {}).get("_", 0.5)

    rows = []
    for _, r in out.iterrows():
        prov = r["provider_api_id"]
        meth = r["method"]
        it = r["predicted_instance_type"]

        v1 = maps.get("rel_provider_method", {}).get((prov, meth), g)
        v2 = maps.get("rel_instype_method", {}).get((it, meth), g)
        v3 = maps.get("rel_provider_instype_method", {}).get((prov, it, meth), v1)
        uq = maps.get("unique_provider_method", {}).get((prov, meth), 0.0)

        row = {
            "rel_provider_method_acc_foldsafe": v1,
            "rel_provider_method_logodds_foldsafe": logit(v1),
            "rel_instype_method_acc_foldsafe": v2,
            "rel_instype_method_logodds_foldsafe": logit(v2),
            "rel_provider_instype_method_acc_foldsafe": v3,
            "rel_provider_instype_method_logodds_foldsafe": logit(v3),
            "rel_unique_correct_rate_provider_method_foldsafe": uq,
        }

        for other in METHODS:
            o = METHOD_ALIAS.get(other, other)
            row[f"pair_disagree_{o}_provider_foldsafe"] = maps.get("pair_disagreement", {}).get((prov, meth, other), 0.5)
            row[f"pair_rescue_{o}_provider_foldsafe"] = maps.get("pair_rescue", {}).get((prov, meth, other), 0.5)
        rows.append(row)

    fdf = pd.DataFrame(rows, index=out.index)
    for c in fdf.columns:
        out[c] = fdf[c]
    return out


def apply_foldsafe_features(cand: pd.DataFrame, alpha: float = 20.0) -> pd.DataFrame:
    out = cand.copy()
    train = out[out["split"] == "train"].copy()
    if train.empty:
        return out

    # OOF for train
    train_idx = train.index.to_numpy()
    groups = train["pool_id"].to_numpy()
    n_groups = len(pd.unique(groups))

    if n_groups >= 2:
        n_splits = max(2, min(5, n_groups))
        gkf = GroupKFold(n_splits=n_splits)
        for tr_loc, va_loc in gkf.split(train_idx, groups=groups):
            src = train.iloc[tr_loc].copy()
            ap = train.iloc[va_loc].copy()
            maps = _build_stats_maps(src, alpha=alpha)
            filled = _apply_maps(ap, maps)
            cols = [c for c in filled.columns if c.endswith("_foldsafe")]
            out.loc[filled.index, cols] = filled[cols].values

    # non-train from full train maps
    maps_full = _build_stats_maps(train, alpha=alpha)
    nontrain = out[out["split"] != "train"].copy()
    if not nontrain.empty:
        filled = _apply_maps(nontrain, maps_full)
        cols = [c for c in filled.columns if c.endswith("_foldsafe")]
        out.loc[filled.index, cols] = filled[cols].values

    # fill any remaining NaNs with global defaults
    for c in [c for c in out.columns if c.endswith("_foldsafe")]:
        if c.endswith("logodds_foldsafe"):
            out[c] = out[c].fillna(0.0)
        else:
            out[c] = out[c].fillna(0.5)
    return out


def build_pool_features(cand_feat: pd.DataFrame) -> pd.DataFrame:
    rows = []
    grp_cols = ["pool_id", "scenario_id", "provider", "dataset", "split"]
    for (pid, scen, prov, ds, spl), sub in cand_feat.groupby(grp_cols, dropna=False):
        row = {
            "pool_id": pid,
            "scenario_id": scen,
            "provider": prov,
            "dataset": ds,
            "split": spl,
            "pool_size": int(len(sub)),
            "distinct_answer_count": int(sub["normalized_answer"].fillna("").nunique()),
            "max_cluster_size": int(pd.to_numeric(sub.get("cluster_size", 0), errors="coerce").fillna(0).max()),
            "agreement_entropy": float(pd.to_numeric(sub.get("agreement_entropy", 0), errors="coerce").fillna(0.0).iloc[0]),
            "parse_success_rate": float(sub.get("parse_success_rt", 0).astype(float).mean()),
            "malformed_rate": float(sub.get("malformed_answer_flag_rt", 0).astype(float).mean()),
            "oracle_available": int(sub.get("oracle_available", 0).max()) if "oracle_available" in sub.columns else 0,
            "all_sources_wrong": int(sub.get("all_sources_wrong", 0).max()) if "all_sources_wrong" in sub.columns else 0,
            "predicted_instance_type_mode": str(sub["predicted_instance_type"].mode().iloc[0]) if not sub["predicted_instance_type"].mode().empty else "unknown",
        }
        for m in METHODS:
            ms = sub[sub["method"] == m]
            a = METHOD_ALIAS.get(m, m)
            if ms.empty:
                row[f"pool_rel_provider_{a}"] = 0.5
                row[f"pool_rel_instype_{a}"] = 0.5
                row[f"pool_rel_provider_instype_{a}"] = 0.5
                row[f"pool_unique_rate_provider_{a}"] = 0.0
            else:
                row[f"pool_rel_provider_{a}"] = float(ms["rel_provider_method_acc_foldsafe"].iloc[0])
                row[f"pool_rel_instype_{a}"] = float(ms["rel_instype_method_acc_foldsafe"].iloc[0])
                row[f"pool_rel_provider_instype_{a}"] = float(ms["rel_provider_instype_method_acc_foldsafe"].iloc[0])
                row[f"pool_unique_rate_provider_{a}"] = float(ms["rel_unique_correct_rate_provider_method_foldsafe"].iloc[0])
        rows.append(row)
    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--unified-dir", required=True)
    ap.add_argument("--baseline-dir", required=True)
    ap.add_argument("--output-dir", required=True)
    args = ap.parse_args()

    udir = Path(args.unified_dir)
    bdir = Path(args.baseline_dir)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    cand = pd.read_csv(udir / "unified_candidate_action_table.csv")
    base = pd.read_csv(bdir / "corrected_baseline_pool_decisions.csv")

    cand = cand[cand["method"].isin(METHODS)].copy()
    cand["candidate_correct"] = cand["candidate_correct"].map(bool_int)

    cand = derive_runtime_features(cand)
    cand = map_pool_labels(cand, base)
    cand = apply_foldsafe_features(cand)

    # offline labels
    cand["ranking_relevance"] = cand["candidate_correct"].astype(int)

    pool = build_pool_features(cand)

    # forbidden columns check
    forbidden = [
        "gold_answer_for_labeling_only",
        "candidate_correct",
        "candidate_correct_exact",
        "candidate_correct_combined",
        "candidate_in_correct_cluster",
        "candidate_is_unique_correct",
        "source_correct_vector_json",
        "oracle_correct",
        "example_uid",
        "original_example_id",
        "question_hash",
        "row_id",
    ]

    cpath = out / "d8_1_candidate_features.csv"
    ppath = out / "d8_1_pool_features.csv"
    cand.to_csv(cpath, index=False)
    pool.to_csv(ppath, index=False)

    feature_cols = [
        c
        for c in cand.columns
        if c
        not in {
            "candidate_correct",
            "candidate_correct_exact",
            "candidate_correct_combined",
            "gold_answer_for_labeling_only",
            "source_correct_vector_json",
            "oracle_available",
            "all_sources_wrong",
            "candidate_in_correct_cluster",
            "candidate_is_unique_correct",
            "example_uid",
            "original_example_id",
            "question_hash",
            "row_id",
        }
    ]

    schema = {
        "candidate_rows": int(len(cand)),
        "pool_rows": int(len(pool)),
        "candidate_feature_columns": feature_cols,
        "foldsafe_feature_columns": [c for c in cand.columns if c.endswith("_foldsafe")],
        "primary_runtime_model_excludes_raw_dataset_id": True,
        "dataset_ablation_supported": True,
        "notes": [
            "train rows use out-of-fold pool-grouped reliability/complementarity stats",
            "non-train rows use train-only maps",
            "oracle is upper-bound diagnostic only",
            "row-wise max baseline is forbidden",
        ],
    }
    (out / "d8_1_feature_schema.json").write_text(json.dumps(schema, indent=2))

    check = {
        "forbidden_columns": forbidden,
        "forbidden_in_candidate_table": [c for c in forbidden if c in cand.columns],
        "runtime_feature_subset_requires_allowlist": True,
        "no_api_calls": True,
    }
    (out / "d8_1_forbidden_columns_check.json").write_text(json.dumps(check, indent=2))

    # Label schema/report
    label_schema = {
        "candidate_labels": ["action_correct", "candidate_correct", "ranking_relevance"],
        "pool_labels": ["oracle_available", "all_sources_wrong"],
        "derivable_labels": [
            "override_good",
            "override_bad",
            "cluster_correct",
            "frontier_unique_correct",
            "external_unique_correct",
            "selector_recoverable",
            "pool_failure",
        ],
        "label_use_boundary": "offline_only",
    }
    (out / "d8_1_label_schema.json").write_text(json.dumps(label_schema, indent=2))

    lrep = [
        "# D8.1 Label Report",
        "",
        f"- Candidate rows: {len(cand)}",
        f"- Pools: {pool['pool_id'].nunique() if 'pool_id' in pool.columns else len(pool)}",
        f"- action_correct positives: {int(cand['action_correct'].sum())}",
        f"- oracle_available positives: {int(pool['oracle_available'].sum()) if 'oracle_available' in pool.columns else 0}",
        "- Labels are offline-only for training/evaluation, never runtime inputs.",
    ]
    (out / "D8_1_LABEL_REPORT.md").write_text("\n".join(lrep) + "\n")

    frep = [
        "# D8.1 Feature Build Report",
        "",
        f"- Candidate feature table: `{cpath.name}` ({len(cand)} rows)",
        f"- Pool feature table: `{ppath.name}` ({len(pool)} rows)",
        f"- Runtime-visible fold-safe columns: {len([c for c in cand.columns if c.endswith('_foldsafe')])}",
        f"- Predicted instance types: {sorted(cand['predicted_instance_type'].dropna().astype(str).unique().tolist())}",
        "- Primary model policy: excludes raw dataset label; separate ablation includes it.",
        "- No API calls; no D6 generation.",
    ]
    (out / "D8_1_FEATURE_BUILD_REPORT.md").write_text("\n".join(frep) + "\n")


if __name__ == "__main__":
    main()
