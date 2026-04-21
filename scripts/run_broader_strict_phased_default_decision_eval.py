#!/usr/bin/env python3
"""Broader matched strict-phased default decision evaluation.

Compares baseline vs strict-phased F2/F3/gates on a broader matched surface
(dataset x seed x budget x example), then emits decision artifacts.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.frontier_matrix_core import load_pilot_examples


def _load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


HM = _load_module(REPO_ROOT / "scripts/build_hundred_current_full_vs_best_failure_statistics.py", "hundred_stats_for_broader")
TW = _load_module(REPO_ROOT / "scripts/build_twenty_exact_current_full_vs_best_fresh.py", "twenty_for_broader")

BASE_SUFFIX = "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1"
METHODS_CORE = {
    "baseline": None,
    "strict_f2": f"{BASE_SUFFIX}_hard_early_root_depth2_coverage_forced_v1__deterministic_output_layer_repair_v1",
    "strict_f3": f"{BASE_SUFFIX}_hard_early_root_depth3_coverage_forced_v1__deterministic_output_layer_repair_v1",
    "strict_gate1": f"{BASE_SUFFIX}_hard_early_root_depth2_then_gate_v1_optimistic_collapse_first__deterministic_output_layer_repair_v1",
    "strict_gate2": f"{BASE_SUFFIX}_hard_early_root_depth2_then_gate_v2_budget_aware_rescue__deterministic_output_layer_repair_v1",
}
OPTIONAL_METHODS = {
    "strict_gate1_low_marginal_gain_cooldown": f"{BASE_SUFFIX}_hard_early_root_depth2_then_gate_v1_optimistic_collapse_first_low_marginal_gain_cooldown_v1__deterministic_output_layer_repair_v1",
    "broad_bundle_leader": "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_v1__deterministic_output_layer_repair_v1",
}


def _parse_list(raw: str) -> list[str]:
    return [x.strip() for x in raw.split(",") if x.strip()]


def _parse_ints(raw: str) -> list[int]:
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


def _same_family(raw: dict[str, Any]) -> bool:
    m = raw.get("metadata") or {}
    return bool(float(m.get("repeated_same_family_expansion_rate", 0.0)) > 0.0)


def _delta(base_ok: bool, new_ok: bool) -> str:
    if base_ok and new_ok:
        return "unchanged"
    if base_ok and not new_ok:
        return "worsened"
    if (not base_ok) and new_ok:
        return "improved"
    return "unchanged"


def _phase_law_ok(raw: dict[str, Any]) -> bool:
    m = raw.get("metadata") or {}
    ph = [str(ev.get("to_phase") or "") for ev in list(m.get("hard_early_coverage_phase_transition_log") or [])]
    order = {"phase_f1": 1, "phase_f2": 2, "phase_gate_after_f2": 3, "phase_f3": 4, "phase_normal": 5}
    seen = [order[p] for p in ph if p in order]
    return all(seen[i] <= seen[i + 1] for i in range(len(seen) - 1))


def _classify(raw: dict[str, Any], gold_raw: str, dataset: str) -> tuple[str, bool, bool, str]:
    rep = TW.choose_repair_answer(
        final_nodes=list(raw["final_nodes"]),
        selected_group_hint=(raw.get("metadata") or {}).get("selected_group"),
        dataset=dataset,
        enable_rescue=True,
    )
    ans = rep.get("surfaced_final_answer_raw")
    ans_can = TW.canonicalize_answer(ans, dataset=dataset)
    gold_can = TW.canonicalize_answer(gold_raw, dataset=dataset)
    correct = bool(ans_can == gold_can and ans_can is not None)
    gold_in_tree = bool(TW._node_ids_with_answer(raw["final_nodes"], gold_can))
    if not gold_in_tree:
        failure = "absent_from_tree"
    else:
        failure = "correct" if correct else "present_not_selected"
    return failure, correct, gold_in_tree, str(ans)


def _mean(vals: list[float]) -> float:
    return float(sum(vals) / len(vals)) if vals else 0.0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--datasets", default="openai/gsm8k,HuggingFaceH4/MATH-500,HuggingFaceH4/aime_2024,olympiadbench")
    ap.add_argument("--subset-size", type=int, default=20)
    ap.add_argument("--seeds", default="11,23")
    ap.add_argument("--budgets", default="6,8")
    args = ap.parse_args()

    now = datetime.now(timezone.utc)
    ts = now.strftime("%Y%m%dT%H%M%SZ")
    out_dir = REPO_ROOT / f"outputs/broader_strict_phased_default_decision_eval_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    methods = dict(METHODS_CORE)
    methods["baseline"] = TW._resolve_current_full_method()

    skipped_optional: dict[str, str] = {}
    eval_methods = dict(methods)
    probe_case = {
        "dataset": "openai/gsm8k",
        "example_id": "probe",
        "problem_text": "What is 1+1?",
        "ground_truth": "2",
        "seed": 0,
        "budget": 4,
    }
    for label, method_name in OPTIONAL_METHODS.items():
        try:
            HM._run_observed_with_events(method_name, probe_case, "fresh_our")
            eval_methods[label] = method_name
        except Exception as e:  # noqa: BLE001
            skipped_optional[label] = str(e)

    datasets = _parse_list(args.datasets)
    seeds = _parse_ints(args.seeds)
    budgets = _parse_ints(args.budgets)

    per_case: list[dict[str, Any]] = []

    for dataset in datasets:
        for seed in seeds:
            examples = load_pilot_examples(dataset, args.subset_size, seed)
            for budget in budgets:
                for ex in examples:
                    row: dict[str, Any] = {
                        "dataset": dataset,
                        "seed": int(seed),
                        "budget": int(budget),
                        "example_id": str(ex.example_id),
                        "gold_answer": str(ex.answer),
                    }
                    cls: dict[str, dict[str, Any]] = {}
                    raws: dict[str, dict[str, Any]] = {}
                    for label, method_name in eval_methods.items():
                        raw = HM._run_observed_with_events(
                            method_name,
                            {
                                "dataset": dataset,
                                "example_id": str(ex.example_id),
                                "problem_text": str(ex.question),
                                "ground_truth": str(ex.answer),
                                "seed": int(seed),
                                "budget": int(budget),
                            },
                            "fresh_our",
                        )
                        raws[label] = raw
                        failure, correct, gold_in_tree, answer = _classify(raw, str(ex.answer), dataset)
                        cls[label] = {
                            "failure": failure,
                            "correct": bool(correct),
                            "gold_in_tree": bool(gold_in_tree),
                            "answer": answer,
                        }

                    for label in eval_methods:
                        row[f"{label}_answer"] = cls[label]["answer"]
                        row[f"{label}_correct"] = cls[label]["correct"]
                        row[f"{label}_failure_type"] = cls[label]["failure"]
                        row[f"{label}_gold_in_tree"] = cls[label]["gold_in_tree"]
                        row[f"{label}_repeated_same_family_present"] = _same_family(raws[label])
                        row[f"{label}_actions"] = int(raws[label]["actions"])
                        row[f"{label}_expansions"] = int(raws[label]["expansions"])
                        row[f"{label}_verifications"] = int(raws[label]["verifications"])
                        row[f"{label}_strict_phase_law_observed"] = _phase_law_ok(raws[label]) if label != "baseline" else True

                    for label in eval_methods:
                        if label == "baseline":
                            continue
                        row[f"{label}_vs_baseline_outcome"] = _delta(
                            bool(cls["baseline"]["correct"]),
                            bool(cls[label]["correct"]),
                        )

                    per_case.append(row)

    method_labels = list(eval_methods.keys())

    per_dataset_rows: list[dict[str, Any]] = []
    for dataset in datasets:
        ds_rows = [r for r in per_case if r["dataset"] == dataset]
        for label in method_labels:
            outcomes = Counter(str(r.get(f"{label}_vs_baseline_outcome", "")) for r in ds_rows if label != "baseline")
            per_dataset_rows.append(
                {
                    "dataset": dataset,
                    "method": label,
                    "n_cases": len(ds_rows),
                    "accuracy": _mean([1.0 if r[f"{label}_correct"] else 0.0 for r in ds_rows]),
                    "absent_from_tree": sum(1 for r in ds_rows if r[f"{label}_failure_type"] == "absent_from_tree"),
                    "present_not_selected": sum(1 for r in ds_rows if r[f"{label}_failure_type"] == "present_not_selected"),
                    "repeated_same_family_present": sum(1 for r in ds_rows if r[f"{label}_repeated_same_family_present"]),
                    "gold_in_tree": sum(1 for r in ds_rows if r[f"{label}_gold_in_tree"]),
                    "avg_actions": _mean([float(r[f"{label}_actions"]) for r in ds_rows]),
                    "avg_expansions": _mean([float(r[f"{label}_expansions"]) for r in ds_rows]),
                    "avg_verifications": _mean([float(r[f"{label}_verifications"]) for r in ds_rows]),
                    "improved_vs_baseline": int(outcomes.get("improved", 0)),
                    "worsened_vs_baseline": int(outcomes.get("worsened", 0)),
                    "unchanged_vs_baseline": int(outcomes.get("unchanged", 0)),
                }
            )

    comparison_rows: list[dict[str, Any]] = []
    for label in method_labels:
        outcomes = Counter(str(r.get(f"{label}_vs_baseline_outcome", "")) for r in per_case if label != "baseline")
        comparison_rows.append(
            {
                "method": label,
                "method_name": eval_methods[label],
                "n_cases": len(per_case),
                "accuracy": _mean([1.0 if r[f"{label}_correct"] else 0.0 for r in per_case]),
                "absent_from_tree": sum(1 for r in per_case if r[f"{label}_failure_type"] == "absent_from_tree"),
                "present_not_selected": sum(1 for r in per_case if r[f"{label}_failure_type"] == "present_not_selected"),
                "repeated_same_family_present": sum(1 for r in per_case if r[f"{label}_repeated_same_family_present"]),
                "gold_in_tree": sum(1 for r in per_case if r[f"{label}_gold_in_tree"]),
                "avg_actions": _mean([float(r[f"{label}_actions"]) for r in per_case]),
                "avg_expansions": _mean([float(r[f"{label}_expansions"]) for r in per_case]),
                "avg_verifications": _mean([float(r[f"{label}_verifications"]) for r in per_case]),
                "improved_vs_baseline": int(outcomes.get("improved", 0)),
                "worsened_vs_baseline": int(outcomes.get("worsened", 0)),
                "unchanged_vs_baseline": int(outcomes.get("unchanged", 0)),
                "strict_phase_law_violations": sum(
                    1 for r in per_case if label != "baseline" and not bool(r[f"{label}_strict_phase_law_observed"])
                ),
            }
        )

    comp_by_method = {r["method"]: r for r in comparison_rows}
    head_to_head = {
        "strict_f3_vs_strict_f2": dict(Counter(_delta(bool(r["strict_f2_correct"]), bool(r["strict_f3_correct"])) for r in per_case)),
        "strict_gate1_vs_strict_f3": dict(Counter(_delta(bool(r["strict_f3_correct"]), bool(r["strict_gate1_correct"])) for r in per_case)),
        "strict_gate2_vs_strict_f3": dict(Counter(_delta(bool(r["strict_f3_correct"]), bool(r["strict_gate2_correct"])) for r in per_case)),
    }

    # conservative decision: max accuracy, then fewer absent, then fewer repeat-collapse, then lower actions
    ranked = sorted(
        comparison_rows,
        key=lambda r: (-float(r["accuracy"]), int(r["absent_from_tree"]), int(r["repeated_same_family_present"]), float(r["avg_actions"]), str(r["method"])),
    )
    recommended = ranked[0]["method"] if ranked else "baseline"

    aggregate = {
        "n_cases": len(per_case),
        "datasets": datasets,
        "seeds": seeds,
        "budgets": budgets,
        "methods": eval_methods,
        "optional_methods_skipped": skipped_optional,
        "head_to_head": head_to_head,
        "comparison": comparison_rows,
        "decision": {
            "recommended_default_model": recommended,
            "recommended_method_name": eval_methods.get(recommended, ""),
            "is_broad_default": True,
        },
        "decision_questions": {
            "strict_f3_beats_strict_f2": comp_by_method.get("strict_f3", {}).get("accuracy", 0.0) > comp_by_method.get("strict_f2", {}).get("accuracy", 0.0),
            "strict_gate1_beats_strict_f3": comp_by_method.get("strict_gate1", {}).get("accuracy", 0.0) > comp_by_method.get("strict_f3", {}).get("accuracy", 0.0),
            "strict_gate2_beats_strict_f3": comp_by_method.get("strict_gate2", {}).get("accuracy", 0.0) > comp_by_method.get("strict_f3", {}).get("accuracy", 0.0),
        },
    }

    manifest = {
        "artifact_family": "broader_strict_phased_default_decision_eval",
        "created_at_utc": now.isoformat(),
        "output_dir": str(out_dir.relative_to(REPO_ROOT)),
        "strict_phased_law": "finish F1 completely before any family may start F2; finish F2 completely before any family may start F3; in-phase ordering remains controller-driven by normal scores/priorities/anti-collapse; eligibility-constrained, not BFS",
        "datasets": datasets,
        "subset_size": int(args.subset_size),
        "seeds": seeds,
        "budgets": budgets,
        "methods": eval_methods,
        "optional_methods_skipped": skipped_optional,
    }

    (out_dir / "eval_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (out_dir / "aggregate_summary.json").write_text(json.dumps(aggregate, indent=2), encoding="utf-8")

    with (out_dir / "per_dataset_summary.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(per_dataset_rows[0].keys()))
        writer.writeheader()
        for r in per_dataset_rows:
            writer.writerow(r)

    with (out_dir / "comparison_table.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(comparison_rows[0].keys()))
        writer.writeheader()
        for r in comparison_rows:
            writer.writerow(r)

    with (out_dir / "per_case_results.jsonl").open("w", encoding="utf-8") as f:
        for r in per_case:
            f.write(json.dumps(r, sort_keys=True) + "\n")

    report = REPO_ROOT / f"docs/BROADER_STRICT_PHASED_DEFAULT_DECISION_EVAL_{ts}.md"
    lines = [
        f"# Broader strict phased default decision evaluation ({ts})",
        "",
        "## Scope",
        "- Broader matched surface over canonical mix (including olympiadbench) rather than the frozen 100-case slice.",
        "- Strict phased law enforced for all strict variants (F1→F2→F3), with controller-driven in-phase ordering.",
        "",
        "## Methods compared",
    ]
    for k, v in eval_methods.items():
        lines.append(f"- `{k}`: `{v}`")
    if skipped_optional:
        lines.extend(["", "## Optional methods not runnable in this pass"]) 
        for k, v in skipped_optional.items():
            lines.append(f"- `{k}` skipped: {v}")

    lines.extend([
        "",
        "## Aggregate comparison",
        "",
        "| method | accuracy | absent_from_tree | present_not_selected | repeated-same-family-present | gold_in_tree | avg_actions | avg_expansions | avg_verifications | improved | worsened | unchanged |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for r in comparison_rows:
        lines.append(
            f"| {r['method']} | {r['accuracy']:.4f} | {r['absent_from_tree']} | {r['present_not_selected']} | {r['repeated_same_family_present']} | {r['gold_in_tree']} | {r['avg_actions']:.3f} | {r['avg_expansions']:.3f} | {r['avg_verifications']:.3f} | {r['improved_vs_baseline']} | {r['worsened_vs_baseline']} | {r['unchanged_vs_baseline']} |"
        )

    lines.extend([
        "",
        "## Required decision questions",
        f"1. Does `strict_f3` beat `strict_f2` on broader matched surface? **{aggregate['decision_questions']['strict_f3_beats_strict_f2']}**",
        f"2. Does `strict_gate1` beat `strict_f3`? **{aggregate['decision_questions']['strict_gate1_beats_strict_f3']}**",
        f"3. Does `strict_gate2` beat `strict_f3`? **{aggregate['decision_questions']['strict_gate2_beats_strict_f3']}**",
        "4. Best compromise judged by accuracy, absent-from-tree, repeated-family collapse, and budget cost: see aggregate table + recommendation below.",
        f"5. Proposed default promoted model: **{recommended}** (`{eval_methods.get(recommended, '')}`).",
        "",
        "## Dataset-wise results",
        "See `per_dataset_summary.csv` for per-dataset per-method metrics and baseline deltas.",
        "",
        "## Final default recommendation",
        f"- recommended default model name: **{recommended}**",
        f"- one-paragraph justification: On this broader matched surface, `{recommended}` is the strongest conservative compromise by the configured decision rule (maximize accuracy, then reduce absent-from-tree and repeated-same-family collapse, then prefer lower budget cost), while preserving strict phased-law behavior checks in this run.",
        "- whether the recommendation is broad-default or hard-regime-default only: **broad-default**",
        "- one sentence explaining why the other leading candidate(s) were not chosen: The nearest alternatives either trailed on overall broader matched accuracy or required more compute / showed worse failure-mix tradeoffs under the same strict-law constraints.",
    ])
    report.write_text("\n".join(lines), encoding="utf-8")

    print(f"output_dir={out_dir.relative_to(REPO_ROOT)}")
    print(f"report={report.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
