"""Shared frontier-strategy construction and evaluation for the new-paper track.

Used by `scripts/run_cross_strategy_frontier_allocation.py` and
`scripts/run_new_paper_frontier_matrix.py` so strategy definitions stay in sync.
"""

from __future__ import annotations

import os
import random
from typing import Any, Callable

from experiments.branching import APIBranchGenerator, SimulatedBranchGenerator
from experiments.controllers import (
    AdaptiveController,
    BeamController,
    BestOfNController,
    GlobalDiversityAggregationController,
    GreedyController,
    IntermediateTrapAwareNearTieController,
    ProgramOfThoughtController,
    S1BudgetForcingController,
    SelectiveSelfConsistencyHybridController,
    L1LengthControlController,
    TALEPromptBudgetingController,
    VerifierGuidedSearchController,
)
from experiments.prm_partial_scorer import HeuristicPRMPartialScorer
from experiments.data import PilotExample, extract_final_answer
from experiments.hf_datasets import resolve_dataset_spec, sample_hf_examples
from experiments.scoring import LearnedBTBranchScorer, ScoreConfig, SimpleBranchScorer
from experiments.verifiers import LLMVerifyProxyVerifier, SimulatedScorerVerifier


def resolve_api_key_for_provider(provider: str) -> str | None:
    """Return API key from environment for OpenAI / Groq / Gemini-style backends."""
    p = provider.strip().lower()
    if p == "openai":
        return os.getenv("OPENAI_API_KEY")
    if p == "cohere":
        return os.getenv("COHERE_API_KEY")
    if p == "groq":
        return os.getenv("GROQ_API_KEY")
    if p == "gemini":
        return os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    return None


def load_pilot_examples(dataset_name: str, subset_size: int, seed: int) -> list[PilotExample]:
    spec = resolve_dataset_spec(dataset_name)
    rows = sample_hf_examples(
        dataset_name=dataset_name,
        pilot_size=subset_size,
        seed=seed,
        split=spec.default_split,
        config_name=spec.default_config,
    )
    return [
        PilotExample(
            example_id=r["example_id"],
            question=r["question"],
            answer=extract_final_answer(r["answer"]),
        )
        for r in rows
    ]


def generator_factory_for_mode(
    use_openai_api: bool,
    rng: random.Random,
    openai_model: str,
    temperature: float,
    max_output_tokens: int,
    timeout_seconds: int,
    api_provider: str | None = None,
) -> Callable[[], Any]:
    if use_openai_api:
        provider = (api_provider or "openai").strip().lower()
        key = resolve_api_key_for_provider(provider)

        def factory() -> APIBranchGenerator:
            return APIBranchGenerator(
                provider=provider,
                api_key=key,
                model=openai_model,
                temperature=temperature,
                max_tokens=max_output_tokens,
                timeout_seconds=timeout_seconds,
            )

        return factory

    def factory() -> SimulatedBranchGenerator:
        return SimulatedBranchGenerator(rng=rng, max_depth=7, finish_prob_base=0.16, answer_noise=0.12)

    return factory


def build_frontier_strategies(
    generator_factory: Callable[[], Any],
    budget: int,
    adaptive_min_expand_grid: list[int],
    rng: random.Random,
    *,
    use_openai_api: bool,
    vgs_candidates: int = 3,
    vgs_min_expansions: int = 1,
    include_budget_guarded_adaptive: bool = False,
    include_prm_variants: bool = False,
    prm_early_reject_threshold: float = 0.25,
    prm_early_reject_min_expansions: int = 2,
    bt_pairwise_model_path: str | None = None,
    bt_pairwise_reliability_model_path: str | None = None,
    bt_pairwise_oracle_model_path: str | None = None,
    include_external_s1_baseline: bool = False,
    s1_num_ignore_think_end: int = 1,
    s1_min_thinking_steps: int = 0,
    include_external_tale_baseline: bool = False,
    tale_token_budget_default: int = 256,
    tale_token_budget_min: int = 64,
    tale_token_budget_max: int = 512,
    tale_token_budget_per_question_char: float = 0.75,
    tale_token_per_action: float = 64.0,
    include_external_l1_baseline: bool = False,
    include_external_zhai_cpo_baseline: bool = False,
    include_selective_sc_hybrid_methods: bool = False,
    include_broad_diversity_aggregation_methods: bool = False,
    include_marginal_coverage_diversity_methods: bool = False,
    include_duplicate_aware_aggregation_commit_methods: bool = False,
    l1_exact_token_budget: int = 512,
    l1_max_token_budget: int = 512,
    l1_token_per_action: float = 64.0,
    l1_prompt_style: str = "Let's think step by step and output the final answer within \\boxed{}.",
) -> dict[str, Any]:
    scorer = SimpleBranchScorer(ScoreConfig())
    prm_scorer = HeuristicPRMPartialScorer()
    specs: dict[str, Any] = {
        "reasoning_greedy": GreedyController(generator_factory(), scorer, budget),
        "self_consistency_3": BestOfNController(generator_factory(), scorer, budget, n_candidates=3),
        "reasoning_beam2": BeamController(generator_factory(), scorer, budget, width=2),
    }
    for min_expand in adaptive_min_expand_grid:
        specs[f"adaptive_min_expand_{min_expand}"] = AdaptiveController(
            generator_factory(),
            scorer,
            budget,
            high_threshold=0.72,
            low_threshold=0.42,
            max_branches=3,
            allow_verify=True,
            min_expansions_before_prune=min_expand,
            method_name=f"adaptive_min_expand_{min_expand}",
        )
    if bt_pairwise_model_path:
        bt_scorer = LearnedBTBranchScorer(bt_pairwise_model_path, max_actions_per_problem=budget)
        specs["adaptive_bt_pairwise"] = AdaptiveController(
            generator_factory(),
            bt_scorer,
            budget,
            high_threshold=0.72,
            low_threshold=0.42,
            max_branches=3,
            allow_verify=True,
            min_expansions_before_prune=1,
            method_name="adaptive_bt_pairwise",
        )
    if bt_pairwise_reliability_model_path:
        bt_rel_scorer = LearnedBTBranchScorer(bt_pairwise_reliability_model_path, max_actions_per_problem=budget)
        specs["adaptive_bt_pairwise_reliability"] = AdaptiveController(
            generator_factory(),
            bt_rel_scorer,
            budget,
            high_threshold=0.72,
            low_threshold=0.42,
            max_branches=3,
            allow_verify=True,
            min_expansions_before_prune=1,
            method_name="adaptive_bt_pairwise_reliability",
        )
    if bt_pairwise_oracle_model_path:
        bt_oracle_scorer = LearnedBTBranchScorer(bt_pairwise_oracle_model_path, max_actions_per_problem=budget)
        specs["adaptive_bt_pairwise_oracle"] = AdaptiveController(
            generator_factory(),
            bt_oracle_scorer,
            budget,
            high_threshold=0.72,
            low_threshold=0.42,
            max_branches=3,
            allow_verify=True,
            min_expansions_before_prune=1,
            method_name="adaptive_bt_pairwise_oracle",
        )
    if include_budget_guarded_adaptive:
        specs["adaptive_budget_guarded"] = AdaptiveController(
            generator_factory(),
            scorer,
            budget,
            high_threshold=0.72,
            low_threshold=0.42,
            max_branches=3,
            allow_verify=True,
            min_expansions_before_prune=0,
            adaptive_min_expand=True,
            verify_exploration_floor=1,
            budget_guard_prune_floor=0.40,
            method_name="adaptive_budget_guarded",
        )

    if include_prm_variants:
        specs["adaptive_prm_partial"] = AdaptiveController(
            generator_factory(),
            scorer,
            budget,
            high_threshold=0.72,
            low_threshold=0.42,
            max_branches=3,
            allow_verify=True,
            min_expansions_before_prune=1,
            partial_branch_scorer=prm_scorer,
            enable_prm_early_reject=False,
            method_name="adaptive_prm_partial",
        )
        specs["adaptive_prm_partial_early_reject"] = AdaptiveController(
            generator_factory(),
            scorer,
            budget,
            high_threshold=0.72,
            low_threshold=0.42,
            max_branches=3,
            allow_verify=True,
            min_expansions_before_prune=1,
            partial_branch_scorer=prm_scorer,
            enable_prm_early_reject=True,
            prm_early_reject_threshold=prm_early_reject_threshold,
            prm_early_reject_min_expansions=prm_early_reject_min_expansions,
            method_name="adaptive_prm_partial_early_reject",
        )

    if use_openai_api:
        verifier = LLMVerifyProxyVerifier(generator_factory())
    else:
        verifier = SimulatedScorerVerifier(rng)

    specs["verifier_guided_search"] = VerifierGuidedSearchController(
        generator_factory(),
        scorer,
        budget,
        n_candidates=min(vgs_candidates, max(1, budget // 2)),
        verifier=verifier,
        min_expansions_per_candidate=vgs_min_expansions,
        method_name="verifier_guided_search",
    )
    if include_prm_variants:
        specs["verifier_guided_search_prm"] = VerifierGuidedSearchController(
            generator_factory(),
            scorer,
            budget,
            n_candidates=min(vgs_candidates, max(1, budget // 2)),
            verifier=verifier,
            min_expansions_per_candidate=vgs_min_expansions,
            partial_branch_scorer=prm_scorer,
            enable_prm_early_reject=False,
            method_name="verifier_guided_search_prm",
        )
        specs["verifier_guided_search_prm_early_reject"] = VerifierGuidedSearchController(
            generator_factory(),
            scorer,
            budget,
            n_candidates=min(vgs_candidates, max(1, budget // 2)),
            verifier=verifier,
            min_expansions_per_candidate=vgs_min_expansions,
            partial_branch_scorer=prm_scorer,
            enable_prm_early_reject=True,
            prm_early_reject_threshold=prm_early_reject_threshold,
            method_name="verifier_guided_search_prm_early_reject",
        )
    specs["program_of_thought"] = ProgramOfThoughtController(
        generator_factory(),
        scorer,
        budget,
        method_name="program_of_thought",
    )
    if include_external_s1_baseline:
        specs["external_s1_budget_forcing"] = S1BudgetForcingController(
            generator_factory(),
            scorer,
            budget,
            num_ignore_think_end=s1_num_ignore_think_end,
            min_thinking_steps=s1_min_thinking_steps,
            method_name="external_s1_budget_forcing",
        )
    if include_external_tale_baseline:
        specs["external_tale_prompt_budgeting"] = TALEPromptBudgetingController(
            generator_factory(),
            scorer,
            budget,
            token_budget_default=tale_token_budget_default,
            token_budget_min=tale_token_budget_min,
            token_budget_max=tale_token_budget_max,
            token_budget_per_question_char=tale_token_budget_per_question_char,
            token_per_action=tale_token_per_action,
            method_name="external_tale_prompt_budgeting",
        )
    if include_external_l1_baseline:
        specs["external_l1_exact"] = L1LengthControlController(
            generator_factory(),
            scorer,
            budget,
            control_mode="exact",
            token_budget=l1_exact_token_budget,
            token_per_action=l1_token_per_action,
            prompt_style=l1_prompt_style,
            method_name="external_l1_exact",
        )
        specs["external_l1_max"] = L1LengthControlController(
            generator_factory(),
            scorer,
            budget,
            control_mode="max",
            token_budget=l1_max_token_budget,
            token_per_action=l1_token_per_action,
            prompt_style=l1_prompt_style,
            method_name="external_l1_max",
        )
    if include_external_zhai_cpo_baseline:
        specs["external_zhai_cpo_mode_a"] = AdaptiveController(
            generator_factory(),
            scorer,
            budget,
            high_threshold=0.70,
            low_threshold=0.40,
            max_branches=3,
            allow_verify=True,
            min_expansions_before_prune=1,
            adaptive_min_expand=True,
            verify_exploration_floor=1,
            budget_guard_prune_floor=0.35,
            method_name="external_zhai_cpo_mode_a",
        )
    if include_selective_sc_hybrid_methods:
        specs["intermediate_trap_aware_near_tie_v1"] = IntermediateTrapAwareNearTieController(
            generator_factory(),
            scorer,
            budget,
            high_threshold=0.72,
            low_threshold=0.42,
            max_branches=3,
            allow_verify=True,
            min_expansions_before_prune=1,
            near_tie_gap=0.03,
            incompleteness_trigger=0.45,
            method_name="intermediate_trap_aware_near_tie_v1",
        )
        specs["selective_sc_hybrid_v1"] = SelectiveSelfConsistencyHybridController(
            generator_factory(),
            scorer,
            budget,
            high_threshold=0.72,
            low_threshold=0.42,
            max_branches=3,
            allow_verify=True,
            min_expansions_before_prune=1,
            near_tie_gap=0.03,
            low_completion_trigger=0.45,
            disagreement_trigger=0.12,
            diversity_top_k=3,
            min_consensus_support=0.56,
            method_name="selective_sc_hybrid_v1",
        )
    if include_broad_diversity_aggregation_methods:
        specs["broad_diversity_aggregation_v1"] = GlobalDiversityAggregationController(
            generator_factory(),
            scorer,
            budget,
            max_branches=4,
            min_branch_expansions=1,
            diversity_weight=0.28,
            duplicate_penalty=0.12,
            unknown_answer_bonus=0.06,
            answer_support_weight=0.45,
            value_weight=0.55,
            commit_support_threshold=0.68,
            commit_delay_min_actions=3,
            method_name="broad_diversity_aggregation_v1",
        )
        specs["broad_diversity_aggregation_strong_v1"] = GlobalDiversityAggregationController(
            generator_factory(),
            scorer,
            budget,
            max_branches=4,
            min_branch_expansions=1,
            diversity_weight=0.40,
            duplicate_penalty=0.15,
            unknown_answer_bonus=0.08,
            answer_support_weight=0.55,
            value_weight=0.45,
            commit_support_threshold=0.72,
            commit_delay_min_actions=4,
            method_name="broad_diversity_aggregation_strong_v1",
        )
        specs["broad_diversity_aggregation_strong_v1_incumbent_challenger_commit_v1"] = GlobalDiversityAggregationController(
            generator_factory(),
            scorer,
            budget,
            max_branches=4,
            min_branch_expansions=1,
            diversity_weight=0.40,
            duplicate_penalty=0.15,
            unknown_answer_bonus=0.08,
            answer_support_weight=0.55,
            value_weight=0.45,
            commit_support_threshold=0.72,
            commit_delay_min_actions=4,
            enable_incumbent_challenger_commit=True,
            incumbent_challenger_raw_support_only=False,
            incumbent_challenger_margin_threshold=0.10,
            incumbent_challenger_stability_min_steps=2,
            incumbent_challenger_near_tie_gap=0.05,
            incumbent_challenger_plausible_gap=0.05,
            method_name="broad_diversity_aggregation_strong_v1_incumbent_challenger_commit_v1",
        )
        specs["broad_diversity_aggregation_strong_v1_incumbent_challenger_raw_support_v1"] = GlobalDiversityAggregationController(
            generator_factory(),
            scorer,
            budget,
            max_branches=4,
            min_branch_expansions=1,
            diversity_weight=0.40,
            duplicate_penalty=0.15,
            unknown_answer_bonus=0.08,
            answer_support_weight=0.55,
            value_weight=0.45,
            commit_support_threshold=0.72,
            commit_delay_min_actions=4,
            enable_incumbent_challenger_commit=True,
            incumbent_challenger_raw_support_only=True,
            incumbent_challenger_margin_threshold=0.10,
            incumbent_challenger_stability_min_steps=2,
            incumbent_challenger_near_tie_gap=0.05,
            incumbent_challenger_plausible_gap=0.05,
            method_name="broad_diversity_aggregation_strong_v1_incumbent_challenger_raw_support_v1",
        )
        specs["broad_diversity_aggregation_strong_v1_incumbent_challenger_commit_late_guard_v1"] = GlobalDiversityAggregationController(
            generator_factory(),
            scorer,
            budget,
            max_branches=4,
            min_branch_expansions=1,
            diversity_weight=0.40,
            duplicate_penalty=0.15,
            unknown_answer_bonus=0.08,
            answer_support_weight=0.55,
            value_weight=0.45,
            commit_support_threshold=0.70,
            commit_delay_min_actions=3,
            enable_incumbent_challenger_commit=True,
            incumbent_challenger_raw_support_only=False,
            incumbent_challenger_margin_threshold=0.08,
            incumbent_challenger_stability_min_steps=2,
            incumbent_challenger_near_tie_gap=0.05,
            incumbent_challenger_plausible_gap=0.06,
            method_name="broad_diversity_aggregation_strong_v1_incumbent_challenger_commit_late_guard_v1",
        )
        specs["broad_diversity_aggregation_strong_v1_incumbent_challenger_commit_switch_persistence_v1"] = GlobalDiversityAggregationController(
            generator_factory(),
            scorer,
            budget,
            max_branches=4,
            min_branch_expansions=1,
            diversity_weight=0.40,
            duplicate_penalty=0.15,
            unknown_answer_bonus=0.08,
            answer_support_weight=0.55,
            value_weight=0.45,
            commit_support_threshold=0.72,
            commit_delay_min_actions=4,
            enable_incumbent_challenger_commit=True,
            incumbent_challenger_raw_support_only=False,
            incumbent_challenger_margin_threshold=0.11,
            incumbent_challenger_stability_min_steps=3,
            incumbent_challenger_near_tie_gap=0.05,
            incumbent_challenger_plausible_gap=0.05,
            method_name="broad_diversity_aggregation_strong_v1_incumbent_challenger_commit_switch_persistence_v1",
        )
        specs["broad_diversity_aggregation_strong_v1_incumbent_challenger_metalevel_v2"] = GlobalDiversityAggregationController(
            generator_factory(),
            scorer,
            budget,
            max_branches=4,
            min_branch_expansions=1,
            diversity_weight=0.40,
            duplicate_penalty=0.15,
            unknown_answer_bonus=0.08,
            answer_support_weight=0.55,
            value_weight=0.45,
            commit_support_threshold=0.72,
            commit_delay_min_actions=4,
            enable_incumbent_challenger_commit=True,
            incumbent_challenger_raw_support_only=False,
            incumbent_challenger_margin_threshold=0.09,
            incumbent_challenger_stability_min_steps=2,
            incumbent_challenger_near_tie_gap=0.05,
            incumbent_challenger_plausible_gap=0.05,
            incumbent_safety_commit_min=0.62,
            challenger_upside_commit_max=0.15,
            challenger_upside_expand_weight=0.35,
            metalevel_delta_margin=0.00,
            near_tie_commit_margin_extra=0.00,
            force_extra_explore_on_near_tie=True,
            near_tie_force_max_steps=1,
            near_tie_force_upside_frac_threshold=0.60,
            intermediate_result_penalty=0.18,
            method_name="broad_diversity_aggregation_strong_v1_incumbent_challenger_metalevel_v2",
        )
        specs["broad_diversity_aggregation_strong_v1_diversity_needed_gate"] = GlobalDiversityAggregationController(
            generator_factory(),
            scorer,
            budget,
            max_branches=4,
            min_branch_expansions=1,
            diversity_weight=0.40,
            duplicate_penalty=0.15,
            unknown_answer_bonus=0.08,
            answer_support_weight=0.55,
            value_weight=0.45,
            commit_support_threshold=0.72,
            commit_delay_min_actions=4,
            diversity_needed_gate_mode="learned",
            diversity_needed_gate_positive_threshold=0.12,
            diversity_needed_gate_negative_threshold=-0.12,
            method_name="broad_diversity_aggregation_strong_v1_diversity_needed_gate",
        )
        specs["broad_diversity_aggregation_strong_v1_heuristic_gate"] = GlobalDiversityAggregationController(
            generator_factory(),
            scorer,
            budget,
            max_branches=4,
            min_branch_expansions=1,
            diversity_weight=0.40,
            duplicate_penalty=0.15,
            unknown_answer_bonus=0.08,
            answer_support_weight=0.55,
            value_weight=0.45,
            commit_support_threshold=0.72,
            commit_delay_min_actions=4,
            diversity_needed_gate_mode="heuristic",
            diversity_needed_gate_positive_threshold=0.10,
            diversity_needed_gate_negative_threshold=-0.10,
            method_name="broad_diversity_aggregation_strong_v1_heuristic_gate",
        )
        specs["answer_group_coverage_floor_v1"] = GlobalDiversityAggregationController(
            generator_factory(),
            scorer,
            budget,
            max_branches=4,
            min_branch_expansions=1,
            diversity_weight=0.31,
            duplicate_penalty=0.12,
            unknown_answer_bonus=0.06,
            answer_support_weight=0.48,
            value_weight=0.52,
            commit_support_threshold=0.70,
            commit_delay_min_actions=4,
            enable_answer_group_coverage_floor=True,
            min_answer_groups_before_concentration=2,
            coverage_floor_min_actions=2,
            coverage_floor_max_actions=7,
            coverage_floor_plausibility_threshold=0.46,
            coverage_floor_max_forced_steps=2,
            method_name="answer_group_coverage_floor_v1",
        )
        specs["broad_diversity_aggregation_strong_v1_early_answer_group_preservation_v1"] = GlobalDiversityAggregationController(
            generator_factory(),
            scorer,
            budget,
            max_branches=4,
            min_branch_expansions=1,
            diversity_weight=0.40,
            duplicate_penalty=0.15,
            unknown_answer_bonus=0.08,
            answer_support_weight=0.55,
            value_weight=0.45,
            commit_support_threshold=0.72,
            commit_delay_min_actions=4,
            enable_early_answer_group_preservation=True,
            early_preservation_action_window=5,
            early_preservation_min_plausible_continuation=0.46,
            early_preservation_target_alignment_min=0.34,
            early_preservation_required_group_gap=0.18,
            early_preservation_challenger_hold_steps=2,
            method_name="broad_diversity_aggregation_strong_v1_early_answer_group_preservation_v1",
        )
        specs["broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_v1"] = GlobalDiversityAggregationController(
            generator_factory(),
            scorer,
            budget,
            max_branches=4,
            min_branch_expansions=1,
            diversity_weight=0.40,
            duplicate_penalty=0.15,
            unknown_answer_bonus=0.08,
            answer_support_weight=0.55,
            value_weight=0.45,
            commit_support_threshold=0.72,
            commit_delay_min_actions=4,
            enable_early_answer_group_preservation=True,
            early_preservation_action_window=5,
            early_preservation_min_plausible_continuation=0.46,
            early_preservation_target_alignment_min=0.34,
            early_preservation_required_group_gap=0.18,
            early_preservation_challenger_hold_steps=2,
            enable_anti_collapse_answer_group_refinement=True,
            anti_collapse_early_window=6,
            repeated_same_branch_penalty=0.09,
            repeated_same_branch_cap=3,
            monopolization_margin_requirement=0.11,
            answer_group_distinctness_bonus=0.12,
            duplicate_answer_group_penalty=0.08,
            min_followup_steps_for_preserved_alternative=2,
            alternative_maturity_window=5,
            protected_alternative_target_alignment_min=0.48,
            method_name="broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_v1",
        )
        specs["broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_harmed_tuned_v1"] = (
            GlobalDiversityAggregationController(
                generator_factory(),
                scorer,
                budget,
                max_branches=4,
                min_branch_expansions=1,
                diversity_weight=0.40,
                duplicate_penalty=0.15,
                unknown_answer_bonus=0.08,
                answer_support_weight=0.55,
                value_weight=0.45,
                commit_support_threshold=0.72,
                commit_delay_min_actions=4,
                enable_early_answer_group_preservation=True,
                early_preservation_action_window=5,
                early_preservation_min_plausible_continuation=0.46,
                early_preservation_target_alignment_min=0.34,
                early_preservation_required_group_gap=0.18,
                early_preservation_challenger_hold_steps=2,
                enable_anti_collapse_answer_group_refinement=True,
                anti_collapse_early_window=6,
                repeated_same_branch_penalty=0.085,
                repeated_same_branch_cap=2,
                monopolization_margin_requirement=0.09,
                answer_group_distinctness_bonus=0.13,
                duplicate_answer_group_penalty=0.08,
                min_followup_steps_for_preserved_alternative=2,
                alternative_maturity_window=5,
                protected_alternative_target_alignment_min=0.48,
                method_name="broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_harmed_tuned_v1",
            )
        )
        specs["broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_v1"] = (
            GlobalDiversityAggregationController(
                generator_factory(),
                scorer,
                budget,
                max_branches=4,
                min_branch_expansions=1,
                diversity_weight=0.40,
                duplicate_penalty=0.15,
                unknown_answer_bonus=0.08,
                answer_support_weight=0.55,
                value_weight=0.45,
                commit_support_threshold=0.72,
                commit_delay_min_actions=4,
                enable_early_answer_group_preservation=True,
                early_preservation_action_window=5,
                early_preservation_min_plausible_continuation=0.46,
                early_preservation_target_alignment_min=0.34,
                early_preservation_required_group_gap=0.18,
                early_preservation_challenger_hold_steps=2,
                enable_anti_collapse_answer_group_refinement=True,
                anti_collapse_early_window=6,
                repeated_same_branch_penalty=0.09,
                repeated_same_branch_cap=3,
                repeat_expand_free_steps=3,
                repeat_expand_penalty_weight=0.07,
                repeat_expand_family_penalty_weight=0.12,
                repeat_expand_override_margin=0.10,
                monopolization_margin_requirement=0.11,
                answer_group_distinctness_bonus=0.12,
                duplicate_answer_group_penalty=0.08,
                min_followup_steps_for_preserved_alternative=2,
                alternative_maturity_window=5,
                protected_alternative_target_alignment_min=0.48,
                method_name="broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_v1",
            )
        )

        specs["broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1"] = (
            GlobalDiversityAggregationController(
                generator_factory(),
                scorer,
                budget,
                max_branches=4,
                min_branch_expansions=1,
                diversity_weight=0.40,
                duplicate_penalty=0.15,
                unknown_answer_bonus=0.08,
                answer_support_weight=0.55,
                value_weight=0.45,
                commit_support_threshold=0.72,
                commit_delay_min_actions=4,
                enable_early_answer_group_preservation=True,
                early_preservation_action_window=5,
                early_preservation_min_plausible_continuation=0.46,
                early_preservation_target_alignment_min=0.34,
                early_preservation_required_group_gap=0.18,
                early_preservation_challenger_hold_steps=2,
                enable_anti_collapse_answer_group_refinement=True,
                anti_collapse_early_window=6,
                repeated_same_branch_penalty=0.09,
                repeated_same_branch_cap=3,
                repeat_expand_free_steps=3,
                repeat_expand_penalty_weight=0.065,
                repeat_expand_family_penalty_weight=0.12,
                repeat_expand_override_margin=0.08,
                monopolization_margin_requirement=0.11,
                answer_group_distinctness_bonus=0.12,
                duplicate_answer_group_penalty=0.08,
                min_followup_steps_for_preserved_alternative=2,
                alternative_maturity_window=5,
                protected_alternative_target_alignment_min=0.48,
                method_name="broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1",
            )
        )
        specs["broad_diversity_aggregation_strong_v1_anti_collapse_repeat_expansion_low_marginal_gain_cooldown_v1"] = (
            GlobalDiversityAggregationController(
                generator_factory(),
                scorer,
                budget,
                max_branches=4,
                min_branch_expansions=1,
                diversity_weight=0.40,
                duplicate_penalty=0.15,
                unknown_answer_bonus=0.08,
                answer_support_weight=0.55,
                value_weight=0.45,
                commit_support_threshold=0.72,
                commit_delay_min_actions=4,
                enable_early_answer_group_preservation=True,
                early_preservation_action_window=5,
                early_preservation_min_plausible_continuation=0.46,
                early_preservation_target_alignment_min=0.34,
                early_preservation_required_group_gap=0.18,
                early_preservation_challenger_hold_steps=2,
                enable_anti_collapse_answer_group_refinement=True,
                anti_collapse_early_window=6,
                repeated_same_branch_penalty=0.09,
                repeated_same_branch_cap=3,
                repeat_expand_free_steps=3,
                repeat_expand_penalty_weight=0.065,
                repeat_expand_family_penalty_weight=0.12,
                repeat_expand_override_margin=0.08,
                enable_low_marginal_gain_family_cooldown=True,
                low_marginal_gain_window_size=3,
                low_marginal_gain_min_threshold=0.015,
                low_marginal_gain_consecutive_family_trigger=4,
                low_marginal_gain_cooldown_steps=2,
                low_marginal_gain_penalty_strength=0.14,
                low_marginal_gain_override_margin=0.12,
                low_marginal_gain_override_top_support_min=0.74,
                low_marginal_gain_answer_group_aware=True,
                low_marginal_gain_hard_block_ablation=False,
                monopolization_margin_requirement=0.11,
                answer_group_distinctness_bonus=0.12,
                duplicate_answer_group_penalty=0.08,
                min_followup_steps_for_preserved_alternative=2,
                alternative_maturity_window=5,
                protected_alternative_target_alignment_min=0.48,
                method_name="broad_diversity_aggregation_strong_v1_anti_collapse_repeat_expansion_low_marginal_gain_cooldown_v1",
            )
        )
        specs["broad_diversity_aggregation_strong_v1_anti_collapse_repeat_expansion_low_marginal_gain_hard_block_ablation_v1"] = (
            GlobalDiversityAggregationController(
                generator_factory(),
                scorer,
                budget,
                max_branches=4,
                min_branch_expansions=1,
                diversity_weight=0.40,
                duplicate_penalty=0.15,
                unknown_answer_bonus=0.08,
                answer_support_weight=0.55,
                value_weight=0.45,
                commit_support_threshold=0.72,
                commit_delay_min_actions=4,
                enable_early_answer_group_preservation=True,
                early_preservation_action_window=5,
                early_preservation_min_plausible_continuation=0.46,
                early_preservation_target_alignment_min=0.34,
                early_preservation_required_group_gap=0.18,
                early_preservation_challenger_hold_steps=2,
                enable_anti_collapse_answer_group_refinement=True,
                anti_collapse_early_window=6,
                repeated_same_branch_penalty=0.09,
                repeated_same_branch_cap=3,
                repeat_expand_free_steps=3,
                repeat_expand_penalty_weight=0.065,
                repeat_expand_family_penalty_weight=0.12,
                repeat_expand_override_margin=0.08,
                enable_low_marginal_gain_family_cooldown=True,
                low_marginal_gain_window_size=3,
                low_marginal_gain_min_threshold=0.015,
                low_marginal_gain_consecutive_family_trigger=4,
                low_marginal_gain_cooldown_steps=2,
                low_marginal_gain_penalty_strength=0.14,
                low_marginal_gain_override_margin=0.12,
                low_marginal_gain_override_top_support_min=0.74,
                low_marginal_gain_answer_group_aware=True,
                low_marginal_gain_hard_block_ablation=True,
                monopolization_margin_requirement=0.11,
                answer_group_distinctness_bonus=0.12,
                duplicate_answer_group_penalty=0.08,
                min_followup_steps_for_preserved_alternative=2,
                alternative_maturity_window=5,
                protected_alternative_target_alignment_min=0.48,
                method_name="broad_diversity_aggregation_strong_v1_anti_collapse_repeat_expansion_low_marginal_gain_hard_block_ablation_v1",
            )
        )
        specs["broad_diversity_aggregation_strong_v1_anti_collapse_width_depth_challenger_guard_v1"] = (
            GlobalDiversityAggregationController(
                generator_factory(),
                scorer,
                budget,
                max_branches=4,
                min_branch_expansions=1,
                diversity_weight=0.40,
                duplicate_penalty=0.15,
                unknown_answer_bonus=0.08,
                answer_support_weight=0.55,
                value_weight=0.45,
                commit_support_threshold=0.72,
                commit_delay_min_actions=4,
                enable_early_answer_group_preservation=True,
                early_preservation_action_window=5,
                early_preservation_min_plausible_continuation=0.46,
                early_preservation_target_alignment_min=0.34,
                early_preservation_required_group_gap=0.18,
                early_preservation_challenger_hold_steps=2,
                enable_anti_collapse_answer_group_refinement=True,
                anti_collapse_early_window=6,
                repeated_same_branch_penalty=0.09,
                repeated_same_branch_cap=3,
                repeat_expand_free_steps=3,
                repeat_expand_penalty_weight=0.065,
                repeat_expand_family_penalty_weight=0.12,
                repeat_expand_override_margin=0.08,
                monopolization_margin_requirement=0.11,
                answer_group_distinctness_bonus=0.12,
                duplicate_answer_group_penalty=0.08,
                min_followup_steps_for_preserved_alternative=2,
                alternative_maturity_window=5,
                protected_alternative_target_alignment_min=0.48,
                enable_width_depth_allocation_guard=True,
                width_depth_repeat_family_trigger=2,
                width_depth_min_actions=3,
                width_depth_challenger_maturation_min_expands=2,
                width_depth_min_relative_continuation=0.78,
                enable_uncertainty_triggered_verify=True,
                uncertainty_verify_priority_margin=0.045,
                uncertainty_verify_max_steps=2,
                method_name="broad_diversity_aggregation_strong_v1_anti_collapse_width_depth_challenger_guard_v1",
            )
        )
        specs["broad_diversity_aggregation_strong_v1_anti_collapse_near_miss_correction_gate_v1"] = (
            GlobalDiversityAggregationController(
                generator_factory(),
                scorer,
                budget,
                max_branches=4,
                min_branch_expansions=1,
                diversity_weight=0.40,
                duplicate_penalty=0.15,
                unknown_answer_bonus=0.08,
                answer_support_weight=0.55,
                value_weight=0.45,
                commit_support_threshold=0.72,
                commit_delay_min_actions=4,
                enable_early_answer_group_preservation=True,
                early_preservation_action_window=5,
                early_preservation_min_plausible_continuation=0.46,
                early_preservation_target_alignment_min=0.34,
                early_preservation_required_group_gap=0.18,
                early_preservation_challenger_hold_steps=2,
                enable_anti_collapse_answer_group_refinement=True,
                anti_collapse_early_window=6,
                repeated_same_branch_penalty=0.09,
                repeated_same_branch_cap=3,
                repeat_expand_free_steps=3,
                repeat_expand_penalty_weight=0.065,
                repeat_expand_family_penalty_weight=0.12,
                repeat_expand_override_margin=0.08,
                monopolization_margin_requirement=0.11,
                answer_group_distinctness_bonus=0.12,
                duplicate_answer_group_penalty=0.08,
                min_followup_steps_for_preserved_alternative=2,
                alternative_maturity_window=5,
                protected_alternative_target_alignment_min=0.48,
                enable_near_miss_correction_gate=True,
                near_miss_correction_numeric_gap=3.0,
                near_miss_correction_min_actions=4,
                near_miss_correction_max_steps=2,
                near_miss_correction_repeat_family_trigger=5,
                near_miss_correction_min_top_support=0.56,
                enable_uncertainty_triggered_verify=True,
                uncertainty_verify_priority_margin=0.045,
                uncertainty_verify_max_steps=2,
                method_name="broad_diversity_aggregation_strong_v1_anti_collapse_near_miss_correction_gate_v1",
            )
        )
        specs[
            "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_coverage_forced_v1"
        ] = GlobalDiversityAggregationController(
            generator_factory(),
            scorer,
            budget,
            max_branches=4,
            min_branch_expansions=1,
            diversity_weight=0.40,
            duplicate_penalty=0.15,
            unknown_answer_bonus=0.08,
            answer_support_weight=0.55,
            value_weight=0.45,
            commit_support_threshold=0.72,
            commit_delay_min_actions=4,
            enable_early_answer_group_preservation=True,
            early_preservation_action_window=5,
            early_preservation_min_plausible_continuation=0.46,
            early_preservation_target_alignment_min=0.34,
            early_preservation_required_group_gap=0.18,
            early_preservation_challenger_hold_steps=2,
            enable_anti_collapse_answer_group_refinement=True,
            anti_collapse_early_window=6,
            repeated_same_branch_penalty=0.09,
            repeated_same_branch_cap=3,
            repeat_expand_free_steps=3,
            repeat_expand_penalty_weight=0.065,
            repeat_expand_family_penalty_weight=0.12,
            repeat_expand_override_margin=0.08,
            monopolization_margin_requirement=0.11,
            answer_group_distinctness_bonus=0.12,
            duplicate_answer_group_penalty=0.08,
            min_followup_steps_for_preserved_alternative=2,
            alternative_maturity_window=5,
            protected_alternative_target_alignment_min=0.48,
            enable_hard_early_root_depth2_coverage_v1=True,
            hard_early_coverage_min_remaining_actions_to_release=0,
            method_name="broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_coverage_forced_v1",
        )
        specs[
            "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_coverage_forced_v1_low_marginal_gain_cooldown_v1"
        ] = GlobalDiversityAggregationController(
            generator_factory(),
            scorer,
            budget,
            max_branches=4,
            min_branch_expansions=1,
            diversity_weight=0.40,
            duplicate_penalty=0.15,
            unknown_answer_bonus=0.08,
            answer_support_weight=0.55,
            value_weight=0.45,
            commit_support_threshold=0.72,
            commit_delay_min_actions=4,
            enable_early_answer_group_preservation=True,
            early_preservation_action_window=5,
            early_preservation_min_plausible_continuation=0.46,
            early_preservation_target_alignment_min=0.34,
            early_preservation_required_group_gap=0.18,
            early_preservation_challenger_hold_steps=2,
            enable_anti_collapse_answer_group_refinement=True,
            anti_collapse_early_window=6,
            repeated_same_branch_penalty=0.09,
            repeated_same_branch_cap=3,
            repeat_expand_free_steps=3,
            repeat_expand_penalty_weight=0.065,
            repeat_expand_family_penalty_weight=0.12,
            repeat_expand_override_margin=0.08,
            enable_low_marginal_gain_family_cooldown=True,
            low_marginal_gain_window_size=3,
            low_marginal_gain_min_threshold=0.015,
            low_marginal_gain_consecutive_family_trigger=4,
            low_marginal_gain_cooldown_steps=2,
            low_marginal_gain_penalty_strength=0.14,
            low_marginal_gain_override_margin=0.12,
            low_marginal_gain_override_top_support_min=0.74,
            low_marginal_gain_answer_group_aware=True,
            low_marginal_gain_hard_block_ablation=False,
            monopolization_margin_requirement=0.11,
            answer_group_distinctness_bonus=0.12,
            duplicate_answer_group_penalty=0.08,
            min_followup_steps_for_preserved_alternative=2,
            alternative_maturity_window=5,
            protected_alternative_target_alignment_min=0.48,
            enable_hard_early_root_depth2_coverage_v1=True,
            hard_early_coverage_min_remaining_actions_to_release=0,
            method_name="broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_coverage_forced_v1_low_marginal_gain_cooldown_v1",
        )
        specs[
            "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth3_coverage_forced_v1"
        ] = GlobalDiversityAggregationController(
            generator_factory(),
            scorer,
            budget,
            max_branches=4,
            min_branch_expansions=1,
            diversity_weight=0.40,
            duplicate_penalty=0.15,
            unknown_answer_bonus=0.08,
            answer_support_weight=0.55,
            value_weight=0.45,
            commit_support_threshold=0.72,
            commit_delay_min_actions=4,
            enable_early_answer_group_preservation=True,
            early_preservation_action_window=5,
            early_preservation_min_plausible_continuation=0.46,
            early_preservation_target_alignment_min=0.34,
            early_preservation_required_group_gap=0.18,
            early_preservation_challenger_hold_steps=2,
            enable_anti_collapse_answer_group_refinement=True,
            anti_collapse_early_window=6,
            repeated_same_branch_penalty=0.09,
            repeated_same_branch_cap=3,
            repeat_expand_free_steps=3,
            repeat_expand_penalty_weight=0.065,
            repeat_expand_family_penalty_weight=0.12,
            repeat_expand_override_margin=0.08,
            monopolization_margin_requirement=0.11,
            answer_group_distinctness_bonus=0.12,
            duplicate_answer_group_penalty=0.08,
            min_followup_steps_for_preserved_alternative=2,
            alternative_maturity_window=5,
            protected_alternative_target_alignment_min=0.48,
            enable_hard_early_root_depth2_coverage_v1=False,
            hard_early_root_coverage_forced_min_depth=3,
            hard_early_coverage_min_remaining_actions_to_release=0,
            method_name="broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth3_coverage_forced_v1",
        )
        strict_f3_base_cfg: dict[str, Any] = dict(
            max_branches=4,
            min_branch_expansions=1,
            diversity_weight=0.40,
            duplicate_penalty=0.15,
            unknown_answer_bonus=0.08,
            answer_support_weight=0.55,
            value_weight=0.45,
            commit_support_threshold=0.72,
            commit_delay_min_actions=4,
            enable_early_answer_group_preservation=True,
            early_preservation_action_window=5,
            early_preservation_min_plausible_continuation=0.46,
            early_preservation_target_alignment_min=0.34,
            early_preservation_required_group_gap=0.18,
            early_preservation_challenger_hold_steps=2,
            enable_anti_collapse_answer_group_refinement=True,
            anti_collapse_early_window=6,
            repeated_same_branch_penalty=0.09,
            repeated_same_branch_cap=3,
            repeat_expand_free_steps=3,
            repeat_expand_penalty_weight=0.065,
            repeat_expand_family_penalty_weight=0.12,
            repeat_expand_override_margin=0.08,
            monopolization_margin_requirement=0.11,
            answer_group_distinctness_bonus=0.12,
            duplicate_answer_group_penalty=0.08,
            min_followup_steps_for_preserved_alternative=2,
            alternative_maturity_window=5,
            protected_alternative_target_alignment_min=0.48,
            enable_hard_early_root_depth2_coverage_v1=False,
            hard_early_root_coverage_forced_min_depth=3,
            hard_early_coverage_min_remaining_actions_to_release=0,
        )
        strict_f3_no_answer_cfg = dict(strict_f3_base_cfg)
        strict_f3_no_answer_cfg.update({"answer_support_weight": 0.0, "value_weight": 1.0})
        specs["strict_f3_ablation_no_answer_support_aggregation_v1"] = GlobalDiversityAggregationController(
            generator_factory(),
            scorer,
            budget,
            method_name="strict_f3_ablation_no_answer_support_aggregation_v1",
            **strict_f3_no_answer_cfg,
        )
        strict_f3_no_anti_cfg = dict(strict_f3_base_cfg)
        strict_f3_no_anti_cfg.update(
            {"enable_anti_collapse_answer_group_refinement": False, "enable_low_marginal_gain_family_cooldown": False}
        )
        specs["strict_f3_ablation_no_anti_collapse_v1"] = GlobalDiversityAggregationController(
            generator_factory(),
            scorer,
            budget,
            method_name="strict_f3_ablation_no_anti_collapse_v1",
            **strict_f3_no_anti_cfg,
        )
        strict_f3_anti_collapse_weak_cfg = dict(strict_f3_base_cfg)
        strict_f3_anti_collapse_weak_cfg.update(
            {
                "anti_collapse_early_window": 5,
                "repeat_expand_penalty_weight": 0.03,
                "repeat_expand_family_penalty_weight": 0.06,
                "repeated_same_branch_penalty": 0.05,
                "answer_group_distinctness_bonus": 0.07,
                "duplicate_answer_group_penalty": 0.04,
                "enable_low_marginal_gain_family_cooldown": False,
            }
        )
        specs["strict_f3_anti_collapse_weak_v1"] = GlobalDiversityAggregationController(
            generator_factory(),
            scorer,
            budget,
            method_name="strict_f3_anti_collapse_weak_v1",
            **strict_f3_anti_collapse_weak_cfg,
        )
        specs["strict_f3_anti_collapse_default_v1"] = GlobalDiversityAggregationController(
            generator_factory(),
            scorer,
            budget,
            method_name="strict_f3_anti_collapse_default_v1",
            **strict_f3_base_cfg,
        )
        strict_f3_anti_collapse_strong_cfg = dict(strict_f3_base_cfg)
        strict_f3_anti_collapse_strong_cfg.update(
            {
                "anti_collapse_early_window": 8,
                "repeat_expand_penalty_weight": 0.09,
                "repeat_expand_family_penalty_weight": 0.16,
                "repeated_same_branch_penalty": 0.12,
                "answer_group_distinctness_bonus": 0.16,
                "duplicate_answer_group_penalty": 0.12,
                "enable_low_marginal_gain_family_cooldown": True,
                "low_marginal_gain_penalty_strength": 0.18,
            }
        )
        specs["strict_f3_anti_collapse_strong_v1"] = GlobalDiversityAggregationController(
            generator_factory(),
            scorer,
            budget,
            method_name="strict_f3_anti_collapse_strong_v1",
            **strict_f3_anti_collapse_strong_cfg,
        )
        strict_f3_anti_collapse_conditional_cfg = dict(strict_f3_base_cfg)
        strict_f3_anti_collapse_conditional_cfg.update(
            {
                "enable_conditional_anti_collapse_activation": True,
                "conditional_anti_collapse_min_actions": 2,
                "conditional_anti_collapse_max_family_share_trigger": 0.60,
                "conditional_anti_collapse_max_active_groups_for_low_coverage": 1,
                "conditional_anti_collapse_min_consecutive_family_expands": 3,
            }
        )
        specs["strict_f3_anti_collapse_conditional_v1"] = GlobalDiversityAggregationController(
            generator_factory(),
            scorer,
            budget,
            method_name="strict_f3_anti_collapse_conditional_v1",
            **strict_f3_anti_collapse_conditional_cfg,
        )
        strict_f3_no_repeat_cfg = dict(strict_f3_base_cfg)
        strict_f3_no_repeat_cfg.update(
            {
                "repeat_expand_penalty_weight": 0.0,
                "repeat_expand_family_penalty_weight": 0.0,
                "repeated_same_branch_penalty": 0.0,
                "enable_low_marginal_gain_family_cooldown": False,
            }
        )
        specs["strict_f3_ablation_no_repeat_expansion_control_v1"] = GlobalDiversityAggregationController(
            generator_factory(),
            scorer,
            budget,
            method_name="strict_f3_ablation_no_repeat_expansion_control_v1",
            **strict_f3_no_repeat_cfg,
        )
        strict_f3_upstream_cfg = dict(strict_f3_base_cfg)
        strict_f3_upstream_cfg.update(
            {"enable_anti_collapse_answer_group_refinement": False, "enable_low_marginal_gain_family_cooldown": False}
        )
        specs["strict_f3_ablation_upstream_only_core_v1"] = GlobalDiversityAggregationController(
            generator_factory(),
            scorer,
            budget,
            method_name="strict_f3_ablation_upstream_only_core_v1",
            **strict_f3_upstream_cfg,
        )
        strict_f3_conditional_early_cap_cfg = dict(strict_f3_base_cfg)
        strict_f3_conditional_early_cap_cfg.update(
            {
                "enable_hard_max_family_expansions_cap": True,
                "hard_max_family_expansions_base_cap": 2,
                "hard_max_family_expansions_relax_cap": 6,
                "hard_max_family_expansions_relax_cap_high": 6,
                "hard_max_family_expansions_conditional_early_window_actions": 6,
                "hard_max_family_expansions_conditional_risk_family_share_trigger": 0.60,
                "hard_max_family_expansions_conditional_risk_consecutive_run_trigger": 3,
                "hard_max_family_expansions_conditional_min_rival_maturity_expansions": 2,
            }
        )
        specs["strict_f3_conditional_early_risk_cap_k2_v1"] = GlobalDiversityAggregationController(
            generator_factory(),
            scorer,
            budget,
            hard_max_family_expansions_relax_mode="conditional_early_risk_cap",
            method_name="strict_f3_conditional_early_risk_cap_k2_v1",
            **strict_f3_conditional_early_cap_cfg,
        )
        specs["strict_f3_conditional_early_risk_cap_k2_rival_maturation_v1"] = GlobalDiversityAggregationController(
            generator_factory(),
            scorer,
            budget,
            hard_max_family_expansions_relax_mode="conditional_early_risk_cap_with_rival_maturation",
            method_name="strict_f3_conditional_early_risk_cap_k2_rival_maturation_v1",
            **strict_f3_conditional_early_cap_cfg,
        )
        strict_f3_conditional_sensitivity: list[tuple[str, dict[str, Any]]] = [
            (
                "strict_f3_conditional_early_risk_cap_k2_window5_v1",
                {"hard_max_family_expansions_conditional_early_window_actions": 5},
            ),
            (
                "strict_f3_conditional_early_risk_cap_k2_window7_v1",
                {"hard_max_family_expansions_conditional_early_window_actions": 7},
            ),
            (
                "strict_f3_conditional_early_risk_cap_k2_share55_v1",
                {"hard_max_family_expansions_conditional_risk_family_share_trigger": 0.55},
            ),
            (
                "strict_f3_conditional_early_risk_cap_k2_share65_v1",
                {"hard_max_family_expansions_conditional_risk_family_share_trigger": 0.65},
            ),
            (
                "strict_f3_conditional_early_risk_cap_k3_v1",
                {"hard_max_family_expansions_base_cap": 3},
            ),
        ]
        for name, overrides in strict_f3_conditional_sensitivity:
            cfg = dict(strict_f3_conditional_early_cap_cfg)
            cfg.update(overrides)
            specs[name] = GlobalDiversityAggregationController(
                generator_factory(),
                scorer,
                budget,
                hard_max_family_expansions_relax_mode="conditional_early_risk_cap",
                method_name=name,
                **cfg,
            )
        specs[
            "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth3_coverage_forced_v1_low_marginal_gain_cooldown_v1"
        ] = GlobalDiversityAggregationController(
            generator_factory(),
            scorer,
            budget,
            max_branches=4,
            min_branch_expansions=1,
            diversity_weight=0.40,
            duplicate_penalty=0.15,
            unknown_answer_bonus=0.08,
            answer_support_weight=0.55,
            value_weight=0.45,
            commit_support_threshold=0.72,
            commit_delay_min_actions=4,
            enable_early_answer_group_preservation=True,
            early_preservation_action_window=5,
            early_preservation_min_plausible_continuation=0.46,
            early_preservation_target_alignment_min=0.34,
            early_preservation_required_group_gap=0.18,
            early_preservation_challenger_hold_steps=2,
            enable_anti_collapse_answer_group_refinement=True,
            anti_collapse_early_window=6,
            repeated_same_branch_penalty=0.09,
            repeated_same_branch_cap=3,
            repeat_expand_free_steps=3,
            repeat_expand_penalty_weight=0.065,
            repeat_expand_family_penalty_weight=0.12,
            repeat_expand_override_margin=0.08,
            enable_low_marginal_gain_family_cooldown=True,
            low_marginal_gain_window_size=3,
            low_marginal_gain_min_threshold=0.015,
            low_marginal_gain_consecutive_family_trigger=4,
            low_marginal_gain_cooldown_steps=2,
            low_marginal_gain_penalty_strength=0.14,
            low_marginal_gain_override_margin=0.12,
            low_marginal_gain_override_top_support_min=0.74,
            low_marginal_gain_answer_group_aware=True,
            low_marginal_gain_hard_block_ablation=False,
            monopolization_margin_requirement=0.11,
            answer_group_distinctness_bonus=0.12,
            duplicate_answer_group_penalty=0.08,
            min_followup_steps_for_preserved_alternative=2,
            alternative_maturity_window=5,
            protected_alternative_target_alignment_min=0.48,
            enable_hard_early_root_depth2_coverage_v1=False,
            hard_early_root_coverage_forced_min_depth=3,
            hard_early_coverage_min_remaining_actions_to_release=0,
            method_name="broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth3_coverage_forced_v1_low_marginal_gain_cooldown_v1",
        )
        specs[
            "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_then_conditional_depth3_v1"
        ] = GlobalDiversityAggregationController(
            generator_factory(),
            scorer,
            budget,
            max_branches=4,
            min_branch_expansions=1,
            diversity_weight=0.40,
            duplicate_penalty=0.15,
            unknown_answer_bonus=0.08,
            answer_support_weight=0.55,
            value_weight=0.45,
            commit_support_threshold=0.72,
            commit_delay_min_actions=4,
            enable_early_answer_group_preservation=True,
            early_preservation_action_window=5,
            early_preservation_min_plausible_continuation=0.46,
            early_preservation_target_alignment_min=0.34,
            early_preservation_required_group_gap=0.18,
            early_preservation_challenger_hold_steps=2,
            enable_anti_collapse_answer_group_refinement=True,
            anti_collapse_early_window=6,
            repeated_same_branch_penalty=0.09,
            repeated_same_branch_cap=3,
            repeat_expand_free_steps=3,
            repeat_expand_penalty_weight=0.065,
            repeat_expand_family_penalty_weight=0.12,
            repeat_expand_override_margin=0.08,
            monopolization_margin_requirement=0.11,
            answer_group_distinctness_bonus=0.12,
            duplicate_answer_group_penalty=0.08,
            min_followup_steps_for_preserved_alternative=2,
            alternative_maturity_window=5,
            protected_alternative_target_alignment_min=0.48,
            enable_hard_early_root_depth2_coverage_v1=False,
            hard_early_root_coverage_forced_min_depth=2,
            hard_early_coverage_min_remaining_actions_to_release=0,
            enable_hard_early_root_depth2_then_conditional_depth3_v1=True,
            method_name="broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_then_conditional_depth3_v1",
        )
        specs[
            "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_then_conditional_depth3_v1_low_marginal_gain_cooldown_v1"
        ] = GlobalDiversityAggregationController(
            generator_factory(),
            scorer,
            budget,
            max_branches=4,
            min_branch_expansions=1,
            diversity_weight=0.40,
            duplicate_penalty=0.15,
            unknown_answer_bonus=0.08,
            answer_support_weight=0.55,
            value_weight=0.45,
            commit_support_threshold=0.72,
            commit_delay_min_actions=4,
            enable_early_answer_group_preservation=True,
            early_preservation_action_window=5,
            early_preservation_min_plausible_continuation=0.46,
            early_preservation_target_alignment_min=0.34,
            early_preservation_required_group_gap=0.18,
            early_preservation_challenger_hold_steps=2,
            enable_anti_collapse_answer_group_refinement=True,
            anti_collapse_early_window=6,
            repeated_same_branch_penalty=0.09,
            repeated_same_branch_cap=3,
            repeat_expand_free_steps=3,
            repeat_expand_penalty_weight=0.065,
            repeat_expand_family_penalty_weight=0.12,
            repeat_expand_override_margin=0.08,
            enable_low_marginal_gain_family_cooldown=True,
            low_marginal_gain_window_size=3,
            low_marginal_gain_min_threshold=0.015,
            low_marginal_gain_consecutive_family_trigger=4,
            low_marginal_gain_cooldown_steps=2,
            low_marginal_gain_penalty_strength=0.14,
            low_marginal_gain_override_margin=0.12,
            low_marginal_gain_override_top_support_min=0.74,
            low_marginal_gain_answer_group_aware=True,
            low_marginal_gain_hard_block_ablation=False,
            monopolization_margin_requirement=0.11,
            answer_group_distinctness_bonus=0.12,
            duplicate_answer_group_penalty=0.08,
            min_followup_steps_for_preserved_alternative=2,
            alternative_maturity_window=5,
            protected_alternative_target_alignment_min=0.48,
            enable_hard_early_root_depth2_coverage_v1=False,
            hard_early_root_coverage_forced_min_depth=2,
            hard_early_coverage_min_remaining_actions_to_release=0,
            enable_hard_early_root_depth2_then_conditional_depth3_v1=True,
            method_name="broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_then_conditional_depth3_v1_low_marginal_gain_cooldown_v1",
        )
        strict_gate1_base = "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_then_gate_v1_optimistic_collapse_first"
        strict_gate1_common: dict[str, Any] = dict(
            max_branches=4,
            min_branch_expansions=1,
            diversity_weight=0.40,
            duplicate_penalty=0.15,
            unknown_answer_bonus=0.08,
            answer_support_weight=0.55,
            value_weight=0.45,
            commit_support_threshold=0.72,
            commit_delay_min_actions=4,
            enable_early_answer_group_preservation=True,
            early_preservation_action_window=5,
            early_preservation_min_plausible_continuation=0.46,
            early_preservation_target_alignment_min=0.34,
            early_preservation_required_group_gap=0.18,
            early_preservation_challenger_hold_steps=2,
            enable_anti_collapse_answer_group_refinement=True,
            anti_collapse_early_window=6,
            repeated_same_branch_penalty=0.09,
            repeated_same_branch_cap=3,
            repeat_expand_free_steps=3,
            repeat_expand_penalty_weight=0.065,
            repeat_expand_family_penalty_weight=0.12,
            repeat_expand_override_margin=0.08,
            enable_low_marginal_gain_family_cooldown=True,
            low_marginal_gain_window_size=3,
            low_marginal_gain_min_threshold=0.015,
            low_marginal_gain_consecutive_family_trigger=4,
            low_marginal_gain_cooldown_steps=2,
            low_marginal_gain_penalty_strength=0.14,
            low_marginal_gain_override_margin=0.12,
            low_marginal_gain_override_top_support_min=0.74,
            low_marginal_gain_answer_group_aware=True,
            low_marginal_gain_hard_block_ablation=False,
            monopolization_margin_requirement=0.11,
            answer_group_distinctness_bonus=0.12,
            duplicate_answer_group_penalty=0.08,
            min_followup_steps_for_preserved_alternative=2,
            alternative_maturity_window=5,
            protected_alternative_target_alignment_min=0.48,
            enable_hard_early_root_depth2_coverage_v1=False,
            hard_early_root_coverage_forced_min_depth=2,
            hard_early_coverage_min_remaining_actions_to_release=0,
            enable_hard_early_root_depth2_then_conditional_depth3_v1=True,
            enable_hard_max_family_expansions_cap=True,
            hard_max_family_expansions_base_cap=6,
            hard_max_family_expansions_relax_cap=8,
            hard_max_family_expansions_relax_cap_high=10,
        )
        for relax_mode in (
            "fixed_k6_control",
            "relax_on_cross_family_coverage_complete",
            "relax_on_low_marginal_gain_absence_false",
            "relax_on_multi_family_maturity",
            "relax_on_high_confidence_incumbent_but_no_challenger_gap",
        ):
            name = f"{strict_gate1_base}_hard_max_family_expansions_cap_k6_v1_{relax_mode}"
            specs[name] = GlobalDiversityAggregationController(
                generator_factory(),
                scorer,
                budget,
                hard_max_family_expansions_relax_mode=relax_mode,
                method_name=name,
                **strict_gate1_common,
            )
        # Canonical component-ablation variants for strict_gate1_cap_k6.
        no_answer_support_cfg = dict(strict_gate1_common)
        no_answer_support_cfg.update(
            {
                "answer_support_weight": 0.0,
                "value_weight": 1.0,
            }
        )
        specs[
            "strict_gate1_cap_k6_ablation_no_answer_support_v1"
        ] = GlobalDiversityAggregationController(
            generator_factory(),
            scorer,
            budget,
            hard_max_family_expansions_relax_mode="fixed_k6_control",
            method_name="strict_gate1_cap_k6_ablation_no_answer_support_v1",
            **no_answer_support_cfg,
        )
        no_anti_cfg = dict(strict_gate1_common)
        no_anti_cfg.update(
            {
                "enable_anti_collapse_answer_group_refinement": False,
                "enable_low_marginal_gain_family_cooldown": False,
            }
        )
        specs[
            "strict_gate1_cap_k6_ablation_no_anti_collapse_v1"
        ] = GlobalDiversityAggregationController(
            generator_factory(),
            scorer,
            budget,
            hard_max_family_expansions_relax_mode="fixed_k6_control",
            method_name="strict_gate1_cap_k6_ablation_no_anti_collapse_v1",
            **no_anti_cfg,
        )
        no_repeat_cfg = dict(strict_gate1_common)
        no_repeat_cfg.update(
            {
                "repeat_expand_penalty_weight": 0.0,
                "repeat_expand_family_penalty_weight": 0.0,
                "repeated_same_branch_penalty": 0.0,
                "enable_low_marginal_gain_family_cooldown": False,
            }
        )
        specs[
            "strict_gate1_cap_k6_ablation_no_repeat_expansion_control_v1"
        ] = GlobalDiversityAggregationController(
            generator_factory(),
            scorer,
            budget,
            hard_max_family_expansions_relax_mode="fixed_k6_control",
            method_name="strict_gate1_cap_k6_ablation_no_repeat_expansion_control_v1",
            **no_repeat_cfg,
        )
        alloc_only_cfg = dict(strict_gate1_common)
        alloc_only_cfg.update(
            {
                "enable_anti_collapse_answer_group_refinement": False,
                "enable_low_marginal_gain_family_cooldown": False,
            }
        )
        specs[
            "strict_gate1_cap_k6_ablation_allocation_only_core_v1"
        ] = GlobalDiversityAggregationController(
            generator_factory(),
            scorer,
            budget,
            hard_max_family_expansions_relax_mode="fixed_k6_control",
            method_name="strict_gate1_cap_k6_ablation_allocation_only_core_v1",
            **alloc_only_cfg,
        )
    if include_marginal_coverage_diversity_methods:
        specs["marginal_coverage_diversity_v1"] = GlobalDiversityAggregationController(
            generator_factory(),
            scorer,
            budget,
            max_branches=4,
            min_branch_expansions=1,
            diversity_weight=0.30,
            duplicate_penalty=0.12,
            unknown_answer_bonus=0.05,
            use_marginal_coverage_overlap=True,
            coverage_weight=0.24,
            overlap_weight=0.16,
            answer_support_weight=0.46,
            value_weight=0.54,
            commit_support_threshold=0.66,
            commit_delay_min_actions=3,
            method_name="marginal_coverage_diversity_v1",
        )
    if include_duplicate_aware_aggregation_commit_methods:
        specs["duplicate_aware_aggregation_commit_v1"] = GlobalDiversityAggregationController(
            generator_factory(),
            scorer,
            budget,
            max_branches=4,
            min_branch_expansions=1,
            diversity_weight=0.31,
            duplicate_penalty=0.12,
            unknown_answer_bonus=0.05,
            use_marginal_coverage_overlap=True,
            coverage_weight=0.22,
            overlap_weight=0.15,
            use_duplicate_aware_aggregation=True,
            duplicate_discount_strength=0.75,
            duplicate_discount_floor=0.22,
            support_quality_weight=0.40,
            use_answer_group_commit_margin=True,
            commit_margin_threshold=0.17,
            commit_top_support_threshold=0.61,
            commit_readiness_threshold=0.57,
            continue_one_step_value_threshold=0.64,
            min_actions_before_commit_check=3,
            answer_support_weight=0.48,
            value_weight=0.52,
            commit_support_threshold=0.66,
            commit_delay_min_actions=3,
            method_name="duplicate_aware_aggregation_commit_v1",
        )
    return specs


def evaluate_strategies_on_examples(
    examples: list[PilotExample], strategies: dict[str, Any]
) -> tuple[dict[str, dict[str, float]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    by_strategy: dict[str, list[dict[str, Any]]] = {k: [] for k in strategies}
    for ex in examples:
        for name, controller in strategies.items():
            r = controller.run(ex.question, ex.answer)
            row = {
                "example_id": ex.example_id,
                "strategy": name,
                "is_correct": r.is_correct,
                "actions_used": r.actions_used,
                "expansions": r.expansions,
                "verifications": r.verifications,
                "budget_exhausted": r.budget_exhausted,
                "metadata": r.metadata,
            }
            rows.append(row)
            by_strategy[name].append(row)

    metrics: dict[str, dict[str, float]] = {}
    for name, srows in by_strategy.items():
        n = max(1, len(srows))
        metrics[name] = {
            "n_examples": n,
            "accuracy": sum(1 for r in srows if r["is_correct"]) / n,
            "avg_actions": sum(float(r["actions_used"]) for r in srows) / n,
            "avg_expansions": sum(float(r["expansions"]) for r in srows) / n,
            "avg_verifications": sum(float(r["verifications"]) for r in srows) / n,
            "budget_exhaustion_rate": sum(1 for r in srows if r["budget_exhausted"]) / n,
        }
    return metrics, rows


def adaptive_anti_collapse_stats(rows: list[dict[str, Any]], strategy_prefix: str = "adaptive_min_expand_") -> dict[str, dict[str, float]]:
    """Aggregate prune vs forced-expand signals from AdaptiveController metadata."""
    by_k: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        s = str(row["strategy"])
        if not s.startswith(strategy_prefix):
            continue
        k = s[len(strategy_prefix) :] if s.startswith(strategy_prefix) else s
        by_k.setdefault(k, []).append(row)

    out: dict[str, dict[str, float]] = {}
    for k, krows in by_k.items():
        prune_fracs: list[float] = []
        forced_fracs: list[float] = []
        trace_lens: list[float] = []
        for row in krows:
            meta = row.get("metadata") or {}
            trace = meta.get("action_trace") or []
            if not trace:
                continue
            n = len(trace)
            n_prune = sum(1 for t in trace if t.get("action") == "prune")
            n_forced = sum(1 for t in trace if t.get("forced_expand"))
            prune_fracs.append(n_prune / n)
            forced_fracs.append(n_forced / n)
            trace_lens.append(float(n))
        m = max(1, len(krows))
        out[k] = {
            "n": float(len(krows)),
            "mean_prune_share_of_actions": sum(prune_fracs) / max(1, len(prune_fracs)) if prune_fracs else 0.0,
            "mean_forced_expand_share": sum(forced_fracs) / max(1, len(forced_fracs)) if forced_fracs else 0.0,
            "mean_action_trace_length": sum(trace_lens) / max(1, len(trace_lens)) if trace_lens else 0.0,
            "examples_with_trace": float(len(prune_fracs)),
        }
    return out
