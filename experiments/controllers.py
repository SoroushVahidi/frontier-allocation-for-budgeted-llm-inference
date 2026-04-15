"""Controller implementations for the lightweight GSM8K pilot."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Protocol

from experiments.branching import BranchState
from experiments.prm_partial_scorer import PartialBranchScorer
from experiments.scoring import SimpleBranchScorer
from experiments.verifiers import CandidateVerifier


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


def _normalize_answer(text: str) -> str:
    stripped = text.strip()
    nums = re.findall(r"[-+]?\d+(?:\.\d+)?", stripped.replace(",", ""))
    if nums:
        value = nums[-1]
        if value.endswith(".0"):
            value = value[:-2]
        return value
    return stripped.lower()
