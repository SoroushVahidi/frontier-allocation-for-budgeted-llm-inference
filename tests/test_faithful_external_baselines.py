from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from experiments.controllers import (
    L1LengthControlController,
    S1BudgetForcingController,
    TALEPromptBudgetingController,
)
from experiments.frontier_matrix_core import (
    ScoreConfig,
    SimpleBranchScorer,
    build_frontier_strategies,
)
from experiments.branching import SimulatedBranchGenerator
from scripts.run_cohere_real_model_cost_normalized_validation import METHODS

REPO = Path(__file__).resolve().parents[1]


def _generator_factory() -> SimulatedBranchGenerator:
    return SimulatedBranchGenerator(
        rng=__import__("random").Random(123),
        max_depth=4,
        finish_prob_base=0.25,
        answer_noise=0.1,
    )


def test_new_and_old_method_ids_exist() -> None:
    for mid in [
        "external_l1_max",
        "external_tale_prompt_budgeting",
        "external_s1_budget_forcing",
        "external_l1_max_fair_v1",
        "external_tale_ep_prompt_budgeting_faithful_v1",
        "external_s1_budget_forcing_faithful_v1",
    ]:
        assert mid in METHODS


def test_frontier_registry_resolves_new_ids_without_api() -> None:
    specs = build_frontier_strategies(
        _generator_factory,
        budget=6,
        adaptive_min_expand_grid=[1],
        rng=__import__("random").Random(7),
        use_openai_api=False,
        include_external_s1_baseline=True,
        include_external_tale_baseline=True,
        include_external_l1_baseline=True,
    )
    for mid in [
        "external_l1_max_fair_v1",
        "external_tale_ep_prompt_budgeting_faithful_v1",
        "external_s1_budget_forcing_faithful_v1",
        "external_l1_max",
        "external_tale_prompt_budgeting",
        "external_s1_budget_forcing",
    ]:
        assert mid in specs


def test_s1_faithful_metadata_fields_present_no_api() -> None:
    scorer = SimpleBranchScorer(ScoreConfig())
    ctl = S1BudgetForcingController(
        _generator_factory(),
        scorer,
        max_actions_per_problem=4,
        faithful_mode=True,
        method_name="external_s1_budget_forcing_faithful_v1",
    )
    res = ctl.run("If Ana has 2 apples and gets 1 more, how many?", "3")
    md = res.metadata
    assert "s1_faithful_enabled" in md
    assert "continuation_cue" in md
    assert "forced_continue_count" in md
    assert "stop_boundary_detected_count" in md


def test_tale_ep_faithful_prompt_and_metadata_no_api() -> None:
    scorer = SimpleBranchScorer(ScoreConfig())
    ctl = TALEPromptBudgetingController(
        _generator_factory(),
        scorer,
        max_actions_per_problem=4,
        faithful_mode=True,
        tale_variant="EP",
        method_name="external_tale_ep_prompt_budgeting_faithful_v1",
    )
    q = "A box has 10 marbles and 3 are removed. How many remain?"
    budgeted = f"{q}\n{ctl.prompt_template.format(budget=ctl._estimate_budget_tokens(q))}"
    assert "less than" in budgeted.lower()
    res = ctl.run(q, "7")
    md = res.metadata
    assert md.get("budget_estimator_type")
    assert md.get("tale_variant") == "EP"
    assert "assigned_token_budget" in md


def test_l1_fair_metadata_marks_not_official_no_api() -> None:
    scorer = SimpleBranchScorer(ScoreConfig())
    ctl = L1LengthControlController(
        _generator_factory(),
        scorer,
        max_actions_per_problem=4,
        control_mode="max",
        fair_mode=True,
        not_official_external_method=True,
        method_name="external_l1_max_fair_v1",
    )
    res = ctl.run("A number is 5 and add 4. What is result?", "9")
    md = res.metadata
    assert md.get("l1_fair_enabled") is True
    assert md.get("not_official_external_method") is True
    assert md.get("l1_control_mode") == "max"


def test_validate_methods_only_new_ids_no_api_calls() -> None:
    cmd = [
        sys.executable,
        "scripts/run_cohere_real_model_cost_normalized_validation.py",
        "--provider",
        "cohere",
        "--datasets",
        "openai/gsm8k",
        "--budgets",
        "6",
        "--seeds",
        "11",
        "--methods",
        "external_l1_max_fair_v1,external_tale_ep_prompt_budgeting_faithful_v1,external_s1_budget_forcing_faithful_v1",
        "--validate-methods-only",
        "--timestamp",
        "faithful_external_baselines_validate_test",
    ]
    cp = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, check=True)
    assert "validate-methods-only report" in cp.stdout
