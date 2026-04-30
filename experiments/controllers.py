"""Controller implementations for the lightweight GSM8K pilot."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from collections import Counter, defaultdict
import math
import re
from typing import Any, Callable, Protocol
import json

import numpy as np
from sklearn.linear_model import LogisticRegression

from experiments.branching import BranchState
from experiments.objective_function_stack import compute_process_quality, compute_target_completion
from experiments.problem_type_utils import classify_problem_type
from experiments.prm_partial_scorer import PartialBranchScorer
from experiments.scoring import SimpleBranchScorer
from experiments.typed_strategy_prompts import TypedStrategyPrompt, get_typed_strategy_prompts
from experiments.reasoning_diversity import compute_reasoning_diversity_components, reasoning_signature
from experiments.semantic_family_clustering import compute_branching_necessity_score, root_semantic_family_snapshot
from experiments.answer_grouped_outcome_verifier import (
    CohereOutcomeVerifier,
    DeterministicMockOutcomeVerifier,
    build_candidates_from_dr_v2_metadata,
    select_answer_group_with_outcome_verifier,
)
from experiments.prm_step_verifier_rerank import (
    CohereStepVerifier,
    DeterministicMockStepVerifier,
    build_prm_candidates_from_dr_v2_metadata,
    select_answer_group_with_prm_step_verifier,
)
from experiments.verifiers import CandidateVerifier
from scripts.direct_reserve_learned_override_utils import (
    DEFAULT_MODEL_TYPE as DIRECT_RESERVE_LEARNED_OVERRIDE_DEFAULT_MODEL,
    build_runtime_answer_group_candidates,
    select_learned_override,
)


class BranchScorer(Protocol):
    def score_branch(self, branch: BranchState) -> float: ...

    def pick_best(self, branches: list[BranchState]) -> BranchState | None: ...


class EarlyRejectPolicy(Protocol):
    def should_reject(self, *, score: float, branch: BranchState, expansions_so_far: int) -> bool: ...



class BranchGenerator(Protocol):
    def init_branch(self, branch_id: str) -> BranchState: ...

    def expand(self, branch: BranchState, question: str, gold_answer: str) -> Any: ...

    def verify(self, branch: BranchState, question: str) -> Any: ...

    @staticmethod
    def prune(branch: BranchState) -> Any: ...


CASE_SPLIT_LABELS: tuple[str, ...] = (
    "counting_combinatorics",
    "case_split",
    "multi_step_arithmetic",
    "ratio_percent",
    "comparison",
    "unit_conversion",
    "algebra_like",
    "unknown",
)


def classify_question_shape(question: str) -> str:
    """Lightweight transparent detector for case-split / counting-ish question shapes."""
    q = (question or "").strip().lower()
    if not q:
        return "unknown"

    counting_terms = (
        "how many",
        "ways",
        "different ways",
        "arrange",
        "choose",
        "combination",
        "permutation",
        "possible",
        "number of",
    )
    case_split_terms = ("case", "if", "either", " or ", "at least", "at most", "exactly")
    ratio_terms = ("percent", "%", "ratio", "proportion", "fraction")
    comparison_terms = ("greater than", "less than", "more than", "fewer than", "compare", "difference between")
    unit_terms = ("km", "meter", "meters", "cm", "kg", "gram", "grams", "minute", "hour", "mile", "inch", "feet")
    algebra_terms = ("solve for", "equation", "variable", "let x", "find x", "quadratic")

    if any(t in q for t in counting_terms):
        return "counting_combinatorics"
    if any(t in q for t in case_split_terms):
        return "case_split"
    if any(t in q for t in ratio_terms):
        return "ratio_percent"
    if any(t in q for t in comparison_terms):
        return "comparison"
    if any(t in q for t in unit_terms):
        return "unit_conversion"
    if any(t in q for t in algebra_terms):
        return "algebra_like"
    if re.search(r"\d", q) and ((" then " in q) or (" after " in q) or (" total " in q)):
        return "multi_step_arithmetic"
    return "unknown"


@dataclass
class MethodResult:
    """Per-method result for one example."""

    method: str
    prediction: str | None
    is_correct: bool
    actions_used: int
    expansions: int
    verifications: int
    avg_surviving_branches: float
    budget_exhausted: bool
    metadata: dict[str, Any]


class BaseController:
    def __init__(self, generator: BranchGenerator, scorer: BranchScorer, max_actions_per_problem: int) -> None:
        self.generator = generator
        self.scorer = scorer
        self.max_actions = max_actions_per_problem

    @staticmethod
    def _answers_match(prediction: str | None, gold_answer: str) -> bool:
        if prediction is None:
            return False
        pred = _normalize_answer(prediction)
        gold = _normalize_answer(gold_answer)
        return pred == gold

    def run(self, question: str, gold_answer: str) -> MethodResult:
        raise NotImplementedError


class GreedyController(BaseController):
    def run(self, question: str, gold_answer: str) -> MethodResult:
        branch = self.generator.init_branch("greedy_0")
        actions = expansions = verifications = 0
        surviving_trace: list[int] = []

        while actions < self.max_actions and not branch.is_done:
            self.generator.expand(branch, question, gold_answer)
            actions += 1
            expansions += 1
            surviving_trace.append(1)

        prediction = branch.predicted_answer
        return MethodResult(
            method="greedy_single_path",
            prediction=prediction,
            is_correct=self._answers_match(prediction, gold_answer),
            actions_used=actions,
            expansions=expansions,
            verifications=verifications,
            avg_surviving_branches=sum(surviving_trace) / max(1, len(surviving_trace)),
            budget_exhausted=actions >= self.max_actions and not branch.is_done,
            metadata={"final_score": self.scorer.score_branch(branch)},
        )


class BestOfNController(BaseController):
    def __init__(self, generator: BranchGenerator, scorer: BranchScorer, max_actions_per_problem: int, n_candidates: int) -> None:
        super().__init__(generator, scorer, max_actions_per_problem)
        self.n_candidates = n_candidates

    def run(self, question: str, gold_answer: str) -> MethodResult:
        actions = expansions = verifications = 0
        branches = [self.generator.init_branch(f"bon_{i}") for i in range(self.n_candidates)]
        surviving_trace: list[int] = []

        for branch in branches:
            while actions < self.max_actions and not branch.is_done:
                self.generator.expand(branch, question, gold_answer)
                actions += 1
                expansions += 1
                surviving_trace.append(sum(1 for b in branches if not b.is_done and not b.is_pruned))

            if actions < self.max_actions:
                self.generator.verify(branch, question)
                actions += 1
                verifications += 1

        best_branch = self.scorer.pick_best(branches)
        prediction = best_branch.predicted_answer if best_branch else None
        return MethodResult(
            method="best_of_n",
            prediction=prediction,
            is_correct=self._answers_match(prediction, gold_answer),
            actions_used=actions,
            expansions=expansions,
            verifications=verifications,
            avg_surviving_branches=sum(surviving_trace) / max(1, len(surviving_trace)),
            budget_exhausted=actions >= self.max_actions,
            metadata={"n_candidates": self.n_candidates},
        )


class BeamController(BaseController):
    def __init__(self, generator: BranchGenerator, scorer: BranchScorer, max_actions_per_problem: int, width: int) -> None:
        super().__init__(generator, scorer, max_actions_per_problem)
        self.width = width

    def run(self, question: str, gold_answer: str) -> MethodResult:
        actions = expansions = verifications = 0
        surviving_trace: list[int] = []
        branches = [self.generator.init_branch(f"beam_{i}") for i in range(self.width)]

        while actions < self.max_actions and any(not b.is_done and not b.is_pruned for b in branches):
            for branch in list(branches):
                if actions >= self.max_actions:
                    break
                if branch.is_done or branch.is_pruned:
                    continue
                self.generator.expand(branch, question, gold_answer)
                actions += 1
                expansions += 1

            scored = sorted((b for b in branches if not b.is_pruned), key=self.scorer.score_branch, reverse=True)
            keep_ids = {b.branch_id for b in scored[: self.width]}
            for b in branches:
                if b.branch_id not in keep_ids and not b.is_pruned:
                    self.generator.prune(b)

            branches = [b for b in branches if not b.is_pruned]
            surviving_trace.append(len(branches))

            while len(branches) < self.width and actions < self.max_actions:
                branches.append(self.generator.init_branch(f"beam_new_{actions}_{len(branches)}"))

        best_branch = self.scorer.pick_best(branches)
        prediction = best_branch.predicted_answer if best_branch else None
        return MethodResult(
            method="fixed_width_beam",
            prediction=prediction,
            is_correct=self._answers_match(prediction, gold_answer),
            actions_used=actions,
            expansions=expansions,
            verifications=verifications,
            avg_surviving_branches=sum(surviving_trace) / max(1, len(surviving_trace)),
            budget_exhausted=actions >= self.max_actions,
            metadata={"width": self.width},
        )


class TreeOfThoughtMatchedBudgetController(BaseController):
    """Matched-budget ToT-style controller adapter.

    This is intentionally a light-weight adapter for this repository's branch API, not
    an official reproduction of the Tree-of-Thoughts reference implementation.
    """

    def __init__(
        self,
        generator: BranchGenerator,
        scorer: BranchScorer,
        max_actions_per_problem: int,
        *,
        method_name: str,
        search_mode: str = "bfs",
        frontier_width: int = 3,
    ) -> None:
        super().__init__(generator, scorer, max_actions_per_problem)
        self.method_name = method_name
        self.search_mode = search_mode.strip().lower()
        self.frontier_width = max(1, int(frontier_width))

    def _pick_active_idx(self, frontier: list[BranchState]) -> int | None:
        active = [(i, b) for i, b in enumerate(frontier) if not b.is_done and not b.is_pruned]
        if not active:
            return None
        if self.search_mode == "dfs":
            return active[-1][0]
        if self.search_mode == "beam":
            scored = sorted(active, key=lambda t: (-float(self.scorer.score_branch(t[1])), str(t[1].branch_id), t[0]))
            return scored[0][0]
        # bfs default
        return active[0][0]

    def run(self, question: str, gold_answer: str) -> MethodResult:
        actions = expansions = verifications = 0
        surviving_trace: list[int] = []
        frontier: list[BranchState] = [self.generator.init_branch(f"{self.method_name}_root")]

        while actions < self.max_actions:
            idx = self._pick_active_idx(frontier)
            if idx is None:
                break
            branch = frontier[idx]
            self.generator.expand(branch, question, gold_answer)
            actions += 1
            expansions += 1

            # Deterministic frontier pruning by score then branch id.
            live = [b for b in frontier if not b.is_pruned]
            live_sorted = sorted(
                live,
                key=lambda b: (-float(self.scorer.score_branch(b)), str(b.branch_id)),
            )
            keep_ids = {b.branch_id for b in live_sorted[: self.frontier_width]}
            for b in live:
                if b.branch_id not in keep_ids and not b.is_pruned:
                    self.generator.prune(b)
            frontier = [b for b in frontier if not b.is_pruned]
            surviving_trace.append(len(frontier))

            if branch.is_done:
                continue
            if len(frontier) < self.frontier_width and actions < self.max_actions:
                child = self.generator.init_branch(f"{self.method_name}_n{actions}_{len(frontier)}")
                child.score = 0.5 * child.score + 0.5 * branch.score
                child.steps = list(branch.steps)
                frontier.append(child)

        best_branch = self.scorer.pick_best(frontier)
        prediction = best_branch.predicted_answer if best_branch else None
        return MethodResult(
            method=self.method_name,
            prediction=prediction,
            is_correct=self._answers_match(prediction, gold_answer),
            actions_used=actions,
            expansions=expansions,
            verifications=verifications,
            avg_surviving_branches=sum(surviving_trace) / max(1, len(surviving_trace)),
            budget_exhausted=actions >= self.max_actions,
            metadata={
                "search_mode": self.search_mode,
                "frontier_width": self.frontier_width,
                "adapter_note": "matched_budget_adapter_not_official_tot_reproduction",
                "scoring_accounting": "scoring_folded_into_expand_action_no_extra_verifier_calls",
            },
        )


class AdaptiveController(BaseController):
    def __init__(
        self,
        generator: BranchGenerator,
        scorer: BranchScorer,
        max_actions_per_problem: int,
        high_threshold: float,
        low_threshold: float,
        max_branches: int,
        allow_verify: bool = True,
        min_expansions_before_prune: int = 0,
        adaptive_min_expand: bool = False,
        verify_exploration_floor: int = 0,
        budget_guard_prune_floor: float = 0.0,
        partial_branch_scorer: PartialBranchScorer | None = None,
        enable_prm_early_reject: bool = False,
        prm_early_reject_threshold: float = 0.25,
        prm_early_reject_min_expansions: int = 2,
        method_name: str = "adaptive_expand_verify_prune",
    ) -> None:
        super().__init__(generator, scorer, max_actions_per_problem)
        self.high_threshold = high_threshold
        self.low_threshold = low_threshold
        self.max_branches = max_branches
        self.allow_verify = allow_verify
        self.min_expansions_before_prune = max(0, min_expansions_before_prune)
        self.adaptive_min_expand = adaptive_min_expand
        self.verify_exploration_floor = max(0, verify_exploration_floor)
        self.budget_guard_prune_floor = max(0.0, min(1.0, budget_guard_prune_floor))
        self.partial_branch_scorer = partial_branch_scorer
        self.enable_prm_early_reject = enable_prm_early_reject
        self.prm_early_reject_threshold = float(prm_early_reject_threshold)
        self.prm_early_reject_min_expansions = max(0, int(prm_early_reject_min_expansions))
        self.method_name = method_name

    def run(self, question: str, gold_answer: str) -> MethodResult:
        actions = expansions = verifications = 0
        surviving_trace: list[int] = []
        action_trace: list[dict[str, Any]] = []
        branch_expansions: dict[str, int] = {}
        branches: list[BranchState] = [self.generator.init_branch("adaptive_0")]

        while actions < self.max_actions and branches:
            next_branches: list[BranchState] = []
            for branch in branches:
                if actions >= self.max_actions:
                    break
                if branch.is_done or branch.is_pruned:
                    next_branches.append(branch)
                    continue

                fallback_score = self.scorer.score_branch(branch)
                partial_info = None
                score_before = fallback_score
                if self.partial_branch_scorer is not None:
                    partial_info = self.partial_branch_scorer.score_partial_branch(
                        branch,
                        question,
                        stage="adaptive_frontier",
                    )
                    score_before = float(partial_info.value)
                branch_expand_count = branch_expansions.get(branch.branch_id, 0)
                remaining_budget_frac = max(0.0, (self.max_actions - actions) / max(1, self.max_actions))
                effective_min_expand = self.min_expansions_before_prune
                if self.adaptive_min_expand and remaining_budget_frac >= 0.5:
                    effective_min_expand += 1

                early_reject_flag = (
                    self.enable_prm_early_reject
                    and self.partial_branch_scorer is not None
                    and branch_expand_count >= self.prm_early_reject_min_expansions
                    and score_before < self.prm_early_reject_threshold
                )
                if early_reject_flag:
                    result = self.generator.prune(branch)
                    action_trace.append(
                        self._trace_row(
                            branch,
                            "prune",
                            score_before,
                            result.score_after,
                            actions,
                            forced_expand=False,
                            forced_expand_reason="prm_early_reject",
                            partial_score=score_before,
                            score_source=(partial_info.score_source if partial_info else "base_scorer"),
                            score_stage=(partial_info.score_stage if partial_info else "adaptive_frontier"),
                            early_reject_flag=True,
                            scorer_notes=(partial_info.scorer_notes if partial_info else ""),
                            fallback_score=fallback_score,
                        )
                    )
                    continue

                if branch_expand_count < effective_min_expand:
                    result = self.generator.expand(branch, question, gold_answer)
                    actions += 1
                    expansions += 1
                    branch_expansions[branch.branch_id] = branch_expand_count + 1
                    next_branches.append(branch)
                    action_trace.append(
                        self._trace_row(
                            branch,
                            "expand",
                            score_before,
                            result.score_after,
                            actions,
                            forced_expand=True,
                            forced_expand_reason="min_expand_guard",
                            partial_score=score_before,
                            score_source=(partial_info.score_source if partial_info else "base_scorer"),
                            score_stage=(partial_info.score_stage if partial_info else "adaptive_frontier"),
                            early_reject_flag=False,
                            scorer_notes=(partial_info.scorer_notes if partial_info else ""),
                            fallback_score=fallback_score,
                        )
                    )
                    if not branch.is_done and len(next_branches) < self.max_branches and actions < self.max_actions:
                        child = self.generator.init_branch(f"adaptive_child_{actions}_{len(next_branches)}")
                        child.score = 0.5 * child.score + 0.5 * branch.score
                        next_branches.append(child)
                        branch_expansions[child.branch_id] = 0
                elif score_before >= self.high_threshold:
                    result = self.generator.expand(branch, question, gold_answer)
                    actions += 1
                    expansions += 1
                    branch_expansions[branch.branch_id] = branch_expand_count + 1
                    next_branches.append(branch)
                    action_trace.append(
                        self._trace_row(
                            branch,
                            "expand",
                            score_before,
                            result.score_after,
                            actions,
                            partial_score=score_before,
                            score_source=(partial_info.score_source if partial_info else "base_scorer"),
                            score_stage=(partial_info.score_stage if partial_info else "adaptive_frontier"),
                            early_reject_flag=False,
                            scorer_notes=(partial_info.scorer_notes if partial_info else ""),
                            fallback_score=fallback_score,
                        )
                    )
                    if not branch.is_done and len(next_branches) < self.max_branches and actions < self.max_actions:
                        child = self.generator.init_branch(f"adaptive_child_{actions}_{len(next_branches)}")
                        child.score = 0.5 * child.score + 0.5 * branch.score
                        next_branches.append(child)
                        branch_expansions[child.branch_id] = 0
                elif (
                    self.allow_verify
                    and score_before >= self.low_threshold
                    and branch_expand_count >= self.verify_exploration_floor
                ):
                    result = self.generator.verify(branch, question)
                    actions += 1
                    verifications += 1
                    next_branches.append(branch)
                    action_trace.append(
                        self._trace_row(
                            branch,
                            "verify",
                            score_before,
                            result.score_after,
                            actions,
                            partial_score=score_before,
                            score_source=(partial_info.score_source if partial_info else "base_scorer"),
                            score_stage=(partial_info.score_stage if partial_info else "adaptive_frontier"),
                            early_reject_flag=False,
                            scorer_notes=(partial_info.scorer_notes if partial_info else ""),
                            fallback_score=fallback_score,
                        )
                    )
                else:
                    prune_guard_active = (
                        self.budget_guard_prune_floor > 0.0
                        and remaining_budget_frac >= self.budget_guard_prune_floor
                        and branch_expand_count <= (effective_min_expand + 1)
                    )
                    if prune_guard_active and actions < self.max_actions:
                        result = self.generator.expand(branch, question, gold_answer)
                        actions += 1
                        expansions += 1
                        branch_expansions[branch.branch_id] = branch_expand_count + 1
                        next_branches.append(branch)
                        action_trace.append(
                            self._trace_row(
                                branch,
                                "expand",
                                score_before,
                                result.score_after,
                                actions,
                                forced_expand=True,
                                forced_expand_reason="budget_guard",
                                partial_score=score_before,
                                score_source=(partial_info.score_source if partial_info else "base_scorer"),
                                score_stage=(partial_info.score_stage if partial_info else "adaptive_frontier"),
                                early_reject_flag=False,
                                scorer_notes=(partial_info.scorer_notes if partial_info else ""),
                                fallback_score=fallback_score,
                            )
                        )
                    else:
                        result = self.generator.prune(branch)
                        action_trace.append(
                            self._trace_row(
                                branch,
                                "prune",
                                score_before,
                                result.score_after,
                                actions,
                                partial_score=score_before,
                                score_source=(partial_info.score_source if partial_info else "base_scorer"),
                                score_stage=(partial_info.score_stage if partial_info else "adaptive_frontier"),
                                early_reject_flag=False,
                                scorer_notes=(partial_info.scorer_notes if partial_info else ""),
                                fallback_score=fallback_score,
                            )
                        )

            branches = [b for b in next_branches if not b.is_pruned][: self.max_branches]
            surviving_trace.append(len(branches))
            if all(b.is_done for b in branches):
                break

        best_branch = self.scorer.pick_best(branches)
        prediction = best_branch.predicted_answer if best_branch else None
        exhausted = actions >= self.max_actions and not any(b.is_done for b in branches)

        return MethodResult(
            method=self.method_name,
            prediction=prediction,
            is_correct=self._answers_match(prediction, gold_answer),
            actions_used=actions,
            expansions=expansions,
            verifications=verifications,
            avg_surviving_branches=sum(surviving_trace) / max(1, len(surviving_trace)),
            budget_exhausted=exhausted,
            metadata={
                "high_threshold": self.high_threshold,
                "low_threshold": self.low_threshold,
                "max_branches": self.max_branches,
                "allow_verify": self.allow_verify,
                "min_expansions_before_prune": self.min_expansions_before_prune,
                "adaptive_min_expand": self.adaptive_min_expand,
                "verify_exploration_floor": self.verify_exploration_floor,
                "budget_guard_prune_floor": self.budget_guard_prune_floor,
                "uses_partial_prm_scorer": self.partial_branch_scorer is not None,
                "enable_prm_early_reject": self.enable_prm_early_reject,
                "prm_early_reject_threshold": self.prm_early_reject_threshold,
                "prm_early_reject_min_expansions": self.prm_early_reject_min_expansions,
                "action_trace": action_trace,
                "final_selected_branch": best_branch.branch_id if best_branch else None,
            },
        )

    def _trace_row(
        self,
        branch: BranchState,
        action: str,
        score_before: float,
        score_after: float,
        actions_used: int,
        forced_expand: bool = False,
        forced_expand_reason: str | None = None,
        partial_score: float | None = None,
        score_source: str | None = None,
        score_stage: str | None = None,
        early_reject_flag: bool = False,
        scorer_notes: str | None = None,
        fallback_score: float | None = None,
    ) -> dict[str, Any]:
        return {
            "branch_id": branch.branch_id,
            "action": action,
            "score_before": round(score_before, 4),
            "score_after": round(score_after, 4),
            "forced_expand": forced_expand,
            "forced_expand_reason": forced_expand_reason,
            "remaining_budget": max(0, self.max_actions - actions_used),
            "branch_done": branch.is_done,
            "branch_pruned": branch.is_pruned,
            "predicted_answer": branch.predicted_answer,
            "partial_score": None if partial_score is None else round(float(partial_score), 4),
            "fallback_score": None if fallback_score is None else round(float(fallback_score), 4),
            "score_source": score_source,
            "score_stage": score_stage,
            "early_reject_flag": bool(early_reject_flag),
            "scorer_notes": scorer_notes,
        }


class IntermediateTrapAwareNearTieController(AdaptiveController):
    """Bounded intermediate-trap-aware near-tie selector on top of adaptive exploration."""

    def __init__(
        self,
        generator: BranchGenerator,
        scorer: BranchScorer,
        max_actions_per_problem: int,
        *,
        near_tie_gap: float = 0.03,
        incompleteness_trigger: float = 0.45,
        method_name: str = "intermediate_trap_aware_near_tie_v1",
        **kwargs: Any,
    ) -> None:
        super().__init__(
            generator,
            scorer,
            max_actions_per_problem,
            method_name=method_name,
            **kwargs,
        )
        self.near_tie_gap = float(near_tie_gap)
        self.incompleteness_trigger = float(incompleteness_trigger)

    @staticmethod
    def _is_intermediate_like(answer: str | None, question: str) -> bool:
        if not answer:
            return True
        q = question.lower()
        a = answer.lower()
        if any(tok in q for tok in ["how many", "difference", "left", "remain", "times"]):
            return not re.search(r"[-+]?\d+(?:\.\d+)?", a)
        return False

    def _pick_final_branch(self, branches: list[BranchState], question: str) -> BranchState | None:
        if not branches:
            return None
        ranked = sorted(branches, key=self.scorer.score_branch, reverse=True)
        top = ranked[0]
        second = ranked[1] if len(ranked) > 1 else ranked[0]
        gap = float(self.scorer.score_branch(top) - self.scorer.score_branch(second))
        if gap > self.near_tie_gap:
            return top
        if self._is_intermediate_like(top.predicted_answer, question):
            for candidate in ranked[1:]:
                if not self._is_intermediate_like(candidate.predicted_answer, question):
                    return candidate
        return top

    def run(self, question: str, gold_answer: str) -> MethodResult:
        result = super().run(question, gold_answer)
        branches_meta = result.metadata.get("final_branch_pool")
        if isinstance(branches_meta, list):
            candidates = [b for b in branches_meta if isinstance(b, BranchState)]
        else:
            candidates = []
        # `AdaptiveController` does not expose branch objects; preserve baseline behavior.
        # We still add explicit method metadata for downstream analysis.
        result.method = self.method_name
        result.metadata["near_tie_gap"] = self.near_tie_gap
        result.metadata["incompleteness_trigger"] = self.incompleteness_trigger
        result.metadata["trap_aware_selector_applied"] = bool(candidates)
        return result


class SelectiveSelfConsistencyHybridController(AdaptiveController):
    """Selective local diversity + bounded answer aggregation over adaptive frontier."""

    def __init__(
        self,
        generator: BranchGenerator,
        scorer: BranchScorer,
        max_actions_per_problem: int,
        *,
        near_tie_gap: float = 0.03,
        low_completion_trigger: float = 0.45,
        disagreement_trigger: float = 0.12,
        diversity_top_k: int = 3,
        min_consensus_support: float = 0.56,
        method_name: str = "selective_sc_hybrid_v1",
        **kwargs: Any,
    ) -> None:
        super().__init__(
            generator,
            scorer,
            max_actions_per_problem,
            method_name=method_name,
            **kwargs,
        )
        self.near_tie_gap = float(near_tie_gap)
        self.low_completion_trigger = float(low_completion_trigger)
        self.disagreement_trigger = float(disagreement_trigger)
        self.diversity_top_k = max(1, int(diversity_top_k))
        self.min_consensus_support = float(min_consensus_support)

    @staticmethod
    def _normalize_prediction(pred: str | None) -> str | None:
        if pred is None:
            return None
        s = str(pred).strip()
        if not s:
            return None
        m = re.findall(r"[-+]?\d+(?:\.\d+)?", s.replace(",", ""))
        return m[-1] if m else s.lower()

    @staticmethod
    def _completion_proxy(branch: BranchState) -> float:
        has_answer = 1.0 if branch.predicted_answer is not None else 0.0
        done = 1.0 if branch.is_done else 0.0
        return max(0.0, min(1.0, 0.65 * has_answer + 0.35 * done))

    def _hard_case_active(self, ranked: list[BranchState]) -> tuple[bool, dict[str, bool]]:
        top = ranked[0]
        second = ranked[1] if len(ranked) > 1 else ranked[0]
        top_score = float(self.scorer.score_branch(top))
        second_score = float(self.scorer.score_branch(second))
        near_tie = (top_score - second_score) <= self.near_tie_gap
        low_completion = self._completion_proxy(top) <= self.low_completion_trigger
        best_completion = max(ranked, key=self._completion_proxy)
        disagree = (
            best_completion.branch_id != top.branch_id
            and (self._completion_proxy(best_completion) - self._completion_proxy(top)) >= self.disagreement_trigger
        )
        return bool(near_tie or low_completion or disagree), {
            "near_tie": bool(near_tie),
            "low_top_completion": bool(low_completion),
            "continuation_completion_disagree": bool(disagree),
        }

    def _choose_hybrid(self, branches: list[BranchState]) -> tuple[BranchState | None, dict[str, Any]]:
        if not branches:
            return None, {"hard_case_active": False}
        ranked = sorted(branches, key=self.scorer.score_branch, reverse=True)
        top = ranked[0]
        hard_case, signals = self._hard_case_active(ranked)
        if not hard_case:
            return top, {"hard_case_active": False, **signals}

        local = ranked[: self.diversity_top_k]
        counts: dict[str, list[BranchState]] = {}
        for b in local:
            key = self._normalize_prediction(b.predicted_answer)
            if key is None:
                continue
            counts.setdefault(key, []).append(b)
        if not counts:
            return top, {"hard_case_active": True, "consensus_override": False, **signals}

        top_score = max(1e-8, float(self.scorer.score_branch(top)))
        best_group = None
        best_support = -1.0
        for answer, supporters in counts.items():
            frac = len(supporters) / max(1, len(local))
            weighted = sum(float(self.scorer.score_branch(b)) for b in supporters) / len(supporters)
            weighted_scaled = max(0.0, min(1.0, weighted / top_score))
            support = 0.70 * frac + 0.30 * weighted_scaled
            if support > best_support:
                best_support = support
                best_group = (answer, supporters, frac, support)

        if best_group is None:
            return top, {"hard_case_active": True, "consensus_override": False, **signals}
        answer, supporters, frac, support = best_group
        top_answer = self._normalize_prediction(top.predicted_answer)
        consensus_disagrees = (top_answer is None) or (answer != top_answer)
        if support >= self.min_consensus_support and consensus_disagrees:
            selected = max(supporters, key=self.scorer.score_branch)
            return selected, {
                "hard_case_active": True,
                "consensus_override": True,
                "consensus_support_score": float(support),
                "consensus_support_fraction": float(frac),
                "diversity_branch_count": len(local),
                **signals,
            }
        return top, {
            "hard_case_active": True,
            "consensus_override": False,
            "consensus_support_score": float(support),
            "consensus_support_fraction": float(frac),
            "diversity_branch_count": len(local),
            **signals,
        }

    def run(self, question: str, gold_answer: str) -> MethodResult:
        actions = expansions = verifications = 0
        surviving_trace: list[int] = []
        action_trace: list[dict[str, Any]] = []
        branch_expansions: dict[str, int] = {}
        branches: list[BranchState] = [self.generator.init_branch("hybrid_0")]

        while actions < self.max_actions and branches:
            next_branches: list[BranchState] = []
            for branch in branches:
                if actions >= self.max_actions:
                    break
                if branch.is_done or branch.is_pruned:
                    next_branches.append(branch)
                    continue
                score_before = self.scorer.score_branch(branch)
                branch_expand_count = branch_expansions.get(branch.branch_id, 0)

                if branch_expand_count < self.min_expansions_before_prune or score_before >= self.high_threshold:
                    result = self.generator.expand(branch, question, gold_answer)
                    actions += 1
                    expansions += 1
                    branch_expansions[branch.branch_id] = branch_expand_count + 1
                    next_branches.append(branch)
                    action_trace.append(self._trace_row(branch, "expand", score_before, result.score_after, actions))
                    if not branch.is_done and len(next_branches) < self.max_branches and actions < self.max_actions:
                        child = self.generator.init_branch(f"hybrid_child_{actions}_{len(next_branches)}")
                        child.score = 0.5 * child.score + 0.5 * branch.score
                        next_branches.append(child)
                        branch_expansions[child.branch_id] = 0
                elif self.allow_verify and score_before >= self.low_threshold:
                    result = self.generator.verify(branch, question)
                    actions += 1
                    verifications += 1
                    next_branches.append(branch)
                    action_trace.append(self._trace_row(branch, "verify", score_before, result.score_after, actions))
                else:
                    self.generator.prune(branch)
                    action_trace.append(self._trace_row(branch, "prune", score_before, score_before, actions))

            branches = [b for b in next_branches if not b.is_pruned][: self.max_branches]
            surviving_trace.append(len(branches))
            if all(b.is_done for b in branches):
                break

        selected, hybrid_meta = self._choose_hybrid(branches)
        prediction = selected.predicted_answer if selected else None
        exhausted = actions >= self.max_actions and not any(b.is_done for b in branches)
        return MethodResult(
            method=self.method_name,
            prediction=prediction,
            is_correct=self._answers_match(prediction, gold_answer),
            actions_used=actions,
            expansions=expansions,
            verifications=verifications,
            avg_surviving_branches=sum(surviving_trace) / max(1, len(surviving_trace)),
            budget_exhausted=exhausted,
            metadata={
                "method_family": "selective_sc_hybrid",
                "action_trace": action_trace,
                "near_tie_gap": self.near_tie_gap,
                "low_completion_trigger": self.low_completion_trigger,
                "disagreement_trigger": self.disagreement_trigger,
                "diversity_top_k": self.diversity_top_k,
                "min_consensus_support": self.min_consensus_support,
                "final_selected_branch": selected.branch_id if selected else None,
                **hybrid_meta,
            },
        )


class GlobalDiversityAggregationController(BaseController):
    """Global diversity/aggregation-aware branch allocator under fixed budget.

    Core design:
    - keep continuation-value scoring as the base signal (`self.scorer.score_branch`),
    - add global diversity pressure during allocation to avoid repeatedly spending
      budget on already-overrepresented answer groups,
    - use answer-support aggregation as the main final decision, not a local fallback.
    """

    def __init__(
        self,
        generator: BranchGenerator,
        scorer: BranchScorer,
        max_actions_per_problem: int,
        *,
        max_branches: int = 4,
        min_branch_expansions: int = 1,
        diversity_weight: float = 0.28,
        duplicate_penalty: float = 0.12,
        unknown_answer_bonus: float = 0.06,
        use_marginal_coverage_overlap: bool = False,
        coverage_weight: float = 0.22,
        overlap_weight: float = 0.14,
        use_duplicate_aware_aggregation: bool = False,
        duplicate_discount_strength: float = 0.70,
        duplicate_discount_floor: float = 0.20,
        support_quality_weight: float = 0.38,
        use_answer_group_commit_margin: bool = False,
        commit_margin_threshold: float = 0.16,
        commit_top_support_threshold: float = 0.62,
        commit_readiness_threshold: float = 0.58,
        continue_one_step_value_threshold: float = 0.66,
        min_actions_before_commit_check: int = 3,
        answer_support_weight: float = 0.45,
        value_weight: float = 0.55,
        commit_support_threshold: float = 0.68,
        commit_delay_min_actions: int = 3,
        enable_answer_group_coverage_floor: bool = False,
        min_answer_groups_before_concentration: int = 2,
        coverage_floor_min_actions: int = 2,
        coverage_floor_max_actions: int = 7,
        coverage_floor_plausibility_threshold: float = 0.44,
        coverage_floor_max_forced_steps: int = 2,
        enable_incumbent_challenger_commit: bool = False,
        incumbent_challenger_raw_support_only: bool = False,
        incumbent_challenger_margin_threshold: float = 0.10,
        incumbent_challenger_stability_min_steps: int = 2,
        incumbent_challenger_near_tie_gap: float = 0.04,
        incumbent_challenger_plausible_gap: float = 0.05,
        incumbent_score_support_weight: float = 0.50,
        incumbent_score_quality_weight: float = 0.35,
        incumbent_score_readiness_weight: float = 0.15,
        incumbent_safety_commit_min: float = 0.62,
        challenger_upside_commit_max: float = 0.16,
        challenger_upside_expand_weight: float = 0.35,
        metalevel_delta_margin: float = 0.02,
        near_tie_commit_margin_extra: float = 0.02,
        stop_continue_value_margin: float = 0.00,
        remaining_budget_commit_bias: float = 0.00,
        late_stage_commit_bonus: float = 0.00,
        near_tie_commit_band: float = 0.00,
        continue_requires_min_best_value: float = 0.00,
        near_tie_weak_continue_value_cap: float = 0.00,
        force_extra_explore_on_near_tie: bool = True,
        near_tie_force_max_steps: int = 1,
        near_tie_force_upside_frac_threshold: float = 0.60,
        intermediate_result_penalty: float = 0.18,
        challenger_overthrow_weight: float = 0.55,
        challenger_correlation_penalty: float = 0.18,
        challenger_repeat_failure_penalty: float = 0.08,
        challenger_min_relative_upside: float = 0.01,
        challenger_low_margin_penalty: float = 0.06,
        diversity_needed_gate_mode: str = "off",
        diversity_needed_gate_positive_threshold: float = 0.12,
        diversity_needed_gate_negative_threshold: float = -0.12,
        diversity_needed_gate_min_confidence_gap: float = 0.04,
        diversity_needed_gate_dataset_path: str = "outputs/branch_label_bruteforce_learning/diversity_needed_feasibility_20260419/labels/diversity_needed_state_dataset.jsonl",
        enable_early_answer_group_preservation: bool = False,
        early_preservation_action_window: int = 5,
        early_preservation_min_plausible_continuation: float = 0.46,
        early_preservation_target_alignment_min: float = 0.34,
        early_preservation_required_group_gap: float = 0.18,
        early_preservation_challenger_hold_steps: int = 1,
        enable_early_answer_diversity_maturation_v1: bool = False,
        enable_early_answer_diversity_maturation_gated_v1: bool = False,
        early_answer_diversity_recent_group_window: int = 2,
        enable_anti_collapse_answer_group_refinement: bool = False,
        anti_collapse_early_window: int = 6,
        enable_conditional_anti_collapse_activation: bool = False,
        conditional_anti_collapse_min_actions: int = 2,
        conditional_anti_collapse_max_family_share_trigger: float = 0.58,
        conditional_anti_collapse_max_active_groups_for_low_coverage: int = 1,
        conditional_anti_collapse_min_consecutive_family_expands: int = 3,
        repeated_same_branch_penalty: float = 0.08,
        repeated_same_branch_cap: int = 3,
        repeat_expand_free_steps: int = 3,
        repeat_expand_penalty_weight: float = 0.08,
        repeat_expand_family_penalty_weight: float = 0.12,
        repeat_expand_override_margin: float = 0.10,
        enable_low_marginal_gain_family_cooldown: bool = False,
        low_marginal_gain_window_size: int = 3,
        low_marginal_gain_min_threshold: float = 0.015,
        low_marginal_gain_consecutive_family_trigger: int = 4,
        low_marginal_gain_cooldown_steps: int = 2,
        low_marginal_gain_penalty_strength: float = 0.14,
        low_marginal_gain_override_margin: float = 0.12,
        low_marginal_gain_override_top_support_min: float = 0.74,
        low_marginal_gain_answer_group_aware: bool = True,
        low_marginal_gain_hard_block_ablation: bool = False,
        monopolization_margin_requirement: float = 0.10,
        answer_group_distinctness_bonus: float = 0.10,
        duplicate_answer_group_penalty: float = 0.08,
        min_followup_steps_for_preserved_alternative: int = 2,
        alternative_maturity_window: int = 5,
        protected_alternative_target_alignment_min: float = 0.48,
        enable_width_depth_allocation_guard: bool = False,
        width_depth_repeat_family_trigger: int = 2,
        width_depth_min_actions: int = 3,
        width_depth_challenger_maturation_min_expands: int = 2,
        width_depth_min_relative_continuation: float = 0.75,
        enable_uncertainty_triggered_verify: bool = False,
        uncertainty_verify_priority_margin: float = 0.05,
        uncertainty_verify_max_steps: int = 2,
        enable_near_miss_correction_gate: bool = False,
        near_miss_correction_numeric_gap: float = 3.0,
        near_miss_correction_min_actions: int = 4,
        near_miss_correction_max_steps: int = 2,
        near_miss_correction_repeat_family_trigger: int = 5,
        near_miss_correction_min_top_support: float = 0.55,
        enable_hard_early_root_depth2_coverage_v1: bool = False,
        hard_early_root_coverage_forced_min_depth: int = 0,
        hard_early_coverage_min_remaining_actions_to_release: int = 0,
        enable_hard_early_root_depth2_then_conditional_depth3_v1: bool = False,
        depth3_gate_min_top_answer_support: float = 0.55,
        depth3_gate_min_support_gap: float = 0.12,
        depth3_gate_min_active_root_families: int = 2,
        depth3_gate_max_family_share_trigger: float = 0.55,
        depth3_gate_longest_run_trigger: int = 4,
        depth3_gate_min_confident_frontier_score: float = 0.62,
        depth3_gate_min_top_group_support_commit: float = 0.52,
        depth3_gate_e_max_top_support: float = 0.48,
        depth3_gate_e_min_answer_groups: int = 2,
        enable_hard_max_family_expansions_cap: bool = False,
        hard_max_family_expansions_base_cap: int = 6,
        hard_max_family_expansions_relax_cap: int = 8,
        hard_max_family_expansions_relax_cap_high: int = 10,
        hard_max_family_expansions_relax_mode: str = "fixed_k6_control",
        hard_max_family_expansions_conditional_early_window_actions: int = 6,
        hard_max_family_expansions_conditional_risk_family_share_trigger: float = 0.60,
        hard_max_family_expansions_conditional_risk_consecutive_run_trigger: int = 3,
        hard_max_family_expansions_conditional_min_rival_maturity_expansions: int = 2,
        enable_case_split_direction_aware_v1: bool = False,
        case_split_direction_aware_labels: tuple[str, ...] = ("counting_combinatorics", "case_split"),
        case_split_direction_aware_min_distinct_families: int = 3,
        case_split_direction_aware_early_window_actions: int = 5,
        case_split_direction_aware_delay_commit_until_families: int = 2,
        case_split_direction_aware_repeat_penalty_multiplier: float = 1.6,
        case_split_direction_aware_unresolved_branch_bonus: float = 0.08,
        case_split_direction_aware_disable_delay_commit_ablation: bool = False,
        case_split_direction_aware_disable_repeat_penalty_ablation: bool = False,
        case_split_direction_aware_disable_unresolved_preservation_ablation: bool = False,
        case_split_direction_aware_detector_off: bool = False,
        enable_direction_combinatorics_guard_v1: bool = False,
        direction_family_cap_share_precoverage: float = 0.60,
        direction_support_weight: float = 1.0,
        direction_process_weight: float = 0.5,
        direction_verifier_weight: float = 1.0,
        direction_strategy_diversity_weight: float = 0.5,
        direction_single_family_penalty_weight: float = 0.5,
        direction_commit_guard_top2_gap_threshold: float = 0.12,
        enable_typed_strategy_seeded_v1: bool = False,
        enable_reasoning_diversity_bonus_v1: bool = False,
        reasoning_diversity_lambda_strategy: float = 0.40,
        reasoning_diversity_lambda_operation: float = 0.30,
        reasoning_diversity_lambda_intermediate: float = 0.25,
        reasoning_diversity_lambda_answer: float = 0.20,
        reasoning_diversity_lambda_role: float = 0.20,
        reasoning_diversity_lambda_redundancy: float = 0.50,
        enable_family_normalized_rerank_v1: bool = False,
        family_rerank_selection_mode: str = "family_normalized_full",
        family_rerank_support_weight: float = 1.0,
        family_rerank_process_weight: float = 0.5,
        family_rerank_verifier_weight: float = 1.0,
        family_rerank_diversity_weight: float = 0.4,
        family_rerank_single_family_penalty_weight: float = 0.5,
        family_rerank_dominant_family_penalty_weight: float = 0.3,
        diagnostic_semantic_maturation: bool = False,
        diagnostic_semantic_maturation_min_depth: int = 0,
        diagnostic_branching_necessity_heuristic: bool = False,
        diagnostic_protected_incumbent_release: bool = False,
        diagnostic_log_semantic_families: bool = False,
        method_name: str = "broad_diversity_aggregation_v1",
    ) -> None:
        super().__init__(generator, scorer, max_actions_per_problem)
        self.max_branches = max(2, int(max_branches))
        self.min_branch_expansions = max(0, int(min_branch_expansions))
        self.diversity_weight = float(diversity_weight)
        self.duplicate_penalty = float(duplicate_penalty)
        self.unknown_answer_bonus = float(unknown_answer_bonus)
        self.use_marginal_coverage_overlap = bool(use_marginal_coverage_overlap)
        self.coverage_weight = float(coverage_weight)
        self.overlap_weight = float(overlap_weight)
        self.use_duplicate_aware_aggregation = bool(use_duplicate_aware_aggregation)
        self.duplicate_discount_strength = float(duplicate_discount_strength)
        self.duplicate_discount_floor = float(duplicate_discount_floor)
        self.support_quality_weight = float(support_quality_weight)
        self.use_answer_group_commit_margin = bool(use_answer_group_commit_margin)
        self.commit_margin_threshold = float(commit_margin_threshold)
        self.commit_top_support_threshold = float(commit_top_support_threshold)
        self.commit_readiness_threshold = float(commit_readiness_threshold)
        self.continue_one_step_value_threshold = float(continue_one_step_value_threshold)
        self.min_actions_before_commit_check = int(min_actions_before_commit_check)
        self.answer_support_weight = float(answer_support_weight)
        self.value_weight = float(value_weight)
        self.commit_support_threshold = float(commit_support_threshold)
        self.commit_delay_min_actions = max(0, int(commit_delay_min_actions))
        self.enable_answer_group_coverage_floor = bool(enable_answer_group_coverage_floor)
        self.min_answer_groups_before_concentration = max(1, int(min_answer_groups_before_concentration))
        self.coverage_floor_min_actions = max(0, int(coverage_floor_min_actions))
        self.coverage_floor_max_actions = max(self.coverage_floor_min_actions, int(coverage_floor_max_actions))
        self.coverage_floor_plausibility_threshold = float(coverage_floor_plausibility_threshold)
        self.coverage_floor_max_forced_steps = max(0, int(coverage_floor_max_forced_steps))
        self.enable_incumbent_challenger_commit = bool(enable_incumbent_challenger_commit)
        self.incumbent_challenger_raw_support_only = bool(incumbent_challenger_raw_support_only)
        self.incumbent_challenger_margin_threshold = float(incumbent_challenger_margin_threshold)
        self.incumbent_challenger_stability_min_steps = max(1, int(incumbent_challenger_stability_min_steps))
        self.incumbent_challenger_near_tie_gap = float(incumbent_challenger_near_tie_gap)
        self.incumbent_challenger_plausible_gap = float(incumbent_challenger_plausible_gap)
        self.incumbent_score_support_weight = float(incumbent_score_support_weight)
        self.incumbent_score_quality_weight = float(incumbent_score_quality_weight)
        self.incumbent_score_readiness_weight = float(incumbent_score_readiness_weight)
        self.incumbent_safety_commit_min = float(incumbent_safety_commit_min)
        self.challenger_upside_commit_max = float(challenger_upside_commit_max)
        self.challenger_upside_expand_weight = float(challenger_upside_expand_weight)
        self.metalevel_delta_margin = float(metalevel_delta_margin)
        self.near_tie_commit_margin_extra = float(near_tie_commit_margin_extra)
        self.stop_continue_value_margin = float(stop_continue_value_margin)
        self.remaining_budget_commit_bias = float(remaining_budget_commit_bias)
        self.late_stage_commit_bonus = float(late_stage_commit_bonus)
        self.near_tie_commit_band = float(near_tie_commit_band)
        self.continue_requires_min_best_value = float(continue_requires_min_best_value)
        self.near_tie_weak_continue_value_cap = float(near_tie_weak_continue_value_cap)
        self.force_extra_explore_on_near_tie = bool(force_extra_explore_on_near_tie)
        self.near_tie_force_max_steps = max(0, int(near_tie_force_max_steps))
        self.near_tie_force_upside_frac_threshold = max(0.0, min(1.0, float(near_tie_force_upside_frac_threshold)))
        self.intermediate_result_penalty = max(0.0, float(intermediate_result_penalty))
        self.challenger_overthrow_weight = float(challenger_overthrow_weight)
        self.challenger_correlation_penalty = float(challenger_correlation_penalty)
        self.challenger_repeat_failure_penalty = float(challenger_repeat_failure_penalty)
        self.challenger_min_relative_upside = float(challenger_min_relative_upside)
        self.challenger_low_margin_penalty = float(challenger_low_margin_penalty)
        self.diversity_needed_gate_mode = str(diversity_needed_gate_mode)
        self.diversity_needed_gate_positive_threshold = float(diversity_needed_gate_positive_threshold)
        self.diversity_needed_gate_negative_threshold = float(diversity_needed_gate_negative_threshold)
        self.diversity_needed_gate_min_confidence_gap = float(diversity_needed_gate_min_confidence_gap)
        self.diversity_needed_gate_dataset_path = str(diversity_needed_gate_dataset_path)
        self.enable_early_answer_group_preservation = bool(enable_early_answer_group_preservation)
        self.early_preservation_action_window = max(1, int(early_preservation_action_window))
        self.early_preservation_min_plausible_continuation = float(early_preservation_min_plausible_continuation)
        self.early_preservation_target_alignment_min = float(early_preservation_target_alignment_min)
        self.early_preservation_required_group_gap = float(early_preservation_required_group_gap)
        self.early_preservation_challenger_hold_steps = max(0, int(early_preservation_challenger_hold_steps))
        self.enable_early_answer_diversity_maturation_v1 = bool(enable_early_answer_diversity_maturation_v1)
        self.enable_early_answer_diversity_maturation_gated_v1 = bool(enable_early_answer_diversity_maturation_gated_v1)
        self.early_answer_diversity_recent_group_window = max(1, int(early_answer_diversity_recent_group_window))
        self.enable_anti_collapse_answer_group_refinement = bool(enable_anti_collapse_answer_group_refinement)
        self.anti_collapse_early_window = max(1, int(anti_collapse_early_window))
        self.enable_conditional_anti_collapse_activation = bool(enable_conditional_anti_collapse_activation)
        self.conditional_anti_collapse_min_actions = max(0, int(conditional_anti_collapse_min_actions))
        self.conditional_anti_collapse_max_family_share_trigger = max(
            0.0, min(1.0, float(conditional_anti_collapse_max_family_share_trigger))
        )
        self.conditional_anti_collapse_max_active_groups_for_low_coverage = max(
            1, int(conditional_anti_collapse_max_active_groups_for_low_coverage)
        )
        self.conditional_anti_collapse_min_consecutive_family_expands = max(
            1, int(conditional_anti_collapse_min_consecutive_family_expands)
        )
        self.repeated_same_branch_penalty = max(0.0, float(repeated_same_branch_penalty))
        self.repeated_same_branch_cap = max(1, int(repeated_same_branch_cap))
        self.repeat_expand_free_steps = max(0, int(repeat_expand_free_steps))
        self.repeat_expand_penalty_weight = max(0.0, float(repeat_expand_penalty_weight))
        self.repeat_expand_family_penalty_weight = max(0.0, float(repeat_expand_family_penalty_weight))
        self.repeat_expand_override_margin = max(0.0, float(repeat_expand_override_margin))
        self.enable_low_marginal_gain_family_cooldown = bool(enable_low_marginal_gain_family_cooldown)
        self.low_marginal_gain_window_size = max(2, int(low_marginal_gain_window_size))
        self.low_marginal_gain_min_threshold = max(0.0, float(low_marginal_gain_min_threshold))
        self.low_marginal_gain_consecutive_family_trigger = max(2, int(low_marginal_gain_consecutive_family_trigger))
        self.low_marginal_gain_cooldown_steps = max(1, int(low_marginal_gain_cooldown_steps))
        self.low_marginal_gain_penalty_strength = max(0.0, float(low_marginal_gain_penalty_strength))
        self.low_marginal_gain_override_margin = max(0.0, float(low_marginal_gain_override_margin))
        self.low_marginal_gain_override_top_support_min = max(0.0, min(1.0, float(low_marginal_gain_override_top_support_min)))
        self.low_marginal_gain_answer_group_aware = bool(low_marginal_gain_answer_group_aware)
        self.low_marginal_gain_hard_block_ablation = bool(low_marginal_gain_hard_block_ablation)
        self.monopolization_margin_requirement = max(0.0, float(monopolization_margin_requirement))
        self.answer_group_distinctness_bonus = max(0.0, float(answer_group_distinctness_bonus))
        self.duplicate_answer_group_penalty = max(0.0, float(duplicate_answer_group_penalty))
        self.min_followup_steps_for_preserved_alternative = max(0, int(min_followup_steps_for_preserved_alternative))
        self.alternative_maturity_window = max(1, int(alternative_maturity_window))
        self.protected_alternative_target_alignment_min = float(protected_alternative_target_alignment_min)
        self.enable_width_depth_allocation_guard = bool(enable_width_depth_allocation_guard)
        self.width_depth_repeat_family_trigger = max(1, int(width_depth_repeat_family_trigger))
        self.width_depth_min_actions = max(0, int(width_depth_min_actions))
        self.width_depth_challenger_maturation_min_expands = max(1, int(width_depth_challenger_maturation_min_expands))
        self.width_depth_min_relative_continuation = max(0.0, min(1.0, float(width_depth_min_relative_continuation)))
        self.enable_uncertainty_triggered_verify = bool(enable_uncertainty_triggered_verify)
        self.uncertainty_verify_priority_margin = max(0.0, float(uncertainty_verify_priority_margin))
        self.uncertainty_verify_max_steps = max(0, int(uncertainty_verify_max_steps))
        self.enable_near_miss_correction_gate = bool(enable_near_miss_correction_gate)
        self.near_miss_correction_numeric_gap = max(0.0, float(near_miss_correction_numeric_gap))
        self.near_miss_correction_min_actions = max(0, int(near_miss_correction_min_actions))
        self.near_miss_correction_max_steps = max(0, int(near_miss_correction_max_steps))
        self.near_miss_correction_repeat_family_trigger = max(1, int(near_miss_correction_repeat_family_trigger))
        self.near_miss_correction_min_top_support = max(0.0, min(1.0, float(near_miss_correction_min_top_support)))
        self.enable_hard_early_root_depth2_coverage_v1 = bool(enable_hard_early_root_depth2_coverage_v1)
        _hec = max(0, min(7, int(hard_early_root_coverage_forced_min_depth)))
        if self.enable_hard_early_root_depth2_coverage_v1 and _hec < 2:
            _hec = 2
        self.hard_early_root_coverage_forced_min_depth = int(_hec)
        self.hard_early_coverage_min_remaining_actions_to_release = max(0, int(hard_early_coverage_min_remaining_actions_to_release))
        self.enable_hard_early_root_depth2_then_conditional_depth3_v1 = bool(
            enable_hard_early_root_depth2_then_conditional_depth3_v1
        )
        if self.enable_hard_early_root_depth2_then_conditional_depth3_v1:
            _hec = max(2, _hec)
        self.depth3_gate_min_top_answer_support = float(depth3_gate_min_top_answer_support)
        self.depth3_gate_min_support_gap = float(depth3_gate_min_support_gap)
        self.depth3_gate_min_active_root_families = max(1, int(depth3_gate_min_active_root_families))
        self.depth3_gate_max_family_share_trigger = float(depth3_gate_max_family_share_trigger)
        self.depth3_gate_longest_run_trigger = max(1, int(depth3_gate_longest_run_trigger))
        self.depth3_gate_min_confident_frontier_score = float(depth3_gate_min_confident_frontier_score)
        self.depth3_gate_min_top_group_support_commit = float(depth3_gate_min_top_group_support_commit)
        self.depth3_gate_e_max_top_support = float(depth3_gate_e_max_top_support)
        self.depth3_gate_e_min_answer_groups = max(2, int(depth3_gate_e_min_answer_groups))
        self.enable_hard_max_family_expansions_cap = bool(enable_hard_max_family_expansions_cap)
        self.hard_max_family_expansions_base_cap = max(1, int(hard_max_family_expansions_base_cap))
        self.hard_max_family_expansions_relax_cap = max(
            self.hard_max_family_expansions_base_cap, int(hard_max_family_expansions_relax_cap)
        )
        self.hard_max_family_expansions_relax_cap_high = max(
            self.hard_max_family_expansions_relax_cap, int(hard_max_family_expansions_relax_cap_high)
        )
        self.hard_max_family_expansions_relax_mode = str(hard_max_family_expansions_relax_mode or "fixed_k6_control")
        self.hard_max_family_expansions_conditional_early_window_actions = max(
            0, int(hard_max_family_expansions_conditional_early_window_actions)
        )
        self.hard_max_family_expansions_conditional_risk_family_share_trigger = max(
            0.0, min(1.0, float(hard_max_family_expansions_conditional_risk_family_share_trigger))
        )
        self.hard_max_family_expansions_conditional_risk_consecutive_run_trigger = max(
            1, int(hard_max_family_expansions_conditional_risk_consecutive_run_trigger)
        )
        self.hard_max_family_expansions_conditional_min_rival_maturity_expansions = max(
            1, int(hard_max_family_expansions_conditional_min_rival_maturity_expansions)
        )
        self.enable_case_split_direction_aware_v1 = bool(enable_case_split_direction_aware_v1)
        self.case_split_direction_aware_labels = tuple(str(x) for x in case_split_direction_aware_labels)
        self.case_split_direction_aware_min_distinct_families = max(2, int(case_split_direction_aware_min_distinct_families))
        self.case_split_direction_aware_early_window_actions = max(1, int(case_split_direction_aware_early_window_actions))
        self.case_split_direction_aware_delay_commit_until_families = max(1, int(case_split_direction_aware_delay_commit_until_families))
        self.case_split_direction_aware_repeat_penalty_multiplier = max(1.0, float(case_split_direction_aware_repeat_penalty_multiplier))
        self.case_split_direction_aware_unresolved_branch_bonus = max(0.0, float(case_split_direction_aware_unresolved_branch_bonus))
        self.case_split_direction_aware_disable_delay_commit_ablation = bool(case_split_direction_aware_disable_delay_commit_ablation)
        self.case_split_direction_aware_disable_repeat_penalty_ablation = bool(case_split_direction_aware_disable_repeat_penalty_ablation)
        self.case_split_direction_aware_disable_unresolved_preservation_ablation = bool(case_split_direction_aware_disable_unresolved_preservation_ablation)
        self.case_split_direction_aware_detector_off = bool(case_split_direction_aware_detector_off)
        self.enable_direction_combinatorics_guard_v1 = bool(enable_direction_combinatorics_guard_v1)
        self.direction_family_cap_share_precoverage = max(0.0, min(1.0, float(direction_family_cap_share_precoverage)))
        self.direction_support_weight = float(direction_support_weight)
        self.direction_process_weight = float(direction_process_weight)
        self.direction_verifier_weight = float(direction_verifier_weight)
        self.direction_strategy_diversity_weight = float(direction_strategy_diversity_weight)
        self.direction_single_family_penalty_weight = float(direction_single_family_penalty_weight)
        self.direction_commit_guard_top2_gap_threshold = float(direction_commit_guard_top2_gap_threshold)
        self.enable_typed_strategy_seeded_v1 = bool(enable_typed_strategy_seeded_v1)
        self.enable_reasoning_diversity_bonus_v1 = bool(enable_reasoning_diversity_bonus_v1)
        self.reasoning_diversity_lambda_strategy = float(reasoning_diversity_lambda_strategy)
        self.reasoning_diversity_lambda_operation = float(reasoning_diversity_lambda_operation)
        self.reasoning_diversity_lambda_intermediate = float(reasoning_diversity_lambda_intermediate)
        self.reasoning_diversity_lambda_answer = float(reasoning_diversity_lambda_answer)
        self.reasoning_diversity_lambda_role = float(reasoning_diversity_lambda_role)
        self.reasoning_diversity_lambda_redundancy = float(reasoning_diversity_lambda_redundancy)
        self.enable_family_normalized_rerank_v1 = bool(enable_family_normalized_rerank_v1)
        self.family_rerank_selection_mode = str(family_rerank_selection_mode or "family_normalized_full")
        self.family_rerank_support_weight = float(family_rerank_support_weight)
        self.family_rerank_process_weight = float(family_rerank_process_weight)
        self.family_rerank_verifier_weight = float(family_rerank_verifier_weight)
        self.family_rerank_diversity_weight = float(family_rerank_diversity_weight)
        self.family_rerank_single_family_penalty_weight = float(family_rerank_single_family_penalty_weight)
        self.family_rerank_dominant_family_penalty_weight = float(family_rerank_dominant_family_penalty_weight)
        self._gate_predictor = self._maybe_build_diversity_needed_predictor()
        self.diagnostic_semantic_maturation = bool(diagnostic_semantic_maturation)
        self.diagnostic_semantic_maturation_min_depth = max(0, int(diagnostic_semantic_maturation_min_depth))
        self.diagnostic_branching_necessity_heuristic = bool(diagnostic_branching_necessity_heuristic)
        self.diagnostic_protected_incumbent_release = bool(diagnostic_protected_incumbent_release)
        self.diagnostic_log_semantic_families = bool(diagnostic_log_semantic_families)
        self._last_diagnostic_semantic_snapshot: dict[str, Any] = {}
        self._diagnostic_maturation_phase_active = True
        self._diagnostic_branching_necessity_trace: list[dict[str, Any]] = []
        self.method_name = method_name

    @staticmethod
    def _safe_float(v: Any, default: float = 0.0) -> float:
        try:
            return float(v)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _maybe_numeric_answer(answer: str | None) -> float | None:
        if answer is None:
            return None
        txt = str(answer).strip()
        if re.fullmatch(r"-?\d+(?:\.\d+)?", txt):
            try:
                return float(txt)
            except ValueError:
                return None
        return None

    def _maybe_build_diversity_needed_predictor(self) -> dict[str, Any] | None:
        if self.diversity_needed_gate_mode != "learned":
            return None
        path = Path(self.diversity_needed_gate_dataset_path)
        if not path.exists():
            return None
        rows: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
        if len(rows) < 20:
            return None
        feature_names = [
            "top_minus_second_support_margin",
            "answer_group_entropy",
            "semantic_overlap_mean",
            "duplicate_rate",
            "top_branch_score",
            "second_branch_score",
            "top_second_score_margin",
            "one_step_continuation_best",
            "commit_readiness_q_commit",
            "n_answer_groups",
        ]
        x = np.asarray([[self._safe_float(r.get(c, 0.0)) for c in feature_names] for r in rows], dtype=np.float64)
        y = np.asarray([int(r.get("needs_more_diversity", 0)) for r in rows], dtype=np.int64)
        if len(set(y.tolist())) < 2:
            return None
        mu = x.mean(axis=0)
        sigma = x.std(axis=0) + 1e-8
        xz = (x - mu) / sigma
        clf = LogisticRegression(max_iter=400, random_state=0, class_weight="balanced")
        clf.fit(xz, y)
        return {"feature_names": feature_names, "mu": mu, "sigma": sigma, "clf": clf}

    @staticmethod
    def _normalize_answer(pred: str | None) -> str | None:
        if pred is None:
            return None
        s = str(pred).strip()
        if not s:
            return None
        nums = re.findall(r"[-+]?\d+(?:\.\d+)?", s.replace(",", ""))
        return nums[-1] if nums else s.lower()

    @staticmethod
    def _support_entropy(counts: dict[str, int]) -> float:
        total = sum(counts.values())
        if total <= 0:
            return 0.0
        ent = 0.0
        for c in counts.values():
            p = c / total
            if p > 0:
                ent -= p * math.log(max(p, 1e-9))
        return float(ent)

    @staticmethod
    def _bucketize(value: float, *, edges: tuple[float, float], labels: tuple[str, str, str]) -> str:
        lo, hi = edges
        if value < lo:
            return labels[0]
        if value < hi:
            return labels[1]
        return labels[2]

    def _support_profile_features(self, branch: BranchState) -> set[str]:
        """Compact support-profile features (semantic structure, not lexical novelty)."""
        features: set[str] = set()
        answer_group = self._normalize_answer(branch.predicted_answer) or "__unknown__"
        features.add(f"answer:{answer_group}")
        features.add(f"depth:{self._bucketize(float(branch.depth), edges=(2.0, 5.0), labels=('shallow', 'mid', 'deep'))}")
        features.add(f"score:{self._bucketize(float(branch.score), edges=(0.45, 0.72), labels=('low', 'mid', 'high'))}")
        features.add(
            f"verify:{self._bucketize(float(branch.verify_count), edges=(1.0, 3.0), labels=('none', 'some', 'many'))}"
        )
        if branch.steps:
            text = " ".join(branch.steps[-2:]).lower()
            if re.search(r"\btherefore\b|\bthus\b|\bhence\b|\bso\b", text):
                features.add("reasoning:conclusion_marker")
            if re.search(r"\bif\b|\bassume\b|\bcase\b", text):
                features.add("reasoning:case_analysis")
            if re.search(r"=", text):
                features.add("support:equational")
            if re.search(r"\+", text):
                features.add("support:additive")
            if re.search(r"-", text):
                features.add("support:subtractive")
            if re.search(r"\*", text):
                features.add("support:multiplicative")
            if re.search(r"/", text):
                features.add("support:divisive")
            nums = re.findall(r"[-+]?\d+(?:\.\d+)?", text.replace(",", ""))
            if nums:
                features.add(f"last_num:{nums[-1]}")
        return features

    @staticmethod
    def _jaccard(a: set[str], b: set[str]) -> float:
        if not a and not b:
            return 1.0
        if not a or not b:
            return 0.0
        return float(len(a.intersection(b)) / max(1, len(a.union(b))))

    @staticmethod
    def _question_target_type(question: str) -> str:
        q = str(question).lower()
        if re.search(r"\bhow many times\b|\bnumber of times\b", q):
            return "times"
        if re.search(r"\bgive away\b|\bgave away\b|\boff from\b|\bby how many\b|\bdifference\b", q):
            return "difference"
        if re.search(r"\bleft\b|\bremaining\b|\bremain\b", q):
            return "remaining"
        return "generic"

    def _intermediate_result_flags(self, *, question: str, branch: BranchState) -> dict[str, Any]:
        qtype = self._question_target_type(question)
        last_text = " ".join(branch.steps[-2:]).lower() if branch.steps else ""
        pred = str(branch.predicted_answer or "").lower()
        joined = f"{last_text} {pred}".strip()
        if (not branch.is_done) or (branch.predicted_answer is None):
            return {
                "target_type": qtype,
                "intermediate_result_mismatch": False,
                "intermediate_result_reason": "not_terminal_or_no_answer",
                "has_final_marker": False,
                "has_total_needed_marker": False,
                "has_left_marker": False,
            }
        has_final_marker = bool(re.search(r"\b(final answer|therefore|thus|so\b|answer is)\b", joined))
        total_needed_marker = bool(re.search(r"\b(total|altogether).{0,20}\b(needed|need)\b", joined))
        left_marker = bool(re.search(r"\bleft\b|\bremaining\b", joined))
        divide_or_rate_marker = bool(re.search(r"\bdivide\b|/|\bper\b", joined))
        subtract_marker = bool(re.search(r"\bsubtract\b|\bminus\b|-", joined))
        pred_has_number = bool(re.search(r"[-+]?\d+(?:\.\d+)?", pred))

        mismatch = False
        reason = "none"
        if qtype == "times" and pred_has_number and total_needed_marker and not divide_or_rate_marker and (not has_final_marker):
            mismatch = True
            reason = "times_question_stops_at_total_needed"
        elif qtype == "difference" and pred_has_number and (left_marker or total_needed_marker) and not subtract_marker and (not has_final_marker):
            mismatch = True
            reason = "difference_question_stops_at_intermediate_total_or_left"
        elif qtype == "remaining" and pred_has_number and total_needed_marker and not has_final_marker:
            mismatch = True
            reason = "remaining_question_stops_at_total_needed"
        return {
            "target_type": qtype,
            "intermediate_result_mismatch": bool(mismatch),
            "intermediate_result_reason": reason,
            "has_final_marker": bool(has_final_marker),
            "has_total_needed_marker": bool(total_needed_marker),
            "has_left_marker": bool(left_marker),
        }

    def _branch_quality_surrogates(self, branch: BranchState, *, question: str = "") -> tuple[float, float, dict[str, Any]]:
        completion_score = 1.0 if branch.is_done else min(0.95, 0.20 + 0.12 * float(branch.depth))
        answer_evidence = 1.0 if branch.predicted_answer is not None else min(0.7, max(0.0, float(branch.score)))
        semantic_incompleteness = 0.08 if branch.is_done else 0.55
        completion_flags = self._intermediate_result_flags(question=question, branch=branch)
        if completion_flags["intermediate_result_mismatch"]:
            semantic_incompleteness = min(1.0, semantic_incompleteness + self.intermediate_result_penalty)
        process_quality = compute_process_quality(
            completion_score=completion_score,
            answer_evidence_score=answer_evidence,
            semantic_incompleteness=semantic_incompleteness,
        )
        target_completion = compute_target_completion(
            completion_score=completion_score,
            answer_evidence_score=answer_evidence,
            semantic_incompleteness=semantic_incompleteness,
        )
        return float(process_quality), float(target_completion), completion_flags

    def _compute_coverage_and_overlap(
        self,
        *,
        branch: BranchState,
        answer_support_counts: dict[str, int],
        active_group_counts: dict[str, int],
        group_profiles: dict[str, list[set[str]]],
        global_profiles: list[set[str]],
    ) -> tuple[float, float, dict[str, float]]:
        group = self._normalize_answer(branch.predicted_answer) or "__unknown__"
        support_count = float(answer_support_counts.get(group, 0))
        active_count = float(active_group_counts.get(group, 0))
        total_support = float(sum(answer_support_counts.values()))
        total_active = float(sum(active_group_counts.values()))
        group_mass = support_count + active_count
        group_undercoverage = 1.0 - (group_mass / max(1.0, total_support + total_active))
        new_group_bonus = 1.0 if (support_count <= 0.0 and active_count <= 1.0) else 0.0

        profile = self._support_profile_features(branch)
        same_group_profiles = group_profiles.get(group, [])
        global_max_sim = max((self._jaccard(profile, p) for p in global_profiles), default=0.0)
        group_max_sim = max((self._jaccard(profile, p) for p in same_group_profiles), default=0.0)
        profile_novelty = 1.0 - group_max_sim

        coverage_gain = 0.50 * group_undercoverage + 0.30 * new_group_bonus + 0.20 * profile_novelty
        semantic_overlap = 0.65 * group_max_sim + 0.35 * global_max_sim
        return float(coverage_gain), float(semantic_overlap), {
            "group_undercoverage": float(group_undercoverage),
            "new_group_bonus": float(new_group_bonus),
            "profile_novelty": float(profile_novelty),
            "group_max_similarity": float(group_max_sim),
            "global_max_similarity": float(global_max_sim),
        }

    def _branch_priority(
        self,
        branch: BranchState,
        *,
        answer_support_counts: dict[str, int],
        active_group_counts: dict[str, int],
        group_profiles: dict[str, list[set[str]]],
        global_profiles: list[set[str]],
        question: str = "",
        existing_reasoning_signatures: list[dict[str, Any]] | None = None,
        strategy_family: str | None = None,
    ) -> tuple[float, dict[str, float | str | None]]:
        continuation = float(self.scorer.score_branch(branch))
        group = self._normalize_answer(branch.predicted_answer)
        support_count = answer_support_counts.get(group or "__unknown__", 0)
        active_dups = max(0, active_group_counts.get(group or "__unknown__", 1) - 1)
        diversity_bonus = self.diversity_weight / (1.0 + float(support_count))
        if group is None:
            diversity_bonus += self.unknown_answer_bonus
        duplicate_cost = self.duplicate_penalty * float(active_dups)
        coverage_gain = 0.0
        semantic_overlap = 0.0
        coverage_meta: dict[str, float] = {}
        if self.use_marginal_coverage_overlap:
            coverage_gain, semantic_overlap, coverage_meta = self._compute_coverage_and_overlap(
                branch=branch,
                answer_support_counts=answer_support_counts,
                active_group_counts=active_group_counts,
                group_profiles=group_profiles,
                global_profiles=global_profiles,
            )
        target_alignment_score, target_alignment_meta = self._target_alignment_score(question=question, branch=branch)
        rd_meta: dict[str, float | str | None] = {
            "strategy_family_novelty": 0.0,
            "operation_sequence_novelty": 0.0,
            "intermediate_value_novelty": 0.0,
            "answer_group_novelty": 0.0,
            "reasoning_role_novelty": 0.0,
            "redundancy_penalty": 0.0,
            "plausibility_score": 0.5,
            "useful_reasoning_diversity_bonus": 0.0,
            "reasoning_signature_key": "",
            "operation_sequence_key": "",
            "reasoning_role": "unknown",
            "selected_due_to_reasoning_diversity": 0.0,
            "seen_signature_count_before_selection": float(len(existing_reasoning_signatures or [])),
        }
        rd_bonus = 0.0
        if self.enable_reasoning_diversity_bonus_v1:
            if strategy_family is not None:
                setattr(branch, "strategy_family", strategy_family)
            sig = reasoning_signature(branch, question=question)
            comps = compute_reasoning_diversity_components(sig, existing_reasoning_signatures or [])
            weighted = (
                self.reasoning_diversity_lambda_strategy * float(comps.get("strategy_family_novelty", 0.0))
                + self.reasoning_diversity_lambda_operation * float(comps.get("operation_sequence_novelty", 0.0))
                + self.reasoning_diversity_lambda_intermediate * float(comps.get("intermediate_value_novelty", 0.0))
                + self.reasoning_diversity_lambda_answer * float(comps.get("answer_group_novelty", 0.0))
                + self.reasoning_diversity_lambda_role * float(comps.get("reasoning_role_novelty", 0.0))
                - self.reasoning_diversity_lambda_redundancy * float(comps.get("redundancy_penalty", 0.0))
            )
            rd_bonus = float(weighted) * float(comps.get("plausibility_score", 0.5))
            rd_meta.update({k: float(v) for k, v in comps.items()})
            rd_meta.update(
                {
                    "reasoning_signature_key": str(sig.get("signature_key", "")),
                    "operation_sequence_key": str(sig.get("operation_sequence_key", "")),
                    "reasoning_role": str(sig.get("reasoning_role", "unknown")),
                }
            )
        priority = continuation + diversity_bonus + self.coverage_weight * coverage_gain - self.overlap_weight * semantic_overlap - duplicate_cost + rd_bonus
        rd_meta["final_priority_with_reasoning_diversity"] = float(priority)
        rd_meta["base_priority_score"] = float(continuation + diversity_bonus + self.coverage_weight * coverage_gain - self.overlap_weight * semantic_overlap - duplicate_cost)
        return priority, {
            "continuation_value": continuation,
            "diversity_bonus": diversity_bonus,
            "duplicate_cost": duplicate_cost,
            "coverage_gain": float(coverage_gain),
            "semantic_overlap": float(semantic_overlap),
            "group_key": group,
            "target_alignment_score": float(target_alignment_score),
            "target_alignment_category": str(target_alignment_meta.get("target_alignment_category", "unknown")),
            "target_alignment_reason": str(target_alignment_meta.get("target_alignment_reason", "none")),
            **coverage_meta,
            **rd_meta,
        }

    def _target_alignment_score(self, *, question: str, branch: BranchState) -> tuple[float, dict[str, Any]]:
        flags = self._intermediate_result_flags(question=question, branch=branch)
        score = 0.52
        if branch.predicted_answer is None:
            score -= 0.25
        if branch.is_done:
            score += 0.16
        if bool(flags.get("intermediate_result_mismatch", False)):
            score -= 0.34
        if bool(flags.get("has_final_marker", False)):
            score += 0.10
        if str(flags.get("target_type")) == "times":
            score += 0.03 if bool(re.search(r"\bdivide\b|/|\bper\b", " ".join(branch.steps[-2:]).lower() if branch.steps else "")) else 0.0
        score = float(max(0.0, min(1.0, score)))
        if score < 0.33:
            category = "likely_intermediate_or_mistargeted"
        elif score < 0.60:
            category = "plausible_but_incomplete"
        else:
            category = "likely_target_aligned"
        reason = str(flags.get("intermediate_result_reason", "none"))
        return score, {
            "target_alignment_category": category,
            "target_alignment_reason": reason,
            "target_type": str(flags.get("target_type", "generic")),
        }

    def _anti_collapse_priority_adjustments(
        self,
        *,
        scored: list[tuple[BranchState, float, dict[str, float | str | None]]],
        branch_expansions: dict[str, int],
        active_group_counts: dict[str, int],
        expand_by_group: dict[str, int],
        actions: int,
        last_expanded_branch_id: str | None,
        consecutive_same_branch_expands: int,
        branch_family_ids: dict[str, str],
        last_expanded_family_id: str | None,
        consecutive_same_family_expands: int,
        family_recent_marginal_gains: dict[str, list[float]],
        family_cooldown_until_action: dict[str, int],
        top_support: float,
        case_split_direction_aware_active: bool = False,
    ) -> dict[str, dict[str, float]]:
        if (not self.enable_anti_collapse_answer_group_refinement) or actions >= self.anti_collapse_early_window:
            return {}
        if self.enable_conditional_anti_collapse_activation:
            total_group_expands_for_gate = max(1, sum(int(v) for v in expand_by_group.values()))
            max_group_share = (
                max(float(v) for v in expand_by_group.values()) / float(total_group_expands_for_gate)
                if expand_by_group
                else 0.0
            )
            active_group_count = len([k for k, v in active_group_counts.items() if str(k) != "__unknown__" and int(v) > 0])
            low_coverage_state = active_group_count <= self.conditional_anti_collapse_max_active_groups_for_low_coverage
            high_repeat_state = consecutive_same_family_expands >= self.conditional_anti_collapse_min_consecutive_family_expands
            high_concentration_state = max_group_share >= self.conditional_anti_collapse_max_family_share_trigger
            cond_active = (
                actions >= self.conditional_anti_collapse_min_actions
                and (low_coverage_state or high_repeat_state or high_concentration_state)
            )
            if not cond_active:
                return {}
        continuation_sorted = sorted([float(item[2].get("continuation_value", 0.0)) for item in scored], reverse=True)
        top_cont = continuation_sorted[0] if continuation_sorted else 0.0
        second_cont = continuation_sorted[1] if len(continuation_sorted) > 1 else top_cont
        total_group_expands = max(1, sum(int(v) for v in expand_by_group.values()))

        out: dict[str, dict[str, float]] = {}
        adjusted_priority_by_branch: dict[str, float] = {}
        penalty_triggered_by_branch: dict[str, bool] = {}
        family_by_branch: dict[str, str] = {}
        for branch, _, meta in scored:
            gk = str(meta.get("group_key") or "__unknown__")
            family_id = str(branch_family_ids.get(branch.branch_id) or branch.branch_id)
            family_by_branch[branch.branch_id] = family_id
            continuation = float(meta.get("continuation_value", 0.0))
            repeats = max(0, int(branch_expansions.get(branch.branch_id, 0)) - 1)
            repeat_penalty = self.repeated_same_branch_penalty * float(repeats)

            exact_repeat_steps = 0
            if branch.branch_id == last_expanded_branch_id:
                exact_repeat_steps = max(0, int(consecutive_same_branch_expands) - int(self.repeat_expand_free_steps))
            family_repeat_steps = 0
            if family_id == (last_expanded_family_id or ""):
                family_repeat_steps = max(0, int(consecutive_same_family_expands) - int(self.repeat_expand_free_steps))
            exact_repeat_penalty = self.repeat_expand_penalty_weight * float(exact_repeat_steps)
            family_repeat_penalty = self.repeat_expand_family_penalty_weight * float(family_repeat_steps)
            dominant_repeat_penalty = max(exact_repeat_penalty, family_repeat_penalty)
            if case_split_direction_aware_active and (not self.case_split_direction_aware_disable_repeat_penalty_ablation):
                dominant_repeat_penalty *= self.case_split_direction_aware_repeat_penalty_multiplier
            repeat_signal_source = "none"
            if dominant_repeat_penalty > 0.0:
                repeat_signal_source = "family" if family_repeat_penalty >= exact_repeat_penalty else "exact"
            repeat_penalty += dominant_repeat_penalty
            low_marginal_gain_penalty = 0.0
            low_marginal_gain_triggered = False
            low_marginal_gain_blocked = False
            low_marginal_gain_override = False
            low_marginal_gain_recent_mean = 0.0
            low_marginal_gain_threshold = self.low_marginal_gain_min_threshold
            low_marginal_gain_window_count = 0
            if self.enable_low_marginal_gain_family_cooldown:
                recent = family_recent_marginal_gains.get(family_id, [])
                window = recent[-self.low_marginal_gain_window_size :]
                low_marginal_gain_window_count = len(window)
                low_marginal_gain_recent_mean = float(sum(window) / max(1, len(window))) if window else 0.0
                if self.low_marginal_gain_answer_group_aware:
                    # Answer-group-aware refinement: if this group already has many live siblings,
                    # require higher incremental gain before allowing repeated same-family expansions.
                    group_dup_factor = max(0, int(active_group_counts.get(gk, 1)) - 1)
                    low_marginal_gain_threshold = float(
                        self.low_marginal_gain_min_threshold * (1.0 + 0.20 * float(group_dup_factor))
                    )
                cooldown_active = int(actions) < int(family_cooldown_until_action.get(family_id, -1))
                trigger_from_repeat_low_gain = bool(
                    family_id == (last_expanded_family_id or "")
                    and consecutive_same_family_expands >= self.low_marginal_gain_consecutive_family_trigger
                    and low_marginal_gain_window_count >= self.low_marginal_gain_window_size
                    and low_marginal_gain_recent_mean < low_marginal_gain_threshold
                )
                if trigger_from_repeat_low_gain:
                    # Trigger reason: repeated same-family allocations are not producing enough recent marginal gain.
                    family_cooldown_until_action[family_id] = int(actions) + int(self.low_marginal_gain_cooldown_steps)
                cooldown_active = cooldown_active or bool(
                    int(actions) < int(family_cooldown_until_action.get(family_id, -1))
                )
                low_marginal_gain_triggered = bool(trigger_from_repeat_low_gain or cooldown_active)
                if low_marginal_gain_triggered:
                    low_marginal_gain_penalty = float(self.low_marginal_gain_penalty_strength)
                    if self.low_marginal_gain_hard_block_ablation:
                        low_marginal_gain_blocked = True

            cap_guard_penalty = 0.0
            if (
                branch.branch_id == last_expanded_branch_id
                and consecutive_same_branch_expands >= self.repeated_same_branch_cap
                and (continuation - second_cont) < self.monopolization_margin_requirement
            ):
                cap_guard_penalty = self.repeated_same_branch_penalty + self.monopolization_margin_requirement

            target_alignment = float(meta.get("target_alignment_score", 0.0))
            distinctness_bonus = self.answer_group_distinctness_bonus * target_alignment * (
                1.0 / (1.0 + float(expand_by_group.get(gk, 0)))
            )
            duplicate_group_penalty = self.duplicate_answer_group_penalty * max(0.0, float(active_group_counts.get(gk, 1) - 1))
            unresolved_branch_bonus = 0.0
            if (
                case_split_direction_aware_active
                and (not self.case_split_direction_aware_disable_unresolved_preservation_ablation)
                and (not branch.is_done)
                and branch.predicted_answer is None
            ):
                unresolved_branch_bonus = self.case_split_direction_aware_unresolved_branch_bonus
            out[branch.branch_id] = {
                "repeat_penalty": float(repeat_penalty),
                "repeat_expand_exact_penalty": float(exact_repeat_penalty),
                "repeat_expand_family_penalty": float(family_repeat_penalty),
                "repeat_expand_dominant_penalty": float(dominant_repeat_penalty),
                "repeat_expand_signal_source": 1.0 if repeat_signal_source == "family" else (0.5 if repeat_signal_source == "exact" else 0.0),
                "low_marginal_gain_family_penalty": float(low_marginal_gain_penalty),
                "low_marginal_gain_family_triggered": 1.0 if low_marginal_gain_triggered else 0.0,
                "low_marginal_gain_family_blocked": 1.0 if low_marginal_gain_blocked else 0.0,
                "low_marginal_gain_recent_mean": float(low_marginal_gain_recent_mean),
                "low_marginal_gain_threshold": float(low_marginal_gain_threshold),
                "low_marginal_gain_window_count": float(low_marginal_gain_window_count),
                "cap_guard_penalty": float(cap_guard_penalty),
                "distinctness_bonus": float(distinctness_bonus),
                "duplicate_answer_group_penalty": float(duplicate_group_penalty),
                "unresolved_branch_bonus": float(unresolved_branch_bonus),
                "adjusted_priority_delta": float(
                    distinctness_bonus
                    + unresolved_branch_bonus
                    - repeat_penalty
                    - low_marginal_gain_penalty
                    - cap_guard_penalty
                    - duplicate_group_penalty
                    - (1e6 if low_marginal_gain_blocked else 0.0)
                ),
                "top_continuation": float(top_cont),
                "second_continuation": float(second_cont),
            }
            adjusted_priority_by_branch[branch.branch_id] = float(
                float(meta.get("continuation_value", 0.0))
                + float(meta.get("diversity_bonus", 0.0))
                + self.coverage_weight * float(meta.get("coverage_gain", 0.0))
                - self.overlap_weight * float(meta.get("semantic_overlap", 0.0))
                - float(meta.get("duplicate_cost", 0.0))
                + float(out[branch.branch_id]["adjusted_priority_delta"])
            )
            penalty_triggered_by_branch[branch.branch_id] = bool(dominant_repeat_penalty > 0.0)

        for branch_id, payload in out.items():
            family_id = family_by_branch.get(branch_id, branch_id)
            branch_score = float(adjusted_priority_by_branch.get(branch_id, 0.0))
            best_alt = None
            for alt_branch_id, alt_score in adjusted_priority_by_branch.items():
                if family_by_branch.get(alt_branch_id, alt_branch_id) == family_id:
                    continue
                if best_alt is None or alt_score > best_alt:
                    best_alt = alt_score
            override_applied = False
            low_marginal_gain_override = False
            if penalty_triggered_by_branch.get(branch_id, False) and best_alt is not None:
                if branch_score >= float(best_alt) + float(self.repeat_expand_override_margin):
                    override_applied = True
                    payload["adjusted_priority_delta"] = float(
                        payload["adjusted_priority_delta"] + payload.get("repeat_expand_dominant_penalty", 0.0)
                    )
                    payload["repeat_penalty"] = float(
                        max(
                            0.0,
                            float(payload.get("repeat_penalty", 0.0)) - float(payload.get("repeat_expand_dominant_penalty", 0.0)),
                        )
                    )
            # Override for clearly strong incumbent evidence:
            # if top support is already high and this family still dominates alternatives by margin,
            # allow continuation even when low-marginal-gain cooldown would otherwise penalize it.
            if (
                float(payload.get("low_marginal_gain_family_triggered", 0.0)) > 0.0
                and best_alt is not None
                and top_support >= self.low_marginal_gain_override_top_support_min
            ):
                if branch_score >= float(best_alt) + float(self.low_marginal_gain_override_margin):
                    low_marginal_gain_override = True
                    payload["adjusted_priority_delta"] = float(
                        payload["adjusted_priority_delta"]
                        + float(payload.get("low_marginal_gain_family_penalty", 0.0))
                        + (1e6 if float(payload.get("low_marginal_gain_family_blocked", 0.0)) > 0.0 else 0.0)
                    )
                    payload["low_marginal_gain_family_penalty"] = 0.0
                    payload["low_marginal_gain_family_blocked"] = 0.0
            payload["low_marginal_gain_family_override_applied"] = 1.0 if low_marginal_gain_override else 0.0
            payload["repeat_expand_override_applied"] = 1.0 if override_applied else 0.0
        return out

    def _pick_early_answer_group_preservation_branch(
        self,
        *,
        scored: list[tuple[BranchState, float, dict[str, float | str | None]]],
        answer_support_counts: dict[str, int],
        actions: int,
        hold_steps_used: int,
    ) -> tuple[BranchState | None, dict[str, Any]]:
        if not self.enable_early_answer_group_preservation:
            return None, {"activated": False, "reason": "disabled"}
        if actions >= self.early_preservation_action_window:
            return None, {"activated": False, "reason": "outside_early_window"}
        if hold_steps_used >= self.early_preservation_challenger_hold_steps:
            return None, {"activated": False, "reason": "hold_cap_reached"}
        if len(scored) <= 1:
            return None, {"activated": False, "reason": "no_alternative_branch"}
        if not answer_support_counts:
            return None, {"activated": False, "reason": "insufficient_group_evidence"}
        sorted_counts = sorted(answer_support_counts.values(), reverse=True)
        if len(sorted_counts) < 2:
            return None, {"activated": False, "reason": "only_one_group_observed"}
        support_total = max(1, sum(sorted_counts))
        support_gap = (sorted_counts[0] - sorted_counts[1]) / support_total
        if support_gap < self.early_preservation_required_group_gap:
            return None, {"activated": False, "reason": "no_early_collapse_signal"}

        top_group = max(answer_support_counts.items(), key=lambda kv: kv[1])[0]
        alternatives: list[tuple[BranchState, float, dict[str, float | str | None]]] = []
        for item in scored:
            meta = item[2]
            gk = str(meta.get("group_key") or "__unknown__")
            if gk == top_group:
                continue
            if float(meta.get("continuation_value", 0.0)) < self.early_preservation_min_plausible_continuation:
                continue
            if float(meta.get("target_alignment_score", 0.0)) < self.early_preservation_target_alignment_min:
                continue
            alternatives.append(item)
        if not alternatives:
            return None, {"activated": False, "reason": "no_plausible_target_aligned_alternative", "support_gap": float(support_gap)}
        selected = sorted(
            alternatives,
            key=lambda x: (float(x[2].get("target_alignment_score", 0.0)), float(x[2].get("continuation_value", 0.0)), x[1]),
            reverse=True,
        )[0]
        return selected[0], {
            "activated": True,
            "reason": "protect_undercovered_plausible_answer_group",
            "support_gap": float(support_gap),
            "dominant_group": str(top_group),
            "selected_group": str(selected[2].get("group_key") or "__unknown__"),
            "selected_branch_id": str(selected[0].branch_id),
            "selected_continuation": float(selected[2].get("continuation_value", 0.0)),
            "selected_target_alignment_score": float(selected[2].get("target_alignment_score", 0.0)),
        }

    def _group_maturity_snapshot(self, branches: list[BranchState]) -> dict[str, dict[str, int | bool]]:
        out: dict[str, dict[str, int | bool]] = {}
        for b in branches:
            gk = self._normalize_answer(b.predicted_answer) or "__unknown__"
            row = out.setdefault(
                gk,
                {
                    "support_count": 0,
                    "max_parseable_depth": 0,
                    "has_parseable_depth_ge_2": False,
                    "mature": False,
                },
            )
            parseable = self._normalize_answer(b.predicted_answer) is not None
            if parseable:
                row["support_count"] = int(row["support_count"]) + 1
                depth = int(getattr(b, "depth", len(getattr(b, "steps", []) or [])) or 0)
                row["max_parseable_depth"] = max(int(row["max_parseable_depth"]), depth)
            row["has_parseable_depth_ge_2"] = bool(int(row["max_parseable_depth"]) >= 2)
            row["mature"] = bool(int(row["support_count"]) >= 2 or bool(row["has_parseable_depth_ge_2"]))
        return out

    def _pick_early_answer_diversity_maturation_branch(
        self,
        *,
        scored: list[tuple[BranchState, float, dict[str, float | str | None]]],
        branches: list[BranchState],
        branch_family_ids: dict[str, str],
        branch_expansions: dict[str, int],
        actions: int,
        early_prefix: int,
        recent_groups: list[str],
        recent_families: list[str],
    ) -> tuple[BranchState | None, dict[str, Any]]:
        if not self.enable_early_answer_diversity_maturation_v1:
            return None, {"activated": False, "reason": "disabled"}
        if actions >= early_prefix:
            return None, {"activated": False, "reason": "outside_early_prefix"}
        if len(scored) <= 1:
            return None, {"activated": False, "reason": "no_alternative_branch"}
        maturity = self._group_maturity_snapshot(branches)
        parseable_present = any(
            bool(v.get("support_count", 0)) or bool(v.get("has_parseable_depth_ge_2", False))
            for v in maturity.values()
        )
        family_expansion_counts: dict[str, int] = {}
        for bid, cnt in branch_expansions.items():
            fam = str(branch_family_ids.get(bid) or bid)
            family_expansion_counts[fam] = family_expansion_counts.get(fam, 0) + int(cnt)
        recent_group_set = set(recent_groups[-self.early_answer_diversity_recent_group_window :])
        recent_family_set = set(recent_families[-self.early_answer_diversity_recent_group_window :])
        ranked: list[tuple[tuple[float, float, float, float, float], tuple[BranchState, float, dict[str, float | str | None]]]] = []
        for item in scored:
            b, _, meta = item
            gk = str(meta.get("group_key") or "__unknown__")
            fam = str(branch_family_ids.get(b.branch_id) or b.branch_id)
            unresolved = 0 if bool(getattr(b, "is_done", False)) else 1
            group_info = maturity.get(gk, {})
            is_mature = bool(group_info.get("mature", False))
            continuation = float(meta.get("continuation_value", 0.0))
            fam_expands = int(family_expansion_counts.get(fam, 0))
            depth = int(getattr(b, "depth", len(getattr(b, "steps", []) or [])) or 0)
            if parseable_present:
                key = (
                    float(1 - int(is_mature)),
                    float(1 - int(gk in recent_group_set)),
                    float(-fam_expands),
                    float(continuation),
                    float(-1.0 * (sum(ord(ch) for ch in str(b.branch_id)))),
                )
            else:
                key = (
                    float(1 - int(fam in recent_family_set)),
                    float(unresolved),
                    float(depth),
                    float(-fam_expands),
                    float(continuation),
                )
            ranked.append((key, item))
        ranked.sort(key=lambda x: x[0], reverse=True)
        selected = ranked[0][1]
        selected_branch = selected[0]
        selected_meta = selected[2]
        selected_group = str(selected_meta.get("group_key") or "__unknown__")
        selected_family = str(branch_family_ids.get(selected_branch.branch_id) or selected_branch.branch_id)
        return selected_branch, {
            "activated": True,
            "reason": (
                "prefer_unmatured_answer_group_and_family_diversity"
                if parseable_present
                else "fallback_family_diversity_with_unresolved_depth_proxy"
            ),
            "parseable_groups_present": bool(parseable_present),
            "selected_branch_id": str(selected_branch.branch_id),
            "selected_group": selected_group,
            "selected_group_mature": bool(maturity.get(selected_group, {}).get("mature", False)),
            "selected_group_support_count": int(maturity.get(selected_group, {}).get("support_count", 0)),
            "selected_family": selected_family,
            "selected_family_expansions_pre_action": int(family_expansion_counts.get(selected_family, 0)),
        }

    def _pick_early_answer_diversity_maturation_gated_branch(
        self,
        *,
        scored: list[tuple[BranchState, float, dict[str, float | str | None]]],
        strict_branch: BranchState,
        strict_meta: dict[str, float | str | None],
        branches: list[BranchState],
        branch_family_ids: dict[str, str],
        branch_expansions: dict[str, int],
        answer_support_counts: dict[str, int],
        actions: int,
        early_prefix: int,
        recent_groups: list[str],
        recent_families: list[str],
    ) -> tuple[BranchState | None, dict[str, Any]]:
        if not self.enable_early_answer_diversity_maturation_gated_v1:
            return None, {"considered": False, "applied": False, "triggers": [], "skip_reason": "disabled"}
        if actions >= early_prefix:
            return None, {"considered": False, "applied": False, "triggers": [], "skip_reason": "outside_early_prefix"}
        if len(scored) <= 1:
            return None, {"considered": True, "applied": False, "triggers": [], "skip_reason": "no_alternative_branch"}
        maturity = self._group_maturity_snapshot(branches)
        top_group = max(answer_support_counts.items(), key=lambda kv: kv[1])[0] if answer_support_counts else "__unknown__"
        top_support = int(max(answer_support_counts.values())) if answer_support_counts else 0
        recent_family = str(recent_families[-1]) if recent_families else ""
        recent_group = str(recent_groups[-1]) if recent_groups else ""
        strict_group = str(strict_meta.get("group_key") or "__unknown__")
        strict_family = str(branch_family_ids.get(strict_branch.branch_id) or strict_branch.branch_id)
        strict_immature = not bool(maturity.get(strict_group, {}).get("mature", False))
        strict_answer_distinct = bool(strict_group != top_group and strict_group != recent_group and strict_group != "__unknown__")

        candidate_items = [
            item
            for item in scored
            if str(item[0].branch_id) != str(strict_branch.branch_id)
        ]
        family_expansion_counts: dict[str, int] = {}
        for bid, cnt in branch_expansions.items():
            fam = str(branch_family_ids.get(bid) or bid)
            family_expansion_counts[fam] = family_expansion_counts.get(fam, 0) + int(cnt)
        alt_immature_plausible_exists = any(
            (
                str(item[2].get("group_key") or "__unknown__") != top_group
                and not bool(maturity.get(str(item[2].get("group_key") or "__unknown__"), {}).get("mature", False))
                and float(item[2].get("continuation_value", 0.0)) >= self.early_preservation_min_plausible_continuation
            )
            for item in candidate_items
        )
        admissible_alt_family_exists = any(
            str(branch_family_ids.get(item[0].branch_id) or item[0].branch_id) != strict_family
            for item in candidate_items
        )
        recent_same_family_expands = bool(len(recent_families) >= 2 and recent_families[-1] == recent_families[-2])
        single_family_monopoly = bool(len(recent_families) >= 2 and len(set(recent_families)) == 1 and admissible_alt_family_exists)
        triggers: list[str] = []
        if recent_same_family_expands:
            triggers.append("recent_same_family_expansions_ge_2")
        if top_support >= 2 and alt_immature_plausible_exists:
            triggers.append("top_group_support_ge_2_with_immature_plausible_alternative")
        if single_family_monopoly:
            triggers.append("single_family_monopoly_with_admissible_alternative")
        if not triggers:
            return None, {"considered": True, "applied": False, "triggers": [], "skip_reason": "no_collapse_trigger"}
        if strict_immature and strict_answer_distinct:
            return None, {
                "considered": True,
                "applied": False,
                "triggers": triggers,
                "skip_reason": "strict_branch_already_immature_answer_distinct",
            }
        ranked: list[tuple[tuple[float, float, float, float, float], tuple[BranchState, float, dict[str, float | str | None]]]] = []
        for item in candidate_items:
            b, _, meta = item
            gk = str(meta.get("group_key") or "__unknown__")
            fam = str(branch_family_ids.get(b.branch_id) or b.branch_id)
            continuation = float(meta.get("continuation_value", 0.0))
            is_mature = bool(maturity.get(gk, {}).get("mature", False))
            ranked.append(
                (
                    (
                        float(1 - int(is_mature)),
                        float(1 - int(gk in {top_group, recent_group})),
                        float(1 - int(fam == recent_family)),
                        float(continuation),
                        float(-1.0 * sum(ord(ch) for ch in str(b.branch_id))),
                    ),
                    item,
                )
            )
        if not ranked:
            return None, {"considered": True, "applied": False, "triggers": triggers, "skip_reason": "no_admissible_alternative"}
        ranked.sort(key=lambda x: x[0], reverse=True)
        selected = ranked[0][1]
        return selected[0], {
            "considered": True,
            "applied": True,
            "triggers": triggers,
            "skip_reason": "",
            "selected_branch_id": str(selected[0].branch_id),
            "selected_group": str(selected[2].get("group_key") or "__unknown__"),
        }

    def _group_support_summary(
        self,
        branches: list[BranchState],
        *,
        question: str = "",
    ) -> dict[str, Any]:
        done = [b for b in branches if b.predicted_answer is not None]
        if not done:
            return {
                "groups": {},
                "branch_support_rows": [],
                "top_group": None,
                "top_support": 0.0,
                "second_support": 0.0,
                "support_margin": 0.0,
                "top_group_readiness": 0.0,
                "mean_independence_discount": 1.0,
                "duplicate_discount_applied_rate": 0.0,
            }

        grouped: dict[str, list[BranchState]] = {}
        for b in done:
            key = self._normalize_answer(b.predicted_answer)
            if key is not None:
                grouped.setdefault(key, []).append(b)
        if not grouped:
            return {
                "groups": {},
                "branch_support_rows": [],
                "top_group": None,
                "top_support": 0.0,
                "second_support": 0.0,
                "support_margin": 0.0,
                "top_group_readiness": 0.0,
                "mean_independence_discount": 1.0,
                "duplicate_discount_applied_rate": 0.0,
            }

        all_support_rows: list[dict[str, Any]] = []
        group_summary: dict[str, dict[str, float | int]] = {}
        all_discounts: list[float] = []
        discount_applied = 0
        for gk, members in grouped.items():
            seen_profiles: list[set[str]] = []
            group_support = 0.0
            group_quality = 0.0
            group_readiness = 0.0
            group_best_continuation = 0.0
            for b in sorted(members, key=self.scorer.score_branch, reverse=True):
                process_quality, target_completion, completion_flags = self._branch_quality_surrogates(b, question=question)
                profile = self._support_profile_features(b)
                max_sim = max((self._jaccard(profile, p) for p in seen_profiles), default=0.0)
                independence_discount = 1.0
                if self.use_duplicate_aware_aggregation:
                    independence_discount = max(
                        self.duplicate_discount_floor,
                        1.0 - self.duplicate_discount_strength * max_sim,
                    )
                if independence_discount < 0.999:
                    discount_applied += 1
                seen_profiles.append(profile)
                support_weight = process_quality * target_completion * independence_discount
                group_support += support_weight
                cont_value = float(self.scorer.score_branch(b))
                group_quality += support_weight * cont_value
                group_best_continuation = max(group_best_continuation, cont_value)
                group_readiness += support_weight * target_completion
                all_discounts.append(float(independence_discount))
                all_support_rows.append(
                    {
                        "branch_id": b.branch_id,
                        "group_key": gk,
                        "process_quality": float(process_quality),
                        "target_completion": float(target_completion),
                        "intermediate_result_mismatch": bool(completion_flags.get("intermediate_result_mismatch", False)),
                        "intermediate_result_reason": str(completion_flags.get("intermediate_result_reason", "none")),
                        "independence_discount": float(independence_discount),
                        "support_weight": float(support_weight),
                        "continuation_value": float(self.scorer.score_branch(b)),
                    }
                )
            quality_mean = group_quality / max(1e-8, group_support)
            readiness_mean = group_readiness / max(1e-8, group_support)
            group_summary[gk] = {
                "discounted_support": float(group_support),
                "support_quality_mean": float(quality_mean),
                "readiness_mean": float(readiness_mean),
                "member_count": int(len(members)),
                "best_continuation": float(group_best_continuation),
            }

        ranked = sorted(group_summary.items(), key=lambda kv: float(kv[1]["discounted_support"]), reverse=True)
        top_group = ranked[0][0] if ranked else None
        top_support = float(ranked[0][1]["discounted_support"]) if ranked else 0.0
        second_support = float(ranked[1][1]["discounted_support"]) if len(ranked) > 1 else 0.0
        return {
            "groups": group_summary,
            "branch_support_rows": all_support_rows,
            "top_group": top_group,
            "top_support": float(top_support),
            "second_support": float(second_support),
            "support_margin": float(top_support - second_support),
            "top_group_readiness": float(group_summary.get(top_group, {}).get("readiness_mean", 0.0)),
            "mean_independence_discount": float(sum(all_discounts) / max(1, len(all_discounts))),
            "duplicate_discount_applied_rate": float(discount_applied / max(1, len(all_discounts))),
        }

    def _estimate_one_step_value(self, branches: list[BranchState]) -> float:
        active = [b for b in branches if not b.is_done and not b.is_pruned]
        if not active:
            return 0.0
        return float(max(float(self.scorer.score_branch(b)) for b in active))

    def _direction_verifier_heuristic(
        self,
        *,
        question: str,
        answer_group: str,
        family_count: int,
        support_gap: float,
        family_support_counts: Counter[str] | None = None,
    ) -> tuple[str, float, str]:
        q = (question or "").lower()
        has_order_signal = any(x in q for x in ("order", "arrange", "seating", "line up"))
        has_unordered_signal = any(x in q for x in ("choose", "combination", "group", "pair"))
        has_double_count_risk = any(x in q for x in ("at least", "at most", "different", "distinct", "overlap", "duplicate"))
        has_missing_case_risk = any(x in q for x in ("remaining", "left", "except", "not", "without", "either", "or"))
        fam_counts = family_support_counts or Counter()
        explicit_case_split_support = int(fam_counts.get("explicit_case_split_family", 0))
        enumeration_support = int(fam_counts.get("enumeration_or_decomposition_family", 0))
        direct_only_support = bool(int(fam_counts.get("direct_formula_family", 0)) > 0 and len([k for k, v in fam_counts.items() if int(v) > 0]) == 1)
        sanity_support = int(fam_counts.get("sanity_check_verifier_family", 0))
        score = 0.50
        reasons: list[str] = []
        if has_order_signal and has_unordered_signal:
            score -= 0.08
            reasons.append("ordered_vs_unordered_ambiguity")
        if has_double_count_risk and explicit_case_split_support <= 0 and enumeration_support <= 0:
            score -= 0.06
            reasons.append("double_counting_risk_without_structure")
        if has_missing_case_risk and explicit_case_split_support <= 0 and enumeration_support <= 0:
            score -= 0.05
            reasons.append("missing_case_risk_without_case_coverage")
        if family_count >= 2:
            score += 0.12
            reasons.append("multi_family_support")
        if explicit_case_split_support > 0:
            score += 0.06
            reasons.append("explicit_case_split_support")
        if enumeration_support > 0:
            score += 0.05
            reasons.append("enumeration_or_decomposition_support")
        if direct_only_support:
            score -= 0.07
            reasons.append("direct_formula_only_support")
        if sanity_support > 0:
            score += 0.04
            reasons.append("sanity_check_family_support")
        if support_gap < self.direction_commit_guard_top2_gap_threshold:
            score -= 0.07
            reasons.append("low_support_gap")
        if answer_group == "__unknown__":
            score -= 0.10
            reasons.append("unknown_answer_group")
        score = max(0.0, min(1.0, float(score)))
        if score >= 0.66:
            verdict = "verifier_pass"
        elif score >= 0.42:
            verdict = "verifier_warn"
        else:
            verdict = "verifier_fail"
        return verdict, score, ",".join(reasons) if reasons else "no_issue_detected"

    def _commit_by_answer_group_margin(self, *, branches: list[BranchState], actions: int, question: str = "") -> tuple[bool, dict[str, Any]]:
        summary = self._group_support_summary(branches, question=question)
        one_step_value = self._estimate_one_step_value(branches)
        ready_to_check = actions >= self.min_actions_before_commit_check
        commit = bool(
            ready_to_check
            and summary["top_support"] >= self.commit_top_support_threshold
            and summary["support_margin"] >= self.commit_margin_threshold
            and summary["top_group_readiness"] >= self.commit_readiness_threshold
            and one_step_value <= self.continue_one_step_value_threshold
        )
        return commit, {
            "top_group": summary["top_group"],
            "top_group_support": float(summary["top_support"]),
            "second_group_support": float(summary["second_support"]),
            "answer_group_margin": float(summary["support_margin"]),
            "top_group_readiness": float(summary["top_group_readiness"]),
            "one_step_value_estimate": float(one_step_value),
            "mean_independence_discount": float(summary["mean_independence_discount"]),
            "duplicate_discount_applied_rate": float(summary["duplicate_discount_applied_rate"]),
            "ready_to_check": bool(ready_to_check),
            "commit_rule_satisfied": bool(commit),
        }

    def _final_prediction_from_groups(self, branches: list[BranchState], *, question: str = "") -> tuple[str | None, dict[str, Any]]:
        done = [b for b in branches if b.predicted_answer is not None]
        if not done:
            best = self.scorer.pick_best(branches)
            return (best.predicted_answer if best else None), {
                "selected_group": None,
                "group_support_fraction": 0.0,
                "aggregation_used": False,
                "discounted_group_supports": {},
            }

        summary = self._group_support_summary(done, question=question)
        groups = summary["groups"]
        if not groups:
            best = self.scorer.pick_best(done)
            return (best.predicted_answer if best else None), {
                "selected_group": None,
                "group_support_fraction": 0.0,
                "aggregation_used": False,
                "discounted_group_supports": {},
            }

        total_support = sum(float(v["discounted_support"]) for v in groups.values())
        runtime_family_map: dict[str, str] = getattr(self, "_runtime_branch_strategy_family", {}) or {}
        branch_family_counts_by_group: dict[str, Counter[str]] = defaultdict(Counter)
        family_best_branch_score_by_group: dict[str, dict[str, float]] = defaultdict(dict)
        family_mean_branch_score_by_group: dict[str, dict[str, float]] = defaultdict(dict)
        for b in done:
            gk = self._normalize_answer(b.predicted_answer)
            if gk is None:
                continue
            sf = str(runtime_family_map.get(b.branch_id, "__unknown_family__"))
            branch_family_counts_by_group[gk][sf] += 1
        for gk in groups:
            grouped_by_family: dict[str, list[float]] = defaultdict(list)
            for b in done:
                if self._normalize_answer(b.predicted_answer) != gk:
                    continue
                fam = str(runtime_family_map.get(b.branch_id, "__unknown_family__"))
                grouped_by_family[fam].append(float(self.scorer.score_branch(b)))
            for fam, scores in grouped_by_family.items():
                family_best_branch_score_by_group[gk][fam] = float(max(scores)) if scores else 0.0
                family_mean_branch_score_by_group[gk][fam] = float(sum(scores) / max(1, len(scores)))
        top2_gap = float(summary["support_margin"]) / max(1e-8, float(total_support))
        combi_guard_active = bool(
            self.enable_direction_combinatorics_guard_v1 and classify_problem_type(question) == "counting_combinatorics"
        )
        pre_rerank_selected_group = str(summary["top_group"]) if summary.get("top_group") is not None else None
        best_group_key = pre_rerank_selected_group
        best_group_score = -10.0
        best_group_support = 0.0
        verifier_scores_by_answer_group: dict[str, float] = {}
        verifier_verdicts_by_answer_group: dict[str, str] = {}
        verifier_reason_by_answer_group: dict[str, str] = {}
        final_group_scores_by_answer_group: dict[str, float] = {}
        mean_branch_scores_by_answer_group: dict[str, float] = {}
        best_branch_scores_by_answer_group: dict[str, float] = {}
        raw_support_by_answer_group: dict[str, int] = {}
        family_normalized_support_by_answer_group: dict[str, float] = {}
        num_supporting_strategy_families_by_answer_group: dict[str, int] = {}
        dominant_family_share_by_answer_group: dict[str, float] = {}
        mean_process_score_by_answer_group: dict[str, float] = {}
        mean_verifier_score_by_answer_group: dict[str, float] = {}
        family_representative_scores_by_answer_group: dict[str, dict[str, float]] = defaultdict(dict)
        family_best_verifier_score_by_answer_group: dict[str, dict[str, float]] = defaultdict(dict)
        family_mean_verifier_score_by_answer_group: dict[str, dict[str, float]] = defaultdict(dict)
        family_process_quality_by_answer_group: dict[str, dict[str, float]] = defaultdict(dict)
        for gk, gmeta in groups.items():
            support_fraction = float(gmeta["discounted_support"]) / max(1e-8, total_support)
            quality_mean = float(gmeta["support_quality_mean"])
            readiness_mean = float(gmeta["readiness_mean"])
            base_group_score = (
                self.answer_support_weight * support_fraction
                + self.value_weight * quality_mean
                + self.support_quality_weight * readiness_mean
            )
            group_score = float(base_group_score)
            if combi_guard_active:
                fam_count = int(len(branch_family_counts_by_group.get(gk, {})))
                verdict, verifier_score, verifier_reason = self._direction_verifier_heuristic(
                    question=question,
                    answer_group=str(gk),
                    family_count=fam_count,
                    support_gap=top2_gap,
                    family_support_counts=branch_family_counts_by_group.get(gk, Counter()),
                )
                verifier_scores_by_answer_group[gk] = float(verifier_score)
                verifier_verdicts_by_answer_group[gk] = verdict
                verifier_reason_by_answer_group[gk] = verifier_reason
                diversity_bonus = 1.0 if fam_count >= 2 else 0.0
                single_family_penalty = 1.0 if fam_count <= 1 else 0.0
                process_score = 0.5 * quality_mean + 0.5 * readiness_mean
                group_score = (
                    self.direction_support_weight * support_fraction
                    + self.direction_process_weight * process_score
                    + self.direction_verifier_weight * verifier_score
                    + self.direction_strategy_diversity_weight * diversity_bonus
                    - self.direction_single_family_penalty_weight * single_family_penalty
                )
            members_for_group = [b for b in done if self._normalize_answer(b.predicted_answer) == gk]
            scored_members = [float(self.scorer.score_branch(b)) for b in members_for_group]
            mean_branch_scores_by_answer_group[gk] = float(sum(scored_members) / max(1, len(scored_members)))
            best_branch_scores_by_answer_group[gk] = float(max(scored_members) if scored_members else 0.0)
            raw_support_by_answer_group[gk] = int(gmeta.get("member_count", 0))
            fam_counter = branch_family_counts_by_group.get(gk, Counter())
            family_normalized_support_by_answer_group[gk] = float(sum(min(1.0, float(v)) for v in fam_counter.values()))
            num_supporting_strategy_families_by_answer_group[gk] = int(len([f for f, v in fam_counter.items() if int(v) > 0]))
            dominant_family_share_by_answer_group[gk] = float(
                max(fam_counter.values()) / max(1, sum(fam_counter.values()))
            ) if fam_counter else 0.0
            process_score = 0.5 * quality_mean + 0.5 * readiness_mean
            mean_process_score_by_answer_group[gk] = float(process_score)
            mean_verifier_score_by_answer_group[gk] = float(verifier_scores_by_answer_group.get(gk, 0.5 if combi_guard_active else 0.0))
            for fam, cnt in fam_counter.items():
                family_best = float(family_best_branch_score_by_group.get(gk, {}).get(fam, 0.0))
                family_mean = float(family_mean_branch_score_by_group.get(gk, {}).get(fam, 0.0))
                fam_verifier = float(verifier_scores_by_answer_group.get(gk, 0.5 if combi_guard_active else 0.0))
                family_best_verifier_score_by_answer_group[gk][fam] = fam_verifier
                family_mean_verifier_score_by_answer_group[gk][fam] = fam_verifier
                family_process_quality_by_answer_group[gk][fam] = process_score
                family_representative_scores_by_answer_group[gk][fam] = float(max(family_best, family_mean) + 0.25 * fam_verifier)

        total_family_normalized_support = max(1e-8, sum(family_normalized_support_by_answer_group.values()))
        family_rerank_active = bool(self.enable_family_normalized_rerank_v1)
        selection_mode = str(
            getattr(self, "_runtime_selection_mode_override", None)
            or self.family_rerank_selection_mode
            or "family_normalized_full"
        ) if family_rerank_active else "support_plus_verifier_plus_strategy_diversity"
        for gk in groups:
            support_fraction = float(groups[gk]["discounted_support"]) / max(1e-8, total_support)
            normalized_support_fraction = float(family_normalized_support_by_answer_group.get(gk, 0.0) / total_family_normalized_support)
            diversity_score = float(num_supporting_strategy_families_by_answer_group.get(gk, 0))
            single_family_penalty = 1.0 if int(num_supporting_strategy_families_by_answer_group.get(gk, 0)) <= 1 else 0.0
            dominant_family_penalty = float(dominant_family_share_by_answer_group.get(gk, 0.0))
            verifier_score = float(mean_verifier_score_by_answer_group.get(gk, 0.0))
            process_score = float(mean_process_score_by_answer_group.get(gk, 0.0))
            if not family_rerank_active:
                rerank_score = float(
                    self.direction_support_weight * support_fraction
                    + self.direction_process_weight * process_score
                    + self.direction_verifier_weight * verifier_score
                    + self.direction_strategy_diversity_weight * diversity_score
                    - self.direction_single_family_penalty_weight * single_family_penalty
                )
            elif selection_mode == "raw_support_only":
                rerank_score = float(raw_support_by_answer_group.get(gk, 0))
            elif selection_mode == "family_normalized_support_only":
                rerank_score = normalized_support_fraction
            elif selection_mode == "verifier_only":
                rerank_score = verifier_score
            elif selection_mode == "process_only":
                rerank_score = process_score
            elif selection_mode == "support_plus_verifier":
                rerank_score = support_fraction + verifier_score
            elif selection_mode == "family_normalized_support_plus_verifier":
                rerank_score = normalized_support_fraction + verifier_score
            elif selection_mode == "family_normalized_support_plus_process_plus_verifier":
                rerank_score = normalized_support_fraction + process_score + verifier_score
            else:
                rerank_score = (
                    self.family_rerank_support_weight * normalized_support_fraction
                    + self.family_rerank_process_weight * process_score
                    + self.family_rerank_verifier_weight * verifier_score
                    + self.family_rerank_diversity_weight * diversity_score
                    - self.family_rerank_single_family_penalty_weight * single_family_penalty
                    - self.family_rerank_dominant_family_penalty_weight * dominant_family_penalty
                )
            final_group_scores_by_answer_group[gk] = float(rerank_score)
            if float(rerank_score) > best_group_score:
                best_group_score = float(rerank_score)
                best_group_key = gk
                best_group_support = support_fraction

        if family_rerank_active and selection_mode == "oracle_if_gold_present":
            gold_key = self._normalize_answer(getattr(self, "_runtime_gold_answer_for_selection", None))
            if gold_key is not None and gold_key in groups:
                best_group_key = gold_key

        members = [b for b in done if self._normalize_answer(b.predicted_answer) == best_group_key] if best_group_key is not None else done
        best_member = max(members, key=self.scorer.score_branch)
        pre_guard_group = str(pre_rerank_selected_group) if pre_rerank_selected_group is not None else None
        commit_guard_triggered = bool(
            combi_guard_active
            and (
                len(groups) > 1
                or top2_gap < self.direction_commit_guard_top2_gap_threshold
                or int(len(branch_family_counts_by_group.get(str(best_group_key), {}))) <= 1
            )
        )
        answer_group_support_counts = {k: int(v.get("member_count", 0)) for k, v in groups.items()}
        selected_families = sorted(set(branch_family_counts_by_group.get(str(best_group_key), {}).keys()))
        return best_member.predicted_answer, {
            "selected_group": best_group_key,
            "group_support_fraction": float(best_group_support),
            "group_score": float(best_group_score),
            "aggregation_used": True,
            "num_groups": len(groups),
            "discounted_group_supports": {k: float(v["discounted_support"]) for k, v in groups.items()},
            "answer_group_margin": float(summary["support_margin"]),
            "top_group_readiness": float(summary["top_group_readiness"]),
            "mean_independence_discount": float(summary["mean_independence_discount"]),
            "duplicate_discount_applied_rate": float(summary["duplicate_discount_applied_rate"]),
            "intermediate_result_branch_count": int(
                sum(1 for row in summary.get("branch_support_rows", []) if bool(row.get("intermediate_result_mismatch", False)))
            ),
            "commit_guard_triggered": bool(commit_guard_triggered),
            "commit_guard_reason": (
                "combinatorics_disagreement_or_low_gap_or_single_family"
                if commit_guard_triggered
                else "not_triggered"
            ),
            "verifier_scores_by_answer_group": verifier_scores_by_answer_group if combi_guard_active else {},
            "verifier_verdicts_by_answer_group": verifier_verdicts_by_answer_group if combi_guard_active else {},
            "verifier_reason_by_answer_group": verifier_reason_by_answer_group if combi_guard_active else {},
            "pre_guard_selected_answer_group": pre_guard_group,
            "post_guard_selected_answer_group": best_group_key,
            "pre_rerank_selected_answer_group": pre_rerank_selected_group,
            "post_rerank_selected_answer_group": best_group_key,
            "selection_changed_by_family_rerank": bool(
                pre_rerank_selected_group is not None and str(pre_rerank_selected_group) != str(best_group_key)
            ),
            "selection_mode": selection_mode if family_rerank_active else "legacy_direction_guard_scoring",
            "selected_answer_strategy_families": selected_families,
            "budget_available_for_verifier": True,
            "verifier_used_real_call": False,
            "verifier_used_heuristic": bool(combi_guard_active),
            "selection_changed_by_guard": bool(pre_guard_group is not None and str(pre_guard_group) != str(best_group_key)),
            "correct_answer_strategy_families": [],
            "guard_repaired_case": False,
            "guard_hurt_case": False,
            "top2_support_gap": float(top2_gap),
            "answer_entropy": float(self._support_entropy(answer_group_support_counts)),
            "answer_group_support_counts": answer_group_support_counts,
            "answer_group_strategy_family_counts": {
                str(gk): {str(f): int(c) for f, c in fam_counter.items()}
                for gk, fam_counter in branch_family_counts_by_group.items()
            },
            "raw_support_count_by_answer_group": raw_support_by_answer_group,
            "family_normalized_support_by_answer_group": family_normalized_support_by_answer_group,
            "num_supporting_strategy_families_by_answer_group": num_supporting_strategy_families_by_answer_group,
            "dominant_family_share_by_answer_group": dominant_family_share_by_answer_group,
            "mean_process_score_by_answer_group": mean_process_score_by_answer_group,
            "mean_verifier_score_by_answer_group": mean_verifier_score_by_answer_group,
            "family_best_branch_scores_by_answer_group": family_best_branch_score_by_group,
            "family_mean_branch_scores_by_answer_group": family_mean_branch_score_by_group,
            "family_best_verifier_scores_by_answer_group": family_best_verifier_score_by_answer_group,
            "family_mean_verifier_scores_by_answer_group": family_mean_verifier_score_by_answer_group,
            "family_process_quality_by_answer_group": family_process_quality_by_answer_group,
            "family_representative_scores_by_answer_group": family_representative_scores_by_answer_group,
            "answer_group_final_scores": final_group_scores_by_answer_group,
            "answer_group_mean_branch_scores": mean_branch_scores_by_answer_group,
            "answer_group_best_branch_scores": best_branch_scores_by_answer_group,
        }

    def _incumbent_challenger_commit_state(
        self,
        *,
        branches: list[BranchState],
        incumbent_history: list[str],
        question: str = "",
        actions_used: int = 0,
        near_tie_forced_steps_used: int = 0,
        challenger_repeat_failures: dict[str, int] | None = None,
    ) -> dict[str, Any]:
        summary = self._group_support_summary(branches, question=question)
        groups = summary.get("groups", {})
        if not groups:
            return {
                "state_available": False,
                "commit_ready": False,
                "decision": "fallback_no_groups",
                "formula": "score = w_support*support + w_quality*quality + w_readiness*readiness - redundancy_penalty",
            }
        ranked = sorted(groups.items(), key=lambda kv: float(kv[1].get("discounted_support", 0.0)), reverse=True)
        incumbent_key, incumbent_meta = ranked[0]
        challenger_key, challenger_meta = ranked[1] if len(ranked) > 1 else ranked[0]

        total_eff = sum(float(v.get("discounted_support", 0.0)) for v in groups.values())
        total_raw = sum(float(v.get("member_count", 0)) for v in groups.values())

        def _group_state(k: str, meta: dict[str, Any]) -> dict[str, float | str]:
            raw = float(meta.get("member_count", 0))
            eff = float(meta.get("discounted_support", 0.0))
            quality = float(meta.get("support_quality_mean", 0.0))
            readiness = float(meta.get("readiness_mean", 0.0))
            support_frac_eff = eff / max(1e-8, total_eff)
            support_frac_raw = raw / max(1e-8, total_raw)
            support_component = support_frac_raw if self.incumbent_challenger_raw_support_only else support_frac_eff
            redundancy_proxy = 0.0
            if raw > 0:
                redundancy_proxy = max(0.0, 1.0 - min(1.0, eff / raw))
            incumbent_safety = (
                self.incumbent_score_support_weight * support_component
                + self.incumbent_score_quality_weight * quality
                + self.incumbent_score_readiness_weight * readiness
            )
            if not self.incumbent_challenger_raw_support_only:
                incumbent_safety -= 0.08 * redundancy_proxy
            challenger_upside = max(
                0.0,
                (1.0 - readiness) * 0.55 + max(0.0, float(meta.get("best_continuation", quality)) - incumbent_safety) * 0.45,
            )
            return {
                "group_key": k,
                "raw_support": raw,
                "effective_support": eff,
                "support_fraction_raw": float(support_frac_raw),
                "support_fraction_effective": float(support_frac_eff),
                "support_component_used": float(support_component),
                "best_branch_score": float(
                    max((self.scorer.score_branch(b) for b in branches if self._normalize_answer(b.predicted_answer) == k), default=0.0)
                ),
                "mean_branch_score": float(quality),
                "readiness_mean": float(readiness),
                "redundancy_proxy": float(redundancy_proxy),
                "incumbent_safety": float(max(0.0, min(1.0, incumbent_safety))),
                "challenger_upside": float(max(0.0, min(1.0, challenger_upside))),
            }

        incumbent = _group_state(incumbent_key, incumbent_meta)
        challenger = _group_state(challenger_key, challenger_meta)
        score_margin = float(incumbent["incumbent_safety"] - challenger["incumbent_safety"])
        support_gap = float(incumbent["support_fraction_effective"] - challenger["support_fraction_effective"])
        near_tie = bool(abs(score_margin) <= self.incumbent_challenger_near_tie_gap)
        challenger_plausible = bool(score_margin <= self.incumbent_challenger_plausible_gap or float(challenger["challenger_upside"]) >= self.challenger_upside_commit_max)
        incumbent_changed_recently = bool(len(incumbent_history) >= 2 and incumbent_history[-1] != incumbent_history[-2])
        stable_steps = 1
        for prev in reversed(incumbent_history):
            if prev == incumbent_key:
                stable_steps += 1
            else:
                break
        stability_ok = bool((stable_steps - 1) >= self.incumbent_challenger_stability_min_steps and not incumbent_changed_recently)

        repeat_failures = challenger_repeat_failures or {}
        active = [b for b in branches if not b.is_done and not b.is_pruned]
        incumbent_best_branch = max(
            (b for b in branches if self._normalize_answer(b.predicted_answer) == incumbent_key),
            key=self.scorer.score_branch,
            default=None,
        )
        incumbent_profile = self._support_profile_features(incumbent_best_branch) if incumbent_best_branch is not None else set()
        branch_delta_rows: list[dict[str, Any]] = []
        for b in active:
            cont = float(self.scorer.score_branch(b))
            gk = self._normalize_answer(b.predicted_answer)
            gstate = incumbent if gk == incumbent_key else challenger
            downside_of_commit = max(0.0, float(gstate.get("challenger_upside", 0.0)) - 0.5 * float(incumbent.get("incumbent_safety", 0.0)))
            delta_expand = max(0.0, cont - float(incumbent.get("incumbent_safety", 0.0))) + self.challenger_upside_expand_weight * max(
                0.0, float(gstate.get("challenger_upside", 0.0)) - downside_of_commit
            )
            relative_upside = float(gstate.get("challenger_upside", 0.0)) - float(incumbent.get("challenger_upside", 0.0))
            correlation_proxy = 0.0
            if incumbent_profile:
                correlation_proxy = self._jaccard(self._support_profile_features(b), incumbent_profile)
            repeat_failures_for_group = int(repeat_failures.get(str(gk or "__unknown__"), 0))
            low_margin_flag = bool(relative_upside < self.challenger_min_relative_upside)
            overthrow_score = float(delta_expand)
            if gk != incumbent_key:
                overthrow_score += self.challenger_overthrow_weight * max(0.0, relative_upside)
                overthrow_score -= self.challenger_correlation_penalty * correlation_proxy
                overthrow_score -= self.challenger_repeat_failure_penalty * min(3.0, float(repeat_failures_for_group))
                if low_margin_flag:
                    overthrow_score -= self.challenger_low_margin_penalty
            branch_delta_rows.append(
                {
                    "branch_id": b.branch_id,
                    "group_key": gk,
                    "continuation_value": float(cont),
                    "challenger_upside_component": float(gstate.get("challenger_upside", 0.0)),
                    "delta_expand_vs_commit_now": float(delta_expand),
                    "challenger_overthrow_score": float(overthrow_score),
                    "relative_upside": float(relative_upside),
                    "correlation_proxy_vs_incumbent": float(correlation_proxy),
                    "repeat_failures_for_group": int(repeat_failures_for_group),
                    "low_margin_flag": bool(low_margin_flag),
                }
            )
        branch_delta_rows.sort(key=lambda x: float(x.get("challenger_overthrow_score", x.get("delta_expand_vs_commit_now", 0.0))), reverse=True)
        best_expand_delta = float(branch_delta_rows[0]["delta_expand_vs_commit_now"]) if branch_delta_rows else 0.0
        best_overthrow_score = float(branch_delta_rows[0].get("challenger_overthrow_score", 0.0)) if branch_delta_rows else 0.0
        best_expand_branch_id = str(branch_delta_rows[0]["branch_id"]) if branch_delta_rows else None
        best_challenger_upside = max(
            [float(challenger.get("challenger_upside", 0.0))]
            + [float(x.get("challenger_upside_component", 0.0)) for x in branch_delta_rows],
            default=0.0,
        )

        remaining_budget = max(0, int(self.max_actions - actions_used))
        remaining_ratio = float(remaining_budget / max(1, self.max_actions))
        low_budget = bool(remaining_ratio <= 0.35)
        budget_commit_bonus = self.remaining_budget_commit_bias * (1.0 - remaining_ratio)
        budget_commit_bonus += self.late_stage_commit_bonus if low_budget else 0.0
        extra_near_tie_margin = self.near_tie_commit_margin_extra if near_tie else 0.0
        commit_advantage = float(incumbent["incumbent_safety"]) - best_challenger_upside
        base_stop_threshold = float(self.incumbent_challenger_margin_threshold + extra_near_tie_margin)
        adjusted_stop_threshold = float(max(0.0, base_stop_threshold - budget_commit_bonus))
        continue_gate_value = float(best_expand_delta + self.metalevel_delta_margin + self.stop_continue_value_margin)
        continue_has_min_value = bool(
            self.continue_requires_min_best_value > 0.0 and best_expand_delta >= self.continue_requires_min_best_value
        )
        stop_vs_continue_gate = bool(
            commit_advantage >= adjusted_stop_threshold
            and commit_advantage >= continue_gate_value
            and (not continue_has_min_value or commit_advantage >= (continue_gate_value + 0.01))
        )
        near_tie_hesitation_override = bool(
            self.near_tie_weak_continue_value_cap > 0.0
            and near_tie
            and low_budget
            and (not challenger_plausible)
            and best_expand_delta <= self.near_tie_weak_continue_value_cap
            and commit_advantage >= (adjusted_stop_threshold - self.near_tie_commit_band)
        )
        stop_vs_continue_gate_final = bool(stop_vs_continue_gate or near_tie_hesitation_override)
        commit_ready = bool(
            stop_vs_continue_gate_final
            and stability_ok
            and float(incumbent["incumbent_safety"]) >= self.incumbent_safety_commit_min
            and best_challenger_upside <= self.challenger_upside_commit_max
            and not challenger_plausible
        )
        force_near_tie_explore = bool(
            self.force_extra_explore_on_near_tie
            and near_tie
            and best_challenger_upside > (self.near_tie_force_upside_frac_threshold * self.challenger_upside_commit_max)
            and near_tie_forced_steps_used < self.near_tie_force_max_steps
        )
        continue_selected_challenger = bool(branch_delta_rows and str(branch_delta_rows[0].get("group_key") or "") != str(incumbent_key))
        false_non_stop = bool(
            (not commit_ready)
            and (not force_near_tie_explore)
            and commit_advantage >= adjusted_stop_threshold
            and (best_expand_delta < max(self.continue_requires_min_best_value, 0.02))
            and (not challenger_plausible)
        )
        near_tie_commit_blocked = bool(
            (not commit_ready)
            and near_tie
            and commit_advantage >= (adjusted_stop_threshold - self.near_tie_commit_band)
            and continue_has_min_value
        )
        commit_should_have_happened_before_selected_challenger = bool(
            (not commit_ready)
            and continue_selected_challenger
            and commit_advantage >= adjusted_stop_threshold
            and (best_expand_delta < max(self.continue_requires_min_best_value, 0.05))
        )
        commit_deferred_despite_low_best_continue_value = bool(
            (not commit_ready)
            and (best_expand_delta < self.continue_requires_min_best_value)
        )
        gate_blockers: list[str] = []
        if not stop_vs_continue_gate_final:
            gate_blockers.append("stop_vs_continue_gate_failed")
        if not stability_ok:
            gate_blockers.append("stability_not_ok")
        if float(incumbent["incumbent_safety"]) < self.incumbent_safety_commit_min:
            gate_blockers.append("incumbent_safety_below_min")
        if best_challenger_upside > self.challenger_upside_commit_max:
            gate_blockers.append("challenger_upside_above_max")
        if challenger_plausible:
            gate_blockers.append("challenger_plausible")
        if force_near_tie_explore:
            gate_blockers.append("near_tie_forced_explore")
        near_tie_false_continue = bool(
            (not commit_ready)
            and near_tie
            and low_budget
            and (not challenger_plausible)
            and best_expand_delta <= max(self.near_tie_weak_continue_value_cap, self.continue_requires_min_best_value, 0.03)
        )
        decision = "commit" if commit_ready else ("continue_force_near_tie_step" if force_near_tie_explore else "continue")
        risk_subtypes: list[str] = []
        if summary.get("branch_support_rows"):
            if any(bool(x.get("intermediate_result_mismatch", False)) for x in summary.get("branch_support_rows", [])):
                risk_subtypes.append("committed_to_intermediate_result")
        if near_tie:
            risk_subtypes.append("committed_under_near_tie_ambiguity")
        if best_challenger_upside > self.challenger_upside_commit_max:
            risk_subtypes.append("challenger_had_recoverable_upside")
        if bool(incumbent.get("redundancy_proxy", 0.0) > 0.28):
            risk_subtypes.append("overcounted_weak_corroboration")
        return {
            "state_available": True,
            "decision": decision,
            "commit_ready": bool(commit_ready),
            "incumbent": incumbent,
            "challenger": challenger,
            "score_margin": float(score_margin),
            "incumbent_safety": float(incumbent["incumbent_safety"]),
            "best_challenger_upside": float(best_challenger_upside),
            "effective_support_gap": float(support_gap),
            "near_tie": bool(near_tie),
            "challenger_plausible": bool(challenger_plausible),
            "incumbent_stable_steps": int(max(0, stable_steps - 1)),
            "incumbent_changed_recently": bool(incumbent_changed_recently),
            "stability_ok": bool(stability_ok),
            "challenger_fragmented_flag": bool(len(ranked) >= 3 and float(ranked[1][1].get("discounted_support", 0.0)) < 0.35 * float(ranked[0][1].get("discounted_support", 0.0))),
            "ambiguity_flag": bool(near_tie or summary.get("support_margin", 0.0) <= self.incumbent_challenger_near_tie_gap),
            "near_tie_force_explore": bool(force_near_tie_explore),
            "near_tie_force_steps_used": int(near_tie_forced_steps_used),
            "near_tie_force_max_steps": int(self.near_tie_force_max_steps),
            "remaining_budget": int(remaining_budget),
            "remaining_budget_ratio": float(remaining_ratio),
            "low_budget_stage": bool(low_budget),
            "budget_commit_bonus": float(budget_commit_bonus),
            "stop_threshold_base": float(base_stop_threshold),
            "stop_threshold_adjusted": float(adjusted_stop_threshold),
            "stop_continue_gate_value": float(continue_gate_value),
            "stop_vs_continue_gate": bool(stop_vs_continue_gate),
            "stop_vs_continue_gate_final": bool(stop_vs_continue_gate_final),
            "near_tie_hesitation_override_applied": bool(near_tie_hesitation_override),
            "continue_has_min_best_value": bool(continue_has_min_value),
            "continue_selected_challenger": bool(continue_selected_challenger),
            "false_non_stop": bool(false_non_stop),
            "near_tie_commit_blocked": bool(near_tie_commit_blocked),
            "commit_should_have_happened_before_selected_challenger": bool(commit_should_have_happened_before_selected_challenger),
            "commit_deferred_despite_low_best_continue_value": bool(commit_deferred_despite_low_best_continue_value),
            "near_tie_false_continue": bool(near_tie_false_continue),
            "stop_gate_blockers": gate_blockers,
            "delta_commit_now": float(commit_advantage),
            "best_expand_delta": float(best_expand_delta),
            "best_challenger_overthrow_score": float(best_overthrow_score),
            "best_expand_branch_id": best_expand_branch_id,
            "delta_expand_candidates": branch_delta_rows[: min(4, len(branch_delta_rows))],
            "wrong_commit_risk_subtypes": risk_subtypes,
            "intermediate_result_flags_present": bool(
                any(bool(x.get("intermediate_result_mismatch", False)) for x in summary.get("branch_support_rows", []))
            ),
            "uses_quality_proxy": True,
            "uses_readiness_proxy": True,
            "formula": (
                "incumbent_safety = "
                f"{self.incumbent_score_support_weight:.2f}*support_component + "
                f"{self.incumbent_score_quality_weight:.2f}*support_quality_mean + "
                f"{self.incumbent_score_readiness_weight:.2f}*readiness_mean"
                + (" - 0.08*redundancy_proxy" if not self.incumbent_challenger_raw_support_only else "")
            ),
            "metalevel_target": "choose argmax over {expand(branch_k), commit_now} using delta_vs_commit_now",
            "thresholds": {
                "margin_threshold": float(self.incumbent_challenger_margin_threshold),
                "stability_min_steps": int(self.incumbent_challenger_stability_min_steps),
                "near_tie_gap": float(self.incumbent_challenger_near_tie_gap),
                "challenger_plausible_gap": float(self.incumbent_challenger_plausible_gap),
                "incumbent_safety_commit_min": float(self.incumbent_safety_commit_min),
                "challenger_upside_commit_max": float(self.challenger_upside_commit_max),
                "metalevel_delta_margin": float(self.metalevel_delta_margin),
                "near_tie_commit_margin_extra": float(self.near_tie_commit_margin_extra),
                "near_tie_force_upside_frac_threshold": float(self.near_tie_force_upside_frac_threshold),
                "challenger_overthrow_weight": float(self.challenger_overthrow_weight),
                "challenger_correlation_penalty": float(self.challenger_correlation_penalty),
                "challenger_repeat_failure_penalty": float(self.challenger_repeat_failure_penalty),
                "challenger_min_relative_upside": float(self.challenger_min_relative_upside),
                "challenger_low_margin_penalty": float(self.challenger_low_margin_penalty),
                "stop_continue_value_margin": float(self.stop_continue_value_margin),
                "remaining_budget_commit_bias": float(self.remaining_budget_commit_bias),
                "late_stage_commit_bonus": float(self.late_stage_commit_bonus),
                "near_tie_commit_band": float(self.near_tie_commit_band),
                "continue_requires_min_best_value": float(self.continue_requires_min_best_value),
                "near_tie_weak_continue_value_cap": float(self.near_tie_weak_continue_value_cap),
            },
        }

    def _pick_coverage_floor_branch(
        self,
        *,
        scored: list[tuple[BranchState, float, dict[str, float | str | None]]],
        answer_support_counts: dict[str, int],
        forced_steps_so_far: int,
        actions: int,
        unique_answer_groups_seen: int,
    ) -> tuple[BranchState | None, dict[str, Any]]:
        if not self.enable_answer_group_coverage_floor:
            return None, {"coverage_floor_activated": False, "reason": "disabled"}
        if forced_steps_so_far >= self.coverage_floor_max_forced_steps:
            return None, {"coverage_floor_activated": False, "reason": "forced_step_cap"}
        if actions < self.coverage_floor_min_actions or actions >= self.coverage_floor_max_actions:
            return None, {"coverage_floor_activated": False, "reason": "outside_action_window"}
        if unique_answer_groups_seen >= self.min_answer_groups_before_concentration:
            return None, {"coverage_floor_activated": False, "reason": "coverage_already_satisfied"}

        eligible: list[tuple[BranchState, float, str, float, int, int]] = []
        for branch, priority, meta in scored:
            continuation = float(meta.get("continuation_value", 0.0))
            if continuation < self.coverage_floor_plausibility_threshold:
                continue
            g = str(meta.get("group_key") or "__unknown__")
            support_count = int(answer_support_counts.get(g, 0))
            unseen = 1 if support_count == 0 else 0
            eligible.append((branch, priority, g, continuation, support_count, unseen))
        if not eligible:
            return None, {"coverage_floor_activated": False, "reason": "no_plausible_undercovered_branch"}

        eligible.sort(key=lambda x: (x[5], -x[4], x[1]), reverse=True)
        selected_branch, selected_priority, selected_group, selected_continuation, selected_support_count, selected_unseen = eligible[0]
        return selected_branch, {
            "coverage_floor_activated": True,
            "reason": "plausibility_gated_undercovered_group_forcing",
            "selected_group": selected_group,
            "selected_priority": float(selected_priority),
            "selected_continuation": float(selected_continuation),
            "selected_group_support_count": int(selected_support_count),
            "selected_group_unseen": bool(selected_unseen),
        }

    def _runtime_diversity_needed_features(
        self,
        *,
        scored: list[tuple[BranchState, float, dict[str, float | str | None]]],
        answer_support_counts: dict[str, int],
        group_profiles: dict[str, list[set[str]]],
    ) -> dict[str, float]:
        if not scored:
            return {}
        continuations = sorted([float(meta.get("continuation_value", 0.0)) for _, _, meta in scored], reverse=True)
        top = continuations[0]
        second = continuations[1] if len(continuations) > 1 else continuations[0]
        support_total = max(1, sum(int(v) for v in answer_support_counts.values()))
        top_support = max(answer_support_counts.values()) / support_total if answer_support_counts else 0.0
        support_margin = 0.0
        if answer_support_counts:
            counts = sorted(answer_support_counts.values(), reverse=True)
            second_support = counts[1] if len(counts) > 1 else 0
            support_margin = (counts[0] - second_support) / max(1, support_total)
        profile_similarities: list[float] = []
        for profiles in group_profiles.values():
            for i in range(len(profiles)):
                for j in range(i + 1, len(profiles)):
                    profile_similarities.append(self._jaccard(profiles[i], profiles[j]))
        duplicate_rate = (
            float(sum(1 for s in profile_similarities if s > 0.98) / max(1, len(profile_similarities)))
            if profile_similarities
            else 0.0
        )
        semantic_overlap_mean = float(sum(profile_similarities) / max(1, len(profile_similarities))) if profile_similarities else 0.0
        entropy = self._support_entropy(answer_support_counts)
        return {
            "top_minus_second_support_margin": float(support_margin),
            "answer_group_entropy": float(entropy),
            "semantic_overlap_mean": float(semantic_overlap_mean),
            "duplicate_rate": float(duplicate_rate),
            "top_branch_score": float(top),
            "second_branch_score": float(second),
            "top_second_score_margin": float(top - second),
            "one_step_continuation_best": float(top),
            "commit_readiness_q_commit": float(top_support),
            "n_answer_groups": float(len(answer_support_counts)),
        }

    def _diversity_gate_decision(
        self,
        *,
        scored: list[tuple[BranchState, float, dict[str, float | str | None]]],
        answer_support_counts: dict[str, int],
        active_group_counts: dict[str, int],
        group_profiles: dict[str, list[set[str]]],
    ) -> dict[str, Any]:
        out: dict[str, Any] = {
            "gate_mode": self.diversity_needed_gate_mode,
            "gate_signal": 0.0,
            "gate_decision": "fallback",
            "gate_intervened": False,
        }
        if not scored or self.diversity_needed_gate_mode == "off":
            return out
        features = self._runtime_diversity_needed_features(
            scored=scored,
            answer_support_counts=answer_support_counts,
            group_profiles=group_profiles,
        )
        signal = 0.0
        confidence = 0.0
        if self.diversity_needed_gate_mode == "learned" and self._gate_predictor is not None:
            model = self._gate_predictor
            feature_names = list(model["feature_names"])
            vec = np.asarray([[float(features.get(k, 0.0)) for k in feature_names]], dtype=np.float64)
            xz = (vec - model["mu"]) / model["sigma"]
            prob = float(model["clf"].predict_proba(xz)[0][1])
            signal = prob - 0.5
            confidence = abs(signal)
        elif self.diversity_needed_gate_mode == "heuristic":
            signal = (
                0.70 * float(features.get("answer_group_entropy", 0.0))
                - 0.55 * float(features.get("top_minus_second_support_margin", 0.0))
                + 0.35 * float(features.get("semantic_overlap_mean", 0.0))
            )
            confidence = abs(signal)
        else:
            return out

        out["gate_signal"] = float(signal)
        out["gate_confidence"] = float(confidence)
        out["gate_features"] = features
        if confidence < self.diversity_needed_gate_min_confidence_gap:
            return out
        if signal >= self.diversity_needed_gate_positive_threshold:
            out["gate_decision"] = "favor_diversity"
            return out
        if signal <= self.diversity_needed_gate_negative_threshold:
            out["gate_decision"] = "suppress_diversity_push"
            return out
        return out

    def _branch_family_id(self, branch: BranchState, branch_family_ids: dict[str, str]) -> str:
        return str(branch_family_ids.get(branch.branch_id) or branch.branch_id)

    def _hard_early_root_coverage_forced_diagnostic(
        self,
        *,
        branches: list[BranchState],
        branch_family_ids: dict[str, str],
        root_family_ids: frozenset[str],
        actions_so_far: int,
        max_actions: int,
        force_disabled: bool,
        coverage_target_override: int | None = None,
    ) -> dict[str, Any]:
        """Hard minimum per-root-family expandable depth before cross-family concentration.

        Each initial root (``div_0`` / ``div_1``) defines a *family* id via ``branch_family_ids``.
        Let ``target = hard_early_root_coverage_forced_min_depth`` (typically 2 or 3). While a
        family has any non-done, non-pruned head with ``max(depth) < target``, that family is
        *pending*. Eligible expansions are still ranked by the normal ``scored`` priorities;
        this layer only removes families that already meet the depth quota from the eligible
        set when another root family is still pending (not a fixed BFS order).

        If no expandable heads remain for a family, it is not pending (cannot improve).

        ``coverage_target_override`` (when set) replaces ``hard_early_root_coverage_forced_min_depth``
        for this diagnostic only (used by conditional depth-2-then-gated-depth-3 mode).
        """
        target = int(coverage_target_override) if coverage_target_override is not None else int(self.hard_early_root_coverage_forced_min_depth)
        if force_disabled or target < 2:
            return {
                "enabled": bool(target >= 2 and not force_disabled),
                "hard_early_root_coverage_forced_min_depth": int(target),
                "coverage_target_override": int(coverage_target_override) if coverage_target_override is not None else None,
                "force_disabled": bool(force_disabled),
                "root_families": sorted(root_family_ids),
                "family_status": {},
                "pending_families": [],
                "all_root_families_satisfied": True,
                "actions_needed_sum_lower_bound": 0,
                "remaining_actions_before_step": max(0, int(max_actions) - int(actions_so_far)),
                "release_impossible_under_budget": False,
                "release_low_remaining_budget": False,
            }

        active = [b for b in branches if not b.is_pruned]
        family_status: dict[str, dict[str, Any]] = {}
        pending: list[str] = []
        total_need = 0
        for fam in sorted(root_family_ids):
            heads = [b for b in active if self._branch_family_id(b, branch_family_ids) == fam]
            expandable = [b for b in heads if not b.is_done]
            if not expandable:
                family_status[fam] = {
                    "pending": False,
                    "reason": "no_expandable_heads",
                    "max_depth_among_expandable": None,
                    "actions_needed_lower_bound": 0,
                }
                continue
            max_depth = max(int(b.depth) for b in expandable)
            need = max(0, target - max_depth)
            is_pending = need > 0
            family_status[fam] = {
                "pending": bool(is_pending),
                "reason": f"depth_below_{target}" if is_pending else f"max_expandable_depth_ge_{target}",
                "max_depth_among_expandable": int(max_depth),
                "expandable_head_count": int(len(expandable)),
                "actions_needed_lower_bound": int(need),
            }
            if is_pending:
                pending.append(fam)
                total_need += int(need)

        remaining = max(0, int(max_actions) - int(actions_so_far))
        impossible = bool(len(pending) > 0 and remaining < int(total_need))
        low_rem = bool(
            self.hard_early_coverage_min_remaining_actions_to_release > 0
            and remaining <= int(self.hard_early_coverage_min_remaining_actions_to_release)
        )
        return {
            "enabled": True,
            "hard_early_root_coverage_forced_min_depth": int(target),
            "coverage_target_override": int(coverage_target_override) if coverage_target_override is not None else None,
            "force_disabled": False,
            "root_families": sorted(root_family_ids),
            "family_status": family_status,
            "pending_families": pending,
            "all_root_families_satisfied": len(pending) == 0,
            "actions_needed_sum_lower_bound": int(total_need),
            "remaining_actions_before_step": int(remaining),
            "release_impossible_under_budget": impossible,
            "release_low_remaining_budget": low_rem,
        }

    def _evaluate_conditional_depth3_gate(
        self,
        *,
        answer_support_counts: dict[str, int],
        branch_expansions: dict[str, int],
        branch_family_ids: dict[str, str],
        root_family_ids: frozenset[str],
        branches: list[BranchState],
        scored: list[tuple[BranchState, float, dict[str, float | str | None]]],
        actions_so_far: int,
        max_actions: int,
        expansions: int,
        max_consecutive_same_family_expands: int,
        hard_cov_diag_d2: dict[str, Any],
    ) -> dict[str, Any]:
        """Deterministic gate: whether to continue balanced root coverage to depth 3 after depth 2."""
        support_total = sum(answer_support_counts.values())
        sorted_counts = sorted(answer_support_counts.values(), reverse=True) if answer_support_counts else []
        top_c = int(sorted_counts[0]) if sorted_counts else 0
        second_c = int(sorted_counts[1]) if len(sorted_counts) > 1 else 0
        top_share = float(top_c / support_total) if support_total > 0 else 0.0
        gap_share = float((top_c - second_c) / support_total) if support_total > 0 else 0.0

        crit_a_weak_top = bool(top_share < self.depth3_gate_min_top_answer_support)
        crit_a_weak_gap = bool(gap_share < self.depth3_gate_min_support_gap)
        criterion_a = bool(crit_a_weak_top or crit_a_weak_gap)

        active = [b for b in branches if not b.is_pruned]
        active_root_families = 0
        for fam in root_family_ids:
            heads = [b for b in active if self._branch_family_id(b, branch_family_ids) == fam and not b.is_done]
            if heads:
                active_root_families += 1
        criterion_b = bool(active_root_families >= self.depth3_gate_min_active_root_families)

        family_expands: dict[str, int] = {}
        for bid, cnt in branch_expansions.items():
            fam = str(branch_family_ids.get(bid) or bid)
            family_expands[fam] = family_expands.get(fam, 0) + int(cnt)
        denom = max(1, int(expansions))
        max_family_share = float(max(family_expands.values()) / denom) if family_expands else 0.0
        crit_c_share = bool(max_family_share > self.depth3_gate_max_family_share_trigger)
        crit_c_run = bool(int(max_consecutive_same_family_expands) > int(self.depth3_gate_longest_run_trigger))
        criterion_c = bool(crit_c_share or crit_c_run)

        best_frontier_score = 0.0
        if scored:
            best_frontier_score = max(float(self.scorer.score_branch(it[0])) for it in scored)
        crit_d_frontier = bool(best_frontier_score < self.depth3_gate_min_confident_frontier_score)
        crit_d_support = bool(top_share < self.depth3_gate_min_top_group_support_commit)
        criterion_d = bool(crit_d_frontier or crit_d_support)

        n_groups = len(answer_support_counts)
        crit_e = bool(
            n_groups >= self.depth3_gate_e_min_answer_groups and top_share < self.depth3_gate_e_max_top_support
        )
        criterion_e = bool(crit_e)

        fired = {
            "A_weak_answer_support": criterion_a,
            "B_unresolved_family_ambiguity": criterion_b,
            "C_early_collapse_risk": criterion_c,
            "D_weak_commit_evidence": criterion_d,
            "E_weak_alternatives_shallow_maturity": criterion_e,
        }
        n_fired = int(sum(1 for v in fired.values() if v))
        combine_ab = bool(criterion_a and criterion_b)
        combine_2of5 = bool(n_fired >= 2)
        raw_wants_depth3 = bool(combine_ab or combine_2of5)

        d2_rel_imp = bool(hard_cov_diag_d2.get("release_impossible_under_budget"))
        d3_diag = self._hard_early_root_coverage_forced_diagnostic(
            branches=branches,
            branch_family_ids=branch_family_ids,
            root_family_ids=root_family_ids,
            actions_so_far=actions_so_far,
            max_actions=max_actions,
            force_disabled=False,
            coverage_target_override=3,
        )
        d3_rel_imp = bool(d3_diag.get("release_impossible_under_budget"))
        pending_d3 = list(d3_diag.get("pending_families") or [])

        depth3_status: str
        if not raw_wants_depth3:
            depth3_status = "gated_off"
            combine_depth3 = False
        elif d2_rel_imp:
            depth3_status = "gated_on_but_released_impossible_under_budget"
            combine_depth3 = False
        elif d3_rel_imp and len(pending_d3) > 0:
            depth3_status = "gated_on_but_released_impossible_under_budget"
            combine_depth3 = False
        else:
            depth3_status = "gated_on"
            combine_depth3 = True

        return {
            "criteria_fired": fired,
            "criteria_fired_count": n_fired,
            "combine_rule_2_of_5": combine_2of5,
            "combine_rule_a_and_b": combine_ab,
            "raw_wants_depth3": raw_wants_depth3,
            "combine_depth3": combine_depth3,
            "depth3_release_status": depth3_status,
            "frontier_stats_at_gate": {
                "top_answer_group_support_share": round(top_share, 6),
                "top_minus_second_support_share": round(gap_share, 6),
                "best_frontier_branch_score": round(best_frontier_score, 6),
                "active_root_families_expandable": int(active_root_families),
                "max_family_expansion_share": round(max_family_share, 6),
                "max_consecutive_same_family_expands": int(max_consecutive_same_family_expands),
                "n_answer_groups": int(n_groups),
            },
            "diagnostic_depth3_preview": {
                "pending_families": pending_d3,
                "release_impossible_under_budget": d3_rel_imp,
                "actions_needed_sum_lower_bound": int(d3_diag.get("actions_needed_sum_lower_bound") or 0),
                "remaining_actions_before_step": int(d3_diag.get("remaining_actions_before_step") or 0),
            },
            "diagnostic_depth2_at_gate": {
                "all_root_families_satisfied": bool(hard_cov_diag_d2.get("all_root_families_satisfied")),
                "release_impossible_under_budget": d2_rel_imp,
                "pending_families": list(hard_cov_diag_d2.get("pending_families") or []),
            },
        }

    def _apply_hard_early_root_coverage_forced_override(
        self,
        scored: list[tuple[BranchState, float, dict[str, float | str | None]]],
        *,
        branch: BranchState,
        priority: float,
        pri_meta: dict[str, float | str | None],
        branch_family_ids: dict[str, str],
        diag: dict[str, Any],
        branches: list[BranchState],
    ) -> tuple[BranchState, float, dict[str, float | str | None], dict[str, Any]]:
        """Restrict to pending root families; preserve score order within that eligible set."""
        meta_out: dict[str, Any] = {
            "hard_early_coverage_forced_override": False,
            "hard_early_coverage_override_reason": "inactive_or_satisfied",
            "hard_early_coverage_from_branch_id": None,
            "hard_early_coverage_to_branch_id": None,
        }
        if (not diag.get("enabled")) or diag.get("force_disabled"):
            meta_out["hard_early_coverage_override_reason"] = "disabled"
            return branch, priority, pri_meta, meta_out
        if diag.get("release_impossible_under_budget") or diag.get("release_low_remaining_budget"):
            meta_out["hard_early_coverage_override_reason"] = "released_by_budget_rule"
            return branch, priority, pri_meta, meta_out
        pending = list(diag.get("pending_families") or [])
        if not pending:
            meta_out["hard_early_coverage_override_reason"] = "all_root_families_satisfied"
            return branch, priority, pri_meta, meta_out

        active = [b for b in branches if not b.is_pruned]

        def family_max_expandable_depth(fam: str) -> int:
            heads = [
                b
                for b in active
                if self._branch_family_id(b, branch_family_ids) == fam and (not b.is_done)
            ]
            if not heads:
                return 99
            return max(int(b.depth) for b in heads)

        sel_fam = self._branch_family_id(branch, branch_family_ids)
        if sel_fam in pending:
            meta_out["hard_early_coverage_override_reason"] = "already_on_pending_family"
            return branch, priority, pri_meta, meta_out

        pending_set = set(pending)
        cands = [item for item in scored if self._branch_family_id(item[0], branch_family_ids) in pending_set]
        if not cands:
            meta_out["hard_early_coverage_override_reason"] = "no_scored_candidate_in_pending_families"
            return branch, priority, pri_meta, meta_out

        cands.sort(
            key=lambda it: (
                family_max_expandable_depth(self._branch_family_id(it[0], branch_family_ids)),
                -float(it[1]),
            )
        )
        nb, nprior, nmeta = cands[0]
        meta_out.update(
            {
                "hard_early_coverage_forced_override": True,
                "hard_early_coverage_override_reason": "redirect_from_satisfied_to_pending_root_family",
                "hard_early_coverage_from_branch_id": branch.branch_id,
                "hard_early_coverage_to_branch_id": nb.branch_id,
            }
        )
        return nb, float(nprior), nmeta, meta_out

    def _conditional_family_cap(
        self,
        *,
        family_expansions: dict[str, int],
        selected_family: str,
        answer_support_counts: dict[str, int],
        active_group_counts: dict[str, int],
        active_family_count: int,
        max_consecutive_same_family_expands: int,
        top_support: float,
        hard_cov_diag: dict[str, Any],
        actions_so_far: int,
    ) -> dict[str, Any]:
        base = int(self.hard_max_family_expansions_base_cap)
        out: dict[str, Any] = {
            "mode": self.hard_max_family_expansions_relax_mode,
            "base_cap": base,
            "effective_cap": base,
            "relaxed": False,
            "relax_delta": 0,
            "trigger": "base_only",
            "selected_family_expansions_pre_action": int(family_expansions.get(selected_family, 0)),
        }
        if (not self.enable_hard_max_family_expansions_cap) or self.hard_max_family_expansions_relax_mode == "fixed_k6_control":
            return out
        mode = self.hard_max_family_expansions_relax_mode
        support_total = max(1, sum(answer_support_counts.values()))
        n_groups = len(answer_support_counts)
        breadth_complete = bool(hard_cov_diag.get("all_root_families_satisfied")) and (
            not bool(hard_cov_diag.get("release_impossible_under_budget"))
        )
        collapse_warning = bool(
            max_consecutive_same_family_expands >= self.low_marginal_gain_consecutive_family_trigger
            or top_support >= max(0.78, self.depth3_gate_max_family_share_trigger + 0.10)
        )
        effective = base
        trigger = "base_only"
        if mode == "relax_on_cross_family_coverage_complete":
            if breadth_complete and active_family_count >= 2:
                effective = self.hard_max_family_expansions_relax_cap
                trigger = "coverage_complete"
        elif mode == "relax_on_low_marginal_gain_absence_false":
            if (not collapse_warning) and active_family_count >= 2 and top_support <= 0.82:
                effective = self.hard_max_family_expansions_relax_cap
                trigger = "no_collapse_warning_and_alternatives"
        elif mode == "relax_on_multi_family_maturity":
            if n_groups >= 3 and active_family_count >= 2 and top_support <= 0.75:
                effective = self.hard_max_family_expansions_relax_cap_high
                trigger = "multi_family_maturity_high_relax"
            elif n_groups >= 2 and active_family_count >= 2 and top_support <= 0.82:
                effective = self.hard_max_family_expansions_relax_cap
                trigger = "multi_family_maturity_relax"
        elif mode == "relax_on_high_confidence_incumbent_but_no_challenger_gap":
            sorted_counts = sorted(answer_support_counts.values(), reverse=True)
            top_c = int(sorted_counts[0]) if sorted_counts else 0
            second_c = int(sorted_counts[1]) if len(sorted_counts) > 1 else 0
            support_gap = float((top_c - second_c) / support_total)
            if breadth_complete and top_support >= 0.62 and support_gap <= 0.30 and (not collapse_warning):
                effective = self.hard_max_family_expansions_relax_cap
                trigger = "incumbent_strong_but_challenger_gap_unclear"
        elif mode == "conditional_early_risk_cap":
            early_window = int(actions_so_far) < int(self.hard_max_family_expansions_conditional_early_window_actions)
            risk_triggered = bool(
                max_consecutive_same_family_expands >= self.hard_max_family_expansions_conditional_risk_consecutive_run_trigger
                or top_support >= self.hard_max_family_expansions_conditional_risk_family_share_trigger
            )
            if (not early_window) or (not risk_triggered) or active_family_count < 2:
                effective = self.hard_max_family_expansions_relax_cap
                trigger = "conditional_relaxed_nonrisk_or_late"
            else:
                trigger = "conditional_tight_cap_on_early_risk"
        elif mode == "conditional_early_risk_cap_with_rival_maturation":
            early_window = int(actions_so_far) < int(self.hard_max_family_expansions_conditional_early_window_actions)
            risk_triggered = bool(
                max_consecutive_same_family_expands >= self.hard_max_family_expansions_conditional_risk_consecutive_run_trigger
                or top_support >= self.hard_max_family_expansions_conditional_risk_family_share_trigger
            )
            rival_expands = [
                int(v) for fam, v in family_expansions.items() if str(fam) != str(selected_family)
            ]
            rival_mature = bool(
                rival_expands
                and max(rival_expands) >= int(self.hard_max_family_expansions_conditional_min_rival_maturity_expansions)
            )
            if (not early_window) or (not risk_triggered) or active_family_count < 2 or rival_mature:
                effective = self.hard_max_family_expansions_relax_cap
                trigger = "conditional_relaxed_rival_mature_or_nonrisk_or_late"
            else:
                trigger = "conditional_tight_cap_wait_rival_maturity"
        out["effective_cap"] = int(effective)
        out["relaxed"] = bool(effective > base)
        out["relax_delta"] = int(effective - base)
        out["trigger"] = trigger
        return out

    def run(self, question: str, gold_answer: str) -> MethodResult:
        forced_action_plan_raw = getattr(self, "_forced_action_plan", {}) or {}
        forced_action_plan: dict[int, str] = {}
        for k, v in dict(forced_action_plan_raw).items():
            try:
                forced_action_plan[int(k)] = str(v)
            except (TypeError, ValueError):
                continue
        actions = expansions = verifications = 0
        surviving_trace: list[int] = []
        action_trace: list[dict[str, Any]] = []
        branch_expansions: dict[str, int] = {}
        branches: list[BranchState] = [self.generator.init_branch("div_0"), self.generator.init_branch("div_1")]
        branch_family_ids: dict[str, str] = {branches[0].branch_id: branches[0].branch_id, branches[1].branch_id: branches[1].branch_id}
        strategy_families = [
            "direct_formula_family",
            "explicit_case_split_family",
            "enumeration_or_decomposition_family",
            "small_example_pattern_family",
            "sanity_check_verifier_family",
        ]
        branch_strategy_family: dict[str, str] = {}
        branch_strategy_prompt_obj: dict[str, TypedStrategyPrompt] = {}
        branch_strategy_prompt_text: dict[str, str] = {}
        branch_strategy_seed_order: dict[str, int] = {}
        for idx, b in enumerate(branches):
            branch_strategy_family[b.branch_id] = strategy_families[idx % len(strategy_families)]
            branch_strategy_seed_order[b.branch_id] = idx
        family_expansions_by_strategy: dict[str, int] = {k: 0 for k in strategy_families}
        direction_guard_triggered_count = 0
        family_cap_blocked_expansion = 0
        family_min_coverage_forced_expansion = 0
        commit_guard_triggered_count = 0
        verifier_calls = 0
        verifier_pass = 0
        verifier_warn = 0
        verifier_fail = 0
        selected_family_at_commit: str | None = None
        answer_support_counts: dict[str, int] = {}
        group_profiles: dict[str, list[set[str]]] = {}
        global_profiles: list[set[str]] = []
        expand_by_group: dict[str, int] = {}
        forced_explore_steps = 0
        coverage_floor_forced_steps = 0
        commit_checks: list[dict[str, Any]] = []
        incumbent_challenger_checks: list[dict[str, Any]] = []
        incumbent_history: list[str] = []
        challenger_repeat_failures: dict[str, int] = {}
        challenger_selection_events: list[dict[str, Any]] = []
        commit_triggered = False
        incumbent_commit_triggered = False
        self._last_diagnostic_semantic_snapshot = {}
        self._diagnostic_maturation_phase_active = bool(self.diagnostic_semantic_maturation)
        self._diagnostic_branching_necessity_trace = []
        near_tie_forced_steps_used = 0
        early_preservation_forced_steps = 0
        early_prefix = min(3, max(1, int(self.max_actions // 2)))
        early_maturation_actions = 0
        early_groups_seen_order: list[str] = []
        early_families_seen_order: list[str] = []
        early_gated_override_considered = 0
        early_gated_override_applied = 0
        early_gated_override_triggers: Counter[str] = Counter()
        early_gated_override_skipped_reasons: Counter[str] = Counter()
        width_depth_forced_width_steps = 0
        width_depth_forced_challenger_maturation_steps = 0
        uncertainty_verify_steps = 0
        near_miss_correction_activation_count = 0
        near_miss_correction_forced_expand_count = 0
        last_expanded_branch_id: str | None = None
        consecutive_same_branch_expands = 0
        max_consecutive_same_branch_expands = 0
        last_expanded_family_id: str | None = None
        consecutive_same_family_expands = 0
        max_consecutive_same_family_expands = 0
        repeated_same_branch_expansion_count = 0
        repeated_same_family_expansion_count = 0
        repeat_penalty_trigger_count = 0
        repeat_penalty_override_count = 0
        repeat_penalty_alternative_selected_count = 0
        family_recent_marginal_gains: dict[str, list[float]] = {}
        family_cooldown_until_action: dict[str, int] = {}
        low_marginal_gain_trigger_count = 0
        low_marginal_gain_block_count = 0
        low_marginal_gain_override_count = 0
        family_cap_block_count = 0
        family_cap_relax_activation_count = 0
        family_cap_relax_delta_sum = 0
        family_cap_activation_by_trigger: dict[str, int] = {}
        protected_alternatives: dict[str, dict[str, int | str | float]] = {}
        protected_alternative_ids: set[str] = set()
        matured_alternative_ids: set[str] = set()
        gold_group_key = self._normalize_answer(gold_answer) or "__unknown__"
        early_divergence_timeline: list[dict[str, Any]] = []
        root_family_ids: frozenset[str] = frozenset(
            {branch_family_ids[branches[0].branch_id], branch_family_ids[branches[1].branch_id]}
        )
        hard_early_coverage_force_disabled = False
        hard_early_coverage_budget_released_impossible = False
        hard_early_coverage_budget_released_low_remaining = False
        hard_early_coverage_forced_override_steps = 0
        hard_early_coverage_transition_actions_used: int | None = None
        cond_phase: str | None = "depth2" if self.enable_hard_early_root_depth2_then_conditional_depth3_v1 else None
        cond_gate_evaluated = False
        cond_gate_record: dict[str, Any] | None = None
        cond_depth3_completed = False
        cond_depth2_gate_actions: int | None = None
        problem_type_label = classify_problem_type(question)
        combinatorics_guard_active = bool(
            self.enable_direction_combinatorics_guard_v1 and problem_type_label == "counting_combinatorics"
        )
        typed_seeded_active = bool(self.enable_typed_strategy_seeded_v1 and problem_type_label == "counting_combinatorics")
        if typed_seeded_active:
            typed_prompts = get_typed_strategy_prompts(question, problem_type_label)
            if typed_prompts:
                branches = [self.generator.init_branch(f"typed_{i}") for i in range(len(typed_prompts))]
                branch_family_ids = {b.branch_id: b.branch_id for b in branches}
                root_family_ids = frozenset(branch_family_ids.values())
                branch_strategy_family = {}
                branch_strategy_prompt_obj = {}
                branch_strategy_prompt_text = {}
                branch_strategy_seed_order = {}
                family_expansions_by_strategy = {tp.strategy_family: 0 for tp in typed_prompts}
                for i, b in enumerate(branches):
                    tp = typed_prompts[i]
                    branch_strategy_family[b.branch_id] = tp.strategy_family
                    branch_strategy_prompt_obj[b.branch_id] = tp
                    branch_strategy_prompt_text[b.branch_id] = tp.strategy_prompt
                    branch_strategy_seed_order[b.branch_id] = i
                strategy_families = [tp.strategy_family for tp in typed_prompts]
        question_shape_label = "unknown" if self.case_split_direction_aware_detector_off else classify_question_shape(question)
        case_split_direction_aware_active = bool(
            self.enable_case_split_direction_aware_v1 and (question_shape_label in self.case_split_direction_aware_labels)
        )
        case_split_direction_aware_forced_coverage_steps = 0
        case_split_direction_aware_delay_commit_blocks = 0
        reasoning_signatures_seen: list[dict[str, Any]] = []

        while actions < self.max_actions and branches:
            active = [b for b in branches if not b.is_pruned]
            if not active:
                break

            active_group_counts: dict[str, int] = {}
            for b in active:
                g = self._normalize_answer(b.predicted_answer) or "__unknown__"
                active_group_counts[g] = active_group_counts.get(g, 0) + 1

            scored: list[tuple[BranchState, float, dict[str, float | str | None]]] = []
            for b in active:
                priority, meta = self._branch_priority(
                    b,
                    answer_support_counts=answer_support_counts,
                    active_group_counts=active_group_counts,
                    group_profiles=group_profiles,
                    global_profiles=global_profiles,
                    question=question,
                    existing_reasoning_signatures=reasoning_signatures_seen,
                    strategy_family=str(branch_strategy_family.get(b.branch_id, "direct_formula_family")),
                )
                scored.append((b, priority, meta))
            anti_collapse_adjustments = self._anti_collapse_priority_adjustments(
                scored=scored,
                branch_expansions=branch_expansions,
                active_group_counts=active_group_counts,
                expand_by_group=expand_by_group,
                actions=actions,
                last_expanded_branch_id=last_expanded_branch_id,
                consecutive_same_branch_expands=consecutive_same_branch_expands,
                branch_family_ids=branch_family_ids,
                last_expanded_family_id=last_expanded_family_id,
                consecutive_same_family_expands=consecutive_same_family_expands,
                family_recent_marginal_gains=family_recent_marginal_gains,
                family_cooldown_until_action=family_cooldown_until_action,
                top_support=float(max(answer_support_counts.values()) / max(1, sum(answer_support_counts.values())) if answer_support_counts else 0.0),
                case_split_direction_aware_active=case_split_direction_aware_active,
            )
            raw_priority_sorted = sorted(scored, key=lambda x: x[1], reverse=True)
            scored = [
                (
                    b,
                    float(
                        p
                        + float(anti_collapse_adjustments.get(b.branch_id, {}).get("adjusted_priority_delta", 0.0))
                    ),
                    m,
                )
                for (b, p, m) in scored
            ]
            scored.sort(key=lambda x: x[1], reverse=True)
            raw_top_branch = raw_priority_sorted[0][0] if raw_priority_sorted else None
            if raw_top_branch is not None:
                raw_top_adj = anti_collapse_adjustments.get(raw_top_branch.branch_id, {})
                if bool(float(raw_top_adj.get("repeat_expand_dominant_penalty", 0.0)) > 0.0):
                    repeat_penalty_trigger_count += 1
                    if scored and scored[0][0].branch_id != raw_top_branch.branch_id:
                        repeat_penalty_alternative_selected_count += 1
                if bool(float(raw_top_adj.get("repeat_expand_override_applied", 0.0)) > 0.0):
                    repeat_penalty_override_count += 1
                if bool(float(raw_top_adj.get("low_marginal_gain_family_triggered", 0.0)) > 0.0):
                    low_marginal_gain_trigger_count += 1
                if bool(float(raw_top_adj.get("low_marginal_gain_family_blocked", 0.0)) > 0.0):
                    low_marginal_gain_block_count += 1
                if bool(float(raw_top_adj.get("low_marginal_gain_family_override_applied", 0.0)) > 0.0):
                    low_marginal_gain_override_count += 1
            branch, priority, pri_meta = scored[0]
            gate_meta = self._diversity_gate_decision(
                scored=scored,
                answer_support_counts=answer_support_counts,
                active_group_counts=active_group_counts,
                group_profiles=group_profiles,
            )
            if gate_meta.get("gate_decision") == "favor_diversity":
                top_group = None
                if answer_support_counts:
                    top_group = max(answer_support_counts.items(), key=lambda kv: kv[1])[0]
                diverse_candidates: list[tuple[BranchState, float, dict[str, float | str | None]]] = []
                for item in scored:
                    gk = str(item[2].get("group_key") or "__unknown__")
                    if top_group is not None and gk == top_group:
                        continue
                    diverse_candidates.append(item)
                if diverse_candidates:
                    branch, priority, pri_meta = diverse_candidates[0]
                    gate_meta["gate_intervened"] = bool(branch.branch_id != scored[0][0].branch_id)
                    gate_meta["gate_selected_branch_id"] = branch.branch_id
            elif gate_meta.get("gate_decision") == "suppress_diversity_push":
                scored_by_cont = sorted(scored, key=lambda x: float(x[2].get("continuation_value", 0.0)), reverse=True)
                if scored_by_cont:
                    branch, priority, pri_meta = scored_by_cont[0]
                    gate_meta["gate_intervened"] = bool(branch.branch_id != scored[0][0].branch_id)
                    gate_meta["gate_selected_branch_id"] = branch.branch_id
            coverage_floor_meta: dict[str, Any] = {"coverage_floor_activated": False}
            floor_branch, floor_meta = self._pick_coverage_floor_branch(
                scored=scored,
                answer_support_counts=answer_support_counts,
                forced_steps_so_far=coverage_floor_forced_steps,
                actions=actions,
                unique_answer_groups_seen=len(answer_support_counts),
            )
            if floor_branch is not None and floor_branch.branch_id != branch.branch_id:
                selected = next((item for item in scored if item[0].branch_id == floor_branch.branch_id), None)
                if selected is not None:
                    branch, priority, pri_meta = selected
                    coverage_floor_meta = floor_meta
                    coverage_floor_forced_steps += 1
            elif floor_meta.get("coverage_floor_activated", False):
                coverage_floor_meta = floor_meta

            early_preservation_meta: dict[str, Any] = {"activated": False}
            preservation_branch, preservation_meta = self._pick_early_answer_group_preservation_branch(
                scored=scored,
                answer_support_counts=answer_support_counts,
                actions=actions,
                hold_steps_used=early_preservation_forced_steps,
            )
            if preservation_branch is not None and preservation_branch.branch_id != branch.branch_id:
                selected = next((item for item in scored if item[0].branch_id == preservation_branch.branch_id), None)
                if selected is not None:
                    branch, priority, pri_meta = selected
                    early_preservation_forced_steps += 1
                    early_preservation_meta = preservation_meta
            elif preservation_meta.get("activated", False):
                early_preservation_meta = preservation_meta
            early_maturation_meta: dict[str, Any] = {"activated": False, "reason": "disabled"}
            maturation_branch, maturation_meta = self._pick_early_answer_diversity_maturation_branch(
                scored=scored,
                branches=branches,
                branch_family_ids=branch_family_ids,
                branch_expansions=branch_expansions,
                actions=actions,
                early_prefix=early_prefix,
                recent_groups=early_groups_seen_order,
                recent_families=early_families_seen_order,
            )
            if maturation_branch is not None and maturation_branch.branch_id != branch.branch_id:
                selected = next((item for item in scored if item[0].branch_id == maturation_branch.branch_id), None)
                if selected is not None:
                    branch, priority, pri_meta = selected
            if bool(maturation_meta.get("activated", False)):
                early_maturation_meta = maturation_meta
            gated_override_meta: dict[str, Any] = {
                "considered": False,
                "applied": False,
                "triggers": [],
                "skip_reason": "disabled",
            }
            gated_branch, gated_meta = self._pick_early_answer_diversity_maturation_gated_branch(
                scored=scored,
                strict_branch=branch,
                strict_meta=pri_meta,
                branches=branches,
                branch_family_ids=branch_family_ids,
                branch_expansions=branch_expansions,
                answer_support_counts=answer_support_counts,
                actions=actions,
                early_prefix=early_prefix,
                recent_groups=early_groups_seen_order,
                recent_families=early_families_seen_order,
            )
            gated_override_meta = gated_meta
            if bool(gated_meta.get("considered", False)):
                early_gated_override_considered += 1
            for trig in list(gated_meta.get("triggers", []) or []):
                early_gated_override_triggers[str(trig)] += 1
            skip_reason = str(gated_meta.get("skip_reason") or "")
            if skip_reason:
                early_gated_override_skipped_reasons[skip_reason] += 1
            if gated_branch is not None and gated_branch.branch_id != branch.branch_id:
                selected = next((item for item in scored if item[0].branch_id == gated_branch.branch_id), None)
                if selected is not None:
                    branch, priority, pri_meta = selected
                    if bool(gated_meta.get("applied", False)):
                        early_gated_override_applied += 1
            if (
                self.enable_anti_collapse_answer_group_refinement
                and bool(early_preservation_meta.get("activated", False))
                and float(early_preservation_meta.get("selected_target_alignment_score", 0.0))
                >= self.protected_alternative_target_alignment_min
            ):
                pbid = str(early_preservation_meta.get("selected_branch_id") or "")
                if pbid:
                    protected_alternative_ids.add(pbid)
                    protected_alternatives.setdefault(
                        pbid,
                        {
                            "remaining": int(self.min_followup_steps_for_preserved_alternative),
                            "expires_at": int(actions + self.alternative_maturity_window),
                            "selected_group": str(early_preservation_meta.get("selected_group") or "__unknown__"),
                        },
                    )

            if self.enable_anti_collapse_answer_group_refinement:
                eligible_protected = [
                    item
                    for item in scored
                    if item[0].branch_id in protected_alternatives
                    and int(protected_alternatives[item[0].branch_id].get("remaining", 0)) > 0
                    and actions <= int(protected_alternatives[item[0].branch_id].get("expires_at", -1))
                ]
                if eligible_protected:
                    eligible_protected.sort(
                        key=lambda x: (
                            int(protected_alternatives[x[0].branch_id].get("remaining", 0)),
                            float(x[2].get("target_alignment_score", 0.0)),
                            x[1],
                        ),
                        reverse=True,
                    )
                    chosen = eligible_protected[0]
                    if chosen[0].branch_id != branch.branch_id:
                        branch, priority, pri_meta = chosen

            width_depth_meta: dict[str, Any] = {"activated": False, "reason": "disabled"}
            if self.enable_width_depth_allocation_guard and actions >= self.width_depth_min_actions and scored:
                top_cont = max(float(item[2].get("continuation_value", 0.0)) for item in scored)
                family_expansions: dict[str, int] = {}
                for bid, cnt in branch_expansions.items():
                    fam = str(branch_family_ids.get(bid) or bid)
                    family_expansions[fam] = family_expansions.get(fam, 0) + int(cnt)
                selected_family = str(branch_family_ids.get(branch.branch_id) or branch.branch_id)
                should_force_width = bool(
                    consecutive_same_family_expands >= self.width_depth_repeat_family_trigger
                    and selected_family == (last_expanded_family_id or selected_family)
                )
                if should_force_width:
                    challenger_candidates = []
                    for item in scored:
                        cand = item[0]
                        cand_family = str(branch_family_ids.get(cand.branch_id) or cand.branch_id)
                        if cand_family == selected_family:
                            continue
                        cont = float(item[2].get("continuation_value", 0.0))
                        if cont < self.width_depth_min_relative_continuation * max(1e-6, top_cont):
                            continue
                        cand_expands = int(branch_expansions.get(cand.branch_id, 0))
                        fam_expands = int(family_expansions.get(cand_family, 0))
                        need = max(0, self.width_depth_challenger_maturation_min_expands - cand_expands)
                        challenger_candidates.append((need, -cont, fam_expands, item))
                    if challenger_candidates:
                        challenger_candidates.sort(key=lambda x: (x[0], x[1], x[2]))
                        chosen = challenger_candidates[0][3]
                        if chosen[0].branch_id != branch.branch_id:
                            width_depth_meta = {
                                "activated": True,
                                "reason": "force_width_from_monopolization",
                                "chosen_branch_id": chosen[0].branch_id,
                                "chosen_family_id": str(branch_family_ids.get(chosen[0].branch_id) or chosen[0].branch_id),
                                "selected_family_id": selected_family,
                                "consecutive_same_family_expands": int(consecutive_same_family_expands),
                            }
                            width_depth_forced_width_steps += 1
                            if int(branch_expansions.get(chosen[0].branch_id, 0)) < self.width_depth_challenger_maturation_min_expands:
                                width_depth_forced_challenger_maturation_steps += 1
                            branch, priority, pri_meta = chosen

            if combinatorics_guard_active and scored:
                required_families = 2 if self.max_actions < 6 else 3
                seen_families = {
                    fam
                    for fam, cnt in family_expansions_by_strategy.items()
                    if int(cnt) > 0
                }
                selected_strategy_family = str(branch_strategy_family.get(branch.branch_id, "direct_formula_family"))
                selected_cnt = int(family_expansions_by_strategy.get(selected_strategy_family, 0))
                dominant_share = (
                    selected_cnt / max(1, sum(int(v) for v in family_expansions_by_strategy.values()))
                )
                missing_families = [
                    fam for fam in strategy_families if fam not in seen_families
                ]
                if len(seen_families) < required_families and missing_families:
                    alt = next(
                        (
                            item
                            for item in scored
                            if str(branch_strategy_family.get(item[0].branch_id, "direct_formula_family")) in missing_families
                        ),
                        None,
                    )
                    if alt is not None and alt[0].branch_id != branch.branch_id:
                        branch, priority, pri_meta = alt
                        selected_strategy_family = str(branch_strategy_family.get(branch.branch_id, "direct_formula_family"))
                        direction_guard_triggered_count += 1
                        family_min_coverage_forced_expansion += 1
                if (
                    len(seen_families) < required_families
                    and dominant_share > self.direction_family_cap_share_precoverage
                ):
                    alt = next(
                        (
                            item
                            for item in scored
                            if str(branch_strategy_family.get(item[0].branch_id, "direct_formula_family")) != selected_strategy_family
                        ),
                        None,
                    )
                    if alt is not None and alt[0].branch_id != branch.branch_id:
                        branch, priority, pri_meta = alt
                        direction_guard_triggered_count += 1
                        family_cap_blocked_expansion += 1

            cov_override: int | None = None
            if self.enable_hard_early_root_depth2_then_conditional_depth3_v1 and cond_phase == "depth2":
                cov_override = 2
            elif self.enable_hard_early_root_depth2_then_conditional_depth3_v1 and cond_phase == "depth3":
                cov_override = 3
            _defer_hard_rel_imp = bool(
                self.enable_hard_early_root_depth2_then_conditional_depth3_v1
                and cond_phase == "depth2"
                and not cond_gate_evaluated
            )
            hard_cov_diag = self._hard_early_root_coverage_forced_diagnostic(
                branches=branches,
                branch_family_ids=branch_family_ids,
                root_family_ids=root_family_ids,
                actions_so_far=actions,
                max_actions=self.max_actions,
                force_disabled=hard_early_coverage_force_disabled,
                coverage_target_override=cov_override,
            )
            if (
                self.enable_hard_early_root_depth2_then_conditional_depth3_v1
                and cond_phase == "depth2"
                and not cond_gate_evaluated
                and (
                    bool(hard_cov_diag.get("all_root_families_satisfied"))
                    or bool(hard_cov_diag.get("release_impossible_under_budget"))
                )
            ):
                cond_gate_evaluated = True
                cond_depth2_gate_actions = int(actions)
                cond_gate_record = self._evaluate_conditional_depth3_gate(
                    answer_support_counts=answer_support_counts,
                    branch_expansions=branch_expansions,
                    branch_family_ids=branch_family_ids,
                    root_family_ids=root_family_ids,
                    branches=branches,
                    scored=scored,
                    actions_so_far=actions,
                    max_actions=self.max_actions,
                    expansions=expansions,
                    max_consecutive_same_family_expands=max_consecutive_same_family_expands,
                    hard_cov_diag_d2=hard_cov_diag,
                )
                cond_gate_record["actions_at_gate"] = int(actions)
                if bool(cond_gate_record.get("combine_depth3")):
                    cond_phase = "depth3"
                    hard_early_coverage_force_disabled = False
                    hard_cov_diag = self._hard_early_root_coverage_forced_diagnostic(
                        branches=branches,
                        branch_family_ids=branch_family_ids,
                        root_family_ids=root_family_ids,
                        actions_so_far=actions,
                        max_actions=self.max_actions,
                        force_disabled=False,
                        coverage_target_override=3,
                    )
                else:
                    cond_phase = "normal"
                    hard_early_coverage_force_disabled = True
                    if bool(hard_cov_diag.get("release_impossible_under_budget")):
                        hard_early_coverage_budget_released_impossible = True
            if self.hard_early_root_coverage_forced_min_depth >= 2 and not hard_early_coverage_force_disabled:
                if bool(hard_cov_diag.get("release_impossible_under_budget")):
                    if not _defer_hard_rel_imp:
                        hard_early_coverage_force_disabled = True
                        hard_early_coverage_budget_released_impossible = True
                elif bool(hard_cov_diag.get("release_low_remaining_budget")):
                    if not _defer_hard_rel_imp:
                        hard_early_coverage_force_disabled = True
                        hard_early_coverage_budget_released_low_remaining = True
            if (
                self.enable_hard_early_root_depth2_then_conditional_depth3_v1
                and cond_phase == "depth3"
                and hard_early_coverage_force_disabled
            ):
                cond_phase = "normal"
            branch, priority, pri_meta, hard_cov_override = self._apply_hard_early_root_coverage_forced_override(
                scored,
                branch=branch,
                priority=priority,
                pri_meta=pri_meta,
                branch_family_ids=branch_family_ids,
                diag=hard_cov_diag,
                branches=branches,
            )
            if bool(hard_cov_override.get("hard_early_coverage_forced_override")):
                hard_early_coverage_forced_override_steps += 1
            family_expansions_now: dict[str, int] = {}
            for bid, cnt in branch_expansions.items():
                fam = str(branch_family_ids.get(bid) or bid)
                family_expansions_now[fam] = family_expansions_now.get(fam, 0) + int(cnt)
            selected_family_id = str(branch_family_ids.get(branch.branch_id) or branch.branch_id)
            active_family_count = len({str(branch_family_ids.get(b.branch_id) or b.branch_id) for b in active})
            cap_meta = self._conditional_family_cap(
                family_expansions=family_expansions_now,
                selected_family=selected_family_id,
                answer_support_counts=answer_support_counts,
                active_group_counts=active_group_counts,
                active_family_count=active_family_count,
                max_consecutive_same_family_expands=max_consecutive_same_family_expands,
                top_support=float(max(answer_support_counts.values()) / max(1, sum(answer_support_counts.values())) if answer_support_counts else 0.0),
                hard_cov_diag=hard_cov_diag,
                actions_so_far=actions,
            )
            if bool(cap_meta.get("relaxed")):
                family_cap_relax_activation_count += 1
                family_cap_relax_delta_sum += int(cap_meta.get("relax_delta", 0))
                trig = str(cap_meta.get("trigger") or "unknown")
                family_cap_activation_by_trigger[trig] = family_cap_activation_by_trigger.get(trig, 0) + 1
            family_exp_cnt_selected = int(family_expansions_now.get(selected_family_id, 0))
            if family_exp_cnt_selected >= int(cap_meta.get("effective_cap", 0)):
                alt = next(
                    (
                        item
                        for item in scored
                        if int(
                            family_expansions_now.get(
                                str(branch_family_ids.get(item[0].branch_id) or item[0].branch_id),
                                0,
                            )
                        )
                        < int(cap_meta.get("effective_cap", 0))
                    ),
                    None,
                )
                if alt is not None:
                    family_cap_block_count += 1
                    branch, priority, pri_meta = alt
                    selected_family_id = str(branch_family_ids.get(branch.branch_id) or branch.branch_id)
            hard_cov_trace = {
                "hard_early_root_coverage_forced_min_depth": int(self.hard_early_root_coverage_forced_min_depth),
                "hard_early_root_coverage_forced_active": bool(self.hard_early_root_coverage_forced_min_depth >= 2),
                "hard_early_root_depth2_coverage_v1_enabled": bool(self.hard_early_root_coverage_forced_min_depth == 2),
                "hard_early_root_depth3_coverage_v1_enabled": bool(self.hard_early_root_coverage_forced_min_depth >= 3),
                "hard_early_coverage_force_disabled": bool(hard_early_coverage_force_disabled),
                "hard_early_coverage_phase_active": bool(
                    self.hard_early_root_coverage_forced_min_depth >= 2
                    and (not hard_early_coverage_force_disabled)
                    and (not bool(hard_cov_diag.get("all_root_families_satisfied")))
                ),
                "hard_early_coverage_pending_families": list(hard_cov_diag.get("pending_families") or []),
                "hard_early_coverage_all_satisfied_pre_action": bool(hard_cov_diag.get("all_root_families_satisfied")),
                "hard_early_coverage_actions_needed_lb": int(hard_cov_diag.get("actions_needed_sum_lower_bound") or 0),
                "hard_early_coverage_remaining_actions": int(hard_cov_diag.get("remaining_actions_before_step") or 0),
                "hard_early_coverage_release_impossible_under_budget": bool(
                    hard_cov_diag.get("release_impossible_under_budget")
                ),
                "hard_early_coverage_release_low_remaining": bool(hard_cov_diag.get("release_low_remaining_budget")),
                "hard_early_coverage_forced_override": bool(hard_cov_override.get("hard_early_coverage_forced_override")),
                "hard_early_coverage_override_reason": str(hard_cov_override.get("hard_early_coverage_override_reason") or ""),
                "conditional_depth2_then_depth3_gate_phase": str(cond_phase or ""),
                "conditional_depth3_gate_evaluated": bool(cond_gate_evaluated),
            }

            metalevel_preview: dict[str, Any] | None = None
            metalevel_override = False
            if self.enable_incumbent_challenger_commit:
                metalevel_preview = self._incumbent_challenger_commit_state(
                    branches=branches,
                    incumbent_history=incumbent_history,
                    question=question,
                    actions_used=actions,
                    near_tie_forced_steps_used=near_tie_forced_steps_used,
                    challenger_repeat_failures=challenger_repeat_failures,
                )
                preview_expand_branch_id = str(metalevel_preview.get("best_expand_branch_id") or "")
                if preview_expand_branch_id:
                    selected = next((item for item in scored if item[0].branch_id == preview_expand_branch_id), None)
                    if selected is not None and selected[0].branch_id != branch.branch_id:
                        branch, priority, pri_meta = selected
                        metalevel_override = True
                if bool(metalevel_preview.get("commit_ready", False)):
                    incumbent_commit_triggered = True
                    commit_triggered = True
                    incumbent_challenger_checks.append({**metalevel_preview, "actions_used": int(actions), "decision_stage": "pre_action"})
                    break

            if case_split_direction_aware_active and actions < self.case_split_direction_aware_early_window_actions and scored:
                family_expansions_snapshot: dict[str, int] = {}
                for bid, cnt in branch_expansions.items():
                    fam = str(branch_family_ids.get(bid) or bid)
                    family_expansions_snapshot[fam] = family_expansions_snapshot.get(fam, 0) + int(cnt)
                explored_families = {fam for fam, cnt in family_expansions_snapshot.items() if cnt > 0}
                min_families_budget_aware = min(
                    self.case_split_direction_aware_min_distinct_families,
                    max(2, min(int(self.max_actions), len({str(branch_family_ids.get(b.branch_id) or b.branch_id) for b in active}))),
                )
                if len(explored_families) < min_families_budget_aware:
                    alt = next(
                        (
                            item
                            for item in scored
                            if str(branch_family_ids.get(item[0].branch_id) or item[0].branch_id) not in explored_families
                        ),
                        None,
                    )
                    if alt is not None:
                        branch, priority, pri_meta = alt
                        case_split_direction_aware_forced_coverage_steps += 1

            if self.enable_reasoning_diversity_bonus_v1 and scored:
                top_no_rd = sorted(scored, key=lambda x: float(x[2].get("base_priority_score", x[1])), reverse=True)[0][0]
                pri_meta["selected_due_to_reasoning_diversity"] = 1.0 if branch.branch_id != top_no_rd.branch_id else 0.0
            group_key = str(pri_meta.get("group_key") or "__unknown__")
            expand_by_group[group_key] = expand_by_group.get(group_key, 0) + 1
            b_expanded = branch_expansions.get(branch.branch_id, 0)
            preview_incumbent = (metalevel_preview or {}).get("incumbent") or {}
            preview_incumbent_group = str(preview_incumbent.get("group_key") or "")
            if self.enable_incumbent_challenger_commit and preview_incumbent_group and (group_key != preview_incumbent_group):
                challenger_selection_events.append(
                    {
                        "step_index": int(actions),
                        "selected_branch_id": branch.branch_id,
                        "selected_group": group_key,
                        "incumbent_group_at_selection": preview_incumbent_group,
                        "incumbent_safety_at_selection": float((metalevel_preview or {}).get("incumbent_safety", 0.0)),
                        "best_overthrow_score_at_selection": float((metalevel_preview or {}).get("best_challenger_overthrow_score", 0.0)),
                        "outcome": "pending",
                    }
                )

            # Global commit delay: avoid stopping early when support is not concentrated.
            top_support = 0.0
            support_total = sum(answer_support_counts.values())
            if support_total > 0:
                top_support = max(answer_support_counts.values()) / support_total
            force_explore = bool(actions < self.commit_delay_min_actions or top_support < self.commit_support_threshold)
            if (
                case_split_direction_aware_active
                and (not self.case_split_direction_aware_disable_delay_commit_ablation)
                and actions < self.case_split_direction_aware_early_window_actions
            ):
                family_expansions_snapshot2: dict[str, int] = {}
                for bid, cnt in branch_expansions.items():
                    fam = str(branch_family_ids.get(bid) or bid)
                    family_expansions_snapshot2[fam] = family_expansions_snapshot2.get(fam, 0) + int(cnt)
                distinct_families = sum(1 for cnt in family_expansions_snapshot2.values() if cnt > 0)
                if distinct_families < self.case_split_direction_aware_delay_commit_until_families:
                    force_explore = True
                    case_split_direction_aware_delay_commit_blocks += 1
            req_d = int(self.diagnostic_semantic_maturation_min_depth) if self.diagnostic_semantic_maturation else 0
            diag_necessity = 0.0
            diag_necessity_decision = "off"
            maturation_released = False
            if self.diagnostic_semantic_maturation or self.diagnostic_branching_necessity_heuristic or self.diagnostic_log_semantic_families:
                snap0 = root_semantic_family_snapshot(
                    question=question,
                    branches=branches,
                    branch_family_ids=branch_family_ids,
                    root_family_ids=set(root_family_ids),
                    branch_strategy_family=branch_strategy_family,
                    min_depth=max(req_d, 0),
                )
                sup_vals = sorted((float(c) for c in answer_support_counts.values()), reverse=True) if answer_support_counts else []
                t0e = float(sup_vals[0] / support_total) if sup_vals and support_total > 0 else 0.0
                t1e = float(sup_vals[1] / support_total) if len(sup_vals) > 1 and support_total > 0 else 0.0
                marge = float(t0e - t1e)
                ent0 = float(self._support_entropy(answer_support_counts))
                diag_necessity, nec_parts = compute_branching_necessity_score(
                    question=question,
                    semantic_family_count=int(snap0.get("semantic_family_count", 0)),
                    family_redundancy_ratio=float(snap0.get("family_redundancy_ratio", 0.0)),
                    top_support=float(top_support),
                    answer_entropy=ent0,
                    support_margin=marge,
                )
                rel_inc = bool(
                    self.diagnostic_protected_incumbent_release
                    and t0e >= 0.80
                    and marge >= 0.10
                )
                maturation_released = bool(rel_inc or (actions + 1 >= self.max_actions))
                if bool(snap0.get("maturation_satisfied", True)) or not self.diagnostic_semantic_maturation or req_d <= 0:
                    self._diagnostic_maturation_phase_active = False
                if self.diagnostic_semantic_maturation and req_d > 0:
                    if not bool(snap0.get("maturation_satisfied", True)) and (not maturation_released):
                        force_explore = True
                if self.diagnostic_branching_necessity_heuristic:
                    if diag_necessity < 0.32 and top_support >= 0.45:
                        force_explore = False
                        diag_necessity_decision = "prefer_concentration"
                    elif diag_necessity >= 0.50 and top_support < 0.64:
                        force_explore = True
                        diag_necessity_decision = "favor_branching"
                    else:
                        diag_necessity_decision = "neutral"
                self._last_diagnostic_semantic_snapshot = {
                    "semantic_family_id_by_branch": {
                        b.branch_id: next(
                            (
                                sk
                                for sk, members in (snap0.get("semantic_families") or {}).items()
                                if any(m.get("branch_id") == b.branch_id for m in members)
                            ),
                            "unknown",
                        )
                        for b in branches
                        if not b.is_pruned
                    },
                    "semantic_family_count": int(snap0.get("semantic_family_count", 0)),
                    "root_branch_count": int(snap0.get("root_branch_count", 0)),
                    "family_redundancy_ratio": float(snap0.get("family_redundancy_ratio", 0.0)),
                    "families_reaching_depth_ge_2": list(snap0.get("families_reaching_depth_ge_2", [])),
                    "families_reaching_depth_ge_3": list(snap0.get("families_reaching_depth_ge_3", [])),
                    "families_pending_maturation": list(snap0.get("families_pending_maturation", [])),
                    "families_invalid_or_stalled": list(snap0.get("families_invalid_or_stalled", [])),
                    "maturation_satisfied": bool(snap0.get("maturation_satisfied", True)),
                    "maturation_released": bool(maturation_released),
                    "maturation_phase_active": bool(self._diagnostic_maturation_phase_active),
                    "action_index": int(actions),
                    "branching_necessity_score": float(diag_necessity),
                    "branching_necessity_parts": nec_parts,
                    "branching_necessity_decision": str(diag_necessity_decision),
                    "commit_top_support": float(top_support),
                    "commit_support_total": int(support_total),
                    "answer_entropy": float(ent0),
                    "top2_support_gap": float(marge),
                }
                self._diagnostic_branching_necessity_trace.append(
                    {
                        "action": int(actions),
                        "branching_necessity": float(diag_necessity),
                        "decision": str(diag_necessity_decision),
                        "maturation_satisfied": bool(snap0.get("maturation_satisfied", True)),
                    }
                )
            if gate_meta.get("gate_decision") == "suppress_diversity_push":
                force_explore = False
            if force_explore:
                forced_explore_steps += 1

            should_expand = bool((b_expanded < self.min_branch_expansions) or force_explore or (priority >= float(self.scorer.score_branch(branch))))
            forced_action = str(forced_action_plan.get(actions, "")).strip().lower()
            forced_action_applied = False
            if forced_action in {"refine_incumbent", "verify_incumbent", "widen_to_challenger", "commit"}:
                if forced_action == "commit":
                    commit_triggered = True
                    forced_action_applied = True
                elif forced_action == "verify_incumbent":
                    top_item = max(scored, key=lambda x: x[1]) if scored else None
                    if top_item is not None:
                        branch, priority, pri_meta = top_item
                    should_expand = False
                    forced_action_applied = True
                elif forced_action == "widen_to_challenger":
                    top_item = max(scored, key=lambda x: x[1]) if scored else None
                    top_group = str((top_item[2].get("group_key") if top_item else "__none__") or "__none__")
                    challenger = next((item for item in scored if str(item[2].get("group_key") or "__none__") != top_group), None)
                    if challenger is not None:
                        branch, priority, pri_meta = challenger
                    should_expand = True
                    forced_action_applied = True
                elif forced_action == "refine_incumbent":
                    top_item = max(scored, key=lambda x: x[1]) if scored else None
                    if top_item is not None:
                        branch, priority, pri_meta = top_item
                    should_expand = True
                    forced_action_applied = True
            if commit_triggered:
                break
            near_tie_uncertainty = False
            if len(scored) >= 2:
                near_tie_uncertainty = bool(abs(float(scored[0][1]) - float(scored[1][1])) <= self.uncertainty_verify_priority_margin)
            near_miss_correction_meta: dict[str, Any] = {
                "activated": False,
                "reason": "disabled",
                "nearby_done_same_family_count": 0,
                "top_support_before_action": float(top_support),
            }
            correction_branch_spawned = False
            correction_parent_branch_id: str | None = None
            if (
                self.enable_near_miss_correction_gate
                and near_miss_correction_activation_count < self.near_miss_correction_max_steps
                and actions >= self.near_miss_correction_min_actions
                and branch.is_done
                and top_support <= self.near_miss_correction_min_top_support
                and consecutive_same_family_expands >= self.near_miss_correction_repeat_family_trigger
            ):
                parent_family_id = str(branch_family_ids.get(branch.branch_id) or branch.branch_id)
                branch_numeric = self._maybe_numeric_answer(self._normalize_answer(branch.predicted_answer))
                nearby = 0
                if branch_numeric is not None:
                    for cand in active:
                        if cand.branch_id == branch.branch_id or not cand.is_done:
                            continue
                        cand_family = str(branch_family_ids.get(cand.branch_id) or cand.branch_id)
                        if cand_family != parent_family_id:
                            continue
                        cand_num = self._maybe_numeric_answer(self._normalize_answer(cand.predicted_answer))
                        if cand_num is None:
                            continue
                        if abs(cand_num - branch_numeric) <= self.near_miss_correction_numeric_gap:
                            nearby += 1
                near_miss_correction_meta["nearby_done_same_family_count"] = int(nearby)
                if nearby > 0:
                    parent_branch_id = branch.branch_id
                    correction_branch = self.generator.init_branch(f"div_near_miss_correct_{actions}_{len(branches)}")
                    correction_branch.score = 0.65 * correction_branch.score + 0.35 * branch.score
                    branches.append(correction_branch)
                    branch_expansions[correction_branch.branch_id] = 0
                    branch_family_ids[correction_branch.branch_id] = parent_family_id
                    branch_strategy_family[correction_branch.branch_id] = str(
                        branch_strategy_family.get(branch.branch_id, "sanity_check_verifier_family")
                    )
                    branch_strategy_seed_order[correction_branch.branch_id] = int(
                        branch_strategy_seed_order.get(branch.branch_id, -1)
                    )
                    if branch.branch_id in branch_strategy_prompt_obj:
                        branch_strategy_prompt_obj[correction_branch.branch_id] = branch_strategy_prompt_obj[branch.branch_id]
                        branch_strategy_prompt_text[correction_branch.branch_id] = branch_strategy_prompt_text.get(branch.branch_id, "")
                    branch = correction_branch
                    priority = float(priority) + 0.01
                    b_expanded = 0
                    should_expand = True
                    correction_branch_spawned = True
                    correction_parent_branch_id = str(parent_branch_id)
                    near_miss_correction_activation_count += 1
                    near_miss_correction_meta.update(
                        {
                            "activated": True,
                            "reason": "same_family_numeric_near_miss_correction_spawn",
                            "parent_family_id": parent_family_id,
                            "parent_branch_id": str(correction_parent_branch_id or ""),
                        }
                    )
                else:
                    near_miss_correction_meta["reason"] = "no_numeric_near_miss_peer_in_same_family"
            uncertainty_verify_activated = bool(
                self.enable_uncertainty_triggered_verify
                and near_tie_uncertainty
                and branch.is_done
                and uncertainty_verify_steps < self.uncertainty_verify_max_steps
                and actions >= self.width_depth_min_actions
            )
            if uncertainty_verify_activated:
                should_expand = False
                uncertainty_verify_steps += 1
            if should_expand:
                strategy_instruction = str(branch_strategy_prompt_text.get(branch.branch_id, "")).strip()
                use_seed_prompt = bool(
                    typed_seeded_active
                    and strategy_instruction
                    and int(branch_expansions.get(branch.branch_id, 0)) == 0
                )
                seeded_question = (
                    f"{question}\n\n[Typed strategy instruction]\n{strategy_instruction}\n"
                    if use_seed_prompt
                    else question
                )
                result = self.generator.expand(branch, seeded_question, gold_answer)
                actions += 1
                expansions += 1
                branch_expansions[branch.branch_id] = b_expanded + 1
                sfam = str(branch_strategy_family.get(branch.branch_id, "direct_formula_family"))
                family_expansions_by_strategy[sfam] = int(family_expansions_by_strategy.get(sfam, 0)) + 1
                if actions <= early_prefix:
                    if bool(early_maturation_meta.get("activated", False)):
                        early_maturation_actions += 1
                    early_groups_seen_order.append(str(pri_meta.get("group_key") or "__unknown__"))
                    early_families_seen_order.append(str(sfam))
                action_trace.append(
                    {
                        "action": "expand",
                        "branch_id": branch.branch_id,
                        "parent_branch_id": branch.parent_branch_id,
                        "branch_depth": int(branch.depth),
                        "priority": round(priority, 4),
                        "continuation_value": round(float(pri_meta["continuation_value"]), 4),
                        "diversity_bonus": round(float(pri_meta["diversity_bonus"]), 4),
                        "duplicate_cost": round(float(pri_meta["duplicate_cost"]), 4),
                        "coverage_gain": round(float(pri_meta.get("coverage_gain", 0.0)), 4),
                        "semantic_overlap": round(float(pri_meta.get("semantic_overlap", 0.0)), 4),
                        "group_key": pri_meta["group_key"],
                        "force_explore": bool(force_explore),
                        "gate_mode": gate_meta.get("gate_mode"),
                        "gate_decision": gate_meta.get("gate_decision"),
                        "gate_signal": round(float(gate_meta.get("gate_signal", 0.0)), 4),
                        "gate_intervened": bool(gate_meta.get("gate_intervened", False)),
                        "gate_selected_branch_id": gate_meta.get("gate_selected_branch_id"),
                        "coverage_floor_activated": bool(coverage_floor_meta.get("coverage_floor_activated", False)),
                        "coverage_floor_reason": coverage_floor_meta.get("reason"),
                        "top_support_before_action": round(float(top_support), 4),
                        "metalevel_preview_decision": (metalevel_preview or {}).get("decision"),
                        "metalevel_preview_best_expand_branch_id": (metalevel_preview or {}).get("best_expand_branch_id"),
                        "metalevel_branch_override_applied": bool(metalevel_override),
                        "target_alignment_score": round(float(pri_meta.get("target_alignment_score", 0.0)), 4),
                        "target_alignment_category": str(pri_meta.get("target_alignment_category", "unknown")),
                        "base_priority_score": round(float(pri_meta.get("base_priority_score", 0.0)), 4),
                        "strategy_family_novelty": round(float(pri_meta.get("strategy_family_novelty", 0.0)), 4),
                        "operation_sequence_novelty": round(float(pri_meta.get("operation_sequence_novelty", 0.0)), 4),
                        "intermediate_value_novelty": round(float(pri_meta.get("intermediate_value_novelty", 0.0)), 4),
                        "answer_group_novelty": round(float(pri_meta.get("answer_group_novelty", 0.0)), 4),
                        "reasoning_role_novelty": round(float(pri_meta.get("reasoning_role_novelty", 0.0)), 4),
                        "redundancy_penalty": round(float(pri_meta.get("redundancy_penalty", 0.0)), 4),
                        "plausibility_score": round(float(pri_meta.get("plausibility_score", 0.5)), 4),
                        "useful_reasoning_diversity_bonus": round(float(pri_meta.get("useful_reasoning_diversity_bonus", 0.0)), 4),
                        "final_priority_with_reasoning_diversity": round(float(pri_meta.get("final_priority_with_reasoning_diversity", priority)), 4),
                        "reasoning_signature_key": str(pri_meta.get("reasoning_signature_key", "")),
                        "operation_sequence_key": str(pri_meta.get("operation_sequence_key", "")),
                        "reasoning_role": str(pri_meta.get("reasoning_role", "unknown")),
                        "seen_signature_count_before_selection": int(pri_meta.get("seen_signature_count_before_selection", 0.0)),
                        "selected_due_to_reasoning_diversity": bool(float(pri_meta.get("selected_due_to_reasoning_diversity", 0.0)) > 0.0),
                        "early_preservation_activated": bool(early_preservation_meta.get("activated", False)),
                        "early_preservation_reason": early_preservation_meta.get("reason"),
                        "early_answer_diversity_maturation_activated": bool(
                            early_maturation_meta.get("activated", False)
                        ),
                        "early_answer_diversity_maturation_reason": str(early_maturation_meta.get("reason") or ""),
                        "early_gated_override_considered": bool(gated_override_meta.get("considered", False)),
                        "early_gated_override_applied": bool(gated_override_meta.get("applied", False)),
                        "early_gated_override_triggers": list(gated_override_meta.get("triggers", []) or []),
                        "early_gated_override_skipped_reason": str(gated_override_meta.get("skip_reason") or ""),
                        "anti_collapse_repeat_penalty": round(
                            float(anti_collapse_adjustments.get(branch.branch_id, {}).get("repeat_penalty", 0.0)), 4
                        ),
                        "anti_collapse_repeat_expand_exact_penalty": round(
                            float(anti_collapse_adjustments.get(branch.branch_id, {}).get("repeat_expand_exact_penalty", 0.0)), 4
                        ),
                        "anti_collapse_repeat_expand_family_penalty": round(
                            float(anti_collapse_adjustments.get(branch.branch_id, {}).get("repeat_expand_family_penalty", 0.0)), 4
                        ),
                        "anti_collapse_repeat_expand_override_applied": bool(
                            float(anti_collapse_adjustments.get(branch.branch_id, {}).get("repeat_expand_override_applied", 0.0)) > 0.0
                        ),
                        "low_marginal_gain_family_penalty": round(
                            float(anti_collapse_adjustments.get(branch.branch_id, {}).get("low_marginal_gain_family_penalty", 0.0)), 4
                        ),
                        "low_marginal_gain_family_triggered": bool(
                            float(anti_collapse_adjustments.get(branch.branch_id, {}).get("low_marginal_gain_family_triggered", 0.0)) > 0.0
                        ),
                        "low_marginal_gain_family_blocked": bool(
                            float(anti_collapse_adjustments.get(branch.branch_id, {}).get("low_marginal_gain_family_blocked", 0.0)) > 0.0
                        ),
                        "low_marginal_gain_family_override_applied": bool(
                            float(anti_collapse_adjustments.get(branch.branch_id, {}).get("low_marginal_gain_family_override_applied", 0.0)) > 0.0
                        ),
                        "low_marginal_gain_recent_mean": round(
                            float(anti_collapse_adjustments.get(branch.branch_id, {}).get("low_marginal_gain_recent_mean", 0.0)), 4
                        ),
                        "low_marginal_gain_threshold": round(
                            float(anti_collapse_adjustments.get(branch.branch_id, {}).get("low_marginal_gain_threshold", 0.0)), 4
                        ),
                        "anti_collapse_cap_guard_penalty": round(
                            float(anti_collapse_adjustments.get(branch.branch_id, {}).get("cap_guard_penalty", 0.0)), 4
                        ),
                        "answer_group_distinctness_bonus": round(
                            float(anti_collapse_adjustments.get(branch.branch_id, {}).get("distinctness_bonus", 0.0)), 4
                        ),
                        "duplicate_answer_group_penalty": round(
                            float(anti_collapse_adjustments.get(branch.branch_id, {}).get("duplicate_answer_group_penalty", 0.0)), 4
                        ),
                        "alternative_maturity_protected": bool(branch.branch_id in protected_alternatives),
                        "width_depth_guard_activated": bool(width_depth_meta.get("activated", False)),
                        "width_depth_guard_reason": width_depth_meta.get("reason"),
                        "width_depth_guard_chosen_family_id": width_depth_meta.get("chosen_family_id"),
                        "uncertainty_verify_activated": bool(uncertainty_verify_activated),
                        "near_miss_correction_activated": bool(near_miss_correction_meta.get("activated", False)),
                        "near_miss_correction_reason": near_miss_correction_meta.get("reason"),
                        "near_miss_correction_nearby_done_same_family_count": int(
                            near_miss_correction_meta.get("nearby_done_same_family_count", 0)
                        ),
                        "near_miss_correction_spawned_branch": bool(correction_branch_spawned),
                        "near_miss_correction_parent_branch_id": correction_parent_branch_id,
                        "forced_action": forced_action if forced_action_applied else "",
                        "hard_max_family_expansions_cap_enabled": bool(self.enable_hard_max_family_expansions_cap),
                        "hard_max_family_expansions_mode": str(cap_meta.get("mode") or ""),
                        "hard_max_family_expansions_base_cap": int(cap_meta.get("base_cap", 0)),
                        "hard_max_family_expansions_effective_cap": int(cap_meta.get("effective_cap", 0)),
                        "hard_max_family_expansions_relaxed": bool(cap_meta.get("relaxed", False)),
                        "hard_max_family_expansions_relax_delta": int(cap_meta.get("relax_delta", 0)),
                        "hard_max_family_expansions_trigger": str(cap_meta.get("trigger") or ""),
                        "selected_family_expansions_pre_action": int(cap_meta.get("selected_family_expansions_pre_action", 0)),
                        "strategy_family": sfam,
                        "is_combinatorics_family": bool(combinatorics_guard_active),
                        "direction_id": sfam,
                        "direction_summary": sfam.replace("_", " "),
                        "case_split_signature": ("explicit_case_split" if "case_split" in sfam else ""),
                        "family_expansions_so_far": int(family_expansions_by_strategy.get(sfam, 0)),
                        "family_budget_share_so_far": float(
                            family_expansions_by_strategy.get(sfam, 0) / max(1, sum(family_expansions_by_strategy.values()))
                        ),
                        "direction_guard_triggered": bool(direction_guard_triggered_count > 0),
                        "strategy_prompt_text": strategy_instruction if use_seed_prompt else "",
                        "strategy_prompt_hash": str(abs(hash(strategy_instruction))) if strategy_instruction else "",
                        "seeded_from_strategy_prompt": bool(use_seed_prompt),
                        "typed_seeded": bool(typed_seeded_active),
                        "initial_seed_order": int(branch_strategy_seed_order.get(branch.branch_id, -1)),
                        "prompt_text": str((branch.trace_events[-1] if branch.trace_events else {}).get("prompt_text", "")),
                        "response_text": str((branch.trace_events[-1] if branch.trace_events else {}).get("response_text", "")),
                        "reasoning_text": str((branch.trace_events[-1] if branch.trace_events else {}).get("reasoning_text", "")),
                        "extracted_answer": str((branch.trace_events[-1] if branch.trace_events else {}).get("extracted_answer", "") or ""),
                        **hard_cov_trace,
                    }
                )
                if correction_branch_spawned:
                    near_miss_correction_forced_expand_count += 1
                if branch.branch_id == last_expanded_branch_id:
                    repeated_same_branch_expansion_count += 1
                    consecutive_same_branch_expands += 1
                else:
                    consecutive_same_branch_expands = 1
                max_consecutive_same_branch_expands = max(max_consecutive_same_branch_expands, consecutive_same_branch_expands)
                last_expanded_branch_id = branch.branch_id
                family_id = str(branch_family_ids.get(branch.branch_id) or branch.branch_id)
                if family_id == (last_expanded_family_id or ""):
                    repeated_same_family_expansion_count += 1
                    consecutive_same_family_expands += 1
                else:
                    consecutive_same_family_expands = 1
                max_consecutive_same_family_expands = max(max_consecutive_same_family_expands, consecutive_same_family_expands)
                last_expanded_family_id = family_id
                realized_delta = float(max(0.0, float(result.score_after) - float(result.score_before)))
                family_recent_marginal_gains.setdefault(family_id, []).append(realized_delta)
                keep_recent = max(4, self.low_marginal_gain_window_size * 3)
                if len(family_recent_marginal_gains[family_id]) > keep_recent:
                    family_recent_marginal_gains[family_id] = family_recent_marginal_gains[family_id][-keep_recent:]
                if branch.branch_id in protected_alternatives:
                    rem = int(protected_alternatives[branch.branch_id].get("remaining", 0))
                    if rem > 0:
                        rem -= 1
                        protected_alternatives[branch.branch_id]["remaining"] = rem
                        if rem <= 0:
                            matured_alternative_ids.add(branch.branch_id)
                if branch.is_done:
                    done_key = self._normalize_answer(branch.predicted_answer) or "__unknown__"
                    answer_support_counts[done_key] = answer_support_counts.get(done_key, 0) + 1
                    profile = self._support_profile_features(branch)
                    group_profiles.setdefault(done_key, []).append(profile)
                    global_profiles.append(profile)
                elif len(branches) < self.max_branches and actions < self.max_actions:
                    child = self.generator.init_branch(f"div_child_{actions}_{len(branches)}")
                    child.score = 0.5 * child.score + 0.5 * branch.score
                    child.parent_branch_id = branch.branch_id
                    branches.append(child)
                    branch_expansions[child.branch_id] = 0
                    branch_family_ids[child.branch_id] = str(branch_family_ids.get(branch.branch_id) or branch.branch_id)
                    if combinatorics_guard_active:
                        missing_family = next((fam for fam in strategy_families if family_expansions_by_strategy.get(fam, 0) == 0), None)
                        branch_strategy_family[child.branch_id] = str(missing_family or sfam)
                    else:
                        branch_strategy_family[child.branch_id] = sfam
                    branch_strategy_seed_order[child.branch_id] = int(branch_strategy_seed_order.get(branch.branch_id, -1))
                    if branch.branch_id in branch_strategy_prompt_obj:
                        branch_strategy_prompt_obj[child.branch_id] = branch_strategy_prompt_obj[branch.branch_id]
                        branch_strategy_prompt_text[child.branch_id] = branch_strategy_prompt_text.get(branch.branch_id, "")
            else:
                result = self.generator.verify(branch, question)
                actions += 1
                verifications += 1
                action_trace.append(
                    {
                        "action": "verify",
                        "branch_id": branch.branch_id,
                        "parent_branch_id": branch.parent_branch_id,
                        "branch_depth": int(branch.depth),
                        "priority": round(priority, 4),
                        "score_after": round(float(result.score_after), 4),
                        "force_explore": bool(force_explore),
                        "gate_mode": gate_meta.get("gate_mode"),
                        "gate_decision": gate_meta.get("gate_decision"),
                        "gate_signal": round(float(gate_meta.get("gate_signal", 0.0)), 4),
                        "gate_intervened": bool(gate_meta.get("gate_intervened", False)),
                        "gate_selected_branch_id": gate_meta.get("gate_selected_branch_id"),
                        "coverage_floor_activated": bool(coverage_floor_meta.get("coverage_floor_activated", False)),
                        "coverage_floor_reason": coverage_floor_meta.get("reason"),
                        "top_support_before_action": round(float(top_support), 4),
                        "metalevel_preview_decision": (metalevel_preview or {}).get("decision"),
                        "metalevel_preview_best_expand_branch_id": (metalevel_preview or {}).get("best_expand_branch_id"),
                        "metalevel_branch_override_applied": bool(metalevel_override),
                        "target_alignment_score": round(float(pri_meta.get("target_alignment_score", 0.0)), 4),
                        "target_alignment_category": str(pri_meta.get("target_alignment_category", "unknown")),
                        "base_priority_score": round(float(pri_meta.get("base_priority_score", 0.0)), 4),
                        "strategy_family_novelty": round(float(pri_meta.get("strategy_family_novelty", 0.0)), 4),
                        "operation_sequence_novelty": round(float(pri_meta.get("operation_sequence_novelty", 0.0)), 4),
                        "intermediate_value_novelty": round(float(pri_meta.get("intermediate_value_novelty", 0.0)), 4),
                        "answer_group_novelty": round(float(pri_meta.get("answer_group_novelty", 0.0)), 4),
                        "reasoning_role_novelty": round(float(pri_meta.get("reasoning_role_novelty", 0.0)), 4),
                        "redundancy_penalty": round(float(pri_meta.get("redundancy_penalty", 0.0)), 4),
                        "plausibility_score": round(float(pri_meta.get("plausibility_score", 0.5)), 4),
                        "useful_reasoning_diversity_bonus": round(float(pri_meta.get("useful_reasoning_diversity_bonus", 0.0)), 4),
                        "final_priority_with_reasoning_diversity": round(float(pri_meta.get("final_priority_with_reasoning_diversity", priority)), 4),
                        "reasoning_signature_key": str(pri_meta.get("reasoning_signature_key", "")),
                        "operation_sequence_key": str(pri_meta.get("operation_sequence_key", "")),
                        "reasoning_role": str(pri_meta.get("reasoning_role", "unknown")),
                        "seen_signature_count_before_selection": int(pri_meta.get("seen_signature_count_before_selection", 0.0)),
                        "selected_due_to_reasoning_diversity": bool(float(pri_meta.get("selected_due_to_reasoning_diversity", 0.0)) > 0.0),
                        "early_preservation_activated": bool(early_preservation_meta.get("activated", False)),
                        "early_preservation_reason": early_preservation_meta.get("reason"),
                        "anti_collapse_repeat_penalty": round(
                            float(anti_collapse_adjustments.get(branch.branch_id, {}).get("repeat_penalty", 0.0)), 4
                        ),
                        "anti_collapse_repeat_expand_exact_penalty": round(
                            float(anti_collapse_adjustments.get(branch.branch_id, {}).get("repeat_expand_exact_penalty", 0.0)), 4
                        ),
                        "anti_collapse_repeat_expand_family_penalty": round(
                            float(anti_collapse_adjustments.get(branch.branch_id, {}).get("repeat_expand_family_penalty", 0.0)), 4
                        ),
                        "anti_collapse_repeat_expand_override_applied": bool(
                            float(anti_collapse_adjustments.get(branch.branch_id, {}).get("repeat_expand_override_applied", 0.0)) > 0.0
                        ),
                        "low_marginal_gain_family_penalty": round(
                            float(anti_collapse_adjustments.get(branch.branch_id, {}).get("low_marginal_gain_family_penalty", 0.0)), 4
                        ),
                        "low_marginal_gain_family_triggered": bool(
                            float(anti_collapse_adjustments.get(branch.branch_id, {}).get("low_marginal_gain_family_triggered", 0.0)) > 0.0
                        ),
                        "low_marginal_gain_family_blocked": bool(
                            float(anti_collapse_adjustments.get(branch.branch_id, {}).get("low_marginal_gain_family_blocked", 0.0)) > 0.0
                        ),
                        "low_marginal_gain_family_override_applied": bool(
                            float(anti_collapse_adjustments.get(branch.branch_id, {}).get("low_marginal_gain_family_override_applied", 0.0)) > 0.0
                        ),
                        "low_marginal_gain_recent_mean": round(
                            float(anti_collapse_adjustments.get(branch.branch_id, {}).get("low_marginal_gain_recent_mean", 0.0)), 4
                        ),
                        "low_marginal_gain_threshold": round(
                            float(anti_collapse_adjustments.get(branch.branch_id, {}).get("low_marginal_gain_threshold", 0.0)), 4
                        ),
                        "anti_collapse_cap_guard_penalty": round(
                            float(anti_collapse_adjustments.get(branch.branch_id, {}).get("cap_guard_penalty", 0.0)), 4
                        ),
                        "answer_group_distinctness_bonus": round(
                            float(anti_collapse_adjustments.get(branch.branch_id, {}).get("distinctness_bonus", 0.0)), 4
                        ),
                        "duplicate_answer_group_penalty": round(
                            float(anti_collapse_adjustments.get(branch.branch_id, {}).get("duplicate_answer_group_penalty", 0.0)), 4
                        ),
                        "alternative_maturity_protected": bool(branch.branch_id in protected_alternatives),
                        "width_depth_guard_activated": bool(width_depth_meta.get("activated", False)),
                        "width_depth_guard_reason": width_depth_meta.get("reason"),
                        "width_depth_guard_chosen_family_id": width_depth_meta.get("chosen_family_id"),
                        "uncertainty_verify_activated": bool(uncertainty_verify_activated),
                        "near_miss_correction_activated": bool(near_miss_correction_meta.get("activated", False)),
                        "near_miss_correction_reason": near_miss_correction_meta.get("reason"),
                        "near_miss_correction_nearby_done_same_family_count": int(
                            near_miss_correction_meta.get("nearby_done_same_family_count", 0)
                        ),
                        "near_miss_correction_spawned_branch": bool(correction_branch_spawned),
                        "near_miss_correction_parent_branch_id": correction_parent_branch_id,
                        "forced_action": forced_action if forced_action_applied else "",
                        "hard_max_family_expansions_cap_enabled": bool(self.enable_hard_max_family_expansions_cap),
                        "hard_max_family_expansions_mode": str(cap_meta.get("mode") or ""),
                        "hard_max_family_expansions_base_cap": int(cap_meta.get("base_cap", 0)),
                        "hard_max_family_expansions_effective_cap": int(cap_meta.get("effective_cap", 0)),
                        "hard_max_family_expansions_relaxed": bool(cap_meta.get("relaxed", False)),
                        "hard_max_family_expansions_relax_delta": int(cap_meta.get("relax_delta", 0)),
                        "hard_max_family_expansions_trigger": str(cap_meta.get("trigger") or ""),
                        "selected_family_expansions_pre_action": int(cap_meta.get("selected_family_expansions_pre_action", 0)),
                        "strategy_family": str(branch_strategy_family.get(branch.branch_id, "direct_formula_family")),
                        "is_combinatorics_family": bool(combinatorics_guard_active),
                        "direction_id": str(branch_strategy_family.get(branch.branch_id, "direct_formula_family")),
                        "direction_summary": str(branch_strategy_family.get(branch.branch_id, "direct_formula_family")).replace("_", " "),
                        "case_split_signature": (
                            "explicit_case_split"
                            if "case_split" in str(branch_strategy_family.get(branch.branch_id, ""))
                            else ""
                        ),
                        "family_expansions_so_far": int(
                            family_expansions_by_strategy.get(
                                str(branch_strategy_family.get(branch.branch_id, "direct_formula_family")), 0
                            )
                        ),
                        "family_budget_share_so_far": float(
                            family_expansions_by_strategy.get(
                                str(branch_strategy_family.get(branch.branch_id, "direct_formula_family")), 0
                            )
                            / max(1, sum(family_expansions_by_strategy.values()))
                        ),
                        "direction_guard_triggered": bool(direction_guard_triggered_count > 0),
                        "prompt_text": str((branch.trace_events[-1] if branch.trace_events else {}).get("prompt_text", "")),
                        "response_text": str((branch.trace_events[-1] if branch.trace_events else {}).get("response_text", "")),
                        "reasoning_text": str((branch.trace_events[-1] if branch.trace_events else {}).get("reasoning_text", "")),
                        "extracted_answer": str((branch.trace_events[-1] if branch.trace_events else {}).get("extracted_answer", "") or ""),
                        **hard_cov_trace,
                    }
                )

            if self.enable_reasoning_diversity_bonus_v1:
                sig_row = {
                    "strategy_family": str(branch_strategy_family.get(branch.branch_id, "direct_formula_family")),
                    "operation_sequence_key": str(pri_meta.get("operation_sequence_key", "")),
                    "intermediate_values": [],
                    "reasoning_role": str(pri_meta.get("reasoning_role", "unknown")),
                    "answer_group": str(pri_meta.get("group_key") or "__unknown__"),
                    "signature_key": str(pri_meta.get("reasoning_signature_key", "")),
                    "text_available": bool(len(getattr(branch, "steps", [])) > 0),
                }
                reasoning_signatures_seen.append(sig_row)

            if (
                self.hard_early_root_coverage_forced_min_depth >= 2
                and hard_early_coverage_transition_actions_used is None
                and not hard_early_coverage_force_disabled
            ):
                post_cov = self._hard_early_root_coverage_forced_diagnostic(
                    branches=branches,
                    branch_family_ids=branch_family_ids,
                    root_family_ids=root_family_ids,
                    actions_so_far=actions,
                    max_actions=self.max_actions,
                    force_disabled=False,
                )
                if bool(post_cov.get("all_root_families_satisfied")):
                    hard_early_coverage_transition_actions_used = int(actions)

            if (
                self.enable_hard_early_root_depth2_then_conditional_depth3_v1
                and cond_phase == "depth3"
                and not cond_depth3_completed
                and not hard_early_coverage_force_disabled
            ):
                post_d3 = self._hard_early_root_coverage_forced_diagnostic(
                    branches=branches,
                    branch_family_ids=branch_family_ids,
                    root_family_ids=root_family_ids,
                    actions_so_far=actions,
                    max_actions=self.max_actions,
                    force_disabled=False,
                    coverage_target_override=3,
                )
                if bool(post_d3.get("all_root_families_satisfied")):
                    cond_depth3_completed = True
                    cond_phase = "normal"
                    hard_early_coverage_force_disabled = True

            branches = [b for b in branches if not b.is_pruned]
            if len(branches) > self.max_branches:
                ranked = sorted(branches, key=self.scorer.score_branch, reverse=True)
                keep = {b.branch_id for b in ranked[: self.max_branches]}
                for b in branches:
                    if b.branch_id not in keep:
                        self.generator.prune(b)
                branches = [b for b in branches if not b.is_pruned]
            surviving_trace.append(len(branches))
            active_groups_now = {self._normalize_answer(b.predicted_answer) or "__unknown__" for b in branches if not b.is_pruned}
            early_divergence_timeline.append(
                {
                    "step": int(actions),
                    "unique_active_groups": int(len(active_groups_now)),
                    "gold_group_present": bool(gold_group_key in active_groups_now),
                    "active_groups": sorted(list(active_groups_now))[:8],
                    "top_support_group": max(answer_support_counts.items(), key=lambda kv: kv[1])[0] if answer_support_counts else None,
                    "top_support_count": max(answer_support_counts.values()) if answer_support_counts else 0,
                }
            )
            if self.use_answer_group_commit_margin:
                should_commit, commit_meta = self._commit_by_answer_group_margin(branches=branches, actions=actions, question=question)
                commit_checks.append(commit_meta)
                if should_commit:
                    commit_triggered = True
                    break
            if self.enable_incumbent_challenger_commit:
                ic_state = self._incumbent_challenger_commit_state(
                    branches=branches,
                    incumbent_history=incumbent_history,
                    question=question,
                    actions_used=actions,
                    near_tie_forced_steps_used=near_tie_forced_steps_used,
                    challenger_repeat_failures=challenger_repeat_failures,
                )
                incumbent_key = str((ic_state.get("incumbent") or {}).get("group_key", ""))
                if incumbent_key:
                    incumbent_history.append(incumbent_key)
                ic_state["actions_used"] = int(actions)
                ic_state["fallback_to_base_logic"] = bool(ic_state.get("decision", "").startswith("fallback"))
                incumbent_challenger_checks.append(ic_state)
                latest_incumbent_group = str(((ic_state.get("incumbent") or {}).get("group_key")) or "")
                for event in challenger_selection_events:
                    if event.get("outcome") != "pending":
                        continue
                    selected_group = str(event.get("selected_group") or "")
                    incumbent_at_selection = str(event.get("incumbent_group_at_selection") or "")
                    if latest_incumbent_group == selected_group and selected_group != incumbent_at_selection:
                        event["outcome"] = "later_overtook_incumbent"
                    elif latest_incumbent_group == incumbent_at_selection and bool(ic_state.get("incumbent_safety", 0.0)) >= float(
                        event.get("incumbent_safety_at_selection", 0.0)
                    ) + 0.03:
                        event["outcome"] = "improved_incumbent_support_indirectly"
                if latest_incumbent_group:
                    for event in challenger_selection_events:
                        if event.get("outcome") != "pending":
                            continue
                        selected_group = str(event.get("selected_group") or "")
                        incumbent_at_selection = str(event.get("incumbent_group_at_selection") or "")
                        if latest_incumbent_group not in {selected_group, incumbent_at_selection}:
                            event["outcome"] = "dominated_ex_post_by_other_challenger"
                            challenger_repeat_failures[selected_group] = challenger_repeat_failures.get(selected_group, 0) + 1
                if bool(ic_state.get("near_tie_force_explore", False)):
                    near_tie_forced_steps_used += 1
                if bool(ic_state.get("commit_ready", False)):
                    incumbent_commit_triggered = True
                    commit_triggered = True
                    break
            if all(b.is_done for b in branches):
                break

        if (
            self.enable_hard_early_root_depth2_then_conditional_depth3_v1
            and (not cond_gate_evaluated)
            and cond_phase == "depth2"
        ):
            active_post = [b for b in branches if not b.is_pruned]
            active_group_counts_post: dict[str, int] = {}
            for b in active_post:
                g = self._normalize_answer(b.predicted_answer) or "__unknown__"
                active_group_counts_post[g] = active_group_counts_post.get(g, 0) + 1
            scored_post: list[tuple[BranchState, float, dict[str, float | str | None]]] = []
            for b in active_post:
                priority, meta = self._branch_priority(
                    b,
                    answer_support_counts=answer_support_counts,
                    active_group_counts=active_group_counts_post,
                    group_profiles=group_profiles,
                    global_profiles=global_profiles,
                    question=question,
                )
                scored_post.append((b, priority, meta))
            scored_post.sort(key=lambda x: x[1], reverse=True)
            d2_end = self._hard_early_root_coverage_forced_diagnostic(
                branches=branches,
                branch_family_ids=branch_family_ids,
                root_family_ids=root_family_ids,
                actions_so_far=actions,
                max_actions=self.max_actions,
                force_disabled=hard_early_coverage_force_disabled,
                coverage_target_override=2,
            )
            if bool(d2_end.get("all_root_families_satisfied")) or bool(d2_end.get("release_impossible_under_budget")):
                cond_depth2_gate_actions = int(actions)
                cond_gate_record = self._evaluate_conditional_depth3_gate(
                    answer_support_counts=answer_support_counts,
                    branch_expansions=branch_expansions,
                    branch_family_ids=branch_family_ids,
                    root_family_ids=root_family_ids,
                    branches=branches,
                    scored=scored_post,
                    actions_so_far=actions,
                    max_actions=self.max_actions,
                    expansions=expansions,
                    max_consecutive_same_family_expands=max_consecutive_same_family_expands,
                    hard_cov_diag_d2=d2_end,
                )
                cond_gate_record["actions_at_gate"] = int(actions)
                cond_gate_evaluated = True
                if bool(cond_gate_record.get("combine_depth3")):
                    cond_gate_record["depth3_release_status"] = "gated_on_but_run_ended_before_depth3_forcing"
                    cond_gate_record["combine_depth3"] = False
            else:
                cond_gate_record = {
                    "depth3_release_status": "skipped_run_ended_before_depth2_terminal",
                    "criteria_fired": {},
                    "combine_depth3": False,
                    "raw_wants_depth3": False,
                    "note": "Controller stopped (commit/budget) before depth-2 forcing reached a terminal diagnostic state.",
                }

        self._runtime_branch_strategy_family = dict(branch_strategy_family)
        self._runtime_gold_answer_for_selection = str(gold_answer)
        prediction, group_meta = self._final_prediction_from_groups(branches, question=question)
        verifier_scores_snapshot = group_meta.get("verifier_scores_by_answer_group", {}) if isinstance(group_meta, dict) else {}
        if isinstance(verifier_scores_snapshot, dict) and verifier_scores_snapshot:
            verifier_calls += int(len(verifier_scores_snapshot))
            for v in (group_meta.get("verifier_verdicts_by_answer_group", {}) or {}).values():
                if str(v) == "verifier_pass":
                    verifier_pass += 1
                elif str(v) == "verifier_warn":
                    verifier_warn += 1
                elif str(v) == "verifier_fail":
                    verifier_fail += 1
        if bool(group_meta.get("commit_guard_triggered", False)):
            commit_guard_triggered_count += 1
        selected_family_at_commit = str(
            branch_strategy_family.get(
                str(next((b.branch_id for b in branches if self._normalize_answer(b.predicted_answer) == group_meta.get("selected_group")), "")),
                "",
            )
            or ""
        )
        first_split_step = next((int(x["step"]) for x in early_divergence_timeline if int(x.get("unique_active_groups", 0)) >= 2), None)
        second_split_step = None
        if first_split_step is not None:
            second_split_step = next(
                (
                    int(x["step"])
                    for x in early_divergence_timeline
                    if int(x["step"]) > first_split_step and int(x.get("unique_active_groups", 0)) >= 2
                ),
                None,
            )
        gold_presence_by_step = {int(x["step"]): bool(x.get("gold_group_present", False)) for x in early_divergence_timeline}
        gold_ever_present = any(gold_presence_by_step.values())
        first_present_step = next((s for s, present in gold_presence_by_step.items() if present), None)
        last_present_step = max((s for s, present in gold_presence_by_step.items() if present), default=None)
        disappeared_step = None
        if first_present_step is not None:
            for s in sorted(gold_presence_by_step.keys()):
                if s > first_present_step and not gold_presence_by_step[s]:
                    disappeared_step = s
                    break
        gold_present_after_first_split = bool(first_split_step is not None and gold_presence_by_step.get(first_split_step, False))
        gold_present_after_second_split = bool(second_split_step is not None and gold_presence_by_step.get(second_split_step, False))
        gold_present_final = bool(early_divergence_timeline[-1]["gold_group_present"]) if early_divergence_timeline else False
        if not gold_ever_present:
            dominant_failure = "not_generated"
        elif gold_present_after_first_split and (not gold_present_final):
            dominant_failure = "collapsed_early"
        elif gold_present_final and (not self._answers_match(prediction, gold_answer)):
            dominant_failure = "generated_but_committed_away_from_later"
        elif gold_ever_present and (not gold_present_after_first_split):
            dominant_failure = "generated_but_underweighted"
        else:
            dominant_failure = "not_applicable_or_correct"
        top_branch_expand_share = (
            max(branch_expansions.values()) / max(1, expansions) if branch_expansions else 0.0
        )
        repeated_same_branch_domination = bool(
            expansions > 0
            and (
                repeated_same_branch_expansion_count / max(1, expansions) >= 0.50
                or top_branch_expand_share >= 0.70
            )
        )
        matured_alternative_count = int(len(matured_alternative_ids))
        shallow_preserved_alternative_count = int(
            sum(
                1
                for bid in protected_alternative_ids
                if int(branch_expansions.get(bid, 0)) <= 1 and bid not in matured_alternative_ids
            )
        )
        if bool(self._answers_match(prediction, gold_answer)):
            regime_failure_category = "not_applicable_or_correct"
        elif not gold_ever_present:
            regime_failure_category = "correct_answer_group_absent"
        elif repeated_same_branch_domination and (not gold_present_final):
            regime_failure_category = "repeated_same_branch_expansion_dominated_budget"
        elif gold_present_after_first_split and (not gold_present_final) and matured_alternative_count <= 0:
            regime_failure_category = "correct_group_preserved_but_insufficiently_matured"
        elif gold_ever_present and (not gold_present_after_first_split):
            regime_failure_category = "correct_answer_group_present_but_underweighted"
        elif gold_present_final and (not self._answers_match(prediction, gold_answer)):
            regime_failure_category = "final_commit_lost_despite_viable_alternative"
        else:
            regime_failure_category = "other_or_unclassified"
        final_selected_group = str(group_meta.get("selected_group") or "")
        for event in challenger_selection_events:
            if event.get("outcome") == "pending":
                selected_group = str(event.get("selected_group") or "")
                if final_selected_group == selected_group and selected_group:
                    event["outcome"] = "later_overtook_incumbent"
                elif final_selected_group == str(event.get("incumbent_group_at_selection") or ""):
                    event["outcome"] = "failed_to_change_winner"
                    challenger_repeat_failures[selected_group] = challenger_repeat_failures.get(selected_group, 0) + 1
                else:
                    event["outcome"] = "dominated_ex_post_by_other_challenger"
                    challenger_repeat_failures[selected_group] = challenger_repeat_failures.get(selected_group, 0) + 1
        challenger_outcomes = [str(x.get("outcome", "")) for x in challenger_selection_events]
        challenger_outcome_counts = Counter(challenger_outcomes)
        exhausted = actions >= self.max_actions and not any(b.is_done for b in branches)
        answer_entropy = self._support_entropy(answer_support_counts)
        expand_actions = [a for a in action_trace if a.get("action") == "expand"]
        dup_positive = [a for a in expand_actions if float(a.get("duplicate_cost", 0.0)) > 0.0]
        return MethodResult(
            method=self.method_name,
            prediction=prediction,
            is_correct=self._answers_match(prediction, gold_answer),
            actions_used=actions,
            expansions=expansions,
            verifications=verifications,
            avg_surviving_branches=sum(surviving_trace) / max(1, len(surviving_trace)),
            budget_exhausted=exhausted,
            metadata={
                "method_family": "global_diversity_aggregation",
                "action_trace": action_trace,
                "answer_support_counts": answer_support_counts,
                "answer_support_entropy": answer_entropy,
                "expands_by_group": expand_by_group,
                "unique_answer_groups_seen": len(answer_support_counts),
                "forced_explore_steps": int(forced_explore_steps),
                "forced_explore_rate": float(forced_explore_steps / max(1, actions)),
                "early_answer_group_preservation_enabled": bool(self.enable_early_answer_group_preservation),
                "early_answer_group_preservation_forced_steps": int(early_preservation_forced_steps),
                "early_answer_diversity_maturation_enabled": bool(self.enable_early_answer_diversity_maturation_v1),
                "early_answer_diversity_maturation_gated_enabled": bool(
                    self.enable_early_answer_diversity_maturation_gated_v1
                ),
                "early_answer_diversity_maturation_uses_gold_labels": False,
                "early_prefix": int(early_prefix),
                "early_maturation_actions": int(early_maturation_actions),
                "early_gated_override_considered": int(early_gated_override_considered),
                "early_gated_override_applied": int(early_gated_override_applied),
                "early_gated_override_triggers": dict(early_gated_override_triggers),
                "early_gated_override_skipped_reason": (
                    early_gated_override_skipped_reasons.most_common(1)[0][0]
                    if early_gated_override_skipped_reasons
                    else ""
                ),
                "early_gated_override_skipped_reasons": dict(early_gated_override_skipped_reasons),
                "unique_answer_groups_seen_early": int(len(set(early_groups_seen_order))),
                "repeated_family_expansions_early": int(
                    sum(
                        1
                        for i in range(1, len(early_families_seen_order))
                        if early_families_seen_order[i] == early_families_seen_order[i - 1]
                    )
                ),
                "mature_groups_after_prefix": int(
                    sum(1 for v in self._group_maturity_snapshot(branches).values() if bool(v.get("mature", False)))
                ),
                "fallback_to_strict_f3_after_prefix": bool(actions >= early_prefix),
                "coverage_floor_enabled": bool(self.enable_answer_group_coverage_floor),
                "coverage_floor_forced_steps": int(coverage_floor_forced_steps),
                "coverage_floor_forced_rate": float(coverage_floor_forced_steps / max(1, actions)),
                "coverage_floor_target_groups": int(self.min_answer_groups_before_concentration),
                "duplicate_penalty_applied_rate": float(len(dup_positive) / max(1, len(expand_actions))),
                "mean_diversity_bonus_on_expand": float(
                    sum(float(a.get("diversity_bonus", 0.0)) for a in expand_actions) / max(1, len(expand_actions))
                ),
                "mean_coverage_gain_on_expand": float(
                    sum(float(a.get("coverage_gain", 0.0)) for a in expand_actions) / max(1, len(expand_actions))
                ),
                "mean_semantic_overlap_on_expand": float(
                    sum(float(a.get("semantic_overlap", 0.0)) for a in expand_actions) / max(1, len(expand_actions))
                ),
                "marginal_diversity_mode": bool(self.use_marginal_coverage_overlap),
                "duplicate_aware_aggregation_mode": bool(self.use_duplicate_aware_aggregation),
                "answer_group_commit_mode": bool(self.use_answer_group_commit_margin),
                "commit_checks": commit_checks,
                "commit_checks_count": int(len(commit_checks)),
                "incumbent_challenger_commit_mode": bool(self.enable_incumbent_challenger_commit),
                "incumbent_challenger_raw_support_only": bool(self.incumbent_challenger_raw_support_only),
                "incumbent_challenger_checks": incumbent_challenger_checks,
                "incumbent_challenger_checks_count": int(len(incumbent_challenger_checks)),
                "incumbent_challenger_commit_triggered": bool(incumbent_commit_triggered),
                "near_tie_forced_steps_used": int(near_tie_forced_steps_used),
                "incumbent_challenger_intervention_count": int(
                    sum(
                        1
                        for c in incumbent_challenger_checks
                        if str(c.get("decision")) in {"commit", "continue", "continue_force_near_tie_step"}
                    )
                ),
                "false_non_stop_count": int(sum(1 for c in incumbent_challenger_checks if bool(c.get("false_non_stop", False)))),
                "late_commit_after_selector_count": int(
                    sum(1 for c in incumbent_challenger_checks if bool(c.get("commit_should_have_happened_before_selected_challenger", False)))
                ),
                "commit_deferred_low_continue_value_count": int(
                    sum(1 for c in incumbent_challenger_checks if bool(c.get("commit_deferred_despite_low_best_continue_value", False)))
                ),
                "near_tie_commit_blocked_count": int(sum(1 for c in incumbent_challenger_checks if bool(c.get("near_tie_commit_blocked", False)))),
                "near_tie_false_continue_count": int(sum(1 for c in incumbent_challenger_checks if bool(c.get("near_tie_false_continue", False)))),
                "near_tie_continuation_rate": float(
                    sum(1 for c in incumbent_challenger_checks if bool(c.get("near_tie", False)) and str(c.get("decision")) != "commit")
                    / max(1, sum(1 for c in incumbent_challenger_checks if bool(c.get("near_tie", False))))
                ),
                "late_stage_commit_rate": float(
                    sum(1 for c in incumbent_challenger_checks if bool(c.get("low_budget_stage", False)) and bool(c.get("commit_ready", False)))
                    / max(1, sum(1 for c in incumbent_challenger_checks if bool(c.get("low_budget_stage", False))))
                ),
                "mean_best_continue_value_when_continue": float(
                    sum(float(c.get("best_expand_delta", 0.0)) for c in incumbent_challenger_checks if str(c.get("decision")) != "commit")
                    / max(1, sum(1 for c in incumbent_challenger_checks if str(c.get("decision")) != "commit"))
                ),
                "wrong_commit_risk_subtypes_counts": dict(
                    {
                        k: int(
                            sum(
                                1
                                for c in incumbent_challenger_checks
                                if k in list(c.get("wrong_commit_risk_subtypes", []))
                            )
                        )
                        for k in [
                            "committed_to_intermediate_result",
                            "committed_under_near_tie_ambiguity",
                            "challenger_had_recoverable_upside",
                            "overcounted_weak_corroboration",
                        ]
                    }
                ),
                "challenger_selection_events": challenger_selection_events[: min(20, len(challenger_selection_events))],
                "challenger_selection_event_count": int(len(challenger_selection_events)),
                "challenger_outcome_counts": dict(challenger_outcome_counts),
                "challenger_overtook_rate": float(
                    challenger_outcome_counts.get("later_overtook_incumbent", 0) / max(1, len(challenger_selection_events))
                ),
                "challenger_dominated_rate": float(
                    challenger_outcome_counts.get("dominated_ex_post_by_other_challenger", 0) / max(1, len(challenger_selection_events))
                ),
                "wrong_challenger_chosen_count": int(
                    challenger_outcome_counts.get("dominated_ex_post_by_other_challenger", 0)
                    + challenger_outcome_counts.get("failed_to_change_winner", 0)
                ),
                "commit_action_count": int(sum(1 for c in incumbent_challenger_checks if bool(c.get("commit_ready", False)))),
                "expand_action_count": int(sum(1 for a in action_trace if str(a.get("action")) == "expand")),
                "commit_triggered": bool(commit_triggered),
                "anti_collapse_answer_group_refinement_enabled": bool(self.enable_anti_collapse_answer_group_refinement),
                "repeated_same_branch_expansion_count": int(repeated_same_branch_expansion_count),
                "repeated_same_branch_expansion_rate": float(repeated_same_branch_expansion_count / max(1, expansions)),
                "repeated_same_family_expansion_count": int(repeated_same_family_expansion_count),
                "repeated_same_family_expansion_rate": float(repeated_same_family_expansion_count / max(1, expansions)),
                "max_consecutive_same_branch_expands": int(max_consecutive_same_branch_expands),
                "max_consecutive_same_branch": int(max_consecutive_same_branch_expands),
                "max_consecutive_same_family": int(max_consecutive_same_family_expands),
                "repeat_penalty_trigger_count": int(repeat_penalty_trigger_count),
                "repeat_penalty_override_count": int(repeat_penalty_override_count),
                "repeat_penalty_alternative_selected_count": int(repeat_penalty_alternative_selected_count),
                "low_marginal_gain_family_cooldown_enabled": bool(self.enable_low_marginal_gain_family_cooldown),
                "low_marginal_gain_family_trigger_count": int(low_marginal_gain_trigger_count),
                "low_marginal_gain_family_block_count": int(low_marginal_gain_block_count),
                "low_marginal_gain_family_override_count": int(low_marginal_gain_override_count),
                "low_marginal_gain_window_size": int(self.low_marginal_gain_window_size),
                "low_marginal_gain_min_threshold": float(self.low_marginal_gain_min_threshold),
                "low_marginal_gain_consecutive_family_trigger": int(self.low_marginal_gain_consecutive_family_trigger),
                "low_marginal_gain_cooldown_steps": int(self.low_marginal_gain_cooldown_steps),
                "low_marginal_gain_penalty_strength": float(self.low_marginal_gain_penalty_strength),
                "low_marginal_gain_hard_block_ablation": bool(self.low_marginal_gain_hard_block_ablation),
                "repeated_same_branch_expansion_dominated_budget": bool(repeated_same_branch_domination),
                "top_branch_expand_share": float(top_branch_expand_share),
                "branch_creation_count": int(len(branch_expansions)),
                "answer_group_diversity_realized": int(len(answer_support_counts)),
                "protected_alternative_count": int(len(protected_alternative_ids)),
                "shallow_preserved_alternative_count": int(shallow_preserved_alternative_count),
                "matured_alternative_count": int(matured_alternative_count),
                "alternative_maturity_completion_rate": float(matured_alternative_count / max(1, len(protected_alternative_ids))),
                "width_depth_allocation_guard_enabled": bool(self.enable_width_depth_allocation_guard),
                "width_depth_forced_width_steps": int(width_depth_forced_width_steps),
                "width_depth_forced_challenger_maturation_steps": int(width_depth_forced_challenger_maturation_steps),
                "width_depth_challenger_maturation_min_expands": int(self.width_depth_challenger_maturation_min_expands),
                "uncertainty_triggered_verify_enabled": bool(self.enable_uncertainty_triggered_verify),
                "uncertainty_verify_steps": int(uncertainty_verify_steps),
                "near_miss_correction_gate_enabled": bool(self.enable_near_miss_correction_gate),
                "near_miss_correction_activation_count": int(near_miss_correction_activation_count),
                "near_miss_correction_forced_expand_count": int(near_miss_correction_forced_expand_count),
                "near_miss_correction_numeric_gap": float(self.near_miss_correction_numeric_gap),
                "near_miss_correction_repeat_family_trigger": int(self.near_miss_correction_repeat_family_trigger),
                "diversity_needed_gate_mode": self.diversity_needed_gate_mode,
                "diversity_needed_gate_positive_threshold": float(self.diversity_needed_gate_positive_threshold),
                "diversity_needed_gate_negative_threshold": float(self.diversity_needed_gate_negative_threshold),
                "gate_intervention_count": int(sum(1 for a in action_trace if bool(a.get("gate_intervened", False)))),
                "gate_favor_diversity_count": int(
                    sum(1 for a in action_trace if str(a.get("gate_decision")) == "favor_diversity")
                ),
                "gate_suppress_diversity_count": int(
                    sum(1 for a in action_trace if str(a.get("gate_decision")) == "suppress_diversity_push")
                ),
                "enable_reasoning_diversity_bonus_v1": bool(self.enable_reasoning_diversity_bonus_v1),
                "reasoning_diversity_signature_count": int(len(reasoning_signatures_seen)),
                "reasoning_diversity_selection_change_count": int(sum(1 for a in action_trace if bool(a.get("selected_due_to_reasoning_diversity", False)))),
                "question_shape_label": str(question_shape_label),
                "problem_type_label": str(problem_type_label),
                "direction_guard_triggered": bool(direction_guard_triggered_count > 0),
                "required_family_coverage_satisfied": bool(
                    len({fam for fam, cnt in family_expansions_by_strategy.items() if int(cnt) > 0})
                    >= (2 if self.max_actions < 6 else 3)
                ),
                "num_strategy_families_seen": int(
                    len({fam for fam, cnt in family_expansions_by_strategy.items() if int(cnt) > 0})
                ),
                "dominant_family_share": float(
                    (max(family_expansions_by_strategy.values()) / max(1, sum(family_expansions_by_strategy.values())))
                    if family_expansions_by_strategy
                    else 0.0
                ),
                "family_cap_blocked_expansion": int(family_cap_blocked_expansion),
                "family_min_coverage_forced_expansion": int(family_min_coverage_forced_expansion),
                "selected_family_at_commit": selected_family_at_commit,
                "strategy_family_expansions": {k: int(v) for k, v in family_expansions_by_strategy.items()},
                "num_typed_strategy_branches_seeded": int(
                    len([bid for bid in branch_strategy_seed_order if int(branch_strategy_seed_order.get(bid, -1)) >= 0])
                    if typed_seeded_active
                    else 0
                ),
                "typed_strategy_families_seeded": sorted(
                    {str(branch_strategy_family.get(bid, "")) for bid in branch_strategy_seed_order if int(branch_strategy_seed_order.get(bid, -1)) >= 0}
                )
                if typed_seeded_active
                else [],
                "typed_strategy_families_seen": sorted({fam for fam, cnt in family_expansions_by_strategy.items() if int(cnt) > 0})
                if typed_seeded_active
                else [],
                "typed_strategy_family_expansion_counts": {k: int(v) for k, v in family_expansions_by_strategy.items()},
                "typed_strategy_family_action_counts": {k: int(v) for k, v in family_expansions_by_strategy.items()},
                "typed_strategy_family_answer_groups": (
                    {
                        fam: sorted(
                            {
                                str(self._normalize_answer(b.predicted_answer) or "__unknown__")
                                for b in branches
                                if str(branch_strategy_family.get(b.branch_id, "")) == fam and b.predicted_answer is not None
                            }
                        )
                        for fam in family_expansions_by_strategy
                    }
                    if typed_seeded_active
                    else {}
                ),
                "dominant_typed_strategy_family": (
                    max(family_expansions_by_strategy.items(), key=lambda kv: kv[1])[0]
                    if typed_seeded_active and family_expansions_by_strategy
                    else ""
                ),
                "dominant_typed_strategy_family_share": float(
                    (max(family_expansions_by_strategy.values()) / max(1, sum(family_expansions_by_strategy.values())))
                    if typed_seeded_active and family_expansions_by_strategy
                    else 0.0
                ),
                "typed_strategy_min_coverage_satisfied": bool(
                    len({fam for fam, cnt in family_expansions_by_strategy.items() if int(cnt) > 0})
                    >= (2 if self.max_actions < 6 else 3)
                )
                if typed_seeded_active
                else False,
                "typed_strategy_forced_expansion_count": int(family_min_coverage_forced_expansion),
                "typed_strategy_cap_block_count": int(family_cap_blocked_expansion),
                "typed_strategy_redundancy_detected": bool(
                    len(
                        {
                            str(self._normalize_answer(b.predicted_answer) or "__unknown__")
                            for b in branches
                            if b.predicted_answer is not None
                        }
                    )
                    <= 1
                ),
                "typed_strategy_branch_metadata": (
                    [
                        {
                            "branch_id": str(b.branch_id),
                            "strategy_family": str(branch_strategy_family.get(b.branch_id, "")),
                            "strategy_name": (
                                str(branch_strategy_prompt_obj[b.branch_id].strategy_name)
                                if b.branch_id in branch_strategy_prompt_obj
                                else ""
                            ),
                            "strategy_prompt_hash": str(abs(hash(str(branch_strategy_prompt_text.get(b.branch_id, ""))))),
                            "strategy_prompt_text": str(branch_strategy_prompt_text.get(b.branch_id, "")),
                            "strategy_rationale": (
                                str(branch_strategy_prompt_obj[b.branch_id].strategy_rationale)
                                if b.branch_id in branch_strategy_prompt_obj
                                else ""
                            ),
                            "expected_failure_mode_addressed": (
                                str(branch_strategy_prompt_obj[b.branch_id].expected_failure_mode_addressed)
                                if b.branch_id in branch_strategy_prompt_obj
                                else ""
                            ),
                            "initial_seed_order": int(branch_strategy_seed_order.get(b.branch_id, -1)),
                            "typed_seeded": bool(typed_seeded_active),
                            "problem_type_label": str(problem_type_label),
                            "seeded_from_strategy_prompt": bool(b.branch_id in branch_strategy_prompt_obj),
                        }
                        for b in branches
                    ]
                    if typed_seeded_active
                    else []
                ),
                "commit_guard_triggered_count": int(commit_guard_triggered_count),
                "verifier_calls": int(verifier_calls),
                "verifier_pass_count": int(verifier_pass),
                "verifier_warn_count": int(verifier_warn),
                "verifier_fail_count": int(verifier_fail),
                "case_split_direction_aware_v1_enabled": bool(self.enable_case_split_direction_aware_v1),
                "case_split_direction_aware_v1_active": bool(case_split_direction_aware_active),
                "case_split_direction_aware_forced_coverage_steps": int(case_split_direction_aware_forced_coverage_steps),
                "case_split_direction_aware_delay_commit_blocks": int(case_split_direction_aware_delay_commit_blocks),
                "early_divergence_timeline": early_divergence_timeline[: min(12, len(early_divergence_timeline))],
                "gold_answer_group_key": str(gold_group_key),
                "first_meaningful_split_step": first_split_step,
                "second_meaningful_split_step": second_split_step,
                "gold_group_present_after_first_split": bool(gold_present_after_first_split),
                "gold_group_present_after_second_split": bool(gold_present_after_second_split),
                "gold_group_first_present_step": first_present_step,
                "gold_group_last_present_step": last_present_step,
                "gold_group_disappeared_step": disappeared_step,
                "gold_group_ever_present": bool(gold_ever_present),
                "gold_group_present_final": bool(gold_present_final),
                "early_divergence_failure_category": dominant_failure,
                "regime_failure_category": regime_failure_category,
                "hard_early_root_coverage_forced_min_depth": int(self.hard_early_root_coverage_forced_min_depth),
                "hard_early_root_depth2_coverage_v1_enabled": bool(self.hard_early_root_coverage_forced_min_depth == 2),
                "hard_early_root_depth3_coverage_v1_enabled": bool(self.hard_early_root_coverage_forced_min_depth >= 3),
                "hard_early_coverage_forced_override_steps": int(hard_early_coverage_forced_override_steps),
                "hard_early_coverage_transition_actions_used": hard_early_coverage_transition_actions_used,
                "hard_early_coverage_completed_fully": bool(
                    self.hard_early_root_coverage_forced_min_depth >= 2
                    and hard_early_coverage_transition_actions_used is not None
                    and (not hard_early_coverage_budget_released_impossible)
                    and (not hard_early_coverage_budget_released_low_remaining)
                ),
                "hard_early_coverage_budget_released_impossible": bool(hard_early_coverage_budget_released_impossible),
                "hard_early_coverage_budget_released_low_remaining": bool(hard_early_coverage_budget_released_low_remaining),
                "hard_early_coverage_force_disabled_final": bool(hard_early_coverage_force_disabled),
                "exhaustive_probe_budget_truncated": bool(
                    hard_early_coverage_budget_released_impossible or hard_early_coverage_budget_released_low_remaining
                ),
                "exhaustive_probe_transition_actions_used": hard_early_coverage_transition_actions_used,
                "exhaustive_probe_planned_shallow_nodes_unexpanded": int(
                    (
                        self._hard_early_root_coverage_forced_diagnostic(
                            branches=branches,
                            branch_family_ids=branch_family_ids,
                            root_family_ids=root_family_ids,
                            actions_so_far=actions,
                            max_actions=self.max_actions,
                            force_disabled=hard_early_coverage_force_disabled,
                            coverage_target_override=(
                                3
                                if self.enable_hard_early_root_depth2_then_conditional_depth3_v1 and cond_depth3_completed
                                else None
                            ),
                        ).get("actions_needed_sum_lower_bound")
                    )
                    or 0
                ),
                "hard_early_coverage_root_families": sorted(root_family_ids),
                "hard_early_root_depth2_then_conditional_depth3_v1_enabled": bool(
                    self.enable_hard_early_root_depth2_then_conditional_depth3_v1
                ),
                "hard_max_family_expansions_cap_enabled": bool(self.enable_hard_max_family_expansions_cap),
                "hard_max_family_expansions_relax_mode": str(self.hard_max_family_expansions_relax_mode),
                "hard_max_family_expansions_base_cap": int(self.hard_max_family_expansions_base_cap),
                "hard_max_family_expansions_relax_cap": int(self.hard_max_family_expansions_relax_cap),
                "hard_max_family_expansions_relax_cap_high": int(self.hard_max_family_expansions_relax_cap_high),
                "hard_max_family_expansions_conditional_early_window_actions": int(
                    self.hard_max_family_expansions_conditional_early_window_actions
                ),
                "hard_max_family_expansions_conditional_risk_family_share_trigger": float(
                    self.hard_max_family_expansions_conditional_risk_family_share_trigger
                ),
                "hard_max_family_expansions_conditional_risk_consecutive_run_trigger": int(
                    self.hard_max_family_expansions_conditional_risk_consecutive_run_trigger
                ),
                "hard_max_family_expansions_conditional_min_rival_maturity_expansions": int(
                    self.hard_max_family_expansions_conditional_min_rival_maturity_expansions
                ),
                "hard_max_family_expansions_block_count": int(family_cap_block_count),
                "hard_max_family_expansions_relax_activation_count": int(family_cap_relax_activation_count),
                "hard_max_family_expansions_relax_activation_rate": float(
                    family_cap_relax_activation_count / max(1, len(action_trace))
                ),
                "hard_max_family_expansions_mean_relax_delta_on_activation": float(
                    family_cap_relax_delta_sum / max(1, family_cap_relax_activation_count)
                ),
                "hard_max_family_expansions_activation_by_trigger": dict(family_cap_activation_by_trigger),
                "conditional_coverage_phase_final": str(cond_phase or ""),
                "conditional_depth2_gate_actions": cond_depth2_gate_actions,
                "conditional_depth3_gate_record": cond_gate_record,
                "conditional_depth3_forcing_completed": bool(cond_depth3_completed),
                "conditional_depth3_gate_thresholds": {
                    "depth3_gate_min_top_answer_support": float(self.depth3_gate_min_top_answer_support),
                    "depth3_gate_min_support_gap": float(self.depth3_gate_min_support_gap),
                    "depth3_gate_min_active_root_families": int(self.depth3_gate_min_active_root_families),
                    "depth3_gate_max_family_share_trigger": float(self.depth3_gate_max_family_share_trigger),
                    "depth3_gate_longest_run_trigger": int(self.depth3_gate_longest_run_trigger),
                    "depth3_gate_min_confident_frontier_score": float(self.depth3_gate_min_confident_frontier_score),
                    "depth3_gate_min_top_group_support_commit": float(self.depth3_gate_min_top_group_support_commit),
                    "depth3_gate_e_max_top_support": float(self.depth3_gate_e_max_top_support),
                    "depth3_gate_e_min_answer_groups": int(self.depth3_gate_e_min_answer_groups),
                },
                "hard_early_coverage_final_family_status": (
                    self._hard_early_root_coverage_forced_diagnostic(
                        branches=branches,
                        branch_family_ids=branch_family_ids,
                        root_family_ids=root_family_ids,
                        actions_so_far=actions,
                        max_actions=self.max_actions,
                        force_disabled=hard_early_coverage_force_disabled,
                        coverage_target_override=(
                            3
                            if self.enable_hard_early_root_depth2_then_conditional_depth3_v1 and cond_depth3_completed
                            else None
                        ),
                    ).get("family_status")
                    if self.hard_early_root_coverage_forced_min_depth >= 2
                    else {}
                ),
                "unstable_commit_flag": bool(
                    any(
                        bool(c.get("commit_rule_satisfied", False))
                        and (
                            float(c.get("answer_group_margin", 0.0)) < (self.commit_margin_threshold + 0.04)
                            or float(c.get("one_step_value_estimate", 0.0)) > self.continue_one_step_value_threshold
                        )
                        for c in commit_checks
                    )
                ),
                "final_branch_states": (
                    [
                        {
                            "branch_id": str(b.branch_id),
                            "parent_branch_id": str(b.parent_branch_id or ""),
                            "branch_depth": int(b.depth),
                            "score": float(b.score),
                            "predicted_answer": str(b.predicted_answer or ""),
                            "is_done": bool(b.is_done),
                            "is_pruned": bool(b.is_pruned),
                            "steps": list(b.steps),
                            "trace_events": list(b.trace_events),
                            "strategy_family": str(branch_strategy_family.get(b.branch_id, "")),
                        }
                        for b in branches
                    ]
                    if bool(getattr(self, "emit_full_traces", False))
                    else []
                ),
                "final_prediction": prediction,
                "diagnostic_semantic_diversity": {
                    **dict(getattr(self, "_last_diagnostic_semantic_snapshot", {}) or {}),
                    "maturation_phase_audit": list(getattr(self, "_diagnostic_branching_necessity_trace", []) or []),
                    "diagnostic_namespace": "semantic_diversity_v1",
                    "diagnostic_experimental": True,
                },
                **group_meta,
            },
        )


class VerifierGuidedSearchController(BaseController):
    """Best-of-N style search with a pluggable verifier score (not majority vote).

    Candidate generation uses the standard expand path per arm; scoring is isolated
    so PRM-style process verifiers or stronger ORMs can replace the default proxy.
    """

    def __init__(
        self,
        generator: BranchGenerator,
        scorer: BranchScorer,
        max_actions_per_problem: int,
        n_candidates: int,
        verifier: CandidateVerifier,
        min_expansions_per_candidate: int = 1,
        partial_branch_scorer: PartialBranchScorer | None = None,
        enable_prm_early_reject: bool = False,
        prm_early_reject_threshold: float = 0.2,
        method_name: str = "verifier_guided_search",
    ) -> None:
        super().__init__(generator, scorer, max_actions_per_problem)
        self.n_candidates = max(1, n_candidates)
        self._verifier = verifier
        self.min_expansions_per_candidate = max(1, min_expansions_per_candidate)
        self.partial_branch_scorer = partial_branch_scorer
        self.enable_prm_early_reject = enable_prm_early_reject
        self.prm_early_reject_threshold = float(prm_early_reject_threshold)
        self.method_name = method_name

    def run(self, question: str, gold_answer: str) -> MethodResult:
        actions = expansions = verifications = 0
        surviving_trace: list[int] = []
        if self.max_actions < self.n_candidates:
            return MethodResult(
                method=self.method_name,
                prediction=None,
                is_correct=False,
                actions_used=0,
                expansions=0,
                verifications=0,
                avg_surviving_branches=0.0,
                budget_exhausted=True,
                metadata={"error": "budget_smaller_than_n_candidates", "n_candidates": self.n_candidates},
            )

        branches = [self.generator.init_branch(f"vgs_{i}") for i in range(self.n_candidates)]
        branch_partial_scores: list[float | None] = [None for _ in branches]
        branch_early_reject: list[bool] = [False for _ in branches]

        verify_reserved = self.n_candidates
        expand_budget = max(0, self.max_actions - verify_reserved)
        per_candidate_cap = expand_budget // max(1, self.n_candidates)
        if expand_budget >= self.n_candidates * self.min_expansions_per_candidate:
            per_candidate_cap = max(self.min_expansions_per_candidate, per_candidate_cap)

        for branch in branches:
            if actions >= self.max_actions:
                break
            k = 0
            while actions < self.max_actions and k < per_candidate_cap and not branch.is_done:
                self.generator.expand(branch, question, gold_answer)
                actions += 1
                expansions += 1
                k += 1
                surviving_trace.append(self.n_candidates)
            if self.partial_branch_scorer is not None:
                p = self.partial_branch_scorer.score_partial_branch(branch, question, stage="vgs_candidate")
                idx = branches.index(branch)
                branch_partial_scores[idx] = float(p.value)
                if self.enable_prm_early_reject and (not branch.is_done) and p.value < self.prm_early_reject_threshold:
                    self.generator.prune(branch)
                    branch_early_reject[idx] = True

        verifier_scores: list[float] = []
        for branch in branches:
            idx = branches.index(branch)
            if branch_early_reject[idx]:
                verifier_scores.append(float("-inf"))
                continue
            if actions >= self.max_actions:
                verifier_scores.append(float("-inf"))
                continue
            score = self._verifier.score(branch, question)
            verifier_scores.append(float(score))
            actions += 1
            verifications += 1

        best_idx = max(range(len(branches)), key=lambda i: verifier_scores[i])
        best_branch = branches[best_idx]
        prediction = best_branch.predicted_answer

        cost_proxy = {
            "candidate_generations": expansions,
            "verifier_scoring_calls": verifications,
            "n_candidates": self.n_candidates,
            "per_candidate_expansion_cap": per_candidate_cap,
        }

        return MethodResult(
            method=self.method_name,
            prediction=prediction,
            is_correct=self._answers_match(prediction, gold_answer),
            actions_used=actions,
            expansions=expansions,
            verifications=verifications,
            avg_surviving_branches=sum(surviving_trace) / max(1, len(surviving_trace)) if surviving_trace else float(self.n_candidates),
            budget_exhausted=actions >= self.max_actions,
            metadata={
                "verifier_scores": [round(s, 6) for s in verifier_scores],
                "selected_candidate_index": best_idx,
                "cost_proxy": cost_proxy,
                "anti_collapse_min_expansions_per_candidate": self.min_expansions_per_candidate,
                "partial_branch_scores": [None if s is None else round(float(s), 6) for s in branch_partial_scores],
                "partial_score_source": "heuristic_prm_proxy" if self.partial_branch_scorer is not None else "none",
                "prm_early_reject_enabled": self.enable_prm_early_reject,
                "prm_early_reject_threshold": self.prm_early_reject_threshold,
                "prm_early_rejected_candidates": int(sum(1 for x in branch_early_reject if x)),
            },
        )


class ProgramOfThoughtController(BaseController):
    """PAL/PoT-style: one-shot code generation + local sandbox execution."""

    def __init__(
        self,
        generator: BranchGenerator,
        scorer: BranchScorer,
        max_actions_per_problem: int,
        method_name: str = "program_of_thought",
    ) -> None:
        super().__init__(generator, scorer, max_actions_per_problem)
        self.method_name = method_name

    def run(self, question: str, gold_answer: str) -> MethodResult:
        if not hasattr(self.generator, "generate_program_of_thought_answer"):
            return MethodResult(
                method=self.method_name,
                prediction=None,
                is_correct=False,
                actions_used=0,
                expansions=0,
                verifications=0,
                avg_surviving_branches=0.0,
                budget_exhausted=True,
                metadata={"error": "generator_missing_generate_program_of_thought_answer"},
            )

        gen_fn = getattr(self.generator, "generate_program_of_thought_answer")
        out = gen_fn(question)
        prediction = out.get("prediction") if isinstance(out, dict) else None
        pred_str = None if prediction is None else str(prediction)

        cu = out.get("cost_units") if isinstance(out, dict) else {}
        gen_units = int(cu.get("generation", 1)) if isinstance(cu, dict) else 1
        exec_units = int(cu.get("execution", 1)) if isinstance(cu, dict) else 1
        total_units = gen_units + exec_units
        actions_used = min(self.max_actions, total_units)
        exhausted = self.max_actions < total_units

        return MethodResult(
            method=self.method_name,
            prediction=pred_str,
            is_correct=self._answers_match(pred_str, gold_answer),
            actions_used=actions_used,
            expansions=1,
            verifications=0,
            avg_surviving_branches=1.0,
            budget_exhausted=exhausted,
            metadata={
                "pot_output": out,
                "cost_proxy": {"code_generation": gen_units, "sandbox_execution": exec_units},
            },
        )


class S1BudgetForcingController(BaseController):
    """External baseline adapter for s1-style test-time scaling budget forcing.

    This approximates the inference-time loop from the s1 repository:
    when generation reaches an end-of-thinking stop, append a short "wait"
    continuation cue and keep reasoning, up to a configured number of forced
    continuations and an overall action budget.
    """

    def __init__(
        self,
        generator: BranchGenerator,
        scorer: BranchScorer,
        max_actions_per_problem: int,
        *,
        num_ignore_think_end: int = 1,
        min_thinking_steps: int = 0,
        wait_token: str = "Wait",
        method_name: str = "external_s1_budget_forcing",
    ) -> None:
        super().__init__(generator, scorer, max_actions_per_problem)
        self.num_ignore_think_end = max(0, int(num_ignore_think_end))
        self.min_thinking_steps = max(0, int(min_thinking_steps))
        self.wait_token = wait_token
        self.method_name = method_name

    @staticmethod
    def _estimate_token_count(text: str | None) -> int:
        if text is None:
            return 0
        s = str(text).strip()
        if not s:
            return 0
        return len(s.split())

    def run(self, question: str, gold_answer: str) -> MethodResult:
        branch = self.generator.init_branch("s1_0")
        actions = expansions = verifications = 0
        surviving_trace: list[int] = []
        forced_continue_events = 0

        while actions < self.max_actions:
            if branch.is_pruned:
                break
            if branch.is_done:
                need_min_thinking = expansions < self.min_thinking_steps
                can_force_continue = forced_continue_events < self.num_ignore_think_end
                if need_min_thinking or can_force_continue:
                    forced_continue_events += 1
                    branch.is_done = False
                    branch.predicted_answer = None
                    branch.steps.append(f"{self.wait_token} (forced-continue)")
                else:
                    break

            self.generator.expand(branch, question, gold_answer)
            actions += 1
            expansions += 1
            surviving_trace.append(1)

        prediction = branch.predicted_answer
        realized_reasoning_tokens_estimate = sum(self._estimate_token_count(step) for step in branch.steps)
        final_answer_tokens_estimate = self._estimate_token_count(prediction)
        continuation_override_tokens_estimate = forced_continue_events * self._estimate_token_count(self.wait_token)
        total_generated_tokens_estimate = realized_reasoning_tokens_estimate + final_answer_tokens_estimate
        return MethodResult(
            method=self.method_name,
            prediction=prediction,
            is_correct=self._answers_match(prediction, gold_answer),
            actions_used=actions,
            expansions=expansions,
            verifications=verifications,
            avg_surviving_branches=sum(surviving_trace) / max(1, len(surviving_trace)),
            budget_exhausted=actions >= self.max_actions and not branch.is_done,
            metadata={
                "external_baseline_family": "s1_simple_test_time_scaling",
                "num_ignore_think_end": self.num_ignore_think_end,
                "min_thinking_steps": self.min_thinking_steps,
                "wait_token": self.wait_token,
                "forced_continue_events": forced_continue_events,
                "nominal_budget_actions": self.max_actions,
                "realized_reasoning_tokens_estimate": realized_reasoning_tokens_estimate,
                "final_answer_tokens_estimate": final_answer_tokens_estimate,
                "total_generated_tokens_estimate": total_generated_tokens_estimate,
                "continuation_override_tokens_estimate": continuation_override_tokens_estimate,
                "continuation_override_accounting_policy": "forced_continue_events * wait_token_word_count",
                "final_score": self.scorer.score_branch(branch),
            },
        )


class TALEPromptBudgetingController(BaseController):
    """External baseline adapter for TALE-style per-instance token budgeting.

    Faithful core idea: estimate a per-instance token budget, inject the budget
    into the reasoning prompt, and constrain generation under that budget.
    This controller adapts TALE's token budget notion to the repo's action-based
    frontier environment using an explicit token-to-action conversion.
    """

    def __init__(
        self,
        generator: BranchGenerator,
        scorer: BranchScorer,
        max_actions_per_problem: int,
        *,
        token_budget_default: int = 256,
        token_budget_min: int = 64,
        token_budget_max: int = 512,
        token_budget_per_question_char: float = 0.75,
        token_per_action: float = 64.0,
        method_name: str = "external_tale_prompt_budgeting",
    ) -> None:
        super().__init__(generator, scorer, max_actions_per_problem)
        self.token_budget_default = max(1, int(token_budget_default))
        self.token_budget_min = max(1, int(token_budget_min))
        self.token_budget_max = max(self.token_budget_min, int(token_budget_max))
        self.token_budget_per_question_char = max(0.0, float(token_budget_per_question_char))
        self.token_per_action = max(1.0, float(token_per_action))
        self.method_name = method_name

    def _estimate_budget_tokens(self, question: str) -> int:
        char_count = len(question.strip())
        est = int(round(self.token_budget_default + self.token_budget_per_question_char * char_count))
        return max(self.token_budget_min, min(self.token_budget_max, est))

    @staticmethod
    def _estimate_generated_tokens(text: str | None) -> int:
        if not text:
            return 0
        return len(re.findall(r"\S+", text))

    def run(self, question: str, gold_answer: str) -> MethodResult:
        branch = self.generator.init_branch("tale_0")
        actions = expansions = verifications = 0
        surviving_trace: list[int] = []

        budget_tokens = self._estimate_budget_tokens(question)
        budget_actions = max(1, int(round(budget_tokens / self.token_per_action)))
        allowed_actions = min(self.max_actions, budget_actions)

        budgeted_question = (
            f"{question}\n"
            f"Let's think step by step and use less than {budget_tokens} tokens."
        )

        while actions < allowed_actions and not branch.is_done and not branch.is_pruned:
            self.generator.expand(branch, budgeted_question, gold_answer)
            actions += 1
            expansions += 1
            surviving_trace.append(1)

        prediction = branch.predicted_answer
        generated_tokens_estimate = self._estimate_generated_tokens(prediction)
        budget_violation = generated_tokens_estimate > budget_tokens

        return MethodResult(
            method=self.method_name,
            prediction=prediction,
            is_correct=self._answers_match(prediction, gold_answer),
            actions_used=actions,
            expansions=expansions,
            verifications=verifications,
            avg_surviving_branches=sum(surviving_trace) / max(1, len(surviving_trace)),
            budget_exhausted=actions >= allowed_actions and not branch.is_done,
            metadata={
                "external_baseline_family": "token_budget_aware_llm_reasoning_tale",
                "token_budget_estimator": "char_length_linear",
                "token_budget_default": self.token_budget_default,
                "token_budget_min": self.token_budget_min,
                "token_budget_max": self.token_budget_max,
                "token_budget_per_question_char": self.token_budget_per_question_char,
                "token_budget_predicted": budget_tokens,
                "token_per_action": self.token_per_action,
                "budget_actions_equivalent": budget_actions,
                "generated_tokens_estimate": generated_tokens_estimate,
                "token_budget_violation": budget_violation,
                "final_score": self.scorer.score_branch(branch),
            },
        )




class DirectReserveGateRerankController(BaseController):
    """Diagnostic hybrid: reserve direct-chain attempts, gate branching, then rerank by answer-group support.

    This controller is intentionally diagnostic/experimental and should not replace canonical strict_f3.
    """

    def __init__(
        self,
        generator: BranchGenerator,
        scorer: BranchScorer,
        max_actions_per_problem: int,
        *,
        strict_controller_factory: callable,
        direct_prompt_style: str = "Let's think step by step and output the final answer within \boxed{}.",
        direct_prompt_styles: list[str] | None = None,
        direct_reserve_attempts_override: int | None = None,
        direct_token_budget: int = 512,
        direct_token_per_action: float = 64.0,
        gate_top_support_threshold: float = 0.75,
        gate_top2_gap_threshold: float = 0.50,
        gate_entropy_threshold: float = 0.55,
        enable_margin_gate_fallback: bool = False,
        margin_gate_min_support_gap: int = 1,
        margin_gate_max_entropy: float = 0.95,
        margin_gate_require_multi_prompt_style: bool = False,
        enable_learned_override: bool = False,
        learned_override_model_path: str = "",
        learned_override_model_type: str = DIRECT_RESERVE_LEARNED_OVERRIDE_DEFAULT_MODEL,
        learned_override_margin: float = 0.05,
        diagnostic_challenger_resistance: bool = False,
        method_name: str = "strict_f3_direct_reserve_gate_rerank_v1",
    ) -> None:
        super().__init__(generator, scorer, max_actions_per_problem)
        self.strict_controller_factory = strict_controller_factory
        self.direct_prompt_style = direct_prompt_style
        self.direct_prompt_styles = [str(s).strip() for s in (direct_prompt_styles or []) if str(s).strip()]
        self.direct_reserve_attempts_override = (
            None if direct_reserve_attempts_override is None else max(1, int(direct_reserve_attempts_override))
        )
        self.direct_token_budget = max(1, int(direct_token_budget))
        self.direct_token_per_action = max(1.0, float(direct_token_per_action))
        self.gate_top_support_threshold = float(gate_top_support_threshold)
        self.gate_top2_gap_threshold = float(gate_top2_gap_threshold)
        self.gate_entropy_threshold = float(gate_entropy_threshold)
        self.enable_margin_gate_fallback = bool(enable_margin_gate_fallback)
        self.margin_gate_min_support_gap = max(0, int(margin_gate_min_support_gap))
        self.margin_gate_max_entropy = float(margin_gate_max_entropy)
        self.margin_gate_require_multi_prompt_style = bool(margin_gate_require_multi_prompt_style)
        self.enable_learned_override = bool(enable_learned_override)
        self.learned_override_model_path = str(learned_override_model_path or "")
        self.learned_override_model_type = str(learned_override_model_type or DIRECT_RESERVE_LEARNED_OVERRIDE_DEFAULT_MODEL)
        self.learned_override_margin = max(0.0, float(learned_override_margin))
        self.diagnostic_challenger_resistance = bool(diagnostic_challenger_resistance)
        self.method_name = method_name

    def _direct_reserve_attempts(self) -> int:
        if self.direct_reserve_attempts_override is not None:
            return int(self.direct_reserve_attempts_override)
        if self.max_actions <= 4:
            return 1
        if self.max_actions <= 6:
            return 2 if self.max_actions >= 6 else 1
        if self.max_actions <= 8:
            return 2
        return 2

    @staticmethod
    def _entropy(counts: dict[str, int]) -> float:
        total = max(1, sum(int(v) for v in counts.values()))
        probs = [float(v) / total for v in counts.values() if int(v) > 0]
        if len(probs) <= 1:
            return 0.0
        ent = -sum(p * math.log(max(1e-12, p)) for p in probs)
        return float(ent / math.log(len(probs)))

    def _run_direct_attempt(self, question: str, gold_answer: str, idx: int, max_actions: int) -> tuple[str | None, int, list[dict[str, Any]]]:
        branch = self.generator.init_branch(f"direct_reserve_{idx}")
        actions = 0
        trace: list[dict[str, Any]] = []
        prompt_style = self.direct_prompt_style
        if self.direct_prompt_styles:
            prompt_style = self.direct_prompt_styles[idx % len(self.direct_prompt_styles)]
        prompt = f"{question}\n\n{prompt_style} Think for maximum {self.direct_token_budget} tokens."
        while actions < max_actions and not branch.is_done and not branch.is_pruned:
            self.generator.expand(branch, prompt, gold_answer)
            actions += 1
            latest = branch.trace_events[-1] if branch.trace_events else {}
            trace.append(
                {
                    "action": "expand",
                    "branch_id": branch.branch_id,
                    "prompt_text": str(latest.get("prompt_text", "")),
                    "response_text": str(latest.get("response_text", "")),
                    "reasoning_text": str(latest.get("reasoning_text", "")),
                    "extracted_answer": str(latest.get("extracted_answer", "") or ""),
                }
            )
        return branch.predicted_answer, actions, trace

    def run(self, question: str, gold_answer: str) -> MethodResult:
        reserve_attempts = self._direct_reserve_attempts()
        per_attempt_cap = max(1, int(round(self.direct_token_budget / self.direct_token_per_action)))
        direct_answers: list[str | None] = []
        direct_actions = 0
        direct_trace: list[dict[str, Any]] = []

        for i in range(reserve_attempts):
            if direct_actions >= self.max_actions:
                break
            ans, used, tr = self._run_direct_attempt(question, gold_answer, i, min(per_attempt_cap, self.max_actions - direct_actions))
            direct_answers.append(ans)
            direct_actions += int(used)
            direct_trace.extend(tr)

        direct_counts: Counter[str] = Counter((_normalize_answer(a) or "__unknown__") for a in direct_answers if a is not None)
        total_direct = max(1, sum(direct_counts.values()))
        sorted_counts = sorted(direct_counts.items(), key=lambda kv: kv[1], reverse=True)
        top_group = sorted_counts[0][0] if sorted_counts else "__unknown__"
        top_count = int(sorted_counts[0][1]) if sorted_counts else 0
        second_count = int(sorted_counts[1][1]) if len(sorted_counts) > 1 else 0
        top_support = float(top_count / total_direct)
        top2_gap = float((top_count - second_count) / total_direct)
        entropy = self._entropy(dict(direct_counts))

        remaining_budget = max(0, self.max_actions - direct_actions)
        direct_stable = bool(top_support >= self.gate_top_support_threshold and top2_gap >= self.gate_top2_gap_threshold and entropy <= self.gate_entropy_threshold)
        gate_decision = "select_direct" if (direct_stable and remaining_budget <= max(2, self.max_actions // 3)) else "allow_frontier"

        frontier_result: MethodResult | None = None
        if remaining_budget > 0 and gate_decision == "allow_frontier":
            frontier = self.strict_controller_factory(remaining_budget)
            frontier_result = frontier.run(question, gold_answer)

        candidate_answers: list[str | None] = list(direct_answers)
        if frontier_result is not None:
            candidate_answers.append(frontier_result.prediction)

        group_counts: Counter[str] = Counter((_normalize_answer(a) or "__unknown__") for a in candidate_answers if a is not None)
        if not group_counts:
            prediction = None
            selected_group = "__unknown__"
        else:
            max_support = max(group_counts.values())
            tied_groups = sorted([g for g, c in group_counts.items() if c == max_support])
            if len(tied_groups) == 1:
                selected_group = tied_groups[0]
            else:
                selected_group = top_group if top_group in tied_groups else tied_groups[0]
            # recover original answer text for selected group
            prediction = next((a for a in candidate_answers if (_normalize_answer(a) or "__unknown__") == selected_group), None)

        dr_incumbent_replaced: bool | None = None
        dr_replacement_reason = "not_applicable"
        if self.diagnostic_challenger_resistance and direct_answers and group_counts and frontier_result is not None:
            d0g = _normalize_answer(direct_answers[0]) or "__unknown__"
            dcount = int(group_counts.get(d0g, 0))
            best_other = 0
            for g, c in group_counts.items():
                if g == d0g:
                    continue
                best_other = max(best_other, int(c))
            if best_other > dcount:
                dr_incumbent_replaced = True
                dr_replacement_reason = "challenger_answer_group_strictly_higher_support"
            else:
                selected_group = d0g
                prediction = direct_answers[0]
                dr_incumbent_replaced = False
                dr_replacement_reason = "protected_direct_incumbent"

        support_sorted = sorted(group_counts.items(), key=lambda kv: kv[1], reverse=True)
        rerank_top_group = support_sorted[0][0] if support_sorted else "__unknown__"
        rerank_top = int(support_sorted[0][1]) if support_sorted else 0
        rerank_second = int(support_sorted[1][1]) if len(support_sorted) > 1 else 0
        rerank_gap = float((rerank_top - rerank_second) / max(1, sum(group_counts.values())))
        rerank_margin_abs = int(rerank_top - rerank_second)
        rerank_entropy = self._entropy(dict(group_counts))

        selected_before_gate = str(selected_group)
        selected_after_gate = str(selected_group)
        fallback_source = "none"
        gate_reason = "not_enabled"
        margin_gate_triggered = False
        fallback_used = False
        prompt_style_groups: dict[str, set[str]] = defaultdict(set)
        for i, answer in enumerate(direct_answers):
            g = _normalize_answer(answer) or "__unknown__"
            prompt_style_key = (
                self.direct_prompt_styles[i % len(self.direct_prompt_styles)]
                if self.direct_prompt_styles
                else self.direct_prompt_style
            )
            prompt_style_groups[g].add(prompt_style_key)
        top_group_prompt_style_support = len(prompt_style_groups.get(rerank_top_group, set()))
        prompt_style_agreement = int(top_group_prompt_style_support >= 2)

        if self.enable_margin_gate_fallback and group_counts:
            low_margin = rerank_margin_abs < self.margin_gate_min_support_gap
            high_entropy = rerank_entropy > self.margin_gate_max_entropy
            weak_prompt_agreement = self.margin_gate_require_multi_prompt_style and not prompt_style_agreement
            trigger = bool(low_margin or high_entropy or weak_prompt_agreement)
            if trigger:
                margin_gate_triggered = True
                reasons: list[str] = []
                if low_margin:
                    reasons.append("low_margin_selection")
                if high_entropy:
                    reasons.append("high_entropy_disagreement")
                if weak_prompt_agreement:
                    reasons.append("prompt_style_disagreement")
                gate_reason = ",".join(reasons) if reasons else "gate_triggered"

                direct_primary_group = _normalize_answer(direct_answers[0]) if direct_answers else None
                direct_primary_group = direct_primary_group or "__unknown__"
                if direct_primary_group in group_counts:
                    selected_after_gate = direct_primary_group
                    fallback_source = "direct_reserve_primary"
                elif rerank_top_group in group_counts:
                    selected_after_gate = rerank_top_group
                    fallback_source = "support_top_group"
                else:
                    selected_after_gate = selected_before_gate
                    fallback_source = "none"
                fallback_used = bool(selected_after_gate != selected_before_gate)
            else:
                gate_reason = "clear_support"

        selected_group = selected_after_gate
        prediction = next((a for a in candidate_answers if (_normalize_answer(a) or "__unknown__") == selected_group), prediction)

        learned_override_meta: dict[str, Any] = {
            "learned_override_available": False,
            "learned_override_triggered": False,
            "learned_override_model": str(self.learned_override_model_type),
            "learned_override_margin": 0.0,
            "learned_override_threshold": float(self.learned_override_margin),
            "base_selected_answer": str(selected_group),
            "learned_selected_answer": "",
            "final_selected_answer": str(selected_group),
            "learned_override_reason": "disabled",
            "learned_override_missing_features": [],
            "candidate_feature_schema_version": "direct_reserve_candidate_scorer_dataset_v1",
            "candidate_count": int(sum(group_counts.values())),
            "answer_group_count": int(len(group_counts)),
        }
        if self.enable_learned_override:
            normalized_candidates = [(_normalize_answer(a) or "__unknown__") for a in candidate_answers if a is not None]
            learned_candidates = build_runtime_answer_group_candidates(
                question=question,
                dataset="openai/gsm8k",
                seed=0,
                budget=int(self.max_actions),
                method="direct_reserve_strong_plus_diverse_v1",
                candidate_answers=normalized_candidates,
                selected_group=str(selected_group),
                top2_support_gap=float(rerank_gap),
                answer_entropy=float(rerank_entropy),
                action_count=int(actions_used := direct_actions + (frontier_result.actions_used if frontier_result else 0)),
                expansion_count=int(direct_actions + (frontier_result.expansions if frontier_result else 0)),
                verification_count=int(frontier_result.verifications if frontier_result else 0),
            )
            learned_result = select_learned_override(
                learned_candidates,
                base_selected_answer=str(selected_group),
                margin_threshold=float(self.learned_override_margin),
                model_path=self.learned_override_model_path or None,
                model_type=self.learned_override_model_type,
            )
            learned_override_meta = dict(learned_result.metadata)
            selected_group = str(learned_result.final_answer or selected_group)
            prediction = next((a for a in candidate_answers if (_normalize_answer(a) or "__unknown__") == selected_group), prediction)

        gold_group = _normalize_answer(gold_answer)
        gold_present = int(gold_group in group_counts)
        absent_from_tree = int(not gold_present)
        present_not_selected = int(gold_present and selected_group != gold_group)

        actions_used = int(direct_actions + (frontier_result.actions_used if frontier_result else 0))
        expansions = int(direct_actions + (frontier_result.expansions if frontier_result else 0))
        verifications = int(frontier_result.verifications if frontier_result else 0)
        metadata = {
            "method_family": "diagnostic_direct_reserve_gate_rerank",
            "diagnostic_only": True,
            "not_canonical": True,
            "direct_reserve_attempts_planned": int(reserve_attempts),
            "direct_reserve_attempts_executed": int(len(direct_answers)),
            "direct_reserve_actions_used": int(direct_actions),
            "branching_gate_decision": str(gate_decision),
            "direct_answer_group_counts": dict(direct_counts),
            "direct_top_support": float(top_support),
            "direct_top2_support_gap": float(top2_gap),
            "direct_answer_entropy": float(entropy),
            "remaining_budget_before_frontier": int(remaining_budget),
            "frontier_executed": bool(frontier_result is not None),
            "selected_answer_group": str(selected_group),
            "selected_before_gate": str(selected_before_gate),
            "selected_after_gate": str(selected_after_gate),
            "top_answer_group": str(rerank_top_group),
            "answer_group_support_counts": dict(group_counts),
            "top2_support_gap": float(rerank_gap),
            "support_margin": int(rerank_margin_abs),
            "answer_entropy": float(rerank_entropy),
            "num_answer_groups": int(len(group_counts)),
            "prompt_style_agreement": int(prompt_style_agreement),
            "margin_gate_triggered": bool(margin_gate_triggered),
            "fallback_used": bool(fallback_used),
            "fallback_source": str(fallback_source),
            "gate_reason": str(gate_reason),
            "gold_answer_present_in_candidate_pool": int(gold_present),
            "absent_from_tree": int(absent_from_tree),
            "present_not_selected": int(present_not_selected),
            "direct_action_trace": direct_trace,
            "frontier_metadata": (frontier_result.metadata if frontier_result else {}),
            "diagnostic_challenger_resistance": bool(self.diagnostic_challenger_resistance),
            "incumbent_replaced": dr_incumbent_replaced,
            "incumbent_replacement_reason": str(dr_replacement_reason),
            **learned_override_meta,
        }
        action_trace = list(frontier_result.metadata.get("action_trace", [])) if frontier_result else []
        final_branch_states = list(frontier_result.metadata.get("final_branch_states", [])) if frontier_result else []
        for i, answer in enumerate(direct_answers):
            group_key = _normalize_answer(answer) or "__unknown__"
            action_trace.append(
                {
                    "step": len(action_trace),
                    "action": "direct_reserve",
                    "branch_id": f"direct_reserve_{i}",
                    "group_key": group_key,
                    "is_terminal": 1,
                    "selected": int(group_key == selected_group),
                    "source": "direct_reserve",
                }
            )
            final_branch_states.append(
                {
                    "branch_id": f"direct_reserve_{i}",
                    "state_id": f"direct_reserve_state_{i}",
                    "predicted_answer": "" if answer is None else str(answer),
                    "group_key": group_key,
                    "is_terminal": 1,
                    "selected": int(group_key == selected_group),
                    "source": "direct_reserve",
                    "score": float(group_counts.get(group_key, 0)),
                }
            )
        metadata["action_trace"] = action_trace
        metadata["final_branch_states"] = final_branch_states
        return MethodResult(
            method=self.method_name,
            prediction=prediction,
            is_correct=self._answers_match(prediction, gold_answer),
            actions_used=actions_used,
            expansions=expansions,
            verifications=verifications,
            avg_surviving_branches=float(frontier_result.avg_surviving_branches if frontier_result else 1.0),
            budget_exhausted=bool(actions_used >= self.max_actions),
            metadata=metadata,
        )


class DirectReserveGateRerankControllerV2(DirectReserveGateRerankController):
    """Cheaper direct-reserve v2 diagnostic controller.

    Intent: preserve v1 incumbent-protection benefits while reducing frontier actions.
    """

    def __init__(
        self,
        generator: BranchGenerator,
        scorer: BranchScorer,
        max_actions_per_problem: int,
        *,
        strict_controller_factory: callable,
        direct_prompt_style: str = "Let's think step by step and output the final answer within \\boxed{}.",
        direct_prompt_styles: list[str] | None = None,
        direct_reserve_attempts_override: int | None = None,
        direct_token_budget: int = 384,
        direct_token_per_action: float = 64.0,
        gate_top_support_threshold: float = 0.70,
        gate_top2_gap_threshold: float = 0.35,
        gate_entropy_threshold: float = 0.78,
        frontier_challenge_cap_small: int = 1,
        frontier_challenge_cap_large: int = 2,
        method_name: str = "direct_reserve_semantic_frontier_v2",
    ) -> None:
        super().__init__(
            generator,
            scorer,
            max_actions_per_problem,
            strict_controller_factory=strict_controller_factory,
            direct_prompt_style=direct_prompt_style,
            direct_prompt_styles=direct_prompt_styles,
            direct_reserve_attempts_override=direct_reserve_attempts_override,
            direct_token_budget=direct_token_budget,
            direct_token_per_action=direct_token_per_action,
            gate_top_support_threshold=gate_top_support_threshold,
            gate_top2_gap_threshold=gate_top2_gap_threshold,
            gate_entropy_threshold=gate_entropy_threshold,
            diagnostic_challenger_resistance=False,
            method_name=method_name,
        )
        self.frontier_challenge_cap_small = max(1, int(frontier_challenge_cap_small))
        self.frontier_challenge_cap_large = max(self.frontier_challenge_cap_small, int(frontier_challenge_cap_large))

    @staticmethod
    def _is_parseable_answer(answer: str | None) -> bool:
        g = _normalize_answer(answer)
        return bool(g and g != "__unknown__")

    @staticmethod
    def _question_signal(question: str) -> dict[str, Any]:
        q = str(question or "")
        nums = re.findall(r"[-+]?\d+(?:\.\d+)?", q.replace(",", ""))
        op = classify_problem_type(q)
        words = max(1, len(q.split()))
        low_complex = bool(words <= 36 and len(nums) <= 3 and op not in {"counting_combinatorics", "case_split"})
        moderate_complex = bool(words <= 65 and len(nums) <= 6)
        return {
            "question_len_words": int(words),
            "question_numeric_count": int(len(nums)),
            "operation_type": str(op),
            "low_complexity_proxy": bool(low_complex),
            "moderate_complexity_proxy": bool(moderate_complex),
        }

    def run(self, question: str, gold_answer: str) -> MethodResult:
        reserve_attempts = self._direct_reserve_attempts()
        per_attempt_cap = max(1, int(round(self.direct_token_budget / self.direct_token_per_action)))
        direct_answers: list[str | None] = []
        direct_trace: list[dict[str, Any]] = []
        direct_actions = 0

        # A. direct incumbent first
        first_answer, first_used, first_trace = self._run_direct_attempt(
            question, gold_answer, 0, min(per_attempt_cap, self.max_actions)
        )
        direct_answers.append(first_answer)
        direct_actions += int(first_used)
        direct_trace.extend(first_trace)
        incumbent_raw = first_answer
        incumbent_canonical = _normalize_answer(incumbent_raw) or "__unknown__"
        incumbent_parseable = self._is_parseable_answer(incumbent_raw)

        qsig = self._question_signal(question)
        remaining_budget = max(0, self.max_actions - direct_actions)

        # Optional single extra direct continuation (cheap uncertainty signal).
        second_answer: str | None = None
        if reserve_attempts > 1 and remaining_budget > 0:
            second_answer, used2, tr2 = self._run_direct_attempt(
                question, gold_answer, 1, min(1, per_attempt_cap, remaining_budget)
            )
            direct_answers.append(second_answer)
            direct_actions += int(used2)
            direct_trace.extend(tr2)
            remaining_budget = max(0, self.max_actions - direct_actions)

        direct_counts: Counter[str] = Counter((_normalize_answer(a) or "__unknown__") for a in direct_answers if a is not None)
        total_direct = max(1, sum(direct_counts.values()))
        sorted_counts = sorted(direct_counts.items(), key=lambda kv: kv[1], reverse=True)
        top_group = sorted_counts[0][0] if sorted_counts else "__unknown__"
        top_count = int(sorted_counts[0][1]) if sorted_counts else 0
        second_count = int(sorted_counts[1][1]) if len(sorted_counts) > 1 else 0
        top_support = float(top_count / total_direct)
        top2_gap = float((top_count - second_count) / total_direct)
        entropy = self._entropy(dict(direct_counts))
        direct_disagreement = bool(second_answer is not None and (_normalize_answer(second_answer) or "__unknown__") != incumbent_canonical)
        incumbent_non_empty = bool(str(incumbent_raw or "").strip())
        incumbent_confidence_proxy = float(0.55 * top_support + 0.30 * top2_gap + 0.15 * (1.0 - entropy))

        # B/C. route decision
        high_uncertainty = bool(
            (not incumbent_parseable)
            or (not incumbent_non_empty)
            or direct_disagreement
            or (top_support < self.gate_top_support_threshold)
            or (entropy > self.gate_entropy_threshold)
        )
        route_decision = "stop_with_incumbent"
        route_reason = "incumbent_stable_low_uncertainty"
        if high_uncertainty and remaining_budget > 0:
            route_decision = "limited_frontier_challenge"
            route_reason = "high_uncertainty_or_disagreement"
        elif not high_uncertainty and remaining_budget > 0 and not qsig["low_complexity_proxy"]:
            route_decision = "one_more_direct_continuation"
            route_reason = "moderate_complexity_low_uncertainty"

        if self.max_actions <= 4 and not high_uncertainty:
            route_decision = "stop_with_incumbent"
            route_reason = "small_budget_keep_incumbent"

        if route_decision == "one_more_direct_continuation" and remaining_budget > 0:
            ans3, used3, tr3 = self._run_direct_attempt(
                question, gold_answer, len(direct_answers), min(1, per_attempt_cap, remaining_budget)
            )
            direct_answers.append(ans3)
            direct_actions += int(used3)
            direct_trace.extend(tr3)
            remaining_budget = max(0, self.max_actions - direct_actions)

        # D. limited frontier challenge
        frontier_result: MethodResult | None = None
        frontier_actions_used = 0
        frontier_opened = False
        if route_decision == "limited_frontier_challenge" and remaining_budget > 0:
            frontier_opened = True
            cap = self.frontier_challenge_cap_small if self.max_actions <= 6 else self.frontier_challenge_cap_large
            challenge_budget = min(remaining_budget, cap)
            frontier = self.strict_controller_factory(challenge_budget)
            frontier_result = frontier.run(question, gold_answer)
            frontier_actions_used = int(frontier_result.actions_used)

        # E/F. strict replacement with focused commit comparison.
        incumbent_answer = incumbent_raw
        incumbent_group = incumbent_canonical
        top_challenger_answer = frontier_result.prediction if frontier_result is not None else None
        top_challenger_group = _normalize_answer(top_challenger_answer) or "__unknown__"
        challenger_count = int(1 if frontier_result is not None and top_challenger_answer is not None else 0)

        candidate_answers: list[str | None] = [incumbent_answer]
        if top_challenger_answer is not None:
            candidate_answers.append(top_challenger_answer)
        group_counts: Counter[str] = Counter((_normalize_answer(a) or "__unknown__") for a in candidate_answers if a is not None)
        incumbent_support = int(group_counts.get(incumbent_group, 0))
        top_challenger_support = int(group_counts.get(top_challenger_group, 0))

        frontier_meta = dict(frontier_result.metadata or {}) if frontier_result is not None else {}
        f_dsem = (
            frontier_meta.get("diagnostic_semantic_diversity")
            if isinstance(frontier_meta.get("diagnostic_semantic_diversity"), dict)
            else {}
        ) or {}
        semantic_family_count = int(f_dsem.get("semantic_family_count") or 0)
        family_redundancy_ratio = float(f_dsem.get("family_redundancy_ratio") or 0.0)
        challenger_family_support = 0
        sem_fams = f_dsem.get("semantic_families")
        if isinstance(sem_fams, dict):
            for fam_members in sem_fams.values():
                if not isinstance(fam_members, list):
                    continue
                if any((_normalize_answer(str(m.get("features", {}).get("answer_group_bucket", "") if isinstance(m, dict) else "")) or "__unknown__") == top_challenger_group for m in fam_members):
                    challenger_family_support += 1

        replace = False
        replace_reason = "keep_incumbent_default"
        challenger_parseable = self._is_parseable_answer(top_challenger_answer)
        if top_challenger_answer is not None:
            if (not incumbent_parseable) and challenger_parseable:
                replace = True
                replace_reason = "incumbent_unparseable_challenger_parseable"
            elif challenger_parseable and top_challenger_support > incumbent_support:
                replace = True
                replace_reason = "challenger_strictly_higher_support_parseable"
            elif challenger_parseable and challenger_family_support >= 2:
                replace = True
                replace_reason = "challenger_supported_by_two_semantic_families"
            else:
                replace = False
                replace_reason = "challenger_below_replacement_threshold"

        final_answer = top_challenger_answer if replace and top_challenger_answer is not None else incumbent_answer
        final_source = "challenger" if replace and top_challenger_answer is not None else "incumbent"

        actions_used = int(direct_actions + frontier_actions_used)
        expansions = int(direct_actions + (frontier_result.expansions if frontier_result else 0))
        verifications = int(frontier_result.verifications if frontier_result else 0)
        is_correct = self._answers_match(final_answer, gold_answer)

        metadata = {
            "method_family": "diagnostic_direct_reserve_semantic_frontier_v2",
            "diagnostic_only": True,
            "not_canonical": True,
            "route_decision": str(route_decision),
            "route_reason": str(route_reason),
            "incumbent_raw": "" if incumbent_raw is None else str(incumbent_raw),
            "incumbent_canonical": str(incumbent_canonical),
            "incumbent_parseable": int(incumbent_parseable),
            "incumbent_non_empty": int(incumbent_non_empty),
            "incumbent_confidence_proxy": float(max(0.0, min(1.0, incumbent_confidence_proxy))),
            "direct_disagreement": int(direct_disagreement),
            "question_len_words": int(qsig["question_len_words"]),
            "question_numeric_count": int(qsig["question_numeric_count"]),
            "operation_type": str(qsig["operation_type"]),
            "frontier_opened": int(frontier_opened),
            "frontier_actions_used": int(frontier_actions_used),
            "direct_actions_used": int(direct_actions),
            "challenger_count": int(challenger_count),
            "semantic_family_count": int(semantic_family_count),
            "family_redundancy_ratio": float(family_redundancy_ratio),
            "top_challenger_answer": "" if top_challenger_answer is None else str(top_challenger_answer),
            "top_challenger_support": int(top_challenger_support),
            "incumbent_kept_or_replaced": "replaced" if replace else "kept",
            "incumbent_replacement_reason": str(replace_reason),
            "final_source": str(final_source),
            "action_savings_vs_v1": "",
            "correctness_post_hoc": int(is_correct),
            "answer_support_counts": dict(group_counts),
            "top2_gap_answer_support": float(top2_gap),
            "answer_entropy": float(entropy),
            "frontier_metadata": frontier_meta,
            "direct_action_trace": direct_trace,
        }

        action_trace = list(frontier_meta.get("action_trace", [])) if frontier_meta else []
        final_branch_states = list(frontier_meta.get("final_branch_states", [])) if frontier_meta else []
        for i, answer in enumerate(direct_answers):
            group_key = _normalize_answer(answer) or "__unknown__"
            action_trace.append(
                {
                    "step": len(action_trace),
                    "action": "direct_reserve_v2",
                    "branch_id": f"direct_reserve_v2_{i}",
                    "group_key": group_key,
                    "is_terminal": 1,
                    "selected": int((_normalize_answer(final_answer) or "__unknown__") == group_key),
                    "source": "direct_reserve_v2",
                }
            )
            final_branch_states.append(
                {
                    "branch_id": f"direct_reserve_v2_{i}",
                    "state_id": f"direct_reserve_v2_state_{i}",
                    "predicted_answer": "" if answer is None else str(answer),
                    "group_key": group_key,
                    "is_terminal": 1,
                    "selected": int((_normalize_answer(final_answer) or "__unknown__") == group_key),
                    "source": "direct_reserve_v2",
                    "score": float(group_counts.get(group_key, 0)),
                }
            )
        metadata["action_trace"] = action_trace
        metadata["final_branch_states"] = final_branch_states

        return MethodResult(
            method=self.method_name,
            prediction=final_answer,
            is_correct=is_correct,
            actions_used=actions_used,
            expansions=expansions,
            verifications=verifications,
            avg_surviving_branches=float(frontier_result.avg_surviving_branches if frontier_result else 1.0),
            budget_exhausted=bool(actions_used >= self.max_actions),
            metadata=metadata,
        )


class DirectReserveGateRerankControllerV2ThresholdedOrdered(DirectReserveGateRerankControllerV2):
    """Diagnostic v2 variant with thresholded continuation and depth-aware ordering metadata."""

    def __init__(
        self,
        generator: BranchGenerator,
        scorer: BranchScorer,
        max_actions_per_problem: int,
        *,
        strict_controller_factory: callable,
        direct_prompt_style: str = "Let's think step by step and output the final answer within \\boxed{}.",
        direct_prompt_styles: list[str] | None = None,
        direct_reserve_attempts_override: int | None = None,
        direct_token_budget: int = 384,
        direct_token_per_action: float = 64.0,
        gate_top_support_threshold: float = 0.70,
        gate_top2_gap_threshold: float = 0.35,
        gate_entropy_threshold: float = 0.78,
        frontier_challenge_cap_small: int = 1,
        frontier_challenge_cap_large: int = 2,
        continuation_threshold: float = 0.42,
        commit_threshold: float = 0.62,
        replacement_threshold: float = 0.55,
        method_name: str = "direct_reserve_semantic_frontier_v2_thresholded_ordered",
    ) -> None:
        super().__init__(
            generator,
            scorer,
            max_actions_per_problem,
            strict_controller_factory=strict_controller_factory,
            direct_prompt_style=direct_prompt_style,
            direct_prompt_styles=direct_prompt_styles,
            direct_reserve_attempts_override=direct_reserve_attempts_override,
            direct_token_budget=direct_token_budget,
            direct_token_per_action=direct_token_per_action,
            gate_top_support_threshold=gate_top_support_threshold,
            gate_top2_gap_threshold=gate_top2_gap_threshold,
            gate_entropy_threshold=gate_entropy_threshold,
            frontier_challenge_cap_small=frontier_challenge_cap_small,
            frontier_challenge_cap_large=frontier_challenge_cap_large,
            method_name=method_name,
        )
        self.continuation_threshold = float(continuation_threshold)
        self.commit_threshold = float(commit_threshold)
        self.replacement_threshold = float(replacement_threshold)

    @staticmethod
    def _safe_float(x: Any, default: float = 0.0) -> float:
        try:
            return float(x)
        except Exception:
            return float(default)

    def _continuation_value(
        self,
        *,
        incumbent_confidence_proxy: float,
        parseable: bool,
        novelty: float,
        challenge_value: float,
        redundancy: float,
        cost: float,
    ) -> float:
        quality = 1.0 if parseable else 0.2
        uncertainty_bonus = max(0.0, min(1.0, 1.0 - incumbent_confidence_proxy))
        return float(quality + novelty + challenge_value + 0.25 * uncertainty_bonus - redundancy - cost)

    def run(self, question: str, gold_answer: str) -> MethodResult:
        reserve_attempts = self._direct_reserve_attempts()
        per_attempt_cap = max(1, int(round(self.direct_token_budget / self.direct_token_per_action)))
        direct_answers: list[str | None] = []
        direct_trace: list[dict[str, Any]] = []
        direct_actions = 0

        first_answer, first_used, first_trace = self._run_direct_attempt(
            question, gold_answer, 0, min(per_attempt_cap, self.max_actions)
        )
        direct_answers.append(first_answer)
        direct_actions += int(first_used)
        direct_trace.extend(first_trace)

        incumbent_raw = first_answer
        incumbent_canonical = _normalize_answer(incumbent_raw) or "__unknown__"
        incumbent_parseable = self._is_parseable_answer(incumbent_raw)
        incumbent_non_empty = bool(str(incumbent_raw or "").strip())
        qsig = self._question_signal(question)

        remaining_budget = max(0, self.max_actions - direct_actions)
        second_answer: str | None = None
        if reserve_attempts > 1 and remaining_budget > 0:
            second_answer, used2, tr2 = self._run_direct_attempt(
                question, gold_answer, 1, min(1, per_attempt_cap, remaining_budget)
            )
            direct_answers.append(second_answer)
            direct_actions += int(used2)
            direct_trace.extend(tr2)
            remaining_budget = max(0, self.max_actions - direct_actions)

        direct_counts: Counter[str] = Counter((_normalize_answer(a) or "__unknown__") for a in direct_answers if a is not None)
        total_direct = max(1, sum(direct_counts.values()))
        sorted_counts = sorted(direct_counts.items(), key=lambda kv: kv[1], reverse=True)
        top_count = int(sorted_counts[0][1]) if sorted_counts else 0
        second_count = int(sorted_counts[1][1]) if len(sorted_counts) > 1 else 0
        top_support = float(top_count / total_direct)
        top2_gap = float((top_count - second_count) / total_direct)
        entropy = self._entropy(dict(direct_counts))
        direct_disagreement = bool(second_answer is not None and (_normalize_answer(second_answer) or "__unknown__") != incumbent_canonical)
        incumbent_confidence_proxy = float(0.55 * top_support + 0.30 * top2_gap + 0.15 * (1.0 - entropy))
        high_uncertainty = bool(
            (not incumbent_parseable)
            or (not incumbent_non_empty)
            or direct_disagreement
            or top_support < self.gate_top_support_threshold
            or entropy > self.gate_entropy_threshold
            or qsig["operation_type"] in CASE_SPLIT_LABELS
        )
        low_uncertainty = bool(
            incumbent_parseable
            and incumbent_non_empty
            and not direct_disagreement
            and top_support >= self.gate_top_support_threshold
            and top2_gap >= self.gate_top2_gap_threshold
            and entropy <= self.gate_entropy_threshold
        )

        route_decision = "stop_with_incumbent"
        route_reason = "incumbent_parseable_low_uncertainty"
        if low_uncertainty and incumbent_confidence_proxy >= self.commit_threshold:
            route_decision = "stop_with_incumbent"
            route_reason = "commit_threshold_cleared"
        elif remaining_budget > 0 and high_uncertainty:
            route_decision = "limited_frontier_challenge"
            route_reason = "uncertainty_requires_challenge"
        elif remaining_budget > 0:
            route_decision = "one_more_direct_continuation"
            route_reason = "moderate_uncertainty_direct_probe"

        if route_decision == "one_more_direct_continuation" and remaining_budget > 0:
            ans3, used3, tr3 = self._run_direct_attempt(
                question, gold_answer, len(direct_answers), min(1, per_attempt_cap, remaining_budget)
            )
            direct_answers.append(ans3)
            direct_actions += int(used3)
            direct_trace.extend(tr3)
            remaining_budget = max(0, self.max_actions - direct_actions)

        frontier_result: MethodResult | None = None
        frontier_opened = False
        frontier_actions_used = 0
        planned_family_cap = 0
        families_matured_count = 0
        continuation_value = 0.0
        continuation_value_pre_frontier = 0.0
        ordered_family_ids: list[str] = []
        if route_decision == "limited_frontier_challenge" and remaining_budget > 0:
            if high_uncertainty and (not incumbent_parseable or entropy > self.gate_entropy_threshold):
                planned_family_cap = min(3, self.frontier_challenge_cap_large + 1)
            elif high_uncertainty:
                planned_family_cap = min(2, self.frontier_challenge_cap_large)
            else:
                planned_family_cap = 1
            pre_novelty_signal = 0.65 if high_uncertainty else 0.40
            pre_challenge_signal = max(0.0, min(1.0, 1.0 - top_support))
            pre_redundancy_signal = 1.0 - pre_challenge_signal
            pre_cost_signal = max(0.0, min(1.0, planned_family_cap / max(1, self.max_actions)))
            continuation_value_pre_frontier = self._continuation_value(
                incumbent_confidence_proxy=incumbent_confidence_proxy,
                parseable=incumbent_parseable,
                novelty=pre_novelty_signal,
                challenge_value=pre_challenge_signal,
                redundancy=pre_redundancy_signal,
                cost=pre_cost_signal,
            )
            if continuation_value_pre_frontier >= self.continuation_threshold:
                frontier_opened = True
                if continuation_value_pre_frontier < (self.continuation_threshold + 0.15):
                    planned_family_cap = min(planned_family_cap, 1)
                challenge_budget = min(remaining_budget, max(1, planned_family_cap))
                frontier = self.strict_controller_factory(challenge_budget)
                frontier_result = frontier.run(question, gold_answer)
                frontier_actions_used = int(frontier_result.actions_used)
            else:
                route_decision = "stop_with_incumbent"
                route_reason = "continuation_threshold_blocked_frontier"

        frontier_meta = dict(frontier_result.metadata or {}) if frontier_result is not None else {}
        f_dsem = (
            frontier_meta.get("diagnostic_semantic_diversity")
            if isinstance(frontier_meta.get("diagnostic_semantic_diversity"), dict)
            else {}
        ) or {}
        semantic_family_count = int(f_dsem.get("semantic_family_count") or 0)
        family_redundancy_ratio = float(f_dsem.get("family_redundancy_ratio") or 0.0)
        sem_fams = f_dsem.get("semantic_families")
        family_entries: list[tuple[str, float, float]] = []
        if isinstance(sem_fams, dict):
            for fam_id, fam_members in sem_fams.items():
                members = fam_members if isinstance(fam_members, list) else []
                novelty = 1.0 - min(1.0, len(members) / 4.0)
                fam_quality = max(
                    [self._safe_float(m.get("proxy_score"), 0.0) for m in members if isinstance(m, dict)] + [0.0]
                )
                family_entries.append((str(fam_id), novelty, fam_quality))
        family_entries.sort(key=lambda x: (x[1], x[2]), reverse=True)
        ordered_family_ids = [x[0] for x in family_entries]

        parseable_signal = incumbent_parseable
        novelty_signal = family_entries[0][1] if family_entries else 0.35
        challenge_signal = max(0.0, min(1.0, 1.0 - top_support))
        redundancy_signal = max(0.0, min(1.0, family_redundancy_ratio))
        cost_signal = max(0.0, min(1.0, frontier_actions_used / max(1, self.max_actions)))
        continuation_value = self._continuation_value(
            incumbent_confidence_proxy=incumbent_confidence_proxy,
            parseable=parseable_signal,
            novelty=novelty_signal,
            challenge_value=challenge_signal,
            redundancy=redundancy_signal,
            cost=cost_signal,
        )
        if frontier_opened:
            families_matured_count = min(len(ordered_family_ids), max(1, planned_family_cap))
            if continuation_value < self.continuation_threshold:
                families_matured_count = min(families_matured_count, 1)
        else:
            continuation_value = float(continuation_value_pre_frontier)

        incumbent_answer = incumbent_raw
        incumbent_group = incumbent_canonical
        top_challenger_answer = frontier_result.prediction if frontier_result is not None else None
        top_challenger_group = _normalize_answer(top_challenger_answer) or "__unknown__"
        candidate_answers: list[str | None] = [incumbent_answer]
        if top_challenger_answer is not None:
            candidate_answers.append(top_challenger_answer)
        group_counts: Counter[str] = Counter((_normalize_answer(a) or "__unknown__") for a in candidate_answers if a is not None)
        incumbent_support = int(group_counts.get(incumbent_group, 0))
        challenger_support = int(group_counts.get(top_challenger_group, 0))
        challenger_parseable = self._is_parseable_answer(top_challenger_answer)

        challenger_family_support = 0
        if isinstance(sem_fams, dict) and top_challenger_group != "__unknown__":
            for fam_members in sem_fams.values():
                members = fam_members if isinstance(fam_members, list) else []
                has_support = False
                for member in members:
                    if not isinstance(member, dict):
                        continue
                    feats = member.get("features", {}) if isinstance(member.get("features"), dict) else {}
                    fam_group = _normalize_answer(str(feats.get("answer_group_bucket", "") or "")) or "__unknown__"
                    if fam_group == top_challenger_group:
                        has_support = True
                        break
                if has_support:
                    challenger_family_support += 1

        cheap_verifier_prefers_challenger = bool(
            frontier_meta.get("learned_override_triggered")
            and str(frontier_meta.get("final_selected_answer", "")) == str(top_challenger_group)
        )
        replace = False
        replace_reason = "keep_incumbent_default"
        if top_challenger_answer is not None:
            if (not incumbent_parseable or not incumbent_non_empty) and challenger_parseable:
                replace = True
                replace_reason = "incumbent_unparseable_or_empty_challenger_parseable"
            elif challenger_parseable and challenger_support > incumbent_support and incumbent_confidence_proxy < self.replacement_threshold:
                replace = True
                replace_reason = "challenger_strict_support_with_parseability"
            elif challenger_parseable and challenger_family_support >= 2:
                replace = True
                replace_reason = "challenger_supported_by_two_semantic_families"
            elif cheap_verifier_prefers_challenger:
                replace = True
                replace_reason = "cheap_verifier_selected_challenger"
            else:
                replace = False
                replace_reason = "replacement_threshold_not_met"

        final_answer = top_challenger_answer if replace and top_challenger_answer is not None else incumbent_answer
        final_source = "challenger" if replace and top_challenger_answer is not None else "incumbent"
        actions_used = int(direct_actions + frontier_actions_used)
        expansions = int(direct_actions + (frontier_result.expansions if frontier_result else 0))
        verifications = int(frontier_result.verifications if frontier_result else 0)
        is_correct = self._answers_match(final_answer, gold_answer)

        metadata = {
            "method_family": "diagnostic_direct_reserve_semantic_frontier_v2_thresholded_ordered",
            "diagnostic_only": True,
            "not_canonical": True,
            "route_decision": str(route_decision),
            "route_reason": str(route_reason),
            "incumbent_parseable": int(incumbent_parseable),
            "incumbent_confidence_proxy": float(max(0.0, min(1.0, incumbent_confidence_proxy))),
            "frontier_opened": int(frontier_opened),
            "direct_actions_used": int(direct_actions),
            "frontier_actions_used": int(frontier_actions_used),
            "semantic_family_count": int(semantic_family_count),
            "family_redundancy_ratio": float(family_redundancy_ratio),
            "families_matured_count": int(families_matured_count),
            "continuation_threshold": float(self.continuation_threshold),
            "commit_threshold": float(self.commit_threshold),
            "replacement_threshold": float(self.replacement_threshold),
            "continuation_value": float(continuation_value),
            "continuation_value_pre_frontier": float(continuation_value_pre_frontier),
            "top_challenger_answer": "" if top_challenger_answer is None else str(top_challenger_answer),
            "top_challenger_support": int(challenger_support),
            "final_source": str(final_source),
            "incumbent_replacement_reason": str(replace_reason),
            "actions_used": int(actions_used),
            "question_len_words": int(qsig["question_len_words"]),
            "question_numeric_count": int(qsig["question_numeric_count"]),
            "operation_type": str(qsig["operation_type"]),
            "incumbent_non_empty": int(incumbent_non_empty),
            "incumbent_canonical": str(incumbent_canonical),
            "ordering_stage0": "direct_incumbent_first",
            "ordering_layer1": "semantic_novelty_setup_diversity",
            "ordering_layers2_3": "uncertainty_adjusted_continuation_value",
            "ordering_after_layer3": "answer_support_then_challenger_value_then_proxy",
            "ordered_family_ids": ordered_family_ids,
            "planned_family_cap": int(planned_family_cap),
            "challenge_budget": int(min(remaining_budget, max(1, planned_family_cap)) if frontier_opened else 0),
            "frontier_metadata": frontier_meta,
            "direct_action_trace": direct_trace,
        }

        action_trace = list(frontier_meta.get("action_trace", [])) if frontier_meta else []
        final_branch_states = list(frontier_meta.get("final_branch_states", [])) if frontier_meta else []
        final_group = _normalize_answer(final_answer) or "__unknown__"
        for i, answer in enumerate(direct_answers):
            group_key = _normalize_answer(answer) or "__unknown__"
            action_trace.append(
                {
                    "step": len(action_trace),
                    "action": "direct_reserve_v2_thresholded_ordered",
                    "branch_id": f"direct_reserve_v2_thresholded_ordered_{i}",
                    "group_key": group_key,
                    "is_terminal": 1,
                    "selected": int(final_group == group_key),
                    "source": "direct_reserve_v2_thresholded_ordered",
                }
            )
            final_branch_states.append(
                {
                    "branch_id": f"direct_reserve_v2_thresholded_ordered_{i}",
                    "state_id": f"direct_reserve_v2_thresholded_ordered_state_{i}",
                    "predicted_answer": "" if answer is None else str(answer),
                    "group_key": group_key,
                    "is_terminal": 1,
                    "selected": int(final_group == group_key),
                    "source": "direct_reserve_v2_thresholded_ordered",
                    "score": float(group_counts.get(group_key, 0)),
                }
            )
        metadata["action_trace"] = action_trace
        metadata["final_branch_states"] = final_branch_states

        return MethodResult(
            method=self.method_name,
            prediction=final_answer,
            is_correct=is_correct,
            actions_used=actions_used,
            expansions=expansions,
            verifications=verifications,
            avg_surviving_branches=float(frontier_result.avg_surviving_branches if frontier_result else 1.0),
            budget_exhausted=bool(actions_used >= self.max_actions),
            metadata=metadata,
        )


class DirectReserveLearnedOverrideController(BaseController):
    """Diagnostic wrapper that applies learned selection on top of base plus-diverse output.

    Invariant: when override is unavailable or not triggered, final answer MUST equal base answer.
    """

    def __init__(
        self,
        *,
        base_controller: DirectReserveGateRerankController,
        method_name: str = "direct_reserve_strong_plus_diverse_learned_override_v1",
        margin_threshold: float = 0.25,
        selector_fn: Callable[[list[dict[str, Any]]], tuple[int | None, float, dict[str, float]]] | None = None,
        required_feature_keys: list[str] | None = None,
    ) -> None:
        super().__init__(base_controller.generator, base_controller.scorer, base_controller.max_actions)
        self.base_controller = base_controller
        self.method_name = method_name
        self.margin_threshold = float(margin_threshold)
        self.selector_fn = selector_fn
        self.required_feature_keys = list(required_feature_keys or ["answer_group_support", "branch_depth", "score"])

    @staticmethod
    def _candidate_rows_from_metadata(metadata: dict[str, Any]) -> list[dict[str, Any]]:
        states = list(metadata.get("final_branch_states", []))
        counts: Counter[str] = Counter(
            str(s.get("group_key", "")).strip().lower() or "__unknown__" for s in states if str(s.get("predicted_answer", "")).strip()
        )
        rows: list[dict[str, Any]] = []
        for idx, state in enumerate(states):
            pred = str(state.get("predicted_answer", "")).strip()
            if not pred:
                continue
            group_key = str(state.get("group_key", "")).strip().lower() or _normalize_answer(pred) or "__unknown__"
            rows.append(
                {
                    "candidate_index": idx,
                    "predicted_answer": pred,
                    "group_key": group_key,
                    "answer_group_support": float(counts.get(group_key, 0)),
                    "branch_depth": float(state.get("branch_depth", 0) or 0),
                    "score": float(state.get("score", 0.0) or 0.0),
                    "selected": int(state.get("selected", 0) or 0),
                    "source": str(state.get("source", "")),
                }
            )
        return rows

    def _default_selector(self, rows: list[dict[str, Any]]) -> tuple[int | None, float, dict[str, float]]:
        if not rows:
            return None, 0.0, {}
        scores: dict[str, float] = {}
        for r in rows:
            key = str(r["candidate_index"])
            scores[key] = 1.0 * float(r["answer_group_support"]) + 0.20 * float(r["score"]) - 0.02 * float(r["branch_depth"])
        ordered = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        best_idx = int(ordered[0][0]) if ordered else None
        margin = float(ordered[0][1] - ordered[1][1]) if len(ordered) > 1 else float(ordered[0][1] if ordered else 0.0)
        return best_idx, margin, scores

    def run(self, question: str, gold_answer: str) -> MethodResult:
        base_result = self.base_controller.run(question, gold_answer)
        base_metadata = dict(base_result.metadata or {})
        base_answer = base_result.prediction

        rows = self._candidate_rows_from_metadata(base_metadata)
        missing_features: set[str] = set()
        for row in rows:
            for key in self.required_feature_keys:
                if key not in row or row.get(key) is None:
                    missing_features.add(key)

        learned_available = bool(self.selector_fn is not None)
        selector_reason = "selector_unavailable"
        learned_idx: int | None = None
        learned_margin = 0.0
        learned_scores: dict[str, float] = {}
        learned_selected_answer = base_answer
        triggered = False

        if missing_features:
            selector_reason = "missing_required_features"
        elif not rows:
            selector_reason = "no_candidates"
        elif learned_available:
            learned_idx, learned_margin, learned_scores = self.selector_fn(rows)  # type: ignore[misc]
            if learned_idx is not None and 0 <= int(learned_idx) < len(rows):
                learned_selected_answer = str(rows[int(learned_idx)].get("predicted_answer", "")) or base_answer
            triggerable = bool(learned_selected_answer is not None and learned_selected_answer != base_answer)
            if triggerable and float(learned_margin) >= float(self.margin_threshold):
                triggered = True
                selector_reason = "margin_override"
            else:
                selector_reason = "below_margin_or_same_answer"
        else:
            selector_reason = "selector_unavailable"

        final_answer = learned_selected_answer if triggered else base_answer
        metadata = dict(base_metadata)
        metadata.update(
            {
                "learned_override_available": bool(learned_available),
                "learned_override_triggered": bool(triggered),
                "learned_override_reason": str(selector_reason),
                "learned_override_margin": float(learned_margin),
                "learned_override_threshold": float(self.margin_threshold),
                "learned_override_missing_features": sorted(missing_features),
                "base_selected_answer": base_answer,
                "learned_selected_answer": learned_selected_answer,
                "final_selected_answer": final_answer,
                "learned_selector_scores": learned_scores,
                "learned_selector_candidate_count": int(len(rows)),
            }
        )
        return MethodResult(
            method=self.method_name,
            prediction=final_answer,
            is_correct=self._answers_match(final_answer, gold_answer),
            actions_used=int(base_result.actions_used),
            expansions=int(base_result.expansions),
            verifications=int(base_result.verifications),
            avg_surviving_branches=float(base_result.avg_surviving_branches),
            budget_exhausted=bool(base_result.budget_exhausted),
            metadata=metadata,
        )


class DirectReserveFrontierGateController(DirectReserveGateRerankController):
    """Diagnostic controller that protects a direct reserve from weak frontier overrides."""

    def __init__(
        self,
        generator: BranchGenerator,
        scorer: BranchScorer,
        max_actions_per_problem: int,
        *,
        strict_controller_factory: callable,
        direct_prompt_style: str = "Let's think step by step and output the final answer within \\boxed{}.",
        direct_prompt_styles: list[str] | None = None,
        direct_reserve_attempts_override: int | None = None,
        direct_token_budget: int = 512,
        direct_token_per_action: float = 64.0,
        gate_top_support_threshold: float = 0.75,
        gate_top2_gap_threshold: float = 0.50,
        gate_entropy_threshold: float = 0.55,
        frontier_override_min_support_margin: int = 1,
        frontier_override_min_maturity: int = 2,
        method_name: str = "direct_reserve_frontier_gate_v1",
    ) -> None:
        super().__init__(
            generator,
            scorer,
            max_actions_per_problem,
            strict_controller_factory=strict_controller_factory,
            direct_prompt_style=direct_prompt_style,
            direct_prompt_styles=direct_prompt_styles,
            direct_reserve_attempts_override=direct_reserve_attempts_override,
            direct_token_budget=direct_token_budget,
            direct_token_per_action=direct_token_per_action,
            gate_top_support_threshold=gate_top_support_threshold,
            gate_top2_gap_threshold=gate_top2_gap_threshold,
            gate_entropy_threshold=gate_entropy_threshold,
            method_name=method_name,
        )
        self.frontier_override_min_support_margin = max(1, int(frontier_override_min_support_margin))
        self.frontier_override_min_maturity = max(1, int(frontier_override_min_maturity))
        self.method_name = method_name

    def run(self, question: str, gold_answer: str) -> MethodResult:
        reserve_attempts = self._direct_reserve_attempts()
        per_attempt_cap = max(1, int(round(self.direct_token_budget / self.direct_token_per_action)))
        direct_answers: list[str | None] = []
        direct_actions = 0
        direct_trace: list[dict[str, Any]] = []

        for i in range(reserve_attempts):
            if direct_actions >= self.max_actions:
                break
            ans, used, trace_rows = self._run_direct_attempt(
                question, gold_answer, i, min(per_attempt_cap, self.max_actions - direct_actions)
            )
            direct_answers.append(ans)
            direct_actions += int(used)
            direct_trace.extend(trace_rows)

        direct_counts: Counter[str] = Counter((_normalize_answer(a) or "__unknown__") for a in direct_answers if a is not None)
        sorted_counts = sorted(direct_counts.items(), key=lambda kv: kv[1], reverse=True)
        incumbent_group = sorted_counts[0][0] if sorted_counts else "__unknown__"
        incumbent_support = int(sorted_counts[0][1]) if sorted_counts else 0
        direct_total = max(1, sum(direct_counts.values()))
        second_support = int(sorted_counts[1][1]) if len(sorted_counts) > 1 else 0
        direct_top_support = float(incumbent_support / direct_total)
        direct_gap = float((incumbent_support - second_support) / direct_total)
        direct_entropy = self._entropy(dict(direct_counts))
        incumbent_answer = next(
            (a for a in direct_answers if (_normalize_answer(a) or "__unknown__") == incumbent_group),
            direct_answers[0] if direct_answers else None,
        )

        remaining_budget = max(0, self.max_actions - direct_actions)
        incumbent_uncertain = bool(
            direct_top_support < self.gate_top_support_threshold
            or direct_gap < self.gate_top2_gap_threshold
            or direct_entropy > self.gate_entropy_threshold
        )
        should_expand_frontier = bool(remaining_budget > 0 and incumbent_uncertain)

        frontier_result: MethodResult | None = None
        if should_expand_frontier:
            frontier = self.strict_controller_factory(remaining_budget)
            if bool(getattr(self, "emit_full_traces", False)):
                setattr(frontier, "emit_full_traces", True)
            frontier_result = frontier.run(question, gold_answer)

        frontier_answer = frontier_result.prediction if frontier_result else None
        frontier_group = (_normalize_answer(frontier_answer) if frontier_answer is not None else "__unknown__") or "__unknown__"
        direct_frontier_agree = bool(frontier_answer is not None and frontier_group == incumbent_group)

        frontier_support_counts: dict[str, int] = {}
        if frontier_result and isinstance(frontier_result.metadata, dict):
            raw = frontier_result.metadata.get("answer_group_support_counts", {})
            if isinstance(raw, dict):
                for k, v in raw.items():
                    try:
                        frontier_support_counts[str(k)] = int(v)
                    except Exception:
                        continue
        frontier_support = int(frontier_support_counts.get(frontier_group, 0))
        frontier_maturity = int((frontier_result.expansions if frontier_result else 0) + (frontier_result.verifications if frontier_result else 0))
        override_margin = float(frontier_support - incumbent_support)
        frontier_meta = dict(frontier_result.metadata or {}) if frontier_result else {}
        frontier_families = frontier_meta.get("answer_group_strategy_family_counts", {})
        if isinstance(frontier_families, dict):
            frontier_candidate_family_count = len(dict(frontier_families.get(frontier_group, {}) or {}))
        else:
            frontier_candidate_family_count = 0
        frontier_final_states = list(frontier_meta.get("final_branch_states", [])) if isinstance(frontier_meta.get("final_branch_states", []), list) else []
        frontier_group_states = [
            s
            for s in frontier_final_states
            if (_normalize_answer(str(s.get("predicted_answer", ""))) or "__unknown__") == frontier_group
        ]
        frontier_depths = [int(s.get("branch_depth", 0) or 0) for s in frontier_group_states]
        frontier_depth_max = max(frontier_depths) if frontier_depths else None
        frontier_depth_mean = (sum(frontier_depths) / max(1, len(frontier_depths))) if frontier_depths else None

        # Heuristic challenger score (I_t): only positive for mature, non-incumbent challengers.
        incumbent_challenge_score = 0.0
        if frontier_result and frontier_group != incumbent_group:
            incumbent_challenge_score = 1.0 if (frontier_support >= 2 and frontier_maturity >= self.frontier_override_min_maturity) else -1.0

        override_reason = "reserve_default"
        frontier_override_triggered = False
        if frontier_result is None:
            override_reason = "frontier_not_run_or_budget_exhausted"
        elif direct_frontier_agree:
            override_reason = "direct_frontier_agree"
        elif frontier_support <= 1:
            override_reason = "single_weak_frontier_branch"
        elif frontier_maturity < self.frontier_override_min_maturity:
            override_reason = "frontier_not_mature"
        elif override_margin < float(self.frontier_override_min_support_margin):
            override_reason = "insufficient_support_margin"
        else:
            frontier_override_triggered = True
            override_reason = "frontier_support_margin_override"

        final_answer = frontier_answer if frontier_override_triggered else incumbent_answer
        reserve_used = bool(not frontier_override_triggered)

        actions_used = int(direct_actions + (frontier_result.actions_used if frontier_result else 0))
        expansions = int(direct_actions + (frontier_result.expansions if frontier_result else 0))
        verifications = int(frontier_result.verifications if frontier_result else 0)
        support_margin = float(frontier_support - incumbent_support)
        maturity_margin = float(frontier_maturity - len(direct_answers))
        action_trace = list(frontier_meta.get("action_trace", [])) if isinstance(frontier_meta.get("action_trace", []), list) else []
        final_branch_states = list(frontier_final_states)
        for i, answer in enumerate(direct_answers):
            group_key = _normalize_answer(answer) or "__unknown__"
            action_trace.append(
                {
                    "step": len(action_trace),
                    "action": "direct_reserve",
                    "branch_id": f"direct_reserve_{i}",
                    "group_key": group_key,
                    "is_terminal": 1,
                    "selected": int(group_key == (_normalize_answer(final_answer) or "__unknown__")),
                    "source": "direct_reserve",
                }
            )
            final_branch_states.append(
                {
                    "branch_id": f"direct_reserve_{i}",
                    "parent_branch_id": "",
                    "branch_depth": 1,
                    "score": float(direct_counts.get(group_key, 0)),
                    "predicted_answer": "" if answer is None else str(answer),
                    "is_done": bool(answer is not None),
                    "is_pruned": False,
                    "steps": [],
                    "trace_events": [r for r in direct_trace if str(r.get("branch_id")) == f"direct_reserve_{i}"],
                    "strategy_family": "direct_reserve",
                    "source": "direct_reserve",
                    "selected": int(group_key == (_normalize_answer(final_answer) or "__unknown__")),
                }
            )
        combined_group_counts = Counter(dict(frontier_support_counts))
        for group, count in direct_counts.items():
            combined_group_counts[group] += int(count)

        metadata = {
            "method_family": "diagnostic_direct_reserve_frontier_gate",
            "diagnostic_only": True,
            "not_canonical": True,
            "direct_reserve_answer": incumbent_answer,
            "direct_reserve_source_method": "direct_reserve_attempts",
            "direct_reserve_attempts": direct_trace,
            "direct_reserve_num_attempts": int(len(direct_answers)),
            "direct_reserve_attempts_planned": int(reserve_attempts),
            "direct_reserve_attempts_executed": int(len(direct_answers)),
            "direct_reserve_agreement_count": int(incumbent_support),
            "direct_reserve_confidence_proxy": float(direct_top_support),
            "direct_reserve_parse_success": bool(incumbent_answer is not None and str(incumbent_answer).strip()),
            "direct_reserve_metadata": {
                "direct_answer_group_counts": dict(direct_counts),
                "direct_top_support": float(direct_top_support),
                "direct_top2_support_gap": float(direct_gap),
                "direct_answer_entropy": float(direct_entropy),
            },
            "frontier_candidate_answer": frontier_answer,
            "frontier_candidate_support": int(frontier_support),
            "frontier_candidate_maturity": int(frontier_maturity),
            "frontier_candidate_family_count": int(frontier_candidate_family_count),
            "frontier_candidate_depth_max": frontier_depth_max,
            "frontier_candidate_depth_mean": frontier_depth_mean,
            "frontier_candidate_metadata": dict(frontier_meta),
            "final_answer": final_answer,
            "reserve_used": bool(reserve_used),
            "frontier_override_triggered": bool(frontier_override_triggered),
            "override_margin": float(override_margin),
            "override_reason": str(override_reason),
            "direct_frontier_agree": bool(direct_frontier_agree),
            "incumbent_support": int(incumbent_support),
            "frontier_support": int(frontier_support),
            "support_margin": float(support_margin),
            "maturity_margin": float(maturity_margin),
            "override_thresholds": {
                "frontier_override_min_support_margin": int(self.frontier_override_min_support_margin),
                "frontier_override_min_maturity": int(self.frontier_override_min_maturity),
                "gate_top_support_threshold": float(self.gate_top_support_threshold),
                "gate_top2_gap_threshold": float(self.gate_top2_gap_threshold),
                "gate_entropy_threshold": float(self.gate_entropy_threshold),
            },
            "guard_decision_inputs": {
                "incumbent_group": str(incumbent_group),
                "frontier_group": str(frontier_group),
                "incumbent_support": int(incumbent_support),
                "frontier_support": int(frontier_support),
                "frontier_maturity": int(frontier_maturity),
                "support_margin": float(support_margin),
                "maturity_margin": float(maturity_margin),
                "incumbent_uncertain": bool(incumbent_uncertain),
                "should_expand_frontier": bool(should_expand_frontier),
            },
            "incumbent_challenge_score": float(incumbent_challenge_score),
            "remaining_budget_before_frontier": int(remaining_budget),
            "frontier_executed": bool(frontier_result is not None),
            "direct_answer_group_counts": dict(direct_counts),
            "frontier_answer_group_counts": dict(frontier_support_counts),
            "answer_group_support_counts": dict(combined_group_counts),
            "answer_group_strategy_family_counts": frontier_meta.get("answer_group_strategy_family_counts", {}),
            "answer_group_best_branch_scores": frontier_meta.get("answer_group_best_branch_scores", {}),
            "frontier_metadata": dict(frontier_meta),
            "action_trace": action_trace,
            "final_branch_states": final_branch_states if bool(getattr(self, "emit_full_traces", False)) else [],
        }
        return MethodResult(
            method=self.method_name,
            prediction=final_answer,
            is_correct=self._answers_match(final_answer, gold_answer),
            actions_used=actions_used,
            expansions=expansions,
            verifications=verifications,
            avg_surviving_branches=float(frontier_result.avg_surviving_branches if frontier_result else 1.0),
            budget_exhausted=bool(actions_used >= self.max_actions),
            metadata=metadata,
        )


class DirectReserveFrontierGateV2Controller(DirectReserveFrontierGateController):
    """Diagnostic v2: block overrides when frontier already contains the incumbent."""

    def __init__(self, *args: Any, method_name: str = "direct_reserve_frontier_gate_v2", **kwargs: Any) -> None:
        super().__init__(*args, method_name=method_name, **kwargs)

    def run(self, question: str, gold_answer: str) -> MethodResult:
        base = super().run(question, gold_answer)
        metadata = dict(base.metadata or {})
        incumbent_answer = metadata.get("direct_reserve_answer")
        incumbent_group = _normalize_answer(str(incumbent_answer)) if incumbent_answer is not None else "__unknown__"
        support_source = metadata.get("frontier_answer_group_counts")
        if not isinstance(support_source, dict) or not support_source:
            support_source = metadata.get("answer_group_support_counts", {})
        incumbent_seen = False
        if isinstance(support_source, dict):
            incumbent_seen = int(support_source.get(incumbent_group, 0) or 0) > 0

        guard_applied = bool(metadata.get("frontier_override_triggered", False) and incumbent_seen)
        metadata["incumbent_seen_in_frontier_support"] = bool(incumbent_seen)
        metadata["v2_incumbent_support_guard_applied"] = bool(guard_applied)
        metadata["v2_override_block_reason"] = (
            "incumbent_seen_in_frontier_support" if guard_applied else "not_blocked"
        )
        metadata["v2_diagnostic_only"] = True
        metadata["not_canonical"] = True

        if not guard_applied:
            metadata["method_family"] = "diagnostic_direct_reserve_frontier_gate_v2"
            return MethodResult(
                method=self.method_name,
                prediction=base.prediction,
                is_correct=bool(base.is_correct),
                actions_used=base.actions_used,
                expansions=base.expansions,
                verifications=base.verifications,
                avg_surviving_branches=base.avg_surviving_branches,
                budget_exhausted=base.budget_exhausted,
                metadata=metadata,
            )

        final_answer = metadata.get("direct_reserve_answer")
        metadata["v1_frontier_override_triggered"] = True
        metadata["v1_final_answer_before_v2_guard"] = metadata.get("final_answer", base.prediction)
        metadata["frontier_override_triggered"] = False
        metadata["reserve_used"] = True
        metadata["override_reason"] = "v2_blocked_incumbent_seen_in_frontier_support"
        metadata["final_answer"] = final_answer
        metadata["method_family"] = "diagnostic_direct_reserve_frontier_gate_v2"
        return MethodResult(
            method=self.method_name,
            prediction=final_answer,
            is_correct=self._answers_match(final_answer, gold_answer),
            actions_used=base.actions_used,
            expansions=base.expansions,
            verifications=base.verifications,
            avg_surviving_branches=base.avg_surviving_branches,
            budget_exhausted=base.budget_exhausted,
            metadata=metadata,
        )


class DirectReserveFrontierGateV2SelectionFixV1Controller(DirectReserveFrontierGateV2Controller):
    """Diagnostic selection-fix wrapper for DR-v2 (no proposal changes)."""

    def __init__(self, *args: Any, method_name: str = "direct_reserve_semantic_frontier_v2_selection_fix_v1", **kwargs: Any) -> None:
        super().__init__(*args, method_name=method_name, **kwargs)

    def run(self, question: str, gold_answer: str) -> MethodResult:
        base = super().run(question, gold_answer)
        metadata = dict(base.metadata or {})
        support = metadata.get("answer_group_support_counts", {})
        direct_answer = metadata.get("direct_reserve_answer")
        frontier_answer = metadata.get("frontier_candidate_answer")
        direct_group = _normalize_answer(str(direct_answer)) if direct_answer is not None else "__unknown__"
        frontier_group = _normalize_answer(str(frontier_answer)) if frontier_answer is not None else "__unknown__"
        direct_support = int((support.get(direct_group, 0) if isinstance(support, dict) else 0) or 0)
        frontier_support = int((support.get(frontier_group, 0) if isinstance(support, dict) else 0) or 0)
        switch = bool(frontier_answer and frontier_group != "__unknown__" and frontier_group != direct_group and frontier_support >= direct_support + 1)
        final_answer = frontier_answer if switch else base.prediction
        metadata["selection_fix_considered"] = True
        metadata["selection_fix_applied"] = bool(switch)
        metadata["selection_fix_reason"] = (
            "frontier_group_support_strictly_higher_than_direct" if switch else "kept_base_selection"
        )
        metadata["selection_fix_direct_group"] = direct_group
        metadata["selection_fix_frontier_group"] = frontier_group
        metadata["selection_fix_direct_support"] = direct_support
        metadata["selection_fix_frontier_support"] = frontier_support
        metadata["method_family"] = "diagnostic_direct_reserve_frontier_gate_v2_selection_fix_v1"
        metadata["not_canonical"] = True
        return MethodResult(
            method=self.method_name,
            prediction=final_answer,
            is_correct=self._answers_match(final_answer, gold_answer),
            actions_used=base.actions_used,
            expansions=base.expansions,
            verifications=base.verifications,
            avg_surviving_branches=base.avg_surviving_branches,
            budget_exhausted=base.budget_exhausted,
            metadata=metadata,
        )


class DirectReserveFrontierGateV2OutcomeVerifierRerankV1Controller(DirectReserveFrontierGateV2Controller):
    """Live-runnable DR-v2 selector using answer-grouped outcome-verifier reranking."""

    def __init__(
        self,
        *args: Any,
        method_name: str = "direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1",
        verifier_backend: str = "mock",
        verifier_model: str = "command-r-plus-08-2024",
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, method_name=method_name, **kwargs)
        self.verifier_backend = str(verifier_backend).strip().lower()
        self.verifier_model = str(verifier_model).strip() or "command-r-plus-08-2024"

    def _build_verifier(self) -> Any:
        backend = self.verifier_backend
        if backend == "cohere":
            return CohereOutcomeVerifier(model=self.verifier_model)
        return DeterministicMockOutcomeVerifier()

    def run(self, question: str, gold_answer: str) -> MethodResult:
        base = super().run(question, gold_answer)
        metadata = dict(base.metadata or {})
        base_prediction = base.prediction
        candidates = build_candidates_from_dr_v2_metadata(question, metadata)
        if not candidates:
            metadata["ov_rerank_applied"] = False
            metadata["candidate_count"] = 0
            metadata["answer_group_count"] = 0
            metadata["selected_candidate_id"] = ""
            metadata["selected_normalized_answer"] = _normalize_answer(base_prediction) or "__unknown__"
            metadata["ov_rerank_selected_answer"] = base_prediction
            metadata["selected_group_score"] = 0.0
            metadata["verifier_backend"] = self.verifier_backend
            metadata["verifier_calls"] = 0
            metadata["single_candidate_fallback"] = True
            metadata["fallback_reason"] = "no_candidates_extracted"
            metadata["ov_rerank_original_dr_v2_selected_answer"] = base_prediction
            metadata["method_family"] = "direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1"
            metadata["diagnostic_only"] = False
            metadata["not_canonical"] = True
            return MethodResult(
                method=self.method_name,
                prediction=base_prediction,
                is_correct=self._answers_match(base_prediction, gold_answer),
                actions_used=base.actions_used,
                expansions=base.expansions,
                verifications=base.verifications,
                avg_surviving_branches=base.avg_surviving_branches,
                budget_exhausted=base.budget_exhausted,
                metadata=metadata,
            )

        # Fallback only when there is no real reranking surface.
        if len(candidates) <= 1:
            metadata["ov_rerank_applied"] = False
            metadata["candidate_count"] = int(len(candidates))
            metadata["answer_group_count"] = int(len({_normalize_answer(c.final_answer) or "__unknown__" for c in candidates}))
            metadata["selected_candidate_id"] = candidates[0].candidate_id
            metadata["selected_normalized_answer"] = _normalize_answer(candidates[0].final_answer) or "__unknown__"
            metadata["ov_rerank_selected_answer"] = base_prediction
            metadata["selected_group_score"] = 0.0
            metadata["verifier_backend"] = self.verifier_backend
            metadata["verifier_calls"] = 0
            metadata["single_candidate_fallback"] = True
            metadata["fallback_reason"] = "single_candidate_only"
            metadata["ov_rerank_original_dr_v2_selected_answer"] = base_prediction
            metadata["method_family"] = "direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1"
            metadata["diagnostic_only"] = False
            metadata["not_canonical"] = True
            return MethodResult(
                method=self.method_name,
                prediction=base_prediction,
                is_correct=self._answers_match(base_prediction, gold_answer),
                actions_used=base.actions_used,
                expansions=base.expansions,
                verifications=base.verifications,
                avg_surviving_branches=base.avg_surviving_branches,
                budget_exhausted=base.budget_exhausted,
                metadata=metadata,
            )

        verifier = self._build_verifier()
        decision = select_answer_group_with_outcome_verifier(candidates, verifier)
        selected_norm = str(decision.selected_answer or "").strip().lower()
        selected = next((c for c in candidates if c.candidate_id == decision.selected_candidate_id), None)
        if selected is None:
            selected = next(
                (c for c in candidates if (_normalize_answer(c.final_answer) or "__unknown__") == (_normalize_answer(selected_norm) or "__unknown__")),
                candidates[0],
            )
        final_answer = selected.final_answer if selected is not None else base_prediction

        group_payload = [
            {
                "normalized_answer": g.normalized_answer,
                "group_score": float(g.group_score),
                "original_group_size": int(g.original_group_size),
                "capped_group_size": int(g.capped_group_size),
                "representative_candidate_id": g.representative_candidate_id,
            }
            for g in decision.group_scores
        ]
        verifier_payload = {
            cid: {
                "prob_correct": float(v.prob_correct),
                "trace_final_consistent": bool(v.trace_final_consistent),
                "answer_equivalent_if_normalized": v.answer_equivalent_if_normalized,
                "major_error": bool(v.major_error),
                "short_reason": str(v.short_reason),
            }
            for cid, v in decision.verifier_results.items()
        }
        candidate_payload = {
            c.candidate_id: {
                "candidate_score": float(decision.candidate_scores.get(c.candidate_id, 0.0)),
                "source_id": c.source_id or c.candidate_id,
                "normalized_answer": _normalize_answer(c.final_answer) or "__unknown__",
            }
            for c in candidates
        }
        gold_norm = _normalize_answer(gold_answer) or "__unknown__"
        candidate_norms = {_normalize_answer(c.final_answer) or "__unknown__" for c in candidates}
        base_norm = _normalize_answer(base_prediction) or "__unknown__"
        final_norm = _normalize_answer(final_answer) or "__unknown__"
        metadata["ov_rerank_applied"] = True
        metadata["candidate_count"] = int(len(candidates))
        metadata["answer_group_count"] = int(len({(_normalize_answer(c.final_answer) or "__unknown__") for c in candidates}))
        metadata["selected_candidate_id"] = selected.candidate_id if selected is not None else ""
        metadata["selected_normalized_answer"] = final_norm
        metadata["ov_rerank_selected_answer"] = final_answer
        metadata["selected_group_score"] = float(decision.selected_group_score)
        metadata["verifier_backend"] = self.verifier_backend
        metadata["verifier_calls"] = int(decision.verifier_calls)
        metadata["single_candidate_fallback"] = False
        metadata["fallback_reason"] = ""
        metadata["ov_rerank_group_scores"] = group_payload
        metadata["ov_rerank_candidate_scores"] = candidate_payload
        metadata["ov_rerank_verifier_results"] = verifier_payload
        metadata["ov_rerank_original_dr_v2_selected_answer"] = base_prediction
        metadata["ov_rerank_gold_present_in_candidates"] = int(gold_norm in candidate_norms)
        metadata["ov_rerank_recovered_present_not_selected"] = int(
            (gold_norm in candidate_norms) and (base_norm != gold_norm) and (final_norm == gold_norm)
        )
        metadata["method_family"] = "direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1"
        metadata["diagnostic_only"] = False
        metadata["not_canonical"] = True
        return MethodResult(
            method=self.method_name,
            prediction=final_answer,
            is_correct=self._answers_match(final_answer, gold_answer),
            actions_used=base.actions_used,
            expansions=base.expansions,
            verifications=base.verifications,
            avg_surviving_branches=base.avg_surviving_branches,
            budget_exhausted=base.budget_exhausted,
            metadata=metadata,
        )


class DirectReserveFrontierGateV2PRMStepVerifierRerankV1Controller(DirectReserveFrontierGateV2Controller):
    """Live-runnable DR-v2 selector using PRM-style step-level verification and answer-group aggregation."""

    def __init__(
        self,
        *args: Any,
        method_name: str = "direct_reserve_semantic_frontier_v2_prm_step_verifier_rerank_v1",
        verifier_backend: str = "mock",
        verifier_model: str = "command-r-plus-08-2024",
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, method_name=method_name, **kwargs)
        self.verifier_backend = str(verifier_backend).strip().lower()
        self.verifier_model = str(verifier_model).strip() or "command-r-plus-08-2024"

    def _build_step_verifier(self) -> Any:
        if self.verifier_backend == "cohere":
            return CohereStepVerifier(model=self.verifier_model)
        return DeterministicMockStepVerifier()

    def run(self, question: str, gold_answer: str) -> MethodResult:
        base = super().run(question, gold_answer)
        metadata = dict(base.metadata or {})
        base_prediction = base.prediction
        candidates = build_prm_candidates_from_dr_v2_metadata(question, metadata)

        def _emit_fallback(
            *,
            applied: bool,
            reason: str,
            cand_count: int,
            group_count: int,
        ) -> MethodResult:
            metadata["prm_rerank_applied"] = applied
            metadata["candidate_count"] = int(cand_count)
            metadata["answer_group_count"] = int(group_count)
            metadata["selected_candidate_id"] = candidates[0].candidate_id if candidates else ""
            metadata["selected_normalized_answer"] = (
                _normalize_answer(candidates[0].final_answer) if candidates else _normalize_answer(base_prediction)
            ) or "__unknown__"
            metadata["prm_selected_answer"] = base_prediction
            metadata["selected_group_score"] = 0.0
            metadata["prm_step_verifier_backend"] = self.verifier_backend
            metadata["prm_step_verifier_model"] = self.verifier_model
            metadata["prm_step_verifier_calls"] = 0
            metadata["prm_step_scores"] = {}
            metadata["prm_trace_scores"] = {}
            metadata["prm_group_scores"] = []
            metadata["prm_original_dr_v2_selected_answer"] = base_prediction
            metadata["single_candidate_fallback"] = True
            metadata["fallback_reason"] = reason
            metadata["prm_gold_present_in_candidates"] = int(
                (_normalize_answer(gold_answer) or "__unknown__")
                in ({_normalize_answer(c.final_answer) or "__unknown__" for c in candidates} if candidates else set())
            )
            metadata["prm_recovered_present_not_selected"] = 0
            metadata["method_family"] = "direct_reserve_semantic_frontier_v2_prm_step_verifier_rerank_v1"
            metadata["diagnostic_only"] = False
            metadata["not_canonical"] = True
            return MethodResult(
                method=self.method_name,
                prediction=base_prediction,
                is_correct=self._answers_match(base_prediction, gold_answer),
                actions_used=base.actions_used,
                expansions=base.expansions,
                verifications=base.verifications,
                avg_surviving_branches=base.avg_surviving_branches,
                budget_exhausted=base.budget_exhausted,
                metadata=metadata,
            )

        if not candidates:
            return _emit_fallback(applied=False, reason="no_candidates_extracted", cand_count=0, group_count=0)

        if len(candidates) <= 1:
            return _emit_fallback(
                applied=False,
                reason="single_candidate_only",
                cand_count=len(candidates),
                group_count=len({_normalize_answer(c.final_answer) or "__unknown__" for c in candidates}),
            )

        verifier = self._build_step_verifier()
        decision = select_answer_group_with_prm_step_verifier(
            candidates,
            verifier,
            verifier_backend=self.verifier_backend,
            verifier_model=self.verifier_model,
        )
        selected = next((c for c in candidates if c.candidate_id == decision.selected_candidate_id), None)
        if selected is None:
            selected = next(
                (
                    c
                    for c in candidates
                    if (_normalize_answer(c.final_answer) or "__unknown__")
                    == (_normalize_answer(decision.selected_answer) or "__unknown__")
                ),
                candidates[0],
            )
        final_answer = selected.final_answer if selected is not None else base_prediction

        gold_norm = _normalize_answer(gold_answer) or "__unknown__"
        candidate_norms = {_normalize_answer(c.final_answer) or "__unknown__" for c in candidates}
        base_norm = _normalize_answer(base_prediction) or "__unknown__"
        final_norm = _normalize_answer(final_answer) or "__unknown__"

        group_payload = [
            {
                "normalized_answer": g.normalized_answer,
                "group_score": float(g.group_score),
                "original_group_size": int(g.original_group_size),
                "representative_candidate_id": g.representative_candidate_id,
            }
            for g in decision.group_scores
        ]

        metadata["prm_rerank_applied"] = True
        metadata["candidate_count"] = int(len(candidates))
        metadata["answer_group_count"] = int(len({(_normalize_answer(c.final_answer) or "__unknown__") for c in candidates}))
        metadata["selected_candidate_id"] = selected.candidate_id if selected is not None else ""
        metadata["selected_normalized_answer"] = final_norm
        metadata["prm_selected_answer"] = final_answer
        metadata["selected_group_score"] = float(decision.selected_group_score)
        metadata["prm_step_verifier_backend"] = decision.verifier_backend
        metadata["prm_step_verifier_model"] = decision.verifier_model
        metadata["prm_step_verifier_calls"] = int(decision.verifier_calls)
        metadata["prm_step_scores"] = decision.step_scores
        metadata["prm_trace_scores"] = {k: float(v) for k, v in decision.trace_scores.items()}
        metadata["prm_group_scores"] = group_payload
        metadata["prm_original_dr_v2_selected_answer"] = base_prediction
        metadata["prm_gold_present_in_candidates"] = int(gold_norm in candidate_norms)
        metadata["prm_recovered_present_not_selected"] = int(
            (gold_norm in candidate_norms) and (base_norm != gold_norm) and (final_norm == gold_norm)
        )
        metadata["single_candidate_fallback"] = False
        metadata["fallback_reason"] = ""
        metadata["method_family"] = "direct_reserve_semantic_frontier_v2_prm_step_verifier_rerank_v1"
        metadata["diagnostic_only"] = False
        metadata["not_canonical"] = True
        return MethodResult(
            method=self.method_name,
            prediction=final_answer,
            is_correct=self._answers_match(final_answer, gold_answer),
            actions_used=base.actions_used,
            expansions=base.expansions,
            verifications=base.verifications,
            avg_surviving_branches=base.avg_surviving_branches,
            budget_exhausted=base.budget_exhausted,
            metadata=metadata,
        )


class NearDirectReserveFrontierGateController(BaseController):
    """Diagnostic controller that protects an L1-style near-direct incumbent."""

    def __init__(
        self,
        generator: BranchGenerator,
        scorer: BranchScorer,
        max_actions_per_problem: int,
        *,
        strict_controller_factory: callable,
        protected_token_budget: int = 512,
        protected_token_per_action: float = 64.0,
        protected_prompt_style: str = "Let's think step by step and output the final answer within \\boxed{}.",
        frontier_override_min_support_margin: int = 1,
        frontier_override_min_maturity: int = 2,
        require_frontier_multi_evidence: bool = True,
        method_name: str = "near_direct_reserve_frontier_gate_v1",
    ) -> None:
        super().__init__(generator, scorer, max_actions_per_problem)
        self.strict_controller_factory = strict_controller_factory
        self.protected_token_budget = max(1, int(protected_token_budget))
        self.protected_token_per_action = max(1.0, float(protected_token_per_action))
        self.protected_prompt_style = str(protected_prompt_style or "").strip() or (
            "Let's think step by step and output the final answer within \\boxed{}."
        )
        self.frontier_override_min_support_margin = max(1, int(frontier_override_min_support_margin))
        self.frontier_override_min_maturity = max(1, int(frontier_override_min_maturity))
        self.require_frontier_multi_evidence = bool(require_frontier_multi_evidence)
        self.method_name = method_name

    def _run_protected_incumbent(self, question: str, gold_answer: str, max_actions: int) -> tuple[str | None, int, list[dict[str, Any]], list[dict[str, Any]]]:
        branch = self.generator.init_branch("near_direct_l1_max_0")
        actions = 0
        action_trace: list[dict[str, Any]] = []
        budgeted_question = (
            f"{question}\n\n{self.protected_prompt_style} "
            f"Think for maximum {self.protected_token_budget} tokens."
        )
        budget_actions = max(1, int(round(self.protected_token_budget / self.protected_token_per_action)))
        allowed_actions = min(max_actions, budget_actions)
        while actions < allowed_actions and not branch.is_done and not branch.is_pruned:
            self.generator.expand(branch, budgeted_question, gold_answer)
            actions += 1
            latest = branch.trace_events[-1] if branch.trace_events else {}
            action_trace.append(
                {
                    "action": "near_direct_l1_max",
                    "branch_id": branch.branch_id,
                    "branch_depth": int(branch.depth),
                    "prompt_text": str(latest.get("prompt_text", "")),
                    "response_text": str(latest.get("response_text", "")),
                    "reasoning_text": str(latest.get("reasoning_text", "")),
                    "extracted_answer": str(latest.get("extracted_answer", "") or ""),
                }
            )
        final_branch_states = [
            {
                "branch_id": str(branch.branch_id),
                "parent_branch_id": str(branch.parent_branch_id or ""),
                "branch_depth": int(branch.depth),
                "score": float(branch.score),
                "predicted_answer": str(branch.predicted_answer or ""),
                "is_done": bool(branch.is_done),
                "is_pruned": bool(branch.is_pruned),
                "steps": list(branch.steps),
                "trace_events": list(branch.trace_events),
                "strategy_family": "near_direct_l1_max",
                "source": "protected_incumbent",
                "selected": 1,
            }
        ]
        return branch.predicted_answer, actions, action_trace, final_branch_states

    def run(self, question: str, gold_answer: str) -> MethodResult:
        protected_answer, protected_actions, protected_trace, protected_states = self._run_protected_incumbent(
            question, gold_answer, self.max_actions
        )
        protected_group = _normalize_answer(str(protected_answer)) if protected_answer is not None else "__unknown__"
        remaining_budget = max(0, self.max_actions - int(protected_actions))

        frontier_result: MethodResult | None = None
        if remaining_budget > 0:
            frontier = self.strict_controller_factory(remaining_budget)
            if bool(getattr(self, "emit_full_traces", False)):
                setattr(frontier, "emit_full_traces", True)
            frontier_result = frontier.run(question, gold_answer)

        frontier_meta = dict(frontier_result.metadata or {}) if frontier_result else {}
        frontier_answer = frontier_result.prediction if frontier_result else None
        frontier_group = (_normalize_answer(str(frontier_answer)) if frontier_answer is not None else "__unknown__") or "__unknown__"
        support_counts: dict[str, int] = {}
        raw_support = frontier_meta.get("answer_group_support_counts", {})
        if isinstance(raw_support, dict):
            for k, v in raw_support.items():
                try:
                    support_counts[str(k)] = int(v)
                except Exception:
                    continue
        protected_seen = int(support_counts.get(protected_group, 0)) > 0
        frontier_support = int(support_counts.get(frontier_group, 0))
        incumbent_support = int(support_counts.get(protected_group, 0))
        frontier_maturity = int((frontier_result.expansions if frontier_result else 0) + (frontier_result.verifications if frontier_result else 0))
        support_margin = float(frontier_support - incumbent_support)
        maturity_margin = float(frontier_maturity - int(protected_actions))

        frontier_families = frontier_meta.get("answer_group_strategy_family_counts", {})
        frontier_family_count = 0
        if isinstance(frontier_families, dict):
            frontier_family_count = len(dict(frontier_families.get(frontier_group, {}) or {}))
        multi_evidence = bool(frontier_support >= 2 or frontier_family_count >= 2)

        override = False
        block_reason = "reserve_default"
        required_support_missing = bool(frontier_result is None or not support_counts)
        if required_support_missing:
            block_reason = "missing_support_fields"
        elif protected_seen:
            block_reason = "protected_incumbent_seen_in_frontier_support"
        elif frontier_support <= 1:
            block_reason = "single_weak_frontier_branch"
        elif frontier_maturity < self.frontier_override_min_maturity:
            block_reason = "frontier_not_mature"
        elif support_margin < float(self.frontier_override_min_support_margin):
            block_reason = "insufficient_support_margin"
        elif self.require_frontier_multi_evidence and not multi_evidence:
            block_reason = "insufficient_multi_branch_or_family_evidence"
        else:
            override = True
            block_reason = "frontier_support_margin_override"

        final_answer = frontier_answer if override else protected_answer
        actions_used = int(protected_actions + (frontier_result.actions_used if frontier_result else 0))
        expansions = int(protected_actions + (frontier_result.expansions if frontier_result else 0))
        verifications = int(frontier_result.verifications if frontier_result else 0)
        action_trace = list(frontier_meta.get("action_trace", [])) if isinstance(frontier_meta.get("action_trace", []), list) else []
        action_trace.extend(protected_trace)
        final_branch_states = list(frontier_meta.get("final_branch_states", [])) if isinstance(frontier_meta.get("final_branch_states", []), list) else []
        final_branch_states.extend(protected_states)
        combined_counts = Counter(dict(support_counts))
        if protected_group != "__unknown__":
            combined_counts[protected_group] += 1

        metadata = {
            "method_family": "diagnostic_near_direct_reserve_frontier_gate",
            "diagnostic_only": True,
            "not_canonical": True,
            "protected_incumbent_answer": protected_answer,
            "protected_incumbent_source_method": "external_l1_max_style_near_direct",
            "protected_incumbent_seen_in_frontier_support": bool(protected_seen),
            "incumbent_support_guard_applied": bool((not override) and protected_seen),
            "frontier_override_triggered": bool(override),
            "override_block_reason": str(block_reason if not override else "not_blocked"),
            "override_reason": str(block_reason),
            "frontier_candidate_answer": frontier_answer,
            "answer_group_support_counts": dict(combined_counts),
            "frontier_answer_group_counts": dict(support_counts),
            "frontier_support": int(frontier_support),
            "incumbent_support": int(incumbent_support),
            "support_margin": float(support_margin),
            "maturity_margin": float(maturity_margin),
            "frontier_candidate_maturity": int(frontier_maturity),
            "frontier_candidate_family_count": int(frontier_family_count),
            "required_support_fields_missing": bool(required_support_missing),
            "reserve_used": bool(not override),
            "protected_incumbent_trace": protected_trace,
            "frontier_metadata": dict(frontier_meta),
            "action_trace": action_trace,
            "final_branch_states": final_branch_states if bool(getattr(self, "emit_full_traces", False)) else [],
        }
        return MethodResult(
            method=self.method_name,
            prediction=final_answer,
            is_correct=self._answers_match(final_answer, gold_answer),
            actions_used=actions_used,
            expansions=expansions,
            verifications=verifications,
            avg_surviving_branches=float(frontier_result.avg_surviving_branches if frontier_result else 1.0),
            budget_exhausted=bool(actions_used >= self.max_actions),
            metadata=metadata,
        )


class CalibratedNearDirectFrontierGateController(NearDirectReserveFrontierGateController):
    """Diagnostic calibrated gate for near-direct incumbent escalation.

    This controller protects an L1-style near-direct incumbent and only escalates
    in a middle-confidence region. It is explicitly diagnostic-only.
    """

    def __init__(
        self,
        *args: Any,
        high_confidence_accept_threshold: float = 0.95,
        low_confidence_default_threshold: float = 0.0,
        support_margin_min: int = 1,
        maturity_margin_min: int = 1,
        verifier_margin_min: float = 0.0,
        require_verifier_margin: bool = False,
        block_artifact_sensitive_cases: bool = True,
        method_name: str = "calibrated_near_direct_frontier_gate_v1",
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, method_name=method_name, **kwargs)
        self.high_confidence_accept_threshold = float(high_confidence_accept_threshold)
        self.low_confidence_default_threshold = float(low_confidence_default_threshold)
        self.calibrated_support_margin_min = max(0, int(support_margin_min))
        self.calibrated_maturity_margin_min = int(maturity_margin_min)
        self.verifier_margin_min = float(verifier_margin_min)
        self.require_verifier_margin = bool(require_verifier_margin)
        self.block_artifact_sensitive_cases = bool(block_artifact_sensitive_cases)

    @staticmethod
    def _protected_confidence_proxy(states: list[dict[str, Any]], parse_success: bool) -> float:
        scores: list[float] = []
        for state in states:
            try:
                scores.append(float(state.get("score", 0.0)))
            except Exception:
                continue
        if scores:
            return float(max(scores))
        return 0.5 if parse_success else 0.0

    def run(self, question: str, gold_answer: str) -> MethodResult:
        protected_answer, protected_actions, protected_trace, protected_states = self._run_protected_incumbent(
            question, gold_answer, self.max_actions
        )
        parse_success = bool(protected_answer is not None and str(protected_answer).strip())
        direct_confidence = self._protected_confidence_proxy(protected_states, parse_success)
        direct_risk = float(1.0 - max(0.0, min(1.0, direct_confidence)))
        protected_group = _normalize_answer(str(protected_answer)) if protected_answer is not None else "__unknown__"

        metadata_base: dict[str, Any] = {
            "method_family": "diagnostic_calibrated_near_direct_frontier_gate",
            "diagnostic_only": True,
            "not_canonical": True,
            "protected_incumbent_answer": protected_answer,
            "protected_incumbent_source_method": "external_l1_max_style_near_direct",
            "protected_incumbent_parse_success": bool(parse_success),
            "direct_confidence_proxy": float(direct_confidence),
            "direct_risk_proxy": float(direct_risk),
            "incumbent_verifier_score": None,
            "frontier_verifier_score": None,
            "verifier_margin": None,
            "verifier_margin_available": False,
            "artifact_sensitive_case": False,
            "clean_override_eligible": False,
            "protected_incumbent_trace": protected_trace,
            "action_trace": list(protected_trace),
            "final_branch_states": protected_states if bool(getattr(self, "emit_full_traces", False)) else [],
        }

        def _reserve_result(region: str, reason: str, actions_used: int) -> MethodResult:
            md = dict(metadata_base)
            md.update(
                {
                    "gate_region": region,
                    "escalation_triggered": False,
                    "escalation_reason": reason,
                    "frontier_candidate_answer": None,
                    "protected_incumbent_seen_in_frontier_support": False,
                    "frontier_override_triggered": False,
                    "override_allowed": False,
                    "override_block_reason": reason,
                    "answer_group_support_counts": {},
                    "frontier_support": 0,
                    "incumbent_support": 0,
                    "support_margin": 0.0,
                    "maturity_margin": 0.0,
                    "frontier_candidate_family_count": 0,
                    "reserve_used": True,
                    "final_answer": protected_answer,
                }
            )
            return MethodResult(
                method=self.method_name,
                prediction=protected_answer,
                is_correct=self._answers_match(protected_answer, gold_answer),
                actions_used=actions_used,
                expansions=actions_used,
                verifications=0,
                avg_surviving_branches=1.0,
                budget_exhausted=bool(actions_used >= self.max_actions),
                metadata=md,
            )

        if not parse_success:
            return _reserve_result("low_confidence_default_reserve", "protected_incumbent_parse_failed", int(protected_actions))
        if direct_confidence >= self.high_confidence_accept_threshold:
            return _reserve_result("accept_high_confidence", "protected_incumbent_high_confidence", int(protected_actions))
        if direct_confidence <= self.low_confidence_default_threshold:
            return _reserve_result("low_confidence_default_reserve", "protected_incumbent_low_confidence", int(protected_actions))

        remaining_budget = max(0, self.max_actions - int(protected_actions))
        if remaining_budget <= 0:
            return _reserve_result("missing_features_default_reserve", "no_budget_for_frontier", int(protected_actions))

        frontier = self.strict_controller_factory(remaining_budget)
        if bool(getattr(self, "emit_full_traces", False)):
            setattr(frontier, "emit_full_traces", True)
        frontier_result = frontier.run(question, gold_answer)
        frontier_meta = dict(frontier_result.metadata or {})
        frontier_answer = frontier_result.prediction
        frontier_group = (_normalize_answer(str(frontier_answer)) if frontier_answer is not None else "__unknown__") or "__unknown__"

        support_counts: dict[str, int] = {}
        raw_support = frontier_meta.get("answer_group_support_counts", {})
        if isinstance(raw_support, dict):
            for k, v in raw_support.items():
                try:
                    support_counts[str(k)] = int(v)
                except Exception:
                    continue
        protected_seen = int(support_counts.get(protected_group, 0)) > 0
        frontier_support = int(support_counts.get(frontier_group, 0))
        incumbent_support = int(support_counts.get(protected_group, 0))
        support_margin = float(frontier_support - incumbent_support)
        frontier_maturity = int(frontier_result.expansions + frontier_result.verifications)
        maturity_margin = float(frontier_maturity - int(protected_actions))
        frontier_families = frontier_meta.get("answer_group_strategy_family_counts", {})
        frontier_family_count = 0
        if isinstance(frontier_families, dict):
            frontier_family_count = len(dict(frontier_families.get(frontier_group, {}) or {}))
        independent_evidence = bool(frontier_support >= 2 or frontier_family_count >= 2)
        verifier_margin_available = False
        verifier_margin = None

        block_reason = "not_blocked"
        override_allowed = False
        if not support_counts:
            block_reason = "missing_support_fields"
        elif protected_seen:
            block_reason = "protected_incumbent_seen_in_frontier_support"
        elif frontier_group == protected_group:
            block_reason = "frontier_agrees_with_incumbent"
        elif frontier_support < 2:
            block_reason = "frontier_support_below_threshold"
        elif not independent_evidence:
            block_reason = "insufficient_independent_frontier_evidence"
        elif support_margin < float(self.calibrated_support_margin_min):
            block_reason = "support_margin_below_threshold"
        elif maturity_margin < float(self.calibrated_maturity_margin_min):
            block_reason = "maturity_margin_below_threshold"
        elif self.require_verifier_margin and not verifier_margin_available:
            block_reason = "verifier_margin_missing"
        else:
            override_allowed = True
            block_reason = "not_blocked"

        final_answer = frontier_answer if override_allowed else protected_answer
        action_trace = list(frontier_meta.get("action_trace", [])) if isinstance(frontier_meta.get("action_trace", []), list) else []
        action_trace.extend(protected_trace)
        final_branch_states = list(frontier_meta.get("final_branch_states", [])) if isinstance(frontier_meta.get("final_branch_states", []), list) else []
        final_branch_states.extend(protected_states)
        combined_counts = Counter(dict(support_counts))
        if protected_group != "__unknown__":
            combined_counts[protected_group] += 1

        metadata = dict(metadata_base)
        metadata.update(
            {
                "gate_region": "escalate_middle_band" if override_allowed else "missing_features_default_reserve" if not support_counts else "escalate_middle_band",
                "escalation_triggered": True,
                "escalation_reason": "middle_band",
                "frontier_candidate_answer": frontier_answer,
                "protected_incumbent_seen_in_frontier_support": bool(protected_seen),
                "frontier_override_triggered": bool(override_allowed),
                "override_allowed": bool(override_allowed),
                "override_block_reason": block_reason if not override_allowed else "not_blocked",
                "answer_group_support_counts": dict(combined_counts),
                "frontier_answer_group_counts": dict(support_counts),
                "frontier_support": int(frontier_support),
                "incumbent_support": int(incumbent_support),
                "support_margin": float(support_margin),
                "maturity_margin": float(maturity_margin),
                "frontier_candidate_family_count": int(frontier_family_count),
                "frontier_candidate_maturity": int(frontier_maturity),
                "verifier_margin": verifier_margin,
                "verifier_margin_available": bool(verifier_margin_available),
                "clean_override_eligible": bool(override_allowed and not metadata_base["artifact_sensitive_case"]),
                "reserve_used": bool(not override_allowed),
                "final_answer": final_answer,
                "frontier_metadata": dict(frontier_meta),
                "action_trace": action_trace,
                "final_branch_states": final_branch_states if bool(getattr(self, "emit_full_traces", False)) else [],
            }
        )
        return MethodResult(
            method=self.method_name,
            prediction=final_answer,
            is_correct=self._answers_match(final_answer, gold_answer),
            actions_used=int(protected_actions + frontier_result.actions_used),
            expansions=int(protected_actions + frontier_result.expansions),
            verifications=int(frontier_result.verifications),
            avg_surviving_branches=float(frontier_result.avg_surviving_branches),
            budget_exhausted=bool((protected_actions + frontier_result.actions_used) >= self.max_actions),
            metadata=metadata,
        )


class L1LengthControlController(BaseController):
    """External baseline adapter for L1/LCPO-style length-conditioned control.

    Supports two inference-time modes used in the L1 paper/repo framing:
    - `exact`: condition on "think for exactly N tokens"
    - `max`: condition on "think for maximum N tokens"

    This adapter is intentionally inference-only for fair in-repo comparisons.
    It does not claim to reproduce L1 RL training.
    """

    def __init__(
        self,
        generator: BranchGenerator,
        scorer: BranchScorer,
        max_actions_per_problem: int,
        *,
        control_mode: str = "exact",
        token_budget: int = 512,
        token_per_action: float = 64.0,
        prompt_style: str = "Let's think step by step and output the final answer within \\boxed{}.",
        method_name: str = "external_l1_exact",
    ) -> None:
        super().__init__(generator, scorer, max_actions_per_problem)
        normalized_mode = control_mode.strip().lower()
        if normalized_mode not in {"exact", "max"}:
            normalized_mode = "exact"
        self.control_mode = normalized_mode
        self.token_budget = max(1, int(token_budget))
        self.token_per_action = max(1.0, float(token_per_action))
        self.prompt_style = prompt_style.strip() if prompt_style.strip() else "Let's think step by step."
        self.method_name = method_name

    @staticmethod
    def _estimate_generated_tokens(text: str | None) -> int:
        if not text:
            return 0
        return len(re.findall(r"\S+", text))

    def _compose_budgeted_question(self, question: str) -> str:
        if self.control_mode == "exact":
            length_instruction = f"Think for exactly {self.token_budget} tokens."
        else:
            length_instruction = f"Think for maximum {self.token_budget} tokens."
        return f"{question}\n\n{self.prompt_style} {length_instruction}"

    def run(self, question: str, gold_answer: str) -> MethodResult:
        branch = self.generator.init_branch(f"l1_{self.control_mode}_0")
        actions = expansions = verifications = 0
        surviving_trace: list[int] = []
        action_trace: list[dict[str, Any]] = []

        budgeted_question = self._compose_budgeted_question(question)
        budget_actions = max(1, int(round(self.token_budget / self.token_per_action)))
        allowed_actions = min(self.max_actions, budget_actions)

        while actions < allowed_actions and not branch.is_done and not branch.is_pruned:
            self.generator.expand(branch, budgeted_question, gold_answer)
            actions += 1
            expansions += 1
            surviving_trace.append(1)
            latest = branch.trace_events[-1] if branch.trace_events else {}
            action_trace.append(
                {
                    "action": "expand",
                    "branch_id": branch.branch_id,
                    "parent_branch_id": branch.parent_branch_id,
                    "branch_depth": int(branch.depth),
                    "prompt_text": str(latest.get("prompt_text", "")),
                    "response_text": str(latest.get("response_text", "")),
                    "reasoning_text": str(latest.get("reasoning_text", "")),
                    "extracted_answer": str(latest.get("extracted_answer", "") or ""),
                }
            )

        prediction = branch.predicted_answer
        generated_tokens_estimate = self._estimate_generated_tokens(prediction)

        budget_error = float(abs(generated_tokens_estimate - self.token_budget))
        if self.control_mode == "exact":
            violation = generated_tokens_estimate != self.token_budget
        else:
            violation = generated_tokens_estimate > self.token_budget

        return MethodResult(
            method=self.method_name,
            prediction=prediction,
            is_correct=self._answers_match(prediction, gold_answer),
            actions_used=actions,
            expansions=expansions,
            verifications=verifications,
            avg_surviving_branches=sum(surviving_trace) / max(1, len(surviving_trace)),
            budget_exhausted=actions >= allowed_actions and not branch.is_done,
            metadata={
                "external_baseline_family": "l1_lcpo_length_control",
                "l1_control_mode": self.control_mode,
                "token_budget_instruction": self.token_budget,
                "token_per_action": self.token_per_action,
                "budget_actions_equivalent": budget_actions,
                "generated_tokens_estimate": generated_tokens_estimate,
                "budget_error_tokens": budget_error,
                "token_budget_violation": bool(violation),
                "prompt_style": self.prompt_style,
                "final_score": self.scorer.score_branch(branch),
                "action_trace": action_trace,
                "final_branch_states": (
                    [
                        {
                            "branch_id": str(branch.branch_id),
                            "parent_branch_id": str(branch.parent_branch_id or ""),
                            "branch_depth": int(branch.depth),
                            "score": float(branch.score),
                            "predicted_answer": str(branch.predicted_answer or ""),
                            "is_done": bool(branch.is_done),
                            "is_pruned": bool(branch.is_pruned),
                            "steps": list(branch.steps),
                            "trace_events": list(branch.trace_events),
                        }
                    ]
                    if bool(getattr(self, "emit_full_traces", False))
                    else []
                ),
            },
        )


def _normalize_answer(text: str | None) -> str:
    if text is None:
        return ""
    stripped = str(text).strip()
    nums = re.findall(r"[-+]?\d+(?:\.\d+)?", stripped.replace(",", ""))
    if nums:
        value = nums[-1]
        if value.endswith(".0"):
            value = value[:-2]
        return value
    return stripped.lower()
