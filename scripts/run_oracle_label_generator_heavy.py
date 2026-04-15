#!/usr/bin/env python3
"""Production-leaning heavy oracle-label generator path for shard-scale pilot runs.

This path keeps the same ACT-vs-STOP semantics and output contract as the real
prototype, but adds operational features needed for sharded HPC execution:
- deterministic shard-friendly processing order,
- resumable output mode,
- per-state error capture and partial-failure policy controls,
- per-shard provenance + progress metadata,
- contract-compliant row/manifest outputs for downstream merge + validation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import random
import sys
import time
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
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(path)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            block = f.read(1024 * 1024)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def _stable_int_seed(*parts: Any) -> int:
    key = "|".join(str(p) for p in parts)
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return int(digest[:16], 16) % (2**31 - 1)


def _mean(values: list[float]) -> float:
    return float(sum(values) / max(1, len(values)))


def _std(values: list[float], center: float) -> float:
    if not values:
        return 0.0
    return math.sqrt(sum((x - center) ** 2 for x in values) / max(1, len(values)))


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
    needed_keys = {(int(r["episode_id"]), int(r["decision_id"]), str(r["current_branch_id"])) for r in rows}
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


def _manifest_group_index(rows: list[dict[str, Any]]) -> dict[tuple[int, int], list[dict[str, Any]]]:
    grouped: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for row in rows:
        key = (int(row["source_seed"]), int(row["budget"]))
        grouped.setdefault(key, []).append(row)
    return grouped


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Heavy-path oracle-label generator for shard-scale pilot runs")
    p.add_argument("--pilot-config", default="configs/stop_vs_act_oracle_label_pilot_v1.json")
    p.add_argument("--selection-config", default="configs/stop_vs_act_oracle_pilot_state_selection_v1.json")
    p.add_argument("--state-manifest", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--labels-out", default="")
    p.add_argument("--manifest-out", default="")
    p.add_argument("--progress-out", default="")
    p.add_argument("--state-errors-out", default="")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--paired-rollouts", type=int, default=0)
    p.add_argument("--max-states", type=int, default=0)
    p.add_argument("--resume", action="store_true")
    p.add_argument("--progress-every", type=int, default=50)
    p.add_argument("--continue-on-state-error", action="store_true")
    p.add_argument("--max-state-errors", type=int, default=0)
    p.add_argument("--allow-partial-output", action="store_true")
    p.add_argument("--shard-name", default="")
    p.add_argument("--shard-id", type=int, default=-1)
    p.add_argument("--split-manifest", default="")
    p.add_argument("--expected-state-count", type=int, default=0)
    return p.parse_args()


def _validate_shard_spec(*, split_manifest_path: Path, shard_name: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    payload = _load_json(split_manifest_path)
    shards = payload.get("shards", [])
    match = None
    for shard in shards:
        if str(shard.get("shard_name", "")) == shard_name:
            match = shard
            break
    if match is None:
        raise SystemExit(f"Shard name '{shard_name}' not found in split manifest: {split_manifest_path}")

    expected_state_ids = [str(x) for x in match.get("state_ids", [])]
    actual_state_ids = [str(r.get("state_id", "")) for r in rows]
    if expected_state_ids != actual_state_ids:
        raise SystemExit(
            f"Shard state_id mismatch for shard={shard_name}: expected {len(expected_state_ids)} ids from split manifest, got {len(actual_state_ids)}"
        )
    return {
        "split_manifest": str(split_manifest_path.resolve()),
        "split_manifest_sha256": _sha256_file(split_manifest_path),
        "shard_spec": match,
    }


def main() -> None:
    args = _parse_args()

    pilot_cfg_path = Path(args.pilot_config)
    selection_cfg_path = Path(args.selection_config)
    state_manifest_path = Path(args.state_manifest)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    labels_path = Path(args.labels_out) if args.labels_out else out_dir / "oracle_stop_vs_act_labels.jsonl"
    manifest_path = Path(args.manifest_out) if args.manifest_out else out_dir / "oracle_label_manifest.json"
    progress_path = Path(args.progress_out) if args.progress_out else out_dir / "oracle_label_progress.json"
    state_errors_path = Path(args.state_errors_out) if args.state_errors_out else out_dir / "oracle_label_state_errors.jsonl"
    if not state_errors_path.exists():
        state_errors_path.parent.mkdir(parents=True, exist_ok=True)
        state_errors_path.write_text("", encoding="utf-8")

    pilot_cfg = _load_json(pilot_cfg_path)
    selection_cfg = _load_json(selection_cfg_path)
    manifest_rows = _read_jsonl(state_manifest_path)

    if args.max_states > 0:
        manifest_rows = manifest_rows[: int(args.max_states)]
    if not manifest_rows:
        raise SystemExit("State manifest is empty after applying --max-states")

    if args.expected_state_count > 0 and len(manifest_rows) != int(args.expected_state_count):
        raise SystemExit(
            f"Expected {int(args.expected_state_count)} rows in state manifest, got {len(manifest_rows)}"
        )

    teacher = dict(pilot_cfg.get("teacher", {}))
    teacher_mode = str(teacher.get("teacher_mode", ""))
    if teacher_mode != "offline_policy_coupled_oracle_rollout":
        raise SystemExit(f"Unsupported teacher mode for heavy path: {teacher_mode}")

    horizon = int(teacher.get("horizon", 0))
    rollout_depth = int(teacher.get("rollout_depth", 0))
    paired_rollouts = int(args.paired_rollouts) if int(args.paired_rollouts) > 0 else int(teacher.get("paired_rollouts_per_state", 0))
    if horizon <= 0 or rollout_depth <= 0 or paired_rollouts <= 0:
        raise SystemExit("Invalid teacher settings: horizon/depth/paired_rollouts must be > 0")

    src_cfg = dict(selection_cfg.get("source_pipeline", {}))
    cand_cfg = dict(selection_cfg.get("candidate_generation", {}))
    episodes_per_seed_budget = int(cand_cfg.get("episodes_per_seed_budget", 0))
    n_init_branches = int(src_cfg.get("n_init_branches", 0))
    source_max_depth = int(src_cfg.get("max_depth", 0))
    finish_prob_base = float(src_cfg.get("finish_prob_base", 0.0))
    answer_noise = float(src_cfg.get("answer_noise", 0.0))

    if episodes_per_seed_budget <= 0 or n_init_branches <= 0 or source_max_depth <= 0:
        raise SystemExit("selection config missing required positive source settings")

    shard_provenance: dict[str, Any] = {}
    if args.split_manifest:
        if not args.shard_name:
            raise SystemExit("--split-manifest requires --shard-name")
        shard_provenance = _validate_shard_spec(
            split_manifest_path=Path(args.split_manifest), shard_name=str(args.shard_name), rows=manifest_rows
        )

    grouped_manifest = _manifest_group_index(manifest_rows)
    group_snapshot_cache: dict[tuple[int, int], dict[tuple[int, int, str], list[SimBranch]]] = {}

    start_ts = time.time()
    resume_skips = 0
    processed = 0
    failures = 0
    failure_records: list[dict[str, Any]] = []

    prior_rows: list[dict[str, Any]] = []
    completed_state_ids: set[str] = set()
    if args.resume and labels_path.exists():
        prior_rows = _read_jsonl(labels_path)
        for row in prior_rows:
            state_id = str(row.get("state_id", ""))
            if state_id:
                completed_state_ids.add(state_id)

    ordered_state_ids = [str(r["state_id"]) for r in manifest_rows]
    if len(set(ordered_state_ids)) != len(ordered_state_ids):
        raise SystemExit("Duplicate state_id entries found in state manifest; cannot safely continue")

    def write_progress(last_state_id: str) -> None:
        payload = {
            "generator_impl": "oracle_label_generator_heavy_v1",
            "state_manifest": str(state_manifest_path),
            "state_manifest_sha256": _sha256_file(state_manifest_path),
            "rows_total": len(manifest_rows),
            "rows_completed": len(completed_state_ids),
            "rows_processed_this_run": processed,
            "rows_skipped_by_resume": resume_skips,
            "state_errors": failures,
            "last_state_id": last_state_id,
            "elapsed_sec": time.time() - start_ts,
            "resume": bool(args.resume),
            "shard_name": str(args.shard_name),
            "shard_id": int(args.shard_id),
            "partial_output_allowed": bool(args.allow_partial_output),
            "continue_on_state_error": bool(args.continue_on_state_error),
        }
        _write_json_atomic(progress_path, payload)

    max_state_errors = int(args.max_state_errors)
    if args.continue_on_state_error and max_state_errors < 0:
        raise SystemExit("--max-state-errors must be >= 0")

    for idx, row in enumerate(manifest_rows):
        state_id = str(row["state_id"])
        if state_id in completed_state_ids:
            resume_skips += 1
            if (idx + 1) % max(1, int(args.progress_every)) == 0:
                write_progress(state_id)
            continue

        source_seed = int(row["source_seed"])
        budget = int(row["budget"])
        episode_id = int(row["episode_id"])
        decision_id = int(row["decision_id"])
        branch_id = str(row["current_branch_id"])
        remaining_budget = int(row["remaining_budget"])

        group_key = (source_seed, budget)
        try:
            if group_key not in group_snapshot_cache:
                captured = _replay_group_snapshots(
                    source_seed=source_seed,
                    budget=budget,
                    rows=grouped_manifest[group_key],
                    episodes_per_seed_budget=episodes_per_seed_budget,
                    n_init_branches=n_init_branches,
                    max_depth=source_max_depth,
                    finish_prob_base=finish_prob_base,
                    answer_noise=answer_noise,
                )
                group_snapshot_cache[group_key] = captured

            captured = group_snapshot_cache[group_key]
            k3 = (episode_id, decision_id, branch_id)
            if k3 not in captured:
                raise RuntimeError(f"Failed to reconstruct state snapshot for key={group_key + k3}")
            active_snapshot = captured[k3]

            act_vals: list[float] = []
            stop_vals: list[float] = []
            gap_vals: list[float] = []
            for rollout_idx in range(paired_rollouts):
                paired_seed = _stable_int_seed(args.seed, state_id, rollout_idx)
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

            out_row = {
                "state_id": state_id,
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
                "gap_std": _std(gap_vals, _mean(gap_vals)),
                "agreement_rate": _mean([1.0 if ((g > 0) == (oracle_gap > 0)) else 0.0 for g in gap_vals]),
                "rollout_count": paired_rollouts,
                "generator_impl": "oracle_label_generator_heavy_v1",
                "prototype_mode": False,
                "shard_name": str(args.shard_name),
                "shard_id": int(args.shard_id),
            }
            _append_jsonl(labels_path, out_row)
            completed_state_ids.add(state_id)
            processed += 1

        except Exception as exc:  # noqa: BLE001 - row-level fault capture is intentional in heavy path
            failures += 1
            err = {
                "state_id": state_id,
                "source_seed": source_seed,
                "budget": budget,
                "episode_id": episode_id,
                "decision_id": decision_id,
                "current_branch_id": branch_id,
                "error": repr(exc),
            }
            failure_records.append(err)
            _append_jsonl(state_errors_path, err)

            if not args.continue_on_state_error:
                write_progress(state_id)
                raise
            if max_state_errors and failures > max_state_errors:
                write_progress(state_id)
                raise SystemExit(
                    f"State errors exceeded --max-state-errors ({max_state_errors}); latest state_id={state_id}"
                )

        if (idx + 1) % max(1, int(args.progress_every)) == 0:
            write_progress(state_id)

    write_progress(ordered_state_ids[-1])

    rows_written = len(_read_jsonl(labels_path))
    expected_rows = len(manifest_rows)
    complete = rows_written == expected_rows

    run_manifest = {
        "pilot_name": pilot_cfg.get("pilot_name"),
        "generator_contract": "oracle_label_generator_interface_v1",
        "generator_impl": "oracle_label_generator_heavy_v1",
        "prototype_real_rollouts": False,
        "heavy_path": True,
        "full_hpc_production_ready": False,
        "note": "Production-leaning shard-scale heavy path; full pilot completion must be established by real HPC run artifacts.",
        "inputs": {
            "pilot_config": str(pilot_cfg_path),
            "selection_config": str(selection_cfg_path),
            "state_manifest": str(state_manifest_path),
            "state_manifest_sha256": _sha256_file(state_manifest_path),
            "max_states": int(args.max_states),
            "seed": int(args.seed),
            "paired_rollouts": int(paired_rollouts),
            "resume": bool(args.resume),
            "expected_state_count": int(args.expected_state_count),
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
        "shard": {
            "shard_name": str(args.shard_name),
            "shard_id": int(args.shard_id),
            "split_manifest": str(args.split_manifest),
            "split_manifest_verified": bool(shard_provenance),
            "split_manifest_provenance": shard_provenance,
        },
        "outputs": {
            "labels_jsonl": str(labels_path),
            "rows_written": rows_written,
            "rows_expected_from_manifest": expected_rows,
            "complete": complete,
            "progress_json": str(progress_path),
            "state_errors_jsonl": str(state_errors_path),
        },
        "run_stats": {
            "rows_processed_this_run": processed,
            "rows_skipped_by_resume": resume_skips,
            "state_errors": failures,
            "elapsed_sec": time.time() - start_ts,
        },
        "partial_failures": failure_records,
    }
    _write_json_atomic(manifest_path, run_manifest)

    print(
        json.dumps(
            {
                "rows_written": rows_written,
                "rows_expected": expected_rows,
                "complete": complete,
                "state_errors": failures,
                "labels": str(labels_path),
                "manifest": str(manifest_path),
                "progress": str(progress_path),
            },
            indent=2,
        )
    )

    if failures > 0 and not args.allow_partial_output:
        raise SystemExit("State errors were recorded; rerun/resume after fixing or pass --allow-partial-output for debug only")
    if not complete and not args.allow_partial_output:
        raise SystemExit("Generator output is incomplete for manifest rows")


if __name__ == "__main__":
    main()
