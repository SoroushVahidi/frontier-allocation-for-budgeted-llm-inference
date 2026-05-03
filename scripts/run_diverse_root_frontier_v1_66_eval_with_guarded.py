#!/usr/bin/env python3
"""Evaluation of diverse_root_frontier_v1 variants on 66 gold-absent cases.

Compares three methods:
1. Baseline: direct_reserve_strategy_seeded_semantic_frontier_v2_final
2. V1: direct_reserve_diverse_root_frontier_v1
3. Guarded: direct_reserve_diverse_root_frontier_v1_guarded (falls back when baseline has strong support)

Primary metric: gold_present_in_candidate_groups.
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
from experiments.selector_candidate_extraction import build_candidates_from_metadata


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Evaluate diverse_root_frontier_v1 variants on 66 gold-absent cases."
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


def _load_gsm8k_examples_by_id() -> dict[str, PilotExample]:
    """Load all GSM8K examples and index by example_id."""
    examples = load_pilot_examples("openai/gsm8k", subset_size=1000, seed=42)
    return {ex.example_id: ex for ex in examples}


def get_example_question(
    example_id: str, dataset_name: str, example_cache: dict[str, PilotExample]
) -> str:
    """Get the actual question text for an example."""
    if dataset_name != "openai/gsm8k":
        return f"[{dataset_name}] {example_id}"

    if not example_cache:
        return f"[{dataset_name}] {example_id}"

    example = example_cache.get(example_id)
    if example:
        return example.question

    return f"[{dataset_name}] {example_id}"


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

    # Load GSM8K examples indexed by example_id
    print("Loading GSM8K examples...", end=" ", flush=True)
    example_cache = _load_gsm8k_examples_by_id()
    print(f"Done ({len(example_cache)} examples)")

    # Create output directory
    output_dir = REPO_ROOT / args.output_root / f"diverse_root_frontier_v1_guarded_66_eval_{args.timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output directory: {output_dir}")

    # Build strategies
    gen_factory_fn = generator_factory_for_mode(
        use_openai_api=False,
        rng=rng,
        openai_model="gpt-4.1-mini",
        temperature=args.temperature,
        max_output_tokens=args.max_output_tokens,
        timeout_seconds=args.timeout_seconds,
    )

    strategies = build_frontier_strategies(
        generator_factory=gen_factory_fn,
        budget=args.budget,
        adaptive_min_expand_grid=[1],
        rng=rng,
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
    )

    # Get the three methods
    baseline_method = "direct_reserve_strategy_seeded_semantic_frontier_v2_final"
    v1_method = "direct_reserve_diverse_root_frontier_v1"
    guarded_method = "direct_reserve_diverse_root_frontier_v1_guarded"

    baseline_ctrl = strategies.get(baseline_method)
    v1_ctrl = strategies.get(v1_method)
    guarded_ctrl = strategies.get(guarded_method)

    if not baseline_ctrl:
        raise SystemExit(f"Strategy {baseline_method} not found")
    if not v1_ctrl:
        raise SystemExit(f"Strategy {v1_method} not found")
    if not guarded_ctrl:
        raise SystemExit(f"Strategy {guarded_method} not found")

    print(f"Using baseline: {baseline_method}")
    print(f"Using v1: {v1_method}")
    print(f"Using guarded: {guarded_method}")

    # Run evaluation
    per_case_results = []
    baseline_gold_count = 0
    v1_gold_count = 0
    guarded_gold_count = 0

    v1_recovered = []
    guarded_recovered = []
    v1_regressed = []
    guarded_regressed = []

    for i, case in enumerate(cases):
        case_id = get_case_key(case)
        print(f"[{i+1}/{len(cases)}] {case_id}...", end=" ", flush=True)

        dataset_name = case.get("dataset", "openai/gsm8k")
        example_id = case.get("example_id", "")
        gold_answer_hint = case.get("gold_answer_canonical_hint", "")

        question_text = get_example_question(example_id, dataset_name, example_cache)
        gold_norm = _normalize_answer_for_comparison(gold_answer_hint)

        # Baseline
        try:
            baseline_result = baseline_ctrl.run(question_text, gold_answer_hint or "")
            candidates = []
            if baseline_result.metadata:
                candidates = build_candidates_from_metadata(question_text, baseline_result.metadata)[0]
            baseline_gold_present = _is_gold_in_candidates(
                [{"normalized_answer": c.normalized_answer} for c in candidates], gold_norm
            )
        except Exception as e:
            print(f"baseline error: {e}", end=" ")
            baseline_gold_present = False

        # V1
        try:
            v1_result = v1_ctrl.run(question_text, gold_answer_hint or "")
            candidates = []
            if v1_result.metadata:
                candidates = build_candidates_from_metadata(question_text, v1_result.metadata)[0]
            v1_gold_present = _is_gold_in_candidates(
                [{"normalized_answer": c.normalized_answer} for c in candidates], gold_norm
            )
        except Exception as e:
            print(f"v1 error: {e}", end=" ")
            v1_gold_present = False

        # Guarded
        try:
            guarded_result = guarded_ctrl.run(question_text, gold_answer_hint or "")
            candidates = []
            if guarded_result.metadata:
                candidates = build_candidates_from_metadata(question_text, guarded_result.metadata)[0]
            guarded_gold_present = _is_gold_in_candidates(
                [{"normalized_answer": c.normalized_answer} for c in candidates], gold_norm
            )
        except Exception as e:
            print(f"guarded error: {e}", end=" ")
            guarded_gold_present = False

        # Count hits
        if baseline_gold_present:
            baseline_gold_count += 1
        if v1_gold_present:
            v1_gold_count += 1
        if guarded_gold_present:
            guarded_gold_count += 1

        # Track recovery/regression
        if v1_gold_present and not baseline_gold_present:
            v1_recovered.append(case_id)
        elif not v1_gold_present and baseline_gold_present:
            v1_regressed.append(case_id)

        if guarded_gold_present and not baseline_gold_present:
            guarded_recovered.append(case_id)
        elif not guarded_gold_present and baseline_gold_present:
            guarded_regressed.append(case_id)

        # Determine statuses
        v1_status = (
            "recovered" if (v1_gold_present and not baseline_gold_present)
            else "regressed" if (not v1_gold_present and baseline_gold_present)
            else "no_change"
        )
        guarded_status = (
            "recovered" if (guarded_gold_present and not baseline_gold_present)
            else "regressed" if (not guarded_gold_present and baseline_gold_present)
            else "no_change"
        )

        per_case_results.append(
            {
                "case_id": case_id,
                "dataset": dataset_name,
                "example_id": example_id,
                "seed": case.get("seed", ""),
                "budget": case.get("budget", ""),
                "gold_answer": gold_answer_hint,
                "baseline_gold_present": "yes" if baseline_gold_present else "no",
                "v1_gold_present": "yes" if v1_gold_present else "no",
                "guarded_gold_present": "yes" if guarded_gold_present else "no",
                "v1_status": v1_status,
                "guarded_status": guarded_status,
            }
        )

        print(f"B={baseline_gold_present} V1={v1_gold_present} G={guarded_gold_present}")

    # Calculate summary metrics
    total_cases = len(cases)
    baseline_rate = baseline_gold_count / total_cases if total_cases > 0 else 0.0
    v1_rate = v1_gold_count / total_cases if total_cases > 0 else 0.0
    guarded_rate = guarded_gold_count / total_cases if total_cases > 0 else 0.0

    summary = {
        "timestamp": args.timestamp,
        "total_cases": total_cases,
        "baseline_method": baseline_method,
        "baseline_gold_present_count": baseline_gold_count,
        "baseline_recovery_rate": baseline_rate,
        "v1_method": v1_method,
        "v1_gold_present_count": v1_gold_count,
        "v1_recovery_rate": v1_rate,
        "v1_delta_gold_present": v1_gold_count - baseline_gold_count,
        "v1_newly_recovered_count": len(v1_recovered),
        "v1_newly_regressed_count": len(v1_regressed),
        "guarded_method": guarded_method,
        "guarded_gold_present_count": guarded_gold_count,
        "guarded_recovery_rate": guarded_rate,
        "guarded_delta_gold_present": guarded_gold_count - baseline_gold_count,
        "guarded_newly_recovered_count": len(guarded_recovered),
        "guarded_newly_regressed_count": len(guarded_regressed),
    }

    # Write outputs
    write_csv(output_dir / "per_case_results.csv", per_case_results)
    write_json(output_dir / "summary.json", summary)

    # Write recovery/regression lists
    with (output_dir / "v1_recovered_case_ids.txt").open("w", encoding="utf-8") as f:
        for case_id in v1_recovered:
            f.write(f"{case_id}\n")
    with (output_dir / "v1_regressed_case_ids.txt").open("w", encoding="utf-8") as f:
        for case_id in v1_regressed:
            f.write(f"{case_id}\n")
    with (output_dir / "guarded_recovered_case_ids.txt").open("w", encoding="utf-8") as f:
        for case_id in guarded_recovered:
            f.write(f"{case_id}\n")
    with (output_dir / "guarded_regressed_case_ids.txt").open("w", encoding="utf-8") as f:
        for case_id in guarded_regressed:
            f.write(f"{case_id}\n")

    # Print summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total cases: {total_cases}")
    print(f"\nBaseline ({baseline_method}): {baseline_gold_count}/{total_cases} ({baseline_rate:.2%})")
    print(f"V1 ({v1_method}): {v1_gold_count}/{total_cases} ({v1_rate:.2%})")
    print(f"  Delta: {v1_gold_count - baseline_gold_count:+d} | Recovered: {len(v1_recovered)} | Regressed: {len(v1_regressed)}")
    print(f"Guarded ({guarded_method}): {guarded_gold_count}/{total_cases} ({guarded_rate:.2%})")
    print(f"  Delta: {guarded_gold_count - baseline_gold_count:+d} | Recovered: {len(guarded_recovered)} | Regressed: {len(guarded_regressed)}")
    print("=" * 80)
    print(f"Output saved to: {output_dir}")


if __name__ == "__main__":
    main()
