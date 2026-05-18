"""Tests for scripts/repair_promotion_review_markers.py."""
from __future__ import annotations

import json
import pathlib
import tempfile

import pytest

from scripts.failure_case_logging_schema import (
    EXPLICIT_NOT_SCORED_YET_MARKER,
    EXPLICIT_UNAVAILABLE_NOT_RECORDED_MARKER,
    validate_promotion_review_record,
)
from scripts.repair_promotion_review_markers import _needs_repair, repair_jsonl, repair_record


def _make_partial_row(*, node_expansion_order=None) -> dict:
    """Build a minimal promotion-review row that is partial due to missing node_expansion_order."""
    prr = {
        "run_id": "run_1",
        "artifact_label": "art",
        "example_id": "openai_gsm8k_190",
        "problem_id": "openai_gsm8k_190",
        "dataset": "openai/gsm8k",
        "provider": "cohere",
        "model": "command-r-plus-08-2024",
        "method": "external_l1_max",
        "budget": 6,
        "seed": 11,
        "question": "How many?",
        "prompt_hash": "question_sha256:abc",
        "candidate_answer": "7",
        "candidate_trace": "The answer is 7",
        "parse_success": 1,
        "parser_status": "ok",
        "parser_error": "",
        "status": "scored",
        "runtime_cap_reached": False,
        "error_type": "",
        "error_message": "",
        "discovery_tree": [{"node_id": "n0"}],
        "node_expansion_order": node_expansion_order,
        "prune_or_selection_reasons": EXPLICIT_UNAVAILABLE_NOT_RECORDED_MARKER,
        "candidate_pool_summary": {"size": 1},
        "call_count": 1,
        "total_tokens": 120,
        "latency_seconds": 0.5,
        "verifier_scores": {},
        "verifier_scores_pointer": EXPLICIT_NOT_SCORED_YET_MARKER,
        "raw_proba_ready": EXPLICIT_NOT_SCORED_YET_MARKER,
        "gate_decision": "scored",
        "policy_family": "conservative_combo",
        "offline_eval_only": True,
    }
    validation = validate_promotion_review_record(prr)
    return {
        "example_id": "openai_gsm8k_190",
        "promotion_review_record": prr,
        "promotion_review_validation": validation,
    }


def test_needs_repair_empty_list() -> None:
    assert _needs_repair([]) is True


def test_needs_repair_none() -> None:
    assert _needs_repair(None) is True


def test_needs_repair_explicit_marker_false() -> None:
    assert _needs_repair(EXPLICIT_UNAVAILABLE_NOT_RECORDED_MARKER) is False


def test_needs_repair_nonempty_list_false() -> None:
    assert _needs_repair(["b0", "b1"]) is False


def test_repair_record_partial_becomes_yes() -> None:
    row = _make_partial_row(node_expansion_order=[])
    assert row["promotion_review_validation"]["enough_for_promotion_review"] in {"partial", "no"}

    repaired_row, changed = repair_record(row)
    assert changed is True
    prr = repaired_row["promotion_review_record"]
    assert prr["node_expansion_order"] == EXPLICIT_UNAVAILABLE_NOT_RECORDED_MARKER
    pv = repaired_row["promotion_review_validation"]
    assert pv["enough_for_promotion_review"] == "yes"
    assert "node_expansion_order_or_unavailable" not in pv["missing_required_fields"]


def test_repair_record_already_yes_unchanged() -> None:
    row = _make_partial_row(node_expansion_order=EXPLICIT_UNAVAILABLE_NOT_RECORDED_MARKER)
    # should already be yes
    _, changed = repair_record(row)
    assert changed is False


def test_repair_record_nonempty_expansion_unchanged() -> None:
    row = _make_partial_row(node_expansion_order=["b0", "b1"])
    _, changed = repair_record(row)
    assert changed is False


def test_repair_jsonl_converts_partial_to_yes(tmp_path: pathlib.Path) -> None:
    partial_row = _make_partial_row(node_expansion_order=[])
    yes_row = _make_partial_row(node_expansion_order=EXPLICIT_UNAVAILABLE_NOT_RECORDED_MARKER)

    input_file = tmp_path / "input.jsonl"
    output_file = tmp_path / "output.jsonl"

    input_file.write_text(
        json.dumps(partial_row) + "\n" + json.dumps(yes_row) + "\n",
        encoding="utf-8",
    )

    metrics = repair_jsonl(input_file, output_file)

    assert metrics["total_rows"] == 2
    assert metrics["rows_repaired"] == 1
    assert metrics["before"]["partial"] >= 1
    assert metrics["after"]["yes"] == 2
    assert metrics["after"]["partial"] == 0
    assert metrics["yes_rate_after"] == 1.0

    output_rows = [json.loads(l) for l in output_file.read_text(encoding="utf-8").splitlines() if l.strip()]
    for r in output_rows:
        prr = r["promotion_review_record"]
        assert prr["node_expansion_order"] == EXPLICIT_UNAVAILABLE_NOT_RECORDED_MARKER
        pv = r["promotion_review_validation"]
        assert pv["enough_for_promotion_review"] == "yes"


def test_repair_jsonl_refuses_same_path(tmp_path: pathlib.Path) -> None:
    f = tmp_path / "file.jsonl"
    f.write_text("{}\n", encoding="utf-8")
    with pytest.raises((ValueError, SystemExit)):
        repair_jsonl(f, f)


def test_repair_utility_no_provider_imports() -> None:
    import pathlib as _pl

    src = (_pl.Path(__file__).resolve().parents[1] / "scripts" / "repair_promotion_review_markers.py").read_text()
    assert "import cohere" not in src
    assert "from cohere" not in src
    assert "import openai" not in src
    assert "from openai" not in src
