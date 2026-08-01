"""Audit raw-vs-canonical answer surface mismatches for offline normalization diagnostics."""

from __future__ import annotations

import argparse
import re
from collections import Counter
from pathlib import Path
from typing import Any

from experiments.build_failure_feature_table import normalize_answer
from experiments.failure_analysis_common import load_feature_rows, write_csv, write_json, write_text

ANSWER_FIELDS = (
    ("frontier", "frontier_answer", "frontier_answer_canonical"),
    ("l1", "l1_answer", "l1_answer_canonical"),
    ("s1", "s1_answer", "s1_answer_canonical"),
    ("tale", "tale_answer", "tale_answer_canonical"),
    ("fta_selected", "fta_selected_answer", "fta_selected_answer_canonical"),
)
NUMERIC_RE = re.compile(r"-?\d+(?:\.\d+)?(?:/\d+(?:\.\d+)?)?")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        default="outputs/failure_analysis/failure_feature_table.jsonl",
        help="Failure feature table JSONL.",
    )
    parser.add_argument("--output-dir", required=True, help="Non-destructive output directory.")
    return parser.parse_args()


def heuristic_numeric_equivalent(raw_answer: Any) -> str | None:
    text = str(raw_answer or "").strip()
    if not text:
        return None
    text = text.replace("\\boxed{", "").replace("}", "")
    text = text.replace("$", "").replace(",", "")
    text = re.sub(r"(\d+)(st|nd|rd|th)\b", r"\1", text, flags=re.IGNORECASE)
    text = text.replace("%", "")
    if "=" in text:
        text = text.split("=")[-1].strip()
    matches = NUMERIC_RE.findall(text)
    if not matches:
        return None
    return normalize_answer(matches[-1])


def categorize_normalization_gap(raw_answer: Any, canonical_answer: Any) -> str:
    raw = str(raw_answer or "").strip()
    canonical = str(canonical_answer or "").strip()
    if not raw or not canonical:
        return "unknown"
    lower_raw = raw.lower()
    if re.search(r"\b\d+(st|nd|rd|th)\b", lower_raw):
        return "ordinal_suffix"
    if "%" in raw:
        return "percent_sign"
    if "=" in raw and NUMERIC_RE.search(raw):
        return "arithmetic_expression_with_final_result"
    if "$" in raw:
        return "currency_symbols"
    if re.search(r"\d+/\d+", raw):
        return "fractions"
    if "," in raw and NUMERIC_RE.search(raw):
        return "commas"
    if re.search(r"\d+\s*[a-zA-Z]+", raw):
        return "units"
    if re.search(r"\d", raw) and re.search(r"[a-zA-Z]", raw):
        return "trailing_explanations"
    return "unknown"


def audit_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    mismatches = []
    category_counts = Counter()
    field_counts = Counter()
    string_diff_count = 0
    normalize_diff_count = 0
    heuristic_match_count = 0
    pairs_examined = 0

    for row in rows:
        for surface_name, raw_field, canonical_field in ANSWER_FIELDS:
            raw_answer = row.get(raw_field)
            canonical_answer = row.get(canonical_field)
            if raw_answer in (None, "") or canonical_answer in (None, ""):
                continue
            pairs_examined += 1
            raw_text = str(raw_answer).strip()
            canonical_text = str(canonical_answer).strip()
            if raw_text == canonical_text:
                continue
            string_diff_count += 1
            raw_normalized = normalize_answer(raw_answer)
            canonical_normalized = normalize_answer(canonical_answer)
            heuristic_normalized = heuristic_numeric_equivalent(raw_answer)
            current_match = raw_normalized == canonical_normalized
            heuristic_match = heuristic_normalized == canonical_normalized and canonical_normalized is not None
            if not current_match:
                normalize_diff_count += 1
            if heuristic_match:
                heuristic_match_count += 1
            if current_match and not heuristic_match:
                continue
            category = categorize_normalization_gap(raw_answer, canonical_answer)
            category_counts[category] += 1
            field_counts[surface_name] += 1
            mismatches.append(
                {
                    "row_id": row.get("row_id"),
                    "example_id": row.get("example_id"),
                    "source_id": row.get("source_id"),
                    "seed": row.get("seed"),
                    "surface_name": surface_name,
                    "raw_field": raw_field,
                    "canonical_field": canonical_field,
                    "raw_answer": raw_answer,
                    "canonical_answer": canonical_answer,
                    "raw_normalized": raw_normalized,
                    "canonical_normalized": canonical_normalized,
                    "heuristic_numeric_normalized": heuristic_normalized,
                    "current_normalization_matches": current_match,
                    "heuristic_numeric_matches": heuristic_match,
                    "category": category,
                }
            )

    summary = {
        "pairs_examined": pairs_examined,
        "raw_vs_canonical_string_difference_count": string_diff_count,
        "current_normalization_difference_count": normalize_diff_count,
        "heuristic_numeric_match_count": heuristic_match_count,
        "category_counts": dict(sorted(category_counts.items())),
        "surface_counts": dict(sorted(field_counts.items())),
    }
    return mismatches, summary


def render_report(summary: dict[str, Any], mismatches: list[dict[str, Any]]) -> str:
    lines = [
        "# Normalization Audit",
        "",
        "Offline diagnostic audit of raw answer surfaces versus canonical answer surfaces.",
        "",
        "## Summary",
        "",
        f"- pairs_examined: {summary['pairs_examined']}",
        f"- raw_vs_canonical_string_difference_count: {summary['raw_vs_canonical_string_difference_count']}",
        f"- current_normalization_difference_count: {summary['current_normalization_difference_count']}",
        f"- heuristic_numeric_match_count: {summary['heuristic_numeric_match_count']}",
        "",
        "## Categories",
        "",
    ]
    for category, count in summary["category_counts"].items():
        lines.append(f"- `{category}`: {count}")
    lines.extend(["", "## Representative mismatches", ""])
    for row in mismatches[:20]:
        lines.append(
            f"- {row['row_id']} | {row['surface_name']} | raw={row['raw_answer']} | canonical={row['canonical_answer']} | "
            f"raw_norm={row['raw_normalized']} | canonical_norm={row['canonical_normalized']} | "
            f"heuristic={row['heuristic_numeric_normalized']} | category={row['category']}"
        )
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    args = parse_args()
    rows = load_feature_rows(args.input)
    mismatches, summary = audit_rows(rows)
    output_dir = Path(args.output_dir)
    write_csv(output_dir / "normalization_mismatches.csv", mismatches, list(mismatches[0].keys()) if mismatches else ["row_id"])
    write_json(output_dir / "normalization_summary.json", summary)
    write_text(output_dir / "normalization_report.md", render_report(summary, mismatches))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
