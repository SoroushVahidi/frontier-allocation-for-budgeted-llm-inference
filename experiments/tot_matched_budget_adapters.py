"""Matched-budget ToT-style search adapters (simulator / API-agnostic).

These are intentionally **not** an official Tree-of-Thoughts reproduction.
They expose recognizable breadth-first / beam / depth-first style multi-branch
expansion under the same per-problem action budget as other controllers.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from experiments.controllers import BaseController, BeamController, MethodResult
class TotBeamMatchedBudgetController(BaseController):
    """Beam-style fixed-width frontier with width derived from the action budget."""

    def run(self, question: str, gold_answer: str) -> MethodResult:
        width = max(2, min(4, max(1, self.max_actions // 2)))
        inner = BeamController(self.generator, self.scorer, self.max_actions, width=width)
        res = inner.run(question, gold_answer)
        return MethodResult(
            method="tot_beam_matched_budget",
            prediction=res.prediction,
            is_correct=res.is_correct,
            actions_used=res.actions_used,
            expansions=res.expansions,
            verifications=res.verifications,
            avg_surviving_branches=res.avg_surviving_branches,
            budget_exhausted=res.budget_exhausted,
            metadata={**res.metadata, "tot_style": "beam_matched_budget", "beam_width": width},
        )


class TotBfsMatchedBudgetController(BaseController):
    """Breadth-like round-robin expansion over a capped pool of parallel roots."""

    def run(self, question: str, gold_answer: str) -> MethodResult:
        width = max(2, min(5, max(1, self.max_actions // 3)))
        branches = [self.generator.init_branch(f"tot_bfs_{i}") for i in range(width)]
        actions = expansions = verifications = 0
        trace: list[int] = []
        idx = 0
        while actions < self.max_actions:
            active = [b for b in branches if not b.is_done and not b.is_pruned]
            if not active:
                break
            b = active[idx % len(active)]
            idx += 1
            self.generator.expand(b, question, gold_answer)
            actions += 1
            expansions += 1
            trace.append(len(active))
        candidates = [b for b in branches if not b.is_pruned]
        best = self.scorer.pick_best(candidates) if candidates else None
        prediction = best.predicted_answer if best else None
        return MethodResult(
            method="tot_bfs_matched_budget",
            prediction=prediction,
            is_correct=self._answers_match(prediction, gold_answer),
            actions_used=actions,
            expansions=expansions,
            verifications=verifications,
            avg_surviving_branches=sum(trace) / max(1, len(trace)),
            budget_exhausted=actions >= self.max_actions
            and any(not b.is_done and not b.is_pruned for b in branches),
            metadata={"tot_style": "bfs_round_robin_matched_budget", "parallel_roots": width},
        )


class TotDfsMatchedBudgetController(BaseController):
    """Depth-biased stack search: expand frontier tip; spawn sibling roots up to a cap."""

    def run(self, question: str, gold_answer: str) -> MethodResult:
        max_width = max(2, min(5, max(1, self.max_actions // 3)))
        stack: list = [self.generator.init_branch("tot_dfs_root")]
        pool: list = list(stack)
        actions = expansions = verifications = 0
        trace: list[int] = []
        fork_id = 0
        while actions < self.max_actions:
            while stack and (stack[-1].is_done or stack[-1].is_pruned):
                stack.pop()
            if not stack:
                break
            b = stack[-1]
            self.generator.expand(b, question, gold_answer)
            actions += 1
            expansions += 1
            trace.append(len(stack))
            if b.is_done:
                stack.pop()
                continue
            if len(stack) < max_width:
                fork_id += 1
                child = self.generator.init_branch(f"tot_dfs_fork_{fork_id}")
                stack.append(child)
                pool.append(child)
        candidates = [b for b in pool if not b.is_pruned]
        best = self.scorer.pick_best(candidates) if candidates else None
        prediction = best.predicted_answer if best else None
        return MethodResult(
            method="tot_dfs_matched_budget",
            prediction=prediction,
            is_correct=self._answers_match(prediction, gold_answer),
            actions_used=actions,
            expansions=expansions,
            verifications=verifications,
            avg_surviving_branches=sum(trace) / max(1, len(trace)),
            budget_exhausted=actions >= self.max_actions
            and any(not b.is_done and not b.is_pruned for b in pool),
            metadata={"tot_style": "dfs_stack_matched_budget", "max_parallel_branches": max_width},
        )


def attach_tot_matched_budget_methods(specs: dict, generator_factory: Callable[[], Any], scorer: Any, budget: int) -> None:
    """Register ToT-style adapters (each uses a fresh generator from ``generator_factory``)."""
    specs["tot_bfs_matched_budget"] = TotBfsMatchedBudgetController(generator_factory(), scorer, budget)
    specs["tot_beam_matched_budget"] = TotBeamMatchedBudgetController(generator_factory(), scorer, budget)
    specs["tot_dfs_matched_budget"] = TotDfsMatchedBudgetController(generator_factory(), scorer, budget)
