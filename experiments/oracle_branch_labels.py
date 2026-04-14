"""Approximate-oracle branch-label generation for the new-paper branch-allocation track.

This module intentionally produces *bounded / approximate* continuation-value labels.
It does not claim exact oracle values except in trivial terminal/zero-budget states.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import itertools
import json
from pathlib import Path
import random
import statistics
from typing import Any

from experiments.branch_scorer_v3 import (
    SimBranch,
    branch_features_v7_ordered_history,
    continuation_value,
    expand_branch,
    maybe_verify,
)


ACTION_EXPAND = "expand"
ACTION_VERIFY = "verify"


@dataclass
class OracleLabelConfig:
    episodes: int = 24
    seed: int = 17
    decision_budget: int = 10
    n_init_branches: int = 4
    max_depth: int = 7
    finish_prob_base: float = 0.16
    answer_noise: float = 0.12
    max_decisions_per_episode_to_label: int = 3
    max_branches_per_decision: int = 3
    rollouts_per_policy: int = 3
    high_budget_multiplier: float = 1.5
    exhaustive_action_budget_cap: int = 2
    tie_margin: float = 0.02
    train_ratio: float = 0.8
    value_aggregation: str = "max"
    value_std_penalty: float = 0.0


@dataclass
class DecisionSnapshot:
    episode_id: int
    decision_id: int
    remaining_budget: int
    branch_states: list[SimBranch]


@dataclass
class RolloutOutcome:
    policy_name: str
    rollout_seed: int
    actions: list[str]
    terminal_reached: bool
    terminal_correct: bool
    actions_used: int
    final_score: float
    max_score_seen: float
    continuation_outcome_value: float



def clone_branch(branch: SimBranch) -> SimBranch:
    return SimBranch(
        branch_id=branch.branch_id,
        latent_quality=branch.latent_quality,
        score=branch.score,
        depth=branch.depth,
        is_done=branch.is_done,
        is_pruned=branch.is_pruned,
        is_correct=branch.is_correct,
        stalled_steps=branch.stalled_steps,
        recent_delta=branch.recent_delta,
        verify_count=branch.verify_count,
        branch_age=branch.branch_age,
        action_history=list(branch.action_history),
        score_history=list(branch.score_history),
        depth_history=list(branch.depth_history),
    )


def _step_policy_action(policy_name: str, branch: SimBranch, step_idx: int, rng: random.Random) -> str:
    if policy_name == "expand_only":
        return ACTION_EXPAND
    if policy_name == "verify_then_expand":
        return ACTION_VERIFY if step_idx == 0 else ACTION_EXPAND
    if policy_name == "stalled_recovery":
        if branch.stalled_steps > 0 or branch.recent_delta < 0.0:
            return ACTION_VERIFY
        return ACTION_EXPAND
    if policy_name == "random_mix":
        return ACTION_VERIFY if rng.random() < 0.30 else ACTION_EXPAND
    return ACTION_EXPAND


def _rollout_value(branch: SimBranch, max_score_seen: float, actions_used: int, budget: int) -> float:
    terminal = 1.0 if branch.is_done else 0.0
    correct = 1.0 if branch.is_done and branch.is_correct else 0.0
    completion_penalty = 1.0 if branch.is_done else 0.75
    budget_use_penalty = 1.0 - min(0.15, 0.03 * max(0, actions_used - max(1, budget // 2)))
    raw = 0.65 * correct + 0.20 * terminal + 0.15 * max_score_seen
    return max(0.0, min(1.0, raw * completion_penalty * budget_use_penalty))


def simulate_rollout(
    branch: SimBranch,
    remaining_budget: int,
    policy_name: str,
    rollout_seed: int,
    *,
    finish_prob_base: float,
    answer_noise: float,
    max_depth: int,
) -> RolloutOutcome:
    rng = random.Random(rollout_seed)
    work = clone_branch(branch)
    max_score_seen = float(work.score)
    actions: list[str] = []

    for step_idx in range(max(0, remaining_budget)):
        if work.is_done or work.is_pruned:
            break
        action = _step_policy_action(policy_name, work, step_idx, rng)
        actions.append(action)
        if action == ACTION_VERIFY:
            maybe_verify(work, rng)
        else:
            expand_branch(work, rng, finish_prob_base=finish_prob_base, answer_noise=answer_noise, max_depth=max_depth)
        max_score_seen = max(max_score_seen, float(work.score))

    value = _rollout_value(work, max_score_seen=max_score_seen, actions_used=len(actions), budget=remaining_budget)
    return RolloutOutcome(
        policy_name=policy_name,
        rollout_seed=rollout_seed,
        actions=actions,
        terminal_reached=bool(work.is_done),
        terminal_correct=bool(work.is_done and work.is_correct),
        actions_used=len(actions),
        final_score=float(work.score),
        max_score_seen=max_score_seen,
        continuation_outcome_value=value,
    )


def approximate_oracle_continuation_value(
    branch: SimBranch,
    remaining_budget: int,
    *,
    cfg: OracleLabelConfig,
    episode_id: int,
    decision_id: int,
) -> dict[str, Any]:
    if branch.is_done or remaining_budget <= 0:
        exact_value = 1.0 if branch.is_done and branch.is_correct else float(branch.score)
        return {
            "approx_oracle_continuation_value": float(exact_value),
            "label_kind": "exact_terminal_or_zero_budget",
            "value_is_exact": True,
            "rollout_count": 0,
            "best_rollout": None,
            "rollout_value_mean": float(exact_value),
            "rollout_value_std": 0.0,
        }

    high_budget = max(1, int(round(remaining_budget * cfg.high_budget_multiplier)))
    policy_names = ["expand_only", "verify_then_expand", "stalled_recovery", "random_mix"]

    outcomes: list[RolloutOutcome] = []
    for policy_idx, policy_name in enumerate(policy_names):
        for rep in range(cfg.rollouts_per_policy):
            rollout_seed = (
                cfg.seed * 10_000_019
                + episode_id * 19_999
                + decision_id * 3_001
                + policy_idx * 101
                + rep
            )
            outcomes.append(
                simulate_rollout(
                    branch,
                    remaining_budget=high_budget,
                    policy_name=policy_name,
                    rollout_seed=rollout_seed,
                    finish_prob_base=cfg.finish_prob_base,
                    answer_noise=cfg.answer_noise,
                    max_depth=cfg.max_depth,
                )
            )

    if remaining_budget <= cfg.exhaustive_action_budget_cap:
        action_space = [ACTION_EXPAND, ACTION_VERIFY]
        for actions in itertools.product(action_space, repeat=remaining_budget):
            rollout_seed = (
                cfg.seed * 1_000_003
                + episode_id * 1009
                + decision_id * 37
                + sum((idx + 1) * (7 if a == ACTION_VERIFY else 3) for idx, a in enumerate(actions))
            )
            work = clone_branch(branch)
            rng = random.Random(rollout_seed)
            max_score_seen = float(work.score)
            taken: list[str] = []
            for action in actions:
                if work.is_done or work.is_pruned:
                    break
                taken.append(action)
                if action == ACTION_VERIFY:
                    maybe_verify(work, rng)
                else:
                    expand_branch(work, rng, finish_prob_base=cfg.finish_prob_base, answer_noise=cfg.answer_noise, max_depth=cfg.max_depth)
                max_score_seen = max(max_score_seen, float(work.score))
            outcomes.append(
                RolloutOutcome(
                    policy_name="bounded_action_enumeration",
                    rollout_seed=rollout_seed,
                    actions=taken,
                    terminal_reached=bool(work.is_done),
                    terminal_correct=bool(work.is_done and work.is_correct),
                    actions_used=len(taken),
                    final_score=float(work.score),
                    max_score_seen=max_score_seen,
                    continuation_outcome_value=_rollout_value(work, max_score_seen=max_score_seen, actions_used=len(taken), budget=remaining_budget),
                )
            )

    values = [x.continuation_outcome_value for x in outcomes]
    best = max(outcomes, key=lambda x: x.continuation_outcome_value)
    sorted_values = sorted(values)
    q50 = sorted_values[len(sorted_values) // 2] if sorted_values else 0.0
    q75 = sorted_values[min(len(sorted_values) - 1, int(0.75 * (len(sorted_values) - 1)))] if sorted_values else 0.0
    value_mean = float(sum(values) / max(1, len(values)))
    value_std = float(statistics.pstdev(values)) if len(values) > 1 else 0.0
    if cfg.value_aggregation == "robust_blend":
        blended = 0.60 * q75 + 0.30 * value_mean + 0.10 * q50
        agg_value = max(0.0, min(1.0, blended - cfg.value_std_penalty * value_std))
        label_kind = "approx_high_budget_rollout_robust_blend"
    else:
        agg_value = float(best.continuation_outcome_value)
        label_kind = "approx_high_budget_rollout_max"

    return {
        "approx_oracle_continuation_value": float(agg_value),
        "label_kind": label_kind,
        "value_is_exact": False,
        "rollout_count": len(outcomes),
        "high_budget_used": high_budget,
        "best_rollout": asdict(best),
        "rollout_value_mean": value_mean,
        "rollout_value_std": value_std,
        "rollout_value_q50": float(q50),
        "rollout_value_q75": float(q75),
    }


def simulate_decision_snapshots(cfg: OracleLabelConfig) -> list[DecisionSnapshot]:
    rng = random.Random(cfg.seed)
    snapshots: list[DecisionSnapshot] = []

    for ep in range(cfg.episodes):
        branches = [
            SimBranch(
                branch_id=f"branch_{idx}",
                latent_quality=rng.uniform(0.2, 0.95),
                score=rng.uniform(0.25, 0.75),
            )
            for idx in range(cfg.n_init_branches)
        ]
        kept_decisions = 0
        for decision_id in range(cfg.decision_budget):
            for branch in branches:
                branch.branch_age += 1
            active = [b for b in branches if not b.is_done and not b.is_pruned]
            if len(active) <= 1:
                break

            remaining_budget = max(0, cfg.decision_budget - decision_id)
            if kept_decisions < cfg.max_decisions_per_episode_to_label:
                snapshots.append(
                    DecisionSnapshot(
                        episode_id=ep,
                        decision_id=decision_id,
                        remaining_budget=remaining_budget,
                        branch_states=[clone_branch(b) for b in active[: cfg.max_branches_per_decision]],
                    )
                )
                kept_decisions += 1

            chosen = rng.choice(active)
            expand_branch(
                chosen,
                rng,
                finish_prob_base=cfg.finish_prob_base,
                answer_noise=cfg.answer_noise,
                max_depth=cfg.max_depth,
            )
            if not chosen.is_done and rng.random() < 0.35:
                maybe_verify(chosen, rng)

    return snapshots


def generate_oracle_branch_labels(cfg: OracleLabelConfig) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    snapshots = simulate_decision_snapshots(cfg)
    branch_rows: list[dict[str, Any]] = []
    grouped: dict[tuple[int, int], list[dict[str, Any]]] = {}

    for snap in snapshots:
        parent_mean = sum(float(b.score) for b in snap.branch_states) / max(1, len(snap.branch_states))
        for branch in snap.branch_states:
            approx = approximate_oracle_continuation_value(
                branch,
                snap.remaining_budget,
                cfg=cfg,
                episode_id=snap.episode_id,
                decision_id=snap.decision_id,
            )
            proxy_value = continuation_value(branch, cfg.finish_prob_base, cfg.answer_noise)
            row = {
                "episode_id": snap.episode_id,
                "decision_id": snap.decision_id,
                "branch_id": branch.branch_id,
                "split": "train" if snap.episode_id < int(cfg.episodes * cfg.train_ratio) else "test",
                "remaining_budget": snap.remaining_budget,
                "score": float(branch.score),
                "depth": int(branch.depth),
                "verify_count": int(branch.verify_count),
                "stalled_steps": int(branch.stalled_steps),
                "action_history_len": int(len(branch.action_history)),
                "parent_relative_score": float(branch.score) - parent_mean,
                "proxy_continuation_value": float(proxy_value),
                **approx,
            }
            row["features_v7"] = branch_features_v7_ordered_history(
                branch=branch,
                parent_mean_score=parent_mean,
                remaining_budget=snap.remaining_budget,
            )
            branch_rows.append(row)
            grouped.setdefault((snap.episode_id, snap.decision_id), []).append(row)

    pair_rows: list[dict[str, Any]] = []
    agreements = 0
    disagreements = 0
    ties = 0
    confident_disagreements = 0
    for (episode_id, decision_id), rows in grouped.items():
        if len(rows) < 2:
            continue
        for i in range(len(rows)):
            for j in range(i + 1, len(rows)):
                a = rows[i]
                b = rows[j]
                oracle_delta = float(a["approx_oracle_continuation_value"]) - float(b["approx_oracle_continuation_value"])
                proxy_delta = float(a["proxy_continuation_value"]) - float(b["proxy_continuation_value"])
                oracle_tie = abs(oracle_delta) <= cfg.tie_margin
                proxy_tie = abs(proxy_delta) <= cfg.tie_margin
                if oracle_tie:
                    ties += 1
                    oracle_pref = 0
                else:
                    oracle_pref = 1 if oracle_delta > 0.0 else -1
                if proxy_tie:
                    proxy_pref = 0
                else:
                    proxy_pref = 1 if proxy_delta > 0.0 else -1

                agree = oracle_pref == proxy_pref
                if agree:
                    agreements += 1
                else:
                    disagreements += 1

                pair_rows.append(
                    {
                        "episode_id": episode_id,
                        "decision_id": decision_id,
                        "remaining_budget": int(a["remaining_budget"]),
                        "branch_a_id": a["branch_id"],
                        "branch_b_id": b["branch_id"],
                        "approx_oracle_a": float(a["approx_oracle_continuation_value"]),
                        "approx_oracle_b": float(b["approx_oracle_continuation_value"]),
                        "proxy_a": float(a["proxy_continuation_value"]),
                        "proxy_b": float(b["proxy_continuation_value"]),
                        "oracle_preference": oracle_pref,
                        "proxy_preference": proxy_pref,
                        "oracle_proxy_agree": int(agree),
                        "oracle_tie": int(oracle_tie),
                        "proxy_tie": int(proxy_tie),
                        "oracle_margin": abs(oracle_delta),
                        "proxy_margin": abs(proxy_delta),
                        "label_source": "approx_oracle_continuation_value_vs_proxy_continuation_value",
                    }
                )
                if (not agree) and (abs(oracle_delta) > cfg.tie_margin):
                    confident_disagreements += 1

    depth_bins: dict[str, int] = {}
    budget_bins: dict[str, int] = {}
    for row in branch_rows:
        depth = int(row["depth"])
        rem = int(row["remaining_budget"])
        depth_key = "0-1" if depth <= 1 else ("2-3" if depth <= 3 else "4+")
        budget_key = "0-2" if rem <= 2 else ("3-5" if rem <= 5 else "6+")
        depth_bins[depth_key] = depth_bins.get(depth_key, 0) + 1
        budget_bins[budget_key] = budget_bins.get(budget_key, 0) + 1

    summary = {
        "n_decision_snapshots": len(snapshots),
        "n_branch_labels": len(branch_rows),
        "n_pairwise_labels": len(pair_rows),
        "n_exact_labels": sum(1 for r in branch_rows if bool(r["value_is_exact"])),
        "n_approximate_labels": sum(1 for r in branch_rows if not bool(r["value_is_exact"])),
        "oracle_proxy_pair_agreement_rate": (agreements / max(1, agreements + disagreements)),
        "oracle_proxy_pair_disagreement_rate": (disagreements / max(1, agreements + disagreements)),
        "oracle_proxy_confident_disagreements": confident_disagreements,
        "oracle_pair_tie_rate": ties / max(1, len(pair_rows)),
        "branch_depth_distribution": depth_bins,
        "remaining_budget_distribution": budget_bins,
    }
    return branch_rows, pair_rows, summary


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")
