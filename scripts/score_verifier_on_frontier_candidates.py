"""Offline verifier scoring for frontier candidates.

Loads the saved SetFit SentenceTransformer encoder (fold_0_model/checkpoint-758/),
re-fits a LogisticRegression head on the full training dataset, then scores each
candidate from the input JSONL artifact(s).

Gold fields (exact_match, gold_answer, etc.) are NEVER included in feature_text.
They are preserved only in per-row metadata for offline evaluation.

Supported input schemas:
  - per_example_records.jsonl: {question, final_nodes[0].reasoning_text,
                                 final_answer_canonical, method, budget, example_id,
                                 exact_match, gold_answer, ...}
  - unified_candidate_trace_enriched.jsonl: {verifier_input.problem_statement,
                                              candidate_nodes[*].trace_text,
                                              candidate_nodes[*].final_answer, budget, ...}
  - training-format rows: {feature_text (pre-built), label, row_id, problem_id, ...}

Usage:
    python3 scripts/score_verifier_on_frontier_candidates.py \\
        --input-jsonl outputs/.../per_example_records.jsonl \\
        --output-dir  outputs/verifier_frontier_scoring_dryrun_<STAMP> \\
        [--model-dir  outputs/relation_verifier_setfit_tuning_.../cfg1_.../fold_0_model/checkpoint-758] \\
        [--train-jsonl outputs/relation_verifier_training_dataset_.../train_rows.jsonl] \\
        [--mode dry_run|score] \\
        [--dry-run-rows 5]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from datetime import datetime, timezone
from typing import Any

# ---------------------------------------------------------------------------
# Gold fields — must NEVER appear in feature_text
# ---------------------------------------------------------------------------
GOLD_FIELDS: frozenset[str] = frozenset(
    {
        "gold_answer",
        "gold_answer_canonical",
        "gold_answer_metadata_only",
        "exact_match",
        "is_correct",
        "is_correct_offline_metadata",
        "gold_in_tree",
        "gold_in_aggregate_answer_groups",
        "selected_answer_in_extracted_terminal_node_finals",
        "relation_ready_label_manual",
        "first_error_axis_manual",
        "notes_manual",
    }
)

# Safe feature columns — same order as training dataset builder
SAFE_FEATURE_COLS: list[str] = [
    "question",
    "target_phrase",
    "target_semantic_type",
    "candidate_answer",
    "candidate_trace_short",
    "candidate_source",
]

# Max chars to keep for candidate_trace_short (mirrors training dataset convention)
TRACE_MAX_CHARS: int = 512


# ---------------------------------------------------------------------------
# Feature extraction — one row per candidate
# ---------------------------------------------------------------------------

def _extract_per_example_record(row: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract one candidate record from per_example_records schema."""
    question = str(row.get("question", "")).strip()
    final_nodes = row.get("final_nodes") or []
    reasoning_text = ""
    if final_nodes and isinstance(final_nodes[0], dict):
        reasoning_text = str(final_nodes[0].get("reasoning_text", "") or "").strip()
    candidate_trace_short = reasoning_text[:TRACE_MAX_CHARS]

    candidate_answer = str(
        row.get("final_answer_canonical")
        or row.get("selected_answer_canonical")
        or row.get("final_answer_raw")
        or ""
    ).strip()

    candidate_source = str(row.get("method", "")).strip()

    feature_fields = {
        "question": question,
        "candidate_answer": candidate_answer,
        "candidate_trace_short": candidate_trace_short,
        "candidate_source": candidate_source,
    }

    metadata = {
        "example_id": row.get("example_id", ""),
        "budget": row.get("budget"),
        "method": row.get("method", ""),
        "model": row.get("model", ""),
        "dataset": row.get("dataset", ""),
        "seed": row.get("seed"),
        # gold fields kept in metadata only, never in feature_text
        "exact_match_metadata": row.get("exact_match"),
        "gold_answer_metadata": row.get("gold_answer"),
    }

    return [{"feature_fields": feature_fields, "metadata": metadata}]


def _extract_unified_candidate_trace(row: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract one record per candidate_node from unified_candidate_trace_enriched schema."""
    vi = row.get("verifier_input", {}) or {}
    question = str(vi.get("problem_statement", "") or row.get("problem_statement", "")).strip()
    budget = row.get("budget")
    example_id = str(row.get("example_id", "")).strip()

    candidates_raw = vi.get("candidates_for_verifier", []) or row.get("candidate_nodes", []) or []
    if isinstance(candidates_raw, str):
        try:
            candidates_raw = json.loads(candidates_raw)
        except Exception:
            candidates_raw = []

    if not candidates_raw:
        candidates_raw = row.get("candidate_nodes", []) or []

    records = []
    for cand in candidates_raw:
        if not isinstance(cand, dict):
            continue
        trace_text = str(cand.get("trace_text", "") or cand.get("reasoning_trace", "") or "").strip()
        candidate_trace_short = trace_text[:TRACE_MAX_CHARS]
        candidate_answer = str(cand.get("final_answer", "") or cand.get("normalized_answer", "")).strip()
        candidate_id = str(cand.get("candidate_id", "")).strip()
        source_family = str(cand.get("source_family", "")).strip()

        feature_fields = {
            "question": question,
            "candidate_answer": candidate_answer,
            "candidate_trace_short": candidate_trace_short,
            "candidate_source": source_family,
        }
        metadata = {
            "example_id": example_id,
            "candidate_id": candidate_id,
            "budget": budget,
            "source_family": source_family,
        }
        records.append({"feature_fields": feature_fields, "metadata": metadata})

    return records


def _extract_training_format(row: dict[str, Any]) -> list[dict[str, Any]]:
    """Handle rows that already have a pre-built feature_text (training-format)."""
    feature_text = str(row.get("feature_text", "")).strip()
    label = row.get("label")
    row_id = row.get("row_id", "")
    problem_id = row.get("problem_id", "")

    metadata = {
        "row_id": row_id,
        "problem_id": problem_id,
        # keep label in metadata for evaluation only
        "label_metadata": label,
    }
    # pre-built feature_text — no structured fields to reconstruct
    return [{"feature_text": feature_text, "metadata": metadata}]


def _detect_schema(row: dict[str, Any]) -> str:
    """Detect input schema from row keys."""
    if "feature_text" in row and "label" in row:
        return "training_format"
    if "final_nodes" in row or "final_answer_canonical" in row:
        return "per_example_records"
    if "verifier_input" in row or "candidate_nodes" in row:
        return "unified_candidate_trace"
    return "per_example_records"  # fallback


def build_feature_text(feature_fields: dict[str, str]) -> str:
    """Build feature_text from structured fields using training dataset template."""
    parts = []
    for col in SAFE_FEATURE_COLS:
        val = str(feature_fields.get(col, "") or "").strip()
        if val:
            parts.append(f"{col}: {val}")
    return " | ".join(parts)


def check_leakage(feature_text: str) -> list[str]:
    """Return list of gold field names found in feature_text (should be empty)."""
    found = []
    ft_lower = feature_text.lower()
    for field in GOLD_FIELDS:
        if field.lower() in ft_lower:
            found.append(field)
    return found


def extract_candidates(
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], str]:
    """Extract all candidate records from a list of rows.

    Returns (records, schema_detected).
    Each record has: feature_text, metadata.
    """
    if not rows:
        return [], "unknown"

    schema = _detect_schema(rows[0])

    records: list[dict[str, Any]] = []
    for row in rows:
        if schema == "training_format":
            extracted = _extract_training_format(row)
        elif schema == "per_example_records":
            extracted = _extract_per_example_record(row)
        elif schema == "unified_candidate_trace":
            extracted = _extract_unified_candidate_trace(row)
        else:
            extracted = _extract_per_example_record(row)

        for rec in extracted:
            if "feature_text" not in rec:
                rec["feature_text"] = build_feature_text(rec.get("feature_fields", {}))
            records.append(rec)

    return records, schema


# ---------------------------------------------------------------------------
# Model loading and scoring
# ---------------------------------------------------------------------------

def _load_sentence_transformer(model_dir: str):
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(model_dir)


def _fit_lr_head(st_model, train_jsonl: pathlib.Path):
    """Encode training examples and fit a balanced LogisticRegression head."""
    from sklearn.linear_model import LogisticRegression
    import numpy as np

    with open(train_jsonl) as f:
        train_rows = [json.loads(l) for l in f]

    texts, labels = [], []
    for row in train_rows:
        ft = row.get("feature_text", "").strip()
        lbl = row.get("label")
        if ft and lbl is not None:
            texts.append(ft)
            labels.append(int(lbl))

    if not texts:
        raise ValueError(f"No usable training rows in {train_jsonl}")

    embeddings = st_model.encode(texts, show_progress_bar=True, normalize_embeddings=True)
    labels_arr = [int(x) for x in labels]

    clf = LogisticRegression(class_weight="balanced", max_iter=1000, random_state=42)
    clf.fit(embeddings, labels_arr)
    return clf


def score_candidates(
    candidates: list[dict[str, Any]],
    model_dir: str,
    train_jsonl: pathlib.Path,
) -> list[dict[str, Any]]:
    """Score candidates with re-fitted SetFit model. Returns records with proba_ready added."""
    st_model = _load_sentence_transformer(model_dir)
    clf = _fit_lr_head(st_model, train_jsonl)

    texts = [c["feature_text"] for c in candidates]
    embeddings = st_model.encode(texts, show_progress_bar=True, normalize_embeddings=True)
    probas = clf.predict_proba(embeddings)

    ready_idx = list(clf.classes_).index(1)
    scored = []
    for rec, proba_row in zip(candidates, probas):
        r = dict(rec)
        r["proba_ready"] = float(proba_row[ready_idx])
        r["score_ready"] = r["proba_ready"]
        r["predicted_label"] = int(proba_row[ready_idx] >= 0.5)
        scored.append(r)

    return scored


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------

def _write_scored_candidates(
    scored: list[dict[str, Any]],
    out_dir: pathlib.Path,
) -> pathlib.Path:
    path = out_dir / "scored_candidates.jsonl"
    with open(path, "w") as f:
        for i, rec in enumerate(scored):
            out = {
                "row_index": i,
                "feature_text": rec["feature_text"],
                "proba_ready": rec.get("proba_ready"),
                "score_ready": rec.get("score_ready"),
                "predicted_label": rec.get("predicted_label"),
                "metadata": rec.get("metadata", {}),
            }
            f.write(json.dumps(out) + "\n")
    return path


def _write_scoring_report(
    scored: list[dict[str, Any]],
    schema: str,
    input_paths: list[str],
    mode: str,
    model_dir: str | None,
    train_jsonl: str | None,
    leakage_violations: list[str],
    out_dir: pathlib.Path,
) -> pathlib.Path:
    import statistics

    path = out_dir / "scoring_report.md"
    now = datetime.now(timezone.utc).isoformat()

    lines = [
        "# Verifier Frontier Scoring Report",
        "",
        f"- **Generated:** {now}",
        f"- **Mode:** {mode}",
        f"- **Schema:** {schema}",
        f"- **Input files:** {len(input_paths)}",
        f"- **Candidates scored:** {len(scored)}",
        "",
        "## Input Artifacts",
        "",
    ]
    for p in input_paths:
        lines.append(f"- `{p}`")
    lines += [
        "",
        "## Model",
        "",
        f"- SentenceTransformer encoder: `{model_dir or 'N/A'}`",
        f"- Training data for LR head: `{train_jsonl or 'N/A'}`",
        "",
        "## Leakage Check",
        "",
    ]
    if leakage_violations:
        lines.append(f"**FAIL** — {len(leakage_violations)} violations found:")
        for v in leakage_violations[:20]:
            lines.append(f"  - {v}")
    else:
        lines.append("**PASS** — No gold fields detected in feature_text.")

    if scored and mode == "score":
        probas = [r["proba_ready"] for r in scored if r.get("proba_ready") is not None]
        if probas:
            lines += [
                "",
                "## Score Distribution",
                "",
                f"| Stat | Value |",
                f"|---|---|",
                f"| n_candidates | {len(probas)} |",
                f"| mean proba_ready | {statistics.mean(probas):.4f} |",
                f"| median proba_ready | {statistics.median(probas):.4f} |",
                f"| min | {min(probas):.4f} |",
                f"| max | {max(probas):.4f} |",
                f"| n_predicted_ready (≥0.5) | {sum(1 for p in probas if p >= 0.5)} |",
            ]

            meta_has_exact_match = any(
                r.get("metadata", {}).get("exact_match_metadata") is not None for r in scored
            )
            if meta_has_exact_match:
                from collections import Counter
                hits = [(r["proba_ready"], r["metadata"].get("exact_match_metadata")) for r in scored]
                ready_correct = sum(1 for p, em in hits if p >= 0.5 and em == 1)
                ready_total = sum(1 for p, _ in hits if p >= 0.5)
                lines += [
                    "",
                    "## Offline Accuracy Cross-tab (metadata only — not used by verifier)",
                    "",
                    "| | predicted_ready | predicted_not_ready |",
                    "|---|---|---|",
                ]
                nr_correct = sum(1 for p, em in hits if p < 0.5 and em == 1)
                nr_total = sum(1 for p, _ in hits if p < 0.5)
                lines += [
                    f"| exact_match=1 | {ready_correct} | {nr_correct} |",
                    f"| exact_match=0 | {ready_total - ready_correct} | {nr_total - nr_correct} |",
                ]

    lines += [
        "",
        "---",
        "",
        "*Gold metadata preserved in `scored_candidates.jsonl` under `metadata` key only.*",
        "*Gold fields were never used as verifier input features.*",
    ]

    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    return path


def _write_manifest(
    cfg: dict[str, Any],
    out_dir: pathlib.Path,
) -> pathlib.Path:
    path = out_dir / "run_manifest.json"
    with open(path, "w") as f:
        json.dump(cfg, f, indent=2, default=str)
    return path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument(
        "--input-jsonl",
        dest="input_jsonl",
        action="append",
        required=True,
        metavar="PATH",
        help="Input JSONL artifact path (repeat for multiple files).",
    )
    p.add_argument("--output-dir", required=True, help="Output directory.")
    p.add_argument(
        "--model-dir",
        default="outputs/relation_verifier_setfit_tuning_20260516_20260517T000951Z"
        "/cfg1_e1_i20_b16_spl2/fold_0_model/checkpoint-758",
        help="Path to SetFit SentenceTransformer checkpoint.",
    )
    p.add_argument(
        "--train-jsonl",
        default="outputs/relation_verifier_training_dataset_combined_33plus250plus100"
        "_20260516T221311Z/train_rows.jsonl",
        help="Training JSONL used to re-fit the LR head.",
    )
    p.add_argument(
        "--mode",
        choices=["dry_run", "score"],
        default="dry_run",
        help="dry_run: validate extraction/leakage only. score: load model, score all.",
    )
    p.add_argument(
        "--dry-run-rows",
        type=int,
        default=5,
        help="Number of rows to validate in dry_run mode.",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    out_dir = pathlib.Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # ------------------------------------------------------------------
    # Load all input rows
    # ------------------------------------------------------------------
    all_rows: list[dict[str, Any]] = []
    for path_str in args.input_jsonl:
        p = pathlib.Path(path_str)
        if not p.exists():
            print(f"ERROR: input file not found: {p}", file=sys.stderr)
            return 1
        with open(p) as f:
            file_rows = [json.loads(line) for line in f if line.strip()]
        print(f"Loaded {len(file_rows)} rows from {p}")
        all_rows.extend(file_rows)

    if not all_rows:
        print("ERROR: no rows loaded from any input file.", file=sys.stderr)
        return 1

    # ------------------------------------------------------------------
    # Extract candidate records
    # ------------------------------------------------------------------
    candidates, schema = extract_candidates(all_rows)
    print(f"Extracted {len(candidates)} candidate records (schema: {schema})")

    # ------------------------------------------------------------------
    # Leakage check
    # ------------------------------------------------------------------
    leakage_violations: list[str] = []
    check_rows = candidates[: args.dry_run_rows] if args.mode == "dry_run" else candidates
    for i, rec in enumerate(check_rows):
        violations = check_leakage(rec["feature_text"])
        for v in violations:
            leakage_violations.append(f"row {i}: '{v}' found in feature_text")

    if leakage_violations:
        print(f"LEAKAGE DETECTED: {len(leakage_violations)} violations:")
        for vio in leakage_violations[:10]:
            print(f"  {vio}")
        # Write manifest with failure info before returning
        cfg = {
            "mode": args.mode,
            "stamp": stamp,
            "input_paths": args.input_jsonl,
            "output_dir": args.output_dir,
            "schema": schema,
            "n_rows_input": len(all_rows),
            "n_candidates": len(candidates),
            "leakage_check": "FAIL",
            "leakage_violations": leakage_violations[:20],
        }
        _write_manifest(cfg, out_dir)
        return 2

    print("Leakage check: PASS")

    # ------------------------------------------------------------------
    # Dry-run: validate and report extraction only
    # ------------------------------------------------------------------
    if args.mode == "dry_run":
        print(f"\n--- Dry-run: first {args.dry_run_rows} candidates ---")
        for i, rec in enumerate(candidates[: args.dry_run_rows]):
            print(f"\n[{i}] feature_text ({len(rec['feature_text'])} chars):")
            print(f"  {rec['feature_text'][:200]}")
            meta = rec.get("metadata", {})
            em = meta.get("exact_match_metadata")
            ga = meta.get("gold_answer_metadata")
            print(f"  metadata.exact_match={em}  metadata.gold_answer={'(present)' if ga else '(absent)'}")

        cfg = {
            "mode": "dry_run",
            "stamp": stamp,
            "input_paths": args.input_jsonl,
            "output_dir": args.output_dir,
            "model_dir": args.model_dir,
            "train_jsonl": args.train_jsonl,
            "schema": schema,
            "n_rows_input": len(all_rows),
            "n_candidates": len(candidates),
            "dry_run_rows_checked": min(args.dry_run_rows, len(candidates)),
            "leakage_check": "PASS",
        }
        _write_manifest(cfg, out_dir)
        # Write a placeholder scoring_report
        _write_scoring_report(
            scored=[],
            schema=schema,
            input_paths=args.input_jsonl,
            mode="dry_run",
            model_dir=args.model_dir,
            train_jsonl=args.train_jsonl,
            leakage_violations=[],
            out_dir=out_dir,
        )
        print(f"\nDry-run complete. Outputs written to: {out_dir}")
        print(f"  {out_dir}/run_manifest.json")
        print(f"  {out_dir}/scoring_report.md")
        return 0

    # ------------------------------------------------------------------
    # Score mode
    # ------------------------------------------------------------------
    model_dir = args.model_dir
    train_jsonl = pathlib.Path(args.train_jsonl)

    if not pathlib.Path(model_dir).exists():
        print(f"ERROR: model_dir not found: {model_dir}", file=sys.stderr)
        return 1
    if not train_jsonl.exists():
        print(f"ERROR: train_jsonl not found: {train_jsonl}", file=sys.stderr)
        return 1

    print(f"\nLoading SentenceTransformer from: {model_dir}")
    print(f"Re-fitting LR head on: {train_jsonl}")
    scored = score_candidates(candidates, model_dir, train_jsonl)
    print(f"Scored {len(scored)} candidates.")

    _write_scored_candidates(scored, out_dir)
    _write_scoring_report(
        scored=scored,
        schema=schema,
        input_paths=args.input_jsonl,
        mode="score",
        model_dir=model_dir,
        train_jsonl=str(train_jsonl),
        leakage_violations=[],
        out_dir=out_dir,
    )

    cfg = {
        "mode": "score",
        "stamp": stamp,
        "input_paths": args.input_jsonl,
        "output_dir": args.output_dir,
        "model_dir": model_dir,
        "train_jsonl": str(train_jsonl),
        "schema": schema,
        "n_rows_input": len(all_rows),
        "n_candidates": len(candidates),
        "leakage_check": "PASS",
    }
    _write_manifest(cfg, out_dir)

    print(f"\nScoring complete. Outputs written to: {out_dir}")
    print(f"  {out_dir}/scored_candidates.jsonl")
    print(f"  {out_dir}/scoring_report.md")
    print(f"  {out_dir}/run_manifest.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
