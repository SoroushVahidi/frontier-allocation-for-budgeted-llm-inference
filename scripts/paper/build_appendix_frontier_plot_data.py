#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from statistics import mean

from scripts.paper.artifact_utils import PAPER_PLOT_DIR, as_float, ensure_output_dirs, load_inputs, read_csv, write_csv


def main() -> None:
    ensure_output_dirs()
    inputs = load_inputs()
    per_seed = read_csv(inputs.full_bundle_run / "per_seed_method_metrics.csv")

    grouped = {}
    for r in per_seed:
        key = (r["dataset"], r["budget"], r["method"])
        grouped.setdefault(key, []).append(r)

    out = []
    for (dataset, budget, method), rows in sorted(grouped.items()):
        acc = mean(as_float(r["accuracy"]) for r in rows)
        acts = mean(as_float(r["avg_actions"]) for r in rows)
        out.append(
            {
                "dataset": dataset,
                "budget": int(budget),
                "method": method,
                "mean_accuracy": acc,
                "mean_avg_actions": acts,
                "n_seed_rows": len(rows),
            }
        )
    write_csv(PAPER_PLOT_DIR / "appendix_per_dataset_frontier_curves.csv", out)


if __name__ == "__main__":
    main()
