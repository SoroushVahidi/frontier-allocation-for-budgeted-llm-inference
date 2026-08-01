"""Lightweight PRM-style partial-branch scoring (new-paper track).

This module intentionally provides a **proxy** scorer inspired by PRM ideas, not a
trained process reward model.

Design goals:
- score partial traces for frontier ranking,
- expose explicit metadata for auditability,
- provide conservative early-rejection hooks.

ThinkPRM inspiration (approximation here):
- score intermediate reasoning states, not only final answers.
- track stage-specific signals for process quality.

Early-rejection PRM inspiration (approximation here):
- allow rejecting/down-ranking low-value partial traces after a minimum
  exploration floor.
- keep all decisions explicit in action traces/metadata.

What is missing vs true PRM:
- no supervised process-reward training,
- no token-level reward decomposition,
- no calibrated reward model over labeled trajectories.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Protocol

from experiments.branching import BranchState


@dataclass
class PRMScore:
    value: float
    score_source: str
    score_stage: str
    early_reject_flag: bool
    scorer_notes: str
    features: dict[str, float]


class PartialBranchScorer(Protocol):
    def score_partial_branch(self, branch: BranchState, question: str, *, stage: str = "frontier") -> PRMScore: ...

    def score_full_candidate(self, branch: BranchState, question: str) -> PRMScore: ...


class HeuristicPRMPartialScorer:
    """A lightweight, auditable PRM proxy scorer.

    This scorer mixes branch-internal confidence with shallow process features.
    It is intended as a drop-in approximation before true PRM training.
    """

    def __init__(
        self,
        *,
        depth_target: int = 4,
        depth_weight: float = 0.10,
        completion_bonus: float = 0.10,
        stagnation_penalty: float = 0.06,
        empty_step_penalty: float = 0.05,
        step_structure_weight: float = 0.08,
        floor: float = 0.0,
        ceiling: float = 1.0,
    ) -> None:
        self.depth_target = max(1, int(depth_target))
        self.depth_weight = float(depth_weight)
        self.completion_bonus = float(completion_bonus)
        self.stagnation_penalty = float(stagnation_penalty)
        self.empty_step_penalty = float(empty_step_penalty)
        self.step_structure_weight = float(step_structure_weight)
        self.floor = float(floor)
        self.ceiling = float(ceiling)

    def _clip(self, v: float) -> float:
        return max(self.floor, min(self.ceiling, v))

    @staticmethod
    def _step_structure_signal(steps: list[str]) -> float:
        if not steps:
            return 0.0
        txt = "\n".join(steps[-3:])
        has_math_ops = 1.0 if re.search(r"[=+\-*/]", txt) else 0.0
        has_number = 1.0 if re.search(r"\d", txt) else 0.0
        has_transition = 1.0 if re.search(r"therefore|so|thus|next|then", txt.lower()) else 0.0
        return (has_math_ops + has_number + has_transition) / 3.0

    @staticmethod
    def _stagnation_signal(steps: list[str]) -> float:
        if len(steps) < 2:
            return 0.0
        a = steps[-1].strip().lower()
        b = steps[-2].strip().lower()
        if not a or not b:
            return 0.5
        return 1.0 if a == b else 0.0

    def score_partial_branch(self, branch: BranchState, question: str, *, stage: str = "frontier") -> PRMScore:  # noqa: ARG002
        base = float(branch.score)
        depth_frac = min(1.0, float(branch.depth) / float(self.depth_target))
        depth_term = self.depth_weight * depth_frac
        structure = self._step_structure_signal(branch.steps)
        structure_term = self.step_structure_weight * structure
        stagnation = self._stagnation_signal(branch.steps)
        stagnation_term = -self.stagnation_penalty * stagnation
        empty_penalty = -self.empty_step_penalty if branch.steps and (not branch.steps[-1].strip()) else 0.0
        completion = self.completion_bonus if branch.is_done else 0.0

        raw = base + depth_term + structure_term + stagnation_term + empty_penalty + completion
        score = self._clip(raw)
        notes = (
            "proxy_prm=heuristic; "
            f"base={base:.3f},depth={depth_term:+.3f},structure={structure_term:+.3f},"
            f"stagnation={stagnation_term:+.3f},empty={empty_penalty:+.3f},completion={completion:+.3f}"
        )
        return PRMScore(
            value=score,
            score_source="heuristic_prm_proxy",
            score_stage=stage,
            early_reject_flag=False,
            scorer_notes=notes,
            features={
                "base_score": base,
                "depth": float(branch.depth),
                "depth_frac": depth_frac,
                "step_structure": structure,
                "stagnation": stagnation,
                "is_done": 1.0 if branch.is_done else 0.0,
            },
        )

    def score_full_candidate(self, branch: BranchState, question: str) -> PRMScore:
        scored = self.score_partial_branch(branch, question, stage="full_candidate")
        return PRMScore(
            value=scored.value,
            score_source=scored.score_source,
            score_stage="full_candidate",
            early_reject_flag=scored.early_reject_flag,
            scorer_notes=scored.scorer_notes,
            features=scored.features,
        )
