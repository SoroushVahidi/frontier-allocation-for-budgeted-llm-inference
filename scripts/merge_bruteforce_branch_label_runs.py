#!/usr/bin/env python3
"""Merge multiple brute-force branch-label runs into one canonical corpus with provenance."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from collections import Counter, defaultdict
from typing import Any


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            block = f.read(1024 * 1024)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Merge brute-force branch-label run directories")
    p.add_argument("--runs-root", default="outputs/branch_label_bruteforce")
    p.add_argument("--run-id-prefix", default="")
    p.add_argument("--run-ids-file", default="")
    p.add_argument("--output-dir", default="outputs/branch_label_bruteforce_merged")
    p.add_argument("--run-id", required=True)
    p.add_argument("--near-tie-margin", type=float, default=0.03)
    return p.parse_args()


def _collect_run_ids(args: argparse.Namespace, runs_root: Path) -> list[str]:
    if args.run_ids_file:
        return [
            ln.strip() for ln in Path(args.run_ids_file).read_text(encoding="utf-8").splitlines() if ln.strip()
        ]
    if args.run_id_prefix:
        return sorted(p.name for p in runs_root.iterdir() if p.is_dir() and p.name.startswith(args.run_id_prefix))
    raise ValueError("Either --run-ids-file or --run-id-prefix is required")


def main() -> None:
    args = parse_args()
    runs_root = Path(args.runs_root)
    run_ids = _collect_run_ids(args, runs_root)

    out_dir = Path(args.output_dir) / args.run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    cand_out = out_dir / "candidate_labels.jsonl"
    pair_out = out_dir / "pairwise_labels.jsonl"
    state_out = out_dir / "state_summaries.jsonl"
    raw_out = out_dir / "raw_rollouts.jsonl"

    for p in (cand_out, pair_out, state_out, raw_out):
        if p.exists():
            p.unlink()

    merged_counts = Counter()
    dataset_counts = Counter()
    budget_counts = Counter()
    mode_counts = Counter()
    near_tie_counts = Counter()
    gap_abs_by_dataset: dict[str, list[float]] = defaultdict(list)
    margin_abs_by_dataset: dict[str, list[float]] = defaultdict(list)

    included_runs: list[dict[str, Any]] = []

    for rid in run_ids:
        run_dir = runs_root / rid
        manifest_path = run_dir / "manifest.json"
        if not manifest_path.exists():
            raise FileNotFoundError(f"Missing manifest.json in {run_dir}")
        manifest = _read_json(manifest_path)
        cfg = manifest.get("config", {})

        seed = int(cfg.get("seed", -1))
        dataset_name = str(cfg.get("dataset_name", "unknown"))
        exact_mode = bool(cfg.get("exact_mode", False))

        candidates = _read_jsonl(run_dir / "candidate_labels.jsonl")
        pairwise = _read_jsonl(run_dir / "pairwise_labels.jsonl")
        states = _read_jsonl(run_dir / "state_summaries.jsonl")
        raw_rollouts = _read_jsonl(run_dir / "raw_rollouts.jsonl")

        for row in states:
            out = dict(row)
            out["source_run_id"] = rid
            out["source_seed"] = seed
            out["source_exact_mode_flag"] = exact_mode
            _append_jsonl(state_out, out)
            merged_counts["state_rows"] += 1

        for row in candidates:
            out = dict(row)
            out["source_run_id"] = rid
            out["source_seed"] = seed
            out["source_exact_mode_flag"] = exact_mode
            out["source_dataset_name"] = dataset_name
            _append_jsonl(cand_out, out)
            merged_counts["candidate_rows"] += 1
            dataset_counts[dataset_name] += 1
            budget_counts[str(int(out.get("remaining_budget", 0)))] += 1
            mode_counts[str(out.get("mode", "unknown"))] += 1
            gap = abs(float(out.get("branch_vs_outside_gap", 0.0)))
            gap_abs_by_dataset[dataset_name].append(gap)

        for row in pairwise:
            out = dict(row)
            out["source_run_id"] = rid
            out["source_seed"] = seed
            out["source_exact_mode_flag"] = exact_mode
            out["source_dataset_name"] = dataset_name
            _append_jsonl(pair_out, out)
            merged_counts["pairwise_rows"] += 1
            m = abs(float(out.get("margin", 0.0)))
            margin_abs_by_dataset[dataset_name].append(m)
            if m <= float(args.near_tie_margin):
                near_tie_counts[dataset_name] += 1
            near_tie_counts["__all__"] += int(m <= float(args.near_tie_margin))

        for row in raw_rollouts:
            out = dict(row)
            out["source_run_id"] = rid
            out["source_seed"] = seed
            out["source_exact_mode_flag"] = exact_mode
            out["source_dataset_name"] = dataset_name
            _append_jsonl(raw_out, out)
            merged_counts["raw_rollout_rows"] += 1

        included_runs.append(
            {
                "run_id": rid,
                "dataset_name": dataset_name,
                "seed": seed,
                "exact_mode": exact_mode,
                "counts": manifest.get("counts", {}),
                "manifest_sha256": _sha256(manifest_path),
            }
        )

    def _quantiles(vals: list[float]) -> dict[str, float]:
        if not vals:
            return {"p50": 0.0, "p90": 0.0, "p95": 0.0}
        s = sorted(vals)
        def q(p: float) -> float:
            idx = min(len(s) - 1, int(round((len(s) - 1) * p)))
            return float(s[idx])
        return {"p50": q(0.5), "p90": q(0.9), "p95": q(0.95)}

    summary = {
        "run_id": args.run_id,
        "source_runs": included_runs,
        "counts": dict(merged_counts),
        "candidate_rows_by_dataset": dict(dataset_counts),
        "candidate_rows_by_budget": dict(budget_counts),
        "candidate_rows_by_mode": dict(mode_counts),
        "near_tie_margin": float(args.near_tie_margin),
        "near_tie_pairwise_by_dataset": {
            ds: {
                "near_tie_rows": int(near_tie_counts.get(ds, 0)),
                "total_rows": int(len(margin_abs_by_dataset.get(ds, []))),
                "near_tie_rate": float(near_tie_counts.get(ds, 0) / max(1, len(margin_abs_by_dataset.get(ds, [])))),
            }
            for ds in sorted(margin_abs_by_dataset.keys())
        },
        "near_tie_pairwise_all": {
            "near_tie_rows": int(near_tie_counts.get("__all__", 0)),
            "total_rows": int(sum(len(v) for v in margin_abs_by_dataset.values())),
            "near_tie_rate": float(near_tie_counts.get("__all__", 0) / max(1, sum(len(v) for v in margin_abs_by_dataset.values()))),
        },
        "outside_option_gap_abs_distribution_by_dataset": {ds: _quantiles(v) for ds, v in gap_abs_by_dataset.items()},
        "pairwise_margin_abs_distribution_by_dataset": {ds: _quantiles(v) for ds, v in margin_abs_by_dataset.items()},
        "checksums": {
            "candidate_labels_sha256": _sha256(cand_out),
            "pairwise_labels_sha256": _sha256(pair_out),
            "state_summaries_sha256": _sha256(state_out),
            "raw_rollouts_sha256": _sha256(raw_out),
        },
    }

    summary_path = out_dir / "merged_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    lines = [
        "# Merged brute-force branch-label corpus",
        "",
        f"- Run ID: `{args.run_id}`",
        f"- Source runs: `{len(included_runs)}`",
        f"- States: `{merged_counts['state_rows']}`",
        f"- Candidate rows: `{merged_counts['candidate_rows']}`",
        f"- Pairwise rows: `{merged_counts['pairwise_rows']}`",
        f"- Raw rollout rows: `{merged_counts['raw_rollout_rows']}`",
        f"- Near-tie margin: `{args.near_tie_margin}`",
        "",
        "## Candidate rows by dataset",
    ]
    for ds, n in sorted(dataset_counts.items()):
        lines.append(f"- {ds}: {n}")
    lines.extend(["", "## Candidate rows by remaining budget"])
    for b, n in sorted(budget_counts.items(), key=lambda x: int(x[0])):
        lines.append(f"- budget {b}: {n}")
    lines.extend(["", "## Candidate rows by mode"])
    for m, n in sorted(mode_counts.items()):
        lines.append(f"- {m}: {n}")
    lines.extend(["", "## Near-tie coverage"])
    for ds in sorted(margin_abs_by_dataset.keys()):
        near = int(near_tie_counts.get(ds, 0))
        total = len(margin_abs_by_dataset[ds])
        lines.append(f"- {ds}: {near}/{total} ({near/max(1,total):.3f})")

    (out_dir / "merged_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    manifest = {
        "run_id": args.run_id,
        "generator": "bruteforce_branch_label_merge_v1",
        "inputs": {
            "runs_root": str(runs_root),
            "run_ids": run_ids,
        },
        "outputs": {
            "candidate_labels": str(cand_out),
            "pairwise_labels": str(pair_out),
            "state_summaries": str(state_out),
            "raw_rollouts": str(raw_out),
            "merged_summary": str(summary_path),
            "merged_report": str(out_dir / "merged_report.md"),
        },
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(json.dumps({"output_dir": str(out_dir), "summary": str(summary_path)}, indent=2))


if __name__ == "__main__":
    main()
