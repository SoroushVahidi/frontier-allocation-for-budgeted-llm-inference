#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.paper.artifact_utils import (
    FIXED_METHODS,
    PAPER_PLOT_DIR,
    allocation_diversity_from_oracle,
    ensure_output_dirs,
    load_inputs,
    read_csv,
    write_csv,
)


def main() -> None:
    ensure_output_dirs()
    inputs = load_inputs()
    per_example = read_csv(inputs.full_bundle_run / "per_example_outcomes.csv")

    method_pool = sorted({r["method"] for r in per_example if r["method"] in FIXED_METHODS or r["method"].startswith("adaptive_min_expand_")})

    grouped = {}
    for r in per_example:
        if r["method"] not in method_pool:
            continue
        key = (r["dataset"], r["seed"], r["budget"], r["example_id"])
        grouped.setdefault(key, []).append(r)

    composition_rows = []
    for (dataset, seed, budget, _), rows in sorted(grouped.items()):
        correct = [x for x in rows if str(x.get("is_correct", "")).lower() in {"1", "true"}]
        winners = [x["method"] for x in correct] if correct else [sorted(rows, key=lambda z: float(z.get("actions_used", 9999.0)))[0]["method"]]
        frac = 1.0 / max(1, len(winners))
        for w in winners:
            composition_rows.append(
                {
                    "dataset": dataset,
                    "seed": int(seed),
                    "budget": int(budget),
                    "family": w,
                    "share_contribution": frac,
                }
            )

    agg = {}
    for r in composition_rows:
        key = (r["dataset"], r["budget"], r["family"])
        agg[key] = agg.get(key, 0.0) + r["share_contribution"]

    counts = {}
    for (dataset, seed, budget, _example_id) in grouped.keys():
        counts[(dataset, budget)] = counts.get((dataset, budget), 0) + 1

    out = []
    for (dataset, budget, family), val in sorted(agg.items()):
        n = counts.get((dataset, budget), 1)
        out.append(
            {
                "dataset": dataset,
                "budget": budget,
                "family": family,
                "oracle_allocation_share": val / max(1, n),
            }
        )
    write_csv(PAPER_PLOT_DIR / "allocation_composition_by_budget.csv", out)

    diagnostics = allocation_diversity_from_oracle(per_example, method_pool)
    write_csv(PAPER_PLOT_DIR / "allocation_diversity_vs_budget.csv", diagnostics)


if __name__ == "__main__":
    main()
