"""Lightweight sklearn baseline trainer for the RelationReady binary verifier.

Uses TF-IDF + LogisticRegression (or LinearSVC) on feature_text.
Intended as a tiny smoke baseline only — NOT a production verifier.

Usage:
    # Dry run (validate dataset, no training):
    python3 scripts/train_relation_verifier_baseline.py \
        --dataset-jsonl outputs/.../train_rows.jsonl \
        --output-dir outputs/relation_verifier_baseline_dryrun_<STAMP> \
        --mode dry_run

    # Tiny local train (finishes quickly, no tmux needed for 33 rows):
    python3 scripts/train_relation_verifier_baseline.py \
        --dataset-jsonl outputs/.../train_rows.jsonl \
        --output-dir outputs/relation_verifier_baseline_train_<STAMP> \
        --mode train \
        --seed 20260514
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


def train_and_evaluate(
    rows: list[dict], label_field: str, seed: int
) -> tuple[dict, list[dict]]:
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression
        from sklearn.model_selection import StratifiedKFold, cross_val_predict
        from sklearn.metrics import accuracy_score, f1_score, classification_report
        import joblib
    except ImportError as e:
        print(f"ERROR: sklearn/joblib not installed: {e}", file=sys.stderr)
        sys.exit(1)

    texts = [r["feature_text"] for r in rows]
    labels = [r[label_field] for r in rows]
    row_ids = [r.get("row_id", str(i)) for i, r in enumerate(rows)]

    unique_labels = sorted(set(labels))
    n = len(rows)

    # With very few samples, cap cv folds
    n_folds = min(3, min(Counter(labels).values()))
    if n_folds < 2:
        # Can't do CV, just fit/predict on full set with a warning
        warnings.warn("Too few samples per class for cross-validation; using train=test.")
        n_folds = None

    vectorizer = TfidfVectorizer(
        ngram_range=(1, 2), max_features=500, sublinear_tf=True
    )
    clf = LogisticRegression(
        max_iter=1000, random_state=seed, class_weight="balanced"
    )

    X = vectorizer.fit_transform(texts)
    y = labels

    if n_folds is not None:
        cv = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=seed)
        preds = cross_val_predict(clf, X, y, cv=cv)
        cv_note = f"StratifiedKFold(n_splits={n_folds})"
    else:
        clf.fit(X, y)
        preds = clf.predict(X)
        cv_note = "train==test (too few samples for CV)"

    acc = accuracy_score(y, preds)
    f1_macro = f1_score(y, preds, average="macro", labels=unique_labels, zero_division=0)
    clf_report = classification_report(y, preds, labels=unique_labels, zero_division=0)

    # Final fit for model persistence
    clf.fit(X, y)

    metrics = {
        "n_samples": n,
        "n_folds_or_mode": cv_note,
        "accuracy": round(acc, 4),
        "f1_macro": round(f1_macro, 4),
        "label_counts": dict(Counter(labels)),
        "classification_report": clf_report,
        "warning": TINY_DATASET_WARNING,
    }

    predictions = [
        {
            "row_id": row_ids[i],
            "label_true": int(labels[i]) if hasattr(labels[i], "__int__") else labels[i],
            "label_pred": int(preds[i]) if hasattr(preds[i], "__int__") else preds[i],
        }
        for i in range(len(rows))
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
        lines += [
            "",
            "## Training results",
            "",
            f"- Evaluation mode: `{metrics['n_folds_or_mode']}`",
            f"- Accuracy: `{metrics['accuracy']}`",
            f"- F1 macro: `{metrics['f1_macro']}`",
            "",
            "```",
            metrics["classification_report"].strip(),
            "```",
            "",
            "> Results above are on tiny data and must not be used for research claims.",
        ]

    (output_dir / "training_report.md").write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="RelationReady baseline trainer")
    parser.add_argument("--dataset-jsonl", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--mode", required=True, choices=["dry_run", "train"])
    parser.add_argument("--label-field", default="label")
    parser.add_argument("--seed", type=int, default=20260514)
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
    print(f"Mode: {args.mode} | Rows: {len(rows)}")

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
        # Write dry-run metrics
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
        # Empty predictions
        (output_dir / "predictions.jsonl").write_text("", encoding="utf-8")

    else:  # train
        try:
            metrics, predictions, vectorizer, clf = train_and_evaluate(
                rows, args.label_field, args.seed
            )
        except Exception as e:
            print(f"ERROR during training: {e}", file=sys.stderr)
            return 1

        (output_dir / "metrics.json").write_text(
            json.dumps(
                {k: v for k, v in metrics.items() if k != "classification_report"},
                indent=2,
            ),
            encoding="utf-8",
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
        print(f"Accuracy: {metrics['accuracy']}  F1-macro: {metrics['f1_macro']}")
        print(f"Eval mode: {metrics['n_folds_or_mode']}")

    print(f"Output dir: {output_dir}")
    print("✓ No APIs called.")
    print("✓ No outputs staged or committed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
