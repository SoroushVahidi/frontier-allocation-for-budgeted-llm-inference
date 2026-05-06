"""Registry and offline bounds for direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4 (no API)."""

from __future__ import annotations

import random
import subprocess
import sys
from pathlib import Path

from experiments.frontier_matrix_core import (
    build_frontier_strategies,
    estimate_guarded_k1_frontier4_diverse_root_dr_cost,
    generator_factory_for_mode,
    load_pilot_examples,
)
from experiments.strategy_seeded_semantic_diversity_frontier_v1 import (
    METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1_GUARDED_K1_FRONTIER4,
    METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1_GUARDED_K1_FRONTIER4_FRONTIER_TIEBREAK,
    METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1_GUARDED_K1_FRONTIER4_FRONTIER_TIEBREAK_FINALGUARD,
    METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1_GUARDED_K1_FRONTIER4_FRONTIER_TIEBREAK_NUMERIC_LEAF,
    build_strategy_prompt_styles_semantic_frontier_v1_guarded_k1_frontier4,
    build_strategy_prompt_styles_semantic_frontier_v1_guarded_k3,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
RUNNER = REPO_ROOT / "scripts/run_cohere_real_model_cost_normalized_validation.py"


def test_k1_frontier4_prompt_styles_first_k3_prompt() -> None:
    k1 = build_strategy_prompt_styles_semantic_frontier_v1_guarded_k1_frontier4()
    k3 = build_strategy_prompt_styles_semantic_frontier_v1_guarded_k3()
    assert len(k1) == 1
    assert k1[0] == k3[0]


def test_estimate_k1_frontier4_worst_case_budget_6() -> None:
    est = estimate_guarded_k1_frontier4_diverse_root_dr_cost(budget=6)
    assert est["max_direct_reserve_expand_calls_worst_case"] <= 2
    assert est["min_budget_remaining_after_worst_case_dr"] >= 4
    assert est["frontier_budget_guaranteed_at_least"] is True
    assert est["direct_reserve_phase_max_actions"] == 2
    assert est["direct_reserve_attempts_override"] == 1
    assert est["strategy_seed_max_actions"] == 2


def test_build_frontier_includes_k1_frontier4() -> None:
    rng = random.Random(0)
    gen_factory = generator_factory_for_mode(False, rng, "gpt-4o-mini", 0.1, 220, 30)
    specs = build_frontier_strategies(
        gen_factory,
        6,
        [1],
        rng,
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
        include_external_l1_baseline=True,
        include_external_s1_baseline=True,
        include_external_tale_baseline=True,
    )
    assert METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1_GUARDED_K1_FRONTIER4 in specs
    ctrl = specs[METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1_GUARDED_K1_FRONTIER4]
    assert ctrl.direct_reserve_attempts_override == 1
    assert ctrl.strategy_seed_max_actions == 2
    assert ctrl.direct_reserve_phase_max_actions == 2


def test_simulated_k1_frontier4_leaves_at_least_four_actions_for_frontier() -> None:
    ex0 = load_pilot_examples("openai/gsm8k", 20, 11)
    for seed in range(15):
        rng = random.Random(seed)
        gen_factory = generator_factory_for_mode(False, rng, "gpt-4o-mini", 0.1, 220, 30)
        specs = build_frontier_strategies(
            gen_factory,
            6,
            [1],
            rng,
            use_openai_api=False,
            include_broad_diversity_aggregation_methods=True,
            include_external_l1_baseline=True,
            include_external_s1_baseline=True,
            include_external_tale_baseline=True,
        )
        ctrl = specs[METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1_GUARDED_K1_FRONTIER4]
        ex = ex0[seed % len(ex0)]
        result = ctrl.run(ex.question, ex.answer)
        md = result.metadata or {}
        rem = int(md.get("remaining_budget_before_frontier", -1))
        assert rem >= 4, (seed, rem, md.get("direct_reserve_metadata"))
        dr_meta = md.get("direct_reserve_metadata") or {}
        assert dr_meta.get("direct_reserve_phase_max_actions") == 2
        dr_trace = md.get("direct_reserve_attempts") or []
        assert len(dr_trace) <= 2


def test_validate_methods_only_accepts_k1_frontier4_no_api() -> None:
    proc = subprocess.run(
        [
            sys.executable,
            str(RUNNER),
            "--providers",
            "cohere",
            "--datasets",
            "openai/gsm8k",
            "--budgets",
            "6",
            "--seeds",
            "20260501",
            "--methods",
            "external_l1_max,direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4,direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak",
            "--max-examples",
            "1",
            "--target-scored-per-slice",
            "1",
            "--validate-methods-only",
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_validate_methods_only_unknown_method_exits_nonzero() -> None:
    proc = subprocess.run(
        [
            sys.executable,
            str(RUNNER),
            "--providers",
            "cohere",
            "--datasets",
            "openai/gsm8k",
            "--budgets",
            "6",
            "--seeds",
            "20260501",
            "--methods",
            "not_a_real_method_ever_k1f4",
            "--validate-methods-only",
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode != 0, proc.stdout + proc.stderr
    assert "Unknown method" in (proc.stderr or "")


def test_build_frontier_includes_k1_frontier4_frontier_tiebreak_numeric_leaf() -> None:
    rng = random.Random(0)
    gen_factory = generator_factory_for_mode(False, rng, "gpt-4o-mini", 0.1, 220, 30)
    specs = build_frontier_strategies(
        gen_factory,
        6,
        [1],
        rng,
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
        include_external_l1_baseline=True,
        include_external_s1_baseline=True,
        include_external_tale_baseline=True,
    )
    assert METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1_GUARDED_K1_FRONTIER4_FRONTIER_TIEBREAK_NUMERIC_LEAF in specs
    ctrl = specs[METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1_GUARDED_K1_FRONTIER4_FRONTIER_TIEBREAK_NUMERIC_LEAF]
    assert getattr(ctrl, "enable_frontier_max_support_tiebreak", False) is True


def test_build_frontier_includes_k1_frontier4_frontier_tiebreak_finalguard() -> None:
    rng = random.Random(0)
    gen_factory = generator_factory_for_mode(False, rng, "gpt-4o-mini", 0.1, 220, 30)
    specs = build_frontier_strategies(
        gen_factory,
        6,
        [1],
        rng,
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
        include_external_l1_baseline=True,
        include_external_s1_baseline=True,
        include_external_tale_baseline=True,
    )
    assert METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1_GUARDED_K1_FRONTIER4_FRONTIER_TIEBREAK_FINALGUARD in specs
    ctrl = specs[METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1_GUARDED_K1_FRONTIER4_FRONTIER_TIEBREAK_FINALGUARD]
    assert getattr(ctrl, "enable_frontier_max_support_tiebreak", False) is True


def test_build_frontier_includes_k1_frontier4_frontier_tiebreak() -> None:
    rng = random.Random(0)
    gen_factory = generator_factory_for_mode(False, rng, "gpt-4o-mini", 0.1, 220, 30)
    specs = build_frontier_strategies(
        gen_factory,
        6,
        [1],
        rng,
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
        include_external_l1_baseline=True,
        include_external_s1_baseline=True,
        include_external_tale_baseline=True,
    )
    assert METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1_GUARDED_K1_FRONTIER4_FRONTIER_TIEBREAK in specs
    ctrl = specs[METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1_GUARDED_K1_FRONTIER4_FRONTIER_TIEBREAK]
    assert getattr(ctrl, "enable_frontier_max_support_tiebreak", False) is True


def test_runner_methods_registry_contains_k1_frontier4() -> None:
    import importlib.util

    mod_name = "cohere_runner_mod_test_guarded_k1_frontier4"
    spec = importlib.util.spec_from_file_location(mod_name, RUNNER)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    row = mod.METHODS.get("direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4")
    assert row is not None
    assert row["runtime"] == "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4"
