"""Controller implementations for the lightweight GSM8K pilot."""

from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Any, Protocol

from experiments.branching import BranchState
from experiments.objective_function_stack import compute_process_quality, compute_target_completion
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
        self.method_name = method_name

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

    def _branch_quality_surrogates(self, branch: BranchState) -> tuple[float, float]:
        completion_score = 1.0 if branch.is_done else min(0.95, 0.20 + 0.12 * float(branch.depth))
        answer_evidence = 1.0 if branch.predicted_answer is not None else min(0.7, max(0.0, float(branch.score)))
        semantic_incompleteness = 0.08 if branch.is_done else 0.55
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
        return float(process_quality), float(target_completion)

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
        priority = continuation + diversity_bonus + self.coverage_weight * coverage_gain - self.overlap_weight * semantic_overlap - duplicate_cost
        return priority, {
            "continuation_value": continuation,
            "diversity_bonus": diversity_bonus,
            "duplicate_cost": duplicate_cost,
            "coverage_gain": float(coverage_gain),
            "semantic_overlap": float(semantic_overlap),
            "group_key": group,
            **coverage_meta,
        }

    def _group_support_summary(
        self,
        branches: list[BranchState],
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
            for b in sorted(members, key=self.scorer.score_branch, reverse=True):
                process_quality, target_completion = self._branch_quality_surrogates(b)
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
                group_quality += support_weight * float(self.scorer.score_branch(b))
                group_readiness += support_weight * target_completion
                all_discounts.append(float(independence_discount))
                all_support_rows.append(
                    {
                        "branch_id": b.branch_id,
                        "group_key": gk,
                        "process_quality": float(process_quality),
                        "target_completion": float(target_completion),
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

    def _commit_by_answer_group_margin(self, *, branches: list[BranchState], actions: int) -> tuple[bool, dict[str, Any]]:
        summary = self._group_support_summary(branches)
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

    def _final_prediction_from_groups(self, branches: list[BranchState]) -> tuple[str | None, dict[str, Any]]:
        done = [b for b in branches if b.predicted_answer is not None]
        if not done:
            best = self.scorer.pick_best(branches)
            return (best.predicted_answer if best else None), {
                "selected_group": None,
                "group_support_fraction": 0.0,
                "aggregation_used": False,
                "discounted_group_supports": {},
            }

        summary = self._group_support_summary(done)
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
        best_group_key = None
        best_group_score = -10.0
        best_group_support = 0.0
        for gk, gmeta in groups.items():
            support_fraction = float(gmeta["discounted_support"]) / max(1e-8, total_support)
            quality_mean = float(gmeta["support_quality_mean"])
            readiness_mean = float(gmeta["readiness_mean"])
            group_score = (
                self.answer_support_weight * support_fraction
                + self.value_weight * quality_mean
                + self.support_quality_weight * readiness_mean
            )
            if group_score > best_group_score:
                best_group_score = group_score
                best_group_key = gk
                best_group_support = support_fraction

        members = [b for b in done if self._normalize_answer(b.predicted_answer) == best_group_key] if best_group_key is not None else done
        best_member = max(members, key=self.scorer.score_branch)
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
        }

    def run(self, question: str, gold_answer: str) -> MethodResult:
        actions = expansions = verifications = 0
        surviving_trace: list[int] = []
        action_trace: list[dict[str, Any]] = []
        branch_expansions: dict[str, int] = {}
        branches: list[BranchState] = [self.generator.init_branch("div_0"), self.generator.init_branch("div_1")]
        answer_support_counts: dict[str, int] = {}
        group_profiles: dict[str, list[set[str]]] = {}
        global_profiles: list[set[str]] = []
        expand_by_group: dict[str, int] = {}
        forced_explore_steps = 0
        commit_checks: list[dict[str, Any]] = []
        commit_triggered = False

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
                )
                scored.append((b, priority, meta))
            scored.sort(key=lambda x: x[1], reverse=True)
            branch, priority, pri_meta = scored[0]

            group_key = str(pri_meta.get("group_key") or "__unknown__")
            expand_by_group[group_key] = expand_by_group.get(group_key, 0) + 1
            b_expanded = branch_expansions.get(branch.branch_id, 0)

            # Global commit delay: avoid stopping early when support is not concentrated.
            top_support = 0.0
            support_total = sum(answer_support_counts.values())
            if support_total > 0:
                top_support = max(answer_support_counts.values()) / support_total
            force_explore = bool(actions < self.commit_delay_min_actions or top_support < self.commit_support_threshold)
            if force_explore:
                forced_explore_steps += 1

            if (b_expanded < self.min_branch_expansions) or force_explore or (priority >= float(self.scorer.score_branch(branch))):
                result = self.generator.expand(branch, question, gold_answer)
                actions += 1
                expansions += 1
                branch_expansions[branch.branch_id] = b_expanded + 1
                action_trace.append(
                    {
                        "action": "expand",
                        "branch_id": branch.branch_id,
                        "priority": round(priority, 4),
                        "continuation_value": round(float(pri_meta["continuation_value"]), 4),
                        "diversity_bonus": round(float(pri_meta["diversity_bonus"]), 4),
                        "duplicate_cost": round(float(pri_meta["duplicate_cost"]), 4),
                        "coverage_gain": round(float(pri_meta.get("coverage_gain", 0.0)), 4),
                        "semantic_overlap": round(float(pri_meta.get("semantic_overlap", 0.0)), 4),
                        "group_key": pri_meta["group_key"],
                        "force_explore": bool(force_explore),
                        "top_support_before_action": round(float(top_support), 4),
                    }
                )
                if branch.is_done:
                    done_key = self._normalize_answer(branch.predicted_answer) or "__unknown__"
                    answer_support_counts[done_key] = answer_support_counts.get(done_key, 0) + 1
                    profile = self._support_profile_features(branch)
                    group_profiles.setdefault(done_key, []).append(profile)
                    global_profiles.append(profile)
                elif len(branches) < self.max_branches and actions < self.max_actions:
                    child = self.generator.init_branch(f"div_child_{actions}_{len(branches)}")
                    child.score = 0.5 * child.score + 0.5 * branch.score
                    branches.append(child)
                    branch_expansions[child.branch_id] = 0
            else:
                result = self.generator.verify(branch, question)
                actions += 1
                verifications += 1
                action_trace.append(
                    {
                        "action": "verify",
                        "branch_id": branch.branch_id,
                        "priority": round(priority, 4),
                        "score_after": round(float(result.score_after), 4),
                        "force_explore": bool(force_explore),
                        "top_support_before_action": round(float(top_support), 4),
                    }
                )

            branches = [b for b in branches if not b.is_pruned]
            if len(branches) > self.max_branches:
                ranked = sorted(branches, key=self.scorer.score_branch, reverse=True)
                keep = {b.branch_id for b in ranked[: self.max_branches]}
                for b in branches:
                    if b.branch_id not in keep:
                        self.generator.prune(b)
                branches = [b for b in branches if not b.is_pruned]
            surviving_trace.append(len(branches))
            if self.use_answer_group_commit_margin:
                should_commit, commit_meta = self._commit_by_answer_group_margin(branches=branches, actions=actions)
                commit_checks.append(commit_meta)
                if should_commit:
                    commit_triggered = True
                    break
            if all(b.is_done for b in branches):
                break

        prediction, group_meta = self._final_prediction_from_groups(branches)
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
                "commit_triggered": bool(commit_triggered),
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
                "final_prediction": prediction,
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

        budgeted_question = self._compose_budgeted_question(question)
        budget_actions = max(1, int(round(self.token_budget / self.token_per_action)))
        allowed_actions = min(self.max_actions, budget_actions)

        while actions < allowed_actions and not branch.is_done and not branch.is_pruned:
            self.generator.expand(branch, budgeted_question, gold_answer)
            actions += 1
            expansions += 1
            surviving_trace.append(1)

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
