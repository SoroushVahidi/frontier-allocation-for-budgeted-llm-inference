"""Controller implementations for the lightweight GSM8K pilot."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Protocol

from experiments.branching import BranchState
from experiments.scoring import SimpleBranchScorer


class BranchScorer(Protocol):
    def score_branch(self, branch: BranchState) -> float: ...

    def pick_best(self, branches: list[BranchState]) -> BranchState | None: ...



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
        method_name: str = "adaptive_expand_verify_prune",
    ) -> None:
        super().__init__(generator, scorer, max_actions_per_problem)
        self.high_threshold = high_threshold
        self.low_threshold = low_threshold
        self.max_branches = max_branches
        self.allow_verify = allow_verify
        self.min_expansions_before_prune = max(0, min_expansions_before_prune)
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

                score_before = self.scorer.score_branch(branch)
                branch_expand_count = branch_expansions.get(branch.branch_id, 0)
                if branch_expand_count < self.min_expansions_before_prune:
                    result = self.generator.expand(branch, question, gold_answer)
                    actions += 1
                    expansions += 1
                    branch_expansions[branch.branch_id] = branch_expand_count + 1
                    next_branches.append(branch)
                    action_trace.append(
                        self._trace_row(branch, "expand", score_before, result.score_after, actions, forced_expand=True)
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
                        self._trace_row(branch, "expand", score_before, result.score_after, actions)
                    )
                    if not branch.is_done and len(next_branches) < self.max_branches and actions < self.max_actions:
                        child = self.generator.init_branch(f"adaptive_child_{actions}_{len(next_branches)}")
                        child.score = 0.5 * child.score + 0.5 * branch.score
                        next_branches.append(child)
                        branch_expansions[child.branch_id] = 0
                elif self.allow_verify and score_before >= self.low_threshold:
                    result = self.generator.verify(branch, question)
                    actions += 1
                    verifications += 1
                    next_branches.append(branch)
                    action_trace.append(
                        self._trace_row(branch, "verify", score_before, result.score_after, actions)
                    )
                else:
                    result = self.generator.prune(branch)
                    action_trace.append(
                        self._trace_row(branch, "prune", score_before, result.score_after, actions)
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
    ) -> dict[str, Any]:
        return {
            "branch_id": branch.branch_id,
            "action": action,
            "score_before": round(score_before, 4),
            "score_after": round(score_after, 4),
            "forced_expand": forced_expand,
            "remaining_budget": max(0, self.max_actions - actions_used),
            "branch_done": branch.is_done,
            "branch_pruned": branch.is_pruned,
            "predicted_answer": branch.predicted_answer,
        }


def _normalize_answer(text: str) -> str:
    stripped = text.strip()
    nums = re.findall(r"[-+]?\d+(?:\.\d+)?", stripped.replace(",", ""))
    if nums:
        value = nums[-1]
        if value.endswith(".0"):
            value = value[:-2]
        return value
    return stripped.lower()
