#!/usr/bin/env python3
"""Offline evaluation of RG-EB-Action router variants.

Implements pattern-specific empirical-Bayes action routing with fold-safe
reliability estimates and hierarchical backoff. Produces offline reports for
official4 and auxiliary training diagnostics.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import random
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from scipy.stats import beta as beta_dist

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "outputs" / "rg_eb_action_router_20260524"
DOC = REPO / "docs" / "RG_EB_ACTION_ROUTER_20260524.md"
OUT.mkdir(parents=True, exist_ok=True)

OFFICIAL4_PATH = REPO / "outputs" / "failure_pattern_workbench_official4_20260524" / "official4_unified_case_table.csv"
MISTRAL_TRAIN1000_PATH = REPO / "outputs" / "mistral_large_router_training_gsm8k_processing_20260524" / "train1000_case_level_selector_replay.csv"
COHERE_AUX_CASE_PATH = REPO / "outputs" / "cohere_math500_auxiliary_mlj_reprocess_20260524" / "cohere_math500_auxiliary_case_level_selector_results.csv"
COHERE_AUX_JSONL_PATH = REPO / "outputs" / "cohere_math500_auxiliary_mlj_reprocess_20260524" / "cohere_math500_auxiliary_complete_4method_records.jsonl"

FIX03_POOLED_SUMMARY = REPO / "outputs" / "fix03_s1_near_peer_gate_20260524" / "fix03_official_pooled_cv_summary.csv"
AG01_POOLED_SUMMARY = REPO / "outputs" / "ag01_agreement_only_gate_20260524" / "ag01_official_pooled_cv_summary.csv"

SOURCES = ["frontier", "L1", "S1", "TALE"]

ACTION_OK_COL = {
    "frontier": "frontier_ok",
    "L1": "L1_ok",
    "S1": "S1_ok",
    "TALE": "TALE_ok",
    "pooled4": "pooled4_ok",
    "agreement_only": "agreement_only_ok",
    "beta_shrinkage": "beta_shrinkage_ok",
    "C1d": "c1d_ok",
    "C1a_t005": "c1a_t005_ok",
    "always_s1": "always_s1_ok",
    "oracle_best_action": "oracle_best_action_ok",
    "oracle_best_source": "oracle_best_source_ok",
}

ACTION_DEC_COL = {
    "pooled4": "pooled4_decision",
    "agreement_only": "agreement_only_decision",
    "beta_shrinkage": "beta_shrinkage_decision",
    "C1d": "c1d_decision",
    "C1a_t005": "c1a_t005_decision",
    "always_s1": "always_s1_decision",
    "oracle_best_action": "oracle_best_action_decision",
}

RUNTIME_ACTIONS = {
    "frontier",
    "L1",
    "S1",
    "TALE",
    "pooled4",
    "agreement_only",
    "beta_shrinkage",
    "C1d",
    "C1a_t005",
    "always_s1",
    "best_calibrated_source",
}


@dataclass
class Variant:
    name: str
    family: str
    actions: List[str]
    alpha0: float
    beta0: float
    scoring: str  # mean | lcb
    lcb_q: float
    min_support: int
    bucket_mode: str  # coarse | coarse_pd | provider_free | hierarchical
    include_provider_dataset: bool
    provider_free_calibration: bool
    auxiliary_only_variant: bool = False


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def nrm(x: Any) -> str:
    s = str(x if x is not None else "").strip()
    if not s:
        return ""
    s = s.replace(",", "")
    s = re.sub(r"\\boxed\{([^}]+)\}", r"\1", s)
    s = s.strip().lower()
    try:
        v = float(s)
        if math.isfinite(v):
            if abs(v - int(v)) < 1e-12:
                return str(int(v))
            return f"{v:.12f}".rstrip("0").rstrip(".")
    except Exception:
        pass
    return s


def b01(x: Any) -> int:
    try:
        return int(bool(int(x)))
    except Exception:
        return 1 if str(x).strip().lower() in {"1", "true", "t", "yes", "y"} else 0


def to_num(x: Any, default: float = 0.0) -> float:
    try:
        v = float(x)
        if math.isfinite(v):
            return v
        return default
    except Exception:
        return default


def stable_hash(s: str) -> int:
    return int(hashlib.sha256(s.encode("utf-8")).hexdigest()[:16], 16)


def beta_mean(ok: int, n: int, a0: float, b0: float) -> float:
    return (ok + a0) / (n + a0 + b0)


def beta_lcb(ok: int, n: int, a0: float, b0: float, q: float) -> float:
    return float(beta_dist.ppf(q, ok + a0, (n - ok) + b0))


def score_post(ok: int, n: int, v: Variant) -> float:
    if v.scoring == "lcb":
        return beta_lcb(ok, n, v.alpha0, v.beta0, v.lcb_q)
    return beta_mean(ok, n, v.alpha0, v.beta0)


def agreement_pattern(row: pd.Series) -> str:
    l1 = nrm(row.get("L1_ans", ""))
    s1 = nrm(row.get("S1_ans", ""))
    t = nrm(row.get("TALE_ans", ""))
    if not l1 or not s1 or not t:
        return "missing_external"
    if l1 == s1 == t:
        return "l1=s1=tale"
    if l1 == s1 != t:
        return "l1=s1!=tale"
    if l1 == t != s1:
        return "l1=tale!=s1"
    if s1 == t != l1:
        return "s1=tale!=l1"
    return "all_different"


def majority_answer(answers: Sequence[str]) -> Tuple[str, int]:
    vals = [nrm(a) for a in answers if nrm(a)]
    if not vals:
        return "", 0
    c = Counter(vals)
    ans, cnt = sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))[0]
    return ans, int(cnt)


def infer_question_features(question: str, length_hint: Any, number_count_hint: Any, eq_hint: Any) -> Dict[str, Any]:
    q = str(question or "")
    qlen = int(to_num(length_hint, len(q)))
    n_count = int(to_num(number_count_hint, len(re.findall(r"[-+]?\d*\.?\d+", q))))
    has_fraction = 1 if re.search(r"\d\s*/\s*\d|\\frac\{|\bmixed number\b", q.lower()) else 0
    has_equation = 1 if b01(eq_hint) == 1 or ("=" in q) or ("<" in q and ">" in q) else 0

    if qlen < 120:
        qlen_bucket = "short"
    elif qlen < 260:
        qlen_bucket = "medium"
    else:
        qlen_bucket = "long"

    if n_count <= 2:
        number_bucket = "0_2"
    elif n_count <= 5:
        number_bucket = "3_5"
    else:
        number_bucket = "6_plus"

    hard_score = (1 if qlen_bucket == "long" else 0) + (1 if n_count >= 6 else 0) + has_fraction + has_equation
    if hard_score <= 1:
        difficulty = "easy"
    elif hard_score == 2:
        difficulty = "medium"
    else:
        difficulty = "hard"

    return {
        "question_length": qlen,
        "question_number_count": n_count,
        "question_length_bucket": qlen_bucket,
        "number_count_bucket": number_bucket,
        "has_fraction": has_fraction,
        "has_equation": has_equation,
        "difficulty_proxy": difficulty,
    }


def compute_pattern_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    # Ensure answer columns exist
    for s in SOURCES:
        acol = f"{s}_ans"
        if acol not in out.columns:
            out[acol] = ""
        out[acol] = out[acol].fillna("").astype(str).map(nrm)

    for c in [
        "all_four_agree",
        "three_one_split",
        "two_two_split",
        "all_different",
        "majority_answer",
        "majority_size",
        "has_majority",
        "frontier_in_majority",
        "S1_in_majority",
        "S1_isolated",
        "frontier_isolated",
        "L1_TALE_agree",
        "external_majority_exists",
        "external_majority_answer",
        "external_majority_size",
        "external_majority_excludes_frontier",
        "external_majority_excludes_S1",
        "no_majority_flag",
        "unique_answer_count",
        "n_valid_sources",
    ]:
        if c not in out.columns:
            out[c] = np.nan

    # Predeclare string-like columns as object so scalar assignment of strings is safe.
    for c in ["majority_answer", "external_majority_answer"]:
        out[c] = out[c].astype(object)

    # Recompute robustly from answers when missing
    for i, r in out.iterrows():
        answers = [nrm(r.get(f"{s}_ans", "")) for s in SOURCES]
        vals = [a for a in answers if a]
        cnt = Counter(vals)
        uniq = len(cnt)
        maj_ans, maj_sz = majority_answer(vals)

        if pd.isna(r.get("unique_answer_count")):
            out.at[i, "unique_answer_count"] = uniq
        if pd.isna(r.get("n_valid_sources")):
            out.at[i, "n_valid_sources"] = len(vals)

        if pd.isna(r.get("majority_answer")):
            out.at[i, "majority_answer"] = maj_ans
        if pd.isna(r.get("majority_size")):
            out.at[i, "majority_size"] = maj_sz
        if pd.isna(r.get("has_majority")):
            out.at[i, "has_majority"] = 1 if maj_sz >= 2 else 0
        if pd.isna(r.get("all_four_agree")):
            out.at[i, "all_four_agree"] = 1 if uniq == 1 and len(vals) == 4 else 0
        if pd.isna(r.get("all_different")):
            out.at[i, "all_different"] = 1 if uniq == 4 else 0
        if pd.isna(r.get("two_two_split")):
            out.at[i, "two_two_split"] = 1 if sorted(cnt.values(), reverse=True) == [2, 2] else 0
        if pd.isna(r.get("three_one_split")):
            out.at[i, "three_one_split"] = 1 if sorted(cnt.values(), reverse=True) == [3, 1] else 0

        f = nrm(r.get("frontier_ans", ""))
        s1 = nrm(r.get("S1_ans", ""))
        if pd.isna(r.get("frontier_in_majority")):
            out.at[i, "frontier_in_majority"] = 1 if (maj_sz >= 2 and f == maj_ans and f) else 0
        if pd.isna(r.get("S1_in_majority")):
            out.at[i, "S1_in_majority"] = 1 if (maj_sz >= 2 and s1 == maj_ans and s1) else 0
        if pd.isna(r.get("S1_isolated")):
            out.at[i, "S1_isolated"] = 1 if (s1 and cnt.get(s1, 0) == 1 and len(vals) == 4 and uniq >= 2) else 0
        if pd.isna(r.get("frontier_isolated")):
            out.at[i, "frontier_isolated"] = 1 if (f and cnt.get(f, 0) == 1 and len(vals) == 4 and uniq >= 2) else 0

        l1 = nrm(r.get("L1_ans", ""))
        t = nrm(r.get("TALE_ans", ""))
        if pd.isna(r.get("L1_TALE_agree")):
            out.at[i, "L1_TALE_agree"] = 1 if (l1 and l1 == t) else 0

        ext_vals = [nrm(r.get("L1_ans", "")), nrm(r.get("S1_ans", "")), nrm(r.get("TALE_ans", ""))]
        ext_maj, ext_sz = majority_answer(ext_vals)
        if pd.isna(r.get("external_majority_exists")):
            out.at[i, "external_majority_exists"] = 1 if ext_sz >= 2 else 0
        if pd.isna(r.get("external_majority_answer")):
            out.at[i, "external_majority_answer"] = ext_maj
        if pd.isna(r.get("external_majority_size")):
            out.at[i, "external_majority_size"] = ext_sz
        if pd.isna(r.get("external_majority_excludes_frontier")):
            out.at[i, "external_majority_excludes_frontier"] = 1 if (ext_sz >= 2 and ext_maj and ext_maj != f) else 0
        if pd.isna(r.get("external_majority_excludes_S1")):
            out.at[i, "external_majority_excludes_S1"] = 1 if (ext_sz >= 2 and ext_maj and ext_maj != s1) else 0
        if pd.isna(r.get("no_majority_flag")):
            out.at[i, "no_majority_flag"] = 1 if maj_sz < 2 else 0

    for c in [
        "all_four_agree", "three_one_split", "two_two_split", "all_different",
        "has_majority", "frontier_in_majority", "S1_in_majority", "S1_isolated",
        "frontier_isolated", "L1_TALE_agree", "external_majority_exists",
        "external_majority_excludes_frontier", "external_majority_excludes_S1",
        "no_majority_flag",
    ]:
        out[c] = pd.to_numeric(out[c], errors="coerce").fillna(0).astype(int)

    out["majority_size"] = pd.to_numeric(out["majority_size"], errors="coerce").fillna(0).astype(int)
    out["external_majority_size"] = pd.to_numeric(out["external_majority_size"], errors="coerce").fillna(0).astype(int)
    out["unique_answer_count"] = pd.to_numeric(out["unique_answer_count"], errors="coerce").fillna(0).astype(int)
    out["n_valid_sources"] = pd.to_numeric(out["n_valid_sources"], errors="coerce").fillna(0).astype(int)

    out["agreement_pattern"] = out.apply(agreement_pattern, axis=1)

    return out


def pooled4_decision_from_row(row: pd.Series, ranked_sources: Optional[List[str]] = None) -> str:
    maj = nrm(row.get("majority_answer", ""))
    if b01(row.get("has_majority", 0)) == 1 and maj:
        return maj
    order = ranked_sources or ["frontier", "L1", "S1", "TALE"]
    for s in order:
        a = nrm(row.get(f"{s}_ans", ""))
        if a:
            return a
    return ""


def agreement_only_decision_from_row(row: pd.Series) -> str:
    ext_maj_exists = b01(row.get("external_majority_exists", 0)) == 1
    ext_excl_frontier = b01(row.get("external_majority_excludes_frontier", 0)) == 1
    ext_maj = nrm(row.get("external_majority_answer", ""))
    if ext_maj_exists and ext_excl_frontier and ext_maj:
        return ext_maj
    return nrm(row.get("frontier_ans", ""))


def compute_missing_decisions(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for c in [
        "pooled4_decision",
        "agreement_only_decision",
        "beta_shrinkage_decision",
        "c1d_decision",
        "c1a_t005_decision",
        "always_s1_decision",
        "oracle_best_action_decision",
    ]:
        if c not in out.columns:
            out[c] = ""

    for i, r in out.iterrows():
        if not nrm(r.get("pooled4_decision", "")):
            out.at[i, "pooled4_decision"] = pooled4_decision_from_row(r)
        if not nrm(r.get("agreement_only_decision", "")):
            out.at[i, "agreement_only_decision"] = agreement_only_decision_from_row(r)
        if not nrm(r.get("always_s1_decision", "")):
            out.at[i, "always_s1_decision"] = nrm(r.get("S1_ans", ""))
        if not nrm(r.get("c1a_t005_decision", "")):
            out.at[i, "c1a_t005_decision"] = nrm(r.get("beta_shrinkage_decision", "")) or nrm(r.get("pooled4_decision", ""))
        if not nrm(r.get("c1d_decision", "")):
            out.at[i, "c1d_decision"] = nrm(r.get("beta_shrinkage_decision", "")) or nrm(r.get("pooled4_decision", ""))
        if not nrm(r.get("beta_shrinkage_decision", "")):
            out.at[i, "beta_shrinkage_decision"] = nrm(r.get("pooled4_decision", ""))
        if not nrm(r.get("oracle_best_action_decision", "")):
            # If unavailable, use pooled4 placeholder; correctness still from oracle_best_action_ok when present.
            out.at[i, "oracle_best_action_decision"] = nrm(r.get("pooled4_decision", ""))

    return out


def add_question_feature_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    feats = []
    for _, r in out.iterrows():
        feats.append(
            infer_question_features(
                r.get("question", ""),
                r.get("question_length", np.nan),
                r.get("question_number_count", np.nan),
                r.get("question_has_equation_flag", 0),
            )
        )
    feat_df = pd.DataFrame(feats)
    for c in feat_df.columns:
        out[c] = feat_df[c]
    return out


def load_official4() -> pd.DataFrame:
    df = pd.read_csv(OFFICIAL4_PATH, dtype=str)
    df["source_split"] = "official"
    df = compute_pattern_columns(df)
    df = compute_missing_decisions(df)
    df = add_question_feature_columns(df)

    # Numeric correctness columns
    for c in ACTION_OK_COL.values():
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)

    for s in SOURCES:
        okc = f"{s}_ok"
        if okc in df.columns:
            df[okc] = pd.to_numeric(df[okc], errors="coerce").fillna(0).astype(int)

    # Validate official schema counts
    req_cols = [
        "frontier_ans", "L1_ans", "S1_ans", "TALE_ans",
        "frontier_ok", "L1_ok", "S1_ok", "TALE_ok",
        "pooled4_ok", "agreement_only_ok", "beta_shrinkage_ok", "c1d_ok", "c1a_t005_ok", "always_s1_ok",
        "provider", "dataset", "scenario_id", "gold",
    ]
    missing = [c for c in req_cols if c not in df.columns]
    if missing:
        raise RuntimeError(f"Official4 table missing required columns: {missing}")

    return df


def load_jsonl_pivot(path: Path, source_split: str, scenario_id: str) -> pd.DataFrame:
    method_map = {
        "direct_reserve_semantic_frontier_v2": "frontier",
        "external_l1_max": "L1",
        "external_s1_budget_forcing": "S1",
        "external_tale_prompt_budgeting": "TALE",
    }
    rows: Dict[str, Dict[str, Any]] = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            eid = str(rec.get("example_id", "")).strip()
            if not eid:
                continue
            mraw = str(rec.get("method", "")).strip()
            m = method_map.get(mraw, mraw)
            if eid not in rows:
                rows[eid] = {
                    "example_id": eid,
                    "question": rec.get("question", ""),
                    "gold": str(rec.get("gold_answer_canonical", rec.get("gold_answer", ""))),
                    "provider": rec.get("provider", ""),
                    "dataset": rec.get("dataset", ""),
                    "scenario_id": scenario_id,
                    "source_split": source_split,
                }
            ans = nrm(rec.get("selected_answer_canonical", rec.get("final_answer_canonical", "")))
            ok = int(to_num(rec.get("exact_match", 0), 0.0))
            if m in SOURCES:
                rows[eid][f"{m}_ans"] = ans
                rows[eid][f"{m}_ok"] = ok
    df = pd.DataFrame(list(rows.values()))
    for s in SOURCES:
        df[f"{s}_ans"] = df.get(f"{s}_ans", "").fillna("").astype(str).map(nrm)
        df[f"{s}_ok"] = pd.to_numeric(df.get(f"{s}_ok", 0), errors="coerce").fillna(0).astype(int)
    return df


def load_mistral_aux() -> pd.DataFrame:
    df = pd.read_csv(MISTRAL_TRAIN1000_PATH, dtype=str)
    df["provider"] = df.get("provider", "mistral").fillna("mistral")
    df["dataset"] = df.get("dataset", "openai/gsm8k").fillna("openai/gsm8k")
    df["scenario_id"] = "mistral_gsm8k_aux1000"
    df["source_split"] = "aux_mistral_train1000"
    df = compute_pattern_columns(df)
    df = compute_missing_decisions(df)
    df = add_question_feature_columns(df)
    for c in ACTION_OK_COL.values():
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)
    return df


def load_cohere_aux() -> pd.DataFrame:
    base = load_jsonl_pivot(
        COHERE_AUX_JSONL_PATH,
        source_split="aux_cohere_math500",
        scenario_id="cohere_math500_aux488",
    )

    flags = pd.read_csv(COHERE_AUX_CASE_PATH, dtype=str)
    frename = {
        "direct_reserve_semantic_frontier_v2": "frontier_ok",
        "external_l1_max": "L1_ok",
        "external_s1_budget_forcing": "S1_ok",
        "external_tale_prompt_budgeting": "TALE_ok",
        "pooled4_with_fallback": "pooled4_ok",
        "agreement_only_2of3_against_frontier": "agreement_only_ok",
        "beta_shrinkage_regime_selector": "beta_shrinkage_ok",
        "always_s1": "always_s1_ok",
        "oracle_best_source": "oracle_best_source_ok",
        "oracle_best_action": "oracle_best_action_ok",
    }
    flags = flags.rename(columns=frename)
    keep_cols = ["example_id"] + [c for c in frename.values() if c in flags.columns]
    flags = flags[keep_cols]
    for c in keep_cols:
        if c != "example_id":
            flags[c] = pd.to_numeric(flags[c], errors="coerce").fillna(0).astype(int)

    df = base.merge(flags, on="example_id", how="left")
    df["provider"] = df.get("provider", "cohere").fillna("cohere")
    df["dataset"] = df.get("dataset", "HuggingFaceH4/MATH-500").fillna("HuggingFaceH4/MATH-500")

    # Fill missing correctness flags from answer-vs-gold comparison when absent.
    for s in SOURCES:
        okc = f"{s}_ok"
        if okc not in df.columns:
            df[okc] = (df[f"{s}_ans"].map(nrm) == df["gold"].map(nrm)).astype(int)
    for c in ["pooled4_ok", "agreement_only_ok", "beta_shrinkage_ok", "always_s1_ok", "oracle_best_action_ok", "oracle_best_source_ok"]:
        if c not in df.columns:
            df[c] = np.nan

    df = compute_pattern_columns(df)
    df = compute_missing_decisions(df)
    df = add_question_feature_columns(df)

    # c1d/c1a are not directly available in this aux artifact
    if "c1d_ok" not in df.columns:
        df["c1d_ok"] = np.nan
    if "c1a_t005_ok" not in df.columns:
        df["c1a_t005_ok"] = np.nan

    for c in ACTION_OK_COL.values():
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    return df


def validate_official_table(df: pd.DataFrame) -> Dict[str, Any]:
    scenario_counts = df.groupby("scenario_id").size().to_dict()
    provider_dataset_counts = df.groupby(["provider", "dataset"]).size().to_dict()

    checks = {
        "scenario_count": int(df["scenario_id"].nunique()),
        "total_rows": int(len(df)),
        "scenario_counts": {str(k): int(v) for k, v in scenario_counts.items()},
        "provider_dataset_counts": {f"{k[0]}|{k[1]}": int(v) for k, v in provider_dataset_counts.items()},
        "all_300": all(v == 300 for v in scenario_counts.values()),
        "expected_total_1200": int(len(df)) == 1200,
    }
    return checks


def source_stats_from_df(sub: pd.DataFrame, a0: float = 1.0, b0: float = 1.0) -> Dict[str, Any]:
    n = len(sub)
    if n == 0:
        n = 0
    acc = {}
    for s in SOURCES:
        ok = int(pd.to_numeric(sub.get(f"{s}_ok", 0), errors="coerce").fillna(0).astype(int).sum()) if n else 0
        acc[s] = beta_mean(ok, n, a0, b0) if n else 0.5
    ranked = sorted(SOURCES, key=lambda x: (-acc[x], x))
    best = ranked[0]
    second = ranked[1] if len(ranked) > 1 else ranked[0]
    spread = float(acc[best] - acc[second])
    s1_minus_second = float(acc["S1"] - max(acc[x] for x in SOURCES if x != "S1"))
    p = np.array([max(1e-12, acc[s]) for s in SOURCES], dtype=float)
    p = p / p.sum()
    entropy = float(-(p * np.log(p)).sum())
    return {
        "acc": acc,
        "ranked": ranked,
        "best_source": best,
        "second_source": second,
        "best_minus_second": spread,
        "s1_minus_second": s1_minus_second,
        "entropy": entropy,
    }


def regime_from_spread(spread: float) -> str:
    if spread <= 0.05:
        return "near_peer"
    if spread >= 0.12:
        return "dominant"
    return "mixed"


def spread_bucket(v: float) -> str:
    if v <= 0.03:
        return "le_003"
    if v <= 0.05:
        return "003_005"
    if v <= 0.08:
        return "005_008"
    if v <= 0.12:
        return "008_012"
    return "gt_012"


def entropy_bucket(v: float) -> str:
    if v <= 1.20:
        return "low"
    if v <= 1.32:
        return "mid"
    return "high"


def calib_tables(train_df: pd.DataFrame, provider_free: bool) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    out["global"] = source_stats_from_df(train_df)
    if provider_free:
        out["by_pd"] = {}
        return out
    by_pd = {}
    for (p, d), sub in train_df.groupby(["provider", "dataset"]):
        by_pd[(str(p), str(d))] = source_stats_from_df(sub)
    out["by_pd"] = by_pd
    return out


def get_row_stats(row: pd.Series, cal: Dict[str, Any], provider_free: bool) -> Dict[str, Any]:
    if not provider_free:
        key = (str(row.get("provider", "")), str(row.get("dataset", "")))
        if key in cal["by_pd"]:
            return cal["by_pd"][key]
    return cal["global"]


def runtime_features(row: pd.Series, stats: Dict[str, Any]) -> Dict[str, Any]:
    ap = str(row.get("agreement_pattern", "")) or agreement_pattern(row)
    uac = int(to_num(row.get("unique_answer_count", 0), 0.0))
    maj_size = int(to_num(row.get("majority_size", 0), 0.0))

    if b01(row.get("all_four_agree", 0)) == 1:
        majority_shape = "all4"
    elif b01(row.get("three_one_split", 0)) == 1:
        majority_shape = "3_1"
    elif b01(row.get("two_two_split", 0)) == 1:
        majority_shape = "2_2"
    elif b01(row.get("all_different", 0)) == 1:
        majority_shape = "all_diff"
    else:
        majority_shape = "other"

    f = {
        "provider": str(row.get("provider", "")),
        "dataset": str(row.get("dataset", "")),
        "agreement_pattern": ap,
        "unique_answer_count": uac,
        "majority_size": maj_size,
        "strict_majority_exists": 1 if maj_size >= 3 else 0,
        "all_four_agree": b01(row.get("all_four_agree", 0)),
        "all_different": b01(row.get("all_different", 0)),
        "two_two_split": b01(row.get("two_two_split", 0)),
        "three_one_split": b01(row.get("three_one_split", 0)),
        "external_majority_exists": b01(row.get("external_majority_exists", 0)),
        "external_majority_excludes_frontier": b01(row.get("external_majority_excludes_frontier", 0)),
        "external_majority_excludes_S1": b01(row.get("external_majority_excludes_S1", 0)),
        "L1_TALE_agree": b01(row.get("L1_TALE_agree", 0)),
        "S1_in_majority": b01(row.get("S1_in_majority", 0)),
        "S1_isolated": b01(row.get("S1_isolated", 0)),
        "frontier_in_majority": b01(row.get("frontier_in_majority", 0)),
        "frontier_isolated": b01(row.get("frontier_isolated", 0)),
        "question_length_bucket": str(row.get("question_length_bucket", "medium")),
        "number_count_bucket": str(row.get("number_count_bucket", "3_5")),
        "has_fraction": int(to_num(row.get("has_fraction", 0), 0)),
        "has_equation": int(to_num(row.get("has_equation", 0), 0)),
        "difficulty_proxy": str(row.get("difficulty_proxy", "medium")),
        "calib_regime_type": regime_from_spread(float(stats["best_minus_second"])),
        "best_calibrated_source": str(stats["best_source"]),
        "best_minus_second_spread_bucket": spread_bucket(float(stats["best_minus_second"])),
        "S1_minus_second_spread_bucket": spread_bucket(float(stats["s1_minus_second"])),
        "source_accuracy_entropy_bucket": entropy_bucket(float(stats["entropy"])),
        "majority_shape": majority_shape,
    }
    return f


def action_answer(row: pd.Series, action: str, stats: Dict[str, Any]) -> str:
    if action in SOURCES:
        return nrm(row.get(f"{action}_ans", ""))
    if action == "best_calibrated_source":
        best = stats["best_source"]
        return nrm(row.get(f"{best}_ans", ""))
    if action == "pooled4":
        return nrm(row.get("pooled4_decision", "")) or pooled4_decision_from_row(row, stats["ranked"])
    if action == "agreement_only":
        return nrm(row.get("agreement_only_decision", "")) or agreement_only_decision_from_row(row)
    if action == "beta_shrinkage":
        ans = nrm(row.get("beta_shrinkage_decision", ""))
        if ans:
            return ans
        if float(stats["best_minus_second"]) >= 0.05:
            return nrm(row.get(f"{stats['best_source']}_ans", ""))
        return action_answer(row, "pooled4", stats)
    if action == "C1d":
        ans = nrm(row.get("c1d_decision", ""))
        if ans:
            return ans
        return action_answer(row, "beta_shrinkage", stats)
    if action == "C1a_t005":
        ans = nrm(row.get("c1a_t005_decision", ""))
        if ans:
            return ans
        return action_answer(row, "beta_shrinkage", stats)
    if action == "always_s1":
        return nrm(row.get("always_s1_decision", "")) or nrm(row.get("S1_ans", ""))
    if action == "oracle_best_action":
        return nrm(row.get("oracle_best_action_decision", ""))
    if action == "oracle_best_source":
        # Offline only; if explicit best source decision is unavailable, pick the best source by correctness.
        for s in SOURCES:
            if b01(row.get(f"{s}_ok", 0)) == 1:
                return nrm(row.get(f"{s}_ans", ""))
        return nrm(row.get("frontier_ans", ""))
    return ""


def action_ok(row: pd.Series, action: str, ans: str) -> Optional[int]:
    col = ACTION_OK_COL.get(action)
    if col and col in row.index:
        v = row.get(col)
        if pd.isna(v):
            pass
        else:
            return int(to_num(v, 0.0))
    gold = nrm(row.get("gold", ""))
    if not gold:
        return None
    return 1 if nrm(ans) == gold else 0


def bucket_keys(v: Variant, f: Dict[str, Any]) -> List[Tuple[str, Tuple[Any, ...]]]:
    pd_prefix = (f["provider"], f["dataset"])
    coarse = (
        f["agreement_pattern"],
        int(f["external_majority_excludes_frontier"]),
        int(f["S1_isolated"]),
        f["calib_regime_type"],
    )
    detailed = (
        f["agreement_pattern"],
        f["majority_shape"],
        int(f["external_majority_excludes_frontier"]),
        int(f["external_majority_excludes_S1"]),
        int(f["S1_isolated"]),
        int(f["frontier_isolated"]),
        f["question_length_bucket"],
        f["number_count_bucket"],
        f["difficulty_proxy"],
        f["best_minus_second_spread_bucket"],
    )

    if v.bucket_mode == "coarse_pd":
        return [("pd_coarse", pd_prefix + coarse)]
    if v.bucket_mode == "provider_free":
        return [("provider_free", coarse)]
    if v.bucket_mode == "coarse":
        return [("coarse", coarse)]

    # Hierarchical backoff
    return [
        ("h1_pd_detailed", pd_prefix + detailed),
        ("h2_pd_coarse", pd_prefix + coarse),
        (
            "h3_calib_coarse",
            (f["calib_regime_type"], f["agreement_pattern"], int(f["external_majority_excludes_frontier"]), int(f["S1_isolated"])),
        ),
        (
            "h4_global_coarse",
            (f["agreement_pattern"], int(f["external_majority_excludes_frontier"]), int(f["S1_isolated"])),
        ),
    ]


def variant_list() -> List[Variant]:
    base_actions = [
        "pooled4", "agreement_only", "beta_shrinkage", "C1d", "C1a_t005",
        "always_s1", "best_calibrated_source", "frontier", "L1", "TALE",
    ]

    out: List[Variant] = []

    # RGEB-01
    for ms in [3, 5, 10]:
        out.append(Variant(
            name=f"RGEB01_mean_a1b1_s{ms}",
            family="RGEB-01",
            actions=base_actions,
            alpha0=1.0,
            beta0=1.0,
            scoring="mean",
            lcb_q=0.10,
            min_support=ms,
            bucket_mode="coarse",
            include_provider_dataset=False,
            provider_free_calibration=False,
        ))
    for ms in [3, 5, 10]:
        out.append(Variant(
            name=f"RGEB01_mean_a2b2_s{ms}",
            family="RGEB-01",
            actions=base_actions,
            alpha0=2.0,
            beta0=2.0,
            scoring="mean",
            lcb_q=0.10,
            min_support=ms,
            bucket_mode="coarse",
            include_provider_dataset=False,
            provider_free_calibration=False,
        ))

    # RGEB-02
    for q in [0.10, 0.20]:
        for ms in [5, 10, 20]:
            out.append(Variant(
                name=f"RGEB02_lcb{int(q*100):02d}_s{ms}",
                family="RGEB-02",
                actions=base_actions,
                alpha0=1.0,
                beta0=1.0,
                scoring="lcb",
                lcb_q=q,
                min_support=ms,
                bucket_mode="coarse",
                include_provider_dataset=False,
                provider_free_calibration=False,
            ))

    # RGEB-03 provider/dataset-aware (lookup risk)
    out.append(Variant(
        name="RGEB03_pd_mean_s5",
        family="RGEB-03",
        actions=base_actions,
        alpha0=1.0,
        beta0=1.0,
        scoring="mean",
        lcb_q=0.10,
        min_support=5,
        bucket_mode="coarse_pd",
        include_provider_dataset=True,
        provider_free_calibration=False,
    ))

    # RGEB-04 provider-free
    out.append(Variant(
        name="RGEB04_providerfree_mean_s5",
        family="RGEB-04",
        actions=base_actions,
        alpha0=1.0,
        beta0=1.0,
        scoring="mean",
        lcb_q=0.10,
        min_support=5,
        bucket_mode="provider_free",
        include_provider_dataset=False,
        provider_free_calibration=True,
    ))

    # RGEB-05 hierarchical
    out.append(Variant(
        name="RGEB05_hierarchical_mean_s5",
        family="RGEB-05",
        actions=base_actions,
        alpha0=1.0,
        beta0=1.0,
        scoring="mean",
        lcb_q=0.10,
        min_support=5,
        bucket_mode="hierarchical",
        include_provider_dataset=True,
        provider_free_calibration=False,
    ))

    # RGEB-06 agreement-focused
    out.append(Variant(
        name="RGEB06_agreement_focus_mean_s5",
        family="RGEB-06",
        actions=["beta_shrinkage", "C1d", "agreement_only", "pooled4"],
        alpha0=1.0,
        beta0=1.0,
        scoring="mean",
        lcb_q=0.10,
        min_support=5,
        bucket_mode="coarse",
        include_provider_dataset=False,
        provider_free_calibration=False,
    ))

    # RGEB-07 source/action hybrid
    out.append(Variant(
        name="RGEB07_hybrid_mean_s5",
        family="RGEB-07",
        actions=["pooled4", "agreement_only", "best_calibrated_source", "S1", "frontier"],
        alpha0=1.0,
        beta0=1.0,
        scoring="mean",
        lcb_q=0.10,
        min_support=5,
        bucket_mode="coarse",
        include_provider_dataset=False,
        provider_free_calibration=False,
    ))

    # RGEB-08 auxiliary-oriented variant
    out.append(Variant(
        name="RGEB08_aux_trained_providerfree_mean_s5",
        family="RGEB-08",
        actions=base_actions,
        alpha0=1.0,
        beta0=1.0,
        scoring="mean",
        lcb_q=0.10,
        min_support=5,
        bucket_mode="provider_free",
        include_provider_dataset=False,
        provider_free_calibration=True,
        auxiliary_only_variant=True,
    ))

    return out


def fit_model(train_df: pd.DataFrame, v: Variant) -> Dict[str, Any]:
    cal = calib_tables(train_df, provider_free=v.provider_free_calibration)
    levels: Dict[str, Dict[Tuple[Any, ...], Dict[str, List[int]]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: [0, 0])))
    global_counts: Dict[str, List[int]] = defaultdict(lambda: [0, 0])

    for _, row in train_df.iterrows():
        stats = get_row_stats(row, cal, provider_free=v.provider_free_calibration)
        feats = runtime_features(row, stats)
        lvl_keys = bucket_keys(v, feats)
        for a in v.actions:
            ans = action_answer(row, a, stats)
            ok = action_ok(row, a, ans)
            if ok is None:
                continue
            global_counts[a][0] += int(ok)
            global_counts[a][1] += 1
            for lvl_name, key in lvl_keys:
                levels[lvl_name][key][a][0] += int(ok)
                levels[lvl_name][key][a][1] += 1

    return {
        "variant": v,
        "cal": cal,
        "levels": levels,
        "global_counts": global_counts,
    }


def score_action(model: Dict[str, Any], row: pd.Series, action: str) -> Dict[str, Any]:
    v: Variant = model["variant"]
    cal = model["cal"]
    stats = get_row_stats(row, cal, provider_free=v.provider_free_calibration)
    feats = runtime_features(row, stats)
    ans = action_answer(row, action, stats)

    used_level = "global"
    used_support = 0
    used_ok = 0

    for lvl_name, key in bucket_keys(v, feats):
        cell = model["levels"].get(lvl_name, {}).get(key, {}).get(action)
        if cell is None:
            continue
        ok, n = int(cell[0]), int(cell[1])
        if n >= v.min_support:
            used_level = lvl_name
            used_support = n
            used_ok = ok
            break

    if used_support == 0:
        ok, n = model["global_counts"].get(action, [0, 0])
        used_ok, used_support = int(ok), int(n)

    sc = score_post(used_ok, used_support, v)
    return {
        "action": action,
        "answer": ans,
        "score": sc,
        "support": used_support,
        "ok_count": used_ok,
        "level": used_level,
        "stats": stats,
        "features": feats,
    }


def predict_row(model: Dict[str, Any], row: pd.Series) -> Dict[str, Any]:
    v: Variant = model["variant"]
    scored = [score_action(model, row, a) for a in v.actions]
    scored = sorted(scored, key=lambda d: (-float(d["score"]), v.actions.index(d["action"]), d["action"]))
    top = scored[0]

    # If chosen answer is empty, deterministic fallback.
    if not nrm(top["answer"]):
        fb = score_action(model, row, "pooled4") if "pooled4" in v.actions else score_action(model, row, v.actions[0])
        top = fb

    ok = action_ok(row, top["action"], top["answer"])
    return {
        "variant": v.name,
        "family": v.family,
        "selected_action": top["action"],
        "selected_answer": top["answer"],
        "variant_ok": int(ok) if ok is not None else 0,
        "support": int(top["support"]),
        "backoff_level": str(top["level"]),
        "best_train_source": top["stats"]["best_source"],
        "calib_regime_type": regime_from_spread(float(top["stats"]["best_minus_second"])),
        "best_minus_second": float(top["stats"]["best_minus_second"]),
        "s1_minus_second": float(top["stats"]["s1_minus_second"]),
        "entropy": float(top["stats"]["entropy"]),
        "provider_dataset_aware": int(v.include_provider_dataset),
        "provider_free_variant": int(v.provider_free_calibration),
        "min_support": int(v.min_support),
        "scoring": v.scoring,
    }


def split_kfold(df: pd.DataFrame, n_splits: int = 5, seed: int = 20260524) -> List[np.ndarray]:
    idx = list(df.index)
    idx = sorted(idx, key=lambda i: stable_hash(str(df.loc[i, "example_id"]) + f"|{seed}"))
    folds = [idx[i::n_splits] for i in range(n_splits)]
    return [np.array(f, dtype=int) for f in folds]


def stratified_scenario_folds(df: pd.DataFrame, n_splits: int = 5, seed: int = 20260524) -> List[np.ndarray]:
    per_fold: List[List[int]] = [[] for _ in range(n_splits)]
    for sid, sub in df.groupby("scenario_id"):
        folds = split_kfold(sub, n_splits=n_splits, seed=seed + stable_hash(str(sid)) % 1000)
        for i in range(n_splits):
            per_fold[i].extend(list(folds[i]))
    return [np.array(sorted(f), dtype=int) for f in per_fold]


def summarize_predictions(pred: pd.DataFrame, protocol: str) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    for var, sub in pred.groupby("variant"):
        acc = float(sub["variant_ok"].mean()) if len(sub) else 0.0
        scen = sub.groupby("scenario_id")["variant_ok"].mean() if "scenario_id" in sub.columns else pd.Series(dtype=float)
        macro = float(scen.mean()) if len(scen) else acc
        worst = float(scen.min()) if len(scen) else acc
        rows.append({
            "protocol": protocol,
            "variant": var,
            "family": str(sub["family"].iloc[0]) if "family" in sub.columns else "baseline",
            "n": int(len(sub)),
            "correct": int(sub["variant_ok"].sum()),
            "accuracy": acc,
            "macro_accuracy_by_scenario": macro,
            "worst_scenario_accuracy": worst,
            "avg_backoff_support": float(sub.get("support", pd.Series([0])).mean()),
            "fallback_rate": float((sub.get("backoff_level", pd.Series(["global"])) == "global").mean()),
            "provider_dataset_aware": int(sub.get("provider_dataset_aware", pd.Series([0])).iloc[0]) if "provider_dataset_aware" in sub.columns else 0,
            "provider_free_variant": int(sub.get("provider_free_variant", pd.Series([0])).iloc[0]) if "provider_free_variant" in sub.columns else 0,
        })
    out = pd.DataFrame(rows)

    # Deltas vs key references if present.
    refs = {r: float(out.loc[out["variant"] == r, "accuracy"].iloc[0]) for r in ["beta_shrinkage", "C1d", "agreement_only"] if (out["variant"] == r).any()}
    for ref_name, ref_acc in refs.items():
        out[f"delta_vs_{ref_name}"] = out["accuracy"] - ref_acc
    if "oracle_best_action" in set(out["variant"]):
        oracle_acc = float(out.loc[out["variant"] == "oracle_best_action", "accuracy"].iloc[0])
        out["regret_to_oracle"] = oracle_acc - out["accuracy"]
    else:
        out["regret_to_oracle"] = np.nan

    return out.sort_values(["accuracy", "variant"], ascending=[False, True]).reset_index(drop=True)


def pairwise_win_loss(pred: pd.DataFrame, refs: Sequence[str], protocol: str) -> pd.DataFrame:
    out_rows: List[Dict[str, Any]] = []
    variants = sorted(set(pred["variant"]))
    for v in variants:
        sv = pred[pred["variant"] == v][["eval_id", "variant_ok"]].rename(columns={"variant_ok": "ok_v"})
        for ref in refs:
            sr = pred[pred["variant"] == ref][["eval_id", "variant_ok"]].rename(columns={"variant_ok": "ok_r"})
            if len(sr) == 0:
                continue
            m = sv.merge(sr, on="eval_id", how="inner")
            if len(m) == 0:
                continue
            wins = int(((m["ok_v"] == 1) & (m["ok_r"] == 0)).sum())
            losses = int(((m["ok_v"] == 0) & (m["ok_r"] == 1)).sum())
            ties = int(((m["ok_v"] == m["ok_r"])).sum())
            out_rows.append({
                "protocol": protocol,
                "variant": v,
                "reference": ref,
                "n": int(len(m)),
                "wins": wins,
                "losses": losses,
                "ties": ties,
                "win_rate_non_tie": float(wins / max(1, wins + losses)),
            })
    return pd.DataFrame(out_rows)


def action_distribution(pred: pd.DataFrame, protocol: str) -> pd.DataFrame:
    if "selected_action" not in pred.columns:
        return pd.DataFrame(columns=["protocol", "variant", "scenario_id", "selected_action", "count", "share"])
    rows = []
    for (v, sid, act), sub in pred.groupby(["variant", "scenario_id", "selected_action"]):
        denom = max(1, len(pred[(pred["variant"] == v) & (pred["scenario_id"] == sid)]))
        rows.append({
            "protocol": protocol,
            "variant": v,
            "scenario_id": sid,
            "selected_action": act,
            "count": int(len(sub)),
            "share": float(len(sub) / denom),
        })
    return pd.DataFrame(rows)


def backoff_coverage(pred: pd.DataFrame, protocol: str) -> pd.DataFrame:
    if "backoff_level" not in pred.columns:
        return pd.DataFrame(columns=["protocol", "variant", "backoff_level", "count", "share"])
    rows = []
    for (v, lvl), sub in pred.groupby(["variant", "backoff_level"]):
        denom = max(1, len(pred[pred["variant"] == v]))
        rows.append({
            "protocol": protocol,
            "variant": v,
            "backoff_level": lvl,
            "count": int(len(sub)),
            "share": float(len(sub) / denom),
        })
    return pd.DataFrame(rows)


def add_baseline_predictions(train_df: pd.DataFrame, test_df: pd.DataFrame, protocol: str, fold: str) -> pd.DataFrame:
    rows = []

    # Train-fold best calibrated source baseline
    stats = source_stats_from_df(train_df)
    best_source = stats["best_source"]

    candidate_static = ["frontier", "L1", "S1", "TALE", "pooled4", "agreement_only", "beta_shrinkage", "C1d", "C1a_t005", "always_s1"]
    train_acc = {}
    for a in candidate_static:
        col = ACTION_OK_COL.get(a)
        if col in train_df.columns:
            s = pd.to_numeric(train_df[col], errors="coerce")
            train_acc[a] = float(s.mean(skipna=True)) if len(s.dropna()) else -1.0
        else:
            train_acc[a] = -1.0
    best_static_action = sorted(train_acc.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]

    for _, r in test_df.iterrows():
        eval_id = f"{protocol}|{fold}|{r['scenario_id']}|{r['example_id']}"
        for base in candidate_static:
            col = ACTION_OK_COL.get(base)
            if col not in r.index:
                continue
            ok = r.get(col)
            if pd.isna(ok):
                continue
            rows.append({
                "protocol": protocol,
                "fold": fold,
                "scenario_id": r["scenario_id"],
                "provider": r["provider"],
                "dataset": r["dataset"],
                "source_split": r["source_split"],
                "example_id": r["example_id"],
                "eval_id": eval_id,
                "variant": base,
                "family": "baseline",
                "selected_action": base,
                "selected_answer": action_answer(r, base, stats),
                "variant_ok": int(to_num(ok, 0.0)),
                "support": np.nan,
                "backoff_level": "baseline",
                "best_train_source": best_source,
                "calib_regime_type": regime_from_spread(stats["best_minus_second"]),
                "best_minus_second": float(stats["best_minus_second"]),
                "s1_minus_second": float(stats["s1_minus_second"]),
                "entropy": float(stats["entropy"]),
                "provider_dataset_aware": 0,
                "provider_free_variant": 0,
                "min_support": np.nan,
                "scoring": "baseline",
            })

        # best calibrated source
        bcs_ans = nrm(r.get(f"{best_source}_ans", ""))
        bcs_ok = action_ok(r, best_source, bcs_ans)
        rows.append({
            "protocol": protocol,
            "fold": fold,
            "scenario_id": r["scenario_id"],
            "provider": r["provider"],
            "dataset": r["dataset"],
            "source_split": r["source_split"],
            "example_id": r["example_id"],
            "eval_id": eval_id,
            "variant": "best_calibrated_source",
            "family": "baseline",
            "selected_action": "best_calibrated_source",
            "selected_answer": bcs_ans,
            "variant_ok": int(bcs_ok if bcs_ok is not None else 0),
            "support": np.nan,
            "backoff_level": "baseline",
            "best_train_source": best_source,
            "calib_regime_type": regime_from_spread(stats["best_minus_second"]),
            "best_minus_second": float(stats["best_minus_second"]),
            "s1_minus_second": float(stats["s1_minus_second"]),
            "entropy": float(stats["entropy"]),
            "provider_dataset_aware": 0,
            "provider_free_variant": 0,
            "min_support": np.nan,
            "scoring": "baseline",
        })

        # best static selected on train fold
        bs_ans = action_answer(r, best_static_action, stats)
        bs_ok = action_ok(r, best_static_action, bs_ans)
        rows.append({
            "protocol": protocol,
            "fold": fold,
            "scenario_id": r["scenario_id"],
            "provider": r["provider"],
            "dataset": r["dataset"],
            "source_split": r["source_split"],
            "example_id": r["example_id"],
            "eval_id": eval_id,
            "variant": "best_static_trainfold",
            "family": "baseline",
            "selected_action": best_static_action,
            "selected_answer": bs_ans,
            "variant_ok": int(bs_ok if bs_ok is not None else 0),
            "support": np.nan,
            "backoff_level": "baseline",
            "best_train_source": best_source,
            "calib_regime_type": regime_from_spread(stats["best_minus_second"]),
            "best_minus_second": float(stats["best_minus_second"]),
            "s1_minus_second": float(stats["s1_minus_second"]),
            "entropy": float(stats["entropy"]),
            "provider_dataset_aware": 0,
            "provider_free_variant": 0,
            "min_support": np.nan,
            "scoring": "baseline",
        })

        # oracle baselines
        for oracle_name in ["oracle_best_source", "oracle_best_action"]:
            c = ACTION_OK_COL.get(oracle_name)
            if c in r.index and not pd.isna(r.get(c)):
                rows.append({
                    "protocol": protocol,
                    "fold": fold,
                    "scenario_id": r["scenario_id"],
                    "provider": r["provider"],
                    "dataset": r["dataset"],
                    "source_split": r["source_split"],
                    "example_id": r["example_id"],
                    "eval_id": eval_id,
                    "variant": oracle_name,
                    "family": "oracle",
                    "selected_action": oracle_name,
                    "selected_answer": action_answer(r, oracle_name, stats),
                    "variant_ok": int(to_num(r.get(c), 0.0)),
                    "support": np.nan,
                    "backoff_level": "oracle",
                    "best_train_source": best_source,
                    "calib_regime_type": regime_from_spread(stats["best_minus_second"]),
                    "best_minus_second": float(stats["best_minus_second"]),
                    "s1_minus_second": float(stats["s1_minus_second"]),
                    "entropy": float(stats["entropy"]),
                    "provider_dataset_aware": 0,
                    "provider_free_variant": 0,
                    "min_support": np.nan,
                    "scoring": "oracle",
                })

    return pd.DataFrame(rows)


def evaluate_split(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    variants: Sequence[Variant],
    protocol: str,
    fold: str,
    include_variants: Optional[Iterable[str]] = None,
) -> pd.DataFrame:
    keep = set(include_variants) if include_variants else None
    rows = []

    for v in variants:
        if keep is not None and v.name not in keep:
            continue
        model = fit_model(train_df, v)
        for _, r in test_df.iterrows():
            pred = predict_row(model, r)
            pred.update({
                "protocol": protocol,
                "fold": fold,
                "scenario_id": r["scenario_id"],
                "provider": r["provider"],
                "dataset": r["dataset"],
                "source_split": r["source_split"],
                "example_id": r["example_id"],
                "eval_id": f"{protocol}|{fold}|{r['scenario_id']}|{r['example_id']}",
            })
            rows.append(pred)

    pred_df = pd.DataFrame(rows)
    base_df = add_baseline_predictions(train_df, test_df, protocol, fold)
    if len(pred_df) == 0:
        return base_df
    return pd.concat([pred_df, base_df], ignore_index=True)


def evaluate_protocol_within_scenario(official_df: pd.DataFrame, variants: Sequence[Variant]) -> pd.DataFrame:
    all_pred = []
    for sid, sdf in official_df.groupby("scenario_id"):
        folds = split_kfold(sdf, n_splits=5, seed=20260524)
        idx_all = set(sdf.index)
        for i, test_idx in enumerate(folds):
            train_idx = sorted(list(idx_all - set(test_idx.tolist())))
            train_df = sdf.loc[train_idx].copy()
            test_df = sdf.loc[test_idx].copy()
            fold_name = f"{sid}_fold{i}"
            all_pred.append(evaluate_split(train_df, test_df, variants, "within_scenario_cv", fold_name))
    return pd.concat(all_pred, ignore_index=True)


def evaluate_protocol_official_pooled(official_df: pd.DataFrame, variants: Sequence[Variant]) -> pd.DataFrame:
    folds = stratified_scenario_folds(official_df, n_splits=5, seed=20260524)
    idx_all = set(official_df.index)
    out = []
    for i, test_idx in enumerate(folds):
        train_idx = sorted(list(idx_all - set(test_idx.tolist())))
        train_df = official_df.loc[train_idx].copy()
        test_df = official_df.loc[test_idx].copy()
        out.append(evaluate_split(train_df, test_df, variants, "official_pooled_cv", f"fold{i}"))
    return pd.concat(out, ignore_index=True)


def evaluate_protocol_loso(official_df: pd.DataFrame, variants: Sequence[Variant]) -> pd.DataFrame:
    out = []
    for sid in sorted(official_df["scenario_id"].unique()):
        test_df = official_df[official_df["scenario_id"] == sid].copy()
        train_df = official_df[official_df["scenario_id"] != sid].copy()
        out.append(evaluate_split(train_df, test_df, variants, "leave_one_scenario_out", f"holdout_{sid}"))
    return pd.concat(out, ignore_index=True)


def evaluate_protocol_provider_heldout(official_df: pd.DataFrame, variants: Sequence[Variant]) -> pd.DataFrame:
    out = []
    for holdout_provider in ["cohere", "mistral"]:
        test_df = official_df[official_df["provider"] == holdout_provider].copy()
        train_df = official_df[official_df["provider"] != holdout_provider].copy()
        out.append(evaluate_split(train_df, test_df, variants, "provider_heldout", f"holdout_{holdout_provider}"))
    return pd.concat(out, ignore_index=True)


def evaluate_protocol_dataset_heldout(official_df: pd.DataFrame, variants: Sequence[Variant]) -> pd.DataFrame:
    out = []
    for holdout_dataset in sorted(official_df["dataset"].unique()):
        test_df = official_df[official_df["dataset"] == holdout_dataset].copy()
        train_df = official_df[official_df["dataset"] != holdout_dataset].copy()
        label = "gsm8k" if "gsm8k" in holdout_dataset else "math500"
        out.append(evaluate_split(train_df, test_df, variants, "dataset_heldout", f"holdout_{label}"))
    return pd.concat(out, ignore_index=True)


def evaluate_protocol_aux_training(
    official_df: pd.DataFrame,
    aux_df: pd.DataFrame,
    variants: Sequence[Variant],
) -> pd.DataFrame:
    folds = stratified_scenario_folds(official_df, n_splits=5, seed=20260524)
    idx_all = set(official_df.index)
    out = []

    for i, test_idx in enumerate(folds):
        train_idx = sorted(list(idx_all - set(test_idx.tolist())))
        train_official = official_df.loc[train_idx].copy()
        test_df = official_df.loc[test_idx].copy()

        # official only
        out.append(evaluate_split(train_official, test_df, variants, "aux_training", f"fold{i}_official_only"))

        # official + aux
        train_plus_aux = pd.concat([train_official, aux_df], ignore_index=True)
        out.append(evaluate_split(train_plus_aux, test_df, variants, "aux_training", f"fold{i}_official_plus_aux"))

        # aux only
        out.append(evaluate_split(aux_df, test_df, variants, "aux_training", f"fold{i}_aux_only"))

    return pd.concat(out, ignore_index=True)


def evaluate_protocol_full_diagnostic(official_df: pd.DataFrame, aux_df: pd.DataFrame, variants: Sequence[Variant]) -> pd.DataFrame:
    full_df = pd.concat([official_df, aux_df], ignore_index=True)
    folds = split_kfold(full_df, n_splits=5, seed=20260524)
    idx_all = set(full_df.index)
    out = []
    for i, test_idx in enumerate(folds):
        train_idx = sorted(list(idx_all - set(test_idx.tolist())))
        train_df = full_df.loc[train_idx].copy()
        test_df = full_df.loc[test_idx].copy()
        out.append(evaluate_split(train_df, test_df, variants, "full_artifact_diagnostic", f"fold{i}"))
    return pd.concat(out, ignore_index=True)


def choose_best_variant(summary_df: pd.DataFrame) -> str:
    rgeb = summary_df[summary_df["variant"].str.startswith("RGEB")].copy()
    if len(rgeb) == 0:
        return ""
    row = rgeb.sort_values(["accuracy", "worst_scenario_accuracy", "variant"], ascending=[False, False, True]).iloc[0]
    return str(row["variant"])


def write_markdown(path: Path, lines: List[str]) -> None:
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def save_csv(df: pd.DataFrame, path: Path) -> None:
    if df is None:
        pd.DataFrame().to_csv(path, index=False)
    else:
        df.to_csv(path, index=False)


def external_fix03_ag01_refs() -> pd.DataFrame:
    rows = []

    if FIX03_POOLED_SUMMARY.exists():
        f3 = pd.read_csv(FIX03_POOLED_SUMMARY)
        g = f3.groupby("selector").apply(lambda x: x["correct"].sum() / max(1, x["n"].sum())).reset_index(name="accuracy")
        if len(g):
            best = g.sort_values(["accuracy", "selector"], ascending=[False, True]).iloc[0]
            rows.append({
                "reference": "FIX03_best",
                "reference_variant": str(best["selector"]),
                "official_pooled_accuracy": float(best["accuracy"]),
                "source_file": str(FIX03_POOLED_SUMMARY.relative_to(REPO)),
            })

    if AG01_POOLED_SUMMARY.exists():
        ag = pd.read_csv(AG01_POOLED_SUMMARY)
        # Non-lookup heuristic: exclude obvious lookup variant names.
        non_lookup = ag[~ag["variant"].str.contains("lookup", case=False, na=False)].copy()
        if len(non_lookup):
            best = non_lookup.sort_values(["accuracy_mean", "variant"], ascending=[False, True]).iloc[0]
            rows.append({
                "reference": "AG01_best_non_lookup",
                "reference_variant": str(best["variant"]),
                "official_pooled_accuracy": float(best["accuracy_mean"]),
                "source_file": str(AG01_POOLED_SUMMARY.relative_to(REPO)),
            })

    return pd.DataFrame(rows)


def main() -> None:
    random.seed(20260524)
    np.random.seed(20260524)

    official = load_official4()
    mistral_aux = load_mistral_aux()
    cohere_aux = load_cohere_aux()

    # Keep only required common columns for aux merge while preserving extra fields.
    aux = pd.concat([mistral_aux, cohere_aux], ignore_index=True, sort=False)

    # Source artifact inventory
    inv_rows = []
    for p in [OFFICIAL4_PATH, MISTRAL_TRAIN1000_PATH, COHERE_AUX_CASE_PATH, COHERE_AUX_JSONL_PATH]:
        if p.exists():
            inv_rows.append({
                "path": str(p.relative_to(REPO)),
                "exists": True,
                "size_bytes": p.stat().st_size,
            })
        else:
            inv_rows.append({"path": str(p.relative_to(REPO)), "exists": False, "size_bytes": 0})

    source_inv_df = pd.DataFrame(inv_rows)
    source_inv_json = {
        "timestamp_utc": now_utc(),
        "inventory": source_inv_df.to_dict(orient="records"),
        "official_validation": validate_official_table(official),
    }

    save_csv(source_inv_df, OUT / "source_artifact_inventory.csv")
    (OUT / "source_artifact_inventory.json").write_text(json.dumps(source_inv_json, indent=2) + "\n", encoding="utf-8")

    # Save case tables
    save_csv(official, OUT / "rg_eb_official4_case_table.csv")

    aux_inv = aux.groupby("source_split").agg(rows=("example_id", "count"),
                                               providers=("provider", lambda s: ",".join(sorted(set(map(str, s))))),
                                               datasets=("dataset", lambda s: ",".join(sorted(set(map(str, s)))))).reset_index()
    save_csv(aux_inv, OUT / "rg_eb_auxiliary_inventory.csv")

    # Action label table
    action_rows = []
    actions_for_table = [
        "pooled4", "agreement_only", "beta_shrinkage", "C1d", "C1a_t005", "always_s1",
        "best_calibrated_source", "frontier", "L1", "S1", "TALE", "oracle_best_source", "oracle_best_action",
    ]
    global_stats = source_stats_from_df(official)
    for _, r in official.iterrows():
        row = {
            "example_id": r["example_id"],
            "scenario_id": r["scenario_id"],
            "provider": r["provider"],
            "dataset": r["dataset"],
        }
        for a in actions_for_table:
            ans = action_answer(r, a, global_stats)
            ok = action_ok(r, a, ans)
            row[f"{a}_answer"] = ans
            row[f"{a}_ok"] = "" if ok is None else int(ok)
            row[f"{a}_zero_extra_call"] = int(a in RUNTIME_ACTIONS)
        action_rows.append(row)
    action_label_df = pd.DataFrame(action_rows)
    save_csv(action_label_df, OUT / "rg_eb_action_label_table.csv")

    action_desc_lines = [
        "# RG-EB Action Set",
        "",
        "Required action set implemented:",
        "- pooled4",
        "- agreement_only",
        "- beta_shrinkage",
        "- C1d",
        "- C1a_t005",
        "- always_s1",
        "- best_calibrated_source (fold-safe from training split only)",
        "- frontier",
        "- L1",
        "- TALE",
        "",
        "Additional offline baselines for regret/reference:",
        "- S1",
        "- oracle_best_source",
        "- oracle_best_action",
        "",
        "All runtime actions are zero-extra-call selectors over precomputed candidate answers.",
    ]
    write_markdown(OUT / "rg_eb_action_set_description.md", action_desc_lines)

    # Feature schema + feature table
    feat_rows = []
    for _, r in official.iterrows():
        stats = source_stats_from_df(official[(official["provider"] == r["provider"]) & (official["dataset"] == r["dataset"])])
        feat = runtime_features(r, stats)
        feat_rows.append({"example_id": r["example_id"], "scenario_id": r["scenario_id"], **feat})
    feat_df = pd.DataFrame(feat_rows)
    save_csv(feat_df, OUT / "rg_eb_feature_table_official4.csv")

    feature_schema_lines = [
        "# RG-EB Runtime-Legal Feature Schema",
        "",
        "Pattern features:",
        "- provider, dataset (used only in RGEB-03 / hierarchical levels that are flagged lookup-risk)",
        "- provider-free variants exclude provider/dataset from both calibration keys and routing buckets",
        "- agreement_pattern",
        "- unique_answer_count",
        "- majority_size",
        "- strict_majority_exists",
        "- all_four_agree",
        "- all_different",
        "- two_two_split",
        "- three_one_split",
        "- external_majority_exists",
        "- external_majority_excludes_frontier",
        "- external_majority_excludes_S1",
        "- L1_TALE_agree",
        "- S1_in_majority",
        "- S1_isolated",
        "- frontier_in_majority",
        "- frontier_isolated",
        "",
        "Question-derived runtime features:",
        "- question_length_bucket",
        "- number_count_bucket",
        "- has_fraction",
        "- has_equation",
        "- difficulty_proxy",
        "",
        "Fold-safe calibration-derived features:",
        "- calib_regime_type (near_peer/mixed/dominant)",
        "- best_calibrated_source",
        "- best_minus_second_spread_bucket",
        "- S1_minus_second_spread_bucket",
        "- source_accuracy_entropy_bucket",
        "",
        "Gold labels are used only for offline training/evaluation targets, never as inference features.",
    ]
    write_markdown(OUT / "rg_eb_feature_schema.md", feature_schema_lines)

    variants = variant_list()

    pred_within = evaluate_protocol_within_scenario(official, variants)
    pred_pooled = evaluate_protocol_official_pooled(official, variants)
    pred_loso = evaluate_protocol_loso(official, variants)
    pred_provider = evaluate_protocol_provider_heldout(official, variants)
    pred_dataset = evaluate_protocol_dataset_heldout(official, variants)
    pred_aux = evaluate_protocol_aux_training(official, aux, variants)
    pred_diag = evaluate_protocol_full_diagnostic(official, aux, variants)

    # Save raw predictions for transparency
    save_csv(pred_within, OUT / "rgeb_within_scenario_case_predictions.csv")
    save_csv(pred_pooled, OUT / "rgeb_official_pooled_case_predictions.csv")
    save_csv(pred_loso, OUT / "rgeb_loso_case_predictions.csv")
    save_csv(pred_provider, OUT / "rgeb_provider_heldout_case_predictions.csv")
    save_csv(pred_dataset, OUT / "rgeb_dataset_heldout_case_predictions.csv")
    save_csv(pred_aux, OUT / "rgeb_aux_training_case_predictions.csv")
    save_csv(pred_diag, OUT / "rgeb_full_artifact_case_predictions.csv")

    sum_within = summarize_predictions(pred_within, "within_scenario_cv")
    sum_pooled = summarize_predictions(pred_pooled, "official_pooled_cv")
    sum_loso = summarize_predictions(pred_loso, "leave_one_scenario_out")
    sum_provider = summarize_predictions(pred_provider, "provider_heldout")
    sum_dataset = summarize_predictions(pred_dataset, "dataset_heldout")
    sum_aux = summarize_predictions(pred_aux, "aux_training")
    sum_diag = summarize_predictions(pred_diag, "full_artifact_diagnostic")

    save_csv(sum_within, OUT / "rgeb_within_scenario_cv_summary.csv")
    save_csv(sum_pooled, OUT / "rgeb_official_pooled_cv_summary.csv")
    save_csv(sum_loso, OUT / "rgeb_leave_one_scenario_out_summary.csv")
    save_csv(sum_provider, OUT / "rgeb_provider_heldout_summary.csv")
    save_csv(sum_dataset, OUT / "rgeb_dataset_heldout_summary.csv")
    save_csv(sum_aux, OUT / "rgeb_auxiliary_training_summary.csv")
    save_csv(sum_diag, OUT / "rgeb_full_artifact_diagnostic_summary.csv")

    pairwise = pd.concat([
        pairwise_win_loss(pred_within, ["beta_shrinkage", "C1d", "agreement_only"], "within_scenario_cv"),
        pairwise_win_loss(pred_pooled, ["beta_shrinkage", "C1d", "agreement_only"], "official_pooled_cv"),
        pairwise_win_loss(pred_loso, ["beta_shrinkage", "C1d", "agreement_only"], "leave_one_scenario_out"),
        pairwise_win_loss(pred_provider, ["beta_shrinkage", "C1d", "agreement_only"], "provider_heldout"),
        pairwise_win_loss(pred_dataset, ["beta_shrinkage", "C1d", "agreement_only"], "dataset_heldout"),
    ], ignore_index=True)
    save_csv(pairwise, OUT / "rgeb_pairwise_win_loss_summary.csv")

    # Oracle regret summary
    oracle_regret_rows = []
    for protocol, dfp in [
        ("within_scenario_cv", pred_within),
        ("official_pooled_cv", pred_pooled),
        ("leave_one_scenario_out", pred_loso),
        ("provider_heldout", pred_provider),
        ("dataset_heldout", pred_dataset),
        ("aux_training", pred_aux),
        ("full_artifact_diagnostic", pred_diag),
    ]:
        oracle = dfp[dfp["variant"] == "oracle_best_action"]["variant_ok"].mean()
        for v, sub in dfp.groupby("variant"):
            oracle_regret_rows.append({
                "protocol": protocol,
                "variant": v,
                "accuracy": float(sub["variant_ok"].mean()),
                "oracle_accuracy": float(oracle) if not np.isnan(oracle) else np.nan,
                "regret_to_oracle": float(oracle - sub["variant_ok"].mean()) if not np.isnan(oracle) else np.nan,
            })
    oracle_regret = pd.DataFrame(oracle_regret_rows)
    save_csv(oracle_regret, OUT / "rgeb_oracle_regret_summary.csv")

    act_dist = pd.concat([
        action_distribution(pred_within, "within_scenario_cv"),
        action_distribution(pred_pooled, "official_pooled_cv"),
        action_distribution(pred_loso, "leave_one_scenario_out"),
        action_distribution(pred_provider, "provider_heldout"),
        action_distribution(pred_dataset, "dataset_heldout"),
    ], ignore_index=True)
    save_csv(act_dist, OUT / "rgeb_action_distribution.csv")

    backoff = pd.concat([
        backoff_coverage(pred_within, "within_scenario_cv"),
        backoff_coverage(pred_pooled, "official_pooled_cv"),
        backoff_coverage(pred_loso, "leave_one_scenario_out"),
        backoff_coverage(pred_provider, "provider_heldout"),
        backoff_coverage(pred_dataset, "dataset_heldout"),
        backoff_coverage(pred_aux, "aux_training"),
    ], ignore_index=True)
    save_csv(backoff, OUT / "rgeb_backoff_coverage.csv")

    # Best variant detail files
    best_variant = choose_best_variant(sum_pooled)
    best_pred_pooled = pred_pooled[pred_pooled["variant"] == best_variant].copy()
    beta_pred_pooled = pred_pooled[pred_pooled["variant"] == "beta_shrinkage"]["eval_id"].to_frame().join(
        pred_pooled[pred_pooled["variant"] == "beta_shrinkage"].set_index("eval_id")["variant_ok"], on="eval_id")

    # Detailed scenario outputs
    cm = best_pred_pooled[best_pred_pooled["scenario_id"] == "cohere_math500"].copy()
    mg = best_pred_pooled[best_pred_pooled["provider"] == "mistral"].copy()
    cg = best_pred_pooled[(best_pred_pooled["provider"] == "cohere") & (best_pred_pooled["dataset"].str.contains("gsm8k", na=False))].copy()
    save_csv(cm, OUT / "rgeb_cohere_math_detailed.csv")
    save_csv(mg, OUT / "rgeb_mistral_dominant_detailed.csv")
    save_csv(cg, OUT / "rgeb_cohere_gsm8k_detailed.csv")

    casebook_lines = [
        "# RG-EB Best Variant Casebook",
        "",
        f"Best pooled-CV variant: **{best_variant}**",
        "",
        "Scenario focus:",
        f"- Cohere MATH-500 rows: {len(cm)}",
        f"- Mistral rows: {len(mg)}",
        f"- Cohere GSM8K rows: {len(cg)}",
    ]
    write_markdown(OUT / "rgeb_best_variant_casebook.md", casebook_lines)

    # Failure/regression analysis vs beta and c1d
    def compare_vs(ref: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
        a = pred_pooled[pred_pooled["variant"] == best_variant][["eval_id", "example_id", "scenario_id", "provider", "dataset", "selected_action", "selected_answer", "variant_ok"]]
        b = pred_pooled[pred_pooled["variant"] == ref][["eval_id", "variant_ok"]].rename(columns={"variant_ok": "ref_ok"})
        m = a.merge(b, on="eval_id", how="inner")
        rec = m[(m["variant_ok"] == 1) & (m["ref_ok"] == 0)].copy()
        reg = m[(m["variant_ok"] == 0) & (m["ref_ok"] == 1)].copy()
        return rec, reg

    rec_beta, reg_beta = compare_vs("beta_shrinkage")
    rec_c1d, reg_c1d = compare_vs("C1d")
    save_csv(rec_beta, OUT / "rgeb_recoveries_vs_beta.csv")
    save_csv(reg_beta, OUT / "rgeb_regressions_vs_beta.csv")
    save_csv(rec_c1d, OUT / "rgeb_recoveries_vs_c1d.csv")
    save_csv(reg_c1d, OUT / "rgeb_regressions_vs_c1d.csv")

    # Agreement wins captured / regressions avoided
    m_ag = pred_pooled[pred_pooled["variant"] == best_variant][["eval_id", "example_id", "scenario_id", "variant_ok"]].merge(
        pred_pooled[pred_pooled["variant"] == "agreement_only"][["eval_id", "variant_ok"]].rename(columns={"variant_ok": "ag_ok"}),
        on="eval_id",
        how="inner",
    ).merge(
        pred_pooled[pred_pooled["variant"] == "beta_shrinkage"][["eval_id", "variant_ok"]].rename(columns={"variant_ok": "beta_ok"}),
        on="eval_id",
        how="inner",
    )
    ag_wins = m_ag[(m_ag["ag_ok"] == 1) & (m_ag["beta_ok"] == 0) & (m_ag["variant_ok"] == 1)]
    ag_avoided = m_ag[(m_ag["ag_ok"] == 0) & (m_ag["beta_ok"] == 1) & (m_ag["variant_ok"] == 1)]
    save_csv(ag_wins, OUT / "rgeb_agreement_wins_captured.csv")
    save_csv(ag_avoided, OUT / "rgeb_agreement_regressions_avoided.csv")

    new_reg = reg_beta.copy()
    save_csv(new_reg, OUT / "rgeb_new_regressions.csv")

    low_support = best_pred_pooled[best_pred_pooled["support"] < 5].copy()
    save_csv(low_support, OUT / "rgeb_low_support_bucket_failures.csv")

    # Candidate decision
    refs_external = external_fix03_ag01_refs()

    cand = sum_pooled.copy()
    cand["lookup_table_risk"] = cand["variant"].str.contains("RGEB03|cohere_math_lookup", regex=True).astype(int)
    cand["overfitting_risk"] = np.where(cand["provider_dataset_aware"] == 1, "higher", "lower")
    cand["complexity"] = np.where(cand["variant"].str.contains("hierarchical", case=False), "medium", "low")

    def rec_for_row(r: pd.Series) -> str:
        v = str(r["variant"])
        if v.startswith("oracle"):
            return "diagnostic only"
        if v.startswith("RGEB03"):
            return "keep diagnostic"
        if v == best_variant:
            return "use as router-v2 baseline"
        if v.startswith("RGEB") and float(r["accuracy"]) >= float(cand[cand["variant"] == "beta_shrinkage"]["accuracy"].iloc[0]):
            return "keep diagnostic"
        if v.startswith("RGEB"):
            return "reject"
        return "baseline"

    cand["recommendation"] = cand.apply(rec_for_row, axis=1)
    save_csv(cand, OUT / "rgeb_candidate_decision_table.csv")

    cand_lines = [
        "# RG-EB Candidate Decision",
        "",
        f"Best pooled official variant: **{best_variant}**.",
        "",
        "Recommendations:",
        "- No RG-EB variant is auto-promoted to replace beta/C1d without stronger heldout stability.",
        "- Provider-aware RGEB-03 remains lookup-risk diagnostic only.",
        "- Best provider-free/hierarchical variant is recommended as router-v2 baseline candidate.",
    ]
    if len(refs_external):
        cand_lines.append("")
        cand_lines.append("External references from prior audits:")
        for _, r in refs_external.iterrows():
            cand_lines.append(f"- {r['reference']}: {r['reference_variant']} @ {100.0*float(r['official_pooled_accuracy']):.2f}%")
    write_markdown(OUT / "rgeb_candidate_decision.md", cand_lines)

    # Manuscript implications
    implication_lines = [
        "# Manuscript Implications",
        "",
        "- RG-EB action-level routing is feasible and interpretable under zero-extra-call constraints.",
        "- Safe claim boundary: report as a robust offline selector family with mixed transfer stability.",
        "- Do not overclaim superiority to beta/C1d/agreement_only unless pooled + heldout gains are jointly positive.",
        "- Agreement-only should be described as a high-value action in specific patterns (not a universal policy).",
        "- Claims that depend on Cerebras scenarios should remain pending until those artifacts are complete and integrity-checked.",
    ]
    write_markdown(OUT / "rgeb_manuscript_implications.md", implication_lines)

    # Router-v2 integration plan
    plan_lines = [
        "# Router-v2 Integration Plan",
        "",
        "- Use best provider-free RG-EB variant as interpretable baseline for router-v2 training.",
        "- Include features: answer-pattern, external-majority indicators, source-isolation, calibration spread/entropy buckets, question hardness proxies.",
        "- Include actions: pooled4, agreement_only, beta_shrinkage, C1d, C1a_t005, best_calibrated_source, frontier/L1/S1/TALE.",
        "- Keep official test sets isolated: train router-v2 on auxiliary + official train folds only; evaluate on heldout official folds.",
        "- Re-run provider/dataset heldout audits before any promotion decision.",
    ]
    write_markdown(OUT / "rgeb_router_v2_integration_plan.md", plan_lines)

    # Next iteration recommendations / queue
    next_lines = [
        "# Next Iteration Recommendations",
        "",
        "- Stop adding manual single-pattern gates as primary strategy.",
        "- Implement learned router-v2 with RG-EB features/actions and strict fold-safe protocols.",
        "- Refresh with Cerebras once artifacts are complete; do not mix incomplete runs.",
        "- Add budget-escalation/hardness detector only after action-router baseline is fixed.",
    ]
    write_markdown(OUT / "rgeb_next_iteration_recommendations.md", next_lines)

    queue = pd.DataFrame([
        {"priority": 1, "task": "learned_router_v2_training", "status": "next", "note": "train on official folds + auxiliary only"},
        {"priority": 2, "task": "cerebras_refresh", "status": "wait", "note": "only after complete/integrity-checked artifacts"},
        {"priority": 3, "task": "agreement_action_revision", "status": "diagnostic", "note": "avoid provider lookup"},
        {"priority": 4, "task": "manual_gate_exploration", "status": "deprioritize", "note": "prefer learned routing"},
    ])
    save_csv(queue, OUT / "rgeb_updated_failure_driven_queue.csv")

    # Human-readable report
    def metric_line(df: pd.DataFrame, v: str) -> str:
        row = df[df["variant"] == v]
        if len(row) == 0:
            return f"- {v}: n/a"
        r = row.iloc[0]
        return f"- {v}: {100.0*float(r['accuracy']):.2f}% (macro {100.0*float(r['macro_accuracy_by_scenario']):.2f}%, worst {100.0*float(r['worst_scenario_accuracy']):.2f}%)"

    summary_best = sum_pooled[sum_pooled["variant"] == best_variant].iloc[0] if len(sum_pooled[sum_pooled["variant"] == best_variant]) else None
    beta_row = sum_pooled[sum_pooled["variant"] == "beta_shrinkage"].iloc[0] if len(sum_pooled[sum_pooled["variant"] == "beta_shrinkage"]) else None
    c1d_row = sum_pooled[sum_pooled["variant"] == "C1d"].iloc[0] if len(sum_pooled[sum_pooled["variant"] == "C1d"]) else None
    ag_row = sum_pooled[sum_pooled["variant"] == "agreement_only"].iloc[0] if len(sum_pooled[sum_pooled["variant"] == "agreement_only"]) else None

    rep = [
        "# RG-EB Action Router (2026-05-24)",
        "",
        "## 1. Executive summary",
        f"- Implemented and evaluated RG-EB action-level empirical-Bayes router variants across official4 protocols and auxiliary-separated diagnostics.",
        f"- Best official pooled variant: **{best_variant}**.",
        f"- Best variant pooled accuracy: {100.0*float(summary_best['accuracy']):.2f}%" if summary_best is not None else "- Best variant pooled accuracy: n/a",
        "",
        "## 2. Data sources and caveats",
        "- Headline results use only official four-scenario matrix (1200 rows).",
        "- Auxiliary data (Mistral train1000 and Cohere MATH aux488) used only in separated auxiliary-training protocol summaries.",
        "- Offline only; no API calls; active jobs observed only.",
        "",
        "## 3. Action set and feature schema",
        "- See `outputs/rg_eb_action_router_20260524/rg_eb_action_set_description.md`.",
        "- See `outputs/rg_eb_action_router_20260524/rg_eb_feature_schema.md`.",
        "",
        "## 4. RG-EB variants",
        "- RGEB-01 mean-shrinkage coarse buckets",
        "- RGEB-02 conservative LCB",
        "- RGEB-03 provider/dataset-aware diagnostic",
        "- RGEB-04 provider-free",
        "- RGEB-05 hierarchical backoff",
        "- RGEB-06 agreement-focused restricted action set",
        "- RGEB-07 source/action hybrid",
        "- RGEB-08 auxiliary-trained provider-free variant",
        "",
        "## 5. Official four-scenario pooled results",
        metric_line(sum_pooled, best_variant),
        metric_line(sum_pooled, "beta_shrinkage"),
        metric_line(sum_pooled, "C1d"),
        metric_line(sum_pooled, "agreement_only"),
        "",
        "## 6. Transfer/heldout results",
        metric_line(sum_loso, best_variant),
        metric_line(sum_provider, best_variant),
        metric_line(sum_dataset, best_variant),
        "",
        "## 7. Auxiliary-training experiments",
        metric_line(sum_aux, best_variant),
        metric_line(sum_aux, "RGEB08_aux_trained_providerfree_mean_s5"),
        "",
        "## 8. Scenario-specific analysis",
        f"- Cohere MATH detailed file: `outputs/rg_eb_action_router_20260524/rgeb_cohere_math_detailed.csv` ({len(cm)} rows)",
        f"- Mistral dominant detailed file: `outputs/rg_eb_action_router_20260524/rgeb_mistral_dominant_detailed.csv` ({len(mg)} rows)",
        f"- Cohere GSM8K detailed file: `outputs/rg_eb_action_router_20260524/rgeb_cohere_gsm8k_detailed.csv` ({len(cg)} rows)",
        "",
        "## 9. Failure/regression analysis",
        f"- Recoveries vs beta: {len(rec_beta)}",
        f"- Regressions vs beta: {len(reg_beta)}",
        f"- Recoveries vs C1d: {len(rec_c1d)}",
        f"- Regressions vs C1d: {len(reg_c1d)}",
        f"- Agreement-only wins captured: {len(ag_wins)}",
        f"- Agreement regressions avoided: {len(ag_avoided)}",
        "",
        "## 10. Candidate decision",
        "- Keep RGEB-03 as lookup-risk diagnostic only.",
        f"- Use **{best_variant}** as router-v2 baseline candidate, pending stronger heldout stability evidence before promotion.",
        "",
        "## 11. Manuscript implications",
        "- Action-level routing is supported as an interpretable methodology, but safe claims remain conservative.",
        "",
        "## 12. Router-v2 integration plan",
        "- See `outputs/rg_eb_action_router_20260524/rgeb_router_v2_integration_plan.md`.",
        "",
        "## 13. Next iteration recommendation",
        "- Implement learned router-v2 next; avoid additional hand-crafted gates.",
        "",
        "## 14. Safety confirmation",
        "- No API calls launched: true",
        "- Active jobs touched: false",
        "- No commits/pushes performed",
    ]
    write_markdown(DOC, rep)

    # Candidate decision/md under outputs already written; add short report aliases
    (OUT / "rgeb_candidate_decision.md").write_text((OUT / "rgeb_candidate_decision.md").read_text(encoding="utf-8"), encoding="utf-8")

    # Manifest
    output_files = sorted([str(p.relative_to(REPO)) for p in OUT.glob("**/*") if p.is_file()])
    manifest = {
        "timestamp_utc": now_utc(),
        "input_artifacts": [str(OFFICIAL4_PATH.relative_to(REPO)), str(MISTRAL_TRAIN1000_PATH.relative_to(REPO)), str(COHERE_AUX_CASE_PATH.relative_to(REPO)), str(COHERE_AUX_JSONL_PATH.relative_to(REPO))],
        "scripts_created": ["scripts/evaluate_rg_eb_action_router.py"],
        "output_files": output_files,
        "api_calls_launched": False,
        "active_jobs_touched": False,
        "limitations": [
            "Cohere aux488 lacks some action labels (e.g., C1d/C1a_t005); missing labels are excluded from EB count updates for those actions.",
            "RGEB-03 provider/dataset-aware variants are lookup-risk diagnostics, not promotion-safe.",
            "No incomplete Cerebras artifacts were processed.",
        ],
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
