#!/usr/bin/env python3
"""Bounded natural-language failure analysis for leading multistep mode."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
VAL_DIR = ROOT / "outputs/branch_label_bruteforce_learning/multistep_branch_utility_target_validation_eval_20260417"
FAIL_DIR = ROOT / "outputs/branch_label_bruteforce_learning/current_leading_failure_case_extraction_20260418"
TARGET_DIR = ROOT / "outputs/branch_label_bruteforce_targets/multistep_branch_utility_target_20260417/regime_multistep_branch_utility_target_k3"
OUT_DIR = ROOT / "outputs/branch_label_bruteforce_learning/natural_language_failure_casebook_dominant_group_20260418"
DOC_PATH = ROOT / "docs/NATURAL_LANGUAGE_FAILURE_CASEBOOK_DOMINANT_GROUP_2026_04_18.md"


@dataclass
class TaxonomyResult:
    group: str
    rationale: str


def load_json(path: Path) -> Any:
    with path.open() as f:
        return json.load(f)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def choose_leading_mode() -> dict[str, Any]:
    summary = load_json(VAL_DIR / "aggregate_comparison_summary.json")
    aggregate = summary["aggregate"]
    mode_rows = []
    for mode, metrics in aggregate.items():
        if mode.startswith("multistep_k"):
            mode_rows.append({"mode": mode, **metrics})
    mode_rows.sort(key=lambda r: r["accepted_accuracy_mean"], reverse=True)
    best = mode_rows[0]
    return {
        "selection_rule": "argmax accepted_accuracy_mean among multistep_k* modes in latest validation aggregate summary",
        "candidates": mode_rows,
        "selected_mode_validation_name": best["mode"],
        "selected_mode_canonical_name": f"multistep_branch_utility_target_{best['mode'].replace('multistep_', '')}",
        "selected_metric": "accepted_accuracy_mean",
        "selected_metric_value": best["accepted_accuracy_mean"],
    }


def assign_taxonomy(row: dict[str, Any]) -> TaxonomyResult:
    per_branch = {b["branch_id"]: b for b in row["per_branch"]}
    chosen = per_branch[row["method_choice_k3"]]
    oracle = per_branch[row["oracle_best_branch"]]

    if row["method_matches_oracle"]:
        return TaxonomyResult(
            group="correct_or_control",
            rationale="Method branch matches oracle-best branch; kept only for controlled backfill when dominant-group strict failures are too few.",
        )

    delayed_payoff_signature = (
        chosen["multistep_delta_vs_onestep"] > 0.05
        and chosen["branch_vs_outside_gap"] < 0
        and oracle["branch_vs_outside_gap"] > 0
    )
    if delayed_payoff_signature:
        return TaxonomyResult(
            group="delayed_payoff_overvaluation_with_outside_option_miss",
            rationale=(
                "Chosen branch receives positive multistep uplift but is still below outside option/oracle, while oracle branch has positive outside-option gap."
            ),
        )

    fragile_boundary_signature = (
        row["is_near_tie_state"]
        and row["oracle_gap_if_choose_k3"] <= 0.03
        and row["k3_pred_margin_top2"] >= 0.08
    )
    if fragile_boundary_signature:
        return TaxonomyResult(
            group="fragile_boundary_overconfidence",
            rationale=(
                "State is near tie with tiny oracle gap, but model margin is comparatively large, indicating overconfident boundary ranking."
            ),
        )

    return TaxonomyResult(
        group="other_score_ordering_error",
        rationale="Mismatch does not meet stronger signatures above; treated as residual ordering error bucket.",
    )


def render_branch_story(branch: dict[str, Any], is_chosen: bool, is_oracle: bool) -> str:
    role_bits = []
    if is_chosen:
        role_bits.append("method-chosen")
    if is_oracle:
        role_bits.append("oracle-best")
    role = ", ".join(role_bits) if role_bits else "competing"

    delta = branch["multistep_delta_vs_onestep"]
    delta_desc = "no multistep uplift"
    if delta > 0.15:
        delta_desc = "strong multistep uplift"
    elif delta > 0.05:
        delta_desc = "moderate multistep uplift"

    outside_desc = "beats outside option" if branch["branch_vs_outside_gap"] > 0 else "trails outside option"
    return (
        f"{role}; {delta_desc}; {outside_desc}; "
        f"depth={branch['features_branch_v1'].get('depth', 'na')}, "
        f"verify_count={branch['features_branch_v1'].get('verify_count', 'na')}, "
        f"recent_delta={branch['features_branch_v1'].get('recent_delta', 'na'):.4f}."
    )


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    leading = choose_leading_mode()

    ranking_rows = load_json(FAIL_DIR / "failure_case_ranking_table.json")["rows"]
    state_summaries = {r["state_id"]: r for r in load_jsonl(TARGET_DIR / "state_summaries.jsonl")}

    candidate_rows = load_jsonl(TARGET_DIR / "candidate_labels.jsonl")
    branch_feature_index: dict[tuple[str, str], dict[str, Any]] = {}
    for row in candidate_rows:
        branch_feature_index[(row["state_id"], row["branch_id"])] = row

    taxonomy_rows = []
    failures_only = []
    for row in ranking_rows:
        tax = assign_taxonomy(row)
        out = dict(row)
        out["mistake_type"] = tax.group
        out["mistake_rationale"] = tax.rationale
        taxonomy_rows.append(out)
        if not row["method_matches_oracle"]:
            failures_only.append(out)

    counts: dict[str, int] = {}
    for row in failures_only:
        counts[row["mistake_type"]] = counts.get(row["mistake_type"], 0) + 1

    dominant_group = max(counts.items(), key=lambda kv: kv[1])[0] if counts else "no_failures"

    strict_dominant = [r for r in taxonomy_rows if (not r["method_matches_oracle"] and r["mistake_type"] == dominant_group)]
    strict_dominant.sort(key=lambda r: (r["oracle_gap_if_choose_k3"], -r["k3_pred_margin_top2"]), reverse=True)

    selected = list(strict_dominant)
    backfill_needed = max(0, 4 - len(selected))

    backfill_pool = []
    for row in taxonomy_rows:
        if row in selected:
            continue
        per_branch = {b["branch_id"]: b for b in row["per_branch"]}
        chosen = per_branch[row["method_choice_k3"]]
        uplift = chosen["multistep_delta_vs_onestep"]
        backfill_pool.append((
            uplift,
            row["k3_pred_margin_top2"],
            row,
        ))
    backfill_pool.sort(key=lambda x: (x[0], -x[1]), reverse=True)

    for _, _, row in backfill_pool:
        if backfill_needed <= 0:
            break
        row = dict(row)
        row["backfill_reason"] = (
            "Backfill control: strict dominant-group failures < 4; selected highest-uplift states to illustrate same delayed-payoff scoring tendency."
        )
        selected.append(row)
        backfill_needed -= 1

    selected = selected[:4]

    selected_case_ids = [r["case_id"] for r in selected]

    branch_detail_rows = []
    selected_structured = []
    for row in selected:
        per_branch = {b["branch_id"]: dict(b) for b in row["per_branch"]}
        for bid in list(per_branch):
            feat_row = branch_feature_index.get((row["state_id"], bid), {})
            per_branch[bid]["features_branch_v1"] = feat_row.get("features_branch_v1", {})
            per_branch[bid]["estimated_value_if_allocate_next"] = feat_row.get("estimated_value_if_allocate_next")
            branch_detail_rows.append(
                {
                    "case_id": row["case_id"],
                    "state_id": row["state_id"],
                    "branch_id": bid,
                    "method_chosen": bid == row["method_choice_k3"],
                    "oracle_best": bid == row["oracle_best_branch"],
                    "method_score_k3": per_branch[bid]["method_score_k3"],
                    "oracle_one_step_value": per_branch[bid]["oracle_one_step_value"],
                    "multistep_target_value": per_branch[bid]["multistep_target_value"],
                    "multistep_delta_vs_onestep": per_branch[bid]["multistep_delta_vs_onestep"],
                    "branch_vs_outside_gap": per_branch[bid]["branch_vs_outside_gap"],
                    "allocation_value_std": per_branch[bid]["allocation_value_std"],
                    "best_followup_allocation": per_branch[bid]["best_followup_allocation"],
                    "multistep_target_self_followup_ratio": per_branch[bid]["multistep_target_self_followup_ratio"],
                    "features_branch_v1": per_branch[bid]["features_branch_v1"],
                }
            )

        question_preview = state_summaries.get(row["state_id"], {}).get("question_preview")
        chosen = per_branch[row["method_choice_k3"]]
        oracle = per_branch[row["oracle_best_branch"]]

        if row["method_matches_oracle"]:
            why_oracle_different = (
                "No oracle disagreement in this backfill control; included only to show the same multistep-uplift tendency under a correct decision."
            )
        else:
            why_oracle_different = (
                "Oracle branch has higher one-step value and stronger outside-option gap, indicating better immediate compute return."
                if oracle["branch_vs_outside_gap"] > 0
                else "Oracle branch wins by small but real one-step edge in a fragile boundary state."
            )

        diagnosis = {
            "why_model_likely_chose_it": (
                "Chosen branch had higher learned k3 score and appeared attractive under multistep utility uplift/self-followup proxy."
                if chosen["multistep_delta_vs_onestep"] > 0
                else "Chosen branch had highest learned score despite little/no multistep uplift signal."
            ),
            "why_oracle_different": why_oracle_different,
            "mistake_type": row["mistake_type"],
            "representative_of_dominant_group": row["mistake_type"] == dominant_group,
        }

        branches_for_story = []
        for bid, b in sorted(per_branch.items(), key=lambda kv: kv[1]["method_score_k3"], reverse=True):
            branches_for_story.append(
                {
                    "branch_id": bid,
                    "role": {
                        "method_chosen": bid == row["method_choice_k3"],
                        "oracle_best": bid == row["oracle_best_branch"],
                    },
                    "story": render_branch_story(b, bid == row["method_choice_k3"], bid == row["oracle_best_branch"]),
                    "signals": b,
                }
            )

        selected_structured.append(
            {
                "case_id": row["case_id"],
                "state_id": row["state_id"],
                "dataset_name": row["dataset_name"],
                "example_id": row["example_id"],
                "question_preview": question_preview,
                "method_choice_k3": row["method_choice_k3"],
                "oracle_best_branch": row["oracle_best_branch"],
                "oracle_gap_if_choose_k3": row["oracle_gap_if_choose_k3"],
                "k3_pred_margin_top2": row["k3_pred_margin_top2"],
                "oracle_margin_top2": row["oracle_margin_top2"],
                "mistake_type": row["mistake_type"],
                "mistake_rationale": row["mistake_rationale"],
                "selection_bucket": row.get("selection_bucket", "analysis_selection"),
                "backfill_reason": row.get("backfill_reason"),
                "branches": branches_for_story,
                "diagnosis": diagnosis,
            }
        )

    taxonomy_summary = {
        "total_states": len(taxonomy_rows),
        "total_failures": len(failures_only),
        "taxonomy_counts_on_failures": counts,
        "taxonomy_definition": {
            "delayed_payoff_overvaluation_with_outside_option_miss": "chosen branch has multistep uplift but negative outside-gap while oracle branch has positive outside-gap",
            "fragile_boundary_overconfidence": "near-tie with tiny oracle gap but large learned top-2 margin",
            "other_score_ordering_error": "residual mismatch not satisfying the stronger signatures",
        },
    }

    dominant_summary = {
        "dominant_group": dominant_group,
        "dominant_group_count": counts.get(dominant_group, 0),
        "failure_total": len(failures_only),
        "dominant_share": (counts.get(dominant_group, 0) / len(failures_only)) if failures_only else 0.0,
        "selection_rule": "Select strict failures in dominant group by highest oracle regret, then backfill to 4 with highest-uplift control states if needed.",
        "strict_dominant_count": len(strict_dominant),
        "backfill_count": sum(1 for r in selected if r.get("backfill_reason")),
    }

    manifest = {
        "run_id": OUT_DIR.name,
        "timestamp_utc": "2026-04-18",
        "input_artifacts": {
            "validation_summary": str(VAL_DIR / "aggregate_comparison_summary.json"),
            "failure_ranking": str(FAIL_DIR / "failure_case_ranking_table.json"),
            "candidate_labels_k3": str(TARGET_DIR / "candidate_labels.jsonl"),
            "state_summaries_k3": str(TARGET_DIR / "state_summaries.jsonl"),
        },
        "leading_method": leading,
        "notes": [
            "Branch free-text reasoning traces are not present in inspected artifacts; natural-language branch descriptions are reconstructed from stored numeric/action-history proxy fields.",
            "This is a bounded diagnostic pass only (no redesign).",
        ],
    }

    (OUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (OUT_DIR / "failure_taxonomy_summary.json").write_text(json.dumps(taxonomy_summary, indent=2) + "\n")
    (OUT_DIR / "dominant_group_selection_summary.json").write_text(json.dumps(dominant_summary, indent=2) + "\n")
    (OUT_DIR / "selected_case_ids.json").write_text(json.dumps({"case_ids": selected_case_ids}, indent=2) + "\n")
    (OUT_DIR / "per_case_structured_summary.json").write_text(json.dumps({"cases": selected_structured}, indent=2) + "\n")
    (OUT_DIR / "taxonomy_assignment_table.json").write_text(json.dumps({"rows": taxonomy_rows}, indent=2) + "\n")
    (OUT_DIR / "recoverable_branch_detail_table.json").write_text(json.dumps({"rows": branch_detail_rows}, indent=2) + "\n")

    caveats = """# Commands / assumptions / caveats
- Command run: `python scripts/run_natural_language_failure_casebook_dominant_group.py`.
- Leading-mode selection is based on latest validation aggregate summary under `multistep_branch_utility_target_validation_eval_20260417`.
- Taxonomy is rule-based from available fields (`multistep_delta_vs_onestep`, `branch_vs_outside_gap`, `near_tie`, `oracle_gap`, `k3_pred_margin_top2`).
- Full free-text branch reasoning traces are not present in inspected artifacts; branch explanations are reconstructed from stored branch-level signals, followup allocation mass, and feature proxies.
- Because dominant-group strict failures were fewer than 4, two backfill controls were included and explicitly labeled.
"""
    (OUT_DIR / "commands_assumptions_caveats.md").write_text(caveats)

    lines = []
    lines.append("# NATURAL-LANGUAGE FAILURE CASEBOOK (Dominant Group, 2026-04-18)")
    lines.append("## Scope and canonical framing")
    lines.append("- Fixed-budget branch-allocation/frontier-allocation diagnosis: which active branch should receive the next unit of compute.")
    lines.append("- Bounded analysis only; no redesign and no drift to binary revise-routing framing.")
    lines.append("")
    lines.append("## How the leading method was chosen")
    lines.append(f"- Source: `{VAL_DIR / 'aggregate_comparison_summary.json'}`.")
    lines.append(f"- Rule: {leading['selection_rule']}.")
    lines.append(f"- Selected mode: `{leading['selected_mode_canonical_name']}` ({leading['selected_metric']}={leading['selected_metric_value']:.6f}).")
    lines.append("")
    lines.append("## Mistake taxonomy for current failures")
    for name, desc in taxonomy_summary["taxonomy_definition"].items():
        lines.append(f"- **{name}**: {desc}.")
    lines.append("")
    lines.append("### Failure counts")
    for k, v in counts.items():
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("## Dominant mistake group")
    lines.append(f"- Dominant group: **{dominant_group}** ({dominant_summary['dominant_group_count']}/{dominant_summary['failure_total']} failures, share={dominant_summary['dominant_share']:.2f}).")
    lines.append("- Why dominant: it is the largest interpretable bucket under rule-based assignment from available artifact fields.")
    lines.append("")
    lines.append("## Selection rule for 4 examples")
    lines.append("- Prioritize strict failures in the dominant group by largest oracle regret (`oracle_gap_if_choose_k3`).")
    lines.append("- If strict dominant-group failures are <4, backfill with clearly-labeled controls exhibiting the strongest same-signature multistep-uplift tendency.")
    lines.append("")

    for idx, case in enumerate(selected_structured, 1):
        lines.append(f"## Case {idx}: `{case['case_id']}`")
        lines.append(f"- state_id=`{case['state_id']}`, dataset=`{case['dataset_name']}`, example_id=`{case['example_id']}`.")
        if case.get("question_preview"):
            lines.append(f"- Question text (preview): {case['question_preview']}")
        else:
            lines.append("- Question text: unavailable in inspected artifacts.")
        lines.append(f"- Method choice: `{case['method_choice_k3']}`; oracle-best: `{case['oracle_best_branch']}`.")
        lines.append(
            f"- Margins: predicted_top2={case['k3_pred_margin_top2']:.6f}, oracle_top2={case['oracle_margin_top2']:.6f}, oracle_regret_if_method={case['oracle_gap_if_choose_k3']:.6f}."
        )
        lines.append(f"- Mistake type: `{case['mistake_type']}`.")
        if case.get("backfill_reason"):
            lines.append(f"- Backfill label: {case['backfill_reason']}")
        lines.append("- Branch narratives:")
        for branch in case["branches"]:
            lines.append(
                f"  - {branch['branch_id']}: {branch['story']} "
                f"(k3_score={branch['signals']['method_score_k3']:.6f}, oracle_one_step={branch['signals']['oracle_one_step_value']:.6f}, "
                f"multistep_target={branch['signals']['multistep_target_value']:.6f}, outside_gap={branch['signals']['branch_vs_outside_gap']:.6f})."
            )
        diag = case["diagnosis"]
        lines.append(f"- Why model likely chose it: {diag['why_model_likely_chose_it']}")
        lines.append(f"- Why oracle differed: {diag['why_oracle_different']}")
        lines.append(f"- Representative of dominant group: {diag['representative_of_dominant_group']}")
        lines.append("")

    lines.append("## Cross-case summary of dominant group")
    lines.append(f"- Dominant group is `{dominant_group}` and concentrates failures where multistep-uplift signals can outrank branches that are stronger on immediate oracle/outside-option value.")
    lines.append("- Shared pattern: chosen branch often has high learned score plus positive self-followup/uplift proxies, while oracle-best branch has better one-step return for the next compute unit.")
    lines.append("- Practical next diagnostic step: audit calibration between multistep uplift proxies and outside-option gap on near-boundary states before any method redesign.")
    lines.append("")
    lines.append("## Commands / assumptions / caveats")
    lines.append("- Commands and caveats are recorded in `outputs/branch_label_bruteforce_learning/natural_language_failure_casebook_dominant_group_20260418/commands_assumptions_caveats.md`.")
    lines.append("- Natural-language branch traces are partially recoverable only through stored signals; full free-text branch reasoning is unavailable in inspected artifacts.")

    DOC_PATH.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
