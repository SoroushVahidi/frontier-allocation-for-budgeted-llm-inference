"""Frontier allocation target-construction pipeline.

This module builds allocation-first supervision targets for the question:
"Which active branch should receive the next unit of compute?"

It supports two frontier-state sources:
1) replayed controller/simulator trace JSONL rows, and
2) lightweight synthetic trace generation for dry-runs.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import csv
import hashlib
import json
from pathlib import Path
import random
import statistics
from typing import Any

from experiments.branch_observability import build_branch_trace_record, write_branch_observability_bundle
from experiments.branch_scorer_v3 import SimBranch, continuation_value, expand_branch, maybe_verify


ACTION_EXPAND = "expand"
ACTION_VERIFY = "verify"


@dataclass
class FrontierTargetConstructionConfig:
    episodes: int = 24
    decision_budget: int = 10
    n_init_branches: int = 4
    max_depth: int = 7
    finish_prob_base: float = 0.16
    answer_noise: float = 0.12
    max_branches_per_state: int = 4
    rollouts_per_branch: int = 8
    tie_margin: float = 0.02
    outside_option_floor: float = 0.35
    rollout_policy: str = "stalled_aware"
    seed: int = 17
    train_ratio: float = 0.8


@dataclass
class FrontierState:
    state_id: str
    episode_id: int
    decision_id: int
    remaining_budget: int
    split: str
    active_branches: list[dict[str, Any]]
    branch_metadata: dict[str, Any]
    trace_provenance: dict[str, Any]
    dataset_name: str | None = None
    example_id: str | None = None
    ground_truth_answer: str | None = None


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def _stable_state_id(
    *,
    episode_id: int,
    decision_id: int,
    remaining_budget: int,
    active_branches: list[dict[str, Any]],
) -> str:
    canon = {
        "episode_id": int(episode_id),
        "decision_id": int(decision_id),
        "remaining_budget": int(remaining_budget),
        "active_branches": [
            {
                "branch_id": str(b.get("branch_id", "")),
                "score": round(float(b.get("score", 0.0)), 6),
                "depth": int(b.get("depth", 0)),
                "verify_count": int(b.get("verify_count", 0)),
                "stalled_steps": int(b.get("stalled_steps", 0)),
                "branch_age": int(b.get("branch_age", 0)),
            }
            for b in sorted(active_branches, key=lambda x: str(x.get("branch_id", "")))
        ],
    }
    payload = json.dumps(canon, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]
    return f"s_ep{episode_id}_d{decision_id}_r{remaining_budget}_{digest}"


def _clone_branch(branch: SimBranch) -> SimBranch:
    return SimBranch(
        branch_id=branch.branch_id,
        latent_quality=float(branch.latent_quality),
        score=float(branch.score),
        depth=int(branch.depth),
        is_done=bool(branch.is_done),
        is_pruned=bool(branch.is_pruned),
        is_correct=bool(branch.is_correct),
        stalled_steps=int(branch.stalled_steps),
        recent_delta=float(branch.recent_delta),
        verify_count=int(branch.verify_count),
        branch_age=int(branch.branch_age),
        action_history=list(branch.action_history),
        score_history=list(branch.score_history),
        depth_history=list(branch.depth_history),
    )


def _branch_to_snapshot(branch: SimBranch, parent_mean_score: float) -> dict[str, Any]:
    return {
        "branch_id": branch.branch_id,
        "score": float(branch.score),
        "depth": int(branch.depth),
        "verify_count": int(branch.verify_count),
        "stalled_steps": int(branch.stalled_steps),
        "recent_delta": float(branch.recent_delta),
        "branch_age": int(branch.branch_age),
        "is_done": int(branch.is_done),
        "is_pruned": int(branch.is_pruned),
        "action_history": list(branch.action_history),
        "score_history": [float(x) for x in branch.score_history],
        "depth_history": [int(x) for x in branch.depth_history],
        "parent_relative_score": float(branch.score) - float(parent_mean_score),
        "branch_text_raw": None,
        "branch_reasoning_text_raw": None,
        "branch_final_answer_text_raw": None,
        "generation_metadata": {
            "source": "synthetic_simulator",
            "notes": "Synthetic branch snapshots do not contain free-text reasoning traces.",
        },
    }


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _rollout_action(branch: SimBranch, *, rng: random.Random, policy_name: str) -> str:
    if policy_name == "expand_only":
        return ACTION_EXPAND
    if policy_name == "verify_only":
        return ACTION_VERIFY
    if branch.stalled_steps > 0 or branch.recent_delta <= 0.0:
        return ACTION_VERIFY if rng.random() < 0.65 else ACTION_EXPAND
    return ACTION_VERIFY if rng.random() < 0.20 else ACTION_EXPAND


def _simulate_next_unit(
    branches: list[SimBranch],
    *,
    target_branch_id: str,
    remaining_budget: int,
    seed: int,
    cfg: FrontierTargetConstructionConfig,
) -> dict[str, Any]:
    work = [_clone_branch(b) for b in branches]
    by_id = {b.branch_id: b for b in work}
    target = by_id.get(target_branch_id)
    if target is None:
        raise ValueError(f"target branch not found: {target_branch_id}")

    rng = random.Random(seed)
    chosen_action = _rollout_action(target, rng=rng, policy_name=cfg.rollout_policy)
    if chosen_action == ACTION_VERIFY:
        maybe_verify(target, rng)
    else:
        expand_branch(
            target,
            rng,
            finish_prob_base=cfg.finish_prob_base,
            answer_noise=cfg.answer_noise,
            max_depth=cfg.max_depth,
        )

    horizon = max(0, remaining_budget - 1)
    for _ in range(horizon):
        active = [b for b in work if not b.is_done and not b.is_pruned]
        if not active:
            break
        pick = max(active, key=lambda b: continuation_value(b, cfg.finish_prob_base, cfg.answer_noise))
        follow_action = _rollout_action(pick, rng=rng, policy_name=cfg.rollout_policy)
        if follow_action == ACTION_VERIFY:
            maybe_verify(pick, rng)
        else:
            expand_branch(
                pick,
                rng,
                finish_prob_base=cfg.finish_prob_base,
                answer_noise=cfg.answer_noise,
                max_depth=cfg.max_depth,
            )

    best_terminal = max(
        continuation_value(b, cfg.finish_prob_base, cfg.answer_noise)
        for b in work
    )
    return {
        "target_branch_id": target_branch_id,
        "seed": int(seed),
        "chosen_action": chosen_action,
        "portfolio_value": float(best_terminal),
        "budget_consumed": int(min(1 + horizon, max(1, remaining_budget))),
    }


def _collect_frontier_states_from_simulator(cfg: FrontierTargetConstructionConfig) -> list[FrontierState]:
    rng = random.Random(cfg.seed)
    states: list[FrontierState] = []

    for episode_id in range(cfg.episodes):
        branches = [
            SimBranch(
                branch_id=f"b_{idx}",
                latent_quality=rng.uniform(0.2, 0.95),
                score=rng.uniform(0.25, 0.75),
            )
            for idx in range(cfg.n_init_branches)
        ]

        for decision_id in range(cfg.decision_budget):
            for branch in branches:
                branch.branch_age += 1
            active = [b for b in branches if not b.is_done and not b.is_pruned]
            if len(active) <= 1:
                break

            remaining_budget = max(0, cfg.decision_budget - decision_id)
            active_kept = active[: cfg.max_branches_per_state]
            parent_mean_score = sum(float(b.score) for b in active_kept) / max(1, len(active_kept))
            active_snapshots = [_branch_to_snapshot(b, parent_mean_score) for b in active_kept]
            state_id = _stable_state_id(
                episode_id=episode_id,
                decision_id=decision_id,
                remaining_budget=remaining_budget,
                active_branches=active_snapshots,
            )
            states.append(
                FrontierState(
                    state_id=state_id,
                    episode_id=episode_id,
                    decision_id=decision_id,
                    remaining_budget=remaining_budget,
                    split="train" if episode_id < int(cfg.episodes * cfg.train_ratio) else "test",
                    active_branches=active_snapshots,
                    branch_metadata={
                        "n_active_branches": len(active_kept),
                        "branch_ids": [str(x["branch_id"]) for x in active_snapshots],
                        "parent_mean_score": float(parent_mean_score),
                    },
                    trace_provenance={
                        "source": "synthetic_simulator",
                        "seed": int(cfg.seed),
                    },
                )
            )

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

    return states


def _collect_frontier_states_from_trace_rows(rows: list[dict[str, Any]], cfg: FrontierTargetConstructionConfig) -> list[FrontierState]:
    grouped: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for row in rows:
        if "episode_id" not in row or "decision_id" not in row:
            continue
        key = (int(row["episode_id"]), int(row["decision_id"]))
        grouped.setdefault(key, []).append(row)

    states: list[FrontierState] = []
    for (episode_id, decision_id), group in sorted(grouped.items()):
        first = group[0]
        remaining_budget = int(first.get("remaining_budget", max(0, cfg.decision_budget - decision_id)))
        dataset_name = str(first.get("dataset_name", "")).strip() or None
        example_id = str(first.get("example_id", "")).strip() or None
        ground_truth_answer = str(first.get("answer", "")).strip() or None

        active_branches: list[dict[str, Any]] = []
        if isinstance(first.get("active_branches"), list):
            for b in first["active_branches"][: cfg.max_branches_per_state]:
                active_branches.append(
                    {
                        "branch_id": str(b.get("branch_id", f"trace_b_{len(active_branches)}")),
                        "score": float(b.get("score", 0.5)),
                        "depth": int(b.get("depth", 0)),
                        "verify_count": int(b.get("verify_count", 0)),
                        "stalled_steps": int(b.get("stalled_steps", 0)),
                        "recent_delta": float(b.get("recent_delta", 0.0)),
                        "branch_age": int(b.get("branch_age", 0)),
                        "is_done": int(bool(b.get("is_done", False))),
                        "is_pruned": int(bool(b.get("is_pruned", False))),
                        "action_history": list(b.get("action_history", [])),
                        "score_history": list(b.get("score_history", [])),
                        "depth_history": list(b.get("depth_history", [])),
                        "parent_relative_score": float(b.get("parent_relative_score", 0.0)),
                        "branch_text_raw": b.get("branch_text_raw"),
                        "branch_reasoning_text_raw": b.get("branch_reasoning_text_raw"),
                        "branch_final_answer_text_raw": b.get("branch_final_answer_text_raw"),
                        "generation_metadata": dict(b.get("generation_metadata", {})) if isinstance(b.get("generation_metadata"), dict) else {},
                    }
                )
        else:
            for row in group[: cfg.max_branches_per_state]:
                active_branches.append(
                    {
                        "branch_id": str(row.get("branch_id", f"trace_b_{len(active_branches)}")),
                        "score": float(row.get("score", 0.5)),
                        "depth": int(row.get("depth", 0)),
                        "verify_count": int(row.get("verify_count", 0)),
                        "stalled_steps": int(row.get("stalled_steps", 0)),
                        "recent_delta": float(row.get("recent_delta", 0.0)),
                        "branch_age": int(row.get("branch_age", 0)),
                        "is_done": int(bool(row.get("is_done", False))),
                        "is_pruned": int(bool(row.get("is_pruned", False))),
                        "action_history": list(row.get("action_history", [])),
                        "score_history": list(row.get("score_history", [])),
                        "depth_history": list(row.get("depth_history", [])),
                        "parent_relative_score": float(row.get("parent_relative_score", 0.0)),
                        "branch_text_raw": row.get("branch_text_raw"),
                        "branch_reasoning_text_raw": row.get("branch_reasoning_text_raw"),
                        "branch_final_answer_text_raw": row.get("branch_final_answer_text_raw"),
                        "generation_metadata": dict(row.get("generation_metadata", {})) if isinstance(row.get("generation_metadata"), dict) else {},
                    }
                )

        if len(active_branches) <= 1:
            continue

        state_id = _stable_state_id(
            episode_id=episode_id,
            decision_id=decision_id,
            remaining_budget=remaining_budget,
            active_branches=active_branches,
        )
        states.append(
            FrontierState(
                state_id=state_id,
                episode_id=episode_id,
                decision_id=decision_id,
                remaining_budget=remaining_budget,
                split=str(first.get("split", "train")),
                active_branches=active_branches,
                branch_metadata={
                    "n_active_branches": len(active_branches),
                    "branch_ids": [str(x["branch_id"]) for x in active_branches],
                    "trace_group_size": len(group),
                },
                trace_provenance={
                    "source": "trace_jsonl",
                    "input_rows_in_group": len(group),
                    "method_name": first.get("method_name"),
                    "method_chosen_branch_id": first.get("method_chosen_branch_id"),
                    "method_score_margin_top2": first.get("method_score_margin_top2"),
                },
                dataset_name=dataset_name,
                example_id=example_id,
                ground_truth_answer=ground_truth_answer,
            )
        )

    return states


def _snapshot_to_sim_branch(branch_snapshot: dict[str, Any]) -> SimBranch:
    return SimBranch(
        branch_id=str(branch_snapshot.get("branch_id", "")),
        latent_quality=float(branch_snapshot.get("score", 0.5)),
        score=float(branch_snapshot.get("score", 0.5)),
        depth=int(branch_snapshot.get("depth", 0)),
        is_done=bool(int(branch_snapshot.get("is_done", 0))),
        is_pruned=bool(int(branch_snapshot.get("is_pruned", 0))),
        is_correct=False,
        stalled_steps=int(branch_snapshot.get("stalled_steps", 0)),
        recent_delta=float(branch_snapshot.get("recent_delta", 0.0)),
        verify_count=int(branch_snapshot.get("verify_count", 0)),
        branch_age=int(branch_snapshot.get("branch_age", 0)),
        action_history=[str(x) for x in list(branch_snapshot.get("action_history", []))],
        score_history=[float(x) for x in list(branch_snapshot.get("score_history", []))],
        depth_history=[int(x) for x in list(branch_snapshot.get("depth_history", []))],
    )


def estimate_marginal_utility_rows(
    states: list[FrontierState],
    cfg: FrontierTargetConstructionConfig,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for state in states:
        branches = [_snapshot_to_sim_branch(b) for b in state.active_branches]
        branch_ids = [b.branch_id for b in branches]

        for branch_index, branch_id in enumerate(branch_ids):
            alternatives = [x for x in branch_ids if x != branch_id]
            best_alt_id = max(
                alternatives,
                key=lambda bid: next(b.score for b in branches if b.branch_id == bid),
            ) if alternatives else None

            values_if_branch: list[float] = []
            values_if_best_alt: list[float] = []
            branch_rollouts: list[dict[str, Any]] = []
            alt_rollouts: list[dict[str, Any]] = []

            for ridx in range(cfg.rollouts_per_branch):
                seed_branch = (
                    cfg.seed * 10_000_019
                    + state.episode_id * 100_003
                    + state.decision_id * 1_009
                    + branch_index * 97
                    + ridx
                )
                out_branch = _simulate_next_unit(
                    branches,
                    target_branch_id=branch_id,
                    remaining_budget=state.remaining_budget,
                    seed=seed_branch,
                    cfg=cfg,
                )
                values_if_branch.append(float(out_branch["portfolio_value"]))
                branch_rollouts.append(out_branch)

                if best_alt_id is not None:
                    seed_alt = seed_branch + 409
                    out_alt = _simulate_next_unit(
                        branches,
                        target_branch_id=best_alt_id,
                        remaining_budget=state.remaining_budget,
                        seed=seed_alt,
                        cfg=cfg,
                    )
                    values_if_best_alt.append(float(out_alt["portfolio_value"]))
                    alt_rollouts.append(out_alt)

            expected_if_branch = float(sum(values_if_branch) / max(1, len(values_if_branch)))
            expected_if_alt = float(sum(values_if_best_alt) / max(1, len(values_if_best_alt))) if values_if_best_alt else 0.0
            delta_u = expected_if_branch - expected_if_alt

            outside_option_utility = max(float(cfg.outside_option_floor), expected_if_alt)
            delta_vs_outside = expected_if_branch - outside_option_utility

            rows.append(
                {
                    "state_id": state.state_id,
                    "episode_id": state.episode_id,
                    "decision_id": state.decision_id,
                    "remaining_budget": state.remaining_budget,
                    "split": state.split,
                    "branch_id": branch_id,
                    "best_alternative_branch_id": best_alt_id,
                    "delta_u": float(delta_u),
                    "delta_u_definition": (
                        "E[value if next unit spent on branch b] - "
                        "E[value under best alternative usage of that unit]"
                    ),
                    "expected_value_if_branch": expected_if_branch,
                    "expected_value_if_best_alternative": expected_if_alt,
                    "outside_option_utility": float(outside_option_utility),
                    "delta_u_vs_outside": float(delta_vs_outside),
                    "branch_rollout_value_std": float(statistics.pstdev(values_if_branch)) if len(values_if_branch) > 1 else 0.0,
                    "alt_rollout_value_std": float(statistics.pstdev(values_if_best_alt)) if len(values_if_best_alt) > 1 else 0.0,
                    "rollout_count": int(cfg.rollouts_per_branch),
                    "label_act_vs_outside": int(delta_vs_outside > cfg.tie_margin),
                    "provenance": {
                        "estimator": "branch_conditioned_rollout",
                        "seed_discipline": "fixed_formula_per_state_branch_rollout",
                        "branch_rollout_seeds": [int(r["seed"]) for r in branch_rollouts],
                        "alternative_rollout_seeds": [int(r["seed"]) for r in alt_rollouts],
                        "rollout_policy": cfg.rollout_policy,
                    },
                }
            )

    return rows


def build_comparative_targets(
    utility_rows: list[dict[str, Any]],
    *,
    tie_margin: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_state: dict[str, list[dict[str, Any]]] = {}
    for row in utility_rows:
        by_state.setdefault(str(row["state_id"]), []).append(row)

    pairwise: list[dict[str, Any]] = []
    outside: list[dict[str, Any]] = []

    for state_id, rows in by_state.items():
        for row in rows:
            outside.append(
                {
                    "state_id": state_id,
                    "episode_id": int(row["episode_id"]),
                    "decision_id": int(row["decision_id"]),
                    "remaining_budget": int(row["remaining_budget"]),
                    "branch_id": str(row["branch_id"]),
                    "delta_u_vs_outside": float(row["delta_u_vs_outside"]),
                    "outside_option_utility": float(row["outside_option_utility"]),
                    "label_prefer_branch_over_outside": int(float(row["delta_u_vs_outside"]) > tie_margin),
                    "tie_margin": float(tie_margin),
                    "label_source": "frontier_next_unit_allocation_vs_outside_option",
                }
            )

        for i in range(len(rows)):
            for j in range(i + 1, len(rows)):
                a = rows[i]
                b = rows[j]
                delta_diff = float(a["delta_u"]) - float(b["delta_u"])
                if abs(delta_diff) <= tie_margin:
                    pref = 0
                else:
                    pref = 1 if delta_diff > 0.0 else -1
                pairwise.append(
                    {
                        "state_id": state_id,
                        "episode_id": int(a["episode_id"]),
                        "decision_id": int(a["decision_id"]),
                        "remaining_budget": int(a["remaining_budget"]),
                        "branch_a_id": str(a["branch_id"]),
                        "branch_b_id": str(b["branch_id"]),
                        "delta_u_a": float(a["delta_u"]),
                        "delta_u_b": float(b["delta_u"]),
                        "delta_u_difference": float(delta_diff),
                        "label_preference": int(pref),
                        "tie_margin": float(tie_margin),
                        "label_source": "pairwise_branch_allocation_from_delta_u_difference",
                    }
                )

    return pairwise, outside


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _build_schema_stub() -> dict[str, Any]:
    return {
        "schema_version": "frontier_target_construction.v1",
        "allocation_first_note": (
            "Targets represent next-unit frontier allocation preference under remaining budget, "
            "not a standalone global stop decision."
        ),
        "files": {
            "frontier_states": {
                "required": [
                    "state_id",
                    "episode_id",
                    "decision_id",
                    "remaining_budget",
                    "active_branches",
                    "branch_metadata",
                    "trace_provenance",
                ]
            },
            "branch_marginal_utility": {
                "required": [
                    "state_id",
                    "branch_id",
                    "delta_u",
                    "expected_value_if_branch",
                    "expected_value_if_best_alternative",
                    "delta_u_vs_outside",
                    "provenance",
                ]
            },
            "pairwise_targets": {
                "required": ["state_id", "branch_a_id", "branch_b_id", "delta_u_difference", "label_preference"]
            },
            "outside_option_targets": {
                "required": ["state_id", "branch_id", "delta_u_vs_outside", "label_prefer_branch_over_outside"]
            },
        },
    }


def run_frontier_target_construction(
    cfg: FrontierTargetConstructionConfig,
    *,
    output_dir: Path,
    trace_jsonl: Path | None = None,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    run_id = output_dir.name

    if trace_jsonl is None:
        states = _collect_frontier_states_from_simulator(cfg)
        trace_source = "synthetic_simulator"
    else:
        trace_rows = _read_jsonl(trace_jsonl)
        states = _collect_frontier_states_from_trace_rows(trace_rows, cfg)
        trace_source = str(trace_jsonl)

    utility_rows = estimate_marginal_utility_rows(states, cfg)
    pairwise_rows, outside_rows = build_comparative_targets(utility_rows, tie_margin=cfg.tie_margin)

    state_rows = [asdict(s) for s in states]
    _write_jsonl(output_dir / "frontier_states.jsonl", state_rows)
    _write_jsonl(output_dir / "branch_marginal_utility.jsonl", utility_rows)
    _write_jsonl(output_dir / "pairwise_allocation_targets.jsonl", pairwise_rows)
    _write_jsonl(output_dir / "outside_option_targets.jsonl", outside_rows)

    summary = {
        "n_states": len(states),
        "n_branch_utility_rows": len(utility_rows),
        "n_pairwise_labels": len(pairwise_rows),
        "n_outside_option_labels": len(outside_rows),
        "avg_remaining_budget": (
            sum(int(s.remaining_budget) for s in states) / max(1, len(states))
        ),
        "avg_active_branches_per_state": (
            sum(len(s.active_branches) for s in states) / max(1, len(states))
        ),
        "pairwise_tie_rate": (
            sum(1 for r in pairwise_rows if int(r["label_preference"]) == 0) / max(1, len(pairwise_rows))
        ),
        "outside_option_positive_rate": (
            sum(1 for r in outside_rows if int(r["label_prefer_branch_over_outside"]) == 1) / max(1, len(outside_rows))
        ),
        "trace_source": trace_source,
    }
    _write_csv(output_dir / "summary.csv", [{"metric": k, "value": v} for k, v in summary.items()])
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    schema = _build_schema_stub()
    (output_dir / "frontier_target_schema.json").write_text(json.dumps(schema, indent=2), encoding="utf-8")

    config_echo = asdict(cfg)
    (output_dir / "config_echo.json").write_text(json.dumps(config_echo, indent=2), encoding="utf-8")

    manifest = {
        "run_id": run_id,
        "created_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "pipeline": "frontier_target_construction",
        "semantics": {
            "allocation_first": True,
            "interpretation": "next_unit_frontier_allocation",
            "delta_u_definition": (
                "delta_u(b | B) = E[value if next unit spent on b] - "
                "E[value under best alternative usage of that unit]"
            ),
        },
        "inputs": {
            "trace_jsonl": str(trace_jsonl) if trace_jsonl else None,
            "trace_source_mode": trace_source,
        },
        "outputs": {
            "frontier_states": "frontier_states.jsonl",
            "branch_marginal_utility": "branch_marginal_utility.jsonl",
            "pairwise_targets": "pairwise_allocation_targets.jsonl",
            "outside_option_targets": "outside_option_targets.jsonl",
            "summary_csv": "summary.csv",
            "summary_json": "summary.json",
            "schema": "frontier_target_schema.json",
            "config_echo": "config_echo.json",
        },
        "summary": summary,
    }

    observability_records: list[dict[str, Any]] = []
    for state in states:
        for branch in state.active_branches:
            observability_records.append(
                build_branch_trace_record(
                    dataset_name=state.dataset_name,
                    example_id=state.example_id,
                    state_id=state.state_id,
                    branch=branch,
                    state_provenance=state.trace_provenance,
                    generation_metadata={
                        **dict(branch.get("generation_metadata", {})),
                        "frontier_target_split": state.split,
                        "remaining_budget": state.remaining_budget,
                    },
                    ground_truth_answer=state.ground_truth_answer,
                )
            )
    observability_out = write_branch_observability_bundle(
        output_root=Path("outputs/branch_observability"),
        run_id=run_id,
        records=observability_records,
        commands_assumptions_caveats=[
            "# Commands / assumptions / caveats",
            "",
            "- Bundle generated from `experiments.frontier_target_construction.run_frontier_target_construction`.",
            "- Branch free-text fields are copied from input trace rows when present.",
            "- For synthetic simulator states, branch text/reasoning/final-answer fields remain null by design.",
        ],
        context_manifest={
            "pipeline": "frontier_target_construction",
            "source_trace": str(trace_jsonl) if trace_jsonl else None,
            "trace_source_mode": trace_source,
            "output_dir": str(output_dir),
        },
    )
    manifest["outputs"]["branch_observability_bundle"] = observability_out["bundle_dir"]
    manifest["outputs"]["branch_observability_manifest"] = observability_out["manifest_path"]
    manifest["summary"]["branch_observability_recoverability"] = observability_out["recoverability_summary"]

    (output_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    return {
        "summary": summary,
        "manifest": manifest,
        "output_dir": str(output_dir),
    }
