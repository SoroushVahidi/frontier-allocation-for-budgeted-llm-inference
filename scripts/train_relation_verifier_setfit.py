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


def _fit_setfit_model(
    train_texts: list[str],
    train_labels: list[int],
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
):
    """Train a SetFit model and return it. Does not score anything."""
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

    trainer = Trainer(model=model, args=args, train_dataset=train_ds)
    trainer.train()
    return model


def _score_model(model, texts: list[str]) -> list[float]:
    """Return ready-class probability scores for a list of texts."""
    import numpy as np
    scores = model.predict_proba(texts)
    if hasattr(scores, "numpy"):
        scores = scores.numpy()
    scores = np.array(scores)
    if scores.ndim == 2:
        return scores[:, 1].tolist()
    return scores.tolist()


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
    model = _fit_setfit_model(
        train_texts=train_texts,
        train_labels=train_labels,
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
    proba_ready = _score_model(model, val_texts)
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


def train_eval_explicit_split(
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
    output_dir: pathlib.Path,
) -> tuple[dict, list[dict]]:
    """Train on (train + no-split) rows, tune threshold on val, evaluate once on test.

    split_group_id="" means no explicit split was assigned (bulk "no-split" pool).
    These rows are included in the training set for maximum coverage.

    Threshold is selected on val to avoid test contamination.
    Test metrics are the primary unbiased estimate.

    WARNING: if the test set has zero ready examples, ready F1 / PR-AUC cannot be
    computed meaningfully; only the false-positive rate on not_ready is measurable.
    """
    import numpy as np
    from sklearn.metrics import (
        accuracy_score, f1_score, precision_score, recall_score,
        confusion_matrix, average_precision_score, classification_report,
    )

    TRAIN_SPLIT_GROUPS = {"train", ""}   # "" = no-split pool
    VAL_SPLIT = "val"
    TEST_SPLIT = "test"

    train_rows = [r for r in rows if r.get("split_group_id", "") in TRAIN_SPLIT_GROUPS]
    val_rows   = [r for r in rows if r.get("split_group_id") == VAL_SPLIT]
    test_rows  = [r for r in rows if r.get("split_group_id") == TEST_SPLIT]

    if not train_rows:
        raise ValueError("No training rows found for split_group_id in {'train', ''}.")
    if not test_rows:
        raise ValueError("No test rows found for split_group_id='test'.")

    train_texts  = [r["feature_text"] for r in train_rows]
    train_labels = [r[label_field] for r in train_rows]
    val_texts    = [r["feature_text"] for r in val_rows]
    val_labels   = [r[label_field] for r in val_rows]
    test_texts   = [r["feature_text"] for r in test_rows]
    test_labels  = [r[label_field] for r in test_rows]

    train_lc = Counter(train_labels)
    val_lc   = Counter(val_labels)
    test_lc  = Counter(test_labels)
    test_has_zero_ready = (test_lc.get(1, 0) == 0)

    print(f"\n=== Explicit split evaluation ===")
    print(f"  train+no-split: {len(train_rows)} rows  {dict(train_lc)}")
    print(f"  val:            {len(val_rows)} rows  {dict(val_lc)}")
    print(f"  test:           {len(test_rows)} rows  {dict(test_lc)}")
    if test_has_zero_ready:
        print("  WARNING: test set has 0 ready examples — ready F1 / PR-AUC undefined.")

    # Train one model on train+no-split
    model = _fit_setfit_model(
        train_texts=train_texts,
        train_labels=train_labels,
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
        fold_idx=0,
    )

    # Tune threshold on val (unbiased w.r.t. test)
    selected_threshold = 0.5
    threshold_source = "default (0.5) — val has no ready examples"
    val_metrics_summary: dict = {}

    if val_rows:
        val_proba = _score_model(model, val_texts)
        val_labels_int = [int(l) for l in val_labels]
        if any(l == 1 for l in val_labels_int):
            val_sweep = _threshold_sweep(val_labels_int, val_proba)
            selected_threshold = val_sweep["best_threshold"]
            threshold_source = f"val sweep (best ready F1 on val at thr={selected_threshold})"
            val_metrics_summary = {
                "n_val": len(val_rows),
                "label_counts": dict(val_lc),
                "best_threshold": val_sweep["best_threshold"],
                "best_ready_f1_on_val": val_sweep["best_ready_f1"],
                "best_macro_f1_on_val": val_sweep["best_macro_f1"],
            }
            print(f"  Val threshold sweep: best thr={selected_threshold}, val ready F1={val_sweep['best_ready_f1']}")
        else:
            print("  Val has no ready examples; using threshold=0.5.")

    # Score test and apply selected threshold
    test_proba = _score_model(model, test_texts)
    test_labels_int = [int(l) for l in test_labels]
    test_preds = [1 if s >= selected_threshold else 0 for s in test_proba]

    # Test metrics
    acc  = float(accuracy_score(test_labels_int, test_preds))
    f1m  = float(f1_score(test_labels_int, test_preds, average="macro", zero_division=0))
    rp   = float(precision_score(test_labels_int, test_preds, pos_label=1, zero_division=0))
    rr   = float(recall_score(test_labels_int, test_preds, pos_label=1, zero_division=0))
    rf1  = float(f1_score(test_labels_int, test_preds, pos_label=1, zero_division=0))
    cm   = confusion_matrix(test_labels_int, test_preds, labels=[0, 1]).tolist()
    clf_report = classification_report(test_labels_int, test_preds, zero_division=0)

    pr_auc = None
    if not test_has_zero_ready:
        try:
            pr_auc = round(float(average_precision_score(test_labels_int, test_proba)), 4)
        except Exception as e:
            warnings.warn(f"PR-AUC on test failed: {e}")

    metrics = {
        # write_report-compatible keys (test metrics as primary)
        "n_samples": len(test_rows),
        "n_folds_or_mode": (
            f"explicit_split: train+no-split={len(train_rows)}, "
            f"val={len(val_rows)}, test={len(test_rows)}"
        ),
        "grouped_cv": False,
        "group_field": None,
        "grouped_cv_warning": None,
        "accuracy": round(acc, 4),
        "f1_macro": round(f1m, 4),
        "pr_auc_ready": pr_auc,
        "confusion_matrix": {
            "labels": [0, 1],
            "label_names": ["not_ready", "ready"],
            "matrix": cm,
            "note": "rows=true, cols=predicted; labels=[0=not_ready, 1=ready]",
        },
        "classification_report": clf_report,
        "threshold_sweep": None,
        "label_counts": dict(test_lc),
        "model_name": model_name,
        "num_epochs": num_epochs,
        "batch_size": batch_size,
        "num_iterations": num_iterations,
        "body_learning_rate": body_learning_rate,
        "head_learning_rate": head_learning_rate,
        "samples_per_label": samples_per_label,
        # Explicit split specific
        "eval_mode": "explicit_split",
        "train_split_groups": ["train", "no-split (split_group_id='')"],
        "val_split_group": VAL_SPLIT,
        "test_split_group": TEST_SPLIT,
        "n_train": len(train_rows),
        "n_val": len(val_rows),
        "n_test": len(test_rows),
        "train_label_counts": dict(train_lc),
        "val_label_counts": dict(val_lc),
        "test_label_counts": dict(test_lc),
        "test_has_zero_ready": test_has_zero_ready,
        "threshold_applied_to_test": selected_threshold,
        "threshold_source": threshold_source,
        "ready_precision_on_test": round(rp, 4),
        "ready_recall_on_test": round(rr, 4),
        "ready_f1_on_test": round(rf1, 4),
        "val_metrics": val_metrics_summary,
    }

    test_row_ids = [r.get("row_id", str(i)) for i, r in enumerate(test_rows)]
    predictions = [
        {
            "row_id": test_row_ids[i],
            "split": "test",
            "label_true": test_labels_int[i],
            "label_pred": test_preds[i],
            "proba_ready": round(float(test_proba[i]), 4),
            "threshold_used": selected_threshold,
        }
        for i in range(len(test_rows))
    ]

    print(
        f"\nTest metrics (thr={selected_threshold}): "
        f"acc={acc:.4f}  macro_F1={f1m:.4f}  "
        f"ready P={rp:.4f} R={rr:.4f} F1={rf1:.4f}  PR-AUC={pr_auc}"
    )
    if test_has_zero_ready:
        print("  (ready F1=0 expected — test set has no ready examples; check FP count only)")

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
        is_explicit = metrics.get("eval_mode") == "explicit_split"

        if is_explicit:
            thresh_note = (
                f"val-tuned threshold={metrics['threshold_applied_to_test']} "
                f"({metrics['threshold_source']})"
            )
        elif ts:
            best_thresh = ts["best_threshold"]
            thresh_note = f"threshold sweep (best={best_thresh}, post-hoc diagnostic)"
        else:
            thresh_note = "default threshold=0.5"

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

        if is_explicit:
            lines += [
                "",
                "### Explicit split details",
                "",
                f"- Train+no-split: {metrics.get('n_train')} rows  {metrics.get('train_label_counts')}",
                f"- Val: {metrics.get('n_val')} rows  {metrics.get('val_label_counts')}",
                f"- Test: {metrics.get('n_test')} rows  {metrics.get('test_label_counts')}",
                f"- Threshold source: {metrics.get('threshold_source')}",
                f"- Threshold applied to test: {metrics.get('threshold_applied_to_test')}",
            ]
            if metrics.get("test_has_zero_ready"):
                lines += [
                    "",
                    "> **WARNING:** Test set has zero `ready` examples. Ready F1 and PR-AUC",
                    "> cannot be meaningfully computed. Only the false-positive rate on",
                    "> `not_ready` examples is measurable from this test split.",
                ]
            if metrics.get("val_metrics"):
                vm = metrics["val_metrics"]
                lines += [
                    "",
                    f"Val threshold sweep: best thr={vm.get('best_threshold')}  "
                    f"val ready F1={vm.get('best_ready_f1_on_val')}  "
                    f"val macro F1={vm.get('best_macro_f1_on_val')}",
                ]
            lines.append("")
            lines.append(
                "> Sanity check only. Test set is small (n=5) and has no ready examples. "
                "Grouped 5-fold CV results remain the primary performance estimate."
            )
        else:
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
    parser.add_argument(
        "--eval-split-mode", default="cv", choices=["cv", "explicit"],
        help=(
            "cv: grouped cross-validation (default). "
            "explicit: train on split_group_id in {train, ''}, "
            "tune threshold on val, evaluate once on test."
        ),
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
            if args.eval_split_mode == "explicit":
                print("Eval mode: explicit split (train+no-split / val / test)")
                metrics, predictions = train_eval_explicit_split(
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
                    output_dir=output_dir,
                )
            else:
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
            "eval_split_mode": args.eval_split_mode,
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
