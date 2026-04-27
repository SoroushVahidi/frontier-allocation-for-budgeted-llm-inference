#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.branching import SimulatedBranchGenerator
from experiments.frontier_matrix_core import build_frontier_strategies
from experiments.trace_schema import build_branch_trace, write_trace_package


@dataclass(frozen=True)
class _Example:
    example_id: str
    question: str
    gold: str


def _now_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _examples() -> list[_Example]:
    return [
        _Example("trace_smoke_1", "What is 12 + 13?", "25"),
        _Example("trace_smoke_2", "A bag has 4 red and 6 blue balls. How many total?", "10"),
        _Example("trace_smoke_3", "If 3x = 21, what is x?", "7"),
    ]


def main() -> int:
    ap = argparse.ArgumentParser(description="Offline branch trace smoke for direct_reserve_frontier_gate_v1.")
    ap.add_argument("--timestamp", default=_now_ts())
    ap.add_argument("--allow-real-api", action="store_true", help="Unused guard; smoke remains offline unless implementation changes.")
    args = ap.parse_args()

    out_dir = REPO_ROOT / "outputs" / f"direct_reserve_frontier_gate_trace_smoke_{args.timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    specs = build_frontier_strategies(
        generator_factory=lambda: SimulatedBranchGenerator(
            rng=random.Random(211), max_depth=7, finish_prob_base=0.16, answer_noise=0.12
        ),
        budget=6,
        adaptive_min_expand_grid=[1],
        rng=random.Random(223),
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
        include_external_l1_baseline=True,
    )
    methods = [
        "external_l1_max",
        "strict_f3_anti_collapse_default_v1",
        "direct_reserve_frontier_gate_v1",
    ]
    traces = []
    for method in methods:
        if method not in specs:
            raise RuntimeError(f"Required method not available in strategy set: {method}")
        setattr(specs[method], "emit_full_traces", True)

    for ex in _examples():
        for method in methods:
            result = specs[method].run(ex.question, ex.gold)
            traces.append(
                build_branch_trace(
                    result=result,
                    example_id=ex.example_id,
                    dataset="offline/smoke",
                    provider="offline",
                    model="simulated",
                    budget=6,
                    seed=223,
                    method=method,
                    question=ex.question,
                    gold_answer=ex.gold,
                )
            )

    stats = write_trace_package(out_dir, traces)
    support_nonempty = any(t["answer_groups"]["answer_group_support_counts"] for t in traces)
    required = [
        out_dir / "candidate_branch_table.csv",
        out_dir / "answer_group_table.csv",
        out_dir / "per_case_trace_index.csv",
    ]
    if not all(p.exists() for p in required):
        raise SystemExit("trace smoke failed: required trace tables missing")
    if stats["n_branches"] <= 0 or stats["n_answer_groups"] <= 0 or not support_nonempty:
        raise SystemExit("trace smoke failed: empty branch/group evidence")

    (out_dir / "manifest.json").write_text(
        json.dumps(
            {
                "artifact_family": "direct_reserve_frontier_gate_trace_smoke",
                "timestamp": args.timestamp,
                "real_api_allowed": bool(args.allow_real_api),
                "real_api_used": False,
                **stats,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Wrote trace smoke package to {out_dir} ({stats})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
