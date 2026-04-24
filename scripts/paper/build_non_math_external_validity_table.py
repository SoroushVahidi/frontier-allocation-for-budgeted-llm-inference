#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import random
from pathlib import Path
from typing import Any

from paper_data_sources import REPO_ROOT, write_csv, write_tex_table


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _latest_non_math_dir() -> Path:
    candidates = sorted((REPO_ROOT / "outputs").glob("non_math_external_validity_*/main_summary.csv"))
    if not candidates:
        raise FileNotFoundError("No outputs/non_math_external_validity_*/main_summary.csv artifacts found.")
    return candidates[-1].parent


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _bootstrap_ci(diffs: list[float], n_boot: int = 3000, seed: int = 0) -> tuple[float, float]:
    if not diffs:
        return (0.0, 0.0)
    rng = random.Random(seed)
    n = len(diffs)
    draws = []
    for _ in range(n_boot):
        sample = [diffs[rng.randrange(n)] for _ in range(n)]
        draws.append(_mean(sample))
    draws.sort()
    return (draws[int(0.025 * n_boot)], draws[min(int(0.975 * n_boot), n_boot - 1)])


def _perm_pvalue(diffs: list[float], n_perm: int = 3000, seed: int = 0) -> float:
    if not diffs:
        return 1.0
    rng = random.Random(seed)
    obs = abs(_mean(diffs))
    geq = 0
    for _ in range(n_perm):
        s = [1.0 if rng.random() < 0.5 else -1.0 for _ in diffs]
        stat = abs(_mean([d * ss for d, ss in zip(diffs, s)]))
        if stat >= obs - 1e-12:
            geq += 1
    return (geq + 1.0) / (n_perm + 1.0)


def _build_non_math_table(non_math_dir: Path) -> list[dict[str, Any]]:
    summary_rows = _read_csv(non_math_dir / "main_summary.csv")
    tests = _read_csv(non_math_dir / "pairwise_statistical_tests.csv")
    test_index = {(r["method_a"], r["method_b"]): r for r in tests}

    rows: list[dict[str, Any]] = []
    for r in sorted(summary_rows, key=lambda x: float(x.get("mean_accuracy", 0.0)), reverse=True):
        m = r["method"]
        paired = test_index.get((m, "self_consistency_3")) or test_index.get(("self_consistency_3", m))
        rows.append(
            {
                "method": m,
                "n_cases": int(float(r.get("n_cases", 0))),
                "mean_accuracy": round(float(r.get("mean_accuracy", 0.0)), 6),
                "avg_actions": round(float(r.get("avg_actions", 0.0)), 6),
                "delta_vs_self_consistency_3": round(float(paired.get("mean_difference", 0.0)), 6) if paired else "",
                "pvalue_vs_self_consistency_3": round(float(paired.get("permutation_p_value", 1.0)), 6) if paired else "",
            }
        )
    return rows


def _build_real_model_table() -> list[dict[str, Any]]:
    run_dirs = sorted((REPO_ROOT / "outputs").glob("real_model_ours_vs_external_validation_*"))
    if not run_dirs:
        return []

    table_rows: list[dict[str, Any]] = []
    for run in run_dirs:
        per_example = list(run.glob("*/per_example_rows.csv"))
        for px in per_example:
            provider = px.parent.name
            rows = _read_csv(px)
            if not rows:
                continue
            methods = sorted({str(r.get("method", "")) for r in rows})
            ours = [m for m in methods if m.startswith("strict_")]
            externals = [m for m in methods if m.startswith("external_") or m.startswith("self_consistency")]
            if not ours or not externals:
                continue
            by_method = {m: [r for r in rows if str(r.get("method")) == m] for m in methods}
            best_ours = max(ours, key=lambda m: _mean([float(x.get("is_correct", 0)) for x in by_method[m]]))
            best_ext = max(externals, key=lambda m: _mean([float(x.get("is_correct", 0)) for x in by_method[m]]))

            idx = {}
            for r in rows:
                idx[(r["dataset"], r["budget"], r["seed"], r["example_id"], r["method"])] = int(float(r.get("is_correct", 0)))
            diffs = []
            for k in list(idx.keys()):
                d, b, s, e, m = k
                if m != best_ours:
                    continue
                other = (d, b, s, e, best_ext)
                if other not in idx:
                    continue
                diffs.append(float(idx[k] - idx[other]))
            ci_low, ci_high = _bootstrap_ci(diffs, seed=hash((run.name, provider, "boot")) & 0xFFFFFFFF)
            p = _perm_pvalue(diffs, seed=hash((run.name, provider, "perm")) & 0xFFFFFFFF)
            table_rows.append(
                {
                    "run": run.name,
                    "provider": provider,
                    "method_a": best_ours,
                    "method_b": best_ext,
                    "accuracy_a": round(_mean([float(x.get("is_correct", 0)) for x in by_method[best_ours]]), 6),
                    "accuracy_b": round(_mean([float(x.get("is_correct", 0)) for x in by_method[best_ext]]), 6),
                    "paired_n": len(diffs),
                    "mean_difference": round(_mean(diffs), 6),
                    "bootstrap_ci_low": round(ci_low, 6),
                    "bootstrap_ci_high": round(ci_high, 6),
                    "permutation_p_value": round(p, 6),
                    "interpretation": "supportive_only" if (p < 0.05 and ci_low > 0) else "not_headline",
                }
            )
    return table_rows


def main() -> None:
    p = argparse.ArgumentParser(description="Build non-math external validity paper tables.")
    p.add_argument("--input-dir", type=Path, default=None)
    p.add_argument("--output-csv", type=Path, default=REPO_ROOT / "outputs" / "paper_tables" / "table_non_math_external_validity.csv")
    p.add_argument("--output-tex", type=Path, default=REPO_ROOT / "outputs" / "paper_tables" / "table_non_math_external_validity.tex")
    p.add_argument("--output-plot-csv", type=Path, default=REPO_ROOT / "outputs" / "paper_plot_data" / "non_math_external_validity.csv")
    p.add_argument("--output-real-csv", type=Path, default=REPO_ROOT / "outputs" / "paper_tables" / "table_real_model_quantitative_audit.csv")
    p.add_argument("--output-real-tex", type=Path, default=REPO_ROOT / "outputs" / "paper_tables" / "table_real_model_quantitative_audit.tex")
    args = p.parse_args()

    non_math_dir = args.input_dir or _latest_non_math_dir()
    rows = _build_non_math_table(non_math_dir)
    write_csv(args.output_csv, rows)
    write_tex_table(args.output_tex, rows)
    write_csv(args.output_plot_csv, rows)

    real_rows = _build_real_model_table()
    write_csv(args.output_real_csv, real_rows)
    write_tex_table(args.output_real_tex, real_rows)

    print(f"Built non-math table from {non_math_dir}")


if __name__ == "__main__":
    main()
