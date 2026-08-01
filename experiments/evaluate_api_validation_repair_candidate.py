"""Post-hoc evaluation of a completed (or dry-run) API validation run.

Run this AFTER `experiments/run_api_validation_repair_candidate.py` has
produced `per_example_records.jsonl` (real or `--dry-run` synthetic). It
never makes an API call itself -- it only replays already-generated
candidate answers against the same offline scoring machinery used
throughout this project's diagnostics
(`experiments/build_failure_feature_table.py`,
`experiments/stress_test_exploratory_rules.py`).

Evaluates 10 candidates on the new split:
  - canonical FTA / FIX-2+FIX-4 (unchanged selector logic)
  - repair_primary_plus_unanimity_fallback (the exploratory candidate under test)
  - primary-only rule (drilldown_majority2of3_reason_frontier_support_margin_override)
  - unanimity-only fallback (3/3 external unanimity override, ungated)
  - frontier, L1, S1, TALE (each used alone, every row)
  - External-3 majority (L1/S1/TALE vote)
  - Pooled-4 majority (offline reconstruction; frontier+L1/S1/TALE vote)

Gold labels are used only for offline scoring here (after generation), never
as a runtime decision feature -- see `rule_decision_audit.csv` in the output.
No selector logic is changed by running this script.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from experiments.build_failure_feature_table import build_feature_rows_from_specs
from experiments.drilldown_frontier_allocation_misses import decision_majority_with_agree_gate
from experiments.explore_offline_selector_rules import RuleSpec
from experiments.failure_analysis_common import write_csv, write_json, write_text
from experiments.mine_pattern_cause_repair import build_repair_rule_specs
from experiments.stress_test_exploratory_rules import (
    audit_rule_decision_legality,
    decision_canonical_fta,
    evaluate_rule_full,
    paired_bootstrap_ci,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        required=True,
        help="per_example_records.jsonl file (or a directory containing exactly one) from a completed validation run.",
    )
    parser.add_argument("--source-id", default="fresh_api_validation_split", help="Label for this evaluation source.")
    parser.add_argument("--output-dir", required=True, help="Non-destructive output directory.")
    parser.add_argument("--bootstrap-resamples", type=int, default=2000)
    parser.add_argument("--bootstrap-seed", type=int, default=1234)
    parser.add_argument(
        "--validation-suite",
        default="repair_candidate",
        choices=["repair_candidate", "pooled4_fs_le1"],
        help="Candidate set to evaluate (pooled4_fs_le1 adds frozen FTA-v2 exploratory candidate).",
    )
    return parser.parse_args()


def _decision_method_only(field: str):
    def _decision(row: dict[str, Any]) -> str | None:
        return row.get(field)

    return _decision


def decision_external3_strict_normalized(row: dict[str, Any]) -> str | None:
    from experiments.freeze_guarded_majority_candidate import external3_valid_majority_normalized

    return external3_valid_majority_normalized(row)


def decision_pooled4_normalized_plurality_tiebreak(row: dict[str, Any]) -> str | None:
    from experiments.pooled4_benefit_risk_classifier import pooled4_normalized

    return pooled4_normalized(row)


def build_pooled4_fs_le1_validation_specs() -> list[RuleSpec]:
    from experiments.freeze_pooled4_fs_le1_notie_candidate import CANDIDATE_NAME, decision_frozen_candidate

    repair_primary = next(s for s in build_repair_rule_specs() if s.name == "repair_primary_plus_unanimity_fallback")
    specs = [
        RuleSpec(
            name="baseline_canonical_fta",
            family="baseline",
            description="Canonical FTA / FIX-2+FIX-4 (no additional override).",
            decision_fn=decision_canonical_fta,
        ),
        RuleSpec(
            name=CANDIDATE_NAME,
            family="exploratory_frozen_not_promoted",
            description="Pooled-4 unique plurality override when fs<=1 and not Pooled-4 tie.",
            decision_fn=decision_frozen_candidate,
        ),
        RuleSpec(
            name="baseline_pooled4_normalized_plurality_tiebreak",
            family="baseline",
            description="Pooled-4 normalized plurality with frontier-first tie order.",
            decision_fn=decision_pooled4_normalized_plurality_tiebreak,
        ),
        RuleSpec(
            name="baseline_external3_strict_majority_normalized",
            family="baseline",
            description="External-3 strict 2-of-3 majority on normalized L1/S1/TALE.",
            decision_fn=decision_external3_strict_normalized,
        ),
        RuleSpec(
            name="repair_primary_plus_unanimity_fallback",
            family="repair_candidate_comparison",
            description="Prior repair candidate (comparison only).",
            decision_fn=repair_primary.decision_fn,
        ),
    ]
    for label, field in (
        ("frontier_only", "frontier_answer_canonical"),
        ("l1_only", "l1_answer_canonical"),
        ("s1_only", "s1_answer_canonical"),
        ("tale_only", "tale_answer_canonical"),
    ):
        specs.append(
            RuleSpec(
                name=label,
                family="single_method_baseline",
                description=f"Always use the {label.split('_')[0].upper()} candidate answer.",
                decision_fn=_decision_method_only(field),
            )
        )
    names = [s.name for s in specs]
    assert len(names) == len(set(names)), f"duplicate candidate names: {names}"
    return specs


def build_candidate_specs() -> list[RuleSpec]:
    specs = list(build_repair_rule_specs())  # canonical_fta, external3, pooled4, primary, primary+unanimity_fallback
    specs.append(
        RuleSpec(
            name="unanimity_only_fallback",
            family="repair_candidate",
            description="3/3 external-unanimity override only, ungated (no override_reason/support/cpc gate).",
            decision_fn=lambda row: decision_majority_with_agree_gate(row, unanimous_only=True),
        )
    )
    for label, field in (
        ("frontier_only", "frontier_answer_canonical"),
        ("l1_only", "l1_answer_canonical"),
        ("s1_only", "s1_answer_canonical"),
        ("tale_only", "tale_answer_canonical"),
    ):
        specs.append(
            RuleSpec(
                name=label,
                family="single_method_baseline",
                description=f"Always use the {label.split('_')[0].upper()} candidate answer, every row.",
                decision_fn=_decision_method_only(field),
            )
        )
    names = [s.name for s in specs]
    assert len(names) == len(set(names)), f"duplicate candidate names: {names}"
    return specs


def _resolve_input_path(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_file():
        return path
    if path.is_dir():
        matches = sorted(path.rglob("per_example_records.jsonl"))
        if len(matches) == 1:
            return matches[0]
        raise ValueError(f"expected exactly one per_example_records.jsonl under {path}, found {len(matches)}")
    raise FileNotFoundError(path)


def _error_class_summary(per_row: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"correct": 0, "wrong_answer": 0, "no_answer": 0}
    for r in per_row:
        if r["selected_correct"]:
            counts["correct"] += 1
        elif r["selected_answer"] in (None, ""):
            counts["no_answer"] += 1
        else:
            counts["wrong_answer"] += 1
    return counts


def evaluate_all(all_rows: list[dict[str, Any]], specs: list[RuleSpec], *, bootstrap_resamples: int, bootstrap_seed: int) -> dict[str, Any]:
    evaluations = {spec.name: evaluate_rule_full(all_rows, spec) for spec in specs}
    canonical = evaluations["baseline_canonical_fta"]
    bootstrap_rows = []
    for name, ev in evaluations.items():
        if name == "baseline_canonical_fta":
            continue
        result = paired_bootstrap_ci(
            ev["per_row"], canonical["per_row"], n_resamples=bootstrap_resamples, seed=bootstrap_seed, stratify_by_source=True
        )
        bootstrap_rows.append({"comparison_name": f"{name}_vs_canonical_fta", **result})
    audit_rows = audit_rule_decision_legality(specs)
    return {"evaluations": evaluations, "bootstrap_rows": bootstrap_rows, "audit_rows": audit_rows}


def main() -> int:
    args = parse_args()
    input_path = _resolve_input_path(args.input)
    specs = [{"source_id": args.source_id, "path": str(input_path), "rationale": "fresh API validation split evaluation"}]
    feature_rows, build_summary = build_feature_rows_from_specs(specs)

    candidate_specs = (
        build_pooled4_fs_le1_validation_specs()
        if args.validation_suite == "pooled4_fs_le1"
        else build_candidate_specs()
    )
    result = evaluate_all(
        feature_rows, candidate_specs, bootstrap_resamples=args.bootstrap_resamples, bootstrap_seed=args.bootstrap_seed
    )

    output_dir = Path(args.output_dir)

    results_rows = []
    for name, ev in result["evaluations"].items():
        error_summary = _error_class_summary(ev["per_row"])
        results_rows.append(
            {
                "candidate": name,
                "family": ev["family"],
                "accuracy": ev["accuracy"],
                "correct_count": ev["correct_count"],
                "row_count": ev["row_count"],
                "wins_vs_canonical_fta": ev["wins_vs_canonical_fta"],
                "losses_vs_canonical_fta": ev["losses_vs_canonical_fta"],
                "ties_vs_canonical_fta": ev["ties_vs_canonical_fta"],
                "net_wins": ev["net_wins"],
                "regression_rate_among_fta_correct": ev["regression_rate_among_fta_correct"],
                "error_correct": error_summary["correct"],
                "error_wrong_answer": error_summary["wrong_answer"],
                "error_no_answer": error_summary["no_answer"],
            }
        )
    write_csv(output_dir / "validation_results.csv", results_rows, list(results_rows[0].keys()))

    source_rows = []
    for name, ev in result["evaluations"].items():
        for source_id, item in ev["per_source"].items():
            source_rows.append(
                {
                    "candidate": name,
                    "source_id": source_id,
                    "seed": item["seed"],
                    "row_count": item["row_count"],
                    "accuracy": item["accuracy"],
                    "wins": item["wins"],
                    "losses": item["losses"],
                    "net_wins": item["net_wins"],
                }
            )
    write_csv(output_dir / "validation_source_breakdown.csv", source_rows, list(source_rows[0].keys()))

    write_csv(
        output_dir / "validation_bootstrap_ci.csv",
        result["bootstrap_rows"],
        list(result["bootstrap_rows"][0].keys()) if result["bootstrap_rows"] else ["comparison_name"],
    )
    write_csv(output_dir / "validation_decision_legality_audit.csv", result["audit_rows"], list(result["audit_rows"][0].keys()))
    write_json(output_dir / "validation_build_summary.json", build_summary)

    report_lines = ["# Fresh-Split Validation Report", "", f"Input: `{input_path}`", ""]
    for row in sorted(results_rows, key=lambda r: -r["net_wins"]):
        report_lines.append(
            f"- `{row['candidate']}`: accuracy={row['accuracy']:.4f}, wins={row['wins_vs_canonical_fta']}, "
            f"losses={row['losses_vs_canonical_fta']}, net_wins={row['net_wins']}"
        )
    report_lines.append("")
    report_lines.append("## Bootstrap CIs vs canonical FTA")
    report_lines.append("")
    for row in result["bootstrap_rows"]:
        report_lines.append(
            f"- `{row['comparison_name']}`: delta={row['observed_delta_accuracy']}, "
            f"95% CI=[{row['ci_low']}, {row['ci_high']}], includes_zero={row['includes_zero']}"
        )
    write_text(output_dir / "validation_report.md", "\n".join(report_lines).rstrip() + "\n")

    print(
        json.dumps(
            {
                "input": str(input_path),
                "output_dir": str(output_dir),
                "row_count": len(feature_rows),
                "candidates_evaluated": len(candidate_specs),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
