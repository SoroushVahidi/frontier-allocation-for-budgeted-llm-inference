"""Frozen sentence-embedding baseline trainer for the RelationReady binary verifier.

Embeds feature_text with a frozen SentenceTransformer model, then trains a
LogisticRegression or LinearSVC on top.  Intended as a direct apples-to-apples
comparison with the TF-IDF baseline under the same grouped-CV protocol.

Usage:
    # Dry run (validate dataset/model config, no embedding/training):
    python3 scripts/train_relation_verifier_embedding_baseline.py \
        --dataset-jsonl outputs/.../training_dataset.jsonl \
        --output-dir outputs/relation_verifier_embedding_dryrun_<STAMP> \
        --mode dry_run

    # Train with grouped CV and threshold sweep:
    python3 scripts/train_relation_verifier_embedding_baseline.py \
        --dataset-jsonl outputs/.../training_dataset.jsonl \
        --output-dir outputs/relation_verifier_embedding_train_<STAMP> \
        --model-name sentence-transformers/all-MiniLM-L6-v2 \
        --classifier logreg \
        --mode train \
        --seed 20260516 \
        --grouped-cv \
        --threshold-sweep \
        --cache-embeddings
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


def dry_run_validate(rows: list[dict], label_field: str, model_name: str) -> dict:
    labels = [r.get(label_field) for r in rows]
    label_counts = Counter(labels)
    leakage_issues = check_leakage(rows)
    split_counts = Counter(r.get("split_group_id", "") for r in rows)
    empty_ft = sum(1 for r in rows if not r.get("feature_text", "").strip())
    try:
        import sentence_transformers  # noqa: F401
        st_available = True
    except ImportError:
        st_available = False
    return {
        "total_rows": len(rows),
        "label_counts": dict(label_counts),
        "split_counts": dict(split_counts),
        "leakage_issues": leakage_issues,
        "empty_feature_text": empty_ft,
        "model_name": model_name,
        "sentence_transformers_available": st_available,
    }


def _resolve_device(device_arg: str) -> str:
    if device_arg == "cpu":
        return "cpu"
    if device_arg == "cuda":
        return "cuda"
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"


def _embed(
    texts: list[str],
    model_name: str,
    device: str,
    batch_size: int,
    output_dir: pathlib.Path,
    use_cache: bool,
) -> "np.ndarray":
    import numpy as np

    cache_path = output_dir / "embeddings_cache.npy"
    if use_cache and cache_path.exists():
        print(f"Loading cached embeddings from {cache_path}")
        return np.load(str(cache_path))

    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        print(
            "ERROR: sentence_transformers not installed. "
            "Run: pip install sentence-transformers",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Loading model: {model_name} (device={device})")
    model = SentenceTransformer(model_name, device=device)
    print(f"Embedding {len(texts)} texts (batch_size={batch_size}) ...")
    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=False,
    )

    if use_cache:
        output_dir.mkdir(parents=True, exist_ok=True)
        np.save(str(cache_path), embeddings)
        print(f"Embeddings cached to {cache_path}")

    return embeddings


def _build_cv(rows: list[dict], n_folds: int, seed: int, use_grouped_cv: bool):
    """Return (cv_object, groups_array_or_None, group_field_used, warning_msg)."""
    if not use_grouped_cv:
        from sklearn.model_selection import StratifiedKFold
        return (
            StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=seed),
            None, None, None,
        )

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

    try:
        from sklearn.model_selection import StratifiedGroupKFold
        cv = StratifiedGroupKFold(n_splits=n_folds, shuffle=True, random_state=seed)
        return cv, group_ids, group_field, None
    except Exception:
        pass

    try:
        from sklearn.model_selection import GroupKFold
        cv = GroupKFold(n_splits=n_folds)
        msg = (
            f"StratifiedGroupKFold unavailable; using GroupKFold (not stratified). "
            f"group={group_field!r}"
        )
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


def _threshold_sweep(y_true: list, scores: list) -> dict:
    """Post-hoc diagnostic sweep on all OOF predictions combined."""
    from sklearn.metrics import (
        f1_score, precision_score, recall_score, accuracy_score, confusion_matrix,
    )

    best_threshold = 0.5
    best_ready_f1 = -1.0
    sweep_rows = []

    for t_int in range(5, 100, 5):
        thresh = t_int / 100.0
        preds_t = [1 if s >= thresh else 0 for s in scores]
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

    preds_best = [1 if s >= best_threshold else 0 for s in scores]
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


def _build_classifier(classifier_name: str, seed: int):
    from sklearn.linear_model import LogisticRegression
    from sklearn.svm import LinearSVC

    if classifier_name == "logreg":
        return LogisticRegression(max_iter=1000, random_state=seed, class_weight="balanced")
    elif classifier_name == "linear_svm":
        return LinearSVC(max_iter=2000, random_state=seed, class_weight="balanced")
    else:
        raise ValueError(f"Unknown classifier: {classifier_name!r}")


def train_and_evaluate(
    rows: list[dict],
    embeddings,
    label_field: str,
    classifier_name: str,
    seed: int,
    use_grouped_cv: bool = False,
    do_threshold_sweep: bool = False,
) -> tuple[dict, list[dict]]:
    from sklearn.metrics import (
        accuracy_score, f1_score, classification_report,
        confusion_matrix, average_precision_score,
    )
    from sklearn.model_selection import cross_val_predict

    labels = [r[label_field] for r in rows]
    row_ids = [r.get("row_id", str(i)) for i, r in enumerate(rows)]

    unique_labels = sorted(set(labels))
    n = len(rows)
    label_counter = Counter(labels)

    n_folds = min(5, min(label_counter.values()))
    use_full_fit_only = n_folds < 2

    clf = _build_classifier(classifier_name, seed)
    X = embeddings
    y = labels

    score_col = "score_ready"
    scores_oof = None
    cv_note = ""
    grouped_cv_warning = None
    group_field_used = None

    if use_full_fit_only:
        warnings.warn("Too few samples per class for CV; using train=test.")
        clf.fit(X, y)
        preds = clf.predict(X)
        if hasattr(clf, "predict_proba"):
            scores_oof = clf.predict_proba(X)[:, 1].tolist()
        else:
            scores_oof = clf.decision_function(X).tolist()
        cv_note = "train==test (too few samples for CV)"
    else:
        cv, group_ids, group_field_used, grouped_cv_warning = _build_cv(
            rows, n_folds, seed, use_grouped_cv
        )
        cv_kwargs = {"groups": group_ids} if group_ids is not None else {}
        cv_note_parts = [type(cv).__name__, f"n_splits={n_folds}"]
        if group_field_used:
            cv_note_parts.append(f"group_field={group_field_used!r}")
        cv_note = ", ".join(cv_note_parts)

        preds = cross_val_predict(clf, X, y, cv=cv, **cv_kwargs)

        if hasattr(clf, "predict_proba"):
            try:
                proba_raw = cross_val_predict(
                    clf, X, y, cv=cv, method="predict_proba", **cv_kwargs
                )
                scores_oof = proba_raw[:, 1].tolist()
            except Exception as e:
                warnings.warn(f"predict_proba not available in CV: {e}. Trying decision_function.")
        if scores_oof is None and hasattr(clf, "decision_function"):
            try:
                dec_raw = cross_val_predict(
                    clf, X, y, cv=cv, method="decision_function", **cv_kwargs
                )
                scores_oof = dec_raw.tolist()
            except Exception as e:
                warnings.warn(f"decision_function failed: {e}. Scores unavailable.")

    acc = accuracy_score(y, preds)
    f1_macro = f1_score(y, preds, average="macro", labels=unique_labels, zero_division=0)
    clf_report = classification_report(y, preds, labels=unique_labels, zero_division=0)
    cm = confusion_matrix(y, preds, labels=[0, 1]).tolist()

    pr_auc = None
    if scores_oof is not None:
        try:
            y_binary = [1 if lbl == 1 else 0 for lbl in y]
            pr_auc = round(float(average_precision_score(y_binary, scores_oof)), 4)
        except Exception as e:
            warnings.warn(f"PR-AUC computation failed: {e}")

    threshold_sweep_result = None
    if do_threshold_sweep and scores_oof is not None:
        y_binary = [1 if lbl == 1 else 0 for lbl in y]
        threshold_sweep_result = _threshold_sweep(y_binary, scores_oof)

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
    }

    predictions = [
        {
            "row_id": row_ids[i],
            "label_true": int(labels[i]),
            "label_pred": int(preds[i]),
            score_col: round(float(scores_oof[i]), 4) if scores_oof is not None else None,
        }
        for i in range(n)
    ]

    return metrics, predictions


def write_report(
    output_dir: pathlib.Path,
    mode: str,
    dry: dict | None,
    metrics: dict | None,
    dataset_path: pathlib.Path,
    model_name: str,
    classifier_name: str,
) -> None:
    lines = [
        "# RelationReady Embedding Baseline Trainer Report",
        "",
        f"- **Mode:** `{mode}`",
        f"- **Dataset:** `{dataset_path}`",
        f"- **Embedding model:** `{model_name}`",
        f"- **Classifier:** `{classifier_name}`",
        f"- **Generated:** {datetime.now(timezone.utc).isoformat()}",
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
            f"- sentence_transformers available: {dry.get('sentence_transformers_available')}",
        ]
        if dry["leakage_issues"]:
            lines += ["", "### Leakage issues detected", ""]
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
                f"Grouped CV warning: {metrics['grouped_cv_warning']}",
                "",
            ]

        lines.append("> Results above must not be used for final research claims without proper held-out evaluation.")

    (output_dir / "training_report.md").write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Frozen sentence-embedding baseline for RelationReady verifier"
    )
    parser.add_argument("--dataset-jsonl", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument(
        "--model-name",
        default="sentence-transformers/all-MiniLM-L6-v2",
        help="HuggingFace model identifier for SentenceTransformer",
    )
    parser.add_argument(
        "--classifier",
        default="logreg",
        choices=["logreg", "linear_svm"],
        help="Downstream classifier to train on embeddings",
    )
    parser.add_argument("--mode", required=True, choices=["dry_run", "train"])
    parser.add_argument("--label-field", default="label")
    parser.add_argument("--seed", type=int, default=20260516)
    parser.add_argument(
        "--grouped-cv",
        action="store_true",
        help="Group CV folds by problem_id/case_id to prevent group leakage",
    )
    parser.add_argument(
        "--threshold-sweep",
        action="store_true",
        help="Sweep decision threshold 0.05–0.95 (post-hoc diagnostic)",
    )
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument(
        "--device",
        default="auto",
        choices=["auto", "cpu", "cuda"],
        help="Device for embedding inference",
    )
    parser.add_argument(
        "--cache-embeddings",
        action="store_true",
        help="Cache embeddings as embeddings_cache.npy under --output-dir",
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

    print(
        f"Mode: {args.mode} | Rows: {len(rows)} | model: {args.model_name} "
        f"| classifier: {args.classifier} | grouped-cv: {args.grouped_cv} "
        f"| threshold-sweep: {args.threshold_sweep}"
    )

    dry = dry_run_validate(rows, args.label_field, args.model_name)
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
        print("Dry-run complete. No embedding or model training performed.")
        dry_metrics = {
            "mode": "dry_run",
            "total_rows": dry["total_rows"],
            "label_counts": dry["label_counts"],
            "split_counts": dry["split_counts"],
            "leakage_issues": dry["leakage_issues"],
            "model_name": args.model_name,
            "classifier": args.classifier,
            "sentence_transformers_available": dry["sentence_transformers_available"],
        }
        (output_dir / "metrics.json").write_text(
            json.dumps(dry_metrics, indent=2), encoding="utf-8"
        )
        write_report(
            output_dir, args.mode, dry, None, dataset_path,
            args.model_name, args.classifier,
        )
        (output_dir / "predictions.jsonl").write_text("", encoding="utf-8")

    else:  # train
        device = _resolve_device(args.device)
        print(f"Using device: {device}")

        try:
            embeddings = _embed(
                texts=[r["feature_text"] for r in rows],
                model_name=args.model_name,
                device=device,
                batch_size=args.batch_size,
                output_dir=output_dir,
                use_cache=args.cache_embeddings,
            )
        except SystemExit:
            return 1
        except Exception as e:
            print(f"ERROR during embedding: {e}", file=sys.stderr)
            import traceback; traceback.print_exc()
            return 1

        print(f"Embeddings shape: {embeddings.shape}")

        try:
            metrics, predictions = train_and_evaluate(
                rows=rows,
                embeddings=embeddings,
                label_field=args.label_field,
                classifier_name=args.classifier,
                seed=args.seed,
                use_grouped_cv=args.grouped_cv,
                do_threshold_sweep=args.threshold_sweep,
            )
        except Exception as e:
            print(f"ERROR during training: {e}", file=sys.stderr)
            import traceback; traceback.print_exc()
            return 1

        metrics_json = {k: v for k, v in metrics.items() if k != "classification_report"}
        (output_dir / "metrics.json").write_text(
            json.dumps(metrics_json, indent=2), encoding="utf-8"
        )

        with open(output_dir / "predictions.jsonl", "w", encoding="utf-8") as f:
            for p in predictions:
                f.write(json.dumps(p) + "\n")

        run_manifest = {
            "dataset_jsonl": str(dataset_path),
            "model_name": args.model_name,
            "classifier": args.classifier,
            "seed": args.seed,
            "grouped_cv": args.grouped_cv,
            "threshold_sweep": args.threshold_sweep,
            "batch_size": args.batch_size,
            "device": device,
            "cache_embeddings": args.cache_embeddings,
            "n_rows": len(rows),
            "embeddings_shape": list(embeddings.shape),
            "generated": datetime.now(timezone.utc).isoformat(),
        }
        (output_dir / "run_manifest.json").write_text(
            json.dumps(run_manifest, indent=2), encoding="utf-8"
        )

        write_report(
            output_dir, args.mode, dry, metrics, dataset_path,
            args.model_name, args.classifier,
        )

        print(
            f"Accuracy: {metrics['accuracy']}  "
            f"F1-macro: {metrics['f1_macro']}  "
            f"PR-AUC-ready: {metrics.get('pr_auc_ready')}"
        )
        print(f"Eval mode: {metrics['n_folds_or_mode']}")

        ts = metrics.get("threshold_sweep")
        if ts:
            print(
                f"Threshold sweep best: threshold={ts['best_threshold']}  "
                f"ready-F1={ts['best_ready_f1']}  macro-F1={ts['best_macro_f1']}"
            )

    print(f"Output dir: {output_dir}")
    print("✓ No APIs called.")
    print("✓ No outputs staged or committed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
