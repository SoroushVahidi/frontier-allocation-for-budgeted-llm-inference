"""Scoring/verifier interfaces for the pilot.

These are intentionally simple placeholders for feasibility experiments.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

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


class RelativeRankBranchScorer:
    """Approximate adaptive_relative_rank policy for branch prioritization."""

    def __init__(self, depth_bonus: float = 0.02) -> None:
        self.depth_bonus = depth_bonus

    def score_branch(self, branch: BranchState) -> float:
        return max(0.0, min(1.0, branch.score + self.depth_bonus * min(5, branch.depth)))

    def pick_best(self, branches: list[BranchState]) -> BranchState | None:
        candidates = [b for b in branches if not b.is_pruned]
        if not candidates:
            return None
        sorted_by_score = sorted(candidates, key=lambda b: b.score)
        rank_map = {b.branch_id: idx + 1 for idx, b in enumerate(sorted_by_score)}
        denom = max(1.0, float(len(candidates)))
        return max(candidates, key=lambda b: (rank_map[b.branch_id] / denom) + self.depth_bonus * b.depth)


class ScorePlusProgressBranchScorer:
    """Approximate adaptive_score_plus_progress policy."""

    def __init__(self, depth_bonus: float = 0.04) -> None:
        self.depth_bonus = depth_bonus

    def score_branch(self, branch: BranchState) -> float:
        raw = branch.score + self.depth_bonus * min(6, branch.depth)
        return max(0.0, min(1.0, raw))

    def pick_best(self, branches: list[BranchState]) -> BranchState | None:
        candidates = [b for b in branches if not b.is_pruned]
        if not candidates:
            return None
        return max(candidates, key=self.score_branch)


class LearnedBranchScorerV3:
    """Model-backed scorer for controller-time branch selection.

    Supports lightweight JSON artifacts exported by scripts/train_branch_scorer_v3.py.
    """

    def __init__(self, model_path: str | Path) -> None:
        self.model = json.loads(Path(model_path).read_text(encoding="utf-8"))

    def _features(self, branch: BranchState, parent_mean_score: float = 0.5) -> dict[str, float]:
        depth = float(branch.depth)
        score = float(branch.score)
        return {
            "score": score,
            "depth": depth,
            "stalled_steps": 0.0,
            "recent_delta": 0.0,
            "verify_count": 0.0,
            "branch_age": depth,
            "score_x_depth": score * depth,
            "parent_relative_score": score - parent_mean_score,
        }

    def _score_with_parent(self, branch: BranchState, parent_mean_score: float) -> float:
        features = self._features(branch, parent_mean_score)
        if self.model.get("model_type") == "logistic":
            linear = float(self.model.get("intercept", 0.0))
            for name, weight in self.model.get("weights", {}).items():
                linear += float(weight) * features.get(name, 0.0)
            return 1.0 / (1.0 + pow(2.718281828, -linear))

        if self.model.get("model_type") == "linear_regression":
            score = float(self.model.get("intercept", 0.0))
            for name, weight in self.model.get("weights", {}).items():
                score += float(weight) * features.get(name, 0.0)
            return score

        node = self.model.get("tree", {})
        while isinstance(node, dict) and "feature" in node:
            feature = str(node["feature"])
            threshold = float(node["threshold"])
            node = node["left"] if features.get(feature, 0.0) <= threshold else node["right"]
        return float(node.get("value", branch.score)) if isinstance(node, dict) else branch.score

    def score_branch(self, branch: BranchState) -> float:
        return self._score_with_parent(branch, parent_mean_score=0.5)

    def pick_best(self, branches: list[BranchState]) -> BranchState | None:
        candidates = [b for b in branches if not b.is_pruned]
        if not candidates:
            return None
        mean_score = sum(float(b.score) for b in candidates) / max(1, len(candidates))
        return max(candidates, key=lambda b: self._score_with_parent(b, mean_score))
