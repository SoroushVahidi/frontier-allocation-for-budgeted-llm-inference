"""Branch state and branch operations for the lightweight pilot experiment.

This module intentionally keeps the simulation logic simple and explicit.
The default generator below is a placeholder that can run locally without an API.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import random
from typing import Optional


@dataclass
class BranchState:
    """State for one partial reasoning trajectory."""

    branch_id: str
    latent_quality: float
    steps: list[str] = field(default_factory=list)
    score: float = 0.5
    predicted_answer: Optional[str] = None
    is_done: bool = False
    is_pruned: bool = False

    @property
    def depth(self) -> int:
        """Number of expansion steps already taken for this branch."""
        return len(self.steps)


@dataclass
class BranchActionResult:
    """Result metadata for a single branch operation."""

    action: str
    score_before: float
    score_after: float
    became_done: bool


class SimulatedBranchGenerator:
    """Simple local generator used when no external LLM is wired.

    NOTE: This simulator is intentionally provisional. To make controller logic
    testable without an API key, it uses a stochastic process and (optionally)
    the known gold answer when finalizing a branch.
    """

    def __init__(
        self,
        rng: random.Random,
        max_depth: int,
        finish_prob_base: float,
        answer_noise: float,
    ) -> None:
        self.rng = rng
        self.max_depth = max_depth
        self.finish_prob_base = finish_prob_base
        self.answer_noise = answer_noise

    def init_branch(self, branch_id: str) -> BranchState:
        """Initialize a branch with sampled latent quality."""
        latent_quality = self.rng.uniform(0.2, 0.95)
        return BranchState(branch_id=branch_id, latent_quality=latent_quality, score=latent_quality)

    def expand(self, branch: BranchState, gold_answer: str) -> BranchActionResult:
        """Expand a branch by one reasoning step in simulation mode."""
        if branch.is_done or branch.is_pruned:
            return BranchActionResult("expand", branch.score, branch.score, branch.is_done)

        score_before = branch.score
        branch.steps.append(f"step_{branch.depth + 1}")

        # Keep a little drift so branch quality can move during expansion.
        drift = self.rng.uniform(-0.05, 0.08)
        branch.score = min(1.0, max(0.0, branch.score + drift))

        finish_prob = min(
            0.95,
            self.finish_prob_base + 0.1 * branch.depth + 0.25 * branch.latent_quality,
        )
        should_finish = branch.depth >= self.max_depth or self.rng.random() < finish_prob

        if should_finish:
            branch.is_done = True
            # Placeholder correctness simulation.
            is_correct = self.rng.random() < max(0.05, branch.score - self.answer_noise)
            if is_correct:
                branch.predicted_answer = gold_answer
            else:
                branch.predicted_answer = self._make_wrong_answer(gold_answer)

        return BranchActionResult("expand", score_before, branch.score, branch.is_done)

    def verify(self, branch: BranchState) -> BranchActionResult:
        """Re-score a branch with a lightweight verification step."""
        score_before = branch.score
        correction = (branch.latent_quality - branch.score) * 0.35
        jitter = self.rng.uniform(-0.03, 0.03)
        branch.score = min(1.0, max(0.0, branch.score + correction + jitter))
        return BranchActionResult("verify", score_before, branch.score, branch.is_done)

    @staticmethod
    def prune(branch: BranchState) -> BranchActionResult:
        """Prune (discard) a branch."""
        score_before = branch.score
        branch.is_pruned = True
        return BranchActionResult("prune", score_before, branch.score, branch.is_done)

    def _make_wrong_answer(self, gold_answer: str) -> str:
        """Create a nearby incorrect answer for simulation diagnostics."""
        try:
            value = int(float(gold_answer))
            return str(value + self.rng.choice([-3, -2, -1, 1, 2, 3]))
        except ValueError:
            return f"wrong_{self.rng.randint(0, 999)}"
