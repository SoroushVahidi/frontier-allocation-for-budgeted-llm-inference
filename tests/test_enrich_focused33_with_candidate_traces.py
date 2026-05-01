from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import enrich_focused33_with_candidate_traces as e


def test_filter_focused_row_count_fixture() -> None:
    rows = [
        {"trace_available": "1", "gold_present_in_candidate_groups": "1", "oracle_selector_would_fix": "1"},
        {"trace_available": "0", "gold_present_in_candidate_groups": "1", "oracle_selector_would_fix": "1"},
    ]
    assert len(e.filter_focused_loss_rows(rows)) == 1


def test_normalize_source_path_mmfs_to_repo(tmp_path: Path) -> None:
    (tmp_path / "outputs/trace_only_x").mkdir(parents=True)
    rp = tmp_path
    txt = "/mmfs1/home/sv96/adaptive-reasoning-budget-allocation/outputs/trace_only_x"
    p = e.normalize_source_path(rp, txt)
    assert p.resolve() == (rp / "outputs/trace_only_x").resolve()


def test_normalize_relative_under_repo(tmp_path: Path) -> None:
    (tmp_path / "outputs/sub").mkdir(parents=True)
    p = e.normalize_source_path(tmp_path, "outputs/sub")
    assert p.resolve() == (tmp_path / "outputs/sub").resolve()


def test_per_example_matching(tmp_path: Path) -> None:
    pe = tmp_path / "per_example_records.jsonl"
    rec_ok = {
        "dataset": "openai/gsm8k",
        "example_id": "e99",
        "seed": 11,
        "budget": 4,
        "method": "strict_f3",
        "result_metadata": {"final_branch_states": []},
    }
    rec_wrong_budget = dict(rec_ok) | {"budget": 99}
    pe.write_text(json.dumps(rec_wrong_budget) + "\n" + json.dumps(rec_ok) + "\n", encoding="utf-8")
    got, tag = e.load_per_example_match(
        pe, dataset="openai/gsm8k", example_id="e99", seed=11, budget=4, method="strict_f3"
    )
    assert tag == "exact"
    assert got is not None
    assert got["example_id"] == "e99"


def test_final_branch_states_matching(tmp_path: Path) -> None:
    fbs = tmp_path / "final_branch_states.jsonl"
    line_ok = {"example_id": "e22", "seed": 53, "budget": 4, "method": "strict_f3", "final_branch_states": []}
    line_bad = dict(line_ok) | {"budget": 1}
    fbs.write_text(json.dumps(line_bad) + "\n" + json.dumps(line_ok) + "\n", encoding="utf-8")
    got, tag = e.load_final_branch_states_match(fbs, example_id="e22", seed=53, budget=4, method="strict_f3")
    assert got is not None and tag == "exact"


def test_build_candidate_nodes_prefers_selector_pool() -> None:
    raw_record = {
        "result_metadata": {
            "selector_candidate_pool": [
                {
                    "branch_id": "b1",
                    "predicted_answer": "42",
                    "score": 0.8,
                    "branch_depth": 1,
                    "trace": "Think step.",
                },
                {
                    "branch_id": "b2",
                    "final_answer": "42",
                    "score": 0.7,
                    "branch_depth": 1,
                    "steps": [],
                },
            ]
        }
    }
    nodes, raw_ct, pk = e.build_candidate_nodes(
        raw_record=raw_record, mode="per_example", question="Q?", current_answer="41"
    )
    assert pk == "selector_candidate_pool"
    assert raw_ct >= 1
    assert any(n["trace_available"] for n in nodes)


def test_build_fallback_final_branch_states() -> None:
    raw_record = {"final_branch_states": [{"branch_id": "root", "predicted_answer": "9", "trace_events": []}]}
    nodes, _, _ = e.build_candidate_nodes(raw_record=raw_record, mode="subset", question="Q?", current_answer="10")
    assert nodes and nodes[0]["final_answer"] == "9"


def test_verifier_input_excludes_gold_and_evaluation_hints(tmp_path: Path) -> None:
    nodes = [
        {
            "candidate_id": "a",
            "source_family": "sf",
            "final_answer": "1",
            "normalized_answer": "1",
            "trace_text": "t",
            "trace_available": True,
            "score": 0.5,
            "branch_depth": 1,
            "is_original_selected": 1,
            "hint_for_verifier_only": "gold hidden",
        }
    ]
    safe = e.verifier_safe_candidates(nodes)
    assert all("hint_for_verifier_only" not in x for x in safe)
    assert all("gold" not in json.dumps(x) for x in safe)


def test_canonical_aggregate_has_gold() -> None:
    row = {"dataset": "openai/gsm8k", "gold_answer": "106", "all_candidate_answer_groups": json.dumps(["$106", "99"])}
    s = e.canonical_group_set(e.casebook_candidate_strings(row), "openai/gsm8k")
    g = e.canon_for_dataset("106", "openai/gsm8k")
    assert g in s


def test_extract_trace_events_reasoning_concat() -> None:
    branch = {
        "trace_events": [
            {"reasoning_text": "first"},
            {"response_text": "second"},
            {"text": "third"},
        ]
    }
    txt = e._extract_trace(branch)
    assert "first" in txt and "second" in txt


def test_graceful_missing_source_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    row = {
        "dataset": "openai/gsm8k",
        "example_id": "x",
        "seed": "1",
        "budget": "2",
        "our_method_name": "strict_f3",
        "source_artifact": str(tmp_path / "nonexistent_upstream"),
        "problem_statement": "p",
        "our_final_answer": "0",
        "selected_answer_group": "0",
        "gold_answer": "1",
        "candidate_count": "0",
        "case_id": "c",
        "all_candidate_answer_groups": "[]",
    }
    enriched = e.enriched_record_for_casebook_row(tmp_path, row)
    assert enriched["raw_record_found"] is False
    assert enriched["candidate_nodes"] == []
