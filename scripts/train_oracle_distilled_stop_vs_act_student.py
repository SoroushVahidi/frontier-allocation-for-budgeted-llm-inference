#!/usr/bin/env python3
"""Train/evaluate first oracle-distilled stop-vs-act student from distillation-ready rows.

This script is designed for post-pilot execution but can be smoke-tested on mock/test
rows in non-claim mode. It keeps the existing stop-vs-act model family and trains via
`fit_stop_vs_act_model` from `experiments.stop_vs_act_controller`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.stop_vs_act_controller import (  # noqa: E402
    STOP_VS_ACT_FEATURE_NAMES,
    evaluate_binary_predictions,
    fit_stop_vs_act_model,
    stop_vs_act_probability,
)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _stable_u01(key: str) -> float:
    dig = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return int(dig[:16], 16) / float(16**16)


def _parse_bucket_list(value: str) -> set[str]:
    out = {x.strip().lower() for x in value.split(",") if x.strip()}
    valid = {"accepted", "borderline", "rejected"}
    unknown = out - valid
    if unknown:
        raise ValueError(f"Unknown bucket(s): {sorted(unknown)}")
    return out


def _resolve_features(row: dict[str, Any], manifest_idx: dict[str, dict[str, Any]]) -> dict[str, float] | None:
    if all(name in row for name in STOP_VS_ACT_FEATURE_NAMES):
        return {name: float(row[name]) for name in STOP_VS_ACT_FEATURE_NAMES}

    state_id = str(row.get("state_id", ""))
    if not state_id:
        return None
    manifest_row = manifest_idx.get(state_id)
    if manifest_row is None:
        return None

    feats = dict(manifest_row.get("features", {}))
    if not all(name in feats for name in STOP_VS_ACT_FEATURE_NAMES):
        return None
    return {name: float(feats[name]) for name in STOP_VS_ACT_FEATURE_NAMES}


def _resolve_split(
    row: dict[str, Any],
    manifest_idx: dict[str, dict[str, Any]],
    *,
    train_ratio: float,
    split_seed: int,
) -> str:
    split = str(row.get("split", "")).lower()
    if split in {"train", "test"}:
        return split

    state_id = str(row.get("state_id", ""))
    manifest_row = manifest_idx.get(state_id, {})
    m_split = str(manifest_row.get("split", "")).lower()
    if m_split in {"train", "test"}:
        return m_split

    key = f"{split_seed}|{state_id}"
    return "train" if _stable_u01(key) < train_ratio else "test"


def _confidence_weight(teacher_prob_act: float) -> float:
    return max(0.0, min(1.0, abs(float(teacher_prob_act) - 0.5) * 2.0))


def _to_optional_float(x: Any) -> float | None:
    if isinstance(x, bool):
        return None
    if isinstance(x, (int, float)):
        return float(x)
    return None


def _evaluate_gain_gap_baseline(test_rows: list[dict[str, Any]], margin: float) -> dict[str, float]:
    scored: list[tuple[float, int]] = []
    for row in test_rows:
        y = int(row["label_act"])
        p = 1.0 if float(row["gap_to_best_other_gain"]) > margin else 0.0
        scored.append((p, y))

    n = max(1, len(scored))
    tp = sum(1 for p, y in scored if y == 1 and p >= 0.5)
    fp = sum(1 for p, y in scored if y == 0 and p >= 0.5)
    tn = sum(1 for p, y in scored if y == 0 and p < 0.5)
    fn = sum(1 for p, y in scored if y == 1 and p < 0.5)
    acc = (tp + tn) / n
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    brier = sum((p - y) ** 2 for p, y in scored) / n

    # Rank-based AUC for deterministic hard baseline.
    pos = [p for p, y in scored if y == 1]
    neg = [p for p, y in scored if y == 0]
    if pos and neg:
        wins = 0.0
        total = 0.0
        for p_pos in pos:
            for p_neg in neg:
                total += 1.0
                if p_pos > p_neg:
                    wins += 1.0
                elif p_pos == p_neg:
                    wins += 0.5
        auc = wins / max(1.0, total)
    else:
        auc = 0.5

    return {
        "rows": float(len(scored)),
        "accuracy": acc,
        "precision": precision,
        "recall": recall,
        "brier": brier,
        "roc_auc": auc,
    }


def _bucket_metrics(model: dict[str, Any], test_rows: list[dict[str, Any]], threshold: float) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for bucket in ["accepted", "borderline", "rejected"]:
        rows = [r for r in test_rows if str(r.get("bucket", "")) == bucket]
        if not rows:
            continue
        out[bucket] = evaluate_binary_predictions(model, rows, threshold=threshold)
    return out


def _predicted_act_rate(model: dict[str, Any], rows: list[dict[str, Any]], threshold: float) -> float:
    if not rows:
        return 0.0
    probs = [stop_vs_act_probability(model, {name: float(r[name]) for name in STOP_VS_ACT_FEATURE_NAMES}) for r in rows]
    acts = [1.0 if p >= threshold else 0.0 for p in probs]
    return float(sum(acts) / max(1, len(acts)))


def _slice_metrics(
    model: dict[str, Any],
    test_rows: list[dict[str, Any]],
    *,
    threshold: float,
    key_name: str,
    key_fn: Any,
) -> dict[str, dict[str, float]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for r in test_rows:
        key = str(key_fn(r))
        groups.setdefault(key, []).append(r)

    out: dict[str, dict[str, float]] = {}
    for key, rows in sorted(groups.items()):
        cls = evaluate_binary_predictions(model, rows, threshold=threshold)
        out[key] = {
            "rows": float(len(rows)),
            "accuracy": float(cls["accuracy"]),
            "roc_auc": float(cls["roc_auc"]),
            "brier": float(cls["brier"]),
            "pred_act_rate": _predicted_act_rate(model, rows, threshold=threshold),
        }
    return {key_name: out}


def _margin_bin(abs_gap: float) -> str:
    if abs_gap < 0.04:
        return "m0_lt_0.04"
    if abs_gap < 0.12:
        return "m1_0.04_to_0.12"
    return "m2_ge_0.12"


def _disagreement_bin(agreement_rate: float | None) -> str:
    if agreement_rate is None or math.isnan(float(agreement_rate)):
        return "unknown"
    if agreement_rate < 0.60:
        return "low_lt_0.60"
    if agreement_rate < 0.80:
        return "mid_0.60_to_0.80"
    return "high_ge_0.80"


def _budget_bin(remaining_budget: float | None) -> str:
    if remaining_budget is None:
        return "unknown"
    if remaining_budget <= 3.0:
        return "low_le_3"
    if remaining_budget <= 7.0:
        return "mid_4_to_7"
    return "high_ge_8"


def _controller_behavior_metrics(
    model: dict[str, Any],
    test_rows: list[dict[str, Any]],
    *,
    threshold: float,
    neutral_gap_band: float,
) -> dict[str, Any]:
    if not test_rows:
        return {
            "available": False,
            "reason": "no_eval_rows",
            "primitive_quantity": "oracle_action_gap",
            "eligible_rows": 0,
            "total_eval_rows": 0,
        }

    counted = 0
    beneficial_act = 0
    harmful_act = 0
    harmful_premature_stop = 0
    beneficial_stop = 0
    neutral_rows = 0
    total_regret = 0.0

    for row in test_rows:
        gap = _to_optional_float(row.get("oracle_action_gap"))
        if gap is None:
            continue
        counted += 1
        prob_act = stop_vs_act_probability(model, {name: float(row[name]) for name in STOP_VS_ACT_FEATURE_NAMES})
        pred_act = prob_act >= threshold

        if gap > neutral_gap_band:
            if pred_act:
                beneficial_act += 1
            else:
                harmful_premature_stop += 1
                total_regret += float(gap)
        elif gap < -neutral_gap_band:
            if pred_act:
                harmful_act += 1
                total_regret += float(-gap)
            else:
                beneficial_stop += 1
        else:
            neutral_rows += 1

    if counted <= 0:
        return {
            "available": False,
            "reason": "missing_oracle_action_gap",
            "primitive_quantity": "oracle_action_gap",
            "eligible_rows": 0,
            "total_eval_rows": len(test_rows),
        }

    denom = float(counted)
    return {
        "available": True,
        "primitive_quantity": "oracle_action_gap",
        "utility_gap_definition": "utility(ACT) - utility(STOP)",
        "neutral_gap_band": float(neutral_gap_band),
        "eligible_rows": counted,
        "total_eval_rows": len(test_rows),
        "missing_rows": int(len(test_rows) - counted),
        "rate_denominator": "eligible_eval_rows",
        "beneficial_act_rate_bar": float(beneficial_act / denom),
        "harmful_act_rate_har": float(harmful_act / denom),
        "harmful_premature_stop_rate_hpsr": float(harmful_premature_stop / denom),
        "beneficial_stop_rate_bsr": float(beneficial_stop / denom),
        "neutral_gap_rate": float(neutral_rows / denom),
        "oracle_action_regret": float(total_regret / denom),
        "aux_counts": {
            "beneficial_act": int(beneficial_act),
            "harmful_act": int(harmful_act),
            "harmful_premature_stop": int(harmful_premature_stop),
            "beneficial_stop": int(beneficial_stop),
            "neutral_gap_rows": int(neutral_rows),
        },
    }


def _threshold_grid(min_threshold: float, max_threshold: float, step: float, include: float) -> list[float]:
    lo = max(0.0, min(1.0, float(min_threshold)))
    hi = max(0.0, min(1.0, float(max_threshold)))
    if hi < lo:
        lo, hi = hi, lo
    step_val = max(1e-6, float(step))
    vals: list[float] = []
    t = lo
    while t <= hi + 1e-9:
        vals.append(round(float(t), 6))
        t += step_val
    vals.append(round(max(0.0, min(1.0, float(include))), 6))
    return sorted(set(vals))


def _evaluation_at_threshold(
    model: dict[str, Any],
    test_rows: list[dict[str, Any]],
    *,
    threshold: float,
    behavior_neutral_gap_band: float,
) -> dict[str, Any]:
    cls = evaluate_binary_predictions(model, test_rows, threshold=threshold)
    return {
        "threshold": float(threshold),
        "predicted_act_rate": _predicted_act_rate(model, test_rows, threshold=threshold),
        "student": {
            "accuracy": float(cls["accuracy"]),
            "roc_auc": float(cls["roc_auc"]),
            "brier": float(cls["brier"]),
            "precision": float(cls["precision"]),
            "recall": float(cls["recall"]),
        },
        "controller_behavior": _controller_behavior_metrics(
            model,
            test_rows,
            threshold=threshold,
            neutral_gap_band=behavior_neutral_gap_band,
        ),
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Train/eval oracle-distilled stop-vs-act student")
    p.add_argument("--distill-dataset", required=True, help="Distillation-ready JSONL from selective builder")
    p.add_argument("--state-manifest", default="", help="Optional pilot state manifest JSONL for feature join")
    p.add_argument("--output-dir", required=True)
    p.add_argument("--run-name", default="oracle_distilled_student_v1")
    p.add_argument("--seed", type=int, default=31)
    p.add_argument("--train-ratio", type=float, default=0.8)
    p.add_argument("--train-buckets", default="accepted,borderline")
    p.add_argument("--eval-buckets", default="accepted,borderline")
    p.add_argument(
        "--train-selection-mode",
        choices=["bucket", "selected_flag"],
        default="bucket",
        help=(
            "bucket: train_rows selected by train_buckets (default). "
            "selected_flag: train_rows selected by row field `selected_for_training`==1."
        ),
    )
    p.add_argument("--model-kind", choices=["logistic", "gbdt"], default="logistic")
    p.add_argument("--uncertain-policy", choices=["none", "filter", "downweight", "downweight_nonpositive"], default="downweight")
    p.add_argument("--decision-threshold", type=float, default=0.5)
    p.add_argument("--use-sample-weight", action="store_true")
    p.add_argument("--soft-weight-mode", choices=["none", "confidence"], default="confidence")
    p.add_argument("--soft-weight-strength", type=float, default=0.3)
    p.add_argument("--heuristic-margin", type=float, default=0.01)
    p.add_argument(
        "--behavior-neutral-gap-band",
        type=float,
        default=0.0,
        help="Treat |oracle_action_gap| <= this value as neutral for BAR/HAR/HPSR/BSR metrics.",
    )
    p.add_argument("--sweep-threshold-min", type=float, default=0.05)
    p.add_argument("--sweep-threshold-max", type=float, default=0.95)
    p.add_argument("--sweep-threshold-step", type=float, default=0.05)
    p.add_argument("--fail-on-mock-provenance", action="store_true")
    p.add_argument("--provenance-tag", default="")
    p.add_argument(
        "--filter-policy",
        default="oracle_distilled_generic",
        help=(
            "Optional role tag used by downstream comparison scaffolds "
            "(e.g. anchor_default, oracle_distilled_accepted_only, "
            "oracle_distilled_accepted_plus_borderline, random_matched_coverage_baseline)."
        ),
    )
    p.add_argument(
        "--random-baseline-source",
        default="",
        help="Optional free-form note for random matched-coverage baseline provenance.",
    )
    p.add_argument(
        "--observed-avg-actions",
        type=float,
        default=-1.0,
        help=(
            "Optional externally measured avg-actions/compute-rate. "
            "If omitted (<0), comparison uses predicted ACT-rate only."
        ),
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()

    distill_rows = _read_jsonl(Path(args.distill_dataset))
    manifest_idx: dict[str, dict[str, Any]] = {}
    if args.state_manifest:
        manifest_rows = _read_jsonl(Path(args.state_manifest))
        manifest_idx = {str(r.get("state_id", "")): r for r in manifest_rows if str(r.get("state_id", ""))}

    train_buckets = _parse_bucket_list(args.train_buckets)
    eval_buckets = _parse_bucket_list(args.eval_buckets)

    prepared: list[dict[str, Any]] = []
    dropped_missing_features = 0
    mock_rows = 0

    for row in distill_rows:
        bucket = str(row.get("bucket", "")).lower()
        if bucket not in {"accepted", "borderline", "rejected"}:
            continue

        prov = dict(row.get("provenance", {}))
        is_mock = bool(prov.get("mock_interface_only", False)) or bool(prov.get("has_non_oracle_warning", False))
        if is_mock:
            mock_rows += 1

        features = _resolve_features(row, manifest_idx)
        if features is None:
            dropped_missing_features += 1
            continue

        split = _resolve_split(row, manifest_idx, train_ratio=float(args.train_ratio), split_seed=int(args.seed))
        teacher_prob = float(row.get("teacher_prob_act", 0.5))
        hard_label = int(row.get("hard_label_act", 0))

        base_weight = float(row.get("sample_weight", 1.0)) if args.use_sample_weight else 1.0
        if args.soft_weight_mode == "confidence":
            conf = _confidence_weight(teacher_prob)
            base_weight = base_weight * ((1.0 - args.soft_weight_strength) + (args.soft_weight_strength * conf))

        prepared_row = {
            "state_id": row.get("state_id"),
            "bucket": bucket,
            "split": split,
            "label_act": hard_label,
            "sample_weight": max(0.0, base_weight),
            "is_uncertain": 1 if bucket == "borderline" else 0,
            "target_reliability_weight": _confidence_weight(teacher_prob),
            "teacher_prob_act": teacher_prob,
            "oracle_action_gap": _to_optional_float(row.get("oracle_action_gap")),
            "agreement_rate": row.get("agreement_rate"),
            "remaining_budget_raw": row.get("remaining_budget"),
            "selected_for_training": int(row.get("selected_for_training", 0)),
            "mock_provenance": int(is_mock),
        }
        prepared_row.update(features)
        prepared.append(prepared_row)

    if args.fail_on_mock_provenance and mock_rows > 0:
        raise SystemExit(f"Mock/non-oracle provenance detected in input rows: {mock_rows}")

    if args.train_selection_mode == "bucket":
        train_rows = [
            r
            for r in prepared
            if r["split"] == "train" and str(r["bucket"]) in train_buckets and float(r["sample_weight"]) > 0.0
        ]
    else:
        train_rows = [
            r
            for r in prepared
            if r["split"] == "train" and int(r.get("selected_for_training", 0)) == 1 and float(r["sample_weight"]) > 0.0
        ]
    test_rows = [r for r in prepared if r["split"] == "test" and str(r["bucket"]) in eval_buckets]
    train_pool_rows = [r for r in prepared if r["split"] == "train"]

    if not train_rows:
        raise SystemExit("No training rows remain after bucket/weight/feature filters")
    if not test_rows:
        raise SystemExit("No eval rows remain after bucket/feature filters")

    model = fit_stop_vs_act_model(
        train_rows,
        model_kind=args.model_kind,
        uncertain_policy=args.uncertain_policy,
        seed=args.seed,
        reliability_power=0.0,
    )

    student_metrics = evaluate_binary_predictions(model, test_rows, threshold=args.decision_threshold)
    baseline_metrics = _evaluate_gain_gap_baseline(test_rows, margin=args.heuristic_margin)
    by_bucket = _bucket_metrics(model, test_rows, threshold=args.decision_threshold)
    predicted_act_rate = _predicted_act_rate(model, test_rows, threshold=args.decision_threshold)
    uncertainty_slices = _slice_metrics(
        model,
        test_rows,
        threshold=args.decision_threshold,
        key_name="uncertainty_bins",
        key_fn=lambda r: "uncertain_borderline" if str(r.get("bucket", "")) == "borderline" else "certain_nonborderline",
    )
    margin_slices = _slice_metrics(
        model,
        test_rows,
        threshold=args.decision_threshold,
        key_name="oracle_margin_bins",
        key_fn=lambda r: (
            _margin_bin(abs(float(r.get("oracle_action_gap"))))
            if isinstance(r.get("oracle_action_gap"), (int, float))
            else "unknown"
        ),
    )
    disagreement_slices = _slice_metrics(
        model,
        test_rows,
        threshold=args.decision_threshold,
        key_name="disagreement_bins",
        key_fn=lambda r: _disagreement_bin(r.get("agreement_rate")),
    )
    budget_slices = _slice_metrics(
        model,
        test_rows,
        threshold=args.decision_threshold,
        key_name="remaining_budget_bins",
        key_fn=lambda r: _budget_bin(
            float(r.get("remaining_budget_raw")) if isinstance(r.get("remaining_budget_raw"), (int, float)) else None
        ),
    )

    student_probs = [
        stop_vs_act_probability(model, {name: float(r[name]) for name in STOP_VS_ACT_FEATURE_NAMES}) for r in test_rows
    ]
    mean_student_prob = float(sum(student_probs) / max(1, len(student_probs)))
    behavior_metrics = _controller_behavior_metrics(
        model,
        test_rows,
        threshold=args.decision_threshold,
        neutral_gap_band=float(args.behavior_neutral_gap_band),
    )
    threshold_grid = _threshold_grid(
        args.sweep_threshold_min,
        args.sweep_threshold_max,
        args.sweep_threshold_step,
        args.decision_threshold,
    )
    threshold_sweep = [
        _evaluation_at_threshold(
            model,
            test_rows,
            threshold=t,
            behavior_neutral_gap_band=float(args.behavior_neutral_gap_band),
        )
        for t in threshold_grid
    ]

    bucket_counts: dict[str, int] = {}
    for r in prepared:
        b = str(r["bucket"])
        bucket_counts[b] = int(bucket_counts.get(b, 0)) + 1

    summary = {
        "run_name": args.run_name,
        "distill_dataset": args.distill_dataset,
        "state_manifest": args.state_manifest,
        "settings": {
            "seed": args.seed,
            "train_ratio": args.train_ratio,
            "train_buckets": sorted(train_buckets),
            "eval_buckets": sorted(eval_buckets),
            "train_selection_mode": args.train_selection_mode,
            "model_kind": args.model_kind,
            "uncertain_policy": args.uncertain_policy,
            "decision_threshold": args.decision_threshold,
            "use_sample_weight": bool(args.use_sample_weight),
            "soft_weight_mode": args.soft_weight_mode,
            "soft_weight_strength": args.soft_weight_strength,
            "heuristic_margin": args.heuristic_margin,
            "behavior_neutral_gap_band": args.behavior_neutral_gap_band,
            "sweep_threshold_min": args.sweep_threshold_min,
            "sweep_threshold_max": args.sweep_threshold_max,
            "sweep_threshold_step": args.sweep_threshold_step,
            "provenance_tag": args.provenance_tag,
            "filter_policy": args.filter_policy,
            "random_baseline_source": args.random_baseline_source,
        },
        "dataset_summary": {
            "input_rows": len(distill_rows),
            "prepared_rows": len(prepared),
            "dropped_missing_features": dropped_missing_features,
            "mock_rows_detected": mock_rows,
            "bucket_counts_prepared": bucket_counts,
            "train_rows": len(train_rows),
            "train_pool_rows": len(train_pool_rows),
            "retained_coverage_train_pool": float(len(train_rows) / max(1, len(train_pool_rows))),
            "eval_rows": len(test_rows),
        },
        "student_model": {
            "model_type": model.get("model_type"),
            "feature_family": model.get("feature_family"),
            "train_rows_used": model.get("train_rows_used"),
            "feature_names": STOP_VS_ACT_FEATURE_NAMES,
        },
        "evaluation": {
            "student": student_metrics,
            "anchor_gain_gap_baseline": baseline_metrics,
            "student_minus_anchor": {
                "accuracy": float(student_metrics["accuracy"] - baseline_metrics["accuracy"]),
                "roc_auc": float(student_metrics["roc_auc"] - baseline_metrics["roc_auc"]),
                "brier": float(student_metrics["brier"] - baseline_metrics["brier"]),
            },
            "student_by_bucket": by_bucket,
            "mean_student_prob": mean_student_prob,
            "compute_reporting": {
                "predicted_act_rate": predicted_act_rate,
                "observed_avg_actions": None if args.observed_avg_actions < 0.0 else float(args.observed_avg_actions),
            },
            "controller_behavior": behavior_metrics,
            "threshold_sweep": threshold_sweep,
            "required_slices": {
                **uncertainty_slices,
                **margin_slices,
                **disagreement_slices,
                **budget_slices,
            },
        },
        "safety": {
            "non_claim_mode": bool(mock_rows > 0),
            "safe_interpretation": "pipeline/diagnostic only" if mock_rows > 0 else "pilot-label eval candidate",
            "warning": (
                "Mock/non-oracle provenance detected; do not claim distilled performance." if mock_rows > 0 else ""
            ),
        },
    }

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_json(out_dir / "oracle_distilled_student_summary.json", summary)

    model_out = dict(model)
    if args.model_kind == "gbdt":
        model_out.pop("estimator", None)
        model_out["export_note"] = "GBDT estimator omitted from JSON export by design"
    _write_json(out_dir / "oracle_distilled_student_model.json", model_out)

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
