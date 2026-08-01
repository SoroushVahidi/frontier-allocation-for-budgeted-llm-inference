"""Brute-force / near-brute-force branch-comparison label generation utilities.

This module builds auditable next-step branch-allocation supervision labels by
simulating expensive continuation evaluation under a fixed remaining budget.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import itertools
import json
import math
from pathlib import Path
import random
from typing import Any

from experiments.branch_scorer_v3 import SimBranch, expand_branch, maybe_verify
from experiments.data import extract_final_answer
from experiments.hf_datasets import resolve_dataset_spec, sample_hf_examples


GENERATOR_VERSION = "branch_label_bruteforce_v1"


@dataclass(frozen=True)
class BruteForceLabelConfig:
    dataset_name: str = "openai/gsm8k"
    dataset_split: str | None = None
    dataset_config: str | None = None
    seed: int = 7
    max_frontier_states: int = 100
    episodes_per_example: int = 2
    init_branches: int = 4
    max_branches_per_state: int = 5
    frontier_budget: int = 8
    min_remaining_budget: int = 2
    max_remaining_budget: int = 5
    state_capture_prob: float = 0.7
    finish_prob_base: float = 0.16
    answer_noise: float = 0.12
    max_depth: int = 7
    exact_mode: bool = False
    max_exact_branches: int = 4
    max_exact_remaining_budget: int = 5
    rollout_samples_per_candidate: int = 48
    max_allocation_samples: int = 128
    include_verify_actions: bool = True
    verify_prob: float = 0.35
    allow_mock_data: bool = True
    ambiguity_near_tie_threshold: float = 0.02
    ambiguity_medium_threshold: float = 0.08
    ambiguity_high_threshold: float = 0.16
    # bounded variance-reduction controls for Q_expand - Q_commit targets
    target_estimation_repeats: int = 1
    paired_rollout_comparison: bool = True
    reliability_min_samples: int = 4
    reliability_floor: float = 0.05
    reliability_scale: float = 2.0
    target_mode: str = "legacy_plus_value_awareness_v1"


@dataclass
class FrontierState:
    state_id: str
    example_id: str
    question: str
    answer: str
    source_episode_id: int
    decision_index: int
    remaining_budget: int
    active_branches: list[SimBranch]


def _stable_seed(*parts: Any) -> int:
    key = "|".join(str(p) for p in parts)
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return int(digest[:16], 16) % (2**31 - 1)


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


def _clone_branches(branches: list[SimBranch]) -> list[SimBranch]:
    return [_clone_branch(b) for b in branches]


def _state_utility(branches: list[SimBranch]) -> float:
    done_correct = sum(1.0 for b in branches if b.is_done and b.is_correct)
    max_score = max((b.score for b in branches), default=0.0)
    avg_score = sum(float(b.score) for b in branches) / max(1, len(branches))
    unresolved_penalty = 0.04 * sum(1.0 for b in branches if not b.is_done and not b.is_pruned)
    return 0.60 * done_correct + 0.25 * max_score + 0.15 * avg_score - unresolved_penalty


def _branch_feature_dict(branch: SimBranch, *, parent_mean_score: float, remaining_budget: int) -> dict[str, float]:
    return {
        "remaining_budget": float(remaining_budget),
        "score": float(branch.score),
        "depth": float(branch.depth),
        "stalled_steps": float(branch.stalled_steps),
        "recent_delta": float(branch.recent_delta),
        "verify_count": float(branch.verify_count),
        "branch_age": float(branch.branch_age),
        "parent_relative_score": float(branch.score - parent_mean_score),
    }


def _expand_branch_once(branch: SimBranch, rng: random.Random, cfg: BruteForceLabelConfig) -> None:
    expand_branch(
        branch=branch,
        rng=rng,
        finish_prob_base=float(cfg.finish_prob_base),
        answer_noise=float(cfg.answer_noise),
        max_depth=int(cfg.max_depth),
    )
    if (
        cfg.include_verify_actions
        and (not branch.is_done)
        and (not branch.is_pruned)
        and rng.random() < float(cfg.verify_prob)
    ):
        maybe_verify(branch, rng)


def _apply_allocation(
    branches: list[SimBranch],
    allocation: tuple[int, ...],
    *,
    rng_seed: int,
    cfg: BruteForceLabelConfig,
) -> float:
    rng = random.Random(rng_seed)
    for idx, steps in enumerate(allocation):
        branch = branches[idx]
        for _ in range(int(steps)):
            if branch.is_done or branch.is_pruned:
                break
            branch.branch_age += 1
            _expand_branch_once(branch, rng, cfg)
    return _state_utility(branches)


def _integer_compositions(total: int, parts: int) -> list[tuple[int, ...]]:
    if parts <= 0:
        return []
    if parts == 1:
        return [(total,)]
    out: list[tuple[int, ...]] = []
    for separators in itertools.combinations(range(total + parts - 1), parts - 1):
        prev = -1
        comp: list[int] = []
        for sep in separators:
            comp.append(sep - prev - 1)
            prev = sep
        comp.append(total + parts - 1 - prev - 1)
        out.append(tuple(comp))
    return out


def _sample_allocations(total: int, parts: int, *, rng: random.Random, max_samples: int) -> list[tuple[int, ...]]:
    if total <= 0:
        return [tuple(0 for _ in range(parts))]
    all_exact = _integer_compositions(total, parts)
    if len(all_exact) <= max_samples:
        return all_exact
    picks = rng.sample(all_exact, k=max_samples)
    # include uniform baseline allocation for stability/auditability
    base = [total // parts for _ in range(parts)]
    for i in range(total % parts):
        base[i] += 1
    base_tuple = tuple(base)
    if base_tuple not in picks:
        picks[0] = base_tuple
    return picks


def _choose_candidate_allocations(
    *,
    remaining_budget_after_first: int,
    n_branches: int,
    exact_mode: bool,
    cfg: BruteForceLabelConfig,
    rng: random.Random,
) -> tuple[str, list[tuple[int, ...]]]:
    if remaining_budget_after_first <= 0:
        return ("degenerate", [tuple(0 for _ in range(n_branches))])

    exact_feasible = (
        exact_mode
        and n_branches <= int(cfg.max_exact_branches)
        and remaining_budget_after_first <= int(cfg.max_exact_remaining_budget)
    )
    if exact_feasible:
        return ("exact", _integer_compositions(remaining_budget_after_first, n_branches))
    return (
        "approx",
        _sample_allocations(
            remaining_budget_after_first,
            n_branches,
            rng=rng,
            max_samples=int(cfg.max_allocation_samples),
        ),
    )


def load_dataset_examples(cfg: BruteForceLabelConfig) -> list[dict[str, str]]:
    try:
        spec = resolve_dataset_spec(cfg.dataset_name)
        split = cfg.dataset_split or spec.default_split
        rows = sample_hf_examples(
            dataset_name=cfg.dataset_name,
            pilot_size=max(1, cfg.max_frontier_states),
            seed=cfg.seed,
            split=split,
            config_name=cfg.dataset_config if cfg.dataset_config is not None else spec.default_config,
        )
        out: list[dict[str, str]] = []
        for row in rows:
            out.append(
                {
                    "example_id": str(row["example_id"]),
                    "question": str(row["question"]),
                    "answer": extract_final_answer(str(row["answer"])),
                }
            )
        return out
    except Exception:
        if not cfg.allow_mock_data:
            raise
        rng = random.Random(cfg.seed)
        mocks: list[dict[str, str]] = []
        for idx in range(max(1, cfg.max_frontier_states)):
            a = rng.randint(3, 80)
            b = rng.randint(1, 30)
            c = rng.randint(1, 10)
            mocks.append(
                {
                    "example_id": f"mock_{idx}",
                    "question": f"Compute ({a}+{b})-{c}.",
                    "answer": str((a + b) - c),
                }
            )
        return mocks


def collect_frontier_states(examples: list[dict[str, str]], cfg: BruteForceLabelConfig) -> list[FrontierState]:
    rng = random.Random(cfg.seed)
    states: list[FrontierState] = []
    global_episode = 0
    for ex in examples:
        for local_ep in range(int(cfg.episodes_per_example)):
            branches = [
                SimBranch(
                    branch_id=f"b{idx}",
                    latent_quality=rng.uniform(0.2, 0.95),
                    score=rng.uniform(0.25, 0.75),
                )
                for idx in range(int(cfg.init_branches))
            ]
            for decision in range(int(cfg.frontier_budget)):
                remaining = int(cfg.frontier_budget) - decision
                active = [b for b in branches if (not b.is_done and not b.is_pruned)]
                if (
                    len(active) >= 2
                    and remaining >= int(cfg.min_remaining_budget)
                    and remaining <= int(cfg.max_remaining_budget)
                    and rng.random() <= float(cfg.state_capture_prob)
                ):
                    selected = sorted(active, key=lambda b: b.branch_id)[: int(cfg.max_branches_per_state)]
                    sid = f"ex{ex['example_id']}_ep{global_episode}_d{decision}"
                    states.append(
                        FrontierState(
                            state_id=sid,
                            example_id=ex["example_id"],
                            question=ex["question"],
                            answer=ex["answer"],
                            source_episode_id=global_episode,
                            decision_index=decision,
                            remaining_budget=remaining,
                            active_branches=_clone_branches(selected),
                        )
                    )
                    if len(states) >= int(cfg.max_frontier_states):
                        return states

                chosen = rng.choice(active) if active else None
                if chosen is None:
                    break
                _expand_branch_once(chosen, rng, cfg)

            global_episode += 1
    return states


def evaluate_state_candidates(
    state: FrontierState,
    cfg: BruteForceLabelConfig,
) -> dict[str, Any]:
    branches = _clone_branches(state.active_branches)
    k = len(branches)
    if k < 2:
        raise ValueError("Need at least 2 active branches for comparison labels")

    remaining_after_first = int(state.remaining_budget) - 1
    mode, allocations = _choose_candidate_allocations(
        remaining_budget_after_first=remaining_after_first,
        n_branches=k,
        exact_mode=bool(cfg.exact_mode),
        cfg=cfg,
        rng=random.Random(_stable_seed(state.state_id, cfg.seed, "alloc")),
    )

    raw_rollouts: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    q_commit = float(_state_utility(_clone_branches(branches)))
    parent_mean_score = sum(float(b.score) for b in branches) / max(1, len(branches))
    for cand_idx, cand in enumerate(branches):
        alloc_means: list[tuple[tuple[int, ...], float, float, float, float]] = []
        for alloc_idx, alloc in enumerate(allocations):
            rep_means: list[float] = []
            paired_deltas_all: list[float] = []
            for rep_idx in range(max(1, int(cfg.target_estimation_repeats))):
                values: list[float] = []
                paired_deltas: list[float] = []
                for sample_idx in range(int(cfg.rollout_samples_per_candidate)):
                    sample_key = _stable_seed(state.state_id, cand.branch_id, alloc_idx, rep_idx, sample_idx, "alloc")
                    if bool(cfg.paired_rollout_comparison):
                        base_cloned = _clone_branches(branches)
                        expand_cloned = _clone_branches(branches)
                        if not expand_cloned[cand_idx].is_done and not expand_cloned[cand_idx].is_pruned:
                            first_seed = _stable_seed(state.state_id, cand.branch_id, rep_idx, sample_idx, "first")
                            _expand_branch_once(expand_cloned[cand_idx], random.Random(first_seed), cfg)
                        base_value = _apply_allocation(base_cloned, alloc, rng_seed=sample_key, cfg=cfg)
                        expand_value = _apply_allocation(expand_cloned, alloc, rng_seed=sample_key, cfg=cfg)
                        value = float(expand_value)
                        paired_delta = float(expand_value - base_value)
                        paired_deltas.append(paired_delta)
                    else:
                        expand_cloned = _clone_branches(branches)
                        if not expand_cloned[cand_idx].is_done and not expand_cloned[cand_idx].is_pruned:
                            first_seed = _stable_seed(state.state_id, cand.branch_id, rep_idx, sample_idx, "first")
                            _expand_branch_once(expand_cloned[cand_idx], random.Random(first_seed), cfg)
                        value = float(_apply_allocation(expand_cloned, alloc, rng_seed=sample_key, cfg=cfg))
                    values.append(value)
                    raw_rollouts.append(
                        {
                            "state_id": state.state_id,
                            "candidate_branch_id": cand.branch_id,
                            "allocation_index": alloc_idx,
                            "allocation_vector": list(alloc),
                            "repeat_index": rep_idx,
                            "sample_index": sample_idx,
                            "post_budget_value": float(value),
                            "paired_delta_expand_minus_no_first_expand": float(paired_deltas[-1]) if paired_deltas else None,
                            "mode": mode,
                        }
                    )
                rep_means.append(sum(values) / max(1, len(values)))
                paired_deltas_all.extend(paired_deltas)
            alloc_mean = sum(rep_means) / max(1, len(rep_means))
            alloc_mean_var = sum((x - alloc_mean) ** 2 for x in rep_means) / max(1, len(rep_means))
            paired_delta_mean = sum(paired_deltas_all) / max(1, len(paired_deltas_all))
            paired_delta_var = sum((x - paired_delta_mean) ** 2 for x in paired_deltas_all) / max(1, len(paired_deltas_all))
            alloc_means.append((alloc, alloc_mean, math.sqrt(max(0.0, alloc_mean_var)), paired_delta_mean, math.sqrt(max(0.0, paired_delta_var))))

        best_alloc, best_mean, best_mean_std, best_paired_delta_mean, best_paired_delta_std = max(alloc_means, key=lambda x: x[1])
        all_means = [x[1] for x in alloc_means]
        mean_all = sum(all_means) / max(1, len(all_means))
        variance = sum((x - mean_all) ** 2 for x in all_means) / max(1, len(all_means))
        target_samples = max(1, int(cfg.rollout_samples_per_candidate) * max(1, int(cfg.target_estimation_repeats)))
        stderr = float(best_mean_std / math.sqrt(max(1, target_samples)))
        reliability = 1.0 / (1.0 + float(cfg.reliability_scale) * max(float(cfg.reliability_floor), stderr))
        candidates.append(
            {
                "branch_id": cand.branch_id,
                "Q_expand": float(best_mean),
                "Q_commit": float(q_commit),
                "A_expand_minus_commit": float(best_mean - q_commit),
                "estimated_value_if_allocate_next": float(best_mean),
                "best_followup_allocation": list(best_alloc),
                "allocation_candidates_evaluated": len(allocations),
                "allocation_value_std": math.sqrt(max(0.0, variance)),
                "target_estimation_repeats": int(max(1, int(cfg.target_estimation_repeats))),
                "target_samples": int(target_samples),
                "target_stderr": float(stderr),
                "target_reliability": float(reliability),
                "best_allocation_mean_std_across_repeats": float(best_mean_std),
                "paired_delta_expand_minus_no_first_expand_mean": float(best_paired_delta_mean),
                "paired_delta_expand_minus_no_first_expand_std": float(best_paired_delta_std),
                "mode": mode,
                "target_provenance": "exact" if mode == "exact" else ("degenerate" if mode == "degenerate" else "approx"),
                "target_fallback_assumptions": "remaining_budget_followup_allocation_search",
                "features_branch_v1": _branch_feature_dict(
                    cand,
                    parent_mean_score=parent_mean_score,
                    remaining_budget=int(state.remaining_budget),
                ),
            }
        )

    winner = max(candidates, key=lambda x: x["estimated_value_if_allocate_next"])
    second_best_value = max(
        [float(c["estimated_value_if_allocate_next"]) for c in candidates if c["branch_id"] != winner["branch_id"]] or [float(winner["estimated_value_if_allocate_next"])]
    )
    best_expand_value = float(winner["estimated_value_if_allocate_next"])
    expand_commit_gap = float(best_expand_value - q_commit)
    if expand_commit_gap <= float(cfg.ambiguity_near_tie_threshold):
        ambiguity_bucket = "near_tie"
    elif expand_commit_gap <= float(cfg.ambiguity_medium_threshold):
        ambiguity_bucket = "medium_margin"
    else:
        ambiguity_bucket = "high_margin"
    best_action = "commit_now" if q_commit >= best_expand_value else f"expand:{winner['branch_id']}"
    for c in candidates:
        alternatives = [x["estimated_value_if_allocate_next"] for x in candidates if x["branch_id"] != c["branch_id"]]
        outside = max(alternatives) if alternatives else c["estimated_value_if_allocate_next"]
        delta_expand_commit = float(c["estimated_value_if_allocate_next"] - q_commit)
        regret_vs_best_action = float(max(best_expand_value, q_commit) - max(float(c["estimated_value_if_allocate_next"]), q_commit))
        c["outside_option_value"] = float(outside)
        c["branch_vs_outside_gap"] = float(c["estimated_value_if_allocate_next"] - outside)
        c["delta_expand_commit"] = delta_expand_commit
        c["regret_vs_best_action"] = regret_vs_best_action
        c["gap_vs_best_expand"] = float(best_expand_value - float(c["estimated_value_if_allocate_next"]))
        c["best_action_overall"] = best_action
        c["best_expand_branch"] = str(winner["branch_id"])
        c["best_expand_value"] = best_expand_value
        c["ambiguity_bucket"] = ambiguity_bucket
        c["defer_candidate"] = bool(ambiguity_bucket in {"near_tie", "medium_margin"})

    pairwise: list[dict[str, Any]] = []
    for i in range(len(candidates)):
        for j in range(i + 1, len(candidates)):
            a = candidates[i]
            b = candidates[j]
            margin = float(a["estimated_value_if_allocate_next"] - b["estimated_value_if_allocate_next"])
            regret_i_over_j = float(max(0.0, float(b["estimated_value_if_allocate_next"]) - float(a["estimated_value_if_allocate_next"])))
            regret_j_over_i = float(max(0.0, float(a["estimated_value_if_allocate_next"]) - float(b["estimated_value_if_allocate_next"])))
            pairwise.append(
                {
                    "branch_i": a["branch_id"],
                    "branch_j": b["branch_id"],
                    "preference": 1 if margin > 0 else 0,
                    "margin": margin,
                    "delta_pair": margin,
                    "regret_if_choose_i": regret_i_over_j,
                    "regret_if_choose_j": regret_j_over_i,
                    "Q_commit": q_commit,
                    "delta_expand_commit_i": float(a["estimated_value_if_allocate_next"] - q_commit),
                    "delta_expand_commit_j": float(b["estimated_value_if_allocate_next"] - q_commit),
                    "pair_ambiguity_bucket": ambiguity_bucket,
                    "defer_candidate": bool(ambiguity_bucket in {"near_tie", "medium_margin"}),
                    "relation": f"{a['branch_id']}>{b['branch_id']}" if margin > 0 else f"{b['branch_id']}>{a['branch_id']}",
                }
            )

    state_value_target = {
        "state_id": state.state_id,
        "example_id": state.example_id,
        "dataset_name": str(cfg.dataset_name),
        "seed": int(cfg.seed),
        "target_mode": str(cfg.target_mode),
        "remaining_budget": int(state.remaining_budget),
        "active_branches": [str(b.branch_id) for b in branches],
        "Q_commit": float(q_commit),
        "Q_expand": {str(c["branch_id"]): float(c["estimated_value_if_allocate_next"]) for c in candidates},
        "A_expand_minus_commit": {str(c["branch_id"]): float(c["delta_expand_commit"]) for c in candidates},
        "best_expand_branch": str(winner["branch_id"]),
        "best_expand_value": best_expand_value,
        "best_action_overall": best_action,
        "best_action_value": float(max(best_expand_value, q_commit)),
        "best_advantage": float(max(0.0, expand_commit_gap)),
        "delta_best_expand_commit": expand_commit_gap,
        "delta_best_two_expands": float(best_expand_value - second_best_value),
        "regret_if_commit": float(max(0.0, best_expand_value - q_commit)),
        "regret_if_expand_best": float(max(0.0, q_commit - best_expand_value)),
        "ambiguity_bucket": ambiguity_bucket,
        "defer_candidate": bool(ambiguity_bucket in {"near_tie", "medium_margin"}),
        "target_provenance": "exact" if mode == "exact" else ("degenerate" if mode == "degenerate" else "approx"),
        "target_is_exact": bool(mode == "exact"),
        "target_is_approximate": bool(mode == "approx"),
        "target_is_mixed": bool(mode == "mixed"),
        "target_reliability_mean": float(sum(float(c.get("target_reliability", 0.0)) for c in candidates) / max(1, len(candidates))),
        "target_stderr_mean": float(sum(float(c.get("target_stderr", 0.0)) for c in candidates) / max(1, len(candidates))),
        "variance_reduction": {
            "paired_rollout_comparison": bool(cfg.paired_rollout_comparison),
            "target_estimation_repeats": int(max(1, int(cfg.target_estimation_repeats))),
        },
        "fallback_assumptions": ["followup_allocation_search", "first_expand_then_rollout"],
    }

    return {
        "state_summary": {
            "state_id": state.state_id,
            "example_id": state.example_id,
            "source_episode_id": state.source_episode_id,
            "decision_index": state.decision_index,
            "remaining_budget": state.remaining_budget,
            "n_active_branches": len(branches),
            "candidate_mode": mode,
            "winner_branch_id": winner["branch_id"],
            "winner_value": winner["estimated_value_if_allocate_next"],
            "Q_commit": float(q_commit),
            "best_expand_branch": str(winner["branch_id"]),
            "best_expand_value": best_expand_value,
            "best_action_overall": best_action,
            "delta_best_expand_commit": expand_commit_gap,
            "ambiguity_bucket": ambiguity_bucket,
            "question_preview": state.question[:180],
        },
        "candidate_labels": candidates,
        "pairwise_labels": pairwise,
        "state_value_target": state_value_target,
        "raw_rollouts": raw_rollouts,
    }


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_manifest(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def config_to_dict(cfg: BruteForceLabelConfig) -> dict[str, Any]:
    return asdict(cfg)
