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
    GreedyController,
    ProgramOfThoughtController,
    S1BudgetForcingController,
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
