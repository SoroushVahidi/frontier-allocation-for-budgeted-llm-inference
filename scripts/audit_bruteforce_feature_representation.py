#!/usr/bin/env python3
"""Audit branch-allocation feature coverage for hard comparison cases."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.bruteforce_branch_allocator import (  # noqa: E402
    ALLOC_FEATURE_NAMES_V1,
    ALLOC_FEATURE_NAMES_V2,
    LearningConfig,
    load_label_artifacts,
    prepare_learning_tables,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Audit hard-case feature representation")
    p.add_argument("--labels-dir", required=True)
    p.add_argument("--output-dir", default="outputs/branch_label_bruteforce_learning")
    p.add_argument("--run-id", required=True)
    p.add_argument("--seed", type=int, default=17)
    p.add_argument("--near-tie-margin", type=float, default=0.03)
    return p.parse_args()


def _mean(xs: list[float]) -> float:
    return sum(xs) / max(1, len(xs))


def main() -> None:
    args = parse_args()
    out_dir = Path(args.output_dir) / args.run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    artifacts = load_label_artifacts(Path(args.labels_dir))
    cfg = LearningConfig(seed=int(args.seed), near_tie_margin=float(args.near_tie_margin), feature_set="v2")
    tables = prepare_learning_tables(artifacts, cfg)

    pairs = tables["pairwise"]
    near_tie = [r for r in pairs if abs(float(r.get("margin", 0.0))) <= float(args.near_tie_margin)]
    adjacent = [r for r in pairs if float(r.get("pair_relational_v2", {}).get("adjacent_rank_flag", 0.0)) > 0.5]

    coverage = {
        "signals": {
            "branch_momentum_recent_trend": ["recent_delta", "recent_delta_per_depth", "score_z"],
            "verification_dynamics": ["verify_count", "verify_rate", "verify_recent_delta_interaction"],
            "peer_relative_rank_structure": ["branch_rank", "branch_rank_norm", "score_gap_to_prev", "score_gap_to_next"],
            "frontier_competition_context": ["frontier_branch_count", "frontier_top2_gap", "frontier_score_hhi", "frontier_score_entropy"],
            "local_uncertainty_context": ["allocation_value_std", "frontier_score_std", "uncertainty_rel_to_score_std"],
            "stagnation_instability": ["stalled_steps", "stalled_ratio"],
            "top_neighbor_gap_signals": ["score_gap_to_top", "score_gap_to_prev", "score_gap_to_next"],
            "budget_context_interactions": ["budget_norm_in_state", "score_budget_interaction"],
            "pair_relational_features": [
                "pair_relational_v2.rank_gap_abs",
                "pair_relational_v2.score_gap_abs",
                "pair_relational_v2.score_z_gap_abs",
                "pair_relational_v2.verify_rate_gap_abs",
                "pair_relational_v2.uncertainty_gap_abs",
            ],
        },
        "v1_feature_count": len(ALLOC_FEATURE_NAMES_V1),
        "v2_feature_count": len(ALLOC_FEATURE_NAMES_V2),
        "new_features_added": len(ALLOC_FEATURE_NAMES_V2) - len(ALLOC_FEATURE_NAMES_V1),
    }

    # Hard-slice diagnostics to make the audit concrete and reproducible.
    def collect_stat(rows: list[dict[str, Any]], key: str) -> float:
        vals = [float(r.get("pair_relational_v2", {}).get(key, 0.0)) for r in rows]
        return _mean(vals)

    diagnostics = {
        "pair_count": len(pairs),
        "near_tie_pair_count": len(near_tie),
        "adjacent_pair_count": len(adjacent),
        "near_tie_mean_rank_gap_abs": collect_stat(near_tie, "rank_gap_abs"),
        "near_tie_mean_score_gap_abs": collect_stat(near_tie, "score_gap_abs"),
        "near_tie_mean_uncertainty_gap_abs": collect_stat(near_tie, "uncertainty_gap_abs"),
        "adjacent_mean_rank_gap_abs": collect_stat(adjacent, "rank_gap_abs"),
        "adjacent_mean_score_gap_abs": collect_stat(adjacent, "score_gap_abs"),
    }

    payload = {
        "run_id": args.run_id,
        "labels_dir": args.labels_dir,
        "coverage": coverage,
        "diagnostics": diagnostics,
        "feature_names_v1": ALLOC_FEATURE_NAMES_V1,
        "feature_names_v2": ALLOC_FEATURE_NAMES_V2,
    }
    (out_dir / "feature_audit.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# Hard-case feature audit",
        "",
        f"- labels_dir: `{args.labels_dir}`",
        f"- v1 feature count: `{coverage['v1_feature_count']}`",
        f"- v2 feature count: `{coverage['v2_feature_count']}`",
        f"- newly added features: `{coverage['new_features_added']}`",
        "",
        "## Targeted hard-case signals",
    ]
    for k, v in coverage["signals"].items():
        lines.append(f"- {k}: {', '.join(v)}")
    lines.extend([
        "",
        "## Hard-slice diagnostics",
        f"- near_tie_pair_count: `{diagnostics['near_tie_pair_count']}`",
        f"- adjacent_pair_count: `{diagnostics['adjacent_pair_count']}`",
        f"- near_tie_mean_rank_gap_abs: `{diagnostics['near_tie_mean_rank_gap_abs']:.4f}`",
        f"- near_tie_mean_score_gap_abs: `{diagnostics['near_tie_mean_score_gap_abs']:.4f}`",
        f"- near_tie_mean_uncertainty_gap_abs: `{diagnostics['near_tie_mean_uncertainty_gap_abs']:.4f}`",
        f"- adjacent_mean_rank_gap_abs: `{diagnostics['adjacent_mean_rank_gap_abs']:.4f}`",
    ])
    (out_dir / "feature_audit.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({"output_dir": str(out_dir), "feature_audit": str(out_dir / 'feature_audit.json')}, indent=2))


if __name__ == "__main__":
    main()
