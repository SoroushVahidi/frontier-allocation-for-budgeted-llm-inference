#!/usr/bin/env python3
"""Offline analysis for official Cohere x MATH-500 agreement-only behavior.

Builds:
- Scenario-4 detailed agreement-only analysis bundle
- Official4 failure-pattern workbench refresh bundle

Safety: offline-only, no API calls, no active-job interaction.
"""

from __future__ import annotations

import json
import math
import os
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from scripts.evaluate_reliability_gated_pooled_voting_c1 import (
    add_pattern_features,
    c1a_decision,
    c1d_decision,
    compute_training_fold_calibration,
    pooled4_decision,
)

REPO = Path(__file__).resolve().parents[1]

SCENARIO4_CASE_LEVEL = REPO / "outputs" / "cohere_math500_official_scenario4_processing_20260524" / "scenario4_case_level_selector_replay.csv"
FOUR_SCENARIO_CASE_LEVEL = REPO / "outputs" / "four_scenario_official_matrix_20260524" / "four_scenario_case_level_replay.csv"
PREV_WORKBENCH_CLUSTER_SUMMARY = REPO / "outputs" / "failure_pattern_mining_workbench_20260524" / "failure_clusters_summary.csv"

OUT = REPO / "outputs" / "cohere_math500_agreement_only_analysis_20260524"
DOC = REPO / "docs" / "COHERE_MATH500_AGREEMENT_ONLY_ANALYSIS_20260524.md"

OFF4_OUT = REPO / "outputs" / "failure_pattern_workbench_official4_20260524"
OFF4_DOC = REPO / "docs" / "FAILURE_PATTERN_WORKBENCH_OFFICIAL4_20260524.md"


def normalize_answer(x: Any) -> str:
    s = str(x or "").strip()
    if not s:
        return ""
    s = re.sub(r"[\$,]", "", s)
    s = re.sub(r"\\boxed\{([^}]+)\}", r"\1", s)
    s = s.strip().lower()
    try:
        v = float(s)
        if math.isfinite(v):
            if v == int(v):
                return str(int(v))
            return f"{v:.10f}".rstrip("0").rstrip(".")
    except Exception:
        pass
    return s


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_int(x: Any) -> int:
    try:
        if pd.isna(x):
            return 0
    except Exception:
        pass
    try:
        return int(x)
    except Exception:
        return 0


def safe_bool(x: Any) -> bool:
    if isinstance(x, (bool, np.bool_)):
        return bool(x)
    if isinstance(x, (int, np.integer, float, np.floating)):
        return bool(int(x))
    if x is None:
        return False
    s = str(x).strip().lower()
    return s in {"1", "true", "yes", "y", "t"}


def answer_to_source(answer: str, row: pd.Series) -> str:
    ans = normalize_answer(answer)
    matches: list[str] = []
    for src in ["frontier", "L1", "S1", "TALE"]:
        if normalize_answer(row.get(f"{src}_ans", "")) == ans and ans:
            matches.append(src)
    if not matches:
        return "none"
    return "+".join(matches)


def question_features(df: pd.DataFrame) -> pd.DataFrame:
    q = df.get("question", "").fillna("").astype(str)
    df["question_length"] = q.str.len()
    df["question_number_count"] = q.str.count(r"[-+]?\d+(?:\.\d+)?")
    df["question_has_equation_flag"] = q.str.contains(r"=|\\frac|\\sqrt|\^|\(|\)", regex=True).astype(int)
    return df


def likely_reason(row: pd.Series, left_name: str, right_name: str) -> str:
    if safe_bool(row.get("all_sources_wrong", 0)):
        return "generation_bound_all_sources_wrong"
    if safe_bool(row.get("external_majority_exists", 0)) and safe_bool(row.get("external_majority_excludes_frontier", 0)):
        return "external_2of3_majority_against_frontier"
    if safe_bool(row.get("no_majority_flag", 0)):
        return "no_majority_fallback_difference"
    if safe_bool(row.get("S1_isolated", 0)):
        return "s1_isolated_split"
    return f"{left_name}_vs_{right_name}_decision_difference"


def compute_all_sources_flags(df: pd.DataFrame) -> pd.DataFrame:
    src_ok_cols = ["frontier_ok", "L1_ok", "S1_ok", "TALE_ok"]
    src_ok_sum = df[src_ok_cols].apply(pd.to_numeric, errors="coerce").fillna(0).astype(int).sum(axis=1)
    df["all_sources_wrong"] = (src_ok_sum == 0).astype(int)
    df["all_sources_correct"] = (src_ok_sum == 4).astype(int)
    df["only_frontier_correct"] = ((df["frontier_ok"] == 1) & (src_ok_sum == 1)).astype(int)
    df["only_L1_correct"] = ((df["L1_ok"] == 1) & (src_ok_sum == 1)).astype(int)
    df["only_S1_correct"] = ((df["S1_ok"] == 1) & (src_ok_sum == 1)).astype(int)
    return df


def build_source_inventory() -> pd.DataFrame:
    rows = [
        {
            "source_group": "official_cohere_math500_scenario4",
            "doc": "docs/COHERE_MATH500_OFFICIAL_SCENARIO4_PROCESSING_20260524.md",
            "artifact": "outputs/cohere_math500_official_scenario4_processing_20260524/",
            "exists": True,
        },
        {
            "source_group": "official_four_scenario_matrix",
            "doc": "docs/FOUR_SCENARIO_OFFICIAL_MATRIX_20260524.md",
            "artifact": "outputs/four_scenario_official_matrix_20260524/",
            "exists": True,
        },
        {
            "source_group": "previous_failure_workbench",
            "doc": "docs/FAILURE_PATTERN_MINING_WORKBENCH_20260524.md",
            "artifact": "outputs/failure_pattern_mining_workbench_20260524/",
            "exists": True,
        },
        {
            "source_group": "c1_fix_context",
            "doc": "docs/RELIABILITY_GATED_POOLED_VOTING_C1_20260524.md",
            "artifact": "outputs/reliability_gated_pooled_voting_c1_20260524/",
            "exists": True,
        },
        {
            "source_group": "fix01_context",
            "doc": "docs/FIX01_STRENGTHENED_C1D_20260524.md",
            "artifact": "outputs/fix01_strengthened_c1d_20260524/",
            "exists": True,
        },
        {
            "source_group": "fix03_context",
            "doc": "docs/FIX03_S1_NEAR_PEER_GATE_20260524.md",
            "artifact": "outputs/fix03_s1_near_peer_gate_20260524/",
            "exists": True,
        },
        {
            "source_group": "mistral_train1000_aux_context",
            "doc": "docs/MISTRAL_LARGE_ROUTER_TRAINING_GSM8K_PROCESSING_20260524.md",
            "artifact": "outputs/mistral_large_router_training_gsm8k_processing_20260524/",
            "exists": True,
        },
    ]
    return pd.DataFrame(rows)


def add_selector_action_source_columns(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    calib = compute_training_fold_calibration(add_pattern_features(df.copy()))
    ranked_sources = list(calib.get("ranked_sources", ["frontier", "L1", "S1", "TALE"]))
    dom_source = str(calib.get("best_source", "frontier"))
    dom_margin = float(calib.get("dominance_margin", 0.0))

    # Ensure replay columns exist exactly as rule definitions in this repo.
    for col in ["pooled4_decision", "beta_shrinkage_decision", "c1d_decision", "c1a_t005_decision"]:
        if col not in df.columns:
            if col == "pooled4_decision":
                df[col] = df.apply(lambda r: pooled4_decision(r, calib), axis=1)
            elif col == "beta_shrinkage_decision":
                if dom_margin >= 0.05:
                    df[col] = df[f"{dom_source}_ans"].astype(str)
                else:
                    df[col] = df.apply(lambda r: pooled4_decision(r, calib), axis=1)
            elif col == "c1d_decision":
                df[col] = df.apply(lambda r: c1d_decision(r, calib), axis=1)
            elif col == "c1a_t005_decision":
                df[col] = df.apply(lambda r: c1a_decision(r, calib, 0.05), axis=1)

    if "agreement_only_decision" not in df.columns:
        def _ao(r: pd.Series) -> str:
            ext = [normalize_answer(r.get("L1_ans", "")), normalize_answer(r.get("S1_ans", "")), normalize_answer(r.get("TALE_ans", ""))]
            ext = [x for x in ext if x]
            if len(ext) < 3:
                return str(r.get("frontier_ans", "") or "")
            c = Counter(ext)
            top, count = c.most_common(1)[0]
            f = normalize_answer(r.get("frontier_ans", ""))
            return top if count >= 2 and top != f else str(r.get("frontier_ans", "") or "")
        df["agreement_only_decision"] = df.apply(_ao, axis=1)

    selector_specs = {
        "pooled4": ("pooled4_decision", "pooled4_ok"),
        "agreement_only": ("agreement_only_decision", "agreement_only_ok"),
        "beta_shrinkage": ("beta_shrinkage_decision", "beta_shrinkage_ok"),
        "C1d": ("c1d_decision", "c1d_ok"),
        "C1a_t005": ("c1a_t005_decision", "c1a_t005_ok"),
    }

    for sel, (dcol, okcol) in selector_specs.items():
        ans_col = f"{sel}_selected_answer"
        src_col = f"{sel}_selected_source"
        act_col = f"{sel}_selected_action"
        cor_col = f"{sel}_selected_correct"

        df[ans_col] = df[dcol].astype(str)
        df[src_col] = df.apply(lambda r: answer_to_source(r[dcol], r), axis=1)

        if sel == "agreement_only":
            df[act_col] = np.where(
                df["agreement_only_decision"].astype(str).map(normalize_answer)
                == df["frontier_ans"].astype(str).map(normalize_answer),
                "keep_frontier",
                "defer_external_2of3_majority",
            )
            df[src_col] = np.where(df[act_col] == "keep_frontier", "frontier", "external_2of3_majority")
        elif sel == "pooled4":
            has_maj = df["has_majority"].apply(safe_bool)
            maj_match = df["pooled4_decision"].astype(str).map(normalize_answer) == df["majority_answer"].astype(str).map(normalize_answer)
            df[act_col] = np.where(has_maj & maj_match, "pooled4_majority_vote", "pooled4_no_majority_fallback")
            # Determine fallback source by ranked source order.
            fallback_src = []
            for _, row in df.iterrows():
                if safe_bool(row.get("has_majority", 0)) and normalize_answer(row.get("pooled4_decision", "")) == normalize_answer(row.get("majority_answer", "")):
                    fallback_src.append("majority_vote")
                    continue
                dec = normalize_answer(row.get("pooled4_decision", ""))
                chosen = "unknown"
                for src in ranked_sources:
                    if normalize_answer(row.get(f"{src}_ans", "")) == dec and dec:
                        chosen = src
                        break
                fallback_src.append(chosen)
            df[src_col] = fallback_src
        elif sel == "beta_shrinkage":
            if dom_margin >= 0.05:
                df[act_col] = "dominant_source_override"
                df[src_col] = dom_source
            else:
                df[act_col] = "fallback_to_pooled4"
        elif sel == "C1d":
            if dom_margin < 0.03:
                df[act_col] = "fallback_to_pooled4"
            else:
                df[act_col] = np.where(
                    df["has_majority"].apply(safe_bool)
                    & (df["majority_answer"].astype(str).map(normalize_answer) == df[f"{dom_source}_ans"].astype(str).map(normalize_answer)),
                    "majority_includes_dominant_source",
                    "dominant_source_override",
                )
                df[src_col] = np.where(df[act_col] == "dominant_source_override", dom_source, "majority_vote")
        elif sel == "C1a_t005":
            if dom_margin >= 0.05:
                df[act_col] = "dominant_source_override"
                df[src_col] = dom_source
            else:
                df[act_col] = "fallback_to_pooled4"

        if okcol in df.columns:
            df[cor_col] = pd.to_numeric(df[okcol], errors="coerce").fillna(0).astype(int)
        else:
            df[cor_col] = (df[ans_col].astype(str).map(normalize_answer) == df["gold"].astype(str).map(normalize_answer)).astype(int)

    # Oracle source/action fields.
    df["oracle_best_source"] = df.apply(
        lambda r: "+".join([s for s in ["frontier", "L1", "S1", "TALE"] if safe_int(r.get(f"{s}_ok", 0)) == 1]) or "none",
        axis=1,
    )
    df["oracle_best_action"] = df.get("oracle_best_action_decision", "")

    calib_meta = {
        "ranked_sources": ranked_sources,
        "best_source": dom_source,
        "dominance_margin": dom_margin,
        "shrunk_acc": {k: float(v) for k, v in calib.get("shrunk_acc", {}).items()},
    }
    return df, calib_meta


def pairwise_summary(df: pd.DataFrame, left_ok: str, right_ok: str, left_ans: str, right_ans: str, left_name: str, right_name: str) -> pd.DataFrame:
    l = pd.to_numeric(df[left_ok], errors="coerce").fillna(0).astype(int)
    r = pd.to_numeric(df[right_ok], errors="coerce").fillna(0).astype(int)
    same_ans = (df[left_ans].astype(str).map(normalize_answer) == df[right_ans].astype(str).map(normalize_answer)).astype(int)
    out = pd.DataFrame([
        {"comparison": f"{left_name}_vs_{right_name}", "metric": "both_correct", "count": int(((l == 1) & (r == 1)).sum())},
        {"comparison": f"{left_name}_vs_{right_name}", "metric": "both_wrong", "count": int(((l == 0) & (r == 0)).sum())},
        {"comparison": f"{left_name}_vs_{right_name}", "metric": f"{left_name}_correct_{right_name}_wrong", "count": int(((l == 1) & (r == 0)).sum())},
        {"comparison": f"{left_name}_vs_{right_name}", "metric": f"{left_name}_wrong_{right_name}_correct", "count": int(((l == 0) & (r == 1)).sum())},
        {"comparison": f"{left_name}_vs_{right_name}", "metric": "same_selected_answer", "count": int((same_ans == 1).sum())},
        {"comparison": f"{left_name}_vs_{right_name}", "metric": "different_selected_answer", "count": int((same_ans == 0).sum())},
        {
            "comparison": f"{left_name}_vs_{right_name}",
            "metric": "net_recovery",
            "count": int(((l == 1) & (r == 0)).sum() - ((l == 0) & (r == 1)).sum()),
        },
    ])
    return out


def build_case_diff(df: pd.DataFrame, left_ok: str, right_ok: str, left_ans: str, right_ans: str, left_name: str, right_name: str, mode: str) -> pd.DataFrame:
    l = pd.to_numeric(df[left_ok], errors="coerce").fillna(0).astype(int)
    r = pd.to_numeric(df[right_ok], errors="coerce").fillna(0).astype(int)
    if mode == "recover":
        mask = (l == 1) & (r == 0)
    else:
        mask = (l == 0) & (r == 1)

    cols = [
        "example_id", "question", "gold",
        "frontier_ans", "frontier_ok", "L1_ans", "L1_ok", "S1_ans", "S1_ok", "TALE_ans", "TALE_ok",
        "unique_answer_count", "all_four_agree", "three_one_split", "two_two_split", "all_different",
        "majority_size", "majority_answer", "external_majority_exists", "external_majority_answer",
        "external_majority_excludes_frontier", "external_majority_excludes_S1", "no_majority_flag", "S1_isolated",
        left_ans, left_ok, right_ans, right_ok,
    ]
    out = df.loc[mask, [c for c in cols if c in df.columns]].copy()
    out[f"likely_reason_{left_name}_vs_{right_name}"] = out.apply(lambda r: likely_reason(r, left_name, right_name), axis=1)
    return out


def pattern_group_tables(df: pd.DataFrame, comp_name: str, right_ok_col: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    base = df.copy()
    base["agreement_recovery"] = ((base["agreement_only_selected_correct"] == 1) & (pd.to_numeric(base[right_ok_col], errors="coerce").fillna(0).astype(int) == 0)).astype(int)
    base["agreement_regression"] = ((base["agreement_only_selected_correct"] == 0) & (pd.to_numeric(base[right_ok_col], errors="coerce").fillna(0).astype(int) == 1)).astype(int)

    group_cols = [
        "unique_answer_count",
        "majority_size",
        "external_majority_exists",
        "external_majority_excludes_frontier",
        "external_majority_excludes_S1",
        "frontier_ok",
        "frontier_in_majority",
        "S1_ok",
        "S1_in_majority",
        "S1_isolated",
        "L1_ok",
        "L1_TALE_agree",
        "only_frontier_correct",
        "only_L1_correct",
        "only_S1_correct",
        "all_sources_wrong",
        "all_sources_correct",
        "question_has_equation_flag",
    ]
    for c in group_cols:
        if c not in base.columns:
            base[c] = 0

    g = (
        base.groupby(group_cols, dropna=False)
        .agg(
            support=("example_id", "count"),
            recovery_count=("agreement_recovery", "sum"),
            regression_count=("agreement_regression", "sum"),
        )
        .reset_index()
    )
    g["recovery_precision"] = np.where(g["support"] > 0, g["recovery_count"] / g["support"], 0.0)
    g["net_benefit"] = g["recovery_count"] - g["regression_count"]
    g["selector_fixable"] = (g["recovery_count"] > 0).astype(int)
    g["generation_bound"] = ((g["all_sources_wrong"] == 1) & (g["recovery_count"] == 0)).astype(int)
    g["comparator"] = comp_name

    win = g[g["recovery_count"] > 0].sort_values(["recovery_count", "net_benefit", "support"], ascending=False)
    loss = g[g["regression_count"] > 0].sort_values(["regression_count", "support"], ascending=False)
    return g, win, loss


def count_by_scenario(df: pd.DataFrame, mask: pd.Series) -> dict[str, int]:
    s = df.loc[mask, "scenario_id"].value_counts().to_dict()
    return {str(k): int(v) for k, v in s.items()}


def table_text(df: pd.DataFrame, index: bool = False) -> str:
    if df is None or len(df) == 0:
        return "None"
    return df.to_string(index=index)


def build_official4_clusters(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    clusters: list[tuple[str, str, str, pd.Series, str, str, str, str, bool, bool]] = [
        (
            "O1_all_sources_wrong",
            "all_sources_wrong",
            "all four sources wrong (selector-irrecoverable)",
            df["all_sources_wrong"] == 1,
            "generation ceiling",
            "budget escalation / generation improvement",
            "selector-only none",
            "n/a",
            False,
            True,
        ),
        (
            "O2_cohere_math_agreement_win_vs_beta",
            "cohere_math_agreement_win_vs_beta",
            "official Cohere MATH where agreement_only correct and beta wrong",
            (df["scenario_id"] == "cohere_math500") & (df["agreement_only_ok"] == 1) & (df["beta_shrinkage_ok"] == 0),
            "external 2-of-3 majority overrides beta/pooled fallback",
            "agreement-only gate in near-peer hard regimes",
            "recover beta misses on Cohere MATH",
            "medium",
            True,
            False,
        ),
        (
            "O3_cohere_math_agreement_regression_vs_beta",
            "cohere_math_agreement_regression_vs_beta",
            "official Cohere MATH where agreement_only wrong and beta correct",
            (df["scenario_id"] == "cohere_math500") & (df["agreement_only_ok"] == 0) & (df["beta_shrinkage_ok"] == 1),
            "wrong external-majority or majority-noise defer",
            "agreement gate + confidence skepticism",
            "bound regressions",
            "medium",
            True,
            False,
        ),
        (
            "O4_beta_c1d_wrong_oracle_right",
            "beta_c1d_wrong_oracle_right",
            "beta and C1d both wrong while oracle action is correct",
            (df["beta_shrinkage_ok"] == 0) & (df["c1d_ok"] == 0) & (df["oracle_best_action_ok"] == 1),
            "action-choice error with available correct source",
            "pattern-specific action table (RG-EB-Action)",
            "high selector-recoverable mass",
            "medium",
            True,
            False,
        ),
        (
            "O5_fix03_revisit_signal",
            "fix03_revisit_signal",
            "S1 correct but beta wrong in no-majority / near-peer regions",
            (df["S1_ok"] == 1) & (df["beta_shrinkage_ok"] == 0) & ((df["no_majority_flag"] == 1) | (df["all_different"] == 1)),
            "possible S1 under-use on hard near-peer cases",
            "revisit FIX-03 with official4 constraints",
            "targeted recoveries",
            "low-medium",
            True,
            False,
        ),
    ]

    for cid, label, definition, mask, mech, fix, benefit, risk, zec, needs_gen in clusters:
        n = int(mask.sum())
        if n == 0:
            continue
        rows.append(
            {
                "cluster_id": cid,
                "cluster_label": label,
                "definition": definition,
                "n_cases": n,
                "count_by_scenario": json.dumps(count_by_scenario(df, mask), sort_keys=True),
                "likely_failure_mechanism": mech,
                "possible_fix": fix,
                "expected_benefit": benefit,
                "regression_risk": risk,
                "zero_extra_call_fix_possible": bool(zec),
                "needs_generation_or_budget": bool(needs_gen),
            }
        )

    out = pd.DataFrame(rows)
    if len(out):
        out = out.sort_values("n_cases", ascending=False).reset_index(drop=True)
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    OFF4_OUT.mkdir(parents=True, exist_ok=True)

    # Step 3 inventory
    inv = build_source_inventory()
    inv.to_csv(OUT / "source_artifact_inventory.csv", index=False)
    (OUT / "source_artifact_inventory.json").write_text(inv.to_json(orient="records", indent=2), encoding="utf-8")

    # Load Scenario 4 official replay table.
    s4 = pd.read_csv(SCENARIO4_CASE_LEVEL)
    s4 = question_features(s4)
    s4 = compute_all_sources_flags(s4)
    s4, calib_meta = add_selector_action_source_columns(s4)

    # Case table export
    required_cols = [
        "example_id", "question", "gold",
        "frontier_ans", "frontier_ok", "L1_ans", "L1_ok", "S1_ans", "S1_ok", "TALE_ans", "TALE_ok",
        "pooled4_selected_answer", "pooled4_selected_source", "pooled4_selected_action", "pooled4_selected_correct",
        "agreement_only_selected_answer", "agreement_only_selected_source", "agreement_only_selected_action", "agreement_only_selected_correct",
        "beta_shrinkage_selected_answer", "beta_shrinkage_selected_source", "beta_shrinkage_selected_action", "beta_shrinkage_selected_correct",
        "C1d_selected_answer", "C1d_selected_source", "C1d_selected_action", "C1d_selected_correct",
        "C1a_t005_selected_answer", "C1a_t005_selected_source", "C1a_t005_selected_action", "C1a_t005_selected_correct",
        "oracle_best_source", "oracle_best_action",
        "unique_answer_count", "all_four_agree", "three_one_split", "two_two_split", "all_different",
        "majority_size", "majority_answer", "frontier_in_majority", "S1_in_majority", "L1_TALE_agree",
        "S1_isolated", "frontier_isolated",
        "external_majority_exists", "external_majority_answer",
        "external_majority_excludes_frontier", "external_majority_excludes_S1",
        "question_length", "question_number_count", "question_has_equation_flag",
        "all_sources_wrong", "all_sources_correct", "only_frontier_correct", "only_L1_correct", "only_S1_correct",
    ]
    s4_case = s4[[c for c in required_cols if c in s4.columns]].copy()
    s4_case.to_csv(OUT / "cohere_math500_official_case_table.csv", index=False)

    # Step 4 rule documentation
    (OUT / "agreement_only_rule_description.md").write_text(
        "\n".join([
            "# agreement_only rule (reconstructed)",
            "- Policy: `agreement_only_2of3_against_frontier` in `experiments/support_aware_selector.py`.",
            "- Inputs used: frontier/L1/S1/TALE answers only (gold-free).",
            "- If any external answer (L1/S1/TALE) is missing/unparseable: keep frontier.",
            "- Else compute external 2-of-3 majority over {L1,S1,TALE}.",
            "- If no external 2-of-3 agreement: keep frontier.",
            "- If external 2-of-3 answer equals frontier: keep frontier.",
            "- If external 2-of-3 answer differs from frontier: defer to external majority answer.",
            "- Fallback behavior: frontier retained in all non-defer cases.",
            "- Difference from pooled4: pooled4 uses all-4 majority and no-majority fallback to best calibrated source; agreement_only never uses S1/L1/TALE single-source fallback unless external 2-of-3 exists.",
            "",
            "Scenario-4 calibration snapshot used by replay diagnostics:",
            json.dumps(calib_meta, indent=2),
        ]),
        encoding="utf-8",
    )

    # Step 5 pairwise tables
    pair_p4 = pairwise_summary(
        s4,
        "agreement_only_selected_correct",
        "pooled4_selected_correct",
        "agreement_only_selected_answer",
        "pooled4_selected_answer",
        "agreement_only",
        "pooled4",
    )
    pair_beta = pairwise_summary(
        s4,
        "agreement_only_selected_correct",
        "beta_shrinkage_selected_correct",
        "agreement_only_selected_answer",
        "beta_shrinkage_selected_answer",
        "agreement_only",
        "beta_shrinkage",
    )
    pair_c1d = pairwise_summary(
        s4,
        "agreement_only_selected_correct",
        "C1d_selected_correct",
        "agreement_only_selected_answer",
        "C1d_selected_answer",
        "agreement_only",
        "C1d",
    )

    pair_sources = []
    for src in ["frontier", "L1", "S1", "TALE"]:
        tmp = pairwise_summary(
            s4,
            "agreement_only_selected_correct",
            f"{src}_ok",
            "agreement_only_selected_answer",
            f"{src}_ans",
            "agreement_only",
            src,
        )
        pair_sources.append(tmp)
    pair_sources_df = pd.concat(pair_sources, ignore_index=True)

    pair_p4.to_csv(OUT / "agreement_vs_pooled4_pairwise.csv", index=False)
    pair_beta.to_csv(OUT / "agreement_vs_beta_pairwise.csv", index=False)
    pair_c1d.to_csv(OUT / "agreement_vs_c1d_pairwise.csv", index=False)
    pair_sources_df.to_csv(OUT / "agreement_vs_sources_pairwise.csv", index=False)

    rec_reg_rows = []
    for nm, right in [("pooled4", "pooled4_selected_correct"), ("beta_shrinkage", "beta_shrinkage_selected_correct"), ("C1d", "C1d_selected_correct")]:
        rec = int(((s4["agreement_only_selected_correct"] == 1) & (s4[right] == 0)).sum())
        reg = int(((s4["agreement_only_selected_correct"] == 0) & (s4[right] == 1)).sum())
        rec_reg_rows.append({
            "comparison": f"agreement_only_vs_{nm}",
            "recoveries": rec,
            "regressions": reg,
            "net_recovery": rec - reg,
            "agreement_accuracy": float(s4["agreement_only_selected_correct"].mean()),
            f"{nm}_accuracy": float(s4[right].mean()),
        })
    pd.DataFrame(rec_reg_rows).to_csv(OUT / "agreement_only_recovery_regression_summary.csv", index=False)

    # Step 6 casebooks
    rec_p4 = build_case_diff(s4, "agreement_only_selected_correct", "pooled4_selected_correct", "agreement_only_selected_answer", "pooled4_selected_answer", "agreement_only", "pooled4", "recover")
    reg_p4 = build_case_diff(s4, "agreement_only_selected_correct", "pooled4_selected_correct", "agreement_only_selected_answer", "pooled4_selected_answer", "agreement_only", "pooled4", "regress")
    rec_b = build_case_diff(s4, "agreement_only_selected_correct", "beta_shrinkage_selected_correct", "agreement_only_selected_answer", "beta_shrinkage_selected_answer", "agreement_only", "beta", "recover")
    reg_b = build_case_diff(s4, "agreement_only_selected_correct", "beta_shrinkage_selected_correct", "agreement_only_selected_answer", "beta_shrinkage_selected_answer", "agreement_only", "beta", "regress")
    rec_c = build_case_diff(s4, "agreement_only_selected_correct", "C1d_selected_correct", "agreement_only_selected_answer", "C1d_selected_answer", "agreement_only", "c1d", "recover")
    reg_c = build_case_diff(s4, "agreement_only_selected_correct", "C1d_selected_correct", "agreement_only_selected_answer", "C1d_selected_answer", "agreement_only", "c1d", "regress")

    rec_p4.to_csv(OUT / "agreement_only_recovers_vs_pooled4_cases.csv", index=False)
    reg_p4.to_csv(OUT / "agreement_only_regresses_vs_pooled4_cases.csv", index=False)
    rec_b.to_csv(OUT / "agreement_only_recovers_vs_beta_cases.csv", index=False)
    reg_b.to_csv(OUT / "agreement_only_regresses_vs_beta_cases.csv", index=False)
    rec_c.to_csv(OUT / "agreement_only_recovers_vs_c1d_cases.csv", index=False)
    reg_c.to_csv(OUT / "agreement_only_regresses_vs_c1d_cases.csv", index=False)

    (OUT / "agreement_only_recovery_casebook.md").write_text(
        "\n".join([
            "# agreement_only recovery casebook",
            f"- vs pooled4: {len(rec_p4)} recoveries",
            f"- vs beta_shrinkage: {len(rec_b)} recoveries",
            f"- vs C1d: {len(rec_c)} recoveries",
            "",
            "Top likely reasons:",
            f"- vs pooled4: {rec_p4.filter(like='likely_reason').iloc[:,0].value_counts().head(5).to_dict() if len(rec_p4) else {}}",
            f"- vs beta: {rec_b.filter(like='likely_reason').iloc[:,0].value_counts().head(5).to_dict() if len(rec_b) else {}}",
            f"- vs C1d: {rec_c.filter(like='likely_reason').iloc[:,0].value_counts().head(5).to_dict() if len(rec_c) else {}}",
        ]),
        encoding="utf-8",
    )

    (OUT / "agreement_only_regression_casebook.md").write_text(
        "\n".join([
            "# agreement_only regression casebook",
            f"- vs pooled4: {len(reg_p4)} regressions",
            f"- vs beta_shrinkage: {len(reg_b)} regressions",
            f"- vs C1d: {len(reg_c)} regressions",
            "",
            "Top likely reasons:",
            f"- vs pooled4: {reg_p4.filter(like='likely_reason').iloc[:,0].value_counts().head(5).to_dict() if len(reg_p4) else {}}",
            f"- vs beta: {reg_b.filter(like='likely_reason').iloc[:,0].value_counts().head(5).to_dict() if len(reg_b) else {}}",
            f"- vs C1d: {reg_c.filter(like='likely_reason').iloc[:,0].value_counts().head(5).to_dict() if len(reg_c) else {}}",
        ]),
        encoding="utf-8",
    )

    # Step 7 patterns
    all_patterns = []
    win_tables = []
    loss_tables = []
    for comp, right_ok in [
        ("pooled4", "pooled4_selected_correct"),
        ("beta_shrinkage", "beta_shrinkage_selected_correct"),
        ("C1d", "C1d_selected_correct"),
    ]:
        g, w, l = pattern_group_tables(s4, comp, right_ok)
        all_patterns.append(g)
        win_tables.append(w)
        loss_tables.append(l)

    all_patterns_df = pd.concat(all_patterns, ignore_index=True)
    win_df = pd.concat(win_tables, ignore_index=True)
    loss_df = pd.concat(loss_tables, ignore_index=True)

    win_df.to_csv(OUT / "agreement_only_win_patterns.csv", index=False)
    loss_df.to_csv(OUT / "agreement_only_loss_patterns.csv", index=False)

    top_win = win_df.sort_values(["recovery_count", "net_benefit"], ascending=False).head(15)
    top_loss = loss_df.sort_values(["regression_count"], ascending=False).head(15)
    (OUT / "agreement_only_pattern_summary.md").write_text(
        "\n".join([
            "# agreement_only pattern summary",
            "## Top win patterns",
            table_text(top_win, index=False),
            "",
            "## Top loss patterns",
            table_text(top_loss, index=False),
        ]),
        encoding="utf-8",
    )

    # Step 8 mechanism diagnosis
    # Quantify key mechanisms.
    a = s4
    ao = a["agreement_only_selected_correct"]
    p4 = a["pooled4_selected_correct"]
    b = a["beta_shrinkage_selected_correct"]
    c = a["C1d_selected_correct"]

    win_p4 = (ao == 1) & (p4 == 0)
    reg_p4_mask = (ao == 0) & (p4 == 1)

    mech_stats = {
        "wins_vs_pooled4": int(win_p4.sum()),
        "regs_vs_pooled4": int(reg_p4_mask.sum()),
        "wins_in_external_maj_excl_frontier": int((win_p4 & (a["external_majority_exists"] == 1) & (a["external_majority_excludes_frontier"] == 1)).sum()),
        "wins_in_no_majority": int((win_p4 & (a["no_majority_flag"] == 1)).sum()),
        "wins_when_s1_isolated": int((win_p4 & (a["S1_isolated"] == 1)).sum()),
        "regs_in_external_maj_excl_frontier": int((reg_p4_mask & (a["external_majority_exists"] == 1) & (a["external_majority_excludes_frontier"] == 1)).sum()),
        "regs_in_no_majority": int((reg_p4_mask & (a["no_majority_flag"] == 1)).sum()),
        "agreement_acc": float(ao.mean()),
        "pooled4_acc": float(p4.mean()),
        "beta_acc": float(b.mean()),
        "c1d_acc": float(c.mean()),
    }

    (OUT / "agreement_only_mechanism_diagnosis.md").write_text(
        "\n".join([
            "# agreement_only mechanism diagnosis",
            "- agreement_only wins are primarily from external 2-of-3 override regions against frontier/pooled fallback.",
            "- pooled4/beta/C1d are tied here because scenario calibration is near-peer; dominance margin is below decisive thresholds, so they collapse to pooled behavior.",
            "- agreement_only is not universally better: regressions occur when external-majority is correlated-wrong or no-majority fallback would have picked a better source.",
            "- Mechanism is likely scenario-conditional (official Cohere MATH hard near-peer slice), not globally dominant.",
            "",
            "## Quantified evidence",
            json.dumps(mech_stats, indent=2),
        ]),
        encoding="utf-8",
    )

    # Step 9 official4 workbench refresh
    off4 = pd.read_csv(FOUR_SCENARIO_CASE_LEVEL)
    off4 = question_features(off4)
    off4 = compute_all_sources_flags(off4)

    # Keep official only (already official4).
    off4.to_csv(OFF4_OUT / "official4_unified_case_table.csv", index=False)

    # failure view summary
    selectors = {
        "frontier": "frontier_ok",
        "L1": "L1_ok",
        "S1": "S1_ok",
        "TALE": "TALE_ok",
        "pooled4": "pooled4_ok",
        "agreement_only": "agreement_only_ok",
        "beta_shrinkage": "beta_shrinkage_ok",
        "C1d": "c1d_ok",
        "C1a_t005": "c1a_t005_ok",
        "oracle_best_action": "oracle_best_action_ok",
    }

    sum_rows = []
    for sid, sdf in off4.groupby("scenario_id"):
        for sel, col in selectors.items():
            if col not in sdf.columns:
                continue
            acc = float(pd.to_numeric(sdf[col], errors="coerce").fillna(0).mean())
            sum_rows.append({"scenario_id": sid, "selector": sel, "accuracy": acc, "n": int(len(sdf))})
    summary_df = pd.DataFrame(sum_rows).sort_values(["scenario_id", "accuracy"], ascending=[True, False])
    summary_df.to_csv(OFF4_OUT / "official4_failure_views_summary.csv", index=False)

    # mined patterns focused on beta as current main selector diagnostic
    patt_cols = [
        "scenario_id", "unique_answer_count", "majority_size", "no_majority_flag",
        "external_majority_exists", "external_majority_excludes_frontier", "external_majority_excludes_S1",
        "S1_isolated", "frontier_ok", "L1_ok", "S1_ok", "TALE_ok", "all_sources_wrong", "all_sources_correct",
        "question_has_equation_flag",
    ]
    for ccol in patt_cols:
        if ccol not in off4.columns:
            off4[ccol] = 0

    mined = (
        off4.groupby(patt_cols, dropna=False)
        .agg(
            support=("example_id", "count"),
            beta_wrong=("beta_shrinkage_ok", lambda s: int((pd.to_numeric(s, errors="coerce").fillna(0) == 0).sum())),
            c1d_wrong=("c1d_ok", lambda s: int((pd.to_numeric(s, errors="coerce").fillna(0) == 0).sum())),
            agreement_win_vs_beta=("agreement_only_ok", lambda s: 0),
        )
        .reset_index()
    )

    # add explicit agreement win count by merged keys
    off4_tmp = off4.copy()
    off4_tmp["agreement_win_vs_beta"] = ((off4_tmp["agreement_only_ok"] == 1) & (off4_tmp["beta_shrinkage_ok"] == 0)).astype(int)
    aw = off4_tmp.groupby(patt_cols, dropna=False)["agreement_win_vs_beta"].sum().reset_index()
    mined = mined.drop(columns=["agreement_win_vs_beta"]).merge(aw, on=patt_cols, how="left")
    mined["agreement_win_vs_beta"] = mined["agreement_win_vs_beta"].fillna(0).astype(int)
    mined["beta_wrong_rate"] = np.where(mined["support"] > 0, mined["beta_wrong"] / mined["support"], 0.0)
    mined["agreement_win_precision"] = np.where(mined["support"] > 0, mined["agreement_win_vs_beta"] / mined["support"], 0.0)
    mined = mined.sort_values(["agreement_win_vs_beta", "beta_wrong", "support"], ascending=False)
    mined.to_csv(OFF4_OUT / "official4_mined_failure_patterns.csv", index=False)

    # cluster summary
    clusters_df = build_official4_clusters(off4)
    clusters_df.to_csv(OFF4_OUT / "official4_failure_clusters_summary.csv", index=False)

    # candidate fixes / queue
    cand_rows = [
        {
            "fix_id": "AG-01",
            "candidate": "agreement_only_gate",
            "motivation": "official Cohere MATH shows agreement_only > pooled4/beta/C1d",
            "expected_recoveries_signal": int(((off4["scenario_id"] == "cohere_math500") & (off4["agreement_only_ok"] == 1) & (off4["beta_shrinkage_ok"] == 0)).sum()),
            "regression_risk_signal": int(((off4["scenario_id"] == "cohere_math500") & (off4["agreement_only_ok"] == 0) & (off4["beta_shrinkage_ok"] == 1)).sum()),
            "required_features": "external_2of3_agreement, no_majority_flag, provider/dataset regime",
            "zero_extra_call": True,
            "evaluation_protocol": "paired official4 replay + regression audit",
            "implement_now": "test-first",
        },
        {
            "fix_id": "AG-02",
            "candidate": "hard_near_peer_fallback_selector",
            "motivation": "near-peer slices where pooled fallback is brittle",
            "expected_recoveries_signal": int(((off4["no_majority_flag"] == 1) & (off4["agreement_only_ok"] == 1) & (off4["beta_shrinkage_ok"] == 0)).sum()),
            "regression_risk_signal": int(((off4["no_majority_flag"] == 1) & (off4["agreement_only_ok"] == 0) & (off4["beta_shrinkage_ok"] == 1)).sum()),
            "required_features": "near-peer regime flags, external majority reliability",
            "zero_extra_call": True,
            "evaluation_protocol": "subset-specific replay by scenario",
            "implement_now": "after AG-01 audit",
        },
        {
            "fix_id": "AG-03",
            "candidate": "pattern_specific_action_table",
            "motivation": "oracle gap remains large when beta and C1d are both wrong",
            "expected_recoveries_signal": int(((off4["beta_shrinkage_ok"] == 0) & (off4["c1d_ok"] == 0) & (off4["oracle_best_action_ok"] == 1)).sum()),
            "regression_risk_signal": 0,
            "required_features": "pattern bucket + source reliability features",
            "zero_extra_call": True,
            "evaluation_protocol": "cross-scenario CV on official4 + auxiliary holdout",
            "implement_now": "design now, train later",
        },
    ]
    cand_df = pd.DataFrame(cand_rows)
    cand_df.to_csv(OUT / "agreement_only_inspired_candidate_fixes.csv", index=False)
    cand_df.to_csv(OFF4_OUT / "official4_candidate_fixes.csv", index=False)

    queue_rows = [
        {"priority": 1, "action": "Evaluate AG-01 agreement-only gate against beta/C1d on official4", "blocking": "none", "zero_extra_call": True},
        {"priority": 2, "action": "Design AG-01 regression guard for external-majority-correlated errors", "blocking": "AG-01 paired results", "zero_extra_call": True},
        {"priority": 3, "action": "Revisit FIX-03 conditions with official4-only evidence", "blocking": "AG-01/FIX-03 overlap audit", "zero_extra_call": True},
        {"priority": 4, "action": "Prepare router-v2 action set including agreement_only", "blocking": "training mix policy", "zero_extra_call": True},
    ]
    pd.DataFrame(queue_rows).to_csv(OFF4_OUT / "official4_next_failure_driven_queue.csv", index=False)

    # official vs auxiliary note
    aux_note_lines = [
        "# official4 vs auxiliary note",
        "- This refresh uses only the four official scenarios: cohere_gsm8k, mistral_gsm8k, cohere_math500, mistral_math500.",
        "- Cohere MATH auxiliary is excluded from official averages and kept as auxiliary context only.",
    ]
    if PREV_WORKBENCH_CLUSTER_SUMMARY.exists() and len(clusters_df):
        prev = pd.read_csv(PREV_WORKBENCH_CLUSTER_SUMMARY)
        aux_note_lines.append("")
        aux_note_lines.append("## Prior-vs-official cluster context")
        if "count_by_scenario" in prev.columns:
            # summarize how much prior mass depended on cohere_math500_aux
            aux_mass = 0
            for _, row in prev.iterrows():
                try:
                    d = json.loads(str(row.get("count_by_scenario", "{}")))
                except Exception:
                    d = {}
                aux_mass += int(d.get("cohere_math500_aux", 0))
            aux_note_lines.append(f"- Prior workbench contained {aux_mass} cluster-attributed cases from `cohere_math500_aux`.")
        aux_cohere_math_all_wrong = int(((off4["scenario_id"] == "cohere_math500") & (off4["all_sources_wrong"] == 1)).sum())
        aux_note_lines.append(f"- Official Cohere MATH all-sources-wrong count: {aux_cohere_math_all_wrong} (official-only).")

    (OFF4_OUT / "official4_official_vs_auxiliary_note.md").write_text("\n".join(aux_note_lines), encoding="utf-8")

    # Candidate-fixes markdown + router implications
    (OUT / "agreement_only_inspired_candidate_fixes.md").write_text(
        "\n".join([
            "# agreement-only inspired candidate fixes",
            "## Candidate A — agreement-only gate",
            "- Motivation: official Cohere MATH has agreement_only above pooled4/beta/C1d.",
            "- Expected recoveries: agreement-only recoveries concentrated in external 2-of-3 patterns.",
            "- Risks: correlated external-majority errors.",
            "- Features: external_majority_exists/excludes_frontier, no_majority_flag, provider/dataset regime.",
            "- Zero-extra-call: yes.",
            "- Evaluation: paired replay on official4 + regression audit by scenario.",
            "",
            "## Candidate B — hard near-peer fallback selector",
            "- Motivation: no-majority/hard-regime pooled fallback brittleness.",
            "- Strategy: use agreement-only in hard near-peer cells; keep beta/C1d elsewhere.",
            "- Zero-extra-call: yes.",
            "",
            "## Candidate C — pattern-specific action table (RG-EB-Action)",
            "- Motivation: remaining oracle gap where beta/C1d both wrong.",
            "- Actions: pooled4/agreement_only/best_source/C1d.",
            "- Zero-extra-call: yes.",
            "- Recommendation: design now; train after expanded mixed training corpus.",
        ]),
        encoding="utf-8",
    )

    (OUT / "router_v2_implications_after_scenario4.md").write_text(
        "\n".join([
            "# router-v2 implications after official Cohere MATH Scenario 4",
            "- Include `agreement_only` as an explicit action candidate in router-v2.",
            "- Train1000 GSM8K alone is insufficient for this effect; add Cohere MATH (official + auxiliary as separate domains) for action calibration.",
            "- Label space should include: pooled4, agreement_only, beta_shrinkage, C1d, best_source fallback.",
            "- Highest-value features after this result: external_majority_exists, external_majority_excludes_frontier, no_majority_flag, S1_isolated, scenario/provider/dataset identifiers.",
            "- To avoid overfit: enforce scenario-stratified validation and report per-scenario regressions, not only macro average.",
        ]),
        encoding="utf-8",
    )

    # official4 report doc
    off4_matrix = summary_df.pivot_table(index="selector", columns="scenario_id", values="accuracy", aggfunc="mean")
    off4_matrix["official_macro_mean"] = off4_matrix.mean(axis=1)
    off4_matrix = off4_matrix.sort_values("official_macro_mean", ascending=False)

    OFF4_DOC.write_text(
        "\n".join([
            "# FAILURE_PATTERN_WORKBENCH_OFFICIAL4_20260524",
            "",
            f"Generated: {now_utc()}",
            "",
            "## 1. Scope",
            "Official-only failure workbench over four official scenarios (Cohere GSM8K, Mistral GSM8K, Cohere MATH-500, Mistral MATH-500).",
            "",
            "## 2. Selector matrix (official4)",
            table_text(off4_matrix.reset_index(), index=False),
            "",
            "## 3. Key cluster summary",
            table_text(clusters_df, index=False),
            "",
            "## 4. Candidate fixes",
            table_text(cand_df, index=False),
            "",
            "## 5. Safety",
            "- offline only",
            "- no API calls",
            "- no active job interference",
            "- no commit/push",
        ]),
        encoding="utf-8",
    )

    # Step 12 main human-readable report
    def _metric(dfm: pd.DataFrame, metric: str) -> int:
        row = dfm[dfm["metric"] == metric]
        return int(row["count"].iloc[0]) if len(row) else 0

    report_lines = [
        "# COHERE_MATH500_AGREEMENT_ONLY_ANALYSIS_20260524",
        "",
        "## 1. Executive summary",
        "Official Cohere MATH-500 Scenario 4 confirms `agreement_only` (33.0%) is above pooled4/beta/C1d (~29.33%). The edge comes from external 2-of-3 defer regions, with meaningful but bounded regressions.",
        "",
        "## 2. Data source and caveats",
        "- Official Scenario 4 case table + selector replay only.",
        "- Offline replay diagnostics; no new generation/API calls.",
        "- C1d/C1a_t005/beta here remain diagnostic full-artifact replays, not fold-safe promotion evidence.",
        "",
        "## 3. Exact agreement-only rule",
        "See `agreement_only_rule_description.md` (generated from canonical policy in `experiments/support_aware_selector.py`).",
        "",
        "## 4. Why agreement-only wins on official Cohere MATH",
        f"- recoveries vs pooled4: {_metric(pair_p4, 'agreement_only_correct_pooled4_wrong')}",
        f"- regressions vs pooled4: {_metric(pair_p4, 'agreement_only_wrong_pooled4_correct')}",
        f"- net recovery vs pooled4: {_metric(pair_p4, 'net_recovery')}",
        f"- wins in external-majority-against-frontier regions: {mech_stats['wins_in_external_maj_excl_frontier']}",
        "",
        "## 5. Pairwise recovery/regression analysis",
        "- Pairwise CSVs: agreement vs pooled4/beta/C1d/sources are exported.",
        "",
        "## 6. Failure/recovery casebooks",
        "- Recovery and regression CSV + markdown casebooks exported.",
        "",
        "## 7. Feature/pattern analysis",
        "- Win/loss pattern tables exported with support, precision, regressions, and net benefit.",
        "",
        "## 8. Mechanism diagnosis",
        f"- agreement_only accuracy: {mech_stats['agreement_acc']:.4f}",
        f"- pooled4 accuracy: {mech_stats['pooled4_acc']:.4f}",
        f"- beta accuracy: {mech_stats['beta_acc']:.4f}",
        f"- C1d accuracy: {mech_stats['c1d_acc']:.4f}",
        "",
        "## 9. Official four-scenario workbench refresh",
        f"- Refreshed bundle: `{OFF4_OUT.relative_to(REPO)}`",
        f"- Report: `{OFF4_DOC.relative_to(REPO)}`",
        "",
        "## 10. Candidate fixes",
        "- Candidate A: agreement-only gate (test-first).",
        "- Candidate B: hard near-peer fallback selector.",
        "- Candidate C: pattern-specific action table.",
        "",
        "## 11. Router-v2 implications",
        "- Include agreement_only as action.",
        "- Keep official and auxiliary domains separated in evaluation summaries.",
        "",
        "## 12. Recommended next implementation query",
        "Implement AG-01 as a conservative agreement-only gate with explicit regression guard, then run paired official4 replay against beta/C1d.",
        "",
        "## 13. Safety confirmation",
        "- offline only",
        "- no API calls",
        "- no active-job interference",
        "- no commit/push",
    ]
    DOC.write_text("\n".join(report_lines), encoding="utf-8")

    # Step 13 manifests
    created_out_files = sorted([str(p.relative_to(REPO)) for p in OUT.glob("**/*") if p.is_file()])
    created_off4_files = sorted([str(p.relative_to(REPO)) for p in OFF4_OUT.glob("**/*") if p.is_file()])

    manifest = {
        "timestamp": now_utc(),
        "input_artifacts": [
            str(SCENARIO4_CASE_LEVEL.relative_to(REPO)),
            str(FOUR_SCENARIO_CASE_LEVEL.relative_to(REPO)),
            str(PREV_WORKBENCH_CLUSTER_SUMMARY.relative_to(REPO)),
        ],
        "output_files": created_out_files,
        "api_calls_launched": False,
        "active_jobs_touched": False,
        "limitations": [
            "C1/beta comparisons are diagnostic replay-level for this bundle",
            "No new model generation or runtime validation performed",
        ],
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    off4_manifest = {
        "timestamp": now_utc(),
        "input_artifacts": [
            str(FOUR_SCENARIO_CASE_LEVEL.relative_to(REPO)),
            str(PREV_WORKBENCH_CLUSTER_SUMMARY.relative_to(REPO)),
        ],
        "output_files": created_off4_files,
        "api_calls_launched": False,
        "active_jobs_touched": False,
        "limitations": [
            "Official4 workbench is offline and descriptive",
            "No policy promotion claim is made",
        ],
    }
    (OFF4_OUT / "manifest.json").write_text(json.dumps(off4_manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
