"""Scoring/verifier interfaces for the pilot.

These are intentionally simple placeholders for feasibility experiments.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import json
from pathlib import Path

from experiments.branching import BranchState
from experiments.branch_scorer_v3 import (
    ACTION_EXPAND,
    ACTION_START,
    ACTION_VERIFY,
    estimate_distance_to_terminal_proxy,
    estimate_future_value_proxy,
)


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


def _ordered_history_features(branch: BranchState, parent_mean_score: float, remaining_budget: int) -> dict[str, float]:
    scores = [float(x) for x in branch.score_history] + [float(branch.score)]
    depths = [float(x) for x in branch.depth_history] + [float(branch.depth)]
    actions = list(branch.action_history)
    node_scores = scores[-4:]
    node_depths = depths[-4:]
    node_masks = [1.0] * len(node_scores)
    while len(node_scores) < 4:
        node_scores.insert(0, 0.0)
        node_depths.insert(0, 0.0)
        node_masks.insert(0, 0.0)
    edge_actions = actions[-3:]
    while len(edge_actions) < 3:
        edge_actions.insert(0, ACTION_START)
    deltas = [scores[i + 1] - scores[i] for i in range(len(scores) - 1)]
    edge_deltas = deltas[-3:]
    while len(edge_deltas) < 3:
        edge_deltas.insert(0, 0.0)

    out = {
        "remaining_budget": float(max(0, remaining_budget)),
        "verify_count": float(branch.verify_count),
        "stalled_steps": float(branch.stalled_steps),
        "branch_age": float(max(branch.branch_age, branch.depth)),
        "parent_relative_score": float(branch.score) - parent_mean_score,
    }
    for i in range(4):
        action_for_distance = ACTION_START if i == 0 else edge_actions[min(i - 1, 2)]
        out[f"node_{i}_mask"] = node_masks[i]
        out[f"node_{i}_score"] = node_scores[i]
        out[f"node_{i}_future_value_est"] = estimate_future_value_proxy(node_scores[i], int(node_depths[i]))
        out[f"node_{i}_distance_to_terminal_est"] = estimate_distance_to_terminal_proxy(
            node_scores[i], int(node_depths[i]), action_for_distance
        )
    for i in range(3):
        action = edge_actions[i]
        out[f"edge_{i}_is_start"] = 1.0 if action == ACTION_START else 0.0
        out[f"edge_{i}_is_expand"] = 1.0 if action == ACTION_EXPAND else 0.0
        out[f"edge_{i}_is_verify"] = 1.0 if action == ACTION_VERIFY else 0.0
        out[f"edge_{i}_score_delta"] = float(edge_deltas[i])
    return out


class LearnedBTBranchScorer:
    """BT-trained scorer with scalar inference.

    Training can be pairwise; inference stays O(n): score each branch once and argmax.
    """

    def __init__(self, model_path: str | Path, max_actions_per_problem: int) -> None:
        self.model = json.loads(Path(model_path).read_text(encoding="utf-8"))
        self.max_actions = max_actions_per_problem

    def _score(self, branch: BranchState, parent_mean_score: float) -> float:
        features = _ordered_history_features(
            branch,
            parent_mean_score=parent_mean_score,
            remaining_budget=max(0, self.max_actions - branch.depth),
        )
        score = float(self.model.get("intercept", 0.0))
        for name, weight in self.model.get("weights", {}).items():
            score += float(weight) * float(features.get(name, 0.0))

        adj = self.model.get("posthoc_adjustment", {})
        if isinstance(adj, dict) and adj:
            remaining_budget = max(0, self.max_actions - branch.depth)
            low_budget_threshold = int(adj.get("low_budget_threshold", -1))
            stalled_steps_threshold = float(adj.get("stalled_steps_threshold", 0.0))
            verify_count_threshold = float(adj.get("verify_count_threshold", 0.0))
            penalty = float(adj.get("penalty", 0.0))
            if (
                remaining_budget <= low_budget_threshold
                and float(branch.stalled_steps) >= stalled_steps_threshold
                and float(branch.verify_count) >= verify_count_threshold
            ):
                score -= penalty
        return score

    def score_branch(self, branch: BranchState) -> float:
        return self._score(branch, parent_mean_score=0.5)

    def pick_best(self, branches: list[BranchState]) -> BranchState | None:
        candidates = [b for b in branches if not b.is_pruned]
        if not candidates:
            return None
        parent_mean = sum(float(b.score) for b in candidates) / max(1, len(candidates))
        scored = [(b, self._score(b, parent_mean_score=parent_mean)) for b in candidates]
        scored.sort(key=lambda x: x[1], reverse=True)

        adj = self.model.get("posthoc_adjustment", {})
        close_margin_threshold = float(adj.get("close_margin_threshold", -1.0)) if isinstance(adj, dict) else -1.0
        if len(scored) >= 2 and close_margin_threshold >= 0.0:
            gap = float(scored[0][1]) - float(scored[1][1])
            if gap <= close_margin_threshold:
                return max(candidates, key=lambda b: float(b.score))

        return scored[0][0]


class TwoStageNearTieBTBranchScorer:
    """Two-stage scorer: baseline BT first, then near-tie tie-breaker on close top-2.

    Stage 1 keeps the strong global BT utility model.
    Stage 2 is only invoked when the top-2 baseline scores are within
    `near_tie_margin`, then a lightweight logistic tie-breaker chooses between them.
    """

    def __init__(self, model_path: str | Path, max_actions_per_problem: int) -> None:
        self.model = json.loads(Path(model_path).read_text(encoding="utf-8"))
        self.max_actions = max_actions_per_problem
        self.base_model = self.model.get("base_model", {})
        self.tie_model = self.model.get("tie_break_model", {})
        self.near_tie_margin = float(self.model.get("near_tie_margin", 0.06))

    def _base_score(self, branch: BranchState, parent_mean_score: float) -> float:
        features = _ordered_history_features(
            branch,
            parent_mean_score=parent_mean_score,
            remaining_budget=max(0, self.max_actions - branch.depth),
        )
        score = float(self.base_model.get("intercept", 0.0))
        for name, weight in self.base_model.get("weights", {}).items():
            score += float(weight) * float(features.get(name, 0.0))
        return score

    def _tie_features(self, a: BranchState, b: BranchState, parent_mean_score: float) -> dict[str, float]:
        fa = _ordered_history_features(
            a,
            parent_mean_score=parent_mean_score,
            remaining_budget=max(0, self.max_actions - a.depth),
        )
        fb = _ordered_history_features(
            b,
            parent_mean_score=parent_mean_score,
            remaining_budget=max(0, self.max_actions - b.depth),
        )
        feats: dict[str, float] = {}
        for name in self.tie_model.get("feature_names", []):
            if name.startswith("diff::"):
                base = name.split("::", 1)[1]
                feats[name] = float(fa.get(base, 0.0)) - float(fb.get(base, 0.0))
            elif name.startswith("abs_diff::"):
                base = name.split("::", 1)[1]
                feats[name] = abs(float(fa.get(base, 0.0)) - float(fb.get(base, 0.0)))
            else:
                feats[name] = 0.0
        return feats

    @staticmethod
    def _sigmoid(z: float) -> float:
        if z >= 0:
            ez = math.exp(-z)
            return 1.0 / (1.0 + ez)
        ez = math.exp(z)
        return ez / (1.0 + ez)

    def _tie_prob_a(self, a: BranchState, b: BranchState, parent_mean_score: float) -> float:
        feats = self._tie_features(a, b, parent_mean_score)
        model_type = str(self.tie_model.get("model_type", "logistic_regression"))
        if model_type == "decision_stump":
            feature = str(self.tie_model.get("stump_feature", ""))
            threshold = float(self.tie_model.get("threshold", 0.0))
            left_prob = float(self.tie_model.get("left_prob_a", 0.5))
            right_prob = float(self.tie_model.get("right_prob_a", 0.5))
            return left_prob if float(feats.get(feature, 0.0)) <= threshold else right_prob

        z = float(self.tie_model.get("intercept", 0.0))
        for name, weight in self.tie_model.get("weights", {}).items():
            z += float(weight) * float(feats.get(name, 0.0))
        return self._sigmoid(z)

    def score_branch(self, branch: BranchState) -> float:
        return self._base_score(branch, parent_mean_score=0.5)

    def pick_best(self, branches: list[BranchState]) -> BranchState | None:
        candidates = [b for b in branches if not b.is_pruned]
        if not candidates:
            return None
        parent_mean = sum(float(b.score) for b in candidates) / max(1, len(candidates))
        ranked = sorted(candidates, key=lambda b: self._base_score(b, parent_mean), reverse=True)
        if len(ranked) < 2:
            return ranked[0]
        gap = self._base_score(ranked[0], parent_mean) - self._base_score(ranked[1], parent_mean)
        if gap > self.near_tie_margin:
            return ranked[0]
        p_top = self._tie_prob_a(ranked[0], ranked[1], parent_mean)
        return ranked[0] if p_top >= 0.5 else ranked[1]
