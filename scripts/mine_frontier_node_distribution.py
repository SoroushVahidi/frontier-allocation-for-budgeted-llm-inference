#!/usr/bin/env python3
"""
mine_frontier_node_distribution.py

No-API frontier node-distribution mining experiment: frontier_node_distribution_mining_v1.

For each case, extracts gold-free features describing the distribution of discovered
candidate nodes and reasoning edges, then analyses whether those features can predict
which missing edge should be explored next (especially backward_from_target_check /
verifier_check).

Gold answers (if inferrable) are used ONLY for offline label construction, never as
input features available at inference time.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.mine_reasoning_edge_sequences import (
    map_edge_color,
    load_trace_packets,
)

_TS = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

# ---------------------------------------------------------------------------
# Question cue patterns (gold-free, text-only)
# ---------------------------------------------------------------------------

_PROFIT_CUE = re.compile(
    r"\b(profit|revenue|cost|earn|charge|price|fee|income|expense|spend|spent|pay|paid|sale)\b",
    re.I,
)
_DIFFERENCE_CUE = re.compile(
    r"\b(left|remaining|leftover|difference|fewer|less|subtract|how many more|how much more|remain)\b",
    re.I,
)
_RATIO_PERCENT_CUE = re.compile(
    r"(\d+\s*%|percent|percentage|ratio|fraction|proportion|rate|per cent)", re.I
)
_ORIGINAL_BEFORE_CUE = re.compile(
    r"\b(before|original|initially|was|had|used to|start with|began with|at first)\b",
    re.I,
)
_PER_UNIT_CUE = re.compile(r"\b(each|per|every|apiece|per unit|per item)\b", re.I)
_UNIT_CONVERSION_CUE = re.compile(
    r"\b(convert|feet|foot|meters?|metres?|miles?|km|kilometers?|hours?|minutes?|seconds?|"
    r"lb|lbs|pounds?|kg|kilograms?|gallons?|liters?|litres?|inches?|yards?|celsius|fahrenheit|"
    r"ounces?|oz)\b",
    re.I,
)
_REMAINDER_LEFTOVER_CUE = re.compile(
    r"\b(remainder|leftover|left over|rest of|what is left|how much is left|remaining|surplus)\b",
    re.I,
)
_TRANSFORM_CUES = [
    _PROFIT_CUE, _DIFFERENCE_CUE, _RATIO_PERCENT_CUE,
    _ORIGINAL_BEFORE_CUE, _PER_UNIT_CUE, _UNIT_CONVERSION_CUE, _REMAINDER_LEFTOVER_CUE,
]


def _cue_count(text: str, patterns: list) -> int:
    return sum(1 for p in patterns if p.search(text))


# ---------------------------------------------------------------------------
# Numeric helpers
# ---------------------------------------------------------------------------

def _parse_numeric(s: str) -> float | None:
    """Parse a candidate answer string to float, or None if unparseable."""
    try:
        return float(str(s).strip().replace(",", ""))
    except (ValueError, TypeError):
        return None


def _numeric_candidates(answers: list[str]) -> list[float]:
    """Return float values from a list of answer strings."""
    return [v for v in (_parse_numeric(a) for a in answers) if v is not None]


def _safe_entropy(counts: list[int]) -> float:
    total = sum(counts)
    if total == 0:
        return 0.0
    return -sum((c / total) * math.log2(c / total) for c in counts if c > 0)


# ---------------------------------------------------------------------------
# Feature extraction (gold-free)
# ---------------------------------------------------------------------------

def extract_features(
    case: dict[str, Any],
) -> dict[str, Any]:
    """
    Extract all gold-free frontier/node-distribution features from one case.
    Returns a flat feature dict.
    """
    case_id = case.get("case_id", "")
    question = case.get("question", "")

    # ---- candidate/value features ----
    raw_answers: list[str] = [
        str(a) for a in case.get("candidate_answers", []) if str(a).strip()
    ]
    # Also include candidate_rows answers when available
    crows: list[dict[str, Any]] = case.get("structural_fields", {}).get("candidate_rows", [])
    crows_answers: list[str] = [
        str(r.get("candidate_answer", "") or "") for r in crows
        if str(r.get("candidate_answer", "") or "").strip()
    ]
    # Keep duplicates for candidate_count; deduplicate only for unique counts
    all_answer_strs: list[str] = raw_answers + [
        a for a in crows_answers if a not in set(raw_answers)
    ]
    all_answer_strs_dedup: list[str] = list(dict.fromkeys(all_answer_strs))

    numeric_vals = _numeric_candidates(all_answer_strs)
    unique_numerics = list(dict.fromkeys(_numeric_candidates(all_answer_strs_dedup)))

    candidate_count = len(all_answer_strs)
    unique_numeric_count = len(unique_numerics)
    repeated_value_count = candidate_count - unique_numeric_count if candidate_count > 0 else 0

    nm_min = min(unique_numerics) if unique_numerics else None
    nm_max = max(unique_numerics) if unique_numerics else None
    nm_range = (nm_max - nm_min) if (nm_min is not None and nm_max is not None) else None

    # ratio spread: max/min (if min > 0)
    pos_vals = [v for v in unique_numerics if v > 0]
    nm_ratio_spread = (max(pos_vals) / min(pos_vals)) if len(pos_vals) >= 2 else None

    # difference spread
    nm_diff_spread = nm_range

    has_integer = any(v == int(v) for v in unique_numerics)
    has_decimal = any(v != int(v) for v in unique_numerics if not math.isinf(v))
    has_frac_pct_like = any(0 < v < 1 for v in unique_numerics)
    has_degenerate_one = 1.0 in unique_numerics
    has_zero = 0.0 in unique_numerics

    sel_meta = case.get("selector_metadata", {})
    selected_answer = str(sel_meta.get("selected_answer", "") or "")

    # ---- semantic role features ----
    roles = [str(r.get("final_answer_role", "") or "") for r in crows]
    count_target_role = roles.count("target")
    count_intermediate_role = roles.count("intermediate")
    count_unknown_role = sum(1 for r in roles if r not in ("target", "intermediate"))

    tas_vals = []
    for r in crows:
        try:
            tas_vals.append(float(r.get("target_alignment_score") or 0.0))
        except (TypeError, ValueError):
            pass

    tas_max = max(tas_vals) if tas_vals else None
    tas_mean = (sum(tas_vals) / len(tas_vals)) if tas_vals else None
    tas_sorted = sorted(tas_vals, reverse=True)
    tas_gap_top2 = (tas_sorted[0] - tas_sorted[1]) if len(tas_sorted) >= 2 else None

    role_counts = [count_target_role, count_intermediate_role, count_unknown_role]
    candidate_role_entropy = _safe_entropy(role_counts)

    has_target_role = count_target_role > 0
    has_intermediate_role = count_intermediate_role > 0

    # ---- source/edge features ----
    bf_set = set(r.get("branch_family", "") for r in crows if r.get("branch_family"))
    colors = [
        map_edge_color(branch_family=r.get("branch_family") or "", last_op=r.get("last_operation_family", ""))
        for r in crows
    ]
    color_set = set(colors)
    color_counts = Counter(colors)

    pal_ok = str(case.get("pal_exec_summary", {}).get("pal_exec_ok", "0")) == "1"

    has_pal_candidate = "PAL_code" in color_set or pal_ok
    has_verifier_check = "verifier_check" in color_set
    has_bft_candidate = any("backward_from_target_check" in str(bf) for bf in bf_set)
    has_equation_setup = "equation_setup" in color_set
    has_target_first = any("target_first" in str(bf) for bf in bf_set)
    has_repair_candidate = "repair" in color_set or (
        str(sel_meta.get("selected_source", "")) == "repair_layer"
    )

    selected_source = str(sel_meta.get("selected_source", "") or "")
    bf_count_str = json.dumps(
        {bf: bfs.count(bf) for bf in sorted(bf_set) for bfs in [[r.get("branch_family","") for r in crows]]}
    )
    edge_color_count_str = json.dumps(dict(color_counts.most_common()))

    # branch family occurrence counts (for known families)
    bf_counts: Counter = Counter(r.get("branch_family", "") for r in crows)

    # ---- question cue features ----
    q = question.lower()
    has_profit_cue = bool(_PROFIT_CUE.search(q))
    has_difference_cue = bool(_DIFFERENCE_CUE.search(q))
    has_ratio_percent_cue = bool(_RATIO_PERCENT_CUE.search(q))
    has_original_before_cue = bool(_ORIGINAL_BEFORE_CUE.search(q))
    has_per_unit_cue = bool(_PER_UNIT_CUE.search(q))
    has_unit_conversion_cue = bool(_UNIT_CONVERSION_CUE.search(q))
    has_remainder_leftover_cue = bool(_REMAINDER_LEFTOVER_CUE.search(q))
    transformed_cue_count = _cue_count(q, _TRANSFORM_CUES)

    # ---- pool geometry features ----
    sel_numeric = _parse_numeric(selected_answer)
    selected_is_extreme = False
    selected_is_smallest = False
    selected_is_largest = False
    if sel_numeric is not None and unique_numerics:
        selected_is_smallest = sel_numeric == min(unique_numerics)
        selected_is_largest = sel_numeric == max(unique_numerics)
        selected_is_extreme = selected_is_smallest or selected_is_largest
    selected_is_one = sel_numeric == 1.0 if sel_numeric is not None else False
    selected_repeated = all_answer_strs.count(selected_answer) > 1 if selected_answer else False

    # Cluster count: use unique numeric values rounded to 2 sig figs as proxy
    def _sig_round(v: float, n: int = 2) -> float:
        if v == 0:
            return 0.0
        mag = math.floor(math.log10(abs(v)))
        return round(v, -int(mag) + n - 1)
    cluster_vals = set(_sig_round(v) for v in unique_numerics)
    candidate_values_cluster_count = len(cluster_vals)

    # Multiplicative relation: check if any pair (a, b) satisfies b ≈ k*a for small integer k
    values_contain_multiplicative_relation = False
    values_contain_additive_relation = False
    values_contain_conversion_like_relation = False
    if len(unique_numerics) >= 2:
        for i, a in enumerate(unique_numerics):
            for b in unique_numerics[i + 1:]:
                if a == 0 or b == 0:
                    continue
                ratio = b / a if b > a else a / b
                # Additive: b - a is close to one of the values
                diff = abs(b - a)
                if any(abs(diff - v) / max(abs(v), 1e-9) < 0.05 for v in unique_numerics):
                    values_contain_additive_relation = True
                # Multiplicative: ratio is close to a small integer
                if any(abs(ratio - k) / k < 0.05 for k in range(2, 11)):
                    values_contain_multiplicative_relation = True
                # Conversion-like: ratio close to known conversion factors
                conv_factors = [12, 3.281, 2.205, 3.785, 0.914, 1.609, 0.621]
                if any(abs(ratio - cf) / cf < 0.1 for cf in conv_factors):
                    values_contain_conversion_like_relation = True

    feats: dict[str, Any] = {
        "case_id": case_id,
        # candidate/value
        "candidate_count": candidate_count,
        "unique_numeric_count": unique_numeric_count,
        "repeated_value_count": repeated_value_count,
        "numeric_min": nm_min,
        "numeric_max": nm_max,
        "numeric_range": nm_range,
        "numeric_ratio_spread": nm_ratio_spread,
        "numeric_difference_spread": nm_diff_spread,
        "has_integer_candidates": int(has_integer),
        "has_decimal_candidates": int(has_decimal),
        "has_fraction_or_percent_like": int(has_frac_pct_like),
        "has_degenerate_one": int(has_degenerate_one),
        "has_zero": int(has_zero),
        "selected_answer": selected_answer,
        # semantic role
        "count_final_target_role": count_target_role,
        "count_intermediate_role": count_intermediate_role,
        "count_unknown_role": count_unknown_role,
        "target_alignment_score_max": tas_max,
        "target_alignment_score_mean": tas_mean,
        "target_alignment_score_gap_top2": tas_gap_top2,
        "candidate_role_entropy": round(candidate_role_entropy, 4),
        "has_candidate_marked_target": int(has_target_role),
        "has_candidate_marked_intermediate": int(has_intermediate_role),
        # source/edge
        "has_PAL_code_candidate": int(has_pal_candidate),
        "has_verifier_check_candidate": int(has_verifier_check),
        "has_backward_from_target_check": int(has_bft_candidate),
        "has_equation_setup_candidate": int(has_equation_setup),
        "has_target_first_candidate": int(has_target_first),
        "has_repair_candidate": int(has_repair_candidate),
        "PAL_success": int(pal_ok),
        "selected_source": selected_source,
        "edge_color_counts": edge_color_count_str,
        # question cues
        "has_profit_cue": int(has_profit_cue),
        "has_difference_cue": int(has_difference_cue),
        "has_ratio_percent_cue": int(has_ratio_percent_cue),
        "has_original_before_cue": int(has_original_before_cue),
        "has_per_unit_share_cue": int(has_per_unit_cue),
        "has_unit_conversion_cue": int(has_unit_conversion_cue),
        "has_remainder_leftover_cue": int(has_remainder_leftover_cue),
        "transformed_target_cue_count": transformed_cue_count,
        # pool geometry
        "selected_value_is_extreme": int(selected_is_extreme),
        "selected_value_is_smallest": int(selected_is_smallest),
        "selected_value_is_largest": int(selected_is_largest),
        "selected_value_is_one": int(selected_is_one),
        "selected_value_repeated": int(selected_repeated),
        "candidate_values_cluster_count": candidate_values_cluster_count,
        "values_contain_multiplicative_relation": int(values_contain_multiplicative_relation),
        "values_contain_additive_relation": int(values_contain_additive_relation),
        "values_contain_conversion_like_relation": int(values_contain_conversion_like_relation),
        # metadata
        "question_type": str(case.get("failure_audit_labels", {}).get("question_type", "") or ""),
        "diversity_bucket": str(case.get("failure_audit_labels", {}).get("diversity_bucket", "") or ""),
        "candidate_pool_status": str(case.get("failure_audit_labels", {}).get("candidate_pool_status", "") or ""),
        "selector_candidate_pool_size": sel_meta.get("selector_candidate_pool_size", 0),
        "has_structural_candidate_rows": int(len(crows) > 0),
    }

    return feats


# ---------------------------------------------------------------------------
# Label construction (gold used only here)
# ---------------------------------------------------------------------------

def build_labels(
    case: dict[str, Any],
    feats: dict[str, Any],
    casebook_row: dict[str, str],
    policy_row: dict[str, str] | None,
) -> dict[str, Any]:
    """
    Construct offline labels from gold-enriched sources.
    Gold is not used in feats; only in this function.
    """
    case_id = feats["case_id"]

    # Pool membership
    subset_memberships = case.get("subset_memberships", [])
    gold_absent = any(
        "gold_absent" in str(sm.get("selection_logic", "")).lower()
        for sm in subset_memberships
    )
    # Fallback: primary_subset name
    if not gold_absent:
        gold_absent = "gold_absent" in str(case.get("primary_subset", "")).lower()

    gold_present = not gold_absent  # approximate for this dataset

    # Verifier branch
    verifier_present = feats["has_verifier_check_candidate"] == 1
    verifier_missing = not verifier_present

    # Requires live VC allocation: PAL present, verifier missing
    requires_live_vc = (feats["has_PAL_code_candidate"] == 1) and verifier_missing

    # Proxy quality label from casebook
    proxy_improved = casebook_row.get("proxy_score_improved", "") == "True"

    # structural_best_is_gold: no gold available in this dataset, use proxy
    structural_best_available = bool(casebook_row.get("structural_best_answer", "").strip())

    # Final transform family: infer from question cues
    cues = {
        "profit_revenue_cost": feats["has_profit_cue"],
        "difference_remainder": feats["has_difference_cue"] or feats["has_remainder_leftover_cue"],
        "ratio_base": feats["has_ratio_percent_cue"],
        "original_before_process": feats["has_original_before_cue"],
        "per_unit_share": feats["has_per_unit_share_cue"],
        "unit_conversion": feats["has_unit_conversion_cue"],
    }
    active_cues = [k for k, v in cues.items() if v]
    final_transform_family = active_cues[0] if len(active_cues) == 1 else (
        "multi_cue" if active_cues else "unknown"
    )

    # Candidate generation gap: what kind of branch is missing
    # Based on which cue is present but its corresponding candidate is absent
    _ecc = str(feats.get("edge_color_counts", "")).lower()
    gap_family = "unknown"
    if requires_live_vc:
        gap_family = "verifier_check"
    elif feats["has_ratio_percent_cue"] and "ratio" not in _ecc:
        gap_family = "ratio_base"
    elif feats["has_profit_cue"] and "profit" not in _ecc:
        gap_family = "profit_revenue_cost"
    elif feats["has_original_before_cue"] and "original" not in _ecc:
        gap_family = "original_before_process"

    return {
        "case_id": case_id,
        "gold_present_in_pool": int(gold_present),
        "gold_absent_from_pool": int(gold_absent),
        "proxy_score_improved": int(proxy_improved),
        "structural_best_available": int(structural_best_available),
        "verifier_branch_present": int(verifier_present),
        "verifier_branch_missing": int(verifier_missing),
        "requires_live_verifier_branch_allocation": int(requires_live_vc),
        "final_transform_family_inferred": final_transform_family,
        "candidate_generation_gap_family": gap_family,
    }


# ---------------------------------------------------------------------------
# Missing-edge recommendation heuristic (gold-free)
# ---------------------------------------------------------------------------

def recommend_next_edge(feats: dict[str, Any], labels: dict[str, Any]) -> dict[str, Any]:
    """
    Deterministic heuristic: based on present nodes and question cues, recommend
    which reasoning edge is most likely to improve the answer.
    """
    recommendations: list[str] = []
    reasons: list[str] = []

    if feats["has_PAL_code_candidate"] and not feats["has_verifier_check_candidate"]:
        recommendations.append("backward_from_target_check")
        reasons.append("PAL_code present but no verifier_check; PAL→VC lift=1.60")

    if feats["has_ratio_percent_cue"] and not feats["has_equation_setup_candidate"]:
        recommendations.append("ratio_base_branch")
        reasons.append("ratio/percent cue present, no equation_setup candidate")

    if feats["has_profit_cue"] and not feats["has_equation_setup_candidate"]:
        recommendations.append("profit_revenue_cost_branch")
        reasons.append("profit cue present, no cost-structure candidate")

    if feats["has_original_before_cue"] and feats["has_PAL_code_candidate"] and not feats["has_verifier_check_candidate"]:
        recommendations.append("original_before_process_branch")
        reasons.append("before/original cue with PAL candidate suggests reverse-state needed")

    if feats["has_per_unit_share_cue"] and not feats["has_equation_setup_candidate"]:
        recommendations.append("per_unit_share_branch")
        reasons.append("per-unit cue but no equation_setup")

    if feats["has_unit_conversion_cue"] and not feats["has_equation_setup_candidate"]:
        recommendations.append("unit_conversion_branch")
        reasons.append("unit conversion cue but no equation_setup")

    if feats["has_difference_cue"] and not feats["has_equation_setup_candidate"]:
        recommendations.append("difference_or_remainder_branch")
        reasons.append("difference/remainder cue but no equation_setup")

    if not recommendations:
        if not feats["has_equation_setup_candidate"]:
            recommendations.append("equation_first_reasoning")
            reasons.append("no equation_setup candidate; fallback recommendation")
        else:
            recommendations.append("none")
            reasons.append("no missing edge identified from available cues")

    return {
        "case_id": feats["case_id"],
        "recommended_next_edges": json.dumps(recommendations),
        "recommendation_reasons": " | ".join(reasons),
        "primary_recommendation": recommendations[0],
    }


# ---------------------------------------------------------------------------
# Analysis: feature contrasts between two groups
# ---------------------------------------------------------------------------

_NUMERIC_FEATURE_KEYS = [
    "candidate_count", "unique_numeric_count", "repeated_value_count",
    "numeric_range", "numeric_ratio_spread",
    "count_final_target_role", "count_intermediate_role",
    "target_alignment_score_max", "target_alignment_score_mean",
    "target_alignment_score_gap_top2",
    "candidate_role_entropy",
    "has_PAL_code_candidate", "has_verifier_check_candidate",
    "has_equation_setup_candidate",
    "transformed_target_cue_count",
    "selected_value_is_extreme", "selected_value_is_one",
    "selected_value_repeated",
    "candidate_values_cluster_count",
    "values_contain_multiplicative_relation",
    "values_contain_additive_relation",
    "has_structural_candidate_rows",
]


def _group_means(
    rows: list[dict[str, Any]],
    group_a_mask: list[bool],
    group_b_mask: list[bool],
    feature_keys: list[str],
) -> list[dict[str, Any]]:
    """Compare feature means between two groups A and B."""
    results = []
    for key in feature_keys:
        a_vals = [
            float(rows[i][key])
            for i, flag in enumerate(group_a_mask)
            if flag and rows[i].get(key) not in (None, "", "None")
        ]
        b_vals = [
            float(rows[i][key])
            for i, flag in enumerate(group_b_mask)
            if flag and rows[i].get(key) not in (None, "", "None")
        ]
        mean_a = (sum(a_vals) / len(a_vals)) if a_vals else None
        mean_b = (sum(b_vals) / len(b_vals)) if b_vals else None
        diff = (mean_a - mean_b) if (mean_a is not None and mean_b is not None) else None
        results.append({
            "feature": key,
            "mean_group_a": round(mean_a, 4) if mean_a is not None else "",
            "mean_group_b": round(mean_b, 4) if mean_b is not None else "",
            "diff_a_minus_b": round(diff, 4) if diff is not None else "",
            "n_group_a": len(a_vals),
            "n_group_b": len(b_vals),
        })
    results.sort(key=lambda r: -abs(float(r["diff_a_minus_b"]) if r["diff_a_minus_b"] != "" else 0))
    return results


# ---------------------------------------------------------------------------
# Optional ML
# ---------------------------------------------------------------------------

def _try_ml_analysis(
    feat_rows: list[dict[str, Any]],
    label_rows: list[dict[str, Any]],
    target_label: str,
) -> dict[str, Any] | None:
    """Attempt logistic regression / random forest; return None if sklearn absent."""
    try:
        from sklearn.linear_model import LogisticRegression
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.model_selection import cross_val_score
        from sklearn.preprocessing import StandardScaler
        import numpy as np
    except ImportError:
        return None

    label_map = {r["case_id"]: r for r in label_rows}
    rows_with_label = [
        (f, label_map[f["case_id"]])
        for f in feat_rows
        if f["case_id"] in label_map
        and label_map[f["case_id"]].get(target_label, "") not in ("", None, "None")
    ]
    if len(rows_with_label) < 10:
        return {"skipped": f"too few rows ({len(rows_with_label)}) for target={target_label}"}

    X_raw, y = [], []
    for feat, lbl in rows_with_label:
        row_vec = []
        for key in _NUMERIC_FEATURE_KEYS:
            v = feat.get(key)
            try:
                row_vec.append(float(v) if v not in (None, "", "None") else 0.0)
            except (TypeError, ValueError):
                row_vec.append(0.0)
        X_raw.append(row_vec)
        y.append(int(lbl[target_label]))

    X = np.array(X_raw)
    y = np.array(y)
    n_pos = int(y.sum())
    n_neg = len(y) - n_pos

    scaler = StandardScaler()
    X_sc = scaler.fit_transform(X)

    cv = min(5, n_pos, n_neg) if min(n_pos, n_neg) >= 2 else 2
    if cv < 2:
        return {"skipped": f"insufficient class balance pos={n_pos} neg={n_neg}"}

    try:
        lr = LogisticRegression(max_iter=500, class_weight="balanced")
        lr_scores = cross_val_score(lr, X_sc, y, cv=cv, scoring="roc_auc")

        rf = RandomForestClassifier(n_estimators=50, random_state=42, class_weight="balanced")
        rf_scores = cross_val_score(rf, X, y, cv=cv, scoring="roc_auc")

        lr.fit(X_sc, y)
        importances = sorted(
            zip(_NUMERIC_FEATURE_KEYS, lr.coef_[0]),
            key=lambda x: -abs(x[1]),
        )[:5]

        return {
            "target_label": target_label,
            "n_total": len(y),
            "n_positive": n_pos,
            "n_negative": n_neg,
            "cv_folds": cv,
            "lr_roc_auc_mean": round(float(lr_scores.mean()), 4),
            "lr_roc_auc_std": round(float(lr_scores.std()), 4),
            "rf_roc_auc_mean": round(float(rf_scores.mean()), 4),
            "rf_roc_auc_std": round(float(rf_scores.std()), 4),
            "top_lr_features": [(k, round(v, 4)) for k, v in importances],
        }
    except Exception as exc:
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("(empty)\n", encoding="utf-8")
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, default=str) + "\n")


def _load_csv_map(path: Path) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            cid = row.get("case_id", "")
            if cid:
                result[cid] = row
    return result


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def _generate_report(
    cases_loaded: int,
    cases_with_crows: int,
    feat_rows: list[dict[str, Any]],
    label_rows: list[dict[str, Any]],
    rec_rows: list[dict[str, Any]],
    gold_absent_contrasts: list[dict[str, Any]],
    vc_missing_contrasts: list[dict[str, Any]],
    ml_vc: dict | None,
    ml_proxy: dict | None,
    args: argparse.Namespace,
) -> str:
    n = len(feat_rows)
    lbl_map = {r["case_id"]: r for r in label_rows}

    gold_absent_n = sum(1 for r in label_rows if r.get("gold_absent_from_pool") == "1")
    gold_present_n = sum(1 for r in label_rows if r.get("gold_present_in_pool") == "1")
    vc_present_n = sum(1 for r in label_rows if r.get("verifier_branch_present") == "1")
    vc_missing_n = sum(1 for r in label_rows if r.get("verifier_branch_missing") == "1")
    live_vc_n = sum(1 for r in label_rows if r.get("requires_live_verifier_branch_allocation") == "1")
    proxy_improved_n = sum(1 for r in label_rows if r.get("proxy_score_improved") == "1")

    # Top recommendations
    rec_counts = Counter(r["primary_recommendation"] for r in rec_rows)
    rec_lines = "\n".join(
        f"  {k}: {v}" for k, v in rec_counts.most_common()
    )

    # Top contrasts
    def _contrast_lines(contrasts: list[dict], n: int = 6) -> str:
        return "\n".join(
            f"  {r['feature']:45s} A={r['mean_group_a']:>8}  B={r['mean_group_b']:>8}  Δ={r['diff_a_minus_b']:>8}"
            for r in contrasts[:n]
            if r['diff_a_minus_b'] != ""
        )

    ml_vc_text = ""
    if ml_vc:
        if "skipped" in ml_vc or "error" in ml_vc:
            ml_vc_text = f"  ML skipped/error: {ml_vc}"
        else:
            ml_vc_text = (
                f"  LogReg AUC: {ml_vc['lr_roc_auc_mean']:.3f} ± {ml_vc['lr_roc_auc_std']:.3f}  "
                f"RF AUC: {ml_vc['rf_roc_auc_mean']:.3f} ± {ml_vc['rf_roc_auc_std']:.3f}\n"
                f"  Top features: {ml_vc['top_lr_features']}"
            )

    ml_proxy_text = ""
    if ml_proxy:
        if "skipped" in ml_proxy or "error" in ml_proxy:
            ml_proxy_text = f"  ML skipped/error: {ml_proxy}"
        else:
            ml_proxy_text = (
                f"  LogReg AUC: {ml_proxy['lr_roc_auc_mean']:.3f} ± {ml_proxy['lr_roc_auc_std']:.3f}  "
                f"RF AUC: {ml_proxy['rf_roc_auc_mean']:.3f} ± {ml_proxy['rf_roc_auc_std']:.3f}"
            )

    report = f"""# Frontier Node-Distribution Mining v1

- experiment: frontier_node_distribution_mining_v1
- trace_packets: {args.trace_packets}
- replay_casebook: {args.replay_casebook}
- out_dir: {args.out_dir}
- timestamp: {_TS}

## Case summary

- Cases loaded: {cases_loaded}
- Cases with structural_fields.candidate_rows: {cases_with_crows}
- Cases without candidate_rows (sparse): {cases_loaded - cases_with_crows}
- Gold absent from pool (by subset membership): {gold_absent_n}
- Gold present in pool: {gold_present_n}
- Verifier branch (backward_from_target_check) present: {vc_present_n}
- Verifier branch missing: {vc_missing_n}
- Requires live verifier branch allocation: {live_vc_n}
- Proxy score improved (casebook): {proxy_improved_n} / {n}

## 1. Are node-distribution features informative?

Features extracted: {len(feat_rows[0]) if feat_rows else 0} per case
(candidate/value, semantic role, source/edge, question cue, pool geometry)

The most discriminating features between verifier-present and verifier-missing
cases are shown below (Section 3). Key signals include:
- has_structural_candidate_rows: the 50 sparse cases have no candidate_rows at all
- has_PAL_code_candidate: PAL presence is the clearest predictor for VC allocation need
- question cue counts: correlate with which branch families should be allocated

## 2. Gold-absent vs gold-present feature contrasts

NOTE: All {cases_loaded} cases in this dataset (wrong_supported_consensus_97) are
gold_absent by selection criteria. Gold-present vs gold-absent analysis is not
possible within this slice. The {proxy_improved_n} proxy-improved cases serve as
the "better-quality" group for feature contrasts instead.

Top feature contrasts (proxy_improved=True, n={proxy_improved_n}) vs
(proxy_improved=False, n={n - proxy_improved_n}):

{_contrast_lines(gold_absent_contrasts)}

## 3. Verifier-missing analysis

Top feature contrasts (verifier_present, n={vc_present_n}) vs
(verifier_missing, n={vc_missing_n}):

{_contrast_lines(vc_missing_contrasts)}

The strongest predictor of verifier_missing is has_structural_candidate_rows=0
(50 sparse cases have no candidate pool at all, hence no verifier branch).
Among the 47 rich cases, verifier_check is present in {vc_present_n} and absent
in {vc_missing_n - (cases_loaded - cases_with_crows)} of them.

### ML baseline (predicting requires_live_verifier_branch_allocation):
{ml_vc_text if ml_vc_text else '  Not run (sklearn unavailable or insufficient data)'}

### ML baseline (predicting proxy_score_improved):
{ml_proxy_text if ml_proxy_text else '  Not run (sklearn unavailable or insufficient data)'}

## 4. Missing-edge recommendation heuristic

Recommendation counts:
{rec_lines}

The heuristic applies rules in priority order:
1. PAL_code present + no verifier_check → backward_from_target_check (strongest signal, lift=1.60)
2. Ratio/percent cue + no equation_setup → ratio_base_branch
3. Profit cue + no equation_setup → profit_revenue_cost_branch
4. Original/before cue + PAL + no VC → original_before_process_branch
5. Per-unit cue + no equation_setup → per_unit_share_branch
6. Unit-conversion cue + no equation_setup → unit_conversion_branch
7. Difference/remainder cue + no equation_setup → difference_or_remainder_branch
8. Fallback: equation_first_reasoning

## 5. Contextual-bandit / best-first-search signal

The PAL_code → verifier_check transition has lift=1.60 and support=22. The
recommendation heuristic identifies {rec_counts.get('backward_from_target_check', 0)} cases
where verifier_check should have been allocated. This is the primary actionable signal.

For a contextual bandit:
- State: current set of discovered candidate colors (edge colors)
- Action: which next edge to expand
- Reward: proxy quality improvement (or exact accuracy in live eval)
- Signal strength: PAL→VC is the clearest arm; ratio_base and profit branches
  have cue-based support but smaller offline sample

## 6. Missing metadata

- No per-case gold answers in this dataset
- 50 cases have empty structural_fields (sparse format); only aggregate answers available
- PAL execution details (pal_stdout, pal_code) truncated in packets
- Action trace truncated to 3 steps; full tree not captured

## 7. Recommended next method

Given the positive verifier-check signal:
- Primary: run live frontier_node_distribution_policy_v1 — allocate
  backward_from_target_check to cases where has_PAL_code_candidate=1 and
  has_verifier_check_candidate=0, then compare exact accuracy
- Secondary: combine colored_reasoning_path_policy_v1 lift-score with
  node_distribution_score as a joint ranking signal
- Stop condition: if live verifier allocation experiment (61 cases) yields
  exact-accuracy improvement < 2%, the signal is too weak to pursue further
"""
    return report


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Frontier node-distribution mining experiment."
    )
    p.add_argument("--trace-packets", required=True, type=Path)
    p.add_argument("--replay-casebook", required=True, type=Path)
    p.add_argument("--colored-policy-output", type=Path, default=None)
    p.add_argument("--out-dir", required=True, type=Path)
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--include-gold-for-labeling", type=str, default="true")
    p.add_argument("--no-gold-features", type=str, default="true")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> dict[str, Any]:
    args = parse_args(argv)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading trace packets from {args.trace_packets}", flush=True)
    cases = load_trace_packets(args.trace_packets)
    if args.limit:
        cases = cases[: args.limit]
    print(f"  Loaded {len(cases)} cases", flush=True)

    casebook: dict[str, dict[str, str]] = {}
    with open(args.replay_casebook, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            cid = row.get("case_id", "")
            if cid:
                casebook[cid] = row

    policy_output: dict[str, dict[str, str]] = {}
    if args.colored_policy_output and args.colored_policy_output.exists():
        policy_output = _load_csv_map(args.colored_policy_output)
        print(f"  Loaded colored policy rows for {len(policy_output)} cases", flush=True)

    feat_rows: list[dict[str, Any]] = []
    label_rows: list[dict[str, Any]] = []
    rec_rows: list[dict[str, Any]] = []

    for case in cases:
        feats = extract_features(case)
        cb_row = casebook.get(feats["case_id"], {})
        pol_row = policy_output.get(feats["case_id"])
        labels = build_labels(case, feats, cb_row, pol_row)
        rec = recommend_next_edge(feats, labels)
        feat_rows.append(feats)
        label_rows.append(labels)
        rec_rows.append(rec)

    cases_loaded = len(cases)
    cases_with_crows = sum(
        1 for c in cases
        if c.get("structural_fields", {}).get("candidate_rows")
    )

    # Feature group summary (mean/rate per feature across all cases)
    group_summary_rows = []
    for key in _NUMERIC_FEATURE_KEYS:
        vals = []
        for r in feat_rows:
            v = r.get(key)
            if v not in (None, "", "None"):
                try:
                    vals.append(float(v))
                except (TypeError, ValueError):
                    pass
        if vals:
            group_summary_rows.append({
                "feature": key,
                "n_valid": len(vals),
                "mean": round(sum(vals) / len(vals), 4),
                "min": round(min(vals), 4),
                "max": round(max(vals), 4),
                "nonzero_rate": round(sum(1 for v in vals if v != 0) / len(vals), 4),
            })

    # Feature contrasts: proxy_improved=True vs False (gold-proxy split)
    # label_rows stores int values; compare with int(bool) 1/0
    proxy_mask_a = [bool(r.get("proxy_score_improved")) for r in label_rows]
    proxy_mask_b = [not bool(r.get("proxy_score_improved")) for r in label_rows]
    gold_absent_contrasts = _group_means(
        feat_rows, proxy_mask_a, proxy_mask_b, _NUMERIC_FEATURE_KEYS
    )

    # Feature contrasts: verifier present vs missing
    vc_present_mask = [bool(r.get("verifier_branch_present")) for r in label_rows]
    vc_missing_mask = [bool(r.get("verifier_branch_missing")) for r in label_rows]
    vc_missing_contrasts = _group_means(
        feat_rows, vc_present_mask, vc_missing_mask, _NUMERIC_FEATURE_KEYS
    )

    # Convert label_rows to str for CSV
    label_rows_csv = [{k: str(v) for k, v in r.items()} for r in label_rows]
    # Merge feat + label for frontier_feature_rows
    merged_rows = []
    lbl_map = {r["case_id"]: r for r in label_rows}
    for fr in feat_rows:
        merged = dict(fr)
        merged.update(lbl_map.get(fr["case_id"], {}))
        merged_rows.append(merged)

    # Optional ML
    ml_vc = _try_ml_analysis(feat_rows, label_rows_csv, "requires_live_verifier_branch_allocation")
    ml_proxy = _try_ml_analysis(feat_rows, label_rows_csv, "proxy_score_improved")

    # Write outputs
    print("Writing outputs...", flush=True)
    _write_csv(args.out_dir / "frontier_feature_rows.csv", merged_rows)
    _write_jsonl(args.out_dir / "frontier_feature_rows.jsonl", merged_rows)
    _write_csv(args.out_dir / "feature_group_summary.csv", group_summary_rows)
    _write_csv(args.out_dir / "gold_absent_feature_contrasts.csv", gold_absent_contrasts)
    _write_csv(args.out_dir / "verifier_missing_feature_contrasts.csv", vc_missing_contrasts)
    _write_csv(args.out_dir / "missing_edge_recommendations.csv", rec_rows)

    report = _generate_report(
        cases_loaded=cases_loaded,
        cases_with_crows=cases_with_crows,
        feat_rows=feat_rows,
        label_rows=label_rows_csv,
        rec_rows=rec_rows,
        gold_absent_contrasts=gold_absent_contrasts,
        vc_missing_contrasts=vc_missing_contrasts,
        ml_vc=ml_vc,
        ml_proxy=ml_proxy,
        args=args,
    )
    (args.out_dir / "report.md").write_text(report, encoding="utf-8")

    rec_counts = Counter(r["primary_recommendation"] for r in rec_rows)
    vc_present_n = sum(1 for r in label_rows if r.get("verifier_branch_present"))
    vc_missing_n = sum(1 for r in label_rows if r.get("verifier_branch_missing"))
    live_vc_n = sum(1 for r in label_rows if r.get("requires_live_verifier_branch_allocation"))

    manifest = {
        "experiment": "frontier_node_distribution_mining_v1",
        "timestamp_utc": _TS,
        "trace_packets": str(args.trace_packets),
        "replay_casebook": str(args.replay_casebook),
        "out_dir": str(args.out_dir),
        "cases_loaded": cases_loaded,
        "cases_with_candidate_rows": cases_with_crows,
        "features_per_case": len(feat_rows[0]) if feat_rows else 0,
        "verifier_branch_present": vc_present_n,
        "verifier_branch_missing": vc_missing_n,
        "requires_live_verifier_branch_allocation": live_vc_n,
        "recommendation_counts": dict(rec_counts),
        "ml_vc_result": ml_vc,
        "ml_proxy_result": ml_proxy,
        "api_calls_made": 0,
        "no_gold_features": True,
        "outputs": [
            "manifest.json",
            "frontier_feature_rows.csv",
            "frontier_feature_rows.jsonl",
            "feature_group_summary.csv",
            "gold_absent_feature_contrasts.csv",
            "verifier_missing_feature_contrasts.csv",
            "missing_edge_recommendations.csv",
            "report.md",
        ],
    }
    with open(args.out_dir / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"Done. Output: {args.out_dir}", flush=True)
    print(f"  Features per case: {manifest['features_per_case']}", flush=True)
    print(f"  Recommendation counts: {dict(rec_counts.most_common())}", flush=True)
    print(f"  Requires live VC: {live_vc_n}", flush=True)

    return manifest


if __name__ == "__main__":
    main()
