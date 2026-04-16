#!/usr/bin/env python3
"""Generate auditable branch-comparison labels with brute-force / near-brute-force rollouts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.bruteforce_branch_labels import (
    GENERATOR_VERSION,
    BruteForceLabelConfig,
    append_jsonl,
    collect_frontier_states,
    config_to_dict,
    evaluate_state_candidates,
    load_dataset_examples,
    read_jsonl,
    write_manifest,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Brute-force branch-comparison label generator")
    p.add_argument("--output-dir", default="outputs/branch_label_bruteforce")
    p.add_argument("--run-id", default="")
    p.add_argument("--resume", action="store_true")
    p.add_argument("--max-frontier-states", type=int, default=100)
    p.add_argument("--dataset-name", default="openai/gsm8k")
    p.add_argument("--dataset-split", default="")
    p.add_argument("--dataset-config", default="")
    p.add_argument("--episodes-per-example", type=int, default=2)
    p.add_argument("--frontier-budget", type=int, default=8)
    p.add_argument("--min-remaining-budget", type=int, default=2)
    p.add_argument("--max-remaining-budget", type=int, default=5)
    p.add_argument("--init-branches", type=int, default=4)
    p.add_argument("--max-branches-per-state", type=int, default=5)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--exact-mode", action="store_true")
    p.add_argument("--max-exact-branches", type=int, default=4)
    p.add_argument("--max-exact-remaining-budget", type=int, default=5)
    p.add_argument("--rollout-samples-per-candidate", type=int, default=48)
    p.add_argument("--max-allocation-samples", type=int, default=128)
    p.add_argument("--disable-mock-data-fallback", action="store_true")
    p.add_argument("--progress-every", type=int, default=5)
    return p.parse_args()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            block = f.read(1024 * 1024)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def _now_run_id(seed: int) -> str:
    stamp = time.strftime("%Y%m%d_%H%M%S", time.gmtime())
    return f"bruteforce_{stamp}_s{seed}"


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Brute-force branch label generator report",
        "",
        f"- Generator: `{GENERATOR_VERSION}`",
        f"- Run ID: `{payload['run_id']}`",
        f"- Started (UTC epoch): `{payload['started_at_epoch']}`",
        f"- Elapsed sec: `{payload['elapsed_sec']:.2f}`",
        f"- States planned: `{payload['states_planned']}`",
        f"- States completed: `{payload['states_completed']}`",
        f"- Candidate rows: `{payload['candidate_rows']}`",
        f"- Pairwise rows: `{payload['pairwise_rows']}`",
        f"- Raw rollout rows: `{payload['raw_rollout_rows']}`",
        f"- Mode counts: `{payload['mode_counts']}`",
        "",
        "## Safe interpretation",
        "",
        "These labels are expensive simulated continuation estimates for fixed-budget next-step branch allocation.",
        "They are supervision targets, not exact global-oracle truth on real model trajectories.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    run_id = args.run_id.strip() or _now_run_id(args.seed)
    out_dir = Path(args.output_dir) / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    labels_candidates_path = out_dir / "candidate_labels.jsonl"
    labels_pairwise_path = out_dir / "pairwise_labels.jsonl"
    labels_state_summary_path = out_dir / "state_summaries.jsonl"
    raw_rollouts_path = out_dir / "raw_rollouts.jsonl"
    progress_path = out_dir / "progress.json"
    manifest_path = out_dir / "manifest.json"
    report_path = out_dir / "report.md"

    cfg = BruteForceLabelConfig(
        dataset_name=str(args.dataset_name),
        dataset_split=(str(args.dataset_split) or None),
        dataset_config=(str(args.dataset_config) or None),
        seed=int(args.seed),
        max_frontier_states=int(args.max_frontier_states),
        episodes_per_example=int(args.episodes_per_example),
        init_branches=int(args.init_branches),
        max_branches_per_state=int(args.max_branches_per_state),
        frontier_budget=int(args.frontier_budget),
        min_remaining_budget=int(args.min_remaining_budget),
        max_remaining_budget=int(args.max_remaining_budget),
        exact_mode=bool(args.exact_mode),
        max_exact_branches=int(args.max_exact_branches),
        max_exact_remaining_budget=int(args.max_exact_remaining_budget),
        rollout_samples_per_candidate=int(args.rollout_samples_per_candidate),
        max_allocation_samples=int(args.max_allocation_samples),
        allow_mock_data=not bool(args.disable_mock_data_fallback),
    )

    start_time = time.time()
    examples = load_dataset_examples(cfg)
    states = collect_frontier_states(examples, cfg)

    completed_state_ids = set()
    if args.resume and labels_state_summary_path.exists():
        for row in read_jsonl(labels_state_summary_path):
            completed_state_ids.add(str(row.get("state_id", "")))

    mode_counts: dict[str, int] = {"exact": 0, "approx": 0, "degenerate": 0}
    candidate_rows = 0
    pairwise_rows = 0
    raw_rollout_rows = 0

    for idx, state in enumerate(states):
        if state.state_id in completed_state_ids:
            continue

        result = evaluate_state_candidates(state, cfg)
        state_summary = dict(result["state_summary"])
        state_summary["dataset_name"] = cfg.dataset_name
        append_jsonl(labels_state_summary_path, state_summary)
        for row in result["candidate_labels"]:
            out_row = dict(row)
            out_row.update(
                {
                    "state_id": state.state_id,
                    "example_id": state.example_id,
                    "remaining_budget": state.remaining_budget,
                    "dataset_name": cfg.dataset_name,
                }
            )
            append_jsonl(labels_candidates_path, out_row)
            candidate_rows += 1
        for row in result["pairwise_labels"]:
            out_row = dict(row)
            out_row.update(
                {
                    "state_id": state.state_id,
                    "example_id": state.example_id,
                    "remaining_budget": state.remaining_budget,
                    "dataset_name": cfg.dataset_name,
                }
            )
            append_jsonl(labels_pairwise_path, out_row)
            pairwise_rows += 1
        for row in result["raw_rollouts"]:
            append_jsonl(raw_rollouts_path, row)
            raw_rollout_rows += 1

        mode = str(state_summary.get("candidate_mode", "approx"))
        mode_counts[mode] = mode_counts.get(mode, 0) + 1
        completed_state_ids.add(state.state_id)

        if (idx + 1) % max(1, int(args.progress_every)) == 0:
            progress = {
                "generator": GENERATOR_VERSION,
                "run_id": run_id,
                "states_planned": len(states),
                "states_completed": len(completed_state_ids),
                "candidate_rows": candidate_rows,
                "pairwise_rows": pairwise_rows,
                "raw_rollout_rows": raw_rollout_rows,
                "elapsed_sec": time.time() - start_time,
            }
            progress_path.write_text(json.dumps(progress, indent=2), encoding="utf-8")

    progress = {
        "generator": GENERATOR_VERSION,
        "run_id": run_id,
        "states_planned": len(states),
        "states_completed": len(completed_state_ids),
        "candidate_rows": candidate_rows,
        "pairwise_rows": pairwise_rows,
        "raw_rollout_rows": raw_rollout_rows,
        "elapsed_sec": time.time() - start_time,
        "complete": len(completed_state_ids) == len(states),
    }
    progress_path.write_text(json.dumps(progress, indent=2), encoding="utf-8")

    manifest = {
        "generator": GENERATOR_VERSION,
        "run_id": run_id,
        "started_at_epoch": start_time,
        "elapsed_sec": time.time() - start_time,
        "config": config_to_dict(cfg),
        "inputs": {
            "dataset_name": cfg.dataset_name,
            "dataset_split": cfg.dataset_split,
            "dataset_config": cfg.dataset_config,
            "example_count": len(examples),
            "state_count": len(states),
            "resume": bool(args.resume),
        },
        "outputs": {
            "state_summaries": str(labels_state_summary_path),
            "candidate_labels": str(labels_candidates_path),
            "pairwise_labels": str(labels_pairwise_path),
            "raw_rollouts": str(raw_rollouts_path),
            "progress": str(progress_path),
            "report": str(report_path),
        },
        "counts": {
            "states_planned": len(states),
            "states_completed": len(completed_state_ids),
            "candidate_rows": candidate_rows,
            "pairwise_rows": pairwise_rows,
            "raw_rollout_rows": raw_rollout_rows,
            "mode_counts": mode_counts,
        },
        "checksums": {
            "state_summaries_sha256": _sha256(labels_state_summary_path) if labels_state_summary_path.exists() else None,
            "candidate_labels_sha256": _sha256(labels_candidates_path) if labels_candidates_path.exists() else None,
            "pairwise_labels_sha256": _sha256(labels_pairwise_path) if labels_pairwise_path.exists() else None,
            "raw_rollouts_sha256": _sha256(raw_rollouts_path) if raw_rollouts_path.exists() else None,
        },
    }
    write_manifest(manifest_path, manifest)

    report_payload = {
        "run_id": run_id,
        "started_at_epoch": start_time,
        "elapsed_sec": time.time() - start_time,
        "states_planned": len(states),
        "states_completed": len(completed_state_ids),
        "candidate_rows": candidate_rows,
        "pairwise_rows": pairwise_rows,
        "raw_rollout_rows": raw_rollout_rows,
        "mode_counts": mode_counts,
    }
    _write_report(report_path, report_payload)

    print(json.dumps({"run_id": run_id, "output_dir": str(out_dir), "progress": progress}, indent=2))


if __name__ == "__main__":
    main()
