#!/usr/bin/env python3
"""Build random matched-coverage oracle-distillation baselines.

Supports:
- single deterministic draw (backward compatible),
- repeated deterministic draws with per-draw outputs + aggregate manifest.
"""

from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path
import random
import statistics
from typing import Any


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _stable_key(row: dict[str, Any], idx: int) -> str:
    sid = str(row.get("state_id", ""))
    if sid:
        return sid
    eid = str(row.get("example_id", ""))
    if eid:
        return f"example:{eid}"
    return f"row:{idx}"


def _bucket_allowed(bucket: str, regime: str) -> bool:
    b = bucket.strip().lower()
    if regime == "accepted_only":
        return b == "accepted"
    if regime == "accepted_plus_borderline":
        return b in {"accepted", "borderline"}
    raise ValueError(f"unknown regime: {regime}")


def _strat_key(row: dict[str, Any], dims: list[str]) -> tuple[str, ...]:
    out: list[str] = []
    for d in dims:
        if d == "bucket":
            out.append(str(row.get("bucket", "")))
        elif d == "budget":
            out.append(str(row.get("budget", row.get("remaining_budget", ""))))
        else:
            raise ValueError(f"Unsupported stratify dim: {d}")
    return tuple(out)


def _group_indices(rows: list[dict[str, Any]], indices: list[int], dims: list[str]) -> dict[tuple[str, ...], list[int]]:
    groups: dict[tuple[str, ...], list[int]] = {}
    for i in indices:
        k = _strat_key(rows[i], dims)
        groups.setdefault(k, []).append(i)
    return groups


def _compute_pool(
    rows: list[dict[str, Any]], *, regime: str, respect_positive_weight_only: bool
) -> tuple[list[int], list[int]]:
    train_pool_idxs: list[int] = []
    selective_train_idxs: list[int] = []
    for i, row in enumerate(rows):
        split = str(row.get("split", "")).lower()
        if split != "train":
            continue
        if respect_positive_weight_only and float(row.get("sample_weight", 1.0)) <= 0.0:
            continue
        train_pool_idxs.append(i)
        bucket = str(row.get("bucket", "")).lower()
        if _bucket_allowed(bucket, regime):
            selective_train_idxs.append(i)
    return train_pool_idxs, selective_train_idxs


def _sample_indices(
    rows: list[dict[str, Any]],
    *,
    train_pool_idxs: list[int],
    selective_train_idxs: list[int],
    seed: int,
    stratify_dims: list[str],
) -> tuple[set[int], dict[str, Any]]:
    selected_target = len(selective_train_idxs)
    rng = random.Random(int(seed))

    if not stratify_dims:
        shuffled = list(train_pool_idxs)
        rng.shuffle(shuffled)
        chosen = set(shuffled[:selected_target])
        return chosen, {"enabled": False, "dimensions": []}

    source_groups = _group_indices(rows, train_pool_idxs, stratify_dims)
    selective_groups = _group_indices(rows, selective_train_idxs, stratify_dims)

    quotas: dict[tuple[str, ...], int] = {k: len(v) for k, v in selective_groups.items()}
    chosen: set[int] = set()
    for key in sorted(source_groups.keys()):
        candidates = list(source_groups[key])
        rng.shuffle(candidates)
        take = min(len(candidates), int(quotas.get(key, 0)))
        chosen.update(candidates[:take])

    if len(chosen) < selected_target:
        remaining = [i for i in train_pool_idxs if i not in chosen]
        rng.shuffle(remaining)
        chosen.update(remaining[: (selected_target - len(chosen))])

    if len(chosen) > selected_target:
        ordered = sorted(chosen, key=lambda idx: _stable_key(rows[idx], idx))
        chosen = set(ordered[:selected_target])

    return chosen, {
        "enabled": True,
        "dimensions": stratify_dims,
        "source_group_counts": {"|".join(k): len(v) for k, v in sorted(source_groups.items())},
        "target_group_counts": {"|".join(k): len(v) for k, v in sorted(selective_groups.items())},
    }


def _rows_with_selection(
    rows: list[dict[str, Any]],
    *,
    chosen: set[int],
    regime: str,
    seed: int,
    draw_index: int,
) -> list[dict[str, Any]]:
    out_rows: list[dict[str, Any]] = []
    for i, row in enumerate(rows):
        new_row = dict(row)
        is_train = str(row.get("split", "")).lower() == "train"
        selected = 1 if (is_train and i in chosen) else 0
        new_row["selected_for_training"] = selected
        new_row["baseline_kind"] = "random_matched_coverage"
        new_row["baseline_target_regime"] = regime
        new_row["baseline_random_seed"] = int(seed)
        new_row["baseline_draw_index"] = int(draw_index)

        prov = dict(new_row.get("provenance", {}))
        prov["random_matched_coverage_baseline"] = True
        prov["baseline_target_regime"] = regime
        prov["baseline_random_seed"] = int(seed)
        prov["baseline_draw_index"] = int(draw_index)
        prov["non_claim_baseline_only"] = True
        new_row["provenance"] = prov
        out_rows.append(new_row)
    return out_rows


def _selection_ids(rows: list[dict[str, Any]], chosen: set[int]) -> set[str]:
    ids: set[str] = set()
    for idx in chosen:
        ids.add(_stable_key(rows[idx], idx))
    return ids


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build random matched-coverage oracle-distillation baseline dataset(s)")
    p.add_argument("--input-jsonl", required=True, help="Distillation-ready dataset JSONL")
    p.add_argument("--summary-json", required=True, help="Output summary JSON")
    p.add_argument(
        "--target-regime",
        choices=["accepted_only", "accepted_plus_borderline"],
        required=True,
        help="Selective regime to match in retained train coverage",
    )
    p.add_argument("--seed", type=int, default=31)
    p.add_argument("--num-draws", type=int, default=1, help="Number of deterministic random draws")
    p.add_argument("--seed-step", type=int, default=1, help="Seed increment between draws")
    p.add_argument(
        "--stratify-by",
        default="",
        help="Optional comma-separated dims for stratified matching. Supported: bucket,budget",
    )
    p.add_argument(
        "--respect-positive-weight-only",
        action="store_true",
        help="If set, compute target regime rows using sample_weight>0 rows only.",
    )

    # Single-draw output mode
    p.add_argument("--output-jsonl", default="", help="Single draw output JSONL (required when --num-draws=1)")

    # Multi-draw output mode
    p.add_argument("--output-dir", default="", help="Directory for repeated draws (required when --num-draws>1)")
    p.add_argument("--output-prefix", default="random_matched", help="Prefix for repeated draw filenames")
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    if args.num_draws < 1:
        raise SystemExit("--num-draws must be >= 1")
    if args.num_draws == 1 and not args.output_jsonl:
        raise SystemExit("--output-jsonl is required when --num-draws=1")
    if args.num_draws > 1 and not args.output_dir:
        raise SystemExit("--output-dir is required when --num-draws>1")

    rows = _read_jsonl(Path(args.input_jsonl))
    stratify_dims = [x.strip() for x in args.stratify_by.split(",") if x.strip()]
    train_pool_idxs, selective_train_idxs = _compute_pool(
        rows,
        regime=args.target_regime,
        respect_positive_weight_only=bool(args.respect_positive_weight_only),
    )

    train_pool_size = len(train_pool_idxs)
    selected_target = len(selective_train_idxs)
    if train_pool_size <= 0:
        raise SystemExit("No train-pool rows found in input dataset")
    if selected_target <= 0:
        raise SystemExit("Target regime has zero rows in train pool; cannot construct matched random baseline")

    selective_cov = float(selected_target / max(1, train_pool_size))

    draws: list[dict[str, Any]] = []
    selections_for_overlap: list[set[str]] = []

    if args.num_draws == 1:
        draw_seed = int(args.seed)
        chosen, strat_meta = _sample_indices(
            rows,
            train_pool_idxs=train_pool_idxs,
            selective_train_idxs=selective_train_idxs,
            seed=draw_seed,
            stratify_dims=stratify_dims,
        )
        out_rows = _rows_with_selection(rows, chosen=chosen, regime=args.target_regime, seed=draw_seed, draw_index=0)
        _write_jsonl(Path(args.output_jsonl), out_rows)

        retained_count = len(chosen)
        retained_cov = float(retained_count / max(1, train_pool_size))
        draw = {
            "draw_index": 0,
            "random_seed": draw_seed,
            "output_jsonl": args.output_jsonl,
            "retained_rows": retained_count,
            "retained_coverage": retained_cov,
            "coverage_gap_vs_regime": float(retained_cov - selective_cov),
        }
        draws.append(draw)
        selections_for_overlap.append(_selection_ids(rows, chosen))
    else:
        out_dir = Path(args.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        for draw_idx in range(args.num_draws):
            draw_seed = int(args.seed + draw_idx * args.seed_step)
            chosen, strat_meta = _sample_indices(
                rows,
                train_pool_idxs=train_pool_idxs,
                selective_train_idxs=selective_train_idxs,
                seed=draw_seed,
                stratify_dims=stratify_dims,
            )
            out_path = out_dir / f"{args.output_prefix}_draw_{draw_idx:03d}_seed_{draw_seed}.jsonl"
            out_rows = _rows_with_selection(
                rows,
                chosen=chosen,
                regime=args.target_regime,
                seed=draw_seed,
                draw_index=draw_idx,
            )
            _write_jsonl(out_path, out_rows)

            retained_count = len(chosen)
            retained_cov = float(retained_count / max(1, train_pool_size))
            draws.append(
                {
                    "draw_index": draw_idx,
                    "random_seed": draw_seed,
                    "output_jsonl": str(out_path),
                    "retained_rows": retained_count,
                    "retained_coverage": retained_cov,
                    "coverage_gap_vs_regime": float(retained_cov - selective_cov),
                }
            )
            selections_for_overlap.append(_selection_ids(rows, chosen))

    overlap_rows: list[dict[str, Any]] = []
    if len(selections_for_overlap) > 1:
        for (i, a), (j, b) in itertools.combinations(enumerate(selections_for_overlap), 2):
            inter = len(a & b)
            union = max(1, len(a | b))
            overlap_rows.append(
                {
                    "draw_i": int(i),
                    "draw_j": int(j),
                    "intersection": inter,
                    "union": int(len(a | b)),
                    "jaccard": float(inter / union),
                }
            )

    covs = [float(d["retained_coverage"]) for d in draws]
    summary = {
        "status": "ok",
        "input_jsonl": args.input_jsonl,
        "target_regime": args.target_regime,
        "num_draws": int(args.num_draws),
        "seed_base": int(args.seed),
        "seed_step": int(args.seed_step),
        "source_pool": {
            "train_pool_rows": train_pool_size,
            "regime_selected_rows": selected_target,
            "regime_retained_coverage": selective_cov,
        },
        "draws": draws,
        "coverage_stats": {
            "mean": float(sum(covs) / max(1, len(covs))),
            "std": float(statistics.pstdev(covs)) if len(covs) > 1 else 0.0,
            "min": float(min(covs)),
            "max": float(max(covs)),
        },
        "stratification": strat_meta,
        "overlap_between_draws": {
            "pairwise": overlap_rows,
            "mean_jaccard": float(sum(x["jaccard"] for x in overlap_rows) / max(1, len(overlap_rows))) if overlap_rows else 1.0,
        },
        "safety": {
            "non_claim_mode": True,
            "warning": "Random matched-coverage baseline artifact(s) only; not oracle performance evidence.",
        },
    }

    _write_json(Path(args.summary_json), summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
