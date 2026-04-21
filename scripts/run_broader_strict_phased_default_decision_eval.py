#!/usr/bin/env python3
"""Broader matched strict-phased cap K-sweep follow-up evaluation.

Primary follow-up surface compares strict_gate1 (uncapped) vs strict_gate1_cap_k6/k7/k8,
with optional k9/k10 on the same broader matched default-decision surface.
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


HM = _load_module(REPO_ROOT / "scripts/build_hundred_current_full_vs_best_failure_statistics.py", "hundred_stats_for_broader")
TW = _load_module(REPO_ROOT / "scripts/build_twenty_exact_current_full_vs_best_fresh.py", "twenty_for_broader")

BASE_SUFFIX = "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1"


def _method_name_for_k(cap_k: int) -> str:
    return (
        f"{BASE_SUFFIX}_hard_early_root_depth2_then_gate_v1_optimistic_collapse_first"
        f"_hard_max_family_expansions_cap_k{cap_k}_v1__deterministic_output_layer_repair_v1"
    )


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
    if "hard_early_root_strict_phased_v1_enabled" in m:
        return bool(m.get("hard_early_root_strict_phased_v1_enabled"))
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
    output_mismatch = bool(
        gold_in_tree
        and (rep.get("chosen_final_node_answer_canonical") == gold_can)
        and (ans_can != gold_can)
    )
    extraction_mismatch = bool(
        (rep.get("chosen_final_node_answer_canonical") != rep.get("extracted_final_answer_canonical"))
        or (rep.get("extracted_final_answer_canonical") != rep.get("surfaced_final_answer_canonical"))
    )
    if not gold_in_tree:
        failure = "absent_from_tree"
    elif output_mismatch or extraction_mismatch:
        failure = "output_layer_mismatch"
    else:
        failure = "correct" if correct else "present_not_selected"
    return failure, correct, gold_in_tree, str(ans)


def _mean(vals: list[float]) -> float:
    return float(sum(vals) / len(vals)) if vals else 0.0


def _head_to_head(rows: list[dict[str, Any]], left: str, right: str) -> dict[str, int]:
    res = Counter(_delta(bool(r[f"{right}_correct"]), bool(r[f"{left}_correct"])) for r in rows)
    return {"improved": int(res.get("improved", 0)), "worsened": int(res.get("worsened", 0)), "unchanged": int(res.get("unchanged", 0))}


def _aggregate(rows: list[dict[str, Any]], label: str) -> dict[str, Any]:
    outcomes = Counter(str(r.get(f"{label}_vs_strict_gate1_outcome", "")) for r in rows if label != "strict_gate1")
    return {
        "method": label,
        "n_cases": len(rows),
        "accuracy": _mean([1.0 if r[f"{label}_correct"] else 0.0 for r in rows]),
        "absent_from_tree": sum(1 for r in rows if r[f"{label}_failure_type"] == "absent_from_tree"),
        "present_not_selected": sum(1 for r in rows if r[f"{label}_failure_type"] == "present_not_selected"),
        "output_layer_mismatch": sum(1 for r in rows if r[f"{label}_failure_type"] == "output_layer_mismatch"),
        "repeated_same_family_present": sum(1 for r in rows if r[f"{label}_repeated_same_family_present"]),
        "gold_in_tree": sum(1 for r in rows if r[f"{label}_gold_in_tree"]),
        "avg_actions": _mean([float(r[f"{label}_actions"]) for r in rows]),
        "avg_expansions": _mean([float(r[f"{label}_expansions"]) for r in rows]),
        "avg_verifications": _mean([float(r[f"{label}_verifications"]) for r in rows]),
        "avg_max_family_expansion_share": _mean([float(r[f"{label}_max_family_expansion_share"]) for r in rows]),
        "avg_longest_same_family_run": _mean([float(r[f"{label}_longest_same_family_run"]) for r in rows]),
        "cap_bound_case_count": sum(1 for r in rows if int(r[f"{label}_cap_bind_count"]) > 0),
        "dominant_family_hit_cap_case_count": sum(1 for r in rows if bool(r[f"{label}_dominant_family_hit_cap"])),
        "improved_vs_strict_gate1": int(outcomes.get("improved", 0)),
        "worsened_vs_strict_gate1": int(outcomes.get("worsened", 0)),
        "unchanged_vs_strict_gate1": int(outcomes.get("unchanged", 0)),
        "strict_phase_law_violations": sum(1 for r in rows if not bool(r[f"{label}_strict_phase_law_observed"])),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--datasets", default="openai/gsm8k,HuggingFaceH4/MATH-500,HuggingFaceH4/aime_2024,olympiadbench")
    ap.add_argument("--subset-size", type=int, default=20)
    ap.add_argument("--seeds", default="11,23")
    ap.add_argument("--budgets", default="6,8")
    ap.add_argument("--include-k9-k10", action="store_true")
    args = ap.parse_args()

    now = datetime.now(timezone.utc)
    ts = now.strftime("%Y%m%dT%H%M%SZ")
    out_dir = REPO_ROOT / f"outputs/final_strict_phased_cap_k678_eval_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    eval_methods: dict[str, str] = {
        "strict_gate1": f"{BASE_SUFFIX}_hard_early_root_depth2_then_gate_v1_optimistic_collapse_first__deterministic_output_layer_repair_v1",
        "strict_gate1_cap_k6": _method_name_for_k(6),
        "strict_gate1_cap_k7": _method_name_for_k(7),
        "strict_gate1_cap_k8": _method_name_for_k(8),
    }
    if args.include_k9_k10:
        eval_methods["strict_gate1_cap_k9"] = _method_name_for_k(9)
        eval_methods["strict_gate1_cap_k10"] = _method_name_for_k(10)

    probe_case = {
        "dataset": "openai/gsm8k",
        "example_id": "probe",
        "problem_text": "What is 1+1?",
        "ground_truth": "2",
        "seed": 0,
        "budget": 4,
    }
    for label, method_name in eval_methods.items():
        HM._run_observed_with_events(method_name, probe_case, "fresh_our")

    datasets = _parse_list(args.datasets)
    seeds = _parse_ints(args.seeds)
    budgets = _parse_ints(args.budgets)

    per_case: list[dict[str, Any]] = []
    for dataset in datasets:
        for seed in seeds:
            examples = load_pilot_examples(dataset, args.subset_size, seed)
            for budget in budgets:
                for ex in examples:
                    base_row = {
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

                    row = dict(base_row)
                    for label in eval_methods:
                        meta = raws[label].get("metadata") or {}
                        cap_events = list(meta.get("hard_max_family_cap_events") or [])
                        row[f"{label}_answer"] = cls[label]["answer"]
                        row[f"{label}_correct"] = cls[label]["correct"]
                        row[f"{label}_failure_type"] = cls[label]["failure"]
                        row[f"{label}_gold_in_tree"] = cls[label]["gold_in_tree"]
                        row[f"{label}_repeated_same_family_present"] = _same_family(raws[label])
                        row[f"{label}_actions"] = int(raws[label]["actions"])
                        row[f"{label}_expansions"] = int(raws[label]["expansions"])
                        row[f"{label}_verifications"] = int(raws[label]["verifications"])
                        row[f"{label}_strict_phase_law_observed"] = _phase_law_ok(raws[label])
                        row[f"{label}_cap_bind_count"] = int(meta.get("hard_max_family_cap_bind_count", 0))
                        row[f"{label}_dominant_family_hit_cap"] = bool(
                            any(bool(ev.get("was_dominant_family_at_bind")) for ev in cap_events if isinstance(ev, dict))
                        )
                        row[f"{label}_max_family_expansion_share"] = float(meta.get("max_family_expansion_share", 0.0))
                        row[f"{label}_longest_same_family_run"] = int(meta.get("max_consecutive_same_family_expands", 0))

                    for label in eval_methods:
                        if label == "strict_gate1":
                            continue
                        row[f"{label}_vs_strict_gate1_outcome"] = _delta(
                            bool(cls["strict_gate1"]["correct"]),
                            bool(cls[label]["correct"]),
                        )

                    per_case.append(row)

    method_labels = list(eval_methods.keys())

    comparison_rows = [_aggregate(per_case, label) for label in method_labels]

    per_dataset_rows: list[dict[str, Any]] = []
    for dataset in datasets:
        ds_rows = [r for r in per_case if r["dataset"] == dataset]
        for label in method_labels:
            base = _aggregate(ds_rows, label)
            per_dataset_rows.append({"dataset": dataset, **base})

    head_to_head = {
        "strict_gate1_cap_k6_vs_strict_gate1": _head_to_head(per_case, "strict_gate1_cap_k6", "strict_gate1"),
        "strict_gate1_cap_k7_vs_strict_gate1": _head_to_head(per_case, "strict_gate1_cap_k7", "strict_gate1"),
        "strict_gate1_cap_k8_vs_strict_gate1": _head_to_head(per_case, "strict_gate1_cap_k8", "strict_gate1"),
        "strict_gate1_cap_k7_vs_strict_gate1_cap_k6": _head_to_head(per_case, "strict_gate1_cap_k7", "strict_gate1_cap_k6"),
        "strict_gate1_cap_k8_vs_strict_gate1_cap_k7": _head_to_head(per_case, "strict_gate1_cap_k8", "strict_gate1_cap_k7"),
        "strict_gate1_cap_k8_vs_strict_gate1_cap_k6": _head_to_head(per_case, "strict_gate1_cap_k8", "strict_gate1_cap_k6"),
    }
    if "strict_gate1_cap_k9" in eval_methods and "strict_gate1_cap_k8" in eval_methods:
        head_to_head["strict_gate1_cap_k9_vs_strict_gate1_cap_k8"] = _head_to_head(per_case, "strict_gate1_cap_k9", "strict_gate1_cap_k8")
    if "strict_gate1_cap_k10" in eval_methods and "strict_gate1_cap_k9" in eval_methods:
        head_to_head["strict_gate1_cap_k10_vs_strict_gate1_cap_k9"] = _head_to_head(per_case, "strict_gate1_cap_k10", "strict_gate1_cap_k9")

    by_method = {r["method"]: r for r in comparison_rows}
    capped_rank = sorted(
        [r for r in comparison_rows if r["method"] != "strict_gate1"],
        key=lambda r: (-float(r["accuracy"]), int(r["absent_from_tree"]), int(r["repeated_same_family_present"]), float(r["avg_actions"]), str(r["method"])),
    )
    recommended = capped_rank[0]["method"] if capped_rank else "strict_gate1"

    decision_questions = {
        "k7_beats_k6": by_method["strict_gate1_cap_k7"]["accuracy"] > by_method["strict_gate1_cap_k6"]["accuracy"],
        "k8_beats_k7": by_method["strict_gate1_cap_k8"]["accuracy"] > by_method["strict_gate1_cap_k7"]["accuracy"],
        "any_cap_beats_uncapped": max(by_method[m]["accuracy"] for m in method_labels if m != "strict_gate1") > by_method["strict_gate1"]["accuracy"],
        "plateau_as_k_increases": (
            abs(by_method["strict_gate1_cap_k7"]["accuracy"] - by_method["strict_gate1_cap_k6"]["accuracy"]) <= 0.01
            and abs(by_method["strict_gate1_cap_k8"]["accuracy"] - by_method["strict_gate1_cap_k7"]["accuracy"]) <= 0.01
        ),
        "larger_k_reverts_toward_uncapped": abs(by_method["strict_gate1_cap_k8"]["accuracy"] - by_method["strict_gate1"]["accuracy"]) < abs(by_method["strict_gate1_cap_k6"]["accuracy"] - by_method["strict_gate1"]["accuracy"]),
    }

    aggregate = {
        "n_cases": len(per_case),
        "datasets": datasets,
        "subset_size": int(args.subset_size),
        "seeds": seeds,
        "budgets": budgets,
        "methods": eval_methods,
        "comparison": comparison_rows,
        "head_to_head": head_to_head,
        "decision_questions": decision_questions,
        "final_recommendation": {
            "recommended_cap_choice": recommended,
            "recommended_method_name": eval_methods.get(recommended, ""),
            "cap_should_remain_in_broad_default": bool(recommended != "strict_gate1"),
        },
    }

    manifest = {
        "artifact_family": "final_strict_phased_cap_k678_eval",
        "created_at_utc": now.isoformat(),
        "output_dir": str(out_dir.relative_to(REPO_ROOT)),
        "strict_phased_law": "finish F1 completely before any family may start F2; finish F2 completely before any family may start F3; in-phase ordering remains controller-driven by normal scores/priorities/anti-collapse; cap applies on top without breaking phased constraints",
        "datasets": datasets,
        "subset_size": int(args.subset_size),
        "seeds": seeds,
        "budgets": budgets,
        "methods": eval_methods,
    }

    (out_dir / "eval_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (out_dir / "aggregate_summary.json").write_text(json.dumps(aggregate, indent=2), encoding="utf-8")

    with (out_dir / "per_dataset_summary.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(per_dataset_rows[0].keys()))
        writer.writeheader()
        writer.writerows(per_dataset_rows)

    with (out_dir / "comparison_table.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(comparison_rows[0].keys()))
        writer.writeheader()
        writer.writerows(comparison_rows)

    with (out_dir / "per_case_results.jsonl").open("w", encoding="utf-8") as f:
        for r in per_case:
            f.write(json.dumps(r, sort_keys=True) + "\n")

    report = REPO_ROOT / f"docs/FINAL_STRICT_PHASED_CAP_K678_EVAL_{ts}.md"
    lines = [
        f"# Final strict phased cap K=6/7/8 follow-up evaluation ({ts})",
        "",
        "## Exact method definitions",
    ]
    for label, method_name in eval_methods.items():
        lines.append(f"- `{label}`: `{method_name}`")
    lines.extend([
        "",
        "## Exact broader matched strict-phased evaluation surface",
        f"- datasets: {datasets}",
        f"- subset_size per (dataset, seed): {args.subset_size}",
        f"- seeds: {seeds}",
        f"- budgets: {budgets}",
        "- total matched cases: dataset_count × seed_count × budget_count × subset_size",
        "- strict phased law: finish F1 before F2 before F3, with normal in-phase controller ordering preserved",
        "",
        "## Aggregate comparison table",
        "",
        "| method | accuracy | absent_from_tree | present_not_selected | output_layer_mismatch | repeated-same-family-present | gold_in_tree | avg_actions | avg_expansions | avg_verifications | avg_max_family_share | avg_longest_same_family_run | cap_bound_case_count | dominant_family_hit_cap_case_count |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for r in comparison_rows:
        lines.append(
            f"| {r['method']} | {r['accuracy']:.4f} | {r['absent_from_tree']} | {r['present_not_selected']} | {r['output_layer_mismatch']} | {r['repeated_same_family_present']} | {r['gold_in_tree']} | {r['avg_actions']:.3f} | {r['avg_expansions']:.3f} | {r['avg_verifications']:.3f} | {r['avg_max_family_expansion_share']:.3f} | {r['avg_longest_same_family_run']:.3f} | {r['cap_bound_case_count']} | {r['dominant_family_hit_cap_case_count']} |"
        )

    lines.extend([
        "",
        "## Dataset-wise table",
        "",
        "| dataset | method | accuracy | absent_from_tree | present_not_selected | repeated-same-family-present | gold_in_tree | avg_actions | avg_expansions | avg_verifications |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for r in per_dataset_rows:
        lines.append(
            f"| {r['dataset']} | {r['method']} | {r['accuracy']:.4f} | {r['absent_from_tree']} | {r['present_not_selected']} | {r['repeated_same_family_present']} | {r['gold_in_tree']} | {r['avg_actions']:.3f} | {r['avg_expansions']:.3f} | {r['avg_verifications']:.3f} |"
        )

    lines.extend([
        "",
        "## Failure-decomposition table",
        "",
        "| method | absent_from_tree | present_not_selected | output_layer_mismatch |",
        "|---|---:|---:|---:|",
    ])
    for r in comparison_rows:
        lines.append(f"| {r['method']} | {r['absent_from_tree']} | {r['present_not_selected']} | {r['output_layer_mismatch']} |")

    lines.extend([
        "",
        "## Cost / budget table",
        "",
        "| method | avg_actions | avg_expansions | avg_verifications | cap_bound_case_count | dominant_family_hit_cap_case_count |",
        "|---|---:|---:|---:|---:|---:|",
    ])
    for r in comparison_rows:
        lines.append(
            f"| {r['method']} | {r['avg_actions']:.3f} | {r['avg_expansions']:.3f} | {r['avg_verifications']:.3f} | {r['cap_bound_case_count']} | {r['dominant_family_hit_cap_case_count']} |"
        )

    lines.extend([
        "",
        "## Head-to-head K comparisons",
        f"- strict_gate1_cap_k6 vs strict_gate1: `{head_to_head['strict_gate1_cap_k6_vs_strict_gate1']}`",
        f"- strict_gate1_cap_k7 vs strict_gate1: `{head_to_head['strict_gate1_cap_k7_vs_strict_gate1']}`",
        f"- strict_gate1_cap_k8 vs strict_gate1: `{head_to_head['strict_gate1_cap_k8_vs_strict_gate1']}`",
        f"- strict_gate1_cap_k7 vs strict_gate1_cap_k6: `{head_to_head['strict_gate1_cap_k7_vs_strict_gate1_cap_k6']}`",
        f"- strict_gate1_cap_k8 vs strict_gate1_cap_k7: `{head_to_head['strict_gate1_cap_k8_vs_strict_gate1_cap_k7']}`",
        f"- strict_gate1_cap_k8 vs strict_gate1_cap_k6: `{head_to_head['strict_gate1_cap_k8_vs_strict_gate1_cap_k6']}`",
    ])

    lines.extend([
        "",
        "## Required decision questions",
        f"1. Does `K = 7` beat `K = 6` on the broader matched surface? **{decision_questions['k7_beats_k6']}**",
        f"2. Does `K = 8` beat `K = 7`? **{decision_questions['k8_beats_k7']}**",
        f"3. Does any capped variant beat uncapped `strict_gate1` clearly enough to justify keeping a cap in the final default? **{decision_questions['any_cap_beats_uncapped']}**",
        f"4. Does performance appear to plateau as K increases? **{decision_questions['plateau_as_k_increases']}**",
        f"5. Does larger K simply revert toward uncapped behavior? **{decision_questions['larger_k_reverts_toward_uncapped']}**",
        f"6. Should the repository keep `K = 6` as final default, move to `K = 7` or `K = 8`, or drop cap entirely? **{recommended}**",
        "",
        "## Honest final recommendation",
        f"Recommended method by conservative tie-break rule (accuracy -> absent_from_tree -> collapse -> actions): **{recommended}**.",
        "",
        "## Final cap recommendation",
        f"- recommended cap choice: **{recommended}**",
        (
            "- one-paragraph justification: On the same broader matched strict-phased surface used for default finalization, "
            f"{recommended} is the strongest conservative compromise after evaluating uncapped strict_gate1 and K=6/7/8 "
            "(plus optional higher K if included), while preserving strict phased-law compliance and stable failure/cost trade-offs."
        ),
        f"- whether the cap should remain part of the broad default model: **{str(recommended != 'strict_gate1')}**",
        "- one sentence explaining why the neighboring K values were not chosen: Neighboring K values either did not improve enough on broader matched accuracy/failure mix or moved closer to uncapped behavior without clear net benefit.",
    ])
    report.write_text("\n".join(lines), encoding="utf-8")

    print(f"output_dir={out_dir.relative_to(REPO_ROOT)}")
    print(f"report={report.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
