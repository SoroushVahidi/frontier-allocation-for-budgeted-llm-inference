"""Compute per-fold metrics and bootstrap confidence intervals for OOF predictions.

Loads an OOF predictions JSONL file (fields: label_true, label_pred, proba_ready,
row_id) and computes:
  - Overall metrics (accuracy, macro F1, ready P/R/F1, PR-AUC)
  - Per-fold metrics (if --dataset-jsonl provided to reconstruct fold assignments)
  - 95% bootstrap CIs (example-level always; group-level if problem_id available)

Outputs:
  ci_metrics.json        — overall + CI metrics
  per_fold_metrics.csv   — per-fold table (when fold info is available)
  ci_report.md           — human-readable report

Usage:
    python3 scripts/analyze_relation_verifier_predictions.py \\
        --predictions outputs/.../predictions.jsonl \\
        --output-dir outputs/ci_analysis_<STAMP> \\
        --dataset-jsonl outputs/.../train_rows.jsonl \\
        --bootstrap-reps 1000 \\
        --seed 20260516
"""
from __future__ import annotations

import argparse
import csv
import json
import pathlib
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone

import numpy as np

_FORBIDDEN = {"openai", "anthropic", "cohere", "httpx", "requests", "boto3"}


def _check_forbidden() -> None:
    for lib in _FORBIDDEN:
        if lib in sys.modules:
            raise RuntimeError(f"Forbidden module loaded: {lib}")


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

def load_jsonl(path: pathlib.Path) -> list[dict]:
    rows: list[dict] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def _compute_metrics(
    labels: list[int],
    scores: list[float],
    preds: list[int] | None = None,
    threshold: float = 0.5,
) -> dict:
    from sklearn.metrics import (
        accuracy_score,
        average_precision_score,
        f1_score,
        precision_score,
        recall_score,
    )

    labels_arr = np.array(labels)
    scores_arr = np.array(scores)
    preds_arr = (
        np.array(preds) if preds is not None else (scores_arr >= threshold).astype(int)
    )

    acc = float(accuracy_score(labels_arr, preds_arr))
    macro_f1 = float(f1_score(labels_arr, preds_arr, average="macro", zero_division=0))
    ready_p = float(precision_score(labels_arr, preds_arr, pos_label=1, zero_division=0))
    ready_r = float(recall_score(labels_arr, preds_arr, pos_label=1, zero_division=0))
    ready_f1 = float(f1_score(labels_arr, preds_arr, pos_label=1, zero_division=0))

    unique = set(labels_arr.tolist())
    pr_auc: float | None = None
    if 0 in unique and 1 in unique:
        pr_auc = float(average_precision_score(labels_arr, scores_arr, pos_label=1))

    return {
        "accuracy": round(acc, 4),
        "macro_f1": round(macro_f1, 4),
        "ready_precision": round(ready_p, 4),
        "ready_recall": round(ready_r, 4),
        "ready_f1": round(ready_f1, 4),
        "pr_auc": round(pr_auc, 4) if pr_auc is not None else None,
        "n": len(labels),
        "n_ready": int(sum(1 for lbl in labels if lbl == 1)),
    }


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

def _example_bootstrap_ci(
    records: list[dict],
    metric_fn,
    n_reps: int = 1000,
    seed: int = 42,
    level: float = 0.95,
) -> tuple[float | None, float | None]:
    """Bootstrap CI by resampling individual prediction records."""
    rng = np.random.default_rng(seed)
    n = len(records)
    values: list[float] = []
    for _ in range(n_reps):
        idx = rng.integers(0, n, n)
        sample = [records[i] for i in idx]
        try:
            val = metric_fn(sample)
            if val is not None:
                values.append(val)
        except Exception:
            pass
    if not values:
        return None, None
    alpha = (1.0 - level) / 2.0
    lo = float(np.percentile(values, alpha * 100))
    hi = float(np.percentile(values, (1.0 - alpha) * 100))
    return round(lo, 4), round(hi, 4)


def _group_bootstrap_ci(
    groups: dict[str, list[dict]],
    metric_fn,
    n_reps: int = 1000,
    seed: int = 43,
    level: float = 0.95,
) -> tuple[float | None, float | None]:
    """Bootstrap CI by resampling problem groups with replacement."""
    rng = np.random.default_rng(seed)
    group_keys = list(groups.keys())
    n_groups = len(group_keys)
    values: list[float] = []
    for _ in range(n_reps):
        sampled = rng.choice(group_keys, n_groups, replace=True)
        sample: list[dict] = []
        for g in sampled:
            sample.extend(groups[g])
        try:
            val = metric_fn(sample)
            if val is not None:
                values.append(val)
        except Exception:
            pass
    if not values:
        return None, None
    alpha = (1.0 - level) / 2.0
    lo = float(np.percentile(values, alpha * 100))
    hi = float(np.percentile(values, (1.0 - alpha) * 100))
    return round(lo, 4), round(hi, 4)


def _make_ready_f1_fn(score_field: str, label_field: str, threshold: float = 0.5):
    def fn(records: list[dict]) -> float | None:
        labels = [r[label_field] for r in records]
        scores = [r[score_field] for r in records]
        return _compute_metrics(labels, scores, threshold=threshold)["ready_f1"]
    return fn


def _make_pr_auc_fn(score_field: str, label_field: str):
    def fn(records: list[dict]) -> float | None:
        labels = [r[label_field] for r in records]
        scores = [r[score_field] for r in records]
        return _compute_metrics(labels, scores)["pr_auc"]  # None if one-class
    return fn


# ---------------------------------------------------------------------------
# Fold reconstruction
# ---------------------------------------------------------------------------

def _reconstruct_fold_assignments(
    pred_records: list[dict],
    dataset_rows: list[dict],
    n_splits: int = 5,
    seed: int = 20260516,
) -> list[dict]:
    """Join predictions with dataset on row_id; add problem_id and fold fields."""
    from sklearn.model_selection import StratifiedGroupKFold

    ds_by_id = {r["row_id"]: r for r in dataset_rows}

    # Enrich with problem_id
    enriched = []
    for p in pred_records:
        ds_row = ds_by_id.get(p["row_id"], {})
        enriched.append({**p, "problem_id": ds_row.get("problem_id", "")})

    labels_arr = np.array([r["label_true"] for r in enriched])
    groups_arr = np.array([
        ds_by_id.get(r["row_id"], {}).get("problem_id", f"_row_{i}")
        for i, r in enumerate(enriched)
    ])

    unique_labels = set(labels_arr.tolist())
    if len(unique_labels) < 2:
        # Can't stratify; return without fold assignment
        return [{**r, "fold": -1} for r in enriched]

    cv = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    fold_arr = np.full(len(enriched), -1, dtype=int)
    for fold_idx, (_, test_idx) in enumerate(cv.split(labels_arr, labels_arr, groups_arr)):
        fold_arr[test_idx] = fold_idx

    return [{**r, "fold": int(fold_arr[i])} for i, r in enumerate(enriched)]


# ---------------------------------------------------------------------------
# Per-fold metrics
# ---------------------------------------------------------------------------

def _compute_per_fold_metrics(
    records: list[dict],
    score_field: str,
    label_field: str,
    threshold: float = 0.5,
) -> list[dict]:
    by_fold: dict[int, list[dict]] = defaultdict(list)
    for r in records:
        by_fold[r.get("fold", -1)].append(r)

    results = []
    for fold in sorted(by_fold.keys()):
        fold_recs = by_fold[fold]
        labels = [r[label_field] for r in fold_recs]
        scores = [r[score_field] for r in fold_recs]
        m = _compute_metrics(labels, scores, threshold=threshold)
        results.append({"fold": fold, **m})
    return results


def _write_per_fold_csv(fold_metrics: list[dict], path: pathlib.Path) -> None:
    if not fold_metrics:
        return
    fields = list(fold_metrics[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(fold_metrics)


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def _ci_str(ci: dict) -> str:
    lo, hi = ci.get("lo"), ci.get("hi")
    if lo is None or hi is None:
        return "N/A"
    return f"[{lo:.4f}, {hi:.4f}]"


def _write_ci_report(
    output_dir: pathlib.Path,
    overall: dict,
    fold_metrics: list[dict] | None,
    ci_result: dict,
    predictions_path: str,
    dataset_path: str | None,
    bootstrap_reps: int,
) -> None:
    lines: list[str] = []
    append = lines.append

    append("# RelationReady Verifier — Prediction CI Analysis Report")
    append("")
    append(f"- **Generated:** {datetime.now(timezone.utc).isoformat()}")
    append(f"- **Predictions:** `{predictions_path}`")
    if dataset_path:
        append(f"- **Dataset (fold/group reconstruction):** `{dataset_path}`")
    append(f"- **Bootstrap reps:** {bootstrap_reps}")
    append("")

    append("## Overall Metrics (threshold=0.5)")
    append("")
    append("| Metric | Value |")
    append("|---|---|")
    append(f"| n | {overall['n']} |")
    append(f"| n\\_ready (true) | {overall['n_ready']} |")
    append(f"| Accuracy | {overall['accuracy']} |")
    append(f"| Macro F1 | {overall['macro_f1']} |")
    append(f"| Ready Precision | {overall['ready_precision']} |")
    append(f"| Ready Recall | {overall['ready_recall']} |")
    append(f"| **Ready F1** | **{overall['ready_f1']}** |")
    pr_str = f"{overall['pr_auc']}" if overall.get("pr_auc") is not None else "N/A"
    append(f"| **PR-AUC (ready)** | **{pr_str}** |")
    append("")

    append("## 95% Bootstrap Confidence Intervals")
    append("")
    append(f"### Example-level bootstrap (n={overall['n']} rows resampled with replacement)")
    append("")
    append("| Metric | Point estimate | 95% CI |")
    append("|---|---|---|")
    for key, name in [("ready_f1", "Ready F1"), ("pr_auc", "PR-AUC")]:
        est = overall.get(key)
        est_s = f"{est:.4f}" if est is not None else "N/A"
        ci_s = _ci_str(ci_result.get(f"example_{key}", {}))
        append(f"| {name} | {est_s} | {ci_s} |")
    append("")
    append("> *Example bootstrap resamples individual predictions — it ignores group structure*")
    append("> *and may underestimate variance caused by problem-level correlation.*")
    append("")

    if ci_result.get("group_available"):
        n_groups = ci_result.get("n_groups", "?")
        append(f"### Group-level bootstrap ({n_groups} problem\\_id groups resampled with replacement)")
        append("")
        append("| Metric | Point estimate | 95% CI |")
        append("|---|---|---|")
        for key, name in [("ready_f1", "Ready F1"), ("pr_auc", "PR-AUC")]:
            est = overall.get(key)
            est_s = f"{est:.4f}" if est is not None else "N/A"
            ci_s = _ci_str(ci_result.get(f"group_{key}", {}))
            append(f"| {name} | {est_s} | {ci_s} |")
        append("")
        append("> *Group bootstrap preserves problem-level correlation. PR-AUC CI is computed*")
        append("> *only from bootstrap samples that contain both ready and not\\_ready examples.*")
        append("")
    else:
        append("### Group-level bootstrap")
        append("")
        append("*Not available — provide `--dataset-jsonl` to enable group-level bootstrap.*")
        append("")

    if fold_metrics:
        append("## Per-Fold Metrics")
        append("")
        headers = [
            "fold", "n", "n_ready", "ready_precision", "ready_recall",
            "ready_f1", "macro_f1", "accuracy", "pr_auc",
        ]
        header_labels = [
            "Fold", "N", "N Ready", "Ready P", "Ready R",
            "Ready F1", "Macro F1", "Acc", "PR-AUC",
        ]
        append("| " + " | ".join(header_labels) + " |")
        append("|" + "|".join("---" for _ in headers) + "|")
        for fm in fold_metrics:
            vals = []
            for h in headers:
                v = fm.get(h)
                vals.append("N/A" if v is None else str(v))
            append("| " + " | ".join(vals) + " |")
        append("")

        f1s = [fm["ready_f1"] for fm in fold_metrics if fm.get("ready_f1") is not None]
        if len(f1s) > 1:
            mean_f1 = statistics.mean(f1s)
            std_f1 = statistics.stdev(f1s)
            append(
                f"Per-fold ready F1: "
                f"mean={mean_f1:.4f}, std={std_f1:.4f}, "
                f"min={min(f1s):.4f}, max={max(f1s):.4f}"
            )
            append("")

    append("## Comparison to Baselines")
    append("")
    append("| Model | Ready F1 | PR-AUC |")
    append("|---|---|---|")
    append("| TF-IDF + LogReg (baseline) | 0.710 | 0.808 |")
    append("| Frozen all-mpnet-base-v2 + LinearSVC | 0.786 | 0.844 |")
    append(f"| **SetFit cfg1 (this run)** | **{overall['ready_f1']}** | **{pr_str}** |")
    append("")

    ex_f1_lo = ci_result.get("example_ready_f1", {}).get("lo")
    if ex_f1_lo is not None:
        if ex_f1_lo > 0.786:
            append(
                f"✓ Example-level 95% CI lower bound ({ex_f1_lo:.4f}) exceeds "
                f"frozen-mpnet SVM ready F1 (0.786)."
            )
        else:
            append(
                f"⚠ Example-level 95% CI lower bound ({ex_f1_lo:.4f}) does not "
                f"clear the frozen-mpnet SVM baseline (0.786). "
                f"CIs overlap — dataset too small for a definitive claim."
            )
        append("")

    if ci_result.get("group_available"):
        gr_f1_lo = ci_result.get("group_ready_f1", {}).get("lo")
        if gr_f1_lo is not None:
            if gr_f1_lo > 0.786:
                append(
                    f"✓ Group-level 95% CI lower bound ({gr_f1_lo:.4f}) exceeds "
                    f"frozen-mpnet SVM ready F1 (0.786)."
                )
            else:
                append(
                    f"⚠ Group-level 95% CI lower bound ({gr_f1_lo:.4f}) does not "
                    f"clear the frozen-mpnet SVM baseline (0.786). "
                    f"Use with caution for paper claims."
                )
            append("")

    append("## Limitations")
    append("")
    append(
        "- **Small dataset (n=380, ready=93):** Bootstrap CIs reflect resampling "
        "variance but cannot compensate for a fundamentally small sample."
    )
    append(
        "- **OOF only:** All metrics are computed on out-of-fold predictions. "
        "No independent held-out test set with ready examples exists."
    )
    append(
        "- **Example bootstrap is optimistically narrow:** Ignores group structure; "
        "underestimates variance from problem-level correlation."
    )
    append(
        "- **Group bootstrap instability:** With ~240 unique problem groups, "
        "some bootstrap samples may have zero ready examples, making PR-AUC undefined. "
        "PR-AUC CI is computed only from samples where both classes are present."
    )
    append(
        "- **Threshold is default (0.5):** Not tuned on a separate held-out val set "
        "for these OOF predictions."
    )
    append("")

    (output_dir / "ci_report.md").write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    _check_forbidden()

    parser = argparse.ArgumentParser(
        description="Bootstrap CI + per-fold analysis for OOF predictions"
    )
    parser.add_argument("--predictions", required=True, help="Path to predictions JSONL")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument(
        "--dataset-jsonl", default=None,
        help="Training dataset JSONL; enables fold reconstruction and group bootstrap"
    )
    parser.add_argument("--label-field", default="label_true")
    parser.add_argument("--score-field", default="proba_ready")
    parser.add_argument("--pred-field", default="label_pred")
    parser.add_argument("--group-field", default="problem_id")
    parser.add_argument("--fold-field", default="fold")
    parser.add_argument("--n-splits", type=int, default=5)
    parser.add_argument("--cv-seed", type=int, default=20260516)
    parser.add_argument("--bootstrap-reps", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=20260516)
    args = parser.parse_args(argv)

    pred_path = pathlib.Path(args.predictions)
    if not pred_path.exists():
        print(f"ERROR: predictions not found: {pred_path}", file=sys.stderr)
        return 1

    output_dir = pathlib.Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    records = load_jsonl(pred_path)
    if not records:
        print("ERROR: predictions file is empty.", file=sys.stderr)
        return 1
    print(f"Loaded {len(records)} predictions from {pred_path}")

    dataset_path: str | None = None
    if args.dataset_jsonl:
        dataset_path = args.dataset_jsonl
        ds_path = pathlib.Path(args.dataset_jsonl)
        if not ds_path.exists():
            print(f"ERROR: dataset not found: {ds_path}", file=sys.stderr)
            return 1
        dataset_rows = load_jsonl(ds_path)
        print(f"Loaded {len(dataset_rows)} dataset rows from {ds_path}")
        records = _reconstruct_fold_assignments(
            records, dataset_rows, n_splits=args.n_splits, seed=args.cv_seed
        )
        print(f"Fold assignments reconstructed (n_splits={args.n_splits}, seed={args.cv_seed})")

    for field in (args.label_field, args.score_field):
        if not all(field in r for r in records):
            print(f"ERROR: field '{field}' missing from predictions.", file=sys.stderr)
            return 1

    # Overall metrics
    labels = [r[args.label_field] for r in records]
    scores = [r[args.score_field] for r in records]
    file_preds = [r.get(args.pred_field) for r in records]
    use_file_preds = all(p is not None for p in file_preds)
    overall = _compute_metrics(
        labels, scores,
        preds=file_preds if use_file_preds else None,
        threshold=0.5,
    )
    print(
        f"Overall: accuracy={overall['accuracy']}  macro_F1={overall['macro_f1']}  "
        f"ready_F1={overall['ready_f1']}  PR-AUC={overall['pr_auc']}"
    )

    # Per-fold metrics
    fold_metrics: list[dict] | None = None
    if args.fold_field in records[0]:
        fold_metrics = _compute_per_fold_metrics(
            records, args.score_field, args.label_field, threshold=0.5
        )
        print(f"Per-fold metrics: {len(fold_metrics)} folds")
        _write_per_fold_csv(fold_metrics, output_dir / "per_fold_metrics.csv")

    # Bootstrap CIs
    print(f"Bootstrap CIs (reps={args.bootstrap_reps}, seed={args.seed})...")
    f1_fn = _make_ready_f1_fn(args.score_field, args.label_field, threshold=0.5)
    pr_fn = _make_pr_auc_fn(args.score_field, args.label_field)

    ex_f1_lo, ex_f1_hi = _example_bootstrap_ci(
        records, f1_fn, n_reps=args.bootstrap_reps, seed=args.seed
    )
    ex_pr_lo, ex_pr_hi = _example_bootstrap_ci(
        records, pr_fn, n_reps=args.bootstrap_reps, seed=args.seed + 1
    )

    ci_result: dict = {
        "example_ready_f1": {"lo": ex_f1_lo, "hi": ex_f1_hi},
        "example_pr_auc": {"lo": ex_pr_lo, "hi": ex_pr_hi},
        "group_available": False,
    }

    # Group-level bootstrap
    if args.group_field in records[0] and any(r.get(args.group_field) for r in records):
        groups: dict[str, list[dict]] = defaultdict(list)
        for r in records:
            groups[r.get(args.group_field) or "__none__"].append(r)
        n_groups = len(groups)
        print(f"Group bootstrap: {n_groups} groups")

        gr_f1_lo, gr_f1_hi = _group_bootstrap_ci(
            dict(groups), f1_fn, n_reps=args.bootstrap_reps, seed=args.seed
        )
        gr_pr_lo, gr_pr_hi = _group_bootstrap_ci(
            dict(groups), pr_fn, n_reps=args.bootstrap_reps, seed=args.seed + 1
        )
        ci_result["group_available"] = True
        ci_result["n_groups"] = n_groups
        ci_result["group_ready_f1"] = {"lo": gr_f1_lo, "hi": gr_f1_hi}
        ci_result["group_pr_auc"] = {"lo": gr_pr_lo, "hi": gr_pr_hi}

    # Save ci_metrics.json
    ci_metrics_out = {
        "overall": overall,
        "ci": ci_result,
        "fold_metrics": fold_metrics,
        "config": {
            "predictions": str(pred_path),
            "dataset_jsonl": dataset_path,
            "bootstrap_reps": args.bootstrap_reps,
            "seed": args.seed,
            "n_splits": args.n_splits,
            "cv_seed": args.cv_seed,
            "generated": datetime.now(timezone.utc).isoformat(),
        },
    }
    (output_dir / "ci_metrics.json").write_text(
        json.dumps(ci_metrics_out, indent=2), encoding="utf-8"
    )

    _write_ci_report(
        output_dir, overall, fold_metrics, ci_result,
        str(pred_path), dataset_path, args.bootstrap_reps,
    )

    print(f"Output dir: {output_dir}")
    print("✓ No provider APIs called.")
    print("✓ No outputs staged or committed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
