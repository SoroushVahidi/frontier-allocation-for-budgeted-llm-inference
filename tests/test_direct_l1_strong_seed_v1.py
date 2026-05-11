from __future__ import annotations

import random
from pathlib import Path

from experiments.frontier_matrix_core import build_frontier_strategies
from scripts import run_cohere_real_model_cost_normalized_validation as runner


METHOD = (
    "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_direct_l1_strong_seed_v1"
)
BASELINE_DIRECT_HYBRID = "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_direct_hybrid"

EXACT_CASES_15 = Path(
    "docs/project_handoff_20260510/exact_case_replay/direct_l1_strong_seed_15case_exact_cases_20260511.jsonl"
)


def test_direct_l1_strong_seed_method_is_registered_and_runnable_without_api() -> None:
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
    runtime = runner.METHODS[METHOD]["runtime"]
    assert runtime in specs


def test_direct_l1_strong_seed_exact_case_slice_15count_is_preserved() -> None:
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


def test_direct_l1_strong_seed_uses_opt_in_prompt_style() -> None:
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
    ctrl = specs[runner.METHODS[METHOD]["runtime"]]
    assert bool(getattr(ctrl, "enable_direct_hybrid_seed", False)) is True
    assert str(getattr(ctrl, "direct_hybrid_seed_source", "")) == "direct_l1_strong_seed_v1"
    prompt_style = str(getattr(ctrl, "direct_hybrid_l1_prompt_style", "") or "")
    assert "Independently self-check" in prompt_style
    assert "Output only the final numeric answer in \\boxed{}." in prompt_style


def test_baseline_direct_hybrid_seed_source_is_unchanged() -> None:
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
    ctrl = specs[runner.METHODS[BASELINE_DIRECT_HYBRID]["runtime"]]
    assert bool(getattr(ctrl, "enable_direct_hybrid_seed", False)) is True
    assert str(getattr(ctrl, "direct_hybrid_seed_source", "")) == "l1_style_max_budget_prompt"
