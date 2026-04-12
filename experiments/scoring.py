"""Scoring/verifier interfaces for the pilot.

These are intentionally simple placeholders for feasibility experiments.
"""

from __future__ import annotations

from dataclasses import dataclass

from experiments.branching import BranchState


@dataclass
class ScoreConfig:
    """Configuration for lightweight scoring behavior."""

    completion_bonus: float = 0.1
    depth_penalty: float = 0.02


class SimpleBranchScorer:
    """A tiny heuristic scorer for branches.

    This scorer is not a strong verifier. It only provides a rough signal so the
    pilot can test control-flow behavior before integrating stronger verifiers.
    """

    def __init__(self, config: ScoreConfig) -> None:
        self.config = config

    def score_branch(self, branch: BranchState) -> float:
        """Compute a simple score from branch metadata."""
        score = branch.score
        if branch.is_done:
            score += self.config.completion_bonus
        score -= self.config.depth_penalty * max(0, branch.depth - 1)
        return max(0.0, min(1.0, score))

    def pick_best(self, branches: list[BranchState]) -> BranchState | None:
        """Choose the best non-pruned branch by heuristic score."""
        candidates = [b for b in branches if not b.is_pruned]
        if not candidates:
            return None
        return max(candidates, key=self.score_branch)
