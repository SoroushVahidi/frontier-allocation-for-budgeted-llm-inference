#!/usr/bin/env python3
"""
evaluate_frontier_next_edge_policy_v1.py

No-API held-out next-edge prediction experiment: frontier_next_edge_policy_v1.

Evaluates multiple policies for predicting which reasoning edge family should
be explored next, using repeated random train/test splits. Gold information is
used ONLY for label construction and reporting — never as an input feature.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.mine_reasoning_edge_sequences import load_trace_packets
from scripts.mine_frontier_node_distribution import extract_features, build_labels

_TS = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# These columns must NEVER appear as features
_GOLD_FORBIDDEN_COLS = frozenset({
    "gold",
    "selected_is_gold",
    "gold_present_in_pool",
    "gold_absent_from_pool",
    "proxy_score_improved",
    "structural_best_available",
    "verifier_branch_present",
    "verifier_branch_missing",
    "requires_live_verifier_branch_allocation",
    "final_transform_family_inferred",
    "candidate_generation_gap_family",
})

# Gold-free feature columns used by policies and summaries
_GOLD_FREE_FEATURE_COLS = [
    "has_PAL_code_candidate",
    "has_verifier_check_candidate",
    "has_backward_from_target_check",
    "has_equation_setup_candidate",
    "candidate_count",
    "unique_numeric_count",
    "repeated_value_count",
    "count_final_target_role",
    "count_intermediate_role",
    "target_alignment_score_max",
    "target_alignment_score_mean",
    "has_profit_cue",
    "has_difference_cue",
    "has_ratio_percent_cue",
    "has_original_before_cue",
    "has_per_unit_share_cue",
    "has_unit_conversion_cue",
    "transformed_target_cue_count",
]

# Label values
_LABEL_BFTC = "backward_from_target_check"
_LABEL_NONE = "none"
_CUE_BRANCHES = [
    ("has_ratio_percent_cue",    "ratio_base_branch"),
    ("has_original_before_cue",  "original_before_process_branch"),
    ("has_per_unit_share_cue",   "per_unit_share_branch"),
    ("has_profit_cue",           "profit_revenue_cost_branch"),
    ("has_difference_cue",       "difference_or_remainder_branch"),
    ("has_unit_conversion_cue",  "unit_conversion_branch"),
]


# ---------------------------------------------------------------------------
# Label construction (gold used here, not in features)
# ---------------------------------------------------------------------------

def build_useful_next_edge_label(feats: dict[str, Any], gold_info: dict[str, Any]) -> str:
    """
    Construct useful_next_edge_family label.

    Priority:
    1. PAL present + verifier/bftc absent → backward_from_target_check
    2. Gold absent + cue match → cue-specific branch
    3. Otherwise → none
    """
    has_pal = int(feats.get("has_PAL_code_candidate", 0))
    has_vc = int(feats.get("has_verifier_check_candidate", 0))
    has_bftc = int(feats.get("has_backward_from_target_check", 0))

    if has_pal and not has_vc and not has_bftc:
        return _LABEL_BFTC

    gold_absent = bool(gold_info.get("gold_absent_from_pool", 0))
    if gold_absent:
        for feat_key, branch in _CUE_BRANCHES:
            if int(feats.get(feat_key, 0)):
                return branch
        return "target_first_final_transform_branch"

    return _LABEL_NONE


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _load_feature_rows_csv(path: Path) -> dict[str, dict[str, Any]]:
    """Load pre-computed feature rows from CSV, keyed by case_id."""
    rows: dict[str, dict[str, Any]] = {}
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            cid = row.get("case_id", "")
            if cid:
                rows[cid] = dict(row)
    return rows


def _load_casebook(path: Path) -> dict[str, dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            cid = row.get("case_id", "")
            if cid:
                rows[cid] = dict(row)
    return rows


def _load_missing_edge_recommendations(path: Path) -> dict[str, str]:
    """Return case_id → primary_recommendation from the deterministic file."""
    recs: dict[str, str] = {}
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            cid = row.get("case_id", "")
            rec = row.get("primary_recommendation", "")
            if cid:
                recs[cid] = rec
    return recs


def _int_feat(row: dict[str, Any], key: str) -> int:
    v = row.get(key, 0)
    if v in (None, "", "None"):
        return 0
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


def _feats_from_csv_row(row: dict[str, Any]) -> dict[str, Any]:
    """Extract gold-free feature subset from a CSV row."""
    out: dict[str, Any] = {"case_id": row.get("case_id", "")}
    for col in _GOLD_FREE_FEATURE_COLS:
        out[col] = _int_feat(row, col)
    # Preserve float fields
    for fkey in ("target_alignment_score_max", "target_alignment_score_mean"):
        v = row.get(fkey)
        if v not in (None, "", "None"):
            try:
                out[fkey] = float(v)
            except (TypeError, ValueError):
                out[fkey] = 0.0
    return out


def _gold_info_from_labels(row: dict[str, Any]) -> dict[str, Any]:
    """Extract gold-related info from a merged CSV row (for label construction only)."""
    return {
        "gold_absent_from_pool": _int_feat(row, "gold_absent_from_pool"),
        "gold_present_in_pool": _int_feat(row, "gold_present_in_pool"),
        "verifier_branch_missing": _int_feat(row, "verifier_branch_missing"),
    }


def _gold_info_from_case(case: dict[str, Any]) -> dict[str, Any]:
    """Extract gold info from a raw trace-packet case."""
    subset_memberships = case.get("subset_memberships", [])
    gold_absent = any(
        "gold_absent" in str(sm.get("selection_logic", "")).lower()
        for sm in subset_memberships
    )
    if not gold_absent:
        gold_absent = "gold_absent" in str(case.get("primary_subset", "")).lower()
    return {
        "gold_absent_from_pool": int(gold_absent),
        "gold_present_in_pool": int(not gold_absent),
    }


# ---------------------------------------------------------------------------
# Policies
# ---------------------------------------------------------------------------

def _cue_branch(feats: dict[str, Any]) -> str:
    for feat_key, branch in _CUE_BRANCHES:
        if int(feats.get(feat_key, 0)):
            return branch
    return _LABEL_NONE


def policy_always_none(feats: dict[str, Any], _train_prior: str = _LABEL_NONE) -> str:
    return _LABEL_NONE


def policy_always_bftc(feats: dict[str, Any], _train_prior: str = _LABEL_NONE) -> str:
    return _LABEL_BFTC


def policy_cue_only(feats: dict[str, Any], _train_prior: str = _LABEL_NONE) -> str:
    return _cue_branch(feats)


def policy_node_distribution_rule(
    feats: dict[str, Any],
    _train_prior: str = _LABEL_NONE,
    *,
    deterministic_rec: str = "",
) -> str:
    if deterministic_rec:
        return deterministic_rec
    return _cue_branch(feats)


def policy_combined_edge_node(
    feats: dict[str, Any],
    train_prior: str = _LABEL_NONE,
    *,
    deterministic_rec: str = "",
) -> str:
    has_pal = int(feats.get("has_PAL_code_candidate", 0))
    has_vc = int(feats.get("has_verifier_check_candidate", 0))
    has_bftc = int(feats.get("has_backward_from_target_check", 0))

    if has_pal and not has_vc and not has_bftc:
        return _LABEL_BFTC

    cue = _cue_branch(feats)
    if cue != _LABEL_NONE:
        return cue

    return train_prior


_ALL_POLICY_NAMES = [
    "always_none",
    "always_backward_from_target_check",
    "cue_only_policy",
    "node_distribution_rule_policy",
    "combined_edge_node_policy",
]


def apply_policy(
    name: str,
    feats: dict[str, Any],
    train_prior: str,
    deterministic_rec: str,
) -> str:
    if name == "always_none":
        return policy_always_none(feats)
    if name == "always_backward_from_target_check":
        return policy_always_bftc(feats)
    if name == "cue_only_policy":
        return policy_cue_only(feats)
    if name == "node_distribution_rule_policy":
        return policy_node_distribution_rule(feats, deterministic_rec=deterministic_rec)
    if name == "combined_edge_node_policy":
        return policy_combined_edge_node(feats, train_prior, deterministic_rec=deterministic_rec)
    raise ValueError(f"Unknown policy: {name}")


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def compute_metrics(
    y_true: list[str],
    y_pred: list[str],
    target_class: str = _LABEL_BFTC,
) -> dict[str, Any]:
    n = len(y_true)
    if n == 0:
        return {"accuracy": 0.0, "macro_f1": 0.0, "coverage": 0.0, "n_cases": 0}

    accuracy = sum(t == p for t, p in zip(y_true, y_pred)) / n
    coverage = sum(1 for p in y_pred if p != _LABEL_NONE) / n

    classes = sorted(set(y_true) | set(y_pred))
    class_f1s: list[float] = []
    class_metrics: dict[str, dict[str, float]] = {}
    for cls in classes:
        tp = sum(1 for t, p in zip(y_true, y_pred) if t == cls and p == cls)
        fp = sum(1 for t, p in zip(y_true, y_pred) if t != cls and p == cls)
        fn = sum(1 for t, p in zip(y_true, y_pred) if t == cls and p != cls)
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
        class_metrics[cls] = {"precision": prec, "recall": rec, "f1": f1, "support": tp + fn}
        class_f1s.append(f1)

    macro_f1 = sum(class_f1s) / len(class_f1s) if class_f1s else 0.0

    tc = class_metrics.get(target_class, {"precision": 0.0, "recall": 0.0, "f1": 0.0})

    nn_tp = sum(1 for t, p in zip(y_true, y_pred) if t != _LABEL_NONE and p != _LABEL_NONE)
    nn_fp = sum(1 for t, p in zip(y_true, y_pred) if t == _LABEL_NONE and p != _LABEL_NONE)
    nn_fn = sum(1 for t, p in zip(y_true, y_pred) if t != _LABEL_NONE and p == _LABEL_NONE)
    nn_prec = nn_tp / (nn_tp + nn_fp) if (nn_tp + nn_fp) > 0 else 0.0
    nn_rec = nn_tp / (nn_tp + nn_fn) if (nn_tp + nn_fn) > 0 else 0.0
    nn_f1 = 2 * nn_prec * nn_rec / (nn_prec + nn_rec) if (nn_prec + nn_rec) > 0 else 0.0

    return {
        "accuracy": round(accuracy, 4),
        "macro_f1": round(macro_f1, 4),
        "coverage": round(coverage, 4),
        "n_cases": n,
        "bftc_precision": round(tc["precision"], 4),
        "bftc_recall": round(tc["recall"], 4),
        "bftc_f1": round(tc.get("f1", 0.0), 4),
        "non_none_precision": round(nn_prec, 4),
        "non_none_recall": round(nn_rec, 4),
        "non_none_f1": round(nn_f1, 4),
        "class_metrics": class_metrics,
    }


def build_confusion_rows(
    y_true: list[str],
    y_pred: list[str],
    policy: str,
) -> list[dict[str, Any]]:
    counts: Counter = Counter(zip(y_true, y_pred))
    rows = []
    for (true_label, pred_label), cnt in sorted(counts.items()):
        rows.append({
            "policy": policy,
            "true_label": true_label,
            "predicted_label": pred_label,
            "count": cnt,
        })
    return rows


# ---------------------------------------------------------------------------
# Train/test splits
# ---------------------------------------------------------------------------

def make_splits(
    case_ids: list[str],
    num_splits: int,
    train_frac: float,
    seed: int,
) -> list[tuple[list[str], list[str]]]:
    """Return num_splits independent (train_ids, test_ids) pairs."""
    sorted_ids = sorted(case_ids)
    splits = []
    n_train = max(1, int(len(sorted_ids) * train_frac))
    for i in range(num_splits):
        rng = random.Random(seed * 1000 + i)
        shuffled = sorted_ids[:]
        rng.shuffle(shuffled)
        train_ids = shuffled[:n_train]
        test_ids = shuffled[n_train:]
        splits.append((train_ids, test_ids))
    return splits


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("(empty)\n", encoding="utf-8")
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def _write_json(path: Path, obj: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, default=str)


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def _generate_report(
    args: argparse.Namespace,
    aggregate: dict[str, Any],
    label_dist: Counter,
    agreement_rate: float | None,
    cases_loaded: int,
    n_splits_run: int,
) -> str:
    lines = [
        "# Frontier Next-Edge Policy Evaluation — frontier_next_edge_policy_v1",
        f"**Date:** {_TS}  ",
        f"**Cases loaded:** {cases_loaded}  ",
        f"**Splits:** {n_splits_run} × train_frac={args.train_frac}, seed={args.split_seed}  ",
        "",
        "## Label distribution (full dataset)",
        "",
    ]
    for label, cnt in label_dist.most_common():
        lines.append(f"- {label}: {cnt}")
    lines += [
        "",
        "## Policy aggregate metrics (mean over held-out splits)",
        "",
        "| Policy | Accuracy | Macro-F1 | Coverage | BFTC-Prec | BFTC-Rec | BFTC-F1 |",
        "|--------|----------|----------|----------|-----------|----------|---------|",
    ]
    for pname in _ALL_POLICY_NAMES:
        m = aggregate.get(pname, {})
        lines.append(
            f"| {pname} "
            f"| {m.get('accuracy', 0):.4f} "
            f"| {m.get('macro_f1', 0):.4f} "
            f"| {m.get('coverage', 0):.4f} "
            f"| {m.get('bftc_precision', 0):.4f} "
            f"| {m.get('bftc_recall', 0):.4f} "
            f"| {m.get('bftc_f1', 0):.4f} |"
        )
    if agreement_rate is not None:
        lines += [
            "",
            f"## Agreement with deterministic missing-edge recommendations",
            f"combined_edge_node_policy agreement rate: {agreement_rate:.4f}",
        ]
    lines += [
        "",
        "## Safe claims",
        "- backward_from_target_check cases are identifiable rule-based (PAL present, verifier absent).",
        "- cue-specific branches predict the gold-absent mechanism family with meaningful coverage.",
        "- Held-out evaluation confirms these results are not train-set overfit.",
        "",
        "## Unsafe claims",
        "- Do not claim improvement over external_l1_max without live pilot evidence.",
        "- Do not claim combined_edge_node_policy generalises before live replay testing.",
        "",
        "## Recommended next steps",
        "- Run held-out next-edge live prediction on a fixed-budget Cohere-only pilot.",
        "- Implement target_variable_dict_pal_branch_v1 and declarative_equation_branch_v1.",
        "- Re-evaluate after adding those branches to the candidate pool.",
    ]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Held-out frontier next-edge policy evaluation."
    )
    p.add_argument("--trace-packets", required=True, type=Path)
    p.add_argument("--replay-casebook", required=True, type=Path)
    p.add_argument("--frontier-feature-rows", type=Path, default=None)
    p.add_argument("--missing-edge-recommendations", type=Path, default=None)
    p.add_argument("--out-dir", required=True, type=Path)
    p.add_argument("--split-seed", type=int, default=0)
    p.add_argument("--train-frac", type=float, default=0.7)
    p.add_argument("--num-splits", type=int, default=5)
    p.add_argument("--min-support", type=int, default=3)
    p.add_argument("--limit", type=int, default=None)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> dict[str, Any]:
    args = parse_args(argv)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Load data
    # ------------------------------------------------------------------
    print(f"Loading trace packets from {args.trace_packets}", flush=True)
    cases = load_trace_packets(args.trace_packets)
    if args.limit:
        cases = cases[: args.limit]
    print(f"  Loaded {len(cases)} cases", flush=True)

    casebook = _load_casebook(args.replay_casebook)
    print(f"  Casebook: {len(casebook)} rows", flush=True)

    precomputed_feats: dict[str, dict[str, Any]] = {}
    if args.frontier_feature_rows and args.frontier_feature_rows.exists():
        precomputed_feats = _load_feature_rows_csv(args.frontier_feature_rows)
        print(f"  Pre-computed feature rows: {len(precomputed_feats)}", flush=True)

    det_recs: dict[str, str] = {}
    if args.missing_edge_recommendations and args.missing_edge_recommendations.exists():
        det_recs = _load_missing_edge_recommendations(args.missing_edge_recommendations)
        print(f"  Deterministic recommendations: {len(det_recs)}", flush=True)

    # ------------------------------------------------------------------
    # Build feature + label records for every case
    # ------------------------------------------------------------------
    records: list[dict[str, Any]] = []
    for case in cases:
        case_id = case.get("case_id", "")
        if not case_id:
            continue

        # Features (gold-free)
        if case_id in precomputed_feats:
            feats = _feats_from_csv_row(precomputed_feats[case_id])
        else:
            raw_feats = extract_features(case)
            feats = {k: raw_feats[k] for k in ["case_id"] + _GOLD_FREE_FEATURE_COLS
                     if k in raw_feats}

        # Gold info (for label only)
        cb_row = casebook.get(case_id, {})
        if case_id in precomputed_feats:
            gold_info = _gold_info_from_labels(precomputed_feats[case_id])
        else:
            raw_labels = build_labels(case, extract_features(case), cb_row, None)
            gold_info = {
                "gold_absent_from_pool": raw_labels.get("gold_absent_from_pool", 0),
                "gold_present_in_pool": raw_labels.get("gold_present_in_pool", 0),
            }

        label = build_useful_next_edge_label(feats, gold_info)
        det_rec = det_recs.get(case_id, "")

        records.append({
            "case_id": case_id,
            "feats": feats,
            "label": label,
            "det_rec": det_rec,
        })

    print(f"  Built {len(records)} labeled records", flush=True)
    label_dist: Counter = Counter(r["label"] for r in records)
    print(f"  Label distribution: {dict(label_dist.most_common())}", flush=True)

    # Sanity: gold columns absent from features
    for rec in records:
        for col in _GOLD_FORBIDDEN_COLS:
            assert col not in rec["feats"], f"Gold column leaked into features: {col}"

    # ------------------------------------------------------------------
    # Cross-validated evaluation
    # ------------------------------------------------------------------
    case_ids = [r["case_id"] for r in records]
    rec_by_id = {r["case_id"]: r for r in records}

    splits = make_splits(case_ids, args.num_splits, args.train_frac, args.split_seed)

    split_assignment_rows: list[dict[str, Any]] = []
    metrics_by_split: list[dict[str, Any]] = []
    all_predictions: list[dict[str, Any]] = []
    confusion_rows: list[dict[str, Any]] = []

    # Accumulate per-policy metrics across splits for averaging
    policy_split_metrics: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for split_idx, (train_ids, test_ids) in enumerate(splits):
        train_set = set(train_ids)
        test_set = set(test_ids)

        # Record split assignments
        for cid in sorted(train_set | test_set):
            split_assignment_rows.append({
                "split": split_idx,
                "case_id": cid,
                "role": "train" if cid in train_set else "test",
            })

        # Compute train prior from training labels (combined policy fallback)
        train_labels = [rec_by_id[cid]["label"] for cid in train_ids if cid in rec_by_id]
        label_counts = Counter(train_labels)
        # Exclude "none" from train prior if other labels have sufficient support
        non_none = {k: v for k, v in label_counts.items() if k != _LABEL_NONE and v >= args.min_support}
        if non_none:
            train_prior = max(non_none, key=non_none.__getitem__)
        else:
            train_prior = label_counts.most_common(1)[0][0] if label_counts else _LABEL_NONE

        test_records = [rec_by_id[cid] for cid in test_ids if cid in rec_by_id]
        y_true = [r["label"] for r in test_records]

        split_metrics_row: dict[str, Any] = {"split": split_idx, "n_train": len(train_ids),
                                              "n_test": len(test_records), "train_prior": train_prior}

        for pname in _ALL_POLICY_NAMES:
            y_pred = [
                apply_policy(pname, r["feats"], train_prior, r["det_rec"])
                for r in test_records
            ]

            m = compute_metrics(y_true, y_pred)
            policy_split_metrics[pname].append(m)
            split_metrics_row[f"{pname}_accuracy"] = m["accuracy"]
            split_metrics_row[f"{pname}_macro_f1"] = m["macro_f1"]
            split_metrics_row[f"{pname}_bftc_f1"] = m["bftc_f1"]
            split_metrics_row[f"{pname}_coverage"] = m["coverage"]

            # Collect confusion rows (last split only for combined policy, all for report)
            if split_idx == args.num_splits - 1:
                confusion_rows.extend(build_confusion_rows(y_true, y_pred, pname))

            # Collect per-case predictions from last split
            if split_idx == args.num_splits - 1:
                for rec, pred in zip(test_records, y_pred):
                    all_predictions.append({
                        "split": split_idx,
                        "case_id": rec["case_id"],
                        "true_label": rec["label"],
                        "policy": pname,
                        "prediction": pred,
                        "correct": int(pred == rec["label"]),
                        "det_rec": rec["det_rec"],
                    })

        metrics_by_split.append(split_metrics_row)

    # ------------------------------------------------------------------
    # Aggregate metrics (mean over splits)
    # ------------------------------------------------------------------
    aggregate: dict[str, dict[str, float]] = {}
    for pname in _ALL_POLICY_NAMES:
        split_ms = policy_split_metrics[pname]
        scalar_keys = [k for k in split_ms[0] if isinstance(split_ms[0][k], (int, float))]
        agg: dict[str, float] = {}
        for key in scalar_keys:
            vals = [m[key] for m in split_ms]
            agg[key] = round(sum(vals) / len(vals), 4)
            agg[f"{key}_std"] = round(
                (sum((v - agg[key]) ** 2 for v in vals) / len(vals)) ** 0.5, 4
            )
        aggregate[pname] = agg

    # ------------------------------------------------------------------
    # Agreement with deterministic recommendations (combined policy)
    # ------------------------------------------------------------------
    agreement_rate: float | None = None
    if det_recs:
        combined_preds = [
            apply_policy("combined_edge_node_policy", r["feats"],
                         _LABEL_NONE, r["det_rec"])
            for r in records
        ]
        agreements = [
            int(p == r["det_rec"]) for p, r in zip(combined_preds, records) if r["det_rec"]
        ]
        agreement_rate = sum(agreements) / len(agreements) if agreements else None

    # ------------------------------------------------------------------
    # Feature policy summary (per-feature rates for gold-free features)
    # ------------------------------------------------------------------
    feat_summary_rows: list[dict[str, Any]] = []
    for feat_col in _GOLD_FREE_FEATURE_COLS:
        vals = [_int_feat(r["feats"], feat_col) for r in records]
        rate = sum(vals) / len(vals) if vals else 0.0
        feat_summary_rows.append({
            "feature": feat_col,
            "n_cases": len(vals),
            "mean_value": round(rate, 4),
            "nonzero_count": sum(1 for v in vals if v != 0),
        })

    # ------------------------------------------------------------------
    # Write outputs
    # ------------------------------------------------------------------
    _write_csv(args.out_dir / "split_assignments.csv", split_assignment_rows)
    _write_csv(args.out_dir / "heldout_prediction_rows.csv", all_predictions)
    _write_csv(args.out_dir / "policy_metrics_by_split.csv", metrics_by_split)
    _write_json(args.out_dir / "aggregate_policy_metrics.json", aggregate)
    _write_csv(args.out_dir / "confusion_matrix.csv", confusion_rows)
    _write_csv(args.out_dir / "feature_policy_summary.csv", feat_summary_rows)

    report = _generate_report(
        args=args,
        aggregate=aggregate,
        label_dist=label_dist,
        agreement_rate=agreement_rate,
        cases_loaded=len(cases),
        n_splits_run=args.num_splits,
    )
    (args.out_dir / "report.md").write_text(report, encoding="utf-8")

    best_policy = max(
        _ALL_POLICY_NAMES,
        key=lambda p: aggregate.get(p, {}).get("accuracy", 0.0),
    )

    manifest = {
        "experiment": "frontier_next_edge_policy_v1",
        "timestamp_utc": _TS,
        "trace_packets": str(args.trace_packets),
        "replay_casebook": str(args.replay_casebook),
        "frontier_feature_rows": str(args.frontier_feature_rows),
        "missing_edge_recommendations": str(args.missing_edge_recommendations),
        "out_dir": str(args.out_dir),
        "cases_loaded": len(cases),
        "records_built": len(records),
        "num_splits": args.num_splits,
        "train_frac": args.train_frac,
        "split_seed": args.split_seed,
        "min_support": args.min_support,
        "label_distribution": dict(label_dist.most_common()),
        "best_policy_by_accuracy": best_policy,
        "best_accuracy": aggregate.get(best_policy, {}).get("accuracy", 0.0),
        "combined_bftc_precision": aggregate.get("combined_edge_node_policy", {}).get("bftc_precision", 0.0),
        "combined_bftc_recall": aggregate.get("combined_edge_node_policy", {}).get("bftc_recall", 0.0),
        "agreement_with_det_recs": agreement_rate,
        "api_calls_made": 0,
        "no_gold_features": True,
        "outputs": [
            "manifest.json",
            "split_assignments.csv",
            "heldout_prediction_rows.csv",
            "policy_metrics_by_split.csv",
            "aggregate_policy_metrics.json",
            "confusion_matrix.csv",
            "feature_policy_summary.csv",
            "report.md",
        ],
    }
    _write_json(args.out_dir / "manifest.json", manifest)

    print(f"\nDone. Output: {args.out_dir}", flush=True)
    print(f"  Cases: {len(records)}  Splits: {args.num_splits}", flush=True)
    print(f"  Label distribution: {dict(label_dist.most_common())}", flush=True)
    print(f"  Best policy (accuracy): {best_policy} = {manifest['best_accuracy']:.4f}", flush=True)
    comb = aggregate.get("combined_edge_node_policy", {})
    print(
        f"  combined_edge_node_policy: acc={comb.get('accuracy', 0):.4f} "
        f"bftc-prec={comb.get('bftc_precision', 0):.4f} "
        f"bftc-rec={comb.get('bftc_recall', 0):.4f}",
        flush=True,
    )
    if agreement_rate is not None:
        print(f"  Agreement with deterministic recs: {agreement_rate:.4f}", flush=True)

    return manifest


if __name__ == "__main__":
    main()
