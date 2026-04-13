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
    VerifierGuidedSearchController,
)
from experiments.data import PilotExample, extract_final_answer
from experiments.hf_datasets import resolve_dataset_spec, sample_hf_examples
from experiments.scoring import ScoreConfig, SimpleBranchScorer
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
) -> dict[str, Any]:
    scorer = SimpleBranchScorer(ScoreConfig())
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
    specs["program_of_thought"] = ProgramOfThoughtController(
        generator_factory(),
        scorer,
        budget,
        method_name="program_of_thought",
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
