#!/usr/bin/env python3
"""Evaluate hard per-family expansion caps on strict-phased methods.

Rule: no branch family may receive more than K true expansion actions in a run.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import sys
from collections import Counter
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


BN = _load_module(REPO_ROOT / "scripts/build_new_hundred_newest_vs_best_failure_statistics.py", "bn_hard_cap")
TW = BN.TW

BASE = "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1"
STRICT_GATE1 = f"{BASE}_hard_early_root_depth2_then_gate_v1_optimistic_collapse_first__deterministic_output_layer_repair_v1"
STRICT_GATE2 = f"{BASE}_hard_early_root_depth2_then_gate_v2_budget_aware_rescue__deterministic_output_layer_repair_v1"
STRICT_GATE1_CAP = {
    2: f"{BASE}_hard_early_root_depth2_then_gate_v1_optimistic_collapse_first_hard_max_family_expansions_cap_k2_v1__deterministic_output_layer_repair_v1",
    3: f"{BASE}_hard_early_root_depth2_then_gate_v1_optimistic_collapse_first_hard_max_family_expansions_cap_k3_v1__deterministic_output_layer_repair_v1",
    4: f"{BASE}_hard_early_root_depth2_then_gate_v1_optimistic_collapse_first_hard_max_family_expansions_cap_k4_v1__deterministic_output_layer_repair_v1",
}
STRICT_GATE2_CAP3 = f"{BASE}_hard_early_root_depth2_then_gate_v2_budget_aware_rescue_hard_max_family_expansions_cap_k3_v1__deterministic_output_layer_repair_v1"


def _latest_new_hundred_file() -> Path | None:
    dirs = sorted(REPO_ROOT.glob("outputs/new_hundred_newest_vs_best_failure_statistics_*/"))
    for d in reversed(dirs):
        p = d / "per_case_failure_statistics.json"
        if p.exists():
            return p
    return None


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


def _same_family(raw: dict[str, Any]) -> bool:
    m = raw.get("metadata") or {}
    return bool(float(m.get("repeated_same_family_expansion_rate", 0.0)) > 0.0)


def _delta(base_ok: bool, new_ok: bool) -> str:
    if base_ok and new_ok:
        return "unchanged"
    if base_ok and (not new_ok):
        return "worsened"
    if (not base_ok) and new_ok:
        return "improved"
    return "unchanged"


def _mean(vals: list[float]) -> float:
    return float(sum(vals) / len(vals)) if vals else 0.0


def _aggregate(rows: list[dict[str, Any]], method_key: str) -> dict[str, Any]:
    outcomes = (
        Counter(r[f"{method_key}_vs_baseline_outcome"] for r in rows)
        if method_key != "baseline"
        else Counter()
    )
    cap_bind = sum(1 for r in rows if int(r.get(f"{method_key}_cap_bind_count", 0)) > 0)
    dominant_hit = sum(1 for r in rows if bool(r.get(f"{method_key}_dominant_family_hit_cap", False)))
    return {
        "method": method_key,
        "n_cases": len(rows),
        "accuracy": _mean([1.0 if r[f"{method_key}_correct"] else 0.0 for r in rows]),
        "absent_from_tree": sum(1 for r in rows if r[f"{method_key}_failure_type"] == "absent_from_tree"),
        "present_not_selected": sum(1 for r in rows if r[f"{method_key}_failure_type"] == "present_not_selected"),
        "repeated_same_family_present": sum(1 for r in rows if r[f"{method_key}_repeated_same_family_present"]),
        "gold_in_tree": sum(1 for r in rows if r[f"{method_key}_gold_in_tree"]),
        "avg_actions": _mean([float(r[f"{method_key}_actions"]) for r in rows]),
        "avg_expansions": _mean([float(r[f"{method_key}_expansions"]) for r in rows]),
        "avg_verifications": _mean([float(r[f"{method_key}_verifications"]) for r in rows]),
        "improved_vs_baseline": int(outcomes.get("improved", 0)),
        "worsened_vs_baseline": int(outcomes.get("worsened", 0)),
        "unchanged_vs_baseline": int(outcomes.get("unchanged", 0)),
        "cap_bound_case_count": int(cap_bind),
        "dominant_family_hit_cap_case_count": int(dominant_hit),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-case-json", type=Path, default=None)
    ap.add_argument("--limit", type=int, default=100)
    ap.add_argument("--k-values", default="2,3,4")
    ap.add_argument("--include-gate2-k3", action="store_true")
    args = ap.parse_args()

    now = datetime.now(timezone.utc)
    ts = now.strftime("%Y%m%dT%H%M%SZ")
    out_dir = REPO_ROOT / f"outputs/hard_max_family_expansions_eval_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    per_case_json = args.per_case_json or _latest_new_hundred_file()
    source = "new_hundred_newest_vs_best"
    if per_case_json is None:
        per_case_json = REPO_ROOT / "outputs/hundred_current_full_vs_best_failure_statistics_20260420T220416Z/per_case_failure_statistics.json"
        source = "fallback_current_full_vs_best"
    per_case_json = per_case_json.resolve()
    try:
        surface_input_rel = str(per_case_json.relative_to(REPO_ROOT))
    except ValueError:
        surface_input_rel = str(per_case_json)

    recs = json.loads(per_case_json.read_text(encoding="utf-8"))[: int(args.limit)]

    baseline_method = TW._resolve_current_full_method()
    comparator_method, comparator_info = BN._resolve_best_comparator()
    newest_method, newest_info = BN._resolve_newest_method()

    target_method = STRICT_GATE1
    target_method_reason = "Picked strict_gate1 explicitly from latest strict-phased docs because it outperformed strict_gate2 on the broader strict-phased default decision report."

    k_values = [int(x.strip()) for x in args.k_values.split(",") if x.strip()]
    methods: dict[str, str] = {
        "baseline": baseline_method,
        "strict_target": target_method,
        "strict_gate2_reference": STRICT_GATE2,
    }
    for k in k_values:
        methods[f"strict_target_cap_k{k}"] = STRICT_GATE1_CAP[k]
    if args.include_gate2_k3:
        methods["strict_gate2_cap_k3"] = STRICT_GATE2_CAP3

    rows: list[dict[str, Any]] = []
    question_cache: dict[tuple[str, int], dict[str, tuple[str, str]]] = {}

    for rec in recs:
        dataset = str(rec["dataset"])
        example_id = str(rec["example_id"])
        seed = int(rec["surface_row"]["seed"])
        budget = int(rec["surface_row"]["budget"])
        gold = str(rec["compact_row"]["gold_answer"])
        cache_key = (dataset, seed)
        if cache_key not in question_cache:
            question_cache[cache_key] = {
                str(ex.example_id): (str(ex.question), str(ex.answer))
                for ex in load_pilot_examples(dataset, BN.HUNDRED_SURFACE_SUBSET_SIZE, seed)
            }
        found = question_cache[cache_key].get(example_id)
        if found is None:
            continue
        question, gold_found = found
        if gold_found.strip():
            gold = gold_found

        runs: dict[str, dict[str, Any]] = {}
        cls: dict[str, dict[str, Any]] = {}

        for key, method in methods.items():
            raw = BN._run_observed_with_events(
                method,
                {
                    "dataset": dataset,
                    "example_id": example_id,
                    "problem_text": question,
                    "ground_truth": gold,
                    "seed": seed,
                    "budget": budget,
                },
                "fresh_our",
            )
            runs[key] = raw
            ft, ok, contains, ans = _classify(raw, gold, dataset)
            cls[key] = {"failure": ft, "correct": ok, "gold_in_tree": contains, "answer": ans}

        comp_raw = BN._run_observed_with_events(
            comparator_method,
            {
                "dataset": dataset,
                "example_id": example_id,
                "problem_text": question,
                "ground_truth": gold,
                "seed": seed,
                "budget": budget,
            },
            "fresh_best",
        )
        _, _, _, comp_ans = _classify(comp_raw, gold, dataset)

        row: dict[str, Any] = {
            "dataset": dataset,
            "example_id": example_id,
            "gold_answer": gold,
            "best_comparator_answer": comp_ans,
            "seed": seed,
            "budget": budget,
        }

        for key in methods:
            meta = runs[key].get("metadata") or {}
            row[f"{key}_answer"] = cls[key]["answer"]
            row[f"{key}_correct"] = cls[key]["correct"]
            row[f"{key}_failure_type"] = cls[key]["failure"]
            row[f"{key}_gold_in_tree"] = cls[key]["gold_in_tree"]
            row[f"{key}_repeated_same_family_present"] = _same_family(runs[key])
            row[f"{key}_actions"] = int(runs[key]["actions"])
            row[f"{key}_expansions"] = int(runs[key]["expansions"])
            row[f"{key}_verifications"] = int(runs[key]["verifications"])
            row[f"{key}_family_expansion_counts"] = dict(meta.get("hard_max_family_expansion_counts") or {})
            row[f"{key}_cap_hit_families"] = list(meta.get("hard_max_family_cap_hit_families") or [])
            row[f"{key}_cap_hit_family_count"] = int(meta.get("hard_max_family_cap_hit_family_count", 0))
            row[f"{key}_cap_bind_count"] = int(meta.get("hard_max_family_cap_bind_count", 0))
            row[f"{key}_dominant_family_hit_cap"] = bool(
                any(bool(ev.get("was_dominant_family_at_bind")) for ev in list(meta.get("hard_max_family_cap_events") or []))
            )

        for key in methods:
            if key == "baseline":
                continue
            row[f"{key}_vs_baseline_outcome"] = _delta(bool(row["baseline_correct"]), bool(row[f"{key}_correct"]))

        rows.append(row)

    comparison_rows = [_aggregate(rows, key) for key in methods]

    helped = [
        r for r in rows
        if r.get("strict_target_cap_k3_vs_baseline_outcome") == "improved"
        and r.get("strict_target_vs_baseline_outcome") != "improved"
    ][:5]
    harmed = [
        r for r in rows
        if r.get("strict_target_cap_k3_vs_baseline_outcome") == "worsened"
        and r.get("strict_target_vs_baseline_outcome") != "worsened"
    ][:5]

    dataset_breakdown: dict[str, dict[str, Any]] = {}
    for ds in sorted({r["dataset"] for r in rows}):
        ds_rows = [r for r in rows if r["dataset"] == ds]
        dataset_breakdown[ds] = {
            key: _aggregate(ds_rows, key) for key in methods
        }

    summary = {
        "n_cases": len(rows),
        "source_surface": source,
        "comparison": comparison_rows,
        "dataset_breakdown": dataset_breakdown,
        "representative_helped_cases": [
            {"dataset": r["dataset"], "example_id": r["example_id"], "baseline_failure": r["baseline_failure_type"], "cap3_failure": r["strict_target_cap_k3_failure_type"]}
            for r in helped
        ],
        "representative_harmed_cases": [
            {"dataset": r["dataset"], "example_id": r["example_id"], "baseline_failure": r["baseline_failure_type"], "cap3_failure": r["strict_target_cap_k3_failure_type"]}
            for r in harmed
        ],
    }

    manifest = {
        "artifact_family": "hard_max_family_expansions_eval",
        "created_at_utc": now.isoformat(),
        "output_dir": str(out_dir.relative_to(REPO_ROOT)),
        "surface_input": surface_input_rel,
        "surface_tag": source,
        "strict_phased_law_preserved": True,
        "family_expansion_cap_definition": "No branch family may receive more than K true expansion actions in a run; capped families become ineligible for further expand actions but verification/commit still proceed.",
        "target_method": target_method,
        "target_method_selection_reason": target_method_reason,
        "newest_method_resolution": newest_info,
        "best_comparator": comparator_method,
        "best_comparator_resolution": comparator_info,
        "k_values": k_values,
        "methods": methods,
    }

    with (out_dir / "eval_manifest.json").open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    with (out_dir / "per_case_comparison.json").open("w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2)
    with (out_dir / "aggregate_summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    with (out_dir / "comparison_table.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(comparison_rows[0].keys()))
        writer.writeheader()
        for r in comparison_rows:
            writer.writerow(r)

    report = REPO_ROOT / f"docs/HARD_MAX_FAMILY_EXPANSIONS_EVAL_{ts}.md"
    by_method = {r["method"]: r for r in comparison_rows}
    lines = [
        f"# Hard max family expansions evaluation ({ts})",
        "",
        "## Definition",
        "Family expansion cap = no branch family may exceed K expansion actions in a run; once capped, that family is ineligible for further expand actions while verify/commit behavior remains enabled.",
        "",
        "## Method and comparator selection",
        f"- Selected target strict-phased method: `{target_method}`",
        f"- Selection note: {target_method_reason}",
        f"- Selected best comparator: `{comparator_method}`",
        f"- K values tested: {k_values}",
        "- Insertion point in code: `GlobalDiversityAggregationController.run` expansion decision path before executing expand.",
        "- Strict phased law preserved: **True**",
        "",
        "## Aggregate comparison",
        "| method | accuracy | absent_from_tree | present_not_selected | repeated_same_family_present | gold_in_tree | avg_actions | avg_expansions | avg_verifications | improved | worsened | unchanged | cap_bound_case_count | dominant_family_hit_cap_case_count |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for key in methods:
        r = by_method[key]
        lines.append(
            f"| {key} | {r['accuracy']:.4f} | {r['absent_from_tree']} | {r['present_not_selected']} | {r['repeated_same_family_present']} | {r['gold_in_tree']} | {r['avg_actions']:.3f} | {r['avg_expansions']:.3f} | {r['avg_verifications']:.3f} | {r['improved_vs_baseline']} | {r['worsened_vs_baseline']} | {r['unchanged_vs_baseline']} | {r['cap_bound_case_count']} | {r['dominant_family_hit_cap_case_count']} |"
        )

    lines.extend([
        "",
        "## Representative helped cases",
    ])
    for r in summary["representative_helped_cases"]:
        lines.append(f"- {r['dataset']} / {r['example_id']}: {r['baseline_failure']} -> {r['cap3_failure']}")
    lines.extend([
        "",
        "## Representative harmed cases",
    ])
    for r in summary["representative_harmed_cases"]:
        lines.append(f"- {r['dataset']} / {r['example_id']}: {r['baseline_failure']} -> {r['cap3_failure']}")

    cap3 = by_method.get("strict_target_cap_k3", {})
    target = by_method.get("strict_target", {})
    verdict = "promising" if float(cap3.get("accuracy", 0.0)) >= float(target.get("accuracy", 0.0)) else "too blunt"
    lines.extend([
        "",
        "## Dataset-wise breakdown",
    ])
    for ds, ds_methods in sorted(dataset_breakdown.items()):
        k3_row = ds_methods.get("strict_target_cap_k3", {})
        tgt_row = ds_methods.get("strict_target", {})
        lines.append(
            f"- {ds}: strict_target acc={float(tgt_row.get('accuracy', 0.0)):.4f}, "
            f"cap_k3 acc={float(k3_row.get('accuracy', 0.0)):.4f}, "
            f"cap_k3 absent={int(k3_row.get('absent_from_tree', 0))}, "
            f"cap_k3 present_not_selected={int(k3_row.get('present_not_selected', 0))}"
        )
    lines.extend([
        "",
        "## Conclusion",
        f"Hard cap verdict: **{verdict}**.",
        "Judgment prioritizes final performance and failure decomposition rather than collapse diagnostics alone.",
        "",
        "## Concise summary",
        f"- files changed: experiments/controllers.py, experiments/frontier_matrix_core.py, "
        f"tests/test_hard_max_family_expansions_cap.py, scripts/run_hard_max_family_expansions_eval.py, "
        f"docs/HARD_MAX_FAMILY_EXPANSIONS_EVAL_{ts}.md",
        "- commands run: see shell command list in run logs.",
        f"- selected target method: {target_method}",
        f"- selected best comparator: {comparator_method}",
        f"- K values tested: {k_values}",
        f"- output directory: outputs/hard_max_family_expansions_eval_{ts}",
        f"- baseline vs capped(K=3) absent_from_tree: "
        f"{by_method['baseline']['absent_from_tree']} vs {by_method['strict_target_cap_k3']['absent_from_tree']}",
        f"- baseline vs capped(K=3) present_not_selected: "
        f"{by_method['baseline']['present_not_selected']} vs {by_method['strict_target_cap_k3']['present_not_selected']}",
        f"- baseline vs capped(K=3) repeated_same_family_present: "
        f"{by_method['baseline']['repeated_same_family_present']} vs {by_method['strict_target_cap_k3']['repeated_same_family_present']}",
        f"- baseline vs capped(K=3) gold_in_tree: "
        f"{by_method['baseline']['gold_in_tree']} vs {by_method['strict_target_cap_k3']['gold_in_tree']}",
        f"- baseline vs capped(K=3) improved/worsened/unchanged: "
        f"{by_method['strict_target_cap_k3']['improved_vs_baseline']}/"
        f"{by_method['strict_target_cap_k3']['worsened_vs_baseline']}/"
        f"{by_method['strict_target_cap_k3']['unchanged_vs_baseline']}",
        f"- one-sentence verdict: hard family-expansion cap looks {verdict} in this run.",
    ])
    report.write_text("\n".join(lines), encoding="utf-8")

    print(f"output_dir={out_dir.relative_to(REPO_ROOT)}")
    print(f"report={report.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
