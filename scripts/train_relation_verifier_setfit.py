"""SetFit-style fine-tuning trainer for the RelationReady binary verifier.

Contrastively fine-tunes a SentenceTransformer encoder (SetFit) on each CV
fold's train split, then evaluates the fine-tuned model on the held-out fold.
Uses the same grouped-CV protocol as the frozen-embedding and TF-IDF baselines
for apples-to-apples comparison.

Requires: pip install setfit

Usage:
    # Dry run (validate dataset/model config, no training):
    python3 scripts/train_relation_verifier_setfit.py \
        --dataset-jsonl outputs/.../training_dataset.jsonl \
        --output-dir outputs/relation_verifier_setfit_dryrun_<STAMP> \
        --mode dry_run

    # Full train with grouped CV:
    python3 scripts/train_relation_verifier_setfit.py \
        --dataset-jsonl outputs/.../training_dataset.jsonl \
        --output-dir outputs/relation_verifier_setfit_mpnet_train_<STAMP> \
        --model-name sentence-transformers/all-mpnet-base-v2 \
        --mode train \
        --seed 20260516 \
        --grouped-cv \
        --threshold-sweep \
        --num-epochs 1 \
        --batch-size 8 \
        --num-iterations 5 \
        --device cuda
"""
from __future__ import annotations

# ── Compatibility shim: setfit 1.1.x imports default_logdir from transformers,
#    which was removed in transformers 5.x. Patch it before setfit loads. ──────
import transformers.training_args as _ta
if not hasattr(_ta, "default_logdir"):
    import datetime as _dt, os as _os
    def _default_logdir():
        return _os.path.join("runs", _dt.datetime.now().strftime("%b%d_%H-%M-%S"))
    _ta.default_logdir = _default_logdir
# ─────────────────────────────────────────────────────────────────────────────

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
        from setfit import SetFitModel  # noqa: F401
        setfit_available = True
    except Exception:
        setfit_available = False
    return {
        "total_rows": len(rows),
        "label_counts": dict(label_counts),
        "split_counts": dict(split_counts),
        "leakage_issues": leakage_issues,
        "empty_feature_text": empty_ft,
        "model_name": model_name,
        "setfit_available": setfit_available,
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


def _build_cv(rows: list[dict], n_folds: int, seed: int, use_grouped_cv: bool):
    """Return (cv, group_ids_or_None, group_field_used, warning_msg)."""
    if not use_grouped_cv:
        from sklearn.model_selection import StratifiedKFold
        return StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=seed), None, None, None

    if any(r.get("problem_id", "") for r in rows):
        group_ids = [r.get("problem_id", f"_row_{i}") for i, r in enumerate(rows)]
        group_field = "problem_id"
    elif any(r.get("case_id", "") for r in rows):
        group_ids = [r.get("case_id", f"_row_{i}") for i, r in enumerate(rows)]
        group_field = "case_id"
    else:
        from sklearn.model_selection import StratifiedKFold
        msg = "No problem_id or case_id; falling back to StratifiedKFold (no grouping)."
        warnings.warn(msg)
        return StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=seed), None, None, msg

    try:
        from sklearn.model_selection import StratifiedGroupKFold
        cv = StratifiedGroupKFold(n_splits=n_folds, shuffle=True, random_state=seed)
        return cv, group_ids, group_field, None
    except Exception:
        pass

    try:
        from sklearn.model_selection import GroupKFold
        msg = f"StratifiedGroupKFold unavailable; using GroupKFold. group={group_field!r}"
        warnings.warn(msg)
        return GroupKFold(n_splits=n_folds), group_ids, group_field, msg
    except Exception as e2:
        from sklearn.model_selection import StratifiedKFold
        msg = f"Grouped CV failed ({e2}); falling back to StratifiedKFold."
        warnings.warn(msg)
        return StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=seed), None, None, msg


def _threshold_sweep(y_true: list, scores: list) -> dict:
    from sklearn.metrics import f1_score, precision_score, recall_score, accuracy_score, confusion_matrix

    best_thresh, best_ready_f1 = 0.5, -1.0
    sweep_rows = []
    for t_int in range(5, 100, 5):
        thresh = t_int / 100.0
        preds_t = [1 if s >= thresh else 0 for s in scores]
        rf1 = f1_score(y_true, preds_t, pos_label=1, zero_division=0)
        rp  = precision_score(y_true, preds_t, pos_label=1, zero_division=0)
        rr  = recall_score(y_true, preds_t, pos_label=1, zero_division=0)
        mf1 = f1_score(y_true, preds_t, average="macro", zero_division=0)
        sweep_rows.append({
            "threshold": thresh,
            "ready_precision": round(float(rp), 4),
            "ready_recall": round(float(rr), 4),
            "ready_f1": round(float(rf1), 4),
            "macro_f1": round(float(mf1), 4),
        })
        if rf1 > best_ready_f1:
            best_ready_f1, best_thresh = rf1, thresh

    preds_best = [1 if s >= best_thresh else 0 for s in scores]
    best_cm  = confusion_matrix(y_true, preds_best, labels=[0, 1]).tolist()
    best_acc = float(accuracy_score(y_true, preds_best))
    best_mf1 = float(f1_score(y_true, preds_best, average="macro", zero_division=0))
    best_rp  = float(precision_score(y_true, preds_best, pos_label=1, zero_division=0))
    best_rr  = float(recall_score(y_true, preds_best, pos_label=1, zero_division=0))

    return {
        "note": (
            "Post-hoc diagnostic sweep on all OOF predictions combined — "
            "threshold chosen on the same OOF data; optimistically biased. "
            "Use for exploration, not as an unbiased estimate."
        ),
        "best_threshold": best_thresh,
        "best_ready_f1": round(best_ready_f1, 4),
        "best_ready_precision": round(best_rp, 4),
        "best_ready_recall": round(best_rr, 4),
        "best_accuracy": round(best_acc, 4),
        "best_macro_f1": round(best_mf1, 4),
        "best_confusion_matrix": {
            "labels": [0, 1],
            "label_names": ["not_ready", "ready"],
            "matrix": best_cm,
            "note": "rows=true, cols=predicted",
        },
        "sweep": sweep_rows,
    }


def _make_hf_dataset(texts: list[str], labels: list[int]):
    """Convert lists to a HuggingFace Dataset with 'text' and 'label' columns."""
    from datasets import Dataset
    return Dataset.from_dict({"text": texts, "label": labels})


def _train_fold(
    train_texts: list[str],
    train_labels: list[int],
    val_texts: list[str],
    model_name: str,
    device: str,
    num_epochs: int,
    batch_size: int,
    num_iterations: int,
    max_seq_length: int | None,
    body_learning_rate: float,
    head_learning_rate: float,
    samples_per_label: int,
    seed: int,
    output_dir: pathlib.Path,
    fold_idx: int,
) -> tuple[list[float], list[int]]:
    """Fine-tune a SetFit model on train fold, return (scores, preds) for val fold."""
    import torch
    from sentence_transformers import SentenceTransformer
    from setfit import SetFitModel, Trainer, TrainingArguments
    from sklearn.linear_model import LogisticRegression

    torch.manual_seed(seed + fold_idx)

    # Load via SentenceTransformer directly to avoid SetFitModel.from_pretrained
    # fetching config_setfit.json (absent on vanilla ST model repos, raises 404).
    # Provide an explicit head: from_pretrained always does this but direct
    # construction leaves model_head=None, causing AttributeError on trainer.train().
    st_body = SentenceTransformer(model_name, device=device)
    if max_seq_length is not None:
        st_body.max_seq_length = max_seq_length
    head = LogisticRegression(max_iter=1000, class_weight="balanced")
    model = SetFitModel(model_body=st_body, model_head=head)

    train_ds = _make_hf_dataset(train_texts, train_labels)

    args = TrainingArguments(
        output_dir=str(output_dir / f"fold_{fold_idx}_model"),
        num_epochs=num_epochs,
        batch_size=batch_size,
        num_iterations=num_iterations,
        body_learning_rate=body_learning_rate,
        head_learning_rate=head_learning_rate,
        samples_per_label=samples_per_label,
        seed=seed + fold_idx,
        show_progress_bar=True,
        report_to="none",
    )

    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=train_ds,
    )
    trainer.train()

    # Score val texts
    val_scores = model.predict_proba(val_texts)
    # predict_proba returns shape (n, 2); take column 1 (ready class)
    if hasattr(val_scores, "numpy"):
        val_scores = val_scores.numpy()
    import numpy as np
    val_scores = np.array(val_scores)
    if val_scores.ndim == 2:
        proba_ready = val_scores[:, 1].tolist()
    else:
        proba_ready = val_scores.tolist()

    val_preds = [1 if s >= 0.5 else 0 for s in proba_ready]
    return proba_ready, val_preds


def train_and_evaluate(
    rows: list[dict],
    label_field: str,
    model_name: str,
    device: str,
    num_epochs: int,
    batch_size: int,
    num_iterations: int,
    max_seq_length: int | None,
    body_learning_rate: float,
    head_learning_rate: float,
    samples_per_label: int,
    seed: int,
    use_grouped_cv: bool,
    do_threshold_sweep: bool,
    output_dir: pathlib.Path,
) -> tuple[dict, list[dict]]:
    import numpy as np
    from sklearn.metrics import (
        accuracy_score, f1_score, classification_report,
        confusion_matrix, average_precision_score,
    )

    texts  = [r["feature_text"] for r in rows]
    labels = [r[label_field] for r in rows]
    row_ids = [r.get("row_id", str(i)) for i, r in enumerate(rows)]

    unique_labels = sorted(set(labels))
    n = len(rows)
    label_counter = Counter(labels)
    n_folds = min(5, min(label_counter.values()))

    if n_folds < 2:
        raise ValueError(f"Too few samples per class for CV: {dict(label_counter)}")

    cv, group_ids, group_field_used, grouped_cv_warning = _build_cv(
        rows, n_folds, seed, use_grouped_cv
    )
    cv_kwargs = {"groups": group_ids} if group_ids is not None else {}
    cv_note = (
        f"{type(cv).__name__}, n_splits={n_folds}"
        + (f", group_field={group_field_used!r}" if group_field_used else "")
    )

    # OOF containers
    oof_proba   = [None] * n
    oof_pred    = [None] * n

    indices = np.arange(n)
    y_arr   = np.array(labels)
    groups_arr = np.array(group_ids) if group_ids is not None else None

    split_iter = cv.split(indices, y_arr, groups_arr) if groups_arr is not None else cv.split(indices, y_arr)

    for fold_idx, (train_idx, val_idx) in enumerate(split_iter):
        print(f"\n--- Fold {fold_idx + 1}/{n_folds} (train={len(train_idx)}, val={len(val_idx)}) ---")
        train_texts_f  = [texts[i] for i in train_idx]
        train_labels_f = [labels[i] for i in train_idx]
        val_texts_f    = [texts[i] for i in val_idx]

        proba_fold, preds_fold = _train_fold(
            train_texts=train_texts_f,
            train_labels=train_labels_f,
            val_texts=val_texts_f,
            model_name=model_name,
            device=device,
            num_epochs=num_epochs,
            batch_size=batch_size,
            num_iterations=num_iterations,
            max_seq_length=max_seq_length,
            body_learning_rate=body_learning_rate,
            head_learning_rate=head_learning_rate,
            samples_per_label=samples_per_label,
            seed=seed,
            output_dir=output_dir,
            fold_idx=fold_idx,
        )
        for local_i, global_i in enumerate(val_idx):
            oof_proba[global_i] = proba_fold[local_i]
            oof_pred[global_i]  = preds_fold[local_i]

    # Final OOF metrics
    y_binary = [1 if lbl == 1 else 0 for lbl in labels]

    acc    = accuracy_score(labels, oof_pred)
    f1_mac = f1_score(labels, oof_pred, average="macro", labels=unique_labels, zero_division=0)
    clf_report = classification_report(labels, oof_pred, labels=unique_labels, zero_division=0)
    cm = confusion_matrix(labels, oof_pred, labels=[0, 1]).tolist()

    pr_auc = None
    try:
        pr_auc = round(float(average_precision_score(y_binary, oof_proba)), 4)
    except Exception as e:
        warnings.warn(f"PR-AUC failed: {e}")

    ts_result = None
    if do_threshold_sweep:
        ts_result = _threshold_sweep(y_binary, oof_proba)

    metrics = {
        "n_samples": n,
        "n_folds_or_mode": cv_note,
        "grouped_cv": use_grouped_cv,
        "group_field": group_field_used,
        "grouped_cv_warning": grouped_cv_warning,
        "accuracy": round(float(acc), 4),
        "f1_macro": round(float(f1_mac), 4),
        "pr_auc_ready": pr_auc,
        "confusion_matrix": {
            "labels": [0, 1],
            "label_names": ["not_ready", "ready"],
            "matrix": cm,
            "note": "rows=true, cols=predicted; labels=[0=not_ready, 1=ready]",
        },
        "classification_report": clf_report,
        "threshold_sweep": ts_result,
        "label_counts": dict(label_counter),
        "model_name": model_name,
        "num_epochs": num_epochs,
        "batch_size": batch_size,
        "num_iterations": num_iterations,
        "body_learning_rate": body_learning_rate,
        "head_learning_rate": head_learning_rate,
        "samples_per_label": samples_per_label,
    }

    predictions = [
        {
            "row_id": row_ids[i],
            "label_true": int(labels[i]),
            "label_pred": int(oof_pred[i]),
            "proba_ready": round(float(oof_proba[i]), 4),
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
) -> None:
    lines = [
        "# RelationReady SetFit Trainer Report",
        "",
        f"- **Mode:** `{mode}`",
        f"- **Dataset:** `{dataset_path}`",
        f"- **Model:** `{model_name}`",
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
            f"- setfit available: {dry.get('setfit_available')}",
        ]
        if dry["leakage_issues"]:
            lines += ["", "### Leakage issues detected", ""]
            for issue in dry["leakage_issues"]:
                lines.append(f"- {issue}")
        else:
            lines.append("- **Leakage check: PASSED**")

    if metrics:
        ts  = metrics.get("threshold_sweep")
        cm_info = metrics.get("confusion_matrix", {})
        cm  = cm_info.get("matrix", [])
        best_thresh = ts["best_threshold"] if ts else 0.5
        thresh_note = (
            f"threshold sweep (best={best_thresh}, post-hoc diagnostic)"
            if ts else "default threshold=0.5"
        )

        lines += [
            "",
            "## Training results",
            "",
            f"- Evaluation mode: `{metrics['n_folds_or_mode']}`",
            f"- Grouped CV: `{metrics['grouped_cv']}`"
            + (f" (group field: `{metrics['group_field']}`)" if metrics.get("group_field") else ""),
            f"- SetFit num_epochs={metrics['num_epochs']}, "
            f"batch_size={metrics['batch_size']}, "
            f"num_iterations={metrics['num_iterations']}, "
            f"samples_per_label={metrics['samples_per_label']}, "
            f"body_lr={metrics['body_learning_rate']}, "
            f"head_lr={metrics['head_learning_rate']}",
            f"- Threshold policy: {thresh_note}",
            f"- Accuracy: `{metrics['accuracy']}`",
            f"- Macro F1: `{metrics['f1_macro']}`",
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
            bcm = ts["best_confusion_matrix"]["matrix"]
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
                f"true not_ready       {bcm[0][0]:>10}   {bcm[0][1]:>10}",
                f"true ready           {bcm[1][0]:>10}   {bcm[1][1]:>10}",
                "```",
                "",
            ]

        if metrics.get("grouped_cv_warning"):
            lines.append(f"Grouped CV warning: {metrics['grouped_cv_warning']}")

        lines.append("")
        lines.append("> OOF results. Do not use for final paper claims without held-out evaluation.")

    (output_dir / "training_report.md").write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SetFit trainer for RelationReady verifier")
    parser.add_argument("--dataset-jsonl", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--model-name", default="sentence-transformers/all-mpnet-base-v2")
    parser.add_argument("--mode", required=True, choices=["dry_run", "train"])
    parser.add_argument("--label-field", default="label")
    parser.add_argument("--seed", type=int, default=20260516)
    parser.add_argument("--grouped-cv", action="store_true")
    parser.add_argument("--num-folds", type=int, default=5)
    parser.add_argument("--num-epochs", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--num-iterations", type=int, default=5)
    parser.add_argument("--body-learning-rate", type=float, default=2e-5)
    parser.add_argument("--head-learning-rate", type=float, default=1e-2)
    parser.add_argument("--samples-per-label", type=int, default=2)
    parser.add_argument("--max-seq-length", type=int, default=None)
    parser.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])
    parser.add_argument("--threshold-sweep", action="store_true")
    parser.add_argument(
        "--limit-rows", type=int, default=None,
        help="Truncate dataset to this many rows (smoke tests only)",
    )
    args = parser.parse_args(argv)

    dataset_path = pathlib.Path(args.dataset_jsonl)
    output_dir   = pathlib.Path(args.output_dir)

    if not dataset_path.exists():
        print(f"ERROR: dataset not found: {dataset_path}", file=sys.stderr)
        return 1

    output_dir.mkdir(parents=True, exist_ok=True)

    rows = load_jsonl(dataset_path)
    if not rows:
        print("ERROR: dataset is empty.", file=sys.stderr)
        return 1

    if args.limit_rows is not None:
        rows = rows[: args.limit_rows]
        print(f"--limit-rows: using first {len(rows)} rows")

    print(
        f"Mode: {args.mode} | Rows: {len(rows)} | model: {args.model_name} "
        f"| grouped-cv: {args.grouped_cv} | epochs: {args.num_epochs} "
        f"| iterations: {args.num_iterations} | samples_per_label: {args.samples_per_label} "
        f"| body_lr: {args.body_learning_rate} | head_lr: {args.head_learning_rate}"
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

    if args.mode == "dry_run":
        print("Dry-run complete. No model fine-tuned.")
        dry_metrics = {
            "mode": "dry_run",
            "total_rows": dry["total_rows"],
            "label_counts": dry["label_counts"],
            "split_counts": dry["split_counts"],
            "leakage_issues": dry["leakage_issues"],
            "model_name": args.model_name,
            "setfit_available": dry["setfit_available"],
        }
        (output_dir / "metrics.json").write_text(
            json.dumps(dry_metrics, indent=2), encoding="utf-8"
        )
        write_report(output_dir, args.mode, dry, None, dataset_path, args.model_name)
        (output_dir / "predictions.jsonl").write_text("", encoding="utf-8")

    else:  # train
        device = _resolve_device(args.device)
        print(f"Using device: {device}")

        try:
            metrics, predictions = train_and_evaluate(
                rows=rows,
                label_field=args.label_field,
                model_name=args.model_name,
                device=device,
                num_epochs=args.num_epochs,
                batch_size=args.batch_size,
                num_iterations=args.num_iterations,
                max_seq_length=args.max_seq_length,
                body_learning_rate=args.body_learning_rate,
                head_learning_rate=args.head_learning_rate,
                samples_per_label=args.samples_per_label,
                seed=args.seed,
                use_grouped_cv=args.grouped_cv,
                do_threshold_sweep=args.threshold_sweep,
                output_dir=output_dir,
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
            "mode": args.mode,
            "seed": args.seed,
            "grouped_cv": args.grouped_cv,
            "threshold_sweep": args.threshold_sweep,
            "num_epochs": args.num_epochs,
            "batch_size": args.batch_size,
            "num_iterations": args.num_iterations,
            "body_learning_rate": args.body_learning_rate,
            "head_learning_rate": args.head_learning_rate,
            "samples_per_label": args.samples_per_label,
            "max_seq_length": args.max_seq_length,
            "device": device,
            "n_rows": len(rows),
            "generated": datetime.now(timezone.utc).isoformat(),
        }
        (output_dir / "run_manifest.json").write_text(
            json.dumps(run_manifest, indent=2), encoding="utf-8"
        )

        write_report(output_dir, args.mode, dry, metrics, dataset_path, args.model_name)

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
    print("✓ No provider APIs called.")
    print("✓ No outputs staged or committed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
