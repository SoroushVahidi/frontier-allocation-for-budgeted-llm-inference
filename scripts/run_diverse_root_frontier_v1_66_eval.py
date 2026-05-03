#!/usr/bin/env python3
"""Minimal evaluation of direct_reserve_diverse_root_frontier_v1 on 66 gold-absent cases.

Compares baseline direct_reserve_strategy_seeded_semantic_frontier_v2_final vs new direct_reserve_diverse_root_frontier_v1
on the same case list. Primary metric: gold_present_in_candidate_groups.

No API calls; uses simulator mode.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.frontier_matrix_core import (
    build_frontier_strategies,
    generator_factory_for_mode,
    load_pilot_examples,
)
from experiments.data import PilotExample, extract_final_answer


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Evaluate direct_reserve_diverse_root_frontier_v1 vs direct_reserve_strategy_seeded_semantic_frontier_v2_final on 66 gold-absent cases."
    )
    p.add_argument(
        "--case-list",
        default="outputs/strategy_seeded_discovery_on_66_gold_absent_20260502T222129Z/gold_absent_case_list.csv",
    )
    p.add_argument("--limit", type=int, default=0, help="Limit number of cases (0=all)")
    p.add_argument("--timestamp", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    p.add_argument("--budget", type=int, default=6)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--temperature", type=float, default=0.2)
    p.add_argument("--max-output-tokens", type=int, default=180)
    p.add_argument("--timeout-seconds", type=int, default=45)
    p.add_argument("--output-root", default="outputs")
    return p.parse_args()


def read_csv(path: Path | str) -> list[dict[str, str]]:
    """Read CSV file."""
    p = Path(path)
    if not p.exists():
        return []
    with p.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    """Write CSV file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        with path.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames or ["empty"])
            w.writeheader()
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames or list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def write_json(path: Path, data: dict[str, Any]) -> None:
    """Write JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=True)


def as_int(v: Any, d: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return d


def as_float(v: Any, d: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return d


def _normalize_answer_for_comparison(ans: str | None) -> str:
    """Normalize answer for comparison."""
    if not ans:
        return ""
    s = str(ans).strip().lower()
    # Remove common math notation
    for ch in "[](){}":
        s = s.replace(ch, "")
    return s.strip()


def _is_gold_in_candidates(candidates: list[dict[str, Any]], gold_norm: str) -> bool:
    """Check if gold is in candidate groups."""
    if not gold_norm or gold_norm.lower() in ("", "na", "none"):
        return False
    for cand in candidates:
        cand_norm = _normalize_answer_for_comparison(cand.get("normalized_answer", ""))
        if cand_norm == gold_norm:
            return True
    return False


def load_case_list(case_list_path: str) -> list[dict[str, Any]]:
    """Load and parse case list CSV."""
    rows = read_csv(case_list_path)
    if not rows:
        raise SystemExit(f"No cases found in {case_list_path}")
    return rows


def get_case_key(case: dict[str, str]) -> str:
    """Extract unique case key."""
    return (
        f"{case.get('dataset', 'unknown')}::{case.get('example_id', '')}::"
        f"{case.get('seed', '')}::{case.get('budget', '')}"
    )


def main() -> None:
    args = parse_args()
    rng = random.Random(args.seed)

    # Load cases
    case_list_path = REPO_ROOT / args.case_list if not Path(args.case_list).is_absolute() else Path(args.case_list)
    cases = load_case_list(str(case_list_path))

    if args.limit > 0:
        cases = cases[:args.limit]

    print(f"Loaded {len(cases)} cases from {case_list_path}")

    # Create output directory
    output_dir = REPO_ROOT / args.output_root / f"diverse_root_frontier_v1_66_eval_{args.timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output directory: {output_dir}")

    # Build strategies
    def gen_factory():
        return generator_factory_for_mode(
            use_openai_api=False,
            rng=rng,
            openai_model="gpt-4.1-mini",
            temperature=args.temperature,
            max_output_tokens=args.max_output_tokens,
            timeout_seconds=args.timeout_seconds,
        )

    strategies = build_frontier_strategies(
        generator_factory=gen_factory,
        budget=args.budget,
        adaptive_min_expand_grid=[1],
        rng=rng,
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
    )

    # Filter to only the two strategies we care about
    baseline_method = "direct_reserve_strategy_seeded_semantic_frontier_v2_final"
    new_method = "direct_reserve_diverse_root_frontier_v1"

    baseline_ctrl = strategies.get(baseline_method)
    new_ctrl = strategies.get(new_method)

    if not baseline_ctrl:
        raise SystemExit(f"Strategy {baseline_method} not found in build_frontier_strategies")
    if not new_ctrl:
        raise SystemExit(f"Strategy {new_method} not found in build_frontier_strategies")

    print(f"Using baseline: {baseline_method}")
    print(f"Using new: {new_method}")

    # Run evaluation
    per_case_results = []
    newly_recovered = []
    baseline_gold_count = 0
    new_gold_count = 0

    for i, case in enumerate(cases):
        case_id = get_case_key(case)
        print(f"[{i+1}/{len(cases)}] Evaluating {case_id}...", end=" ", flush=True)

        dataset_name = case.get("dataset", "openai/gsm8k")
        example_id = case.get("example_id", "")
        gold_answer_hint = case.get("gold_answer_canonical_hint", "")

        # Normalize gold answer
        gold_norm = _normalize_answer_for_comparison(gold_answer_hint)

        # Try to run both strategies
        try:
            baseline_result = baseline_ctrl.run(f"[{dataset_name}] {example_id}", gold_answer_hint or "")
            baseline_gold_present = _is_gold_in_candidates(
                baseline_result.metadata.get("candidates", []) if baseline_result.metadata else [], gold_norm
            )
        except Exception as e:
            print(f"baseline error: {e}", end=" ")
            baseline_gold_present = False
            baseline_result = None

        try:
            new_result = new_ctrl.run(f"[{dataset_name}] {example_id}", gold_answer_hint or "")
            new_gold_present = _is_gold_in_candidates(
                new_result.metadata.get("candidates", []) if new_result.metadata else [], gold_norm
            )
        except Exception as e:
            print(f"new error: {e}", end=" ")
            new_gold_present = False
            new_result = None

        if baseline_gold_present:
            baseline_gold_count += 1
        if new_gold_present:
            new_gold_count += 1
            if not baseline_gold_present:
                newly_recovered.append(case_id)

        recovery_status = "recovered" if (new_gold_present and not baseline_gold_present) else "no_change"

        per_case_results.append(
            {
                "case_id": case_id,
                "dataset": dataset_name,
                "example_id": example_id,
                "seed": case.get("seed", ""),
                "budget": case.get("budget", ""),
                "gold_answer": gold_answer_hint,
                "baseline_gold_present": "yes" if baseline_gold_present else "no",
                "new_gold_present": "yes" if new_gold_present else "no",
                "baseline_actions": baseline_result.actions_used if baseline_result else 0,
                "new_actions": new_result.actions_used if new_result else 0,
                "recovery_status": recovery_status,
            }
        )

        print(f"baseline={baseline_gold_present} new={new_gold_present}")

    # Calculate summary metrics
    total_cases = len(cases)
    baseline_recovery_rate = baseline_gold_count / total_cases if total_cases > 0 else 0.0
    new_recovery_rate = new_gold_count / total_cases if total_cases > 0 else 0.0
    newly_recovered_count = len(newly_recovered)

    summary = {
        "timestamp": args.timestamp,
        "total_cases": total_cases,
        "baseline_method": baseline_method,
        "new_method": new_method,
        "baseline_gold_present_count": baseline_gold_count,
        "baseline_recovery_rate": baseline_recovery_rate,
        "new_gold_present_count": new_gold_count,
        "new_recovery_rate": new_recovery_rate,
        "delta_gold_present": new_gold_count - baseline_gold_count,
        "newly_recovered_count": newly_recovered_count,
        "improvement": "yes" if new_gold_count > baseline_gold_count else "no",
    }

    # Write outputs
    write_csv(output_dir / "per_case_results.csv", per_case_results)
    write_json(output_dir / "summary.json", summary)

    # Write summary.csv
    summary_csv = [
        {
            "metric": "total_cases",
            "value": total_cases,
        },
        {
            "metric": "baseline_gold_present_count",
            "value": baseline_gold_count,
        },
        {
            "metric": "baseline_recovery_rate",
            "value": f"{baseline_recovery_rate:.4f}",
        },
        {
            "metric": "new_gold_present_count",
            "value": new_gold_count,
        },
        {
            "metric": "new_recovery_rate",
            "value": f"{new_recovery_rate:.4f}",
        },
        {
            "metric": "delta_gold_present",
            "value": new_gold_count - baseline_gold_count,
        },
        {
            "metric": "newly_recovered_count",
            "value": newly_recovered_count,
        },
    ]
    write_csv(output_dir / "summary.csv", summary_csv)

    # Write newly recovered case IDs
    with (output_dir / "newly_recovered_case_ids.txt").open("w", encoding="utf-8") as f:
        for case_id in newly_recovered:
            f.write(f"{case_id}\n")

    # Print summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total cases: {total_cases}")
    print(f"Baseline ({baseline_method}): {baseline_gold_count}/{total_cases} ({baseline_recovery_rate:.2%})")
    print(f"New ({new_method}): {new_gold_count}/{total_cases} ({new_recovery_rate:.2%})")
    print(f"Delta: {new_gold_count - baseline_gold_count:+d}")
    print(f"Newly recovered: {newly_recovered_count}")
    print("=" * 80)
    print(f"Output saved to: {output_dir}")


if __name__ == "__main__":
    main()
