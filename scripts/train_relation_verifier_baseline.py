"""Lightweight sklearn baseline trainer for the RelationReady binary verifier.

Uses TF-IDF + LogisticRegression (or LinearSVC) on feature_text.
Intended as a paper-quality smoke baseline — NOT a production verifier.

Usage:
    # Dry run (validate dataset, no training):
    python3 scripts/train_relation_verifier_baseline.py \
        --dataset-jsonl outputs/.../train_rows.jsonl \
        --output-dir outputs/relation_verifier_baseline_dryrun_<STAMP> \
        --mode dry_run

    # Train with grouped CV and threshold sweep:
    python3 scripts/train_relation_verifier_baseline.py \
        --dataset-jsonl outputs/.../train_rows.jsonl \
        --output-dir outputs/relation_verifier_baseline_train_<STAMP> \
        --mode train \
        --seed 20260514 \
        --grouped-cv \
        --threshold-sweep
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import warnings
from collections import Counter
from datetime import datetime, timezone

FORBIDDEN_FEATURE_KEYS = {
    "gold_answer_metadata_only",
    "relation_ready_label_manual",
    "first_error_axis_manual",
    "notes_manual",
}

TINY_DATASET_WARNING = (
    "⚠  TINY DATASET WARNING: This baseline is trained on a very small dataset "
    "(≤33 rows). Metrics are not reliable and must not be interpreted as "
    "production-verifier performance. Use this scaffold only for smoke-testing "
    "the training pipeline."
)


def load_jsonl(path: pathlib.Path) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def check_leakage(rows: list[dict]) -> list[str]:
    issues = []
    for i, row in enumerate(rows):
        ft = row.get("feature_text", "")
        sf = row.get("structured_features", {})
        for key in FORBIDDEN_FEATURE_KEYS:
            if key in ft:
                issues.append(f"Row {i}: forbidden key '{key}' found in feature_text")
            if key in sf:
                issues.append(f"Row {i}: forbidden key '{key}' found in structured_features")
    return issues


def dry_run(rows: list[dict], label_field: str) -> dict:
    labels = [r.get(label_field) for r in rows]
    label_counts = Counter(labels)
    leakage_issues = check_leakage(rows)
    split_counts = Counter(r.get("split_group_id", "") for r in rows)
    empty_ft = sum(1 for r in rows if not r.get("feature_text", "").strip())
    return {
        "total_rows": len(rows),
        "label_counts": dict(label_counts),
        "split_counts": dict(split_counts),
        "leakage_issues": leakage_issues,
        "empty_feature_text": empty_ft,
    }


def _build_cv(rows: list[dict], n_folds: int, seed: int, use_grouped_cv: bool):
    """Return (cv_object, groups_array_or_None, group_field_used, warning_msg)."""
    if not use_grouped_cv:
        from sklearn.model_selection import StratifiedKFold
        return (
            StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=seed),
            None, None, None,
        )

    # Determine group field
    if any(r.get("problem_id", "") for r in rows):
        group_ids = [r.get("problem_id", f"_row_{i}") for i, r in enumerate(rows)]
        group_field = "problem_id"
    elif any(r.get("case_id", "") for r in rows):
        group_ids = [r.get("case_id", f"_row_{i}") for i, r in enumerate(rows)]
        group_field = "case_id"
    else:
        from sklearn.model_selection import StratifiedKFold
        msg = "No problem_id or case_id field; falling back to StratifiedKFold (no grouping)."
        warnings.warn(msg)
        return (
            StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=seed),
            None, None, msg,
        )

    # Try StratifiedGroupKFold first (sklearn >= 0.24)
    try:
        from sklearn.model_selection import StratifiedGroupKFold
        cv = StratifiedGroupKFold(n_splits=n_folds, shuffle=True, random_state=seed)
        return cv, group_ids, group_field, None
    except Exception as e1:
        pass

    # Fallback to GroupKFold
    try:
        from sklearn.model_selection import GroupKFold
        cv = GroupKFold(n_splits=n_folds)
        msg = f"StratifiedGroupKFold unavailable; using GroupKFold (not stratified). group={group_field!r}"
        warnings.warn(msg)
        return cv, group_ids, group_field, msg
    except Exception as e2:
        from sklearn.model_selection import StratifiedKFold
        msg = f"Grouped CV failed ({e2}); falling back to StratifiedKFold without grouping."
        warnings.warn(msg)
        return (
            StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=seed),
            None, None, msg,
        )


def _threshold_sweep(y_true: list, proba_ready: list) -> dict:
    """Post-hoc diagnostic sweep on all OOF predictions combined."""
    from sklearn.metrics import (
        f1_score, precision_score, recall_score, accuracy_score, confusion_matrix,
    )
    import numpy as np

    best_threshold = 0.5
    best_ready_f1 = -1.0
    sweep_rows = []

    for t_int in range(5, 100, 5):
        thresh = t_int / 100.0
        preds_t = [1 if s >= thresh else 0 for s in proba_ready]
        rf1 = f1_score(y_true, preds_t, pos_label=1, zero_division=0)
        rp = precision_score(y_true, preds_t, pos_label=1, zero_division=0)
        rr = recall_score(y_true, preds_t, pos_label=1, zero_division=0)
        mf1 = f1_score(y_true, preds_t, average="macro", zero_division=0)
        sweep_rows.append({
            "threshold": thresh,
            "ready_precision": round(float(rp), 4),
            "ready_recall": round(float(rr), 4),
            "ready_f1": round(float(rf1), 4),
            "macro_f1": round(float(mf1), 4),
        })
        if rf1 > best_ready_f1:
            best_ready_f1 = rf1
            best_threshold = thresh

    preds_best = [1 if s >= best_threshold else 0 for s in proba_ready]
    best_cm = confusion_matrix(y_true, preds_best, labels=[0, 1]).tolist()
    best_acc = float(accuracy_score(y_true, preds_best))
    best_mf1 = float(f1_score(y_true, preds_best, average="macro", zero_division=0))
    best_rp = float(precision_score(y_true, preds_best, pos_label=1, zero_division=0))
    best_rr = float(recall_score(y_true, preds_best, pos_label=1, zero_division=0))

    return {
        "note": (
            "Post-hoc diagnostic sweep on all OOF predictions combined — "
            "threshold chosen on the same OOF data used for reporting; "
            "optimistically biased. Use for exploration, not as unbiased estimate."
        ),
        "best_threshold": best_threshold,
        "best_ready_f1": round(best_ready_f1, 4),
        "best_ready_precision": round(best_rp, 4),
        "best_ready_recall": round(best_rr, 4),
        "best_accuracy": round(best_acc, 4),
        "best_macro_f1": round(best_mf1, 4),
        "best_confusion_matrix": {
            "labels": [0, 1],
            "label_names": ["not_ready", "ready"],
            "matrix": best_cm,
            "note": "rows=true, cols=predicted; labels=[0=not_ready, 1=ready]",
        },
        "sweep": sweep_rows,
    }


def train_and_evaluate(
    rows: list[dict],
    label_field: str,
    seed: int,
    use_grouped_cv: bool = False,
    do_threshold_sweep: bool = False,
) -> tuple[dict, list[dict], object, object]:
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression
        from sklearn.model_selection import cross_val_predict
        from sklearn.metrics import (
            accuracy_score, f1_score, classification_report,
            confusion_matrix, average_precision_score,
        )
        import joblib
    except ImportError as e:
        print(f"ERROR: sklearn/joblib not installed: {e}", file=sys.stderr)
        sys.exit(1)

    texts = [r["feature_text"] for r in rows]
    labels = [r[label_field] for r in rows]
    row_ids = [r.get("row_id", str(i)) for i, r in enumerate(rows)]

    unique_labels = sorted(set(labels))
    n = len(rows)
    label_counter = Counter(labels)

    # Number of CV folds — cap at 5, must be ≥ 2 per class
    n_folds = min(5, min(label_counter.values()))
    use_full_fit_only = n_folds < 2

    vectorizer = TfidfVectorizer(
        ngram_range=(1, 2), max_features=500, sublinear_tf=True
    )
    clf = LogisticRegression(
        max_iter=1000, random_state=seed, class_weight="balanced"
    )

    X = vectorizer.fit_transform(texts)
    y = labels

    proba_scores = None  # OOF probability for class 1 (ready)
    cv_note = ""
    grouped_cv_warning = None
    group_field_used = None

    if use_full_fit_only:
        warnings.warn("Too few samples per class for CV; using train=test.")
        clf.fit(X, y)
        preds = clf.predict(X)
        proba_scores = clf.predict_proba(X)[:, 1].tolist()
        cv_note = "train==test (too few samples for CV)"
    else:
        cv, group_ids, group_field_used, grouped_cv_warning = _build_cv(
            rows, n_folds, seed, use_grouped_cv
        )
        cv_kwargs = {"groups": group_ids} if group_ids is not None else {}
        cv_note_parts = [
            type(cv).__name__,
            f"n_splits={n_folds}",
        ]
        if group_field_used:
            cv_note_parts.append(f"group_field={group_field_used!r}")
        cv_note = f"{', '.join(cv_note_parts)}"

        preds = cross_val_predict(clf, X, y, cv=cv, **cv_kwargs)
        try:
            proba_raw = cross_val_predict(
                clf, X, y, cv=cv, method="predict_proba", **cv_kwargs
            )
            proba_scores = proba_raw[:, 1].tolist()
        except Exception as e:
            warnings.warn(f"predict_proba not available in CV: {e}. PR-AUC skipped.")
            proba_scores = None

    # Default metrics (threshold = 0.5 implied by preds)
    acc = accuracy_score(y, preds)
    f1_macro = f1_score(y, preds, average="macro", labels=unique_labels, zero_division=0)
    clf_report = classification_report(y, preds, labels=unique_labels, zero_division=0)
    cm = confusion_matrix(y, preds, labels=[0, 1]).tolist()

    # PR-AUC for ready class (label=1)
    pr_auc = None
    if proba_scores is not None:
        try:
            y_binary = [1 if lbl == 1 else 0 for lbl in y]
            pr_auc = round(float(average_precision_score(y_binary, proba_scores)), 4)
        except Exception as e:
            warnings.warn(f"PR-AUC computation failed: {e}")

    # Threshold sweep
    threshold_sweep_result = None
    if do_threshold_sweep and proba_scores is not None:
        y_binary = [1 if lbl == 1 else 0 for lbl in y]
        threshold_sweep_result = _threshold_sweep(y_binary, proba_scores)

    # Final fit on full data for model persistence
    clf.fit(X, y)

    metrics = {
        "n_samples": n,
        "n_folds_or_mode": cv_note,
        "grouped_cv": use_grouped_cv,
        "group_field": group_field_used,
        "grouped_cv_warning": grouped_cv_warning,
        "accuracy": round(float(acc), 4),
        "f1_macro": round(float(f1_macro), 4),
        "pr_auc_ready": pr_auc,
        "confusion_matrix": {
            "labels": [0, 1],
            "label_names": ["not_ready", "ready"],
            "matrix": cm,
            "note": "rows=true, cols=predicted; labels=[0=not_ready, 1=ready]",
        },
        "classification_report": clf_report,
        "threshold_sweep": threshold_sweep_result,
        "label_counts": dict(label_counter),
        "warning": TINY_DATASET_WARNING,
    }

    predictions = [
        {
            "row_id": row_ids[i],
            "label_true": int(labels[i]),
            "label_pred": int(preds[i]),
            "proba_ready": round(float(proba_scores[i]), 4) if proba_scores is not None else None,
        }
        for i in range(n)
    ]

    return metrics, predictions, vectorizer, clf


def write_report(
    output_dir: pathlib.Path,
    mode: str,
    dry: dict | None,
    metrics: dict | None,
    dataset_path: pathlib.Path,
) -> None:
    lines = [
        "# RelationReady Baseline Trainer Report",
        "",
        f"- **Mode:** `{mode}`",
        f"- **Dataset:** `{dataset_path}`",
        f"- **Generated:** {datetime.now(timezone.utc).isoformat()}",
        "",
        f"## {TINY_DATASET_WARNING}",
        "",
    ]

    if dry:
        lines += [
            "## Dry-run validation",
            "",
            f"- Total rows: {dry['total_rows']}",
            f"- Empty feature_text: {dry['empty_feature_text']}",
            f"- Label counts: {dry['label_counts']}",
            f"- Split counts: {dry['split_counts']}",
        ]
        if dry["leakage_issues"]:
            lines += ["", "### ⛔ Leakage issues detected", ""]
            for issue in dry["leakage_issues"]:
                lines.append(f"- {issue}")
        else:
            lines.append("- **Leakage check: PASSED** — no forbidden columns in feature_text.")

    if metrics:
        ts = metrics.get("threshold_sweep")
        best_thresh = ts["best_threshold"] if ts else 0.5
        thresh_note = (
            f"threshold sweep (best={best_thresh}, post-hoc diagnostic)"
            if ts else "default threshold=0.5"
        )
        cm_info = metrics.get("confusion_matrix", {})
        cm = cm_info.get("matrix", [])

        lines += [
            "",
            "## Training results",
            "",
            f"- Evaluation mode: `{metrics['n_folds_or_mode']}`",
            f"- Grouped CV: `{metrics['grouped_cv']}`"
            + (f" (group field: `{metrics['group_field']}`)" if metrics.get("group_field") else ""),
            f"- Threshold policy: {thresh_note}",
            f"- Accuracy: `{metrics['accuracy']}`",
            f"- F1 macro: `{metrics['f1_macro']}`",
            f"- PR-AUC (ready class): `{metrics.get('pr_auc_ready', 'N/A')}`",
            "",
            "### Classification report (threshold=0.5)",
            "",
            "```",
            metrics["classification_report"].strip(),
            "```",
            "",
        ]

        if cm:
            lines += [
                "### Confusion matrix (threshold=0.5)",
                "",
                "```",
                "                  pred not_ready   pred ready",
                f"true not_ready       {cm[0][0]:>10}   {cm[0][1]:>10}",
                f"true ready           {cm[1][0]:>10}   {cm[1][1]:>10}",
                "```",
                "",
            ]

        if ts:
            best_cm = ts["best_confusion_matrix"]["matrix"]
            lines += [
                f"### Threshold sweep (best threshold={ts['best_threshold']})",
                "",
                f"> {ts['note']}",
                "",
                f"- Best ready F1: `{ts['best_ready_f1']}`",
                f"- Best ready precision: `{ts['best_ready_precision']}`",
                f"- Best ready recall: `{ts['best_ready_recall']}`",
                f"- Best macro F1: `{ts['best_macro_f1']}`",
                f"- Best accuracy: `{ts['best_accuracy']}`",
                "",
                "Confusion matrix at best threshold:",
                "",
                "```",
                "                  pred not_ready   pred ready",
                f"true not_ready       {best_cm[0][0]:>10}   {best_cm[0][1]:>10}",
                f"true ready           {best_cm[1][0]:>10}   {best_cm[1][1]:>10}",
                "```",
                "",
            ]

        if metrics.get("grouped_cv_warning"):
            lines += [
                f"⚠ Grouped CV warning: {metrics['grouped_cv_warning']}",
                "",
            ]

        lines.append("> Results above are on small data and must not be used for research claims.")

    (output_dir / "training_report.md").write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="RelationReady baseline trainer")
    parser.add_argument("--dataset-jsonl", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--mode", required=True, choices=["dry_run", "train"])
    parser.add_argument("--label-field", default="label")
    parser.add_argument("--seed", type=int, default=20260514)
    parser.add_argument(
        "--grouped-cv",
        action="store_true",
        help="Group CV folds by problem_id (or case_id) to prevent leakage across related rows.",
    )
    parser.add_argument(
        "--threshold-sweep",
        action="store_true",
        help="Sweep decision threshold 0.05–0.95 to maximise ready-class F1 (post-hoc diagnostic).",
    )
    args = parser.parse_args(argv)

    dataset_path = pathlib.Path(args.dataset_jsonl)
    output_dir = pathlib.Path(args.output_dir)

    if not dataset_path.exists():
        print(f"ERROR: dataset not found: {dataset_path}", file=sys.stderr)
        return 1

    output_dir.mkdir(parents=True, exist_ok=True)

    rows = load_jsonl(dataset_path)
    if not rows:
        print("ERROR: dataset is empty.", file=sys.stderr)
        return 1

    print(TINY_DATASET_WARNING)
    print(f"Mode: {args.mode} | Rows: {len(rows)} | grouped-cv: {args.grouped_cv} | threshold-sweep: {args.threshold_sweep}")

    dry = dry_run(rows, args.label_field)
    print(f"Labels: {dry['label_counts']}")
    print(f"Splits: {dry['split_counts']}")

    if dry["leakage_issues"]:
        print("LEAKAGE ISSUES DETECTED:", file=sys.stderr)
        for issue in dry["leakage_issues"]:
            print(f"  {issue}", file=sys.stderr)
        return 1
    print("✓ Leakage check passed.")

    if dry["empty_feature_text"] > 0:
        print(f"WARNING: {dry['empty_feature_text']} rows have empty feature_text.")

    metrics = None
    if args.mode == "dry_run":
        print("Dry-run complete. No model trained.")
        dry_metrics = {
            "mode": "dry_run",
            "total_rows": dry["total_rows"],
            "label_counts": dry["label_counts"],
            "split_counts": dry["split_counts"],
            "leakage_issues": dry["leakage_issues"],
            "warning": TINY_DATASET_WARNING,
        }
        (output_dir / "metrics.json").write_text(
            json.dumps(dry_metrics, indent=2), encoding="utf-8"
        )
        write_report(output_dir, args.mode, dry, None, dataset_path)
        (output_dir / "predictions.jsonl").write_text("", encoding="utf-8")

    else:  # train
        try:
            metrics, predictions, vectorizer, clf = train_and_evaluate(
                rows,
                args.label_field,
                args.seed,
                use_grouped_cv=args.grouped_cv,
                do_threshold_sweep=args.threshold_sweep,
            )
        except Exception as e:
            print(f"ERROR during training: {e}", file=sys.stderr)
            import traceback; traceback.print_exc()
            return 1

        # Save metrics JSON (exclude verbose classification_report string)
        metrics_json = {k: v for k, v in metrics.items() if k != "classification_report"}
        (output_dir / "metrics.json").write_text(
            json.dumps(metrics_json, indent=2), encoding="utf-8"
        )

        with open(output_dir / "predictions.jsonl", "w", encoding="utf-8") as f:
            for p in predictions:
                f.write(json.dumps(p) + "\n")

        try:
            import joblib
            joblib.dump({"vectorizer": vectorizer, "clf": clf}, output_dir / "model.joblib")
            print("✓ model.joblib saved.")
        except Exception as e:
            print(f"WARNING: could not save model.joblib: {e}")

        write_report(output_dir, args.mode, dry, metrics, dataset_path)
        print(f"Accuracy: {metrics['accuracy']}  F1-macro: {metrics['f1_macro']}  PR-AUC-ready: {metrics.get('pr_auc_ready')}")
        print(f"Eval mode: {metrics['n_folds_or_mode']}")

        ts = metrics.get("threshold_sweep")
        if ts:
            print(f"Threshold sweep best: threshold={ts['best_threshold']}  ready-F1={ts['best_ready_f1']}  macro-F1={ts['best_macro_f1']}")

    print(f"Output dir: {output_dir}")
    print("✓ No APIs called.")
    print("✓ No outputs staged or committed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
