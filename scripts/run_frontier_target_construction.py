#!/usr/bin/env python3
"""Run allocation-first frontier target construction.

Outputs an auditable package with frontier states, budget-conditioned marginal
utility estimates, comparative labels, summary files, run manifest, schema,
and config echo.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.frontier_target_construction import FrontierTargetConstructionConfig, run_frontier_target_construction


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build frontier allocation supervision targets from traces.")
    p.add_argument("--output-root", default="outputs/frontier_target_construction")
    p.add_argument("--run-id", default=None)
    p.add_argument("--trace-jsonl", default="", help="Optional trace JSONL path; uses synthetic simulator if omitted.")

    p.add_argument("--episodes", type=int, default=24)
    p.add_argument("--decision-budget", type=int, default=10)
    p.add_argument("--n-init-branches", type=int, default=4)
    p.add_argument("--max-depth", type=int, default=7)
    p.add_argument("--finish-prob-base", type=float, default=0.16)
    p.add_argument("--answer-noise", type=float, default=0.12)
    p.add_argument("--max-branches-per-state", type=int, default=4)
    p.add_argument("--rollouts-per-branch", type=int, default=8)
    p.add_argument("--tie-margin", type=float, default=0.02)
    p.add_argument("--outside-option-floor", type=float, default=0.35)
    p.add_argument("--rollout-policy", choices=["stalled_aware", "expand_only", "verify_only"], default="stalled_aware")
    p.add_argument("--seed", type=int, default=17)
    p.add_argument("--train-ratio", type=float, default=0.8)
    return p.parse_args()


def _resolve_run_id(user_supplied: str | None) -> str:
    if user_supplied:
        return user_supplied
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def main() -> None:
    args = parse_args()
    run_id = _resolve_run_id(args.run_id)
    out_dir = REPO_ROOT / args.output_root / run_id

    cfg = FrontierTargetConstructionConfig(
        episodes=args.episodes,
        decision_budget=args.decision_budget,
        n_init_branches=args.n_init_branches,
        max_depth=args.max_depth,
        finish_prob_base=args.finish_prob_base,
        answer_noise=args.answer_noise,
        max_branches_per_state=args.max_branches_per_state,
        rollouts_per_branch=args.rollouts_per_branch,
        tie_margin=args.tie_margin,
        outside_option_floor=args.outside_option_floor,
        rollout_policy=args.rollout_policy,
        seed=args.seed,
        train_ratio=args.train_ratio,
    )

    trace_jsonl = Path(args.trace_jsonl) if args.trace_jsonl else None
    result = run_frontier_target_construction(cfg, output_dir=out_dir, trace_jsonl=trace_jsonl)

    payload = {
        "run_id": run_id,
        "output_dir": str(out_dir),
        "summary": result["summary"],
    }
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
