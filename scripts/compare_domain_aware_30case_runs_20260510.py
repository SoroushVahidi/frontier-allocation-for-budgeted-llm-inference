from __future__ import annotations

import argparse
import collections
import json
import pathlib
import statistics
from typing import Any


def _load_manifest(run_dir: pathlib.Path) -> dict[str, Any]:
    return json.loads((run_dir / "manifest.json").read_text())


def _load_records(run_dir: pathlib.Path) -> dict[str, dict[str, dict[str, Any]]]:
    records: dict[str, dict[str, dict[str, Any]]] = collections.defaultdict(dict)
    with (run_dir / "per_example_records.jsonl").open() as handle:
        for line in handle:
            row = json.loads(line)
            records[str(row["example_id"])][str(row["method"])] = row
    return records


def _mean(values: list[float]) -> float:
    return statistics.mean(values) if values else 0.0


def _summarize_run(records: dict[str, dict[str, dict[str, Any]]], new_method: str) -> dict[str, Any]:
    vals = [entry[new_method] for entry in records.values() if new_method in entry]
    return {
        "exact": int(sum(row["exact_match"] for row in vals)),
        "gold_in_tree": int(sum(row.get("gold_in_tree", 0) for row in vals)),
        "candidate_mean": float(_mean([float(row["result_metadata"].get("candidate_pool_answer_group_count", 0)) for row in vals])),
        "entropy_mean": float(_mean([float(row["result_metadata"].get("answer_group_entropy", 0)) for row in vals])),
        "collapse": int(sum(1 for row in vals if row["result_metadata"].get("frontier_collapse_detected"))),
        "guard_available": int(sum(1 for row in vals if row["result_metadata"].get("regression_guard_available"))),
        "guard_enabled": int(sum(1 for row in vals if row["result_metadata"].get("regression_guard_enabled"))),
        "guard_triggered": int(sum(1 for row in vals if row["result_metadata"].get("regression_guard_triggered"))),
        "domains": collections.Counter(str(row["result_metadata"].get("detected_problem_domain") or "") for row in vals),
        "domain_sources": collections.Counter(str(row["result_metadata"].get("domain_detection_source") or "") for row in vals),
        "ratio_anchor_exec": int(sum(1 for row in vals if "ratio_percentage_anchor" in row["result_metadata"].get("diverse_prompt_anchor_ids_executed", []))),
        "money_anchor_exec": int(sum(1 for row in vals if "unit_ledger_money_anchor" in row["result_metadata"].get("diverse_prompt_anchor_ids_executed", []))),
        "backward_anchor_exec": int(sum(1 for row in vals if "backward_check_anchor" in row["result_metadata"].get("diverse_prompt_anchor_ids_executed", []))),
    }


def compare_runs(run_a: pathlib.Path, run_b: pathlib.Path) -> dict[str, Any]:
    manifest_a = _load_manifest(run_a)
    manifest_b = _load_manifest(run_b)
    records_a = _load_records(run_a)
    records_b = _load_records(run_b)

    case_ids_a = set(records_a)
    case_ids_b = set(records_b)
    methods = sorted({method for per_case in records_a.values() for method in per_case} | {method for per_case in records_b.values() for method in per_case})
    if len(methods) != 2:
        raise RuntimeError(f"Expected exactly 2 methods, found {methods}")
    old_method, new_method = methods

    new_a = {case_id: per_case[new_method] for case_id, per_case in records_a.items() if new_method in per_case}
    new_b = {case_id: per_case[new_method] for case_id, per_case in records_b.items() if new_method in per_case}

    flipped_a_correct_b_wrong: list[str] = []
    flipped_a_wrong_b_correct: list[str] = []
    stable_correct: list[str] = []
    stable_wrong: list[str] = []
    for case_id in sorted(case_ids_a & case_ids_b):
        exact_a = int(new_a[case_id]["exact_match"])
        exact_b = int(new_b[case_id]["exact_match"])
        if exact_a and not exact_b:
            flipped_a_correct_b_wrong.append(case_id)
        elif not exact_a and exact_b:
            flipped_a_wrong_b_correct.append(case_id)
        elif exact_a and exact_b:
            stable_correct.append(case_id)
        else:
            stable_wrong.append(case_id)

    def _case_detail(case_id: str, run: str) -> dict[str, Any]:
        row = new_a[case_id] if run == "A" else new_b[case_id]
        md = row["result_metadata"]
        return {
            "final": row.get("final_answer_canonical"),
            "gold": row.get("gold_answer_canonical"),
            "gold_in_tree": int(row.get("gold_in_tree", 0)),
            "selected_group": md.get("selected_group"),
            "candidate_pool": md.get("selector_candidate_pool_sources", []),
            "answer_group_support_counts": md.get("answer_group_support_counts", {}),
            "anchor_ids": md.get("diverse_prompt_anchor_ids_executed", []),
            "anchor_metadata": md.get("diverse_prompt_anchor_metadata", []),
            "entropy": md.get("answer_group_entropy"),
            "collapse": md.get("frontier_collapse_detected"),
            "guard_available": md.get("regression_guard_available"),
            "guard_enabled": md.get("regression_guard_enabled"),
            "guard_triggered": md.get("regression_guard_triggered"),
            "guard_reason": md.get("regression_guard_reason"),
        }

    return {
        "manifest_a": manifest_a,
        "manifest_b": manifest_b,
        "same_case_ids": case_ids_a == case_ids_b,
        "same_methods": set(methods) == set(manifest_a.get("methods", [])) == set(manifest_b.get("methods", [])),
        "same_budget": manifest_a.get("budgets") == manifest_b.get("budgets"),
        "same_seed": manifest_a.get("seeds") == manifest_b.get("seeds"),
        "same_provider": manifest_a.get("providers") == manifest_b.get("providers"),
        "same_dataset": manifest_a.get("datasets") == manifest_b.get("datasets"),
        "old_method": old_method,
        "new_method": new_method,
        "run_a_summary": _summarize_run(records_a, new_method),
        "run_b_summary": _summarize_run(records_b, new_method),
        "cases": {
            "a_correct_b_wrong": flipped_a_correct_b_wrong,
            "a_wrong_b_correct": flipped_a_wrong_b_correct,
            "stable_correct": stable_correct,
            "stable_wrong": stable_wrong,
        },
        "details": {
            case_id: {
                "A": _case_detail(case_id, "A"),
                "B": _case_detail(case_id, "B"),
            }
            for case_id in sorted(set(flipped_a_correct_b_wrong + flipped_a_wrong_b_correct))
        },
        "logical_calls": {
            "A": int(sum(row.get("cohere_logical_api_calls", 0) for row in new_a.values())),
            "B": int(sum(row.get("cohere_logical_api_calls", 0) for row in new_b.values())),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare two domain-aware 30-case Cohere runs.")
    parser.add_argument("run_a", type=pathlib.Path)
    parser.add_argument("run_b", type=pathlib.Path)
    parser.add_argument("--markdown", action="store_true", help="Emit markdown instead of JSON.")
    args = parser.parse_args()
    summary = compare_runs(args.run_a, args.run_b)
    if not args.markdown:
        print(json.dumps(summary, indent=2, sort_keys=True))
        return

    print("# Domain-Aware 30-Case Run Stability Comparison")
    print()
    print(f"- Same case IDs: `{summary['same_case_ids']}`")
    print(f"- Same methods: `{summary['same_methods']}`")
    print(f"- Same budget: `{summary['same_budget']}`")
    print(f"- Same seed: `{summary['same_seed']}`")
    print(f"- Same provider: `{summary['same_provider']}`")
    print(f"- Same dataset: `{summary['same_dataset']}`")
    print()
    print("## New-Method Summary")
    for label, run_key in [("Run A", "run_a_summary"), ("Run B", "run_b_summary")]:
        s = summary[run_key]
        print(f"- {label} exact: `{s['exact']}/30`")
        print(f"- {label} gold-in-tree: `{s['gold_in_tree']}/30`")
        print(f"- {label} mean answer groups: `{s['candidate_mean']:.3f}`")
        print(f"- {label} mean entropy: `{s['entropy_mean']:.3f}`")
        print(f"- {label} collapse: `{s['collapse']}/30`")
        print(f"- {label} guard available/enabled/triggered: `{s['guard_available']}/{s['guard_enabled']}/{s['guard_triggered']}`")
    print()
    print("## Flips")
    print(f"- Correct in Run A, wrong in Run B: `{summary['cases']['a_correct_b_wrong']}`")
    print(f"- Wrong in Run A, correct in Run B: `{summary['cases']['a_wrong_b_correct']}`")


if __name__ == "__main__":
    main()
