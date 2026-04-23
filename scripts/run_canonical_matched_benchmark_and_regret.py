#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_SURFACE_DIR = REPO_ROOT / "outputs/matched_surface_multiseed_main_comparison_20260423T002000Z"
DECISION_MATRIX_PATH = REPO_ROOT / "docs/external_baseline_paper_readiness_decision_matrix.json"
REGIME_CONTEXT_DIR = REPO_ROOT / "outputs/canonical_matched_surface_regime_breakdown_20260423T012859Z"


@dataclass(frozen=True)
class SurfaceContract:
    datasets: list[str]
    budgets: list[int]
    seeds: list[int]
    budget_unit: str
    subset_size_per_dataset_seed: int
    grading: str
    accounting: str


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build canonical manuscript-facing matched benchmark + bounded hindsight frontier/regret bundle "
            "on the exact matched-surface comparison rows."
        )
    )
    parser.add_argument("--timestamp", default=utc_timestamp())
    parser.add_argument("--input-dir", default=str(CANONICAL_SURFACE_DIR.relative_to(REPO_ROOT)))
    parser.add_argument("--decision-matrix", default=str(DECISION_MATRIX_PATH.relative_to(REPO_ROOT)))
    parser.add_argument("--regime-context", default=str(REGIME_CONTEXT_DIR.relative_to(REPO_ROOT)))
    parser.add_argument(
        "--output-prefix",
        default="outputs/canonical_matched_benchmark_and_regret_",
        help="Output directory prefix. Timestamp is appended automatically.",
    )
    return parser.parse_args()


def _mean_or_nan(series: pd.Series) -> float:
    if len(series) == 0:
        return float("nan")
    return float(series.mean())


def _build_method_status_matrix(
    surface_methods: list[str],
    decision_rows: list[dict[str, Any]],
) -> pd.DataFrame:
    external_decisions = {
        str(row.get("baseline_key")): row
        for row in decision_rows
        if isinstance(row, dict) and row.get("baseline_key")
    }

    canonical_external_map = {
        "s1": "s1_simple_test_time_scaling",
        "tale": "tale_token_budget_aware_reasoning",
        "l1_max": "l1_length_control_rl",
        "l1_exact": "l1_length_control_rl",
    }

    rows: list[dict[str, Any]] = []
    for method in sorted(surface_methods):
        if method in {"strict_f3", "strict_gate1_cap_k6", "strict_f2"}:
            rows.append(
                {
                    "method": method,
                    "method_group": "internal_main_family",
                    "in_canonical_surface": True,
                    "comparator_class": "direct_matched",
                    "main_table_eligible": True,
                    "appendix_only": False,
                    "fairness_reason": "Internal method on exact matched-surface contract.",
                    "source": "canonical_surface",
                }
            )
            continue

        mapped = canonical_external_map.get(method)
        dec = external_decisions.get(mapped) if mapped else None
        readiness = (dec or {}).get("readiness_decision")
        fair_flag = (dec or {}).get("neurips_main_table_fair")
        main_table_ok = bool(readiness == "main_table_ready" and isinstance(fair_flag, str) and fair_flag.startswith("yes"))
        rows.append(
            {
                "method": method,
                "method_group": "external_near_direct" if method in canonical_external_map else "other",
                "in_canonical_surface": True,
                "comparator_class": (dec or {}).get("control_equivalence", "direct_matched"),
                "main_table_eligible": main_table_ok,
                "appendix_only": not main_table_ok,
                "fairness_reason": (dec or {}).get(
                    "claim_boundary",
                    "Included in matched-surface rows but missing main-table fairness closure.",
                ),
                "source": "external_baseline_paper_readiness_decision_matrix",
            }
        )

    for row in decision_rows:
        baseline = str(row.get("baseline_key", "")).strip()
        if not baseline:
            continue
        if baseline in canonical_external_map.values():
            continue
        rows.append(
            {
                "method": baseline,
                "method_group": "external_adjacent_or_discuss_only",
                "in_canonical_surface": False,
                "comparator_class": row.get("control_equivalence", "adjacent"),
                "main_table_eligible": False,
                "appendix_only": True,
                "fairness_reason": row.get("claim_boundary", "adjacent or discuss-only comparator"),
                "source": "external_baseline_paper_readiness_decision_matrix",
            }
        )

    out = pd.DataFrame(rows).drop_duplicates(subset=["method"], keep="first")
    return out.sort_values(["in_canonical_surface", "main_table_eligible", "method"], ascending=[False, False, True]).reset_index(drop=True)


def main() -> None:
    args = parse_args()

    input_dir = REPO_ROOT / args.input_dir
    if not input_dir.exists():
        raise FileNotFoundError(f"Missing input directory: {input_dir}")

    raw_case_path = input_dir / "raw_case_results.csv"
    if not raw_case_path.exists():
        raise FileNotFoundError(f"Missing raw case rows: {raw_case_path}")

    with (REPO_ROOT / args.decision_matrix).open("r", encoding="utf-8") as f:
        decision_matrix = json.load(f)
    decision_rows = decision_matrix.get("rows", [])

    raw = pd.read_csv(raw_case_path)
    needed_cols = {"dataset", "seed", "budget", "example_id", "method", "is_correct", "actions", "expansions", "verifications"}
    missing = sorted(needed_cols - set(raw.columns))
    if missing:
        raise ValueError(f"raw_case_results.csv missing required columns: {missing}")

    for col in ["seed", "budget", "is_correct", "actions", "expansions", "verifications"]:
        raw[col] = pd.to_numeric(raw[col], errors="coerce")
    raw["is_correct"] = raw["is_correct"].fillna(0).astype(int)

    contract = SurfaceContract(
        datasets=sorted(raw["dataset"].dropna().astype(str).unique().tolist()),
        budgets=sorted(raw["budget"].dropna().astype(int).unique().tolist()),
        seeds=sorted(raw["seed"].dropna().astype(int).unique().tolist()),
        budget_unit="actions",
        subset_size_per_dataset_seed=int(raw[["dataset", "seed", "example_id"]].drop_duplicates().groupby(["dataset", "seed"]).size().mode().iloc[0]),
        grading="is_correct from canonical answer extraction/repair lane",
        accounting="matched actions/expansions/verifications accounting on identical per-case rows",
    )

    method_status = _build_method_status_matrix(sorted(raw["method"].astype(str).unique().tolist()), decision_rows)
    main_methods = set(method_status.loc[method_status["main_table_eligible"], "method"].astype(str).tolist())

    if not main_methods:
        raise RuntimeError("No main-table-eligible methods found; cannot build benchmark bundle.")

    # Bounded hindsight reference on exact same case rows, restricted to fair main-table-eligible methods.
    main_surface = raw[raw["method"].isin(main_methods)].copy()
    ref = (
        main_surface.groupby(["dataset", "seed", "budget", "example_id"], as_index=False)["is_correct"]
        .max()
        .rename(columns={"is_correct": "reference_is_correct"})
    )
    joined = raw.merge(ref, on=["dataset", "seed", "budget", "example_id"], how="inner")
    joined["regret_gap"] = joined["reference_is_correct"] - joined["is_correct"]

    # Summaries
    aggregate = (
        joined.groupby("method", as_index=False)
        .agg(
            n_cases=("is_correct", "size"),
            accuracy=("is_correct", "mean"),
            reference_accuracy=("reference_is_correct", "mean"),
            average_regret=("regret_gap", "mean"),
            avg_actions=("actions", "mean"),
            avg_expansions=("expansions", "mean"),
            avg_verifications=("verifications", "mean"),
        )
        .sort_values(["accuracy", "average_regret"], ascending=[False, True])
        .reset_index(drop=True)
    )
    aggregate["raw_score_rank"] = aggregate["accuracy"].rank(method="min", ascending=False).astype(int)
    aggregate["regret_rank"] = aggregate["average_regret"].rank(method="min", ascending=True).astype(int)
    aggregate["headroom_to_reference"] = aggregate["reference_accuracy"] - aggregate["accuracy"]

    per_dataset = (
        joined.groupby(["method", "dataset"], as_index=False)
        .agg(accuracy=("is_correct", "mean"), reference_accuracy=("reference_is_correct", "mean"), regret=("regret_gap", "mean"), n_cases=("is_correct", "size"))
        .sort_values(["dataset", "accuracy"], ascending=[True, False])
    )
    per_budget = (
        joined.groupby(["method", "budget"], as_index=False)
        .agg(accuracy=("is_correct", "mean"), reference_accuracy=("reference_is_correct", "mean"), regret=("regret_gap", "mean"), n_cases=("is_correct", "size"))
        .sort_values(["budget", "accuracy"], ascending=[True, False])
    )
    regime_breakdown = (
        joined.groupby(["dataset", "budget", "method"], as_index=False)
        .agg(accuracy=("is_correct", "mean"), reference_accuracy=("reference_is_correct", "mean"), regret=("regret_gap", "mean"), n_cases=("is_correct", "size"))
        .sort_values(["dataset", "budget", "accuracy"], ascending=[True, True, False])
    )
    seed_summary = (
        joined.groupby(["method", "seed"], as_index=False)
        .agg(accuracy=("is_correct", "mean"), regret=("regret_gap", "mean"), n_cases=("is_correct", "size"))
        .sort_values(["seed", "accuracy"], ascending=[True, False])
    )

    frontier_plot = per_budget[["method", "budget", "accuracy", "reference_accuracy", "n_cases"]].copy()
    frontier_plot = frontier_plot.sort_values(["method", "budget"]).reset_index(drop=True)
    regret_plot = per_budget[["method", "budget", "regret", "reference_accuracy", "accuracy", "n_cases"]].copy()

    top_methods = aggregate.sort_values(["accuracy", "average_regret"], ascending=[False, True])["method"].head(3).tolist()
    pairwise_rows: list[dict[str, Any]] = []
    for i, m1 in enumerate(top_methods):
        for m2 in top_methods[i + 1 :]:
            r1 = float(aggregate.loc[aggregate["method"] == m1, "average_regret"].iloc[0])
            r2 = float(aggregate.loc[aggregate["method"] == m2, "average_regret"].iloc[0])
            a1 = float(aggregate.loc[aggregate["method"] == m1, "accuracy"].iloc[0])
            a2 = float(aggregate.loc[aggregate["method"] == m2, "accuracy"].iloc[0])
            pairwise_rows.append(
                {
                    "method_a": m1,
                    "method_b": m2,
                    "regret_delta_a_minus_b": r1 - r2,
                    "accuracy_delta_a_minus_b": a1 - a2,
                }
            )
    pairwise = pd.DataFrame(pairwise_rows)

    main_table = aggregate.merge(method_status[["method", "main_table_eligible", "fairness_reason"]], on="method", how="left")
    main_table = main_table[main_table["main_table_eligible"]].copy().sort_values(["accuracy", "average_regret"], ascending=[False, True])

    appendix_join = aggregate.merge(method_status, on="method", how="right")
    appendix_table = appendix_join[~appendix_join["main_table_eligible"].fillna(False)].copy()
    appendix_table = appendix_table.sort_values(["in_canonical_surface", "method"], ascending=[False, True])

    out_dir = REPO_ROOT / f"{args.output_prefix}{args.timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Writes
    (out_dir / "manifest.json").write_text(
        json.dumps(
            {
                "artifact_family": "canonical_matched_benchmark_and_regret",
                "run_timestamp": args.timestamp,
                "command": (
                    f"python scripts/run_canonical_matched_benchmark_and_regret.py --timestamp {args.timestamp} "
                    f"--input-dir {args.input_dir} --decision-matrix {args.decision_matrix} --regime-context {args.regime_context}"
                ),
                "source_artifacts": {
                    "matched_surface_multiseed": str(Path(args.input_dir) / "raw_case_results.csv"),
                    "method_fairness_matrix": args.decision_matrix,
                    "regime_context_reference": args.regime_context,
                },
                "benchmark_contract": {
                    "canonical_surface_type": "matched datasets x matched budgets x matched seeds x matched extraction/grading",
                    "datasets": contract.datasets,
                    "budgets": contract.budgets,
                    "seeds": contract.seeds,
                    "budget_unit": contract.budget_unit,
                    "subset_size_per_dataset_seed": contract.subset_size_per_dataset_seed,
                    "grading": contract.grading,
                    "compute_accounting": contract.accounting,
                    "surface_case_count": int(len(raw[["dataset", "seed", "budget", "example_id"]].drop_duplicates())),
                },
                "main_table_methods": sorted(main_methods),
                "all_surface_methods": sorted(raw["method"].astype(str).unique().tolist()),
                "output_files": [
                    "manifest.json",
                    "aggregate_summary.csv",
                    "per_dataset_summary.csv",
                    "per_budget_summary.csv",
                    "regime_breakdown.csv",
                    "seed_summary.csv",
                    "frontier_plot_data.csv",
                    "regret_plot_data.csv",
                    "reference_definition.json",
                    "method_status_matrix.csv",
                    "main_table.csv",
                    "appendix_table.csv",
                    "pairwise_regret_deltas.csv",
                    "summary.md",
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    reference_def = {
        "reference_name": "bounded_hindsight_upper_envelope_on_matched_surface",
        "is_true_oracle": False,
        "description": (
            "For each exact (dataset, seed, budget, example_id) case, the reference equals max is_correct across "
            "main-table-eligible methods observed on the same matched surface."
        ),
        "formula": {
            "reference_case_value": "R(c) = max_{m in M_main} score(m, c)",
            "method_regret_case": "g(m,c) = R(c) - score(m,c)",
            "method_average_regret": "G(m) = mean_c g(m,c)",
        },
        "score_domain": "binary correctness in {0,1}",
        "fairness_scope": "No cross-surface mixing; only methods on the same matched surface are used.",
        "limitations": [
            "This is a bounded hindsight envelope, not a causal or deployable online oracle policy.",
            "If a method is excluded from main-table eligibility for fairness reasons, it is excluded from reference construction.",
        ],
        "main_table_methods_used_for_reference": sorted(main_methods),
    }
    (out_dir / "reference_definition.json").write_text(json.dumps(reference_def, indent=2) + "\n", encoding="utf-8")

    aggregate.to_csv(out_dir / "aggregate_summary.csv", index=False)
    per_dataset.to_csv(out_dir / "per_dataset_summary.csv", index=False)
    per_budget.to_csv(out_dir / "per_budget_summary.csv", index=False)
    regime_breakdown.to_csv(out_dir / "regime_breakdown.csv", index=False)
    seed_summary.to_csv(out_dir / "seed_summary.csv", index=False)
    frontier_plot.to_csv(out_dir / "frontier_plot_data.csv", index=False)
    regret_plot.to_csv(out_dir / "regret_plot_data.csv", index=False)
    method_status.to_csv(out_dir / "method_status_matrix.csv", index=False)
    main_table.to_csv(out_dir / "main_table.csv", index=False)
    appendix_table.to_csv(out_dir / "appendix_table.csv", index=False)
    pairwise.to_csv(out_dir / "pairwise_regret_deltas.csv", index=False)

    # Manuscript-facing summary
    best_raw = aggregate.sort_values(["accuracy", "average_regret"], ascending=[False, True]).iloc[0]
    best_regret = aggregate.sort_values(["average_regret", "accuracy"], ascending=[True, False]).iloc[0]
    headroom = float(best_raw["headroom_to_reference"])
    worst_regime = regime_breakdown.sort_values(["regret", "dataset", "budget"], ascending=[False, True, True]).iloc[0]

    summary_lines = [
        "# Canonical matched benchmark + regret summary",
        "",
        "## Benchmark contract",
        f"- Canonical matched surface source: `{args.input_dir}/raw_case_results.csv`.",
        f"- Datasets: {contract.datasets}.",
        f"- Budgets (actions): {contract.budgets}.",
        f"- Seeds: {contract.seeds}.",
        f"- Subset size per (dataset, seed): {contract.subset_size_per_dataset_seed}.",
        "- Matching dimensions enforced: dataset, budget, seed, case id, extraction/grading contract, and compute accounting fields.",
        "",
        "## Reference/regret definition",
        "- Reference is **bounded hindsight upper envelope**, not a true oracle policy.",
        "- Per-case reference: max binary correctness among main-table-eligible methods on the same exact case and budget.",
        "- Regret gap: reference correctness minus method correctness (0 means method is on the attained frontier for that case).",
        "",
        "## Main safe findings",
        f"- Highest raw score on this canonical surface: `{best_raw['method']}` with accuracy {best_raw['accuracy']:.4f}.",
        f"- Closest to bounded hindsight frontier (lowest average regret): `{best_regret['method']}` with regret {best_regret['average_regret']:.4f}.",
        f"- Remaining headroom for top raw-score method vs reference: {headroom:.4f} absolute accuracy.",
        (
            f"- Largest dataset×budget regret pocket (method-level regime): dataset `{worst_regime['dataset']}`, "
            f"budget {int(worst_regime['budget'])}, method `{worst_regime['method']}`, regret {worst_regime['regret']:.4f}."
        ),
        "",
        "## Comparator eligibility and fairness",
        "- Main table includes direct matched internal methods plus near-direct external MODE A comparators marked main-table-ready.",
        "- Adjacent/control-space-mismatched external methods are auto-routed to appendix-only status.",
    ]
    (out_dir / "summary.md").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    doc_path = REPO_ROOT / f"docs/CANONICAL_MATCHED_BENCHMARK_AND_REGRET_{args.timestamp}.md"
    doc_lines = [
        f"# Canonical matched benchmark and regret bundle ({args.timestamp})",
        "",
        "## Purpose",
        "Jointly close Experiment 1 (canonical matched benchmark) and Experiment 5 (oracle headroom/regret) on one exact matched surface.",
        "",
        "## Benchmark contract",
        f"- Source rows: `{args.input_dir}/raw_case_results.csv`.",
        f"- Datasets: {contract.datasets}",
        f"- Budgets: {contract.budgets} actions",
        f"- Seeds: {contract.seeds}",
        f"- Per-(dataset,seed) subset size: {contract.subset_size_per_dataset_seed}",
        "- Strict matched dimensions: dataset × seed × budget × example_id with shared grading and accounting.",
        "",
        "## Included methods and fairness rules",
        "- Main table: methods marked `main_table_eligible=true` in `method_status_matrix.csv`.",
        "- Appendix-only: external adjacent/control-space-mismatched methods or methods without sufficient fairness closure.",
        "- Rule source: `docs/external_baseline_paper_readiness_decision_matrix.json` plus canonical matched-surface inclusion.",
        "",
        "## Reference/oracle definition",
        "- Name: `bounded_hindsight_upper_envelope_on_matched_surface`.",
        "- Not a true oracle: uses hindsight max over observed main-table methods on each exact case.",
        "- Regret definition: `regret = reference_case_value - method_case_value` with binary correctness values.",
        "- This keeps reference construction inside one fairness-closed surface.",
        "",
        "## Main results (safe claims)",
        f"- Top raw-score method: `{best_raw['method']}` (accuracy {best_raw['accuracy']:.4f}).",
        f"- Lowest-regret method: `{best_regret['method']}` (average regret {best_regret['average_regret']:.4f}).",
        f"- Headroom from top raw-score method to bounded reference: {headroom:.4f}.",
        "- Claims are regime-qualified via `regime_breakdown.csv` (dataset × budget × method).",
        "",
        "## Caveats",
        "- The reference is bounded by methods currently available on this surface; it is not a guarantee of globally attainable performance.",
        "- External comparators in appendix remain scientifically useful but are not mixed into main-table claims.",
        "",
        "## Output bundle",
        f"- `outputs/canonical_matched_benchmark_and_regret_{args.timestamp}/`",
        "- Contains machine-readable summaries, frontier/regret plot data, fairness status matrix, and manuscript-facing summary.",
    ]
    doc_path.write_text("\n".join(doc_lines) + "\n", encoding="utf-8")

    print(out_dir.relative_to(REPO_ROOT))
    print(doc_path.relative_to(REPO_ROOT))


if __name__ == "__main__":
    main()
