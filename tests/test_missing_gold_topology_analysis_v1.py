from __future__ import annotations

import csv
import json
from pathlib import Path

from scripts import analyze_missing_gold_topology_v1 as topo


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def test_no_api_at_import() -> None:
    source = Path(topo.__file__).read_text(encoding="utf-8")
    prefix = source.split("def _load_cohere_client", 1)[0]
    assert "import cohere" not in prefix


def test_numeric_candidate_extraction_and_dedup() -> None:
    candidate_map: dict[str, dict] = {}
    topo.add_candidate_record(candidate_map, "12", provenance="a")
    topo.add_candidate_record(candidate_map, 12.0, provenance="b")
    topo.add_candidate_record(candidate_map, "12.00", provenance="c")
    assert list(candidate_map) == ["12"]
    row = candidate_map["12"]
    assert row["value"] == 12.0
    assert row["provenance_types"] == {"a", "b", "c"}
    assert row["occurrence_count"] == 3


def test_closest_candidate_selection() -> None:
    candidates = [
        {"value": 10.0, "value_normalized": "10", "occurrence_count": 1, "support_count": 0.0, "provenance_types": []},
        {"value": 24.0, "value_normalized": "24", "occurrence_count": 2, "support_count": 0.0, "provenance_types": []},
        {"value": 21.0, "value_normalized": "21", "occurrence_count": 1, "support_count": 0.0, "provenance_types": []},
    ]
    closest = topo.select_closest_numeric_candidate(candidates, 23.0)
    assert closest is not None
    assert closest["value_normalized"] == "24"


def test_missing_edge_taxonomy_per_unit_to_total() -> None:
    edge = topo.assign_missing_edge_type(
        question="Each box has 6 apples. What is the total number of apples in 4 boxes?",
        target_text="total number of apples",
        question_type="multi-step arithmetic",
        prompt_gold_consistency="consistent",
        selector_rebinding_signal=False,
        primary_category="",
        previous_category="",
        failure_axis="",
        diagnosis="Model found apples per box but never multiplied to total.",
        minimal_fix="Multiply the per-box count by box_count.",
        target_correct=True,
        relative_distance=0.3,
    )
    assert edge == "per_unit_to_total"


def test_missing_edge_taxonomy_difference_to_total() -> None:
    edge = topo.assign_missing_edge_type(
        question="Tom has 5 more marbles than Ana. Together they have 17 marbles.",
        target_text="total marbles together",
        question_type="multi-step arithmetic",
        prompt_gold_consistency="consistent",
        selector_rebinding_signal=False,
        primary_category="",
        previous_category="",
        failure_axis="",
        diagnosis="The branch stayed on the difference and never rebounded to the total.",
        minimal_fix="Convert the difference relation into the combined total.",
        target_correct=True,
        relative_distance=0.4,
    )
    assert edge == "difference_to_total"


def test_missing_edge_taxonomy_unit_conversion() -> None:
    edge = topo.assign_missing_edge_type(
        question="A pole is 480 inches tall. How many feet tall is it?",
        target_text="height in feet",
        question_type="unit conversion",
        prompt_gold_consistency="consistent",
        selector_rebinding_signal=False,
        primary_category="unit_or_scale_error_in_formula",
        previous_category="unit_or_scale_error",
        failure_axis="unit_scale",
        diagnosis="Forgot the final inches-to-feet conversion.",
        minimal_fix="Divide by 12.",
        target_correct=True,
        relative_distance=11.0,
    )
    assert edge == "unit_conversion"


def test_missing_edge_taxonomy_ratio_base_correction() -> None:
    edge = topo.assign_missing_edge_type(
        question="The heartworm check is 60% of the total bill. How much change is left?",
        target_text="change left",
        question_type="ratio/proportion/percentage",
        prompt_gold_consistency="consistent",
        selector_rebinding_signal=False,
        primary_category="ratio_or_percentage_base_error_in_formula",
        previous_category="ratio_or_percentage_base_error",
        failure_axis="relation_construction",
        diagnosis="Used 60% of the subtotal instead of 60% of the total bill.",
        minimal_fix="Solve the circular total relation.",
        target_correct=True,
        relative_distance=0.8,
    )
    assert edge == "percentage_base_correction"


def test_missing_edge_taxonomy_selector_rebinding() -> None:
    edge = topo.assign_missing_edge_type(
        question="Question text",
        target_text="target",
        question_type="unknown",
        prompt_gold_consistency="consistent",
        selector_rebinding_signal=True,
        primary_category="",
        previous_category="",
        failure_axis="",
        diagnosis="Gold was already in the pool.",
        minimal_fix="Rebind selector.",
        target_correct=True,
        relative_distance=0.0,
    )
    assert edge == "selector_rebinding"


def test_missing_edge_taxonomy_prompt_gold_inconsistent() -> None:
    edge = topo.assign_missing_edge_type(
        question="What percent is left?",
        target_text="percent left",
        question_type="ratio/proportion/percentage",
        prompt_gold_consistency="definite_mismatch",
        selector_rebinding_signal=False,
        primary_category="",
        previous_category="",
        failure_axis="",
        diagnosis="Prompt surface and casebook gold disagree.",
        minimal_fix="Audit artifacts.",
        target_correct=True,
        relative_distance=0.1,
    )
    assert edge == "prompt_gold_inconsistent"


def test_steps_from_closest_node_heuristic() -> None:
    assert topo.estimate_steps_from_closest_node(
        gold_present=True,
        missing_edge_type="selector_rebinding",
        deterministic_repair_possible=True,
        new_generation_needed=False,
    ) == 0
    assert topo.estimate_steps_from_closest_node(
        gold_present=False,
        missing_edge_type="unit_conversion",
        deterministic_repair_possible=True,
        new_generation_needed=False,
    ) == 1
    assert topo.estimate_steps_from_closest_node(
        gold_present=False,
        missing_edge_type="source_fact_missing",
        deterministic_repair_possible=False,
        new_generation_needed=True,
    ) == 3


def test_strict_api_label_parser() -> None:
    payload = {
        "closest_explored_node": "formula variable revenue",
        "closest_candidate_value": "45",
        "missing_edge_type": "percentage_base_correction",
        "missing_edge_description": "Wrong percentage base.",
        "estimated_steps_from_closest_node_to_gold": 1,
        "needed_branch_family": "ratio_base_check",
        "tree_topology_label": "near_miss_pool",
        "existing_tree_had_needed_facts": True,
        "deterministic_repair_possible": True,
        "new_generation_needed": False,
        "confidence": 0.8,
        "rationale": "The needed facts were present.",
    }
    parsed, error = topo.parse_api_label_response(json.dumps(payload))
    assert error == ""
    assert parsed is not None
    assert parsed["missing_edge_type"] == "percentage_base_correction"

    bad = dict(payload)
    bad["missing_edge_type"] = "bad_label"
    parsed, error = topo.parse_api_label_response(json.dumps(bad))
    assert parsed is None
    assert error == "invalid_missing_edge_type"


def test_prompt_audit_fields() -> None:
    audit = topo._audit_prompt("ANALYSIS MODE ONLY\nquestion: hi", "case_1", False)
    assert audit["case_id"] == "case_1"
    assert audit["gold_in_prompt"] is False
    assert audit["not_for_runtime"] is True
    assert audit["not_for_provider_request_reuse"] is True


def test_gold_conditioned_prompt_marked_analysis_only() -> None:
    packet = {
        "case_id": "case_1",
        "question": "What is the total?",
        "gold_answer": "23",
        "baseline_selected_answer": "20",
        "target_text": "total",
        "explored_candidates": [],
        "bftc_summary": {},
        "executable_summary": {},
        "candidate_rebinding_summary": {},
        "prompt_gold_consistency": "consistent",
    }
    prompt = topo.build_api_prompt(packet, allow_gold=True)
    audit = topo._audit_prompt(prompt, "case_1", True)
    assert "ANALYSIS MODE ONLY" in prompt
    assert '"gold_answer"' in prompt
    assert audit["analysis_only_gold_conditioned"] is True
    assert audit["not_for_runtime"] is True
    assert audit["not_for_provider_request_reuse"] is True


def test_summary_counts() -> None:
    rows = [
        {
            "case_id": "a",
            "missing_edge_type": "unit_conversion",
            "needed_branch_family": "unit_conversion_branch",
            "tree_topology_label": "near_miss_pool",
            "estimated_steps_from_closest_node_to_gold": 1,
            "label_source": "heuristic",
            "deterministic_local_repair_possible": True,
            "new_model_generation_edge_needed": False,
            "existing_information_sufficient": True,
        },
        {
            "case_id": "b",
            "missing_edge_type": "selector_rebinding",
            "needed_branch_family": "selector_rebinding",
            "tree_topology_label": "selector_only_failure",
            "estimated_steps_from_closest_node_to_gold": 0,
            "label_source": "heuristic_plus_api",
            "deterministic_local_repair_possible": True,
            "new_model_generation_edge_needed": False,
            "existing_information_sufficient": True,
        },
    ]
    summary = topo.build_summary(rows, {"manifest": "x"})
    assert summary["case_count"] == 2
    assert summary["missing_edge_type_counts"]["selector_rebinding"] == 1
    assert summary["needed_branch_family_counts"]["unit_conversion_branch"] == 1
    assert summary["distance_to_gold_step_counts"]["0"] == 1


def test_cli_smoke_tiny_fixtures(tmp_path: Path) -> None:
    casebook = tmp_path / "casebook.csv"
    with casebook.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["case_id", "question_type", "gold"])
        writer.writeheader()
        writer.writerow({"case_id": "openai_gsm8k_1", "question_type": "unit conversion", "gold": "40"})

    trace_packets = tmp_path / "trace_packets.jsonl"
    trace_row = {
        "batch_id": "b1",
        "cases": [
            {
                "case_id": "openai_gsm8k_1",
                "question": "A pole is 480 inches tall. How many feet tall is it?",
                "candidate_answers": ["480", "48", "40"],
                "selector_candidate_pool": ["480", "48"],
                "model_final_prediction": "480",
                "selector_metadata": {"selected_answer": "480"},
                "candidate_answer_groups": [{"candidate_answer": "480", "source_family": "selector_answer_group", "support_count": 2}],
                "structural_fields": {
                    "candidate_rows": [
                        {
                            "candidate_answer": "480",
                            "branch_family": "unit_conversion_branch",
                            "candidate_trace": "Converted nothing yet; still in inches.",
                            "structural_selector_score": 0.7,
                        }
                    ]
                },
            }
        ],
    }
    _write_jsonl(trace_packets, [trace_row])

    out_dir = tmp_path / "out"
    summary = topo.main(
        [
            "--trace-packets",
            str(trace_packets),
            "--casebook",
            str(casebook),
            "--out-dir",
            str(out_dir),
            "--limit",
            "1",
        ]
    )
    assert summary["case_count"] == 1
    assert (out_dir / "missing_gold_topology_summary.json").exists()
    assert (out_dir / "missing_gold_topology_rows.jsonl").exists()
    assert (out_dir / "missing_gold_topology_rows.csv").exists()
    assert (out_dir / "missing_gold_topology_report.md").exists()
    assert (out_dir / "prompt_audit.json").exists()

    rows = [json.loads(line) for line in (out_dir / "missing_gold_topology_rows.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    assert rows[0]["closest_numeric_candidate_to_gold"] == "40"
    assert rows[0]["needed_branch_family"] in topo.NEEDED_BRANCH_FAMILIES
