from __future__ import annotations

import csv
import json

from scripts.mine_failure_case_patterns import run


def _write_csv(path, rows, fieldnames):
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def test_mine_failure_case_patterns_outputs(tmp_path):
    failure_csv = tmp_path / "failure_cases.csv"
    failure_jsonl = tmp_path / "failure_cases.jsonl"
    recovery_csv = tmp_path / "case_recovery_table.csv"
    out_dir = tmp_path / "out"

    csv_rows = [
        {
            "example_id": "a",
            "outcome_bucket": "external_only",
            "our_exact": "0",
            "external_exact": "1",
            "our_gold_in_pool": "0",
            "failure_stage": "gold_absent_everywhere_detectable",
            "operation_hints": "rate_ratio|temporal_change",
            "quantity_bucket": "qnum_4_5",
            "our_candidate_diversity": "2",
            "anchor_regression": "1",
        },
        {
            "example_id": "b",
            "outcome_bucket": "both_wrong",
            "our_exact": "0",
            "external_exact": "0",
            "our_gold_in_pool": "1",
            "failure_stage": "gold_in_trace_candidates",
            "operation_hints": "difference",
            "quantity_bucket": "qnum_2_3",
            "our_candidate_diversity": "1",
            "anchor_regression": "0",
        },
        {
            "example_id": "c",
            "outcome_bucket": "external_only",
            "our_exact": "0",
            "external_exact": "1",
            "our_gold_in_pool": "0",
            "failure_stage": "gold_absent_everywhere_detectable",
            "operation_hints": "rate_ratio",
            "quantity_bucket": "qnum_4_5",
            "our_candidate_diversity": "3",
            "anchor_regression": "0",
        },
    ]
    _write_csv(failure_csv, csv_rows, fieldnames=list(csv_rows[0].keys()))

    with failure_jsonl.open("w", encoding="utf-8") as f:
        f.write(json.dumps({"example_id": "a", "our_discovery_trace": [1], "external_discovery_trace": [1]}) + "\n")
        f.write(json.dumps({"example_id": "b", "our_discovery_trace": [1], "external_discovery_trace": []}) + "\n")
        f.write(json.dumps({"example_id": "c", "our_discovery_trace": [1], "external_discovery_trace": [1]}) + "\n")

    recovery_rows = [
        {"example_id": "a", "recovery_status": "still_failing"},
        {"example_id": "b", "recovery_status": "corrected_now"},
        {"example_id": "c", "recovery_status": "still_failing"},
    ]
    _write_csv(recovery_csv, recovery_rows, fieldnames=["example_id", "recovery_status"])

    summary = run(
        failure_cases_jsonl=failure_jsonl,
        failure_cases_csv=failure_csv,
        recovery_table_csv=recovery_csv,
        output_dir=out_dir,
    )

    assert summary["still_failing_cases_mined"] == 2
    assert summary["counts_by_outcome_bucket"]["external_only"] == 2
    assert summary["counts_by_failure_stage"]["gold_absent_everywhere_detectable"] == 2
    assert (out_dir / "summary.json").is_file()
    assert (out_dir / "failure_archetypes.csv").is_file()
    assert (out_dir / "anchor_cases.csv").is_file()
    assert (out_dir / "pattern_mining_report.md").is_file()
