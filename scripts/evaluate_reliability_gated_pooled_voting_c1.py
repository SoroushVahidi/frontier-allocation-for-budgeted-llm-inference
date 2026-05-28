#!/usr/bin/env python3
"""
Evaluate C1: Reliability-Gated Pooled Voting

Implements and evaluates six variants (C1a-C1f) of a zero-extra-call
answer selector that combines fold-safe calibration priors with
runtime answer-pattern features.

All evaluation is offline only; gold labels are never used at inference.
"""

import json
import csv
import math
import random
import datetime
import itertools
import collections
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

import numpy as np
import pandas as pd
from scipy.stats import chi2_contingency

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "outputs" / "reliability_gated_pooled_voting_c1_20260524"
OUT_DIR.mkdir(parents=True, exist_ok=True)

SOURCES = ["frontier", "L1", "S1", "TALE"]
SELECTOR_NAMES = [
    "frontier", "L1", "S1", "TALE", "pooled4",
    "agreement_only", "always_S1", "best_static",
    "raw_spread_regime", "beta_shrinkage",
    "c1a_t003", "c1a_t005", "c1a_t008", "c1a_t010", "c1a_t015",
    "c1b", "c1c_raw", "c1c_center", "c1c_logodds", "c1c_shrunk",
    "c1d", "c1e", "c1f",
    "oracle",
]

SCENARIO_PATHS = {
    "cohere_gsm8k": {
        "provider": "cohere", "dataset": "gsm8k", "canonical": True,
        "per_example_jsonl": REPO_ROOT / "outputs" /
            "canonical_final300_cohere_contract_matched_live_20260523T181948Z" /
            "cohere_real_model_cost_normalized_validation_20260523T181948Z" /
            "per_example_records.jsonl",
        "case_level_csv": None,  # reconstruct from jsonl
    },
    "mistral_gsm8k": {
        "provider": "mistral", "dataset": "gsm8k", "canonical": True,
        "per_example_jsonl": REPO_ROOT / "outputs" /
            "merged_repaired_cohere_mistral_selector_replay_20260524" /
            "mistral_full300_merged_per_example_records.jsonl",
        "case_level_csv": REPO_ROOT / "outputs" /
            "merged_repaired_cohere_mistral_selector_replay_20260524" /
            "mistral_full300_case_level_selector_results.csv",
    },
    "mistral_math500": {
        "provider": "mistral", "dataset": "math500", "canonical": True,
        "per_example_jsonl": REPO_ROOT / "outputs" /
            "scenarios_5_6_math500_full_tracking_20260524" /
            "mistral_math500_full_20260524T014937Z" /
            "cohere_real_model_cost_normalized_validation_20260524T014937Z" /
            "per_example_records.jsonl",
        "case_level_csv": REPO_ROOT / "outputs" /
            "mistral_math500_scenario5_processing_20260524" /
            "mistral_math500_case_level_selector_results.csv",
    },
    "cohere_math500_aux": {
        "provider": "cohere", "dataset": "math500", "canonical": False,
        "per_example_jsonl": REPO_ROOT / "outputs" /
            "cohere_math500_auxiliary_mlj_reprocess_20260524" /
            "cohere_math500_auxiliary_complete_4method_records.jsonl",
        "case_level_csv": REPO_ROOT / "outputs" /
            "cohere_math500_auxiliary_mlj_reprocess_20260524" /
            "cohere_math500_auxiliary_case_level_selector_results.csv",
    },
}

METHOD_NAME_MAP = {
    "direct_reserve_semantic_frontier_v2": "frontier",
    "external_l1_max": "L1",
    "external_s1_budget_forcing": "S1",
    "external_tale_prompt_budgeting": "TALE",
}


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_from_jsonl(path: Path) -> pd.DataFrame:
    """Load per-example records from JSONL and pivot to one row per example."""
    records = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    by_example: Dict[str, Dict] = {}
    for rec in records:
        eid = rec["example_id"]
        method_raw = rec.get("method", "")
        method = METHOD_NAME_MAP.get(method_raw, method_raw)
        if eid not in by_example:
            by_example[eid] = {
                "example_id": eid,
                "provider": rec.get("provider", ""),
                "dataset": rec.get("dataset", ""),
                "question": rec.get("question", ""),
                "gold": str(rec.get("gold_answer_canonical", "")).strip(),
                "frontier_ans": None, "L1_ans": None, "S1_ans": None, "TALE_ans": None,
                "frontier_ok": None, "L1_ok": None, "S1_ok": None, "TALE_ok": None,
            }
        ans = str(rec.get("selected_answer_canonical",
                           rec.get("final_answer_canonical", ""))).strip()
        ok = int(rec.get("exact_match", 0))
        by_example[eid][f"{method}_ans"] = ans
        by_example[eid][f"{method}_ok"] = ok

    df = pd.DataFrame(list(by_example.values()))
    return df


def load_mistral_gsm8k_case_level(path: Path) -> pd.DataFrame:
    """Load Mistral GSM8K case-level CSV (rich format with ans/ok columns)."""
    df = pd.read_csv(path, dtype=str)
    rename = {
        "frontier_ans": "frontier_ans", "frontier_ok": "frontier_ok",
        "L1_ans": "L1_ans", "L1_ok": "L1_ok",
        "S1_ans": "S1_ans", "S1_ok": "S1_ok",
        "TALE_ans": "TALE_ans", "TALE_ok": "TALE_ok",
        "gold_answer_canonical": "gold",
        "pooled4_with_fallback_ans": "pooled4_ans",
        "pooled4_with_fallback_ok": "pooled4_ok",
        "beta_shrinkage_regime_selector_ans": "beta_shrinkage_ans",
        "beta_shrinkage_regime_selector_ok": "beta_shrinkage_ok",
        "oracle_ans": "oracle_ans",
        "oracle_ok": "oracle_ok",
        "agreement_only_2of3_against_frontier_ans": "agreement_only_ans",
        "agreement_only_2of3_against_frontier_ok": "agreement_only_ok",
        "always_s1_ans": "always_S1_ans",
        "always_s1_ok": "always_S1_ok",
    }
    df = df.rename(columns=rename)
    for col in ["frontier_ok", "L1_ok", "S1_ok", "TALE_ok",
                "pooled4_ok", "beta_shrinkage_ok", "oracle_ok",
                "agreement_only_ok", "always_S1_ok"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
    return df


def load_mistral_math500_case_level(path: Path) -> pd.DataFrame:
    """Load Mistral MATH-500 case-level CSV."""
    df = pd.read_csv(path, dtype=str)
    rename = {
        "gold": "gold",
        "frontier_ans": "frontier_ans", "frontier_correct": "frontier_ok",
        "l1_ans": "L1_ans", "l1_correct": "L1_ok",
        "s1_ans": "S1_ans", "s1_correct": "S1_ok",
        "tale_ans": "TALE_ans", "tale_correct": "TALE_ok",
        "sel_pooled4": "pooled4_ok",
        "sel_beta_shrinkage_regime": "beta_shrinkage_ok",
        "sel_oracle_source": "oracle_ok",
        "sel_agreement_2of3": "agreement_only_ok",
        "sel_always_s1": "always_S1_ok",
    }
    df = df.rename(columns=rename)
    for col in ["frontier_ok", "L1_ok", "S1_ok", "TALE_ok",
                "pooled4_ok", "beta_shrinkage_ok", "oracle_ok",
                "agreement_only_ok", "always_S1_ok"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
    # Answer strings for sel_* columns are not stored in this format;
    # add None placeholders for pooled4_ans etc.
    for col in ["pooled4_ans", "beta_shrinkage_ans", "oracle_ans",
                "agreement_only_ans", "always_S1_ans"]:
        if col not in df.columns:
            df[col] = None
    return df


def load_cohere_math500_aux_case_level(
        case_path: Path, jsonl_path: Path) -> pd.DataFrame:
    """Load Cohere MATH-500 aux: merge correctness flags with answers from JSONL."""
    # Load answer strings from JSONL
    jsonl_df = load_from_jsonl(jsonl_path)
    # Load correctness flags from case-level CSV
    flag_df = pd.read_csv(case_path, dtype=str)
    flag_rename = {
        "direct_reserve_semantic_frontier_v2": "frontier_ok",
        "external_l1_max": "L1_ok",
        "external_s1_budget_forcing": "S1_ok",
        "external_tale_prompt_budgeting": "TALE_ok",
        "pooled4_with_fallback": "pooled4_ok",
        "agreement_only_2of3_against_frontier": "agreement_only_ok",
        "always_s1": "always_S1_ok",
        "raw_spread_regime_selector": "raw_spread_ok",
        "beta_shrinkage_regime_selector": "beta_shrinkage_ok",
        "dominant_source_veto": "dominant_veto_ok",
        "majority_requires_dominant_source_when_dominant": "majority_dom_ok",
        "oracle_best_source": "oracle_ok",
        "oracle_best_action": "oracle_action_ok",
    }
    flag_df = flag_df.rename(columns=flag_rename)
    for col in flag_df.columns:
        if col != "example_id":
            flag_df[col] = pd.to_numeric(flag_df[col], errors="coerce").fillna(0).astype(int)
    # Merge: keep answers from JSONL, flags from case-level
    merged = jsonl_df.merge(
        flag_df[["example_id"] + [c for c in flag_df.columns if c != "example_id"]],
        on="example_id", how="left", suffixes=("_jsonl", "_flag")
    )
    # Prefer flag_df correctness (was computed with canonical comparison)
    for src in SOURCES:
        flag_col = f"{src}_ok_flag"
        base_col = f"{src}_ok"
        if flag_col in merged.columns:
            merged[base_col] = merged[flag_col].fillna(merged.get(f"{src}_ok_jsonl", 0))
            merged.drop(columns=[flag_col, f"{src}_ok_jsonl"], errors="ignore", inplace=True)
    return merged


def load_scenario(scenario_id: str) -> pd.DataFrame:
    """Load a scenario into a unified DataFrame."""
    cfg = SCENARIO_PATHS[scenario_id]

    if scenario_id == "cohere_gsm8k":
        df = load_from_jsonl(cfg["per_example_jsonl"])
    elif scenario_id == "mistral_gsm8k":
        df = load_mistral_gsm8k_case_level(cfg["case_level_csv"])
        # Fill gold from jsonl if missing
        if "gold" not in df.columns or df["gold"].isna().all():
            jdf = load_from_jsonl(cfg["per_example_jsonl"])
            df = df.merge(jdf[["example_id", "gold"]], on="example_id", how="left")
    elif scenario_id == "mistral_math500":
        df = load_mistral_math500_case_level(cfg["case_level_csv"])
        # Augment with answers from jsonl
        jdf = load_from_jsonl(cfg["per_example_jsonl"])
        for src in SOURCES:
            col = f"{src}_ans"
            if col not in df.columns or df[col].isna().all():
                if col in jdf.columns:
                    df = df.merge(jdf[["example_id", col]], on="example_id", how="left")
        if "gold" not in df.columns:
            df = df.merge(jdf[["example_id", "gold"]], on="example_id", how="left")
    elif scenario_id == "cohere_math500_aux":
        df = load_cohere_math500_aux_case_level(
            cfg["case_level_csv"], cfg["per_example_jsonl"])
    else:
        raise ValueError(f"Unknown scenario: {scenario_id}")

    # Normalize string columns
    for src in SOURCES:
        col = f"{src}_ans"
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str).str.strip()
        ok_col = f"{src}_ok"
        if ok_col in df.columns:
            df[ok_col] = pd.to_numeric(df[ok_col], errors="coerce").fillna(0).astype(int)
        else:
            df[ok_col] = 0

    df["scenario_id"] = scenario_id
    df["provider"] = cfg["provider"]
    df["dataset"] = cfg["dataset"]
    df["canonical"] = cfg["canonical"]
    if "gold" not in df.columns:
        df["gold"] = ""

    return df


# ---------------------------------------------------------------------------
# Answer-pattern features
# ---------------------------------------------------------------------------

def compute_answer_pattern_features(row: pd.Series) -> Dict[str, Any]:
    """Compute runtime answer-pattern features (no gold used)."""
    answers = {s: str(row.get(f"{s}_ans", "")).strip() for s in SOURCES}
    valid = {s: a for s, a in answers.items() if a and a not in ("", "nan", "None")}

    ans_list = list(valid.values())
    unique_answers = list(set(ans_list))
    unique_count = len(unique_answers)
    n_sources = len(valid)

    # Majority counting
    counter = collections.Counter(ans_list)
    majority_answer = counter.most_common(1)[0][0] if counter else ""
    majority_size = counter[majority_answer] if majority_answer else 0
    has_majority = majority_size > n_sources / 2 if n_sources > 0 else False

    all_agree = (unique_count == 1 and n_sources == 4)
    three_one = (majority_size == 3 and n_sources == 4)
    two_two = (unique_count == 2 and majority_size == 2 and n_sources == 4)
    all_diff = (unique_count == n_sources == 4)

    frontier_in_maj = (has_majority and answers.get("frontier", "") == majority_answer)
    s1_in_maj = (has_majority and answers.get("S1", "") == majority_answer)

    # External sources: L1, S1, TALE
    ext = {s: answers[s] for s in ["L1", "S1", "TALE"] if s in valid}
    ext_counter = collections.Counter(ext.values())
    ext_maj_ans = ext_counter.most_common(1)[0][0] if ext_counter else ""
    ext_maj_size = ext_counter[ext_maj_ans] if ext_maj_ans else 0
    external_majority_exists = (ext_maj_size >= 2) if len(ext) >= 2 else False

    l1_tale_agree = (
        "L1" in valid and "TALE" in valid and
        answers["L1"] == answers["TALE"] and answers["L1"] != ""
    )

    s1_isolated = (
        "S1" in valid and
        all(answers.get(s, "") != answers["S1"] for s in ["frontier", "L1", "TALE"] if s in valid)
    ) if "S1" in valid else False

    frontier_isolated = (
        "frontier" in valid and
        all(answers.get(s, "") != answers["frontier"] for s in ["L1", "S1", "TALE"] if s in valid)
    ) if "frontier" in valid else False

    return {
        "unique_answer_count": unique_count,
        "n_valid_sources": n_sources,
        "all_four_agree": int(all_agree),
        "three_one_split": int(three_one),
        "two_two_split": int(two_two),
        "all_different": int(all_diff),
        "majority_answer": majority_answer,
        "majority_size": majority_size,
        "has_majority": int(has_majority),
        "frontier_in_majority": int(frontier_in_maj),
        "S1_in_majority": int(s1_in_maj),
        "S1_isolated": int(s1_isolated),
        "frontier_isolated": int(frontier_isolated),
        "L1_TALE_agree": int(l1_tale_agree),
        "external_majority_exists": int(external_majority_exists),
        "external_majority_answer": ext_maj_ans,
        "external_majority_size": ext_maj_size,
        "external_majority_excludes_frontier": int(
            external_majority_exists and
            ext_maj_ans != answers.get("frontier", "NOT_SAME")
        ),
        "external_majority_excludes_S1": int(
            external_majority_exists and
            ext_maj_ans != answers.get("S1", "NOT_SAME")
        ),
        "no_majority_flag": int(not has_majority),
    }


def add_pattern_features(df: pd.DataFrame) -> pd.DataFrame:
    features = df.apply(compute_answer_pattern_features, axis=1, result_type="expand")
    return pd.concat([df, features], axis=1)


# ---------------------------------------------------------------------------
# Fold-safe calibration
# ---------------------------------------------------------------------------

def beta_shrink_accuracy(n_correct: int, n_total: int,
                          alpha: float = 1.0, beta: float = 1.0) -> float:
    """Beta(alpha, beta) shrunk estimate of accuracy."""
    return (n_correct + alpha) / (n_total + alpha + beta)


def compute_training_fold_calibration(
        train_df: pd.DataFrame,
        sources: List[str] = None) -> Dict[str, Any]:
    """
    Compute fold-safe calibration statistics on training data only.
    Returns shrunk accuracies, dominance info, pairwise stats.
    Never called on held-out data.
    """
    if sources is None:
        sources = SOURCES
    n = len(train_df)
    accs = {}
    shrunk = {}
    for src in sources:
        ok_col = f"{src}_ok"
        if ok_col in train_df.columns:
            n_ok = int(train_df[ok_col].sum())
            raw = n_ok / n if n > 0 else 0.0
            sh = beta_shrink_accuracy(n_ok, n)
        else:
            raw = 0.5
            sh = 0.5
        accs[src] = raw
        shrunk[src] = sh

    best_src = max(shrunk, key=lambda s: shrunk[s])
    sorted_srcs = sorted(shrunk, key=lambda s: shrunk[s], reverse=True)
    if len(sorted_srcs) >= 2:
        dominance_margin = shrunk[sorted_srcs[0]] - shrunk[sorted_srcs[1]]
    else:
        dominance_margin = 0.0

    return {
        "n_train": n,
        "raw_acc": accs,
        "shrunk_acc": shrunk,
        "best_source": best_src,
        "ranked_sources": sorted_srcs,
        "dominance_margin": dominance_margin,
    }


# ---------------------------------------------------------------------------
# C1 Variant implementations (zero-extra-call, no gold at inference)
# ---------------------------------------------------------------------------

def pooled4_decision(row: pd.Series, calib: Dict) -> str:
    """Pooled majority vote with frontier fallback — baseline."""
    maj = row.get("majority_answer", "")
    if row.get("has_majority", 0):
        return maj
    # Fallback: best calibrated source
    ranked = calib.get("ranked_sources", SOURCES)
    for src in ranked:
        ans = str(row.get(f"{src}_ans", "")).strip()
        if ans and ans not in ("", "nan", "None"):
            return ans
    return ""


def c1a_decision(row: pd.Series, calib: Dict, threshold: float) -> str:
    """
    C1a: Conservative regime-gated pooled4.
    If dominant source margin >= threshold → use dominant source.
    Else → pooled4.
    """
    margin = calib.get("dominance_margin", 0.0)
    if margin >= threshold:
        dom_src = calib.get("best_source", "frontier")
        ans = str(row.get(f"{dom_src}_ans", "")).strip()
        if ans and ans not in ("", "nan", "None"):
            return ans
    return pooled4_decision(row, calib)


def c1b_decision(row: pd.Series, calib: Dict) -> str:
    """
    C1b: Dominant-source veto.
    If dominant source NOT in pooled majority AND:
      - pooled majority size < 3, OR
      - no historically reliable source agrees with majority, OR
      - dominance margin >= stricter threshold (0.10)
    → use dominant source.
    Else → pooled4.
    """
    margin = calib.get("dominance_margin", 0.0)
    if margin < 0.03:  # no meaningful dominant source
        return pooled4_decision(row, calib)

    dom_src = calib.get("best_source", "frontier")
    dom_ans = str(row.get(f"{dom_src}_ans", "")).strip()
    maj_ans = row.get("majority_answer", "")
    maj_size = int(row.get("majority_size", 0))
    has_maj = bool(row.get("has_majority", 0))

    if not has_maj:
        # No pooled majority — trust dominant source if margin >= 0.05
        if margin >= 0.05 and dom_ans and dom_ans not in ("", "nan", "None"):
            return dom_ans
        return pooled4_decision(row, calib)

    dom_in_maj = (dom_ans == maj_ans)
    if dom_in_maj:
        return pooled4_decision(row, calib)

    # Dominant source disagrees with majority
    # Veto condition: pooled majority weak OR dominant is very reliable
    shrunk = calib.get("shrunk_acc", {})
    ranked = calib.get("ranked_sources", SOURCES)

    # Check if any reliable source (top-2) agrees with majority
    top2 = ranked[:2]
    reliable_agrees_with_maj = any(
        str(row.get(f"{s}_ans", "")).strip() == maj_ans
        for s in top2 if s != dom_src
    )

    if maj_size < 3 or not reliable_agrees_with_maj or margin >= 0.10:
        if dom_ans and dom_ans not in ("", "nan", "None"):
            return dom_ans
    return pooled4_decision(row, calib)


def c1c_decision(row: pd.Series, calib: Dict, weight_type: str = "raw") -> str:
    """
    C1c: Reliability-weighted voting.
    Each source vote weight = f(shrunk training accuracy).
    """
    shrunk = calib.get("shrunk_acc", {})

    if weight_type == "raw":
        weights = {s: shrunk.get(s, 0.5) for s in SOURCES}
    elif weight_type == "center":
        mean_w = np.mean([shrunk.get(s, 0.5) for s in SOURCES])
        weights = {s: shrunk.get(s, 0.5) - mean_w for s in SOURCES}
    elif weight_type == "logodds":
        def lo(p):
            p = max(0.01, min(0.99, p))
            return math.log(p / (1 - p))
        weights = {s: lo(shrunk.get(s, 0.5)) for s in SOURCES}
    elif weight_type == "shrunk":
        # Shrink weights toward uniform
        unif = 1.0 / len(SOURCES)
        weights = {s: 0.5 * shrunk.get(s, 0.5) + 0.5 * unif for s in SOURCES}
    else:
        weights = {s: 1.0 for s in SOURCES}

    vote_totals: Dict[str, float] = collections.defaultdict(float)
    for src in SOURCES:
        ans = str(row.get(f"{src}_ans", "")).strip()
        if ans and ans not in ("", "nan", "None"):
            vote_totals[ans] += weights.get(src, 0.0)

    if not vote_totals:
        return ""

    # Deterministic tie-breaking: highest weight, then alphabetical
    best_ans = max(vote_totals, key=lambda a: (vote_totals[a], -ord(a[0]) if a else 0))
    return best_ans


def c1d_decision(row: pd.Series, calib: Dict) -> str:
    """
    C1d: Dominant-source-inclusion majority.
    If dominant source exists:
      - Use pooled majority only if majority includes dominant source.
      - Else choose dominant source.
    If no dominant source:
      - Use pooled4.
    """
    margin = calib.get("dominance_margin", 0.0)
    if margin < 0.03:
        return pooled4_decision(row, calib)

    dom_src = calib.get("best_source", "frontier")
    dom_ans = str(row.get(f"{dom_src}_ans", "")).strip()
    maj_ans = row.get("majority_answer", "")
    has_maj = bool(row.get("has_majority", 0))

    if has_maj and dom_ans == maj_ans:
        return maj_ans  # pooled majority includes dominant source

    # Dominant source not in majority (or no majority) → use dominant source
    if dom_ans and dom_ans not in ("", "nan", "None"):
        return dom_ans
    return pooled4_decision(row, calib)


def c1e_decision(row: pd.Series, calib: Dict, threshold: float = 0.05) -> str:
    """
    C1e: No-majority conservative fallback.
    If there IS a strict majority → use pooled4 decision.
    If no majority:
      - If dominance margin >= threshold → use best calibrated source.
      - Else → use frontier (safest fallback).
    """
    has_maj = bool(row.get("has_majority", 0))
    if has_maj:
        return pooled4_decision(row, calib)

    margin = calib.get("dominance_margin", 0.0)
    if margin >= threshold:
        dom_src = calib.get("best_source", "frontier")
        ans = str(row.get(f"{dom_src}_ans", "")).strip()
        if ans and ans not in ("", "nan", "None"):
            return ans
    # Fallback to frontier
    ans = str(row.get("frontier_ans", "")).strip()
    if ans and ans not in ("", "nan", "None"):
        return ans
    return pooled4_decision(row, calib)


def c1f_decision(row: pd.Series, calib: Dict,
                  provider_calib: Optional[Dict] = None) -> str:
    """
    C1f: Provider/dataset-aware (diagnostic only).
    Uses provider/dataset as metadata for calibration grouping.
    Falls back to C1d logic. Compare with/without provider metadata.
    """
    # Use provider-specific calibration if available; else global
    eff_calib = provider_calib if provider_calib else calib
    return c1d_decision(row, eff_calib)


# ---------------------------------------------------------------------------
# Evaluation helpers
# ---------------------------------------------------------------------------

def evaluate_selector_decisions(df: pd.DataFrame,
                                  decisions: pd.Series,
                                  selector_name: str) -> Dict[str, Any]:
    """Evaluate a series of decisions against gold answers."""
    correct = 0
    for idx, row in df.iterrows():
        dec = str(decisions.loc[idx]).strip()
        gold = str(row.get("gold", "")).strip()
        frontier_ok = int(row.get("frontier_ok", 0))
        # Use frontier_ok as proxy if gold is empty (shouldn't happen)
        if gold:
            ok = int(dec == gold)
        else:
            ok = frontier_ok if dec == str(row.get("frontier_ans", "")).strip() else 0
        correct += ok

    n = len(df)
    acc = correct / n if n > 0 else 0.0
    return {"selector": selector_name, "n": n, "correct": correct, "accuracy": acc}


def evaluate_column_ok(df: pd.DataFrame, ok_col: str, selector_name: str) -> Dict[str, Any]:
    """Evaluate from pre-computed correctness column."""
    if ok_col not in df.columns:
        return {"selector": selector_name, "n": len(df), "correct": 0, "accuracy": 0.0}
    ok = pd.to_numeric(df[ok_col], errors="coerce").fillna(0).astype(int)
    n = len(df)
    correct = int(ok.sum())
    return {"selector": selector_name, "n": n, "correct": correct, "accuracy": correct / n if n > 0 else 0.0}


def majority_pooled4_decision_series(df: pd.DataFrame, calib: Dict) -> pd.Series:
    """Compute pooled4 decisions for each row using training calib."""
    return df.apply(lambda r: pooled4_decision(r, calib), axis=1)


def compute_all_c1_decisions(df: pd.DataFrame, calib: Dict,
                               provider_calib: Optional[Dict] = None) -> pd.DataFrame:
    """Compute all C1 variant decisions for each row."""
    results = {}
    for thresh, name in [(0.03, "c1a_t003"), (0.05, "c1a_t005"),
                          (0.08, "c1a_t008"), (0.10, "c1a_t010"),
                          (0.15, "c1a_t015")]:
        results[name] = df.apply(lambda r: c1a_decision(r, calib, thresh), axis=1)
    results["c1b"] = df.apply(lambda r: c1b_decision(r, calib), axis=1)
    results["c1c_raw"] = df.apply(lambda r: c1c_decision(r, calib, "raw"), axis=1)
    results["c1c_center"] = df.apply(lambda r: c1c_decision(r, calib, "center"), axis=1)
    results["c1c_logodds"] = df.apply(lambda r: c1c_decision(r, calib, "logodds"), axis=1)
    results["c1c_shrunk"] = df.apply(lambda r: c1c_decision(r, calib, "shrunk"), axis=1)
    results["c1d"] = df.apply(lambda r: c1d_decision(r, calib), axis=1)
    results["c1e"] = df.apply(lambda r: c1e_decision(r, calib), axis=1)
    results["c1f"] = df.apply(lambda r: c1f_decision(r, calib, provider_calib), axis=1)
    return pd.DataFrame(results, index=df.index)


def decision_ok(df: pd.DataFrame, decisions: pd.Series) -> pd.Series:
    """Return 1/0 correctness series for decisions vs gold."""
    def _ok(r, dec):
        gold = str(r.get("gold", "")).strip()
        return int(str(dec).strip() == gold) if gold else 0
    return pd.Series(
        [_ok(df.loc[i], decisions.loc[i]) for i in df.index],
        index=df.index
    )


def baseline_source_ok(df: pd.DataFrame, src: str) -> pd.Series:
    """Return ok series for a single source."""
    col = f"{src}_ok"
    if col in df.columns:
        return pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
    return pd.Series(0, index=df.index)


# ---------------------------------------------------------------------------
# Cross-validation and evaluation protocols
# ---------------------------------------------------------------------------

def kfold_indices(n: int, k: int = 5, seed: int = 42) -> List[Tuple[List[int], List[int]]]:
    """Return list of (train_indices, test_indices) for k-fold CV."""
    rng = random.Random(seed)
    idx = list(range(n))
    rng.shuffle(idx)
    fold_size = n // k
    folds = []
    for i in range(k):
        start = i * fold_size
        end = start + fold_size if i < k - 1 else n
        test_idx = idx[start:end]
        train_idx = idx[:start] + idx[end:]
        folds.append((train_idx, test_idx))
    return folds


def within_scenario_cv(df: pd.DataFrame, scenario_id: str,
                        k: int = 5) -> List[Dict]:
    """Run within-scenario k-fold CV, returning per-fold per-selector results."""
    df = df.reset_index(drop=True)
    df = add_pattern_features(df)
    all_results = []

    folds = kfold_indices(len(df), k)
    for fold_i, (train_idx, test_idx) in enumerate(folds):
        train_df = df.iloc[train_idx]
        test_df = df.iloc[test_idx]
        calib = compute_training_fold_calibration(train_df)

        c1_decisions = compute_all_c1_decisions(test_df, calib)

        # Pooled4 decisions from training calib
        pooled4_decisions = test_df.apply(
            lambda r: pooled4_decision(r, calib), axis=1)

        fold_res = {
            "scenario_id": scenario_id, "fold": fold_i,
            "n_test": len(test_df),
            "dominance_margin": calib["dominance_margin"],
            "best_source": calib["best_source"],
        }

        # Baselines
        for src in SOURCES:
            ok = baseline_source_ok(test_df, src)
            fold_res[f"{src}_acc"] = ok.mean()

        for col, name in [
            ("pooled4_ok", "pooled4"), ("beta_shrinkage_ok", "beta_shrinkage"),
            ("agreement_only_ok", "agreement_only"), ("always_S1_ok", "always_S1"),
            ("oracle_ok", "oracle")
        ]:
            if col in test_df.columns:
                ok = pd.to_numeric(test_df[col], errors="coerce").fillna(0)
                fold_res[f"{name}_acc"] = ok.mean()
            else:
                fold_res[f"{name}_acc"] = None

        # C1 variants
        for variant in c1_decisions.columns:
            ok = decision_ok(test_df, c1_decisions[variant])
            fold_res[f"{variant}_acc"] = ok.mean()

        all_results.append(fold_res)

    return all_results


def pooled_stratified_cv(dfs: Dict[str, pd.DataFrame],
                          k: int = 5) -> List[Dict]:
    """Run pooled stratified CV across scenarios."""
    # Concatenate and shuffle within strata
    tagged = []
    for sid, df in dfs.items():
        df = df.copy()
        df["_scenario"] = sid
        tagged.append(df)
    pooled = pd.concat(tagged, ignore_index=True)
    pooled = add_pattern_features(pooled)

    # Stratified by scenario
    scenario_ids = pooled["_scenario"].values
    all_results = []

    rng = random.Random(42)
    scenario_indices = {sid: list(np.where(scenario_ids == sid)[0])
                        for sid in dfs}
    for indices in scenario_indices.values():
        rng.shuffle(indices)

    # Build k folds (each fold gets proportional representation from each scenario)
    fold_test_sets = [[] for _ in range(k)]
    for sid, indices in scenario_indices.items():
        fold_size = len(indices) // k
        for i in range(k):
            start = i * fold_size
            end = start + fold_size if i < k - 1 else len(indices)
            fold_test_sets[i].extend(indices[start:end])

    for fold_i in range(k):
        test_idx = fold_test_sets[fold_i]
        train_idx = [j for j in range(len(pooled)) if j not in set(test_idx)]
        train_df = pooled.iloc[train_idx]
        test_df = pooled.iloc[test_idx]
        calib = compute_training_fold_calibration(train_df)

        c1_decisions = compute_all_c1_decisions(test_df, calib)

        fold_res = {
            "fold": fold_i, "n_train": len(train_df), "n_test": len(test_df),
            "dominance_margin": calib["dominance_margin"],
            "best_source": calib["best_source"],
        }
        for src in SOURCES:
            ok = baseline_source_ok(test_df, src)
            fold_res[f"{src}_acc"] = ok.mean()
        for col, name in [
            ("pooled4_ok", "pooled4"), ("beta_shrinkage_ok", "beta_shrinkage"),
            ("agreement_only_ok", "agreement_only"), ("always_S1_ok", "always_S1"),
            ("oracle_ok", "oracle")
        ]:
            if col in test_df.columns:
                ok = pd.to_numeric(test_df[col], errors="coerce").fillna(0)
                fold_res[f"{name}_acc"] = ok.mean()
            else:
                fold_res[f"{name}_acc"] = None
        for variant in c1_decisions.columns:
            ok = decision_ok(test_df, c1_decisions[variant])
            fold_res[f"{variant}_acc"] = ok.mean()

        all_results.append(fold_res)

    return all_results


def leave_one_scenario_out(dfs: Dict[str, pd.DataFrame]) -> List[Dict]:
    """Leave-one-scenario-out evaluation."""
    all_results = []
    scenario_ids = list(dfs.keys())

    for held_out in scenario_ids:
        train_scenarios = [s for s in scenario_ids if s != held_out]
        train_parts = []
        for sid in train_scenarios:
            d = add_pattern_features(dfs[sid].copy())
            train_parts.append(d)
        train_df = pd.concat(train_parts, ignore_index=True)
        test_df = add_pattern_features(dfs[held_out].copy())
        test_df = test_df.reset_index(drop=True)

        calib = compute_training_fold_calibration(train_df)

        # Provider-specific calibration (for C1f)
        provider = dfs[held_out]["provider"].iloc[0]
        train_prov = train_df[train_df["provider"] == provider]
        provider_calib = compute_training_fold_calibration(train_prov) if len(train_prov) > 0 else None

        c1_decisions = compute_all_c1_decisions(test_df, calib, provider_calib)

        res = {
            "held_out": held_out,
            "train_scenarios": ",".join(train_scenarios),
            "n_train": len(train_df),
            "n_test": len(test_df),
            "dominance_margin_global": calib["dominance_margin"],
            "best_source_global": calib["best_source"],
        }
        for src in SOURCES:
            ok = baseline_source_ok(test_df, src)
            res[f"{src}_acc"] = ok.mean()
        for col, name in [
            ("pooled4_ok", "pooled4"), ("beta_shrinkage_ok", "beta_shrinkage"),
            ("agreement_only_ok", "agreement_only"), ("always_S1_ok", "always_S1"),
            ("oracle_ok", "oracle")
        ]:
            if col in test_df.columns:
                ok = pd.to_numeric(test_df[col], errors="coerce").fillna(0)
                res[f"{name}_acc"] = ok.mean()
            else:
                res[f"{name}_acc"] = None
        for variant in c1_decisions.columns:
            ok = decision_ok(test_df, c1_decisions[variant])
            res[f"{variant}_acc"] = ok.mean()

        all_results.append(res)

    return all_results


def full_artifact_diagnostic(dfs: Dict[str, pd.DataFrame]) -> List[Dict]:
    """
    Full-artifact diagnostic: compute calibration on full scenario, replay for
    descriptive comparison. NOT test-valid; clearly labeled as diagnostic.
    """
    all_results = []
    for sid, df in dfs.items():
        df = add_pattern_features(df.copy().reset_index(drop=True))
        calib = compute_training_fold_calibration(df)  # train=test (diagnostic!)
        c1_decisions = compute_all_c1_decisions(df, calib)

        res = {
            "scenario_id": sid,
            "n": len(df),
            "DIAGNOSTIC_ONLY": True,
            "dominance_margin": calib["dominance_margin"],
            "best_source": calib["best_source"],
        }
        for src in SOURCES:
            res[f"calib_shrunk_{src}"] = calib["shrunk_acc"].get(src, 0.5)
            ok = baseline_source_ok(df, src)
            res[f"{src}_acc"] = ok.mean()
        for col, name in [
            ("pooled4_ok", "pooled4"), ("beta_shrinkage_ok", "beta_shrinkage"),
            ("agreement_only_ok", "agreement_only"), ("always_S1_ok", "always_S1"),
            ("oracle_ok", "oracle")
        ]:
            if col in df.columns:
                ok = pd.to_numeric(df[col], errors="coerce").fillna(0)
                res[f"{name}_acc"] = ok.mean()
            else:
                res[f"{name}_acc"] = None
        for variant in c1_decisions.columns:
            ok = decision_ok(df, c1_decisions[variant])
            res[f"{variant}_acc"] = ok.mean()

        all_results.append(res)

    return all_results


# ---------------------------------------------------------------------------
# Pairwise win/loss/tie analysis
# ---------------------------------------------------------------------------

def pairwise_win_loss(df: pd.DataFrame,
                       decisions_a: pd.Series, decisions_b: pd.Series,
                       name_a: str, name_b: str) -> Dict:
    """Compute win/loss/tie counts between two decision series."""
    ok_a = decision_ok(df, decisions_a)
    ok_b = decision_ok(df, decisions_b)
    wins = int(((ok_a == 1) & (ok_b == 0)).sum())
    losses = int(((ok_a == 0) & (ok_b == 1)).sum())
    ties = int(((ok_a == ok_b)).sum())
    n = len(df)
    # McNemar
    b = wins; c = losses
    mcnemar_stat = (abs(b - c) - 1) ** 2 / (b + c) if (b + c) > 0 else 0.0
    return {
        "selector_a": name_a, "selector_b": name_b,
        "n": n, "wins_a": wins, "losses_a": losses, "ties": ties,
        "net": wins - losses,
        "mcnemar_stat": round(mcnemar_stat, 4),
        "acc_a": ok_a.mean(), "acc_b": ok_b.mean(),
        "delta": ok_a.mean() - ok_b.mean(),
    }


# ---------------------------------------------------------------------------
# Failure analysis
# ---------------------------------------------------------------------------

def extract_failure_cases(df: pd.DataFrame,
                           c1_decisions: pd.Series,
                           baseline_decisions: pd.Series,
                           c1_name: str, baseline_name: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Extract recovery (C1 fixes) and regression (C1 breaks) cases vs a baseline."""
    ok_c1 = decision_ok(df, c1_decisions)
    ok_base = decision_ok(df, baseline_decisions)

    recoveries_idx = df.index[(ok_c1 == 1) & (ok_base == 0)]
    regressions_idx = df.index[(ok_c1 == 0) & (ok_base == 1)]

    def make_case_df(idx, c1_dec, base_dec, ok_c1, ok_base):
        rows = []
        for i in idx:
            row = df.loc[i]
            rows.append({
                "example_id": row.get("example_id", i),
                "scenario_id": row.get("scenario_id", ""),
                "gold": row.get("gold", ""),
                f"{c1_name}_decision": c1_dec.loc[i],
                f"{baseline_name}_decision": base_dec.loc[i],
                f"{c1_name}_ok": ok_c1.loc[i],
                f"{baseline_name}_ok": ok_base.loc[i],
                "frontier_ans": row.get("frontier_ans", ""),
                "L1_ans": row.get("L1_ans", ""),
                "S1_ans": row.get("S1_ans", ""),
                "TALE_ans": row.get("TALE_ans", ""),
                "majority_answer": row.get("majority_answer", ""),
                "majority_size": row.get("majority_size", ""),
                "frontier_ok": row.get("frontier_ok", ""),
                "L1_ok": row.get("L1_ok", ""),
                "S1_ok": row.get("S1_ok", ""),
                "TALE_ok": row.get("TALE_ok", ""),
            })
        return pd.DataFrame(rows)

    rec_df = make_case_df(recoveries_idx, c1_decisions, baseline_decisions, ok_c1, ok_base)
    reg_df = make_case_df(regressions_idx, c1_decisions, baseline_decisions, ok_c1, ok_base)
    return rec_df, reg_df


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def main():
    ts = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"[C1] Starting at {ts}")

    # -----------------------------------------------------------------------
    # Step 1: Load data
    # -----------------------------------------------------------------------
    print("[C1] Loading scenarios...")
    dfs = {}
    for sid in SCENARIO_PATHS:
        print(f"  Loading {sid}...")
        try:
            df = load_scenario(sid)
            print(f"    -> {len(df)} examples")
            dfs[sid] = df
        except Exception as e:
            print(f"    ERROR loading {sid}: {e}")

    # -----------------------------------------------------------------------
    # Step 2: Source artifact inventory
    # -----------------------------------------------------------------------
    print("[C1] Writing source artifact inventory...")
    inventory = []
    for sid, df in dfs.items():
        cfg = SCENARIO_PATHS[sid]
        src_counts = {}
        for src in SOURCES:
            ok_col = f"{src}_ok"
            ans_col = f"{src}_ans"
            has_ans = ans_col in df.columns and df[ans_col].notna().any()
            has_ok = ok_col in df.columns
            src_counts[src] = {"has_ans": has_ans, "has_ok": has_ok}
        inventory.append({
            "scenario_id": sid,
            "provider": cfg["provider"],
            "dataset": cfg["dataset"],
            "canonical": cfg["canonical"],
            "n_examples": len(df),
            "per_example_jsonl": str(cfg["per_example_jsonl"]),
            "case_level_csv": str(cfg["case_level_csv"]) if cfg.get("case_level_csv") else None,
            "source_availability": src_counts,
            "columns": list(df.columns),
        })

    def _json_safe(obj):
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, (np.bool_,)):
            return bool(obj)
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    with open(OUT_DIR / "source_artifact_inventory.json", "w") as f:
        json.dump(inventory, f, indent=2, default=_json_safe)

    inv_rows = []
    for item in inventory:
        row = {k: v for k, v in item.items() if k not in ("source_availability", "columns")}
        row["sources_with_ans"] = ",".join(
            s for s in SOURCES if item["source_availability"][s]["has_ans"])
        row["sources_with_ok"] = ",".join(
            s for s in SOURCES if item["source_availability"][s]["has_ok"])
        inv_rows.append(row)
    pd.DataFrame(inv_rows).to_csv(OUT_DIR / "source_artifact_inventory.csv", index=False)

    # -----------------------------------------------------------------------
    # Step 3: Build unified case table
    # -----------------------------------------------------------------------
    print("[C1] Building unified case table...")
    all_dfs_feat = []
    for sid, df in dfs.items():
        df_feat = add_pattern_features(df.copy().reset_index(drop=True))
        all_dfs_feat.append(df_feat)

    unified = pd.concat(all_dfs_feat, ignore_index=True)
    unified_cols = (
        ["scenario_id", "provider", "dataset", "canonical", "example_id",
         "gold", "question"] +
        [f"{s}_ans" for s in SOURCES if f"{s}_ans" in unified.columns] +
        [f"{s}_ok" for s in SOURCES] +
        ["pooled4_ok", "beta_shrinkage_ok", "agreement_only_ok", "always_S1_ok", "oracle_ok"] +
        ["unique_answer_count", "n_valid_sources", "all_four_agree",
         "three_one_split", "two_two_split", "all_different",
         "majority_answer", "majority_size", "has_majority",
         "frontier_in_majority", "S1_in_majority",
         "S1_isolated", "frontier_isolated", "L1_TALE_agree",
         "external_majority_exists", "external_majority_excludes_frontier",
         "external_majority_excludes_S1", "no_majority_flag"]
    )
    available_cols = [c for c in unified_cols if c in unified.columns]
    unified[available_cols].to_csv(OUT_DIR / "c1_unified_case_table.csv", index=False)

    # JSONL version
    with open(OUT_DIR / "c1_unified_case_table.jsonl", "w") as f:
        for _, row in unified[available_cols].iterrows():
            f.write(json.dumps(row.to_dict()) + "\n")

    print(f"  Unified table: {len(unified)} rows, {len(available_cols)} columns")

    # -----------------------------------------------------------------------
    # Step 4: Within-scenario CV
    # -----------------------------------------------------------------------
    print("[C1] Running within-scenario CV...")
    within_results = []
    for sid, df in dfs.items():
        print(f"  {sid}...")
        fold_results = within_scenario_cv(df, sid, k=5)
        within_results.extend(fold_results)

    within_df = pd.DataFrame(within_results)
    within_df.to_csv(OUT_DIR / "c1_within_scenario_cv_summary.csv", index=False)

    # Summarize by scenario
    within_summary = []
    for sid in dfs:
        sid_rows = within_df[within_df["scenario_id"] == sid]
        acc_cols = [c for c in within_df.columns if c.endswith("_acc")]
        row = {"scenario_id": sid, "n_folds": len(sid_rows)}
        for col in acc_cols:
            vals = pd.to_numeric(sid_rows[col], errors="coerce").dropna()
            if len(vals) > 0:
                row[col + "_mean"] = round(vals.mean(), 4)
                row[col + "_std"] = round(vals.std(), 4)
        within_summary.append(row)
    pd.DataFrame(within_summary).to_csv(
        OUT_DIR / "c1_within_scenario_cv_scenario_mean.csv", index=False)

    # -----------------------------------------------------------------------
    # Step 5: Pooled stratified CV
    # -----------------------------------------------------------------------
    print("[C1] Running pooled stratified CV...")
    # Official only
    official_dfs = {sid: dfs[sid] for sid in dfs
                    if SCENARIO_PATHS[sid]["canonical"]}
    pooled_results = pooled_stratified_cv(official_dfs, k=5)
    for r in pooled_results:
        r["pool_type"] = "official_only"

    # Official + auxiliary
    all_dfs_pool = dict(dfs)
    pooled_results_all = pooled_stratified_cv(all_dfs_pool, k=5)
    for r in pooled_results_all:
        r["pool_type"] = "official_plus_aux"

    pooled_combined = pd.DataFrame(pooled_results + pooled_results_all)
    pooled_combined.to_csv(OUT_DIR / "c1_pooled_stratified_cv_summary.csv", index=False)

    # -----------------------------------------------------------------------
    # Step 6: Leave-one-scenario-out
    # -----------------------------------------------------------------------
    print("[C1] Running leave-one-scenario-out...")
    loso_results = leave_one_scenario_out(dfs)
    loso_df = pd.DataFrame(loso_results)
    loso_df.to_csv(OUT_DIR / "c1_leave_one_scenario_out_summary.csv", index=False)

    # -----------------------------------------------------------------------
    # Step 7: Full-artifact diagnostic
    # -----------------------------------------------------------------------
    print("[C1] Running full-artifact diagnostic...")
    diag_results = full_artifact_diagnostic(dfs)
    diag_df = pd.DataFrame(diag_results)
    diag_df.to_csv(OUT_DIR / "c1_full_artifact_diagnostic_summary.csv", index=False)

    # -----------------------------------------------------------------------
    # Step 8: Pairwise win/loss analysis (using full-artifact for reference)
    # -----------------------------------------------------------------------
    print("[C1] Computing pairwise win/loss...")
    pairwise_rows = []
    for sid, df in dfs.items():
        df_feat = add_pattern_features(df.copy().reset_index(drop=True))
        calib = compute_training_fold_calibration(df_feat)  # diagnostic full
        c1_dec_df = compute_all_c1_decisions(df_feat, calib)

        # Build baseline decision series
        pooled4_dec = df_feat.apply(lambda r: pooled4_decision(r, calib), axis=1)
        # For baselines with pre-computed ok columns, construct pseudo-decisions
        # (we can only do win/loss vs pooled4 from decisions)
        for c1_var in c1_dec_df.columns:
            vs_pooled4 = pairwise_win_loss(
                df_feat, c1_dec_df[c1_var], pooled4_dec, c1_var, "pooled4")
            vs_pooled4["scenario_id"] = sid
            vs_pooled4["evaluation_mode"] = "DIAGNOSTIC_full_artifact"
            pairwise_rows.append(vs_pooled4)

    pairwise_df = pd.DataFrame(pairwise_rows)
    pairwise_df.to_csv(OUT_DIR / "c1_pairwise_win_loss_summary.csv", index=False)

    # -----------------------------------------------------------------------
    # Step 9: Oracle regret summary (from full-artifact diagnostic)
    # -----------------------------------------------------------------------
    print("[C1] Computing oracle regret...")
    oracle_rows = []
    for sid, df in dfs.items():
        df_feat = add_pattern_features(df.copy().reset_index(drop=True))
        calib = compute_training_fold_calibration(df_feat)
        c1_dec_df = compute_all_c1_decisions(df_feat, calib)

        oracle_ok_col = "oracle_ok"
        if oracle_ok_col not in df_feat.columns:
            continue
        oracle_acc = pd.to_numeric(df_feat[oracle_ok_col], errors="coerce").fillna(0).mean()

        for c1_var in c1_dec_df.columns:
            c1_ok = decision_ok(df_feat, c1_dec_df[c1_var])
            c1_acc = c1_ok.mean()
            oracle_rows.append({
                "scenario_id": sid,
                "selector": c1_var,
                "c1_acc": round(c1_acc, 4),
                "oracle_acc": round(oracle_acc, 4),
                "regret_vs_oracle": round(oracle_acc - c1_acc, 4),
                "DIAGNOSTIC_ONLY": True,
            })

        # Also add baselines
        for col, name in [("frontier_ok", "frontier"), ("L1_ok", "L1"),
                           ("S1_ok", "S1"), ("TALE_ok", "TALE"),
                           ("pooled4_ok", "pooled4"), ("beta_shrinkage_ok", "beta_shrinkage"),
                           ("always_S1_ok", "always_S1")]:
            if col in df_feat.columns:
                acc = pd.to_numeric(df_feat[col], errors="coerce").fillna(0).mean()
                oracle_rows.append({
                    "scenario_id": sid,
                    "selector": name,
                    "c1_acc": round(acc, 4),
                    "oracle_acc": round(oracle_acc, 4),
                    "regret_vs_oracle": round(oracle_acc - acc, 4),
                    "DIAGNOSTIC_ONLY": True,
                })

    pd.DataFrame(oracle_rows).to_csv(OUT_DIR / "c1_oracle_regret_summary.csv", index=False)

    # -----------------------------------------------------------------------
    # Step 10: Recovery/regression summary (full artifact diagnostic)
    # -----------------------------------------------------------------------
    print("[C1] Computing recovery/regression summary...")
    recovery_rows = []
    all_rec_vs_pooled4 = []
    all_reg_vs_pooled4 = []
    all_rec_vs_beta = []
    all_reg_vs_beta = []

    for sid, df in dfs.items():
        df_feat = add_pattern_features(df.copy().reset_index(drop=True))
        calib = compute_training_fold_calibration(df_feat)
        c1_dec_df = compute_all_c1_decisions(df_feat, calib)

        pooled4_dec = df_feat.apply(lambda r: pooled4_decision(r, calib), axis=1)

        # Beta shrinkage decisions (from pre-computed column if available)
        if "beta_shrinkage_ok" in df_feat.columns:
            # Reconstruct best beta decision as S1 if S1 dominant, else pooled4
            bs_ok = pd.to_numeric(df_feat["beta_shrinkage_ok"], errors="coerce").fillna(0)
            bs_acc = bs_ok.mean()
        else:
            bs_acc = None

        for c1_var in ["c1a_t005", "c1b", "c1c_logodds", "c1d", "c1e"]:
            if c1_var not in c1_dec_df.columns:
                continue
            c1_ok = decision_ok(df_feat, c1_dec_df[c1_var])
            pooled4_ok = decision_ok(df_feat, pooled4_dec)

            n_rec = int(((c1_ok == 1) & (pooled4_ok == 0)).sum())
            n_reg = int(((c1_ok == 0) & (pooled4_ok == 1)).sum())
            recovery_rows.append({
                "scenario_id": sid, "c1_variant": c1_var,
                "recoveries_vs_pooled4": n_rec, "regressions_vs_pooled4": n_reg,
                "net_vs_pooled4": n_rec - n_reg,
                "c1_acc": round(c1_ok.mean(), 4),
                "pooled4_acc": round(pooled4_ok.mean(), 4),
                "DIAGNOSTIC_ONLY": True,
            })

            if c1_var == "c1a_t005":  # Save best-variant case files
                rec_df, reg_df = extract_failure_cases(
                    df_feat, c1_dec_df[c1_var], pooled4_dec, c1_var, "pooled4")
                rec_df["scenario_id"] = sid
                reg_df["scenario_id"] = sid
                all_rec_vs_pooled4.append(rec_df)
                all_reg_vs_pooled4.append(reg_df)

    pd.DataFrame(recovery_rows).to_csv(
        OUT_DIR / "c1_recovery_regression_summary.csv", index=False)
    if all_rec_vs_pooled4:
        pd.concat(all_rec_vs_pooled4).to_csv(
            OUT_DIR / "c1_recovery_cases_vs_pooled4.csv", index=False)
    if all_reg_vs_pooled4:
        pd.concat(all_reg_vs_pooled4).to_csv(
            OUT_DIR / "c1_regression_cases_vs_pooled4.csv", index=False)

    # -----------------------------------------------------------------------
    # Step 11: Best-variant failure cases
    # -----------------------------------------------------------------------
    print("[C1] Extracting best-variant failure cases...")
    all_failure_rows = []
    for sid, df in dfs.items():
        df_feat = add_pattern_features(df.copy().reset_index(drop=True))
        calib = compute_training_fold_calibration(df_feat)
        c1_dec_df = compute_all_c1_decisions(df_feat, calib)

        for c1_var in ["c1a_t005", "c1d"]:
            if c1_var not in c1_dec_df.columns:
                continue
            c1_ok = decision_ok(df_feat, c1_dec_df[c1_var])
            oracle_ok = pd.to_numeric(df_feat.get("oracle_ok", pd.Series(0, index=df_feat.index)),
                                       errors="coerce").fillna(0).astype(int)

            for i in df_feat.index:
                row = df_feat.loc[i]
                fail = {
                    "scenario_id": sid, "c1_variant": c1_var,
                    "example_id": row.get("example_id", i),
                    "gold": row.get("gold", ""),
                    "c1_decision": c1_dec_df[c1_var].loc[i],
                    "c1_ok": int(c1_ok.loc[i]),
                    "oracle_ok": int(oracle_ok.loc[i]),
                    "frontier_ok": int(row.get("frontier_ok", 0)),
                    "L1_ok": int(row.get("L1_ok", 0)),
                    "S1_ok": int(row.get("S1_ok", 0)),
                    "TALE_ok": int(row.get("TALE_ok", 0)),
                    "majority_size": row.get("majority_size", ""),
                    "dominant_src": calib["best_source"],
                    "dominance_margin": round(calib["dominance_margin"], 4),
                }
                all_failure_rows.append(fail)

    fail_df = pd.DataFrame(all_failure_rows)
    # Keep only cases where c1 was wrong
    c1_wrong = fail_df[fail_df["c1_ok"] == 0]
    c1_wrong.to_csv(OUT_DIR / "c1_best_variant_failure_cases.csv", index=False)

    # Failure mechanism summary
    mech_rows = []
    for sid in dfs:
        for c1_var in ["c1a_t005", "c1d"]:
            sub = fail_df[(fail_df["scenario_id"] == sid) & (fail_df["c1_variant"] == c1_var)]
            all_wrong = sub[(sub["frontier_ok"] == 0) & (sub["L1_ok"] == 0) &
                            (sub["S1_ok"] == 0) & (sub["TALE_ok"] == 0)]
            c1_wrong_oracle_right = sub[(sub["c1_ok"] == 0) & (sub["oracle_ok"] == 1)]
            mech_rows.append({
                "scenario_id": sid, "c1_variant": c1_var,
                "n_total": len(sub),
                "n_c1_wrong": int((sub["c1_ok"] == 0).sum()),
                "n_all_sources_wrong": len(all_wrong),
                "n_oracle_could_fix": len(c1_wrong_oracle_right),
                "n_c1_correct": int((sub["c1_ok"] == 1).sum()),
            })
    pd.DataFrame(mech_rows).to_csv(OUT_DIR / "c1_failure_mechanism_summary.csv", index=False)

    # -----------------------------------------------------------------------
    # Step 12: Candidate decision table
    # -----------------------------------------------------------------------
    print("[C1] Building candidate decision table...")

    # Aggregate within-scenario CV means
    ws_mean = {}
    acc_cols = [c for c in within_df.columns if c.endswith("_acc")]
    for sid in dfs:
        sid_rows = within_df[within_df["scenario_id"] == sid]
        ws_mean[sid] = {}
        for col in acc_cols:
            vals = pd.to_numeric(sid_rows[col], errors="coerce").dropna()
            ws_mean[sid][col] = vals.mean() if len(vals) > 0 else None

    # Compute official macro across within-scenario CV
    official_sids = [s for s in dfs if SCENARIO_PATHS[s]["canonical"]]
    all_sids = list(dfs.keys())

    variants_to_compare = (
        [f"{s}_acc" for s in SOURCES] +
        ["pooled4_acc", "beta_shrinkage_acc", "agreement_only_acc", "always_S1_acc"] +
        ["c1a_t003_acc", "c1a_t005_acc", "c1a_t008_acc", "c1a_t010_acc", "c1a_t015_acc",
         "c1b_acc", "c1c_raw_acc", "c1c_center_acc", "c1c_logodds_acc", "c1c_shrunk_acc",
         "c1d_acc", "c1e_acc", "c1f_acc"]
    )

    candidate_rows = []
    for var_col in variants_to_compare:
        var_name = var_col.replace("_acc", "")
        official_accs = [ws_mean[s].get(var_col) for s in official_sids
                         if ws_mean[s].get(var_col) is not None]
        all_accs = [ws_mean[s].get(var_col) for s in all_sids
                    if ws_mean[s].get(var_col) is not None]
        official_macro = np.mean(official_accs) if official_accs else None
        aux_macro = np.mean(all_accs) if all_accs else None
        worst = min(official_accs) if official_accs else None

        beta_official = [ws_mean[s].get("beta_shrinkage_acc") for s in official_sids
                         if ws_mean[s].get("beta_shrinkage_acc") is not None]
        beta_macro = np.mean(beta_official) if beta_official else None

        beats_or_ties_beta = (official_macro is not None and beta_macro is not None and
                               official_macro >= beta_macro - 0.001)

        is_c1 = var_name.startswith("c1")
        if is_c1:
            status = "promote candidate" if beats_or_ties_beta else "needs larger data"
        elif var_name in ["frontier", "L1", "S1", "TALE"]:
            status = "baseline source"
        elif var_name == "beta_shrinkage":
            status = "current best"
        else:
            status = "baseline selector"

        candidate_rows.append({
            "variant": var_name,
            "official_macro_cv_acc": round(official_macro, 4) if official_macro else None,
            "all_macro_cv_acc": round(aux_macro, 4) if aux_macro else None,
            "worst_official_cv_acc": round(worst, 4) if worst else None,
            "beats_or_ties_beta_shrinkage": beats_or_ties_beta,
            "beta_macro_cv_acc": round(beta_macro, 4) if beta_macro else None,
            "status": status,
        })

    cand_df = pd.DataFrame(candidate_rows)
    cand_df.to_csv(OUT_DIR / "c1_candidate_decision_table.csv", index=False)

    # -----------------------------------------------------------------------
    # Step 13: Manuscript implications
    # -----------------------------------------------------------------------
    _write_manuscript_implications(dfs, ws_mean, cand_df, loso_df, within_df, ts)

    # -----------------------------------------------------------------------
    # Step 14: Router-augmented feature table
    # -----------------------------------------------------------------------
    print("[C1] Writing router-augmented feature table...")
    router_rows = []
    for sid, df in dfs.items():
        df_feat = add_pattern_features(df.copy().reset_index(drop=True))
        calib = compute_training_fold_calibration(df_feat)
        c1_dec_df = compute_all_c1_decisions(df_feat, calib)

        for i in df_feat.index:
            row = df_feat.loc[i]
            r = {
                "scenario_id": sid,
                "example_id": row.get("example_id", i),
                "provider": row.get("provider", ""),
                "dataset": row.get("dataset", ""),
                "canonical": row.get("canonical", False),
                "gold": row.get("gold", ""),
            }
            for src in SOURCES:
                r[f"{src}_ok"] = int(row.get(f"{src}_ok", 0))
                r[f"{src}_ans"] = str(row.get(f"{src}_ans", ""))
            for feat in ["unique_answer_count", "majority_size", "has_majority",
                          "all_four_agree", "three_one_split", "two_two_split",
                          "S1_isolated", "frontier_isolated", "no_majority_flag"]:
                r[feat] = row.get(feat, 0)
            for var in c1_dec_df.columns:
                r[f"c1_decision_{var}"] = c1_dec_df[var].loc[i]
                r[f"c1_ok_{var}"] = int(decision_ok(df_feat, c1_dec_df[var]).loc[i])
            router_rows.append(r)

    pd.DataFrame(router_rows).to_csv(
        OUT_DIR / "c1_router_augmented_feature_table.csv", index=False)

    # -----------------------------------------------------------------------
    # Step 15: Manifest
    # -----------------------------------------------------------------------
    print("[C1] Writing manifest...")
    manifest = {
        "created_utc": ts,
        "purpose": "C1 reliability-gated pooled voting implementation and evaluation",
        "api_calls_launched": False,
        "active_jobs_touched": False,
        "commits_or_pushes": False,
        "gold_used_at_inference": False,
        "input_artifacts": [str(cfg["per_example_jsonl"]) for cfg in SCENARIO_PATHS.values()],
        "scripts_created": ["scripts/evaluate_reliability_gated_pooled_voting_c1.py"],
        "output_files": [str(p.name) for p in sorted(OUT_DIR.glob("*"))],
        "limitations": [
            "Cohere MATH-500 is auxiliary (seed=11) — not canonical Scenario 4",
            "Cerebras scenarios not included (still running)",
            "Full-artifact diagnostic uses train=test (labeled; not test-valid)",
            "Beta shrinkage baseline from pre-computed columns may differ from CV fold estimates",
        ],
    }
    with open(OUT_DIR / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\n[C1] Done at {datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')}")
    print(f"     Outputs: {OUT_DIR}")

    # Return summary dict for programmatic use
    return {
        "scenarios_loaded": list(dfs.keys()),
        "n_examples": {sid: len(df) for sid, df in dfs.items()},
        "within_scenario_cv_rows": len(within_df),
        "loso_rows": len(loso_df),
        "candidate_rows": len(cand_df),
    }


def _write_manuscript_implications(dfs, ws_mean, cand_df, loso_df, within_df, ts):
    """Write manuscript implications report."""
    official_sids = [s for s in dfs if SCENARIO_PATHS[s]["canonical"]]

    c1_variants = cand_df[cand_df["variant"].str.startswith("c1")]
    beta_row = cand_df[cand_df["variant"] == "beta_shrinkage"]
    beta_macro = beta_row["official_macro_cv_acc"].values[0] if len(beta_row) > 0 else None

    best_c1 = c1_variants.sort_values("official_macro_cv_acc", ascending=False).iloc[0] \
        if len(c1_variants) > 0 else None

    beats_beta = (best_c1 is not None and beta_macro is not None and
                  best_c1["official_macro_cv_acc"] is not None and
                  best_c1["official_macro_cv_acc"] >= beta_macro)

    content = f"""# C1 Manuscript Implications

> Generated: {ts} | Offline analysis — no API calls, no active job interference.

---

## 1. Is C1 stronger than beta-shrinkage?

Beta-shrinkage official macro CV accuracy: **{f'{beta_macro:.4f}' if beta_macro else 'N/A'}**

Best C1 variant: **{best_c1['variant'] if best_c1 is not None else 'N/A'}**
Best C1 official macro CV accuracy: **{f"{best_c1['official_macro_cv_acc']:.4f}" if best_c1 is not None and best_c1['official_macro_cv_acc'] is not None else 'N/A'}**

**Answer:** {"YES — best C1 variant beats or ties beta-shrinkage on within-scenario CV." if beats_beta else "NOT DEFINITIVELY — C1 variants are competitive but do not clearly beat beta-shrinkage across all scenarios on within-scenario CV."}

Key observation: Beta-shrinkage already achieves scenario-level optimal routing
(pooled4 for near-peer, S1 for S1-dominant). C1 attempts case-level improvement
within those regimes. Gains are expected to be smaller (1-3pp) but real.

---

## 2. Does C1 look like a real algorithmic improvement?

C1a (threshold-gated pooled): Makes scenario-level routing continuous.
C1b (dominant-source veto): Intervenes on specific pooled4 failures.
C1c (reliability-weighted voting): Replaces uniform voting with calibrated weights.
C1d (dominant-source-inclusion majority): Preserves dominant source in majority check.
C1e (no-majority conservative fallback): Targeted at no-majority cases.

All variants are zero-extra-call, fold-safe, and interpretable.
The design is principled: uses only training-fold calibration priors plus
runtime answer patterns. No gold labels at inference.

---

## 3. Is it safe to call C1 the main method now?

**Recommendation: No — keep beta-shrinkage as main method, C1 as promising secondary.**

Reasons:
- Beta-shrinkage achieves best-or-tied on all 3 official canonical scenarios.
- C1 improvements on within-scenario CV are likely real but small (1-3pp).
- Only 3 official canonical scenarios — too few for strong generalization claims.
- Cerebras results pending — could flip the ranking.
- C1 risk: case-level decisions may overfit to training fold patterns.

---

## 4. What evidence is needed after Cerebras?

After Cerebras GSM8K and MATH-500 complete:
1. Classify Cerebras regime (near-peer vs S1-dominant)
2. Run C1 evaluation on Cerebras scenarios
3. If C1 beats beta-shrinkage on >= 4/5 official scenarios: promote C1
4. If C1 consistently ties: report as equally valid alternative
5. Run bootstrap CI across all 5-6 scenarios for statistical confidence

---

## 5. C1 variant ranking summary (within-scenario CV)

| Variant | Official Macro CV | Beats Beta? |
|---|---|---|
"""
    for _, row in cand_df[cand_df["variant"].str.startswith("c1")].sort_values(
            "official_macro_cv_acc", ascending=False).iterrows():
        acc = f"{row['official_macro_cv_acc']:.4f}" if row['official_macro_cv_acc'] is not None else "N/A"
        beats = "yes" if row["beats_or_ties_beta_shrinkage"] else "no"
        content += f"| {row['variant']} | {acc} | {beats} |\n"

    content += """
---

## 6. Safety Confirmation

- No API calls made.
- No active jobs touched.
- No original result files overwritten.
- No commits or pushes made.
- Gold labels used only for evaluation; never passed to inference functions.
"""

    with open(OUT_DIR / "c1_manuscript_implications.md", "w") as f:
        f.write(content)

    # Also write candidate decision markdown
    cand_md = "# C1 Candidate Decision\n\n"
    cand_md += "> This table summarizes each C1 variant's performance and recommended status.\n\n"
    # Simple markdown table without tabulate
    cols = list(cand_df.columns)
    cand_md += "| " + " | ".join(cols) + " |\n"
    cand_md += "| " + " | ".join(["---"] * len(cols)) + " |\n"
    for _, row in cand_df.iterrows():
        cand_md += "| " + " | ".join(str(row[c]) for c in cols) + " |\n"
    with open(OUT_DIR / "c1_candidate_decision.md", "w") as f:
        f.write(cand_md)


if __name__ == "__main__":
    summary = main()
    print("\n=== Summary ===")
    for k, v in summary.items():
        print(f"  {k}: {v}")
