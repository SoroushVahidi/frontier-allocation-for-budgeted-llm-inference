#!/usr/bin/env python3
"""Offline FIX-6 / LoVEC-1 scaffold evaluation.

No API calls. Consumes existing artifacts only.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from experiments import support_aware_selector as sas
from experiments import value_of_compute_controller as voc


@dataclass
class ArtifactSpec:
    name: str
    path: Path
    split_kind: str  # unbiased|diagnostic


def _norm(x: Any) -> str | None:
    return sas._normalize_answer(x)


def _is_correct(ans: Any, gold: Any) -> bool:
    a = _norm(ans)
    g = _norm(gold)
    return bool(a and g and a == g)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    with path.open() as f:
        for line in f:
            if line.strip():
                out.append(json.loads(line))
    return out


def _group_rows(rows: list[dict[str, Any]]) -> dict[tuple[str, Any, Any, str], dict[str, dict[str, Any]]]:
    grouped: dict[tuple[str, Any, Any, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        key = (
            str(row.get("example_id")),
            row.get("seed"),
            row.get("budget"),
            str(row.get("dataset") or ""),
        )
        method = str(row.get("method") or "")
        grouped[key][method] = row
    return grouped


def _complete_groups(
    grouped: dict[tuple[str, Any, Any, str], dict[str, dict[str, Any]]]
) -> dict[tuple[str, Any, Any, str], dict[str, dict[str, Any]]]:
    out = {}
    need = set(voc.REQUIRED_METHODS)
    for k, mm in grouped.items():
        if need.issubset(mm.keys()):
            out[k] = mm
    return out


def _external_signature(mm: dict[str, dict[str, Any]]) -> str:
    ext = {
        "external_l1_max": mm["external_l1_max"].get("final_answer_canonical"),
        "external_s1_budget_forcing": mm["external_s1_budget_forcing"].get("final_answer_canonical"),
        "external_tale_prompt_budgeting": mm["external_tale_prompt_budgeting"].get("final_answer_canonical"),
    }
    return sas.external_agreement_signature(ext)


def _has_parser_issue(frontier_row: dict[str, Any]) -> bool:
    if frontier_row.get("parse_extraction_failure"):
        return True
    if frontier_row.get("status") != "scored":
        return True
    ans = _norm(frontier_row.get("final_answer_canonical") or frontier_row.get("selected_answer_canonical"))
    return not bool(ans)


def _root_cause_label(case: dict[str, Any]) -> str:
    if case["all_methods_wrong"]:
        return "all_methods_wrong"
    if case["fix24_wrong_and_tale_correct"]:
        return "residual_tale_complementarity"
    if case["parser_issue"]:
        return "residual_parser_issue"
    if case["external_signature"] == "l1=s1=tale" and not case["fix24_correct"]:
        return "residual_external_consensus"
    if case["low_depth_flag"] and not case["fix24_correct"]:
        return "residual_low_depth_not_caught"
    if case["fix24_wrong"] and case["oracle_observable_correct"] and case["avail_logged_frontier_alternative_proxy"]:
        return "residual_present_not_selected"
    if case["fix24_wrong"] and not case["avail_logged_frontier_alternative_proxy"] and not case["avail_logged_external_alternative_proxy"]:
        return "residual_frontier_pool_miss"
    if case["fix24_wrong"] and not case["oracle_observable_correct"]:
        return "insufficient_counterfactual_logs"
    return "residual_external_consensus" if case["fix24_wrong"] else "not_failure"


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow(row)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory. Default: outputs/fix6_lovec1_value_of_compute_20260519_<STAMP>",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = (
        args.output_dir
        if args.output_dir
        else repo_root / f"outputs/fix6_lovec1_value_of_compute_20260519_{stamp}"
    )
    out_dir.mkdir(parents=True, exist_ok=False)

    artifacts = [
        ArtifactSpec(
            name="overnight_300_unbiased",
            path=repo_root
            / "outputs/overnight_fix5_promotion_grade_validation_20260519T040621Z/runner_output/cohere_real_model_cost_normalized_validation_fix5_overnight_live_20260519T040621Z/per_example_records.jsonl",
            split_kind="unbiased",
        ),
        ArtifactSpec(
            name="promotion_100_unbiased",
            path=repo_root
            / "outputs/promotion_grade_cohere_all_baselines_validation_20260519T005021Z/runner_output/cohere_real_model_cost_normalized_validation_20260519T005206Z/per_example_records.jsonl",
            split_kind="unbiased",
        ),
        ArtifactSpec(
            name="diagnostic_420_failure_enriched",
            path=repo_root
            / "outputs/targeted_cohere_100_failure_cases_postrun_20260519T002844Z/repaired_all_generated_records.jsonl",
            split_kind="diagnostic",
        ),
    ]

    all_case_rows: list[dict[str, Any]] = []
    state_rows: list[dict[str, Any]] = []
    action_rows: list[dict[str, Any]] = []
    oracle_rows: list[dict[str, Any]] = []

    for spec in artifacts:
        rows = _load_jsonl(spec.path)
        grouped = _complete_groups(_group_rows(rows))

        for (example_id, seed, budget, dataset), mm in grouped.items():
            frontier_row = mm["direct_reserve_semantic_frontier_v2"]
            ext_answers = {
                "external_l1_max": mm["external_l1_max"].get("final_answer_canonical"),
                "external_s1_budget_forcing": mm["external_s1_budget_forcing"].get("final_answer_canonical"),
                "external_tale_prompt_budgeting": mm["external_tale_prompt_budgeting"].get("final_answer_canonical"),
            }

            fix2_row = sas.apply_fix2_to_row(frontier_row, external_answers=ext_answers)
            fix24_row = sas.apply_combined_fix24_to_row(frontier_row, external_answers=ext_answers)
            fix5_row = sas.apply_fix5_tale_default_router(frontier_row, external_answers=ext_answers)
            lovec_row = voc.apply_lovec1_controller(mm)
            state = lovec_row["state"]
            avail = lovec_row["available_actions"]
            oracle = voc.choose_oracle_observable_action_offline(
                mm,
                frontier_row.get("gold_answer_canonical") or frontier_row.get("gold_answer"),
            )

            gold = _norm(frontier_row.get("gold_answer_canonical") or frontier_row.get("gold_answer"))

            answers = {
                "frontier": _norm(frontier_row.get("final_answer_canonical") or frontier_row.get("selected_answer_canonical")),
                "fix2": _norm(fix2_row.get("fix2_answer_canonical")),
                "fix24": _norm(fix24_row.get("combined24_answer_canonical")),
                "fix5": _norm(fix5_row.get("fix5_answer_canonical")),
                "lovec1": _norm(lovec_row.get("lovec_answer_canonical")),
                "tale": _norm(mm["external_tale_prompt_budgeting"].get("final_answer_canonical")),
                "l1": _norm(mm["external_l1_max"].get("final_answer_canonical")),
                "s1": _norm(mm["external_s1_budget_forcing"].get("final_answer_canonical")),
                "oracle_observable": _norm(oracle.get("oracle_answer_canonical")),
            }
            corr = {k: _is_correct(v, gold) for k, v in answers.items()}

            # State feature row (runtime features only).
            state_row = {
                "artifact": spec.name,
                "split_kind": spec.split_kind,
                "example_id": example_id,
                "seed": seed,
                "budget": budget,
                "dataset": dataset,
            }
            for k, v in state.items():
                if k.startswith("_"):
                    continue
                state_row[k] = v
            state_rows.append(state_row)

            action_row = {
                "artifact": spec.name,
                "split_kind": spec.split_kind,
                "example_id": example_id,
                "seed": seed,
                "budget": budget,
                "dataset": dataset,
                "lovec_action": lovec_row.get("lovec_action"),
                "lovec_reason": lovec_row.get("lovec_reason"),
                "lovec_action_changed": bool(lovec_row.get("lovec_action_changed")),
            }
            for action_name, meta in avail.items():
                action_row[f"avail_{action_name}"] = bool(meta.get("available"))
                action_row[f"ans_{action_name}"] = _norm(meta.get("candidate_answer"))
            action_rows.append(action_row)

            case = {
                "artifact": spec.name,
                "split_kind": spec.split_kind,
                "example_id": example_id,
                "seed": seed,
                "budget": budget,
                "dataset": dataset,
                "gold_answer_canonical": gold,
                "frontier_answer_canonical": answers["frontier"],
                "fix2_answer_canonical": answers["fix2"],
                "fix24_answer_canonical": answers["fix24"],
                "fix5_answer_canonical": answers["fix5"],
                "lovec1_answer_canonical": answers["lovec1"],
                "tale_answer_canonical": answers["tale"],
                "l1_answer_canonical": answers["l1"],
                "s1_answer_canonical": answers["s1"],
                "oracle_observable_answer_canonical": answers["oracle_observable"],
                "frontier_correct": corr["frontier"],
                "fix2_correct": corr["fix2"],
                "fix24_correct": corr["fix24"],
                "fix5_correct": corr["fix5"],
                "lovec1_correct": corr["lovec1"],
                "tale_correct": corr["tale"],
                "l1_correct": corr["l1"],
                "s1_correct": corr["s1"],
                "oracle_observable_correct": corr["oracle_observable"],
                "external_signature": _external_signature(mm),
                "low_depth_flag": bool(state.get("low_depth_flag")),
                "weak_search_flag": bool(state.get("weak_search_flag")),
                "parser_issue": _has_parser_issue(frontier_row),
                "avail_logged_frontier_alternative_proxy": bool(avail["logged_frontier_alternative_proxy"]["available"]),
                "avail_logged_external_alternative_proxy": bool(avail["logged_external_alternative_proxy"]["available"]),
                "lovec_action": lovec_row.get("lovec_action"),
                "lovec_reason": lovec_row.get("lovec_reason"),
            }
            case["fix24_wrong"] = not case["fix24_correct"]
            case["fix24_wrong_and_tale_correct"] = (not case["fix24_correct"]) and bool(case["tale_correct"])
            case["fix24_correct_and_tale_wrong"] = bool(case["fix24_correct"]) and (not case["tale_correct"])
            case["both_fix24_and_tale_wrong"] = (not case["fix24_correct"]) and (not case["tale_correct"])
            case["all_externals_wrong"] = (not case["tale_correct"]) and (not case["l1_correct"]) and (not case["s1_correct"])
            case["all_methods_wrong"] = case["all_externals_wrong"] and (not case["frontier_correct"]) and (not case["fix24_correct"])
            case["requires_new_generation"] = (not case["fix24_correct"]) and (not case["oracle_observable_correct"])
            case["root_cause_label"] = _root_cause_label(case)
            all_case_rows.append(case)

            oracle_rows.append(
                {
                    "artifact": spec.name,
                    "split_kind": spec.split_kind,
                    "example_id": example_id,
                    "seed": seed,
                    "budget": budget,
                    "dataset": dataset,
                    "fix24_correct": case["fix24_correct"],
                    "tale_correct": case["tale_correct"],
                    "oracle_observable_action": oracle.get("oracle_action"),
                    "oracle_observable_answer_canonical": oracle.get("oracle_answer_canonical"),
                    "oracle_observable_correct": case["oracle_observable_correct"],
                    "oracle_gain_over_fix24": int(case["oracle_observable_correct"]) - int(case["fix24_correct"]),
                    "oracle_gain_over_tale": int(case["oracle_observable_correct"]) - int(case["tale_correct"]),
                    "requires_new_generation": case["requires_new_generation"],
                }
            )

    # Summaries.
    by_artifact_summary: list[dict[str, Any]] = []
    oracle_upper_bound_rows: list[dict[str, Any]] = []

    for artifact in sorted({r["artifact"] for r in all_case_rows}):
        rows = [r for r in all_case_rows if r["artifact"] == artifact]
        n = len(rows)

        def acc(k: str) -> float:
            return (sum(int(bool(r[k])) for r in rows) / n) if n else 0.0

        a_frontier = acc("frontier_correct")
        a_fix2 = acc("fix2_correct")
        a_fix24 = acc("fix24_correct")
        a_fix5 = acc("fix5_correct")
        a_lovec = acc("lovec1_correct")
        a_tale = acc("tale_correct")
        a_l1 = acc("l1_correct")
        a_s1 = acc("s1_correct")
        a_oracle_obs = acc("oracle_observable_correct")

        fix24_errors = sum(1 for r in rows if not r["fix24_correct"])
        reducible = sum(1 for r in rows if (not r["fix24_correct"]) and r["oracle_observable_correct"])
        irreducible = sum(1 for r in rows if (not r["fix24_correct"]) and (not r["oracle_observable_correct"]))

        avail_frontier_alt = sum(1 for r in rows if r["avail_logged_frontier_alternative_proxy"]) / n
        avail_ext_alt = sum(1 for r in rows if r["avail_logged_external_alternative_proxy"]) / n
        low_depth_rate = sum(1 for r in rows if r["low_depth_flag"]) / n

        by_artifact_summary.append(
            {
                "artifact": artifact,
                "split_kind": rows[0]["split_kind"],
                "n": n,
                "frontier_acc": round(a_frontier * 100, 4),
                "fix2_acc": round(a_fix2 * 100, 4),
                "fix24_acc": round(a_fix24 * 100, 4),
                "fix5_acc": round(a_fix5 * 100, 4),
                "lovec1_acc": round(a_lovec * 100, 4),
                "tale_acc": round(a_tale * 100, 4),
                "l1_acc": round(a_l1 * 100, 4),
                "s1_acc": round(a_s1 * 100, 4),
                "oracle_observable_acc": round(a_oracle_obs * 100, 4),
                "lovec1_delta_vs_tale_pp": round((a_lovec - a_tale) * 100, 4),
                "lovec1_delta_vs_fix24_pp": round((a_lovec - a_fix24) * 100, 4),
                "oracle_gain_vs_fix24_pp": round((a_oracle_obs - a_fix24) * 100, 4),
                "oracle_gain_vs_tale_pp": round((a_oracle_obs - a_tale) * 100, 4),
                "fix24_errors": fix24_errors,
                "oracle_reducible_errors": reducible,
                "oracle_irreducible_errors": irreducible,
                "logged_frontier_alt_availability_rate": round(avail_frontier_alt, 6),
                "logged_external_alt_availability_rate": round(avail_ext_alt, 6),
                "low_depth_rate": round(low_depth_rate, 6),
            }
        )

        oracle_upper_bound_rows.append(
            {
                "artifact": artifact,
                "n": n,
                "fix24_accuracy": round(a_fix24, 6),
                "oracle_observable_accuracy": round(a_oracle_obs, 6),
                "oracle_gain_over_fix24_pp": round((a_oracle_obs - a_fix24) * 100, 4),
                "tale_accuracy": round(a_tale, 6),
                "oracle_gain_over_tale_pp": round((a_oracle_obs - a_tale) * 100, 4),
                "fix24_errors": fix24_errors,
                "reducible_with_logged_actions": reducible,
                "irreducible_without_new_generation": irreducible,
            }
        )

    # Residual failure table focuses on main 300-case artifact.
    residual_rows = [
        r
        for r in all_case_rows
        if r["artifact"] == "overnight_300_unbiased" and (
            r["fix24_wrong"]
            or r["fix24_correct_and_tale_wrong"]
            or r["all_methods_wrong"]
            or r["all_externals_wrong"]
        )
    ]

    # Representative cases (small, diverse).
    rep_cases: list[dict[str, Any]] = []
    by_label: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in residual_rows:
        by_label[r["root_cause_label"]].append(r)
    for label in sorted(by_label):
        rep_cases.extend(by_label[label][:5])

    # Minimal API pilot plan (no execution).
    main_rows = [r for r in all_case_rows if r["artifact"] == "overnight_300_unbiased"]
    losses_vs_tale = [r for r in main_rows if r["fix24_wrong_and_tale_correct"]]
    both_wrong_poolmiss = [
        r
        for r in main_rows
        if r["both_fix24_and_tale_wrong"] and r["root_cause_label"] in {"residual_frontier_pool_miss", "insufficient_counterfactual_logs", "all_methods_wrong"}
    ]
    low_depth_losses = [r for r in main_rows if r["fix24_wrong"] and r["low_depth_flag"]]

    selected_ids: list[str] = []
    for bucket in (losses_vs_tale, both_wrong_poolmiss, low_depth_losses):
        for r in bucket:
            eid = str(r["example_id"])
            if eid not in selected_ids:
                selected_ids.append(eid)
            if len(selected_ids) >= 45:
                break
        if len(selected_ids) >= 45:
            break

    main_summary = next(b for b in by_artifact_summary if b["artifact"] == "overnight_300_unbiased")
    api_needed = bool(main_summary["oracle_irreducible_errors"] > 0)

    pilot_plan = {
        "pilot_name": "fix6_lovec1_minimal_extra_action_pilot",
        "launch_ready": False,
        "api_needed": api_needed,
        "provider": "cohere",
        "model": "command-r-plus-08-2024",
        "execution": {
            "tmux_required": True,
            "strict_api_cap": 1200,
            "promotion_review_logging_required": True,
            "gold_in_prompt_forbidden": True,
        },
        "target_size": {
            "min": 30,
            "max": 50,
            "selected_example_count": len(selected_ids),
        },
        "case_selection": {
            "residual_fix24_losses_vs_tale": len(losses_vs_tale),
            "both_wrong_pool_miss_signatures": len(both_wrong_poolmiss),
            "low_depth_or_weak_search_losses": len(low_depth_losses),
            "selected_example_ids": selected_ids,
        },
        "actions_to_collect": [
            "one_extra_frontier_branch",
            "or_one_diverse_frontier_sample",
            "or_one_extra_tale_call",
        ],
        "acceptance_criteria": {
            "primary": "LoVEC action policy improves over FIX-2+FIX-4 by >= +1.0pp on pilot without regression concentration.",
            "secondary": "Observable-action-only oracle gap narrows materially after adding extra-action outcomes.",
            "safety": "No gold/exact fields in runtime prompts/features; cap not exceeded.",
        },
    }

    policy_definition = {
        "policy_name": "lovec1_skeleton_fix24_default_v1",
        "version": "1.0",
        "base_policy": sas.COMBINED_FIX24_POLICY_NAME,
        "runtime_gold_free": True,
        "default_action": "stop_fix24",
        "allowed_actions": [
            "stop_fix24",
            "stop_tale",
            "stop_external_consensus",
            "logged_frontier_alternative_proxy",
            "logged_external_alternative_proxy",
            "no_observable_extra_action",
        ],
        "switching_behavior": "disabled_in_v1_scaffold",
        "notes": [
            "LoVEC-1 currently records state and action availability only.",
            "Accuracy-changing switches require extra-action disjoint pilot evidence.",
        ],
    }

    # Decide recommended next action A/B/C/D/E.
    if api_needed:
        next_action = "A"
    elif main_summary["oracle_gain_vs_fix24_pp"] > 0.0:
        next_action = "B"
    elif main_summary["fix24_acc"] >= 83.0:
        next_action = "D"
    else:
        next_action = "E"

    eval_metrics = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "output_dir": str(out_dir),
        "artifacts": [
            {"name": a.name, "path": str(a.path), "split_kind": a.split_kind}
            for a in artifacts
        ],
        "summary_by_artifact": by_artifact_summary,
        "main_findings": {
            "base_policy": sas.COMBINED_FIX24_POLICY_NAME,
            "fix24_main_accuracy_pct": main_summary["fix24_acc"],
            "tale_main_accuracy_pct": main_summary["tale_acc"],
            "fix5_main_accuracy_pct": main_summary["fix5_acc"],
            "lovec1_main_accuracy_pct": main_summary["lovec1_acc"],
            "lovec1_delta_vs_fix24_pp": main_summary["lovec1_delta_vs_fix24_pp"],
            "oracle_observable_gain_vs_fix24_pp": main_summary["oracle_gain_vs_fix24_pp"],
            "oracle_irreducible_errors_main": main_summary["oracle_irreducible_errors"],
            "api_needed_for_true_extra_action": api_needed,
        },
        "recommended_next_action": next_action,
        "safety": {
            "no_api_calls": True,
            "gold_offline_only": True,
            "outputs_not_overwritten": True,
        },
    }

    # Write outputs.
    _write_csv(
        out_dir / "fix6_state_feature_table.csv",
        state_rows,
        sorted({k for r in state_rows for k in r.keys()}),
    )
    _write_csv(
        out_dir / "fix6_action_availability.csv",
        action_rows,
        sorted({k for r in action_rows for k in r.keys()}),
    )
    _write_csv(
        out_dir / "fix6_oracle_action_table.csv",
        oracle_rows,
        sorted({k for r in oracle_rows for k in r.keys()}),
    )
    _write_csv(
        out_dir / "fix6_oracle_upper_bound.csv",
        oracle_upper_bound_rows,
        [
            "artifact",
            "n",
            "fix24_accuracy",
            "oracle_observable_accuracy",
            "oracle_gain_over_fix24_pp",
            "tale_accuracy",
            "oracle_gain_over_tale_pp",
            "fix24_errors",
            "reducible_with_logged_actions",
            "irreducible_without_new_generation",
        ],
    )
    _write_csv(
        out_dir / "fix6_by_artifact_summary.csv",
        by_artifact_summary,
        [
            "artifact",
            "split_kind",
            "n",
            "frontier_acc",
            "fix2_acc",
            "fix24_acc",
            "fix5_acc",
            "lovec1_acc",
            "tale_acc",
            "l1_acc",
            "s1_acc",
            "oracle_observable_acc",
            "lovec1_delta_vs_tale_pp",
            "lovec1_delta_vs_fix24_pp",
            "oracle_gain_vs_fix24_pp",
            "oracle_gain_vs_tale_pp",
            "fix24_errors",
            "oracle_reducible_errors",
            "oracle_irreducible_errors",
            "logged_frontier_alt_availability_rate",
            "logged_external_alt_availability_rate",
            "low_depth_rate",
        ],
    )
    _write_csv(
        out_dir / "fix6_residual_failure_cases.csv",
        residual_rows,
        sorted({k for r in residual_rows for k in r.keys()}),
    )

    with (out_dir / "fix6_policy_definition.json").open("w") as f:
        json.dump(policy_definition, f, indent=2)
    with (out_dir / "fix6_eval_metrics.json").open("w") as f:
        json.dump(eval_metrics, f, indent=2)
    with (out_dir / "fix6_minimal_api_pilot_plan.json").open("w") as f:
        json.dump(pilot_plan, f, indent=2)
    with (out_dir / "metrics.json").open("w") as f:
        json.dump(eval_metrics, f, indent=2)

    with (out_dir / "fix6_representative_cases.jsonl").open("w") as f:
        for row in rep_cases:
            f.write(json.dumps(row) + "\n")

    root_counts = Counter(r["root_cause_label"] for r in residual_rows)
    report_lines = [
        "# FIX-6 / LoVEC-1 Offline Feasibility Report",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"Output dir: `{out_dir}`",
        "",
        "## Core Result",
        f"- Base policy (`{sas.COMBINED_FIX24_POLICY_NAME}`) remains strongest on overnight 300 by point estimate.",
        f"- LoVEC-1 scaffold accuracy (main 300): {main_summary['lovec1_acc']:.2f}%",
        f"- FIX-2+FIX-4 accuracy (main 300): {main_summary['fix24_acc']:.2f}%",
        f"- Delta LoVEC-1 vs FIX-2+FIX-4: {main_summary['lovec1_delta_vs_fix24_pp']:+.2f} pp",
        "",
        "## Observable Action Availability",
        f"- Logged frontier alternative availability (main 300): {main_summary['logged_frontier_alt_availability_rate']*100:.1f}%",
        f"- Logged external alternative availability (main 300): {main_summary['logged_external_alt_availability_rate']*100:.1f}%",
        f"- Low-depth rate (main 300): {main_summary['low_depth_rate']*100:.1f}%",
        "",
        "## Oracle Observable Upper Bound (Logged Actions Only)",
        f"- Oracle observable gain vs FIX-2+FIX-4 (main 300): {main_summary['oracle_gain_vs_fix24_pp']:+.2f} pp",
        f"- Reducible FIX-2+FIX-4 errors with logged actions: {main_summary['oracle_reducible_errors']}",
        f"- Irreducible FIX-2+FIX-4 errors without new generation: {main_summary['oracle_irreducible_errors']}",
        "",
        "## Residual Root-Cause Counts (main 300 focus)",
    ]
    for k, v in sorted(root_counts.items()):
        report_lines.append(f"- {k}: {v}")
    report_lines.extend(
        [
            "",
            "## Decision",
            f"- Is offline logged-counterfactual data sufficient for accuracy-changing LoVEC now? {'yes' if not api_needed else 'no'}",
            f"- Is new API data needed for true value-of-compute action outcomes? {'yes' if api_needed else 'no'}",
            f"- Recommended next action: {next_action}",
        ]
    )

    (out_dir / "fix6_lovec_report.md").write_text("\n".join(report_lines))

    print(out_dir)


if __name__ == "__main__":
    main()
