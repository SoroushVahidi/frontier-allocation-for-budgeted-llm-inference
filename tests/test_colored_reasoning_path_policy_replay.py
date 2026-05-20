from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from scripts.replay_colored_reasoning_path_policy_v1 import (
    build_candidate_prefix_path,
    build_transition_lift_index,
    load_casebook,
    load_motif_summary,
    load_transition_rules,
    main,
    process_case,
    score_path,
    _pal_vc_lift,
)


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------

def _make_rules(rows: list[dict]) -> list[dict[str, str]]:
    """Minimal transition-rule rows."""
    defaults = {
        "prefix_sequence": '["PAL_code"]',
        "next_color": "verifier_check",
        "prefix_len": "1",
        "support": "5",
        "correct_count": "4",
        "success_rate": "0.80",
        "lift": "1.60",
        "example_case_indices": "[]",
        "example_case_ids": "[]",
    }
    return [{**defaults, **r} for r in rows]


def _write_rules(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("(empty)\n")
        return
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def _write_casebook(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("(empty)\n")
        return
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def _make_case(
    case_id: str = "case_1",
    candidates: list[dict] | None = None,
    pal_exec_ok: str = "0",
    selected_source: str = "controller_metadata_final_answer",
) -> dict:
    if candidates is None:
        candidates = [
            {
                "branch_family": "equation_first_reasoning",
                "branch_slot": "1",
                "last_operation_family": "subtract",
                "target_alignment_score": "0.9",
                "candidate_answer": "42",
                "final_answer_role": "target",
                "exec_ok": "",
            }
        ]
    return {
        "case_id": case_id,
        "structural_fields": {"candidate_rows": candidates},
        "pal_exec_summary": {
            "pal_exec_ok": pal_exec_ok,
            "pal_execution_status": "success" if pal_exec_ok == "1" else "",
        },
        "selector_metadata": {
            "selected_source": selected_source,
            "selected_answer": "42",
        },
        "action_trace_summary": {"trace_excerpt": [], "action_trace_step_count": 2},
        "failure_audit_labels": {"question_type": "money"},
    }


def _write_packets(path: Path, cases: list[dict]) -> None:
    batch = {"batch_id": "test", "case_count": len(cases), "cases": cases}
    path.write_text(json.dumps(batch) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# build_transition_lift_index
# ---------------------------------------------------------------------------

def test_lift_index_only_prefix_len_1():
    rules = _make_rules([
        {"prefix_sequence": '["PAL_code"]', "next_color": "verifier_check",
         "prefix_len": "1", "lift": "1.60"},
        {"prefix_sequence": '["PAL_code", "equation_setup"]', "next_color": "selector",
         "prefix_len": "2", "lift": "0.80"},
    ])
    idx = build_transition_lift_index(rules)
    assert ("PAL_code", "verifier_check") in idx
    assert ("PAL_code", "equation_setup") not in idx  # prefix_len=2 excluded


def test_lift_index_takes_max_when_duplicate_pairs():
    rules = _make_rules([
        {"prefix_sequence": '["A"]', "next_color": "B", "prefix_len": "1", "lift": "1.2"},
        {"prefix_sequence": '["A"]', "next_color": "B", "prefix_len": "1", "lift": "1.8"},
    ])
    idx = build_transition_lift_index(rules)
    assert idx[("A", "B")] == pytest.approx(1.8)


def test_lift_index_min_lift_filter():
    rules = _make_rules([
        {"prefix_sequence": '["A"]', "next_color": "B", "prefix_len": "1", "lift": "0.5"},
        {"prefix_sequence": '["A"]', "next_color": "C", "prefix_len": "1", "lift": "1.5"},
    ])
    idx = build_transition_lift_index(rules, min_lift=1.0)
    assert ("A", "B") not in idx
    assert ("A", "C") in idx


def test_lift_index_ignores_malformed_rows():
    rules = [{"prefix_sequence": "NOT_JSON", "next_color": "B",
              "prefix_len": "1", "lift": "1.0"}]
    idx = build_transition_lift_index(rules)
    assert len(idx) == 0


# ---------------------------------------------------------------------------
# _pal_vc_lift
# ---------------------------------------------------------------------------

def test_pal_vc_lift_found():
    rules = _make_rules([
        {"prefix_sequence": '["PAL_code"]', "next_color": "verifier_check",
         "prefix_len": "1", "lift": "1.60"},
    ])
    assert _pal_vc_lift(rules) == pytest.approx(1.60)


def test_pal_vc_lift_absent():
    rules = _make_rules([
        {"prefix_sequence": '["equation_setup"]', "next_color": "PAL_code",
         "prefix_len": "1", "lift": "1.56"},
    ])
    assert _pal_vc_lift(rules) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# build_candidate_prefix_path
# ---------------------------------------------------------------------------

def test_prefix_path_single_candidate():
    rows = [{"branch_family": "equation_first_reasoning", "branch_slot": "1",
             "last_operation_family": "subtract"}]
    path = build_candidate_prefix_path(rows, target_slot=1)
    assert path == ["equation_setup"]


def test_prefix_path_stops_at_target_slot():
    rows = [
        {"branch_family": "target_first_reasoning", "branch_slot": "1",
         "last_operation_family": ""},
        {"branch_family": "equation_first_reasoning", "branch_slot": "2",
         "last_operation_family": ""},
        {"branch_family": "backward_from_target_check", "branch_slot": "5",
         "last_operation_family": ""},
    ]
    path = build_candidate_prefix_path(rows, target_slot=2)
    assert path == ["target_extraction", "equation_setup"]
    assert "verifier_check" not in path


def test_prefix_path_deduplicates_same_bf_color():
    rows = [
        {"branch_family": "entity_unit_ledger_reasoning", "branch_slot": "1",
         "last_operation_family": ""},
        {"branch_family": "entity_unit_ledger_reasoning", "branch_slot": "2",
         "last_operation_family": ""},
    ]
    path = build_candidate_prefix_path(rows, target_slot=2)
    assert path.count("target_extraction") == 1


def test_prefix_path_verifier_after_pal():
    rows = [
        {"branch_family": "pal_code_with_required_target_variable", "branch_slot": "3",
         "last_operation_family": ""},
        {"branch_family": "backward_from_target_check", "branch_slot": "5",
         "last_operation_family": ""},
    ]
    # Verifier candidate path includes PAL_code before verifier_check
    path = build_candidate_prefix_path(rows, target_slot=5)
    assert "PAL_code" in path
    assert "verifier_check" in path
    assert path.index("PAL_code") < path.index("verifier_check")


# ---------------------------------------------------------------------------
# score_path
# ---------------------------------------------------------------------------

def test_score_path_empty_sequence():
    assert score_path([], {}) == pytest.approx(0.0)


def test_score_path_single_element():
    assert score_path(["A"], {("A", "B"): 1.5}) == pytest.approx(0.0)


def test_score_path_sums_adjacent_lifts():
    idx = {("A", "B"): 1.5, ("B", "C"): 1.6}
    assert score_path(["A", "B", "C"], idx) == pytest.approx(3.1)


def test_score_path_missing_transition_contributes_zero():
    idx = {("A", "B"): 1.5}
    assert score_path(["A", "B", "C"], idx) == pytest.approx(1.5)


# ---------------------------------------------------------------------------
# process_case — tie-breaking
# ---------------------------------------------------------------------------

def _make_lift_idx(pairs: dict[tuple[str, str], float]) -> dict:
    return pairs


def test_tie_breaking_prefers_higher_score():
    case = _make_case(candidates=[
        {"branch_family": "target_first_reasoning", "branch_slot": "1",
         "last_operation_family": "", "target_alignment_score": "0.9",
         "candidate_answer": "10", "exec_ok": ""},
        {"branch_family": "backward_from_target_check", "branch_slot": "2",
         "last_operation_family": "", "target_alignment_score": "0.8",
         "candidate_answer": "20", "exec_ok": ""},
    ])
    # Give verifier_check transition a high lift
    lift_idx = {("target_extraction", "verifier_check"): 2.0}
    cb = {"baseline_answer": "10", "structural_best_answer": "20", "verifier_answer": "20"}
    result = process_case(case, cb, lift_idx, pal_vc_lift_value=1.6)
    assert result["policy_selected_answer"] == "20"
    assert result["policy_selected_branch_family"] == "backward_from_target_check"


def test_tie_breaking_prefers_higher_target_alignment_score():
    # Both candidates get score=0 (no transition in index)
    case = _make_case(candidates=[
        {"branch_family": "equation_first_reasoning", "branch_slot": "1",
         "last_operation_family": "", "target_alignment_score": "0.7",
         "candidate_answer": "low", "exec_ok": ""},
        {"branch_family": "target_first_reasoning", "branch_slot": "2",
         "last_operation_family": "", "target_alignment_score": "0.95",
         "candidate_answer": "high", "exec_ok": ""},
    ])
    cb = {"baseline_answer": "low", "structural_best_answer": "high", "verifier_answer": ""}
    result = process_case(case, cb, {}, pal_vc_lift_value=0.0)
    assert result["policy_selected_answer"] == "high"


def test_tie_breaking_non_repair_wins():
    case = _make_case(candidates=[
        {"branch_family": "repair_layer_something", "branch_slot": "1",
         "last_operation_family": "", "target_alignment_score": "0.9",
         "candidate_answer": "repair_ans", "exec_ok": ""},
        {"branch_family": "equation_first_reasoning", "branch_slot": "2",
         "last_operation_family": "", "target_alignment_score": "0.9",
         "candidate_answer": "normal_ans", "exec_ok": ""},
    ])
    cb = {"baseline_answer": "other", "structural_best_answer": "", "verifier_answer": ""}
    result = process_case(case, cb, {}, pal_vc_lift_value=0.0)
    assert result["policy_selected_answer"] == "normal_ans"


def test_tie_breaking_stable_order_as_last_resort():
    case = _make_case(candidates=[
        {"branch_family": "equation_first_reasoning", "branch_slot": "1",
         "last_operation_family": "", "target_alignment_score": "0.9",
         "candidate_answer": "first", "exec_ok": ""},
        {"branch_family": "target_first_reasoning", "branch_slot": "2",
         "last_operation_family": "", "target_alignment_score": "0.9",
         "candidate_answer": "second", "exec_ok": ""},
    ])
    cb = {"baseline_answer": "x", "structural_best_answer": "", "verifier_answer": ""}
    result = process_case(case, cb, {}, pal_vc_lift_value=0.0)
    assert result["policy_selected_answer"] == "first"


# ---------------------------------------------------------------------------
# process_case — outcome labels
# ---------------------------------------------------------------------------

def test_outcome_no_change_when_policy_matches_baseline():
    case = _make_case(candidates=[
        {"branch_family": "equation_first_reasoning", "branch_slot": "1",
         "last_operation_family": "", "target_alignment_score": "0.9",
         "candidate_answer": "42", "exec_ok": ""},
    ])
    cb = {"baseline_answer": "42", "structural_best_answer": "99", "verifier_answer": ""}
    result = process_case(case, cb, {}, pal_vc_lift_value=0.0)
    assert result["no_change"] is True
    assert result["policy_improves_proxy"] is False
    assert result["policy_regresses_proxy"] is False


def test_outcome_improves_when_policy_matches_structural():
    case = _make_case(candidates=[
        {"branch_family": "equation_first_reasoning", "branch_slot": "1",
         "last_operation_family": "", "target_alignment_score": "0.5",
         "candidate_answer": "base", "exec_ok": ""},
        {"branch_family": "backward_from_target_check", "branch_slot": "2",
         "last_operation_family": "", "target_alignment_score": "0.95",
         "candidate_answer": "better", "exec_ok": ""},
    ])
    lift_idx = {("equation_setup", "verifier_check"): 1.6}
    cb = {"baseline_answer": "base", "structural_best_answer": "better", "verifier_answer": "better"}
    result = process_case(case, cb, lift_idx, pal_vc_lift_value=0.0)
    assert result["policy_improves_proxy"] is True
    assert result["policy_regresses_proxy"] is False
    assert result["no_change"] is False


def test_outcome_regresses_when_policy_diverges_from_both():
    case = _make_case(candidates=[
        {"branch_family": "equation_first_reasoning", "branch_slot": "1",
         "last_operation_family": "", "target_alignment_score": "0.9",
         "candidate_answer": "wrong_policy", "exec_ok": ""},
    ])
    cb = {"baseline_answer": "baseline_val", "structural_best_answer": "structural_val",
          "verifier_answer": ""}
    result = process_case(case, cb, {}, pal_vc_lift_value=0.0)
    assert result["policy_regresses_proxy"] is True


def test_outcome_agrees_with_structural():
    case = _make_case(candidates=[
        {"branch_family": "equation_first_reasoning", "branch_slot": "1",
         "last_operation_family": "", "target_alignment_score": "0.9",
         "candidate_answer": "struct_ans", "exec_ok": ""},
    ])
    cb = {"baseline_answer": "other", "structural_best_answer": "struct_ans", "verifier_answer": ""}
    result = process_case(case, cb, {}, pal_vc_lift_value=0.0)
    assert result["policy_agrees_with_structural"] is True


# ---------------------------------------------------------------------------
# process_case — metadata_insufficient
# ---------------------------------------------------------------------------

def test_metadata_insufficient_when_no_candidates():
    case = _make_case(candidates=[])
    cb = {"baseline_answer": "1", "structural_best_answer": "1", "verifier_answer": ""}
    result = process_case(case, cb, {}, pal_vc_lift_value=0.0)
    assert result["metadata_insufficient"] is True


def test_metadata_insufficient_when_no_candidate_answer():
    case = _make_case(candidates=[
        {"branch_family": "equation_first_reasoning", "branch_slot": "1",
         "last_operation_family": "", "target_alignment_score": "0.9",
         "candidate_answer": "", "exec_ok": ""},
    ])
    cb = {"baseline_answer": "1", "structural_best_answer": "1", "verifier_answer": ""}
    result = process_case(case, cb, {}, pal_vc_lift_value=0.0)
    assert result["metadata_insufficient"] is True


# ---------------------------------------------------------------------------
# process_case — missing verifier flag
# ---------------------------------------------------------------------------

def test_requires_live_vc_when_pal_no_verifier():
    case = _make_case(pal_exec_ok="1", candidates=[
        {"branch_family": "pal_code_with_required_target_variable", "branch_slot": "1",
         "last_operation_family": "", "target_alignment_score": "0.8",
         "candidate_answer": "5", "exec_ok": ""},
    ])
    cb = {"baseline_answer": "5", "structural_best_answer": "", "verifier_answer": ""}
    result = process_case(case, cb, {}, pal_vc_lift_value=1.6)
    assert result["requires_live_verifier_branch_allocation"] is True


def test_no_live_vc_when_verifier_already_present():
    case = _make_case(pal_exec_ok="1", candidates=[
        {"branch_family": "pal_code_with_required_target_variable", "branch_slot": "1",
         "last_operation_family": "", "target_alignment_score": "0.8",
         "candidate_answer": "5", "exec_ok": ""},
        {"branch_family": "backward_from_target_check", "branch_slot": "2",
         "last_operation_family": "", "target_alignment_score": "0.95",
         "candidate_answer": "7", "exec_ok": ""},
    ])
    cb = {"baseline_answer": "5", "structural_best_answer": "7", "verifier_answer": "7"}
    result = process_case(case, cb, {("PAL_code", "verifier_check"): 1.6}, pal_vc_lift_value=1.6)
    assert result["requires_live_verifier_branch_allocation"] is False


def test_no_live_vc_when_pal_vc_lift_below_threshold():
    case = _make_case(pal_exec_ok="1", candidates=[
        {"branch_family": "pal_code_with_required_target_variable", "branch_slot": "1",
         "last_operation_family": "", "target_alignment_score": "0.8",
         "candidate_answer": "5", "exec_ok": ""},
    ])
    cb = {"baseline_answer": "5", "structural_best_answer": "", "verifier_answer": ""}
    result = process_case(case, cb, {}, pal_vc_lift_value=0.9)  # lift < 1.0
    assert result["requires_live_verifier_branch_allocation"] is False


# ---------------------------------------------------------------------------
# Gold scoring (used only after selection, not in policy)
# ---------------------------------------------------------------------------

def test_gold_not_used_in_policy_selection(tmp_path: Path):
    # Gold says answer "gold_ans" is correct, but it's not in candidates.
    # Policy should still select based on scores, not gold.
    packets = tmp_path / "packets.jsonl"
    _write_packets(packets, [
        _make_case("c1", candidates=[
            {"branch_family": "equation_first_reasoning", "branch_slot": "1",
             "last_operation_family": "", "target_alignment_score": "0.9",
             "candidate_answer": "42", "exec_ok": ""},
        ])
    ])
    rules_path = tmp_path / "rules.csv"
    _write_rules(rules_path, [
        {"prefix_sequence": '["equation_setup"]', "next_color": "selector",
         "prefix_len": "1", "lift": "1.0", "support": "3", "correct_count": "2",
         "success_rate": "0.67", "example_case_indices": "[]", "example_case_ids": "[]"},
    ])
    cb_path = tmp_path / "casebook.csv"
    _write_casebook(cb_path, [
        {"case_id": "c1", "baseline_answer": "10", "structural_best_answer": "10",
         "verifier_answer": "10", "proxy_score_improved": "False",
         "proxy_alignment_improved": "False", "gold_answer": "gold_ans"},
    ])
    out = tmp_path / "out"
    result = main([
        "--trace-packets", str(packets),
        "--transition-rules", str(rules_path),
        "--replay-casebook", str(cb_path),
        "--out-dir", str(out),
    ])
    # The selected answer should be "42" from the candidate (not "gold_ans")
    rows = list(csv.DictReader(open(out / "case_policy_rows.csv")))
    assert rows[0]["policy_selected_answer"] == "42"


# ---------------------------------------------------------------------------
# CLI / end-to-end: expected output files
# ---------------------------------------------------------------------------

def _make_full_fixture(tmp_path: Path):
    """Write minimal complete fixture and return (packets, rules, motifs, casebook, out)."""
    cases = [
        _make_case("c1", pal_exec_ok="1", candidates=[
            {"branch_family": "pal_code_with_required_target_variable", "branch_slot": "3",
             "last_operation_family": "", "target_alignment_score": "0.8",
             "candidate_answer": "5", "exec_ok": ""},
            {"branch_family": "backward_from_target_check", "branch_slot": "5",
             "last_operation_family": "", "target_alignment_score": "0.95",
             "candidate_answer": "7", "exec_ok": ""},
        ]),
        _make_case("c2", pal_exec_ok="0", candidates=[
            {"branch_family": "equation_first_reasoning", "branch_slot": "1",
             "last_operation_family": "", "target_alignment_score": "0.7",
             "candidate_answer": "10", "exec_ok": ""},
        ]),
    ]
    packets = tmp_path / "packets.jsonl"
    _write_packets(packets, cases)

    rules = _make_rules([
        {"prefix_sequence": '["PAL_code"]', "next_color": "verifier_check",
         "prefix_len": "1", "lift": "1.60", "support": "5",
         "correct_count": "4", "success_rate": "0.80",
         "example_case_indices": "[]", "example_case_ids": "[]"},
        {"prefix_sequence": '["equation_setup"]', "next_color": "PAL_code",
         "prefix_len": "1", "lift": "1.56", "support": "4",
         "correct_count": "3", "success_rate": "0.75",
         "example_case_indices": "[]", "example_case_ids": "[]"},
    ])
    rules_path = tmp_path / "rules.csv"
    _write_rules(rules_path, rules)

    motifs_path = tmp_path / "motifs.csv"
    motifs_path.write_text(
        "sequence,length,support_count,correct_count,wrong_count,unknown_count,"
        "precision,lift,baseline_correct_rate\n"
        '["PAL_code"],1,10,8,2,0,0.80,1.60,0.50\n',
        encoding="utf-8",
    )

    cb_path = tmp_path / "casebook.csv"
    _write_casebook(cb_path, [
        {"case_id": "c1", "baseline_answer": "5", "structural_best_answer": "7",
         "verifier_answer": "7", "proxy_score_improved": "True",
         "proxy_alignment_improved": "True"},
        {"case_id": "c2", "baseline_answer": "10", "structural_best_answer": "10",
         "verifier_answer": "", "proxy_score_improved": "False",
         "proxy_alignment_improved": "False"},
    ])
    out = tmp_path / "out"
    return packets, rules_path, motifs_path, cb_path, out


def test_cli_writes_all_expected_files(tmp_path: Path):
    packets, rules, motifs, cb, out = _make_full_fixture(tmp_path)
    result = main([
        "--trace-packets", str(packets),
        "--transition-rules", str(rules),
        "--motif-summary", str(motifs),
        "--replay-casebook", str(cb),
        "--out-dir", str(out),
    ])
    assert result["api_calls_made"] == 0
    for fname in [
        "manifest.json", "case_policy_rows.csv", "case_policy_rows.jsonl",
        "policy_summary.json", "policy_summary.csv",
        "missing_verifier_branch_cases.csv", "report.md",
    ]:
        assert (out / fname).is_file(), f"Missing: {fname}"


def test_cli_zero_api_calls(tmp_path: Path):
    packets, rules, motifs, cb, out = _make_full_fixture(tmp_path)
    result = main([
        "--trace-packets", str(packets),
        "--transition-rules", str(rules),
        "--replay-casebook", str(cb),
        "--out-dir", str(out),
    ])
    assert result["api_calls_made"] == 0
    manifest = json.loads((out / "manifest.json").read_text())
    assert manifest["api_calls_made"] == 0


def test_cli_no_gold_features_flag(tmp_path: Path):
    packets, rules, motifs, cb, out = _make_full_fixture(tmp_path)
    result = main([
        "--trace-packets", str(packets),
        "--transition-rules", str(rules),
        "--replay-casebook", str(cb),
        "--out-dir", str(out),
    ])
    assert result["no_gold_features"] is True


def test_cli_case_policy_rows_has_required_columns(tmp_path: Path):
    packets, rules, motifs, cb, out = _make_full_fixture(tmp_path)
    main([
        "--trace-packets", str(packets),
        "--transition-rules", str(rules),
        "--replay-casebook", str(cb),
        "--out-dir", str(out),
    ])
    rows = list(csv.DictReader(open(out / "case_policy_rows.csv")))
    assert len(rows) == 2
    required = {
        "case_id", "baseline_answer", "structural_best_answer", "verifier_answer",
        "policy_selected_answer", "policy_selected_branch_family",
        "policy_selected_color_sequence", "policy_score", "target_alignment_score",
        "policy_agrees_with_structural", "policy_improves_proxy",
        "policy_regresses_proxy", "no_change", "metadata_insufficient",
        "requires_live_verifier_branch_allocation",
    }
    assert required.issubset(set(rows[0].keys()))


def test_cli_case_policy_rows_jsonl_matches_csv(tmp_path: Path):
    packets, rules, motifs, cb, out = _make_full_fixture(tmp_path)
    main([
        "--trace-packets", str(packets),
        "--transition-rules", str(rules),
        "--replay-casebook", str(cb),
        "--out-dir", str(out),
    ])
    csv_rows = list(csv.DictReader(open(out / "case_policy_rows.csv")))
    jsonl_rows = [
        json.loads(line) for line in
        (out / "case_policy_rows.jsonl").read_text().splitlines()
        if line.strip()
    ]
    assert len(csv_rows) == len(jsonl_rows)
    assert {r["case_id"] for r in csv_rows} == {r["case_id"] for r in jsonl_rows}


def test_cli_missing_verifier_cases_csv(tmp_path: Path):
    packets, rules, motifs, cb, out = _make_full_fixture(tmp_path)
    main([
        "--trace-packets", str(packets),
        "--transition-rules", str(rules),
        "--replay-casebook", str(cb),
        "--out-dir", str(out),
    ])
    # c1 has both PAL_code + verifier_check → NOT missing
    # c2 has no PAL, no verifier → has_pal=False → NOT flagged
    mv_rows = list(csv.DictReader(open(out / "missing_verifier_branch_cases.csv")))
    case_ids = {r["case_id"] for r in mv_rows}
    assert "c1" not in case_ids  # has verifier already


def test_cli_policy_selects_verifier_candidate_over_pal(tmp_path: Path):
    """Verifier_check candidate should win over PAL_code because PAL→VC lift is high."""
    packets, rules, motifs, cb, out = _make_full_fixture(tmp_path)
    main([
        "--trace-packets", str(packets),
        "--transition-rules", str(rules),
        "--replay-casebook", str(cb),
        "--out-dir", str(out),
    ])
    rows = {r["case_id"]: r for r in
            csv.DictReader(open(out / "case_policy_rows.csv"))}
    # c1 should select backward_from_target_check (answer "7"), not PAL_code (answer "5")
    assert rows["c1"]["policy_selected_answer"] == "7"
    assert "verifier_check" in rows["c1"]["policy_selected_color_sequence"]


def test_cli_with_limit(tmp_path: Path):
    packets, rules, motifs, cb, out = _make_full_fixture(tmp_path)
    result = main([
        "--trace-packets", str(packets),
        "--transition-rules", str(rules),
        "--replay-casebook", str(cb),
        "--out-dir", str(out),
        "--limit", "1",
    ])
    assert result["cases_loaded"] == 1


def test_cli_report_md_written(tmp_path: Path):
    packets, rules, motifs, cb, out = _make_full_fixture(tmp_path)
    main([
        "--trace-packets", str(packets),
        "--transition-rules", str(rules),
        "--replay-casebook", str(cb),
        "--out-dir", str(out),
    ])
    report = (out / "report.md").read_text()
    assert "colored_reasoning_path_policy_v1" in report
    assert "Cases loaded" in report
    assert "verifier" in report.lower()
