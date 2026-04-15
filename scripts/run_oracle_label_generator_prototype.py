#!/usr/bin/env python3
"""First real prototype for stop-vs-act oracle-label generation.

This prototype computes real paired ACT-vs-STOP local rollout estimates from
reconstructed pilot manifest snapshots. It is intentionally limited and CPU-only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import random
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.branch_scorer_v3 import SimBranch, expand_branch, maybe_verify
from experiments.stop_vs_act_controller import _clone_active_branches, _local_rollout_value


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _stable_int_seed(*parts: Any) -> int:
    key = "|".join(str(p) for p in parts)
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return int(digest[:16], 16) % (2**31 - 1)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Real local paired-rollout oracle-label prototype generator")
    p.add_argument("--pilot-config", default="configs/stop_vs_act_oracle_label_pilot_v1.json")
    p.add_argument("--selection-config", default="configs/stop_vs_act_oracle_pilot_state_selection_v1.json")
    p.add_argument("--state-manifest", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--max-states", type=int, default=0, help="Optional cap for prototype scale (0 means all rows)")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument(
        "--paired-rollouts",
        type=int,
        default=0,
        help="Optional override for paired rollouts per state (0 uses pilot config value)",
    )
    p.add_argument("--labels-out", default="")
    p.add_argument("--manifest-out", default="")
    return p.parse_args()


def _group_manifest_rows(rows: list[dict[str, Any]]) -> dict[tuple[int, int], list[dict[str, Any]]]:
    grouped: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for row in rows:
        seed = int(row["source_seed"])
        budget = int(row["budget"])
        grouped.setdefault((seed, budget), []).append(row)
    return grouped


def _init_episode_branches(*, rng: random.Random, n_init_branches: int) -> list[SimBranch]:
    return [
        SimBranch(
            branch_id=f"b_{idx}",
            latent_quality=rng.uniform(0.2, 0.95),
            score=rng.uniform(0.25, 0.75),
        )
        for idx in range(n_init_branches)
    ]


def _replay_group_snapshots(
    *,
    source_seed: int,
    budget: int,
    rows: list[dict[str, Any]],
    episodes_per_seed_budget: int,
    n_init_branches: int,
    max_depth: int,
    finish_prob_base: float,
    answer_noise: float,
) -> dict[tuple[int, int, str], list[SimBranch]]:
    needed_keys = {
        (int(r["episode_id"]), int(r["decision_id"]), str(r["current_branch_id"]))
        for r in rows
    }
    captured: dict[tuple[int, int, str], list[SimBranch]] = {}

    rng = random.Random(source_seed)
    for episode_id in range(episodes_per_seed_budget):
        branches = _init_episode_branches(rng=rng, n_init_branches=n_init_branches)

        for decision_id in range(budget):
            for branch in branches:
                branch.branch_age += 1

            active = [b for b in branches if not b.is_done and not b.is_pruned]
            if len(active) <= 1:
                if not active:
                    break
                chosen = active[0]
                expand_branch(chosen, rng, finish_prob_base, answer_noise, max_depth)
                continue

            for branch in active:
                key = (episode_id, decision_id, branch.branch_id)
                if key in needed_keys and key not in captured:
                    captured[key] = _clone_active_branches(active)

            chosen = rng.choice(active)
            expand_branch(chosen, rng, finish_prob_base, answer_noise, max_depth)
            if not chosen.is_done and rng.random() < 0.35:
                maybe_verify(chosen, rng)

            if len(captured) == len(needed_keys):
                return captured

    return captured


def _mean(values: list[float]) -> float:
    return float(sum(values) / max(1, len(values)))


def _std(values: list[float], center: float) -> float:
    if not values:
        return 0.0
    return math.sqrt(sum((x - center) ** 2 for x in values) / max(1, len(values)))


def main() -> None:
    args = parse_args()

    pilot_cfg = _load_json(Path(args.pilot_config))
    selection_cfg = _load_json(Path(args.selection_config))
    manifest_rows = _read_jsonl(Path(args.state_manifest))
    if args.max_states > 0:
        manifest_rows = manifest_rows[: int(args.max_states)]

    if not manifest_rows:
        raise SystemExit("State manifest is empty after applying --max-states")

    teacher = dict(pilot_cfg.get("teacher", {}))
    teacher_mode = str(teacher.get("teacher_mode", ""))
    if teacher_mode != "offline_policy_coupled_oracle_rollout":
        raise SystemExit(f"Unsupported teacher mode for prototype: {teacher_mode}")

    horizon = int(teacher.get("horizon", 0))
    rollout_depth = int(teacher.get("rollout_depth", 0))
    paired_rollouts = int(args.paired_rollouts) if int(args.paired_rollouts) > 0 else int(teacher.get("paired_rollouts_per_state", 0))
    if horizon <= 0 or rollout_depth <= 0 or paired_rollouts <= 0:
        raise SystemExit("Invalid teacher settings: horizon/depth/paired_rollouts must be > 0")

    src_cfg = dict(selection_cfg.get("source_pipeline", {}))
    cand_cfg = dict(selection_cfg.get("candidate_generation", {}))
    episodes_per_seed_budget = int(cand_cfg.get("episodes_per_seed_budget", 0))
    if episodes_per_seed_budget <= 0:
        raise SystemExit("selection config missing positive candidate_generation.episodes_per_seed_budget")

    n_init_branches = int(src_cfg.get("n_init_branches", 0))
    source_max_depth = int(src_cfg.get("max_depth", 0))
    finish_prob_base = float(src_cfg.get("finish_prob_base", 0.0))
    answer_noise = float(src_cfg.get("answer_noise", 0.0))
    if n_init_branches <= 0 or source_max_depth <= 0:
        raise SystemExit("selection config missing positive source_pipeline.n_init_branches/max_depth")

    grouped = _group_manifest_rows(manifest_rows)
    snapshot_lookup: dict[tuple[int, int, int, int, str], list[SimBranch]] = {}

    for (source_seed, budget), rows in grouped.items():
        captured = _replay_group_snapshots(
            source_seed=int(source_seed),
            budget=int(budget),
            rows=rows,
            episodes_per_seed_budget=episodes_per_seed_budget,
            n_init_branches=n_init_branches,
            max_depth=source_max_depth,
            finish_prob_base=finish_prob_base,
            answer_noise=answer_noise,
        )
        for row in rows:
            k3 = (int(row["episode_id"]), int(row["decision_id"]), str(row["current_branch_id"]))
            key = (int(source_seed), int(budget), *k3)
            if k3 not in captured:
                raise SystemExit(f"Failed to reconstruct state snapshot for key={key}")
            snapshot_lookup[key] = captured[k3]

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    labels_path = Path(args.labels_out) if args.labels_out else out_dir / "oracle_stop_vs_act_labels.jsonl"
    manifest_path = Path(args.manifest_out) if args.manifest_out else out_dir / "oracle_label_manifest.json"

    labels_out: list[dict[str, Any]] = []
    for idx, row in enumerate(manifest_rows):
        source_seed = int(row["source_seed"])
        budget = int(row["budget"])
        episode_id = int(row["episode_id"])
        decision_id = int(row["decision_id"])
        branch_id = str(row["current_branch_id"])
        remaining_budget = int(row["remaining_budget"])

        lookup_key = (source_seed, budget, episode_id, decision_id, branch_id)
        active_snapshot = snapshot_lookup[lookup_key]

        act_vals: list[float] = []
        stop_vals: list[float] = []
        gap_vals: list[float] = []

        for rollout_idx in range(paired_rollouts):
            paired_seed = _stable_int_seed(args.seed, row.get("state_id", ""), rollout_idx)
            act_rng = random.Random(paired_seed)
            stop_rng = random.Random(paired_seed)

            act_value = _local_rollout_value(
                active_snapshot=active_snapshot,
                forced_first_branch_id=branch_id,
                skip_first_branch_id=None,
                horizon_steps=horizon,
                rng=act_rng,
                finish_prob_base=finish_prob_base,
                answer_noise=answer_noise,
                max_depth=rollout_depth,
            )
            stop_value = _local_rollout_value(
                active_snapshot=active_snapshot,
                forced_first_branch_id=None,
                skip_first_branch_id=branch_id,
                horizon_steps=horizon,
                rng=stop_rng,
                finish_prob_base=finish_prob_base,
                answer_noise=answer_noise,
                max_depth=rollout_depth,
            )
            act_vals.append(float(act_value))
            stop_vals.append(float(stop_value))
            gap_vals.append(float(act_value - stop_value))

        q_act = _mean(act_vals)
        q_stop = _mean(stop_vals)
        oracle_gap = q_act - q_stop
        oracle_label_act = 1 if oracle_gap > 0 else 0
        gap_std = _std(gap_vals, _mean(gap_vals))
        agreement_rate = _mean([1.0 if ((g > 0) == (oracle_gap > 0)) else 0.0 for g in gap_vals])

        labels_out.append(
            {
                "state_id": str(row["state_id"]),
                "example_id": f"seed{source_seed}_ep{episode_id}",
                "budget": budget,
                "remaining_budget": remaining_budget,
                "current_branch_id": branch_id,
                "q_act": q_act,
                "q_stop": q_stop,
                "oracle_action_gap": oracle_gap,
                "oracle_label_act": oracle_label_act,
                "horizon": horizon,
                "rollout_depth": rollout_depth,
                "teacher_mode": teacher_mode,
                "paired_randomness_used": True,
                "gap_std": gap_std,
                "agreement_rate": agreement_rate,
                "rollout_count": paired_rollouts,
                "generator_impl": "oracle_label_generator_prototype_v1",
                "prototype_mode": True,
            }
        )

        if (idx + 1) % 100 == 0:
            print(f"Processed {idx + 1} / {len(manifest_rows)} states")

    with labels_path.open("w", encoding="utf-8") as f:
        for out_row in labels_out:
            f.write(json.dumps(out_row) + "\n")

    generation_manifest = {
        "pilot_name": pilot_cfg.get("pilot_name"),
        "generator_contract": "oracle_label_generator_interface_v1",
        "generator_impl": "oracle_label_generator_prototype_v1",
        "prototype_real_rollouts": True,
        "full_hpc_production_ready": False,
        "note": "Real paired ACT/STOP rollouts on reconstructed manifest states; limited first prototype.",
        "inputs": {
            "pilot_config": str(Path(args.pilot_config)),
            "selection_config": str(Path(args.selection_config)),
            "state_manifest": str(Path(args.state_manifest)),
            "max_states": int(args.max_states),
            "seed": int(args.seed),
            "paired_rollouts": int(paired_rollouts),
        },
        "teacher": {
            "teacher_mode": teacher_mode,
            "horizon": horizon,
            "rollout_depth": rollout_depth,
            "paired_rollouts_per_state": paired_rollouts,
        },
        "source_reconstruction": {
            "episodes_per_seed_budget": episodes_per_seed_budget,
            "n_init_branches": n_init_branches,
            "source_max_depth": source_max_depth,
            "finish_prob_base": finish_prob_base,
            "answer_noise": answer_noise,
        },
        "outputs": {
            "labels_jsonl": str(labels_path),
            "rows_written": len(labels_out),
        },
    }
    manifest_path.write_text(json.dumps(generation_manifest, indent=2), encoding="utf-8")
    print(json.dumps({"rows_written": len(labels_out), "labels": str(labels_path), "manifest": str(manifest_path)}, indent=2))


if __name__ == "__main__":
    main()
