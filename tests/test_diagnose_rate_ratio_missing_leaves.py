from __future__ import annotations

import csv
import json

from scripts.diagnose_rate_ratio_missing_leaves import run


def _write_csv(path, rows, fieldnames):
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def test_diagnose_rate_ratio_missing_leaves(tmp_path):
    failure_jsonl = tmp_path / "failure_cases.jsonl"
    anchor_csv = tmp_path / "anchor_cases.csv"
    recovery_csv = tmp_path / "recovery.csv"
    out_dir = tmp_path / "out"

    rows = [
        {
            "example_id": "openai_gsm8k_812",
            "question": "A factory makes 120 units per day and then half are shipped.",
            "gold_answer": "40",
            "our_answer": "20",
            "our_exact": 0,
            "external_answer": "40",
            "operation_hints": "rate_ratio|temporal_change",
            "failure_stage": "gold_absent_everywhere_detectable",
            "outcome_bucket": "external_only",
            "quantity_bucket": "qnum_4_5",
            "our_candidate_diversity": 1,
            "our_candidate_pool": [{"normalized_answer": "20"}],
            "our_discovery_trace": [{"action": "compute"}],
            "external_discovery_trace": [{"action": "compute"}],
        },
        {
            "example_id": "openai_gsm8k_999",
            "question": "Non-selected due to stage",
            "gold_answer": "10",
            "our_answer": "5",
            "our_exact": 0,
            "operation_hints": "rate_ratio",
            "failure_stage": "gold_in_trace_candidates",
            "outcome_bucket": "both_wrong",
        },
    ]
    with failure_jsonl.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")

    _write_csv(
        anchor_csv,
        [{"example_id": "openai_gsm8k_812"}],
        fieldnames=["example_id"],
    )
    _write_csv(
        recovery_csv,
        [
            {
                "example_id": "openai_gsm8k_812",
                "recovery_status": "still_failing",
                "original_bucket_membership": "rate_ratio_anchors",
                "current_output_source": "x",
            },
            {
                "example_id": "openai_gsm8k_778",
                "recovery_status": "corrected_now",
                "original_bucket_membership": "rate_ratio_anchors|gold_absent_everywhere_detectable",
                "current_output_source": "y",
            },
        ],
        fieldnames=["example_id", "recovery_status", "original_bucket_membership", "current_output_source"],
    )

    summary = run(
        failure_cases_jsonl=failure_jsonl,
        anchor_cases_csv=anchor_csv,
        recovery_table_csv=recovery_csv,
        output_dir=out_dir,
    )
    assert summary["selected_case_count"] == 1
    assert summary["anchor_focus_case_ids"] == ["openai_gsm8k_812"]
    assert summary["recovered_rate_ratio_reference_cases"][0]["example_id"] == "openai_gsm8k_778"
    assert (out_dir / "summary.json").is_file()
    assert (out_dir / "case_diagnosis.csv").is_file()
    assert (out_dir / "root_cause_table.csv").is_file()
    assert (out_dir / "anchor_review.md").is_file()
