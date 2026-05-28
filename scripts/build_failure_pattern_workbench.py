#!/usr/bin/env python3
"""
Failure Pattern Mining Workbench (2026-05-24).

Builds a repeatable, offline analysis bundle from completed artifacts:
- unified case-level table
- algorithm failure views
- grouped failure-pattern mining
- named failure clusters + casebooks
- mechanism diagnoses
- candidate fixes + implementation queue
- human-readable report + manifest

Safety:
- no API calls
- no active job interaction
- no source artifact mutation
"""

from __future__ import annotations

import datetime
import json
import math
import os
import re
from collections import Counter
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_ROOT = os.path.join(REPO, "outputs", "failure_pattern_mining_workbench_20260524")
DOC_REPORT = os.path.join(REPO, "docs", "FAILURE_PATTERN_MINING_WORKBENCH_20260524.md")
CASEBOOK_DIR = os.path.join(OUT_ROOT, "failure_cluster_casebooks")

TIMESTAMP = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

os.makedirs(OUT_ROOT, exist_ok=True)
os.makedirs(CASEBOOK_DIR, exist_ok=True)

# Canonical input tables
C1_BASE = os.path.join(
    REPO,
    "outputs",
    "reliability_gated_pooled_voting_c1_20260524",
    "c1_unified_case_table.csv",
)
C1_ROUTER = os.path.join(
    REPO,
    "outputs",
    "reliability_gated_pooled_voting_c1_20260524",
    "c1_router_augmented_feature_table.csv",
)

# Learned router case-level predictions (within-scenario CV rows)
LEARNED_ROUTER_CASE_PRED = os.path.join(
    REPO,
    "outputs",
    "cohere_math500_auxiliary_mlj_reprocess_20260524",
    "learned_router_four_datasets",
    "case_level_router_predictions.csv",
)

# Raw per-example records for filling missing question/problem text and optional features.
SCENARIO_RECORDS = {
    "cohere_gsm8k": os.path.join(
        REPO,
        "outputs",
        "canonical_final300_cohere_contract_matched_live_20260523T181948Z",
        "cohere_real_model_cost_normalized_validation_20260523T181948Z",
        "per_example_records.jsonl",
    ),
    "mistral_gsm8k": os.path.join(
        REPO,
        "outputs",
        "merged_repaired_cohere_mistral_selector_replay_20260524",
        "mistral_full300_merged_per_example_records.jsonl",
    ),
    "mistral_math500": os.path.join(
        REPO,
        "outputs",
        "scenarios_5_6_math500_full_tracking_20260524",
        "mistral_math500_full_20260524T014937Z",
        "cohere_real_model_cost_normalized_validation_20260524T014937Z",
        "per_example_records.jsonl",
    ),
    "cohere_math500_aux": os.path.join(
        REPO,
        "outputs",
        "cohere_math500_auxiliary_mlj_reprocess_20260524",
        "cohere_math500_auxiliary_complete_4method_records.jsonl",
    ),
}

# Source inventory metadata that explicitly mirrors the user-requested sources.
SOURCE_INVENTORY_SPEC = [
    {
        "source_group": "cohere_gsm8k_official",
        "doc": "docs/COHERE_CANONICAL_FINAL300_FROZEN_AGREEMENT_LIVE_RESULT_20260523.md",
        "artifact": "outputs/cohere_canonical_final300_frozen_agreement_live_result_20260523/",
    },
    {
        "source_group": "cohere_gsm8k_official",
        "doc": "docs/COHERE_CANONICAL_FINAL300_FROZEN_AGREEMENT_LIVE_RESULT_20260523.md",
        "artifact": "outputs/canonical_final300_cohere_contract_matched_live_20260523T181948Z/",
    },
    {
        "source_group": "mistral_gsm8k_official",
        "doc": "docs/MERGED_REPAIRED_COHERE_MISTRAL_SELECTOR_REPLAY_20260524.md",
        "artifact": "outputs/merged_repaired_cohere_mistral_selector_replay_20260524/",
    },
    {
        "source_group": "mistral_math500_official",
        "doc": "docs/MISTRAL_MATH500_SCENARIO5_PROCESSING_20260524.md",
        "artifact": "outputs/mistral_math500_scenario5_processing_20260524/",
    },
    {
        "source_group": "cohere_math500_auxiliary",
        "doc": "docs/COHERE_MATH500_AUXILIARY_MLJ_REPROCESS_20260524.md",
        "artifact": "outputs/cohere_math500_auxiliary_mlj_reprocess_20260524/",
    },
    {
        "source_group": "reliability_gated_c1",
        "doc": "docs/RELIABILITY_GATED_POOLED_VOTING_C1_20260524.md",
        "artifact": "outputs/reliability_gated_pooled_voting_c1_20260524/",
    },
    {
        "source_group": "cross_scenario_investigation",
        "doc": "docs/CROSS_SCENARIO_ALGORITHM_IMPROVEMENT_INVESTIGATION_20260524.md",
        "artifact": "outputs/cross_scenario_algorithm_improvement_investigation_20260524/",
    },
]

SCENARIO_META = {
    "cohere_gsm8k": {
        "provider": "cohere",
        "dataset": "gsm8k",
        "official_or_auxiliary": "official",
    },
    "mistral_gsm8k": {
        "provider": "mistral",
        "dataset": "gsm8k",
        "official_or_auxiliary": "official",
    },
    "mistral_math500": {
        "provider": "mistral",
        "dataset": "math500",
        "official_or_auxiliary": "official",
    },
    "cohere_math500_aux": {
        "provider": "cohere",
        "dataset": "math500",
        "official_or_auxiliary": "auxiliary",
    },
}

# Beta-shrinkage decision identity inferred from scenario-level replay conclusions.
BETA_SOURCE_BY_SCENARIO = {
    "cohere_gsm8k": "pooled4",
    "mistral_gsm8k": "S1",
    "mistral_math500": "S1",
    "cohere_math500_aux": "pooled4",
}

ALGORITHM_COLS = {
    "beta_shrinkage": "beta_shrinkage_ok",
    "C1d": "C1d_ok",
    "pooled4": "pooled4_ok",
    "always_S1": "always_S1_ok",
    "agreement_only": "agreement_only_ok",
    "C1a_t005": "C1a_t005_ok",
    "learned_router": "learned_router_ok",
}


def _safe_bool(v) -> bool:
    if isinstance(v, (bool, np.bool_)):
        return bool(v)
    if pd.isna(v):
        return False
    if isinstance(v, (int, np.integer, float, np.floating)):
        return bool(int(v))
    s = str(v).strip().lower()
    return s in {"1", "true", "yes", "y", "t"}


def _to_jsonable(val):
    if isinstance(val, (np.integer,)):
        return int(val)
    if isinstance(val, (np.floating,)):
        if math.isnan(float(val)):
            return None
        return float(val)
    if pd.isna(val):
        return None
    return val


def _read_jsonl(path: str) -> Iterable[dict]:
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def _majority_answer(answers: List[str]) -> Tuple[str, int]:
    clean = [a for a in answers if isinstance(a, str) and a != ""]
    if not clean:
        return "", 0
    ctr = Counter(clean)
    top_answer, top_count = ctr.most_common(1)[0]
    return top_answer, int(top_count)


def _agreement_only_answer(frontier: str, l1: str, s1: str, tale: str) -> str:
    ext = [l1, s1, tale]
    top, count = _majority_answer(ext)
    if count >= 2 and top and top != frontier:
        return top
    return frontier


def _math_topic(question: str, dataset: str) -> str:
    if not isinstance(question, str) or not question.strip():
        return "unknown"
    q = question.lower()
    if "triangle" in q or "angle" in q or "circle" in q or "radius" in q or "perimeter" in q:
        return "geometry"
    if "probability" in q or "dice" in q or "coin" in q:
        return "probability"
    if "integral" in q or "derivative" in q or "limit" in q:
        return "calculus"
    if "prime" in q or "divisible" in q or "remainder" in q or "mod" in q:
        return "number_theory"
    if "equation" in q or "solve" in q or "polynomial" in q or "factor" in q:
        return "algebra"
    if "combination" in q or "permutation" in q:
        return "combinatorics"
    if "math" in dataset.lower():
        return "other_math"
    return "word_problem"


def _answer_features(ans: str) -> dict:
    a = "" if ans is None else str(ans).strip()
    if a == "":
        return {
            "answer_length": 0,
            "parse_success": 0,
            "final_answer_cleanliness": "empty",
            "reasoning_length_bucket": "none",
        }

    numeric_like = bool(re.fullmatch(r"[-+]?\d+(?:\.\d+)?", a))
    fraction_like = bool(re.fullmatch(r"[-+]?\d+\s*/\s*\d+", a))
    percent_like = a.endswith("%") and bool(re.search(r"\d", a))

    if numeric_like or fraction_like or percent_like:
        clean = "clean_numeric"
        parse_success = 1
    elif len(a) <= 32 and re.search(r"\d", a):
        clean = "semi_clean_numeric"
        parse_success = 1
    else:
        clean = "free_form_or_messy"
        parse_success = 0

    alen = len(a)
    if alen <= 8:
        bucket = "very_short"
    elif alen <= 24:
        bucket = "short"
    elif alen <= 64:
        bucket = "medium"
    else:
        bucket = "long"

    return {
        "answer_length": alen,
        "parse_success": parse_success,
        "final_answer_cleanliness": clean,
        "reasoning_length_bucket": bucket,
    }


def load_question_gold_maps() -> Tuple[Dict[Tuple[str, str], str], Dict[Tuple[str, str], str]]:
    """Load question/gold text keyed by (scenario_id, example_id) from per-example records."""
    qmap: Dict[Tuple[str, str], str] = {}
    gmap: Dict[Tuple[str, str], str] = {}

    for scenario_id, path in SCENARIO_RECORDS.items():
        if not os.path.exists(path):
            continue
        for row in _read_jsonl(path):
            ex = row.get("example_id")
            if not ex:
                continue
            key = (scenario_id, ex)
            q = row.get("question")
            if isinstance(q, str) and q.strip() and key not in qmap:
                qmap[key] = q.strip()
            g = row.get("gold_answer_canonical") or row.get("gold_answer")
            if isinstance(g, str) and g.strip() and key not in gmap:
                gmap[key] = g.strip()

    return qmap, gmap


def load_learned_router_rows() -> pd.DataFrame:
    if not os.path.exists(LEARNED_ROUTER_CASE_PRED):
        return pd.DataFrame(columns=["scenario_id", "example_id", "learned_router_decision", "learned_router_answer", "learned_router_ok"])

    usecols = [
        "scenario_id",
        "example_id",
        "model_name",
        "protocol",
        "selected_action",
        "selected_answer",
        "selected_correct",
    ]
    df = pd.read_csv(LEARNED_ROUTER_CASE_PRED, usecols=usecols)
    df = df[
        (df["model_name"] == "action_hgb_router_with_ids")
        & (df["protocol"].astype(str).str.startswith("within_"))
    ].copy()

    # The filtered subset is already one row per (scenario, example).
    df = df.rename(
        columns={
            "selected_action": "learned_router_decision",
            "selected_answer": "learned_router_answer",
            "selected_correct": "learned_router_ok",
        }
    )
    return df[["scenario_id", "example_id", "learned_router_decision", "learned_router_answer", "learned_router_ok"]]


def build_unified_case_table() -> pd.DataFrame:
    print("[step3] Building unified case table...")

    base = pd.read_csv(C1_BASE)
    feat = pd.read_csv(C1_ROUTER)

    # Merge supplemental C1 columns from router-augmented table.
    extra_cols = [c for c in feat.columns if c not in base.columns]
    unified = base.merge(feat[["scenario_id", "example_id"] + extra_cols], on=["scenario_id", "example_id"], how="left")

    # Add official/auxiliary label + canonical provider/dataset normalization.
    unified["official_or_auxiliary"] = unified["scenario_id"].map(
        {k: v["official_or_auxiliary"] for k, v in SCENARIO_META.items()}
    )

    # Fill missing question/gold from raw records.
    qmap, gmap = load_question_gold_maps()
    if "question" not in unified.columns:
        unified["question"] = ""
    if "gold" not in unified.columns:
        unified["gold"] = ""

    def _fill_text(row, field, m):
        cur = row.get(field)
        if isinstance(cur, str) and cur.strip():
            return cur
        return m.get((row["scenario_id"], row["example_id"]), cur)

    unified["question"] = unified.apply(lambda r: _fill_text(r, "question", qmap), axis=1)
    unified["gold"] = unified.apply(lambda r: _fill_text(r, "gold", gmap), axis=1)

    # Add learned-router case-level decisions (if available).
    lr = load_learned_router_rows()
    unified = unified.merge(lr, on=["scenario_id", "example_id"], how="left")

    # Common aliases used throughout workbench outputs.
    unified["C1d_ok"] = unified.get("c1_ok_c1d", np.nan)
    unified["C1a_t005_ok"] = unified.get("c1_ok_c1a_t005", np.nan)
    unified["dominant_source"] = unified.get("c1_decision_c1d", "none").fillna("none")

    # Ensure expected source columns exist.
    for col in ["frontier_ans", "L1_ans", "S1_ans", "TALE_ans", "frontier_ok", "L1_ok", "S1_ok", "TALE_ok"]:
        if col not in unified.columns:
            unified[col] = np.nan

    # Majority + answer pattern features.
    if "answer_pattern_bucket" not in unified.columns:
        def _bucket(row):
            if _safe_bool(row.get("all_four_agree")):
                return "all_agree"
            if _safe_bool(row.get("three_one_split")):
                return "3-1_split"
            if _safe_bool(row.get("two_two_split")):
                return "2-2_split"
            if _safe_bool(row.get("all_different")):
                return "all_different"
            if _safe_bool(row.get("no_majority_flag")):
                return "no_majority"
            return "other"

        unified["answer_pattern_bucket"] = unified.apply(_bucket, axis=1)

    # Derived source-level bookkeeping.
    bool_cols = ["frontier_ok", "L1_ok", "S1_ok", "TALE_ok", "pooled4_ok", "beta_shrinkage_ok", "agreement_only_ok", "always_S1_ok", "oracle_ok", "C1d_ok", "C1a_t005_ok", "learned_router_ok"]
    for col in bool_cols:
        if col in unified.columns:
            unified[col] = unified[col].map(_safe_bool)

    unified["all_sources_wrong"] = (~unified["frontier_ok"] & ~unified["L1_ok"] & ~unified["S1_ok"] & ~unified["TALE_ok"]).astype(int)
    unified["n_sources_correct"] = (
        unified["frontier_ok"].astype(int)
        + unified["L1_ok"].astype(int)
        + unified["S1_ok"].astype(int)
        + unified["TALE_ok"].astype(int)
    )

    # Best source identity per case, using scenario-level source reliability as tie-break.
    scenario_source_acc = (
        unified.groupby("scenario_id")[["frontier_ok", "L1_ok", "S1_ok", "TALE_ok"]]
        .mean()
        .to_dict("index")
    )

    def _best_source_identity(row):
        srcs = ["frontier", "L1", "S1", "TALE"]
        ok_map = {
            "frontier": _safe_bool(row.get("frontier_ok")),
            "L1": _safe_bool(row.get("L1_ok")),
            "S1": _safe_bool(row.get("S1_ok")),
            "TALE": _safe_bool(row.get("TALE_ok")),
        }
        good = [s for s in srcs if ok_map[s]]
        if not good:
            return "none"
        if len(good) == 1:
            return good[0]
        accs = scenario_source_acc.get(row["scenario_id"], {})
        return sorted(good, key=lambda s: accs.get(f"{s}_ok", 0.0), reverse=True)[0]

    unified["best_source_identity"] = unified.apply(_best_source_identity, axis=1)
    unified["only_source_correct_identity"] = unified.apply(
        lambda r: r["best_source_identity"] if int(r["n_sources_correct"]) == 1 else "none",
        axis=1,
    )

    # Selector decision-answer fields.
    unified["pooled4_decision_answer"] = unified.apply(
        lambda r: r.get("majority_answer") if _safe_bool(r.get("has_majority")) and isinstance(r.get("majority_answer"), str) and r.get("majority_answer") != "" else r.get("frontier_ans"),
        axis=1,
    )
    unified["pooled4_decision"] = unified.apply(
        lambda r: "majority" if _safe_bool(r.get("has_majority")) else "frontier_fallback",
        axis=1,
    )

    unified["agreement_only_decision_answer"] = unified.apply(
        lambda r: _agreement_only_answer(r.get("frontier_ans"), r.get("L1_ans"), r.get("S1_ans"), r.get("TALE_ans")),
        axis=1,
    )
    unified["agreement_only_decision"] = unified.apply(
        lambda r: "external_majority" if r["agreement_only_decision_answer"] != r.get("frontier_ans") else "frontier",
        axis=1,
    )

    unified["always_S1_decision"] = "S1"
    unified["always_S1_decision_answer"] = unified["S1_ans"]

    def _beta_source(row):
        return BETA_SOURCE_BY_SCENARIO.get(row["scenario_id"], "pooled4")

    unified["beta_shrinkage_decision"] = unified.apply(_beta_source, axis=1)

    def _beta_answer(row):
        src = row["beta_shrinkage_decision"]
        if src == "S1":
            return row.get("S1_ans")
        return row.get("pooled4_decision_answer")

    unified["beta_shrinkage_decision_answer"] = unified.apply(_beta_answer, axis=1)

    unified["C1d_decision"] = unified.get("c1_decision_c1d", "none")
    unified["C1a_t005_decision"] = unified.get("c1_decision_c1a_t005", "none")

    # Oracle decision fields.
    unified["oracle_best_source_action"] = unified["best_source_identity"]
    unified["oracle_best_source_correct"] = unified["oracle_ok"]

    # Majority pattern flags requested explicitly.
    unified["all_agree"] = unified["all_four_agree"].map(_safe_bool).astype(int)
    unified["split_3_1"] = unified["three_one_split"].map(_safe_bool).astype(int)
    unified["split_2_2"] = unified["two_two_split"].map(_safe_bool).astype(int)
    unified["all_different_flag"] = unified["all_different"].map(_safe_bool).astype(int)
    unified["no_majority"] = unified["no_majority_flag"].map(_safe_bool).astype(int)
    unified["dominant_source_in_majority"] = unified.apply(
        lambda r: int(
            str(r.get("dominant_source", "")).lower() in {"frontier", "l1", "s1", "tale"}
            and _safe_bool(r.get("frontier_in_majority"))
            and str(r.get("dominant_source", "")).lower() == "frontier"
            or _safe_bool(r.get("S1_in_majority"))
            and str(r.get("dominant_source", "")).lower() == "s1"
        ),
        axis=1,
    )

    # Question features.
    q = unified["question"].fillna("").astype(str)
    unified["q_length_chars"] = q.str.len()
    unified["q_length_words"] = q.apply(lambda s: len(s.split()))
    unified["q_number_count"] = q.apply(lambda s: len(re.findall(r"\d+(?:\.\d+)?", s)))
    unified["q_equation_symbol_count"] = q.apply(lambda s: sum(s.count(sym) for sym in ["=", "+", "-", "*", "/", "^", "%"]))
    unified["q_has_fraction"] = q.apply(lambda s: int(bool(re.search(r"\d+\s*/\s*\d+", s))))
    unified["q_has_decimal"] = q.apply(lambda s: int(bool(re.search(r"\d+\.\d+", s))))
    unified["q_has_percent"] = q.apply(lambda s: int("%" in s.lower() or "percent" in s.lower()))
    unified["math_topic_type"] = unified.apply(lambda r: _math_topic(r.get("question", ""), str(r.get("dataset", ""))), axis=1)

    # Numeric complexity bucket used for grouped mining.
    unified["q_numeric_complexity_bucket"] = pd.cut(
        unified["q_number_count"],
        bins=[-1, 1, 3, 6, 999],
        labels=["very_low", "low", "medium", "high"],
    ).astype(str)

    # Output/answer features from pooled decision answer + per-source answers.
    pooled_feats = unified["pooled4_decision_answer"].apply(_answer_features).apply(pd.Series)
    pooled_feats = pooled_feats.rename(
        columns={
            "answer_length": "decision_answer_length",
            "parse_success": "decision_parse_success",
            "final_answer_cleanliness": "decision_final_answer_cleanliness",
            "reasoning_length_bucket": "decision_reasoning_length_bucket",
        }
    )
    unified = pd.concat([unified, pooled_feats], axis=1)

    for src in ["frontier", "L1", "S1", "TALE"]:
        feats = unified[f"{src}_ans"].apply(_answer_features).apply(pd.Series)
        unified[f"{src}_answer_length"] = feats["answer_length"]
        unified[f"{src}_parse_success"] = feats["parse_success"]

    # Fail-opportunity markers.
    unified["oracle_correct_pooled4_wrong"] = (unified["oracle_ok"] & ~unified["pooled4_ok"]).astype(int)
    unified["oracle_correct_beta_wrong"] = (unified["oracle_ok"] & ~unified["beta_shrinkage_ok"]).astype(int)

    # Write outputs.
    out_csv = os.path.join(OUT_ROOT, "failure_workbench_unified_cases.csv")
    out_jsonl = os.path.join(OUT_ROOT, "failure_workbench_unified_cases.jsonl")
    unified.to_csv(out_csv, index=False)
    with open(out_jsonl, "w", encoding="utf-8") as f:
        for _, row in unified.iterrows():
            payload = {k: _to_jsonable(v) for k, v in row.to_dict().items()}
            f.write(json.dumps(payload, ensure_ascii=True) + "\n")

    # Source artifact inventory outputs.
    inv_rows = []
    for spec in SOURCE_INVENTORY_SPEC:
        doc_abs = os.path.join(REPO, spec["doc"])
        art_abs = os.path.join(REPO, spec["artifact"])
        inv_rows.append(
            {
                "source_group": spec["source_group"],
                "doc": spec["doc"],
                "doc_exists": os.path.exists(doc_abs),
                "artifact": spec["artifact"],
                "artifact_exists": os.path.exists(art_abs),
                "artifact_file_count": sum(len(files) for _, _, files in os.walk(art_abs)) if os.path.exists(art_abs) else 0,
            }
        )

    inv_csv = os.path.join(OUT_ROOT, "source_artifact_inventory.csv")
    inv_json = os.path.join(OUT_ROOT, "source_artifact_inventory.json")
    pd.DataFrame(inv_rows).to_csv(inv_csv, index=False)
    with open(inv_json, "w", encoding="utf-8") as f:
        json.dump({"created_utc": TIMESTAMP, "inventory": inv_rows}, f, indent=2)

    print(f"  Unified rows={len(unified)}, cols={len(unified.columns)}")
    print(f"  Scenario counts={unified['scenario_id'].value_counts().to_dict()}")
    print(f"  Written: {out_csv}")
    print(f"  Written: {out_jsonl}")
    print(f"  Written: {inv_csv}")
    print(f"  Written: {inv_json}")

    return unified


def define_failure_views(df: pd.DataFrame) -> pd.DataFrame:
    print("[step4] Defining failure views...")
    rows = []

    best_source_correct = df["best_source_identity"] != "none"

    for algo, ok_col in ALGORITHM_COLS.items():
        if ok_col not in df.columns:
            continue

        valid = df[df[ok_col].notna()].copy()
        ok = valid[ok_col].map(_safe_bool)
        wrong = valid[~ok]

        wrong_oracle_correct = wrong[wrong["oracle_ok"]]
        wrong_best_source_correct = wrong[wrong["best_source_identity"] != "none"]
        wrong_when_s1_correct = wrong[wrong["S1_ok"]]
        wrong_when_pooled4_correct = wrong[wrong["pooled4_ok"]]
        wrong_not_all_sources_wrong = wrong[wrong["all_sources_wrong"] == 0]
        all_sources_wrong_subset = wrong[wrong["all_sources_wrong"] == 1]

        regressions_vs_pooled4 = pd.DataFrame()
        recoveries_vs_pooled4 = pd.DataFrame()
        if algo != "pooled4" and "pooled4_ok" in valid.columns:
            regressions_vs_pooled4 = valid[(~ok) & (valid["pooled4_ok"])]
            recoveries_vs_pooled4 = valid[(ok) & (~valid["pooled4_ok"])]

        regressions_vs_beta = pd.DataFrame()
        recoveries_vs_beta = pd.DataFrame()
        if algo != "beta_shrinkage" and "beta_shrinkage_ok" in valid.columns:
            regressions_vs_beta = valid[(~ok) & (valid["beta_shrinkage_ok"])]
            recoveries_vs_beta = valid[(ok) & (~valid["beta_shrinkage_ok"])]

        # Required filenames
        wrong_oracle_correct.to_csv(os.path.join(OUT_ROOT, f"failure_view_{algo}_wrong_oracle_correct.csv"), index=False)
        regressions_vs_pooled4.to_csv(os.path.join(OUT_ROOT, f"failure_view_{algo}_regressions_vs_pooled4.csv"), index=False)
        recoveries_vs_pooled4.to_csv(os.path.join(OUT_ROOT, f"failure_view_{algo}_recoveries_vs_pooled4.csv"), index=False)
        regressions_vs_beta.to_csv(os.path.join(OUT_ROOT, f"failure_view_{algo}_regressions_vs_beta_shrinkage.csv"), index=False)
        recoveries_vs_beta.to_csv(os.path.join(OUT_ROOT, f"failure_view_{algo}_recoveries_vs_beta_shrinkage.csv"), index=False)

        # Extra useful views
        wrong.to_csv(os.path.join(OUT_ROOT, f"failure_view_{algo}_wrong_cases.csv"), index=False)
        wrong_best_source_correct.to_csv(os.path.join(OUT_ROOT, f"failure_view_{algo}_wrong_best_source_correct.csv"), index=False)
        wrong_when_s1_correct.to_csv(os.path.join(OUT_ROOT, f"failure_view_{algo}_wrong_when_S1_correct.csv"), index=False)
        wrong_when_pooled4_correct.to_csv(os.path.join(OUT_ROOT, f"failure_view_{algo}_wrong_when_pooled4_correct.csv"), index=False)
        wrong_not_all_sources_wrong.to_csv(os.path.join(OUT_ROOT, f"failure_view_{algo}_wrong_not_all_sources_wrong.csv"), index=False)
        all_sources_wrong_subset.to_csv(os.path.join(OUT_ROOT, f"failure_view_{algo}_all_sources_wrong.csv"), index=False)

        rows.append(
            {
                "algorithm": algo,
                "n_cases": int(len(valid)),
                "n_wrong": int(len(wrong)),
                "wrong_rate": float(len(wrong) / len(valid)) if len(valid) else 0.0,
                "n_wrong_oracle_correct": int(len(wrong_oracle_correct)),
                "n_wrong_best_source_correct": int(len(wrong_best_source_correct)),
                "n_regressions_vs_pooled4": int(len(regressions_vs_pooled4)),
                "n_recoveries_vs_pooled4": int(len(recoveries_vs_pooled4)),
                "n_regressions_vs_beta_shrinkage": int(len(regressions_vs_beta)),
                "n_recoveries_vs_beta_shrinkage": int(len(recoveries_vs_beta)),
                "n_wrong_when_S1_correct": int(len(wrong_when_s1_correct)),
                "n_wrong_when_pooled4_correct": int(len(wrong_when_pooled4_correct)),
                "n_wrong_not_all_sources_wrong": int(len(wrong_not_all_sources_wrong)),
                "n_all_sources_wrong": int(len(all_sources_wrong_subset)),
            }
        )

        print(
            f"  {algo}: wrong={len(wrong)}/{len(valid)} "
            f"oracle-recoverable={len(wrong_oracle_correct)} "
            f"reg_vs_p4={len(regressions_vs_pooled4)} rec_vs_p4={len(recoveries_vs_pooled4)}"
        )

    out = pd.DataFrame(rows).sort_values("wrong_rate", ascending=False)
    out_path = os.path.join(OUT_ROOT, "failure_views_summary.csv")
    out.to_csv(out_path, index=False)
    print(f"  Written: {out_path}")
    return out


def mine_failure_patterns(df: pd.DataFrame) -> pd.DataFrame:
    print("[step5] Mining recurring failure patterns...")

    group_keys = [
        "provider",
        "dataset",
        "official_or_auxiliary",
        "answer_pattern_bucket",
        "majority_size",
        "best_source_identity",
        "only_source_correct_identity",
        "S1_isolated",
        "frontier_in_majority",
        "external_majority_excludes_S1",
        "L1_TALE_agree",
        "no_majority_flag",
        "all_sources_wrong",
        "q_numeric_complexity_bucket",
        "decision_final_answer_cleanliness",
        "decision_parse_success",
    ]
    group_keys = [k for k in group_keys if k in df.columns]

    patterns = []

    def _acc(sdf: pd.DataFrame, col: str) -> float:
        if col not in sdf.columns:
            return float("nan")
        vals = sdf[col].dropna().map(_safe_bool)
        if len(vals) == 0:
            return float("nan")
        return float(vals.mean())

    for keys, sdf in df.groupby(group_keys, dropna=False):
        if len(sdf) < 4:
            continue

        if not isinstance(keys, tuple):
            keys = (keys,)
        key_map = dict(zip(group_keys, keys))

        n = len(sdf)
        oracle_correct_count = int(sdf["oracle_ok"].sum())

        src_correct_counts = {
            "frontier": int(sdf["frontier_ok"].sum()),
            "L1": int(sdf["L1_ok"].sum()),
            "S1": int(sdf["S1_ok"].sum()),
            "TALE": int(sdf["TALE_ok"].sum()),
        }
        best_src = max(src_correct_counts, key=src_correct_counts.get)

        pooled4_acc = _acc(sdf, "pooled4_ok")
        beta_acc = _acc(sdf, "beta_shrinkage_ok")
        c1d_acc = _acc(sdf, "C1d_ok")
        learned_acc = _acc(sdf, "learned_router_ok")

        recovery_opportunity = int(((sdf["oracle_ok"]) & (~sdf["beta_shrinkage_ok"])).sum())
        regression_risk = int(((~sdf["C1d_ok"]) & (sdf["pooled4_ok"])).sum()) if "C1d_ok" in sdf.columns else 0

        scenario_counts = sdf["scenario_id"].value_counts()
        top_share = float(scenario_counts.iloc[0] / n)

        if sdf["official_or_auxiliary"].nunique() == 1:
            scope = "official-only" if sdf["official_or_auxiliary"].iloc[0] == "official" else "auxiliary-only"
        else:
            scope = "cross-scenario"

        # Current algorithm wrong rate defaults to beta-shrinkage wrong-rate.
        cur_wrong_rate = float((~sdf["beta_shrinkage_ok"]).mean())

        rank_score = (
            recovery_opportunity * (1.0 + cur_wrong_rate) * (1.0 + (1.0 - top_share)) * (1.0 - min(regression_risk / max(n, 1), 0.9))
        )

        row = {
            **key_map,
            "n_cases": int(n),
            "oracle_correct_count": oracle_correct_count,
            "oracle_correct_rate": float(oracle_correct_count / n),
            "current_algorithm_wrong_count": int((~sdf["beta_shrinkage_ok"]).sum()),
            "current_algorithm_wrong_rate": cur_wrong_rate,
            "best_available_source": best_src,
            "source_correct_most_often": best_src,
            "pooled4_accuracy": pooled4_acc,
            "beta_shrinkage_accuracy": beta_acc,
            "C1d_accuracy": c1d_acc,
            "learned_router_accuracy": learned_acc,
            "recovery_opportunity_count": recovery_opportunity,
            "regression_risk_count": regression_risk,
            "scenario_concentration_top_share": top_share,
            "scenario_count": int(sdf["scenario_id"].nunique()),
            "pattern_scope": scope,
            "rank_score": rank_score,
        }
        patterns.append(row)

    pat = pd.DataFrame(patterns)
    if len(pat):
        pat = pat.sort_values(
            ["recovery_opportunity_count", "current_algorithm_wrong_rate", "scenario_count", "rank_score", "n_cases"],
            ascending=[False, False, False, False, False],
        )

    out_csv = os.path.join(OUT_ROOT, "mined_failure_patterns.csv")
    pat.to_csv(out_csv, index=False)

    md = [
        "# Mined Failure Patterns (Ranked)\n\n",
        f"Generated: {TIMESTAMP}\n\n",
        "Ranking priority: high oracle-correct opportunity, high current error rate, repeated across scenarios, low regression risk, enough support.\n\n",
        f"Total pattern groups kept (n>=4): {len(pat)}\n\n",
    ]

    top = pat.head(40)
    for i, (_, r) in enumerate(top.iterrows(), start=1):
        desc_bits = [f"{k}={r[k]}" for k in group_keys if k in r and pd.notna(r[k])]
        md.append(f"## {i}. {' | '.join(desc_bits)}\n")
        md.append(
            f"- support: {int(r['n_cases'])}\n"
            f"- oracle-correct opportunity: {int(r['recovery_opportunity_count'])}\n"
            f"- current wrong rate (beta-shrinkage): {r['current_algorithm_wrong_rate']:.2%}\n"
            f"- pooled4={r['pooled4_accuracy']:.2%} beta={r['beta_shrinkage_accuracy']:.2%} C1d={r['C1d_accuracy']:.2%}\n"
            f"- best source: {r['best_available_source']}\n"
            f"- scenario_count={int(r['scenario_count'])}, scope={r['pattern_scope']}, top_share={r['scenario_concentration_top_share']:.2f}\n"
            f"- regression_risk_count={int(r['regression_risk_count'])}\n\n"
        )

    out_md = os.path.join(OUT_ROOT, "mined_failure_patterns_ranked.md")
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("".join(md))

    print(f"  Written: {out_csv}")
    print(f"  Written: {out_md}")
    return pat


CLUSTER_DEFS = {
    "A_dominant_source_outvoted": {
        "label": "dominant_source_outvoted",
        "description": "dominant source correct but pooled/majority selects another answer",
        "likely_failure_mechanism": "majority ignores source reliability asymmetry",
        "possible_fix": "strengthen C1d dominant-source override with conservative gate",
        "expected_benefit": "recover S1-isolated wins in dominant-source regimes",
        "regression_risk": "low-medium (false dominance in near-peer)",
        "zero_extra_call_fix_possible": True,
        "needs_generation_or_budget": False,
    },
    "B_near_peer_false_dominance": {
        "label": "near_peer_false_dominance",
        "description": "selector trusts a dominant source in near-peer conditions where pooled vote was right",
        "likely_failure_mechanism": "dominance trigger too aggressive under small source spread",
        "possible_fix": "near-peer gate: block dominance when spread < threshold",
        "expected_benefit": "cuts dominant-source false positives",
        "regression_risk": "medium",
        "zero_extra_call_fix_possible": True,
        "needs_generation_or_budget": False,
    },
    "C_no_majority_bad_fallback": {
        "label": "no_majority_bad_fallback",
        "description": "no majority, fallback answer wrong while another source was correct",
        "likely_failure_mechanism": "fallback defaults to frontier without local evidence",
        "possible_fix": "calibrated no-majority fallback to dominant/best source",
        "expected_benefit": "recover no-majority misses",
        "regression_risk": "low-medium",
        "zero_extra_call_fix_possible": True,
        "needs_generation_or_budget": False,
    },
    "D_external_majority_wrong": {
        "label": "external_majority_wrong",
        "description": "external sources agree but are wrong",
        "likely_failure_mechanism": "prompt-family correlated error",
        "possible_fix": "external-majority skepticism when frontier disagrees",
        "expected_benefit": "recover correlated external-majority failures",
        "regression_risk": "medium-high",
        "zero_extra_call_fix_possible": True,
        "needs_generation_or_budget": False,
    },
    "E_frontier_fallback_wrong": {
        "label": "frontier_fallback_wrong",
        "description": "frontier fallback selected and wrong while some external source was correct",
        "likely_failure_mechanism": "provider/dataset mismatch in fallback default",
        "possible_fix": "provider/dataset-calibrated fallback hierarchy",
        "expected_benefit": "recover fallback errors in non-frontier-dominant slices",
        "regression_risk": "medium",
        "zero_extra_call_fix_possible": True,
        "needs_generation_or_budget": False,
    },
    "F_S1_overtrusted": {
        "label": "S1_overtrusted",
        "description": "S1 selected and wrong while pooled4/L1/frontier could be correct",
        "likely_failure_mechanism": "S1 trust transferred into near-peer regimes",
        "possible_fix": "S1-trust gate conditioned on reliability spread",
        "expected_benefit": "reduce S1-overtrust regressions",
        "regression_risk": "low",
        "zero_extra_call_fix_possible": True,
        "needs_generation_or_budget": False,
    },
    "G_S1_undertrusted": {
        "label": "S1_undertrusted",
        "description": "S1 correct but selector chooses another wrong answer",
        "likely_failure_mechanism": "majority or fallback overrules dominant S1",
        "possible_fix": "dominant-source inclusion majority (C1d)",
        "expected_benefit": "recover S1 isolated wins",
        "regression_risk": "low",
        "zero_extra_call_fix_possible": True,
        "needs_generation_or_budget": False,
    },
    "H_L1_or_frontier_best_on_Cohere_MATH": {
        "label": "L1_or_frontier_best_on_Cohere_MATH",
        "description": "Cohere MATH slice where L1/frontier outperforms S1/TALE",
        "likely_failure_mechanism": "provider-specific mismatch for budget-forcing prompts",
        "possible_fix": "provider/dataset calibration hierarchy",
        "expected_benefit": "prevent S1 bias in Cohere-MATH-like slices",
        "regression_risk": "medium",
        "zero_extra_call_fix_possible": True,
        "needs_generation_or_budget": False,
    },
    "I_MATH_all_sources_wrong": {
        "label": "MATH_all_sources_wrong",
        "description": "all sources wrong; selector cannot recover",
        "likely_failure_mechanism": "generation ceiling / insufficient reasoning budget",
        "possible_fix": "hardness detector + budget escalation",
        "expected_benefit": "requires generation/budget changes, not selector tweaks",
        "regression_risk": "n/a (selector-irrecovable)",
        "zero_extra_call_fix_possible": False,
        "needs_generation_or_budget": True,
    },
    "J_agreement_fragility": {
        "label": "agreement_fragility",
        "description": "agreement-only fails under no-majority or wrong-majority conditions",
        "likely_failure_mechanism": "agreement logic lacks robust fallback",
        "possible_fix": "agreement + calibrated C1d fallback",
        "expected_benefit": "recover brittle agreement failures",
        "regression_risk": "low-medium",
        "zero_extra_call_fix_possible": True,
        "needs_generation_or_budget": False,
    },
    "K_weighted_vote_amplifies_bad_sources": {
        "label": "weighted_vote_amplifies_bad_sources",
        "description": "weighted/log-odds voting regresses versus simple pooling",
        "likely_failure_mechanism": "small reliability gaps amplified too strongly",
        "possible_fix": "shrinked/clipped weights; avoid raw log-odds in near-peer",
        "expected_benefit": "remove avoidable weighted-vote regressions",
        "regression_risk": "low",
        "zero_extra_call_fix_possible": True,
        "needs_generation_or_budget": False,
    },
}


def assign_clusters(df: pd.DataFrame) -> Dict[str, List[int]]:
    clusters = {k: [] for k in CLUSTER_DEFS}

    for idx, row in df.iterrows():
        frontier_ok = _safe_bool(row.get("frontier_ok"))
        l1_ok = _safe_bool(row.get("L1_ok"))
        s1_ok = _safe_bool(row.get("S1_ok"))
        tale_ok = _safe_bool(row.get("TALE_ok"))
        pooled4_ok = _safe_bool(row.get("pooled4_ok"))
        agreement_ok = _safe_bool(row.get("agreement_only_ok"))
        always_s1_ok = _safe_bool(row.get("always_S1_ok"))
        c1d_ok = _safe_bool(row.get("C1d_ok"))
        oracle_ok = _safe_bool(row.get("oracle_ok"))

        no_majority = _safe_bool(row.get("no_majority_flag"))
        ext_maj_exists = _safe_bool(row.get("external_majority_exists"))
        ext_maj_excl_frontier = _safe_bool(row.get("external_majority_excludes_frontier"))
        all_wrong = int(row.get("all_sources_wrong", 0)) == 1

        provider = str(row.get("provider", ""))
        dataset = str(row.get("dataset", ""))
        c1c_logodds_ok = row.get("c1_ok_c1c_logodds")
        c1c_logodds_ok = _safe_bool(c1c_logodds_ok) if not pd.isna(c1c_logodds_ok) else None

        # A: dominant source outvoted
        if c1d_ok and (not pooled4_ok) and oracle_ok:
            clusters["A_dominant_source_outvoted"].append(idx)

        # B: near-peer false dominance
        if (not c1d_ok) and pooled4_ok:
            clusters["B_near_peer_false_dominance"].append(idx)

        # C: no-majority bad fallback
        if no_majority and (not pooled4_ok) and oracle_ok:
            clusters["C_no_majority_bad_fallback"].append(idx)

        # D: external majority wrong
        if ext_maj_exists and ext_maj_excl_frontier and frontier_ok and (not pooled4_ok):
            clusters["D_external_majority_wrong"].append(idx)

        # E: frontier fallback wrong while some external source correct
        if (not pooled4_ok) and (not frontier_ok) and (l1_ok or s1_ok or tale_ok):
            clusters["E_frontier_fallback_wrong"].append(idx)

        # F: S1 overtrusted
        if (not always_s1_ok) and (pooled4_ok or frontier_ok):
            clusters["F_S1_overtrusted"].append(idx)

        # G: S1 undertrusted
        if s1_ok and (not pooled4_ok):
            clusters["G_S1_undertrusted"].append(idx)

        # H: Cohere MATH where L1/frontier beat S1
        if provider == "cohere" and "math" in dataset and (l1_ok or frontier_ok) and (not s1_ok):
            clusters["H_L1_or_frontier_best_on_Cohere_MATH"].append(idx)

        # I: all sources wrong
        if all_wrong:
            clusters["I_MATH_all_sources_wrong"].append(idx)

        # J: agreement fragility
        if (not agreement_ok) and oracle_ok:
            clusters["J_agreement_fragility"].append(idx)

        # K: weighted vote amplifies bad sources
        if c1c_logodds_ok is False and pooled4_ok:
            clusters["K_weighted_vote_amplifies_bad_sources"].append(idx)

    return clusters


def produce_failure_clusters(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, List[int]]]:
    print("[step6] Producing failure clusters...")
    clusters = assign_clusters(df)

    rows = []
    for cid, idxs in clusters.items():
        meta = CLUSTER_DEFS[cid]
        cdf = df.loc[idxs] if idxs else pd.DataFrame(columns=df.columns)
        scenario_counts = cdf["scenario_id"].value_counts().to_dict() if len(cdf) else {}

        rows.append(
            {
                "cluster_id": cid,
                "cluster_label": meta["label"],
                "definition": meta["description"],
                "n_cases": int(len(idxs)),
                "count_by_scenario": json.dumps(scenario_counts),
                "likely_failure_mechanism": meta["likely_failure_mechanism"],
                "possible_fix": meta["possible_fix"],
                "expected_benefit": meta["expected_benefit"],
                "regression_risk": meta["regression_risk"],
                "zero_extra_call_fix_possible": bool(meta["zero_extra_call_fix_possible"]),
                "needs_generation_or_budget": bool(meta["needs_generation_or_budget"]),
            }
        )

        # Casebook with 5-10 representative examples.
        casebook_path = os.path.join(CASEBOOK_DIR, f"{meta['label']}_casebook.md")
        with open(casebook_path, "w", encoding="utf-8") as f:
            f.write(f"# Failure Cluster Casebook: {meta['label']}\n\n")
            f.write(f"**Definition:** {meta['description']}\n\n")
            f.write(f"**Likely mechanism:** {meta['likely_failure_mechanism']}\n\n")
            f.write(f"**Possible fix:** {meta['possible_fix']}\n\n")
            f.write(f"**Expected benefit:** {meta['expected_benefit']}\n\n")
            f.write(f"**Regression risk:** {meta['regression_risk']}\n\n")
            f.write(f"**Zero-extra-call possible:** {meta['zero_extra_call_fix_possible']}\n\n")
            f.write(f"**Needs generation/budget change:** {meta['needs_generation_or_budget']}\n\n")
            f.write(f"**Count by scenario:** {json.dumps(scenario_counts)}\n\n")
            f.write("## Representative Cases\n\n")

            reps = cdf.head(10)
            for i, (_, r) in enumerate(reps.iterrows(), start=1):
                q = str(r.get("question", ""))
                if len(q) > 360:
                    q = q[:360] + "..."
                f.write(f"### {i}. {r.get('scenario_id')} :: {r.get('example_id')}\n")
                f.write(f"- question: {q}\n")
                f.write(f"- gold: {r.get('gold')}\n")
                f.write(f"- frontier: {r.get('frontier_ans')} (ok={r.get('frontier_ok')})\n")
                f.write(f"- L1: {r.get('L1_ans')} (ok={r.get('L1_ok')})\n")
                f.write(f"- S1: {r.get('S1_ans')} (ok={r.get('S1_ok')})\n")
                f.write(f"- TALE: {r.get('TALE_ans')} (ok={r.get('TALE_ok')})\n")
                f.write(f"- pooled4_ok={r.get('pooled4_ok')} beta_ok={r.get('beta_shrinkage_ok')} C1d_ok={r.get('C1d_ok')}\n")
                f.write(f"- learned_router_ok={r.get('learned_router_ok')}\n")
                f.write(f"- answer_pattern={r.get('answer_pattern_bucket')}\n\n")

    summary = pd.DataFrame(rows).sort_values("n_cases", ascending=False)
    out_csv = os.path.join(OUT_ROOT, "failure_clusters_summary.csv")
    out_md = os.path.join(OUT_ROOT, "failure_clusters_detailed.md")
    summary.to_csv(out_csv, index=False)

    with open(out_md, "w", encoding="utf-8") as f:
        f.write("# Detailed Failure Clusters\n\n")
        f.write(f"Generated: {TIMESTAMP}\n\n")
        for _, r in summary.iterrows():
            f.write(f"## {r['cluster_label']} (n={int(r['n_cases'])})\n\n")
            f.write(f"- definition: {r['definition']}\n")
            f.write(f"- likely mechanism: {r['likely_failure_mechanism']}\n")
            f.write(f"- possible fix: {r['possible_fix']}\n")
            f.write(f"- expected benefit: {r['expected_benefit']}\n")
            f.write(f"- regression risk: {r['regression_risk']}\n")
            f.write(f"- zero-extra-call possible: {r['zero_extra_call_fix_possible']}\n")
            f.write(f"- needs generation/budget change: {r['needs_generation_or_budget']}\n")
            f.write(f"- count by scenario: {r['count_by_scenario']}\n\n")

    print(f"  Written: {out_csv}")
    print(f"  Written: {out_md}")
    return summary, clusters


def write_mechanism_diagnoses(df: pd.DataFrame, cluster_summary: pd.DataFrame) -> str:
    print("[step7] Writing mechanism diagnoses...")
    out = os.path.join(OUT_ROOT, "failure_mechanism_diagnoses.md")

    scenario_stats = (
        df.groupby("scenario_id")[["frontier_ok", "L1_ok", "S1_ok", "TALE_ok", "pooled4_ok", "beta_shrinkage_ok", "all_sources_wrong", "no_majority_flag"]]
        .mean()
        .reset_index()
    )

    with open(out, "w", encoding="utf-8") as f:
        f.write("# Failure Mechanism Diagnoses\n\n")
        f.write(f"Generated: {TIMESTAMP}\n\n")
        f.write("## Scenario Summary\n\n")
        f.write("| scenario | frontier | L1 | S1 | TALE | pooled4 | beta | all_wrong | no_majority |\n")
        f.write("|---|---:|---:|---:|---:|---:|---:|---:|---:|\n")
        for _, r in scenario_stats.iterrows():
            f.write(
                f"| {r['scenario_id']} | {r['frontier_ok']:.2%} | {r['L1_ok']:.2%} | {r['S1_ok']:.2%} | "
                f"{r['TALE_ok']:.2%} | {r['pooled4_ok']:.2%} | {r['beta_shrinkage_ok']:.2%} | "
                f"{r['all_sources_wrong']:.2%} | {r['no_majority_flag']:.2%} |\n"
            )

        f.write("\n## Major Pattern Diagnoses\n\n")
        f.write("### 1) S1 Undertrusted in Dominant Regimes\n")
        f.write("When S1 is isolated-correct (especially Mistral scenarios), pooled-majority can still vote against it. This is a reliability-mismatch error: answer support count is overweighted relative to source competence.\n\n")

        f.write("### 2) S1 Overtrusted in Near-Peer Regimes\n")
        f.write("In near-peer slices, dominant-source assumptions are weak. Forcing S1 in those cases causes avoidable regressions, especially on Cohere-like conditions where S1 is not globally strongest.\n\n")

        f.write("### 3) No-Majority Fallback Fragility\n")
        f.write("When no strict majority exists, a fixed fallback (frontier-only) can be wrong while another source is right. This points to local-evidence fallback policy gaps, not generation failure.\n\n")

        f.write("### 4) External Majority Correlated Error\n")
        f.write("L1/S1/TALE can form correlated wrong majorities; this appears when prompt-family bias aligns. Pure majority rules then over-trust agreement quantity.\n\n")

        f.write("### 5) MATH All-Sources-Wrong Ceiling\n")
        f.write("High all-sources-wrong rates in MATH slices indicate a generation/budget bottleneck. Selector refinements cannot recover these examples; only stronger generation or more budget can.\n\n")

        f.write("### 6) Weighted-Vote Instability\n")
        f.write("Raw/log-odds weighting can amplify small reliability deltas into large decision swings, causing regressions in near-peer slices. Shrinked or clipped weights are safer.\n")

    print(f"  Written: {out}")
    return out


CANDIDATE_FIXES = [
    {
        "fix_id": "FIX-01",
        "target_failure_cluster": "dominant_source_outvoted, S1_undertrusted",
        "zero_extra_call": True,
        "description": "Strengthen C1d dominance rule with conservative activation gates.",
        "required_features": "dominant_source, S1_isolated, provider/dataset regime spread",
        "implementation_complexity": "low",
        "expected_recoveries": "medium-high",
        "expected_regressions": "low",
        "scenarios_likely_helped": "mistral_gsm8k, mistral_math500",
        "scenarios_at_risk": "cohere_gsm8k near-peer",
        "evaluation_protocol": "paired replay vs pooled4 and beta-shrinkage across all scenarios",
        "status": "implement now",
    },
    {
        "fix_id": "FIX-02",
        "target_failure_cluster": "no_majority_bad_fallback",
        "zero_extra_call": True,
        "description": "Narrow no-majority fallback to calibrated high-confidence dominant-source cases.",
        "required_features": "no_majority_flag, dominance margin, source reliability",
        "implementation_complexity": "low",
        "expected_recoveries": "medium",
        "expected_regressions": "low",
        "scenarios_likely_helped": "mistral_gsm8k",
        "scenarios_at_risk": "cohere near-peer",
        "evaluation_protocol": "isolate no-majority subset, compare fallback variants",
        "status": "implement now",
    },
    {
        "fix_id": "FIX-03",
        "target_failure_cluster": "S1_overtrusted, near_peer_false_dominance",
        "zero_extra_call": True,
        "description": "S1-trust gate to block S1 override in Cohere-like near-peer regimes.",
        "required_features": "provider, dataset, source spread, regime label",
        "implementation_complexity": "low",
        "expected_recoveries": "medium",
        "expected_regressions": "low",
        "scenarios_likely_helped": "cohere_gsm8k, cohere_math500_aux",
        "scenarios_at_risk": "mistral dominant slices",
        "evaluation_protocol": "threshold sweep with regression audit on Mistral",
        "status": "implement now",
    },
    {
        "fix_id": "FIX-04",
        "target_failure_cluster": "external_majority_wrong",
        "zero_extra_call": True,
        "description": "External-majority skepticism when L1+TALE family historically correlates on errors.",
        "required_features": "L1_TALE_agree, frontier disagreement markers",
        "implementation_complexity": "medium",
        "expected_recoveries": "low-medium",
        "expected_regressions": "medium",
        "scenarios_likely_helped": "cohere_math500 official candidate",
        "scenarios_at_risk": "global if frontier is weak",
        "evaluation_protocol": "wait for official Cohere MATH scenario then replay",
        "status": "test after Cohere official Scenario 4",
    },
    {
        "fix_id": "FIX-05",
        "target_failure_cluster": "cross-pattern reliability mismatch",
        "zero_extra_call": True,
        "description": "Pattern-specific RG-EB-Action table keyed by regime/pattern/provider/dataset.",
        "required_features": "answer_pattern_bucket, regime features, provider, dataset",
        "implementation_complexity": "medium",
        "expected_recoveries": "medium-high",
        "expected_regressions": "medium",
        "scenarios_likely_helped": "cross-scenario",
        "scenarios_at_risk": "low-support cells",
        "evaluation_protocol": "cross-scenario CV and holdout transfer",
        "status": "test after Cerebras",
    },
    {
        "fix_id": "FIX-06",
        "target_failure_cluster": "MATH_all_sources_wrong",
        "zero_extra_call": False,
        "description": "Hardness detector to escalate budget on high all-sources-wrong risk cases.",
        "required_features": "question complexity and topic features",
        "implementation_complexity": "high",
        "expected_recoveries": "selector-only none; generation-level potential",
        "expected_regressions": "budget waste risk",
        "scenarios_likely_helped": "math500 scenarios",
        "scenarios_at_risk": "none selector-side",
        "evaluation_protocol": "predictive precision/recall on held-out MATH cases",
        "status": "needs larger training data",
    },
    {
        "fix_id": "FIX-07",
        "target_failure_cluster": "multi-pattern routing errors",
        "zero_extra_call": True,
        "description": "Learned router v2 with Mistral train1000 + auxiliary routing-decisive cases.",
        "required_features": "full unified feature table and larger routing-decisive pool",
        "implementation_complexity": "high",
        "expected_recoveries": "medium-high",
        "expected_regressions": "overfit risk",
        "scenarios_likely_helped": "all scenarios",
        "scenarios_at_risk": "transfer to unseen provider/dataset",
        "evaluation_protocol": "train/holdout by scenario with paired regression audit",
        "status": "test after Mistral train1000",
    },
    {
        "fix_id": "FIX-08",
        "target_failure_cluster": "provider-dataset mismatch",
        "zero_extra_call": True,
        "description": "Provider/dataset calibration hierarchy for default fallback policies.",
        "required_features": "provider, dataset, regime",
        "implementation_complexity": "low",
        "expected_recoveries": "medium",
        "expected_regressions": "low-medium",
        "scenarios_likely_helped": "cohere_math500_aux, cohere_gsm8k",
        "scenarios_at_risk": "mistral if over-applied",
        "evaluation_protocol": "scenario-conditional replay against uniform policy",
        "status": "implement now",
    },
    {
        "fix_id": "FIX-09",
        "target_failure_cluster": "evaluation focus drift",
        "zero_extra_call": True,
        "description": "Oracle-gap targeting: evaluate/train on routing-decisive cases only.",
        "required_features": "oracle flag + source-correctness counts",
        "implementation_complexity": "low",
        "expected_recoveries": "meta-improvement in fix quality",
        "expected_regressions": "none",
        "scenarios_likely_helped": "all",
        "scenarios_at_risk": "none",
        "evaluation_protocol": "all reports include routing-decisive slice metrics",
        "status": "implement now",
    },
]

# Backward-compatible aliases expected by tests/importers.
for _fix in CANDIDATE_FIXES:
    _fix.setdefault("target_cluster", _fix.get("target_failure_cluster", ""))
    _fix.setdefault("scenarios_helped", _fix.get("scenarios_likely_helped", ""))


def write_candidate_fixes() -> pd.DataFrame:
    print("[step8] Writing candidate fixes...")
    df = pd.DataFrame(CANDIDATE_FIXES)
    out_csv = os.path.join(OUT_ROOT, "candidate_fixes_from_failure_patterns.csv")
    out_md = os.path.join(OUT_ROOT, "candidate_fixes_from_failure_patterns.md")
    df.to_csv(out_csv, index=False)

    with open(out_md, "w", encoding="utf-8") as f:
        f.write("# Candidate Fixes from Failure Patterns\n\n")
        f.write(f"Generated: {TIMESTAMP}\n\n")
        for _, r in df.iterrows():
            f.write(f"## {r['fix_id']}\n")
            f.write(f"- target failure cluster: {r['target_failure_cluster']}\n")
            f.write(f"- zero-extra-call: {r['zero_extra_call']}\n")
            f.write(f"- description: {r['description']}\n")
            f.write(f"- required features: {r['required_features']}\n")
            f.write(f"- implementation complexity: {r['implementation_complexity']}\n")
            f.write(f"- expected recoveries: {r['expected_recoveries']}\n")
            f.write(f"- expected regressions: {r['expected_regressions']}\n")
            f.write(f"- scenarios likely helped: {r['scenarios_likely_helped']}\n")
            f.write(f"- scenarios at risk: {r['scenarios_at_risk']}\n")
            f.write(f"- evaluation protocol: {r['evaluation_protocol']}\n")
            f.write(f"- status: {r['status']}\n\n")

    print(f"  Written: {out_csv}")
    print(f"  Written: {out_md}")
    return df


IMPL_QUEUE = [
    {
        "priority": 1,
        "fix_id": "FIX-01",
        "estimated_benefit": "high",
        "regression_risk": "low-medium",
        "zero_extra_call_compatible": True,
        "implementation_difficulty": "low",
        "evidence_strength": "high",
        "enough_completed_data_now": True,
        "pending_runs_needed": "no",
        "loop": "implement strengthened C1d; compare vs beta-shrinkage and pooled4; inspect regressions; tune; repeat",
    },
    {
        "priority": 2,
        "fix_id": "FIX-03",
        "estimated_benefit": "high",
        "regression_risk": "low",
        "zero_extra_call_compatible": True,
        "implementation_difficulty": "low",
        "evidence_strength": "high",
        "enough_completed_data_now": True,
        "pending_runs_needed": "no",
        "loop": "add S1-trust gate for near-peer; replay all scenarios; verify no Mistral harm; tune threshold",
    },
    {
        "priority": 3,
        "fix_id": "FIX-02",
        "estimated_benefit": "medium",
        "regression_risk": "low-medium",
        "zero_extra_call_compatible": True,
        "implementation_difficulty": "low",
        "evidence_strength": "medium-high",
        "enough_completed_data_now": True,
        "pending_runs_needed": "no",
        "loop": "narrow no-majority fallback to calibrated cases; compare vs baseline fallback; inspect no-majority regressions",
    },
    {
        "priority": 4,
        "fix_id": "FIX-08",
        "estimated_benefit": "medium",
        "regression_risk": "medium",
        "zero_extra_call_compatible": True,
        "implementation_difficulty": "low",
        "evidence_strength": "medium",
        "enough_completed_data_now": True,
        "pending_runs_needed": "no",
        "loop": "apply provider/dataset hierarchy; replay; verify gains and guard Mistral",
    },
    {
        "priority": 5,
        "fix_id": "FIX-04",
        "estimated_benefit": "medium",
        "regression_risk": "medium-high",
        "zero_extra_call_compatible": True,
        "implementation_difficulty": "medium",
        "evidence_strength": "medium",
        "enough_completed_data_now": False,
        "pending_runs_needed": "Cohere official Scenario 4",
        "loop": "after official Cohere MATH completion, calibrate external-majority skepticism and rerun regression audit",
    },
    {
        "priority": 6,
        "fix_id": "FIX-05",
        "estimated_benefit": "high",
        "regression_risk": "medium",
        "zero_extra_call_compatible": True,
        "implementation_difficulty": "medium",
        "evidence_strength": "medium",
        "enough_completed_data_now": False,
        "pending_runs_needed": "Cerebras scenario completion",
        "loop": "build RG-EB-Action table with richer cross-provider support after Cerebras",
    },
    {
        "priority": 7,
        "fix_id": "FIX-07",
        "estimated_benefit": "high",
        "regression_risk": "high",
        "zero_extra_call_compatible": True,
        "implementation_difficulty": "high",
        "evidence_strength": "medium",
        "enough_completed_data_now": False,
        "pending_runs_needed": "Mistral train1000 completion",
        "loop": "train learned router v2 on expanded routing-decisive data, then cross-scenario holdout test",
    },
    {
        "priority": 8,
        "fix_id": "FIX-06",
        "estimated_benefit": "generation-level",
        "regression_risk": "budget risk",
        "zero_extra_call_compatible": False,
        "implementation_difficulty": "high",
        "evidence_strength": "medium",
        "enough_completed_data_now": False,
        "pending_runs_needed": "larger labeled MATH set",
        "loop": "train hardness detector and evaluate budget-escalation policy",
    },
]


def write_implementation_queue() -> pd.DataFrame:
    print("[step9] Writing implementation queue...")
    df = pd.DataFrame(IMPL_QUEUE)
    out_csv = os.path.join(OUT_ROOT, "next_failure_driven_implementation_queue.csv")
    out_md = os.path.join(OUT_ROOT, "next_failure_driven_implementation_queue.md")
    df.to_csv(out_csv, index=False)

    with open(out_md, "w", encoding="utf-8") as f:
        f.write("# Next Failure-Driven Implementation Queue\n\n")
        f.write(f"Generated: {TIMESTAMP}\n\n")
        f.write("## Concrete Repeat Loop\n\n")
        f.write("1. implement/test top fix\n")
        f.write("2. compare against beta-shrinkage and C1d baselines\n")
        f.write("3. inspect regression case files and casebooks\n")
        f.write("4. revise thresholds or gates\n")
        f.write("5. repeat until net-positive across scenarios\n\n")

        f.write("## Priority Table\n\n")
        for _, r in df.sort_values("priority").iterrows():
            f.write(f"### P{int(r['priority'])} - {r['fix_id']}\n")
            f.write(f"- estimated benefit: {r['estimated_benefit']}\n")
            f.write(f"- regression risk: {r['regression_risk']}\n")
            f.write(f"- zero-extra-call compatible: {r['zero_extra_call_compatible']}\n")
            f.write(f"- implementation difficulty: {r['implementation_difficulty']}\n")
            f.write(f"- evidence strength: {r['evidence_strength']}\n")
            f.write(f"- enough completed data now: {r['enough_completed_data_now']}\n")
            f.write(f"- pending runs needed: {r['pending_runs_needed']}\n")
            f.write(f"- loop: {r['loop']}\n\n")

    print(f"  Written: {out_csv}")
    print(f"  Written: {out_md}")
    return df


def write_human_report(
    unified: pd.DataFrame,
    views: pd.DataFrame,
    patterns: pd.DataFrame,
    clusters: pd.DataFrame,
    fixes: pd.DataFrame,
    queue_df: pd.DataFrame,
) -> str:
    print("[step11] Writing human-readable report...")

    n_total = len(unified)
    scenario_counts = unified["scenario_id"].value_counts().to_dict()
    top_clusters = clusters.sort_values("n_cases", ascending=False).head(5)
    selector_fixable = clusters[clusters["needs_generation_or_budget"] == False]["n_cases"].sum()
    generation_bound = clusters[clusters["needs_generation_or_budget"] == True]["n_cases"].sum()

    def _table_md(df_in: pd.DataFrame, max_rows: int = 50) -> str:
        if df_in is None or len(df_in) == 0:
            return "_no rows_"
        d = df_in.head(max_rows).copy()
        cols = list(d.columns)
        lines = []
        lines.append("| " + " | ".join(str(c) for c in cols) + " |")
        lines.append("|" + "|".join(["---"] * len(cols)) + "|")
        for _, row in d.iterrows():
            vals = []
            for c in cols:
                v = row[c]
                if isinstance(v, float):
                    s = f"{v:.6g}"
                else:
                    s = str(v)
                s = s.replace("\n", " ").replace("|", "/")
                vals.append(s)
            lines.append("| " + " | ".join(vals) + " |")
        return "\n".join(lines)

    with open(DOC_REPORT, "w", encoding="utf-8") as f:
        f.write("# FAILURE_PATTERN_MINING_WORKBENCH_20260524\n\n")
        f.write(f"Generated: {TIMESTAMP}\n\n")

        f.write("## 1. Executive summary\n")
        f.write(f"Built an offline failure-pattern workbench over {n_total} completed cases across four scenarios. The workbench outputs actionable failure clusters, mechanism diagnoses, candidate fixes, and a repeatable implementation loop.\n\n")

        f.write("## 2. Data sources and caveats\n")
        f.write("Included completed sources only (official + auxiliary): Cohere GSM8K canonical, Mistral GSM8K full300 replay, Mistral MATH-500 Scenario 5, Cohere MATH-500 auxiliary, C1 pooled voting analysis, and cross-scenario investigation.\n\n")

        f.write("## 3. Current algorithm failure overview\n")
        if len(views):
            f.write(_table_md(views))
            f.write("\n\n")
        else:
            f.write("No view summary rows generated.\n\n")

        f.write("## 4. Ranked failure patterns\n")
        if len(patterns):
            f.write(_table_md(patterns, max_rows=20))
            f.write("\n\n")
        else:
            f.write("No mined groups above support threshold.\n\n")

        f.write("## 5. Detailed failure clusters\n")
        f.write(_table_md(clusters.sort_values("n_cases", ascending=False)))
        f.write("\n\n")

        f.write("## 6. Mechanism diagnoses\n")
        f.write("See `outputs/failure_pattern_mining_workbench_20260524/failure_mechanism_diagnoses.md` for per-pattern causal hypotheses and evidence-linked reasoning.\n\n")

        f.write("## 7. Candidate fixes\n")
        f.write(_table_md(fixes))
        f.write("\n\n")

        f.write("## 8. Implementation priority queue\n")
        f.write(_table_md(queue_df))
        f.write("\n\n")

        f.write("## 9. What can be improved by selector alone\n")
        f.write(f"Selector-fixable cluster mass (sum of cluster counts where `needs_generation_or_budget=false`): {int(selector_fixable)}.\n\n")

        f.write("## 10. What requires better generation/more budget\n")
        f.write(f"Generation/budget-bound cluster mass (`MATH_all_sources_wrong` family): {int(generation_bound)}.\n\n")

        f.write("## 11. How to repeat this loop after new runs\n")
        f.write("1. Wait for run completion and integrity PASS.\n")
        f.write("2. Update source artifacts in this script if new canonical paths change.\n")
        f.write("3. Re-run `python3 scripts/build_failure_pattern_workbench.py`.\n")
        f.write("4. Re-check `failure_views_summary.csv` and top clusters.\n")
        f.write("5. Re-prioritize queue and implement top fix.\n\n")

        f.write("## 12. Safety confirmation\n")
        f.write("- Offline analysis only\n")
        f.write("- No API calls launched\n")
        f.write("- No active jobs touched\n")
        f.write("- No source artifact overwrite\n")
        f.write("- No commit/push\n")

    print(f"  Written: {DOC_REPORT}")
    return DOC_REPORT


def write_manifest(unified: pd.DataFrame) -> str:
    print("[step12] Writing manifest...")

    files_created = sorted([p for p in os.listdir(OUT_ROOT) if os.path.isfile(os.path.join(OUT_ROOT, p))])
    casebooks = sorted(os.listdir(CASEBOOK_DIR))

    manifest = {
        "timestamp": TIMESTAMP,
        "input_artifacts": {
            "c1_unified_case_table": os.path.relpath(C1_BASE, REPO),
            "c1_router_augmented_feature_table": os.path.relpath(C1_ROUTER, REPO),
            "learned_router_case_predictions": os.path.relpath(LEARNED_ROUTER_CASE_PRED, REPO),
            "source_inventory_spec": SOURCE_INVENTORY_SPEC,
        },
        "scripts_created": ["scripts/build_failure_pattern_workbench.py"],
        "files_created": files_created,
        "cluster_casebooks": casebooks,
        "scenarios_included": unified["scenario_id"].value_counts().to_dict(),
        "api_calls_launched": False,
        "active_jobs_touched": False,
        "limitations": [
            "Cohere official MATH-500 Scenario 4 was active and excluded from completed-scenario analysis.",
            "Cerebras GSM8K and Mistral train1000 active runs were excluded.",
            "Learned-router column uses within-scenario CV selected_correct from existing artifact; no retraining run was launched.",
            "Some selector decision answers are inferred from scenario-level replay behavior where direct per-case answers are not available.",
        ],
    }

    out = os.path.join(OUT_ROOT, "manifest.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"  Written: {out}")
    return out


def main():
    print("=== Failure Pattern Mining Workbench ===")
    print(f"timestamp={TIMESTAMP}")
    print(f"output_root={OUT_ROOT}")

    unified = build_unified_case_table()
    views = define_failure_views(unified)
    patterns = mine_failure_patterns(unified)
    clusters, _ = produce_failure_clusters(unified)
    write_mechanism_diagnoses(unified, clusters)
    fixes = write_candidate_fixes()
    queue_df = write_implementation_queue()
    write_human_report(unified, views, patterns, clusters, fixes, queue_df)
    write_manifest(unified)

    print("=== Done ===")
    print(f"unified_rows={len(unified)}")
    print(f"pattern_groups={len(patterns)}")
    print(f"clusters={len(clusters)}")


if __name__ == "__main__":
    main()
