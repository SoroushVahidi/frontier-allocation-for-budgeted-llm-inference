from __future__ import annotations

import json
import csv
from pathlib import Path

import pytest

from scripts.mine_reasoning_edge_sequences import (
    EDGE_COLORS,
    map_edge_color,
    build_case_path,
    build_trace_excerpt_path,
    assign_quality_label,
    mine_motifs,
    mine_transitions,
    load_trace_packets,
    main,
)


# ---------------------------------------------------------------------------
# Edge-color mapper
# ---------------------------------------------------------------------------

def test_all_edge_colors_are_unique():
    assert len(EDGE_COLORS) == len(set(EDGE_COLORS))


@pytest.mark.parametrize("branch_family,expected", [
    ("entity_unit_ledger_reasoning", "target_extraction"),
    ("target_first_reasoning", "target_extraction"),
    ("equation_first_reasoning", "equation_setup"),
    ("backward_from_target_check", "verifier_check"),
    ("pal_code_with_required_target_variable", "PAL_code"),
    ("ratio_base_branch", "ratio_base"),
    ("unit_conversion_branch", "unit_conversion"),
    ("original_before_process_branch", "original_before_process"),
    ("per_unit_share_branch", "per_unit_share"),
    ("profit_revenue_cost_branch", "profit_revenue_cost"),
    ("difference_or_remainder_branch", "difference_remainder"),
    ("target_first_final_transform_branch", "target_extraction"),
])
def test_branch_family_maps_to_expected_color(branch_family, expected):
    assert map_edge_color(branch_family=branch_family) == expected


def test_pal_seed_source_maps_to_PAL_code():
    assert map_edge_color(source="pal_seed") == "PAL_code"


def test_is_pal_exec_maps_to_PAL_code():
    assert map_edge_color(is_pal_exec=True) == "PAL_code"


def test_is_repair_maps_to_repair():
    assert map_edge_color(is_repair=True) == "repair"


def test_is_selector_beats_branch_family():
    # selector flag takes priority
    assert map_edge_color(is_selector=True, branch_family="equation_first_reasoning") == "selector"


def test_unknown_branch_family_falls_back_to_op():
    assert map_edge_color(branch_family="mystery_branch", last_op="subtract") == "difference_remainder"
    assert map_edge_color(branch_family="mystery_branch", last_op="divide") == "ratio_base"


def test_completely_unknown_returns_unknown():
    assert map_edge_color() == "unknown"


# ---------------------------------------------------------------------------
# Path construction
# ---------------------------------------------------------------------------

def _make_case(
    branch_families=None,
    pal_exec_ok="1",
    selected_source="controller_metadata_final_answer",
    trace_steps=None,
):
    branch_families = branch_families or ["entity_unit_ledger_reasoning", "equation_first_reasoning"]
    candidate_rows = [
        {
            "branch_family": bf,
            "branch_slot": str(i + 1),
            "last_operation_family": "subtract",
            "target_alignment_score": "0.9",
            "final_answer_role": "target",
            "exec_ok": "",
        }
        for i, bf in enumerate(branch_families)
    ]
    return {
        "case_id": "openai_gsm8k_test",
        "structural_fields": {"candidate_rows": candidate_rows},
        "pal_exec_summary": {"pal_exec_ok": pal_exec_ok, "pal_execution_status": "success"},
        "selector_metadata": {
            "selected_source": selected_source,
            "selected_answer": "42",
        },
        "action_trace_summary": {
            "trace_excerpt": trace_steps or [],
            "action_trace_step_count": 3,
        },
        "failure_audit_labels": {"question_type": "money"},
    }


def test_build_case_path_includes_branch_colors():
    case = _make_case(["entity_unit_ledger_reasoning", "equation_first_reasoning"])
    path = build_case_path(case)
    assert "target_extraction" in path
    assert "equation_setup" in path


def test_build_case_path_ends_with_selector():
    case = _make_case()
    path = build_case_path(case)
    assert path[-1] == "selector"


def test_build_case_path_includes_PAL_when_exec_ok():
    case = _make_case(pal_exec_ok="1")
    path = build_case_path(case)
    assert "PAL_code" in path


def test_build_case_path_no_PAL_when_exec_fails():
    case = _make_case(pal_exec_ok="0")
    path = build_case_path(case)
    assert "PAL_code" not in path


def test_build_case_path_includes_repair_for_repair_source():
    case = _make_case(selected_source="repair_layer")
    path = build_case_path(case)
    assert "repair" in path
    assert path[-1] == "selector"


def test_build_case_path_deduplicates_same_branch_family():
    # Same branch family at two slots → one color entry
    case = _make_case(["entity_unit_ledger_reasoning", "entity_unit_ledger_reasoning"])
    path = build_case_path(case)
    assert path.count("target_extraction") == 1


def test_build_trace_excerpt_path_pal_seed():
    case = _make_case(trace_steps=[
        {"action": "expand", "branch_id": "pal_seed_0", "source": "pal_seed",
         "extracted_answer": "", "target_alignment_category": ""},
    ])
    trace_path = build_trace_excerpt_path(case)
    assert trace_path == ["PAL_code"]


def test_build_trace_excerpt_path_likely_intermediate():
    case = _make_case(trace_steps=[
        {"action": "expand", "branch_id": "div_0", "source": "",
         "extracted_answer": "", "target_alignment_category": "likely_intermediate_or_mistargeted"},
    ])
    trace_path = build_trace_excerpt_path(case)
    assert trace_path == ["target_extraction"]


# ---------------------------------------------------------------------------
# Quality label assignment
# ---------------------------------------------------------------------------

def test_quality_label_target_aligned_proxy_when_proxy_score_improved():
    gold_map = {"openai_gsm8k_test": {"proxy_score_improved": "True", "proxy_alignment_improved": "False"}}
    case = _make_case()
    assert assign_quality_label(case, gold_map) == "target_aligned_proxy"


def test_quality_label_wrong_when_both_false():
    gold_map = {"openai_gsm8k_test": {"proxy_score_improved": "False", "proxy_alignment_improved": "False"}}
    case = _make_case()
    assert assign_quality_label(case, gold_map) == "wrong"


def test_quality_label_fallback_to_alignment_score_high():
    case = _make_case()  # candidate rows have target_alignment_score=0.9
    # No gold map
    assert assign_quality_label(case, {}) == "target_aligned_proxy"


def test_quality_label_fallback_to_alignment_score_low():
    case = _make_case()
    # Overwrite alignment scores to low value
    for row in case["structural_fields"]["candidate_rows"]:
        row["target_alignment_score"] = "0.2"
    assert assign_quality_label(case, {}) == "wrong"


# ---------------------------------------------------------------------------
# Motif and transition mining
# ---------------------------------------------------------------------------

def test_mine_motifs_finds_unigrams():
    paths = [["A", "B", "C"], ["A", "B", "D"], ["A", "C", "D"]]
    labels = ["target_aligned_proxy", "wrong", "target_aligned_proxy"]
    motifs = mine_motifs(paths, labels, max_seq_len=2, min_support=2, baseline_correct_rate=0.5)
    seqs = [json.loads(m["sequence"]) for m in motifs]
    assert ["A"] in seqs


def test_mine_motifs_respects_min_support():
    paths = [["A", "B"], ["A", "C"], ["D", "E"]]
    labels = ["target_aligned_proxy"] * 3
    # min_support=2 → only A should appear as unigram (appears 2 times)
    motifs = mine_motifs(paths, labels, max_seq_len=1, min_support=2, baseline_correct_rate=0.5)
    seqs = [json.loads(m["sequence"]) for m in motifs]
    assert ["A"] in seqs
    assert ["D"] not in seqs


def test_mine_motifs_computes_precision():
    paths = [["A", "B"], ["A", "B"]]
    labels = ["target_aligned_proxy", "wrong"]
    motifs = mine_motifs(paths, labels, max_seq_len=1, min_support=2, baseline_correct_rate=0.5)
    a_motif = next(m for m in motifs if json.loads(m["sequence"]) == ["A"])
    assert a_motif["precision"] == pytest.approx(0.5)


def test_mine_motifs_computes_lift():
    paths = [["A"]] * 4
    labels = ["target_aligned_proxy"] * 4
    motifs = mine_motifs(paths, labels, max_seq_len=1, min_support=3, baseline_correct_rate=0.5)
    a_motif = next(m for m in motifs if json.loads(m["sequence"]) == ["A"])
    assert a_motif["lift"] == pytest.approx(2.0)


def test_mine_transitions_finds_bigram_rule():
    paths = [["A", "B", "C"], ["A", "B", "D"], ["A", "B", "C"]]
    labels = ["target_aligned_proxy", "wrong", "target_aligned_proxy"]
    trans = mine_transitions(paths, labels, max_prefix_len=1, min_support=2, baseline_correct_rate=0.5)
    prefixes = [json.loads(t["prefix_sequence"]) for t in trans]
    assert ["A"] in prefixes


def test_mine_transitions_respects_min_support():
    paths = [["X", "Y"], ["A", "B"]]
    labels = ["target_aligned_proxy", "wrong"]
    trans = mine_transitions(paths, labels, max_prefix_len=1, min_support=2, baseline_correct_rate=0.5)
    assert len(trans) == 0  # nothing hits min_support=2


# ---------------------------------------------------------------------------
# End-to-end: main() on synthetic data
# ---------------------------------------------------------------------------

def _write_synthetic_packets(path: Path) -> None:
    batch = {
        "batch_id": "test",
        "case_count": 3,
        "cases": [
            {
                "case_id": f"openai_gsm8k_{i}",
                "structural_fields": {
                    "candidate_rows": [
                        {
                            "branch_family": "equation_first_reasoning",
                            "branch_slot": "1",
                            "last_operation_family": "subtract",
                            "target_alignment_score": "0.9",
                            "final_answer_role": "target",
                            "exec_ok": "",
                        },
                        {
                            "branch_family": "backward_from_target_check",
                            "branch_slot": "2",
                            "last_operation_family": "subtract",
                            "target_alignment_score": "0.95",
                            "final_answer_role": "target",
                            "exec_ok": "",
                        },
                    ]
                },
                "pal_exec_summary": {
                    "pal_exec_ok": "1",
                    "pal_execution_status": "success",
                    "pal_retry_reason": "",
                },
                "selector_metadata": {
                    "selected_source": "controller_metadata_final_answer",
                    "selected_answer": "42",
                    "frontier_answer": "42",
                    "direct_reserve_answer": "40",
                    "gold_present_in_candidate_pool": "",
                    "answer_group_support_counts": {},
                },
                "action_trace_summary": {
                    "trace_excerpt": [
                        {
                            "action": "expand",
                            "branch_id": "div_0",
                            "source": "",
                            "extracted_answer": "",
                            "target_alignment_category": "likely_target_aligned",
                        }
                    ],
                    "action_trace_step_count": 3,
                    "selection_reason": "direct_frontier_agree",
                    "final_answer_source": "controller_metadata_final_answer",
                    "latest_method_failure_tag": "",
                    "failure_category": "",
                    "failure_family": "",
                },
                "failure_audit_labels": {
                    "question_type": "money/cost/revenue",
                    "diversity_bucket": "low (1 group)",
                    "num_candidate_groups": 1,
                    "candidate_pool_status": "Both wrong",
                },
            }
            for i in range(3)
        ],
    }
    path.write_text(json.dumps(batch) + "\n", encoding="utf-8")


def test_main_no_api_produces_all_outputs(tmp_path: Path) -> None:
    packets = tmp_path / "trace_packets.jsonl"
    _write_synthetic_packets(packets)
    out = tmp_path / "out"

    result = main([
        "--trace-packets", str(packets),
        "--out-dir", str(out),
        "--max-seq-len", "3",
        "--min-support", "2",
    ])

    assert result["api_calls_made"] == 0
    assert result["cases_loaded"] == 3
    assert result["no_gold_features"] is True
    assert (out / "manifest.json").is_file()
    assert (out / "edge_color_rows.csv").is_file()
    assert (out / "path_sequence_rows.csv").is_file()
    assert (out / "motif_summary.csv").is_file()
    assert (out / "transition_rules.csv").is_file()
    assert (out / "case_sequence_casebook.csv").is_file()
    assert (out / "report.md").is_file()


def test_main_path_sequence_rows_contain_required_columns(tmp_path: Path) -> None:
    packets = tmp_path / "trace_packets.jsonl"
    _write_synthetic_packets(packets)
    out = tmp_path / "out"
    main(["--trace-packets", str(packets), "--out-dir", str(out), "--min-support", "1"])

    rows = list(csv.DictReader((out / "path_sequence_rows.csv").open()))
    assert len(rows) == 3
    required_cols = {"case_id", "path_json", "path_length", "quality_label", "question_type"}
    assert required_cols.issubset(set(rows[0].keys()))


def test_main_edge_rows_all_colors_are_valid(tmp_path: Path) -> None:
    packets = tmp_path / "trace_packets.jsonl"
    _write_synthetic_packets(packets)
    out = tmp_path / "out"
    main(["--trace-packets", str(packets), "--out-dir", str(out), "--min-support", "1"])

    valid = set(EDGE_COLORS)
    rows = list(csv.DictReader((out / "edge_color_rows.csv").open()))
    for row in rows:
        assert row["edge_color"] in valid, f"Invalid color: {row['edge_color']}"


def test_main_no_gold_features_flag_set(tmp_path: Path) -> None:
    packets = tmp_path / "trace_packets.jsonl"
    _write_synthetic_packets(packets)
    out = tmp_path / "out"
    result = main(["--trace-packets", str(packets), "--out-dir", str(out)])

    manifest = json.loads((out / "manifest.json").read_text())
    assert manifest["no_gold_features"] is True
    assert manifest["api_calls_made"] == 0


def test_main_with_limit(tmp_path: Path) -> None:
    packets = tmp_path / "trace_packets.jsonl"
    _write_synthetic_packets(packets)
    out = tmp_path / "out"
    result = main([
        "--trace-packets", str(packets),
        "--out-dir", str(out),
        "--limit", "2",
    ])
    assert result["cases_loaded"] == 2
