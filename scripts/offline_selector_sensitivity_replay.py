#!/usr/bin/env python3
"""Offline selector-sensitivity replay from broad/conservative gate per-case outputs (no API)."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _to_int(v: Any) -> int:
    try:
        return int(float(str(v)))
    except Exception:
        return 0


def _norm(v: Any) -> str:
    return str(v if v is not None else "").strip()


def _idx(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for r in rows:
        eid = _norm(r.get("example_id"))
        if eid:
            out[eid] = r
    return out


def _build_casebook_index(path: Path | None) -> dict[str, dict[str, str]]:
    if path is None or not path.is_file():
        return {}
    return _idx(_read_csv_rows(path))


def _extract_broad_features(row: dict[str, str] | None) -> dict[str, Any]:
    if not row:
        return {}
    return {
        "broad_prediction_changed": int(_norm(row.get("incumbent_prediction")) != _norm(row.get("new_prediction"))),
        "broad_exact_changed": int(_to_int(row.get("incumbent_exact")) != _to_int(row.get("new_exact"))),
        "broad_exact_worsened": int(_to_int(row.get("incumbent_exact")) > _to_int(row.get("new_exact"))),
        "broad_incumbent_correct": int(_to_int(row.get("incumbent_exact")) == 1),
        "broad_triggered": _to_int(row.get("rate_ratio_gate_triggered")),
        "broad_added_candidates": _to_int(row.get("rate_ratio_gate_added_candidates")),
        "broad_duplicate_skip": _to_int(row.get("rate_ratio_gate_skipped_duplicate")),
        "broad_gold_present_delta": _to_int(row.get("new_gold_present_pool")) - _to_int(row.get("incumbent_gold_present_pool")),
        "broad_reason": _norm(row.get("rate_ratio_gate_reason")),
        "broad_question_bucket": _norm(row.get("rate_ratio_gate_question_bucket")),
    }


def _extract_conservative_features(row: dict[str, str] | None) -> dict[str, Any]:
    if not row:
        return {}
    return {
        "cons_prediction_changed": int(_norm(row.get("incumbent_prediction")) != _norm(row.get("conservative_prediction"))),
        "cons_exact_changed": int(_to_int(row.get("incumbent_exact")) != _to_int(row.get("conservative_exact"))),
        "cons_exact_worsened": int(_to_int(row.get("incumbent_exact")) > _to_int(row.get("conservative_exact"))),
        "cons_incumbent_correct": int(_to_int(row.get("incumbent_exact")) == 1),
        "cons_triggered": _to_int(row.get("conservative_rate_ratio_gate_triggered")),
        "cons_frozen": _to_int(row.get("conservative_rate_ratio_gate_frozen")),
        "cons_added_candidates": _to_int(row.get("conservative_rate_ratio_gate_added_candidates")),
        "cons_duplicate_skip": _to_int(row.get("conservative_rate_ratio_gate_skipped_duplicate")),
        "cons_override_allowed": _to_int(row.get("conservative_rate_ratio_gate_override_allowed")),
        "cons_override_block_reason": _norm(row.get("conservative_rate_ratio_gate_override_block_reason")),
        "cons_reason": _norm(row.get("conservative_rate_ratio_gate_reason")),
        "cons_question_bucket": _norm(row.get("conservative_rate_ratio_gate_question_bucket")),
    }


def run_replay(
    broad_per_case_csv: Path,
    conservative_per_case_csv: Path,
    output_dir: Path,
    paired_casebook_csv: Path | None = None,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    broad_rows = _idx(_read_csv_rows(broad_per_case_csv))
    cons_rows = _idx(_read_csv_rows(conservative_per_case_csv))
    casebook = _build_casebook_index(paired_casebook_csv)
    all_ids = sorted(set(broad_rows.keys()) | set(cons_rows.keys()))

    per_case: list[dict[str, Any]] = []
    bucket_counts: Counter[str] = Counter()
    feature_counts: Counter[str] = Counter()
    feature_buckets: defaultdict[str, Counter[str]] = defaultdict(Counter)

    for eid in all_ids:
        br = broad_rows.get(eid)
        cr = cons_rows.get(eid)
        b = _extract_broad_features(br)
        c = _extract_conservative_features(cr)
        inc_exact = max(_to_int((br or {}).get("incumbent_exact")), _to_int((cr or {}).get("incumbent_exact")))
        gate_exacts = [
            _to_int((br or {}).get("new_exact")),
            _to_int((cr or {}).get("conservative_exact")),
        ]
        gate_exact = min(gate_exacts) if gate_exacts else 0
        exact_worsened_any = int(inc_exact > gate_exact)
        prediction_changed_any = int(
            b.get("broad_prediction_changed", 0) == 1 or c.get("cons_prediction_changed", 0) == 1
        )
        added_any = int(b.get("broad_added_candidates", 0) > 0 or c.get("cons_added_candidates", 0) > 0)
        dup_any = int(b.get("broad_duplicate_skip", 0) == 1 or c.get("cons_duplicate_skip", 0) == 1)
        gold_present_delta = int(b.get("broad_gold_present_delta", 0))
        override_blocked_but_changed = int(
            c.get("cons_override_allowed", 0) == 0 and c.get("cons_prediction_changed", 0) == 1
        )
        previously_correct_regressed = int(inc_exact == 1 and exact_worsened_any == 1)

        buckets: list[str] = []
        if added_any and prediction_changed_any and exact_worsened_any:
            buckets.append("added_candidate_flip_wrong")
        if dup_any and prediction_changed_any:
            buckets.append("duplicate_skip_flip")
        if gold_present_delta > 0 and exact_worsened_any:
            buckets.append("gold_present_improved_but_exact_worse")
        if override_blocked_but_changed:
            buckets.append("override_blocked_but_selection_changed")
        if previously_correct_regressed:
            buckets.append("previously_correct_regressed")
        for bk in buckets:
            bucket_counts[bk] += 1

        if prediction_changed_any:
            for ft, on in {
                "triggered_any": int(b.get("broad_triggered", 0) == 1 or c.get("cons_triggered", 0) == 1),
                "added_any": added_any,
                "duplicate_skip_any": dup_any,
                "gold_present_delta_positive": int(gold_present_delta > 0),
                "conservative_override_allowed": int(c.get("cons_override_allowed", 0) == 1),
                "conservative_override_blocked": int(c.get("cons_override_allowed", 0) == 0),
                "conservative_frozen": int(c.get("cons_frozen", 0) == 1),
            }.items():
                if on:
                    feature_counts[ft] += 1
                    for bk in buckets:
                        feature_buckets[ft][bk] += 1

        row = {
            "example_id": eid,
            "prediction_changed_any": prediction_changed_any,
            "exact_worsened_any": exact_worsened_any,
            "incumbent_was_correct": int(inc_exact == 1),
            "added_candidate_count_any": int(b.get("broad_added_candidates", 0)) + int(c.get("cons_added_candidates", 0)),
            "duplicate_skip_any": dup_any,
            "triggered_any": int(b.get("broad_triggered", 0) == 1 or c.get("cons_triggered", 0) == 1),
            "conservative_frozen": int(c.get("cons_frozen", 0)),
            "conservative_override_allowed": int(c.get("cons_override_allowed", 0)),
            "conservative_override_block_reason": _norm(c.get("cons_override_block_reason", "")),
            "gold_present_pool_delta_broad": gold_present_delta,
            "buckets": "|".join(sorted(set(buckets))) if buckets else "",
            "broad_reason": _norm(b.get("broad_reason", "")),
            "conservative_reason": _norm(c.get("cons_reason", "")),
            "broad_question_bucket": _norm(b.get("broad_question_bucket", "")),
            "conservative_question_bucket": _norm(c.get("cons_question_bucket", "")),
            "casebook_external_exact": _norm((casebook.get(eid) or {}).get("external_exact")),
            "casebook_pal_exact": _norm((casebook.get(eid) or {}).get("pal_exact")),
        }
        per_case.append(row)

    feature_table: list[dict[str, Any]] = []
    for ft, n in sorted(feature_counts.items(), key=lambda kv: (-kv[1], kv[0])):
        feature_table.append(
            {
                "feature": ft,
                "count_prediction_changed_cases": n,
                "added_candidate_flip_wrong": feature_buckets[ft]["added_candidate_flip_wrong"],
                "duplicate_skip_flip": feature_buckets[ft]["duplicate_skip_flip"],
                "gold_present_improved_but_exact_worse": feature_buckets[ft]["gold_present_improved_but_exact_worse"],
                "override_blocked_but_selection_changed": feature_buckets[ft]["override_blocked_but_selection_changed"],
                "previously_correct_regressed": feature_buckets[ft]["previously_correct_regressed"],
            }
        )

    summary = {
        "meta": {
            "broad_per_case_csv": str(broad_per_case_csv.resolve()),
            "conservative_per_case_csv": str(conservative_per_case_csv.resolve()),
            "paired_casebook_csv": str(paired_casebook_csv.resolve()) if paired_casebook_csv else "",
            "output_dir": str(output_dir.resolve()),
            "api_calls": "none",
        },
        "cases_total": len(all_ids),
        "cases_analyzed_worsened_any": int(sum(1 for r in per_case if int(r["exact_worsened_any"]) == 1)),
        "cases_prediction_changed_any": int(sum(1 for r in per_case if int(r["prediction_changed_any"]) == 1)),
        "bucket_counts": dict(bucket_counts),
        "top_sensitivity_features": [r["feature"] for r in feature_table[:5]],
    }

    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with (output_dir / "per_case_delta.csv").open("w", encoding="utf-8", newline="") as f:
        fns = list(per_case[0].keys()) if per_case else ["example_id"]
        w = csv.DictWriter(f, fieldnames=fns)
        w.writeheader()
        if per_case:
            w.writerows(per_case)
    with (output_dir / "feature_attribution_table.csv").open("w", encoding="utf-8", newline="") as f:
        fns = list(feature_table[0].keys()) if feature_table else ["feature"]
        w = csv.DictWriter(f, fieldnames=fns)
        w.writeheader()
        if feature_table:
            w.writerows(feature_table)

    report_lines = [
        "# Offline selector-sensitivity replay",
        "",
        f"- Cases analyzed: {summary['cases_total']}",
        f"- Prediction changed (any): {summary['cases_prediction_changed_any']}",
        f"- Worsened exact (any): {summary['cases_analyzed_worsened_any']}",
        "",
        "## Bucket counts",
    ]
    for k in (
        "added_candidate_flip_wrong",
        "duplicate_skip_flip",
        "gold_present_improved_but_exact_worse",
        "override_blocked_but_selection_changed",
        "previously_correct_regressed",
    ):
        report_lines.append(f"- {k}: {int(bucket_counts.get(k, 0))}")
    report_lines.extend(
        [
            "",
            "## Top sensitivity features",
            *[f"- {x}" for x in summary["top_sensitivity_features"]],
            "",
            "## Recommendation",
            "- Adopt a no-selection-side-effect exploration logging path: record exploratory candidates outside selector-visible pool until explicit selector-ablation diagnostics pass.",
        ]
    )
    (output_dir / "report.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    p = argparse.ArgumentParser(description="Offline selector-sensitivity replay from gate per-case outputs.")
    p.add_argument("--broad-per-case", type=Path, required=True)
    p.add_argument("--conservative-per-case", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--paired-casebook", type=Path, default=None)
    args = p.parse_args()
    summary = run_replay(
        broad_per_case_csv=args.broad_per_case,
        conservative_per_case_csv=args.conservative_per_case,
        output_dir=args.output_dir,
        paired_casebook_csv=args.paired_casebook,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
