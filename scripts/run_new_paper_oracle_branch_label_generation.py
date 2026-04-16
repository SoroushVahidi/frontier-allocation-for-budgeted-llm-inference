#!/usr/bin/env python3
"""Run a small new-paper pilot for approximate-oracle branch labels."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.oracle_branch_labels import OracleLabelConfig, generate_oracle_branch_labels, write_jsonl


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate approximate-oracle branch labels (new-paper track)")
    p.add_argument("--output-root", default="outputs/new_paper/oracle_branch_labels")
    p.add_argument("--run-id", default=None)
    p.add_argument("--episodes", type=int, default=24)
    p.add_argument("--seed", type=int, default=17)
    p.add_argument("--decision-budget", type=int, default=10)
    p.add_argument("--n-init-branches", type=int, default=4)
    p.add_argument("--max-decisions-per-episode-to-label", type=int, default=3)
    p.add_argument("--max-branches-per-decision", type=int, default=3)
    p.add_argument("--rollouts-per-policy", type=int, default=3)
    p.add_argument("--high-budget-multiplier", type=float, default=1.5)
    p.add_argument("--exhaustive-action-budget-cap", type=int, default=2)
    p.add_argument("--tie-margin", type=float, default=0.02)
    p.add_argument("--uncertainty-margin-band", type=float, default=None)
    p.add_argument("--disagreement-rate-threshold", type=float, default=0.25)
    p.add_argument("--disable-margin-uncertainty-rule", action="store_true")
    p.add_argument("--disable-ci-uncertainty-rule", action="store_true")
    p.add_argument("--disable-disagreement-uncertainty-rule", action="store_true")
    p.add_argument("--value-aggregation", choices=["max", "robust_blend"], default="max")
    p.add_argument("--value-std-penalty", type=float, default=0.0)
    return p.parse_args()


def _run_id(user_supplied: str | None) -> str:
    if user_supplied:
        return user_supplied
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def main() -> None:
    args = parse_args()
    run_id = _run_id(args.run_id)
    out_dir = Path(args.output_root) / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    cfg = OracleLabelConfig(
        episodes=args.episodes,
        seed=args.seed,
        decision_budget=args.decision_budget,
        n_init_branches=args.n_init_branches,
        max_decisions_per_episode_to_label=args.max_decisions_per_episode_to_label,
        max_branches_per_decision=args.max_branches_per_decision,
        rollouts_per_policy=args.rollouts_per_policy,
        high_budget_multiplier=args.high_budget_multiplier,
        exhaustive_action_budget_cap=args.exhaustive_action_budget_cap,
        tie_margin=args.tie_margin,
        uncertainty_margin_band=args.uncertainty_margin_band,
        enable_margin_uncertainty_rule=not bool(args.disable_margin_uncertainty_rule),
        enable_ci_uncertainty_rule=not bool(args.disable_ci_uncertainty_rule),
        enable_disagreement_uncertainty_rule=not bool(args.disable_disagreement_uncertainty_rule),
        disagreement_rate_threshold=args.disagreement_rate_threshold,
        value_aggregation=args.value_aggregation,
        value_std_penalty=args.value_std_penalty,
    )

    branch_rows, pair_rows, summary = generate_oracle_branch_labels(cfg)

    branch_path = out_dir / "branch_oracle_labels.jsonl"
    pair_path = out_dir / "pairwise_oracle_preferences.jsonl"
    summary_csv_path = out_dir / "oracle_label_summary.csv"
    manifest_path = out_dir / "run_manifest.json"
    interpretation_path = out_dir / "interpretation.md"

    write_jsonl(branch_path, branch_rows)
    write_jsonl(pair_path, pair_rows)

    with summary_csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["metric", "value"])
        writer.writeheader()
        for key, val in summary.items():
            writer.writerow({"metric": key, "value": val})

    manifest = {
        "run_id": run_id,
        "track": "new-paper",
        "label_name": "approx_oracle_continuation_value",
        "label_definition": (
            "Best continuation-outcome value found among bounded high-budget rollouts and small action-enumeration "
            "when remaining budget is tiny. Approximate unless branch is already terminal or budget is zero."
        ),
        "output_files": {
            "branch_oracle_labels": str(branch_path),
            "pairwise_oracle_preferences": str(pair_path),
            "oracle_label_summary": str(summary_csv_path),
            "interpretation": str(interpretation_path),
        },
        "config": vars(args),
        "summary": summary,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    interpretation = f"""# Approximate Oracle Branch Label Pilot ({run_id})

## What the label means
- `approx_oracle_continuation_value` = maximum continuation-outcome value found under a bounded high-budget continuation set.
- It is **not exact** in general; it is an estimate from finite policies/rollouts.
- It is marked exact only for trivial cases (`branch.is_done` or `remaining_budget == 0`).

## Pilot scope
- Episodes: {cfg.episodes}
- Decision budget: {cfg.decision_budget}
- Kept decision snapshots per episode: {cfg.max_decisions_per_episode_to_label}
- Branches per labeled decision: {cfg.max_branches_per_decision}
- Rollouts per policy: {cfg.rollouts_per_policy}

## Main feasibility signals
- Branch labels generated: {summary['n_branch_labels']}
- Pairwise labels generated: {summary['n_pairwise_labels']}
- Approximate labels: {summary['n_approximate_labels']}
- Exact labels: {summary['n_exact_labels']}

## Proxy vs oracle-ish comparison
- Pairwise agreement rate: {summary['oracle_proxy_pair_agreement_rate']:.4f}
- Pairwise disagreement rate: {summary['oracle_proxy_pair_disagreement_rate']:.4f}
- Oracle tie rate: {summary['oracle_pair_tie_rate']:.4f}

## Interpretation notes
- Disagreements indicate where one-step proxy continuation estimates differ from stronger bounded continuation search.
- Because the oracle-ish labels include deeper/high-budget continuation probes, they can serve as richer supervision than proxy-only pairwise labels.
- This pilot remains conservative: bounded rollout families, small subset size, and explicit non-exact naming.
"""
    interpretation_path.write_text(interpretation, encoding="utf-8")

    print(json.dumps({"run_id": run_id, "out_dir": str(out_dir), "summary": summary}, indent=2))


if __name__ == "__main__":
    main()
