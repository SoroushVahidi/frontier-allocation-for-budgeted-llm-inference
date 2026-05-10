from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from experiments.branching import SimulatedBranchGenerator
from experiments.controllers import (
    L1LengthControlController,
    ProgramOfThoughtController,
    S1BudgetForcingController,
    SelfConsistencyFairController,
    TALEPromptBudgetingController,
)
from experiments.frontier_matrix_core import ScoreConfig, SimpleBranchScorer, build_frontier_strategies
from scripts.run_cohere_real_model_cost_normalized_validation import METHODS

REPO = Path(__file__).resolve().parents[1]


def _gen() -> SimulatedBranchGenerator:
    return SimulatedBranchGenerator(
        rng=__import__("random").Random(42),
        max_depth=4,
        finish_prob_base=0.25,
        answer_noise=0.1,
    )


def test_main_table_method_ids_and_legacy_ids_exist() -> None:
    new_ids = {
        "external_l1_max_fair_v1",
        "external_self_consistency_4_fair_v1",
        "external_self_consistency_6_fair_v1",
        "external_pal_pot_fair_v1",
        "external_s1_budget_forcing_faithful_v1",
        "external_tale_ep_prompt_budgeting_faithful_v1",
    }
    old_ids = {
        "external_l1_max",
        "external_tale_prompt_budgeting",
        "external_s1_budget_forcing",
    }
    assert new_ids.issubset(METHODS.keys())
    assert old_ids.issubset(METHODS.keys())


def test_self_consistency_4_and_6_metadata() -> None:
    scorer = SimpleBranchScorer(ScoreConfig())
    c4 = SelfConsistencyFairController(_gen(), scorer, 6, n_samples=4, method_name="external_self_consistency_4_fair_v1")
    c6 = SelfConsistencyFairController(_gen(), scorer, 6, n_samples=6, method_name="external_self_consistency_6_fair_v1")
    r4 = c4.run("2+2?", "4")
    r6 = c6.run("2+2?", "4")
    assert r4.metadata.get("n_samples") == 4
    assert r6.metadata.get("n_samples") == 6
    assert r4.metadata.get("call_count") == 4
    assert r6.metadata.get("call_count") == 6
    assert "tie_break_rule" in r4.metadata


def test_l1_s1_tale_faithful_metadata_support() -> None:
    scorer = SimpleBranchScorer(ScoreConfig())
    l1 = L1LengthControlController(
        _gen(),
        scorer,
        4,
        control_mode="max",
        fair_mode=True,
        not_official_external_method=True,
        method_name="external_l1_max_fair_v1",
    ).run("5+4?", "9")
    assert l1.metadata.get("not_official_external_method") is True

    s1 = S1BudgetForcingController(
        _gen(),
        scorer,
        4,
        faithful_mode=True,
        method_name="external_s1_budget_forcing_faithful_v1",
    ).run("6-1?", "5")
    assert s1.metadata.get("continuation_cue") == "Wait"
    assert "num_ignore_think_end" in s1.metadata

    tale = TALEPromptBudgetingController(
        _gen(),
        scorer,
        4,
        faithful_mode=True,
        tale_variant="EP",
        method_name="external_tale_ep_prompt_budgeting_faithful_v1",
    ).run("If 10 marbles and 3 removed, remaining?", "7")
    assert tale.metadata.get("tale_variant") == "EP"
    assert "budget_estimator_type" in tale.metadata
    assert "assigned_token_budget" in tale.metadata


def test_pal_pot_fair_has_metadata_or_is_marked_missing() -> None:
    scorer = SimpleBranchScorer(ScoreConfig())
    pot = ProgramOfThoughtController(_gen(), scorer, 4, method_name="external_pal_pot_fair_v1").run("1+1?", "2")
    md = pot.metadata
    if "error" in md:
        assert md["error"] == "generator_missing_generate_program_of_thought_answer"
    else:
        assert "baseline_family" in md
        assert ("code_generated" in md) or ("pot_output" in md)


def test_new_ids_resolve_in_frontier_registry() -> None:
    specs = build_frontier_strategies(
        _gen,
        budget=6,
        adaptive_min_expand_grid=[1],
        rng=__import__("random").Random(11),
        use_openai_api=False,
        include_external_s1_baseline=True,
        include_external_tale_baseline=True,
        include_external_l1_baseline=True,
    )
    for mid in [
        "external_l1_max_fair_v1",
        "external_self_consistency_4_fair_v1",
        "external_self_consistency_6_fair_v1",
        "external_pal_pot_fair_v1",
        "external_s1_budget_forcing_faithful_v1",
        "external_tale_ep_prompt_budgeting_faithful_v1",
    ]:
        assert mid in specs


def test_validate_methods_only_for_six_ids_no_api() -> None:
    cmd = [
        sys.executable,
        "scripts/run_cohere_real_model_cost_normalized_validation.py",
        "--provider",
        "cohere",
        "--datasets",
        "openai/gsm8k",
        "--budgets",
        "4,6",
        "--seeds",
        "11",
        "--methods",
        (
            "external_l1_max_fair_v1,external_self_consistency_4_fair_v1,"
            "external_self_consistency_6_fair_v1,external_pal_pot_fair_v1,"
            "external_s1_budget_forcing_faithful_v1,external_tale_ep_prompt_budgeting_faithful_v1"
        ),
        "--validate-methods-only",
        "--timestamp",
        "main_table_external_baselines_validate_test",
    ]
    cp = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, check=True)
    assert "bad_rows=0" in cp.stdout
