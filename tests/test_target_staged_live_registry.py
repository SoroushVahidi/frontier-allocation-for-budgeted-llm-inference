from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import pytest

from experiments.frontier_matrix_core import build_frontier_strategies
from scripts import prepare_target_staged_pal_frontier_v1_preflight as preflight
from scripts import run_cohere_real_model_cost_normalized_validation as runner


TARGET_METHOD = "target_staged_pal_frontier_v1"
TARGET_ALIAS = "ts_pal_frontier_v1"
TARGET_RUNTIME = (
    "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal_structural_commit_v1_targeted_retry_v1"
)
EXACT_CASES_15 = Path(
    "docs/project_handoff_20260510/exact_case_replay/direct_l1_strong_seed_15case_exact_cases_20260511.jsonl"
)


def _runner_specs() -> dict[str, object]:
    return build_frontier_strategies(
        lambda: None,
        6,
        [1],
        random.Random(11),
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
        include_external_l1_baseline=True,
        include_external_s1_baseline=True,
        include_external_tale_baseline=True,
    )


def test_target_staged_registry_aliases_resolve_to_runnable_runtime() -> None:
    specs = _runner_specs()
    assert runner.METHODS[TARGET_METHOD]["runtime"] == TARGET_RUNTIME
    assert runner.METHODS[TARGET_ALIAS]["runtime"] == TARGET_RUNTIME
    assert TARGET_RUNTIME in specs


def test_target_staged_exact_case_rows_load_without_mutation() -> None:
    rows = runner.load_exact_case_rows(str(EXACT_CASES_15))
    assert len(rows) == 15
    assert len({r["example_id"] for r in rows}) == 15
    assert [r["example_id"] for r in rows] == [
        "openai_gsm8k_168",
        "openai_gsm8k_180",
        "openai_gsm8k_190",
        "openai_gsm8k_197",
        "openai_gsm8k_213",
        "openai_gsm8k_264",
        "openai_gsm8k_347",
        "openai_gsm8k_367",
        "openai_gsm8k_376",
        "openai_gsm8k_391",
        "openai_gsm8k_297",
        "openai_gsm8k_204",
        "openai_gsm8k_228",
        "openai_gsm8k_233",
        "openai_gsm8k_354",
    ]


def test_target_staged_prompt_bundle_renders_and_stays_gold_free() -> None:
    question = "A tank has 4 liters of water and gains 3 more liters. How much water is there now?"
    schema = preflight.build_target_schema(question, case_id="synthetic_case", slice_name="guardrail")
    forbidden_tokens = ("gold", "gold_answer", "answer_key", "hidden labels")
    for template_id in preflight.PROMPT_TEMPLATE_IDS:
        prompt = preflight.render_prompt(template_id, question=question, target_schema=schema)
        assert "{{" not in prompt
        assert "}}" not in prompt
        lower = prompt.lower()
        for token in forbidden_tokens:
            assert token not in lower


def test_target_staged_validate_only_skips_api_client_construction(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_args, **_kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("API client construction should not happen in validate-only mode")

    monkeypatch.setattr("experiments.branching.APIBranchGenerator.__init__", boom, raising=False)

    args = argparse.Namespace(
        timestamp="TEST_TARGET_STAGED_VALIDATE_ONLY",
        output_root=str(tmp_path),
        exact_cases_jsonl=str(EXACT_CASES_15),
        expected_exact_case_count=15,
    )
    with pytest.raises(SystemExit) as excinfo:
        runner.validate_exact_cases_only(
            args=args,
            providers=["cohere"],
            datasets=["openai/gsm8k"],
            budgets=[6],
            methods=[TARGET_METHOD, TARGET_ALIAS],
        )
    assert excinfo.value.code == 0

    report_path = tmp_path / "cohere_real_model_cost_normalized_validation_TEST_TARGET_STAGED_VALIDATE_ONLY" / "exact_case_validation_report.json"
    assert report_path.is_file()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["case_count"] == 15
    assert report["mismatch_count"] == 0
    assert report["api_calls_made"] == 0
    method_rows = {row["method_id"]: row for row in report["methods"]}
    assert method_rows[TARGET_METHOD]["runnable_without_api"] is True
    assert method_rows[TARGET_ALIAS]["runnable_without_api"] is True
