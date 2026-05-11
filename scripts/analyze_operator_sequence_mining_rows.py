#!/usr/bin/env python3
"""Analyze exported operator-sequence mining rows for offline signal audit."""

from __future__ import annotations

import argparse
import csv
import json
import sys
import tempfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
EXPORT_FILENAMES = ("path_prefix_rows.jsonl", "summary.json")

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.operator_sequence_mining import operator_ngrams
from scripts import export_operator_sequence_mining_rows as exporter


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _safe_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    text = str(value).strip().lower()
    if text in {"1", "true", "t", "yes", "y"}:
        return True
    if text in {"0", "false", "f", "no", "n"}:
        return False
    return default


def _stringify(value: Any) -> str:
    return str(value).strip()


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            obj = json.loads(text)
            if isinstance(obj, dict):
                rows.append(obj)
    return rows


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = list(rows)
    fieldnames = sorted({key for row in rows for key in row.keys()}) if rows else []
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _looks_like_export_dir(path: Path) -> bool:
    return path.is_dir() and all((path / name).is_file() for name in EXPORT_FILENAMES)


def _resolve_input_dir(raw: str) -> Path:
    candidate = Path(raw).expanduser()
    if candidate.exists():
        return candidate
    if not candidate.is_absolute():
        repo_candidate = REPO_ROOT / candidate
        if repo_candidate.exists():
            return repo_candidate
    raise FileNotFoundError(f"Missing input path: {raw}")


def _coerce_sequence(row: dict[str, Any]) -> list[str]:
    value = row.get("feature_operator_sequence")
    if isinstance(value, list):
        return [_stringify(item) for item in value if _stringify(item)]
    if isinstance(value, tuple):
        return [_stringify(item) for item in value if _stringify(item)]
    seq_key = _stringify(row.get("feature_operator_sequence_key"))
    if seq_key:
        return [part for part in seq_key.split("->") if part]
    return []


def _sequence_key(row: dict[str, Any]) -> str:
    key = _stringify(row.get("feature_operator_sequence_key"))
    if key:
        return key
    sequence = _coerce_sequence(row)
    return "->".join(sequence)


def _row_quality(row: dict[str, Any]) -> float:
    for key in (
        "label_best_descendant_quality",
        "label_terminal_quality",
    ):
        if key in row:
            return _safe_float(row.get(key))
    if "label_gold_in_subtree" in row:
        return 1.0 if _safe_bool(row.get("label_gold_in_subtree")) else 0.0
    return 0.0


def _label_bucket(row: dict[str, Any]) -> str:
    if "label_best_descendant_quality" in row:
        return f"best_descendant_quality={_safe_float(row.get('label_best_descendant_quality')):g}"
    if "label_terminal_quality" in row:
        return f"terminal_quality={_safe_float(row.get('label_terminal_quality')):g}"
    if "label_gold_in_subtree" in row:
        return f"gold_in_subtree={_safe_bool(row.get('label_gold_in_subtree'))}"
    return "unlabeled"


def _extract_feature_fields(rows: list[dict[str, Any]]) -> list[str]:
    return sorted({key for row in rows for key in row if key.startswith("feature_")})


def _extract_label_fields(rows: list[dict[str, Any]]) -> list[str]:
    return sorted({key for row in rows for key in row if key.startswith("label_")})


def _coverage(rows: list[dict[str, Any]], prefix: str) -> list[dict[str, Any]]:
    total = len(rows)
    counter: Counter[str] = Counter()
    for row in rows:
        for key in row:
            if key.startswith(prefix):
                counter[key] += 1
    out = []
    for field, count in sorted(counter.items(), key=lambda item: (-item[1], item[0])):
        out.append(
            {
                "field": field,
                "count": count,
                "coverage": float(count / total) if total else 0.0,
            }
        )
    return out


def _distribution(rows: list[dict[str, Any]], field_name: str, *, value_fn) -> list[dict[str, Any]]:
    counter: Counter[str] = Counter()
    for row in rows:
        if field_name in row:
            counter[value_fn(row.get(field_name))] += 1
    total = sum(counter.values())
    return [
        {
            "value": value,
            "count": count,
            "coverage": float(count / total) if total else 0.0,
        }
        for value, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    ]


def _mean(values: Iterable[float]) -> float:
    items = [float(value) for value in values]
    return float(sum(items) / len(items)) if items else 0.0


def _sequence_statistics(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = defaultdict(lambda: {
        "count": 0,
        "quality_sum": 0.0,
        "entropy_sum": 0.0,
        "support_margin_sum": 0.0,
        "outlier_sum": 0.0,
    })
    for row in rows:
        key = _sequence_key(row) or "unsequenced"
        stat = buckets[key]
        stat["count"] += 1
        stat["quality_sum"] += _row_quality(row)
        stat["entropy_sum"] += _safe_float(row.get("feature_answer_entropy"))
        stat["support_margin_sum"] += _safe_float(row.get("feature_support_margin"))
        stat["outlier_sum"] += 1.0 if _safe_bool(row.get("feature_is_answer_outlier")) else 0.0

    out: list[dict[str, Any]] = []
    for key, stat in buckets.items():
        count = stat["count"] or 1
        out.append(
            {
                "operator_sequence_key": key,
                "count": stat["count"],
                "mean_quality": float(stat["quality_sum"] / count),
                "mean_answer_entropy": float(stat["entropy_sum"] / count),
                "mean_support_margin": float(stat["support_margin_sum"] / count),
                "outlier_rate": float(stat["outlier_sum"] / count),
            }
        )
    return sorted(out, key=lambda item: (-item["count"], -item["mean_quality"], item["operator_sequence_key"]))


def _ngram_statistics(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = defaultdict(lambda: {
        "count": 0,
        "quality_sum": 0.0,
    })
    for row in rows:
        quality = _row_quality(row)
        ngram_counts = row.get("feature_operator_ngram_counts")
        if not isinstance(ngram_counts, dict) or not ngram_counts:
            sequence = _coerce_sequence(row)
            ngram_counts = operator_ngrams(sequence, max_n=3)
        for key, count_value in ngram_counts.items():
            count = _safe_int(count_value, default=0)
            if count <= 0:
                continue
            stat = buckets[_stringify(key)]
            stat["count"] += count
            stat["quality_sum"] += quality * count

    out: list[dict[str, Any]] = []
    for key, stat in buckets.items():
        count = stat["count"] or 1
        out.append(
            {
                "ngram": key,
                "count": stat["count"],
                "mean_quality": float(stat["quality_sum"] / count),
            }
        )
    return sorted(out, key=lambda item: (-item["count"], -item["mean_quality"], item["ngram"]))


def _bucket_summaries(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = defaultdict(lambda: {
        "count": 0,
        "entropy_sum": 0.0,
        "support_margin_sum": 0.0,
        "outlier_sum": 0.0,
        "quality_sum": 0.0,
        "gold_sum": 0.0,
    })
    for row in rows:
        bucket = _label_bucket(row)
        stat = buckets[bucket]
        stat["count"] += 1
        stat["quality_sum"] += _row_quality(row)
        stat["entropy_sum"] += _safe_float(row.get("feature_answer_entropy"))
        stat["support_margin_sum"] += _safe_float(row.get("feature_support_margin"))
        stat["outlier_sum"] += 1.0 if _safe_bool(row.get("feature_is_answer_outlier")) else 0.0
        if "label_gold_in_subtree" in row:
            stat["gold_sum"] += 1.0 if _safe_bool(row.get("label_gold_in_subtree")) else 0.0

    out: list[dict[str, Any]] = []
    for bucket, stat in buckets.items():
        count = stat["count"] or 1
        out.append(
            {
                "bucket": bucket,
                "count": stat["count"],
                "mean_quality": float(stat["quality_sum"] / count),
                "mean_answer_entropy": float(stat["entropy_sum"] / count),
                "mean_support_margin": float(stat["support_margin_sum"] / count),
                "outlier_rate": float(stat["outlier_sum"] / count),
                "gold_in_subtree_rate": float(stat["gold_sum"] / count) if stat["gold_sum"] else 0.0,
            }
        )
    return sorted(out, key=lambda item: (-item["count"], item["bucket"]))


def _next_experiment_suggestion(rows: list[dict[str, Any]], source_row_type: str) -> str:
    if not rows:
        return "Collect more exported rows before attempting a ranking or policy experiment."

    if "pseudo_path" in source_row_type or "singleton" in source_row_type:
        return (
            "Collect a real tree-path artifact with reliable parent links before training any policy; "
            "the current source is sequence-like rather than a verified tree."
        )

    sequence_stats = [item for item in _sequence_statistics(rows) if item["count"] >= 2]
    if len(sequence_stats) >= 2:
        best = max(sequence_stats, key=lambda item: item["mean_quality"])
        worst = min(sequence_stats, key=lambda item: item["mean_quality"])
        if best["mean_quality"] - worst["mean_quality"] >= 0.2:
            return (
                "Run a tiny held-out sequence-ranking experiment over the highest- and lowest-quality operator "
                "prefixes, then test whether a lightweight reranker improves candidate selection."
            )

    return (
        "The offline signal is weak or small; next collect more rows across a richer artifact source and rerun "
        "the audit before attempting learned policy work."
    )


def _render_table(rows: list[dict[str, Any]], headers: list[str]) -> str:
    if not rows:
        return "_No rows._"
    widths = {header: len(header) for header in headers}
    for row in rows:
        for header in headers:
            widths[header] = max(widths[header], len(_stringify(row.get(header, ""))))

    def _fmt_row(row: dict[str, Any]) -> str:
        return " | ".join(_stringify(row.get(header, "")).ljust(widths[header]) for header in headers)

    header_line = " | ".join(header.ljust(widths[header]) for header in headers)
    divider = " | ".join("-" * widths[header] for header in headers)
    body = "\n".join(_fmt_row(row) for row in rows)
    return f"{header_line}\n{divider}\n{body}"


def _render_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Operator Sequence Signal Audit",
        "",
        f"- Generated at: `{summary['generated_at_utc']}`",
        f"- Input: `{summary['input_path']}`",
        f"- Exported rows analyzed: `{summary['row_count']}`",
        f"- Source row type: `{summary['source_row_type']}`",
        f"- Primary quality field: `{summary['primary_quality_field']}`",
        "",
        "## Warnings",
        "",
    ]
    warnings = summary.get("warnings", [])
    if warnings:
        lines.extend(f"- {warning}" for warning in warnings)
    else:
        lines.append("- None.")

    lines.extend(
        [
            "",
            "## Field Coverage",
            "",
            "### Feature Fields",
            _render_table(summary.get("feature_field_coverage", [])[:12], ["field", "count", "coverage"]),
            "",
            "### Label Fields",
            _render_table(summary.get("label_field_coverage", [])[:12], ["field", "count", "coverage"]),
            "",
            "## Label Distributions",
            "",
            "### Best Descendant Quality",
            _render_table(summary.get("best_descendant_quality_distribution", []), ["value", "count", "coverage"]),
            "",
            "### Gold In Subtree",
            _render_table(summary.get("gold_in_subtree_distribution", []), ["value", "count", "coverage"]),
            "",
            "## Operator Sequence Signal",
            "",
            "### Top Sequences",
            _render_table(summary.get("top_operator_sequences", [])[:10], ["operator_sequence_key", "count", "mean_quality"]),
            "",
            "### Top N-grams",
            _render_table(summary.get("top_ngrams", [])[:10], ["ngram", "count", "mean_quality"]),
            "",
            "## Entropy / Support / Outlier By Quality Bucket",
            "",
            _render_table(
                summary.get("bucket_summaries", []),
                ["bucket", "count", "mean_quality", "mean_answer_entropy", "mean_support_margin", "outlier_rate"],
            ),
            "",
            "## Next Targeted Experiment",
            "",
            summary.get("next_experiment_suggestion", ""),
            "",
            "## Notes",
            "",
            "- Offline signal audit only.",
            "- No paid or model API calls were made.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        required=True,
        help="Export directory with path_prefix_rows.jsonl and summary.json, or a source artifact path to export first.",
    )
    parser.add_argument(
        "--output-dir",
        default="",
        help="Optional output directory. Defaults to outputs/operator_sequence_signal_audit_<timestamp>.",
    )
    parser.add_argument(
        "--timestamp",
        default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        help="UTC timestamp suffix for the default output directory.",
    )
    return parser.parse_args(argv)


def _load_rows_and_summary(input_path: Path) -> tuple[list[dict[str, Any]], dict[str, Any], Path]:
    if _looks_like_export_dir(input_path):
        rows = _load_jsonl(input_path / "path_prefix_rows.jsonl")
        summary = json.loads((input_path / "summary.json").read_text(encoding="utf-8"))
        return rows, summary, input_path

    with tempfile.TemporaryDirectory(prefix="operator_sequence_signal_audit_", dir=str(REPO_ROOT / "outputs")) as temp_dir:
        export_dir = Path(temp_dir)
        exporter.run(["--input", str(input_path), "--output-dir", str(export_dir)])
        rows = _load_jsonl(export_dir / "path_prefix_rows.jsonl")
        summary = json.loads((export_dir / "summary.json").read_text(encoding="utf-8"))
        return rows, summary, export_dir


def analyze(argv: list[str] | None = None) -> dict[str, Any]:
    args = parse_args(argv)
    input_path = _resolve_input_dir(args.input)
    rows, export_summary, resolved_export_dir = _load_rows_and_summary(input_path)

    if not rows:
        raise ValueError(f"Input export contains no rows: {input_path}")

    feature_fields = _extract_feature_fields(rows)
    label_fields = _extract_label_fields(rows)
    primary_quality_field = "label_best_descendant_quality" if "label_best_descendant_quality" in label_fields else (
        "label_terminal_quality" if "label_terminal_quality" in label_fields else (
            "label_gold_in_subtree" if "label_gold_in_subtree" in label_fields else "none"
        )
    )

    best_descendant_quality_distribution = _distribution(
        rows,
        "label_best_descendant_quality",
        value_fn=lambda value: f"{_safe_float(value):g}",
    )
    gold_in_subtree_distribution = _distribution(
        rows,
        "label_gold_in_subtree",
        value_fn=lambda value: str(_safe_bool(value)),
    )

    top_sequences = _sequence_statistics(rows)[:20]
    top_ngrams = _ngram_statistics(rows)[:20]
    bucket_summaries = _bucket_summaries(rows)
    warnings = []
    source_row_type = _stringify(export_summary.get("source_selection", {}).get("row_type", "unknown"))
    if "pseudo_path" in source_row_type or "singleton" in source_row_type:
        warnings.append(
            "Source is pseudo-path only; row chains are ordered trace approximations, not verified tree paths."
        )
    if source_row_type == "unknown":
        warnings.append("Source row type was not declared in the export summary.")

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_path": str(input_path),
        "resolved_export_dir": str(resolved_export_dir),
        "row_count": len(rows),
        "feature_field_names": feature_fields,
        "label_field_names": label_fields,
        "feature_field_coverage": _coverage(rows, "feature_"),
        "label_field_coverage": _coverage(rows, "label_"),
        "best_descendant_quality_distribution": best_descendant_quality_distribution,
        "gold_in_subtree_distribution": gold_in_subtree_distribution,
        "top_operator_sequences": top_sequences,
        "top_ngrams": top_ngrams,
        "bucket_summaries": bucket_summaries,
        "primary_quality_field": primary_quality_field,
        "source_row_type": source_row_type,
        "warnings": warnings,
        "next_experiment_suggestion": _next_experiment_suggestion(rows, source_row_type),
        "export_source": export_summary.get("source_selection", {}),
    }

    output_dir = Path(args.output_dir) if args.output_dir else REPO_ROOT / "outputs" / f"operator_sequence_signal_audit_{args.timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "summary.json", summary)
    (output_dir / "operator_sequence_signal_report.md").write_text(_render_report(summary), encoding="utf-8")
    _write_csv(output_dir / "operator_sequence_quality_table.csv", top_sequences)
    _write_csv(output_dir / "ngram_quality_table.csv", top_ngrams)
    return summary


def main() -> int:
    try:
        analyze()
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
