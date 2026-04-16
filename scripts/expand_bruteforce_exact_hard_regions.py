#!/usr/bin/env python3
"""Targeted exact relabeling for mined hard regions with resume + manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.bruteforce_branch_labels import (  # noqa: E402
    BruteForceLabelConfig,
    collect_frontier_states,
    evaluate_state_candidates,
    load_dataset_examples,
)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def _pair_key(state_id: str, bi: str, bj: str) -> tuple[str, str, str]:
    a, b = sorted([str(bi), str(bj)])
    return (str(state_id), a, b)


def _sha(path: Path) -> str | None:
    if not path.exists():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(1024 * 1024)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Expand exact labels for mined hard regions")
    p.add_argument("--base-labels-dir", required=True)
    p.add_argument("--mined-candidates-jsonl", required=True)
    p.add_argument("--output-dir", default="outputs/branch_label_bruteforce_targets")
    p.add_argument("--run-id", required=True)
    p.add_argument("--max-target-pairs", type=int, default=120)
    p.add_argument("--resume", action="store_true")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    base_dir = Path(args.base_labels_dir)
    mined_rows = _read_jsonl(Path(args.mined_candidates_jsonl))
    out_dir = Path(args.output_dir) / args.run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    exact_candidates_path = out_dir / "exact_candidate_labels.jsonl"
    exact_pairs_path = out_dir / "exact_pairwise_labels.jsonl"
    progress_path = out_dir / "progress.json"
    manifest_path = out_dir / "manifest.json"

    selected = mined_rows[: max(1, int(args.max_target_pairs))]
    wanted_states = sorted({str(r["state_id"]) for r in selected})
    wanted_pair_keys = {_pair_key(str(r["state_id"]), str(r["branch_i"]), str(r["branch_j"])) for r in selected}
    mined_by_pair = {
        _pair_key(str(r["state_id"]), str(r["branch_i"]), str(r["branch_j"])): r
        for r in selected
    }

    completed_states: set[str] = set()
    if args.resume and progress_path.exists():
        payload = json.loads(progress_path.read_text(encoding="utf-8"))
        completed_states = set(payload.get("completed_states", []))

    base_manifest = json.loads((base_dir / "manifest.json").read_text(encoding="utf-8"))
    cfg_src = base_manifest["config"]
    exact_cfg = BruteForceLabelConfig(
        dataset_name=str(cfg_src["dataset_name"]),
        dataset_split=cfg_src.get("dataset_split"),
        dataset_config=cfg_src.get("dataset_config"),
        seed=int(cfg_src["seed"]),
        max_frontier_states=int(cfg_src["max_frontier_states"]),
        episodes_per_example=int(cfg_src["episodes_per_example"]),
        init_branches=int(cfg_src["init_branches"]),
        max_branches_per_state=int(cfg_src["max_branches_per_state"]),
        frontier_budget=int(cfg_src["frontier_budget"]),
        min_remaining_budget=int(cfg_src["min_remaining_budget"]),
        max_remaining_budget=int(cfg_src["max_remaining_budget"]),
        state_capture_prob=float(cfg_src["state_capture_prob"]),
        finish_prob_base=float(cfg_src["finish_prob_base"]),
        answer_noise=float(cfg_src["answer_noise"]),
        max_depth=int(cfg_src["max_depth"]),
        exact_mode=True,
        max_exact_branches=int(cfg_src.get("max_exact_branches", 6)),
        max_exact_remaining_budget=int(cfg_src.get("max_exact_remaining_budget", 8)),
        rollout_samples_per_candidate=int(cfg_src["rollout_samples_per_candidate"]),
        max_allocation_samples=int(cfg_src["max_allocation_samples"]),
        include_verify_actions=bool(cfg_src["include_verify_actions"]),
        verify_prob=float(cfg_src["verify_prob"]),
        allow_mock_data=bool(cfg_src.get("allow_mock_data", True)),
    )

    examples = load_dataset_examples(exact_cfg)
    states = collect_frontier_states(examples, exact_cfg)
    state_map = {s.state_id: s for s in states}

    emitted_pairs = 0
    replaced_pairs = 0
    emitted_candidates = 0
    for sid in wanted_states:
        if sid in completed_states:
            continue
        state = state_map.get(sid)
        if state is None:
            completed_states.add(sid)
            continue
        result = evaluate_state_candidates(state, exact_cfg)

        for crow in result["candidate_labels"]:
            out = dict(crow)
            out.update(
                {
                    "state_id": sid,
                    "example_id": state.example_id,
                    "dataset_name": exact_cfg.dataset_name,
                    "remaining_budget": state.remaining_budget,
                    "label_source": "exact_hard_region_runner",
                }
            )
            _append_jsonl(exact_candidates_path, out)
            emitted_candidates += 1

        for prow in result["pairwise_labels"]:
            pkey = _pair_key(sid, str(prow["branch_i"]), str(prow["branch_j"]))
            if pkey not in wanted_pair_keys:
                continue
            mined = mined_by_pair.get(pkey, {})
            out = dict(prow)
            out.update(
                {
                    "state_id": sid,
                    "example_id": state.example_id,
                    "dataset_name": exact_cfg.dataset_name,
                    "remaining_budget": state.remaining_budget,
                    "mined_reasons": mined.get("mined_reasons", []),
                    "original_regime": mined.get("original_regime", "all_pairs_approx"),
                    "replaced_approx_label": True,
                    "pair_type": mined.get("pair_type", "generic"),
                    "label_source": "exact_hard_region_runner",
                }
            )
            _append_jsonl(exact_pairs_path, out)
            emitted_pairs += 1
            replaced_pairs += 1

        completed_states.add(sid)
        progress_path.write_text(
            json.dumps(
                {
                    "run_id": args.run_id,
                    "completed_states": sorted(completed_states),
                    "target_state_count": len(wanted_states),
                    "emitted_pairs": emitted_pairs,
                    "emitted_candidates": emitted_candidates,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    manifest = {
        "run_id": args.run_id,
        "base_labels_dir": str(base_dir),
        "mined_candidates_jsonl": str(args.mined_candidates_jsonl),
        "target_pairs": len(wanted_pair_keys),
        "target_states": len(wanted_states),
        "exact_emitted_pairs": emitted_pairs,
        "exact_emitted_candidates": emitted_candidates,
        "replaced_approx_pairs": replaced_pairs,
        "outputs": {
            "exact_pairwise_labels": str(exact_pairs_path),
            "exact_candidate_labels": str(exact_candidates_path),
            "progress": str(progress_path),
        },
        "checksums": {
            "exact_pairwise_labels": _sha(exact_pairs_path),
            "exact_candidate_labels": _sha(exact_candidates_path),
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "output_dir": str(out_dir),
                "exact_emitted_pairs": emitted_pairs,
                "replaced_approx_pairs": replaced_pairs,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
