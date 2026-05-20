from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

from scripts.run_final_target_verifier_offline_replay import (
    _packet_completeness_summary,
    _replay_case,
    _select_with_verifier_calibrated_v1,
)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def _make_replay_case() -> dict[str, object]:
    return {
        "case_id": "c1",
        "primary_subset": "wrong_supported_consensus_97",
        "question": "A book costs $12 and a pen costs $3. What is the total cost?",
        "model_final_prediction": "12",
        "direct_reserve_answer": "12",
        "frontier_candidate_answer": "15",
        "selector_metadata": {
            "selected_answer": "12",
            "selected_source": "repair_layer",
        },
        "candidate_answers": ["12", "15"],
        "candidate_answer_groups": [
            {"candidate_answer": "12", "support_count": 1, "structural_selector_score": 0.55},
            {"candidate_answer": "15", "support_count": 2, "structural_selector_score": 0.80},
        ],
        "answer_group_support_counts": {"12": 1, "15": 2},
        "action_trace_summary": {
            "latest_method_failure_tag": "correct answer absent from explored tree",
            "trace_excerpt": [
                {
                    "reasoning_text": "subtotal is 12",
                    "target_alignment_category": "likely_intermediate_or_mistargeted",
                },
                {
                    "reasoning_text": "therefore 15",
                    "target_alignment_category": "target",
                },
            ],
        },
        "pal_exec_summary": {
            "pal_execution_status": "success",
            "pal_exec_ok": "1",
            "pal_parse_ok": "1",
            "pal_safety_ok": "1",
        },
        "structural_fields": {
            "candidate_rows": [
                {
                    "candidate_answer": "12",
                    "candidate_trace": "subtotal is 12",
                    "candidate_code": "",
                    "final_answer_role": "intermediate",
                    "structural_selector_score": 0.55,
                    "support_count": 1,
                    "entity_unit_ledger_proxy": {"ledger_status": "unknown"},
                },
                {
                    "candidate_answer": "15",
                    "candidate_trace": "therefore 15",
                    "candidate_code": "",
                    "final_answer_role": "target",
                    "structural_selector_score": 0.80,
                    "support_count": 2,
                    "entity_unit_ledger_proxy": {"ledger_status": "unknown"},
                },
            ]
        },
    }


def test_replay_prefers_target_candidate_over_repair_collapse() -> None:
    row = _replay_case(_make_replay_case())
    assert row["baseline_answer"] == "12"
    assert row["combined_answer"] == "15"
    assert row["replay_final_answer_role"] == "target"
    assert row["proxy_alignment_improved"] is True


def test_calibrated_variant_keeps_unapproved_source_and_type_baseline() -> None:
    case = _make_replay_case()
    case["selector_metadata"] = {"selected_answer": "12", "selected_source": "repair_layer"}
    case["question"] = "What number is written on the sign?"
    case["frontier_candidate_answer"] = "99"
    case["candidate_answers"] = ["12", "99"]
    case["candidate_answer_groups"] = [
        {"candidate_answer": "12", "support_count": 1, "structural_selector_score": 0.55},
        {"candidate_answer": "99", "support_count": 3, "structural_selector_score": 0.95},
    ]
    case["answer_group_support_counts"] = {"12": 1, "99": 3}
    case["structural_fields"]["candidate_rows"] = [
        {
            "candidate_answer": "12",
            "candidate_trace": "subtotal is 12",
            "candidate_code": "",
            "final_answer_role": "intermediate",
            "structural_selector_score": 0.55,
            "support_count": 1,
            "entity_unit_ledger_proxy": {"ledger_status": "unknown"},
        },
        {
            "candidate_answer": "99",
            "candidate_trace": "therefore 99",
            "candidate_code": "",
            "final_answer_role": "target",
            "structural_selector_score": 0.95,
            "support_count": 3,
            "entity_unit_ledger_proxy": {"ledger_status": "unknown"},
        },
    ]
    row = _replay_case(case, variant="calibrated_v1")
    assert row["baseline_answer"] == "12"
    assert row["combined_answer"] == "12"
    assert row["verifier_selected_source"] == "baseline_candidate"
    assert row["selection_variant"] == "calibrated_v1"


def test_calibrated_variant_accepts_allowed_transform_type() -> None:
    case = _make_replay_case()
    case["selector_metadata"] = {"selected_answer": "12", "selected_source": "controller_metadata_final_answer"}
    case["question"] = "A train is 4 miles away and the other train is 7 miles away. How many more miles is the second train away?"
    case["candidate_answer_groups"] = [
        {"candidate_answer": "12", "support_count": 1, "structural_selector_score": 0.20},
        {"candidate_answer": "15", "support_count": 2, "structural_selector_score": 0.90},
    ]
    case["answer_group_support_counts"] = {"12": 1, "15": 2}
    case["candidate_answers"] = ["12", "15"]
    case["direct_reserve_answer"] = "12"
    case["frontier_candidate_answer"] = "15"
    case["structural_fields"]["candidate_rows"][0]["final_answer_role"] = "intermediate"
    case["structural_fields"]["candidate_rows"][1]["final_answer_role"] = "target"
    row = _replay_case(case, variant="calibrated_v1")
    assert row["combined_answer"] == "15"
    assert row["verifier_selected_source"] == "our_candidate"


def test_packet_completeness_counts_sparse_packets() -> None:
    complete_case = _make_replay_case()
    sparse_case = {
        "case_id": "c2",
        "primary_subset": "wrong_supported_consensus_97",
        "candidate_answers": [],
        "candidate_answer_groups": [],
        "answer_group_support_counts": {},
        "action_trace_summary": {},
        "pal_exec_summary": {},
        "structural_fields": {},
    }
    summary = _packet_completeness_summary([complete_case, sparse_case], min_completeness=0.75)
    assert summary["case_count"] == 2
    assert summary["question_present_rate"] == 0.5
    assert summary["prediction_present_rate"] == 0.5
    assert summary["empty_packet_count"] == 1
    assert summary["warnings"]


def test_script_writes_gold_free_casebook(tmp_path: Path) -> None:
    packets = tmp_path / "trace_packets.jsonl"
    output_dir = tmp_path / "out"
    _write_jsonl(
        packets,
        [
            {
                "provider": "cohere",
                "model": "command-r-plus-08-2024",
                "batch_id": "batch-1",
                "cases_reviewed": ["c1"],
                "case_count": 1,
                "mode": "pattern_discovery",
                "cases": [_make_replay_case()],
            }
        ],
    )

    subprocess.check_call(
        [
            sys.executable,
            "scripts/run_final_target_verifier_offline_replay.py",
            "--trace-packets",
            str(packets),
            "--output-dir",
            str(output_dir),
        ],
        cwd=Path(__file__).resolve().parents[1],
    )

    header = next(csv.reader((output_dir / "replay_casebook.csv").read_text(encoding="utf-8").splitlines()))
    assert "gold_answer" not in header
    summary = json.loads((output_dir / "replay_summary.json").read_text(encoding="utf-8"))
    assert summary["case_count"] == 1
    assert summary["proxy_alignment_improved_count"] == 1


def test_calibrated_selector_helper_requires_allowed_type_and_source() -> None:
    case = _make_replay_case()
    case["model_final_prediction"] = "1"
    case["selector_metadata"] = {"selected_answer": "1", "selected_source": "repair_layer"}
    case["question"] = "A store has 4 apples and 7 pears. How many total pieces of fruit are there?"
    case["candidate_answers"] = ["1", "11"]
    case["candidate_answer_groups"] = [
        {"candidate_answer": "1", "support_count": 1, "structural_selector_score": 0.55},
        {"candidate_answer": "11", "support_count": 3, "structural_selector_score": 0.95},
    ]
    case["answer_group_support_counts"] = {"1": 1, "11": 3}
    case["direct_reserve_answer"] = "1"
    case["frontier_candidate_answer"] = "11"
    case["structural_fields"]["candidate_rows"] = [
        {
            "candidate_answer": "1",
            "candidate_trace": "subtotal is 1",
            "candidate_code": "",
            "final_answer_role": "intermediate",
            "structural_selector_score": 0.55,
            "support_count": 1,
            "entity_unit_ledger_proxy": {"ledger_status": "unknown"},
        },
        {
            "candidate_answer": "11",
            "candidate_trace": "therefore 11",
            "candidate_code": "",
            "final_answer_role": "target",
            "structural_selector_score": 0.95,
            "support_count": 3,
            "entity_unit_ledger_proxy": {"ledger_status": "unknown"},
        },
    ]
    chosen = _select_with_verifier_calibrated_v1(case, _replay_case(case)["candidates"])
    assert chosen["verifier_selected_source"] == "baseline_candidate"
