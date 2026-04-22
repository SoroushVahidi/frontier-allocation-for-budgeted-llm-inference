#!/usr/bin/env python3
"""Repackage existing strict_f3 manuscript-surface ablation artifacts.

This script is explicitly non-evaluative: it reads existing machine-readable
artifacts and writes a paper-facing package with provenance links.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List


SOURCE_DIR = Path("outputs/manuscript_surface_component_ablation_20260422T172218Z")
SOURCE_REPORT = Path("docs/MANUSCRIPT_SURFACE_COMPONENT_ABLATION_REPORT_2026_04_22.md")
SOURCE_RUN_REPORT = Path("docs/MANUSCRIPT_SURFACE_COMPONENT_ABLATION_20260422T172218Z.md")


def _read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _write_csv(path: Path, rows: List[Dict[str, object]], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _read_json(path: Path) -> Dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _f(x: float, ndigits: int = 6) -> str:
    return f"{x:.{ndigits}f}"


def _variant_rows(aggregate_rows: List[Dict[str, str]]) -> Dict[str, Dict[str, str]]:
    return {row["variant"]: row for row in aggregate_rows}


def _build_budget_frontier(per_case_rows: List[Dict[str, str]]) -> List[Dict[str, object]]:
    grouped: Dict[tuple, List[Dict[str, str]]] = defaultdict(list)
    for row in per_case_rows:
        key = (row["variant"], int(row["budget"]))
        grouped[key].append(row)
    out: List[Dict[str, object]] = []
    for (variant, budget), rows in sorted(grouped.items(), key=lambda x: (x[0][0], x[0][1])):
        n = len(rows)
        accuracy = sum(1.0 if r["correct"] == "True" else 0.0 for r in rows) / n if n else 0.0
        avg_actions = sum(float(r["actions"]) for r in rows) / n if n else 0.0
        avg_expansions = sum(float(r["expansions"]) for r in rows) / n if n else 0.0
        avg_verifications = sum(float(r["verifications"]) for r in rows) / n if n else 0.0
        out.append(
            {
                "variant": variant,
                "budget": budget,
                "n_cases": n,
                "accuracy": _f(accuracy),
                "avg_actions": _f(avg_actions),
                "avg_expansions": _f(avg_expansions),
                "avg_verifications": _f(avg_verifications),
            }
        )
    return out


def _build_anti_collapse_plot_data(compute_rows: List[Dict[str, str]]) -> List[Dict[str, object]]:
    out: List[Dict[str, object]] = []
    for row in compute_rows:
        out.append(
            {
                "variant": row["variant"],
                "repeated_same_family_case_rate": row["repeated_same_family_case_rate"],
                "avg_max_family_expansion_share": row["avg_max_family_expansion_share"],
                "avg_longest_same_family_run": row["avg_longest_same_family_run"],
                "low_marginal_gain_trigger_rate": row["low_marginal_gain_trigger_rate"],
                "avg_actions": row["avg_actions"],
                "avg_expansions": row["avg_expansions"],
                "avg_verifications": row["avg_verifications"],
            }
        )
    return out


def _build_component_summary_table(
    aggregate_rows: List[Dict[str, str]],
    failure_rows: List[Dict[str, str]],
    strongest_reduced_variant: str,
) -> List[Dict[str, object]]:
    by_variant = _variant_rows(aggregate_rows)
    full = by_variant["full_method"]
    full_acc = float(full["accuracy"])
    full_absent = int(full["absent_from_tree"])
    full_pns = int(full["present_not_selected"])
    full_olm = int(full["output_layer_mismatch"])
    failure_by_variant = {r["variant"]: r for r in failure_rows}

    mapping = [
        ("full_method", "full_strict_f3", "reference"),
        ("no_answer_support_aggregation", "no_answer_support", "answer-support aggregation"),
        ("no_anti_collapse", "no_anti_collapse", "anti-collapse controls"),
        ("no_repeat_expansion_control", "no_repeat_expansion_control", "repeat-expansion moderation"),
        ("no_output_repair", "no_output_repair", "bounded output repair"),
        ("upstream_only_core", "upstream_only_core", "upstream-only core (anti-collapse + repair removed)"),
        (strongest_reduced_variant, "strongest_reduced_variant", "best reduced variant alias"),
    ]

    out: List[Dict[str, object]] = []
    for source_variant, paper_variant, component in mapping:
        row = by_variant[source_variant]
        fr = failure_by_variant[source_variant]
        acc = float(row["accuracy"])
        absent = int(row["absent_from_tree"])
        pns = int(row["present_not_selected"])
        olm = int(row["output_layer_mismatch"])
        out.append(
            {
                "variant": paper_variant,
                "source_variant": source_variant,
                "component_intervention": component,
                "accuracy": _f(acc, 4),
                "delta_accuracy_vs_full": _f(acc - full_acc, 4),
                "absent_from_tree_n": absent,
                "delta_absent_from_tree_vs_full": absent - full_absent,
                "present_not_selected_n": pns,
                "delta_present_not_selected_vs_full": pns - full_pns,
                "output_layer_mismatch_n": olm,
                "delta_output_layer_mismatch_vs_full": olm - full_olm,
                "absent_from_tree_rate": fr["absent_from_tree_rate"],
                "present_not_selected_rate": fr["present_not_selected_rate"],
                "output_layer_mismatch_rate": fr["output_layer_mismatch_rate"],
                "avg_actions": row["avg_actions"],
            }
        )
    return out


def _copy_text(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timestamp", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    args = parser.parse_args()

    out_dir = Path(f"outputs/component_ablation_strict_f3_paper_surface/{args.timestamp}")
    doc_path = Path(f"docs/COMPONENT_ABLATION_STRICT_F3_PAPER_SURFACE_{args.timestamp}.md")

    source_manifest = _read_json(SOURCE_DIR / "manifest.json")
    source_agg_json = _read_json(SOURCE_DIR / "aggregate_summary.json")
    aggregate_rows = _read_csv(SOURCE_DIR / "aggregate_summary.csv")
    per_dataset_rows = _read_csv(SOURCE_DIR / "per_dataset_summary.csv")
    per_seed_rows = _read_csv(SOURCE_DIR / "per_seed_summary.csv")
    failure_rows = _read_csv(SOURCE_DIR / "failure_decomposition.csv")
    compute_rows = _read_csv(SOURCE_DIR / "compute_allocation_diagnostics.csv")
    per_case_rows = _read_csv(SOURCE_DIR / "per_case_results.csv")

    strongest_reduced = str(source_agg_json.get("strongest_reduced_variant", "no_anti_collapse"))
    variant_lookup = _variant_rows(aggregate_rows)

    # Core required files.
    eval_manifest = {
        "artifact_family": "component_ablation_strict_f3_paper_surface",
        "packaging_timestamp": args.timestamp,
        "provenance": {
            "source_output_dir": str(SOURCE_DIR),
            "source_manifest": str(SOURCE_DIR / "manifest.json"),
            "source_aggregate_summary_json": str(SOURCE_DIR / "aggregate_summary.json"),
            "source_report": str(SOURCE_REPORT),
            "source_run_report": str(SOURCE_RUN_REPORT),
            "non_duplicative_packaging_only": True,
            "evaluation_rerun_performed": False,
        },
        "surface": source_agg_json["surface"],
        "variants": source_agg_json["variants"],
        "strongest_reduced_variant": strongest_reduced,
    }
    _write_json(out_dir / "eval_manifest.json", eval_manifest)

    _write_json(out_dir / "aggregate_summary.json", source_agg_json)
    _copy_text(SOURCE_DIR / "per_dataset_summary.csv", out_dir / "per_dataset_summary.csv")
    _copy_text(SOURCE_DIR / "per_seed_summary.csv", out_dir / "per_seed_summary.csv")
    _copy_text(SOURCE_DIR / "failure_decomposition.csv", out_dir / "failure_decomposition.csv")

    collapse_rows = [
        {
            "variant": r["variant"],
            "avg_max_family_expansion_share": r["avg_max_family_expansion_share"],
            "avg_longest_same_family_run": r["avg_longest_same_family_run"],
            "repeated_same_family_case_rate": r["repeated_same_family_case_rate"],
            "low_marginal_gain_trigger_rate": r["low_marginal_gain_trigger_rate"],
        }
        for r in compute_rows
    ]
    _write_csv(
        out_dir / "collapse_diagnostics.csv",
        collapse_rows,
        [
            "variant",
            "avg_max_family_expansion_share",
            "avg_longest_same_family_run",
            "repeated_same_family_case_rate",
            "low_marginal_gain_trigger_rate",
        ],
    )

    _write_csv(
        out_dir / "action_compute_summary.csv",
        compute_rows,
        [
            "variant",
            "avg_actions",
            "avg_expansions",
            "avg_verifications",
            "avg_max_family_expansion_share",
            "avg_longest_same_family_run",
            "repeated_same_family_case_rate",
            "low_marginal_gain_trigger_rate",
        ],
    )

    comparison_rows = []
    full_acc = float(variant_lookup["full_method"]["accuracy"])
    for row in aggregate_rows:
        comparison_rows.append(
            {
                "variant": row["variant"],
                "n_cases": row["n_cases"],
                "accuracy": row["accuracy"],
                "delta_accuracy_vs_full": _f(float(row["accuracy"]) - full_acc, 6),
                "absent_from_tree": row["absent_from_tree"],
                "present_not_selected": row["present_not_selected"],
                "output_layer_mismatch": row["output_layer_mismatch"],
                "avg_actions": row["avg_actions"],
                "avg_expansions": row["avg_expansions"],
                "avg_verifications": row["avg_verifications"],
            }
        )
    _write_csv(
        out_dir / "comparison_table.csv",
        comparison_rows,
        [
            "variant",
            "n_cases",
            "accuracy",
            "delta_accuracy_vs_full",
            "absent_from_tree",
            "present_not_selected",
            "output_layer_mismatch",
            "avg_actions",
            "avg_expansions",
            "avg_verifications",
        ],
    )

    notes = {
        "strongest_reduced_variant": strongest_reduced,
        "component_most_critical_for_accuracy": "no_repeat_expansion_control",
        "component_most_critical_for_absent_from_tree": "no_repeat_expansion_control",
        "output_repair_secondary_effect_supported": True,
        "manuscript_narrative_support": "partial",
        "narrative_caveat": "Some removals improve bounded-surface accuracy; claims should be component-specific and conservative.",
        "source_of_truth": {
            "output_dir": str(SOURCE_DIR),
            "reports": [str(SOURCE_REPORT), str(SOURCE_RUN_REPORT)],
        },
    }
    _write_json(out_dir / "ablation_decision_notes.json", notes)

    # Figure-ready files.
    budget_frontier_rows = _build_budget_frontier(per_case_rows)
    _write_csv(
        out_dir / "budget_performance_frontier.csv",
        budget_frontier_rows,
        [
            "variant",
            "budget",
            "n_cases",
            "accuracy",
            "avg_actions",
            "avg_expansions",
            "avg_verifications",
        ],
    )

    (out_dir / "oracle_gap_regret.csv").write_text(
        "status,note\n"
        "not_derived,Oracle-gap/frontier-regret cannot be honestly derived from this ablation bundle because oracle/reference-best columns are not present in source machine-readable artifacts.\n",
        encoding="utf-8",
    )

    _write_csv(
        out_dir / "anti_collapse_plot_data.csv",
        _build_anti_collapse_plot_data(compute_rows),
        [
            "variant",
            "repeated_same_family_case_rate",
            "avg_max_family_expansion_share",
            "avg_longest_same_family_run",
            "low_marginal_gain_trigger_rate",
            "avg_actions",
            "avg_expansions",
            "avg_verifications",
        ],
    )

    _copy_text(SOURCE_DIR / "failure_decomposition.csv", out_dir / "failure_decomposition_plot_data.csv")

    component_summary = _build_component_summary_table(aggregate_rows, failure_rows, strongest_reduced)
    _write_csv(
        out_dir / "component_summary_table.csv",
        component_summary,
        [
            "variant",
            "source_variant",
            "component_intervention",
            "accuracy",
            "delta_accuracy_vs_full",
            "absent_from_tree_n",
            "delta_absent_from_tree_vs_full",
            "present_not_selected_n",
            "delta_present_not_selected_vs_full",
            "output_layer_mismatch_n",
            "delta_output_layer_mismatch_vs_full",
            "absent_from_tree_rate",
            "present_not_selected_rate",
            "output_layer_mismatch_rate",
            "avg_actions",
        ],
    )

    summary_md = f"""# Component Ablation Strict-F3 Paper Surface ({args.timestamp})

This package is a non-duplicative consolidation of an existing strict_f3 manuscript-surface ablation run.

## Provenance
- Source outputs: `{SOURCE_DIR}`
- Source reports: `{SOURCE_REPORT}`, `{SOURCE_RUN_REPORT}`
- Evaluation rerun: `False`

## Surface
- Canonical source: `outputs/canonical_full_method_ranking_20260421T212948Z`
- Method lock: `strict_f3`
- Datasets: openai/gsm8k, HuggingFaceH4/MATH-500, HuggingFaceH4/aime_2024
- Seeds: 11, 23
- Budgets: 4, 6, 8

## Key findings carried forward
- Largest accuracy drop from full strict_f3: `no_repeat_expansion_control`
- Largest absent_from_tree worsening: `no_repeat_expansion_control`
- Output repair appears secondary on this bounded manuscript surface.
- Narrative support status: partial (component behavior is variant-dependent).
"""
    (out_dir / "summary.md").write_text(summary_md, encoding="utf-8")

    full = variant_lookup["full_method"]
    no_repeat = variant_lookup["no_repeat_expansion_control"]
    no_output = variant_lookup["no_output_repair"]
    no_anti = variant_lookup["no_anti_collapse"]

    report = f"""# Component Ablation Strict-F3 Paper Surface ({args.timestamp})

## Scope and non-duplication
This report performs a packaging-only consolidation of an existing strict_f3 manuscript-surface component ablation.
No evaluation was rerun and no outcomes were altered.

## Source-of-truth artifacts
- `{SOURCE_REPORT}`
- `{SOURCE_RUN_REPORT}`
- `{SOURCE_DIR}`

## Exact manuscript surface used
- Canonical matched surface: `outputs/canonical_full_method_ranking_20260421T212948Z`
- Method lock: `strict_f3`
- Datasets: `openai/gsm8k`, `HuggingFaceH4/MATH-500`, `HuggingFaceH4/aime_2024`
- Seeds: `11`, `23`
- Budgets: `4`, `6`, `8`
- Subset size: `20` per `(dataset, seed)`

## Exact ablation variants
- `full_method`
- `no_answer_support_aggregation`
- `no_anti_collapse`
- `no_repeat_expansion_control`
- `no_output_repair`
- `upstream_only_core`
- `strongest_reduced_variant` = `{strongest_reduced}`

## Mapping from manuscript components to implementation
- Answer-support aggregation:
  - `experiments/controllers.py`: `_group_support_summary`, `_final_prediction_from_groups`
  - Toggles: `answer_support_weight`, `value_weight`
- Anti-collapse control:
  - `experiments/controllers.py`: `_anti_collapse_priority_adjustments`
  - Toggle: `enable_anti_collapse_answer_group_refinement`
- Repeated same-family expansion moderation:
  - `experiments/controllers.py`: repeat penalties and cooldown controls
  - Toggles include `repeat_expand_penalty_weight`, `repeat_expand_family_penalty_weight`, `repeated_same_branch_penalty`, `enable_low_marginal_gain_family_cooldown`
- Bounded deterministic output-layer repair:
  - `experiments/output_layer_repair.py`: `choose_repair_answer(..., enable_rescue=...)`

## Main findings from existing results
- Full strict_f3 accuracy: `{float(full["accuracy"]):.4f}`
- No repeat-expansion control accuracy: `{float(no_repeat["accuracy"]):.4f}` (largest drop)
- No output repair accuracy: `{float(no_output["accuracy"]):.4f}` (small change vs full)
- No anti-collapse accuracy: `{float(no_anti["accuracy"]):.4f}` (improves on this bounded surface)

Failure decomposition signals:
- `absent_from_tree` is worst for `no_repeat_expansion_control` (`{no_repeat["absent_from_tree"]}` vs `{full["absent_from_tree"]}` for full).
- `present_not_selected` differences are smaller and mixed across variants.
- `output_layer_mismatch` remains a narrower slice.

## Which component matters most
Within this strict_f3 manuscript surface, repeated same-family expansion moderation has the strongest marginal contribution: removing it causes the largest accuracy drop and largest `absent_from_tree` increase.

## Is output repair secondary?
Yes on this bounded surface. Disabling output repair causes only a small aggregate accuracy change (`{float(full["accuracy"]):.4f}` to `{float(no_output["accuracy"]):.4f}`), consistent with a secondary/residual role.

## Manuscript narrative status
Partially supported. The upstream-allocation narrative is supported by the sensitivity to repeat-expansion moderation and `absent_from_tree`, but not every component removal is uniformly harmful (`no_anti_collapse` improves aggregate accuracy here). Claims should remain conservative and component-specific.

## Safe wording for manuscript
- Safe: "On the matched strict_f3 manuscript surface, repeat-expansion moderation is the most critical ablated component for preserving accuracy and reducing absent-from-tree failures."
- Safe: "Output-layer repair has a secondary effect relative to upstream allocation controls on this bounded evaluation."
- Weaken: "All anti-collapse mechanisms are uniformly beneficial across this surface."
- Weaken: "Every strict_f3 subcomponent contributes positively in isolation."

## Manuscript-use guidance
- Use this table in the paper: `outputs/component_ablation_strict_f3_paper_surface/{args.timestamp}/component_summary_table.csv`
- Use this figure in the appendix: `outputs/component_ablation_strict_f3_paper_surface/{args.timestamp}/budget_performance_frontier.csv`
- Safe claims: repeat-expansion moderation is the strongest contributor; output repair is secondary on this surface.
- Claims to weaken: universal anti-collapse benefit and universal monotonic benefit of every subcomponent.
"""
    doc_path.write_text(report, encoding="utf-8")

    print(str(out_dir))
    print(str(doc_path))


if __name__ == "__main__":
    main()
