from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

from experiments.frontier_matrix_core import build_frontier_strategies
from scripts import run_cohere_real_model_cost_normalized_validation as runner

OLD_METHOD = "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_direct_hybrid"
NEW_METHOD = "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_diverse_anchor"
STABILITY_METHOD = "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_stability_redundant_anchor_v1"
UNCERTAINTY_METHOD = "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_uncertainty_retry_v1"


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def test_exact_case_jsonl_loads_deterministically(tmp_path: Path) -> None:
    p = tmp_path / "exact_cases.jsonl"
    rows = [
        {"example_id": "case_2", "question": "What is 2 + 2?", "gold_answer_canonical": "4", "failure_domain": "unit"},
        {"example_id": "case_1", "question": "What is 3 + 5?", "gold_answer": "#### 8", "failure_domain": "unit"},
    ]
    _write_jsonl(p, rows)

    first = runner.load_exact_case_rows(str(p))
    second = runner.load_exact_case_rows(str(p))

    assert [r["example_id"] for r in first] == ["case_2", "case_1"]
    assert first == second
    assert [ex.example_id for ex in runner.exact_case_rows_to_examples(first)] == ["case_2", "case_1"]
    assert [ex.answer for ex in runner.exact_case_rows_to_examples(first)] == ["4", "8"]


def test_exact_case_validation_detects_question_and_gold_mismatch(tmp_path: Path) -> None:
    p = tmp_path / "exact_cases.jsonl"
    _write_jsonl(p, [{"example_id": "case_1", "question": "What is 2 + 2?", "gold_answer_canonical": "4"}])
    rows = runner.load_exact_case_rows(str(p))

    bad_examples = [runner.PilotExample(example_id="case_1", question="What is 2 + 3?", answer="5")]
    mismatches = runner.validate_exact_case_examples(rows, bad_examples)

    assert {m["type"] for m in mismatches} == {"question_mismatch", "gold_mismatch"}


def test_valid_exact_cases_pass_validation(tmp_path: Path) -> None:
    p = tmp_path / "exact_cases.jsonl"
    _write_jsonl(p, [{"example_id": "case_1", "question": "What is 2 + 2?", "gold_answer_canonical": "4"}])
    rows = runner.load_exact_case_rows(str(p))
    examples = runner.exact_case_rows_to_examples(rows)

    assert runner.validate_exact_case_examples(rows, examples) == []


def test_selected_failure_recovery_exact_case_count_is_preserved() -> None:
    path = Path("docs/project_handoff_20260510/exact_case_replay/failure_recovery_30case_exact_cases_20260510.jsonl")
    rows = runner.load_exact_case_rows(str(path))

    assert len(rows) == 30
    assert len({r["example_id"] for r in rows}) == 30
    assert rows[0]["example_id"] == "openai_gsm8k_337"


def test_selected_failure_recovery_exact_case_50count_is_preserved_and_appended() -> None:
    path_30 = Path("docs/project_handoff_20260510/exact_case_replay/failure_recovery_30case_exact_cases_20260510.jsonl")
    path_50 = Path("docs/project_handoff_20260510/exact_case_replay/failure_recovery_50case_exact_cases_20260510.jsonl")
    rows_30 = runner.load_exact_case_rows(str(path_30))
    rows_50 = runner.load_exact_case_rows(str(path_50))

    assert len(rows_50) == 50
    assert len({r["example_id"] for r in rows_50}) == 50
    assert [r["example_id"] for r in rows_50[:30]] == [r["example_id"] for r in rows_30]
    for row in rows_50:
        assert str(row.get("question") or "").strip()
        assert str(row.get("gold_answer_canonical") or "").strip()
        assert str(row.get("failure_domain") or "").strip()


def test_exact_case_mode_does_not_use_shuffled_loader(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    p = tmp_path / "exact_cases.jsonl"
    _write_jsonl(p, [{"example_id": "case_1", "question": "What is 2 + 2?", "gold_answer_canonical": "4"}])
    rows = runner.load_exact_case_rows(str(p))

    def forbidden_loader(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("shuffled loader should not be called in exact-case mode")

    monkeypatch.setattr(runner, "load_pilot_examples", forbidden_loader)
    examples = runner.resolve_examples_for_dataset("openai/gsm8k", subset_size=999, seed=123, exact_case_rows=rows)

    assert [(ex.example_id, ex.question, ex.answer) for ex in examples] == [("case_1", "What is 2 + 2?", "4")]


def test_direct_hybrid_and_diverse_anchor_methods_resolve_without_api() -> None:
    specs = build_frontier_strategies(
        lambda: None,
        4,
        [1],
        random.Random(11),
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
        include_external_l1_baseline=True,
        include_external_s1_baseline=True,
        include_external_tale_baseline=True,
    )

    assert runner.METHODS[OLD_METHOD]["runtime"] in specs
    assert runner.METHODS[NEW_METHOD]["runtime"] in specs


def test_runner_registry_resolves_stability_redundant_anchor_without_api() -> None:
    specs = build_frontier_strategies(
        lambda: None,
        4,
        [1],
        random.Random(11),
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
        include_external_l1_baseline=True,
        include_external_s1_baseline=True,
        include_external_tale_baseline=True,
    )

    assert runner.METHODS[NEW_METHOD]["runtime"] in specs
    assert runner.METHODS[STABILITY_METHOD]["runtime"] in specs
    assert runner.METHODS[STABILITY_METHOD]["enable_output_repair"] is True


def test_runner_registry_resolves_uncertainty_retry_without_api() -> None:
    specs = build_frontier_strategies(
        lambda: None,
        4,
        [1],
        random.Random(11),
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
        include_external_l1_baseline=True,
        include_external_s1_baseline=True,
        include_external_tale_baseline=True,
    )

    assert runner.METHODS[NEW_METHOD]["runtime"] in specs
    assert runner.METHODS[UNCERTAINTY_METHOD]["runtime"] in specs
    assert runner.METHODS[UNCERTAINTY_METHOD]["enable_output_repair"] is True
