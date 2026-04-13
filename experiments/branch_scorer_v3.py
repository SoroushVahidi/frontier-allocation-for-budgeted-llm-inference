"""Decision-point ranking data and learned branch scorers (v1/v2/v3)."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
import random
from typing import Any

FEATURE_NAMES = [
    "score",
    "depth",
    "stalled_steps",
    "recent_delta",
    "verify_count",
    "branch_age",
    "score_x_depth",
    "parent_relative_score",
]


@dataclass
class SimBranch:
    branch_id: str
    latent_quality: float
    score: float
    depth: int = 0
    is_done: bool = False
    is_pruned: bool = False
    is_correct: bool = False
    stalled_steps: int = 0
    recent_delta: float = 0.0
    verify_count: int = 0
    branch_age: int = 0


def _clip01(value: float) -> float:
    return max(0.0, min(1.0, value))


def branch_features(branch: SimBranch, parent_mean_score: float = 0.5) -> dict[str, float]:
    return {
        "score": branch.score,
        "depth": float(branch.depth),
        "stalled_steps": float(branch.stalled_steps),
        "recent_delta": branch.recent_delta,
        "verify_count": float(branch.verify_count),
        "branch_age": float(branch.branch_age),
        "score_x_depth": branch.score * float(branch.depth),
        "parent_relative_score": branch.score - parent_mean_score,
    }


def expected_next_gain(branch: SimBranch, finish_prob_base: float, answer_noise: float) -> float:
    expected_drift = 0.015
    expected_score_after = _clip01(branch.score + expected_drift)
    finish_prob = min(0.95, finish_prob_base + 0.1 * (branch.depth + 1) + 0.25 * branch.latent_quality)
    expected_correct_if_finishes = max(0.05, expected_score_after - answer_noise)
    stalled_recovery = 0.06 * min(3.0, float(branch.stalled_steps)) * max(0.0, branch.latent_quality - 0.45)
    momentum_bonus = 0.04 * max(0.0, branch.recent_delta)
    saturation_penalty = 0.05 if branch.score > 0.82 and branch.depth > 3 else 0.0
    return finish_prob * expected_correct_if_finishes + stalled_recovery + momentum_bonus - saturation_penalty


def continuation_value(branch: SimBranch, finish_prob_base: float, answer_noise: float) -> float:
    """Scalar continuation-style value for next compute on this branch.

    This is intentionally non-binary: it combines expected immediate gain,
    branch confidence, and a depth regularizer to mimic progress-style value.
    """
    gain = expected_next_gain(branch, finish_prob_base, answer_noise)
    depth_penalty = 0.02 * max(0.0, float(branch.depth) - 2.0)
    return gain + 0.55 * branch.score - depth_penalty


def expand_branch(branch: SimBranch, rng: random.Random, finish_prob_base: float, answer_noise: float, max_depth: int) -> None:
    if branch.is_done or branch.is_pruned:
        return
    branch.depth += 1
    drift = rng.uniform(-0.06, 0.08) + 0.05 * (branch.latent_quality - 0.5) - 0.015 * min(3, branch.stalled_steps)
    old_score = branch.score
    branch.score = _clip01(branch.score + drift)
    branch.recent_delta = branch.score - old_score
    branch.stalled_steps = branch.stalled_steps + 1 if branch.recent_delta <= 0.005 else 0

    finish_prob = min(0.95, finish_prob_base + 0.1 * branch.depth + 0.25 * branch.latent_quality)
    should_finish = branch.depth >= max_depth or rng.random() < finish_prob
    if should_finish:
        branch.is_done = True
        correct_prob = max(0.05, branch.score - answer_noise)
        branch.is_correct = rng.random() < correct_prob


def maybe_verify(branch: SimBranch, rng: random.Random) -> None:
    if branch.is_done or branch.is_pruned:
        return
    branch.verify_count += 1
    correction = (branch.latent_quality - branch.score) * 0.35 + rng.uniform(-0.03, 0.03)
    branch.score = _clip01(branch.score + correction)


def baseline_priority(method: str, branch: SimBranch, active: list[SimBranch]) -> float:
    if method == "adaptive_raw_score":
        return branch.score
    if method == "adaptive_score_plus_progress":
        return branch.score + 0.04 * branch.depth - 0.02 * branch.stalled_steps
    if method == "adaptive_relative_rank":
        scores = sorted(b.score for b in active)
        rank = scores.index(branch.score) + 1
        return rank / max(1.0, float(len(active))) + 0.02 * branch.depth
    if method == "adaptive_eptree_baseline":
        # Lightweight EPTree-style proxy:
        # prioritize uncertain (high-entropy) and unstable branches for expansion.
        p = _clip01(branch.score)
        entropy = 0.0
        if 1e-6 < p < 1 - 1e-6:
            entropy = -(p * math.log(p) + (1 - p) * math.log(1 - p))
        instability = abs(branch.recent_delta) + 0.05 * min(3.0, float(branch.stalled_steps))
        shallow_bonus = 0.04 * max(0.0, 4.0 - float(branch.depth))
        return entropy + instability + shallow_bonus
    raise ValueError(f"Unknown baseline method: {method}")


def load_model(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def model_priority(model: dict[str, Any], features: dict[str, float]) -> float:
    model_type = model.get("model_type")
    if model_type == "logistic":
        linear = float(model.get("intercept", 0.0))
        for name, weight in model.get("weights", {}).items():
            linear += float(weight) * features.get(name, 0.0)
        if linear >= 0:
            z = 1.0 / (1.0 + pow(2.718281828, -linear))
        else:
            exp_linear = pow(2.718281828, linear)
            z = exp_linear / (1.0 + exp_linear)
        return z

    if model_type in {"decision_tree", "decision_tree_regressor"}:
        node = model["tree"]
        while "feature" in node:
            threshold = float(node["threshold"])
            value = features.get(str(node["feature"]), 0.0)
            node = node["left"] if value <= threshold else node["right"]
        return float(node["value"])

    if model_type == "linear_regression":
        score = float(model.get("intercept", 0.0))
        for name, weight in model.get("weights", {}).items():
            score += float(weight) * features.get(name, 0.0)
        return score

    raise ValueError(f"Unsupported model_type: {model_type}")


def _choose_branch(
    method: str,
    active: list[SimBranch],
    model_map: dict[str, dict[str, Any]] | None,
) -> SimBranch:
    if method.startswith("adaptive_learned_branch_score"):
        if model_map is None or method not in model_map:
            raise ValueError(f"Model for {method} not provided")
        model = model_map[method]
        parent_mean = sum(b.score for b in active) / max(1, len(active))
        return max(active, key=lambda b: model_priority(model, branch_features(b, parent_mean)))

    return max(active, key=lambda b: baseline_priority(method, b, active))


def simulate_controller(
    method: str,
    rng: random.Random,
    budget: int,
    n_init_branches: int,
    max_depth: int,
    finish_prob_base: float,
    answer_noise: float,
    model_map: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    branches = [
        SimBranch(
            branch_id=f"b_{idx}",
            latent_quality=rng.uniform(0.2, 0.95),
            score=rng.uniform(0.25, 0.75),
        )
        for idx in range(n_init_branches)
    ]

    for step in range(budget):
        for branch in branches:
            branch.branch_age += 1
        active = [b for b in branches if not b.is_done and not b.is_pruned]
        if not active:
            break

        chosen = _choose_branch(method, active, model_map)
        expand_branch(chosen, rng, finish_prob_base, answer_noise, max_depth)
        if not chosen.is_done and rng.random() < 0.35:
            maybe_verify(chosen, rng)

    done = [b for b in branches if b.is_done]
    if done:
        best = max(done, key=lambda b: b.score)
    else:
        best = max(branches, key=lambda b: b.score)

    return {
        "is_correct": bool(best.is_correct),
        "actions_used": budget,
        "solved_any": any(b.is_correct for b in branches if b.is_done),
    }
