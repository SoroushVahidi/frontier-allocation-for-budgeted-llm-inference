#!/usr/bin/env python3
"""Offline audit of previous failure/loss recovery using local artifacts only."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _index(rows: list[dict[str, str]], key: str = "example_id") -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for row in rows:
        eid = str(row.get(key) or "").strip()
        if eid:
            out[eid] = row
    return out


def _to_int(value: Any) -> int:
    try:
        return int(float(str(value)))
    except Exception:
        return 0


def _bucket_membership(eid: str, bucket_sets: dict[str, set[str]]) -> str:
    labels = [k for k, s in bucket_sets.items() if eid in s]
    return "|".join(sorted(labels)) if labels else "none"


def run(args: argparse.Namespace) -> dict[str, Any]:
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    casebook = _index(_read_csv(Path(args.paired_casebook_csv)))
    coverage = _index(_read_csv(Path(args.path_coverage_csv)))
    broad = _index(_read_csv(Path(args.broad_anchor_csv)))
    conservative = _index(_read_csv(Path(args.conservative_anchor_csv)))
    isolated = _index(_read_csv(Path(args.isolated_anchor_csv)))

    external_only = {
        eid
        for eid, r in casebook.items()
        if _to_int(r.get("external_exact")) == 1 and _to_int(r.get("pal_exact")) == 0
    }
    both_wrong = {
        eid
        for eid, r in casebook.items()
        if _to_int(r.get("external_exact")) == 0 and _to_int(r.get("pal_exact")) == 0
    }
    gold_absent = {
        eid
        for eid, r in coverage.items()
        if _to_int(r.get("gold_absent_everywhere_detectable")) == 1
    }
    rate_ratio_anchors = set(broad) | set(conservative) | set(isolated)
    regressed_prev_correct = {
        eid
        for eid, r in broad.items()
        if _to_int(r.get("incumbent_exact")) == 1 and _to_int(r.get("new_exact")) == 0
    } | {
        eid
        for eid, r in conservative.items()
        if _to_int(r.get("incumbent_exact")) == 1 and _to_int(r.get("conservative_exact")) == 0
    } | {
        eid
        for eid, r in isolated.items()
        if _to_int(r.get("incumbent_exact")) == 1 and _to_int(r.get("log_variant_exact")) == 0
    }

    bucket_sets = {
        "external_only": external_only,
        "both_wrong": both_wrong,
        "gold_absent_everywhere_detectable": gold_absent,
        "rate_ratio_anchors": rate_ratio_anchors,
        "previously_correct_regressed_validation_anchors": regressed_prev_correct,
    }

    previous_union = set().union(*bucket_sets.values())

    table_rows: list[dict[str, Any]] = []
    status_counter = Counter()
    by_bucket = defaultdict(lambda: Counter())

    for eid in sorted(previous_union):
        casebook_row = casebook.get(eid, {})
        isolated_row = isolated.get(eid, {})

        current_exact = None
        current_source = "missing"
        if isolated_row:
            current_exact = _to_int(isolated_row.get("log_variant_exact"))
            current_source = "offline_selector_isolated_exploration_log_anchor_validation_20260507/per_case.csv"
        elif casebook_row:
            current_exact = _to_int(casebook_row.get("pal_exact"))
            current_source = "cohere_paired_pal_retry_vs_external_l1_300case_20260506T194114Z/paired_casebook.csv"

        if current_exact is None:
            recovery_status = "missing_current_output"
        elif current_exact == 1:
            recovery_status = "corrected_now"
        else:
            recovery_status = "still_failing"

        membership = [k for k, s in bucket_sets.items() if eid in s]
        if not membership:
            membership = ["none"]

        status_counter[recovery_status] += 1
        for b in membership:
            by_bucket[b][recovery_status] += 1

        table_rows.append(
            {
                "example_id": eid,
                "original_bucket_membership": _bucket_membership(eid, bucket_sets),
                "current_exact": "" if current_exact is None else current_exact,
                "recovery_status": recovery_status,
                "current_output_source": current_source,
                "casebook_pal_exact": "" if not casebook_row else _to_int(casebook_row.get("pal_exact")),
                "casebook_external_exact": "" if not casebook_row else _to_int(casebook_row.get("external_exact")),
                "coverage_gold_absent_everywhere_detectable": (
                    "" if not coverage.get(eid) else _to_int(coverage[eid].get("gold_absent_everywhere_detectable"))
                ),
            }
        )

    csv_path = output_dir / "case_recovery_table.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(table_rows[0].keys()) if table_rows else ["example_id"])
        writer.writeheader()
        for row in table_rows:
            writer.writerow(row)

    summary = {
        "previous_failure_loss_corpus_definition": {
            "external_only": "external_exact=1 and pal_exact=0 from paired_casebook.csv",
            "both_wrong": "external_exact=0 and pal_exact=0 from paired_casebook.csv",
            "gold_absent_everywhere_detectable": "gold_absent_everywhere_detectable=1 from coverage_table.csv",
            "rate_ratio_anchors": "union of example_id in broad/conservative/isolated gate anchor per_case.csv",
            "previously_correct_regressed_validation_anchors": "incumbent_exact=1 and variant_exact=0 in any gate anchor per_case.csv",
        },
        "latest_current_output_artifacts_used": {
            "preferred_for_anchor_ids": "outputs/offline_selector_isolated_exploration_log_anchor_validation_20260507/per_case.csv",
            "fallback_for_non_anchor_ids": "outputs/cohere_paired_pal_retry_vs_external_l1_300case_20260506T194114Z/paired_casebook.csv",
            "note": "No fresh rerun after latest local code state; this audit uses latest available local artifacts.",
        },
        "counts": {
            "total_unique_previous_failure_loss_cases": len(previous_union),
            "corrected_now": status_counter["corrected_now"],
            "still_failing": status_counter["still_failing"],
            "missing_current_output": status_counter["missing_current_output"],
        },
        "bucket_sizes": {k: len(v) for k, v in bucket_sets.items()},
        "breakdown_by_bucket": {k: dict(v) for k, v in by_bucket.items()},
    }

    summary_path = output_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    report_lines = [
        "# Previous Failure Recovery Audit (Local Artifacts Only)",
        "",
        "## Corpus Definition",
        "- external_only: external exact, PAL wrong (from 300-case paired casebook)",
        "- both_wrong: both external and PAL wrong (from 300-case paired casebook)",
        "- gold_absent_everywhere_detectable: from offline path-coverage counterfactual",
        "- rate_ratio_anchors: union of broad/conservative/selector-isolated anchor example IDs",
        "- previously_correct_regressed_validation_anchors: incumbent exact -> variant wrong",
        "",
        "## Current Output Used",
        "- Preferred: `offline_selector_isolated_exploration_log_anchor_validation_20260507/per_case.csv`",
        "- Fallback: `cohere_paired_pal_retry_vs_external_l1_300case_20260506T194114Z/paired_casebook.csv`",
        "- Important: no fresh rerun after latest code state; this is latest-available-artifact based.",
        "",
        "## Results",
        f"- total unique previous failure/loss cases: {summary['counts']['total_unique_previous_failure_loss_cases']}",
        f"- corrected now: {summary['counts']['corrected_now']}",
        f"- still failing: {summary['counts']['still_failing']}",
        f"- missing/no-current-output: {summary['counts']['missing_current_output']}",
        "",
        "## Breakdown by bucket",
    ]
    for b in sorted(by_bucket):
        c = by_bucket[b]
        report_lines.append(
            f"- {b}: corrected={c.get('corrected_now', 0)}, still_failing={c.get('still_failing', 0)}, missing={c.get('missing_current_output', 0)}"
        )

    (output_dir / "report.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit previous failure/loss recovery from local artifacts.")
    parser.add_argument(
        "--paired-casebook-csv",
        default="outputs/cohere_paired_pal_retry_vs_external_l1_300case_20260506T194114Z/paired_casebook.csv",
    )
    parser.add_argument(
        "--path-coverage-csv",
        default="outputs/offline_pal_path_coverage_counterfactual_20260506/coverage_table.csv",
    )
    parser.add_argument(
        "--broad-anchor-csv",
        default="outputs/offline_rate_ratio_gate_anchor_validation_20260507/per_case.csv",
    )
    parser.add_argument(
        "--conservative-anchor-csv",
        default="outputs/offline_rate_ratio_conservative_gate_anchor_validation_20260507/per_case.csv",
    )
    parser.add_argument(
        "--isolated-anchor-csv",
        default="outputs/offline_selector_isolated_exploration_log_anchor_validation_20260507/per_case.csv",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs/previous_failure_recovery_audit_20260507",
    )
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
